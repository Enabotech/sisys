"""EvaluationHarness 单元测试（Story 5.8——三 TDD 循环）。

循环 A：Schema 扁平性 + prompt 模块形态 + 幻觉检测 LLM 结构化调用（prompt 三要素/
Schema 身份/config 派生纪律）+ isinstance 守卫 450 + LLM 族异常包装矩阵（450 包装
与 332/Cancelled 透传分述）。
循环 B：compute_context_relevance 四态参数化 + compute_confidence_accuracy 数值矩阵
+ overall 加权手算对照（同式表达式——R3-F1 钉死禁十进制字面量）。
循环 C：evaluate 端到端编排（四字段全断言 + 只读不改写）。

Fake LLM：AsyncMock(spec=LLMClientPort) + response_schema 身份分派（5-3 先例）；
resolver 替身：固定基底 LLMConfig（temperature=0.7/timeout=600.0 默认——与评估常量
0.1/8.0 相异是 config 派生断言的判别力前提，实现漏 replace 必红）。

Run with:
    poetry run pytest tests/unit/application/services/test_evaluation_harness.py -v
"""

from __future__ import annotations

import asyncio as asyncio_module
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.application.ports.agent_workflow import AgentWorkflowResult
from src.domain.exceptions import (
    AgentEvaluationError,
    LLMAPIError,
    LLMConfigError,
    LLMResponseError,
    ServiceUnavailableError,
)
from src.domain.value_objects.chain_of_thought import ChainOfThought
from src.domain.value_objects.task_evidence import TaskEvidencePackage

_INPUT_SUMMARY = "任务理解：分析新能源汽车行业进入战略并给出三层次建议"
_FINAL_ANSWER = '{"answer": "三层次进入策略：聚焦细分市场"}'
#: 测试假密钥占位（resolver 替身基底的连接字段——非真实凭据，断言经 base_config 引用比对）
_BASE_EVAL_FAKE_KEY = "base-eval-" + "key"


class _StaticModelResolverStub:
    """固定基底配置解析替身（连接字段非默认值——连接继承断言有判别力）。"""

    def __init__(self) -> None:
        from src.domain.ports.llm_client import LLMConfig

        self.base_config = LLMConfig(
            model="base-eval-model",
            endpoint="https://base-eval.example/v1",
            api_key=_BASE_EVAL_FAKE_KEY,
        )
        self.resolve_calls: list[str] = []

    async def resolve_config(self, input_text: str) -> Any:
        self.resolve_calls.append(input_text)
        return self.base_config


def _make_input(
    *,
    tool_trace: tuple[str, ...] = (),
    artifacts_snapshot: tuple[tuple[str, str], ...] = (),
    citations: tuple[str, ...] = (),
    confidence: float = 0.85,
) -> AgentWorkflowResult:
    """评估输入真实 VO 构造（242 校验通过的真实材料）。"""
    chain = ChainOfThought(
        input_summary=_INPUT_SUMMARY,
        reflection="复盘：论证链条完整",
        tools_used=tool_trace,
        constraints_check="约束核对通过",
        final_answer=_FINAL_ANSWER,
    )
    evidence = TaskEvidencePackage(
        input_hash="a" * 64,  # 64 位 hex 假值（VO 校验形态——5-3 存量先例 L97）
        task_breakdown=("市场分析", "进入策略制定"),
        tool_trace=tool_trace,
        artifacts_snapshot=artifacts_snapshot,
        confidence=confidence,
        confidence_rationale="结构化检查通过",
        citations=citations,
        status="completed",
        failure_reason="",
    )
    return AgentWorkflowResult(
        chain=chain,
        evidence=evidence,
        workflow_status="completed",
        retry_count=0,
        executed_phases=("perceive", "plan", "verify", "package"),
    )


def _make_fake_llm(hallucination_score: float = 0.2) -> AsyncMock:
    """幻觉检测 Fake LLM（Schema 身份分派——未预期 Schema 抛 AssertionError）."""
    from src.application.services.evaluation_schemas import HallucinationEvaluationSchema
    from src.domain.ports.llm_client import LLMClientPort

    async def _structured_generate(
        prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None
    ) -> Any:
        if response_schema is HallucinationEvaluationSchema:
            return HallucinationEvaluationSchema(
                rationale="回答与证据材料一致，无幻觉内容",
                hallucination_score=hallucination_score,
            )
        raise AssertionError(f"未预期 response_schema: {response_schema!r}")

    fake = AsyncMock(spec=LLMClientPort)
    fake.structured_generate.side_effect = _structured_generate
    return fake


