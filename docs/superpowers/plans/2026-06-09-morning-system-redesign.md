# 晨报系统重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构晨报系统，实现异动监控、晚间回溯、特别关注、操作日志四大功能模块

**Architecture:** 模块化架构，采用每日独立数据库 + 全局数据库的设计，支持手动启动和打包部署

**Tech Stack:** Python 3.10+, akshare, feedparser, openai, pandas, sqlite3, pyinstaller

---

## 文件结构

```
morning/
├── __init__.py
├── config.py              # 配置模块（扩展）
├── news_fetcher.py        # 新闻抓取模块（现有）
├── ai_analyzer.py         # AI 分析模块（现有）
├── dingtalk_sender.py     # 钉钉推送模块（现有）
├── fundamental_analyzer.py # 基本面分析模块（现有）
├── anomaly_monitor.py     # 【新增】异动监控模块
├── stock_tracker.py       # 【新增】晚间回溯模块
├── watchlist_manager.py   # 【新增】特别关注模块
├── trade_journal.py       # 【新增】操作日志模块
└── db_manager.py          # 【新增】数据库管理模块

tests/
├── __init__.py
├── test_db_manager.py
├── test_anomaly_monitor.py
├── test_stock_tracker.py
├── test_watchlist_manager.py
└── test_trade_journal.py

data/
├── daily/                 # 每日独立数据库
├── global.db              # 全局数据库
└── backup/                # 备份目录
```

---

## Task 1: 数据库管理模块 (db_manager.py)

**Files:**
- Create: `morning/db_manager.py`
- Test: `tests/test_db_manager.py`

- [ ] **Step 1: 创建数据库管理模块基础结构**

```python
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
```

- [ ] **Step 2: 创建数据库管理模块测试**

```python
# tests/test_db_manager.py
"""
数据库管理模块测试
"""
import pytest
import tempfile
import shutil
from datetime import date, datetime
from pathlib import Path
from morning.db_manager import DBManager, TradeRecord


class TestDBManager:
    """数据库管理器测试"""
    
    @pytest.fixture
    def db_manager(self):
        """创建临时数据库管理器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            daily_path = Path(tmpdir) / "daily"
            global_path = Path(tmpdir) / "global.db"
            yield DBManager(str(daily_path), str(global_path))
    
    def test_init_global_db(self, db_manager):
        """测试全局数据库初始化"""
        assert db_manager.global_path.exists()
    
    def test_add_recommendation(self, db_manager):
        """测试添加推荐记录"""
        db_manager.add_recommendation("000001", "平安银行", 10.83, "突破年线")
        
        recommendations = db_manager.get_recommendations(days=1)
        assert len(recommendations) == 1
        assert recommendations[0]["stock_code"] == "000001"
        assert recommendations[0]["stock_name"] == "平安银行"
    
    def test_add_watchlist(self, db_manager):
        """测试添加特别关注"""
        db_manager.add_watchlist("000001", "平安银行", 10.83, "突破年线", "短线")
        
        watchlist = db_manager.get_watchlist()
        assert len(watchlist) == 1
        assert watchlist[0].stock_code == "000001"
        assert watchlist[0].group_name == "短线"
    
    def test_remove_watchlist(self, db_manager):
        """测试移除特别关注"""
        db_manager.add_watchlist("000001", "平安银行", 10.83, "突破年线")
        db_manager.remove_watchlist("000001")
        
        watchlist = db_manager.get_watchlist()
        assert len(watchlist) == 0
    
    def test_add_trade_record(self, db_manager):
        """测试添加操作记录"""
        record = TradeRecord(
            trade_date=datetime.now(),
            trade_type="BUY",
            stock_code="000001",
            stock_name="平安银行",
            price=10.83,
            quantity=1000,
            reason="突破年线",
            emotion="自信",
            tags=["技术面"]
        )
        db_manager.add_trade_record(record)
        
        records = db_manager.get_trade_records(days=1)
        assert len(records) == 1
        assert records[0].trade_type == "BUY"
    
    def test_get_status(self, db_manager):
        """测试获取数据库状态"""
        status = db_manager.get_status()
        assert "daily_db_count" in status
        assert "watchlist_count" in status
        assert "trade_record_count" in status
    
    def test_backup(self, db_manager):
        """测试备份功能"""
        db_manager.add_watchlist("000001", "平安银行", 10.83, "突破年线")
        
        with tempfile.TemporaryDirectory() as backup_dir:
            db_manager.backup(backup_dir)
            assert len(list(Path(backup_dir).glob("*.db"))) > 0
```

- [ ] **Step 3: 运行测试验证**

```bash
pytest tests/test_db_manager.py -v
```

- [ ] **Step 4: 提交代码**

```bash
git add morning/db_manager.py tests/test_db_manager.py
git commit -m "feat: add database manager module with daily and global database support"
```

---

## Task 2: 扩展配置模块 (config.py)

**Files:**
- Modify: `morning/config.py`
- Modify: `config.yaml`

- [ ] **Step 1: 扩展配置模块支持新功能**

```python
# morning/config.py (新增部分)

@dataclass
class AnomalyMonitorConfig:
    """异动监控配置"""
    enabled: bool = True
    push_threshold: int = 60
    dimensions: dict = None
    
    def __post_init__(self):
        if self.dimensions is None:
            self.dimensions = {
                "macro": {"enabled": True, "weight": 25},
                "commodity": {"enabled": True, "weight": 25},
                "tech": {"enabled": True, "weight": 25},
                "event": {"enabled": True, "weight": 25}
            }


@dataclass
class StockTrackerConfig:
    """晚间回溯配置"""
    enabled: bool = True
    tracking_days: int = 5
    data_fields: list = None
    
    def __post_init__(self):
        if self.data_fields is None:
            self.data_fields = ["open", "high", "low", "close", "volume", "turnover_rate", "change_pct"]


@dataclass
class WatchlistConfig:
    """特别关注配置"""
    enabled: bool = True
    groups: list = None
    
    def __post_init__(self):
        if self.groups is None:
            self.groups = [
                {"name": "短线", "color": "#FF6B6B"},
                {"name": "中线", "color": "#4ECDC4"},
                {"name": "长线", "color": "#45B7D1"}
            ]


@dataclass
class TradeJournalConfig:
    """操作日志配置"""
    enabled: bool = True
    emotion_tags: list = None
    trade_tags: list = None
    
    def __post_init__(self):
        if self.emotion_tags is None:
            self.emotion_tags = ["自信", "犹豫", "恐惧", "贪婪", "平静"]
        if self.trade_tags is None:
            self.trade_tags = ["技术面", "基本面", "消息面", "资金面"]


@dataclass
class DatabaseConfig:
    """数据库配置"""
    daily_path: str = "data/daily"
    global_path: str = "data/global.db"
    backup_enabled: bool = True
    backup_days: int = 30
    auto_cleanup: bool = True
    cleanup_days: int = 90


@dataclass
class AppConfig:
    """应用配置"""
    morning: MorningConfig = None
    ai: AIConfig = None
    dingtalk: DingTalkConfig = None
    anomaly_monitor: AnomalyMonitorConfig = None
    stock_tracker: StockTrackerConfig = None
    watchlist: WatchlistConfig = None
    trade_journal: TradeJournalConfig = None
    database: DatabaseConfig = None
    logging: LoggingConfig = None
    
    def __post_init__(self):
        if self.morning is None:
            self.morning = MorningConfig()
        if self.ai is None:
            self.ai = AIConfig()
        if self.dingtalk is None:
            self.dingtalk = DingTalkConfig()
        if self.anomaly_monitor is None:
            self.anomaly_monitor = AnomalyMonitorConfig()
        if self.stock_tracker is None:
            self.stock_tracker = StockTrackerConfig()
        if self.watchlist is None:
            self.watchlist = WatchlistConfig()
        if self.trade_journal is None:
            self.trade_journal = TradeJournalConfig()
        if self.database is None:
            self.database = DatabaseConfig()
        if self.logging is None:
            self.logging = LoggingConfig()
```

