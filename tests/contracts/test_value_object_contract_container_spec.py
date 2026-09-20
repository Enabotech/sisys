"""Story 4.4: ContainerSpec 值对象契约测试

参考样板:tests/contracts/test_event_contract_tool_executed.py
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.container_spec import ContainerSpec


class TestContainerSpecContract:
    """ContainerSpec 值对象契约测试"""

    def _make_spec(self, **overrides: object) -> ContainerSpec:
        defaults: dict[str, Any] = {
            "image": "python:3.11-slim@sha256:62dad7dd96e602c9e08c7724e50333b1834c4f2b6dbc5f8b7c97c39293fe2bdd"
        }
        defaults.update(overrides)
        return ContainerSpec(**defaults)

    def test_is_frozen_dataclass(self) -> None:
        """ContainerSpec 应为 frozen dataclass"""
        assert dataclasses.is_dataclass(ContainerSpec)
        # 通过实例化后修改验证 frozen
        spec = self._make_spec()
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
            setattr(spec, "image", "modified")

    def test_total_fields_is_12(self) -> None:
        """总字段数应为 12"""
        fields = dataclasses.fields(ContainerSpec)
        assert len(fields) == 12

    def test_required_field_image_only(self) -> None:
        """仅 image 是必填字段(default 或 default_factory 均为 MISSING 即视为必填)"""
        required_fields = [
            f
            for f in dataclasses.fields(ContainerSpec)
            if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
        ]
        assert len(required_fields) == 1
        assert required_fields[0].name == "image"

    def test_default_values_match_spec(self) -> None:
        """默认值应匹配 Story 4.4 AC-1 定义"""
        spec = self._make_spec()
        assert spec.mem_limit_mb == 512
        assert spec.cpu_quota == 1.0
        assert spec.pids_limit == 256
        assert spec.network_mode == "none"
        assert spec.read_only_rootfs is True
        assert spec.tmpfs_mounts == {"/sandbox-tmp": "size=100m,uid=1000"}
        assert spec.cap_drop == ("ALL",)
        assert spec.security_opt == ("no-new-privileges",)
        assert spec.userns_mode == ""
        assert spec.timeout_sec == 30.0
        # seccomp_profile 应为 JSON 文件路径
        assert "sisys-hardened" in spec.seccomp_profile or spec.seccomp_profile.endswith(".json")

    def test_inv_validation_uses_entity_validation_error(self) -> None:
        """不变量校验应抛 EntityValidationError(EXCEPTION_242)"""
        with pytest.raises(EntityValidationError) as exc_info:
            self._make_spec(mem_limit_mb=9999)
        assert exc_info.value.code == "EXCEPTION_242"
