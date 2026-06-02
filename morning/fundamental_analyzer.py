"""
基本面量化评分模块
对 A 股个股进行 5 维度量化评分：盈利能力、成长性、估值安全、财务健康、股价动能
每个维度 0-10 分，加权汇总为总分（满分 100）
"""

import logging
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional

import akshare as ak
import pandas as pd

from .ai_analyzer import StockRecommendation

logger = logging.getLogger(__name__)

# ============================================================
# 评分阈值与权重
# ============================================================

# 各财务指标的评分阈值 (best, worst)，用于线性映射到 0-10 分
_THRESHOLDS = {
    "roe": (20.0, 0.0, True),
    "gross_margin": (40.0, 10.0, True),
    "roa": (10.0, 0.0, True),
    "revenue_growth": (20.0, -10.0, True),
    "profit_growth": (20.0, -20.0, True),
    "debt_ratio": (40.0, 80.0, False),
    "current_ratio": (2.0, 0.8, True),
    "turnover_rate": (5.0, 0.5, True),
}

# 维度权重（总和为 10，乘以维度分后得总分满分 100）
_DIM_WEIGHTS = {
    "盈利能力": 0.25,
    "成长性": 0.20,
    "估值安全": 0.25,
    "财务健康": 0.20,
    "股价动能": 0.10,
}


# ============================================================
# 工具函数
# ============================================================

def _linear_scale(value, best, worst, higher_is_better=True):
    """
    线性映射函数，将 value 从 [worst, best] 映射到 [0, 10]
    若 higher_is_better=False，则 best 对应 10 分但方向反转
    值在区间外则截断到 [0, 10]
    """
    if value is None:
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        return 0.0

    if higher_is_better:
        if value >= best:
            return 10.0
        if value <= worst:
            return 0.0
        return (value - worst) / (best - worst) * 10.0
    else:
        # 反向：值越小越好
        if value <= best:
            return 10.0
        if value >= worst:
            return 0.0
        return (worst - value) / (worst - best) * 10.0


# ============================================================
# 数据获取
# ============================================================

def _parse_float(val) -> Optional[float]:
    """安全解析浮点数，无效值返回 None"""
    if val is None:
        return None
    try:
        s = str(val).replace("%", "").replace("元", "").replace(",", "").strip()
        if s in ("--", "", "None", "nan"):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _fetch_financial_indicators(code: str) -> dict:
    """
    从 akshare 获取个股财务指标
    返回 dict，包含 roe, gross_margin, roa, revenue_growth, profit_growth,
    debt_ratio, current_ratio
    获取失败时相关指标为 None
    """
    try:
        # 获取财务分析指标（最新一期）
        df = ak.stock_financial_analysis_indicator(symbol=code)
        if df is None or df.empty:
            logger.warning("[%s] 财务指标数据为空", code)
            return {}

        # 取最新一期（第一行）
        latest = df.iloc[0]

        data = {
            "roe":            _parse_float(latest.get("净资产收益率")),
            "gross_margin":   _parse_float(latest.get("毛利率")),
            "roa":            _parse_float(latest.get("总资产报酬率")),
            "revenue_growth": _parse_float(latest.get("营业收入同比增长率")),
            "profit_growth":  _parse_float(latest.get("净利润同比增长率")),
            "debt_ratio":     _parse_float(latest.get("资产负债率")),
            "current_ratio":  _parse_float(latest.get("流动比率")),
        }
        logger.debug("[%s] 财务指标: %s", code, data)
        return data

    except ImportError:
        logger.error("akshare 未安装，无法获取财务指标")
        return {}
    except Exception as e:
        logger.warning("[%s] 获取财务指标失败: %s", code, e)
        return {}


@lru_cache(maxsize=1)
def _fetch_all_spot_data() -> pd.DataFrame:
    """获取全市场实时行情（缓存，每次晨报流程只请求一次）"""
    return ak.stock_zh_a_spot_em()


