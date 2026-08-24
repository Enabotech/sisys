"""领域层异常模块

领域异常层次结构：
- DomainError: 异常层次结构根类
- SystemException: 系统级异常（基础设施故障）
- BusinessException: 业务级异常（业务规则违反）
- ExternalException: 外部服务异常

架构约束：领域层零依赖，仅使用 Python 标准库
"""

from __future__ import annotations

from src.domain.exceptions.archive_exceptions import (
    ArchiveConflictError,
    ArchiveNotFoundError,
    ArchiveStorageError,
    ValidityPeriodConflictError,
)
from src.domain.exceptions.base_exceptions import BaseException, DomainError  # BaseException 是向后兼容别名
from src.domain.exceptions.business_exceptions import (
    AuthenticationError,
    BusinessException,
    BusinessRuleViolationError,
    ConflictError,
    EntityBusinessRuleError,
    EntityStateTransitionError,
    EntityValidationError,
    InvalidStateError,
    InvalidStateTransitionError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from src.domain.exceptions.dictionary_exceptions import (
    DictionaryEntryConflictError,
    DictionaryNotFoundError,
    DictionaryVersionConflictError,
)
from src.domain.exceptions.embedding_exceptions import (
    ConcurrencyOverloadError,
    EmbeddingAPIError,
    EmbeddingModelError,
    EmbeddingResponseError,
    ModelInferenceError,
)
from src.domain.exceptions.entity_extraction_exceptions import EntityExtractionError
from src.domain.exceptions.event_exceptions import VersionError
from src.domain.exceptions.external_exceptions import (
    ExternalException,
    ServiceUnavailableError,
    ThirdPartyError,
    TimeoutError,
    UnknownError,
)
from src.domain.exceptions.hybrid_search_exceptions import HybridSearchError
from src.domain.exceptions.layered_retrieval_exceptions import (
    LayeredRetrievalError,
    LevelTransitionError,
)
from src.domain.exceptions.llm_exceptions import (
    LLMAPIError,
    LLMConfigError,
    LLMResponseError,
)
from src.domain.exceptions.ocr_exceptions import (
    OCRConnectionError,
    OCRProcessingError,
)
from src.domain.exceptions.permission_exceptions import InsufficientTokenError
from src.domain.exceptions.relevance_exceptions import (
    RelevanceEvaluationBlockedError,
    RelevanceEvaluationError,
)
from src.domain.exceptions.reranker_exceptions import RerankError
from src.domain.exceptions.role_exceptions import (
    CannotDeleteRoleWithUsersError,
    CannotDeleteSystemRoleError,
    RoleAlreadyExistsError,
    RoleNotFoundError,
)
from src.domain.exceptions.sandbox_exceptions import (
    ContainerStartError,
    ContainerStopError,
    ExecutionError,
    SandboxError,
)
from src.domain.exceptions.service_exceptions import (
    AuditError,
    ComplianceLockError,
    PasswordValidationError,
)
from src.domain.exceptions.storage_exceptions import (
    BucketNameValidationError,
    BucketNotFoundError,
    ChunkingError,
    DocumentVersionConflictError,
    MemoryAccessDeniedError,
    MemoryNotFoundError,
    MemoryVersionConflictError,
    MetadataValidationError,
    MinIOConnectionError,
    UploadSessionExpiredError,
)
from src.domain.exceptions.summary_exceptions import (
    SummaryGenerationError,
    SummaryPerspectiveNotSupportedError,
)
from src.domain.exceptions.system_exceptions import (
    ConfigurationError,
    MessageBusError,
    NetworkError,
    StorageError,
    SystemException,
)
from src.domain.exceptions.traceability_exceptions import (
    TraceabilityError,
    TraceabilityNotFoundError,
)
from src.domain.exceptions.transfer_exceptions import (
    TransferNotApprovedError,
    TransferNotFoundError,
)

__all__ = [
    # 抽象根类
    "DomainError",
    "BaseException",  # 向后兼容别名
    # 系统级异常
    "SystemException",
    "ConfigurationError",
    "NetworkError",
    "StorageError",
    "MessageBusError",
    # 业务级异常
    "BusinessException",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "PermissionDeniedError",
    "AuthenticationError",
    "InvalidStateError",
    "InvalidStateTransitionError",
    "BusinessRuleViolationError",
    "EntityValidationError",
    "EntityStateTransitionError",
    "EntityBusinessRuleError",
    # 外部服务异常
    "ExternalException",
    "ThirdPartyError",
    "TimeoutError",
    "ServiceUnavailableError",
    "UnknownError",
    # 服务异常
    "AuditError",
    "PasswordValidationError",
    "ComplianceLockError",
    "DocumentVersionConflictError",
    "MetadataValidationError",
    "ChunkingError",
    # 存储异常
    "MemoryVersionConflictError",
    "MemoryNotFoundError",
    "BucketNotFoundError",
    "MinIOConnectionError",
    "BucketNameValidationError",
    "MemoryAccessDeniedError",
    "UploadSessionExpiredError",
    # 角色管理异常
    "RoleAlreadyExistsError",
    "RoleNotFoundError",
    "CannotDeleteSystemRoleError",
    "CannotDeleteRoleWithUsersError",
    # Sandbox异常
    "SandboxError",
    "ContainerStartError",
    "ExecutionError",
    "ContainerStopError",
    # 嵌入服务异常
    "EmbeddingAPIError",
    "EmbeddingResponseError",
    "EmbeddingModelError",
    "ModelInferenceError",
    "ConcurrencyOverloadError",
    # LLM 异常
    "LLMAPIError",
    "LLMResponseError",
    "LLMConfigError",
    # 实体抽取异常
    "EntityExtractionError",
    # 重排序异常
    "RerankError",
    # 检索相关性评估异常
    "RelevanceEvaluationError",
    "RelevanceEvaluationBlockedError",
    # 混合检索异常
    "HybridSearchError",
    # 分层检索异常
    "LayeredRetrievalError",
    "LevelTransitionError",
    # OCR 异常
    "OCRConnectionError",
    "OCRProcessingError",
    # 权限异常
    "InsufficientTokenError",
    # 事件异常
    "VersionError",
    # 跨境传输异常
    "TransferNotFoundError",
    "TransferNotApprovedError",
    # 词典管理异常
    "DictionaryNotFoundError",
    "DictionaryEntryConflictError",
    "DictionaryVersionConflictError",
    # 档案管理异常
    "ArchiveNotFoundError",
    "ArchiveConflictError",
    "ArchiveStorageError",
    "ValidityPeriodConflictError",
    # 摘要生成异常
    "SummaryGenerationError",
    "SummaryPerspectiveNotSupportedError",
    # 溯源异常
    "TraceabilityError",
    "TraceabilityNotFoundError",
]
