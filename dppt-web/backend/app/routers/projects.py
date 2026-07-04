import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.store import save_project, load_project

router = APIRouter()


class ProjectConfig(BaseModel):
    id: str
    title: str = ""
    outline: list = []
    template: dict | None = None
    slides: list = []
    output_path: str | None = None


@router.post("")
def create_project():
    project_id = str(uuid.uuid4())
    project_data = {
        "id": project_id,
        "title": "",
        "outline": [],
        "template": None,
        "slides": [],
        "output_path": None,
    }
    save_project(project_id, project_data)
    return {"id": project_id, "message": "项目创建成功"}


@router.get("/{project_id}")
def get_project(project_id: str):
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.patch("/{project_id}")
def update_project(project_id: str, config: ProjectConfig):
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = config.model_dump()
    save_project(project_id, data)
    return {"status": "saved", "id": project_id}
