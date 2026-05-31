#!/usr/bin/env python3
"""
打板策略回测 —— 运行入口
用法:
    python strategy/run_backtest.py                  # 默认近3个月回测
    python strategy/run_backtest.py --start 20260101 --end 20260529
    python strategy/run_backtest.py --rating 65       # 提高评分门槛
    python strategy/run_backtest.py --max-buy 5       # 每日最多买5只
    python strategy/run_backtest.py --quick           # 快速模式(只取最近20天)
    python strategy/run_backtest.py --export          # 导出交易流水CSV
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

import pandas as pd

from config import LOG_LEVEL, LOG_FORMAT
from strategy.board_chaser import BoardChaserStrategy, _PASS_SCORE
from strategy.data_fetcher import get_today_str

# 日志
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def get_default_dates() -> tuple[str, str]:
    """获取近3个月的起止日期"""
    from datetime import datetime, timedelta
    end = datetime.now()
    start = end - timedelta(days=90)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def main():
    parser = argparse.ArgumentParser(
        description="📈 打板策略回测系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--start", default=None, help="开始日期 YYYYMMDD")
    parser.add_argument("--end", default=None, help="结束日期 YYYYMMDD")
    parser.add_argument("--score", type=int, default=14, help="最低评分门槛 (默认14/40分)")
    parser.add_argument("--max-buy", type=int, default=3, help="每日最多买入 (默认3)")
    parser.add_argument("--capital", type=float, default=1_000_000, help="初始资金 (默认1,000,000)")
    parser.add_argument("--quick", action="store_true", help="快速模式(只跑最近30天)")
    parser.add_argument("--export", action="store_true", help="导出交易流水CSV")
    parser.add_argument("--silent", action="store_true", help="安静模式(只输出结果)")

    args = parser.parse_args()

    # 确定日期范围
    if args.quick:
        from datetime import datetime, timedelta
        end = datetime.now()
        start = end - timedelta(days=30)
        start_date = start.strftime("%Y%m%d")
        end_date = end.strftime("%Y%m%d")
        logger.info("⚡ 快速模式: 近30天")
    else:
        start_date = args.start
        end_date = args.end
        if not start_date or not end_date:
            start_date, end_date = get_default_dates()
        logger.info(f"📅 回测区间: {start_date} → {end_date}")

    # 初始化策略
    strategy = BoardChaserStrategy(initial_capital=args.capital)

    if not args.silent:
        print(f"""
╔══════════════════════════════════════╗
║      📈 打板策略回测系统              ║
╠══════════════════════════════════════╣
║  区间: {start_date} → {end_date}          ║
║  资金: {args.capital:>10,.0f} 元            ║
║  评分门槛: {args.score:>2}/{_PASS_SCORE}分              ║
║  每日买入: {args.max_buy:>2}只                 ║
╚══════════════════════════════════════╝
""")

    # 运行回测
    engine = strategy.run(
        start_date=start_date,
        end_date=end_date,
        max_daily_buy=args.max_buy,
        min_score=args.score,
    )

    # 输出报告
    result = engine.summary()
    strategy.print_report()

    # 导出CSV
    if args.export and result.trades:
        records = []
        for t in result.trades:
            records.append({
                "代码": t.stock_code, "名称": t.stock_name,
                "买入日": t.buy_date, "卖出日": t.sell_date,
                "买入价": round(t.buy_price, 2), "卖出价": round(t.sell_price, 2),
                "收益率%": round(t.profit_pct, 2), "盈亏额": round(t.profit_amount, 2),
                "持仓天": t.hold_days, "评分": t.rating, "板型": t.board_type,
                "卖出原因": t.exit_reason,
            })

        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"data/backtest/trades_{ts}.csv"
        pd.DataFrame(records).to_csv(path, index=False, encoding="utf-8-sig")
        print(f"\n💾 交易流水已导出: {path}")

    return result


if __name__ == "__main__":
    main()
