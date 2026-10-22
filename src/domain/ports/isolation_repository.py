"""领域层 EIP 隔离状态仓储端口模块（Story 5.4 — EIP 弹性隔离协议基础）

EIP 隔离状态聚合的仓储抽象（R1 领域层基础端口——AgentRepository 同款先例）。
Redis 实现（RedisIsolationRepository）在 infrastructure 层，经组合根注册为
`isolation_repository`（SINGLETON——DC-7：无状态仓储构造零 IO，被 SINGLETON
服务捕获无 captive 实害，D7 评估从源头避免）。

设计决策（Story 5.4 DC-1）:
- 独立键空间 sisys:isolation:{agent_id}（与 sisys:agent:{agent_id} 并存互不
  侵入）——隔离状态有独立生命周期（切换/过期）与独立读写面（检查入口
  P95 计时锚），与 Agent 实体状态机解耦
- save(state, ttl) 的 TTL 为必填参数：真源 AgentConfig.state_ttl（隔离键
  TTL 与 Agent 键同源——DC-9），仓储签名无默认值避免双真源；
  范围 60~2592000 防御性二次校验抛 AgentConfigError(EXCEPTION_440)
- get_by_agent_id 命名对齐项目仓储端口主流命名（单字段标识查找用直接参数）

本端口无专属异常契约：TTL 越界抛 AgentConfigError(440，配置参数越界语义)、
存储连接故障由实现包装 StorageError(103) 向上传播（禁静默）。
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from src.domain.entities.isolation_state import IsolationState


@runtime_checkable
class IsolationRepository(Protocol):
    """EIP 隔离状态仓储端口（领域层，Story 5.4 新增）

    基本操作（按 agent_id UUID 主键索引，键空间 sisys:isolation:*）:
    - save: insert-or-update（幂等覆盖，TTL 重置为本次值）
    - get_by_agent_id: 主键查找，不存在返回 None
    - delete: 幂等删除
    - exists: 键存在性
    """

    async def save(self, state: IsolationState, ttl: int) -> None:
        """保存隔离状态（upsert 语义，带 TTL 过期）

        Args:
            state: EIP 隔离状态实体
            ttl: 状态 TTL 秒（必填——真源 AgentConfig.state_ttl；
                防御性校验闭区间 60~2592000）

        Raises:
            AgentConfigError: TTL 越界（EXCEPTION_440）
            StorageError: Redis 连接/写入故障（EXCEPTION_103，不静默）
        """
        ...

    async def get_by_agent_id(self, agent_id: uuid.UUID) -> IsolationState | None:
        """按 agent_id 查询（主键查找）

        Args:
            agent_id: 归属 Agent 唯一标识

        Returns:
            IsolationState 实体（UUID/IsolationLevel/datetime 显式重建）；
            键不存在返回 None

        Raises:
            StorageError: Redis 连接/读取故障
        """
        ...

    async def delete(self, agent_id: uuid.UUID) -> None:
        """删除隔离状态键（幂等，键不存在不抛错）

        Raises:
            StorageError: Redis 连接/删除故障
        """
        ...

    async def exists(self, agent_id: uuid.UUID) -> bool:
        """查询隔离状态键是否存在

        Raises:
            StorageError: Redis 连接故障
        """
        ...


__all__ = ["IsolationRepository"]
