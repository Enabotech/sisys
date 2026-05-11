"""CrossBorderTransferServicePort — Interface for cross-border transfer service.

遵循六边形架构：端口接口定义，仅依赖 ABC 和 Python 标准库。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.cross_border_transfer import CrossBorderTransferRequest


class CrossBorderTransferServicePort(ABC):
    """跨境数据传输服务端口（抽象接口）."""

    @abstractmethod
    def request_transfer(self, data: CrossBorderTransferRequest) -> None:
        """发起跨境传输请求。

        Args:
            data: 跨境传输请求
        """
        ...

    @abstractmethod
    def approve(self, transfer_id: str, approver: str) -> None:
        """审批通过跨境传输请求。

        Args:
            transfer_id: 传输请求 ID
            approver: 审批者
        """
        ...

    @abstractmethod
    def reject(self, transfer_id: str, approver: str) -> None:
        """审批拒绝跨境传输请求。

        Args:
            transfer_id: 传输请求 ID
            approver: 审批者
        """
        ...

    @abstractmethod
    def list_pending_requests(self) -> list[CrossBorderTransferRequest]:
        """列出所有待审批的请求。

        Returns:
            待审批请求列表
        """
        ...
