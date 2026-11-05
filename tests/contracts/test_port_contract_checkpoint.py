"""Story 6-3 — Checkpoint 端口契约测试（注册可达/spec 元数据/注入链）。

形态对齐 test_port_contract_blm_planning.py：注册可达断言 + spec 元数据
（interface/lifetime/tags/owner）+ 真实构造 resolve + 注入链签名断言。
链路接线断言清单①②③承载（Task 0.9）。
"""

from __future__ import annotations

import inspect

import pytest

from src.domain.ports.registry import _global_registry

PORT_NAMES = (
    "checkpoint_service",
    "checkpoint_use_case",
    "checkpoint_recovery_use_case",
    "checkpoint_list_use_case",
    "checkpoint_recovery_execute_use_case",
)


class TestCheckpointPortContracts:
    """Checkpoint 新注册三端口契约（R1 审查 FR-17 扩恢复用例）。"""

    def test_ports_registered(self) -> None:
        """端口注册可达（bootstrap 后 registry 可查——6-6 增 checkpoint_list_use_case）。"""
        for name in PORT_NAMES:
            spec = _global_registry.get(name)
            assert spec is not None, f"端口 {name} 未注册"

    def test_checkpoint_service_version_v1_1_0(self) -> None:
        """checkpoint_service spec.version == "v1.1.0"（Story 6-6 演进留痕）。"""
        spec = _global_registry.get("checkpoint_service")
        assert spec is not None
        assert spec.version == "v1.1.0", (
            f"checkpoint_service version 实测={spec.version} 期望='v1.1.0'（Story 6-6 端口演进——读面/恢复执行两方法组纯新增）"
        )

    def test_checkpoint_list_use_case_spec_metadata(self) -> None:
        """checkpoint_list_use_case 元数据（SINGLETON 无状态透传——6-3 用例注册形态同构）。"""
        from src.application.use_cases.checkpoint_approval import ListCheckpointsUseCase
        from src.domain.ports.registry import Lifetime

        spec = _global_registry.get("checkpoint_list_use_case")
        assert spec is not None
        assert spec.interface is ListCheckpointsUseCase
        assert spec.lifetime == Lifetime.SINGLETON
        assert spec.owner
        assert "checkpoint" in spec.tags

    def test_checkpoint_service_spec_metadata(self) -> None:
        """checkpoint_service 元数据（interface/lifetime/tags/owner 齐备）。"""
        from src.application.ports.checkpoint import CheckpointServicePort
        from src.domain.ports.registry import Lifetime

        spec = _global_registry.get("checkpoint_service")
        assert spec is not None
        assert spec.interface is CheckpointServicePort
        assert spec.lifetime == Lifetime.SINGLETON  # 无状态编排服务（blm_planning_service 先例）
        assert "checkpoint" in spec.tags
        assert spec.owner

    def test_checkpoint_use_case_spec_metadata(self) -> None:
        """checkpoint_use_case 元数据（SINGLETON——无状态透传，Task 0 钦定）。"""
        from src.domain.ports.registry import Lifetime

        spec = _global_registry.get("checkpoint_use_case")
        assert spec is not None
        assert spec.lifetime == Lifetime.SINGLETON
        assert spec.owner

    def test_checkpoint_service_lambda_injects_five_dependencies(self) -> None:
        """组合根 lambda 五依赖注入面（检索-压缩循环激活证据——链路断言③）。"""
        spec = _global_registry.get("checkpoint_service")
        assert spec is not None
        assert callable(spec.impl), "impl 应为 lambda 工厂（resolver 注入构造）"
        source = inspect.getsource(spec.impl)
        for dependency in (
            "persistent_note_taker",
            "context_compressor",
            "strategic_archive_service",
            "snapshot_repository",
            "event_publisher",
        ):
            assert dependency in source, f"组合根 lambda 未注入 {dependency}（五依赖注入面断裂）"

    def test_checkpoint_service_resolvable(self) -> None:
        """resolve 可达 + 端口兼容（真实构造——链路断言①）。"""
        from src.application.ports.checkpoint import CheckpointServicePort
        from src.domain.ports.resolver import resolve

        instance = resolve("checkpoint_service")
        assert instance is not None
        assert isinstance(instance, CheckpointServicePort)

    def test_checkpoint_use_case_resolvable(self) -> None:
        """checkpoint_use_case resolve 可达 + 注入 checkpoint_service 非 None。"""
        from src.domain.ports.resolver import resolve

        instance = resolve("checkpoint_use_case")
        assert instance is not None
        assert getattr(instance, "_checkpoint_service", None) is not None

    def test_checkpoint_recovery_use_case_spec_metadata(self) -> None:
        """checkpoint_recovery_use_case 元数据（SINGLETON——R1 审查 FR-17 补齐注册）。"""
        from src.application.use_cases.create_checkpoint import RecoverCheckpointUseCase
        from src.domain.ports.registry import Lifetime

        spec = _global_registry.get("checkpoint_recovery_use_case")
        assert spec is not None
        assert spec.interface is RecoverCheckpointUseCase
        assert spec.lifetime == Lifetime.SINGLETON
        assert spec.owner

    def test_checkpoint_recovery_use_case_resolvable(self) -> None:
        """checkpoint_recovery_use_case resolve 可达 + 注入链非 None（6-6 sanctioned 入口）。"""
        from src.application.use_cases.create_checkpoint import RecoverCheckpointUseCase
        from src.domain.ports.resolver import resolve

        instance = resolve("checkpoint_recovery_use_case")
        assert instance is not None
        assert isinstance(instance, RecoverCheckpointUseCase)
        assert getattr(instance, "_checkpoint_service", None) is not None

    def test_checkpoint_list_use_case_resolvable(self) -> None:
        """checkpoint_list_use_case resolve 可达 + 注入链非 None（Story 6-6 链路接线断言①）。"""
        from src.application.use_cases.checkpoint_approval import ListCheckpointsUseCase
        from src.domain.ports.resolver import resolve

        instance = resolve("checkpoint_list_use_case")
        assert instance is not None
        assert isinstance(instance, ListCheckpointsUseCase)
        assert getattr(instance, "_checkpoint_service", None) is not None

    def test_checkpoint_recovery_execute_use_case_spec_metadata(self) -> None:
        """checkpoint_recovery_execute_use_case 元数据（SINGLETON 无状态——AC-3 执行面）。"""
        from src.application.use_cases.checkpoint_approval import ExecuteCheckpointRecoveryUseCase
        from src.domain.ports.registry import Lifetime

        spec = _global_registry.get("checkpoint_recovery_execute_use_case")
        assert spec is not None
        assert spec.interface is ExecuteCheckpointRecoveryUseCase
        assert spec.lifetime == Lifetime.SINGLETON
        assert spec.owner
        assert "checkpoint" in spec.tags

    def test_checkpoint_recovery_execute_use_case_resolvable(self) -> None:
        """checkpoint_recovery_execute_use_case resolve 可达 + 注入链非 None（接线断言①）。"""
        from src.application.use_cases.checkpoint_approval import ExecuteCheckpointRecoveryUseCase
        from src.domain.ports.resolver import resolve

        instance = resolve("checkpoint_recovery_execute_use_case")
        assert instance is not None
        assert isinstance(instance, ExecuteCheckpointRecoveryUseCase)
        assert getattr(instance, "_checkpoint_service", None) is not None

    def test_checkpoint_service_new_method_signatures(self) -> None:
        """新方法签名存在性（inspect.signature 键位断言——6-4 CR1-R3 先例）。"""
        import inspect

        from src.domain.ports.resolver import resolve

        service = resolve("checkpoint_service")
        list_params = set(inspect.signature(service.list_checkpoints).parameters.keys())
        assert list_params == {"plan_id"}, f"list_checkpoints 形参实测={list_params}（bound method 不含 self）"
        execute_params = set(inspect.signature(service.execute_recovery).parameters.keys())
        assert execute_params == {"plan_id", "checkpoint_no", "correction", "mode", "confirmed_by", "created_via"}, (
            f"execute_recovery 形参实测={execute_params}"
        )


@pytest.mark.parametrize("name", PORT_NAMES)
def test_port_spec_version_present(name: str) -> None:
    """三端口 version 元数据在位。"""
    spec = _global_registry.get(name)
    assert spec is not None
    assert spec.version.startswith("v"), f"{name} version 缺失"
