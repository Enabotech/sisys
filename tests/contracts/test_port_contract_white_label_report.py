"""Story 6-11 - 白标报告基础端口契约测试（五断言族）.

四新注册名（brand_template_repository[SCOPED]/brand_template_service/
save_brand_template_use_case/list_brand_templates_use_case[SINGLETON×3]）+
三处版本升级断言（pdf_renderer/pdf_report_generation_service/
consultant_view_service → v1.1.0+compatibility 元组含 "v1.0.0"）；
GeneratePdfReportUseCase 注册零改动维持 v1.0.0（可选参向后兼容——R3-1）。

pdf 系两处等值断言落本文件承载（R2 钉死：既有 pdf 契约测试仅
startswith("v") 无等值断言——不改既有文件）；SERVICE_INJECTION_DEPENDENCIES
可选增列 brand_template_service 成十依赖（防「九依赖」注释漂移——非红面）。

Run with:
    poetry run pytest tests/contracts/test_port_contract_white_label_report.py -v
"""

from __future__ import annotations

import inspect

from src.domain.ports.registry import Lifetime, _global_registry
from src.domain.ports.resolver import get_resolver

#: 四新注册名（版本/lifetime 权威期望单源）
NEW_PORTS: dict[str, tuple[str, Lifetime]] = {
    "brand_template_repository": ("v1.0.0", Lifetime.SCOPED),
    "brand_template_service": ("v1.0.0", Lifetime.SINGLETON),
    "save_brand_template_use_case": ("v1.0.0", Lifetime.SINGLETON),
    "list_brand_templates_use_case": ("v1.0.0", Lifetime.SINGLETON),
}

#: 三处版本升级（v1.1.0+compatibility 含 v1.0.0——签名演进零破坏运行面）
UPGRADED_PORTS: tuple[str, ...] = (
    "pdf_renderer",
    "pdf_report_generation_service",
    "consultant_view_service",
)


def test_new_ports_registered() -> None:
    """断言族 1：四新注册块在全局注册表可达."""
    for name in NEW_PORTS:
        spec = _global_registry.get(name)
        assert spec is not None, f"端口未注册: {name}"


def test_new_ports_spec_metadata() -> None:
    """断言族 2：spec 元数据（版本/lifetime/owner/tags 含 brand）."""
    for name, (version, lifetime) in NEW_PORTS.items():
        spec = _global_registry.get(name)
        assert spec is not None
        assert spec.version == version, f"{name} 版本应为 {version}"
        assert spec.lifetime == lifetime, f"{name} 生命周期应为 {lifetime}"
        assert spec.owner, f"{name} owner 应非空"
        assert "brand" in spec.tags, f"{name} tags 应含 brand"


def test_new_ports_interface_is_concrete_class() -> None:
    """断言族 2b：interface 指向具体类（端口/用例——契约面钉死）."""
    from src.application.ports.brand_template import BrandTemplateServicePort
    from src.application.use_cases.list_brand_templates import ListBrandTemplatesUseCase
    from src.application.use_cases.save_brand_template import SaveBrandTemplateUseCase
    from src.domain.ports.brand_template_repository import BrandTemplateRepositoryProtocol

    expected_interfaces = {
        "brand_template_repository": BrandTemplateRepositoryProtocol,
        "brand_template_service": BrandTemplateServicePort,
        "save_brand_template_use_case": SaveBrandTemplateUseCase,
        "list_brand_templates_use_case": ListBrandTemplatesUseCase,
    }
    for name, interface in expected_interfaces.items():
        spec = _global_registry.get(name)
        assert spec is not None
        assert spec.interface is interface, f"{name} interface 应为 {interface.__name__}"


def test_lambda_getsource_injection_chain() -> None:
    """断言族 3：lambda 注入链 getsource 锚（依赖注册名带引号字面量）."""
    expected_dependencies: dict[str, tuple[str, ...]] = {
        "brand_template_repository": ("session_factory",),
        "brand_template_service": ("brand_template_repository", "l4_object"),
        "save_brand_template_use_case": ("brand_template_service",),
        "list_brand_templates_use_case": ("brand_template_service",),
    }
    for name, dependencies in expected_dependencies.items():
        spec = _global_registry.get(name)
        assert spec is not None
        assert callable(spec.impl), f"{name} impl 应为可调用 lambda"
        source = inspect.getsource(spec.impl)
        for dependency in dependencies:
            assert f'"{dependency}"' in source, f"{name} lambda 应 resolve 注入 {dependency}（getsource 锚）"


