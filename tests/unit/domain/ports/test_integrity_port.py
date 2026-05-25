"""Test IntegrityPort - Protocol Interface Tests."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

from src.domain.ports.integrity import IntegrityPort


class TestIntegrityPortSignature:
    """Structural signature tests — verify async/sync contract."""

    def test_verify_file_is_async(self) -> None:
        """verify_file should be async."""
        assert inspect.iscoroutinefunction(IntegrityPort.verify_file), "verify_file must be async"

    def test_compute_hash_is_sync(self) -> None:
        """compute_hash should be sync (not async)."""
        assert not inspect.iscoroutinefunction(IntegrityPort.compute_hash), "compute_hash must NOT be async"

    def test_verify_hash_is_sync(self) -> None:
        """verify_hash should be sync."""
        assert not inspect.iscoroutinefunction(IntegrityPort.verify_hash), "verify_hash must NOT be async"


class TestIntegrityPortMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec约束."""

    async def test_mock_verify_file_verified(self):
        """Mock verify_file should be verifiable."""
        mock = AsyncMock(spec=IntegrityPort)
        mock.verify_file.return_value = True

        result = await mock.verify_file("/path/to/file", "expected-hash")
        assert result is True
        mock.verify_file.assert_called_once_with("/path/to/file", "expected-hash")

    def test_mock_compute_hash_verified(self):
        """Mock compute_hash should be verifiable."""
        mock = MagicMock(spec=IntegrityPort)
        mock.compute_hash.return_value = "fake_hash_value"

        result = mock.compute_hash("test data", "sha256")
        assert isinstance(result, str)
        mock.compute_hash.assert_called_once_with("test data", "sha256")

    def test_mock_verify_hash_verified(self):
        """Mock verify_hash should be verifiable."""
        mock = MagicMock(spec=IntegrityPort)
        mock.verify_hash.return_value = True

        result = mock.verify_hash("test data", "abc123", "sha256")
        assert result is True
        mock.verify_hash.assert_called_once_with("test data", "abc123", "sha256")


class ConcreteIntegrityAdapter(IntegrityPort):
    """Concrete implementation for integration tests."""

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
    assert len(hash1) == 64


def test_concrete_verify_hash():
    """Concrete implementation should support verify_hash."""
    adapter = ConcreteIntegrityAdapter()
    result = adapter.verify_hash("hello", adapter.compute_hash("hello"))
    assert result is True
    result = adapter.verify_hash("hello", "wrong_hash")
    assert result is False
