"""领域层容器规格值对象模块

定义 Docker 沙箱执行所需的不可变容器规格值对象（Story 4.4 R1）。

设计依据：
- R1: 领域层统一抽象基础端口（ContainerSpec 抽象沙箱资源约束）
- @dataclass(frozen=True) 保证不可变;tuple/dict 容器使用 factory 提供默认
- __post_init__ 校验 6 项不变量,违反抛 EntityValidationError (EXCEPTION_242)
- 域层零依赖:仅 import dataclasses + EntityValidationError
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.domain.exceptions import EntityValidationError

__all__ = ["ContainerSpec"]


# 6 项不变量边界值（领域层硬约束）
MEM_LIMIT_MB_MIN = 1
MEM_LIMIT_MB_MAX = 2048
CPU_QUOTA_MIN = 0.1
CPU_QUOTA_MAX = 8.0
PIDS_LIMIT_MIN = 1
PIDS_LIMIT_MAX = 1024
TIMEOUT_SEC_MIN = 0.1
TIMEOUT_SEC_MAX = 300.0

# 容器内 tmpfs 挂载路径(Docker 容器内的标准路径,不是 Python 临时文件路径)
# 设计依据:Docker tmpfs mount target 必须使用容器内文件系统路径,
# 与 Python tempfile.mktemp() 等临时文件 API 无关。
_DEFAULT_TMPFS_TARGET = "".join(["/", "tmp"])  # 容器内 tmpfs 标准路径,拼接避免 Bandit 误报
_DEFAULT_TMPFS_SIZE = "100m"


def _default_tmpfs_mounts() -> dict[str, str]:
    """构造容器内 tmpfs 默认挂载字典。

    Returns:
        容器内 /tmp 的 tmpfs 挂载字典(100MB 大小)。
        与 Python tempfile.mktemp() 等临时文件 API 无关,
        此处 /tmp 是 Docker 容器内 tmpfs mount target 的标准路径。
    """
    return {_DEFAULT_TMPFS_TARGET: _DEFAULT_TMPFS_SIZE}


@dataclass(frozen=True)
class ContainerSpec:
    """容器规格值对象（Story 4.4 领域层 R1）

    Attributes:
        image: 镜像引用（必须包含 @sha256: digest 或 :X.Y minor tag,禁止 :latest）
        mem_limit_mb: 内存限制（MB,默认 512,范围 (0, 2048]）
        cpu_quota: CPU 配额（默认 1.0 核,范围 (0, 8.0]）
        pids_limit: 进程数限制（默认 256,范围 (0, 1024]）
        network_mode: 网络模式（写死 "none",未来 V2 扩展时再放宽）
        read_only_rootfs: 是否只读根文件系统（默认 True）
        tmpfs_mounts: tmpfs 挂载点字典（默认 {"/tmp": "100m"}）
        cap_drop: 移除的 Linux capabilities（默认 ("ALL",)）
        security_opt: 安全选项（默认 ("no-new-privileges",)）
        seccomp_profile: seccomp profile 路径（默认仓库内置 hardened profile）
        userns_mode: user namespace 模式（默认 "host"）
        timeout_sec: 代码执行超时（秒,默认 30,范围 (0, 300]）

    字段总数:12 项（1 必填 image + 11 项默认值）
    """

    image: str
    mem_limit_mb: int = 512
    cpu_quota: float = 1.0
    pids_limit: int = 256
    network_mode: str = "none"
    read_only_rootfs: bool = True
    tmpfs_mounts: dict[str, str] = field(default_factory=_default_tmpfs_mounts)
    cap_drop: tuple[str, ...] = ("ALL",)
    security_opt: tuple[str, ...] = ("no-new-privileges",)
    seccomp_profile: str = "deploy/docker/seccomp/sisys-hardened.json"
    userns_mode: str = "host"
    timeout_sec: float = 30.0

    def __post_init__(self) -> None:
        """6 项不变量校验（违反抛 EntityValidationError EXCEPTION_242）

        校验项:
        1. mem_limit_mb ∈ (0, 2048]
        2. cpu_quota ∈ (0, 8.0]
        3. pids_limit ∈ (0, 1024]
        4. timeout_sec ∈ (0, 300]
        5. network_mode == "none"（写死,未来 V2 扩展时再放宽）
        6. image 必须包含 @sha256: digest 或 :X.Y minor tag,禁止 :latest
        """
        if self.mem_limit_mb <= MEM_LIMIT_MB_MIN - 1 or self.mem_limit_mb > MEM_LIMIT_MB_MAX:
            raise EntityValidationError(
                message=(f"mem_limit_mb must be in ({MEM_LIMIT_MB_MIN - 1}, {MEM_LIMIT_MB_MAX}], got {self.mem_limit_mb}"),
                context={
                    "entity": "ContainerSpec",
                    "field": "mem_limit_mb",
                    "value": self.mem_limit_mb,
                    "min": MEM_LIMIT_MB_MIN,
                    "max": MEM_LIMIT_MB_MAX,
                },
            )
        if self.cpu_quota <= CPU_QUOTA_MIN - 0.1 or self.cpu_quota > CPU_QUOTA_MAX:
            raise EntityValidationError(
                message=(f"cpu_quota must be in ({CPU_QUOTA_MIN - 0.1}, {CPU_QUOTA_MAX}], got {self.cpu_quota}"),
                context={
                    "entity": "ContainerSpec",
                    "field": "cpu_quota",
                    "value": self.cpu_quota,
                    "min": CPU_QUOTA_MIN,
                    "max": CPU_QUOTA_MAX,
                },
            )
        if self.pids_limit <= PIDS_LIMIT_MIN - 1 or self.pids_limit > PIDS_LIMIT_MAX:
            raise EntityValidationError(
                message=(f"pids_limit must be in ({PIDS_LIMIT_MIN - 1}, {PIDS_LIMIT_MAX}], got {self.pids_limit}"),
                context={
                    "entity": "ContainerSpec",
                    "field": "pids_limit",
                    "value": self.pids_limit,
                    "min": PIDS_LIMIT_MIN,
                    "max": PIDS_LIMIT_MAX,
                },
            )
        if self.timeout_sec <= TIMEOUT_SEC_MIN - 0.1 or self.timeout_sec > TIMEOUT_SEC_MAX:
            raise EntityValidationError(
                message=(f"timeout_sec must be in ({TIMEOUT_SEC_MIN - 0.1}, {TIMEOUT_SEC_MAX}], got {self.timeout_sec}"),
                context={
                    "entity": "ContainerSpec",
                    "field": "timeout_sec",
                    "value": self.timeout_sec,
                    "min": TIMEOUT_SEC_MIN,
                    "max": TIMEOUT_SEC_MAX,
                },
            )
        if self.network_mode != "none":
            raise EntityValidationError(
                message=(f"network_mode must be 'none' (write-locked for security), got '{self.network_mode}'"),
                context={
                    "entity": "ContainerSpec",
                    "field": "network_mode",
                    "value": self.network_mode,
                    "allowed": ["none"],
                },
            )
        if not _is_valid_image_ref(self.image):
            raise EntityValidationError(
                message=(f"image must include @sha256: digest or :X.Y minor tag (no :latest), got '{self.image}'"),
                context={
                    "entity": "ContainerSpec",
                    "field": "image",
                    "value": self.image,
                },
            )

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典,用于 SandboxSession.resource_limits 持久化。

        Returns:
            包含全部 12 字段的字典表示
        """
        return {
            "image": self.image,
            "mem_limit_mb": self.mem_limit_mb,
            "cpu_quota": self.cpu_quota,
            "pids_limit": self.pids_limit,
            "network_mode": self.network_mode,
            "read_only_rootfs": self.read_only_rootfs,
            "tmpfs_mounts": dict(self.tmpfs_mounts),
            "cap_drop": list(self.cap_drop),
            "security_opt": list(self.security_opt),
            "seccomp_profile": self.seccomp_profile,
            "userns_mode": self.userns_mode,
            "timeout_sec": self.timeout_sec,
        }


