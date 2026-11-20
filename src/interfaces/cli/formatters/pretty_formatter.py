"""美化输出格式化器

终端美化输出（分组+缩进）：dict 每键一行（嵌套 dict 递归缩进两空格），
list 每条独立分组。空态契约：空列表/空 dict 输出空态提示语。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_EMPTY_HINT = "（无数据）"
_INDENT = "  "


def _render_value(key: str, value: Any, depth: int, lines: list[str]) -> None:
    """递归渲染键值（嵌套 Mapping 缩进呈现，其余值 str 展平）。"""
    prefix = _INDENT * depth
    if isinstance(value, Mapping):
        lines.append(f"{prefix}{key}:")
        for inner_key, inner_value in value.items():
            _render_value(inner_key, inner_value, depth + 1, lines)
    else:
        text = value if isinstance(value, str) else str(value)
        lines.append(f"{prefix}{key}: {text}")


def render(payload: Any) -> str:
    """将载荷渲染为终端美化文本（分组+缩进）。

    Args:
        payload: dict 载荷（每键一行分组）或 list[dict] 载荷（每条独立分组）；
            空载荷输出空态提示语

    Returns:
        美化文本字符串
    """
    if isinstance(payload, Mapping):
        if not payload:
            return _EMPTY_HINT
        lines: list[str] = []
        for key, value in payload.items():
            _render_value(key, value, 0, lines)
        return "\n".join(lines)
    if isinstance(payload, Sequence):
        records = list(payload)
        if not records:
            return _EMPTY_HINT
        blocks: list[str] = []
        for idx, item in enumerate(records, start=1):
            if isinstance(item, Mapping):
                item_lines: list[str] = []
                for key, value in item.items():
                    _render_value(key, value, 0, item_lines)
                blocks.append(f"--- 第 {idx} 条 ---\n" + "\n".join(item_lines))
            else:
                blocks.append(f"--- 第 {idx} 条 ---\n{item if isinstance(item, str) else str(item)}")
        return "\n".join(blocks)
    return str(payload)
