"""Celery 异步任务测试。"""

from unittest.mock import patch

from app.celery_app import celery_app
from app.database import SessionLocal
from app.db_models import PPTJob
from app.store import save_project
from app.tasks import render_ppt_task


def test_render_ppt_task_updates_job_status():
    """验证 Celery 任务执行后会更新数据库中的 job 状态。"""
    project_id = "celery-test-proj"
    save_project(project_id, {
        "id": project_id,
        "title": "Celery 测试项目",
        "outline": [],
        "template": None,
        "slides": [],
        "output_path": None,
    })

    with patch("app.tasks.generate_ppt_for_project") as mock_generate:
        mock_generate.return_value = {
            "status": "success",
            "output_path": "D:/缓存区/dppt-web/test/output.pptx",
            "message": "PPT 已生成",
        }

        # 内存 broker + eager 模式会同步执行任务
        result = render_ppt_task.delay(project_id, {})

    assert result.successful()
    assert result.result["status"] == "completed"
    assert result.result["output_path"] == "D:/缓存区/dppt-web/test/output.pptx"

    # 验证数据库状态
    db = SessionLocal()
    try:
        job = db.query(PPTJob).filter(PPTJob.project_id == project_id).first()
        assert job is not None
        assert job.status == "completed"
        assert job.output_path == "D:/缓存区/dppt-web/test/output.pptx"
    finally:
        db.close()


def test_celery_eager_mode_configuration():
    """验证本地测试环境使用 eager 模式，无需 Redis。"""
    assert celery_app.conf.broker_url.startswith("memory://")
    assert celery_app.conf.task_always_eager is True
