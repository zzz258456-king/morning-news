# 晨报基本面评分模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在晨报推荐股票后，自动从 akshare 拉取财务数据做 5 维度量化评分（0-100分），追加到钉钉推送中。

**Architecture:** 新增 `morning/fundamental_analyzer.py` 作为独立评分模块，main.py 的 cmd_morning() 在获取 AI 分析结果后自动调用评分并追加到消息体尾部。

**Tech Stack:** Python 3.10+, akshare（已安装）, pandas

---

### Task 1: 创建 morning/fundamental_analyzer.py — 量化评分核心

**Files:**
- Create: `morning/fundamental_analyzer.py`

- [ ] **Step 1: 创建模块框架和线性评分工具函数**

```python
"""
基本面量化评分模块
在晨报推荐个股后，自动拉取 AKShare 财务数据做 5 维度评分

评分模型：
  盈利能力(25%) + 成长性(20%) + 估值安全(25%)
  + 财务健康(20%) + 股价动能(10%)  →  总分 0-100
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from .ai_analyzer import StockRecommendation

logger = logging.getLogger(__name__)

# ---------- 评分阈值 ----------

_THRESHOLDS = {
    # (指标名, 满分阈值, 0分阈值, 是否越大越好)
    "roe": (20.0, 0.0, True),          # ROE %
    "gross_margin": (40.0, 10.0, True), # 毛利率 %
    "roa": (10.0, 0.0, True),          # ROA %
    "revenue_growth": (20.0, -10.0, True),   # 营收增速 %
    "profit_growth": (20.0, -20.0, True),    # 净利润增速 %
    "debt_ratio": (40.0, 80.0, False),       # 资产负债率 %
    "current_ratio": (2.0, 0.8, True),       # 流动比率
    "turnover_rate": (5.0, 0.5, True),       # 日均换手率 %
}

# 维度权重
_DIM_WEIGHTS = {
    "盈利能力": 0.25,
    "成长性": 0.20,
    "估值安全": 0.25,
    "财务健康": 0.20,
    "股价动能": 0.10,
}


def _linear_scale(value, best, worst, higher_is_better=True):
    """
    线性映射: value 在 [worst, best] 之间映射到 [0, 10]
    超出边界则截断到 0 或 10
    """
    if value is None:
        return None
    lo, hi = (worst, best) if higher_is_better else (best, worst)
    if value >= hi:
        return 10.0
    if value <= lo:
        return 0.0
    return round((value - lo) / (hi - lo) * 10, 1)
```

- [ ] **Step 2: 实现数据获取函数**

```python
def _fetch_financial_indicators(code: str) -> dict:
    """
    从 akshare 获取财务分析指标
    包含: ROE, 毛利率, ROA, 资产负债率, 流动比率, 营收增速, 净利润增速
    返回 dict 或 None（全部失败时）
    """
    import akshare as ak
    result = {}

    try:
        df = ak.stock_financial_analysis_indicator(stock=code)
        if df is not None and not df.empty:
            latest = df.iloc[0]
            # 盈利能力
            result["roe"] = _parse_float(latest.get("净资产收益率"))
            result["gross_margin"] = _parse_float(latest.get("毛利率"))
            result["roa"] = _parse_float(latest.get("总资产报酬率"))
            # 财务健康
            result["debt_ratio"] = _parse_float(latest.get("资产负债率"))
            result["current_ratio"] = _parse_float(latest.get("流动比率"))
            # 成长性（同比增速字段）
            result["revenue_growth"] = _parse_float(latest.get("营业收入同比增长率"))
            result["profit_growth"] = _parse_float(latest.get("净利润同比增长率"))
    except Exception as e:
        logger.warning("财务指标获取失败 [%s]: %s", code, e)
        return None

    if not result:
        return None
    return result


def _parse_float(val):
    """安全解析浮点数，处理 akshare 可能返回的字符串、None 等"""
    if val is None:
        return None
    try:
        # akshare 数据可能是 "-3.2172%" 这种格式
        s = str(val).replace("%", "").replace("元", "").replace(",", "").strip()
        if s in ("--", "", "None", "nan"):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _fetch_spot_data(code: str) -> dict:
    """
    从 akshare 获取实时行情（含 PE, PB, 总市值）
    """
    import akshare as ak
    result = {}
    try:
        df = ak.stock_zh_a_spot_em()
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
    获取近 5 年日线行情（前复权），用于 PE 历史百分位和股价动能
    """
    import akshare as ak
    try:
        start = (datetime.now() - timedelta(days=5*365)).strftime("%Y%m%d")
        end = datetime.now().strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                 start_date=start, end_date=end, adjust="qfq")
        if df is not None and not df.empty:
            df["日期"] = pd.to_datetime(df["日期"])
            df = df.sort_values("日期")
            return df
    except Exception as e:
        logger.warning("历史行情获取失败 [%s]: %s", code, e)
    return pd.DataFrame()


def _calc_pe_percentile(code: str, spot_pe: float, hist_df: pd.DataFrame) -> Optional[float]:
    """
    计算 PE 在近 5 年中的历史百分位
    使用每日收盘价 / 最新EPS 估算每日PE
    若无法计算返回 None（表示无数据）
    """
    if spot_pe is None or spot_pe <= 0 or hist_df.empty:
        return None
    # 用当前 PE 反推 EPS
    try:
        # 获取最近一期每股收益
        import akshare as ak
        yjbb = ak.stock_yjbb_em(date=datetime.now().strftime("%Y%m%d"))
        eps_row = yjbb[yjbb["股票代码"] == code]
        if eps_row.empty:
            # 使用最新年报
            year = datetime.now().year
            yjbb = ak.stock_yjbb_em(date=f"{year-1}1231")
            eps_row = yjbb[yjbb["股票代码"] == code]
        if eps_row.empty:
            return None
        eps = _parse_float(eps_row.iloc[0].get("每股收益"))
        if eps is None or eps <= 0:
            return None

        # 历史收盘价 * 最新EPS 近似历史 PE
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
```

