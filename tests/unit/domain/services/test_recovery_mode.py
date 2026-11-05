"""Story 6-3/6-6 — 恢复模式纯函数单元测试（recommend_recovery_mode + 转换/风险等级）。

TDD 循环 B 载体：≥2 → REPLAY 强制 / <2 → OVERRIDE 推荐边界全覆盖
（AC-7 判定纯函数——纯计算零副作用，双模式执行引擎归 6-6，OD-1）。
Story 6-6 扩展：to_event_recovery_mode 双枚举显式转换（entities 小写 →
events 大写——OD-9：两版成员值不等是代码事实，6-3 story L171 钦定注记兑现）
+ assess_consistency_risk 一致性风险等级同源计算（OD-5/R1-10：CLI dry-run
评估输出与引擎⑤步事件构造同源消费——单一事实源防双实现漂移）。
"""

from __future__ import annotations

import pytest

from src.domain.entities.checkpoint import RecoveryMode
from src.domain.events.enums import RecoveryMode as EventRecoveryMode


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


class TestToEventRecoveryMode:
    """双枚举显式转换纯函数（entities 小写 → events 大写——OD-9）。

    属性形态断裂族预防（6-1 三犯+6-3 再证）：entities 版 "replay"/"override"
    与 events 版 "Replay"/"Override" 成员值不等是代码事实——值级断言防只验类型。
    """

    def test_replay_maps_to_event_upper(self) -> None:
        """REPLAY → events 版 "Replay"（.value 值级断言——防只验枚举类型）。"""
        from src.domain.services.recovery_mode import to_event_recovery_mode

        result = to_event_recovery_mode(RecoveryMode.REPLAY)
        assert result is EventRecoveryMode.REPLAY
        assert result.value == "Replay", (
            f"转换实测值={result.value!r} 期望='Replay'（events 枚举首字母大写形态——CheckpointRecovered.recovery_mode 消费面）"
        )

    def test_override_maps_to_event_upper(self) -> None:
        """OVERRIDE → events 版 "Override"（.value 值级断言）。"""
        from src.domain.services.recovery_mode import to_event_recovery_mode

        result = to_event_recovery_mode(RecoveryMode.OVERRIDE)
        assert result is EventRecoveryMode.OVERRIDE
        assert result.value == "Override", f"转换实测值={result.value!r} 期望='Override'（events 枚举首字母大写形态）"

    def test_member_values_not_equal_across_dual_enums(self) -> None:
        """双枚举成员值不等事实锚（"replay"≠"Replay"——转换函数存在性论证）。"""
        assert RecoveryMode.REPLAY.value != EventRecoveryMode.REPLAY.value
        assert RecoveryMode.OVERRIDE.value != EventRecoveryMode.OVERRIDE.value

    def test_injective_mapping_preserves_distinction(self) -> None:
        """转换保持成员区分度（单射——REPLAY/OVERRIDE 映射后互异）。"""
        from src.domain.services.recovery_mode import to_event_recovery_mode

        replay_side = to_event_recovery_mode(RecoveryMode.REPLAY)
        override_side = to_event_recovery_mode(RecoveryMode.OVERRIDE)
        assert replay_side is not override_side
        assert replay_side.value != override_side.value


class TestAssessConsistencyRisk:
    """一致性风险等级纯函数（三分支矩阵逐支钉死——同源消费单一事实源）。

    矩阵：Override+有后续→"medium" / Override+无后续→"low" / Replay 全形态→
    "low"。medium 腿是同源消费漂移的唯一可判别腿（low 与 CheckpointRecovered.
    consistency_risk_level 默认值同值，Replay 腿不可判别漂移——Task 1.1 钉死）。
    """

    def test_override_with_one_subsequent_returns_medium(self) -> None:
        """Override+1 后续 → "medium"（唯一可判别腿——同源消费漂移哨兵）。"""
        from src.domain.services.recovery_mode import assess_consistency_risk

        result = assess_consistency_risk(RecoveryMode.OVERRIDE, 1)
        assert result == "medium", (
            f"Override+1 后续实测={result!r} 期望='medium'（待同步标记有一致性风险——CLI dry-run 与引擎⑤步同源计算）"
        )

    def test_override_with_zero_subsequent_returns_low(self) -> None:
        """Override+无后续 → "low"（单点恢复无下游影响）。"""
        from src.domain.services.recovery_mode import assess_consistency_risk

        assert assess_consistency_risk(RecoveryMode.OVERRIDE, 0) == "low"

    def test_replay_with_two_subsequent_returns_low(self) -> None:
        """Replay+≥2 后续 → "low"（强一致作废语义——后续全部重算无漂移面）。"""
        from src.domain.services.recovery_mode import assess_consistency_risk

        assert assess_consistency_risk(RecoveryMode.REPLAY, 2) == "low"

    def test_replay_with_zero_subsequent_returns_low(self) -> None:
        """Replay+0 后续 → "low"（边界值——空影响清单）。"""
        from src.domain.services.recovery_mode import assess_consistency_risk

        assert assess_consistency_risk(RecoveryMode.REPLAY, 0) == "low"

    def test_pure_function_deterministic(self) -> None:
        """纯计算零副作用（同输入重复调用同输出）。"""
        from src.domain.services.recovery_mode import assess_consistency_risk

        assert assess_consistency_risk(RecoveryMode.OVERRIDE, 1) == assess_consistency_risk(RecoveryMode.OVERRIDE, 1)
