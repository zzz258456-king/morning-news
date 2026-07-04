"""
DPPT 质量检查器
在渲染前后检测：溢出、对比度、格式问题、可修复错误。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .models import DpptDocument, Element, Fill, Page, Text
from .theme import apply_theme


@dataclass
class Issue:
    level: str  # error / warning / info
    page_index: int
    element_id: Optional[str]
    message: str
    suggestion: str = ""


class DpptChecker:
    """DPPT 文档质量检查器。"""

    def __init__(self, document: DpptDocument):
        self.document = document
        apply_theme(document)
        self.issues: List[Issue] = []

    def check_all(self) -> List[Issue]:
        self.issues = []
        self._check_format()
        self._check_overflow()
        self._check_contrast()
        self._check_resources()
        return self.issues

    def _check_format(self) -> None:
        """检查 DSL 格式基本问题。"""
        if not self.document.title:
            self.issues.append(Issue("warning", -1, None, "文档缺少标题", "建议设置 title 字段"))
        if not self.document.pages:
            self.issues.append(Issue("error", -1, None, "文档没有页面", "至少添加一个 page"))

        for idx, page in enumerate(self.document.pages):
            if page.type == "cover" and not page.title:
                self.issues.append(Issue("warning", idx, None, "封面页缺少标题", "封面建议设置 title"))
            for elem in page.elements:
                if not elem.bounds or "width" not in elem.bounds or "height" not in elem.bounds:
                    self.issues.append(
                        Issue("warning", idx, elem.id, f"{elem.type} 元素缺少 bounds 尺寸", "设置 x, y, width, height")
                    )

    def _check_overflow(self) -> None:
        """检查元素是否超出页面边界或相互重叠严重。"""
        width, height = self.document.theme.page_size
        for idx, page in enumerate(self.document.pages):
            for elem in page.elements:
                b = elem.bounds
                if not b:
                    continue
                x, y, w, h = b.get("x", 0), b.get("y", 0), b.get("width", 0), b.get("height", 0)
                if x < 0 or y < 0 or x + w > width or y + h > height:
                    self.issues.append(
                        Issue("warning", idx, elem.id, f"{elem.type} 元素超出页面边界", "调整 bounds 使其位于页面内")
                    )

    def _luminance(self, color: str) -> float:
        """计算 sRGB 相对亮度。"""
        color = color.lstrip("#")
        if len(color) == 3:
            color = "".join([c * 2 for c in color])
        try:
            rgb = [int(color[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
        except ValueError:
            return 1.0
        rgb = [(c / 12.92) if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]

    def _contrast_ratio(self, fg: str, bg: str) -> float:
        l1 = self._luminance(fg) + 0.05
        l2 = self._luminance(bg) + 0.05
        return max(l1, l2) / min(l1, l2)

    def _check_contrast(self) -> None:
        """检查文本与背景对比度。"""
        for idx, page in enumerate(self.document.pages):
            bg_color = "#FFFFFF"
            if page.background and page.background.color:
                bg_color = page.background.color

            for elem in page.elements:
                if elem.type != "text":
                    continue
                text = elem  # type: Text
                fg = text.style.color
                if not fg:
                    continue
                ratio = self._contrast_ratio(fg, bg_color)
                if ratio < 3.0:
                    self.issues.append(
                        Issue(
                            "error",
                            idx,
                            elem.id,
                            f"文本对比度过低 ({ratio:.2f}:1)",
                            "调整文本颜色或背景色，确保对比度 ≥ 4.5:1",
                        )
                    )
                elif ratio < 4.5:
                    self.issues.append(
                        Issue(
                            "warning",
                            idx,
                            elem.id,
                            f"文本对比度偏低 ({ratio:.2f}:1)",
                            "建议提升到 4.5:1 以上",
                        )
                    )

    def _check_resources(self) -> None:
        """检查图片/资源是否可解析。"""
        import os

        base = self.document.resources.get("__base__", "")
        for idx, page in enumerate(self.document.pages):
            for elem in page.elements:
                if elem.type == "image":
                    src = getattr(elem, "src", "")
                    if not src:
                        self.issues.append(Issue("warning", idx, elem.id, "图片元素缺少 src", "填写图片路径或 URL"))
                    elif not os.path.isabs(src):
                        full = os.path.join(base, src)
                        if not os.path.exists(full):
                            self.issues.append(
                                Issue("warning", idx, elem.id, f"图片文件不存在: {src}", "检查资源路径")
                            )

    @staticmethod
    def quick_check(document: DpptDocument) -> Tuple[bool, List[Issue]]:
        """快速检查，返回 (是否通过, 问题列表)。"""
        checker = DpptChecker(document)
        issues = checker.check_all()
        ok = not any(i.level == "error" for i in issues)
        return ok, issues
