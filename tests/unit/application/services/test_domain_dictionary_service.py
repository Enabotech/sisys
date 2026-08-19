"""DomainDictionaryService 单元测试

测试 CRUD 编排、热更新、快照/回滚、事件发布。
使用 mock 的 DomainDictionaryPort、DictionaryConsumerPort、event_publisher。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import (
    DictionaryNotFoundError,
)
from src.domain.ports.domain_dictionary import (
    DictionaryConsumerPort,
    DictionaryEntry,
    DictionaryQuery,
    DictionarySnapshot,
    DomainDictionaryPort,
)

# ===================================================================
# Mock Factories
# ===================================================================


def _make_mock_repo(**kwargs: object) -> MagicMock:
    """创建 mock DomainDictionaryPort"""
    repo = MagicMock(spec=DomainDictionaryPort)
    repo.list_entries = AsyncMock(**kwargs)
    repo.get_entry = AsyncMock(**kwargs)
    repo.add_entry = AsyncMock(**kwargs)
    repo.update_entry = AsyncMock(**kwargs)
    repo.delete_entry = AsyncMock(**kwargs)
    repo.get_active_dictionary = AsyncMock(**kwargs)
    repo.create_snapshot = AsyncMock(**kwargs)
    repo.rollback = AsyncMock(**kwargs)
    repo.list_snapshots = AsyncMock(**kwargs)
    repo.count_entries = AsyncMock(**kwargs)
    return repo


def _make_mock_consumer() -> MagicMock:
    """创建 mock DictionaryConsumerPort"""
    consumer = MagicMock(spec=DictionaryConsumerPort)
    consumer.reload_dictionary = MagicMock()
    return consumer


def _make_mock_publisher() -> AsyncMock:
    """创建 mock event publisher"""
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    return publisher


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def mock_repo():
    return _make_mock_repo()


@pytest.fixture
def mock_consumer():
    return _make_mock_consumer()


@pytest.fixture
def mock_publisher():
    return _make_mock_publisher()


@pytest.fixture
def service(mock_repo, mock_consumer, mock_publisher):
    from src.application.services.domain_dictionary_service import DomainDictionaryService

    return DomainDictionaryService(
        dictionary_repo=mock_repo,
        dictionary_consumer=mock_consumer,
        event_publisher=mock_publisher,
    )


# ===================================================================
# Tests: add_entry
# ===================================================================


class TestAddEntry:
    """添加词条测试"""

    async def test_happy_path(self, service, mock_repo, mock_publisher):
        """添加词条 -> 调用 repo.add_entry + 发布事件"""
        entry = DictionaryEntry(term="BLM", entity_type="CONCEPT")
        saved_entry = DictionaryEntry(term="BLM", entity_type="CONCEPT", version=1)
        mock_repo.add_entry.return_value = saved_entry

        result = await service.add_entry(entry, trigger="api")

        assert result.term == "BLM"
        mock_repo.add_entry.assert_awaited_once_with(entry)
        mock_publisher.publish.assert_awaited_once()
        # 验证事件类型
        event = mock_publisher.publish.await_args.args[0]
        assert event.event_type == "DictionaryUpdated"
        assert event.action == "add"
        assert event.term == "BLM"

    async def test_event_publish_failure_logs_error(self, service, mock_repo, mock_publisher):
        """事件发布失败仅记录日志，不阻止返回"""
        entry = DictionaryEntry(term="BLM", entity_type="CONCEPT")
        mock_repo.add_entry.return_value = entry
        mock_publisher.publish.side_effect = Exception("publish failed")

        with patch("src.application.services.domain_dictionary_service.logger") as mock_logger:
            result = await service.add_entry(entry, trigger="api")
            assert result.term == "BLM"
            mock_logger.warning.assert_called()

    async def test_empty_term_raises_error(self, service, mock_repo):
        """空词条在值对象层校验，不会到达服务"""
        with pytest.raises(Exception):
            DictionaryEntry(term="", entity_type="CONCEPT")


# ===================================================================
# Tests: update_entry
# ===================================================================


class TestUpdateEntry:
    """修改词条测试"""

    async def test_happy_path(self, service, mock_repo, mock_publisher):
        """修改词条 -> 调用 repo.update_entry + 发布事件"""
        updated = DictionaryEntry(term="BLM", entity_type="STRATEGY", version=2)
        mock_repo.update_entry.return_value = updated

        result = await service.update_entry("BLM", updated, trigger="api")

        assert result.entity_type == "STRATEGY"
        mock_repo.update_entry.assert_awaited_once()
        mock_publisher.publish.assert_awaited_once()

    async def test_not_found_raises(self, service, mock_repo):
        """词条不存在 -> 抛 DictionaryNotFoundError"""
        from src.domain.exceptions import DictionaryNotFoundError

        mock_repo.update_entry.side_effect = DictionaryNotFoundError(term="不存在的词")

        with pytest.raises(DictionaryNotFoundError):
            entry = DictionaryEntry(term="不存在的词", entity_type="CONCEPT")
            await service.update_entry("不存在的词", entry, trigger="api")


# ===================================================================
# Tests: delete_entry
# ===================================================================


class TestDeleteEntry:
    """删除词条测试"""

    async def test_happy_path(self, service, mock_repo, mock_publisher):
        """删除词条 -> 调用 repo.delete_entry + 发布事件"""
        mock_repo.get_entry.return_value = DictionaryEntry(term="BLM", entity_type="CONCEPT")

        await service.delete_entry("BLM", trigger="api")

        mock_repo.delete_entry.assert_awaited_once_with("BLM")
        mock_publisher.publish.assert_awaited_once()

    async def test_not_found_raises(self, service, mock_repo):
        """词条不存在 -> 仓储层抛 DictionaryNotFoundError（应用层透传）"""
        from src.domain.exceptions import DictionaryNotFoundError

        mock_repo.delete_entry.side_effect = DictionaryNotFoundError(term="不存在的词")

        with pytest.raises(DictionaryNotFoundError):
            await service.delete_entry("不存在的词", trigger="api")


# ===================================================================
# Tests: refresh_dictionary
# ===================================================================


class TestRefreshDictionary:
    """热更新测试"""

    async def test_happy_path(self, service, mock_repo, mock_consumer):
        """refresh_dictionary -> 读取活动词典 -> 调用 consumer.reload_dictionary"""
        active_dict = [("BLM", "CONCEPT"), ("SWOT", "CONCEPT")]
        mock_repo.get_active_dictionary.return_value = active_dict

        await service.refresh_dictionary()

        mock_repo.get_active_dictionary.assert_awaited_once()
        mock_consumer.reload_dictionary.assert_called_once_with(active_dict)

    async def test_empty_dictionary(self, service, mock_repo, mock_consumer):
        """空词典也正确传递"""
        mock_repo.get_active_dictionary.return_value = []

        await service.refresh_dictionary()

        mock_consumer.reload_dictionary.assert_called_once_with([])


# ===================================================================
# Tests: create_snapshot
# ===================================================================


class TestCreateSnapshot:
    """创建快照测试"""

    async def test_happy_path(self, service, mock_repo):
        """create_snapshot -> 委托 repo.create_snapshot"""
        snapshot = DictionarySnapshot(
            snapshot_id="snap-001",
            version=1,
            entries=(),
            created_by="admin",
            created_at="2026-01-01T00:00:00",
        )
        mock_repo.create_snapshot.return_value = snapshot

        result = await service.create_snapshot("admin")

        assert result.snapshot_id == "snap-001"
        assert result.version == 1
        mock_repo.create_snapshot.assert_awaited_once_with("admin")


# ===================================================================
# Tests: rollback
# ===================================================================


class TestRollback:
    """回滚测试"""

    async def test_happy_path(self, service, mock_repo, mock_consumer, mock_publisher):
        """回滚 -> 委托 repo.rollback + 刷新 + 发布事件"""
        await service.rollback(version=1, trigger="api")

        mock_repo.rollback.assert_awaited_once_with(1)
        mock_repo.get_active_dictionary.assert_awaited()
        mock_consumer.reload_dictionary.assert_called_once()
        mock_publisher.publish.assert_awaited_once()

    async def test_rollback_not_found(self, service, mock_repo):
        """回滚到不存在的版本 -> 抛 DictionaryNotFoundError"""
        mock_repo.rollback.side_effect = DictionaryNotFoundError(version=99)

        with pytest.raises(DictionaryNotFoundError):
            await service.rollback(version=99, trigger="api")


# ===================================================================
# Tests: list_entries / get_entry
# ===================================================================


class TestListEntries:
    """列表词条测试"""

    async def test_happy_path(self, service, mock_repo):
        """list_entries -> 委托 repo.list_entries"""
        query = DictionaryQuery(category="strategy")
        entries = [DictionaryEntry(term="BLM", entity_type="CONCEPT")]
        mock_repo.list_entries.return_value = entries

        result = await service.list_entries(query)

        assert len(result) == 1
        assert result[0].term == "BLM"
        mock_repo.list_entries.assert_awaited_once_with(query)


class TestGetEntry:
    """查询词条测试"""

    async def test_happy_path(self, service, mock_repo):
        """get_entry -> 委托 repo.get_entry"""
        entry = DictionaryEntry(term="BLM", entity_type="CONCEPT")
        mock_repo.get_entry.return_value = entry

        result = await service.get_entry("BLM")

        assert result is not None
        assert result.term == "BLM"
        mock_repo.get_entry.assert_awaited_once_with("BLM")

    async def test_not_found(self, service, mock_repo):
        """不存在返回 None"""
        mock_repo.get_entry.return_value = None

        result = await service.get_entry("不存在的词")
        assert result is None
