"""AuditService Port - 审计服务端口.

领域层接口，定义审计服务的契约。
遵循六边形架构：领域层零依赖，仅使用标准库。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from src.domain.exceptions.service_exceptions import AuditError

__all__ = ["AuditError"]


@dataclass(frozen=True)
class AuditRecord:
    """审计记录领域值对象（不可变）."""

    log_id: UUID
    timestamp: datetime
    actor: str
    action_type: str
    target_resource: str
    old_value: dict[str, Any]
    new_value: dict[str, Any]
    correction_level: int | None = None


@runtime_checkable
class AuditServicePort(Protocol):
    """审计服务端口（领域层定义，仅使用标准库）.

    定义审计日志记录、检索、完整性验证的接口。
    实现类位于 infrastructure 层（可导入外部库）。
    """

    async def record(
        self,
        actor: str,
        action_type: str,
        target_resource: str,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> AuditRecord:
        """记录审计日志。

        Args:
            actor: 用户 ID 或系统组件标识
            action_type: 操作类型（如 "authentication:login"）
            target_resource: 被操作资源的标识
            old_value: 操作前的状态（可选）
            new_value: 操作后的状态（可选）
            correlation_id: 可选的关联 ID 用于追踪

        Returns:
            AuditRecord 审计记录领域值对象

        Raises:
            AuditError: 记录失败时抛出
        """

    async def verify_integrity(self, log_id: UUID) -> bool:
        """验证单条审计日志的完整性。

        Args:
            log_id: 审计日志的 UUID

        Returns:
            True 如果校验和匹配，False 如果已篡改

        Raises:
            AuditError: 验证过程出错时抛出
        """

    async def verify_batch(self, log_ids: list[UUID] | None = None) -> dict[str, Any]:
        """批量验证审计日志完整性。

        Args:
            log_ids: 要验证的日志 UUID 列表（None 表示全部）

        Returns:
            dict 包含 total, passed, failed, details
        """

    async def archive(self, older_than_days: int = 30) -> int:
        """归档旧的审计日志到 WORM 存储。

        Args:
            older_than_days: 归档多久之前的日志（默认 30 天）

        Returns:
            int 已归档的日志数量
        """
