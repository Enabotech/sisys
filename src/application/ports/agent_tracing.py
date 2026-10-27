"""应用层 Agent 追踪端口模块（Story 5.7 — FR-EV-01 追踪面）

Agent 评估可观测族（5.7 追踪 / 5.8 评估 / 5.9 漂移检测）的应用契约：R2 具体
应用端口（同层先例 metrics_port/cache_metrics_port——追踪非领域概念，domain
零依赖原则下不设 domain 端口）。实现 PhoenixTracer 在 infrastructure 层
（OTel SDK——OD-1 零新运行时依赖）。

SpanHandle 方法签名逐名且逐参对齐 OTel Span 原生签名（duck-type 零包装层，
OTel Span 天然满足）；set_status 不入协议——OTel 原生签名是
Status|StatusCode 联合类型，bool 业务签名直透会落 isinstance 双分支皆不中的
静默 no-op（R1-③ 实测），status 置位由 OTel use_span __exit__ 框架兜底
（Exception 路径自动 set ERROR——R1-F4 后 @trace 无显式调用，避免双
exception 事件；BaseException 路径按 OTel #4484 设计有意不置位）。
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol, runtime_checkable

#: span 属性值合法类型（OTel set_attribute 契约——str/bool/int/float/str 序列）
SpanAttributeValue = str | bool | int | float | tuple[str, ...]


@runtime_checkable
class SpanHandle(Protocol):
    """span 句柄协议（duck-type OTel Span 原生对象——零包装层）

    契约锁定必须行为断言（runtime_checkable isinstance 只查方法名存在——
    假绿风险）：set_attribute/record_exception 经 exporter 可观测。
    """

    def set_attribute(self, key: str, value: SpanAttributeValue) -> None:
        """写入 span 属性。

        Args:
            key: 属性键（SpanAttributeKeys 常量——键字符串单一真源）
            value: 属性值（str/bool/int/float/str 元组；None 非法——OTel 契约）
        """
        ...

    def record_exception(self, exception: BaseException) -> None:
        """记录异常事件（span events 追加 exception 事件——5.9/异常路径消费面）。

        Args:
            exception: 被捕获的异常实例
        """
        ...


@runtime_checkable
class AgentTracingPort(Protocol):
    """Agent 追踪端口（应用层——5.8 EvaluationHarness/5.9 CUSUM 的注入式消费契约）

    create_span 的 tracer 解析规则（R2-1 双源解析——钉死）：
    trace.get_tracer("sisys.agent", tracer_provider=self._provider)——注入
    provider 优先（构造注入通道下无需 initialize 即产真 span）；未注入时走
    全局 API（initialize 已 set 后解析为真 tracer，否则 proxy → NoOp）。

    Raises 契约（R1-F1 修订——装配段与消费方段分述）：
    装配段（tracer 解析）零抛出——异常降级 logger.warning + yield None
    （DC-7 可观测性附加哲学：可观测组件故障不得影响主链）；消费方段
    （with 体内）异常**原样穿透**——业务异常不是追踪抛出面，实现不得捕获、
    不得改写（OTel use_span __exit__ 兜底记录后透传）。
    """

    def create_span(
        self,
        name: str,
        attributes: dict[str, SpanAttributeValue] | None = None,
    ) -> AbstractContextManager[SpanHandle | None]:
        """span 生命周期上下文（进入开 span + attributes 批量写入；退出 end）。

        Args:
            name: span 名称（SpanNames 常量）
            attributes: 进入时批量写入的属性（可选）

        Returns:
            上下文管理器——有可用 tracer 来源（已注入 provider 或已 initialize）
            时 yield SpanHandle（OTel Span 原生对象 duck-type）；无可用来源
            （未注入且未 initialize）或装配段异常时 yield None（零开销降级
            ——显式消费方判 None；降级判据是「无 tracer 来源」而非「未
            initialize」）；消费方在 with 体内抛出的异常原样穿透（R1-F1——
            实现不得捕获/改写消费方异常）
        """
        ...

    def initialize(self) -> bool:
        """配置全局 TracerProvider（幂等——实例闩：同实例再入静默返回 True；
        外来 set 检测：全局已非 proxy 态且非本实例所 set 时 logger.warning）。

        Returns:
            是否实际启用（enabled=false 返回 False 不装配不设全局）
        """
        ...

    def shutdown(self) -> None:
        """刷盘并释放（BatchSpanProcessor force_flush + provider shutdown）。"""
        ...


class SpanAttributeKeys:
    """span 属性键常量注册表（键字符串单一真源——5.8/5.9 引用防拼写漂移）

    MVP 十项（值取自 run 链现成数据——agent 实体/AgentProfileLoadResult/
    AgentWorkflowResult 及其 .evidence）+ eval/drift 四键（三键逐字源 epics
    L1726-1728，第四键源 §17.3.8 L1700 §2.5 指标名 confidence_accuracy 的
    span 键形增设——5.8 消费）。eval.* 值生产归 5.8、drift.* 归 5.9（OD-2——
    本 Story 交付键常量与写入通道，不做生产预置）。
    """

    AGENT_ID: str = "agent.id"
    AGENT_NAME: str = "agent.name"
    AGENT_ROLE: str = "agent.role"
    AGENT_STARTUP_CONTEXT_TOKENS: str = "agent.startup_context_tokens"
    AGENT_ACTIVE_SKILL_COUNT: str = "agent.active_skill_count"
    WORKFLOW_STATUS: str = "workflow.status"
    WORKFLOW_RETRY_COUNT: str = "workflow.retry_count"
    WORKFLOW_EXECUTED_PHASES: str = "workflow.executed_phases"
    EVAL_CONFIDENCE: str = "eval.confidence"
    EVIDENCE_INPUT_HASH: str = "evidence.input_hash"
    EVAL_HALLUCINATION_SCORE: str = "eval.hallucination_score"
    EVAL_CONTEXT_RELEVANCE: str = "eval.context_relevance"
    EVAL_CONFIDENCE_ACCURACY: str = "eval.confidence_accuracy"
    DRIFT_DETECTED: str = "drift.detected"


class SpanNames:
    """span 名称常量（agent_execution 根 span[epics 钦定] + agent.{phase} 六阶段前缀）。

    span 名末段对齐 executed_phases 枚举（末阶段 "package" 非 package_evidence
    ——5-3 图节点名与谓词键映射，一致性由 AC-2 元断言锁定）。
    """

    AGENT_EXECUTION: str = "agent_execution"
    PHASE_PREFIX: str = "agent."


__all__ = [
    "AgentTracingPort",
    "SpanAttributeKeys",
    "SpanAttributeValue",
    "SpanHandle",
    "SpanNames",
]