- [ ] **Step 3: 实现各维度评分函数**

```python
def _calc_profitability(data: dict) -> tuple[float, str, str]:
    """
    盈利能力评分 (权重25%)
    使用 ROE, 毛利率, ROA 三项等权

    Returns:
        (score_0_to_10, 维度描述, 核心亮点)
    """
    roe = data.get("roe")
    gm = data.get("gross_margin")
    roa = data.get("roa")
    scores = []
    labels = []

    if roe is not None:
        s = _linear_scale(roe, *_THRESHOLDS["roe"])
        if s is not None:
            scores.append(s)
            labels.append(f"ROE {roe:.1f}%")
    if gm is not None:
        s = _linear_scale(gm, *_THRESHOLDS["gross_margin"])
        if s is not None:
            scores.append(s)
            labels.append(f"毛利 {gm:.1f}%")
    if roa is not None:
        s = _linear_scale(roa, *_THRESHOLDS["roa"])
        if s is not None:
            scores.append(s)
            labels.append(f"ROA {roa:.1f}%")

    if not scores:
        return 5.0, "无数据", ""
    avg = round(sum(scores) / len(scores), 1)
    # 取最突出的指标作描述
    if avg >= 7:
        desc = "盈利强劲"
    elif avg >= 4:
        desc = "盈利一般"
    else:
        desc = "盈利偏弱"
    highlight = "、".join(labels[:2])
    return avg, desc, highlight


def _calc_growth(data: dict) -> tuple[float, str, str]:
    """
    成长性评分 (权重20%)
    使用营收增速、净利润增速
    """
    rev = data.get("revenue_growth")
    prof = data.get("profit_growth")
    scores = []
    labels = []

    if rev is not None:
        s = _linear_scale(rev, *_THRESHOLDS["revenue_growth"])
        if s is not None:
            scores.append(s)
            labels.append(f"营收 {rev:+.1f}%")
    if prof is not None:
        s = _linear_scale(prof, *_THRESHOLDS["profit_growth"])
        if s is not None:
            scores.append(s)
            labels.append(f"净利 {prof:+.1f}%")

    if not scores:
        return 5.0, "无数据", ""
    avg = round(sum(scores) / len(scores), 1)
    if avg >= 7:
        desc = "高成长"
    elif avg >= 4:
        desc = "稳健增长"
    else:
        desc = "增长乏力"
    hl = "、".join(labels)
    return avg, desc, hl


def _calc_valuation(pe_pct: Optional[float], pb: Optional[float]) -> tuple[float, str, str]:
    """
    估值安全评分 (权重25%)
    使用 PE 历史百分位 + PB
    """
    scores = []
    labels = []

    if pe_pct is not None:
        # PE 百分位越低越好（低估）
        s = _linear_scale(pe_pct, 20.0, 80.0, higher_is_better=False)
        if s is not None:
            scores.append(s)
            labels.append(f"PE处于{pe_pct:.0f}%分位")
    if pb is not None:
        if 1 <= pb <= 3:
            s = 10.0
        elif 3 < pb <= 5:
            s = 7.0
        elif 0 < pb < 1:
            s = 4.0
        elif 5 < pb <= 8:
            s = 3.0
        else:
            s = 0.0
        scores.append(s)
        labels.append(f"PB {pb:.1f}")

    if not scores:
        return 5.0, "无数据", ""
    avg = round(sum(scores) / len(scores), 1)
    if avg >= 7:
        desc = "估值偏低"
    elif avg >= 4:
        desc = "估值合理"
    else:
        desc = "估值偏高"
    hl = "、".join(labels)
    return avg, desc, hl


def _calc_financial_health(data: dict) -> tuple[float, str, str]:
    """
    财务健康评分 (权重20%)
    使用资产负债率、流动比率
    """
    dr = data.get("debt_ratio")
    cr = data.get("current_ratio")
    scores = []
    labels = []

    if dr is not None:
        s = _linear_scale(dr, *_THRESHOLDS["debt_ratio"])
        if s is not None:
            scores.append(s)
            labels.append(f"负债率 {dr:.1f}%")
    if cr is not None:
        s = _linear_scale(cr, *_THRESHOLDS["current_ratio"])
        if s is not None:
            scores.append(s)
            labels.append(f"流动比率 {cr:.1f}")

    if not scores:
        return 5.0, "无数据", ""
    avg = round(sum(scores) / len(scores), 1)
    if avg >= 7:
        desc = "财务健康"
    elif avg >= 4:
        desc = "财务一般"
    else:
        desc = "财务风险偏高"
    hl = "、".join(labels)
    return avg, desc, hl


def _calc_momentum(hist_df: pd.DataFrame) -> tuple[float, str, str]:
    """
    股价动能评分 (权重10%)
    使用近60日涨跌幅 + 日均换手率
    """
    if hist_df.empty or len(hist_df) < 20:
        return 5.0, "数据不足", ""
    scores = []
    labels = []

    # 近60日涨跌幅
    recent = hist_df.tail(60)
    if len(recent) >= 20:
        pct_change = (recent["收盘"].iloc[-1] / recent["收盘"].iloc[0] - 1) * 100
        if pct_change >= 30:
            s = 0.0  # 过热
            labels.append(f"60日+{pct_change:.0f}%(过热)")
        elif pct_change >= 15:
            s = 5.0
            labels.append(f"60日+{pct_change:.0f}%")
        elif pct_change >= 5:
            # 最佳区间 5%-15%
            s = _linear_scale(pct_change, 15.0, 5.0, higher_is_better=True)
            labels.append(f"60日+{pct_change:.0f}%")
        elif pct_change >= -15:
            s = _linear_scale(pct_change, 5.0, -15.0, higher_is_better=True)
            labels.append(f"60日{pct_change:+.0f}%")
        else:
            s = 0.0
            labels.append(f"60日{pct_change:.0f}%(深跌)")
        scores.append(s)

    # 日均换手率
    if "换手率" in recent.columns:
        avg_turnover = recent["换手率"].mean()
        if avg_turnover is not None and not pd.isna(avg_turnover):
            if 2 <= avg_turnover <= 8:
                s = 10.0
            elif avg_turnover < 0.5:
                s = 0.0
            elif avg_turnover < 2:
                s = _linear_scale(avg_turnover, *_THRESHOLDS["turnover_rate"])
            elif avg_turnover > 20:
                s = 0.0
            else:
                s = _linear_scale(avg_turnover, 8.0, 20.0, higher_is_better=False)
            scores.append(s)
            labels.append(f"换手 {avg_turnover:.1f}%")

    if not scores:
        return 5.0, "无数据", ""
    avg = round(sum(scores) / len(scores), 1)
    if avg >= 7:
        desc = "趋势良好"
    elif avg >= 4:
        desc = "走势平淡"
    else:
        desc = "需警惕"
    hl = "、".join(labels[:2])
    return avg, desc, hl
```

