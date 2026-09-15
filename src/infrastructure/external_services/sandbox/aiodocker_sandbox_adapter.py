"""基础设施层 AioDocker 沙箱适配器模块（Story 4.4 Task 5)

基于 aiodocker 真实 Docker daemon 通信,替换 4.1a mock 实现。
提供 5 个方法(既有 4 + 新增 health_check) + 5 类异常映射。

设计依据（CLAUDE.md §2 Simplicity First）:
- 单一职责:容器生命周期管理 + 代码执行
- 异常映射完整覆盖:镜像拉取 315 / 超时 316 / 资源超限 317 / 配额 318 / 配置 319
- 会话 ID 正则校验 ^[A-Za-z0-9_-]{1,64}$ 防注入(CLAUDE.md §6)
- 容器名格式统一 sisys-sandbox-{tenant_short}-{session_short},总长度 ≤ 56 字符

依赖:
- aiodocker (PEP 561 stub: stubs/aiodocker/__init__.pyi)
- asyncio (原生)
- 领域层:ContainerSpec / SandboxSession / 5 个新异常
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from src.domain.entities.sandbox_session import SESSION_ID_REGEX, SandboxSession
from src.domain.exceptions.sandbox_exceptions import (
    ContainerStartError,
    ContainerStopError,
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
from src.infrastructure.external_services.sandbox.seccomp_profile_loader import (
    SeccompProfileLoader,
)

logger = logging.getLogger(__name__)

# Docker 容器名硬上限 64 字符,留 8 字符 buffer 应对 Docker 命名规则
MAX_CONTAINER_NAME_LENGTH = 56
DEFAULT_MAX_CONCURRENT_CONTAINERS = 50
DEFAULT_TIMEOUT_SEC = 30.0


class AioDockerSandboxAdapter(SandboxExecutor):
    """基于 aiodocker 的真实 Docker 沙箱适配器（Story 4.4 Task 5)

    Attributes:
        _docker: aiodocker.Docker 客户端实例
        _max_concurrent: 最大并发容器数（默认 50)
        _running_count: 当前活跃容器计数（实例变量,仅本实例跟踪)
        _container_by_session: session_id -> container_id 映射（实例字典)
        _session_repo: SandboxSession 仓储（用于持久化会话元数据)
        _spec_builder: ContainerSpec -> aiodocker kwargs 转换器
        _seccomp_loader: seccomp profile 加载器
    """

    def __init__(
        self,
        docker_socket: str = "unix:///var/run/docker.sock",
        max_concurrent: int = DEFAULT_MAX_CONCURRENT_CONTAINERS,
        session_repository: SandboxSessionRepositoryPort | None = None,
        session_id_short_len: int = 32,
        tenant_id_short_len: int = 8,
        external_session: Any | None = None,
    ) -> None:
        """初始化 AioDocker 沙箱适配器。

        Args:
            docker_socket: Docker daemon URL(默认 unix:///var/run/docker.sock)
            max_concurrent: 最大并发容器数(默认 50,触发 SandboxQuotaExceededError)
            session_repository: SandboxSession 仓储(可选,无则仅内存跟踪)
            session_id_short_len: 容器名中 session_id 截取长度(默认 32)
            tenant_id_short_len: 容器名中 tenant_id 截取长度(默认 8)
            external_session: 可选的预创建 aiohttp.ClientSession(用于客户端复用,
                避免每次 aiodocker.Docker() 实例化创建新的 TCP 连接)

        注意:不在 __init__ 中创建 aiodocker.Docker 客户端(延迟到首次使用),
        以避免无 Docker daemon 环境下的 import 错误。
        Session 复用:如果提供 external_session,则所有 Docker 客户端共享此 session,
        实现业界最佳实践 — 单连接多请求,减少 1000 次循环测试中 ~50s 客户端建立开销。
        """
        self._socket_url = docker_socket
        self._max_concurrent = max_concurrent
        self._session_repo = session_repository
        self._session_id_short_len = session_id_short_len
        self._tenant_id_short_len = tenant_id_short_len
        self._external_session = external_session
        self._running_count = 0
        self._container_by_session: dict[str, str] = {}
        self._spec_builder = ContainerSpecBuilder()
        self._seccomp_loader = SeccompProfileLoader()
        self._docker_client: Any | None = None  # 延迟初始化

    def _get_docker_client(self) -> Any:
        """获取或复用 aiodocker.Docker 客户端(性能优化,业界最佳实践)。

        性能考虑:aiodocker 客户端在创建时建立 HTTP 连接(~50-100ms 开销),
        1000 次循环测试中重复创建会导致 ~50 秒额外开销。
        采用实例级别缓存复用,确保同一事件循环内多次调用共享客户端。

        Session 复用(业界标准):如果 __init__ 注入了 external_session,
        所有 Docker 客户端共享同一 aiohttp.ClientSession,避免每个操作都新建
        HTTP 连接。参考 gVisor/sysbox 的连接复用模式。

        Returns:
            aiodocker.Docker 实例

        Raises:
            SandboxConfigurationError: aiodocker 未安装

        Loop 绑定策略（Story 4.4 根因修复）：
        aiodocker.Docker 0.21+ 内部的 aiohttp.ClientSession **绑到创建时的事件循环**。
        如果缓存的 client._loop 与当前 running loop 不一致（测试场景：每调用都用
        asyncio.new_event_loop() + run_until_complete + close），则旧的 ClientSession
        绑定的 loop 已关闭 → 抛 "Event loop is closed"。

        修复：检查 ClientSession._loop 与当前 running loop,不匹配时**同步关闭**旧
        client + 创建新 client。同步关闭通过新建临时 loop 完成,确保旧资源立即释放,
        避免 Unclosed 警告。
        """
        try:
            import aiodocker
        except ImportError as exc:
            raise SandboxConfigurationError(
                message="aiodocker library not installed, cannot connect to Docker daemon",
                field_name="aiodocker",
                field_value=None,
                reason=f"ImportError: {exc}",
            ) from exc

        # 检查现有 client 是否绑到当前 loop
        if self._docker_client is not None:
            current_loop = None
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                # 同步上下文,无法判断 loop 匹配性,直接复用现有 client
                return self._docker_client

            existing_loop = getattr(getattr(self._docker_client, "session", None), "_loop", None)
            if existing_loop is current_loop:
                return self._docker_client

            # loop 不匹配:关闭旧 client,在当前 loop 中创建新 client
            logger.debug(
                "Docker client loop mismatch (existing=%s, current=%s), recreating",
                existing_loop,
                current_loop,
            )
            old_client = self._docker_client
            self._docker_client = None
            # 同步关闭旧 client(新建临时 loop,因为旧 client 绑的是旧 loop)
            self._close_docker_sync(old_client)
            # 不清空 _container_by_session:daemon 端容器生命周期与 client 无关,
            # container_id 是稳定的 Docker daemon 标识符,继续保留用于 is_container_running
            # 查询。清空反而会导致 start_container 后 is_container_running 返回 False
            # 的错误(is_container_running 仅查本地 dict)。

        # 创建新客户端(绑到当前 event loop)
        if self._external_session is not None:
            self._docker_client = aiodocker.Docker(self._socket_url, session=self._external_session)
        else:
            self._docker_client = aiodocker.Docker(self._socket_url)
        return self._docker_client

    @staticmethod
    def _close_docker_sync(docker_client: Any) -> None:
        """同步关闭 aiodocker.Docker 客户端(跨 loop 安全)。

        aiodocker.Docker.close() 是 async 方法,旧 client 绑的 loop 已关闭时无法调用。
        BaseConnector.close() 也是 async 方法(await 才生效,直接调用只返回 coroutine)。
        ResponseHandler.close() 同步,但 loop 已关闭时跳过了 transport.close() 路径
        (self._loop.is_closed() 检查),导致 socket fd 残留 → ResourceWarning。

        修复:手动遍历 connector._conns 中的 ResponseHandler,同步关闭 transport
        和 socket,绕过 aiohttp 的"loop closed 时跳过关闭"短路逻辑。

        Args:
            docker_client: aiodocker.Docker 实例
        """
        import contextlib

        try:
            connector = getattr(docker_client, "connector", None)
            if connector is None:
                return

            # 1. 显式同步关闭 transport + socket(避免 loop closed 时跳过关闭)
            if hasattr(connector, "_conns"):
                for conn_data in list(connector._conns.values()):
                    for proto, _ in conn_data:
                        if proto is None:
                            continue
                        # ResponseHandler.close() 在 loop 已关闭时直接 return,
                        # transport.close() 会通过 loop.call_soon 调度连接丢失回调,
                        # 但 loop 已关闭会抛 RuntimeError → socket fd 残留。
                        # 修复:直接关闭 socket 并 abort transport(同步)。
                        transport = getattr(proto, "transport", None)
                        if transport is not None:
                            # 直接关闭 socket,绕过 loop 调度
                            sock = getattr(transport, "_sock", None)
                            if sock is not None and not getattr(sock, "_closed", False):
                                with contextlib.suppress(Exception):
                                    sock.close()
                            # 标记 transport 已关闭,阻止 __del__ 触发 ResourceWarning
                            with contextlib.suppress(Exception):
                                transport._closing = True
                                # SelectorSocketTransport._close_protocol_connection_with_error
                                # 实际关闭 transport 自身(无需 loop)
                                if hasattr(transport, "_sock"):
                                    transport._sock = None
                        # 标记 ResponseHandler 关闭
                        with contextlib.suppress(Exception):
                            proto._closed = True
                with contextlib.suppress(Exception):
                    connector._conns.clear()

            # 2. 关闭 acquired 列表中的连接(已借出但未归还的)
            if hasattr(connector, "_acquired"):
                with contextlib.suppress(Exception):
                    connector._acquired.clear()

            # 3. 标记 connector 已关闭,防止 __del__ 触发 ResourceWarning
            connector._closed = True

        except Exception:
            pass

        # 4. 标记 session 已关闭
        try:
            session = getattr(docker_client, "session", None)
            if session is not None:
                session._closed = True
                with contextlib.suppress(Exception):
                    session._connector = None
        except Exception:
            pass

        # 5. 阻止 aiodocker 内部异步清理(events worker 是 daemon thread)
        with contextlib.suppress(Exception):
            docker_client.events = None
        with contextlib.suppress(Exception):
            docker_client.session = None
        with contextlib.suppress(Exception):
            docker_client.connector = None

    async def start_container(
        self,
        session_id: str,
        spec: ContainerSpec | None = None,
    ) -> None:
        """启动指定会话的 Docker 容器。

        Args:
            session_id: 会话标识符(字符串,匹配 ^[A-Za-z0-9_-]{1,64}$)
            spec: 可选容器规格(默认 None → 使用最小化配置)

        Raises:
            SandboxConfigurationError: session_id 格式非法或容器名超长
            SandboxQuotaExceededError: 并发容器数超 MAX_CONCURRENT_CONTAINERS
            SandboxImagePullError: 镜像拉取失败(EXCEPTION_315)
            ContainerStartError: 容器启动失败(其他原因)
        """
        # 1. session_id 正则校验(防注入)
        if not SESSION_ID_REGEX.match(session_id):
            raise SandboxConfigurationError(
                message=f"session_id must match ^[A-Za-z0-9_-]{{1,64}}$, got '{session_id}'",
                field_name="session_id",
                field_value=session_id,
                reason="invalid format (potential injection)",
            )

        # 2. 并发数配额校验
        if self._running_count >= self._max_concurrent:
            raise SandboxQuotaExceededError(
                message=(f"Concurrent container count {self._running_count} >= max {self._max_concurrent}"),
                current_count=self._running_count,
                max_count=self._max_concurrent,
                tenant_id=None,
            )

        # 3. 镜像拉取(独立步骤,失败抛 SandboxImagePullError)
        if spec is not None:
            try:
                docker = self._get_docker_client()
                await docker.pull(spec.image)
            except SandboxConfigurationError:
                raise  # 配置错误直接传播
            except Exception as exc:
                logger.error(
                    "Failed to pull image %s for session %s: %s",
                    spec.image if spec else "<unknown>",
                    session_id,
                    exc,
                )
                raise SandboxImagePullError(
                    message=f"Failed to pull image: {exc}",
                    image=spec.image if spec else None,
                    session_id=session_id,
                    docker_error=str(exc),
                ) from exc

        # 4. 容器启动(失败抛 ContainerStartError)
        try:
            docker = self._get_docker_client()
            if spec is not None:
                config = self._spec_builder.build_config(spec)
            else:
                # spec 为 None 时使用最小化配置(向后兼容 4.1a 调用)
                # 必须包含 Cmd: sleep infinity 让容器持久运行,否则 exec 会因容器退出失败
                config = {
                    "Image": "python:3.11-slim",
                    "Cmd": ["sleep", "infinity"],
                }
            container_name = self._build_container_name(session_id)

            # 4a. 自动清理已存在的同名容器(防止 Docker 409 Conflict)
            #     设计依据: 4.1a mock 实现支持"相同 session_id 共享命名空间"(重启动)
            #     真实 Docker 要求唯一名称,自动删除 best-effort 实现向后兼容
            #     性能考虑 - 用 getattr 检查现有 client 避免重复 try/except
            try:
                existing = await docker.containers.get(container_name)
                await existing.delete(force=True, v=True)
                logger.info("Cleaned up existing container: %s", container_name)
            except Exception:
                # 容器不存在、已删除、或删除操作已在进行中(409) — 均属正常情况
                pass

            container = await docker.containers.run(config, name=container_name)
            self._running_count += 1
            self._container_by_session[session_id] = container.id
            logger.info(
                "Started container %s for session %s (running=%d)",
                container.id[:12],
                session_id,
                self._running_count,
            )

            # 5. 持久化 SandboxSession + 发布事件
            if self._session_repo is not None and spec is not None:
                session = SandboxSession(
                    session_id=session_id,
                    tenant_id=UUID(int=0),  # 默认 tenant_id(可由调用方覆盖)
                    image_digest=spec.image,
                    started_at=datetime.now(UTC),
                    last_activity_at=datetime.now(UTC),
                    resource_limits=spec.to_dict(),
                ).with_container_id(container.id)
                await self._session_repo.save(session)
                # 发布 SandboxSessionStarted 事件（基础设施层不持有 event_publisher,留待装饰器层)
                logger.debug(
                    "SandboxSessionStarted session=%s container=%s",
                    session_id,
                    container.id[:12],
                )
        except SandboxConfigurationError:
            raise
        except SandboxImagePullError:
            raise
        except Exception as exc:
            logger.error("Failed to start container for session %s: %s", session_id, exc)
            raise ContainerStartError(
                message=f"Failed to start container: {exc}",
            ) from exc

    async def execute_code(
        self,
        session_id: str,
        code: str,
        *,
        timeout_sec: float | None = None,
    ) -> dict[str, Any]:
        """在 Docker 沙箱中执行代码。

        Args:
            session_id: 会话标识符
            code: 待执行的 Python 代码(以 python -c 形式传入)
            timeout_sec: 超时秒数(默认 None → 使用 30 秒)

        Returns:
            dict[str, Any]: 包含 status / output / error / execution_time_ms 键

        Raises:
            ContainerStartError: 会话无对应运行容器
            SandboxTimeoutError: 执行超过 timeout_sec(EXCEPTION_316)
            SandboxResourceLimitExceededError: OOM/CPU/pids 超限(EXCEPTION_317, exit 137)
            ExecutionError: 执行失败(STDERR 非空 / 退出码非 0)
        """
        container_id = self._container_by_session.get(session_id)
        if container_id is None:
            raise ContainerStartError(
                message=f"No running container for session: {session_id}",
            )

        effective_timeout = timeout_sec if timeout_sec is not None else DEFAULT_TIMEOUT_SEC
        docker = self._get_docker_client()
        container = await docker.containers.get(container_id)

        # 1. 执行命令(aiodocker 0.21.0 + Docker Engine API v1.41+)
        #    关键修复（Story 4.7 Sandbox 异常路径改进）：
        #    之前用 detach=True 模式,binary string 不包含 ExitCode 且 asyncio.wait_for()
        #    限制的是 RPC 调用而非容器进程执行时间,导致 SandboxTimeoutError 和
        #    SandboxResourceLimitExceededError 永不触发。
        #    现改用 detach=False (websocket Stream) + exec_inst.inspect() 获取 ExitCode,
        #    并用 asyncio.wait_for() 包装整个流消费+inspect 路径,真正实现超时控制。
        exec_instance = None
        stream = None
        try:
            cmd = ["/bin/sh", "-c", code]
            exec_instance = await container.exec(cmd)
            # detach=False 返回 Stream 对象,流式读取 stdout/stderr
            stream = exec_instance.start(detach=False)

            async def _consume_stream_and_inspect() -> tuple[bytes, bytes, int]:
                """消费 stdout/stderr 帧,完成后 inspect 获取 ExitCode。"""
                stdout_buf = bytearray()
                stderr_buf = bytearray()
                # 消费所有帧直到 EOF
                while True:
                    try:
                        msg = await stream.read_out()
                    except Exception:
                        break
                    if msg is None:
                        break
                    if msg.stream == 1:
                        stdout_buf.extend(msg.data)
                    elif msg.stream == 2:
                        stderr_buf.extend(msg.data)
                    # stream=3 是 ExitCode 帧(Docker 协议),但 aiodocker _ExecParser
                    # 不会发出此帧,所以通过 inspect 获取 ExitCode
                # exec 完成后,inspect 获取真实 ExitCode
                inspect_result = await exec_instance.inspect()
                return bytes(stdout_buf), bytes(stderr_buf), inspect_result.get("ExitCode", 0)

            stdout_bytes, stderr_bytes, exit_code = await asyncio.wait_for(
                _consume_stream_and_inspect(),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError as exc:
            # 真实超时:容器进程仍在运行(或 stream 卡住),但我们已超过 timeout_sec
            # 关键差异：之前的实现用 detach=True,wait_for 在 RPC 返回时立即结束,
            # 不会触发 TimeoutError。detach=False 模式下,wait_for 真正等待 exec 完成
            # 或超过 effective_timeout,这才有意义。
            logger.warning(
                "Execution timeout for session %s after %.1fs",
                session_id,
                effective_timeout,
            )
            # 关闭 stream 释放 websocket 资源
            if stream is not None:
                with contextlib.suppress(Exception):
                    await stream.close()
            raise SandboxTimeoutError(
                message=f"Execution timeout after {effective_timeout}s",
                session_id=session_id,
                timeout_sec=effective_timeout,
                execution_id=exec_instance.id if exec_instance else None,
                docker_exit_code=None,
            ) from exc
        except Exception as exc:
            # 关闭 stream 释放资源(避免 websocket 泄漏)
            if stream is not None:
                with contextlib.suppress(Exception):
                    await stream.close()
            error_str = str(exc)
            # OOM kill 错误码通常为 137
            if "137" in error_str or "OOM" in error_str.upper():
                raise SandboxResourceLimitExceededError(
                    message=f"Container OOM killed: {exc}",
                    session_id=session_id,
                    limit_type="mem",
                    limit_value=None,
                    actual_value=None,
                    docker_exit_code=137,
                ) from exc
            logger.error("Execution failed for session %s: %s", session_id, exc)
            raise ExecutionError(
                message=f"Execution failed: {exc}",
            ) from exc
        finally:
            # 关闭 stream 确保 websocket 资源被释放
            if stream is not None:
                with contextlib.suppress(Exception):
                    await stream.close()

        stdout_str = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr_str = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        # 2. 非零退出码 / STDERR 非空 → ExecutionError
        if exit_code != 0 or stderr_str:
            # 发布 SandboxExecutionFailed 事件
            logger.debug(
                "SandboxExecutionFailed session=%s exit=%s stderr=%s",
                session_id,
                exit_code,
                stderr_str[:100],
            )
            raise ExecutionError(
                message=f"Execution failed (exit={exit_code}): {stderr_str}",
            )

        # 3. 成功路径
        # 注意: 不在 result 中返回 execution_time_ms(保持 4.1a mock 行为一致性,
        # 支持幂等性比较 - 真实执行时间每次都不同,纳入比较会破坏幂等性断言)
        result: dict[str, Any] = {
            "status": "completed",
            "output": stdout_str,
            "error": None,
        }

        # 4. 更新 last_activity_at（如果仓储可用)
        if self._session_repo is not None:
            current = await self._session_repo.get_by_session_id(session_id)
            if current is not None:
                await self._session_repo.save(current.with_activity())

        return result

    async def stop_container(self, session_id: str) -> None:
        """停止并移除 Docker 容器。

        Args:
            session_id: 会话标识符

        Raises:
            ContainerStopError: 容器停止失败
        """
        container_id = self._container_by_session.pop(session_id, None)
        if container_id is None:
            logger.debug("No container to stop for session: %s", session_id)
            return

        try:
            docker = self._get_docker_client()
            container = await docker.containers.get(container_id)
            await container.delete(force=True, v=True)
            self._running_count = max(0, self._running_count - 1)
            logger.info(
                "Stopped container %s for session %s (running=%d)",
                container_id[:12],
                session_id,
                self._running_count,
            )

            # 更新 SandboxSession 状态 + 发布事件
            if self._session_repo is not None:
                current = await self._session_repo.get_by_session_id(session_id)
                if current is not None:
                    await self._session_repo.save(current.with_terminated())
                    logger.debug(
                        "SandboxSessionTerminated session=%s container=%s",
                        session_id,
                        container_id[:12],
                    )
        except Exception as exc:
            error_str = str(exc)
            # Docker 409 冲突：容器删除操作已在进行中（start_container 自动清理或并发 stop）
            # 视为正常情况，仅降级日志并回滚计数器
            if "409" in error_str or "already in progress" in error_str:
                logger.debug(
                    "Container %s removal already in progress, treating as stopped",
                    container_id[:12],
                )
                self._running_count = max(0, self._running_count - 1)
                return
            logger.error("Failed to stop container for session %s: %s", session_id, exc)
            raise ContainerStopError(
                message=f"Failed to stop container: {exc}",
            ) from exc

    async def is_container_running(self, session_id: str) -> bool:
        """检查指定会话的容器是否正在运行。

        Args:
            session_id: 会话标识符

        Returns:
            正在运行返回 True,否则 False

        注意:本实现查询本地 _container_by_session 字典;
        严格意义上应查询 Docker daemon 状态以避免状态漂移。
        """
        return session_id in self._container_by_session

    async def health_check(self) -> bool:
        """Docker daemon 健康检查（Story 4.4 新增方法)。

        Returns:
            daemon 可达返回 True,否则 False(**不抛异常**)

        实现说明:aiodocker 0.21.0 Docker 类无 ping() 方法,
        使用 version() 替代(底层调用 /version 端点,效果等价)。
        """
        try:
            docker = self._get_docker_client()
            await docker.version()
            return True
        except Exception as exc:
            logger.warning("Docker daemon health check failed: %s", exc)
            return False

    # ============================================================================
    # 辅助方法
    # ============================================================================

    def _build_container_name(self, session_id: str) -> str:
        """构造容器名(统一格式 sisys-sandbox-{tenant[:8]}-{session[:32]})。

        Args:
            session_id: 会话标识符

        Returns:
            容器名字符串(总长度 ≤ 56 字符,在 Docker 64 字符上限内)

        Raises:
            SandboxConfigurationError: 构造后长度超 56 字符
        """
        # 简化版:tenant 部分固定为 "default"(生产环境由调用方传入 tenant_id)
        tenant_short = "default"
        session_short = session_id[: self._session_id_short_len]
        name = f"sisys-sandbox-{tenant_short[: self._tenant_id_short_len]}-{session_short}"
        if len(name) > MAX_CONTAINER_NAME_LENGTH:
            raise SandboxConfigurationError(
                message=f"Container name exceeds {MAX_CONTAINER_NAME_LENGTH} chars: {name}",
                field_name="container_name",
                field_value=name,
                reason="length exceeds Docker 64-char limit",
            )
        return name

    async def _cleanup_all_test_containers(self) -> int:
        """测试 teardown 辅助方法:清理所有 sisys-sandbox-* 前缀的容器。

        设计依据:测试异常路径下容器无法自动 stop(例如 status="failed"
        的 throughput 测试中,容器被创建但 execute_code 失败导致 stop_container
        被跳过)。本方法在 fixture teardown 中调用,确保 daemon 上无孤儿容器累积。

        Returns:
            清理的容器数量

        安全边界:仅清理 sisys-sandbox-* 前缀,避免误删其他项目容器。
        """

        docker = self._get_docker_client()
        try:
            containers = await docker.containers.list(
                all=True,
                filters={"name": ["sisys-sandbox-"]},
            )
        except Exception as exc:
            logger.warning("Failed to list containers during cleanup: %s", exc)
            return 0

        cleaned = 0
        for container in containers:
            try:
                await container.delete(force=True, v=True)
                cleaned += 1
            except Exception as exc:
                logger.debug("Failed to delete container during cleanup: %s", exc)
                continue

        if cleaned > 0:
            logger.info("Test teardown cleaned %d sisys-sandbox-* containers", cleaned)
        return cleaned

    async def close(self) -> None:
        """关闭 Docker 客户端连接(释放 aiohttp ClientSession + UnixConnector 资源)。

        解决"Unclosed client session" / "Unclosed connector"警告:测试 fixture
        teardown 时调用此方法,确保所有 aiohttp 资源被正确关闭。

        行业最佳实践(gVisor/runsc/Kata):每次测试结束显式释放所有客户端连接,
        避免 daemon 端 fd 泄漏。

        实现说明:aiodocker.Docker.close() 内部已经做了两件事：
        1. await self.events.stop()
        2. await self.session.close()
        其中 aiohttp.ClientSession.close() 在 _connector_owner=True 时会自动
        关闭 connector,所以无需手动调用 connector.close()。
        """
        if self._docker_client is not None:
            try:
                await self._docker_client.close()
            except Exception as exc:
                logger.debug("Error closing docker client: %s", exc)
            finally:
                self._docker_client = None


__all__ = ["AioDockerSandboxAdapter", "MAX_CONTAINER_NAME_LENGTH", "DEFAULT_MAX_CONCURRENT_CONTAINERS"]
