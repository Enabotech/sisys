"""JSON serialization utilities for Redis and message transport.

Handles types that Python's standard json module cannot serialize natively:
- datetime → ISO 8601 string
- UUID → string representation
- Enum → value
- bytes → string (UTF-8, fallback latin-1)
- set → list

Usage:
    from src.infrastructure.utils import json_dumps, json_loads

    data = json_dumps({"created_at": datetime.now(), "id": uuid.uuid4()})
    obj = json_loads(data)
"""

import json
import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any


class RedisJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime, UUID, Enum, bytes, and set types."""

    def default(self, o: Any) -> Any:
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, date):
            return o.isoformat()
        if isinstance(o, uuid.UUID):
            return str(o)
        if isinstance(o, Enum):
            return o.value
        if isinstance(o, bytes):
            try:
                return o.decode("utf-8")
            except UnicodeDecodeError:
                return o.decode("latin-1")
        if isinstance(o, set):
            return sorted(o)
        return super().default(o)


def json_dumps(obj: Any, **kwargs: Any) -> str:
    """Serialize object to JSON string with RedisJSONEncoder.

    Args:
        obj: Any Python object to serialize.
        **kwargs: Additional keyword arguments passed to json.dumps().

    Returns:
        JSON string representation.
    """
    return json.dumps(obj, cls=RedisJSONEncoder, **kwargs)


def json_loads(s: str | bytes, **kwargs: Any) -> Any:
    """Deserialize JSON string or bytes to Python object.

    Note: datetime and UUID strings are NOT automatically converted back
    to their original types. Callers should reconstruct typed objects
    from the deserialized dict.

    Args:
        s: JSON string or bytes to deserialize.
        **kwargs: Additional keyword arguments passed to json.loads().

    Returns:
        Deserialized Python object.
    """
    return json.loads(s, **kwargs)
