"""应用层数据源解析编排服务（Story 4.1b — Skills 数据采集基础设施）

DataSourceResolverService 实现 DataSourceResolverPort（R2 组合注入）：
- 组合 DataSourcePort 适配器集合（composition_root 按 data_source_* 端口聚合注入）
- 复用 L1CachePort 缓存（禁止新建缓存端口；缓存键 build_key("cache", "datasource", ...)）
- 新鲜度评分（DataFreshness 指数衰减 + stale 判定 → 触发重采）
- 白名单校验（ToolMetadata.data_sources 声明为准）
- 事件发布（DataSourceFetched / DataSourceFetchFailed，双通道）
- 缓存故障降级：Redis 异常时透传采集，不阻断主流程
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Mapping

from src.application.ports.skill_loader import ToolMetadata
from src.domain.events.data_source_events import DataSourceFetched, DataSourceFetchFailed
from src.domain.exceptions import (
    BusinessRuleViolationError,
    DataSourceUnavailableError,
)
from src.domain.ports.data_source import DataSourcePort, DataSourceQuery
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.l1_cache import L1CachePort
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceRef,
    DataSourceResult,
)

logger = logging.getLogger(__name__)


def build_data_source_cache_key(tenant_id: uuid.UUID | str | None, source_name: str, query: str) -> str:
    """构建数据源缓存键（租户前缀隔离 + 查询哈希化）

    Args:
        tenant_id: 租户标识（None 归一化为 "global"）
        source_name: 数据源名称
        query: 查询表达式（SHA256 哈希化，避免原始 query 直接进入键）

    Returns:
        格式：sisys:cache:datasource:{tenant}:{source}:{query_hash16}
        （命名空间格式与 infrastructure/storage/redis/key_builder.build_key 输出一致；
        应用层禁止跨层 import infrastructure，此处内联构造保持依赖方向合规）
    """
    tenant = str(tenant_id) if tenant_id is not None else "global"
    query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
    return f"sisys:cache:datasource:{tenant}:{source_name}:{query_hash}"


class DataSourceResolverService:
    """数据源解析编排服务（白名单 + 缓存 + 并发 + 新鲜度 + 事件）

    Attributes:
        _adapters: 数据源名称 → DataSourcePort 适配器映射（Key 缺失的适配器不在其中）
        _cache: L1CachePort 缓存（Redis）
        _event_publisher: 事件发布端口（可选，None 时不发布事件）
    """

    def __init__(
        self,
        adapters: Mapping[str, DataSourcePort],
        cache: L1CachePort,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        """初始化编排服务

        Args:
            adapters: 数据源适配器映射（name → DataSourcePort）
            cache: L1 缓存端口（Redis KV）
            event_publisher: 事件发布端口（可选）
        """
        self._adapters = adapters
        self._cache = cache
        self._event_publisher = event_publisher

    # ===== 公开端口方法 =====

    async def fetch(
        self,
        tool_metadata: ToolMetadata,
        name: str,
        query: str,
        *,
        tenant_id: uuid.UUID | str | None = None,
        execution_id: uuid.UUID | None = None,
    ) -> DataSourceResult:
        """单源采集（白名单 → 缓存 → 适配器 → 写缓存 → 事件）"""
        allowed = self._check_whitelist(tool_metadata, name)
        cache_key = build_data_source_cache_key(tenant_id, name, query)

        # 第 1 步：缓存读（故障降级：异常时按未命中处理）
        cached = await self._read_cache(cache_key, allowed)
        if cached is not None:
            await self._publish_fetched(cached, query, execution_id=execution_id)
            return cached

        # 第 2 步：适配器采集
        adapter = self._adapters.get(name)
        if adapter is None:
            raise DataSourceUnavailableError(
                message=f"数据源 {name} 未注册（可能因 API Key 缺失被条件注册排除）",
                context={"source_name": name},
            )
        started = time.monotonic()
        result = await adapter.fetch(DataSourceQuery(source_name=name, query=query, tenant_id=tenant_id))
        latency_ms = (time.monotonic() - started) * 1000

        # 第 3 步：写缓存（故障降级：异常仅告警）
        await self._write_cache(cache_key, result, allowed.ttl_seconds)

        # 第 4 步：事件发布
        await self._publish_fetched(result, query, latency_ms=latency_ms, execution_id=execution_id)
        return result

    async def fetch_many(
        self,
        tool_metadata: ToolMetadata,
        requests: tuple[DataSourceQuery, ...],
        *,
        tenant_id: uuid.UUID | str | None = None,
        execution_id: uuid.UUID | None = None,
    ) -> tuple[DataSourceResult, ...]:
        """并发采集（白名单前置校验 + gather 部分成功收敛 + 全失败抛首个异常）"""
        # 白名单前置校验：任一违规立即抛出，不采集任何源
        for req in requests:
            self._check_whitelist(tool_metadata, req.source_name)

        if not requests:
            return ()

        outcomes = await asyncio.gather(
            *(
                self.fetch(
                    tool_metadata,
                    req.source_name,
                    req.query,
                    tenant_id=req.tenant_id or tenant_id,
                    execution_id=execution_id,
                )
                for req in requests
            ),
            return_exceptions=True,
        )

        results: list[DataSourceResult] = []
        first_error: Exception | None = None
        for req, outcome in zip(requests, outcomes, strict=True):
            if isinstance(outcome, DataSourceResult):
                results.append(outcome)
                continue
            # asyncio.gather(return_exceptions=True) 返回 BaseException（含 CancelledError）
            if isinstance(outcome, Exception):
                error = outcome
            else:
                error = DataSourceUnavailableError(
                    message=f"数据源 {req.source_name} 采集被中断（{type(outcome).__name__}）",
                    context={"source_name": req.source_name},
                )
            if first_error is None:
                first_error = error
            await self._publish_failed(req, error, execution_id=execution_id)

        if first_error is not None and not results:
            # 全部失败：抛首个异常（Engine 依此传播 412/413 等到调用方）
            raise first_error
        return tuple(results)

    # ===== 内部方法 =====

    def _check_whitelist(self, tool_metadata: ToolMetadata, name: str) -> DataSourceRef:
        """白名单校验（name ∈ tool_metadata.data_sources）

        Returns:
            匹配的 DataSourceRef（含 ttl_seconds 供缓存写）

        Raises:
            BusinessRuleViolationError: 未声明（EXCEPTION_207）
        """
        for ref in tool_metadata.data_sources:
            if ref.name == name:
                return ref
        raise BusinessRuleViolationError(
            message=f"数据源 {name} 未在工具 {tool_metadata.slug} 的 data_sources 白名单中声明",
            context={
                "source_name": name,
                "tool": tool_metadata.slug,
                "declared": [r.name for r in tool_metadata.data_sources],
            },
        )

    async def _read_cache(self, cache_key: str, ref: DataSourceRef) -> DataSourceResult | None:
        """读缓存（命中且未 stale → 重建 DataSourceResult；故障/未命中/stale → None）"""
        try:
            raw = await self._cache.get(cache_key)
        except Exception as e:
            logger.warning("数据源缓存读故障（降级透传采集）: %s", type(e).__name__)
            return None
        if raw is None:
            return None
        try:
            entry = json.loads(raw)
            source_ts = datetime.fromisoformat(entry["source_timestamp"])
            fetched_at = datetime.fromisoformat(entry["fetched_at"])
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("数据源缓存条目损坏（按未命中处理）: %s", type(e).__name__)
            return None

        freshness = DataFreshness(source_timestamp=source_ts, ttl_seconds=ref.ttl_seconds)
        if freshness.is_stale(datetime.now(UTC)):
            return None  # stale → 触发重采
        return DataSourceResult(
            source_name=ref.name,
            payload=entry["payload"],
            source_timestamp=source_ts,
            fetched_at=fetched_at,
            freshness=freshness,
            confidence=float(entry.get("confidence", 0.5)),
            cache_hit=True,
        )

    async def _write_cache(self, cache_key: str, result: DataSourceResult, ttl_seconds: int) -> None:
        """写缓存（故障仅告警，不阻断主流程）"""
        entry = {
            "payload": result.payload,
            "source_timestamp": result.source_timestamp.isoformat(),
            "fetched_at": result.fetched_at.isoformat(),
            "confidence": result.confidence,
        }
        try:
            await self._cache.set_with_ttl(cache_key, json.dumps(entry, ensure_ascii=False), ttl_seconds)
        except Exception as e:
            logger.warning("数据源缓存写故障（降级透传）: %s", type(e).__name__)

    async def _publish_fetched(
        self,
        result: DataSourceResult,
        query: str,
        latency_ms: float = 0.0,
        execution_id: uuid.UUID | None = None,
    ) -> None:
        """发布 DataSourceFetched 事件（event_publisher 为 None 时跳过）"""
        if self._event_publisher is None:
            return
        event = DataSourceFetched(
            source_name=result.source_name,
            query=query,
            freshness_score=result.freshness.score(datetime.now(UTC)),
            confidence=result.confidence,
            cache_hit=result.cache_hit,
            latency_ms=latency_ms,
        )
        if execution_id is not None:
            object.__setattr__(event, "execution_id", execution_id)
            object.__setattr__(event, "aggregate_id", execution_id)
        await self._event_publisher.publish(event)

    async def _publish_failed(
        self,
        req: DataSourceQuery,
        error: Exception,
        execution_id: uuid.UUID | None = None,
    ) -> None:
        """发布 DataSourceFetchFailed 事件（event_publisher 为 None 时跳过）"""
        if self._event_publisher is None:
            return
        error_code = getattr(error, "code", type(error).__name__)
        error_message = getattr(error, "message", str(error))[:500]
        event = DataSourceFetchFailed(
            source_name=req.source_name,
            query=req.query,
            error_code=str(error_code),
            error_message=str(error_message),
        )
        if execution_id is not None:
            object.__setattr__(event, "execution_id", execution_id)
            object.__setattr__(event, "aggregate_id", execution_id)
        await self._event_publisher.publish(event)


__all__ = ["DataSourceResolverService", "build_data_source_cache_key"]
