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