def _make_harness(fake_llm: Any = None, resolver: Any = None) -> Any:
    """装配被测 harness（Fake LLM + 固定基底 resolver 替身）."""
    from src.application.services.evaluation_harness import EvaluationHarness

    return EvaluationHarness(
        llm_client=fake_llm if fake_llm is not None else _make_fake_llm(),
        model_resolver=resolver if resolver is not None else _StaticModelResolverStub(),
    )


# =====================================================================
# 循环 A：Schema + prompt + 幻觉检测调用
# =====================================================================


class TestHallucinationSchema:
    """HallucinationEvaluationSchema 形态（扁平零嵌套 + 域约束 + 身份互斥）。"""

    def test_schema_fields_and_constraints(self) -> None:
        """两字段：rationale（min/max_length）先行 + hallucination_score（ge/le）。"""
        from src.application.services.evaluation_schemas import HallucinationEvaluationSchema

        schema = HallucinationEvaluationSchema(rationale="判断理由", hallucination_score=0.2)
        assert schema.rationale == "判断理由"
        assert schema.hallucination_score == 0.2
        # 字段声明序 rationale 在前（CoT-then-score——DC-2 细则(b)）
        field_order = list(HallucinationEvaluationSchema.model_fields.keys())
        assert field_order == ["rationale", "hallucination_score"]

    def test_schema_flat_no_nested_models(self) -> None:
        """扁平零嵌套（anthropic 通道约束——嵌套 Schema 服务端栈溢出）."""
        from src.application.services.evaluation_schemas import HallucinationEvaluationSchema

        for field_info in HallucinationEvaluationSchema.model_fields.values():
            assert "BaseModel" not in str(field_info.annotation), f"字段 {field_info} 应为标量（零嵌套）"

    def test_schema_domain_constraint_violation(self) -> None:
        """ge/le 域约束（越界 pydantic 校验失败）。"""
        from pydantic import ValidationError as PydanticValidationError

        from src.application.services.evaluation_schemas import HallucinationEvaluationSchema

        with pytest.raises(PydanticValidationError):
            HallucinationEvaluationSchema(rationale="判断理由", hallucination_score=1.5)
        with pytest.raises(PydanticValidationError):
            HallucinationEvaluationSchema(rationale="", hallucination_score=0.5)  # min_length=1

    def test_schema_identity_distinct_from_existing_five(self) -> None:
        """与既有五 Schema 类对象两两不同（身份分派前提——agent_workflow_schemas L9-10）."""
        from src.application.services.agent_workflow_schemas import (
            ChainOfThoughtSchema,
            PerceptionSchema,
            PlanSchema,
            ReflectionSchema,
            VerificationSchema,
        )
        from src.application.services.evaluation_schemas import HallucinationEvaluationSchema

        for existing in (
            PerceptionSchema,
            PlanSchema,
            VerificationSchema,
            ReflectionSchema,
            ChainOfThoughtSchema,
        ):
            assert HallucinationEvaluationSchema is not existing


class TestEvaluationPrompts:
    """prompt 模块形态（SYSTEM_PROMPT 六档量表 + USER_TEMPLATE 三要素占位）."""

    def test_prompt_constants_exist(self) -> None:
        """SYSTEM_PROMPT/USER_TEMPLATE 模块级常量实名（relevance_prompts 先例）。"""
        from src.application.services import evaluation_prompts

        assert hasattr(evaluation_prompts, "SYSTEM_PROMPT")
        assert hasattr(evaluation_prompts, "USER_PROMPT_TEMPLATE")
        assert "0.0" in evaluation_prompts.SYSTEM_PROMPT and "1.0" in evaluation_prompts.SYSTEM_PROMPT, (
            "SYSTEM_PROMPT 应附六档量表锚定（DC-2 细则(c)——裸 float 评分会塌缩）"
        )

    def test_user_template_three_element_placeholders(self) -> None:
        """USER_TEMPLATE 三要素占位（input_summary/证据摘要/final_answer）。"""
        from src.application.services.evaluation_prompts import USER_PROMPT_TEMPLATE

        for placeholder in ("{input_summary}", "{evidence_summary}", "{final_answer}"):
            assert placeholder in USER_PROMPT_TEMPLATE, f"USER_PROMPT_TEMPLATE 缺占位 {placeholder}"


