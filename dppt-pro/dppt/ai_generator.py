"""
AI DSL 生成器

调用 Claude API，根据用户自然语言输入生成 DPPT outline.yaml，
再通过 outline_to_dppt.py 转换为完整 DSL。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

import yaml


DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
MAX_TOKENS = 4096


class AiGeneratorError(Exception):
    """AI 生成错误。"""


class AiDslGenerator:
    """根据自然语言输入生成 DPPT outline。"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or DEFAULT_MODEL
        if not self.api_key:
            raise AiGeneratorError("未配置 ANTHROPIC_API_KEY")
        try:
            import anthropic

            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError as e:
            raise AiGeneratorError("缺少 anthropic 依赖，请运行 pip install anthropic") from e

    def generate_outline(
        self,
        topic: str,
        pages: int = 6,
        style: str = "business",
        audience: Optional[str] = None,
        extra: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成 outline YAML 字典。"""
        prompt = self._build_prompt(topic, pages, style, audience, extra)
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = self._extract_text(message)
        except Exception as e:
            raise AiGeneratorError(f"调用 Claude API 失败：{e}") from e

        return self._parse_outline(raw)

    @staticmethod
    def _extract_text(message) -> str:
        """从 Anthropic Message 中提取第一个 text block 内容。"""
        for block in message.content:
            if getattr(block, "type", None) == "text" and hasattr(block, "text"):
                return block.text
        raise AiGeneratorError("Claude API 返回内容中没有找到文本块")

    def save_outline(self, outline: Dict[str, Any], path: str) -> None:
        out_dir = os.path.dirname(os.path.abspath(path))
        os.makedirs(out_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(outline, f, allow_unicode=True, sort_keys=False, width=120)

    def generate_dppt(
        self,
        topic: str,
        pages: int = 6,
        style: str = "business",
        audience: Optional[str] = None,
        extra: Optional[str] = None,
    ) -> str:
        """生成完整 .dppt DSL 字符串。"""
        outline = self.generate_outline(topic, pages, style, audience, extra)
        from scripts.outline_to_dppt import convert

        return yaml.dump(convert(outline), allow_unicode=True, sort_keys=False, width=120)

    @staticmethod
    def _build_prompt(topic: str, pages: int, style: str, audience: Optional[str], extra: Optional[str]) -> str:
        audience_line = f"目标受众：{audience}\n" if audience else ""
        extra_line = f"补充要求：{extra}\n" if extra else ""

        return f"""你是一位专业的商业级 PPT 内容设计师。请根据以下要求生成一份 DPPT Pro 大纲。

主题：{topic}
页数：约 {pages} 页（包含封面、目录、内容页、数据页可选、结束页）
风格：{style}（可选 business / tech / academic）
{audience_line}{extra_line}
请严格输出一个 YAML 对象，不要包含任何 Markdown 代码块标记或其他说明文字。YAML 格式如下：

```yaml
title: PPT 总标题
author: DPPT Pro
theme: {style}
slides:
  - type: cover
    title: 封面主标题
    subtitle: 副标题
    info: 报告信息，如 "DPPT Pro 出品 · 2026.07"

  - type: toc
    title: 目录
    items:
      - 目录项 1
      - 目录项 2
      - 目录项 3

  - type: section
    layout: title-only
    title: 第一部分标题
    subtitle: 本部分一句话概述
    number: "01"

  - type: content
    layout: two-column
    title: 页面标题
    bullets:
      - 要点 1
      - 要点 2
      - 要点 3
    highlight:
      title: 右侧卡片标题
      text: |
        关键数据/补充信息
        第二行

  - type: content
    layout: three-column
    title: 三栏并列
    columns:
      - title: 栏目标题 1
        bullets:
          - 要点 A
          - 要点 B
      - title: 栏目标题 2
        bullets:
          - 要点 A
          - 要点 B
      - title: 栏目标题 3
        bullets:
          - 要点 A
          - 要点 B

  - type: content
    layout: timeline
    title: 发展历程
    steps:
      - label: 2023
        description: 阶段描述
      - label: 2024
        description: 阶段描述
      - label: 2025
        description: 阶段描述

  - type: content
    layout: data-cards
    title: 核心指标
    stats:
      - value: 128%
        label: 增长率
        note: 同比去年
      - value: 50万+
        label: 用户数
        note: 日活跃用户

  - type: content
    layout: comparison
    title: 方案对比
    left:
      title: 方案 A
      bullets:
        - 优点 1
        - 优点 2
    right:
      title: 方案 B
      bullets:
        - 优点 1
        - 优点 2

  - type: content
    layout: quote
    quote: 一句有力量的话，作为本页核心观点。
    source: 来源或作者

  - type: chart
    title: 数据页标题
    chart_type: bar
    labels: [类别 A, 类别 B, 类别 C]
    series:
      - name: 2024
        data: [120, 200, 150]
      - name: 2025
        data: [140, 220, 180]
    insights:
      - 洞察要点 1
      - 洞察要点 2

  - type: closing
    title: 谢谢观看
    info: 结束语或品牌信息
```

可用布局说明（按需要选择，不要堆砌）：
- cover / toc / closing：固定结构，必填字段见示例。
- title-only（section）：章节分隔页，可用 number 给章节编号。
- two-column：左侧 bullets + 右侧 highlight 卡片。
- three-column：三栏卡片，每栏有 title + bullets。
- timeline：水平时间轴，steps 字段每个节点含 label + description。
- team：团队介绍，members 字段每个成员含 name + role。
- data-cards：KPI 数字卡片，stats 字段每个含 value + label + note。
- comparison：左右对比，left/right 各含 title + bullets。
- quote：金句页，quote + source。
- image-left / image-right：图文混排，image + bullets。
- chart：数据图表，chart_type(bar/line/pie) + labels + series + insights。

要求：
1. 总页数控制在 {pages} 页左右。
2. 内容页 bullets 数量 3-5 条，每条简洁有力，使用中文。
3. 数据页必须包含 chart_type、labels、series、insights；数据可以基于主题合理虚构，但要显得真实。
4. 根据内容选择最合适的 layout，使 PPT 视觉丰富但不杂乱。
5. 主题引用已经在 DPPT Pro 主题中定义，不要在大纲中写 `$` 引用。
6. 不要输出任何 YAML 以外的文字。
"""

    @staticmethod
    def _parse_outline(raw: str) -> Dict[str, Any]:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:yaml|yml)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            raw = raw.strip()
        try:
            data = yaml.safe_load(raw)
        except Exception as e:
            raise AiGeneratorError(f"AI 返回内容 YAML 解析失败：{e}\n原始内容：{raw[:500]}") from e

        if not isinstance(data, dict):
            raise AiGeneratorError(f"AI 返回内容不是有效的 YAML mapping：{raw[:500]}")
        if "slides" not in data:
            raise AiGeneratorError(f"AI 返回的 YAML 缺少 slides 字段：{raw[:500]}")
        return data


def generate_from_prompt(
    topic: str,
    output_path: str,
    pages: int = 6,
    style: str = "business",
    audience: Optional[str] = None,
    extra: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """一键生成 .dppt 文件并保存到指定路径。"""
    gen = AiDslGenerator(api_key=api_key, model=model)
    outline = gen.generate_outline(topic, pages, style, audience, extra)

    from scripts.outline_to_dppt import convert

    doc = convert(outline)

    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(doc, f, allow_unicode=True, sort_keys=False, width=120)

    return output_path
