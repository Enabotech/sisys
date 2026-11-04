"""report 子域异常双类单元测试（Story 6-5a Task 1 循环 C）。

覆盖面：
- ReportGenerationError（EXCEPTION_490，404 语义）：构造/context 暴露/
  message 覆写/cause 链/to_dict/继承链
- ReportStorageError（EXCEPTION_491，500 语义）：layer 二元值域 {l0,l2}
  （自有元组——禁复用 284 常量）/非法 layer 抛 242 守卫/layer 属性暴露
- 四处登记联动：_code_ranges 开 report 段 (490,499)/_CLASS_TO_SUBDOMAIN
  双类注册/__init__ 导出/EXCEPTION_HTTP_MAP 值级（490→404、491→500）

Run with:
    poetry run pytest tests/unit/domain/exceptions/test_report_exceptions.py -v
"""

import pytest
from fastapi import status

from src.domain.exceptions import (
    EntityValidationError,
    PdfRenderingError,
    ReportEvidenceStorageError,
    ReportGenerationError,
    ReportStorageError,
)
from src.domain.exceptions._code_ranges import CODE_RANGES, get_subdomain_for_class
from src.domain.exceptions.base_exceptions import DomainError
from src.domain.exceptions.business_exceptions import BusinessException
from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP


class TestReportGenerationError:
    """ReportGenerationError（490——数据源全缺，404 语义）。"""

    def test_code_and_default_message(self) -> None:
        """code=EXCEPTION_490 + message 钦定可观测事实口径。"""
        error = ReportGenerationError(plan_id="plan-abc")
        assert error.code == "EXCEPTION_490"
        assert error.message == "该 plan_id 无思维链归档记录，无法生成报告"

    def test_context_exposes_plan_id(self) -> None:
        """context 暴露领域上下文 plan_id（调用方可观测）。"""
        error = ReportGenerationError(plan_id="plan-abc")
        assert error.context["plan_id"] == "plan-abc"

    def test_message_override(self) -> None:
        """message 覆写参数（缺省回落类静态文案）。"""
        error = ReportGenerationError(plan_id="plan-abc", message="自定义消息")
        assert error.message == "自定义消息"

    def test_context_extra_merge(self) -> None:
        """context_extra 合并进 context（家族形态对齐 480）。"""
        error = ReportGenerationError(plan_id="plan-abc", context_extra={"source": "cli"})
        assert error.context["plan_id"] == "plan-abc"
        assert error.context["source"] == "cli"

    def test_cause_chain(self) -> None:
        """cause 链保留（底层异常可追溯——显式 cause 属性，家族形态对齐 481 先例）。"""
        root = RuntimeError("底层失败")
        error = ReportGenerationError(plan_id="plan-abc", cause=root)
        assert error.cause is root

    def test_to_dict_contains_code_and_plan_id(self) -> None:
        """to_dict 序列化含 code 与 plan_id 上下文。"""
        error = ReportGenerationError(plan_id="plan-abc")
        payload = error.to_dict()
        assert payload["code"] == "EXCEPTION_490"
        assert payload["context"]["plan_id"] == "plan-abc"

    def test_inheritance_chain(self) -> None:
        """继承 BusinessException（HTTP 映射回退面——business 段）。"""
        error = ReportGenerationError(plan_id="plan-abc")
        assert isinstance(error, BusinessException)
        assert isinstance(error, DomainError)


