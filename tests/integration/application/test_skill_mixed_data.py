"""混合数据型 Skills 集成测试（10 个 Skills 全链路 + 内外数据融合）

真实服务链路：真实 ToolExecutionEngine + 真实 DataSourceResolverService + 真实
Redis（测试端口，real_redis fixture）+ 真实 InMemorySkillLoader（load_sop 加载
真实 SKILL.md frontmatter 白名单）；Mock 仅限 LLM/Sandbox/数据源适配器
（_StubAdapter 可编程替身，call_count 计数）。

覆盖（Story AC-4）：
- 10 个 Skills 全链路：LLM 生成含 $DATA_SOURCE 标记代码 → 双源并发采集 →
  preamble 注入 → EvidencePackage.data_sources 溯源元数据完备（注入源数 == 2）
- 内外数据融合双通道：arguments（内部数据）进入 Think prompt（repr 子串断言）
  与 DATA_SOURCES 注入（外部基准）并存
- 新鲜度评分 ∈ [0,1] + 缓存命中二次执行外部调用不增 + 跨租户缓存隔离
- Key 缺失降级：单敏感源 Skill 物理缺 1 敏感源 → 部分失败收敛（SUCCESS +
  DataSourceFetchFailed 且 error_code == "EXCEPTION_411"）；
  双敏感 Skill 全缺 → 411 直传播（fetch_many 全失败契约对照）
- 源不可用（5xx）部分失败收敛：其余源正常注入

测试隔离：缓存键租户 = 场景级 UUID（与 ExecutionContext.tenant_id 一致），
teardown delete_pattern 仅清本租户前缀；xdist_group("data-source-cache") 同 worker 串行。
范本：test_skill_data_collection.py（Story 4-1c 集成测试）。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.services.data_source_resolver import DataSourceResolverService
from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.application.skills.loader import InMemorySkillLoader
from src.domain.entities.tool import Tool
from src.domain.events.data_source_events import DataSourceFetchFailed
from src.domain.exceptions import DataSourceUnavailableError
from src.domain.exceptions.base_exceptions import DomainError
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
from tests.unit.application.skills.skill_data_collection_contracts import KEY_SENSITIVE_SOURCES
from tests.unit.application.skills.skill_mixed_data_contracts import (
    MIXED_SKILL_DATA_SOURCES,
    build_min_arguments,
)

pytestmark = [pytest.mark.integration, pytest.mark.xdist_group("data-source-cache")]

# 数据契约 SSOT：import contracts 模块唯一来源（R2-F3 统一）

# 单敏感 Skill 参数化集（R1-F8：从两 SSOT 表派生，消除字面复制）：
# 声明含恰好 1 个 Key 敏感源（KEY_SENSITIVE_SOURCES，import 4-1c 契约库同源常量）
# 的 4-1d Skill——物理缺该敏感源 → 部分失败收敛可满足（留 1 个免 Key 源）
SINGLE_SENSITIVE_SLUGS: tuple[str, ...] = tuple(
    slug for slug, sources in MIXED_SKILL_DATA_SOURCES.items() if len(set(sources) & set(KEY_SENSITIVE_SOURCES)) == 1
)


class _StubAdapter:
    """数据源 Stub 适配器（call_count 计数，behavior 可编程，范本 4-1c 集成测试）"""

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
        payload = '{"indicator": "%s", "value": 1.0}' % query.query
        return DataSourceResult(
            source_name=self._ref.name,
            payload=payload,
            source_timestamp=now,
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=now, ttl_seconds=3600),
            confidence=0.9,
        )


@pytest.fixture
async def redis_tenant_cache(real_redis: Any) -> Any:
    """双租户缓存 fixture（tenant_b 专供跨租户隔离测试，4-1c R2-F1 模式）。"""
    tenant = uuid.uuid4()
    tenant_b = uuid.uuid4()
    cache = RedisAdapter(redis_client=real_redis)
    yield cache, tenant, tenant_b
    await cache.delete_pattern(f"sisys:cache:datasource:{tenant}:*")
    await cache.delete_pattern(f"sisys:cache:datasource:{tenant_b}:*")


def _make_adapters(names: tuple[str, ...], unavailable: tuple[str, ...] = ()) -> dict[str, _StubAdapter]:
    """按声明源构建 Stub 适配器映射（unavailable 源行为可编程）。"""
    return {name: _StubAdapter(name=name, behavior="unavailable" if name in unavailable else "ok") for name in names}


def _code_with_markers(sources: tuple[str, ...]) -> str:
    """生成含全部指定数据源标记的沙箱代码。"""
    return "\n".join(f'data_{idx} = $DATA_SOURCE("{name}", "indicator query for {name}")' for idx, name in enumerate(sources))


def _make_engine(
    event_bus: InMemoryEventBus,
    adapters: dict[str, _StubAdapter],
    cache: Any,
    code: str,
    prompts: list[str],
) -> ToolExecutionEngine:
    """构建真实 Engine + 后注入真实 Resolver（LLM 按内容特征分派并捕获全部 prompt）。

    LLM mock 按内容分派（非序数，4-1c R2-F1 教训）：Code 阶段（prompt 含
    「生成代码」）返回注入的 code，其余返回 "ok"；全部 prompt 捕获留存
    （Think prompt 的 arguments repr 断言依据——内外融合双通道之一）。
    """

    async def _llm_dispatch(prompt: str, response_schema: Any) -> str:
        prompts.append(prompt)
        if "生成代码" in prompt:
            return code
        return "ok"

    llm = AsyncMock()
    llm.structured_generate = AsyncMock(side_effect=_llm_dispatch)

    sandbox = AsyncMock()
    sandbox.execute_code = AsyncMock(return_value={"status": "ok", "output": "done"})

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
    event_bus: InMemoryEventBus,
    arguments: dict[str, Any] | None = None,
) -> tuple[Any, DomainError | None, list[str]]:
    """驱动真实 Engine 执行（真实 load_sop 白名单 + ToolCall.arguments 内部数据）。

    返回 (tool_result, error, prompts)——prompts 供 Think prompt 的 arguments
    repr 子串断言（Engine 以 f-string 注入 dict repr 单引号形态，非 json.dumps）。
    仅捕获 DomainError（异常是领域契约：Engine 只抛领域异常，非领域异常
    逃逸直接使测试红——暴露违反异常体系红线的行为）。
    """
    prompts: list[str] = []
    loader = InMemorySkillLoader()
    document = await loader.load_sop(slug)
    engine = _make_engine(event_bus, adapters, cache, code, prompts)
    tool = Tool(tool_id=uuid.uuid4(), name=slug, slug=slug)
    context = ExecutionContext(
        tenant_id=tenant,
        session_id=f"it-{uuid.uuid4().hex[:8]}",
        extensions={"tool_metadata": document.frontmatter},
    )
    executed_arguments = arguments if arguments is not None else {}
    try:
        result = await engine.execute(
            tool_id=tool.tool_id,
            tool=tool,
            tool_call=ToolCall(tool_id=tool.tool_id, arguments=executed_arguments),
            context=context,
        )
        return result, None, prompts
    except DomainError as exc:  # 部分失败收敛语义下的异常断言入口
        return None, exc, prompts


def _injected_source_names(prompts_result: Any) -> set[str]:
    """从 EvidencePackage 提取溯源元数据源名集合。"""
    assert prompts_result is not None and prompts_result.evidence_package is not None
    return {meta.source_name for meta in prompts_result.evidence_package.data_sources}


def _assert_arguments_in_think_prompt(arguments: dict[str, Any], prompts: list[str]) -> None:
    """内外融合双通道断言之一：Think prompt 含 arguments 的 Python repr 子串。

    Think 阶段识别特征串「规划执行步骤」（tool_execution_engine.py:522，
    Engine 以 f-string 注入 dict repr——断言 json 序列化子串必假红）。
    """
    think_prompts = [p for p in prompts if "规划执行步骤" in p]
    assert think_prompts, f"未捕获到 Think 阶段提示词（捕获 {len(prompts)} 条）"
    assert repr(arguments) in think_prompts[0], f"Think prompt 未包含内部数据参数 repr 子串: {think_prompts[0][:120]}"


class TestMixedSkillFullChain:
    """10 个混合数据型 Skills 全链路（双源覆盖 + 溯源元数据 + 内外融合）"""

    @pytest.mark.parametrize("slug", list(MIXED_SKILL_DATA_SOURCES.keys()))
    async def test_skill_full_chain_dual_source(self, slug: str, redis_tenant_cache: Any) -> None:
        """每 Skill 2 源 call_count == 1（并发去重）+ 溯源元数据完备 + 注入源数 == 2"""
        cache, tenant, _tenant_b = redis_tenant_cache
        event_bus = InMemoryEventBus()
        declared = MIXED_SKILL_DATA_SOURCES[slug]
        adapters = _make_adapters(declared)
        arguments = build_min_arguments(slug)
        code = _code_with_markers(declared)
        result, error, prompts = await _run_skill(slug, code, adapters, cache, tenant, event_bus, arguments=arguments)
        assert error is None, f"{slug} 执行失败: {error}"
        assert result is not None and result.status == ToolResultStatus.SUCCESS
        # 双源覆盖：每声明源恰好采集 1 次
        for name in declared:
            assert adapters[name].call_count == 1, f"{slug}/{name}: 采集次数 != 1"
        # 溯源元数据完备（source_name/freshness_score/confidence）
        assert result.evidence_package is not None
        metas = result.evidence_package.data_sources
        assert len(metas) == len(declared), f"{slug}: 注入源数 {len(metas)} != 声明源数 {len(declared)}"
        for meta in metas:
            assert meta.source_name in declared
            assert 0.0 <= meta.freshness_score <= 1.0
            assert 0.0 <= meta.confidence <= 1.0
        # 内外融合双通道：arguments（内部数据）进入 Think prompt
        _assert_arguments_in_think_prompt(arguments, prompts)


class TestCacheAndTenantIsolation:
    """缓存命中 + 跨租户隔离（4-1c R2-F1 判别力先例复用）"""

    async def test_cache_hit_second_run_no_new_fetch(self, redis_tenant_cache: Any) -> None:
        """二次执行同代码：外部采集次数不增（首轮绝对计数守卫防 0==0 伪满足）"""
        cache, tenant, _tenant_b = redis_tenant_cache
        event_bus = InMemoryEventBus()
        slug = "swot-tows"
        declared = MIXED_SKILL_DATA_SOURCES[slug]
        adapters = _make_adapters(declared)
        code = _code_with_markers(declared)
        result, error, _ = await _run_skill(slug, code, adapters, cache, tenant, event_bus)
        assert error is None and result is not None
        first_counts = {name: adp.call_count for name, adp in adapters.items()}
        assert first_counts and all(count >= 1 for count in first_counts.values()), (
            f"首轮零外部采集（标记代码未送达）: {first_counts}"
        )
        result2, error2, _ = await _run_skill(slug, code, adapters, cache, tenant, event_bus)
        assert error2 is None and result2 is not None
        for name, adapter in adapters.items():
            assert adapter.call_count == first_counts[name], f"{name}: 缓存未命中，二次执行产生新外部采集"
        # 二次执行 freshness 仍在 [0,1]
        assert result2.evidence_package is not None
        for meta in result2.evidence_package.data_sources:
            assert 0.0 <= meta.freshness_score <= 1.0

    async def test_tenant_isolation_cross_tenant_no_cache_share(self, redis_tenant_cache: Any) -> None:
        """租户 B 执行同代码：必须全新采集（call_count == first + 1 绝对断言）"""
        cache, tenant, tenant_b = redis_tenant_cache
        event_bus = InMemoryEventBus()
        slug = "swot-tows"
        declared = MIXED_SKILL_DATA_SOURCES[slug]
        adapters = _make_adapters(declared)
        code = _code_with_markers(declared)
        result, error, _ = await _run_skill(slug, code, adapters, cache, tenant, event_bus)
        assert error is None and result is not None
        first_counts = {name: adp.call_count for name, adp in adapters.items()}
        assert first_counts and all(count >= 1 for count in first_counts.values())
        result_b, error_b, _ = await _run_skill(slug, code, adapters, cache, tenant_b, event_bus)
        assert error_b is None and result_b is not None
        for name, adapter in adapters.items():
            assert adapter.call_count == first_counts[name] + 1, f"{name}: 跨租户缓存串用（租户 B 未全新采集）"


class TestKeyMissingDegradation:
    """Key 缺失降级（411 语义断言，4-1c R1-P1-1 判别力先例）"""

    @pytest.mark.parametrize("slug", SINGLE_SENSITIVE_SLUGS)
    async def test_single_sensitive_missing_partial_convergence(self, slug: str, redis_tenant_cache: Any) -> None:
        """单敏感源 Skill 物理缺 1 敏感源：SUCCESS + DataSourceFetchFailed(411) + 其余源注入。

        Round 2 勘正：双敏感 Skill（swot/value-curve/change-management）两源全缺
        会 fetch_many 全失败直传 411（data_source_resolver.py:233-235）而非部分
        收敛——故本用例限定单敏感 Skill（物理缺其唯一敏感源，留 1 个免 Key 源）。
        """
        cache, tenant, _tenant_b = redis_tenant_cache
        event_bus = InMemoryEventBus()
        declared = MIXED_SKILL_DATA_SOURCES[slug]
        missing = [name for name in declared if name in KEY_SENSITIVE_SOURCES]
        assert len(missing) == 1, f"{slug} 应为单敏感 Skill（恰好 1 个敏感源），实际 {missing}"
        # 物理缺敏感源（模拟 Key 缺失被条件注册排除）
        present = tuple(name for name in declared if name not in missing)
        adapters = _make_adapters(present)
        arguments = build_min_arguments(slug)
        code = _code_with_markers(declared)
        result, error, prompts = await _run_skill(slug, code, adapters, cache, tenant, event_bus, arguments=arguments)
        assert error is None, f"{slug} 部分失败应收敛不抛出，实际: {error}"
        assert result is not None and result.status == ToolResultStatus.SUCCESS
        # 411 语义断言（error_code 逐字）
        assert any(
            isinstance(evt, DataSourceFetchFailed) and evt.error_code == "EXCEPTION_411" for evt in event_bus.published_events
        ), f"{slug}: 未发布 error_code=EXCEPTION_411 的 DataSourceFetchFailed 事件"
        # 其余源正常注入 + 内部数据继续分析（arguments 进 Think prompt）
        assert _injected_source_names(result) == set(present)
        _assert_arguments_in_think_prompt(arguments, prompts)

    async def test_dual_sensitive_all_missing_411_propagates(self, redis_tenant_cache: Any) -> None:
        """双敏感 Skill 全缺对照：2 源全失败 → 411 直传播（锁死 fetch_many 全失败契约）。"""
        cache, tenant, _tenant_b = redis_tenant_cache
        event_bus = InMemoryEventBus()
        slug = "swot-tows"
        declared = MIXED_SKILL_DATA_SOURCES[slug]
        # 双敏感 Skill 物理缺全部源（adapters 空）
        adapters: dict[str, _StubAdapter] = {}
        code = _code_with_markers(declared)
        _result, error, _prompts = await _run_skill(slug, code, adapters, cache, tenant, event_bus)
        assert error is not None, "全源缺失应直传播异常（fetch_many 全失败契约）"
        assert error.code == "EXCEPTION_411", f"期望 411 直传播，实际 {error.code}"


class TestSourceUnavailableConvergence:
    """源不可用（5xx）部分失败收敛"""

    async def test_source_unavailable_partial_convergence(self, redis_tenant_cache: Any) -> None:
        """单源 5xx：SUCCESS + 411 事件 + 其余源正常注入"""
        cache, tenant, _tenant_b = redis_tenant_cache
        event_bus = InMemoryEventBus()
        slug = "swot-tows"
        declared = MIXED_SKILL_DATA_SOURCES[slug]
        unavailable = ("newsapi",)
        adapters = _make_adapters(declared, unavailable=unavailable)
        code = _code_with_markers(declared)
        result, error, _ = await _run_skill(slug, code, adapters, cache, tenant, event_bus)
        assert error is None, f"部分失败应收敛不抛出，实际: {error}"
        assert result is not None and result.status == ToolResultStatus.SUCCESS
        expected = set(declared) - set(unavailable)
        assert _injected_source_names(result) == expected
        assert any(
            isinstance(evt, DataSourceFetchFailed) and evt.error_code == "EXCEPTION_411" for evt in event_bus.published_events
        )
