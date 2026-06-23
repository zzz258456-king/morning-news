import json
from pathlib import Path
from typing import Optional

WORK_DIR = Path("D:/缓存区/dppt-web")
WORK_DIR.mkdir(parents=True, exist_ok=True)


def get_project_path(project_id: str) -> Path:
    return WORK_DIR / project_id


def save_project(project_id: str, data: dict):
    project_dir = get_project_path(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    with open(project_dir / "project.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_project(project_id: str) -> Optional[dict]:
    project_file = get_project_path(project_id) / "project.json"
    if not project_file.exists():
        return None
    with open(project_file, "r", encoding="utf-8") as f:
        return json.load(f)


def list_projects() -> list:
    projects = []
    for d in WORK_DIR.iterdir():
        if d.is_dir():
            data = load_project(d.name)
            if data:
                projects.append({"id": data["id"], "title": data.get("title", "")})
    return projects
