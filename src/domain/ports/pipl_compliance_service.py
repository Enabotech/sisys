"""PIPLComplianceServicePort — Interface for PIPL compliance service.

遵循六边形架构：端口接口定义，仅依赖 Protocol 和 Python 标准库。
"""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.pipl_compliance_record import PIPLComplianceRecord


class PIPLComplianceServicePort(Protocol):
    """PIPL 合规服务端口（协议接口）."""

    def record_access(self, record: PIPLComplianceRecord) -> None:
        """记录个人信息访问。

        Args:
            record: PIPL 合规记录
        """

    def validate_legal_basis(self, data_id: str, legal_basis: str) -> bool:
        """验证数据处理的法律依据。

        Args:
            data_id: 数据 ID
            legal_basis: 法律依据类型

        Returns:
            True 如果法律依据有效
        """

    def respond_to_access_request(self, data_subject_id: str) -> dict:
        """响应数据主体访问请求。

        Args:
            data_subject_id: 数据主体 ID

        Returns:
            包含访问请求响应的字典
        """

    def respond_to_correction_request(self, data_subject_id: str, corrections: dict) -> dict:
        """响应数据主体更正请求。

        Args:
            data_subject_id: 数据主体 ID
            corrections: 更正内容

        Returns:
            包含更正请求响应的字典
        """

    def respond_to_deletion_request(self, data_subject_id: str) -> dict:
        """响应数据主体删除请求。

        Args:
            data_subject_id: 数据主体 ID

        Returns:
            包含删除请求响应的字典
        """

    def respond_to_portability_request(self, data_subject_id: str) -> dict:
        """响应数据主体可携带权请求。

        Args:
            data_subject_id: 数据主体 ID

        Returns:
            包含可携带权请求响应的字典
        """

    def get_record(self, personal_data_id: str) -> PIPLComplianceRecord | None:
        """获取 PIPL 合规记录。

        Args:
            personal_data_id: 个人数据 ID

        Returns:
            PIPL 合规记录，如果不存在则返回 None
        """
