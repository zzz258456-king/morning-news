"""
仪表盘 API 路由
提供综合数据概览和状态监控
"""
import logging
from pathlib import Path

from fastapi import APIRouter

from crawler import TaskScheduler
from config import RAW_DATA_DIR, PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)

router = APIRouter()
scheduler = TaskScheduler()


@router.get("/overview")
async def dashboard_overview():
    """获取系统总览数据"""
    overview = {
        "system": {
            "name": "全能数据平台",
            "version": "1.0.0",
            "status": "running",
        },
        "data_stats": {
            "raw_files": count_files(RAW_DATA_DIR),
            "processed_files": count_files(PROCESSED_DATA_DIR),
        },
        "scheduler_status": scheduler.get_status(),
    }

    # 获取最近的爬取数据
    recent = get_recent_crawl_data()
    if recent:
        overview["recent_data"] = recent

    return overview


@router.get("/recent-crawls")
async def recent_crawls(limit: int = 10):
    """获取最近的爬取记录"""
    files = sorted(RAW_DATA_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]
    results = []
    for f in files:
        try:
            import json
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "url": data.get("url", ""),
                "title": data.get("title", ""),
                "success": data.get("success", False),
                "crawled_at": data.get("crawled_at", ""),
                "file": f.name,
            })
        except Exception:
            pass
    return {"results": results}


def count_files(directory: Path) -> dict:
    """统计目录中的文件"""
    if not directory.exists():
        return {"total": 0}
    total = len(list(directory.iterdir()))
    return {"total": total, "path": str(directory)}


def get_recent_crawl_data() -> list:
    """获取最近的爬取数据摘要"""
    files = sorted(RAW_DATA_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)[:5]
    results = []
    for f in files:
        try:
            import json
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "url": data.get("url", "")[:50],
                "title": data.get("title", "")[:30],
                "success": data.get("success", False),
                "time": data.get("crawled_at", ""),
            })
        except Exception:
            pass
    return results
