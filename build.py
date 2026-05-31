#!/usr/bin/env python3
"""
编译脚本 - 将 Python 项目打包为独立的 Windows 可执行文件
使用方法:
    python build.py             # 编译桌面版 + Web版
    python build.py desktop     # 仅编译桌面版
    python build.py web         # 仅编译 Web 版
    python build.py all         # 全部编译
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"

# 确保可执行文件能被找到
os.environ["PATH"] += os.pathsep + str(BASE_DIR / ".venv" / "Scripts")


def clean_build():
    """清理旧的构建产物"""
    print("正在清理旧的构建产物...")
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"  已删除: {d}")
    # 清理 .spec 文件
    for spec in BASE_DIR.glob("*.spec"):
        spec.unlink()
    print("  清理完成\n")


def build_desktop():
    """编译桌面应用 (PyQt6)"""
    print("=" * 60)
    print("开始编译桌面版应用...")
    print("=" * 60)

    # 查找 PyQt6 的 Qt6 插件路径
    import PyQt6
    pyqt6_dir = Path(PyQt6.__file__).parent
    qt_plugins_dir = pyqt6_dir / "Qt6" / "plugins"
    print(f"  PyQt6 路径: {pyqt6_dir}")
    print(f"  Qt 插件路径: {qt_plugins_dir}")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "DataPlatform_Desktop",
        "--onefile",
        "--windowed",  # 无控制台窗口
        "--noconfirm",
        "--clean",
        # 添加数据文件
        "--add-data", f"{BASE_DIR / 'config.py'}{os.pathsep}.",
        "--add-data", f"{BASE_DIR / 'crawler'}{os.pathsep}crawler",
        "--add-data", f"{BASE_DIR / 'analyzer'}{os.pathsep}analyzer",
        "--add-data", f"{BASE_DIR / 'desktop'}{os.pathsep}desktop",
        # 隐藏导入
        "--hidden-import", "PyQt6.sip",
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "PyQt6.QtGui",
        "--hidden-import", "lxml",
        "--hidden-import", "lxml._elementpath",
        "--hidden-import", "lxml.etree",
        "--hidden-import", "bs4",
        "--hidden-import", "pandas",
        "--hidden-import", "numpy",
        "--hidden-import", "matplotlib",
        "--hidden-import", "matplotlib.backends.backend_agg",
        "--hidden-import", "seaborn",
        "--hidden-import", "sklearn",
        "--hidden-import", "requests",
        "--hidden-import", "schedule",
        "--collect-all", "PyQt6",
        "--collect-all", "matplotlib",
        "--collect-all", "pandas",
        # 入口脚本
        str(BASE_DIR / "main.py"),
    ]

    print("  执行 PyInstaller...")
    result = subprocess.run(cmd, cwd=BASE_DIR)
    if result.returncode == 0:
        print(f"\n  ✅ 桌面版编译成功!")
        exe_path = DIST_DIR / "DataPlatform_Desktop" / "DataPlatform_Desktop.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"     输出: {exe_path}")
            print(f"     大小: {size_mb:.1f} MB")
    else:
        print(f"\n  ❌ 桌面版编译失败 (错误码: {result.returncode})")
    return result.returncode


def build_web():
    """编译 Web 服务器"""
    print("=" * 60)
    print("开始编译 Web 服务版...")
    print("=" * 60)

    # 创建入口脚本 - 因为 uvicorn 的 reload 模式在 PyInstaller 中不支持
    web_entry = BASE_DIR / "_web_entry.py"
    web_entry.write_text("""\
# Web 服务入口 - 用于 PyInstaller 打包
import sys
import os
from pathlib import Path

# 确保能找到资源文件
os.chdir(Path(__file__).parent)

from web_app.app import create_app
import uvicorn

if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
""", encoding="utf-8")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "DataPlatform_Web",
        "--onefile",
        "--noconfirm",
        "--clean",
        # 添加数据文件 (模板 + 静态文件)
        "--add-data", f"{BASE_DIR / 'config.py'}{os.pathsep}.",
        "--add-data", f"{BASE_DIR / 'crawler'}{os.pathsep}crawler",
        "--add-data", f"{BASE_DIR / 'analyzer'}{os.pathsep}analyzer",
        "--add-data", f"{BASE_DIR / 'web_app'}{os.pathsep}web_app",
        "--add-data", f"{BASE_DIR / 'web_app' / 'templates'}{os.pathsep}web_app/templates",
        # 隐藏导入
        "--hidden-import", "uvicorn",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "fastapi",
        "--hidden-import", "starlette",
        "--hidden-import", "pydantic",
        "--hidden-import", "jinja2",
        "--hidden-import", "aiofiles",
        "--hidden-import", "python_multipart",
        "--hidden-import", "yarl",
        "--hidden-import", "multidict",
        "--hidden-import", "lxml",
        "--hidden-import", "bs4",
        "--hidden-import", "requests",
        "--collect-all", "uvicorn",
        "--collect-all", "fastapi",
        "--collect-all", "starlette",
        "--collect-all", "jinja2",
        # 入口脚本
        str(web_entry),
    ]

    print("  执行 PyInstaller...")
    result = subprocess.run(cmd, cwd=BASE_DIR)

    # 清理临时入口脚本
    if web_entry.exists():
        web_entry.unlink()

    if result.returncode == 0:
        print(f"\n  ✅ Web 版编译成功!")
        exe_path = DIST_DIR / "DataPlatform_Web" / "DataPlatform_Web.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"     输出: {exe_path}")
            print(f"     大小: {size_mb:.1f} MB")
    else:
        print(f"\n  ❌ Web 版编译失败 (错误码: {result.returncode})")
    return result.returncode


def build_all():
    """编译所有版本"""
    print("\n" + "=" * 60)
    print("         全能数据平台 - 编译打包")
    print("=" * 60)

    results = {}
    results["desktop"] = build_desktop()
    results["web"] = build_web()

    print("\n" + "=" * 60)
    print("编译结果汇总:")
    for name, code in results.items():
        status = "✅ 成功" if code == 0 else "❌ 失败"
        print(f"  {name}: {status}")
    print("=" * 60)

    return all(code == 0 for name, code in results.items())


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "all":
        build_all()
    elif sys.argv[1] == "desktop":
        build_desktop()
    elif sys.argv[1] == "web":
        build_web()
    elif sys.argv[1] == "clean":
        clean_build()
    else:
        print(f"用法: python build.py [desktop|web|all|clean]")
        sys.exit(1)
