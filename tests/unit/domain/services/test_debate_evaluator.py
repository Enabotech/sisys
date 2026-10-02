"""Story 4.5 — DebateEvaluator 领域服务单元测试

验证字符 bigram 集合 Jaccard 相似度族三算法（GAP-CRITICAL-09 清偿）：
- compute_repetition_rate：相邻轮次重复内容占比（V1 终止条件 >0.50）
- compute_gain_rate：新信息量/上轮信息量（V1 终止条件 <0.10）
- evaluate_overlap：红蓝重叠率（MVP 门控 ≥0.95 抛 422 / ≥0.80 警告）

算法性质：纯函数无状态（SINGLETON 注册前提）、中文免分词、标准库实现。

边界规则（与架构 8.0.0 版修正项对齐）：
- repetition_rate：两者皆空返回 0.0（空参数列表 bug 修正），一空一非空返回 0.0
- gain_rate：previous 为空返回 1.0（全新信息）；current 为空返回 0.0
- evaluate_overlap：bigram 并集为空（双方各仅单字论点）返回 0.0（防 0/0 未定义）
"""

from __future__ import annotations

import pytest

from src.domain.services.debate_evaluator import DebateEvaluator
from src.domain.value_objects.debate import DebatePerspective, PerspectiveAnalysis


def _make_perspective(
    arguments: tuple[str, ...],
    perspective: DebatePerspective = DebatePerspective.RED_AGGRESSIVE,
) -> PerspectiveAnalysis:
    """按论点元组构造视角分析（评估器入参）"""
    return PerspectiveAnalysis(perspective=perspective, stance="立场", arguments=arguments, confidence=0.5)


# ===================================================================
# compute_repetition_rate
# ===================================================================


class TestComputeRepetitionRate:
    def test_identical_texts_returns_one(self) -> None:
        """完全相同文本 → 1.0"""
        assert DebateEvaluator().compute_repetition_rate("ABC", "ABC") == 1.0

    def test_partial_overlap_known_value(self) -> None:
        """部分重叠精确值：bigram {AB,BC}∩{AB,BD}={AB}，并集 3 → 1/3"""
        assert DebateEvaluator().compute_repetition_rate("ABC", "ABD") == pytest.approx(1 / 3)

    def test_disjoint_texts_returns_zero(self) -> None:
        """无交集 → 0.0"""
        assert DebateEvaluator().compute_repetition_rate("XYZ", "ABC") == 0.0

    def test_both_empty_returns_zero(self) -> None:
        """两者皆空 → 0.0（空参数列表重复率 bug 是架构 8.0.0 修正项，必须覆盖）"""
        assert DebateEvaluator().compute_repetition_rate("", "") == 0.0

    def test_current_empty_returns_zero(self) -> None:
        """当前空、上轮非空 → 0.0"""
        assert DebateEvaluator().compute_repetition_rate("", "ABC") == 0.0

    def test_previous_empty_returns_zero(self) -> None:
        """上轮空、当前非空 → 0.0"""
        assert DebateEvaluator().compute_repetition_rate("ABC", "") == 0.0

    def test_single_char_texts_no_bigram_returns_zero(self) -> None:
        """单字符无 bigram → 空并集 → 0.0"""
        assert DebateEvaluator().compute_repetition_rate("A", "A") == 0.0

    def test_chinese_texts_known_value(self) -> None:
        """中文用例：{市场,场进,进入}∩{市场,场退,退出}={市场}，并集 5 → 1/5"""
        assert DebateEvaluator().compute_repetition_rate("市场进入", "市场退出") == pytest.approx(1 / 5)

    def test_deterministic_pure_function(self) -> None:
        """纯函数确定性：同输入同输出"""
        evaluator = DebateEvaluator()
        first = evaluator.compute_repetition_rate("战略窗口期", "战略观察期")
        second = evaluator.compute_repetition_rate("战略窗口期", "战略观察期")
        assert first == second


# ===================================================================
# compute_gain_rate
# ===================================================================


class TestComputeGainRate:
    def test_known_value_abcd_over_abc(self) -> None:
        """精确值：bigram(ABCD)={AB,BC,CD} 与 bigram(ABC)={AB,BC} 差集 {CD}=1，1/max(2,1)=0.5"""
        assert DebateEvaluator().compute_gain_rate("ABCD", "ABC") == 0.5

    def test_identical_texts_returns_zero(self) -> None:
        """完全相同 → 无新信息 → 0.0"""
        assert DebateEvaluator().compute_gain_rate("ABC", "ABC") == 0.0

    def test_previous_empty_returns_one(self) -> None:
        """previous 为空 → 1.0（全新信息）"""
        assert DebateEvaluator().compute_gain_rate("ABC", "") == 1.0

    def test_current_empty_returns_zero(self) -> None:
        """current 为空、previous 非空 → 差集空 → 0.0"""
        assert DebateEvaluator().compute_gain_rate("", "ABC") == 0.0

    def test_both_empty_returns_one(self) -> None:
        """两者皆空 → previous 为空规则适用 → 1.0（故事规范：previous 为空时返回 1.0）"""
        assert DebateEvaluator().compute_gain_rate("", "") == 1.0

    def test_chinese_known_value(self) -> None:
        """中文精确值：bigram(市场进入期) 4 个，previous 3 个，差集 {入期}=1 → 1/3"""
        assert DebateEvaluator().compute_gain_rate("市场进入期", "市场进入") == pytest.approx(1 / 3)

    def test_chinese_full_suffix_info_returns_one(self) -> None:
        """中文全新后缀：差集 {入窗,窗口,口期}=3，max(3,1)=3 → 1.0"""
        assert DebateEvaluator().compute_gain_rate("市场进入窗口期", "市场进入") == 1.0

    def test_deterministic_pure_function(self) -> None:
        """纯函数确定性"""
        evaluator = DebateEvaluator()
        first = evaluator.compute_gain_rate("新增战略论点", "既有战略论点")
        second = evaluator.compute_gain_rate("新增战略论点", "既有战略论点")
        assert first == second


