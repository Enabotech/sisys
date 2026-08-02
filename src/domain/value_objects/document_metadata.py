"""领域层文档元数据值对象模块

定义 DocumentMetadata 值对象，封装入库文档的最小元字段集。
遵循领域层零依赖原则，仅使用 Python 标准库（dataclass / uuid / datetime / re）。
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# 最小元字段集常量（FR-DM-07 定义，单点维护）
REQUIRED_METADATA_FIELDS: tuple[str, ...] = (
    "creator",
    "created_at",
    "source",
    "license",
    "business_domain",
)

# 可自动填充字段映射：field_name → 自动填充策略描述
AUTO_FILLABLE_FIELDS: dict[str, str] = {
    "creator": "uploaded_by 参数",
    "created_at": "当前 UTC 时间（ISO 8601）",
}

# ISO 8601 简化校验正则（接受常见变体：YYYY-MM-DDTHH:MM:SS ±HH:MM / Z）
_ISO8601_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}"  # 日期部分
    r"([ T]\d{2}:\d{2}(:\d{2})?"  # 时间部分（秒可选）
    r"([+-]\d{2}:?\d{2}|Z)?"  # 时区偏移（可选）
    r")$"
)


def _is_valid_iso8601(value: str) -> bool:
    """纯函数：验证字符串是否为合法 ISO 8601 格式。

    领域层零依赖，仅使用 re 标准库。
    不接受仅日期无时间的格式（如 "2024-01-01"），
    因为这不符合 FR-DM-07 对精确时间戳的要求。

    Args:
        value: 待验证的时间戳字符串

    Returns:
        True 如果是合法 ISO 8601 格式
    """
    return bool(_ISO8601_PATTERN.match(value))


@dataclass(frozen=True)
class DocumentMetadata:
    """文档元数据值对象 — 封装入库文档的最小元字段集。

    不变量：
    - 五个最小元字段（creator/created_at/source/license/business_domain）必须全部非空
    - created_at 必须为合法 ISO 8601 格式
    - document_id 关联正确的文档引用

    Attributes:
        document_id: 文档唯一标识符
        metadata: 文档元数据字典
    """

    document_id: uuid.UUID
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """确保 metadata 不为 None。"""
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})

    def validate(self, raise_on_error: bool = True) -> list[str] | None:
        """验证最小元字段集完整性。

        支持灰度日志模式：当 raise_on_error=False 时，
        返回缺失字段列表而非抛出异常。

        Args:
            raise_on_error: 是否在验证失败时抛出异常
                            （True=抛出，False=仅返回缺失字段列表）

        Returns:
            当 raise_on_error=False 时，返回缺失字段列表
            （无缺失返回空列表）；raise_on_error=True 时返回 None

        Raises:
            MetadataValidationError: 当 raise_on_error=True 且存在缺失字段时抛出
        """
        missing = self.missing_fields()
        if missing and raise_on_error:
            from src.domain.exceptions.storage_exceptions import MetadataValidationError

            raise MetadataValidationError(
                document_id=self.document_id,
                missing_fields=missing,
            )
        return missing

    def missing_fields(self) -> list[str]:
        """返回缺失的必需字段列表（不抛出异常）。

        Returns:
            缺失字段名列表，空列表表示全部满足
        """
        missing: list[str] = []
        for field_name in REQUIRED_METADATA_FIELDS:
            value = self.metadata.get(field_name)
            if value is None or value == "":
                missing.append(field_name)
                continue
            # 特殊校验 created_at 的 ISO 8601 格式
            if field_name == "created_at" and isinstance(value, str):
                if not _is_valid_iso8601(value):
                    missing.append(field_name)
        return missing

    @classmethod
    def from_upload(
        cls,
        document_id: uuid.UUID,
        raw_metadata: dict[str, Any] | None = None,
        *,
        uploaded_by: str = "",
    ) -> DocumentMetadata:
        """从上传请求构造元数据值对象（含自动填充逻辑）。

        自动填充规则：
        - creator ← uploaded_by（如果原始 metadata 中未提供）
        - created_at ← 当前 UTC ISO 8601 时间戳（如果原始 metadata 中未提供）

        Args:
            document_id: 文档 ID
            raw_metadata: 用户提供的原始元数据字典
            uploaded_by: 上传者标识符（用于自动填充 creator）

        Returns:
            构造好的 DocumentMetadata 值对象
        """
        metadata = dict(raw_metadata or {})

        # 自动填充 creator（如果未显式提供）
        if "creator" not in metadata or metadata["creator"] is None or metadata["creator"] == "":
            metadata["creator"] = uploaded_by

        # 自动填充 created_at（如果未显式提供）
        if "created_at" not in metadata or metadata["created_at"] is None or metadata["created_at"] == "":
            metadata["created_at"] = datetime.now(UTC).isoformat()

        return cls(document_id=document_id, metadata=metadata)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（UUID 用 str() 处理，对齐 DocumentVersionSnapshot 模式）。

        Returns:
            包含 document_id（str）和 metadata 字段的字典
        """
        return {
            "document_id": str(self.document_id),
            "metadata": dict(self.metadata),
        }


__all__ = [
    "REQUIRED_METADATA_FIELDS",
    "AUTO_FILLABLE_FIELDS",
    "DocumentMetadata",
    "_is_valid_iso8601",
]