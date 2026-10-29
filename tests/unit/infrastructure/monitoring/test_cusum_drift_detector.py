"""CUSUMDriftDetector 单元测试——Story 5.9 双侧累积和漂移检测核心。

覆盖面（三循环）：循环 A 预热基线 + 双侧累积和手算锚 + 常量单源；循环 B N中M
确认（含当前样本条件）+ 分级 + 确认后复位 + 防御面（degenerate/入参域/上漂/
moderate 档/边界三形态）；循环 C trigger_recalibration 事件发布（Task 3 追加）。

浮点断言纪律（R1 钉死）：全部数值断言用同式 Python 表达式（σ₀ 经
statistics.stdev(baseline) 实算）——禁 k 写死 0.05 的假红形态（σ₀=√(0.3/29)
≈0.1017 非 0.1）、禁 pytest.approx（仓内无先例——纪律是精确等式+同式表达式）、
禁十进制字面量；上漂锚 n≥6 一律区间比较（闭式与逐次累加差 1ulp——R3 钉死）。

Run with:
    poetry run pytest tests/unit/infrastructure/monitoring/test_cusum_drift_detector.py -v
"""

from __future__ import annotations

import statistics
from typing import Any

import pytest

from src.domain.exceptions import ValidationError
from src.infrastructure.monitoring.cusum_detector import (
    CONFIRMATION_M,
    CONFIRMATION_N,
    H_MULTIPLIER,
    K_MULTIPLIER,
    METRIC_NAME,
    WARMUP_SAMPLES,
    CUSUMDriftDetector,
)

#: 手算锚基线序列（[0.7, 0.9]×15——μ₀=0.8，σ₀ 实算 ≈0.1017）
_BASELINE = [0.7, 0.9] * 15

#: 漂移注入值（下漂锚——Sₗ 增量 = 0.8 - 0.5×σ₀ - 0.4 ≈ 0.349）
_DOWN = 0.4


def _sigma0() -> float:
    """基线 σ₀ 实算（statistics.stdev[ddof=1]——同式单源）。"""
    return statistics.stdev(_BASELINE)


def _feed(detector: CUSUMDriftDetector, scores: list[float]) -> list[Any]:
    """逐样本灌入（pytest-asyncio auto 模式下同步驱动——update 是 async）。"""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return [loop.run_until_complete(detector.update(score)) for score in scores]
    finally:
        loop.close()


def _down_increment() -> float:
    """下漂单步增量同式表达（μ₀ - k - x——钦定形态）。"""
    return 0.8 - 0.5 * _sigma0() - _DOWN


def _up_increment() -> float:
    """上漂单步增量同式表达（x - μ₀ - k）。"""
    return 0.95 - 0.8 - 0.5 * _sigma0()


class TestModuleConstants:
    """常量单源六项断言（附录 I 钦定值——防参数漂移）。"""

    def test_constants_locked_to_appendix(self) -> None:
        """六常量值锁定（§29.3.1.1 参数 + §29.3.2.2 警告级 + §29.2.3.2 样本量）。"""
        assert METRIC_NAME == "overall_score"
        assert K_MULTIPLIER == 0.5
        assert H_MULTIPLIER == 5.0
        assert CONFIRMATION_N == 3
        assert CONFIRMATION_M == 5
        assert WARMUP_SAMPLES == 30


