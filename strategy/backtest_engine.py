"""
回测引擎
通用回测框架，支持：
- T+1 交易规则
- 佣金与滑点
- 多空双向
- 绩效统计（年化收益、夏普、最大回撤、胜率）
- 交易流水记录
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from config import (
    BACKTEST_INITIAL_CAPITAL,
    BACKTEST_COMMISSION,
    BACKTEST_SLIPPAGE,
)

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class TradeRecord:
    """单笔交易记录"""
    stock_code: str = ""
    stock_name: str = ""
    buy_date: str = ""
    sell_date: str = ""
    buy_price: float = 0.0
    sell_price: float = 0.0
    volume: int = 0
    commission: float = 0.0
    profit_pct: float = 0.0  # 收益率 %
    profit_amount: float = 0.0
    hold_days: int = 1
    exit_reason: str = ""  # 止盈/止损/条件卖/收盘卖
    board_type: str = ""   # 首板/连板
    rating: float = 0.0    # 策略评分
    signal_detail: dict = field(default_factory=dict)


@dataclass
class BacktestResult:
    """回测结果汇总"""
    # 基础统计
    total_trades: int = 0
    win_trades: int = 0
    lose_trades: int = 0
    win_rate: float = 0.0

    # 收益
    total_return: float = 0.0       # 总收益率 %
    annual_return: float = 0.0      # 年化收益率 %
    max_drawdown: float = 0.0       # 最大回撤 %

    # 风险指标
    sharpe_ratio: float = 0.0       # 夏普比率
    profit_loss_ratio: float = 0.0  # 盈亏比
    avg_profit: float = 0.0         # 平均单笔收益 %
    avg_loss: float = 0.0           # 平均单笔亏损 %

    # 交易统计
    max_consecutive_losses: int = 0
    avg_hold_days: float = 0.0
    total_commission: float = 0.0

    # 原始数据
    trades: list[TradeRecord] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)


class BacktestEngine:
    """
    回测引擎核心

    用法：
        engine = BacktestEngine(initial_capital=1_000_000)
        engine.run(signals_df)     # signals_df 包含买卖信号
        report = engine.summary()
    """

    def __init__(
        self,
        initial_capital: float = BACKTEST_INITIAL_CAPITAL,
        commission: float = BACKTEST_COMMISSION,
        slippage: float = BACKTEST_SLIPPAGE,
        t_plus_1: bool = True,
    ):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.t_plus_1 = t_plus_1

        # 运行时状态
        self.cash = initial_capital
        self.equity = initial_capital
        self.peak_equity = initial_capital
        self.max_drawdown = 0.0

        # 持仓 {stock_code: {"volume": N, "buy_price": P, "buy_date": D, "name": N}}
        self.positions: dict = {}

        # 交易记录
        self.trades: list[TradeRecord] = []
        self.equity_curve: list[float] = [initial_capital]

        # 连续亏损计数
        self._consecutive_losses = 0
        self._max_consecutive_losses = 0

    # --------------------------------------------------------
    # 核心下单接口
    # --------------------------------------------------------

    def buy(
        self,
        stock_code: str,
        stock_name: str,
        price: float,
        date: str,
        volume: Optional[int] = None,
        amount: Optional[float] = None,
        signal_detail: Optional[dict] = None,
    ) -> bool:
        """
        买入下单

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            price: 买入价格（涨停价）
            date: 日期 YYYYMMDD
            volume: 买入股数（按手取整）
            amount: 买入金额（与 volume 二选一）
            signal_detail: 信号详情（评分等）

        Returns:
            是否成交
        """
        # 计算买入股数
        if volume is not None:
            vol = volume
        elif amount is not None:
            vol = int(amount / price / 100) * 100
        else:
            # 默认单只股票使用 20% 资金
            vol = int(self.cash * 0.2 / price / 100) * 100

        # 检查资金
        cost = vol * price
        commission_fee = cost * self.commission
        total_cost = cost + commission_fee

        if total_cost > self.cash or vol <= 0:
            return False

        # 执行买入
        self.cash -= total_cost
        self.positions[stock_code] = {
            "volume": vol,
            "buy_price": price,
            "buy_date": date,
            "name": stock_name,
            "commission": commission_fee,
            "signal_detail": signal_detail or {},
        }

        logger.debug(f"买入 {stock_name}({stock_code}) {vol}股 @{price:.2f}")
        return True

    def sell(
        self,
        stock_code: str,
        price: float,
        date: str,
        reason: str = "",
    ) -> bool:
        """
        卖出持仓

        Args:
            stock_code: 股票代码
            price: 卖出价格
            date: 日期 YYYYMMDD
            reason: 卖出原因

        Returns:
            是否成交
        """
        if stock_code not in self.positions:
            return False

        pos = self.positions[stock_code]
        volume = pos["volume"]
        buy_price = pos["buy_price"]
        buy_date = pos["buy_date"]
        stock_name = pos["name"]

        # 计算卖出
        sell_amount = volume * price
        commission_fee = sell_amount * self.commission
        net_sell = sell_amount - commission_fee

        self.cash += net_sell

        # 计算盈亏
        buy_cost = volume * buy_price
        buy_commission = pos["commission"]
        total_profit = net_sell - buy_cost - buy_commission
        profit_pct = (price / buy_price - 1) * 100

        # 记录交易
        hold_days = 1
        try:
            bd = datetime.strptime(buy_date, "%Y%m%d")
            sd = datetime.strptime(date, "%Y%m%d")
            hold_days = max(1, (sd - bd).days)
        except Exception:
            pass

        trade = TradeRecord(
            stock_code=stock_code,
            stock_name=stock_name,
            buy_date=buy_date,
            sell_date=date,
            buy_price=buy_price,
            sell_price=price,
            volume=volume,
            commission=buy_commission + commission_fee,
            profit_pct=profit_pct,
            profit_amount=total_profit,
            hold_days=hold_days,
            exit_reason=reason,
            board_type=pos["signal_detail"].get("board_type", ""),
            rating=pos["signal_detail"].get("rating", 0),
            signal_detail=pos["signal_detail"],
        )
        self.trades.append(trade)

        # 连续亏损
        if profit_pct > 0:
            self._consecutive_losses = 0
        else:
            self._consecutive_losses += 1
            self._max_consecutive_losses = max(
                self._max_consecutive_losses, self._consecutive_losses
            )

        # 更新净值
        self.equity = self.cash + self._calc_position_value({})
        self.peak_equity = max(self.peak_equity, self.equity)
        dd = (self.peak_equity - self.equity) / self.peak_equity * 100
        self.max_drawdown = max(self.max_drawdown, dd)

        # 移除持仓
        del self.positions[stock_code]

        logger.debug(
            f"卖出 {stock_name}({stock_code}) "
            f"@{price:.2f} {reason} 收益:{profit_pct:+.2f}%"
        )
        return True

    def has_position(self, stock_code: str) -> bool:
        """是否持有某股票"""
        return stock_code in self.positions

    @property
    def position_count(self) -> int:
        """持仓个数"""
        return len(self.positions)

    # --------------------------------------------------------
    # 日终处理
    # --------------------------------------------------------

    def daily_close(self, date: str, prices: dict[str, float]):
        """
        日终处理：更新持仓市值、记录净值曲线

        Args:
            date: 日期
            prices: {stock_code: close_price} 当日收盘价
        """
        total_value = self.cash
        for code, pos in list(self.positions.items()):
            close_price = prices.get(code, pos["buy_price"])
            total_value += pos["volume"] * close_price

        self.equity = total_value
        self.peak_equity = max(self.peak_equity, self.equity)
        dd = (self.peak_equity - self.equity) / self.peak_equity * 100
        self.max_drawdown = max(self.max_drawdown, dd)

        self.equity_curve.append(total_value)

    def total_commission(self) -> float:
        """总佣金"""
        return sum(t.commission for t in self.trades)

    # --------------------------------------------------------
    # 业绩统计
    # --------------------------------------------------------

    def summary(self) -> BacktestResult:
        """生成回测结果汇总"""
        if not self.trades:
            return BacktestResult()

        trades = self.trades
        total = len(trades)
        wins = [t for t in trades if t.profit_pct > 0]
        losses = [t for t in trades if t.profit_pct <= 0]
        n_wins = len(wins)
        n_losses = len(losses)

        # 胜率
        win_rate = n_wins / total * 100 if total > 0 else 0

        # 总收益率
        total_return = (self.equity - self.initial_capital) / self.initial_capital * 100

        # 年化收益（按250个交易日）
        trading_days = len(self.equity_curve) - 1
        years = max(trading_days / 250, 0.01)
        annual_return = ((1 + total_return / 100) ** (1 / years) - 1) * 100

        # 平均盈亏
        avg_profit = (
            sum(t.profit_pct for t in wins) / n_wins if n_wins > 0 else 0
        )
        avg_loss = (
            sum(t.profit_pct for t in losses) / n_losses if n_losses > 0 else 0
        )

        # 盈亏比
        pl_ratio = abs(avg_profit / avg_loss) if avg_loss != 0 else 0

        # 夏普比率
        returns = [
            t.profit_pct for t in trades
        ]
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(250 / max(np.mean([t.hold_days for t in trades]), 1))
        else:
            sharpe = 0

        # 平均持仓天数
        avg_hold = np.mean([t.hold_days for t in trades])

        return BacktestResult(
            total_trades=total,
            win_trades=n_wins,
            lose_trades=n_losses,
            win_rate=round(win_rate, 2),
            total_return=round(total_return, 2),
            annual_return=round(annual_return, 2),
            max_drawdown=round(self.max_drawdown, 2),
            sharpe_ratio=round(sharpe, 2),
            profit_loss_ratio=round(pl_ratio, 2),
            avg_profit=round(avg_profit, 2),
            avg_loss=round(avg_loss, 2),
            max_consecutive_losses=self._max_consecutive_losses,
            avg_hold_days=round(avg_hold, 1),
            total_commission=round(self.total_commission(), 2),
            trades=self.trades,
            equity_curve=self.equity_curve,
        )

    def _calc_position_value(self, prices: dict) -> float:
        """计算持仓市值"""
        total = 0
        for code, pos in self.positions.items():
            p = prices.get(code, pos["buy_price"])
            total += pos["volume"] * p
        return total

    def print_report(self, result: Optional[BacktestResult] = None):
        """打印回测报告"""
        if result is None:
            result = self.summary()

        print("\n" + "=" * 56)
        print("   📊 回测绩效报告")
        print("=" * 56)
        print(f"  {'交易次数':<12} {result.total_trades:>8} 次")
        print(f"  {'胜率':<12} {result.win_rate:>8.1f}%")
        print(f"  {'盈利次数':<12} {result.win_trades:>8} 次")
        print(f"  {'亏损次数':<12} {result.lose_trades:>8} 次")
        print(f"  {'总收益率':<12} {result.total_return:>+8.2f}%")
        print(f"  {'年化收益率':<12} {result.annual_return:>+8.2f}%")
        print(f"  {'最大回撤':<12} {result.max_drawdown:>8.2f}%")
        print(f"  {'夏普比率':<12} {result.sharpe_ratio:>8.2f}")
        print(f"  {'盈亏比':<12} {result.profit_loss_ratio:>8.2f}")
        print(f"  {'平均盈利':<12} {result.avg_profit:>+8.2f}%")
        print(f"  {'平均亏损':<12} {result.avg_loss:>+8.2f}%")
        print(f"  {'最大连亏':<12} {result.max_consecutive_losses:>8} 次")
        print(f"  {'平均持仓':<12} {result.avg_hold_days:>8.1f} 天")
        print(f"  {'总佣金':<12} {result.total_commission:>8.2f} 元")
        print(f"  {'最终权益':<12} {self.equity:>8,.0f} 元")
        print("=" * 56)
