"""领域层财务估值值对象模块（Story 5.12 财务建模与估值基础）

11 类 frozen dataclass 财务估值 VO 族：输入类 7（CashFlow / CashFlowSchedule /
DcfAssumptions / ComparableCompany / ComparableSet / PrecedentTransaction /
PrecedentTransactionSet——__post_init__ 抛 EntityValidationError 242 守卫）+
结果类 4（DcfValuationResult / MultiplesStats / ComparableValuationResult /
PrecedentValuationResult——纯载体零守卫：负 NPV / weight 越界是合法计算结果
非构造违例，防御过度守卫会使负 NPV 用例误抛 242）。

约束：
- 领域层零外部依赖（仅 Python 标准库 decimal/dataclasses）
- @dataclass(frozen=True) 不可变（schema_validator.py SchemaValidationResult 先例）
- Decimal 类型注解全程（OD-5：字符串构造 Decimal("0.1") 禁 float 中转）
- terminal_value_method 为 str 字段 + __post_init__ 闭集判等（domain 层零
  typing.Literal 依赖的判等守卫形态——与 Schema 层 Literal 对应）
- 符号变更在非零子序列上计数（Descartes 忽略零系数——[−100, 0, 110] 有一处
  变更放行；「相邻元素异号」实现对零成员序列两头误判，禁用）
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.domain.exceptions import EntityValidationError

#: 终值方法闭集（str 判等守卫——与 Schema 层 Literal["perpetual_growth", "exit_multiple"] 对应）
_TERMINAL_VALUE_METHODS: frozenset[str] = frozenset({"perpetual_growth", "exit_multiple"})


@dataclass(frozen=True)
class CashFlow:
    """单期现金流值对象

    period 是序数索引非量值（int 形态不套字符串数字 wire 契约——AC-1 Given 钦定）；
    amount 任意符号（负=流出/投资，正=流入/收益——零成员合法）。

    不变量约束:
    - period >= 1（序数索引从 1 起——年末贴现口径 t=1..n）

    Attributes:
        period: 期序（1 起严格序数）
        amount: 现金流金额（Decimal 字符串构造）
    """

    period: int
    amount: Decimal

    def __post_init__(self) -> None:
        """成员级守卫：period >= 1（违例 context field="period"）。"""
        if self.period < 1:
            raise EntityValidationError(
                message=f"period 必须为不小于 1 的序数索引，当前值: {self.period}",
                context={"entity": "CashFlow", "field": "period"},
            )


@dataclass(frozen=True)
class CashFlowSchedule:
    """现金流表值对象（DCF 输入面）

    字段名 cash_flows（与守卫锚 context field="cash_flows" / Schema 段名一致）。

    不变量约束:
    - cash_flows 非空（min 1）
    - period 从 1 严格连续（枚举位次等于期序——覆盖重复与非 1 起）
    - 至少一次符号变更（IRR 可解必要条件——Descartes 符号规则，在非零子序列上
      计数：[−100, 0, 110] 放行 / [100, 50] 拒绝；[−100, 0.0001, −110] 非零
      子序列有变更故放行——IRR 实不存在由引擎层 bracket 470 兜底，两层分工）

    Attributes:
        cash_flows: 逐期现金流元组（按期序排列）
    """

    cash_flows: tuple[CashFlow, ...]

    def __post_init__(self) -> None:
        """schedule 级守卫：非空 + 严格连续 + 符号变更存在（违例 field="cash_flows"）。"""
        if not self.cash_flows:
            raise EntityValidationError(
                message="cash_flows 必须为非空序列（DCF 计算至少一期现金流）",
                context={"entity": "CashFlowSchedule", "field": "cash_flows"},
            )
        # 校验 2: period 从 1 严格连续（枚举位次 != 期序覆盖重复/跳期/非 1 起三类违规）
        for expected_period, flow in enumerate(self.cash_flows, start=1):
            if flow.period != expected_period:
                raise EntityValidationError(
                    message=f"cash_flows 的 period 必须从 1 严格连续，第 {expected_period} 位期望 "
                    f"period={expected_period}，实际 period={flow.period}",
                    context={"entity": "CashFlowSchedule", "field": "cash_flows"},
                )
        # 校验 3: 符号变更在非零子序列上计数（Descartes 忽略零系数——禁「相邻异号」实现）
        nonzero_signs = [-1 if flow.amount < 0 else 1 for flow in self.cash_flows if flow.amount != 0]
        sign_changes = sum(1 for current, following in zip(nonzero_signs, nonzero_signs[1:]) if current != following)
        if sign_changes < 1:
            raise EntityValidationError(
                message="cash_flows 至少需要一次符号变更（IRR 可解必要条件——全正或全负序列无内部收益率）",
                context={"entity": "CashFlowSchedule", "field": "cash_flows"},
            )


@dataclass(frozen=True)
class DcfAssumptions:
    """DCF 折现假设值对象（终值两法——永续增长 / 退出倍数）

    不变量约束:
    - 0 < discount_rate < 1（折现率经济域）
    - terminal_value_method ∈ {"perpetual_growth", "exit_multiple"}（闭集判等）
    - perpetual_growth 法：terminal_growth_rate 必填（g >= 0 且 g < r——r−g 分母
      非正不可解，构造期静态可判定的不变量归 VO 层）、exit 两字段须 None
    - exit_multiple 法：exit_multiple 与 terminal_exit_metric 必填且 > 0
      （terminal_exit_metric 语义 = 终年 EBITDA——与可比法 ev_ebitda 同分母口径，
      任意的 metric×multiple 组合会静默产出单位错配值）、g 须 None

    Attributes:
        discount_rate: 折现率（年末贴现口径——与 Excel NPV() 函数一致）
        terminal_value_method: 终值方法（str 闭集判等）
        terminal_growth_rate: 永续增长率（perpetual_growth 法专用）
        exit_multiple: 退出倍数（exit_multiple 法专用——EV/EBITDA 口径）
        terminal_exit_metric: 终年 EBITDA（exit_multiple 法专用——分母口径钦定）
    """

    discount_rate: Decimal
    terminal_value_method: str
    terminal_growth_rate: Decimal | None = None
    exit_multiple: Decimal | None = None
    terminal_exit_metric: Decimal | None = None

    def __post_init__(self) -> None:
        """跨字段守卫：折现率域 + 法闭集 + 法-参数互斥配套。"""
        if self.discount_rate <= 0 or self.discount_rate >= 1:
            raise EntityValidationError(
                message=f"discount_rate 必须落于开区间 (0, 1)，当前值: {self.discount_rate}",
                context={"entity": "DcfAssumptions", "field": "discount_rate"},
            )
        if self.terminal_value_method not in _TERMINAL_VALUE_METHODS:
            raise EntityValidationError(
                message=f"terminal_value_method 必须为闭集 {{perpetual_growth, exit_multiple}} 成员，"
                f"当前值: {self.terminal_value_method}",
                context={"entity": "DcfAssumptions", "field": "terminal_value_method"},
            )
        if self.terminal_value_method == "perpetual_growth":
            if self.terminal_growth_rate is None:
                raise EntityValidationError(
                    message="perpetual_growth 法必须提供 terminal_growth_rate（法配套必填）",
                    context={"entity": "DcfAssumptions", "field": "terminal_growth_rate"},
                )
            if self.terminal_growth_rate < 0:
                raise EntityValidationError(
                    message=f"terminal_growth_rate 必须非负，当前值: {self.terminal_growth_rate}",
                    context={"entity": "DcfAssumptions", "field": "terminal_growth_rate"},
                )
            if self.terminal_growth_rate >= self.discount_rate:
                raise EntityValidationError(
                    message=f"terminal_growth_rate（{self.terminal_growth_rate}）必须小于 "
                    f"discount_rate（{self.discount_rate}）——永续增长公式 r−g 分母非正不可解",
                    context={"entity": "DcfAssumptions", "field": "terminal_growth_rate"},
                )
            if self.exit_multiple is not None or self.terminal_exit_metric is not None:
                offending_field = "exit_multiple" if self.exit_multiple is not None else "terminal_exit_metric"
                raise EntityValidationError(
                    message=f"perpetual_growth 法不得携带 {offending_field}（法-参数互斥——非本法参数须 None）",
                    context={"entity": "DcfAssumptions", "field": offending_field},
                )
        else:
            if self.exit_multiple is None:
                raise EntityValidationError(
                    message="exit_multiple 法必须提供 exit_multiple（法配套必填）",
                    context={"entity": "DcfAssumptions", "field": "exit_multiple"},
                )
            if self.exit_multiple <= 0:
                raise EntityValidationError(
                    message=f"exit_multiple 必须为正，当前值: {self.exit_multiple}",
                    context={"entity": "DcfAssumptions", "field": "exit_multiple"},
                )
            if self.terminal_exit_metric is None:
                raise EntityValidationError(
                    message="exit_multiple 法必须提供 terminal_exit_metric（终年 EBITDA——法配套必填）",
                    context={"entity": "DcfAssumptions", "field": "terminal_exit_metric"},
                )
            if self.terminal_exit_metric <= 0:
                raise EntityValidationError(
                    message=f"terminal_exit_metric 必须为正（终年 EBITDA——V1 不支持亏损标的），"
                    f"当前值: {self.terminal_exit_metric}",
                    context={"entity": "DcfAssumptions", "field": "terminal_exit_metric"},
                )
            if self.terminal_growth_rate is not None:
                raise EntityValidationError(
                    message="exit_multiple 法不得携带 terminal_growth_rate（法-参数互斥——非本法参数须 None）",
                    context={"entity": "DcfAssumptions", "field": "terminal_growth_rate"},
                )


@dataclass(frozen=True)
class DcfValuationResult:
    """DCF 估值结果值对象（纯载体——零 __post_init__ 守卫）

    负 NPV 与 weight 越界（>1 或 <0）是合法经济结果非构造违例（AC-1 Then① 钦定
    结果类零守卫——防御过度守卫使负 NPV 用例误抛 242）。

    Attributes:
        present_values: 逐期现值（可观测中间量——PV_t = CF_t/(1+r)^t，年末贴现）
        npv: 净现值（Σ present_values + 折现终值）
        terminal_value: 终值（未折现名义值——永续增长或退出倍数法）
        terminal_value_weight: 折现终值占 NPV 比（terminal_value/(1+r)^n/npv）
        irr: 内部收益率（二分法迭代解——仅显性现金流序列，不含终值）
    """

    present_values: tuple[Decimal, ...]
    npv: Decimal
    terminal_value: Decimal
    terminal_value_weight: Decimal
    irr: Decimal


@dataclass(frozen=True)
class ComparableCompany:
    """可比公司值对象

    不变量约束:
    - name 非空（标识）
    - ev_ebitda > 0（倍数域正值不变量）

    Attributes:
        name: 可比公司名称
        ev_ebitda: EV/EBITDA 倍数（交易市场倍数口径）
    """

    name: str
    ev_ebitda: Decimal

    def __post_init__(self) -> None:
        """成员级守卫：name 非空 + ev_ebitda > 0。"""
        if not self.name:
            raise EntityValidationError(
                message="name 必须为非空字符串（可比公司标识）",
                context={"entity": "ComparableCompany", "field": "name"},
            )
        if self.ev_ebitda <= 0:
            raise EntityValidationError(
                message=f"ev_ebitda 必须为正（倍数域正值不变量），当前值: {self.ev_ebitda}",
                context={"entity": "ComparableCompany", "field": "ev_ebitda"},
            )


@dataclass(frozen=True)
class ComparableSet:
    """可比公司集合值对象（字段名 comparables——与 Schema 段名一致）

    不变量约束:
    - comparables 非空（min 1——空集合统计无意义，VO 层拦截后引擎零空集合防御分支）

    Attributes:
        comparables: 可比公司元组
    """

    comparables: tuple[ComparableCompany, ...]

    def __post_init__(self) -> None:
        """集合级守卫：非空（违例 field="comparables"）。"""
        if not self.comparables:
            raise EntityValidationError(
                message="comparables 必须为非空集合（可比估值至少一家可比公司）",
                context={"entity": "ComparableSet", "field": "comparables"},
            )


@dataclass(frozen=True)
class MultiplesStats:
    """倍数描述统计值对象（纯载体——零守卫）

    Excel MIN/MEDIAN/AVERAGE/MAX 四值对齐口径；median 偶数样本取中间两数均值
    （statistics.median 官方语义——Decimal 域原生支持）。

    Attributes:
        min: 最小倍数
        median: 中位倍数
        mean: 平均倍数（Decimal 域自实现 sum/len——引擎 _multiple_stats[CR3-1①：statistics.mean 有理转换挂死面改定]）
        max: 最大倍数
    """

    min: Decimal
    median: Decimal
    mean: Decimal
    max: Decimal


@dataclass(frozen=True)
class ComparableValuationResult:
    """可比公司估值结果值对象（纯载体——零守卫）

    Attributes:
        multiples_stats: 倍数统计四值
        implied_ev_low: 隐含企业价值下界（stats.min × target_ebitda）
        implied_ev_median: 隐含企业价值中位（stats.median × target_ebitda）
        implied_ev_high: 隐含企业价值上界（stats.max × target_ebitda）
    """

    multiples_stats: MultiplesStats
    implied_ev_low: Decimal
    implied_ev_median: Decimal
    implied_ev_high: Decimal


@dataclass(frozen=True)
class PrecedentTransaction:
    """先例交易值对象

    不变量约束:
    - target_name 非空（标识）
    - ev_ebitda > 0（倍数域正值不变量——交易对价倍数口径）

    Attributes:
        target_name: 交易标的名称
        ev_ebitda: 交易对价 EV/EBITDA 倍数
    """

    target_name: str
    ev_ebitda: Decimal

    def __post_init__(self) -> None:
        """成员级守卫：target_name 非空 + ev_ebitda > 0。"""
        if not self.target_name:
            raise EntityValidationError(
                message="target_name 必须为非空字符串（先例交易标的标识）",
                context={"entity": "PrecedentTransaction", "field": "target_name"},
            )
        if self.ev_ebitda <= 0:
            raise EntityValidationError(
                message=f"ev_ebitda 必须为正（倍数域正值不变量），当前值: {self.ev_ebitda}",
                context={"entity": "PrecedentTransaction", "field": "ev_ebitda"},
            )


@dataclass(frozen=True)
class PrecedentTransactionSet:
    """先例交易集合值对象（字段名 transactions——与 Schema 段名一致）

    不变量约束:
    - transactions 非空（min 1）

    Attributes:
        transactions: 先例交易元组
    """

    transactions: tuple[PrecedentTransaction, ...]

    def __post_init__(self) -> None:
        """集合级守卫：非空（违例 field="transactions"）。"""
        if not self.transactions:
            raise EntityValidationError(
                message="transactions 必须为非空集合（先例交易估值至少一笔交易）",
                context={"entity": "PrecedentTransactionSet", "field": "transactions"},
            )


@dataclass(frozen=True)
class PrecedentValuationResult:
    """先例交易估值结果值对象（纯载体——零守卫，同 Comparable 结果形态）

    语义与 ComparableValuationResult 同构但独立类型：可比是交易市场倍数、先例是
    交易对价倍数（语义入口分立——共享统计数学经引擎私有 helper 承载，VO 独立）。

    Attributes:
        multiples_stats: 对价倍数统计四值
        implied_ev_low: 隐含参考价值下界
        implied_ev_median: 隐含参考价值中位
        implied_ev_high: 隐含参考价值上界
    """

    multiples_stats: MultiplesStats
    implied_ev_low: Decimal
    implied_ev_median: Decimal
    implied_ev_high: Decimal


__all__ = [
    "CashFlow",
    "CashFlowSchedule",
    "ComparableCompany",
    "ComparableSet",
    "ComparableValuationResult",
    "DcfAssumptions",
    "DcfValuationResult",
    "MultiplesStats",
    "PrecedentTransaction",
    "PrecedentTransactionSet",
    "PrecedentValuationResult",
]
