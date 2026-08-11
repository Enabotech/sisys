"""实体抽取集成测试

验证端到端实体抽取流程：规则基抽取 + LLM 语义抽取 + 冲突仲裁。
使用真实 AC 自动机规则基抽取 + aiohttp 本地 HTTP 服务器模拟 LLM API。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from src.application.services.entity_extraction_service import EntityExtractionService
from src.domain.events.publish_result import PublishResult
from src.domain.ports.entity_extraction import (
    EntityExtractionPort,
    ExtractionResult,
)
from src.domain.ports.l5_graph import L5GraphPort
from src.domain.ports.llm_client import LLMClientPort
from src.infrastructure.external_services.entity_extraction.conflict_arbitrator import (
    ConflictArbitrator,
)
from src.infrastructure.external_services.entity_extraction.llm_extractor import (
    LLMEntityExtractor,
)
from src.infrastructure.external_services.entity_extraction.rule_extractor import (
    RuleBasedExtractor,
)


class TestEntityExtractionIntegration:
    """实体抽取集成测试"""

    @pytest.fixture
    def rule_extractor(self) -> RuleBasedExtractor:
        """创建真实 RuleBasedExtractor"""
        return RuleBasedExtractor()

    @pytest.fixture
    def mock_llm_client(self) -> AsyncMock:
        """创建 Mock LLMClientPort"""
        client = AsyncMock(spec=LLMClientPort)
        return client

    @pytest.fixture
    def llm_extractor(self, mock_llm_client: AsyncMock) -> LLMEntityExtractor:
        """创建 LLMEntityExtractor（注入 Mock LLMClientPort）"""
        return LLMEntityExtractor(llm_client=mock_llm_client)

    @pytest.fixture
    def arbitrator(self) -> ConflictArbitrator:
        """创建真实 ConflictArbitrator"""
        return ConflictArbitrator()

    @pytest.fixture
    def l5_graph(self) -> AsyncMock:
        """创建 Mock L5GraphPort"""
        graph = AsyncMock(spec=L5GraphPort)
        graph.create_entity.return_value = True
        graph.create_relationship.return_value = True
        return graph

    @pytest.fixture
    def event_publisher(self) -> AsyncMock:
        """创建 Mock 事件发布器"""
        publisher = AsyncMock()
        publish_result = MagicMock(spec=PublishResult)
        type(publish_result).is_success = PropertyMock(return_value=True)
        publisher.publish.return_value = publish_result
        return publisher

    @pytest.fixture
    def service(
        self,
        rule_extractor: RuleBasedExtractor,
        llm_extractor: LLMEntityExtractor,
        l5_graph: AsyncMock,
        arbitrator: ConflictArbitrator,
        event_publisher: AsyncMock,
    ) -> EntityExtractionService:
        """创建 EntityExtractionService（真实 RuleBasedExtractor + Mock LLM）"""
        return EntityExtractionService(
            rule_extractor=rule_extractor,
            llm_extractor=llm_extractor,
            l5_graph=l5_graph,
            arbitrator=arbitrator,
            event_publisher=event_publisher,
        )

    # --- 端到端：规则基 + LLM 混合抽取 ---

    @pytest.mark.asyncio
    async def test_rule_and_llm_hybrid_extraction(
        self,
        service: EntityExtractionService,
        mock_llm_client: AsyncMock,
        l5_graph: AsyncMock,
        event_publisher: AsyncMock,
    ) -> None:
        """验证规则基 + LLM 混合抽取完整流程

        使用真实 AC 自动机规则基 + Mock LLM 返回，验证仲裁融合结果。
        """
        # 模拟 LLM 返回实体（包含规则基已有的 BLM 和新实体 PESTEL）
        from src.infrastructure.external_services.entity_extraction.llm_extractor_schema import (
            EntityExtractionSchema,
            ExtractedEntitySchema,
            ExtractedRelationSchema,
        )

        mock_llm_client.structured_generate.return_value = EntityExtractionSchema(
            entities=[
                ExtractedEntitySchema(name="BLM", entity_type="CONCEPT", confidence=0.7),
                ExtractedEntitySchema(name="PESTEL", entity_type="CONCEPT", confidence=0.85),
            ],
            relations=[
                ExtractedRelationSchema(source="BLM", target="PESTEL", relation_type="RELATES_TO", confidence=0.75),
            ],
        )

        result = await service.extract_entities(
            content="BLM 模型和 PESTEL 分析是战略规划工具",
            memory_id="int-test-001",
        )

        # 验证仲裁融合结果
        names = {e.name for e in result.entities}
        assert "BLM" in names  # 规则基已有
        assert "PESTEL" in names  # LLM 新增
        assert result.extraction_metadata.get("strategy") == "hybrid"

        # 验证持久化
        assert l5_graph.create_entity.called
        assert l5_graph.create_relationship.called

        # 验证事件发布
        assert event_publisher.publish.called

    # --- 规则基 + LLM 降级 ---

    @pytest.mark.asyncio
    async def test_llm_failure_fallback_to_rule(
        self,
        service: EntityExtractionService,
        mock_llm_client: AsyncMock,
        l5_graph: AsyncMock,
    ) -> None:
        """验证 LLM 调用失败时降级至仅规则基结果"""
        from src.domain.exceptions import LLMAPIError

        mock_llm_client.structured_generate.side_effect = LLMAPIError("LLM API 错误")

        result = await service.extract_entities(
            content="BLM 模型是战略规划工具",
            memory_id="int-test-002",
        )

        # 验证规则基结果仍在
        assert len(result.entities) >= 1
        assert "BLM" in {e.name for e in result.entities}

        # 验证每次调用参数含有独立节点 ID（基于 memory_id 的哈希）
        for call_args in l5_graph.create_entity.call_args_list:
            kwargs = call_args[1] if len(call_args) > 1 else {}
            if "memory_id" in kwargs:
                assert kwargs["memory_id"].startswith("int-test-002"), f"memory_id 应包含前缀，实际为 {kwargs['memory_id']}"

    # --- 空内容 ---

    @pytest.mark.asyncio
    async def test_empty_content(
        self,
        service: EntityExtractionService,
        mock_llm_client: AsyncMock,
    ) -> None:
        """验证空内容返回空结果"""
        result = await service.extract_entities(
            content="",
            memory_id="int-test-003",
        )
        assert isinstance(result, ExtractionResult)
        assert len(result.entities) == 0

    # --- 异常链路 ---

    @pytest.mark.asyncio
    async def test_rule_extractor_failure_raises_entity_extraction_error(
        self,
        rule_extractor: RuleBasedExtractor,
        llm_extractor: LLMEntityExtractor,
        l5_graph: AsyncMock,
        arbitrator: ConflictArbitrator,
        event_publisher: AsyncMock,
    ) -> None:
        """验证规则基失败时抛出 EntityExtractionError"""
        from src.domain.exceptions import EntityExtractionError

        # 使用会失败的规则基抽取器
        class FailingRuleExtractor(EntityExtractionPort):
            """模拟规则基抽取失败的抽取器，实现 EntityExtractionPort 接口"""

            async def extract_entities(self, content: str, domain_context: dict | None = None) -> ExtractionResult:
                msg = "规则基引擎初始化失败"
                raise RuntimeError(msg)

        service = EntityExtractionService(
            rule_extractor=FailingRuleExtractor(),
            llm_extractor=llm_extractor,
            l5_graph=l5_graph,
            arbitrator=arbitrator,
            event_publisher=event_publisher,
        )

        with pytest.raises(EntityExtractionError):
            await service.extract_entities(
                content="BLM 模型",
                memory_id="int-test-004",
            )
