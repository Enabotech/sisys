"""应用层实体抽取编排服务模块

编排规则基→LLM→仲裁→持久化→事件发布完整流程。
遵循六边形架构：依赖领域层端口，不依赖基础设施层具体实现。
"""

from __future__ import annotations

import hashlib
import logging

from src.domain.events.entity_extraction_events import EntitiesExtracted
from src.domain.exceptions import EntityExtractionError
from src.domain.ports.entity_extraction import (
    EntityArbitratorPort,
    EntityExtractionPort,
    ExtractionResult,
)
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.l5_graph import L5GraphPort

logger = logging.getLogger(__name__)

# 实体类型到 Neo4j entity_type 属性值的映射
_ENTITY_TYPE_MAP: dict[str, str] = {
    "PERSON": "person",
    "ORG": "organization",
    "LOC": "location",
    "PRODUCT": "product",
    "CONCEPT": "concept",
    "DATE": "date",
    "AMOUNT": "amount",
    "PERCENT": "percent",
    "CONTACT": "contact",
}


def _make_entity_node_id(memory_id: str, entity_name: str) -> str:
    """为抽取实体生成独立的 Neo4j 节点 ID

    基于 memory_id + 实体名称的确定性哈希，确保：
    - 同一 memory_id 下不同实体名称 → 不同节点 ID（独立节点）
    - 同一 memory_id + 同一实体名称 → 相同节点 ID（幂等 MERGE）

    Args:
        memory_id: 关联记忆 ID
        entity_name: 实体名称

    Returns:
        Neo4j 节点 ID（格式: {memory_id}:{sha256前16位}）
    """
    suffix = hashlib.sha256(entity_name.encode("utf-8")).hexdigest()[:16]
    return f"{memory_id}:{suffix}"


def _map_extraction_type(result: ExtractionResult) -> str:
    """将仲裁策略映射为领域事件规范定义的 extraction_type 值

    SDD 规范定义 extraction_type 合法值为 "rule_only" / "llm_only" / "hybrid"。
    仲裁器 metadata 中的 strategy 取值为 "rule" / "llm" / "hybrid"，
    此处按抽取结果实际来源分布映射为规范值。

    Args:
        result: 仲裁后的抽取结果

    Returns:
        extraction_type 规范值（rule_only / llm_only / hybrid）
    """
    strategy = result.extraction_metadata.get("strategy", "")

    # 有实体/关系时按实际来源判定
    # hybrid 表示规则+LLM均有贡献，rule 表示仅规则，llm 表示仅 LLM
    has_rule = any(e.extraction_source in ("rule", "hybrid") for e in result.entities)
    has_llm = any(e.extraction_source in ("llm", "hybrid") for e in result.entities)

    if has_rule and has_llm:
        return "hybrid"
    if has_rule:
        return "rule_only"
    if has_llm:
        return "llm_only"
    # 无实体时回退到仲裁器策略或默认值
    if strategy == "hybrid":
        return "hybrid"
    if strategy == "llm":
        return "llm_only"
    if strategy == "rule":
        return "rule_only"
    return "unknown"


