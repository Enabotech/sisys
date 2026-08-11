"""冲突仲裁器单元测试

验证 ConflictArbitrator 的实体融合、置信度加权、关系去重和仲裁准确率。
遵循 TDD：红阶段先写失败测试。
"""

from __future__ import annotations

import pytest

from src.domain.ports.entity_extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from src.infrastructure.external_services.entity_extraction.conflict_arbitrator import (
    ConflictArbitrator,
)


class TestConflictArbitrator:
    """ConflictArbitrator 测试"""

    @pytest.fixture
    def arbitrator(self) -> ConflictArbitrator:
        """创建 ConflictArbitrator 实例"""
        return ConflictArbitrator()

    # --- Happy Path: 实体融合 ---

    def test_merge_same_entity_weighted_average(self, arbitrator: ConflictArbitrator) -> None:
        """验证规则+LLM 相同实体融合（置信度加权平均）"""
        rule_result = ExtractionResult(
            entities=(ExtractedEntity(name="BLM", entity_type="CONCEPT", confidence=0.9, extraction_source="rule"),),
        )
        llm_result = ExtractionResult(
            entities=(ExtractedEntity(name="BLM", entity_type="CONCEPT", confidence=0.7, extraction_source="llm"),),
        )
        final = arbitrator.arbitrate(rule_result, llm_result)
        assert len(final.entities) == 1
        assert final.entities[0].name == "BLM"
        # 默认权重 rule=0.6, llm=0.4 -> 0.9*0.6 + 0.7*0.4 = 0.54+0.28=0.82
        assert abs(final.entities[0].confidence - 0.82) < 0.01
        assert final.entities[0].extraction_source == "hybrid"

    def test_merge_different_entities_preserve_both(self, arbitrator: ConflictArbitrator) -> None:
        """验证规则+LLM 不同实体合并（保留两者）"""
        rule_result = ExtractionResult(
            entities=(ExtractedEntity(name="BLM", entity_type="CONCEPT", confidence=0.9, extraction_source="rule"),),
        )
        llm_result = ExtractionResult(
            entities=(ExtractedEntity(name="SWOT", entity_type="CONCEPT", confidence=0.8, extraction_source="llm"),),
        )
        final = arbitrator.arbitrate(rule_result, llm_result)
        assert len(final.entities) == 2
        names = {e.name for e in final.entities}
        assert names == {"BLM", "SWOT"}

    def test_entity_type_specific_weights(self, arbitrator: ConflictArbitrator) -> None:
        """验证按实体类型差异化配置权重"""
        # 为 CONCEPT 类型设置 rule=0.7, llm=0.3
        arbitrator.set_entity_type_weight("CONCEPT", rule_weight=0.7, llm_weight=0.3)

        rule_result = ExtractionResult(
            entities=(ExtractedEntity(name="BLM", entity_type="CONCEPT", confidence=0.9, extraction_source="rule"),),
        )
        llm_result = ExtractionResult(
            entities=(ExtractedEntity(name="BLM", entity_type="CONCEPT", confidence=0.7, extraction_source="llm"),),
        )
        final = arbitrator.arbitrate(rule_result, llm_result)
        # 0.9*0.7 + 0.7*0.3 = 0.63+0.21=0.84
        assert abs(final.entities[0].confidence - 0.84) < 0.01

    # --- Happy Path: 关系融合 ---

    def test_merge_relations_dedup(self, arbitrator: ConflictArbitrator) -> None:
        """验证规则基关系 + LLM 语义关系去重合并"""
        rule_result = ExtractionResult(
            entities=(
                ExtractedEntity(name="BLM", entity_type="CONCEPT", confidence=0.9, extraction_source="rule"),
                ExtractedEntity(name="SWOT", entity_type="CONCEPT", confidence=0.8, extraction_source="rule"),
            ),
            relations=(
                ExtractedRelation(
                    source="BLM",
                    target="SWOT",
                    relation_type="RELATES_TO",
                    confidence=0.8,
                    extraction_source="rule",
                ),
            ),
        )
        llm_result = ExtractionResult(
            relations=(
                ExtractedRelation(
                    source="BLM",
                    target="SWOT",
                    relation_type="RELATES_TO",
                    confidence=0.7,
                    extraction_source="llm",
                ),
                ExtractedRelation(
                    source="BLM",
                    target="PESTEL",
                    relation_type="RELATES_TO",
                    confidence=0.6,
                    extraction_source="llm",
                ),
            ),
        )
        final = arbitrator.arbitrate(rule_result, llm_result)
        # 去重后应有 2 条关系（BLM→SWOT 合并，BLM→PESTEL 保留）
        assert len(final.relations) == 2
        # BLM→SWOT 应合并（置信度加权平均）
        blm_swot = [r for r in final.relations if r.target == "SWOT"][0]
        assert abs(blm_swot.confidence - 0.76) < 0.01  # 0.8*0.6 + 0.7*0.4 = 0.48+0.28=0.76
        assert blm_swot.extraction_source == "hybrid"

    # --- Edge Case: 单路结果 ---

    def test_only_rule_result(self, arbitrator: ConflictArbitrator) -> None:
        """验证仅规则基结果直接返回"""
        rule_result = ExtractionResult(
            entities=(ExtractedEntity(name="BLM", entity_type="CONCEPT", confidence=0.9, extraction_source="rule"),),
        )
        llm_result = ExtractionResult()
        final = arbitrator.arbitrate(rule_result, llm_result)
        assert len(final.entities) == 1
        assert final.entities[0].extraction_source == "rule"

    def test_only_llm_result(self, arbitrator: ConflictArbitrator) -> None:
        """验证仅 LLM 结果直接返回"""
        rule_result = ExtractionResult()
        llm_result = ExtractionResult(
            entities=(ExtractedEntity(name="BLM", entity_type="CONCEPT", confidence=0.9, extraction_source="llm"),),
        )
        final = arbitrator.arbitrate(rule_result, llm_result)
        assert len(final.entities) == 1
        assert final.entities[0].extraction_source == "llm"

    def test_both_empty(self, arbitrator: ConflictArbitrator) -> None:
        """验证两者均为空返回空结果"""
        final = arbitrator.arbitrate(ExtractionResult(), ExtractionResult())
        assert len(final.entities) == 0
        assert len(final.relations) == 0

    def test_confidence_conflict_weighted_average(self, arbitrator: ConflictArbitrator) -> None:
        """验证同一实体置信度冲突时使用加权平均（AC-6规范）"""
        rule_result = ExtractionResult(
            entities=(ExtractedEntity(name="BLM", entity_type="CONCEPT", confidence=0.4, extraction_source="rule"),),
        )
        llm_result = ExtractionResult(
            entities=(ExtractedEntity(name="BLM", entity_type="CONCEPT", confidence=0.95, extraction_source="llm"),),
        )
        # 虽然 LLM 置信度高，但仲裁使用加权平均
        final = arbitrator.arbitrate(rule_result, llm_result)
        # 0.4*0.6 + 0.95*0.4 = 0.24+0.38=0.62
        assert abs(final.entities[0].confidence - 0.62) < 0.01

    # --- 仲裁准确率验证 ---

    def test_arbitration_accuracy_above_85_percent(self, arbitrator: ConflictArbitrator) -> None:
        """验证仲裁准确率≥85%"""
        test_cases = [
            # (规则实体, LLM 实体, 期望实体数, 期望名称)
            (
                [("BLM", 0.9), ("SWOT", 0.8)],
                [("BLM", 0.7), ("PESTEL", 0.85)],
                3,  # BLM 合并 + SWOT + PESTEL
            ),
            (
                [("BLM", 0.9)],
                [("BLM", 0.95)],
                1,  # 完全一致
            ),
            (
                [],
                [("BLM", 0.9)],
                1,  # 仅 LLM
            ),
            (
                [("BLM", 0.9)],
                [],
                1,  # 仅规则
            ),
        ]

        correct = 0
        for rule_entities, llm_entities, expected_count, *_ in test_cases:
            rule_result = ExtractionResult(
                entities=tuple(
                    ExtractedEntity(name=name, entity_type="CONCEPT", confidence=conf, extraction_source="rule")
                    for name, conf in rule_entities
                ),
            )
            llm_result = ExtractionResult(
                entities=tuple(
                    ExtractedEntity(name=name, entity_type="CONCEPT", confidence=conf, extraction_source="llm")
                    for name, conf in llm_entities
                ),
            )
            final = arbitrator.arbitrate(rule_result, llm_result)
            if len(final.entities) == expected_count:
                correct += 1

        accuracy = correct / len(test_cases)
        assert accuracy >= 0.85, f"仲裁准确率 {accuracy:.0%} < 85%"
