"""
应用层测试示例 - 测试用例服务、命令/查询处理器。

应用层测试特点：
- Mock 基础设施依赖（仓储、事件总线）
- 验证业务逻辑
- 验证命令处理
- 验证事件发布
"""
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from src.application.usecases.create_plan import CreatePlanCommand, CreatePlanHandler
from src.application.usecases.get_plan import GetPlanHandler, GetPlanQuery
from src.domain.entities.strategic_plan import PlanType, StrategicPlan
from src.domain.exceptions import NotFoundError, ValidationError


class TestCreatePlanHandler:
    """创建战略规划用例测试"""

    @pytest.mark.asyncio
    async def test_create_plan_success(
        self,
        mock_llm_router,
        mock_repository,
        mock_event_bus,
        mocker: MockerFixture,
    ):
        """Given 有效的创建命令，When 执行创建用例，Then 成功创建并发布事件"""
        # Arrange
        command = CreatePlanCommand(
            plan_type=PlanType.SP,
            creator_id="agent_ceo",
        )
        handler = CreatePlanHandler(
            plan_repository=mock_repository,
            event_bus=mock_event_bus,
        )

        # Mock 仓储返回
        mock_plan = mocker.Mock(spec=StrategicPlan)
        mock_plan.id = uuid4()
        mock_repository.add = mocker.AsyncMock(return_value=mock_plan)

        # Act
        result = await handler.handle(command)

        # Assert
        assert result is not None
        assert result.id == mock_plan.id
        mock_repository.add.assert_called_once()
        mock_event_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_plan_with_invalid_command_raises_error(
        self,
        mock_repository,
        mock_event_bus,
    ):
        """Given 无效的创建命令，When 执行创建用例，Then 抛出验证异常"""
        # Arrange
        command = CreatePlanCommand(
            plan_type="INVALID",  # type: ignore
            creator_id="agent_ceo",
        )
        handler = CreatePlanHandler(
            plan_repository=mock_repository,
            event_bus=mock_event_bus,
        )

        # Act & Assert
        with pytest.raises(ValidationError):
            await handler.handle(command)


class TestGetPlanHandler:
    """获取战略规划用例测试"""

    @pytest.mark.asyncio
    async def test_get_plan_found(
        self,
        mock_repository,
        mocker: MockerFixture,
    ):
        """Given 存在的规划 ID，When 执行查询用例，Then 返回规划数据"""
        # Arrange
        plan_id = uuid4()
        command = GetPlanQuery(plan_id=plan_id)

        # Mock 仓储返回
        mock_plan = mocker.Mock(spec=StrategicPlan)
        mock_repository.get_by_id = mocker.AsyncMock(return_value=mock_plan)

        handler = GetPlanHandler(plan_repository=mock_repository)

        # Act
        result = await handler.handle(command)

        # Assert
        assert result is not None
        mock_repository.get_by_id.assert_called_once_with(plan_id)

    @pytest.mark.asyncio
    async def test_get_plan_not_found_raises_error(
        self,
        mock_repository,
        mocker: MockerFixture,
    ):
        """Given 不存在的规划 ID，When 执行查询用例，Then 抛出未找到异常"""
        # Arrange
        plan_id = uuid4()
        command = GetPlanQuery(plan_id=plan_id)

        # Mock 仓储返回 None
        mock_repository.get_by_id = mocker.AsyncMock(return_value=None)

        handler = GetPlanHandler(plan_repository=mock_repository)

        # Act & Assert
        with pytest.raises(NotFoundError):
            await handler.handle(command)
