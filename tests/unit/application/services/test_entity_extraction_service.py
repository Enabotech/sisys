"""实体抽取编排服务单元测试

验证 EntityExtractionService 的完整编排流程：
规则基→LLM→仲裁→持久化→事件发布。
遵循 TDD：红阶段先写失败测试。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from src.application.services.entity_extraction_service import EntityExtractionService
from src.domain.events.entity_extraction_events import EntitiesExtracted
from src.domain.events.publish_result import PublishResult
from src.domain.ports.entity_extraction import (
    EntityExtractionPort,
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from src.domain.ports.l5_graph import L5GraphPort
from src.infrastructure.external_services.entity_extraction.conflict_arbitrator import (
    ConflictArbitrator,
)


class TestEntityExtractionService:
    """EntityExtractionService 测试"""

    @pytest.fixture
    def rule_extractor(self) -> AsyncMock:
        """创建 Mock 规则基抽取器"""
        extractor = AsyncMock(spec=EntityExtractionPort)
        extractor.extract_entities.return_value = ExtractionResult(
            entities=(ExtractedEntity(name="BLM", entity_type="CONCEPT", confidence=0.9, extraction_source="rule"),),
        )
        return extractor

    @pytest.fixture
    def llm_extractor(self) -> AsyncMock:
        """创建 Mock LLM 抽取器"""
        extractor = AsyncMock(spec=EntityExtractionPort)
        extractor.extract_entities.return_value = ExtractionResult(
            entities=(
                ExtractedEntity(name="BLM", entity_type="CONCEPT", confidence=0.7, extraction_source="llm"),
                ExtractedEntity(name="SWOT", entity_type="CONCEPT", confidence=0.8, extraction_source="llm"),
            ),
            relations=(
                ExtractedRelation(
                    source="BLM",
                    target="SWOT",
                    relation_type="RELATES_TO",
                    confidence=0.8,
                    extraction_source="llm",
                ),
            ),
        )
        return extractor

    @pytest.fixture
    def l5_graph(self) -> AsyncMock:
        """创建 Mock L5GraphPort"""
        graph = AsyncMock(spec=L5GraphPort)
        graph.create_entity.return_value = True
        graph.create_relationship.return_value = True
        return graph

    @pytest.fixture
    def arbitrator(self) -> ConflictArbitrator:
        """创建真实 ConflictArbitrator"""
        return ConflictArbitrator()

    @pytest.fixture
    def event_publisher(self) -> AsyncMock:
        """创建 Mock 事件发布器"""
        publisher = AsyncMock()
        publish_result = MagicMock(spec=PublishResult)
        # 使用 PropertyMock 模拟 is_success 属性
        type(publish_result).is_success = PropertyMock(return_value=True)
        publisher.publish.return_value = publish_result
        return publisher

    @pytest.fixture
    def service(
        self,
        rule_extractor: AsyncMock,
        llm_extractor: AsyncMock,
        l5_graph: AsyncMock,
        arbitrator: ConflictArbitrator,
        event_publisher: AsyncMock,
    ) -> EntityExtractionService:
        """创建 EntityExtractionService 实例"""
        return EntityExtractionService(
            rule_extractor=rule_extractor,
            llm_extractor=llm_extractor,
            l5_graph=l5_graph,
            arbitrator=arbitrator,
            event_publisher=event_publisher,
        )

    # --- Happy Path: 完整流程 ---

    @pytest.mark.asyncio
    async def test_full_pipeline(
        self,
        service: EntityExtractionService,
        rule_extractor: AsyncMock,
        llm_extractor: AsyncMock,
        l5_graph: AsyncMock,
        event_publisher: AsyncMock,
    ) -> None:
        """验证完整流程执行（规则→LLM→仲裁→持久化→事件发布）"""
        result = await service.extract_entities(
            content="BLM 和 SWOT 是常用战略工具",
            memory_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        )

        # 验证规则基和 LLM 都被调用
        rule_extractor.extract_entities.assert_called_once()
        llm_extractor.extract_entities.assert_called_once()

        # 验证持久化（实体 + 关系）
        assert l5_graph.create_entity.call_count >= 2  # BLM 和 SWOT（仲裁后合并 BLM + SWOT 至少 2 个）
        assert l5_graph.create_relationship.call_count >= 1  # BLM→SWOT

        # 验证事件发布
        event_publisher.publish.assert_called_once()
        published_event = event_publisher.publish.call_args[0][0]
        assert isinstance(published_event, EntitiesExtracted)
        assert published_event.memory_id == uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        assert published_event.entity_count >= 2
        assert published_event.relation_count >= 1
        assert published_event.extraction_type == "hybrid"
        assert published_event.source == "entity_extraction_service"

        # 验证返回完整结果
        assert result is not None
        assert len(result.entities) >= 2
        assert len(result.relations) >= 1

    # --- Happy Path: 抽取结果写入 Neo4j ---

    @pytest.mark.asyncio
    async def test_neo4j_persistence(
        self,
        service: EntityExtractionService,
        l5_graph: AsyncMock,
    ) -> None:
        """验证抽取结果正确写入 Neo4j"""
        await service.extract_entities(
            content="BLM 模型",
            memory_id="test-mem-002",
        )

        # 验证 create_entity 被调用
        l5_graph.create_entity.assert_called()
        # 每个实体生成独立节点 ID（基于 memory_id 的确定性哈希）
        node_ids: list[str] = []
        for call_args in l5_graph.create_entity.call_args_list:
            kwargs = call_args[1] if len(call_args) > 1 else {}
            if "memory_id" in kwargs:
                mid = kwargs["memory_id"]
                node_ids.append(mid)
                assert mid.startswith("test-mem-002"), f"节点ID应含memory_id前缀: {mid}"
                assert ":" in mid, f"节点ID应含实体哈希后缀: {mid}"
        # 不同实体名称应生成不同节点 ID（独立节点）
        assert len(set(node_ids)) >= 2, "BLM 与 SWOT 应生成不同节点 ID"

    # --- Edge Case: LLM 调用失败降级 ---

    @pytest.mark.asyncio
    async def test_llm_failure_fallback_to_rule(
        self,
        service: EntityExtractionService,
        llm_extractor: AsyncMock,
        event_publisher: AsyncMock,
    ) -> None:
        """验证 LLM 调用失败降级至仅规则基结果"""
        # LLM 返回空结果（透明降级）
        llm_extractor.extract_entities.return_value = ExtractionResult(
            extraction_metadata={"strategy": "llm", "entity_count": 0, "error": "mock error"},
        )

        result = await service.extract_entities(
            content="BLM 模型",
            memory_id="test-mem-003",
        )

        # 验证仍返回结果（规则基结果）
        assert len(result.entities) >= 1
        # 事件应发布（hybrid 或 rule_only）
        assert event_publisher.publish.called

    # --- Edge Case: 空内容输入 ---

    @pytest.mark.asyncio
    async def test_empty_content(
        self,
        service: EntityExtractionService,
        rule_extractor: AsyncMock,
        llm_extractor: AsyncMock,
    ) -> None:
        """验证空内容输入返回空结果（不抛出异常）"""
        result = await service.extract_entities(
            content="",
            memory_id="test-mem-004",
        )
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 0
        assert len(result.relations) == 0
        # 规则基和 LLM 不应被调用
        rule_extractor.extract_entities.assert_not_called()
        llm_extractor.extract_entities.assert_not_called()

    # --- Edge Case: 规则基返回空 ---

    @pytest.mark.asyncio
    async def test_rule_empty_use_llm_only(
        self,
        service: EntityExtractionService,
        rule_extractor: AsyncMock,
        event_publisher: AsyncMock,
    ) -> None:
        """验证规则基返回空时仅使用 LLM 结果"""
        rule_extractor.extract_entities.return_value = ExtractionResult(
            extraction_metadata={"strategy": "rule", "entity_count": 0},
        )

        result = await service.extract_entities(
            content="BLM 模型",
            memory_id="test-mem-005",
        )

        # 验证仍返回结果（LLM 结果）
        assert len(result.entities) >= 1
        # 所有实体来源应为 llm
        assert all(e.extraction_source == "llm" for e in result.entities)

    # --- Edge Case: 持久化失败 ---

    @pytest.mark.asyncio
    async def test_persistence_failure_raises_error(
        self,
        service: EntityExtractionService,
        l5_graph: AsyncMock,
    ) -> None:
        """验证持久化失败抛出 EntityExtractionError（包装原始异常）"""
        from src.domain.exceptions import EntityExtractionError

        l5_graph.create_entity.side_effect = RuntimeError("Neo4j 连接超时")

        with pytest.raises(EntityExtractionError) as exc_info:
            await service.extract_entities(
                content="BLM 模型",
                memory_id="test-mem-006",
            )
        assert exc_info.value.code == "EXCEPTION_340"
        assert exc_info.value.context.get("entity_count", -1) >= 0
        assert exc_info.value.context.get("content_preview", "") == "BLM 模型"

    # --- Edge Case: 事件发布失败记录日志 ---

    @pytest.mark.asyncio
    async def test_event_publish_failure_logs_only(
        self,
        service: EntityExtractionService,
        event_publisher: AsyncMock,
    ) -> None:
        """验证事件发布失败时记录日志，不阻止主流程返回 ExtractionResult"""
        publish_result = MagicMock(spec=PublishResult)
        type(publish_result).is_success = PropertyMock(return_value=False)
        event_publisher.publish.return_value = publish_result

        # 不应抛出异常
        result = await service.extract_entities(
            content="BLM 模型",
            memory_id="test-mem-007",
        )
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) >= 1
