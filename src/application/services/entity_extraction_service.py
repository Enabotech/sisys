"""应用层实体抽取编排服务模块

编排规则基→LLM→仲裁→持久化→事件发布完整流程。
遵循六边形架构：依赖领域层端口，不依赖基础设施层具体实现。
"""

from __future__ import annotations

import logging
from typing import Any

from src.domain.events.entity_extraction_events import EntitiesExtracted
from src.domain.exceptions import EntityExtractionError
from src.domain.ports.entity_extraction import (
    EntityArbitratorPort,
    EntityExtractionPort,
    ExtractionResult,
)
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
        event_publisher: Any,
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
                extraction_type = final_result.extraction_metadata.get("strategy", "unknown")
                event = EntitiesExtracted(
                    memory_id=memory_id,
                    entity_count=len(final_result.entities),
                    relation_count=len(final_result.relations),
                    extraction_type=extraction_type,
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

        Args:
            memory_id: 关联记忆 ID
            result: 抽取结果
        """
        # 持久化实体
        for entity in result.entities:
            entity_type_value = _ENTITY_TYPE_MAP.get(entity.entity_type, entity.entity_type.lower())
            properties = {
                "name": entity.name,
                "entity_type": entity_type_value,
                "confidence": entity.confidence,
                "extraction_source": entity.extraction_source,
                "normalized_name": entity.normalized_name or entity.name,
            }
            await self._l5_graph.create_entity(
                memory_id=memory_id,
                entity_type=entity_type_value,
                properties=properties,
            )

        # 持久化关系
        for relation in result.relations:
            await self._l5_graph.create_relationship(
                source_memory_id=memory_id,
                target_memory_id=memory_id,
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
