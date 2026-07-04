"""
DPPT DSL YAML 解析器
把 .dppt YAML 文件解析为 DpptDocument 对象。
"""

from __future__ import annotations

import os
import yaml
from typing import Any, Dict, List, Optional

from .models import (
    Border,
    Chart,
    DpptDocument,
    Element,
    Fill,
    Icon,
    Image,
    Page,
    Shadow,
    Shape,
    Table,
    TableCell,
    Text,
    TextStyle,
    Theme,
    UnitValue,
)


def _unit(value: Any, default_unit: str = "pt") -> Optional[UnitValue]:
    if value is None:
        return None
    if isinstance(value, dict):
        return UnitValue(value=value.get("value", 0), unit=value.get("unit", default_unit))
    if isinstance(value, (int, float)):
        return UnitValue(float(value), default_unit)
    if isinstance(value, str):
        value = value.strip()
        if value.endswith("pt"):
            return UnitValue(float(value[:-2]), "pt")
        if value.endswith("px"):
            return UnitValue(float(value[:-2]), "px")
        if value.endswith("mm"):
            return UnitValue(float(value[:-2]), "mm")
        if value.endswith("in"):
            return UnitValue(float(value[:-2]), "inch")
        if value.endswith("em"):
            return UnitValue(float(value[:-2]), "em")
        return UnitValue(float(value), default_unit)
    return UnitValue(0, default_unit)


def _fill(data: Optional[Dict[str, Any]]) -> Optional[Fill]:
    if not data:
        return None
    return Fill(
        type=data.get("type", "solid"),
        color=data.get("color"),
        gradient=data.get("gradient"),
        image=data.get("image"),
        alpha=float(data.get("alpha", 1.0)),
    )


def _border(data: Optional[Dict[str, Any]]) -> Optional[Border]:
    if not data:
        return None
    return Border(
        width=float(data.get("width", 0)),
        color=data.get("color"),
        style=data.get("style", "solid"),
        alpha=float(data.get("alpha", 1.0)),
    )


def _shadow(data: Optional[Dict[str, Any]]) -> Optional[Shadow]:
    if not data:
        return None
    offset = data.get("offset", [0, 0])
    return Shadow(
        color=data.get("color"),
        blur=float(data.get("blur", 0)),
        offset=(float(offset[0]), float(offset[1])),
        alpha=float(data.get("alpha", 0.5)),
    )


def _text_style(data: Optional[Any]) -> TextStyle:
    if not data:
        return TextStyle()
    if isinstance(data, str):
        return TextStyle(ref=data.strip())
    return TextStyle(
        font_family=data.get("font_family"),
        font_size=_unit(data.get("font_size"), "pt"),
        color=data.get("color"),
        bold=bool(data.get("bold", False)),
        italic=bool(data.get("italic", False)),
        underline=bool(data.get("underline", False)),
        line_through=bool(data.get("line_through", False)),
        align=data.get("align", "left"),
        valign=data.get("valign", "top"),
        line_spacing=data.get("line_spacing"),
        letter_spacing=data.get("letter_spacing"),
    )


def _bounds(data: Optional[Dict[str, Any]]) -> Dict[str, float]:
    if not data:
        return {}
    return {k: float(v) for k, v in data.items()}


def _base_element(data: Dict[str, Any], elem: Element) -> Element:
    elem.id = data.get("id")
    elem.name = data.get("name")
    elem.bounds = _bounds(data.get("bounds"))
    elem.rotation = float(data.get("rotation", 0))
    elem.opacity = float(data.get("opacity", 1.0))
    elem.fill = _fill(data.get("fill"))
    elem.border = _border(data.get("border"))
    elem.shadow = _shadow(data.get("shadow"))
    elem.visible = bool(data.get("visible", True))
    return elem


def _text(data: Dict[str, Any]) -> Text:
    t = Text(type="text")
    _base_element(data, t)
    t.text = data.get("text", "")
    t.style = _text_style(data.get("style"))
    t.auto_size = bool(data.get("auto_size", True))
    t.wrap = bool(data.get("wrap", True))
    t.padding = data.get("padding", {"left": 0, "top": 0, "right": 0, "bottom": 0})
    return t


def _shape(data: Dict[str, Any]) -> Shape:
    s = Shape(type="shape")
    _base_element(data, s)
    s.shape_type = data.get("shape_type", "rect")
    s.rounded_radius = float(data.get("rounded_radius", 0))
    s.points = [tuple(p) for p in data.get("points", [])]
    s.svg_path = data.get("svg_path")
    return s


