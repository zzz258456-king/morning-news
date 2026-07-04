import json
import os
import tempfile
from pathlib import Path

import pytest

from app.services.pptx_renderer import render_presentation, hex_to_rgb
from app.store import save_project, load_project, get_project_path, WORK_DIR


def test_hex_to_rgb():
    rgb = hex_to_rgb("#1F3864")
    assert rgb == (31, 56, 100)  # RGBColor 可比较


def test_render_presentation():
    config = {
        "id": "test_render",
        "title": "测试演示",
        "template": {
            "id": "deepppt-academic",
            "name": "deepPPT 学术风",
            "colors": ["#1F3864", "#2E5EAA", "#C00000", "#FFFFFF"],
            "layout": "16:9",
            "source": "builtin",
        },
        "generated_slides": [
            {
                "page_id": "page_1",
                "title": "第一页",
                "bullets": ["要点1", "要点2"],
                "layout": "title-bullets-only",
            },
            {
                "page_id": "page_2",
                "title": "第二页",
                "bullets": ["左侧要点"],
                "layout": "title-bullets-left-image",
            },
        ],
    }
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "output.pptx"
        render_presentation(config, output, Path(tmp))
        assert output.exists()
        assert output.stat().st_size > 0


def test_store_save_load():
    project_id = "test_store_123"
    data = {"id": project_id, "title": "测试"}
    save_project(project_id, data)
    loaded = load_project(project_id)
    assert loaded == data


def test_store_missing():
    assert load_project("non_existent_project") is None
