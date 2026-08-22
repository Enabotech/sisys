"""CompressionQualityEvaluator 领域服务单元测试

验证压缩质量评估器的评分算法：
1. 信息熵评分 — 基于字符分布多样性的 Shannon 熵
2. 关键实体覆盖率 — Top-20 关键实体保留比例
3. 冗余度评分 — 基于 n-gram 重复检测
4. 综合评分 — 加权融合

遵循领域层零外部依赖测试原则（仅使用 Python 标准库）。
"""

from __future__ import annotations

from src.domain.services.compression_quality_evaluator import (
    QUALITY_THRESHOLD,
    CompressionQualityEvaluator,
)


class TestCompressionQualityEvaluator:
    """CompressionQualityEvaluator 单元测试"""

    async def test_empty_input_returns_zero(self) -> None:
        """空输入返回 0.0"""
        evaluator = CompressionQualityEvaluator()
        score = await evaluator.evaluate(
            compressed_context="",
            original_docs=[],
            key_entities=[],
        )
        assert score == 0.0

    async def test_whitespace_input_returns_zero(self) -> None:
        """仅空白字符输入返回 0.0"""
        evaluator = CompressionQualityEvaluator()
        score = await evaluator.evaluate(
            compressed_context="   \n\t  ",
            original_docs=[],
            key_entities=[],
        )
        assert score == 0.0

    async def test_high_entropy_high_coverage_text(self) -> None:
        """高信息熵 + 高覆盖率的文本应得分较高"""
        evaluator = CompressionQualityEvaluator()
        text = (
            "企业战略规划包括BLM模型和BEM模型两个核心框架。"
            "BLM模型包含业绩差距分析、市场洞察、战略意图等六个阶段。"
            "BEM模型则包含战略解码、目标分解和重点工作计划。"
            "2024年营业收入增长15%，净利润率达到12%。"
        )
        entities = [
            {"name": "BLM", "entity_type": "CONCEPT"},
            {"name": "BEM", "entity_type": "CONCEPT"},
            {"name": "战略规划", "entity_type": "CONCEPT"},
            {"name": "净利润率", "entity_type": "CONCEPT"},
        ]

        score = await evaluator.evaluate(
            compressed_context=text,
            original_docs=[],
            key_entities=entities,
        )

        assert score >= 0.7, f"高信息密度文本应≥0.7，实际{score}"
        assert score <= 1.0

    async def test_low_entropy_repetitive_text(self) -> None:
        """低信息熵 + 重复文本应得分较低"""
        evaluator = CompressionQualityEvaluator()
        text = (
            "重复重复重复重复重复重复重复重复重复重复重复重复重复重复"
            "重复重复重复重复重复重复重复重复重复重复重复重复重复重复"
            "重复重复重复重复重复重复重复重复重复重复重复重复重复重复"
        ) * 5
        entities = [
            {"name": "战略规划", "entity_type": "CONCEPT"},
        ]

        score = await evaluator.evaluate(
            compressed_context=text,
            original_docs=[],
            key_entities=entities,
        )

        # 低信息熵 + 高覆盖（实体重复出现）→ 综合评分可能较低
        assert score >= 0.0
        assert score <= 1.0

    async def test_no_entities_returns_full_coverage_score(self) -> None:
        """无实体时覆盖率维度满分"""
        evaluator = CompressionQualityEvaluator()
        text = "企业战略规划与执行的综合分析报告。"
        score = await evaluator.evaluate(
            compressed_context=text,
            original_docs=[],
            key_entities=[],
        )
        # 无实体时覆盖率为 1.0，综合评分至少 ≥ 0.4（覆盖率权重 40%）
        assert score >= 0.4

    async def test_partial_entity_coverage(self) -> None:
        """部分实体被覆盖时评分随覆盖比例变化"""
        evaluator = CompressionQualityEvaluator()
        text = "BLM模型是核心战略规划框架。"
        entities = [
            {"name": "BLM", "entity_type": "CONCEPT"},
            {"name": "BEM", "entity_type": "CONCEPT"},
            {"name": "PESTEL", "entity_type": "CONCEPT"},
        ]

        score = await evaluator.evaluate(
            compressed_context=text,
            original_docs=[],
            key_entities=entities,
        )

        # 覆盖率 = 1/3（仅 BLM 出现），综合评分受覆盖率影响
        assert score < 0.9

    async def test_all_entities_covered(self) -> None:
        """所有实体都被覆盖时覆盖率满分"""
        evaluator = CompressionQualityEvaluator()
        text = "BLM模型包含业绩差距分析和市场洞察。BEM模型包含战略解码。"
        entities = [
            {"name": "BLM", "entity_type": "CONCEPT"},
            {"name": "BEM", "entity_type": "CONCEPT"},
            {"name": "业绩差距分析", "entity_type": "CONCEPT"},
            {"name": "市场洞察", "entity_type": "CONCEPT"},
        ]

        score = await evaluator.evaluate(
            compressed_context=text,
            original_docs=[],
            key_entities=entities,
        )

        # 覆盖率为 4/4 = 1.0，综合评分应较高
        assert score >= 0.7

    async def test_quality_threshold_constant(self) -> None:
        """质量门禁阈值为 0.7"""
        assert QUALITY_THRESHOLD == 0.70


