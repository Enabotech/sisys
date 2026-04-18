"""RedisKeyBuilder tests."""

from __future__ import annotations

from src.infrastructure.storage.redis.key_builder import build_key


class TestKeyBuilder:
    """RedisKeyBuilder 测试。"""

    def test_single_part(self) -> None:
        """单部分键。"""
        assert build_key("session", "sess-1") == "sisys:session:sess-1"

    def test_multiple_parts(self) -> None:
        """多部分键。"""
        assert build_key("cache", "semantic", "vec:123") == "sisys:cache:semantic:vec:123"

    def test_blackboard_key(self) -> None:
        """黑板键。"""
        assert build_key("blackboard", "conv-1", "version") == "sisys:blackboard:conv-1:version"

    def test_namespace_with_special_chars(self) -> None:
        """命名空间包含特殊字符。"""
        assert build_key("cache:semantic", "key") == "sisys:cache:semantic:key"

    def test_empty_parts(self) -> None:
        """空部分。"""
        assert build_key("session", "") == "sisys:session:"

    def test_wildcard_pattern(self) -> None:
        """通配符模式。"""
        assert build_key("session", "*") == "sisys:session:*"
