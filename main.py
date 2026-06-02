#!/usr/bin/env python3
"""
StockStrategySystem — 量化策略研究与预警系统
统一入口，支持命令行参数运行各模块

用法:
    python main.py                        # 显示帮助
    python main.py --morning              # 运行晨报 + 风险预警
    python main.py --risk                 # 仅运行风险预警
    python main.py --evolution            # 运行策略进化
    python main.py --update_data          # 更新历史数据
    python main.py --all                  # 常驻进程模式，按定时任务运行
    python main.py --dry-run              # 预览晨报（抓取+分析，不推送）
"""
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# 确保项目根目录在 sys.path 中
BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from morning.config import load_config, get_config
from risk.risk_engine import RiskWarningEngine

logger = logging.getLogger(__name__)


# ============================================================
# 日志初始化
# ============================================================

def setup_logging(config: dict = None):
    """配置日志"""
    level = logging.INFO
    log_file = "logs/system.log"

    if config:
        lvl_name = config.get("logging", {}).get("level", "INFO")
        level = getattr(logging, lvl_name.upper(), logging.INFO)
        log_file = config.get("logging", {}).get("file", "logs/system.log")

    log_dir = Path(log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )

    # 关闭第三方库的详细日志
    for name in ["urllib3", "feedparser", "anthropic"]:
        logging.getLogger(name).setLevel(logging.WARNING)


# ============================================================
# 子命令实现
# ============================================================

def cmd_morning(dry_run: bool = False):
    """
    抓取新闻 → AI 分析 → 风险预警 → 钉钉推送

    Args:
        dry_run: True 则只打印结果到控制台，不推送
    """
    from morning.news_fetcher import fetch_all_news
    from morning.ai_analyzer import analyze_news
    from morning.risk_integration import build_risk_section

    cfg = get_config()
    logging.info("=" * 40)
    logging.info("开始执行晨报流程")
    logging.info("=" * 40)

    # 1. 判断周一模式
    is_monday = datetime.now().weekday() == 0
    max_news = cfg.monday_max_news if is_monday else cfg.max_news_per_source
    if is_monday:
        logging.info("周一模式：加大抓取量覆盖周末消息")

    # 2. 抓取新闻
    news_list = fetch_all_news(max_per_source=max_news)
    if not news_list:
        logging.error("未抓取到新闻，流程终止")
        return False

    logging.info("共抓取 %d 条新闻", len(news_list))

    # 3. AI 分析
    result = analyze_news(news_list, is_monday=is_monday)

    # 5. 构建 Markdown
    from morning.dingtalk_sender import build_markdown
    source_names = [s.name for s in cfg.rss_sources]
    markdown = build_markdown(result, source_names)

    # 6. 基本面评分
    try:
        from morning.fundamental_analyzer import score_recommended_stocks
        stocks = []
        for pick in result.top_picks:
            stocks.extend(pick.stocks)
        if stocks:
            fund_section = score_recommended_stocks(stocks)
            if fund_section:
                markdown += "\n" + fund_section
    except Exception as e:
        logger.warning("基本面评分生成失败: %s", e)

    # 7. 风险预警段
    risk_section = ""
    if cfg.risk.enabled:
        try:
            risk_engine = RiskWarningEngine(
                ad_warn=cfg.risk.ad_warn,
                ad_danger=cfg.risk.ad_danger,
                north_warn=cfg.risk.north_warn,
                north_danger=cfg.risk.north_danger,
                index_dev_warn=cfg.risk.index_dev_warn,
                index_dev_danger=cfg.risk.index_dev_danger,
            )
            risk_result = risk_engine.assess()
            risk_section = build_risk_section(risk_result)
            risk_engine.print_report(risk_result)
        except Exception as e:
            logger.warning("风险预警生成失败: %s", e)

    # 8. 推送
    if dry_run:
        if risk_section:
            markdown += "\n" + risk_section
        print("\n" + "=" * 60)
        print("干运行模式 — 以下为推送内容：")
        print("=" * 60)
        print(markdown)
        print("\n" + "=" * 60)
        logging.info("干运行完成（共 %d 字符）", len(markdown))
        return True

    # 微信推送（完整晨报 + 风险预警）
    wechat_enabled = hasattr(cfg, 'wechat') and cfg.wechat.enabled
    wechat_ok = False

    full_md = markdown
    if risk_section:
        full_md += "\n" + risk_section

    if wechat_enabled:
        try:
            from wechat.push_integration import push_morning_report
            wechat_ok = push_morning_report(full_md)
        except Exception as e:
            logger.warning("微信推送晨报失败: %s", e)

    success = wechat_ok
    if success:
        logging.info("晨报已通过微信推送成功")
    else:
        logging.warning("晨报推送失败（微信不可用）")

    logging.info("晨报流程执行完毕")
    return success