def _fetch_spot_data(code: str) -> dict:
    """
    从 akshare 获取个股实时行情指标（PE, PB, 总市值等）
    """
    result = {}
    try:
        df = _fetch_all_spot_data()
        row = df[df["代码"] == code]
        if row.empty:
            logger.warning("未找到股票 [%s] 的实时行情", code)
            return result
        r = row.iloc[0]
        result["pe"] = _parse_float(r.get("市盈率-动态"))
        result["pb"] = _parse_float(r.get("市净率"))
        result["total_mv"] = _parse_float(r.get("总市值"))
        result["name"] = str(r.get("名称", ""))
    except Exception as e:
        logger.warning("实时行情获取失败 [%s]: %s", code, e)
    return result


def _fetch_hist_price(code: str) -> pd.DataFrame:
    """
    获取近 5 年日线数据（前复权）
    用于计算 PE 历史百分位和股价动量
    """
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=365 * 5)).strftime("%Y%m%d")

        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",  # 前复权
        )
        if df is None or df.empty:
            logger.warning("[%s] 历史日线数据为空", code)
            return pd.DataFrame()

        # 确保日期列为 datetime 类型并排序
        date_col = "日期" if "日期" in df.columns else "date"
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col)

        logger.debug("[%s] 获取到 %d 条日线记录", code, len(df))
        return df

    except ImportError:
        logger.error("akshare 未安装，无法获取历史日线")
        return pd.DataFrame()
    except Exception as e:
        logger.warning("[%s] 获取历史日线失败: %s", code, e)
        return pd.DataFrame()


@lru_cache(maxsize=1)
def _fetch_eps_data(date: str) -> pd.DataFrame:
    """获取指定日期的业绩报表（缓存）"""
    return ak.stock_yjbb_em(date=date)


def _calc_pe_percentile(code: str, spot_pe: Optional[float],
                        hist_df: pd.DataFrame) -> Optional[float]:
    """
    计算 PE 在近 5 年中的历史百分位
    使用 price/EPS 计算每期 PE，再与当前 PE 比较
    """
    if spot_pe is None or spot_pe <= 0 or hist_df.empty:
        return None
    try:
        yjbb = _fetch_eps_data(date=datetime.now().strftime("%Y%m%d"))
        eps_row = yjbb[yjbb["股票代码"] == code]
        if eps_row.empty:
            year = datetime.now().year
            yjbb = _fetch_eps_data(date=f"{year-1}1231")
            eps_row = yjbb[yjbb["股票代码"] == code]
        if eps_row.empty:
            return None
        eps = _parse_float(eps_row.iloc[0].get("每股收益"))
        if eps is None or eps <= 0:
            return None
        hist_df = hist_df.dropna(subset=["收盘"])
        hist_pe = hist_df["收盘"] / eps
        if hist_pe.empty:
            return None
        below_count = (hist_pe <= spot_pe).sum()
        total = len(hist_pe)
        if total == 0:
            return None
        return round(below_count / total * 100, 1)
    except Exception as e:
        logger.warning("PE 百分位计算失败 [%s]: %s", code, e)
        return None


# ============================================================
# 各维度评分函数
# ============================================================

def _calc_profitability(data: dict) -> tuple:
    """
    盈利能力评分
    指标：ROE, 毛利率, ROA

    Returns:
        (score_0_to_10, desc, highlight)
    """
    scores = []
    details = []

    for key, label in [("roe", "ROE"), ("gross_margin", "毛利率"), ("roa", "ROA")]:
        v = data.get(key)
        s = _linear_scale(v, *_THRESHOLDS[key])
        scores.append(s)
        if v is not None:
            details.append(f"{label}={v:.1f}%")

    valid_scores = [s for s in scores if s is not None]
    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 5.0

    # 生成描述
    desc = "盈利能力 " + ", ".join(details) if details else "盈利能力 数据不足"

    # 提取亮点
    highlights = []
    roe = data.get("roe")
    if roe is not None and roe >= 15:
        highlights.append(f"ROE {roe:.1f}% 优秀")
    elif roe is not None and roe >= 10:
        highlights.append(f"ROE {roe:.1f}% 良好")
    gm = data.get("gross_margin")
    if gm is not None and gm >= 50:
        highlights.append(f"毛利率 {gm:.1f}% 优秀")

    highlight = "；".join(highlights) if highlights else ""
    return round(avg_score, 1), desc, highlight


