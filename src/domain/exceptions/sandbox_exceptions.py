"""领域层沙箱异常模块

定义沙箱执行相关的领域异常，包括容器启动失败、代码执行失败、容器停止失败等。
每个异常类分配独立编码（311-319），确保监控可精确区分故障类型。

Story 4.4 新增 5 个异常：
- EXCEPTION_315 SandboxImagePullError — 镜像拉取失败
- EXCEPTION_316 SandboxTimeoutError — 代码执行超时
- EXCEPTION_317 SandboxResourceLimitExceededError — 资源超限（OOM 等）
- EXCEPTION_318 SandboxQuotaExceededError — 并发容器数超配额
- EXCEPTION_319 SandboxConfigurationError — 容器规格配置错误
"""

from __future__ import annotations

from src.domain.exceptions.external_exceptions import ExternalException


class SandboxError(ExternalException):
    """沙箱基础异常."""

    code = "EXCEPTION_311"
    message = "Sandbox error"


class ContainerStartError(SandboxError):
    """容器启动失败异常."""

    code = "EXCEPTION_312"
    message = "Container start error"


class ExecutionError(SandboxError):
    """代码执行失败异常.

    Story 4.7 构造器增强（STDERR 数据链——AC-1）：stderr/exit_code 可选参数
    写入 context（stderr 截断 ≤2000 防 DoS）；context/cause 透传合并——两个
    既有子类 SandboxTimeoutError/SandboxResourceLimitExceededError 的
    super().__init__(reason, context={...}) 调用零改动兼容（Task 0 契约）。
    """

    code = "EXCEPTION_313"
    message = "Execution error"

    # stderr 截断上限（摘录字段统一口径）
    _STDERR_MAX_LENGTH = 2000

    def __init__(
        self,
        message: str | None = None,
        *,
        stderr: str | None = None,
        exit_code: int | None = None,
        cause: Exception | None = None,
        context: dict | None = None,
    ) -> None:
        """初始化并合并 STDERR 数据链字段.

        Args:
            message: 错误消息
            stderr: 标准错误输出（截断 ≤2000——Validation Feedback 闭环的修复输入）
            exit_code: 容器退出码
            cause: 原始异常（透传保留链路）
            context: 附加上下文（透传合并——新字段优先，既有键不被覆盖）
        """
        merged: dict = {**(context or {})}
        if stderr is not None:
            merged["stderr"] = stderr[: self._STDERR_MAX_LENGTH]
        if exit_code is not None:
            merged["exit_code"] = exit_code
        super().__init__(message=message, cause=cause, context=merged)


class ContainerStopError(SandboxError):
    """容器停止失败异常."""

    code = "EXCEPTION_314"
    message = "Container stop error"


class SandboxImagePullError(ContainerStartError):
    """EXCEPTION_315 — 容器镜像拉取失败.

    触发场景：
    - 镜像 digest 不存在
    - Docker daemon 拉取权限不足
    - 网络超时（registry 不可达）
    """

    code = "EXCEPTION_315"
    message = "Sandbox image pull error"

    def __init__(
        self,
        reason: str,
        *,
        image: str | None = None,
        session_id: str | None = None,
        digest: str | None = None,
        docker_error: str | None = None,
    ) -> None:
        super().__init__(
            reason,
            context={
                "image": image,
                "session_id": session_id,
                "digest": digest,
                "docker_error": docker_error,
            },
        )


class SandboxTimeoutError(ExecutionError):
    """EXCEPTION_316 — 代码执行超时.

    触发场景：容器内代码执行超过 ``ContainerSpec.timeout_sec``（默认 30s）。
    HTTP 映射 504 Gateway Timeout。
    """

    code = "EXCEPTION_316"
    message = "Sandbox execution timeout"

    def __init__(
        self,
        reason: str,
        *,
        session_id: str | None = None,
        timeout_sec: float | None = None,
        execution_id: str | None = None,
        docker_exit_code: int | None = None,
    ) -> None:
        super().__init__(
            reason,
            context={
                "session_id": session_id,
                "timeout_sec": timeout_sec,
                "execution_id": execution_id,
                "docker_exit_code": docker_exit_code,
            },
        )


class SandboxResourceLimitExceededError(ExecutionError):
    """EXCEPTION_317 — 容器资源超限.

    触发场景：容器内存/CPU/pids 超出 cgroups 限制（典型为 OOM kill exit 137）。
    """

    code = "EXCEPTION_317"
    message = "Sandbox resource limit exceeded"

    def __init__(
        self,
        reason: str,
        *,
        session_id: str | None = None,
        limit_type: str | None = None,
        limit_value: float | int | None = None,
        actual_value: float | int | None = None,
        docker_exit_code: int | None = None,
    ) -> None:
        super().__init__(
            reason,
            context={
                "session_id": session_id,
                "limit_type": limit_type,
                "limit_value": limit_value,
                "actual_value": actual_value,
                "docker_exit_code": docker_exit_code,
            },
        )


class SandboxQuotaExceededError(SandboxError):
    """EXCEPTION_318 — 并发容器数超过配额.

    触发场景：当前并发容器数 >= ``MAX_CONCURRENT_CONTAINERS``（默认 50）。
    HTTP 映射 503 Service Unavailable。
    """

    code = "EXCEPTION_318"
    message = "Sandbox quota exceeded"

    def __init__(
        self,
        reason: str,
        *,
        current_count: int | None = None,
        max_count: int | None = None,
        tenant_id: str | None = None,
    ) -> None:
        super().__init__(
            reason,
            context={
                "current_count": current_count,
                "max_count": max_count,
                "tenant_id": tenant_id,
            },
        )


class SandboxConfigurationError(SandboxError):
    """EXCEPTION_319 — 容器规格配置错误.

    触发场景：
    - ContainerSpec 字段不合法（运行时校验失败，区别于领域层 __post_init__）
    - seccomp profile 加载失败
    - 容器名长度超 Docker 64 字符上限
    """

    code = "EXCEPTION_319"
    message = "Sandbox configuration error"

    def __init__(
        self,
        reason: str,
        *,
        field_name: str | None = None,
        field_value: object = None,
        reason_detail: str | None = None,
    ) -> None:
        super().__init__(
            reason,
            context={
                "field_name": field_name,
                "field_value": field_value,
                "reason_detail": reason_detail,
            },
        )


__all__ = [
    "SandboxError",
    "ContainerStartError",
    "ExecutionError",
    "ContainerStopError",
    "SandboxImagePullError",
    "SandboxTimeoutError",
    "SandboxResourceLimitExceededError",
    "SandboxQuotaExceededError",
    "SandboxConfigurationError",
]
