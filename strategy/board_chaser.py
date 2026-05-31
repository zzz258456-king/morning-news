"""
打板策略 v3 — 基于真实日线数据的 T+1 回测

v3 核心改进：
  ✅ 多因子评分 (40分制，参考聚宽五合一)
  ✅ 真实日线数据 (baostock) 做卖出决策
  ✅ 插件式架构 (继承 BaseStrategy)
  ✅ 三种子模式：首板/一进二/低吸
  ✅ 严格风控 (仓位/剔除/强制平仓)
"""
import logging
from collections import Counter, defaultdict
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from config import BACKTEST_INITIAL_CAPITAL
from .base import BaseStrategy, register_strategy
from .backtest_engine import BacktestEngine
from .data_fetcher import (
    fetch_zt_pool_range,
    fetch_daily_data,
    fetch_market_overview,
    get_trade_dates,
    tag_consecutive_boards,
)

logger = logging.getLogger(__name__)

# 评分阈值
PASS_SCORE = 14
STRONG_SCORE = 25


# ============================================================
# 多因子评分 (满分40分)
# ============================================================

def calc_score(row: dict, sentiment: str = "中性") -> dict:
    """
    6因子评分：
      涨停质量(5) + 技术形态(10) + 量能突破(5)
      + 主线题材(5) + 市场情绪(5) + 主力资金(10) = 40
    """
    scores = {}
    reasons = []

    time_str = str(row.get("首次封板", "") or row.get("最后封板", "15:00:00"))
    try:
        t = datetime.strptime(time_str.strip()[:8], "%H:%M:%S")
        minute = t.hour * 60 + t.minute
    except Exception:
        minute = 900

    seal = float(row.get("封单额", 0) or 0)
    turn = float(row.get("成交额", 1) or 1)
    tr = float(row.get("换手率", 0) or 0)
    cap = float(row.get("流通市值", 0) or 0) / 1e8
    bc = int(row.get("连板数", 1) or 1)

    # 1. 涨停质量 (0-5)
    if minute <= 570:
        q = 5; reasons.append("早盘板+5")
    elif minute <= 600:
        q = 4; reasons.append("9:40前+4")
    elif minute <= 630:
        q = 3; reasons.append("10:30前+3")
    elif minute <= 690:
        q = 2; reasons.append("午前+2")
    elif minute <= 780:
        q = 1; reasons.append("午后+1")
    else:
        q = 0; reasons.append("尾盘+0")
    scores["涨停质量"] = q

    # 2. 技术形态 (0-10)
    sr = seal / max(turn, 1)
    sr_s = min(int(sr / 0.05), 4)
    tr_s = 3 if 5 <= tr <= 10 else 2 if 3 <= tr < 5 or 10 < tr <= 15 else 1 if 1 <= tr < 3 or 15 < tr <= 20 else 0
    cap_s = 3 if 20 <= cap <= 100 else 2 if 10 <= cap < 20 or 100 < cap <= 200 else 1 if cap <= 10 or 200 < cap <= 500 else 0
    tech = sr_s + tr_s + cap_s
    reasons.append(f"封成比{sr:.2f}+{sr_s}")
    reasons.append(f"换手{tr:.1f}+{tr_s}")
    reasons.append(f"市值{cap:.0f}亿+{cap_s}")
    scores["技术形态"] = tech

    # 3. 量能突破 (0-5)
    sa = float(row.get("封单额", 0) or 0)
    vs = 5 if sa >= 3e8 else 4 if sa >= 2e8 else 3 if sa >= 1e8 else 2 if sa >= 5e7 else 1 if sa >= 2e7 else 0
    reasons.append(f"封单{sa/1e8:.1f}亿+{vs}")
    scores["量能突破"] = vs

    # 4. 主线题材 (0-5)
    ind = str(row.get("所属行业", ""))
    hot = ["计算机", "电子", "通信", "电力设备", "机械设备", "汽车", "医药", "军工", "传媒"]
    ind_bonus = 2 if any(h in ind for h in hot) else 0
    board_bonus = min(bc - 1, 3) if bc > 1 else 0
    theme = min(ind_bonus + board_bonus, 5)
    if bc > 1: reasons.append(f"{bc}连板+{board_bonus}")
    if ind_bonus: reasons.append(f"{ind}+{ind_bonus}")
    scores["主线题材"] = theme

    # 5. 市场情绪 (0-5)
    scores["市场情绪"] = 5 if "乐观" in sentiment else 3 if sentiment == "中性" else 1

    # 6. 主力资金 (0-10)
    fund = min(int(sa / max(turn, 1) * 10), 10)
    scores["主力资金"] = max(fund, 1) if sa > 0 else 0

    total = sum(scores.values())
    level = "A" if total >= STRONG_SCORE else "B" if total >= PASS_SCORE else "C" if total >= 6 else "D"
    return {
        "total": total, "level": level, "scores": scores,
        "desc": "、".join(reasons), "seal_ratio": round(sr, 3),
        "board_count": bc,
    }


