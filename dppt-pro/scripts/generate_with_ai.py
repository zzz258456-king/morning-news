"""
AI 一键生成 PPTX

用法：
    python scripts/generate_with_ai.py "主题" output.pptx --pages 6 --style business
"""

import argparse
import os
import sys
from pathlib import Path

# 让脚本可以从 scripts/ 目录直接运行并导入 dppt 包
sys.path.insert(0, str(Path(__file__).parent.parent))

from dppt import DpptChecker, DpptRenderer, load_dppt
from dppt.ai_generator import generate_from_prompt


def main(argv=None):
    parser = argparse.ArgumentParser(description="AI 一键生成 PPTX")
    parser.add_argument("topic", help="PPT 主题/需求描述")
    parser.add_argument("output", help="输出 .pptx 文件路径")
    parser.add_argument("--pages", type=int, default=6, help="页数（默认 6）")
    parser.add_argument("--style", default="business", help="主题风格 business/tech/academic")
    parser.add_argument("--audience", help="目标受众")
    parser.add_argument("--extra", help="补充要求")
    parser.add_argument("--model", help="Claude 模型名称")
    parser.add_argument(
        "--keep-dppt",
        help="保留中间 .dppt 文件路径（可选）",
    )
    args = parser.parse_args(argv)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[错误] 请先设置环境变量 ANTHROPIC_API_KEY", file=sys.stderr)
        return 1

    dppt_path = args.keep_dppt or os.path.join(
        os.path.dirname(os.path.abspath(args.output)),
        os.path.splitext(os.path.basename(args.output))[0] + ".dppt",
    )

    try:
        print(f"[生成] 正在根据主题生成 DSL: {args.topic}")
        generate_from_prompt(
            topic=args.topic,
            output_path=dppt_path,
            pages=args.pages,
            style=args.style,
            audience=args.audience,
            extra=args.extra,
            model=args.model,
        )
        print(f"[保存] DSL 已保存: {dppt_path}")
    except Exception as e:
        print(f"[错误] 生成 DSL 失败: {e}", file=sys.stderr)
        return 1

    try:
        doc = load_dppt(dppt_path)
        ok, issues = DpptChecker.quick_check(doc)
        for issue in issues:
            print(f"[{issue.level.upper()}] 第 {issue.page_index} 页 {issue.element_id or ''}: {issue.message}")
        if not ok:
            print("[错误] 文档检查未通过，中止渲染。", file=sys.stderr)
            return 1

        renderer = DpptRenderer(doc)
        renderer.render(args.output)
        print(f"[成功] PPTX 已生成: {args.output}")
    except Exception as e:
        print(f"[错误] 渲染失败: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
