#!/usr/bin/env python3
"""
量化回测 — CLI 运行入口
用法:
    python run.py                                      # 默认打板策略
    python run.py --quick                              # 快速模式
    python run.py --strategy 趋势                       # 趋势跟踪策略
    python run.py --score 18 --max-buy 5 --export      # 自定义打板参数
    python run.py --risk                               # 风险预警分析
    python run.py --list                               # 列出可用策略
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

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def ensure_strategies_registered():
    """确保所有策略已注册"""
    import strategy.board_chaser  # noqa: F401
    import strategy.trend_follower  # noqa: F401


def main():
    parser = argparse.ArgumentParser(description="量化回测系统 CLI")
    parser.add_argument("--strategy", default="打板策略", help="策略名称")
    parser.add_argument("--start", default=None, help="开始日期 YYYYMMDD")
    parser.add_argument("--end", default=None, help="结束日期 YYYYMMDD")
    parser.add_argument("--score", type=int, default=None, help="最低评分门槛")
    parser.add_argument("--max-buy", type=int, default=None, help="每日最多买入/最大持仓")
    parser.add_argument("--capital", type=float, default=1_000_000, help="初始资金")
    parser.add_argument("--quick", action="store_true", help="快速模式")
    parser.add_argument("--export", action="store_true", help="导出CSV")
    parser.add_argument("--silent", action="store_true", help="安静模式")
    args = parser.parse_args()

    ensure_strategies_registered()

    # 检查策略是否存在
    available = StrategyFactory.list_strategies()
    if args.strategy not in available:
        print(f"\n未知策略: {args.strategy}")
        print(f"可用策略: {', '.join(available)}")
        sys.exit(1)

    # 日期处理
    if args.quick:
        end = datetime.now()
        start = end - timedelta(days=30)
        args.start = start.strftime("%Y%m%d")
        args.end = end.strftime("%Y%m%d")
        logger.info("快速模式")
    else:
        if not args.start:
            args.start = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
        if not args.end:
            args.end = datetime.now().strftime("%Y%m%d")
        logger.info(f"区间: {args.start} -> {args.end}")

    # 构建回测参数
    strategy_params = {
        "start_date": args.start,
        "end_date": args.end,
    }

    # 根据策略类型传入不同参数
    if args.strategy == "打板策略":
        strategy_params["min_score"] = args.score or 14
        strategy_params["max_daily_buy"] = args.max_buy or 3
        strategy_params["single_pct"] = 0.10
    elif args.strategy == "趋势跟踪策略":
        strategy_params["min_score"] = args.score or 14
        strategy_params["max_positions"] = args.max_buy or 5

    if not args.silent:
        print(f"""
{'='*50}
   量化回测系统 v3
{'='*50}
   策略: {args.strategy}
   区间: {args.start} -> {args.end}
   资金: {args.capital:>12,.0f} 元
{'='*50}
""")

    # 创建并运行策略
    strategy = StrategyFactory.create(
        args.strategy,
        initial_capital=args.capital,
        **strategy_params,
    )

    engine = strategy.run(**strategy_params)
    strategy.print_report()

    # 导出
    if args.export:
        result = engine.summary()
        if result.trades:
            records = [{
                "代码": t.stock_code, "名称": t.stock_name,
                "买入日": t.buy_date, "卖出日": t.sell_date,
                "买入价": round(t.buy_price, 2),
                "卖出价": round(t.sell_price, 2),
                "收益率%": round(t.profit_pct, 2),
                "评分": t.rating,
                "级别": t.signal_detail.get("level", ""),
                "板型/策略": t.board_type or t.signal_detail.get("board_type", ""),
                "卖出原因": t.exit_reason,
            } for t in result.trades]

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = f"data/backtest/trades_{ts}.csv"
            Path("data/backtest").mkdir(parents=True, exist_ok=True)
            pd.DataFrame(records).to_csv(path, index=False, encoding="utf-8-sig")
            print(f"\n导出: {path}")

    return strategy


if __name__ == "__main__":
    main()
