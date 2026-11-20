"""JSON 输出格式化器

序列化策略冻结（Story 7-1 R2-1）：``json.dumps(payload, default=str,
ensure_ascii=False)``——命令对象/结果 DTO 含 UUID/Decimal/datetime 字段时
经 ``default=str`` 统一降维（UUID→hex 串、Decimal→十进制串）；中文原样
输出非 ``\\u`` 转义（LLM 直接消费可读性）。空列表契约：输出 ``[]``。
"""

from __future__ import annotations

import json
from typing import Any


def render(payload: Any) -> str:
    """将载荷渲染为合法 JSON 单文档字符串。

    Args:
        payload: 命令结果载荷（dict 或 list[dict]，可含 UUID/Decimal/datetime 字段）

    Returns:
        JSON 字符串（ensure_ascii=False，default=str 降维非原生类型）
    """
    return json.dumps(payload, default=str, ensure_ascii=False)
