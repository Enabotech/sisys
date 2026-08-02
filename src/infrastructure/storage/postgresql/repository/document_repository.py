"""基础设施层文档仓储模块

继承 PostgreSQLAdapter[Document, DocumentModel]，实现实体与模型转换。
通过 DocumentQuery 值对象支持租户隔离和结构化过滤。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import List, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from src.domain.entities.document import Document, DocumentType, ParseStatus
from src.domain.exceptions import DocumentVersionConflictError
from src.domain.ports.document_repository import DocumentQuery
from src.domain.value_objects.document_version import DocumentVersionSnapshot
from src.infrastructure.storage.postgresql.models.document import DocumentModel
from src.infrastructure.storage.postgresql.models.document_version import (
    DocumentVersionSnapshotModel,
)
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

    async def list(self, query: DocumentQuery) -> List[Document]:
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

    # ------------------------------------------------------------------
    # 版本快照相关方法
    # ------------------------------------------------------------------

    async def save_version_snapshot(self, snapshot: DocumentVersionSnapshot) -> DocumentVersionSnapshot:
        """持久化版本快照

        Args:
            snapshot: 版本快照值对象

        Returns:
            持久化后的版本快照
        """
        model = DocumentVersionSnapshotModel(
            document_id=snapshot.document_id,
            version=snapshot.version,
            snapshot_id=snapshot.snapshot_id,
            created_at=snapshot.created_at,
            created_by=snapshot.created_by,
            change_description=snapshot.change_description,
            diff_summary=snapshot.diff_summary,
            diff_json=snapshot.diff_json,
            storage_object_key=snapshot.storage_object_key,
            file_size_bytes=snapshot.file_size_bytes,
            checksum=snapshot.checksum,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            raise DocumentVersionConflictError(
                document_id=snapshot.document_id,
                expected_version=snapshot.version - 1,
                actual_version=snapshot.version,
            )
        return snapshot

    async def list_versions(self, document_id: UUID, tenant_id: str) -> List[DocumentVersionSnapshot]:
        """按文档 ID 和租户列出版本历史

        Args:
            document_id: 文档唯一标识符
            tenant_id: 租户标识符

        Returns:
            版本快照列表（按版本号降序排列）
        """
        # 先验证文档属于该租户
        doc_stmt = select(DocumentModel).where(
            DocumentModel.id == document_id,
            DocumentModel.tenant_id == tenant_id,
        )
        doc_result = await self._session.execute(doc_stmt)
        if doc_result.scalar_one_or_none() is None:
            return []

        stmt = (
            select(DocumentVersionSnapshotModel)
            .where(DocumentVersionSnapshotModel.document_id == document_id)
            .order_by(DocumentVersionSnapshotModel.version.desc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_version_snapshot(m) for m in models]

    async def get_version(self, document_id: UUID, version: int, tenant_id: str) -> DocumentVersionSnapshot | None:
        """获取指定版本快照

        Args:
            document_id: 文档唯一标识符
            version: 版本号
            tenant_id: 租户标识符

        Returns:
            版本快照或 None
        """
        # 先验证文档属于该租户
        doc_stmt = select(DocumentModel).where(
            DocumentModel.id == document_id,
            DocumentModel.tenant_id == tenant_id,
        )
        doc_result = await self._session.execute(doc_stmt)
        if doc_result.scalar_one_or_none() is None:
            return None

        stmt = select(DocumentVersionSnapshotModel).where(
            DocumentVersionSnapshotModel.document_id == document_id,
            DocumentVersionSnapshotModel.version == version,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_version_snapshot(model)

    async def save_with_version_check(self, document: Document, expected_version: int) -> Document:
        """带乐观锁版本检查的保存方法

        当 document.version == expected_version + 1 时执行保存，
        否则抛出 DocumentVersionConflictError。

        使用原子 UPDATE ... WHERE version = :expected 避免 TOCTOU 竞态条件。

        Args:
            document: 待保存的文档实体
            expected_version: 期望的当前版本号

        Returns:
            保存后的文档实体

        Raises:
            DocumentVersionConflictError: 版本不匹配时抛出
            NotFoundError: 文档不存在时抛出
        """
        # 原子 UPDATE 实现乐观锁，避免 TOCTOU 竞态条件
        stmt = (
            update(DocumentModel)
            .where(
                DocumentModel.id == document.document_id,
                DocumentModel.tenant_id == document.tenant_id,
                DocumentModel.version == expected_version,
            )
            .values(
                version=document.version,
                updated_at=datetime.now(UTC),
            )
        )
        result = await self._session.execute(stmt)
        from sqlalchemy.engine import CursorResult

        cursor_result = cast(CursorResult, result)

        if cursor_result.rowcount == 0:
            # rowcount == 0：文档不存在或版本不匹配
            check_stmt = select(DocumentModel).where(
                DocumentModel.id == document.document_id,
                DocumentModel.tenant_id == document.tenant_id,
            )
            check_result = await self._session.execute(check_stmt)
            model = check_result.scalar_one_or_none()

            if model is None:
                from src.domain.exceptions import NotFoundError

                raise NotFoundError(f"Document not found: {document.document_id}, tenant: {document.tenant_id}")

            raise DocumentVersionConflictError(
                document_id=document.document_id,
                expected_version=expected_version,
                actual_version=model.version,
            )

        # 读取更新后的数据
        reload_stmt = select(DocumentModel).where(
            DocumentModel.id == document.document_id,
        )
        reload_result = await self._session.execute(reload_stmt)
        model = reload_result.scalar_one()
        return self._to_entity(model)

    @staticmethod
    def _to_version_snapshot(model: DocumentVersionSnapshotModel) -> DocumentVersionSnapshot:
        """将 ORM 模型转换为版本快照值对象

        Args:
            model: ORM 模型实例

        Returns:
            版本快照值对象
        """
        return DocumentVersionSnapshot(
            document_id=model.document_id,
            version=model.version,
            snapshot_id=model.snapshot_id,
            created_at=model.created_at,
            created_by=model.created_by,
            change_description=model.change_description,
            diff_summary=model.diff_summary,
            diff_json=model.diff_json,
            storage_object_key=model.storage_object_key,
            file_size_bytes=model.file_size_bytes,
            checksum=model.checksum,
        )
