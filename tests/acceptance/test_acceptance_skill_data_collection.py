"""Story 4.1c — Skills 数据采集集成验收测试（BDD 场景步骤实现）。

6 个外部数据型 Skills 复用 Story 4.1b 数据采集基础设施的端到端验收：
真实 InMemorySkillLoader（加载真实 SKILL.md）+ 真实 DataSourceResolverService +
真实 Redis 缓存 + 真实 ToolExecutionEngine；Mock 仅限端口替身
（_FakeDataSourceAdapter 数据源 / LLM 客户端 / 沙箱）。

结构范本：test_acceptance_postgresql_relational_layer.py（显式 @scenario 场景绑定 +
按 AC 分节 + Background 服务可用性动态 skip）；
领域基建范本：test_acceptance_data_source.py（Story 4.1b）。

Run with:
    poetry run pytest tests/acceptance/test_acceptance_skill_data_collection.py -v

Prerequisites:
    - Redis 服务可用（默认 localhost:6379，可通过 SISYS_TEST_REDIS_* 环境变量覆盖；
      不可用时场景在 Background 步骤 pytest.skip() 动态跳过，禁止写死 skip）

测试隔离（TestTenant）:
    - 场景级 UUID 租户前缀，teardown 仅 delete_pattern 本租户缓存键，禁止全库 flush
    - 场景级独立 Redis 客户端 + 场景级共享 event_loop（session 客户端跨场景复用
      会抛 "Event loop is closed"，4-1b 探针实测教训）
    - BDD 步骤函数禁止 @pytest.mark.asyncio（context 数据丢失），统一 _run_async 调度
    - xdist_group("data-source-cache")：与共享缓存键的测试同 worker 串行
"""

from __future__ import annotations

import ast
import asyncio
import json
import uuid
from collections.abc import Coroutine, Generator
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

FEATURE = "test_acceptance_skill_data_collection.feature"

# 全部场景归入 data-source-cache 组: 与共享缓存键的测试在同一 worker 串行执行
pytestmark = pytest.mark.xdist_group("data-source-cache")

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context(
    event_loop: asyncio.AbstractEventLoop,
    acceptance_env_config: Any,
) -> Generator[dict[str, Any], None, None]:
    """BDD 步骤间共享状态容器（场景级 UUID 租户 + 场景级共享事件循环 + 场景级独立 Redis 客户端）。

    Redis 客户端必须场景级独立创建（不用 session 级共享 fixture）：session 客户端的
    连接池持有前一场景已关闭事件循环的连接，跨场景复用会抛 RuntimeError
    "Event loop is closed"（4-1b 探针实测复现）。场景级创建 + 同循环 teardown 关闭
    彻底规避跨循环连接污染；teardown 仅清理本场景租户前缀缓存键。
    """
    import redis.asyncio as aioredis

    redis_client = aioredis.Redis(
        host=acceptance_env_config.redis.host,
        port=acceptance_env_config.redis.port,
        password=acceptance_env_config.redis.password,
        decode_responses=True,
    )
    ctx: dict[str, Any] = {
        "_tenant": uuid.uuid4(),
        "_loop": event_loop,
        "_redis_client": redis_client,
    }
    yield ctx

    # teardown: 仅清理本场景创建的缓存键（delete_pattern 限定租户前缀）+ 同循环关闭客户端
    cache = ctx.get("cache")
    if cache is not None:
        _run_async(event_loop, cache.delete_pattern(f"sisys:cache:datasource:{ctx['_tenant']}:*"))
    _run_async(event_loop, redis_client.close())


# ===================================================================
# 测试替身（Mock 仅限外部数据源端口适配器）
# ===================================================================


class _FakeDataSourceAdapter:
    """外部数据源测试替身（替代真实外部 HTTP API，行为可编程）。

    实现 DataSourcePort 契约（fetch/get_metadata/health_check），
    call_count 记录真实采集次数，供"缓存命中不重复采集"等断言使用。
    范本：test_acceptance_data_source.py（Story 4.1b）。
    """

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
# 辅助函数
# ===================================================================


def _run_async(event_loop: asyncio.AbstractEventLoop, coro: Coroutine[Any, Any, Any]) -> Any:
    """在场景级共享事件循环上同步调度协程。

    BDD 步骤函数禁止 @pytest.mark.asyncio（context 数据丢失）；
    aioredis/asyncio.Lock 等对象在首次使用时绑定事件循环，
    必须复用同一循环，否则抛 "Event loop is closed" 跨循环错误。
    """
    return event_loop.run_until_complete(coro)


