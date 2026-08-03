"""DocumentVersionSnapshotModel TDD tests — Red phase.

验证 ORM 模型字段、约束和创建行为。
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import DeclarativeBase

from src.infrastructure.storage.postgresql.models.document_version import (
    DocumentVersionSnapshotModel,
)


class TestDocumentVersionSnapshotModel:
    """DocumentVersionSnapshotModel tests (TDD red-green-refactor)."""

    def test_table_name(self) -> None:
        """表名应为 document_version_snapshots"""
        assert DocumentVersionSnapshotModel.__tablename__ == "document_version_snapshots"

    def test_has_id_column(self) -> None:
        """应有 id 列作为 UUID 主键"""
        columns = {c.name: c for c in DocumentVersionSnapshotModel.__table__.columns}
        assert "id" in columns
        assert columns["id"].primary_key

    def test_has_document_id_column(self) -> None:
        """应有 document_id 列，非空，外键"""
        columns = {c.name: c for c in DocumentVersionSnapshotModel.__table__.columns}
        assert "document_id" in columns
        assert not columns["document_id"].nullable

    def test_has_version_column(self) -> None:
        """应有 version 列，非空"""
        columns = {c.name: c for c in DocumentVersionSnapshotModel.__table__.columns}
        assert "version" in columns
        assert not columns["version"].nullable

    def test_has_snapshot_id_column(self) -> None:
        """应有 snapshot_id 列，非空"""
        columns = {c.name: c for c in DocumentVersionSnapshotModel.__table__.columns}
        assert "snapshot_id" in columns
        assert not columns["snapshot_id"].nullable

    def test_has_created_at_column(self) -> None:
        """应有 created_at 列，非空"""
        columns = {c.name: c for c in DocumentVersionSnapshotModel.__table__.columns}
        assert "created_at" in columns
        assert not columns["created_at"].nullable

    def test_has_created_by_column(self) -> None:
        """应有 created_by 列"""
        columns = {c.name: c for c in DocumentVersionSnapshotModel.__table__.columns}
        assert "created_by" in columns

    def test_has_change_description_column(self) -> None:
        """应有 change_description 列"""
        columns = {c.name: c for c in DocumentVersionSnapshotModel.__table__.columns}
        assert "change_description" in columns

    def test_has_diff_summary_column(self) -> None:
        """应有 diff_summary 列"""
        columns = {c.name: c for c in DocumentVersionSnapshotModel.__table__.columns}
        assert "diff_summary" in columns

    def test_has_diff_json_column(self) -> None:
        """应有 diff_json 列（可为空）"""
        columns = {c.name: c for c in DocumentVersionSnapshotModel.__table__.columns}
        assert "diff_json" in columns
        assert columns["diff_json"].nullable

    def test_has_storage_object_key_column(self) -> None:
        """应有 storage_object_key 列"""
        columns = {c.name: c for c in DocumentVersionSnapshotModel.__table__.columns}
        assert "storage_object_key" in columns

    def test_has_file_size_bytes_column(self) -> None:
        """应有 file_size_bytes 列"""
        columns = {c.name: c for c in DocumentVersionSnapshotModel.__table__.columns}
        assert "file_size_bytes" in columns

    def test_has_checksum_column(self) -> None:
        """应有 checksum 列"""
        columns = {c.name: c for c in DocumentVersionSnapshotModel.__table__.columns}
        assert "checksum" in columns

    def test_has_unique_constraint_on_document_version(self) -> None:
        """应有 (document_id, version) 唯一约束"""
        found = False
        for arg in DocumentVersionSnapshotModel.__table_args__:
            if hasattr(arg, "name") and "uq_document_version" in str(arg.name):
                found = True
                break
        assert found, "缺少 uq_document_version 唯一约束"

    def test_has_index_on_document_id(self) -> None:
        """应有 document_id 索引"""
        from typing import cast

        from sqlalchemy import Table

        table = cast(Table, DocumentVersionSnapshotModel.__table__)
        index_names = [idx.name for idx in table.indexes]
        assert "idx_doc_ver_snapshots_doc_id" in index_names

    def test_can_instantiate(self) -> None:
        """应能创建模型实例"""
        instance = DocumentVersionSnapshotModel(
            document_id=uuid4(),
            version=1,
            snapshot_id=uuid4(),
            created_by="test_user",
            diff_summary="initial version",
        )
        assert instance.document_id is not None
        assert instance.version == 1
        assert instance.created_by == "test_user"
        assert instance.diff_summary == "initial version"

    def test_inherits_from_declarative_base(self) -> None:
        """应继承自 DeclarativeBase"""
        assert issubclass(DocumentVersionSnapshotModel, DeclarativeBase) or hasattr(DocumentVersionSnapshotModel, "__mapper__")
