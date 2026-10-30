"""财务建模与估值引擎单测（DCF/可比/先例三引擎）——Story 5.12。

覆盖：DCF NPV + 终值两法 Excel 基准对齐（相对误差 < EXCEL_ALIGNMENT_TOLERANCE——
OD-5③ Decimal 域断言零 pytest.approx）+ present_values 逐期独立断言 + NPV 分解
自洽锚（精确相等——测试侧重算包 localcontext prec=50）+ IRR 二分法（基准对齐/
零成员序列/已知精确解收敛/bracket 失败 470）+ 可比与先例统计引擎（统计四值 +
隐含区间精确相等 + 偶数样本 median）。

基准值生成法双源纪律（AC-1 Given 钦定）：主源 = 本文件 fractions.Fraction 独立
精确复算（封闭式 NPV/终值/统计——与引擎 Decimal prec=50 前数十字符逐位吻合）；
IRR 无闭式解——基准限单符号变更序列（Descartes：恰一次符号变更 ⇒ 恰一正根），
expected 由独立 Decimal 200 位精度二分产生（烘焙进 JSON）；Excel 公式形态
（=NPV(rate, CF1:CFn) + TV/(1+rate)^n 与 =IRR(CF0:CFn)）作业务面交叉对照非唯一
源；禁用被测引擎自身生成 expected（循环自证红线）。

Excel 公式形态对照（业务面注记）：
- NPV: =NPV(rate, CF1:CFn) + TV/(1+rate)^n（年末贴现口径——t=1..n）
- 永续增长终值: =CF_n*(1+g)/(r-g)
- 退出倍数终值: =exit_multiple*终年 EBITDA
- IRR: =IRR(CF0:CFn)（仅显性现金流——不含终值）

Run with:
    poetry run pytest tests/unit/domain/services/test_financial_modeling.py -v
"""

from __future__ import annotations

import json
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from src.domain.value_objects.financial_valuation import (
    CashFlow,
    CashFlowSchedule,
    ComparableCompany,
    ComparableSet,
    DcfAssumptions,
    PrecedentTransaction,
    PrecedentTransactionSet,
)

#: Excel 基准对齐容差（单源定义——集成 re-export / 验收 import 链取值禁双真源；
#: epics L1971 钦定 0.01%）
EXCEL_ALIGNMENT_TOLERANCE = Decimal("0.0001")

#: 测试侧精确重算精度（与引擎一致 prec=50——精确相等断言前提：present_values 是
#: 50 位商，默认 prec=28 求和/做除法必截断使精确相等断言假红）
_TEST_PRECISION = 50

_BENCHMARK_PATH = Path(__file__).parent / "financial_test_cases.json"


def _load_cases(section: str) -> list[dict[str, Any]]:
    """加载基准用例集（只读消费——禁修改回写）。"""
    with _BENCHMARK_PATH.open(encoding="utf-8") as file_handle:
        payload: dict[str, Any] = json.load(file_handle)
    return list(payload[section])


def _build_schedule(case_input: dict[str, Any]) -> CashFlowSchedule:
    """现金流表 VO 构造（period int + amount str→Decimal wire 形态）。"""
    return CashFlowSchedule(
        cash_flows=tuple(
            CashFlow(period=int(item["period"]), amount=Decimal(item["amount"])) for item in case_input["cash_flows"]
        )
    )


def _build_assumptions(case_input: dict[str, Any]) -> DcfAssumptions:
    """折现假设 VO 构造（两法参数按 terminal_value_method 分派）。"""
    method = str(case_input["terminal_value_method"])
    kwargs: dict[str, Any] = {
        "discount_rate": Decimal(case_input["discount_rate"]),
        "terminal_value_method": method,
    }
    if method == "perpetual_growth":
        kwargs["terminal_growth_rate"] = Decimal(case_input["terminal_growth_rate"])
    else:
        kwargs["exit_multiple"] = Decimal(case_input["exit_multiple"])
        kwargs["terminal_exit_metric"] = Decimal(case_input["terminal_exit_metric"])
    return DcfAssumptions(**kwargs)