def _calc_growth(data: dict) -> tuple:
    """
    成长性评分
    指标：营收增速, 净利润增速

    Returns:
        (score_0_to_10, desc, highlight)
    """
    scores = []
    details = []

    for key, label in [("revenue_growth", "营收增速"), ("profit_growth", "净利增速")]:
        v = data.get(key)
        s = _linear_scale(v, *_THRESHOLDS[key])
        scores.append(s)
        if v is not None:
            details.append(f"{label}={v:.1f}%")

    valid_scores = [s for s in scores if s is not None]
    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 5.0
    desc = "成长性 " + ", ".join(details) if details else "成长性 数据不足"

    highlights = []
    rv = data.get("revenue_growth")
    pv = data.get("profit_growth")
    if rv is not None and rv >= 20:
        highlights.append(f"营收增长 {rv:.1f}% 高增长")
    if pv is not None and pv >= 20:
        highlights.append(f"净利增长 {pv:.1f}% 高增长")
    elif pv is not None and pv < -10:
        highlights.append(f"净利下滑 {pv:.1f}%")

    highlight = "；".join(highlights) if highlights else ""
    return round(avg_score, 1), desc, highlight


def _calc_valuation(pe_pct: Optional[float], pb: Optional[float]) -> tuple:
    """
    估值安全评分
    指标：PE 历史百分位（越低越好）, PB（越低越好）

    Returns:
        (score_0_to_10, desc, highlight)
    """
    scores = []
    details = []

    # PE 百分位评分（值越小越好）
    s_pe = _linear_scale(pe_pct, 30.0, 80.0, higher_is_better=False)
    scores.append(s_pe)
    if pe_pct is not None:
        if pe_pct <= 20:
            details.append("PE处于历史低位(<=20%)")
        elif pe_pct <= 50:
            details.append("PE处于历史中位")
        else:
            details.append("PE处于历史高位")

    # PB 评分（值越小越好）
    s_pb = _linear_scale(pb, 1.5, 8.0, higher_is_better=False)
    scores.append(s_pb)
    if pb is not None:
        details.append(f"PB={pb:.2f}")

    valid_scores = [s for s in scores if s is not None]
    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 5.0
    desc = "估值 " + ", ".join(details) if details else "估值 数据不足"

    highlights = []
    if pe_pct is not None and pe_pct <= 20:
        highlights.append("PE处于近5年低位")
    if pb is not None and pb <= 2:
        highlights.append(f"PB {pb:.2f} 较低")

    highlight = "；".join(highlights) if highlights else ""
    return round(avg_score, 1), desc, highlight


def _calc_financial_health(data: dict) -> tuple:
    """
    财务健康评分
    指标：资产负债率, 流动比率

    Returns:
        (score_0_to_10, desc, highlight)
    """
    scores = []
    details = []

    # 负债率评分（越低越好）
    debt = data.get("debt_ratio")
    s_debt = _linear_scale(debt, *_THRESHOLDS["debt_ratio"])
    scores.append(s_debt)
    if debt is not None:
        details.append(f"负债率={debt:.1f}%")

    # 流动比率评分
    cr = data.get("current_ratio")
    s_cr = _linear_scale(cr, *_THRESHOLDS["current_ratio"])
    scores.append(s_cr)
    if cr is not None:
        details.append(f"流动比率={cr:.2f}")

    valid_scores = [s for s in scores if s is not None]
    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 5.0
    desc = "财务健康 " + ", ".join(details) if details else "财务健康 数据不足"

    highlights = []
    if debt is not None and debt <= 30:
        highlights.append(f"负债率 {debt:.1f}% 很低")
    elif debt is not None and debt >= 70:
        highlights.append(f"负债率 {debt:.1f}% 偏高")
    if cr is not None and cr >= 2:
        highlights.append(f"流动比率 {cr:.2f} 充裕")

    highlight = "；".join(highlights) if highlights else ""
    return round(avg_score, 1), desc, highlight


