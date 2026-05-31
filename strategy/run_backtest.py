#!/usr/bin/env python3
"""
打板策略回测 — CLI 运行入口
用法:
    python -m strategy.run_backtest
    python -m strategy.run_backtest --quick
    python -m strategy.run_backtest --score 18 --max-buy 5 --export
"""
import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

import pandas as pd

from config import LOG_LEVEL, LOG_FORMAT
from strategy.base import StrategyFactory
from strategy.board_chaser import BoardChaserStrategy, PASS_SCORE

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="📈 打板策略回测系统")
    parser.add_argument("--start", default=None, help="开始日期 YYYYMMDD")
    parser.add_argument("--end", default=None, help="结束日期 YYYYMMDD")
    parser.add_argument("--score", type=int, default=PASS_SCORE, help="最低评分门槛")
    parser.add_argument("--max-buy", type=int, default=3, help="每日最多买入")
    parser.add_argument("--capital", type=float, default=1_000_000, help="初始资金")
    parser.add_argument("--quick", action="store_true", help="快速模式")
    parser.add_argument("--export", action="store_true", help="导出CSV")
    parser.add_argument("--silent", action="store_true", help="安静模式")
    args = parser.parse_args()

    # 日期
    if args.quick:
        end = datetime.now()
        start = end - timedelta(days=30)
        args.start = start.strftime("%Y%m%d")
        args.end = end.strftime("%Y%m%d")
        logger.info("⚡ 快速模式")
    else:
        if not args.start:
            args.start = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
        if not args.end:
            args.end = datetime.now().strftime("%Y%m%d")
        logger.info(f"📅 {args.start} → {args.end}")

    # 确保注册
    if "打板策略" not in StrategyFactory.list_strategies():
        StrategyFactory.register(BoardChaserStrategy)

    if not args.silent:
        print(f"""
╔══════════════════════════════════════╗
║   📈 量化回测系统 v3                  ║
╠══════════════════════════════════════╣
║  区间: {args.start} → {args.end}          ║
║  资金: {args.capital:>10,.0f} 元            ║
║  评分门槛: {args.score:>2}/{PASS_SCORE}分            ║
║  每日买入: {args.max_buy:>2}只                 ║
╚══════════════════════════════════════╝
""")

    strategy = StrategyFactory.create(
        "打板策略",
        initial_capital=args.capital,
        min_score=args.score,
        max_daily_buy=args.max_buy,
        start_date=args.start,
        end_date=args.end,
    )
    engine = strategy.run(
        start_date=args.start, end_date=args.end,
        min_score=args.score, max_daily_buy=args.max_buy,
    )
    strategy.print_report()

    if args.export:
        result = engine.summary()
        if result.trades:
            records = []
            for t in result.trades:
                records.append({
                    "代码": t.stock_code, "名称": t.stock_name,
                    "买入日": t.buy_date, "卖出日": t.sell_date,
                    "买入价": round(t.buy_price, 2),
                    "卖出价": round(t.sell_price, 2),
                    "收益率%": round(t.profit_pct, 2),
                    "评分": t.rating,
                    "级别": t.signal_detail.get("level", ""),
                    "板型": t.board_type,
                    "卖出原因": t.exit_reason,
                })
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = f"data/backtest/trades_{ts}.csv"
            pd.DataFrame(records).to_csv(path, index=False, encoding="utf-8-sig")
            print(f"\n💾 导出: {path}")

    return strategy


if __name__ == "__main__":
    main()
