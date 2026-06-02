"""
定时任务定义

依赖于 schedule 库：
    pip install schedule

用法：
    from scheduler.tasks import register_tasks
    register_tasks(config_dict)

    import schedule, time
    while True:
        schedule.run_pending()
        time.sleep(30)
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 项目根目录
BASE_DIR = Path(__file__).parent.parent.resolve()


# ============================================================
# 任务函数
# ============================================================

def morning_job():
    """晨报任务：抓取新闻 → AI 分析 → 风险预警 → 推送（微信+钉钉）"""
    import sys
    sys.path.insert(0, str(BASE_DIR))

    from morning.config import load_config, get_config
    from morning.news_fetcher import fetch_all_news
    from morning.ai_analyzer import analyze_news
    from morning.dingtalk_sender import build_markdown, send_dingtalk
    from morning.risk_integration import build_risk_section
    from risk.risk_engine import RiskWarningEngine as _RiskWarningEngine

    load_config()
    cfg = get_config()

    is_monday = datetime.now().weekday() == 0
    max_news = cfg.monday_max_news if is_monday else cfg.max_news_per_source

    logger.info("【定时任务】开始执行晨报 (max_per_source=%d)", max_news)
    news_list = fetch_all_news(max_per_source=max_news)

    if not news_list:
        logger.error("晨报任务失败：未抓取到新闻")
        return

    result = analyze_news(news_list, is_monday=is_monday)

    # ---- 生成 Markdown ----
    source_names = [s.name for s in cfg.rss_sources]
    markdown = build_markdown(result, source_names)

    # ---- 风险预警 ----
    risk_section = ""
    if cfg.risk.enabled:
        try:
            engine = _RiskWarningEngine(
                ad_warn=cfg.risk.ad_warn, ad_danger=cfg.risk.ad_danger,
                north_warn=cfg.risk.north_warn, north_danger=cfg.risk.north_danger,
                index_dev_warn=cfg.risk.index_dev_warn, index_dev_danger=cfg.risk.index_dev_danger,
            )
            risk_result = engine.assess()
            risk_section = build_risk_section(risk_result)
            engine.print_report(risk_result)
        except Exception as e:
            logger.warning("风险预警生成失败: %s", e)

    # ---- 推送（微信优先，钉钉回退）----
    wechat_enabled = hasattr(cfg, 'wechat') and cfg.wechat.enabled
    dingtalk_available = cfg.dingtalk.available if hasattr(cfg, 'dingtalk') else True

    # 微信推送晨报
    wechat_ok = False
    if wechat_enabled:
        try:
            from wechat.push_integration import push_morning_report
            wechat_ok = push_morning_report(markdown)
        except Exception as e:
            logger.warning("微信推送晨报失败: %s", e)

    # 钉钉推送晨报
    dingtalk_ok = False
    if dingtalk_available and not (wechat_ok and wechat_enabled):
        dingtalk_ok = send_dingtalk(markdown)
        if dingtalk_ok:
            logger.info("钉钉晨报推送成功")

    success = wechat_ok or dingtalk_ok

    # ---- 推送风险预警 ----
    if risk_section:
        if wechat_enabled:
            try:
                from wechat.push_integration import push_risk_warning
                push_risk_warning(risk_section)
            except Exception as e:
                logger.warning("微信推送风险预警失败: %s", e)
        if dingtalk_available:
            send_dingtalk(risk_section, title="【风险预警】市场风险评分")

    if success:
        logger.info("晨报任务执行成功")
    else:
        logger.warning("晨报任务执行完成，但推送失败")


def risk_job():
    """风险预警独立任务（微信+钉钉）"""
    import sys
    sys.path.insert(0, str(BASE_DIR))

    from morning.config import load_config, get_config
    from risk.risk_engine import RiskWarningEngine
    from morning.risk_integration import build_risk_section
    from morning.dingtalk_sender import send_dingtalk

    load_config()
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
    section = build_risk_section(result)

    if not section:
        logger.warning("风险预警任务：生成结果为空")
        return

    # 微信推送
    wechat_enabled = hasattr(cfg, 'wechat') and cfg.wechat.enabled
    if wechat_enabled:
        try:
            from wechat.push_integration import push_risk_warning
            push_risk_warning(section)
        except Exception as e:
            logger.warning("微信推送风险预警失败: %s", e)

    # 钉钉推送
    send_dingtalk(section, title="【风险预警】市场风险评分")
    engine.print_report(result)
    logger.info("风险预警任务执行成功")


def update_data_job():
    """数据更新任务"""
    import sys
    sys.path.insert(0, str(BASE_DIR))

    logger.info("【定时任务】开始更新数据...")

    try:
        from strategy.data_fetcher import fetch_zt_pool_range
        from datetime import timedelta

        end = datetime.now().strftime("%Y%m%d")
        start_dt = datetime.now() - timedelta(days=15)
        start = start_dt.strftime("%Y%m%d")

        df = fetch_zt_pool_range(start, end)
        if df is not None and not df.empty:
            logger.info("涨停板数据更新成功，共 %d 条", len(df))
        else:
            logger.warning("涨停板数据为空")
    except Exception as e:
        logger.warning("数据更新失败: %s", e)

    logger.info("数据更新任务执行完毕")


def evolution_job():
    """策略进化任务（微信+钉钉推送）"""
    import sys
    sys.path.insert(0, str(BASE_DIR))

    from morning.config import load_config, get_config
    from strategy.evolver import StrategyEvolver

    load_config()
    cfg = get_config()
    evo_cfg = cfg.evolution

    logger.info("【定时任务】开始策略进化 (种群=%d, 代数=%d)",
                evo_cfg.population_size, evo_cfg.generations)

    evolver = StrategyEvolver(config={
        "population_size": evo_cfg.population_size,
        "generations": evo_cfg.generations,
        "elite_ratio": evo_cfg.elite_ratio,
        "crossover_prob": evo_cfg.crossover_prob,
        "mutation_prob": evo_cfg.mutation_prob,
        "fitness_weights": evo_cfg.fitness_weights,
    })
    best_params = evolver.evolve(verbose=True)
    report = evolver.generate_report(best_params)

    # 保存报告
    report_path = BASE_DIR / "logs" / "evolution_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    logger.info("策略进化报告已保存至: %s", report_path)

    # 推送报告
    wechat_enabled = hasattr(cfg, 'wechat') and cfg.wechat.enabled
    dingtalk_available = cfg.dingtalk.available if hasattr(cfg, 'dingtalk') else True

    pushed = False
    if wechat_enabled:
        try:
            from wechat.push_integration import push_evolution_report
            pushed = push_evolution_report(report)
        except Exception as e:
            logger.warning("微信推送进化报告失败: %s", e)

    if dingtalk_available and not pushed:
        try:
            from morning.dingtalk_sender import send_dingtalk
            send_dingtalk(f"# 🧬 策略进化报告\n\n{report}", title="【策略进化】报告")
            pushed = True
        except Exception as e:
            logger.warning("钉钉推送进化报告失败: %s", e)

    if pushed:
        logger.info("策略进化报告已推送")
    else:
        logger.warning("策略进化报告推送失败")

    logger.info("策略进化任务完成")


# ============================================================
# 任务注册
# ============================================================

def register_tasks(config: dict):
    """
    根据配置注册定时任务

    Args:
        config: 从 config.yaml 加载的完整配置字典

    调度规则：
        - 晨报：每个交易日 8:30
        - 数据更新：每个交易日 15:30
        - 策略进化：每周五 16:00
    """
    try:
        import schedule
    except ImportError:
        logger.error("schedule 库未安装，请执行: pip install schedule")
        return

    morning_cfg = config.get("morning", {})
    risk_cfg = config.get("risk", {})
    data_cfg = config.get("data_update", {})
    evo_cfg = config.get("evolution", {})

    registered = []

    # 晨报
    if morning_cfg.get("enabled", True):
        morning_time = morning_cfg.get("schedule_time", "08:30")
        schedule.every().day.at(morning_time).do(morning_job)
        schedule.every().day.at(morning_time).do(
            lambda: logger.info("晨报定时任务已注册: 每日 %s", morning_time)
        )
        registered.append(f"晨报 @ {morning_time}")

    # 风险预警
    if risk_cfg.get("enabled", True):
        risk_time = risk_cfg.get("schedule_time", "08:30")
        # 如果与晨报同时，不重复注册
        if risk_time != morning_cfg.get("schedule_time", "08:30"):
            schedule.every().day.at(risk_time).do(risk_job)
            registered.append(f"风险预警 @ {risk_time}")

    # 数据更新
    if data_cfg.get("enabled", True):
        data_time = data_cfg.get("schedule_time", "15:30")
        schedule.every().day.at(data_time).do(update_data_job)
        registered.append(f"数据更新 @ {data_time}")

    # 策略进化（每周五）
    if evo_cfg.get("enabled", True):
        evo_time = evo_cfg.get("schedule_time", "16:00")
        evo_day = evo_cfg.get("schedule_day", "fri")
        day_attr = getattr(schedule.every(), evo_day, None)
        if day_attr:
            day_attr.at(evo_time).do(evolution_job)
            registered.append(f"策略进化 @ 每周{evo_day} {evo_time}")

    if registered:
        logger.info("定时任务注册完成: %s", ", ".join(registered))
    else:
        logger.warning("未注册任何定时任务")


def run_all_now():
    """
    立即执行所有已注册的定时任务一次（用于首次启动）
    """
    logger.info("立即执行所有任务...")
    morning_job()
    logger.info("所有任务执行完毕")
