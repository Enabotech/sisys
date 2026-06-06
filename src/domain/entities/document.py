"""领域层文档实体模块

定义文档领域实体，包含元数据、版本历史和解析状态管理
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from src.domain.exceptions import EntityValidationError


class DocumentType(str, Enum):
    """支持的文档类型枚举"""

    STRATEGIC_PLAN = "strategic_plan"
    BUSINESS_PLAN = "business_plan"
    MARKET_REPORT = "market_report"
    FINANCIAL_REPORT = "financial_report"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    MEETING_NOTES = "meeting_notes"
    OTHER = "other"


class ParseStatus(str, Enum):
    """文档解析状态枚举"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DocumentVersion:
    """文档版本记录"""

    version: int
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    created_by: str = ""
    change_description: str = ""


@dataclass
class Document:
    """文档实体，包含元数据和版本历史

    不变量约束:
    - document_id 必须为有效 UUID
    - filename 不能为空
    - version 必须 >= 1
    - 支持格式: pdf, docx, xlsx, pptx, txt, md, csv, html 等

    Attributes:
        document_id: 文档唯一标识符
        filename: 文件名
        document_type: 文档类型
        file_size_bytes: 文件大小（字节）
        mime_type: MIME 类型
        parse_status: 解析状态
        version: 当前版本号
        version_history: 版本历史记录
        metadata: 文档元数据
        embedding: 文档嵌入向量
        created_at: 创建时间
        updated_at: 最后更新时间
    """

    document_id: uuid.UUID
    filename: str
    document_type: DocumentType = DocumentType.OTHER
    file_size_bytes: int = 0
    mime_type: str = ""
    parse_status: ParseStatus = ParseStatus.PENDING
    version: int = 1
    version_history: list[DocumentVersion] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    tenant_id: str = ""
    uploaded_by: str = ""

    def validate(self) -> bool:
        """验证不变量约束

        Returns:
            所有不变量满足时返回 True

        Raises:
            EntityValidationError: 任何不变量违反时抛出
        """
        if not isinstance(self.document_id, uuid.UUID):
            raise EntityValidationError(
                message="document_id must be a valid UUID",
                context={"entity": "Document", "field": "document_id"},
            )
        if not self.filename or not self.filename.strip():
            raise EntityValidationError(
                message="filename must not be empty",
                context={"entity": "Document", "field": "filename"},
            )
        if self.version < 1:
            raise EntityValidationError(
                message="version must be >= 1",
                context={"entity": "Document", "field": "version", "constraint": ">=1"},
            )
        if self.file_size_bytes < 0:
            raise EntityValidationError(
                message="file_size_bytes must be non-negative",
                context={"entity": "Document", "field": "file_size_bytes"},
            )
        # P1-03 Fix: Validate embedding for NaN/Inf values
        if self.embedding is not None:
            for i, val in enumerate(self.embedding):
                if not isinstance(val, int | float):
                    raise EntityValidationError(
                        message=f"embedding[{i}] must be a number",
                        context={"entity": "Document", "field": f"embedding[{i}]"},
                    )
                if math.isnan(val) or math.isinf(val):
                    raise EntityValidationError(
                        message=f"embedding[{i}] contains NaN/Inf",
                        context={"entity": "Document", "field": f"embedding[{i}]"},
                    )
        return True

    def validate_metadata(self, required_fields: list[str] | None = None) -> bool:
        """验证必需的元数据字段是否存在

        Args:
            required_fields: 必需的元数据键列表

        Returns:
            所有必需字段都存在时返回 True

        Raises:
            EntityValidationError: 任何必需字段缺失时抛出
        """
        if required_fields is None:
            required_fields = []
        missing = [f for f in required_fields if f not in self.metadata]
        if missing:
            raise EntityValidationError(
                message=f"Missing required metadata fields: {missing}",
                context={"entity": "Document", "field": "metadata", "missing": missing},
            )
        return True

    def bump_version(self, change_description: str, created_by: str = "") -> int:
        """递增文档版本号并记录历史

        Args:
            change_description: 本次版本变更描述
            created_by: 变更操作者

        Returns:
            新版本号
        """
        # Record current version in history
        current_version = DocumentVersion(
            version=self.version,
            change_description=change_description,
            created_by=created_by,
        )
        self.version_history.append(current_version)
        self.version += 1
        self.updated_at = datetime.now(UTC)
        return self.version
