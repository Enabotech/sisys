"""Unit tests for LocalModelHealth infrastructure service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.infrastructure.routing.local_model_health import LocalModelHealth


class TestLocalModelHealth:
    """Test suite for LocalModelHealth."""

    def test_check_returns_true_when_ollama_available(self) -> None:
        """Should return True when Ollama is available."""
        health = LocalModelHealth()
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response
        with patch("src.infrastructure.routing.local_model_health._get_session", return_value=mock_session):
            result = health.check()
        assert result is True

    def test_check_returns_false_when_ollama_unavailable(self) -> None:
        """Should return False when Ollama returns non-200."""
        health = LocalModelHealth()
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_session.get.return_value = mock_response
        with patch("src.infrastructure.routing.local_model_health._get_session", return_value=mock_session):
            result = health.check()
        assert result is False

    def test_check_returns_false_on_connection_error(self) -> None:
        """Should return False when connection fails."""
        health = LocalModelHealth()
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Connection refused")
        with patch("src.infrastructure.routing.local_model_health._get_session", return_value=mock_session):
            result = health.check()
        assert result is False

    def test_default_endpoint(self) -> None:
        """Should use default Ollama endpoint."""
        health = LocalModelHealth()
        assert "localhost" in health.endpoint
        assert "11434" in health.endpoint
