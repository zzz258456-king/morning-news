#!/usr/bin/env python3
"""
打包脚本 — 将量化回测系统编译为独立 exe

用法:
    python build.py              # 打包（默认带控制台）
    python build.py --gui        # 打包 GUI 模式（隐藏控制台）
    python build.py --clean      # 清理构建文件

注意：Windows PowerShell 下需先执行 $env:PYTHONIOENCODING='utf-8'
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def build(gui_mode: bool = False, clean: bool = False):
    base = Path(__file__).parent.resolve()

    if clean:
        for d in ["build", "dist"]:
            p = base / d
            if p.exists():
                shutil.rmtree(p)
                print(f"清理: {d}/")
        for f in base.glob("*.spec"):
            f.unlink()
            print(f"清理: {f.name}")
        print("清理完成")
        return

    # 检查必要文件
    if not (base / "morning" / "config.yaml").exists():
        print("缺少 morning/config.yaml")
        return

    print("=" * 60)
    print("  打包量化回测系统 v3")
    print("=" * 60)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "量化回测系统",
        "--onedir",
        "--noconfirm",
    ]

    if gui_mode:
        cmd.append("--noconsole")
    else:
        cmd.append("--console")

    # 添加数据目录
    cmd.extend([
        "--add-data", f"{base / 'morning' / 'config.yaml'}{os.pathsep}morning"
    ])

    # 隐藏导入（只导入实际需要的，不要用 --collect-all pandas）
    hidden = [
        "PyQt6", "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets",
        "PyQt6.QtSvg", "PyQt6.QtPrintSupport",
        "matplotlib", "matplotlib.backends.backend_qtagg",
        "matplotlib.backends.backend_agg",
        "matplotlib.pyplot", "matplotlib.figure",
        "pandas", "numpy",
        "akshare", "baostock",
        "feedparser", "openai",
        "yaml", "dotenv",
        "requests", "bs4", "lxml",
        "schedule",
    ]
    for mod in hidden:
        cmd.extend(["--hidden-import", mod])

    # 收集完整包数据（akshare 需要数据文件，PyQt6/matplotlib 需要完整资源）
    for pkg in ["akshare", "PyQt6", "matplotlib"]:
        cmd.extend(["--collect-all", pkg])

    # 入口
    cmd.append(str(base / "run.py"))

    # 执行
    print(f"  输入: run.py")
    print(f"  模式: {'GUI (无控制台)' if gui_mode else '控制台'}")
    print(f"  输出: dist/量化回测系统/")
    print("=" * 60)

    result = subprocess.run(cmd, cwd=base)
    if result.returncode != 0:
        print(f"\n打包失败")
        sys.exit(1)

    # 复制配置文件到输出目录
    dist_dir = base / "dist" / "量化回测系统"
    out_morning = dist_dir / "morning"
    out_morning.mkdir(exist_ok=True)
    shutil.copy2(base / "morning" / "config.yaml", out_morning / "config.yaml")

    # 如果 .env 存在也复制过去
    env_file = base / ".env"
    if env_file.exists():
        shutil.copy2(env_file, dist_dir / ".env")

    # 统计大小
    exe_path = dist_dir / "量化回测系统.exe"
    if exe_path.exists():
        exe_size = exe_path.stat().st_size / 1024 / 1024
    else:
        exe_size = 0
    total_size = sum(f.stat().st_size for f in dist_dir.rglob("*") if f.is_file())

    print("\n" + "=" * 60)
    print("  打包成功!")
    print(f"  程序: {exe_path}")
    print(f"  EXE大小: {exe_size:.1f} MB")
    print(f"  总大小: {total_size / 1024 / 1024:.1f} MB")
    print("=" * 60)
    print()
    print("  使用方式:")
    print("    双击 run.exe         -> 启动图形界面")
    print("    run.exe --quick      -> 命令行快速回测")
    print("    run.exe --risk       -> 风险预警分析")
    print("    run.exe --score 18   -> 自定义参数回测")
    print()
    print("  目录说明:")
    print("    run.exe             程序入口")
    print("    morning/config.yaml 配置文件")
    print("    data/               数据缓存目录")
    print("    .env                环境变量")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="打包量化回测系统")
    parser.add_argument("--gui", action="store_true", help="GUI模式(隐藏控制台)")
    parser.add_argument("--clean", action="store_true", help="清理构建文件")
    args = parser.parse_args()
    build(gui_mode=args.gui, clean=args.clean)
