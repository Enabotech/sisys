"""领域层实体抽取事件模块

定义 EntitiesExtracted 事件，在实体抽取完成后发布。
事件携带完整的抽取结果元数据（entity_count, relation_count, memory_id）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import DomainEvent


@dataclass(frozen=True)
class EntitiesExtracted(DomainEvent):
    """实体抽取完成事件

    在实体抽取完成后发布，包含抽取结果元数据。

    Attributes:
        memory_id: 关联记忆 ID（str 类型，对标 MemoryChanged 模式）
        entity_count: 抽取实体数量
        relation_count: 抽取关系数量
        extraction_type: 抽取类型（"rule_only" / "llm_only" / "hybrid"）
    """

    event_type: str = field(default="EntitiesExtracted", init=False)
    memory_id: str = ""
    entity_count: int = 0
    relation_count: int = 0
    extraction_type: str = ""

    def __post_init__(self) -> None:
        """设置 aggregate_id, aggregate_type"""
        if self.aggregate_id is None and self.memory_id:
            object.__setattr__(self, "aggregate_id", self.memory_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "EntityExtraction")


__all__ = [
    "EntitiesExtracted",
]
