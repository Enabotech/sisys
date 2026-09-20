"""Story 4.4: ContainerSpec 值对象单元测试

验证 ContainerSpec 的 12 字段 + 6 项不变量校验。
参考样板：tests/unit/domain/value_objects/test_*.py
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.container_spec import ContainerSpec


def _make_container_spec(**overrides: object) -> ContainerSpec:
    """工厂函数:创建 ContainerSpec 默认实例,可覆盖任意字段"""
    defaults: dict[str, Any] = {
        "image": "python:3.11-slim@sha256:62dad7dd96e602c9e08c7724e50333b1834c4f2b6dbc5f8b7c97c39293fe2bdd",
    }
    defaults.update(overrides)
    return ContainerSpec(**defaults)


class TestContainerSpecFields:
    """ContainerSpec 字段完整性测试（12 字段）"""

    def test_required_image_field(self) -> None:
        """image 是必填字段"""
        spec = _make_container_spec()
        assert spec.image.startswith("python:")

    def test_default_mem_limit_mb(self) -> None:
        """mem_limit_mb 默认 512"""
        spec = _make_container_spec()
        assert spec.mem_limit_mb == 512

    def test_default_cpu_quota(self) -> None:
        """cpu_quota 默认 1.0"""
        spec = _make_container_spec()
        assert spec.cpu_quota == 1.0

    def test_default_pids_limit(self) -> None:
        """pids_limit 默认 256"""
        spec = _make_container_spec()
        assert spec.pids_limit == 256

    def test_default_network_mode_none(self) -> None:
        """network_mode 默认 'none'"""
        spec = _make_container_spec()
        assert spec.network_mode == "none"

    def test_default_read_only_rootfs(self) -> None:
        """read_only_rootfs 默认 True"""
        spec = _make_container_spec()
        assert spec.read_only_rootfs is True

    def test_default_tmpfs_mounts(self) -> None:
        """tmpfs_mounts 默认 {/tmp: size=100m,uid=1000}(docker daemon 标准格式)"""
        spec = _make_container_spec()
        assert spec.tmpfs_mounts == {"/sandbox-tmp": "size=100m,uid=1000"}

    def test_default_cap_drop(self) -> None:
        """cap_drop 默认 ('ALL',)"""
        spec = _make_container_spec()
        assert spec.cap_drop == ("ALL",)

    def test_default_security_opt(self) -> None:
        """security_opt 默认 ('no-new-privileges',)"""
        spec = _make_container_spec()
        assert spec.security_opt == ("no-new-privileges",)

    def test_default_seccomp_profile(self) -> None:
        """seccomp_profile 默认仓库内置路径"""
        spec = _make_container_spec()
        assert "sisys-hardened" in spec.seccomp_profile or spec.seccomp_profile.endswith(".json")

    def test_default_userns_mode(self) -> None:
        """userns_mode 默认 ''（Docker daemon 默认行为,不启用 user namespace remap）"""
        spec = _make_container_spec()
        assert spec.userns_mode == ""

    def test_default_timeout_sec(self) -> None:
        """timeout_sec 默认 30.0"""
        spec = _make_container_spec()
        assert spec.timeout_sec == 30.0

    def test_total_fields_count_is_12(self) -> None:
        """总字段数应为 12（含 image 必填）"""
        import dataclasses

        fields = dataclasses.fields(ContainerSpec)
        assert len(fields) == 12


class TestContainerSpecInvariants:
    """ContainerSpec 不变量校验测试（6 项）"""

    def test_mem_limit_mb_zero_raises(self) -> None:
        """mem_limit_mb == 0 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError):
            _make_container_spec(mem_limit_mb=0)

    def test_mem_limit_mb_negative_raises(self) -> None:
        """mem_limit_mb < 0 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError):
            _make_container_spec(mem_limit_mb=-1)

    def test_mem_limit_mb_over_2048_raises(self) -> None:
        """mem_limit_mb > 2048 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError):
            _make_container_spec(mem_limit_mb=2049)

    def test_mem_limit_mb_at_upper_boundary_ok(self) -> None:
        """mem_limit_mb == 2048 边界值应通过"""
        spec = _make_container_spec(mem_limit_mb=2048)
        assert spec.mem_limit_mb == 2048

    def test_cpu_quota_zero_raises(self) -> None:
        """cpu_quota == 0 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError):
            _make_container_spec(cpu_quota=0)

    def test_cpu_quota_negative_raises(self) -> None:
        """cpu_quota < 0 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError):
            _make_container_spec(cpu_quota=-0.5)

    def test_cpu_quota_over_8_raises(self) -> None:
        """cpu_quota > 8.0 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError):
            _make_container_spec(cpu_quota=8.5)

    def test_pids_limit_zero_raises(self) -> None:
        """pids_limit == 0 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError):
            _make_container_spec(pids_limit=0)

    def test_pids_limit_over_1024_raises(self) -> None:
        """pids_limit > 1024 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError):
            _make_container_spec(pids_limit=1025)

    def test_timeout_sec_zero_raises(self) -> None:
        """timeout_sec == 0 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError):
            _make_container_spec(timeout_sec=0)

    def test_timeout_sec_over_300_raises(self) -> None:
        """timeout_sec > 300 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError):
            _make_container_spec(timeout_sec=301)

    def test_network_mode_not_none_raises(self) -> None:
        """network_mode != 'none' 抛 EntityValidationError（写死 none）"""
        with pytest.raises(EntityValidationError):
            _make_container_spec(network_mode="bridge")

    def test_image_latest_tag_raises(self) -> None:
        """image 包含 :latest 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError):
            _make_container_spec(image="python:latest")

    def test_image_without_digest_or_minor_tag_raises(self) -> None:
        """image 缺少 @sha256: digest 或 :X.Y minor tag 抛 EntityValidationError"""
        with pytest.raises(EntityValidationError):
            _make_container_spec(image="python:3")

    def test_image_with_minor_tag_ok(self) -> None:
        """image 包含 :X.Y minor tag 应通过"""
        spec = _make_container_spec(image="python:3.11")
        assert spec.image == "python:3.11"

    def test_image_with_digest_ok(self) -> None:
        """image 包含 @sha256: digest 应通过"""
        spec = _make_container_spec(
            image="python:3.11-slim@sha256:62dad7dd96e602c9e08c7724e50333b1834c4f2b6dbc5f8b7c97c39293fe2bdd"
        )
        assert "@sha256:" in spec.image


class TestContainerSpecImmutability:
    """ContainerSpec 不可变性测试"""

    def test_container_spec_is_frozen(self) -> None:
        """ContainerSpec 应为 frozen dataclass"""
        spec = _make_container_spec()
        with pytest.raises((AttributeError, Exception)):
            setattr(spec, "image", "modified")


class TestContainerSpecEntityValidationErrorCode:
    """ContainerSpec 字段不变量错误码验证（EXCEPTION_242）"""

    def test_invalid_mem_limit_uses_entity_validation_error_code(self) -> None:
        """不变量违反应抛 EntityValidationError（EXCEPTION_242）"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_container_spec(mem_limit_mb=9999)
        assert exc_info.value.code == "EXCEPTION_242"