- [ ] **Step 2: 更新 config.yaml 配置文件**

```yaml
# config.yaml

# 异动监控配置
anomaly_monitor:
  enabled: true
  push_threshold: 60
  dimensions:
    macro:
      enabled: true
      weight: 25
      data_sources:
        - "macro_bank_usa_interest_rate"
        - "macro_china_cpi_yearly"
    commodity:
      enabled: true
      weight: 25
      data_sources:
        - "futures_main_sina"
        - "spot_golden_benchmark_sge"
    tech:
      enabled: true
      weight: 25
      keywords: ["AI", "芯片", "新能源", "半导体", "人工智能"]
    event:
      enabled: true
      weight: 25
      keywords: ["政策", "地缘", "制裁", "战争", "灾害"]

# 晚间回溯配置
stock_tracker:
  enabled: true
  tracking_days: 5
  data_fields:
    - open
    - high
    - low
    - close
    - volume
    - turnover_rate
    - change_pct

# 特别关注配置
watchlist:
  enabled: true
  groups:
    - name: "短线"
      color: "#FF6B6B"
    - name: "中线"
      color: "#4ECDC4"
    - name: "长线"
      color: "#45B7D1"

# 操作日志配置
trade_journal:
  enabled: true
  emotion_tags: ["自信", "犹豫", "恐惧", "贪婪", "平静"]
  trade_tags: ["技术面", "基本面", "消息面", "资金面"]

# 数据库配置
database:
  daily_path: "data/daily"
  global_path: "data/global.db"
  backup_enabled: true
  backup_days: 30
  auto_cleanup: true
  cleanup_days: 90
```

- [ ] **Step 3: 提交代码**

```bash
git add morning/config.py config.yaml
git commit -m "feat: extend config module to support new features"
```

---

## Task 3: 异动监控模块 (anomaly_monitor.py)

**Files:**
- Create: `morning/anomaly_monitor.py`
- Test: `tests/test_anomaly_monitor.py`

- [ ] **Step 1: 创建异动监控模块**

```python
# morning/anomaly_monitor.py
"""
异动监控模块
监控宏观经济、大宗商品、科技赛道、突发事件四个维度
"""
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AnomalyScore:
    """异动评分"""
    dimension: str  # 宏观/大宗/科技/突发
    score: float    # 0-25分
    description: str
    details: dict = None


@dataclass
class AnomalyResult:
    """异动监控结果"""
    total_score: float  # 0-100分
    scores: list  # List[AnomalyScore]
    timestamp: datetime
    should_push: bool  # 是否达到推送阈值


class AnomalyMonitor:
    """异动监控器"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.push_threshold = self.config.get("push_threshold", 60)
    
    def monitor_macro(self) -> AnomalyScore:
        """监控宏观经济"""
        score = 0
        details = {}
        description_parts = []
        
        try:
            # 获取美联储利率数据
            df = ak.macro_bank_usa_interest_rate()
            if len(df) > 0:
                latest = df.iloc[-1]
                # 简化评分逻辑：根据最新利率变化评分
                score += 5  # 基础分
                description_parts.append("美联储利率数据正常")
                details["fed_rate"] = "正常"
        except Exception as e:
            logger.warning(f"获取美联储利率失败: {e}")
            details["fed_rate"] = f"失败: {e}"
        
        try:
            # 获取中国CPI数据
            df = ak.macro_china_cpi_yearly()
            if len(df) > 0:
                score += 5
                description_parts.append("CPI数据正常")
                details["cpi"] = "正常"
        except Exception as e:
            logger.warning(f"获取CPI数据失败: {e}")
            details["cpi"] = f"失败: {e}"
        
        # 限制分数范围
        score = max(0, min(25, score))
        description = "宏观经济: " + "; ".join(description_parts) if description_parts else "宏观经济数据获取失败"
        
        return AnomalyScore(
            dimension="宏观",
            score=score,
            description=description,
            details=details
        )
    
    def monitor_commodity(self) -> AnomalyScore:
        """监控大宗商品"""
        score = 0
        details = {}
        description_parts = []
        
        try:
            # 获取期货主力数据
            df = ak.futures_main_sina(symbol="V0")  # 聚氯乙烯主力
            if len(df) > 0:
                latest = df.iloc[-1]
                # 简化评分逻辑
                score += 8
                description_parts.append("期货数据正常")
                details["futures"] = "正常"
        except Exception as e:
            logger.warning(f"获取期货数据失败: {e}")
            details["futures"] = f"失败: {e}"
        
        # 限制分数范围
        score = max(0, min(25, score))
        description = "大宗商品: " + "; ".join(description_parts) if description_parts else "大宗商品数据获取失败"
        
        return AnomalyScore(
            dimension="大宗",
            score=score,
            description=description,
            details=details
        )
    
    def monitor_tech(self, news_list: list = None) -> AnomalyScore:
        """监控科技赛道"""
        score = 0
        details = {}
        description_parts = []
        
        tech_keywords = self.config.get("dimensions", {}).get("tech", {}).get("keywords", 
            ["AI", "芯片", "新能源", "半导体", "人工智能"])
        
        if news_list:
            # 统计科技相关新闻数量
            tech_news = []
            for news in news_list:
                if any(keyword in news.get("title", "") or keyword in news.get("text", "") 
                      for keyword in tech_keywords):
                    tech_news.append(news)
            
            # 每条科技新闻 +2分，上限15分
            news_score = min(15, len(tech_news) * 2)
            score += news_score
            description_parts.append(f"科技新闻 {len(tech_news)} 条")
            details["tech_news_count"] = len(tech_news)
        
        # 限制分数范围
        score = max(0, min(25, score))
        description = "科技赛道: " + "; ".join(description_parts) if description_parts else "无科技相关新闻"
        
        return AnomalyScore(
            dimension="科技",
            score=score,
            description=description,
            details=details
        )
    
    def monitor_event(self, news_list: list = None) -> AnomalyScore:
        """监控突发事件"""
        score = 0
        details = {}
        description_parts = []
        
        event_keywords = self.config.get("dimensions", {}).get("event", {}).get("keywords",
            ["政策", "地缘", "制裁", "战争", "灾害"])
        
        if news_list:
            # 统计突发事件相关新闻数量
            event_news = []
            for news in news_list:
                if any(keyword in news.get("title", "") or keyword in news.get("text", "")
                      for keyword in event_keywords):
                    event_news.append(news)
            
            # 每条突发事件新闻 +5分，上限25分
            event_score = min(25, len(event_news) * 5)
            score += event_score
            description_parts.append(f"突发事件新闻 {len(event_news)} 条")
            details["event_news_count"] = len(event_news)
        
        # 限制分数范围
        score = max(0, min(25, score))
        description = "突发事件: " + "; ".join(description_parts) if description_parts else "无突发事件"
        
        return AnomalyScore(
            dimension="突发",
            score=score,
            description=description,
            details=details
        )
    
    def run(self, news_list: list = None) -> AnomalyResult:
        """运行异动监控"""
        logger.info("开始异动监控...")
        
        scores = []
        
        # 监控宏观经济
        macro_score = self.monitor_macro()
        scores.append(macro_score)
        
        # 监控大宗商品
        commodity_score = self.monitor_commodity()
        scores.append(commodity_score)
        
        # 监控科技赛道
        tech_score = self.monitor_tech(news_list)
        scores.append(tech_score)
        
        # 监控突发事件
        event_score = self.monitor_event(news_list)
        scores.append(event_score)
        
        # 计算总分
        total_score = sum(s.score for s in scores)
        
        # 判断是否达到推送阈值
        should_push = total_score >= self.push_threshold
        
        result = AnomalyResult(
            total_score=total_score,
            scores=scores,
            timestamp=datetime.now(),
            should_push=should_push
        )
        
        logger.info(f"异动监控完成: 总分={total_score}, 推送阈值={self.push_threshold}, 是否推送={should_push}")
        
        return result
```