def _declared_sources(context: dict[str, Any]) -> tuple[str, ...]:
    """当前场景技能的声明源有序集合（SSOT 表，用于构造标记代码与适配器）。"""
    return SKILL_DATA_SOURCES[context["slug"]]


def _make_adapters(context: dict[str, Any], behavior_by_source: dict[str, str] | None = None) -> None:
    """按当前技能声明源构建 Fake 适配器映射（behavior_by_source 可编程行为）。"""
    behaviors = behavior_by_source or {}
    context["adapters"] = {
        name: _FakeDataSourceAdapter(name=name, behavior=behaviors.get(name, "ok"))
        for name in _declared_sources(context)
        if behaviors.get(name) != "unregistered"
    }


def _make_engine(context: dict[str, Any], code: str) -> ToolExecutionEngine:
    """构建真实 ToolExecutionEngine（Mock LLM/Sandbox 端口适配器）+ 后注入真实 Resolver。

    LLM mock 按调用顺序响应（范本 test_acceptance_data_source.py Round 1 重构）：
    1. Think 阶段（第 1 次调用）→ 返回 "ok"
    2. Code 阶段（第 2 次调用）→ 返回上下文注入的 code（含 DATA_SOURCE 标记）
    3. Validate 阶段（第 3 次调用）→ 返回 "ok"
    """
    llm_call_count = {"n": 0}

    async def _llm_dispatch(prompt: str, response_schema: Any) -> str:
        llm_call_count["n"] += 1
        if llm_call_count["n"] == 2:
            return code
        return "ok"

    llm = AsyncMock()
    llm.structured_generate = AsyncMock(side_effect=_llm_dispatch)
    context["llm_mock"] = llm

    async def _sandbox_execute(session_id: str, code_arg: str, **_kwargs: Any) -> dict[str, Any]:
        context.setdefault("sandbox_codes", []).append(code_arg)
        return {"status": "ok", "output": "done"}

    sandbox = AsyncMock()
    sandbox.start_container = AsyncMock()
    sandbox.execute_code = AsyncMock(side_effect=_sandbox_execute)
    sandbox.stop_container = AsyncMock()
    context["sandbox_mock"] = sandbox

    engine = ToolExecutionEngine(llm_client=llm, sandbox=sandbox)
    resolver = DataSourceResolverService(
        adapters=context["adapters"],
        cache=context["cache"],
        event_publisher=context["event_bus"],
    )
    context["resolver"] = resolver
    engine.set_data_source_resolver(resolver)
    return engine


def _code_with_markers(sources: tuple[str, ...]) -> str:
    """生成含全部指定数据源标记的沙箱代码。"""
    return "\n".join(f'data_{idx} = $DATA_SOURCE("{name}", "indicator query for {name}")' for idx, name in enumerate(sources))


def _run_engine(context: dict[str, Any], code: str) -> None:
    """驱动真实 Engine 执行含标记代码，异常捕获到 context["query_error"]。

    extensions["tool_metadata"] 注入真实 load_sop 解析出的 ToolMetadata ——
    复刻 Task 1 生产链路接线后的语义（白名单依据来自 L2 SKILL.md frontmatter）。
    """
    _assert_redis_available(context)
    context.setdefault("adapters", {})
    engine = _make_engine(context, code)
    tool = Tool(tool_id=uuid.uuid4(), name="测试工具", slug=context.get("slug", "test-tool"))
    exec_context = ExecutionContext(
        tenant_id=context["_tenant"],
        session_id=f"sess-{uuid.uuid4().hex[:8]}",
        extensions={"tool_metadata": context["metadata"]},
    )
    try:
        result = _run_async(
            context["_loop"],
            engine.execute(
                tool_id=tool.tool_id,
                tool=tool,
                tool_call=ToolCall(tool_id=tool.tool_id, arguments={}),
                context=exec_context,
            ),
        )
        context["tool_result"] = result
        context["query_error"] = None
    except Exception as exc:  # BDD 异常断言统一入口（isinstance + code 在 Then 步骤校验）
        context["tool_result"] = None
        context["query_error"] = exc


