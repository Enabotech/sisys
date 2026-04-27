"""UDMR configuration model."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_LOCAL_MODEL = "qwen2.5:7b"
DEFAULT_CLOUD_MODELS = ["qwen-turbo", "qwen-plus", "claude-3-haiku"]
DEFAULT_TIMEOUT = 30  # seconds


@dataclass
class UDMRConfig:
    """Configuration for Unified Dynamic Model Router.

    Reads configuration from environment variables:
    - UDMR_ENABLED: Enable/disable UDMR (default: true)
    - UDMR_LOCAL_FIRST: Prefer local model (default: true)
    - UDMR_LOCAL_TIMEOUT: Timeout for local model in seconds (default: 30)
    - UDMR_LOCAL_MODEL: Local model name (default: qwen2.5:7b)
    - UDMR_CLOUD_MODELS: Comma-separated cloud model names
    """

    enabled: bool = True
    local_first: bool = True
    local_timeout: int = DEFAULT_TIMEOUT
    local_model: str = DEFAULT_LOCAL_MODEL
    cloud_models: list[str] = field(default_factory=lambda: DEFAULT_CLOUD_MODELS.copy())

    @classmethod
    def from_env(cls) -> UDMRConfig:
        """Create config from environment variables.

        Returns:
            UDMRConfig instance with values from environment.
        """
        enabled = os.getenv("UDMR_ENABLED", "true").lower() in ("true", "1", "yes")
        local_first = os.getenv("UDMR_LOCAL_FIRST", "true").lower() in ("true", "1", "yes")
        try:
            local_timeout = int(os.getenv("UDMR_LOCAL_TIMEOUT", str(DEFAULT_TIMEOUT)))
            if local_timeout < 0:
                local_timeout = DEFAULT_TIMEOUT
        except ValueError:
            local_timeout = DEFAULT_TIMEOUT
        local_model = os.getenv("UDMR_LOCAL_MODEL", DEFAULT_LOCAL_MODEL)
        cloud_models_str = os.getenv("UDMR_CLOUD_MODELS", "")
        if cloud_models_str:
            cloud_models = [m.strip() for m in cloud_models_str.split(",") if m.strip()]
        else:
            cloud_models = DEFAULT_CLOUD_MODELS.copy()

        return cls(
            enabled=enabled,
            local_first=local_first,
            local_timeout=local_timeout,
            local_model=local_model,
            cloud_models=cloud_models,
        )
