"""Story 6-7 端口契约测试（五断言族——test_port_contract_checkpoint 样板）

覆盖组合根两新注册块：traceability_tree_service（SINGLETON + lambda 三依赖注入
+ env collection/tenant 参数）/ traceability_tree_use_case（SINGLETON 透传）。
既有注册行零删改（Task 4 diff 审计承载）。
"""

from __future__ import annotations

import inspect

import pytest

from src.domain.ports.registry import Lifetime, _global_registry
from src.domain.ports.resolver import get_resolver

PORT_NAMES: tuple[str, ...] = ("traceability_tree_service", "traceability_tree_use_case")


def test_ports_registered() -> None:
    """断言族 1：两注册块在全局注册表可达."""
    for name in PORT_NAMES:
        spec = _global_registry.get(name)
        assert spec is not None, f"端口未注册: {name}"


@pytest.mark.parametrize("name", PORT_NAMES)
def test_spec_metadata(name: str) -> None:
    """断言族 2：spec 元数据（version v1.0.0 / SINGLETON / owner / tags 含 traceability）."""
    spec = _global_registry.get(name)
    assert spec is not None
    assert spec.version == "v1.0.0", f"{name} 版本应为 v1.0.0，实际 {spec.version}"
    assert spec.lifetime == Lifetime.SINGLETON, f"{name} 应 SINGLETON（无状态聚合读），实际 {spec.lifetime}"
    assert spec.owner, f"{name} owner 应非空"
    assert "traceability" in spec.tags, f"{name} tags 应含 traceability，实际 {spec.tags}"


def test_service_spec_interface() -> None:
    """断言族 2b：服务注册 interface 指向 TraceabilityTreePort Protocol."""
    from src.application.ports.traceability_tree import TraceabilityTreePort

    spec = _global_registry.get("traceability_tree_service")
    assert spec is not None
    assert spec.interface is TraceabilityTreePort


def test_lambda_getsource_injection_chain() -> None:
    """断言族 3：lambda 注入链（三依赖 resolve 调用锚——getsource 形态）."""
    spec = _global_registry.get("traceability_tree_service")
    assert spec is not None
    assert callable(spec.impl)
    source = inspect.getsource(spec.impl)
    for dependency in ("strategic_archive_service", "l3_vector", "document_repository"):
        assert f'"{dependency}"' in source, f"服务 lambda 应 resolve 注入 {dependency}（getsource 锚）"
    assert "BLM_SEARCH_COLLECTION" in source, "服务 lambda 应 env 传导 search_collection（组合根单源）"

    use_case_spec = _global_registry.get("traceability_tree_use_case")
    assert use_case_spec is not None
    use_case_impl = use_case_spec.impl
    assert callable(use_case_impl), "用例 impl 应为可调用（lambda 注册形态）"
    use_case_source = inspect.getsource(use_case_impl)
    assert '"traceability_tree_service"' in use_case_source, "用例 lambda 应 resolve 注入树服务"


def test_resolve_reachable_with_injection() -> None:
    """断言族 4：resolve 可达 + isinstance + 注入链非 None."""
    from src.application.services.traceability_tree_service import TraceabilityTreeService
    from src.application.use_cases.get_traceability_tree import GetTraceabilityTreeUseCase

    resolver = get_resolver()
    service = resolver.resolve("traceability_tree_service")
    assert isinstance(service, TraceabilityTreeService)
    assert service._strategic_archive_service is not None, "注入链：strategic_archive_service 应真实可达"
    assert service._l3_vector is not None, "注入链：l3_vector 应真实可达"
    assert service._document_repository is not None, "注入链：document_repository 应真实可达"

    use_case = resolver.resolve("traceability_tree_use_case")
    assert isinstance(use_case, GetTraceabilityTreeUseCase)
    assert getattr(use_case, "_tree_service", None) is not None, "注入链：tree_service 应非 None"


def test_method_signature() -> None:
    """断言族 5：新方法签名键位（类级签名——零实例构造；keyword-only plan_id/depth + 默认 4）."""
    from src.application.services.traceability_tree_service import TraceabilityTreeService

    signature = inspect.signature(TraceabilityTreeService.build_trace_tree)
    assert set(signature.parameters.keys()) == {"self", "plan_id", "depth"}, f"方法键位: {set(signature.parameters.keys())}"
    assert signature.parameters["depth"].default == 4
    assert signature.parameters["plan_id"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["depth"].kind is inspect.Parameter.KEYWORD_ONLY