def _injected_data_sources(context: dict[str, Any]) -> dict[str, Any]:
    """从沙箱实际收到的代码中解析 DATA_SOURCES 前言字典。

    Engine 五阶段可能多次调用沙箱（Execute 注入代码 + 后续阶段其他代码），
    遍历全部捕获代码，取含 DATA_SOURCES 前言的那一份。
    """
    codes = context.get("sandbox_codes") or []
    assert codes, "沙箱未收到注入后的代码（采集链路未到达 Execute 阶段）"
    for code in codes:
        first_line = code.split("\n", 1)[0]
        if first_line.startswith("DATA_SOURCES = "):
            # 前言为 repr Python 字面量（4-1b R2-P0-1 修复：json.dumps → repr，ast.literal_eval 可逆）
            injected: dict[str, Any] = ast.literal_eval(first_line.removeprefix("DATA_SOURCES = "))
            return injected
    raise AssertionError(f"缺少 DATA_SOURCES 数据前言: {codes[-1].splitlines()[0][:80]}")


def _assert_redis_available(context: dict[str, Any]) -> None:
    """执行入口二次实证 Redis 可用性（Background 首道检查的防御性补充，防中途掉线）。"""
    client = context.get("_redis_client")
    if client is None:
        pytest.skip("Redis 客户端未初始化")
    try:
        _run_async(context["_loop"], client.ping())
    except Exception as exc:
        pytest.skip(f"Redis 不可用: {exc}")


# ===================================================================
# Background Steps
# ===================================================================


@given("数据采集基础设施已初始化")
def given_infra_initialized(context: dict[str, Any]) -> None:
    """初始化场景级事件总线与真实 Redis 缓存适配器。"""
    context["event_bus"] = InMemoryEventBus()
    context["cache"] = RedisAdapter(redis_client=context["_redis_client"])


@given("Redis 缓存服务可用")
def given_redis_service_available(context: dict[str, Any]) -> None:
    """验证 Redis 服务可用（不可用时场景整体动态跳过，对齐范本 Background 模式）。"""
    try:
        _run_async(context["_loop"], context["_redis_client"].ping())
    except Exception as exc:
        pytest.skip(f"Redis not available: {exc}")


# ===================================================================
# AC-4: 六个外部数据型 Skills 全链路并发采集
# ===================================================================


@scenario(FEATURE, "pestel-analysis 六源并发采集全链路")
def test_pestel_analysis_full_chain(context: dict[str, Any]) -> None:
    """pestel-analysis 六源并发采集 + 注入 + 溯源元数据完备。"""
    pass


@scenario(FEATURE, "porters-five-forces 三源并发采集链路")
def test_porters_five_forces_full_chain(context: dict[str, Any]) -> None:
    """porters-five-forces 三源并发采集链路。"""
    pass


@scenario(FEATURE, "appeals-analysis 三源并发采集链路")
def test_appeals_analysis_full_chain(context: dict[str, Any]) -> None:
    """appeals-analysis 三源并发采集链路。"""
    pass


@scenario(FEATURE, "competitor-analysis 六源并发采集链路")
def test_competitor_analysis_full_chain(context: dict[str, Any]) -> None:
    """competitor-analysis 六源并发采集链路。"""
    pass


@scenario(FEATURE, "scenario-planning 三源并发采集链路")
def test_scenario_planning_full_chain(context: dict[str, Any]) -> None:
    """scenario-planning 三源并发采集链路。"""
    pass


@scenario(FEATURE, "disruptive-innovation 三源采集链路（专利双库 + 市场单源）")
def test_disruptive_innovation_full_chain(context: dict[str, Any]) -> None:
    """disruptive-innovation 三源采集链路（专利双库 + 市场单源）。"""
    pass


@given(parsers.parse('加载技能 "{slug}" 的 L2 技能元数据'))
def given_load_skill_metadata(context: dict[str, Any], slug: str) -> None:
    """真实 InMemorySkillLoader.load_sop 加载真实 SKILL.md，frontmatter 即白名单依据。"""
    context["slug"] = slug
    loader = InMemorySkillLoader()
    document = _run_async(context["_loop"], loader.load_sop(slug))
    context["metadata"] = document.frontmatter
    context["skill_document"] = document


@given("全部声明数据源适配器行为正常")
def given_all_adapters_ok(context: dict[str, Any]) -> None:
    """按当前技能声明源构建全部行为正常的 Fake 适配器。"""
    _make_adapters(context)


@when("该技能全部声明数据源标记经 Engine Execute 阶段处理")
def when_run_all_declared_markers(context: dict[str, Any]) -> None:
    """生成含全部声明源标记的沙箱代码并驱动真实 Engine 执行。"""
    _run_engine(context, _code_with_markers(_declared_sources(context)))


