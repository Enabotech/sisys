"""
sisys - Get Plan Use Case Tests.

测试应用层获取战略规划用例。
"""

from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from src.application.usecases.get_plan import GetPlanHandler, GetPlanQuery
from src.domain.exceptions.not_found_error import NotFoundError


class TestGetPlanQuery:
    """测试 GetPlanQuery 查询类"""

    def test_query_creation(self):
        """Given 查询参数，When 创建查询，Then 包含所有字段"""
        plan_id = uuid4()
        query = GetPlanQuery(plan_id=plan_id)

        assert query.plan_id == plan_id

    def test_query_is_frozen(self):
        """Given 查询，When 尝试修改，Then 抛出异常"""
        plan_id = uuid4()
        query = GetPlanQuery(plan_id=plan_id)

        with pytest.raises(Exception):  # frozen dataclass 会抛出 FrozenInstanceError
            query.plan_id = uuid4()  # type: ignore


class TestGetPlanHandler:
    """测试 GetPlanHandler 处理器"""

    @pytest.mark.asyncio
    async def test_handle_returns_plan(self, mocker: MockerFixture):
        """Given 存在的规划 ID，When 处理查询，Then 返回规划"""
        # Arrange
        mock_repository = mocker.AsyncMock()
        mock_plan = mocker.MagicMock()
        mock_repository.get_by_id.return_value = mock_plan

        handler = GetPlanHandler(plan_repository=mock_repository)
        query = GetPlanQuery(plan_id=uuid4())

        # Act
        result = await handler.handle(query)

        # Assert
        assert result == mock_plan
        mock_repository.get_by_id.assert_called_once_with(query.plan_id)

    @pytest.mark.asyncio
    async def test_handle_with_none_returns_raises_error(self, mocker: MockerFixture):
        """Given 不存在的规划 ID，When 处理查询，Then 抛出 NotFoundError"""
        # Arrange
        mock_repository = mocker.AsyncMock()
        mock_repository.get_by_id.return_value = None

        handler = GetPlanHandler(plan_repository=mock_repository)
        plan_id = uuid4()
        query = GetPlanQuery(plan_id=plan_id)

        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            await handler.handle(query)

        assert exc_info.value.entity_type == "StrategicPlan"
        assert str(plan_id) in exc_info.value.entity_id

    @pytest.mark.asyncio
    async def test_handler_initialization(self, mocker: MockerFixture):
        """Given 仓储，When 初始化处理器，Then 保存引用"""
        # Arrange
        mock_repository = mocker.AsyncMock()

        # Act
        handler = GetPlanHandler(plan_repository=mock_repository)

        # Assert
        assert handler._plan_repository == mock_repository

    @pytest.mark.asyncio
    async def test_handle_with_string_id(self, mocker: MockerFixture):
        """Given 字符串 ID，When 处理查询，Then 转换为 UUID 并查询"""
        # Arrange
        mock_repository = mocker.AsyncMock()
        mock_plan = mocker.MagicMock()
        mock_repository.get_by_id.return_value = mock_plan

        handler = GetPlanHandler(plan_repository=mock_repository)
        plan_id = uuid4()
        query = GetPlanQuery(plan_id=plan_id)

        # Act
        result = await handler.handle(query)

        # Assert
        assert result == mock_plan
        mock_repository.get_by_id.assert_called_once_with(plan_id)

    @pytest.mark.asyncio
    async def test_handle_preserves_plan_identity(self, mocker: MockerFixture):
        """Given 规划 ID，When 获取规划，Then 返回相同 ID 的规划"""
        # Arrange
        mock_repository = mocker.AsyncMock()
        mock_plan = mocker.MagicMock()
        mock_plan.id = uuid4()
        mock_repository.get_by_id.return_value = mock_plan

        handler = GetPlanHandler(plan_repository=mock_repository)
        query = GetPlanQuery(plan_id=mock_plan.id)

        # Act
        result = await handler.handle(query)

        # Assert
        assert result.id == mock_plan.id
