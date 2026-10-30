"""集成测试：Story 5.12 财务建模与估值——性能三锚（委托计时单源模块）.

口径声明（四注记——AC-5 And 钦定）：
1. 进程内绊线定位：纯 Decimal 计算 ms 级，5s 门是回归绊线非容量预算（本地进程
   口径——纯计算与网络/IO 无关，5-11 AC-5 同款诚实注记形态）。
2. 20 样本方差知悉：单进程内采样存在调度噪声，P95 口径取 exclusive 分位
   [18]（5-8/5-9/5-10/5-11 同款），20 样本下 P95 估计有方差但足以拦回归级劣化。
3. 标准载荷定义：单次全量估值 = 三方法一次 execute（5 期现金流 + 4 可比 +
   3 先例——与验收 AC-4.2 对照载荷同构）。
4. 精度汇总口径：基准 JSON 全用例（dcf×4 + comparable×2 + precedent×2 的全部
   expected 字段）引擎复算后取最大相对误差——与单测逐例断言双保险。

并发口径（epics L1972「并发估值请求≥10」）：ThreadPoolExecutor 10 线程并发调用
同步 execute（同步契约配套钦定——asyncio.gather 不适用同步函数；GIL 下 CPU-bound
实际串行，验证面是并发调用不互扰 + 全成功 + 结果隔离 + 与串行基线逐路精确相等
[确定性锚——基线获取钦定：同 10 路请求先串行执行一遍存结果再并发比对]，非并行
加速）。

纯计算零外部服务依赖：不挂任何服务 marker（文件名 financial 不命中 conftest
关键词映射，仅自动挂 integration）——CI 无外部服务环境全绿零 skip。

常量单源分层钦定（AC-5 Given④）：EXCEL_ALIGNMENT_TOLERANCE 定义于单测文件
（tests/unit/domain/services/test_financial_modeling.py——本模块 re-export，
验收经本链取值禁双真源）；FINANCIAL_VALUATION_P95_LIMIT_SECONDS /
FINANCIAL_CONCURRENCY_FLOOR 本模块定义（仅性能面使用——验收 import 禁双真源）。
_PERF_CACHE 单 key financial_perf 载三指标 summary（xdist_group 同 worker 串行
是命中前提——「命中或首次采样」禁先跑断言）。

Run with:
    poetry run pytest tests/integration/test_integration_financial_modeling.py -v
"""

from __future__ import annotations

import json
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

import pytest

from src.application.services.financial_schemas import FinancialValuationRequest
from src.application.use_cases.financial_modeling import FinancialModelingUseCase
from src.domain.services.financial_modeling import FinancialModelingService

# 容差单源 re-export（单测文件是源——AC-5 Given④ 分层钦定，集成/验收经此链取值禁双真源；
# 冗余别名是 PEP 484 显式再导出约定形态）
from tests.unit.domain.services.test_financial_modeling import (
    EXCEL_ALIGNMENT_TOLERANCE as EXCEL_ALIGNMENT_TOLERANCE,
)

#: 单次全量估值 P95 上限（秒）——epics L1970 钦定（单源定义——验收侧 import 本常量断言，禁双真源）
FINANCIAL_VALUATION_P95_LIMIT_SECONDS = 5.0
#: 并发估值下限（路数）——epics L1972 钦定（单源定义——验收侧 import 禁双真源）
FINANCIAL_CONCURRENCY_FLOOR = 10
#: 采样轮数（warmup 1 + 采样 20——正向锚 21）
FINANCIAL_SAMPLE_ROUNDS = 20

#: 委托缓存（单 key financial_perf 载三指标 summary——loadgroup 同 worker 串行命中）
_PERF_CACHE: dict[str, dict[str, Any]] = {}

_BENCHMARK_PATH = Path(__file__).resolve().parents[1] / "unit" / "domain" / "services" / "financial_test_cases.json"

