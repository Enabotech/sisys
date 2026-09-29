"""Story 4.1d — 混合数据型 Skills 验收测试（Acceptance Tests）

Real instance integration tests using actual services:
InMemorySkillLoader (real SKILL.md), ToolExecutionEngine,
DataSourceResolverService and Redis cache (test port).
No mocks except external boundaries: data source adapters (_FakeDataSourceAdapter),
LLM client and sandbox.

Run with: poetry run pytest tests/acceptance/test_acceptance_skill_mixed_data.py -v

Prerequisites:
    - Redis service running at test port (SISYS_USE_TEST_PORTS=1 or .env test config)
    - 10 mixed-data Skills SKILL.md with data_sources declarations (Task 2-11)

Tenant Isolation:
    - Per-scenario UUID tenant: sisys:cache:datasource:{tenant}:*
    - Teardown deletes only this scenario's tenant-prefix keys

BDD 风格（范本 test_acceptance_postgresql_relational_layer.py）：
    - @scenario 显式绑定（每场景一个 test_* 函数，带 fixture 参数）
    - 步骤产物经场景级共享领域对象 execution 传递（无 target_fixture）
    - 场景级共享 event_loop + run_until_complete（禁止 @pytest.mark.asyncio）
"""

from __future__ import annotations

import ast
import json
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from src.application.services.data_source_resolver import DataSourceResolverService
from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.application.skills.loader import InMemorySkillLoader
from src.domain.entities.tool import Tool
from src.domain.events.data_source_events import DataSourceFetchFailed
from src.domain.exceptions import (
    BusinessRuleViolationError,
    DataSourceRateLimitError,
    DataSourceResponseError,
    DataSourceUnavailableError,
)
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
from tests.unit.application.skills.skill_mixed_data_contracts import (
    MIXED_SKILL_DATA_SOURCES,
    build_min_arguments,
)

# ===================================================================
# Paths & Constants
# ===================================================================

# 数据契约 SSOT：import contracts 模块唯一来源（R2-F3 统一，声明源经
# MIXED_SKILL_DATA_SOURCES[slug] 查询，场景 slug 由 load_sop 步骤写入 execution）


class _SkillExecution:
    """Skill 执行上下文（场景级共享领域对象：given 装配、when 写入、then 读取）。"""

    def __init__(self) -> None:
        self.slug: str = ""
        self.metadata: Any = None  # ToolMetadata（真实 load_sop 解析的 frontmatter）
        self.adapters: dict[str, _FakeDataSourceAdapter] = {}
        self.result: Any = None  # ToolResult
        self.error: DomainError | None = None
        self.arguments: dict[str, Any] = {}
        self.prompts: list[str] = []
        self.sandbox_codes: list[str] = []
        self.first_call_counts: dict[str, int] | None = None


# ===================================================================
# Test Double（Fake 仅限外部数据源端口适配器）
# ===================================================================


class _FakeDataSourceAdapter:
    """外部数据源测试替身（行为可编程，call_count 记录真实采集次数）。"""

    def __init__(self, name: str, behavior: str = "ok", ttl_seconds: int = 3600) -> None:
        self._ref = DataSourceRef(
            name=name,
            url=f"https://fake.local/{name}",
            ttl_seconds=ttl_seconds,
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
        if self.behavior == "rate_limit":
            raise DataSourceRateLimitError(
                message=f"数据源 {self._ref.name} 触发限流（模拟 429）",
                context={"source_name": self._ref.name},
            )
        if self.behavior == "bad_response":
            raise DataSourceResponseError(
                message=f"数据源 {self._ref.name} 响应解析失败（模拟非法 JSON）",
                context={"source_name": self._ref.name},
            )
        now = datetime.now(UTC)
        return DataSourceResult(
            source_name=self._ref.name,
            payload=json.dumps({"indicator": query.query, "value": 1.23}),
            source_timestamp=now,
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=now, ttl_seconds=self._ref.ttl_seconds),
            confidence=0.9,
        )


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    """真实内存事件总线（失败事件断言依据）。"""
    return InMemoryEventBus()


@pytest.fixture
def tenant_id() -> uuid.UUID:
    """场景级 UUID 租户（缓存键隔离前缀）。"""
    return uuid.uuid4()


@pytest.fixture
def execution() -> _SkillExecution:
    """场景级共享执行上下文（given 装配 → when 写入产物 → then 读取断言）。"""
    return _SkillExecution()


