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


# ---------- 新增命令处理函数 ----------

def cmd_watch(args, db_manager):
    """特别关注命令"""
    if not args.watch:
        print("请指定操作: add/remove/list/group")
        return

    action = args.watch[0]

    from morning.watchlist_manager import WatchlistManager
    manager = WatchlistManager(db_manager)

    if action == "add":
        if len(args.watch) < 3:
            print("用法: --watch add <股票代码> <股票名称> [--reason 理由] [--group 分组]")
            return

        stock_code = args.watch[1]
        stock_name = args.watch[2]
        reason = ""
        group = "默认"

        # 解析可选参数
        i = 3
        while i < len(args.watch):
            if args.watch[i] == "--reason" and i + 1 < len(args.watch):
                reason = args.watch[i + 1]
                i += 2
            elif args.watch[i] == "--group" and i + 1 < len(args.watch):
                group = args.watch[i + 1]
                i += 2
            else:
                i += 1

        # 获取当前价格（简化处理，实际应从行情接口获取）
        price = 0.0

        success = manager.add(stock_code, stock_name, price, reason, group)
        if success:
            print(f"✅ 添加关注成功: {stock_code} {stock_name} [{group}]")
        else:
            print(f"❌ 添加关注失败")

    elif action == "remove":
        if len(args.watch) < 2:
            print("用法: --watch remove <股票代码>")
            return

        stock_code = args.watch[1]
        success = manager.remove(stock_code)
        if success:
            print(f"✅ 移除关注成功: {stock_code}")
        else:
            print(f"❌ 移除关注失败")

    elif action == "list":
        group = args.watch[1] if len(args.watch) > 1 else None
        output = manager.format_list(group)
        print(output)

    elif action == "group":
        if len(args.watch) < 3:
            print("用法: --watch group <股票代码> <新分组>")
            return

        stock_code = args.watch[1]
        new_group = args.watch[2]
        success = manager.change_group(stock_code, new_group)
        if success:
            print(f"✅ 修改分组成功: {stock_code} -> {new_group}")
        else:
            print(f"❌ 修改分组失败")


def cmd_trade(args, db_manager):
    """操作日志命令"""
    if not args.trade:
        print("请指定操作: buy/sell/watch/log/review/stats")
        return

    action = args.trade[0]

    from morning.trade_journal import TradeJournal
    journal = TradeJournal(db_manager)

    if action == "buy":
        if len(args.trade) < 4:
            print("用法: --trade buy <股票代码> <价格> <数量> [--reason 理由] [--emotion 情绪]")
            return

        stock_code = args.trade[1]
        price = float(args.trade[2])
        quantity = int(args.trade[3])
        reason = ""
        emotion = ""
        tags = []

        # 解析可选参数
        i = 4
        while i < len(args.trade):
            if args.trade[i] == "--reason" and i + 1 < len(args.trade):
                reason = args.trade[i + 1]
                i += 2
            elif args.trade[i] == "--emotion" and i + 1 < len(args.trade):
                emotion = args.trade[i + 1]
                i += 2
            elif args.trade[i] == "--tags" and i + 1 < len(args.trade):
                tags = args.trade[i + 1].split(",")
                i += 2
            else:
                i += 1

        # 获取股票名称（简化处理）
        stock_name = ""

        success = journal.record_buy(stock_code, stock_name, price, quantity, reason, emotion, tags)
        if success:
            print(f"✅ 记录买入成功: {stock_code} @ {price} x {quantity}")
        else:
            print(f"❌ 记录买入失败")

    elif action == "sell":
        if len(args.trade) < 4:
            print("用法: --trade sell <股票代码> <价格> <数量> [--reason 理由] [--emotion 情绪] [--pnl 盈亏]")
            return

        stock_code = args.trade[1]
        price = float(args.trade[2])
        quantity = int(args.trade[3])
        reason = ""
        emotion = ""
        tags = []
        profit_loss = 0.0

        # 解析可选参数
        i = 4
        while i < len(args.trade):
            if args.trade[i] == "--reason" and i + 1 < len(args.trade):
                reason = args.trade[i + 1]
                i += 2
            elif args.trade[i] == "--emotion" and i + 1 < len(args.trade):
                emotion = args.trade[i + 1]
                i += 2
            elif args.trade[i] == "--tags" and i + 1 < len(args.trade):
                tags = args.trade[i + 1].split(",")
                i += 2
            elif args.trade[i] == "--pnl" and i + 1 < len(args.trade):
                profit_loss = float(args.trade[i + 1])
                i += 2
            else:
                i += 1

        # 获取股票名称（简化处理）
        stock_name = ""

        success = journal.record_sell(stock_code, stock_name, price, quantity, reason, emotion, tags, profit_loss)
        if success:
            print(f"✅ 记录卖出成功: {stock_code} @ {price} x {quantity}")
        else:
            print(f"❌ 记录卖出失败")

    elif action == "watch":
        if len(args.trade) < 2:
            print("用法: --trade watch <股票代码> [--reason 理由]")
            return

        stock_code = args.trade[1]
        reason = ""

        if len(args.trade) > 2 and args.trade[2] == "--reason":
            reason = args.trade[3] if len(args.trade) > 3 else ""

        success = journal.record_watch(stock_code, reason)
        if success:
            print(f"✅ 记录关注成功: {stock_code}")
        else:
            print(f"❌ 记录关注失败")

    elif action == "log":
        days = 30
        if len(args.trade) > 1 and args.trade[1] == "--days":
            days = int(args.trade[2]) if len(args.trade) > 2 else 30

        records = journal.get_records(days)

        print(f"📊 操作日志 (最近{days}天)")
        print()

        for record in records:
            print(f"{record.trade_date.strftime('%Y-%m-%d %H:%M')}  {record.trade_type:5}  {record.stock_code} {record.stock_name}")
            if record.reason:
                print(f"  理由: {record.reason}")
            if record.emotion:
                print(f"  情绪: {record.emotion}")
            if record.tags:
                print(f"  标签: {', '.join(record.tags)}")
            if record.profit_loss != 0:
                print(f"  盈亏: {record.profit_loss:+.2%}")
            print()

    elif action == "review":
        days = 30
        if len(args.trade) > 1 and args.trade[1] == "--days":
            days = int(args.trade[2]) if len(args.trade) > 2 else 30

        report = journal.generate_review_report(days)
        print(report)

    elif action == "stats":
        days = 30
        if len(args.trade) > 1 and args.trade[1] == "--days":
            days = int(args.trade[2]) if len(args.trade) > 2 else 30

        stats = journal.calculate_stats(days)

        print(f"📊 交易统计 (最近{days}天)")
        print()
        print(f"总交易次数: {stats.total_trades}")
        print(f"盈利次数: {stats.win_count}")
        print(f"亏损次数: {stats.loss_count}")
        print(f"胜率: {stats.win_rate:.1%}")
        print(f"平均盈利: {stats.avg_profit:+.2%}")
        print(f"平均亏损: {stats.avg_loss:+.2%}")
        print(f"盈亏比: {stats.profit_loss_ratio:.2f}")
        print(f"最大单笔盈利: {stats.max_profit:+.2%}")
        print(f"最大单笔亏损: {stats.max_loss:+.2%}")


