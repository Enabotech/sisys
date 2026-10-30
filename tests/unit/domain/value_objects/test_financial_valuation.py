"""财务估值值对象族单测（11 类 frozen dataclass + 242 守卫）——Story 5.12。

覆盖：输入类 7 类（CashFlow/CashFlowSchedule/DcfAssumptions/ComparableCompany/
ComparableSet/PrecedentTransaction/PrecedentTransactionSet）构造成功 + __post_init__
守卫失败路径参数化（EntityValidationError 242——context 携 entity/field 键）；
结果类 4 类（DcfValuationResult/MultiplesStats/ComparableValuationResult/
PrecedentValuationResult）纯载体零守卫（负 NPV/weight 越界是合法计算结果非构造
违例）+ 全类 frozen 断言（赋值抛 FrozenInstanceError）。

符号变更守卫钦定：非零子序列上计数（Descartes 忽略零系数——[−100, 0, 110] 有
IRR≈4.88% 构造放行；[−100, 0.0001, −110] 非零子序列 (−,+,−) 有变更故 VO 放行、
IRR 实不存在由引擎 bracket 470 兜底——两层分工）。

Run with:
    poetry run pytest tests/unit/domain/value_objects/test_financial_valuation.py -v
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.financial_valuation import (
    CashFlow,
    CashFlowSchedule,
    ComparableCompany,
    ComparableSet,
    ComparableValuationResult,
    DcfAssumptions,
    DcfValuationResult,
    MultiplesStats,
    PrecedentTransaction,
    PrecedentTransactionSet,
    PrecedentValuationResult,
)


def _make_schedule(amounts: list[str]) -> CashFlowSchedule:
    """现金流表构造 helper（period 1..n 严格连续 + 量值字符串形态）。"""
    return CashFlowSchedule(
        cash_flows=tuple(CashFlow(period=index, amount=Decimal(amount)) for index, amount in enumerate(amounts, start=1))
    )


def _make_perpetual_assumptions(**overrides: str) -> DcfAssumptions:
    """永续增长假设构造 helper（默认合法值 + 覆盖）。"""
    kwargs: dict[str, str] = {
        "discount_rate": "0.1",
        "terminal_value_method": "perpetual_growth",
        "terminal_growth_rate": "0.02",
    }
    kwargs.update(overrides)
    return DcfAssumptions(
        discount_rate=Decimal(kwargs["discount_rate"]),
        terminal_value_method=kwargs["terminal_value_method"],
        terminal_growth_rate=Decimal(kwargs["terminal_growth_rate"]) if "terminal_growth_rate" in kwargs else None,
        exit_multiple=Decimal(kwargs["exit_multiple"]) if "exit_multiple" in kwargs else None,
        terminal_exit_metric=Decimal(kwargs["terminal_exit_metric"]) if "terminal_exit_metric" in kwargs else None,
    )


# ==== CashFlow（成员级守卫——period ≥ 1） ====


class TestCashFlow:
    """CashFlow 构造与成员级守卫。"""

    def test_valid_construction(self) -> None:
        """合法构造（period≥1 + 任意符号 amount——负=流出）。"""
        flow = CashFlow(period=1, amount=Decimal("-100"))
        assert flow.period == 1
        assert flow.amount == Decimal("-100")

    @pytest.mark.parametrize("period", [0, -1])
    def test_period_below_one_rejected(self, period: int) -> None:
        """period<1 两形态 → 242（context field=period——序数索引不变量）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            CashFlow(period=period, amount=Decimal("100"))
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "period"
        assert exc_info.value.context["entity"] == "CashFlow"

    def test_zero_amount_allowed(self) -> None:
        """零金额成员合法（零现金流序列语义——Descartes 忽略零系数）。"""
        flow = CashFlow(period=2, amount=Decimal("0"))
        assert flow.amount == Decimal("0")


# ==== CashFlowSchedule（schedule 级守卫——非空/连续/符号变更） ====


