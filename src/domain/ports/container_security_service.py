"""领域层容器安全服务端口模块

定义容器安全服务的抽象接口，遵循六边形架构端口协议
用于等保2.0三级容器安全

设计原则：
- verify_sandbox_isolation(): 沙箱隔离验证
- check_container_limits(): 资源限制检查
- detect_escape_attempts(): 逃逸尝试检测
- validate_container_network_isolation(): 网络隔离验证

注意：detect_escape_attempts 返回类型使用 list[EscapeAttempt]
（Python 3.9+ 内置泛型），而非 List[EscapeAttempt]（typing 模块）
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.value_objects.container_security_result import (
    EscapeAttempt,
    IsolationVerificationResult,
    NetworkIsolationResult,
    ResourceLimitsStatus,
)


@runtime_checkable
class ContainerSecurityServicePort(Protocol):
    """容器安全服务抽象端口

    等保2.0三级容器安全要求的核心服务端口，负责：
    - 沙箱隔离验证（Docker/gVisor）
    - 资源限制检查（CPU/内存）
    - 容器逃逸检测
    - 网络隔离验证

    实现类必须遵循此接口契约，确保端口的可替换性
    """

    async def verify_sandbox_isolation(
        self,
        container_id: str,
    ) -> IsolationVerificationResult:
        """验证沙箱隔离状态

        Args:
            container_id: 容器标识符

        Returns:
            IsolationVerificationResult 包含隔离验证结果和违规列表
        """
        ...

    async def check_container_limits(
        self,
        container_id: str,
    ) -> ResourceLimitsStatus:
        """检查容器资源限制

        Args:
            container_id: 容器标识符

        Returns:
            ResourceLimitsStatus 包含资源使用和限制状态
        """
        ...

    async def detect_escape_attempts(
        self,
        container_id: str,
    ) -> list[EscapeAttempt]:
        """检测容器逃逸尝试

        Args:
            container_id: 容器标识符

        Returns:
            逃逸尝试记录列表
        """
        ...

    async def validate_container_network_isolation(
        self,
        container_id: str,
    ) -> NetworkIsolationResult:
        """验证容器网络隔离

        Args:
            container_id: 容器标识符

        Returns:
            NetworkIsolationResult 包含网络隔离验证结果
        """
        ...