class TestHallucinationDetection:
    """幻觉检测 LLM 结构化调用（config 派生纪律 + prompt 三要素 + 异常矩阵）."""

    async def test_structured_generate_call_assertions(self) -> None:
        """调用矩阵：prompt 三要素 + Schema 身份 kwarg + config 派生 + 连接继承."""
        from src.application.services.evaluation_harness import (
            EVALUATION_TEMPERATURE,
            EVALUATION_TIMEOUT_SEC,
        )
        from src.application.services.evaluation_schemas import HallucinationEvaluationSchema

        fake_llm = _make_fake_llm(hallucination_score=0.2)
        resolver = _StaticModelResolverStub()
        harness = _make_harness(fake_llm=fake_llm, resolver=resolver)
        result = await harness.evaluate(_make_input())

        # 幻觉分与 Fake 注入值相等
        assert result.hallucination_score == 0.2
        calls = [
            c
            for c in fake_llm.structured_generate.call_args_list
            if c.kwargs.get("response_schema") is HallucinationEvaluationSchema
        ]
        assert len(calls) == 1, f"应恰一次幻觉检测调用，实际 {len(calls)}"
        call = calls[0]
        prompt = call.kwargs["prompt"]
        assert _INPUT_SUMMARY in prompt, "prompt 应含 chain.input_summary"
        assert "证据" in prompt, "prompt 应含证据摘要段"
        assert _FINAL_ANSWER in prompt, "prompt 应含 chain.final_answer"
        assert call.kwargs["response_schema"] is HallucinationEvaluationSchema
        assert call.kwargs.get("system_prompt"), "应传 SYSTEM_PROMPT"
        config = call.kwargs.get("config")
        assert config is not None, "应传派生 config"
        assert config.temperature == EVALUATION_TEMPERATURE == 0.1
        assert config.timeout == EVALUATION_TIMEOUT_SEC == 8.0
        # 连接字段随路由产物继承（基底 0.7/600.0 与评估常量相异——判别力前提）
        assert config.model == "base-eval-model"
        assert config.endpoint == "https://base-eval.example/v1"
        assert config.api_key == resolver.base_config.api_key

    async def test_resolver_input_is_final_answer(self) -> None:
        """resolver 入参 = chain.final_answer（UDMRTask.input——合规检测输入面）."""
        resolver = _StaticModelResolverStub()
        harness = _make_harness(resolver=resolver)
        await harness.evaluate(_make_input())
        assert resolver.resolve_calls == [_FINAL_ANSWER]

    async def test_non_schema_result_raises_450(self) -> None:
        """Fake 返回非 Schema 实例 → isinstance 守卫 → 450（reason=schema_validation）."""
        from src.domain.ports.llm_client import LLMClientPort

        async def _bad_schema(prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None) -> Any:
            return {"hallucination_score": 0.1, "rationale": "非 Schema 实例"}

        bad_llm = AsyncMock(spec=LLMClientPort)
        bad_llm.structured_generate.side_effect = _bad_schema
        harness = _make_harness(fake_llm=bad_llm)
        with pytest.raises(AgentEvaluationError) as exc_info:
            await harness.evaluate(_make_input())
        caught = exc_info.value
        assert caught.code == "EXCEPTION_450"
        assert caught.context["phase"] == "evaluation"
        assert caught.context["reason"] == "schema_validation"

    @pytest.mark.parametrize(
        "injected",
        [
            LLMAPIError(message="模拟 330"),
            LLMResponseError(message="模拟 331"),
            TimeoutError("模拟超时"),
            ServiceUnavailableError(message="模拟 503"),
        ],
        ids=["llm_api_error_330", "llm_response_error_331", "timeout", "service_unavailable"],
    )
    async def test_llm_family_wrapped_to_450(self, injected: Exception) -> None:
        """LLM 族四异常 → 450 包装 from error（reason=llm_call）."""
        from src.domain.ports.llm_client import LLMClientPort

        async def _raise_error(prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None) -> Any:
            raise injected

        fake = AsyncMock(spec=LLMClientPort)
        fake.structured_generate.side_effect = _raise_error
        harness = _make_harness(fake_llm=fake)
        with pytest.raises(AgentEvaluationError) as exc_info:
            await harness.evaluate(_make_input())
        caught = exc_info.value
        assert caught.code == "EXCEPTION_450", f"{type(injected).__name__} 应包装 450"
        assert caught.context["reason"] == "llm_call"
        assert isinstance(caught.__cause__, type(injected)), "包装应 from error 保留异常链"

    async def test_llm_config_error_passthrough(self) -> None:
        """LLMConfigError（332）透传不包装（开发期配置错误显性失败）。"""
        from src.domain.ports.llm_client import LLMClientPort

        async def _raise_config_error(
            prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None
        ) -> Any:
            raise LLMConfigError(message="模拟 332")

        fake = AsyncMock(spec=LLMClientPort)
        fake.structured_generate.side_effect = _raise_config_error
        harness = _make_harness(fake_llm=fake)
        with pytest.raises(LLMConfigError):
            await harness.evaluate(_make_input())

    async def test_cancelled_error_passthrough(self) -> None:
        """asyncio.CancelledError 透传（协程取消语义保护）。"""
        from src.domain.ports.llm_client import LLMClientPort

        async def _raise_cancelled(
            prompt: str, response_schema: type, config: Any = None, system_prompt: str | None = None
        ) -> Any:
            raise asyncio_module.CancelledError()

        fake = AsyncMock(spec=LLMClientPort)
        fake.structured_generate.side_effect = _raise_cancelled
        harness = _make_harness(fake_llm=fake)
        with pytest.raises(asyncio_module.CancelledError):
            await harness.evaluate(_make_input())


