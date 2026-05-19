"""SagaContext 和 SagaStatus 单元测试

验证 AC-7: Saga 基础设施
对应 Task 7 的 TDD 测试
"""

from __future__ import annotations

import uuid

from src.infrastructure.saga.saga_context import SagaContext
from src.infrastructure.saga.saga_status import SagaStatus


class TestSagaStatus:
    """验证 SagaStatus 枚举"""

    def test_saga_status_values(self) -> None:
        """SagaStatus 应包含所有必要状态"""
        assert SagaStatus.PENDING.value == "PENDING"
        assert SagaStatus.RUNNING.value == "RUNNING"
        assert SagaStatus.COMPLETED.value == "COMPLETED"
        assert SagaStatus.COMPENSATING.value == "COMPENSATING"
        assert SagaStatus.COMPENSATED.value == "COMPENSATED"
        assert SagaStatus.FAILED.value == "FAILED"

    def test_terminal_states(self) -> None:
        """COMPLETED, COMPENSATED, FAILED 应为终态"""
        assert SagaStatus.COMPLETED.is_terminal
        assert SagaStatus.COMPENSATED.is_terminal
        assert SagaStatus.FAILED.is_terminal

    def test_non_terminal_states(self) -> None:
        """PENDING, RUNNING, COMPENSATING 不应为终态"""
        assert not SagaStatus.PENDING.is_terminal
        assert not SagaStatus.RUNNING.is_terminal
        assert not SagaStatus.COMPENSATING.is_terminal

    def test_valid_transitions(self) -> None:
        """状态转换应符合设计"""
        assert SagaStatus.PENDING.can_transition_to(SagaStatus.RUNNING)
        assert SagaStatus.RUNNING.can_transition_to(SagaStatus.COMPLETED)
        assert SagaStatus.RUNNING.can_transition_to(SagaStatus.COMPENSATING)
        assert SagaStatus.COMPENSATING.can_transition_to(SagaStatus.COMPENSATED)
        assert SagaStatus.COMPENSATING.can_transition_to(SagaStatus.FAILED)

    def test_invalid_transitions(self) -> None:
        """非法状态转换应返回 False"""
        assert not SagaStatus.PENDING.can_transition_to(SagaStatus.COMPLETED)
        assert not SagaStatus.COMPLETED.can_transition_to(SagaStatus.RUNNING)


class TestSagaContext:
    """验证 SagaContext 状态管理"""

    def test_create_context(self) -> None:
        """应能创建有效的 SagaContext"""
        ctx = SagaContext(saga_id=uuid.uuid4(), saga_type="test_saga")
        assert ctx.status == SagaStatus.PENDING
        assert ctx.current_step_index == 0
        assert ctx.steps_data == {}

    def test_update_status(self) -> None:
        """update_status 应返回新实例"""
        ctx = SagaContext(saga_id=uuid.uuid4(), saga_type="test_saga")
        new_ctx = ctx.update_status(SagaStatus.RUNNING)
        assert ctx.status == SagaStatus.PENDING
        assert new_ctx.status == SagaStatus.RUNNING

    def test_set_step_data(self) -> None:
        """set_step_data 应保存步骤数据"""
        ctx = SagaContext(saga_id=uuid.uuid4(), saga_type="test_saga")
        new_ctx = ctx.set_step_data("step1", {"input": 1}, {"output": 2})
        assert "step1" in new_ctx.steps_data
        assert new_ctx.steps_data["step1"]["output"] == {"output": 2}

    def test_get_step_output(self) -> None:
        """get_step_output 应返回步骤输出"""
        ctx = SagaContext(saga_id=uuid.uuid4(), saga_type="test_saga")
        ctx = ctx.set_step_data("step1", None, {"key": "value"})
        assert ctx.get_step_output("step1") == {"key": "value"}

    def test_advance_step(self) -> None:
        """advance_step 应递增步骤索引"""
        ctx = SagaContext(saga_id=uuid.uuid4(), saga_type="test_saga")
        ctx = ctx.advance_step(total_steps=3)
        assert ctx.current_step_index == 1

    def test_add_error(self) -> None:
        """add_error 应添加错误记录"""
        ctx = SagaContext(saga_id=uuid.uuid4(), saga_type="test_saga")
        ctx = ctx.add_error("step1", "something failed")
        assert len(ctx.errors) == 1
        assert ctx.errors[0]["step"] == "step1"
        assert ctx.errors[0]["error"] == "something failed"

    def test_to_dict_and_from_dict(self) -> None:
        """序列化/反序列化应保持一致"""
        saga_id = uuid.uuid4()
        ctx = SagaContext(
            saga_id=saga_id,
            saga_type="test_saga",
            status=SagaStatus.RUNNING,
            steps_data={"step1": {"input": None, "output": {"result": "ok"}}},
            current_step_index=1,
        )
        data = ctx.to_dict()
        restored = SagaContext.from_dict(data)

        assert str(restored.saga_id) == str(saga_id)
        assert restored.saga_type == "test_saga"
        assert restored.status == SagaStatus.RUNNING
        assert restored.steps_data == ctx.steps_data
        assert restored.current_step_index == 1
