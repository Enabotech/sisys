"""Tests for ChannelRouter."""

from __future__ import annotations

from src.infrastructure.messaging.channel_router import (
    ChannelMapping,
    ChannelRouter,
    DeliveryMode,
)


class TestDeliveryModeEnum:
    """Test DeliveryMode enum values."""

    def test_realtime_value(self) -> None:
        """DeliveryMode.REALTIME should have correct value."""
        assert DeliveryMode.REALTIME.value == "realtime"

    def test_reliable_value(self) -> None:
        """DeliveryMode.RELIABLE should have correct value."""
        assert DeliveryMode.RELIABLE.value == "reliable"


class TestChannelMapping:
    """Test ChannelMapping dataclass."""

    def test_default_delivery_mode_is_reliable(self) -> None:
        """Default delivery mode should be RELIABLE."""
        mapping = ChannelMapping(event_type="TestEvent")
        assert mapping.delivery_mode == DeliveryMode.RELIABLE

    def test_all_fields_optional_except_event_type(self) -> None:
        """Only event_type is required, others have defaults."""
        mapping = ChannelMapping(event_type="TestEvent")
        assert mapping.event_type == "TestEvent"
        assert mapping.redis_channel is None
        assert mapping.rabbitmq_routing_key is None
        assert mapping.description == ""


class TestChannelRouterDefaults:
    """Test ChannelRouter default mappings."""

    def test_creates_with_defaults_by_default(self) -> None:
        """ChannelRouter should load default mappings by default."""
        router = ChannelRouter()
        # Should have default mappings loaded
        assert router.get_delivery_mode("AutoTriggered") == DeliveryMode.REALTIME
        assert router.get_delivery_mode("DocumentProcessed") == DeliveryMode.RELIABLE

    def test_creates_without_defaults_when_specified(self) -> None:
        """ChannelRouter should not load defaults when load_defaults=False."""
        router = ChannelRouter(load_defaults=False)
        # Should not have default mappings
        assert router.get_delivery_mode("AutoTriggered") == DeliveryMode.RELIABLE  # defaults to reliable


class TestChannelRouterGetDeliveryMode:
    """Test get_delivery_mode method."""

    def test_returns_configured_mode(self) -> None:
        """Should return the configured delivery mode."""
        router = ChannelRouter()
        assert router.get_delivery_mode("AutoTriggered") == DeliveryMode.REALTIME
        assert router.get_delivery_mode("DocumentProcessed") == DeliveryMode.RELIABLE

    def test_returns_reliable_for_unknown_event_type(self) -> None:
        """Unknown event types should default to RELIABLE."""
        router = ChannelRouter()
        assert router.get_delivery_mode("UnknownEvent") == DeliveryMode.RELIABLE


class TestChannelRouterSetOverride:
    """Test set_override method."""

    def test_override_changes_delivery_mode(self) -> None:
        """set_override should change delivery mode for an event type."""
        router = ChannelRouter()
        # DocumentProcessed is RELIABLE by default
        assert router.get_delivery_mode("DocumentProcessed") == DeliveryMode.RELIABLE
        # Override to REALTIME
        router.set_override("DocumentProcessed", DeliveryMode.REALTIME)
        assert router.get_delivery_mode("DocumentProcessed") == DeliveryMode.REALTIME


class TestChannelRouterRegister:
    """Test register method."""

    def test_register_adds_mapping(self) -> None:
        """register should add a new channel mapping."""
        router = ChannelRouter(load_defaults=False)
        mapping = ChannelMapping(
            event_type="NewEvent",
            redis_channel="test:channel",
            delivery_mode=DeliveryMode.REALTIME,
        )
        router.register(mapping)
        assert router.get_delivery_mode("NewEvent") == DeliveryMode.REALTIME

    def test_register_overwrites_existing_mapping(self) -> None:
        """register should overwrite existing mapping."""
        router = ChannelRouter()
        # AutoTriggered is REALTIME by default
        assert router.get_delivery_mode("AutoTriggered") == DeliveryMode.REALTIME
        # Register override
        new_mapping = ChannelMapping(
            event_type="AutoTriggered",
            delivery_mode=DeliveryMode.RELIABLE,
        )
        router.register(new_mapping)
        assert router.get_delivery_mode("AutoTriggered") == DeliveryMode.RELIABLE