class EntityExtractionService:
    """实体抽取编排服务

    编排规则基抽取→LLM 语义抽取→冲突仲裁→Neo4j 持久化→事件发布完整流程。

    Attributes:
        rule_extractor: 规则基实体抽取器（实现 EntityExtractionPort）
        llm_extractor: LLM 语义实体抽取器（实现 EntityExtractionPort）
        l5_graph: Neo4j 图存储端口
        arbitrator: 冲突仲裁器
        event_publisher: 事件发布器
    """

    def __init__(
        self,
        rule_extractor: EntityExtractionPort,
        llm_extractor: EntityExtractionPort,
        l5_graph: L5GraphPort,
        arbitrator: EntityArbitratorPort,
        event_publisher: EventPublisher,
    ) -> None:
        """初始化实体抽取编排服务

        Args:
            rule_extractor: 规则基实体抽取器
            llm_extractor: LLM 语义实体抽取器
            l5_graph: L5 图存储端口
            arbitrator: 冲突仲裁器
            event_publisher: 事件发布器
        """
        self._rule_extractor = rule_extractor
        self._llm_extractor = llm_extractor
        self._l5_graph = l5_graph
        self._arbitrator = arbitrator
        self._event_publisher = event_publisher

    async def extract_entities(
        self,
        content: str,
        memory_id: str = "",
        domain_context: dict | None = None,
    ) -> ExtractionResult:
        """执行完整实体抽取流程

        1. 规则基抽取 → rule_result
        2. LLM 语义抽取 → llm_result（失败时透明降级）
        3. 冲突仲裁 → final_result
        4. Neo4j 持久化（实体 + 关系）
        5. 事件发布

        Args:
            content: 待抽取的文本内容
            memory_id: 关联记忆 ID（用于 Neo4j 持久化）
            domain_context: 领域上下文（可选）

        Returns:
            ExtractionResult 完整抽取结果

        Raises:
            EntityExtractionError: 持久化失败时抛出
        """
        # 输入验证：空内容返回空结果
        if not content or not content.strip():
            logger.warning("实体抽取输入为空，返回空结果")
            return ExtractionResult(extraction_metadata={"strategy": "none", "entity_count": 0})

        # 1. 规则基抽取
        try:
            rule_result = await self._rule_extractor.extract_entities(content, domain_context)
        except Exception as e:
            raise EntityExtractionError(
                "规则基实体抽取失败",
                cause=e,
                extraction_strategy="rule",
                content_preview=content[:200],
            ) from e

        # 2. LLM 语义抽取（透明降级）
        try:
            llm_result = await self._llm_extractor.extract_entities(content, domain_context)
        except Exception:
            logger.warning("LLM 实体抽取失败，降级至仅规则基结果")
            llm_result = ExtractionResult(extraction_metadata={"strategy": "llm", "entity_count": 0, "error": "LLM 调用异常"})

        # 3. 冲突仲裁
        final_result = self._arbitrator.arbitrate(rule_result, llm_result)

        # 4. Neo4j 持久化
        if memory_id and (final_result.entities or final_result.relations):
            try:
                await self._persist_to_neo4j(memory_id, final_result)
            except EntityExtractionError:
                raise
            except Exception as e:
                raise EntityExtractionError(
                    "Neo4j 持久化失败",
                    cause=e,
                    extraction_strategy=final_result.extraction_metadata.get("strategy", "unknown"),
                    entity_count=len(final_result.entities),
                    content_preview=content[:200],
                ) from e

        # 5. 发布事件
        if memory_id:
            try:
                extraction_type = _map_extraction_type(final_result)
                event = EntitiesExtracted(
                    memory_id=memory_id,
                    entity_count=len(final_result.entities),
                    relation_count=len(final_result.relations),
                    extraction_type=extraction_type,
                    source="entity_extraction_service",
                )
                publish_result = await self._event_publisher.publish(event)
                if not publish_result.is_success:
                    logger.warning("EntitiesExtracted 事件发布失败: %s", publish_result.partial_error)
            except Exception as e:
                logger.warning("EntitiesExtracted 事件发布异常: %s", e)

        return final_result

    async def _persist_to_neo4j(
        self,
        memory_id: str,
        result: ExtractionResult,
    ) -> None:
        """将抽取结果持久化到 Neo4j

        每个抽取实体生成独立节点 ID（memory_id + 实体名称哈希），
        关系通过实体节点 ID 建立有向边，形成正确的"实体-关系-实体"三元组图结构。

        Args:
            memory_id: 关联记忆 ID
            result: 抽取结果
        """
        # 持久化实体
        entity_node_ids: dict[str, str] = {}
        for entity in result.entities:
            entity_type_value = _ENTITY_TYPE_MAP.get(entity.entity_type, entity.entity_type.lower())
            entity_node_id = _make_entity_node_id(memory_id, entity.name)
            entity_node_ids[entity.name] = entity_node_id
            properties = {
                "name": entity.name,
                "entity_type": entity_type_value,
                "confidence": entity.confidence,
                "extraction_source": entity.extraction_source,
                "normalized_name": entity.normalized_name or entity.name,
            }
            await self._l5_graph.create_entity(
                memory_id=entity_node_id,
                entity_type=entity_type_value,
                properties=properties,
            )

        # 持久化关系
        for relation in result.relations:
            # 如果关系源/目标实体未被抽取为独立实体，为其创建占位节点
            if relation.source not in entity_node_ids:
                placeholder_id = _make_entity_node_id(memory_id, relation.source)
                entity_node_ids[relation.source] = placeholder_id
                await self._l5_graph.create_entity(
                    memory_id=placeholder_id,
                    entity_type="unknown",
                    properties={"name": relation.source, "extraction_source": "relation"},
                )
            if relation.target not in entity_node_ids:
                placeholder_id = _make_entity_node_id(memory_id, relation.target)
                entity_node_ids[relation.target] = placeholder_id
                await self._l5_graph.create_entity(
                    memory_id=placeholder_id,
                    entity_type="unknown",
                    properties={"name": relation.target, "extraction_source": "relation"},
                )

            source_node_id = entity_node_ids[relation.source]
            target_node_id = entity_node_ids[relation.target]
            await self._l5_graph.create_relationship(
                source_memory_id=source_node_id,
                target_memory_id=target_node_id,
                relationship_type=relation.relation_type,
                properties={
                    "source_name": relation.source,
                    "target_name": relation.target,
                    "confidence": relation.confidence,
                    "extraction_source": relation.extraction_source,
                },
            )


__all__ = [
    "EntityExtractionService",
]