@then("每个声明数据源恰好采集 1 次")
def then_each_source_fetched_once(context: dict[str, Any]) -> None:
    """并发去重语义：每个声明源恰好采集 1 次，执行结果 SUCCESS。"""
    assert context["query_error"] is None, f"执行失败: {context['query_error']}"
    assert context["tool_result"].status == ToolResultStatus.SUCCESS
    for name in _declared_sources(context):
        assert context["adapters"][name].call_count == 1, f"数据源 {name} 采集次数 != 1"


@then("注入 DATA_SOURCES 字典键集合等于声明数据源集合")
def then_injected_keys_match_declared(context: dict[str, Any]) -> None:
    """沙箱收到的 DATA_SOURCES 前言键集合与声明源集合双向一致。"""
    injected = _injected_data_sources(context)
    assert set(injected.keys()) == set(_declared_sources(context))


@then("输出元数据含 source 与 freshness 与 confidence")
def then_evidence_metadata_complete(context: dict[str, Any]) -> None:
    """EvidencePackage.data_sources 溯源元数据完备（源名/新鲜度/置信度）。"""
    result = context["tool_result"]
    assert result is not None and result.evidence_package is not None
    metas = result.evidence_package.data_sources
    assert len(metas) == len(_declared_sources(context))
    for meta in metas:
        assert meta.source_name in _declared_sources(context)
        assert 0.0 <= meta.freshness_score <= 1.0
        assert 0.0 <= meta.confidence <= 1.0


# ===================================================================
# AC-6: 异常路径与安全失败不变量（Edge Cases）
# ===================================================================


@scenario(FEATURE, "沙箱代码引用白名单外数据源安全失败")
def test_whitelist_violation_safety_failure(context: dict[str, Any]) -> None:
    """白名单外数据源标记 → BusinessRuleViolationError(207) 安全失败。"""
    pass


@when(parsers.parse('沙箱代码引用白名单外数据源 "{source}"'))
def when_run_whitelist_out_marker(context: dict[str, Any], source: str) -> None:
    """生成仅含白名单外数据源标记的沙箱代码并驱动 Engine 执行。"""
    _run_engine(context, _code_with_markers((source,)))


@then("抛出 BusinessRuleViolationError")
def then_raise_business_rule_violation(context: dict[str, Any]) -> None:
    """断言捕获的异常为 BusinessRuleViolationError。"""
    assert isinstance(context["query_error"], BusinessRuleViolationError), (
        f"期望 BusinessRuleViolationError，实际: {context['query_error']!r}"
    )


@then(parsers.parse("错误码为 EXCEPTION_{code:d}"))
def then_error_code(context: dict[str, Any], code: int) -> None:
    """断言领域异常编码与消息（error.code + error.message 非空）。"""
    error = context["query_error"]
    assert error is not None, "未捕获到异常"
    expected = f"EXCEPTION_{code}"
    assert error.code == expected, f"期望错误码 {expected}，实际 {error.code}"
    assert error.message, "异常消息不能为空"


@scenario(FEATURE, "数据源不可用部分失败收敛")
def test_source_unavailable_partial_convergence(context: dict[str, Any]) -> None:
    """单源不可用 → 其余源正常注入 + DataSourceFetchFailed 事件。"""
    pass


@given(parsers.parse('数据源 "{source}" 配置为不可用，其余声明源行为正常'))
def given_source_unavailable(context: dict[str, Any], source: str) -> None:
    """将指定数据源适配器配置为不可用行为（模拟 5xx）。"""
    _make_adapters(context, behavior_by_source={source: "unavailable"})


@then("可用数据源数据已注入")
def then_available_sources_injected(context: dict[str, Any]) -> None:
    """部分失败收敛：仅行为正常的源注入，失败源不出现且注入集合非空。"""
    assert context["query_error"] is None, f"部分失败应收敛不抛出，实际: {context['query_error']}"
    injected = _injected_data_sources(context)
    expected = {name for name in _declared_sources(context) if name in context["adapters"]}
    # 行为为 unavailable 的适配器采集失败，不应出现在注入集合中
    expected = {name for name in expected if context["adapters"][name].behavior == "ok"}
    assert set(injected.keys()) == expected
    assert injected, "可用数据源注入集合不能为空"


@then("已发布 DataSourceFetchFailed 事件")
def then_fetch_failed_event_published(context: dict[str, Any]) -> None:
    """失败事件携带 EXCEPTION_411 语义（源不可用与 Key 缺失未注册均为 411，4-1c R1-P1-1）。"""
    events = context["event_bus"].published_events
    assert any(isinstance(evt, DataSourceFetchFailed) and evt.error_code == "EXCEPTION_411" for evt in events), (
        "未发布 error_code=EXCEPTION_411 的 DataSourceFetchFailed 事件"
    )


