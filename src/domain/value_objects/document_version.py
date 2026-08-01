"""领域层文档版本快照值对象

定义 DocumentVersionSnapshot 和 DocumentVersionDiff 值对象，
用于文档版本快照和差异计算。

所有值对象均为 frozen dataclass，保持不可变性。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class DocumentVersionDiff:
    """文档版本差异值对象（中间值对象，不持久化）

    diff_summary 在创建快照时存入 DocumentVersionSnapshot.diff_summary，
    changed_fields 作为 dict[str, Any] 存入 DocumentVersionSnapshot.diff_json。

    Attributes:
        diff_summary: 人类可读的差异摘要
        changed_fields: 发生变更的字段列表
        is_initial: 是否为首次版本
    """

    diff_summary: str
    changed_fields: list[str] = field(default_factory=list)
    is_initial: bool = False


@dataclass(frozen=True)
class DocumentVersionSnapshot:
    """文档版本快照值对象（持久化）

    记录文档在某个时间点的版本快照信息，包含差异摘要和存储引用。

    Attributes:
        document_id: 文档唯一标识符
        version: 版本号
        snapshot_id: 快照唯一标识符
        created_at: 快照创建时间
        created_by: 操作者标识
        change_description: 变更描述
        diff_summary: 差异摘要文本
        diff_json: 结构化差异数据（JSONB 存储）
        storage_object_key: MinIO 对象存储 key
        file_size_bytes: 文件大小（字节）
        checksum: 文件校验和
    """

    document_id: uuid.UUID
    version: int
    snapshot_id: uuid.UUID
    created_at: datetime
    created_by: str
    change_description: str = ""
    diff_summary: str = ""
    diff_json: dict[str, Any] | None = None
    storage_object_key: str = ""
    file_size_bytes: int = 0
    checksum: str = ""

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典

        Returns:
            包含所有字段的字典，UUID 和 datetime 序列化为字符串
        """
        result: dict[str, Any] = {
            "document_id": str(self.document_id),
            "version": self.version,
            "snapshot_id": str(self.snapshot_id),
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "change_description": self.change_description,
            "diff_summary": self.diff_summary,
            "diff_json": self.diff_json,
            "storage_object_key": self.storage_object_key,
            "file_size_bytes": self.file_size_bytes,
            "checksum": self.checksum,
        }
        return result
