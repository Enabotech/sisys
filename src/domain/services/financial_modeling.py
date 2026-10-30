"""领域层财务建模与估值服务模块（Story 5.12 财务建模与估值基础）

确定性估值计算引擎：DCF 现金流折现（NPV + 终值两法 + IRR 二分法）+ 可比公司
倍数法 + 先例交易法。全部 decimal.Decimal 精确计算（OD-5：字符串构造
Decimal("0.1") 禁 float 中转——全仓首个 Decimal 算术面，与 cost_calculator 的
float 先例是精度标准升级差异点）。

钦定注记（AC-1 And 全集）：
- 贴现口径：年末惯例（end-of-year——PV_t = CF_t/(1+r)^t，t=1..n，与 Excel
  NPV() 函数口径一致；期初口径[Excel NPV×(1+r) 或 XNPV]不在 V1）。
- 初始投资 t=0 惯例知悉：业者资本预算惯例是 =CF0 + NPV(rate, CF1:CFn)（CF0
  外置不折现）——本引擎 period>=1 使首笔现金流亦折现一期，结果较 t=0 口径
  整体 ÷(1+r)（IRR 因平移不变性不受影响）。引擎与 Schema docstring 显式注记
  此语义差异，防 CFO 消费方直觉错读。
- IRR 求解对象：仅显性现金流序列 Σ CF_t/(1+r)^t = 0（与 Excel IRR(CF0:CFn)
  同口径——不含终值；含终值的 total-returns IRR 归 V2+ 完整版）。
- 计算精度：localcontext prec=50（默认 28 位在十年期 (1+r)^10 连乘下可能截断；
  localcontext 而非模块级 getcontext()——后者不传播到新建线程，并发路径会
  静默降精度）。
- IRR 求解：二分法 + bracket 前提（NPV 端点异号）+ 收敛判据区间宽度 < 1e-12 +
  最大迭代 256 次防御；支持域 (−0.99, 10) 即 IRR∈(−99%, 1000%)。
- 退出倍数法指标口径：terminal_exit_metric 语义 = 终年 EBITDA（与可比法
  ev_ebitda 同分母口径——任意的 metric×multiple 组合会静默产出单位错配值）。

设计决策（DC-2/DC-9）：
- 单类三方法 + 类即接口注册（debate_evaluator 无状态领域服务注册先例——
  组合根字符串 impl SINGLETON）
- 无状态纯计算零共享可变状态（VO in / VO out 全 frozen——SINGLETON 并发安全）
- 领域层零外部依赖（decimal/statistics 标准库——import-linter 白名单天然过）
"""

from __future__ import annotations

import statistics
from decimal import Decimal, localcontext
from typing import cast

from src.domain.exceptions import FinancialCalculationError
from src.domain.value_objects.financial_valuation import (
    CashFlowSchedule,
    ComparableSet,
    ComparableValuationResult,
    DcfAssumptions,
    DcfValuationResult,
    MultiplesStats,
    PrecedentTransactionSet,
    PrecedentValuationResult,
)

#: 计算精度（OD-5③ 钦定 prec=50——DCF 十年期幂运算连乘位数增长，默认 28 位可能截断）
_CALC_PRECISION = 50

#: IRR 二分 bracket 下界（支持域 (−0.99, 10)——经济现实覆盖知悉注记）
_IRR_RATE_LOW = Decimal("-0.99")
#: IRR 二分 bracket 上界
_IRR_RATE_HIGH = Decimal("10")
#: IRR 收敛判据（区间宽度唯一判据——连续性下 1e-12 宽度时中点必近零，双判据冗余）
_IRR_INTERVAL_TOLERANCE = Decimal("1e-12")
#: IRR 最大迭代次数（理论 bracket 下二分必收敛——防御分支，正常收敛约 44 次）
_IRR_MAX_ITERATIONS = 256


