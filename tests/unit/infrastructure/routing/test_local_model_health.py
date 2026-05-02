"""Unit tests for LocalModelHealth (OllamaHealthAdapter) infrastructure service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.infrastructure.routing.local_model_health import LocalModelHealth


class TestLocalModelHealth:
    """Test suite for LocalModelHealth (OllamaHealthAdapter)."""

    @pytest.mark.asyncio
    async def test_check_returns_true_when_ollama_available(self) -> None:
        """Should return True when Ollama is available."""
        health = LocalModelHealth()

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.aclose = AsyncMock()

        with patch.object(health, "_client", mock_client):
            result = await health.check()

        assert result is True
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_returns_false_when_ollama_unavailable(self) -> None:
        """Should return False when Ollama returns non-200."""
        health = LocalModelHealth(endpoint="http://localhost:11434/api/health", timeout=0.1)

        mock_response = MagicMock()
        mock_response.status_code = 503

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.aclose = AsyncMock()

        with patch.object(health, "_client", mock_client):
            result = await health.check()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_returns_false_on_connection_error(self) -> None:
        """Should return False when connection fails."""
        health = LocalModelHealth(endpoint="http://invalid-endpoint:9999/api/health", timeout=0.1)

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.RequestError("Connection refused")
        mock_client.aclose = AsyncMock()

        with patch.object(health, "_client", mock_client):
            result = await health.check()

        assert result is False

    def test_default_endpoint(self) -> None:
        """Should use default Ollama endpoint."""
        health = LocalModelHealth()
        assert "localhost" in health._endpoint
        assert "11434" in health._endpoint