# ===================================================================
# evaluate_overlap
# ===================================================================


class TestEvaluateOverlap:
    def test_identical_arguments_returns_one(self) -> None:
        """红蓝论点完全相同 → Jaccard = 1.0（422 门控稳定触发构造）"""
        arguments = ("市场窗口期稍纵即逝",)
        red = _make_perspective(arguments)
        blue = _make_perspective(arguments, DebatePerspective.BLUE_CONSERVATIVE)
        assert DebateEvaluator().evaluate_overlap(red, blue) == 1.0

    def test_unrelated_arguments_returns_zero(self) -> None:
        """完全无关论点 → 0.0"""
        red = _make_perspective(("供应链本地化成本高企",))
        blue = _make_perspective(("关税政策存在不确定性",), DebatePerspective.BLUE_CONSERVATIVE)
        assert DebateEvaluator().evaluate_overlap(red, blue) == 0.0

    def test_partial_overlap_known_value(self) -> None:
        """部分重叠精确值：红=("ABCD",) 蓝=("ABDE",) → 交集 {AB}∪跨拼接项 / 精确计算"""
        red = _make_perspective(("ABCD",))
        blue = _make_perspective(("ABDE",), DebatePerspective.BLUE_CONSERVATIVE)
        # bigram(red)={AB,BC,CD}，bigram(blue)={AB,BD,DE}，交集 {AB}=1，并集 5 → 0.2
        assert DebateEvaluator().evaluate_overlap(red, blue) == pytest.approx(1 / 5)

    def test_chinese_arguments_partial_overlap(self) -> None:
        """中文论点对可用：红蓝共享"东南亚市场"前缀"""
        red = _make_perspective(("东南亚市场窗口期正打开",))
        blue = _make_perspective(("东南亚市场政策不确定性高",), DebatePerspective.BLUE_CONSERVATIVE)
        overlap = DebateEvaluator().evaluate_overlap(red, blue)
        assert 0.0 < overlap < 1.0

    def test_warning_zone_construction(self) -> None:
        """警告区构造精确验证：37 字唯一字符论点改第 20 字 → J=34/38≈0.895 ∈ [0.80, 0.95)"""
        red_arg = "东南亚市场窗口期正打开需果断布局渠道供应链并建立本地化运营团队抢占先发优势"
        assert len(red_arg) == 37
        blue_arg = red_arg[:19] + "变" + red_arg[20:]  # 改第 20 字"应"→"变"
        red = _make_perspective((red_arg,))
        blue = _make_perspective((blue_arg,), DebatePerspective.BLUE_CONSERVATIVE)
        overlap = DebateEvaluator().evaluate_overlap(red, blue)
        assert overlap == pytest.approx(34 / 38)
        assert 0.80 <= overlap < 0.95

    def test_both_single_char_arguments_returns_zero(self) -> None:
        """空 bigram 并集：红蓝各仅单字论点 → 双方 bigram 皆空 → 0.0（防 0/0）"""
        red = _make_perspective(("甲",))
        blue = _make_perspective(("乙",), DebatePerspective.BLUE_CONSERVATIVE)
        assert DebateEvaluator().evaluate_overlap(red, blue) == 0.0

    def test_single_char_vs_two_char_arguments_returns_zero(self) -> None:
        """一方 bigram 空（单字论点）→ 交集空 → 0.0"""
        red = _make_perspective(("甲",))
        blue = _make_perspective(("甲乙",), DebatePerspective.BLUE_CONSERVATIVE)
        assert DebateEvaluator().evaluate_overlap(red, blue) == 0.0

    def test_multi_arguments_joined_semantics(self) -> None:
        """多论点拼接语义：论点顺序不改变重叠率（拼接后整体 bigram）"""
        red = _make_perspective(("论点甲内容", "论点乙内容"))
        blue = _make_perspective(("论点甲内容", "论点乙内容"), DebatePerspective.BLUE_CONSERVATIVE)
        assert DebateEvaluator().evaluate_overlap(red, blue) == 1.0

    def test_returns_plain_float_not_quality_object(self) -> None:
        """纯函数单一职责：返回 float，不构造 DebateQuality（组装归服务层）"""
        red = _make_perspective(("论点内容一",))
        blue = _make_perspective(("论点内容一",), DebatePerspective.BLUE_CONSERVATIVE)
        result = DebateEvaluator().evaluate_overlap(red, blue)
        assert isinstance(result, float)

    def test_deterministic_pure_function(self) -> None:
        """纯函数确定性（SINGLETON 注册前提）"""
        evaluator = DebateEvaluator()
        red = _make_perspective(("确定性验证论点",))
        blue = _make_perspective(("确定性验证论点",), DebatePerspective.BLUE_CONSERVATIVE)
        assert evaluator.evaluate_overlap(red, blue) == DebateEvaluator().evaluate_overlap(red, blue)


# ===================================================================
# 纯函数与实例化语义
# ===================================================================


class TestEvaluatorSemantics:
    def test_stateless_instances_interchangeable(self) -> None:
        """无状态：不同实例可互换（SINGLETON 语义验证）"""
        first = DebateEvaluator()
        second = DebateEvaluator()
        assert first.compute_repetition_rate("AB", "AB") == second.compute_repetition_rate("AB", "AB")

    def test_no_evaluate_round_method(self) -> None:
        """evaluate_round 不实现（V1 随 Story 10.6 演进，MVP 禁止过度设计）"""
        assert not hasattr(DebateEvaluator(), "evaluate_round")