- [ ] **Step 2: 创建异动监控模块测试**

```python
# tests/test_anomaly_monitor.py
"""
异动监控模块测试
"""
import pytest
from morning.anomaly_monitor import AnomalyMonitor, AnomalyResult


class TestAnomalyMonitor:
    """异动监控器测试"""
    
    @pytest.fixture
    def monitor(self):
        """创建异动监控器"""
        return AnomalyMonitor({"push_threshold": 60})
    
    def test_monitor_macro(self, monitor):
        """测试宏观经济监控"""
        score = monitor.monitor_macro()
        assert score.dimension == "宏观"
        assert 0 <= score.score <= 25
    
    def test_monitor_commodity(self, monitor):
        """测试大宗商品监控"""
        score = monitor.monitor_commodity()
        assert score.dimension == "大宗"
        assert 0 <= score.score <= 25
    
    def test_monitor_tech(self, monitor):
        """测试科技赛道监控"""
        news_list = [
            {"title": "AI技术突破", "text": "人工智能"},
            {"title": "芯片产业发展", "text": "半导体"},
            {"title": "普通新闻", "text": "无关键词"}
        ]
        score = monitor.monitor_tech(news_list)
        assert score.dimension == "科技"
        assert 0 <= score.score <= 25
    
    def test_monitor_event(self, monitor):
        """测试突发事件监控"""
        news_list = [
            {"title": "政策变化", "text": "新政策"},
            {"title": "地缘政治", "text": "制裁"}
        ]
        score = monitor.monitor_event(news_list)
        assert score.dimension == "突发"
        assert 0 <= score.score <= 25
    
    def test_run(self, monitor):
        """测试完整运行"""
        result = monitor.run()
        assert isinstance(result, AnomalyResult)
        assert 0 <= result.total_score <= 100
        assert isinstance(result.should_push, bool)
    
    def test_push_threshold(self):
        """测试推送阈值"""
        monitor = AnomalyMonitor({"push_threshold": 0})
        result = monitor.run()
        assert result.should_push == True
        
        monitor = AnomalyMonitor({"push_threshold": 100})
        result = monitor.run()
        assert result.should_push == False
```

- [ ] **Step 3: 运行测试验证**

```bash
pytest tests/test_anomaly_monitor.py -v
```

- [ ] **Step 4: 提交代码**

```bash
git add morning/anomaly_monitor.py tests/test_anomaly_monitor.py
git commit -m "feat: add anomaly monitor module with macro/commodity/tech/event monitoring"
```

---

## Task 4: 特别关注模块 (watchlist_manager.py)

**Files:**
- Create: `morning/watchlist_manager.py`
- Test: `tests/test_watchlist_manager.py`

- [ ] **Step 1: 创建特别关注模块**

```python
# morning/watchlist_manager.py
"""
特别关注模块
管理特别关注的股票列表
"""
import logging
from datetime import date, datetime
from typing import Optional
from dataclasses import dataclass
from .db_manager import DBManager, WatchlistItem

logger = logging.getLogger(__name__)


class WatchlistManager:
    """特别关注管理器"""
    
    def __init__(self, db_manager: DBManager):
        self.db_manager = db_manager
    
    def add(self, stock_code: str, stock_name: str, 
            price: float, reason: str, group_name: str = "默认") -> bool:
        """添加特别关注"""
        try:
            self.db_manager.add_watchlist(stock_code, stock_name, price, reason, group_name)
            return True
        except Exception as e:
            logger.error(f"添加特别关注失败: {e}")
            return False
    
    def remove(self, stock_code: str) -> bool:
        """移除特别关注"""
        try:
            self.db_manager.remove_watchlist(stock_code)
            return True
        except Exception as e:
            logger.error(f"移除特别关注失败: {e}")
            return False
    
    def list(self, group_name: str = None) -> list:
        """获取特别关注列表"""
        return self.db_manager.get_watchlist(group_name)
    
    def change_group(self, stock_code: str, new_group: str) -> bool:
        """修改分组"""
        try:
            # 获取当前关注信息
            watchlist = self.db_manager.get_watchlist()
            item = next((w for w in watchlist if w.stock_code == stock_code), None)
            
            if not item:
                logger.warning(f"未找到关注股票: {stock_code}")
                return False
            
            # 更新分组
            self.db_manager.add_watchlist(
                item.stock_code,
                item.stock_name,
                item.add_price,
                item.reason,
                new_group
            )
            
            logger.info(f"修改分组: {stock_code} -> {new_group}")
            return True
        except Exception as e:
            logger.error(f"修改分组失败: {e}")
            return False
    
    def get_groups(self) -> list:
        """获取所有分组"""
        watchlist = self.list()
        groups = list(set(item.group_name for item in watchlist))
        return sorted(groups)
    
    def format_list(self, group_name: str = None) -> str:
        """格式化输出关注列表"""
        watchlist = self.list(group_name)
        
        if not watchlist:
            return "暂无特别关注股票"
        
        lines = ["📊 特别关注列表", ""]
        
        # 按分组组织
        groups = {}
        for item in watchlist:
            if item.group_name not in groups:
                groups[item.group_name] = []
            groups[item.group_name].append(item)
        
        for group_name, items in groups.items():
            lines.append(f"【{group_name}】")
            for item in items:
                lines.append(f"  {item.stock_code} {item.stock_name}")
                lines.append(f"    关注日期: {item.add_date}")
                lines.append(f"    关注价格: {item.add_price}")
                lines.append(f"    关注理由: {item.reason}")
            lines.append("")
        
        return "\n".join(lines)
```

