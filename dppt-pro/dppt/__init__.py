"""
DPPT Pro - 商业级 PPT 生成引擎
本地 DSL + 渲染器 + 检查器，对标 Kimi PPT 架构。
"""

__version__ = "0.1.0"
__author__ = "DPPT Pro"

from .parser import load_dppt, loads_dppt
from .renderer import DpptRenderer
from .checker import DpptChecker

__all__ = ["load_dppt", "loads_dppt", "DpptRenderer", "DpptChecker"]
