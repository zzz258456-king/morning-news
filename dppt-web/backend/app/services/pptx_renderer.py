"""
DPPT Pro 渲染器封装

保留 dppt-web 原有的 render_presentation 接口，
内部将 config 转换为 DPPT Pro outline → DSL → PPTX。
"""

import hashlib
import sys
from pathlib import Path
from typing import Optional

import yaml

# 引入 DPPT Pro 包路径
dppt_pro_root = Path(__file__).resolve().parents[4] / "dppt-pro"
if str(dppt_pro_root) not in sys.path:
    sys.path.insert(0, str(dppt_pro_root))

from dppt import DpptRenderer, loads_dppt  # noqa: E402
from scripts.outline_to_dppt import convert  # noqa: E402


LAYOUT_16_9 = (13.333, 7.5)  # inches
LAYOUT_4_3 = (10.0, 7.5)


def hex_to_rgb(hex_color: str):
    from pptx.dml.color import RGBColor
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return RGBColor(int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def get_template_colors(template: dict):
    colors = template.get("colors", ["#1F3864", "#2E5EAA", "#C00000", "#FFFFFF"])
    return [hex_to_rgb(c) for c in colors]


def get_layout_size(template: dict) -> tuple[float, float]:
    return LAYOUT_4_3 if template.get("layout") == "4:3" else LAYOUT_16_9


def _resolve_image(image: Optional[dict], project_dir: Path) -> Optional[Path]:
    if not image:
        return None
    if image.get("local_path"):
        p = Path(image["local_path"])
        if p.exists():
            return p
    if image.get("url"):
        p = Path(image["url"])
        if p.exists():
            return p
    return None


def _map_layout(slide_data: dict) -> str:
    layout = slide_data.get("layout", "title-bullets-only")
    if layout in ("title-bullets-right-image",):
        return "image-right"
    if layout in ("title-bullets-left-image",):
        return "image-left"
    if layout == "title-image-banner":
        return "image-left"
    return "content"


def _config_to_outline(config: dict, project_dir: Path) -> dict:
    """把 dppt-web 的 config 转换为 DPPT Pro outline。"""
    template = config.get("template", {})
    title = config.get("title", "未命名")
    generated = config.get("generated_slides", config.get("slides", []))

    # 主题色映射到 business 主题的三个主色
    colors = template.get("colors", ["#1F3864", "#2E5EAA", "#C00000", "#FFFFFF"])
    primary = colors[0] if colors else "#0F172A"
    secondary = colors[1] if len(colors) > 1 else "#3B82F6"
    accent = colors[2] if len(colors) > 2 else "#F59E0B"

    slides = []

    # 封面
    slides.append(
        {
            "type": "cover",
            "title": title,
            "subtitle": config.get("subtitle", "由 DPPT Web 生成"),
            "info": config.get("info", "DPPT Pro · DPPT Web"),
        }
    )

    # 目录（可选）
    if len(generated) > 3:
        slides.append(
            {
                "type": "toc",
                "title": "目录",
                "items": [s.get("title", f"第 {i+1} 页") for i, s in enumerate(generated)],
            }
        )

    # 内容页
    for slide_data in generated:
        layout = _map_layout(slide_data)
        bullets = slide_data.get("bullets", [])
        image = _resolve_image(slide_data.get("image"), project_dir)

        if layout in ("image-left", "image-right") and image:
            slide = {
                "type": "content",
                "layout": layout,
                "title": slide_data.get("title", ""),
                "image": str(image),
                "bullets": bullets,
            }
        else:
            slide = {
                "type": "content",
                "layout": "two-column",
                "title": slide_data.get("title", ""),
                "bullets": bullets,
                "highlight": {
                    "title": "关键信息",
                    "text": slide_data.get("image_prompt", "") or "",
                },
            }
        slides.append(slide)

    # 结束页
    slides.append(
        {
            "type": "closing",
            "title": config.get("closing_title", "谢谢观看"),
            "info": config.get("closing_info", "DPPT Web · 让每一份演示都足够专业"),
        }
    )

    return {
        "title": title,
        "theme": "business",
        "author": "DPPT Web",
        "description": config.get("description", ""),
        "slides": slides,
    }


def render_presentation(config: dict, output_file: Path, project_dir: Path) -> Path:
    """使用 DPPT Pro 渲染 PPTX。"""
    outline = _config_to_outline(config, project_dir)
    doc_dict = convert(outline)
    dppt_text = yaml.dump(doc_dict, allow_unicode=True, sort_keys=False, width=120)
    doc = loads_dppt(dppt_text)

    renderer = DpptRenderer(doc, enable_animation=True)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    renderer.render(str(output_file))
    return output_file