class FinancialModelingService:
    """财务建模与估值领域服务（三方法确定性计算引擎）

    SINGLETON 注册前提：无状态纯计算零共享可变状态（同输入同输出——DC-9 并发
    安全论证：VO in / VO out 全 frozen，localcontext 线程隔离）。

    三方法：
    - calculate_dcf：DCF 现金流折现（NPV + 终值两法 + IRR 二分法）
    - calculate_comparable_valuation：可比公司倍数统计 + 隐含企业价值区间
    - calculate_precedent_valuation：先例交易倍数统计 + 隐含参考区间
    """

    def calculate_dcf(self, schedule: CashFlowSchedule, assumptions: DcfAssumptions) -> DcfValuationResult:
        """DCF 现金流折现估值（NPV + 终值两法 + IRR）。

        Excel 公式对照（业务面交叉对照）：
        - NPV: =NPV(rate, CF1:CFn) + TV/(1+rate)^n（年末贴现——t=1..n）
        - 永续增长终值: TV = CF_n*(1+g)/(r-g)（Gordon 模型）
        - 退出倍数终值: TV = exit_multiple * 终年 EBITDA
        - IRR: =IRR(CF0:CFn)（仅显性现金流——不含终值）

        Args:
            schedule: 现金流表（VO 构造即验——非空/严格连续/符号变更存在）
            assumptions: 折现假设（VO 构造即验——折现率域/法闭集/法配套互斥）

        Returns:
            DcfValuationResult 五字段（present_values/npv/terminal_value/
            terminal_value_weight/irr——结果类零守卫：负 NPV 与 weight 越界是
            合法经济结果）

        Raises:
            FinancialCalculationError: 数值求解失败双路径（①IRR bracket 端点同号等
                病态输入 ②NPV 为零使 terminal_value_weight 分母失效——盈亏平衡精确
                抵消输入；均 fail-loud 显式报错而非静默返回 None；method="dcf"）
        """
        with localcontext() as decimal_context:
            decimal_context.prec = _CALC_PRECISION
            one = Decimal(1)
            discount_base = one + assumptions.discount_rate
            # 逐期现值（年末贴现口径：PV_t = CF_t/(1+r)^t，t=1..n）
            present_values = tuple(flow.amount / discount_base**flow.period for flow in schedule.cash_flows)
            terminal_value = self._terminal_value(schedule, assumptions)
            period_count = len(schedule.cash_flows)
            discounted_terminal_value = terminal_value / discount_base**period_count
            npv = sum(present_values, Decimal(0)) + discounted_terminal_value
            if npv == 0:
                # npv==0 ⟹ 结果不可定义（盈亏平衡精确抵消：weight 分母失效——
                # Decimal 精确算术下可确定性构造，非浮点巧合；fail-loud 470 短路，
                # 与 IRR 求解失败同语义族——弃 weight 置 0/None 的静默经济谎言形态）
                raise FinancialCalculationError(
                    method="dcf",
                    detail="NPV 为零——terminal_value_weight 无定义（盈亏平衡输入，请调整折现率或现金流后重试）",
                )
            # 折现终值占比（weight = PV(TV)/npv——结果类零守卫，npv<0 或 ΣPV<0 时
            # 允许 (0,1) 外值：重前期投入序列 PV(TV)>npv → weight>1 属正常经济结果）
            terminal_value_weight = discounted_terminal_value / npv
            irr = self._solve_irr(schedule)
        return DcfValuationResult(
            present_values=present_values,
            npv=npv,
            terminal_value=terminal_value,
            terminal_value_weight=terminal_value_weight,
            irr=irr,
        )

    @staticmethod
    def _terminal_value(schedule: CashFlowSchedule, assumptions: DcfAssumptions) -> Decimal:
        """终值计算（未折现名义值——两法分派）。

        Args:
            schedule: 现金流表（终年现金流取末位成员）
            assumptions: 折现假设（法配套参数经 VO 守卫非 None）

        Returns:
            永续增长法 TV = CF_n×(1+g)/(r−g)；退出倍数法 TV = exit_multiple×终年 EBITDA
        """
        one = Decimal(1)
        final_amount = schedule.cash_flows[-1].amount
        if assumptions.terminal_value_method == "perpetual_growth":
            # cast 可信契约标注（VO 法配套守卫保证非 None——非运行时防御）
            growth = cast(Decimal, assumptions.terminal_growth_rate)
            return final_amount * (one + growth) / (assumptions.discount_rate - growth)
        exit_multiple = cast(Decimal, assumptions.exit_multiple)
        terminal_exit_metric = cast(Decimal, assumptions.terminal_exit_metric)
        return exit_multiple * terminal_exit_metric

    @staticmethod
    def _solve_irr(schedule: CashFlowSchedule) -> Decimal:
        """IRR 二分法求解（仅显性现金流——与折现率假设无关）。

        Excel IRR 官方口径对照：从 guess[默认 0.1] 出发迭代求解、20 次内精度
        0.00001 percent 不收敛则 #NUM!——本引擎端点同号即 470 更严格（双根序列
        [−100, 230, −132] 在 Excel guess=0.1 恰收敛返回 10%，本引擎知悉注记非
        bug：fail-loud 审计语义钦定——数值不可解或根歧义时显式报错）。

        Args:
            schedule: 现金流表（VO 已守卫符号变更存在——IRR 可解必要条件非充分
                条件：静态必要条件归 VO 层 242、数值求解失败归引擎层 470 分工）

        Returns:
            IRR 迭代解（收敛区间宽度 < 1e-12——相对误差约 1e-11 量级）

        Raises:
            FinancialCalculationError: bracket 失败（NPV 端点同号）或迭代超上限
                （method="dcf"——触发面之一；另见 calculate_dcf 的 NPV 为零守卫）
        """

        def npv_at_rate(rate: Decimal) -> Decimal:
            """该折现率下的显性现金流 NPV（Σ CF_t/(1+r)^t——不含终值）。"""
            discount_base = Decimal(1) + rate
            return sum(
                (flow.amount / discount_base**flow.period for flow in schedule.cash_flows),
                Decimal(0),
            )

        rate_low, rate_high = _IRR_RATE_LOW, _IRR_RATE_HIGH
        # bracket 前置检查（端点异号——同号即 fail-loud 470，不进循环防死循环）
        if npv_at_rate(rate_low) * npv_at_rate(rate_high) > 0:
            raise FinancialCalculationError(
                method="dcf",
                detail="IRR 数值求解失败：支持域端点净现值同号（无符号变更的根或根歧义病态序列）",
            )
        # 二分迭代（bracket 下必然收敛可证——迭代减半区间；收敛判据唯一：区间宽度）
        for _ in range(_IRR_MAX_ITERATIONS):
            midpoint = (rate_low + rate_high) / 2
            if rate_high - rate_low < _IRR_INTERVAL_TOLERANCE:
                return midpoint
            if npv_at_rate(rate_low) * npv_at_rate(midpoint) <= 0:
                rate_high = midpoint
            else:
                rate_low = midpoint
        raise FinancialCalculationError(
            method="dcf",
            detail="IRR 数值求解失败：迭代超出上限仍未收敛（防御分支——理论 bracket 下二分必收敛）",
        )

    def calculate_comparable_valuation(self, comparables: ComparableSet, target_ebitda: Decimal) -> ComparableValuationResult:
        """可比公司倍数估值（交易市场倍数口径）。

        Excel 公式对照：=MIN/MEDIAN/AVERAGE/MAX(倍数区间) × target_ebitda。

        语义注记：V1 全集统计无离群值剔除、无行业细分（完整版归 V2——prd L528
        语义锚）；low/median/high 是倍数区间×目标指标的机械映射（投资判断口径
        [剔除/加权]是 LLM 推荐面——OD-2 V2+）；target_ebitda 是引擎裸参数非 VO
        字段（负值拦截在 Schema 层 gt=0——引擎层单层守卫钦定不重复守卫）。

        Args:
            comparables: 可比公司集合（VO 已守卫非空 + 倍数正值）
            target_ebitda: 目标公司 EBITDA（Schema 层 gt=0 拦截负值——直调引擎
                传负值属调用方契约外）

        Returns:
            ComparableValuationResult（统计四值 + 隐含企业价值区间三值）
        """
        with localcontext() as decimal_context:
            decimal_context.prec = _CALC_PRECISION
            stats = self._multiple_stats(tuple(company.ev_ebitda for company in comparables.comparables))
            return ComparableValuationResult(
                multiples_stats=stats,
                implied_ev_low=stats.min * target_ebitda,
                implied_ev_median=stats.median * target_ebitda,
                implied_ev_high=stats.max * target_ebitda,
            )

    def calculate_precedent_valuation(
        self, transactions: PrecedentTransactionSet, target_ebitda: Decimal
    ) -> PrecedentValuationResult:
        """先例交易倍数估值（交易对价倍数口径）。

        与可比引擎语义分立：可比是交易市场倍数（二级市场估值）、先例是交易对价
        倍数（并购控制权溢价内含）——共享统计数学经 _multiple_stats 承载，入口
        与结果类型独立（语义入口分立钦定）。

        Args:
            transactions: 先例交易集合（VO 已守卫非空 + 倍数正值）
            target_ebitda: 目标公司 EBITDA（同可比法口径）

        Returns:
            PrecedentValuationResult（对价倍数统计 + 隐含参考区间三值）
        """
        with localcontext() as decimal_context:
            decimal_context.prec = _CALC_PRECISION
            stats = self._multiple_stats(tuple(txn.ev_ebitda for txn in transactions.transactions))
            return PrecedentValuationResult(
                multiples_stats=stats,
                implied_ev_low=stats.min * target_ebitda,
                implied_ev_median=stats.median * target_ebitda,
                implied_ev_high=stats.max * target_ebitda,
            )

    @staticmethod
    def _multiple_stats(values: tuple[Decimal, ...]) -> MultiplesStats:
        """倍数描述统计（两引擎共享私有 helper——数学同构，语义入口分立）。

        statistics.mean/median 原生支持 Decimal（Python 3.11 官方语义——median
        偶数样本取中间两数均值）；本 helper 调用方均在 localcontext prec=50 内
        （statistics.mean 的除法在默认 prec=28 下舍入——精度纪律全程一致）。

        Args:
            values: 倍数元组（VO 已守卫非空 + 正值）

        Returns:
            MultiplesStats 四值（min/median/mean/max）
        """
        return MultiplesStats(
            min=min(values),
            median=statistics.median(values),
            mean=statistics.mean(values),
            max=max(values),
        )


__all__ = ["FinancialModelingService"]