- [ ] **Step 4: 实现综合评分主函数和 Markdown 生成**

```python
def score_stock(code: str, name: str) -> dict:
    """
    对单只股票进行完整的基本面评分

    Args:
        code: 股票代码，如 "600519"
        name: 股票名称，如 "贵州茅台"

    Returns:
        {
            "code": str, "name": str, "total": int(0-100),
            "dimensions": { "盈利能力": {"score": float, "desc": str, "hl": str}, ... },
            "summary": str  # 一句话核心逻辑
        }
        或 None（全部数据不可用时）
    """
    # 1. 拉取数据
    fin = _fetch_financial_indicators(code)
    spot = _fetch_spot_data(code)
    hist = _fetch_hist_price(code)

    # 用行情中的名称覆盖
    display_name = spot.get("name", name) if spot else name

    # 2. PE 历史百分位
    pe_pct = _calc_pe_percentile(code, spot.get("pe"), hist) if spot else None

    # 3. 各维度评分
    dims = {}
    profit_score, profit_desc, profit_hl = _calc_profitability(fin or {})
    dims["盈利能力"] = {"score": profit_score, "desc": profit_desc, "hl": profit_hl}

    growth_score, growth_desc, growth_hl = _calc_growth(fin or {})
    dims["成长性"] = {"score": growth_score, "desc": growth_desc, "hl": growth_hl}

    val_score, val_desc, val_hl = _calc_valuation(pe_pct, spot.get("pb"))
    dims["估值安全"] = {"score": val_score, "desc": val_desc, "hl": val_hl}

    health_score, health_desc, health_hl = _calc_financial_health(fin or {})
    dims["财务健康"] = {"score": health_score, "desc": health_desc, "hl": health_hl}

    mom_score, mom_desc, mom_hl = _calc_momentum(hist)
    dims["股价动能"] = {"score": mom_score, "desc": mom_desc, "hl": mom_hl}

    # 4. 综合加权（可用维度重新归一化权重）
    total_weight = 0
    weighted_sum = 0
    for dim_name, w in _DIM_WEIGHTS.items():
        d = dims.get(dim_name)
        if d and d["score"] is not None:
            weighted_sum += d["score"] * w
            total_weight += w

    if total_weight == 0:
        logger.warning("股票 [%s] 无任何可用数据，跳过评分", code)
        return None

    total = round(weighted_sum / total_weight / 10 * 100)

    # 5. 一句话核心逻辑
    summary = _build_summary(dims)

    return {
        "code": code,
        "name": display_name,
        "total": total,
        "dimensions": dims,
        "summary": summary,
    }


def _build_summary(dims: dict) -> str:
    """
    从各维度评分中提炼一句话核心逻辑
    取最高分维度的亮点 + 最低分维度的风险
    """
    sorted_dims = sorted(
        [(name, d) for name, d in dims.items() if d.get("score") is not None],
        key=lambda x: x[1]["score"],
        reverse=True,
    )
    if not sorted_dims:
        return "数据暂不可用"

    parts = []
    # 最强的维度
    best_name, best = sorted_dims[0]
    if best["score"] >= 7 and best.get("hl"):
        parts.append(f"{best_name}表现较好({best['hl']})")
    elif best["score"] >= 5:
        parts.append(f"{best_name}尚可")

    # 最弱的维度
    if len(sorted_dims) > 1:
        worst_name, worst = sorted_dims[-1]
        if worst["score"] < 5 and worst.get("hl"):
            parts.append(f"注意{worst_name.lower()}({worst['hl']})")

    return "；".join(parts) if parts else "暂无突出特征"


def score_recommended_stocks(stocks: list[StockRecommendation]) -> str:
    """
    对推荐个股列表进行评分，返回 Markdown 段落

    Args:
        stocks: 推荐个股列表（来自 AnalysisResult.top_picks[].stocks）

    Returns:
        Markdown 格式的段落字符串，可直接追加到晨报尾部
        若无有效数据则返回空字符串
    """
    if not stocks:
        return ""

    results = []
    for st in stocks:
        if not st.code:
            continue
        result = score_stock(st.code, st.name)
        if result:
            results.append(result)

    if not results:
        return ""

    lines = [
        "",
        "—📊 个股基本面评分📊—",
        "",
    ]
    for r in results:
        dims = r["dimensions"]
        lines.append(
            f"📈 `{r['code']}` {r['name']}  "
            f"评分 **{r['total']}**  "
            f"盈利 {_fmt_score(dims['盈利能力']['score'])}  "
            f"成长 {_fmt_score(dims['成长性']['score'])}  "
            f"估值 {_fmt_score(dims['估值安全']['score'])}  "
            f"财务 {_fmt_score(dims['财务健康']['score'])}  "
            f"动能 {_fmt_score(dims['股价动能']['score'])}"
        )
        if r["summary"]:
            lines.append(f"   └ {r['summary']}")

    lines.append(
        "  _评分模型：盈利(25%)+成长(20%)+估值(25%)+财务(20%)+动能(10%)_"
    )
    lines.append("")
    return "\n".join(lines)


def _fmt_score(score: Optional[float]) -> str:
    """格式化维度分为固定宽度字符串"""
    if score is None:
        return " -/10"
    s = round(score, 1)
    if s >= 7:
        return f"🟢{s:.1f}"
    elif s >= 4:
        return f"🟡{s:.1f}"
    return f"🔴{s:.1f}"
```

