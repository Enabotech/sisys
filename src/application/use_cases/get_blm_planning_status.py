"""应用层 BLM 规划状态查询用例（Story 6-1 — GetBlmPlanningStatusUseCase）

读侧用例（Task 2 循环 B——写入方唯一归 BlmPlanningService 各方法末尾，
本用例只读；「写读一致」断言由写入方测试与集成 Subtask 5.2 承载）。

三层键形态读取（DC-6）：BLM_PLANNING_SESSION_PREFIX 单源常量 →
session_id = f"blm-planning-{plan_id}" → 经快照存储端口 load（最终键
sisys:snapshot:blm-planning-{plan_id} 的 hget 在存储实现内部——用例只持
session_id，不自持 Redis 客户端）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.application.ports.blm_planning import (
    BLM_PLANNING_SESSION_PREFIX,
    BLM_PLANNING_SNAPSHOT_STAGE,
)
from src.domain.exceptions.planning_exceptions import PlanningNotFoundError
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
from src.domain.value_objects.blm_phases import (
    BlmPhase,
    BlmPlanningStatus,
    BlmTimelineEntry,
)


class GetBlmPlanningStatusUseCase:
    """BLM 规划状态查询用例（AC-3 流程可视化数据面读侧）。"""

    def __init__(self, snapshot_repository: SnapshotRepositoryProtocol) -> None:
        """构造状态查询用例。

        Args:
            snapshot_repository: 快照存储端口（load——hget latest 在存储内部）。
        """
        self._snapshot_repository = snapshot_repository

    async def execute(self, plan_id: str) -> BlmPlanningStatus:
        """查询规划状态（快照 latest 读取 + 反序列化）。

        Args:
            plan_id: 规划任务标识。

        Returns:
            BlmPlanningStatus 流程状态（phase/current_step/进度百分比/timeline）。

        Raises:
            PlanningNotFoundError: 480——plan_id 无快照记录（第三态显式失败）。
        """
        session_id = f"{BLM_PLANNING_SESSION_PREFIX}{plan_id}"
        snapshot = await self._snapshot_repository.load(session_id)
        if snapshot is None:
            raise PlanningNotFoundError(plan_id=plan_id)
        return self._deserialize(snapshot.state_data, plan_id=plan_id)

    def _deserialize(self, state_data: dict[str, Any], *, plan_id: str) -> BlmPlanningStatus:
        """快照 state_data → BlmPlanningStatus（序列化契约反序列化——SSOT 见端口文件）。

        Args:
            state_data: 快照存储 state_data dict（timeline 条目六键 dict 形态）。
            plan_id: 规划任务标识（校验锚）。

        Returns:
            BlmPlanningStatus 实例。
        """
        timeline = tuple(
            BlmTimelineEntry(
                step=entry["step"],
                started_at=datetime.fromisoformat(entry["started_at"]),
                completed_at=datetime.fromisoformat(entry["completed_at"]),
                status=entry.get("status", "completed"),
                summary_excerpt=entry.get("summary_excerpt", ""),
                degraded=bool(entry.get("degraded", False)),
            )
            for entry in state_data.get("timeline", [])
        )
        return BlmPlanningStatus(
            plan_id=state_data.get("plan_id", plan_id),
            phase=BlmPhase(state_data["phase"]),
            current_step=state_data.get("current_step", "performance_gap"),
            completed_steps=int(state_data["completed_steps"]),
            total_steps=int(state_data.get("total_steps", 8)),
            degraded_steps=tuple(state_data.get("degraded_steps", ())),
            timeline=timeline,
        )


__all__ = ["BLM_PLANNING_SNAPSHOT_STAGE", "GetBlmPlanningStatusUseCase"]
