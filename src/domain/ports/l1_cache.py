"""L1CachePort — Generic KV cache port (Rule 1).

Technology-agnostic key-value cache with TTL support.
Zero external dependencies (only typing).

This is the base port for all L1 cache implementations.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class L1CachePort(Protocol):
    """Generic KV cache port — Rule 1 domain interface.

    Provides key-value cache operations with optional TTL.
    Callers are responsible for key namespacing/prefixing.

    Methods:
        get(key): Read value by key.
        set(key, value, ttl): Write value with optional TTL.
        delete(key): Delete a key.
        exists(key): Check if key exists.
        delete_pattern(pattern): Delete keys matching glob pattern.
        set_with_ttl(key, value, ttl): Write with explicit TTL (no default).
    """

    async def get(self, key: str) -> str | None:
        """Read value by key.

        Args:
            key: Cache key (caller is responsible for namespacing).

        Returns:
            Cached value, or None if not found / expired.
        """

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        """Write value with optional TTL.

        Args:
            key: Cache key.
            value: Value to store.
            ttl: TTL in seconds. None means use default.

        Returns:
            True if successful.
        """

    async def delete(self, key: str) -> bool:
        """Delete a key.

        Args:
            key: Cache key.

        Returns:
            True if the key existed and was deleted.
        """

    async def exists(self, key: str) -> bool:
        """Check whether a key exists (and is not expired).

        Args:
            key: Cache key.

        Returns:
            True if the key exists.
        """

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob-style pattern.

        Uses SCAN (not KEYS) to avoid blocking.

        Args:
            pattern: Glob pattern, e.g. "memory:user:123:*".

        Returns:
            Number of keys deleted.
        """

    async def set_with_ttl(self, key: str, value: str, ttl: int) -> bool:
        """Write value with explicit TTL (no default fallback).

        Args:
            key: Cache key.
            value: Value to store.
            ttl: TTL in seconds (required).

        Returns:
            True if successful.
        """
