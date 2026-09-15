"""领域层沙箱异常模块

定义沙箱执行相关的领域异常，包括容器启动失败、代码执行失败、容器停止失败等。
每个异常类分配独立编码（311-319），确保监控可精确区分故障类型。

子域（sandbox 311-319）累计 9 个异常：
- EXCEPTION_311 SandboxError (Story 4.1a)
- EXCEPTION_312 ContainerStartError (Story 4.1a)
- EXCEPTION_313 ExecutionError (Story 4.1a)
- EXCEPTION_314 ContainerStopError (Story 4.1a)
- EXCEPTION_315 SandboxImagePullError (Story 4.4,本模块新增)
- EXCEPTION_316 SandboxTimeoutError (Story 4.4,本模块新增)
- EXCEPTION_317 SandboxResourceLimitExceededError (Story 4.4,本模块新增)
- EXCEPTION_318 SandboxQuotaExceededError (Story 4.4,本模块新增)
- EXCEPTION_319 SandboxConfigurationError (Story 4.4,本模块新增)

HTTP 状态码映射（由 ExceptionHandlers 自动处理）：
- EXCEPTION_315 → 502（上游镜像不可达）
- EXCEPTION_316 → 504（执行超时）
- EXCEPTION_317 → 502（资源限制越界,语义对齐 ExecutionError 父类）
- EXCEPTION_318 → 503（配额超限,服务不可用）
- EXCEPTION_319 → 502（运行时配置错误,与父类 SandboxError 一致）

继承层次设计说明（异常 5 轮审查经验）：
- SandboxTimeoutError / SandboxResourceLimitExceededError 继承 ExecutionError 而非直接继承
  SandboxError,因为"超时/资源超限"是"执行失败"的特定场景,语义层次清晰。
- SandboxImagePullError 继承 ContainerStartError 而非直接继承 SandboxError,因为"镜像拉取失败"
  是"容器启动失败"的特定原因,监控可精确告警。
- SandboxQuotaExceededError / SandboxConfigurationError 直接继承 SandboxError。
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
    """代码执行失败异常."""

    code = "EXCEPTION_313"
    message = "Execution error"


class ContainerStopError(SandboxError):
    """容器停止失败异常."""

    code = "EXCEPTION_314"
    message = "Container stop error"


class SandboxImagePullError(ContainerStartError):
    """EXCEPTION_315 — 容器镜像拉取失败

    继承自 ContainerStartError (EXCEPTION_312) → HTTP 502（上游不可达）。
    触发场景：
    - 镜像 digest 不存在（私有仓库镜像被删除）
    - Docker daemon 拉取权限不足（registry 认证失败）
    - 镜像拉取网络超时（registry 不可达）
    - 镜像 manifest 格式错误（OCI 规范违反）

    Attributes:
        code: 错误码 EXCEPTION_315
        message: 默认消息
    """

    code = "EXCEPTION_315"
    message = "Sandbox image pull error"

    def __init__(
        self,
        message: str | None = None,
        image: str | None = None,
        session_id: str | None = None,
        digest: str | None = None,
        docker_error: str | None = None,
    ) -> None:
        context: dict = {}
        if image is not None:
            context["image"] = image
        if session_id is not None:
            context["session_id"] = session_id
        if digest is not None:
            context["digest"] = digest
        if docker_error is not None:
            context["docker_error"] = docker_error
        super().__init__(message=message, context=context)


class SandboxTimeoutError(ExecutionError):
    """EXCEPTION_316 — 代码执行超过 ContainerSpec.timeout_sec

    继承自 ExecutionError (EXCEPTION_313) → HTTP 504（执行超时）。
    触发场景：
    - 代码执行 wall time 超过 ContainerSpec.timeout_sec（默认 30 秒，上限 300 秒）
    - asyncio.wait_for() 触发超时回调
    - 容器内进程因 hang 导致无法在时限内返回

    Attributes:
        code: 错误码 EXCEPTION_316
        message: 默认消息
    """

    code = "EXCEPTION_316"
    message = "Sandbox execution timeout"

    def __init__(
        self,
        message: str | None = None,
        session_id: str | None = None,
        timeout_sec: float | None = None,
        execution_id: str | None = None,
        docker_exit_code: int | None = None,
    ) -> None:
        context: dict = {}
        if session_id is not None:
            context["session_id"] = session_id
        if timeout_sec is not None:
            context["timeout_sec"] = timeout_sec
        if execution_id is not None:
            context["execution_id"] = execution_id
        if docker_exit_code is not None:
            context["docker_exit_code"] = docker_exit_code
        super().__init__(message=message, context=context)


class SandboxResourceLimitExceededError(ExecutionError):
    """EXCEPTION_317 — 容器资源超出 cgroups 限制

    继承自 ExecutionError (EXCEPTION_313) → HTTP 502（语义对齐父类）。
    触发场景：
    - OOM kill（exit 137）：mem_limit 越界
    - CPU throttle 超限：cpu_quota 越界
    - fork bomb 触发：pids_limit 越界（cgroup 杀死进程）

    Attributes:
        code: 错误码 EXCEPTION_317
        message: 默认消息
    """

    code = "EXCEPTION_317"
    message = "Sandbox resource limit exceeded"

    def __init__(
        self,
        message: str | None = None,
        session_id: str | None = None,
        limit_type: str | None = None,
        limit_value: float | int | None = None,
        actual_value: float | int | None = None,
        docker_exit_code: int | None = None,
    ) -> None:
        context: dict = {}
        if session_id is not None:
            context["session_id"] = session_id
        if limit_type is not None:
            context["limit_type"] = limit_type
        if limit_value is not None:
            context["limit_value"] = limit_value
        if actual_value is not None:
            context["actual_value"] = actual_value
        if docker_exit_code is not None:
            context["docker_exit_code"] = docker_exit_code
        super().__init__(message=message, context=context)


class SandboxQuotaExceededError(SandboxError):
    """EXCEPTION_318 — 并发容器数超过 MAX_CONCURRENT_CONTAINERS

    继承自 SandboxError (EXCEPTION_311) → HTTP 503（服务不可用）。
    触发场景：
    - 启动新容器时，当前活跃容器数已超过 MAX_CONCURRENT_CONTAINERS（默认 50）
    - 多租户并发争抢资源

    Attributes:
        code: 错误码 EXCEPTION_318
        message: 默认消息
    """

    code = "EXCEPTION_318"
    message = "Sandbox quota exceeded"

    def __init__(
        self,
        message: str | None = None,
        current_count: int | None = None,
        max_count: int | None = None,
        tenant_id: str | None = None,
    ) -> None:
        context: dict = {}
        if current_count is not None:
            context["current_count"] = current_count
        if max_count is not None:
            context["max_count"] = max_count
        if tenant_id is not None:
            context["tenant_id"] = tenant_id
        super().__init__(message=message, context=context)


class SandboxConfigurationError(SandboxError):
    """EXCEPTION_319 — 容器规格 / 运行时配置错误

    继承自 SandboxError (EXCEPTION_311) → HTTP 502（运行时配置错误）。
    触发场景：
    - ContainerSpec 字段不合法（如 image digest 缺失、mem_limit 越界）
    - seccomp profile 文件加载失败
    - 容器名长度超 Docker 64 字符上限
    - session_id 格式不符合 ^[A-Za-z0-9_-]{1,64}$（防注入）

    Attributes:
        code: 错误码 EXCEPTION_319
        message: 默认消息
    """

    code = "EXCEPTION_319"
    message = "Sandbox configuration error"

    def __init__(
        self,
        message: str | None = None,
        field_name: str | None = None,
        field_value: str | int | None = None,
        reason: str | None = None,
    ) -> None:
        context: dict = {}
        if field_name is not None:
            context["field_name"] = field_name
        if field_value is not None:
            context["field_value"] = field_value
        if reason is not None:
            context["reason"] = reason
        super().__init__(message=message, context=context)


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
