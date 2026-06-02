"""值对象 ParsedDocument 系列单元测试

TDD 红阶段：验证解析结果值对象的构造、不可变性和 to_dict() 序列化。
"""

from __future__ import annotations

import pytest

from src.domain.value_objects.parsed_document import (
    BoundingBox,
    ParsedDocument,
    ParsedElement,
    ParsedPage,
    ParsedTable,
)


class TestBoundingBox:
    """BoundingBox 值对象测试"""

    def test_create_with_valid_values(self) -> None:
        bbox = BoundingBox(x=10.0, y=20.0, width=100.0, height=50.0, page=0)
        assert bbox.x == 10.0
        assert bbox.y == 20.0
        assert bbox.width == 100.0
        assert bbox.height == 50.0
        assert bbox.page == 0

    def test_frozen_immutable(self) -> None:
        bbox = BoundingBox(x=0.0, y=0.0, width=100.0, height=100.0, page=0)
        with pytest.raises(AttributeError):
            setattr(bbox, "x", 99.0)

    def test_to_dict(self) -> None:
        bbox = BoundingBox(x=1.0, y=2.0, width=3.0, height=4.0, page=0)
        d = bbox.to_dict()
        assert d == {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0, "page": 0}


class TestParsedElement:
    """ParsedElement 值对象测试"""

    def test_create_with_defaults(self) -> None:
        elem = ParsedElement(content="hello")
        assert elem.content == "hello"
        assert elem.bbox is None
        assert elem.confidence == 1.0

    def test_to_dict(self) -> None:
        elem = ParsedElement(content="文本内容", confidence=0.95)
        d = elem.to_dict()
        assert d == {"content": "文本内容", "bbox": None, "confidence": 0.95, "metadata": {}}

    def test_to_dict_with_bbox_serialized(self) -> None:
        bbox = BoundingBox(x=1.0, y=2.0, width=3.0, height=4.0, page=0)
        elem = ParsedElement(content="test", bbox=bbox)
        d = elem.to_dict()
        # bbox 应正确序列化为字典
        assert d["bbox"] == {"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0, "page": 0}


class TestParsedTable:
    """ParsedTable 值对象测试"""

    def test_create_with_defaults(self) -> None:
        table = ParsedTable()
        assert table.rows == []
        assert table.bbox is None
        assert table.confidence == 1.0

    def test_to_dict(self) -> None:
        table = ParsedTable(rows=[["A", "B"], ["1", "2"]])
        d = table.to_dict()
        assert d == {"rows": [["A", "B"], ["1", "2"]], "bbox": None, "confidence": 1.0}


class TestParsedPage:
    """ParsedPage 值对象测试"""

    def test_create_with_defaults(self) -> None:
        page = ParsedPage(page_number=1)
        assert page.page_number == 1
        assert page.texts == []
        assert page.tables == []
        assert page.images == []

    def test_to_dict(self) -> None:
        page = ParsedPage(
            page_number=1,
            texts=[ParsedElement(content="hello")],
            tables=[ParsedTable(rows=[["A"]])],
        )
        d = page.to_dict()
        assert d["page_number"] == 1
        assert len(d["texts"]) == 1
        assert d["texts"][0] == {"content": "hello", "bbox": None, "confidence": 1.0, "metadata": {}}
        assert len(d["tables"]) == 1
        assert d["tables"][0] == {"rows": [["A"]], "bbox": None, "confidence": 1.0}
        assert d["images"] == []


class TestParsedDocument:
    """ParsedDocument 顶层值对象测试"""

    def test_create_completed(self) -> None:
        doc = ParsedDocument(
            document_id="doc-123",
            mime_type="application/pdf",
            pages=[ParsedPage(page_number=1)],
            parse_timestamp="2026-05-31T00:00:00Z",
        )
        assert doc.document_id == "doc-123"
        assert doc.mime_type == "application/pdf"
        assert doc.parse_status == "completed"
        assert doc.error_message is None
        assert len(doc.pages) == 1

    def test_create_failed(self) -> None:
        doc = ParsedDocument(
            document_id="doc-456",
            mime_type="application/pdf",
            parse_status="failed",
            error_message="PDF is encrypted",
        )
        assert doc.parse_status == "failed"
        assert doc.error_message == "PDF is encrypted"

    def test_to_dict_completed(self) -> None:
        doc = ParsedDocument(
            document_id="doc-789",
            mime_type="text/plain",
            pages=[ParsedPage(page_number=1, texts=[ParsedElement(content="abc")])],
            parse_timestamp="2026-05-31T00:00:00Z",
        )
        d = doc.to_dict()
        assert d["document_id"] == "doc-789"
        assert d["mime_type"] == "text/plain"
        assert d["parse_status"] == "completed"
        assert d["error_message"] is None
        assert d["parse_timestamp"] == "2026-05-31T00:00:00Z"
        assert len(d["pages"]) == 1
        assert d["pages"][0]["page_number"] == 1

    def test_to_dict_failed(self) -> None:
        doc = ParsedDocument(
            document_id="doc-err",
            mime_type="application/pdf",
            parse_status="failed",
            error_message="Empty PDF",
        )
        d = doc.to_dict()
        assert d["parse_status"] == "failed"
        assert d["error_message"] == "Empty PDF"
        assert d["pages"] == []

    def test_frozen_immutable(self) -> None:
        doc = ParsedDocument(document_id="x", mime_type="text/plain")
        with pytest.raises(AttributeError):
            setattr(doc, "document_id", "y")

    def test_is_failed_returns_true_for_failed_status(self) -> None:
        doc = ParsedDocument(document_id="x", mime_type="text/plain", parse_status="failed", error_message="err")
        assert doc.is_failed() is True

    def test_is_failed_returns_false_for_completed_status(self) -> None:
        doc = ParsedDocument(document_id="x", mime_type="text/plain")
        assert doc.is_failed() is False

    def test_is_completed_returns_true_for_completed_status(self) -> None:
        doc = ParsedDocument(document_id="x", mime_type="text/plain")
        assert doc.is_completed() is True

    def test_is_completed_returns_false_for_failed_status(self) -> None:
        doc = ParsedDocument(document_id="x", mime_type="text/plain", parse_status="failed", error_message="err")
        assert doc.is_completed() is False
