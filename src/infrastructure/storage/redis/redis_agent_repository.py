"""基础设施层 Agent Redis 仓储模块（Story 5-1 — CEO Agent 实例化 MVP）

实现领域层 AgentRepository 端口：Agent 聚合状态的 Redis 持久化。

存储形态（对齐 RedisSnapshotStore 先例）：
- 键 sisys:agent:{agent_id}（build_key("agent", ...)）
- Redis Hash 单 field `latest` 承载全字段 JSON blob——hset 与 expire 经
  MULTI/EXEC pipeline 原子提交（非逐 field Hash，亦非两条独立命令）
- 序列化：json_dumps（UUID→str、Enum→value、datetime→ISO）；
  json_loads 不还原类型——_hash_to_agent 显式重建 AgentRole/AgentStatus/
  datetime/list[str]（调用方重建责任）

错误契约：
- TTL 防御性校验：整数 + 闭区间 60~2592000，违规抛 AgentConfigError(440)——
  范围数字对齐 RedisSnapshotStore.set_ttl，异常类型按 AC-3 语义为 440
- 连接/写入故障包装 StorageError 向上传播（对齐 RedisSnapshotStore.save
  先例，禁静默吞异常——与 RedisSessionStorage 优雅降级语义刻意区分）
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from src.domain.entities.agent import Agent, AgentRole, AgentStatus
from src.domain.exceptions import AgentConfigError, StorageError
from src.domain.ports.agent_repository import AgentRepository
from src.domain.value_objects.agent_config import STATE_TTL_MAX_SECONDS, STATE_TTL_MIN_SECONDS
from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.utils import json_dumps, json_loads

if TYPE_CHECKING:
    from src.infrastructure.storage.redis.redis_adapter import RedisAdapter

logger = logging.getLogger(__name__)


class RedisAgentRepository(AgentRepository):
    """Agent 聚合 Redis 仓储（AgentRepository 端口的 infrastructure 实现）

    组合 RedisAdapter（Rule 3——通用操作走 adapter 委托，Hash 操作
    hset/hget/expire 走 adapter.raw_client）。
    """

    _AGENT_NAMESPACE = "agent"

    def __init__(self, adapter: RedisAdapter) -> None:
        """初始化仓储

        Args:
            adapter: Redis KV 适配器（组合根注入 redis_adapter SINGLETON；
                测试可注入场景级客户端包装的适配器）
        """
        self._adapter = adapter

    async def save(self, agent: Agent, ttl: int) -> None:
        """保存 Agent 实体（upsert 语义，单 field latest JSON blob + TTL）

        hset 与 expire 经 MULTI/EXEC pipeline 原子提交——两命令分离时进程在
        两者之间崩溃会留下永不过期的孤儿键，击穿「非幂等 + TTL 自然回收」
        设计假设（对齐 semantic_cache pipeline 先例）。

        Args:
            agent: Agent 聚合根实体
            ttl: 状态 TTL 秒（防御性校验：整数 + 闭区间 60~2592000）

        Raises:
            AgentConfigError: TTL 非整数或越界（EXCEPTION_440）
            StorageError: Redis 连接/写入故障（不静默）
        """
        if isinstance(ttl, bool) or not isinstance(ttl, int):
            raise AgentConfigError(
                role=agent.role.value if isinstance(agent.role, AgentRole) else str(agent.role),
                config_path="",
                reason=f"state_ttl 必须为整数（实际类型 {type(ttl).__name__}）",
            )
        if not STATE_TTL_MIN_SECONDS <= ttl <= STATE_TTL_MAX_SECONDS:
            raise AgentConfigError(
                role=agent.role.value if isinstance(agent.role, AgentRole) else str(agent.role),
                config_path="",
                reason=f"state_ttl 必须在 {STATE_TTL_MIN_SECONDS}~{STATE_TTL_MAX_SECONDS} 秒范围内（实际 {ttl}）",
            )

        key = build_key(self._AGENT_NAMESPACE, str(agent.agent_id))
        try:
            hash_data = self._agent_to_hash(agent)
            async with self._adapter.raw_client.pipeline(transaction=True) as pipe:
                pipe.hset(key, "latest", json_dumps(hash_data))
                pipe.expire(key, ttl)
                await pipe.execute()
            logger.debug("Saved agent state: agent_id=%s ttl=%d", agent.agent_id, ttl)
        except Exception as exc:
            logger.error("Failed to save agent state: agent_id=%s error=%s", agent.agent_id, exc)
            raise StorageError(f"Failed to save agent state: {exc}", cause=exc) from exc

    async def get_by_id(self, agent_id: uuid.UUID) -> Agent | None:
        """按 agent_id 读取并重建实体（键不存在返回 None）

        Raises:
            StorageError: Redis 连接/读取故障（不静默——确定性读取，
            不采用优雅降级返回 None）
        """
        key = build_key(self._AGENT_NAMESPACE, str(agent_id))
        try:
            raw = await self._adapter.raw_client.hget(key, "latest")
            if raw is None:
                return None
            return self._hash_to_agent(json_loads(raw))
        except Exception as exc:
            logger.error("Failed to load agent state: agent_id=%s error=%s", agent_id, exc)
            raise StorageError(f"Failed to load agent state: {exc}", cause=exc) from exc

    async def delete(self, agent_id: uuid.UUID) -> None:
        """删除 Agent 状态键（幂等）

        Raises:
            StorageError: Redis 连接/删除故障
        """
        key = build_key(self._AGENT_NAMESPACE, str(agent_id))
        try:
            await self._adapter.raw_client.delete(key)
        except Exception as exc:
            logger.error("Failed to delete agent state: agent_id=%s error=%s", agent_id, exc)
            raise StorageError(f"Failed to delete agent state: {exc}", cause=exc) from exc

    async def exists(self, agent_id: uuid.UUID) -> bool:
        """查询 Agent 状态键是否存在

        Raises:
            StorageError: Redis 连接故障
        """
        key = build_key(self._AGENT_NAMESPACE, str(agent_id))
        try:
            return bool(await self._adapter.raw_client.exists(key))
        except Exception as exc:
            logger.error("Failed to check agent state existence: agent_id=%s error=%s", agent_id, exc)
            raise StorageError(f"Failed to check agent state existence: {exc}", cause=exc) from exc

    @staticmethod
    def _agent_to_hash(agent: Agent) -> dict[str, str]:
        """实体 → Hash 原始字段（全 str：UUID→str、Enum→value、datetime→ISO、list→JSON）

        Args:
            agent: Agent 聚合根实体

        Returns:
            全部字段值为 str 的字典（经 json_dumps 整体序列化写入 latest field）
        """
        return {
            "agent_id": str(agent.agent_id),
            "role": agent.role.value,
            "name": agent.name,
            "description": agent.description,
            "status": agent.status.value,
            "failure_reason": agent.failure_reason,
            "domain_knowledge": json_dumps(agent.domain_knowledge),
            "responsibilities": json_dumps(agent.responsibilities),
            "created_at": agent.created_at.isoformat(),
            "updated_at": agent.updated_at.isoformat(),
        }

    @staticmethod
    def _hash_to_agent(data: dict[str, Any]) -> Agent:
        """Hash 原始字段 → 实体（显式重建 UUID/Enum/datetime/list）

        Args:
            data: json_loads 还原的原始字典（类型未还原——本方法负责全部重建）

        Returns:
            Agent 聚合根实体（字段类型与写入前一致）
        """
        return Agent(
            agent_id=uuid.UUID(data["agent_id"]),
            role=AgentRole(data["role"]),
            name=data["name"],
            description=data["description"],
            status=AgentStatus(data["status"]),
            failure_reason=data["failure_reason"],
            domain_knowledge=json_loads(data["domain_knowledge"]),
            responsibilities=json_loads(data["responsibilities"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


__all__ = ["RedisAgentRepository"]
