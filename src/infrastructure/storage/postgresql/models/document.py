"""基础设施层文档模型模块

定义文档的 SQLAlchemy ORM 模型，对应 documents 表
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class DocumentModel(Base):
    """文档 SQLAlchemy 模型，对应 documents 表

    Attributes:
        id: 主键 UUID
        tenant_id: 租户标识符（Row-Level Isolation）
        filename: 原始文件名
        mime_type: MIME 类型
        file_size_bytes: 文件大小（字节）
        document_type: 文档类型枚举值
        parse_status: 解析状态枚举值
        uploaded_by: 上传者用户标识符
        version: 版本号
        metadata: 文档元数据（JSONB）
        created_at: 创建时间
        updated_at: 最后更新时间
    """

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    parse_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    uploaded_by: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True, default=dict)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(
        self,
        id: UUID | None = None,
        tenant_id: str = "",
        filename: str = "",
        mime_type: str = "",
        file_size_bytes: int = 0,
        document_type: str = "other",
        parse_status: str = "pending",
        uploaded_by: str = "",
        version: int = 1,
        metadata: dict | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.tenant_id = tenant_id
        self.filename = filename
        self.mime_type = mime_type
        self.file_size_bytes = file_size_bytes
        self.document_type = document_type
        self.parse_status = parse_status
        self.uploaded_by = uploaded_by
        self.version = version
        self.metadata_ = metadata or {}
        self.created_at = created_at
        self.updated_at = updated_at
