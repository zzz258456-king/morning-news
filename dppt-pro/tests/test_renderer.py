"""
DPPT Pro 单元测试
"""

import os
import tempfile
import unittest

import yaml

from dppt import DpptChecker, DpptRenderer, load_dppt, loads_dppt


SAMPLE_DPPT = """
version: "0.1"
title: 测试演示
author: DPPT Pro
theme:
  name: business
  colors:
    primary: "#1E3A8A"
    secondary: "#3B82F6"
    accent: "#F59E0B"
    background: "#FFFFFF"
    text: "#1F2937"
  fonts:
    heading: "Microsoft YaHei"
    body: "Microsoft YaHei"
  text_styles:
    title:
      font_family: "$heading"
      font_size: 44pt
      color: "$primary"
      bold: true
    subtitle:
      font_family: "$body"
      font_size: 24pt
      color: "$secondary"
    body:
      font_family: "$body"
      font_size: 18pt
      color: "$text"
  page_size: [13.333, 7.5]
pages:
  - type: cover
    title: DPPT Pro
    subtitle: 商业级 PPT 生成引擎
    background:
      type: solid
      color: "$background"
    elements:
      - type: shape
        shape_type: rect
        bounds: {x: 0, y: 0, width: 13.333, height: 7.5}
        fill: {type: solid, color: "$background"}
      - type: text
        text: DPPT Pro
        style: $title
        bounds: {x: 1, y: 2.5, width: 11, height: 1.2}
      - type: text
        text: 商业级 PPT 生成引擎
        style: $subtitle
        bounds: {x: 1, y: 3.8, width: 11, height: 0.8}
  - type: content
    title: 核心能力
    elements:
      - type: text
        text: 核心能力
        style: $title
        bounds: {x: 0.8, y: 0.6, width: 11, height: 1}
      - type: text
        text: |
          1. DSL 驱动的高度可控排版
          2. 专业主题与颜色系统
          3. 图片、表格、图表支持
          4. 自动质量检查
        style: $body
        bounds: {x: 0.8, y: 1.8, width: 11, height: 3}
"""


class TestParser(unittest.TestCase):
    def test_loads_basic(self):
        doc = loads_dppt(SAMPLE_DPPT)
        self.assertEqual(doc.title, "测试演示")
        self.assertEqual(len(doc.pages), 2)
        self.assertEqual(doc.theme.colors["primary"], "#1E3A8A")

    def test_theme_reference_resolution(self):
        doc = loads_dppt(SAMPLE_DPPT)
        from dppt.theme import apply_theme

        apply_theme(doc)
        first_text = doc.pages[0].elements[1]
        self.assertEqual(first_text.style.color, "#1E3A8A")
        self.assertEqual(first_text.style.font_family, "Microsoft YaHei")


class TestRenderer(unittest.TestCase):
    def test_render_pptx(self):
        doc = loads_dppt(SAMPLE_DPPT)
        renderer = DpptRenderer(doc)
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "test.pptx")
            renderer.render(output)
            self.assertTrue(os.path.exists(output))
            self.assertGreater(os.path.getsize(output), 1000)


class TestChecker(unittest.TestCase):
    def test_quick_check_pass(self):
        doc = loads_dppt(SAMPLE_DPPT)
        ok, issues = DpptChecker.quick_check(doc)
        self.assertTrue(ok)

    def test_contrast_error(self):
        bad_yaml = """
version: "0.1"
title: 低对比度测试
theme:
  colors:
    bg: "#FFFFFF"
    fg: "#EEEEEE"
pages:
  - type: content
    background: {type: solid, color: "$bg"}
    elements:
      - type: text
        text: 看不清的文字
        style: {font_size: 18pt, color: "$fg"}
        bounds: {x: 1, y: 1, width: 5, height: 1}
"""
        doc = loads_dppt(bad_yaml)
        ok, issues = DpptChecker.quick_check(doc)
        self.assertFalse(ok)
        self.assertTrue(any("对比度" in i.message for i in issues))


