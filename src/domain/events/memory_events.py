"""SISYS 领域层记忆变更事件模块

定义用户记忆变更事件 MemoryChanged

触发时机:
- L1 显式确认：用户主动说"记住..."（is_automatic=False）
- L3 自动压缩：Checkpoint 创建时（is_automatic=True）

下游监听器处理:
1. 写入 memory_metadata（UPSERT，version + 1）
2. 写入 memory_change_history（append-only）
3. 失效 L1 Redis 缓存

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class MemoryChanged(DomainEvent):
    """用户记忆变更事件

    Attributes:
        memory_id: 记忆唯一标识（UUID 字符串）
        user_id: 用户标识（多租户隔离）
        name: 记忆名称（UNIQUE）
        change_type: 变更类型（create/update/delete）
        is_automatic: 是否自动触发（False=用户主动，True=系统自动）
        old_value: 变更前的值（dict 或 None）
        new_value: 变更后的值（dict 或 None）
    """

    memory_id: str = ""
    user_id: str = ""
    name: str = ""
    change_type: str = ""  # "create" | "update" | "delete"
    is_automatic: bool = False
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """设置 event_type, aggregate_id, aggregate_type"""
        if not self.event_type:
            object.__setattr__(self, "event_type", "MemoryChanged")
        if self.aggregate_id is None and self.memory_id:
            object.__setattr__(self, "aggregate_id", self.memory_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Memory")


# 注册事件类型
DomainEvent._registry["MemoryChanged"] = MemoryChanged
