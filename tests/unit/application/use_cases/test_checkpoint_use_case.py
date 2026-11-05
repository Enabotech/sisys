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
        """恢复面领域异常透传（480/484 零包装——恢复三分语义在服务层承载）。

        R3-5 薄透传格豁免注记：Create 用例 483 透传/Recover 用例 480 透传
        两格不建独立用例——薄透传无自身逻辑+服务层全承载+242 守卫自测在位
        （R5-2 补可检索注记）。
        """
        from src.application.use_cases.create_checkpoint import RecoverCheckpointUseCase
        from src.domain.exceptions import CheckpointIntegrityError

        service = self._make_service_with_view()
        service.recover_checkpoint = AsyncMock(side_effect=CheckpointIntegrityError(reason="checksum_mismatch"))
        use_case = RecoverCheckpointUseCase(checkpoint_service=service)

        with pytest.raises(CheckpointIntegrityError) as exc_info:
            await use_case.execute(plan_id=str(uuid.uuid4()), checkpoint_no="CP-1")

        assert exc_info.value.code == "EXCEPTION_484"


class TestListCheckpointsUseCase:
    """摘要清单用例（Story 6-6 AC-1——UUID 守卫 + 薄透传）。"""

    def _make_service_with_summaries(self) -> Any:
        """带摘要清单的服务替身（AsyncMock(spec=CheckpointServicePort)）。"""
        from src.application.ports.checkpoint import CheckpointServicePort, CheckpointSummaryView

        service = AsyncMock(spec=CheckpointServicePort)
        service.list_checkpoints = AsyncMock(
            return_value=[
                CheckpointSummaryView(checkpoint_no="CP-1", stage_id="performance_gap", completed=True, summary="s1"),
                CheckpointSummaryView(checkpoint_no="CP-3", stage_id="performance_gap", completed=True, summary="s3"),
            ]
        )
        return service

    async def test_execute_passthrough_to_list(self) -> None:
        """execute 透传 list_checkpoints（薄透传——plan_id 原样传抵）。"""
        service = self._make_service_with_summaries()
        from src.application.use_cases.checkpoint_approval import ListCheckpointsUseCase

        use_case = ListCheckpointsUseCase(checkpoint_service=service)
        plan_id = str(uuid.uuid4())

        summaries = await use_case.execute(plan_id=plan_id)

        service.list_checkpoints.assert_awaited_once()
        kwargs = service.list_checkpoints.await_args.kwargs
        assert kwargs["plan_id"] == plan_id
        assert [s.checkpoint_no for s in summaries] == ["CP-1", "CP-3"]

    async def test_execute_invalid_plan_id_raises_242(self) -> None:
        """plan_id 非 UUID → 242（守卫与创建/恢复用例对称——plan_id UUID 守卫=用例层承载）。"""
        from src.application.use_cases.checkpoint_approval import ListCheckpointsUseCase
        from src.domain.exceptions import EntityValidationError

        service = self._make_service_with_summaries()
        use_case = ListCheckpointsUseCase(checkpoint_service=service)

        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(plan_id="not-a-uuid")

        assert exc_info.value.code == "EXCEPTION_242"
        assert "plan_id" in str(exc_info.value.context)
        service.list_checkpoints.assert_not_awaited()

    async def test_execute_empty_list_passthrough(self) -> None:
        """空清单透传（空族不抛 480——枚举面语义在服务层承载，用例层零包装）。"""
        service = self._make_service_with_summaries()
        service.list_checkpoints = AsyncMock(return_value=[])
        from src.application.use_cases.checkpoint_approval import ListCheckpointsUseCase

        use_case = ListCheckpointsUseCase(checkpoint_service=service)

        summaries = await use_case.execute(plan_id=str(uuid.uuid4()))

        assert summaries == []