- [ ] **Step 2: 创建特别关注模块测试**

```python
# tests/test_watchlist_manager.py
"""
特别关注模块测试
"""
import pytest
import tempfile
from pathlib import Path
from morning.db_manager import DBManager
from morning.watchlist_manager import WatchlistManager


class TestWatchlistManager:
    """特别关注管理器测试"""
    
    @pytest.fixture
    def manager(self):
        """创建特别关注管理器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_manager = DBManager(
                str(Path(tmpdir) / "daily"),
                str(Path(tmpdir) / "global.db")
            )
            yield WatchlistManager(db_manager)
    
    def test_add(self, manager):
        """测试添加关注"""
        result = manager.add("000001", "平安银行", 10.83, "突破年线", "短线")
        assert result == True
        
        watchlist = manager.list()
        assert len(watchlist) == 1
        assert watchlist[0].stock_code == "000001"
    
    def test_remove(self, manager):
        """测试移除关注"""
        manager.add("000001", "平安银行", 10.83, "突破年线")
        result = manager.remove("000001")
        assert result == True
        
        watchlist = manager.list()
        assert len(watchlist) == 0
    
    def test_list(self, manager):
        """测试获取列表"""
        manager.add("000001", "平安银行", 10.83, "突破年线", "短线")
        manager.add("600036", "招商银行", 35.20, "价值投资", "中线")
        
        # 获取全部
        watchlist = manager.list()
        assert len(watchlist) == 2
        
        # 按分组获取
        watchlist = manager.list("短线")
        assert len(watchlist) == 1
        assert watchlist[0].stock_code == "000001"
    
    def test_change_group(self, manager):
        """测试修改分组"""
        manager.add("000001", "平安银行", 10.83, "突破年线", "短线")
        result = manager.change_group("000001", "中线")
        assert result == True
        
        watchlist = manager.list("中线")
        assert len(watchlist) == 1
    
    def test_get_groups(self, manager):
        """测试获取分组"""
        manager.add("000001", "平安银行", 10.83, "突破年线", "短线")
        manager.add("600036", "招商银行", 35.20, "价值投资", "中线")
        
        groups = manager.get_groups()
        assert "短线" in groups
        assert "中线" in groups
    
    def test_format_list(self, manager):
        """测试格式化输出"""
        manager.add("000001", "平安银行", 10.83, "突破年线", "短线")
        
        output = manager.format_list()
        assert "000001" in output
        assert "平安银行" in output
        assert "短线" in output
```

- [ ] **Step 3: 运行测试验证**

```bash
pytest tests/test_watchlist_manager.py -v
```

- [ ] **Step 4: 提交代码**

```bash
git add morning/watchlist_manager.py tests/test_watchlist_manager.py
git commit -m "feat: add watchlist manager module for stock tracking"
```

---

## Task 5: 操作日志模块 (trade_journal.py)

**Files:**
- Create: `morning/trade_journal.py`
- Test: `tests/test_trade_journal.py`

- [ ] **Step 1: 创建操作日志模块**