#: 标准载荷（5 期现金流 + 4 可比 + 3 先例全量请求——AC-5 Given① 口径）
_STANDARD_PAYLOAD: dict[str, Any] = {
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
            {"name": "性能可比甲", "ev_ebitda": "8.5"},
            {"name": "性能可比乙", "ev_ebitda": "10.2"},
            {"name": "性能可比丙", "ev_ebitda": "12.8"},
            {"name": "性能可比丁", "ev_ebitda": "15.0"},
        ],
        "target_ebitda": "120",
    },
    "precedents": {
        "transactions": [
            {"target_name": "性能先例一", "ev_ebitda": "9.0"},
            {"target_name": "性能先例二", "ev_ebitda": "11.5"},
            {"target_name": "性能先例三", "ev_ebitda": "13.2"},
        ],
        "target_ebitda": "120",
    },
}

pytestmark = [
    pytest.mark.integration,
    pytest.mark.xdist_group("financial-modeling-perf"),
]


def _relative_error(actual: Decimal, expected: Decimal) -> Decimal:
    """相对误差（|actual−expected|/|expected|——Decimal 域零 pytest.approx）。"""
    if expected == 0:
        return abs(actual - expected)
    return abs(actual - expected) / abs(expected)


def _compute_precision_summary(service: FinancialModelingService) -> Decimal:
    """精度汇总：基准 JSON 全用例引擎复算取最大相对误差（与单测逐例断言双保险汇总面）。"""
    from src.domain.value_objects.financial_valuation import (
        CashFlow,
        CashFlowSchedule,
        ComparableCompany,
        ComparableSet,
        DcfAssumptions,
        PrecedentTransaction,
        PrecedentTransactionSet,
    )

    with _BENCHMARK_PATH.open(encoding="utf-8") as file_handle:
        benchmark: dict[str, Any] = json.load(file_handle)

    max_relative_error = Decimal("0")
    for case in benchmark["dcf_cases"]:
        case_input = case["input"]
        schedule = CashFlowSchedule(
            cash_flows=tuple(
                CashFlow(period=int(item["period"]), amount=Decimal(item["amount"])) for item in case_input["cash_flows"]
            )
        )
        assumptions_kwargs: dict[str, Any] = {
            "discount_rate": Decimal(case_input["discount_rate"]),
            "terminal_value_method": case_input["terminal_value_method"],
        }
        if case_input["terminal_value_method"] == "perpetual_growth":
            assumptions_kwargs["terminal_growth_rate"] = Decimal(case_input["terminal_growth_rate"])
        else:
            assumptions_kwargs["exit_multiple"] = Decimal(case_input["exit_multiple"])
            assumptions_kwargs["terminal_exit_metric"] = Decimal(case_input["terminal_exit_metric"])
        result = service.calculate_dcf(schedule, DcfAssumptions(**assumptions_kwargs))
        max_relative_error = max(
            max_relative_error,
            _relative_error(result.npv, Decimal(case["expected"]["npv"])),
            _relative_error(result.terminal_value, Decimal(case["expected"]["terminal_value"])),
            _relative_error(result.irr, Decimal(case["expected"]["irr"])),
        )
    for case in benchmark["comparable_cases"]:
        case_input = case["input"]
        comparable_result = service.calculate_comparable_valuation(
            ComparableSet(
                comparables=tuple(
                    ComparableCompany(name=str(i["name"]), ev_ebitda=Decimal(i["ev_ebitda"])) for i in case_input["comparables"]
                )
            ),
            Decimal(case_input["target_ebitda"]),
        )
        for stat_name in ("min", "median", "mean", "max"):
            expected_value = Decimal(case["expected"]["multiples"][stat_name])
            max_relative_error = max(
                max_relative_error,
                _relative_error(getattr(comparable_result.multiples_stats, stat_name), expected_value),
            )
    for case in benchmark["precedent_cases"]:
        case_input = case["input"]
        precedent_result = service.calculate_precedent_valuation(
            PrecedentTransactionSet(
                transactions=tuple(
                    PrecedentTransaction(target_name=str(i["target_name"]), ev_ebitda=Decimal(i["ev_ebitda"]))
                    for i in case_input["transactions"]
                )
            ),
            Decimal(case_input["target_ebitda"]),
        )
        for stat_name in ("min", "median", "mean", "max"):
            expected_value = Decimal(case["expected"]["multiples"][stat_name])
            max_relative_error = max(
                max_relative_error,
                _relative_error(getattr(precedent_result.multiples_stats, stat_name), expected_value),
            )
    return max_relative_error


