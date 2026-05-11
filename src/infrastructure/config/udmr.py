"""UDMR configuration model."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_LOCAL_MODEL = "qwen2.5:7b"
DEFAULT_TIMEOUT = 30  # seconds


@dataclass(frozen=True)
class CloudModelConfig:
    """Configuration for a single cloud model provider.

    Attributes:
        api_type: API format type - "openai", "anthropic", or "custom"
        endpoint: API endpoint URL
        api_key: API key (can reference environment variable)
        model: Model name
        enabled: Whether this cloud config is enabled
    """

    api_type: str = "openai"
    endpoint: str = ""
    api_key: str = ""
    model: str = ""
    enabled: bool = True


# Default cloud configs when no environment variables are set
_DEFAULT_CLOUD_CONFIGS: list[CloudModelConfig] = [
    CloudModelConfig(api_type="openai", model="qwen-turbo"),
    CloudModelConfig(api_type="openai", model="qwen-plus"),
    CloudModelConfig(api_type="openai", model="claude-3-haiku"),
]


@dataclass(frozen=True)
class UDMRConfig:
    """Configuration for Unified Dynamic Model Router.

    Reads configuration from environment variables:
    - UDMR_ENABLED: Enable/disable UDMR (default: true)
    - UDMR_LOCAL_FIRST: Prefer local model (default: true)
    - UDMR_LOCAL_TIMEOUT: Timeout for local model in seconds (default: 30)
    - UDMR_LOCAL_MODEL: Local model name (default: qwen2.5:7b)
    - UDMR_CLOUD_{n}_API_TYPE: Cloud model API type (openai | anthropic | custom)
    - UDMR_CLOUD_{n}_ENDPOINT: Cloud model API endpoint
    - UDMR_CLOUD_{n}_API_KEY: Cloud model API key
    - UDMR_CLOUD_{n}_MODEL: Cloud model name
    - UDMR_CLOUD_{n}_ENABLED: Cloud model enabled (true | false)

    Raises:
        ValueError: If no cloud model configuration is provided and no defaults available.
    """

    enabled: bool = True
    local_first: bool = True
    local_timeout: int = DEFAULT_TIMEOUT
    local_model: str = DEFAULT_LOCAL_MODEL
    local_model_type: str | None = None  # "ollama" | "gemini" | "vllm" | None
    cloud_configs: list[CloudModelConfig] = field(default_factory=lambda: _DEFAULT_CLOUD_CONFIGS.copy())

    @property
    def cloud_models(self) -> list[str]:
        """Get list of cloud model names from cloud_configs."""
        return [c.model for c in self.cloud_configs if c.enabled]

    @classmethod
    def from_env(cls) -> UDMRConfig:
        """Create config from environment variables.

        Returns:
            UDMRConfig instance with values from environment.

        Raises:
            ValueError: If no cloud model configuration is provided.
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
        local_model_type = os.getenv("UDMR_LOCAL_MODEL_TYPE", None)

        # Parse cloud_configs from UDMR_CLOUD_{n}_* environment variables
        cloud_configs: list[CloudModelConfig] = []
        for i in range(10):
            c_type = os.getenv(f"UDMR_CLOUD_{i}_API_TYPE")
            if c_type is None:
                break
            cloud_configs.append(
                CloudModelConfig(
                    api_type=c_type,
                    endpoint=os.getenv(f"UDMR_CLOUD_{i}_ENDPOINT", ""),
                    api_key=os.getenv(f"UDMR_CLOUD_{i}_API_KEY", ""),
                    model=os.getenv(f"UDMR_CLOUD_{i}_MODEL", ""),
                    enabled=os.getenv(f"UDMR_CLOUD_{i}_ENABLED", "true").lower() in ("true", "1"),
                )
            )

        # Use provided cloud_configs if available, otherwise use defaults
        if not cloud_configs:
            cloud_configs = _DEFAULT_CLOUD_CONFIGS.copy()

        return cls(
            enabled=enabled,
            local_first=local_first,
            local_timeout=local_timeout,
            local_model=local_model,
            local_model_type=local_model_type,
            cloud_configs=cloud_configs,
        )
