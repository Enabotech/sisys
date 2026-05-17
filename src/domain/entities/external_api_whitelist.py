"""SISYS 领域层外部 API 白名单实体模块。

定义外部 API 白名单领域实体，遵循六边形架构：领域层零依赖。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4


class RiskLevel(str, Enum):
    """External API risk levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class ExternalAPIWhitelist:
    """外部 API 白名单领域实体（不可变）.

    Attributes:
        api_id: 唯一标识符
        endpoint: API 端点
        provider: API 提供商
        region: 服务区域
        is_verified: 是否已验证
        risk_level: 风险等级
        valid_from: 生效时间
        valid_until: 失效时间
    """

    api_id: UUID = field(default_factory=uuid4)
    endpoint: str = ""
    provider: str = ""
    region: str = ""
    is_verified: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    valid_from: datetime = field(default_factory=lambda: datetime.now(UTC))
    valid_until: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_valid(self) -> bool:
        """检查白名单条目是否有效（未过期且已验证）。

        Returns:
            True 如果条目有效
        """
        if not self.is_verified:
            return False
        now = datetime.now(UTC)
        return self.valid_from <= now <= self.valid_until

    def is_high_risk(self) -> bool:
        """检查是否为高风险 API。

        Returns:
            True 如果 risk_level 为 HIGH
        """
        return self.risk_level == RiskLevel.HIGH

    def requires_dpo_approval(self) -> bool:
        """检查是否需要 DPO 审批（高风险 API）。

        Returns:
            True 如果风险等级为 HIGH
        """
        return self.is_high_risk()

    def is_expired(self) -> bool:
        """检查是否已过期。

        Returns:
            True 如果当前时间超过 valid_until
        """
        return datetime.now(UTC) > self.valid_until

    def days_until_expiry(self) -> int:
        """计算距离过期的天数。

        Returns:
            距离过期的天数，负数表示已过期
        """
        delta = self.valid_until - datetime.now(UTC)
        return delta.days