```python
# morning/trade_journal.py
"""
操作日志模块
记录交易操作，支持复盘分析
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field
from collections import Counter
from .db_manager import DBManager, TradeRecord

logger = logging.getLogger(__name__)


@dataclass
class TradeStats:
    """交易统计"""
    total_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    profit_loss_ratio: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0


@dataclass
class EmotionStats:
    """情绪统计"""
    emotion: str
    count: int
    win_count: int
    win_rate: float


@dataclass
class TagStats:
    """标签统计"""
    tag: str
    count: int
    win_count: int
    win_rate: float


class TradeJournal:
    """操作日志管理器"""
    
    def __init__(self, db_manager: DBManager, config: dict = None):
        self.db_manager = db_manager
        self.config = config or {}
        self.emotion_tags = self.config.get("emotion_tags", ["自信", "犹豫", "恐惧", "贪婪", "平静"])
        self.trade_tags = self.config.get("trade_tags", ["技术面", "基本面", "消息面", "资金面"])
    
    def record_buy(self, stock_code: str, stock_name: str, 
                   price: float, quantity: int, reason: str, 
                   emotion: str = "", tags: list = None) -> bool:
        """记录买入操作"""
        try:
            record = TradeRecord(
                trade_date=datetime.now(),
                trade_type="BUY",
                stock_code=stock_code,
                stock_name=stock_name,
                price=price,
                quantity=quantity,
                reason=reason,
                emotion=emotion,
                tags=tags or []
            )
            self.db_manager.add_trade_record(record)
            logger.info(f"记录买入: {stock_code} {stock_name} @ {price} x {quantity}")
            return True
        except Exception as e:
            logger.error(f"记录买入失败: {e}")
            return False
    
    def record_sell(self, stock_code: str, stock_name: str,
                    price: float, quantity: int, reason: str,
                    emotion: str = "", tags: list = None,
                    profit_loss: float = 0.0) -> bool:
        """记录卖出操作"""
        try:
            record = TradeRecord(
                trade_date=datetime.now(),
                trade_type="SELL",
                stock_code=stock_code,
                stock_name=stock_name,
                price=price,
                quantity=quantity,
                reason=reason,
                emotion=emotion,
                tags=tags or [],
                profit_loss=profit_loss
            )
            self.db_manager.add_trade_record(record)
            logger.info(f"记录卖出: {stock_code} {stock_name} @ {price} x {quantity}")
            return True
        except Exception as e:
            logger.error(f"记录卖出失败: {e}")
            return False
    
    def record_watch(self, stock_code: str, reason: str) -> bool:
        """记录关注操作"""
        try:
            record = TradeRecord(
                trade_date=datetime.now(),
                trade_type="WATCH",
                stock_code=stock_code,
                reason=reason
            )
            self.db_manager.add_trade_record(record)
            logger.info(f"记录关注: {stock_code}")
            return True
        except Exception as e:
            logger.error(f"记录关注失败: {e}")
            return False
    
    def record_unwatch(self, stock_code: str) -> bool:
        """记录取消关注操作"""
        try:
            record = TradeRecord(
                trade_date=datetime.now(),
                trade_type="UNWATCH",
                stock_code=stock_code
            )
            self.db_manager.add_trade_record(record)
            logger.info(f"记录取消关注: {stock_code}")
            return True
        except Exception as e:
            logger.error(f"记录取消关注失败: {e}")
            return False
    
    def record_note(self, stock_code: str, notes: str) -> bool:
        """记录备注"""
        try:
            record = TradeRecord(
                trade_date=datetime.now(),
                trade_type="NOTE",
                stock_code=stock_code,
                notes=notes
            )
            self.db_manager.add_trade_record(record)
            logger.info(f"记录备注: {stock_code}")
            return True
        except Exception as e:
            logger.error(f"记录备注失败: {e}")
            return False
    
    def get_records(self, days: int = 30) -> list:
        """获取操作记录"""
        return self.db_manager.get_trade_records(days)
    
    def calculate_stats(self, days: int = 30) -> TradeStats:
        """计算交易统计"""
        records = self.get_records(days)
        
        # 筛选卖出记录
        sell_records = [r for r in records if r.trade_type == "SELL"]
        
        if not sell_records:
            return TradeStats()
        
        # 计算统计
        profits = [r.profit_loss for r in sell_records if r.profit_loss > 0]
        losses = [r.profit_loss for r in sell_records if r.profit_loss < 0]
        
        win_count = len(profits)
        loss_count = len(losses)
        total_trades = len(sell_records)
        
        avg_profit = sum(profits) / len(profits) if profits else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        return TradeStats(
            total_trades=total_trades,
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_count / total_trades if total_trades > 0 else 0,
            avg_profit=avg_profit,
            avg_loss=avg_loss,
            profit_loss_ratio=abs(avg_profit / avg_loss) if avg_loss != 0 else 0,
            max_profit=max(profits) if profits else 0,
            max_loss=min(losses) if losses else 0
        )
    
    def calculate_emotion_stats(self, days: int = 30) -> list:
        """计算情绪统计"""
        records = self.get_records(days)
        sell_records = [r for r in records if r.trade_type == "SELL" and r.emotion]
        
        emotion_data = {}
        for record in sell_records:
            if record.emotion not in emotion_data:
                emotion_data[record.emotion] = {"count": 0, "win_count": 0}
            emotion_data[record.emotion]["count"] += 1
            if record.profit_loss > 0:
                emotion_data[record.emotion]["win_count"] += 1
        
        return [
            EmotionStats(
                emotion=emotion,
                count=data["count"],
                win_count=data["win_count"],
                win_rate=data["win_count"] / data["count"] if data["count"] > 0 else 0
            )
            for emotion, data in emotion_data.items()
        ]
    
    def calculate_tag_stats(self, days: int = 30) -> list:
        """计算标签统计"""
        records = self.get_records(days)
        sell_records = [r for r in records if r.trade_type == "SELL" and r.tags]
        
        tag_data = {}
        for record in sell_records:
            for tag in record.tags:
                if tag not in tag_data:
                    tag_data[tag] = {"count": 0, "win_count": 0}
                tag_data[tag]["count"] += 1
                if record.profit_loss > 0:
                    tag_data[tag]["win_count"] += 1
        
        return [
            TagStats(
                tag=tag,
                count=data["count"],
                win_count=data["win_count"],
                win_rate=data["win_count"] / data["count"] if data["count"] > 0 else 0
            )
            for tag, data in tag_data.items()
        ]
    
    def generate_review_report(self, days: int = 30) -> str:
        """生成复盘报告"""
        stats = self.calculate_stats(days)
        emotion_stats = self.calculate_emotion_stats(days)
        tag_stats = self.calculate_tag_stats(days)
        records = self.get_records(days)
        
        lines = [
            f"📊 操作复盘报告 (最近{days}天)",
            "",
            "═" * 40,
            "【交易统计】",
            "═" * 40,
            f"总交易次数：{stats.total_trades}",
            f"盈利次数：{stats.win_count}",
            f"亏损次数：{stats.loss_count}",
            f"胜率：{stats.win_rate:.1%}",
            f"平均盈利：{stats.avg_profit:+.2%}",
            f"平均亏损：{stats.avg_loss:+.2%}",
            f"盈亏比：{stats.profit_loss_ratio:.2f}",
            f"最大单笔盈利：{stats.max_profit:+.2%}",
            f"最大单笔亏损：{stats.max_loss:+.2%}",
            "",
            "═" * 40,
            "【情绪分析】",
            "═" * 40,
        ]
        
        for emotion_stat in emotion_stats:
            lines.append(f"{emotion_stat.emotion}时交易：{emotion_stat.count}次，胜率{emotion_stat.win_rate:.1%}")
        
        lines.extend([
            "",
            "═" * 40,
            "【标签分析】",
            "═" * 40,
        ])
        
        for tag_stat in tag_stats:
            lines.append(f"{tag_stat.tag}交易：{tag_stat.count}次，胜率{tag_stat.win_rate:.1%}")
        
        lines.extend([
            "",
            "═" * 40,
            "【操作明细】",
            "═" * 40,
        ])
        
        for record in records[:20]:  # 只显示最近20条
            lines.append(f"{record.trade_date.strftime('%Y-%m-%d %H:%M')}  {record.trade_type:5}  {record.stock_code} {record.stock_name}")
            if record.reason:
                lines.append(f"理由：{record.reason} | 情绪：{record.emotion} | 标签：{', '.join(record.tags)}")
            if record.profit_loss != 0:
                lines.append(f"结果：{record.profit_loss:+.2%}")
            lines.append("")
        
        return "\n".join(lines)
```

- [ ] **Step 2: 创建操作日志模块测试**

