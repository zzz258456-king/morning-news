"""Celery 异步任务定义。"""

import json

from app.celery_app import celery_app
from app.database import SessionLocal
from app.db_models import PPTJob
from app.services.ppt_generator import generate_ppt_for_project


@celery_app.task(bind=True, max_retries=3)
def render_ppt_task(self, project_id: str, config_dict: dict):
    """异步渲染 PPT 任务。

    任务执行流程：
    1. 在数据库中创建/更新 PPTJob 记录
    2. 调用生成服务渲染 PPT
    3. 更新任务状态为 completed 或 failed
    """
    db = SessionLocal()
    job = None
    try:
        # 创建任务记录
        job = PPTJob(
            project_id=project_id,
            status="running",
            input_data=json.dumps(config_dict, ensure_ascii=False),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # 执行渲染
        result = generate_ppt_for_project(project_id, config_dict)

        # 更新成功状态
        job.status = "completed"
        job.output_path = result.get("output_path")
        db.commit()

        return {
            "job_id": job.id,
            "project_id": project_id,
            "status": "completed",
            "output_path": result.get("output_path"),
            "message": result.get("message", "PPT 已生成"),
        }
    except Exception as exc:
        # 更新失败状态
        if job is not None:
            job.status = "failed"
            job.error_message = str(exc)
            db.commit()

        # 重试机制
        raise self.retry(exc=exc, countdown=10)
    finally:
        db.close()
