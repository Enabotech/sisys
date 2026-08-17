"""PostgreSQLArchiveRepository 仓储单元测试

验证 CRUD、查询、实体/模型转换等操作。
使用 Mock 获取的 session 测试。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.strategic_archive import ArchiveType, StrategicArchive
from src.domain.ports.archive_repository import ArchiveQuery
from src.infrastructure.storage.postgresql.models.archive import ArchiveModel
from src.infrastructure.storage.postgresql.repository.archive_repository import (
    PostgreSQLArchiveRepository,
)


@pytest.fixture
def repository() -> PostgreSQLArchiveRepository:
    """创建仓储实例"""
    return PostgreSQLArchiveRepository()


def _make_archive(overrides: dict[str, Any] | None = None) -> StrategicArchive:
    """创建测试用档案实体"""
    archive_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    archive = StrategicArchive(
        archive_id=archive_id,
        plan_id=plan_id,
        plan_type="SP",
        archive_type=ArchiveType.ASSUMPTION,
        assumptions={"key": "value"},
        decision_basis={},
        execution_deviation={},
        metadata_ref="strategic_archives:test",
        created_at=datetime.now(UTC),
        archived_at=datetime.now(UTC),
    )
    if overrides:
        for key, value in overrides.items():
            setattr(archive, key, value)
    return archive


def _make_model(archive: StrategicArchive | None = None) -> ArchiveModel:
    """创建测试用 ArchiveModel"""
    if archive is None:
        archive = _make_archive()
    return ArchiveModel(
        archive_id=archive.archive_id,
        plan_id=archive.plan_id,
        plan_type=archive.plan_type,
        archive_type=archive.archive_type.value if archive.archive_type else "assumption",
        assumptions=archive.assumptions,
        decision_basis=archive.decision_basis,
        execution_deviation=archive.execution_deviation,
        metadata_ref=archive.metadata_ref,
        embedding_ref=archive.embedding_ref,
        blob_ref=archive.blob_ref,
        graph_ref=archive.graph_ref,
        created_by=archive.created_by,
        version=archive.version,
        deleted_at=archive.deleted_at,
        created_at=archive.created_at,
        archived_at=archive.archived_at,
    )


class TestConversion:
    """实体/模型转换测试"""

    def test_to_entity(self, repository: PostgreSQLArchiveRepository) -> None:
        """ORM 模型转领域实体"""
        archive = _make_archive()
        model = _make_model(archive)
        entity = repository._to_entity(model)
        assert entity.archive_id == archive.archive_id
        assert entity.plan_id == archive.plan_id
        assert entity.archive_type == archive.archive_type
        assert entity.assumptions == archive.assumptions
        assert entity.metadata_ref == archive.metadata_ref

    def test_to_model(self, repository: PostgreSQLArchiveRepository) -> None:
        """领域实体转 ORM 模型"""
        archive = _make_archive()
        model = repository._to_model(archive)
        assert model.archive_id == archive.archive_id
        assert model.plan_type == archive.plan_type
        assert model.archive_type == archive.archive_type.value
        assert model.assumptions == archive.assumptions
        assert model.metadata_ref == archive.metadata_ref


class TestSave:
    """save() 测试"""

    @pytest.mark.asyncio
    async def test_save_executes_merge(self, repository: PostgreSQLArchiveRepository) -> None:
        """save 调用 _do_save"""
        archive = _make_archive()
        with patch.object(repository, "_do_save", new_callable=AsyncMock) as mock_save:
            mock_save.return_value = None
            result = await repository.save(archive)
            assert result is not None


class TestFind:
    """find() 测试"""

    @pytest.mark.asyncio
    async def test_find_by_archive_type(self, repository: PostgreSQLArchiveRepository) -> None:
        """按 archive_type 查询"""
        query = ArchiveQuery(archive_type=ArchiveType.ASSUMPTION)
        assert query.archive_type == ArchiveType.ASSUMPTION

    @pytest.mark.asyncio
    async def test_find_by_plan_id(self, repository: PostgreSQLArchiveRepository) -> None:
        """按 plan_id 查询"""
        plan_id = uuid.uuid4()
        query = ArchiveQuery(plan_id=plan_id)
        assert query.plan_id == plan_id

    @pytest.mark.asyncio
    async def test_find_with_pagination(self, repository: PostgreSQLArchiveRepository) -> None:
        """分页查询"""
        query = ArchiveQuery(offset=10, limit=50)
        assert query.offset == 10
        assert query.limit == 50

    @pytest.mark.asyncio
    async def test_find_date_range(self, repository: PostgreSQLArchiveRepository) -> None:
        """时间范围查询"""
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 12, 31, tzinfo=UTC)
        query = ArchiveQuery(start_date=start, end_date=end)
        assert query.start_date == start
        assert query.end_date == end

    @pytest.mark.asyncio
    async def test_find_empty_result(self, repository: PostgreSQLArchiveRepository) -> None:
        """无结果返回空列表"""
        query = ArchiveQuery(archive_type=ArchiveType.EVIDENCE_PACKAGE)
        assert query.archive_type == ArchiveType.EVIDENCE_PACKAGE


class TestListByPlan:
    """list_by_plan() 测试"""

    @pytest.mark.asyncio
    async def test_list_by_plan_returns_empty_on_no_data(self, repository: PostgreSQLArchiveRepository) -> None:
        """无数据时返回空列表"""
        from src.infrastructure.storage.postgresql.session_context import with_session

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        async with with_session(mock_session):
            result = await repository.list_by_plan(uuid.uuid4())
        assert result == []


class TestListByArchiveType:
    """list_by_archive_type() 测试"""

    @pytest.mark.asyncio
    async def test_list_by_type_returns_empty_on_no_data(self, repository: PostgreSQLArchiveRepository) -> None:
        """无数据时返回空列表"""
        from src.infrastructure.storage.postgresql.session_context import with_session

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        async with with_session(mock_session):
            result = await repository.list_by_archive_type(ArchiveType.ASSUMPTION)
        assert result == []


class TestArchiveQuery:
    """ArchiveQuery 值对象测试"""

    def test_limit_default(self) -> None:
        """默认 limit 为 20"""
        query = ArchiveQuery()
        assert query.limit == 20

    def test_limit_clamps_to_min(self) -> None:
        """limit 最小为 1"""
        query = ArchiveQuery(limit=0)
        assert query.limit == 1

    def test_limit_clamps_to_max(self) -> None:
        """limit 最大为 1000"""
        query = ArchiveQuery(limit=2000)
        assert query.limit == 1000

    def test_frozen(self) -> None:
        """frozen dataclass 不可变"""
        query = ArchiveQuery()
        with pytest.raises(AttributeError):
            setattr(query, "plan_id", uuid.uuid4())

    def test_all_fields(self) -> None:
        """所有字段赋值"""
        plan_id = uuid.uuid4()
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 12, 31, tzinfo=UTC)
        query = ArchiveQuery(
            plan_id=plan_id,
            archive_type=ArchiveType.DECISION,
            plan_type="SP",
            start_date=start,
            end_date=end,
            offset=5,
            limit=30,
        )
        assert query.plan_id == plan_id
        assert query.archive_type == ArchiveType.DECISION
        assert query.plan_type == "SP"
        assert query.start_date == start
        assert query.end_date == end
        assert query.offset == 5
        assert query.limit == 30


class TestArchiveModelValidity:
    """ArchiveModel valid_from/valid_until 列测试"""

    def test_validity_columns(self, repository: PostgreSQLArchiveRepository) -> None:
        """ArchiveModel 包含 valid_from/valid_until 列"""

        archive = _make_archive()
        now = datetime.now(UTC)
        model = repository._to_model(archive)
        model.valid_from = now
        model.valid_until = datetime(2027, 12, 31, tzinfo=UTC)
        assert model.valid_from == now
        assert model.valid_until == datetime(2027, 12, 31, tzinfo=UTC)

    def test_to_entity_with_validity(self, repository: PostgreSQLArchiveRepository) -> None:
        """_to_entity 转换包含有效期字段"""

        now = datetime.now(UTC)
        archive = _make_archive({"valid_from": now, "valid_until": datetime(2027, 12, 31, tzinfo=UTC)})
        model = repository._to_model(archive)
        entity = repository._to_entity(model)
        assert entity.valid_from == now
        assert entity.valid_until == datetime(2027, 12, 31, tzinfo=UTC)

    def test_to_model_with_validity(self, repository: PostgreSQLArchiveRepository) -> None:
        """_to_model 转换包含有效期字段"""
        now = datetime.now(UTC)
        archive = _make_archive({"valid_from": now, "valid_until": datetime(2027, 12, 31, tzinfo=UTC)})
        model = repository._to_model(archive)
        assert model.valid_from == now
        assert model.valid_until == datetime(2027, 12, 31, tzinfo=UTC)


class TestStalenessFilter:
    """_apply_filters staleness_status 过滤测试（Story 3.12 AC-6）"""

    def test_staleness_status_stale(self, repository: PostgreSQLArchiveRepository) -> None:
        """staleness_status='stale' 生成 metadata_['staleness'] == 'stale' 过滤"""
        from sqlalchemy import select

        from src.infrastructure.storage.postgresql.models.archive import ArchiveModel

        query = ArchiveQuery(staleness_status="stale")
        stmt = select(ArchiveModel)
        stmt = repository._apply_filters(stmt, query)
        sql = str(stmt)
        # 生成 `.astext == 'stale'` 表达式：metadata ->> (JSONB text 提取) = 'stale'
        assert "metadata ->>" in sql
        assert "=" in sql

    def test_staleness_status_fresh(self, repository: PostgreSQLArchiveRepository) -> None:
        """staleness_status='fresh' 生成 .astext.is_distinct_from('stale') 过滤"""
        from sqlalchemy import select

        from src.infrastructure.storage.postgresql.models.archive import ArchiveModel

        query = ArchiveQuery(staleness_status="fresh")
        stmt = select(ArchiveModel)
        stmt = repository._apply_filters(stmt, query)
        sql = str(stmt)
        # 生成 .astext.is_distinct_from('stale') 表达式
        assert "IS DISTINCT FROM" in sql

    def test_staleness_status_none_no_filter(self, repository: PostgreSQLArchiveRepository) -> None:
        """staleness_status=None 不生成过滤条件"""
        from sqlalchemy import select

        from src.infrastructure.storage.postgresql.models.archive import ArchiveModel

        query = ArchiveQuery()
        stmt = select(ArchiveModel)
        stmt = repository._apply_filters(stmt, query)
        sql = str(stmt)
        # 不包含 staleness 过滤
        assert "staleness" not in sql

    def test_archive_ids_filter(self, repository: PostgreSQLArchiveRepository) -> None:
        """archive_ids 生成 .archive_id.in_(...) 过滤"""
        from sqlalchemy import select

        from src.infrastructure.storage.postgresql.models.archive import ArchiveModel

        ids = [uuid.uuid4(), uuid.uuid4()]
        query = ArchiveQuery(archive_ids=ids)
        stmt = select(ArchiveModel)
        stmt = repository._apply_filters(stmt, query)
        sql = str(stmt)
        assert "archive_id" in sql
        assert "IN" in sql.upper()