def _image(data: Dict[str, Any]) -> Image:
    img = Image(type="image")
    _base_element(data, img)
    img.src = data.get("src", "")
    img.alt = data.get("alt", "")
    img.object_fit = data.get("object_fit", "cover")
    img.crop = data.get("crop")
    return img


def _icon(data: Dict[str, Any]) -> Icon:
    icon = Icon(type="icon")
    _base_element(data, icon)
    icon.icon_name = data.get("icon_name")
    icon.svg_path = data.get("svg_path")
    icon.src = data.get("src")
    icon.color = data.get("color")
    icon.size = data.get("size")
    return icon


def _table_cell(data: Dict[str, Any]) -> TableCell:
    return TableCell(
        text=data.get("text", ""),
        row_span=int(data.get("row_span", 1)),
        col_span=int(data.get("col_span", 1)),
        style=_text_style(data.get("style")),
        fill=_fill(data.get("fill")),
        border=_border(data.get("border")),
    )


def _table(data: Dict[str, Any]) -> Table:
    t = Table(type="table")
    _base_element(data, t)
    t.rows = [[_table_cell(cell) for cell in row] for row in data.get("rows", [])]
    t.col_widths = [float(v) for v in data.get("col_widths", [])]
    t.row_heights = [float(v) for v in data.get("row_heights", [])]
    t.header_rows = int(data.get("header_rows", 0))
    t.header_fill = _fill(data.get("header_fill"))
    return t


def _chart(data: Dict[str, Any]) -> Chart:
    c = Chart(type="chart")
    _base_element(data, c)
    c.chart_type = data.get("chart_type", "bar")
    c.data = data.get("data", {})
    c.labels = data.get("labels", [])
    c.series = data.get("series", [])
    c.colors = data.get("colors", [])
    c.show_legend = bool(data.get("show_legend", True))
    c.show_grid = bool(data.get("show_grid", True))
    c.title = data.get("title")
    return c


def _element(data: Dict[str, Any]) -> Optional[Element]:
    etype = data.get("type")
    if etype == "text":
        return _text(data)
    if etype == "shape":
        return _shape(data)
    if etype == "image":
        return _image(data)
    if etype == "icon":
        return _icon(data)
    if etype == "table":
        return _table(data)
    if etype == "chart":
        return _chart(data)
    return None


def _page(data: Dict[str, Any]) -> Page:
    page = Page(
        type=data.get("type", "content"),
        layout=data.get("layout", "default"),
        title=data.get("title"),
        subtitle=data.get("subtitle"),
        background=_fill(data.get("background")),
        notes=data.get("notes"),
        transition=data.get("transition"),
        animations=data.get("animations", []),
        master_ref=data.get("master_ref"),
    )
    for e in data.get("elements", []):
        elem = _element(e)
        if elem:
            page.elements.append(elem)
    return page


def _theme(data: Dict[str, Any]) -> Theme:
    return Theme(
        name=data.get("name", "default"),
        colors=data.get("colors", {}),
        fonts=data.get("fonts", {}),
        text_styles={k: _text_style(v) for k, v in data.get("text_styles", {}).items()},
        table_styles=data.get("table_styles", {}),
        page_size=tuple(data.get("page_size", [13.333, 7.5])),
        page_margin=data.get("page_margin", {"left": 0.5, "top": 0.5, "right": 0.5, "bottom": 0.5}),
    )


def loads_dppt(content: str, resource_base: Optional[str] = None) -> DpptDocument:
    """从 YAML 字符串解析 DPPT 文档。"""
    raw = yaml.safe_load(content)
    if not isinstance(raw, dict):
        raise ValueError("DPPT 文档必须是 YAML mapping")

    doc = DpptDocument(
        version=str(raw.get("version", "0.1")),
        title=raw.get("title", ""),
        author=raw.get("author"),
        description=raw.get("description"),
        theme=_theme(raw.get("theme", {})),
        resources=raw.get("resources", {}),
    )
    for p in raw.get("pages", []):
        doc.pages.append(_page(p))

    if resource_base:
        doc.resources["__base__"] = resource_base
    return doc


def load_dppt(path: str) -> DpptDocument:
    """从 .dppt 文件加载文档。"""
    with open(path, "r", encoding="utf-8") as f:
        return loads_dppt(f.read(), resource_base=os.path.dirname(os.path.abspath(path)))
