"""应用层财务建模估值用例模块（Story 5.12 财务建模与估值基础）

估值用例统一编排：三段可选载荷请求 → to_value_objects 转换（Schema→VO）→
按段分派领域服务三方法 → FinancialValuationResult 汇总 DTO。纯编排零业务逻辑
（同输入同输出——编排零变换锚），execute 同步契约（纯计算无 IO，async 无谓
开销——Task 0.1 钦定；消费方需异步自行 asyncio.to_thread 或直接同步调用）。

fail-loud 编排（DC-8）：任一方法抛 FinancialCalculationError 470 → 整个
execute 上抛（不吞不降级不返回部分结果——调用方拿到明确失败自行处置）。

三层异常语义分立重申：Schema 层 pydantic.ValidationError（输入契约失败——框架
面原样透传）/ VO 层 EntityValidationError 242（构造守卫经 to_value_objects 触
发）/ 引擎层 FinancialCalculationError 470（数值求解失败上抛）。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from src.application.services.financial_schemas import FinancialValuationRequest
from src.domain.services.financial_modeling import FinancialModelingService
from src.domain.value_objects.financial_valuation import (
    CashFlow,
    CashFlowSchedule,
    ComparableCompany,
    ComparableSet,
    ComparableValuationResult,
    DcfAssumptions,
    DcfValuationResult,
    PrecedentTransaction,
    PrecedentTransactionSet,
    PrecedentValuationResult,
)


@dataclass(frozen=True)
class FinancialValuationResult:
    """财务估值汇总结果 DTO（三段结果 Optional 字段——None=该方法未请求）

    与请求三段同名（dcf/comparables/precedents——AC-3 顶层三字段名钦定对应）。

    Decimal 序列化警示（CR3-2）：三段嵌套结果全部 Decimal 字段不可直接
    JSON 序列化（json.dumps 抛 TypeError；FastAPI jsonable_encoder 会静默
    Decimal→float 截断到 17 位有效数字——反噬 str wire 精度纪律且违反
    「金融计算禁止浮点误差」红线）。消费方 JSON 化时钦定逐 Decimal 叶子
    字段 str()（嵌套 VO/元组递归遍历——与请求 str wire 对称往返，str→Decimal
    构造恒精确）；禁用 float()。本 DTO 不内建序列化方法（警示非保证——
    to_wire_dict 辅助函数归 Story 20-1 REST 面立项时定）。

    Attributes:
        dcf: DCF 估值结果（未请求该段为 None）
        comparables: 可比公司估值结果（未请求该段为 None）
        precedents: 先例交易估值结果（未请求该段为 None）
    """

    dcf: DcfValuationResult | None
    comparables: ComparableValuationResult | None
    precedents: PrecedentValuationResult | None


def to_value_objects(
    request: FinancialValuationRequest,
) -> tuple[CashFlowSchedule | None, DcfAssumptions | None, ComparableSet | None, PrecedentTransactionSet | None]:
    """Schema→VO 四元组转换（纯转换零业务逻辑——Schema 保持纯契约）。

    Args:
        request: 财务估值请求（至少一段非 None——Schema 层已守卫）

    Returns:
        (schedule, assumptions, comparable_set, transaction_set) 四元组：DCF 段产
        两件、可比/先例段各一件，未请求段为 None（用例按 None 跳过该方法分派）

    Raises:
        EntityValidationError: VO 构造守卫 242（Schema 约束镜像的双层守卫——绕过
            Schema 的内部构造由此拦截）
    """
    schedule: CashFlowSchedule | None = None
    assumptions: DcfAssumptions | None = None
    if request.dcf is not None:
        section = request.dcf
        schedule = CashFlowSchedule(
            cash_flows=tuple(CashFlow(period=item.period, amount=item.amount) for item in section.cash_flows)
        )
        if section.terminal_value_method == "perpetual_growth":
            # cast 可信契约标注（Schema 法配套校验 + VO 守卫双重封死 None 路径——非运行时防御）
            growth = cast(Decimal, section.terminal_growth_rate)
            assumptions = DcfAssumptions(
                discount_rate=section.discount_rate,
                terminal_value_method=section.terminal_value_method,
                terminal_growth_rate=growth,
            )
        else:
            exit_multiple = cast(Decimal, section.exit_multiple)
            terminal_exit_metric = cast(Decimal, section.terminal_exit_metric)
            assumptions = DcfAssumptions(
                discount_rate=section.discount_rate,
                terminal_value_method=section.terminal_value_method,
                exit_multiple=exit_multiple,
                terminal_exit_metric=terminal_exit_metric,
            )

    comparable_set: ComparableSet | None = None
    if request.comparables is not None:
        comparable_set = ComparableSet(
            comparables=tuple(
                ComparableCompany(name=item.name, ev_ebitda=item.ev_ebitda) for item in request.comparables.comparables
            )
        )

    transaction_set: PrecedentTransactionSet | None = None
    if request.precedents is not None:
        transaction_set = PrecedentTransactionSet(
            transactions=tuple(
                PrecedentTransaction(target_name=item.target_name, ev_ebitda=item.ev_ebitda)
                for item in request.precedents.transactions
            )
        )

    return schedule, assumptions, comparable_set, transaction_set


class FinancialModelingUseCase:
    """财务建模估值用例（三段可选载荷统一入口——R2 组合注入领域服务）。

    构造注入 FinancialModelingService（domain 服务经 resolver 注入——
    application→domain 合法依赖面）；SINGLETON 安全（无状态纯编排）。
    """

    def __init__(self, service: FinancialModelingService) -> None:
        """初始化估值用例.

        Args:
            service: 财务建模领域服务（组合根 lambda 注入 financial_modeling_service 端口）
        """
        self._service = service

    def execute(self, request: FinancialValuationRequest) -> FinancialValuationResult:
        """执行估值编排（转换 → 按段分派服务方法 → 组装 DTO——零捕获零降级）。

        同步契约注记（CR3-5）：纯 Decimal 计算 ms 级无 IO——async 消费方
        （LangGraph/Prefect）经 asyncio.to_thread 包装或直接同步调用。

        Args:
            request: 财务估值请求（至少一段非 None）

        Returns:
            FinancialValuationResult 三段汇总（未请求段 None）

        Raises:
            EntityValidationError: VO 构造守卫 242（转换阶段触发）
            FinancialCalculationError: 引擎数值求解失败 470（fail-loud 上抛——
                不吞不降级不返回部分结果）
        """
        schedule, assumptions, comparable_set, transaction_set = to_value_objects(request)
        dcf_result = None
        if schedule is not None and assumptions is not None:
            dcf_result = self._service.calculate_dcf(schedule, assumptions)
        comparable_result = None
        if comparable_set is not None and request.comparables is not None:
            comparable_result = self._service.calculate_comparable_valuation(comparable_set, request.comparables.target_ebitda)
        precedent_result = None
        if transaction_set is not None and request.precedents is not None:
            precedent_result = self._service.calculate_precedent_valuation(transaction_set, request.precedents.target_ebitda)
        return FinancialValuationResult(
            dcf=dcf_result,
            comparables=comparable_result,
            precedents=precedent_result,
        )


__all__ = ["FinancialModelingUseCase", "FinancialValuationResult", "to_value_objects"]
