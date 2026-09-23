"""领域层容器规格值对象模块

定义不可变容器规格值对象（12 字段）+ 6 项不变量校验。
Story 4.4 — Docker 沙箱执行。

约束：
- 领域层零外部依赖（仅 Python 标准库）
- @dataclass(frozen=True) 不可变
- __post_init__ 抛 EntityValidationError(EXCEPTION_242)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.domain.exceptions import EntityValidationError


@dataclass(frozen=True)
class ContainerSpec:
    """容器规格值对象（12 字段,不可变）

    Attributes:
        image: 镜像引用（必填,必须包含 @sha256: digest 或 :X.Y minor tag,禁止 :latest）
        mem_limit_mb: 内存限制(MB),默认 512,上限 2048
        cpu_quota: CPU 配额(核数),默认 1.0,上限 8.0
        pids_limit: 进程数限制,默认 256,上限 1024
        network_mode: 网络模式（写死 "none"）
        read_only_rootfs: 是否只读根文件系统,默认 True
        tmpfs_mounts: tmpfs 挂载点字典,默认 {"/sandbox-tmp": "size=100m,uid=1000"}
        cap_drop: 移除的 Linux capabilities,默认 ("ALL",)
        security_opt: 安全选项,默认 ("no-new-privileges",)
        seccomp_profile: seccomp profile 路径,默认仓库内置 hardened profile
        userns_mode: user namespace 模式,默认 "" (Docker daemon 默认行为)
        timeout_sec: 代码执行超时(秒),默认 30.0,上限 300

    字段总数:**12 项**（含 image 必填 + 11 项默认值）
    """

    image: str
    mem_limit_mb: int = 512
    cpu_quota: float = 1.0
    pids_limit: int = 256
    network_mode: str = "none"
    read_only_rootfs: bool = True
    tmpfs_mounts: dict[str, str] = field(default_factory=lambda: {"/sandbox-tmp": "size=100m,uid=1000"})
    cap_drop: tuple[str, ...] = ("ALL",)
    security_opt: tuple[str, ...] = ("no-new-privileges",)
    seccomp_profile: str = "deploy/docker/seccomp/sisys-hardened.json"
    userns_mode: str = ""
    timeout_sec: float = 30.0

    def __post_init__(self) -> None:
        """字段不变量校验（抛 EntityValidationError EXCEPTION_242）

        6 项校验:
        1. mem_limit_mb ∈ (0, 2048]
        2. cpu_quota ∈ (0, 8.0]
        3. pids_limit ∈ (0, 1024]
        4. timeout_sec ∈ (0, 300]
        5. network_mode == "none"（写死）
        6. image 必须包含 @sha256: digest 或 :X.Y minor tag;禁止 :latest
        """
        # 校验 1: 内存上限
        if self.mem_limit_mb <= 0 or self.mem_limit_mb > 2048:
            raise EntityValidationError(
                f"mem_limit_mb must be in (0, 2048], got {self.mem_limit_mb}",
                context={
                    "entity": "ContainerSpec",
                    "field": "mem_limit_mb",
                    "value": self.mem_limit_mb,
                    "constraint": "(0, 2048]",
                },
            )
        # 校验 2: CPU 上限
        if self.cpu_quota <= 0 or self.cpu_quota > 8.0:
            raise EntityValidationError(
                f"cpu_quota must be in (0, 8.0], got {self.cpu_quota}",
                context={
                    "entity": "ContainerSpec",
                    "field": "cpu_quota",
                    "value": self.cpu_quota,
                    "constraint": "(0, 8.0]",
                },
            )
        # 校验 3: pids 上限
        if self.pids_limit <= 0 or self.pids_limit > 1024:
            raise EntityValidationError(
                f"pids_limit must be in (0, 1024], got {self.pids_limit}",
                context={
                    "entity": "ContainerSpec",
                    "field": "pids_limit",
                    "value": self.pids_limit,
                    "constraint": "(0, 1024]",
                },
            )
        # 校验 4: timeout 上限
        if self.timeout_sec <= 0 or self.timeout_sec > 300:
            raise EntityValidationError(
                f"timeout_sec must be in (0, 300], got {self.timeout_sec}",
                context={
                    "entity": "ContainerSpec",
                    "field": "timeout_sec",
                    "value": self.timeout_sec,
                    "constraint": "(0, 300]",
                },
            )
        # 校验 5: 网络模式写死
        if self.network_mode != "none":
            raise EntityValidationError(
                f"network_mode must be 'none', got '{self.network_mode}'",
                context={
                    "entity": "ContainerSpec",
                    "field": "network_mode",
                    "value": self.network_mode,
                    "constraint": "'none' (hardcoded)",
                },
            )
        # 校验 6: image 必须包含 digest 或 minor tag,禁止 latest
        if ":latest" in self.image:
            raise EntityValidationError(
                f"image must not contain ':latest', got '{self.image}'",
                context={
                    "entity": "ContainerSpec",
                    "field": "image",
                    "value": self.image,
                    "constraint": "must contain '@sha256:' digest or ':X.Y' minor tag, no ':latest'",
                },
            )
        # 接受任一: @sha256: digest 或 :X.Y 格式 minor tag (如 python:3.11)
        has_digest = "@sha256:" in self.image
        # 提取最后一个 : 之后的内容作为 tag 部分(必须形如 X.Y 或 X.Y.Z)
        tag_match = re.search(r":(\d+\.\d+(?:\.\d+)?)(?:@|$)", self.image)
        has_minor_tag = tag_match is not None
        if not (has_digest or has_minor_tag):
            raise EntityValidationError(
                f"image must contain '@sha256:' digest or ':X.Y' minor tag, got '{self.image}'",
                context={
                    "entity": "ContainerSpec",
                    "field": "image",
                    "value": self.image,
                    "constraint": "must contain '@sha256:' digest or ':X.Y' minor tag",
                },
            )


__all__ = ["ContainerSpec"]
