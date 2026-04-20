"""AuditConfig — Audit logging configuration.

Reference: Story 1.4-1.9 Config pattern (XxxConfig + from_env()).
Reference: Story 1.10 SDD规范定义
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class AuditConfig:
    """Audit logging configuration.

    Attributes:
        enabled: Whether audit logging is enabled.
        storage_backend: Storage backend ("postgresql" MVP, "minio" V1+).
        retention_days: Number of days to retain audit logs.
        archive_enabled: Whether archival to WORM storage is enabled.
        worm_bucket: MinIO bucket name for WORM storage.
        outbox_poll_interval: Outbox processor poll interval in seconds.
        outbox_batch_size: Number of outbox entries to process per batch.
        max_retries: Maximum retry attempts for failed outbox entries.
        checksum_algorithm: Algorithm for integrity checksums ("sha256").
        query_timeout: Query timeout in seconds.
        page_size_default: Default page size for queries.
        page_size_max: Maximum allowed page size.
        event_types_enabled: List of event types to record (empty = all).
        actor_resolver: Actor resolution strategy ("auth_service" MVP).
    """

    enabled: bool = True
    storage_backend: str = "postgresql"
    retention_days: int = 2555  # 7 years
    archive_enabled: bool = False
    worm_bucket: str = "audit-archives"
    outbox_poll_interval: int = 5
    outbox_batch_size: int = 100
    max_retries: int = 3
    checksum_algorithm: str = "sha256"
    query_timeout: int = 30
    page_size_default: int = 50
    page_size_max: int = 1000
    event_types_enabled: list[str] = field(default_factory=list)
    actor_resolver: str = "auth_service"

    @classmethod
    def from_env(cls) -> AuditConfig:
        """Load configuration from environment variables.

        Environment variables:
            AUDIT_ENABLED: Enable audit logging (default: true).
            AUDIT_STORAGE_BACKEND: Storage backend (default: postgresql).
            AUDIT_RETENTION_DAYS: Retention period in days (default: 2555).
            AUDIT_ARCHIVE_ENABLED: Enable WORM archival (default: false).
            AUDIT_WORM_BUCKET: MinIO bucket for WORM storage.
            AUDIT_OUTBOX_POLL_INTERVAL: Outbox poll interval in seconds.
            AUDIT_OUTBOX_BATCH_SIZE: Batch size for outbox processing.
            AUDIT_MAX_RETRIES: Maximum retry attempts.
            AUDIT_CHECKSUM_ALGORITHM: Checksum algorithm (default: sha256).
            AUDIT_QUERY_TIMEOUT: Query timeout in seconds.
            AUDIT_PAGE_SIZE_DEFAULT: Default page size.
            AUDIT_PAGE_SIZE_MAX: Maximum page size.
            AUDIT_EVENT_TYPES_ENABLED: Comma-separated event types to record.
            AUDIT_ACTOR_RESOLVER: Actor resolution strategy.
        """

        def _int_env(key: str, default: int) -> int:
            """Parse integer from environment variable with fallback."""
            try:
                return int(os.getenv(key, str(default)))
            except ValueError:
                return default

        event_types_raw = os.getenv("AUDIT_EVENT_TYPES_ENABLED", "")
        event_types = [et.strip() for et in event_types_raw.split(",") if et.strip()]

        return cls(
            enabled=os.getenv("AUDIT_ENABLED", "true").lower() in ("true", "1", "yes"),
            storage_backend=os.getenv("AUDIT_STORAGE_BACKEND", "postgresql"),
            retention_days=_int_env("AUDIT_RETENTION_DAYS", 2555),
            archive_enabled=os.getenv("AUDIT_ARCHIVE_ENABLED", "false").lower() in ("true", "1", "yes"),
            worm_bucket=os.getenv("AUDIT_WORM_BUCKET", "audit-archives"),
            outbox_poll_interval=_int_env("AUDIT_OUTBOX_POLL_INTERVAL", 5),
            outbox_batch_size=_int_env("AUDIT_OUTBOX_BATCH_SIZE", 100),
            max_retries=_int_env("AUDIT_MAX_RETRIES", 3),
            checksum_algorithm=os.getenv("AUDIT_CHECKSUM_ALGORITHM", "sha256"),
            query_timeout=_int_env("AUDIT_QUERY_TIMEOUT", 30),
            page_size_default=_int_env("AUDIT_PAGE_SIZE_DEFAULT", 50),
            page_size_max=_int_env("AUDIT_PAGE_SIZE_MAX", 1000),
            event_types_enabled=event_types,
            actor_resolver=os.getenv("AUDIT_ACTOR_RESOLVER", "auth_service"),
        )


# Global config instance (lazy loading)
_audit_config: AuditConfig | None = None


def get_audit_config() -> AuditConfig:
    """Get the global AuditConfig instance (lazy loading).

    Returns:
        AuditConfig: The global audit configuration.
    """
    global _audit_config
    if _audit_config is None:
        _audit_config = AuditConfig.from_env()
    return _audit_config