class TestWarmupBaseline:
    """循环 A：预热期行为（前 30 样本——统计手算对照 + N=1 钉死）。"""

    def test_warmup_phase_not_ready_not_drifted(self) -> None:
        """前 30 样本 baseline_ready=False + is_drifted=False + 计数递增。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE)
        for index, assessment in enumerate(assessments):
            assert assessment.baseline_ready is False, f"样本 {index + 1} 预热期 baseline_ready 应 False"
            assert assessment.is_drifted is False
            assert assessment.sample_count == index + 1

    def test_warmup_running_statistics(self) -> None:
        """预热统计手算对照（前 i 样本 mean/stdev——逐样本演进）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE)
        for index, assessment in enumerate(assessments):
            window = _BASELINE[: index + 1]
            assert assessment.baseline_mean == statistics.mean(window)
            if index == 0:
                assert assessment.baseline_std == 0.0, "N=1 时 baseline_std 应 0.0（stdev 需 ≥2 样本）"
            else:
                assert assessment.baseline_std == statistics.stdev(window)

    def test_sample30_returns_full_window_statistics(self) -> None:
        """第 30 样本返回 30 样本窗统计（先入窗后统计——与冻结值同值）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE)
        assert assessments[29].baseline_mean == statistics.mean(_BASELINE)
        assert assessments[29].baseline_std == _sigma0()

    def test_detection_phase_starts_at_sample31(self) -> None:
        """第 31 样本起 baseline_ready=True（检测期开始）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [_DOWN])
        assert assessments[29].baseline_ready is False
        assert assessments[30].baseline_ready is True

    def test_baseline_frozen_after_warmup(self) -> None:
        """基线冻结（检测期样本不改变 μ₀/σ₀——滑动基线 V1）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [0.4, 0.5, 0.6])
        for assessment in assessments[30:]:
            assert assessment.baseline_mean == statistics.mean(_BASELINE)
            assert assessment.baseline_std == _sigma0()

    def test_warmup_no_cumulation(self) -> None:
        """预热期不累积（Sₕ/Sₗ 恒 0——第 31 样本从零起算）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [_DOWN])
        for assessment in assessments[:30]:
            assert assessment.cusum_high == 0.0
            assert assessment.cusum_low == 0.0
        # s31 从零累积第一步
        assert assessments[30].cusum_low == _down_increment()


class TestTwoSidedCumulativeSum:
    """循环 A：双侧累积和手算锚（下漂注入逐样本 Sₗ 演算 + Sₕ 对称锚）。"""

    def test_down_drift_cumsum_low_anchor(self) -> None:
        """s31-s35 逐样本 Sₗ == (0.8 - 0.5*sigma0 - 0.4) * n（钦定同式表达式）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [_DOWN] * 5)
        increment = _down_increment()
        for n in range(1, 6):
            assessment = assessments[29 + n]
            assert assessment.cusum_low == increment * n, (
                f"s{30 + n} Sₗ 应等于同式闭式（实际 {assessment.cusum_low}，期望 {increment * n}）"
            )

    def test_down_drift_cumsum_high_stays_zero(self) -> None:
        """下漂注入下 Sₕ 恒 0（对称锚——增量恒负触底）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [_DOWN] * 5)
        for assessment in assessments[30:]:
            assert assessment.cusum_high == 0.0

    def test_detection_threshold_strict_inequality(self) -> None:
        """detection 判定 S>h 严格大于（0.95×5 处余量 2.5% 不触发）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [0.95] * 5)
        assert _up_increment() * 5 < H_MULTIPLIER * _sigma0(), "n=5 时 Sₕ 仍在 h 下（余量前提）"
        for assessment in assessments[30:35]:
            assert assessment.is_drifted is False, "前 5 样本余量内不应触发"

    def test_no_drift_alternating_control(self) -> None:
        """无漂移对照（交替续灌 10 样本恒不触发 + S 有界）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [0.7, 0.9] * 5)[30:]
        # 上界用与实现完全同序的同式表达式（μ₀ - k - x 的 0.7 形态——Sₗ 单步增量；
        # 0.9-0.8-k 形态与实现计算序不等价，浮点下差 1.5e-16 必假红）
        single_increment = 0.8 - 0.5 * _sigma0() - 0.7
        for index, assessment in enumerate(assessments):
            assert assessment.is_drifted is False, f"对照样本 {index + 1} 不应触发"
            assert max(assessment.cusum_high, assessment.cusum_low) <= single_increment