class TestCashFlowSchedule:
    """CashFlowSchedule 构造与 schedule 级守卫。"""

    def test_valid_construction(self) -> None:
        """合法构造（非空 + period 连续 + 符号变更存在）。"""
        schedule = _make_schedule(["-100", "40", "50"])
        assert len(schedule.cash_flows) == 3
        assert schedule.cash_flows[0] == CashFlow(period=1, amount=Decimal("-100"))

    def test_empty_schedule_rejected(self) -> None:
        """空集合 → 242（field=cash_flows——非空不变量）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            CashFlowSchedule(cash_flows=())
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "cash_flows"

    def test_non_continuous_period_rejected(self) -> None:
        """period 非连续（1,3）→ 242（严格从 1 连续不变量）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            CashFlowSchedule(
                cash_flows=(
                    CashFlow(period=1, amount=Decimal("-100")),
                    CashFlow(period=3, amount=Decimal("110")),
                )
            )
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "cash_flows"

    def test_period_not_starting_at_one_rejected(self) -> None:
        """period 不从 1 起（2,3）→ 242。"""
        with pytest.raises(EntityValidationError) as exc_info:
            CashFlowSchedule(
                cash_flows=(
                    CashFlow(period=2, amount=Decimal("-100")),
                    CashFlow(period=3, amount=Decimal("110")),
                )
            )
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "cash_flows"

    def test_duplicate_period_rejected(self) -> None:
        """period 重复（1,1）→ 242。"""
        with pytest.raises(EntityValidationError) as exc_info:
            CashFlowSchedule(
                cash_flows=(
                    CashFlow(period=1, amount=Decimal("-100")),
                    CashFlow(period=1, amount=Decimal("110")),
                )
            )
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "cash_flows"

    @pytest.mark.parametrize("amounts", [["100", "50"], ["-100", "-50"]])
    def test_no_sign_change_rejected(self, amounts: list[str]) -> None:
        """无符号变更（全正/全负）→ 242（IRR 可解必要条件——Descartes 符号规则）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_schedule(amounts)
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "cash_flows"

    def test_zero_member_positive_case_allowed(self) -> None:
        """零成员正向用例 [−100, 0, 110] 构造成功（非零子序列 (−,+) 有一次变更——IRR≈4.88% 存在）。"""
        schedule = _make_schedule(["-100", "0", "110"])
        assert schedule.cash_flows[1].amount == Decimal("0")

    def test_zero_member_pathological_case_passes_vo(self) -> None:
        """零成员病态序列 [−100, 0.0001, −110] VO 放行（非零子序列 (−,+,−) 有变更——
        IRR 实不存在由引擎 bracket 470 兜底，两层分工）。"""
        schedule = _make_schedule(["-100", "0.0001", "-110"])
        assert len(schedule.cash_flows) == 3


# ==== DcfAssumptions（跨字段守卫——折现率域/法闭集/法配套互斥） ====


class TestDcfAssumptions:
    """DcfAssumptions 构造与跨字段守卫（构造期静态可判定不变量归 VO 层）。"""

    def test_valid_perpetual_growth(self) -> None:
        """合法永续增长假设（0<r<1 + g≥0 且 g<r）。"""
        assumptions = _make_perpetual_assumptions()
        assert assumptions.discount_rate == Decimal("0.1")
        assert assumptions.terminal_value_method == "perpetual_growth"
        assert assumptions.terminal_growth_rate == Decimal("0.02")
        assert assumptions.exit_multiple is None
        assert assumptions.terminal_exit_metric is None

    def test_valid_exit_multiple(self) -> None:
        """合法退出倍数假设（exit_multiple>0 + terminal_exit_metric>0——终年 EBITDA 口径）。"""
        assumptions = DcfAssumptions(
            discount_rate=Decimal("0.1"),
            terminal_value_method="exit_multiple",
            exit_multiple=Decimal("8.5"),
            terminal_exit_metric=Decimal("70"),
        )
        assert assumptions.exit_multiple == Decimal("8.5")
        assert assumptions.terminal_exit_metric == Decimal("70")
        assert assumptions.terminal_growth_rate is None

    @pytest.mark.parametrize("discount_rate", ["0", "-0.1"])
    def test_discount_rate_not_positive_rejected(self, discount_rate: str) -> None:
        """r≤0 两形态 → 242（field=discount_rate）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_perpetual_assumptions(discount_rate=discount_rate)
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "discount_rate"

    @pytest.mark.parametrize("discount_rate", ["1", "1.5"])
    def test_discount_rate_ge_one_rejected(self, discount_rate: str) -> None:
        """r≥1 两形态 → 242（折现率 <100% 经济域）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_perpetual_assumptions(discount_rate=discount_rate)
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "discount_rate"

    def test_method_not_in_closed_set_rejected(self) -> None:
        """terminal_value_method 闭集外 → 242（str 字段闭集判等——domain 零 Literal 依赖）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_perpetual_assumptions(terminal_value_method="invalid_method")
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "terminal_value_method"

    def test_perpetual_missing_growth_rate_rejected(self) -> None:
        """perpetual 法缺 g → 242（field=terminal_growth_rate——法配套必填）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            DcfAssumptions(
                discount_rate=Decimal("0.1"),
                terminal_value_method="perpetual_growth",
                terminal_growth_rate=None,
            )
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "terminal_growth_rate"

    def test_negative_growth_rate_rejected(self) -> None:
        """g<0 → 242（永续增长非负域）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_perpetual_assumptions(terminal_growth_rate="-0.01")
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "terminal_growth_rate"

    def test_growth_rate_ge_discount_rate_rejected(self) -> None:
        """g≥r → 242（永续增长公式 r−g 分母非正——构造期静态可判定不变量归 VO 层）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_perpetual_assumptions(discount_rate="0.10", terminal_growth_rate="0.12")
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "terminal_growth_rate"

    def test_perpetual_with_exit_fields_rejected(self) -> None:
        """perpetual 法携 exit 字段 → 242（法-参数互斥——非本法参数须 None）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            _make_perpetual_assumptions(exit_multiple="8.5")
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "exit_multiple"

    def test_exit_missing_exit_multiple_rejected(self) -> None:
        """exit 法缺 exit_multiple → 242（法配套必填）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            DcfAssumptions(
                discount_rate=Decimal("0.1"),
                terminal_value_method="exit_multiple",
                terminal_exit_metric=Decimal("70"),
            )
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "exit_multiple"

    def test_exit_missing_terminal_exit_metric_rejected(self) -> None:
        """exit 法缺 terminal_exit_metric → 242（终年 EBITDA 必填）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            DcfAssumptions(
                discount_rate=Decimal("0.1"),
                terminal_value_method="exit_multiple",
                exit_multiple=Decimal("8.5"),
            )
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "terminal_exit_metric"

    @pytest.mark.parametrize("exit_multiple", ["0", "-1.5"])
    def test_non_positive_exit_multiple_rejected(self, exit_multiple: str) -> None:
        """exit_multiple≤0 两形态 → 242（倍数域正值不变量）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            DcfAssumptions(
                discount_rate=Decimal("0.1"),
                terminal_value_method="exit_multiple",
                exit_multiple=Decimal(exit_multiple),
                terminal_exit_metric=Decimal("70"),
            )
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "exit_multiple"

    @pytest.mark.parametrize("metric", ["0", "-5"])
    def test_non_positive_terminal_exit_metric_rejected(self, metric: str) -> None:
        """terminal_exit_metric≤0 两形态 → 242（终年 EBITDA 正值域——V1 不支持亏损标的）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            DcfAssumptions(
                discount_rate=Decimal("0.1"),
                terminal_value_method="exit_multiple",
                exit_multiple=Decimal("8.5"),
                terminal_exit_metric=Decimal(metric),
            )
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "terminal_exit_metric"

    def test_exit_with_growth_rate_rejected(self) -> None:
        """exit 法携 g → 242（法-参数互斥反向）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            DcfAssumptions(
                discount_rate=Decimal("0.1"),
                terminal_value_method="exit_multiple",
                exit_multiple=Decimal("8.5"),
                terminal_exit_metric=Decimal("70"),
                terminal_growth_rate=Decimal("0.02"),
            )
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "terminal_growth_rate"


# ==== ComparableCompany / ComparableSet（成员级 + 集合级守卫） ====


class TestComparableCompanyAndSet:
    """ComparableCompany 成员守卫 + ComparableSet 非空不变量。"""

    def test_valid_construction(self) -> None:
        """合法构造（name 非空 + ev_ebitda>0 + 集合非空）。"""
        company_set = ComparableSet(
            comparables=(
                ComparableCompany(name="可比甲", ev_ebitda=Decimal("8.5")),
                ComparableCompany(name="可比乙", ev_ebitda=Decimal("10.2")),
            )
        )
        assert len(company_set.comparables) == 2

    def test_empty_set_rejected(self) -> None:
        """空可比集合 → 242（field=comparables——非空不变量）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            ComparableSet(comparables=())
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "comparables"

    def test_empty_name_rejected(self) -> None:
        """name 空串 → 242（field=name——标识非空）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            ComparableCompany(name="", ev_ebitda=Decimal("8.5"))
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "name"

    @pytest.mark.parametrize("ev_ebitda", ["0", "-1.5"])
    def test_non_positive_multiple_rejected(self, ev_ebitda: str) -> None:
        """ev_ebitda≤0 两形态 → 242（field=ev_ebitda——倍数域正值不变量）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            ComparableCompany(name="可比丙", ev_ebitda=Decimal(ev_ebitda))
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "ev_ebitda"


