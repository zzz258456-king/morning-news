"""数据库配置模块。

Phase 1 使用 SQLite（文件位于 D:/缓存区/dppt-web/dppt_web.db），
后续切换到 PostgreSQL 时只需修改 DATABASE_URL。
"""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 数据库文件统一放到 D 盘缓存区
DB_DIR = Path("D:/缓存区/dppt-web")
DB_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_PATH = DB_DIR / "dppt_web.db"

# 后续切换到 PostgreSQL 时改为：
# DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:pass@localhost/dppt_web")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{SQLITE_PATH}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI Depends 使用的数据库会话生成器。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """创建所有表。通常在应用启动时调用一次。"""
    Base.metadata.create_all(bind=engine)
