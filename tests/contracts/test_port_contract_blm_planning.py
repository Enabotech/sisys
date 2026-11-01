"""Story 6-1 — BLM 规划端口契约测试（组合根注册族 + 兼容性）。

Task 4 循环 A 载体（Task 0 编写规格 / Task 4 转绿——绿点与组合根注册同
Task 闭合，5-12 R1-19 教训）：三端口注册可达 + spec 构造真实实例 +
runtime_checkable 兼容 + agent_engine lambda 注入链。

形态对齐 test_port_contract_agent_checkpoint.py（11 维度单测方法）。

Run with:
    poetry run pytest tests/contracts/test_port_contract_blm_planning.py -v
"""

from __future__ import annotations

import pytest

from src.domain.ports.registry import _global_registry

PORT_NAMES = ("blm_planning_service", "blm_planning_use_case", "blm_planning_status_use_case")


class TestBlmPlanningPortContracts:
    """BLM 规划三端口契约（注册/元数据/构造/兼容）。"""

    def test_ports_registered(self) -> None:
        """三端口注册可达（bootstrap 后 registry 可查）。"""
        for name in PORT_NAMES:
            spec = _global_registry.get(name)
            assert spec is not None, f"端口 {name} 未注册"

    def test_blm_planning_service_spec_metadata(self) -> None:
        """blm_planning_service 元数据（interface/lifetime/tags/owner 齐备）。"""
        from src.application.ports.blm_planning import BlmPlanningServicePort
        from src.domain.ports.registry import Lifetime

        spec = _global_registry.get("blm_planning_service")
        assert spec is not None
        assert spec.interface is BlmPlanningServicePort
        assert spec.lifetime == Lifetime.SINGLETON
        assert "blm" in spec.tags or "planning" in spec.tags
        assert spec.owner

    def test_use_case_specs_metadata(self) -> None:
        """两用例端口元数据（usecase 标签 + SINGLETON）。"""
        from src.domain.ports.registry import Lifetime

        for name in ("blm_planning_use_case", "blm_planning_status_use_case"):
            spec = _global_registry.get(name)
            assert spec is not None
            assert spec.lifetime == Lifetime.SINGLETON
            assert any("usecase" in tag for tag in spec.tags), f"{name} 缺 usecase 标签"

    def test_blm_planning_service_resolvable(self) -> None:
        """resolve 可达 + 注入链非 None + 端口兼容（真实构造）。"""
        from src.application.ports.blm_planning import BlmPlanningServicePort
        from src.domain.ports.resolver import resolve

        instance = resolve("blm_planning_service")
        assert instance is not None
        assert isinstance(instance, BlmPlanningServicePort)

    def test_use_case_resolvable(self) -> None:
        """RunBlmPlanningUseCase resolve 可达（真实构造）。"""
        from src.application.use_cases.run_blm_planning import RunBlmPlanningUseCase
        from src.domain.ports.resolver import resolve

        instance = resolve("blm_planning_use_case")
        assert isinstance(instance, RunBlmPlanningUseCase)

    def test_status_use_case_resolvable(self) -> None:
        """GetBlmPlanningStatusUseCase resolve 可达。"""
        from src.application.use_cases.get_blm_planning_status import GetBlmPlanningStatusUseCase
        from src.domain.ports.resolver import resolve

        instance = resolve("blm_planning_status_use_case")
        assert isinstance(instance, GetBlmPlanningStatusUseCase)

    def test_agent_engine_lambda_injects_blm_service(self) -> None:
        """agent_engine lambda 增 blm_planning_service 注入（引擎构造签名消费）。"""
        import inspect

        from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine

        signature = inspect.signature(LangGraphEngine.__init__)
        assert "blm_planning_service" in signature.parameters, (
            "LangGraphEngine 构造器缺 blm_planning_service 注入位（Task 0.6①）"
        )

    def test_search_collection_configurable(self) -> None:
        """检索 collection 经组合根可配置（组合根 lambda 真实注入 collection 实参——R1-9⑥）。"""
        import inspect

        spec = _global_registry.get("blm_planning_service")
        assert spec is not None
        assert callable(spec.impl), "impl 应为 lambda 工厂（resolver 注入构造）"
        # lambda 源码含 search_collection 实参注入（组合根装配面——空壳断言改真断言）
        source = inspect.getsource(spec.impl)
        assert "search_collection" in source, "组合根 lambda 未注入 search_collection（collection 装配面断裂）"


@pytest.mark.parametrize("name", PORT_NAMES)
def test_port_spec_version_present(name: str) -> None:
    """三端口 version 元数据在位。"""
    spec = _global_registry.get(name)
    assert spec is not None
    assert spec.version.startswith("v"), f"{name} version 缺失"
