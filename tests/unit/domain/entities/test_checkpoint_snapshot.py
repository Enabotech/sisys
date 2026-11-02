"""Tests for CheckpointSnapshot domain entity."""

import uuid
from dataclasses import replace
from typing import Any

import pytest

from src.domain.entities.checkpoint_snapshot import CheckpointSnapshot


def _make_complete_state_data() -> dict[str, Any]:
    """完整形态 state_data 13 键（Task 0.2 冻结键族——期望值独立构造）。"""
    return {
        "checkpoint_no": "CP-1",
        "stage_id": "performance_gap",
        "stage_number": 1,
        "plan_id": "plan-1",
        "completed": True,
        "summary": "阶段摘要（直供）",
        "compressed_context": "压缩后的战略语境摘要",
        "compression_ratio": 0.85,
        "quality_score": 0.82,
        "token_count": 320,
        "persistent_note_ref": "note-ref-1",
        "correction_history": [],
        "created_via": "use_case",
    }


def _make_complete_snapshot() -> CheckpointSnapshot:
    """完整形态快照工厂（新四字段填充——Story 6-3 扩展形态；确定性默认值）。"""
    return CheckpointSnapshot(
        session_id="blm-checkpoint-plan-1:CP-1",
        stage_id="performance_gap",
        state_version=0,
        checkpoint_no="CP-1",
        persistent_note_ref=str(uuid.uuid5(uuid.NAMESPACE_URL, "note-ref-complete-form")),
        snapshot_metadata={
            "compression_ratio": 0.85,
            "quality_score": 0.82,
            "token_count": 320,
            "original_token_count": 2100,
            "rerun_count": 0,
        },
        state_data=_make_complete_state_data(),
    )


def _make_sealed_snapshot() -> CheckpointSnapshot:
    """封印快照工厂（checksum 显式计算写入——AC-3 初始化链：编排④步显式计算）。"""
    snapshot = _make_complete_snapshot()
    return replace(snapshot, checksum=snapshot.calculate_checksum())


class TestCheckpointSnapshot:
    """TDD tests for CheckpointSnapshot entity."""

    def test_create_snapshot_with_required_fields(self) -> None:
        """RED: CheckpointSnapshot should be creatable with session_id."""
        session_id = "test-session-123"
        snapshot = CheckpointSnapshot(session_id=session_id)

        assert snapshot.session_id == session_id
        assert snapshot.snapshot_id is not None
        assert isinstance(snapshot.snapshot_id, uuid.UUID)
        assert snapshot.state_version == 0
        assert snapshot.state_data == {}
        assert snapshot.stage_id == ""

    def test_with_updated_state_creates_new_snapshot(self) -> None:
        """RED: with_updated_state should create new snapshot with merged state."""
        original = CheckpointSnapshot(
            session_id="test-session",
            stage_id="planning",
            state_version=1,
            state_data={"original_key": "original_value"},
        )

        updated = original.with_updated_state({"new_key": "new_value"})

        assert updated.session_id == original.session_id
        assert updated.stage_id == original.stage_id
        assert updated.state_version == 2
        assert updated.state_data["original_key"] == "original_value"
        assert updated.state_data["new_key"] == "new_value"
        assert updated.snapshot_id != original.snapshot_id

    def test_snapshot_immutability(self) -> None:
        """RED: CheckpointSnapshot should be immutable (frozen dataclass)."""
        snapshot = CheckpointSnapshot(session_id="test-session")
        field_name = "session_id"

        # Using setattr with string to bypass mypy's property check
        # This tests that frozen dataclass raises FrozenInstanceError
        with pytest.raises(Exception):
            setattr(snapshot, field_name, "changed-session")


