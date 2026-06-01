"""
风险预警模块 v1
综合市场情绪、资金流向、指数技术面，输出 0-10 风险评分

功能：
  1. 涨跌家数比 → 市场广度
  2. 北向资金净流入 → 聪明钱方向
  3. 上证指数 20/60 日线偏离度 → 技术风险
  4. 日历效应统计 → 星期几效应
  5. 综合风险评分 (0-10) → 低/中/高三级

数据源：akshare（免费、免注册）
集成：既可独立运行，也可作为回测策略的动态风控组件
"""
import logging
import pickle
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from config import RAW_DATA_DIR

logger = logging.getLogger(__name__)

# ============================================================
# 常量
# ============================================================

RISK_CACHE_DIR = RAW_DATA_DIR / "risk_cache"
RISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 默认阈值（可在 config.py 中覆盖）
DEFAULT_AD_THRESHOLD_WARN = 30.0   # 涨跌家数比% 预警线
DEFAULT_AD_THRESHOLD_DANGER = 20.0 # 涨跌家数比% 危险线
DEFAULT_NORTH_THRESHOLD_WARN = -20.0   # 北向资金(亿) 预警线
DEFAULT_NORTH_THRESHOLD_DANGER = -50.0 # 北向资金(亿) 危险线
DEFAULT_INDEX_DEV_WARN = 5.0   # 指数偏离% 预警
DEFAULT_INDEX_DEV_DANGER = 8.0 # 指数偏离% 危险
DEFAULT_AD_WINDOW = 20         # 涨跌家数均线窗口
DEFAULT_NORTH_WINDOW = 10      # 北向资金均线窗口


# ============================================================
# 数据获取
# ============================================================

def fetch_advance_decline(date: Optional[str] = None) -> dict:
    """
    获取全市场涨跌家数

    返回:
        {"上涨": int, "下跌": int, "平盘": int,
         "总数": int, "涨跌比%": float, "日期": str}
    """
    if date is None:
        date = datetime.now().strftime("%Y%m%d")

    try:
        import akshare as ak
        df = ak.stock_market_activity_em()
        if df is not None and not df.empty:
            row = df.iloc[0]
            up = int(row.get("上涨家数", 0))
            down = int(row.get("下跌家数", 0))
            flat = int(row.get("平盘家数", 0))
            total = up + down + flat
            ratio = round(up / max(total, 1) * 100, 2)
            return {
                "上涨": up, "下跌": down, "平盘": flat,
                "总数": total, "涨跌比%": ratio, "日期": date,
            }
    except Exception as e:
        logger.warning(f"涨跌家数获取失败 [{date}]: {e}")

    # 兜底：akshare 实时行情统计
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        up = int((df["涨跌幅"] > 0).sum())
        down = int((df["涨跌幅"] < 0).sum())
        flat = int((df["涨跌幅"] == 0).sum())
        total = up + down + flat
        ratio = round(up / max(total, 1) * 100, 2)
        return {
            "上涨": up, "下跌": down, "平盘": flat,
            "总数": total, "涨跌比%": ratio, "日期": date,
        }
    except Exception as e:
        logger.warning(f"实时行情涨跌统计失败: {e}")

    return {}


def fetch_northbound_flow(date: Optional[str] = None) -> dict:
    """
    获取北向资金（沪股通+深股通）当日净流入

    返回:
        {"沪股通": float, "深股通": float, "合计": float, "日期": str}
    """
    if date is None:
        date = datetime.now().strftime("%Y%m%d")

    try:
        import akshare as ak
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            sh = float(latest.get("沪股通_净流入", 0))
            sz = float(latest.get("深股通_净流入", 0))
            total = sh + sz
            return {
                "沪股通": round(sh, 2),
                "深股通": round(sz, 2),
                "合计": round(total, 2),
                "日期": str(latest.get("date", date))[:10],
            }
    except Exception as e:
        logger.warning(f"北向资金获取失败: {e}")

    # 备用接口
    try:
        import akshare as ak
        df = ak.stock_hsgt_summary_em()
        latest = df.iloc[-1]
        sh = float(latest.get("沪股通_净流入", 0))
        sz = float(latest.get("深股通_净流入", 0))
        return {
            "沪股通": round(sh, 2),
            "深股通": round(sz, 2),
            "合计": round(sh + sz, 2),
            "日期": str(latest.get("日期", date))[:10],
        }
    except Exception as e:
        logger.warning(f"北向备用接口失败: {e}")

    return {}


