"""Unit tests for LocalModelHealthFacade and related components."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.local_model_health_facade import (
    LocalModelHealthFacade,
)
from src.domain.ports.health_check import HealthCheckPort
from src.domain.ports.health_check_factory import HealthCheckerFactory
from src.infrastructure.routing.local_model_health import (
    LocalModelHealth,
    create_local_model_health_facade,
)
from src.infrastructure.routing.ollama_health import (
    OllamaHealthAdapter,
    OllamaHealthCheckerFactory,
)


class TestOllamaHealthAdapter:
    """Test suite for OllamaHealthAdapter."""

    def test_default_endpoint(self) -> None:
        """Should use default Ollama endpoint."""
        from src.infrastructure.routing.ollama_health import DEFAULT_OLLAMA_ENDPOINT

        adapter = OllamaHealthAdapter()
        assert adapter._endpoint == DEFAULT_OLLAMA_ENDPOINT

    def test_custom_endpoint(self) -> None:
        """Should accept custom endpoint."""
        adapter = OllamaHealthAdapter(endpoint="http://custom:9999/api/health")
        assert adapter._endpoint == "http://custom:9999/api/health"

    def test_custom_timeout(self) -> None:
        """Should accept custom timeout."""
        adapter = OllamaHealthAdapter(timeout=10.0)
        assert adapter._timeout == 10.0

    @pytest.mark.asyncio
    async def test_check_returns_true_on_healthy_response(self) -> None:
        """Should return True when Ollama returns 200."""
        from unittest.mock import AsyncMock, patch

        adapter = OllamaHealthAdapter()
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(adapter, "_client", None):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            adapter._client = mock_client

            result = await adapter.check()
            assert result is True

    @pytest.mark.asyncio
    async def test_check_returns_false_on_unhealthy_response(self) -> None:
        """Should return False when Ollama returns non-200."""
        from unittest.mock import AsyncMock, MagicMock

        adapter = OllamaHealthAdapter()
        mock_response = MagicMock()
        mock_response.status_code = 503

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        adapter._client = mock_client

        result = await adapter.check()
        assert result is False

    @pytest.mark.asyncio
    async def test_check_returns_false_on_request_error(self) -> None:
        """Should return False when request fails."""
        import httpx

        adapter = OllamaHealthAdapter()
        adapter._client = AsyncMock()
        adapter._client.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))

        result = await adapter.check()
        assert result is False

    @pytest.mark.asyncio
    async def test_check_returns_false_on_timeout(self) -> None:
        """Should return False when request times out."""
        import httpx

        adapter = OllamaHealthAdapter()
        adapter._client = AsyncMock()
        adapter._client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        result = await adapter.check()
        assert result is False

    @pytest.mark.asyncio
    async def test_close_resets_client(self) -> None:
        """Should reset client to None after close."""
        from unittest.mock import AsyncMock

        adapter = OllamaHealthAdapter()
        mock_client = AsyncMock()
        adapter._client = mock_client

        await adapter.close()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_close_handles_none_client(self) -> None:
        """Should handle close when client is None."""
        adapter = OllamaHealthAdapter()
        adapter._client = None

        await adapter.close()
        assert adapter._client is None


class TestOllamaHealthCheckerFactory:
    """Test suite for OllamaHealthCheckerFactory."""

    def test_creates_ollama_health_adapter(self) -> None:
        """Should create OllamaHealthAdapter."""
        factory = OllamaHealthCheckerFactory(config=None)
        adapter = factory.create()
        assert isinstance(adapter, OllamaHealthAdapter)

    def test_uses_config_local_model_as_endpoint(self) -> None:
        """Should use config.local_model as endpoint."""
        from src.infrastructure.config.udmr import UDMRConfig

        config = UDMRConfig(local_model="http://custom:1234/health")
        factory = OllamaHealthCheckerFactory(config=config)
        adapter = factory.create()
        assert "custom:1234" in getattr(adapter, "_endpoint")


class TestLocalModelHealthFacade:
    """Test suite for LocalModelHealthFacade."""

    def test_requires_factory(self) -> None:
        """Should require factory parameter."""
        mock_factory = MagicMock(spec=HealthCheckerFactory)
        mock_factory.create.return_value = MagicMock(spec=HealthCheckPort)
        facade = LocalModelHealthFacade(factory=mock_factory)
        assert facade._factory is mock_factory

    def test_accepts_config_as_optional(self) -> None:
        """Should accept config as optional second parameter."""
        mock_factory = MagicMock(spec=HealthCheckerFactory)
        mock_factory.create.return_value = MagicMock(spec=HealthCheckPort)
        facade = LocalModelHealthFacade(factory=mock_factory, config=None)
        assert facade._config is None

    def test_creates_adapter_via_factory(self) -> None:
        """Should create adapter via injected factory."""
        mock_adapter = MagicMock(spec=HealthCheckPort)
        mock_factory = MagicMock(spec=HealthCheckerFactory)
        mock_factory.create.return_value = mock_adapter

        facade = LocalModelHealthFacade(factory=mock_factory)
        assert facade._health_checker is mock_adapter

    @pytest.mark.asyncio
    async def test_check_delegates_to_adapter(self) -> None:
        """Should delegate check to adapter."""
        mock_adapter = AsyncMock(spec=HealthCheckPort)
        mock_adapter.check.return_value = True

        mock_factory = MagicMock(spec=HealthCheckerFactory)
        mock_factory.create.return_value = mock_adapter

        facade = LocalModelHealthFacade(factory=mock_factory)
        result = await facade.check()

        assert result is True
        mock_adapter.check.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_delegates_to_adapter(self) -> None:
        """Should delegate close to adapter."""
        mock_adapter = AsyncMock(spec=HealthCheckPort)
        mock_adapter.check.return_value = True
        mock_adapter.close.return_value = None

        mock_factory = MagicMock(spec=HealthCheckerFactory)
        mock_factory.create.return_value = mock_adapter

        facade = LocalModelHealthFacade(factory=mock_factory)
        _ = facade._health_checker  # Trigger creation
        await facade.close()

        mock_adapter.close.assert_called_once()


class TestLocalModelHealthFactoryFunction:
    """Test suite for create_local_model_health_facade."""

    def test_creates_facade_with_ollama_factory(self) -> None:
        """Should create facade with OllamaHealthCheckerFactory."""
        facade = create_local_model_health_facade(config=None)
        assert isinstance(facade, LocalModelHealthFacade)
        assert isinstance(facade._health_checker, OllamaHealthAdapter)

    def test_uses_config_for_factory(self) -> None:
        """Should pass config to factory."""
        from src.infrastructure.config.udmr import UDMRConfig

        config = UDMRConfig(local_model="http://custom:9999/health")
        facade = create_local_model_health_facade(config=config)
        assert "custom:9999" in getattr(facade._health_checker, "_endpoint")

    def test_raises_for_gemini_model_type(self) -> None:
        """Should raise NotImplementedError for gemini model type."""
        from src.infrastructure.config.udmr import UDMRConfig

        config = UDMRConfig()
        setattr(config, "local_model_type", "gemini")
        with pytest.raises(NotImplementedError):
            create_local_model_health_facade(config=config)

    def test_raises_for_vllm_model_type(self) -> None:
        """Should raise NotImplementedError for vllm model type."""
        from src.infrastructure.config.udmr import UDMRConfig

        config = UDMRConfig()
        setattr(config, "local_model_type", "vllm")
        with pytest.raises(NotImplementedError):
            create_local_model_health_facade(config=config)


class TestLocalModelHealthBackwardCompat:
    """Test suite for LocalModelHealth backward compatibility."""

    def test_returns_local_model_health_facade(self) -> None:
        """Should return LocalModelHealthFacade instance."""
        health = LocalModelHealth()
        assert isinstance(health, LocalModelHealthFacade)

    def test_accepts_config_parameter(self) -> None:
        """Should accept UDMRConfig parameter."""
        from src.infrastructure.config.udmr import UDMRConfig

        config = UDMRConfig()
        health = LocalModelHealth(config=config)
        assert isinstance(health, LocalModelHealthFacade)

    def test_returns_facade_with_ollama_adapter(self) -> None:
        """Should return facade with OllamaHealthAdapter."""
        health = LocalModelHealth()
        assert isinstance(health._health_checker, OllamaHealthAdapter)

    def test_module_has_no_attribute_raises_error(self) -> None:
        """Accessing non-existent attribute should raise AttributeError."""
        import src.infrastructure.routing.local_model_health as module

        with pytest.raises(AttributeError):
            getattr(module, "NonExistentClass")
