"""
Web应用模块 - 基于 FastAPI
提供 RESTful API、数据可视化展示、爬虫控制面板
"""
from .app import create_app

__all__ = ["create_app"]
