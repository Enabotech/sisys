"""Story 6-3 — CreateCheckpointUseCase 用例单元测试。

TDD 循环 B 载体：编排透传（参数逐项传抵服务）/plan_id UUID 守卫/
created_via 默认参（编程调用 "use_case"）/recovered 用例骨架（Task 3 载体）。
Mock 工厂（AsyncMock(spec=CheckpointServicePort)——单元测试 Mock 端口）。
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.create_checkpoint import CreateCheckpointUseCase


def _make_checkpoint_service_mock() -> Any:
    """Checkpoint 服务端口替身（AsyncMock(spec=CheckpointServicePort)）。"""
    from src.application.ports.checkpoint import CheckpointServicePort
    from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot

    service = AsyncMock(spec=CheckpointServicePort)
    service.create_checkpoint = AsyncMock(
        return_value=CheckpointSnapshot(
            session_id="blm-checkpoint-plan:CP-1",
            stage_id="performance_gap",
            checkpoint_no="CP-1",
            persistent_note_ref=str(uuid.uuid4()),
        )
    )
    return service


class TestCreateCheckpointUseCase:
    """创建用例（编排透传 + 参数守卫）。"""

    async def test_execute_passthrough_all_params(self) -> None:
        """execute 全参数透传至 create_checkpoint（薄透传零改写）。"""
        service = _make_checkpoint_service_mock()
        use_case = CreateCheckpointUseCase(checkpoint_service=service)

        await use_case.execute(
            plan_id=str(uuid.uuid4()),
            checkpoint_no="CP-1",
            stage_id="performance_gap",
            query="五年战略规划",
            retrieved_docs=[{"id": "c-1", "score": 0.9, "payload": {"content": "证据"}}],
            user_id="unit-executor",
            summary="阶段摘要",
        )

        service.create_checkpoint.assert_awaited_once()
        kwargs = service.create_checkpoint.await_args.kwargs
        assert kwargs["checkpoint_no"] == "CP-1"
        assert kwargs["stage_id"] == "performance_gap"
        assert kwargs["summary"] == "阶段摘要"
        assert kwargs["created_via"] == "use_case"  # 默认参（R7-5——用例层直调形态）

    async def test_execute_created_via_passthrough(self) -> None:
        """created_via 显式传参透传（CLI 入口固定传 "cli" 的通道——R6-4）。"""
        service = _make_checkpoint_service_mock()
        use_case = CreateCheckpointUseCase(checkpoint_service=service)

        await use_case.execute(
            plan_id=str(uuid.uuid4()),
            checkpoint_no="CP-1",
            stage_id="performance_gap",
            query="q",
            retrieved_docs=[],
            user_id="u",
            summary="s",
            completed=False,
            created_via="cli",
        )

        kwargs = service.create_checkpoint.await_args.kwargs
        assert kwargs["created_via"] == "cli"
        assert kwargs["completed"] is False

    async def test_execute_invalid_plan_id_raises_242(self) -> None:
        """plan_id 非 UUID 字符串 → EntityValidationError(242) 参数守卫。"""
        from src.domain.exceptions import EntityValidationError

        service = _make_checkpoint_service_mock()
        use_case = CreateCheckpointUseCase(checkpoint_service=service)

        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(
                plan_id="not-a-uuid",
                checkpoint_no="CP-1",
                stage_id="performance_gap",
                query="q",
                retrieved_docs=[],
                user_id="u",
                summary="s",
            )

        assert exc_info.value.code == "EXCEPTION_242"  # R1 审查 FR-11：拆双断言（原 OR 右支使 code 断言失锚）
        assert "plan_id" in str(exc_info.value.context)
        service.create_checkpoint.assert_not_awaited()

    async def test_execute_returns_snapshot(self) -> None:
        """execute 返回快照实体（服务产物直传）。"""
        service = _make_checkpoint_service_mock()
        use_case = CreateCheckpointUseCase(checkpoint_service=service)

        result = await use_case.execute(
            plan_id=str(uuid.uuid4()),
            checkpoint_no="CP-1",
            stage_id="performance_gap",
            query="q",
            retrieved_docs=[],
            user_id="u",
            summary="s",
        )

        assert result.checkpoint_no == "CP-1"


class TestRecoverCheckpointUseCase:
    """恢复用例（R1 审查 FR-17 补齐——透传 + 守卫对称 + 异常透传）。"""

    def _make_service_with_view(self) -> Any:
        """带恢复视图的服务替身（AsyncMock(spec=CheckpointServicePort)）。"""
        from src.application.ports.checkpoint import CheckpointRecoveryView, CheckpointServicePort
        from src.domain.entities.checkpoint import RecoveryMode

        service = AsyncMock(spec=CheckpointServicePort)
        service.recover_checkpoint = AsyncMock(
            return_value=CheckpointRecoveryView(
                checkpoint_no="CP-1",
                stage="performance_gap",
                recommended_mode=RecoveryMode.OVERRIDE,
            )
        )
        return service

    async def test_execute_passthrough_to_recover(self) -> None:
        """execute 透传 recover_checkpoint（薄透传——plan_id/checkpoint_no 原样传抵）。"""
        service = self._make_service_with_view()
        from src.application.use_cases.create_checkpoint import RecoverCheckpointUseCase

        use_case = RecoverCheckpointUseCase(checkpoint_service=service)
        plan_id = str(uuid.uuid4())

        view = await use_case.execute(plan_id=plan_id, checkpoint_no="CP-1")

        service.recover_checkpoint.assert_awaited_once()
        kwargs = service.recover_checkpoint.await_args.kwargs
        assert kwargs["plan_id"] == plan_id
        assert kwargs["checkpoint_no"] == "CP-1"
        assert view.checkpoint_no == "CP-1"

    async def test_execute_invalid_plan_id_raises_242(self) -> None:
        """plan_id 非 UUID → 242（守卫与创建用例对称——R1 审查 FR-17）。"""
        from src.application.use_cases.create_checkpoint import RecoverCheckpointUseCase
        from src.domain.exceptions import EntityValidationError

        service = self._make_service_with_view()
        use_case = RecoverCheckpointUseCase(checkpoint_service=service)

        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(plan_id="not-a-uuid", checkpoint_no="CP-1")

        assert exc_info.value.code == "EXCEPTION_242"
        service.recover_checkpoint.assert_not_awaited()

    async def test_execute_propagates_domain_errors(self) -> None:
        """恢复面领域异常透传（480/484 零包装——恢复三分语义在服务层承载）。"""
        from src.application.use_cases.create_checkpoint import RecoverCheckpointUseCase
        from src.domain.exceptions import CheckpointIntegrityError

        service = self._make_service_with_view()
        service.recover_checkpoint = AsyncMock(side_effect=CheckpointIntegrityError(reason="checksum_mismatch"))
        use_case = RecoverCheckpointUseCase(checkpoint_service=service)

        with pytest.raises(CheckpointIntegrityError) as exc_info:
            await use_case.execute(plan_id=str(uuid.uuid4()), checkpoint_no="CP-1")

        assert exc_info.value.code == "EXCEPTION_484"
