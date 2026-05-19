"""领域层端口包

定义领域层与基础设施层之间的契约接口（Protocol），
遵循六边形架构：领域层零外部依赖

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

# Deprecated ports - not registered, not for new use
# from src.domain.ports.graph_storage import GraphManager, GraphStorage  # deprecated
# from src.domain.ports.vector_storage import VectorStorage  # deprecated

from src.domain.ports.connection_manager import ConnectionManager
from src.domain.ports.hash_router_protocol import HashRouterProtocol
from src.domain.ports.index_manager import IndexManagerPort
from src.domain.ports.l0_storage import L0StoragePort
from src.domain.ports.l1_cache import L1CachePort
from src.domain.ports.l2_rdb import BaseRepository, L2RdbPort
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.l4_object import L4ObjectPort
from src.domain.ports.l5_graph import L5GraphPort
from src.domain.ports.memory_repository import (
    L2ChangeHistoryRepositoryPort,
    L2GroupMemberRepositoryPort,
    L2MetadataRepositoryPort,
)
from src.domain.ports.outbox import OutboxRepository
from src.domain.ports.permission_repository import PermissionRepositoryPort
from src.domain.ports.saga import SagaRepositoryProtocol, SagaStep
from src.domain.ports.sandbox_executor_protocol import SandboxExecutorProtocol
from src.domain.ports.semantic_router_protocol import SemanticRouterProtocol
from src.domain.ports.session_storage import SessionStorage
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
from src.domain.ports.storage_enums import DataAccessPattern, StorageLayer, StorageTier
from src.domain.ports.unified_storage import UnifiedStoragePort
from src.domain.ports.unit_of_work import UnitOfWork

__all__ = [
    "ConnectionManager",
    "DataAccessPattern",
    "BaseRepository",
    "HashRouterProtocol",
    "IndexManagerPort",
    "L0StoragePort",
    "L1CachePort",
    "L2ChangeHistoryRepositoryPort",
    "L2GroupMemberRepositoryPort",
    "L2MetadataRepositoryPort",
    "L2RdbPort",
    "L3VectorPort",
    "L4ObjectPort",
    "L5GraphPort",
    "OutboxRepository",
    "PermissionRepositoryPort",
    "SagaRepositoryProtocol",
    "SagaStep",
    "SandboxExecutorProtocol",
    "SemanticRouterProtocol",
    "SessionStorage",
    "SnapshotRepositoryProtocol",
    "StorageLayer",
    "StorageTier",
    "UnifiedStoragePort",
    "UnitOfWork",
]
