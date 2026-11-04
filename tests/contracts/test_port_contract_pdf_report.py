"""PDF 报告端口契约测试（Story 6-5b——五断言族）。

断言族（6-5a test_port_contract_report_generation 形态模板）：
①注册存在（三端口：pdf_renderer/pdf_report_generation_service/
  pdf_report_generation_use_case——Task 4 组合根三注册块）
②spec 元数据（interface/lifetime/tags/owner）
③v 前缀版本
④getsource 注入面（pdf_report_generation_service 九依赖包含性——
  chain_trace + snapshot + report_repository + event_publisher +
  pdf_renderer + l4_object + l3_vector + document_repository + archive_service）
⑤resolve isinstance（端口实例类型校验）

构造参数默认值断言（collection=="documents"/tenant_id==str(MVP_TENANT_ID)）
归单测（防过度断言——R4T-8 裁定），本契约测试仅断言九依赖注入面。

Run with:
    poetry run pytest tests/contracts/test_port_contract_pdf_report.py -v
"""

import inspect

import pytest

from src.application.ports.pdf_report import (
    PdfRendererPort,
    PdfReportGenerationServicePort,
)
from src.domain.ports.registry import Lifetime, _global_registry
from src.domain.ports.resolver import get_resolver

#: 本 Story 三端口注册名（组合根 === Story 6-5b === 三注册块——Task 4 落地）
PORT_NAMES: tuple[str, ...] = (
    "pdf_renderer",
    "pdf_report_generation_service",
    "pdf_report_generation_use_case",
)

#: pdf_report_generation_service 注入面九依赖（R2 组合律——getsource 包含性断言锚）
SERVICE_INJECTION_DEPENDENCIES: tuple[str, ...] = (
    "chain_of_thought_archive_service",
    "snapshot_repository",
    "report_repository",
    "event_publisher",
    "pdf_renderer",
    "l4_object",
    "l3_vector",
    "document_repository",
    "strategic_archive_service",
)


class TestPdfReportContracts:
    """PDF 报告三端口契约（注册/元数据/版本/注入面/resolve）。"""

    @pytest.mark.parametrize("port_name", PORT_NAMES)
    def test_port_registered(self, port_name: str) -> None:
        """①三端口注册存在（组合根三注册块）。"""
        spec = _global_registry.get(port_name)
        assert spec is not None, f"端口未注册: {port_name}"

    def test_pdf_renderer_spec_metadata(self) -> None:
        """②渲染器 spec 元数据：application 端口 + SINGLETON（无状态）。"""
        spec = _global_registry.get("pdf_renderer")
        assert spec is not None
        assert spec.interface is PdfRendererPort
        assert spec.lifetime == Lifetime.SINGLETON
        assert {"report", "pdf"} <= set(spec.tags)
        assert spec.owner

    def test_pdf_report_generation_service_spec_metadata(self) -> None:
        """②服务 spec 元数据：应用端口 + SINGLETON（无状态并发约束——AC-7）。"""
        spec = _global_registry.get("pdf_report_generation_service")
        assert spec is not None
        assert spec.interface is PdfReportGenerationServicePort
        assert spec.lifetime == Lifetime.SINGLETON
        assert {"report", "pdf"} <= set(spec.tags)
        assert spec.owner

    def test_use_case_spec_metadata(self) -> None:
        """②用例 spec 元数据（具体类 interface 先例——6-5a 形态）。"""
        from src.application.use_cases.generate_pdf_report import GeneratePdfReportUseCase

        spec = _global_registry.get("pdf_report_generation_use_case")
        assert spec is not None
        assert spec.interface is GeneratePdfReportUseCase  # 具体类（无独立 Protocol）
        assert spec.lifetime == Lifetime.SINGLETON
        assert "use_case" in spec.tags
        assert spec.owner

    @pytest.mark.parametrize("port_name", PORT_NAMES)
    def test_port_spec_version_prefix(self, port_name: str) -> None:
        """③版本 v 前缀（PortSpec 版本纪律）。"""
        spec = _global_registry.get(port_name)
        assert spec is not None
        assert spec.version.startswith("v")

    def test_service_getsource_injection_surface(self) -> None:
        """④getsource 注入面：九依赖 resolve 调用锚定（R2 组合律实证——注释免疫）。"""
        spec = _global_registry.get("pdf_report_generation_service")
        assert spec is not None
        assert callable(spec.impl), "impl 必须为可调用 lambda（str 延迟 impl 无源码面）"
        source = inspect.getsource(spec.impl)
        for dependency in SERVICE_INJECTION_DEPENDENCIES:
            resolve_call = f'resolver.resolve("{dependency}")'
            assert resolve_call in source, f"服务注入面缺失 resolve 调用: {resolve_call}"

    def test_resolve_renderer_isinstance(self) -> None:
        """⑤resolve isinstance：渲染器实例实现应用端口（reportlab 唯一宿主）。"""
        instance = get_resolver().resolve("pdf_renderer")
        assert isinstance(instance, PdfRendererPort)

    def test_resolve_service_isinstance(self) -> None:
        """⑤resolve isinstance：服务实例实现应用端口。"""
        instance = get_resolver().resolve("pdf_report_generation_service")
        assert isinstance(instance, PdfReportGenerationServicePort)

    def test_resolve_use_case_isinstance(self) -> None:
        """⑤resolve isinstance：用例实例（具体类直判）。"""
        from src.application.use_cases.generate_pdf_report import GeneratePdfReportUseCase

        instance = get_resolver().resolve("pdf_report_generation_use_case")
        assert isinstance(instance, GeneratePdfReportUseCase)

    def test_evidence_bucket_type_matches_code_single_source(self) -> None:
        """桶常量等值钉：EVIDENCE_BUCKET_TYPE 与代码单源 L4_BUCKET_TYPE 同值（CR1-F16）。

        两常量分属端口契约与战略档案服务（值级镜像非 import 单源——ports
        引 service 是更差依赖方向）；漂移即「证据流一桶贯通」静默断裂，
        等值锚使漂移必红。
        """
        from src.application.ports.pdf_report import EVIDENCE_BUCKET_TYPE
        from src.application.services.strategic_archive_service import StrategicArchiveService

        assert EVIDENCE_BUCKET_TYPE == StrategicArchiveService.L4_BUCKET_TYPE
