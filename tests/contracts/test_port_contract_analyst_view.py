"""Story 6-9 - AnalystViewPort 端口契约测试（五断言族）.

直系复刻 test_port_contract_executive_view.py 形态；注入链锚改三依赖注册名
（OD-11：skill_selector/snapshot_repository/traceability_tree_service——两
SINGLETON+一 SCOPED 混态捕获声明）。

Run with:
    poetry run pytest tests/contracts/test_port_contract_analyst_view.py -v
"""

from __future__ import annotations

import inspect

from src.domain.ports.registry import Lifetime, _global_registry
from src.domain.ports.resolver import get_resolver

PORT_NAMES: tuple[str, ...] = ("analyst_view_service", "analyst_view_use_case")


def test_ports_registered() -> None:
    """断言族 1：两注册块在全局注册表可达."""
    for name in PORT_NAMES:
        spec = _global_registry.get(name)
        assert spec is not None, f"端口未注册: {name}"


def test_spec_metadata() -> None:
    """断言族 2：spec 元数据（v1.0.0/SINGLETON/owner/tags）."""
    for name in PORT_NAMES:
        spec = _global_registry.get(name)
        assert spec is not None
        assert spec.version == "v1.0.0", f"{name} 版本应为 v1.0.0"
        assert spec.lifetime == Lifetime.SINGLETON, f"{name} 生命周期应为 SINGLETON"
        assert spec.owner, f"{name} owner 应非空"
        assert "analyst" in spec.tags, f"{name} tags 应含 analyst"


def test_service_spec_interface() -> None:
    """断言族 2b：interface 指向应用层端口/用例具体类."""
    from src.application.ports.analyst_view import AnalystViewPort
    from src.application.use_cases.get_analyst_view import GetAnalystViewUseCase

    service_spec = _global_registry.get("analyst_view_service")
    assert service_spec is not None
    assert service_spec.interface is AnalystViewPort
    use_case_spec = _global_registry.get("analyst_view_use_case")
    assert use_case_spec is not None
    assert use_case_spec.interface is GetAnalystViewUseCase


def test_lambda_getsource_injection_chain() -> None:
    """断言族 3：lambda 注入链 getsource 锚（三依赖注册名——OD-11）."""
    service_spec = _global_registry.get("analyst_view_service")
    assert service_spec is not None
    assert callable(service_spec.impl)
    source = inspect.getsource(service_spec.impl)
    for dependency in ("skill_selector", "snapshot_repository", "traceability_tree_service"):
        assert f'"{dependency}"' in source, f"服务 lambda 应 resolve 注入 {dependency}（getsource 锚）"

    use_case_spec = _global_registry.get("analyst_view_use_case")
    assert use_case_spec is not None
    use_case_impl = use_case_spec.impl
    assert callable(use_case_impl)
    use_case_source = inspect.getsource(use_case_impl)
    assert '"analyst_view_service"' in use_case_source, "用例 lambda 应 resolve 注入视图服务"


def test_resolve_reachable_with_dependencies() -> None:
    """断言族 4：resolve 可达 + isinstance + 三依赖注入链非 None."""
    from src.application.services.analyst_view_service import AnalystViewService
    from src.application.use_cases.get_analyst_view import GetAnalystViewUseCase

    resolver = get_resolver()
    service = resolver.resolve("analyst_view_service")
    assert isinstance(service, AnalystViewService)
    assert service._skill_selector is not None, "注入链：skill_selector 应真实可达"
    assert service._snapshot_repository is not None, "注入链：snapshot_repository 应真实可达"
    assert service._traceability_tree_service is not None, "注入链：traceability_tree_service 应真实可达"
    use_case = resolver.resolve("analyst_view_use_case")
    assert isinstance(use_case, GetAnalystViewUseCase)
    assert getattr(use_case, "_view_service", None) is not None, "注入链：视图服务应真实可达"


def test_method_signature() -> None:
    """断言族 5：方法签名 keyword-only（6-7/6-8 签名风格——PEP 563 字符串注解形态）."""
    from src.application.services.analyst_view_service import AnalystViewService

    signature = inspect.signature(AnalystViewService.build_analyst_view)
    assert set(signature.parameters.keys()) == {"self", "plan_id"}
    assert signature.parameters["plan_id"].kind is inspect.Parameter.KEYWORD_ONLY
    assert str(signature.parameters["plan_id"].annotation) == "str"
