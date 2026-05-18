"""Unit tests for AutoRouteService — domain service for routing decisions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.events.auto_route_events import AutoRouted
from src.domain.events.auto_trigger_events import AutoTriggered
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.hash_router_protocol import HashRouterProtocol
from src.domain.ports.semantic_router_protocol import SemanticRouterProtocol
from src.domain.services.auto_route_service import AutoRouteService


class TestAutoRouteService:
    """Test suite for AutoRouteService."""

    @pytest.fixture
    def mock_publisher(self) -> AsyncMock:
        """Create mock event publisher."""
        return AsyncMock()

    @pytest.fixture
    def mock_hash_router(self) -> MagicMock:
        """Create mock hash router."""
        router = MagicMock(spec=HashRouterProtocol)
        router.route.return_value = "node-A"
        return router

    @pytest.fixture
    def mock_semantic_router(self) -> AsyncMock:
        """Create mock semantic router."""
        router = AsyncMock(spec=SemanticRouterProtocol)
        router.route.return_value = ("cfo-agent", 0.95)
        return router

    @pytest.fixture
    def route_service(
        self,
        mock_publisher: AsyncMock,
        mock_hash_router: MagicMock,
        mock_semantic_router: AsyncMock,
    ) -> AutoRouteService:
        """Create AutoRouteService with mocks."""
        return AutoRouteService(
            publisher=mock_publisher,
            hash_router=mock_hash_router,
            semantic_router=mock_semantic_router,
        )

    @pytest.mark.asyncio
    async def test_on_triggered_event_publishes_routed(
        self,
        route_service: AutoRouteService,
        mock_publisher: AsyncMock,
    ) -> None:
        """AutoRouteService should publish AutoRouted event when receiving AutoTriggered event."""
        triggered = AutoTriggered(
            session_id="session-123",
            task_context={"task_type": "financial_analysis"},
        )

        result = await route_service.on_triggered_event(triggered)

        assert result is not None
        assert isinstance(result, AutoRouted)
        assert result.session_id == "session-123"
        mock_publisher.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_triggered_event_with_hash_router(
        self,
        mock_hash_router: MagicMock,
        mock_semantic_router: AsyncMock,
        mock_publisher: AsyncMock,
    ) -> None:
        """AutoRouteService should use hash router for session consistency."""
        hash_router = MagicMock(spec=HashRouterProtocol)
        hash_router.route.return_value = "node-A"

        semantic_router = AsyncMock(spec=SemanticRouterProtocol)
        semantic_router.route.return_value = ("", 0.0)  # No semantic routing

        route_service = AutoRouteService(
            publisher=mock_publisher,
            hash_router=hash_router,
            semantic_router=semantic_router,
        )

        triggered = AutoTriggered(
            session_id="session-hash-test",
            task_context={},
        )

        result = await route_service.on_triggered_event(triggered)

        assert result is not None
        assert result.route_type == "hash"
        assert result.route_target == "node-A"
        assert result.route_score == 1.0

    @pytest.mark.asyncio
    async def test_on_triggered_event_with_semantic_router(
        self,
        mock_hash_router: MagicMock,
        mock_semantic_router: AsyncMock,
        mock_publisher: AsyncMock,
    ) -> None:
        """AutoRouteService should use semantic router when available."""
        hash_router = MagicMock(spec=HashRouterProtocol)
        hash_router.route.return_value = "node-A"

        semantic_router = AsyncMock(spec=SemanticRouterProtocol)
        semantic_router.route.return_value = ("cfo-agent", 0.95)

        route_service = AutoRouteService(
            publisher=mock_publisher,
            hash_router=hash_router,
            semantic_router=semantic_router,
        )

        triggered = AutoTriggered(
            session_id="session-semantic-test",
            task_context={"task_type": "financial"},
        )

        result = await route_service.on_triggered_event(triggered)

        assert result is not None
        assert result.route_type in ("semantic", "mixed")
        assert result.route_target == "cfo-agent"
        assert result.route_score == 0.95

    @pytest.mark.asyncio
    async def test_on_triggered_event_no_publisher(
        self,
        mock_hash_router: MagicMock,
        mock_semantic_router: AsyncMock,
    ) -> None:
        """AutoRouteService without publisher should not raise, just log warning."""
        route_service = AutoRouteService(
            publisher=None,
            hash_router=mock_hash_router,
            semantic_router=mock_semantic_router,
        )

        triggered = AutoTriggered(
            session_id="session-no-pub",
            task_context={},
        )

        # Should not raise, just return the event without publishing
        result = await route_service.on_triggered_event(triggered)
        assert result is not None

    @pytest.mark.asyncio
    async def test_on_triggered_event_mixed_routing(
        self,
        mock_publisher: AsyncMock,
    ) -> None:
        """AutoRouteService with both routers should prefer higher score (mixed mode)."""
        hash_router = MagicMock(spec=HashRouterProtocol)
        hash_router.route.return_value = "node-A"

        semantic_router = AsyncMock(spec=SemanticRouterProtocol)
        semantic_router.route.return_value = ("cfo-agent", 0.95)  # Higher score

        route_service = AutoRouteService(
            publisher=mock_publisher,
            hash_router=hash_router,
            semantic_router=semantic_router,
        )

        triggered = AutoTriggered(
            session_id="session-mixed",
            task_context={"task_type": "financial"},
        )

        result = await route_service.on_triggered_event(triggered)

        assert result is not None
        assert result.route_type == "mixed"
        assert result.route_score == 0.95

    @pytest.mark.asyncio
    async def test_on_triggered_event_no_routers(
        self,
        mock_publisher: AsyncMock,
    ) -> None:
        """AutoRouteService without routers should use defaults."""
        route_service = AutoRouteService(publisher=mock_publisher)

        triggered = AutoTriggered(
            session_id="session-no-routers",
            task_context={},
        )

        result = await route_service.on_triggered_event(triggered)

        assert result is not None
        assert result.route_type == "hash"
        assert result.route_target == "default"
        assert result.route_score == 0.0

    def test_route_service_initialization(self) -> None:
        """AutoRouteService should initialize with all dependencies."""
        publisher = AsyncMock(spec=EventPublisher)
        hash_router = MagicMock(spec=HashRouterProtocol)
        semantic_router = AsyncMock(spec=SemanticRouterProtocol)

        service = AutoRouteService(
            publisher=publisher,
            hash_router=hash_router,
            semantic_router=semantic_router,
        )

        assert service._publisher is publisher
        assert service._hash_router is hash_router
        assert service._semantic_router is semantic_router

    def test_route_service_with_none_dependencies(self) -> None:
        """AutoRouteService should handle None dependencies gracefully."""
        service = AutoRouteService(publisher=None)

        assert service._publisher is None
        assert service._hash_router is None
        assert service._semantic_router is None

    @pytest.mark.asyncio
    async def test_on_triggered_event_publisher_exception(
        self,
        mock_hash_router: MagicMock,
    ) -> None:
        """AutoRouteService should propagate exception when publisher fails."""
        mock_publisher = AsyncMock()
        mock_publisher.publish.side_effect = RuntimeError("Publisher failed")

        route_service = AutoRouteService(
            publisher=mock_publisher,
            hash_router=mock_hash_router,
        )

        triggered = AutoTriggered(
            session_id="session-pub-error",
            task_context={},
        )

        with pytest.raises(RuntimeError, match="Publisher failed"):
            await route_service.on_triggered_event(triggered)