def fetch_index_data(code: str = "000001",
                     start_date: str = "20250101",
                     end_date: str = "") -> pd.DataFrame:
    """
    获取指数日线数据（用于计算均线偏离度）

    Args:
        code: 指数代码，000001=上证指数
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期，默认今天

    Returns:
        DataFrame: 日期, 收盘, 20日均线, 60日均线
    """
    if not end_date:
        end_date = datetime.now().strftime("%Y%m%d")

    cache_file = RISK_CACHE_DIR / f"index_{code}_{start_date}_{end_date}.parquet"
    if cache_file.exists():
        try:
            return pd.read_parquet(cache_file)
        except Exception:
            pass

    try:
        import akshare as ak
        df = ak.stock_zh_index_daily_em(symbol=f"sh{code}")
        if df is None or df.empty:
            return pd.DataFrame()

        df["日期"] = pd.to_datetime(df["date"]).dt.strftime("%Y%m%d")
        df = df.sort_values("日期").reset_index(drop=True)
        df["20日均线"] = df["close"].rolling(20).mean()
        df["60日均线"] = df["close"].rolling(60).mean()

        # 筛选日期范围
        mask = (df["日期"] >= start_date) & (df["日期"] <= end_date)
        result = df[mask][["日期", "close", "20日均线", "60日均线"]].copy()
        result.columns = ["日期", "收盘", "20日均线", "60日均线"]

        try:
            result.to_parquet(cache_file, index=False)
        except Exception:
            pass
        return result
    except Exception as e:
        logger.warning(f"指数数据获取失败 [{code}]: {e}")

    return pd.DataFrame()


def calc_index_deviation(index_df: pd.DataFrame) -> dict:
    """
    计算指数相对于20日/60日均线的偏离度

    Returns:
        {"收盘": float, "20日偏离%": float, "60日偏离%": float, "日期": str}
    """
    if index_df.empty or len(index_df) < 60:
        return {}

    latest = index_df.iloc[-1]
    close = float(latest["收盘"])
    ma20 = float(latest["20日均线"])
    ma60 = float(latest["60日均线"])

    return {
        "收盘": close,
        "20日偏离%": round((close / ma20 - 1) * 100, 2) if ma20 > 0 else 0,
        "60日偏离%": round((close / ma60 - 1) * 100, 2) if ma60 > 0 else 0,
        "日期": str(latest["日期"]),
    }


# ============================================================
# 日历效应统计
# ============================================================

