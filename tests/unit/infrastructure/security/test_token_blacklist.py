"""Tests for RedisTokenBlacklist."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from src.infrastructure.security.token_blacklist import RedisTokenBlacklist


class TestRedisTokenBlacklist:
    """Test RedisTokenBlacklist implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_redis = AsyncMock()
        self.service = RedisTokenBlacklist(self.mock_redis, default_ttl_hours=24)

    def test_get_key_returns_consistent_hash(self):
        """Same token should produce same key hash."""
        token = "test_token_123"
        key1 = self.service._get_key(token)
        key2 = self.service._get_key(token)
        assert key1 == key2
        assert key1.startswith("token:blacklist:")

    def test_get_key_different_tokens_different_keys(self):
        """Different tokens should produce different keys."""
        token1 = "token_1"
        token2 = "token_2"
        key1 = self.service._get_key(token1)
        key2 = self.service._get_key(token2)
        assert key1 != key2

    async def test_add_sets_token_with_default_ttl(self):
        """add() should set token in Redis with default TTL."""
        token = "test_token"
        await self.service.add(token)

        self.mock_redis.setex.assert_called_once()
        call_args = self.mock_redis.setex.call_args
        assert call_args[0][1] == timedelta(hours=24)  # default TTL
        assert call_args[0][2] == "1"

    async def test_add_sets_token_with_custom_ttl(self):
        """add() should use custom TTL when provided."""
        token = "test_token"
        custom_ttl = timedelta(hours=12)
        await self.service.add(token, ttl=custom_ttl)

        self.mock_redis.setex.assert_called_once()
        call_args = self.mock_redis.setex.call_args
        assert call_args[0][1] == custom_ttl

    async def test_is_blacklisted_returns_true_when_exists(self):
        """is_blacklisted() returns True when token is in blacklist."""
        self.mock_redis.exists.return_value = 1

        result = await self.service.is_blacklisted("test_token")

        assert result is True
        self.mock_redis.exists.assert_called_once()

    async def test_is_blacklisted_returns_false_when_not_exists(self):
        """is_blacklisted() returns False when token is not in blacklist."""
        self.mock_redis.exists.return_value = 0

        result = await self.service.is_blacklisted("test_token")

        assert result is False

    async def test_is_blacklisted_returns_false_when_count_is_zero(self):
        """is_blacklisted() returns False when exists returns 0."""
        self.mock_redis.exists.return_value = 0

        result = await self.service.is_blacklisted("test_token")

        assert result is False

    async def test_token_not_in_blacklist_after_add_check(self):
        """Verify token is added and can be checked."""
        token = "my_token"

        # Not blacklisted initially
        self.mock_redis.exists.return_value = 0
        assert await self.service.is_blacklisted(token) is False

        # Add to blacklist
        await self.service.add(token)

        # Now blacklisted
        self.mock_redis.exists.return_value = 1
        assert await self.service.is_blacklisted(token) is True
