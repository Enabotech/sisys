"""ConnectionManager Protocol — unified async connection lifecycle.

Defines the contract for all async storage connection managers
(PostgreSQL, Qdrant, Neo4j, Redis). Each manager owns a connection pool,
provides health checking, and supports graceful shutdown.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ConnectionManager(Protocol):
    """Unified async connection lifecycle contract.

    All async storage wrappers (DatabaseEngine, QdrantClientWrapper,
    Neo4jClientWrapper, RedisConnectionManager) satisfy this Protocol
    via structural subtyping.
    """

    async def health_check(self) -> bool:
        """Check if the underlying connection is healthy.

        Returns:
            True if connection is alive, False otherwise.
        """
        ...

    async def close(self) -> None:
        """Close the connection pool and release all resources."""
        ...
