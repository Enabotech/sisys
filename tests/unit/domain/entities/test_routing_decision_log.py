"""Unit tests for RoutingDecisionLog domain entity."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest

from src.domain.entities.routing_decision_log import RoutingDecisionLog


class TestRoutingDecisionLog:
    """Test suite for RoutingDecisionLog."""

    def test_create_valid_log(self) -> None:
        """Should create a valid routing decision log."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
        )
        log.validate()

    def test_validate_log_id_must_be_uuid(self) -> None:
        """Should raise if log_id is not a UUID."""
        log = RoutingDecisionLog(
            log_id=cast(uuid.UUID, "not-a-uuid"),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
        )
        with pytest.raises(ValueError, match="log_id must be a valid UUID"):
            log.validate()

    def test_validate_task_id_empty(self) -> None:
        """Should raise if task_id is empty."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
        )
        with pytest.raises(ValueError, match="task_id must not be empty"):
            log.validate()

    def test_validate_session_id_empty(self) -> None:
        """Should raise if session_id is empty."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
        )
        with pytest.raises(ValueError, match="session_id must not be empty"):
            log.validate()

    def test_validate_route_type_invalid(self) -> None:
        """Should raise if route_type is not one of hash/semantic/mixed."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="invalid",
            route_target="cfo-agent",
            route_score=0.95,
        )
        with pytest.raises(ValueError, match="route_type must be one of"):
            log.validate()

    def test_validate_score_below_zero(self) -> None:
        """Should raise if route_score < 0.0."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=-0.1,
        )
        with pytest.raises(ValueError, match="route_score must be between 0.0 and 1.0"):
            log.validate()

    def test_validate_cost_estimate_negative(self) -> None:
        """Should raise if cost_estimate < 0."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
            cost_estimate=-1.0,
        )
        with pytest.raises(ValueError, match="cost_estimate must be non-negative"):
            log.validate()

    def test_validate_latency_ms_negative(self) -> None:
        """Should raise if latency_ms < 0."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
            latency_ms=-1.0,
        )
        with pytest.raises(ValueError, match="latency_ms must be non-negative"):
            log.validate()

    def test_default_values(self) -> None:
        """Should have correct default values."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="hash",
            route_target="node-A",
            route_score=1.0,
        )
        assert log.cost_estimate == 0.0
        assert log.latency_ms == 0.0
        assert log.worm_storage_ref == ""
        assert log.timestamp is not None

    def test_custom_timestamp(self) -> None:
        """Should accept custom timestamp."""
        custom_time = datetime(2024, 1, 1, tzinfo=UTC)
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
            timestamp=custom_time,
        )
        assert log.timestamp == custom_time

    def test_worm_storage_ref(self) -> None:
        """Should store WORM storage reference."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="cfo-agent",
            route_score=0.95,
            worm_storage_ref="s3://bucket/worm/route-log-123",
        )
        assert log.worm_storage_ref == "s3://bucket/worm/route-log-123"

    def test_route_type_local(self) -> None:
        """Should accept route_type=local (UDMR extension)."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            route_target="qwen2.5:7b",
            route_score=1.0,
        )
        log.validate()

    def test_route_type_cloud(self) -> None:
        """Should accept route_type=cloud (UDMR extension)."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="cloud",
            route_target="qwen-turbo",
            route_score=1.0,
        )
        log.validate()

    def test_fallback_reason_valid_values(self) -> None:
        """Should accept valid fallback_reason values (UDMR extension)."""
        for reason in ["timeout", "unavailable", "health_check_failed"]:
            log = RoutingDecisionLog(
                log_id=uuid.uuid4(),
                task_id="task-001",
                session_id="session-001",
                route_type="cloud",
                route_target="qwen-turbo",
                route_score=1.0,
                fallback_reason=reason,
            )
            log.validate()

    def test_fallback_reason_invalid_value(self) -> None:
        """Should raise if fallback_reason has invalid value."""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="cloud",
            route_target="qwen-turbo",
            route_score=1.0,
            fallback_reason="invalid_reason",
        )
        with pytest.raises(ValueError, match="fallback_reason must be one of"):
            log.validate()


