"""AgentEvaluationError（EXCEPTION_450）单元测试——Story 5.8 评估子域新开。

覆盖面：构造与 context 三键暴露 / code 与 message / to_dict 序列化 / HTTP 映射 500
（EXCEPTION_HTTP_MAP 显式注册）/ 子域注册（CODE_RANGES evaluation 段 450-459 +
_CLASS_TO_SUBDOMAIN 映射）/ SystemException 继承面。

Run with:
    poetry run pytest tests/unit/domain/exceptions/test_evaluation_exceptions.py -v
"""

from __future__ import annotations

from src.domain.exceptions import AgentEvaluationError, SystemException, ValidationError
from src.domain.exceptions._code_ranges import _CLASS_TO_SUBDOMAIN, CODE_RANGES


class TestAgentEvaluationErrorConstruction:
    """构造与 context 暴露（对齐 AgentWorkflowError 三键形态）。"""

    def test_default_message_and_code(self) -> None:
        """默认消息非空 + code 精确 450。"""
        from src.domain.exceptions import AgentEvaluationError as Cls

        error = Cls()
        assert error.code == "EXCEPTION_450"
        assert error.message, "默认消息应为非空静态文案"

    def test_context_carries_three_keys(self) -> None:
        """context 三键（agent_id/phase/reason）——agent_id 默认空串（evaluate 输入无 agent_id）。"""
        error = AgentEvaluationError(agent_id="agent-001", reason="llm_call")
        assert error.context["agent_id"] == "agent-001"
        assert error.context["phase"] == "evaluation"
        assert error.context["reason"] == "llm_call"

    def test_phase_defaults_to_evaluation(self) -> None:
        """phase 默认 evaluation（评估管线唯一环节标识）。"""
        error = AgentEvaluationError(reason="schema_validation")
        assert error.context["phase"] == "evaluation"

    def test_context_extra_diagnostic_keys(self) -> None:
        """context_extra 诊断键合并（匹配失败场景 selected_model/available_models）。"""
        error = AgentEvaluationError(
            reason="model_resolution",
            context_extra={"selected_model": "model-b", "available_models": "model-a"},
        )
        assert error.context["selected_model"] == "model-b"
        assert error.context["available_models"] == "model-a"
        assert error.context["reason"] == "model_resolution"

    def test_custom_message_override(self) -> None:
        """自定义 message 覆盖默认。"""
        error = AgentEvaluationError(message="评估路由失败（自定义）")
        assert error.message == "评估路由失败（自定义）"

    def test_cause_chain_preserved(self) -> None:
        """cause 异常链保留（LLM 族包装 from error 语义）。"""
        original = ValidationError(message="内层校验失败")
        error = AgentEvaluationError(reason="llm_call", cause=original)
        assert error.cause is original

    def test_inherits_system_exception(self) -> None:
        """继承面：SystemException（评估是系统侧可观测行为）+ DomainError。"""
        from src.domain.exceptions.base_exceptions import DomainError

        error = AgentEvaluationError()
        assert isinstance(error, SystemException)
        assert isinstance(error, DomainError)

    def test_to_dict_serialization(self) -> None:
        """to_dict 序列化（code/message/context 三段）。"""
        error = AgentEvaluationError(agent_id="agent-002", reason="model_resolution")
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_450"
        assert data["context"]["phase"] == "evaluation"
        assert data["context"]["reason"] == "model_resolution"


class TestAgentEvaluationErrorHttpMapping:
    """HTTP 映射（EXCEPTION_HTTP_MAP 显式注册——惯例性消歧）。"""

    def test_maps_to_500_via_function(self) -> None:
        """_get_http_status 正向断言。"""
        from src.interfaces.api.exception_handlers import _get_http_status

        error = AgentEvaluationError()
        assert _get_http_status(error) == 500

    def test_registered_in_exception_http_map(self) -> None:
        """表直查反向断言（防 isinstance 回退歧义）。"""
        from fastapi import status

        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP[AgentEvaluationError] == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestAgentEvaluationErrorSubdomainRegistration:
    """子域注册（evaluation 段 450-459 新开——四代开段先例）。"""

    def test_class_to_subdomain_mapping(self) -> None:
        """_CLASS_TO_SUBDOMAIN 映射到 evaluation。"""
        assert _CLASS_TO_SUBDOMAIN["AgentEvaluationError"] == "evaluation"

    def test_code_ranges_evaluation_segment(self) -> None:
        """CODE_RANGES evaluation 段 = (450, 459)。"""
        assert CODE_RANGES["evaluation"] == (450, 459)

    def test_code_within_segment(self) -> None:
        """码值 450 落段断言。"""
        low, high = CODE_RANGES["evaluation"]
        numeric = int(AgentEvaluationError.code.removeprefix("EXCEPTION_"))
        assert low <= numeric <= high

    def test_segment_not_overlapping_agent(self) -> None:
        """与 agent 段（440-449 已满）不重叠。"""
        agent_low, agent_high = CODE_RANGES["agent"]
        eval_low, eval_high = CODE_RANGES["evaluation"]
        assert eval_low > agent_high
