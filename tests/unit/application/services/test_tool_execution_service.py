"""ToolExecutionService 版本集成单元测试（Story 4-6 Task 5 TDD 红→绿）

TestToolVersionIntegration：注入 tool_version_service 后的版本路由 + 派生副本
（引擎/装饰器零改动——_RecordingEngine 子类观测传入副本）。

Mock 工厂先例：test_input_output_validator_chain.py 的 _make_tool/_make_context/
_make_tool_call + MagicMock(spec=RegistryPort)。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.application.services.tool_execution_service import ToolExecutionService
from src.application.services.tool_version_service import ToolVersionService
from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.tool_version_repository import ToolVersionQuery
from src.infrastructure.storage.inmemory.tool_repository import InMemoryToolRepository
from src.infrastructure.storage.inmemory.tool_version_repository import (
    InMemoryToolVersionRepository,
)
from src.infrastructure.validation.jsonschema_validator import JsonSchemaValidatorImpl

BASE = {"type": "object", "properties": {"factor": {"type": "string"}}, "required": ["factor"]}
CANARY_SCHEMA = {
    "type": "object",
    "properties": {"factor": {"type": "string"}},
    "required": ["factor"],
    "additionalProperties": False,
}


class _RecordingEngine(ToolExecutionEngine):
    """真实引擎子类：记录传入 Tool 副本（引擎零改动前提下的观测面）。"""

    def __init__(self, llm_client: Any, sandbox: Any) -> None:
        super().__init__(llm_client=llm_client, sandbox=sandbox)
        self.received_tools: list[Tool] = []

    async def execute(self, tool_id, tool, tool_call, context) -> Any:
        self.received_tools.append(tool)
        return await super().execute(tool_id=tool_id, tool=tool, tool_call=tool_call, context=context)


def _make_mock_llm() -> AsyncMock:
    mock = AsyncMock()
    mock.structured_generate = AsyncMock(return_value="ok")
    mock.generate = AsyncMock(return_value=AsyncMock(content="ok"))
    return mock


def _make_mock_sandbox() -> AsyncMock:
    mock = AsyncMock()
    mock.start_container = AsyncMock()
    mock.execute_code = AsyncMock(return_value={"status": "ok", "output": "out"})
    mock.stop_container = AsyncMock()
    return mock


def _make_tool() -> Tool:
    now = datetime.now(UTC)
    return Tool(
        tool_id=uuid.uuid4(),
        name=f"exec-tool-{uuid.uuid4().hex[:6]}",
        description="t",
        category=ToolCategory.ANALYSIS,
        input_schema=dict(BASE),
        output_schema=dict(BASE),
        status=ToolStatus.ACTIVE,
        version="1.0.0",
        created_at=now,
        updated_at=now,
    )


def _expected_hit(route_key: str, weight: int) -> bool:
    import hashlib

    return int(hashlib.sha256(route_key.encode()).hexdigest(), 16) % 100 < weight


def _make_stack() -> dict[str, Any]:
    """构造注入 version service 的真实执行栈（InMemory 全真实服务）。"""
    tool = _make_tool()
    tool_repo = InMemoryToolRepository()
    tool_repo.save(tool)
    registry = MagicMock()
    registry.get_tool = MagicMock(return_value=tool)
    version_repo = InMemoryToolVersionRepository()
    version_service = ToolVersionService(
        repository=version_repo,
        schema_validator=JsonSchemaValidatorImpl(),
        tool_registry=registry,
        event_publisher=AsyncMock(spec=EventPublisher),
    )
    engine = _RecordingEngine(llm_client=_make_mock_llm(), sandbox=_make_mock_sandbox())
    service = ToolExecutionService(
        registry=registry,
        engine=engine,
        tool_version_service=version_service,
    )
    return {
        "service": service,
        "engine": engine,
        "version_service": version_service,
        "version_repo": version_repo,
        "tool": tool,
    }


def _make_context(route_key: str) -> Any:
    from src.domain.value_objects.tool_execution import ExecutionContext

    return ExecutionContext(tenant_id=uuid.uuid4(), trace_id=route_key)


async def _setup_canary(stack: dict[str, Any], weight: int = 30) -> None:
    """构造灰度态：1.0.0 STABLE + 1.1.0 CANARY(weight)。"""
    vs: ToolVersionService = stack["version_service"]
    tool: Tool = stack["tool"]
    tid = tool.tool_id
    await vs.register_version(tid, "1.0.0", dict(BASE), dict(BASE))
    await vs.publish_version(tid, "1.0.0", 100)
    await vs.register_version(tid, "1.1.0", dict(CANARY_SCHEMA), dict(BASE))
    await vs.publish_version(tid, "1.1.0", weight)


def _pick_hit_miss(weight: int) -> tuple[str, str]:
    for i in range(10000):
        hit, miss = f"hit-{i}", f"miss-{i}"
        if _expected_hit(hit, weight) and not _expected_hit(miss, weight):
            return hit, miss
    raise AssertionError("样本集内必存在命中与未命中键")


class TestToolVersionIntegration:
    """执行链版本集成（注入路由 / 派生副本 / 未注入回退 / 惰性注册）。"""

    @pytest.mark.asyncio
    async def test_canary_hit_routes_to_canary_copy(self) -> None:
        """命中灰度 → 引擎收到副本 version=1.1.0 且 schema 已替换。"""
        stack = _make_stack()
        await _setup_canary(stack, 30)
        hit, _ = _pick_hit_miss(30)
        tool_call = MagicMock()
        tool_call.version = None
        await stack["service"].execute(stack["tool"].tool_id, tool_call, _make_context(hit))
        received = stack["engine"].received_tools[-1]
        assert received.version == "1.1.0"
        assert received.input_schema == CANARY_SCHEMA

    @pytest.mark.asyncio
    async def test_canary_miss_routes_to_stable_copy(self) -> None:
        """未命中 → 引擎收到 stable 副本 version=1.0.0。"""
        stack = _make_stack()
        await _setup_canary(stack, 30)
        _, miss = _pick_hit_miss(30)
        tool_call = MagicMock()
        tool_call.version = None
        await stack["service"].execute(stack["tool"].tool_id, tool_call, _make_context(miss))
        received = stack["engine"].received_tools[-1]
        assert received.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_explicit_version_skips_routing(self) -> None:
        """ToolCall.version 显式 → 精确执行该版本（跳过流量路由）。"""
        stack = _make_stack()
        await _setup_canary(stack, 30)
        tool_call = MagicMock()
        tool_call.version = "1.0.0"  # 即使命中灰度键也走 stable
        hit, _ = _pick_hit_miss(30)
        await stack["service"].execute(stack["tool"].tool_id, tool_call, _make_context(hit))
        received = stack["engine"].received_tools[-1]
        assert received.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_lazy_initial_registration_on_first_execute(self) -> None:
        """惰性初始版本：无版本记录时首执行建立 STABLE 1.0.0。"""
        stack = _make_stack()
        tool_call = MagicMock()
        tool_call.version = None
        await stack["service"].execute(stack["tool"].tool_id, tool_call, _make_context("first"))
        versions = await stack["version_repo"].list_by_query(ToolVersionQuery(tool_id=stack["tool"].tool_id, limit=10**9))
        assert any(tv.version == "1.0.0" and tv.status.value == "stable" for tv in versions)
        received = stack["engine"].received_tools[-1]
        assert received.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_without_version_service_original_behavior(self) -> None:
        """未注入 tool_version_service → 4.1a 原行为（直接 registry Tool）。"""
        tool = _make_tool()
        registry = MagicMock()
        registry.get_tool = MagicMock(return_value=tool)
        engine = _RecordingEngine(llm_client=_make_mock_llm(), sandbox=_make_mock_sandbox())
        service = ToolExecutionService(registry=registry, engine=engine)
        tool_call = MagicMock()
        tool_call.version = None
        await service.execute(tool.tool_id, tool_call, _make_context("any"))
        received = engine.received_tools[-1]
        assert received.version == "1.0.0"  # registry 原对象
