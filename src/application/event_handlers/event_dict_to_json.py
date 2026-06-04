"""应用层事件序列化适配器模块

使用 Pydantic TypeAdapter 完成 dict ↔ JSON 边界转换
领域层事件使用 dataclasses.asdict() / DomainEvent.from_dict()，
本适配器处理应用层边界的 JSON 字符串转换
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter

from src.domain.exceptions import ValidationError

# TypeAdapter for dict ↔ JSON string conversion at application layer boundary
dict_adapter: TypeAdapter[dict[str, Any]] = TypeAdapter(dict[str, Any])


def event_dict_to_json(event_dict: dict[str, Any]) -> str:
    """将事件字典序列化为 JSON 字符串（使用 Pydantic TypeAdapter）

    Args:
        event_dict: 来自 DomainEvent.to_dict() 的字典

    Returns:
        JSON 字符串表示

    Raises:
        ValueError: 字典无法序列化为 JSON 时抛出
    """
    try:
        return dict_adapter.dump_json(event_dict).decode("utf-8")
    except Exception as e:
        raise ValidationError(message=f"Failed to serialize event dict to JSON: {e}") from e


def json_to_event_dict(json_str: str) -> dict[str, Any]:
    """将 JSON 字符串反序列化为事件字典（使用 Pydantic TypeAdapter）

    Args:
        json_str: JSON 字符串

    Returns:
        适用于 DomainEvent.from_dict() 的字典

    Raises:
        ValueError: JSON 字符串无效时抛出
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValidationError(message=f"Invalid JSON string: {e}") from e
    return dict_adapter.validate_python(data)
