"""
爬虫 API 路由
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from crawler import WebScraper, TaskScheduler

logger = logging.getLogger(__name__)

router = APIRouter()
scraper = WebScraper()
scheduler = TaskScheduler()


class CrawlRequest(BaseModel):
    """爬取请求"""
    url: str
    extract_tables: bool = False
    extract_articles: bool = False


class BatchCrawlRequest(BaseModel):
    """批量爬取请求"""
    urls: List[str]
    max_workers: int = 5


class ScheduleRequest(BaseModel):
    """定时任务请求"""
    name: str
    url: str
    interval: str  # "5m", "1h", "daily@09:00"


@router.post("/crawl")
async def crawl_url(req: CrawlRequest):
    """爬取指定URL"""
    try:
        result = scraper.crawl(req.url)
        if not result.success:
            raise HTTPException(status_code=500, detail="爬取失败")
        response = {
            "success": True,
            "title": result.title,
            "url": result.url,
            "content_length": len(result.content),
            "crawled_at": result.crawled_at,
        }
        if req.extract_tables:
            df = scraper.extract_tables(result.html)
            if df is not None:
                response["tables"] = df.fillna("").to_dict(orient="records")
        if req.extract_articles:
            articles = scraper.extract_articles(result.html)
            response["articles"] = articles
        return response
    except Exception as e:
        logger.exception("爬取异常")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-crawl")
async def batch_crawl(req: BatchCrawlRequest):
    """批量爬取多个URL"""
    try:
        results = scraper.batch_crawl(req.urls, max_workers=req.max_workers)
        return {
            "total": len(results),
            "success_count": sum(1 for r in results if r.success),
            "fail_count": sum(1 for r in results if not r.success),
            "results": [
                {
                    "url": r.url,
                    "success": r.success,
                    "title": r.title,
                    "crawled_at": r.crawled_at,
                }
                for r in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/saved-files")
async def list_saved_files():
    """列出已保存的爬取文件"""
    from config import RAW_DATA_DIR
    files = []
    for f in sorted(RAW_DATA_DIR.glob("*.json"), reverse=True)[:50]:
        files.append({
            "name": f.name,
            "size": f.stat().st_size,
            "modified": f.stat().st_mtime,
        })
    return {"files": files}


@router.post("/export-csv")
async def export_to_csv(url: str):
    """爬取并导出为CSV"""
    path = scraper.crawl_and_export_csv(url)
    if path is None:
        raise HTTPException(status_code=400, detail="未找到表格数据")
    return {"file_path": path}
