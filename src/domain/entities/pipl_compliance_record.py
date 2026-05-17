"""领域层 PIPL 合规记录实体模块

定义个人信息保护法合规记录领域实体，遵循六边形架构：领域层零依赖

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4


class ConsentStatus(str, Enum):
    """Consent status for PIPL compliance."""

    NOT_GIVEN = "not_given"
    GIVEN = "given"
    WITHDRAWN = "withdrawn"


class LegalBasis(str, Enum):
    """Legal basis types for personal information processing under PIPL."""

    CONSENT = "consent"  # 同意
    CONTRACT = "contract"  # 合同
    LEGAL_OBLIGATION = "legal_obligation"  # 法定义务
    VITAL_INTEREST = "vital_interest"  # 生命利益
    PUBLIC_TASK = "public_task"  # 公共任务
    LEGITIMATE_INTEREST = "legitimate_interest"  # 合法权益
    MINOR_CONSENT = "minor_consent"  # 未成年人监护人同意


@dataclass(frozen=True)
class PIPLComplianceRecord:
    """PIPL 合规记录领域实体（不可变）.

    Attributes:
        access_id: 唯一标识符
        personal_data_id: 个人数据标识符
        purpose: 处理目的
        legal_basis: 法律依据
        consent_status: 同意状态
        accessor: 访问者
        accessed_at: 访问时间
        data_subject_id: 数据主体标识符
        is_minor: 是否为未成年人
        guardian_consent_obtained: 是否获得监护人同意
    """

    access_id: UUID = field(default_factory=uuid4)
    personal_data_id: str = ""
    purpose: str = ""
    legal_basis: str = "consent"
    consent_status: ConsentStatus = ConsentStatus.NOT_GIVEN
    accessor: str = ""
    accessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    data_subject_id: str = ""
    is_minor: bool = False
    guardian_consent_obtained: bool = False

    def validate_consent(self) -> bool:
        """验证同意是否有效

        Returns:
            True 如果同意状态为 GIVEN
        """
        return self.consent_status == ConsentStatus.GIVEN

    def is_compliant(self) -> bool:
        """检查处理是否合规

        Returns:
            True 如果合规（同意有效或非同意法律依据）
        """
        if self.legal_basis == LegalBasis.CONSENT.value:
            return self.validate_consent()
        return True

    def validate_minor_consent(self) -> bool:
        """验证未成年人同意是否有效

        Returns:
            True 如果不是未成年人，或未成年人已获得监护人同意
        """
        if not self.is_minor:
            return True
        return self.guardian_consent_obtained and self.validate_consent()
