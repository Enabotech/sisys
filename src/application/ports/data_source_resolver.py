"""应用层数据源解析编排端口模块（Story 4.1b）

R2 组合注入：DataSourceResolverPort 组合领域层 DataSourcePort 集合 +
L1CachePort 缓存，为 Engine.Execute 阶段提供白名单/缓存/新鲜度/并发采集能力。

实现位置：src/application/services/data_source_resolver.py
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from src.application.ports.skill_loader import ToolMetadata
from src.domain.ports.data_source import DataSourceQuery
from src.domain.value_objects.data_source import DataSourceResult


@runtime_checkable
class DataSourceResolverPort(Protocol):
    """数据源解析编排端口

    职责边界：
    - 白名单校验（name ∈ tool_metadata.data_sources，违规抛 BusinessRuleViolationError 207）
    - 缓存读/写（L1CachePort，按 DataSourceRef.ttl_seconds 失效；故障降级透传）
    - 新鲜度评分（DataFreshness 指数衰减 + stale 判定）
    - 并发采集（fetch_many：asyncio.gather 部分成功收敛；全部失败抛首个异常）
    - 事件发布（DataSourceFetched / DataSourceFetchFailed）
    """

    async def fetch(
        self,
        tool_metadata: ToolMetadata,
        name: str,
        query: str,
        *,
        tenant_id: uuid.UUID | str | None = None,
    ) -> DataSourceResult:
        """单源采集（白名单 → 缓存命中返回 → 适配器采集 → 写缓存 → 新鲜度评分）

        Args:
            tool_metadata: 工具元数据（白名单依据）
            name: 数据源名称
            query: 查询表达式
            tenant_id: 租户隔离标识（缓存键前缀）

        Returns:
            DataSourceResult（缓存命中时 cache_hit=True）

        Raises:
            BusinessRuleViolationError: name 未在 tool_metadata.data_sources 声明（207）
            DataSourceUnavailableError: 适配器未注册/数据源不可用（411）
            DataSourceRateLimitError: 限流（412）
            DataSourceResponseError: 响应解析失败（413）
            TimeoutError: 超时（302）
        """
        ...

    async def fetch_many(
        self,
        tool_metadata: ToolMetadata,
        requests: tuple[DataSourceQuery, ...],
        *,
        tenant_id: uuid.UUID | str | None = None,
        execution_id: uuid.UUID | None = None,
    ) -> tuple[DataSourceResult, ...]:
        """并发采集（asyncio.gather + return_exceptions 部分成功收敛）

        语义：
        - 白名单校验在并发采集**之前**统一执行（违规立即抛出，不采集任何源）
        - 单个源失败不阻断其他源（失败发布 DataSourceFetchFailed 事件）
        - **全部失败**（且有请求）时抛出首个异常（Engine 依此传播 412/413 等）

        Args:
            tool_metadata: 工具元数据（白名单依据）
            requests: DataSourceQuery 元组
            tenant_id: 租户隔离标识（requests 中 tenant_id 缺省时使用）
            execution_id: ToolExecution 聚合根 ID（事件 aggregate_id 关联，可选）

        Returns:
            成功源的 DataSourceResult 元组（保持请求顺序中的成功项）

        Raises:
            BusinessRuleViolationError: 任一 name 未声明（207）
            DataSourceError 子类: 全部源失败时抛首个异常
        """
        ...


__all__ = ["DataSourceResolverPort"]
