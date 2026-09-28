"""Story 4.1c — Skills 数据采集集成验收测试（BDD 步骤实现）

6 个外部数据型 Skills（pestel-analysis / porters-five-forces / appeals-analysis /
competitor-analysis / scenario-planning / disruptive-innovation）复用 Story 4.1b
数据采集基础设施的端到端验收。

遵循项目验收测试规范（范本 test_acceptance_data_source.py，Story 4.1b）：
- 步骤函数使用 @given / @when / @then 装饰器 + context: dict[str, Any] fixture
- 真实服务优先：真实 InMemorySkillLoader（加载真实 SKILL.md）+ 真实
  DataSourceResolverService + 真实 Redis（RedisAdapter）+ 真实 ToolExecutionEngine
- Mock 仅限端口适配器：外部数据源（_FakeDataSourceAdapter 测试替身）、LLM 客户端、沙箱
- 步骤严格按 feature 场景编号顺序排列（场景 1 → 场景 8）
- 异常处理：try/except 捕获到 context["query_error"]，Then 步骤断言 isinstance + error.code
- Redis 不可用时通过 pytest.skip() 动态跳过（禁止写死 @pytest.mark.skip）
- BDD 步骤函数**禁止** @pytest.mark.asyncio，使用 _run_async helper（场景级共享 event_loop）

红阶段说明（Task 0.6）：6 个目标 SKILL.md 的 frontmatter `data_sources` 尚未填写，
load_sop 解析出的 ToolMetadata.data_sources 为空 tuple，白名单校验抛
BusinessRuleViolationError(207) —— Happy Path 场景预期失败（红），
Task 2-7 填充声明后转绿。
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
from pytest_bdd import given, parsers, scenarios, then, when

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

scenarios("test_acceptance_skill_data_collection.feature")

# 全部场景归入 data-source-cache 组: 与共享缓存键的测试在同一 worker 串行执行
pytestmark = pytest.mark.xdist_group("data-source-cache")


# =============================================================================
# 数据契约 SSOT（与 Story 「6 个 Skills 数据源白名单声明表」逐字一致）
# =============================================================================

SKILL_DATA_SOURCES: dict[str, tuple[str, ...]] = {
    "pestel-analysis": ("world-bank", "imf", "eurostat", "ipcc", "newsapi", "china-nbs"),
    "porters-five-forces": ("newsapi", "world-bank", "eurostat"),
    "appeals-analysis": ("tavily", "newsapi", "china-nbs"),
    "competitor-analysis": ("newsapi", "uspto", "tavily", "china-nbs"),
    "scenario-planning": ("tavily", "ipcc", "eurostat"),
    "disruptive-innovation": ("uspto", "tavily"),
}


def _run_async(event_loop: Any, coro: Any) -> Any:
    """同步调度异步协程（BDD 步骤函数禁止 @pytest.mark.asyncio）。

    使用场景级共享事件循环（pytest-asyncio function-scope fixture）：
    aioredis/asyncio.Lock 等对象在首次使用时绑定事件循环，
    每次新建循环会导致 "Event loop is closed" 跨循环错误。
    """
    return event_loop.run_until_complete(coro)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def context(
    event_loop: Any,
    acceptance_env_config: Any,
) -> Generator[dict[str, Any], None, None]:
    """BDD 步骤间共享状态容器（场景级 UUID 租户 + 场景级共享事件循环 + 场景级独立 Redis 客户端）

    Redis 客户端必须场景级独立创建（不用 session 级共享 fixture）：session 客户端的
    连接池持有前一场景已关闭事件循环的连接，跨场景复用会抛 RuntimeError
    "Event loop is closed"（探针实测复现）。场景级创建 + 同循环 teardown 关闭
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


# =============================================================================
# 测试替身（Mock 仅限外部数据源端口适配器）
# =============================================================================


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


# =============================================================================
# 辅助函数
# =============================================================================


