"""
Claude Code CLI 调用服务
MVP 阶段先预留接口，后续接入真实调用。
"""

import subprocess
from pathlib import Path


def call_claude(prompt: str, cwd: Path) -> str:
    """调用 Claude Code CLI 执行提示词"""
    # TODO: 接入真实的 claude 命令
    # result = subprocess.run(
    #     ["claude", prompt],
    #     cwd=str(cwd),
    #     capture_output=True,
    #     text=True,
    #     timeout=300,
    # )
    # return result.stdout
    return "[Claude 调用占位]"
