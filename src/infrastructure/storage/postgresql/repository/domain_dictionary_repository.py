"""基础设施层 PostgreSQL 词典仓储模块

实现 DomainDictionaryPort 端口，使用 PostgreSQL 持久化词典数据。
词条存 dictionary_entries 表，快照存 dictionary_snapshots 表。
支持乐观锁版本控制和快照回滚。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError

from src.domain.exceptions import (
    DictionaryEntryConflictError,
    DictionaryNotFoundError,
    DictionaryVersionConflictError,
)
from src.domain.ports.domain_dictionary import (
    DictionaryEntry,
    DictionaryQuery,
    DictionarySnapshot,
)
from src.infrastructure.storage.postgresql.models.dictionary import (
    DictionaryEntryModel,
    DictionarySnapshotModel,
)
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import PostgreSQLAdapter


class PostgreSQLDomainDictionaryRepository(PostgreSQLAdapter[DictionaryEntry, DictionaryEntryModel]):
    """词典仓储实现

    继承 PostgreSQLAdapter[DictionaryEntry, DictionaryEntryModel]，
    通过 _to_entity/_to_model 隔离领域层与 ORM 层。
    使用 DictionaryQuery 值对象支持结构化过滤和分页。
    """

    pk_column: str = "term"

    def __init__(self) -> None:
        super().__init__(DictionaryEntryModel)

    # ------------------------------------------------------------------
    # 实体/模型转换
    # ------------------------------------------------------------------

    def _to_entity(self, model: DictionaryEntryModel) -> DictionaryEntry:
        """将 ORM 模型转换为领域实体"""
        return DictionaryEntry(
            term=model.term,
            entity_type=model.entity_type,
            category=model.category,
            active=model.active,
            version=model.version,
            created_by=model.created_by,
            created_at=model.created_at.isoformat() if model.created_at else "",
            updated_at=model.updated_at.isoformat() if model.updated_at else "",
        )

    def _to_model(self, entry: DictionaryEntry) -> DictionaryEntryModel:
        """将领域实体转换为 ORM 模型"""
        created_at = None
        if entry.created_at:
            try:
                created_at = datetime.fromisoformat(entry.created_at)
            except (ValueError, TypeError):
                created_at = datetime.now(UTC)
        updated_at = None
        if entry.updated_at:
            try:
                updated_at = datetime.fromisoformat(entry.updated_at)
            except (ValueError, TypeError):
                updated_at = datetime.now(UTC)

        return DictionaryEntryModel(
            term=entry.term,
            entity_type=entry.entity_type,
            category=entry.category,
            active=entry.active,
            version=entry.version,
            created_by=entry.created_by,
            created_at=created_at,
            updated_at=updated_at,
        )

    # ------------------------------------------------------------------
    # DomainDictionaryPort 实现
    # ------------------------------------------------------------------

    async def list_entries(self, query: DictionaryQuery) -> list[DictionaryEntry]:
        """按查询条件列出词条"""
        stmt = select(DictionaryEntryModel)

        if query.category is not None:
            stmt = stmt.where(DictionaryEntryModel.category == query.category)
        if query.entity_type is not None:
            stmt = stmt.where(DictionaryEntryModel.entity_type == query.entity_type)
        if query.active_only:
            stmt = stmt.where(DictionaryEntryModel.active.is_(True))

        # 分页
        offset = (query.page - 1) * query.page_size
        stmt = stmt.order_by(DictionaryEntryModel.term).offset(offset).limit(query.page_size)

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def get_entry(self, term: str) -> DictionaryEntry | None:
        """按词条名查询"""
        stmt = select(DictionaryEntryModel).where(DictionaryEntryModel.term == term)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def add_entry(self, entry: DictionaryEntry) -> DictionaryEntry:
        """添加词条

        Raises:
            DictionaryEntryConflictError: 词条已存在
        """
        model = self._to_model(entry)
        self._session.add(model)
        try:
            # 使用 savepoint 局部回滚，避免破坏外层事务
            async with self._session.begin_nested():
                await self._session.flush()
        except IntegrityError as exc:
            if "dictionary_entries_pkey" in str(exc) or "unique" in str(exc).lower():
                raise DictionaryEntryConflictError(term=entry.term)
            raise
        return self._to_entity(model)

    async def update_entry(self, term: str, entry: DictionaryEntry) -> DictionaryEntry:
        """修改词条

        Raises:
            DictionaryNotFoundError: 词条不存在
            DictionaryVersionConflictError: 版本冲突
        """
        # 原子 UPDATE 实现乐观锁
        now = datetime.now(UTC)
        stmt = (
            update(DictionaryEntryModel)
            .where(
                DictionaryEntryModel.term == term,
                DictionaryEntryModel.version == entry.version - 1,
            )
            .values(
                entity_type=entry.entity_type,
                category=entry.category,
                active=entry.active,
                version=entry.version,
                updated_at=now,
            )
        )
        result = await self._session.execute(stmt)
        cursor_result = cast("CursorResult", result)

        if cursor_result.rowcount == 0:
            # rowcount == 0：词条不存在或版本不匹配
            check_stmt = select(DictionaryEntryModel).where(DictionaryEntryModel.term == term)
            check_result = await self._session.execute(check_stmt)
            model = check_result.scalar_one_or_none()

            if model is None:
                raise DictionaryNotFoundError(term=term)

            raise DictionaryVersionConflictError(
                expected_version=entry.version - 1,
                actual_version=model.version,
            )

        # 读取更新后的数据
        reload_stmt = select(DictionaryEntryModel).where(DictionaryEntryModel.term == term)
        reload_result = await self._session.execute(reload_stmt)
        model = reload_result.scalar_one()
        return self._to_entity(model)

    async def delete_entry(self, term: str) -> None:
        """删除词条

        Raises:
            DictionaryNotFoundError: 词条不存在
        """
        stmt = select(DictionaryEntryModel).where(DictionaryEntryModel.term == term)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            raise DictionaryNotFoundError(term=term)

        await self._session.delete(model)

    async def get_active_dictionary(self) -> list[tuple[str, str]]:
        """获取活动词典（仅 active=True 的词条）"""
        stmt = select(DictionaryEntryModel).where(DictionaryEntryModel.active.is_(True)).order_by(DictionaryEntryModel.term)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [(m.term, m.entity_type) for m in models]

    async def create_snapshot(self, created_by: str) -> DictionarySnapshot:
        """创建词典快照"""
        # 获取所有词条
        stmt = select(DictionaryEntryModel).order_by(DictionaryEntryModel.term)
        result = await self._session.execute(stmt)
        all_entries = result.scalars().all()

        # 计算版本号
        version_stmt = select(DictionarySnapshotModel).order_by(DictionarySnapshotModel.version.desc()).limit(1)
        version_result = await self._session.execute(version_stmt)
        latest_snapshot = version_result.scalar_one_or_none()
        new_version = (latest_snapshot.version + 1) if latest_snapshot else 1

        # 序列化词条
        entries_dict = {}
        for entry in all_entries:
            entries_dict[entry.term] = {
                "term": entry.term,
                "entity_type": entry.entity_type,
                "category": entry.category,
                "active": entry.active,
                "version": entry.version,
                "created_by": entry.created_by,
                "created_at": entry.created_at.isoformat() if entry.created_at else "",
                "updated_at": entry.updated_at.isoformat() if entry.updated_at else "",
            }

        # 计算变更摘要
        added_count = len(all_entries)
        change_summary = {"total_entries": added_count}

        snapshot_model = DictionarySnapshotModel(
            version=new_version,
            entries=entries_dict,
            created_by=created_by,
            change_summary=change_summary,
        )
        self._session.add(snapshot_model)
        await self._session.flush()

        return DictionarySnapshot(
            snapshot_id=str(snapshot_model.snapshot_id),
            version=new_version,
            entries=tuple(self._to_entity(e) for e in all_entries),
            created_by=created_by,
            created_at=snapshot_model.created_at.isoformat() if snapshot_model.created_at else "",
            change_summary=change_summary,
        )

    async def rollback(self, version: int) -> None:
        """回滚至指定版本

        Raises:
            DictionaryNotFoundError: 目标版本不存在
        """
        # 查找目标快照
        stmt = select(DictionarySnapshotModel).where(DictionarySnapshotModel.version == version)
        result = await self._session.execute(stmt)
        snapshot_model = result.scalar_one_or_none()

        if snapshot_model is None:
            raise DictionaryNotFoundError(version=version)

        if not snapshot_model.entries:
            return

        # 清空现有词条（批量删除，避免 N+1）
        await self._session.execute(delete(DictionaryEntryModel))

        # 从快照重建词条
        now = datetime.now(UTC)
        for term_data in snapshot_model.entries.values():
            created_at = _parse_datetime(term_data.get("created_at", ""), now)
            updated_at = _parse_datetime(term_data.get("updated_at", ""), now)

            entry_model = DictionaryEntryModel(
                term=term_data.get("term", ""),
                entity_type=term_data.get("entity_type", ""),
                category=term_data.get("category", "general"),
                active=term_data.get("active", True),
                version=term_data.get("version", 1),
                created_by=term_data.get("created_by", ""),
                created_at=created_at,
                updated_at=updated_at,
            )
            self._session.add(entry_model)

        await self._session.flush()

    async def list_snapshots(self) -> list[DictionarySnapshot]:
        """列出所有快照（按版本降序）"""
        stmt = select(DictionarySnapshotModel).order_by(DictionarySnapshotModel.version.desc())
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        snapshots = []
        for model in models:
            # 快照的 entries 不加载完整词条对象（仅计数）
            entry_count = len(model.entries) if model.entries else 0
            snapshots.append(
                DictionarySnapshot(
                    snapshot_id=str(model.snapshot_id),
                    version=model.version,
                    entries=(),
                    created_by=model.created_by,
                    created_at=model.created_at.isoformat() if model.created_at else "",
                    change_summary={
                        **(model.change_summary or {}),
                        "entry_count": entry_count,
                    },
                )
            )
        return snapshots

    async def count_entries(self, query: DictionaryQuery) -> int:
        """统计符合条件的词条总数

        Args:
            query: 查询条件

        Returns:
            符合条件的词条总数
        """
        from sqlalchemy import func as sa_func

        stmt = select(sa_func.count()).select_from(DictionaryEntryModel)
        if query.category is not None:
            stmt = stmt.where(DictionaryEntryModel.category == query.category)
        if query.entity_type is not None:
            stmt = stmt.where(DictionaryEntryModel.entity_type == query.entity_type)
        if query.active_only:
            stmt = stmt.where(DictionaryEntryModel.active.is_(True))
        result = await self._session.execute(stmt)
        return int(result.scalar() or 0)


def _parse_datetime(dt_str: str, default: datetime) -> datetime | None:
    """解析 ISO 时间字符串"""
    if not dt_str:
        return default
    try:
        return datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        return default
