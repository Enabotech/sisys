"""领域层跨境数据传输请求实体模块

定义跨境数据传输请求领域实体，遵循六边形架构：领域层零依赖
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4


class TransferStatus(str, Enum):
    """Cross-border transfer request status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    BLOCKED = "blocked"


class LegalBasisType(str, Enum):
    """Legal basis types for cross-border transfer under PIPL."""

    SCC = "scc"  # 标准合同条款
    ADEQUACY_ASSESSMENT = "adequacy_assessment"  # 充分性认定
    SECURITY_ASSESSMENT = "security_assessment"  # 安全评估
    OTHER = "other"  # 法律法规其他条件


@dataclass(frozen=True)
class CrossBorderTransferRequest:
    """跨境数据传输请求领域实体（不可变）.

    Attributes:
        request_id: 唯一标识符
        data_id: 数据标识符
        destination: 目标国家/地区
        purpose: 传输目的
        status: 请求状态
        requester: 请求者
        approver: 审批者
        approval_timestamp: 审批时间戳
        legal_basis_type: 法律依据类型
    """

    request_id: UUID = field(default_factory=uuid4)
    data_id: str = ""
    destination: str = ""
    purpose: str = ""
    status: TransferStatus = TransferStatus.PENDING
    requester: str = ""
    approver: str | None = None
    approval_timestamp: datetime | None = None
    legal_basis_type: LegalBasisType = LegalBasisType.OTHER

    def is_pending(self) -> bool:
        """检查请求是否处于待审批状态

        Returns:
            True 如果状态为 PENDING
        """
        return self.status == TransferStatus.PENDING

    def approve(self, approver: str) -> CrossBorderTransferRequest:
        """审批通过

        Args:
            approver: 审批者

        Returns:
            新的 CrossBorderTransferRequest 实例，状态为 APPROVED
        """
        return CrossBorderTransferRequest(
            request_id=self.request_id,
            data_id=self.data_id,
            destination=self.destination,
            purpose=self.purpose,
            status=TransferStatus.APPROVED,
            requester=self.requester,
            approver=approver,
            approval_timestamp=datetime.now(UTC),
            legal_basis_type=self.legal_basis_type,
        )

    def reject(self, approver: str) -> CrossBorderTransferRequest:
        """审批拒绝

        Args:
            approver: 审批者

        Returns:
            新的 CrossBorderTransferRequest 实例，状态为 REJECTED
        """
        return CrossBorderTransferRequest(
            request_id=self.request_id,
            data_id=self.data_id,
            destination=self.destination,
            purpose=self.purpose,
            status=TransferStatus.REJECTED,
            requester=self.requester,
            approver=approver,
            approval_timestamp=datetime.now(UTC),
            legal_basis_type=self.legal_basis_type,
        )

    def execute(self) -> CrossBorderTransferRequest:
        """执行传输

        Returns:
            新的 CrossBorderTransferRequest 实例，状态为 EXECUTED
        """
        return CrossBorderTransferRequest(
            request_id=self.request_id,
            data_id=self.data_id,
            destination=self.destination,
            purpose=self.purpose,
            status=TransferStatus.EXECUTED,
            requester=self.requester,
            approver=self.approver,
            approval_timestamp=self.approval_timestamp,
            legal_basis_type=self.legal_basis_type,
        )

    def block(self) -> CrossBorderTransferRequest:
        """阻止传输

        Returns:
            新的 CrossBorderTransferRequest 实例，状态为 BLOCKED
        """
        return CrossBorderTransferRequest(
            request_id=self.request_id,
            data_id=self.data_id,
            destination=self.destination,
            purpose=self.purpose,
            status=TransferStatus.BLOCKED,
            requester=self.requester,
            approver=self.approver,
            approval_timestamp=self.approval_timestamp,
            legal_basis_type=self.legal_basis_type,
        )
