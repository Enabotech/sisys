"""JSON 格式化器（Story 7-1——AC-2 输出格式面 json 态）。

单行紧凑 JSON（ensure_ascii=False 中文原样）——stdout 唯一内容可被
``json.loads`` 直接解析（LLM Agent pipe 消费契约——P1 原则）。
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any


def build_envelope(
    command: str,
    data: dict[str, Any],
    *,
    ok: bool = True,
    mock: bool = False,
    echo: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造统一输出信封（Task 0.3 冻结契约）。

    骨架: ``{"ok": bool, "command": str, "data": {...}, "mock": bool}``；
    mock 时附 ``"echo"`` 参数回显。错误形态不进信封（沿用
    ``[EXCEPTION_code] message`` stderr + exit 1 定式）。

    Args:
        command: 命令全名（如 "sisys document upload"）
        data: CLI 视图 dict 最小字段载荷（白名单原则——REST DTO 同构）
        ok: 执行状态（True=成功）
        mock: 模拟模式标记（--mock 时 True）
        echo: mock 模式参数回显（仅 mock 时携带）

    Returns:
        统一信封 dict
    """
    envelope: dict[str, Any] = {"ok": ok, "command": command, "data": data, "mock": mock}
    if mock:
        envelope["echo"] = echo or {}
    return envelope


def _json_default(value: Any) -> str:
    """json.dumps default 回调（R1-F15——非 JSON 原生类型的兜底序列化）。

    Enum 成员先取 ``.value``（防 ``Class.MEMBER`` 形态泄漏——非 str-Enum 未来
    新增时的防御分支）；其余形态（datetime/UUID 等）``str()`` 兜底。

    Args:
        value: json.dumps 无法原生序列化的对象

    Returns:
        字符串形态（Enum 为 value，其他为 str()）
    """
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def render_json(envelope: dict[str, Any]) -> str:
    """渲染信封为单行紧凑 JSON（ensure_ascii=False）。

    Args:
        envelope: build_envelope 构造的统一信封

    Returns:
        单行 JSON 字符串（无换行——pipe 消费友好）
    """
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"), default=_json_default)
