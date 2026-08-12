"""PostgreSQLDomainDictionaryRepository 单元测试

使用 mock AsyncSession 验证 CRUD、乐观锁、快照、回滚逻辑。
（真实 PG 集成验证见 tests/integration/test_integration_domain_dictionary.py）
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from src.domain.exceptions import (
    DictionaryEntryConflictError,
    DictionaryNotFoundError,
    DictionaryVersionConflictError,
)
from src.domain.ports.domain_dictionary import (
    DictionaryEntry,
    DictionaryQuery,
)
from src.infrastructure.storage.postgresql.models.dictionary import (
    DictionaryEntryModel,
    DictionarySnapshotModel,
)
from src.infrastructure.storage.postgresql.repository.domain_dictionary_repository import (
    PostgreSQLDomainDictionaryRepository,
)
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


def run_async(coro):
    """同步运行 async 协程"""
    return asyncio.run(coro)


class _MockResult:
    """Mock SQLAlchemy execute result"""

    def __init__(self, scalar_one_or_none=None, scalars_all=None, rowcount=1):
        self._scalar_one_or_none = scalar_one_or_none
        self._scalars_all = scalars_all or []
        self.rowcount = rowcount

    def scalar_one_or_none(self):
        return self._scalar_one_or_none

    def scalar_one(self):
        return self._scalar_one_or_none

    def scalars(self):
        return _MockScalars(self._scalars_all)


class _MockScalars:
    """Mock scalars result"""

    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


def _make_model(term="BLM", entity_type="CONCEPT") -> DictionaryEntryModel:
    """创建测试用 DictionaryEntryModel"""
    return DictionaryEntryModel(
        term=term,
        entity_type=entity_type,
        category="strategy",
        active=True,
        version=1,
        created_by="admin",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_session():
    """创建 mock AsyncSession"""
    session = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    # begin_nested 返回支持异步上下文管理协议的对象（savepoint）
    session.begin_nested = MagicMock()
    session.begin_nested.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin_nested.return_value.__aexit__ = AsyncMock(return_value=None)
    return session


@pytest.fixture
def repo(mock_session):
    """创建仓储实例并绑定 session"""
    token = set_session(mock_session)
    yield PostgreSQLDomainDictionaryRepository()
    reset_session(token)


def _run(coro):
    """运行 async 测试协程"""
    return asyncio.run(coro)


# ===================================================================
# CRUD
# ===================================================================


class TestAddEntry:
    """添加词条测试"""

    def test_add_entry_success(self, repo, mock_session):
        """添加词条成功"""
        entry = DictionaryEntry(term="BLM", entity_type="CONCEPT")
        mock_session.flush.return_value = None

        result = _run(repo.add_entry(entry))

        assert result.term == "BLM"
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    def test_add_entry_conflict(self, repo, mock_session):
        """添加已存在词条 -> 抛 DictionaryEntryConflictError"""
        entry = DictionaryEntry(term="BLM", entity_type="CONCEPT")
        mock_session.flush.side_effect = IntegrityError(
            "statement",
            {},
            Exception("duplicate key value violates unique constraint dictionary_entries_pkey"),
        )

        with pytest.raises(DictionaryEntryConflictError):
            _run(repo.add_entry(entry))


class TestGetEntry:
    """查询词条测试"""

    def test_get_entry_found(self, repo, mock_session):
        """查询存在的词条"""
        model = _make_model()
        mock_session.execute.return_value = _MockResult(scalar_one_or_none=model)

        result = _run(repo.get_entry("BLM"))

        assert result is not None
        assert result.term == "BLM"
        assert result.entity_type == "CONCEPT"

    def test_get_entry_not_found(self, repo, mock_session):
        """查询不存在的词条 -> None"""
        mock_session.execute.return_value = _MockResult(scalar_one_or_none=None)

        result = _run(repo.get_entry("不存在的词"))

        assert result is None


class TestUpdateEntry:
    """修改词条测试"""

    def test_update_entry_success(self, repo, mock_session):
        """修改词条成功，版本递增"""
        entry = DictionaryEntry(term="BLM", entity_type="STRATEGY", version=1)
        updated_model = _make_model(term="BLM", entity_type="STRATEGY")
        updated_model.version = 2

        # 第一次 execute 返回 rowcount=1 (UPDATE)，第二次返回更新后的模型
        mock_session.execute.side_effect = [
            _MockResult(rowcount=1),  # UPDATE 结果
            _MockResult(scalar_one_or_none=updated_model),  # 重新查询
        ]

        result = _run(repo.update_entry("BLM", entry))

        assert result.entity_type == "STRATEGY"
        assert result.version == 2

    def test_update_entry_not_found(self, repo, mock_session):
        """修改不存在的词条 -> 抛 DictionaryNotFoundError"""
        entry = DictionaryEntry(term="不存在的词", entity_type="CONCEPT", version=1)
        # 第一次 execute UPDATE rowcount=0，第二次查询返回 None
        mock_session.execute.side_effect = [
            _MockResult(rowcount=0),
            _MockResult(scalar_one_or_none=None),
        ]

        with pytest.raises(DictionaryNotFoundError):
            _run(repo.update_entry("不存在的词", entry))

    def test_update_entry_version_conflict(self, repo, mock_session):
        """版本不匹配 -> 抛 DictionaryVersionConflictError"""
        entry = DictionaryEntry(term="BLM", entity_type="CONCEPT", version=2)
        existing_model = _make_model(term="BLM", entity_type="CONCEPT")
        existing_model.version = 1

        # 第一次 execute UPDATE rowcount=0，第二次查询返回版本1的模型
        mock_session.execute.side_effect = [
            _MockResult(rowcount=0),
            _MockResult(scalar_one_or_none=existing_model),
        ]

        with pytest.raises(DictionaryVersionConflictError):
            _run(repo.update_entry("BLM", entry))


class TestDeleteEntry:
    """删除词条测试"""

    def test_delete_entry_success(self, repo, mock_session):
        """删除存在的词条"""
        model = _make_model()
        mock_session.execute.return_value = _MockResult(scalar_one_or_none=model)

        _run(repo.delete_entry("BLM"))

        mock_session.delete.assert_called_once()

    def test_delete_entry_not_found(self, repo, mock_session):
        """删除不存在的词条 -> 抛 DictionaryNotFoundError"""
        mock_session.execute.return_value = _MockResult(scalar_one_or_none=None)

        with pytest.raises(DictionaryNotFoundError):
            _run(repo.delete_entry("不存在的词"))


class TestListEntries:
    """列表词条测试"""

    def test_list_entries_success(self, repo, mock_session):
        """列出词条"""
        models = [_make_model(term="BLM"), _make_model(term="SWOT", entity_type="CONCEPT")]
        mock_session.execute.return_value = _MockResult(scalars_all=models)

        query = DictionaryQuery()
        result = _run(repo.list_entries(query))

        assert len(result) == 2
        assert result[0].term == "BLM"
        assert result[1].term == "SWOT"


class TestGetActiveDictionary:
    """获取活动词典测试"""

    def test_get_active_dictionary(self, repo, mock_session):
        """获取活动词典 (term, entity_type)"""
        models = [_make_model(term="BLM"), _make_model(term="SWOT", entity_type="CONCEPT")]
        mock_session.execute.return_value = _MockResult(scalars_all=models)

        result = _run(repo.get_active_dictionary())

        assert result == [("BLM", "CONCEPT"), ("SWOT", "CONCEPT")]


class TestCreateSnapshot:
    """创建快照测试"""

    def test_create_snapshot_success(self, repo, mock_session):
        """创建快照"""
        entries = [_make_model(term="BLM")]
        # 变量赋值给 _ 表示有意不使用（变量仅用于触发 mock 行为验证）
        _ = DictionarySnapshotModel(
            version=1,
            entries={"BLM": {"term": "BLM", "entity_type": "CONCEPT"}},
            created_by="admin",
            created_at=datetime.now(UTC),
            change_summary={"total_entries": 1},
        )

        # 第一次 execute 查询词条，第二次查询最新快照，第三次 flush
        mock_session.execute.side_effect = [
            _MockResult(scalars_all=entries),  # 所有词条
            _MockResult(scalar_one_or_none=None),  # 无最新快照
        ]

        result = _run(repo.create_snapshot("admin"))

        assert result is not None
        assert result.version == 1
        assert result.snapshot_id != ""
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited()


class TestRollback:
    """回滚测试"""

    def test_rollback_snapshot_not_found(self, repo, mock_session):
        """回滚到不存在的版本 -> 抛 DictionaryNotFoundError"""
        mock_session.execute.return_value = _MockResult(scalar_one_or_none=None)

        with pytest.raises(DictionaryNotFoundError):
            _run(repo.rollback(99))

    def test_rollback_success(self, repo, mock_session):
        """回滚成功"""
        snapshot_model = DictionarySnapshotModel(
            version=1,
            entries={
                "BLM": {"term": "BLM", "entity_type": "CONCEPT", "category": "strategy", "active": True, "version": 1},
            },
            created_by="admin",
            created_at=datetime.now(UTC),
            change_summary={},
        )
        # 第一次 execute 查询目标快照，第二次查询现有词条（返回空）
        mock_session.execute.side_effect = [
            _MockResult(scalar_one_or_none=snapshot_model),
            _MockResult(scalars_all=[]),  # 无现有词条
        ]

        _run(repo.rollback(1))

        mock_session.add.assert_called()
        mock_session.flush.assert_awaited()


class TestListSnapshots:
    """列出快照测试"""

    def test_list_snapshots(self, repo, mock_session):
        """列出快照"""
        models = [
            DictionarySnapshotModel(
                version=2,
                entries={"BLM": {"term": "BLM"}},
                created_by="admin",
                created_at=datetime.now(UTC),
                change_summary={"total_entries": 1},
            ),
            DictionarySnapshotModel(
                version=1,
                entries={"SWOT": {"term": "SWOT"}},
                created_by="admin",
                created_at=datetime.now(UTC),
                change_summary={},
            ),
        ]
        mock_session.execute.return_value = _MockResult(scalars_all=models)

        result = _run(repo.list_snapshots())

        assert len(result) == 2
        assert result[0].version == 2
        assert result[1].version == 1