@pytest.fixture
def redis_client(event_loop, acceptance_env_config, tenant_id: uuid.UUID) -> Generator[Any, None, None]:
    """场景级独立 Redis 客户端（连接池绑定本场景事件循环，teardown 清理租户缓存后同循环关闭）。

    必须场景级独立创建：session 级共享客户端的连接池持有前一场景已关闭
    事件循环的连接，跨场景复用抛 RuntimeError "Event loop is closed"。

    Teardown（R1-F2，对齐 4-1c 范本条件清理）：仅 delete_pattern 本场景租户
    前缀缓存键（ping 守卫——Redis 不可用场景已被背景步骤 pytest.skip 跳过，
    无键可清，不得把合法 skip 变成 teardown ERROR）；close 无条件执行
    （不依赖服务端存活）。场景级真实断言均在场景体内先行抛出，不受此处
    异常兜底影响。
    """
    import redis.asyncio as aioredis

    client = aioredis.Redis(
        host=acceptance_env_config.redis.host,
        port=acceptance_env_config.redis.port,
        password=acceptance_env_config.redis.password,
        decode_responses=True,
    )
    yield client
    try:
        try:
            redis_available = bool(_run_async(event_loop, client.ping()))
        except Exception:
            # Redis 不可用：场景已被背景步骤 pytest.skip 跳过，无本租户缓存键可清
            # （清理对象不存在，非掩盖告警——R2-F11②：仅 ping 守卫允许静默）
            redis_available = False
        if redis_available:
            # Redis 存活态：delete 失败不吞——真实清理缺陷应显式红（禁止掩盖）
            cache = RedisAdapter(redis_client=client)
            _run_async(event_loop, cache.delete_pattern(f"sisys:cache:datasource:{tenant_id}:*"))
    finally:
        # close 无条件执行（不依赖服务端存活；delete 失败也不泄漏连接）
        _run_async(event_loop, client.close())


@pytest.fixture
def resolver_cache(redis_client: Any, event_loop) -> Any:
    """真实 Redis 缓存适配器（ping 失败返回 None，执行入口二次实证 skip）。"""
    try:
        _run_async(event_loop, redis_client.ping())
        return RedisAdapter(redis_client=redis_client)
    except Exception:
        return None


# ===================================================================
# Helpers
# ===================================================================


def _run_async(event_loop, coro):
    """同步调度异步协程（BDD 步骤禁止 @pytest.mark.asyncio，共用场景级循环）。"""
    return event_loop.run_until_complete(coro)


def _declared_sources(execution: _SkillExecution) -> tuple[str, ...]:
    """当前技能的声明源集合（SSOT 表）。"""
    return MIXED_SKILL_DATA_SOURCES[execution.slug]


def _make_adapters(slug: str, behavior_by_source: dict[str, str] | None = None) -> dict[str, _FakeDataSourceAdapter]:
    """按声明源构建 Fake 适配器映射（behavior 可编程，unregistered 物理排除）。"""
    behaviors = behavior_by_source or {}
    return {
        name: _FakeDataSourceAdapter(name=name, behavior=behaviors.get(name, "ok"))
        for name in MIXED_SKILL_DATA_SOURCES[slug]
        if behaviors.get(name) != "unregistered"
    }


def _code_with_markers(sources: tuple[str, ...]) -> str:
    """生成含全部指定数据源标记的沙箱代码。"""
    return "\n".join(f'data_{idx} = $DATA_SOURCE("{name}", "indicator query for {name}")' for idx, name in enumerate(sources))


def _assert_cache_available(resolver_cache: Any, redis_client: Any, event_loop) -> Any:
    """Redis 不可用时显式 pytest.skip（执行时实证 ping + lazy 重建 cache）。"""
    if redis_client is None:
        pytest.skip("Redis 客户端未初始化")
    try:
        _run_async(event_loop, redis_client.ping())
    except Exception as exc:
        pytest.skip(f"Redis 不可用: {exc}")
    if resolver_cache is None:
        resolver_cache = RedisAdapter(redis_client=redis_client)
    return resolver_cache


