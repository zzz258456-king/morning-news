#!/usr/bin/env python3
"""
全能数据平台 - 主入口
集爬虫、数据分析、机器学习、Web服务、桌面应用为一体的综合性数据平台

用法:
    python main.py web          # 启动Web服务 (FastAPI)
    python main.py desktop      # 启动桌面应用 (PyQt6)
    python main.py crawler      # 命令行爬虫模式
    python main.py analyze      # 命令行分析模式
    python main.py              # 交互式菜单选择
"""
import sys
import argparse
import logging
from pathlib import Path

# 将项目根目录加入路径
BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import LOG_LEVEL, LOG_FORMAT

# 配置日志
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def start_web_server():
    """启动 Web 服务器 (FastAPI)"""
    try:
        import uvicorn
        from config import WEB_HOST, WEB_PORT, WEB_DEBUG
        logger.info(f"正在启动 Web 服务: http://{WEB_HOST}:{WEB_PORT}")
        print(f"\n🌐 Web 服务启动中...")
        print(f"   本地访问: http://{WEB_HOST}:{WEB_PORT}")
        print(f"   API文档:  http://{WEB_HOST}:{WEB_PORT}/docs")
        print(f"   健康检查: http://{WEB_HOST}:{WEB_PORT}/health\n")
        uvicorn.run(
            "web_app.app:create_app",
            host=WEB_HOST,
            port=WEB_PORT,
            reload=WEB_DEBUG,
            factory=True,
        )
    except ImportError as e:
        logger.error(f"依赖缺失: {e}")
        print(f"❌ 请先安装依赖: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.exception("Web 服务启动失败")
        print(f"❌ Web 服务启动失败: {e}")
        sys.exit(1)


def start_desktop_app():
    """启动桌面应用 (PyQt6)"""
    try:
        from desktop import run_desktop_app
        logger.info("正在启动桌面应用...")
        print("\n🖥️  桌面应用启动中...\n")
        run_desktop_app()
    except ImportError as e:
        logger.error(f"依赖缺失: {e}")
        print(f"❌ 请先安装依赖: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.exception("桌面应用启动失败")
        print(f"❌ 桌面应用启动失败: {e}")
        sys.exit(1)


def run_crawler_cli():
    """命令行爬虫模式"""
    url = input("请输入要爬取的 URL: ").strip()
    if not url:
        print("❌ URL 不能为空")
        return

    from crawler import WebScraper
    scraper = WebScraper()

    print(f"\n🕷️  正在爬取: {url}")
    result = scraper.crawl(url)

    if result.success:
        print(f"\n✅ 爬取成功!")
        print(f"   标题: {result.title or '(无标题)'}")
        print(f"   内容长度: {len(result.content)} 字符")
        print(f"   链接数: {result.metadata.get('links_count', 0)}")
        print(f"   结果已保存到 data/raw/ 目录")
    else:
        print(f"\n❌ 爬取失败 (状态码: {result.status_code})")


def run_analyzer_cli():
    """命令行分析模式"""
    import glob
    from analyzer import DataProcessor, DataVisualizer

    # 查找可用数据文件
    data_files = list(Path("data/raw").glob("*.csv")) + list(Path("data/raw").glob("*.json"))

    if not data_files:
        print("📂 未找到数据文件，请先使用爬虫采集数据")
        print("   你也可以指定文件路径:")
        file_path = input("   文件路径 (留空取消): ").strip()
        if not file_path:
            return
        data_files = [Path(file_path)]

    print("\n📊 可用的数据文件:")
    for i, f in enumerate(data_files):
        print(f"   [{i}] {f}")

    try:
        idx = int(input("\n请选择文件编号: "))
        selected = data_files[idx]
    except (ValueError, IndexError):
        print("❌ 无效选择")
        return

    processor = DataProcessor()
    try:
        if selected.suffix == ".csv":
            df = processor.load_csv(selected)
        else:
            df = processor.load_json(selected)

        print(f"\n已加载: {len(df)} 行 × {len(df.columns)} 列")

        # 自动清洗
        print("\n🧹 正在清洗数据...")
        processor.clean()

        # 显示统计信息
        summary = processor.summary()
        print("\n📋 数据概况:")
        print(f"   行数: {summary['行数']}")
        print(f"   列数: {summary['列数']}")
        print(f"   内存: {summary['内存占用']}")

        print("\n📋 各列信息:")
        for col, info in summary['各列信息'].items():
            print(f"   {col}:")
            print(f"     类型: {info['类型']}")
            print(f"     非空值: {info['非空值']}/{summary['行数']}")
            print(f"     唯一值: {info['唯一值']}")

        # 导出
        output = processor.export_csv()
        print(f"\n💾 已导出: {output}")

    except Exception as e:
        print(f"❌ 分析失败: {e}")


def show_interactive_menu():
    """交互式菜单"""
    print("""
╔══════════════════════════════════════╗
║       🚀 全能数据平台 v1.0           ║
║                                      ║
║   [1] 🌐 启动 Web 服务              ║
║   [2] 🖥️  启动桌面应用              ║
║   [3] 🕷️  命令行爬虫                ║
║   [4] 📊 命令行数据分析             ║
║   [0] ❌ 退出                       ║
╚══════════════════════════════════════╝
""")

    choices = {
        "1": ("启动 Web 服务", start_web_server),
        "2": ("启动桌面应用", start_desktop_app),
        "3": ("命令行爬虫", run_crawler_cli),
        "4": ("命令行数据分析", run_analyzer_cli),
    }

    choice = input("请选择 [0-4]: ").strip()

    if choice == "0":
        print("👋 再见!")
        return
    elif choice in choices:
        name, func = choices[choice]
        print(f"\n▶️  执行: {name}")
        func()
    else:
        print("❌ 无效选择")


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(
        description="全能数据平台 - 集爬虫、数据分析、ML、Web、桌面于一体",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "mode", nargs="?", default="menu",
        choices=["web", "desktop", "crawler", "analyze", "menu"],
        help="运行模式 (默认: menu 交互菜单)"
    )

    args = parser.parse_args()

    mode_map = {
        "web": start_web_server,
        "desktop": start_desktop_app,
        "crawler": run_crawler_cli,
        "analyze": run_analyzer_cli,
        "menu": show_interactive_menu,
    }

    mode_map[args.mode]()


if __name__ == "__main__":
    main()