# =====================================================================
# 循环 B：证据支撑度四态 + 校准公式矩阵 + overall 加权
# =====================================================================


class TestComputeContextRelevance:
    """compute_context_relevance 四态参数化（OD-3 三元加权精确值）。"""

    @pytest.mark.parametrize(
        ("tool_trace", "artifacts", "citations", "expected"),
        [
            ((), (), (), 0.0),
            (("pestel_analysis:1.0",), (), (), 0.3),
            ((), (("report", "内容"),), (), 0.3),
            ((), (), ("行业白皮书-2026",), 0.4),
            (("pestel_analysis:1.0",), (), ("行业白皮书-2026",), 0.7),
            (("pestel_analysis:1.0",), (("report", "内容"),), ("行业白皮书-2026",), 1.0),
        ],
        ids=["all_empty", "tool_trace_only", "artifacts_only", "citations_only", "citations_and_tools", "all_full"],
    )
    def test_four_states_exact_values(
        self,
        tool_trace: tuple[str, ...],
        artifacts: tuple[tuple[str, str], ...],
        citations: tuple[str, ...],
        expected: float,
    ) -> None:
        """四态精确值断言（全空 0.0 / 单元 0.3-0.4 / 组合 / 全满 1.0）。"""
        from src.application.services.evaluation_harness import EvaluationHarness

        evidence = _make_input(tool_trace=tool_trace, artifacts_snapshot=artifacts, citations=citations).evidence
        assert EvaluationHarness.compute_context_relevance(evidence) == expected


class TestComputeConfidenceAccuracy:
    """compute_confidence_accuracy 数值矩阵（§17.3.8 L1681 钦定公式）。"""

    @pytest.mark.parametrize(
        ("predicted", "actual", "expected"),
        [
            (0.5, 0.5, 1.0),
            (1.0, 0.7, 0.7),
            (0.6, 0.3, 0.7),
            (0.5, 0.2, 0.7),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.85, 0.4, 0.55),
        ],
        ids=["zero_diff", "diff_0.3_a", "diff_0.3_b", "diff_0.3_c", "full_diff", "full_diff_rev", "chain_triple"],
    )
    def test_numeric_matrix(self, predicted: float, actual: float, expected: float) -> None:
        """数值矩阵（钦定公式 1.0 - min(|pred-actual|, 1.0)——安全值对浮点精确）。"""
        from src.application.services.evaluation_harness import EvaluationHarness

        assert EvaluationHarness.compute_confidence_accuracy(predicted, actual) == expected


