"""Test IntegrityPort - Red Phase (Test First)."""

from __future__ import annotations

import pytest

from src.domain.ports.integrity import IntegrityPort


class TestIntegrityPort:
    """IntegrityPort interface tests."""

    def test_integrity_port_is_abstract(self):
        """IntegrityPort should be abstract class."""
        with pytest.raises(TypeError):
            IntegrityPort()

    def test_verify_file_is_abstract(self):
        """verify_file() should be abstract async method."""
        port = IntegrityPort.__abstractmethods__
        assert "verify_file" in port

    def test_compute_hash_is_abstract(self):
        """compute_hash() should be abstract sync method."""
        port = IntegrityPort.__abstractmethods__
        assert "compute_hash" in port

    def test_verify_hash_is_abstract(self):
        """verify_hash() should be abstract sync method."""
        port = IntegrityPort.__abstractmethods__
        assert "verify_hash" in port


class ConcreteIntegrityAdapter(IntegrityPort):
    """Concrete implementation for testing."""

    def __init__(self) -> None:
        self._hashes: dict[str, str] = {}

    async def verify_file(self, file_path: str, expected_hash: str) -> bool:
        return self._hashes.get(file_path) == expected_hash

    def compute_hash(self, data: str | bytes, algorithm: str | None = None) -> str:
        import hashlib

        if isinstance(data, str):
            data = data.encode("utf-8")
        algo = algorithm or "sha256"
        if algo == "sha256":
            return hashlib.sha256(data).hexdigest()
        elif algo == "sha512":
            return hashlib.sha512(data).hexdigest()
        elif algo == "md5":
            return hashlib.md5(data, usedforsecurity=False).hexdigest()
        raise ValueError(f"Unsupported algorithm: {algo}")

    def verify_hash(self, data: str | bytes, expected_hash: str, algorithm: str | None = None) -> bool:
        actual = self.compute_hash(data, algorithm)
        return actual.lower() == expected_hash.lower()


@pytest.mark.asyncio
async def test_concrete_verify_file():
    """Concrete implementation should support verify_file."""
    adapter = ConcreteIntegrityAdapter()
    adapter._hashes["/path/to/file"] = "abc123"
    result = await adapter.verify_file("/path/to/file", "abc123")
    assert result is True
    result = await adapter.verify_file("/path/to/file", "wrong")
    assert result is False


def test_concrete_compute_hash():
    """Concrete implementation should support compute_hash."""
    adapter = ConcreteIntegrityAdapter()
    hash1 = adapter.compute_hash("hello", "sha256")
    hash2 = adapter.compute_hash("hello", "sha256")
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 produces 64 hex chars


def test_concrete_verify_hash():
    """Concrete implementation should support verify_hash."""
    adapter = ConcreteIntegrityAdapter()
    result = adapter.verify_hash("hello", adapter.compute_hash("hello"))
    assert result is True
    result = adapter.verify_hash("hello", "wrong_hash")
    assert result is False