def _run_engine(
    execution: _SkillExecution,
    event_loop,
    cache: Any,
    event_bus: InMemoryEventBus,
    tenant: uuid.UUID,
    code: str,
    arguments: dict[str, Any] | None = None,
) -> None:
    """驱动真实 Engine 执行含标记代码，产物写入 execution（结果/异常/prompt/代码）。

    extensions["tool_metadata"] 注入真实 load_sop 解析的 frontmatter——
    复刻 4-1c 双入口接线语义；LLM 按内容特征分派（「生成代码」→ Code 阶段）
    并捕获全部 prompt（Think prompt 的 arguments repr 断言依据）。
    """

    async def _llm_dispatch(prompt: str, response_schema: Any) -> str:
        execution.prompts.append(prompt)
        if "生成代码" in prompt:
            return code
        return "ok"

    llm = AsyncMock()
    llm.structured_generate = AsyncMock(side_effect=_llm_dispatch)

    async def _sandbox_execute(session_id: str, code_arg: str, **_kwargs: Any) -> dict[str, Any]:
        execution.sandbox_codes.append(code_arg)
        return {"status": "ok", "output": "done"}

    sandbox = AsyncMock()
    sandbox.start_container = AsyncMock()
    sandbox.execute_code = AsyncMock(side_effect=_sandbox_execute)
    sandbox.stop_container = AsyncMock()

    engine = ToolExecutionEngine(llm_client=llm, sandbox=sandbox)
    resolver = DataSourceResolverService(adapters=execution.adapters, cache=cache, event_publisher=event_bus)
    engine.set_data_source_resolver(resolver)

    tool = Tool(tool_id=uuid.uuid4(), name="测试工具", slug=execution.slug)
    exec_context = ExecutionContext(
        tenant_id=tenant,
        session_id=f"sess-{uuid.uuid4().hex[:8]}",
        extensions={"tool_metadata": execution.metadata},
    )
    execution.arguments = arguments if arguments is not None else {}
    try:
        execution.result = _run_async(
            event_loop,
            engine.execute(
                tool_id=tool.tool_id,
                tool=tool,
                tool_call=ToolCall(tool_id=tool.tool_id, arguments=execution.arguments),
                context=exec_context,
            ),
        )
        execution.error = None
    except DomainError as exc:  # BDD 异常断言统一入口（isinstance + code 在 Then 步骤校验；
        # 仅捕获领域异常——非领域异常逃逸直接使场景红，暴露异常体系红线违规）
        execution.result = None
        execution.error = exc


def _injected_data_sources(execution: _SkillExecution) -> dict[str, Any]:
    """从沙箱收到的代码解析 DATA_SOURCES 前言（repr Python 字面量，ast 可逆）。"""
    codes = execution.sandbox_codes
    assert codes, "沙箱未收到注入后的代码（采集链路未到达 Execute 阶段）"
    for code in codes:
        first_line = code.split("\n", 1)[0]
        if first_line.startswith("DATA_SOURCES = "):
            injected: dict[str, Any] = ast.literal_eval(first_line.removeprefix("DATA_SOURCES = "))
            return injected
    raise AssertionError(f"缺少 DATA_SOURCES 数据前言: {codes[-1].splitlines()[0][:80]}")


# ===================================================================
# Background Steps
# ===================================================================


@given("数据采集基础设施已初始化")
def data_source_infra_initialized(redis_client, event_loop):
    """验证 Redis 服务可用（不可用则跳过场景）。"""
    try:
        _run_async(event_loop, redis_client.ping())
    except Exception as exc:
        pytest.skip(f"Redis 不可用: {exc}")


# ===================================================================
# AC-1/AC-4: 双源采集全链路（Happy Path）
# ===================================================================


@scenario("test_acceptance_skill_mixed_data.feature", "swot-tows 全链路双源采集与内外数据融合")
def test_swot_tows_full_chain_dual_source(execution: _SkillExecution):
    """swot-tows 双源并发采集 + 内部数据融合 + 溯源元数据全链路。"""
    pass


@given(parsers.parse('加载技能 "{slug}" 的 L2 技能元数据'))
def load_skill_metadata(execution: _SkillExecution, event_loop, slug):
    """真实 load_sop 加载 SKILL.md，frontmatter 即白名单依据。"""
    loader = InMemorySkillLoader()
    document = _run_async(event_loop, loader.load_sop(slug))
    execution.slug = slug
    execution.metadata = document.frontmatter


@given("该技能全部声明数据源适配器行为正常")
def all_declared_adapters_ok(execution: _SkillExecution):
    """按声明源构建全部行为正常的 Fake 适配器。"""
    execution.adapters = _make_adapters(execution.slug)


