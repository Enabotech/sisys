"""AuditRepository Port - 审计仓储端口.

领域层接口，定义审计日志的数据访问契约。
遵循六边形架构：领域层零依赖，仅使用 ABC + 标准库。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class AuditSearchCriteria:
    """审计日志搜索条件（不可变）."""

    start_time: datetime | None = None
    end_time: datetime | None = None
    actor: str | None = None
    action_type: str | None = None
    target_resource: str | None = None
    offset: int = 0
    limit: int = 20
    match_any: bool = False  # True=OR条件, False=AND条件（默认）


@dataclass(frozen=True)
class AuditSearchResult:
    """审计日志搜索结果（不可变）."""

    items: tuple[dict[str, Any], ...]
    total: int
    offset: int
    limit: int


class AuditRepositoryPort(ABC):
    """审计仓储端口（领域层定义，仅使用 ABC + 标准库）.

    定义审计日志的 CRUD 和检索接口。
    实现类位于 infrastructure 层（可导入外部ORM框架）。
    """

    @abstractmethod
    async def save(self, audit_data: dict[str, Any]) -> UUID:
        """保存审计日志。

        Args:
            audit_data: 审计日志数据字典

        Returns:
            UUID 保存的审计日志 ID
        """
        ...

    @abstractmethod
    async def get_by_id(self, log_id: UUID) -> dict[str, Any] | None:
        """根据 ID 获取审计日志。

        Args:
            log_id: 审计日志 UUID

        Returns:
            dict 审计日志数据，或 None
        """
        ...

    @abstractmethod
    async def search(self, criteria: AuditSearchCriteria) -> AuditSearchResult:
        """搜索审计日志。

        Args:
            criteria: 搜索条件

        Returns:
            AuditSearchResult 包含 items, total, offset, limit
        """
        ...

    @abstractmethod
    async def update_archive_status(
        self,
        log_id: UUID,
        archived: bool,
        archived_at: datetime | None = None,
    ) -> bool:
        """更新归档状态。

        Args:
            log_id: 审计日志 UUID
            archived: 是否已归档
            archived_at: 归档时间

        Returns:
            True 如果更新成功
        """
        ...

    @abstractmethod
    async def get_archive_status(self, log_id: UUID) -> dict[str, Any] | None:
        """获取归档状态。

        Args:
            log_id: 审计日志 UUID

        Returns:
            dict 包含 archived, archived_at 等字段，或 None
        """
        ...
