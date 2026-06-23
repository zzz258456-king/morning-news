import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.store import save_project, load_project, get_project_path
from app.services.outline_parser import parse_outline

router = APIRouter()


@router.post("/{project_id}/outline")
async def upload_outline(
    project_id: str,
    text: str = Form(""),
    file: UploadFile = File(None),
):
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project_dir = get_project_path(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    content_text = text
    uploaded_filename = None

    if file:
        uploaded_filename = file.filename
        file_path = project_dir / (uploaded_filename or "uploaded")
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # 尝试解析文件
        try:
            outline_pages = parse_outline(file_path)
            project["outline"] = outline_pages
            # 用第一页标题作为项目标题
            if outline_pages:
                project["title"] = outline_pages[0]["title"]
            save_project(project_id, project)
            return {
                "project_id": project_id,
                "outline": outline_pages,
                "source_file": uploaded_filename,
            }
        except Exception as e:
            return {
                "project_id": project_id,
                "outline": [],
                "source_file": uploaded_filename,
                "error": f"文件解析失败：{str(e)}，请使用文本输入",
            }

    if not content_text.strip():
        raise HTTPException(status_code=400, detail="请提供文本或上传文件")

    outline_pages = parse_outline_text(content_text)
    project["outline"] = outline_pages
    if outline_pages:
        project["title"] = outline_pages[0]["title"]
    save_project(project_id, project)

    return {
        "project_id": project_id,
        "outline": outline_pages,
    }


@router.get("/{project_id}/outline")
def get_outline(project_id: str):
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"project_id": project_id, "outline": project.get("outline", [])}


def parse_outline_text(text: str) -> list:
    """简易大纲解析：按行提取标题"""
    pages = []
    idx = 1
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        title = line.lstrip("#").strip().lstrip("*").strip().lstrip("-").strip()
        if title:
            pages.append({
                "id": f"page_{idx}",
                "title": title,
                "content": "",
                "notes": "",
            })
            idx += 1
    return pages
