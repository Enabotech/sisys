"""应用层工具版本管理服务端口（Story 4-6）

ToolVersionServicePort：R2 组合注入端口（组合注入 ToolVersionRepositoryPort
+ SchemaValidatorPort + ToolRegistryServicePort 三基础端口）。

7 方法集（Story SDD 端口清单——唯一事实源）：
- register_version：注册（含兼容性分级拦截 397/标记 canary_only）
- publish_version：状态感知发布（灰度发起/调档/直接全量/promote 转正）
- abort_canary：放弃灰度（STABLE 不动）
- rollback：一键回滚（防 ping-pong 缺省目标 + 430/433 分立）
- resolve_version：执行链路由（规范散列 + 惰性初始注册三分支）
- list_versions / get_version_traffic：查询
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable

from src.domain.entities.tool_version import ToolVersion


@runtime_checkable
class ToolVersionServicePort(Protocol):
    """工具版本管理服务端口（应用层组合注入端口）。"""

    async def register_version(
        self,
        tool_id: uuid.UUID,
        version: str,
        input_schema: dict,
        output_schema: dict,
    ) -> ToolVersion:
        """注册新版本（兼容性分级拦截：critical 拒绝 397 / major canary_only）。

        Args:
            tool_id: 工具 ID
            version: SemVer 版本号
            input_schema: 输入 Schema 快照
            output_schema: 输出 Schema 快照

        Returns:
            注册后的版本实体（PENDING）

        Raises:
            ToolNotFoundError: 工具不存在（380）
            ToolVersionAlreadyExistsError: 版本号重复（431）
            ToolSchemaCompatibilityError: critical 破坏性变更（397）
        """
        ...

    async def publish_version(
        self,
        tool_id: uuid.UUID,
        version: str,
        traffic_weight: int = 100,
    ) -> ToolVersion:
        """发布版本（状态感知：PENDING=发起灰度/直接全量；CANARY=调档/promote）。

        Args:
            tool_id: 工具 ID
            version: 版本号
            traffic_weight: 权重 (0,100]——<100 灰度档，=100 全量档

        Returns:
            发布后的版本实体

        Raises:
            ToolVersionNotFoundError: 版本不存在（430）
            ToolVersionTrafficWeightError: 权重非法/约束冲突/并存冲突（432）
            EntityStateTransitionError: 非法状态迁移（243）
        """
        ...

    async def abort_canary(self, tool_id: uuid.UUID) -> ToolVersion:
        """放弃灰度（活跃 CANARY → DEPRECATED，STABLE 不动）。

        Args:
            tool_id: 工具 ID

        Returns:
            被放弃的版本实体

        Raises:
            EntityStateTransitionError: 无活跃 CANARY（243）
        """
        ...

    async def rollback(
        self,
        tool_id: uuid.UUID,
        target_version: str | None = None,
        trigger: str = "api",
    ) -> ToolVersion:
        """一键回滚至历史稳定版本。

        Args:
            tool_id: 工具 ID
            target_version: 显式目标（缺省 = last_stable_at 最新且排除本次
                被降级版本——防 ping-pong）
            trigger: 触发来源（api/manual）

        Returns:
            恢复为 STABLE 的目标版本实体

        Raises:
            ToolVersionNotFoundError: 显式目标无记录（430）
            ToolVersionRollbackError: 无可回滚历史/目标非可回滚态（433）
        """
        ...

    async def resolve_version(
        self,
        tool_id: uuid.UUID,
        requested_version: str | None = None,
        route_key: str | None = None,
    ) -> ToolVersion:
        """执行链版本路由（规范散列确定性 + 惰性初始注册）。

        Args:
            tool_id: 工具 ID
            requested_version: 显式版本（跳过流量路由）
            route_key: 路由键（V1 = context.trace_id）

        Returns:
            路由命中的版本实体

        Raises:
            ToolVersionNotFoundError: 精确版本不存在或有记录无活跃（430）
        """
        ...

    async def list_versions(self, tool_id: uuid.UUID) -> list[ToolVersion]:
        """列出工具全部版本（注册时间升序）。"""
        ...

    async def get_version_traffic(self, tool_id: uuid.UUID) -> dict[str, Any]:
        """查询当前流量分布 {stable_version, canary_version, canary_weight}。"""
        ...


__all__ = ["ToolVersionServicePort"]
