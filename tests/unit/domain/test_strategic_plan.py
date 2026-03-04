"""
领域层测试示例 - 测试领域实体、值对象、领域事件。

领域层测试特点：
- 快速执行（无外部依赖）
- 100% 内存执行
- 验证业务规则
- 验证领域不变量
"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone

from src.domain.entities.strategic_plan import StrategicPlan, PlanType, PlanStatus
from src.domain.events import DomainEvent
from src.domain.exceptions import InvalidStatusError, DomainValidationError


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
        """Given 空的 ID，When 创建规划，Then 抛出验证异常"""
        with pytest.raises(DomainValidationError):
            StrategicPlan.create(
                plan_type=PlanType.SP,
                creator_id="agent_ceo",
                id=None,  # type: ignore
            )
