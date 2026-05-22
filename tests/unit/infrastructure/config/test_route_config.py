"""Unit tests for AutoRouteConfig."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.infrastructure.config.auto_route import AutoRouteConfig


class TestAutoRouteConfig:
    """Test suite for AutoRouteConfig."""

    def test_default_values(self) -> None:
        """Should have correct default values."""
        config = AutoRouteConfig()
        assert config.route_enabled is True
        assert config.route_type == "mixed"
        assert config.semantic_threshold == 0.7
        assert config.hash_ring_size == 150

    def test_from_env_defaults(self) -> None:
        """Should use defaults when env vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = AutoRouteConfig.from_env()
            assert config.route_enabled is True
            assert config.route_type == "mixed"
            assert config.semantic_threshold == 0.7
            assert config.hash_ring_size == 150

    def test_from_env_route_enabled_true(self) -> None:
        """Should parse ROUTE_ENABLED=true."""
        with patch.dict(os.environ, {"ROUTE_ENABLED": "true"}):
            config = AutoRouteConfig.from_env()
            assert config.route_enabled is True

    def test_from_env_route_enabled_false(self) -> None:
        """Should parse ROUTE_ENABLED=false."""
        with patch.dict(os.environ, {"ROUTE_ENABLED": "false"}):
            config = AutoRouteConfig.from_env()
            assert config.route_enabled is False

    def test_from_env_route_enabled_1(self) -> None:
        """Should parse ROUTE_ENABLED=1."""
        with patch.dict(os.environ, {"ROUTE_ENABLED": "1"}):
            config = AutoRouteConfig.from_env()
            assert config.route_enabled is True

    def test_from_env_route_enabled_yes(self) -> None:
        """Should parse ROUTE_ENABLED=yes."""
        with patch.dict(os.environ, {"ROUTE_ENABLED": "yes"}):
            config = AutoRouteConfig.from_env()
            assert config.route_enabled is True

    def test_from_env_route_enabled_on(self) -> None:
        """Should parse ROUTE_ENABLED=on."""
        with patch.dict(os.environ, {"ROUTE_ENABLED": "on"}):
            config = AutoRouteConfig.from_env()
            assert config.route_enabled is True

    def test_from_env_route_type_hash(self) -> None:
        """Should parse ROUTE_TYPE=hash."""
        with patch.dict(os.environ, {"ROUTE_TYPE": "hash"}):
            config = AutoRouteConfig.from_env()
            assert config.route_type == "hash"

    def test_from_env_route_type_semantic(self) -> None:
        """Should parse ROUTE_TYPE=semantic."""
        with patch.dict(os.environ, {"ROUTE_TYPE": "semantic"}):
            config = AutoRouteConfig.from_env()
            assert config.route_type == "semantic"

    def test_from_env_route_type_mixed(self) -> None:
        """Should parse ROUTE_TYPE=mixed."""
        with patch.dict(os.environ, {"ROUTE_TYPE": "mixed"}):
            config = AutoRouteConfig.from_env()
            assert config.route_type == "mixed"

    def test_from_env_route_type_invalid(self) -> None:
        """Should raise on invalid ROUTE_TYPE."""
        with patch.dict(os.environ, {"ROUTE_TYPE": "invalid"}):
            with pytest.raises(ValueError, match="ROUTE_TYPE must be one of"):
                AutoRouteConfig.from_env()

    def test_from_env_semantic_threshold(self) -> None:
        """Should parse SEMANTIC_THRESHOLD."""
        with patch.dict(os.environ, {"SEMANTIC_THRESHOLD": "0.8"}):
            config = AutoRouteConfig.from_env()
            assert config.semantic_threshold == 0.8

    def test_from_env_semantic_threshold_zero(self) -> None:
        """Should parse SEMANTIC_THRESHOLD=0.0."""
        with patch.dict(os.environ, {"SEMANTIC_THRESHOLD": "0.0"}):
            config = AutoRouteConfig.from_env()
            assert config.semantic_threshold == 0.0

    def test_from_env_semantic_threshold_one(self) -> None:
        """Should parse SEMANTIC_THRESHOLD=1.0."""
        with patch.dict(os.environ, {"SEMANTIC_THRESHOLD": "1.0"}):
            config = AutoRouteConfig.from_env()
            assert config.semantic_threshold == 1.0

    def test_from_env_semantic_threshold_invalid_range(self) -> None:
        """Should raise on SEMANTIC_THRESHOLD out of range."""
        with patch.dict(os.environ, {"SEMANTIC_THRESHOLD": "1.5"}):
            with pytest.raises(ValueError, match="Invalid SEMANTIC_THRESHOLD value"):
                AutoRouteConfig.from_env()

    def test_from_env_semantic_threshold_negative(self) -> None:
        """Should raise on negative SEMANTIC_THRESHOLD."""
        with patch.dict(os.environ, {"SEMANTIC_THRESHOLD": "-0.1"}):
            with pytest.raises(ValueError, match="Invalid SEMANTIC_THRESHOLD value"):
                AutoRouteConfig.from_env()

    def test_from_env_semantic_threshold_not_number(self) -> None:
        """Should raise on non-numeric SEMANTIC_THRESHOLD."""
        with patch.dict(os.environ, {"SEMANTIC_THRESHOLD": "abc"}):
            with pytest.raises(ValueError, match="Invalid SEMANTIC_THRESHOLD value"):
                AutoRouteConfig.from_env()

    def test_from_env_hash_ring_size(self) -> None:
        """Should parse HASH_RING_SIZE."""
        with patch.dict(os.environ, {"HASH_RING_SIZE": "200"}):
            config = AutoRouteConfig.from_env()
            assert config.hash_ring_size == 200

    def test_from_env_hash_ring_size_zero(self) -> None:
        """Should raise on HASH_RING_SIZE=0."""
        with patch.dict(os.environ, {"HASH_RING_SIZE": "0"}):
            with pytest.raises(ValueError, match="Invalid HASH_RING_SIZE value"):
                AutoRouteConfig.from_env()

    def test_from_env_hash_ring_size_negative(self) -> None:
        """Should raise on negative HASH_RING_SIZE."""
        with patch.dict(os.environ, {"HASH_RING_SIZE": "-1"}):
            with pytest.raises(ValueError, match="Invalid HASH_RING_SIZE value"):
                AutoRouteConfig.from_env()

    def test_from_env_hash_ring_size_not_number(self) -> None:
        """Should raise on non-numeric HASH_RING_SIZE."""
        with patch.dict(os.environ, {"HASH_RING_SIZE": "abc"}):
            with pytest.raises(ValueError, match="Invalid HASH_RING_SIZE value"):
                AutoRouteConfig.from_env()

    def test_from_env_all_params(self) -> None:
        """Should parse all environment variables."""
        with patch.dict(
            os.environ,
            {
                "ROUTE_ENABLED": "false",
                "ROUTE_TYPE": "hash",
                "SEMANTIC_THRESHOLD": "0.9",
                "HASH_RING_SIZE": "300",
            },
        ):
            config = AutoRouteConfig.from_env()
            assert config.route_enabled is False
            assert config.route_type == "hash"
            assert config.semantic_threshold == 0.9
            assert config.hash_ring_size == 300

    def test_config_is_frozen(self) -> None:
        """Should be immutable (frozen dataclass)."""
        config = AutoRouteConfig()
        with pytest.raises(AttributeError):
            setattr(config, "route_enabled", False)

    def test_from_env_returns_frozen_instance(self) -> None:
        """from_env() should return frozen instance."""
        with patch.dict(os.environ, {}, clear=True):
            config = AutoRouteConfig.from_env()
            with pytest.raises(AttributeError):
                setattr(config, "semantic_threshold", 0.5)