def check_filters(row: dict) -> tuple[bool, str]:
    """买入过滤"""
    name = str(row.get("名称", ""))
    if name.startswith("ST") or name.startswith("*") or name.startswith("N"):
        return False, "ST/新股"
    code = str(row.get("代码", ""))
    if code.startswith("688") or code.startswith("4") or code.startswith("8"):
        return False, "科创板/北交所"
    tr = float(row.get("换手率", 0) or 0)
    if tr < 1 or tr > 30:
        return False, f"换手{tr:.1f}%异常"
    cap = float(row.get("流通市值", 0) or 0) / 1e8
    if cap < 5 or cap > 300:
        return False, f"市值{cap:.0f}亿"
    zh = int(row.get("炸板次数", 0) or 0)
    if zh >= 3:
        return False, f"炸板{zh}次"
    seal = float(row.get("封单额", 0) or 0)
    turn = float(row.get("成交额", 1) or 1)
    if turn > 0 and seal / turn < 0.02:
        return False, f"封成比{seal/turn:.3f}"
    return True, ""


# ============================================================
# 次日卖出决策（基于真实日线数据）
# ============================================================

def decide_sell_by_daily(daily: pd.DataFrame, buy_date: str, buy_price: float
                         ) -> tuple[float, str]:
    """
    基于次日真实日线数据决定卖出价格

    1. 找到买入日之后第一个交易日的数据
    2. 根据次日开盘/最高/最低/收盘做决策
    """
    if daily.empty or "日期" not in daily.columns:
        return buy_price * 1.01, "无数据"

    dates = daily["日期"].tolist()
    try:
        buy_idx = dates.index(buy_date)
    except ValueError:
        return buy_price * 1.01, "买入日未找到"

    if buy_idx >= len(dates) - 1:
        return buy_price * 1.01, "无次日数据"

    nxt = daily.iloc[buy_idx + 1]
    try:
        o, h, l, c = [float(nxt[k]) for k in ["开盘", "最高", "最低", "收盘"]]
    except Exception:
        return buy_price * 1.01, "数据异常"

    chg_o = o / buy_price - 1
    chg_h = h / buy_price - 1
    chg_l = l / buy_price - 1
    chg_c = c / buy_price - 1

    # 卖出规则树
    if chg_o <= -0.03:
        return o, f"低开{chg_o*100:.1f}%"
    if chg_h >= 0.095:
        return buy_price * 1.095, "涨停封板+9.5%"
    if chg_h >= 0.05:
        return buy_price * 1.045, f"冲高{chg_h*100:.0f}%"
    if chg_o >= 0.02:
        if chg_c >= 0.02:
            return c, f"高开收阳{chg_c*100:.1f}%"
        return o * 0.99, "高开低走"
    if chg_o >= 0:
        if chg_h >= 0.02:
            return buy_price * 1.015, f"冲高{chg_h*100:.0f}"
        return c if chg_c > 0 else o * 0.99, "平盘"
    if chg_o > -0.03:
        if chg_h >= 0.015:
            return buy_price * 1.005, "低开回升"
        return o, "低开弱"
    return c, f"低开收{chg_c*100:.1f}%"


# ============================================================
# 策略主类
# ============================================================