class TestReportStorageError:
    """ReportStorageError（491——报告持久化失败，500 语义）。"""

    def test_code_and_layer_context(self) -> None:
        """code=EXCEPTION_491 + context 暴露 layer。"""
        error = ReportStorageError(layer="l0")
        assert error.code == "EXCEPTION_491"
        assert error.context["layer"] == "l0"
        assert error.layer == "l0"

    def test_valid_layers_l0_and_l2(self) -> None:
        """layer 二元值域恰 {l0, l2}（自有元组——L0 文件/L2 元数据行两形态）。"""
        assert ReportStorageError._VALID_LAYERS == ("l0", "l2")
        for layer in ("l0", "l2"):
            error = ReportStorageError(layer=layer)
            assert error.layer == layer

    def test_invalid_layer_raises_242(self) -> None:
        """非法 layer（284 值域 l4 亦拒）抛 EntityValidationError 242 守卫。"""
        with pytest.raises(EntityValidationError) as exc_info:
            ReportStorageError(layer="l4")
        assert exc_info.value.code == "EXCEPTION_242"

    def test_empty_layer_raises_242(self) -> None:
        """空 layer 抛 242（值域守卫先于构造）。"""
        with pytest.raises(EntityValidationError):
            ReportStorageError(layer="")

    def test_message_override_and_cause(self) -> None:
        """message 覆写 + cause 链（显式 cause 属性——家族形态对齐 284/481 先例）。"""
        root = OSError("磁盘写失败")
        error = ReportStorageError(layer="l0", message="L0 落盘失败", cause=root)
        assert error.message == "L0 落盘失败"
        assert error.cause is root

    def test_default_message_contains_layer(self) -> None:
        """缺省 message 含 layer 语境（可观测面）。"""
        error = ReportStorageError(layer="l2")
        assert "l2" in error.message


class TestPdfRenderingError:
    """PdfRenderingError（492——PDF 渲染失败，500 语义，Story 6-5b Task 1）。"""

    def test_code_and_default_message(self) -> None:
        """code=EXCEPTION_492 + message 钦定口径。"""
        error = PdfRenderingError(plan_id="plan-pdf")
        assert error.code == "EXCEPTION_492"
        assert error.message == "PDF 报告渲染失败"

    def test_context_exposes_plan_id(self) -> None:
        """context 暴露 plan_id（构造器领域参在前——同构 490 形态）。"""
        error = PdfRenderingError(plan_id="plan-pdf")
        assert error.context["plan_id"] == "plan-pdf"

    def test_message_override(self) -> None:
        """message 覆写参数。"""
        error = PdfRenderingError(plan_id="plan-pdf", message="STSong-Light 注册失败")
        assert error.message == "STSong-Light 注册失败"

    def test_context_extra_merge(self) -> None:
        """context_extra 合并进 context（家族形态对齐 490）。"""
        error = PdfRenderingError(plan_id="plan-pdf", context_extra={"renderer": "reportlab"})
        assert error.context["plan_id"] == "plan-pdf"
        assert error.context["renderer"] == "reportlab"

    def test_cause_chain(self) -> None:
        """cause 链保留（reportlab 原生异常领域包装——492 触发主形态）。"""
        root = ValueError("format not resolved, probably missing URL scheme or undefined destination")
        error = PdfRenderingError(plan_id="plan-pdf", cause=root)
        assert error.cause is root

    def test_to_dict_contains_code_and_plan_id(self) -> None:
        """to_dict 序列化含 code 与 plan_id。"""
        error = PdfRenderingError(plan_id="plan-pdf")
        payload = error.to_dict()
        assert payload["code"] == "EXCEPTION_492"
        assert payload["context"]["plan_id"] == "plan-pdf"

    def test_inheritance_chain(self) -> None:
        """继承 BusinessException（business 段 500 语义）。"""
        error = PdfRenderingError(plan_id="plan-pdf")
        assert isinstance(error, BusinessException)
        assert isinstance(error, DomainError)


