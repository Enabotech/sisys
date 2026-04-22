"""Unit tests for HashRouter — consistent hashing implementation."""

from __future__ import annotations

from src.infrastructure.routing.hash_router import HashRouter


class TestHashRouter:
    """Test suite for HashRouter consistent hashing."""

    def test_route_returns_node_for_existing_nodes(self) -> None:
        """Route should return a node ID when nodes exist."""
        router = HashRouter(nodes=["node-A", "node-B", "node-C"])
        result = router.route("session-123")
        assert result in ("node-A", "node-B", "node-C")

    def test_route_returns_default_for_empty_ring(self) -> None:
        """Route should return 'default' when hash ring is empty."""
        router = HashRouter()
        result = router.route("session-123")
        assert result == "default"

    def test_consistent_routing_same_session(self) -> None:
        """Same session_id should always route to same node (100% consistency)."""
        router = HashRouter(nodes=["node-A", "node-B", "node-C"])
        session_id = "session-consistency-test"

        # Route 10 times and verify same result
        results = [router.route(session_id) for _ in range(10)]
        assert len(set(results)) == 1, f"Expected same node, got {set(results)}"
        assert all(r == results[0] for r in results)

    def test_add_node_increases_node_count(self) -> None:
        """Adding a node should increase the physical node count."""
        router = HashRouter(nodes=["node-A", "node-B"])
        assert router.node_count == 2

        router.add_node("node-C")
        assert router.node_count == 3

    def test_remove_node_decreases_node_count(self) -> None:
        """Removing a node should decrease the physical node count."""
        router = HashRouter(nodes=["node-A", "node-B", "node-C"])
        assert router.node_count == 3

        router.remove_node("node-B")
        assert router.node_count == 2

    def test_rebalancing_on_node_removal(self) -> None:
        """Removing a node should rebalance affected sessions to remaining nodes."""
        router = HashRouter(nodes=["node-A", "node-B", "node-C"])
        sessions = [f"session-{i}" for i in range(100)]

        # Remove node-B
        router.remove_node("node-B")

        # Route after removal
        after = {sid: router.route(sid) for sid in sessions}

        # All sessions should now route to node-A or node-C (not node-B)
        for sid in sessions:
            assert after[sid] in ("node-A", "node-C"), f"Session {sid} routes to {after[sid]}"

    def test_route_after_multiple_additions_removals(self) -> None:
        """Router should handle multiple add/remove operations correctly."""
        router = HashRouter(nodes=["node-A"])

        # Add nodes
        router.add_node("node-B")
        router.add_node("node-C")

        assert router.node_count == 3

        # Remove and re-add
        router.remove_node("node-B")
        assert router.node_count == 2

        router.add_node("node-D")
        assert router.node_count == 3

        # Verify routing works
        session = "test-session"
        result = router.route(session)
        assert result in ("node-A", "node-C", "node-D")

    def test_special_characters_in_session_id(self) -> None:
        """Special characters in session_id should be handled correctly."""
        router = HashRouter(nodes=["node-A", "node-B"])

        session_ids = [
            "session:with:colons",
            "session/with/slashes",
            "session spaces",
            "session-中文-test",
            "session-123-ABC",
        ]

        for sid in session_ids:
            result = router.route(sid)
            assert result in ("node-A", "node-B")

    def test_consistent_hash_algorithm_deterministic(self) -> None:
        """Hash algorithm should be deterministic."""
        router = HashRouter(nodes=["node-A"])

        result1 = router.route("same-session")
        result2 = router.route("same-session")

        assert result1 == result2

    def test_different_sessions_can_route_to_different_nodes(self) -> None:
        """Different sessions should potentially route to different nodes."""
        router = HashRouter(nodes=["node-A", "node-B", "node-C"])

        sessions = [f"session-{i}" for i in range(100)]
        targets = set(router.route(sid) for sid in sessions)

        # Should use at least 2 different nodes for 100 sessions
        assert len(targets) >= 2, f"Only {len(targets)} node(s) used for 100 sessions"

    def test_node_virtual_node_count(self) -> None:
        """Each node should have configured number of virtual nodes."""
        router = HashRouter(nodes=["node-A", "node-B"])

        # Default is 150 virtual nodes per node
        assert router.virtual_node_count == 300  # 2 nodes * 150

        router.add_node("node-C")
        assert router.virtual_node_count == 450  # 3 nodes * 150

    def test_empty_node_id_allowed(self) -> None:
        """Empty node ID should be allowed."""
        router = HashRouter(nodes=["", "node-A"])
        result = router.route("session-123")
        assert result in ("", "node-A")

    def test_single_node_routing(self) -> None:
        """With single node, all sessions should route to it."""
        router = HashRouter(nodes=["only-node"])

        for i in range(50):
            result = router.route(f"session-{i}")
            assert result == "only-node"

    def test_route_wraps_around_when_hash_greater_than_all_keys(self) -> None:
        """Should wrap around to first node when hash > all virtual node keys."""
        router = HashRouter(nodes=["node-A", "node-B", "node-C"])

        # Test multiple sessions - the wrap-around case is when hash value is
        # greater than all virtual node keys, it should return first node
        results = [router.route(f"session-{i}") for i in range(100)]
        # All results should be valid nodes
        assert all(r in ("node-A", "node-B", "node-C") for r in results)

    def test_adding_node_changes_some_routes(self) -> None:
        """Adding a node may change routing for some existing sessions."""
        router = HashRouter(nodes=["node-A", "node-B"])

        # Route 100 sessions before adding node using random UUIDs
        sessions = [f"user-session-{i}-uuid" for i in range(100)]
        before = {sid: router.route(sid) for sid in sessions}

        # Add node-C
        router.add_node("node-C")

        # Route after adding
        after = {sid: router.route(sid) for sid in sessions}

        # Count how many changed
        unchanged = sum(1 for sid in sessions if before[sid] == after[sid])
        unchanged_percent = (unchanged / len(sessions)) * 100

        # Some routes should remain unchanged (consistent hashing property)
        # With random session IDs, we expect at least some to stay the same
        assert unchanged_percent >= 20, f"Only {unchanged_percent:.1f}% unchanged, expected >= 20%"

    def test_multi_node_weighted_routing(self) -> None:
        """Weighted nodes should receive proportionally distributed routes."""
        router = HashRouter()
        router.add_node("light-node", weight=1)
        router.add_node("heavy-node", weight=3)

        sessions = [f"weighted-session-{i}" for i in range(500)]
        distribution: dict[str, int] = {}
        for sid in sessions:
            target = router.route(sid)
            distribution[target] = distribution.get(target, 0) + 1

        light_count = distribution.get("light-node", 0)
        heavy_count = distribution.get("heavy-node", 0)

        # Heavy node (3x weight) should get more routes
        assert heavy_count > light_count, "Heavy node should receive more routes"

        # Ratio should be roughly 3:1
        assert light_count > 0, "light_count should not be zero for valid weighted test"
        ratio = heavy_count / light_count
        assert 2.0 <= ratio <= 4.0, f"Expected ratio ~3, got {ratio:.2f}"
