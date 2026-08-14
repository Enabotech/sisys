"""领域层档案事件模块

定义 ArchiveCreated 事件，在战略档案创建完成（含多存储层协同完成）时发布。
事件携带档案元数据（archive_id, plan_id, archive_type, storage_refs）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

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

    event_type: str = field(default="ArchiveCreated", init=False)
    archive_id: uuid.UUID = field(default_factory=uuid.uuid4)
    plan_id: uuid.UUID | None = None
    plan_type: str = ""
    archive_type: ArchiveType = ArchiveType.ASSUMPTION
    has_embedding: bool = False
    has_blob: bool = False
    has_graph: bool = False

    def __post_init__(self) -> None:
        """设置 aggregate_id, aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.archive_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "StrategicArchive")


__all__ = [
    "ArchiveCreated",
]