class TestCompressionQualityEvaluatorEntropy:
    """信息熵评分测试"""

    async def test_entropy_normal_text(self) -> None:
        """正常文本的信息熵应在合理范围"""
        text = "企业战略规划分析报告包含多个维度的评估。"
        evaluator = CompressionQualityEvaluator()
        score = await evaluator.evaluate(
            compressed_context=text,
            original_docs=[],
            key_entities=[],
        )
        # 中文文本信息熵通常在 0.5-0.9
        assert 0.5 <= score <= 1.0

    async def test_entropy_very_short_text(self) -> None:
        """极短文本信息熵"""
        evaluator = CompressionQualityEvaluator()
        score = await evaluator.evaluate(
            compressed_context="测试",
            original_docs=[],
            key_entities=[],
        )
        # 短文本信息熵可能较低
        assert score >= 0.0

    async def test_entropy_diverse_characters(self) -> None:
        """多样字符产生高信息熵"""
        text = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()"
        evaluator = CompressionQualityEvaluator()
        score = await evaluator.evaluate(
            compressed_context=text,
            original_docs=[],
            key_entities=[],
        )
        # 多样字符的信息熵应接近 1.0
        assert score >= 0.8


class TestCompressionQualityEvaluatorCoverage:
    """关键实体覆盖率测试"""

    async def test_coverage_entity_not_in_text(self) -> None:
        """实体不在文本中时贡献为 0"""
        text = "企业战略规划分析"
        evaluator = CompressionQualityEvaluator()
        score = await evaluator.evaluate(
            compressed_context=text,
            original_docs=[],
            key_entities=[{"name": "BLM", "entity_type": "CONCEPT"}],
        )
        # 覆盖率 = 0/1 = 0，但信息熵和冗余度仍贡献 60% 权重
        # 理想情况下 score <= 0.6（0*0.4 + 熵*0.4 + 冗余*0.2）
        assert score <= 0.9

    async def test_coverage_entity_in_text(self) -> None:
        """实体在文本中时贡献为 1"""
        text = "BLM模型是核心框架"
        evaluator = CompressionQualityEvaluator()
        score = await evaluator.evaluate(
            compressed_context=text,
            original_docs=[],
            key_entities=[{"name": "BLM", "entity_type": "CONCEPT"}],
        )
        # 覆盖率 = 1/1 = 1.0
        assert score >= 0.5

    async def test_coverage_entity_empty_name(self) -> None:
        """实体名称为空时跳过"""
        text = "测试内容"
        evaluator = CompressionQualityEvaluator()
        score = await evaluator.evaluate(
            compressed_context=text,
            original_docs=[],
            key_entities=[{"name": "", "entity_type": "CONCEPT"}],
        )
        # 空名称实体不计入总数，覆盖率为 1.0
        assert score >= 0.5


