"""
趋势跟踪策略 v1
基于经典技术指标的多周期趋势跟踪系统

核心逻辑：
  1. 双均线金叉/死叉 → 主趋势判断
  2. RSI 超买超卖 → 过滤器（避免追高杀跌）
  3. MACD 柱体确认 → 趋势强度确认
  4. ATR 动态止盈止损 → 自适应波动率

评分体系（30分制）：
  均线趋势(0-10) + RSI位置(0-5) + MACD强度(0-5)
  + 量比确认(0-5) + 多周期共振(0-5)

数据源：akshare 日线
适合：中低频趋势交易，持仓 3-15 天
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from config import BACKTEST_INITIAL_CAPITAL
from .base import BaseStrategy, register_strategy
from .backtest_engine import BacktestEngine
from .data_fetcher import fetch_daily_data, get_trade_dates

logger = logging.getLogger(__name__)


# ============================================================
# 技术指标计算
# ============================================================

def calc_sma(series: pd.Series, window: int) -> pd.Series:
    """简单移动平均"""
    return series.rolling(window).mean()


def calc_ema(series: pd.Series, span: int) -> pd.Series:
    """指数移动平均"""
    return series.ewm(span=span, adjust=False).mean()


def calc_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """RSI 计算"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window).mean()
    avg_loss = loss.rolling(window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_macd(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD：DIF, DEA, MACD柱"""
    dif = calc_ema(series, 12) - calc_ema(series, 26)
    dea = calc_ema(dif, 9)
    macd = 2 * (dif - dea)
    return dif, dea, macd


def calc_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """ATR 平均真实波幅"""
    high = df["最高"]
    low = df["最低"]
    close = df["收盘"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window).mean()


# ============================================================
# 趋势评分
# ============================================================

def trend_score(df: pd.DataFrame, idx: int) -> dict:
    """
    多维度趋势评分

    Args:
        df: 日线数据 (列: 日期,开盘,收盘,最高,最低,成交量)
        idx: 当前行索引

    Returns:
        {"total": int, "level": str, "scores": dict, "desc": str}
    """
    if idx < 60:
        return {"total": 0, "level": "D", "scores": {}, "desc": "数据不足"}

    close = df["收盘"]
    volume = df.get("成交量", pd.Series(0, index=df.index))

    # 1. 均线趋势 (0-10)
    ma5 = calc_sma(close, 5)
    ma10 = calc_sma(close, 10)
    ma20 = calc_sma(close, 20)
    ma60 = calc_sma(close, 60)

    c = close.iloc[idx]
    m5 = ma5.iloc[idx]
    m10 = ma10.iloc[idx]
    m20 = ma20.iloc[idx]
    m60 = ma60.iloc[idx]

    # 多头排列得分
    alignment = sum([
        m5 > m10, m10 > m20, m20 > m60,
        c > m5, c > m10, c > m20,
    ])
    trend = min(alignment, 10)
    reasons = [f"均线排列{align}/6"]

    # 2. RSI 位置 (0-5)
    rsi = calc_rsi(close, 14).iloc[idx]
    if 40 <= rsi <= 60:
        rsi_score = 5
        reasons.append(f"RSI{rsi:.0f}中性+5")
    elif 30 <= rsi < 40 or 60 < rsi <= 70:
        rsi_score = 3
        reasons.append(f"RSI{rsi:.0f}偏区+3")
    elif rsi < 30:
        rsi_score = 1
        reasons.append(f"RSI{rsi:.0f}超卖+1")
    else:
        rsi_score = 0
        reasons.append(f"RSI{rsi:.0f}超买+0")

    # 3. MACD 强度 (0-5)
    _, _, macd = calc_macd(close)
    macd_v = macd.iloc[idx]
    macd_prev = macd.iloc[idx - 1] if idx > 0 else 0

    if macd_v > 0 and macd_v > macd_prev:
        macd_score = 5
        reasons.append(f"MACD走强+5")
    elif macd_v > 0:
        macd_score = 3
        reasons.append(f"MACD正值+3")
    elif macd_v > macd_prev:
        macd_score = 1
        reasons.append(f"MACD收敛+1")
    else:
        macd_score = 0
        reasons.append("MACD弱势+0")

    # 4. 量比确认 (0-5)
    vol = volume.iloc[idx]
    vol_ma5 = volume.iloc[max(0, idx-5):idx+1].mean()
    if vol > 0 and vol_ma5 > 0:
        vr = vol / max(vol_ma5, 1)
        if vr >= 1.5:
            vol_score = 5
            reasons.append(f"放量{vr:.1f}倍+5")
        elif vr >= 1.2:
            vol_score = 3
            reasons.append(f"温和放量{vr:.1f}+3")
        elif vr >= 0.8:
            vol_score = 1
            reasons.append("量能正常+1")
        else:
            vol_score = 0
            reasons.append("缩量+0")
    else:
        vol_score = 0

    # 5. 多周期共振 (0-5)
    # 检查周线趋势（用日线模拟5日）
    ma5_prev = ma5.iloc[max(0, idx-5)]
    ma10_prev = ma10.iloc[max(0, idx-5)]
    trend_up_short = ma5.iloc[idx] > ma5_prev
    trend_up_medium = ma10.iloc[idx] > ma10_prev
    trend_up_long = ma20.iloc[idx] > ma20.iloc[max(0, idx-5)]

    resonance = sum([trend_up_short, trend_up_medium, c > m20])
    sync_score = min(resonance, 5)
    if sync_score >= 3:
        reasons.append(f"多周期共振+{sync_score}")

    # 总分
    scores = {
        "均线趋势": trend,
        "RSI位置": rsi_score,
        "MACD强度": macd_score,
        "量比确认": vol_score,
        "多周期共振": sync_score,
    }
    total = trend + rsi_score + macd_score + vol_score + sync_score

    if total >= 22:
        level = "A"
    elif total >= 16:
        level = "B"
    elif total >= 10:
        level = "C"
    else:
        level = "D"

    return {
        "total": total,
        "level": level,
        "scores": scores,
        "desc": "、".join(reasons),
    }


# ============================================================
# 策略主类
# ============================================================

@register_strategy
class TrendFollowerStrategy(BaseStrategy):
    """趋势跟踪策略 — 多指标共振 + ATR动态风控"""

    @property
    def name(self):
        return "趋势跟踪策略"

    @property
    def description(self):
        return "双均线+RSI+MACD多因子共振趋势跟踪"

    def get_params_desc(self):
        return [
            {"key": "min_score", "label": "最低评分", "type": "int", "default": 14, "min": 6, "max": 30},
            {"key": "max_positions", "label": "最大持仓数", "type": "int", "default": 5, "min": 1, "max": 20},
            {"key": "take_profit", "label": "止盈%", "type": "float", "default": 0.12, "min": 0.03, "max": 0.30},
            {"key": "stop_loss", "label": "止损%", "type": "float", "default": 0.05, "min": 0.02, "max": 0.15},
            {"key": "use_atr_sl", "label": "ATR动态止损", "type": "bool", "default": True},
        ]

    def run(
        self,
        start_date: str = "",
        end_date: str = "",
        min_score: int = 14,
        max_positions: int = 5,
        take_profit: float = 0.12,
        stop_loss: float = 0.05,
        use_atr_sl: bool = True,
        **kwargs,
    ) -> BacktestEngine:
        """
        运行趋势跟踪回测

        策略流程：
          1. 获取 A 股候选股票池（沪深300成分股，或全市场）
          2. 对每只股票计算技术指标
          3. 每日扫描池子，对满足评分条件的买入
          4. 持仓中按 ATR/SL/TP 条件卖出
        """
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")

        logger.info(f"🚀 {self.name}: {start_date} → {end_date}")

        # ---- 获取候选股票池 ----
        stock_pool = self._get_stock_pool()
        if not stock_pool:
            logger.error("无候选股票池")
            return self.engine

        logger.info(f"候选池: {len(stock_pool)} 只")

        # ---- 获取日线数据 ----
        all_data = {}  # {code: DataFrame}
        trade_dates = get_trade_dates(start_date, end_date)
        date_set = set(trade_dates)

        for code, name in stock_pool:
            df = fetch_daily_data(code, start_date, end_date)
            if df is not None and not df.empty and len(df) >= 60:
                # 确保列名统一
                df = self._standardize_columns(df)
                all_data[code] = {"name": name, "data": df}

        logger.info(f"有效数据: {len(all_data)} 只")
        if not all_data:
            return self.engine

        # ---- 建立每日扫描索引 ----
        code_list = list(all_data.keys())

        # ---- 逐日回测 ----
        for idx, date in enumerate(trade_dates):
            if date not in date_set:
                self.engine.daily_close(date, {})
                continue

            # 1. 检查持仓卖出条件
            self._check_sells(date, all_data, take_profit, stop_loss, use_atr_sl)

            # 2. 扫描买入信号
            self._check_buys(date, all_data, code_list, min_score, max_positions)

            # 3. 日终
            self.engine.daily_close(date, {})

            if (idx + 1) % 30 == 0:
                logger.info(f"进度: {idx+1}/{len(trade_dates)}  {len(self.engine.trades)}笔")

        # 平仓
        for code in list(self.engine.positions.keys()):
            info = self.engine.positions[code]
            self.engine.sell(code, info["buy_price"] * 0.98, trade_dates[-1], "期末平仓")

        self._result = self.engine.summary()
        logger.info(f"✅ 完成! 交易{len(self.engine.trades)}笔")
        return self.engine

    def _get_stock_pool(self) -> list[tuple[str, str]]:
        """
        获取候选股票池
        优先沪深300，兜底全市场
        """
        try:
            import akshare as ak
            # 沪深300成分股
            df = ak.index_stock_cons_weight_csindex("000300")
            if df is not None and not df.empty:
                codes = []
                for _, r in df.iterrows():
                    code = str(r.get("成分券代码", "")).zfill(6)
                    name = str(r.get("成分券名称", ""))
                    if code and name:
                        codes.append((code, name))
                if codes:
                    return codes[:100]  # 取前100只足够回测用
        except Exception as e:
            logger.debug(f"沪深300获取失败: {e}")

        # 兜底：一些常见蓝筹
        fallback = [
            ("600519", "贵州茅台"), ("000858", "五粮液"),
            ("601318", "中国平安"), ("600036", "招商银行"),
            ("000333", "美的集团"), ("600276", "恒瑞医药"),
            ("002415", "海康威视"), ("601012", "隆基绿能"),
            ("300750", "宁德时代"), ("000002", "万科A"),
        ]
        return fallback

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化列名"""
        rename = {
            "date": "日期", "open": "开盘", "high": "最高",
            "low": "最低", "close": "收盘", "volume": "成交量",
            "amount": "成交额",
        }
        return df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    def _check_sells(self, today: str, all_data: dict,
                     take_profit: float, stop_loss: float, use_atr_sl: bool):
        """检查持仓卖出条件"""
        for code in list(self.engine.positions.keys()):
            pos = self.engine.positions[code]
            buy_price = pos["buy_price"]
            info = all_data.get(code)
            if info is None:
                continue

            df = info["data"]
            daily = df[df["日期"] == today]
            if daily.empty:
                continue

            row = daily.iloc[0]
            close = float(row.get("收盘", buy_price))
            high = float(row.get("最高", close))
            low = float(row.get("最低", close))

            chg_high = high / buy_price - 1
            chg_low = low / buy_price - 1

            # ATR 动态止损
            if use_atr_sl and len(df) >= 20:
                atr = calc_atr(df)
                atr_val = atr.iloc[-1] if not atr.empty else 0
                if atr_val > 0:
                    atr_sl_price = close - 2 * atr_val
                    if low <= atr_sl_price:
                        reason = f"ATR止损({atr_val:.2f})"
                        self.engine.sell(code, atr_sl_price, today, reason)
                        continue

            # 固定止盈
            if chg_high >= take_profit:
                self.engine.sell(code, buy_price * (1 + take_profit), today,
                                 f"止盈+{take_profit*100:.0f}%")
                continue

            # 固定止损
            if chg_low <= -stop_loss:
                self.engine.sell(code, buy_price * (1 - stop_loss), today,
                                 f"止损-{stop_loss*100:.0f}%")
                continue

            # 趋势反转：收盘跌破20日线
            ma20 = df["收盘"].rolling(20).mean()
            if len(ma20) > 0 and close < ma20.iloc[-1]:
                self.engine.sell(code, close, today, "跌破20线")

    def _check_buys(self, today: str, all_data: dict,
                    code_list: list, min_score: int, max_positions: int):
        """扫描买入信号"""
        if self.engine.position_count >= max_positions:
            return

        candidates = []
        for code in code_list:
            if code in self.engine.positions:
                continue

            info = all_data.get(code)
            if info is None:
                continue

            df = info["data"]
            idx = df[df["日期"] == today].index
            if idx.empty:
                continue

            pos = idx[0]
            if pos < 60:
                continue

            # 评分
            sc = trend_score(df, pos)
            if sc["total"] < min_score:
                continue

            # 检查现金仓位
            price = float(df.iloc[pos]["收盘"])
            if price <= 0:
                continue

            candidates.append({
                "code": code,
                "name": info["name"],
                "price": price,
                "score": sc["total"],
                "level": sc["level"],
                "desc": sc["desc"],
            })

        if not candidates:
            return

        candidates.sort(key=lambda x: x["score"], reverse=True)
        for c in candidates:
            if self.engine.position_count >= max_positions:
                break
            if c["code"] in self.engine.positions:
                continue

            detail = {"rating": c["score"], "level": c["level"], "desc": c["desc"]}
            single_pct = min(1.0 / max_positions, 0.25)
            self.engine.buy(
                c["code"], c["name"], c["price"], today,
                amount=self.engine.cash * single_pct,
                signal_detail=detail,
            )

    def print_report(self):
        """打印回测报告"""
        result = self.engine.summary()
        self.engine.print_report(result)

        if not result.trades:
            return

        # 评分等级分析
        from collections import Counter
        levels = Counter(t.signal_detail.get("level", "?") for t in result.trades)
        print("\n  ┌─ 评分收益 ────────────────────────┐")
        for lv in ["A", "B", "C", "D"]:
            sub = [t for t in result.trades if t.signal_detail.get("level") == lv]
            if not sub:
                continue
            wr = sum(1 for t in sub if t.profit_pct > 0) / len(sub) * 100
            avg = np.mean([t.profit_pct for t in sub])
            print(f"  │ {lv}级({len(sub):>2}次): 胜率{wr:>5.1f}% 均{avg:>+6.2f}%")
        print("  └──────────────────────────────────┘")


# 独立测试
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__file__).parent.parent.resolve())

    s = TrendFollowerStrategy()
    engine = s.run(min_score=14, max_positions=5,
                   start_date="20260301", end_date="20260529")
    s.print_report()