def _calc_momentum(hist_df: pd.DataFrame) -> tuple:
    """
    股价动能评分
    指标：60日涨跌幅, 换手率

    Returns:
        (score_0_to_10, desc, highlight)
    """
    scores = []
    details = []
    highlights = []

    # --- 60日涨跌幅 ---
    mom_60d = None
    close_col = "收盘" if "收盘" in hist_df.columns else "close"
    if not hist_df.empty and close_col in hist_df.columns:
        prices = hist_df[close_col].dropna()
        if len(prices) >= 60:
            mom_60d = (prices.iloc[-1] - prices.iloc[-60]) / prices.iloc[-60] * 100
        elif len(prices) > 1:
            # 数据不足60日，用全部区间近似
            mom_60d = (prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0] * 100

    s_mom = _linear_scale(mom_60d, 20.0, -20.0)
    scores.append(s_mom)
    if mom_60d is not None:
        direction = "上涨" if mom_60d >= 0 else "下跌"
        details.append(f"60日{direction}={abs(mom_60d):.1f}%")
        if mom_60d > 10:
            highlights.append(f"60日涨幅 {mom_60d:.1f}% 强势")
        elif mom_60d < -15:
            highlights.append(f"60日跌幅 {abs(mom_60d):.1f}% 弱势")

    # --- 换手率 ---
    turnover = None
    turnover_col = "换手率" if "换手率" in hist_df.columns else None
    if turnover_col and not hist_df.empty:
        tv_series = hist_df[turnover_col].dropna()
        if not tv_series.empty:
            turnover = tv_series.iloc[-1]

    s_turn = _linear_scale(turnover, *_THRESHOLDS["turnover_rate"])
    scores.append(s_turn)
    if turnover is not None:
        details.append(f"换手率={turnover:.2f}%")

    valid_scores = [s for s in scores if s is not None]
    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 5.0
    desc = "动能 " + ", ".join(details) if details else "动能 数据不足"

    highlight = "；".join(highlights) if highlights else ""
    return round(avg_score, 1), desc, highlight


# ============================================================
# 综合评分主函数
# ============================================================

def score_stock(code: str, name: str) -> Optional[dict]:
    """
    对单只股票进行完整的 5 维度基本面评分

    Args:
        code: 股票代码 (如 "600519")
        name: 股票名称 (如 "贵州茅台")

    Returns:
        包含各维度评分及总分的 dict；若关键数据全部缺失则返回 None
        返回结构：
        {
            "code": str,
            "name": str,
            "total": float,              # 加权总分 (0-100)
            "dimensions": {
                "盈利能力": {"score": float, "desc": str, "hl": str},
                "成长性":   {"score": float, "desc": str, "hl": str},
                "估值安全":  {"score": float, "desc": str, "hl": str},
                "财务健康":  {"score": float, "desc": str, "hl": str},
                "股价动能":  {"score": float, "desc": str, "hl": str},
            },
            "summary": str,              # 一句话总结
        }
    """
    logger.info("开始评分: %s (%s)", name, code)

    # 1. 并行获取各类数据
    fin_data = _fetch_financial_indicators(code)
    spot_data = _fetch_spot_data(code)
    hist_df = _fetch_hist_price(code)

    # 2. 计算 PE 历史百分位
    pe_pct = _calc_pe_percentile(code, spot_data.get("pe"), hist_df)

    # 3. 各维度评分
    dims = {}

    dims["盈利能力"] = _calc_profitability(fin_data)
    dims["成长性"] = _calc_growth(fin_data)
    dims["估值安全"] = _calc_valuation(pe_pct, spot_data.get("pb"))
    dims["财务健康"] = _calc_financial_health(fin_data)
    dims["股价动能"] = _calc_momentum(hist_df)

    # 4. 加权总分
    total = 0.0
    total_weight = 0.0
    for key, weight in _DIM_WEIGHTS.items():
        dim_score = dims[key][0]
        total += dim_score * weight
        total_weight += weight

    if total_weight == 0:
        return None

    # 归一化到 0-100 分（维度分 0-10 × 权重 → 加权得分 × 10）
    total_100 = round(total / total_weight / 10 * 100)

    # 5. 提炼总结
    summary = _build_summary(dims)

    # 6. 组装结果
    result = {
        "code": code,
        "name": name,
        "total": total_100,
        "dimensions": {},
    }
    for key, (score, desc, hl) in dims.items():
        result["dimensions"][key] = {
            "score": score,
            "desc": desc,
            "hl": hl,
        }
    result["summary"] = summary

    logger.info("[%s] %s 总分: %d/100 — %s", code, name, total_100, summary)
    return result


