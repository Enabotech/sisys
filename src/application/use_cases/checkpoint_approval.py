"""应用层 Checkpoint 审批面用例模块（Story 6-6）

摘要清单与恢复执行两用例（薄透传+守卫——CreateCheckpointUseCase/
RecoverCheckpointUseCase 双先例粒度）：

- ListCheckpointsUseCase：plan_id UUID 守卫 + list_checkpoints 透传
  （AC-1 清单面——枚举语义零包装，空族空清单不抛 480）。
- ExecuteCheckpointRecoveryUseCase：plan_id UUID 守卫 + confirmed_by 非空
  守卫 242 + execute_recovery 透传（AC-3 执行面）。四参数成组校验不在
  本层承载：CorrectionRecord 默认值兜底下部分出现到用例层不可表达，
  成组约束唯一落位 = CLI 层 post-parse 检测（AC-2 裁定）。
"""

from __future__ import annotations

import uuid

from src.application.ports.checkpoint import CheckpointRecoveryOutcome, CheckpointServicePort, CheckpointSummaryView
from src.domain.entities.checkpoint import CorrectionRecord, RecoveryMode
from src.domain.exceptions import EntityValidationError


class ListCheckpointsUseCase:
    """摘要清单用例（AC-1——plan_id UUID 守卫 + 薄透传）。"""

    def __init__(self, *, checkpoint_service: CheckpointServicePort) -> None:
        """初始化摘要清单用例。

        Args:
            checkpoint_service: Checkpoint 编排服务端口（list_checkpoints 消费面）。
        """
        self._checkpoint_service = checkpoint_service

    async def execute(self, *, plan_id: str) -> list[CheckpointSummaryView]:
        """执行摘要清单查询（守卫 + 透传）。

        Args:
            plan_id: 规划任务标识（UUID 字符串）。

        Returns:
            摘要视图清单（checkpoint_no 升序；空族空清单）。

        Raises:
            EntityValidationError: 242——plan_id 非 UUID 字符串。
        """
        try:
            uuid.UUID(plan_id)
        except ValueError as error:
            raise EntityValidationError(
                message="plan_id 必须为 UUID 字符串",
                context={"use_case": "ListCheckpointsUseCase", "field": "plan_id", "plan_id": plan_id},
            ) from error
        return await self._checkpoint_service.list_checkpoints(plan_id=plan_id)


class ExecuteCheckpointRecoveryUseCase:
    """恢复执行用例（AC-3——UUID/confirmed_by 双守卫 + 透传）。"""

    def __init__(self, *, checkpoint_service: CheckpointServicePort) -> None:
        """初始化恢复执行用例。

        Args:
            checkpoint_service: Checkpoint 编排服务端口（execute_recovery 消费面）。
        """
        self._checkpoint_service = checkpoint_service

    async def execute(
        self,
        *,
        plan_id: str,
        checkpoint_no: str,
        correction: CorrectionRecord | None = None,
        mode: RecoveryMode | None = None,
        confirmed_by: str = "",
        created_via: str = "use_case",
    ) -> CheckpointRecoveryOutcome:
        """执行恢复（守卫链 + 透传——引擎假设调用方已确认，dry-run 在接口层拦截）。

        Args:
            plan_id: 规划任务标识（UUID 字符串）。
            checkpoint_no: 恢复起点检查点编号。
            correction: 关键参数修正（None=纯恢复）。
            mode: 显式恢复模式（None=引擎建议）。
            confirmed_by: 审批人标识（非空强制——审批身份不可缺省空）。
            created_via: 触发源标识（"cli"/"use_case"）。

        Returns:
            恢复执行结果（10 键 Outcome）。

        Raises:
            EntityValidationError: 242——plan_id 非 UUID 或 confirmed_by 空串。
        """
        try:
            uuid.UUID(plan_id)
        except ValueError as error:
            raise EntityValidationError(
                message="plan_id 必须为 UUID 字符串",
                context={"use_case": "ExecuteCheckpointRecoveryUseCase", "field": "plan_id", "plan_id": plan_id},
            ) from error
        if not confirmed_by:
            raise EntityValidationError(
                message="confirmed_by 不可为空（审批人身份必填——AC-4 审批留痕前提）",
                context={
                    "use_case": "ExecuteCheckpointRecoveryUseCase",
                    "field": "confirmed_by",
                    "confirmed_by": confirmed_by,
                },
            )
        return await self._checkpoint_service.execute_recovery(
            plan_id=plan_id,
            checkpoint_no=checkpoint_no,
            correction=correction,
            mode=mode,
            confirmed_by=confirmed_by,
            created_via=created_via,
        )
