"""基础设施层冲突仲裁器模块

实现规则基 + LLM 双路抽取结果的冲突仲裁。
支持按实体类型差异化配置权重，实体合并策略（置信度加权平均），关系去重合并。
"""

from __future__ import annotations

from typing import Any

from src.domain.ports.entity_extraction import (
    EntityArbitratorPort,
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)

# 默认权重配置
_DEFAULT_RULE_WEIGHT = 0.6
_DEFAULT_LLM_WEIGHT = 0.4


class ConflictArbitrator(EntityArbitratorPort):
    """冲突仲裁器

    规则基 + LLM 双路抽取结果的融合仲裁。
    支持按实体类型差异化配置权重。

    Attributes:
        _entity_type_weights: 按实体类型配置的权重映射
        _default_rule_weight: 默认规则权重
        _default_llm_weight: 默认 LLM 权重
    """

    def __init__(
        self,
        default_rule_weight: float = _DEFAULT_RULE_WEIGHT,
        default_llm_weight: float = _DEFAULT_LLM_WEIGHT,
    ) -> None:
        """初始化冲突仲裁器

        Args:
            default_rule_weight: 默认规则权重（默认 0.6）
            default_llm_weight: 默认 LLM 权重（默认 0.4）
        """
        self._default_rule_weight = default_rule_weight
        self._default_llm_weight = default_llm_weight
        self._entity_type_weights: dict[str, tuple[float, float]] = {}
        self._relation_type_weights: dict[str, tuple[float, float]] = {}

    def set_entity_type_weight(
        self,
        entity_type: str,
        rule_weight: float,
        llm_weight: float,
    ) -> None:
        """设置实体类型的差异化权重

        Args:
            entity_type: 实体类型
            rule_weight: 规则权重
            llm_weight: LLM 权重
        """
        self._entity_type_weights[entity_type] = (rule_weight, llm_weight)

    def set_relation_type_weight(
        self,
        relation_type: str,
        rule_weight: float,
        llm_weight: float,
    ) -> None:
        """设置关系类型的差异化权重

        Args:
            relation_type: 关系类型
            rule_weight: 规则权重
            llm_weight: LLM 权重
        """
        self._relation_type_weights[relation_type] = (rule_weight, llm_weight)

    def _get_weights(self, entity_type: str) -> tuple[float, float]:
        """获取实体类型的权重

        Args:
            entity_type: 实体类型

        Returns:
            (rule_weight, llm_weight) 权重元组
        """
        if entity_type in self._entity_type_weights:
            return self._entity_type_weights[entity_type]
        return (self._default_rule_weight, self._default_llm_weight)

    def _get_relation_weights(self, relation_type: str) -> tuple[float, float]:
        """获取关系类型的权重

        Args:
            relation_type: 关系类型

        Returns:
            (rule_weight, llm_weight) 权重元组
        """
        if relation_type in self._relation_type_weights:
            return self._relation_type_weights[relation_type]
        return (self._default_rule_weight, self._default_llm_weight)

    def arbitrate(
        self,
        rule_result: ExtractionResult,
        llm_result: ExtractionResult,
    ) -> ExtractionResult:
        """执行冲突仲裁

        Args:
            rule_result: 规则基抽取结果
            llm_result: LLM 语义抽取结果

        Returns:
            融合后的 ExtractionResult
        """
        # 如果一方为空，直接返回另一方
        if not rule_result.entities and not rule_result.relations:
            return llm_result
        if not llm_result.entities and not llm_result.relations:
            return rule_result

        # 实体合并
        merged_entities = self._merge_entities(rule_result.entities, llm_result.entities)

        # 关系合并
        merged_relations = self._merge_relations(rule_result.relations, llm_result.relations)

        # 合并元数据
        metadata: dict[str, Any] = {
            "strategy": "hybrid",
            "rule_entity_count": len(rule_result.entities),
            "llm_entity_count": len(llm_result.entities),
            "final_entity_count": len(merged_entities),
            "final_relation_count": len(merged_relations),
        }

        return ExtractionResult(
            entities=tuple(merged_entities),
            relations=tuple(merged_relations),
            extraction_metadata=metadata,
        )

    def _merge_entities(
        self,
        rule_entities: tuple[ExtractedEntity, ...],
        llm_entities: tuple[ExtractedEntity, ...],
    ) -> list[ExtractedEntity]:
        """合并实体列表

        按名称匹配，相同实体使用置信度加权平均。
        不同实体保留两者。

        Args:
            rule_entities: 规则基实体列表
            llm_entities: LLM 实体列表

        Returns:
            合并后的实体列表
        """
        # 构建名称到实体的映射
        rule_map: dict[str, ExtractedEntity] = {}
        for entity in rule_entities:
            name = entity.normalized_name or entity.name
            rule_map[name] = entity

        llm_map: dict[str, ExtractedEntity] = {}
        for entity in llm_entities:
            name = entity.normalized_name or entity.name
            llm_map[name] = entity

        # 所有实体名称
        all_names = set(rule_map.keys()) | set(llm_map.keys())

        result: list[ExtractedEntity] = []
        for name in all_names:
            rule_entity = rule_map.get(name)
            llm_entity = llm_map.get(name)

            if rule_entity is not None and llm_entity is not None:
                # 两者都存在 → 加权平均
                rule_weight, llm_weight = self._get_weights(rule_entity.entity_type)
                weighted_confidence = rule_entity.confidence * rule_weight + llm_entity.confidence * llm_weight
                # 保留较高置信度的来源或 hybrid
                source = (
                    "hybrid" if rule_entity.extraction_source != llm_entity.extraction_source else rule_entity.extraction_source
                )
                result.append(
                    ExtractedEntity(
                        name=rule_entity.name,
                        entity_type=rule_entity.entity_type,
                        confidence=round(weighted_confidence, 4),
                        extraction_source=source,
                        normalized_name=rule_entity.normalized_name or llm_entity.normalized_name,
                        metadata={**rule_entity.metadata, **llm_entity.metadata},
                    )
                )
            elif rule_entity is not None:
                result.append(rule_entity)
            elif llm_entity is not None:
                result.append(llm_entity)

        return result

    def _merge_relations(
        self,
        rule_relations: tuple[ExtractedRelation, ...],
        llm_relations: tuple[ExtractedRelation, ...],
    ) -> list[ExtractedRelation]:
        """合并关系列表

        按 (source, target, relation_type) 三元组去重。
        相同关系使用置信度加权平均。

        Args:
            rule_relations: 规则基关系列表
            llm_relations: LLM 关系列表

        Returns:
            合并后的关系列表
        """

        def rel_key(rel: ExtractedRelation) -> tuple[str, str, str]:
            return (rel.source, rel.target, rel.relation_type)

        rule_map: dict[tuple[str, str, str], ExtractedRelation] = {}
        for rel in rule_relations:
            rule_map[rel_key(rel)] = rel

        llm_map: dict[tuple[str, str, str], ExtractedRelation] = {}
        for rel in llm_relations:
            llm_map[rel_key(rel)] = rel

        all_keys = set(rule_map.keys()) | set(llm_map.keys())

        result: list[ExtractedRelation] = []
        for key in all_keys:
            rule_rel = rule_map.get(key)
            llm_rel = llm_map.get(key)

            if rule_rel is not None and llm_rel is not None:
                # 两者都存在 → 加权平均（使用关系类型专属权重，避免与实体类型混淆）
                rule_weight, llm_weight = self._get_relation_weights(rule_rel.relation_type)
                weighted_confidence = rule_rel.confidence * rule_weight + llm_rel.confidence * llm_weight
                source = "hybrid" if rule_rel.extraction_source != llm_rel.extraction_source else rule_rel.extraction_source
                result.append(
                    ExtractedRelation(
                        source=rule_rel.source,
                        target=rule_rel.target,
                        relation_type=rule_rel.relation_type,
                        confidence=round(weighted_confidence, 4),
                        extraction_source=source,
                        metadata={**rule_rel.metadata, **llm_rel.metadata},
                    )
                )
            elif rule_rel is not None:
                result.append(rule_rel)
            elif llm_rel is not None:
                result.append(llm_rel)

        return result


__all__ = [
    "ConflictArbitrator",
]
