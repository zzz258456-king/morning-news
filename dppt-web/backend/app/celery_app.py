"""Celery 应用配置。"""

import os

from celery import Celery

# 默认使用内存模式，保证本地无 Redis 也能直接运行。
# 生产环境通过环境变量 CELERY_BROKER_URL 切换到 Redis。
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "memory://")
# result backend 不能直接用 memory://，使用 cache+memory://
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "cache+memory://")

# 内存模式下同步执行任务；真实 broker 模式下关闭 eager，由 worker 异步执行。
TASK_ALWAYS_EAGER = CELERY_BROKER_URL.startswith("memory://")

celery_app = Celery(
    "dppt_web",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)

celery_app.conf.update(
    result_expires=3600,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=TASK_ALWAYS_EAGER,
    task_store_eager_result=True,
)
