#!/usr/bin/env python3
"""
量化回测系统 GUI 启动入口
用法:
    python run_ui.py              # 启动图形界面
    python run_ui.py --cli        # 命令行回测（无界面）
    python run_ui.py --quick      # 快速模式命令行回测
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from config import LOG_LEVEL, LOG_FORMAT

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)


def main():
    parser = argparse.ArgumentParser(description="🔬 量化回测系统")
    parser.add_argument("--cli", action="store_true", help="命令行模式，不启动UI")
    parser.add_argument("--quick", action="store_true", help="快速模式（CLI下）")
    parser.add_argument("--score", type=int, default=14, help="最低评分门槛")
    parser.add_argument("--max-buy", type=int, default=3, help="每日最多买入")
    parser.add_argument("--export", action="store_true", help="导出CSV")
    args = parser.parse_args()

    if args.cli or args.quick:
        # 命令行模式
        from strategy.run_backtest import main as cli_main
        sys.argv = ["run_backtest.py"]
        if args.quick:
            sys.argv.append("--quick")
        if args.export:
            sys.argv.append("--export")
        sys.argv.extend(["--score", str(args.score)])
        sys.argv.extend(["--max-buy", str(args.max_buy)])
        cli_main()
    else:
        # GUI 模式
        try:
            from strategy.ui.main_window import run_ui
            run_ui()
        except ImportError as e:
            print(f"❌ GUI 依赖缺失: {e}")
            print("   尝试: pip install PyQt6 matplotlib")
            sys.exit(1)


if __name__ == "__main__":
    main()