def _declared_sources(context: dict[str, Any]) -> tuple[str, ...]:
    """当前场景技能的声明源集合（SSOT 表，用于构造标记代码与适配器）。"""
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
            # 前言为 repr Python 字面量（R2-P0-1 修复：json.dumps → repr，ast.literal_eval 可逆）
            injected: dict[str, Any] = ast.literal_eval(first_line.removeprefix("DATA_SOURCES = "))
            return injected
    raise AssertionError(f"缺少 DATA_SOURCES 数据前言: {codes[-1].splitlines()[0][:80]}")


# =============================================================================
# 背景 Background Steps
# =============================================================================


@given("数据采集基础设施已初始化（真实 DataSourceResolverService + 可编程数据源适配器 + 真实缓存 + InMemoryEventBus）")
def given_infra_initialized(context: dict[str, Any]) -> None:
    """初始化真实缓存与事件总线（优雅降级：Redis ping 失败仅标记，执行入口二次实证 skip）。

    范本 test_acceptance_data_source.py Round 3 根因修复：session-scope Redis 客户端
    与 function-scope event_loop 存在跨循环绑定问题，单次 ping 结果不可靠，
    Redis 可用性以 _assert_redis_available 执行时实证为准。
    """
    context["event_bus"] = InMemoryEventBus()
    try:
        _run_async(context["_loop"], context["_redis_client"].ping())
        context["cache"] = RedisAdapter(redis_client=context["_redis_client"])
    except Exception:
        context["cache"] = None


def _assert_redis_available(context: dict[str, Any]) -> None:
    """Redis 不可用时显式 pytest.skip（每次实证 ping + lazy 重建 cache，防跨循环误判）。"""
    client = context.get("_redis_client")
    if client is None:
        pytest.skip("Redis 客户端未初始化")
    try:
        _run_async(context["_loop"], client.ping())
    except Exception as exc:
        pytest.skip(f"Redis 不可用: {exc}")
    if context.get("cache") is None:
        context["cache"] = RedisAdapter(redis_client=client)


# =============================================================================
# Given Steps（技能元数据加载 + 适配器行为编排）
# =============================================================================


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
    _make_adapters(context)


@given(parsers.parse('数据源 "{source}" 配置为不可用，其余声明源行为正常'))
def given_source_unavailable(context: dict[str, Any], source: str) -> None:
    _make_adapters(context, behavior_by_source={source: "unavailable"})


@given(parsers.parse('数据源 "{source_a}" 与 "{source_b}" 未注册（模拟 API Key 缺失），其余声明源行为正常'))
def given_sources_unregistered(context: dict[str, Any], source_a: str, source_b: str) -> None:
    _make_adapters(context, behavior_by_source={source_a: "unregistered", source_b: "unregistered"})


# =============================================================================
# When Steps（Engine 执行驱动）
# =============================================================================


@when("该技能全部声明数据源标记经 Engine Execute 阶段处理")
def when_run_all_declared_markers(context: dict[str, Any]) -> None:
    _run_engine(context, _code_with_markers(_declared_sources(context)))


@when("该技能全部声明数据源标记连续两次经 Engine Execute 阶段处理")
def when_run_all_declared_markers_twice(context: dict[str, Any]) -> None:
    code = _code_with_markers(_declared_sources(context))
    _run_engine(context, code)
    assert context["query_error"] is None, f"第一次执行失败: {context['query_error']}"
    context["first_result"] = context["tool_result"]
    context["first_call_counts"] = {name: adp.call_count for name, adp in context["adapters"].items()}
    _run_engine(context, code)


@when(parsers.parse('沙箱代码引用白名单外数据源 "{source}"'))
def when_run_whitelist_out_marker(context: dict[str, Any], source: str) -> None:
    _run_engine(context, _code_with_markers((source,)))


@when("含数据源标记的沙箱代码经 Engine Execute 阶段处理")
def when_run_generic_marker(context: dict[str, Any]) -> None:
    # 未成熟化 Skill 场景：引用任一已注册源标记（白名单为空时应安全失败 207）
    _run_engine(context, _code_with_markers(("world-bank",)))


# =============================================================================
# Then Steps（断言）
# =============================================================================


