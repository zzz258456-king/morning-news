"""
大纲到 DPPT DSL 转换器

接收简化的大纲 YAML，自动套用布局模板生成 .dppt DSL。
这样 AI 只需生成大纲，不需要手写每个元素的 bounds。

用法：
    python scripts/outline_to_dppt.py examples/outline.yaml output.dppt
"""

import argparse
import os
import sys
from pathlib import Path

import yaml

# 让脚本可以从 scripts/ 目录直接运行并导入 dppt 包
sys.path.insert(0, str(Path(__file__).parent.parent))


THEME_PATH = os.path.join(os.path.dirname(__file__), "..", "templates", "themes")

# 16:9 画布尺寸（英寸）
PAGE_W = 13.333
PAGE_H = 7.5
MARGIN = {"left": 0.8, "top": 0.6, "right": 0.8, "bottom": 0.6}


def load_theme(name: str):
    path = os.path.join(THEME_PATH, f"{name}.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"主题不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def make_text(text: str, style: str, bounds: dict, **kwargs):
    return {"type": "text", "text": text, "style": style, "bounds": bounds, **kwargs}


def make_shape(shape_type: str, bounds: dict, fill: dict = None, border: dict = None, shadow: dict = None, **kwargs):
    elem = {"type": "shape", "shape_type": shape_type, "bounds": bounds, **kwargs}
    if fill:
        elem["fill"] = fill
    if border:
        elem["border"] = border
    if shadow:
        elem["shadow"] = shadow
    return elem


def make_icon(icon_name: str, bounds: dict, color: str = "$primary", **kwargs):
    return {"type": "icon", "icon_name": icon_name, "color": color, "bounds": bounds, **kwargs}


def make_bullet_text(items: list, style: str = "$body", bounds: dict = None, symbol: str = "·") -> dict:
    text = "\n".join(f"{symbol} {item}" for item in items)
    return make_text(text, style, bounds or {"x": 0.8, "y": 1.8, "width": 11.7, "height": 4.5})


def _card_bounds(index: int, count: int, start_y: float = 1.8, height: float = 4.2, gap: float = 0.3):
    """计算等宽卡片的 bounds。"""
    usable_w = PAGE_W - MARGIN["left"] - MARGIN["right"]
    total_gap = gap * (count - 1)
    card_w = (usable_w - total_gap) / count
    x = MARGIN["left"] + index * (card_w + gap)
    return {"x": x, "y": start_y, "width": card_w, "height": height}


def _title_element(title: str, bounds: dict = None):
    return make_text(title or "", "$h2", bounds or {"x": MARGIN["left"], "y": MARGIN["top"], "width": PAGE_W - MARGIN["left"] - MARGIN["right"], "height": 0.9})


# ---------------------------------------------------------------------------
# 布局 builders
# ---------------------------------------------------------------------------


def build_cover(slide: dict) -> dict:
    return {
        "type": "cover",
        "layout": "cover",
        "title": slide.get("title"),
        "subtitle": slide.get("subtitle"),
        "background": {"type": "solid", "color": "$background"},
        "elements": [
            make_shape("rect", {"x": 0, "y": 0, "width": PAGE_W, "height": 0.15}, fill={"type": "solid", "color": "$secondary"}),
            make_shape(
                "rounded_rect",
                {"x": 0.6, "y": 1, "width": 12.1, "height": 5.5},
                fill={"type": "solid", "color": "$surface"},
                rounded_radius=0.2,
                shadow={"color": "#000000", "blur": 20, "offset": [0, 4], "alpha": 0.08},
            ),
            make_text(slide.get("title", ""), "$h1", {"x": 1.2, "y": 2.2, "width": 10.9, "height": 1.3}),
            make_text(slide.get("subtitle", ""), "$h3", {"x": 1.2, "y": 3.6, "width": 10.9, "height": 0.7}),
            make_text(slide.get("info", ""), "$caption", {"x": 1.2, "y": 5.2, "width": 10.9, "height": 0.5}),
        ],
    }


def build_toc(slide: dict) -> dict:
    items = slide.get("items", [])
    numbered = "\n".join(f"{i+1:02d}  {item}" for i, item in enumerate(items))
    return {
        "type": "toc",
        "layout": "toc",
        "title": slide.get("title", "目录"),
        "background": {"type": "solid", "color": "$background"},
        "elements": [
            _title_element(slide.get("title", "目录")),
            make_text(numbered, "$body", {"x": 1.5, "y": 1.8, "width": 10, "height": 4}),
        ],
    }


def build_title_only(slide: dict) -> dict:
    """章节分隔页：大标题 + 简短副标题 + 装饰元素。"""
    title = slide.get("title", "")
    subtitle = slide.get("subtitle", "")
    number = slide.get("number", "")
    display_title = f"{number}  {title}" if number else title
    return {
        "type": "section",
        "layout": "title-only",
        "title": title,
        "background": {"type": "solid", "color": "$primary"},
        "elements": [
            make_shape("rect", {"x": 0, "y": 0, "width": PAGE_W, "height": PAGE_H}, fill={"type": "solid", "color": "$primary"}),
            make_shape("rounded_rect", {"x": 0.8, "y": 2.2, "width": 0.4, "height": 3}, fill={"type": "solid", "color": "$accent"}, rounded_radius=0.1),
            make_text(display_title, {"font_family": "$heading", "font_size": "48pt", "color": "#FFFFFF", "bold": True}, {"x": 1.5, "y": 2.6, "width": 11, "height": 1.4}),
            make_text(subtitle, {"font_family": "$body", "font_size": "22pt", "color": "#CBD5E1"}, {"x": 1.5, "y": 4.2, "width": 11, "height": 0.8}),
        ],
    }


def build_two_column(slide: dict) -> dict:
    """双栏内容：左侧要点，右侧高亮卡片。"""
    bullets = slide.get("bullets", [])
    highlight = slide.get("highlight", {})
    elements = [
        _title_element(slide.get("title", "")),
        make_bullet_text(bullets, "$body", {"x": 0.8, "y": 1.8, "width": 6, "height": 4}),
        make_shape(
            "rounded_rect",
            {"x": 7.2, "y": 1.8, "width": 5.2, "height": 4},
            fill={"type": "solid", "color": "$surface"},
            border={"width": 1, "color": "#E2E8F0"},
            rounded_radius=0.2,
        ),
    ]
    if highlight:
        right_text = f"{highlight.get('title', '')}\n{highlight.get('text', '')}"
        elements.append(make_text(right_text, "$body", {"x": 7.6, "y": 2.2, "width": 4.4, "height": 3}))
    return {
        "type": "content",
        "layout": "two-column",
        "title": slide.get("title"),
        "background": {"type": "solid", "color": "$background"},
        "elements": elements,
    }


def build_three_column(slide: dict) -> dict:
    """三栏卡片：每列一个可选图标 + 标题 + 要点。"""
    columns = slide.get("columns", slide.get("cards", []))
    if not columns:
        # 退化为双栏
        return build_two_column(slide)

    elements = [_title_element(slide.get("title", ""))]
    for idx, col in enumerate(columns[:3]):
        b = _card_bounds(idx, 3, start_y=1.8, height=4.5, gap=0.3)
        elements.append(
            make_shape(
                "rounded_rect",
                b,
                fill={"type": "solid", "color": "$surface"},
                border={"width": 1, "color": "#E2E8F0"},
                rounded_radius=0.15,
            )
        )
        title = col.get("title", col.get("heading", ""))
        items = col.get("bullets", col.get("items", []))
        icon_name = col.get("icon")

        inner_x = b["x"] + 0.2
        inner_y = b["y"] + 0.25
        inner_w = b["width"] - 0.4

        if icon_name:
            icon_size = 0.45
            icon_x = inner_x + (inner_w - icon_size) / 2
            elements.append({
                "type": "icon",
                "icon_name": icon_name,
                "color": "$secondary",
                "bounds": {"x": icon_x, "y": inner_y, "width": icon_size, "height": icon_size},
            })
            inner_y += icon_size + 0.15

        text = (title + "\n" + "\n".join(f"· {item}" for item in items)) if items else title
        elements.append(make_text(text, "$body", {"x": inner_x, "y": inner_y, "width": inner_w, "height": b["height"] - (inner_y - b["y"]) - 0.3}))

    return {
        "type": "content",
        "layout": "three-column",
        "title": slide.get("title"),
        "background": {"type": "solid", "color": "$background"},
        "elements": elements,
    }


def build_image_text(slide: dict, side: str = "left") -> dict:
    """图文混排：一侧图片，另一侧文字。"""
    image_src = slide.get("image", slide.get("image_src", ""))
    bullets = slide.get("bullets", [])
    text_w = 5.8
    img_w = 5.2
    gap = 0.5
    if side == "left":
        img_x = MARGIN["left"]
        text_x = img_x + img_w + gap
    else:
        text_x = MARGIN["left"]
        img_x = text_x + text_w + gap

    elements = [_title_element(slide.get("title", ""))]
    if image_src:
        elements.append({
            "type": "image",
            "src": image_src,
            "bounds": {"x": img_x, "y": 1.8, "width": img_w, "height": 4.5},
            "object_fit": "cover",
        })
    else:
        elements.append(make_shape("rounded_rect", {"x": img_x, "y": 1.8, "width": img_w, "height": 4.5}, fill={"type": "solid", "color": "#E2E8F0"}, rounded_radius=0.15))

    elements.append(make_bullet_text(bullets, "$body", {"x": text_x, "y": 1.8, "width": text_w, "height": 4.5}))
    return {
        "type": "content",
        "layout": f"image-{side}",
        "title": slide.get("title"),
        "background": {"type": "solid", "color": "$background"},
        "elements": elements,
    }


def build_timeline(slide: dict) -> dict:
    """水平时间轴：最多 4 个节点。"""
    steps = slide.get("steps", slide.get("timeline", []))[:4]
    if not steps:
        return build_two_column(slide)

    elements = [_title_element(slide.get("title", ""))]
    n = len(steps)
    usable_w = PAGE_W - MARGIN["left"] - MARGIN["right"]
    node_w = min(2.8, (usable_w - 0.5 * (n - 1)) / n)
    start_x = MARGIN["left"]
    y = 2.2

    # 时间轴线
    elements.append(make_shape("rect", {"x": start_x, "y": y + 0.35, "width": start_x + n * (node_w + 0.5) - 0.5 - start_x, "height": 0.05}, fill={"type": "solid", "color": "$secondary"}))

    for idx, step in enumerate(steps):
        x = start_x + idx * (node_w + 0.5)
        label = str(step.get("label", step.get("year", step.get("time", f"{idx+1}"))))
        desc = str(step.get("description", step.get("text", step.get("title", ""))))
        # 节点圆点
        elements.append(make_shape("ellipse", {"x": x + node_w / 2 - 0.15, "y": y + 0.2, "width": 0.3, "height": 0.3}, fill={"type": "solid", "color": "$accent"}))
        # 标签
        elements.append(make_text(label, {"font_family": "$heading", "font_size": "18pt", "color": "$primary", "bold": True}, {"x": x, "y": y - 0.6, "width": node_w, "height": 0.5}))
        # 描述
        elements.append(make_text(desc, "$body", {"x": x, "y": y + 0.7, "width": node_w, "height": 2.2}))

    return {
        "type": "content",
        "layout": "timeline",
        "title": slide.get("title"),
        "background": {"type": "solid", "color": "$background"},
        "elements": elements,
    }


def build_team(slide: dict) -> dict:
    """团队介绍：最多 4 人，头像占位 + 姓名 + 职位。"""
    members = slide.get("members", slide.get("team", []))[:4]
    if not members:
        return build_two_column(slide)

    elements = [_title_element(slide.get("title", ""))]
    n = len(members)
    usable_w = PAGE_W - MARGIN["left"] - MARGIN["right"]
    gap = 0.4
    card_w = (usable_w - gap * (n - 1)) / n
    avatar_size = min(1.4, card_w - 0.6)
    start_y = 2.0

    for idx, member in enumerate(members):
        x = MARGIN["left"] + idx * (card_w + gap)
        avatar_x = x + (card_w - avatar_size) / 2
        # 头像占位
        elements.append(make_shape("ellipse", {"x": avatar_x, "y": start_y, "width": avatar_size, "height": avatar_size}, fill={"type": "solid", "color": "$secondary"}))
        # 姓名
        elements.append(make_text(member.get("name", ""), {"font_family": "$heading", "font_size": "18pt", "color": "$primary", "bold": True, "align": "center"}, {"x": x, "y": start_y + avatar_size + 0.25, "width": card_w, "height": 0.45}))
        # 职位
        elements.append(make_text(member.get("role", member.get("title", "")), {"font_family": "$body", "font_size": "14pt", "color": "$muted", "align": "center"}, {"x": x, "y": start_y + avatar_size + 0.75, "width": card_w, "height": 0.6}))

    return {
        "type": "content",
        "layout": "team",
        "title": slide.get("title"),
        "background": {"type": "solid", "color": "$background"},
        "elements": elements,
    }


def build_quote(slide: dict) -> dict:
    """引用页：大引号 + 引用文字 + 来源。"""
    quote = slide.get("quote", slide.get("text", ""))
    source = slide.get("source", slide.get("author", ""))
    return {
        "type": "content",
        "layout": "quote",
        "title": slide.get("title"),
        "background": {"type": "solid", "color": "$background"},
        "elements": [
            make_text("“", {"font_family": "$heading", "font_size": "96pt", "color": "$primary", "bold": True}, {"x": 1, "y": 1.2, "width": 1.5, "height": 1.2}),
            make_text(quote, {"font_family": "$heading", "font_size": "28pt", "color": "$primary"}, {"x": 1.2, "y": 2.5, "width": 10.9, "height": 2.5}),
            make_text(f"—— {source}" if source else "", {"font_family": "$body", "font_size": "18pt", "color": "$muted", "align": "right"}, {"x": 1.2, "y": 5.2, "width": 10.9, "height": 0.6}),
        ],
    }


def build_data_cards(slide: dict) -> dict:
    """数据卡片：多个 KPI 数字。"""
    stats = slide.get("stats", slide.get("cards", slide.get("numbers", [])))
    if not stats:
        return build_two_column(slide)

    elements = [_title_element(slide.get("title", ""))]
    n = min(len(stats), 4)
    b = _card_bounds(0, n, start_y=1.9, height=3.8, gap=0.3)
    card_h = b["height"]

    for idx, stat in enumerate(stats[:n]):
        cb = _card_bounds(idx, n, start_y=1.9, height=card_h, gap=0.3)
        value = str(stat.get("value", stat.get("number", "")))
        label = stat.get("label", stat.get("name", ""))
        note = stat.get("note", stat.get("description", ""))
        icon_name = stat.get("icon")
        # 卡片背景
        elements.append(make_shape("rounded_rect", cb, fill={"type": "solid", "color": "$surface"}, border={"width": 1, "color": "#E2E8F0"}, rounded_radius=0.15))

        y_cursor = cb["y"] + 0.35
        if icon_name:
            icon_size = 0.45
            icon_x = cb["x"] + (cb["width"] - icon_size) / 2
            elements.append({
                "type": "icon",
                "icon_name": icon_name,
                "color": "$secondary",
                "bounds": {"x": icon_x, "y": y_cursor, "width": icon_size, "height": icon_size},
            })
            y_cursor += icon_size + 0.1

        # 数字
        elements.append(make_text(value, {"font_family": "$heading", "font_size": "36pt", "color": "$primary", "bold": True, "align": "center"}, {"x": cb["x"], "y": y_cursor, "width": cb["width"], "height": 0.9}))
        # 标签
        elements.append(make_text(label, {"font_family": "$heading", "font_size": "16pt", "color": "$text", "bold": True, "align": "center"}, {"x": cb["x"], "y": y_cursor + 0.9, "width": cb["width"], "height": 0.5}))
        # 说明
        if note:
            elements.append(make_text(note, {"font_family": "$body", "font_size": "13pt", "color": "$muted", "align": "center"}, {"x": cb["x"] + 0.1, "y": y_cursor + 1.5, "width": cb["width"] - 0.2, "height": 1.0}))

    return {
        "type": "data",
        "layout": "data-cards",
        "title": slide.get("title"),
        "background": {"type": "solid", "color": "$background"},
        "elements": elements,
    }


def build_comparison(slide: dict) -> dict:
    """对比页：左右两列对比。"""
    left = slide.get("left", {})
    right = slide.get("right", {})
    col_w = 5.6
    x_left = MARGIN["left"]
    x_right = PAGE_W - MARGIN["right"] - col_w

    elements = [_title_element(slide.get("title", ""))]

    # 左侧卡片
    elements.append(make_shape("rounded_rect", {"x": x_left, "y": 1.8, "width": col_w, "height": 4.5}, fill={"type": "solid", "color": "$surface"}, border={"width": 1, "color": "#E2E8F0"}, rounded_radius=0.15))
    elements.append(make_text(left.get("title", ""), {"font_family": "$heading", "font_size": "22pt", "color": "$primary", "bold": True, "align": "center"}, {"x": x_left, "y": 2.0, "width": col_w, "height": 0.6}))
    elements.append(make_bullet_text(left.get("points", left.get("bullets", [])), "$body", {"x": x_left + 0.3, "y": 2.7, "width": col_w - 0.6, "height": 3.4}))

    # 右侧卡片
    elements.append(make_shape("rounded_rect", {"x": x_right, "y": 1.8, "width": col_w, "height": 4.5}, fill={"type": "solid", "color": "$surface"}, border={"width": 1, "color": "#E2E8F0"}, rounded_radius=0.15))
    elements.append(make_text(right.get("title", ""), {"font_family": "$heading", "font_size": "22pt", "color": "$primary", "bold": True, "align": "center"}, {"x": x_right, "y": 2.0, "width": col_w, "height": 0.6}))
    elements.append(make_bullet_text(right.get("points", right.get("bullets", [])), "$body", {"x": x_right + 0.3, "y": 2.7, "width": col_w - 0.6, "height": 3.4}))

    # VS 标记
    elements.append(make_shape("ellipse", {"x": PAGE_W / 2 - 0.35, "y": 3.6, "width": 0.7, "height": 0.7}, fill={"type": "solid", "color": "$surface"}, border={"width": 1, "color": "$primary"}))
    elements.append(make_text("VS", {"font_family": "$heading", "font_size": "16pt", "color": "$primary", "bold": True, "align": "center"}, {"x": PAGE_W / 2 - 0.35, "y": 3.75, "width": 0.7, "height": 0.4}))

    return {
        "type": "content",
        "layout": "comparison",
        "title": slide.get("title"),
        "background": {"type": "solid", "color": "$background"},
        "elements": elements,
    }


def build_chart(slide: dict) -> dict:
    insights = slide.get("insights", [])
    insight_text = "\n".join(f"· {i}" for i in insights)
    return {
        "type": "data",
        "layout": "chart",
        "title": slide.get("title"),
        "background": {"type": "solid", "color": "$background"},
        "elements": [
            _title_element(slide.get("title", "")),
            {
                "type": "chart",
                "chart_type": slide.get("chart_type", "bar"),
                "labels": slide.get("labels", []),
                "series": slide.get("series", []),
                "colors": slide.get("colors", ["$secondary", "$accent"]),
                "bounds": {"x": 0.8, "y": 1.7, "width": 7.5, "height": 4.8},
            },
            make_text(insight_text, "$body", {"x": 8.6, "y": 1.7, "width": 4, "height": 4}),
        ],
    }


def build_closing(slide: dict) -> dict:
    return {
        "type": "closing",
        "layout": "closing",
        "title": slide.get("title", "谢谢观看"),
        "background": {"type": "solid", "color": "$primary"},
        "elements": [
            make_text(
                slide.get("title", "谢谢观看"),
                {"font_family": "$heading", "font_size": "60pt", "color": "#FFFFFF", "bold": True},
                {"x": 0.8, "y": 2.8, "width": 11.7, "height": 1.3},
            ),
            make_text(
                slide.get("info", "DPPT Pro · 让每一份演示都足够专业"),
                {"font_family": "$body", "font_size": "20pt", "color": "#CBD5E1"},
                {"x": 0.8, "y": 4.3, "width": 11.7, "height": 0.7},
            ),
        ],
    }


# 新版布局注册表：以 layout 为键
LAYOUT_BUILDERS = {
    "cover": build_cover,
    "toc": build_toc,
    "title-only": build_title_only,
    "section": build_title_only,
    "two-column": build_two_column,
    "content": build_two_column,
    "three-column": build_three_column,
    "image-left": lambda s: build_image_text(s, "left"),
    "image-right": lambda s: build_image_text(s, "right"),
    "timeline": build_timeline,
    "team": build_team,
    "quote": build_quote,
    "data-cards": build_data_cards,
    "comparison": build_comparison,
    "chart": build_chart,
    "closing": build_closing,
}

# 旧版兼容：以 type 为键
TYPE_BUILDERS = {
    "cover": build_cover,
    "toc": build_toc,
    "content": build_two_column,
    "chart": build_chart,
    "closing": build_closing,
}


def _infer_layout(slide: dict) -> str:
    """当用户未指定 layout 时，根据内容推断最合适的布局。"""
    stype = slide.get("type", "content")
    # 显式类型映射
    if stype in ("cover", "toc", "closing"):
        return stype
    if stype == "chart" or "series" in slide:
        return "chart"
    if "stats" in slide or "numbers" in slide:
        return "data-cards"
    if "quote" in slide or "source" in slide:
        return "quote"
    if "steps" in slide or "timeline" in slide:
        return "timeline"
    if "members" in slide or "team" in slide:
        return "team"
    if "left" in slide and "right" in slide:
        return "comparison"
    if "columns" in slide or "cards" in slide:
        cols = slide.get("columns") or slide.get("cards") or []
        if len(cols) >= 3:
            return "three-column"
    if "image" in slide or "image_src" in slide:
        return "image-left"
    if stype == "section":
        return "title-only"
    return "two-column"


def build_page(slide: dict) -> dict:
    layout = slide.get("layout")
    if not layout:
        layout = _infer_layout(slide)

    builder = LAYOUT_BUILDERS.get(layout)
    if not builder:
        # 旧版兼容
        stype = slide.get("type", "content")
        builder = TYPE_BUILDERS.get(stype)
    if not builder:
        raise ValueError(f"不支持的 slide 类型或布局: type={stype}, layout={layout}")
    return builder(slide)


def convert(outline: dict) -> dict:
    theme_name = outline.get("theme", "business")
    theme = load_theme(theme_name)

    doc = {
        "version": "0.1",
        "title": outline.get("title", ""),
        "author": outline.get("author", "DPPT Pro"),
        "description": outline.get("description", ""),
        "theme": theme,
        "pages": [build_page(slide) for slide in outline.get("slides", [])],
    }
    return doc


def main(argv=None):
    parser = argparse.ArgumentParser(description="大纲转 DPPT DSL")
    parser.add_argument("input", help="输入大纲 YAML 文件")
    parser.add_argument("output", help="输出 .dppt 文件")
    args = parser.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as f:
        outline = yaml.safe_load(f)

    doc = convert(outline)

    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        yaml.dump(doc, f, allow_unicode=True, sort_keys=False, width=120)

    print(f"[成功] 已生成 DSL: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
