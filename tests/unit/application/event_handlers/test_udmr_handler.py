"""Unit tests for UDMRHandler.

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.event_handlers.udmr_handler import UDMRHandler
from src.domain.events.auto_route_events import AutoRouted
from src.domain.events.routing_events import RoutingDecided


@pytest.fixture
def mock_udmr_service() -> AsyncMock:
    """Mock UDMRService."""
    svc = AsyncMock()
    svc.decide.return_value = RoutingDecided(
        task_id=uuid.uuid4(),
        route_type="cloud",
        selected_model="MiniMax-M2.7",
    )
    return svc


@pytest.fixture
def mock_event_bus() -> AsyncMock:
    """Mock DualChannelEventBus (EventSubscriber)."""
    bus = AsyncMock()
    bus.subscribe_async.return_value = None
    bus.start.return_value = None
    bus.close.return_value = None
    return bus


@pytest.fixture
def handler(
    mock_udmr_service: AsyncMock,
    mock_event_bus: AsyncMock,
) -> UDMRHandler:
    """构造 UDMRHandler 实例."""
    return UDMRHandler(
        udmr_service=mock_udmr_service,
        event_bus=mock_event_bus,
        enabled=True,
    )


# ===================================================================
# 初始化测试
# ===================================================================


class TestUDMRHandlerInit:
    """初始化测试."""

    def test_init_with_service_and_bus(
        self,
        mock_udmr_service: AsyncMock,
        mock_event_bus: AsyncMock,
    ) -> None:
        """应正确存储服务引用."""
        h = UDMRHandler(mock_udmr_service, mock_event_bus, enabled=True)
        assert h._udmr_service is mock_udmr_service

    def test_init_disabled(
        self,
        mock_udmr_service: AsyncMock,
        mock_event_bus: AsyncMock,
    ) -> None:
        """disabled 时 enabled=False."""
        h = UDMRHandler(mock_udmr_service, mock_event_bus, enabled=False)
        assert h._enabled is False


# ===================================================================
# on_routed 测试
# ===================================================================


class TestUDMRHandlerOnRouted:
    """on_routed() 测试."""

    async def test_on_routed_calls_decide(
        self,
        handler: UDMRHandler,
        mock_udmr_service: AsyncMock,
    ) -> None:
        """on_routed 应调用 UDMRService.decide()."""
        event = AutoRouted(
            session_id="session-123",
            task_context={"input": "test"},
            route_type="hash",
            route_target="agent-1",
        )
        await handler.on_routed(event)
        mock_udmr_service.decide.assert_called_once()

    async def test_on_routed_disabled_skips(
        self,
        mock_udmr_service: AsyncMock,
        mock_event_bus: AsyncMock,
    ) -> None:
        """disabled 时跳过处理."""
        h = UDMRHandler(mock_udmr_service, mock_event_bus, enabled=False)
        event = AutoRouted(session_id="session-123", task_context={})
        await h.on_routed(event)
        mock_udmr_service.decide.assert_not_called()

    async def test_on_routed_non_auto_routed_skips(
        self,
        handler: UDMRHandler,
        mock_udmr_service: AsyncMock,
    ) -> None:
        """非 AutoRouted 事件跳过."""
        event = MagicMock()
        await handler.on_routed(event)
        mock_udmr_service.decide.assert_not_called()

    async def test_on_routed_task_context_extraction(
        self,
        handler: UDMRHandler,
        mock_udmr_service: AsyncMock,
    ) -> None:
        """应从 task_context 提取字段."""
        event = AutoRouted(
            session_id="session-123",
            task_context={
                "input": "test input",
                "data_residency": "OVERSEAS",
            },
            route_type="hash",
        )
        await handler.on_routed(event)
        task_arg = mock_udmr_service.decide.call_args[0][0]
        assert task_arg.input == "test input"
        assert task_arg.data_residency == "OVERSEAS"


# ===================================================================
# register 测试
# ===================================================================


class TestUDMRHandlerRegister:
    """register() 测试."""

    async def test_register_calls_subscribe_async(
        self,
        handler: UDMRHandler,
        mock_event_bus: AsyncMock,
    ) -> None:
        """register() 应调用 subscribe_async."""
        await handler.register()
        mock_event_bus.subscribe_async.assert_called_once_with("AutoRouted", handler.on_routed)