@when("该技能携带内部数据参数执行且全部声明数据源标记经 Engine Execute 阶段处理")
def run_with_internal_arguments(
    execution: _SkillExecution,
    event_loop,
    event_bus: InMemoryEventBus,
    tenant_id: uuid.UUID,
    resolver_cache,
    redis_client,
):
    """携带内部数据参数执行（arguments 从契约库构造，repr 进 Think prompt）。"""
    cache = _assert_cache_available(resolver_cache, redis_client, event_loop)
    _run_engine(
        execution,
        event_loop,
        cache,
        event_bus,
        tenant_id,
        _code_with_markers(_declared_sources(execution)),
        arguments=build_min_arguments(execution.slug),
    )


@then("执行结果为成功")
def verify_execution_success(execution: _SkillExecution):
    """断言执行成功（无异常 + SUCCESS 状态）。"""
    assert execution.error is None, f"执行失败: {execution.error}"
    assert execution.result is not None
    assert execution.result.status == ToolResultStatus.SUCCESS


@then("每个声明数据源恰好采集 1 次")
def verify_each_source_fetched_once(execution: _SkillExecution):
    """断言每声明源 call_count == 1（并发去重语义）。"""
    assert execution.error is None, f"执行失败: {execution.error}"
    assert execution.result.status == ToolResultStatus.SUCCESS
    for name in _declared_sources(execution):
        assert execution.adapters[name].call_count == 1, f"数据源 {name} 采集次数 != 1"


@then("输出元数据含 source 与 freshness 与 confidence")
def verify_evidence_metadata_complete(execution: _SkillExecution):
    """断言溯源元数据完备（source_name/freshness/confidence ∈ [0,1]）。"""
    result = execution.result
    assert result is not None and result.evidence_package is not None
    metas = result.evidence_package.data_sources
    assert len(metas) == len(_declared_sources(execution))
    for meta in metas:
        assert meta.source_name in _declared_sources(execution)
        assert 0.0 <= meta.freshness_score <= 1.0
        assert 0.0 <= meta.confidence <= 1.0


@scenario("test_acceptance_skill_mixed_data.feature", "ansoff-matrix 双源采集链路")
def test_ansoff_matrix_dual_source_chain(execution: _SkillExecution):
    """ansoff-matrix 双源采集链路。"""
    pass


@scenario("test_acceptance_skill_mixed_data.feature", "value-curve-analysis 双源采集链路")
def test_value_curve_analysis_dual_source_chain(execution: _SkillExecution):
    """value-curve-analysis 双源采集链路。"""
    pass


@scenario("test_acceptance_skill_mixed_data.feature", "ge-mckinsey-matrix 双源采集链路")
def test_ge_mckinsey_matrix_dual_source_chain(execution: _SkillExecution):
    """ge-mckinsey-matrix 双源采集链路。"""
    pass


@scenario("test_acceptance_skill_mixed_data.feature", "space-matrix 双源采集链路")
def test_space_matrix_dual_source_chain(execution: _SkillExecution):
    """space-matrix 双源采集链路。"""
    pass


@scenario("test_acceptance_skill_mixed_data.feature", "value-chain-analysis 双源采集链路")
def test_value_chain_analysis_dual_source_chain(execution: _SkillExecution):
    """value-chain-analysis 双源采集链路。"""
    pass


@scenario("test_acceptance_skill_mixed_data.feature", "vrio-framework 双源采集链路")
def test_vrio_framework_dual_source_chain(execution: _SkillExecution):
    """vrio-framework 双源采集链路。"""
    pass


@scenario("test_acceptance_skill_mixed_data.feature", "bsc-scorecard 双源采集链路")
def test_bsc_scorecard_dual_source_chain(execution: _SkillExecution):
    """bsc-scorecard 双源采集链路。"""
    pass


@scenario("test_acceptance_skill_mixed_data.feature", "kpi-tree 双源采集链路")
def test_kpi_tree_dual_source_chain(execution: _SkillExecution):
    """kpi-tree 双源采集链路。"""
    pass


@scenario("test_acceptance_skill_mixed_data.feature", "change-management 双源采集链路")
def test_change_management_dual_source_chain(execution: _SkillExecution):
    """change-management 双源采集链路。"""
    pass


@when("该技能全部声明数据源标记经 Engine Execute 阶段处理")
def run_all_declared_markers(
    execution: _SkillExecution,
    event_loop,
    event_bus: InMemoryEventBus,
    tenant_id: uuid.UUID,
    resolver_cache,
    redis_client,
):
    """驱动 Engine 处理全部声明源标记代码。"""
    cache = _assert_cache_available(resolver_cache, redis_client, event_loop)
    _run_engine(execution, event_loop, cache, event_bus, tenant_id, _code_with_markers(_declared_sources(execution)))


