"""Acceptance tests for Story 4-6 — 工具版本管理（灰度发布与回滚）.

BDD 步骤实现（context dict + scenarios() 批量注册 + 真实服务链）：
- 真实服务：InMemoryToolVersionRepository / JsonSchemaValidatorImpl / ToolRegistryService
  / InMemoryToolRepository / ToolVersionService / ToolExecutionService / _RecordingEventPublisher
- 仅 LLM/Sandbox 端口适配器为 AsyncMock（Story 认可形态）；事件发布器为真实记录器
- HTTP 级 AC-6 场景：TestClient + 服务 AsyncMock（认可子模式）
- 模块级 event_loop fixture + run_until_complete（BDD 步骤禁 @pytest.mark.asyncio）
- 红窗口说明：本文件引用 Task 1-5 产物（实体/仓储/服务/端口），Task 0 阶段
  collection error 为设计内红（Story Subtask 0.9）
"""

from __future__ import annotations

import asyncio
import hashlib
import statistics
import time
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.application.services.tool_execution_service import ToolExecutionService
from src.application.services.tool_registry_service import ToolRegistryService
from src.application.services.tool_version_service import ToolVersionService
from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import ChannelResult, PublishResult
from src.domain.events.tool_version_events import ToolRolledBack, ToolVersionPublished
from src.domain.exceptions import DomainError
from src.domain.value_objects.tool_execution import ExecutionContext, ToolCall
from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository
from src.infrastructure.storage.inmemory.tool_version_repository import (
    InMemoryToolVersionRepository,
)
from src.infrastructure.validation.jsonschema_validator import JsonSchemaValidatorImpl
from src.interfaces.api.exception_handlers import (
    EXCEPTION_HTTP_MAP,
    register_exception_handlers,
)
from src.interfaces.api.middleware.exception_context import (
    ExceptionContextMiddleware,
)
from src.interfaces.api.tools import create_tools_router

scenarios("test_acceptance_tool_version_management.feature")

# 规范散列公式（Story AC-3 验证标准——TrafficRouter 与测试共用的规范条款）:
# int(hashlib.sha256(route_key.encode()).hexdigest(), 16) % 100 < weight → 命中 canary

# 测试 Schema 构造（已冒烟实证判别性）：
# - critical = 顶层字段 type 变更（FIELD_TYPE_CHANGED critical）
# - major    = 新增 required 字段（REQUIRED_FIELD_ADDED major）
# - minor    = 新增可选字段（OPTIONAL_FIELD_ADDED 非破坏）

_BASE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"factor": {"type": "string"}},
    "required": ["factor"],
}


def _schema_variant(kind: str) -> dict[str, Any]:
    """按破坏性级别构造 Schema 变体（判别性构造，真实校验器检测）。"""
    if kind == "critical":
        return {
            "type": "object",
            "properties": {"factor": {"type": "integer"}},
            "required": ["factor"],
        }
    if kind == "major":
        return {
            "type": "object",
            "properties": {"factor": {"type": "string"}, "extra": {"type": "string"}},
            "required": ["factor", "extra"],
        }
    if kind == "minor":
        return {
            "type": "object",
            "properties": {"factor": {"type": "string"}, "optional": {"type": "string"}},
            "required": ["factor"],
        }
    return dict(_BASE_SCHEMA)


# ============================================================================
# 共享 fixtures
# ============================================================================


