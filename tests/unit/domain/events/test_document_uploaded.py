"""Tests for DocumentUploaded domain event"""

import uuid

import pytest

from src.domain.events.base import DomainEvent
from src.domain.events.document_events import DocumentUploaded


class TestDocumentUploadedCreation:
    """验证 DocumentUploaded 事件构造"""

    def test_create_with_all_fields(self) -> None:
        doc_id = uuid.uuid4()
        event = DocumentUploaded(
            document_id=doc_id,
            filename="report.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            tenant_id="tenant-123",
            uploaded_by="user-456",
        )
        assert event.document_id == doc_id
        assert event.filename == "report.pdf"
        assert event.mime_type == "application/pdf"
        assert event.file_size_bytes == 1024
        assert event.tenant_id == "tenant-123"
        assert event.uploaded_by == "user-456"

    def test_create_with_defaults(self) -> None:
        event = DocumentUploaded()
        assert event.document_id is not None
        assert event.filename == ""
        assert event.mime_type == ""
        assert event.file_size_bytes == 0
        assert event.tenant_id == ""
        assert event.uploaded_by == ""

    def test_event_type_is_fixed(self) -> None:
        event = DocumentUploaded()
        assert event.event_type == "DocumentUploaded"

    def test_frozen_immutability(self) -> None:
        event = DocumentUploaded(filename="test.pdf")
        with pytest.raises(AttributeError):
            setattr(event, "filename", "changed.pdf")


class TestDocumentUploadedRegistration:
    """验证事件自动注册"""

    def test_registered_in_domain_event_registry(self) -> None:
        assert "DocumentUploaded" in DomainEvent._registry

    def test_registry_maps_to_correct_class(self) -> None:
        assert DomainEvent._registry["DocumentUploaded"] is DocumentUploaded


class TestDocumentUploadedPostInit:
    """验证 __post_init__ 设置 aggregate_id 和 aggregate_type"""

    def test_aggregate_id_set_to_document_id(self) -> None:
        doc_id = uuid.uuid4()
        event = DocumentUploaded(document_id=doc_id)
        assert event.aggregate_id == doc_id

    def test_aggregate_type_set_to_document(self) -> None:
        event = DocumentUploaded()
        assert event.aggregate_type == "Document"


class TestDocumentUploadedSerialization:
    """验证序列化/反序列化"""

    def test_to_dict_contains_custom_fields_in_payload(self) -> None:
        event = DocumentUploaded(
            document_id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            filename="test.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            tenant_id="t1",
            uploaded_by="u1",
        )
        d = event.to_dict()
        assert d["event_type"] == "DocumentUploaded"
        # 子类字段应在 payload 中
        payload = d.get("payload", {})
        assert payload.get("filename") == "test.pdf"
        assert payload.get("tenant_id") == "t1"
        assert payload.get("uploaded_by") == "u1"

    def test_from_dict_roundtrip(self) -> None:
        doc_id = uuid.uuid4()
        original = DocumentUploaded(
            document_id=doc_id,
            filename="test.pdf",
            mime_type="application/pdf",
            file_size_bytes=2048,
            tenant_id="t1",
            uploaded_by="u1",
        )
        d = original.to_dict()
        restored = DomainEvent.from_dict(d)
        assert isinstance(restored, DocumentUploaded)
        assert str(restored.document_id) == str(doc_id)
        assert restored.filename == "test.pdf"
        assert restored.file_size_bytes == 2048
        assert restored.tenant_id == "t1"
        assert restored.uploaded_by == "u1"
