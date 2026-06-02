"""
配置加载模块
优先级：环境变量 > .env 文件 > config.yaml 默认值
支持 DeepSeek API（兼容 OpenAI 接口格式）

配置来源（按优先级）：
  1. 项目根目录 config.yaml（主配置）
  2. morning/config.yaml（旧版位置，向后兼容）
"""
import os
import sys
import yaml
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 模块根目录（兼容 PyInstaller 打包）
if getattr(sys, 'frozen', False):
    _MODULE_DIR = Path(sys._MEIPASS) / "morning"
    PROJECT_DIR = Path(sys.executable).parent
else:
    _MODULE_DIR = Path(__file__).parent.resolve()
    PROJECT_DIR = _MODULE_DIR.parent  # 项目根目录


def _load_yaml() -> dict:
    """
    加载配置文件，优先级：
      1. 项目根目录 config.yaml（新统一配置）
      2. morning/config.yaml（旧版，向后兼容）
    """
    yaml_path = PROJECT_DIR / "config.yaml"
    if not yaml_path.exists():
        # 兼容旧版路径
        yaml_path = _MODULE_DIR / "config.yaml"
    if not yaml_path.exists():
        return {}
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_env() -> None:
    """加载项目根目录的 .env 文件"""
    env_paths = [
        PROJECT_DIR / ".env",          # 项目根目录
        _MODULE_DIR / ".env",          # 模块目录
    ]
    for p in env_paths:
        if p.exists():
            load_dotenv(p, override=False)


# ---------- 数据结构 ----------

class RSSSource:
    """RSS 源配置"""
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url

    def __repr__(self):
        return f"RSSSource({self.name}, {self.url})"


class AIConfig:
    """AI API 配置（兼容 DeepSeek / OpenAI 格式）"""
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        max_tokens: int = 4096,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens

    @property
    def available(self) -> bool:
        return bool(self.api_key)


class DingTalkConfig:
    """钉钉机器人配置"""
    def __init__(
        self,
        webhook_url: str = "",
        secret: str = "",
        title: str = "📰 财经新闻晨报",
    ):
        self.webhook_url = webhook_url
        self.secret = secret
        self.title = title

    @property
    def available(self) -> bool:
        return bool(self.webhook_url)


class RiskConfig:
    """风险预警配置"""
    def __init__(
        self,
        enabled: bool = True,
        schedule_time: str = "08:30",
        ad_warn: float = 30.0,
        ad_danger: float = 20.0,
        north_warn: float = -20.0,
        north_danger: float = -50.0,
        index_dev_warn: float = 5.0,
        index_dev_danger: float = 8.0,
        low_risk_max: int = 3,
        medium_risk_max: int = 6,
    ):
        self.enabled = enabled
        self.schedule_time = schedule_time
        self.ad_warn = ad_warn
        self.ad_danger = ad_danger
        self.north_warn = north_warn
        self.north_danger = north_danger
        self.index_dev_warn = index_dev_warn
        self.index_dev_danger = index_dev_danger
        self.low_risk_max = low_risk_max
        self.medium_risk_max = medium_risk_max


class BacktestConfig:
    """回测参数配置"""
    def __init__(
        self,
        initial_capital: float = 1_000_000,
        commission: float = 0.0003,
        slippage: float = 0.001,
        t_plus_1: bool = True,
    ):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.t_plus_1 = t_plus_1


class BoardStrategyConfig:
    """打板策略配置"""
    def __init__(
        self,
        min_score: int = 14,
        max_daily_buy: int = 3,
        single_pct: float = 0.10,
    ):
        self.min_score = min_score
        self.max_daily_buy = max_daily_buy
        self.single_pct = single_pct


class EvolutionConfig:
    """遗传算法进化配置"""
    def __init__(
        self,
        enabled: bool = True,
        schedule_time: str = "16:00",
        schedule_day: str = "fri",
        population_size: int = 30,
        generations: int = 20,
        elite_ratio: float = 0.2,
        crossover_prob: float = 0.7,
        mutation_prob: float = 0.1,
        fitness_weights: Optional[dict] = None,
    ):
        self.enabled = enabled
        self.schedule_time = schedule_time
        self.schedule_day = schedule_day
        self.population_size = population_size
        self.generations = generations
        self.elite_ratio = elite_ratio
        self.crossover_prob = crossover_prob
        self.mutation_prob = mutation_prob
        self.fitness_weights = fitness_weights or {
            "annual_return": 0.5,
            "sharpe_ratio": 0.3,
            "max_drawdown": -0.2,
        }


class DataUpdateConfig:
    """数据更新配置"""
    def __init__(
        self,
        enabled: bool = True,
        schedule_time: str = "15:30",
        cache_hours: int = 24,
    ):
        self.enabled = enabled
        self.schedule_time = schedule_time
        self.cache_hours = cache_hours


class LoggingConfig:
    """日志配置"""
    def __init__(
        self,
        level: str = "INFO",
        file: str = "logs/system.log",
        max_bytes: int = 10485760,
        backup_count: int = 7,
    ):
        self.level = level
        self.file = file
        self.max_bytes = max_bytes
        self.backup_count = backup_count


