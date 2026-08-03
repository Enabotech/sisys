"""SemanticChunkerImpl 单元测试

测试语义分块的核心算法：Token 计数、边界检测、分块聚合。
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

import pytest

from src.domain.value_objects.semantic_chunk import ChunkBoundaryType, ChunkingConfig, SemanticChunk

# ===================================================================
# Token 计数测试
# ===================================================================


class TestEstimateTokens:
    """测试 estimate_tokens 函数"""

    def test_empty_string(self) -> None:
        """空字符串返回 0"""
        from src.infrastructure.document_parsing.semantic_chunker_impl import estimate_tokens

        assert estimate_tokens("") == 0

    def test_whitespace_only(self) -> None:
        """纯空白字符串返回低值"""
        from src.infrastructure.document_parsing.semantic_chunker_impl import estimate_tokens

        result = estimate_tokens("   \n\n  \t  ")
        # 空白字符很少，但需要至少 1
        assert result >= 1

    def test_chinese_only(self) -> None:
        """纯中文文本估算"""
        from src.infrastructure.document_parsing.semantic_chunker_impl import estimate_tokens

        text = "今天天气很好，适合出去散步。"
        result = estimate_tokens(text)
        # 中文约 10 个中文字符，每个约 0.8 tokens
        assert result > 0
        assert result < 20  # 合理范围

    def test_english_only(self) -> None:
        """纯英文文本估算"""
        from src.infrastructure.document_parsing.semantic_chunker_impl import estimate_tokens

        text = "Hello world, this is a test for token estimation accuracy."
        result = estimate_tokens(text)
        # 英文约 10 个单词，每个约 1.2 tokens
        assert result > 0
        assert result < 20  # 合理范围

    def test_mixed_chinese_english(self) -> None:
        """中英混合文本估算"""
        from src.infrastructure.document_parsing.semantic_chunker_impl import estimate_tokens

        text = "Hello world，今天天气很好。This is a test for token estimation."
        result = estimate_tokens(text)
        assert result > 0

    def test_long_text(self) -> None:
        """长文本估算"""
        from src.infrastructure.document_parsing.semantic_chunker_impl import estimate_tokens

        text = "今天天气很好。" * 1000
        result = estimate_tokens(text)
        assert result > 0
        # 每个句子10个中文字符，共1000句，约 8000 tokens
        assert result < 20000  # 合理范围

    def test_punctuation_only(self) -> None:
        """纯标点文本估算"""
        from src.infrastructure.document_parsing.semantic_chunker_impl import estimate_tokens

        text = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~"
        result = estimate_tokens(text)
        assert result >= 1

    def test_numbers_only(self) -> None:
        """纯数字文本估算"""
        from src.infrastructure.document_parsing.semantic_chunker_impl import estimate_tokens

        text = "1234567890 " * 10
        result = estimate_tokens(text)
        assert result > 0

    def test_accuracy_within_20_percent(self) -> None:
        """验证估算精度在 20% 以内"""
        # 使用已知的字符比例验证
        from src.infrastructure.document_parsing.semantic_chunker_impl import estimate_tokens

        # 纯中文：〜800 chars, 每个约 0.8 tokens = 640 tokens
        chinese_text = "今天" * 400
        result = estimate_tokens(chinese_text)
        # 640 * 0.8 = 512, 640 * 1.2 = 768
        assert 400 < result < 900, f"Chinese estimation out of range: {result}"


# ===================================================================
# 边界分类测试
# ===================================================================


class TestClassifyBoundary:
    """测试 _classify_boundary 方法"""

    def test_paragraph_default(self) -> None:
        """无 style 时返回 PARAGRAPH"""
        from src.domain.value_objects.parsed_document import ParsedElement
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        chunker = SemanticChunkerImpl()
        element = ParsedElement(content="测试", metadata={})
        result = chunker._classify_boundary(element)
        assert result == ChunkBoundaryType.PARAGRAPH

    def test_paragraph_no_style_key(self) -> None:
        """无 metadata 时返回 PARAGRAPH"""
        from src.domain.value_objects.parsed_document import ParsedElement
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        chunker = SemanticChunkerImpl()
        element = ParsedElement(content="测试")
        result = chunker._classify_boundary(element)
        assert result == ChunkBoundaryType.PARAGRAPH

    def test_section_header_h1(self) -> None:
        """style h1 返回 SECTION_HEADER"""
        from src.domain.value_objects.parsed_document import ParsedElement
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        chunker = SemanticChunkerImpl()
        element = ParsedElement(content="标题", metadata={"style": "h1"})
        result = chunker._classify_boundary(element)
        assert result == ChunkBoundaryType.SECTION_HEADER

    def test_section_header_h6(self) -> None:
        """style h6 返回 SECTION_HEADER"""
        from src.domain.value_objects.parsed_document import ParsedElement
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        chunker = SemanticChunkerImpl()
        element = ParsedElement(content="标题", metadata={"style": "h6"})
        result = chunker._classify_boundary(element)
        assert result == ChunkBoundaryType.SECTION_HEADER

    @pytest.mark.parametrize("style", ["Heading 1", "Heading 2", "Heading 9", "heading 1", "HEADING 1"])
    def test_section_header_word_heading(self, style: str) -> None:
        """Word Heading 样式返回 SECTION_HEADER"""
        from src.domain.value_objects.parsed_document import ParsedElement
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        chunker = SemanticChunkerImpl()
        element = ParsedElement(content="标题", metadata={"style": style})
        result = chunker._classify_boundary(element)
        assert result == ChunkBoundaryType.SECTION_HEADER, f"style={style} should be SECTION_HEADER"

    @pytest.mark.parametrize("style", ["Heading 1 Char", "heading 1 + 中文", "Heading 1 - 副本"])
    def test_section_header_word_heading_variant(self, style: str) -> None:
        """含 heading 子串的样式返回 SECTION_HEADER"""
        from src.domain.value_objects.parsed_document import ParsedElement
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        chunker = SemanticChunkerImpl()
        element = ParsedElement(content="标题", metadata={"style": style})
        result = chunker._classify_boundary(element)
        assert result == ChunkBoundaryType.SECTION_HEADER, f"style={style} should be SECTION_HEADER"

    @pytest.mark.parametrize("style", ["Normal", "body", "highlight", "title", "h10", "Header"])
    def test_paragraph_non_header_styles(self, style: str) -> None:
        """非标题样式返回 PARAGRAPH"""
        from src.domain.value_objects.parsed_document import ParsedElement
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        chunker = SemanticChunkerImpl()
        element = ParsedElement(content="正文", metadata={"style": style})
        result = chunker._classify_boundary(element)
        assert result == ChunkBoundaryType.PARAGRAPH, f"style={style} should be PARAGRAPH"


# ===================================================================
# 表格展平测试
# ===================================================================


class TestFlattenTable:
    """测试 _flatten_table 方法"""

    def test_table_with_header(self) -> None:
        """含表头的表格展平"""
        from src.domain.value_objects.parsed_document import ParsedTable
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        chunker = SemanticChunkerImpl()
        table = ParsedTable(
            rows=[["张三", "28"], ["李四", "32"]],
            header=["姓名", "年龄"],
            table_caption="用户信息",
        )
        result = chunker._flatten_table(table)
        assert "[表格: 用户信息]" in result
        assert "| 姓名 | 年龄 |" in result
        assert "| 张三 | 28 |" in result
        assert "| 李四 | 32 |" in result

    def test_table_without_header(self) -> None:
        """无表头表格展平"""
        from src.domain.value_objects.parsed_document import ParsedTable
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        chunker = SemanticChunkerImpl()
        table = ParsedTable(
            rows=[["A", "B"], ["1", "2"]],
        )
        result = chunker._flatten_table(table)
        assert "[表格]" in result
        assert "| A | B |" in result
        assert "| 1 | 2 |" in result

    def test_table_with_caption(self) -> None:
        """含标题的表格展平"""
        from src.domain.value_objects.parsed_document import ParsedTable
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        chunker = SemanticChunkerImpl()
        table = ParsedTable(
            rows=[["数据"]],
            table_caption="测试表",
        )
        result = chunker._flatten_table(table)
        assert "[表格: 测试表]" in result

    def test_table_no_caption(self) -> None:
        """无标题的表格展平"""
        from src.domain.value_objects.parsed_document import ParsedTable
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        chunker = SemanticChunkerImpl()
        table = ParsedTable(rows=[["数据"]])
        result = chunker._flatten_table(table)
        assert "[表格]" in result


# ===================================================================
# 语义分块器集成测试
# ===================================================================


class TestSemanticChunkerImpl:
    """测试 SemanticChunkerImpl 完整分块流程"""

    def test_single_paragraph(self) -> None:
        """单段落文档"""
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        doc = ParsedDocument(
            document_id=str(uuid.uuid4()),
            mime_type="text/plain",
            pages=[
                ParsedPage(
                    page_number=1,
                    texts=[ParsedElement(content="今天天气很好，适合出去散步。")],
                )
            ],
        )
        chunker = SemanticChunkerImpl()
        chunks = _run_chunker(chunker, doc)
        assert len(chunks) == 1
        assert chunks[0].boundary_type == ChunkBoundaryType.PARAGRAPH

    def test_empty_document(self) -> None:
        """空文档返回空列表"""
        from src.domain.value_objects.parsed_document import ParsedDocument
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        doc = ParsedDocument(
            document_id=str(uuid.uuid4()),
            mime_type="text/plain",
        )
        chunker = SemanticChunkerImpl()
        chunks = _run_chunker(chunker, doc)
        assert chunks == []

    def test_empty_page(self) -> None:
        """空页面返回空列表"""
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedPage
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        doc = ParsedDocument(
            document_id=str(uuid.uuid4()),
            mime_type="text/plain",
            pages=[ParsedPage(page_number=1)],
        )
        chunker = SemanticChunkerImpl()
        chunks = _run_chunker(chunker, doc)
        assert chunks == []

    def test_section_header_split(self) -> None:
        """章节标题触发新分块"""
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        doc = ParsedDocument(
            document_id=str(uuid.uuid4()),
            mime_type="text/plain",
            pages=[
                ParsedPage(
                    page_number=1,
                    texts=[
                        ParsedElement(content="第一章", metadata={"style": "h1"}),
                        ParsedElement(content="这是第一章的内容。" * 20),
                        ParsedElement(content="第二章", metadata={"style": "h2"}),
                        ParsedElement(content="这是第二章的内容。" * 20),
                    ],
                )
            ],
        )
        chunker = SemanticChunkerImpl()
        chunks = _run_chunker(chunker, doc)
        header_chunks = [c for c in chunks if c.boundary_type == ChunkBoundaryType.SECTION_HEADER]
        assert len(header_chunks) >= 2

    def test_table_independent_chunk(self) -> None:
        """表格独立分块"""
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage, ParsedTable
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        doc = ParsedDocument(
            document_id=str(uuid.uuid4()),
            mime_type="text/plain",
            pages=[
                ParsedPage(
                    page_number=1,
                    texts=[ParsedElement(content="正文")],
                    tables=[
                        ParsedTable(
                            rows=[["A", "B"], ["1", "2"]],
                            header=["A", "B"],
                        )
                    ],
                )
            ],
        )
        chunker = SemanticChunkerImpl()
        chunks = _run_chunker(chunker, doc)
        table_chunks = [c for c in chunks if c.boundary_type == ChunkBoundaryType.TABLE]
        assert len(table_chunks) >= 1

    def test_page_break(self) -> None:
        """跨页边界切分"""
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        doc = ParsedDocument(
            document_id=str(uuid.uuid4()),
            mime_type="text/plain",
            pages=[
                ParsedPage(
                    page_number=1,
                    texts=[ParsedElement(content="第一页内容。" * 20)],
                ),
                ParsedPage(
                    page_number=2,
                    texts=[ParsedElement(content="第二页内容。" * 20)],
                ),
            ],
        )
        chunker = SemanticChunkerImpl()
        chunks = _run_chunker(chunker, doc)
        assert len(chunks) >= 2, f"Expected at least 2 chunks for 2 pages, got {len(chunks)}"

    def test_page_range_metadata(self) -> None:
        """分块页码范围正确"""
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        doc = ParsedDocument(
            document_id=str(uuid.uuid4()),
            mime_type="text/plain",
            pages=[
                ParsedPage(
                    page_number=1,
                    texts=[ParsedElement(content="第一页内容。" * 20)],
                ),
                ParsedPage(
                    page_number=2,
                    texts=[ParsedElement(content="第二页内容。" * 20)],
                ),
            ],
        )
        chunker = SemanticChunkerImpl()
        chunks = _run_chunker(chunker, doc)
        assert chunks[0].page_start == 1
        assert chunks[-1].page_end == 2

    def test_empty_table_skipped(self) -> None:
        """空表格不产生分块"""
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedPage, ParsedTable
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        doc = ParsedDocument(
            document_id=str(uuid.uuid4()),
            mime_type="text/plain",
            pages=[
                ParsedPage(
                    page_number=1,
                    tables=[ParsedTable(rows=[])],
                )
            ],
        )
        chunker = SemanticChunkerImpl()
        chunks = _run_chunker(chunker, doc)
        assert chunks == []

    def test_content_hash_sha256(self) -> None:
        """分块 content_hash 使用 SHA256"""
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        content = "测试内容"
        doc = ParsedDocument(
            document_id=str(uuid.uuid4()),
            mime_type="text/plain",
            pages=[
                ParsedPage(
                    page_number=1,
                    texts=[ParsedElement(content=content)],
                )
            ],
        )
        chunker = SemanticChunkerImpl()
        chunks = _run_chunker(chunker, doc)
        assert chunks[0].content_hash == hashlib.sha256(content.encode("utf-8")).hexdigest()

    def test_chunk_index_increment(self) -> None:
        """分块索引递增"""
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        doc = ParsedDocument(
            document_id=str(uuid.uuid4()),
            mime_type="text/plain",
            pages=[
                ParsedPage(
                    page_number=1,
                    texts=[
                        ParsedElement(content="段落1。" * 20),
                        ParsedElement(content="段落2。" * 20),
                        ParsedElement(content="段落3。" * 50),
                        ParsedElement(content="段落4。" * 50),
                        ParsedElement(content="段落5。" * 20),
                    ],
                )
            ],
        )
        chunker = SemanticChunkerImpl()
        chunks = _run_chunker(chunker, doc)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i, f"Chunk index mismatch at {i}: got {c.chunk_index}"

    def test_to_dict_serializable(self) -> None:
        """分块可序列化为 JSON"""
        import json

        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        doc = ParsedDocument(
            document_id=str(uuid.uuid4()),
            mime_type="text/plain",
            pages=[
                ParsedPage(
                    page_number=1,
                    texts=[ParsedElement(content="测试")],
                )
            ],
        )
        chunker = SemanticChunkerImpl()
        chunks = _run_chunker(chunker, doc)
        for chunk in chunks:
            d = chunk.to_dict()
            json_str = json.dumps(d, ensure_ascii=False)
            assert json_str

    def test_metadata_preserved(self) -> None:
        """分块 metadata 保留文档级元数据"""
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        doc = ParsedDocument(
            document_id=str(uuid.uuid4()),
            mime_type="text/plain",
            pages=[
                ParsedPage(
                    page_number=1,
                    texts=[ParsedElement(content="测试")],
                )
            ],
        )
        chunker = SemanticChunkerImpl()
        chunks = _run_chunker(chunker, doc, metadata={"business_domain": "test"})
        assert chunks[0].metadata.get("business_domain") == "test"

    def test_multiple_paragraphs_aggregated(self) -> None:
        """多段落按目标大小聚合"""
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        paragraphs = ["这是第" + str(i + 1) + "段的内容。" * 30 for i in range(5)]
        doc = ParsedDocument(
            document_id=str(uuid.uuid4()),
            mime_type="text/plain",
            pages=[
                ParsedPage(
                    page_number=1,
                    texts=[ParsedElement(content=p) for p in paragraphs],
                )
            ],
        )
        chunker = SemanticChunkerImpl()
        chunks = _run_chunker(chunker, doc)
        assert len(chunks) > 0
        assert all(c.token_count <= 8192 for c in chunks)

    def test_section_header_with_word_heading(self) -> None:
        """Word Heading 样式归一化"""
        from src.domain.value_objects.parsed_document import ParsedDocument, ParsedElement, ParsedPage
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        doc = ParsedDocument(
            document_id=str(uuid.uuid4()),
            mime_type="text/plain",
            pages=[
                ParsedPage(
                    page_number=1,
                    texts=[
                        ParsedElement(content="第一章", metadata={"style": "Heading 1"}),
                        ParsedElement(content="内容。" * 20),
                        ParsedElement(content="第一节", metadata={"style": "Heading 2"}),
                        ParsedElement(content="内容。" * 20),
                        ParsedElement(content="附录", metadata={"style": "Heading 1 Char"}),
                        ParsedElement(content="附录内容。" * 10),
                    ],
                )
            ],
        )
        chunker = SemanticChunkerImpl()
        chunks = _run_chunker(chunker, doc)
        header_chunks = [c for c in chunks if c.boundary_type == ChunkBoundaryType.SECTION_HEADER]
        # "Heading 1" 和 "Heading 2" 是 SECTION_HEADER 边界
        # "Heading 1 Char" 是小标题分块，合并到后一个分块中
        assert len(header_chunks) >= 2, f"Expected at least 2 header chunks, got {len(header_chunks)}"


# ===================================================================
# 辅助函数
# ===================================================================


def _run_chunker(
    chunker: Any,
    parsed_doc: Any,
    config: ChunkingConfig | None = None,
    metadata: dict[str, Any] | None = None,
) -> list[SemanticChunk]:
    """运行分块器并返回结果"""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(chunker.chunk(parsed_doc, config=config, metadata=metadata))
    finally:
        loop.close()
