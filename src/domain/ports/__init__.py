"""领域层端口包

定义领域层与基础设施层之间的契约接口（Protocol），
遵循六边形架构：领域层零外部依赖
"""

# Deprecated ports - not registered, not for new use
# from src.domain.ports.graph_storage import GraphManager, GraphStorage  # deprecated
# from src.domain.ports.vector_storage import VectorStorage  # deprecated

from src.domain.ports.agent_engine import AgentEnginePort
from src.domain.ports.archive_repository import ArchiveQuery, ArchiveRepositoryPort
from src.domain.ports.connection_manager import ConnectionManager
from src.domain.ports.crawler_client import CrawlerClientPort
from src.domain.ports.dead_letter_queue import DeadLetterQueue
from src.domain.ports.domain_dictionary import (
    DictionaryConsumerPort,
    DictionaryEntry,
    DictionaryQuery,
    DictionarySnapshot,
    DomainDictionaryPort,
)
from src.domain.ports.embedding_service import EmbeddingServicePort, SparseEmbedding
from src.domain.ports.entity_extraction import (
    EntityArbitratorPort,
    EntityExtractionPort,
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from src.domain.ports.event_listener import EventListener, EventListenerAsync
from src.domain.ports.hash_router_protocol import HashRouterProtocol
from src.domain.ports.index_manager import IndexManagerPort
from src.domain.ports.l0_storage import L0StoragePort
from src.domain.ports.l1_cache import L1CachePort
from src.domain.ports.l2_rdb import BaseRepository, L2RdbPort
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.l4_object import L4ObjectPort
from src.domain.ports.l5_graph import L5GraphPort
from src.domain.ports.layered_retrieval import LayeredRetrievalPort
from src.domain.ports.llm_client import LLMClientPort, LLMConfig, LLMResponse
from src.domain.ports.memory_repository import (
    L2ChangeHistoryRepositoryPort,
    L2GroupMemberRepositoryPort,
    L2MetadataRepositoryPort,
)
from src.domain.ports.ocr import OCR_CONFIDENCE_THRESHOLD, OCR_MAX_BYTES, OCRPort
from src.domain.ports.outbox import OutboxRepository
from src.domain.ports.pdf_page_renderer import PdfPageRendererPort
from src.domain.ports.permission_repository import PermissionRepositoryPort
from src.domain.ports.reranker import RerankerPort
from src.domain.ports.saga import SagaRepositoryProtocol, SagaStep
from src.domain.ports.sandbox_executor import SandboxExecutor
from src.domain.ports.semantic_chunker import SemanticChunkerPort
from src.domain.ports.semantic_router_protocol import SemanticRouterProtocol
from src.domain.ports.session_storage import SessionStorage
from src.domain.ports.snapshot_repository_protocol import SnapshotRepositoryProtocol
from src.domain.ports.storage_enums import DataAccessPattern, StorageLayer, StorageTier
from src.domain.ports.table_detector import TableDetectorPort
from src.domain.ports.table_enhancer import TableSemanticEnhancerPort
from src.domain.ports.table_extractor import (
    TableExtractorPort,  # deprecated: 使用 TableDetectorPort + TableSemanticEnhancerPort 替代
)
from src.domain.ports.udmr_policy import UdmrPolicyPort
from src.domain.ports.unified_storage import UnifiedStoragePort
from src.domain.ports.unit_of_work import UnitOfWork
from src.domain.ports.workflow_engine import WorkflowEnginePort

__all__ = [
    "AgentEnginePort",
    "ArchiveQuery",
    "ArchiveRepositoryPort",
    "ConnectionManager",
    "CrawlerClientPort",
    "DataAccessPattern",
    "BaseRepository",
    "DeadLetterQueue",
    "DictionaryConsumerPort",
    "DictionaryEntry",
    "DictionaryQuery",
    "DictionarySnapshot",
    "DomainDictionaryPort",
    "EmbeddingServicePort",
    "EntityArbitratorPort",
    "EntityExtractionPort",
    "ExtractedEntity",
    "ExtractedRelation",
    "ExtractionResult",
    "EventListener",
    "EventListenerAsync",
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
    "LayeredRetrievalPort",
    "LayoutDetector",
    "LLMClientPort",
    "LLMConfig",
    "LLMResponse",
    "OCRPort",
    "OCR_CONFIDENCE_THRESHOLD",
    "OCR_MAX_BYTES",
    "OutboxRepository",
    "PdfPageRendererPort",
    "PermissionRepositoryPort",
    "RerankerPort",
    "SagaRepositoryProtocol",
    "SagaStep",
    "SandboxExecutor",
    "SemanticChunkerPort",
    "SemanticRouterProtocol",
    "SessionStorage",
    "SnapshotRepositoryProtocol",
    "SparseEmbedding",
    "StorageLayer",
    "StorageTier",
    "TableDetectorPort",
    "TableSemanticEnhancerPort",
    "TableExtractorPort",
    "UnifiedStoragePort",
    "UnitOfWork",
    "UdmrPolicyPort",
    "WorkflowEnginePort",
]
