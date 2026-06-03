"""应用层组合根模块

所有端口的注册和装配在此完成，是唯一允许注册端口的位置
遵循六边形架构原则：领域层定义端口，基础设施层实现端口，组合根负责装配
"""

from __future__ import annotations

import logging
import os

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
    # Auto-Invocation Pipeline
    from src.application.event_handlers.auto_execute_completed_handler import (
        AutoExecuteCompletedHandler,
    )
    from src.application.event_handlers.auto_route_handler import AutoRouteHandler
    from src.application.event_handlers.auto_trigger_handler import AutoTriggerHandler
    from src.application.event_handlers.udmr_handler import UDMRHandler
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
    from src.application.ports.semantic_cache import SemanticCache
    from src.application.ports.session_cache_port import SessionCachePort
    from src.application.ports.text_extractor_service import TextExtractorService
    from src.application.services.unified_storage_gateway import UnifiedStorageGateway
    from src.domain.ports.api_security_service import APISecurityServicePort
    from src.domain.ports.audit_repository import AuditRepositoryPort
    from src.domain.ports.audit_service import AuditServicePort

    # Auth ports
    from src.domain.ports.auth_service import AuthServicePort

    # Security Level 3 Compliance Ports (等保2.0三级)
    from src.domain.ports.backup_recovery_service import BackupRecoveryServicePort

    # Other domain ports
    # Compliance ports
    from src.domain.ports.compliance_gateway import ComplianceGatewayPort

    # Connection manager
    from src.domain.ports.connection_manager import ConnectionManager
    from src.domain.ports.container_security_service import ContainerSecurityServicePort
    from src.domain.ports.cross_border_transfer_service import CrossBorderTransferServicePort
    from src.domain.ports.data_integrity_service import DataIntegrityServicePort
    from src.domain.ports.data_residency_enforcer import DataResidencyEnforcerPort

    # Event listener port
    from src.domain.ports.event_listener import EventListener

    # Event ports
    from src.domain.ports.event_publisher import EventPublisher
    from src.domain.ports.hash_router_protocol import HashRouterProtocol
    from src.domain.ports.intrusion_detection_service import IntrusionDetectionServicePort
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
    from src.domain.ports.sandbox_executor import SandboxExecutor
    from src.domain.ports.semantic_router_protocol import SemanticRouterProtocol
    from src.domain.ports.sensitive_data_detector import SensitiveDataDetectorPort
    from src.domain.ports.session_storage import SessionStorage
    from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
    from src.domain.ports.storage_encryption_service import StorageEncryptionServicePort
    from src.domain.ports.token_blacklist import TokenBlacklistPort
    from src.domain.ports.unified_storage import UnifiedStoragePort

    # Transaction subsystem
    from src.domain.ports.unit_of_work import UnitOfWorkFactory

    # Repository ports
    from src.domain.ports.user_repository import UserRepositoryPort
    from src.domain.ports.user_role_repository import UserRoleRepositoryPort
    from src.domain.ports.whitelist_service import WhitelistServicePort
    from src.domain.services.auto_execute_service import AutoExecuteService
    from src.domain.services.auto_route_service import AutoRouteService
    from src.domain.services.auto_trigger_service import AutoTriggerService

    # === Storage Layer ===
    from src.infrastructure.config.auto_route import AutoRouteConfig
    from src.infrastructure.config.redis import RedisConfig
    from src.infrastructure.external_services.sandbox.session_namespace_manager import (
        SessionNamespaceManager,
    )
    from src.infrastructure.messaging.inmemory_event_listener import InMemoryEventListener
    from src.infrastructure.messaging.unit_of_work.postgresql_unit_of_work import (
        PostgreSQLUnitOfWork,
    )
    from src.infrastructure.saga.saga_repository import PostgreSQLSagaRepository
    from src.infrastructure.scheduler.heartbeat_scheduler import HeartbeatScheduler
    from src.infrastructure.security.audit_service_impl import AuditServiceImpl
    from src.infrastructure.security.auth_service_impl import AuthServiceImpl
    from src.infrastructure.security.encryption_service import EncryptionService
    from src.infrastructure.security.jwt_service import JWTService
    from src.infrastructure.security.token_blacklist import RedisTokenBlacklist
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
    from src.infrastructure.storage.qdrant.collection_manager import (
        QdrantCollectionManager,
    )
    from src.infrastructure.storage.qdrant.qdrant_adapter import QdrantAdapter
    from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage

    register_port(
        name="l3_vector",
        version="v1.0.0",
        interface=L3VectorPort,
        impl=lambda resolver: QdrantAdapter(
            storage=QdrantVectorStorage(resolver.resolve("qdrant_client")),
            collection_manager=QdrantCollectionManager(resolver.resolve("qdrant_client")),
        ),
        module="src.infrastructure.storage.qdrant.qdrant_adapter",
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
        impl="src.infrastructure.security.audit_repository_impl.AuditRepository",
        module="src.infrastructure.security.audit_repository_impl",
        lifetime=Lifetime.SCOPED,
        owner="compliance-team",
    )

    register_port(
        name="audit_service",
        version="v1.0.0",
        interface=AuditServicePort,
        impl=lambda resolver: AuditServiceImpl(
            audit_repository=resolver.resolve("audit_repo"),
        ),
        module="src.infrastructure.security.audit_service_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
    )

    # === Auth Ports ===
    from src.infrastructure.config.auth import AuthConfig

    register_port(
        name="auth_service",
        version="v1.0.0",
        interface=AuthServicePort,
        impl=lambda resolver: AuthServiceImpl(
            jwt_service=JWTService(AuthConfig.from_env()),
            encryption_service=EncryptionService(),
            user_repository=resolver.resolve("user_repo"),
            user_role_repository=resolver.resolve("user_role_repo"),
            login_attempt_repository=resolver.resolve("login_attempt_repo"),
        ),
        module="src.infrastructure.security.auth_service_impl",
        lifetime=Lifetime.SINGLETON,
        owner="security-team",
    )

    register_port(
        name="permission_service",
        version="v1.0.0",
        interface=PermissionServicePort,
        impl="src.infrastructure.security.permission_service_impl.PermissionServiceImpl",
        module="src.infrastructure.security.permission_service_impl",
        lifetime=Lifetime.SINGLETON,
        owner="security-team",
    )

    register_port(
        name="token_blacklist",
        version="v1.0.0",
        interface=TokenBlacklistPort,
        impl=lambda resolver: RedisTokenBlacklist(redis_client=resolver.resolve("redis_client")),
        module="src.infrastructure.security.token_blacklist",
        lifetime=Lifetime.SCOPED,
        owner="security-team",
    )

    register_port(
        name="password_validation",
        version="v1.0.0",
        interface=PasswordValidationServicePort,
        impl="src.infrastructure.security.password_validation_service.PasswordValidationService",
        module="src.infrastructure.security.password_validation_service",
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

    # === Security Level 3 Compliance Ports (等保2.0三级) ===
    register_port(
        name="intrusion_detection_service",
        version="v1.0.0",
        interface=IntrusionDetectionServicePort,
        impl="src.infrastructure.security.intrusion_detection_service_impl.IntrusionDetectionServiceImpl",
        module="src.infrastructure.security.intrusion_detection_service_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
        tags=("security", "compliance", "intrusion-detection"),
    )

    register_port(
        name="data_integrity_service",
        version="v1.0.0",
        interface=DataIntegrityServicePort,
        impl="src.infrastructure.security.data_integrity_service_impl.DataIntegrityServiceImpl",
        module="src.infrastructure.security.data_integrity_service_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
        tags=("security", "compliance", "data-integrity"),
    )

    register_port(
        name="backup_recovery_service",
        version="v1.0.0",
        interface=BackupRecoveryServicePort,
        impl="src.infrastructure.security.backup_recovery_service_impl.BackupRecoveryServiceImpl",
        module="src.infrastructure.security.backup_recovery_service_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
        tags=("security", "compliance", "backup-recovery"),
    )

    register_port(
        name="storage_encryption_service",
        version="v1.0.0",
        interface=StorageEncryptionServicePort,
        impl="src.infrastructure.security.storage_encryption_service_impl.StorageEncryptionServiceImpl",
        module="src.infrastructure.security.storage_encryption_service_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
        tags=("security", "compliance", "encryption"),
    )

    register_port(
        name="api_security_service",
        version="v1.0.0",
        interface=APISecurityServicePort,
        impl="src.infrastructure.security.api_security_service_impl.APISecurityServiceImpl",
        module="src.infrastructure.security.api_security_service_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
        tags=("security", "compliance", "api-security"),
    )

    register_port(
        name="container_security_service",
        version="v1.0.0",
        interface=ContainerSecurityServicePort,
        impl="src.infrastructure.security.container_security_service_impl.ContainerSecurityServiceImpl",
        module="src.infrastructure.security.container_security_service_impl",
        lifetime=Lifetime.SINGLETON,
        owner="compliance-team",
        tags=("security", "compliance", "container-security"),
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
        impl="src.infrastructure.external_services.sandbox.docker_sandbox_adapter.DockerSandboxAdapter",
        module="src.infrastructure.external_services.sandbox.docker_sandbox_adapter",
        lifetime=Lifetime.SCOPED,
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
        name="snapshot_repository",
        version="v1.0.0",
        interface=SnapshotRepositoryProtocol,
        impl=lambda resolver: __import__(
            "src.infrastructure.storage.redis.redis_snapshot_store",
            fromlist=["RedisSnapshotStore"],
        ).RedisSnapshotStore(
            adapter=resolver.resolve("redis_adapter"),
        ),
        module="src.infrastructure.storage.redis.redis_snapshot_store",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
        tags=("redis", "snapshot"),
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

    # === Auto-Invocation Pipeline ===

    register_port(
        name="event_listener",
        version="v1.0.0",
        interface=EventListener,
        impl=lambda resolver: InMemoryEventListener(),
        module="src.infrastructure.messaging.inmemory_event_listener",
        lifetime=Lifetime.SINGLETON,
        owner="auto-invocation-team",
    )

    register_port(
        name="auto_trigger_service",
        version="v1.0.0",
        interface=AutoTriggerService,
        impl=lambda resolver: AutoTriggerService(
            publisher=resolver.resolve("event_publisher"),
        ),
        module="src.domain.services.auto_trigger_service",
        lifetime=Lifetime.SINGLETON,
        owner="auto-invocation-team",
    )

    # RoutingDecisionLogRepository — 路由决策日志仓储
    from src.domain.ports.routing_decision_log_repository import RoutingDecisionLogRepository
    from src.infrastructure.messaging.inmemory_routing_decision_log_repository import (
        InMemoryRoutingDecisionLogRepository,
    )

    register_port(
        name="routing_decision_log_repository",
        version="v1.0.0",
        interface=RoutingDecisionLogRepository,
        impl=lambda resolver: InMemoryRoutingDecisionLogRepository(),
        module="src.infrastructure.messaging.inmemory_routing_decision_log_repository",
        lifetime=Lifetime.SINGLETON,
        owner="auto-invocation-team",
    )

    register_port(
        name="auto_route_service",
        version="v1.0.0",
        interface=AutoRouteService,
        impl=lambda resolver: AutoRouteService(
            publisher=resolver.resolve("event_publisher"),
            hash_router=resolver.resolve("hash_router"),
            semantic_router=resolver.resolve("semantic_router"),
            semantic_threshold=AutoRouteConfig.from_env().semantic_threshold,
            decision_log_repo=resolver.resolve("routing_decision_log_repository"),
        ),
        module="src.domain.services.auto_route_service",
        lifetime=Lifetime.SINGLETON,
        owner="auto-invocation-team",
    )

    register_port(
        name="auto_execute_service",
        version="v1.0.0",
        interface=AutoExecuteService,
        impl=lambda resolver: AutoExecuteService(
            sandbox=resolver.resolve("sandbox_executor"),
            snapshot_repo=resolver.resolve("snapshot_repository"),
        ),
        module="src.domain.services.auto_execute_service",
        lifetime=Lifetime.SINGLETON,
        owner="auto-invocation-team",
    )

    register_port(
        name="auto_route_handler",
        version="v1.0.0",
        interface=AutoRouteHandler,
        impl=lambda resolver: AutoRouteHandler(
            auto_route_service=resolver.resolve("auto_route_service"),
        ),
        module="src.application.event_handlers.auto_route_handler",
        lifetime=Lifetime.SINGLETON,
        owner="auto-invocation-team",
    )

    register_port(
        name="auto_execute_completed_handler",
        version="v1.0.0",
        interface=AutoExecuteCompletedHandler,
        impl=lambda resolver: AutoExecuteCompletedHandler(
            publisher=resolver.resolve("event_publisher"),
        ),
        module="src.application.event_handlers.auto_execute_completed_handler",
        lifetime=Lifetime.SINGLETON,
        owner="auto-invocation-team",
    )

    register_port(
        name="heartbeat_scheduler",
        version="v1.0.0",
        interface=HeartbeatScheduler,
        impl=lambda resolver: HeartbeatScheduler(
            redis_config=RedisConfig.from_env(),
        ),
        module="src.infrastructure.scheduler.heartbeat_scheduler",
        lifetime=Lifetime.SINGLETON,
        owner="auto-invocation-team",
    )

    register_port(
        name="session_namespace_manager",
        version="v1.0.0",
        interface=SessionNamespaceManager,
        impl=lambda resolver: SessionNamespaceManager(
            sandbox=resolver.resolve("sandbox_executor"),
        ),
        module="src.infrastructure.external_services.sandbox.session_namespace_manager",
        lifetime=Lifetime.SINGLETON,
        owner="auto-invocation-team",
    )

    register_port(
        name="auto_trigger_handler",
        version="v1.0.0",
        interface=AutoTriggerHandler,
        impl=lambda resolver: AutoTriggerHandler(
            auto_trigger_service=resolver.resolve("auto_trigger_service"),
            event_listener=resolver.resolve("event_listener"),
        ),
        module="src.application.event_handlers.auto_trigger_handler",
        lifetime=Lifetime.SINGLETON,
        owner="auto-invocation-team",
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

    # Document Repository — PostgreSQL 文档元数据持久化
    from src.domain.ports.document_repository import DocumentRepositoryPort

    register_port(
        name="document_repository",
        version="v1.0.0",
        interface=DocumentRepositoryPort,
        impl="src.infrastructure.storage.postgresql.repository.document_repository.PostgreSQLDocumentRepository",
        module="src.infrastructure.storage.postgresql.repository.document_repository",
        lifetime=Lifetime.SCOPED,
        owner="doc-team",
    )

    # DocumentUploadService — 应用层文档上传编排
    from src.application.services.document_upload_service import DocumentUploadService

    register_port(
        name="document_upload_service",
        version="v1.0.0",
        interface=DocumentUploadService,
        impl=lambda resolver: DocumentUploadService(
            document_repository=resolver.resolve("document_repository"),
            document_storage=resolver.resolve("document_storage"),
            event_publisher=resolver.resolve("event_publisher"),
        ),
        module="src.application.services.document_upload_service",
        lifetime=Lifetime.SCOPED,
        owner="doc-team",
    )

    # DocumentParser — 文档解析（MIME 路由组合模式）
    from src.domain.ports.document_parser import DocumentParserPort

    register_port(
        name="document_parser",
        version="v1.1.0",
        interface=DocumentParserPort,
        impl=lambda resolver: __import__(
            "src.infrastructure.document_parsing.composite_parser",
            fromlist=["CompositeDocumentParser"],
        ).CompositeDocumentParser(
            parsers={
                "application/pdf": __import__(
                    "src.infrastructure.document_parsing.pdf_parser",
                    fromlist=["PDFParser"],
                ).PDFParser(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document": __import__(
                    "src.infrastructure.document_parsing.word_parser",
                    fromlist=["WordParser"],
                ).WordParser(),
                "application/msword": __import__(  # DOC 格式由 WordParser 返回友好拒绝消息
                    "src.infrastructure.document_parsing.word_parser",
                    fromlist=["WordParser"],
                ).WordParser(),
                "text/plain": __import__(
                    "src.infrastructure.document_parsing.text_parser",
                    fromlist=["TextParser"],
                ).TextParser(),
                # --- Story 2-2b 扩展格式 ---
                "application/vnd.openxmlformats-officedocument.presentationml.presentation": __import__(
                    "src.infrastructure.document_parsing.pptx_parser",
                    fromlist=["PptxParser"],
                ).PptxParser(),
                "application/vnd.ms-powerpoint": __import__(  # PPT 格式由 PptxParser 返回友好拒绝消息
                    "src.infrastructure.document_parsing.pptx_parser",
                    fromlist=["PptxParser"],
                ).PptxParser(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": __import__(
                    "src.infrastructure.document_parsing.excel_parser",
                    fromlist=["ExcelParser"],
                ).ExcelParser(),
                "application/vnd.ms-excel": __import__(  # XLS 格式由 ExcelParser 返回友好拒绝消息
                    "src.infrastructure.document_parsing.excel_parser",
                    fromlist=["ExcelParser"],
                ).ExcelParser(),
                "text/csv": __import__(
                    "src.infrastructure.document_parsing.csv_parser",
                    fromlist=["CSVParser"],
                ).CSVParser(),
                "image/jpeg": __import__(
                    "src.infrastructure.document_parsing.image_parser",
                    fromlist=["ImageParser"],
                ).ImageParser(),
                "image/png": __import__(
                    "src.infrastructure.document_parsing.image_parser",
                    fromlist=["ImageParser"],
                ).ImageParser(),
                "image/gif": __import__(
                    "src.infrastructure.document_parsing.image_parser",
                    fromlist=["ImageParser"],
                ).ImageParser(),
                "text/html": __import__(
                    "src.infrastructure.document_parsing.html_parser",
                    fromlist=["HTMLParser"],
                ).HTMLParser(),
                "text/markdown": __import__(
                    "src.infrastructure.document_parsing.markdown_parser",
                    fromlist=["MarkdownParser"],
                ).MarkdownParser(),
                "application/rtf": __import__(
                    "src.infrastructure.document_parsing.rtf_parser",
                    fromlist=["RTFParser"],
                ).RTFParser(),
            },
        ),
        module="src.infrastructure.document_parsing.composite_parser",
        lifetime=Lifetime.SCOPED,
        owner="epic-2",
    )

    # DocumentParsingService — 应用层文档解析编排
    from src.application.services.document_parsing_service import DocumentParsingService

    register_port(
        name="document_parsing_service",
        version="v1.0.0",
        interface=DocumentParsingService,
        impl=lambda resolver: DocumentParsingService(
            document_repository=resolver.resolve("document_repository"),
            document_storage=resolver.resolve("document_storage"),
            event_publisher=resolver.resolve("event_publisher"),
            document_parser=resolver.resolve("document_parser"),
            redis_client=resolver.resolve("redis_client"),
        ),
        module="src.application.services.document_parsing_service",
        lifetime=Lifetime.SCOPED,
        owner="epic-2",
    )

    # ChunkedUploadManager — 分片上传状态管理
    from src.infrastructure.storage.redis.chunked_upload_manager import ChunkedUploadManager

    register_port(
        name="chunked_upload_manager",
        version="v1.0.0",
        interface=ChunkedUploadManager,
        impl=lambda resolver: ChunkedUploadManager(
            cache=resolver.resolve("redis_adapter"),
        ),
        module="src.infrastructure.storage.redis.chunked_upload_manager",
        lifetime=Lifetime.SCOPED,
        owner="doc-team",
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

    # Workflow Engine — Prefect 工作流引擎适配器
    from src.domain.ports.workflow_engine import WorkflowEnginePort
    from src.infrastructure.config.prefect import PrefectConfig
    from src.infrastructure.workflow.prefect_engine import PrefectEngine

    register_port(
        name="workflow_engine",
        version="v1.0.0",
        interface=WorkflowEnginePort,
        impl=lambda resolver: PrefectEngine(
            PrefectConfig.from_env(),
            resolver.resolve("event_publisher"),
        ),
        module="src.infrastructure.workflow.prefect_engine",
        lifetime=Lifetime.SINGLETON,
        owner="platform",
        tags=("workflow", "prefect"),
    )

    # Agent Engine — LangGraph Agent 编排引擎适配器
    from src.domain.ports.agent_engine import AgentEnginePort
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.config.langgraph import LangGraphConfig

    register_port(
        name="agent_engine",
        version="v1.0.0",
        interface=AgentEnginePort,
        impl=lambda resolver: LangGraphEngine(
            LangGraphConfig.from_env(),
            resolver.resolve("event_publisher"),
        ),
        module="src.infrastructure.agent_orch.langgraph_engine",
        lifetime=Lifetime.SINGLETON,
        owner="platform",
        tags=("agent", "langgraph"),
    )

    # OrchestrationService — 应用层编排服务（service 注册，非 port）
    from src.application.services.orchestration_service import OrchestrationService

    register_port(
        name="orchestration_service",
        version="v1.0.0",
        interface=OrchestrationService,
        impl=lambda resolver: OrchestrationService(
            resolver.resolve("workflow_engine"),
            resolver.resolve("agent_engine"),
        ),
        module="src.application.services.orchestration_service",
        lifetime=Lifetime.SINGLETON,
        owner="platform",
        tags=("orchestration", "application", "service"),
    )

    # === UDMR (Unified Dynamic Model Routing) ===
    from src.application.event_handlers.cost_metrics_handler import CostMetricsListener
    from src.domain.ports.health_check import HealthCheckPort
    from src.domain.ports.routing_decision_log_repository import (
        RoutingDecisionLogRepository,
    )
    from src.domain.ports.token_estimator import TokenEstimatorPort
    from src.domain.ports.udmr_policy import UdmrPolicyPort
    from src.domain.services.cost_calculator import CostCalculator
    from src.domain.services.udmr_service import UDMRService
    from src.infrastructure.config.udmr import UDMRConfig
    from src.infrastructure.external_services.llm.cloud_health_checker import (
        CloudHealthChecker,
    )
    from src.infrastructure.monitoring.static_token_estimator import StaticTokenEstimator
    from src.infrastructure.routing.udmr_policy import StaticUdmrPolicy

    # UDMR Policy — 静态路由策略
    register_port(
        name="udmr_policy",
        version="v1.0.0",
        interface=UdmrPolicyPort,
        impl=lambda resolver: StaticUdmrPolicy(
            cloud_configs=UDMRConfig.from_env().cloud_configs,
            local_model=UDMRConfig.from_env().local_model,
            local_first=UDMRConfig.from_env().local_first,
        ),
        module="src.infrastructure.routing.udmr_policy",
        lifetime=Lifetime.SINGLETON,
        owner="routing-team",
        tags=("udmr", "routing", "policy"),
    )

    # CloudHealthChecker — 云端健康检查
    register_port(
        name="cloud_health_checker",
        version="v1.0.0",
        interface=HealthCheckPort,
        impl=lambda resolver: CloudHealthChecker(
            cloud_configs=UDMRConfig.from_env().cloud_configs,
            timeout=UDMRConfig.from_env().llm_timeout,
            cache_ttl=UDMRConfig.from_env().healthcheck_interval,
        ),
        module="src.infrastructure.external_services.llm.cloud_health_checker",
        lifetime=Lifetime.SINGLETON,
        owner="routing-team",
        tags=("udmr", "health-check"),
    )

    # UDMRService — 三层决策服务
    register_port(
        name="udmr_service",
        version="v1.0.0",
        interface=UDMRService,
        impl=lambda resolver: UDMRService(
            compliance_gateway=resolver.resolve("compliance_gateway"),
            policy=resolver.resolve("udmr_policy"),
            health_checker=resolver.resolve("cloud_health_checker"),
            log_repo=resolver.resolve("routing_decision_log_repository"),
            publisher=resolver.resolve("event_publisher"),
            local_first=UDMRConfig.from_env().local_first,
            local_model=UDMRConfig.from_env().local_model,
            llm_timeout=UDMRConfig.from_env().llm_timeout,
            token_estimator=resolver.resolve("token_estimator"),
            cost_calculator=resolver.resolve("cost_calculator"),
        ),
        module="src.domain.services.udmr_service",
        lifetime=Lifetime.SINGLETON,
        owner="routing-team",
        tags=("udmr", "service", "domain"),
    )

    # UDMRHandler — 事件处理器
    register_port(
        name="udmr_handler",
        version="v1.0.0",
        interface=UDMRHandler,
        impl=lambda resolver: UDMRHandler(
            udmr_service=resolver.resolve("udmr_service"),
            event_bus=resolver.resolve("event_publisher"),
            enabled=UDMRConfig.from_env().enabled,
        ),
        module="src.application.event_handlers.udmr_handler",
        lifetime=Lifetime.SINGLETON,
        owner="routing-team",
        tags=("udmr", "handler", "application"),
    )

    # === Cost Metrics (Story 1.19) ===

    # TokenEstimatorPort — 静态 Token 估算器
    register_port(
        name="token_estimator",
        version="v1.0.0",
        interface=TokenEstimatorPort,
        impl=lambda resolver: StaticTokenEstimator(),
        module="src.infrastructure.monitoring.static_token_estimator",
        lifetime=Lifetime.SINGLETON,
        owner="routing-team",
        tags=("udmr", "cost", "infrastructure"),
    )

    # CostCalculator — 成本计算领域服务
    def _make_cost_calculator(resolver: object) -> CostCalculator:
        cfg = UDMRConfig.from_env()
        return CostCalculator(
            local_input_price=0.002,
            local_output_price=0.002,
            cloud_input_price=(cfg.cloud_configs[0].price_per_input_1k_tokens if cfg.cloud_configs else 0.02),
            cloud_output_price=(cfg.cloud_configs[0].price_per_output_1k_tokens if cfg.cloud_configs else 0.02),
            model_pricing_map={
                c.model: {"input": c.price_per_input_1k_tokens, "output": c.price_per_output_1k_tokens}
                for c in cfg.cloud_configs
            },
        )

    register_port(
        name="cost_calculator",
        version="v1.0.0",
        interface=CostCalculator,
        impl=_make_cost_calculator,
        module="src.domain.services.cost_calculator",
        lifetime=Lifetime.SINGLETON,
        owner="routing-team",
        tags=("udmr", "cost", "domain"),
    )

    # CostMetricsListener — 成本度量事件处理器
    register_port(
        name="cost_metrics_handler",
        version="v1.0.0",
        interface=CostMetricsListener,
        impl=lambda resolver: CostMetricsListener(
            token_estimator=resolver.resolve("token_estimator"),
            cost_calculator=resolver.resolve("cost_calculator"),
            log_repo=resolver.resolve("routing_decision_log_repository"),
            metrics=resolver.resolve("metrics"),
            event_bus=resolver.resolve("event_subscriber"),
        ),
        module="src.application.event_handlers.cost_metrics_handler",
        lifetime=Lifetime.SINGLETON,
        owner="routing-team",
        tags=("udmr", "cost", "handler", "application"),
    )

    # === Search Ports (Epic 3) ===
    from src.application.services.dense_search_service import DenseSemanticSearchService
    from src.domain.ports.crawler_client import CrawlerClientPort
    from src.domain.ports.embedding_service import EmbeddingServicePort
    from src.infrastructure.config.embedding import EmbeddingConfig
    from src.infrastructure.external_services.embedding.bge3_embedding_service import (
        BGE3EmbeddingService,
    )

    register_port(
        name="embedding_service",
        version="v1.0.0",
        interface=EmbeddingServicePort,
        impl=lambda resolver: BGE3EmbeddingService(EmbeddingConfig.from_env()),
        module="src.infrastructure.external_services.embedding.bge3_embedding_service",
        lifetime=Lifetime.SINGLETON,
        owner="search-team",
        tags=("embedding", "search"),
    )

    register_port(
        name="dense_search_service",
        version="v1.0.0",
        interface=DenseSemanticSearchService,
        impl=lambda resolver: DenseSemanticSearchService(
            embedding_service=resolver.resolve("embedding_service"),
            vector_storage=resolver.resolve("l3_vector"),
        ),
        module="src.application.services.dense_search_service",
        lifetime=Lifetime.SCOPED,
        owner="search-team",
        tags=("search", "dense"),
    )

    # === Crawler Ports ===
    register_port(
        name="crawler_client",
        version="v1.0.0",
        interface=CrawlerClientPort,
        impl=lambda resolver: __import__(
            "src.infrastructure.crawler.http_crawler_client",
            fromlist=["HttpCrawlerClient"],
        ).HttpCrawlerClient(
            base_url=os.getenv("CRAWLER_SERVICE_URL", "http://localhost:8900"),
        ),
        module="src.infrastructure.crawler.http_crawler_client",
        lifetime=Lifetime.SINGLETON,
        owner="crawler-team",
        tags=("crawler", "client"),
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
