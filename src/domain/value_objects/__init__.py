"""领域层值对象模块

领域值对象是领域模型中的不可变对象，通过值而非标识来衡量
本模块聚合所有值对象定义，统一对外导出
"""

from src.domain.value_objects.api_security_result import (
    AuthValidationResult,
    InjectionDetectionResult,
    RateLimitResult,
)
from src.domain.value_objects.auto_trigger_context import AutoTriggerContext
from src.domain.value_objects.backup_result import (
    BackupResult,
    BackupStatus,
    BackupType,
    RestoreResult,
)
from src.domain.value_objects.compliance_result import ComplianceResult
from src.domain.value_objects.container_security_result import (
    EscapeAttempt,
    IsolationVerificationResult,
    NetworkIsolationResult,
    ResourceLimitsStatus,
)
from src.domain.value_objects.data_integrity_result import IntegrityResult
from src.domain.value_objects.document_format import (
    ARCHIVE_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    SUPPORTED_FORMATS,
    get_extension,
    get_mime_type,
    is_supported,
)
from src.domain.value_objects.flow_status import FlowStatus
from src.domain.value_objects.intrusion_detection_result import (
    AttackDetectionResult,
    IntrusionStats,
)
from src.domain.value_objects.storage_encryption_result import (
    EncryptedData,
    EncryptionVerificationResult,
)
from src.domain.value_objects.token_payload import TokenPayload
from src.domain.value_objects.udmr_task import UDMRTask
from src.domain.value_objects.upload_limits import (
    CHUNK_SIZES,
    CHUNKED_UPLOAD_TTL,
    MAX_ARCHIVE_EXTRACTED_SIZE,
    MAX_BATCH_COUNT,
    MAX_BATCH_SIZE,
    MAX_COMPRESSION_RATIO,
    MAX_FILE_SIZE,
    MAX_FILENAME_LENGTH,
    MAX_NESTING_DEPTH,
    get_chunk_size,
)

__all__ = [
    "ARCHIVE_EXTENSIONS",
    "AttackDetectionResult",
    "AuthValidationResult",
    "AutoTriggerContext",
    "BackupResult",
    "BackupStatus",
    "BackupType",
    "CHUNKED_UPLOAD_TTL",
    "CHUNK_SIZES",
    "ComplianceResult",
    "DOCUMENT_EXTENSIONS",
    "EncryptedData",
    "EncryptionVerificationResult",
    "EscapeAttempt",
    "FlowStatus",
    "InjectionDetectionResult",
    "IntegrityResult",
    "IntrusionStats",
    "IsolationVerificationResult",
    "MAX_ARCHIVE_EXTRACTED_SIZE",
    "MAX_BATCH_COUNT",
    "MAX_BATCH_SIZE",
    "MAX_COMPRESSION_RATIO",
    "MAX_FILE_SIZE",
    "MAX_FILENAME_LENGTH",
    "MAX_NESTING_DEPTH",
    "NetworkIsolationResult",
    "RateLimitResult",
    "ResourceLimitsStatus",
    "RestoreResult",
    "SUPPORTED_FORMATS",
    "TokenPayload",
    "UDMRTask",
    "get_chunk_size",
    "get_extension",
    "get_mime_type",
    "is_supported",
]
