"""领域层容器安全结果值对象

定义容器安全服务返回的结果类型，用于等保2.0三级容器安全
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IsolationVerificationResult:
    """沙箱隔离验证结果

    Attributes:
        isolated: 容器是否正确隔离
        container_id: 容器标识符
        violations: 隔离违规列表
        network_isolated: 网络是否隔离
        resource_limits_enforced: 资源限制是否生效
    """

    isolated: bool = False
    container_id: str = ""
    violations: list[str] = field(default_factory=list)
    network_isolated: bool = False
    resource_limits_enforced: bool = False


@dataclass(frozen=True)
class ResourceLimitsStatus:
    """容器资源限制状态

    Attributes:
        within_limits: 资源使用是否在限制内
        container_id: 容器标识符
        cpu_usage_percent: CPU 使用率百分比
        memory_usage_mb: 内存使用量（MB）
        cpu_limit: CPU 限制（核数）
        memory_limit_mb: 内存限制（MB）
    """

    within_limits: bool = False
    container_id: str = ""
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_limit: float = 0.0
    memory_limit_mb: float = 0.0


@dataclass(frozen=True)
class EscapeAttempt:
    """容器逃逸尝试记录

    Attributes:
        detected: 是否检测到逃逸尝试
        container_id: 容器标识符
        attempt_type: 逃逸尝试类型
        severity: 严重级别
        evidence: 证据数据
        timestamp: 检测时间（ISO 格式）
    """

    detected: bool = False
    container_id: str = ""
    attempt_type: str = ""
    severity: str = "high"
    evidence: str = ""
    timestamp: str = ""


@dataclass(frozen=True)
class NetworkIsolationResult:
    """容器网络隔离验证结果

    Attributes:
        isolated: 网络是否正确隔离
        container_id: 容器标识符
        allowed_hosts: 允许访问的主机列表
        blocked_connections: 已阻断的连接列表
    """

    isolated: bool = False
    container_id: str = ""
    allowed_hosts: list[str] = field(default_factory=list)
    blocked_connections: list[str] = field(default_factory=list)
