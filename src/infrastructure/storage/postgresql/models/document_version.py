"""PostgreSQL 文档版本快照模型

定义 DocumentVersionSnapshotModel，用于持久化版本快照数据。
"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class DocumentVersionSnapshotModel(Base):
    """文档版本快照 ORM 模型

    持久化文档版本快照数据，与 documents 表通过 document_id 外键关联。
    """

    __tablename__ = "document_version_snapshots"

    id: Mapped[UUID] = mapped_column(SA_UUID, primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(SA_UUID, ForeignKey("documents.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_id: Mapped[UUID] = mapped_column(SA_UUID, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    change_description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    diff_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    diff_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    storage_object_key: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_document_version"),
        Index("idx_doc_ver_snapshots_doc_id", "document_id"),
    )

    def __init__(
        self,
        id: UUID | None = None,
        document_id: UUID | None = None,
        version: int = 0,
        snapshot_id: UUID | None = None,
        created_at: datetime | None = None,
        created_by: str = "",
        change_description: str = "",
        diff_summary: str = "",
        diff_json: dict | None = None,
        storage_object_key: str = "",
        file_size_bytes: int = 0,
        checksum: str = "",
    ) -> None:
        """初始化文档版本快照模型"""
        self.id = id or uuid4()
        self.document_id = cast("UUID", document_id or uuid4())
        self.version = version
        self.snapshot_id = cast("UUID", snapshot_id or uuid4())
        self.created_at = cast("datetime", created_at or datetime.now())
        self.created_by = created_by
        self.change_description = change_description
        self.diff_summary = diff_summary
        self.diff_json = diff_json
        self.storage_object_key = storage_object_key
        self.file_size_bytes = file_size_bytes
        self.checksum = checksum
