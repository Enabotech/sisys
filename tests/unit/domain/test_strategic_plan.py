"""
领域层测试示例 - 测试领域实体、值对象、领域事件。

领域层测试特点：
- 快速执行（无外部依赖）
- 100% 内存执行
- 验证业务规则
- 验证领域不变量
"""
from uuid import uuid4

import pytest

from src.domain.entities.strategic_plan import PlanStatus, PlanType, StrategicPlan
from src.domain.events import DomainEvent
from src.domain.exceptions import DomainValidationError, InvalidStatusError


class TestStrategicPlan:
    """战略规划领域实体测试"""

    def test_create_plan_with_valid_data(self):
        """Given 有效的领域数据，When 创建战略规划，Then 成功创建"""
        # Arrange
        plan_id = uuid4()
        creator_id = "agent_ceo"

        # Act
        plan = StrategicPlan.create(
            id=plan_id,
            plan_type=PlanType.SP,
            creator_id=creator_id,
        )

        # Assert
        assert plan.id == plan_id
        assert plan.plan_type == PlanType.SP
        assert plan.status == PlanStatus.DRAFT
        assert plan.creator_id == creator_id
        assert len(plan.domain_events) == 1
        assert isinstance(plan.domain_events[0], DomainEvent)

    def test_create_plan_with_invalid_type_raises_error(self):
        """Given 无效的规划类型，When 创建战略规划，Then 抛出领域验证异常"""
        # Arrange & Act & Assert
        with pytest.raises(DomainValidationError):
            StrategicPlan.create(
                plan_type="INVALID",  # type: ignore
                creator_id="agent_ceo",
            )

    def test_change_status_from_draft_to_in_progress(self):
        """Given 草稿状态的规划，When 变更为进行中，Then 状态变更成功并发布事件"""
        # Arrange
        plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")
        assert plan.status == PlanStatus.DRAFT

        # Act
        plan.change_status(PlanStatus.IN_PROGRESS)

        # Assert
        assert plan.status == PlanStatus.IN_PROGRESS
        assert len(plan.domain_events) == 2  # PlanCreated + PlanStatusChanged

    def test_change_status_invalid_transition_raises_error(self):
        """Given 草稿状态的规划，When 直接变更为已批准，Then 抛出无效状态变更异常"""
        # Arrange
        plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")

        # Act & Assert
        with pytest.raises(InvalidStatusError):
            plan.change_status(PlanStatus.APPROVED)

    def test_plan_events_are_published(self):
        """Given 新规划创建，When 创建成功，Then 发布 PlanCreated 事件"""
        # Act
        plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")

        # Assert
        assert len(plan.domain_events) >= 1
        event = plan.domain_events[0]
        assert event.event_type == "plan.created"
        assert event.aggregate_id == plan.id


class TestPlanStatusTransitions:
    """测试规划状态转换规则"""

    def test_draft_to_in_progress(self):
        """Given 草稿状态，When 变更为进行中，Then 成功"""
        plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")
        plan.change_status(PlanStatus.IN_PROGRESS)
        assert plan.status == PlanStatus.IN_PROGRESS

    def test_in_progress_to_completed(self):
        """Given 进行中状态，When 变更为已完成，Then 成功"""
        plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")
        plan.change_status(PlanStatus.IN_PROGRESS)
        plan.change_status(PlanStatus.COMPLETED)
        assert plan.status == PlanStatus.COMPLETED

    def test_draft_to_completed_raises_error(self):
        """Given 草稿状态，When 直接变更为已完成，Then 抛出异常"""
        plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")
        with pytest.raises(InvalidStatusError):
            plan.change_status(PlanStatus.COMPLETED)


class TestPlanValidation:
    """测试规划验证规则"""

    def test_plan_with_invalid_creator_raises_error(self):
        """Given 空的创建者 ID，When 创建规划，Then 抛出验证异常"""
        with pytest.raises(DomainValidationError):
            StrategicPlan.create(
                plan_type=PlanType.SP,
                creator_id="",
            )

    def test_plan_id_cannot_be_none(self):
        """Given 无效的 ID 类型，When 创建规划，Then 抛出验证异常"""
        with pytest.raises(DomainValidationError):
            StrategicPlan.create(
                plan_type=PlanType.SP,
                creator_id="agent_ceo",
                id="invalid-uuid",  # type: ignore
            )