class TestChannelRouterQueryMethods:
    """Test get_redis_channel and get_rabbitmq_routing_key methods."""

    def test_get_redis_channel_returns_configured_channel(self) -> None:
        """Should return configured Redis channel."""
        router = ChannelRouter()
        assert router.get_redis_channel("AutoTriggered") == "sisys:rt:auto_triggered"

    def test_get_redis_channel_returns_none_for_unknown(self) -> None:
        """Should return None for unknown event types."""
        router = ChannelRouter()
        assert router.get_redis_channel("UnknownEvent") is None

    def test_get_redis_channel_returns_none_when_not_configured(self) -> None:
        """Should return None when event type has no Redis channel."""
        router = ChannelRouter()
        # MemoryChanged has no Redis channel
        assert router.get_redis_channel("MemoryChanged") is None

    def test_get_rabbitmq_routing_key_returns_configured_key(self) -> None:
        """Should return configured RabbitMQ routing key."""
        router = ChannelRouter()
        assert router.get_rabbitmq_routing_key("MemoryChanged") == "sisys.events.reliable.memory_changed"

    def test_get_rabbitmq_routing_key_returns_none_for_unknown(self) -> None:
        """Should return None for unknown event types."""
        router = ChannelRouter()
        assert router.get_rabbitmq_routing_key("UnknownEvent") is None

    def test_get_rabbitmq_routing_key_returns_none_when_not_configured(self) -> None:
        """Should return None when event type has no RabbitMQ routing key."""
        router = ChannelRouter()
        # AutoTriggered has no RabbitMQ routing key
        assert router.get_rabbitmq_routing_key("AutoTriggered") is None


class TestChannelRouterGetMapping:
    """Test get_mapping method."""

    def test_get_mapping_returns_channel_mapping(self) -> None:
        """Should return the ChannelMapping for an event type."""
        router = ChannelRouter()
        mapping = router.get_mapping("AutoTriggered")
        assert mapping is not None
        assert mapping.event_type == "AutoTriggered"
        assert mapping.redis_channel == "sisys:rt:auto_triggered"

    def test_get_mapping_returns_none_for_unknown(self) -> None:
        """Should return None for unknown event types."""
        router = ChannelRouter()
        assert router.get_mapping("UnknownEvent") is None


class TestChannelRouterCreateForTesting:
    """Test create_for_testing class method."""

    def test_creates_router_without_defaults(self) -> None:
        """create_for_testing should create router without defaults."""
        router = ChannelRouter.create_for_testing()
        assert router.get_delivery_mode("AutoTriggered") == DeliveryMode.RELIABLE


class TestWorkflowSubmittedChannelMapping:
    """Test WorkflowSubmitted event channel registration."""

    def test_workflow_submitted_in_default_mappings(self) -> None:
        """WorkflowSubmitted 应在 DEFAULT_MAPPINGS 中注册"""
        from src.infrastructure.messaging.channel_router import ChannelRouter

        assert "WorkflowSubmitted" in ChannelRouter.DEFAULT_MAPPINGS
        mapping = ChannelRouter.DEFAULT_MAPPINGS["WorkflowSubmitted"]
        assert mapping.event_type == "WorkflowSubmitted"

    def test_workflow_submitted_delivery_mode_is_reliable(self) -> None:
        """WorkflowSubmitted 通道策略应为 RELIABLE"""
        from src.infrastructure.messaging.channel_router import ChannelRouter, DeliveryMode

        mapping = ChannelRouter.DEFAULT_MAPPINGS["WorkflowSubmitted"]
        assert mapping.delivery_mode == DeliveryMode.RELIABLE

    def test_workflow_submitted_rabbitmq_routing_key(self) -> None:
        """WorkflowSubmitted 应配置 RabbitMQ routing key"""
        from src.infrastructure.messaging.channel_router import ChannelRouter

        mapping = ChannelRouter.DEFAULT_MAPPINGS["WorkflowSubmitted"]
        assert mapping.rabbitmq_routing_key == "sisys.events.reliable.workflow_submitted"

    def test_router_returns_workflow_submitted_mapping(self) -> None:
        """ChannelRouter 应返回 WorkflowSubmitted 的映射"""
        router = ChannelRouter()
        mapping = router.get_mapping("WorkflowSubmitted")
        assert mapping is not None
        assert mapping.event_type == "WorkflowSubmitted"
        assert mapping.delivery_mode == DeliveryMode.RELIABLE