- [ ] **Step 5: 验证模块导入和运行**

Run: `cd try && python -c "import logging; logging.basicConfig(level=logging.CRITICAL); from morning.fundamental_analyzer import score_stock, score_recommended_stocks, _linear_scale; print('import_ok')"`

Expected: `import_ok`

---

### Task 2: 修改 main.py — 在晨报流程中串入基本面评分

**Files:**
- Modify: `main.py` (`cmd_morning` 函数尾部)

- [ ] **Step 1: 修改 cmd_morning()，在构建 Markdown 后追加基本面评分再发送**

当前流程对比：

**改造前：**
```
build_markdown + send_analysis(result, sources)  →  直接发钉钉
```

**改造后：**
```
build_markdown(result, sources)  →  base_md
score_recommended_stocks(stocks) →  fund_section
base_md + fund_section          →  full_md
send_dingtalk(full_md)          →  发送
```

修改 `cmd_morning()` 中约第 105-135 行的推送逻辑：

```python
    # 5. 构建 Markdown
    from morning.dingtalk_sender import build_markdown, send_dingtalk
    source_names = [s.name for s in cfg.rss_sources]
    markdown = build_markdown(result, source_names)

    # 6. 基本面评分（追加在尾部）
    try:
        from morning.fundamental_analyzer import score_recommended_stocks
        stocks = []
        for pick in result.top_picks:
            stocks.extend(pick.stocks)
        if stocks:
            fund_section = score_recommended_stocks(stocks)
            if fund_section:
                markdown += "\n" + fund_section
    except Exception as e:
        logger.warning("基本面评分生成失败: %s", e)

    # 7. 风险预警段（已有，保持不变）
    risk_section = ""
    if cfg.risk.enabled:
        try:
            risk_engine = RiskWarningEngine(...)
            risk_result = risk_engine.assess()
            risk_section = build_risk_section(risk_result)
            risk_engine.print_report(risk_result)
        except Exception as e:
            logger.warning("风险预警生成失败: %s", e)

    # 8. 推送
    if dry_run:
        if risk_section:
            markdown += "\n" + risk_section
        print("\n" + "=" * 60)
        print("干运行模式 — 以下为推送到钉钉的内容：")
        print("=" * 60)
        print(markdown)
        print("\n" + "=" * 60)
        logging.info("干运行完成（共 %d 字符）", len(markdown))
        return True

    success = send_dingtalk(markdown)
    if success:
        logging.info("晨报推送成功")

    if risk_section:
        risk_title = "【风险预警】市场风险评分"
        send_dingtalk(risk_section, title=risk_title)
        logging.info("风险预警推送成功")

    logging.info("晨报流程执行完毕")
    return success
```

