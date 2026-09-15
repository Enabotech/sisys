"""基础设施层容器规格转换器模块（Story 4.4 Task 5 重构)

将领域层 ContainerSpec 值对象转换为 aiodocker 0.21.0 容器启动 config dict。

设计依据:
- aiodocker 0.21.0 DockerContainers.run(config, *, name, auth) — 只接受 config 字典 + name
- config 字典结构遵循 Docker Engine API v1.40+ ContainerCreate schema:
  - Image: 镜像引用(顶层)
  - HostConfig: 容器运行时配置(Memory / CpuQuota / NetworkMode / ... 嵌套)
  - 其他顶层字段如 Env / Cmd / User
- 单一职责:ContainerSpec → dict[str, Any](符合 Docker API schema)
- 安全配置映射:mem_limit(MB→bytes) / pids_limit / network_mode / read_only / tmpfs /
  cap_drop / security_opt / userns_mode
- CPU 配额转换:cpu_quota(核数)→ CpuPeriod/CpuQuota(微秒对)
- memswap_limit = mem_limit(字节相同,禁用 swap)
"""

from __future__ import annotations

from typing import Any

from src.domain.value_objects.container_spec import ContainerSpec

__all__ = ["ContainerSpecBuilder"]


class ContainerSpecBuilder:
    """ContainerSpec → aiodocker config dict 转换器(Story 4.4 Task 5 重构抽取)

    Attributes:
        _cpu_period_us: CPU 周期(微秒,默认 100000 = 100ms)
    """

    def __init__(self, cpu_period_us: int = 100000) -> None:
        """初始化转换器。

        Args:
            cpu_period_us: CPU 周期微秒数(默认 100000 = 100ms)
        """
        self._cpu_period_us = cpu_period_us

    def build_config(self, spec: ContainerSpec) -> dict[str, Any]:
        """将 ContainerSpec 转换为 aiodocker 容器启动 config dict。

        Args:
            spec: 领域层 ContainerSpec 值对象

        Returns:
            符合 Docker Engine API v1.40+ ContainerCreate schema 的配置字典
        """
        mem_bytes = spec.mem_limit_mb * 1024 * 1024
        # Docker API Tmpfs 字段是 Map[String, String] 类型
        # 格式: {"/tmp": "rw,size=100m,uid=1000"} — 必须包含至少一个选项
        tmpfs_config: dict[str, str] = {}
        for mount_path, size in spec.tmpfs_mounts.items():
            # 标准化为 size=N 格式(默认 rw)
            if "size=" in size:
                tmpfs_config[mount_path] = f"rw,{size}" if not size.startswith("rw,") else size
            else:
                tmpfs_config[mount_path] = f"rw,size={size}"
        return {
            "Image": spec.image,
            # 默认 Cmd: sleep infinity 让容器持久运行(否则 alpine/python 等基础镜像启动后立即 exit)
            # exec_create 必须在容器运行状态下才能工作,这是真实 Docker 而非 mock 的关键差异
            "Cmd": ["sleep", "infinity"],
            "HostConfig": {
                "Memory": mem_bytes,
                "MemorySwap": mem_bytes,  # 禁用 swap
                "CpuPeriod": self._cpu_period_us,
                "CpuQuota": int(spec.cpu_quota * self._cpu_period_us),
                "PidsLimit": spec.pids_limit,
                "NetworkMode": spec.network_mode,
                "ReadonlyRootfs": spec.read_only_rootfs,
                "Tmpfs": tmpfs_config,
                "CapDrop": list(spec.cap_drop),
                "SecurityOpt": list(spec.security_opt),
                "UsernsMode": spec.userns_mode,
            },
            # 默认 detach=True(由 aiodocker.containers.run() 隐含)
        }


__all__ = ["ContainerSpecBuilder"]
