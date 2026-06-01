#!/usr/bin/env python3
"""
量化回测系统 — 统一入口

用法:
    python run.py                 # 命令行回测（默认打板策略）
    python run.py --gui           # 启动图形界面
    python run.py --quick         # 快速回测
    python run.py --risk          # 风险预警分析
    python run.py --strategy 趋势  # 指定策略
    python run.py --list          # 列出可用策略
"""
import sys
from pathlib import Path

# --noconsole 模式下保护编码
if getattr(sys, 'frozen', False) and sys.stdout is not None:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def main():
    # 注册策略（import 触发 @register_strategy 装饰器）
    import strategy.board_chaser  # noqa: F401
    import strategy.trend_follower  # noqa: F401
    from strategy.base import StrategyFactory

    # --list：列出可用策略
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        print("\n可用策略:")
        for name in StrategyFactory.list_strategies():
            info = StrategyFactory.get_strategy_info(name)
            print(f"  - {name}: {info.get('description', '')}")
        print()
        return

    # --risk：风险预警分析
    if len(sys.argv) > 1 and sys.argv[1] == "--risk":
        from strategy.risk_warning import main as risk_main
        risk_main()
        return

    # --gui：图形界面
    if len(sys.argv) > 1 and sys.argv[1] == "--gui":
        try:
            from strategy.ui.main_window import run_ui
            run_ui()
            return
        except Exception as e:
            print(f"\nGUI 启动失败: {e}")
            print("当前环境不支持图形界面（需桌面环境 + PyQt6）")
            if getattr(sys, 'frozen', False):
                input("\n按回车退出...")
            return

    # 默认：命令行回测（支持 --strategy 指定策略）
    # 构造假 argv 传给 run_backtest
    import shlex
    cli_args = sys.argv[1:] if len(sys.argv) > 1 else []
    # 保留原始行为：无参数时从 run_backtest 的默认行为走
    from strategy.run_backtest import main as cli_main
    # 临时替换 sys.argv
    old_argv = sys.argv
    sys.argv = ["run_backtest.py"] + cli_args
    try:
        cli_main()
    finally:
        sys.argv = old_argv

    if getattr(sys, 'frozen', False):
        input("\n回测完成，按回车退出...")


if __name__ == "__main__":
    main()
