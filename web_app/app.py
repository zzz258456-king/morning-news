"""
FastAPI 主应用
集成爬虫、数据分析、可视化等所有功能
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from config import WEB_TITLE, WEB_DESCRIPTION, WEB_VERSION

from .routes.crawler_routes import router as crawler_router
from .routes.analysis_routes import router as analysis_router
from .routes.dashboard_routes import router as dashboard_router

logger = logging.getLogger(__name__)

# 模板与静态文件路径
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Web应用启动中...")
    yield
    logger.info("Web应用已关闭")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用"""
    app = FastAPI(
        title=WEB_TITLE,
        description=WEB_DESCRIPTION,
        version=WEB_VERSION,
        lifespan=lifespan,
    )

    # 挂载静态文件
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # 注册路由
    app.include_router(crawler_router, prefix="/api/crawler", tags=["爬虫"])
    app.include_router(analysis_router, prefix="/api/analysis", tags=["数据分析"])
    app.include_router(dashboard_router, prefix="/api/dashboard", tags=["仪表盘"])

    # 页面路由
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index(request: Request):
        return templates.TemplateResponse("index.html", {
            "request": request,
            "title": WEB_TITLE,
        })

    @app.get("/crawler", response_class=HTMLResponse, include_in_schema=False)
    async def crawler_page(request: Request):
        return templates.TemplateResponse("crawler.html", {
            "request": request,
            "title": "爬虫管理",
        })

    @app.get("/analysis", response_class=HTMLResponse, include_in_schema=False)
    async def analysis_page(request: Request):
        return templates.TemplateResponse("analysis.html", {
            "request": request,
            "title": "数据分析",
        })

    @app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_page(request: Request):
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "title": "数据仪表盘",
        })

    @app.get("/health", tags=["系统"])
    async def health_check():
        return {"status": "ok", "version": WEB_VERSION}

    return app
