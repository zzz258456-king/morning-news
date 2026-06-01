#!/usr/bin/env python
"""
新闻晨报系统 —— 主入口
每日开盘前运行：抓取新闻 → Claude 分析 → 钉钉推送

用法：
    python run_morning.py              # 完整流程（抓取 → 分析 → 推送）
    python run_morning.py --fetch      # 仅测试抓取
    python run_morning.py --analyze    # 仅测试分析（需先有缓存）
    python run_morning.py --send       # 仅测试钉钉推送
    python run_morning.py --dry-run    # 抓取 + 分析，不推送，打印结果到控制台
"""
import argparse
import json
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from morning.config import load_config, get_config
from morning.news_fetcher import fetch_all_news
from morning.ai_analyzer import analyze_news, AnalysisResult
from morning.dingtalk_sender import send_analysis, build_markdown

# ---------- 日志配置 ----------


def _is_monday() -> bool:
    """判断今天是否是周一"""
    return datetime.now().weekday() == 0  # 0 = Monday


def setup_logging(verbose: bool = False):
    """配置日志输出"""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%H:%M:%S")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # 关闭第三方库的详细日志
    for name in ["anthropic", "urllib3", "feedparser"]:
        logging.getLogger(name).setLevel(logging.WARNING)


# ---------- 子命令 ----------

def cmd_fetch(verbose: bool, max_per_source: int = 20):
    """仅测试新闻抓取"""
    logging.info("=" * 40)
    logging.info("📡 测试新闻抓取")
    logging.info("=" * 40)

    if _is_monday():
        max_per_source = 50
        logging.info("📅 周一模式：加大抓取量覆盖周末消息")

    news_list = fetch_all_news(max_per_source=max_per_source)
    if not news_list:
        logging.warning("⚠️ 未抓取到任何新闻，请检查 RSS 源 URL")
        return news_list

    logging.info("")
    logging.info("共抓取 %d 条新闻：", len(news_list))
    for i, news in enumerate(news_list, 1):
        print(f"  {i:2d}. [{news.source_name}] {news.title}")
        if verbose:
            print(f"      链接: {news.link}")
    logging.info("")
    return news_list


def cmd_analyze(verbose: bool):
    """测试 AI 分析（先抓取新闻）"""
    logging.info("=" * 40)
    logging.info("🤖 测试 AI 分析")
    logging.info("=" * 40)

    news_list = cmd_fetch(verbose)
    if not news_list:
        return None

    logging.info("开始分析...")
    is_monday = _is_monday()
    if is_monday:
        logging.info("📅 周一模式：AI 将汇总周末消息面")
    result = analyze_news(news_list, is_monday=is_monday)

    if not result.valid:
        logging.warning("⚠️ 分析结果为空")
        return result

    print_analysis(result)
    return result


def cmd_send(verbose: bool):
    """测试钉钉推送（先抓取 + 分析）"""
    logging.info("=" * 40)
    logging.info("📤 测试钉钉推送")
    logging.info("=" * 40)

    result = cmd_analyze(verbose)
    if not result:
        return False

    config = get_config()
    source_names = [s.name for s in config.rss_sources]

    logging.info("正在推送钉钉...")
    success = send_analysis(result, source_names)

    if success:
        logging.info("✅ 钉钉推送成功")
    else:
        logging.error("❌ 钉钉推送失败")
    return success


def cmd_dry_run(verbose: bool):
    """抓取 + 分析，结果打印到控制台，不推送"""
    logging.info("=" * 40)
    if _is_monday():
        logging.info("🔍 干运行模式（周一 · 周末消息汇总）")
    else:
        logging.info("🔍 干运行模式（不推送钉钉）")
    logging.info("=" * 40)

    result = cmd_analyze(verbose)
    if not result or not result.valid:
        return

    config = get_config()
    source_names = [s.name for s in config.rss_sources]

    print("\n" + "=" * 60)
    print("📋 以下为即将推送到钉钉的 Markdown 内容：")
    print("=" * 60 + "\n")

    markdown = build_markdown(result, source_names)
    print(markdown)

    print("\n" + "=" * 60)
    print(f"✅ 干运行完成（共 {len(markdown)} 字符）")
    print("=" * 60)


