"""Tests for Fake Mock Implementations (Task 12).

RED PHASE: 验证 Fake 实现存在

验证标准（Task 12）:
- [ ] FakeL0StorageAdapter 实现 L0StoragePort
- [ ] FakeMemoryIndex 实现 IndexManagerPort
- [ ] FakeIntegrityVerifier 实现 IntegrityPort
"""

from __future__ import annotations

import pytest

from src.domain.ports.index_manager import IndexManagerPort
from src.domain.ports.integrity import IntegrityPort
from src.domain.ports.l0_storage import L0StoragePort


class FakeL0StorageAdapter(L0StoragePort):
    """Fake implementation of L0StoragePort for testing."""

    def __init__(self):
        self._storage = {}

    async def write(self, memory_id: str, memory_type: str, content: str) -> bool:
        key = f"{memory_type}:{memory_id}"
        self._storage[key] = content
        return True

    async def read(self, memory_id: str, memory_type: str) -> str:
        key = f"{memory_type}:{memory_id}"
        return self._storage.get(key, "") or ""

    async def delete(self, memory_id: str, memory_type: str) -> bool:
        key = f"{memory_type}:{memory_id}"
        existed = key in self._storage
        self._storage.pop(key, None)
        return existed

    async def exists(self, memory_id: str, memory_type: str) -> bool:
        key = f"{memory_type}:{memory_id}"
        return key in self._storage

    async def list_memories(self, memory_type: str) -> list[str]:
        prefix = f"{memory_type}:"
        return [k[len(prefix) :] for k in self._storage.keys() if k.startswith(prefix)]


class FakeMemoryIndex(IndexManagerPort):
    """Fake implementation of IndexManagerPort for testing."""

    def __init__(self):
        self._entries = []

    async def update_entry(self, entry: dict) -> None:
        # 移除已存在的相同 memory_id 条目
        self._entries = [e for e in self._entries if e["memory_id"] != entry["memory_id"]]
        self._entries.append(entry)

    async def remove_entry(self, memory_id: str) -> None:
        self._entries = [e for e in self._entries if e["memory_id"] != memory_id]

    async def read_entries(self) -> list[dict]:
        return list(self._entries)

    async def search(self, query: str) -> list[dict]:
        query_lower = query.lower()
        return [e for e in self._entries if query_lower in e["name"].lower()]

    async def truncate(self) -> None:
        # Fake 不需要截断
        pass


class FakeIntegrityVerifier(IntegrityPort):
    """Fake implementation of IntegrityPort for testing."""

    def __init__(self):
        self._verified = []

    async def verify_file(self, file_path: str, expected_hash: str) -> bool:
        return file_path in self._verified or expected_hash == "valid"

    def compute_hash(self, data: str | bytes, algorithm: str | None = None) -> str:
        return "fake_hash"

    def verify_hash(self, data: str | bytes, expected_hash: str, algorithm: str | None = None) -> bool:
        return expected_hash == "valid" or self.compute_hash(data) == expected_hash


class TestFakeL0StorageAdapter:
    """FakeL0StorageAdapter 实现验证"""

    def test_has_l0_storage_port_methods(self):
        """FakeL0StorageAdapter should have L0StoragePort methods."""
        fake = FakeL0StorageAdapter()
        assert hasattr(fake, "write")
        assert hasattr(fake, "read")
        assert hasattr(fake, "exists")

    @pytest.mark.asyncio
    async def test_write_and_read(self):
        """验证写入和读取"""
        fake = FakeL0StorageAdapter()
        await fake.write("id-1", "user", "test content")
        result = await fake.read("id-1", "user")
        assert result == "test content"

    @pytest.mark.asyncio
    async def test_exists(self):
        """验证 exists 方法"""
        fake = FakeL0StorageAdapter()
        assert not await fake.exists("id-1", "user")
        await fake.write("id-1", "user", "content")
        assert await fake.exists("id-1", "user")


class TestFakeMemoryIndex:
    """FakeMemoryIndex 实现验证"""

    def test_has_index_manager_port_methods(self):
        """FakeMemoryIndex should have IndexManagerPort methods."""
        fake = FakeMemoryIndex()
        assert hasattr(fake, "update_entry")
        assert hasattr(fake, "read_entries")

    @pytest.mark.asyncio
    async def test_update_and_read(self):
        """验证更新和读取"""
        fake = FakeMemoryIndex()
        await fake.update_entry({"memory_id": "id-1", "name": "test", "type": "user"})
        entries = await fake.read_entries()
        assert len(entries) == 1
        assert entries[0]["memory_id"] == "id-1"

    @pytest.mark.asyncio
    async def test_search(self):
        """验证搜索"""
        fake = FakeMemoryIndex()
        await fake.update_entry({"memory_id": "id-1", "name": "bun npm", "type": "user"})
        results = await fake.search("bun")
        assert len(results) == 1


class TestFakeIntegrityVerifier:
    """FakeIntegrityVerifier 实现验证"""

    def test_has_integrity_port_methods(self):
        """FakeIntegrityVerifier should have IntegrityPort methods."""
        fake = FakeIntegrityVerifier()
        assert hasattr(fake, "compute_hash")
        assert hasattr(fake, "verify_hash")

    def test_compute_hash(self):
        """验证 compute_hash"""
        fake = FakeIntegrityVerifier()
        hash_result = fake.compute_hash("test data")
        assert hash_result == "fake_hash"

    def test_verify_hash_valid(self):
        """验证 verify_hash with valid hash"""
        fake = FakeIntegrityVerifier()
        assert fake.verify_hash("test data", "valid") is True

    def test_verify_hash_invalid(self):
        """验证 verify_hash with invalid hash"""
        fake = FakeIntegrityVerifier()
        assert fake.verify_hash("test data", "invalid") is False