def cmd_risk():
    """仅风险预警分析"""
    cfg = get_config()
    engine = RiskWarningEngine(
        ad_warn=cfg.risk.ad_warn,
        ad_danger=cfg.risk.ad_danger,
        north_warn=cfg.risk.north_warn,
        north_danger=cfg.risk.north_danger,
        index_dev_warn=cfg.risk.index_dev_warn,
        index_dev_danger=cfg.risk.index_dev_danger,
    )
    result = engine.assess()
    engine.print_report(result)

    # 显示日历效应
    from risk.calendar_effects import compute_calendar_effects
    effects = compute_calendar_effects()
    if effects:
        print("\n  日历效应（历史统计）:")
        for day, info in effects.items():
            print(f"    {day}: {info['样本数']}天  "
                  f"下跌概率{info['下跌概率%']}%  "
                  f"平均{info['平均涨跌幅%']:+.2f}%")
    print()
    return True


def cmd_evolution():
    """运行遗传算法进化"""
    cfg = get_config()
    evo_cfg = cfg.evolution

    from strategy.evolver import StrategyEvolver
    evolver = StrategyEvolver(config={
        "population_size": evo_cfg.population_size,
        "generations": evo_cfg.generations,
        "elite_ratio": evo_cfg.elite_ratio,
        "crossover_prob": evo_cfg.crossover_prob,
        "mutation_prob": evo_cfg.mutation_prob,
        "fitness_weights": evo_cfg.fitness_weights,
    })

    logging.info("开始遗传算法进化（种群 %d，代数 %d）...",
                 evo_cfg.population_size, evo_cfg.generations)

    best_params = evolver.evolve(verbose=True)

    # 输出报告
    report = evolver.generate_report(best_params)
    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    # 保存结果
    report_path = Path(BASE_DIR) / "logs" / "evolution_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    logging.info("进化报告已保存至: %s", report_path)

    return True


def cmd_update_data():
    """更新历史数据"""
    logging.info("开始更新历史数据...")

    try:
        from strategy.data_fetcher import fetch_zt_pool_range, get_trade_dates
        from datetime import timedelta

        # 获取最近 10 个交易日的涨停池数据
        end = datetime.now().strftime("%Y%m%d")
        # 向前推 15 个自然日覆盖交易日
        start_dt = datetime.now() - timedelta(days=15)
        start = start_dt.strftime("%Y%m%d")

        logging.info("更新 %s ~ %s 的涨停板数据...", start, end)
        df = fetch_zt_pool_range(start, end)

        if df is not None and not df.empty:
            logging.info("涨停板数据更新成功，共 %d 条记录", len(df))
        else:
            logging.warning("涨停板数据为空")
    except Exception as e:
        logging.warning("涨停板数据更新失败: %s", e)

    # 更新股票日线数据
    try:
        from strategy.data_fetcher import fetch_daily_data
        # 获取最近 60 个交易日的沪深300数据
        logging.info("更新主要指数数据...")
    except Exception as e:
        logging.warning("日线数据更新失败: %s", e)

    logging.info("数据更新完成")
    return True


def cmd_all():
    """常驻进程模式，按定时任务运行"""
    logging.info("启动常驻进程模式...")

    # 尝试发送微信启动通知
    try:
        cfg = get_config()
        if hasattr(cfg, 'wechat') and cfg.wechat.enabled and cfg.wechat.notify_on_startup:
            from wechat.bot import WeChatBot
            bot = WeChatBot()
            if bot.login(interactive=False):
                bot.send_notification(
                    "StockStrategySystem 已启动",
                    f"常驻进程模式 · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    msg_type="info",
                )
    except Exception as e:
        logger.debug("微信启动通知发送失败: %s", e)

    try:
        from scheduler.tasks import register_tasks, run_all_now
        cfg_dict = _load_config_as_dict()
        register_tasks(cfg_dict)

        # 立即执行一次所有任务
        logging.info("首次启动，立即执行所有任务...")
        run_all_now()

        # 进入定时循环
        import schedule
        import time

        logging.info("进入定时调度循环...")
        while True:
            schedule.run_pending()
            time.sleep(30)
    except ImportError as e:
        logging.error("调度模块未就绪: %s", e)
        logging.info("请先安装依赖: pip install schedule")
        return False
    except KeyboardInterrupt:
        logging.info("收到退出信号，进程终止")
        return True


# ============================================================
# 微信互联命令
# ============================================================

def cmd_wechat_login():
    """微信扫码登录"""
    from wechat.auth import WeChatAuth
    print("\n" + "=" * 50)
    print("🔐  微信 ClawBot 扫码登录")
    print("=" * 50)
    auth = WeChatAuth()
    creds = auth.login_interactive()
    if creds:
        print(f"\n✅ 微信登录成功！")
        print(f"   账号ID: {creds.accountId}")
        print(f"   凭证文件: {auth.cred_file}")

        print(f"\n💡 下一步：请给机器人发一条微信消息激活连接")
        print(f"   然后运行 python main.py --wechat 进入消息监听模式")
    else:
        print("\n❌ 微信登录失败")
    return bool(creds)


