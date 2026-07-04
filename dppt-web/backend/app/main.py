import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from contextlib import asynccontextmanager

from app.routers import projects, outline, templates, generate, images, health, jobs
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库表。"""
    from app import db_models  # noqa: F401 确保模型注册到 Base.metadata
    init_db()
    yield


app = FastAPI(title="DPPT Web API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(outline.router, prefix="/api/projects", tags=["outline"])
app.include_router(templates.router, prefix="/api/projects", tags=["templates"])
app.include_router(images.router, prefix="/api/projects", tags=["images"])
app.include_router(generate.router, prefix="/api/projects", tags=["generate"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(jobs.router, prefix="/api", tags=["jobs"])


# 生产模式：托管前端构建产物
if os.environ.get("DPPT_FRONTEND_DIST"):
    FRONTEND_DIST = Path(os.environ["DPPT_FRONTEND_DIST"])
else:
    FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    # 静态文件走 /assets/* /favicon.svg 等
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="static")