@then("注入 DATA_SOURCES 字典键集合等于声明数据源集合")
def verify_injected_keys_match_declared(execution: _SkillExecution):
    """断言注入 DATA_SOURCES dict 键集合 == 声明源集合。"""
    injected = _injected_data_sources(execution)
    assert set(injected.keys()) == set(_declared_sources(execution))


# ===================================================================
# AC-6: Edge Cases（策略违规与降级）
# ===================================================================


@scenario("test_acceptance_skill_mixed_data.feature", "白名单外数据源标记被拒绝")
def test_whitelist_violation_rejected(execution: _SkillExecution):
    """白名单外源标记 → 207 策略违规。"""
    pass


@when(parsers.parse('代码含白名单外数据源 "{source}" 标记经 Engine Execute 阶段处理'))
def run_whitelist_out_marker(
    execution: _SkillExecution,
    event_loop,
    event_bus: InMemoryEventBus,
    tenant_id: uuid.UUID,
    resolver_cache,
    redis_client,
    source: str,
):
    """驱动含白名单外源标记的代码（策略违规路径，无需适配器）。"""
    cache = _assert_cache_available(resolver_cache, redis_client, event_loop)
    _run_engine(execution, event_loop, cache, event_bus, tenant_id, _code_with_markers((source,)))


@then("抛出 BusinessRuleViolationError")
def verify_business_rule_violation_raised(execution: _SkillExecution):
    """断言抛出 207 策略违规异常。"""
    assert isinstance(execution.error, BusinessRuleViolationError), (
        f"期望 BusinessRuleViolationError，实际: {execution.error!r}"
    )


@then(parsers.parse("错误码为 EXCEPTION_{code:d}"))
def verify_error_code(execution: _SkillExecution, code: int):
    """断言异常错误码与消息非空。"""
    error = execution.error
    assert error is not None, "未捕获到异常"
    expected = f"EXCEPTION_{code}"
    assert error.code == expected, f"期望错误码 {expected}，实际 {error.code}"
    assert error.message, "异常消息不能为空"


@scenario("test_acceptance_skill_mixed_data.feature", "数据源不可用部分失败收敛")
def test_source_unavailable_partial_convergence(execution: _SkillExecution):
    """单源不可用 → SUCCESS + DataSourceFetchFailed(411) 部分收敛。"""
    pass


@given(parsers.parse('数据源 "{source}" 配置为不可用'))
def source_configured_unavailable(execution: _SkillExecution, source: str):
    """指定源行为不可用（模拟 5xx），其余声明源行为正常。"""
    execution.adapters = _make_adapters(execution.slug, behavior_by_source={source: "unavailable"})


@then("已发布 DataSourceFetchFailed 事件")
def verify_fetch_failed_event_published(event_bus: InMemoryEventBus):
    """断言发布 411 语义失败事件（源不可用与未注册同为 411）。"""
    events = event_bus.published_events
    assert any(isinstance(evt, DataSourceFetchFailed) and evt.error_code == "EXCEPTION_411" for evt in events), (
        "未发布 error_code=EXCEPTION_411 的 DataSourceFetchFailed 事件"
    )


@then("可用数据源数据已注入")
def verify_available_sources_injected(execution: _SkillExecution):
    """断言部分失败收敛：仅行为正常源注入（失败位 None 不进 DATA_SOURCES）。"""
    assert execution.error is None, f"部分失败应收敛不抛出，实际: {execution.error}"
    injected = _injected_data_sources(execution)
    expected = {
        name
        for name in _declared_sources(execution)
        if name in execution.adapters and execution.adapters[name].behavior == "ok"
    }
    assert set(injected.keys()) == expected
    assert injected, "可用数据源注入集合不能为空"


@scenario("test_acceptance_skill_mixed_data.feature", "Key 缺失降级与内部数据继续分析")
def test_key_missing_degradation(execution: _SkillExecution):
    """单敏感源未注册（Key 缺失）→ 411 降级 + 内部数据继续分析。"""
    pass


@given(parsers.parse('数据源 "{source}" 未注册'))
def source_unregistered(execution: _SkillExecution, source: str):
    """单敏感源 Key 缺失降级：物理排除该源适配器（模拟条件注册未生效）。"""
    execution.adapters = _make_adapters(execution.slug, behavior_by_source={source: "unregistered"})


