"""领域层词典管理事件模块

定义 DictionaryUpdated 事件，在词典发生变更（新增/修改/删除/回滚）时发布。
事件携带变更元数据（term, action, trigger, dictionary_version）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .base import DomainEvent


@dataclass(frozen=True)
class DictionaryUpdated(DomainEvent):
    """词典更新事件

    在词典发生变更时发布，包含变更元数据。
    使用独立字段 dictionary_version 避免与基类 version（事件版本）冲突。

    Attributes:
        term: 变更词条
        action: 动作（add/update/delete/rollback）
        trigger: 触发源（api/ingest/manual）
        dictionary_version: 变更后的词典版本号
    """

    event_type: str = field(default="DictionaryUpdated", init=False)
    term: str = ""
    action: str = ""
    trigger: str = ""
    dictionary_version: int = 0

    def __post_init__(self) -> None:
        """设置 aggregate_id, aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", uuid.uuid4())
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Dictionary")


__all__ = [
    "DictionaryUpdated",
]
