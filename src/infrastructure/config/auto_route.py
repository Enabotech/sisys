"""基础设施层自动路由配置模块

提供自动路由机制的配置，支持哈希/语义/混合路由策略

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AutoRouteConfig:
    """自动路由机制配置

    使用 from_env() 类方法从环境变量加载配置

    Attributes:
        route_enabled: 是否启用自动路由机制
        route_type: 路由类型（hash/semantic/mixed）
        semantic_threshold: 语义路由最小相似度分数
        hash_ring_size: 每个物理节点的虚拟节点数
        cache_ttl_seconds: 缓存 TTL（秒）
    """

    route_enabled: bool = True
    route_type: str = "mixed"  # "hash" | "semantic" | "mixed"
    semantic_threshold: float = 0.7  # Minimum similarity score for semantic routing
    hash_ring_size: int = 150  # Number of virtual nodes per physical node
    cache_ttl_seconds: int = 86400  # 24 hours

    @classmethod
    def from_env(cls) -> AutoRouteConfig:
        """从环境变量加载配置

        Args:
            无（从 os.environ 读取）

        Returns:
            AutoRouteConfig 实例

        Raises:
            ValueError: 环境变量值不合法时抛出
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
