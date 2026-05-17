"""SISYS 基础设施层 PIPL 合规服务模块。

基于 PIPLComplianceServicePort 接口实现个人信息保护法合规记录管理和数据主体权利响应。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.entities.pipl_compliance_record import (
    LegalBasis,
    PIPLComplianceRecord,
)
from src.domain.ports.pipl_compliance_service import PIPLComplianceServicePort

if TYPE_CHECKING:
    pass


class PIPLComplianceServiceImpl(PIPLComplianceServicePort):
    """PIPL 合规服务实现，管理合规记录和响应数据主体权利请求。

    Attributes:
        _records: 内存中存储的合规记录字典，键为个人数据 ID
    """

    def __init__(self) -> None:
        """初始化 PIPL 合规服务."""
        self._records: dict[str, PIPLComplianceRecord] = {}

    def record_access(self, record: PIPLComplianceRecord) -> None:
        """记录个人信息访问。

        Args:
            record: PIPL 合规记录
        """
        self._records[record.personal_data_id] = record

    def get_record(self, personal_data_id: str) -> PIPLComplianceRecord | None:
        """获取 PIPL 合规记录。

        Args:
            personal_data_id: 个人数据 ID

        Returns:
            PIPL 合规记录，如果不存在则返回 None
        """
        return self._records.get(personal_data_id)

    def validate_legal_basis(self, data_id: str, legal_basis: str) -> bool:
        """验证数据处理的法律依据。

        Args:
            data_id: 数据 ID
            legal_basis: 法律依据类型

        Returns:
            True 如果法律依据有效
        """
        record = self._records.get(data_id)
        if record is None:
            return False

        if legal_basis == LegalBasis.CONSENT.value:
            return record.validate_consent()
        return True

    def respond_to_access_request(self, data_subject_id: str) -> dict:
        """响应数据主体访问请求。

        Args:
            data_subject_id: 数据主体 ID

        Returns:
            包含访问请求响应的字典
        """
        records = [r for r in self._records.values() if r.data_subject_id == data_subject_id]
        return {
            "status": "available",
            "records": [
                {
                    "personal_data_id": r.personal_data_id,
                    "purpose": r.purpose,
                    "legal_basis": r.legal_basis,
                    "accessed_at": r.accessed_at.isoformat() if r.accessed_at else None,
                }
                for r in records
            ],
        }

    def respond_to_correction_request(self, data_subject_id: str, corrections: dict) -> dict:
        """响应数据主体更正请求。

        Args:
            data_subject_id: 数据主体 ID
            corrections: 更正内容

        Returns:
            包含更正请求响应的字典
        """
        return {
            "status": "processed",
            "data_subject_id": data_subject_id,
            "corrections": corrections,
        }

    def respond_to_deletion_request(self, data_subject_id: str) -> dict:
        """响应数据主体删除请求。

        Args:
            data_subject_id: 数据主体 ID

        Returns:
            包含删除请求响应的字典
        """
        keys_to_remove = [pid for pid, r in self._records.items() if r.data_subject_id == data_subject_id]
        for key in keys_to_remove:
            del self._records[key]

        return {
            "status": "deleted",
            "data_subject_id": data_subject_id,
        }

    def respond_to_portability_request(self, data_subject_id: str) -> dict:
        """响应数据主体可携带权请求。

        Args:
            data_subject_id: 数据主体 ID

        Returns:
            包含可携带权请求响应的字典
        """
        records = [r for r in self._records.values() if r.data_subject_id == data_subject_id]
        return {
            "status": "available",
            "data": [
                {
                    "personal_data_id": r.personal_data_id,
                    "purpose": r.purpose,
                    "legal_basis": r.legal_basis,
                }
                for r in records
            ],
        }
