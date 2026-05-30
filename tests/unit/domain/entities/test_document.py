"""Tests for Document domain entity."""

import uuid

import pytest

from src.domain.entities.document import (
    Document,
    ParseStatus,
)


def _make_doc(**kwargs) -> Document:
    """Factory helper for Document."""
    defaults: dict = {
        "document_id": uuid.uuid4(),
        "filename": "test.pdf",
    }
    defaults.update(kwargs)
    return Document(**defaults)


class TestDocumentCreation:
    """Test Document entity creation."""

    def test_create_minimal_document(self):
        """Can create a document with minimal arguments."""
        doc = _make_doc()
        assert doc.document_id is not None
        assert doc.filename == "test.pdf"
        assert doc.version == 1
        assert doc.parse_status == ParseStatus.PENDING

    def test_document_has_version_history(self):
        """Document starts with empty version history."""
        doc = _make_doc()
        assert doc.version_history == []


class TestDocumentValidation:
    """Test Document invariant validation."""

    def test_valid_document_passes(self):
        """Correctly constructed document passes validation."""
        doc = _make_doc()
        assert doc.validate() is True

    def test_empty_filename_fails(self):
        """Document with empty filename fails validation."""
        doc = _make_doc(filename="")
        with pytest.raises(ValueError, match="filename must not be empty"):
            doc.validate()

    def test_negative_file_size_fails(self):
        """Document with negative file size fails validation."""
        doc = _make_doc(file_size_bytes=-1)
        with pytest.raises(ValueError, match="file_size_bytes must be non-negative"):
            doc.validate()

    def test_zero_version_fails(self):
        """Document with version < 1 fails validation."""
        doc = _make_doc()
        doc.version = 0
        with pytest.raises(ValueError, match="version must be >= 1"):
            doc.validate()

    def test_metadata_validation_passes(self):
        """Document with required metadata passes."""
        doc = _make_doc(metadata={"author": "test", "source": "upload"})
        assert doc.validate_metadata(["author", "source"]) is True

    def test_metadata_validation_fails(self):
        """Document missing required metadata fails."""
        doc = _make_doc(metadata={"author": "test"})
        with pytest.raises(ValueError, match="Missing required metadata"):
            doc.validate_metadata(["author", "source"])


class TestDocumentVersioning:
    """Test Document version management."""

    def test_bump_version_increments(self):
        """bump_version increments version and records history."""
        doc = _make_doc()
        old_version = doc.version
        new_version = doc.bump_version("Updated content", "user1")
        assert new_version == old_version + 1
        assert len(doc.version_history) == 1
        assert doc.version_history[0].version == old_version
        assert doc.version_history[0].change_description == "Updated content"
        assert doc.version_history[0].created_by == "user1"

    def test_version_recorded_in_history(self):
        """Each version bump records a DocumentVersion in history."""
        doc = _make_doc()
        doc.bump_version("v1->v2")
        doc.bump_version("v2->v3")
        assert len(doc.version_history) == 2
        assert doc.version_history[0].version == 1
        assert doc.version_history[1].version == 2


class TestDocumentEmbeddingValidation:
    """P1-03 Fix: Test Document embedding NaN/Inf validation."""

    def test_valid_embedding_passes(self):
        """Document with valid embedding passes validation."""
        doc = _make_doc(embedding=[0.1, 0.2, 0.3])
        assert doc.validate() is True

    def test_nan_embedding_fails(self):
        """Document with NaN in embedding fails validation."""
        doc = _make_doc(embedding=[0.1, float("nan"), 0.3])
        with pytest.raises(ValueError, match="contains NaN"):
            doc.validate()

    def test_inf_embedding_fails(self):
        """Document with Inf in embedding fails validation."""
        doc = _make_doc(embedding=[0.1, float("inf"), 0.3])
        with pytest.raises(ValueError, match="contains NaN"):
            doc.validate()

    def test_none_embedding_passes(self):
        """Document with None embedding passes validation."""
        doc = _make_doc(embedding=None)
        assert doc.validate() is True


class TestDocumentTenantFields:
    """Story 2-1: 验证 Document 实体的 tenant_id 和 uploaded_by 字段"""

    def test_tenant_id_default_empty_string(self):
        """tenant_id 默认为空字符串（向后兼容）"""
        doc = _make_doc()
        assert doc.tenant_id == ""

    def test_uploaded_by_default_empty_string(self):
        """uploaded_by 默认为空字符串（向后兼容）"""
        doc = _make_doc()
        assert doc.uploaded_by == ""

    def test_tenant_id_can_be_set(self):
        """tenant_id 可以在构造时设置"""
        doc = _make_doc(tenant_id="tenant-123")
        assert doc.tenant_id == "tenant-123"

    def test_uploaded_by_can_be_set(self):
        """uploaded_by 可以在构造时设置"""
        doc = _make_doc(uploaded_by="user-456")
        assert doc.uploaded_by == "user-456"

    def test_new_fields_do_not_break_validation(self):
        """新字段不影响 validate()"""
        doc = _make_doc(tenant_id="t1", uploaded_by="u1")
        assert doc.validate() is True

    def test_metadata_accepts_any_value_type(self):
        """metadata 字典值类型为 Any，支持复杂结构"""
        doc = _make_doc(metadata={"source": "upload", "size": 1024, "tags": ["a", "b"]})
        assert doc.metadata["size"] == 1024
        assert doc.metadata["tags"] == ["a", "b"]
