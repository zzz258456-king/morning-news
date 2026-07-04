"""
DPPT Pro 命令行入口
"""

import argparse
import sys

from dppt import DpptChecker, DpptRenderer, load_dppt


def main(argv=None):
    parser = argparse.ArgumentParser(description="DPPT Pro - 商业级 PPT 生成引擎")
    parser.add_argument("input", help="输入 .dppt 文件路径")
    parser.add_argument("output", help="输出 .pptx 文件路径")
    parser.add_argument("--check", action="store_true", help="仅检查，不渲染")
    parser.add_argument("--theme", help="外部主题 YAML 路径（可选）")
    parser.add_argument("--master", help="PowerPoint 母版文件路径（可选）")
    args = parser.parse_args(argv)

    try:
        doc = load_dppt(args.input)
    except Exception as e:
        print(f"[错误] 解析 DSL 失败: {e}", file=sys.stderr)
        return 1

    ok, issues = DpptChecker.quick_check(doc)
    for issue in issues:
        print(f"[{issue.level.upper()}] 第 {issue.page_index} 页 {issue.element_id or ''}: {issue.message}")

    if args.check:
        return 0 if ok else 1

    if not ok:
        print("[错误] 文档存在严重问题，中止渲染。", file=sys.stderr)
        return 1

    renderer = DpptRenderer(doc)
    try:
        renderer.render(args.output, master_path=args.master)
        print(f"[成功] 已生成: {args.output}")
    except Exception as e:
        print(f"[错误] 渲染失败: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
