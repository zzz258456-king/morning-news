"""
SVG / Icon 渲染支持

提供内置图标库，并将 SVG 路径/文件渲染为 PNG 后插入 PPTX。
后续可升级为矢量形状或原生 SVG 嵌入。
"""

from __future__ import annotations

import io
import os
import re
from typing import Optional, Tuple


# 内置图标库：icon_name -> SVG path d 属性（viewBox 0 0 24 24）
BUILTIN_ICONS = {
    "user": "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
    "users": "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M13 7a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm6 12v-2a4 4 0 0 0-3-3.87M21 7a4 4 0 1 0-8 0",
    "chart": "M18 20V10M12 20V4M6 20v-6M2 20h20",
    "chart-bar": "M12 20V10M18 20V4M6 20v-6M2 20h20",
    "chart-line": "M22 12h-4l-3 9L9 3l-3 9H2",
    "settings": "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.1a2 2 0 0 1-1-1.72v-.51a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    "target": "M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12zm0-4a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
    "bulb": "M9 18h6M10 22h4M12 2a7 7 0 0 0-7 7c0 2.5 1.5 4.5 3 6v1h8v-1c1.5-1.5 3-3.5 3-6a7 7 0 0 0-7-7z",
    "clock": "M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM12 6v6l4 2",
    "shield": "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
    "mail": "M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2zm0 2 8 5 8-5",
    "phone": "M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z",
    "map-pin": "M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0zM12 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
    "star": "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z",
    "heart": "M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z",
    "check": "M20 6L9 17l-5-5",
    "check-circle": "M22 11.08V12a10 10 0 1 1-5.93-9.14M22 4 12 14.01l-3-3",
    "alert": "M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01",
    "info": "M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM12 16v-4M12 8h.01",
    "search": "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zm10 2-4.35-4.35",
    "home": "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM9 22V12h6v10",
    "download": "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3",
    "upload": "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12",
    "link": "M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71",
    "file": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8",
    "folder": "M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z",
    "calendar": "M19 4H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zM16 2v4M8 2v4M3 10h18",
    "trash": "M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6",
    "edit": "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z",
    "plus": "M12 5v14M5 12h14",
    "minus": "M5 12h14",
    "x": "M18 6 6 18M6 6l12 12",
    "arrow-up": "M12 19V5M5 12l7-7 7 7",
    "arrow-down": "M12 5v14M5 12l7 7 7-7",
    "arrow-left": "M19 12H5M12 19l-7-7 7-7",
    "arrow-right": "M5 12h14M12 5l7 7-7 7",
    "trending-up": "M23 6l-9.5 9.5-5-5L1 18M17 6h6v6",
    "trending-down": "M23 18l-9.5-9.5-5 5L1 6M17 18h6v-6",
    "dollar": "M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6",
    "percent": "M19 5 5 19M6.5 4a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM17.5 15a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z",
    "award": "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M4.22 4.22l1.42 1.42M2 12h2M4.22 19.78l1.42-1.42M12 20v2M19.78 19.78l-1.42-1.42M22 12h-2M19.78 4.22l-1.42 1.42",
    "flag": "M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7",
    "globe": "M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z",
}


def _hex_to_rgb(color: str) -> Optional[Tuple[int, int, int]]:
    if not color:
        return None
    color = color.lstrip("#")
    if len(color) == 3:
        color = "".join([c * 2 for c in color])
    if len(color) == 6:
        try:
            return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return None
    return None


def _normalize_svg_path(d: str) -> str:
    """清理 SVG path，确保是单一路径。"""
    return re.sub(r"\s+", " ", d.strip())


def build_svg(path_data: str, color: str = "#000000", size: int = 48) -> str:
    """把 path d 属性和颜色包装成完整 SVG 字符串。"""
    rgb = _hex_to_rgb(color) or (0, 0, 0)
    fill = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{fill}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="{_normalize_svg_path(path_data)}"/></svg>'''


def render_svg_to_png(svg_content: str, size: int = 96, dpi: int = 150) -> Optional[bytes]:
    """把 SVG 字符串渲染为 PNG 字节。优先使用 svglib + reportlab，失败返回 None。"""
    try:
        from reportlab.graphics import renderPM
        from svglib.svglib import svg2rlg
    except ImportError:
        return None

    try:
        drawing = svg2rlg(io.BytesIO(svg_content.encode("utf-8")))
        if drawing is None:
            return None
        # 缩放到目标尺寸（reportlab 内部单位为点，1 inch = 72 pt）
        scale = (size / 72.0 * dpi / 96.0) / max(drawing.width, drawing.height)
        drawing.width *= scale
        drawing.height *= scale
        drawing.scale(scale, scale)
        buf = io.BytesIO()
        renderPM.drawToFile(drawing, buf, fmt="PNG", dpi=dpi)
        return buf.getvalue()
    except Exception:
        return None


def resolve_icon(icon_name: str) -> Optional[str]:
    """根据名称返回内置 SVG path，如不存在返回 None。"""
    return BUILTIN_ICONS.get(icon_name)


def render_icon(
    icon_name: Optional[str] = None,
    svg_path: Optional[str] = None,
    svg_file: Optional[str] = None,
    color: Optional[str] = None,
    size: int = 96,
) -> Optional[bytes]:
    """渲染图标为 PNG 字节。支持内置 icon_name、svg_path 字符串或 SVG 文件路径。"""
    path_data = svg_path
    if icon_name:
        path_data = resolve_icon(icon_name)
    if svg_file and os.path.exists(svg_file):
        try:
            with open(svg_file, "r", encoding="utf-8") as f:
                svg_content = f.read()
            return render_svg_to_png(svg_content, size=size)
        except Exception:
            return None

    if not path_data:
        return None

    return render_svg_to_png(build_svg(path_data, color=color or "#000000", size=24), size=size)
