"""
sisys - Create Plan Use Case Tests.

测试应用层创建战略规划用例。
"""


import pytest
from pytest_mock import MockerFixture

from src.application.usecases.create_plan import CreatePlanCommand, CreatePlanHandler
from src.domain.entities.strategic_plan import PlanType


class TestCreatePlanCommand:
    """测试 CreatePlanCommand 命令类"""

    def test_command_creation(self):
        """Given 创建命令参数，When 创建命令，Then 包含所有字段"""
        command = CreatePlanCommand(
            plan_type=PlanType.SP,
            creator_id="user-123",
        )

        assert command.plan_type == PlanType.SP
        assert command.creator_id == "user-123"

    def test_command_is_frozen(self):
        """Given 创建命令，When 尝试修改，Then 抛出异常"""
        command = CreatePlanCommand(
            plan_type=PlanType.SP,
            creator_id="user-123",
        )

        with pytest.raises(Exception):  # frozen dataclass 会抛出 FrozenInstanceError
            command.creator_id = "user-456"  # type: ignore


class TestCreatePlanHandler:
    """测试 CreatePlanHandler 处理器"""

    @pytest.mark.asyncio
    async def test_handle_creates_plan(self, mocker: MockerFixture):
        """Given 创建命令，When 处理，Then 创建规划"""
        # Arrange
        mock_repository = mocker.AsyncMock()
        mock_plan = mocker.MagicMock()
        mock_plan.domain_events = []
        mock_repository.add.return_value = mock_plan

        handler = CreatePlanHandler(plan_repository=mock_repository)
        command = CreatePlanCommand(
            plan_type=PlanType.SP,
            creator_id="user-123",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert result == mock_plan
        mock_repository.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_with_event_bus(self, mocker: MockerFixture):
        """Given 创建命令和事件总线，When 处理，Then 发布事件"""
        # Arrange
        mock_repository = mocker.AsyncMock()
        mock_event_bus = mocker.AsyncMock()
        mock_plan = mocker.MagicMock()
        mock_repository.add.return_value = mock_plan

        handler = CreatePlanHandler(
            plan_repository=mock_repository,
            event_bus=mock_event_bus,
        )
        command = CreatePlanCommand(
            plan_type=PlanType.SP,
            creator_id="user-123",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert result == mock_plan
        mock_event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_handle_without_event_bus(self, mocker: MockerFixture):
        """Given 创建命令但无事件总线，When 处理，Then 不发布事件"""
        # Arrange
        mock_repository = mocker.AsyncMock()
        mock_plan = mocker.MagicMock()
        mock_plan.domain_events = []
        mock_repository.add.return_value = mock_plan

        handler = CreatePlanHandler(plan_repository=mock_repository)
        command = CreatePlanCommand(
            plan_type=PlanType.SP,
            creator_id="user-123",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert result == mock_plan
        mock_repository.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_with_multiple_events(self, mocker: MockerFixture):
        """Given 创建命令和多个事件，When 处理，Then 发布所有事件"""
        # Arrange
        mock_repository = mocker.AsyncMock()
        mock_event_bus = mocker.AsyncMock()
        mock_plan = mocker.MagicMock()
        mock_repository.add.return_value = mock_plan

        handler = CreatePlanHandler(
            plan_repository=mock_repository,
            event_bus=mock_event_bus,
        )
        command = CreatePlanCommand(
            plan_type=PlanType.SP,
            creator_id="user-123",
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert result == mock_plan
        assert mock_event_bus.publish.call_count >= 1

    @pytest.mark.asyncio
    async def test_handler_initialization(self, mocker: MockerFixture):
        """Given 仓储和事件总线，When 初始化处理器，Then 保存引用"""
        # Arrange
        mock_repository = mocker.AsyncMock()
        mock_event_bus = mocker.AsyncMock()

        # Act
        handler = CreatePlanHandler(
            plan_repository=mock_repository,
            event_bus=mock_event_bus,
        )

        # Assert
        assert handler._plan_repository == mock_repository
        assert handler._event_bus == mock_event_bus

    @pytest.mark.asyncio
    async def test_handler_initialization_without_event_bus(self, mocker: MockerFixture):
        """Given 只有仓储，When 初始化处理器，Then 事件总线为 None"""
        # Arrange
        mock_repository = mocker.AsyncMock()

        # Act
        handler = CreatePlanHandler(plan_repository=mock_repository)

        # Assert
        assert handler._plan_repository == mock_repository
        assert handler._event_bus is None
