"""
风险评分引擎
综合市场情绪（涨跌家数）、资金流向（北向资金）、技术面（指数偏离）、日历效应，
输出 0-10 分综合风险评分

评分维度（满分10分）：
  涨跌家数(0-3) + 北向资金(0-3) + 指数偏离(0-3) + 日历效应(0-1)
"""
import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from .data_provider import (
    fetch_advance_decline,
    fetch_index_data,
    fetch_northbound_flow,
    calc_index_deviation,
)
from .calendar_effects import compute_calendar_effects

logger = logging.getLogger(__name__)

# 默认阈值
DEFAULT_AD_WINDOW = 20
DEFAULT_NORTH_WINDOW = 10


class RiskWarningEngine:
    """
    综合风险评分引擎

    使用方式：
        engine = RiskWarningEngine()
        result = engine.assess()
        engine.print_report(result)
    """

    def __init__(
        self,
        ad_window: int = DEFAULT_AD_WINDOW,
        north_window: int = DEFAULT_NORTH_WINDOW,
        ad_warn: float = 30.0,
        ad_danger: float = 20.0,
        north_warn: float = -20.0,
        north_danger: float = -50.0,
        index_dev_warn: float = 5.0,
        index_dev_danger: float = 8.0,
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
        dims = result.get("各维度", {})
        print(f"  涨跌家数:  {dims.get('涨跌家数', {}).get('说明','?')} "
              f"({dims.get('涨跌家数', {}).get('值','?')}) "
              f"[+{dims.get('涨跌家数', {}).get('分数',0)}]")
        print(f"  北向资金:  {dims.get('北向资金', {}).get('说明','?')} "
              f"({dims.get('北向资金', {}).get('值','?')}) "
              f"[+{dims.get('北向资金', {}).get('分数',0)}]")
        print(f"  指数偏离:  {dims.get('指数偏离', {}).get('说明','?')} "
              f"[+{dims.get('指数偏离', {}).get('分数',0)}]")
        print(f"  日历效应:  {dims.get('日历效应', {}).get('说明','?')} "
              f"[+{dims.get('日历效应', {}).get('分数',0)}]")
        print("  " + "-" * 46)
        print(f"  📋 {result['操作建议']}")
        print("=" * 50)
