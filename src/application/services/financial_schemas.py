"""应用层 财务估值请求 Pydantic Schema 模块

定义财务估值三段请求 Schema 族（DCF 现金流折现 / 可比公司倍数 / 先例交易倍数），
作为财务建模估值用例的外部输入契约（epics L1967「输入 Schema 测试——验证财务
数据输入契约」的结构化承载）。

设计决策：
- 定义在应用层（src/application/），允许依赖 Pydantic——领域层零外部依赖约束
  不适用于此（summary_schemas.py L8-12 先例）
- wire 契约：数字字段钦定字符串形态（金融工程惯例——FIX 协议价格/数量字段
  wire 形态即 ASCII 文本十进制；str→Decimal 解析零精度损失）；数值形态
  （int/float）经 pydantic 官方 str 换算兼容接受（AC-3 When② 知悉注记口径：
  实测 v2.13 经最短表示换算无二进制噪声——55 位噪声仅出现在直接 Decimal(float)
  构造；>17 位有效数字的 float 表示域截断除外，精度意图显式化是 str 形态的
  实际价值[CR2-2 措辞对齐钦定——不启用 Strict 拒绝]）；period 是序数索引
  非量值，int 形态不套字符串契约
- Schema-VO 约束镜像双层守卫（刻意冗余）：Schema 是外部契约面（pydantic 约束，
  框架异常可读性好），VO 是领域不变量面（__post_init__ 242 独立守卫防绕过
  Schema 的内部构造——防御纵深，两层测试各自覆盖）；**max_length 单层
  carve-out（CR2-1）**：三 list 字段的长度上限是资源策略（超长输入 DoS 防御）
  非领域不变量——仅 Schema 单层拦截，VO 层不加期数上限（内部构造信任边界）；
  **量级界同属单层资源策略（CR3-1②）**：amount 双侧 ±1E+15（10 倍全球 GDP
  量级上界）/ 倍数类 le=1E+9（荒谬上界）——封大量级 decimal.Overflow 非领域
  异常逃逸面与 statistics 挂死残余面；pydantic 对 Decimal 字段默认拒绝
  NaN/±Infinity（finite_number——非有限值非本层需处理的面）
- wire 接受面知悉（CR3-7）：接受面=Decimal 解析器超集（Unicode 数字/下划线
  分隔/前后空白/正号/前导零均容许——语义零精度损失，比 FIX-ASCII 表述宽）
- 三层异常语义分立：Schema 层 pydantic.ValidationError / VO 层 242 / 引擎层
  470——框架原生异常透传不包装
- 校验器异常形态（CR1-2 代码审查裁定）：model_validator 内以
  raise AssertionError("...") 显式 raise 形态 signalling 校验失败——pydantic v2
  官方钦定双形态（ValueError or AssertionError 均被框架捕获包装为 ValidationError
  零逃逸），本项目取 AssertionError 形态使红线自查（禁止 ValueError raise 形态）
  在本 Story 交付面归零。两点纪律：①禁改写为 assert 语句形态（python -O 下
  校验整体静默消失）；②错误 msg 会被 pydantic 加英文前缀
  "Assertion failed, "（REST 面 7-2 接线时知悉——OpenAPI 422 响应
  type=assertion_error 无契约约束）
- 结果类字段不在 Schema 层重复定义（请求面纯输入契约——结果 DTO 在用例文件，
  防双向耦合）
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DcfCashFlowItem(BaseModel):
    """单期现金流输入项（period 序数索引 int + amount 字符串数字）。"""

    period: int = Field(..., ge=1, description="期序（1 起严格序数索引——年末贴现口径 t=1..n）")
    amount: Decimal = Field(
        ...,
        ge=Decimal("-1E+15"),
        le=Decimal("1E+15"),
        description="现金流金额（字符串数字 wire 形态——负=流出；量级界 ±1E+15 双侧[CR3-1②]）",
    )


class DcfRequestSection(BaseModel):
    """DCF 估值请求段（现金流表 + 折现假设——终值两法）。

    期数由 cash_flows 长度承载（不设 projection_periods 冗余期数字段）。

    t=0 初始投资口径知悉：业者资本预算惯例是 =CF0 + NPV(rate, CF1:CFn)（CF0 外置
    不折现）——本契约 period>=1 使首笔现金流亦折现一期，估值结果较 t=0 口径整体
    ÷(1+r)（IRR 因平移不变性不受影响），防 CFO 消费方直觉错读。
    """

    cash_flows: list[DcfCashFlowItem] = Field(
        ...,
        min_length=1,
        max_length=1200,
        description=(
            "逐期现金流（非空——与 CashFlowSchedule VO 非空不变量镜像；上限 1200=月度百年模型量级——超长输入资源防御[CR2-1]）"
        ),
    )
    discount_rate: Decimal = Field(..., gt=0, lt=1, description="折现率（开区间 (0,1)——年末贴现口径）")
    terminal_value_method: Literal["perpetual_growth", "exit_multiple"] = Field(
        ..., description="终值方法（永续增长 Gordon / 退出倍数两法）"
    )
    terminal_growth_rate: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "永续增长率（perpetual_growth 法必填且 < discount_rate）；"
            "知悉：g 与 r 差值过小时终值发散（Gordon 模型本性——g=0.099999/r=0.1 时 TV≈110 万倍末年现金流，CR3-6 警示）"
        ),
    )
    exit_multiple: Decimal | None = Field(
        default=None,
        gt=0,
        le=Decimal("1E+9"),
        description="退出倍数 EV/EBITDA（exit_multiple 法必填；量级界 1E+9[CR3-1②]）",
    )
    terminal_exit_metric: Decimal | None = Field(
        default=None,
        gt=0,
        le=Decimal("1E+15"),
        description="终年 EBITDA（exit_multiple 法必填——与可比法 ev_ebitda 同分母口径钦定；量级界 1E+15[CR3-1②]）",
    )

    @model_validator(mode="after")
    def _validate_method_parameter_pairing(self) -> DcfRequestSection:
        """终值两法字段配套校验（法配套必填 + 法-参数互斥 + g<r 二次守卫——VO 层镜像）。"""
        if self.terminal_value_method == "perpetual_growth":
            if self.terminal_growth_rate is None:
                raise AssertionError("perpetual_growth 法必须提供 terminal_growth_rate")
            if self.terminal_growth_rate >= self.discount_rate:
                raise AssertionError("terminal_growth_rate 必须小于 discount_rate（r−g 分母非正不可解）")
            if self.exit_multiple is not None or self.terminal_exit_metric is not None:
                raise AssertionError("perpetual_growth 法不得携带 exit_multiple/terminal_exit_metric（法-参数互斥）")
        else:
            if self.exit_multiple is None:
                raise AssertionError("exit_multiple 法必须提供 exit_multiple")
            if self.terminal_exit_metric is None:
                raise AssertionError("exit_multiple 法必须提供 terminal_exit_metric（终年 EBITDA）")
            if self.terminal_growth_rate is not None:
                raise AssertionError("exit_multiple 法不得携带 terminal_growth_rate（法-参数互斥）")
        return self


class ComparableCompanyInput(BaseModel):
    """可比公司输入项。"""

    name: str = Field(..., min_length=1, description="可比公司名称")
    ev_ebitda: Decimal = Field(
        ...,
        gt=0,
        le=Decimal("1E+9"),
        description="EV/EBITDA 交易市场倍数（正值域；量级界 1E+9[CR3-1②]）",
    )


class ComparableRequestSection(BaseModel):
    """可比公司估值请求段（交易市场倍数口径）。"""

    comparables: list[ComparableCompanyInput] = Field(
        ...,
        min_length=1,
        max_length=100,
        description=("可比公司集合（非空——与 ComparableSet VO 不变量镜像；上限 100=业界 5~20 家惯例的 5 倍裕度[CR2-1]）"),
    )
    target_ebitda: Decimal = Field(
        ...,
        gt=0,
        le=Decimal("1E+15"),
        description=(
            "目标公司 EBITDA（正值——V1 倍数法不支持负 EBITDA 亏损标的，引擎层无 242 落点由此拦截；量级界 1E+15[CR3-1②]）"
        ),
    )


class PrecedentTransactionInput(BaseModel):
    """先例交易输入项。"""

    target_name: str = Field(..., min_length=1, description="交易标的名称")
    ev_ebitda: Decimal = Field(
        ...,
        gt=0,
        le=Decimal("1E+9"),
        description="交易对价 EV/EBITDA 倍数（正值域；量级界 1E+9[CR3-1②]）",
    )


class PrecedentRequestSection(BaseModel):
    """先例交易估值请求段（交易对价倍数口径）。"""

    transactions: list[PrecedentTransactionInput] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="先例交易集合（非空——与 PrecedentTransactionSet VO 不变量镜像；上限 100=业界惯例 5 倍裕度[CR2-1]）",
    )
    target_ebitda: Decimal = Field(
        ...,
        gt=0,
        le=Decimal("1E+15"),
        description=(
            "目标公司 EBITDA（正值——V1 倍数法不支持负 EBITDA 亏损标的，引擎层无 242 落点由此拦截[CR4-6 与可比段双落]；"
            "量级界 1E+15[CR3-1②]）"
        ),
    )


class FinancialValuationRequest(BaseModel):
    """财务估值统一请求（三段可选载荷——顶层三字段名 dcf/comparables/precedents 与结果 DTO 三段同名）。

    至少一段非 None（单法请求自由度 + 全量汇总两形态承载）。
    """

    dcf: DcfRequestSection | None = Field(default=None, description="DCF 现金流折现段（未请求为 None）")
    comparables: ComparableRequestSection | None = Field(default=None, description="可比公司倍数段（未请求为 None）")
    precedents: PrecedentRequestSection | None = Field(default=None, description="先例交易倍数段（未请求为 None）")

    @model_validator(mode="after")
    def _validate_at_least_one_section(self) -> FinancialValuationRequest:
        """跨段守卫：至少一段非 None（三段全 None 拒绝）。"""
        if self.dcf is None and self.comparables is None and self.precedents is None:
            raise AssertionError("至少需要提供 dcf/comparables/precedents 三段之一")
        return self


__all__ = [
    "ComparableCompanyInput",
    "ComparableRequestSection",
    "DcfCashFlowItem",
    "DcfRequestSection",
    "FinancialValuationRequest",
    "PrecedentTransactionInput",
    "PrecedentRequestSection",
]
