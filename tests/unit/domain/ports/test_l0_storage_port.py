"""Test L0StoragePort - Red Phase (Test First)."""

from __future__ import annotations

import pytest

from src.domain.ports.l0_storage import L0StoragePort


class TestL0StoragePort:
    """L0StoragePort interface tests."""

    def test_l0_storage_port_is_abstract(self):
        """L0StoragePort should be abstract class."""
        with pytest.raises(TypeError):
            L0StoragePort()

    def test_write_method_is_abstract(self):
        """write() should be abstract async method."""
        port = L0StoragePort.__abstractmethods__
        assert "write" in port

    def test_read_method_is_abstract(self):
        """read() should be abstract async method."""
        port = L0StoragePort.__abstractmethods__
        assert "read" in port

    def test_delete_method_is_abstract(self):
        """delete() should be abstract async method."""
        port = L0StoragePort.__abstractmethods__
        assert "delete" in port

    def test_exists_method_is_abstract(self):
        """exists() should be abstract async method."""
        port = L0StoragePort.__abstractmethods__
        assert "exists" in port

    def test_list_memories_method_is_abstract(self):
        """list_memories() should be abstract async method."""
        port = L0StoragePort.__abstractmethods__
        assert "list_memories" in port


class ConcreteL0StorageAdapter(L0StoragePort):
    """Concrete implementation for testing."""

    def __init__(self) -> None:
        self._memories: dict[str, dict[str, str]] = {}

    async def write(self, memory_id: str, memory_type: str, content: str) -> None:
        if memory_type not in self._memories:
            self._memories[memory_type] = {}
        self._memories[memory_type][memory_id] = content

    async def read(self, memory_id: str, memory_type: str) -> str:
        if memory_type not in self._memories:
            raise FileNotFoundError(f"Memory {memory_id} not found")
        if memory_id not in self._memories[memory_type]:
            raise FileNotFoundError(f"Memory {memory_id} not found")
        return self._memories[memory_type][memory_id]

    async def delete(self, memory_id: str, memory_type: str) -> None:
        if memory_type in self._memories and memory_id in self._memories[memory_type]:
            del self._memories[memory_type][memory_id]

    async def exists(self, memory_id: str, memory_type: str) -> bool:
        return memory_type in self._memories and memory_id in self._memories[memory_type]

    async def list_memories(self, memory_type: str) -> list[str]:
        if memory_type not in self._memories:
            return []
        return list(self._memories[memory_type].keys())


@pytest.mark.asyncio
async def test_concrete_write_and_read():
    """Concrete implementation should support write and read."""
    adapter = ConcreteL0StorageAdapter()
    await adapter.write("test-id", "user", "test content")
    content = await adapter.read("test-id", "user")
    assert content == "test content"


@pytest.mark.asyncio
async def test_concrete_delete():
    """Concrete implementation should support delete."""
    adapter = ConcreteL0StorageAdapter()
    await adapter.write("test-id", "user", "test content")
    assert await adapter.exists("test-id", "user") is True
    await adapter.delete("test-id", "user")
    assert await adapter.exists("test-id", "user") is False


@pytest.mark.asyncio
async def test_concrete_list_memories():
    """Concrete implementation should support list_memories."""
    adapter = ConcreteL0StorageAdapter()
    await adapter.write("id1", "user", "content1")
    await adapter.write("id2", "user", "content2")
    ids = await adapter.list_memories("user")
    assert set(ids) == {"id1", "id2"}
