"""
FastAPI 应用主文件
创建应用实例，注册路由，挂载静态文件
"""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.database import init_db

logger = logging.getLogger(__name__)

# 路径
WEB_DIR = Path(__file__).parent
STATIC_DIR = WEB_DIR / "static"
TEMPLATES_DIR = WEB_DIR / "templates"


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用"""

    app = FastAPI(
        title="股票策略系统 Web 平台",
        description="量化策略研究与预警系统 Web 界面",
        version="1.0.0",
    )

    # 初始化数据库
    try:
        init_db()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error("数据库初始化失败: %s", e)

    # 注册路由
    _register_routers(app)

    # 挂载静态文件
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # 模板引擎
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR)) if TEMPLATES_DIR.exists() else None

    # 根路由
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """首页"""
        index_html = STATIC_DIR / "index.html"
        if index_html.exists():
            return index_html.read_text(encoding="utf-8")
        return HTMLResponse(
            content="<h1>股票策略系统 Web 平台</h1><p>请先创建 web/static/index.html</p>",
            status_code=200,
        )

    # 全局异常处理
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("未捕获异常: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": f"服务器内部错误: {str(exc)}"},
        )

    return app


def _register_routers(app: FastAPI) -> None:
    """注册所有路由"""
    from web.routers.morning_router import router as morning_router
    from web.routers.risk_router import router as risk_router
    from web.routers.fundamental_router import router as fundamental_router
    from web.routers.fund_flow_router import router as fund_flow_router
    from web.routers.trades_router import router as trades_router
    from web.routers.history_router import router as history_router

    # 注意：fundamental 路由中 /stock/{code}/intraday 必须在 /{code} 之前
    # 由于 fundamental_router 内部已正确排列，直接 include 即可
    app.include_router(morning_router)
    app.include_router(risk_router)
    app.include_router(fundamental_router)
    app.include_router(fund_flow_router)
    app.include_router(trades_router)
    app.include_router(history_router)

    logger.info("所有路由注册完成")


# 创建应用实例（供 uvicorn 引用）
app = create_app()
