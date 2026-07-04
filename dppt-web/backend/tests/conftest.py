"""pytest 共享 fixtures。"""

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.db_models import PPTJob
from app.main import app


@pytest.fixture
def client():
    """提供已触发 lifespan 的 TestClient。"""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session():
    """提供数据库会话，并在测试结束后回滚。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clean_ppt_jobs(db_session):
    """每个测试前清空 ppt_jobs 表，保证测试隔离。"""
    from app.database import init_db

    init_db()  # 确保表已创建（ lifespan 触发前 fixture 可能先执行）
    db_session.query(PPTJob).delete()
    db_session.commit()
    yield
    db_session.query(PPTJob).delete()
    db_session.commit()
