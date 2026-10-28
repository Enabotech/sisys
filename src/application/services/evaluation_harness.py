"""EvaluationHarness——Agent 输出质量评估编排核心（Story 5.8 — FR-EV-02）。

评估管线五步流程（evaluate 编排）：
1. 幻觉检测——经 EvaluationModelResolverPort（UDMR in-band 动态路由）派生
   per-call config，structured_generate 调用 LLM 结构化评分（OD-5：0.0=无
   幻觉 1.0=完全幻觉——越高越坏）；
2. 证据支撑度——compute_context_relevance 纯同步三元加权（OD-3：度量证据
   完备度[存在性]非语义相关性——消费方不得当语义质量用）；
3. 校准——compute_confidence_accuracy（§17.3.8 L1681 钦定公式；actual 口径
   OD-4：代理一致性[proxy agreement]非真值校准）；
4. overall——三键方向归一反转加权（OD-5：越高越好，5.9 CUSUM 消费方向）；
5. EvaluationResult 构造（四分数 [0,1] 守卫 201）。

调用纪律（``_structured_call`` L430-487 照抄）：LLMConfigError（332）与
asyncio.CancelledError 透传不包装；LLMAPIError/LLMResponseError/TimeoutError/
ServiceUnavailableError 包装 AgentEvaluationError（450）from error；isinstance
守卫在 try 块之外（守卫 raise 不被异常分支二次捕获——relevance 服务双层包装
缺陷规避）。不引入兜底 except Exception（比 _structured_call 宽的 relevance
先例不抄——评估失败面应全部显性映射）。
"""

from __future__ import annotations

import asyncio
import dataclasses

from src.application.ports.agent_evaluation import (
    ACTUAL_FACTUAL_WEIGHT,
    CONFIDENCE_ACCURACY_WEIGHT,
    CONTEXT_ARTIFACT_WEIGHT,
    CONTEXT_CITATION_WEIGHT,
    CONTEXT_RELEVANCE_WEIGHT,
    CONTEXT_TOOL_TRACE_WEIGHT,
    HALLUCINATION_WEIGHT,
    EvaluationModelResolverPort,
    EvaluationResult,
)
from src.application.ports.agent_workflow import AgentWorkflowResult
from src.application.services.evaluation_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from src.application.services.evaluation_schemas import HallucinationEvaluationSchema
from src.domain.exceptions import (
    AgentEvaluationError,
    LLMAPIError,
    LLMConfigError,
    LLMResponseError,
    ServiceUnavailableError,
)
from src.domain.ports.llm_client import LLMClientPort
from src.domain.value_objects.task_evidence import TaskEvidencePackage

__all__ = ["EVALUATION_TEMPERATURE", "EVALUATION_TIMEOUT_SEC", "EvaluationHarness"]

#: 评估温度（低温——verify 档 0.1 先例：评估判定任务需要确定性；TEMPERATURE_PROFILE 形态）
EVALUATION_TEMPERATURE: float = 0.1

#: per-call timeout（秒）——显式传递禁依赖 from_env 默认 600s（_DEFAULT_PER_CALL_TIMEOUT_SEC 先例）
EVALUATION_TIMEOUT_SEC: float = 8.0

#: 证据摘要工件简编上限（每工件摘录字符数——prompt 组装量级控制）
_EVIDENCE_ARTIFACT_EXCERPT_CHARS = 120


