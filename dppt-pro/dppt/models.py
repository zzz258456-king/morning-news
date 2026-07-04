"""
DPPT DSL 数据模型 (v0.1)
参考 Kimi .pptd 格式：文档 - 页面 - 元素三层结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class UnitValue:
    """带单位数值，默认 pt。"""
    value: float
    unit: str = "pt"  # pt / px / mm / inch / em


@dataclass
class Fill:
    """填充定义。"""
    type: str = "none"  # none / solid / gradient / image / pattern
    color: Optional[str] = None
    gradient: Optional[Dict[str, Any]] = None
    image: Optional[str] = None
    alpha: float = 1.0


@dataclass
class Border:
    """边框定义。"""
    width: float = 0.0
    color: Optional[str] = None
    style: str = "solid"  # solid / dashed / dotted / double
    alpha: float = 1.0


@dataclass
class Shadow:
    """阴影定义。"""
    color: Optional[str] = None
    blur: float = 0.0
    offset: Tuple[float, float] = (0.0, 0.0)
    alpha: float = 0.5


@dataclass
class TextStyle:
    """文本样式。"""
    font_family: Optional[str] = None
    font_size: Optional[UnitValue] = None
    color: Optional[str] = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    line_through: bool = False
    align: str = "left"  # left / center / right / justify
    valign: str = "top"  # top / middle / bottom
    line_spacing: Optional[float] = None
    letter_spacing: Optional[float] = None
    ref: Optional[str] = None  # 样式引用，如 $title


@dataclass
class Element:
    """页面元素基类。"""
    type: str
    id: Optional[str] = None
    name: Optional[str] = None
    bounds: Dict[str, float] = field(default_factory=dict)  # x, y, width, height
    rotation: float = 0.0
    opacity: float = 1.0
    fill: Optional[Fill] = None
    border: Optional[Border] = None
    shadow: Optional[Shadow] = None
    visible: bool = True


@dataclass
class Text(Element):
    """文本元素。"""
    text: str = ""
    style: TextStyle = field(default_factory=TextStyle)
    auto_size: bool = True
    wrap: bool = True
    padding: Dict[str, float] = field(default_factory=lambda: {"left": 0, "top": 0, "right": 0, "bottom": 0})


@dataclass
class Shape(Element):
    """形状元素：矩形、圆角矩形、椭圆、箭头、自定义 SVG 路径等。"""
    shape_type: str = "rect"  # rect / rounded_rect / ellipse / triangle / arrow / line / custom
    rounded_radius: float = 0.0
    points: List[Tuple[float, float]] = field(default_factory=list)
    svg_path: Optional[str] = None


@dataclass
class Image(Element):
    """图片元素。"""
    src: str = ""
    alt: str = ""
    object_fit: str = "cover"  # cover / contain / fill / none
    crop: Optional[Dict[str, float]] = None


@dataclass
class Icon(Element):
    """图标元素，使用 SVG 路径、图标名称或 SVG 文件。"""
    icon_name: Optional[str] = None
    svg_path: Optional[str] = None
    src: Optional[str] = None  # SVG 文件路径
    color: Optional[str] = None
    size: Optional[float] = None


@dataclass
class TableCell:
    """表格单元格。"""
    text: str = ""
    row_span: int = 1
    col_span: int = 1
    style: TextStyle = field(default_factory=TextStyle)
    fill: Optional[Fill] = None
    border: Optional[Border] = None


@dataclass
class Table(Element):
    """表格元素。"""
    rows: List[List[TableCell]] = field(default_factory=list)
    col_widths: List[float] = field(default_factory=list)
    row_heights: List[float] = field(default_factory=list)
    header_rows: int = 0
    header_fill: Optional[Fill] = None


@dataclass
class Chart(Element):
    """图表元素：柱状图、折线图、饼图、散点图等。"""
    chart_type: str = "bar"  # bar / line / pie / scatter / area
    data: Dict[str, Any] = field(default_factory=dict)
    labels: List[str] = field(default_factory=list)
    series: List[Dict[str, Any]] = field(default_factory=list)
    colors: List[str] = field(default_factory=list)
    show_legend: bool = True
    show_grid: bool = True
    title: Optional[str] = None


@dataclass
class Page:
    """单页幻灯片。"""
    type: str = "content"  # cover / toc / content / data / closing / custom
    layout: str = "default"
    title: Optional[str] = None
    subtitle: Optional[str] = None
    background: Optional[Fill] = None
    elements: List[Element] = field(default_factory=list)
    notes: Optional[str] = None
    transition: Optional[str] = None
    animations: List[Dict[str, Any]] = field(default_factory=list)
    master_ref: Optional[str] = None  # 母版引用


@dataclass
class Theme:
    """主题：颜色、字体、文本样式、表格样式、全局尺寸。"""
    name: str = "default"
    colors: Dict[str, str] = field(default_factory=dict)
    fonts: Dict[str, str] = field(default_factory=dict)
    text_styles: Dict[str, TextStyle] = field(default_factory=dict)
    table_styles: Dict[str, Any] = field(default_factory=dict)
    page_size: Tuple[float, float] = (13.333, 7.5)  # 16:9, inch
    page_margin: Dict[str, float] = field(default_factory=lambda: {"left": 0.5, "top": 0.5, "right": 0.5, "bottom": 0.5})


@dataclass
class DpptDocument:
    """DPPT DSL 根文档。"""
    version: str = "0.1"
    title: str = ""
    author: Optional[str] = None
    description: Optional[str] = None
    theme: Theme = field(default_factory=Theme)
    pages: List[Page] = field(default_factory=list)
    resources: Dict[str, str] = field(default_factory=dict)


ElementUnion = Union[Text, Shape, Image, Icon, Table, Chart]
