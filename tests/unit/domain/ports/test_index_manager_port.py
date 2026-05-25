"""Test IndexManagerPort - Protocol Interface Tests."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

from src.domain.ports.index_manager import IndexManagerPort


class TestIndexManagerPortSignature:
    """Structural signature tests — verify async contract."""

    def test_all_methods_are_async(self) -> None:
        """All methods should be async."""
        for method_name in ["update_entry", "remove_entry", "read_entries", "search", "truncate"]:
            method = getattr(IndexManagerPort, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} must be async"


class TestIndexManagerPortMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec约束."""

    async def test_mock_update_entry_verified(self):
        """Mock update_entry should be verifiable."""
        mock = AsyncMock(spec=IndexManagerPort)
        mock.update_entry.return_value = None

        await mock.update_entry({"memory_id": "id-1", "name": "test"})
        mock.update_entry.assert_called_once()

    async def test_mock_remove_entry_verified(self):
        """Mock remove_entry should be verifiable."""
        mock = AsyncMock(spec=IndexManagerPort)
        mock.remove_entry.return_value = None

        await mock.remove_entry("memory-id-123")
        mock.remove_entry.assert_called_once_with("memory-id-123")

    async def test_mock_read_entries_verified(self):
        """Mock read_entries should be verifiable."""
        mock = AsyncMock(spec=IndexManagerPort)
        mock.read_entries.return_value = [{"memory_id": "id-1", "name": "test"}]

        result = await mock.read_entries()
        assert len(result) == 1
        mock.read_entries.assert_called_once()

    async def test_mock_search_verified(self):
        """Mock search should be verifiable."""
        mock = AsyncMock(spec=IndexManagerPort)
        mock.search.return_value = [{"memory_id": "id-1", "name": "Alice的记忆"}]

        result = await mock.search("Alice")
        assert len(result) == 1
        mock.search.assert_called_once_with("Alice")

    async def test_mock_truncate_verified(self):
        """Mock truncate should be verifiable."""
        mock = AsyncMock(spec=IndexManagerPort)
        mock.truncate.return_value = None

        await mock.truncate()
        mock.truncate.assert_called_once()


class ConcreteIndexManagerAdapter(IndexManagerPort):
    """Concrete implementation for integration tests."""

    def __init__(self) -> None:
        self._entries: list[dict[str, str]] = []

    async def update_entry(self, entry: dict) -> None:
        self._entries = [e for e in self._entries if e.get("memory_id") != entry.get("memory_id")]
        self._entries.append(entry)

    async def remove_entry(self, memory_id: str) -> None:
        self._entries = [e for e in self._entries if e.get("memory_id") != memory_id]

    async def read_entries(self) -> list[dict]:
        return list(self._entries)

    async def search(self, query: str) -> list[dict]:
        query_lower = query.lower()
        return [e for e in self._entries if query_lower in e.get("name", "").lower()]

    async def truncate(self) -> None:
        if len(self._entries) > 200:
            self._entries = self._entries[-200:]


async def test_concrete_update_and_read():
    """Concrete implementation should support update and read."""
    adapter = ConcreteIndexManagerAdapter()
    await adapter.update_entry({"name": "test", "memory_id": "id1", "type": "user"})
    entries = await adapter.read_entries()
    assert len(entries) == 1
    assert entries[0]["memory_id"] == "id1"


async def test_concrete_search():
    """Concrete implementation should support search."""
    adapter = ConcreteIndexManagerAdapter()
    await adapter.update_entry({"name": "Alice的记忆", "memory_id": "id1", "type": "user"})
    await adapter.update_entry({"name": "Bob的记忆", "memory_id": "id2", "type": "user"})
    results = await adapter.search("Alice")
    assert len(results) == 1
    assert results[0]["memory_id"] == "id1"


async def test_concrete_truncate():
    """Concrete implementation should support truncate."""
    adapter = ConcreteIndexManagerAdapter()
    for i in range(250):
        await adapter.update_entry({"name": f"entry{i}", "memory_id": f"id{i}", "type": "user"})
    await adapter.truncate()
    entries = await adapter.read_entries()
    assert len(entries) == 200
