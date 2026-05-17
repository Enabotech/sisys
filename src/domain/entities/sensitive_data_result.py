"""SISYS 领域层敏感数据检测结果实体模块。

定义敏感数据检测结果领域实体，遵循六边形架构：领域层零依赖。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class SensitiveType(str, Enum):
    """Sensitive data type classification."""

    PII = "pii"  # Personally Identifiable Information
    TRADE_SECRET = "trade_secret"  # Business trade secrets  # pragma: allowlist secret
    FINANCIAL = "financial"  # Financial data
    BIOMETRIC = "biometric"  # Biometric data (PIPL sensitive)
    MINOR = "minor"  # Data about minors (PIPL enhanced protection)
    CUSTOM = "custom"  # User-defined sensitive type


@dataclass(frozen=True)
class SensitiveDataResult:
    """敏感数据检测结果领域实体（不可变）.

    Attributes:
        result_id: 唯一标识符
        source_data_hash: 源数据哈希，用于完整性追踪
        sensitive_types: 检测到的敏感数据类型列表
        confidence: 检测置信度 (0.0-1.0)
        labels: 附加标签
        detected_at: 检测时间戳
    """

    result_id: uuid.UUID = field(default_factory=uuid.uuid4)
    source_data_hash: str = ""
    sensitive_types: tuple[SensitiveType, ...] = field(default_factory=tuple)
    confidence: float = 1.0
    labels: tuple[str, ...] = field(default_factory=tuple)
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """检查检测置信度是否高于阈值。

        Args:
            threshold: 最小置信度阈值，默认 0.8

        Returns:
            True 如果置信度 >= threshold
        """
        return self.confidence >= threshold

    def has_type(self, sensitive_type: SensitiveType) -> bool:
        """检查结果是否包含指定敏感类型。

        Args:
            sensitive_type: 要检查的敏感数据类型

        Returns:
            True 如果 sensitive_types 中包含该类型
        """
        return sensitive_type in self.sensitive_types

    def merge_with(self, other: SensitiveDataResult) -> SensitiveDataResult:
        """合并两个检测结果。

        Args:
            other: 另一个检测结果

        Returns:
            合并后的新 SensitiveDataResult
        """
        combined_types = tuple(set(self.sensitive_types + other.sensitive_types))
        highest_confidence = max(self.confidence, other.confidence)
        combined_labels = tuple(set(self.labels + other.labels))
        return SensitiveDataResult(
            result_id=self.result_id,
            source_data_hash=self.source_data_hash or other.source_data_hash,
            sensitive_types=combined_types,
            confidence=highest_confidence,
            labels=combined_labels,
            detected_at=self.detected_at,
        )
