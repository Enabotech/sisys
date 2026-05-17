"""领域层 L1 缓存端口模块

技术无关的键值缓存端口，支持 TTL
零外部依赖（仅使用 typing）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class L1CachePort(Protocol):
    """通用键值缓存端口 — Rule 1 领域接口

    提供带可选 TTL 的键值缓存操作
    调用方负责键的命名空间/前缀管理
    """

    async def get(self, key: str) -> str | None:
        """按键读取值

        Args:
            key: 缓存键（调用方负责命名空间）

        Returns:
            缓存值，未找到或已过期则返回 None
        """

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        """写入值（可选 TTL）

        Args:
            key: 缓存键
            value: 待存储的值
            ttl: TTL 秒数，None 表示使用默认值

        Returns:
            成功返回 True
        """

    async def delete(self, key: str) -> bool:
        """删除键

        Args:
            key: 缓存键

        Returns:
            键存在且已删除返回 True
        """

    async def exists(self, key: str) -> bool:
        """检查键是否存在（且未过期）

        Args:
            key: 缓存键

        Returns:
            键存在返回 True
        """

    async def delete_pattern(self, pattern: str) -> int:
        """删除匹配 glob 模式的所有键

        使用 SCAN（非 KEYS）以避免阻塞

        Args:
            pattern: glob 模式，如 "memory:user:123:*"

        Returns:
            已删除的键数量
        """

    async def set_with_ttl(self, key: str, value: str, ttl: int) -> bool:
        """写入值（显式 TTL，无默认回退）

        Args:
            key: 缓存键
            value: 待存储的值
            ttl: TTL 秒数（必填）

        Returns:
            成功返回 True
        """
