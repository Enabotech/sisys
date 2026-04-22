"""TriggerConfig — configuration for trigger mechanism."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class TriggerConfig:
    """Configuration for trigger mechanism.

    Environment variables follow OtelConfig pattern (from_env() class method).
    """

    trigger_enabled: bool = True
    heartbeat_interval_seconds: int = 60
    trigger_max_retries: int = 3

    @classmethod
    def from_env(cls) -> TriggerConfig:
        """Load configuration from environment variables.

        Environment variables:
            TRIGGER_ENABLED: Enable trigger mechanism (default: true)
            HEARTBEAT_INTERVAL_SECONDS: Heartbeat interval in seconds (default: 60)
            TRIGGER_MAX_RETRIES: Max retry attempts on failure (default: 3)

        Returns:
            TriggerConfig instance with values from environment
        """
        enabled_str = os.getenv("TRIGGER_ENABLED", "true").lower()
        interval_str = os.getenv("HEARTBEAT_INTERVAL_SECONDS", "60")
        retries_str = os.getenv("TRIGGER_MAX_RETRIES", "3")

        try:
            interval = int(interval_str)
            if interval <= 0:
                raise ValueError(f"HEARTBEAT_INTERVAL_SECONDS must be positive: {interval}")
        except ValueError as e:
            raise ValueError(f"Invalid HEARTBEAT_INTERVAL_SECONDS value: {interval_str}") from e

        try:
            max_retries = int(retries_str)
            if max_retries < 0:
                raise ValueError(f"TRIGGER_MAX_RETRIES must be non-negative: {max_retries}")
        except ValueError as e:
            raise ValueError(f"Invalid TRIGGER_MAX_RETRIES value: {retries_str}") from e

        return cls(
            trigger_enabled=enabled_str in ("true", "1", "yes", "on"),
            heartbeat_interval_seconds=interval,
            trigger_max_retries=max_retries,
        )
