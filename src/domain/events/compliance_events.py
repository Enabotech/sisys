"""SISYS 领域层 合规事件模块

定义数据主权、PIPL和等保2.0相关的领域事件

本模块中的事件遵循DomainEvent标准：
- 仅使用Python标准库类型（dataclasses、uuid、datetime）
- 领域事件中不使用Pydantic
- 子类特定字段通过to_dict()包含在payload中

等保2.0三级合规事件：
- MFAChallengeIssuedEvent: 多因素认证挑战
- IntrusionDetectedEvent: 安全入侵检测
- DataIntegrityViolationEvent: 数据完整性违规检测

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from src.domain.entities.sensitive_data_result import SensitiveType

from .base import DomainEvent


class MFAChallengeType(str, Enum):
    """支持的MFA挑战类型。"""

    TOTP = "totp"  # 基于时间的一次性密码
    HOTP = "hotp"  # 基于HMAC的一次性密码
    SMS = "sms"  # 短信验证码（MVP中未实现）
    EMAIL = "email"  # 邮件验证码（MVP中未实现）


class MFAChallengeStatus(str, Enum):
    """MFA挑战状态。"""

    PENDING = "pending"  # 待处理
    VERIFIED = "verified"  # 已验证
    EXPIRED = "expired"  # 已过期
    FAILED = "failed"  # 已失败


class IntrusionSeverity(str, Enum):
    """入侵严重级别。"""

    LOW = "low"  # 低
    MEDIUM = "medium"  # 中
    HIGH = "high"  # 高
    CRITICAL = "critical"  # 严重


class IntrusionAction(str, Enum):
    """入侵响应采取的动作。"""

    LOGGED = "logged"  # 已记录
    ALERTED = "alerted"  # 已告警
    BLOCKED = "blocked"  # 已阻止
    QUARANTINED = "quarantined"  # 已隔离


class AttackType(str, Enum):
    """入侵检测的常见攻击类型。"""

    BRUTE_FORCE = "brute_force"  # 暴力破解
    SQL_INJECTION = "sql_injection"  # SQL注入
    XSS = "xss"  # 跨站脚本
    CSRF = "csrf"  # 跨站请求伪造
    PATH_TRAVERSAL = "path_traversal"  # 路径遍历
    COMMAND_INJECTION = "command_injection"  # 命令注入
    RATE_LIMIT_VIOLATION = "rate_limit_violation"  # 速率限制违规
    PROMPT_INJECTION = "prompt_injection"  # 提示注入
    UNAUTHORIZED_ACCESS = "unauthorized_access"  # 未授权访问
    DATA_EXFILTRATION = "data_exfiltration"  # 数据泄露


@dataclass(frozen=True)
class MFAChallengeIssuedEvent(DomainEvent):
    """向用户发放MFA挑战时触发的事件

    在MFA设置或验证流程中触发
    用于审计日志记录和安全合规（等保2.0）

    Attributes:
        challenge_id: 挑战唯一标识符
        event_type: 事件类型，固定为"MFAChallengeIssuedEvent"
        user_id: 用户唯一标识符
        challenge_type: 挑战类型（TOTP/HOTP/SMS/EMAIL）
        status: 挑战状态
        expires_at: 过期时间
        issued_at: 发放时间
        ip_address: 客户端IP地址
        user_agent: 客户端User-Agent
    """

    challenge_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="MFAChallengeIssuedEvent", init=False)
    user_id: uuid.UUID = field(default_factory=uuid.uuid4)
    challenge_type: MFAChallengeType = MFAChallengeType.TOTP
    status: MFAChallengeStatus = MFAChallengeStatus.PENDING
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    issued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ip_address: str = ""
    user_agent: str = ""

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.challenge_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "MFAChallenge")


@dataclass(frozen=True)
class IntrusionDetectedEvent(DomainEvent):
    """检测到入侵尝试时触发的事件

    由IntrusionDetector在识别恶意活动时触发
    用于安全审计和事件响应（等保2.0入侵防范）

    Attributes:
        intrusion_id: 入侵检测唯一标识符
        event_type: 事件类型，固定为"IntrusionDetectedEvent"
        source_ip: 攻击来源IP地址
        attack_type: 攻击类型
        severity: 严重级别
        action_taken: 采取的响应动作
        description: 描述信息
        raw_evidence: 原始日志/证据数据
        detected_at: 检测时间
    """

    intrusion_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="IntrusionDetectedEvent", init=False)
    source_ip: str = ""
    attack_type: AttackType = AttackType.BRUTE_FORCE
    severity: IntrusionSeverity = IntrusionSeverity.MEDIUM
    action_taken: IntrusionAction = IntrusionAction.LOGGED
    description: str = ""
    raw_evidence: str = ""  # Raw log/evidence data
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.intrusion_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "IntrusionDetection")


@dataclass(frozen=True)
class DataIntegrityViolationEvent(DomainEvent):
    """检测到数据完整性违规时触发的事件

    在数据哈希验证失败时触发，表明数据可能被篡改
    用于数据完整性审计（等保2.0数据完整性）

    Attributes:
        violation_id: 违规唯一标识符
        event_type: 事件类型，固定为"DataIntegrityViolationEvent"
        data_id: 数据唯一标识符
        expected_hash: 预期的哈希值
        actual_hash: 实际的哈希值
        source: 数据存储/访问位置
        verification_method: 验证方法（sha256、sha512、md5）
        detected_at: 检测时间
    """

    violation_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="DataIntegrityViolationEvent", init=False)
    data_id: uuid.UUID = field(default_factory=uuid.uuid4)
    expected_hash: str = ""
    actual_hash: str = ""
    source: str = ""  # Where the data is stored/accessed
    verification_method: str = "sha256"  # sha256, sha512, md5
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.violation_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "DataIntegrity")


@dataclass(frozen=True)
class SensitiveDataDetected(DomainEvent):
    """检测到敏感数据时触发的事件

    在数据摄入或访问时触发，标记敏感数据以进行适当处理
    （本地处理、加密等）

    Attributes:
        data_id: 数据唯一标识符
        event_type: 事件类型，固定为"SensitiveDataDetected"
        sensitive_type: 敏感数据类型
        confidence: 检测置信度，范围0.0-1.0
        labels: 附加标签
        detection_method: 检测方法（regex、keyword、nlp）
        detected_at: 检测时间
    """

    data_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="SensitiveDataDetected", init=False)
    sensitive_type: SensitiveType = SensitiveType.PII
    confidence: float = 1.0  # Detection confidence 0.0-1.0
    labels: list[str] = field(default_factory=list)  # Additional labels
    detection_method: str = "regex"  # regex, keyword, nlp
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.data_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "DataSovereignty")


@dataclass(frozen=True)
class CrossBorderTransferRequested(DomainEvent):
    """请求跨境数据传输时触发的事件

    此事件触发需要传输到境外的数据审批工作流

    Attributes:
        request_id: 请求唯一标识符
        data_id: 数据唯一标识符
        event_type: 事件类型，固定为"CrossBorderTransferRequested"
        destination: 目的地国家/地区
        purpose: 传输目的
        approval_id: 审批ID（审批工作流启动后设置）
        status: 状态（pending、approved、rejected、blocked）
        requester: 请求传输的用户ID
        requested_at: 请求时间
    """

    request_id: uuid.UUID = field(default_factory=uuid.uuid4)
    data_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="CrossBorderTransferRequested", init=False)
    destination: str = ""  # Destination country/region
    purpose: str = ""  # Purpose of transfer
    approval_id: uuid.UUID | None = None  # Set after approval workflow starts
    status: str = "pending"  # pending, approved, rejected, blocked
    requester: str = ""  # User ID who requested the transfer
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.request_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "CrossBorderTransfer")


@dataclass(frozen=True)
class DataSovereigntyViolation(DomainEvent):
    """数据主权策略违规时触发的事件

    Attributes:
        violation_id: 违规唯一标识符
        data_id: 数据唯一标识符
        event_type: 事件类型，固定为"DataSovereigntyViolation"
        violation_type: 违规类型（如unauthorized_transfer、境外_storage等）
        severity: 严重级别（low、medium、high、critical）
        description: 描述信息
        detected_at: 检测时间
    """

    violation_id: uuid.UUID = field(default_factory=uuid.uuid4)
    data_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="DataSovereigntyViolation", init=False)
    violation_type: str = ""  # 违规类型：unauthorized_transfer、境外_storage等
    severity: str = "high"  # low, medium, high, critical
    description: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.violation_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "DataSovereignty")


@dataclass(frozen=True)
class PIPLDataAccessRequested(DomainEvent):
    """PIPL框架下访问个人信息时触发的事件

    PIPL要求追踪所有个人信息访问，包括目的、法律依据和数据主体同意

    Attributes:
        access_id: 访问唯一标识符
        personal_data_id: 个人数据唯一标识符
        event_type: 事件类型，固定为"PIPLDataAccessRequested"
        purpose: 数据处理目的
        legal_basis: 法律依据（consent、contract、legal_obligation等）
        data_subject_consent: 数据主体是否同意
        accessor: 访问数据的用户/系统
        accessed_at: 访问时间
    """

    access_id: uuid.UUID = field(default_factory=uuid.uuid4)
    personal_data_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = field(default="PIPLDataAccessRequested", init=False)
    purpose: str = ""  # Purpose of data processing
    legal_basis: str = ""  # Legal basis: consent, contract, legal_obligation, etc.
    data_subject_consent: bool = False
    accessor: str = ""  # User/System accessing the data
    accessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """设置aggregate_id和aggregate_type。"""
        if self.aggregate_id is None:
            object.__setattr__(self, "aggregate_id", self.access_id)
        if not self.aggregate_type:
            object.__setattr__(self, "aggregate_type", "PIPLCompliance")
