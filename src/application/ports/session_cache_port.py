"""SessionCachePort — 会话缓存端口（应用层）。

继承 L1CachePort，添加会话状态 save/load 语义。

注意: SemanticCache 的 get(query_embedding, threshold) 签名与
L1CachePort.get(memory_type, owner_id, name) 不兼容，不能继承。
SemanticCache 作为独立应用端口存在。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.ports.l1_cache import L1CachePort


@runtime_checkable
class SessionCachePort(L1CachePort, Protocol):
    """会话缓存端口 — 继承L1CachePort，添加会话管理语义。

    继承所有L1方法，额外提供：
    - 会话状态save/load语义
    - 会话TTL管理
    """

    async def save_session(
        self,
        session_id: str,
        agent_id: str,
        state: dict,
        ttl: int = 86400,
    ) -> None:
        """保存会话状态。

        Args:
            session_id: 会话 ID
            agent_id: Agent ID
            state: 会话状态字典
            ttl: TTL 秒数（默认 86400 = 24h）
        """

    async def load_session(self, session_id: str) -> dict | None:
        """加载会话状态。

        Args:
            session_id: 会话 ID

        Returns:
            会话状态字典，不存在返回 None
        """

    async def delete_session(self, session_id: str) -> None:
        """删除会话。

        Args:
            session_id: 会话 ID
        """

    async def session_exists(self, session_id: str) -> bool:
        """检查会话是否存在。

        Args:
            session_id: 会话 ID

        Returns:
            True 如果存在，False 否则
        """
