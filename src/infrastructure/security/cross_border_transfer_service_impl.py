"""基础设施层跨境数据传输服务模块

基于 CrossBorderTransferServicePort 接口实现跨境数据传输请求的审批流程管理

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.entities.cross_border_transfer import (
    CrossBorderTransferRequest,
    TransferStatus,
)
from src.domain.ports.cross_border_transfer_service import CrossBorderTransferServicePort

if TYPE_CHECKING:
    pass


class TransferNotFoundError(Exception):
    """跨境传输请求未找到时抛出"""


class TransferNotApprovedError(Exception):
    """跨境传输请求未审批通过时执行操作抛出"""


class CrossBorderTransferServiceImpl(CrossBorderTransferServicePort):
    """跨境数据传输服务实现，管理跨境数据传输请求的审批流程

    Attributes:
        _requests: 内存中存储的传输请求字典，键为请求 ID
    """

    # SLA: Normal 4 hours, Urgent 1 hour
    SLA_NORMAL_HOURS = 4
    SLA_URGENT_HOURS = 1

    def __init__(self) -> None:
        """初始化跨境传输服务."""
        self._requests: dict[str, CrossBorderTransferRequest] = {}

    def request_transfer(self, data: CrossBorderTransferRequest) -> None:
        """发起跨境传输请求

        Args:
            data: 跨境传输请求
        """
        self._requests[str(data.request_id)] = data

    def approve(self, transfer_id: str, approver: str) -> None:
        """审批通过跨境传输请求

        Args:
            transfer_id: 传输请求 ID
            approver: 审批者

        Raises:
            TransferNotFoundError: 如果请求不存在
        """
        request = self._requests.get(transfer_id)
        if request is None:
            raise TransferNotFoundError(f"Transfer request {transfer_id} not found")

        approved = request.approve(approver)
        self._requests[transfer_id] = approved

    def reject(self, transfer_id: str, approver: str) -> None:
        """审批拒绝跨境传输请求

        Args:
            transfer_id: 传输请求 ID
            approver: 审批者

        Raises:
            TransferNotFoundError: 如果请求不存在
        """
        request = self._requests.get(transfer_id)
        if request is None:
            raise TransferNotFoundError(f"Transfer request {transfer_id} not found")

        rejected = request.reject(approver)
        self._requests[transfer_id] = rejected

    def execute(self, transfer_id: str) -> None:
        """执行已审批的跨境传输

        Args:
            transfer_id: 传输请求 ID

        Raises:
            TransferNotFoundError: 如果请求不存在
            TransferNotApprovedError: 如果请求未审批通过
        """
        request = self._requests.get(transfer_id)
        if request is None:
            raise TransferNotFoundError(f"Transfer request {transfer_id} not found")

        if request.status != TransferStatus.APPROVED:
            raise TransferNotApprovedError(f"Transfer request {transfer_id} is not approved (status: {request.status.value})")

        executed = request.execute()
        self._requests[transfer_id] = executed

    def block(self, transfer_id: str) -> None:
        """阻止跨境传输请求

        Args:
            transfer_id: 传输请求 ID

        Raises:
            TransferNotFoundError: 如果请求不存在
        """
        request = self._requests.get(transfer_id)
        if request is None:
            raise TransferNotFoundError(f"Transfer request {transfer_id} not found")

        blocked = request.block()
        self._requests[transfer_id] = blocked

    def get_request(self, transfer_id: str) -> CrossBorderTransferRequest | None:
        """获取跨境传输请求

        Args:
            transfer_id: 传输请求 ID

        Returns:
            跨境传输请求，如果不存在则返回 None
        """
        return self._requests.get(transfer_id)

    def list_pending_requests(self) -> list[CrossBorderTransferRequest]:
        """列出所有待审批的请求

        Returns:
            待审批请求列表
        """
        return [r for r in self._requests.values() if r.status == TransferStatus.PENDING]
