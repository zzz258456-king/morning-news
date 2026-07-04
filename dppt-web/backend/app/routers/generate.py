"""PPT 生成路由。"""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models import GenerateRequest
from app.services.ppt_generator import generate_ppt_from_request
from app.store import load_project, get_project_path

router = APIRouter()


@router.post("/{project_id}/generate")
def generate_ppt(project_id: str, request: GenerateRequest):
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    try:
        return generate_ppt_from_request(project_id, request)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/download")
def download_ppt(project_id: str):
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    output_file = Path(project.get("output_path", get_project_path(project_id) / "output.pptx"))
    if not output_file.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        path=str(output_file),
        filename=f"{project.get('title', 'output')}.pptx",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