def cmd_db_status(args, db_manager):
    """数据库状态命令"""
    status = db_manager.get_status()

    print("📊 数据库状态")
    print()
    print(f"每日数据库数量: {status['daily_db_count']}")
    print(f"特别关注数量: {status['watchlist_count']}")
    print(f"操作记录数量: {status['trade_record_count']}")
    print(f"全局数据库大小: {status['global_db_size'] / 1024:.2f} KB")


def cmd_anomaly(args, config, db_manager):
    """异动监控命令"""
    from morning.anomaly_monitor import AnomalyMonitor

    monitor = AnomalyMonitor(config.anomaly_monitor.__dict__)
    result = monitor.run()

    print(f"📊 异动监控结果")
    print()
    print(f"总分: {result.total_score:.1f}/100")
    print(f"推送阈值: {monitor.push_threshold}")
    print(f"是否推送: {'是' if result.should_push else '否'}")
    print()

    for score in result.scores:
        print(f"【{score.dimension}】{score.score:.1f}/25")
        print(f"  {score.description}")
        print()


def cmd_track(args, config, db_manager):
    """晚间回溯命令"""
    from morning.stock_tracker import StockTracker

    tracker = StockTracker(db_manager, config.stock_tracker.__dict__)
    results = tracker.track_stocks(args.track_days)
    report = tracker.generate_report(results)

    print(report)


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

    # 新增功能示例
    python run_morning.py --anomaly         运行异动监控
    python run_morning.py --track           运行晚间回溯
    python run_morning.py --track --track-days 7  回溯7天
    python run_morning.py --watch add 600519 贵州茅台 --reason 业绩预增 --group 白酒
    python run_morning.py --watch list      查看关注列表
    python run_morning.py --trade buy 600519 1800 100 --reason 业绩预增
    python run_morning.py --trade log --days 7  查看7天操作日志
    python run_morning.py --db-status       查看数据库状态
    python run_morning.py --db-backup       手动备份数据库
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

    # 异动监控
    parser.add_argument("--anomaly", action="store_true", help="运行异动监控")

    # 晚间回溯
    parser.add_argument("--track", action="store_true", help="运行晚间回溯")
    parser.add_argument("--track-days", type=int, default=5, help="跟踪天数")

    # 特别关注
    parser.add_argument("--watch", nargs="+", help="特别关注操作 (add/remove/list/group)")

    # 操作日志
    parser.add_argument("--trade", nargs="+", help="操作日志 (buy/sell/watch/log/review/stats)")

    # 数据库管理
    parser.add_argument("--db-status", action="store_true", help="查看数据库状态")
    parser.add_argument("--db-export", action="store_true", help="导出数据")
    parser.add_argument("--db-backup", action="store_true", help="手动备份")
    parser.add_argument("--db-cleanup", action="store_true", help="清理旧数据")

    args = parser.parse_args()

    # 初始化
    setup_logging(args.verbose)
    load_config()
    config = get_config()

    print(f"🚀 新闻晨报系统 v{morning.__version__}\n")
    if _is_monday():
        print("📅 周一模式：将汇总周末消息面（加大抓取量 + 专属分析提示）\n")
    check_config()

    # 初始化数据库管理器
    from morning.db_manager import DBManager
    db_manager = DBManager(config.database.daily_path, config.database.global_path)

    # 路由命令
    if args.fetch:
        cmd_fetch(args.verbose)
    elif args.analyze:
        cmd_analyze(args.verbose)
    elif args.send:
        cmd_send(args.verbose)
    elif args.dry_run:
        cmd_dry_run(args.verbose)
    elif args.anomaly:
        cmd_anomaly(args, config, db_manager)
    elif args.track:
        cmd_track(args, config, db_manager)
    elif args.watch:
        cmd_watch(args, db_manager)
    elif args.trade:
        cmd_trade(args, db_manager)
    elif args.db_status:
        cmd_db_status(args, db_manager)
    elif args.db_backup:
        db_manager.backup()
        print("✅ 数据库备份完成")
    elif args.db_cleanup:
        db_manager.cleanup()
        print("✅ 旧数据清理完成")
    else:
        cmd_full(args.verbose)


if __name__ == "__main__":
    import morning  # noqa: 确保模块可导入
    main()
