"""Story 4.4: SandboxSession 聚合根单元测试

验证 SandboxSession 10 字段 + session_id 正则 + 终态不变量。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.domain.entities.sandbox_session import (
    SESSION_ID_REGEX,
    SandboxSession,
)
from src.domain.exceptions import (
    EntityBusinessRuleError,
    EntityValidationError,
)


def _make_sandbox_session(**overrides: object) -> SandboxSession:
    """工厂函数:创建 SandboxSession 默认实例"""
    defaults: dict[str, object] = {
        "session_id": "sess-abc123def456",
        "tenant_id": uuid.uuid4(),
        "image_digest": "python:3.11-slim@sha256:abc",
    }
    defaults.update(overrides)
    return SandboxSession(**defaults)  # type: ignore[arg-type]


class TestSandboxSessionFields:
    """SandboxSession 字段完整性测试（10 字段）"""

    def test_default_state_is_running(self) -> None:
        """state 默认 'RUNNING'"""
        session = _make_sandbox_session()
        assert session.state == "RUNNING"

    def test_default_state_version_is_zero(self) -> None:
        """state_version 默认 0"""
        session = _make_sandbox_session()
        assert session.state_version == 0

    def test_default_container_id_is_none(self) -> None:
        """container_id 默认 None"""
        session = _make_sandbox_session()
        assert session.container_id is None

    def test_total_fields_count_is_10(self) -> None:
        """总字段数应为 10"""
        import dataclasses

        fields = dataclasses.fields(SandboxSession)
        assert len(fields) == 10

    def test_session_id_preserved(self) -> None:
        """session_id 应正确传递"""
        session = _make_sandbox_session(session_id="my-session-001")
        assert session.session_id == "my-session-001"


class TestSandboxSessionInvariants:
    """SandboxSession 字段不变量校验测试"""

    def test_session_id_invalid_chars_raises(self) -> None:
        """session_id 包含非法字符抛 EntityValidationError"""
        with pytest.raises(EntityValidationError):
            _make_sandbox_session(session_id="invalid session!")

    def test_session_id_too_long_raises(self) -> None:
        """session_id > 64 字符抛 EntityValidationError"""
        long_id = "a" * 65
        with pytest.raises(EntityValidationError):
            _make_sandbox_session(session_id=long_id)

    def test_session_id_empty_raises(self) -> None:
        """session_id 空字符串抛 EntityValidationError"""
        with pytest.raises(EntityValidationError):
            _make_sandbox_session(session_id="")

    def test_session_id_at_upper_boundary_ok(self) -> None:
        """session_id == 64 字符边界值应通过"""
        session = _make_sandbox_session(session_id="a" * 64)
        assert len(session.session_id) == 64

    def test_session_id_with_underscore_ok(self) -> None:
        """session_id 含下划线应通过"""
        session = _make_sandbox_session(session_id="sess_abc_123")
        assert session.session_id == "sess_abc_123"

    def test_session_id_with_dash_ok(self) -> None:
        """session_id 含连字符应通过"""
        session = _make_sandbox_session(session_id="sess-abc-123")
        assert session.session_id == "sess-abc-123"

    def test_terminated_state_without_terminated_at_raises(self) -> None:
        """TERMINATED 状态但 terminated_at 未设置抛 EntityBusinessRuleError"""
        with pytest.raises(EntityBusinessRuleError):
            SandboxSession(
                session_id="sess-001",
                tenant_id=uuid.uuid4(),
                state="TERMINATED",
                terminated_at=None,
            )

    def test_failed_state_without_terminated_at_raises(self) -> None:
        """FAILED 状态但 terminated_at 未设置抛 EntityBusinessRuleError"""
        with pytest.raises(EntityBusinessRuleError):
            SandboxSession(
                session_id="sess-001",
                tenant_id=uuid.uuid4(),
                state="FAILED",
                terminated_at=None,
            )

    def test_terminated_state_with_terminated_at_ok(self) -> None:
        """TERMINATED 状态 + terminated_at 应通过"""
        now = datetime.now(UTC)
        session = SandboxSession(
            session_id="sess-001",
            tenant_id=uuid.uuid4(),
            state="TERMINATED",
            terminated_at=now,
        )
        assert session.terminated_at == now


class TestSandboxSessionIsIdle:
    """SandboxSession.is_idle 测试"""

    def test_running_session_with_old_activity_is_idle(self) -> None:
        """RUNNING 状态 + last_activity_at 早于阈值 → 空闲"""
        old = datetime.now(UTC) - timedelta(minutes=45)
        session = _make_sandbox_session(last_activity_at=old)
        threshold = datetime.now(UTC) - timedelta(minutes=30)
        assert session.is_idle(threshold) is True

    def test_running_session_with_recent_activity_is_not_idle(self) -> None:
        """RUNNING 状态 + last_activity_at 晚于阈值 → 非空闲"""
        recent = datetime.now(UTC) - timedelta(minutes=5)
        session = _make_sandbox_session(last_activity_at=recent)
        threshold = datetime.now(UTC) - timedelta(minutes=30)
        assert session.is_idle(threshold) is False

    def test_terminated_session_is_not_idle(self) -> None:
        """TERMINATED 状态 → 非空闲"""
        old = datetime.now(UTC) - timedelta(hours=1)
        now = datetime.now(UTC)
        session = _make_sandbox_session(
            state="TERMINATED",
            last_activity_at=old,
            terminated_at=now,
        )
        threshold = datetime.now(UTC) - timedelta(minutes=30)
        assert session.is_idle(threshold) is False


class TestSandboxSessionWithActivityUpdated:
    """SandboxSession.with_activity_updated 测试"""

    def test_with_activity_updated_increments_state_version(self) -> None:
        """with_activity_updated 应递增 state_version"""
        session = _make_sandbox_session()
        assert session.state_version == 0
        updated = session.with_activity_updated()
        assert updated.state_version == 1

    def test_with_activity_updated_preserves_session_id(self) -> None:
        """with_activity_updated 应保留 session_id 不变"""
        session = _make_sandbox_session(session_id="sess-001")
        updated = session.with_activity_updated()
        assert updated.session_id == "sess-001"

    def test_with_activity_updated_returns_new_instance(self) -> None:
        """with_activity_updated 应返回新实例(frozen)"""
        session = _make_sandbox_session()
        updated = session.with_activity_updated()
        assert updated is not session


class TestSandboxSessionWithTerminated:
    """SandboxSession.with_terminated 测试"""

    def test_with_terminated_sets_terminated_state(self) -> None:
        """with_terminated 应设置 state='TERMINATED'"""
        session = _make_sandbox_session()
        terminated = session.with_terminated()
        assert terminated.state == "TERMINATED"
        assert terminated.terminated_at is not None

    def test_with_terminated_increments_state_version(self) -> None:
        """with_terminated 应递增 state_version"""
        session = _make_sandbox_session()
        terminated = session.with_terminated()
        assert terminated.state_version == 1


class TestSandboxSessionRegexConstant:
    """SESSION_ID_REGEX 常量测试"""

    def test_session_id_regex_pattern(self) -> None:
        """SESSION_ID_REGEX pattern 应为 ^[A-Za-z0-9_-]{1,64}$"""
        assert SESSION_ID_REGEX.pattern == r"^[A-Za-z0-9_-]{1,64}$"

    def test_session_id_regex_matches_valid(self) -> None:
        """SESSION_ID_REGEX 应匹配合法 session_id"""
        assert SESSION_ID_REGEX.match("abc-123_xyz")
        assert SESSION_ID_REGEX.match("a")
        assert SESSION_ID_REGEX.match("a" * 64)

    def test_session_id_regex_rejects_invalid(self) -> None:
        """SESSION_ID_REGEX 应拒绝非法 session_id"""
        assert not SESSION_ID_REGEX.match("a" * 65)
        assert not SESSION_ID_REGEX.match("")
        assert not SESSION_ID_REGEX.match("invalid id with space")
        assert not SESSION_ID_REGEX.match("invalid@id")
