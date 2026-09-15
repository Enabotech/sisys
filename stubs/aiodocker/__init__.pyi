"""aiodocker 第三方库类型存根（PEP 561)

aiodocker 无 py.typed,
本存根仅覆盖 Story 4.4 实际使用的 9 个 API 面:

- Docker.pull(image) — 镜像拉取
- Docker.ping() — daemon 健康检查
- Docker.containers.run(image, **kwargs) — 容器启动
- Docker.containers.get(container_id) — 容器查询
- Docker.containers.list(filter=...) — 孤儿容器扫描
- Docker.containers.delete(force=True) — 容器删除
- Container.exec_create(cmd, ...) — 执行命令创建
- Container.exec_start(exec_id, ...) — 执行命令启动
- Container.stats(stream=False) — 资源统计（性能基准）

设计依据（CLAUDE.md §5 import-untyped 修复）:
- 禁止用 ignore_missing_imports=true 豁免
- 必须在 stubs/<package>/__init__.pyi 创建 PEP 561 类型存根
- 仅覆盖项目实际使用的 API 面,避免过度设计
"""

from __future__ import annotations

from typing import Any

__all__ = ["Docker", "Container", "Exec"]

class Exec:
    """aiodocker exec 实例(对应 Container.exec_create 返回值)"""

    id: str

    async def start(self, detach: bool = False) -> tuple[bytes, bytes] | None:
        """启动 exec 进程,返回 (stdout, stderr) 元组或 None(detach=True 时)。

        Args:
            detach: 是否分离模式

        Returns:
            (stdout_bytes, stderr_bytes) 元组或 None
        """
        ...

class Container:
    """aiodocker 容器实例(对应 Docker.containers.get/run 返回值)"""

    id: str
    name: str

    async def delete(self, *, force: bool = False, v: bool = False) -> None:
        """删除容器。

        Args:
            force: 是否强制删除运行中容器
            v: 是否删除关联卷
        """
        ...

    async def start(self) -> None:
        """启动容器。"""
        ...

    async def stop(self, *, timeout: int = 10) -> None:
        """停止容器。

        Args:
            timeout: 优雅停止超时秒数
        """
        ...

    async def wait(self) -> dict[str, Any]:
        """等待容器退出,返回 exit code 字典。

        Returns:
            包含 "StatusCode" 键的字典
        """
        ...

    async def exec_create(self, cmd: list[str], *, environment: dict[str, str] | None = None) -> Exec:
        """创建 exec 实例。

        Args:
            cmd: 命令列表
            environment: 环境变量字典

        Returns:
            Exec 实例
        """
        ...

    async def exec_start(self, exec_id: str, *, detach: bool = False) -> tuple[bytes, bytes] | None:
        """启动 exec(简化接口)。

        Args:
            exec_id: exec ID
            detach: 是否分离模式

        Returns:
            (stdout_bytes, stderr_bytes) 元组或 None
        """
        ...

    async def stats(self, *, stream: bool = False) -> dict[str, Any]:
        """查询容器资源统计。

        Args:
            stream: 是否流式

        Returns:
            资源统计字典(包含 CPU/内存等字段)
        """
        ...

class ContainerCollection:
    """aiodocker 容器集合(Docker.containers 实例)"""

    async def run(
        self,
        image: str,
        *,
        name: str | None = None,
        mem_limit: str | int | None = None,
        memswap_limit: str | int | None = None,
        cpu_period: int | None = None,
        cpu_quota: int | None = None,
        pids_limit: int | None = None,
        network_mode: str | None = None,
        read_only: bool = False,
        tmpfs: dict[str, str] | None = None,
        cap_drop: list[str] | None = None,
        security_opt: list[str] | None = None,
        userns_mode: str | None = None,
        labels: dict[str, str] | None = None,
        environment: dict[str, str] | None = None,
        detach: bool = True,
        command: str | list[str] | None = None,
        working_dir: str | None = None,
        user: str | None = None,
        hostname: str | None = None,
        domainname: str | None = None,
        restart_policy: dict[str, Any] | None = None,
    ) -> Container:
        """启动容器。

        Args:
            image: 镜像引用
            name: 容器名
            mem_limit: 内存限制(如 "512m")
            memswap_limit: swap 限制(通常与 mem_limit 相等以禁用 swap)
            cpu_period: CPU 周期(微秒,通常 100000)
            cpu_quota: CPU 配额(微秒,cpu_period 的倍数)
            pids_limit: 进程数限制
            network_mode: 网络模式("none"/"bridge"/...)
            read_only: 是否只读根文件系统
            tmpfs: tmpfs 挂载点字典
            cap_drop: 移除的 Linux capabilities
            security_opt: 安全选项(如 ["no-new-privileges"])
            userns_mode: user namespace 模式("host"/自定义)
            labels: 标签字典
            environment: 环境变量
            detach: 是否分离
            command: 默认命令
            working_dir: 工作目录
            user: 运行用户
            hostname: 主机名
            domainname: 域名
            restart_policy: 重启策略

        Returns:
            Container 实例
        """
        ...

    async def get(self, container_id: str) -> Container:
        """按 ID 或名称查询容器。

        Args:
            container_id: 容器 ID 或名称

        Returns:
            Container 实例
        """
        ...

    async def list(
        self,
        *,
        all: bool = False,
        filters: dict[str, list[str]] | None = None,
    ) -> list[Container]:
        """列出容器。

        Args:
            all: 是否包含已停止容器
            filters: 过滤条件字典(如 {"name": ["sisys-sandbox-*"]})

        Returns:
            Container 列表
        """
        ...

    async def delete(self, container_id: str, *, force: bool = False, v: bool = False) -> None:
        """删除容器。

        Args:
            container_id: 容器 ID
            force: 是否强制
            v: 是否删除卷
        """
        ...

class Docker:
    """aiodocker Docker 客户端主类"""

    containers: ContainerCollection

    def __init__(
        self,
        url: str | None = None,
        *,
        connector: Any | None = None,
        session: Any | None = None,
        ssl_context: Any | None = None,
    ) -> None:
        """初始化 Docker 客户端。

        Args:
            url: Docker daemon URL(如 "unix:///var/run/docker.sock" 或 "tcp://...")
            connector: 可选的自定义 aiohttp 连接器
            session: 可选的预创建 aiohttp.ClientSession（用于客户端复用）
            ssl_context: 可选的 SSL 上下文
        """
        ...

    async def pull(
        self,
        image: str,
        *,
        auth: dict[str, str] | None = None,
        stream: bool = False,
    ) -> Any:
        """拉取镜像。

        Args:
            image: 镜像引用
            auth: 认证信息(如 {"username": "...", "password": "..."})
            stream: 是否流式

        Returns:
            流式消息列表或 None
        """
        ...

    async def ping(self) -> bool:
        """Docker daemon 健康检查。

        Returns:
            daemon 可达返回 True,否则抛异常
        """
        ...

    async def version(self) -> dict[str, Any]:
        """查询 Docker 版本。

        Returns:
            版本信息字典
        """
        ...

    async def close(self) -> None:
        """关闭客户端连接。"""
        ...
