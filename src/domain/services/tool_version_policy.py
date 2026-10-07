"""领域层工具版本策略服务模块（Story 4-6 — 灰度发布策略/流量路由/保留规划）

三个无状态领域服务 + 一个值对象（storage_tier_strategy.py 的 VO+服务共存形态）：
- RolloutPolicyService：Schema 兼容性 severity → 发布策略分级决策（纯函数，
  stdlib 原生参数——领域层禁止 import 应用层 SchemaCompatibilityResult）
- TrafficRouter：确定性流量路由（规范散列公式：sha256 稳定散列，禁内建 hash）
- VersionRetentionPlanner：版本保留两级排序淘汰规划（纯函数可单测）

Story 4-6 AC-2/AC-3/AC-4 的决策逻辑全部在此层提纯——应用层服务只做编排。
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from src.domain.entities.tool_version import ToolVersion, ToolVersionStatus

# 规范散列公式（Story AC-3 验证标准——规范条款而非实现自由度，
# 实现与测试共用；测试按此公式独立重算期望桶位，禁以 route() 探测同源）：
#   int(hashlib.sha256(route_key.encode()).hexdigest(), 16) % 100 < weight → 命中 canary


@dataclass(frozen=True)
class RolloutDecision:
    """发布策略决策结果值对象。

    Attributes:
        allowed: 是否允许注册（critical 破坏性变更为 False）
        mode: 发布模式约束——"any"（可直接全量）或 "canary_only"（强制灰度）
        reason: 决策依据说明（面向运维可读）
    """

    allowed: bool
    mode: str
    reason: str


class RolloutPolicyService:
    """Schema 兼容性 severity → 发布策略分级决策（领域纯函数服务）。

    分级规则（与 Story 4-3 文件「4.6 对 4.3 的 API 依赖契约」表一致）：
    - critical → 拒绝注册（allowed=False；服务层抛 ToolSchemaCompatibilityError 397）
    - major   → 允许注册 + canary_only（仅禁止 PENDING 直接全量；CANARY promote 放行）
    - minor / 无破坏 → 允许注册 + any（可直接全量）
    """

    @staticmethod
    def decide(max_severity: str | None, breaking_count: int = 0) -> RolloutDecision:
        """按双 Schema 校验结果的最高 severity 做分级决策。

        Args:
            max_severity: 输入/输出双 Schema 校验的 breaking severity 最高值
                （"critical" | "major" | "minor" | None——无破坏性变更）
            breaking_count: 破坏性变更条数（仅用于决策说明文案——4.3 校验器
                顶层变更存在双重上报实态，计数不作决策输入）

        Returns:
            RolloutDecision 值对象
        """
        if max_severity == "critical":
            return RolloutDecision(
                allowed=False,
                mode="canary_only",
                reason=f"critical 破坏性变更（{breaking_count} 条）——拒绝注册",
            )
        if max_severity == "major":
            return RolloutDecision(
                allowed=True,
                mode="canary_only",
                reason=f"major 破坏性变更（{breaking_count} 条）——强制灰度，禁止直接全量",
            )
        return RolloutDecision(
            allowed=True,
            mode="any",
            reason="minor 或无破坏性变更——可直接全量发布",
        )


class TrafficRouter:
    """确定性流量路由器（规范散列公式）。

    同一 route_key 永远路由到同一版本（会话粘性的确定性基础）；散列算法
    为规范条款（sha256 + % 100 < weight 桶映射），实现与测试共用。
    禁用内建 hash()——PYTHONHASHSEED 进程盐化导致跨次运行漂移。
    """

    @staticmethod
    def route(
        route_key: str,
        canary_version: str,
        canary_weight: int,
        stable_version: str,
    ) -> str:
        """按规范散列公式将 route_key 路由到 canary 或 stable 版本。

        Args:
            route_key: 路由键（V1 = context.trace_id，单次执行确定性粒度）
            canary_version: 活跃灰度版本号
            canary_weight: 灰度权重（1-100）
            stable_version: 当前稳定版本号

        Returns:
            命中灰度返回 canary_version，否则 stable_version
        """
        bucket = int(hashlib.sha256(route_key.encode()).hexdigest(), 16) % 100
        return canary_version if bucket < canary_weight else stable_version


class VersionRetentionPlanner:
    """版本保留策略规划器（领域纯函数）。

    两级排序淘汰（淘汰键与回滚价值键对齐）：
    - 第一级：无戳组（last_stable_at 为空的灰度清场产物，非回滚候选）优先
      于带戳组（曾稳定版）
    - 第二级组内排序——无戳组按 created_at 升序（平局裁决键）、带戳组按
      last_stable_at 升序（最新回滚价值最低）
    仅淘汰 DEPRECATED；STABLE/CANARY/PENDING 永不淘汰（软上限——可淘汰
    不足时数量上限让位于保护态）。
    """

    @staticmethod
    def plan(versions: list[ToolVersion], max_retained: int) -> list[uuid.UUID]:
        """计算待淘汰的 version_id 列表。

        Args:
            versions: 某工具的全部版本记录
            max_retained: 保留上限（总数口径，含活跃态）

        Returns:
            待淘汰的 version_id 列表（按淘汰顺序；无淘汰返回空列表）
        """
        excess = len(versions) - max_retained
        if excess <= 0:
            return []

        deprecated = [tv for tv in versions if tv.status is ToolVersionStatus.DEPRECATED]
        unstamped = [tv for tv in deprecated if tv.last_stable_at is None]
        stamped = [tv for tv in deprecated if tv.last_stable_at is not None]

        unstamped.sort(key=lambda tv: tv.created_at)
        stamped.sort(key=lambda tv: tv.last_stable_at or tv.created_at)

        ordered = unstamped + stamped
        return [tv.version_id for tv in ordered[:excess]]


__all__ = [
    "RolloutDecision",
    "RolloutPolicyService",
    "TrafficRouter",
    "VersionRetentionPlanner",
]
