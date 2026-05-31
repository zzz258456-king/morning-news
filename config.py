"""
全局配置文件
"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.resolve()

# 数据目录
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Web 服务器配置
WEB_HOST = "127.0.0.1"
WEB_PORT = 8000
WEB_DEBUG = True
WEB_TITLE = "全能数据平台"
WEB_DESCRIPTION = "集爬虫、数据分析、ML、Web服务与桌面应用为一体的综合性数据平台"
WEB_VERSION = "1.0.0"

# 爬虫配置
CRAWLER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
CRAWLER_TIMEOUT = 30  # 秒
CRAWLER_DELAY = 1     # 请求间隔（秒）

# 数据库配置（如使用 SQLite）
DATABASE_URL = f"sqlite:///{DATA_DIR / 'app.db'}"

# 确保数据目录存在
for d in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 默认分析配置
DEFAULT_CHART_DPI = 100
DEFAULT_CHART_FIGSIZE = (10, 6)

# 日志配置
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
