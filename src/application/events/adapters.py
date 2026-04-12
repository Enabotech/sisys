"""Event serialization adapters (application layer).

Uses Pydantic TypeAdapter for dict ↔ JSON boundary conversion.
Domain layer events use dataclasses.asdict() / DomainEvent.from_dict().
This adapter handles the JSON string conversion at the application layer boundary.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter

# TypeAdapter for dict ↔ JSON string conversion at application layer boundary
dict_adapter: TypeAdapter[dict[str, Any]] = TypeAdapter(dict[str, Any])


def event_dict_to_json(event_dict: dict[str, Any]) -> str:
    """Serialize event dict to JSON string using Pydantic TypeAdapter.

    Args:
        event_dict: Dictionary from DomainEvent.to_dict().

    Returns:
        JSON string representation.

    Raises:
        ValueError: If the dict cannot be serialized to JSON.
    """
    try:
        return dict_adapter.dump_json(event_dict).decode("utf-8")
    except Exception as e:
        raise ValueError(f"Failed to serialize event dict to JSON: {e}") from e


def json_to_event_dict(json_str: str) -> dict[str, Any]:
    """Deserialize JSON string to event dict using Pydantic TypeAdapter.

    Args:
        json_str: JSON string.

    Returns:
        Dictionary suitable for DomainEvent.from_dict().

    Raises:
        ValueError: If JSON string is invalid.
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON string: {e}") from e
    return dict_adapter.validate_python(data)
