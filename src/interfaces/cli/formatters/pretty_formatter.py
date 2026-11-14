"""人类可读格式化器（Story 7-1——AC-2 输出格式面 pretty 态/缺省态）。

多行中文键值渲染（既有 print 形态——整合命令沿用 agent_cli ``_print_*``
既有渲染，本渲染器服务新命令 document/tool/archive 的 pretty 态）。
"""

from __future__ import annotations

from typing import Any


def render_pretty(data: dict[str, Any]) -> str:
    """渲染数据 dict 为人类可读多行文本。

    标量键值逐行 ``键: 值``；嵌套 list[dict] 逐项缩进渲染（清单语义）。

    Args:
        data: CLI 视图 dict（信封 data 载荷）

    Returns:
        多行中文文本
    """
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            lines.append(f"{key}:")
            for item in value:
                fields = " / ".join(f"{item_key}={item_value}" for item_key, item_value in item.items())
                lines.append(f"  - {fields}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)
