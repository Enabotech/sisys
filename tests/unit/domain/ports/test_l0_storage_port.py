"""Test L0StoragePort - Protocol Interface Tests."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

from src.domain.ports.l0_storage import L0StoragePort


class TestL0StoragePortSignature:
    """Structural signature tests — verify async contract."""

    def test_all_methods_are_async(self) -> None:
        """All methods should be async."""
        for method_name in ["write", "read", "delete", "exists", "list_memories"]:
            method = getattr(L0StoragePort, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} must be async"


class TestL0StoragePortMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec约束."""

    async def test_mock_write_verified(self):
        """Mock write should be verifiable."""
        mock = AsyncMock(spec=L0StoragePort)
        mock.write.return_value = True

        result = await mock.write("id", "user", "content")
        assert result is True
        mock.write.assert_called_once_with("id", "user", "content")

    async def test_mock_read_verified(self):
        """Mock read should be verifiable."""
        mock = AsyncMock(spec=L0StoragePort)
        mock.read.return_value = "test content"

        result = await mock.read("id", "user")
        assert result == "test content"
        mock.read.assert_called_once_with("id", "user")

    async def test_mock_delete_verified(self):
        """Mock delete should be verifiable."""
        mock = AsyncMock(spec=L0StoragePort)
        mock.delete.return_value = True

        result = await mock.delete("id", "user")
        assert result is True
        mock.delete.assert_called_once_with("id", "user")

    async def test_mock_exists_verified(self):
        """Mock exists should be verifiable."""
        mock = AsyncMock(spec=L0StoragePort)
        mock.exists.return_value = True

        result = await mock.exists("id", "user")
        assert result is True
        mock.exists.assert_called_once_with("id", "user")

    async def test_mock_list_memories_verified(self):
        """Mock list_memories should be verifiable."""
        mock = AsyncMock(spec=L0StoragePort)
        mock.list_memories.return_value = ["id1", "id2"]

        result = await mock.list_memories("user")
        assert result == ["id1", "id2"]
        mock.list_memories.assert_called_once_with("user")


class ConcreteL0StorageAdapter(L0StoragePort):
    """Concrete implementation for integration tests."""

    def __init__(self) -> None:
        self._memories: dict[str, dict[str, str]] = {}

    async def write(self, memory_id: str, memory_type: str, content: str) -> bool:
        if memory_type not in self._memories:
            self._memories[memory_type] = {}
        self._memories[memory_type][memory_id] = content
        return True

    async def read(self, memory_id: str, memory_type: str) -> str:
        if memory_type not in self._memories:
            raise FileNotFoundError(f"Memory {memory_id} not found")
        if memory_id not in self._memories[memory_type]:
            raise FileNotFoundError(f"Memory {memory_id} not found")
        return self._memories[memory_type][memory_id]

    async def delete(self, memory_id: str, memory_type: str) -> bool:
        if memory_type in self._memories and memory_id in self._memories[memory_type]:
            del self._memories[memory_type][memory_id]
            return True
        return False

    async def exists(self, memory_id: str, memory_type: str) -> bool:
        return memory_type in self._memories and memory_id in self._memories[memory_type]

    async def list_memories(self, memory_type: str) -> list[str]:
        if memory_type not in self._memories:
            return []
        return list(self._memories[memory_type].keys())


async def test_concrete_write_and_read():
    """Concrete implementation should support write and read."""
    adapter = ConcreteL0StorageAdapter()
    await adapter.write("test-id", "user", "test content")
    content = await adapter.read("test-id", "user")
    assert content == "test content"


async def test_concrete_delete():
    """Concrete implementation should support delete."""
    adapter = ConcreteL0StorageAdapter()
    await adapter.write("test-id", "user", "test content")
    assert await adapter.exists("test-id", "user") is True
    await adapter.delete("test-id", "user")
    assert await adapter.exists("test-id", "user") is False


async def test_concrete_list_memories():
    """Concrete implementation should support list_memories."""
    adapter = ConcreteL0StorageAdapter()
    await adapter.write("id1", "user", "content1")
    await adapter.write("id2", "user", "content2")
    ids = await adapter.list_memories("user")
    assert set(ids) == {"id1", "id2"}
