"""评估子域异常（evaluation，450-459）——Story 5.8 Agent 输出质量评估。

子域范围：Agent 输出质量评估管线（EvaluationHarness：幻觉检测 LLM 调用 +
证据支撑度计算 + 置信度校准 + overall 加权；评估模型 UDMR in-band 路由解析）。
评估是 Agent 可观测族的可观测附加面——评估失败经 use case 降级 catch（warning
跳过不阻断工作流主链），450 与评估路径透传的 LLMConfigError（332——现实可达
源是运行期 env 半配置态，CR1-F1）是降级网捕获面；主链六阶段的 332 显性失败
语义不受影响。

编码段：450-459（evaluation 子域新开——agent 段 440-449 已满后的四代开段先例：
data_source 410/debate 420/tool_version 430/agent 440 后第五段）。
"""

from __future__ import annotations

from src.domain.exceptions.system_exceptions import SystemException

__all__ = ["AgentEvaluationError"]


class AgentEvaluationError(SystemException):
    """Agent 输出质量评估管线执行失败（Story 5.8 — FR-EV-02 评估面）

    触发场景：
        - 幻觉检测 LLM 调用失败包装（LLMAPIError/LLMResponseError/TimeoutError/
          ServiceUnavailableError 收敛 450——``_structured_call`` 传播纪律先例）；
        - 幻觉检测返回结果不是 HallucinationEvaluationSchema 实例（isinstance 守卫）；
        - 评估模型路由产物匹配失败（selected_model 不在 cloud_configs——配置漂移，
          禁静默回退）；
        - local 分支 LLMConfig.from_env() 配置解析失败的防御性包装（模型解析失败
          归降级网——运行期 env 损坏不得击穿主链）。

    LLM 族异常传播策略（``_structured_call`` L468-473 纪律照抄）：LLMConfigError
    （332——透传使 use case 评估块降级网可区分「配置错（可行动）」与「瞬态失败
    （450 族）」，现实可达源是运行期 env 半配置态非开发期代码错误[CR1-F1]）与
    asyncio.CancelledError（协程取消语义保护）透传不包装；其余 LLM 族异常包装
    450 携 cause 链。

    Attributes:
        code: EXCEPTION_450
        message: 默认消息（静态文案，不含动态内部细节）
        context: 领域上下文（agent_id/phase/reason——reason 取值 llm_call/
            schema_validation/model_resolution 标识失败环节；agent_id 在 evaluate
            包装路径不可得时为空串，仅供构造面/未来调用方扩展）
    """

    code = "EXCEPTION_450"
    message = "Agent 输出质量评估执行失败"

    def __init__(
        self,
        agent_id: str = "",
        phase: str = "evaluation",
        reason: str = "",
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """初始化评估管线执行异常

        Args:
            agent_id: 评估归属的 Agent 标识（字符串形态——evaluate 输入
                AgentWorkflowResult 不含 agent_id，包装路径默认空串）。
            phase: 失败环节名（评估管线恒为 "evaluation"——对齐
                AgentWorkflowError 的 phase 锚点形态）。
            reason: 面向调用方可理解的失败环节摘要（llm_call/schema_validation/
                model_resolution 之一）。
            message: 覆盖默认消息（可选）。
            cause: 原始异常（可选，用于异常链）。
            context_extra: 额外诊断键（如匹配失败场景的 selected_model/
                available_models——合并进 context，值域 str）。
        """
        context: dict[str, str] = {
            "agent_id": agent_id,
            "phase": phase,
            "reason": reason,
        }
        if context_extra:
            context.update(context_extra)
        super().__init__(message=message, cause=cause, context=context)