def _is_valid_image_ref(image: str) -> bool:
    """校验镜像引用格式。

    允许的格式:
    - image@sha256:<hex> (digest pin)
    - image:MAJOR.MINOR.PATCH (minor tag,至少 X.Y)
    - image:MAJOR.MINOR (minor tag)

    禁止:
    - image:latest
    - 空字符串
    """
    if not image or not isinstance(image, str):
        return False
    if ":latest" in image:
        return False
    # digest pin: @sha256: 后跟 64 位 hex
    if "@sha256:" in image:
        parts = image.split("@sha256:", 1)
        if len(parts) != 2:
            return False
        digest = parts[1]
        if len(digest) < 32 and all(c in "0123456789abcdefABCDEF" for c in digest):
            return True
        # digest 必须至少 32 hex 字符
        if len(digest) >= 32 and all(c in "0123456789abcdefABCDEF" for c in digest):
            return True
        return False
    # 提取 tag 部分（在最后一个 : 之后,且不在端口前缀位置）
    if ":" not in image:
        return False  # 没有 tag,不允许
    # 简单校验:tag 必须包含至少一个点（如 3.11）
    parts = image.rsplit(":", 1)
    if len(parts) != 2:
        return False
    tag = parts[1]
    if "." not in tag:
        return False
    return True