def test_resolve_reachable_with_dependencies() -> None:
    """断言族 4：resolve 可达 + isinstance + 注入链非 None."""
    from src.application.services.brand_template_service import BrandTemplateService
    from src.application.use_cases.list_brand_templates import ListBrandTemplatesUseCase
    from src.application.use_cases.save_brand_template import SaveBrandTemplateUseCase
    from src.domain.ports.brand_template_repository import BrandTemplateRepositoryProtocol
    from src.infrastructure.storage.postgresql.repository.brand_template_repository import (
        PostgreSQLBrandTemplateRepository,
    )

    resolver = get_resolver()
    repository = resolver.resolve("brand_template_repository")
    assert isinstance(repository, PostgreSQLBrandTemplateRepository)
    assert isinstance(repository, BrandTemplateRepositoryProtocol)
    service = resolver.resolve("brand_template_service")
    assert isinstance(service, BrandTemplateService)
    assert service._repository is not None, "注入链：brand_template_repository 应真实可达"
    assert service._l4_object is not None, "注入链：l4_object 应真实可达"
    save_use_case = resolver.resolve("save_brand_template_use_case")
    assert isinstance(save_use_case, SaveBrandTemplateUseCase)
    list_use_case = resolver.resolve("list_brand_templates_use_case")
    assert isinstance(list_use_case, ListBrandTemplatesUseCase)


def test_method_signature() -> None:
    """断言族 5：方法签名（save 四参 keyword-only+logo 可选/get_render_spec 单参/
    list 零参——Task 0.3 冻结签名逐字一致）."""
    from src.application.services.brand_template_service import BrandTemplateService

    save_params = inspect.signature(BrandTemplateService.save_brand_template).parameters
    assert set(save_params.keys()) == {"self", "name", "color_scheme", "font_preset", "logo_path"}
    keyword_only = [p for name, p in save_params.items() if name != "self"]
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in keyword_only)
    assert save_params["logo_path"].default is None

    spec_params = inspect.signature(BrandTemplateService.get_render_spec).parameters
    assert set(spec_params.keys()) == {"self", "template_name"}

    list_params = inspect.signature(BrandTemplateService.list_brand_templates).parameters
    assert set(list_params.keys()) == {"self"}


def test_upgraded_ports_version_and_compatibility() -> None:
    """三处版本升级断言（v1.1.0 等值+compatibility 元组含 v1.0.0——R2 钉死：
    pdf 系两处等值断言落本文件，既有 pdf 契约测试零修改）."""
    for name in UPGRADED_PORTS:
        spec = _global_registry.get(name)
        assert spec is not None, f"端口未注册: {name}"
        assert spec.version == "v1.1.0", f"{name} 版本应为 v1.1.0（实得 {spec.version}）"
        assert "v1.0.0" in spec.compatibility, f"{name} 应携带 v1.0.0 兼容元组"


def test_pdf_use_case_registration_unchanged() -> None:
    """GeneratePdfReportUseCase 注册零改动维持 v1.0.0（可选参向后兼容——R3-1
    裁定的注册面证据）."""
    from src.application.use_cases.generate_pdf_report import GeneratePdfReportUseCase

    spec = _global_registry.get("pdf_report_generation_use_case")
    assert spec is not None
    assert spec.version == "v1.0.0"
    assert spec.interface is GeneratePdfReportUseCase


def test_pdf_service_lambda_ten_dependencies() -> None:
    """pdf_report_generation_service lambda 十依赖注入链（v1.1.0 增
    brand_template_service——SERVICE_INJECTION_DEPENDENCIES 增列防注释漂移）."""
    spec = _global_registry.get("pdf_report_generation_service")
    assert spec is not None
    assert callable(spec.impl)
    source = inspect.getsource(spec.impl)
    for dependency in (
        "chain_of_thought_archive_service",
        "snapshot_repository",
        "report_repository",
        "event_publisher",
        "pdf_renderer",
        "l4_object",
        "l3_vector",
        "document_repository",
        "strategic_archive_service",
        "brand_template_service",
    ):
        assert f'"{dependency}"' in source, f"pdf 服务 lambda 十依赖缺 {dependency}"
