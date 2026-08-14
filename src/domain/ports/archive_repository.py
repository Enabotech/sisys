"""领域层档案仓储端口模块

定义 ArchiveRepositoryPort 协议和 ArchiveQuery 值对象。
ArchiveRepositoryPort 继承 L2RdbPort[StrategicArchive] 获得基础 CRUD，
并扩展 find、list_by_plan、list_by_archive_type、count 等查询方法。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.ports.l2_rdb import L2RdbPort

logger = logging.getLogger(__name__)


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
        offset: 分页偏移量
        limit: 每页条数（1-1000，默认 20）
    """

    plan_id: UUID | None = None
    archive_type: ArchiveType | None = None
    plan_type: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    offset: int = 0
    limit: int = 20

    def __post_init__(self) -> None:
        """构造后校验 limit 取值范围"""
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
            raise ValueError("start_date must be before or equal to end_date")


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


__all__ = [
    "ArchiveQuery",
    "ArchiveRepositoryPort",
]
