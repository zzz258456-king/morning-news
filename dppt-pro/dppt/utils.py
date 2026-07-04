"""
工具函数集合。
"""

from __future__ import annotations

import os
from typing import Optional


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def resolve_resource(src: str, base: Optional[str] = None) -> Optional[str]:
    if not src:
        return None
    if os.path.isabs(src) and os.path.exists(src):
        return src
    if base:
        candidate = os.path.join(base, src)
        if os.path.exists(candidate):
            return candidate
    return None


def truncate_text(text: str, max_length: int = 80) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