class TestReportEvidenceStorageError:
    """ReportEvidenceStorageError（493——L4 证据对象归档失败，500 语义，Story 6-5b Task 1）。"""

    def test_code_and_default_message(self) -> None:
        """code=EXCEPTION_493 + message 钦定口径。"""
        error = ReportEvidenceStorageError(plan_id="plan-pdf")
        assert error.code == "EXCEPTION_493"
        assert error.message == "PDF 报告证据归档失败"

    def test_context_exposes_plan_id(self) -> None:
        """context 暴露 plan_id。"""
        error = ReportEvidenceStorageError(plan_id="plan-pdf")
        assert error.context["plan_id"] == "plan-pdf"

    def test_message_override_and_cause(self) -> None:
        """message 覆写 + cause 链（L4 archive 异常包装——493 触发主形态）。"""
        root = OSError("MinIO 不可达")
        error = ReportEvidenceStorageError(plan_id="plan-pdf", message="WORM 归档失败", cause=root)
        assert error.message == "WORM 归档失败"
        assert error.cause is root

    def test_to_dict_contains_code_and_plan_id(self) -> None:
        """to_dict 序列化含 code 与 plan_id。"""
        error = ReportEvidenceStorageError(plan_id="plan-pdf")
        payload = error.to_dict()
        assert payload["code"] == "EXCEPTION_493"
        assert payload["context"]["plan_id"] == "plan-pdf"

    def test_inheritance_chain(self) -> None:
        """继承 BusinessException。"""
        error = ReportEvidenceStorageError(plan_id="plan-pdf")
        assert isinstance(error, BusinessException)
        assert isinstance(error, DomainError)


class TestReportExceptionRegistration:
    """四处登记联动（码段/子域/导出/HTTP 映射）。"""

    def test_code_ranges_report_segment(self) -> None:
        """CODE_RANGES 含 report 段 (490, 499)（独立段——planning 485-489 预留不可占）。"""
        assert CODE_RANGES.get("report") == (490, 499)

    def test_report_segment_no_overlap_with_planning(self) -> None:
        """report 段与 planning 段 (480,489) 区间不相交。"""
        report_low, report_high = CODE_RANGES["report"]
        planning_low, planning_high = CODE_RANGES["planning"]
        assert report_low > planning_high or report_high < planning_low

    def test_class_to_subdomain_registered(self) -> None:
        """四类注册到 report 子域（test_code_ranges Rule 1 联动——6-5b 增 492/493）。"""
        assert get_subdomain_for_class("ReportGenerationError") == "report"
        assert get_subdomain_for_class("ReportStorageError") == "report"
        assert get_subdomain_for_class("PdfRenderingError") == "report"
        assert get_subdomain_for_class("ReportEvidenceStorageError") == "report"

    def test_subdomain_range_covers_codes(self) -> None:
        """report 段范围覆盖 490-493（Rule 5 联动——∈ (490,499)）。"""
        low, high = CODE_RANGES["report"]
        for code in (490, 491, 492, 493):
            assert low <= code <= high

    def test_http_map_values(self) -> None:
        """EXCEPTION_HTTP_MAP 值级：490→404 / 491→500 / 492→500 / 493→500。"""
        assert EXCEPTION_HTTP_MAP[ReportGenerationError] == status.HTTP_404_NOT_FOUND
        assert EXCEPTION_HTTP_MAP[ReportStorageError] == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert EXCEPTION_HTTP_MAP[PdfRenderingError] == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert EXCEPTION_HTTP_MAP[ReportEvidenceStorageError] == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_exported_in_domain_all(self) -> None:
        """四类经 src.domain.exceptions 导出（test_error_code_uniqueness 自动发现面）。"""
        from src.domain import exceptions as exc_module

        assert "ReportGenerationError" in exc_module.__all__
        assert "ReportStorageError" in exc_module.__all__
        assert "PdfRenderingError" in exc_module.__all__
        assert "ReportEvidenceStorageError" in exc_module.__all__

    def test_codes_distinct(self) -> None:
        """四码互异（编码唯一性面——uniqueness 测试自动覆盖）。"""
        codes = {
            ReportGenerationError.code,
            ReportStorageError.code,
            PdfRenderingError.code,
            ReportEvidenceStorageError.code,
        }
        assert len(codes) == 4
