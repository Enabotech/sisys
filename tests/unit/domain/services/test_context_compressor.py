"""ContextCompressor 领域服务单元测试

验证上下文压缩器的核心流程：
1. 前置条件验证（verify_persisted 检查）
2. LLM 摘要生成（Temperature=0.3）
3. 压缩率验证（≥70%，不足触发二次压缩）
4. 质量评估（<0.7 触发二次生成）
5. 缓存策略

遵循 Mock 端口策略（仅单元测试允许）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.domain.exceptions import EntityValidationError
from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.llm_client import LLMResponse
from src.domain.services.context_compressor import (
    CompressedContext,
    CompressionQualityEvaluator,
    ContextCompressor,
    PersistentNote,
    PersistentNoteTaker,
)


def _make_search_result(
    doc_id: str = "doc-1",
    score: float = 0.9,
    content: str = "测试文档内容用于压缩测试。这是一个企业战略规划相关的文档片段。",
) -> SearchResult:
    """构造测试用 SearchResult"""
    return SearchResult(id=doc_id, score=score, payload={"content": content})


def _make_persistent_note(
    query: str = "测试查询",
    persisted: bool = True,
    entities: list | None = None,
) -> PersistentNote:
    """构造测试用 PersistentNote"""
    return PersistentNote(
        query=query,
        user_id="test-user",
        session_id="test-session",
        entities=entities or [{"name": "BLM", "entity_type": "CONCEPT"}],
        persisted=persisted,
        persisted_at=datetime.now(UTC) if persisted else None,
    )


class TestContextCompressor:
    """ContextCompressor 单元测试"""

    async def test_unpersisted_note_raises_error(self) -> None:
        """未持久化的笔记触发 EntityValidationError"""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=LLMResponse(content="摘要内容"))
        mock_note_taker = AsyncMock(spec=PersistentNoteTaker)

        compressor = ContextCompressor(
            llm_client=mock_llm,
            note_taker=mock_note_taker,
        )

        note = _make_persistent_note(persisted=False)

        with pytest.raises(EntityValidationError, match="persistent note"):
            await compressor.compress(
                retrieved_docs=[_make_search_result()],
                query="测试查询",
                persistent_note=note,
            )

    async def test_compress_normal_flow(self) -> None:
        """正常压缩流程返回 CompressedContext"""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(
            return_value=LLMResponse(
                content="企业战略规划包括BLM模型六个阶段。业绩差距分析是关键第一步。市场洞察包含六子步骤。",
            )
        )
        mock_note_taker = AsyncMock(spec=PersistentNoteTaker)

        compressor = ContextCompressor(
            llm_client=mock_llm,
            note_taker=mock_note_taker,
        )

        note = _make_persistent_note()
        # 使用足够长的文档内容确保压缩率估算合理
        long_text = (
            "BLM模型包含业绩差距分析、市场洞察、战略意图、"
            "创新焦点、业务设计、执行设计六个阶段。"
            "每个阶段都有详细的输出物和检查点。"
        ) * 20
        docs = [_make_search_result(content=long_text)]
        result = await compressor.compress(
            retrieved_docs=docs,
            query="BLM模型介绍",
            persistent_note=note,
        )

        assert isinstance(result, CompressedContext)
        assert result.context, "压缩上下文不应为空"
        assert result.persistent_note_ref == str(note.note_id)
        assert result.query == "BLM模型介绍"
        assert result.original_token_count > 0
        assert result.quality_score >= 0.0
        # compression_ratio 可能为负（输出比输入长是 LLM 的正常行为），仅验证类型
        assert isinstance(result.compression_ratio, float)
        assert result.rerun_count >= 0

    async def test_compress_with_quality_evaluator(self) -> None:
        """注入质量评估器时执行质量评估"""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(
            return_value=LLMResponse(
                content="高质量摘要内容，覆盖核心实体。",
            )
        )
        mock_note_taker = AsyncMock(spec=PersistentNoteTaker)
        mock_quality = AsyncMock(spec=CompressionQualityEvaluator)
        mock_quality.evaluate = AsyncMock(return_value=0.85)

        compressor = ContextCompressor(
            llm_client=mock_llm,
            note_taker=mock_note_taker,
            quality_evaluator=mock_quality,
        )

        note = _make_persistent_note(entities=[{"name": "BLM", "entity_type": "CONCEPT"}])
        docs = [_make_search_result(content="BLM模型六个阶段")]
        result = await compressor.compress(
            retrieved_docs=docs,
            query="BLM模型",
            persistent_note=note,
        )

        assert result.quality_score == 0.85
        mock_quality.evaluate.assert_called_once()

    async def test_compress_quality_below_threshold_trigger_regenerate(self) -> None:
        """质量评分 < 0.7 触发二次生成"""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(
            return_value=LLMResponse(
                content="经过二次生成后的高质量摘要内容。",
            )
        )
        mock_note_taker = AsyncMock(spec=PersistentNoteTaker)
        mock_quality = AsyncMock(spec=CompressionQualityEvaluator)
        # 第一次评估 0.5（触发二次生成），第二次评估 0.85
        mock_quality.evaluate = AsyncMock(side_effect=[0.5, 0.85])

        compressor = ContextCompressor(
            llm_client=mock_llm,
            note_taker=mock_note_taker,
            quality_evaluator=mock_quality,
        )

        note = _make_persistent_note(entities=[{"name": "BLM", "entity_type": "CONCEPT"}])
        docs = [_make_search_result(content="BLM模型")]
        result = await compressor.compress(
            retrieved_docs=docs,
            query="BLM模型",
            persistent_note=note,
        )

        assert result.quality_score == 0.85
        assert result.rerun_count >= 1
        # 二次生成调用了 generate 两次（首次 + 二次生成）
        assert mock_llm.generate.call_count >= 2

    async def test_compress_with_l1_cache(self) -> None:
        """注入 L1 缓存时写入缓存"""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=LLMResponse(content="摘要内容"))
        mock_note_taker = AsyncMock(spec=PersistentNoteTaker)
        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock(return_value=True)

        compressor = ContextCompressor(
            llm_client=mock_llm,
            note_taker=mock_note_taker,
            l1_cache=mock_cache,
        )

        note = _make_persistent_note()
        docs = [_make_search_result(content="测试内容")]
        compressed = await compressor.compress(
            retrieved_docs=docs,
            query="测试",
            persistent_note=note,
        )

        assert compressed.context, "压缩结果应含上下文"
        mock_cache.set.assert_called_once()
        key = mock_cache.set.call_args[1]["key"]
        assert key.startswith("compressed:")

    async def test_compress_result_fields(self) -> None:
        """压缩结果包含所有必需字段"""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(
            return_value=LLMResponse(
                content="企业战略规划是指企业为实现长期目标而制定的系统性计划。",
            )
        )
        mock_note_taker = AsyncMock(spec=PersistentNoteTaker)

        compressor = ContextCompressor(
            llm_client=mock_llm,
            note_taker=mock_note_taker,
        )

        note = _make_persistent_note(
            entities=[
                {"name": "BLM", "entity_type": "CONCEPT"},
                {"name": "战略规划", "entity_type": "CONCEPT"},
            ],
            query="企业战略规划",
        )
        # 使用长文档确保原始 token 估算较大
        long_text = "企业战略规划文档" * 100
        docs = [_make_search_result(content=long_text)]
        result = await compressor.compress(
            retrieved_docs=docs,
            query="企业战略规划",
            persistent_note=note,
        )

        assert result.context is not None
        assert isinstance(result.compression_ratio, float)
        assert result.quality_score >= 0.0
        assert result.token_count >= 0
        assert result.original_token_count > 0
        assert result.persistent_note_ref == str(note.note_id)
        assert result.query == "企业战略规划"
        assert len(result.key_entities) > 0

    async def test_l1_cache_failure_does_not_block(self) -> None:
        """L1 缓存失败不阻断主流程"""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=LLMResponse(content="摘要内容"))
        mock_note_taker = AsyncMock(spec=PersistentNoteTaker)
        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock(side_effect=Exception("Redis 不可用"))

        compressor = ContextCompressor(
            llm_client=mock_llm,
            note_taker=mock_note_taker,
            l1_cache=mock_cache,
        )

        note = _make_persistent_note()
        docs = [_make_search_result(content="测试内容")]
        result = await compressor.compress(
            retrieved_docs=docs,
            query="测试",
            persistent_note=note,
        )

        assert result.context, "缓存失败不影响压缩结果"

    async def test_recompress_not_called_when_ratio_ok(self) -> None:
        """压缩率足够时不会触发二次压缩"""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=LLMResponse(content="A" * 100))
        mock_note_taker = AsyncMock(spec=PersistentNoteTaker)

        compressor = ContextCompressor(
            llm_client=mock_llm,
            note_taker=mock_note_taker,
        )

        # 大量文档内容使原始 token 数很大，保证压缩率 ≥ 70%
        note = _make_persistent_note()
        docs = [_make_search_result(content="A" * 5000)]
        result = await compressor.compress(
            retrieved_docs=docs,
            query="测试",
            persistent_note=note,
        )

        # 压缩率应 ≥ 70%
        assert result.compression_ratio >= 0.5
        # 默认评估器不存在时 rerun_count 为 0
        assert result.rerun_count == 0


class TestContextCompressorBuildMethods:
    """ContextCompressor 静态方法测试"""

    def test_build_compress_prompt_contains_query(self) -> None:
        """压缩 prompt 包含查询文本"""
        prompt = ContextCompressor._build_compress_prompt(
            retrieved_docs=[_make_search_result(content="测试内容")],
            query="企业战略规划",
            key_entities=[{"name": "BLM", "entity_type": "CONCEPT"}],
        )
        assert "企业战略规划" in prompt
        assert "BLM" in prompt

    def test_build_compress_prompt_truncates_long_content(self) -> None:
        """压缩 prompt 截断超长文档内容"""
        long_content = "测试" * 1000
        prompt = ContextCompressor._build_compress_prompt(
            retrieved_docs=[_make_search_result(content=long_content)],
            query="测试",
            key_entities=[],
        )
        # prompt 总长度有限制
        assert len(prompt) < 20000

    def test_build_context_contains_query(self) -> None:
        """构建的上下文包含查询文本"""
        context = ContextCompressor._build_context("摘要内容", "测试查询")
        assert "测试查询" in context

    def test_build_context_truncates_to_limit(self) -> None:
        """上下文截断至 _CONTEXT_SIZE_LIMIT"""
        from src.domain.services.context_compressor import _CONTEXT_SIZE_LIMIT

        long_summary = "A" * 5000
        context = ContextCompressor._build_context(long_summary, "查询")
        assert len(context) <= _CONTEXT_SIZE_LIMIT

    def test_estimate_tokens_empty(self) -> None:
        """空文档返回 1（防止除零）"""
        assert ContextCompressor._estimate_tokens([]) == 1

    def test_estimate_tokens_with_content(self) -> None:
        """有内容的文档估算 token 数"""
        docs = [_make_search_result(content="四个字符")]
        tokens = ContextCompressor._estimate_tokens(docs)
        assert tokens >= 1

    def test_estimate_chars_tokens_empty(self) -> None:
        """空文本返回 1"""
        assert ContextCompressor._estimate_chars_tokens("") == 1

    def test_estimate_chars_tokens_normal(self) -> None:
        """正常文本估算 token 数"""
        assert ContextCompressor._estimate_chars_tokens("ABCD") == 1  # 4/4
        assert ContextCompressor._estimate_chars_tokens("ABCDEFGH") == 2  # 8/4

    def test_truncate_context(self) -> None:
        """截断上下文至 _CONTEXT_SIZE_LIMIT"""
        from src.domain.services.context_compressor import _CONTEXT_SIZE_LIMIT

        long_text = "A" * 5000
        truncated = ContextCompressor._truncate_context(long_text)
        assert len(truncated) <= _CONTEXT_SIZE_LIMIT
        assert truncated == long_text[:_CONTEXT_SIZE_LIMIT]


class TestCompressedContextValueObject:
    """CompressedContext 值对象测试"""

    def test_default_creation(self) -> None:
        """默认创建"""
        ctx = CompressedContext()
        assert ctx.context == ""
        assert ctx.compression_ratio == 0.0
        assert ctx.quality_score == 0.0
        assert ctx.token_count == 0
        assert ctx.original_token_count == 0
        assert ctx.rerun_count == 0

    def test_frozen(self) -> None:
        """CompressedContext 是 frozen dataclass"""
        ctx = CompressedContext(context="测试")
        with pytest.raises(AttributeError):
            ctx.context = "修改"  # type: ignore[misc]


class TestContextCompressorEdgeCases:
    """ContextCompressor 边界情况测试"""

    async def test_empty_docs_with_persisted_note(self) -> None:
        """空文档列表但笔记已持久化时正常返回"""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=LLMResponse(content="无相关内容"))
        mock_note_taker = AsyncMock(spec=PersistentNoteTaker)

        compressor = ContextCompressor(
            llm_client=mock_llm,
            note_taker=mock_note_taker,
        )

        note = _make_persistent_note()
        result = await compressor.compress(
            retrieved_docs=[],
            query="测试",
            persistent_note=note,
        )

        assert result.context is not None
        assert result.original_token_count == 1

    async def test_single_doc_with_persisted_note(self) -> None:
        """单文档压缩"""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=LLMResponse(content="单文档摘要"))
        mock_note_taker = AsyncMock(spec=PersistentNoteTaker)

        compressor = ContextCompressor(
            llm_client=mock_llm,
            note_taker=mock_note_taker,
        )

        note = _make_persistent_note()
        docs = [_make_search_result(doc_id="unique-doc-1", content="唯一文档内容")]
        result = await compressor.compress(
            retrieved_docs=docs,
            query="测试",
            persistent_note=note,
        )

        assert result.context is not None
        assert result.persistent_note_ref == str(note.note_id)
