"""Story 4.1c Task 1 [A]: StrategicAnalysisUseCase 生产链路接线单元测试

验证用例将 L2 `load_sop` 解析出的 ToolMetadata（含 data_sources 白名单）注入
`ExecutionContext.extensions["tool_metadata"]`，使 Engine `_resolve_data_sources`
白名单校验在生产链路真正生效（AC-2）。

4 场景（Story AC-2 验证标准）：
1. load_sop 注入 —— extensions 含 tool_metadata 且 data_sources == L2 声明
2. load_sop 失败容错 —— 不阻断执行，extensions 不含 tool_metadata 键
3. 无标记零行为变化 —— 代码无 $DATA_SOURCE 标记时执行链路行为不变
4. 空白名单 207 —— 未成熟化 Skill（data_sources 空 tuple）含标记时抛 207

场景 3/4 通过真实 ToolExecutionEngine（Mock LLM/Sandbox 端口 + 真实 Resolver +
Stub 数据源适配器）作为 execution_service side_effect 驱动，验证接线端到端语义。

遵循项目标准单元测试模式（Mock 端口，禁止真实服务/真实 Redis）。
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.ports.skill_loader import SkillDocument, SkillLoaderPort, ToolMetadata
from src.application.ports.tool_execution_service import ToolExecutionServicePort
from src.application.ports.tool_registry_service import ToolRegistryServicePort
from src.application.services.data_source_resolver import DataSourceResolverService
from src.application.services.tool_execution_engine import ToolExecutionEngine
from src.application.use_cases.strategic_analysis import (
    StrategicAnalysisRequest,
    StrategicAnalysisUseCase,
)
from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.exceptions import BusinessRuleViolationError, SkillLoadError
from src.domain.ports.data_source import DataSourceQuery
from src.domain.ports.event_publisher import EventPublisher
from src.domain.value_objects.data_source import (
    DataFreshness,
    DataSourceApiType,
    DataSourceRef,
    DataSourceResult,
)
from src.domain.value_objects.tool_execution import (
    ExecutionContext,
    ToolResult,
    ToolResultStatus,
)

# =============================================================================
# 测试工厂
# =============================================================================


def _make_tool(**kwargs: object) -> Tool:
    """工厂函数：创建 Tool 实体（范本 test_strategic_analysis_usecase.py）"""
    defaults: dict = {
        "tool_id": uuid.uuid4(),
        "name": "pestel-analysis",
        "category": ToolCategory.ENVIRONMENT_ANALYSIS,
        "status": ToolStatus.ACTIVE,
        "description": "PESTEL 宏观环境分析",
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object", "properties": {}},
        "rule_version": "BLM-v3.2",
        "reliability_score": 0.85,
        "execution_count": 10,
        "slug": "pestel-analysis",
    }
    defaults.update(kwargs)
    return Tool(**defaults)


def _make_metadata(*source_names: str) -> ToolMetadata:
    """工厂函数：创建声明指定数据源白名单的 ToolMetadata（模拟 L2 frontmatter）"""
    return ToolMetadata(
        tool_name="pestel-analysis",
        slug="pestel-analysis",
        category="environment_analysis",
        input_schema={},
        output_schema={},
        data_sources=tuple(
            DataSourceRef(
                name=name,
                url=f"https://fake.local/{name}",
                ttl_seconds=3600,
                api_type=DataSourceApiType.REST_JSON,
            )
            for name in source_names
        ),
    )


def _make_skill_document(metadata: ToolMetadata) -> SkillDocument:
    """工厂函数：创建 load_sop 返回的 SkillDocument（frontmatter 即 ToolMetadata）"""
    return SkillDocument(
        tool_name=metadata.tool_name,
        slug=metadata.slug,
        content="# SOP",
        token_count=10,
        frontmatter=metadata,
        body="# SOP",
    )


def _make_request(tool_name: str = "pestel-analysis") -> StrategicAnalysisRequest:
    """工厂函数：创建用例请求"""
    return StrategicAnalysisRequest(
        tool_name=tool_name,
        arguments={},
        user_id=uuid.uuid4(),
        session_id="session-123",
        trace_id="trace-456",
    )


class _StubDataSourceAdapter:
    """数据源 Stub 适配器（单元测试专用，call_count 计数）"""

    def __init__(self, name: str) -> None:
        self._ref = DataSourceRef(
            name=name,
            url=f"https://fake.local/{name}",
            ttl_seconds=3600,
            api_type=DataSourceApiType.REST_JSON,
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
            payload=json.dumps({"indicator": query.query, "value": 1.0}),
            source_timestamp=now,
            fetched_at=now,
            freshness=DataFreshness(source_timestamp=now, ttl_seconds=3600),
            confidence=0.9,
        )


class _StubCache:
    """L1 缓存 Stub（单元测试禁用真实 Redis；读始终未命中，写透传）

    完整实现 L1CachePort 协议 8 方法（mypy 结构兼容性要求）。
    """

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        return True

    async def delete(self, key: str) -> bool:
        return True

    async def exists(self, key: str) -> bool:
        return False

    async def delete_pattern(self, pattern: str) -> int:
        return 0

    async def set_with_ttl(self, key: str, value: str, ttl: int) -> bool:
        return True

    async def set_nx(self, key: str, value: str, ttl: int) -> bool:
        return True

    async def eval(self, script: str, keys: list[str], args: list[str]) -> Any:
        return None


def _make_real_engine_side_effect(code: str, adapters: dict[str, _StubDataSourceAdapter]) -> Any:
    """构造 execution_service.execute 的 side_effect：以真实 Engine 驱动传入的 context。

    LLM mock 内容分派（Code 阶段 prompt 含「生成代码」特征串时返回预设 code），
    Resolver 真实（白名单校验真实生效），缓存 Stub（始终未命中）。
    """

    async def _execute(tool_id: uuid.UUID, tool_call: Any, context: ExecutionContext) -> ToolResult:
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
        resolver = DataSourceResolverService(adapters=adapters, cache=_StubCache(), event_publisher=None)
        engine.set_data_source_resolver(resolver)

        tool = _make_tool(tool_id=tool_id)
        return await engine.execute(tool_id=tool_id, tool=tool, tool_call=tool_call, context=context)

    return _execute


# =============================================================================
# 测试类
# =============================================================================


class TestStrategicAnalysisDataSourceWiring:
    """StrategicAnalysisUseCase 接线测试（load_sop + extensions["tool_metadata"] 注入）"""

    @pytest.fixture
    def mock_registry(self) -> MagicMock:
        return MagicMock(spec=ToolRegistryServicePort)

    @pytest.fixture
    def mock_execution_service(self) -> AsyncMock:
        return AsyncMock(spec=ToolExecutionServicePort)

    @pytest.fixture
    def mock_skill_loader(self) -> AsyncMock:
        return AsyncMock(spec=SkillLoaderPort)

    @pytest.fixture
    def mock_event_publisher(self) -> AsyncMock:
        return AsyncMock(spec=EventPublisher)

    @pytest.fixture
    def use_case(
        self,
        mock_registry: MagicMock,
        mock_execution_service: AsyncMock,
        mock_skill_loader: AsyncMock,
        mock_event_publisher: AsyncMock,
    ) -> StrategicAnalysisUseCase:
        return StrategicAnalysisUseCase(
            tool_registry=mock_registry,
            execution_service=mock_execution_service,
            skill_loader=mock_skill_loader,
            event_publisher=mock_event_publisher,
        )

    @pytest.mark.asyncio
    async def test_load_sop_metadata_injected_into_extensions(
        self,
        use_case: StrategicAnalysisUseCase,
        mock_registry: MagicMock,
        mock_execution_service: AsyncMock,
        mock_skill_loader: AsyncMock,
    ) -> None:
        """场景 1：load_sop 解析的 ToolMetadata 注入 extensions["tool_metadata"]"""
        tool = _make_tool()
        mock_registry.get_tool.return_value = tool
        metadata = _make_metadata("world-bank", "imf")
        mock_skill_loader.load_sop.return_value = _make_skill_document(metadata)
        mock_execution_service.execute.return_value = ToolResult(
            tool_id=tool.tool_id,
            status=ToolResultStatus.SUCCESS,
            output={},
            evidence_package=None,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )

        result = await use_case.execute(_make_request())

        assert result.status == ToolResultStatus.SUCCESS
        mock_skill_loader.load_sop.assert_called_once_with("pestel-analysis")
        context = mock_execution_service.execute.call_args[1]["context"]
        assert context.extensions.get("tool_metadata") is metadata
        assert tuple(ref.name for ref in context.extensions["tool_metadata"].data_sources) == ("world-bank", "imf")

    @pytest.mark.asyncio
    async def test_load_sop_failure_tolerated_not_blocking(
        self,
        use_case: StrategicAnalysisUseCase,
        mock_registry: MagicMock,
        mock_execution_service: AsyncMock,
        mock_skill_loader: AsyncMock,
    ) -> None:
        """场景 2：load_sop 失败容错不阻断执行，extensions 不含 tool_metadata 键"""
        tool = _make_tool()
        mock_registry.get_tool.return_value = tool
        mock_skill_loader.load_sop.side_effect = SkillLoadError(
            slug="pestel-analysis",
            file_path="/fake/SKILL.md",
            cause=OSError("disk error"),
        )
        mock_execution_service.execute.return_value = ToolResult(
            tool_id=tool.tool_id,
            status=ToolResultStatus.SUCCESS,
            output={},
            evidence_package=None,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )

        result = await use_case.execute(_make_request())

        assert result.status == ToolResultStatus.SUCCESS
        mock_skill_loader.load_sop.assert_called_once_with("pestel-analysis")
        context = mock_execution_service.execute.call_args[1]["context"]
        assert "tool_metadata" not in context.extensions

    @pytest.mark.asyncio
    async def test_no_marker_zero_behavior_change(
        self,
        use_case: StrategicAnalysisUseCase,
        mock_registry: MagicMock,
        mock_execution_service: AsyncMock,
        mock_skill_loader: AsyncMock,
    ) -> None:
        """场景 3：代码无 $DATA_SOURCE 标记时执行链路零行为变化（真实 Engine 驱动）"""
        tool = _make_tool()
        mock_registry.get_tool.return_value = tool
        metadata = _make_metadata("world-bank")
        mock_skill_loader.load_sop.return_value = _make_skill_document(metadata)

        adapters = {"world-bank": _StubDataSourceAdapter("world-bank")}
        mock_execution_service.execute.side_effect = _make_real_engine_side_effect(
            code='result = {"analysis": "no marker"}',
            adapters=adapters,
        )

        result = await use_case.execute(_make_request())

        assert result.status == ToolResultStatus.SUCCESS
        # 无标记：Resolver 未被触发，数据源适配器零调用
        assert adapters["world-bank"].call_count == 0

    @pytest.mark.asyncio
    async def test_empty_whitelist_raises_207(
        self,
        use_case: StrategicAnalysisUseCase,
        mock_registry: MagicMock,
        mock_execution_service: AsyncMock,
        mock_skill_loader: AsyncMock,
    ) -> None:
        """场景 4：未成熟化 Skill（data_sources 空 tuple）代码含标记时抛 207（安全失败）"""
        tool = _make_tool()
        mock_registry.get_tool.return_value = tool
        # 未成熟化 Skill：load_sop 成功但白名单为空
        mock_skill_loader.load_sop.return_value = _make_skill_document(_make_metadata())

        adapters = {"world-bank": _StubDataSourceAdapter("world-bank")}
        mock_execution_service.execute.side_effect = _make_real_engine_side_effect(
            code='data = $DATA_SOURCE("world-bank", "GDP China")',
            adapters=adapters,
        )

        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await use_case.execute(_make_request())
        assert exc_info.value.code == "EXCEPTION_207"
        assert "白名单" in exc_info.value.message