class TestCheckpointSnapshotCompleteForm:
    """Story 6-3 完整形态扩展——新四字段默认值/守卫/checksum/verify_integrity/透传。"""

    def test_new_fields_default_values_backward_compatible(self) -> None:
        """既有构造零参通过（新四字段默认值——6-1/6-2/5-10 三消费面向后兼容）。"""
        snapshot = CheckpointSnapshot(session_id="legacy-session")

        assert snapshot.persistent_note_ref == ""
        assert snapshot.checksum == ""  # 空串默认不自动算（AC-3——编排④步显式计算）
        assert snapshot.snapshot_metadata == {}
        assert snapshot.checkpoint_no == ""

    def test_complete_form_populated_construction(self) -> None:
        """完整形态填充构造（四新字段与 13 键 state_data）。"""
        snapshot = _make_complete_snapshot()

        assert snapshot.checkpoint_no == "CP-1"
        assert snapshot.persistent_note_ref
        assert snapshot.snapshot_metadata["compression_ratio"] == 0.85
        assert set(snapshot.state_data.keys()) == {
            "checkpoint_no",
            "stage_id",
            "stage_number",
            "plan_id",
            "completed",
            "summary",
            "compressed_context",
            "compression_ratio",
            "quality_score",
            "token_count",
            "persistent_note_ref",
            "correction_history",
            "created_via",
        }

    def test_guard_empty_note_ref_with_checkpoint_no_raises_484(self) -> None:
        """空 persistent_note_ref + checkpoint_no 非空 → 构造抛 484（进入完整形态即校验——AC-2）。"""
        from src.domain.exceptions import CheckpointIntegrityError

        with pytest.raises(CheckpointIntegrityError) as exc_info:
            CheckpointSnapshot(
                session_id="blm-checkpoint-plan-1:CP-1",
                stage_id="performance_gap",
                checkpoint_no="CP-1",
                persistent_note_ref="",
            )

        assert exc_info.value.code == "EXCEPTION_484"

    def test_guard_not_triggered_for_legacy_form(self) -> None:
        """守卫双条件限定——checkpoint_no 空（6-1/6-2 既有全默认构造）不触发（R2A-11 防误触发）。"""
        snapshot = CheckpointSnapshot(session_id="legacy", stage_id="planning", persistent_note_ref="")

        assert snapshot.checkpoint_no == ""  # legacy 形态构造成功（守卫不触发）

    def test_checksum_deterministic_and_snapshot_id_excluded(self) -> None:
        """calculate_checksum 确定性（同输入同输出；snapshot_id 不参与——每次更新轮换）。"""
        first = _make_complete_snapshot()
        second = _make_complete_snapshot()  # snapshot_id 不同（uuid4 默认工厂）

        assert first.calculate_checksum() == second.calculate_checksum()

    def test_checksum_normalized_against_state_data_key_order(self) -> None:
        """state_data 键序无关（sort_keys=True 规范化序列化——OD-11）。"""
        base = _make_complete_snapshot()
        reordered = replace(base, state_data=dict(reversed(list(base.state_data.items()))))

        assert base.calculate_checksum() == reordered.calculate_checksum()

    def test_checksum_participating_fields_full_coverage(self) -> None:
        """checksum 参与字段集全覆盖（身份五字段+state_data——逐字段突变使 checksum 变化）。"""
        base = _make_complete_snapshot()
        base_checksum = base.calculate_checksum()

        mutations = (
            replace(base, session_id="blm-checkpoint-plan-1:CP-2"),
            replace(base, stage_id="market_insight_trend"),
            replace(base, state_version=base.state_version + 1),
            replace(base, checkpoint_no="CP-2"),
            replace(base, persistent_note_ref=str(uuid.uuid4())),
            replace(base, state_data={**base.state_data, "compressed_context": "被篡改的上下文"}),
        )
        for index, mutated in enumerate(mutations):
            assert mutated.calculate_checksum() != base_checksum, f"参与字段 #{index} 突变未引起 checksum 变化"

    def test_verify_integrity_roundtrip_green(self) -> None:
        """round-trip 绿（checksum 显式写入后 verify True——AC-3）。"""
        assert _make_sealed_snapshot().verify_integrity() is True

    def test_verify_integrity_legacy_form_false(self) -> None:
        """legacy 形态（无 note_ref/checksum）verify False（缺失引用纯判定分支——不抛）。"""
        assert CheckpointSnapshot(session_id="legacy", stage_id="planning").verify_integrity() is False

    def test_verify_integrity_tampered_state_data_red(self) -> None:
        """篡改 state_data 任一键 → verify False（载荷参与 checksum 的直接可达性——OD-11）。"""
        sealed = _make_sealed_snapshot()

        tampering: list[tuple[str, Any]] = [
            ("compressed_context", "被篡改的压缩上下文"),
            ("summary", "被篡改的摘要"),
            ("correction_history", [{"correction_type": "fake"}]),
        ]
        for key, value in tampering:
            tampered_state = dict(sealed.state_data)
            tampered_state[key] = value
            tampered = replace(sealed, state_data=tampered_state)
            assert tampered.verify_integrity() is False, f"篡改 state_data.{key} 后 verify 仍绿"

    def test_verify_integrity_tampered_identity_fields_red(self) -> None:
        """替换 persistent_note_ref / 篡改实体顶层 checkpoint_no / 篡改 checksum → verify False。"""
        sealed = _make_sealed_snapshot()

        assert replace(sealed, persistent_note_ref=str(uuid.uuid4())).verify_integrity() is False
        assert replace(sealed, checkpoint_no="CP-8").verify_integrity() is False
        assert replace(sealed, checksum="0" * 64).verify_integrity() is False

    def test_verify_integrity_is_pure_judgment(self) -> None:
        """verify_integrity 纯判定无副作用（不修改实体字段、不抛异常——签名与行为一致）。"""
        sealed = _make_sealed_snapshot()

        result = sealed.verify_integrity()

        assert result is True
        assert sealed.checksum == sealed.calculate_checksum()  # 未被写回

    def test_with_updated_state_carries_new_fields(self) -> None:
        """with_updated_state 透传新字段（persistent_note_ref/snapshot_metadata/checkpoint_no——R2A-3 修正通道防丢字段）。"""
        sealed = _make_sealed_snapshot()

        updated = sealed.with_updated_state({"correction_history": [{"correction_type": "key_param"}]})

        assert updated.persistent_note_ref == sealed.persistent_note_ref
        assert updated.snapshot_metadata == sealed.snapshot_metadata
        assert updated.checkpoint_no == sealed.checkpoint_no
        assert updated.checksum == ""  # 不透传（服务层重算点——AC-3）
        assert updated.state_data["correction_history"] == [{"correction_type": "key_param"}]

    def test_checksum_algorithm_sha256_hexdigest(self) -> None:
        """checksum 算法 SHA-256 hexdigest（64 位十六进制——标准库 hashlib，domain 零依赖合规）。"""
        checksum = _make_complete_snapshot().calculate_checksum()

        assert len(checksum) == 64
        int(checksum, 16)  # 全部为合法十六进制字符（否则 ValueError）
