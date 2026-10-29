"""评估子域异常（evaluation，450-459）——Story 5.8 Agent 输出质量评估 + Story 5.9 漂移检测 + Story 5.10 评估历史持久化。

子域范围：Agent 输出质量评估管线（EvaluationHarness：幻觉检测 LLM 调用 +
证据支撑度计算 + 置信度校准 + overall 加权；评估模型 UDMR in-band 路由解析）+
CUSUM 漂移检测管线（CUSUMDriftDetector：双侧累积和 + N中M 确认 + DriftDetected
事件发布）+ 评估历史持久化管线（EvaluationCheckpointRecorder：累积→打包→
save 委托→restore 恢复式解包）。评估/漂移检测/历史持久化均为 Agent 可观测族的
可观测附加面——评估与漂移失败经 use case 评估块共享降级 catch（warning 跳过
不阻断工作流主链），历史持久化失败经 record 块专属内层 catch 独立降级（452
不进共享 catch 元组——两附加面互不牵连）；450/451/452 与评估路径透传的
LLMConfigError（332——现实可达源是运行期 env 半配置态，CR1-F1）分属三层
降级网与内层独立降级网捕获面；主链六阶段的 332 显性失败语义不受影响。

编码段：450-459（evaluation 子域新开——agent 段 440-449 已满后的四代开段先例：
data_source 410/debate 420/tool_version 430/agent 440 后第五段；451 是预留段
首个取用——_code_ranges 段注释钦定「5.9 漂移检测/5.10 评估历史如需新码在此段取」；
452 是 452-459 预留段首个取用——5.10 评估历史）。
"""

from __future__ import annotations

from src.domain.exceptions.system_exceptions import SystemException

__all__ = ["AgentEvaluationError", "DriftDetectionError", "EvaluationHistoryError"]


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


class DriftDetectionError(SystemException):
    """CUSUM 漂移检测管线执行失败（Story 5.9 — FR-EV-03 漂移检测面）

    触发场景：
        - 检测管线状态异常防御面（update 双侧累积/确认窗状态机不可达态——
          理论不可达的防御层，主链可用性优先于漂移检测完整性。R1 代码审查
          注记：当前实现 update 状态机 total、全仓零 raise 点——本码属契约
          预留防御码，降级网/HTTP 映射先行接线，测试经 FakeDriftPort 注入
          行使；V1 Redis 持久化实现的状态检查失败通道即刻可用）；
        - degenerate 基线外的管线级异常路径（σ₀ 退化是数据形态降级非管线
          错误——恒走 detection=False 可观测降级，不抛本异常）。

    三层降级网第三层（CR1-F1[5.8] 论证形态延续）：评估失败 450 / 评估配置
    失败 332 / 漂移检测失败 451——use case 评估块 catch 元组
    ``(AgentEvaluationError, LLMConfigError, DriftDetectionError)`` 单一 catch 点
    warning 跳过不阻断主链（可观测附加面哲学：漂移检测完整性损失不阻断已
    完成的工作流结果）。

    Attributes:
        code: EXCEPTION_451（evaluation 子域预留段首个取用）
        message: 默认消息（静态文案——仅 phase/reason 语义面，不泄露内部
            统计量全序列）
        context: 领域上下文（metric_name/phase/reason——reason 取值
            invalid_state/degenerate_baseline 标识失败环节）
    """

    code = "EXCEPTION_451"
    message = "CUSUM 漂移检测执行失败"

    def __init__(
        self,
        metric_name: str = "overall_score",
        phase: str = "drift_detection",
        reason: str = "",
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """初始化漂移检测管线执行异常

        Args:
            metric_name: 漂移检测的指标名（检测器绑定常量同值——overall_score）。
            phase: 失败环节名（漂移检测管线恒为 "drift_detection"——与 450 的
                "evaluation" 区分，降级网诊断锚）。
            reason: 面向调用方可理解的失败环节摘要（invalid_state/
                degenerate_baseline——与 Attributes 行同闭集）。
            message: 覆盖默认消息（可选）。
            cause: 原始异常（可选，用于异常链）。
            context_extra: 额外诊断键（合并进 context，值域 str）。
        """
        context: dict[str, str] = {
            "metric_name": metric_name,
            "phase": phase,
            "reason": reason,
        }
        if context_extra:
            context.update(context_extra)
        super().__init__(message=message, cause=cause, context=context)


class EvaluationHistoryError(SystemException):
    """评估历史持久化管线执行失败（Story 5.10 — FR-EV-04 持久化面）

    触发场景：
        - record 时存储 save 失败（SnapshotRepositoryProtocol.save 抛
          StorageError 的链路透传包装——Redis 故障在存储面即 103，Recorder
          捕获后包装本码携 cause 链上抛）；
        - record 时输入域违规（EvaluationCheckpoint 构造守卫的 ValidationError
          收敛——主链三重上游守卫下不可达的防御层，451 同款哲学；直调消费方
          触发即达——端口「唯一异常」契约成立锚）；
        - restore 时快照结构不完整（state_data 缺 evaluation_history/
          hallucination_trend/confidence_accuracy_trend/agent_id 任一键、
          类型不符、分数值域违规、trend 元素非法或三序列等长破坏——
          反序列化 fail-loud 防御面，正常路径快照由本管线产出必含四键）。

    独立降级网语义（区别于 450/451 的共享 catch 面）：use case 评估块内
    record 块专属内层 ``except EvaluationHistoryError`` 捕获（三键 span 写入
    后、漂移块之前）——record 失败不得阻断漂移检测、漂移失败不得丢评估历史，
    两独立可观测附加面互不牵连；共享 catch 三元组（450/332/451）零改动。

    Attributes:
        code: EXCEPTION_452（452-459 预留段首个取用）
        message: 默认消息（静态文案——str(本异常) 恒等于 message，cause 动态
            文案只进 to_dict 不进 str，主链 warning 文本断言锚）
        context: 领域上下文（agent_id/phase/reason——reason 取值 save_failed/
            invalid_structure/invalid_input 标识失败环节[save_failed=存储失败、
            invalid_structure=restore 快照结构异常族收敛、invalid_input=record
            输入域违规收敛]；phase 取值 record/restore）
    """

    code = "EXCEPTION_452"
    message = "评估历史持久化失败"

    def __init__(
        self,
        agent_id: str = "",
        phase: str = "record",
        reason: str = "",
        message: str | None = None,
        cause: Exception | None = None,
        context_extra: dict[str, str] | None = None,
    ) -> None:
        """初始化评估历史持久化管线异常

        Args:
            agent_id: 评估历史归属的 Agent 标识（record 主链路径恒可得——
                execute 形参透传；restore 路径不可得时空串——450「不可得时
                空串」同款形态，诊断以 context.session_id 为准）。
            phase: 失败环节名（record/restore——record 是累积+打包+save
                原子主路径）。
            reason: 面向调用方可理解的失败环节摘要（save_failed/
                invalid_structure/invalid_input 之一——结构异常族含缺键/
                类型错/分数值域违规/trend 元素非法/等长破坏，收敛单值不
                再细分[防御路径消费面仅日志，cause 链已携精确原异常]）。
            message: 覆盖默认消息（可选）。
            cause: 原始异常（可选，用于异常链——StorageError 包装链锚）。
            context_extra: 额外诊断键（如 session_id/记录数——合并进
                context，值域 str）。
        """
        context: dict[str, str] = {
            "agent_id": agent_id,
            "phase": phase,
            "reason": reason,
        }
        if context_extra:
            context.update(context_extra)
        super().__init__(message=message, cause=cause, context=context)