具体替换 `main.py` 中 `cmd_morning()` 的完整代码（从注释 `# 5. 推送` 到 `return success`）：

- [ ] **Step 2: 编辑 main.py 的 cmd_morning() 推送部分**

找到 `cmd_morning()` 中的这一段：
```python
    # 5. 推送
    if dry_run:
        ...
```

替换为：
```python
    # 5. 构建 Markdown
    from morning.dingtalk_sender import build_markdown, send_dingtalk
    source_names = [s.name for s in cfg.rss_sources]
    markdown = build_markdown(result, source_names)

    # 6. 基本面评分
    try:
        from morning.fundamental_analyzer import score_recommended_stocks
        stocks = []
        for pick in result.top_picks:
            stocks.extend(pick.stocks)
        if stocks:
            fund_section = score_recommended_stocks(stocks)
            if fund_section:
                markdown += "\n" + fund_section
    except Exception as e:
        logger.warning("基本面评分生成失败: %s", e)

    # 7. 风险预警段
    risk_section = ""
    if cfg.risk.enabled:
        try:
            risk_engine = RiskWarningEngine(
                ad_warn=cfg.risk.ad_warn,
                ad_danger=cfg.risk.ad_danger,
                north_warn=cfg.risk.north_warn,
                north_danger=cfg.risk.north_danger,
                index_dev_warn=cfg.risk.index_dev_warn,
                index_dev_danger=cfg.risk.index_dev_danger,
            )
            risk_result = risk_engine.assess()
            risk_section = build_risk_section(risk_result)
            risk_engine.print_report(risk_result)
        except Exception as e:
            logger.warning("风险预警生成失败: %s", e)

    # 8. 推送
    if dry_run:
        if risk_section:
            markdown += "\n" + risk_section
        print("\n" + "=" * 60)
        print("干运行模式 — 以下为推送到钉钉的内容：")
        print("=" * 60)
        print(markdown)
        print("\n" + "=" * 60)
        logging.info("干运行完成（共 %d 字符）", len(markdown))
        return True

    success = send_dingtalk(markdown)
    if success:
        logging.info("晨报推送成功")

    if risk_section:
        risk_title = "【风险预警】市场风险评分"
        send_dingtalk(risk_section, title=risk_title)
        logging.info("风险预警推送成功")

    logging.info("晨报流程执行完毕")
    return success
```

