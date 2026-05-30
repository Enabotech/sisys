"""领域层 文档仓储端口

定义文档持久化的 Protocol 接口和查询条件值对象。
查询条件对标 AuditSearchCriteria 模式（结构化、不可变）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.entities.document import Document


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