```python
# tests/test_trade_journal.py
"""
操作日志模块测试
"""
import pytest
import tempfile
from pathlib import Path
from morning.db_manager import DBManager
from morning.trade_journal import TradeJournal


class TestTradeJournal:
    """操作日志管理器测试"""
    
    @pytest.fixture
    def journal(self):
        """创建操作日志管理器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_manager = DBManager(
                str(Path(tmpdir) / "daily"),
                str(Path(tmpdir) / "global.db")
            )
            yield TradeJournal(db_manager)
    
    def test_record_buy(self, journal):
        """测试记录买入"""
        result = journal.record_buy("000001", "平安银行", 10.83, 1000, "突破年线", "自信", ["技术面"])
        assert result == True
        
        records = journal.get_records(days=1)
        assert len(records) == 1
        assert records[0].trade_type == "BUY"
    
    def test_record_sell(self, journal):
        """测试记录卖出"""
        result = journal.record_sell("000001", "平安银行", 11.13, 1000, "止盈", "犹豫", ["技术面"], 0.028)
        assert result == True
        
        records = journal.get_records(days=1)
        assert len(records) == 1
        assert records[0].trade_type == "SELL"
    
    def test_record_watch(self, journal):
        """测试记录关注"""
        result = journal.record_watch("000001", "突破年线")
        assert result == True
        
        records = journal.get_records(days=1)
        assert len(records) == 1
        assert records[0].trade_type == "WATCH"
    
    def test_record_unwatch(self, journal):
        """测试记录取消关注"""
        result = journal.record_unwatch("000001")
        assert result == True
        
        records = journal.get_records(days=1)
        assert len(records) == 1
        assert records[0].trade_type == "UNWATCH"
    
    def test_record_note(self, journal):
        """测试记录备注"""
        result = journal.record_note("000001", "这是一条备注")
        assert result == True
        
        records = journal.get_records(days=1)
        assert len(records) == 1
        assert records[0].trade_type == "NOTE"
    
    def test_calculate_stats(self, journal):
        """测试计算统计"""
        # 添加测试数据
        journal.record_sell("000001", "平安银行", 11.13, 1000, "止盈", profit_loss=0.028)
        journal.record_sell("600036", "招商银行", 34.50, 1000, "止损", profit_loss=-0.02)
        
        stats = journal.calculate_stats(days=1)
        assert stats.total_trades == 2
        assert stats.win_count == 1
        assert stats.loss_count == 1
        assert stats.win_rate == 0.5
    
    def test_calculate_emotion_stats(self, journal):
        """测试情绪统计"""
        journal.record_sell("000001", "平安银行", 11.13, 1000, "止盈", "自信", profit_loss=0.028)
        journal.record_sell("600036", "招商银行", 34.50, 1000, "止损", "犹豫", profit_loss=-0.02)
        
        emotion_stats = journal.calculate_emotion_stats(days=1)
        assert len(emotion_stats) == 2
    
    def test_calculate_tag_stats(self, journal):
        """测试标签统计"""
        journal.record_sell("000001", "平安银行", 11.13, 1000, "止盈", tags=["技术面"], profit_loss=0.028)
        journal.record_sell("600036", "招商银行", 34.50, 1000, "止损", tags=["基本面"], profit_loss=-0.02)
        
        tag_stats = journal.calculate_tag_stats(days=1)
        assert len(tag_stats) == 2
    
    def test_generate_review_report(self, journal):
        """测试生成复盘报告"""
        journal.record_sell("000001", "平安银行", 11.13, 1000, "止盈", "自信", ["技术面"], 0.028)
        
        report = journal.generate_review_report(days=1)
        assert "操作复盘报告" in report
        assert "交易统计" in report
        assert "情绪分析" in report
        assert "标签分析" in report
```

- [ ] **Step 3: 运行测试验证**

```bash
pytest tests/test_trade_journal.py -v
```

- [ ] **Step 4: 提交代码**

```bash
git add morning/trade_journal.py tests/test_trade_journal.py
git commit -m "feat: add trade journal module for operation logging and review"
```

---

## Task 6: 晚间回溯模块 (stock_tracker.py)

**Files:**
- Create: `morning/stock_tracker.py`
- Test: `tests/test_stock_tracker.py`

- [ ] **Step 1: 创建晚间回溯模块**