class TestRoutingDecisionLogBoundaryValues:
    """边界值和 UDMR 扩展字段测试"""

    def test_score_exactly_zero(self) -> None:
        """route_score=0.0 应有效"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="hash",
            route_target="node-A",
            route_score=0.0,
        )
        log.validate()

    def test_score_exactly_one(self) -> None:
        """route_score=1.0 应有效"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="hash",
            route_target="node-A",
            route_score=1.0,
        )
        log.validate()

    def test_score_above_one(self) -> None:
        """route_score > 1.0 应无效"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="hash",
            route_target="node-A",
            route_score=1.1,
        )
        with pytest.raises(ValueError, match="route_score"):
            log.validate()

    def test_task_id_whitespace_only(self) -> None:
        """task_id 仅含空格应无效"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="   ",
            session_id="session-001",
            route_type="hash",
            route_target="node-A",
            route_score=0.5,
        )
        with pytest.raises(ValueError, match="task_id must not be empty"):
            log.validate()

    def test_session_id_whitespace_only(self) -> None:
        """session_id 仅含空格应无效"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="   ",
            route_type="hash",
            route_target="node-A",
            route_score=0.5,
        )
        with pytest.raises(ValueError, match="session_id must not be empty"):
            log.validate()

    def test_cost_actual_negative(self) -> None:
        """cost_actual < 0 应无效"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="cloud",
            route_target="model-a",
            route_score=0.8,
            cost_actual=-0.01,
        )
        with pytest.raises(ValueError, match="cost_actual must be non-negative"):
            log.validate()

    def test_cost_actual_zero(self) -> None:
        """cost_actual=0.0 应有效"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="cloud",
            route_target="model-a",
            route_score=0.8,
            cost_actual=0.0,
        )
        log.validate()

    def test_cost_estimate_zero(self) -> None:
        """cost_estimate=0.0 应有效"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="cloud",
            route_target="model-a",
            route_score=0.8,
            cost_estimate=0.0,
        )
        log.validate()

    def test_latency_ms_zero(self) -> None:
        """latency_ms=0.0 应有效"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="semantic",
            route_target="agent-a",
            route_score=0.8,
            latency_ms=0.0,
        )
        log.validate()

    def test_fallback_reason_none_is_valid(self) -> None:
        """fallback_reason=None 应有效"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="cloud",
            route_target="model-a",
            route_score=0.8,
            fallback_reason=None,
        )
        log.validate()

    def test_all_route_types_valid(self) -> None:
        """所有 route_type 值都应有效"""
        for route_type in ("hash", "semantic", "mixed", "local", "cloud"):
            log = RoutingDecisionLog(
                log_id=uuid.uuid4(),
                task_id="task-001",
                session_id="session-001",
                route_type=route_type,
                route_target="target",
                route_score=0.5,
            )
            log.validate()


class TestRoutingDecisionLogTokenFields:
    """Token 消耗扩展字段测试（Story 1.19）"""

    def test_token_fields_default_zero(self) -> None:
        """Token 字段默认值应为 0（向后兼容）"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            route_target="qwen2.5:7b",
            route_score=1.0,
        )
        assert log.prompt_tokens == 0
        assert log.completion_tokens == 0
        assert log.total_tokens == 0

    def test_token_fields_set(self) -> None:
        """Token 字段应可正确赋值"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="cloud",
            route_target="MiniMax-M2.7",
            route_score=0.9,
            prompt_tokens=512,
            completion_tokens=1024,
            total_tokens=1536,
        )
        assert log.prompt_tokens == 512
        assert log.completion_tokens == 1024
        assert log.total_tokens == 1536

    def test_validate_prompt_tokens_negative(self) -> None:
        """prompt_tokens < 0 应无效"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            route_target="test",
            route_score=1.0,
            prompt_tokens=-1,
        )
        with pytest.raises(ValueError, match="prompt_tokens must be non-negative"):
            log.validate()

    def test_validate_completion_tokens_negative(self) -> None:
        """completion_tokens < 0 应无效"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            route_target="test",
            route_score=1.0,
            completion_tokens=-1,
        )
        with pytest.raises(ValueError, match="completion_tokens must be non-negative"):
            log.validate()

    def test_validate_total_tokens_negative(self) -> None:
        """total_tokens < 0 应无效"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            route_target="test",
            route_score=1.0,
            total_tokens=-1,
        )
        with pytest.raises(ValueError, match="total_tokens must be non-negative"):
            log.validate()

    def test_token_fields_do_not_break_existing_construction(self) -> None:
        """已有构造方式不受影响（向后兼容）"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="hash",
            route_target="node-A",
            route_score=1.0,
        )
        log.validate()
        assert log.cost_estimate == 0.0
        assert log.prompt_tokens == 0


class TestRoutingDecisionLogUDMRFields:
    """UDMR 扩展字段测试"""

    def test_selected_model(self) -> None:
        """selected_model 应被正确存储"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="local",
            route_target="qwen2.5:7b",
            route_score=1.0,
            selected_model="qwen2.5:7b",
        )
        assert log.selected_model == "qwen2.5:7b"

    def test_cost_actual(self) -> None:
        """cost_actual 应被正确存储"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="cloud",
            route_target="qwen-turbo",
            route_score=0.9,
            cost_actual=0.005,
        )
        assert log.cost_actual == 0.005

    def test_frozen_dataclass(self) -> None:
        """RoutingDecisionLog 应为 frozen dataclass"""
        log = RoutingDecisionLog(
            log_id=uuid.uuid4(),
            task_id="task-001",
            session_id="session-001",
            route_type="hash",
            route_target="node-A",
            route_score=1.0,
        )
        import dataclasses

        assert dataclasses.is_dataclass(log)
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(log, "task_id", "mutated")
