"""Story 6-10 - ConsultantViewPort 端口契约测试（五断言族）.

直系复刻 test_port_contract_analyst_view.py 形态；注入链锚改两依赖注册名
（OD-10：archive_repository/report_repository——两 SCOPED 无混态最简捕获声明）；
签名断言零参（build_consultant_view=={self}——与 6-8/6-9 {self, plan_id} 分立注记）。

Run with:
    poetry run pytest tests/contracts/test_port_contract_consultant_view.py -v
"""

from __future__ import annotations

import inspect

from src.domain.ports.registry import Lifetime, _global_registry
from src.domain.ports.resolver import get_resolver

PORT_NAMES: tuple[str, ...] = ("consultant_view_service", "consultant_view_use_case")


def test_ports_registered() -> None:
    """断言族 1：两注册块在全局注册表可达."""
    for name in PORT_NAMES:
        spec = _global_registry.get(name)
        assert spec is not None, f"端口未注册: {name}"


def test_spec_metadata() -> None:
    """断言族 2：spec 元数据（版本拆分——6-11 v1.1.0：service 升 v1.1.0 品牌段
    读配置面[compatibility 元组含 v1.0.0]，use_case 维持 v1.0.0[签名零变]；
    机械改断言值会致 use_case 假红——拆分钦定 Task 6.6）."""
    expected_versions = {"consultant_view_service": "v1.1.0", "consultant_view_use_case": "v1.0.0"}
    for name in PORT_NAMES:
        spec = _global_registry.get(name)
        assert spec is not None
        assert spec.version == expected_versions[name], f"{name} 版本应为 {expected_versions[name]}"
        assert spec.lifetime == Lifetime.SINGLETON, f"{name} 生命周期应为 SINGLETON"
        assert spec.owner, f"{name} owner 应非空"
        assert "consultant" in spec.tags, f"{name} tags 应含 consultant"
    service_spec = _global_registry.get("consultant_view_service")
    assert service_spec is not None
    assert "v1.0.0" in service_spec.compatibility, "service v1.1.0 应携带 v1.0.0 兼容元组"


def test_service_spec_interface() -> None:
    """断言族 2b：interface 指向应用层端口/用例具体类."""
    from src.application.ports.consultant_view import ConsultantViewPort
    from src.application.use_cases.get_consultant_view import GetConsultantViewUseCase

    service_spec = _global_registry.get("consultant_view_service")
    assert service_spec is not None
    assert service_spec.interface is ConsultantViewPort
    use_case_spec = _global_registry.get("consultant_view_use_case")
    assert use_case_spec is not None
    assert use_case_spec.interface is GetConsultantViewUseCase


def test_lambda_getsource_injection_chain() -> None:
    """断言族 3：lambda 注入链 getsource 锚（三依赖注册名——6-11 v1.1.0 增
    brand_template_repository 第三依赖；原两 SCOPED 捕获+1）."""
    service_spec = _global_registry.get("consultant_view_service")
    assert service_spec is not None
    assert callable(service_spec.impl)
    source = inspect.getsource(service_spec.impl)
    for dependency in ("archive_repository", "report_repository", "brand_template_repository"):
        assert f'"{dependency}"' in source, f"服务 lambda 应 resolve 注入 {dependency}（getsource 锚）"

    use_case_spec = _global_registry.get("consultant_view_use_case")
    assert use_case_spec is not None
    use_case_impl = use_case_spec.impl
    assert callable(use_case_impl)
    use_case_source = inspect.getsource(use_case_impl)
    assert '"consultant_view_service"' in use_case_source, "用例 lambda 应 resolve 注入视图服务"


def test_resolve_reachable_with_dependencies() -> None:
    """断言族 4：resolve 可达 + isinstance + 三依赖注入链非 None（6-11 v1.1.0
    增 brand_template_repository 注入链锚）."""
    from src.application.services.consultant_view_service import ConsultantViewService
    from src.application.use_cases.get_consultant_view import GetConsultantViewUseCase

    resolver = get_resolver()
    service = resolver.resolve("consultant_view_service")
    assert isinstance(service, ConsultantViewService)
    assert service._archive_repository is not None, "注入链：archive_repository 应真实可达"
    assert service._report_repository is not None, "注入链：report_repository 应真实可达"
    assert service._brand_template_repository is not None, "注入链：brand_template_repository 应真实可达（v1.1.0）"
    use_case = resolver.resolve("consultant_view_use_case")
    assert isinstance(use_case, GetConsultantViewUseCase)
    assert getattr(use_case, "_view_service", None) is not None, "注入链：视图服务应真实可达"


def test_method_signature() -> None:
    """断言族 5：方法签名零参（build_consultant_view=={self}——全局视图 OD-1 与 6-8/6-9 keyword-only 分立注记）."""
    from src.application.services.consultant_view_service import ConsultantViewService

    signature = inspect.signature(ConsultantViewService.build_consultant_view)
    assert set(signature.parameters.keys()) == {"self"}, "零参数签名（全局多项目面板本义跨 plan）"
