"""Test IndexManagerPort - Red Phase (Test First)."""
from __future__ import annotations

import pytest

from src.domain.ports.index_manager import IndexManagerPort


class TestIndexManagerPort:
    """IndexManagerPort interface tests."""

    def test_index_manager_port_is_abstract(self):
        """IndexManagerPort should be abstract class."""
        with pytest.raises(TypeError):
            IndexManagerPort()

    def test_update_entry_is_abstract(self):
        """update_entry() should be abstract async method."""
        port = IndexManagerPort.__abstractmethods__
        assert "update_entry" in port

    def test_remove_entry_is_abstract(self):
        """remove_entry() should be abstract async method."""
        port = IndexManagerPort.__abstractmethods__
        assert "remove_entry" in port

    def test_read_entries_is_abstract(self):
        """read_entries() should be abstract async method."""
        port = IndexManagerPort.__abstractmethods__
        assert "read_entries" in port

    def test_search_is_abstract(self):
        """search() should be abstract async method."""
        port = IndexManagerPort.__abstractmethods__
        assert "search" in port

    def test_truncate_is_abstract(self):
        """truncate() should be abstract async method."""
        port = IndexManagerPort.__abstractmethods__
        assert "truncate" in port


class ConcreteIndexManagerAdapter(IndexManagerPort):
    """Concrete implementation for testing."""

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


@pytest.mark.asyncio
async def test_concrete_update_and_read():
    """Concrete implementation should support update and read."""
    adapter = ConcreteIndexManagerAdapter()
    await adapter.update_entry({"name": "test", "memory_id": "id1", "type": "user"})
    entries = await adapter.read_entries()
    assert len(entries) == 1
    assert entries[0]["memory_id"] == "id1"


@pytest.mark.asyncio
async def test_concrete_search():
    """Concrete implementation should support search."""
    adapter = ConcreteIndexManagerAdapter()
    await adapter.update_entry({"name": "Alice的记忆", "memory_id": "id1", "type": "user"})
    await adapter.update_entry({"name": "Bob的记忆", "memory_id": "id2", "type": "user"})
    results = await adapter.search("Alice")
    assert len(results) == 1
    assert results[0]["memory_id"] == "id1"


@pytest.mark.asyncio
async def test_concrete_truncate():
    """Concrete implementation should support truncate."""
    adapter = ConcreteIndexManagerAdapter()
    for i in range(250):
        await adapter.update_entry({"name": f"entry{i}", "memory_id": f"id{i}", "type": "user"})
    await adapter.truncate()
    entries = await adapter.read_entries()
    assert len(entries) == 200