class TestOutlineConverter(unittest.TestCase):
    def test_outline_to_dppt_and_render(self):
        import tempfile

        import yaml

        from dppt import DpptRenderer, load_dppt

        outline = {
            "title": "大纲测试",
            "theme": "business",
            "slides": [
                {"type": "cover", "title": "封面", "subtitle": "副标题", "info": "信息"},
                {"type": "toc", "items": ["A", "B", "C"]},
                {"type": "content", "title": "内容", "bullets": ["要点1", "要点2"]},
                {"type": "closing", "title": "结束"},
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            outline_path = os.path.join(tmpdir, "outline.yaml")
            dppt_path = os.path.join(tmpdir, "outline.dppt")
            pptx_path = os.path.join(tmpdir, "outline.pptx")

            with open(outline_path, "w", encoding="utf-8") as f:
                yaml.dump(outline, f, allow_unicode=True)

            from scripts.outline_to_dppt import main as outline_main

            outline_main([outline_path, dppt_path])
            doc = load_dppt(dppt_path)
            self.assertEqual(len(doc.pages), 4)

            renderer = DpptRenderer(doc)
            renderer.render(pptx_path)
            self.assertTrue(os.path.exists(pptx_path))


class TestAiGenerator(unittest.TestCase):
    def test_parse_outline(self):
        from dppt.ai_generator import AiDslGenerator

        raw = """
```yaml
title: 测试
theme: business
slides:
  - type: cover
    title: 封面
```
"""
        outline = AiDslGenerator._parse_outline(raw)
        self.assertEqual(outline["title"], "测试")
        self.assertEqual(len(outline["slides"]), 1)

    def test_generate_dppt_mock(self):
        from unittest.mock import MagicMock, patch

        from dppt.ai_generator import AiDslGenerator

        fake_client = MagicMock()
        fake_message = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = """
title: 测试演示
theme: business
slides:
  - type: cover
    title: 封面
    subtitle: 副标题
    info: 信息
  - type: closing
    title: 谢谢
"""
        fake_message.content = [text_block]
        fake_client.messages.create.return_value = fake_message

        with patch("anthropic.Anthropic", return_value=fake_client):
            gen = AiDslGenerator(api_key="fake-key")
            dppt_text = gen.generate_dppt("测试", pages=2, style="business")

        self.assertIn("type: cover", dppt_text)
        self.assertIn("type: closing", dppt_text)


class TestLayoutBuilders(unittest.TestCase):
    def _render_outline(self, outline: dict):
        import tempfile

        from dppt import DpptChecker, DpptRenderer, loads_dppt
        from scripts.outline_to_dppt import convert

        doc_dict = convert(outline)
        doc = loads_dppt(yaml.dump(doc_dict, allow_unicode=True, sort_keys=False, width=120))
        ok, issues = DpptChecker.quick_check(doc)
        self.assertTrue(ok, "\n".join(i.message for i in issues))

        with tempfile.TemporaryDirectory() as tmpdir:
            pptx_path = os.path.join(tmpdir, "layouts.pptx")
            renderer = DpptRenderer(doc)
            renderer.render(pptx_path)
            self.assertTrue(os.path.exists(pptx_path))
            return pptx_path

    def test_title_only_layout(self):
        outline = {
            "title": "布局测试",
            "theme": "business",
            "slides": [
                {"type": "section", "layout": "title-only", "title": "第一部分", "subtitle": "概述", "number": "01"},
            ],
        }
        self._render_outline(outline)

    def test_three_column_layout(self):
        outline = {
            "title": "布局测试",
            "theme": "business",
            "slides": [
                {
                    "type": "content",
                    "layout": "three-column",
                    "title": "三栏布局",
                    "columns": [
                        {"title": "A", "bullets": ["a1", "a2"]},
                        {"title": "B", "bullets": ["b1", "b2"]},
                        {"title": "C", "bullets": ["c1", "c2"]},
                    ],
                },
            ],
        }
        self._render_outline(outline)

    def test_timeline_layout(self):
        outline = {
            "title": "布局测试",
            "theme": "business",
            "slides": [
                {
                    "type": "content",
                    "layout": "timeline",
                    "title": "时间轴",
                    "steps": [
                        {"label": "2023", "description": "起点"},
                        {"label": "2024", "description": "发展"},
                        {"label": "2025", "description": "成熟"},
                    ],
                },
            ],
        }
        self._render_outline(outline)

    def test_team_layout(self):
        outline = {
            "title": "布局测试",
            "theme": "business",
            "slides": [
                {
                    "type": "content",
                    "layout": "team",
                    "title": "团队",
                    "members": [
                        {"name": "张三", "role": "CEO"},
                        {"name": "李四", "role": "CTO"},
                        {"name": "王五", "role": "Designer"},
                    ],
                },
            ],
        }
        self._render_outline(outline)

    def test_quote_layout(self):
        outline = {
            "title": "布局测试",
            "theme": "business",
            "slides": [
                {
                    "type": "content",
                    "layout": "quote",
                    "title": "引用",
                    "quote": "设计不仅仅是外观，更是工作方式。",
                    "source": "史蒂夫·乔布斯",
                },
            ],
        }
        self._render_outline(outline)

    def test_data_cards_layout(self):
        outline = {
            "title": "布局测试",
            "theme": "business",
            "slides": [
                {
                    "type": "content",
                    "layout": "data-cards",
                    "title": "核心指标",
                    "stats": [
                        {"value": "128%", "label": "增长", "note": "同比"},
                        {"value": "50万+", "label": "用户", "note": "日活"},
                        {"value": "99.9%", "label": "可用性", "note": "SLA"},
                    ],
                },
            ],
        }
        self._render_outline(outline)

    def test_comparison_layout(self):
        outline = {
            "title": "布局测试",
            "theme": "business",
            "slides": [
                {
                    "type": "content",
                    "layout": "comparison",
                    "title": "对比",
                    "left": {"title": "方案 A", "bullets": ["快", "省"]},
                    "right": {"title": "方案 B", "bullets": ["稳", "强"]},
                },
            ],
        }
        self._render_outline(outline)

    def test_image_text_layout(self):
        outline = {
            "title": "布局测试",
            "theme": "business",
            "slides": [
                {
                    "type": "content",
                    "layout": "image-left",
                    "title": "图文",
                    "image": "nonexistent.png",
                    "bullets": ["要点 1", "要点 2"],
                },
            ],
        }
        self._render_outline(outline)

    def test_layout_inference(self):
        """测试未指定 layout 时能否根据内容自动推断。"""
        outline = {
            "title": "推断测试",
            "theme": "business",
            "slides": [
                {"type": "cover", "title": "封面"},
                {"type": "content", "title": "三栏", "columns": [{"title": "A", "bullets": ["1", "2"]}, {"title": "B", "bullets": ["1"]}, {"title": "C", "bullets": ["1"]}]},
                {"type": "content", "title": "时间轴", "steps": [{"label": "T1", "description": "d"}, {"label": "T2", "description": "d"}]},
                {"type": "closing", "title": "结束"},
            ],
        }
        from scripts.outline_to_dppt import convert

        doc = convert(outline)
        layouts = [p.get("layout") for p in doc["pages"]]
        self.assertEqual(layouts, ["cover", "three-column", "timeline", "closing"])


class TestIconRendering(unittest.TestCase):
    def test_builtin_icon_render(self):
        from dppt import DpptRenderer, loads_dppt

        dppt_text = """
version: "0.1"
title: 图标测试
theme:
  name: business
  colors:
    primary: "#0F172A"
    secondary: "#3B82F6"
    accent: "#F59E0B"
    background: "#F8FAFC"
    surface: "#FFFFFF"
    text: "#1E2937"
    muted: "#64748B"
  fonts:
    heading: "Microsoft YaHei"
    body: "Microsoft YaHei"
  text_styles:
    h2:
      font_family: "$heading"
      font_size: 36pt
      color: "$primary"
      bold: true
pages:
  - type: content
    title: 图标
    background: {type: solid, color: "$background"}
    elements:
      - type: icon
        icon_name: chart
        color: "$secondary"
        bounds: {x: 1, y: 2, width: 1, height: 1}
      - type: icon
        svg_path: "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
        color: "#F59E0B"
        bounds: {x: 3, y: 2, width: 1, height: 1}
"""
        doc = loads_dppt(dppt_text)
        renderer = DpptRenderer(doc)
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "icons.pptx")
            renderer.render(output)
            self.assertTrue(os.path.exists(output))
            self.assertGreater(os.path.getsize(output), 1000)


class TestAnimation(unittest.TestCase):
    def test_entrance_animation_xml(self):
        import zipfile

        from dppt import DpptRenderer, loads_dppt

        dppt_text = """
version: "0.1"
title: 动画测试
theme:
  name: business
  colors:
    primary: "#0F172A"
    secondary: "#3B82F6"
    accent: "#F59E0B"
    background: "#F8FAFC"
    surface: "#FFFFFF"
    text: "#1E2937"
    muted: "#64748B"
  fonts:
    heading: "Microsoft YaHei"
  text_styles:
    body:
      font_family: "$body"
      font_size: 18pt
      color: "$text"
pages:
  - type: content
    title: 动画页
    background: {type: solid, color: "$background"}
    elements:
      - type: text
        text: 第一行
        style: $body
        bounds: {x: 1, y: 2, width: 5, height: 0.8}
      - type: text
        text: 第二行
        style: $body
        bounds: {x: 1, y: 3, width: 5, height: 0.8}
"""
        doc = loads_dppt(dppt_text)
        renderer = DpptRenderer(doc, enable_animation=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "animated.pptx")
            renderer.render(output)
            with zipfile.ZipFile(output) as z:
                slide_xml = z.read("ppt/slides/slide1.xml").decode("utf-8")
                self.assertIn("animEffect", slide_xml)
                self.assertIn("fade", slide_xml)

    def test_disable_animation(self):
        import zipfile

        from dppt import DpptRenderer, loads_dppt

        dppt_text = """
version: "0.1"
title: 无动画测试
theme:
  name: business
  colors:
    primary: "#0F172A"
    background: "#F8FAFC"
    text: "#1E2937"
  fonts:
    heading: "Microsoft YaHei"
  text_styles:
    body:
      font_family: "$body"
      font_size: 18pt
      color: "$text"
pages:
  - type: content
    title: 无动画页
    background: {type: solid, color: "$background"}
    elements:
      - type: text
        text: 文本
        style: $body
        bounds: {x: 1, y: 2, width: 5, height: 0.8}
"""
        doc = loads_dppt(dppt_text)
        renderer = DpptRenderer(doc, enable_animation=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "no_anim.pptx")
            renderer.render(output)
            with zipfile.ZipFile(output) as z:
                slide_xml = z.read("ppt/slides/slide1.xml").decode("utf-8")
                self.assertNotIn("animEffect", slide_xml)


if __name__ == "__main__":
    unittest.main()
