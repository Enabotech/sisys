"""基础设施层 EIP 隔离状态 Redis 仓储模块（Story 5.4 — EIP 弹性隔离协议基础）

实现领域层 IsolationRepository 端口：Agent EIP 隔离状态的 Redis 持久化
（RedisAgentRepository 同款模式照抄——Story 5.4 DC-1）。

存储形态（对齐 RedisAgentRepository 先例）:
- 键 sisys:isolation:{agent_id}（build_key("isolation", ...)——独立键空间，
  与 sisys:agent:{agent_id} 并存互不侵入）
- Redis Hash 单 field `latest` 承载全字段 JSON blob——hset 与 expire 经
  MULTI/EXEC pipeline 原子提交
- 序列化：json_dumps（UUID→str、Enum→value、datetime→ISO）；
  _hash_to_state 显式重建 UUID/IsolationLevel/datetime（调用方重建责任）

错误契约:
- TTL 防御性校验：整数 + 闭区间 60~2592000，违规抛 AgentConfigError(440)——
  与 RedisAgentRepository.save 同款（范围数字对齐 RedisSnapshotStore.set_ttl）
- 连接/写入故障包装 StorageError 向上传播（禁静默吞异常；cause 经构造参数
  传递——from exc 仅设 __cause__ 不够，5-1 Task 3 实测教训）
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from src.domain.entities.isolation_state import IsolationState
from src.domain.events.enums import IsolationLevel
from src.domain.exceptions import AgentConfigError, StorageError
from src.domain.ports.isolation_repository import IsolationRepository
from src.domain.value_objects.agent_config import STATE_TTL_MAX_SECONDS, STATE_TTL_MIN_SECONDS
from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.utils import json_dumps, json_loads

if TYPE_CHECKING:
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter

logger = logging.getLogger(__name__)


class RedisIsolationRepository(IsolationRepository):
    """EIP 隔离状态 Redis 仓储（IsolationRepository 端口的 infrastructure 实现）

    组合 RedisAdapter（Rule 3——通用操作走 adapter 委托，Hash 操作
    hset/hget/expire 走 adapter.raw_client）。
    """

    _ISOLATION_NAMESPACE = "isolation"

    def __init__(self, adapter: RedisAdapter) -> None:
        """初始化仓储

        Args:
            adapter: Redis KV 适配器（组合根注入 redis_adapter SINGLETON；
                测试可注入场景级客户端包装的适配器）
        """
        self._adapter = adapter

    async def save(self, state: IsolationState, ttl: int) -> None:
        """保存隔离状态（upsert 语义，单 field latest JSON blob + TTL）

        hset 与 expire 经 MULTI/EXEC pipeline 原子提交——两命令分离时进程在
        两者之间崩溃会留下永不过期的孤儿键（对齐 RedisAgentRepository 先例）。

        Args:
            state: EIP 隔离状态实体
            ttl: 状态 TTL 秒（真源 AgentConfig.state_ttl；防御性校验：
                整数 + 闭区间 60~2592000）

        Raises:
            AgentConfigError: TTL 非整数或越界（EXCEPTION_440）
            StorageError: Redis 连接/写入故障（不静默）
        """
        if isinstance(ttl, bool) or not isinstance(ttl, int):
            raise AgentConfigError(
                reason=f"state_ttl 必须为整数（实际类型 {type(ttl).__name__}）",
            )
        if not STATE_TTL_MIN_SECONDS <= ttl <= STATE_TTL_MAX_SECONDS:
            raise AgentConfigError(
                reason=f"state_ttl 必须在 {STATE_TTL_MIN_SECONDS}~{STATE_TTL_MAX_SECONDS} 秒范围内（实际 {ttl}）",
            )

        key = build_key(self._ISOLATION_NAMESPACE, str(state.agent_id))
        try:
            hash_data = self._state_to_hash(state)
            async with self._adapter.raw_client.pipeline(transaction=True) as pipe:
                pipe.hset(key, "latest", json_dumps(hash_data))
                pipe.expire(key, ttl)
                await pipe.execute()
            logger.debug("Saved isolation state: agent_id=%s ttl=%d", state.agent_id, ttl)
        except Exception as exc:
            logger.error("Failed to save isolation state: agent_id=%s error=%s", state.agent_id, exc)
            raise StorageError(f"Failed to save isolation state: {exc}", cause=exc) from exc

    async def get_by_agent_id(self, agent_id: uuid.UUID) -> IsolationState | None:
        """按 agent_id 读取并重建隔离状态（键不存在返回 None）

        Raises:
            StorageError: Redis 连接/读取故障（不静默——确定性读取）
        """
        key = build_key(self._ISOLATION_NAMESPACE, str(agent_id))
        try:
            raw = await self._adapter.raw_client.hget(key, "latest")
            if raw is None:
                return None
            return self._hash_to_state(json_loads(raw))
        except Exception as exc:
            logger.error("Failed to load isolation state: agent_id=%s error=%s", agent_id, exc)
            raise StorageError(f"Failed to load isolation state: {exc}", cause=exc) from exc

    async def delete(self, agent_id: uuid.UUID) -> None:
        """删除隔离状态键（幂等）

        Raises:
            StorageError: Redis 连接/删除故障
        """
        key = build_key(self._ISOLATION_NAMESPACE, str(agent_id))
        try:
            await self._adapter.raw_client.delete(key)
        except Exception as exc:
            logger.error("Failed to delete isolation state: agent_id=%s error=%s", agent_id, exc)
            raise StorageError(f"Failed to delete isolation state: {exc}", cause=exc) from exc

    async def exists(self, agent_id: uuid.UUID) -> bool:
        """查询隔离状态键是否存在

        Raises:
            StorageError: Redis 连接故障
        """
        key = build_key(self._ISOLATION_NAMESPACE, str(agent_id))
        try:
            return bool(await self._adapter.raw_client.exists(key))
        except Exception as exc:
            logger.error("Failed to check isolation state existence: agent_id=%s error=%s", agent_id, exc)
            raise StorageError(f"Failed to check isolation state existence: {exc}", cause=exc) from exc

    @staticmethod
    def _state_to_hash(state: IsolationState) -> dict[str, str]:
        """实体 → Hash 原始字段（全 str：UUID→str、Enum→value、datetime→ISO）

        Args:
            state: EIP 隔离状态实体

        Returns:
            全部字段值为 str 的字典（经 json_dumps 整体序列化写入 latest field）
        """
        return {
            "agent_id": str(state.agent_id),
            "current_level": state.current_level.value,
            "initialized_at": state.initialized_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
            "last_trigger_reason": state.last_trigger_reason,
        }

    @staticmethod
    def _hash_to_state(data: dict[str, Any]) -> IsolationState:
        """Hash 原始字段 → 实体（显式重建 UUID/IsolationLevel/datetime）

        Args:
            data: json_loads 还原的原始字典（类型未还原——本方法负责全部重建）

        Returns:
            IsolationState 实体（字段类型与写入前一致）
        """
        return IsolationState(
            agent_id=uuid.UUID(data["agent_id"]),
            current_level=IsolationLevel(data["current_level"]),
            initialized_at=datetime.fromisoformat(data["initialized_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            last_trigger_reason=data["last_trigger_reason"],
        )


__all__ = ["RedisIsolationRepository"]