class WeChatConfig:
    """微信互联配置"""
    def __init__(
        self,
        enabled: bool = False,
        auto_login: bool = False,
        poll_interval: float = 3.0,
        notify_on_startup: bool = True,
        dingtalk_fallback: bool = True,
    ):
        self.enabled = enabled
        self.auto_login = auto_login
        self.poll_interval = poll_interval
        self.notify_on_startup = notify_on_startup
        self.dingtalk_fallback = dingtalk_fallback

    @property
    def available(self) -> bool:
        """检查微信是否可用（需要已登录凭证）"""
        from wechat.auth import WeChatAuth
        return WeChatAuth().check_login()


class MorningConfig:
    """系统总配置"""
    def __init__(self):
        # 晨报模块
        self.enabled: bool = True
        self.schedule_time: str = "08:30"
        self.rss_sources: list[RSSSource] = []
        self.max_news_per_source: int = 20
        self.monday_max_news: int = 50
        self.ai = AIConfig()
        self.dingtalk = DingTalkConfig()

        # 风险预警
        self.risk = RiskConfig()

        # 回测参数
        self.backtest = BacktestConfig()

        # 打板策略
        self.board_strategy = BoardStrategyConfig()

        # 遗传算法进化
        self.evolution = EvolutionConfig()

        # 数据更新
        self.data_update = DataUpdateConfig()

        # 日志
        self.logging = LoggingConfig()

        # 微信互联
        self.wechat = WeChatConfig()


# ---------- 内部解析函数 ----------


def _parse_rss_sources(raw_sources: list) -> list[RSSSource]:
    """解析 RSS 源列表"""
    sources = []
    for s in raw_sources:
        sources.append(RSSSource(
            name=s.get("name", "未知源"),
            url=s.get("url", ""),
        ))
    return sources


def _parse_ai_config(ai_yaml: dict) -> AIConfig:
    """解析 AI 配置（环境变量优先）"""
    return AIConfig(
        api_key=(
            os.environ.get("AI_API_KEY")
            or os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("CLAUDE_API_KEY")
            or ai_yaml.get("api_key", "")
        ),
        base_url=(
            os.environ.get("AI_BASE_URL")
            or os.environ.get("DEEPSEEK_BASE_URL")
            or ai_yaml.get("base_url", "https://api.deepseek.com/v1")
        ),
        model=(
            os.environ.get("AI_MODEL")
            or os.environ.get("DEEPSEEK_MODEL")
            or ai_yaml.get("model", "deepseek-chat")
        ),
        max_tokens=int(
            os.environ.get("AI_MAX_TOKENS")
            or ai_yaml.get("max_tokens", 4096)
        ),
    )


def _parse_dingtalk_config(dingtalk_yaml: dict) -> DingTalkConfig:
    """解析钉钉配置（环境变量优先）"""
    return DingTalkConfig(
        webhook_url=(
            os.environ.get("DINGTALK_WEBHOOK_URL")
            or dingtalk_yaml.get("webhook_url", "")
        ),
        secret=(
            os.environ.get("DINGTALK_SECRET")
            or dingtalk_yaml.get("secret", "")
        ),
        title=(
            dingtalk_yaml.get("title", "📰 财经新闻晨报")
        ),
    )


def _parse_risk_config(raw: dict) -> RiskConfig:
    """解析风险预警配置"""
    return RiskConfig(
        enabled=raw.get("enabled", True),
        schedule_time=raw.get("schedule_time", "08:30"),
        ad_warn=float(raw.get("ad_warn", 30.0)),
        ad_danger=float(raw.get("ad_danger", 20.0)),
        north_warn=float(raw.get("north_warn", -20.0)),
        north_danger=float(raw.get("north_danger", -50.0)),
        index_dev_warn=float(raw.get("index_dev_warn", 5.0)),
        index_dev_danger=float(raw.get("index_dev_danger", 8.0)),
        low_risk_max=int(raw.get("low_risk_max", 3)),
        medium_risk_max=int(raw.get("medium_risk_max", 6)),
    )


def _parse_backtest_config(raw: dict) -> BacktestConfig:
    """解析回测参数配置"""
    return BacktestConfig(
        initial_capital=float(raw.get("initial_capital", 1_000_000)),
        commission=float(raw.get("commission", 0.0003)),
        slippage=float(raw.get("slippage", 0.001)),
        t_plus_1=raw.get("t_plus_1", True),
    )


def _parse_board_strategy_config(raw: dict) -> BoardStrategyConfig:
    """解析打板策略配置"""
    return BoardStrategyConfig(
        min_score=int(raw.get("min_score", 14)),
        max_daily_buy=int(raw.get("max_daily_buy", 3)),
        single_pct=float(raw.get("single_pct", 0.10)),
    )