@then("内部数据参数已进入规划提示词")
def verify_arguments_in_think_prompt(execution: _SkillExecution):
    """断言 Think prompt 含 arguments 的 Python repr 子串（内部数据通道）。

    Engine 以 f-string 注入 dict repr（单引号形态，非 json.dumps）；
    Think 阶段识别特征串「规划执行步骤」（tool_execution_engine.py:522）。
    """
    think_prompts = [p for p in execution.prompts if "规划执行步骤" in p]
    assert think_prompts, f"未捕获到 Think 阶段提示词（捕获 {len(execution.prompts)} 条）"
    assert repr(execution.arguments) in think_prompts[0], f"Think prompt 未包含内部数据参数 repr 子串: {think_prompts[0][:120]}"


@scenario("test_acceptance_skill_mixed_data.feature", "缓存命中二次执行不重复采集")
def test_cache_hit_no_refetch(execution: _SkillExecution):
    """二次执行缓存命中，外部采集次数不增。"""
    pass


@when("该技能连续两次执行全部声明数据源标记处理")
def run_all_declared_markers_twice(
    execution: _SkillExecution,
    event_loop,
    event_bus: InMemoryEventBus,
    tenant_id: uuid.UUID,
    resolver_cache,
    redis_client,
):
    """连续两次执行同标记代码（首轮绝对计数守卫 + 二次不增）。"""
    cache = _assert_cache_available(resolver_cache, redis_client, event_loop)
    code = _code_with_markers(_declared_sources(execution))
    _run_engine(execution, event_loop, cache, event_bus, tenant_id, code)
    assert execution.error is None, f"第一次执行失败: {execution.error}"
    execution.first_call_counts = {name: adp.call_count for name, adp in execution.adapters.items()}
    # 首轮绝对计数守卫（4-1c R2-F1）：防相对断言被 0==0 伪满足
    first_counts = execution.first_call_counts
    assert first_counts and all(count >= 1 for count in first_counts.values()), (
        f"首轮零外部采集（标记代码未送达 Sandbox）: {first_counts}"
    )
    _run_engine(execution, event_loop, cache, event_bus, tenant_id, code)


@then("第二次执行外部采集次数不增加")
def verify_second_run_no_new_fetch(execution: _SkillExecution):
    """断言缓存命中：第二次执行各源 call_count 与首轮一致。"""
    assert execution.error is None, f"第二次执行失败: {execution.error}"
    first_counts = execution.first_call_counts
    assert first_counts is not None, "缺少首轮采集计数（首轮守卫未执行）"
    for name, adapter in execution.adapters.items():
        assert adapter.call_count == first_counts[name], f"数据源 {name} 缓存未命中：第二次执行产生新外部采集"


@then("输出元数据 freshness 评分在 0 到 1 之间")
def verify_freshness_in_range(execution: _SkillExecution):
    """断言溯源元数据 freshness_score ∈ [0,1]。"""
    result = execution.result
    assert result is not None and result.evidence_package is not None
    for meta in result.evidence_package.data_sources:
        assert 0.0 <= meta.freshness_score <= 1.0


@scenario("test_acceptance_skill_mixed_data.feature", "纯内部框架 Skill 空白名单安全失败")
def test_pure_internal_skill_empty_whitelist_safe_failure(execution: _SkillExecution):
    """纯内部框架 Skill 空白名单含标记 → 207 安全失败（永久锚定——D8，空白名单为纯内部型永久设计态）。"""
    pass


@scenario("test_acceptance_skill_mixed_data.feature", "内外数据融合双通道并存")
def test_dual_channel_internal_external_fusion(execution: _SkillExecution):
    """arguments 进 Think prompt + DATA_SOURCES 注入双通道并存。"""
    pass


@then("注入代码前缀含 DATA_SOURCES 字典")
def verify_preamble_contains_data_sources(execution: _SkillExecution):
    """断言注入沙箱的代码首行为 DATA_SOURCES 前言（外部基准通道）。"""
    codes = execution.sandbox_codes
    assert codes, "沙箱未收到代码（采集链路未到达 Execute 阶段）"
    assert any(code.split("\n", 1)[0].startswith("DATA_SOURCES = ") for code in codes), (
        "注入代码缺少 DATA_SOURCES 前言（外部基准注入通道未生效）"
    )
