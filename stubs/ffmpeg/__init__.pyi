"""PEP 561 类型存根：ffmpeg-python

仅覆盖 SISYS 项目实际使用的 API 面：
- ffmpeg.probe(filename) — 探测媒体文件元数据
"""

from typing import Any

def probe(filename: str, **kwargs: Any) -> dict[str, Any]:
    """探测媒体文件元数据

    Args:
        filename: 媒体文件路径

    Returns:
        包含 format/streams 等信息的字典
    """
    ...
