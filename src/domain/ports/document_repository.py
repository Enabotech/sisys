"""领域层 文档仓储端口

定义文档持久化的 Protocol 接口和查询条件值对象。
查询条件对标 AuditSearchCriteria 模式（结构化、不可变）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol, runtime_checkable
from uuid import UUID

from src.domain.entities.document import Document
from src.domain.value_objects.document_version import DocumentVersionSnapshot


@dataclass(frozen=True)
class DocumentQuery:
    """文档查询条件（不可变）

    对标 AuditSearchCriteria，将查询参数结构化。

    Attributes:
        tenant_id: 租户标识符（必填，租户隔离）
        document_id: 文档唯一标识符（按 ID 查询时使用）
        parse_status: 解析状态过滤
        document_type: 文档类型过滤
        uploaded_by: 上传者过滤
        offset: 分页偏移量
        limit: 分页大小
    """

    tenant_id: str
    document_id: UUID | None = None
    parse_status: str | None = None
    document_type: str | None = None
    uploaded_by: str | None = None
    offset: int = 0
    limit: int = 100


@runtime_checkable
class DocumentRepositoryPort(Protocol):
    """文档仓储端口协议

    提供文档实体的持久化操作接口，支持租户隔离。

    Methods:
        save: 持久化文档实体（新建或更新）
        find: 按条件查询单个文档
        list: 按条件列出文档（支持过滤和分页）
        save_version_snapshot: 持久化版本快照
        list_versions: 按文档 ID 和租户列出版本
        get_version: 获取指定版本快照
        save_with_version_check: 带乐观锁版本检查的保存方法
    """

    async def save(self, document: Document) -> Document:
        """持久化文档实体

        Args:
            document: 待持久化的文档实体

        Returns:
            持久化后的文档实体（含数据库生成的字段）
        """
        ...

    async def find(self, query: DocumentQuery) -> Document | None:
        """按条件查询单个文档

        Args:
            query: 查询条件（必须包含 tenant_id，可选 document_id）

        Returns:
            文档实体或 None
        """
        ...

    async def list(self, query: DocumentQuery) -> list[Document]:
        """按条件列出文档

        Args:
            query: 查询条件（必须包含 tenant_id，可选过滤字段）

        Returns:
            文档实体列表
        """
        ...

    async def save_version_snapshot(self, snapshot: DocumentVersionSnapshot) -> DocumentVersionSnapshot:
        """持久化版本快照

        Args:
            snapshot: 版本快照值对象

        Returns:
            持久化后的版本快照
        """
        ...

    async def list_versions(self, document_id: UUID, tenant_id: str) -> List[DocumentVersionSnapshot]:
        """按文档 ID 和租户列出版本历史

        Args:
            document_id: 文档唯一标识符
            tenant_id: 租户标识符

        Returns:
            版本快照列表（按版本号降序排列）
        """
        ...

    async def get_version(self, document_id: UUID, version: int, tenant_id: str) -> DocumentVersionSnapshot | None:
        """获取指定版本快照

        Args:
            document_id: 文档唯一标识符
            version: 版本号
            tenant_id: 租户标识符

        Returns:
            版本快照或 None
        """
        ...

    async def save_with_version_check(self, document: Document, expected_version: int) -> Document:
        """带乐观锁版本检查的保存方法

        当 document.version == expected_version 时执行保存并递增版本号，
        否则抛出 DocumentVersionConflictError。

        Args:
            document: 待保存的文档实体
            expected_version: 期望的当前版本号

        Returns:
            保存后的文档实体

        Raises:
            DocumentVersionConflictError: 版本不匹配时抛出
        """
        ...