# ==== Fraction 独立精确复算 helpers（基准生成主源——非被测引擎） ====


def _frac_terminal_value(case_input: dict[str, Any]) -> Fraction:
    """终值封闭式复算（永续增长 CF_n×(1+g)/(r−g) / 退出倍数 exit_multiple×终年 EBITDA）。"""
    final_amount = Fraction(case_input["cash_flows"][-1]["amount"])
    if case_input["terminal_value_method"] == "perpetual_growth":
        growth = Fraction(case_input["terminal_growth_rate"])
        rate = Fraction(case_input["discount_rate"])
        return final_amount * (Fraction(1) + growth) / (rate - growth)
    return Fraction(case_input["exit_multiple"]) * Fraction(case_input["terminal_exit_metric"])


def _frac_present_value(case_input: dict[str, Any], period_index: int) -> Fraction:
    """单期现值封闭式复算（PV_t = CF_t/(1+r)^t——年末贴现口径）。"""
    amount = Fraction(case_input["cash_flows"][period_index]["amount"])
    period = int(case_input["cash_flows"][period_index]["period"])
    discount_base = Fraction(1) + Fraction(case_input["discount_rate"])
    return amount / discount_base**period


def _frac_npv(case_input: dict[str, Any]) -> Fraction:
    """NPV 封闭式复算（Σ PV_t + TV/(1+r)^n——Fraction 逐项无舍入）。"""
    total = sum(
        (_frac_present_value(case_input, index) for index in range(len(case_input["cash_flows"]))),
        Fraction(0),
    )
    discount_base = Fraction(1) + Fraction(case_input["discount_rate"])
    period_count = len(case_input["cash_flows"])
    return total + _frac_terminal_value(case_input) / discount_base**period_count


def _frac_to_decimal(value: Fraction) -> Decimal:
    """Fraction → Decimal（测试侧 60 位精度换算——消费面均为相对误差比较，位数充裕）。"""
    with localcontext() as decimal_context:
        decimal_context.prec = 60
        quotient: Decimal = Decimal(int(value.numerator)) / Decimal(int(value.denominator))
        return quotient


# ==== 循环 A: DCF NPV + 终值两法（Excel 基准对齐） ====

#: DCF 基准用例模块级加载（parametrize 动态生成——CR1-5：由用例数驱动参数化，
#: 防硬编码 range(4) 与 JSON 增删用例静默漂移）
_ALL_DCF_CASES = _load_cases("dcf_cases")


