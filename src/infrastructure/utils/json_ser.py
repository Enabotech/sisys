"""基础设施层 JSON 序列化工具模块

处理 Python 标准 json 模块无法原生序列化的类型：
- datetime → ISO 8601 字符串
- UUID → 字符串表示
- Enum → 值
- bytes → 字符串（UTF-8，回退 latin-1）
- set → 列表
"""

import json
import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any


class RedisJSONEncoder(json.JSONEncoder):
    """自定义 JSON 编码器，处理 datetime、UUID、Enum、bytes 和 set 类型"""

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
    """使用 RedisJSONEncoder 将对象序列化为 JSON 字符串

    Args:
        obj: 待序列化的 Python 对象
        **kwargs: 传递给 json.dumps() 的额外关键字参数

    Returns:
        JSON 字符串表示
    """
    return json.dumps(obj, cls=RedisJSONEncoder, **kwargs)


def json_loads(s: str | bytes, **kwargs: Any) -> Any:
    """将 JSON 字符串或字节反序列化为 Python 对象

    注意：datetime 和 UUID 字符串不会自动还原为原始类型，
    调用方应从反序列化后的字典中重建类型化对象

    Args:
        s: 待反序列化的 JSON 字符串或字节
        **kwargs: 传递给 json.loads() 的额外关键字参数

    Returns:
        反序列化后的 Python 对象
    """
    return json.loads(s, **kwargs)
