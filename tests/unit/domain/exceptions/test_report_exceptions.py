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
    BrandTemplateStorageError,
    BrandTemplateValidationError,
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


class TestBrandTemplateValidationError:
    """BrandTemplateValidationError（494——品牌模板校验伞形，400 语义，Story 6-11 Task 1）。

    七形态 = 494 全触发面（非法 color_scheme key/非法 font_preset key/Logo magic
    bytes 非法/超 2MB/路径不存在/模板不存在/参数组合非法——name 空值/超长归 242
    实体守卫形态非 494）。
    """

    def test_code_and_default_message(self) -> None:
        """code=EXCEPTION_494 + message 钦定口径。"""
        error = BrandTemplateValidationError(field="color_scheme")
        assert error.code == "EXCEPTION_494"
        assert error.message == "品牌模板校验失败"

    def test_context_exposes_field(self) -> None:
        """context 暴露 field（七形态区分键——message+context.field 组合可观测）。"""
        error = BrandTemplateValidationError(field="font_preset")
        assert error.context["field"] == "font_preset"

    def test_message_override_and_context_extra(self) -> None:
        """message 覆写（合法预设键清单入消息——调用方可理解性）+context_extra
        合并（template_name/reason 领域上下文）。"""
        error = BrandTemplateValidationError(
            field="color_scheme",
            message="color_scheme 必须为预设键之一（corporate-blue/graphite/burgundy）",
            context_extra={"template_name": "商务蓝模板", "reason": "值域外"},
        )
        assert "corporate-blue" in error.message
        assert error.context["template_name"] == "商务蓝模板"
        assert error.context["reason"] == "值域外"

    def test_cause_chain_and_to_dict(self) -> None:
        """cause 链保留 + to_dict 序列化含 code 与 field。"""
        root = OSError("logo 文件不可读")
        error = BrandTemplateValidationError(field="logo_path", message="Logo 文件不可读", cause=root)
        assert error.cause is root
        payload = error.to_dict()
        assert payload["code"] == "EXCEPTION_494"
        assert payload["context"]["field"] == "logo_path"

    def test_inheritance_chain(self) -> None:
        """继承 BusinessException（400 语义——与基类兜底一致但族惯例全显式注册）。"""
        error = BrandTemplateValidationError(field="color_scheme")
        assert isinstance(error, BusinessException)
        assert isinstance(error, DomainError)


class TestBrandTemplateStorageError:
    """BrandTemplateStorageError（495——品牌配置持久化失败，500 语义，Story 6-11 Task 1）。

    与 491 ReportStorageError 同族分立：彼为报告产物持久化（二元 {l0,l2}），
    此为品牌配置持久化（二元 {l2,l4}——brand_templates PG 读写/L4 logo 存取）。
    """

    def test_code_and_layer_context(self) -> None:
        """code=EXCEPTION_495 + context 暴露 layer。"""
        error = BrandTemplateStorageError(layer="l2")
        assert error.code == "EXCEPTION_495"
        assert error.context["layer"] == "l2"
        assert error.layer == "l2"

    def test_valid_layers_l2_and_l4(self) -> None:
        """layer 二元值域恰 {l2, l4}（PG 读写/L4 logo 存取——与 491 {l0,l2} 分立）。"""
        assert BrandTemplateStorageError._VALID_LAYERS == ("l2", "l4")
        for layer in ("l2", "l4"):
            error = BrandTemplateStorageError(layer=layer)
            assert error.layer == layer

    def test_invalid_layer_raises_242(self) -> None:
        """非法 layer（491 值域 l0 亦拒——值域分立双向判别）抛 242 守卫。"""
        with pytest.raises(EntityValidationError) as exc_info:
            BrandTemplateStorageError(layer="l0")
        assert exc_info.value.code == "EXCEPTION_242"

    def test_default_message_contains_layer(self) -> None:
        """缺省 message 含 layer 语境（可观测面）。"""
        error = BrandTemplateStorageError(layer="l4")
        assert "l4" in error.message

    def test_message_override_and_cause(self) -> None:
        """message 覆写 + cause 链（存储驱动异常包装——495 触发主形态）。"""
        root = RuntimeError("MinIO 不可达")
        error = BrandTemplateStorageError(layer="l4", message="Logo 对象上传失败", cause=root)
        assert error.message == "Logo 对象上传失败"
        assert error.cause is root

    def test_to_dict_and_inheritance(self) -> None:
        """to_dict 序列化 + 继承 BusinessException（500 语义——显式注册
        HTTP_MAP 是族纪律：BusinessException 基类兜底 400，495→500 必须显式）。"""
        error = BrandTemplateStorageError(layer="l2")
        payload = error.to_dict()
        assert payload["code"] == "EXCEPTION_495"
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
        """六类注册到 report 子域（test_code_ranges Rule 1 联动——6-5b 增 492/493、6-11 增 494/495）。"""
        assert get_subdomain_for_class("ReportGenerationError") == "report"
        assert get_subdomain_for_class("ReportStorageError") == "report"
        assert get_subdomain_for_class("PdfRenderingError") == "report"
        assert get_subdomain_for_class("ReportEvidenceStorageError") == "report"
        assert get_subdomain_for_class("BrandTemplateValidationError") == "report"
        assert get_subdomain_for_class("BrandTemplateStorageError") == "report"

    def test_subdomain_range_covers_codes(self) -> None:
        """report 段范围覆盖 490-495（Rule 5 联动——∈ (490,499)；496-499 仍预留）。"""
        low, high = CODE_RANGES["report"]
        for code in (490, 491, 492, 493, 494, 495):
            assert low <= code <= high

    def test_http_map_values(self) -> None:
        """EXCEPTION_HTTP_MAP 值级：490→404 / 491→500 / 492→500 / 493→500 /
        494→400 / 495→500（495 显式注册是族纪律——BusinessException 基类兜底 400）。"""
        assert EXCEPTION_HTTP_MAP[ReportGenerationError] == status.HTTP_404_NOT_FOUND
        assert EXCEPTION_HTTP_MAP[ReportStorageError] == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert EXCEPTION_HTTP_MAP[PdfRenderingError] == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert EXCEPTION_HTTP_MAP[ReportEvidenceStorageError] == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert EXCEPTION_HTTP_MAP[BrandTemplateValidationError] == status.HTTP_400_BAD_REQUEST
        assert EXCEPTION_HTTP_MAP[BrandTemplateStorageError] == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_exported_in_domain_all(self) -> None:
        """六类经 src.domain.exceptions 导出（test_error_code_uniqueness 自动发现面）。"""
        from src.domain import exceptions as exc_module

        assert "ReportGenerationError" in exc_module.__all__
        assert "ReportStorageError" in exc_module.__all__
        assert "PdfRenderingError" in exc_module.__all__
        assert "ReportEvidenceStorageError" in exc_module.__all__
        assert "BrandTemplateValidationError" in exc_module.__all__
        assert "BrandTemplateStorageError" in exc_module.__all__

    def test_codes_distinct(self) -> None:
        """六码互异（编码唯一性面——uniqueness 测试自动覆盖）。"""
        codes = {
            ReportGenerationError.code,
            ReportStorageError.code,
            PdfRenderingError.code,
            ReportEvidenceStorageError.code,
            BrandTemplateValidationError.code,
            BrandTemplateStorageError.code,
        }
        assert len(codes) == 6
