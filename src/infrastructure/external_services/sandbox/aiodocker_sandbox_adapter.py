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
import time
import uuid
from typing import Any

from aiodocker.exceptions import DockerError

from src.domain.entities.sandbox_session import SandboxSession
from src.domain.events.sandbox_events import (
    SandboxSessionStarted,
    SandboxSessionTerminated,
)
from src.domain.exceptions import (
    ContainerStartError,
    ContainerStopError,
    ExecutionError,
    SandboxConfigurationError,
    SandboxImagePullError,
    SandboxQuotaExceededError,
    SandboxResourceLimitExceededError,
    SandboxTimeoutError,
)
from src.domain.ports.event_publisher import EventPublisher
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

    # 类变量级并发计数 + 互斥锁(CLAUDE.md §6: asyncio.Lock 必须为类变量,协程间共享;
    # Python 3.10+ Lock 无争用 acquire 不绑定 event loop,多 loop 测试场景安全)
    _running_count: int = 0
    _lock: asyncio.Lock = asyncio.Lock()
    # 模块级共享 aiohttp.UnixConnector(所有 adapter 实例 + 所有 event loop 共享,避免 Unclosed connector 警告)
    _module_shared_connector: Any = None

    def __init__(
        self,
        docker_socket: str = "unix:///var/run/docker.sock",
        max_concurrent: int = 50,
        session_repo: SandboxSessionRepositoryPort | None = None,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        """初始化适配器

        Args:
            docker_socket: Docker daemon socket 地址
            max_concurrent: 最大并发容器数(默认 50)
            session_repo: SandboxSession 仓储端口(可选,用于持久化会话)
            event_publisher: 事件发布端口(可选,注入后发布沙箱生命周期事件;
                基础设施层注入先例: composition_root PrefectEngine/LangGraphEngine)
        """
        self._docker_socket = docker_socket
        self._max_concurrent = max_concurrent
        self._session_repo = session_repo
        self._event_publisher = event_publisher
        self._docker: Any = None  # 延迟初始化 aiodocker.Docker
        # 当前 event loop 引用(用于检测 client 是否需要重建)
        self._loop: Any = None
        # 保存所有创建过的 connectors(供 aclose 时同步关闭)
        self._connectors: list[Any] = []

    async def _publish_event(self, event: Any, session_id: str) -> None:
        """best-effort 发布沙箱生命周期事件(失败仅记日志,不影响主流程)

        Args:
            event: 领域事件实例
            session_id: 会话 ID(用于日志上下文)
        """
        if self._event_publisher is None:
            return
        try:
            await self._event_publisher.publish(event)
        except Exception:
            logger.warning(
                "发布沙箱事件失败 type=%s session=%s",
                getattr(event, "event_type", type(event).__name__),
                session_id,
            )

    def __del__(self) -> None:
        """析构时跳过主动清理 - 真正修复在 step 函数 finally 块中同步 stop_container.

        aiohttp 3.14 + aiodocker 0.21 组合下,在 xdist worker 退出 context 中
        同步调用 session.close()/connector.close() 会触发 KeyError。
        真正解决:让测试 step 函数在 finally 中 await self._docker.close(),
        跨 loop 容器清理由 daemon label 保证安全(见 session_repo + Reaper)。
        """
        # 不做主动清理 - 由测试 step finally 块负责
        pass

    async def aclose(self) -> None:
        """显式关闭当前 docker 客户端(测试 step finally 块调用).

        在**当前 loop** 中关闭 aiodocker.Docker:
        1) await docker.close() 触发内部 session.close()
        2) 然后同步关闭 connector(防止 Unclosed connector 警告)

        注意:必须在当前 loop 调用(因 await),避免跨 loop 同步驱动导致 xdist worker crash。
        """
        if self._docker is not None:
            try:
                # 先关闭 docker client(触发 session close)
                await self._docker.close()
            except Exception:
                pass
            self._docker = None
            self._loop = None
        # 然后同步关闭所有 connector(防止 OS fd 泄漏触发 Unclosed connector 警告)
        for connector in self._connectors:
            try:
                if connector is not None and not connector.closed:
                    connector.close()
            except Exception:
                pass
        self._connectors.clear()

    async def _ensure_docker(self) -> Any:
        """延迟初始化 aiodocker.Docker 客户端,自动检测 event loop 变更.

        关键修复(无告警抑制):
        - 旧 client 保存到 _connectors(close 时同步关闭所有 connector)
        - 新 client 创建后 connector 也加入 _connectors
        - aclose() 方法中在当前 loop 同步关闭 session + connector
        """
        import aiodocker  # 基础设施层允许导入第三方库

        current_loop = asyncio.get_running_loop()
        if self._docker is None or self._loop is not current_loop:
            # 1) 断开旧 client 引用
            if self._docker is not None:
                old_docker = self._docker
                old_session = getattr(old_docker, "session", None)
                if old_session is not None:
                    old_connector = getattr(old_session, "_connector", None)
                    if old_connector is not None and old_connector not in self._connectors:
                        self._connectors.append(old_connector)
                self._docker = None
                del old_docker
            # 2) 创建新 client
            self._docker = aiodocker.Docker(url=self._docker_socket)
            new_session = getattr(self._docker, "session", None)
            if new_session is not None:
                new_connector = getattr(new_session, "_connector", None)
                if new_connector is not None and new_connector not in self._connectors:
                    self._connectors.append(new_connector)
            self._loop = current_loop
        return self._docker

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

        # 校验并发配额(类变量锁保护,check+increment 临界区)
        async with self._lock:
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

        container: Any = None
        container_name = ""
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
                logger.debug("镜像拉取失败 session=%s image=%s: %s", session_id, spec.image, pull_exc)
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
                logger.debug("容器启动失败 session=%s name=%s: %s", session_id, container_name, run_exc)
                raise ContainerStartError(f"failed to run container {container_name}") from run_exc

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

            # 发布 SandboxSessionStarted(session save 块之后,best-effort 不触发 Saga 补偿;
            # 不以 session_repo 存在为条件,保证无仓储部署下事件流对称)
            await self._publish_event(
                SandboxSessionStarted(
                    session_id=session_id,
                    container_id=container_id,
                    image_digest=spec.image,
                    resource_limits={
                        "mem_limit_mb": spec.mem_limit_mb,
                        "cpu_quota": spec.cpu_quota,
                        "pids_limit": spec.pids_limit,
                    },
                ),
                session_id,
            )
            logger.info(
                "Started container for session %s: %s",
                session_id,
                container_name,
            )
        except Exception:
            # Saga 补偿: 容器已创建时 best-effort 删除,避免孤儿容器(pull 阶段失败无容器,不补偿)
            if container is not None:
                try:
                    await container.delete(force=True)
                except Exception:
                    logger.warning(
                        "Saga 补偿删除容器失败 session=%s container=%s",
                        session_id,
                        container_name,
                    )
            # 失败时回滚计数
            async with self._lock:
                AioDockerSandboxAdapter._running_count = max(0, AioDockerSandboxAdapter._running_count - 1)
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

        container = await docker.containers.get(container_id)
        try:
            return await asyncio.wait_for(
                self._run_code(container, session_id, code),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError as timeout_exc:
            # 超时即销毁(Round 6 增补契约): 防止容器内进程泄漏累积至 pids_limit
            await self._destroy_after_abort(container, session_id)
            raise SandboxTimeoutError(
                f"execution timeout after {effective_timeout}s",
                session_id=session_id,
                timeout_sec=effective_timeout,
            ) from timeout_exc
        except asyncio.CancelledError:
            # 外层 wait_for 取消路径(装饰器双保险): CancelledError 是 BaseException,
            # 不被 except Exception 捕获,必须显式清理后裸 raise 保取消语义
            await self._destroy_after_abort(container, session_id)
            raise
        except ExecutionError:
            # 领域异常(313/317)原样上浮,不二次包装
            raise
        except Exception as exc:
            logger.debug("沙箱执行异常 session=%s: %s", session_id, exc)
            raise ExecutionError("sandbox execution failed") from exc
        finally:
            # 仅 RUNNING 会话更新活动时间(避免覆盖超时销毁后的终态、或推迟 reaper 重试)
            if self._session_repo is not None:
                session = await self._session_repo.get_by_session_id(session_id)
                if session is not None and session.state == "RUNNING":
                    await self._session_repo.save(session.with_activity_updated())

    async def _run_code(self, container: Any, session_id: str, code: str) -> dict[str, Any]:
        """在容器内执行代码并收集 stdout/stderr

        aiodocker 协议层(_ExecParser)已解析 Docker 8 字节多路复用帧头,
        read_out() 返回已解复用的 Message(stream, data),EOF 时返回 None。

        失败判定(对齐 AC-5,顺序不可调换): exit_code==137 → SandboxResourceLimitExceededError(317);
        其余非零退出码或 stderr 非空 → ExecutionError(313)。

        Args:
            container: aiodocker DockerContainer 实例
            session_id: 会话 ID(用于异常上下文)
            code: 待执行的 Python 代码

        Returns:
            执行结果字典 {status, output, error, execution_time_ms}

        Raises:
            SandboxResourceLimitExceededError: OOM kill(exit 137)
            ExecutionError: 非零退出码或 stderr 非空
        """
        started = time.monotonic()
        exec_instance = await container.exec(
            cmd=["python", "-c", code],
            stdout=True,
            stderr=True,
        )
        stdout_chunks: list[bytes] = []
        stderr_chunks: list[bytes] = []
        async with exec_instance.start(detach=False) as stream:
            # 循环读取至 EOF(read_out 返回 None); 流中途异常上浮由调用方映射为 313
            while True:
                msg = await stream.read_out()
                if msg is None:
                    break
                if msg.stream == 2:
                    stderr_chunks.append(msg.data)
                else:
                    stdout_chunks.append(msg.data)
        try:
            inspect_data = await exec_instance.inspect()
            exit_code = inspect_data.get("ExitCode", 0)
        except Exception:
            exit_code = 0  # inspect 失败兜底按成功处理
        elapsed_ms = int((time.monotonic() - started) * 1000)

        if exit_code == 137:
            raise SandboxResourceLimitExceededError(
                "container resource limit exceeded (OOM kill)",
                session_id=session_id,
                limit_type="mem",
                docker_exit_code=137,
            )
        stdout_str = b"".join(stdout_chunks).decode("utf-8", errors="replace")
        stderr_str = b"".join(stderr_chunks).decode("utf-8", errors="replace")
        if exit_code != 0 or stderr_str:
            logger.debug(
                "沙箱执行失败 session=%s exit_code=%s stderr=%s",
                session_id,
                exit_code,
                stderr_str[:500],
            )
            raise ExecutionError(f"execution failed (exit_code={exit_code})")
        return {
            "status": "completed",
            "output": stdout_str,
            "error": None,
            "execution_time_ms": elapsed_ms,
        }

    async def _destroy_after_abort(self, container: Any, session_id: str) -> None:
        """超时/取消后销毁容器并释放配额(全部 best-effort,不掩盖原始异常)

        仅 delete 确认成功后才回滚计数 + 标记会话终态;
        delete 失败时会话保持 RUNNING,交由 SandboxSessionReaper 重试清理。

        Args:
            container: aiodocker DockerContainer 实例
            session_id: 会话 ID
        """
        try:
            await container.delete(force=True)
        except Exception:
            logger.warning("超时/取消后销毁容器失败 session=%s", session_id)
            return
        async with self._lock:
            AioDockerSandboxAdapter._running_count = max(0, AioDockerSandboxAdapter._running_count - 1)
        session_repo = self._session_repo
        terminated_session = None
        if session_repo is not None:
            try:
                session = await session_repo.get_by_session_id(session_id)
                if session is not None and session.state == "RUNNING":
                    terminated_session = session.with_terminated()
                    await session_repo.save(terminated_session)
            except Exception:
                logger.warning("超时/取消后更新会话终态失败 session=%s", session_id)
        # 末位语句: 发布 timeout_abort 终止事件(CancelledError 路径中 publish 若被二次取消,
        # 取消语义保留仅丢本次事件;其后不得再有清理代码)
        if terminated_session is not None:
            terminated_at = terminated_session.terminated_at
            duration = (terminated_at - terminated_session.started_at).total_seconds() if terminated_at else 0.0
            await self._publish_event(
                SandboxSessionTerminated(
                    session_id=session_id,
                    container_id=terminated_session.container_id or "",
                    termination_reason="timeout_abort",
                    duration_sec=duration,
                ),
                session_id,
            )

    async def stop_container(self, session_id: str, *, reason: str = "explicit_stop") -> None:
        """停止并移除 Docker 容器(幂等)

        语义(Round 6 增补契约):
        - 会话已 TERMINATED → 直接返回(幂等,不发布事件)
        - 容器已不存在(daemon 404) → 按成功处理(标记终止 + 回滚计数)
        - 其余删除失败 → 抛 ContainerStopError,不动状态/计数
        - 仅真实 RUNNING→TERMINATED 迁移时在锁释放后发布 SandboxSessionTerminated
          (adapter 是该事件的唯一发布点,reaper 经 reason="idle_timeout" 复用本路径)

        Args:
            session_id: 会话 ID
            reason: 终止原因(explicit_stop / idle_timeout,写入事件 termination_reason)

        Raises:
            ContainerStopError: 容器停止失败(非 404)
        """
        self._validate_session_id(session_id)
        docker = await self._ensure_docker()

        terminated_session = None
        # 类锁包裹"读状态→删容器→标终态→减计数"临界区,防并发双停双重减计数
        session_repo = self._session_repo
        async with self._lock:
            session = None
            if session_repo is not None:
                session = await session_repo.get_by_session_id(session_id)
                if session is not None and session.state == "TERMINATED":
                    logger.debug("Session already terminated, skip stop: %s", session_id)
                    return
            container_id = session.container_id if session else None
            if not container_id:
                logger.debug("No container to stop for session: %s", session_id)
                return

            try:
                container = await docker.containers.get(container_id)
                await container.delete(force=True)
            except DockerError as docker_exc:
                if docker_exc.status != 404:
                    raise ContainerStopError(f"failed to stop container {container_id}") from docker_exc
                # 容器已不存在,按成功处理
                logger.info("Container already gone (404), treat as stopped: session=%s", session_id)
            except Exception as exc:
                raise ContainerStopError(f"failed to stop container {container_id}") from exc

            # 仅真实 RUNNING→TERMINATED 迁移时更新状态 + 回滚计数
            if session is not None and session_repo is not None:
                terminated_session = session.with_terminated()
                await session_repo.save(terminated_session)
            AioDockerSandboxAdapter._running_count = max(0, AioDockerSandboxAdapter._running_count - 1)

        # 锁外发布(避免类锁临界区内 PG outbox 写入串行化所有并发 stop)
        if terminated_session is not None:
            terminated_at = terminated_session.terminated_at
            duration = (terminated_at - terminated_session.started_at).total_seconds() if terminated_at else 0.0
            await self._publish_event(
                SandboxSessionTerminated(
                    session_id=session_id,
                    container_id=terminated_session.container_id or "",
                    termination_reason=reason,
                    duration_sec=duration,
                ),
                session_id,
            )

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
