"""PPT 渲染任务路由。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import PPTJob
from app.schemas import JobCreateRequest, JobListResponse, JobResponse
from app.store import load_project
from app.tasks import render_ppt_task

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=201)
def create_job(request: JobCreateRequest, db: Session = Depends(get_db)):
    """创建并提交一个 PPT 渲染异步任务。"""
    project = load_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 创建任务记录
    job = PPTJob(
        project_id=request.project_id,
        status="pending",
        input_data=request.input_data,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 提交 Celery 任务
    # 内存 broker（本地无 Redis）时 task_always_eager=True，会同步执行
    # 真实 Redis broker 时由 worker 异步消费
    render_ppt_task.delay(request.project_id, project)

    # 同步执行后刷新 job 状态
    db.refresh(job)
    return job


@router.get("", response_model=JobListResponse)
def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """列出 PPT 渲染任务。"""
    total = db.query(PPTJob).count()
    items = db.query(PPTJob).order_by(PPTJob.created_at.desc()).offset(offset).limit(limit).all()
    return JobListResponse(items=items, total=total)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """获取单个 PPT 渲染任务详情。"""
    job = db.query(PPTJob).filter(PPTJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job