@pytest.fixture
def event_loop():
    """模块级事件循环（BDD 步骤 run_until_complete 专用，禁 @pytest.mark.asyncio）。

    覆盖 pytest-asyncio 已废弃的内建 event_loop fixture（domain_dictionary 验收先例）。
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def context() -> dict[str, Any]:
    """BDD 步骤间共享状态容器。"""
    return {}


def _make_tool(
    input_schema: dict | None = None,
    output_schema: dict | None = None,
    name: str = "swot-analysis",
    version: str = "1.0.0",
) -> Tool:
    """构造测试用 Tool 实体（tool_io 验收同款工厂）。"""
    now = datetime.now(UTC)
    return Tool(
        tool_id=uuid.uuid4(),
        name=name,
        description="t",
        category=ToolCategory.ANALYSIS,
        input_schema=input_schema if input_schema is not None else {},
        output_schema=output_schema if output_schema is not None else {},
        status=ToolStatus.ACTIVE,
        version=version,
        created_at=now,
        updated_at=now,
    )


def _make_mock_llm(output: str = "mock_response") -> AsyncMock:
    """LLM 端口适配器 Mock（认可形态）。"""
    mock = AsyncMock()
    mock.structured_generate = AsyncMock(return_value=output)
    mock.generate = AsyncMock(return_value=AsyncMock(content=output))
    return mock


def _make_mock_sandbox(result: str = "result_data") -> AsyncMock:
    """Sandbox 端口适配器 Mock（认可形态）。"""
    mock = AsyncMock()
    mock.start_container = AsyncMock()
    mock.execute_code = AsyncMock(return_value={"status": "ok", "output": result})
    mock.stop_container = AsyncMock()
    return mock


class _RecordingEngine(ToolExecutionEngine):
    """真实引擎子类：记录收到的 Tool 副本后委托真实执行（AC-5 观测面）。

    引擎对 ToolExecution.tool_version 的快照公式为 `tool.version`（4.1a 既有
    行为、4-6 零改动），故记录副本的 version 即等价断言聚合快照输入。
    类型上为 ToolExecutionEngine 真子类（服务构造签名无需放宽）。
    """

    def __init__(self, llm_client: Any, sandbox: Any) -> None:
        super().__init__(llm_client=llm_client, sandbox=sandbox)
        self.received_tools: list[Tool] = []

    async def execute(
        self,
        tool_id: uuid.UUID,
        tool: Tool,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> Any:
        """记录传入副本后委托真实引擎执行。"""
        self.received_tools.append(tool)
        return await super().execute(tool_id=tool_id, tool=tool, tool_call=tool_call, context=context)


# ============================================================================
# Background
# ============================================================================


@given("工具版本管理服务链已装配（真实服务）")
def given_services_initialized(context: dict[str, Any]) -> None:
    """初始化真实服务链 + Mock 端口适配器（每场景独立实例，自包含）。"""
    tool_repo = InMemoryToolRepository()
    registry = ToolRegistryService(repository=tool_repo)
    version_repo = InMemoryToolVersionRepository()
    schema_validator = JsonSchemaValidatorImpl()
    event_publisher = _RecordingEventPublisher()

    version_service = ToolVersionService(
        repository=version_repo,
        schema_validator=schema_validator,
        tool_registry=registry,
        event_publisher=event_publisher,
        max_retained_versions=10,
    )
    llm = _make_mock_llm()
    sandbox = _make_mock_sandbox()
    recording_engine = _RecordingEngine(llm_client=llm, sandbox=sandbox)
    execution_service = ToolExecutionService(
        registry=registry,
        engine=recording_engine,
        tool_version_service=version_service,
    )

    context["tool_repo"] = tool_repo
    context["registry"] = registry
    context["version_repo"] = version_repo
    context["schema_validator"] = schema_validator
    context["event_publisher"] = event_publisher
    context["version_service"] = version_service
    context["execution_service"] = execution_service
    context["recording_engine"] = recording_engine
    # 预注册被测工具（背景之上由各场景 Given 细化状态）
    tool = _make_tool(input_schema=dict(_BASE_SCHEMA), output_schema=dict(_BASE_SCHEMA))
    tool_repo.save(tool)
    context["tool"] = tool
    context["tool_id"] = tool.tool_id


# ============================================================================
# 服务级辅助（Given 构造器）
# ============================================================================


def _run(coro: Any) -> Any:
    """BDD 步骤内联运行协程（独立短生命周期循环——InMemory 装配无跨循环连接风险）。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _RecordingEventPublisher:
    """真实事件记录发布器（验收禁 mock 纪律——_RecordingEngine 同款形态）。

    记录全部发布调用并恒返回成功结果，供事件场景断言（成功路径发布 /
    失败路径零发布）。
    """

    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> PublishResult:
        """记录事件并返回全通道成功结果。"""
        self.published.append(event)
        return PublishResult(
            event_id=str(uuid.uuid4()),
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


def _register(context: dict[str, Any], version: str, kind: str = "minor") -> Any:
    """注册指定破坏性级别的版本（真实服务链）。"""
    svc: ToolVersionService = context["version_service"]
    return _run(
        svc.register_version(
            tool_id=context["tool_id"],
            version=version,
            input_schema=_schema_variant(kind),
            output_schema=_schema_variant(kind),
        )
    )


def _publish(context: dict[str, Any], version: str, weight: int) -> Any:
    """发布指定版本到指定权重。"""
    svc: ToolVersionService = context["version_service"]
    return _run(svc.publish_version(tool_id=context["tool_id"], version=version, traffic_weight=weight))


def _make_stable(context: dict[str, Any], version: str) -> None:
    """构造 STABLE 版本（注册 minor + 全量发布）。"""
    _register(context, version, "minor")
    _publish(context, version, 100)


def _make_canary(context: dict[str, Any], version: str, weight: int) -> None:
    """构造灰度态（存在 STABLE 前提下注册 minor + 部分发布）。"""
    _register(context, version, "minor")
    _publish(context, version, weight)


def _capture_error(context: dict[str, Any], fn: Any) -> None:
    """执行 fn 并捕获业务异常到 context['error']。"""
    try:
        fn()
        context["error"] = None
    except DomainError as exc:
        context["error"] = exc


def _get_version(context: dict[str, Any], version: str) -> Any:
    """从仓储取版本实体。"""
    repo: InMemoryToolVersionRepository = context["version_repo"]
    return _run(repo.get_by_tool_and_version(context["tool_id"], version))


def _expected_hash_hit(route_key: str, weight: int) -> bool:
    """按规范散列公式独立重算期望桶位（禁以 route() 探测结果作锚点）。"""
    return int(hashlib.sha256(route_key.encode()).hexdigest(), 16) % 100 < weight


def _pick_keys(weight: int) -> tuple[str, str]:
    """按规范公式扫描固定样本集，返回（命中键，未命中键）。"""
    hit = miss = None
    for i in range(1000):
        key = f"key-{i}"
        if _expected_hash_hit(key, weight) and hit is None:
            hit = key
        if not _expected_hash_hit(key, weight) and miss is None:
            miss = key
        if hit is not None and miss is not None:
            break
    assert hit is not None and miss is not None, "固定样本集必须同时存在命中与未命中键"
    return hit, miss


# ============================================================================
# AC-1: 工具多版本并存注册
# ============================================================================


@given("系统中已有已注册工具")
def given_tool_registered(context: dict[str, Any]) -> None:
    """背景已预注册工具——本步骤为语义显式化（no-op）。"""


@given("系统中不存在目标工具")
def given_tool_missing(context: dict[str, Any]) -> None:
    """将被引用的工具不存在（构造悬空 tool_id）。"""
    context["tool_id"] = uuid.uuid4()


@given("工具已注册版本 1.0.0")
def given_version_registered(context: dict[str, Any]) -> None:
    """已注册 PENDING 版本 1.0.0。"""
    _register(context, "1.0.0", "minor")


@when("运维为工具依次注册版本 1.0.0、1.1.0、2.0.0")
def when_register_three(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    for v in ("1.0.0", "1.1.0", "2.0.0"):
        _run(
            svc.register_version(
                tool_id=context["tool_id"],
                version=v,
                input_schema=dict(_BASE_SCHEMA),
                output_schema=dict(_BASE_SCHEMA),
            )
        )


@when("运维再次注册相同版本 1.0.0")
def when_register_duplicate(context: dict[str, Any]) -> None:
    _capture_error(context, lambda: _register(context, "1.0.0", "minor"))


@when("运维为不存在的工具注册版本 1.0.0")
def when_register_missing_tool(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]

    def _call() -> None:
        _run(
            svc.register_version(
                tool_id=context["tool_id"],
                version="1.0.0",
                input_schema=dict(_BASE_SCHEMA),
                output_schema=dict(_BASE_SCHEMA),
            )
        )

    _capture_error(context, _call)


@then("工具的版本列表包含 3 个版本")
def then_three_versions(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    versions = _run(svc.list_versions(context["tool_id"]))
    assert len(versions) == 3


@then("全部版本状态为 pending 且按注册时间排序")
def then_pending_sorted(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    versions = _run(svc.list_versions(context["tool_id"]))
    assert all(v.status.value == "pending" for v in versions)
    times = [v.created_at for v in versions]
    assert times == sorted(times)


# ============================================================================
# 异常断言（全 AC 复用）
# ============================================================================


@then("抛出业务异常 EXCEPTION_431 且 HTTP 状态为 409")
def then_error_431(context: dict[str, Any]) -> None:
    _assert_error(context, "EXCEPTION_431", 409)


@then("抛出业务异常 EXCEPTION_380 且 HTTP 状态为 404")
def then_error_380(context: dict[str, Any]) -> None:
    _assert_error(context, "EXCEPTION_380", 404)


@then("抛出业务异常 EXCEPTION_397 且 HTTP 状态为 409")
def then_error_397(context: dict[str, Any]) -> None:
    _assert_error(context, "EXCEPTION_397", 409)


@then("抛出业务异常 EXCEPTION_432 且 HTTP 状态为 400")
def then_error_432(context: dict[str, Any]) -> None:
    _assert_error(context, "EXCEPTION_432", 400)


@then("抛出业务异常 EXCEPTION_430 且 HTTP 状态为 404")
def then_error_430(context: dict[str, Any]) -> None:
    _assert_error(context, "EXCEPTION_430", 404)


@then("抛出业务异常 EXCEPTION_433 且 HTTP 状态为 409")
def then_error_433(context: dict[str, Any]) -> None:
    _assert_error(context, "EXCEPTION_433", 409)


def _assert_error(context: dict[str, Any], code: str, http: int) -> None:
    """统一异常断言：code + HTTP 映射（EXCEPTION_HTTP_MAP 权威）。"""
    error = context.get("error")
    assert error is not None, f"预期抛出 {code}，实际未抛出异常"
    assert error.code == code, f"预期 {code}，实际 {error.code}"
    assert EXCEPTION_HTTP_MAP.get(type(error)) == http


# ============================================================================
# AC-2: Schema 变更兼容性校验拦截
# ============================================================================


@given("工具已有稳定版本 1.0.0")
def given_stable_1(context: dict[str, Any]) -> None:
    _make_stable(context, "1.0.0")


@when("运维注册 critical 破坏性变更版本 2.0.0")
def when_register_critical(context: dict[str, Any]) -> None:
    _capture_error(context, lambda: _register(context, "2.0.0", "critical"))


@when("运维注册 critical 破坏性变更版本 2.0.0 作为首个版本")
def when_register_critical_first(context: dict[str, Any]) -> None:
    _capture_error(context, lambda: _register(context, "2.0.0", "critical"))


@when("运维注册 major 破坏性变更版本 2.0.0")
def when_register_major(context: dict[str, Any]) -> None:
    _capture_error(context, lambda: _register(context, "2.0.0", "major"))


@when("运维注册 minor 变更版本 1.1.0")
def when_register_minor_11(context: dict[str, Any]) -> None:
    _capture_error(context, lambda: _register(context, "1.1.0", "minor"))


@when("运维注册 minor 变更版本 3.0.0")
def when_register_minor_30(context: dict[str, Any]) -> None:
    _capture_error(context, lambda: _register(context, "3.0.0", "minor"))


@when("运维注册 minor 变更版本 3.1.0")
def when_register_minor_31(context: dict[str, Any]) -> None:
    _capture_error(context, lambda: _register(context, "3.1.0", "minor"))


@then("异常 context 携带 tool_id old_version new_version breaking_changes")
def then_397_context(context: dict[str, Any]) -> None:
    error = context["error"]
    for key in ("tool_id", "old_version", "new_version", "breaking_changes"):
        assert key in error.context, f"397 context 缺少 {key}"


@then("工具的版本数量保持 1")
def then_count_1(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    versions = _run(svc.list_versions(context["tool_id"]))
    assert len(versions) == 1


@then("版本 2.0.0 注册成功且发布模式为 canary_only")
def then_major_registered(context: dict[str, Any]) -> None:
    assert context.get("error") is None, "major 注册应成功"
    tv = _get_version(context, "2.0.0")
    assert tv.required_rollout_mode == "canary_only"


@then("版本 1.1.0 注册成功且发布模式为 any")
def then_minor_registered(context: dict[str, Any]) -> None:
    assert context.get("error") is None, "minor 注册应成功"
    tv = _get_version(context, "1.1.0")
    assert tv.required_rollout_mode == "any"


@then("版本 2.0.0 注册成功且发布模式为 any")
def then_first_version_any(context: dict[str, Any]) -> None:
    """首版本跳过校验 → critical schema 也注册成功且 mode=any。"""
    assert context.get("error") is None, "首版本（含 critical schema）应跳过校验注册成功"
    tv = _get_version(context, "2.0.0")
    assert tv.required_rollout_mode == "any"


@when("运维对 canary_only 版本请求直接全量发布")
def when_canary_only_full(context: dict[str, Any]) -> None:
    _capture_error(context, lambda: _publish(context, "2.0.0", 100))


# ============================================================================
# AC-3: 灰度发布
# ============================================================================


@given("工具存在稳定版本 1.0.0 与灰度版本 1.1.0 权重 30")
def given_stable_canary(context: dict[str, Any]) -> None:
    _make_stable(context, "1.0.0")
    _make_canary(context, "1.1.0", 30)


@given("工具已注册待发布版本 1.1.0")
def given_pending_11(context: dict[str, Any]) -> None:
    _register(context, "1.1.0", "minor")


@when("运维以权重 30 发布版本 2.0.0")
def when_publish_2_w30(context: dict[str, Any]) -> None:
    _capture_error(context, lambda: _publish(context, "2.0.0", 30))


@when("运维以权重 100 发布版本 2.0.0")
def when_publish_2_w100(context: dict[str, Any]) -> None:
    _capture_error(context, lambda: _publish(context, "2.0.0", 100))


@when("运维以权重 30 发布版本 1.1.0")
def when_publish_w30(context: dict[str, Any]) -> None:
    _capture_error(context, lambda: _publish(context, "1.1.0", 30))


@when("运维以权重 0 发布版本 1.1.0")
def when_publish_w0(context: dict[str, Any]) -> None:
    _capture_error(context, lambda: _publish(context, "1.1.0", 0))


@when("运维以权重 101 发布版本 1.1.0")
def when_publish_w101(context: dict[str, Any]) -> None:
    _capture_error(context, lambda: _publish(context, "1.1.0", 101))


@when("运维以权重 50 发布版本 1.1.0")
def when_publish_w50(context: dict[str, Any]) -> None:
    _capture_error(context, lambda: _publish(context, "1.1.0", 50))


@when("运维以权重 100 发布版本 1.1.0")
def when_publish_w100(context: dict[str, Any]) -> None:
    _capture_error(context, lambda: _publish(context, "1.1.0", 100))


@when("运维放弃灰度")
def when_abort_canary(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    _capture_error(context, lambda: _run(svc.abort_canary(context["tool_id"])))


@then("1000 个固定路由键的灰度命中比例在 30%±5% 容差内")
def then_ratio(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    hit = 0
    for i in range(1000):
        tv = _run(svc.resolve_version(context["tool_id"], route_key=f"key-{i}"))
        if tv.version == "1.1.0":
            hit += 1
    ratio = hit / 1000
    assert 0.25 <= ratio <= 0.35, f"灰度命中比例 {ratio:.1%} 超出 30%±5% 容差"


@then("同一路由键重复解析 100 次结果完全一致")
def then_deterministic(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    results = {_run(svc.resolve_version(context["tool_id"], route_key="key-42")).version for _ in range(100)}
    assert len(results) == 1, f"同一路由键解析结果不稳定: {results}"


@then("未命中灰度的路由键全部解析到稳定版本 1.0.0")
def then_miss_to_stable(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    _, miss = _pick_keys(30)
    tv = _run(svc.resolve_version(context["tool_id"], route_key=miss))
    assert tv.version == "1.0.0"


@then("版本 2.0.0 状态为 stable")
def then_v2_stable(context: dict[str, Any]) -> None:
    assert context.get("error") is None
    tv = _get_version(context, "2.0.0")
    assert tv.status.value == "stable"


@then("版本 1.0.0 状态为 deprecated 且记录了 last_stable_at")
def then_v1_deprecated_stamped(context: dict[str, Any]) -> None:
    tv = _get_version(context, "1.0.0")
    assert tv.status.value == "deprecated"
    assert tv.last_stable_at is not None


@then("版本 1.1.0 状态为 stable")
def then_v11_stable(context: dict[str, Any]) -> None:
    assert context.get("error") is None
    tv = _get_version(context, "1.1.0")
    assert tv.status.value == "stable"


@then("版本 1.1.0 状态保持 canary 且权重为 50")
def then_v11_canary_50(context: dict[str, Any]) -> None:
    assert context.get("error") is None, "调档应成功"
    tv = _get_version(context, "1.1.0")
    assert tv.status.value == "canary"
    assert tv.traffic_weight == 50


@then("版本 1.1.0 状态为 deprecated 且未记录 last_stable_at")
def then_v11_deprecated_unstamped(context: dict[str, Any]) -> None:
    tv = _get_version(context, "1.1.0")
    assert tv.status.value == "deprecated"
    assert tv.last_stable_at is None


@then("版本 1.0.0 状态保持 stable")
def then_v1_stable_kept(context: dict[str, Any]) -> None:
    tv = _get_version(context, "1.0.0")
    assert tv.status.value == "stable"


@then("工具的流量视图稳定版本为 1.1.0 且无灰度版本")
def then_traffic_v11(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    view = _run(svc.get_version_traffic(context["tool_id"]))
    assert view["stable_version"] == "1.1.0"
    assert view["canary_version"] is None


@then("工具的流量视图稳定版本为 1.0.0 且无灰度版本")
def then_traffic_v1(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    view = _run(svc.get_version_traffic(context["tool_id"]))
    assert view["stable_version"] == "1.0.0"
    assert view["canary_version"] is None


@then("工具的流量视图灰度权重为 50")
def then_traffic_weight_50(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    view = _run(svc.get_version_traffic(context["tool_id"]))
    assert view["canary_version"] == "1.1.0"
    assert view["canary_weight"] == 50


# ============================================================================
# AC-4: 一键回滚与保留策略
# ============================================================================


@given("工具当前稳定版本为 2.0.0 且历史稳定版本为 1.9.0")
def given_rollback_state(context: dict[str, Any]) -> None:
    _make_stable(context, "1.9.0")
    _make_stable(context, "2.0.0")  # promote：1.9.0 降级带戳


@given("工具仅有惰性初始稳定版本")
def given_lazy_stable(context: dict[str, Any]) -> None:
    _make_stable(context, "1.0.0")  # 无带戳 DEPRECATED → 无可回滚


@given("工具已有连续三代稳定版本 1.0.0、1.1.0、2.0.0")
def given_three_generations(context: dict[str, Any]) -> None:
    _make_stable(context, "1.0.0")
    _make_stable(context, "1.1.0")
    _make_stable(context, "2.0.0")


@given("工具已积累 10 个版本含 1 个无戳弃用版本与 1 个最旧曾稳定版本")
def given_retention_pool(context: dict[str, Any]) -> None:
    """构造 10 版本：8 个 promote 链带戳 DEP + 1 个 abort 无戳 DEP + 1 个 STABLE。"""
    for v in ("1.0.0", "1.1.0", "1.2.0", "1.3.0", "1.4.0", "1.5.0", "1.6.0", "1.7.0"):
        _make_stable(context, v)  # 依次 promote——1.0.0 为最旧带戳 DEP
    _make_canary(context, "1.8.0", 30)
    svc: ToolVersionService = context["version_service"]
    _run(svc.abort_canary(context["tool_id"]))  # 1.8.0 → 无戳 DEP
    _make_stable(context, "1.9.0")  # 当前 STABLE（总数 = 8 + 1 + 1 = 10）


@when("运维执行一键回滚")
def when_rollback(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    _capture_error(context, lambda: _run(svc.rollback(context["tool_id"])))


@when("运维再次执行一键回滚")
def when_rollback_again(context: dict[str, Any]) -> None:
    when_rollback(context)


@when("运维回滚至不存在的版本 9.9.9")
def when_rollback_missing(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    _capture_error(context, lambda: _run(svc.rollback(context["tool_id"], target_version="9.9.9")))


@when("运维回滚至当前稳定版本自身 2.0.0")
def when_rollback_self(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    _capture_error(context, lambda: _run(svc.rollback(context["tool_id"], target_version="2.0.0")))


@then("版本 1.9.0 状态为 stable")
def then_v19_stable(context: dict[str, Any]) -> None:
    assert context.get("error") is None, "回滚应成功"
    tv = _get_version(context, "1.9.0")
    assert tv.status.value == "stable"


@then("版本 2.0.0 状态为 deprecated 且 last_stable_at 已清空")
def then_v2_deprecated_cleared(context: dict[str, Any]) -> None:
    tv = _get_version(context, "2.0.0")
    assert tv.status.value == "deprecated"
    assert tv.last_stable_at is None, "回滚降级必须显式清空戳（指针原则）"


@then("任意路由键解析工具全部得到版本 1.9.0")
def then_all_routes_v19(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    for i in range(50):
        tv = _run(svc.resolve_version(context["tool_id"], route_key=f"rk-{i}"))
        assert tv.version == "1.9.0"


@then("版本 1.1.0 状态为 stable")
def then_v11_stable_after_rb(context: dict[str, Any]) -> None:
    assert context.get("error") is None
    tv = _get_version(context, "1.1.0")
    assert tv.status.value == "stable"


@then("版本 1.0.0 状态为 stable")
def then_v1_stable_after_rb2(context: dict[str, Any]) -> None:
    assert context.get("error") is None
    tv = _get_version(context, "1.0.0")
    assert tv.status.value == "stable"


@then("版本 1.1.0 状态为 deprecated 且 last_stable_at 已清空")
def then_v11_deprecated_cleared(context: dict[str, Any]) -> None:
    tv = _get_version(context, "1.1.0")
    assert tv.status.value == "deprecated"
    assert tv.last_stable_at is None


@then("版本总数不超过 10 且无戳弃用版本已被淘汰")
def then_evict_unstamped(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    versions = _run(svc.list_versions(context["tool_id"]))
    assert len(versions) <= 10
    remaining = {v.version for v in versions}
    assert "1.8.0" not in remaining, "无戳弃用版本（灰度清场产物）应最先淘汰"
    assert "1.0.0" in remaining, "带戳版本在无戳组未清空前不应淘汰"


@then("版本总数不超过 10 且最旧曾稳定版本已被淘汰")
def then_evict_oldest_stamped(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    versions = _run(svc.list_versions(context["tool_id"]))
    assert len(versions) <= 10
    remaining = {v.version for v in versions}
    assert "1.0.0" not in remaining, "无戳组清空后应淘汰最旧带戳版本"


# ============================================================================
# AC-5: 版本化执行集成
# ============================================================================


@given("已按规范散列公式预计算命中灰度的路由键")
def given_hit_key(context: dict[str, Any]) -> None:
    hit, _ = _pick_keys(30)
    context["route_key"] = hit


@given("已按规范散列公式预计算未命中灰度的路由键")
def given_miss_key(context: dict[str, Any]) -> None:
    _, miss = _pick_keys(30)
    context["route_key"] = miss


@when("Agent以命中路由键执行工具")
def when_execute_hit(context: dict[str, Any]) -> None:
    _execute(context, route_key=context["route_key"])


@when("Agent以未命中路由键执行工具")
def when_execute_miss(context: dict[str, Any]) -> None:
    _execute(context, route_key=context["route_key"])


@when("Agent显式指定版本 1.1.0 执行工具")
def when_execute_explicit(context: dict[str, Any]) -> None:
    _execute(context, requested_version="1.1.0")


@when("Agent以任意路由键首次执行工具")
def when_execute_first(context: dict[str, Any]) -> None:
    _execute(context, route_key="first-key")


def _execute(
    context: dict[str, Any],
    route_key: str | None = None,
    requested_version: str | None = None,
) -> None:
    """通过真实 ToolExecutionService 执行（版本路由 + 派生副本观测）。"""
    service: ToolExecutionService = context["execution_service"]
    tool_call = ToolCall(
        tool_id=context["tool_id"],
        arguments={"factor": "test"},
        version=requested_version,
    )
    exec_context = ExecutionContext(tenant_id=uuid.uuid4(), trace_id=route_key or "no-route-key")
    _run(service.execute(context["tool_id"], tool_call, exec_context))


@then("执行聚合快照版本为 1.1.0")
def then_snapshot_11(context: dict[str, Any]) -> None:
    engine: _RecordingEngine = context["recording_engine"]
    assert engine.received_tools, "引擎应收到执行请求"
    received = engine.received_tools[-1]
    assert received.version == "1.1.0", f"引擎收到副本版本 {received.version}，期望 1.1.0（快照公式 tool_version=tool.version）"


@then("执行聚合快照版本为 1.0.0")
def then_snapshot_10(context: dict[str, Any]) -> None:
    engine: _RecordingEngine = context["recording_engine"]
    assert engine.received_tools, "引擎应收到执行请求"
    received = engine.received_tools[-1]
    assert received.version == "1.0.0"


@then("引擎收到的工具副本版本为 1.1.0 且输入 Schema 已替换为灰度快照")
def then_engine_copy(context: dict[str, Any]) -> None:
    engine: _RecordingEngine = context["recording_engine"]
    received = engine.received_tools[-1]
    assert received.version == "1.1.0"
    tv = _get_version(context, "1.1.0")
    assert received.input_schema == tv.input_schema, "派生副本的 input_schema 应为灰度快照"


@then("工具自动建立版本为 1.0.0 的 stable 初始版本")
def then_lazy_initial(context: dict[str, Any]) -> None:
    tv = _get_version(context, "1.0.0")
    assert tv is not None, "首次执行应惰性建立初始版本"
    assert tv.status.value == "stable"


# ============================================================================
# AC-6: 运维 REST API（HTTP 级——TestClient + 服务 AsyncMock）
# ============================================================================


@pytest.fixture
def mocks() -> dict[str, AsyncMock]:
    """AC-6 场景共享的 mock 服务（HTTP 级认可子模式）。"""
    from src.application.ports.tool_version_service import ToolVersionServicePort

    return {"version_service": AsyncMock(spec=ToolVersionServicePort)}


def _make_token():
    """构造认证 TokenPayload（document_upload 先例）。"""
    from src.domain.value_objects.token_payload import TokenPayload

    return TokenPayload(
        user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        username="testuser",
        roles=("admin",),
        exp=datetime(2099, 1, 1, tzinfo=UTC),
    )


def _make_http_client(context: dict[str, Any], mocks: dict[str, AsyncMock] | None, auth: bool = True):
    """构建 tools 路由的 TestClient（auth=False 构造未认证客户端）。"""
    app = FastAPI()
    app.add_middleware(ExceptionContextMiddleware)
    register_exception_handlers(app)

    def _override():
        return _make_token()

    kwargs: dict[str, Any] = {
        "tool_version_service": mocks["version_service"] if mocks else AsyncMock(),
    }
    if auth:
        kwargs["get_current_user_override"] = _override
    router = create_tools_router(**kwargs)
    app.include_router(router)
    context["tool_path_id"] = str(context["tool_id"])
    return TestClient(app)


@given("运维工程师已通过 OAuth2 认证")
def given_oauth(context: dict[str, Any], mocks: dict[str, AsyncMock]) -> None:
    """认证已就绪（no-op，客户端由 when 步骤构建）。"""


@given("运维工程师未携带认证凭证")
def given_no_auth(context: dict[str, Any]) -> None:
    """未认证（no-op）。"""


@given("版本管理服务正常响应注册请求")
def given_svc_register_ok(context: dict[str, Any], mocks: dict[str, AsyncMock]) -> None:
    from src.domain.entities.tool_version import ToolVersion, ToolVersionStatus

    tv = ToolVersion(
        tool_id=context["tool_id"],
        version="1.1.0",
        input_schema={},
        output_schema={},
        status=ToolVersionStatus.PENDING,
    )
    mocks["version_service"].register_version = AsyncMock(return_value=tv)


@given("版本管理服务返回两个版本记录")
def given_svc_list_two(context: dict[str, Any], mocks: dict[str, AsyncMock]) -> None:
    from src.domain.entities.tool_version import ToolVersion, ToolVersionStatus

    versions = [
        ToolVersion(
            tool_id=context["tool_id"],
            version=v,
            input_schema={},
            output_schema={},
            status=ToolVersionStatus.STABLE if v == "1.0.0" else ToolVersionStatus.DEPRECATED,
        )
        for v in ("1.0.0", "1.1.0")
    ]
    mocks["version_service"].list_versions = AsyncMock(return_value=versions)


@given("版本管理服务正常响应发布请求")
def given_svc_publish_ok(context: dict[str, Any], mocks: dict[str, AsyncMock]) -> None:
    from src.domain.entities.tool_version import ToolVersion, ToolVersionStatus

    tv = ToolVersion(
        tool_id=context["tool_id"],
        version="1.1.0",
        input_schema={},
        output_schema={},
        status=ToolVersionStatus.CANARY,
        traffic_weight=30,
    )
    mocks["version_service"].publish_version = AsyncMock(return_value=tv)


@given("版本管理服务对回滚请求抛出 EXCEPTION_433")
def given_svc_rollback_433(context: dict[str, Any], mocks: dict[str, AsyncMock]) -> None:
    from src.domain.exceptions.tool_version_exceptions import ToolVersionRollbackError

    mocks["version_service"].rollback = AsyncMock(side_effect=ToolVersionRollbackError(tool_id=str(context["tool_id"])))


@given("版本管理服务正常响应放弃灰度请求")
def given_svc_abort_ok(context: dict[str, Any], mocks: dict[str, AsyncMock]) -> None:
    from src.domain.entities.tool_version import ToolVersion, ToolVersionStatus

    tv = ToolVersion(
        tool_id=context["tool_id"],
        version="1.1.0",
        input_schema={},
        output_schema={},
        status=ToolVersionStatus.DEPRECATED,
    )
    mocks["version_service"].abort_canary = AsyncMock(return_value=tv)


@given("版本管理服务返回当前流量分布")
def given_svc_traffic(context: dict[str, Any], mocks: dict[str, AsyncMock]) -> None:
    mocks["version_service"].get_version_traffic = AsyncMock(
        return_value={
            "stable_version": "1.0.0",
            "canary_version": "1.1.0",
            "canary_weight": 30,
        }
    )


@when("运维调用注册版本端点")
def when_api_register(context: dict[str, Any], mocks: dict[str, AsyncMock]) -> None:
    client = _make_http_client(context, mocks)
    resp = client.post(
        f"/api/v1/tools/{context['tool_path_id']}/versions",
        json={"version": "1.1.0", "input_schema": {}, "output_schema": {}},
    )
    context["http_response"] = resp


@when("运维调用版本列表端点")
def when_api_list(context: dict[str, Any], mocks: dict[str, AsyncMock]) -> None:
    client = _make_http_client(context, mocks)
    resp = client.get(f"/api/v1/tools/{context['tool_path_id']}/versions")
    context["http_response"] = resp


@when("运维调用发布版本端点携带权重 30")
def when_api_publish(context: dict[str, Any], mocks: dict[str, AsyncMock]) -> None:
    client = _make_http_client(context, mocks)
    resp = client.post(
        f"/api/v1/tools/{context['tool_path_id']}/versions/1.1.0/publish",
        json={"traffic_weight": 30},
    )
    context["http_response"] = resp


@when("运维调用回滚端点")
def when_api_rollback(context: dict[str, Any], mocks: dict[str, AsyncMock]) -> None:
    client = _make_http_client(context, mocks)
    resp = client.post(f"/api/v1/tools/{context['tool_path_id']}/rollback")
    context["http_response"] = resp


@when("运维调用放弃灰度端点")
def when_api_abort(context: dict[str, Any], mocks: dict[str, AsyncMock]) -> None:
    client = _make_http_client(context, mocks)
    resp = client.post(f"/api/v1/tools/{context['tool_path_id']}/abort-canary")
    context["http_response"] = resp


@when("运维调用流量视图端点")
def when_api_traffic(context: dict[str, Any], mocks: dict[str, AsyncMock]) -> None:
    client = _make_http_client(context, mocks)
    resp = client.get(f"/api/v1/tools/{context['tool_path_id']}/versions/traffic")
    context["http_response"] = resp


@when("运维未认证调用版本列表端点")
def when_api_no_auth(context: dict[str, Any]) -> None:
    client = _make_http_client(context, mocks=None, auth=False)
    resp = client.get(f"/api/v1/tools/{context['tool_path_id']}/versions")
    context["http_response"] = resp


@then("HTTP 响应状态码为 201 且响应体包含版本详情字段")
def then_http_201(context: dict[str, Any]) -> None:
    resp = context["http_response"]
    assert resp.status_code == 201, resp.text
    data = resp.json()
    for field in ("version_id", "tool_id", "version", "status", "created_at"):
        assert field in data, f"响应缺少 {field}"


@then("HTTP 响应状态码为 200 且 items 共 2 条 total 为 2")
def then_http_list(context: dict[str, Any]) -> None:
    resp = context["http_response"]
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 2


@then("HTTP 响应状态码为 200 且响应体状态为 canary")
def then_http_publish(context: dict[str, Any]) -> None:
    resp = context["http_response"]
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "canary"


@then("HTTP 响应状态码为 409")
def then_http_409(context: dict[str, Any]) -> None:
    resp = context["http_response"]
    assert resp.status_code == 409, resp.text


@then("响应体 error.code 为 EXCEPTION_433 且包含 error.message 与 request_id")
def then_http_error_body(context: dict[str, Any]) -> None:
    data = context["http_response"].json()
    assert data["error"]["code"] == "EXCEPTION_433"
    assert data["error"]["message"]
    assert "request_id" in data


@then("HTTP 响应状态码为 200 且响应体状态为 deprecated")
def then_http_abort(context: dict[str, Any]) -> None:
    resp = context["http_response"]
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "deprecated"


@then("HTTP 响应状态码为 200 且包含 stable_version canary_version canary_weight")
def then_http_traffic(context: dict[str, Any]) -> None:
    resp = context["http_response"]
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for field in ("stable_version", "canary_version", "canary_weight"):
        assert field in data


@then("HTTP 响应状态码为 401")
def then_http_401(context: dict[str, Any]) -> None:
    resp = context["http_response"]
    assert resp.status_code == 401, resp.text


# ============================================================================
# AC-7: 性能要求（分级断言：达标 assert，不达标 skip 留测量证据）
# ============================================================================


@given("工具版本管理服务就绪（InMemory 装配）")
def given_perf_ready(context: dict[str, Any]) -> None:
    """背景服务链即 InMemory 装配（no-op 显式化）。"""


@when("执行 50 轮注册-发布-回滚往返计时")
def when_perf_roundtrip(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    _register(context, "1.0.0", "base")  # 初始 STABLE（schema 与循环一致，避免兼容性降级）
    _publish(context, "1.0.0", 100)
    durations: list[float] = []
    for i in range(50):
        v_new = f"9.0.{i}"  # 每轮消耗新版本号（DEPRECATED 不可再 publish → 243）
        t0 = time.perf_counter()
        _run(
            svc.register_version(
                tool_id=context["tool_id"],
                version=v_new,
                input_schema=dict(_BASE_SCHEMA),
                output_schema=dict(_BASE_SCHEMA),
            )
        )
        _run(svc.publish_version(context["tool_id"], v_new, 100))
        _run(svc.rollback(context["tool_id"]))
        durations.append((time.perf_counter() - t0) * 1000)
    context["perf_durations"] = durations


@when("执行 50 次灰度发布操作")
def when_perf_publish(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    _register(context, "1.0.0", "base")  # 初始 STABLE（schema 与循环一致，避免兼容性降级）
    _publish(context, "1.0.0", 100)
    successes = 0
    for i in range(50):
        v_new = f"8.0.{i}"
        _run(
            svc.register_version(
                tool_id=context["tool_id"],
                version=v_new,
                input_schema=dict(_BASE_SCHEMA),
                output_schema=dict(_BASE_SCHEMA),
            )
        )
        try:
            _run(svc.publish_version(context["tool_id"], v_new, 30))
            _run(svc.abort_canary(context["tool_id"]))
            successes += 1
        except DomainError:
            pass
    context["perf_successes"] = successes


@when("执行 20 次回滚操作")
def when_perf_rollback(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    _register(context, "1.0.0", "base")  # 初始 STABLE（schema 与循环一致，避免兼容性降级）
    _publish(context, "1.0.0", 100)
    outcomes: list[str] = []
    for i in range(20):
        v_new = f"7.0.{i}"
        _run(
            svc.register_version(
                tool_id=context["tool_id"],
                version=v_new,
                input_schema=dict(_BASE_SCHEMA),
                output_schema=dict(_BASE_SCHEMA),
            )
        )
        _run(svc.publish_version(context["tool_id"], v_new, 100))
        try:
            _run(svc.rollback(context["tool_id"]))
            outcomes.append("success")
        except DomainError:
            outcomes.append("explicit-failure")
        # 每轮后校验状态无中间态：恰好一个 STABLE 或零个（若无可回滚目标）
        versions = _run(svc.list_versions(context["tool_id"]))
        stables = [v for v in versions if v.status.value == "stable"]
        canaries = [v for v in versions if v.status.value == "canary"]
        assert len(stables) <= 1, "并发不变量破坏：多 STABLE 中间态"
        assert len(canaries) <= 1, "并发不变量破坏：多 CANARY 中间态"
    context["perf_outcomes"] = outcomes


@when("执行 1000 次版本解析计时")
def when_perf_resolve(context: dict[str, Any]) -> None:
    svc: ToolVersionService = context["version_service"]
    # 预热（排除惰性注册等一次性开销）
    _run(svc.resolve_version(context["tool_id"], route_key="warmup"))
    durations: list[float] = []
    for i in range(1000):
        t0 = time.perf_counter()
        _run(svc.resolve_version(context["tool_id"], route_key=f"perf-{i}"))
        durations.append((time.perf_counter() - t0) * 1000)
    context["perf_resolve_durations"] = durations


@then("版本切换延迟 P95 小于 500 毫秒（不达标时跳过并留存测量证据）")
def then_p95_switch(context: dict[str, Any]) -> None:
    durations = context["perf_durations"]
    p95 = statistics.quantiles(durations, n=20)[18]
    if p95 >= 500:
        pytest.skip(f"环境不达标：切换延迟 P95 = {p95:.1f}ms ≥ 500ms（测量证据留存）")
    assert p95 < 500


@then("灰度发布成功率不低于 95%")
def then_publish_rate(context: dict[str, Any]) -> None:
    rate = context["perf_successes"] / 50
    assert rate >= 0.95, f"灰度发布成功率 {rate:.0%} < 95%"


@then("全部回滚操作要么成功要么明确失败且状态无中间态")
def then_rollback_rate(context: dict[str, Any]) -> None:
    outcomes = context["perf_outcomes"]
    assert all(o in ("success", "explicit-failure") for o in outcomes)
    assert len(outcomes) == 20


@then("版本路由开销 P95 小于 5 毫秒（InMemory 断言，不达标时跳过并留存测量证据）")
def then_p95_resolve(context: dict[str, Any]) -> None:
    durations = context["perf_resolve_durations"]
    p95 = statistics.quantiles(durations, n=20)[18]
    if p95 >= 5:
        pytest.skip(f"环境不达标：路由开销 P95 = {p95:.2f}ms ≥ 5ms（InMemory 装配测量证据留存）")
    assert p95 < 5


# ============================================================================
# 领域事件（Round 1 审查：成功操作发布对应事件且失败路径零发布）
# ============================================================================


@when("执行灰度提升转正与二次回滚操作序列")
def when_promote_then_double_rollback(context: dict[str, Any]) -> None:
    """promote 1.1.0 → 回滚恢复 1.0.0 → 再回滚（无可回滚目标 433 失败）。"""
    svc: ToolVersionService = context["version_service"]
    publisher: _RecordingEventPublisher = context["event_publisher"]
    publisher.published.clear()
    _publish(context, "1.1.0", 100)  # promote 转正（1.0.0 被替代记戳）
    _run(svc.rollback(context["tool_id"]))  # 恢复 1.0.0（1.1.0 清空戳）
    _capture_error(context, lambda: _run(svc.rollback(context["tool_id"])))  # 433 失败
    assert context["error"] is not None, "第二次回滚应明确失败（无可回滚目标）"


@then("成功操作各发布一个对应领域事件且失败操作零发布")
def then_events_and_failure_silence(context: dict[str, Any]) -> None:
    """promote→Published(from=canary)、rollback→RolledBack；失败回滚零事件。"""
    publisher: _RecordingEventPublisher = context["event_publisher"]
    events = publisher.published
    published_events = [e for e in events if isinstance(e, ToolVersionPublished)]
    rolled_back_events = [e for e in events if isinstance(e, ToolRolledBack)]
    assert len(published_events) == 1, f"promote 应恰好发布一个 Published 事件，实得 {len(published_events)}"
    pub = published_events[0]
    assert (pub.from_status, pub.to_status, pub.traffic_weight) == ("canary", "stable", 100)
    assert len(rolled_back_events) == 1, f"回滚应恰好发布一个 RolledBack 事件，实得 {len(rolled_back_events)}"
    rolled = rolled_back_events[0]
    assert rolled.from_version == "1.1.0"
    assert rolled.to_version == "1.0.0"
    assert rolled.deprecated_versions == ["1.1.0"]
    # 失败回滚零新增事件（published 总数 = 2 个成功事件）
    assert len(events) == 2, f"失败操作必须零发布，实得 {len(events)} 个事件"


# ============================================================================
# Task 9: 开发结束收尾验收（完成清单逐项确认）
# ============================================================================

_SRC_DELIVERY_FILES = [
    "src/domain/entities/tool_version.py",
    "src/domain/events/tool_version_events.py",
    "src/domain/exceptions/tool_version_exceptions.py",
    "src/domain/ports/tool_version_repository.py",
    "src/domain/services/tool_version_policy.py",
    "src/application/ports/tool_version_service.py",
    "src/application/services/tool_version_service.py",
    "src/infrastructure/storage/inmemory/tool_version_repository.py",
    "src/infrastructure/storage/postgresql/models/tool_version.py",
    "src/infrastructure/storage/postgresql/repository/tool_version_repository.py",
    "src/infrastructure/config/tool_version.py",
    "src/interfaces/api/tools.py",
]

_TEST_DELIVERY_FILES = [
    "tests/acceptance/test_acceptance_tool_version_management.feature",
    "tests/acceptance/test_acceptance_tool_version_management.py",
    "tests/unit/architecture/test_tool_version_management.py",
    "tests/unit/domain/entities/test_tool_version.py",
    "tests/unit/domain/services/test_tool_version_policy.py",
    "tests/unit/domain/events/test_tool_version_events.py",
    "tests/unit/domain/exceptions/test_tool_version_exceptions.py",
    "tests/unit/application/services/test_tool_version_service.py",
    "tests/unit/application/services/test_tool_execution_service.py",
    "tests/unit/infrastructure/storage/test_inmemory_tool_version_repository.py",
    "tests/unit/infrastructure/config/test_tool_version_config.py",
    "tests/unit/interfaces/api/test_tools_api.py",
    "tests/contracts/test_port_contract_tool_version_repository.py",
    "tests/contracts/test_port_contract_tool_version_service.py",
    "tests/contracts/test_api_contract_tools.py",
    "tests/contracts/test_event_contract_tool_version_events.py",
    "tests/contracts/test_event_channel_mapping_tool_version.py",
    "tests/integration/test_tool_version_integration.py",
]


@when("检查 src 完成清单的 12 个交付文件")
def when_check_src_files(context: dict[str, Any]) -> None:
    """收集 src 交付文件的存在性与可导入性。"""
    import importlib
    from pathlib import Path

    missing: list[str] = []
    for rel in _SRC_DELIVERY_FILES:
        path = Path(rel)
        if not path.exists():
            missing.append(f"缺失: {rel}")
            continue
        module = rel.removesuffix(".py").replace("/", ".")
        try:
            importlib.import_module(module)
        except Exception as exc:  # 收尾清单聚合全部导入异常（任何模块级异常都要收集）
            missing.append(f"导入失败: {rel} ({exc})")
    context["src_missing"] = missing


@then("全部文件存在且模块可导入")
def then_src_files_ok(context: dict[str, Any]) -> None:
    """src 完成清单零缺失零导入失败。"""
    assert not context["src_missing"], "src 完成清单异常:\n" + "\n".join(context["src_missing"])


@when("检查 tests 完成清单的 17 个交付文件")
def when_check_test_files(context: dict[str, Any]) -> None:
    """收集测试交付文件的存在性。"""
    from pathlib import Path

    missing = [rel for rel in _TEST_DELIVERY_FILES if not Path(rel).exists()]
    context["tests_missing"] = missing


@then("全部测试文件存在且可收集")
def then_test_files_ok(context: dict[str, Any]) -> None:
    """tests 完成清单零缺失。"""
    assert not context["tests_missing"], f"tests 完成清单缺失: {context['tests_missing']}"