- [ ] **Step 3: 验证修改后 main.py 语法正确**

Run: `cd try && python -c "import main; print('main.py syntax OK')"`

Expected: `main.py syntax OK`

---

### Task 3: 测试基本面评分功能

**Files:**
- Test: `morning/fundamental_analyzer.py` (indirectly via test script in D:\缓存区\)

- [ ] **Step 1: 用几只已知股票验证评分逻辑**

Run: `cd try && python -c "
import logging
logging.basicConfig(level=logging.CRITICAL)
from morning.fundamental_analyzer import score_stock

for code, name in [('600519','贵州茅台'), ('000858','五粮液'), ('601318','中国平安')]:
    r = score_stock(code, name)
    if r:
        print('%s(%s): total=%d  prof=%s growth=%s val=%s health=%s mom=%s | %s' % (
            r['name'], r['code'], r['total'],
            r['dimensions']['盈利能力']['score'],
            r['dimensions']['成长性']['score'],
            r['dimensions']['估值安全']['score'],
            r['dimensions']['财务健康']['score'],
            r['dimensions']['股价动能']['score'],
            r['summary']
        ))
    else:
        print('%s(%s): 数据不可用' % (name, code))
"`

Expected: 各股票输出评分行或标记为数据不可用

- [ ] **Step 2: 验证空数据降级**

Run: `cd try && python -c "
import logging
logging.basicConfig(level=logging.CRITICAL)
from morning.fundamental_analyzer import score_recommended_stocks
from morning.ai_analyzer import StockRecommendation

# 无股票
r = score_recommended_stocks([])
assert r == '', '空列表应返回空字符串'

# 有代码但无数据的股票
r = score_recommended_stocks([StockRecommendation(code='999999', name='测试', reason='测试')])
print('降级测试: len=%d' % len(r))
print('ALL OK')
"`

Expected: `降级测试: len=0`（数据不可用跳过） + `ALL OK`

- [ ] **Step 3: 端到端 dry-run 测试晨报含基本面评分**

Run: `cd try && python main.py --dry-run`

Expected: 干运行输出末尾应包含 "—📊 个股基本面评分📊—" 段

---

### Task 4: 重新打包为 exe

**Files:**
- Re-build: dist/StockStrategySystem.exe

- [ ] **Step 1: 清理并重新打包**

```bash
cd try
python build.py --clean
python build.py
```

Expected: 打包成功，EXE 位于 `dist/StockStrategySystem/StockStrategySystem.exe`

- [ ] **Step 2: 验证 exe 可启动**

Run: `dist\StockStrategySystem\StockStrategySystem.exe --help`

Expected: 显示帮助信息

---

### Task 5: 清理临时测试文件

- [ ] **Step 1: 删除缓存测试脚本**

```bash
Remove-Item "D:\缓存区\test_*.py" -ErrorAction SilentlyContinue
```
