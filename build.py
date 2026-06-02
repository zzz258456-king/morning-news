#!/usr/bin/env python3
"""
打包脚本 — 将 StockStrategySystem 编译为独立 exe

用法:
    python build.py                    # 打包 StockStrategySystem
    python build.py --legacy           # 打包旧版回测系统(run.py)
    python build.py --gui              # 打包 GUI 模式（隐藏控制台）
    python build.py --clean            # 清理构建文件

注意：Windows PowerShell 下需先执行 $env:PYTHONIOENCODING='utf-8'
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def build(gui_mode: bool = False, clean: bool = False, legacy: bool = False):
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

    # 确定入口和输出名
    if legacy:
        entry_arg = str(base / "run.py")
        output_name = "量化回测系统"
    else:
        entry_arg = str(base / "main.py")
        output_name = "StockStrategySystem"

    print("=" * 60)
    print(f"  打包 {output_name} v2")
    print("=" * 60)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", output_name,
        "--onedir",
        "--noconfirm",
    ]

    if gui_mode:
        cmd.append("--noconsole")
    else:
        cmd.append("--console")

    # 添加数据文件
    if (base / "config.yaml").exists():
        cmd.extend(["--add-data", f"{base / 'config.yaml'}{os.pathsep}."])

    # 隐藏导入
    hidden = [
        "pandas", "numpy",
        "akshare", "baostock",
        "feedparser", "openai",
        "yaml", "dotenv",
        "requests", "bs4", "lxml",
        "schedule",
    ]
    if legacy:
        hidden += [
            "PyQt6", "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets",
            "PyQt6.QtSvg", "PyQt6.QtPrintSupport",
            "matplotlib", "matplotlib.backends.backend_qtagg",
            "matplotlib.backends.backend_agg",
            "matplotlib.pyplot", "matplotlib.figure",
        ]
    for mod in hidden:
        cmd.extend(["--hidden-import", mod])

    # 排除项目中未直接使用的大型包，减少体积和启动时间
    excluded = ["torch", "torchvision", "tensorflow", "sympy", "cv2"]
    for mod in excluded:
        cmd.extend(["--exclude-module", mod])

    # 收集完整包数据
    collect_pkgs = ["akshare"]
    if legacy:
        collect_pkgs += ["PyQt6", "matplotlib"]
    for pkg in collect_pkgs:
        cmd.extend(["--collect-all", pkg])

    cmd.append(entry_arg)

    # 执行
    print(f"  入口: {Path(entry_arg).name}")
    print(f"  输出名: {output_name}")
    print(f"  模式: {'GUI (无控制台)' if gui_mode else '控制台'}")
    print(f"  输出: dist/{output_name}/")
    print("=" * 60)

    result = subprocess.run(cmd, cwd=base)
    if result.returncode != 0:
        print("\n打包失败")
        sys.exit(1)

    # 复制配置文件到输出目录
    dist_dir = base / "dist" / output_name
    if (base / "config.yaml").exists():
        shutil.copy2(base / "config.yaml", dist_dir / "config.yaml")
    env_file = base / ".env"
    if env_file.exists():
        shutil.copy2(env_file, dist_dir / ".env")

    # 统计大小
    exe_path = dist_dir / f"{output_name}.exe"
    exe_size = exe_path.stat().st_size / 1024 / 1024 if exe_path.exists() else 0
    total_size = sum(f.stat().st_size for f in dist_dir.rglob("*") if f.is_file()) / 1024 / 1024

    print("\n" + "=" * 60)
    print("  打包成功!")
    print(f"  程序: {exe_path}")
    print(f"  EXE大小: {exe_size:.1f} MB")
    print(f"  总大小: {total_size:.1f} MB")
    print("=" * 60)
    print()
    print(f"  {output_name} 使用方式:")
    print(f"    {output_name}.exe --help       -> 查看帮助")
    print(f"    {output_name}.exe --dry-run    -> 晨报预览")
    print(f"    {output_name}.exe --morning    -> 完整晨报")
    print(f"    {output_name}.exe --risk       -> 风险预警")
    print(f"    {output_name}.exe --evolution  -> 策略进化")
    print(f"    {output_name}.exe --all        -> 常驻进程")
    print()
    print("  目录说明:")
    print(f"    {output_name}.exe    程序入口")
    print("    config.yaml          统一配置")
    print("    data/                数据目录")
    print("    .env                API密钥")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="打包 StockStrategySystem")
    parser.add_argument("--gui", action="store_true", help="GUI模式(隐藏控制台)")
    parser.add_argument("--clean", action="store_true", help="清理构建文件")
    parser.add_argument("--legacy", action="store_true", help="打包旧版回测系统(run.py)")
    args = parser.parse_args()
    build(gui_mode=args.gui, clean=args.clean, legacy=args.legacy)
