"""领域层辩论质量评估器模块

Story 4.5 — 红蓝辩论机制基础：辩论质量三算法（GAP-CRITICAL-09 清偿——
architecture.md GAP 表"辩论质量评估器未实现"就此落地）。

算法族：字符 bigram 集合 Jaccard 相似度（中文无需分词，标准库实现，纯函数）

公式与阈值对应（architecture.md §7.3 终止条件）：
- compute_repetition_rate(current, previous) = |C ∩ P| / |C ∪ P|
  （C/P 为相邻轮次文本的字符 bigram 集合；V1 多轮终止条件：> 0.50 强制终止）
- compute_gain_rate(current, previous) = |C − P| / max(|P|, 1)
  （新信息量/上轮信息量；V1 多轮终止条件：< 0.10 强制终止；
  previous 为空返回 1.0 表示全新信息）
- evaluate_overlap(red, blue) = |R ∩ B| / |R ∪ B|
  （R/B 为红蓝论点拼接文本的字符 bigram 集合；MVP 门控：
  ≥ 0.95 抛 DebateLowDivergenceError，≥ 0.80 输出 RiskView.warnings 警告——
  门控判断在应用层服务，本评估器仅返回重叠率）

边界规则（与架构 8.0.0 版修正项对齐）：
- repetition_rate：两者皆空返回 0.0，一空一非空返回 0.0（空参数列表 bug 修正）
- gain_rate：previous 为空返回 1.0（全新信息）；current 为空返回 0.0
- evaluate_overlap：bigram 并集为空返回 0.0（防 0/0 未定义，与空集规则对齐）

纯函数单一职责：本评估器不构造 DebateQuality 对象（组装归应用层服务）。
evaluate_round 不实现——V1 多轮接口随 Story 10.6 演进（MVP 无轮次序列）。
"""

from __future__ import annotations

from src.domain.value_objects.debate import PerspectiveAnalysis


def _extract_bigrams(text: str) -> frozenset[str]:
    """提取字符串的字符 bigram 集合

    Args:
        text: 输入文本

    Returns:
        相邻字符对集合（frozenset，去重）；空串与单字符返回空集合
    """
    return frozenset(text[i : i + 2] for i in range(len(text) - 1))


def _jaccard_similarity(current: frozenset[str], previous: frozenset[str]) -> float:
    """两集合的 Jaccard 相似度（空并集返回 0.0，防 0/0）

    Args:
        current: 当前集合
        previous: 对照集合

    Returns:
        |C ∩ P| / |C ∪ P|；并集为空时返回 0.0
    """
    union = current | previous
    if not union:
        return 0.0
    intersection = current & previous
    return len(intersection) / len(union)


class DebateEvaluator:
    """辩论质量评估器（领域服务，纯算法零状态）

    SINGLETON 注册前提：纯函数无状态，同输入同输出。
    """

    def compute_repetition_rate(self, current_text: str, previous_text: str) -> float:
        """相邻轮次重复内容占比（字符 bigram Jaccard）

        V1 多轮辩论终止条件算法基础（> 0.50 强制终止）；
        MVP 单轮不调用，为 Story 10.6 预留。

        Args:
            current_text: 当前轮次文本
            previous_text: 上轮文本

        Returns:
            重复率 ∈ [0.0, 1.0]；完全相同返回 1.0；无交集返回 0.0；
            两者皆空返回 0.0；一空一非空返回 0.0（空参数列表 bug 修正）

        Example:
            >>> DebateEvaluator().compute_repetition_rate("ABC", "ABC")
            1.0
        """
        return _jaccard_similarity(_extract_bigrams(current_text), _extract_bigrams(previous_text))

    def compute_gain_rate(self, current_text: str, previous_text: str) -> float:
        """新信息量/上轮信息量（相对增益率）

        V1 多轮辩论终止条件算法基础（< 0.10 强制终止）；
        MVP 单轮不调用，为 Story 10.6 预留。

        Args:
            current_text: 当前轮次文本
            previous_text: 上轮文本

        Returns:
            增益率 = |current_bigrams − previous_bigrams| / max(|previous_bigrams|, 1)；
            previous 为空返回 1.0（全新信息）；current 为空返回 0.0

        Example:
            >>> DebateEvaluator().compute_gain_rate("ABCD", "ABC")
            0.5
        """
        current_bigrams = _extract_bigrams(current_text)
        previous_bigrams = _extract_bigrams(previous_text)
        if not previous_bigrams:
            return 1.0
        new_bigrams = current_bigrams - previous_bigrams
        return len(new_bigrams) / max(len(previous_bigrams), 1)

    def evaluate_overlap(
        self,
        red_analysis: PerspectiveAnalysis,
        blue_analysis: PerspectiveAnalysis,
    ) -> float:
        """红蓝重叠率（MVP 分化度门控的核心度量）

        红蓝论点分别按序拼接后提取字符 bigram，计算 Jaccard 相似度；
        高重叠 = 低分化（≥ 0.95 两视角实质相同，辩论失去意义）。

        Args:
            red_analysis: 红方（激进派）视角分析
            blue_analysis: 蓝方（保守派）视角分析

        Returns:
            重叠率 ∈ [0.0, 1.0]；论点完全相同返回 1.0；无交集返回 0.0；
            bigram 并集为空（如双方各仅单字论点）返回 0.0

        Example:
            >>> evaluator = DebateEvaluator()
            >>> # 红蓝论点完全相同 → 1.0
        """
        red_text = "".join(red_analysis.arguments)
        blue_text = "".join(blue_analysis.arguments)
        return _jaccard_similarity(_extract_bigrams(red_text), _extract_bigrams(blue_text))


__all__ = ["DebateEvaluator"]
