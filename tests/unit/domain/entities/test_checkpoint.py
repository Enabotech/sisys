"""Tests for Checkpoint domain entity."""

import uuid
from typing import cast

import pytest

from src.domain.entities.checkpoint import Checkpoint, CheckpointStatus, RecoveryMode
from src.domain.exceptions import EntityStateTransitionError, EntityValidationError


def _make_checkpoint(**kwargs) -> Checkpoint:
    """Factory helper for Checkpoint."""
    defaults: dict = {
        "checkpoint_id": uuid.uuid4(),
        "phase_identifier": "phase-1",
    }
    defaults.update(kwargs)
    return Checkpoint(**defaults)


class TestCheckpointCreation:
    """Test Checkpoint entity creation."""

    def test_create_minimal_checkpoint(self):
        """Can create a checkpoint with minimal arguments."""
        cp = _make_checkpoint()
        assert cp.checkpoint_id is not None
        assert cp.phase_identifier == "phase-1"
        assert cp.status == CheckpointStatus.PENDING
        assert cp.recovery_mode is None

    def test_checkpoint_has_empty_correction_records(self):
        """Checkpoint starts with empty correction records."""
        cp = _make_checkpoint()
        assert cp.correction_records == []


class TestCheckpointValidation:
    """Test Checkpoint invariant validation."""

    def test_valid_checkpoint_passes(self):
        """Correctly constructed checkpoint passes validation."""
        cp = _make_checkpoint()
        assert cp.validate() is True

    def test_invalid_id_fails(self):
        """Checkpoint with non-UUID id fails validation."""
        cp = _make_checkpoint()
        object.__setattr__(cp, "checkpoint_id", cast(uuid.UUID, "not-a-uuid"))
        with pytest.raises(EntityValidationError, match="checkpoint_id must be a valid UUID"):
            cp.validate()

    def test_empty_phase_identifier_fails(self):
        """Checkpoint with empty phase_identifier fails validation."""
        cp = _make_checkpoint(phase_identifier="")
        with pytest.raises(EntityValidationError, match="phase_identifier must not be empty"):
            cp.validate()

    def test_invalid_status_fails(self):
        """Checkpoint with invalid status fails validation."""
        cp = _make_checkpoint()
        object.__setattr__(cp, "status", cast(CheckpointStatus, "invalid_status"))
        with pytest.raises(EntityValidationError, match="status must be a valid CheckpointStatus"):
            cp.validate()


class TestCheckpointTransitions:
    """Test Checkpoint state transitions."""

    def test_complete_checkpoint(self):
        """Can complete a checkpoint."""
        cp = _make_checkpoint()
        cp.complete()
        assert cp.status == CheckpointStatus.COMPLETED
        assert cp.completed_at is not None

    def test_recover_checkpoint_replay(self):
        """Can recover a checkpoint in REPLAY mode."""
        cp = _make_checkpoint()
        cp.recover(RecoveryMode.REPLAY)
        assert cp.status == CheckpointStatus.RECOVERED
        assert cp.recovery_mode == RecoveryMode.REPLAY

    def test_recover_checkpoint_override(self):
        """Can recover a checkpoint in OVERRIDE mode."""
        cp = _make_checkpoint()
        cp.recover(RecoveryMode.OVERRIDE)
        assert cp.status == CheckpointStatus.RECOVERED
        assert cp.recovery_mode == RecoveryMode.OVERRIDE

    def test_cannot_complete_twice(self):
        """P1-01 Fix: Cannot complete an already completed checkpoint."""
        cp = _make_checkpoint()
        cp.complete()
        with pytest.raises(EntityStateTransitionError, match="already completed"):
            cp.complete()

    def test_cannot_recover_completed_checkpoint(self):
        """P1-02 Fix: Cannot recover a completed checkpoint."""
        cp = _make_checkpoint()
        cp.complete()
        with pytest.raises(EntityStateTransitionError, match="Cannot recover"):
            cp.recover(RecoveryMode.REPLAY)


class TestCheckpointAggregationActivation:
    """Story 6-3 — Epic 1 骨架聚合激活验证（6-3 是首个生产消费方）。

    聚合驱动点钦定（OD-12 附则 a）：创建面④内 complete()（仅 completed=True）/
    修正面 apply_correction（经 state_data.correction_history 键投影——R6-8）/
    恢复面只读不驱动 recover()（R2A-4——243 陷阱防线）。本类验证激活前置：
    守卫行为 + CorrectionRecord 序列化投影（correction_history 键承载形态）。
    """

    def test_correction_record_five_fields_roundtrip_projection(self):
        """CorrectionRecord 五字段 dict 投影（correction_history 键承载——R8-F5 asdict 等价形态）。"""
        from dataclasses import asdict

        from src.domain.entities.checkpoint import CorrectionRecord

        record = CorrectionRecord(
            correction_type="key_param",
            previous_value="营收目标达成率 87%",
            new_value="营收目标达成率 90%",
            applied_by="acceptance-executor",
        )

        projection = asdict(record)
        assert set(projection.keys()) == {
            "correction_type",
            "previous_value",
            "new_value",
            "applied_by",
            "applied_at",
        }
        # applied_at 经 isoformat 字符串化入键的投影断言在服务单测（history[0]["applied_at"]
        # is str——R1 审查 FR-11：本行原 isoformat() 恒 str 恒真陪衬，删除）

    def test_correction_record_no_correction_id_field(self):
        """correction_id 仅 docstring 提及无字段（R1-F5 定谳——五字段 MVP 子集差异注记）。"""
        from src.domain.entities.checkpoint import CorrectionRecord

        record = CorrectionRecord(correction_type="t")
        assert not hasattr(record, "correction_id")

    def test_checkpoint_aggregate_accepts_correction_records(self):
        """聚合承载修正记录列表（correction_records 字段族——修正面构造面激活）。"""
        from src.domain.entities.checkpoint import CorrectionRecord

        cp = _make_checkpoint(
            correction_records=[
                CorrectionRecord(correction_type="k1", previous_value="a", new_value="b", applied_by="exec"),
            ]
        )
        assert len(cp.correction_records) == 1
        assert cp.correction_records[0].new_value == "b"
        assert cp.validate() is True

    def test_in_progress_checkpoint_aggregate_kept(self):
        """IN_PROGRESS 聚合（completed=False 创建面保持——不调 complete()）。

        R1 审查 FR-13：原两用例以测试内自建映射表自查（恒真陪衬），真实映射
        覆盖由服务单测 test_build_snapshot_incompleted_maps_false（state_data.
        completed=False）+ complete() 守卫路径承载——此处保留聚合状态面断言。
        """
        cp = _make_checkpoint(status=CheckpointStatus.IN_PROGRESS)
        assert cp.status == CheckpointStatus.IN_PROGRESS  # completed=False 时聚合保持 IN_PROGRESS 不调 complete()
