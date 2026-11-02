"""应用层 Checkpoint 创建/恢复用例模块（Story 6-3）

CreateCheckpointUseCase——薄透传用例（OD-5 显式触发面：MVP 同步链下
"阶段完成即暂停等审批"物理不可达，由显式调用触发）：参数守卫（plan_id
UUID 校验）+ 编排透传（created_via 默认 "use_case"——编程调用形态；
CLI 入口显式传 "cli"，R6-4）。

RecoverCheckpointUseCase——恢复数据面用例（Task 2/3 钦定恢复用例骨架的
R1 审查 FR-17 补齐交付：6-6 审批/恢复执行面的 sanctioned 入口——CLI 节
「6-3 恢复数据面经用例层消费」为真；plan_id UUID 守卫与创建用例对称）。
"""

from __future__ import annotations

import uuid

from src.application.ports.checkpoint import CheckpointRecoveryView, CheckpointServicePort
from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot
from src.domain.exceptions import EntityValidationError
from src.domain.ports.l3_vector import SearchResult


class CreateCheckpointUseCase:
    """创建 Checkpoint 用例（参数守卫 + 编排服务透传）。"""

    def __init__(self, *, checkpoint_service: CheckpointServicePort) -> None:
        """初始化创建用例。

        Args:
            checkpoint_service: Checkpoint 编排服务端口（五步编排）。
        """
        self._checkpoint_service = checkpoint_service

    async def execute(
        self,
        *,
        plan_id: str,
        checkpoint_no: str,
        stage_id: str,
        query: str,
        retrieved_docs: list[SearchResult],
        user_id: str,
        summary: str,
        completed: bool = True,
        created_via: str = "use_case",
    ) -> CheckpointSnapshot:
        """执行 Checkpoint 创建（守卫 + 透传五步编排）。

        Args:
            plan_id: 规划任务标识（UUID 字符串——守卫校验；归档关联键同源）。
            checkpoint_no: 检查点编号（"CP-1".."CP-8"）。
            stage_id: 阶段标识（STAGE_VALUE_DOMAIN 值域）。
            query: 原始查询文本。
            retrieved_docs: 检索证据族（CLI 路径经空列表构造——实体抽取降级容忍）。
            user_id: 执行用户标识。
            summary: 阶段摘要（调用方直供）。
            completed: 完成状态（默认 True）。
            created_via: 触发源标识（默认 "use_case"；CLI 固定传 "cli"）。

        Returns:
            已落库的完整形态快照。

        Raises:
            EntityValidationError: 242——plan_id 非 UUID 字符串（参数守卫）。
            CheckpointCreationError: 483——五步编排强制环节失败（透传）。
        """
        # 参数守卫：plan_id 必须 UUID 字符串（归档 plan_id=UUID 入参前置校验）
        try:
            uuid.UUID(plan_id)
        except ValueError as error:
            raise EntityValidationError(
                message="plan_id 必须为 UUID 字符串",
                context={"use_case": "CreateCheckpointUseCase", "field": "plan_id", "plan_id": plan_id},
            ) from error

        return await self._checkpoint_service.create_checkpoint(
            plan_id=plan_id,
            checkpoint_no=checkpoint_no,
            stage_id=stage_id,
            query=query,
            retrieved_docs=retrieved_docs,
            user_id=user_id,
            summary=summary,
            completed=completed,
            created_via=created_via,
        )


class RecoverCheckpointUseCase:
    """恢复 Checkpoint 用例（参数守卫 + 恢复数据面透传——6-6 消费面入口）。

    Story File List「创建/恢复用例（Task 2/3）」的恢复半边（R1 审查 FR-17
    补齐——原实现缺失使 File List 声明失实）；恢复执行引擎（Replay/Override）
    归 6-6（OD-1），本用例只承载 load→verify→视图组装的数据面入口。
    """

    def __init__(self, *, checkpoint_service: CheckpointServicePort) -> None:
        """初始化恢复用例。

        Args:
            checkpoint_service: Checkpoint 编排服务端口（恢复方法组）。
        """
        self._checkpoint_service = checkpoint_service

    async def execute(self, *, plan_id: str, checkpoint_no: str) -> CheckpointRecoveryView:
        """执行 Checkpoint 恢复数据面（守卫 + 透传恢复视图组装）。

        Args:
            plan_id: 规划任务标识（UUID 字符串——守卫校验，与创建用例对称）。
            checkpoint_no: 恢复起点检查点编号（"CP-1".."CP-8"——服务层守卫）。

        Returns:
            恢复视图 DTO（6-6 审批/恢复执行面消费契约）。

        Raises:
            EntityValidationError: 242——plan_id 非 UUID 字符串（参数守卫）。
            PlanningNotFoundError: 480——键不存在（含 JSON 损坏同路径）。
            CheckpointIntegrityError: 484——checksum 校验失败（拒绝恢复）。
        """
        # 参数守卫：plan_id 必须 UUID 字符串（镜像创建用例——R1 审查 FR-17 对称性）
        try:
            uuid.UUID(plan_id)
        except ValueError as error:
            raise EntityValidationError(
                message="plan_id 必须为 UUID 字符串",
                context={"use_case": "RecoverCheckpointUseCase", "field": "plan_id", "plan_id": plan_id},
            ) from error

        return await self._checkpoint_service.recover_checkpoint(plan_id=plan_id, checkpoint_no=checkpoint_no)
