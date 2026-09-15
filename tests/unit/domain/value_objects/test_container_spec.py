"""ContainerSpec 值对象单元测试（Story 4.4 Task 1）

覆盖 AC-1: 12 字段值对象 + 6 项不变量校验

设计依据:
- 域层零依赖:仅依赖标准库 + 领域层异常
- TDD 循环:测试工厂函数 _make_container_spec + 6 项不变量失败测试
- 不可变设计:@dataclass(frozen=True) 验证
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.container_spec import (
    CPU_QUOTA_MAX,
    MEM_LIMIT_MB_MAX,
    PIDS_LIMIT_MAX,
    TIMEOUT_SEC_MAX,
    ContainerSpec,
)

# ============================================================================
# 工厂函数
# ============================================================================


def _make_container_spec(**overrides: Any) -> ContainerSpec:
    """构造 ContainerSpec 工厂函数。

    Args:
        **overrides: 覆盖默认字段的值

    Returns:
        ContainerSpec 实例
    """
    defaults: dict[str, Any] = {
        "image": "python:3.11-slim@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
    }
    defaults.update(overrides)
    return ContainerSpec(**defaults)


# ============================================================================
# 默认值验证测试
# ============================================================================


class TestContainerSpecDefaults:
    """测试 ContainerSpec 11 项默认值"""

    def test_default_mem_limit_mb(self) -> None:
        """mem_limit_mb 默认 512 MB"""
        spec = _make_container_spec()
        assert spec.mem_limit_mb == 512

    def test_default_cpu_quota(self) -> None:
        """cpu_quota 默认 1.0 核"""
        spec = _make_container_spec()
        assert spec.cpu_quota == 1.0

    def test_default_pids_limit(self) -> None:
        """pids_limit 默认 256"""
        spec = _make_container_spec()
        assert spec.pids_limit == 256

    def test_default_network_mode(self) -> None:
        """network_mode 默认 none"""
        spec = _make_container_spec()
        assert spec.network_mode == "none"

    def test_default_read_only_rootfs(self) -> None:
        """read_only_rootfs 默认 True"""
        spec = _make_container_spec()
        assert spec.read_only_rootfs is True

    def test_default_tmpfs_mounts(self) -> None:
        """tmpfs_mounts 默认 {"/tmp": "100m"}"""
        spec = _make_container_spec()
        assert spec.tmpfs_mounts == {"/tmp": "100m"}

    def test_default_cap_drop(self) -> None:
        """cap_drop 默认 ("ALL",)"""
        spec = _make_container_spec()
        assert spec.cap_drop == ("ALL",)

    def test_default_security_opt(self) -> None:
        """security_opt 默认 ("no-new-privileges",)"""
        spec = _make_container_spec()
        assert spec.security_opt == ("no-new-privileges",)

    def test_default_seccomp_profile(self) -> None:
        """seccomp_profile 默认仓库内置 hardened profile 路径"""
        spec = _make_container_spec()
        assert spec.seccomp_profile == "deploy/docker/seccomp/sisys-hardened.json"

    def test_default_userns_mode(self) -> None:
        """userns_mode 默认 host"""
        spec = _make_container_spec()
        assert spec.userns_mode == "host"

    def test_default_timeout_sec(self) -> None:
        """timeout_sec 默认 30.0 秒"""
        spec = _make_container_spec()
        assert spec.timeout_sec == 30.0


# ============================================================================
# 6 项不变量校验失败测试
# ============================================================================


class TestContainerSpecInvariants:
    """测试 ContainerSpec 6 项不变量校验"""

    def test_mem_limit_mb_zero_raises(self) -> None:
        """mem_limit_mb=0 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_container_spec(mem_limit_mb=0)
        assert exc_info.value.code == "EXCEPTION_242"
        assert "mem_limit_mb" in exc_info.value.context.get("field", "")

    def test_mem_limit_mb_exceeds_max_raises(self) -> None:
        """mem_limit_mb > 2048 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_container_spec(mem_limit_mb=MEM_LIMIT_MB_MAX + 1)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_cpu_quota_zero_raises(self) -> None:
        """cpu_quota=0 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_container_spec(cpu_quota=0)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_cpu_quota_exceeds_max_raises(self) -> None:
        """cpu_quota > 8.0 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_container_spec(cpu_quota=CPU_QUOTA_MAX + 0.1)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_pids_limit_zero_raises(self) -> None:
        """pids_limit=0 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_container_spec(pids_limit=0)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_pids_limit_exceeds_max_raises(self) -> None:
        """pids_limit > 1024 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_container_spec(pids_limit=PIDS_LIMIT_MAX + 1)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_timeout_sec_zero_raises(self) -> None:
        """timeout_sec=0 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_container_spec(timeout_sec=0)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_timeout_sec_exceeds_max_raises(self) -> None:
        """timeout_sec > 300 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_container_spec(timeout_sec=TIMEOUT_SEC_MAX + 1)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_network_mode_bridge_raises(self) -> None:
        """network_mode='bridge' 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_container_spec(network_mode="bridge")
        assert exc_info.value.code == "EXCEPTION_242"

    def test_network_mode_host_raises(self) -> None:
        """network_mode='host' 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_container_spec(network_mode="host")
        assert exc_info.value.code == "EXCEPTION_242"

    def test_image_latest_tag_raises(self) -> None:
        """image='python:latest' 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_container_spec(image="python:latest")
        assert exc_info.value.code == "EXCEPTION_242"

    def test_image_no_digest_no_tag_raises(self) -> None:
        """image='python' 无 digest 无 tag 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_container_spec(image="python")
        assert exc_info.value.code == "EXCEPTION_242"


# ============================================================================
# 有效 image 引用测试
# ============================================================================


class TestContainerSpecValidImages:
    """测试有效的 image 引用格式"""

    def test_image_with_sha256_digest(self) -> None:
        """image@sha256:<hex> digest 格式"""
        spec = _make_container_spec(
            image="python:3.11-slim@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
        )
        assert spec.image == "python:3.11-slim@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"

    def test_image_with_minor_tag(self) -> None:
        """image:X.Y minor tag 格式"""
        spec = _make_container_spec(image="python:3.11")
        assert spec.image == "python:3.11"

    def test_image_with_patch_tag(self) -> None:
        """image:X.Y.Z patch tag 格式"""
        spec = _make_container_spec(image="python:3.11.5")
        assert spec.image == "python:3.11.5"


# ============================================================================
# 不可变冻结测试
# ============================================================================


class TestContainerSpecImmutable:
    """测试 ContainerSpec 不可变设计

    使用 setattr() 而非直接属性赋值,绕过 mypy 静态类型检查
    (setattr 是运行时动态操作,不影响 frozen 类型语义)。
    """

    def test_cannot_modify_image(self) -> None:
        """修改 image 字段抛 FrozenInstanceError"""
        spec = _make_container_spec()
        with pytest.raises(FrozenInstanceError):
            setattr(spec, "image", "modified")

    def test_cannot_modify_mem_limit_mb(self) -> None:
        """修改 mem_limit_mb 字段抛 FrozenInstanceError"""
        spec = _make_container_spec()
        with pytest.raises(FrozenInstanceError):
            setattr(spec, "mem_limit_mb", 1024)

    def test_cannot_modify_network_mode(self) -> None:
        """修改 network_mode 字段抛 FrozenInstanceError"""
        spec = _make_container_spec()
        with pytest.raises(FrozenInstanceError):
            setattr(spec, "network_mode", "bridge")


# ============================================================================
# to_dict 序列化测试
# ============================================================================


class TestContainerSpecSerialization:
    """测试 ContainerSpec 序列化"""

    def test_to_dict_contains_all_12_fields(self) -> None:
        """to_dict() 包含全部 12 字段"""
        spec = _make_container_spec()
        data = spec.to_dict()
        assert len(data) == 12
        assert data["image"] == spec.image
        assert data["mem_limit_mb"] == spec.mem_limit_mb
        assert data["cpu_quota"] == spec.cpu_quota
        assert data["pids_limit"] == spec.pids_limit
        assert data["network_mode"] == spec.network_mode
        assert data["read_only_rootfs"] == spec.read_only_rootfs
        assert data["tmpfs_mounts"] == dict(spec.tmpfs_mounts)
        assert data["cap_drop"] == list(spec.cap_drop)
        assert data["security_opt"] == list(spec.security_opt)
        assert data["seccomp_profile"] == spec.seccomp_profile
        assert data["userns_mode"] == spec.userns_mode
        assert data["timeout_sec"] == spec.timeout_sec

    def test_to_dict_tmpfs_is_independent_copy(self) -> None:
        """to_dict() 返回的 tmpfs_mounts 是独立副本,避免共享可变状态"""
        spec = _make_container_spec()
        data = spec.to_dict()
        data["tmpfs_mounts"]["/new"] = "50m"
        # 原 spec 不应受影响
        assert "/new" not in spec.tmpfs_mounts


# ============================================================================
# 边界值测试
# ============================================================================


class TestContainerSpecBoundaryValues:
    """测试 ContainerSpec 边界值"""

    def test_mem_limit_mb_min_value(self) -> None:
        """mem_limit_mb=1 合法"""
        spec = _make_container_spec(mem_limit_mb=1)
        assert spec.mem_limit_mb == 1

    def test_mem_limit_mb_max_value(self) -> None:
        """mem_limit_mb=2048 合法"""
        spec = _make_container_spec(mem_limit_mb=MEM_LIMIT_MB_MAX)
        assert spec.mem_limit_mb == MEM_LIMIT_MB_MAX

    def test_cpu_quota_min_value(self) -> None:
        """cpu_quota=0.1 合法"""
        spec = _make_container_spec(cpu_quota=0.1)
        assert spec.cpu_quota == 0.1

    def test_cpu_quota_max_value(self) -> None:
        """cpu_quota=8.0 合法"""
        spec = _make_container_spec(cpu_quota=CPU_QUOTA_MAX)
        assert spec.cpu_quota == CPU_QUOTA_MAX

    def test_pids_limit_min_value(self) -> None:
        """pids_limit=1 合法"""
        spec = _make_container_spec(pids_limit=1)
        assert spec.pids_limit == 1

    def test_pids_limit_max_value(self) -> None:
        """pids_limit=1024 合法"""
        spec = _make_container_spec(pids_limit=PIDS_LIMIT_MAX)
        assert spec.pids_limit == PIDS_LIMIT_MAX

    def test_timeout_sec_min_value(self) -> None:
        """timeout_sec=0.1 合法"""
        spec = _make_container_spec(timeout_sec=0.1)
        assert spec.timeout_sec == 0.1

    def test_timeout_sec_max_value(self) -> None:
        """timeout_sec=300.0 合法"""
        spec = _make_container_spec(timeout_sec=TIMEOUT_SEC_MAX)
        assert spec.timeout_sec == TIMEOUT_SEC_MAX


__all__ = [
    "TestContainerSpecDefaults",
    "TestContainerSpecInvariants",
    "TestContainerSpecValidImages",
    "TestContainerSpecImmutable",
    "TestContainerSpecSerialization",
    "TestContainerSpecBoundaryValues",
]