def _make_concurrency_payload(target_ebitda: str) -> FinancialValuationRequest:
    """并发请求构造（每路异 target_ebitda——结果隔离锚载体）。"""
    payload = json.loads(json.dumps(_STANDARD_PAYLOAD))
    payload["comparables"]["target_ebitda"] = target_ebitda
    payload["precedents"]["target_ebitda"] = target_ebitda
    return FinancialValuationRequest.model_validate(payload)


def sample_financial_perf() -> dict[str, Any]:
    """性能三锚委托采样（cache-or-compute——_PERF_CACHE 单 key financial_perf 载三指标 summary）.

    采样口径：单次全量估值全程（构造请求 → execute → 结果返回 monotonic 计时，
    全同步采样循环）；warmup 1 + 20 采样 exclusive P95 = quantiles(latencies, n=20)[18]
    （5-8/5-9/5-10/5-11 同款口径）；正向锚 = 延迟轮收到计数 == warmup 1 + 采样 20。

    Returns:
        {"valuation_p95_seconds", "valuation_sample_count", "max_relative_error",
        "concurrency_success_count", "concurrency_isolated", "concurrency_deterministic"}
        六键 summary（验收 AC-5 与本模块测试同源消费）。
    """
    cached = _PERF_CACHE.get("financial_perf")
    if cached is not None:
        return cached

    service = FinancialModelingService()
    use_case = FinancialModelingUseCase(service=service)

    # 锚一：延迟（warmup 1 + 20 采样——首轮不计时；计时窗含请求构造——
    # CR1-4 修复：构造请求 → execute → 结果返回全程 monotonic 计时，与 docstring
    # 及 AC-5 When① 钦定口径对齐，pydantic 校验成本纳入绊线）
    latencies: list[float] = []
    received_count = 0
    for round_index in range(1 + FINANCIAL_SAMPLE_ROUNDS):
        start = time.perf_counter()
        standard_request = FinancialValuationRequest.model_validate(_STANDARD_PAYLOAD)
        result = use_case.execute(standard_request)
        received_count += 1 if result is not None else 0
        if round_index > 0:  # warmup 轮不计时
            latencies.append(time.perf_counter() - start)
    valuation_p95 = statistics.quantiles(latencies, n=FINANCIAL_SAMPLE_ROUNDS)[18]

    # 锚二：精度汇总（基准 JSON 全用例最大相对误差）
    max_relative_error = _compute_precision_summary(service)

    # 锚三：并发（10 线程 10 路独立请求——每路异 target_ebitda；串行基线先存再并发比对）
    targets = [Decimal(100 + index * 10) for index in range(FINANCIAL_CONCURRENCY_FLOOR)]
    serial_results = [use_case.execute(_make_concurrency_payload(str(target))) for target in targets]
    with ThreadPoolExecutor(max_workers=FINANCIAL_CONCURRENCY_FLOOR) as executor:
        concurrent_results = list(
            executor.map(lambda target: use_case.execute(_make_concurrency_payload(str(target))), targets)
        )
    concurrency_success_count = sum(
        1
        for dto in concurrent_results
        if dto is not None and dto.comparables is not None and dto.dcf is not None and dto.precedents is not None
    )
    # 隔离锚乘法包 prec=50（与引擎精度纪律一致——CR1-8；两段对照锚：comparables + precedents）
    with localcontext() as decimal_context:
        decimal_context.prec = 50
        concurrency_isolated = all(
            dto.comparables is not None
            and dto.precedents is not None
            and dto.comparables.implied_ev_median == dto.comparables.multiples_stats.median * target
            and dto.precedents.implied_ev_median == dto.precedents.multiples_stats.median * target
            for dto, target in zip(concurrent_results, targets)
        )
    concurrency_deterministic = concurrent_results == serial_results

    summary: dict[str, Any] = {
        "valuation_p95_seconds": valuation_p95,
        "valuation_sample_count": received_count,
        "max_relative_error": max_relative_error,
        "concurrency_success_count": concurrency_success_count,
        "concurrency_isolated": concurrency_isolated,
        "concurrency_deterministic": concurrency_deterministic,
    }
    _PERF_CACHE["financial_perf"] = summary
    return summary


