"""Skills 数据采集集成测试（6 个外部数据型 Skills 全链路）

真实服务链路：真实 ToolExecutionEngine + 真实 DataSourceResolverService + 真实
Redis（测试端口，real_redis fixture）+ 真实 InMemorySkillLoader（load_sop 加载
真实 SKILL.md frontmatter 白名单）；Mock 仅限 LLM/Sandbox/数据源适配器
（_StubAdapter 可编程替身，call_count 计数）。

覆盖（Story AC-4）：
- 6 个 Skills 全链路：LLM 生成含 $DATA_SOURCE 标记代码 → 并发采集 → preamble 注入
  → EvidencePackage.data_sources 溯源元数据完备
- 多源三角化：≥3 源 Skill 全声明源并发覆盖（每源 call_count == 1）；
  disruptive-innovation 专利双库 + 市场单源跨域互证（== 3，4-1f D8 重开升级）
- 新鲜度评分 ∈ [0,1] + 缓存命中二次执行外部调用不增
- Key 缺失降级：adapters 缺 newsapi/tavily 时部分失败收敛，其余源正常注入

测试隔离：缓存键租户 = 场景级 UUID（与 ExecutionContext.tenant_id 一致），
teardown delete_pattern 仅清本租户前缀；xdist_group("data-source-cache") 同 worker 串行。
范本：test_data_source_execution.py（Story 4.1b 集成测试）。
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.ports.skill_loader import ToolMetadata
from src.application.services.data_source_resolver import DataSourceResolverService
from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.application.skills.loader import InMemorySkillLoader
from src.domain.entities.tool import Tool
from src.domain.events.data_source_events import DataSourceFetchFailed
from src.domain.exceptions import DataSourceUnavailableError
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
from tests.unit.application.skills.skill_data_collection_contracts import SKILL_DATA_SOURCES

pytestmark = [pytest.mark.integration, pytest.mark.xdist_group("data-source-cache")]

# 数据契约 SSOT：import contracts 模块唯一来源（R2-F3 统一，值与 Story 声明表逐字一致）


class _StubAdapter:
    """数据源 Stub 适配器（call_count 计数，behavior 可编程，范本 4-1b 集成测试）"""

    def __init__(self, name: str, behavior: str = "ok") -> None:
        self._ref = DataSourceRef(
            name=name,
            url=f"https://stub.local/{name}",
            ttl_seconds=3600,
            api_type=DataSourceApiType.REST_JSON,
        )
        self.behavior = behavior
        self.call_count = 0

    def get_metadata(self) -> DataSourceRef:
        return self._ref

    async def health_check(self) -> bool:
        return self.behavior == "ok"

    async def fetch(self, query: DataSourceQuery) -> DataSourceResult:
        self.call_count += 1
        if self.behavior == "unavailable":
            raise DataSourceUnavailableError(
                message=f"数据源 {self._ref.name} 不可用（模拟 5xx）",
                context={"source_name": self._ref.name},
            )
        now = datetime.now(UTC)
        return DataSourceResult(
            source_name=self._ref.name,
            payload=json.dumps({"indicator": query.query, "value": 1.0}),
            source_timestamp=now,
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=now, ttl_seconds=3600),
            confidence=0.9,
        )


@pytest.fixture
async def redis_tenant_cache(real_redis: Any) -> Any:
    """租户隔离缓存（teardown 仅清本测试租户前缀键，禁止全库 flush）

    双租户形态：第二租户供跨租户缓存隔离测试使用（R2-F1），
    teardown 对两个前缀都执行 delete_pattern（不存在的模式零成本），
    保证断言中途失败也不泄漏键（ipcc ttl 2592000s = 30 天）。
    """
    tenant = uuid.uuid4()
    tenant_b = uuid.uuid4()
    cache = RedisAdapter(redis_client=real_redis)
    yield cache, tenant, tenant_b
    await cache.delete_pattern(f"sisys:cache:datasource:{tenant}:*")
    await cache.delete_pattern(f"sisys:cache:datasource:{tenant_b}:*")


def _make_adapters(names: tuple[str, ...], unavailable: tuple[str, ...] = ()) -> dict[str, _StubAdapter]:
    """按声明源构建 Stub 适配器映射"""
    return {name: _StubAdapter(name, behavior="unavailable" if name in unavailable else "ok") for name in names}


def _code_with_markers(sources: tuple[str, ...]) -> str:
    """生成含全部指定数据源标记的沙箱代码"""
    return "\n".join(f'data_{idx} = $DATA_SOURCE("{name}", "indicator query for {name}")' for idx, name in enumerate(sources))


def _make_engine(code: str, adapters: dict[str, _StubAdapter], cache: Any, event_bus: Any) -> ToolExecutionEngine:
    """构建真实 Engine（Mock LLM/Sandbox 端口 + 真实 Resolver 后注入）

    LLM 内容分派（对齐 4-1b 集成范本 test_data_source_execution.py）：Code 阶段
    prompt 固定含「生成代码」特征串，按内容而非调用序分派——对阶段重排/重试
    稳健（R2-F1：序数分派依赖「每执行恰好第 2 次调用是 Code」的脆弱假设）。
    """

    async def _llm_dispatch(prompt: str, response_schema: Any) -> str:
        if "生成代码" in prompt:
            return code
        return "ok"

    llm = AsyncMock()
    llm.structured_generate = AsyncMock(side_effect=_llm_dispatch)

    sandbox = AsyncMock()
    sandbox.start_container = AsyncMock()
    sandbox.execute_code = AsyncMock(return_value={"status": "ok", "output": "done"})
    sandbox.stop_container = AsyncMock()

    engine = ToolExecutionEngine(llm_client=llm, sandbox=sandbox)
    resolver = DataSourceResolverService(adapters=adapters, cache=cache, event_publisher=event_bus)
    engine.set_data_source_resolver(resolver)
    return engine


async def _run_skill(
    slug: str,
    code: str,
    adapters: dict[str, _StubAdapter],
    cache: Any,
    tenant: uuid.UUID,
    event_bus: Any,
) -> Any:
    """真实 load_sop 加载白名单 + 真实 Engine 全链路执行"""
    loader = InMemorySkillLoader()
    document = await loader.load_sop(slug)
    metadata: ToolMetadata = document.frontmatter

    engine = _make_engine(code, adapters, cache, event_bus)
    tool = Tool(tool_id=uuid.uuid4(), name=slug, slug=slug)
    context = ExecutionContext(
        tenant_id=tenant,
        session_id=f"it-{uuid.uuid4().hex[:8]}",
        extensions={"tool_metadata": metadata},
    )
    return await engine.execute(
        tool_id=tool.tool_id,
        tool=tool,
        tool_call=ToolCall(tool_id=tool.tool_id, arguments={}),
        context=context,
    )


class TestSkillDataCollectionIntegration:
    """6 个 Skills 全链路采集集成测试（AC-4）"""

    @pytest.mark.parametrize("slug", list(SKILL_DATA_SOURCES.keys()))
    async def test_skill_full_chain_all_sources(self, slug: str, redis_tenant_cache: Any) -> None:
        """每 Skill 全声明源并发采集 + 溯源元数据完备（source/freshness/confidence）"""
        cache, tenant, _tenant_b = redis_tenant_cache
        declared = SKILL_DATA_SOURCES[slug]
        adapters = _make_adapters(declared)
        event_bus = InMemoryEventBus()

        result = await _run_skill(slug, _code_with_markers(declared), adapters, cache, tenant, event_bus)

        assert result.status == ToolResultStatus.SUCCESS
        # 每源恰好采集 1 次（并发去重语义）
        for name in declared:
            assert adapters[name].call_count == 1, f"{slug}/{name} 采集次数 != 1"
        # 溯源元数据完备
        metas = result.evidence_package.data_sources
        assert len(metas) == len(declared)
        for meta in metas:
            assert meta.source_name in declared
            assert 0.0 <= meta.freshness_score <= 1.0
            assert 0.0 <= meta.confidence <= 1.0

    async def test_cache_hit_second_run_no_new_fetch(self, redis_tenant_cache: Any) -> None:
        """缓存命中：二次执行外部调用次数不增 + 新鲜度评分 ∈ [0,1]"""
        cache, tenant, _tenant_b = redis_tenant_cache
        slug = "scenario-planning"
        declared = SKILL_DATA_SOURCES[slug]
        adapters = _make_adapters(declared)
        event_bus = InMemoryEventBus()
        code = _code_with_markers(declared)

        first = await _run_skill(slug, code, adapters, cache, tenant, event_bus)
        assert first.status == ToolResultStatus.SUCCESS
        first_counts = {name: adp.call_count for name, adp in adapters.items()}
        # 首轮绝对计数守卫（R2-F1）：标记代码必须真实送达——若 LLM 分派错位导致
        # 零采集，second == first 相对断言会被 0==0 伪满足（空转通道）
        assert first_counts and all(count >= 1 for count in first_counts.values()), (
            f"首轮零外部采集（标记代码未送达 Sandbox）: {first_counts}"
        )

        second = await _run_skill(slug, code, adapters, cache, tenant, event_bus)
        assert second.status == ToolResultStatus.SUCCESS
        for name in declared:
            assert adapters[name].call_count == first_counts[name], f"{name} 缓存未命中产生新采集"
        for meta in second.evidence_package.data_sources:
            assert 0.0 <= meta.freshness_score <= 1.0

    async def test_tenant_isolation_cross_tenant_no_cache_share(self, redis_tenant_cache: Any) -> None:
        """跨租户缓存隔离（R2-F1）：租户 B 执行同标记代码不得命中租户 A 的缓存

        守护 context.tenant_id 经 Engine 全链路（frontmatter 白名单 → Engine →
        Resolver → Redis 键）的传递接线：若缓存键丢失租户前缀（坍缩为 global:*）
        或 Engine 丢失 tenant_id，租户 B 会错误命中 A 的采集结果（B 零采集）。
        """
        cache, tenant, tenant_b = redis_tenant_cache
        slug = "scenario-planning"
        declared = SKILL_DATA_SOURCES[slug]
        adapters = _make_adapters(declared)
        event_bus = InMemoryEventBus()
        code = _code_with_markers(declared)

        first = await _run_skill(slug, code, adapters, cache, tenant, event_bus)
        assert first.status == ToolResultStatus.SUCCESS
        first_counts = {name: adp.call_count for name, adp in adapters.items()}
        assert all(count >= 1 for count in first_counts.values())

        second = await _run_skill(slug, code, adapters, cache, tenant_b, event_bus)
        assert second.status == ToolResultStatus.SUCCESS
        # 租户 B 全新缓存前缀：每个声明源都应产生 1 次新采集（first + 1，绝对断言）
        for name in declared:
            assert adapters[name].call_count == first_counts[name] + 1, (
                f"{name} 租户 B 错误命中租户 A 缓存（跨租户数据泄漏风险）"
            )

    async def test_key_missing_partial_failure_convergence(self, redis_tenant_cache: Any) -> None:
        """Key 缺失降级：adapters 缺 newsapi/tavily（模拟未注册）→ 部分失败收敛，其余源正常注入"""
        cache, tenant, _tenant_b = redis_tenant_cache
        slug = "appeals-analysis"
        declared = SKILL_DATA_SOURCES[slug]
        # 模拟 Key 缺失：adapters 映射不含 tavily/newsapi（Resolver 抛 411 未注册语义）
        adapters = {"china-nbs": _StubAdapter("china-nbs")}
        event_bus = InMemoryEventBus()

        result = await _run_skill(slug, _code_with_markers(declared), adapters, cache, tenant, event_bus)

        assert result.status == ToolResultStatus.SUCCESS
        assert adapters["china-nbs"].call_count == 1
        # 仅可用源注入溯源元数据
        injected_names = {meta.source_name for meta in result.evidence_package.data_sources}
        assert injected_names == {"china-nbs"}
        # 部分失败发布 DataSourceFetchFailed 事件（Key 缺失未注册 → 411 语义，R1-P1-1）
        assert any(
            isinstance(evt, DataSourceFetchFailed) and evt.error_code == "EXCEPTION_411" for evt in event_bus.published_events
        )

    async def test_triangulation_competitor_six_sources(self, redis_tenant_cache: Any) -> None:
        """三角化：competitor-analysis（6 源，4-1f 双库扩充）注入源数 == 6 全声明覆盖（>=3 升格强断言）"""
        cache, tenant, _tenant_b = redis_tenant_cache
        slug = "competitor-analysis"
        declared = SKILL_DATA_SOURCES[slug]
        adapters = _make_adapters(declared)

        result = await _run_skill(slug, _code_with_markers(declared), adapters, cache, tenant, InMemoryEventBus())

        assert result.status == ToolResultStatus.SUCCESS
        assert len(result.evidence_package.data_sources) == 6

    async def test_disruptive_innovation_triple_source(self, redis_tenant_cache: Any) -> None:
        """专利双库 + 市场单源：disruptive-innovation（3 源，4-1f D8 重开升级）注入源数 == 3"""
        cache, tenant, _tenant_b = redis_tenant_cache
        slug = "disruptive-innovation"
        declared = SKILL_DATA_SOURCES[slug]
        adapters = _make_adapters(declared)

        result = await _run_skill(slug, _code_with_markers(declared), adapters, cache, tenant, InMemoryEventBus())

        assert result.status == ToolResultStatus.SUCCESS
        assert len(result.evidence_package.data_sources) == 3

    async def test_source_unavailable_partial_convergence(self, redis_tenant_cache: Any) -> None:
        """数据源不可用：porters（3 源）eurostat 故障 → 其余 2 源正常注入 + 失败事件"""
        cache, tenant, _tenant_b = redis_tenant_cache
        slug = "porters-five-forces"
        declared = SKILL_DATA_SOURCES[slug]
        adapters = _make_adapters(declared, unavailable=("eurostat",))
        event_bus = InMemoryEventBus()

        result = await _run_skill(slug, _code_with_markers(declared), adapters, cache, tenant, event_bus)

        assert result.status == ToolResultStatus.SUCCESS
        injected_names = {meta.source_name for meta in result.evidence_package.data_sources}
        assert injected_names == {"newsapi", "world-bank"}
        # 源不可用（behavior=unavailable → DataSourceUnavailableError）同为 411 语义（R1-P1-1 对称收敛）
        assert any(
            isinstance(evt, DataSourceFetchFailed) and evt.error_code == "EXCEPTION_411" for evt in event_bus.published_events
        )
