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

__all__ = [
    "AttackDetectionResult",
    "AuthValidationResult",
    "AutoTriggerContext",
    "BackupResult",
    "BackupStatus",
    "BackupType",
    "ComplianceResult",
    "EncryptedData",
    "EncryptionVerificationResult",
    "EscapeAttempt",
    "FlowStatus",
    "InjectionDetectionResult",
    "IntegrityResult",
    "IntrusionStats",
    "IsolationVerificationResult",
    "NetworkIsolationResult",
    "RateLimitResult",
    "ResourceLimitsStatus",
    "RestoreResult",
    "TokenPayload",
    "UDMRTask",
]
