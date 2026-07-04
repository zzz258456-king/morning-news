"""
调用 Anthropic Claude API 生成结构化 PPT 内容。
"""

import json
import os
from typing import Any

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
MAX_TOKENS = 4096


class ClaudeServiceError(Exception):
    pass


def _get_client():
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ClaudeServiceError("未配置 ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=api_key)


def generate_slide_content(config: dict) -> dict[str, Any]:
    """根据项目配置生成每页结构化内容。

    返回结构示例：
    {
      "title": "硅量子点研究进展",
      "slides": [
        {
          "page_id": "page_1",
          "title": "研究背景",
          "bullets": ["量子计算需求", "硅基材料优势"],
          "layout": "title-bullets-right-image",
          "image_prompt": "silicon quantum dots abstract illustration"
        }
      ]
    }
    """
    client = _get_client()

    slides = config.get("slides", [])
    outline = config.get("outline", [])
    template = config.get("template", {})
    title = config.get("title", "未命名")

    slides_input = []
    for s in slides:
        slides_input.append({
            "page_id": s.get("page_id", ""),
            "title": s.get("title", ""),
            "body": s.get("body", ""),
            "notes": s.get("notes", ""),
            "has_image": bool(s.get("image")),
        })

    prompt = f"""你是一位专业的 PPT 内容设计师。请根据用户提供的主题、大纲和页面草稿，生成一份结构化 PPT 内容。

主题：{title}

模板信息：
- 名称：{template.get('name', '默认')}
- 配色：{', '.join(template.get('colors', []))}
- 比例：{template.get('layout', '16:9')}

页面草稿（共 {len(slides_input)} 页）：
{json.dumps(slides_input, ensure_ascii=False, indent=2)}

请严格输出一个 JSON 对象，不要包含任何 Markdown 代码块标记或其他说明文字。JSON 格式如下：
{{
  "title": "PPT 总标题",
  "slides": [
    {{
      "page_id": "page_1",
      "title": "该页标题",
      "bullets": ["要点1", "要点2", "要点3"],
      "layout": "title-bullets-right-image",
      "image_prompt": "用于搜索配图的关键词，英文"
    }}
  ]
}}

要求：
1. 每页必须保留原始 page_id，title 和 bullets 使用中文。
2. bullets 数量 2-5 条，每条简洁有力。
3. layout 从以下选项中选择：
   - title-bullets-right-image：标题+左侧要点+右侧图片
   - title-bullets-left-image：标题+右侧要点+左侧图片
   - title-bullets-only：标题+纯文字要点
   - title-image-banner：标题+横幅大图+下方要点
   - title-center：居中标题页（用于封面）
4. image_prompt 用英文描述，便于后续搜索无版权图片；如果原页面没有图片，可留空字符串。
5. 不要改变页面顺序和 page_id。
"""

    try:
        message = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = _extract_text_from_message(message)
        return _extract_json(raw)
    except Exception as e:
        import anthropic
        if isinstance(e, anthropic.APIError):
            raise ClaudeServiceError(f"Anthropic API 错误：{e}")
        if isinstance(e, json.JSONDecodeError):
            raise ClaudeServiceError(f"Claude 返回内容 JSON 解析失败：{e}")
        raise ClaudeServiceError(f"调用 Claude 失败：{e}")


def recommend_templates(title: str, outline: list[dict]) -> list[dict]:
    """基于标题和大纲生成推荐模板名称与配色建议。"""
    client = _get_client()

    prompt = f"""你是一位 PPT 设计顾问。请根据以下 PPT 主题和大纲，推荐 2 套配色方案。

主题：{title}
大纲：{', '.join(p.get('title', '') for p in outline)}

请严格输出 JSON 数组，不要包含 Markdown 代码块标记：
[
  {{
    "name": "模板中文名",
    "colors": ["#主色", "#辅色", "#强调色", "#背景色"]
  }},
  {{
    "name": "模板中文名2",
    "colors": ["#主色", "#辅色", "#强调色"]
  }}
]
"""

    try:
        message = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = _extract_text_from_message(message)
        return _extract_json(raw)
    except Exception as e:
        raise ClaudeServiceError(f"推荐模板失败：{e}")


def _extract_text_from_message(message) -> str:
    """从 Claude 消息响应中提取第一个文本块内容，兼容 thinking 块。"""
    for block in message.content:
        if getattr(block, "type", None) == "text" and hasattr(block, "text"):
            return block.text
    raise ClaudeServiceError("Claude 返回内容中未找到文本块")


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3].strip()
    return json.loads(text)
