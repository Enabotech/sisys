"""Redis Key Builder.

统一的 Redis 键构建器，确保所有键使用一致的命名空间格式。
"""

from __future__ import annotations

NAMESPACE = "sisys"


def build_key(namespace: str, *parts: str) -> str:
    """构建 Redis 键。

    Args:
        namespace: 命名空间（如 session, cache, blackboard）
        *parts: 键的其余部分

    Returns:
        格式化的 Redis 键：sisys:{namespace}:{parts 用 : 连接}
    """
    joined_parts = ":".join(parts)
    return f"{NAMESPACE}:{namespace}:{joined_parts}"
