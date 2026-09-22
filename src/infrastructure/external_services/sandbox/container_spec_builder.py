"""基础设施层 ContainerSpec → aiodocker kwargs 转换器

Story 4.4 — 将领域层 ContainerSpec 值对象转换为 aiodocker 容器启动参数。
负责:
- 安全配置 (mem_limit / cpu / pids / network / read_only / tmpfs)
- 权限管理 (cap_drop / security_opt / userns_mode)
- 容器命名 (sisys-sandbox-{tenant[:8]}-{session[:32]})

约束:容器名总长度 ≤ 55 字符(在 Docker 64 字符上限内,留 9 字符 buffer)
"""

from __future__ import annotations

import uuid
from typing import Any

from src.domain.exceptions import SandboxConfigurationError
from src.domain.value_objects.container_spec import ContainerSpec


class ContainerSpecBuilder:
    """ContainerSpec → aiodocker 容器配置 dict 转换器"""

    @staticmethod
    def build_host_config(spec: ContainerSpec) -> dict[str, Any]:
        """将 ContainerSpec 转换为 aiodocker HostConfig dict

        Args:
            spec: 容器规格值对象

        Returns:
            aiodocker HostConfig 字典(含 mem_limit / cpu_quota / network_mode 等)
        """
        return {
            # aiodocker 0.21 HostConfig 字段名:Memory/MemorySwap(字节)
            "Memory": spec.mem_limit_mb * 1024 * 1024,
            "MemorySwap": spec.mem_limit_mb * 1024 * 1024,  # 禁止 swap
            "CpuPeriod": 100000,
            "CpuQuota": int(spec.cpu_quota * 100000),
            "PidsLimit": spec.pids_limit,
            "NetworkMode": spec.network_mode,
            "ReadonlyRootfs": spec.read_only_rootfs,
            # tmpfs 格式：{"path": "options"} 字典(Docker daemon HostConfig.Tmpfs 类型)
            "Tmpfs": dict(spec.tmpfs_mounts),
            "CapDrop": list(spec.cap_drop),
            "SecurityOpt": list(spec.security_opt),
        }

    @staticmethod
    def build_container_name(tenant_id: uuid.UUID, session_id: str) -> str:
        """生成统一格式容器名:sisys-sandbox-{tenant[:8]}-{session[:32]}

        Args:
            tenant_id: 租户 UUID
            session_id: 会话 ID（已通过正则校验 ^[A-Za-z0-9_-]{1,64}$）

        Returns:
            Docker 容器名称,总长度 ≤ 55 字符

        Raises:
            SandboxConfigurationError: 容器名长度超 Docker 64 字符上限（理论上不会发生）
        """
        tenant_short = str(tenant_id).replace("-", "")[:8]
        session_short = session_id[:32]
        container_name = f"sisys-sandbox-{tenant_short}-{session_short}"
        if len(container_name) > 64:
            raise SandboxConfigurationError(
                f"container_name too long: {len(container_name)} > 64 chars",
                field_name="container_name",
                field_value=container_name,
                reason_detail="exceeds Docker 64-char limit",
            )
        return container_name


__all__ = ["ContainerSpecBuilder"]
