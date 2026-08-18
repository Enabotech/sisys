"""领域层档案仓储端口模块

定义 ArchiveRepositoryPort 协议和 ArchiveQuery 值对象。
ArchiveRepositoryPort 继承 L2RdbPort[StrategicArchive] 获得基础 CRUD，
并扩展 find、list_by_plan、list_by_archive_type、count 等查询方法。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.exceptions import EntityValidationError
from src.domain.ports.l2_rdb import L2RdbPort

logger = logging.getLogger(__name__)


class ValidityStatus(str, Enum):
    """档案有效期状态枚举

    用于 ArchiveQuery 按有效期状态过滤查询。

    Attributes:
        VALID: 当前有效（未过期且已生效）
        EXPIRED: 已过期（valid_until 早于当前时间）
    """

    VALID = "valid"
    EXPIRED = "expired"


@dataclass(frozen=True)
class ArchiveQuery:
    """档案查询值对象

    用于多字段组合查询 + 分页的多字段查询场景。

    Attributes:
        plan_id: 按规划 ID 过滤
        archive_type: 按档案类型过滤
        plan_type: 按规划类型过滤（"SP"/"BP"）
        start_date: 归档时间范围起始
        end_date: 归档时间范围结束
        valid_from: 按生效时间过滤（valid_from >= 指定值）
        valid_until: 按失效时间过滤（valid_until <= 指定值）
        validity_status: 按有效期状态过滤（VALID/EXPIRED，None 表示不过滤）
        staleness_status: 按陈旧状态过滤（"stale"/"fresh"，None 表示不过滤；
                          与 validity_status 语义区分：validity_status 按时间计算，staleness_status 按 metadata 标记判断）
        archive_ids: 按 ID 列表批量查询（供 StalenessWeightService 兜底链使用，避免 N+1 问题）
        exclude_staleness: 排除已标记陈旧的档案（幂等保证）
        stale_before: 仅查询满足陈旧判定条件的档案（valid_until 早于该时间，或无有效期且 archived_at 早于该时间前 365 天）
        offset: 分页偏移量
        limit: 每页条数（1-1000，默认 20）
    """

    plan_id: UUID | None = None
    archive_type: ArchiveType | None = None
    plan_type: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    validity_status: ValidityStatus | None = None
    staleness_status: str | None = None
    archive_ids: list[UUID] | None = None
    exclude_staleness: bool = False
    stale_before: datetime | None = None
    offset: int = 0
    limit: int = 20

    def __post_init__(self) -> None:
        """构造后校验 limit 取值范围和 validity_status/staleness_status 取值"""
        # 使用 object.__setattr__ 因为 frozen=True
        if self.limit < 1:
            logger.warning("ArchiveQuery limit %s clamped to 1", self.limit)
            object.__setattr__(self, "limit", 1)
        elif self.limit > 1000:
            logger.warning("ArchiveQuery limit %s clamped to 1000", self.limit)
            object.__setattr__(self, "limit", 1000)
        if self.offset < 0:
            object.__setattr__(self, "offset", 0)
        if self.start_date is not None and self.end_date is not None and self.start_date > self.end_date:
            raise EntityValidationError(
                message="start_date must be before or equal to end_date",
                context={"entity": "ArchiveQuery", "field": "start_date"},
            )
        if self.validity_status is not None and not isinstance(self.validity_status, ValidityStatus):
            raise EntityValidationError(
                message="validity_status must be a ValidityStatus enum member or None",
                context={"entity": "ArchiveQuery", "field": "validity_status"},
            )
        # staleness_status 校验：仅允许 "stale"/"fresh"/None
        if self.staleness_status is not None and self.staleness_status not in ("stale", "fresh"):
            raise EntityValidationError(
                message="staleness_status must be 'stale', 'fresh', or None",
                context={"entity": "ArchiveQuery", "field": "staleness_status"},
            )


@runtime_checkable
class ArchiveRepositoryPort(L2RdbPort[StrategicArchive], Protocol):
    """档案仓储端口

    继承 L2RdbPort[StrategicArchive] 获得：
    - get_by_id(archive_id) -> StrategicArchive | None
    - save(archive) -> StrategicArchive
    - delete(archive_id) -> None（软删除）
    - list_all() -> list[StrategicArchive]

    扩展方法：
    - find(query) -> list[StrategicArchive]：按条件查询
    - list_by_plan(plan_id) -> list[StrategicArchive]：按规划 ID 列出
    - list_by_archive_type(archive_type) -> list[StrategicArchive]：按类型列出
    - count(query) -> int：统计数量
    """

    async def find(self, query: ArchiveQuery) -> list[StrategicArchive]:
        """按条件查询档案

        Args:
            query: 查询条件（ArchiveQuery 值对象）

        Returns:
            符合条件的档案列表
        """

    async def list_by_plan(self, plan_id: UUID) -> list[StrategicArchive]:
        """按规划 ID 列出档案

        Args:
            plan_id: 规划 ID

        Returns:
            该规划关联的所有档案
        """

    async def list_by_archive_type(self, archive_type: ArchiveType) -> list[StrategicArchive]:
        """按档案类型列出

        Args:
            archive_type: 档案类型

        Returns:
            指定类型的档案列表
        """

    async def count(self, query: ArchiveQuery) -> int:
        """统计满足条件的档案数量

        Args:
            query: 查询条件

        Returns:
            符合条件的档案数量
        """

    async def find_for_update(self, query: ArchiveQuery) -> list[StrategicArchive]:
        """按条件查询档案（带 FOR UPDATE 悲观锁）

        用于冲突检测等需要并发安全的场景，锁定同一 plan_id+archive_type 的相关行。

        Args:
            query: 查询条件（ArchiveQuery 值对象）

        Returns:
            符合条件的档案列表
        """

    async def mark_stale(self, archive_id: UUID, stale_since: str | None = None, stale_reason: str | None = None) -> bool:
        """条件标记档案为陈旧（并发安全）

        使用 UPDATE ... WHERE ... AND metadata->>'staleness' IS DISTINCT FROM 'stale'
        条件更新，确保仅当档案尚未标记时才写入。并发环境下被其他实例抢先标记时
        返回 False，避免重复事件。

        Args:
            archive_id: 档案 ID
            stale_since: 标记时间（ISO 8601 字符串，None 时由实现自行生成）
            stale_reason: 陈旧原因（"expired"/"archived_too_long"，None 时不写入）

        Returns:
            标记成功返回 True，已被其他实例抢先标记返回 False
        """


__all__ = [
    "ArchiveQuery",
    "ArchiveRepositoryPort",
    "ValidityStatus",
]
