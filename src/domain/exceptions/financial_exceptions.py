"""financial 子域异常（financial，470-479）——Story 5.12 财务建模与估值基础。

financial 子域单异常：FinancialCalculationError（470——财务计算失败，BusinessException）。

开段先例（第七段）：sap 段 460-469 之后「语义独立 → 开独立段」（data_source 410/
debate 420/tool_version 430/agent 440/evaluation 450/sap 460 六段同款）；471-479
预留 financial 域后续异常。

语义归属：470 business（数值求解失败 = 输入数据使计算约束不可满足，调用方可调整
输入/换方法重试——语义挂 BusinessRuleViolationError 422 族「业务约束不可满足」；
与 evaluation 子域 450 的 SystemException 族形成对照：本 Story 基类选型经异常
契约节勘误注裁定，仅取评估子域 450 的 kwargs 构造形态模板——kwargs 领域参数在
前 + message 缺省回落 + context_extra 合并）。
"""

from __future__ import annotations

from src.domain.exceptions.business_exceptions import BusinessException

__all__ = ["FinancialCalculationError"]


class FinancialCalculationError(BusinessException):
    """财务计算执行失败（Story 5.12 — FR-ST-09 估值计算面）

    触发场景：
    - DCF 数值求解失败双路径（V1 实际触发面：①IRR bracket 端点同号等病态输入
      ②NPV 为零使 terminal_value_weight 分母失效[盈亏平衡精确抵消输入——CR1-1 补]）
    - comparable/precedent 统计面 V1 零失败路径（空集合已由 VO 层 242 拦截）

    fail-loud 审计语义：数值不可解或根歧义时显式报错而非静默返回 None 或任取
    一根（Excel #NUM! 是该语义的类比参照——非逐字行为对齐）。

    Attributes:
        code: EXCEPTION_470
        message: 默认消息（静态文案，不含动态内部细节——零迭代区间端点泄露）
        context: 领域上下文（method——估值方法诊断标注；detail——失败描述）
    """

    code = "EXCEPTION_470"
    message = "财务计算执行失败"

    def __init__(
        self,
        method: str,
        detail: str = "",
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """初始化财务计算失败异常

        Args:
            method: 估值方法诊断标注（闭集语义 {"dcf", "comparable", "precedent"}——
                docstring 语义非闭集校验，自由字符串容错：诊断标注面与 SAPBusStateError
                reason 协议契约错误面的差异钦定）
            detail: 失败描述（面向调用方的计算语义——零内部实现细节）
            message: 自定义消息（缺省回落类属性静态文案）
            cause: 底层异常
            context_extra: 扩展上下文键（合并不覆盖既有双键）
        """
        context: dict[str, str] = {
            "method": method,
            "detail": detail,
        }
        if context_extra:
            context.update(context_extra)
        super().__init__(message=message, cause=cause, context=context)