@then("每个声明数据源恰好采集 1 次")
def then_each_source_fetched_once(context: dict[str, Any]) -> None:
    assert context["query_error"] is None, f"执行失败: {context['query_error']}"
    assert context["tool_result"].status == ToolResultStatus.SUCCESS
    for name in _declared_sources(context):
        assert context["adapters"][name].call_count == 1, f"数据源 {name} 采集次数 != 1"


@then("注入 DATA_SOURCES 字典键集合等于声明数据源集合")
def then_injected_keys_match_declared(context: dict[str, Any]) -> None:
    injected = _injected_data_sources(context)
    assert set(injected.keys()) == set(_declared_sources(context))


@then("输出元数据含 source 与 freshness 与 confidence")
def then_evidence_metadata_complete(context: dict[str, Any]) -> None:
    result = context["tool_result"]
    assert result is not None and result.evidence_package is not None
    metas = result.evidence_package.data_sources
    assert len(metas) == len(_declared_sources(context))
    for meta in metas:
        assert meta.source_name in _declared_sources(context)
        assert 0.0 <= meta.freshness_score <= 1.0
        assert 0.0 <= meta.confidence <= 1.0


@then("抛出 BusinessRuleViolationError")
def then_raise_business_rule_violation(context: dict[str, Any]) -> None:
    assert isinstance(context["query_error"], BusinessRuleViolationError), (
        f"期望 BusinessRuleViolationError，实际: {context['query_error']!r}"
    )


@then(parsers.parse("错误码为 EXCEPTION_{code:d}"))
def then_error_code(context: dict[str, Any], code: int) -> None:
    error = context["query_error"]
    assert error is not None, "未捕获到异常"
    expected = f"EXCEPTION_{code}"
    assert error.code == expected, f"期望错误码 {expected}，实际 {error.code}"
    assert error.message, "异常消息不能为空"


@then("可用数据源数据已注入")
def then_available_sources_injected(context: dict[str, Any]) -> None:
    assert context["query_error"] is None, f"部分失败应收敛不抛出，实际: {context['query_error']}"
    injected = _injected_data_sources(context)
    expected = {name for name in _declared_sources(context) if name in context["adapters"]}
    # 行为为 unavailable 的适配器采集失败，不应出现在注入集合中
    expected = {name for name in expected if context["adapters"][name].behavior == "ok"}
    assert set(injected.keys()) == expected
    assert injected, "可用数据源注入集合不能为空"


@then("已发布 DataSourceFetchFailed 事件")
def then_fetch_failed_event_published(context: dict[str, Any]) -> None:
    events = context["event_bus"].published_events
    # 场景 4（源不可用）与场景 5（Key 缺失未注册）失败语义均为 411（R1-P1-1）
    assert any(isinstance(evt, DataSourceFetchFailed) and evt.error_code == "EXCEPTION_411" for evt in events), (
        "未发布 error_code=EXCEPTION_411 的 DataSourceFetchFailed 事件"
    )


@then("第二次执行外部采集次数不增加")
def then_second_run_no_new_fetch(context: dict[str, Any]) -> None:
    assert context["query_error"] is None, f"第二次执行失败: {context['query_error']}"
    for name, adapter in context["adapters"].items():
        assert adapter.call_count == context["first_call_counts"][name], f"数据源 {name} 缓存未命中：第二次执行产生新外部采集"


@then("输出元数据 freshness 评分在 0 到 1 之间")
def then_freshness_in_range(context: dict[str, Any]) -> None:
    result = context["tool_result"]
    assert result is not None and result.evidence_package is not None
    for meta in result.evidence_package.data_sources:
        assert 0.0 <= meta.freshness_score <= 1.0


@then("注入数据源数量大于等于 3")
def then_triangulation_source_count(context: dict[str, Any]) -> None:
    assert context["query_error"] is None, f"执行失败: {context['query_error']}"
    injected = _injected_data_sources(context)
    assert len(injected) >= 3, f"三角化要求注入源数 >= 3，实际 {len(injected)}"