class EvaluationHarness:
    """Agent 输出质量评估编排（AgentEvaluationPort 实现）。

    编排双端口注入（DC-1）：``llm_client``（domain 基础端口 R1——幻觉检测调用面）+
    ``model_resolver``（application 端口 R2——评估模型 per-call 动态路由）。
    无状态纯函数式 evaluate（无 eval_history 累积——5.9/5.10 范围）——SINGLETON 安全。

    Attributes:
        _llm_client: LLM 客户端端口（structured_generate 结构化评分调用）。
        _model_resolver: 评估模型解析端口（UDMR in-band 路由 → per-call LLMConfig）。
    """

    def __init__(
        self,
        llm_client: LLMClientPort,
        model_resolver: EvaluationModelResolverPort,
    ) -> None:
        """初始化评估编排服务。

        Args:
            llm_client: LLM 客户端端口实例。
            model_resolver: 评估模型解析端口实例（EvaluationModelResolverPort）。
        """
        self._llm_client = llm_client
        self._model_resolver = model_resolver

    async def evaluate(self, result: AgentWorkflowResult) -> EvaluationResult:
        """评估 Agent 工作流输出质量（评估管线五步编排——只读不改写）。

        Args:
            result: 工作流结果（chain 五字段 + evidence 九字段）。

        Returns:
            EvaluationResult: 四分数评估结果。

        Raises:
            AgentEvaluationError: 450——幻觉检测 LLM 调用失败包装 / Schema 实例
                校验失败。
            LLMConfigError: 332 与 asyncio.CancelledError 透传不包装。
        """
        hallucination_score = await self._detect_hallucination(result)
        context_relevance = self.compute_context_relevance(result.evidence)
        confidence_accuracy = self.compute_confidence_accuracy(
            predicted=result.evidence.confidence,
            actual=self._compute_actual_quality(hallucination_score, context_relevance),
        )
        overall_score = self._compute_overall(hallucination_score, context_relevance, confidence_accuracy)
        return EvaluationResult(
            hallucination_score=hallucination_score,
            context_relevance=context_relevance,
            confidence_accuracy=confidence_accuracy,
            overall_score=overall_score,
        )

    async def _detect_hallucination(self, result: AgentWorkflowResult) -> float:
        """幻觉检测 LLM 结构化调用（UDMR 路由派生 config + 三要素 prompt）。

        config 派生纪律（``_build_call_config`` L414-428 同款）：dataclasses.replace
        只覆写温度/超时——连接字段（api_type/model/endpoint/api_key/max_tokens）
        随路由产物继承（防裸 LLMConfig() 丢连接字段）。

        Args:
            result: 工作流结果（chain.input_summary 任务理解 + chain.final_answer
                被评估回答与路由输入 + evidence 证据四材料）。

        Returns:
            float: 幻觉分 [0,1]（Schema ge/le 域约束保证）。

        Raises:
            AgentEvaluationError: 450——LLM 族失败包装（reason=llm_call）或返回
                非 Schema 实例（reason=schema_validation）。
            LLMConfigError: 332 与 CancelledError 透传。
        """
        base_config = await self._model_resolver.resolve_config(result.chain.final_answer)
        config = dataclasses.replace(
            base_config,
            temperature=EVALUATION_TEMPERATURE,
            timeout=EVALUATION_TIMEOUT_SEC,
        )
        prompt = USER_PROMPT_TEMPLATE.format(
            input_summary=result.chain.input_summary,
            evidence_summary=self._summarize_evidence(result.evidence),
            final_answer=result.chain.final_answer,
        )
        try:
            schema_result = await self._llm_client.structured_generate(
                prompt=prompt,
                response_schema=HallucinationEvaluationSchema,
                config=config,
                system_prompt=SYSTEM_PROMPT,
            )
        except LLMConfigError:
            # 配置错误透传不包装（开发期错误应显性失败——_structured_call L468-473 纪律）
            raise
        except asyncio.CancelledError:
            # 协程取消透传（父任务取消语义保护）
            raise
        except (LLMAPIError, LLMResponseError, TimeoutError, ServiceUnavailableError) as error:
            raise AgentEvaluationError(
                reason="llm_call",
                message=f"幻觉检测 LLM 调用失败: {error}",
                cause=error,
            ) from error
        # isinstance 守卫在 try 之外（守卫 raise 不被异常分支二次捕获）
        if not isinstance(schema_result, HallucinationEvaluationSchema):
            raise AgentEvaluationError(
                reason="schema_validation",
                message=(f"LLM 返回结果不是 HallucinationEvaluationSchema 实例（实际 {type(schema_result).__name__}）"),
            )
        return schema_result.hallucination_score

    @staticmethod
    def _summarize_evidence(evidence: TaskEvidencePackage) -> str:
        """证据摘要四材料组装（DC-2 细则(a)：纳入工件简编使 judge 对伪造引用保有判别力）。

        Args:
            evidence: 任务证据包（citations/artifacts_snapshot/tool_trace/
                confidence_rationale 四材料 + confidence）。

        Returns:
            str: prompt 证据摘要段文本。
        """
        citations = "；".join(evidence.citations) if evidence.citations else "（无引用源）"
        tool_trace = "；".join(evidence.tool_trace) if evidence.tool_trace else "（无工具轨迹）"
        if evidence.artifacts_snapshot:
            artifact_lines = [
                f"{name}: {excerpt[:_EVIDENCE_ARTIFACT_EXCERPT_CHARS]}" for name, excerpt in evidence.artifacts_snapshot
            ]
            artifacts = "；".join(artifact_lines)
        else:
            artifacts = "（无工件快照）"
        return (
            f"引用源：{citations}\n"
            f"工具轨迹：{tool_trace}\n"
            f"工件快照（简编）：{artifacts}\n"
            f"自报置信度：{evidence.confidence}（理由：{evidence.confidence_rationale}）"
        )

    @staticmethod
    def compute_context_relevance(evidence: TaskEvidencePackage) -> float:
        """证据支撑度计算（OD-3——三元存在性加权，纯同步零外部调用）。

        语义诚实注记：本启发式度量「证据完备度（存在性）」非语义相关性——
        纯结构性信号可被填充行为刷分（垃圾引用串亦得分），消费方（5.9/仪表盘）
        不得当语义质量用；其真实价值 = 证据流程完备度监控（Agent 突然不再产出
        citations 本身即有价值的退化信号）。权重 0.4/0.3/0.3 非标定值
        （citations 外部可核验引用源权重最高），V1 有人类评估数据可重标定。

        Args:
            evidence: 任务证据包（取 citations/artifacts_snapshot/tool_trace 三元组）。

        Returns:
            float: 证据支撑度 [0,1]（全空 0.0 / 全满 1.0）。
        """
        score = 0.0
        if evidence.citations:
            score += CONTEXT_CITATION_WEIGHT
        if evidence.artifacts_snapshot:
            score += CONTEXT_ARTIFACT_WEIGHT
        if evidence.tool_trace:
            score += CONTEXT_TOOL_TRACE_WEIGHT
        return score

    @staticmethod
    def compute_confidence_accuracy(predicted: float, actual: float) -> float:
        """置信度校准准确度计算（§17.3.8 L1681 钦定公式）。

        公式：``1.0 - min(|predicted - actual|, 1.0)``（误差越小校准越准）。

        语义诚实注记（OD-4）：actual 是代理质量（(1-h)×0.5+cr×0.5——幻觉事实性
        与证据支撑均权），本指标度量「自报置信度与代理质量的代理一致性
        （proxy agreement）」非真值校准（业界 calibration 的 actual = ground
        truth + ECE/Brier 度量——无人类标签可用，V1 真校准通道见 deferred-work）。

        Args:
            predicted: Agent 自报置信度（evidence.confidence，[0,1]）。
            actual: 代理质量分（_compute_actual_quality 产物，[0,1]）。

        Returns:
            float: 校准准确度 [0,1]（diff=0 → 1.0；|diff|>=1.0 → 0.0）。
        """
        error = abs(predicted - actual)
        return 1.0 - min(error, 1.0)

    @staticmethod
    def _compute_actual_quality(hallucination_score: float, context_relevance: float) -> float:
        """代理质量口径（OD-4——幻觉事实性与证据支撑均权，最小假设形态）。

        反循环论证注记：actual 不取 overall（overall 含 confidence_accuracy 而
        confidence_accuracy 依赖 actual——定义性循环）；(1-h)+cr 组合规避之。
        注意权重向量与 overall 权重统计高度相关——本规避是定义性反循环而非
        统计独立性（consumers 须知 actual 与 overall 近仿射相关）。

        Args:
            hallucination_score: 幻觉分（反转后为事实性）。
            context_relevance: 证据支撑度。

        Returns:
            float: 代理质量 [0,1]。
        """
        return (1.0 - hallucination_score) * ACTUAL_FACTUAL_WEIGHT + context_relevance * (1.0 - ACTUAL_FACTUAL_WEIGHT)

    @staticmethod
    def _compute_overall(hallucination_score: float, context_relevance: float, confidence_accuracy: float) -> float:
        """overall 质量总分（OD-5 反转加权——三键方向归一后求和，越高越好）。

        公式：``(1-h)×0.4 + cr×0.35 + ca×0.25``——反转 (1-h) 使三键方向一致
        （hallucination_score 字面语义越高越坏，质量分须单调正向——5.9 CUSUM
        消费方向一致性前提）。权重为手工产品先验（grounding 类维度合计 0.75
        ——overall 高度由证据面驱动），V1 有数据可重标定。

        Args:
            hallucination_score: 幻觉分 [0,1]。
            context_relevance: 证据支撑度 [0,1]。
            confidence_accuracy: 校准准确度 [0,1]。

        Returns:
            float: overall [0,1]。
        """
        return (
            (1.0 - hallucination_score) * HALLUCINATION_WEIGHT
            + context_relevance * CONTEXT_RELEVANCE_WEIGHT
            + confidence_accuracy * CONFIDENCE_ACCURACY_WEIGHT
        )
