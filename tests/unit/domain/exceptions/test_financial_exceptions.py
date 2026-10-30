"""financial 子域异常单测（financial，470-479）——Story 5.12 财务建模与估值基础。

覆盖：FinancialCalculationError 构造/属性/code 470/to_dict/context 两键
（method/detail——kwargs 构造形态模板照抄 AgentEvaluationError 450 形态、基类落
BusinessException[勘误注：AgentEvaluationError 实为 SystemException 族，仅取其
kwargs 形态模板]/cause 链/继承链 + message 缺省回落 + method 自由字符串容错
（与 SAPBusStateError reason 闭集校验差异钦定：method 是诊断标注面非协议契约面）
+ HTTP 映射（470→422——BusinessRuleViolationError 422 惯例锚「业务约束不可满足」
语义就近映射）+ 子域段注册（CODE_RANGES "financial": (470, 479) 第七段 +
_CLASS_TO_SUBDOMAIN 一行）+ 编码互异（470 与 sap 段 460-462 零冲突）。

Run with:
    poetry run pytest tests/unit/domain/exceptions/test_financial_exceptions.py -v
"""

from __future__ import annotations

from src.domain.exceptions import (
    BusinessException,
    FinancialCalculationError,
    SystemException,
)
from src.domain.exceptions._code_ranges import _CLASS_TO_SUBDOMAIN, CODE_RANGES

# ==== FinancialCalculationError（EXCEPTION_470——BusinessException，财务计算失败） ====


class TestFinancialCalculationErrorConstruction:
    """FinancialCalculationError 构造与属性（method/detail 双键——V1 触发：IRR 求解失败 + NPV 为零双路径）。"""

    def test_default_message_and_code(self) -> None:
        """默认构造：code 470 + 非空静态文案（message 缺省回落类属性）。"""
        error = FinancialCalculationError(method="dcf", detail="IRR 数值求解失败")
        assert error.code == "EXCEPTION_470"
        assert error.message, "默认消息应为非空静态文案"
        assert error.message == FinancialCalculationError.message, "缺省 message 应回落类属性静态文案"

    def test_explicit_message_override(self) -> None:
        """显式 message 覆盖类属性文案（调用方可定制）。"""
        error = FinancialCalculationError(method="dcf", detail="求解失败", message="自定义计算失败文案")
        assert error.message == "自定义计算失败文案"

    def test_context_carries_method_and_detail(self) -> None:
        """context 双键：method（诊断标注）+ detail（失败描述——面向调用方的计算语义）。"""
        error = FinancialCalculationError(method="dcf", detail="IRR 在支持域内无解")
        assert error.context["method"] == "dcf"
        assert error.context["detail"] == "IRR 在支持域内无解"

    def test_context_only_two_keys_by_default(self) -> None:
        """默认 context 恰两键（method/detail——零内部实现细节泄露）。"""
        error = FinancialCalculationError(method="dcf", detail="bracket 失败")
        assert set(error.context.keys()) == {"method", "detail"}

    def test_method_free_string_tolerance(self) -> None:
        """method 自由字符串容错（闭集 {"dcf","comparable","precedent"} 仅 docstring 语义——不做闭集校验）。"""
        error = FinancialCalculationError(method="sensitivity", detail="预留扩展面")
        assert error.context["method"] == "sensitivity", "method 非 closed-set 校验（诊断标注面）"

    def test_empty_detail_default(self) -> None:
        """detail 缺省空串（context 键仍在）。"""
        error = FinancialCalculationError(method="comparable")
        assert error.context["detail"] == ""
        assert error.context["method"] == "comparable"

    def test_context_extra_merge(self) -> None:
        """context_extra 合并（扩展键不覆盖既有双键）。"""
        error = FinancialCalculationError(
            method="dcf",
            detail="求解失败",
            context_extra={"case_name": "perpetual_growth_5y"},
        )
        assert error.context["case_name"] == "perpetual_growth_5y"
        assert error.context["method"] == "dcf"

    def test_cause_chain(self) -> None:
        """cause 链（显式 cause 形参传递）。"""
        original = RuntimeError("底层二分迭代异常")
        error = FinancialCalculationError(method="dcf", detail="迭代失败", cause=original)
        assert error.cause is original

    def test_to_dict(self) -> None:
        """to_dict 携 code/message/context 三段。"""
        error = FinancialCalculationError(method="dcf", detail="bracket 失败")
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_470"
        assert data["context"]["method"] == "dcf"
        assert data["context"]["detail"] == "bracket 失败"

    def test_str_equals_static_message_with_cause(self) -> None:
        """str(异常) 恒等于 message（cause 动态文案只进 to_dict 不进 str）。"""
        original = ValueError("inner")
        error = FinancialCalculationError(method="dcf", detail="求解失败", cause=original)
        assert str(error) == error.message
        assert "inner" not in str(error)

    def test_message_safety_no_internal_details(self) -> None:
        """默认文案面向调用方计算语义（零迭代内部量/区间端点值泄露）。"""
        error = FinancialCalculationError(method="dcf", detail="求解失败")
        assert "r_lo" not in error.message
        assert "r_hi" not in error.message
        assert "-0.99" not in error.message