```python
# morning/stock_tracker.py
"""
晚间回溯模块
跟踪推荐股票和特别关注股票的行情
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional
from dataclasses import dataclass
import akshare as ak
import pandas as pd
from .db_manager import DBManager, WatchlistItem

logger = logging.getLogger(__name__)


@dataclass
class StockTrackingInfo:
    """股票跟踪信息"""
    stock_code: str
    stock_name: str
    is_watchlist: bool  # 是否特别关注
    recommend_date: date
    recommend_price: float
    current_price: float
    change_pct: float
    tracking_days: int
    history_data: list  # 历史行情数据


class StockTracker:
    """股票跟踪器"""
    
    def __init__(self, db_manager: DBManager, config: dict = None):
        self.db_manager = db_manager
        self.config = config or {}
        self.default_tracking_days = self.config.get("tracking_days", 5)
    
    def fetch_stock_history(self, stock_code: str, days: int = 5) -> pd.DataFrame:
        """获取股票历史行情"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days + 5)  # 多取几天以确保有足够的交易日
            
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq"  # 前复权
            )
            
            if df is not None and len(df) > 0:
                # 标准化列名
                df = df.rename(columns={
                    "日期": "trade_date",
                    "开盘": "open",
                    "最高": "high",
                    "最低": "low",
                    "收盘": "close",
                    "成交量": "volume",
                    "换手率": "turnover_rate",
                    "涨跌幅": "change_pct"
                })
                return df
            
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"获取股票历史行情失败 {stock_code}: {e}")
            return pd.DataFrame()
    
    def get_tracking_stocks(self, days: int = None) -> list:
        """获取需要跟踪的股票列表"""
        if days is None:
            days = self.default_tracking_days
        
        tracking_stocks = []
        
        # 1. 获取推荐记录
        recommendations = self.db_manager.get_recommendations(days)
        for rec in recommendations:
            tracking_stocks.append({
                "stock_code": rec["stock_code"],
                "stock_name": rec["stock_name"],
                "is_watchlist": False,
                "recommend_date": rec["recommend_date"],
                "recommend_price": rec["recommend_price"],
                "tracking_days": days
            })
        
        # 2. 获取特别关注股票
        watchlist = self.db_manager.get_watchlist()
        for item in watchlist:
            # 检查是否已经在推荐记录中
            if not any(s["stock_code"] == item.stock_code for s in tracking_stocks):
                tracking_stocks.append({
                    "stock_code": item.stock_code,
                    "stock_name": item.stock_name,
                    "is_watchlist": True,
                    "recommend_date": item.add_date,
                    "recommend_price": item.add_price,
                    "tracking_days": item.tracking_days if item.tracking_days > 0 else days
                })
        
        return tracking_stocks
    
    def track_stocks(self, days: int = None) -> list:
        """跟踪股票行情"""
        if days is None:
            days = self.default_tracking_days
        
        tracking_stocks = self.get_tracking_stocks(days)
        results = []
        
        for stock_info in tracking_stocks:
            stock_code = stock_info["stock_code"]
            tracking_days = stock_info["tracking_days"]
            
            logger.info(f"跟踪股票: {stock_code} {stock_info['stock_name']}")
            
            # 获取历史行情
            history_df = self.fetch_stock_history(stock_code, tracking_days)
            
            if history_df.empty:
                logger.warning(f"无法获取股票行情: {stock_code}")
                continue
            
            # 计算当前价格和涨跌幅
            current_price = history_df.iloc[-1]["close"]
            recommend_price = stock_info["recommend_price"]
            change_pct = (current_price - recommend_price) / recommend_price if recommend_price > 0 else 0
            
            # 构建历史数据
            history_data = []
            for _, row in history_df.iterrows():
                history_data.append({
                    "trade_date": row["trade_date"],
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                    "turnover_rate": row["turnover_rate"],
                    "change_pct": row["change_pct"]
                })
            
            # 保存跟踪数据到数据库
            today = date.today()
            for data in history_data:
                try:
                    self.db_manager.add_tracking_data(
                        stock_code=stock_code,
                        trade_date=data["trade_date"],
                        open_price=data["open"],
                        high=data["high"],
                        low=data["low"],
                        close=data["close"],
                        volume=data["volume"],
                        turnover_rate=data["turnover_rate"],
                        change_pct=data["change_pct"],
                        target_date=today
                    )
                except Exception as e:
                    logger.warning(f"保存跟踪数据失败 {stock_code} {data['trade_date']}: {e}")
            
            # 构建跟踪信息
            tracking_info = StockTrackingInfo(
                stock_code=stock_code,
                stock_name=stock_info["stock_name"],
                is_watchlist=stock_info["is_watchlist"],
                recommend_date=stock_info["recommend_date"],
                recommend_price=recommend_price,
                current_price=current_price,
                change_pct=change_pct,
                tracking_days=tracking_days,
                history_data=history_data
            )
            
            results.append(tracking_info)
        
        return results
    
    def generate_report(self, tracking_results: list) -> str:
        """生成跟踪报告"""
        if not tracking_results:
            return "暂无跟踪股票"
        
        lines = [
            f"📊 推荐股票跟踪报告 ({date.today()})",
            "",
        ]
        
        # 分离推荐股票和特别关注股票
        recommendations = [r for r in tracking_results if not r.is_watchlist]
        watchlist = [r for r in tracking_results if r.is_watchlist]
        
        # 推荐股票部分
        if recommendations:
            lines.extend([
                "═" * 40,
                "【推荐股票】",
                "═" * 40,
                ""
            ])
            
            for info in recommendations:
                lines.extend([
                    f"【{info.stock_code}】{info.stock_name}",
                    f"推荐日期：{info.recommend_date}",
                    f"推荐价格：{info.recommend_price:.2f}",
                    f"当前价格：{info.current_price:.2f}",
                    f"累计涨跌：{info.change_pct:+.2%}",
                    "",
                    f"{info.tracking_days}日行情：",
                    "日期        开盘    最高    最低    收盘    成交量    换手率"
                ])
                
                for data in info.history_data[-info.tracking_days:]:
                    lines.append(
                        f"{data['trade_date']}  {data['open']:6.2f}  {data['high']:6.2f}  "
                        f"{data['low']:6.2f}  {data['close']:6.2f}  {data['volume']:8.0f}  "
                        f"{data['turnover_rate']:6.2%}"
                    )
                
                lines.append("")
        
        # 特别关注股票部分
        if watchlist:
            lines.extend([
                "═" * 40,
                "【特别关注】",
                "═" * 40,
                ""
            ])
            
            for info in watchlist:
                lines.extend([
                    f"【{info.stock_code}】{info.stock_name}",
                    f"关注日期：{info.recommend_date}",
                    f"关注价格：{info.recommend_price:.2f}",
                    f"当前价格：{info.current_price:.2f}",
                    f"累计涨跌：{info.change_pct:+.2%}",
                    f"跟踪天数：{info.tracking_days}天",
                    "",
                    f"{info.tracking_days}日行情：",
                    "日期        开盘    最高    最低    收盘    成交量    换手率"
                ])
                
                for data in info.history_data[-info.tracking_days:]:
                    lines.append(
                        f"{data['trade_date']}  {data['open']:6.2f}  {data['high']:6.2f}  "
                        f"{data['low']:6.2f}  {data['close']:6.2f}  {data['volume']:8.0f}  "
                        f"{data['turnover_rate']:6.2%}"
                    )
                
                lines.append("")
        
        return "\n".join(lines)
```

- [ ] **Step 2: 在 db_manager.py 中添加跟踪数据方法**

```python
# morning/db_manager.py (在 DBManager 类中添加)

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
```

- [ ] **Step 3: 创建晚间回溯模块测试**

```python
# tests/test_stock_tracker.py
"""
晚间回溯模块测试
"""
import pytest
import tempfile
from pathlib import Path
from datetime import date
from morning.db_manager import DBManager
from morning.stock_tracker import StockTracker


class TestStockTracker:
    """股票跟踪器测试"""
    
    @pytest.fixture
    def tracker(self):
        """创建股票跟踪器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_manager = DBManager(
                str(Path(tmpdir) / "daily"),
                str(Path(tmpdir) / "global.db")
            )
            yield StockTracker(db_manager)
    
    def test_get_tracking_stocks_empty(self, tracker):
        """测试获取空跟踪列表"""
        stocks = tracker.get_tracking_stocks()
        assert len(stocks) == 0
    
    def test_get_tracking_stocks_with_recommendations(self, tracker):
        """测试获取推荐股票"""
        # 添加推荐记录
        tracker.db_manager.add_recommendation("000001", "平安银行", 10.83, "突破年线")
        
        stocks = tracker.get_tracking_stocks()
        assert len(stocks) == 1
        assert stocks[0]["stock_code"] == "000001"
        assert stocks[0]["is_watchlist"] == False
    
    def test_get_tracking_stocks_with_watchlist(self, tracker):
        """测试获取特别关注股票"""
        # 添加特别关注
        tracker.db_manager.add_watchlist("600036", "招商银行", 35.20, "价值投资")
        
        stocks = tracker.get_tracking_stocks()
        assert len(stocks) == 1
        assert stocks[0]["stock_code"] == "600036"
        assert stocks[0]["is_watchlist"] == True
    
    def test_get_tracking_stocks_dedup(self, tracker):
        """测试去重"""
        # 同时添加推荐和特别关注
        tracker.db_manager.add_recommendation("000001", "平安银行", 10.83, "突破年线")
        tracker.db_manager.add_watchlist("000001", "平安银行", 10.83, "突破年线")
        
        stocks = tracker.get_tracking_stocks()
        assert len(stocks) == 1
    
    def test_generate_report_empty(self, tracker):
        """测试生成空报告"""
        report = tracker.generate_report([])
        assert "暂无跟踪股票" in report
    
    def test_generate_report_with_data(self, tracker):
        """测试生成报告"""
        from morning.stock_tracker import StockTrackingInfo
        
        info = StockTrackingInfo(
            stock_code="000001",
            stock_name="平安银行",
            is_watchlist=False,
            recommend_date=date.today(),
            recommend_price=10.83,
            current_price=11.13,
            change_pct=0.028,
            tracking_days=5,
            history_data=[
                {"trade_date": "2026-06-05", "open": 10.83, "high": 10.98, "low": 10.75, "close": 10.90, "volume": 123456, "turnover_rate": 0.0185, "change_pct": 0.0065},
                {"trade_date": "2026-06-06", "open": 10.90, "high": 11.05, "low": 10.88, "close": 11.00, "volume": 134567, "turnover_rate": 0.0192, "change_pct": 0.0092}
            ]
        )
        
        report = tracker.generate_report([info])
        assert "000001" in report
        assert "平安银行" in report
        assert "+2.80%" in report
```

