"""Story 4.4 Round 3: SeccompProfileLoader + ContainerSpecBuilder seccomp 接线单元测试

验证:
- profile 加载/缓存/失败路径(SandboxConfigurationError 319)
- builder SecurityOpt 含 seccomp 内联
- adapter start_container 容器 config 含 seccomp + Labels
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import SandboxConfigurationError
from src.domain.value_objects.container_spec import ContainerSpec
from src.infrastructure.external_services.sandbox.container_spec_builder import (
    ContainerSpecBuilder,
)
from src.infrastructure.external_services.sandbox.seccomp_profile_loader import (
    load_seccomp_profile,
)

_VALID_SPEC = ContainerSpec(image="python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534")


class TestSeccompProfileLoader:
    """SeccompProfileLoader 测试"""

    def test_load_default_profile_success(self) -> None:
        """默认仓库内置 profile 加载成功,返回 seccomp= 前缀内联字符串"""
        result = load_seccomp_profile("deploy/docker/seccomp/sisys-hardened.json")

        assert result.startswith("seccomp=")
        profile = json.loads(result[len("seccomp=") :])
        assert profile["defaultAction"] == "SCMP_ACT_ERRNO"
        assert profile["syscalls"]

    def test_profile_dangerous_syscalls_not_allowed(self) -> None:
        """危险 syscall(ptrace/mount/kexec_load/bpf/socket)不在任何 ALLOW 规则中"""
        result = load_seccomp_profile("deploy/docker/seccomp/sisys-hardened.json")
        profile = json.loads(result[len("seccomp=") :])

        allowed: set[str] = set()
        for rule in profile["syscalls"]:
            if rule.get("action") == "SCMP_ACT_ALLOW":
                allowed.update(rule.get("names", []))
        for dangerous in ("ptrace", "mount", "umount2", "kexec_load", "bpf", "socket", "init_module", "keyctl"):
            assert dangerous not in allowed, f"{dangerous} 不应在 ALLOW 白名单"

    def test_load_missing_file_raises_319(self) -> None:
        """文件不存在抛 SandboxConfigurationError(EXCEPTION_319)"""
        with pytest.raises(SandboxConfigurationError) as exc_info:
            load_seccomp_profile("deploy/docker/seccomp/nonexistent.json")
        assert exc_info.value.code == "EXCEPTION_319"
        assert exc_info.value.context["field_name"] == "seccomp_profile"

    def test_load_invalid_json_raises_319(self, tmp_path: Any) -> None:
        """非法 JSON 抛 SandboxConfigurationError"""
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")

        with pytest.raises(SandboxConfigurationError):
            load_seccomp_profile(str(bad))

    def test_load_missing_required_keys_raises_319(self, tmp_path: Any) -> None:
        """缺 defaultAction/syscalls 键抛 SandboxConfigurationError"""
        incomplete = tmp_path / "incomplete.json"
        incomplete.write_text(json.dumps({"defaultAction": "SCMP_ACT_ERRNO"}), encoding="utf-8")

        with pytest.raises(SandboxConfigurationError):
            load_seccomp_profile(str(incomplete))

    def test_load_cached_identity(self) -> None:
        """同路径两次加载返回同一对象(lru_cache)"""
        first = load_seccomp_profile("deploy/docker/seccomp/sisys-hardened.json")
        second = load_seccomp_profile("deploy/docker/seccomp/sisys-hardened.json")
        assert first is second


class TestBuilderSeccompWiring:
    """ContainerSpecBuilder seccomp 接线测试"""

    def test_host_config_contains_seccomp_inline(self) -> None:
        """SecurityOpt 含 no-new-privileges + seccomp= 内联条目"""
        config = ContainerSpecBuilder.build_host_config(_VALID_SPEC, seccomp_inline="seccomp={}")

        security_opt = config["SecurityOpt"]
        assert "no-new-privileges" in security_opt
        assert any(o.startswith("seccomp=") for o in security_opt)


class TestAdapterSeccompAndLabels:
    """adapter start_container 容器 config 断言(seccomp + Labels)"""

    @patch("aiodocker.Docker")
    async def test_start_container_config_includes_seccomp_and_labels(self, mock_docker_cls: MagicMock) -> None:
        """containers.run 收到的 config 含 seccomp 内联与归属 Labels"""
        from src.infrastructure.external_services.sandbox.aiodocker_sandbox_adapter import (
            AioDockerSandboxAdapter,
        )

        mock_docker = MagicMock()
        mock_docker.images.pull = AsyncMock(return_value={"status": "success"})
        mock_docker.images.list = AsyncMock(return_value=[])
        container = MagicMock()
        container.id = "container-abc"
        container.show = AsyncMock(return_value={"Image": "sha256:9534e5a8"})
        mock_docker.containers.run = AsyncMock(return_value=container)
        mock_docker_cls.return_value = mock_docker

        adapter = AioDockerSandboxAdapter()
        await adapter.start_container("sess-seccomp-test")

        run_call = mock_docker.containers.run.await_args
        config = run_call.kwargs["config"]
        security_opt = config["HostConfig"]["SecurityOpt"]
        assert any(o.startswith("seccomp=") for o in security_opt)
        labels = config["Labels"]
        assert labels["managed-by"] == "sisys-sandbox"
        assert labels["sisys.session-id"] == "sess-seccomp-test"
        assert "sisys.tenant-id" in labels