def compute_calendar_effects(
    years: int = 3,
    force_refresh: bool = False,
) -> dict[str, dict]:
    """
    计算星期几效应：过去 N 年各星期几的下跌概率和平均涨跌幅

    结果缓存到本地，每周更新一次

    Returns:
        {
            "周一": {"样本数": N, "下跌概率%": float, "平均涨跌幅%": float},
            "周二": ...,
        }
    """
    cache_file = RISK_CACHE_DIR / "calendar_effects.pkl"

    if not force_refresh and cache_file.exists():
        try:
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if (datetime.now() - mtime).days < 7:  # 一周缓存
                with open(cache_file, "rb") as f:
                    return pickle.load(f)
        except Exception:
            pass

    logger.info("计算日历效应（过去 %d 年）...", years)

    try:
        import akshare as ak

        end = datetime.now()
        start = end - timedelta(days=years * 365)
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        # 获取上证指数日线
        df = ak.stock_zh_index_daily_em(symbol="sh000001")
        if df is None or df.empty:
            logger.warning("日历效应：获取指数数据失败")
            return {}

        df["日期"] = pd.to_datetime(df["date"])
        df = df[(df["日期"] >= start) & (df["日期"] <= end)].copy()
        df["星期几"] = df["日期"].dt.dayofweek  # 0=周一
        df["涨跌幅%"] = df["close"].pct_change() * 100

        # 按星期几分组统计
        day_names = ["周一", "周二", "周三", "周四", "周五"]
        result = {}
        for dow, name in enumerate(day_names):
            sub = df[df["星期几"] == dow]["涨跌幅%"].dropna()
            if len(sub) == 0:
                continue
            down_prob = (sub < 0).sum() / len(sub) * 100
            result[name] = {
                "样本数": len(sub),
                "下跌概率%": round(down_prob, 1),
                "平均涨跌幅%": round(sub.mean(), 2),
            }

        # 缓存
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(result, f)
        except Exception:
            pass

        return result
    except Exception as e:
        logger.warning(f"日历效应计算失败: {e}")
        return {}


# ============================================================
# 核心风险评分模型
# ============================================================

