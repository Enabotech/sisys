"""领域层工具版本管理事件模块（Story 4-6 — 灰度发布与回滚）

3 个领域事件（聚合根 = ToolVersion，event_type init=False 写法触发自动注册）：
- ToolVersionRegistered：register_version 成功
- ToolVersionPublished：publish_version / abort_canary 成功
  （from_status 区分审计语义：PENDING=直接全量 / CANARY=转正或调档）
- ToolRolledBack：rollback 成功（deprecated_versions 记录被降级清单）

平台级资源事件：payload 不含 tenant_id——工具定义全局共享（TOOL_CATALOG
语义一致），区别于租户数据事件；惰性初始注册不发 Registered（catalog 23
工具首次执行不产生事件风暴——显式 register_version 才发事件）。
列表字段一律截断 ≤10 条（4-3 P0-H 先例，防撑爆 Redis pub/sub）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent

# payload 列表字段截断上限（4-3 P0-H 先例）
_MAX_LIST_ITEMS = 10


def _truncate(items: list[Any] | None) -> list[Any]:
    """列表字段截断 ≤10 条（None 归一为空列表）。"""
    if not items:
        return []
    return items[:_MAX_LIST_ITEMS]


@dataclass(frozen=True)
class ToolVersionRegistered(DomainEvent):
    """新工具版本注册完成事件。

    Attributes:
        tool_id: 所属工具 ID
        tool_version: 新注册版本号
        required_rollout_mode: 发布模式约束（any/canary_only——兼容性分级结果）
        breaking_summary: 破坏性变更摘要（截断 ≤10 条）
        event_type: 事件类型，固定 "ToolVersionRegistered"
    """

    tool_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tool_version: str = ""
    required_rollout_mode: str = "any"
    breaking_summary: list[dict[str, Any]] = field(default_factory=list)
    event_type: str = field(default="ToolVersionRegistered", init=False)

    def __post_init__(self) -> None:
        """设置聚合标识 + 摘要截断。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.tool_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "ToolVersion")
        object.__setattr__(self, "breaking_summary", _truncate(self.breaking_summary))


@dataclass(frozen=True)
class ToolVersionPublished(DomainEvent):
    """工具版本发布状态变更事件（灰度发起/调档/直接全量/提升转正/放弃灰度）。

    from_status 审计语义：PENDING→STABLE = 直接全量；CANARY→STABLE = 灰度
    毕业转正（canary_only 版本唯一全量通道）；CANARY→CANARY = 渐进调档
    （traffic_weight 为新值）；CANARY→DEPRECATED = 放弃灰度（abort）。

    Attributes:
        tool_id: 所属工具 ID
        tool_version: 目标版本号
        from_status: 迁移前状态（pending/canary/stable）
        to_status: 迁移后状态（canary/stable/deprecated）
        traffic_weight: 迁移后承接权重（调档为新值；abort 为 0）
        event_type: 事件类型，固定 "ToolVersionPublished"
    """

    tool_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tool_version: str = ""
    from_status: str = "pending"
    to_status: str = "canary"
    traffic_weight: int = 0
    event_type: str = field(default="ToolVersionPublished", init=False)

    def __post_init__(self) -> None:
        """设置聚合标识。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.tool_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "ToolVersion")


@dataclass(frozen=True)
class ToolRolledBack(DomainEvent):
    """工具版本一键回滚完成事件。

    Attributes:
        tool_id: 所属工具 ID
        from_version: 回滚前当前 STABLE 版本
        to_version: 回滚目标版本（恢复为 STABLE）
        trigger: 触发来源（api/manual/auto——V1 仅 api/manual）
        deprecated_versions: 本次被降级的全部版本号（含被清场 CANARY，
            截断 ≤10——下游可完整重建状态史）
        event_type: 事件类型，固定 "ToolRolledBack"
    """

    tool_id: uuid.UUID = field(default_factory=uuid.uuid4)
    from_version: str = ""
    to_version: str = ""
    trigger: str = "api"
    deprecated_versions: list[str] = field(default_factory=list)
    event_type: str = field(default="ToolRolledBack", init=False)

    def __post_init__(self) -> None:
        """设置聚合标识 + 清单截断。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.tool_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "ToolVersion")
        object.__setattr__(self, "deprecated_versions", _truncate(self.deprecated_versions))


__all__ = [
    "ToolRolledBack",
    "ToolVersionPublished",
    "ToolVersionRegistered",
]
