"""领域层记忆元数据索引实体模块

定义用户记忆元数据索引实体，架构来源: architecture.md §11.2.5

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class MemoryMetadata:
    """用户记忆元数据索引实体

    用于追踪 L0 文件系统记忆的状态快照
    """

    memory_id: uuid.UUID
    name: str
    type: str  # 'user' | 'feedback' | 'project' | 'reference'
    path: str
    user_id: str = ""
    description: str = ""
    version: int = 1
    mtime: datetime = field(default_factory=lambda: datetime.now(UTC))
    owner: str = ""
    group_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    deleted_at: datetime | None = None  # 软删除标记

    def __post_init__(self) -> None:
        """验证类型字段"""
        valid_types = {"user", "feedback", "project", "reference"}
        if self.type not in valid_types:
            raise ValueError(f"type must be one of {valid_types}, got '{self.type}'")

    def bump_version(self) -> None:
        """递增版本号（乐观锁）"""
        self.version += 1
        self.updated_at = datetime.now(UTC)

    @classmethod
    def create(
        cls,
        name: str,
        memory_type: str,
        user_id: str = "",
        description: str = "",
    ) -> MemoryMetadata:
        """创建新的 MemoryMetadata 实例

        Args:
            name: 记忆名称（UNIQUE）
            memory_type: 记忆类型
            user_id: 用户标识
            description: 描述

        Returns:
            MemoryMetadata 实例
        """
        memory_id = uuid.uuid4()
        path = f"{memory_type}/{memory_id}.md"
        return cls(
            memory_id=memory_id,
            name=name,
            type=memory_type,
            path=path,
            user_id=user_id,
            description=description,
        )