class TestStrategicPlanSpecialMethods:
    """测试战略规划特殊方法"""

    def test_plan_repr(self):
        """Given 规划实例，When 调用 repr，Then 返回格式化的字符串表示"""
        # Arrange
        plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")

        # Act
        result = repr(plan)

        # Assert
        assert "StrategicPlan" in result
        assert "SP" in result
        assert "draft" in result
        assert "agent_ceo" in result

    def test_plan_eq_same_object(self):
        """Given 同一对象，When 比较，Then 相等"""
        # Arrange
        plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")

        # Act & Assert
        assert plan == plan

    def test_plan_eq_different_objects_same_id(self):
        """Given 不同对象但相同 ID，When 比较，Then 相等"""
        # Arrange
        plan1 = StrategicPlan.create(
            plan_type=PlanType.SP,
            creator_id="agent_ceo",
            id=uuid4(),
        )
        plan2 = StrategicPlan.create(
            plan_type=PlanType.SP,
            creator_id="agent_ceo",
            id=plan1.id,
        )

        # Act & Assert
        assert plan1 == plan2

    def test_plan_eq_different_objects_different_id(self):
        """Given 不同对象且不同 ID，When 比较，Then 不相等"""
        # Arrange
        plan1 = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")
        plan2 = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")

        # Act & Assert
        assert plan1 != plan2

    def test_plan_eq_different_type(self):
        """Given 不同类型对象，When 比较，Then 不相等"""
        # Arrange
        plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")

        # Act & Assert
        assert plan != "not a plan"
        assert plan != 123
        assert plan != {"id": plan.id}

    def test_plan_hash(self):
        """Given 规划实例，When 调用 hash，Then 返回 ID 的哈希值"""
        # Arrange
        plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")

        # Act
        result = hash(plan)

        # Assert
        assert result == hash(plan.id)

    def test_add_checkpoint(self):
        """Given 规划，When 添加检查点，Then 检查点添加到列表"""
        # Arrange
        from datetime import datetime, timezone

        plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")
        checkpoint_time = datetime.now(timezone.utc)

        # Act
        plan.add_checkpoint(
            stage="gap_analysis",
            status="completed",
            completed_at=checkpoint_time,
            notes="Test checkpoint",
        )

        # Assert
        assert len(plan.checkpoints) == 1
        checkpoint = plan.checkpoints[0]
        assert checkpoint["stage"] == "gap_analysis"
        assert checkpoint["status"] == "completed"
        assert checkpoint["notes"] == "Test checkpoint"

    def test_add_checkpoint_without_optional_fields(self):
        """Given 规划，When 添加检查点（不提供可选字段），Then 成功添加"""
        # Arrange
        plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")

        # Act
        plan.add_checkpoint(
            stage="market_insight",
            status="in-progress",
        )

        # Assert
        assert len(plan.checkpoints) == 1
        checkpoint = plan.checkpoints[0]
        assert checkpoint["stage"] == "market_insight"
        assert checkpoint["status"] == "in-progress"
        assert "completed_at" in checkpoint  # 自动生成

    def test_clear_events(self):
        """Given 有事件的规划，When 清空事件，Then 事件列表为空"""
        # Arrange
        plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")
        assert len(plan.domain_events) > 0

        # Act
        plan.clear_events()

        # Assert
        assert len(plan.domain_events) == 0

    def test_plan_properties(self):
        """Given 规划实例，When 访问属性，Then 返回正确的值"""
        # Arrange
        plan = StrategicPlan.create(plan_type=PlanType.SP, creator_id="agent_ceo")

        # Act & Assert
        assert plan.plan_type == PlanType.SP
        assert plan.status == PlanStatus.DRAFT
        assert plan.creator_id == "agent_ceo"
        assert plan.version == 1
        assert plan.blm_stage is None
        assert plan.created_at is not None
        assert plan.updated_at is not None
