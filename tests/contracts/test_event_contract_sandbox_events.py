"""Story 4.4: 沙箱事件契约测试

验证 SandboxSessionStarted / SandboxSessionTerminated / SandboxExecutionFailed 事件的：
- 字段完整性（必填字段、默认值）
- 继承 DomainEvent 基类
- 序列化 roundtrip
- 双通道配置（reliable + redis_channel + rabbitmq_routing_key）

参考样板：tests/contracts/test_event_contract_tool_executed.py
"""

from __future__ import annotations

import uuid

import pytest

from src.domain.events.sandbox_events import (
    SandboxExecutionFailed,
    SandboxSessionStarted,
    SandboxSessionTerminated,
)
from src.infrastructure.messaging.channel_router import (
    ChannelRouter,
    DeliveryMode,
)


class TestSandboxSessionStartedEventSchema:
    """SandboxSessionStarted 事件 Schema 完整性测试"""

    def _make_event(self) -> SandboxSessionStarted:
        """创建标准 SandboxSessionStarted 事件实例"""
        return SandboxSessionStarted(
            session_id="test-session-1234567890abcdef",
            container_id="abc123def456",
            image_digest="python:3.11-slim@sha256:62dad7dd96e602c9e08c7724e50333b1834c4f2b6dbc5f8b7c97c39293fe2bdd",
            resource_limits={"mem_limit_mb": 512, "cpu_quota": 1.0, "pids_limit": 256},
        )

    def test_event_type_is_sandbox_session_started(self) -> None:
        """事件类型固定为 SandboxSessionStarted"""
        event = self._make_event()
        assert event.event_type == "SandboxSessionStarted"

    def test_event_inherits_domain_event_fields(self) -> None:
        """事件应继承 DomainEvent 所有核心字段"""
        from src.domain.events.base import DomainEvent

        event = self._make_event()
        assert isinstance(event, DomainEvent)
        assert hasattr(event, "event_id")
        assert hasattr(event, "timestamp")
        assert hasattr(event, "source")
        assert hasattr(event, "schema_version")
        assert hasattr(event, "aggregate_id")
        assert hasattr(event, "aggregate_type")

    def test_event_has_all_subclass_fields(self) -> None:
        """事件应包含所有子类特有字段"""
        event = self._make_event()
        assert event.session_id == "test-session-1234567890abcdef"
        assert event.container_id == "abc123def456"
        assert event.image_digest.startswith("python:3.11-slim@sha256:")
        assert event.resource_limits["mem_limit_mb"] == 512

    def test_aggregate_type_is_sandbox_session(self) -> None:
        """aggregate_type 应为 SandboxSession"""
        event = self._make_event()
        assert event.aggregate_type == "SandboxSession"

    def test_session_id_in_metadata(self) -> None:
        """session_id 应通过 metadata 字典透传（与 aggregate_id UUID 分离）"""
        event = self._make_event()
        assert event.metadata.get("session_id") == "test-session-1234567890abcdef"

    def test_event_is_frozen(self) -> None:
        """frozen dataclass 应不可变"""
        event = self._make_event()
        with pytest.raises(AttributeError):
            setattr(event, "session_id", "modified")


class TestSandboxSessionTerminatedEventSchema:
    """SandboxSessionTerminated 事件 Schema 完整性测试"""

    def _make_event(self) -> SandboxSessionTerminated:
        """创建标准 SandboxSessionTerminated 事件实例"""
        return SandboxSessionTerminated(
            session_id="test-session-1234567890abcdef",
            container_id="abc123def456",
            termination_reason="idle_timeout",
            duration_sec=1800.5,
        )

    def test_event_type_is_sandbox_session_terminated(self) -> None:
        """事件类型固定为 SandboxSessionTerminated"""
        event = self._make_event()
        assert event.event_type == "SandboxSessionTerminated"

    def test_termination_reason_preserved(self) -> None:
        """终止原因字段应正确传递"""
        event = self._make_event()
        assert event.termination_reason == "idle_timeout"
        assert event.duration_sec == 1800.5

    def test_event_inherits_domain_event(self) -> None:
        """事件应继承 DomainEvent"""
        from src.domain.events.base import DomainEvent

        event = self._make_event()
        assert isinstance(event, DomainEvent)


