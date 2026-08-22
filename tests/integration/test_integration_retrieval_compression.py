"""检索-压缩循环集成测试

验证 PersistentNoteTaker → ContextCompressor → CompressionQualityEvaluator
完整链路（系统公理二：压缩前必须持久化）：
- 真实 RuleBasedExtractor（AC 自动机）+ Mock LLM（摘要生成）
- PersistentNoteTaker 提取实体、记录血缘、标记持久化
- ContextCompressor 验证 verify_persisted 后压缩
- CompressionQualityEvaluator 质量评估

遵循集成测试模式：真实服务优先（RuleBasedExtractor + DiscordQualityEvaluator），
Mock 仅限外部依赖（LLMClientPort 为纯外部调用）。
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.domain.exceptions import EntityValidationError
from src.domain.ports.entity_extraction import ExtractionResult
from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.llm_client import LLMResponse
from src.domain.services.compression_quality_evaluator import CompressionQualityEvaluator
from src.domain.services.context_compressor import CompressedContext, ContextCompressor
from src.domain.services.persistent_note_taker import PersistentNote, PersistentNoteTaker
from src.infrastructure.external_services.entity_extraction.rule_extractor import (
    RuleBasedExtractor,
)


def _make_search_result(
    doc_id: str = "doc-1",
    score: float = 0.9,
    content: str = "测试文档内容",
) -> SearchResult:
    """构造测试用 SearchResult"""
    return SearchResult(id=doc_id, score=score, payload={"content": content})


class TestRetrievalCompressionLoopIntegration:
    """检索-压缩循环端到端集成测试"""

    @pytest.fixture
    def entity_extractor(self) -> RuleBasedExtractor:
        """创建真实 RuleBasedExtractor（AC 自动机）"""
        return RuleBasedExtractor()

    @pytest.fixture
    def mock_llm(self) -> AsyncMock:
        """创建 Mock LLMClientPort（外部依赖 Mock）"""
        client = AsyncMock()

        async def mock_generate(
            prompt: str,
            config=None,
            system_prompt=None,
        ) -> LLMResponse:
            return LLMResponse(
                content="企业战略规划包括BLM模型六个阶段。业绩差距分析是关键第一步。市场洞察包含六子步骤。",
                model="test-model",
            )

        client.generate = mock_generate
        return client

    @pytest.fixture
    def auditor(self) -> AsyncMock:
        """创建 Mock 审计服务"""
        auditor = AsyncMock()
        return auditor

    @pytest.fixture
    def l1_cache(self) -> AsyncMock:
        """创建 Mock L1 缓存（L1CachePort）"""
        cache = AsyncMock()
        cache.set = AsyncMock(return_value=True)
        return cache

    async def test_full_loop(
        self,
        entity_extractor: RuleBasedExtractor,
        mock_llm: AsyncMock,
        auditor: AsyncMock,
        l1_cache: AsyncMock,
    ) -> None:
        """端到端：持久化笔记 → 压缩 → 质量评估"""
        # Step 1: PersistentNoteTaker 持久化笔记
        note_taker = PersistentNoteTaker(
            entity_extractor=entity_extractor,
            audit_service=auditor,
            l1_cache=l1_cache,
        )
        docs = [
            _make_search_result(
                doc_id="docs/001",
                content="BLM模型包含业绩差距分析、市场洞察、战略意图六个阶段。企业战略规划的核心方法论。",
            ),
            _make_search_result(
                doc_id="docs/002",
                content="BEM模型包含战略解码、目标分解和重点工作计划。",
            ),
        ]

        note = await note_taker.take_notes(
            query="企业战略规划方法论",
            retrieved_docs=docs,
            user_id="int-test-user",
            session_id="int-test-session",
        )

        # 验证持久化笔记
        assert isinstance(note, PersistentNote)
        assert note.persisted is True, "笔记必须标记为已持久化"
        assert note.persisted_at is not None
        assert note.lineage["query"] == "企业战略规划方法论"
        assert note.lineage["top_k"] == 2
        assert "BLM" in {e["name"] for e in note.entities}, "规则基应抽取 BLM 实体"

        # 验证审计血缘记录
        auditor.record.assert_called_once()

        # 验证 L1 缓存
        l1_cache.set.assert_called_once()
        assert l1_cache.set.call_args[1]["key"].startswith("note:")

        # Step 2: ContextCompressor 压缩
        compressor = ContextCompressor(
            llm_client=mock_llm,
            note_taker=note_taker,
            quality_evaluator=CompressionQualityEvaluator(),
            l1_cache=l1_cache,
        )
        compressed = await compressor.compress(
            retrieved_docs=docs,
            query="企业战略规划方法论",
            persistent_note=note,
        )

        # 验证压缩结果
        assert isinstance(compressed, CompressedContext)
        assert compressed.context, "压缩上下文不应为空"
        assert compressed.persistent_note_ref == str(note.note_id)
        assert compressed.query == "企业战略规划方法论"
        assert compressed.quality_score >= 0.0, "质量评分应为非负"
        assert compressed.original_token_count > 0

        # 验证质量评估器被执行
        assert 0.0 <= compressed.quality_score <= 1.0

    async def test_compression_requires_persisted_note(
        self,
        mock_llm: AsyncMock,
    ) -> None:
        """未持久化笔记触发 EntityValidationError（系统公理二）"""
        compressor = ContextCompressor(
            llm_client=mock_llm,
            note_taker=AsyncMock(),
        )

        # 未持久化的笔记
        note = PersistentNote(query="测试", persisted=False)
        docs = [_make_search_result(content="测试内容")]

        with pytest.raises(EntityValidationError):
            await compressor.compress(
                retrieved_docs=docs,
                query="测试",
                persistent_note=note,
            )

    async def test_entity_extraction_real_rule_based(
        self,
        entity_extractor: RuleBasedExtractor,
    ) -> None:
        """真实 RuleBasedExtractor 抽取战略领域实体"""
        result = await entity_extractor.extract_entities(
            content="BLM模型和BEM模型是华为战略规划的核心框架。NPV和IRR是财务评价指标。2024年营业收入增长15%。",
        )
        assert isinstance(result, ExtractionResult)
        names = {e.name for e in result.entities}
        assert "BLM" in names, "应抽取 BLM"
        assert "BEM" in names, "应抽取 BEM"
        assert "NPV" in names, "应抽取 NPV"
        assert "IRR" in names, "应抽取 IRR"
        assert "15%" in names, "正则应抽取百分数"

    async def test_quality_evaluator_low_repetition_high_score(
        self,
    ) -> None:
        """真实 CompressionQualityEvaluator：低冗余高信息熵文本评分高"""
        evaluator = CompressionQualityEvaluator()
        docs = [_make_search_result(content="测试文档")]
        text = (
            "企业战略规划包括BLM模型和BEM模型。"
            "业绩差距分析、市场洞察、战略意图构成六个阶段。"
            "2024年营业收入增长15%，净利润率达到12%。"
        )
        entities = [
            {"name": "BLM", "entity_type": "CONCEPT"},
            {"name": "BEM", "entity_type": "CONCEPT"},
            {"name": "战略规划", "entity_type": "CONCEPT"},
        ]
        score = await evaluator.evaluate(
            compressed_context=text,
            original_docs=docs,
            key_entities=entities,
        )
        assert score >= 0.7, f"高质量文本应≥0.7，实际{score}"

    async def test_compression_cache_written(
        self,
        entity_extractor: RuleBasedExtractor,
        mock_llm: AsyncMock,
        auditor: AsyncMock,
        l1_cache: AsyncMock,
    ) -> None:
        """压缩结果写入 L1 缓存（compressed: 前缀）"""
        note_taker = PersistentNoteTaker(
            entity_extractor=entity_extractor,
            audit_service=auditor,
        )
        docs = [_make_search_result(content="企业战略规划文档内容")]
        note = await note_taker.take_notes(
            query="战略规划",
            retrieved_docs=docs,
            user_id="int-user",
            session_id="int-session",
        )

        compressor = ContextCompressor(
            llm_client=mock_llm,
            note_taker=note_taker,
            l1_cache=l1_cache,
        )
        await compressor.compress(
            retrieved_docs=docs,
            query="战略规划",
            persistent_note=note,
        )

        # 验证 compressed 缓存写入
        compressed_calls = [c for c in l1_cache.set.call_args_list if str(c[1].get("key", "")).startswith("compressed:")]
        assert compressed_calls, "应写入 compressed: 前缀缓存"
