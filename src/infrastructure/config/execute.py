"""ExecuteConfig — configuration for execute mechanism.

Environment variables:
- EXECUTE_ENABLED: Enable/disable execute mechanism (default: true)
- SANDBOX_TYPE: Sandbox type: docker/gvisor (default: docker)
- SNAPSHOT_TTL_SECONDS: Snapshot TTL in seconds (default: 86400 = 24h)
- RESOURCE_LIMITS: JSON string with resource limits
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExecuteConfig:
    """Configuration for the execute mechanism.

    Uses from_env() class method pattern (same as OtelConfig).

    Attributes:
        enabled: Whether execute mechanism is enabled
        sandbox_type: Type of sandbox (docker/gvisor)
        snapshot_ttl_seconds: TTL for state snapshots (default 24h)
        resource_limits: Resource limit configuration
    """

    enabled: bool = True
    sandbox_type: str = "docker"
    snapshot_ttl_seconds: int = 86400  # 24 hours
    resource_limits: dict[str, Any] | None = None

    @classmethod
    def from_env(cls) -> ExecuteConfig:
        """Load configuration from environment variables.

        Returns:
            ExecuteConfig instance with values from environment
        """
        enabled = os.getenv("EXECUTE_ENABLED", "true").lower() in ("true", "1", "yes")
        sandbox_type = os.getenv("SANDBOX_TYPE", "docker")
        snapshot_ttl = int(os.getenv("SNAPSHOT_TTL_SECONDS", "86400"))

        resource_limits_str = os.getenv("RESOURCE_LIMITS", "{}")
        try:
            resource_limits = json.loads(resource_limits_str)
        except json.JSONDecodeError:
            resource_limits = None

        return cls(
            enabled=enabled,
            sandbox_type=sandbox_type,
            snapshot_ttl_seconds=snapshot_ttl,
            resource_limits=resource_limits,
        )

    def validate(self) -> bool:
        """Validate configuration values.

        Returns:
            True if valid, False otherwise
        """
        if self.sandbox_type not in ("docker", "gvisor"):
            return False
        if self.snapshot_ttl_seconds < 60 or self.snapshot_ttl_seconds > 2592000:
            return False  # 1 minute to 30 days
        return True
