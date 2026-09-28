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
from dataclasses import replace
from datetime import UTC, datetime
from typing import Mapping

from src.application.ports.skill_loader import ToolMetadata
from src.domain.events.data_source_events import DataSourceFetched, DataSourceFetchFailed
from src.domain.exceptions import (
    BusinessRuleViolationError,
    DataSourceUnavailableError,
    ValidationError,
    redact_url_sensitive_params,
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


def _as_aware_utc(value: datetime) -> datetime:
    """naive 时间戳按 UTC 归一（aware 输入原样返回）"""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def build_data_source_cache_key(
    tenant_id: uuid.UUID | str | None,
    source_name: str,
    query: str,
    parameters: tuple[tuple[str, str], ...] = (),
) -> str:
    """构建数据源缓存键（租户前缀隔离 + 查询与参数哈希化）

    Args:
        tenant_id: 租户标识（None 归一化为 "global"）
        source_name: 数据源名称
        query: 查询表达式（SHA256 哈希化，避免原始 query 直接进入键）
        parameters: 附加查询参数（非空时按 canonical 排序与 query 一并哈希，
            防止同 (tenant, name, query) 不同参数组合互相污染缓存——R2-P1-1 修复；
            空 parameters 保持历史哈希输入，旧缓存条目零失效）

    Returns:
        格式：sisys:cache:datasource:{tenant}:{source}:{query_hash}
        （命名空间格式与 infrastructure/storage/redis/key_builder.build_key 输出一致；
        应用层禁止跨层 import infrastructure，此处内联构造保持依赖方向合规）
    """
    tenant = str(tenant_id) if tenant_id is not None else "global"
    if parameters:
        # "p" 域分隔标签：收窄空参分支（历史哈希输入为裸 query 文本）与带参分支
        # JSON 包络文本的理论碰撞窗（空参分支受旧条目零失效约束无法加标签，
        # 残留碰撞需 query 文本精确等于带参包络，现实不可达）
        hash_input = json.dumps(["p", query, sorted(parameters)], ensure_ascii=False)
    else:
        hash_input = query
    query_hash = hashlib.sha256(hash_input.encode()).hexdigest()
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
        *,
        max_concurrency: int = 4,
    ) -> None:
        """初始化编排服务

        Args:
            adapters: 数据源适配器映射（name → DataSourcePort）
            cache: L1 缓存端口（Redis KV）
            event_publisher: 事件发布端口（可选）
            max_concurrency: fetch_many 并发采集上限（默认 4；仅约束 fetch_many 的
                gather 协程，不影响单源 fetch 语义。8 个外部配额敏感源场景下
                兼顾并发收益与免费配额突发保护——R2-2-C9/H9）

        Raises:
            ValidationError: max_concurrency < 1（EXCEPTION_201）
        """
        if max_concurrency < 1:
            raise ValidationError(
                message=f"max_concurrency 必须 >= 1，实际 {max_concurrency}",
                context={"stage": "init", "field": "max_concurrency"},
            )
        self._adapters = adapters
        self._cache = cache
        self._event_publisher = event_publisher
        # 实例属性为正确位置：本服务以 SINGLETON 注册（composition_root），
        # 全进程唯一实例，实例属性即全局共享；3.10+ Semaphore 首次 acquire 时
        # 才惰性绑定运行循环，同步 __init__ 创建安全
        self._fetch_semaphore = asyncio.Semaphore(max_concurrency)

    # ===== 公开端口方法 =====

    async def fetch(
        self,
        tool_metadata: ToolMetadata,
        name: str,
        query: str,
        parameters: tuple[tuple[str, str], ...] = (),
        *,
        tenant_id: uuid.UUID | str | None = None,
        execution_id: uuid.UUID | None = None,
    ) -> DataSourceResult:
        """单源采集（白名单 → 缓存 → 适配器 → 写缓存 → 事件）"""
        allowed = self._check_whitelist(tool_metadata, name)
        cache_key = build_data_source_cache_key(tenant_id, name, query, parameters)

        # 第 1 步：缓存读（故障降级：异常时按未命中处理）
        cached = await self._read_cache(cache_key, allowed)
        if cached is not None:
            await self._publish_fetched(cached, query, execution_id=execution_id)
            return cached

        # 第 2 步：适配器采集（parameters 透传——R2-P1-1 修复，不再静默丢弃）
        # 失败事件唯一发布点（R2-2-C8/H8：fetch_many 收敛循环不再发布，结构性防双发；
        # except Exception 不捕获 CancelledError——3.8+ BaseException，取消语义安全）
        adapter = self._adapters.get(name)
        if adapter is None:
            error = DataSourceUnavailableError(
                message=f"数据源 {name} 未注册（可能因 API Key 缺失被条件注册排除）",
                context={"source_name": name},
            )
            await self._publish_failed(name, query, error, execution_id=execution_id)
            raise error
        started = time.monotonic()
        try:
            result = await adapter.fetch(
                DataSourceQuery(source_name=name, query=query, parameters=parameters, tenant_id=tenant_id)
            )
        except Exception as e:
            await self._publish_failed(name, query, e, execution_id=execution_id)
            raise
        latency_ms = (time.monotonic() - started) * 1000

        # is_stale 判定权威统一为白名单 ttl（R2-2-B8/H6：消除适配器 config ttl
        # 与缓存窗口的判定口径分裂；保留适配器 half_life_seconds 扩展面）
        if result.freshness.ttl_seconds != allowed.ttl_seconds:
            result = replace(result, freshness=replace(result.freshness, ttl_seconds=allowed.ttl_seconds))

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
    ) -> tuple[DataSourceResult | None, ...]:
        """并发采集（白名单前置校验 + gather 部分成功收敛 + 全失败抛首个异常）

        Returns:
            与 requests 等长对齐的结果元组（失败位 None 占位——R2 第二周期修复：
            紧凑化会丢失结果↔请求对应关系，导致注入键错位静默污染数据）
        """
        # 白名单前置校验：任一违规立即抛出，不采集任何源
        for req in requests:
            self._check_whitelist(tool_metadata, req.source_name)

        if not requests:
            return ()

        async def _bounded_fetch(req: DataSourceQuery) -> DataSourceResult:
            async with self._fetch_semaphore:
                return await self.fetch(
                    tool_metadata,
                    req.source_name,
                    req.query,
                    req.parameters,
                    tenant_id=req.tenant_id or tenant_id,
                    execution_id=execution_id,
                )

        outcomes = await asyncio.gather(
            *(_bounded_fetch(req) for req in requests),
            return_exceptions=True,
        )

        results: list[DataSourceResult | None] = []
        first_error: Exception | None = None
        for req, outcome in zip(requests, outcomes, strict=True):
            if isinstance(outcome, DataSourceResult):
                results.append(outcome)
                continue
            # BaseException 子类（含 CancelledError / KeyboardInterrupt / SystemExit）
            # 必须传播，不得包装为 DataSourceUnavailableError —— 否则父任务取消语义被吞
            if not isinstance(outcome, Exception):
                raise outcome
            error = outcome
            if first_error is None:
                first_error = error
            # 失败事件由 fetch 内部唯一发布（H8 结构性防双发），此处仅收敛
            results.append(None)

        if first_error is not None and not any(results):
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
            # 整条解析+重建段纳入统一 try（R2-P0-2 + R2-2-P1-1 修复：payload 提取/
            # confidence 转换/freshness 比较/值对象构造的内置 KeyError/TypeError
            # 与领域 EntityValidationError 均不得逃逸降级路径——缓存内容是不可信输入，
            # 构造失败语义与反序列化失败一致，走同一「清理 + 重采」契约，防缓存毒丸）；
            # naive 时间戳按 UTC 归一（历史写入方不规范条目的合理解释）
            entry = json.loads(raw)
            source_ts = _as_aware_utc(datetime.fromisoformat(entry["source_timestamp"]))
            fetched_at = _as_aware_utc(datetime.fromisoformat(entry["fetched_at"]))
            payload = entry["payload"]
            confidence = float(entry.get("confidence", 0.5))
            # 缓存过期以「条目年龄」（fetched_at 距今 > ttl）判定（R3-P1-1 修复：
            # 原以 source_timestamp〔源端数据时间〕判定——WorldBank/IMF 年度数据
            # source_timestamp 取数据年份 1 月 1 日，任何合法 ttl 下恒 stale →
            # 缓存结构性永不命中，AC-3 配额保护落空；对齐 HTTP 缓存 Age /
            # expireAfterWrite 语义：缓存条目过期 = 写入后经过的时间）。
            # 与 Redis set_with_ttl 双口径非冗余：白名单 ttl 收紧时（R2-2-B8 权威），
            # Redis 旧 ttl 条目仍存活，本判定是收紧生效的唯一通道；source_timestamp
            # 保留给 DataFreshness.score() 衰减评分（其唯一正确用途）
            if (datetime.now(UTC) - fetched_at).total_seconds() > ref.ttl_seconds:
                return None  # 条目过期 → 触发重采
            freshness = DataFreshness(source_timestamp=source_ts, ttl_seconds=ref.ttl_seconds)
            return DataSourceResult(
                source_name=ref.name,
                payload=payload,
                source_timestamp=source_ts,
                fetched_at=fetched_at,
                freshness=freshness,
                confidence=confidence,
                cache_hit=True,
            )
        except Exception as e:
            # 主动清理损坏条目，避免同 key 重复 deserialize 失败
            # + 日志噪音 + Redis 重复 IO（cache-aside pattern：Caffeine/Spring/redis-py 官方示例）
            logger.warning("数据源缓存条目损坏（按未命中处理 + 主动清理）: %s", type(e).__name__)
            try:
                await self._cache.delete(cache_key)
            except Exception:
                pass  # 清理失败不影响"按未命中处理"主流程
            return None

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
        """发布 DataSourceFetched 事件（event_publisher 为 None 时跳过）

        使用 with_execution_id 工厂方法绑定 execution_id，保留 event 的
        frozen immutability 语义（避免 object.__setattr__ 绕过）。
        """
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
            event = event.with_execution_id(execution_id)
        # 发布可观测性（R3-P1-7 最小闭环）：publish 端口契约「错误内部消化返回
        # PublishResult(False)」——非 HTTP 上下文（CLI/LangGraph/Prefect）无请求
        # session 时 reliable 通道 outbox 写入失败即静默丢弃；此处检查返回值记
        # warning（仅日志，不改变控制流——发布失败不得影响采集主流程）。
        # outbox 独立 session scope 的结构性修复 defer Story 4.7（事件基础设施域）
        publish_result = await self._event_publisher.publish(event)
        if not publish_result.is_success:
            logger.warning(
                "DataSourceFetched 事件发布失败（source_name=%s, event_id=%s, 首个失败通道: %s）",
                event.source_name,
                event.event_id,
                publish_result.partial_error,
            )

    async def _publish_failed(
        self,
        source_name: str,
        query: str,
        error: Exception,
        execution_id: uuid.UUID | None = None,
    ) -> None:
        """发布 DataSourceFetchFailed 事件（event_publisher 为 None 时跳过）

        error_message 先脱敏后截断（R2-2-C7/H7：防 URL query 参数中 API Key
        经事件通道泄露；截断点可能切开密文锚点，故顺序不可调换）。
        注意取舍：发布异常会掩盖原始采集异常（与既有多源收敛路径一致，
        事件发布为尽力而为的遥测，不阻断主错误传播）。
        """
        if self._event_publisher is None:
            return
        error_code = getattr(error, "code", type(error).__name__)
        raw_message = getattr(error, "message", str(error))
        error_message = redact_url_sensitive_params(str(raw_message))[:500]
        event = DataSourceFetchFailed(
            source_name=source_name,
            query=query,
            error_code=str(error_code),
            error_message=error_message,
        )
        if execution_id is not None:
            event = event.with_execution_id(execution_id)
        # 发布可观测性（R3-P1-7 最小闭环，语义同 _publish_fetched；error_code
        # 记录领域异常编码便于按码聚合检索）
        publish_result = await self._event_publisher.publish(event)
        if not publish_result.is_success:
            logger.warning(
                "DataSourceFetchFailed 事件发布失败（source_name=%s, error_code=%s, event_id=%s, 首个失败通道: %s）",
                event.source_name,
                event.error_code,
                event.event_id,
                publish_result.partial_error,
            )


__all__ = ["DataSourceResolverService", "build_data_source_cache_key"]