class TestSandboxExecutionFailedEventSchema:
    """SandboxExecutionFailed 事件 Schema 完整性测试"""

    def _make_event(self) -> SandboxExecutionFailed:
        """创建标准 SandboxExecutionFailed 事件实例"""
        return SandboxExecutionFailed(
            session_id="test-session-1234567890abcdef",
            execution_id=str(uuid.uuid4()),
            error_code="EXCEPTION_316",
            error_message="Sandbox execution timeout",
            stderr="Traceback (most recent call last):\n  ...",
        )

    def test_event_type_is_sandbox_execution_failed(self) -> None:
        """事件类型固定为 SandboxExecutionFailed"""
        event = self._make_event()
        assert event.event_type == "SandboxExecutionFailed"

    def test_error_fields_preserved(self) -> None:
        """错误字段应正确传递"""
        event = self._make_event()
        assert event.error_code == "EXCEPTION_316"
        assert event.error_message == "Sandbox execution timeout"
        assert "Traceback" in event.stderr

    def test_event_inherits_domain_event(self) -> None:
        """事件应继承 DomainEvent"""
        from src.domain.events.base import DomainEvent

        event = self._make_event()
        assert isinstance(event, DomainEvent)


class TestSandboxEventSerialization:
    """沙箱事件序列化 roundtrip 测试"""

    def test_session_started_to_from_dict_roundtrip(self) -> None:
        """SandboxSessionStarted 序列化 roundtrip"""
        event = SandboxSessionStarted(
            session_id="sess-abc123",
            container_id="container-xyz",
            image_digest="python:3.11-slim@sha256:abc",
            resource_limits={"mem_limit_mb": 256},
        )
        data = event.to_dict()
        assert data["event_type"] == "SandboxSessionStarted"
        assert data["payload"]["session_id"] == "sess-abc123"
        assert data["payload"]["container_id"] == "container-xyz"

    def test_session_terminated_to_dict(self) -> None:
        """SandboxSessionTerminated to_dict 包含终止信息"""
        event = SandboxSessionTerminated(
            session_id="sess-abc123",
            container_id="container-xyz",
            termination_reason="explicit_stop",
            duration_sec=120.5,
        )
        data = event.to_dict()
        assert data["payload"]["termination_reason"] == "explicit_stop"
        assert data["payload"]["duration_sec"] == 120.5

    def test_execution_failed_to_dict(self) -> None:
        """SandboxExecutionFailed to_dict 包含错误信息"""
        event = SandboxExecutionFailed(
            session_id="sess-abc123",
            execution_id="exec-001",
            error_code="EXCEPTION_317",
            error_message="Memory limit exceeded",
            stderr="Killed",
        )
        data = event.to_dict()
        assert data["payload"]["error_code"] == "EXCEPTION_317"
        assert data["payload"]["stderr"] == "Killed"


class TestSandboxEventChannelMapping:
    """沙箱事件双通道（reliable）配置验证"""

    @pytest.mark.parametrize(
        "event_type,expected_redis,expected_rabbit",
        [
            (
                "SandboxSessionStarted",
                "sisys:rt:sandbox.session.started",
                "sisys.events.reliable.sandbox.session.started",
            ),
            (
                "SandboxSessionTerminated",
                "sisys:rt:sandbox.session.terminated",
                "sisys.events.reliable.sandbox.session.terminated",
            ),
            (
                "SandboxExecutionFailed",
                "sisys:rt:sandbox.execution.failed",
                "sisys.events.reliable.sandbox.execution.failed",
            ),
        ],
    )
    def test_event_has_reliable_channel_mapping(self, event_type: str, expected_redis: str, expected_rabbit: str) -> None:
        """3 个沙箱事件均应注册为双通道（realtime + reliable）"""
        mapping = ChannelRouter.DEFAULT_MAPPINGS.get(event_type)
        assert mapping is not None, f"{event_type} 未在 ChannelRouter.DEFAULT_MAPPINGS 中注册"
        assert mapping.delivery_mode == DeliveryMode.RELIABLE
        assert mapping.redis_channel == expected_redis
        assert mapping.rabbitmq_routing_key == expected_rabbit
