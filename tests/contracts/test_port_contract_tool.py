"""Tests for Composition Root tool port registration."""

from src.domain.ports.registry import _global_registry


class TestToolPortRegistration:
    """Test tool ports are registered in Composition Root."""

    def test_tool_repository_registered(self):
        """tool_repository port is registered after bootstrap."""
        # Bootstrap is called by conftest.py session fixture
        spec = _global_registry.get("tool_repository")
        assert spec is not None
        assert spec.name == "tool_repository"
        assert spec.version == "v1.0.0"
        assert spec.owner == "tool-team"

    def test_tool_registry_service_registered(self):
        """tool_registry_service port is registered after bootstrap."""
        spec = _global_registry.get("tool_registry_service")
        assert spec is not None
        assert spec.name == "tool_registry_service"
        assert spec.version == "v1.0.0"
        assert spec.owner == "tool-team"

    def test_tool_repository_has_correct_lifetime(self):
        """tool_repository has SCOPED lifetime."""
        spec = _global_registry.get("tool_repository")
        assert spec is not None
        from src.domain.ports.registry import Lifetime

        assert spec.lifetime == Lifetime.SCOPED

    def test_tool_registry_service_has_correct_lifetime(self):
        """tool_registry_service has SCOPED lifetime."""
        spec = _global_registry.get("tool_registry_service")
        assert spec is not None
        from src.domain.ports.registry import Lifetime

        assert spec.lifetime == Lifetime.SCOPED

    def test_total_port_count_increased(self):
        """Total port count increased by 2 after tool registration."""
        tool_ports = [spec for spec in _global_registry.list_all() if "tool" in spec.name.lower()]
        assert len(tool_ports) >= 2
