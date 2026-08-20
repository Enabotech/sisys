"""Story 3.8 高保真溯源 Citation 值对象单元测试

验证 Citation 值对象的构造、序列化、反序列化和不可变性。
BoundingBox 复用 parsed_document.py 中已有定义。
"""

from __future__ import annotations

import uuid

import pytest

from src.domain.value_objects.citation import Citation
from src.domain.value_objects.parsed_document import BoundingBox

_TEST_DOCUMENT_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


def _make_bbox() -> BoundingBox:
    """构造测试用 BoundingBox"""
    return BoundingBox(x=100.5, y=200.3, width=400.0, height=50.0, page=3)


def _make_citation(bbox: BoundingBox | None = None, confidence: float = 0.92) -> Citation:
    """构造测试用 Citation"""
    return Citation(
        citation_id="chunk-001-cit",
        document_id=_TEST_DOCUMENT_ID,
        chunk_id="chunk-001",
        text="公司2024年营收同比增长15%，净利润率达到12%。",
        start_offset=0,
        end_offset=20,
        page_number=3,
        bbox=bbox,
        confidence=confidence,
    )


class TestCitationConstruction:
    """Citation 值对象构造测试"""

    def test_construct_with_all_fields(self) -> None:
        """构造包含所有字段的 Citation"""
        citation = _make_citation(bbox=_make_bbox())
        assert citation.citation_id == "chunk-001-cit"
        assert citation.chunk_id == "chunk-001"
        assert citation.document_id == _TEST_DOCUMENT_ID
        assert citation.start_offset == 0
        assert citation.end_offset == 20
        assert citation.page_number == 3
        assert citation.confidence == 0.92
        assert citation.bbox is not None

    def test_construct_with_integer_offset(self) -> None:
        """offset 字段为整数且 start < end"""
        citation = _make_citation()
        assert isinstance(citation.start_offset, int)
        assert isinstance(citation.end_offset, int)
        assert citation.start_offset < citation.end_offset

    def test_construct_without_bbox(self) -> None:
        """不传 bbox 时默认为 None"""
        citation = _make_citation(bbox=None)
        assert citation.bbox is None

    def test_confidence_within_bounds(self) -> None:
        """置信度在 0-1 范围内"""
        citation = _make_citation(confidence=0.99)
        assert 0.0 <= citation.confidence <= 1.0

    def test_frozen_immutable(self) -> None:
        """Citation 是不可变值对象（frozen dataclass）"""
        citation = _make_citation()
        with pytest.raises(AttributeError):
            # 用 setattr 验证运行时不可变性：mypy 将 frozen dataclass 属性视为
            # 只读（静态检查），直接赋值会触发静态错误，改用反射式赋值验证运行时行为
            setattr(citation, "citation_id", "changed")


class TestCitationSerialization:
    """Citation 序列化/反序列化测试"""

    def test_to_dict_with_bbox(self) -> None:
        """to_dict() 序列化含全部字段（含 bbox）"""
        citation = _make_citation(bbox=_make_bbox())
        data = citation.to_dict()
        assert data["citation_id"] == "chunk-001-cit"
        assert data["document_id"] == str(_TEST_DOCUMENT_ID)
        assert data["chunk_id"] == "chunk-001"
        assert data["text"].startswith("公司2024年")
        assert data["start_offset"] == 0
        assert data["end_offset"] == 20
        assert data["page_number"] == 3
        assert data["confidence"] == 0.92
        assert data["bbox"] is not None
        assert data["bbox"]["x"] == 100.5
        assert data["bbox"]["width"] == 400.0
        assert data["bbox"]["page"] == 3

    def test_to_dict_without_bbox(self) -> None:
        """无 bbox 时 to_dict() 的 bbox 为 None"""
        citation = _make_citation(bbox=None)
        data = citation.to_dict()
        assert data["bbox"] is None

    def test_from_dict_with_bbox(self) -> None:
        """from_dict() 反序列化含 bbox 的 dict"""
        citation = _make_citation(bbox=_make_bbox())
        data = citation.to_dict()
        restored = Citation.from_dict(data)
        assert isinstance(restored, Citation)
        assert restored.citation_id == citation.citation_id
        assert restored.chunk_id == citation.chunk_id
        assert restored.document_id == _TEST_DOCUMENT_ID
        assert restored.text == citation.text
        assert restored.confidence == citation.confidence
        assert restored.bbox is not None
        assert restored.bbox.x == 100.5
        assert restored.bbox.page == 3

    def test_from_dict_without_bbox(self) -> None:
        """from_dict() 反序列化无 bbox 的 dict"""
        citation = _make_citation(bbox=None)
        data = citation.to_dict()
        restored = Citation.from_dict(data)
        assert restored.bbox is None

    def test_round_trip_preserves_equality(self) -> None:
        """to_dict → from_dict 往返后字段保持不变"""
        citation = _make_citation(bbox=_make_bbox())
        restored = Citation.from_dict(citation.to_dict())
        assert restored == citation

    def test_from_dict_with_confidence_default(self) -> None:
        """from_dict() 缺省 confidence 时使用默认值 1.0"""
        data = _make_citation(bbox=None).to_dict()
        del data["confidence"]
        restored = Citation.from_dict(data)
        assert restored.confidence == 1.0


class TestCitationBoundingBoxReuse:
    """Citation 复用已有 BoundingBox 验证"""

    def test_bbox_is_parsed_document_bounding_box(self) -> None:
        """bbox 字段类型为 parsed_document.BoundingBox（复用，不重复定义）"""
        from src.domain.value_objects.parsed_document import BoundingBox as ParsedBoundingBox

        citation = _make_citation(bbox=_make_bbox())
        assert isinstance(citation.bbox, ParsedBoundingBox)

    def test_no_bbox_duplicate_definition(self) -> None:
        """citation.py 不重复定义 BoundingBox"""
        import inspect

        import src.domain.value_objects.citation as citation_module

        source = inspect.getsource(citation_module)
        assert "class BoundingBox" not in source
