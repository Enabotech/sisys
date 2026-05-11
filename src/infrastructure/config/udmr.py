"""UDMR configuration model."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from src.domain.exceptions import ConfigurationError

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
        ConfigurationError: If no cloud model configuration is provided.
    """

    enabled: bool = True
    local_first: bool = True
    local_timeout: int = DEFAULT_TIMEOUT
    local_model: str = DEFAULT_LOCAL_MODEL
    local_model_type: str | None = None  # "ollama" | "gemini" | "vllm" | None
    cloud_configs: list[CloudModelConfig] = field(default_factory=list)

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
            ConfigurationError: If no cloud model configuration is provided.
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

        if not cloud_configs:
            raise ConfigurationError(
                "No cloud model configuration found. "
                "Set UDMR_CLOUD_0_API_TYPE, UDMR_CLOUD_0_ENDPOINT, "
                "UDMR_CLOUD_0_API_KEY, UDMR_CLOUD_0_MODEL environment variables.",
                context={"module": "udmr"},
            )

        return cls(
            enabled=enabled,
            local_first=local_first,
            local_timeout=local_timeout,
            local_model=local_model,
            local_model_type=local_model_type,
            cloud_configs=cloud_configs,
        )
