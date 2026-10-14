"""领域层 Agent 仓储端口模块（Story 5-1 — CEO Agent 实例化 MVP）

Agent 聚合根的仓储抽象（R1 领域层基础端口）。
Redis 实现（RedisAgentRepository）在 infrastructure 层，经组合根注册为
`agent_repository`（SCOPED）。

设计决策：
- 独立 Protocol，不继承 L2RdbPort（Agent 状态持久化在 Redis L1 键空间，
  键 sisys:agent:{agent_id}，无 PG 泛型基座收益——对齐
  debate_session_repository 独立 Protocol 先例）
- save(agent, ttl) 的 TTL 为必填参数：Agent 实体无 TTL 载体（复用不修改），
  持久化策略由调用方显式声明（AgentConfig.state_ttl 是唯一默认值真源，
  仓储签名无默认值避免双真源，DC-8）；范围 60~2592000 防御性二次校验
  抛 AgentConfigError(EXCEPTION_440)
- get_by_id 命名对齐项目仓储端口主流命名（单字段标识查找用直接参数——
  CLAUDE.md §4 端口查询参数决策规则）

本端口无专属异常契约：TTL 越界抛 AgentConfigError(440，配置参数越界语义)、
存储连接故障由实现包装 StorageError(103) 向上传播（禁静默——与
RedisSessionStorage 优雅降级语义刻意区分）。
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from src.domain.entities.agent import Agent


@runtime_checkable
class AgentRepository(Protocol):
    """Agent 聚合仓储端口（领域层，Story 5-1 新增）

    基本操作（按 agent_id UUID 主键索引，键空间 sisys:agent:*）：
    - save: insert-or-update（幂等覆盖，TTL 重置为本次值）
    - get_by_id: 主键查找，不存在返回 None
    - delete: 幂等删除
    - exists: 键存在性
    """

    async def save(self, agent: Agent, ttl: int) -> None:
        """保存 Agent 实体（upsert 语义，带 TTL 过期）

        Args:
            agent: Agent 聚合根实体
            ttl: 状态 TTL 秒（必填——调用方从 AgentConfig.state_ttl 显式传入；
                防御性校验闭区间 60~2592000）

        Raises:
            AgentConfigError: TTL 越界（EXCEPTION_440）
            StorageError: Redis 连接/写入故障（EXCEPTION_103，不静默）
        """
        ...

    async def get_by_id(self, agent_id: uuid.UUID) -> Agent | None:
        """按 agent_id 查询（主键查找）

        Args:
            agent_id: Agent 唯一标识

        Returns:
            Agent 实体（UUID/Enum/datetime 显式重建）；键不存在返回 None

        Raises:
            StorageError: Redis 连接/读取故障
        """
        ...

    async def delete(self, agent_id: uuid.UUID) -> None:
        """删除 Agent 状态键（幂等，键不存在不抛错）

        Raises:
            StorageError: Redis 连接/删除故障
        """
        ...

    async def exists(self, agent_id: uuid.UUID) -> bool:
        """查询 Agent 状态键是否存在

        Raises:
            StorageError: Redis 连接故障
        """
        ...


__all__ = ["AgentRepository"]
