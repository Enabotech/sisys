"""Agent 输出质量评估端口族（Story 5.8 — FR-EV-02 评估面）。

评估族端口聚合文件：``AgentEvaluationPort``（评估编排契约）+
``EvaluationModelResolverPort``（评估模型解析契约）+ ``EvaluationResult`` DTO +
``EVALUATION_WEIGHTS`` 权重常量——与 ``agent_tracing`` 同族命名（Agent 评估
可观测族 5.7-5.9 的应用契约层）。

端口命名甄别：本文件 ``AgentEvaluationPort`` 评估「Agent 回答 vs 证据包输出质量」，
区别于检索域 ``RelevanceEvaluationPort``（domain/ports/relevance_evaluation.py——
评估「查询 vs SearchResult 检索质量」）。两端口语义分立，检索域端口的
TypedDict ``context_relevance`` 字段与本 Story ``EvaluationResult`` 同名属巧合撞名。

设计决策（R1/R2/R3 规则落地）：
- LLMClientPort（domain 基础端口）被 EvaluationHarness 组合注入（R2）；
- UDMR 路由 + cloud_configs 匹配是技术实现面——EvaluationModelResolverPort 由
  infrastructure 实现（UdmrEvaluationModelResolver），支持扩展静态配置解析/
  多路由源等同类技术实现（R3）；
- 本文件纯标准库零第三方（Protocol + dataclass + 常量——agent_tracing.py 同款
  形态；LLMConfig 从 domain/ports import、AgentWorkflowResult 从同层 import）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from src.application.ports.agent_workflow import AgentWorkflowResult
from src.domain.exceptions import ValidationError
from src.domain.ports.llm_client import LLMConfig

__all__ = [
    "ACTUAL_FACTUAL_WEIGHT",
    "CONFIDENCE_ACCURACY_WEIGHT",
    "CONTEXT_ARTIFACT_WEIGHT",
    "CONTEXT_CITATION_WEIGHT",
    "CONTEXT_RELEVANCE_WEIGHT",
    "CONTEXT_TOOL_TRACE_WEIGHT",
    "EVALUATION_WEIGHTS",
    "AgentEvaluationPort",
    "EvaluationModelResolverPort",
    "EvaluationResult",
    "HALLUCINATION_WEIGHT",
]

# =====================================================================
# 权重常量（评估契约单源——防漂移，测试以两组和为 1.0 元断言钉死）
# =====================================================================

#: overall 三维权重（OD-5 反转加权——三键方向归一后求和；幻觉检测是质量核心
#: > 证据支撑 > 校准，SYS AGENT 五维评分先例形态[architecture.md §17.4 L2952]；
#: 手工产品先验非标注数据标定结果，V1 有人类评估数据可重标定；grounding 类
#: 维度[(1-h)+cr] 合计权重 0.75——overall 高度由证据面驱动，消费方须知）
HALLUCINATION_WEIGHT: float = 0.4
CONTEXT_RELEVANCE_WEIGHT: float = 0.35
CONFIDENCE_ACCURACY_WEIGHT: float = 0.25

#: actual_quality 均权（OD-4 口径——幻觉事实性与证据支撑的均权「实际质量」，
#: 均权是最小假设形态（无先验偏置））
ACTUAL_FACTUAL_WEIGHT: float = 0.5

#: 证据支撑度三元权重（OD-3——citations 是外部可核验引用源[权重最高]、
#: artifacts_snapshot/tool_trace 多为过程性证据；非标定值，V1 可重标定）
CONTEXT_CITATION_WEIGHT: float = 0.4
CONTEXT_ARTIFACT_WEIGHT: float = 0.3
CONTEXT_TOOL_TRACE_WEIGHT: float = 0.3

#: 权重常量聚合（单源引用面——整体导入或逐键消费均可）
EVALUATION_WEIGHTS: dict[str, float] = {
    "HALLUCINATION_WEIGHT": HALLUCINATION_WEIGHT,
    "CONTEXT_RELEVANCE_WEIGHT": CONTEXT_RELEVANCE_WEIGHT,
    "CONFIDENCE_ACCURACY_WEIGHT": CONFIDENCE_ACCURACY_WEIGHT,
    "ACTUAL_FACTUAL_WEIGHT": ACTUAL_FACTUAL_WEIGHT,
    "CONTEXT_CITATION_WEIGHT": CONTEXT_CITATION_WEIGHT,
    "CONTEXT_ARTIFACT_WEIGHT": CONTEXT_ARTIFACT_WEIGHT,
    "CONTEXT_TOOL_TRACE_WEIGHT": CONTEXT_TOOL_TRACE_WEIGHT,
}


# =====================================================================
# 评估结果 DTO
# =====================================================================


@dataclass(frozen=True)
class EvaluationResult:
    """Agent 输出质量评估结果（四分数——应用层 DTO，评估是可观测应用面非领域概念）。

    四分数语义对照表（方向注记：hallucination_score 越高越坏，其余三键越高越好）：

    - ``hallucination_score``：字面幻觉程度——0.0 = 无幻觉（完全事实）、
      1.0 = 完全幻觉（OD-5 字面语义锚；Phoenix 生态惯例——hallucination 评估器
      输出幻觉概率，越高越坏）。
    - ``context_relevance``：证据支撑度——OD-3 启发式（citations/artifacts_snapshot/
      tool_trace 三元存在性加权）。**语义诚实注记：度量「证据完备度（存在性）」
      非语义相关性——纯结构性信号可被填充行为刷分（Goodhart 风险知悉），消费方
      （5.9/仪表盘）不得当语义质量用；其真实价值 = 证据流程完备度监控**
      （Agent 突然不再产出 citations 本身即有价值的退化信号）。
    - ``confidence_accuracy``：置信度校准准确度——OD-4 口径。**语义诚实注记：
      度量「自报置信度与代理质量的代理一致性（proxy agreement）」非真值校准**
      （无人类标签可用——业界 calibration 的 actual = ground truth + ECE/Brier
      度量；本指标是无标注 MVP 的代理构造）。
    - ``overall_score``：质量总分——OD-5 反转加权
      ``(1-h)×0.4 + cr×0.35 + ca×0.25``（三键方向归一，越高越好；5.9 CUSUM
      消费本键做漂移累积——方向一致性前提）。

    与 AgentWorkflowResult 同层同风格（application/ports/agent_workflow.py 先例）；
    分数域守卫自设加严（[0,1] 闭区间——应用层输入校验，越界抛 ValidationError 201）。
    """

    hallucination_score: float
    context_relevance: float
    confidence_accuracy: float
    overall_score: float

    def __post_init__(self) -> None:
        """四字段分数域守卫（[0,1] 闭区间 + bool 拒 + 数值类型校验）。

        Raises:
            ValidationError: EXCEPTION_201——任一字段越界 / 类型非数值 / bool
                （context 携 ``{字段名: 实际值}``——242 惯例形态）。
        """
        for field in ("hallucination_score", "context_relevance", "confidence_accuracy", "overall_score"):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValidationError(
                    message=f"评估分数 {field} 必须为数值（实际 {type(value).__name__}）",
                    context={field: str(value)},
                )
            if not 0.0 <= value <= 1.0:
                raise ValidationError(
                    message=f"评估分数 {field} 越界 [0,1]（实际 {value}）",
                    context={field: str(value)},
                )


# =====================================================================
# 端口定义
# =====================================================================


@runtime_checkable
class AgentEvaluationPort(Protocol):
    """Agent 输出质量评估端口（R2 具体应用端口——Agent 评估可观测族应用契约）。

    评估编排：幻觉检测 LLM 调用 + 证据支撑度计算 + 置信度校准 + overall 加权。
    实现方：``EvaluationHarness``（application/services——llm_client +
    evaluation_model_resolver 双端口组合注入）。

    端口命名甄别：区别于检索域 ``RelevanceEvaluationPort``
    （domain/ports/relevance_evaluation.py——评估「查询 vs SearchResult 检索
    质量」），本端口评估「Agent 回答 vs 证据包输出质量」——两端口语义分立。
    """

    async def evaluate(self, result: AgentWorkflowResult) -> EvaluationResult:
        """评估 Agent 工作流输出质量。

        Args:
            result: 工作流结果（AgentWorkflowResult 五字段——evaluate 只读不改写）。

        Returns:
            EvaluationResult: 四分数评估结果。

        Raises:
            AgentEvaluationError: EXCEPTION_450——幻觉检测 LLM 调用失败包装
                （LLMAPIError/LLMResponseError/TimeoutError/ServiceUnavailableError）/
                Schema 实例校验失败 / 路由产物匹配失败。
            LLMConfigError: EXCEPTION_332 与 asyncio.CancelledError 透传不包装
                （``_structured_call`` L468-473 同款纪律——配置错误是开发期错误
                应显性失败非运行期降级面）。
            ValidationError: EXCEPTION_201——EvaluationResult 分数域守卫
                （理论不可达[输入域已约束]防御层）。
        """
        ...


@runtime_checkable
class EvaluationModelResolverPort(Protocol):
    """评估模型解析端口（R2 具体应用端口——评估调用模型解析契约）。

    UDMR in-band 动态路由：UDMRTask → decide() → selected_model → per-call
    LLMConfig——区别于既有 bootstrap 定格的 SSOT 静态接线
    （build_default_llm_config——执行模型取第一个 enabled）。

    R3 落点：UDMR 路由 + cloud_configs 匹配是技术实现面——infrastructure 实现
    （UdmrEvaluationModelResolver）可替换（静态配置解析/多路由源），支持扩展
    其他同类技术实现。
    """

    async def resolve_config(self, input_text: str) -> LLMConfig:
        """解析评估调用的 LLM 配置。

        Args:
            input_text: 被评估文本（UDMRTask.input——合规检测与 token 估算输入）。

        Returns:
            LLMConfig: cloud 匹配条目或 local 形态的 per-call 配置。

        Raises:
            AgentEvaluationError: EXCEPTION_450——路由产物匹配失败（配置漂移，
                禁静默回退）；local 分支 LLMConfig.from_env() 的 ConfigurationError
                101 亦防御性包装 450（模型解析失败归降级网——R1 审查修订；现
                from_env 实现无校验且非法值静默回退默认[llm_client.py L46-96]
                实际不抛 101，本包装是防御性契约——未来 from_env 加校验即活，
                测试经 monkeypatch 注入触发）。UDMRService 内部异常上抛面由其
                自身契约决定（decide() 的合规降级是 forced_local 非异常）。
        """
        ...
