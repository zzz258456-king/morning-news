from fastapi import APIRouter, HTTPException
from app.store import load_project
from app.services.claude_service import recommend_templates, ClaudeServiceError

router = APIRouter()

BUILTIN_TEMPLATES = [
    {
        "id": "deepppt-academic",
        "name": "deepPPT 学术风",
        "colors": ["#1F3864", "#2E5EAA", "#C00000", "#FFFFFF"],
        "layout": "16:9",
        "source": "builtin",
    },
    {
        "id": "midnight-executive",
        "name": "Midnight Executive",
        "colors": ["#1E2761", "#FFFFFF", "#008DDD"],
        "layout": "16:9",
        "source": "builtin",
    },
    {
        "id": "charcoal-minimal",
        "name": "Charcoal Minimal",
        "colors": ["#36454F", "#F2F2F2"],
        "layout": "16:9",
        "source": "builtin",
    },
    {
        "id": "ocean-gradient",
        "name": "Ocean Gradient",
        "colors": ["#065A82", "#1C7293", "#FFFFFF"],
        "layout": "16:9",
        "source": "builtin",
    },
]


def _build_recommended_templates(raw: list, layout: str = "16:9") -> list[dict]:
    templates = []
    for i, item in enumerate(raw):
        colors = item.get("colors", [])
        if len(colors) < 2:
            colors = ["#1F3864", "#2E5EAA", "#FFFFFF"]
        templates.append({
            "id": f"recommended-{i}",
            "name": item.get("name", f"推荐方案 {i + 1}"),
            "colors": colors,
            "layout": layout,
            "source": "recommended",
        })
    return templates


@router.post("/{project_id}/templates")
def get_templates(project_id: str):
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"project_id": project_id, "templates": BUILTIN_TEMPLATES}


@router.post("/{project_id}/templates/refresh")
def refresh_templates(project_id: str):
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    title = project.get("title", "")
    outline = project.get("outline", [])

    try:
        raw = recommend_templates(title, outline)
        recommended = _build_recommended_templates(raw, project.get("template", {}).get("layout", "16:9"))
        # 推荐方案与内置方案混合
        templates = recommended[:2] + BUILTIN_TEMPLATES[:2]
        return {"project_id": project_id, "templates": templates}
    except ClaudeServiceError:
        # 未配置 API 时返回内置模板
        return {"project_id": project_id, "templates": BUILTIN_TEMPLATES}