class TestDcfNpv:
    """calculate_dcf NPV/终值/present_values 基准对齐（循环 A——本批不断言 irr）。"""

    @pytest.fixture
    def service(self) -> Any:
        """手工直调构造（无状态纯计算服务）。"""
        from src.domain.services.financial_modeling import FinancialModelingService

        return FinancialModelingService()

    @pytest.fixture
    def dcf_cases(self) -> list[dict[str, Any]]:
        """DCF 基准用例集（4 条：两终值法各≥1 + 常规 + 零值序列）。"""
        cases = _load_cases("dcf_cases")
        methods = {str(case["input"]["terminal_value_method"]) for case in cases}
        assert {"perpetual_growth", "exit_multiple"} <= methods, "基准应覆盖两终值法各至少一例"
        return cases

    def test_benchmark_terminal_value_alignment(self, service: Any, dcf_cases: list[dict[str, Any]]) -> None:
        """终值对齐（未折现名义值——Fraction 复算主源 + JSON 静态值双源一致性）。"""
        for case in dcf_cases:
            case_input = case["input"]
            result = service.calculate_dcf(_build_schedule(case_input), _build_assumptions(case_input))
            expected_frac = _frac_terminal_value(case_input)
            assert (
                abs(result.terminal_value - _frac_to_decimal(expected_frac)) / abs(_frac_to_decimal(expected_frac))
                < EXCEL_ALIGNMENT_TOLERANCE
            ), f"终值与 Fraction 复算不齐: {case['name']}"
            expected_json = Decimal(case["expected"]["terminal_value"])
            assert abs(result.terminal_value - expected_json) / abs(expected_json) < EXCEL_ALIGNMENT_TOLERANCE, (
                f"终值与 JSON 基准不齐: {case['name']}"
            )

    def test_benchmark_npv_alignment(self, service: Any, dcf_cases: list[dict[str, Any]]) -> None:
        """NPV 对齐（Fraction 复算主源 + JSON 静态值双源一致性——Excel =NPV()+TV 折现形态）。"""
        for case in dcf_cases:
            case_input = case["input"]
            result = service.calculate_dcf(_build_schedule(case_input), _build_assumptions(case_input))
            expected_frac = _frac_to_decimal(_frac_npv(case_input))
            assert abs(result.npv - expected_frac) / abs(expected_frac) < EXCEL_ALIGNMENT_TOLERANCE, (
                f"NPV 与 Fraction 复算不齐: {case['name']}"
            )
            expected_json = Decimal(case["expected"]["npv"])
            assert abs(result.npv - expected_json) / abs(expected_json) < EXCEL_ALIGNMENT_TOLERANCE, (
                f"NPV 与 JSON 基准不齐: {case['name']}"
            )

    @pytest.mark.parametrize(
        "case_index",
        range(len(_ALL_DCF_CASES)),
        ids=[str(case["name"]) for case in _ALL_DCF_CASES],
    )
    def test_present_values_per_period(self, service: Any, dcf_cases: list[dict[str, Any]], case_index: int) -> None:
        """逐期现值独立断言（PV_t = CF_t/(1+r)^t 逐项对齐——可观测中间量；
        参数化由基准 JSON 用例数动态驱动[CR1-5]）。"""
        case = dcf_cases[case_index]
        case_input = case["input"]
        result = service.calculate_dcf(_build_schedule(case_input), _build_assumptions(case_input))
        assert len(result.present_values) == len(case_input["cash_flows"])
        for period_index in range(len(case_input["cash_flows"])):
            expected_pv = _frac_to_decimal(_frac_present_value(case_input, period_index))
            actual_pv = result.present_values[period_index]
            if expected_pv == 0:
                # 零现金流成员的现值恰为 0（精确相等——相对误差断言分母纪律不适用）
                assert actual_pv == 0, f"第 {period_index + 1} 期零现值应精确为 0: {case['name']}"
                continue
            assert abs(actual_pv - expected_pv) / abs(expected_pv) < EXCEL_ALIGNMENT_TOLERANCE, (
                f"第 {period_index + 1} 期现值不齐: {case['name']}"
            )

    def test_npv_decomposition_anchor(self, service: Any, dcf_cases: list[dict[str, Any]]) -> None:
        """NPV 分解自洽锚（npv == ΣPV + TV/(1+r)^n 精确相等——同源算术分解内部自洽；
        测试侧重算包 localcontext prec=50 钦定前提）。"""
        one = Decimal(1)
        for case in dcf_cases:
            case_input = case["input"]
            result = service.calculate_dcf(_build_schedule(case_input), _build_assumptions(case_input))
            rate = Decimal(case_input["discount_rate"])
            period_count = len(case_input["cash_flows"])
            with localcontext() as decimal_context:
                decimal_context.prec = _TEST_PRECISION
                recomposed = sum(result.present_values, Decimal(0)) + result.terminal_value / (one + rate) ** period_count
            assert recomposed == result.npv, f"NPV 分解自洽锚失败: {case['name']}"

    def test_terminal_value_weight_semantics(self, service: Any, dcf_cases: list[dict[str, Any]]) -> None:
        """weight == TV/(1+r)^n/npv（折现终值占比口径——基准选例 npv>0 且 ΣPV>0 使 weight∈(0,1)）。"""
        one = Decimal(1)
        for case in dcf_cases:
            case_input = case["input"]
            result = service.calculate_dcf(_build_schedule(case_input), _build_assumptions(case_input))
            rate = Decimal(case_input["discount_rate"])
            period_count = len(case_input["cash_flows"])
            with localcontext() as decimal_context:
                decimal_context.prec = _TEST_PRECISION
                expected_weight = result.terminal_value / (one + rate) ** period_count / result.npv
            assert result.terminal_value_weight == expected_weight, f"weight 口径失败: {case['name']}"
            assert Decimal(0) < result.terminal_value_weight < Decimal(1), f"常规形态基准 weight 应落于 (0,1): {case['name']}"

    def test_decimal_string_roundtrip_precision(self, service: Any, dcf_cases: list[dict[str, Any]]) -> None:
        """str→Decimal→引擎→str 回读精确（Decimal 字符串构造纪律锚——零 float 中转）。"""
        case = dcf_cases[0]
        result = service.calculate_dcf(_build_schedule(case["input"]), _build_assumptions(case["input"]))
        npv_string = str(result.npv)
        assert Decimal(npv_string) == result.npv, "str 回读应精确相等（Decimal 无损序列化）"
        assert isinstance(result.npv, Decimal) and isinstance(result.irr, Decimal)

    @pytest.mark.parametrize(
        "case_input",
        [
            # 形态一（TV=0 → 0/0 InvalidOperation）：末位 CF=0 使 TV=0；−100/1.1 与
            # 110/1.21 同为 ±1000/11 循环小数，prec=50 下正确舍入值精确抵消 → ΣPV=0
            {
                "cash_flows": [
                    {"period": 1, "amount": "-100"},
                    {"period": 2, "amount": "110"},
                    {"period": 3, "amount": "0"},
                ],
                "discount_rate": "0.1",
                "terminal_value_method": "perpetual_growth",
                "terminal_growth_rate": "0.02",
            },
            # 形态二（TV≠0 → x/0 DivisionByZero）：ΣPV=−5/1.25+5/1.5625=−4+3.2=−0.8，
            # 折现 TV=1.25/1.5625=+0.8 → npv 精确为 0 而 TV=1.25≠0（防守卫只挡 TV=0 特例）
            {
                "cash_flows": [
                    {"period": 1, "amount": "-5"},
                    {"period": 2, "amount": "5"},
                ],
                "discount_rate": "0.25",
                "terminal_value_method": "exit_multiple",
                "exit_multiple": "0.5",
                "terminal_exit_metric": "2.5",
            },
        ],
        ids=["tv_zero_invalid_operation", "tv_nonzero_division_by_zero"],
    )
    def test_zero_npv_raises_470(self, service: Any, case_input: dict[str, Any]) -> None:
        """npv=0（盈亏平衡精确抵消输入）→ 470 fail-loud 三段式（CR1-1——weight 分母
        失效是 470 双触发路径之二；两种除零形态双构造防守卫只挡其一的假绿）。"""
        from src.domain.exceptions import FinancialCalculationError

        with pytest.raises(FinancialCalculationError) as exc_info:
            service.calculate_dcf(_build_schedule(case_input), _build_assumptions(case_input))
        assert exc_info.value.code == "EXCEPTION_470"
        assert exc_info.value.context["method"] == "dcf"
        assert "NPV" in exc_info.value.context["detail"], "detail 应陈述 NPV 为零的计算事实"