# ==== PrecedentTransaction / PrecedentTransactionSet（同构守卫） ====


class TestPrecedentTransactionAndSet:
    """PrecedentTransaction 成员守卫 + PrecedentTransactionSet 非空不变量（同构参数化）。"""

    def test_valid_construction(self) -> None:
        """合法构造。"""
        transaction_set = PrecedentTransactionSet(
            transactions=(PrecedentTransaction(target_name="先例一", ev_ebitda=Decimal("9.0")),)
        )
        assert len(transaction_set.transactions) == 1

    def test_empty_set_rejected(self) -> None:
        """空先例集合 → 242（field=transactions）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            PrecedentTransactionSet(transactions=())
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "transactions"

    def test_empty_target_name_rejected(self) -> None:
        """target_name 空串 → 242（field=target_name）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            PrecedentTransaction(target_name="", ev_ebitda=Decimal("9.0"))
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "target_name"

    @pytest.mark.parametrize("ev_ebitda", ["0", "-0.5"])
    def test_non_positive_multiple_rejected(self, ev_ebitda: str) -> None:
        """ev_ebitda≤0 → 242（field=ev_ebitda）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            PrecedentTransaction(target_name="先例二", ev_ebitda=Decimal(ev_ebitda))
        assert exc_info.value.code == "EXCEPTION_242"
        assert exc_info.value.context["field"] == "ev_ebitda"


# ==== 结果类 4 类（纯载体零守卫——负 NPV/weight 越界是合法计算结果） ====


class TestResultValueObjects:
    """结果类纯载体构造（零 __post_init__ 守卫——防御过度守卫使负 NPV 用例误抛 242）。"""

    def test_dcf_result_negative_npv_allowed(self) -> None:
        """DcfValuationResult 负 NPV 构造成功（合法经济结果非构造违例）。"""
        result = DcfValuationResult(
            present_values=(Decimal("-90.9"), Decimal("33.06")),
            npv=Decimal("-57.85"),
            terminal_value=Decimal("0"),
            terminal_value_weight=Decimal("-0.5"),
            irr=Decimal("0.05"),
        )
        assert result.npv == Decimal("-57.85")

    def test_dcf_result_weight_above_one_allowed(self) -> None:
        """weight>1 构造成功（ΣPV<0[重前期投入]时 PV(TV)>npv——正常经济结果）。"""
        result = DcfValuationResult(
            present_values=(Decimal("-8.26"),),
            npv=Decimal("1045.45"),
            terminal_value=Decimal("1402.5"),
            terminal_value_weight=Decimal("1.0079"),
            irr=Decimal("0.0488"),
        )
        assert result.terminal_value_weight > Decimal("1")

    def test_multiples_stats_carrier(self) -> None:
        """MultiplesStats 四值纯载体。"""
        stats = MultiplesStats(min=Decimal("8.5"), median=Decimal("11.35"), mean=Decimal("11.625"), max=Decimal("15.0"))
        assert stats.min == Decimal("8.5")

    def test_comparable_result_carrier(self) -> None:
        """ComparableValuationResult 纯载体。"""
        stats = MultiplesStats(min=Decimal("8.5"), median=Decimal("11.35"), mean=Decimal("11.625"), max=Decimal("15.0"))
        result = ComparableValuationResult(
            multiples_stats=stats,
            implied_ev_low=Decimal("1020"),
            implied_ev_median=Decimal("1362"),
            implied_ev_high=Decimal("1800"),
        )
        assert result.implied_ev_low == Decimal("1020")

    def test_precedent_result_carrier(self) -> None:
        """PrecedentValuationResult 同构纯载体。"""
        stats = MultiplesStats(min=Decimal("9.0"), median=Decimal("11.5"), mean=Decimal("11.23"), max=Decimal("13.2"))
        result = PrecedentValuationResult(
            multiples_stats=stats,
            implied_ev_low=Decimal("1080"),
            implied_ev_median=Decimal("1380"),
            implied_ev_high=Decimal("1584"),
        )
        assert result.implied_ev_high == Decimal("1584")


# ==== 全类 frozen 断言（11 类不可变） ====


class TestFrozenImmutability:
    """11 类 frozen dataclass 断言（赋值抛 FrozenInstanceError）。"""

    def test_input_vos_frozen(self) -> None:
        """输入类 7 类 frozen 断言。"""
        instances = [
            CashFlow(period=1, amount=Decimal("-100")),
            _make_schedule(["-100", "110"]),
            _make_perpetual_assumptions(),
            ComparableCompany(name="可比甲", ev_ebitda=Decimal("8.5")),
            ComparableSet(comparables=(ComparableCompany(name="可比甲", ev_ebitda=Decimal("8.5")),)),
            PrecedentTransaction(target_name="先例一", ev_ebitda=Decimal("9.0")),
            PrecedentTransactionSet(transactions=(PrecedentTransaction(target_name="先例一", ev_ebitda=Decimal("9.0")),)),
        ]
        for instance in instances:
            with pytest.raises(FrozenInstanceError):
                setattr(instance, "__dummy__", 1)

    def test_result_vos_frozen(self) -> None:
        """结果类 4 类 frozen 断言。"""
        stats = MultiplesStats(min=Decimal("8.5"), median=Decimal("11.35"), mean=Decimal("11.625"), max=Decimal("15.0"))
        instances = [
            DcfValuationResult(
                present_values=(Decimal("-90.9"),),
                npv=Decimal("-57.85"),
                terminal_value=Decimal("0"),
                terminal_value_weight=Decimal("-0.5"),
                irr=Decimal("0.05"),
            ),
            stats,
            ComparableValuationResult(
                multiples_stats=stats,
                implied_ev_low=Decimal("1020"),
                implied_ev_median=Decimal("1362"),
                implied_ev_high=Decimal("1800"),
            ),
            PrecedentValuationResult(
                multiples_stats=stats,
                implied_ev_low=Decimal("1080"),
                implied_ev_median=Decimal("1380"),
                implied_ev_high=Decimal("1584"),
            ),
        ]
        for instance in instances:
            with pytest.raises(FrozenInstanceError):
                setattr(instance, "__dummy__", 1)