class RiskWarningEngine:
    """
    综合风险评分引擎

    评分维度（满分10分）：
      涨跌家数(0-3) + 北向资金(0-3) + 指数偏离(0-3) + 日历效应(0-1)
    """

    def __init__(
        self,
        ad_window: int = DEFAULT_AD_WINDOW,
        north_window: int = DEFAULT_NORTH_WINDOW,
        ad_warn: float = DEFAULT_AD_THRESHOLD_WARN,
        ad_danger: float = DEFAULT_AD_THRESHOLD_DANGER,
        north_warn: float = DEFAULT_NORTH_THRESHOLD_WARN,
        north_danger: float = DEFAULT_NORTH_THRESHOLD_DANGER,
        index_dev_warn: float = DEFAULT_INDEX_DEV_WARN,
        index_dev_danger: float = DEFAULT_INDEX_DEV_DANGER,
    ):
        self.ad_window = ad_window
        self.north_window = north_window
        self.ad_warn = ad_warn
        self.ad_danger = ad_danger
        self.north_warn = north_warn
        self.north_danger = north_danger
        self.index_dev_warn = index_dev_warn
        self.index_dev_danger = index_dev_danger

        # 历史序列（用于计算均线）
        self._ad_history: list[float] = []
        self._north_history: list[float] = []

        # 缓存日历效应
        self._calendar_effects: dict = {}

    def update(self, ad_ratio: float, north_net: float):
        """更新最新市场数据"""
        self._ad_history.append(ad_ratio)
        self._north_history.append(north_net)
        max_len = max(self.ad_window, self.north_window) * 3
        if len(self._ad_history) > max_len:
            self._ad_history = self._ad_history[-max_len:]
        if len(self._north_history) > max_len:
            self._north_history = self._north_history[-max_len:]

    # ---- 各维度评分 ----

    def _score_advance_decline(self, ad_ratio: float) -> tuple[float, str]:
        """涨跌家数评分 (0-3分)"""
        if ad_ratio >= 50:
            return 0.0, "市场健康"
        elif ad_ratio >= self.ad_warn:
            return 1.0, "情绪偏弱"
        elif ad_ratio >= self.ad_danger:
            return 2.0, "情绪低迷"
        else:
            return 3.0, "市场恐慌"

    def _score_northbound(self, north_net: float) -> tuple[float, str]:
        """北向资金评分 (0-3分)"""
        if north_net >= 0:
            return 0.0, "外资流入"
        elif north_net >= self.north_warn:
            return 1.0, "小幅流出"
        elif north_net >= self.north_danger:
            return 2.0, "明显流出"
        else:
            return 3.0, "资金出逃"

    def _score_index_deviation(self, dev: dict) -> tuple[float, str]:
        """指数偏离评分 (0-3分)"""
        if not dev:
            return 1.0, "无指数数据"

        dev_20 = abs(dev.get("20日偏离%", 0))
        dev_60 = abs(dev.get("60日偏离%", 0))
        max_dev = max(dev_20, dev_60)

        if max_dev <= 2:
            return 0.0, "指数正常"
        elif max_dev <= self.index_dev_warn:
            return 1.0, "小幅偏离"
        elif max_dev <= self.index_dev_danger:
            return 2.0, "明显偏离"
        else:
            return 3.0, "严重偏离"

    def _score_calendar(self) -> tuple[float, str]:
        """日历效应评分 (0-1分)"""
        if not self._calendar_effects:
            self._calendar_effects = compute_calendar_effects()

        today_idx = datetime.now().weekday()
        day_names = ["周一", "周二", "周三", "周四", "周五"]
        today_name = day_names[today_idx] if 0 <= today_idx <= 4 else "非交易日"

        info = self._calendar_effects.get(today_name)
        if info is None:
            return 0.0, "无日历数据"

        down_prob = info.get("下跌概率%", 50)
        if down_prob >= 55:
            return 1.0, f"{today_name}下跌概率{down_prob:.0f}%"
        elif down_prob >= 50:
            return 0.5, f"{today_name}偏弱(下跌概率{down_prob:.0f}%)"
        else:
            return 0.0, f"{today_name}正常"

    # ---- 综合评估 ----

    def assess(
        self,
        ad_ratio: Optional[float] = None,
        north_net: Optional[float] = None,
        index_code: str = "000001",
    ) -> dict:
        """
        综合风险评估

        Args:
            ad_ratio: 涨跌比%，None 则自动获取
            north_net: 北向净流入(亿)，None 则自动获取
            index_code: 指数代码

        Returns:
            {
                "风险分数": float(0-10),
                "风险等级": "低风险"/"中风险"/"高风险",
                "各维度": {...},
                "操作建议": str,
                "数据快照": {...},
            }
        """
        # ---- 获取原始数据 ----
        ad_data = fetch_advance_decline() if ad_ratio is None else {}
        ad_ratio = ad_ratio if ad_ratio is not None else ad_data.get("涨跌比%", 50)

        north_data = fetch_northbound_flow() if north_net is None else {}
        north_net = north_net if north_net is not None else north_data.get("合计", 0)

        index_df = fetch_index_data(code=index_code)
        index_dev = calc_index_deviation(index_df)

        # 更新历史
        self.update(ad_ratio, north_net)

        # ---- 各维度评分 ----
        ad_score, ad_reason = self._score_advance_decline(ad_ratio)
        north_score, north_reason = self._score_northbound(north_net)
        index_score, index_reason = self._score_index_deviation(index_dev)
        # 日历效应评分
        try:
            cal_score, cal_reason = self._score_calendar()
        except Exception:
            cal_score, cal_reason = 0.0, "日历数据不可用"

        # ---- 综合 ----
        total_score = round(ad_score + north_score + index_score + cal_score, 1)
        total_score = min(total_score, 10.0)

        if total_score <= 3:
            level = "低风险"
            suggestion = "✅ 市场环境健康，可正常交易"
        elif total_score <= 6:
            level = "中风险"
            suggestion = "⚠️ 出现风险信号，建议控制仓位 ≤ 70%，暂停追高操作"
        else:
            level = "高风险"
            suggestion = "🔴 风险较高！建议减仓至半仓以下，不开新仓，等待风险释放"

        return {
            "风险分数": total_score,
            "风险等级": level,
            "各维度": {
                "涨跌家数": {"分数": ad_score, "说明": ad_reason, "值": f"{ad_ratio:.1f}%"},
                "北向资金": {"分数": north_score, "说明": north_reason, "值": f"{north_net:.1f}亿"},
                "指数偏离": {"分数": index_score, "说明": index_reason},
                "日历效应": {"分数": cal_score, "说明": cal_reason},
            },
            "操作建议": suggestion,
            "数据快照": {
                "涨跌比%": ad_ratio,
                "北向合计(亿)": north_net,
                "指数20日偏离%": index_dev.get("20日偏离%"),
                "指数60日偏离%": index_dev.get("60日偏离%"),
            },
            "时间戳": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    # ---- 回测支持 ----

    def assess_for_backtest(
        self,
        date: str,
        precomputed_risk: Optional[pd.DataFrame] = None,
    ) -> dict:
        """
        回测模式下获取指定日期的风险评估

        Args:
            date: 回测日期 YYYYMMDD
            precomputed_risk: 预先计算好的风险数据 DataFrame
                              (列: 日期, 涨跌比%, 北向合计, 20日偏离%, 60日偏离%)

        Returns:
            风险字典（同 assess() 格式）
        """
        if precomputed_risk is not None and "日期" in precomputed_risk.columns:
            row = precomputed_risk[precomputed_risk["日期"] == date]
            if not row.empty:
                r = row.iloc[0]
                return self.assess(
                    ad_ratio=float(r.get("涨跌比%", 50)),
                    north_net=float(r.get("北向合计", 0)),
                )

        # 无预计算数据：返回中性评分
        return {
            "风险分数": 2.0,
            "风险等级": "低风险",
            "各维度": {},
            "操作建议": "无风险数据",
            "数据快照": {},
            "时间戳": date,
        }

    def print_report(self, result: dict):
        """打印风险报告"""
        print("\n" + "=" * 50)
        print("  🛡️  市场风险预警报告")
        print("=" * 50)
        print(f"  综合风险: {result['风险分数']}/10  →  {result['风险等级']}")
        print(f"  时间: {result['时间戳']}")
        print("  " + "-" * 46)
        print(f"  涨跌家数:  {result['各维度'].get('涨跌家数', {}).get('说明','?')} "
              f"({result['各维度'].get('涨跌家数', {}).get('值','?')}) "
              f"[+{result['各维度'].get('涨跌家数', {}).get('分数',0)}]")
        print(f"  北向资金:  {result['各维度'].get('北向资金', {}).get('说明','?')} "
              f"({result['各维度'].get('北向资金', {}).get('值','?')}) "
              f"[+{result['各维度'].get('北向资金', {}).get('分数',0)}]")
        print(f"  指数偏离:  {result['各维度'].get('指数偏离', {}).get('说明','?')} "
              f"[+{result['各维度'].get('指数偏离', {}).get('分数',0)}]")
        print(f"  日历效应:  {result['各维度'].get('日历效应', {}).get('说明','?')} "
              f"[+{result['各维度'].get('日历效应', {}).get('分数',0)}]")
        print("  " + "-" * 46)
        print(f"  📋 {result['操作建议']}")
        print("=" * 50)


# ============================================================
# 独立运行入口
# ============================================================

def main():
    """独立运行：获取当前风险并打印报告"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    engine = RiskWarningEngine()
    try:
        result = engine.assess()
        engine.print_report(result)
    except Exception as e:
        logger.warning(f"实时风险分析失败: {e}")
        print("\n  [实时数据不可用] 展示历史日历效应统计\n")
        pass

    # 打印日历效应
    print("\n  日历效应（历史统计）:")
    try:
        effects = compute_calendar_effects()
        for day, info in effects.items():
            print(f"    {day}: {info['样本数']}天  下跌概率{info['下跌概率%']}%  "
                  f"平均{info['平均涨跌幅%']:+.2f}%")
    except Exception as e:
        print(f"    (数据获取失败: {e})")
    print()


if __name__ == "__main__":
    main()