def cmd_full(verbose: bool):
    """完整流程：抓取 → 分析 → 推送"""
    logging.info("=" * 40)
    logging.info("🚀 新闻晨报系统 - 完整流程")
    logging.info("=" * 40)

    is_monday = _is_monday()
    max_per_source = 50 if is_monday else 20
    if is_monday:
        logging.info("📅 周一模式：加大抓取量覆盖周末消息")

    # 1. 抓取
    news_list = fetch_all_news(max_per_source=max_per_source)
    if not news_list:
        logging.error("❌ 未抓取到新闻，流程终止")
        return False

    # 2. 分析
    if is_monday:
        logging.info("📅 周一模式：AI 将汇总周末消息面")
    result = analyze_news(news_list, is_monday=is_monday)
    if not result.valid:
        logging.warning("⚠️ 分析结果为空，但仍尝试推送")

    # 3. 推送
    config = get_config()
    source_names = [s.name for s in config.rss_sources]
    success = send_analysis(result, source_names)

    if success:
        logging.info("🎉 晨报推送完成！")
    else:
        logging.error("❌ 晨报推送失败")
    return success


# ---------- 辅助 ----------

def print_analysis(result: AnalysisResult):
    """在控制台打印分析结果概要"""
    print(f"\n📊 市场情绪：{result.market_sentiment}")

    # 重点推荐板块
    if result.top_picks:
        print(f"\n🔥 重点推荐板块 ({len(result.top_picks)}):")
        for pick in result.top_picks:
            print(f"   🏆 {pick.name} (强度 {pick.strength}/5)")
            if pick.stocks:
                for st in pick.stocks:
                    print(f"      → {st.code} {st.name} - {st.reason}")

    if result.good_sectors:
        print(f"\n🟢 其他利好板块 ({len(result.good_sectors)}):")
        for s in result.good_sectors:
            print(f"   - {s.name} (强度 {s.strength}/5)")

    if result.bad_sectors:
        print(f"\n🔴 利空板块 ({len(result.bad_sectors)}):")
        for name in result.bad_sectors:
            print(f"   - {name}")

    if result.stock_mentions:
        print(f"\n📊 提及个股 ({len(result.stock_mentions)}):")
        for st in result.stock_mentions:
            print(f"   - {st.code} {st.name} [{st.direction}]")

    if result.key_events:
        print(f"\n📌 关键事件 ({len(result.key_events)}):")
        for ev in result.key_events:
            print(f"   - {ev.title}")

    print(f"\n📐 JSON 原始输出 ({len(result.raw_text)} 字符)")
    try:
        pretty = json.dumps(json.loads(result.raw_text), ensure_ascii=False, indent=2)
        print(pretty[:1000])
    except Exception:
        print(result.raw_text[:500])
    print()


def check_config() -> bool:
    """检查配置是否完整，给出提示"""
    config = get_config()

    issues = []

    if not config.rss_sources:
        issues.append("❌ 未配置任何 RSS 源")

    if not config.ai.available:
        issues.append("⚠️ AI API 密钥未配置（设置 DEEPSEEK_API_KEY 或 AI_API_KEY）")

    if not config.dingtalk.available:
        issues.append("⚠️ 钉钉 Webhook URL 未配置（设置 DINGTALK_WEBHOOK_URL）")

    if issues:
        print("\n🔧 配置检查：")
        for issue in issues:
            print(f"  {issue}")
        print("  编辑 .env 文件填入密钥即可")
        print()
        return False
    return True


# ---------- 主入口 ----------

def main():
    parser = argparse.ArgumentParser(
        description="📰 新闻晨报系统 — 抓取财经新闻 → Claude 分析 → 钉钉推送",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python run_morning.py                   完整流程
    python run_morning.py --dry-run         预览但不推送
    python run_morning.py --fetch           仅测试新闻抓取
    python run_morning.py --analyze         测试分析
    python run_morning.py -v                详细日志
        """,
    )
    parser.add_argument(
        "--fetch", action="store_true", help="仅测试新闻抓取"
    )
    parser.add_argument(
        "--analyze", action="store_true", help="测试抓取 + 分析"
    )
    parser.add_argument(
        "--send", action="store_true", help="测试完整流程并推送钉钉"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="干运行：抓取+分析，结果打印到控制台，不推送"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="详细日志输出"
    )

    args = parser.parse_args()

    # 初始化
    setup_logging(args.verbose)
    load_config()
    print(f"🚀 新闻晨报系统 v{morning.__version__}\n")
    if _is_monday():
        print("📅 周一模式：将汇总周末消息面（加大抓取量 + 专属分析提示）\n")
    check_config()

    # 路由
    if args.fetch:
        cmd_fetch(args.verbose)
    elif args.analyze:
        cmd_analyze(args.verbose)
    elif args.send:
        cmd_send(args.verbose)
    elif args.dry_run:
        cmd_dry_run(args.verbose)
    else:
        cmd_full(args.verbose)


if __name__ == "__main__":
    import morning  # noqa: 确保模块可导入
    main()
