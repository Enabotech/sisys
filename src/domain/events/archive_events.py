"""领域层档案事件模块

定义 ArchiveCreated 事件，在战略档案创建完成（含多存储层协同完成）时发布。
事件携带档案元数据（archive_id, plan_id, archive_type, storage_refs）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.entities.strategic_archive import ArchiveType
from src.domain.events.base import DomainEvent


@dataclass(frozen=True)
class ArchiveCreated(DomainEvent):
    """战略档案创建完成事件

    在档案创建完成（含多存储层协同完成）时发布。
    事件类型: "ArchiveCreated"（RELIABLE 模式）
    Schema 版本: v1.0.0

    Attributes:
        archive_id: 档案标识
        plan_id: 关联的 SP/BP 规划标识
        plan_type: 规划类型（"SP"/"BP"）
        archive_type: 档案类型
        has_embedding: 是否有 L3 向量
        has_blob: 是否有 L4 对象
        has_graph: 是否有 L5 图谱
    """

    archive_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="ArchiveCreated", init=False)
    plan_id: uuid.UUID | None = None
    plan_type: str = ""
    archive_type: ArchiveType = ArchiveType.ASSUMPTION
    has_embedding: bool = False
    has_blob: bool = False
    has_graph: bool = False

    def __post_init__(self) -> None:
        """设置 aggregate_id, aggregate_type"""
        # default_factory=uuid.uuid4 仅为兼容 dataclass 继承约束（父类 event_type 有默认值后，
        # 子类首字段必须有默认值），调用方必须显式传入 archive_id，不应依赖自动生成的值
        object.__setattr__(self, "aggregate_id", self.archive_id)
        object.__setattr__(self, "aggregate_type", "StrategicArchive")


@dataclass(frozen=True)
class ValidityPeriodSet(DomainEvent):
    """档案有效期设置完成事件

    在档案有效期设置完成时发布。
    事件类型: "ValidityPeriodSet"（RELIABLE 模式）
    Schema 版本: v1.0.0

    Attributes:
        archive_id: 档案标识（必填）
        plan_id: 关联的 SP/BP 规划标识
        archive_type: 档案类型
        valid_from: 生效时间
        valid_until: 失效时间
    """

    archive_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="ValidityPeriodSet", init=False)
    plan_id: uuid.UUID | None = None
    archive_type: ArchiveType = ArchiveType.ASSUMPTION
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    def __post_init__(self) -> None:
        """设置 aggregate_id, aggregate_type（无条件赋值）"""
        # default_factory=uuid.uuid4 仅为兼容 dataclass 继承约束（父类 event_type 有默认值后，
        # 子类首字段必须有默认值），调用方必须显式传入 archive_id，不应依赖自动生成的值
        object.__setattr__(self, "aggregate_id", self.archive_id)
        object.__setattr__(self, "aggregate_type", "StrategicArchive")


@dataclass(frozen=True)
class FactBecameStale(DomainEvent):
    """事实变为陈旧事件

    在档案有效期过期或归档超 12 个月自动陈旧时发布。
    事件类型: "FactBecameStale"（RELIABLE 模式）
    Schema 版本: v1.0.0

    Attributes:
        archive_id: 档案标识（必填）
        stale_reason: 陈旧原因（"expired"/"archived_too_long"）
        plan_id: 关联的 SP/BP 规划标识
        archive_type: 档案类型
        valid_until: 失效时间（基于 archived_at 标记陈旧时为 None）
        stale_since: 标记为陈旧的时间
    """

    archive_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="FactBecameStale", init=False)
    stale_reason: str = "expired"
    plan_id: uuid.UUID | None = None
    archive_type: ArchiveType = ArchiveType.ASSUMPTION
    valid_until: datetime | None = None
    stale_since: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """设置 aggregate_id, aggregate_type（无条件赋值）"""
        # default_factory=uuid.uuid4 仅为兼容 dataclass 继承约束（父类 event_type 有默认值后，
        # 子类首字段必须有默认值），调用方必须显式传入 archive_id，不应依赖自动生成的值
        object.__setattr__(self, "aggregate_id", self.archive_id)
        object.__setattr__(self, "aggregate_type", "StrategicArchive")


__all__ = [
    "ArchiveCreated",
    "ValidityPeriodSet",
    "FactBecameStale",
]
