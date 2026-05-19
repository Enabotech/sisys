"""Saga 编排器 - Saga 执行流程控制器

SagaOrchestrator 负责：
- 协调多个 SagaStep 的执行顺序
- 管理正向执行流程
- 触发补偿流程（逆向执行已成功步骤的 compensate）
- 更新 SagaContext 状态

设计原则：
- 每个 Saga 实例有独立的 Orchestrator
- 支持 UoW 模式（通过 SagaRepository 持久化）
- 补偿失败时标记为 FAILED 而非继续尝试

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Sequence
from uuid import UUID

from src.domain.ports.saga_context import SagaContext
from src.infrastructure.saga.saga_context import SagaContext as ConcreteSagaContext
from src.infrastructure.saga.saga_status import SagaStatus

if TYPE_CHECKING:
    from src.domain.ports.saga import SagaRepositoryProtocol, SagaStep

logger = logging.getLogger(__name__)


class SagaOrchestrator:
    """Saga 编排器

    协调多个 SagaStep 的执行和补偿流程

    Attributes:
        saga_id: Saga 实例唯一标识
        saga_type: Saga 类型标识符
        steps: 步骤列表（按执行顺序）
        context: 当前执行上下文
    """

    def __init__(
        self,
        saga_id: UUID,
        saga_type: str,
        steps: Sequence[SagaStep],
        repository: SagaRepositoryProtocol,
    ) -> None:
        """初始化 SagaOrchestrator

        Args:
            saga_id: Saga 实例唯一标识
            saga_type: Saga 类型标识符
            steps: 步骤列表（按执行顺序）
            repository: Saga 持久化仓储

        Raises:
            ValueError: steps 为空列表时抛出
        """
        if not steps:
            raise ValueError("steps 不能为空列表")
        self.saga_id = saga_id
        self.saga_type = saga_type
        self._steps = steps
        self._repository = repository
        self._context: SagaContext = ConcreteSagaContext(
            saga_id=saga_id,
            saga_type=saga_type,
            status=SagaStatus.PENDING,
        )

    @property
    def context(self) -> SagaContext:
        """获取当前执行上下文。"""
        return self._context

    @property
    def steps(self) -> Sequence[SagaStep]:
        """获取步骤列表。"""
        return self._steps

    async def execute(self) -> SagaContext:
        """执行 Saga 流程

        正向执行所有步骤，若中间步骤失败则触发补偿流程

        Returns:
            执行完成后的 SagaContext
        """
        self._context = self._context.update_status(SagaStatus.RUNNING)
        await self._repository.save(self._context)

        for index, step in enumerate(self._steps):
            try:
                logger.info("Saga %s: executing step %s", self.saga_id, step.name)
                updated_context = await step.execute(self._context)
                self._context = updated_context
                self._context = self._context.set_step_data(step.name, None, updated_context)
                self._context = self._context.advance_step(len(self._steps))
                await self._repository.save(self._context)
            except Exception as e:
                logger.error("Saga %s: step %s failed: %s", self.saga_id, step.name, e)
                self._context = self._context.add_error(step.name, str(e))
                return await self._compensate(index)

        self._context = self._context.update_status(SagaStatus.COMPLETED)
        await self._repository.save(self._context)
        logger.info("Saga %s: completed successfully", self.saga_id)
        return self._context

    async def _compensate(self, failed_index: int) -> SagaContext:
        """补偿已成功的步骤（从失败步骤前一个开始逆向执行）

        Args:
            failed_index: 失败步骤的索引

        Returns:
            补偿完成后的 SagaContext
        """
        if failed_index == 0:
            self._context = self._context.add_error(
                "_compensate",
                "没有可补偿的步骤，直接标记为 FAILED",
            )
            self._context = self._context.update_status(SagaStatus.FAILED)
            await self._repository.save(self._context)
            return self._context

        self._context = self._context.update_status(SagaStatus.COMPENSATING)
        compensation_failed = False

        for index in range(failed_index - 1, -1, -1):
            step = self._steps[index]
            try:
                logger.info("Saga %s: compensating step %s", self.saga_id, step.name)
                await step.compensate(self._context)
            except Exception as e:
                logger.error("Saga %s: compensation failed for step %s: %s", self.saga_id, step.name, e)
                self._context = self._context.add_error(f"{step.name}_compensation", str(e))
                compensation_failed = True
                break

        if compensation_failed:
            self._context = self._context.update_status(SagaStatus.FAILED)
        else:
            self._context = self._context.update_status(SagaStatus.COMPENSATED)

        await self._repository.save(self._context)
        return self._context
