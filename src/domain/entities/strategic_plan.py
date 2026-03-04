"""
sisys - Strategic Plan Entity.

战略规划领域实体 - 核心业务模型。
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from src.domain.events import DomainEvent
from src.domain.exceptions import DomainValidationError, InvalidStatusError

if TYPE_CHECKING:
    pass


class PlanType(str, Enum):
    """规划类型枚举。"""

    SP = "SP"  # 战略规划 (Strategic Plan)
    BP = "BP"  # 业务计划 (Business Plan)
    AP = "AP"  # 年度计划 (Annual Plan)


class PlanStatus(str, Enum):
    """规划状态枚举。"""

    DRAFT = "draft"  # 草稿
    IN_PROGRESS = "in-progress"  # 进行中
    REVIEW = "review"  # 审查中
    APPROVED = "approved"  # 已批准
    COMPLETED = "completed"  # 已完成
    CANCELLED = "cancelled"  # 已取消


class StrategicPlan:
    """
    战略规划领域实体。

     encapsulates 核心业务逻辑和不变量。
    """

    # 有效的状态转换规则
    VALID_TRANSITIONS = {
        PlanStatus.DRAFT: {PlanStatus.IN_PROGRESS, PlanStatus.CANCELLED},
        PlanStatus.IN_PROGRESS: {PlanStatus.REVIEW, PlanStatus.COMPLETED, PlanStatus.CANCELLED},
        PlanStatus.REVIEW: {PlanStatus.IN_PROGRESS, PlanStatus.APPROVED, PlanStatus.CANCELLED},
        PlanStatus.APPROVED: {PlanStatus.IN_PROGRESS, PlanStatus.COMPLETED},
        PlanStatus.COMPLETED: set(),  # 终态，不可转换
        PlanStatus.CANCELLED: set(),  # 终态，不可转换
    }

    def __init__(
        self,
        id: UUID,
        plan_type: PlanType,
        status: PlanStatus,
        creator_id: str,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
        blm_stage: str | None = None,
    ):
        """初始化战略规划。"""
        self._id = id
        self._plan_type = plan_type
        self._status = status
        self._creator_id = creator_id
        self._created_at = created_at or datetime.now(UTC)
        self._updated_at = updated_at or datetime.now(UTC)
        self._version = version
        self._blm_stage = blm_stage
        self._domain_events: list[DomainEvent] = []
        self._checkpoints: list[dict] = []

    @classmethod
    def create(
        cls,
        plan_type: PlanType | str,
        creator_id: str,
        id: UUID | None = None,
    ) -> "StrategicPlan":
        """
        创建新的战略规划。

        Args:
            plan_type: 规划类型（SP/BP/AP）
            creator_id: 创建者 ID
            id: 可选的 UUID，不提供则自动生成

        Returns:
            新创建的战略规划实例

        Raises:
            DomainValidationError: 当参数验证失败时
        """
        from uuid import uuid4

        # 验证 creator_id
        if not creator_id or not creator_id.strip():
            raise DomainValidationError("creator_id 不能为空")

        # 验证 plan_type
        if isinstance(plan_type, str):
            try:
                plan_type = PlanType(plan_type)
            except ValueError:
                raise DomainValidationError(f"无效的规划类型：{plan_type}")

        # 如果 id 为 None，自动生成
        if id is None:
            id = uuid4()
        elif not isinstance(id, UUID):
            raise DomainValidationError("id 必须是 UUID 类型")

        plan = cls(
            id=id,
            plan_type=plan_type,
            status=PlanStatus.DRAFT,
            creator_id=creator_id,
        )

        # 发布 PlanCreated 事件
        from src.domain.events import PlanCreated

        plan._domain_events.append(PlanCreated(plan_id=plan.id, creator_id=creator_id))

        return plan

    # ========== 属性 ==========

    @property
    def id(self) -> UUID:
        """返回规划 ID。"""
        return self._id

    @property
    def plan_type(self) -> PlanType:
        """返回规划类型。"""
        return self._plan_type

    @property
    def status(self) -> PlanStatus:
        """返回当前状态。"""
        return self._status

    @property
    def creator_id(self) -> str:
        """返回创建者 ID。"""
        return self._creator_id

    @property
    def created_at(self) -> datetime:
        """返回创建时间。"""
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        """返回更新时间。"""
        return self._updated_at

    @property
    def version(self) -> int:
        """返回版本号。"""
        return self._version

    @property
    def blm_stage(self) -> str | None:
        """返回 BLM 阶段。"""
        return self._blm_stage

    @property
    def domain_events(self) -> list[DomainEvent]:
        """返回领域事件列表。"""
        return self._domain_events.copy()

    @property
    def checkpoints(self) -> list[dict]:
        """返回检查点列表。"""
        return self._checkpoints.copy()

    # ========== 业务方法 ==========

    def change_status(self, new_status: PlanStatus | str) -> None:
        """
        变更规划状态。

        Args:
            new_status: 新状态

        Raises:
            InvalidStatusError: 当状态转换不合法时
        """
        # 转换字符串为 PlanStatus
        if isinstance(new_status, str):
            try:
                new_status = PlanStatus(new_status)
            except ValueError:
                raise InvalidStatusError(f"无效的状态：{new_status}")

        # 验证状态转换
        if new_status not in self.VALID_TRANSITIONS.get(self._status, set()):
            raise InvalidStatusError(f"无效的状态转换：{self._status.value} -> {new_status.value}")

        # 执行状态转换
        old_status = self._status
        self._status = new_status
        self._updated_at = datetime.now(UTC)
        self._version += 1

        # 发布 PlanStatusChanged 事件
        from src.domain.events import PlanStatusChanged

        self._domain_events.append(
            PlanStatusChanged(
                plan_id=self.id,
                old_status=old_status,
                new_status=new_status,
            )
        )

    def add_checkpoint(
        self,
        stage: str,
        status: str,
        completed_at: datetime | None = None,
        notes: str | None = None,
    ) -> None:
        """
        添加检查点。

        Args:
            stage: 阶段名称
            status: 检查点状态
            completed_at: 完成时间
            notes: 备注
        """
        checkpoint = {
            "stage": stage,
            "status": status,
            "completed_at": completed_at or datetime.now(UTC),
            "notes": notes,
        }
        self._checkpoints.append(checkpoint)
        self._updated_at = datetime.now(UTC)

    def clear_events(self) -> None:
        """清空领域事件列表（通常在事件发布后调用）。"""
        self._domain_events.clear()

    # ========== 特殊方法 ==========

    def __repr__(self) -> str:
        """返回实体的字符串表示。"""
        return (
            f"StrategicPlan(id={self.id}, type={self.plan_type.value}, "
            f"status={self.status.value}, creator={self.creator_id})"
        )

    def __eq__(self, other: object) -> bool:
        """比较两个实体是否相等。"""
        if not isinstance(other, StrategicPlan):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """返回实体的哈希值。"""
        return hash(self.id)
