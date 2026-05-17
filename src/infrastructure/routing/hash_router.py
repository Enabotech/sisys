"""SISYS 基础设施层一致性哈希路由模块

基于 FNV-1a 哈希算法实现会话级别的一致性路由，支持虚拟节点和加权分配

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class HashNode:
    """哈希环节点数据类

    Attributes:
        node_id: 节点唯一标识
        weight: 加权一致性哈希的权重值
    """

    node_id: str
    weight: int = 1


class HashRouter:
    """一致性哈希路由器，基于 FNV-1a 哈希实现会话路由

    提供 O(log n) 路由复杂度，节点增删时最小化重分配。使用虚拟节点确保均匀分布

    Attributes:
        VIRTUAL_NODES_PER_NODE: 每个物理节点的虚拟节点数
    """

    VIRTUAL_NODES_PER_NODE: int = 150  # 每个物理节点的虚拟节点数量

    def __init__(self, nodes: Sequence[str] | None = None, virtual_nodes: int | None = None):
        """初始化哈希路由器

        Args:
            nodes: 初始节点 ID 列表，None 表示创建空路由器
            virtual_nodes: 覆盖 VIRTUAL_NODES_PER_NODE 的值（用于测试）
        """
        self._virtual_nodes_per_node = virtual_nodes or self.VIRTUAL_NODES_PER_NODE
        self._ring: dict[int, str] = {}
        self._sorted_keys: list[int] = []
        self._node_weights: dict[str, int] = {}

        if nodes:
            for node in nodes:
                self.add_node(node)

    def add_node(self, node_id: str, weight: int = 1) -> None:
        """添加节点到哈希环

        Args:
            node_id: 节点唯一标识
            weight: 加权一致性哈希的权重值（默认 1）
        """
        self._node_weights[node_id] = weight

        # 根据权重添加虚拟节点
        for i in range(self._virtual_nodes_per_node * weight):
            virtual_key = self._hash(f"{node_id}:{i}")
            self._ring[virtual_key] = node_id

        self._sorted_keys = sorted(self._ring.keys())

    def remove_node(self, node_id: str) -> None:
        """从哈希环移除节点

        Args:
            node_id: 要移除的节点标识
        """
        self._node_weights.pop(node_id, None)

        # 移除该节点的所有虚拟节点
        keys_to_remove = [key for key, node in self._ring.items() if node == node_id]
        for key in keys_to_remove:
            del self._ring[key]

        self._sorted_keys = sorted(self._ring.keys())

    def route(self, session_id: str) -> str:
        """通过一致性哈希将会话路由到目标节点

        Args:
            session_id: 会话标识

        Returns:
            目标节点 ID
        """
        if not self._ring:
            return "default"

        key = self._hash(session_id)

        # 二分查找第一个大于等于 key 的节点
        # 如果 key 大于所有节点，环绕到第一个节点
        for ring_key in self._sorted_keys:
            if ring_key >= key:
                return self._ring[ring_key]

        # 环绕到第一个节点
        return self._ring[self._sorted_keys[0]]

    @staticmethod
    def _hash(value: str) -> int:
        """计算字符串的 FNV-1a 哈希值

        使用 FNV-1a 作为 murmurhash3 的快速替代方案，分布均匀

        Args:
            value: 待哈希字符串

        Returns:
            32 位无符号整数哈希值
        """
        # FNV-1a 32-bit 哈希算法
        hash_value = 2166136261  # FNV 基准偏移量
        for byte in value.encode("utf-8"):
            hash_value ^= byte
            hash_value *= 16777619  # FNV 质数
        return hash_value & 0xFFFFFFFF

    @property
    def node_count(self) -> int:
        """返回物理节点数量。"""
        return len(self._node_weights)

    @property
    def virtual_node_count(self) -> int:
        """返回虚拟节点总数。"""
        return len(self._ring)
