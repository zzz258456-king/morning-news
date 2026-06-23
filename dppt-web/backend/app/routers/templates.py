import random
from fastapi import APIRouter

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

SEARCH_TEMPLATES = [
    {
        "id": "search-modern-tech",
        "name": "Modern Tech",
        "colors": ["#0F172A", "#3B82F6", "#10B981"],
        "layout": "16:9",
        "source": "search",
    },
    {
        "id": "search-warm-neutral",
        "name": "Warm Neutral",
        "colors": ["#F5F5F4", "#78716C", "#EA580C"],
        "layout": "16:9",
        "source": "search",
    },
]


def get_template_options(refresh: bool = False):
    if refresh:
        # 模拟搜索返回新方案
        return random.sample(SEARCH_TEMPLATES, min(2, len(SEARCH_TEMPLATES))) + random.sample(BUILTIN_TEMPLATES, 2)
    return BUILTIN_TEMPLATES[:4]


@router.post("/{project_id}/templates")
def get_templates(project_id: str):
    return {"project_id": project_id, "templates": get_template_options(False)}


@router.post("/{project_id}/templates/refresh")
def refresh_templates(project_id: str):
    return {"project_id": project_id, "templates": get_template_options(True)}