def _parse_evolution_config(raw: dict) -> EvolutionConfig:
    """解析遗传算法进化配置"""
    return EvolutionConfig(
        enabled=raw.get("enabled", True),
        schedule_time=raw.get("schedule_time", "16:00"),
        schedule_day=raw.get("schedule_day", "fri"),
        population_size=int(raw.get("population_size", 30)),
        generations=int(raw.get("generations", 20)),
        elite_ratio=float(raw.get("elite_ratio", 0.2)),
        crossover_prob=float(raw.get("crossover_prob", 0.7)),
        mutation_prob=float(raw.get("mutation_prob", 0.1)),
        fitness_weights=raw.get("fitness_weights", None),
    )


def _parse_data_update_config(raw: dict) -> DataUpdateConfig:
    """解析数据更新配置"""
    return DataUpdateConfig(
        enabled=raw.get("enabled", True),
        schedule_time=raw.get("schedule_time", "15:30"),
        cache_hours=int(raw.get("cache_hours", 24)),
    )


def _parse_logging_config(raw: dict) -> LoggingConfig:
    """解析日志配置"""
    return LoggingConfig(
        level=raw.get("level", "INFO"),
        file=raw.get("file", "logs/system.log"),
        max_bytes=int(raw.get("max_bytes", 10485760)),
        backup_count=int(raw.get("backup_count", 7)),
    )


# ---------- 全局单例 ----------

_config: Optional[MorningConfig] = None


def load_config() -> MorningConfig:
    """
    加载所有配置，返回 MorningConfig 对象。
    优先级：环境变量 > .env > config.yaml

    支持两种 YAML 结构：
      - 新版（根 config.yaml）：所有晨报配置放在 morning: 键下
      - 旧版（morning/config.yaml）：配置在顶层（rss_sources, ai, dingtalk 等）
    """
    global _config
    if _config is not None:
        return _config

    _load_env()
    yaml_cfg = _load_yaml()

    cfg = MorningConfig()

    # ---- 判断配置格式：新版（morning 键） vs 旧版（顶层键） ----
    morning_yaml = yaml_cfg.get("morning", yaml_cfg)

    # ---- RSS 源 ----
    raw_sources = morning_yaml.get("rss_sources", [])
    if not raw_sources:
        # 默认 RSS 源
        raw_sources = [
            {"name": "财联社",   "url": "https://www.cls.cn/telegraph"},
            {"name": "华尔街见闻", "url": "https://wallstreetcn.com/rss/global"},
            {"name": "东方财富",  "url": "https://finance.eastmoney.com/a/czqyw.html"},
        ]
    cfg.rss_sources = _parse_rss_sources(raw_sources)

    # ---- 晨报通用设置 ----
    cfg.enabled = morning_yaml.get("enabled", True)
    cfg.schedule_time = morning_yaml.get("schedule_time", "08:30")
    cfg.max_news_per_source = int(morning_yaml.get("max_news_per_source", 20))
    cfg.monday_max_news = int(morning_yaml.get("monday_max_news", 50))

    # ---- AI 配置 ----
    ai_yaml = morning_yaml.get("ai", yaml_cfg.get("claude", {}))
    cfg.ai = _parse_ai_config(ai_yaml)

    # ---- 钉钉配置 ----
    dingtalk_yaml = morning_yaml.get("dingtalk", {})
    cfg.dingtalk = _parse_dingtalk_config(dingtalk_yaml)

    # ---- 风险预警 ----
    risk_yaml = yaml_cfg.get("risk", {})
    cfg.risk = _parse_risk_config(risk_yaml)

    # ---- 回测参数 ----
    backtest_yaml = yaml_cfg.get("backtest", {})
    cfg.backtest = _parse_backtest_config(backtest_yaml)

    # ---- 打板策略 ----
    board_yaml = yaml_cfg.get("board_strategy", {})
    cfg.board_strategy = _parse_board_strategy_config(board_yaml)

    # ---- 遗传算法进化 ----
    evolution_yaml = yaml_cfg.get("evolution", {})
    cfg.evolution = _parse_evolution_config(evolution_yaml)

    # ---- 数据更新 ----
    data_update_yaml = yaml_cfg.get("data_update", {})
    cfg.data_update = _parse_data_update_config(data_update_yaml)

    # ---- 日志 ----
    logging_yaml = yaml_cfg.get("logging", {})
    cfg.logging = _parse_logging_config(logging_yaml)

    # ---- 微信互联 ----
    wechat_yaml = yaml_cfg.get("wechat", {})
    cfg.wechat = WeChatConfig(
        enabled=wechat_yaml.get("enabled", False),
        auto_login=wechat_yaml.get("auto_login", False),
        poll_interval=float(wechat_yaml.get("poll_interval", 3.0)),
        notify_on_startup=wechat_yaml.get("notify_on_startup", True),
        dingtalk_fallback=wechat_yaml.get("dingtalk_fallback", True),
    )

    _config = cfg
    return cfg


def get_config() -> MorningConfig:
    """获取已加载的配置（未加载则自动加载）"""
    if _config is None:
        return load_config()
    return _config
