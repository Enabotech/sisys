"""MemoryCachePort — Memory-domain cache port (Rule 2).

Extends L1CachePort with memory-specific semantic methods.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.ports.l1_cache import L1CachePort


@runtime_checkable
class MemoryCachePort(L1CachePort, Protocol):
    """Memory-domain-specific cache port — Rule 2 application interface.

    Inherits all generic KV methods from L1CachePort and adds
    memory-specific semantic methods.

    Memory key convention:
        Private: memory:user:{user_id}:{name}
        Group:   memory:group:{group_id}:{name}
    """

    async def get_memory(
        self,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> str | None:
        """Read a cached memory entry.

        Args:
            memory_type: 'private' | 'group'
            owner_id: User ID or group ID
            name: Memory name

        Returns:
            Cached content, or None.
        """

    async def set_memory(
        self,
        memory_type: str,
        owner_id: str,
        name: str,
        content: str,
        ttl: int | None = None,
    ) -> bool:
        """Write a cached memory entry.

        Args:
            memory_type: 'private' | 'group'
            owner_id: User ID or group ID
            name: Memory name
            content: Content to cache
            ttl: TTL in seconds. None uses default (24h-30h random).

        Returns:
            True if successful.
        """

    async def delete_memory(
        self,
        memory_type: str,
        owner_id: str,
        name: str,
    ) -> bool:
        """Delete a specific cached memory entry.

        Args:
            memory_type: 'private' | 'group'
            owner_id: User ID or group ID
            name: Memory name

        Returns:
            True if deleted.
        """

    async def invalidate_owner(
        self,
        memory_type: str,
        owner_id: str,
    ) -> int:
        """Invalidate all cached entries for an owner.

        Args:
            memory_type: 'private' | 'group'
            owner_id: User ID or group ID

        Returns:
            Number of entries invalidated.
        """
