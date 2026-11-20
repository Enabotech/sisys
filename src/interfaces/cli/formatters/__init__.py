"""CLI 输出格式化器包

三态输出（AC-4）：json / table / pretty 按命令 ``--format`` 参数分发。
统一渲染入口签名 ``render(payload) -> str``（payload=dict 或 list[dict]）。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.domain.exceptions import ValidationError
from src.interfaces.cli.formatters import json_formatter, pretty_formatter, table_formatter

__all__ = ["get_formatter", "json_formatter", "pretty_formatter", "table_formatter"]


def get_formatter(fmt: str) -> Callable[[Any], str]:
    """按 format 值返回渲染函数（第二道防线——typer choice 守卫为第一道）。

    Args:
        fmt: 格式标识（json / table / pretty）

    Returns:
        对应格式化器的 render 函数

    Raises:
        ValidationError: EXCEPTION_201——未知格式值
    """
    formatters = {
        "json": json_formatter.render,
        "table": table_formatter.render,
        "pretty": pretty_formatter.render,
    }
    if fmt not in formatters:
        raise ValidationError(
            message=f"不支持的输出格式: {fmt!r}（可选值: json|table|pretty）",
            context={"format": fmt, "allowed": ("json", "table", "pretty")},
        )
    return formatters[fmt]
