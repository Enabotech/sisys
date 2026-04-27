"""Local model health check for Ollama."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434/api/health"

_session = None


def _get_session() -> requests.Session:
    """Get or create a shared session for connection pooling."""
    global _session
    if _session is None:
        _session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=Retry(total=0),
        )
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)
    return _session


class LocalModelHealth:
    """Health check for local Ollama model.

    Checks if Ollama service is available and responding.
    """

    def __init__(self, endpoint: str | None = None) -> None:
        """Initialize with optional custom endpoint.

        Args:
            endpoint: Custom Ollama health endpoint. Defaults to localhost:11434.
        """
        self.endpoint = endpoint or DEFAULT_OLLAMA_ENDPOINT

    def check(self) -> bool:
        """Check if local model is healthy.

        Returns:
            True if Ollama is available, False otherwise.
        """
        try:
            session = _get_session()
            response = session.get(self.endpoint, timeout=5)
            return response.status_code == 200
        except Exception:
            return False
