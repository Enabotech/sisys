"""验收测试：Story 5.12 财务建模与估值基础。

模板基准: test_acceptance_sap_protocol.py（R6 现代形态——多行 @scenario 字面量路径 +
场景绑定与步骤实现交替排列 + AC 横幅分组）。本 Story 裁剪注记：全同步交付面
（execute/引擎/性能采样全同步——R6 改造三件套中 event_loop/_run_async 两件不适用
纯同步步骤，省略不引入；context dict fixture 单件保留——5-11 形态裁剪）。纯计算
零外部服务依赖（零 Redis/PG/LLM/Docker——零探测零 skip 全场景可跑；替身仅限
单测层，验收全部真实服务直调：引擎真算 + 组合根 resolve 全链）。

13 场景三属性分档表（外部服务依赖 / 前置状态 / 断言面）:
| 场景 | 外部服务依赖 | 前置状态（Given 装配） | 断言面（Then） |
| AC-1.1 NPV+终值两法对齐 | 无 | 手工服务 + JSON 基准 | 相对误差<0.0001 + 分解自洽锚 + weight∈(0,1) |
| AC-1.2 IRR 对齐 | 无 | 手工服务 + JSON 基准 | IRR 相对误差 + 精确解收敛锚 |
| AC-1.3 DCF 异常三层 | 无 | 手工服务 | 242×2 三段式 + 470 三段式 |
| AC-2.1 可比统计+区间 | 无 | 手工服务 + JSON 基准 | 统计四值 + 隐含区间精确相等 |
| AC-2.2 先例统计+区间 | 无 | 手工服务 + JSON 基准 | 同构独立断言 |
| AC-2.3 集合异常 | 无 | 手工服务 | 空集合/非正倍数 242 |
| AC-3.1 合法构造 | 无 | Schema 族 | 精确解析 + 四 VO 转换 |
| AC-3.2 六类非法 | 无 | Schema 族 | pydantic ValidationError |
| AC-4.1 组合根接线 | 无（bootstrap 注册表） | bootstrap | resolve 四件 + 注入链 |
| AC-4.2 编排零变换 | 无 | resolve 用例 | 三段逐一相等 + 470 上抛 + 三零 |
| AC-5.1 延迟+精度 | 无（进程内委托计时） | _PERF_CACHE 委托 | <5s + <0.0001 + 正向锚 21 |
| AC-5.2 并发 10 | 无 | _PERF_CACHE 委托 | 10/10 + 隔离 + 确定性 |
| 收尾 完成清单 | 无 | 交付完成 | src 六件 + tests 十件 + 注册联动 |

marker 分档: 文件名 financial 不命中 conftest 服务关键词映射（仅自动挂
acceptance——纯计算零外部服务，全部场景可跑零 skip）；xdist_group 与集成计时
逐字同组 financial-modeling-perf（loadgroup 同 worker 串行是 _PERF_CACHE 命中前提）。

延迟 import 纪律: 模块顶部仅 stdlib+pytest+pytest_bdd；本 Story 新交付模块
（VO/引擎/异常/Schema/用例/集成常量与 helper）一律步骤函数体内 import——Task 0-5
窗口期为运行期 ModuleNotFoundError 逐场景 failed 非 collection error（5-11 先例）。

Run with:
    poetry run pytest tests/acceptance/test_acceptance_financial_modeling.py -v
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenario, then, when

pytestmark = [
    pytest.mark.acceptance,
    pytest.mark.xdist_group("financial-modeling-perf"),
]


@pytest.fixture
def context() -> Generator[dict[str, Any], None, None]:
    """场景级共享上下文（dict 形态——全同步交付面无事件循环与环境依赖）。"""
    ctx: dict[str, Any] = {}
    yield ctx


def _load_benchmark_cases(section: str) -> list[dict[str, Any]]:
    """加载 Excel 基准用例集（只读消费——禁修改回写；OD-7 落位单测目录旁）。"""
    json_path = Path(__file__).resolve().parents[1] / "unit" / "domain" / "services" / "financial_test_cases.json"
    with json_path.open(encoding="utf-8") as file_handle:
        payload: dict[str, Any] = json.load(file_handle)
    return list(payload[section])


def _build_schedule(case_input: dict[str, Any]) -> Any:
    """现金流表 VO 构造（延迟 import——period int + amount str→Decimal 钦定形态）。"""
    from decimal import Decimal

    from src.domain.value_objects.financial_valuation import CashFlow, CashFlowSchedule

    return CashFlowSchedule(
        cash_flows=tuple(
            CashFlow(period=int(item["period"]), amount=Decimal(item["amount"])) for item in case_input["cash_flows"]
        )
    )


def _build_assumptions(case_input: dict[str, Any]) -> Any:
    """折现假设 VO 构造（perpetual_growth 携 g / exit_multiple 携倍数+终年 EBITDA）。"""
    from decimal import Decimal

    from src.domain.value_objects.financial_valuation import DcfAssumptions

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


# ==== AC-1: DCF 现金流折现引擎（NPV + 终值两法 + IRR） ====


@scenario(
    "test_acceptance_financial_modeling.feature",
    "AC-1.1 - DCF NPV 与终值两法 Excel 基准对齐",
)
def test_ac_1_1_npv_terminal_alignment(context: dict[str, Any]) -> None:
    """AC-1.1: NPV/终值相对误差 + 分解自洽锚 + 终值占比三面（两终值法各≥1 例）。"""


@scenario(
    "test_acceptance_financial_modeling.feature",
    "AC-1.2 - IRR 二分法求解与 Excel 基准对齐",
)
def test_ac_1_2_irr_alignment(context: dict[str, Any]) -> None:
    """AC-1.2: IRR 相对误差（限单符号变更序列）+ 已知精确解收敛锚（含零成员序列）。"""


@scenario(
    "test_acceptance_financial_modeling.feature",
    "AC-1.3 - DCF 异常路径三层三段式",
)
def test_ac_1_3_dcf_exception_paths(context: dict[str, Any]) -> None:
    """AC-1.3: 无符号变更 242 + g≥r 242 + 病态 bracket 470 三段式。"""


@given("手工实例化 FinancialModelingService 并加载 DCF 基准用例集")
def given_service_with_dcf_cases(context: dict[str, Any]) -> None:
    """手工直调构造（无状态纯计算服务——验收/单测均手工实例化，组合根 resolve 在 AC-4 面）。"""
    from src.domain.services.financial_modeling import FinancialModelingService

    context["service"] = FinancialModelingService()
    context["dcf_cases"] = _load_benchmark_cases("dcf_cases")


@when("逐例构造现金流表与折现假设并执行 DCF 计算（永续增长与退出倍数两法各至少一例）")
def when_run_dcf_cases(context: dict[str, Any]) -> None:
    """逐例执行（VO 构造即验——两法覆盖断言是基准集形态守卫）。"""
    methods_seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for case in context["dcf_cases"]:
        case_input: dict[str, Any] = case["input"]
        result = context["service"].calculate_dcf(_build_schedule(case_input), _build_assumptions(case_input))
        results.append({"case": case, "result": result})
        methods_seen.add(str(case_input["terminal_value_method"]))
    assert {"perpetual_growth", "exit_multiple"} <= methods_seen, "基准集应覆盖两终值法各至少一例"
    context["dcf_results"] = results


@then("NPV 与终值相对误差均在 0.0001 内（Decimal 域相对误差断言）")
def then_npv_terminal_aligned(context: dict[str, Any]) -> None:
    """相对误差断言（Decimal 域零 pytest.approx——OD-5③；终值是未折现名义值）。"""
    from decimal import Decimal

    from tests.integration.test_integration_financial_modeling import EXCEL_ALIGNMENT_TOLERANCE

    assert str(EXCEL_ALIGNMENT_TOLERANCE) == "0.0001", "容差常量单源应为 0.0001"
    for entry in context["dcf_results"]:
        expected: dict[str, str] = entry["case"]["expected"]
        result = entry["result"]
        expected_npv = Decimal(expected["npv"])
        expected_tv = Decimal(expected["terminal_value"])
        assert abs(result.npv - expected_npv) / abs(expected_npv) < EXCEL_ALIGNMENT_TOLERANCE, (
            f"NPV 相对误差越限: {entry['case']['name']}"
        )
        assert abs(result.terminal_value - expected_tv) / abs(expected_tv) < EXCEL_ALIGNMENT_TOLERANCE, (
            f"终值相对误差越限: {entry['case']['name']}"
        )


@then("NPV 分解自洽锚成立（逐期现值之和加折现终值精确等于 NPV）")
def then_npv_decomposition_anchor(context: dict[str, Any]) -> None:
    """同源算术分解内部自洽（精确相等——测试侧重算包 localcontext prec=50 钦定前提）。"""
    from decimal import Decimal, localcontext

    for entry in context["dcf_results"]:
        case_input: dict[str, Any] = entry["case"]["input"]
        result = entry["result"]
        rate = Decimal(case_input["discount_rate"])
        period_count = len(case_input["cash_flows"])
        with localcontext() as decimal_context:
            decimal_context.prec = 50
            recomposed = sum(result.present_values, Decimal("0")) + result.terminal_value / (Decimal(1) + rate) ** period_count
        assert recomposed == result.npv, f"NPV 分解自洽锚失败: {entry['case']['name']}"


@then("终值占比等于折现终值除以 NPV 且落于 0 与 1 之间")
def then_terminal_weight_anchor(context: dict[str, Any]) -> None:
    """weight == TV/(1+r)^n/npv（折现终值占比口径——基准选例 npv>0 且 ΣPV>0 使 weight∈(0,1)）。"""
    from decimal import Decimal, localcontext

    for entry in context["dcf_results"]:
        case_input: dict[str, Any] = entry["case"]["input"]
        result = entry["result"]
        rate = Decimal(case_input["discount_rate"])
        period_count = len(case_input["cash_flows"])
        with localcontext() as decimal_context:
            decimal_context.prec = 50
            expected_weight = result.terminal_value / (Decimal(1) + rate) ** period_count / result.npv
        assert result.terminal_value_weight == expected_weight, f"终值占比口径失败: {entry['case']['name']}"
        assert Decimal(0) < result.terminal_value_weight < Decimal(1), (
            f"终值占比应落于 (0,1): {entry['case']['name']} 实际 {result.terminal_value_weight}"
        )


@given("手工实例化 FinancialModelingService 并加载 IRR 基准用例")
def given_service_with_irr_cases(context: dict[str, Any]) -> None:
    """IRR 基准与 DCF 基准同源（每条 dcf 用例含 expected.irr——限单符号变更序列）。"""
    from src.domain.services.financial_modeling import FinancialModelingService

    context["service"] = FinancialModelingService()
    context["irr_cases"] = _load_benchmark_cases("dcf_cases")


@when("逐例执行 DCF 计算并读取 IRR 字段（含零成员序列 -100 0 110）")
def when_run_irr_cases(context: dict[str, Any]) -> None:
    """逐例执行（零成员序列存在性是基准集形态守卫——Descartes 非零子序列计数锚）。"""
    results: list[dict[str, Any]] = []
    zero_member_seen = False
    for case in context["irr_cases"]:
        case_input: dict[str, Any] = case["input"]
        result = context["service"].calculate_dcf(_build_schedule(case_input), _build_assumptions(case_input))
        results.append({"case": case, "result": result})
        if any(item["amount"] == "0" for item in case_input["cash_flows"]):
            zero_member_seen = True
    assert zero_member_seen, "基准集应含零成员序列用例（[−100, 0, 110]）"
    context["irr_results"] = results


@then("IRR 相对误差均在 0.0001 内（限单符号变更序列根唯一无歧义）")
def then_irr_aligned(context: dict[str, Any]) -> None:
    """IRR 对齐（迭代解相对误差口径——基准是独立高精度求解产物非 Excel 输出）。"""
    from decimal import Decimal

    from tests.integration.test_integration_financial_modeling import EXCEL_ALIGNMENT_TOLERANCE

    for entry in context["irr_results"]:
        expected_irr = Decimal(entry["case"]["expected"]["irr"])
        assert abs(entry["result"].irr - expected_irr) / abs(expected_irr) < EXCEL_ALIGNMENT_TOLERANCE, (
            f"IRR 相对误差越限: {entry['case']['name']}"
        )


@then("已知精确解用例收敛（-100 110 的 IRR 精确收敛到 0.1 容差内）")
def then_irr_known_solution(context: dict[str, Any]) -> None:
    """闭式可解形态收敛锚（(−100, 110) → IRR=0.1——平移不变性下 period≥1 口径同解；
    容差经集成 re-export 链单源取值[CR1-7——禁字面量双真源]）。"""
    from decimal import Decimal

    from src.domain.value_objects.financial_valuation import CashFlow, CashFlowSchedule
    from tests.integration.test_integration_financial_modeling import EXCEL_ALIGNMENT_TOLERANCE

    schedule = CashFlowSchedule(
        cash_flows=(CashFlow(period=1, amount=Decimal("-100")), CashFlow(period=2, amount=Decimal("110")))
    )
    assumptions = _build_assumptions(
        {
            "cash_flows": [{"period": 1, "amount": "-100"}, {"period": 2, "amount": "110"}],
            "discount_rate": "0.1",
            "terminal_value_method": "perpetual_growth",
            "terminal_growth_rate": "0.02",
        }
    )
    result = context["service"].calculate_dcf(schedule, assumptions)
    expected_irr = Decimal("0.1")
    assert abs(result.irr - expected_irr) / abs(expected_irr) < EXCEL_ALIGNMENT_TOLERANCE, (
        f"已知精确解应收敛到 0.1，实际 {result.irr}"
    )


@given("手工实例化 FinancialModelingService")
def given_service_plain(context: dict[str, Any]) -> None:
    """异常路径前置（手工实例化——AC-2.3 同款 Given 文本复用）。"""
    from src.domain.services.financial_modeling import FinancialModelingService

    context["service"] = FinancialModelingService()


@when("构造无符号变更现金流与 g 不小于 r 假设及病态 bracket 序列并逐一触发")
def when_prepare_dcf_exception_payloads(context: dict[str, Any]) -> None:
    """三类非法/病态载体构造（VO 守卫与引擎求解失败的触发面在 Then 断言——三层异常语义分立）。"""
    context["no_sign_change_flows"] = [
        {"period": 1, "amount": "100"},
        {"period": 2, "amount": "50"},
    ]
    context["g_ge_r_assumptions"] = {
        "cash_flows": [{"period": 1, "amount": "-100"}, {"period": 2, "amount": "60"}],
        "discount_rate": "0.10",
        "terminal_value_method": "perpetual_growth",
        "terminal_growth_rate": "0.12",
    }
    context["pathological_flows"] = [
        {"period": 1, "amount": "-100"},
        {"period": 2, "amount": "230"},
        {"period": 3, "amount": "-132"},
    ]
    context["valid_assumptions"] = {
        "discount_rate": "0.1",
        "terminal_value_method": "perpetual_growth",
        "terminal_growth_rate": "0.02",
    }


@then("无符号变更与 g 不小于 r 各抛 242 且 context 字段逐项匹配")
def then_dcf_242_paths(context: dict[str, Any]) -> None:
    """VO 构造期守卫三段式（raises + code + context.field——EntityValidationError 242）。"""
    from decimal import Decimal

    from src.domain.exceptions import EntityValidationError
    from src.domain.value_objects.financial_valuation import CashFlow, CashFlowSchedule, DcfAssumptions

    with pytest.raises(EntityValidationError) as exc_info:
        CashFlowSchedule(
            cash_flows=tuple(
                CashFlow(period=int(item["period"]), amount=Decimal(item["amount"])) for item in context["no_sign_change_flows"]
            )
        )
    assert exc_info.value.code == "EXCEPTION_242"
    assert exc_info.value.context["field"] == "cash_flows", "无符号变更守卫 context 应携 field=cash_flows"

    g_ge_r = context["g_ge_r_assumptions"]
    with pytest.raises(EntityValidationError) as exc_info:
        DcfAssumptions(
            discount_rate=Decimal(g_ge_r["discount_rate"]),
            terminal_value_method=g_ge_r["terminal_value_method"],
            terminal_growth_rate=Decimal(g_ge_r["terminal_growth_rate"]),
        )
    assert exc_info.value.code == "EXCEPTION_242"
    assert exc_info.value.context["field"] == "terminal_growth_rate", "g≥r 守卫 context 应携 field=terminal_growth_rate"


@then("病态序列 IRR 求解失败抛 470 且 context 携 method 为 dcf")
def then_dcf_470_bracket_failure(context: dict[str, Any]) -> None:
    """fail-loud 审计语义（bracket 端点同号即 470——双根序列仅作触发用例非对齐用例）。"""
    from decimal import Decimal

    from src.domain.exceptions import FinancialCalculationError
    from src.domain.value_objects.financial_valuation import CashFlow, CashFlowSchedule, DcfAssumptions

    schedule = CashFlowSchedule(
        cash_flows=tuple(
            CashFlow(period=int(item["period"]), amount=Decimal(item["amount"])) for item in context["pathological_flows"]
        )
    )
    valid = context["valid_assumptions"]
    assumptions = DcfAssumptions(
        discount_rate=Decimal(valid["discount_rate"]),
        terminal_value_method=valid["terminal_value_method"],
        terminal_growth_rate=Decimal(valid["terminal_growth_rate"]),
    )
    with pytest.raises(FinancialCalculationError) as exc_info:
        context["service"].calculate_dcf(schedule, assumptions)
    assert exc_info.value.code == "EXCEPTION_470"
    assert exc_info.value.context["method"] == "dcf", "470 context 应携 method=dcf"


# ==== AC-2: 可比公司与先例交易引擎（倍数统计 + 隐含区间） ====


@scenario(
    "test_acceptance_financial_modeling.feature",
    "AC-2.1 - 可比公司倍数统计与隐含企业价值区间",
)
def test_ac_2_1_comparable_stats(context: dict[str, Any]) -> None:
    """AC-2.1: 统计四值相对误差 + 隐含区间精确相等（含偶数样本 median 语义）。"""


@scenario(
    "test_acceptance_financial_modeling.feature",
    "AC-2.2 - 先例交易倍数统计与隐含参考区间",
)
def test_ac_2_2_precedent_stats(context: dict[str, Any]) -> None:
    """AC-2.2: 先例统计与参考区间同构独立断言（交易对价倍数语义入口分立）。"""


@scenario(
    "test_acceptance_financial_modeling.feature",
    "AC-2.3 - 集合不变量异常路径",
)
def test_ac_2_3_set_invariants(context: dict[str, Any]) -> None:
    """AC-2.3: 空集合/非正倍数两类 VO 守卫 242（集合非空 + 倍数域正值不变量）。"""


@given("手工实例化 FinancialModelingService 并加载可比基准用例集")
def given_service_with_comparable_cases(context: dict[str, Any]) -> None:
    """可比基准前置（comparables 数组——奇偶样本各≥1）。"""
    from src.domain.services.financial_modeling import FinancialModelingService

    context["service"] = FinancialModelingService()
    context["comparable_cases"] = _load_benchmark_cases("comparable_cases")


@when("逐例构造可比集合并执行可比估值计算（含偶数样本 median 语义）")
def when_run_comparable_cases(context: dict[str, Any]) -> None:
    """逐例执行（偶数样本存在性是 median 语义守卫——中间两数均值）。"""
    from decimal import Decimal

    from src.domain.value_objects.financial_valuation import ComparableCompany, ComparableSet

    results: list[dict[str, Any]] = []
    even_sample_seen = False
    for case in context["comparable_cases"]:
        case_input: dict[str, Any] = case["input"]
        company_set = ComparableSet(
            comparables=tuple(
                ComparableCompany(name=str(item["name"]), ev_ebitda=Decimal(item["ev_ebitda"]))
                for item in case_input["comparables"]
            )
        )
        result = context["service"].calculate_comparable_valuation(company_set, Decimal(case_input["target_ebitda"]))
        results.append({"case": case, "result": result})
        if len(case_input["comparables"]) % 2 == 0:
            even_sample_seen = True
    assert even_sample_seen, "基准集应含偶数样本用例（median 中间两数均值语义）"
    context["comparable_results"] = results


@then("统计四值相对误差均在 0.0001 内（Excel MIN/MEDIAN/AVERAGE/MAX 对齐）")
def then_multiples_stats_aligned(context: dict[str, Any]) -> None:
    """统计四值对齐（min/median/mean/max——statistics 原生 Decimal 域）。"""
    from decimal import Decimal

    from tests.integration.test_integration_financial_modeling import EXCEL_ALIGNMENT_TOLERANCE

    for entry in context["comparable_results"]:
        expected_multiples: dict[str, str] = entry["case"]["expected"]["multiples"]
        stats = entry["result"].multiples_stats
        for stat_name in ("min", "median", "mean", "max"):
            expected_value = Decimal(expected_multiples[stat_name])
            actual_value = getattr(stats, stat_name)
            assert abs(actual_value - expected_value) / abs(expected_value) < EXCEL_ALIGNMENT_TOLERANCE, (
                f"统计值 {stat_name} 相对误差越限: {entry['case']['name']}"
            )


@then("隐含区间三值与统计值乘目标 EBITDA 精确相等（同源乘法锚）")
def then_implied_ev_exact(context: dict[str, Any]) -> None:
    """同源 Decimal 乘法精确断言（测试侧算术包 localcontext prec=50——AC-2 Then① 钦定）。"""
    from decimal import Decimal, localcontext

    for entry in context["comparable_results"]:
        case_input: dict[str, Any] = entry["case"]["input"]
        target = Decimal(case_input["target_ebitda"])
        result = entry["result"]
        with localcontext() as decimal_context:
            decimal_context.prec = 50
            assert result.implied_ev_low == result.multiples_stats.min * target, (
                f"隐含区间 low 精确相等失败: {entry['case']['name']}"
            )
            assert result.implied_ev_median == result.multiples_stats.median * target, (
                f"隐含区间 median 精确相等失败: {entry['case']['name']}"
            )
            assert result.implied_ev_high == result.multiples_stats.max * target, (
                f"隐含区间 high 精确相等失败: {entry['case']['name']}"
            )


@given("手工实例化 FinancialModelingService 并加载先例基准用例集")
def given_service_with_precedent_cases(context: dict[str, Any]) -> None:
    """先例基准前置（transactions 数组——对价倍数语义）。"""
    from src.domain.services.financial_modeling import FinancialModelingService

    context["service"] = FinancialModelingService()
    context["precedent_cases"] = _load_benchmark_cases("precedent_cases")


@when("逐例构造先例交易集合并执行先例估值计算")
def when_run_precedent_cases(context: dict[str, Any]) -> None:
    """逐例执行（与可比引擎同构独立断言载体）。"""
    from decimal import Decimal

    from src.domain.value_objects.financial_valuation import PrecedentTransaction, PrecedentTransactionSet

    results: list[dict[str, Any]] = []
    for case in context["precedent_cases"]:
        case_input: dict[str, Any] = case["input"]
        transaction_set = PrecedentTransactionSet(
            transactions=tuple(
                PrecedentTransaction(target_name=str(item["target_name"]), ev_ebitda=Decimal(item["ev_ebitda"]))
                for item in case_input["transactions"]
            )
        )
        result = context["service"].calculate_precedent_valuation(transaction_set, Decimal(case_input["target_ebitda"]))
        results.append({"case": case, "result": result})
    context["precedent_results"] = results


@then("统计四值与隐含参考区间同口径对齐（与可比引擎同构独立断言）")
def then_precedent_stats_aligned(context: dict[str, Any]) -> None:
    """先例统计四值相对误差 + 参考区间三值精确相等（一次覆盖——同构合并断言）。"""
    from decimal import Decimal, localcontext

    from tests.integration.test_integration_financial_modeling import EXCEL_ALIGNMENT_TOLERANCE

    for entry in context["precedent_results"]:
        case_input: dict[str, Any] = entry["case"]["input"]
        expected: dict[str, Any] = entry["case"]["expected"]
        target = Decimal(case_input["target_ebitda"])
        result = entry["result"]
        for stat_name in ("min", "median", "mean", "max"):
            expected_value = Decimal(expected["multiples"][stat_name])
            actual_value = getattr(result.multiples_stats, stat_name)
            assert abs(actual_value - expected_value) / abs(expected_value) < EXCEL_ALIGNMENT_TOLERANCE, (
                f"先例统计值 {stat_name} 相对误差越限: {entry['case']['name']}"
            )
        with localcontext() as decimal_context:
            decimal_context.prec = 50
            assert result.implied_ev_low == result.multiples_stats.min * target, (
                f"先例参考区间 low 精确相等失败: {entry['case']['name']}"
            )
            assert result.implied_ev_median == result.multiples_stats.median * target, (
                f"先例参考区间 median 精确相等失败: {entry['case']['name']}"
            )
            assert result.implied_ev_high == result.multiples_stats.max * target, (
                f"先例参考区间 high 精确相等失败: {entry['case']['name']}"
            )


@when("构造空可比与空先例集合及含非正倍数的成员（两类集合）")
def when_prepare_invalid_set_payloads(context: dict[str, Any]) -> None:
    """非法集合载体登记（空集合载荷 + 非正倍数成员——When 登记 Then 消费，
    AC-1.3 When 全量登记形态对齐[CR2-7]；触发面在 Then——242 成员级/集合级守卫）。"""
    context["empty_comparables"] = ()
    context["empty_transactions"] = ()
    context["invalid_member_company"] = ("零倍数公司", "0")
    context["invalid_member_transaction"] = ("负倍数标的", "-1.5")


@then("两类空集合各抛 242（非空不变量）")
def then_empty_set_242(context: dict[str, Any]) -> None:
    """ComparableSet/PrecedentTransactionSet 非空不变量（VO min 1 守卫参数化面；
    空集合载荷经 When 登记[CR2-7——When/Then 职责对齐]）。"""
    from src.domain.exceptions import EntityValidationError
    from src.domain.value_objects.financial_valuation import ComparableSet, PrecedentTransactionSet

    with pytest.raises(EntityValidationError) as comparable_exc:
        ComparableSet(comparables=context["empty_comparables"])
    assert comparable_exc.value.code == "EXCEPTION_242"
    assert comparable_exc.value.context["field"] == "comparables"

    with pytest.raises(EntityValidationError) as precedent_exc:
        PrecedentTransactionSet(transactions=context["empty_transactions"])
    assert precedent_exc.value.code == "EXCEPTION_242"
    assert precedent_exc.value.context["field"] == "transactions"


@then("非正倍数成员抛 242（倍数域正值不变量）")
def then_non_positive_multiple_242(context: dict[str, Any]) -> None:
    """成员级 ev_ebitda > 0 守卫（可比公司与先例交易两类成员各验）。"""
    from decimal import Decimal

    from src.domain.exceptions import EntityValidationError
    from src.domain.value_objects.financial_valuation import ComparableCompany, PrecedentTransaction

    company_name, company_multiple = context["invalid_member_company"]
    with pytest.raises(EntityValidationError) as company_exc:
        ComparableCompany(name=str(company_name), ev_ebitda=Decimal(str(company_multiple)))
    assert company_exc.value.code == "EXCEPTION_242"
    assert company_exc.value.context["field"] == "ev_ebitda"

    transaction_name, transaction_multiple = context["invalid_member_transaction"]
    with pytest.raises(EntityValidationError) as transaction_exc:
        PrecedentTransaction(target_name=str(transaction_name), ev_ebitda=Decimal(str(transaction_multiple)))
    assert transaction_exc.value.code == "EXCEPTION_242"
    assert transaction_exc.value.context["field"] == "ev_ebitda"


# ==== AC-3: 财务数据输入 Schema 契约 ====


@scenario(
    "test_acceptance_financial_modeling.feature",
    "AC-3.1 - 三段请求合法构造与字符串数字精确解析",
)
def test_ac_3_1_valid_construction(context: dict[str, Any]) -> None:
    """AC-3.1: 全量/部分请求合法构造 + str→Decimal 零损失锚 + 四 VO 转换。"""


@scenario(
    "test_acceptance_financial_modeling.feature",
    "AC-3.2 - 六类非法输入 pydantic 拒绝",
)
def test_ac_3_2_invalid_rejection(context: dict[str, Any]) -> None:
    """AC-3.2: 六类非法输入 pydantic.ValidationError（Schema 层拦截——三层异常语义分立）。"""


@given("财务估值请求 Schema 族已就位（应用层 Pydantic v2）")
def given_schemas_ready(context: dict[str, Any]) -> None:
    """Schema 族前置（延迟 import——Task 0-5 窗口期运行期失败形态）。"""
    from src.application.services.financial_schemas import FinancialValuationRequest

    context["request_cls"] = FinancialValuationRequest
    context["full_payload"] = {
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


@when("构造三段全量请求（量值字段全字符串数字）与单段 DCF 部分请求")
def when_construct_requests(context: dict[str, Any]) -> None:
    """全量 + 部分构造（period int 序数索引不套 str 契约——量值字段全 str）。"""
    context["full_request"] = context["request_cls"].model_validate(context["full_payload"])
    context["partial_request"] = context["request_cls"].model_validate({"dcf": context["full_payload"]["dcf"]})


@then("全量与部分请求均通过校验且 Decimal 字段精确等于字符串解析值")
def then_decimal_exact_parse(context: dict[str, Any]) -> None:
    """str→Decimal 零精度损失验证锚（OD-5② 核心断言——精确相等非 approx）。"""
    from decimal import Decimal

    full_dcf = context["full_request"].dcf
    assert full_dcf is not None, "全量请求 DCF 段应非 None"
    assert full_dcf.discount_rate == Decimal("0.1")
    assert full_dcf.terminal_growth_rate == Decimal("0.02")
    assert full_dcf.cash_flows[0].amount == Decimal("-100")
    assert full_dcf.cash_flows[4].amount == Decimal("70")
    full_comparables = context["full_request"].comparables
    assert full_comparables is not None
    assert full_comparables.target_ebitda == Decimal("120")
    assert full_comparables.comparables[0].ev_ebitda == Decimal("8.5")

    partial = context["partial_request"]
    assert partial.dcf is not None, "部分请求 DCF 段应非 None"
    assert partial.comparables is None, "未请求段应为 None"
    assert partial.precedents is None, "未请求段应为 None"


@then("值对象转换产出四类值对象且未请求段为 None")
def then_to_value_objects(context: dict[str, Any]) -> None:
    """to_value_objects 四元组（Schema 保持纯契约——转换函数在用例文件）。"""
    from src.application.use_cases.financial_modeling import to_value_objects
    from src.domain.value_objects.financial_valuation import (
        CashFlowSchedule,
        ComparableSet,
        DcfAssumptions,
        PrecedentTransactionSet,
    )

    schedule, assumptions, comparable_set, transaction_set = to_value_objects(context["full_request"])
    assert isinstance(schedule, CashFlowSchedule)
    assert isinstance(assumptions, DcfAssumptions)
    assert isinstance(comparable_set, ComparableSet)
    assert isinstance(transaction_set, PrecedentTransactionSet)

    partial_schedule, partial_assumptions, none_set, none_transactions = to_value_objects(context["partial_request"])
    assert isinstance(partial_schedule, CashFlowSchedule)
    assert isinstance(partial_assumptions, DcfAssumptions)
    assert none_set is None, "未请求的可比段应转换为 None"
    assert none_transactions is None, "未请求的先例段应转换为 None"


@when("构造负折现率与折现率不小于 1 与 g 不小于 r 跨字段与空现金流与空可比与三段全 None 六类非法输入")
def when_construct_invalid_payloads(context: dict[str, Any]) -> None:
    """六类非法载荷登记（Schema 层拦截——Field 约束 + model_validator 跨字段守卫）。"""
    base_dcf = dict(context["full_payload"]["dcf"])
    context["invalid_payloads"] = [
        {**context["full_payload"], "dcf": {**base_dcf, "discount_rate": "-0.1"}},  # 1. 负折现率
        {**context["full_payload"], "dcf": {**base_dcf, "discount_rate": "1.5"}},  # 2. 折现率≥1
        {  # 3. g≥r 跨字段
            **context["full_payload"],
            "dcf": {**base_dcf, "discount_rate": "0.10", "terminal_growth_rate": "0.12"},
        },
        {**context["full_payload"], "dcf": {**base_dcf, "cash_flows": []}},  # 4. 空现金流
        {**context["full_payload"], "comparables": {"comparables": [], "target_ebitda": "120"}},  # 5. 空可比
        {},  # 6. 三段全 None
    ]


@then("六类输入均抛 pydantic ValidationError（Schema 层拦截——三层异常语义分立）")
def then_pydantic_rejection(context: dict[str, Any]) -> None:
    """框架原生异常透传（不包装——Schema/VO/引擎三层异常语义互不越界）。"""
    from pydantic import ValidationError

    assert len(context["invalid_payloads"]) == 6, "六类非法输入载荷应齐备"
    for index, payload in enumerate(context["invalid_payloads"], start=1):
        with pytest.raises(ValidationError) as exc_info:
            context["request_cls"].model_validate(payload)
        assert type(exc_info.value) is ValidationError, f"第 {index} 类应 pydantic.ValidationError 原样抛出"


# ==== AC-4: 端口接线与契约 ====


@scenario(
    "test_acceptance_financial_modeling.feature",
    "AC-4.1 - 组合根注册与注入链",
)
def test_ac_4_1_port_wiring(context: dict[str, Any]) -> None:
    """AC-4.1: resolve 两端口四件 + PortSpec 元数据 + 注入链。"""


@scenario(
    "test_acceptance_financial_modeling.feature",
    "AC-4.2 - 全链编排零变换与 fail-loud",
)
def test_ac_4_2_orchestration(context: dict[str, Any]) -> None:
    """AC-4.2: 三段结果与直接调用逐一相等 + 470 上抛 + 三零边界。"""


@given("组合根 bootstrap 完成")
def given_bootstrap(context: dict[str, Any]) -> None:
    """组合根注册中心就绪（bootstrap 由 tests/conftest _bootstrap_once 会话级自动调用——验收禁二次调用）。"""
    from src.domain.ports.registry import _global_registry

    assert _global_registry.get("public_blackboard") is not None, "组合根未 bootstrap（conftest 应已执行）"


@when("解析 financial_modeling_service 与 financial_modeling_use_case 两端口")
def when_resolve_two_ports(context: dict[str, Any]) -> None:
    """两端口 resolve（SINGLETON 惰性首解析——lambda 此时执行）。"""
    from src.domain.ports.resolver import resolve

    context["service_instance"] = resolve("financial_modeling_service")
    context["use_case_instance"] = resolve("financial_modeling_use_case")


@then("两端口均可解析且 PortSpec 元数据逐项匹配（版本/生命周期/owner/tags）")
def then_portspec_metadata(context: dict[str, Any]) -> None:
    """resolve 四件（可达/实例类型/PortSpec 元数据/生命周期）。"""
    from src.application.use_cases.financial_modeling import FinancialModelingUseCase
    from src.domain.ports.registry import Lifetime, _global_registry
    from src.domain.services.financial_modeling import FinancialModelingService

    service = context["service_instance"]
    use_case = context["use_case_instance"]
    assert isinstance(service, FinancialModelingService), "resolve('financial_modeling_service') 实例类型"
    assert isinstance(use_case, FinancialModelingUseCase), "resolve('financial_modeling_use_case') 实例类型"

    service_spec = _global_registry.get("financial_modeling_service")
    assert service_spec is not None, "端口 financial_modeling_service 未注册"
    assert service_spec.version == "v1.0.0"
    assert service_spec.lifetime is Lifetime.SINGLETON, "无状态纯计算——DC-9 并发安全论证"
    assert service_spec.owner == "platform"
    assert service_spec.tags == ("financial", "valuation", "domain-service")

    use_case_spec = _global_registry.get("financial_modeling_use_case")
    assert use_case_spec is not None, "端口 financial_modeling_use_case 未注册"
    assert use_case_spec.version == "v1.0.0"
    assert use_case_spec.lifetime is Lifetime.SINGLETON
    assert use_case_spec.owner == "platform"
    assert use_case_spec.tags == ("financial", "valuation", "usecase")


@then("用例实例注入链完整（服务依赖非空）")
def then_injection_chain(context: dict[str, Any]) -> None:
    """lambda 注入链（use_case._service 非 None——AC-4 Then② 钦定）。"""
    assert getattr(context["use_case_instance"], "_service", None) is not None, "服务依赖注入链断裂"


@given("组合根 resolve 获得估值用例（真实服务注入）")
def given_use_case_resolved(context: dict[str, Any]) -> None:
    """全链前置（resolve 用例 + resolve 服务——真实服务直调对照面）。"""
    from src.domain.ports.resolver import resolve

    context["use_case"] = resolve("financial_modeling_use_case")
    context["direct_service"] = resolve("financial_modeling_service")


@when("以三段全量请求执行 execute 并与直接调用服务三方法对照")
def when_execute_full_vs_direct(context: dict[str, Any]) -> None:
    """全链 execute + 直接服务三方法同输入对照（编排零变换验证输入面）。"""
    from decimal import Decimal

    from src.application.services.financial_schemas import FinancialValuationRequest
    from src.application.use_cases.financial_modeling import to_value_objects

    payload = {
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
                {"name": "对照可比甲", "ev_ebitda": "8.5"},
                {"name": "对照可比乙", "ev_ebitda": "10.2"},
                {"name": "对照可比丙", "ev_ebitda": "12.8"},
                {"name": "对照可比丁", "ev_ebitda": "15.0"},
            ],
            "target_ebitda": "120",
        },
        "precedents": {
            "transactions": [
                {"target_name": "对照先例一", "ev_ebitda": "9.0"},
                {"target_name": "对照先例二", "ev_ebitda": "11.5"},
                {"target_name": "对照先例三", "ev_ebitda": "13.2"},
            ],
            "target_ebitda": "120",
        },
    }
    request = FinancialValuationRequest.model_validate(payload)
    context["full_payload_dto_input"] = request
    context["dto"] = context["use_case"].execute(request)

    schedule, assumptions, comparable_set, transaction_set = to_value_objects(request)
    assert comparable_set is not None and transaction_set is not None
    context["direct_dcf"] = context["direct_service"].calculate_dcf(schedule, assumptions)
    context["direct_comparable"] = context["direct_service"].calculate_comparable_valuation(
        comparable_set, Decimal(str(payload["comparables"]["target_ebitda"]))
    )
    context["direct_precedent"] = context["direct_service"].calculate_precedent_valuation(
        transaction_set, Decimal(str(payload["precedents"]["target_ebitda"]))
    )


@then("三段结果与直接调用逐一相等（编排零变换锚）")
def then_orchestration_zero_transform(context: dict[str, Any]) -> None:
    """同输入同输出（用例是纯编排——Schema→VO→服务→DTO 零业务变换）。"""
    dto = context["dto"]
    assert dto.dcf == context["direct_dcf"], "DCF 段应与直接调用相等"
    assert dto.comparables == context["direct_comparable"], "可比段应与直接调用相等"
    assert dto.precedents == context["direct_precedent"], "先例段应与直接调用相等"


@then("病态 IRR 序列经全链触发 470 上抛（fail-loud 不吞不降级）")
def then_fail_loud_470(context: dict[str, Any]) -> None:
    """验收侧 fail-loud 经病态 IRR 序列走 resolve 全链真实触发（不用替身）。"""
    from src.application.services.financial_schemas import FinancialValuationRequest
    from src.domain.exceptions import FinancialCalculationError

    pathological_payload = {
        "dcf": {
            "cash_flows": [
                {"period": 1, "amount": "-100"},
                {"period": 2, "amount": "230"},
                {"period": 3, "amount": "-132"},
            ],
            "discount_rate": "0.1",
            "terminal_value_method": "perpetual_growth",
            "terminal_growth_rate": "0.02",
        },
    }
    request = FinancialValuationRequest.model_validate(pathological_payload)
    with pytest.raises(FinancialCalculationError) as exc_info:
        context["use_case"].execute(request)
    assert exc_info.value.code == "EXCEPTION_470", "全链应上抛 470（fail-loud）"
    assert exc_info.value.context["method"] == "dcf"


@then("零事件零 REST 零 catalog 三零边界成立")
def then_three_zero_boundaries(context: dict[str, Any]) -> None:
    """三零断言（OD-2/OD-3/OD-6——计算服务无事件/无端点/无工具注册）。"""
    repo_root = Path(__file__).resolve().parents[2]
    event_channels = (repo_root / "configs" / "event_channels.yaml").read_text(encoding="utf-8")
    assert "financial" not in event_channels, "零事件面：event_channels.yaml 不应含 financial 条目"
    openapi_spec = (repo_root / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8")
    assert "/financial" not in openapi_spec, "零 REST 面：openapi.yaml 不应含 /financial 路径"
    catalog_source = (repo_root / "src" / "domain" / "entities" / "strategic_tool_catalog.py").read_text(encoding="utf-8")
    assert "FINANCIAL" not in catalog_source, "零 catalog 面：ToolCategory 不应含 FINANCIAL 枚举"
    skill_manifest = (repo_root / "src" / "application" / "skills" / "skill_manifest.py").read_text(encoding="utf-8")
    assert "financial" not in skill_manifest, "零 catalog 面：skill_manifest 不应含 financial slug"


# ==== AC-5: 性能三锚（委托计时 + 并发） ====


@scenario(
    "test_acceptance_financial_modeling.feature",
    "AC-5.1 - 单次估值延迟与精度汇总双锚（委托计时）",
)
def test_ac_5_1_p95_precision_anchors(context: dict[str, Any]) -> None:
    """AC-5.1: P95<5s + 精度汇总 <0.0001 + 正向锚 21（常量等值变异锚）。"""


@scenario(
    "test_acceptance_financial_modeling.feature",
    "AC-5.2 - 10 路并发估值全成功与结果隔离",
)
def test_ac_5_2_concurrency_10(context: dict[str, Any]) -> None:
    """AC-5.2: 10/10 全成功 + 隔离锚 + 确定性锚（ThreadPoolExecutor 同步契约配套）。"""


@given("集成计时委托模块已加载（_PERF_CACHE 委托采样）")
def given_perf_delegate(context: dict[str, Any]) -> None:
    """委托采样（helper cache-or-compute——命中或首次采样，同 xdist_group 同 worker 串行）。"""
    from tests.integration.test_integration_financial_modeling import sample_financial_perf

    context["perf_summary"] = sample_financial_perf()


@when("读取委托采样的延迟摘要与精度汇总及并发下限常量")
def when_read_perf_summary(context: dict[str, Any]) -> None:
    """常量单源 import（验收侧禁双真源——集成模块定义/验收 import）。"""
    from tests.integration.test_integration_financial_modeling import (
        EXCEL_ALIGNMENT_TOLERANCE,
        FINANCIAL_CONCURRENCY_FLOOR,
        FINANCIAL_VALUATION_P95_LIMIT_SECONDS,
    )

    summary: dict[str, Any] = context["perf_summary"]
    context["valuation_p95"] = summary["valuation_p95_seconds"]
    context["valuation_sample_count"] = summary["valuation_sample_count"]
    context["max_relative_error"] = summary["max_relative_error"]
    context["p95_limit"] = FINANCIAL_VALUATION_P95_LIMIT_SECONDS
    context["tolerance"] = EXCEL_ALIGNMENT_TOLERANCE
    context["concurrency_floor"] = FINANCIAL_CONCURRENCY_FLOOR


@then("P95 延迟小于 5 秒且常量等值断言成立（常量单源）")
def then_p95_latency(context: dict[str, Any]) -> None:
    """epics L1970 钦定（等值断言是常量改错值变异锚的充分条件——5-11 v1.3.0 补注同款）。"""
    assert context["p95_limit"] == 5.0, "FINANCIAL_VALUATION_P95_LIMIT_SECONDS 应为 5.0（常量单源）"
    assert context["valuation_p95"] < context["p95_limit"], (
        f"单次全量估值 P95 应 < {context['p95_limit']}s，实际 {context['valuation_p95']}s"
    )


@then("基准全集最大相对误差小于 0.0001（精度汇总锚）")
def then_precision_summary(context: dict[str, Any]) -> None:
    """epics L1971 钦定（与逐例断言双保险汇总面——Decimal 域断言）。"""
    assert str(context["tolerance"]) == "0.0001", "EXCEL_ALIGNMENT_TOLERANCE 应为 0.0001（常量单源）"
    assert context["max_relative_error"] < context["tolerance"], (
        f"基准全集最大相对误差应 < 0.0001，实际 {context['max_relative_error']}"
    )


@then("正向锚收到计数为 21")
def then_positive_anchor(context: dict[str, Any]) -> None:
    """warmup 1 + 20 采样（防静默跳过假绿）+ 并发下限常量等值锚。"""
    assert context["valuation_sample_count"] == 21, (
        f"正向锚应为 21（warmup 1 + 20 采样），实际 {context['valuation_sample_count']}"
    )
    assert context["concurrency_floor"] == 10, "FINANCIAL_CONCURRENCY_FLOOR 应为 10（常量单源）"


@when("读取委托采样的并发摘要（10 线程 10 路独立请求）")
def when_read_concurrency_summary(context: dict[str, Any]) -> None:
    """并发面摘要（ThreadPoolExecutor 10 线程——GIL 串行知悉，验证并发不互扰）。"""
    summary: dict[str, Any] = context["perf_summary"]
    context["concurrency_success_count"] = summary["concurrency_success_count"]
    context["concurrency_isolated"] = summary["concurrency_isolated"]
    context["concurrency_deterministic"] = summary["concurrency_deterministic"]


@then("10 路全部成功且每路结果匹配各自输入（并发隔离锚）")
def then_concurrency_isolation(context: dict[str, Any]) -> None:
    """10/10 全成功 + 每路异 target_ebitda 各自结果匹配（epics L1972 钦定）。"""
    assert context["concurrency_success_count"] == 10, f"并发估值应 10/10 全成功，实际 {context['concurrency_success_count']}"
    assert context["concurrency_isolated"] is True, "每路结果应匹配各自输入（并发隔离锚）"


@then("并发结果与串行基线逐路精确相等（并发确定性锚）")
def then_concurrency_determinism(context: dict[str, Any]) -> None:
    """同 10 路请求串行基线与并发结果逐路精确相等（确定性在并发下保持）。"""
    assert context["concurrency_deterministic"] is True, "并发结果应与串行基线逐路精确相等"


# ==== 收尾: 开发结束验收（完成清单逐项确认） ====


@scenario(
    "test_acceptance_financial_modeling.feature",
    "开发结束 - 交付完成清单逐项确认",
)
def test_delivery_complete_checklist(context: dict[str, Any]) -> None:
    """收尾: src 六件 + tests 十件 + 注册联动全部就位。"""


@given("Story 5.12 交付完成")
def given_delivery_complete(context: dict[str, Any]) -> None:
    """收尾验收前置（开发结束状态——存在性与关键符号断言载体）。"""


@then("src 完成清单六件全部就位且关键符号可导入")
def then_src_checklist(context: dict[str, Any]) -> None:
    """5 新建 + 1 修改生产/注册面文件（组合根区段——两注册）。"""
    repo_root = Path(__file__).resolve().parents[2]
    src_files = [
        "src/domain/value_objects/financial_valuation.py",
        "src/domain/services/financial_modeling.py",
        "src/domain/exceptions/financial_exceptions.py",
        "src/application/services/financial_schemas.py",
        "src/application/use_cases/financial_modeling.py",
        "src/composition_root.py",
    ]
    for relative in src_files:
        assert (repo_root / relative).exists(), f"src 完成清单缺件: {relative}"

    from src.domain.exceptions import FinancialCalculationError
    from src.domain.services.financial_modeling import FinancialModelingService
    from src.domain.value_objects.financial_valuation import CashFlowSchedule

    assert callable(FinancialModelingService), "引擎关键符号缺失"
    assert CashFlowSchedule is not None, "VO 关键符号缺失"
    assert FinancialCalculationError.code == "EXCEPTION_470", "异常编码应为 EXCEPTION_470"


@then("tests 完成清单十件全部就位")
def then_tests_checklist(context: dict[str, Any]) -> None:
    """unit 五件 + contracts 一件 + integration 一件 + architecture 一件 + acceptance 两件。"""
    repo_root = Path(__file__).resolve().parents[2]
    test_files = [
        "tests/unit/domain/value_objects/test_financial_valuation.py",
        "tests/unit/domain/services/test_financial_modeling.py",
        "tests/unit/domain/services/financial_test_cases.json",
        "tests/unit/domain/exceptions/test_financial_exceptions.py",
        "tests/unit/application/use_cases/test_financial_modeling_use_case.py",
        "tests/contracts/test_port_contract_financial_modeling.py",
        "tests/unit/architecture/test_arch_financial_modeling.py",
        "tests/integration/test_integration_financial_modeling.py",
        "tests/acceptance/test_acceptance_financial_modeling.feature",
        "tests/acceptance/test_acceptance_financial_modeling.py",
    ]
    for relative in test_files:
        assert (repo_root / relative).exists(), f"tests 完成清单缺件: {relative}"


@then("组合根注册与导出及文档联动全部就位")
def then_wiring_checklist(context: dict[str, Any]) -> None:
    """注册四件套（CODE_RANGES financial 段/HTTP 映射 470→422/__init__ 导出）+ 组合根两注册。"""
    from fastapi import status

    from src.domain.exceptions import FinancialCalculationError
    from src.domain.exceptions._code_ranges import CODE_RANGES
    from src.domain.ports.registry import _global_registry
    from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

    assert CODE_RANGES.get("financial") == (470, 479), "CODE_RANGES financial 段未注册"
    assert EXCEPTION_HTTP_MAP[FinancialCalculationError] == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert _global_registry.get("financial_modeling_service") is not None, "组合根 financial_modeling_service 注册缺失"
    assert _global_registry.get("financial_modeling_use_case") is not None, "组合根 financial_modeling_use_case 注册缺失"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
