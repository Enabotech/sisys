"""领域层跨境数据传输服务端口模块

定义跨境数据传输服务的端口接口，遵循六边形架构：仅依赖 Protocol 和 Python 标准库

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.entities.cross_border_transfer import CrossBorderTransferRequest


@runtime_checkable
class CrossBorderTransferServicePort(Protocol):
    """跨境数据传输服务端口（协议接口）."""

    def request_transfer(self, data: CrossBorderTransferRequest) -> None:
        """发起跨境传输请求

        Args:
            data: 跨境传输请求
        """

    def approve(self, transfer_id: str, approver: str) -> None:
        """审批通过跨境传输请求

        Args:
            transfer_id: 传输请求 ID
            approver: 审批者
        """

    def reject(self, transfer_id: str, approver: str) -> None:
        """审批拒绝跨境传输请求

        Args:
            transfer_id: 传输请求 ID
            approver: 审批者
        """

    def list_pending_requests(self) -> list[CrossBorderTransferRequest]:
        """列出所有待审批的请求

        Returns:
            待审批请求列表
        """