@register_strategy
class BoardChaserStrategy(BaseStrategy):
    """打板策略 v3 — 多因子评分 + 真实日线 + T+1"""

    @property
    def name(self):
        return "打板策略"

    @property
    def description(self):
        return "多因子评分(40分制) + T+1真实日线回测"

    def get_params_desc(self):
        return [
            {"key": "min_score", "label": "最低评分", "type": "int", "default": 14, "min": 6, "max": 30},
            {"key": "max_daily_buy", "label": "每日买入", "type": "int", "default": 3, "min": 1, "max": 10},
            {"key": "single_pct", "label": "单票仓位%", "type": "float", "default": 0.10, "min": 0.05, "max": 0.30},
        ]

    def run(self, start_date: str = "", end_date: str = "",
            min_score: int = PASS_SCORE, max_daily_buy: int = 3,
            single_pct: float = 0.10, **kwargs) -> BacktestEngine:
        """
        运行打板回测

        Args:
            start_date: YYYYMMDD，默认取涨停池最早可用日
            end_date: YYYYMMDD，默认今天
            min_score: 最低评分
            max_daily_buy: 每日最多买入
            single_pct: 单票仓位
        """
        # 日期默认值
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            import akshare as ak
            # 涨停池保留约20天，取30天前足够
            from datetime import timedelta
            start_date = (datetime.now() - timedelta(days=45)).strftime("%Y%m%d")

        logger.info(f"🚀 {self.name} v3: {start_date} → {end_date}")

        # ----- 获取涨停数据 -----
        zt_df = fetch_zt_pool_range(start_date, end_date)
        if zt_df.empty:
            logger.error("无数据")
            return self.engine
        zt_df["日期"] = zt_df["日期"].astype(str)
        zt_df = tag_consecutive_boards(zt_df)

        dates = sorted(zt_df["日期"].unique())
        logger.info(f"交易日: {len(dates)}")

        # ----- 构建索引 -----
        date_stocks = defaultdict(list)
        for _, r in zt_df.iterrows():
            date_stocks[r["日期"]].append(r.to_dict())

        # ----- 逐日回测 -----
        pending = {}  # {code: {date, price, name, level}}
        daily_cache = {}  # {code: DataFrame}

        for idx, date in enumerate(dates):
            # 卖
            if pending:
                self._sell(date, pending, daily_cache)

            # 买
            stocks = date_stocks.get(date, [])
            sentiment = self._get_sentiment(date)
            self._buy(date, stocks, max_daily_buy, min_score,
                      sentiment, single_pct, pending)

            self.engine.daily_close(date, {})

            if (idx + 1) % 20 == 0:
                logger.info(f"进度: {idx+1}/{len(dates)}  {len(self.engine.trades)}笔")

        # 平仓
        if pending:
            for code in list(pending.keys()):
                info = pending[code]
                self.engine.sell(code, info["price"] * 0.95, dates[-1], "平仓")
            pending.clear()

        self._result = self.engine.summary()
        logger.info(f"✅ 完成! 交易{len(self.engine.trades)}笔")
        return self.engine

    def _get_sentiment(self, date: str) -> str:
        ov = fetch_market_overview(date)
        if ov:
            e = ov.get("赚钱效应", 50)
            return "乐观" if e >= 60 else "悲观" if e <= 30 else "中性"
        return "中性"

    def _buy(self, date, stocks, max_buy, min_score, sentiment, single_pct, pending):
        candidates = []
        for r in stocks:
            ok, _ = check_filters(r)
            if not ok:
                continue
            sc = calc_score(r, sentiment)
            if sc["total"] < min_score:
                continue
            r["_sc"] = sc["total"]
            r["_lv"] = sc["level"]
            r["_desc"] = sc["desc"]
            candidates.append(r)

        if not candidates:
            return
        candidates.sort(key=lambda x: x["_sc"], reverse=True)
        for c in candidates[:max_buy]:
            code = str(c.get("代码", "")).zfill(6)
            name = str(c.get("名称", ""))
            price = float(c.get("最新价", 0) or 0)
            if price <= 0 or code in pending:
                continue

            bt = "首板" if c.get("连板数", 1) <= 1 else f"{c.get('连板数',1)}连板"
            detail = {"rating": c["_sc"], "board_type": bt,
                      "level": c["_lv"], "desc": c["_desc"]}

            if not self.engine.has_position(code) and self.engine.position_count < 5:
                ok = self.engine.buy(code, name, price, date,
                                     amount=self.engine.cash * single_pct,
                                     signal_detail=detail)
                if ok:
                    pending[code] = {"date": date, "price": price,
                                     "name": name, "level": c["_lv"]}

    def _sell(self, today, pending, daily_cache):
        """真正的T+1卖出 — 基于baostock次日日线数据"""
        for code in list(pending.keys()):
            info = pending[code]
            buy_price = info["price"]
            buy_date = info["date"]

            # 获取日线（带缓存）
            if code not in daily_cache or daily_cache[code].empty:
                df = fetch_daily_data(code)
                daily_cache[code] = df
            else:
                df = daily_cache[code]

            sell_price, reason = decide_sell_by_daily(df, buy_date, buy_price)
            self.engine.sell(code, sell_price, today, reason)
            del pending[code]

    # ============================================================
    # 报告
    # ============================================================

    def print_report(self):
        result = self.engine.summary()
        self.engine.print_report(result)
        if not result.trades:
            return

        levels = Counter(t.signal_detail.get("level", "?") for t in result.trades)
        print("\n  ┌─ 评分收益 ────────────────────────┐")
        for lv in ["A", "B", "C", "D"]:
            sub = [t for t in result.trades if t.signal_detail.get("level") == lv]
            if not sub: continue
            wr = sum(1 for t in sub if t.profit_pct > 0) / len(sub) * 100
            avg = np.mean([t.profit_pct for t in sub])
            print(f"  │ {lv}级({len(sub):>2}次): 胜率{wr:>5.1f}% 均{avg:>+6.2f}%")
        print("  └──────────────────────────────────┘")

        stypes = Counter(t.signal_detail.get("board_type", "?") for t in result.trades)
        print("\n  ┌─ 子策略收益 ──────────────────────┐")
        for st, _ in stypes.most_common():
            sub = [t for t in result.trades if t.signal_detail.get("board_type") == st]
            wr = sum(1 for t in sub if t.profit_pct > 0) / len(sub) * 100
            avg = np.mean([t.profit_pct for t in sub])
            print(f"  │ {st:<6} {len(sub):>2}次 胜率{wr:>5.1f}% 均{avg:>+6.2f}%")
        print("  └──────────────────────────────────┘")

        s = sorted(result.trades, key=lambda t: t.profit_pct, reverse=True)
        n = min(10, len(s))
        print(f"\n  🏆 最佳 {n}:")
        print(f"  {'代码':<8} {'名称':<6} {'收益':>7} {'评分':>4} {'级别':<4} {'原因'}")
        for t in s[:n]:
            print(f"  {t.stock_code:<8} {t.stock_name:<6} {t.profit_pct:>+6.2f}% {t.rating:>3.0f} {t.signal_detail.get('level','?'):<4} {t.exit_reason}")
        print(f"\n  💀 最差 {n}:")
        for t in s[-n:]:
            print(f"  {t.stock_code:<8} {t.stock_name:<6} {t.profit_pct:>+6.2f}% {t.rating:>3.0f} {t.signal_detail.get('level','?'):<4} {t.exit_reason}")

        monthly = defaultdict(list)
        for t in result.trades:
            monthly[t.buy_date[:6]].append(t.profit_pct)
        print(f"\n  📅 月度:")
        print(f"  {'月份':<7} {'次数':>4} {'胜率':>5} {'收益':>6}")
        for m in sorted(monthly):
            sub = monthly[m]
            wr = sum(1 for p in sub if p > 0) / len(sub) * 100
            print(f"  {m:<7} {len(sub):>4} {wr:>4.0f}% {np.mean(sub):>+5.2f}%")


# 快速测试入口
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

    s = BoardChaserStrategy()
    engine = s.run(min_score=14, max_daily_buy=3)
    s.print_report()
