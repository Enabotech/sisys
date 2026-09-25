"""Story 4.1b — Engine $DATA_SOURCE 全链路集成测试

真实服务协作验证（Mock 仅限 LLM/Sandbox 端口适配器）：
- 真实 ToolExecutionEngine + DataSourceResolverService + 真实 Redis（L1CachePort）
  + InMemoryEventBus + 真实标记解析器
- $DATA_SOURCE 全链路：标记 → 白名单 → 采集 → preamble 注入 → 溯源元数据
- 缓存命中二次执行不重复采集（真实 Redis TTL 写入）
- 租户隔离（不同租户前缀不共享缓存键）

真实 Redis 不可用时 pytest.skip() 动态跳过（禁止写死 @pytest.mark.skip）。
测试隔离：缓存键含测试级 UUID 租户前缀，teardown 仅清理本测试键。
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.ports.skill_loader import ToolMetadata
from src.application.services.data_source_resolver import DataSourceResolverService
from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.domain.entities.tool import Tool
from src.domain.ports.data_source import DataSourceQuery
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceRef,
    DataSourceResult,
)
from src.domain.value_objects.tool_execution import ExecutionContext, ToolCall, ToolResultStatus
from src.infrastructure.messaging.inmemory_event_bus import InMemoryEventBus
from src.infrastructure.storage.redis.redis_adapter import RedisAdapter

pytestmark = [pytest.mark.integration, pytest.mark.xdist_group("data-source-cache")]


class _StubAdapter:
    """可编程数据源适配器桩（Mock 仅限外部数据源端口）。"""

    def __init__(self, name: str) -> None:
        self._ref = DataSourceRef(
            name=name, url=f"https://fake.local/{name}", ttl_seconds=3600, api_type=DataSourceApiType.REST_JSON
        )
        self.call_count = 0

    def get_metadata(self) -> DataSourceRef:
        return self._ref

    async def health_check(self) -> bool:
        return True

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        self.call_count += 1
        now = datetime.now(UTC)
        return DataSourceResult(
            source_name=self._ref.name,
            payload=json.dumps({"q": query.query, "v": 42.0}),
            source_timestamp=now,
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=now, ttl_seconds=3600),
            confidence=0.9,
        )


@pytest.fixture
async def redis_tenant_cache(real_redis: Any) -> AsyncGenerator[tuple[RedisAdapter, str], None]:
    """真实 Redis 缓存 + 测试级租户前缀（teardown 仅清理本测试键）"""
    tenant = f"it-{uuid.uuid4().hex[:8]}"
    cache = RedisAdapter(redis_client=real_redis)
    yield cache, tenant
    await cache.delete_pattern(f"sisys:cache:datasource:{tenant}:*")


def _make_metadata(*names: str) -> ToolMetadata:
    return ToolMetadata(
        tool_name="集成测试工具",
        slug="test-tool-it",
        category="environment_analysis",
        input_schema={},
        output_schema={},
        data_sources=tuple(
            DataSourceRef(name=n, url=f"https://fake.local/{n}", api_type=DataSourceApiType.REST_JSON) for n in names
        ),
    )


def _make_engine(code: str, sandbox_codes: list[str], resolver: DataSourceResolverService) -> ToolExecutionEngine:
    """真实 Engine（Mock LLM/Sandbox）+ 后注入真实 Resolver"""

    async def _llm_dispatch(prompt: str, response_schema: Any) -> str:
        if "生成代码" in prompt:
            return code
        return "ok"

    llm = AsyncMock()
    llm.structured_generate = AsyncMock(side_effect=_llm_dispatch)

    async def _sandbox_execute(session_id: str, code_arg: str, **_kwargs: Any) -> dict[str, Any]:
        sandbox_codes.append(code_arg)
        return {"status": "ok", "output": "done"}

    sandbox = AsyncMock()
    sandbox.start_container = AsyncMock()
    sandbox.execute_code = AsyncMock(side_effect=_sandbox_execute)
    sandbox.stop_container = AsyncMock()

    engine = ToolExecutionEngine(llm_client=llm, sandbox=sandbox)
    engine.set_data_source_resolver(resolver)
    return engine


class TestDataSourceExecutionIntegration:
    @pytest.mark.asyncio
    async def test_end_to_end_marker_collection_with_real_redis(self, redis_tenant_cache: tuple[RedisAdapter, str]) -> None:
        """$DATA_SOURCE 全链路：真实 Engine + Resolver + Redis 缓存 + 事件总线。"""
        cache, tenant = redis_tenant_cache
        stub = _StubAdapter("world-bank")
        bus = InMemoryEventBus()
        resolver = DataSourceResolverService(adapters={"world-bank": stub}, cache=cache, event_publisher=bus)

        code = '$DATA_SOURCE("world-bank", "GDP China")\nprint(DATA_SOURCES)'
        sandbox_codes: list[str] = []
        engine = _make_engine(code, sandbox_codes, resolver)

        tool = Tool(tool_id=uuid.uuid4(), name="集成测试工具", slug="test-tool-it")
        result = await engine.execute(
            tool_id=tool.tool_id,
            tool=tool,
            tool_call=ToolCall(tool_id=tool.tool_id, arguments={}),
            context=ExecutionContext(
                tenant_id=uuid.uuid4(),
                session_id=f"sess-{uuid.uuid4().hex[:8]}",
                extensions={"tool_metadata": _make_metadata("world-bank")},
            ),
        )

        assert result.status == ToolResultStatus.SUCCESS
        preamble = sandbox_codes[0].split("\n", 1)[0]
        assert preamble.startswith("DATA_SOURCES = ")
        assert "world-bank" in preamble
        assert result.evidence_package is not None
        assert len(result.evidence_package.data_sources) == 1
        assert result.evidence_package.data_sources[0].source_name == "world-bank"
        assert stub.call_count == 1

    @pytest.mark.asyncio
    async def test_second_run_cache_hit_no_refetch(self, redis_tenant_cache: tuple[RedisAdapter, str]) -> None:
        """缓存命中：同一租户同一查询第二次走缓存（真实 Redis TTL 写入验证）。"""
        cache, tenant = redis_tenant_cache
        stub = _StubAdapter("world-bank")
        resolver = DataSourceResolverService(adapters={"world-bank": stub}, cache=cache, event_publisher=None)
        metadata = _make_metadata("world-bank")

        first = await resolver.fetch(metadata, "world-bank", "GDP", tenant_id=tenant)
        second = await resolver.fetch(metadata, "world-bank", "GDP", tenant_id=tenant)

        assert first.cache_hit is False
        assert second.cache_hit is True
        assert stub.call_count == 1

    @pytest.mark.asyncio
    async def test_tenant_isolation_real_redis(self, redis_tenant_cache: tuple[RedisAdapter, str]) -> None:
        """租户隔离：租户 B 同查询不命中租户 A 缓存（真实 Redis 键前缀隔离）。"""
        cache, tenant = redis_tenant_cache
        stub = _StubAdapter("world-bank")
        resolver = DataSourceResolverService(adapters={"world-bank": stub}, cache=cache, event_publisher=None)
        metadata = _make_metadata("world-bank")

        await resolver.fetch(metadata, "world-bank", "GDP", tenant_id=tenant)
        other = await resolver.fetch(metadata, "world-bank", "GDP", tenant_id=f"{tenant}-other")

        assert other.cache_hit is False
        assert stub.call_count == 2
