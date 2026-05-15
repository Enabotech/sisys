"""ConnectionManager Protocol — unified async connection lifecycle.

Defines the contract for all async storage connection managers
(PostgreSQL, Qdrant, Neo4j, Redis). Each manager owns a connection pool,
provides health checking, and supports graceful shutdown.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ConnectionManager(Protocol):
    """Unified async connection lifecycle contract.

    All async storage wrappers (DatabaseEngine, QdrantClientWrapper,
    Neo4jClientWrapper, RedisConnectionManager) satisfy this Protocol
    via structural subtyping.

    Required methods:
        health_check(): Check if the underlying connection is healthy
        close(): Close the connection pool and release all resources

    Optional method (default raises NotImplementedError):
        get_client(): Return the underlying client instance for direct access.
            Implementations should override this to return their specific client:
            - RedisConnectionManager -> aioredis.Redis
            - DatabaseEngine -> AsyncEngine
            - QdrantClientWrapper -> AsyncQdrantClient
            - Neo4jClientWrapper -> AsyncDriver
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

    def get_client(self) -> Any:
        """Get the underlying client instance.

        Optional: implementations that expose their client should override.
        Default raises NotImplementedError for managers that don't expose a client.

        Returns:
            The underlying client instance (e.g., aioredis.Redis, AsyncEngine).

        Raises:
            NotImplementedError: If the implementation does not expose a client.
        """
        raise NotImplementedError(
            f"{type(self).__name__}.get_client() is not implemented. "
            "This ConnectionManager does not expose a client instance."
        )