class TestNOfMConfirmation:
    """循环 B：N中M 确认（窗未满 + 当前样本条件 + 边界三形态参数化）。"""

    def test_window_not_full_no_confirmation(self) -> None:
        """s32-s34 detection True 但窗未满 5 不确认。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [_DOWN] * 4)
        sigma0 = _sigma0()
        for offset in (2, 3, 4):
            assessment = assessments[29 + offset]
            assert assessment.is_drifted is False, f"s{30 + offset} 窗未满不应确认"
            assert assessment.cusum_low > H_MULTIPLIER * sigma0, "detection=True 推导断言（Sₗ 已越线）"

    def test_s35_confirms_with_current_sample_true(self) -> None:
        """s35 确认（窗 (F,T,T,T,T) 计数 4≥3 且当前样本 T）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [_DOWN] * 5)
        confirmed = assessments[34]
        assert confirmed.is_drifted is True
        assert confirmed.drift_direction == "down"
        assert confirmed.drift_level == "severe"

    @pytest.mark.parametrize(
        ("tail", "expected_confirmed"),
        [
            ([0.35, 0.52, 0.75, 1.0, 0.4], True),  # (F,T,T,F,T) 计数 3 且当前 T → 确认
            ([0.35, 0.52, 0.75, 0.75, 1.0], False),  # (F,T,T,T,F) 计数 3 但当前 F → 不确认
            ([0.35, 0.52, 0.75, 1.0, 1.0], False),  # (F,T,T,F,F) 计数 2 → 不确认
        ],
        ids=["confirm-3-count-current-true", "no-confirm-current-false", "no-confirm-count-2"],
    )
    def test_boundary_patterns_end_to_end(self, tail: list[float], expected_confirmed: bool) -> None:
        """边界三形态（R2 钦定构造序列——各新检测器实例防窗历史互染）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + tail)
        for assessment in assessments[30:34]:
            assert assessment.is_drifted is False, "前 4 样本窗未满不确认"
        assert assessments[34].is_drifted is expected_confirmed

    def test_severity_severe_ratio_anchor(self) -> None:
        """s35 severe 档同式断言（Sₗ > 8σ₀——乘法同式与 detection 同系）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [_DOWN] * 5)
        sigma0 = _sigma0()
        assert _down_increment() * 5 > 8 * sigma0, "ratio 同式断言（>8 severe 域）"
        assert assessments[34].cusum_low > 8 * sigma0

    def test_moderate_level_anchor(self) -> None:
        """moderate 档锚（0.62×10——R1 实测：s36 确认、ratio≈7.6→moderate）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [0.62] * 10)[30:]
        sigma0 = _sigma0()
        for index in range(5):
            assert assessments[index].is_drifted is False, f"前 5 样本不确认（n={index + 1}）"
        confirmed = assessments[5]
        assert confirmed.is_drifted is True, "s36 应确认（窗 (F,F,F,T,T,T) 计数 3 且当前 T）"
        assert confirmed.drift_level == "moderate"
        assert confirmed.drift_direction == "down"
        assert 5 * sigma0 < confirmed.cusum_low <= 8 * sigma0, "moderate 域（5σ<S≤8σ）区间断言"


class TestConfirmationReset:
    """循环 B：确认后复位（S 归零 + 窗清空 + 基线保持 + 再确认间隔锚）。"""

    def test_reset_cumsum_from_zero(self) -> None:
        """复位后新序列从零累积（s36 cusum_low == 单增量）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [_DOWN] * 5 + [_DOWN] * 5)
        assert assessments[34].is_drifted is True
        followup = assessments[35]
        assert followup.cusum_low == _down_increment(), (
            f"复位后第 1 样本应从零累积（实际 {followup.cusum_low}，期望 {_down_increment()}）"
        )

    def test_reset_confirmation_window_cleared(self) -> None:
        """确认窗清空（复位后前 4 样本计数不足不确认——(F,T,T,T) 窗未满）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [_DOWN] * 5 + [_DOWN] * 5)
        for offset in range(4):
            assert assessments[35 + offset].is_drifted is False, f"复位后第 {offset + 1} 样本不应确认"

    def test_reconfirmation_interval_anchor(self) -> None:
        """再确认间隔锚（复位后第 5 样本再确认——OD-5① 实测 down δ=0.4 间隔 5）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [_DOWN] * 5 + [_DOWN] * 5)
        reconfirmed = assessments[39]
        assert reconfirmed.is_drifted is True, "复位后第 5 样本应再确认（重复告警节奏锚）"
        assert reconfirmed.drift_direction == "down"

    def test_baseline_preserved_after_reset(self) -> None:
        """基线保持（复位后 baseline_mean/std 与首确认时相等——复位不重估基线）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [_DOWN] * 5 + [_DOWN] * 5)
        first_confirmed = assessments[34]
        for followup in assessments[35:40]:
            assert followup.baseline_mean == first_confirmed.baseline_mean
            assert followup.baseline_std == first_confirmed.baseline_std


class TestUpwardDrift:
    """循环 B：正向漂移（0.95×8——up 确认 moderate + 1ulp 区间断言纪律）。"""

    def test_upward_cumsum_closed_form_n_le_5(self) -> None:
        """n=1..5 闭式位等（(0.95-0.8-0.5*sigma0)*n——已数值实证安全）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [0.95] * 8)[30:]
        increment = _up_increment()
        for n in range(1, 6):
            assert assessments[n - 1].cusum_high == increment * n, f"上漂 n={n} Sₕ 同式闭式"

    def test_upward_margin_no_trigger_first_5(self) -> None:
        """前 5 样本余量 2.5% 不触发（Sₕ(5) < h 同式断言）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [0.95] * 8)[30:]
        assert _up_increment() * 5 < H_MULTIPLIER * _sigma0()
        for n in range(1, 6):
            assert assessments[n - 1].is_drifted is False

    def test_upward_confirmation_at_s38_moderate(self) -> None:
        """s38 确认 up + moderate（n=6/7 计数不足；s38 区间断言禁闭式精确等式）。"""
        assessments = _feed(CUSUMDriftDetector(), _BASELINE + [0.95] * 8)[30:]
        sigma0 = _sigma0()
        increment = _up_increment()
        # n=6 首次 detection、n=7 窗计数 2 不足
        assert assessments[5].cusum_high > 5 * sigma0, "n=6 首次越线"
        assert assessments[5].is_drifted is False and assessments[6].is_drifted is False
        # s38 确认（窗 (F,F,T,T,T) 计数 3 且当前 T）——n≥6 一律区间比较（1ulp 形态）
        confirmed = assessments[7]
        assert confirmed.is_drifted is True
        assert confirmed.drift_direction == "up"
        assert confirmed.drift_level == "moderate"
        assert increment * 7 < confirmed.cusum_high <= 8 * sigma0, "s38 Sₕ 区间断言（moderate 域）"


class TestDegenerateBaselineDefense:
    """循环 B：degenerate 基线防御（σ₀<ε 恒不判定 + 计数继续——可观测降级非异常）。"""

    def test_degenerate_never_confirms(self) -> None:
        """全同值基线（[0.8]×30 → σ₀=0）后漂移注入恒不判定。"""
        assessments = _feed(CUSUMDriftDetector(), [0.8] * 30 + [_DOWN] * 10)
        assert assessments[29].baseline_std == 0.0, "全同值基线 σ₀ 应为 0"
        for index, assessment in enumerate(assessments):
            assert assessment.is_drifted is False, f"degenerate 样本 {index + 1} 不应判定"

    def test_degenerate_sample_count_continues(self) -> None:
        """degenerate 下 sample_count 继续递增（31..40）。"""
        assessments = _feed(CUSUMDriftDetector(), [0.8] * 30 + [_DOWN] * 10)
        for index, assessment in enumerate(assessments, start=1):
            assert assessment.sample_count == index

    def test_degenerate_zero_division_defense(self) -> None:
        """防线必要性强于恒触发（确认路径 ratio=S/σ₀ 会 ZeroDivisionError——防线封死该路径）。"""
        assessments = _feed(CUSUMDriftDetector(), [0.8] * 30 + [0.4, 0.4, 0.4, 0.4, 0.4])
        # 连续 5 个偏移样本仍不确认（若防线缺失：detection 恒 True → s35 确认 → ratio 除零崩溃）
        assert all(a.is_drifted is False for a in assessments)


class TestScoreDomainGuard:
    """循环 B：入参域守卫（score 非 [0,1] → ValidationError 201 三段式）。"""

    @pytest.mark.parametrize(
        "bad_score",
        [-0.01, 1.01, -1.0, 2.0, True, "0.8", None],
        ids=["neg", "over", "neg-one", "two", "bool", "str", "none"],
    )
    def test_invalid_score_raises_201(self, bad_score: Any) -> None:
        """越界/bool/非数值参数化 → 201 + context 携 score。"""
        detector = CUSUMDriftDetector()

        async def _call() -> None:
            await detector.update(bad_score)

        import asyncio

        loop = asyncio.new_event_loop()
        try:
            with pytest.raises(ValidationError) as exc_info:
                loop.run_until_complete(_call())
        finally:
            loop.close()
        assert exc_info.value.code == "EXCEPTION_201"
        assert "score" in exc_info.value.context

    def test_valid_boundary_scores_accepted(self) -> None:
        """[0,1] 闭区间边界值合法（0.0/1.0）。"""
        assessments = _feed(CUSUMDriftDetector(), [0.0, 1.0] * 15)
        assert len(assessments) == 30
        assert assessments[29].baseline_ready is False

    def test_invalid_score_does_not_consume_sample(self) -> None:
        """域守卫失败不消耗样本（计数不变——下一合法样本序号衔接）。"""
        detector = CUSUMDriftDetector()
        _feed(detector, [0.8, 0.8])

        async def _bad() -> None:
            await detector.update(1.5)

        import asyncio

        loop = asyncio.new_event_loop()
        try:
            with pytest.raises(ValidationError):
                loop.run_until_complete(_bad())
        finally:
            loop.close()
        assessments = _feed(detector, [0.8])
        assert assessments[0].sample_count == 3, "非法样本不应计入 sample_count"


# ===================================================================
# 循环 C（Task 3）：trigger_recalibration 事件发布 + 降级
# ===================================================================


class _RecordingPublisher:
    """记录发布事件的发布器（内存替身——验收同款形态）。"""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, event: Any) -> Any:
        from src.domain.events.publish_result import ChannelResult, PublishResult

        self.published_events.append(event)
        return PublishResult(
            event_id=str(event.event_id) if hasattr(event, "event_id") else "",
            results=(ChannelResult(channel_name="inmemory", success=True),),
        )


class _RaisingPublisher:
    """恒抛异常的发布器（发布失败降级注入面）。"""

    async def publish(self, event: Any) -> Any:
        raise RuntimeError("模拟事件发布通道故障")


def _confirmed_assessment() -> Any:
    """手算锚序列产出确认 assessment（s35——事件字段数据源）。"""
    assessments = _feed(CUSUMDriftDetector(), _BASELINE + [_DOWN] * 5)
    confirmed = assessments[34]
    assert confirmed.is_drifted is True
    return confirmed


def _unconfirmed_assessment() -> Any:
    """合法未确认 assessment（未确认守卫断言材料）。"""
    from src.application.ports.agent_drift import DriftAssessment

    return DriftAssessment(
        is_drifted=False,
        baseline_ready=True,
        drift_direction="none",
        drift_level="none",
        cusum_high=0.0,
        cusum_low=0.1,
        baseline_mean=statistics.mean(_BASELINE),
        baseline_std=_sigma0(),
        observed_value=0.8,
        sample_count=40,
    )


def _run_trigger(detector: CUSUMDriftDetector, assessment: Any, agent_id: str | None = "agent-x") -> Any:
    """同步驱动 trigger_recalibration（BDD/单测统一调度形态）。"""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(detector.trigger_recalibration(assessment, agent_id=agent_id))
    finally:
        loop.close()


class TestTriggerRecalibrationPublish:
    """循环 C：trigger_recalibration（事件发布 + 字段真值 + agent_id 透传）。"""

    def test_publishes_drift_detected_event_once(self) -> None:
        """确认 assessment → publish 单次调用 + isinstance DriftDetected。"""
        from src.domain.events.drift_events import DriftDetected

        publisher = _RecordingPublisher()
        detector = CUSUMDriftDetector(event_publisher=publisher)
        assessment = _confirmed_assessment()
        result = _run_trigger(detector, assessment)
        assert result is None
        assert len(publisher.published_events) == 1, "应恰发布一次"
        assert isinstance(publisher.published_events[0], DriftDetected)

    def test_event_fields_match_assessment(self) -> None:
        """事件字段与 assessment 逐字段相等（统一数据源——OD-7）。"""
        publisher = _RecordingPublisher()
        detector = CUSUMDriftDetector(event_publisher=publisher)
        assessment = _confirmed_assessment()
        _run_trigger(detector, assessment)
        event = publisher.published_events[0]
        assert event.metric_name == "overall_score"
        assert event.drift_direction == assessment.drift_direction
        assert event.drift_level == assessment.drift_level
        assert event.cusum_high == assessment.cusum_high
        assert event.cusum_low == assessment.cusum_low
        assert event.baseline_mean == assessment.baseline_mean
        assert event.baseline_std == assessment.baseline_std
        assert event.observed_value == assessment.observed_value
        assert event.sample_count == assessment.sample_count

    def test_event_defaults_and_agent_id_passthrough(self) -> None:
        """recommended_action 默认 + agent_id 双形态透传（显式/None）。"""
        publisher = _RecordingPublisher()
        detector = CUSUMDriftDetector(event_publisher=publisher)
        assessment = _confirmed_assessment()
        _run_trigger(detector, assessment, agent_id="agent-x")
        _run_trigger(detector, assessment, agent_id=None)
        assert publisher.published_events[0].agent_id == "agent-x"
        assert publisher.published_events[1].agent_id is None
        assert publisher.published_events[0].recommended_action == "manual_review"

    def test_unconfirmed_assessment_zero_publish(self) -> None:
        """未确认 assessment → 零发布 + returns None（trigger 内守卫双保险）。"""
        publisher = _RecordingPublisher()
        detector = CUSUMDriftDetector(event_publisher=publisher)
        result = _run_trigger(detector, _unconfirmed_assessment())
        assert result is None
        assert publisher.published_events == [], "未确认 assessment 不应发布"

    def test_no_publisher_no_error(self) -> None:
        """publisher 未注入（None 构造）→ 纯检测消费面零异常。"""
        detector = CUSUMDriftDetector()
        result = _run_trigger(detector, _confirmed_assessment())
        assert result is None


class TestTriggerRecalibrationDegradation:
    """循环 C：发布失败降级（可观测附加面——不上抛 + logger.error）。"""

    def test_publish_failure_degrades_gracefully(self, caplog: pytest.LogCaptureFixture) -> None:
        """替身抛 RuntimeError → 不上抛 returns None + caplog error 断言。"""
        import logging

        detector = CUSUMDriftDetector(event_publisher=_RaisingPublisher())
        result = _run_trigger(detector, _confirmed_assessment())
        assert result is None, "发布失败应降级不上抛"
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR and "DriftDetected" in r.message]
        assert error_records, "应有 ERROR 级降级日志（含 DriftDetected 事件标识）"

    def test_unsuccessful_result_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """publish 返回 is_success=False → logger.error（非异常降级面）。"""
        import logging

        class _FailingResultPublisher:
            """发布返回失败 ChannelResult 的替身（Outbox 写入失败形态）。"""

            async def publish(self, event: Any) -> Any:
                from src.domain.events.publish_result import ChannelResult, PublishResult

                return PublishResult(
                    event_id=str(event.event_id),
                    results=(ChannelResult(channel_name="reliable", success=False, error="outbox unavailable"),),
                )

        detector = CUSUMDriftDetector(event_publisher=_FailingResultPublisher())
        result = _run_trigger(detector, _confirmed_assessment())
        assert result is None
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR and "DriftDetected" in r.message]
        assert error_records, "is_success=False 应有 ERROR 日志"