@scenario(FEATURE, "Key 缺失未注册降级部分失败收敛")
def test_key_missing_unregistered_partial_convergence(context: dict[str, Any]) -> None:
    """Key 缺失未注册（411 语义）→ 其余源正常注入 + 失败事件。"""
    pass


@given(parsers.parse('数据源 "{source_a}" 与 "{source_b}" 未注册（模拟 API Key 缺失），其余声明源行为正常'))
def given_sources_unregistered(context: dict[str, Any], source_a: str, source_b: str) -> None:
    """将两个 Key 敏感源从适配器映射物理移除（模拟 API Key 缺失未注册）。"""
    _make_adapters(context, behavior_by_source={source_a: "unregistered", source_b: "unregistered"})


@scenario(FEATURE, "缓存命中二次执行不重复采集")
def test_cache_hit_second_run_no_refetch(context: dict[str, Any]) -> None:
    """同租户二次执行命中缓存：外部采集次数不增 + 新鲜度元数据完备。"""
    pass


@when("该技能全部声明数据源标记连续两次经 Engine Execute 阶段处理")
def when_run_all_declared_markers_twice(context: dict[str, Any]) -> None:
    """连续两次驱动 Engine 执行同标记代码，记录首轮计数与绝对守卫。"""
    code = _code_with_markers(_declared_sources(context))
    _run_engine(context, code)
    assert context["query_error"] is None, f"第一次执行失败: {context['query_error']}"
    context["first_result"] = context["tool_result"]
    context["first_call_counts"] = {name: adp.call_count for name, adp in context["adapters"].items()}
    # 首轮绝对计数守卫（4-1c R2-F1/GAP-1）：标记代码必须真实送达，防相对断言被 0==0 伪满足
    first_counts = context["first_call_counts"]
    assert first_counts and all(count >= 1 for count in first_counts.values()), (
        f"首轮零外部采集（标记代码未送达 Sandbox）: {first_counts}"
    )
    _run_engine(context, code)


@then("第二次执行外部采集次数不增加")
def then_second_run_no_new_fetch(context: dict[str, Any]) -> None:
    """缓存命中断言：二次执行每源采集计数与首轮相等（相对断言已有首轮守卫保护）。"""
    assert context["query_error"] is None, f"第二次执行失败: {context['query_error']}"
    for name, adapter in context["adapters"].items():
        assert adapter.call_count == context["first_call_counts"][name], f"数据源 {name} 缓存未命中：第二次执行产生新外部采集"


@then("输出元数据 freshness 评分在 0 到 1 之间")
def then_freshness_in_range(context: dict[str, Any]) -> None:
    """EvidencePackage.data_sources[].freshness_score ∈ [0, 1]。"""
    result = context["tool_result"]
    assert result is not None and result.evidence_package is not None
    for meta in result.evidence_package.data_sources:
        assert 0.0 <= meta.freshness_score <= 1.0


@scenario(FEATURE, "纯内部框架 Skill 空白名单安全失败")
def test_pure_internal_skill_empty_whitelist_safety_failure(context: dict[str, Any]) -> None:
    """纯内部框架 Skill（data_sources 空 tuple）含标记 → 207 安全失败。

    永久锚定（4-1e Task 1.4 改名，D8）：空白名单是纯内部框架型的永久设计态
    ——7 个纯内部框架 Skill 不声明任何外部数据源（一等不变量），
    锚 business-model-canvas 语义长期成立，无滚动迁移义务（23/23 全部成熟化，
    滚动锚点规则终点态）。
    """
    pass


@when("含数据源标记的沙箱代码经 Engine Execute 阶段处理")
def when_run_generic_marker(context: dict[str, Any]) -> None:
    """引用任一已注册源标记（空白名单下应安全失败 207）。"""
    _run_engine(context, _code_with_markers(("world-bank",)))


@scenario(FEATURE, "多源三角化全声明源覆盖")
def test_triangulation_full_coverage(context: dict[str, Any]) -> None:
    """≥3 源 Skill（competitor-analysis 六源）注入源数 ≥3 且全声明源覆盖。"""
    pass


@then("注入数据源数量大于等于 3")
def then_triangulation_source_count(context: dict[str, Any]) -> None:
    """三角化断言：注入源数 ≥3（D4 决策：全声明源并发覆盖）。"""
    assert context["query_error"] is None, f"执行失败: {context['query_error']}"
    injected = _injected_data_sources(context)
    assert len(injected) >= 3, f"三角化要求注入源数 >= 3，实际 {len(injected)}"
