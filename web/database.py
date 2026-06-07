"""
SQLite 数据库初始化与管理
创建 trades, daily_logs, fund_flow_snapshots 三张表
"""
import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 数据库文件路径
DB_PATH = Path(__file__).parent.parent / "data" / "web_platform.db"

# SQL 建表语句
_CREATE_TRADES_TABLE = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL CHECK(action IN ('buy', 'sell')),
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    reason TEXT DEFAULT '',
    reflection TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""

_CREATE_DAILY_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS daily_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    log_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'info',
    summary TEXT DEFAULT '',
    detail TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""

_CREATE_FUND_FLOW_TABLE = """
CREATE TABLE IF NOT EXISTS fund_flow_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    sector_name TEXT NOT NULL,
    sector_type TEXT NOT NULL DEFAULT 'industry',
    main_net_inflow REAL DEFAULT 0,
    retail_net_inflow REAL DEFAULT 0,
    super_large_inflow REAL DEFAULT 0,
    large_inflow REAL DEFAULT 0,
    medium_inflow REAL DEFAULT 0,
    small_inflow REAL DEFAULT 0,
    rank INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""

# 索引
_CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date);
CREATE INDEX IF NOT EXISTS idx_trades_stock_code ON trades(stock_code);
CREATE INDEX IF NOT EXISTS idx_daily_logs_date ON daily_logs(date);
CREATE INDEX IF NOT EXISTS idx_daily_logs_type ON daily_logs(log_type);
CREATE INDEX IF NOT EXISTS idx_fund_flow_date ON fund_flow_snapshots(date);
CREATE INDEX IF NOT EXISTS idx_fund_flow_sector ON fund_flow_snapshots(sector_name);
"""


def get_db_path() -> Path:
    """获取数据库文件路径"""
    return DB_PATH


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    获取数据库连接

    Args:
        db_path: 数据库路径，None 则使用默认路径

    Returns:
        sqlite3.Connection 对象
    """
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """
    初始化数据库，创建所有表和索引

    Args:
        db_path: 数据库路径，None 则使用默认路径
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(_CREATE_TRADES_TABLE)
        cursor.execute(_CREATE_DAILY_LOGS_TABLE)
        cursor.execute(_CREATE_FUND_FLOW_TABLE)
        cursor.executescript(_CREATE_INDEXES)
        conn.commit()
        logger.info("数据库初始化完成: %s", db_path or DB_PATH)
    except Exception as e:
        logger.error("数据库初始化失败: %s", e)
        raise
    finally:
        conn.close()


def reset_db(db_path: Optional[Path] = None) -> None:
    """
    重置数据库（删除所有表后重建）

    Args:
        db_path: 数据库路径，None 则使用默认路径
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS trades")
        cursor.execute("DROP TABLE IF EXISTS daily_logs")
        cursor.execute("DROP TABLE IF EXISTS fund_flow_snapshots")
        conn.commit()
        logger.info("数据库已重置")
    finally:
        conn.close()

    init_db(db_path)
