"""财务估值 Schema 与估值用例单测——Story 5.12。

覆盖：三段请求 Schema 族（合法全量/部分构造 + str→Decimal 零精度损失锚 +
六类非法 pydantic.ValidationError + 终值两法字段配套校验）+ 估值用例编排
（_StubModelingService duck-typing 替身分派形态/编排零变换/部分请求跳过/
fail-loud 470 上抛/真实服务全量对照）。

三层异常语义分立（AC-3 Then③ 钦定）：Schema 层 pydantic.ValidationError /
VO 层 EntityValidationError 242 / 引擎层 FinancialCalculationError 470——各自
触发面互不越界（本文件承载 Schema 层 + 经用例触及 470 透传）。

Run with:
    poetry run pytest tests/unit/application/use_cases/test_financial_modeling_use_case.py -v
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

import pytest
from pydantic import ValidationError

from src.application.services.financial_schemas import FinancialValuationRequest
from src.domain.services.financial_modeling import FinancialModelingService

#: 三段全量合法载荷（量值字段全字符串数字 wire 形态——period int 序数索引）
_FULL_PAYLOAD: dict[str, Any] = {
    "dcf": {
        "cash_flows": [
            {"period": 1, "amount": "-100"},
            {"period": 2, "amount": "40"},
            {"period": 3, "amount": "50"},
            {"period": 4, "amount": "60"},
            {"period": 5, "amount": "70"},
        ],
        "discount_rate": "0.1",
        "terminal_value_method": "perpetual_growth",
        "terminal_growth_rate": "0.02",
    },
    "comparables": {
        "comparables": [
            {"name": "可比甲", "ev_ebitda": "8.5"},
            {"name": "可比乙", "ev_ebitda": "10.2"},
            {"name": "可比丙", "ev_ebitda": "12.8"},
            {"name": "可比丁", "ev_ebitda": "15.0"},
        ],
        "target_ebitda": "120",
    },
    "precedents": {
        "transactions": [
            {"target_name": "先例一", "ev_ebitda": "9.0"},
            {"target_name": "先例二", "ev_ebitda": "11.5"},
            {"target_name": "先例三", "ev_ebitda": "13.2"},
        ],
        "target_ebitda": "120",
    },
}


# ==== 循环 A: financial_schemas.py 三段请求族 ====


class TestFinancialSchemas:
    """三段请求 Schema 合法构造 + 精确解析 + 六类非法拒绝。"""

    def test_full_request_construction(self) -> None:
        """三段全量合法构造（量值字段全字符串数字）。"""
        request = FinancialValuationRequest.model_validate(_FULL_PAYLOAD)
        assert request.dcf is not None
        assert request.comparables is not None
        assert request.precedents is not None

    def test_decimal_exact_parse_from_string(self) -> None:
        """str→Decimal 零精度损失锚（OD-5② 核心断言——精确相等非 approx）。"""
        request = FinancialValuationRequest.model_validate(_FULL_PAYLOAD)
        assert request.dcf is not None
        assert request.dcf.discount_rate == Decimal("0.1"), "字符串解析应精确等于 Decimal('0.1')"
        assert request.dcf.terminal_growth_rate == Decimal("0.02")
        assert request.dcf.cash_flows[0].amount == Decimal("-100")
        assert request.dcf.cash_flows[4].amount == Decimal("70")
        assert request.dcf.cash_flows[0].period == 1
        assert request.comparables is not None
        assert request.comparables.target_ebitda == Decimal("120")
        assert request.comparables.comparables[0].ev_ebitda == Decimal("8.5")
        assert request.precedents is not None
        assert request.precedents.transactions[2].ev_ebitda == Decimal("13.2")

    def test_partial_request_dcf_only(self) -> None:
        """单段 DCF 部分请求（另两段缺省 None——用例按 None 跳过编排）。"""
        request = FinancialValuationRequest.model_validate({"dcf": _FULL_PAYLOAD["dcf"]})
        assert request.dcf is not None
        assert request.comparables is None
        assert request.precedents is None

    def test_partial_request_comparables_only(self) -> None:
        """单段可比部分请求。"""
        request = FinancialValuationRequest.model_validate({"comparables": _FULL_PAYLOAD["comparables"]})
        assert request.comparables is not None
        assert request.dcf is None

    def test_exit_multiple_section_construction(self) -> None:
        """退出倍数法段构造（exit_multiple + terminal_exit_metric=终年 EBITDA）。"""
        payload = {
            "dcf": {
                "cash_flows": [{"period": 1, "amount": "-100"}, {"period": 2, "amount": "110"}],
                "discount_rate": "0.1",
                "terminal_value_method": "exit_multiple",
                "exit_multiple": "8.5",
                "terminal_exit_metric": "110",
            }
        }
        request = FinancialValuationRequest.model_validate(payload)
        assert request.dcf is not None
        assert request.dcf.exit_multiple == Decimal("8.5")
        assert request.dcf.terminal_exit_metric == Decimal("110")

    @pytest.mark.parametrize(
        "mutator",
        [
            pytest.param(lambda p: {**p, "dcf": {**p["dcf"], "discount_rate": "-0.1"}}, id="负折现率"),
            pytest.param(lambda p: {**p, "dcf": {**p["dcf"], "discount_rate": "1.5"}}, id="折现率不小于1"),
            pytest.param(
                lambda p: {
                    **p,
                    "dcf": {**p["dcf"], "discount_rate": "0.10", "terminal_growth_rate": "0.12"},
                },
                id="g不小于r跨字段",
            ),
            pytest.param(lambda p: {**p, "dcf": {**p["dcf"], "cash_flows": []}}, id="空现金流"),
            pytest.param(
                lambda p: {**p, "comparables": {"comparables": [], "target_ebitda": "120"}},
                id="空可比",
            ),
            pytest.param(lambda p: {}, id="三段全None"),
        ],
    )
    def test_six_invalid_payloads_rejected(self, mutator: Any) -> None:
        """六类非法输入 → pydantic.ValidationError（Schema 层拦截——Field 约束 + 跨字段校验器）。"""
        with pytest.raises(ValidationError):
            FinancialValuationRequest.model_validate(mutator(_FULL_PAYLOAD))

    def test_cross_field_validator_error_type_locked(self) -> None:
        """跨字段校验器错误 type 锁定断言（CR1-2——校验器以 raise AssertionError 显式
        raise 形态 signalling，pydantic 包装为 type=assertion_error 的 ValidationError；
        本断言防回退 ValueError 形态使红线 grep 门禁静默再破）。"""
        payload = {**_FULL_PAYLOAD["dcf"]}
        payload["terminal_growth_rate"] = "0.12"  # g≥r 跨字段非法（g=0.12 > r=0.1）
        with pytest.raises(ValidationError) as exc_info:
            FinancialValuationRequest.model_validate({"dcf": payload})
        assert exc_info.value.errors()[0]["type"] == "assertion_error", (
            "跨字段校验器应经 raise AssertionError 形态（CR1-2 钦定——type=assertion_error）"
        )

    @pytest.mark.parametrize(
        ("section_key", "list_key", "over_limit"),
        [
            pytest.param("dcf", "cash_flows", 1201, id="cash_flows_1201"),
            pytest.param("comparables", "comparables", 101, id="comparables_101"),
            pytest.param("precedents", "transactions", 101, id="transactions_101"),
        ],
    )
    def test_list_length_upper_bound_rejected(self, section_key: str, list_key: str, over_limit: int) -> None:
        """三 list 字段 max_length 超限拒绝（CR2-1——超长输入 DoS 防御单层钦定；
        错误 type=too_long 锁定）。"""
        base_section = _FULL_PAYLOAD[section_key]
        section: dict[str, Any] = {**base_section}
        if list_key == "cash_flows":
            section[list_key] = [{"period": index + 1, "amount": "-100"} for index in range(over_limit)]
        else:
            item_template = base_section[list_key][0]
            section[list_key] = [{**item_template, "name": f"member-{index}"} for index in range(over_limit)]
        with pytest.raises(ValidationError) as exc_info:
            FinancialValuationRequest.model_validate({section_key: section})
        error_types = {error["type"] for error in exc_info.value.errors()}
        assert "too_long" in error_types, f"超限应触发 pydantic too_long 错误，实际 {error_types}"

    def test_at_limit_boundary_accepted(self) -> None:
        """上限恰好通过边界锚（1200/100/100 精确构造——CR2-1：防上限值手误漂移
        [如误写 120]导致的只红不绿盲区——恰好在上限的合法载荷必须通过）。"""
        request = FinancialValuationRequest.model_validate(
            {
                "dcf": {
                    **_FULL_PAYLOAD["dcf"],
                    "cash_flows": [{"period": index + 1, "amount": "100"} for index in range(1200)],
                },
                "comparables": {
                    **_FULL_PAYLOAD["comparables"],
                    "comparables": [{"name": f"comp-{index}", "ev_ebitda": "8.5"} for index in range(100)],
                },
                "precedents": {
                    **_FULL_PAYLOAD["precedents"],
                    "transactions": [{"target_name": f"target-{index}", "ev_ebitda": "9.0"} for index in range(100)],
                },
            }
        )
        assert request.dcf is not None and len(request.dcf.cash_flows) == 1200
        assert request.comparables is not None and len(request.comparables.comparables) == 100
        assert request.precedents is not None and len(request.precedents.transactions) == 100

    def test_perpetual_with_exit_fields_rejected(self) -> None:
        """终值两法字段配套：perpetual 法带 exit_multiple → 拒绝（法-参数互斥）。"""
        payload = {
            "dcf": {
                **_FULL_PAYLOAD["dcf"],
                "exit_multiple": "8.5",
            }
        }
        with pytest.raises(ValidationError):
            FinancialValuationRequest.model_validate(payload)

    def test_exit_missing_exit_multiple_rejected(self) -> None:
        """终值两法字段配套：exit 法缺 exit_multiple → 拒绝（法配套必填）。"""
        payload = {
            "dcf": {
                "cash_flows": [{"period": 1, "amount": "-100"}],
                "discount_rate": "0.1",
                "terminal_value_method": "exit_multiple",
                "terminal_exit_metric": "70",
            }
        }
        with pytest.raises(ValidationError):
            FinancialValuationRequest.model_validate(payload)

    def test_non_positive_comparable_multiple_rejected(self) -> None:
        """可比成员非正倍数 → 拒绝（Schema gt=0——与 VO 守卫镜像的双层守卫）。"""
        payload = {
            "comparables": {
                "comparables": [{"name": "可比零", "ev_ebitda": "0"}],
                "target_ebitda": "120",
            }
        }
        with pytest.raises(ValidationError):
            FinancialValuationRequest.model_validate(payload)

    def test_negative_target_ebitda_rejected(self) -> None:
        """target_ebitda 负值 → 拒绝（Schema gt=0——亏损标的 V1 不支持，拦截落点在 Schema 层非 242）。"""
        payload = {
            "comparables": {
                "comparables": [{"name": "可比甲", "ev_ebitda": "8.5"}],
                "target_ebitda": "-5",
            }
        }
        with pytest.raises(ValidationError):
            FinancialValuationRequest.model_validate(payload)

    def test_period_below_one_rejected(self) -> None:
        """period<1 → 拒绝（Field ge=1——与 VO 成员级守卫镜像）。"""
        payload = {
            "dcf": {
                "cash_flows": [{"period": 0, "amount": "-100"}, {"period": 1, "amount": "110"}],
                "discount_rate": "0.1",
                "terminal_value_method": "perpetual_growth",
                "terminal_growth_rate": "0.02",
            }
        }
        with pytest.raises(ValidationError):
            FinancialValuationRequest.model_validate(payload)


# ==== 循环 B: FinancialModelingUseCase + to_value_objects（编排/fail-loud/真实对照） ====


class _StubModelingService:
    """手写零 IO 引擎替身（duck-typing 捕获三方法调用——单测编排断言专用；验收面用真实服务）。"""

    def __init__(self) -> None:
        self.dcf_calls: list[tuple[Any, Any]] = []
        self.comparable_calls: list[tuple[Any, Any]] = []
        self.precedent_calls: list[tuple[Any, Any]] = []
        self.dcf_result: Any = None
        self.comparable_result: Any = None
        self.precedent_result: Any = None
        self.dcf_error: Exception | None = None

    def calculate_dcf(self, schedule: Any, assumptions: Any) -> Any:
        """捕获 DCF 调用（可预置结果或异常——fail-loud 断言面）。"""
        self.dcf_calls.append((schedule, assumptions))
        if self.dcf_error is not None:
            raise self.dcf_error
        return self.dcf_result

    def calculate_comparable_valuation(self, comparables: Any, target_ebitda: Any) -> Any:
        """捕获可比调用。"""
        self.comparable_calls.append((comparables, target_ebitda))
        return self.comparable_result

    def calculate_precedent_valuation(self, transactions: Any, target_ebitda: Any) -> Any:
        """捕获先例调用。"""
        self.precedent_calls.append((transactions, target_ebitda))
        return self.precedent_result


class TestToValueObjects:
    """to_value_objects 转换函数（Schema→VO 四元组——零业务变换）。"""

    def test_full_request_yields_four_vos(self) -> None:
        """全量请求产四 VO（DCF 段产两件 + 可比/先例段各一件）。"""
        from src.application.use_cases.financial_modeling import to_value_objects
        from src.domain.value_objects.financial_valuation import (
            CashFlowSchedule,
            ComparableSet,
            DcfAssumptions,
            PrecedentTransactionSet,
        )

        request = FinancialValuationRequest.model_validate(_FULL_PAYLOAD)
        schedule, assumptions, comparable_set, transaction_set = to_value_objects(request)
        assert isinstance(schedule, CashFlowSchedule)
        assert isinstance(assumptions, DcfAssumptions)
        assert isinstance(comparable_set, ComparableSet)
        assert isinstance(transaction_set, PrecedentTransactionSet)
        # VO 转换零变换锚：金额/折现率逐值透传（str→Decimal 解析值直接进 VO）
        assert assumptions.discount_rate == Decimal("0.1")
        assert schedule.cash_flows[0].amount == Decimal("-100")
        assert comparable_set.comparables[0].ev_ebitda == Decimal("8.5")
        assert transaction_set.transactions[0].ev_ebitda == Decimal("9.0")

    def test_partial_request_yields_none_sections(self) -> None:
        """单段请求产 None 段（未请求段转换为 None——用例按 None 跳过编排）。"""
        from src.application.use_cases.financial_modeling import to_value_objects

        request = FinancialValuationRequest.model_validate({"dcf": _FULL_PAYLOAD["dcf"]})
        schedule, assumptions, comparable_set, transaction_set = to_value_objects(request)
        assert schedule is not None
        assert assumptions is not None
        assert comparable_set is None
        assert transaction_set is None


class TestFinancialModelingUseCase:
    """FinancialModelingUseCase 编排（分派完整性/零变换/fail-loud/真实对照）。"""

    def _make_preset_results(self) -> tuple[Any, Any, Any]:
        """预置三段结果（stub 返回形态——DTO 组装逐字段断言面）。"""
        from src.domain.value_objects.financial_valuation import (
            ComparableValuationResult,
            DcfValuationResult,
            MultiplesStats,
            PrecedentValuationResult,
        )

        stats = MultiplesStats(min=Decimal("8.5"), median=Decimal("11.5"), mean=Decimal("11.625"), max=Decimal("15.0"))
        dcf_result = DcfValuationResult(
            present_values=(Decimal("-90.9"), Decimal("33.06")),
            npv=Decimal("-57.85"),
            terminal_value=Decimal("0"),
            terminal_value_weight=Decimal("-0.5"),
            irr=Decimal("0.05"),
        )
        comparable_result = ComparableValuationResult(
            multiples_stats=stats,
            implied_ev_low=Decimal("1020"),
            implied_ev_median=Decimal("1380"),
            implied_ev_high=Decimal("1800"),
        )
        precedent_result = PrecedentValuationResult(
            multiples_stats=stats,
            implied_ev_low=Decimal("1080"),
            implied_ev_median=Decimal("1530"),
            implied_ev_high=Decimal("1860"),
        )
        return dcf_result, comparable_result, precedent_result

    def test_full_request_dispatches_all_three_methods(self) -> None:
        """全量请求三方法各被调一次（分派完整性锚——编排零业务逻辑纯分派）。"""
        from src.application.use_cases.financial_modeling import FinancialModelingUseCase

        stub = _StubModelingService()
        stub.dcf_result, stub.comparable_result, stub.precedent_result = self._make_preset_results()
        use_case = FinancialModelingUseCase(service=cast(FinancialModelingService, stub))
        use_case.execute(FinancialValuationRequest.model_validate(_FULL_PAYLOAD))
        assert len(stub.dcf_calls) == 1, "calculate_dcf 应被调一次"
        assert len(stub.comparable_calls) == 1, "calculate_comparable_valuation 应被调一次"
        assert len(stub.precedent_calls) == 1, "calculate_precedent_valuation 应被调一次"

    def test_dto_assembles_stub_results_verbatim(self) -> None:
        """stub 返回预置结果时 DTO 三段组装逐字段相等（编排零变换——stub 返回什么 DTO 就装什么）。"""
        from src.application.use_cases.financial_modeling import FinancialModelingUseCase

        stub = _StubModelingService()
        dcf_result, comparable_result, precedent_result = self._make_preset_results()
        stub.dcf_result, stub.comparable_result, stub.precedent_result = (
            dcf_result,
            comparable_result,
            precedent_result,
        )
        use_case = FinancialModelingUseCase(service=cast(FinancialModelingService, stub))
        dto = use_case.execute(FinancialValuationRequest.model_validate(_FULL_PAYLOAD))
        assert dto.dcf == dcf_result
        assert dto.comparables == comparable_result
        assert dto.precedents == precedent_result

    def test_partial_request_skips_none_sections(self) -> None:
        """部分请求跳过 None 段（仅 DCF 段 → 只 calculate_dcf 被调、DTO 另两段 None）。"""
        from src.application.use_cases.financial_modeling import FinancialModelingUseCase

        stub = _StubModelingService()
        stub.dcf_result, _, _ = self._make_preset_results()
        use_case = FinancialModelingUseCase(service=cast(FinancialModelingService, stub))
        dto = use_case.execute(FinancialValuationRequest.model_validate({"dcf": _FULL_PAYLOAD["dcf"]}))
        assert len(stub.dcf_calls) == 1
        assert stub.comparable_calls == [], "未请求的可比段不应分派"
        assert stub.precedent_calls == [], "未请求的先例段不应分派"
        assert dto.dcf is not None
        assert dto.comparables is None
        assert dto.precedents is None

    def test_dispatch_passes_converted_vos(self) -> None:
        """分派参数与 to_value_objects 转换结果一致（转换零变换锚）。"""
        from src.application.use_cases.financial_modeling import FinancialModelingUseCase, to_value_objects

        stub = _StubModelingService()
        stub.dcf_result, stub.comparable_result, stub.precedent_result = self._make_preset_results()
        use_case = FinancialModelingUseCase(service=cast(FinancialModelingService, stub))
        request = FinancialValuationRequest.model_validate(_FULL_PAYLOAD)
        use_case.execute(request)
        schedule, assumptions, comparable_set, transaction_set = to_value_objects(request)
        assert stub.dcf_calls[0] == (schedule, assumptions)
        assert stub.comparable_calls[0][0] == comparable_set
        assert stub.comparable_calls[0][1] == Decimal("120")
        assert stub.precedent_calls[0][0] == transaction_set

    def test_fail_loud_470_propagates(self) -> None:
        """fail-loud：引擎抛 470 → execute 上抛同异常（不吞不降级不返回部分结果）。"""
        from src.application.use_cases.financial_modeling import FinancialModelingUseCase
        from src.domain.exceptions import FinancialCalculationError

        stub = _StubModelingService()
        stub.dcf_error = FinancialCalculationError(method="dcf", detail="IRR 求解失败")
        use_case = FinancialModelingUseCase(service=cast(FinancialModelingService, stub))
        with pytest.raises(FinancialCalculationError) as exc_info:
            use_case.execute(FinancialValuationRequest.model_validate(_FULL_PAYLOAD))
        assert exc_info.value.code == "EXCEPTION_470"
        assert exc_info.value is stub.dcf_error, "应上抛同一异常实例（零捕获零包装）"

    def test_real_service_full_consistency(self) -> None:
        """真实服务全量对照（同输入 execute 结果三段与直接调真实服务逐一相等——真实链零变换总锚）。"""
        from src.application.use_cases.financial_modeling import FinancialModelingUseCase, to_value_objects
        from src.domain.services.financial_modeling import FinancialModelingService

        real_service = FinancialModelingService()
        use_case = FinancialModelingUseCase(service=real_service)
        request = FinancialValuationRequest.model_validate(_FULL_PAYLOAD)
        dto = use_case.execute(request)

        schedule, assumptions, comparable_set, transaction_set = to_value_objects(request)
        assert schedule is not None and assumptions is not None
        assert comparable_set is not None and transaction_set is not None
        assert dto.dcf == real_service.calculate_dcf(schedule, assumptions)
        assert dto.comparables == real_service.calculate_comparable_valuation(
            comparable_set, Decimal(_FULL_PAYLOAD["comparables"]["target_ebitda"])
        )
        assert dto.precedents == real_service.calculate_precedent_valuation(
            transaction_set, Decimal(_FULL_PAYLOAD["precedents"]["target_ebitda"])
        )
