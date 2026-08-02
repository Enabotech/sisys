"""语义分块值对象测试

测试 ChunkBoundaryType 枚举、ChunkingConfig 值对象、SemanticChunk 值对象
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid
from typing import Any

import pytest

from src.domain.value_objects.semantic_chunk import ChunkBoundaryType, ChunkingConfig, SemanticChunk


class TestChunkBoundaryType:
    """测试 ChunkBoundaryType 枚举"""

    def test_enum_values(self) -> None:
        """验证所有枚举值定义"""
        assert ChunkBoundaryType.PARAGRAPH.value == "paragraph"
        assert ChunkBoundaryType.SECTION_HEADER.value == "section_header"
        assert ChunkBoundaryType.TABLE.value == "table"
        assert ChunkBoundaryType.PAGE_BREAK.value == "page_break"
        assert ChunkBoundaryType.TOKEN_LIMIT.value == "token_limit"

    def test_enum_members_count(self) -> None:
        """验证枚举成员数量"""
        assert len(ChunkBoundaryType) == 5

    def test_enum_from_string(self) -> None:
        """验证从字符串构造枚举"""
        assert ChunkBoundaryType("paragraph") is ChunkBoundaryType.PARAGRAPH
        assert ChunkBoundaryType("section_header") is ChunkBoundaryType.SECTION_HEADER
        assert ChunkBoundaryType("table") is ChunkBoundaryType.TABLE
        assert ChunkBoundaryType("page_break") is ChunkBoundaryType.PAGE_BREAK
        assert ChunkBoundaryType("token_limit") is ChunkBoundaryType.TOKEN_LIMIT

    def test_is_str_enum(self) -> None:
        """验证是 str 枚举"""
        assert issubclass(ChunkBoundaryType, str)


class TestChunkingConfig:
    """测试 ChunkingConfig 值对象"""

    def test_default_values(self) -> None:
        """验证默认值"""
        config = ChunkingConfig()
        assert config.target_chunk_size_tokens == 300
        assert config.min_chunk_size_tokens == 50
        assert config.max_chunk_size_tokens == 8192

    def test_custom_values(self) -> None:
        """验证自定义值"""
        config = ChunkingConfig(
            target_chunk_size_tokens=500,
            min_chunk_size_tokens=100,
            max_chunk_size_tokens=4096,
        )
        assert config.target_chunk_size_tokens == 500
        assert config.min_chunk_size_tokens == 100
        assert config.max_chunk_size_tokens == 4096

    def test_frozen_immutable(self) -> None:
        """验证 frozen 不可变性"""
        config = ChunkingConfig()
        with pytest.raises(AttributeError):
            setattr(config, "target_chunk_size_tokens", 500)  # type: ignore[attr-defined]

    def test_is_dataclass(self) -> None:
        """验证是 dataclass"""
        assert dataclasses.is_dataclass(ChunkingConfig)
        assert ChunkingConfig.__dataclass_params__.frozen  # type: ignore[attr-defined]

    def test_to_dict(self) -> None:
        """验证 to_dict 序列化"""
        config = ChunkingConfig()
        d = config.to_dict()
        assert d == {
            "target_chunk_size_tokens": 300,
            "min_chunk_size_tokens": 50,
            "max_chunk_size_tokens": 8192,
        }


class TestSemanticChunk:
    """测试 SemanticChunk 值对象"""

    def test_create_with_all_fields(self) -> None:
        """验证全字段构造"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        content = "测试内容"
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        chunk = SemanticChunk(
            chunk_id=chunk_id,
            document_id=doc_id,
            content=content,
            chunk_index=0,
            boundary_type=ChunkBoundaryType.PARAGRAPH,
            token_count=10,
            page_start=1,
            page_end=1,
            content_hash=content_hash,
            metadata={"business_domain": "test"},
        )

        assert chunk.chunk_id == chunk_id
        assert chunk.document_id == doc_id
        assert chunk.content == content
        assert chunk.chunk_index == 0
        assert chunk.boundary_type == ChunkBoundaryType.PARAGRAPH
        assert chunk.token_count == 10
        assert chunk.page_start == 1
        assert chunk.page_end == 1
        assert chunk.content_hash == content_hash
        assert chunk.metadata == {"business_domain": "test"}

    def test_frozen_immutable(self) -> None:
        """验证 frozen 不可变性"""
        chunk = _make_chunk()
        with pytest.raises(AttributeError):
            setattr(chunk, "content", "新内容")  # type: ignore[attr-defined]

    def test_is_dataclass(self) -> None:
        """验证是 frozen dataclass"""
        assert dataclasses.is_dataclass(SemanticChunk)
        assert SemanticChunk.__dataclass_params__.frozen  # type: ignore[attr-defined]

    def test_to_dict(self) -> None:
        """验证 to_dict 序列化"""
        doc_id = uuid.uuid4()
        content = "测试内容"
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        chunk = SemanticChunk(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            content=content,
            chunk_index=0,
            boundary_type=ChunkBoundaryType.PARAGRAPH,
            token_count=4,
            page_start=1,
            page_end=1,
            content_hash=content_hash,
            metadata={"business_domain": "test"},
        )

        d = chunk.to_dict()
        assert isinstance(d["chunk_id"], str)
        assert isinstance(d["document_id"], str)
        assert d["content"] == content
        assert d["chunk_index"] == 0
        assert d["boundary_type"] == "paragraph"
        assert d["token_count"] == 4
        assert d["page_start"] == 1
        assert d["page_end"] == 1
        assert d["content_hash"] == content_hash
        assert d["metadata"] == {"business_domain": "test"}

    def test_to_dict_json_serializable(self) -> None:
        """验证 to_dict 输出可 JSON 序列化"""
        chunk = _make_chunk()
        d = chunk.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["content"] == chunk.content
        assert parsed["chunk_index"] == chunk.chunk_index
        assert parsed["boundary_type"] == chunk.boundary_type.value

    def test_chunk_index_increment(self) -> None:
        """验证 chunk_index 递增"""
        chunks = []
        for i in range(3):
            chunks.append(_make_chunk(chunk_index=i))
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_page_range_single_page(self) -> None:
        """验证单页页码范围"""
        chunk = _make_chunk(page_start=1, page_end=1)
        assert chunk.page_start == 1
        assert chunk.page_end == 1

    def test_page_range_multi_page(self) -> None:
        """验证多页页码范围"""
        chunk = _make_chunk(page_start=1, page_end=3)
        assert chunk.page_start == 1
        assert chunk.page_end == 3

    def test_content_hash_consistency(self) -> None:
        """验证相同内容哈希一致"""
        content = "相同内容"
        chunk1 = _make_chunk(content=content)
        chunk2 = _make_chunk(content=content)
        assert chunk1.content_hash == chunk2.content_hash

    def test_content_hash_change(self) -> None:
        """验证不同内容哈希不同"""
        chunk1 = _make_chunk(content="内容A")
        chunk2 = _make_chunk(content="内容B")
        assert chunk1.content_hash != chunk2.content_hash

    def test_content_hash_is_sha256(self) -> None:
        """验证 content_hash 是 SHA256 格式"""
        chunk = _make_chunk()
        expected_hash = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
        assert chunk.content_hash == expected_hash
        assert len(chunk.content_hash) == 64  # SHA256 hex length

    def test_metadata_dict(self) -> None:
        """验证 metadata 是字典"""
        chunk = _make_chunk(metadata={"business_domain": "test", "license": "MIT"})
        assert chunk.metadata["business_domain"] == "test"
        assert chunk.metadata["license"] == "MIT"

    def test_boundary_type_section_header(self) -> None:
        """验证 SECTION_HEADER 边界类型"""
        chunk = _make_chunk(boundary_type=ChunkBoundaryType.SECTION_HEADER)
        assert chunk.boundary_type == ChunkBoundaryType.SECTION_HEADER

    def test_boundary_type_table(self) -> None:
        """验证 TABLE 边界类型"""
        chunk = _make_chunk(boundary_type=ChunkBoundaryType.TABLE)
        assert chunk.boundary_type == ChunkBoundaryType.TABLE

    def test_boundary_type_page_break(self) -> None:
        """验证 PAGE_BREAK 边界类型"""
        chunk = _make_chunk(boundary_type=ChunkBoundaryType.PAGE_BREAK)
        assert chunk.boundary_type == ChunkBoundaryType.PAGE_BREAK

    def test_boundary_type_token_limit(self) -> None:
        """验证 TOKEN_LIMIT 边界类型"""
        chunk = _make_chunk(boundary_type=ChunkBoundaryType.TOKEN_LIMIT)
        assert chunk.boundary_type == ChunkBoundaryType.TOKEN_LIMIT


def _make_chunk(
    content: str = "测试内容",
    chunk_index: int = 0,
    boundary_type: ChunkBoundaryType = ChunkBoundaryType.PARAGRAPH,
    page_start: int = 1,
    page_end: int = 1,
    metadata: dict[str, Any] | None = None,
    token_count: int | None = None,
) -> SemanticChunk:
    """测试辅助：创建 SemanticChunk 实例"""
    doc_id = uuid.uuid4()
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if token_count is None:
        token_count = len(content)
    return SemanticChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        content=content,
        chunk_index=chunk_index,
        boundary_type=boundary_type,
        token_count=token_count,
        page_start=page_start,
        page_end=page_end,
        content_hash=content_hash,
        metadata=metadata or {},
    )