"""PPT 生成服务：把生成逻辑从路由中抽离，便于路由和 Celery 任务复用。"""

from pathlib import Path

from app.models import GenerateRequest
from app.services.claude_service import ClaudeServiceError, generate_slide_content
from app.services.pptx_renderer import render_presentation
from app.store import get_project_path, load_project, save_project


def generate_ppt_for_project(project_id: str, config_dict: dict) -> dict:
    """为指定项目生成 PPT，返回结果字典。

    该函数不依赖 FastAPI 请求对象，可在路由和 Celery 任务中调用。
    """
    project = load_project(project_id)
    if not project:
        raise ValueError("项目不存在")

    project_dir = get_project_path(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    output_file = project_dir / "output.pptx"

    # 同步项目状态
    project["title"] = config_dict.get("title", project.get("title", ""))
    project["template"] = config_dict.get("template")
    project["slides"] = config_dict.get("slides", [])
    project["outline"] = config_dict.get("outline", project.get("outline", []))
    save_project(project_id, project)

    # 兜底：slides 为空时根据 outline 生成默认 slides
    if not project["slides"] and project.get("outline"):
        project["slides"] = [
            {
                "page_id": p["id"],
                "title": p["title"],
                "body": p.get("content", ""),
                "image": None,
                "layout": "default",
            }
            for p in project["outline"]
        ]
        save_project(project_id, project)

    try:
        # 调用 Claude 生成结构化内容
        generated = generate_slide_content(project)

        # 将生成结果合并到原始 slides 中，保留用户已选图片
        slides_by_id = {s["page_id"]: s for s in project["slides"]}
        merged_slides = []
        for g in generated.get("slides", []):
            original = slides_by_id.get(g["page_id"], {})
            merged = {
                **original,
                "page_id": g["page_id"],
                "title": g.get("title", original.get("title", "")),
                "bullets": g.get("bullets", []),
                "layout": g.get("layout", original.get("layout", "title-bullets-only")),
                "image_prompt": g.get("image_prompt", ""),
            }
            merged_slides.append(merged)

        config_for_render = {
            **config_dict,
            "generated_slides": merged_slides,
        }

        render_presentation(config_for_render, output_file, project_dir)

        project["output_path"] = str(output_file)
        project["generated_title"] = generated.get("title", project.get("title", ""))
        save_project(project_id, project)

        return {
            "project_id": project_id,
            "status": "success",
            "output_path": str(output_file),
            "message": "PPT 已生成",
        }
    except ClaudeServiceError as e:
        # API 未配置时降级为直接渲染原始大纲
        try:
            fallback_slides = [
                {
                    "page_id": s["page_id"],
                    "title": s["title"],
                    "bullets": [line for line in s.get("body", "").split("\n") if line.strip()] or [s["title"]],
                    "layout": "title-bullets-only" if not s.get("image") else "title-bullets-right-image",
                    "image": s.get("image"),
                }
                for s in project["slides"]
            ]
            render_presentation({**config_dict, "generated_slides": fallback_slides}, output_file, project_dir)
            project["output_path"] = str(output_file)
            save_project(project_id, project)
            return {
                "project_id": project_id,
                "status": "fallback",
                "output_path": str(output_file),
                "message": f"Claude 不可用，已使用原始内容生成（{e}）",
            }
        except Exception as fallback_err:
            raise RuntimeError(f"生成失败：{fallback_err}")
    except Exception as e:
        raise RuntimeError(f"生成失败：{str(e)}")


def generate_ppt_from_request(project_id: str, request: GenerateRequest) -> dict:
    """从 GenerateRequest 生成 PPT 的便捷包装。"""
    return generate_ppt_for_project(project_id, request.config.model_dump())
