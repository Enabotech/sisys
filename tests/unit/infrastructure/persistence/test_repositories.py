"""
基础设施层测试示例 - 测试仓储实现、事件总线、外部服务适配器。

基础设施层测试特点：
- 可能需要真实外部服务（集成测试）
- 或使用 Mock（单元测试）
- 验证技术实现细节
- 验证与外部服务的交互
"""

from uuid import uuid4

import pytest
from pytest_mock import MockerFixture


class TestStrategicPlanRepositoryUnit:
    """战略规划仓储单元测试（使用 Mock）"""

    @pytest.mark.asyncio
    async def test_repository_add_plan(
        self,
        mock_repository,
        mocker: MockerFixture,
    ):
        """Given 新规划，When 添加到仓储，Then 成功保存"""
        # Arrange
        mock_plan = mocker.Mock()
        mock_plan.id = uuid4()
        mock_repository.add = mocker.AsyncMock(return_value=mock_plan)

        # Act
        result = await mock_repository.add(mock_plan)

        # Assert
        assert result == mock_plan
        mock_repository.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_repository_get_by_id(
        self,
        mock_repository,
        mocker: MockerFixture,
    ):
        """Given 存在的规划 ID，When 查询，Then 返回规划"""
        # Arrange
        plan_id = uuid4()
        mock_plan = mocker.Mock()
        mock_repository.get_by_id = mocker.AsyncMock(return_value=mock_plan)

        # Act
        result = await mock_repository.get_by_id(plan_id)

        # Assert
        assert result == mock_plan
        mock_repository.get_by_id.assert_called_once_with(plan_id)

    @pytest.mark.asyncio
    async def test_repository_update_plan(
        self,
        mock_repository,
        mocker: MockerFixture,
    ):
        """Given 现有规划，When 更新，Then 成功保存变更"""
        # Arrange
        mock_plan = mocker.Mock()
        mock_plan.id = uuid4()
        mock_repository.update = mocker.AsyncMock(return_value=mock_plan)

        # Act
        result = await mock_repository.update(mock_plan)

        # Assert
        assert result == mock_plan
        mock_repository.update.assert_called_once_with(mock_plan)

    @pytest.mark.asyncio
    async def test_repository_delete_plan(
        self,
        mock_repository,
        mocker: MockerFixture,
    ):
        """Given 规划 ID，When 删除，Then 成功删除"""
        # Arrange
        plan_id = uuid4()
        mock_repository.delete = mocker.AsyncMock()

        # Act
        await mock_repository.delete(plan_id)

        # Assert
        mock_repository.delete.assert_called_once_with(plan_id)


class TestEventBusUnit:
    """事件总线单元测试（使用 Mock）"""

    @pytest.mark.asyncio
    async def test_event_bus_publish(
        self,
        mock_event_bus,
    ):
        """Given 事件，When 发布，Then 成功发送到总线"""
        # Arrange
        event_type = "plan.created"
        event_data = {"plan_id": str(uuid4())}

        # Act
        await mock_event_bus.publish(event_type, event_data)

        # Assert
        mock_event_bus.publish.assert_called_once_with(event_type, event_data)

    @pytest.mark.asyncio
    async def test_event_bus_subscribe(
        self,
        mock_event_bus,
    ):
        """Given 事件处理器，When 订阅，Then 成功注册"""
        # Arrange
        event_type = "plan.created"

        async def handler(event):
            pass

        # Act
        await mock_event_bus.subscribe(event_type, handler)

        # Assert
        mock_event_bus.subscribe.assert_called_once_with(event_type, handler)

    @pytest.mark.asyncio
    async def test_event_bus_unsubscribe(
        self,
        mock_event_bus,
    ):
        """Given 订阅的处理器，When 取消订阅，Then 成功移除"""
        # Arrange
        event_type = "plan.created"

        async def handler(event):
            pass

        # Act
        await mock_event_bus.unsubscribe(event_type, handler)

        # Assert
        mock_event_bus.unsubscribe.assert_called_once_with(event_type, handler)


class TestLLMRouterUnit:
    """LLM 路由器单元测试"""

    @pytest.mark.asyncio
    async def test_llm_router_selects_model(
        self,
        mock_llm_router,
    ):
        """Given 路由请求，When 执行路由，Then 返回选定的模型"""
        # Act
        result = await mock_llm_router.route()

        # Assert
        assert result["selected_model"] == "ollama/qwen2.5-7b"
        assert result["estimated_cost"] == 0.001
        assert result["estimated_latency"] == 500
        mock_llm_router.route.assert_called_once()


class TestEventBusImplementation:
    """事件总线实现测试"""

    @pytest.mark.asyncio
    async def test_event_bus_publish(self):
        """Given 事件数据，When 发布，Then 不抛出异常"""
        # Arrange
        from src.infrastructure.event_bus import EventBus

        event_bus = EventBus()

        # Act & Assert
        await event_bus.publish("plan.created", {"plan_id": "test-123"})
        # 不抛出异常即为通过

    @pytest.mark.asyncio
    async def test_event_bus_subscribe(self):
        """Given 事件处理器，When 订阅，Then 不抛出异常"""
        # Arrange
        from src.infrastructure.event_bus import EventBus

        event_bus = EventBus()

        async def handler(event):
            pass

        # Act & Assert
        await event_bus.subscribe("plan.created", handler)
        # 不抛出异常即为通过

    @pytest.mark.asyncio
    async def test_event_bus_unsubscribe(self):
        """Given 订阅的处理器，When 取消订阅，Then 不抛出异常"""
        # Arrange
        from src.infrastructure.event_bus import EventBus

        event_bus = EventBus()

        async def handler(event):
            pass

        # Act & Assert
        await event_bus.unsubscribe("plan.created", handler)
        # 不抛出异常即为通过


class TestPlanRepositoryProtocol:
    """PlanRepository 协议测试（验证接口定义）"""

    def test_repository_protocol_defined(self):
        """Given PlanRepository 协议，When 检查，Then 定义所有必需方法"""
        # Arrange
        from src.domain.repositories.plan_repository import PlanRepository

        # Act & Assert
        assert hasattr(PlanRepository, "get_by_id")
        assert hasattr(PlanRepository, "find_all")
        assert hasattr(PlanRepository, "add")
        assert hasattr(PlanRepository, "update")
        assert hasattr(PlanRepository, "delete")