# ==== FinancialCalculationError HTTP 映射（470→422 Unprocessable Entity） ====


class TestFinancialCalculationErrorHttpMapping:
    """FinancialCalculationError HTTP 映射（422——BusinessRuleViolationError 惯例锚就近映射）。"""

    def test_get_http_status_422(self) -> None:
        """_get_http_status 正向 422（业务约束不可满足——调用方可调整输入重试）。"""
        from src.interfaces.api.exception_handlers import _get_http_status

        error = FinancialCalculationError(method="dcf", detail="IRR 求解失败")
        assert _get_http_status(error) == 422

    def test_exception_http_map_direct(self) -> None:
        """EXCEPTION_HTTP_MAP 表直查 422。"""
        from fastapi import status

        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP[FinancialCalculationError] == status.HTTP_422_UNPROCESSABLE_ENTITY


# ==== FinancialCalculationError 子域注册（financial 段 470-479） ====


class TestFinancialCalculationErrorSubdomainRegistration:
    """FinancialCalculationError 子域段注册（470 落 financial 段——第七段先例）。"""

    def test_class_to_subdomain(self) -> None:
        """_CLASS_TO_SUBDOMAIN 映射 financial。"""
        assert _CLASS_TO_SUBDOMAIN["FinancialCalculationError"] == "financial"

    def test_code_within_financial_range(self) -> None:
        """编码 470 落 financial 段 [470, 479]。"""
        assert CODE_RANGES["financial"] == (470, 479)
        low, high = CODE_RANGES["financial"]
        numeric = int(FinancialCalculationError.code.removeprefix("EXCEPTION_"))
        assert low <= numeric <= high

    def test_inherits_business_exception(self) -> None:
        """继承链：BusinessException（计算失败是调用方可处理结果——422 语义族非系统故障）。"""
        assert issubclass(FinancialCalculationError, BusinessException)
        assert issubclass(FinancialCalculationError, SystemException) is False


# ==== 编码互异（470 与前段零冲突） ====


class TestFinancialCodeUniqueness:
    """470 编码互异（与前段 sap 460-462 及全仓异常零冲突）。"""

    def test_code_distinct_from_preceding_segments(self) -> None:
        """financial 段起点严格大于 sap 段终点（470 > 469——段间零重叠）。"""
        fin_low, _fin_high = CODE_RANGES["financial"]
        _, sap_high = CODE_RANGES["sap"]
        assert fin_low > sap_high

    def test_code_unique_across_registry(self) -> None:
        """470 全仓唯一（经 src.domain.exceptions.__all__ 全量反向穷举各类 code 属性——
        任何异常类误占 EXCEPTION_470 即红；CR1-3 修复：原实现是键存在性恒真断言）。"""
        import inspect

        import src.domain.exceptions as exceptions_module

        same_code_classes = {
            name
            for name in exceptions_module.__all__
            if inspect.isclass(obj := getattr(exceptions_module, name)) and getattr(obj, "code", None) == "EXCEPTION_470"
        }
        assert same_code_classes == {"FinancialCalculationError"}

    def test_placeholder_not_used(self) -> None:
        """非占位码（EXCEPTION_470 匹配 ^EXCEPTION_\\d[X\\d]{2}$ 模式）。"""
        import re

        assert re.match(r"^EXCEPTION_\d[X\d]{2}$", FinancialCalculationError.code)