class TestFinancialPerformanceAnchors:
    """性能三锚（P95 延迟 + 精度汇总 + 并发 10 路——委托采样消费）。"""

    def test_valuation_p95_under_limit(self) -> None:
        """锚一：单次全量估值 P95 < 5s（epics L1970——常量等值断言是变异锚充分条件）。"""
        assert FINANCIAL_VALUATION_P95_LIMIT_SECONDS == 5.0, "P95 上限常量单源应为 5.0"
        summary = sample_financial_perf()
        assert summary["valuation_p95_seconds"] < FINANCIAL_VALUATION_P95_LIMIT_SECONDS, (
            f"单次全量估值 P95 应 < {FINANCIAL_VALUATION_P95_LIMIT_SECONDS}s，实际 {summary['valuation_p95_seconds']}s"
        )

    def test_precision_summary_under_tolerance(self) -> None:
        """锚二：基准全集最大相对误差 < 0.0001（epics L1971——与逐例断言双保险）。"""
        assert str(EXCEL_ALIGNMENT_TOLERANCE) == "0.0001", "容差常量单源应为 0.0001"
        summary = sample_financial_perf()
        assert summary["max_relative_error"] < EXCEL_ALIGNMENT_TOLERANCE, (
            f"基准全集最大相对误差应 < 0.0001，实际 {summary['max_relative_error']}"
        )

    def test_positive_anchor_sample_count_21(self) -> None:
        """正向锚：延迟轮收到计数 == warmup 1 + 采样 20（防静默跳过假绿）+ 并发下限等值锚。"""
        assert FINANCIAL_CONCURRENCY_FLOOR == 10, "并发下限常量单源应为 10"
        summary = sample_financial_perf()
        assert summary["valuation_sample_count"] == 21, (
            f"正向锚应为 21（warmup 1 + 20 采样），实际 {summary['valuation_sample_count']}"
        )

    def test_concurrency_10_all_success_isolated_deterministic(self) -> None:
        """锚三：10 路并发全成功 + 每路结果匹配各自输入（隔离锚）+ 与串行基线逐路精确相等（确定性锚）。"""
        summary = sample_financial_perf()
        assert summary["concurrency_success_count"] == FINANCIAL_CONCURRENCY_FLOOR, (
            f"并发估值应 10/10 全成功，实际 {summary['concurrency_success_count']}"
        )
        assert summary["concurrency_isolated"] is True, "每路结果应匹配各自输入（并发隔离锚）"
        assert summary["concurrency_deterministic"] is True, "并发结果应与串行基线逐路精确相等（确定性锚）"


class TestXdistGroupUnique:
    """xdist 组名互异守护（financial-modeling-perf 与既有 16 组互异——grep 断言）。"""

    def test_financial_group_distinct_from_existing_groups(self) -> None:
        """新组与全仓既有组互异（存量子集断言 + 新组 in——5-9/5-10/5-11 同款）。"""
        repo_root = Path(__file__).resolve().parents[2]
        existing_groups: set[str] = set()
        for python_file in repo_root.glob("tests/**/*.py"):
            content = python_file.read_text(encoding="utf-8")
            existing_groups.update(re.findall(r'xdist_group\("([^"]+)"\)', content))
        expected_existing = {
            "agent-evaluation-perf",
            "agent-instantiation",
            "agent-isolation-perf",
            "agent-profile-loading",
            "agent-triple-isolation-perf",
            "agent-workflow-perf",
            "checkpoint-evaluation-perf",
            "data-source-cache",
            "drift-detection-perf",
            "isolation-switch-log-perf",
            "phoenix-tracer-perf",
            "sandbox-daemon",
            "sap-protocol-perf",
            "tool-executions-pg",
            "tool-versions-pg",
            "validation-feedback-pg",
        }
        assert expected_existing <= existing_groups, "既有 16 组应全部在仓（存量子集断言）"
        assert "financial-modeling-perf" in existing_groups, "新组 financial-modeling-perf 应已注册"
        assert len(existing_groups) >= 17, "组数应不少于 17（16 既有 + 1 新组）"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
