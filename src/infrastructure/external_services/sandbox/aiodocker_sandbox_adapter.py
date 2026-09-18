"""基础设施层 AioDocker 沙箱适配器

Story 4.4 — 替换 mock 实现,基于 aiodocker 真实 Docker daemon 通信。
安全配置:network_mode=none + read_only + cap_drop ALL + no-new-privileges + 强化 seccomp。

架构约束:
- 依赖 aiodocker (基础设施层允许第三方库)
- 不修改既有 SandboxExecutor Protocol 签名(默认参数兼容)
- session_id 注入防御:正则 ^[A-Za-z0-9_-]{1,64}$
- 容器名统一: sisys-sandbox-{tenant[:8]}-{session[:32]}, 总长度 ≤ 55 字符
- 5 类异常映射: 镜像拉取(315) / 超时(316) / 资源超限(317) / 配额(318) / 配置(319)
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from typing import Any

from src.domain.entities.sandbox_session import SandboxSession
from src.domain.exceptions import (
    ContainerStartError,
    ContainerStopError,
    EntityValidationError,
    ExecutionError,
    SandboxConfigurationError,
    SandboxImagePullError,
    SandboxQuotaExceededError,
    SandboxResourceLimitExceededError,
    SandboxTimeoutError,
)
from src.domain.ports.sandbox_executor import SandboxExecutor
from src.domain.ports.sandbox_session_repository import SandboxSessionRepositoryPort
from src.domain.value_objects.container_spec import ContainerSpec
from src.infrastructure.external_services.sandbox.container_spec_builder import (
    ContainerSpecBuilder,
)

logger = logging.getLogger(__name__)

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class AioDockerSandboxAdapter(SandboxExecutor):
    """基于 aiodocker 的沙箱执行适配器

    每个会话获得独立 Docker 容器,应用以下安全配置:
    - network_mode: "none" (网络隔离)
    - read_only: True (只读根文件系统)
    - cap_drop: ["ALL"] (移除所有 Linux capabilities)
    - security_opt: ["no-new-privileges"] (禁止提权)
    - tmpfs: {"/tmp": "100m"} (临时写入)
    - 资源限制: CPU + 内存 + pids (cgroups)

    Attributes:
        _docker: aiodocker.Docker 客户端(单例)
        _session_repo: SandboxSession 仓储端口
        _max_concurrent: 最大并发容器数
        _running_count: 当前运行容器数(类变量级跟踪)
    """

    # 类变量级并发计数(避免实例间不一致)
    _running_count: int = 0
    # 模块级共享 aiohttp.UnixConnector(所有 adapter 实例 + 所有 event loop 共享,避免 Unclosed connector 警告)
    _module_shared_connector: Any = None

    def __init__(
        self,
        docker_socket: str = "unix:///var/run/docker.sock",
        max_concurrent: int = 50,
        session_repo: SandboxSessionRepositoryPort | None = None,
    ) -> None:
        """初始化适配器

        Args:
            docker_socket: Docker daemon socket 地址
            max_concurrent: 最大并发容器数(默认 50)
            session_repo: SandboxSession 仓储端口(可选,用于持久化会话)
        """
        self._docker_socket = docker_socket
        self._max_concurrent = max_concurrent
        self._session_repo = session_repo
        self._docker: Any = None  # 延迟初始化 aiodocker.Docker
        # 实例级 asyncio.Lock(避免跨 event loop 冲突)
        self._lock: asyncio.Lock | None = None
        # 当前 event loop 引用(用于检测 client 是否需要重建)
        self._loop: Any = None
        # 保存所有创建过的 connectors(在 __del__ 时统一关闭,避免 Unclosed 警告)
        self._connectors: list[Any] = []

    def __del__(self) -> None:
        """析构时同步关闭所有 connectors(避免 Unclosed connector 警告).

        这种方法有效是因为:
        - UnixConnector.close() 是**同步**方法(底层只是 close OS 文件描述符)
        - Python 解释器退出时,所有 adapter 实例被 GC,触发 __del__
        - __del__ 中同步关闭所有 connector,释放 OS fd
        - 此时即使旧 event loop 已关闭,close() 仍能安全执行(只是 OS fd 操作)
        """
        for connector in self._connectors:
            try:
                if connector is not None and not connector.closed:
                    connector.close()
            except Exception:
                pass
        self._connectors.clear()

    async def _ensure_docker(self) -> Any:
        """延迟初始化 aiodocker.Docker 客户端,自动检测 event loop 变更.

        真正根本修复(无告警抑制):
        1) 旧 client 引用置空(由 __del__ 统一关闭其 connector)
        2) 旧 client 持有的 connector 保存到 self._connectors(由 __del__ 关闭)
        3) 新 client 创建,新 connector 也保存到 _connectors
        4) 进程退出时 __del__ 同步关闭所有 connector(UnixConnector.close() 同步)
        """
        import aiodocker  # 基础设施层允许导入第三方库

        current_loop = asyncio.get_running_loop()
        if self._docker is None or self._loop is not current_loop:
            # 1) 断开旧 client 引用(__del__ 会关闭其 connector)
            if self._docker is not None:
                old_docker = self._docker
                # 保存旧 connector(由 __del__ 统一关闭)
                old_session = getattr(old_docker, "session", None)
                if old_session is not None:
                    old_connector = getattr(old_session, "_connector", None)
                    if old_connector is not None and old_connector not in self._connectors:
                        self._connectors.append(old_connector)
                self._docker = None
                del old_docker
            # 2) 创建新 client(每次新建避免跨 loop 问题)
            self._docker = aiodocker.Docker(url=self._docker_socket)
            # 3) 保存新 connector 到清理列表(由 __del__ 统一关闭)
            new_session = getattr(self._docker, "session", None)
            if new_session is not None:
                new_connector = getattr(new_session, "_connector", None)
                if new_connector is not None and new_connector not in self._connectors:
                    self._connectors.append(new_connector)
            self._loop = current_loop
        return self._docker

    async def aclose(self) -> None:
        """显式关闭 docker 客户端(由 caller 负责在正确的 loop 内调用)."""
        if self._docker is not None:
            try:
                # 仅关闭 session(不直接 docker.close(),后者会一并关闭 connector)
                old_session = getattr(self._docker, "session", None)
                if old_session is not None and not old_session.closed:
                    await old_session.close()
            except Exception:
                pass
            try:
                # 同步关闭 connector(UnixConnector.close() 是 sync 方法)
                old_session = getattr(self._docker, "session", None) if self._docker else None
                if old_session is not None:
                    old_connector = getattr(old_session, "_connector", None)
                    if old_connector is not None and not old_connector.closed:
                        old_connector.close()
            except Exception:
                pass
            self._docker = None
            self._loop = None

    def _ensure_lock(self) -> asyncio.Lock:
        """延迟初始化 asyncio.Lock(每次调用都关联当前 event loop)"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @staticmethod
    def _validate_session_id(session_id: str) -> None:
        """session_id 注入防御(正则校验)

        Raises:
            SandboxConfigurationError: session_id 不匹配 ^[A-Za-z0-9_-]{1,64}$
        """
        if not SESSION_ID_PATTERN.match(session_id):
            raise SandboxConfigurationError(
                f"session_id must match {SESSION_ID_PATTERN.pattern}",
                field_name="session_id",
                field_value=session_id,
                reason_detail="regex mismatch",
            )

    async def start_container(
        self,
        session_id: str,
        spec: ContainerSpec | None = None,
    ) -> None:
        """启动指定会话的 Docker 容器

        Args:
            session_id: 会话 ID(匹配 ^[A-Za-z0-9_-]{1,64}$)
            spec: 容器规格(默认 None → 使用安全默认 ContainerSpec)

        Raises:
            SandboxConfigurationError: session_id 非法
            SandboxQuotaExceededError: 并发容器数超配额
            SandboxImagePullError: 镜像拉取失败
            ContainerStartError: 容器启动失败(其他原因)
        """
        # 校验 session_id
        self._validate_session_id(session_id)

        # 校验并发配额
        async with self._ensure_lock():
            if AioDockerSandboxAdapter._running_count >= self._max_concurrent:
                raise SandboxQuotaExceededError(
                    "concurrent container limit reached",
                    current_count=AioDockerSandboxAdapter._running_count,
                    max_count=self._max_concurrent,
                    tenant_id=None,
                )
            AioDockerSandboxAdapter._running_count += 1

        spec = spec or ContainerSpec(
            image="python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534"
        )

        try:
            docker = await self._ensure_docker()
            tenant_id = uuid.uuid4()  # 生产应从 context 注入
            container_name = ContainerSpecBuilder.build_container_name(tenant_id, session_id)

            # 镜像拉取(分离 name:tag 与 digest 避免 aiodocker 解析错误)
            try:
                # Docker daemon 通常有本地缓存 image,run() 会自动复用
                # 这里只在 image 不在本地时才显式 pull
                image_ref = spec.image
                if "@sha256:" in image_ref:
                    # 拆为 name:tag + digest,让 aiodocker 正确处理
                    name_tag, digest = image_ref.rsplit("@", 1)
                    # 检查本地是否已有此 image(避免重复 pull)
                    local_images = await docker.images.list()
                    local_digests = {img.get("Id", "") for img in local_images}
                    if digest not in local_digests:
                        await docker.images.pull(name_tag)
                else:
                    await docker.images.pull(image_ref)
            except Exception as pull_exc:
                raise SandboxImagePullError(
                    f"failed to pull image {spec.image}",
                    image=spec.image,
                    session_id=session_id,
                    docker_error=str(pull_exc),
                ) from pull_exc

            # 容器启动
            host_config = ContainerSpecBuilder.build_host_config(spec)
            config = {
                "Image": spec.image,
                "Cmd": ["sleep", "infinity"],
                "Env": [f"SESSION_ID={session_id}"],
                "HostConfig": host_config,
            }
            try:
                container = await docker.containers.run(
                    config=config,
                    name=container_name,
                )
                # aiodocker DockerContainer 提供 .id 属性
                container_id = container.id
            except Exception as run_exc:
                raise ContainerStartError(f"failed to run container {container_name}: {run_exc}") from run_exc

            # 持久化会话
            if self._session_repo is not None:
                session = SandboxSession(
                    session_id=session_id,
                    tenant_id=tenant_id,
                    container_id=container_id,
                    image_digest=spec.image,
                    resource_limits={
                        "mem_limit_mb": spec.mem_limit_mb,
                        "cpu_quota": spec.cpu_quota,
                        "pids_limit": spec.pids_limit,
                    },
                )
                await self._session_repo.save(session)

            # 发布事件(此处简化:实际应用层应有 event_publisher)
            logger.info(
                "Started container for session %s: %s",
                session_id,
                container_name,
            )
        except (SandboxImagePullError, ContainerStartError, EntityValidationError):
            # 失败时回滚计数
            async with self._ensure_lock():
                AioDockerSandboxAdapter._running_count -= 1
            raise
        except Exception:
            async with self._ensure_lock():
                AioDockerSandboxAdapter._running_count -= 1
            raise

    async def execute_code(
        self,
        session_id: str,
        code: str,
        *,
        timeout_sec: float | None = None,
    ) -> dict[str, Any]:
        """在 Docker 沙箱中执行代码

        Args:
            session_id: 会话 ID
            code: 待执行的 Python 代码
            timeout_sec: 超时秒数(默认 None → 使用 spec.timeout_sec)

        Returns:
            执行结果字典 {status, output, error, execution_time_ms}

        Raises:
            SandboxTimeoutError: 执行超时
            SandboxResourceLimitExceededError: 资源超限(OOM exit 137)
            ExecutionError: 其他执行失败
        """
        self._validate_session_id(session_id)
        effective_timeout = timeout_sec if timeout_sec is not None else 30.0

        docker = await self._ensure_docker()

        # 获取容器 ID
        container_id: str | None = None
        if self._session_repo is not None:
            session = await self._session_repo.get_by_session_id(session_id)
            container_id = session.container_id if session else None
        if not container_id:
            raise ExecutionError(f"No running container for session: {session_id}")

        try:
            container = await docker.containers.get(container_id)

            async def _run_code() -> dict[str, Any]:
                exec_instance = await container.exec(
                    cmd=["python", "-c", code],
                    stdout=True,
                    stderr=True,
                )
                output_data: bytes | None = None
                stream_exc: Exception | None = None
                try:
                    async with exec_instance.start(detach=False) as stream:
                        output_bytes = await stream.read_out()
                        # aiodocker 0.21 中 output_bytes.data 可能为 None(OOM kill)
                        if output_bytes is not None:
                            output_data = getattr(output_bytes, "data", None)
                except Exception as exc:
                    stream_exc = exc
                # OOM 检测:aiodocker 0.21 inspect 现在能正确返回 ExitCode=137
                try:
                    inspect_data = await exec_instance.inspect()
                    exit_code = inspect_data.get("ExitCode", 0)
                except Exception:
                    exit_code = 0
                # 综合判定 OOM:ExitCode=137 或 stream 异常
                if exit_code == 137 or (exit_code != 0 and output_data is None):
                    raise SandboxResourceLimitExceededError(
                        f"container OOM killed (exit_code={exit_code}, stream_exc={stream_exc})",
                        session_id=session_id,
                        limit_type="mem",
                        docker_exit_code=exit_code or 137,
                    )
                output_str = output_data.decode("utf-8") if output_data else ""
                return {
                    "status": "completed",
                    "output": output_str,
                    "error": None,
                    "execution_time_ms": 0,
                }

            result = await asyncio.wait_for(_run_code(), timeout=effective_timeout)
            return result  # type: ignore[return-value]
        except asyncio.TimeoutError as timeout_exc:
            raise SandboxTimeoutError(
                f"execution timeout after {effective_timeout}s",
                session_id=session_id,
                timeout_sec=effective_timeout,
            ) from timeout_exc
        except Exception as exc:
            error_msg = str(exc)
            # OOM kill exit 137 → SandboxResourceLimitExceededError
            if "137" in error_msg or "out of memory" in error_msg.lower():
                raise SandboxResourceLimitExceededError(
                    f"container OOM: {error_msg}",
                    session_id=session_id,
                    limit_type="mem",
                    docker_exit_code=137,
                ) from exc
            raise ExecutionError(f"Execution failed: {error_msg}") from exc
        finally:
            # 更新 last_activity_at
            if self._session_repo is not None:
                session = await self._session_repo.get_by_session_id(session_id)
                if session is not None:
                    await self._session_repo.save(session.with_activity_updated())

    async def stop_container(self, session_id: str) -> None:
        """停止并移除 Docker 容器

        Args:
            session_id: 会话 ID

        Raises:
            ContainerStopError: 容器停止失败
        """
        self._validate_session_id(session_id)
        docker = await self._ensure_docker()

        container_id: str | None = None
        if self._session_repo is not None:
            session = await self._session_repo.get_by_session_id(session_id)
            container_id = session.container_id if session else None
        if not container_id:
            logger.debug("No container to stop for session: %s", session_id)
            return

        try:
            container = await docker.containers.get(container_id)
            await container.delete(force=True)
        except Exception as exc:
            raise ContainerStopError(f"failed to stop container {container_id}: {exc}") from exc
        finally:
            # 更新会话状态 + 计数回滚
            if self._session_repo is not None:
                session = await self._session_repo.get_by_session_id(session_id)
                if session is not None:
                    await self._session_repo.save(session.with_terminated())
            async with self._ensure_lock():
                AioDockerSandboxAdapter._running_count = max(0, AioDockerSandboxAdapter._running_count - 1)

    async def is_container_running(self, session_id: str) -> bool:
        """检查指定会话的容器是否正在运行(查询 Docker daemon,非本地字典)"""
        self._validate_session_id(session_id)
        try:
            docker = await self._ensure_docker()
            container_id: str | None = None
            if self._session_repo is not None:
                session = await self._session_repo.get_by_session_id(session_id)
                container_id = session.container_id if session else None
            if not container_id:
                return False
            container = await docker.containers.get(container_id)
            container_info = await container.show()
            state = container_info.get("State", {})
            running: bool = state.get("Running", False)
            return running
        except Exception:
            return False

    async def health_check(self) -> bool:
        """Docker daemon 健康检查(不抛异常,返回 bool 用于熔断器)"""
        try:
            docker = await self._ensure_docker()
            await docker.version()
            return True
        except Exception:
            return False


__all__ = ["AioDockerSandboxAdapter", "SESSION_ID_PATTERN"]
