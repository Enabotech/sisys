"""SagaStatusChanged 事件单元测试"""

from __future__ import annotations

import uuid

import pytest

from src.domain.events.saga_events import SagaStatusChanged
from src.domain.exceptions import EntityValidationError


class TestSagaStatusChanged:
    """SagaStatusChanged 事件测试"""

    def test_create_valid_event(self) -> None:
        """测试创建有效的 Saga 状态变更事件"""
        saga_id = uuid.uuid4()
        event = SagaStatusChanged(
            saga_id=saga_id,
            saga_type="DocumentProcessing",
            old_status=None,
            new_status="PENDING",
        )

        assert event.saga_id == saga_id
        assert event.saga_type == "DocumentProcessing"
        assert event.old_status is None
        assert event.new_status == "PENDING"
        assert event.event_type == "SagaStatusChanged"
        assert event.source == "saga"
        assert event.aggregate_type == "Saga"

    def test_create_event_with_all_fields(self) -> None:
        """测试创建包含所有字段的事件"""
        saga_id = uuid.uuid4()
        event = SagaStatusChanged(
            saga_id=saga_id,
            saga_type="StrategicPlanning",
            old_status="RUNNING",
            new_status="COMPLETED",
            step_index=3,
            error_message=None,
        )

        assert event.saga_id == saga_id
        assert event.step_index == 3
        assert event.error_message is None

    def test_create_event_with_error_message(self) -> None:
        """测试创建包含错误信息的失败事件"""
        event = SagaStatusChanged(
            saga_type="DocumentProcessing",
            new_status="FAILED",
            error_message="Connection timeout",
        )

        assert event.new_status == "FAILED"
        assert event.error_message == "Connection timeout"

    def test_aggregate_id_set_to_saga_id(self) -> None:
        """测试 aggregate_id 被设置为 saga_id"""
        saga_id = uuid.uuid4()
        event = SagaStatusChanged(
            saga_id=saga_id,
            saga_type="Test",
            new_status="RUNNING",
        )

        assert event.aggregate_id == saga_id

    def test_invalid_empty_saga_type_raises(self) -> None:
        """测试空的 saga_type 抛出 ValueError"""
        with pytest.raises(EntityValidationError, match="saga_type 不能为空"):
            SagaStatusChanged(
                saga_type="",
                new_status="PENDING",
            )

    def test_invalid_empty_new_status_raises(self) -> None:
        """测试空的 new_status 抛出 ValueError"""
        with pytest.raises(EntityValidationError, match="new_status 不能为空"):
            SagaStatusChanged(
                saga_type="Test",
                new_status="",
            )

    def test_invalid_new_status_raises(self) -> None:
        """测试无效的 new_status 抛出 ValueError"""
        with pytest.raises(EntityValidationError, match="new_status 必须是有效状态"):
            SagaStatusChanged(
                saga_type="Test",
                new_status="INVALID_STATUS",
            )

    def test_invalid_old_status_raises(self) -> None:
        """测试无效的 old_status 抛出 ValueError"""
        with pytest.raises(EntityValidationError, match="old_status 必须是有效状态"):
            SagaStatusChanged(
                saga_type="Test",
                old_status="INVALID_STATUS",
                new_status="COMPLETED",
            )

    def test_valid_status_values(self) -> None:
        """测试所有有效状态值都能被接受"""
        valid_statuses = ("PENDING", "RUNNING", "COMPLETED", "COMPENSATING", "COMPENSATED", "FAILED")

        for status in valid_statuses:
            event = SagaStatusChanged(
                saga_type="Test",
                new_status=status,
            )
            assert event.new_status == status

    def test_to_dict_includes_all_fields(self) -> None:
        """测试 to_dict 包含所有事件字段"""
        saga_id = uuid.uuid4()
        event = SagaStatusChanged(
            saga_id=saga_id,
            saga_type="TestSaga",
            old_status="RUNNING",
            new_status="COMPLETED",
            step_index=5,
            error_message=None,
        )

        data = event.to_dict()

        # 验证基础字段
        assert data["event_type"] == "SagaStatusChanged"
        assert data["source"] == "saga"
        assert data["aggregate_type"] == "Saga"
        assert data["aggregate_id"] == str(saga_id)  # to_dict 返回字符串

        # 验证 payload 包含 saga 相关字段
        payload = data["payload"]
        assert payload["saga_type"] == "TestSaga"
        assert payload["old_status"] == "RUNNING"
        assert payload["new_status"] == "COMPLETED"
        assert payload["step_index"] == 5


class TestSagaStatusChangedPayload:
    """SagaStatusChanged 事件 payload 测试"""

    def test_status_transition_payload(self) -> None:
        """测试状态转换的 payload 结构"""
        event = SagaStatusChanged(
            saga_type="DocumentProcessing",
            old_status="PENDING",
            new_status="RUNNING",
            step_index=0,
        )

        # 注意：event.payload 是 dataclass 字段，to_dict()["payload"] 包含 saga 字段
        data = event.to_dict()
        payload = data["payload"]
        assert payload["saga_type"] == "DocumentProcessing"
        assert payload["old_status"] == "PENDING"
        assert payload["new_status"] == "RUNNING"
        assert payload["step_index"] == 0

    def test_compensation_flow_events(self) -> None:
        """测试补偿流程的事件序列"""
        # 模拟 Saga 补偿流程的状态转换
        compensating_event = SagaStatusChanged(
            saga_type="OrderProcessing",
            old_status="RUNNING",
            new_status="COMPENSATING",
            step_index=2,
        )
        assert compensating_event.new_status == "COMPENSATING"

        compensated_event = SagaStatusChanged(
            saga_type="OrderProcessing",
            old_status="COMPENSATING",
            new_status="COMPENSATED",
            step_index=2,
        )
        assert compensated_event.new_status == "COMPENSATED"
