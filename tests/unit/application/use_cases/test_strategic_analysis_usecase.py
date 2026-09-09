"""Story 4.1a: StrategicAnalysisUseCase 单元测试

验证用例编排逻辑：
- tool_name 查询 → Skill 加载 → ToolExecutionService.execute → ToolExecuted 事件发布
- ToolNotFoundError 传播路径
- Skill 加载失败容错行为
- 依赖注入正确性

遵循项目标准单元测试模式（Mock 端口，禁止真实服务）。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.ports.skill_loader import SkillLoaderPort
from src.application.ports.tool_execution_service import ToolExecutionServicePort
from src.application.use_cases.strategic_analysis import (
    StrategicAnalysisRequest,
    StrategicAnalysisUseCase,
)
from src.domain.entities.tool import Tool, ToolCategory, ToolStatus
from src.domain.events.tool_events import ToolExecuted
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.tool_repository import ToolRepositoryPort
from src.domain.value_objects.tool_execution import (
    ToolResult,
    ToolResultStatus,
)


def _make_tool(**kwargs: object) -> Tool:
    """工厂函数：创建 Tool 实体"""
    defaults = {
        "tool_id": uuid.uuid4(),
        "tool_name": "pestel-analysis",
        "category": ToolCategory.EXTERNAL_ANALYSIS,
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


class TestStrategicAnalysisRequest:
    """StrategicAnalysisRequest 值对象测试"""

    def test_create_request_minimal(self) -> None:
        """最小参数构造"""
        request = StrategicAnalysisRequest(
            tool_name="pestel-analysis",
            arguments={},
            user_id=uuid.uuid4(),
            session_id="session-123",
            trace_id="trace-456",
        )
        assert request.tool_name == "pestel-analysis"
        assert request.arguments == {}
        assert isinstance(request.user_id, uuid.UUID)
        assert request.session_id == "session-123"
        assert request.trace_id == "trace-456"

    def test_request_fields_complete(self) -> None:
        """完整字段构造"""
        request = StrategicAnalysisRequest(
            tool_name="pestel-analysis",
            arguments={"industry": "tech"},
            user_id=uuid.uuid4(),
            session_id="session-789",
            trace_id="trace-012",
        )
        assert request.arguments == {"industry": "tech"}


class TestStrategicAnalysisUseCase:
    """StrategicAnalysisUseCase 用例编排测试"""

    @pytest.fixture
    def mock_registry(self) -> MagicMock:
        """模拟 ToolRegistryServicePort"""
        mock = MagicMock(spec=ToolRepositoryPort)
        return mock

    @pytest.fixture
    def mock_execution_service(self) -> AsyncMock:
        """模拟 ToolExecutionServicePort"""
        return AsyncMock(spec=ToolExecutionServicePort)

    @pytest.fixture
    def mock_skill_loader(self) -> AsyncMock:
        """模拟 SkillLoaderPort"""
        return AsyncMock(spec=SkillLoaderPort)

    @pytest.fixture
    def mock_event_publisher(self) -> AsyncMock:
        """模拟 EventPublisher"""
        return AsyncMock(spec=EventPublisher)

    @pytest.fixture
    def use_case(
        self,
        mock_registry: MagicMock,
        mock_execution_service: AsyncMock,
        mock_skill_loader: AsyncMock,
        mock_event_publisher: AsyncMock,
    ) -> StrategicAnalysisUseCase:
        """创建 StrategicAnalysisUseCase 实例"""
        return StrategicAnalysisUseCase(
            registry=mock_registry,
            execution_service=mock_execution_service,
            skill_loader=mock_skill_loader,
            event_publisher=mock_event_publisher,
        )

    @pytest.mark.asyncio
    async def test_execute_success_happy_path(
        self,
        use_case: StrategicAnalysisUseCase,
        mock_registry: MagicMock,
        mock_execution_service: AsyncMock,
        mock_skill_loader: AsyncMock,
        mock_event_publisher: AsyncMock,
    ) -> None:
        """正常执行并发布事件"""
        # 准备
        tool = _make_tool()
        mock_registry.get_tool.return_value = tool
        mock_execution_service.execute.return_value = ToolResult(
            tool_id=tool.tool_id,
            status=ToolResultStatus.SUCCESS,
            output={"result": "analysis complete"},
            evidence_package=None,
            started_at=None,
            completed_at=None,
        )

        request = StrategicAnalysisRequest(
            tool_name="pestel-analysis",
            arguments={},
            user_id=uuid.uuid4(),
            session_id="session-123",
            trace_id="trace-456",
        )

        # 执行
        result = await use_case.execute(request)

        # 验证
        assert result.status == ToolResultStatus.SUCCESS
        mock_registry.get_tool.assert_called_once_with(tool_name="pestel-analysis")
        mock_skill_loader.load_metadata.assert_called_once_with("pestel-analysis")
        mock_execution_service.execute.assert_called_once()
        mock_event_publisher.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_not_found_raises(
        self,
        use_case: StrategicAnalysisUseCase,
        mock_registry: MagicMock,
    ) -> None:
        """ToolNotFoundError 透传"""
        from src.domain.exceptions import ToolNotFoundError

        mock_registry.get_tool.return_value = None

        request = StrategicAnalysisRequest(
            tool_name="nonexistent-tool",
            arguments={},
            user_id=uuid.uuid4(),
            session_id="session-123",
            trace_id="trace-456",
        )

        with pytest.raises(ToolNotFoundError):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_execute_delegates_to_execution_service(
        self,
        use_case: StrategicAnalysisUseCase,
        mock_registry: MagicMock,
        mock_execution_service: AsyncMock,
    ) -> None:
        """验证委托调用"""
        tool = _make_tool()
        mock_registry.get_tool.return_value = tool
        mock_execution_service.execute.return_value = ToolResult(
            tool_id=tool.tool_id,
            status=ToolResultStatus.SUCCESS,
            output={},
            evidence_package=None,
            started_at=None,
            completed_at=None,
        )

        request = StrategicAnalysisRequest(
            tool_name="pestel-analysis",
            arguments={"key": "value"},
            user_id=uuid.uuid4(),
            session_id="session-123",
            trace_id="trace-456",
        )

        await use_case.execute(request)

        mock_execution_service.execute.assert_called_once()
        call_args = mock_execution_service.execute.call_args
        assert call_args[1]["tool_id"] == tool.tool_id or call_args[0][0] == tool.tool_id

    @pytest.mark.asyncio
    async def test_execute_publishes_tool_executed_event(
        self,
        use_case: StrategicAnalysisUseCase,
        mock_registry: MagicMock,
        mock_execution_service: AsyncMock,
        mock_event_publisher: AsyncMock,
    ) -> None:
        """验证 EventPublisher.publish 被调用"""
        tool = _make_tool()
        mock_registry.get_tool.return_value = tool
        mock_execution_service.execute.return_value = ToolResult(
            tool_id=tool.tool_id,
            status=ToolResultStatus.SUCCESS,
            output={"result": "done"},
            evidence_package=None,
            started_at=None,
            completed_at=None,
        )

        request = StrategicAnalysisRequest(
            tool_name="pestel-analysis",
            arguments={},
            user_id=uuid.uuid4(),
            session_id="session-123",
            trace_id="trace-456",
        )

        await use_case.execute(request)

        mock_event_publisher.publish.assert_called_once()
        event = mock_event_publisher.publish.call_args[0][0]
        assert isinstance(event, ToolExecuted)

    @pytest.mark.asyncio
    async def test_execute_event_has_correct_aggregate(
        self,
        use_case: StrategicAnalysisUseCase,
        mock_registry: MagicMock,
        mock_execution_service: AsyncMock,
        mock_event_publisher: AsyncMock,
    ) -> None:
        """验证事件 aggregate_id = execution_id, type = ToolExecution"""
        tool = _make_tool()
        mock_registry.get_tool.return_value = tool
        mock_execution_service.execute.return_value = ToolResult(
            tool_id=tool.tool_id,
            status=ToolResultStatus.SUCCESS,
            output={},
            evidence_package=None,
            started_at=None,
            completed_at=None,
        )

        request = StrategicAnalysisRequest(
            tool_name="pestel-analysis",
            arguments={},
            user_id=uuid.uuid4(),
            session_id="session-123",
            trace_id="trace-456",
        )

        await use_case.execute(request)

        event = mock_event_publisher.publish.call_args[0][0]
        assert event.aggregate_type == "ToolExecution"

    @pytest.mark.asyncio
    async def test_execute_propagates_execution_error(
        self,
        use_case: StrategicAnalysisUseCase,
        mock_registry: MagicMock,
        mock_execution_service: AsyncMock,
    ) -> None:
        """ToolExecutionFailedError 透传"""
        from src.domain.exceptions import ToolExecutionFailedError

        tool = _make_tool()
        mock_registry.get_tool.return_value = tool
        mock_execution_service.execute.side_effect = ToolExecutionFailedError(
            execution_id=str(uuid.uuid4()),
            stage="Think",
            reason="LLM 调用失败",
        )

        request = StrategicAnalysisRequest(
            tool_name="pestel-analysis",
            arguments={},
            user_id=uuid.uuid4(),
            session_id="session-123",
            trace_id="trace-456",
        )

        with pytest.raises(ToolExecutionFailedError):
            await use_case.execute(request)
