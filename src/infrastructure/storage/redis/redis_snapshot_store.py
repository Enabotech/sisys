"""SISYS 基础设施层 Redis 快照存储模块

基于 RedisAdapter 实现检查点快照仓储端口，
支持 TTL 过期和主从复制
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.exceptions import ValidationError
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.utils import json_dumps, json_loads

if TYPE_CHECKING:
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter

logger = logging.getLogger(__name__)


class RedisSnapshotStore(SnapshotRepositoryProtocol):
    """Redis 快照存储，实现 SnapshotRepositoryProtocol

    基于 Redis Hash 实现检查点快照仓储，支持 TTL 过期
    组合 RedisAdapter（Rule 3），通用操作走 adapter 委托，
    Hash 操作（hset/hget/expire）走 adapter.raw_client

    Attributes:
        _adapter: RedisAdapter 通用 KV 适配器实例
        _ttl_seconds: 默认 TTL 秒数（默认 24 小时）
    """

    _SNAPSHOT_NAMESPACE = "snapshot"

    def __init__(self, adapter: RedisAdapter) -> None:
        """初始化 Redis 快照存储

        Args:
            adapter: RedisAdapter 实例（通用 KV 适配器）
        """
        self._adapter = adapter
        self._ttl_seconds: int = 86400

    @staticmethod
    def _snapshot_to_hash(snapshot: CheckpointSnapshot) -> dict[str, str]:
        """将 CheckpointSnapshot 序列化为 Redis Hash 字段

        Args:
            snapshot: 检查点快照实体

        Returns:
            Redis Hash 字段字典
        """
        return {
            "snapshot_id": str(snapshot.snapshot_id),
            "session_id": snapshot.session_id,
            "stage_id": snapshot.stage_id,
            "state_version": str(snapshot.state_version),
            "state_data": json_dumps(snapshot.state_data),
            "timestamp": snapshot.timestamp.isoformat(),
            "ttl_seconds": str(snapshot.ttl_seconds),
        }

    @staticmethod
    def _hash_to_snapshot(data: dict[str, Any]) -> CheckpointSnapshot:
        """从 Redis Hash 字段反序列化为 CheckpointSnapshot

        Args:
            data: Redis Hash 字段字典

        Returns:
            检查点快照实体
        """
        return CheckpointSnapshot(
            snapshot_id=uuid.UUID(data["snapshot_id"]),
            session_id=data["session_id"],
            stage_id=data["stage_id"],
            state_version=int(data["state_version"]),
            state_data=json_loads(data["state_data"]) if isinstance(data["state_data"], str) else data["state_data"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            ttl_seconds=int(data["ttl_seconds"]),
        )

    def set_ttl(self, ttl_seconds: int) -> None:
        """设置快照默认 TTL

        Args:
            ttl_seconds: TTL 秒数（60 ~ 2592000）

        Raises:
            ValueError: TTL 超出允许范围
        """
        if ttl_seconds < 60 or ttl_seconds > 2592000:
            raise ValidationError(message="TTL must be between 60 seconds and 30 days")
        self._ttl_seconds = ttl_seconds

    async def save(self, snapshot: CheckpointSnapshot) -> None:
        """保存快照到 Redis

        Args:
            snapshot: 待持久化的检查点快照

        Raises:
            RuntimeError: Redis 操作失败
        """
        key = build_key(self._SNAPSHOT_NAMESPACE, snapshot.session_id)
        ttl = snapshot.ttl_seconds if snapshot.ttl_seconds > 0 else self._ttl_seconds

        try:
            hash_data = self._snapshot_to_hash(snapshot)
            await self._adapter.raw_client.hset(key, "latest", json_dumps(hash_data))
            await self._adapter.raw_client.expire(key, ttl)

            logger.debug(
                "Saved snapshot: session_id=%s version=%d ttl=%d",
                snapshot.session_id,
                snapshot.state_version,
                ttl,
            )

        except Exception as e:
            logger.error("Failed to save snapshot: session_id=%s error=%s", snapshot.session_id, e)
            raise RuntimeError(f"Failed to save snapshot: {e}") from e

    async def load(self, session_id: str) -> CheckpointSnapshot | None:
        """加载会话的最新快照

        Args:
            session_id: 会话标识

        Returns:
            最新快照，不存在返回 None
        """
        key = build_key(self._SNAPSHOT_NAMESPACE, session_id)

        try:
            data = await self._adapter.raw_client.hget(key, "latest")
            if data is None:
                logger.debug("No snapshot found: session_id=%s", session_id)
                return None

            hash_data = json_loads(data)
            snapshot = self._hash_to_snapshot(hash_data)

            logger.debug(
                "Loaded snapshot: session_id=%s version=%d",
                session_id,
                snapshot.state_version,
            )
            return snapshot

        except Exception as e:
            logger.error("Failed to load snapshot: session_id=%s error=%s", session_id, e)
            return None

    async def delete(self, session_id: str) -> None:
        """删除会话的快照

        Args:
            session_id: 会话标识

        Raises:
            RuntimeError: Redis 操作失败
        """
        key = build_key(self._SNAPSHOT_NAMESPACE, session_id)

        try:
            await self._adapter.delete(key)
            logger.debug("Deleted snapshot: session_id=%s", session_id)

        except Exception as e:
            logger.error("Failed to delete snapshot: session_id=%s error=%s", session_id, e)
            raise RuntimeError(f"Failed to delete snapshot: {e}") from e

    async def exists(self, session_id: str) -> bool:
        """检查快照是否存在

        Args:
            session_id: 会话标识

        Returns:
            存在返回 True，否则 False
        """
        key = build_key(self._SNAPSHOT_NAMESPACE, session_id)
        return await self._adapter.exists(key)
