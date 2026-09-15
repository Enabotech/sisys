"""领域层沙箱执行端口模块（Story 4.4 向后兼容扩展)

定义沙箱执行适配器的接口协议。Story 4.4 通过**默认参数**扩展入参签名
(不破坏 4.1a 既有 4 方法的调用行为),并新增 health_check() 方法。

向后兼容原则（CLAUDE.md §4 端口契约 + Story 4.3 经验）:
- 既有 4 方法位置参数调用不受影响（默认参数 None → 沿用既有默认配置）
- @runtime_checkable Protocol 不验证默认参数
- inspect.signature() 会反映参数扩展,但既有调用点按位置参数调用不受影响
- 4.1a 调用点零修改（ToolExecutionEngine.__init__ 既有签名不变)
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.domain.exceptions.sandbox_exceptions import (
    ContainerStartError,
    ContainerStopError,
    ExecutionError,
    SandboxError,
)
from src.domain.value_objects.container_spec import ContainerSpec

__all__ = [
    "SandboxError",
    "ContainerStartError",
    "ExecutionError",
    "ContainerStopError",
]


@runtime_checkable
class SandboxExecutor(Protocol):
    """沙箱执行协议端口（Story 4.4 扩展,向后兼容 4.1a 既有签名)

    调用行为保持不变:
    - 既有 4 方法位置参数调用不受影响
    - 新增可选 ContainerSpec 参数（默认 None → 沿用既有默认配置)
    - 新增方法 health_check() 用于监控与熔断器集成
    """

    async def start_container(
        self,
        session_id: str,
        spec: ContainerSpec | None = None,  # 新增可选参数(默认 None),向后兼容
    ) -> None:
        """为指定会话启动沙箱容器。

        Args:
            session_id: 会话唯一标识(字符串,匹配 ^[A-Za-z0-9_-]{1,64}$)
            spec: 可选容器规格(默认 None → 沿用 4.1a 既有默认配置)

        Raises:
            ContainerStartError: 容器启动失败
            SandboxImagePullError: 镜像拉取失败(Story 4.4 新增 EXCEPTION_315)
            SandboxQuotaExceededError: 并发容器数超 MAX_CONCURRENT_CONTAINERS(Story 4.4 EXCEPTION_318)
            SandboxConfigurationError: session_id 格式非法或容器名超长(Story 4.4 EXCEPTION_319)
        """
        ...

    async def execute_code(
        self,
        session_id: str,
        code: str,
        *,
        timeout_sec: float | None = None,  # 新增可选 keyword-only 参数(默认 None),向后兼容
    ) -> dict[str, Any]:
        """在沙箱中执行代码。

        Args:
            session_id: 会话标识
            code: 待执行的代码
            timeout_sec: 可选超时(秒,默认 None → 沿用 ContainerSpec.timeout_sec=30)

        Returns:
            执行结果字典,包含 status、output、error、execution_time_ms 键
                (保持 4.1a 既有契约,强类型化推迟到 Story 4.7)

        Raises:
            ExecutionError: 执行失败(STDERR 非空 / 退出码非 0)
            SandboxTimeoutError: 超过 timeout_sec(Story 4.4 EXCEPTION_316)
            SandboxResourceLimitExceededError: 内存/CPU/pids 超出 cgroups 限制(Story 4.4 EXCEPTION_317)
        """
        ...

    async def stop_container(self, session_id: str) -> None:
        """停止并清理沙箱容器。

        Args:
            session_id: 会话标识

        Raises:
            ContainerStopError: 容器停止失败
        """
        ...

    async def is_container_running(self, session_id: str) -> bool:
        """检查指定会话的容器是否正在运行。

        Args:
            session_id: 会话标识

        Returns:
            容器正在运行返回 True,否则返回 False
        """
        ...

    async def health_check(self) -> bool:
        """Docker daemon 健康检查(Story 4.4 新增方法)。

        用于熔断器 + 启动探针集成。

        Returns:
            daemon 可达返回 True,否则 False(**不抛异常**,由调用方决定熔断)
        """
        ...
