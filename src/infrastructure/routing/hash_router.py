"""HashRouter — consistent hashing implementation for session-based routing."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class HashNode:
    """Represents a node in the hash ring."""

    node_id: str
    weight: int = 1  # Weight for weighted consistent hashing


class HashRouter:
    """Consistent hash router using FNV-1a hash for session-based routing.

    Provides O(log n) routing with minimal rebalancing when nodes are added/removed.
    Uses virtual nodes to ensure even distribution.
    """

    VIRTUAL_NODES_PER_NODE: int = 150  # Number of virtual nodes per physical node

    def __init__(self, nodes: Sequence[str] | None = None, virtual_nodes: int | None = None):
        """Initialize HashRouter.

        Args:
            nodes: Initial list of node IDs. None creates empty router.
            virtual_nodes: Override for VIRTUAL_NODES_PER_NODE (for testing).
        """
        self._virtual_nodes_per_node = virtual_nodes or self.VIRTUAL_NODES_PER_NODE
        self._ring: dict[int, str] = {}
        self._sorted_keys: list[int] = []
        self._node_weights: dict[str, int] = {}

        if nodes:
            for node in nodes:
                self.add_node(node)

    def add_node(self, node_id: str, weight: int = 1) -> None:
        """Add a node to the hash ring.

        Args:
            node_id: Unique node identifier
            weight: Weight for weighted consistent hashing (default: 1)
        """
        self._node_weights[node_id] = weight

        # Add virtual nodes based on weight
        for i in range(self._virtual_nodes_per_node * weight):
            virtual_key = self._hash(f"{node_id}:{i}")
            self._ring[virtual_key] = node_id

        self._sorted_keys = sorted(self._ring.keys())

    def remove_node(self, node_id: str) -> None:
        """Remove a node from the hash ring.

        Args:
            node_id: Node identifier to remove
        """
        self._node_weights.pop(node_id, None)

        # Remove all virtual nodes for this node
        keys_to_remove = [key for key, node in self._ring.items() if node == node_id]
        for key in keys_to_remove:
            del self._ring[key]

        self._sorted_keys = sorted(self._ring.keys())

    def route(self, session_id: str) -> str:
        """Route a session to a node using consistent hashing.

        Args:
            session_id: Session identifier to hash

        Returns:
            Node ID of the target node
        """
        if not self._ring:
            return "default"

        key = self._hash(session_id)

        # Binary search for the first node >= key
        # If key is greater than all nodes, wrap around to first node
        for ring_key in self._sorted_keys:
            if ring_key >= key:
                return self._ring[ring_key]

        # Wrap around to first node
        return self._ring[self._sorted_keys[0]]

    @staticmethod
    def _hash(value: str) -> int:
        """Compute murmurhash3-like hash for a string.

        Using FNV-1a as a fast, well-distributed alternative to murmurhash3.

        Args:
            value: String to hash

        Returns:
            32-bit unsigned integer hash
        """
        # FNV-1a 32-bit hash
        hash_value = 2166136261  # FNV offset basis
        for byte in value.encode("utf-8"):
            hash_value ^= byte
            hash_value *= 16777619  # FNV prime
        return hash_value & 0xFFFFFFFF

    @property
    def node_count(self) -> int:
        """Return the number of physical nodes in the ring."""
        return len(self._node_weights)

    @property
    def virtual_node_count(self) -> int:
        """Return the total number of virtual nodes in the ring."""
        return len(self._ring)
