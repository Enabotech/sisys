"""Story 6-3 — 恢复模式判定纯函数单元测试（recommend_recovery_mode）。

TDD 循环 B 载体：≥2 → REPLAY 强制 / <2 → OVERRIDE 推荐边界全覆盖
（AC-7 判定纯函数——纯计算零副作用，双模式执行引擎归 6-6，OD-1）。
"""

from __future__ import annotations

import pytest

from src.domain.entities.checkpoint import RecoveryMode


class TestRecommendRecoveryMode:
    """影响评估判定纯函数（0/1→OVERRIDE、≥2→REPLAY——边界值 2 恰好强制）。"""

    def test_zero_subsequent_recommends_override(self) -> None:
        """0 个后续 Checkpoint → OVERRIDE 推荐（单点修正影响面小）。"""
        from src.domain.services.recovery_mode import recommend_recovery_mode

        assert recommend_recovery_mode(0) is RecoveryMode.OVERRIDE

    def test_one_subsequent_recommends_override(self) -> None:
        """1 个后续 Checkpoint → OVERRIDE 推荐。"""
        from src.domain.services.recovery_mode import recommend_recovery_mode

        assert recommend_recovery_mode(1) is RecoveryMode.OVERRIDE

    def test_two_subsequent_forces_replay(self) -> None:
        """恰 2 个后续 Checkpoint → REPLAY 强制（边界值——突变实证锚）。"""
        from src.domain.services.recovery_mode import recommend_recovery_mode

        assert recommend_recovery_mode(2) is RecoveryMode.REPLAY

    def test_three_subsequent_forces_replay(self) -> None:
        """3 个后续 Checkpoint → REPLAY 强制。"""
        from src.domain.services.recovery_mode import recommend_recovery_mode

        assert recommend_recovery_mode(3) is RecoveryMode.REPLAY

    def test_ten_subsequent_forces_replay(self) -> None:
        """10 个后续 Checkpoint → REPLAY 强制（值域上限 7 之外的健壮性）。"""
        from src.domain.services.recovery_mode import recommend_recovery_mode

        assert recommend_recovery_mode(10) is RecoveryMode.REPLAY

    def test_returns_existing_recovery_mode_enum(self) -> None:
        """返回既有 RecoveryMode 枚举（Epic 1 骨架——小写成员值，零新建类型）。"""
        from src.domain.services.recovery_mode import recommend_recovery_mode

        result = recommend_recovery_mode(1)
        assert isinstance(result, RecoveryMode)
        assert result.value == "override"
        assert recommend_recovery_mode(2).value == "replay"

    def test_negative_count_raises_entity_validation_error(self) -> None:
        """负数非法入参 → EntityValidationError（影响范围计数不可为负——fail-loud）。"""
        from src.domain.exceptions import EntityValidationError
        from src.domain.services.recovery_mode import recommend_recovery_mode

        with pytest.raises(EntityValidationError):
            recommend_recovery_mode(-1)

    def test_pure_function_no_side_effects(self) -> None:
        """纯计算零副作用（同输入重复调用同输出——无内部状态）。"""
        from src.domain.services.recovery_mode import recommend_recovery_mode

        first = recommend_recovery_mode(2)
        second = recommend_recovery_mode(2)
        assert first is second is RecoveryMode.REPLAY