- [ ] **Step 4: 运行测试验证**

```bash
pytest tests/test_stock_tracker.py -v
```

- [ ] **Step 5: 提交代码**

```bash
git add morning/stock_tracker.py morning/db_manager.py tests/test_stock_tracker.py
git commit -m "feat: add stock tracker module for evening review"
```

---

## Task 7: 命令行接口 (run_morning.py)

**Files:**
- Modify: `run_morning.py`

- [ ] **Step 1: 扩展命令行接口支持新功能**

```python
# run_morning.py (新增部分)

def setup_parser():
    """设置命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="📰 新闻晨报系统 — 抓取财经新闻 → Claude 分析 → 钉钉推送",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python run_morning.py                   完整晨报
    python run_morning.py --dry-run         预览不推送
    python run_morning.py --anomaly         异动监控
    python run_morning.py --track           晚间回溯
    python run_morning.py --watch list      查看关注列表
    python run_morning.py --trade log       查看操作日志
        """,
    )
    
    # 晨报流程
    parser.add_argument("--fetch", action="store_true", help="仅测试新闻抓取")
    parser.add_argument("--analyze", action="store_true", help="测试抓取 + 分析")
    parser.add_argument("--send", action="store_true", help="测试完整流程并推送钉钉")
    parser.add_argument("--dry-run", action="store_true", help="干运行：不推送")
    
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
    
    # 通用选项
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志输出")
    
    return parser


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
```

- [ ] **Step 2: 更新 main 函数**

```python
# run_morning.py (更新 main 函数)

def main():
    parser = setup_parser()
    args = parser.parse_args()
    
    # 初始化
    setup_logging(args.verbose)
    load_config()
    config = get_config()
    
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
        cmd_full(args.verbose, db_manager)
```

- [ ] **Step 3: 提交代码**

```bash
git add run_morning.py
git commit -m "feat: add command line interface for new features"
```

---

## Task 8: 集成测试和打包

**Files:**
- Create: `tests/test_integration.py`
- Create: `morning.spec` (PyInstaller 配置)

- [ ] **Step 1: 创建集成测试**

```python
# tests/test_integration.py
"""
集成测试
"""
import pytest
import tempfile
from pathlib import Path
from morning.db_manager import DBManager
from morning.watchlist_manager import WatchlistManager
from morning.trade_journal import TradeJournal
from morning.stock_tracker import StockTracker
from morning.anomaly_monitor import AnomalyMonitor


class TestIntegration:
    """集成测试"""
    
    @pytest.fixture
    def setup(self):
        """设置测试环境"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_manager = DBManager(
                str(Path(tmpdir) / "daily"),
                str(Path(tmpdir) / "global.db")
            )
            yield db_manager
    
    def test_full_workflow(self, setup):
        """测试完整工作流程"""
        db_manager = setup
        
        # 1. 添加推荐记录
        db_manager.add_recommendation("000001", "平安银行", 10.83, "突破年线")
        
        # 2. 添加特别关注
        watchlist_manager = WatchlistManager(db_manager)
        watchlist_manager.add("600036", "招商银行", 35.20, "价值投资", "中线")
        
        # 3. 记录操作
        journal = TradeJournal(db_manager)
        journal.record_buy("000001", "平安银行", 10.83, 1000, "突破年线", "自信", ["技术面"])
        
        # 4. 验证数据
        recommendations = db_manager.get_recommendations(days=1)
        assert len(recommendations) == 1
        
        watchlist = db_manager.get_watchlist()
        assert len(watchlist) == 1
        
        records = journal.get_records(days=1)
        assert len(records) == 1
        
        # 5. 生成报告
        report = journal.generate_review_report(days=1)
        assert "操作复盘报告" in report
    
    def test_database_operations(self, setup):
        """测试数据库操作"""
        db_manager = setup
        
        # 测试备份
        with tempfile.TemporaryDirectory() as backup_dir:
            db_manager.backup(backup_dir)
            assert len(list(Path(backup_dir).glob("*.db"))) > 0
        
        # 测试状态
        status = db_manager.get_status()
        assert "daily_db_count" in status
    
    def test_anomaly_monitor_integration(self, setup):
        """测试异动监控集成"""
        monitor = AnomalyMonitor({"push_threshold": 60})
        result = monitor.run()
        
        assert 0 <= result.total_score <= 100
        assert isinstance(result.should_push, bool)
```

- [ ] **Step 2: 运行集成测试**

```bash
pytest tests/test_integration.py -v
```

- [ ] **Step 3: 创建 PyInstaller 配置**

```python
# morning.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['run_morning.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.yaml', '.'),
        ('morning/*.py', 'morning'),
    ],
    hiddenimports=[
        'morning.db_manager',
        'morning.anomaly_monitor',
        'morning.stock_tracker',
        'morning.watchlist_manager',
        'morning.trade_journal',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='morning',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

- [ ] **Step 4: 测试打包**

```bash
pyinstaller morning.spec
```

- [ ] **Step 5: 提交代码**

```bash
git add tests/test_integration.py morning.spec
git commit -m "feat: add integration tests and PyInstaller configuration"
```

---

## 完成检查清单

- [ ] 所有测试通过: `pytest tests/ -v`
- [ ] 代码无语法错误: `python -m py_compile morning/*.py`
- [ ] 配置文件正确: `config.yaml` 包含所有新配置项
- [ ] 命令行接口完整: `python run_morning.py --help` 显示所有命令
- [ ] 打包成功: `pyinstaller morning.spec` 生成可执行文件
- [ ] 文档完整: README.md 包含使用说明
