"""Composition root — all port registrations happen here.

This is the single location where all port implementations are registered
with the global registry. No other module should register ports.

This module follows hexagonal architecture principles:
- Domain layer defines ports (interfaces)
- Infrastructure layer implements ports
- This composition root wires them together
"""

from __future__ import annotations

import logging

from src.domain.ports.registry import (
    Lifetime,
    _global_registry,
    register_port,
)

logger = logging.getLogger(__name__)


def bootstrap() -> None:
    """Bootstrap the port registry with all known ports.

    Called once at application startup.
    """
    logger.info("Bootstrapping port registry...")

    # Import all domain ports for registration
    # Storage layer ports
    from src.application.ports.compressor_service import CompressorService
    from src.application.ports.event_subscriber import EventSubscriber
    from src.application.ports.exception_metrics_port import ExceptionMetricsPort
    from src.application.ports.metrics_port import MetricsPort
    from src.application.ports.public_blackboard import PublicBlackboard
    from src.application.ports.sandbox_port import SandboxExecutor

    # Application layer ports
    from src.application.ports.semantic_cache import SemanticCache
    from src.application.ports.text_extractor_service import TextExtractorService
    from src.domain.ports.audit_repository import AuditRepositoryPort
    from src.domain.ports.audit_service import AuditServicePort

    # Auth ports
    from src.domain.ports.auth_service import AuthServicePort

    # Other domain ports
    # Compliance ports
    from src.domain.ports.compliance_gateway import ComplianceGatewayPort
    from src.domain.ports.cross_border_transfer_service import CrossBorderTransferServicePort
    from src.domain.ports.data_residency_enforcer import DataResidencyEnforcerPort

    # Event ports
    from src.domain.ports.event_publisher import EventPublisher
    from src.domain.ports.hash_router_protocol import HashRouterProtocol
    from src.domain.ports.l0_storage import L0StoragePort
    from src.domain.ports.l1_cache import L1CachePort
    from src.domain.ports.login_attempt_repository import LoginAttemptRepositoryPort
    from src.domain.ports.outbox import OutboxRepository
    from src.domain.ports.password_validation_service import PasswordValidationServicePort
    from src.domain.ports.permission_service import PermissionServicePort
    from src.domain.ports.pipl_compliance_service import PIPLComplianceServicePort
    from src.domain.ports.role_repository import RoleRepositoryPort

    # Service protocols (migrated from services)
    from src.domain.ports.sandbox_executor_protocol import SandboxExecutorProtocol
    from src.domain.ports.semantic_router_protocol import SemanticRouterProtocol
    from src.domain.ports.sensitive_data_detector import SensitiveDataDetectorPort
    from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
    from src.domain.ports.token_blacklist import TokenBlacklistPort

    # Repository ports
    from src.domain.ports.user_repository import UserRepositoryPort
    from src.domain.ports.user_role_repository import UserRoleRepositoryPort
    from src.domain.ports.whitelist_service import WhitelistServicePort

    # === Storage Layer ===
    register_port(
        name="l0_storage",
        version="v1.0.0",
        interface=L0StoragePort,
        impl="src.infrastructure.storage.file_memory_adapter.FileMemoryAdapter",
        module="src.infrastructure.storage.file_memory_adapter",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
    )

    register_port(
        name="l1_cache",
        version="v1.0.0",
        interface=L1CachePort,
        impl="src.infrastructure.storage.redis.redis_memory_cache.RedisMemoryCache",
        module="src.infrastructure.storage.redis.redis_memory_cache",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
        tags=("redis", "cache"),
    )

    # === Repository Ports ===
    register_port(
        name="user_repo",
        version="v1.0.0",
        interface=UserRepositoryPort,
        impl="src.infrastructure.storage.postgresql.user_repository.SqlAlchemyUserRepository",
        module="src.infrastructure.storage.postgresql.user_repository",
        lifetime=Lifetime.SCOPED,
        owner="platform-team",
    )

    register_port(
        name="role_repo",
        version="v1.0.0",
        interface=RoleRepositoryPort,
        impl="src.infrastructure.storage.postgresql.role_repository.SqlAlchemyRoleRepository",
        module="src.infrastructure.storage.postgresql.role_repository",
        lifetime=Lifetime.SCOPED,
        owner="platform-team",
    )

    register_port(
        name="user_role_repo",
        version="v1.0.0",
        interface=UserRoleRepositoryPort,
        impl="src.infrastructure.storage.postgresql.user_role_repository.SqlAlchemyUserRoleRepository",
        module="src.infrastructure.storage.postgresql.user_role_repository",
        lifetime=Lifetime.SCOPED,
        owner="platform-team",
    )

    register_port(
        name="login_attempt_repo",
        version="v1.0.0",
        interface=LoginAttemptRepositoryPort,
        impl="src.infrastructure.storage.postgresql.login_attempt_repository.SqlAlchemyLoginAttemptRepository",
        module="src.infrastructure.storage.postgresql.login_attempt_repository",
        lifetime=Lifetime.SCOPED,
        owner="platform-team",
    )

    register_port(
        name="audit_repo",
        version="v1.0.0",
        interface=AuditRepositoryPort,
        impl="src.infrastructure.storage.postgresql.audit_repository.SqlAlchemyAuditRepository",
        module="src.infrastructure.storage.postgresql.audit_repository",
        lifetime=Lifetime.SCOPED,
        owner="compliance-team",
    )

    register_port(
        name="audit_service",
        version="v1.0.0",
        interface=AuditServicePort,
        impl="src.infrastructure.services.audit_service_impl.AuditServiceImpl",
        module="src.infrastructure.services.audit_service_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
    )

    # === Auth Ports ===
    register_port(
        name="auth_service",
        version="v1.0.0",
        interface=AuthServicePort,
        impl="src.infrastructure.services.auth_service_impl.AuthServiceImpl",
        module="src.infrastructure.services.auth_service_impl",
        lifetime=Lifetime.SINGLETON,
        owner="security-team",
    )

    register_port(
        name="permission_service",
        version="v1.0.0",
        interface=PermissionServicePort,
        impl="src.infrastructure.services.permission_service_impl.PermissionServiceImpl",
        module="src.infrastructure.services.permission_service_impl",
        lifetime=Lifetime.SINGLETON,
        owner="security-team",
    )

    register_port(
        name="token_blacklist",
        version="v1.0.0",
        interface=TokenBlacklistPort,
        impl="src.infrastructure.services.token_blacklist_impl.RedisTokenBlacklist",
        module="src.infrastructure.services.token_blacklist_impl",
        lifetime=Lifetime.SCOPED,
        owner="security-team",
    )

    register_port(
        name="password_validation",
        version="v1.0.0",
        interface=PasswordValidationServicePort,
        impl="src.infrastructure.services.password_validation_impl.PasswordValidationService",
        module="src.infrastructure.services.password_validation_impl",
        lifetime=Lifetime.SINGLETON,
        owner="security-team",
    )

    # === Event Ports ===
    register_port(
        name="event_publisher",
        version="v1.0.0",
        interface=EventPublisher,
        impl="src.infrastructure.messaging.dual_channel_event_bus.DualChannelEventBus",
        module="src.infrastructure.messaging.dual_channel_event_bus",
        lifetime=Lifetime.SINGLETON,
        owner="messaging-team",
        tags=("redis", "rabbitmq"),
    )

    register_port(
        name="outbox_repo",
        version="v1.0.0",
        interface=OutboxRepository,
        impl="src.infrastructure.storage.postgresql.outbox_repository.SqlAlchemyOutboxRepository",
        module="src.infrastructure.storage.postgresql.outbox_repository",
        lifetime=Lifetime.SCOPED,
        owner="messaging-team",
    )

    # === Compliance Ports ===
    register_port(
        name="compliance_gateway",
        version="v1.0.0",
        interface=ComplianceGatewayPort,
        impl="src.infrastructure.services.compliance_gateway_impl.ComplianceGateway",
        module="src.infrastructure.services.compliance_gateway_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
    )

    register_port(
        name="sensitive_data_detector",
        version="v1.0.0",
        interface=SensitiveDataDetectorPort,
        impl="src.infrastructure.services.sensitive_data_detector_impl.SensitiveDataDetector",
        module="src.infrastructure.services.sensitive_data_detector_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
    )

    register_port(
        name="data_residency_enforcer",
        version="v1.0.0",
        interface=DataResidencyEnforcerPort,
        impl="src.infrastructure.services.data_residency_enforcer_impl.DataResidencyEnforcer",
        module="src.infrastructure.services.data_residency_enforcer_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
    )

    register_port(
        name="whitelist_service",
        version="v1.0.0",
        interface=WhitelistServicePort,
        impl="src.infrastructure.services.whitelist_service_impl.WhitelistService",
        module="src.infrastructure.services.whitelist_service_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
    )

    register_port(
        name="pipl_compliance",
        version="v1.0.0",
        interface=PIPLComplianceServicePort,
        impl="src.infrastructure.services.pipl_compliance_impl.PIPLComplianceService",
        module="src.infrastructure.services.pipl_compliance_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
    )

    register_port(
        name="cross_border_transfer",
        version="v1.0.0",
        interface=CrossBorderTransferServicePort,
        impl="src.infrastructure.services.cross_border_transfer_impl.CrossBorderTransferService",
        module="src.infrastructure.services.cross_border_transfer_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
    )

    # === Application Layer Ports ===
    register_port(
        name="semantic_cache",
        version="v1.0.0",
        interface=SemanticCache,
        impl="src.infrastructure.storage.redis.semantic_cache.RedisSemanticCache",
        module="src.infrastructure.storage.redis.semantic_cache",
        lifetime=Lifetime.SCOPED,
        owner="cache-team",
    )

    register_port(
        name="public_blackboard",
        version="v1.0.0",
        interface=PublicBlackboard,
        impl="src.infrastructure.storage.redis.public_blackboard.RedisPublicBlackboard",
        module="src.infrastructure.storage.redis.public_blackboard",
        lifetime=Lifetime.SCOPED,
        owner="collaboration-team",
    )

    register_port(
        name="sandbox_executor",
        version="v1.0.0",
        interface=SandboxExecutor,
        impl="src.infrastructure.sandbox.docker_sandbox_adapter.DockerSandboxAdapter",
        module="src.infrastructure.sandbox.docker_sandbox_adapter",
        lifetime=Lifetime.TRANSIENT,
        owner="sandbox-team",
    )

    register_port(
        name="metrics",
        version="v1.0.0",
        interface=MetricsPort,
        impl="src.infrastructure.monitoring.metrics_adapter.PrometheusMetricsAdapter",
        module="src.infrastructure.monitoring.metrics_adapter",
        lifetime=Lifetime.SINGLETON,
        owner="monitoring-team",
    )

    register_port(
        name="exception_metrics",
        version="v1.0.0",
        interface=ExceptionMetricsPort,
        impl="src.infrastructure.monitoring.exception_metrics_adapter.ExceptionMetricsAdapter",
        module="src.infrastructure.monitoring.exception_metrics_adapter",
        lifetime=Lifetime.SINGLETON,
        owner="monitoring-team",
    )

    register_port(
        name="text_extractor",
        version="v1.0.0",
        interface=TextExtractorService,
        impl="src.infrastructure.document.text_extractor_impl.TextExtractorService",
        module="src.infrastructure.document.text_extractor_impl",
        lifetime=Lifetime.SINGLETON,
        owner="document-team",
    )

    register_port(
        name="compressor",
        version="v1.0.0",
        interface=CompressorService,
        impl="src.infrastructure.storage.compressor_impl.CompressorService",
        module="src.infrastructure.storage.compressor_impl",
        lifetime=Lifetime.SINGLETON,
        owner="storage-team",
    )

    register_port(
        name="event_subscriber",
        version="v1.0.0",
        interface=EventSubscriber,
        impl="src.infrastructure.messaging.redis_event_subscriber.RedisEventSubscriber",
        module="src.infrastructure.messaging.redis_event_subscriber",
        lifetime=Lifetime.SCOPED,
        owner="messaging-team",
    )

    # === Service Protocols ===
    register_port(
        name="sandbox_executor_protocol",
        version="v1.0.0",
        interface=SandboxExecutorProtocol,
        impl="src.infrastructure.sandbox.docker_sandbox_adapter.DockerSandboxAdapter",
        module="src.infrastructure.sandbox.docker_sandbox_adapter",
        lifetime=Lifetime.TRANSIENT,
        owner="sandbox-team",
    )

    register_port(
        name="snapshot_repository",
        version="v1.0.0",
        interface=SnapshotRepositoryProtocol,
        impl="src.infrastructure.storage.redis_snapshot_store.RedisSnapshotStore",
        module="src.infrastructure.storage.redis_snapshot_store",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
    )

    register_port(
        name="hash_router",
        version="v1.0.0",
        interface=HashRouterProtocol,
        impl="src.infrastructure.routing.hash_router.HashRouter",
        module="src.infrastructure.routing.hash_router",
        lifetime=Lifetime.SINGLETON,
        owner="routing-team",
    )

    register_port(
        name="semantic_router",
        version="v1.0.0",
        interface=SemanticRouterProtocol,
        impl="src.infrastructure.routing.semantic_router.SemanticRouter",
        module="src.infrastructure.routing.semantic_router",
        lifetime=Lifetime.SINGLETON,
        owner="routing-team",
    )

    logger.info("Registered %d ports", len(_global_registry.list_all()))


__all__ = ["bootstrap", "_global_registry"]
