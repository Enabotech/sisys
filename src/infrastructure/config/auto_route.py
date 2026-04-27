"""AutoRouteConfig — configuration for auto-route mechanism."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AutoRouteConfig:
    """Configuration for auto-route mechanism.

    Environment variables follow OtelConfig pattern (from_env() class method).
    """

    route_enabled: bool = True
    route_type: str = "mixed"  # "hash" | "semantic" | "mixed"
    semantic_threshold: float = 0.7  # Minimum similarity score for semantic routing
    hash_ring_size: int = 150  # Number of virtual nodes per physical node
    cache_ttl_seconds: int = 86400  # 24 hours

    @classmethod
    def from_env(cls) -> AutoRouteConfig:
        """Load configuration from environment variables.

        Environment variables:
            ROUTE_ENABLED: Enable auto-route mechanism (default: true)
            ROUTE_TYPE: Routing type - hash/semantic/mixed (default: mixed)
            SEMANTIC_THRESHOLD: Minimum similarity for semantic routing (default: 0.7)
            HASH_RING_SIZE: Virtual nodes per physical node (default: 150)
            ROUTE_CACHE_TTL: Cache TTL in seconds (default: 86400)

        Returns:
            AutoRouteConfig instance with values from environment
        """
        enabled_str = os.getenv("ROUTE_ENABLED", "true").lower()
        route_type_str = os.getenv("ROUTE_TYPE", "mixed").lower()
        semantic_threshold_str = os.getenv("SEMANTIC_THRESHOLD", "0.7")
        hash_ring_size_str = os.getenv("HASH_RING_SIZE", "150")
        cache_ttl_str = os.getenv("ROUTE_CACHE_TTL", "86400")

        # Validate route_type
        if route_type_str not in ("hash", "semantic", "mixed"):
            raise ValueError(f"ROUTE_TYPE must be one of: hash, semantic, mixed. Got: {route_type_str}")

        try:
            semantic_threshold = float(semantic_threshold_str)
            if not (0.0 <= semantic_threshold <= 1.0):
                raise ValueError(f"SEMANTIC_THRESHOLD must be between 0.0 and 1.0: {semantic_threshold}")
        except ValueError as e:
            raise ValueError(f"Invalid SEMANTIC_THRESHOLD value: {semantic_threshold_str}") from e

        try:
            hash_ring_size = int(hash_ring_size_str)
            if hash_ring_size <= 0:
                raise ValueError(f"HASH_RING_SIZE must be positive: {hash_ring_size}")
        except ValueError as e:
            raise ValueError(f"Invalid HASH_RING_SIZE value: {hash_ring_size_str}") from e

        try:
            cache_ttl = int(cache_ttl_str)
            if cache_ttl <= 0:
                raise ValueError(f"ROUTE_CACHE_TTL must be positive: {cache_ttl}")
        except ValueError as e:
            raise ValueError(f"Invalid ROUTE_CACHE_TTL value: {cache_ttl_str}") from e

        return cls(
            route_enabled=enabled_str in ("true", "1", "yes", "on"),
            route_type=route_type_str,
            semantic_threshold=semantic_threshold,
            hash_ring_size=hash_ring_size,
            cache_ttl_seconds=cache_ttl,
        )
