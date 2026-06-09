# morning/db_manager.py
"""
数据库管理模块
采用每日独立数据库 + 全局数据库的架构
"""
import sqlite3
import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    """推荐记录"""
    stock_code: str
    stock_name: str
    recommend_price: float
    reason: str
    source: str = "晨报"
    ai_analysis: str = ""
    created_at: datetime = None


@dataclass
class WatchlistItem:
    """特别关注项"""
    stock_code: str
    stock_name: str
    add_date: date
    add_price: float
    reason: str
    group_name: str = "默认"
    tracking_days: int = -1
    is_active: bool = True


@dataclass
class TradeRecord:
    """操作记录"""
    trade_date: datetime
    trade_type: str  # BUY/SELL/WATCH/UNWATCH/NOTE
    stock_code: str
    stock_name: str = ""
    price: float = 0.0
    quantity: int = 0
    reason: str = ""
    emotion: str = ""
    tags: list = None
    profit_loss: float = 0.0
    notes: str = ""


class DBManager:
    """数据库管理器"""

    def __init__(self, daily_path: str = "data/daily", global_path: str = "data/global.db"):
        self.daily_path = Path(daily_path)
        self.global_path = Path(global_path)
        self.daily_path.mkdir(parents=True, exist_ok=True)
        self.global_path.parent.mkdir(parents=True, exist_ok=True)

        # 初始化全局数据库
        self._init_global_db()

    def _init_global_db(self):
        """初始化全局数据库"""
        with sqlite3.connect(self.global_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL UNIQUE,
                    stock_name TEXT NOT NULL,
                    add_date DATE NOT NULL,
                    add_price REAL,
                    reason TEXT,
                    group_name TEXT DEFAULT '默认',
                    tracking_days INTEGER DEFAULT -1,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date TIMESTAMP NOT NULL,
                    trade_type TEXT NOT NULL,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    price REAL,
                    quantity INTEGER,
                    reason TEXT,
                    emotion TEXT,
                    tags TEXT,
                    profit_loss REAL,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS db_version (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            """)

            conn.commit()

    def _get_daily_db_path(self, target_date: date) -> Path:
        """获取每日数据库路径"""
        return self.daily_path / f"{target_date.strftime('%Y-%m-%d')}.db"

    def get_daily_db(self, target_date: date) -> sqlite3.Connection:
        """获取指定日期的数据库连接"""
        db_path = self._get_daily_db_path(target_date)
        conn = sqlite3.connect(db_path)

        # 初始化每日数据库表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                recommend_price REAL,
                reason TEXT,
                source TEXT DEFAULT '晨报',
                ai_analysis TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS tracking_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                trade_date DATE NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                turnover_rate REAL,
                change_pct REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(stock_code, trade_date)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dimension TEXT NOT NULL,
                score REAL NOT NULL,
                description TEXT,
                details TEXT,
                pushed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        return conn

    def add_recommendation(self, stock_code: str, stock_name: str,
                          price: float, reason: str, source: str = "晨报",
                          ai_analysis: str = "", target_date: date = None):
        """添加推荐记录"""
        if target_date is None:
            target_date = date.today()

        with self.get_daily_db(target_date) as conn:
            conn.execute(
                "INSERT INTO recommendations (stock_code, stock_name, recommend_price, reason, source, ai_analysis) VALUES (?, ?, ?, ?, ?, ?)",
                (stock_code, stock_name, price, reason, source, ai_analysis)
            )
            conn.commit()

        logger.info(f"添加推荐记录: {stock_code} {stock_name} @ {price}")

    def get_recommendations(self, days: int = 5) -> list:
        """获取最近N天的推荐记录"""
        recommendations = []
        today = date.today()

        for i in range(days):
            target_date = today - timedelta(days=i)
            db_path = self._get_daily_db_path(target_date)

            if not db_path.exists():
                continue

            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute(
                    "SELECT stock_code, stock_name, recommend_price, reason, source, ai_analysis, created_at FROM recommendations"
                )
                for row in cursor.fetchall():
                    recommendations.append({
                        "stock_code": row[0],
                        "stock_name": row[1],
                        "recommend_price": row[2],
                        "reason": row[3],
                        "source": row[4],
                        "ai_analysis": row[5],
                        "created_at": row[6],
                        "recommend_date": target_date
                    })

        return recommendations

    def add_watchlist(self, stock_code: str, stock_name: str,
                     add_price: float, reason: str, group_name: str = "默认"):
        """添加特别关注"""
        with sqlite3.connect(self.global_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO watchlist (stock_code, stock_name, add_date, add_price, reason, group_name) VALUES (?, ?, ?, ?, ?, ?)",
                (stock_code, stock_name, date.today(), add_price, reason, group_name)
            )
            conn.commit()

        logger.info(f"添加特别关注: {stock_code} {stock_name} [{group_name}]")

    def remove_watchlist(self, stock_code: str):
        """移除特别关注"""
        with sqlite3.connect(self.global_path) as conn:
            conn.execute("DELETE FROM watchlist WHERE stock_code = ?", (stock_code,))
            conn.commit()

        logger.info(f"移除特别关注: {stock_code}")

    def get_watchlist(self, group_name: str = None) -> list:
        """获取特别关注列表"""
        with sqlite3.connect(self.global_path) as conn:
            if group_name:
                cursor = conn.execute(
                    "SELECT stock_code, stock_name, add_date, add_price, reason, group_name, tracking_days, is_active FROM watchlist WHERE is_active = 1 AND group_name = ?",
                    (group_name,)
                )
            else:
                cursor = conn.execute(
                    "SELECT stock_code, stock_name, add_date, add_price, reason, group_name, tracking_days, is_active FROM watchlist WHERE is_active = 1"
                )

            return [
                WatchlistItem(
                    stock_code=row[0],
                    stock_name=row[1],
                    add_date=date.fromisoformat(row[2]),
                    add_price=row[3],
                    reason=row[4],
                    group_name=row[5],
                    tracking_days=row[6],
                    is_active=bool(row[7])
                )
                for row in cursor.fetchall()
            ]

    def add_trade_record(self, record: TradeRecord):
        """添加操作记录"""
        with sqlite3.connect(self.global_path) as conn:
            conn.execute(
                "INSERT INTO trade_journal (trade_date, trade_type, stock_code, stock_name, price, quantity, reason, emotion, tags, profit_loss, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.trade_date,
                    record.trade_type,
                    record.stock_code,
                    record.stock_name,
                    record.price,
                    record.quantity,
                    record.reason,
                    record.emotion,
                    json.dumps(record.tags or []),
                    record.profit_loss,
                    record.notes
                )
            )
            conn.commit()

        logger.info(f"添加操作记录: {record.trade_type} {record.stock_code}")

    def get_trade_records(self, days: int = 30) -> list:
        """获取操作记录"""
        cutoff_date = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.global_path) as conn:
            cursor = conn.execute(
                "SELECT trade_date, trade_type, stock_code, stock_name, price, quantity, reason, emotion, tags, profit_loss, notes FROM trade_journal WHERE trade_date >= ? ORDER BY trade_date DESC",
                (cutoff_date,)
            )

            return [
                TradeRecord(
                    trade_date=datetime.fromisoformat(row[0]),
                    trade_type=row[1],
                    stock_code=row[2],
                    stock_name=row[3],
                    price=row[4],
                    quantity=row[5],
                    reason=row[6],
                    emotion=row[7],
                    tags=json.loads(row[8]) if row[8] else [],
                    profit_loss=row[9],
                    notes=row[10]
                )
                for row in cursor.fetchall()
            ]

    def add_tracking_data(self, stock_code: str, trade_date: date,
                          open_price: float, high: float, low: float,
                          close: float, volume: float, turnover_rate: float,
                          change_pct: float, target_date: date = None):
        """添加跟踪数据"""
        if target_date is None:
            target_date = date.today()

        with self.get_daily_db(target_date) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tracking_data (stock_code, trade_date, open, high, low, close, volume, turnover_rate, change_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (stock_code, trade_date, open_price, high, low, close, volume, turnover_rate, change_pct)
            )
            conn.commit()

    def backup(self, backup_dir: str = "data/backup"):
        """备份数据库"""
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 备份全局数据库
        if self.global_path.exists():
            shutil.copy2(self.global_path, backup_path / f"global_{timestamp}.db")

        # 备份每日数据库
        for db_file in self.daily_path.glob("*.db"):
            shutil.copy2(db_file, backup_path / db_file.name)

        logger.info(f"数据库备份完成: {backup_path}")

    def cleanup(self, keep_days: int = 30):
        """清理旧数据库"""
        cutoff_date = date.today() - timedelta(days=keep_days)

        for db_file in self.daily_path.glob("*.db"):
            try:
                file_date = date.fromisoformat(db_file.stem)
                if file_date < cutoff_date:
                    db_file.unlink()
                    logger.info(f"清理旧数据库: {db_file}")
            except ValueError:
                continue

    def get_status(self) -> dict:
        """获取数据库状态"""
        daily_count = len(list(self.daily_path.glob("*.db")))

        with sqlite3.connect(self.global_path) as conn:
            watchlist_count = conn.execute("SELECT COUNT(*) FROM watchlist WHERE is_active = 1").fetchone()[0]
            trade_count = conn.execute("SELECT COUNT(*) FROM trade_journal").fetchone()[0]

        return {
            "daily_db_count": daily_count,
            "watchlist_count": watchlist_count,
            "trade_record_count": trade_count,
            "global_db_size": self.global_path.stat().st_size if self.global_path.exists() else 0
        }
