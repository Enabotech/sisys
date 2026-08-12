"""领域词典端口与值对象单元测试

测试 DomainDictionaryPort、DictionaryConsumerPort 协议以及
DictionaryEntry、DictionaryQuery、DictionarySnapshot 值对象。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pytest

from src.domain.ports.domain_dictionary import (
    DictionaryConsumerPort,
    DictionaryEntry,
    DictionaryQuery,
    DictionarySnapshot,
    DomainDictionaryPort,
)


class TestDictionaryEntry:
    """DictionaryEntry 值对象测试"""

    def test_required_field_term(self):
        """term 是必填字段"""
        entry = DictionaryEntry(term="BLM", entity_type="CONCEPT")
        assert entry.term == "BLM"
        assert entry.entity_type == "CONCEPT"

    def test_default_values(self):
        """默认值正确"""
        entry = DictionaryEntry(term="BLM", entity_type="CONCEPT")
        assert entry.category == "general"
        assert entry.active is True
        assert entry.version == 1
        assert entry.created_by == ""
        assert entry.created_at == ""
        assert entry.updated_at == ""

    def test_frozen_dataclass(self):
        """frozen dataclass 不可变"""
        entry = DictionaryEntry(term="BLM", entity_type="CONCEPT")
        with pytest.raises(AttributeError):
            entry.term = "SWOT"  # type: ignore[misc]

    def test_term_empty_raises_validation_error(self):
        """term 为空字符串时抛 EntityValidationError"""
        from src.domain.exceptions import EntityValidationError

        with pytest.raises(EntityValidationError, match="term must not be empty"):
            DictionaryEntry(term="", entity_type="CONCEPT")

    def test_term_whitespace_raises_validation_error(self):
        """term 为空白字符串时抛 EntityValidationError"""
        from src.domain.exceptions import EntityValidationError

        with pytest.raises(EntityValidationError):
            DictionaryEntry(term="   ", entity_type="CONCEPT")

    def test_equality(self):
        """相同字段值的两个实例相等"""
        e1 = DictionaryEntry(term="BLM", entity_type="CONCEPT")
        e2 = DictionaryEntry(term="BLM", entity_type="CONCEPT")
        assert e1 == e2

    def test_repr(self):
        """repr 包含关键字段"""
        entry = DictionaryEntry(term="BLM", entity_type="CONCEPT")
        rep = repr(entry)
        assert "BLM" in rep
        assert "CONCEPT" in rep


class TestDictionaryQuery:
    """DictionaryQuery 值对象测试"""

    def test_default_values(self):
        """默认值正确"""
        query = DictionaryQuery()
        assert query.category is None
        assert query.entity_type is None
        assert query.active_only is True
        assert query.page == 1
        assert query.page_size == 50

    def test_frozen_dataclass(self):
        """frozen dataclass 不可变"""
        query = DictionaryQuery()
        with pytest.raises(AttributeError):
            query.page = 2  # type: ignore[misc]

    def test_page_size_clamped_to_100(self):
        """page_size 超过 100 时抛 EntityValidationError"""
        from src.domain.exceptions import EntityValidationError

        with pytest.raises(EntityValidationError, match="page_size must not exceed 100"):
            DictionaryQuery(page_size=200)

    def test_page_less_than_1_raises_error(self):
        """page 小于 1 时抛 EntityValidationError"""
        from src.domain.exceptions import EntityValidationError

        with pytest.raises(EntityValidationError, match="page must be >= 1"):
            DictionaryQuery(page=0)

    def test_page_size_zero_raises_error(self):
        """page_size 为 0 时抛 EntityValidationError"""
        from src.domain.exceptions import EntityValidationError

        with pytest.raises(EntityValidationError):
            DictionaryQuery(page_size=0)

    def test_page_size_100_is_valid(self):
        """page_size 恰好为 100 时合法"""
        query = DictionaryQuery(page_size=100)
        assert query.page_size == 100

    def test_equality(self):
        """相同字段值的两个实例相等"""
        q1 = DictionaryQuery(category="strategy", page=2)
        q2 = DictionaryQuery(category="strategy", page=2)
        assert q1 == q2


class TestDictionarySnapshot:
    """DictionarySnapshot 值对象测试"""

    def test_required_fields(self):
        """snapshot_id 和 version 和 entries 是必填字段"""
        entry = DictionaryEntry(term="BLM", entity_type="CONCEPT")
        snapshot = DictionarySnapshot(
            snapshot_id="snap-001",
            version=1,
            entries=(entry,),
        )
        assert snapshot.snapshot_id == "snap-001"
        assert snapshot.version == 1
        assert len(snapshot.entries) == 1
        assert snapshot.entries[0].term == "BLM"

    def test_default_values(self):
        """默认值正确"""
        snapshot = DictionarySnapshot(
            snapshot_id="snap-001",
            version=1,
            entries=(),
        )
        assert snapshot.created_by == ""
        assert snapshot.created_at == ""
        assert snapshot.change_summary == {}

    def test_frozen_dataclass(self):
        """frozen dataclass 不可变"""
        snapshot = DictionarySnapshot(snapshot_id="snap-001", version=1, entries=())
        with pytest.raises(AttributeError):
            snapshot.version = 2  # type: ignore[misc]

    def test_entries_tuple(self):
        """entries 是 tuple 类型"""
        entry = DictionaryEntry(term="BLM", entity_type="CONCEPT")
        snapshot = DictionarySnapshot(
            snapshot_id="snap-001",
            version=1,
            entries=(entry,),
        )
        assert isinstance(snapshot.entries, tuple)


class TestDomainDictionaryPort:
    """DomainDictionaryPort 协议结构测试"""

    def test_is_protocol(self):
        """DomainDictionaryPort 是 typing.Protocol"""
        assert issubclass(DomainDictionaryPort, Protocol)

    def test_is_runtime_checkable(self):
        """DomainDictionaryPort 是 @runtime_checkable"""
        assert hasattr(DomainDictionaryPort, "__instancecheck__")

    def test_protocol_methods_exist(self):
        """协议方法签名正确"""
        # list_entries
        assert hasattr(DomainDictionaryPort, "list_entries")
        # get_entry
        assert hasattr(DomainDictionaryPort, "get_entry")
        # add_entry
        assert hasattr(DomainDictionaryPort, "add_entry")
        # update_entry
        assert hasattr(DomainDictionaryPort, "update_entry")
        # delete_entry
        assert hasattr(DomainDictionaryPort, "delete_entry")
        # get_active_dictionary
        assert hasattr(DomainDictionaryPort, "get_active_dictionary")
        # create_snapshot
        assert hasattr(DomainDictionaryPort, "create_snapshot")
        # rollback
        assert hasattr(DomainDictionaryPort, "rollback")
        # list_snapshots
        assert hasattr(DomainDictionaryPort, "list_snapshots")
        # count_entries
        assert hasattr(DomainDictionaryPort, "count_entries")


class TestConcreteDomainDictionaryPort:
    """验证具体实现类可被 runtime_checkable 识别"""

    def test_concrete_implementation_isinstance(self):
        """具体实现类可通过 isinstance 检查"""
        # 使用 @runtime_checkable 验证

        @dataclass
        class FakeRepo:
            async def list_entries(self, query):  # type: ignore[no-untyped-def]
                return []

            async def get_entry(self, term: str) -> DictionaryEntry | None:
                return None

            async def add_entry(self, entry):  # type: ignore[no-untyped-def]
                return entry

            async def update_entry(self, term, entry):  # type: ignore[no-untyped-def]
                return entry

            async def delete_entry(self, term: str) -> None:
                pass

            async def get_active_dictionary(self) -> list[tuple[str, str]]:
                return []

            async def create_snapshot(self, created_by: str):  # type: ignore[no-untyped-def]
                return DictionarySnapshot(snapshot_id="s1", version=1, entries=())

            async def rollback(self, version: int) -> None:
                pass

            async def list_snapshots(self):  # type: ignore[no-untyped-def]
                return []

            async def count_entries(self, query):  # type: ignore[no-untyped-def]
                return 0

        repo = FakeRepo()
        assert isinstance(repo, DomainDictionaryPort)


class TestDictionaryConsumerPort:
    """DictionaryConsumerPort 协议结构测试"""

    def test_is_protocol(self):
        """DictionaryConsumerPort 是 typing.Protocol"""
        assert issubclass(DictionaryConsumerPort, Protocol)

    def test_has_reload_dictionary_method(self):
        """协议包含 reload_dictionary 方法"""
        assert hasattr(DictionaryConsumerPort, "reload_dictionary")

    def test_reload_dictionary_signature(self):
        """reload_dictionary 方法签名正确"""
        import inspect

        sig = inspect.signature(DictionaryConsumerPort.reload_dictionary)
        params = list(sig.parameters.values())
        assert len(params) >= 2  # self + dictionary
        param_names = [p.name for p in params]
        assert "dictionary" in param_names

    def test_is_runtime_checkable(self):
        """DictionaryConsumerPort 是 @runtime_checkable"""
        assert hasattr(DictionaryConsumerPort, "__instancecheck__")

    def test_concrete_implementation_isinstance(self):
        """具体实现类可通过 isinstance 检查"""

        class FakeConsumer:
            def reload_dictionary(self, dictionary: list[tuple[str, str]]) -> None:
                pass

        consumer = FakeConsumer()
        assert isinstance(consumer, DictionaryConsumerPort)
