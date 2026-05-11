"""UDMR configuration model."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_LOCAL_MODEL = "qwen2.5:7b"
DEFAULT_CLOUD_MODELS = ["qwen-turbo", "qwen-plus", "claude-3-haiku"]
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
    - UDMR_CLOUD_MODELS: Comma-separated cloud model names
    - UDMR_CLOUD_{n}_TYPE: Cloud model API type (openai | anthropic | custom)
    - UDMR_CLOUD_{n}_ENDPOINT: Cloud model API endpoint
    - UDMR_CLOUD_{n}_API_KEY: Cloud model API key
    - UDMR_CLOUD_{n}_MODEL: Cloud model name
    - UDMR_CLOUD_{n}_ENABLED: Cloud model enabled (true | false)
    """

    enabled: bool = True
    local_first: bool = True
    local_timeout: int = DEFAULT_TIMEOUT
    local_model: str = DEFAULT_LOCAL_MODEL
    cloud_models: list[str] = field(default_factory=lambda: DEFAULT_CLOUD_MODELS.copy())
    local_model_type: str | None = None  # "ollama" | "gemini" | "vllm" | None
    cloud_configs: list[CloudModelConfig] = field(default_factory=list)  # Cloud model configurations

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
        local_model_type = os.getenv("UDMR_LOCAL_MODEL_TYPE", None)
        cloud_models_env = os.getenv("UDMR_CLOUD_MODELS")
        if cloud_models_env is not None and cloud_models_env:
            cloud_models = [m.strip() for m in cloud_models_env.split(",") if m.strip()]
        elif cloud_models_env is None:
            cloud_models = DEFAULT_CLOUD_MODELS.copy()
        else:
            cloud_models = []

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

        # Backward compatibility: if no cloud_configs but cloud_models set, create from cloud_models
        if not cloud_configs and cloud_models:
            for model in cloud_models:
                cloud_configs.append(
                    CloudModelConfig(
                        api_type="openai",
                        endpoint="",
                        api_key="",
                        model=model,
                        enabled=True,
                    )
                )

        return cls(
            enabled=enabled,
            local_first=local_first,
            local_timeout=local_timeout,
            local_model=local_model,
            cloud_models=cloud_models,
            local_model_type=local_model_type,
            cloud_configs=cloud_configs,
        )
