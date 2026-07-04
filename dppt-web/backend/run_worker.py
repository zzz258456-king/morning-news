"""Celery Worker 启动入口。"""

from app.celery_app import celery_app

if __name__ == "__main__":
    celery_app.start()