# ==== 循环 B: IRR 二分法（基准对齐 + 零成员序列 + bracket 失败 470） ====


class TestDcfIrr:
    """_solve_irr 二分法求解（bracket 前提 + 1e-12 收敛 + 256 次上限）。"""

    @pytest.fixture
    def service(self) -> Any:
        """手工直调构造。"""
        from src.domain.services.financial_modeling import FinancialModelingService

        return FinancialModelingService()

    @pytest.fixture
    def dcf_cases(self) -> list[dict[str, Any]]:
        """DCF 基准用例集（IRR 用例限单符号变更序列——根唯一无歧义）。"""
        return _load_cases("dcf_cases")

    def _calculate_irr(self, service: Any, case_input: dict[str, Any]) -> Any:
        """基准用例 IRR 计算便捷通道。"""
        result = service.calculate_dcf(_build_schedule(case_input), _build_assumptions(case_input))
        return result.irr

    def test_benchmark_irr_alignment(self, service: Any, dcf_cases: list[dict[str, Any]]) -> None:
        """IRR 基准对齐（JSON expected = 独立 Decimal 200 位二分产物——引擎侧相对误差 ~1e-11 对 1e-4 容差约 7 个数量级余量）。"""
        for case in dcf_cases:
            irr = self._calculate_irr(service, case["input"])
            expected_irr = Decimal(case["expected"]["irr"])
            assert abs(irr - expected_irr) / abs(expected_irr) < EXCEL_ALIGNMENT_TOLERANCE, (
                f"IRR 相对误差越限: {case['name']} 实际 {irr} 期望 {expected_irr}"
            )

    def test_zero_member_sequence_irr_closed_form(self, service: Any) -> None:
        """零成员序列 [−100, 0, 110] IRR = √1.1−1（闭式解——非零子序列单符号变更根唯一）。"""
        case_input = {
            "cash_flows": [
                {"period": 1, "amount": "-100"},
                {"period": 2, "amount": "0"},
                {"period": 3, "amount": "110"},
            ],
            "discount_rate": "0.1",
            "terminal_value_method": "perpetual_growth",
            "terminal_growth_rate": "0.02",
        }
        irr = self._calculate_irr(service, case_input)
        # 闭式解：−100/(1+r) + 110/(1+r)^3 = 0 → (1+r)^2 = 1.1 → IRR = √1.1 − 1
        with localcontext() as decimal_context:
            decimal_context.prec = _TEST_PRECISION
            expected_irr = Decimal("1.1").sqrt() - Decimal(1)
        assert abs(irr - expected_irr) / abs(expected_irr) < EXCEL_ALIGNMENT_TOLERANCE, (
            f"零成员序列 IRR 应为 √1.1−1 ≈ 0.0488，实际 {irr}"
        )

    def test_known_exact_solution_convergence(self, service: Any) -> None:
        """已知精确解收敛锚（(−100, 110) → IRR=0.1——平移不变性下 period≥1 口径同解）。"""
        case_input = {
            "cash_flows": [
                {"period": 1, "amount": "-100"},
                {"period": 2, "amount": "110"},
            ],
            "discount_rate": "0.1",
            "terminal_value_method": "perpetual_growth",
            "terminal_growth_rate": "0.02",
        }
        irr = self._calculate_irr(service, case_input)
        expected_irr = Decimal("0.1")
        assert abs(irr - expected_irr) / abs(expected_irr) < Decimal("1e-11"), (
            f"已知精确解应收敛到 0.1（1e-12 区间宽度判据下 ~1e-11 量级），实际 {irr}"
        )

    def test_bracket_failure_raises_470(self, service: Any) -> None:
        """病态序列 [−100, 230, −132] bracket 端点同号 → 470 三段式（fail-loud 审计语义——
        双根序列 r=0.1/0.2 均在区间内，端点符号检验探测不到，正是其盲区的实证用例）。"""
        from src.domain.exceptions import FinancialCalculationError

        case_input = {
            "cash_flows": [
                {"period": 1, "amount": "-100"},
                {"period": 2, "amount": "230"},
                {"period": 3, "amount": "-132"},
            ],
            "discount_rate": "0.1",
            "terminal_value_method": "perpetual_growth",
            "terminal_growth_rate": "0.02",
        }
        with pytest.raises(FinancialCalculationError) as exc_info:
            service.calculate_dcf(_build_schedule(case_input), _build_assumptions(case_input))
        assert exc_info.value.code == "EXCEPTION_470"
        assert exc_info.value.context["method"] == "dcf"
        assert exc_info.value.context["detail"], "detail 应携求解失败描述"

    def test_no_root_sequence_bracket_failure_raises_470(self, service: Any) -> None:
        """无根形态 bracket 失败（[−100, 0.0001, −110]——CR1-6：P(x)=x(−100+0.0001x−110x²)
        判别式 1e-8−44000<0 对 x>0 恒负 → 端点同号无任何正根；VO 非零子序列两处符号
        变更放行、引擎 470 兜底——与 VO docstring 分工声明测试闭环）。"""
        from src.domain.exceptions import FinancialCalculationError

        case_input = {
            "cash_flows": [
                {"period": 1, "amount": "-100"},
                {"period": 2, "amount": "0.0001"},
                {"period": 3, "amount": "-110"},
            ],
            "discount_rate": "0.1",
            "terminal_value_method": "perpetual_growth",
            "terminal_growth_rate": "0.02",
        }
        with pytest.raises(FinancialCalculationError) as exc_info:
            service.calculate_dcf(_build_schedule(case_input), _build_assumptions(case_input))
        assert exc_info.value.code == "EXCEPTION_470"
        assert exc_info.value.context["method"] == "dcf"
        assert exc_info.value.context["detail"], "detail 应携求解失败描述"

    def test_underflow_both_endpoints_zero_raises_470(self, service: Any) -> None:
        """全下溢显性现金流 → IRR 两端同零特判 470（CR3-1③——防静默错误 IRR：
        显性 CF=[−1E-1000460, +1E-1000460] 全下溢为 ±0 时，无特判则二分退化收敛
        rate_low 端点返回 IRR=−0.99 而数学真值 0；exit_multiple 法使 TV 正常
        npv≠0 走到 IRR 路径[perpetual 法同构造会被 npv==0 守卫先行拦截]）。"""
        from src.domain.exceptions import FinancialCalculationError

        case_input = {
            "cash_flows": [
                {"period": 1, "amount": "-1E-1000460"},
                {"period": 2, "amount": "1E-1000460"},
            ],
            "discount_rate": "0.1",
            "terminal_value_method": "exit_multiple",
            "exit_multiple": "8.5",
            "terminal_exit_metric": "70",
        }
        with pytest.raises(FinancialCalculationError) as exc_info:
            service.calculate_dcf(_build_schedule(case_input), _build_assumptions(case_input))
        assert exc_info.value.code == "EXCEPTION_470"
        assert exc_info.value.context["method"] == "dcf"
        assert "同时为零" in exc_info.value.context["detail"], "detail 应陈述端点同零双因（全下溢或双根歧义）"

    def test_max_iterations_defense_branch(self, service: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        """迭代上限防御分支（monkeypatch 压缩 _IRR_MAX_ITERATIONS=2 → 区间未收敛即 470——
        正常收敛约 44 次，256 是防御分支经本路径触发覆盖）。"""
        from src.domain import services as services_module
        from src.domain.exceptions import FinancialCalculationError

        case_input = {
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
        }
        monkeypatch.setattr(services_module.financial_modeling, "_IRR_MAX_ITERATIONS", 2)
        with pytest.raises(FinancialCalculationError) as exc_info:
            service.calculate_dcf(_build_schedule(case_input), _build_assumptions(case_input))
        assert exc_info.value.code == "EXCEPTION_470"
        assert exc_info.value.context["method"] == "dcf"

    def test_bisection_constants_single_source(self) -> None:
        """二分法参数常量断言（r_lo/r_hi/收敛判据/迭代上限——参数面锚）。"""
        from src.domain.services.financial_modeling import (
            _IRR_INTERVAL_TOLERANCE,
            _IRR_MAX_ITERATIONS,
            _IRR_RATE_HIGH,
            _IRR_RATE_LOW,
        )

        assert _IRR_RATE_LOW == Decimal("-0.99"), "bracket 下界钦定 −0.99（支持域 IRR>−99%）"
        assert _IRR_RATE_HIGH == Decimal("10"), "bracket 上界钦定 10（支持域 IRR<1000%）"
        assert _IRR_INTERVAL_TOLERANCE == Decimal("1e-12"), "收敛判据钦定区间宽度 1e-12"
        assert _IRR_MAX_ITERATIONS == 256, "迭代上限钦定 256（正常收敛约 44 次——防御分支）"


# ==== 循环 A（Task 4）: 可比公司与先例交易统计引擎 ====


def _frac_stats(multiples: list[str]) -> dict[str, Fraction]:
    """倍数统计四值封闭式复算（Excel MIN/MEDIAN/AVERAGE/MAX——Fraction 精确）。"""
    values = sorted(Fraction(m) for m in multiples)
    count = len(values)
    median = values[count // 2] if count % 2 == 1 else (values[count // 2 - 1] + values[count // 2]) / 2
    return {
        "min": values[0],
        "median": median,
        "mean": sum(values, Fraction(0)) / count,
        "max": values[-1],
    }


class TestComparableValuation:
    """calculate_comparable_valuation 统计四值 + 隐含区间（含偶数样本 median 语义）。"""

    @pytest.fixture
    def service(self) -> Any:
        """手工直调构造。"""
        from src.domain.services.financial_modeling import FinancialModelingService

        return FinancialModelingService()

    @pytest.fixture
    def comparable_cases(self) -> list[dict[str, Any]]:
        """可比基准用例集（2 条：奇偶样本各 1）。"""
        cases = _load_cases("comparable_cases")
        parities = {len(case["input"]["comparables"]) % 2 for case in cases}
        assert parities == {0, 1}, "基准应含奇偶样本各至少一例"
        return cases

    def test_multiples_stats_alignment(self, service: Any, comparable_cases: list[dict[str, Any]]) -> None:
        """统计四值对齐（Fraction 复算主源 + JSON 静态值双源——Excel MIN/MEDIAN/AVERAGE/MAX）。"""
        for case in comparable_cases:
            case_input = case["input"]
            result = service.calculate_comparable_valuation(
                ComparableSet(
                    comparables=tuple(
                        ComparableCompany(name=str(item["name"]), ev_ebitda=Decimal(item["ev_ebitda"]))
                        for item in case_input["comparables"]
                    )
                ),
                Decimal(case_input["target_ebitda"]),
            )
            expected_frac = _frac_stats([item["ev_ebitda"] for item in case_input["comparables"]])
            expected_json = case["expected"]["multiples"]
            for stat_name in ("min", "median", "mean", "max"):
                frac_value = _frac_to_decimal(expected_frac[stat_name])
                assert abs(getattr(result.multiples_stats, stat_name) - frac_value) / abs(frac_value) < (
                    EXCEL_ALIGNMENT_TOLERANCE
                ), f"统计值 {stat_name} 与 Fraction 复算不齐: {case['name']}"
                json_value = Decimal(expected_json[stat_name])
                assert abs(getattr(result.multiples_stats, stat_name) - json_value) / abs(json_value) < (
                    EXCEL_ALIGNMENT_TOLERANCE
                ), f"统计值 {stat_name} 与 JSON 基准不齐: {case['name']}"

    def test_implied_ev_exact_multiplication(self, service: Any, comparable_cases: list[dict[str, Any]]) -> None:
        """隐含区间三值精确相等（同源 Decimal 乘法——测试侧算术包 localcontext prec=50）。"""
        for case in comparable_cases:
            case_input = case["input"]
            result = service.calculate_comparable_valuation(
                ComparableSet(
                    comparables=tuple(
                        ComparableCompany(name=str(item["name"]), ev_ebitda=Decimal(item["ev_ebitda"]))
                        for item in case_input["comparables"]
                    )
                ),
                Decimal(case_input["target_ebitda"]),
            )
            target = Decimal(case_input["target_ebitda"])
            with localcontext() as decimal_context:
                decimal_context.prec = _TEST_PRECISION
                assert result.implied_ev_low == result.multiples_stats.min * target, f"隐含 low 精确相等失败: {case['name']}"
                assert result.implied_ev_median == result.multiples_stats.median * target, (
                    f"隐含 median 精确相等失败: {case['name']}"
                )
                assert result.implied_ev_high == result.multiples_stats.max * target, f"隐含 high 精确相等失败: {case['name']}"

    def test_even_sample_median_semantics(self, service: Any) -> None:
        """偶数样本 median 语义（4 家可比——中间两数均值：median(8.5,10.2,12.8,15.0)=11.5）。"""
        result = service.calculate_comparable_valuation(
            ComparableSet(
                comparables=(
                    ComparableCompany(name="甲", ev_ebitda=Decimal("8.5")),
                    ComparableCompany(name="乙", ev_ebitda=Decimal("10.2")),
                    ComparableCompany(name="丙", ev_ebitda=Decimal("12.8")),
                    ComparableCompany(name="丁", ev_ebitda=Decimal("15.0")),
                )
            ),
            Decimal("120"),
        )
        assert result.multiples_stats.median == Decimal("11.5"), "偶数样本 median 应取中间两数均值 11.5"


class TestPrecedentValuation:
    """calculate_precedent_valuation 对价倍数统计 + 参考区间（与可比引擎同构独立断言）。"""

    @pytest.fixture
    def service(self) -> Any:
        """手工直调构造。"""
        from src.domain.services.financial_modeling import FinancialModelingService

        return FinancialModelingService()

    @pytest.fixture
    def precedent_cases(self) -> list[dict[str, Any]]:
        """先例基准用例集（2 条：奇偶样本各 1）。"""
        cases = _load_cases("precedent_cases")
        parities = {len(case["input"]["transactions"]) % 2 for case in cases}
        assert parities == {0, 1}, "基准应含奇偶样本各至少一例"
        return cases

    def test_precedent_stats_alignment(self, service: Any, precedent_cases: list[dict[str, Any]]) -> None:
        """先例统计四值 + 参考区间同口径对齐（与可比引擎同构——一次覆盖）。"""
        for case in precedent_cases:
            case_input = case["input"]
            result = service.calculate_precedent_valuation(
                PrecedentTransactionSet(
                    transactions=tuple(
                        PrecedentTransaction(target_name=str(item["target_name"]), ev_ebitda=Decimal(item["ev_ebitda"]))
                        for item in case_input["transactions"]
                    )
                ),
                Decimal(case_input["target_ebitda"]),
            )
            expected_frac = _frac_stats([item["ev_ebitda"] for item in case_input["transactions"]])
            expected_json = case["expected"]
            target = Decimal(case_input["target_ebitda"])
            for stat_name in ("min", "median", "mean", "max"):
                frac_value = _frac_to_decimal(expected_frac[stat_name])
                assert abs(getattr(result.multiples_stats, stat_name) - frac_value) / abs(frac_value) < (
                    EXCEL_ALIGNMENT_TOLERANCE
                ), f"先例统计值 {stat_name} 与 Fraction 复算不齐: {case['name']}"
                json_value = Decimal(expected_json["multiples"][stat_name])
                assert abs(getattr(result.multiples_stats, stat_name) - json_value) / abs(json_value) < (
                    EXCEL_ALIGNMENT_TOLERANCE
                ), f"先例统计值 {stat_name} 与 JSON 基准不齐: {case['name']}"
            with localcontext() as decimal_context:
                decimal_context.prec = _TEST_PRECISION
                assert result.implied_ev_low == result.multiples_stats.min * target
                assert result.implied_ev_median == result.multiples_stats.median * target
                assert result.implied_ev_high == result.multiples_stats.max * target
