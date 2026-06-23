import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.store import load_project, get_project_path

router = APIRouter()


@router.post("/{project_id}/slides/{page_id}/images")
def search_images(project_id: str, page_id: str):
    """搜索某页配图（MVP 返回占位候选图）"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # MVP 阶段返回通用占位图片链接
    return {
        "project_id": project_id,
        "page_id": page_id,
        "images": [
            {"id": "placeholder_1", "url": "https://via.placeholder.com/400x300?text=Image+1", "source": "search"},
            {"id": "placeholder_2", "url": "https://via.placeholder.com/400x300?text=Image+2", "source": "search"},
        ],
    }


@router.post("/{project_id}/slides/{page_id}/images/upload")
async def upload_image(project_id: str, page_id: str, file: UploadFile = File(...)):
    """上传本地图片到项目目录"""
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
            "local_path": str(image_path),
            "filename": file.filename,
            "source": "upload",
        },
    }
