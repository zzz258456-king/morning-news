"""
全局配置文件
"""
import os
import sys
from pathlib import Path

# 项目根目录（兼容 PyInstaller 打包）
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent.resolve()
else:
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

# ========== 回测系统配置 ==========

# 回测基础参数
BACKTEST_INITIAL_CAPITAL = 1_000_000  # 初始资金 100万
BACKTEST_COMMISSION = 0.0003          # 佣金 0.03%
BACKTEST_SLIPPAGE = 0.001            # 滑点 0.1%

# 打板策略参数
BOARD_BUY_TIMEOUT = "10:00"          # 早盘涨停截止时间
BOARD_MIN_SEAL_RATIO = 0.05          # 最小封单额/成交额比（实际市场通常0.05-0.5）
BOARD_MIN_VOLUME_RATIO = 0.1         # 最小封单额(亿)，低于此不买
BOARD_TURNOVER_MIN = 3.0             # 最小换手率 %
BOARD_TURNOVER_MAX = 25.0            # 最大换手率 %
BOARD_MARKET_CAP_MIN = 20            # 最小流通市值 (亿)
BOARD_MARKET_CAP_MAX = 300           # 最大流通市值 (亿)

# 卖出参数（T+1）
SELL_PROFIT_TARGET = 0.05            # 止盈 +5%
SELL_STOP_LOSS = -0.03               # 止损 -3%
SELL_TRAILING_STOP = 0.02            # 回落止盈 2%

# 回测时间
BACKTEST_START_DATE = "20260301"     # 回测开始日期
BACKTEST_END_DATE = "20260529"       # 回测结束日期

# ========== 风险预警配置 ==========

# 涨跌家数阈值
RISK_AD_WARN = 30.0          # 涨跌比% 预警线
RISK_AD_DANGER = 20.0        # 涨跌比% 危险线

# 北向资金阈值
RISK_NORTH_WARN = -20.0      # 北向净流入(亿) 预警线
RISK_NORTH_DANGER = -50.0    # 北向净流入(亿) 危险线

# 指数偏离阈值
RISK_INDEX_DEV_WARN = 5.0    # 指数偏离% 预警
RISK_INDEX_DEV_DANGER = 8.0  # 指数偏离% 危险

# 风险评分对应的仓位限制
RISK_LOW_POSITION = 1.0      # 低风险 → 满仓
RISK_MED_POSITION = 0.7      # 中风险 → 7成仓
RISK_HIGH_POSITION = 0.3     # 高风险 → 3成仓