class TestExecuteCheckpointRecoveryUseCase:
    """恢复执行用例（Story 6-6 AC-3——UUID 守卫 + confirmed_by 非空守卫 + 透传）。"""

    def _make_service_with_outcome(self) -> Any:
        """带恢复结果的服务替身（AsyncMock(spec=CheckpointServicePort)）。"""
        from src.application.ports.checkpoint import CheckpointRecoveryOutcome, CheckpointServicePort
        from src.domain.entities.checkpoint import RecoveryMode

        service = AsyncMock(spec=CheckpointServicePort)
        service.execute_recovery = AsyncMock(
            return_value=CheckpointRecoveryOutcome(
                checkpoint_no="CP-3",
                recovery_mode=RecoveryMode.OVERRIDE,
            )
        )
        return service

    async def test_execute_passthrough_with_correction_and_mode(self) -> None:
        """execute 透传 execute_recovery（correction/mode/confirmed_by/created_via 全参传抵）。"""
        service = self._make_service_with_outcome()
        from src.application.use_cases.checkpoint_approval import ExecuteCheckpointRecoveryUseCase
        from src.domain.entities.checkpoint import CorrectionRecord, RecoveryMode

        use_case = ExecuteCheckpointRecoveryUseCase(checkpoint_service=service)
        plan_id = str(uuid.uuid4())
        correction = CorrectionRecord(correction_type="L2", previous_value="a", new_value="b", applied_by="u")

        outcome = await use_case.execute(
            plan_id=plan_id,
            checkpoint_no="CP-3",
            correction=correction,
            mode=RecoveryMode.OVERRIDE,
            confirmed_by="高管",
            created_via="cli",
        )

        service.execute_recovery.assert_awaited_once()
        kwargs = service.execute_recovery.await_args.kwargs
        assert kwargs["plan_id"] == plan_id
        assert kwargs["checkpoint_no"] == "CP-3"
        assert kwargs["correction"] is correction
        assert kwargs["mode"] is RecoveryMode.OVERRIDE
        assert kwargs["confirmed_by"] == "高管"
        assert kwargs["created_via"] == "cli"
        assert outcome.checkpoint_no == "CP-3"

    async def test_execute_defaults_passthrough(self) -> None:
        """默认参透传（correction=None/mode=None/created_via="use_case"）。"""
        service = self._make_service_with_outcome()
        from src.application.use_cases.checkpoint_approval import ExecuteCheckpointRecoveryUseCase

        use_case = ExecuteCheckpointRecoveryUseCase(checkpoint_service=service)

        await use_case.execute(plan_id=str(uuid.uuid4()), checkpoint_no="CP-1", confirmed_by="x")

        kwargs = service.execute_recovery.await_args.kwargs
        assert kwargs["correction"] is None
        assert kwargs["mode"] is None
        assert kwargs["created_via"] == "use_case"

    async def test_execute_invalid_plan_id_raises_242(self) -> None:
        """plan_id 非 UUID → 242（守卫族对称）。"""
        from src.application.use_cases.checkpoint_approval import ExecuteCheckpointRecoveryUseCase
        from src.domain.exceptions import EntityValidationError

        service = self._make_service_with_outcome()
        use_case = ExecuteCheckpointRecoveryUseCase(checkpoint_service=service)

        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(plan_id="not-a-uuid", checkpoint_no="CP-1", confirmed_by="x")

        assert exc_info.value.code == "EXCEPTION_242"
        service.execute_recovery.assert_not_awaited()

    async def test_execute_empty_confirmed_by_raises_242(self) -> None:
        """confirmed_by 空串 → 242（审批人身份不可缺省空——AC-4 审批留痕前提）。"""
        from src.application.use_cases.checkpoint_approval import ExecuteCheckpointRecoveryUseCase
        from src.domain.exceptions import EntityValidationError

        service = self._make_service_with_outcome()
        use_case = ExecuteCheckpointRecoveryUseCase(checkpoint_service=service)

        with pytest.raises(EntityValidationError) as exc_info:
            await use_case.execute(plan_id=str(uuid.uuid4()), checkpoint_no="CP-1", confirmed_by="")

        assert exc_info.value.code == "EXCEPTION_242"
        assert "confirmed_by" in str(exc_info.value.context)
        service.execute_recovery.assert_not_awaited()
