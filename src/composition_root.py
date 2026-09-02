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


# 工厂函数已迁移至对应 infrastructure/config/ 模块；组合根仅做装配，不包含业务逻辑
# 组合根仅做装配，不包含业务逻辑


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
        impl=lambda resolver: __import__(
            "src.infrastructure.storage.minio.minio_adapter",
            fromlist=["MinIOAdapter"],
        ).MinIOAdapter(
            repository=__import__(
                "src.infrastructure.storage.minio.minio_repository",
                fromlist=["MinIORepository"],
            ).MinIORepository(
                bucket_manager=__import__(
                    "src.infrastructure.storage.minio.bucket_manager",
                    fromlist=["BucketManager"],
                ).BucketManager(
                    config=__import__(
                        "src.infrastructure.config.minio",
                        fromlist=["MinIOConfig"],
                    ).MinIOConfig.from_env(),
                ),
                object_operations=__import__(
                    "src.infrastructure.storage.minio.object_operations",
                    fromlist=["ObjectOperations"],
                ).ObjectOperations(
                    config=__import__(
                        "src.infrastructure.config.minio",
                        fromlist=["MinIOConfig"],
                    ).MinIOConfig.from_env(),
                ),
                worm_manager=__import__(
                    "src.infrastructure.storage.minio.worm_lifecycle",
                    fromlist=["WORMManager"],
                ).WORMManager(
                    config=__import__(
                        "src.infrastructure.config.minio",
                        fromlist=["MinIOConfig"],
                    ).MinIOConfig.from_env(),
                ),
            ),
        ),
        module="src.infrastructure.storage.minio.minio_adapter",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
    )

    register_port(
        name="l5_graph",
        version="v1.0.0",
        interface=L5GraphPort,
        impl=lambda resolver: __import__(
            "src.infrastructure.storage.neo4j.neo4j_adapter",
            fromlist=["Neo4jAdapter"],
        ).Neo4jAdapter(
            storage=__import__(
                "src.infrastructure.storage.neo4j.graph_storage",
                fromlist=["Neo4jGraphStorage"],
            ).Neo4jGraphStorage(
                driver=resolver.resolve("neo4j_driver"),
            ),
        ),
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
    from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus
    from src.infrastructure.messaging.redis_event_bus import RedisEventBus
    from src.infrastructure.messaging.redis_publisher import RedisEventPublisher
    from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

    register_port(
        name="router",
        version="v1.0.0",
        interface=ChannelRouter,
        impl=lambda resolver: ChannelRouter.from_default_config(),
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
    # semantic_cache 从 SCOPED 升级为 SINGLETON（缓存实例全局共享）
    register_port(
        name="semantic_cache",
        version="v1.1.0",
        interface=SemanticCache,
        impl="src.infrastructure.storage.redis.semantic_cache.RedisSemanticCache",
        module="src.infrastructure.storage.redis.semantic_cache",
        lifetime=Lifetime.SINGLETON,
        owner="cache-team",
        compatibility=("v1.0.0",),
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
        impl=lambda resolver: __import__(
            "src.infrastructure.storage.minio.minio_document_storage",
            fromlist=["MinIODocumentStorage"],
        ).MinIODocumentStorage(
            adapter=resolver.resolve("l4_object"),
        ),
        module="src.infrastructure.storage.minio.minio_document_storage",
        lifetime=Lifetime.SCOPED,
        owner="storage-team",
    )

    # Document Repository — PostgreSQL 文档元数据持久化
    from src.domain.ports.document_repository import DocumentRepositoryPort

    register_port(
        name="document_repository",
        version="v1.1.0",
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

    # === OCR Port (Story 2-5) ===
    # 必须在 document_parser 之前注册，以便 ImageParser 可以通过 resolver 获取 OCR 实例
    from src.domain.ports.ocr import OCRPort

    register_port(
        name="ocr",
        version="v1.0.0",
        interface=OCRPort,
        impl="src.infrastructure.document_parsing.rapidocr_adapter.RapidOCRAdapter",
        module="src.infrastructure.document_parsing.rapidocr_adapter",
        lifetime=Lifetime.SINGLETON,
        owner="epic-2",
        tags=("ocr", "rapidocr", "local"),
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
                ).ImageParser(ocr=resolver.resolve("ocr")),
                "image/png": __import__(
                    "src.infrastructure.document_parsing.image_parser",
                    fromlist=["ImageParser"],
                ).ImageParser(ocr=resolver.resolve("ocr")),
                "image/gif": __import__(
                    "src.infrastructure.document_parsing.image_parser",
                    fromlist=["ImageParser"],
                ).ImageParser(ocr=resolver.resolve("ocr")),
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

    # === Layout Detection Ports (Story 2-3) ===
    from src.domain.ports.layout_detector import LayoutDetector
    from src.domain.ports.pdf_page_renderer import PdfPageRendererPort

    register_port(
        name="layout_detector",
        version="v1.0.0",
        interface=LayoutDetector,
        impl=lambda resolver: __import__(
            "src.infrastructure.document_parsing.onnx_layout_detector",
            fromlist=["OnnxLayoutDetector"],
        ).OnnxLayoutDetector(
            model_path=os.getenv(
                "SISYS_LAYOUT_MODEL_PATH",
                os.path.expanduser("~/models/docling-layout-heron.onnx"),
            ),
        ),
        module="src.infrastructure.document_parsing.onnx_layout_detector",
        lifetime=Lifetime.SINGLETON,
        owner="epic-2",
        tags=("layout", "onnx", "document"),
    )

    register_port(
        name="pdf_page_renderer",
        version="v1.0.0",
        interface=PdfPageRendererPort,
        impl=lambda resolver: __import__(
            "src.infrastructure.document_parsing.pdf_page_renderer",
            fromlist=["PdfPageRenderer"],
        ).PdfPageRenderer(),
        module="src.infrastructure.document_parsing.pdf_page_renderer",
        lifetime=Lifetime.SCOPED,
        owner="epic-2",
        tags=("layout", "pdf", "document"),
    )

    # === Table Extraction Ports (Story 2-4) ===
    from src.domain.ports.table_detector import TableDetectorPort
    from src.domain.ports.table_enhancer import TableSemanticEnhancerPort

    register_port(
        name="table_detector",
        version="v1.0.0",
        interface=TableDetectorPort,
        impl=lambda resolver: __import__(
            "src.infrastructure.document_parsing.pdf_table_extractor",
            fromlist=["PdfTableDetector"],
        ).PdfTableDetector(),
        module="src.infrastructure.document_parsing.pdf_table_extractor",
        lifetime=Lifetime.SCOPED,
        owner="epic-2",
        tags=("table", "pdf", "document"),
    )

    register_port(
        name="table_enhancer",
        version="v1.0.0",
        interface=TableSemanticEnhancerPort,
        impl=lambda resolver: __import__(
            "src.infrastructure.document_parsing.table_semantic_extractor",
            fromlist=["TableSemanticExtractor"],
        ).TableSemanticExtractor(),
        module="src.infrastructure.document_parsing.table_semantic_extractor",
        lifetime=Lifetime.SCOPED,
        owner="epic-2",
        tags=("table", "semantic", "document"),
    )

    # DocumentParsingService — 应用层文档解析编排
    # 可选端口通过 resolver.resolve_optional() 解析，依赖缺失时自动降级为 None
    from src.application.services.document_parsing_service import DocumentParsingService

    register_port(
        name="document_parsing_service",
        version="v1.3.0",
        interface=DocumentParsingService,
        impl=lambda resolver: DocumentParsingService(
            document_repository=resolver.resolve("document_repository"),
            document_storage=resolver.resolve("document_storage"),
            event_publisher=resolver.resolve("event_publisher"),
            document_parser=resolver.resolve("document_parser"),
            redis_client=resolver.resolve("redis_client"),
            layout_detector=resolver.resolve_optional(
                "layout_detector",
                fallback_on=(FileNotFoundError, ImportError, RuntimeError, OSError),
            ),
            pdf_page_renderer=resolver.resolve_optional(
                "pdf_page_renderer",
                fallback_on=(FileNotFoundError, ImportError, RuntimeError, OSError),
            ),
            table_detector=resolver.resolve_optional(
                "table_detector",
                fallback_on=(FileNotFoundError, ImportError, RuntimeError, OSError),
            ),
            table_enhancer=resolver.resolve_optional(
                "table_enhancer",
                fallback_on=(FileNotFoundError, ImportError, RuntimeError, OSError),
            ),
            ocr=resolver.resolve_optional(
                "ocr",
                fallback_on=(FileNotFoundError, ImportError, RuntimeError, OSError),
            ),
        ),
        module="src.application.services.document_parsing_service",
        lifetime=Lifetime.SCOPED,
        owner="epic-2",
    )

    # DocumentVersionService — 文档版本快照服务
    from src.application.services.document_version_service import DocumentVersionService

    register_port(
        name="document_version_service",
        version="v1.0.0",
        interface=DocumentVersionService,
        impl=lambda resolver: DocumentVersionService(
            document_repository=resolver.resolve("document_repository"),
            event_publisher=resolver.resolve("event_publisher"),
        ),
        module="src.application.services.document_version_service",
        lifetime=Lifetime.SCOPED,
        owner="epic-2",
    )

    # DocumentVersionHandler — 事件驱动自动触发版本快照
    from src.application.event_handlers.document_version_handler import DocumentVersionHandler

    register_port(
        name="document_version_handler",
        version="v1.0.0",
        interface=DocumentVersionHandler,
        impl=lambda resolver: DocumentVersionHandler(
            document_version_service=resolver.resolve("document_version_service"),
            event_listener=resolver.resolve("event_listener"),
        ),
        module="src.application.event_handlers.document_version_handler",
        lifetime=Lifetime.SINGLETON,
        owner="epic-2",
    )

    # SemanticChunkerPort — 语义分块器端口
    from src.domain.ports.semantic_chunker import SemanticChunkerPort

    register_port(
        name="semantic_chunker",
        version="v1.1.0",
        interface=SemanticChunkerPort,
        impl="src.infrastructure.document_parsing.semantic_chunker_impl.SemanticChunkerImpl",
        module="src.infrastructure.document_parsing.semantic_chunker_impl",
        lifetime=Lifetime.SINGLETON,
        owner="epic-2",
    )

    # SemanticChunkingService — 语义分块编排服务
    from src.application.services.semantic_chunking_service import SemanticChunkingService

    register_port(
        name="semantic_chunking_service",
        version="v1.0.0",
        interface=SemanticChunkingService,
        impl=lambda resolver: SemanticChunkingService(
            document_repository=resolver.resolve("document_repository"),
            semantic_chunker=resolver.resolve("semantic_chunker"),
            event_publisher=resolver.resolve("event_publisher"),
        ),
        module="src.application.services.semantic_chunking_service",
        lifetime=Lifetime.SCOPED,
        owner="epic-2",
    )

    # SemanticChunkingHandler — 事件驱动自动触发语义分块
    from src.application.event_handlers.semantic_chunking_handler import SemanticChunkingHandler

    register_port(
        name="semantic_chunking_handler",
        version="v1.0.0",
        interface=SemanticChunkingHandler,
        impl=lambda resolver: SemanticChunkingHandler(
            semantic_chunking_service=resolver.resolve("semantic_chunking_service"),
            event_listener=resolver.resolve("event_listener"),
        ),
        module="src.application.event_handlers.semantic_chunking_handler",
        lifetime=Lifetime.SINGLETON,
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
    from src.infrastructure.config.udmr import UDMRConfig, build_cost_calculator
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

    # CostCalculator — 成本计算领域服务（工厂函数已迁移至 infrastructure/config/cost.py）
    register_port(
        name="cost_calculator",
        version="v1.0.0",
        interface=CostCalculator,
        impl=lambda resolver: build_cost_calculator(),
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
    from src.infrastructure.external_services.embedding.embedding_api_client import (
        EmbeddingAPIClient,
    )

    register_port(
        name="embedding_service",
        version="v1.1.0",
        interface=EmbeddingServicePort,
        impl=lambda resolver: EmbeddingAPIClient(EmbeddingConfig.from_env()),
        module="src.infrastructure.external_services.embedding.embedding_api_client",
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

    # === Story 3-1b: Sparse Search + Hybrid Search Ports ===
    from src.application.services.hybrid_search_service import HybridSearchService
    from src.application.services.sparse_search_service import Bm25SparseSearchService
    from src.domain.services.rrf_fusion import fuse

    register_port(
        name="sparse_search_service",
        version="v1.0.0",
        interface=Bm25SparseSearchService,
        impl=lambda resolver: Bm25SparseSearchService(
            embedding_service=resolver.resolve("embedding_service"),
            vector_storage=resolver.resolve("l3_vector"),
        ),
        module="src.application.services.sparse_search_service",
        lifetime=Lifetime.SCOPED,
        owner="search-team",
        tags=("search", "sparse", "bm25"),
    )

    # === Story 3-4: Graph Search + Reranker + 升级 HybridSearchService ===
    from src.application.services.graph_search_service import GraphSearchService
    from src.domain.ports.reranker import RerankerPort
    from src.infrastructure.external_services.reranker import LiteLLMRerankerClient
    from src.infrastructure.external_services.reranker.config import RerankerConfig

    # 注册 GraphSearchService（第三路检索，仅注入 L5GraphPort）
    register_port(
        name="graph_search_service",
        version="v1.0.0",
        interface=GraphSearchService,
        impl=lambda resolver: GraphSearchService(
            l5_graph=resolver.resolve("l5_graph"),
        ),
        module="src.application.services.graph_search_service",
        lifetime=Lifetime.SCOPED,
        owner="search-team",
        tags=("search", "graph", "neo4j"),
    )

    # 注册重排序器（LiteLLMRerankerClient 实现 RerankerPort，注入 RerankerConfig）
    reranker_enabled = os.getenv("RERANKER_ENABLED", "true").lower() == "true"
    if reranker_enabled:
        register_port(
            name="reranker",
            version="v1.0.0",
            interface=RerankerPort,
            impl=lambda resolver: LiteLLMRerankerClient(
                config=RerankerConfig.from_env(),
            ),
            module="src.infrastructure.external_services.reranker.litellm_reranker_client",
            lifetime=Lifetime.SCOPED,
            owner="search-team",
            tags=("reranker", "colbert", "search"),
        )

    # 升级 HybridSearchService 注册（三路注入 + 可配置权重 + 重排序）
    # v1.0.0 → v1.1.0：先 unregister 旧端口再 register
    # unregister 对不存在的名字是静默 no-op，无需异常防护
    register_port(
        name="hybrid_search_service",
        version="v1.1.0",
        interface=HybridSearchService,
        impl=lambda resolver: HybridSearchService(
            dense_search=resolver.resolve("dense_search_service"),
            sparse_search=resolver.resolve("sparse_search_service"),
            fuse=fuse,
            graph_search=resolver.resolve("graph_search_service"),
            weights=[1.0, 1.0, 0.5],
            reranker=resolver.resolve_optional("reranker"),
        ),
        module="src.application.services.hybrid_search_service",
        lifetime=Lifetime.SCOPED,
        owner="search-team",
        tags=("search", "hybrid", "rrf", "three-way"),
        compatibility=("v1.0.0",),
    )

    # === Story 3-9: Semantic Cache ===
    # CacheMetricsPort — 应用层缓存指标端口（EventMetricsCollector 作为实现注入）
    from src.application.ports.cache_metrics_port import CacheMetricsPort
    from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

    register_port(
        name="cache_metrics",
        version="v1.0.0",
        interface=CacheMetricsPort,
        impl=lambda resolver: EventMetricsCollector(),
        module="src.infrastructure.monitoring.event_metrics",
        lifetime=Lifetime.SINGLETON,
        owner="cache-team",
        tags=("cache", "metrics", "search"),
    )

    # SemanticCacheMiddleware — 语义缓存中间件（包装 HybridSearchService）
    from src.application.services.semantic_cache_middleware import SemanticCacheMiddleware

    register_port(
        name="semantic_cache_middleware",
        version="v1.0.0",
        interface=SemanticCacheMiddleware,
        impl=lambda resolver: SemanticCacheMiddleware(
            search_service=resolver.resolve("hybrid_search_service"),
            cache=resolver.resolve("semantic_cache"),
            embedding_service=resolver.resolve("embedding_service"),
            metrics=resolver.resolve("cache_metrics"),
        ),
        module="src.application.services.semantic_cache_middleware",
        lifetime=Lifetime.SCOPED,
        owner="cache-team",
        tags=("cache", "semantic", "middleware", "search"),
    )

    # CacheInvalidationHandler — 缓存失效事件监听器（订阅 DocumentProcessed）
    from src.infrastructure.messaging.event_handlers.cache_invalidation_handler import (
        CacheInvalidationHandler,
    )

    register_port(
        name="cache_invalidation_handler",
        version="v1.0.0",
        interface=CacheInvalidationHandler,
        impl=lambda resolver: CacheInvalidationHandler(
            cache=resolver.resolve("semantic_cache"),
            event_listener=resolver.resolve("event_listener"),
        ),
        module="src.infrastructure.messaging.event_handlers.cache_invalidation_handler",
        lifetime=Lifetime.SINGLETON,
        owner="cache-team",
        tags=("cache", "invalidation", "handler", "messaging"),
    )

    # === Story 3-5: Layered Retrieval (L1-L4) Port ===
    from src.application.services.layered_retrieval_service import LayeredRetrievalService
    from src.domain.ports.layered_retrieval import LayeredRetrievalPort

    register_port(
        name="layered_retrieval_service",
        version="v1.0.0",
        interface=LayeredRetrievalPort,
        impl=lambda resolver: LayeredRetrievalService(
            hybrid_search=resolver.resolve("hybrid_search_service"),
            l3_vector=resolver.resolve("l3_vector"),
            embedding_service=resolver.resolve("embedding_service"),
        ),
        module="src.application.services.layered_retrieval_service",
        lifetime=Lifetime.SCOPED,
        owner="search-team",
        tags=("search", "layered", "l1-l4"),
    )

    # === Story 3-6: Summary Generation Port ===
    from src.application.services.summary_generation_service import SummaryGenerationService
    from src.domain.ports.summary_generation import SummaryGenerationPort

    register_port(
        name="summary_generation_service",
        version="v1.1.0",
        interface=SummaryGenerationPort,
        impl=lambda resolver: SummaryGenerationService(
            llm_client=resolver.resolve("llm_client"),
            layered_retrieval=resolver.resolve("layered_retrieval_service"),
            embedding_service=resolver.resolve("embedding_service"),
            l3_vector=resolver.resolve("l3_vector"),
            relevance_evaluation_service=resolver.resolve_optional("relevance_evaluation_service"),
            archive_repo=resolver.resolve_optional("archive_repository"),
        ),
        module="src.application.services.summary_generation_service",
        lifetime=Lifetime.SCOPED,
        owner="search-team",
        tags=("search", "summary", "generation"),
        compatibility=("v1.0.0",),
    )

    # === Story 3-7: Relevance Evaluation Port ===
    from src.application.services.relevance_evaluation_service import RelevanceEvaluationService
    from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

    register_port(
        name="relevance_evaluation_service",
        version="v1.0.0",
        interface=RelevanceEvaluationPort,
        impl=lambda resolver: RelevanceEvaluationService(
            llm_client=resolver.resolve("llm_client"),
        ),
        module="src.application.services.relevance_evaluation_service",
        lifetime=Lifetime.SCOPED,
        owner="search-team",
        tags=("search", "relevance", "evaluation"),
    )

    # ChunkIndexingHandler — 分块向量索引（Story 3.5 分层检索依赖）
    from src.application.event_handlers.chunk_indexing_handler import ChunkIndexingHandler

    register_port(
        name="chunk_indexing_handler",
        version="v1.0.0",
        interface=ChunkIndexingHandler,
        impl=lambda resolver: ChunkIndexingHandler(
            embedding_service=resolver.resolve("embedding_service"),
            l3_vector=resolver.resolve("l3_vector"),
            document_repository=resolver.resolve("document_repository"),
            event_listener=resolver.resolve("event_listener"),
        ),
        module="src.application.event_handlers.chunk_indexing_handler",
        lifetime=Lifetime.SINGLETON,
        owner="search-team",
        tags=("search", "layered", "indexing"),
    )

    # === Story 3-8: Traceability (High-Fidelity Bounding Box) Port ===
    from src.application.services.traceability_service import TraceabilityService
    from src.domain.ports.traceability import TraceabilityPort

    register_port(
        name="traceability_service",
        version="v1.0.0",
        interface=TraceabilityPort,
        impl=lambda resolver: TraceabilityService(
            retrieval_port=resolver.resolve("layered_retrieval_service"),
        ),
        module="src.application.services.traceability_service",
        lifetime=Lifetime.SCOPED,
        owner="search-team",
        tags=("search", "traceability", "bounding-box"),
    )

    # === ArchiveValidityHandler — 档案有效期事件处理器（Story 3.11/3.12）===
    from src.application.event_handlers.archive_handlers import ArchiveValidityHandler

    register_port(
        name="archive_validity_handler",
        version="v1.1.0",
        interface=ArchiveValidityHandler,
        impl=lambda resolver: ArchiveValidityHandler(
            event_listener=resolver.resolve("event_listener"),
            l3_vector=resolver.resolve_optional("l3_vector"),
            l5_graph=resolver.resolve_optional("l5_graph"),
        ),
        module="src.application.event_handlers.archive_handlers",
        lifetime=Lifetime.SINGLETON,
        owner="foundation-team",
        tags=("archive", "validity", "event"),
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

    # === LLM Client Port ===
    from src.domain.ports.llm_client import LLMClientPort, LLMConfig
    from src.infrastructure.external_services.llm import LitellmLLMClient

    register_port(
        name="llm_client",
        version="v1.0.0",
        interface=LLMClientPort,
        impl=lambda resolver: LitellmLLMClient(LLMConfig.from_env()),
        module="src.infrastructure.external_services.llm.litellm_llm_client",
        lifetime=Lifetime.SINGLETON,
        owner="foundation-team",
        tags=("llm", "client", "infrastructure"),
    )

    # === Entity Extraction Ports ===
    from src.application.services.entity_extraction_service import EntityExtractionService
    from src.domain.ports.entity_extraction import (
        EntityArbitratorPort,
        EntityExtractionPort,
    )
    from src.infrastructure.external_services.entity_extraction.conflict_arbitrator import (
        ConflictArbitrator,
    )
    from src.infrastructure.external_services.entity_extraction.llm_extractor import (
        LLMEntityExtractor,
    )
    from src.infrastructure.external_services.entity_extraction.rule_extractor import (
        RuleBasedExtractor,
    )

    # 注册规则基实体抽取器（RuleBasedExtractor 实现 EntityExtractionPort + DictionaryConsumerPort）
    # 生命周期 SINGLETON：确保词典热更新跨请求全局共享（词典消费端）
    register_port(
        name="entity_extraction_rule",
        version="v1.0.0",
        interface=EntityExtractionPort,
        impl=lambda resolver: RuleBasedExtractor(),
        module="src.infrastructure.external_services.entity_extraction.rule_extractor",
        lifetime=Lifetime.SINGLETON,
        owner="foundation-team",
        tags=("entity_extraction", "rule", "nlp", "dictionary_consumer"),
    )

    # 注册 LLM 语义实体抽取器（LLMEntityExtractor 实现 EntityExtractionPort）
    register_port(
        name="entity_extraction_llm",
        version="v1.0.0",
        interface=EntityExtractionPort,
        impl=lambda resolver: LLMEntityExtractor(
            llm_client=resolver.resolve("llm_client"),
        ),
        module="src.infrastructure.external_services.entity_extraction.llm_extractor",
        lifetime=Lifetime.SCOPED,
        owner="foundation-team",
        tags=("entity_extraction", "llm"),
    )

    # 注册冲突仲裁器
    register_port(
        name="conflict_arbitrator",
        version="v1.0.0",
        interface=EntityArbitratorPort,
        impl=lambda resolver: ConflictArbitrator(),
        module="src.infrastructure.external_services.entity_extraction.conflict_arbitrator",
        lifetime=Lifetime.SCOPED,
        owner="foundation-team",
        tags=("entity_extraction", "arbitrator"),
    )

    # 注册 EntityExtractionService 应用服务（注入所需的端口）
    register_port(
        name="entity_extraction_service",
        version="v1.0.0",
        interface=EntityExtractionService,
        impl=lambda resolver: EntityExtractionService(
            rule_extractor=resolver.resolve("entity_extraction_rule"),
            llm_extractor=resolver.resolve("entity_extraction_llm"),
            l5_graph=resolver.resolve("l5_graph"),
            arbitrator=resolver.resolve("conflict_arbitrator"),
            event_publisher=resolver.resolve("event_publisher"),
        ),
        module="src.application.services.entity_extraction_service",
        lifetime=Lifetime.SCOPED,
        owner="foundation-team",
        tags=("entity_extraction", "service"),
    )

    # === Domain Dictionary Ports ===
    from src.application.services.domain_dictionary_service import DomainDictionaryService
    from src.domain.ports.domain_dictionary import (
        DomainDictionaryPort,
    )
    from src.infrastructure.storage.postgresql.repository.domain_dictionary_repository import (
        PostgreSQLDomainDictionaryRepository,
    )

    register_port(
        name="domain_dictionary_repo",
        version="v1.0.0",
        interface=DomainDictionaryPort,
        impl=lambda resolver: PostgreSQLDomainDictionaryRepository(),
        module="src.infrastructure.storage.postgresql.repository.domain_dictionary_repository",
        lifetime=Lifetime.SCOPED,
        owner="foundation-team",
        tags=("dictionary", "gateway", "application"),
    )

    # 注册 DomainDictionaryService 应用服务（注入仓储 + 词典消费端 + 事件发布）
    # dictionary_consumer 复用 entity_extraction_rule（RuleBasedExtractor 同时实现
    # EntityExtractionPort 与 DictionaryConsumerPort）
    register_port(
        name="domain_dictionary_service",
        version="v1.0.0",
        interface=DomainDictionaryService,
        impl=lambda resolver: DomainDictionaryService(
            dictionary_repo=resolver.resolve("domain_dictionary_repo"),
            dictionary_consumer=resolver.resolve("entity_extraction_rule"),
            event_publisher=resolver.resolve("event_publisher"),
        ),
        module="src.application.services.domain_dictionary_service",
        lifetime=Lifetime.SCOPED,
        owner="foundation-team",
        tags=("dictionary", "service", "application"),
    )

    # === Strategic Archive Ports (Story 3.10) ===
    from src.application.services.strategic_archive_service import StrategicArchiveService
    from src.domain.ports.archive_repository import ArchiveRepositoryPort
    from src.infrastructure.storage.postgresql.repository.archive_repository import (
        PostgreSQLArchiveRepository,
    )

    # 注册档案仓储（PostgreSQLArchiveRepository 实现 ArchiveRepositoryPort）
    register_port(
        name="archive_repository",
        version="v1.0.0",
        interface=ArchiveRepositoryPort,
        impl=lambda resolver: PostgreSQLArchiveRepository(),
        module="src.infrastructure.storage.postgresql.repository.archive_repository",
        lifetime=Lifetime.SCOPED,
        owner="foundation-team",
        tags=("archive", "gateway", "application"),
    )

    # 注册 StalenessWeightService 降权服务（Story 3.12 AC-7）
    # SCOPED 生命周期：依赖 archive_repo（SCOPED），避免持有过期引用
    from src.application.services.staleness_weight_service import StalenessWeightService

    register_port(
        name="staleness_weight_service",
        version="v1.0.0",
        interface=StalenessWeightService,
        impl=lambda resolver: StalenessWeightService(
            archive_repo=resolver.resolve_optional("archive_repository"),
        ),
        module="src.application.services.staleness_weight_service",
        lifetime=Lifetime.SCOPED,
        owner="foundation-team",
        tags=("archive", "staleness", "weight", "application"),
    )

    # 注册 StrategicArchiveService 应用服务（注入 L2-L5 各层存储 + 事件发布 + 降权服务）
    # L3/L5 使用 resolve_optional 实现优雅降级（依赖缺失时自动降级为 None）
    register_port(
        name="strategic_archive_service",
        version="v1.1.0",
        interface=StrategicArchiveService,
        impl=lambda resolver: StrategicArchiveService(
            archive_repo=resolver.resolve("archive_repository"),
            embedding_service=resolver.resolve("embedding_service"),
            vector_storage=resolver.resolve_optional("l3_vector"),
            object_storage=resolver.resolve_optional("l4_object"),
            graph_storage=resolver.resolve_optional("l5_graph"),
            event_publisher=resolver.resolve("event_publisher"),
            staleness_service=resolver.resolve_optional("staleness_weight_service"),
        ),
        module="src.application.services.strategic_archive_service",
        lifetime=Lifetime.SCOPED,
        owner="foundation-team",
        tags=("archive", "service", "application"),
        compatibility=("v1.0.0",),
    )

    # === 检索-压缩循环（系统公理二：压缩前必须持久化）===
    # 实现 PersistentNoteTaker → ContextCompressor → CompressionQualityEvaluator 链路
    # 注册顺序：必须先注册 persistent_note_taker（ContextCompressor 依赖 verify_persisted）
    from src.domain.services.compression_quality_evaluator import CompressionQualityEvaluator
    from src.domain.services.context_compressor import ContextCompressor
    from src.domain.services.persistent_note_taker import PersistentNoteTaker

    register_port(
        name="persistent_note_taker",
        version="v1.0.0",
        interface=PersistentNoteTaker,
        impl=lambda resolver: PersistentNoteTaker(
            entity_extractor=resolver.resolve("entity_extraction_service"),
            audit_service=resolver.resolve_optional("audit_service"),
            l1_cache=resolver.resolve_optional("redis_adapter"),
        ),
        module="src.domain.services.persistent_note_taker",
        lifetime=Lifetime.SCOPED,
        owner="foundation-team",
        tags=("retrieval", "compression", "domain"),
    )

    register_port(
        name="compression_quality_evaluator",
        version="v1.0.0",
        interface=CompressionQualityEvaluator,
        impl=lambda resolver: CompressionQualityEvaluator(),
        module="src.domain.services.compression_quality_evaluator",
        lifetime=Lifetime.SCOPED,
        owner="foundation-team",
        tags=("retrieval", "compression", "domain"),
    )

    register_port(
        name="context_compressor",
        version="v1.0.0",
        interface=ContextCompressor,
        impl=lambda resolver: ContextCompressor(
            llm_client=resolver.resolve("llm_client"),
            note_taker=resolver.resolve("persistent_note_taker"),
            quality_evaluator=resolver.resolve_optional("compression_quality_evaluator"),
            l1_cache=resolver.resolve_optional("redis_adapter"),
        ),
        module="src.domain.services.context_compressor",
        lifetime=Lifetime.SCOPED,
        owner="foundation-team",
        tags=("retrieval", "compression", "domain"),
    )

    # === Strategic Toolbox Ports (Story 4.1) ===
    from src.application.ports.tool_registry_service import ToolRegistryServicePort
    from src.domain.ports.tool_repository import ToolRepositoryPort

    register_port(
        name="tool_repository",
        version="v1.0.0",
        interface=ToolRepositoryPort,
        impl=lambda resolver: __import__(
            "src.infrastructure.storage.inmemory.tool_repository",
            fromlist=["InMemoryToolRepository"],
        ).InMemoryToolRepository(),
        module="src.infrastructure.storage.inmemory.tool_repository",
        lifetime=Lifetime.SCOPED,
        owner="tool-team",
        tags=("tool", "repository", "inmemory"),
    )

    register_port(
        name="tool_registry_service",
        version="v1.0.0",
        interface=ToolRegistryServicePort,
        impl=lambda resolver: __import__(
            "src.application.services.tool_registry_service",
            fromlist=["ToolRegistryService"],
        ).ToolRegistryService(
            repository=resolver.resolve("tool_repository"),
        ),
        module="src.application.services.tool_registry_service",
        lifetime=Lifetime.SCOPED,
        owner="tool-team",
        tags=("tool", "registry", "service"),
    )

    # === 事件处理器注册（register_handlers）===
    # 所有事件处理器端口注册完成后，统一调用 register_handlers()
    # 将处理器订阅到 InMemoryEventListener 事件总线
    from src.domain.ports.resolver import get_resolver

    handler_names = [
        "document_version_handler",
        "chunk_indexing_handler",
        "semantic_chunking_handler",
        "archive_validity_handler",
    ]
    resolver = get_resolver()
    for handler_name in handler_names:
        try:
            handler = resolver.resolve(handler_name)
        except Exception:
            logger.warning("事件处理器未注册，跳过 register_handlers: %s", handler_name)
            continue
        register_fn = getattr(handler, "register_handlers", None)
        if callable(register_fn):
            register_fn()


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
            logger.error("Failed to close %s: %s", name, e)

    # 关闭 RabbitMQ 发布器连接
    try:
        rabbitmq_publisher = resolver.resolve("rabbitmq_publisher")
        await rabbitmq_publisher.close()
        logger.info("Closed rabbitmq_publisher")
    except Exception as e:
        logger.error("Failed to close rabbitmq_publisher: %s", e)

    # 关闭 embedding_service HTTP 客户端连接池
    try:
        embedding = resolver.resolve("embedding_service")
        if embedding is not None:
            await embedding.close()
            logger.info("Closed embedding_service")
    except Exception as e:
        logger.error("Failed to close embedding_service: %s", e)

    # 关闭 llm_client HTTP 连接池
    try:
        llm_client = resolver.resolve("llm_client")
        if llm_client is not None:
            await llm_client.close()
            logger.info("Closed llm_client")
    except Exception as e:
        logger.error("Failed to close llm_client: %s", e)

    # 关闭 ONNX 版面检测模型会话（释放 GPU/CPU 推理资源）
    try:
        layout_detector = resolver.resolve("layout_detector")
        if layout_detector is not None and hasattr(layout_detector, "close"):
            layout_detector.close()
            logger.info("Closed layout_detector ONNX session")
    except (FileNotFoundError, ImportError, RuntimeError, OSError, KeyError):
        pass  # 端口未注册或初始化失败，无需清理
    except Exception as e:
        logger.error("Failed to close layout_detector: %s", e)


__all__ = ["bootstrap", "shutdown", "_global_registry"]
