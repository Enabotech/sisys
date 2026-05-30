"""领域层 文档事件模块

定义文档处理相关的领域事件
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .base import DomainEvent


@dataclass(frozen=True)
class DocumentProcessed(DomainEvent):
    """文档成功解析和索引后触发的事件

    Attributes:
        document_id: 文档唯一标识符
        event_type: 事件类型，固定为"DocumentProcessed"
        parse_result: 解析结果字典
        embedding: 文档嵌入向量（可选）
    """

    document_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="DocumentProcessed", init=False)
    parse_result: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.document_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Document")


@dataclass(frozen=True)
class DocumentUploaded(DomainEvent):
    """文档上传完成后触发的事件（RELIABLE 模式，RabbitMQ via Outbox）

    与 DocumentProcessed（解析完成）是文档生命周期中的不同阶段事件。

    Attributes:
        document_id: 文档唯一标识符
        filename: 原始文件名
        mime_type: 文件 MIME 类型
        file_size_bytes: 文件大小（字节）
        tenant_id: 租户标识符
        uploaded_by: 上传者用户标识符
    """

    document_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="DocumentUploaded", init=False)
    filename: str = ""
    mime_type: str = ""
    file_size_bytes: int = 0
    tenant_id: str = ""
    uploaded_by: str = ""

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.document_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "Document")
