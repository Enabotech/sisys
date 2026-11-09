"""报告生成端口契约测试（Story 6-5a——五断言族）。

断言族（6-4 test_port_contract_chain_of_thought 形态模板）：
①注册存在（三端口：report_generation_service/report_generation_use_case/
  report_repository——Task 3 组合根三注册块）
②spec 元数据（interface/lifetime/tags/owner）
③v 前缀版本
④getsource 注入面（report_generation_service 五依赖 resolve 调用锚定——chain_trace +
  snapshot + l0 + report_repository + event_publisher）
⑤resolve isinstance（端口实例类型校验）

Run with:
    poetry run pytest tests/contracts/test_port_contract_report_generation.py -v
"""

import inspect

import pytest

from src.application.ports.report_generation import ReportGenerationServicePort
from src.domain.ports.registry import Lifetime, _global_registry
from src.domain.ports.report_repository import ReportRepositoryProtocol
from src.domain.ports.resolver import get_resolver

#: 本 Story 三端口注册名（组合根三注册块——Task 3 落地）
PORT_NAMES: tuple[str, ...] = (
    "report_repository",
    "report_generation_service",
    "report_generation_use_case",
)

#: report_generation_service 注入面五依赖（R2 组合律——getsource 包含性断言锚）
SERVICE_INJECTION_DEPENDENCIES: tuple[str, ...] = (
    "chain_of_thought_archive_service",
    "snapshot_repository",
    "l0_storage",
    "report_repository",
    "event_publisher",
)


class TestReportGenerationContracts:
    """报告生成三端口契约（注册/元数据/版本/注入面/resolve）。"""

    @pytest.mark.parametrize("port_name", PORT_NAMES)
    def test_port_registered(self, port_name: str) -> None:
        """①三端口注册存在（组合根三注册块）。"""
        spec = _global_registry.get(port_name)
        assert spec is not None, f"端口未注册: {port_name}"

    def test_report_generation_service_spec_metadata(self) -> None:
        """②服务 spec 元数据：interface=SINGLETON 应用端口 + tags 子集断言。"""
        spec = _global_registry.get("report_generation_service")
        assert spec is not None
        assert spec.interface is ReportGenerationServicePort
        assert spec.lifetime == Lifetime.SINGLETON
        assert {"report", "markdown"} <= set(spec.tags)
        assert spec.owner

    def test_report_repository_spec_metadata(self) -> None:
        """②仓储 spec 元数据：interface=R1 端口 + SCOPED + tags（CR2-F4 补 tags 断言）。"""
        spec = _global_registry.get("report_repository")
        assert spec is not None
        assert spec.interface is ReportRepositoryProtocol
        assert spec.lifetime == Lifetime.SCOPED
        assert "report" in spec.tags and "gateway" in spec.tags  # 组合根 :3360 三 tags
        assert spec.owner

    def test_use_case_spec_metadata(self) -> None:
        """②用例 spec 元数据（CR2-F4 补——具体类 interface 先例：agent_instantiation 形态）。"""
        from src.application.use_cases.generate_markdown_report import GenerateMarkdownReportUseCase

        spec = _global_registry.get("report_generation_use_case")
        assert spec is not None
        assert spec.interface is GenerateMarkdownReportUseCase  # 具体类（无独立 Protocol）
        assert spec.lifetime == Lifetime.SINGLETON
        assert "use_case" in spec.tags
        assert spec.owner

    def test_resolve_use_case_isinstance(self) -> None:
        """⑤resolve isinstance：用例实例（CR2-F4 补——具体类直判）。"""
        from src.application.use_cases.generate_markdown_report import GenerateMarkdownReportUseCase

        instance = get_resolver().resolve("report_generation_use_case")
        assert isinstance(instance, GenerateMarkdownReportUseCase)

    @pytest.mark.parametrize("port_name", PORT_NAMES)
    def test_port_spec_version_prefix(self, port_name: str) -> None:
        """③版本 v 前缀（PortSpec 版本纪律）。"""
        spec = _global_registry.get(port_name)
        assert spec is not None
        assert spec.version.startswith("v")

    def test_service_getsource_injection_surface(self) -> None:
        """④getsource 注入面：五依赖 resolve 调用锚定（R2 组合律实证——注释免疫，依赖名仅存注释不通过）。"""
        spec = _global_registry.get("report_generation_service")
        assert spec is not None
        assert callable(spec.impl), "impl 必须为可调用 lambda（str 延迟 impl 无源码面）"
        source = inspect.getsource(spec.impl)
        for dependency in SERVICE_INJECTION_DEPENDENCIES:
            resolve_call = f'resolver.resolve("{dependency}")'
            assert resolve_call in source, f"服务注入面缺失 resolve 调用: {resolve_call}"

    def test_resolve_service_isinstance(self) -> None:
        """⑤resolve isinstance：服务实例实现应用端口。"""
        instance = get_resolver().resolve("report_generation_service")
        assert isinstance(instance, ReportGenerationServicePort)

    def test_resolve_repository_isinstance(self) -> None:
        """⑤resolve isinstance：仓储实例实现 R1 端口。"""
        instance = get_resolver().resolve("report_repository")
        assert isinstance(instance, ReportRepositoryProtocol)