def _build_summary(dims: dict) -> str:
    """
    根据各维度得分提炼一句话核心逻辑

    Args:
        dims: 维度字典 {key: (score, desc, highlight)}

    Returns:
        一句话总结字符串
    """
    scores = {k: v[0] for k, v in dims.items()}
    total = sum(scores[k] * _DIM_WEIGHTS[k] for k in scores)
    # 归一化到 0-100
    total = total / sum(_DIM_WEIGHTS.get(k, 0) for k in scores) / 10 * 100

    # 找出最强和最弱维度
    sorted_dims = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_dim, best_score = sorted_dims[0]
    worst_dim, worst_score = sorted_dims[-1]

    parts = []
    if total >= 70:
        parts.append(f"总分 {total:.1f}/100，基本面优秀")
    elif total >= 50:
        parts.append(f"总分 {total:.1f}/100，基本面中等偏上")
    elif total >= 30:
        parts.append(f"总分 {total:.1f}/100，基本面一般")
    else:
        parts.append(f"总分 {total:.1f}/100，基本面偏弱")

    parts.append(f"最强维度: {best_dim}({best_score:.1f}分)")
    parts.append(f"最弱维度: {worst_dim}({worst_score:.1f}分)")

    return "，".join(parts)


def _fmt_score(score: Optional[float]) -> str:
    """格式化分数显示，带颜色指示"""
    if score is None:
        return " -/10"
    s = round(score, 1)
    if s >= 7:
        return f"\U0001f7e2{s:.1f}"  # 🟢
    elif s >= 4:
        return f"\U0001f7e1{s:.1f}"  # 🟡
    return f"\U0001f534{s:.1f}"  # 🔴


def score_recommended_stocks(stocks: list[StockRecommendation]) -> str:
    """
    对 AI 推荐的所有股票逐一评分，生成 Markdown 段落

    Args:
        stocks: StockRecommendation 对象列表

    Returns:
        Markdown 格式的评分表格字符串
    """
    if not stocks:
        return ""

    lines = []
    lines.append("---")
    lines.append("### 基本面量化评分")
    lines.append("")
    lines.append(
        "| 股票 | 总分 | 盈利 | 成长 | 估值 | 财务 | 动能 | 核心观点 |"
    )
    lines.append(
        "|------|:----:|:----:|:----:|:----:|:----:|:----:|----------|"
    )

    has_valid = False

    for st in stocks:
        if not st.code:
            continue

        result = score_stock(st.code, st.name)
        if result is None:
            continue

        has_valid = True
        dim = result["dimensions"]
        dim_scores = {k: dim[k]["score"] for k in _DIM_WEIGHTS}

        scores_str = "|".join(
            _fmt_score(dim_scores.get(k))
            for k in _DIM_WEIGHTS
        )

        total_str = str(result["total"])
        name_display = f"{st.name}({st.code})" if st.name else st.code

        lines.append(
            f"| **{name_display}** | **{total_str}** | {scores_str} "
            f"| {result['summary']} |"
        )
        lines.append("")

        # 补充 AI 推荐理由
        if st.reason:
            lines.append(f"  > AI 推荐理由：{st.reason}")
            lines.append("")

    if not has_valid:
        return ""

    return "\n".join(lines)
