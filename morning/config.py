"""
配置加载模块
优先级：环境变量 > .env 文件 > config.yaml 默认值
支持 DeepSeek API（兼容 OpenAI 接口格式）
"""
import os
import yaml
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 模块根目录
_MODULE_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = _MODULE_DIR.parent  # 项目根目录


def _load_yaml() -> dict:
    """加载 morning/config.yaml 配置"""
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


class MorningConfig:
    """新闻晨报系统总配置"""
    def __init__(self):
        self.rss_sources: list[RSSSource] = []
        self.ai = AIConfig()
        self.dingtalk = DingTalkConfig()


# ---------- 全局单例 ----------

_config: Optional[MorningConfig] = None


def load_config() -> MorningConfig:
    """
    加载所有配置，返回 MorningConfig 对象。
    优先级：环境变量 > .env > config.yaml
    """
    global _config
    if _config is not None:
        return _config

    _load_env()
    yaml_cfg = _load_yaml()

    cfg = MorningConfig()

    # ---- RSS 源 ----
    raw_sources = yaml_cfg.get("rss_sources", [])
    if not raw_sources:
        # 默认 RSS 源
        raw_sources = [
            {"name": "财联社",   "url": "https://www.cls.cn/telegraph"},
            {"name": "华尔街见闻", "url": "https://wallstreetcn.com/rss/global"},
            {"name": "东方财富",  "url": "https://finance.eastmoney.com/a/czqyw.html"},
        ]
    for s in raw_sources:
        cfg.rss_sources.append(RSSSource(
            name=s.get("name", "未知源"),
            url=s.get("url", ""),
        ))

    # ---- AI 配置（DeepSeek / OpenAI） ----
    ai_yaml = yaml_cfg.get("ai", yaml_cfg.get("claude", {}))
    cfg.ai = AIConfig(
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

    # ---- 钉钉 ----
    dingtalk_yaml = yaml_cfg.get("dingtalk", {})
    cfg.dingtalk = DingTalkConfig(
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

    _config = cfg
    return cfg


def get_config() -> MorningConfig:
    """获取已加载的配置（未加载则自动加载）"""
    if _config is None:
        return load_config()
    return _config