class TestOverallWeighting:
    """overall 加权与 actual 口径（OD-4/OD-5）。"""

    def test_actual_quality_formula(self) -> None:
        """actual 口径断言：(1-h)×0.5 + cr×0.5（OD-4 均权——反循环规避）。"""
        from src.application.services.evaluation_harness import EvaluationHarness

        assert EvaluationHarness._compute_actual_quality(0.2, 0.0) == 0.4
        assert EvaluationHarness._compute_actual_quality(0.2, 1.0) == 0.9
        assert EvaluationHarness._compute_actual_quality(0.0, 0.0) == 0.5

    def test_overall_formula_manual_check(self) -> None:
        """overall 同式表达式对照（禁十进制字面量——组合链实算值非精确字面）。"""
        from src.application.ports.agent_evaluation import (
            CONFIDENCE_ACCURACY_WEIGHT,
            CONTEXT_RELEVANCE_WEIGHT,
            HALLUCINATION_WEIGHT,
        )
        from src.application.services.evaluation_harness import EvaluationHarness

        h, cr, ca = 0.2, 0.4, 0.75
        expected = (1.0 - h) * HALLUCINATION_WEIGHT + cr * CONTEXT_RELEVANCE_WEIGHT + ca * CONFIDENCE_ACCURACY_WEIGHT
        assert EvaluationHarness._compute_overall(h, cr, ca) == expected
        # R3-F1 锚：该组合实算 0.6475000000000001（写字面量 0.6475 必假红）
        assert expected != 0.6475

    def test_overall_direction_monotonic(self) -> None:
        """overall 方向性：幻觉分升高 → overall 降低（反转加权——5.9 CUSUM 方向前提）。"""
        from src.application.services.evaluation_harness import EvaluationHarness

        low_hallucination = EvaluationHarness._compute_overall(0.1, 0.5, 0.5)
        high_hallucination = EvaluationHarness._compute_overall(0.9, 0.5, 0.5)
        assert low_hallucination > high_hallucination


# =====================================================================
# 循环 C：evaluate 端到端编排
# =====================================================================


class TestEvaluateOrchestration:
    """evaluate 端到端（四字段全断言 + 只读不改写）。"""

    async def test_evaluate_end_to_end_all_fields(self) -> None:
        """端到端四字段：h=Fake 注入 0.2 / cr=启发式手算 / ca=校准手算 / overall=加权手算。"""
        from src.application.ports.agent_evaluation import (
            CONFIDENCE_ACCURACY_WEIGHT,
            CONTEXT_RELEVANCE_WEIGHT,
            HALLUCINATION_WEIGHT,
        )

        harness = _make_harness(fake_llm=_make_fake_llm(hallucination_score=0.2))
        result = await harness.evaluate(
            _make_input(
                citations=("行业白皮书-2026",),
                tool_trace=("pestel_analysis:1.0",),
                artifacts_snapshot=(("report", "政策支持"),),
                confidence=0.85,
            )
        )
        h, cr, pred = 0.2, 1.0, 0.85
        actual_quality = (1.0 - h) * 0.5 + cr * 0.5
        expected_ca = 1.0 - min(abs(pred - actual_quality), 1.0)
        expected_overall = (
            (1.0 - h) * HALLUCINATION_WEIGHT + cr * CONTEXT_RELEVANCE_WEIGHT + expected_ca * CONFIDENCE_ACCURACY_WEIGHT
        )
        assert result.hallucination_score == h
        assert result.context_relevance == cr
        assert result.confidence_accuracy == expected_ca
        assert result.overall_score == expected_overall

    async def test_evaluate_zero_evidence_chain_triple(self) -> None:
        """零证据链钦定三元组（R3 钦定：h=0.2/cr=0.0/pred=0.85 → ca=0.55 全二进制精确）。"""
        harness = _make_harness(fake_llm=_make_fake_llm(hallucination_score=0.2))
        result = await harness.evaluate(_make_input())
        assert result.hallucination_score == 0.2
        assert result.context_relevance == 0.0
        assert result.confidence_accuracy == 0.55

    async def test_evaluate_read_only_not_mutate_input(self) -> None:
        """只读不改写（输入 result 字段不变——frozen 天然 + evidence.confidence 原值）。"""
        original_input = _make_input(confidence=0.85)
        harness = _make_harness()
        await harness.evaluate(original_input)
        assert original_input.evidence.confidence == 0.85
        assert original_input.chain.final_answer == _FINAL_ANSWER
        assert original_input.workflow_status == "completed"

    async def test_evaluate_returns_evaluation_result_instance(self) -> None:
        """返回类型断言（EvaluationResult frozen dataclass）。"""
        from src.application.ports.agent_evaluation import EvaluationResult

        harness = _make_harness()
        result = await harness.evaluate(_make_input())
        assert isinstance(result, EvaluationResult)
