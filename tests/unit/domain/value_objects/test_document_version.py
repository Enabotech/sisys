"""文档版本快照值对象单元测试

测试 DocumentVersionSnapshot 和 DocumentVersionDiff 值对象的：
- 构造与默认值
- frozen 不可变性
- to_dict() 序列化
- 边界值
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.domain.value_objects.document_version import (
    DocumentVersionDiff,
    DocumentVersionSnapshot,
)


class TestDocumentVersionSnapshotCreation:
    """测试 DocumentVersionSnapshot 值对象的构造"""

    def test_create_with_all_required_fields(self) -> None:
        """应该能使用所有必填字段创建快照"""
        document_id = uuid4()
        version = 1
        snapshot_id = uuid4()
        created_at = datetime.now(UTC)
        created_by = "user-1"

        snapshot = DocumentVersionSnapshot(
            document_id=document_id,
            version=version,
            snapshot_id=snapshot_id,
            created_at=created_at,
            created_by=created_by,
        )

        assert snapshot.document_id == document_id
        assert snapshot.version == version
        assert snapshot.snapshot_id == snapshot_id
        assert snapshot.created_at == created_at
        assert snapshot.created_by == created_by
        assert snapshot.change_description == ""
        assert snapshot.diff_summary == ""
        assert snapshot.diff_json is None
        assert snapshot.storage_object_key == ""
        assert snapshot.file_size_bytes == 0
        assert snapshot.checksum == ""

    def test_create_with_all_fields(self) -> None:
        """应该能使用所有字段创建快照"""
        snapshot = DocumentVersionSnapshot(
            document_id=uuid4(),
            version=2,
            snapshot_id=uuid4(),
            created_at=datetime.now(UTC),
            created_by="user-2",
            change_description="文档上传",
            diff_summary="initial version",
            diff_json={"changed_fields": [], "is_initial": True},
            storage_object_key="documents/abc.pdf",
            file_size_bytes=1024,
            checksum="abc123",
        )

        assert snapshot.change_description == "文档上传"
        assert snapshot.diff_summary == "initial version"
        assert snapshot.diff_json == {"changed_fields": [], "is_initial": True}
        assert snapshot.storage_object_key == "documents/abc.pdf"
        assert snapshot.file_size_bytes == 1024
        assert snapshot.checksum == "abc123"


class TestDocumentVersionSnapshotFrozen:
    """测试 DocumentVersionSnapshot 的不可变性"""

    def test_cannot_modify_after_creation(self) -> None:
        """创建后修改字段应抛出 AttributeError"""
        snapshot = DocumentVersionSnapshot(
            document_id=uuid4(),
            version=1,
            snapshot_id=uuid4(),
            created_at=datetime.now(UTC),
            created_by="user",
        )

        with pytest.raises(AttributeError):
            snapshot.diff_summary = "modified"  # type: ignore[misc]


class TestDocumentVersionSnapshotSerialization:
    """测试 DocumentVersionSnapshot 的序列化"""

    def test_to_dict_returns_all_fields(self) -> None:
        """to_dict() 应返回包含所有字段的字典"""
        snapshot_id = uuid4()
        document_id = uuid4()
        created_at = datetime.now(UTC)

        snapshot = DocumentVersionSnapshot(
            document_id=document_id,
            version=3,
            snapshot_id=snapshot_id,
            created_at=created_at,
            created_by="user-3",
            change_description="解析完成",
            diff_summary="metadata changed",
            diff_json={"changed_fields": ["parse_status"], "is_initial": False},
            storage_object_key="documents/def.pdf",
            file_size_bytes=2048,
            checksum="def456",
        )

        result = snapshot.to_dict()

        assert result["document_id"] == str(document_id)
        assert result["version"] == 3
        assert result["snapshot_id"] == str(snapshot_id)
        assert result["created_at"] == created_at.isoformat()
        assert result["created_by"] == "user-3"
        assert result["change_description"] == "解析完成"
        assert result["diff_summary"] == "metadata changed"
        assert result["diff_json"] == {"changed_fields": ["parse_status"], "is_initial": False}
        assert result["storage_object_key"] == "documents/def.pdf"
        assert result["file_size_bytes"] == 2048
        assert result["checksum"] == "def456"

    def test_to_dict_minimal(self) -> None:
        """最小必填字段的 to_dict() 应正确序列化"""
        snapshot = DocumentVersionSnapshot(
            document_id=uuid4(),
            version=1,
            snapshot_id=uuid4(),
            created_at=datetime.now(UTC),
            created_by="user",
        )

        result = snapshot.to_dict()

        assert isinstance(result["document_id"], str)
        assert isinstance(result["snapshot_id"], str)
        assert isinstance(result["created_at"], str)
        assert result["diff_json"] is None


class TestDocumentVersionDiffCreation:
    """测试 DocumentVersionDiff 值对象的构造"""

    def test_create_non_initial_diff(self) -> None:
        """创建非首次版本差异"""
        diff = DocumentVersionDiff(
            diff_summary="changed fields: filename, parse_status",
            changed_fields=["filename", "parse_status"],
        )

        assert diff.diff_summary == "changed fields: filename, parse_status"
        assert diff.changed_fields == ["filename", "parse_status"]
        assert diff.is_initial is False

    def test_create_initial_diff(self) -> None:
        """创建首次版本差异"""
        diff = DocumentVersionDiff(
            diff_summary="initial version",
            is_initial=True,
        )

        assert diff.diff_summary == "initial version"
        assert diff.changed_fields == []
        assert diff.is_initial is True

    def test_create_no_changes_diff(self) -> None:
        """创建无变更差异"""
        diff = DocumentVersionDiff(
            diff_summary="no changes",
        )

        assert diff.diff_summary == "no changes"
        assert diff.changed_fields == []
        assert diff.is_initial is False


class TestDocumentVersionDiffFrozen:
    """测试 DocumentVersionDiff 的不可变性"""

    def test_cannot_modify_after_creation(self) -> None:
        """创建后修改字段应抛出 AttributeError"""
        diff = DocumentVersionDiff(diff_summary="test")

        with pytest.raises(AttributeError):
            diff.diff_summary = "modified"  # type: ignore[misc]


class TestDocumentVersionSnapshotValidation:
    """测试 DocumentVersionSnapshot __post_init__ 校验"""

    def test_version_must_be_ge_1(self) -> None:
        """version < 1 时抛出 EntityValidationError"""
        from src.domain.exceptions import EntityValidationError

        with pytest.raises(EntityValidationError, match="version 必须 ≥ 1"):
            DocumentVersionSnapshot(
                document_id=uuid4(),
                version=0,
                snapshot_id=uuid4(),
                created_at=datetime.now(UTC),
                created_by="user",
            )

    def test_version_negative_raises(self) -> None:
        """version 负值时抛出 EntityValidationError"""
        from src.domain.exceptions import EntityValidationError

        with pytest.raises(EntityValidationError, match="version 必须 ≥ 1"):
            DocumentVersionSnapshot(
                document_id=uuid4(),
                version=-1,
                snapshot_id=uuid4(),
                created_at=datetime.now(UTC),
                created_by="user",
            )

    def test_file_size_bytes_negative_raises(self) -> None:
        """file_size_bytes < 0 时抛出 EntityValidationError"""
        from src.domain.exceptions import EntityValidationError

        with pytest.raises(EntityValidationError, match="file_size_bytes 必须 ≥ 0"):
            DocumentVersionSnapshot(
                document_id=uuid4(),
                version=1,
                snapshot_id=uuid4(),
                created_at=datetime.now(UTC),
                created_by="user",
                file_size_bytes=-1,
            )
