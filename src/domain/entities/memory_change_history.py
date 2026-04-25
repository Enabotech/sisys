"""MemoryChangeHistory 实体 — 用户记忆变更历史。

架构来源: architecture.md §11.2.5

特点:
- append-only（历史记录不可删除/修改）
- delete 操作本身会作为新条目记录（change_type='delete'）
- 使用 UUID 外键（memory_id）引用 MemoryMetadata.memory_id

字段:
- id: UUID 主键
- memory_id: UUID 外键引用 MemoryMetadata.memory_id
- version: INTEGER
- changed_at: TIMESTAMP
- changed_by: VARCHAR(255) ('user_id' 或 'system')
- change_type: VARCHAR(50) ('create' | 'update' | 'delete')
- changed_fields: JSONB
- diff_summary: TEXT
- archived_ref: VARCHAR(500)（L4 归档引用，可选）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class MemoryChangeHistory:
    """用户记忆变更历史实体（append-only）。

    用于追溯记忆的变更过程，不存储当前状态。
    """

    id: uuid.UUID
    memory_id: uuid.UUID
    version: int
    changed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    changed_by: str = ""
    change_type: str = ""  # 'create' | 'update' | 'delete'
    changed_fields: dict = field(default_factory=dict)  # JSONB 格式
    diff_summary: str = ""
    archived_ref: str = ""

    def __post_init__(self) -> None:
        """验证 change_type 字段"""
        valid_types = {"create", "update", "delete"}
        if self.change_type not in valid_types:
            raise ValueError(f"change_type must be one of {valid_types}, got '{self.change_type}'")

    @classmethod
    def create(
        cls,
        memory_id: uuid.UUID,
        version: int,
        change_type: str,
        changed_by: str = "",
        changed_fields: dict | None = None,
        diff_summary: str = "",
        archived_ref: str = "",
    ) -> MemoryChangeHistory:
        """创建新的 MemoryChangeHistory 条目。

        Args:
            memory_id: 关联的记忆 ID
            version: 版本号
            change_type: 变更类型
            changed_by: 变更者
            changed_fields: 变更字段（JSONB 格式）
            diff_summary: 变更摘要
            archived_ref: L4 归档引用

        Returns:
            MemoryChangeHistory 实例
        """
        return cls(
            id=uuid.uuid4(),
            memory_id=memory_id,
            version=version,
            changed_by=changed_by,
            change_type=change_type,
            changed_fields=changed_fields or {},
            diff_summary=diff_summary,
            archived_ref=archived_ref,
        )
