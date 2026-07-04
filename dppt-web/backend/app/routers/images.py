import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

import requests
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from app.store import load_project, get_project_path

router = APIRouter()

UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")
UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"
PLACEHOLDER_URL = "https://via.placeholder.com/400x300?text={text}"


def _placeholder_images(query: str, count: int = 4) -> list[dict]:
    return [
        {
            "id": f"placeholder_{i}",
            "url": PLACEHOLDER_URL.format(text=f"Image+{i+1}"),
            "thumb": PLACEHOLDER_URL.format(text=f"Thumb+{i+1}"),
            "source": "placeholder",
        }
        for i in range(count)
    ]


def _search_unsplash(query: str, count: int = 6) -> list[dict]:
    if not UNSPLASH_ACCESS_KEY:
        return []
    try:
        response = requests.get(
            UNSPLASH_SEARCH_URL,
            params={"query": query, "per_page": count, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        results = []
        for photo in data.get("results", []):
            results.append({
                "id": photo["id"],
                "url": photo["urls"]["regular"],
                "thumb": photo["urls"]["small"],
                "source": "unsplash",
                "author": photo["user"]["name"],
                "link": photo["links"]["html"],
            })
        return results
    except Exception:
        return []


@router.post("/{project_id}/slides/{page_id}/images")
def search_images(project_id: str, page_id: str, query: Optional[str] = Form(None)):
    """搜索某页配图。优先 Unsplash，无 key 或失败时返回占位图。"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 如果没有关键词，从页面标题/body 提取
    if not query:
        for slide in project.get("slides", []):
            if slide.get("page_id") == page_id:
                query = f"{slide.get('title', '')} {slide.get('body', '')}".strip()
                break
    if not query:
        query = "presentation"

    search_query = query[:100]
    images = _search_unsplash(search_query)
    if not images:
        images = _placeholder_images(search_query)

    return {
        "project_id": project_id,
        "page_id": page_id,
        "query": search_query,
        "images": images,
    }


@router.post("/{project_id}/slides/{page_id}/images/upload")
async def upload_image(project_id: str, page_id: str, file: UploadFile = File(...)):
    """上传本地图片到项目目录。"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project_dir = get_project_path(project_id)
    images_dir = project_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename).suffix or ".png"
    image_id = f"{uuid.uuid4().hex}{ext}"
    image_path = images_dir / image_id

    with open(image_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {
        "project_id": project_id,
        "page_id": page_id,
        "image": {
            "id": image_id,
            "url": str(image_path),
            "local_path": str(image_path),
            "filename": file.filename,
            "source": "upload",
        },
    }
