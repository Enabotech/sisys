"""应用层组合根模块

所有端口的注册和装配在此完成，是唯一允许注册端口的位置
遵循六边形架构原则：领域层定义端口，基础设施层实现端口，组合根负责装配

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from src.domain.ports.registry import (
    Lifetime,
    _global_registry,
    register_port,
)

logger = logging.getLogger(__name__)


def bootstrap() -> None:
    """引导端口注册表，注册所有已知端口

    在应用启动时调用一次

    Args:
        无

    Returns:
        无
    """
    logger.info("Bootstrapping port registry...")

    # Import all domain ports for registration
    # Storage layer ports
    from src.application.ports.compressor_service import CompressorService

    # Application layer ports
    from src.application.ports.document_storage_port import DocumentStoragePort
    from src.application.ports.event_subscriber import EventSubscriber
    from src.application.ports.exception_metrics_port import ExceptionMetricsPort
    from src.application.ports.memory_cache_port import MemoryCachePort
    from src.application.ports.memory_file_port import MemoryFilePort
    from src.application.ports.memory_graph_port import MemoryGraphPort
    from src.application.ports.memory_vector_port import MemoryVectorPort
    from src.application.ports.metrics_port import MetricsPort
    from src.application.ports.public_blackboard import PublicBlackboard
    from src.application.ports.sandbox_port import SandboxExecutor
    from src.application.ports.semantic_cache import SemanticCache
    from src.application.ports.session_cache_port import SessionCachePort
    from src.application.ports.text_extractor_service import TextExtractorService
    from src.application.services.unified_storage_gateway import UnifiedStorageGateway
    from src.domain.ports.audit_repository import AuditRepositoryPort
    from src.domain.ports.audit_service import AuditServicePort

    # Auth ports
    from src.domain.ports.auth_service import AuthServicePort

    # Other domain ports
    # Compliance ports
    from src.domain.ports.compliance_gateway import ComplianceGatewayPort

    # Connection manager
    from src.domain.ports.connection_manager import ConnectionManager
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
    from src.domain.ports.saga import SagaRepositoryProtocol

    # Service protocols (migrated from services)
    from src.domain.ports.sandbox_executor_protocol import SandboxExecutorProtocol
    from src.domain.ports.semantic_router_protocol import SemanticRouterProtocol
    from src.domain.ports.sensitive_data_detector import SensitiveDataDetectorPort
    from src.domain.ports.session_storage import SessionStorage
    from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
    from src.domain.ports.token_blacklist import TokenBlacklistPort
    from src.domain.ports.unified_storage import UnifiedStoragePort

    # Transaction subsystem
    from src.domain.ports.unit_of_work import UnitOfWorkFactory

    # Repository ports
    from src.domain.ports.user_repository import UserRepositoryPort
    from src.domain.ports.user_role_repository import UserRoleRepositoryPort
    from src.domain.ports.whitelist_service import WhitelistServicePort

    # === Storage Layer ===
    from src.infrastructure.config.redis import RedisConfig
    from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import (
        PostgreSQLUnitOfWork,
    )
    from src.infrastructure.saga.saga_repository import PostgreSQLSagaRepository
    from src.infrastructure.storage.redis.redis_manager import RedisManager

    register_port(
        name="redis_connection_manager",
        version="v1.0.0",
        interface=ConnectionManager,
        impl=lambda resolver: RedisManager(RedisConfig.from_env()),
        module="src.infrastructure.storage.redis.redis_connection_manager",
        lifetime=Lifetime.SINGLETON,
        owner="storage-team",
        tags=("redis", "infrastructure"),
    )

    register_port(
        name="redis_client",
        version="v1.0.0",
        interface=aioredis.Redis,
        impl=lambda resolver: resolver.resolve("redis_connection_manager").get_client(),
        module="src.infrastructure.storage.redis.redis_connection_manager",
        lifetime=Lifetime.SINGLETON,
        owner="storage-team",
        tags=("redis", "infrastructure"),
    )

    # === ConnectionManagers (L2/L3/L5) ===
    from neo4j import AsyncDriver
    from qdrant_client import AsyncQdrantClient
    from sqlalchemy.ext.asyncio import AsyncEngine

    from src.infrastructure.config.neo4j import Neo4jConfig
    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.config.qdrant import QdrantConfig
    from src.infrastructure.storage.neo4j.neo4j_manager import Neo4jManager
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
    from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager

    register_port(
        name="postgresql_connection_manager",
        version="v1.0.0",
        interface=ConnectionManager,
        impl=lambda resolver: PostgreSQLManager(PostgreSQLConfig.from_env()),
        module="src.infrastructure.storage.postgresql.engine",
        lifetime=Lifetime.SINGLETON,
        owner="storage-team",
        tags=("postgresql", "infrastructure"),
    )

    register_port(
        name="qdrant_connection_manager",
        version="v1.0.0",
        interface=ConnectionManager,
        impl=lambda resolver: QdrantManager(QdrantConfig.from_env()),
        module="src.infrastructure.storage.qdrant.client",
        lifetime=Lifetime.SINGLETON,
        owner="storage-team",
        tags=("qdrant", "infrastructure"),
    )

    register_port(
        name="neo4j_connection_manager",
        version="v1.0.0",
        interface=ConnectionManager,
        impl=lambda resolver: Neo4jManager.from_config(Neo4jConfig.from_env()),
        module="src.infrastructure.storage.neo4j.client",
        lifetime=Lifetime.SINGLETON,
        owner="storage-team",
        tags=("neo4j", "infrastructure"),
    )

    register_port(
        name="postgresql_async_engine",
        version="v1.0.0",
        interface=AsyncEngine,
        impl=lambda resolver: resolver.resolve("postgresql_connection_manager").get_client(),
        module="src.infrastructure.storage.postgresql.engine",
        lifetime=Lifetime.SINGLETON,
        owner="storage-team",
        tags=("postgresql", "infrastructure"),
    )

    # === Session Factory (ContextVar-based session management) ===
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    register_port(
        name="session_factory",
        version="v1.0.0",
        interface=async_sessionmaker,
        impl=lambda resolver: async_sessionmaker(
            bind=resolver.resolve("postgresql_async_engine"),
            class_=AsyncSession,
            expire_on_commit=False,
        ),
        module="src.infrastructure.storage.postgresql.session_context",
        lifetime=Lifetime.SINGLETON,
        owner="storage-team",
        tags=("postgresql", "session"),
    )

    register_port(
        name="qdrant_client",
        version="v1.0.0",
        interface=AsyncQdrantClient,
        impl=lambda resolver: resolver.resolve("qdrant_connection_manager").get_client(),
        module="src.infrastructure.storage.qdrant.client",
        lifetime=Lifetime.SINGLETON,
        owner="storage-team",
        tags=("qdrant", "infrastructure"),
    )

    register_port(
        name="neo4j_driver",
        version="v1.0.0",
        interface=AsyncDriver,
        impl=lambda resolver: resolver.resolve("neo4j_connection_manager").get_client(),
        module="src.infrastructure.storage.neo4j.client",
        lifetime=Lifetime.SINGLETON,
        owner="storage-team",
        tags=("neo4j", "infrastructure"),
    )

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
        name="redis_adapter",
        version="v1.0.0",
        interface=L1CachePort,
        impl="src.infrastructure.storage.redis.redis_adapter.RedisAdapter",
        module="src.infrastructure.storage.redis.redis_adapter",
        lifetime=Lifetime.SINGLETON,
        owner="storage-team",
        tags=("redis", "cache"),
    )

    register_port(
        name="memory_cache",
        version="v1.0.0",
        interface=MemoryCachePort,
        impl=lambda resolver: __import__(
            "src.infrastructure.storage.redis.redis_memory_cache",
            fromlist=["RedisMemoryCache"],
        ).RedisMemoryCache(
            adapter=resolver.resolve("redis_adapter"),
        ),
        module="src.infrastructure.storage.redis.redis_memory_cache",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
        tags=("redis", "cache", "memory"),
    )

    register_port(
        name="session_storage",
        version="v1.0.0",
        interface=SessionStorage,
        impl="src.infrastructure.storage.redis.session_storage.RedisSessionStorage",
        module="src.infrastructure.storage.redis.session_storage",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
        tags=("redis", "session"),
    )

    # === L2 Memory Repository Ports (Rule 3) ===
    from src.domain.ports.memory_repository import (
        L2ChangeHistoryRepositoryPort,
        L2GroupMemberRepositoryPort,
        L2MetadataRepositoryPort,
    )

    register_port(
        name="memory_metadata",
        version="v1.0.0",
        interface=L2MetadataRepositoryPort,
        impl="src.infrastructure.storage.postgresql.repository.memory_metadata_repository.PostgreSQLMemoryMetadataRepository",
        module="src.infrastructure.storage.postgresql.repository.memory_metadata_repository",
        lifetime=Lifetime.SCOPED,
        owner="platform-team",
    )

    register_port(
        name="memory_change_history",
        version="v1.0.0",
        interface=L2ChangeHistoryRepositoryPort,
        impl="src.infrastructure.storage.postgresql.repository.memory_change_history_repository.PostgreSQLMemoryChangeHistoryRepository",
        module="src.infrastructure.storage.postgresql.repository.memory_change_history_repository",
        lifetime=Lifetime.SCOPED,
        owner="platform-team",
    )

    register_port(
        name="memory_group_member",
        version="v1.0.0",
        interface=L2GroupMemberRepositoryPort,
        impl="src.infrastructure.storage.postgresql.repository.memory_group_member_repository.PostgreSQLMemoryGroupMemberRepository",
        module="src.infrastructure.storage.postgresql.repository.memory_group_member_repository",
        lifetime=Lifetime.SCOPED,
        owner="platform-team",
    )

    # === L3/L4/L5 Storage Layer Ports (Rule 3) ===
    from src.domain.ports.l3_vector import L3VectorPort
    from src.domain.ports.l4_object import L4ObjectPort
    from src.domain.ports.l5_graph import L5GraphPort

    register_port(
        name="l3_vector",
        version="v1.0.0",
        interface=L3VectorPort,
        impl="src.infrastructure.storage.qdrant.qdrant_vector_adapter.QdrantAdapter",
        module="src.infrastructure.storage.qdrant.qdrant_vector_adapter",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
    )

    register_port(
        name="l4_object",
        version="v1.0.0",
        interface=L4ObjectPort,
        impl="src.infrastructure.storage.minio.minio_adapter.MinIOAdapter",
        module="src.infrastructure.storage.minio.minio_adapter",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
    )

    register_port(
        name="l5_graph",
        version="v1.0.0",
        interface=L5GraphPort,
        impl="src.infrastructure.storage.neo4j.neo4j_adapter.Neo4jAdapter",
        module="src.infrastructure.storage.neo4j.neo4j_adapter",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
    )

    # === Repository Ports ===
    register_port(
        name="user_repo",
        version="v1.0.0",
        interface=UserRepositoryPort,
        impl="src.infrastructure.storage.postgresql.repository.user_repository.UserRepository",
        module="src.infrastructure.storage.postgresql.repository.user_repository",
        lifetime=Lifetime.SCOPED,
        owner="platform-team",
    )

    register_port(
        name="role_repo",
        version="v1.0.0",
        interface=RoleRepositoryPort,
        impl="src.infrastructure.storage.postgresql.repository.role_repository.RoleRepository",
        module="src.infrastructure.storage.postgresql.repository.role_repository",
        lifetime=Lifetime.SCOPED,
        owner="platform-team",
    )

    register_port(
        name="user_role_repo",
        version="v1.0.0",
        interface=UserRoleRepositoryPort,
        impl="src.infrastructure.storage.postgresql.repository.user_role_repository.UserRoleRepository",
        module="src.infrastructure.storage.postgresql.repository.user_role_repository",
        lifetime=Lifetime.SCOPED,
        owner="platform-team",
    )

    register_port(
        name="login_attempt_repo",
        version="v1.0.0",
        interface=LoginAttemptRepositoryPort,
        impl="src.infrastructure.storage.postgresql.repository.login_attempt_repository.LoginAttemptRepository",
        module="src.infrastructure.storage.postgresql.repository.login_attempt_repository",
        lifetime=Lifetime.SCOPED,
        owner="platform-team",
    )

    register_port(
        name="audit_repo",
        version="v1.0.0",
        interface=AuditRepositoryPort,
        impl="src.infrastructure.storage.postgresql.repository.audit_repository.AuditRepository",
        module="src.infrastructure.storage.postgresql.repository.audit_repository",
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
    from src.infrastructure.messaging.channel_router import ChannelRouter
    from src.infrastructure.messaging.event_bus_config_loader import DEFAULT_CONFIG_PATH, EventBusConfigLoader
    from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus
    from src.infrastructure.messaging.redis_event_bus import RedisEventBus
    from src.infrastructure.messaging.redis_publisher import RedisEventPublisher
    from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

    def _create_router() -> ChannelRouter:
        router = ChannelRouter()
        EventBusConfigLoader().load(router, DEFAULT_CONFIG_PATH)
        return router

    register_port(
        name="router",
        version="v1.0.0",
        interface=ChannelRouter,
        impl=lambda resolver: _create_router(),
        module="src.infrastructure.messaging.channel_router",
        lifetime=Lifetime.SINGLETON,
        owner="messaging-team",
    )

    register_port(
        name="redis_bus",
        version="v1.0.0",
        interface=EventPublisher,
        impl=lambda resolver: RedisEventBus(
            publisher=RedisEventPublisher(RedisConfig.from_env()),
            subscriber=RedisEventSubscriber(RedisConfig.from_env()),
            router=resolver.resolve("router"),
        ),
        module="src.infrastructure.messaging.redis_event_bus",
        lifetime=Lifetime.SINGLETON,
        owner="messaging-team",
        tags=("redis",),
    )

    register_port(
        name="rabbitmq_bus",
        version="v1.0.0",
        interface=EventPublisher,
        impl=lambda resolver: RabbitMQEventBus(
            outbox_repository=resolver.resolve("outbox_repo"),
            router=resolver.resolve("router"),
        ),
        module="src.infrastructure.messaging.rabbitmq_event_bus",
        lifetime=Lifetime.SINGLETON,
        owner="messaging-team",
        tags=("rabbitmq",),
    )

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
        impl="src.infrastructure.messaging.outbox.outbox_repository.PostgreSQLOutboxRepository",
        module="src.infrastructure.messaging.outbox.outbox_repository",
        lifetime=Lifetime.SINGLETON,
        owner="messaging-team",
    )

    from src.infrastructure.config.rabbitmq import RabbitMQConfig
    from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller
    from src.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher

    register_port(
        name="rabbitmq_publisher",
        version="v1.0.0",
        interface=RabbitMQPublisher,
        impl=lambda resolver: RabbitMQPublisher(config=RabbitMQConfig.from_env()),
        module="src.infrastructure.messaging.rabbitmq_publisher",
        lifetime=Lifetime.SINGLETON,
        owner="messaging-team",
    )

    register_port(
        name="outbox_poller",
        version="v1.0.0",
        interface=AsyncOutboxPoller,
        impl=lambda resolver: AsyncOutboxPoller(
            outbox_repository=resolver.resolve("outbox_repo"),
            publisher=resolver.resolve("rabbitmq_publisher"),
            router=resolver.resolve("router"),
            session_factory=resolver.resolve("session_factory"),
        ),
        module="src.infrastructure.messaging.outbox.outbox_processor",
        lifetime=Lifetime.SINGLETON,
        owner="messaging-team",
    )

    # === Transaction Ports ===
    register_port(
        name="uow_factory",
        version="v1.0.0",
        interface=UnitOfWorkFactory,
        impl=lambda resolver: PostgreSQLUnitOfWork,
        module="src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work",
        lifetime=Lifetime.TRANSIENT,
        owner="platform-team",
    )

    register_port(
        name="saga_repository",
        version="v1.0.0",
        interface=SagaRepositoryProtocol,
        impl=PostgreSQLSagaRepository,
        module="src.infrastructure.saga.saga_repository",
        lifetime=Lifetime.SCOPED,
        owner="platform-team",
    )

    # === Compliance Ports ===
    register_port(
        name="compliance_gateway",
        version="v1.0.0",
        interface=ComplianceGatewayPort,
        impl="src.infrastructure.security.compliance_gateway_impl.ComplianceGatewayImpl",
        module="src.infrastructure.security.compliance_gateway_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
    )

    register_port(
        name="sensitive_data_detector",
        version="v1.0.0",
        interface=SensitiveDataDetectorPort,
        impl="src.infrastructure.security.sensitive_data_detector_impl.SensitiveDataDetectorImpl",
        module="src.infrastructure.security.sensitive_data_detector_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
    )

    register_port(
        name="data_residency_enforcer",
        version="v1.0.0",
        interface=DataResidencyEnforcerPort,
        impl="src.infrastructure.security.data_residency_enforcer_impl.DataResidencyEnforcerImpl",
        module="src.infrastructure.security.data_residency_enforcer_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
    )

    register_port(
        name="whitelist_service",
        version="v1.0.0",
        interface=WhitelistServicePort,
        impl="src.infrastructure.security.whitelist_service_impl.WhitelistServiceImpl",
        module="src.infrastructure.security.whitelist_service_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
    )

    register_port(
        name="pipl_compliance",
        version="v1.0.0",
        interface=PIPLComplianceServicePort,
        impl="src.infrastructure.security.pipl_compliance_service_impl.PIPLComplianceServiceImpl",
        module="src.infrastructure.security.pipl_compliance_service_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
    )

    register_port(
        name="cross_border_transfer",
        version="v1.0.0",
        interface=CrossBorderTransferServicePort,
        impl="src.infrastructure.security.cross_border_transfer_service_impl.CrossBorderTransferServiceImpl",
        module="src.infrastructure.security.cross_border_transfer_service_impl",
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
        impl=lambda resolver: resolver.resolve("event_publisher"),
        module="src.infrastructure.messaging.dual_channel_event_bus",
        lifetime=Lifetime.SINGLETON,
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

    # === Rule 4: Application Port Implementations ===
    register_port(
        name="memory_file_storage",
        version="v1.0.0",
        interface=MemoryFilePort,
        impl="src.infrastructure.storage.memory_file_storage.MemoryFileStorage",
        module="src.infrastructure.storage.memory_file_storage",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
    )

    register_port(
        name="session_cache",
        version="v1.0.0",
        interface=SessionCachePort,
        impl=lambda resolver: __import__(
            "src.infrastructure.storage.redis.redis_session_cache",
            fromlist=["RedisSessionCache"],
        ).RedisSessionCache(
            adapter=resolver.resolve("redis_adapter"),
        ),
        module="src.infrastructure.storage.redis.redis_session_cache",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
        tags=("redis", "session"),
    )

    register_port(
        name="memory_vector_storage",
        version="v1.0.0",
        interface=MemoryVectorPort,
        impl="src.infrastructure.storage.qdrant.qdrant_memory_vector_storage.QdrantMemoryVectorStorage",
        module="src.infrastructure.storage.qdrant.qdrant_memory_vector_storage",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
    )

    register_port(
        name="document_storage",
        version="v1.0.0",
        interface=DocumentStoragePort,
        impl="src.infrastructure.storage.minio.minio_document_storage.MinIODocumentStorage",
        module="src.infrastructure.storage.minio.minio_document_storage",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
    )

    register_port(
        name="memory_graph_storage",
        version="v1.0.0",
        interface=MemoryGraphPort,
        impl="src.infrastructure.storage.neo4j.neo4j_memory_graph_storage.Neo4jMemoryGraphStorage",
        module="src.infrastructure.storage.neo4j.neo4j_memory_graph_storage",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
    )

    # UnifiedStorageGateway — 六层存储统一入口
    register_port(
        name="unified_storage",
        version="v1.0.0",
        interface=UnifiedStoragePort,
        impl=lambda resolver: UnifiedStorageGateway(
            l0_storage=resolver.resolve("l0_storage"),
            memory_cache=resolver.resolve("memory_cache"),
            l2_metadata=resolver.resolve("memory_metadata"),
            l2_history=resolver.resolve("memory_change_history"),
            l2_group_member=resolver.resolve("memory_group_member"),
            l3_vector=resolver.resolve("memory_vector_storage"),
            l4_object=resolver.resolve("document_storage"),
            l5_graph=resolver.resolve("memory_graph_storage"),
            event_publisher=resolver.resolve("event_publisher"),
        ),
        module="src.application.services.unified_storage_gateway",
        lifetime=Lifetime.SCOPED,
        owner="platform",
        tags=("storage", "gateway", "application", "unified"),
    )

    logger.info("Registered %d ports", len(_global_registry.list_all()))


async def shutdown() -> None:
    """关闭所有连接管理器，释放资源

    在应用退出时调用，优雅释放所有连接池和资源

    Args:
        无

    Returns:
        无
    """
    from src.domain.ports.resolver import get_resolver

    resolver = get_resolver()
    managers = [
        "redis_connection_manager",
        "postgresql_connection_manager",
        "qdrant_connection_manager",
        "neo4j_connection_manager",
    ]
    for name in managers:
        try:
            manager = resolver.resolve(name)
            await manager.close()
            logger.info("Closed %s", name)
        except Exception as e:
            logger.warning("Failed to close %s: %s", name, e)


__all__ = ["bootstrap", "shutdown", "_global_registry"]
