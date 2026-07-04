"""
主题解析器：处理 DPPT DSL 中的 $color / $style 引用。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .models import Fill, TextStyle, Theme


_COLOR_REF_RE = re.compile(r"\$([A-Za-z0-9_\-]+)")


def resolve_color(value: Any, theme: Theme) -> Any:
    """解析颜色引用；非引用值原样返回。"""
    if not isinstance(value, str):
        return value
    match = _COLOR_REF_RE.fullmatch(value.strip())
    if match:
        key = match.group(1)
        if key in theme.colors:
            return theme.colors[key]
        raise ValueError(f"主题未定义颜色: ${key}")
    return value


def resolve_text_style(style_ref: Any, theme: Theme) -> Optional[TextStyle]:
    """解析文本样式引用。"""
    if isinstance(style_ref, str):
        match = _COLOR_REF_RE.fullmatch(style_ref.strip())
        if match:
            key = match.group(1)
            if key in theme.text_styles:
                return theme.text_styles[key]
            raise ValueError(f"主题未定义文本样式: ${key}")
    if isinstance(style_ref, dict):
        return _dict_to_text_style(style_ref, theme)
    return None


def _dict_to_text_style(data: Dict[str, Any], theme: Theme) -> TextStyle:
    from .parser import _unit

    return TextStyle(
        font_family=data.get("font_family"),
        font_size=_unit(data.get("font_size"), "pt"),
        color=resolve_color(data.get("color"), theme),
        bold=bool(data.get("bold", False)),
        italic=bool(data.get("italic", False)),
        underline=bool(data.get("underline", False)),
        line_through=bool(data.get("line_through", False)),
        align=data.get("align", "left"),
        valign=data.get("valign", "top"),
        line_spacing=data.get("line_spacing"),
        letter_spacing=data.get("letter_spacing"),
    )


def resolve_fill(fill: Optional[Fill], theme: Theme) -> Optional[Fill]:
    if fill is None:
        return None
    if fill.color:
        fill.color = resolve_color(fill.color, theme)
    if fill.gradient:
        # 简单解析渐变中的颜色引用
        stops = fill.gradient.get("stops", [])
        for stop in stops:
            if isinstance(stop, dict) and "color" in stop:
                stop["color"] = resolve_color(stop["color"], theme)
    return fill


def resolve_text_style_in_place(style: TextStyle, theme: Theme) -> TextStyle:
    if style.ref:
        match = _COLOR_REF_RE.fullmatch(style.ref)
        if match:
            key = match.group(1)
            if key in theme.text_styles:
                # 用主题样式替换当前样式，但仍保留当前样式的显式覆盖
                base = theme.text_styles[key]
                if style.font_family is None and base.font_family is not None:
                    style.font_family = base.font_family
                if style.font_size is None and base.font_size is not None:
                    style.font_size = base.font_size
                if style.color is None and base.color is not None:
                    style.color = base.color
                style.bold = base.bold
                style.italic = base.italic
                style.underline = base.underline
                style.line_through = base.line_through
                style.align = base.align
                style.valign = base.valign
                if style.line_spacing is None:
                    style.line_spacing = base.line_spacing
                if style.letter_spacing is None:
                    style.letter_spacing = base.letter_spacing
            else:
                raise ValueError(f"主题未定义文本样式: {style.ref}")
    if style.color:
        style.color = resolve_color(style.color, theme)
    if style.font_family and style.font_family.startswith("$"):
        key = style.font_family[1:]
        if key in theme.fonts:
            style.font_family = theme.fonts[key]
    return style


def apply_theme_to_page(page, theme: Theme):
    """把主题颜色/字体引用解析到页面元素上。"""
    if page.background:
        page.background = resolve_fill(page.background, theme)
    for elem in page.elements:
        if elem.fill:
            elem.fill = resolve_fill(elem.fill, theme)
        if elem.border and elem.border.color:
            elem.border.color = resolve_color(elem.border.color, theme)
        if elem.shadow and elem.shadow.color:
            elem.shadow.color = resolve_color(elem.shadow.color, theme)
        if hasattr(elem, "style") and elem.style:
            resolve_text_style_in_place(elem.style, theme)
        if hasattr(elem, "header_fill") and elem.header_fill:
            elem.header_fill = resolve_fill(elem.header_fill, theme)
        if hasattr(elem, "colors") and elem.colors:
            elem.colors = [resolve_color(c, theme) for c in elem.colors]


def apply_theme(doc) -> None:
    """解析整份文档的主题引用。"""
    for page in doc.pages:
        apply_theme_to_page(page, doc.theme)
