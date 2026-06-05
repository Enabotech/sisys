"""基础设施层文档仓储模块

继承 PostgreSQLAdapter[Document, DocumentModel]，实现实体与模型转换。
通过 DocumentQuery 值对象支持租户隔离和结构化过滤。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from src.domain.entities.document import Document, DocumentType, ParseStatus
from src.domain.ports.document_repository import DocumentQuery
from src.infrastructure.storage.postgresql.models.document import DocumentModel
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import PostgreSQLAdapter


class PostgreSQLDocumentRepository(PostgreSQLAdapter[Document, DocumentModel]):
    """文档仓储实现

    继承 PostgreSQLAdapter[Document, DocumentModel]，
    通过 _to_entity/_to_model 隔离领域层与 ORM 层。
    使用 DocumentQuery 值对象支持租户隔离和结构化过滤。
    """

    def __init__(self) -> None:
        super().__init__(DocumentModel)

    def _to_entity(self, model: DocumentModel) -> Document:
        """将 ORM 模型转换为领域实体"""
        return Document(
            document_id=model.id,
            filename=model.filename,
            document_type=DocumentType(model.document_type),
            file_size_bytes=model.file_size_bytes,
            mime_type=model.mime_type,
            parse_status=ParseStatus(model.parse_status),
            version=model.version,
            metadata=model.metadata_ or {},
            created_at=model.created_at or datetime.now(UTC),
            updated_at=model.updated_at or datetime.now(UTC),
            tenant_id=model.tenant_id,
            uploaded_by=model.uploaded_by,
        )

    def _to_model(self, entity: Document) -> DocumentModel:
        """将领域实体转换为 ORM 模型"""
        return DocumentModel(
            id=entity.document_id,
            tenant_id=entity.tenant_id,
            filename=entity.filename,
            mime_type=entity.mime_type,
            file_size_bytes=entity.file_size_bytes,
            document_type=entity.document_type.value,
            parse_status=entity.parse_status.value,
            uploaded_by=entity.uploaded_by,
            version=entity.version,
            metadata=entity.metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def delete(self, id: UUID) -> None:
        """覆写父类硬删除 — 文档删除尚未得到领域支持

        父类 PostgreSQLAdapter 继承的硬删除方法在端口层面不可见，
        但可被绕过端口契约直接调用，存在安全隐患。
        显式覆写为 NotImplementedError 消除此风险。

        未来有文档删除用例时：
        1. DocumentModel 添加 deleted_at 列
        2. 设置 self.soft_delete_column = "deleted_at"
        3. 在 DocumentRepositoryPort 中添加 delete 方法
        4. 删除此覆写

        Raises:
            NotImplementedError: 总是抛出
        """
        raise NotImplementedError("Document 删除尚未得到领域支持")

    async def find(self, query: DocumentQuery) -> Document | None:
        """按条件查询单个文档

        Args:
            query: 查询条件（必须包含 tenant_id + document_id）

        Returns:
            Document 实体或 None
        """
        stmt = select(DocumentModel).where(
            DocumentModel.tenant_id == query.tenant_id,
        )
        if query.document_id is not None:
            stmt = stmt.where(DocumentModel.id == query.document_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def list(self, query: DocumentQuery) -> list[Document]:
        """按条件列出文档"""
        stmt = select(DocumentModel).where(DocumentModel.tenant_id == query.tenant_id)

        if query.parse_status is not None:
            stmt = stmt.where(DocumentModel.parse_status == query.parse_status)
        if query.document_type is not None:
            stmt = stmt.where(DocumentModel.document_type == query.document_type)
        if query.uploaded_by is not None:
            stmt = stmt.where(DocumentModel.uploaded_by == query.uploaded_by)

        stmt = stmt.order_by(DocumentModel.created_at.desc()).offset(query.offset).limit(query.limit)

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]
