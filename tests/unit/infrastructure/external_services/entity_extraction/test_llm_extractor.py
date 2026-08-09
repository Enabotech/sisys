"""LLM 语义实体抽取器单元测试

验证 LLMEntityExtractor 的 LLM 调用、降级逻辑和 Schema 验证。
遵循 TDD：红阶段先写失败测试。
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.domain.ports.entity_extraction import (
    EntityExtractionPort,
    ExtractionResult,
)
from src.domain.ports.llm_client import LLMClientPort
from src.infrastructure.external_services.entity_extraction.llm_extractor import (
    LLMEntityExtractor,
)


class TestLLMEntityExtractor:
    """LLMEntityExtractor 测试"""

    @pytest.fixture
    def mock_llm_client(self) -> AsyncMock:
        """创建 Mock LLMClientPort"""
        client = AsyncMock(spec=LLMClientPort)
        return client

    @pytest.fixture
    def extractor(self, mock_llm_client: AsyncMock) -> LLMEntityExtractor:
        """创建 LLMEntityExtractor 实例"""
        return LLMEntityExtractor(llm_client=mock_llm_client)

    def test_implements_entity_extraction_port(self, extractor: LLMEntityExtractor) -> None:
        """验证实现 EntityExtractionPort"""
        assert isinstance(extractor, EntityExtractionPort)

    # --- Happy Path ---

    @pytest.mark.asyncio
    async def test_llm_returns_entities_and_relations(self, extractor: LLMEntityExtractor, mock_llm_client: AsyncMock) -> None:
        """验证 LLM 成功返回实体和关系"""
        # 模拟 LLM 返回结构化结果
        mock_llm_client.structured_generate.return_value = MockExtractionSchema(
            entities=[
                MockEntitySchema(name="BLM", entity_type="CONCEPT", confidence=0.95),
                MockEntitySchema(name="SWOT", entity_type="CONCEPT", confidence=0.90),
            ],
            relations=[
                MockRelationSchema(source="BLM", target="SWOT", relation_type="RELATES_TO", confidence=0.80),
            ],
        )

        result = await extractor.extract_entities("BLM 和 SWOT 是战略工具")
        assert len(result.entities) == 2
        assert len(result.relations) == 1
        assert result.entities[0].name == "BLM"
        assert result.entities[0].extraction_source == "llm"
        assert result.relations[0].extraction_source == "llm"

    @pytest.mark.asyncio
    async def test_extraction_metadata_contains_llm_strategy(
        self, extractor: LLMEntityExtractor, mock_llm_client: AsyncMock
    ) -> None:
        """验证抽取元数据包含 LLM 策略"""
        mock_llm_client.structured_generate.return_value = MockExtractionSchema(
            entities=[MockEntitySchema(name="BLM", entity_type="CONCEPT", confidence=0.95)],
            relations=[],
        )
        result = await extractor.extract_entities("BLM 模型")
        assert result.extraction_metadata.get("strategy") == "llm"

    # --- Edge Case: LLM 调用失败 ---

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty_result(self, extractor: LLMEntityExtractor, mock_llm_client: AsyncMock) -> None:
        """验证 LLM 调用失败时返回空结果（透明降级）"""
        from src.domain.exceptions import LLMAPIError

        mock_llm_client.structured_generate.side_effect = LLMAPIError("LLM API 错误")

        result = await extractor.extract_entities("测试内容")
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 0
        assert len(result.relations) == 0

    # --- Edge Case: LLM 返回空实体列表 ---

    @pytest.mark.asyncio
    async def test_llm_returns_empty_entities(self, extractor: LLMEntityExtractor, mock_llm_client: AsyncMock) -> None:
        """验证 LLM 返回空实体列表时返回空结果"""
        mock_llm_client.structured_generate.return_value = MockExtractionSchema(
            entities=[],
            relations=[],
        )

        result = await extractor.extract_entities("测试内容")
        assert len(result.entities) == 0
        assert len(result.relations) == 0

    # --- Edge Case: Schema 验证失败 ---

    @pytest.mark.asyncio
    async def test_schema_validation_failure_returns_empty(
        self, extractor: LLMEntityExtractor, mock_llm_client: AsyncMock
    ) -> None:
        """验证 Schema 验证失败时降级至空结果"""
        from src.domain.exceptions import LLMResponseError

        mock_llm_client.structured_generate.side_effect = LLMResponseError("Schema 验证失败")

        result = await extractor.extract_entities("测试内容")
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 0


# --- 辅助 Mock Schema 类 ---


class MockEntitySchema:
    """模拟 Pydantic Schema 实体"""

    def __init__(self, name: str, entity_type: str, confidence: float):
        self.name = name
        self.entity_type = entity_type
        self.confidence = confidence


class MockRelationSchema:
    """模拟 Pydantic Schema 关系"""

    def __init__(self, source: str, target: str, relation_type: str, confidence: float):
        self.source = source
        self.target = target
        self.relation_type = relation_type
        self.confidence = confidence


class MockExtractionSchema:
    """模拟实体抽取 Schema 返回"""

    def __init__(self, entities: list, relations: list):
        self.entities = entities
        self.relations = relations