def cmd_wechat():
    """微信消息轮询模式"""
    from wechat.bot import WeChatBot
    from morning.config import get_config

    cfg = get_config()

    bot = WeChatBot()
    if not bot.login(interactive=True):
        print("微信登录失败，退出")
        return False

    interval = cfg.wechat.poll_interval if hasattr(cfg, 'wechat') else 3.0

    print(f"\n{'=' * 50}")
    print("📱  微信消息监听模式")
    print(f"    轮询间隔: {interval}秒")
    print("   按 Ctrl+C 停止")
    print(f"{'=' * 50}\n")

    # 注册默认消息处理器
    bot.add_handler(lambda msg: print(
        f"[微信] {msg.from_name or msg.from_user_id}: {msg.content[:100]}"
    ))

    try:
        bot.start_polling()
    except KeyboardInterrupt:
        print("\n已停止微信消息监听")
    return True


# ============================================================
# 辅助
# ============================================================

def _load_config_as_dict() -> dict:
    """加载 YAML 配置为纯字典（供 scheduler 使用）"""
    import yaml
    yaml_path = BASE_DIR / "config.yaml"
    if yaml_path.exists():
        with open(yaml_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="StockStrategySystem — 量化策略研究与预警系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python main.py --morning               完整晨报+风险+推送
    python main.py --dry-run               预览但不推送
    python main.py --risk                  仅风险预警
    python main.py --evolution             策略参数进化
    python main.py --update_data           更新数据
    python main.py --wechat-login          微信扫码登录
    python main.py --wechat                微信消息监听
    python main.py --all                   常驻进程模式
        """,
    )
    parser.add_argument("--morning", action="store_true", help="运行晨报 + 风险预警 + 钉钉推送")
    parser.add_argument("--dry-run", action="store_true", help="晨报干运行（抓取+分析，不推送）")
    parser.add_argument("--risk", action="store_true", help="仅运行风险预警分析")
    parser.add_argument("--evolution", action="store_true", help="运行遗传算法策略进化")
    parser.add_argument("--update_data", action="store_true", help="更新历史数据")
    parser.add_argument("--wechat-login", action="store_true", dest="wechat_login", help="微信扫码登录")
    parser.add_argument("--wechat", action="store_true", help="微信消息监听模式")
    parser.add_argument("--all", action="store_true", help="常驻进程模式，按定时任务运行")

    args = parser.parse_args()

    # 加载配置
    try:
        config = load_config()
        setup_logging(_load_config_as_dict())
    except Exception:
        pass  # 配置加载失败不影响帮助显示

    # 路由
    if args.morning:
        cmd_morning(dry_run=False)
    elif args.dry_run:
        cmd_morning(dry_run=True)
    elif args.risk:
        cmd_risk()
    elif args.evolution:
        cmd_evolution()
    elif args.update_data:
        cmd_update_data()
    elif args.wechat_login:
        cmd_wechat_login()
    elif args.wechat:
        cmd_wechat()
    elif args.all:
        cmd_all()
    else:
        # 无参数 → 交互菜单模式（双击友好）
        _interactive_menu()


def _interactive_menu():
    """交互式菜单：双击运行时不闪退"""
    import sys
    is_frozen = getattr(sys, 'frozen', False)

    banner = """
╔══════════════════════════════════════════╗
║     StockStrategySystem v2              ║
║     量化策略研究与预警系统               ║
╚══════════════════════════════════════════╝

请选择操作模式:

  [1] 📰 晨报预览 (抓取+分析，不推送)
  [2] 🚀 完整晨报 (抓取+分析+风险+钉钉推送)
  [3] 🛡️  风险预警
  [4] 🧬 策略参数进化
  [5] 🔄 更新数据
  [6] 🔐 微信扫码登录
  [7] 📱 微信消息监听
  [8] ⏰ 常驻进程模式
  [9] ❓ 查看命令行帮助
  [0] 🚪 退出
"""
    print(banner)

    while True:
        try:
            choice = input("请输入数字 (0-9): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n退出")
            break

        if choice == "1":
            cmd_morning(dry_run=True)
        elif choice == "2":
            cmd_morning(dry_run=False)
        elif choice == "3":
            cmd_risk()
        elif choice == "4":
            cmd_evolution()
        elif choice == "5":
            cmd_update_data()
        elif choice == "6":
            cmd_wechat_login()
        elif choice == "7":
            cmd_wechat()
        elif choice == "8":
            cmd_all()
            break
        elif choice == "9":
            print(__doc__)
        elif choice == "0":
            print("退出")
            break
        else:
            print("无效输入，请重新选择")

        if is_frozen:
            print("\n" + "-" * 40)
            input("按回车返回主菜单...")
        print()

    if is_frozen:
        input("\n按回车退出...")


if __name__ == "__main__":
    main()
