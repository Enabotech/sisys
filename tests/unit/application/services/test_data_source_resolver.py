"""Story 4.1b — DataSourceResolverService 单元测试

验证应用层数据源解析编排服务：
- 白名单校验（name ∉ tool_metadata.data_sources → BusinessRuleViolationError 207）
- 未注册适配器（metadata 声明但端口未注册，如 Key 缺失条件注册降级）→ DataSourceUnavailableError(411)
- Redis 缓存：命中（cache_hit=True 不消耗配额）/ stale 重采 / TTL 写过期 / 租户隔离
- 缓存故障降级：Redis 异常时透传采集（不阻断主流程）
- 并发采集：asyncio.gather 部分成功收敛 + DataSourceFetchFailed 事件
- 全部失败：抛出首个异常（Engine 依此传播 412/413 等）
- 成功发布 DataSourceFetched 事件

测试模式：Mock 端口适配器（AsyncMock/测试替身）+ fakeredis/Mock L1CachePort + InMemoryEventBus。
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.application.ports.data_source_resolver import DataSourceResolverPort
from src.application.ports.skill_loader import ToolMetadata
from src.application.services.data_source_resolver import (
    DataSourceResolverService,
    build_data_source_cache_key,
)
from src.domain.events.data_source_events import DataSourceFetched, DataSourceFetchFailed
from src.domain.exceptions import (
    BusinessRuleViolationError,
    DataSourceRateLimitError,
    DataSourceUnavailableError,
)
from src.domain.ports.data_source import DataSourceQuery
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceRef,
    DataSourceResult,
)
from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus

# ===================================================================
# 测试替身
# ===================================================================


class _StubAdapter:
    """可编程数据源适配器桩（fetch 计数 + 行为切换）。"""

    def __init__(self, name: str, ttl_seconds: int = 3600, error: Exception | None = None) -> None:
        self._ref = DataSourceRef(
            name=name, url=f"https://fake.local/{name}", ttl_seconds=ttl_seconds, api_type=DataSourceApiType.REST_JSON
        )
        self.call_count = 0
        self._error = error
        self.last_query: DataSourceQuery | None = None

    def get_metadata(self) -> DataSourceRef:
        return self._ref

    async def health_check(self) -> bool:
        return self._error is None

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        self.call_count += 1
        self.last_query = query
        if self._error is not None:
            raise self._error
        now = datetime.now(UTC)
        return DataSourceResult(
            source_name=self._ref.name,
            payload=json.dumps({"q": query.query}),
            source_timestamp=now,
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=now, ttl_seconds=self._ref.ttl_seconds),
            confidence=0.9,
        )


class _InMemoryCache:
    """L1CachePort 内存实现（单元测试用；集成/验收测试用真实 Redis）。"""

    def __init__(self, fail: bool = False) -> None:
        self._store: dict[str, str] = {}
        self._fail = fail

    def _maybe_fail(self) -> None:
        if self._fail:
            raise ConnectionError("redis down")

    async def get(self, key: str) -> str | None:
        self._maybe_fail()
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        self._maybe_fail()
        self._store[key] = value
        return True

    async def set_with_ttl(self, key: str, value: str, ttl: int) -> bool:
        self._maybe_fail()
        self._store[key] = value
        return True

    async def delete(self, key: str) -> bool:
        self._maybe_fail()
        return self._store.pop(key, None) is not None

    async def delete_pattern(self, pattern: str) -> int:
        self._maybe_fail()
        prefix = pattern.rstrip("*")
        keys = [k for k in self._store if k.startswith(prefix)]
        for k in keys:
            del self._store[k]
        return len(keys)

    async def exists(self, key: str) -> bool:
        self._maybe_fail()
        return key in self._store

    async def set_nx(self, key: str, value: str, ttl: int) -> bool:
        self._maybe_fail()
        if key in self._store:
            return False
        self._store[key] = value
        return True

    async def eval(self, script: str, keys: list[str], args: list[str]) -> Any:
        return None


def _make_metadata(*names: str, ttl_seconds: int = 3600) -> ToolMetadata:
    return ToolMetadata(
        tool_name="测试工具",
        slug="test-tool",
        category="environment_analysis",
        input_schema={},
        output_schema={},
        data_sources=tuple(
            DataSourceRef(name=n, url=f"https://fake.local/{n}", ttl_seconds=ttl_seconds, api_type=DataSourceApiType.REST_JSON)
            for n in names
        ),
    )


def _make_service(
    adapters: dict[str, Any] | None = None,
    cache: Any = None,
    event_bus: InMemoryEventBus | None = None,
) -> tuple[DataSourceResolverService, InMemoryEventBus]:
    bus = event_bus or InMemoryEventBus()
    service = DataSourceResolverService(
        adapters=adapters if adapters is not None else {"world-bank": _StubAdapter("world-bank")},
        cache=cache or _InMemoryCache(),
        event_publisher=bus,
    )
    return service, bus


# ===================================================================
# 白名单校验
# ===================================================================


class TestWhitelist:
    @pytest.mark.asyncio
    async def test_undeclared_source_raises_207(self) -> None:
        service, _ = _make_service()
        metadata = _make_metadata("world-bank")
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await service.fetch(metadata, "newsapi", "tech")
        assert exc_info.value.code == "EXCEPTION_207"

    @pytest.mark.asyncio
    async def test_declared_but_unregistered_source_raises_411(self) -> None:
        """Key 缺失条件注册降级：metadata 声明但适配器未注册 → 411（优雅降级语义）。"""
        service, _ = _make_service(adapters={})  # 无适配器注册
        metadata = _make_metadata("tavily")
        with pytest.raises(DataSourceUnavailableError) as exc_info:
            await service.fetch(metadata, "tavily", "q")
        assert exc_info.value.code == "EXCEPTION_411"

    @pytest.mark.asyncio
    async def test_fetch_many_whitelist_check_upfront(self) -> None:
        """fetch_many 在并发采集前统一做白名单校验（违规立即抛出，不采集任何源）。"""
        stub = _StubAdapter("world-bank")
        service, _ = _make_service(adapters={"world-bank": stub})
        metadata = _make_metadata("world-bank")
        requests = (
            DataSourceQuery(source_name="world-bank", query="a"),
            DataSourceQuery(source_name="newsapi", query="b"),
        )
        with pytest.raises(BusinessRuleViolationError):
            await service.fetch_many(metadata, requests)
        assert stub.call_count == 0


# ===================================================================
# 缓存行为
# ===================================================================


class TestCache:
    @pytest.mark.asyncio
    async def test_cache_hit_second_call(self) -> None:
        stub = _StubAdapter("world-bank")
        service, _ = _make_service(adapters={"world-bank": stub})
        metadata = _make_metadata("world-bank")
        first = await service.fetch(metadata, "world-bank", "GDP", tenant_id="t-1")
        second = await service.fetch(metadata, "world-bank", "GDP", tenant_id="t-1")
        assert first.cache_hit is False
        assert second.cache_hit is True
        assert stub.call_count == 1

    @pytest.mark.asyncio
    async def test_stale_entry_triggers_refetch(self) -> None:
        stub = _StubAdapter("world-bank")
        cache = _InMemoryCache()
        service, _ = _make_service(adapters={"world-bank": stub}, cache=cache)
        metadata = _make_metadata("world-bank", ttl_seconds=60)
        # 预置过期缓存条目（fetched_at 120s 前 > ttl 60s）
        stale = datetime.now(UTC) - timedelta(seconds=120)
        key = build_data_source_cache_key("t-1", "world-bank", "GDP")
        await cache.set_with_ttl(
            key,
            json.dumps(
                {
                    "payload": '{"old": true}',
                    "source_timestamp": stale.isoformat(),
                    "fetched_at": stale.isoformat(),
                    "confidence": 0.5,
                }
            ),
            3600,
        )
        result = await service.fetch(metadata, "world-bank", "GDP", tenant_id="t-1")
        assert result.cache_hit is False
        assert stub.call_count == 1

    @pytest.mark.asyncio
    async def test_tenant_isolation(self) -> None:
        stub = _StubAdapter("world-bank")
        service, _ = _make_service(adapters={"world-bank": stub})
        metadata = _make_metadata("world-bank")
        await service.fetch(metadata, "world-bank", "GDP", tenant_id="tenant-a")
        # 租户 B 同查询不命中租户 A 缓存
        result_b = await service.fetch(metadata, "world-bank", "GDP", tenant_id="tenant-b")
        assert result_b.cache_hit is False
        assert stub.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_failure_degrades_to_passthrough(self) -> None:
        """Redis 故障降级：缓存读写异常不阻断采集（透传 + 每次重新采集）。"""
        stub = _StubAdapter("world-bank")
        cache = _InMemoryCache(fail=True)
        service, _ = _make_service(adapters={"world-bank": stub}, cache=cache)
        metadata = _make_metadata("world-bank")
        r1 = await service.fetch(metadata, "world-bank", "GDP", tenant_id="t-1")
        r2 = await service.fetch(metadata, "world-bank", "GDP", tenant_id="t-1")
        assert r1.cache_hit is False and r2.cache_hit is False
        assert stub.call_count == 2


# ===================================================================
# 并发采集与事件
# ===================================================================


class TestFetchManyAndEvents:
    @pytest.mark.asyncio
    async def test_partial_success_converges(self) -> None:
        ok = _StubAdapter("world-bank")
        bad = _StubAdapter("eurostat", error=DataSourceUnavailableError(message="down", context={"source_name": "eurostat"}))
        bus = InMemoryEventBus()
        service, _ = _make_service(adapters={"world-bank": ok, "eurostat": bad}, event_bus=bus)
        metadata = _make_metadata("world-bank", "eurostat")
        results = await service.fetch_many(
            metadata,
            (
                DataSourceQuery(source_name="world-bank", query="a"),
                DataSourceQuery(source_name="eurostat", query="b"),
            ),
        )
        assert len(results) == 2  # 等长对齐（R2 第二周期：失败位 None 占位，杜绝紧凑化错位）
        assert results[0] is not None and results[0].source_name == "world-bank"
        assert results[1] is None  # eurostat 采集失败位
        failed_events = [e for e in bus.published_events if isinstance(e, DataSourceFetchFailed)]
        assert len(failed_events) == 1
        assert failed_events[0].source_name == "eurostat"
        assert failed_events[0].error_code == "EXCEPTION_411"

    @pytest.mark.asyncio
    async def test_all_failed_raises_first_error(self) -> None:
        """全部失败时抛出首个异常（Engine 依此传播 412 等到调用方）。"""
        bad = _StubAdapter("newsapi", error=DataSourceRateLimitError(message="429", context={"source_name": "newsapi"}))
        service, _ = _make_service(adapters={"newsapi": bad})
        metadata = _make_metadata("newsapi")
        with pytest.raises(DataSourceRateLimitError):
            await service.fetch_many(metadata, (DataSourceQuery(source_name="newsapi", query="x"),))

    @pytest.mark.asyncio
    async def test_success_publishes_fetched_event(self) -> None:
        stub = _StubAdapter("world-bank")
        bus = InMemoryEventBus()
        service, _ = _make_service(adapters={"world-bank": stub}, event_bus=bus)
        metadata = _make_metadata("world-bank")
        await service.fetch(metadata, "world-bank", "GDP", tenant_id=uuid.uuid4())
        fetched = [e for e in bus.published_events if isinstance(e, DataSourceFetched)]
        assert len(fetched) == 1
        assert fetched[0].source_name == "world-bank"
        assert fetched[0].cache_hit is False
        assert fetched[0].aggregate_type == "ToolExecution"

    @pytest.mark.asyncio
    async def test_cache_hit_does_not_consume_quota_but_reports_event(self) -> None:
        stub = _StubAdapter("world-bank")
        bus = InMemoryEventBus()
        service, _ = _make_service(adapters={"world-bank": stub}, event_bus=bus)
        metadata = _make_metadata("world-bank")
        await service.fetch(metadata, "world-bank", "GDP", tenant_id="t-9")
        await service.fetch(metadata, "world-bank", "GDP", tenant_id="t-9")
        assert stub.call_count == 1
        fetched = [e for e in bus.published_events if isinstance(e, DataSourceFetched)]
        assert fetched[-1].cache_hit is True


# ===================================================================
# 损坏缓存条目降级（R2-P0-2：内置 KeyError/TypeError 不得逃逸）
# ===================================================================


class TestCorruptedCacheEntry:
    @pytest.mark.asyncio
    async def test_missing_payload_key_degrades_to_refetch_and_cleanup(self) -> None:
        """缓存条目缺 payload 键 → 按未命中重采 + 主动清理（不抛内置 KeyError）。"""
        stub = _StubAdapter("world-bank")
        cache = _InMemoryCache()
        service, _ = _make_service(adapters={"world-bank": stub}, cache=cache)
        metadata = _make_metadata("world-bank")
        key = build_data_source_cache_key("t-1", "world-bank", "GDP")
        now = datetime.now(UTC)
        await cache.set_with_ttl(
            key,
            json.dumps({"source_timestamp": now.isoformat(), "fetched_at": now.isoformat(), "confidence": 0.5}),
            3600,
        )
        result = await service.fetch(metadata, "world-bank", "GDP", tenant_id="t-1")
        assert result.cache_hit is False
        assert stub.call_count == 1
        # 损坏条目已被主动清理（后续写入的是新采集条目）
        raw = await cache.get(key)
        assert raw is not None
        entry = json.loads(raw)
        assert "payload" in entry

    @pytest.mark.asyncio
    async def test_naive_timestamp_normalized_and_cache_hit(self) -> None:
        """新鲜 naive 时间戳条目 → UTC 归一后正常命中（cache_hit=True），条目不被误清理。

        判别性：删掉 _as_aware_utc 归一后，aware-naive 比较抛 TypeError 走降级重采，
        本用例变红（钉住归一化语义而非"naive 即损坏"）。
        """
        stub = _StubAdapter("world-bank")
        cache = _InMemoryCache()
        service, _ = _make_service(adapters={"world-bank": stub}, cache=cache)
        metadata = _make_metadata("world-bank")
        key = build_data_source_cache_key("t-1", "world-bank", "GDP")
        fresh_naive = datetime.now(UTC).replace(tzinfo=None).isoformat()  # 新鲜但 naive
        await cache.set_with_ttl(
            key,
            json.dumps(
                {
                    "payload": '{"v": 1}',
                    "source_timestamp": fresh_naive,
                    "fetched_at": fresh_naive,
                    "confidence": 0.5,
                }
            ),
            3600,
        )
        result = await service.fetch(metadata, "world-bank", "GDP", tenant_id="t-1")
        assert result.cache_hit is True
        assert stub.call_count == 0
        # 归一化命中而非损坏清理：条目应仍在（后续命中路径一致）
        assert await cache.get(key) is not None

    @pytest.mark.asyncio
    async def test_invariant_violating_entry_degrades_to_refetch_and_cleanup(self) -> None:
        """合法 JSON 但违反值对象不变量（confidence 越界）→ EntityValidationError 不逃逸，
        走「清理 + 重采」降级（缓存毒丸防护：同 key 不得重复抛错至 TTL 过期）。"""
        stub = _StubAdapter("world-bank")
        cache = _InMemoryCache()
        service, _ = _make_service(adapters={"world-bank": stub}, cache=cache)
        metadata = _make_metadata("world-bank")
        key = build_data_source_cache_key("t-1", "world-bank", "GDP")
        now = datetime.now(UTC)
        await cache.set_with_ttl(
            key,
            json.dumps(
                {
                    "payload": '{"v": 1}',
                    "source_timestamp": now.isoformat(),
                    "fetched_at": now.isoformat(),
                    "confidence": 5.0,  # 越界（值对象不变量 [0,1]）
                }
            ),
            3600,
        )
        result = await service.fetch(metadata, "world-bank", "GDP", tenant_id="t-1")
        assert result.cache_hit is False
        assert stub.call_count == 1
        # 第二次调用同样重采成功（毒丸已清理，不再抛错）
        result2 = await service.fetch(metadata, "world-bank", "GDP", tenant_id="t-1")
        assert result2.cache_hit is True  # 首轮重采已写入新条目
        assert stub.call_count == 1

    @pytest.mark.asyncio
    async def test_non_numeric_confidence_degrades_to_refetch(self) -> None:
        """confidence 非数值 → 按未命中重采（float 转换纳入降级契约）。"""
        stub = _StubAdapter("world-bank")
        cache = _InMemoryCache()
        service, _ = _make_service(adapters={"world-bank": stub}, cache=cache)
        metadata = _make_metadata("world-bank")
        key = build_data_source_cache_key("t-1", "world-bank", "GDP")
        now = datetime.now(UTC)
        await cache.set_with_ttl(
            key,
            json.dumps(
                {
                    "payload": '{"v": 1}',
                    "source_timestamp": now.isoformat(),
                    "fetched_at": now.isoformat(),
                    "confidence": "high",
                }
            ),
            3600,
        )
        result = await service.fetch(metadata, "world-bank", "GDP", tenant_id="t-1")
        assert result.cache_hit is False
        assert stub.call_count == 1


# ===================================================================
# parameters 透传与缓存键完整性（R2-P1-1）
# ===================================================================


class TestParameters:
    @pytest.mark.asyncio
    async def test_fetch_passes_parameters_to_adapter(self) -> None:
        """fetch 透传 parameters 到适配器（不再静默丢弃）。"""
        stub = _StubAdapter("world-bank")
        service, _ = _make_service(adapters={"world-bank": stub})
        metadata = _make_metadata("world-bank")
        params = (("country", "CN"), ("year", "2025"))
        await service.fetch(metadata, "world-bank", "GDP", params, tenant_id="t-1")
        assert stub.last_query is not None
        assert stub.last_query.parameters == params

    @pytest.mark.asyncio
    async def test_fetch_many_passes_parameters_to_adapter(self) -> None:
        """fetch_many 透传每个请求的 parameters（不再重建时丢弃）。"""
        stub = _StubAdapter("world-bank")
        service, _ = _make_service(adapters={"world-bank": stub})
        metadata = _make_metadata("world-bank")
        params = (("country", "DE"),)
        await service.fetch_many(metadata, (DataSourceQuery(source_name="world-bank", query="GDP", parameters=params),))
        assert stub.last_query is not None
        assert stub.last_query.parameters == params

    @pytest.mark.asyncio
    async def test_cache_key_distinguishes_parameters(self) -> None:
        """同 (tenant, name, query) 不同 parameters → 不同缓存键（防互相污染）。"""
        stub = _StubAdapter("world-bank")
        service, _ = _make_service(adapters={"world-bank": stub})
        metadata = _make_metadata("world-bank")
        await service.fetch(metadata, "world-bank", "GDP", (("country", "CN"),), tenant_id="t-1")
        result = await service.fetch(metadata, "world-bank", "GDP", (("country", "US"),), tenant_id="t-1")
        assert result.cache_hit is False
        assert stub.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_hit_with_same_parameters(self) -> None:
        """同 parameters（含顺序不同）→ 缓存命中（canonical 排序归一）。"""
        stub = _StubAdapter("world-bank")
        service, _ = _make_service(adapters={"world-bank": stub})
        metadata = _make_metadata("world-bank")
        await service.fetch(metadata, "world-bank", "GDP", (("a", "1"), ("b", "2")), tenant_id="t-1")
        result = await service.fetch(metadata, "world-bank", "GDP", (("b", "2"), ("a", "1")), tenant_id="t-1")
        assert result.cache_hit is True
        assert stub.call_count == 1

    def test_empty_parameters_keeps_legacy_key(self) -> None:
        """空 parameters 缓存键与历史格式一致（旧条目零失效）。"""
        assert build_data_source_cache_key("t-1", "world-bank", "GDP") == build_data_source_cache_key(
            "t-1", "world-bank", "GDP", ()
        )


# ===================================================================
# 端口契约
# ===================================================================


class TestPortCompliance:
    def test_service_implements_resolver_port(self) -> None:
        service, _ = _make_service()
        assert isinstance(service, DataSourceResolverPort)

    def test_build_cache_key_format(self) -> None:
        key = build_data_source_cache_key("t-1", "world-bank", "GDP China")
        assert key.startswith("sisys:cache:datasource:t-1:world-bank:")
        # 查询哈希化（原始 query 不直接进入键）
        assert "GDP China" not in key