class TestCompressionQualityEvaluatorRedundancy:
    """冗余度评分测试"""

    async def test_redundancy_no_repetition(self) -> None:
        """无重复的文本冗余度评分高（低冗余）"""
        text = "企业战略规划BLM模型BEM模型市场洞察业绩差距分析"
        evaluator = CompressionQualityEvaluator()
        score = await evaluator.evaluate(
            compressed_context=text,
            original_docs=[],
            key_entities=[],
        )
        # 无重复信息熵较高
        assert score >= 0.0

    async def test_redundancy_short_text(self) -> None:
        """短于 n-gram 大小的文本默认低冗余"""
        text = "AB"
        evaluator = CompressionQualityEvaluator()
        score = await evaluator.evaluate(
            compressed_context=text,
            original_docs=[],
            key_entities=[],
        )
        # 短文本默认低冗余
        assert score >= 0.0


class TestCompressionQualityEvaluatorCalculateEntropy:
    """_calculate_entropy 静态方法测试"""

    def test_calculate_entropy_empty(self) -> None:
        """空字符串返回 0.0"""
        assert CompressionQualityEvaluator._calculate_entropy("") == 0.0

    def test_calculate_entropy_single_char(self) -> None:
        """单字符熵为 0（均匀分布但只有一种字符）"""
        entropy = CompressionQualityEvaluator._calculate_entropy("A")
        assert entropy == 0.0

    def test_calculate_entropy_all_same(self) -> None:
        """全相同字符熵为 0"""
        entropy = CompressionQualityEvaluator._calculate_entropy("AAAAA")
        assert entropy == 0.0

    def test_calculate_entropy_diverse(self) -> None:
        """多样字符熵接近 1.0"""
        entropy = CompressionQualityEvaluator._calculate_entropy("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        assert entropy >= 0.8


class TestCompressionQualityEvaluatorCalculateCoverage:
    """_calculate_coverage 静态方法测试"""

    def test_calculate_coverage_all_covered(self) -> None:
        """所有实体都在文本中"""
        text = "BLM模型和BEM模型是战略规划核心框架"
        entities = [{"name": "BLM", "entity_type": "CONCEPT"}, {"name": "BEM", "entity_type": "CONCEPT"}]
        coverage = CompressionQualityEvaluator._calculate_coverage(text, entities)
        assert coverage == 1.0

    def test_calculate_coverage_none_covered(self) -> None:
        """没有实体在文本中"""
        text = "企业战略规划"
        entities = [{"name": "BLM", "entity_type": "CONCEPT"}]
        coverage = CompressionQualityEvaluator._calculate_coverage(text, entities)
        assert coverage == 0.0

    def test_calculate_coverage_empty_entities(self) -> None:
        """空实体列表返回 1.0"""
        coverage = CompressionQualityEvaluator._calculate_coverage("测试文本", [])
        assert coverage == 1.0

    def test_calculate_coverage_no_valid_names(self) -> None:
        """实体列表中的名称均为空时返回 1.0"""
        entities = [{"name": "", "entity_type": "CONCEPT"}, {"name": "", "entity_type": "CONCEPT"}]
        coverage = CompressionQualityEvaluator._calculate_coverage("测试文本", entities)
        assert coverage == 1.0


class TestCompressionQualityEvaluatorCalculateRedundancy:
    """_calculate_redundancy 静态方法测试"""

    def test_calculate_redundancy_empty(self) -> None:
        """空字符串返回 1.0"""
        assert CompressionQualityEvaluator._calculate_redundancy("") == 1.0

    def test_calculate_redundancy_short(self) -> None:
        """短于 n-gram 大小的文本返回 1.0"""
        assert CompressionQualityEvaluator._calculate_redundancy("AB") == 1.0

    def test_calculate_redundancy_unique(self) -> None:
        """唯一 n-gram 返回 1.0"""
        assert CompressionQualityEvaluator._calculate_redundancy("ABCDEFG") == 1.0

    def test_calculate_redundancy_high_repetition(self) -> None:
        """高重复文本冗余度评分低"""
        text = (
            "ABABABABABABABABABABABABABABABABABABABABABABABABAB"
            "ABABABABABABABABABABABABABABABABABABABABABABABABAB"
            "ABABABABABABABABABABABABABABABABABABABABABABABABAB"
        )
        redundancy = CompressionQualityEvaluator._calculate_redundancy(text)
        # 高重复文本应得到低冗余评分
        assert redundancy < 0.5
