"""AgentEvaluationError（EXCEPTION_450）+ DriftDetectionError（EXCEPTION_451）单元测试。

覆盖面：构造与 context 三键暴露 / code 与 message / to_dict 序列化 / HTTP 映射 500
（EXCEPTION_HTTP_MAP 显式注册）/ 子域注册（CODE_RANGES evaluation 段 450-459 +
_CLASS_TO_SUBDOMAIN 映射）/ SystemException 继承面；451（Story 5.9 漂移检测——
evaluation 子域预留段首个取用）同族追加。

Run with:
    poetry run pytest tests/unit/domain/exceptions/test_evaluation_exceptions.py -v
"""

from __future__ import annotations

from src.domain.exceptions import AgentEvaluationError, DriftDetectionError, SystemException, ValidationError
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


class TestDriftDetectionErrorConstruction:
    """DriftDetectionError（EXCEPTION_451——Story 5.9 漂移检测）构造与 context 暴露。"""

    def test_default_message_and_code(self) -> None:
        """默认消息非空 + code 精确 451。"""
        error = DriftDetectionError()
        assert error.code == "EXCEPTION_451"
        assert error.message, "默认消息应为非空静态文案"

    def test_context_carries_three_keys(self) -> None:
        """context 三键（metric_name/phase/reason）——漂移检测的定位维度。"""
        error = DriftDetectionError(metric_name="overall_score", reason="invalid_state")
        assert error.context["metric_name"] == "overall_score"
        assert error.context["phase"] == "drift_detection"
        assert error.context["reason"] == "invalid_state"

    def test_metric_name_defaults_to_overall_score(self) -> None:
        """metric_name 默认 overall_score（检测器绑定常量同值）。"""
        error = DriftDetectionError()
        assert error.context["metric_name"] == "overall_score"

    def test_phase_defaults_to_drift_detection(self) -> None:
        """phase 默认 drift_detection（区别于 450 的 evaluation——降级网诊断区分锚）。"""
        error = DriftDetectionError(reason="invalid_state")
        assert error.context["phase"] == "drift_detection"

    def test_custom_message_override(self) -> None:
        """自定义 message 覆盖默认。"""
        error = DriftDetectionError(message="漂移检测状态异常（自定义）")
        assert error.message == "漂移检测状态异常（自定义）"

    def test_cause_chain_preserved(self) -> None:
        """cause 异常链保留。"""
        original = ValidationError(message="内层校验失败")
        error = DriftDetectionError(reason="degenerate_baseline", cause=original)
        assert error.cause is original

    def test_inherits_system_exception(self) -> None:
        """继承面：SystemException（漂移检测是系统侧可观测行为——450 同族论证延续）。"""
        from src.domain.exceptions.base_exceptions import DomainError

        error = DriftDetectionError()
        assert isinstance(error, SystemException)
        assert isinstance(error, DomainError)

    def test_to_dict_serialization(self) -> None:
        """to_dict 序列化（code/message/context 三段）。"""
        error = DriftDetectionError(metric_name="overall_score", reason="invalid_state")
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_451"
        assert data["context"]["phase"] == "drift_detection"
        assert data["context"]["reason"] == "invalid_state"


class TestDriftDetectionErrorHttpMapping:
    """HTTP 映射（EXCEPTION_HTTP_MAP 显式注册——惯例性消歧，SystemException 族 500）。"""

    def test_maps_to_500_via_function(self) -> None:
        """_get_http_status 正向断言。"""
        from src.interfaces.api.exception_handlers import _get_http_status

        error = DriftDetectionError()
        assert _get_http_status(error) == 500

    def test_registered_in_exception_http_map(self) -> None:
        """表直查反向断言（防 isinstance 回退歧义——451 精确注册惯例）。"""
        from fastapi import status

        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP[DriftDetectionError] == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestDriftDetectionErrorSubdomainRegistration:
    """子域注册（evaluation 段内取用 451——预留段钦定 L137-138 注释兑现）。"""

    def test_class_to_subdomain_mapping(self) -> None:
        """_CLASS_TO_SUBDOMAIN 映射到 evaluation。"""
        assert _CLASS_TO_SUBDOMAIN["DriftDetectionError"] == "evaluation"

    def test_code_within_segment(self) -> None:
        """码值 451 落 evaluation 段（450-459）。"""
        low, high = CODE_RANGES["evaluation"]
        numeric = int(DriftDetectionError.code.removeprefix("EXCEPTION_"))
        assert low <= numeric <= high

    def test_code_distinct_from_450(self) -> None:
        """451 与 450 语义分立（评估失败 vs 检测失败——三层降级网诊断区分）。"""
        assert DriftDetectionError.code != AgentEvaluationError.code


class TestEvaluationHistoryErrorConstruction:
    """EvaluationHistoryError（EXCEPTION_452——Story 5.10 评估历史持久化）构造与 context 暴露。"""

    def test_default_message_and_code(self) -> None:
        """默认消息非空 + code 精确 452 + message 静态文案钦定（AC-2 warning 断言锚）。"""
        from src.domain.exceptions import EvaluationHistoryError

        error = EvaluationHistoryError()
        assert error.code == "EXCEPTION_452"
        assert error.message == "评估历史持久化失败"

    def test_context_carries_three_keys(self) -> None:
        """context 三键（agent_id/phase/reason）——AgentEvaluationError 构造签名同款。"""
        from src.domain.exceptions import EvaluationHistoryError

        error = EvaluationHistoryError(agent_id="agent-001", reason="save_failed")
        assert error.context["agent_id"] == "agent-001"
        assert error.context["phase"] == "record"
        assert error.context["reason"] == "save_failed"

    def test_phase_covers_record_and_restore(self) -> None:
        """phase 支持 record/restore 两主路径取值（serialize/deserialize 防御面同参数面）。"""
        from src.domain.exceptions import EvaluationHistoryError

        record_error = EvaluationHistoryError(phase="record", reason="save_failed")
        restore_error = EvaluationHistoryError(phase="restore", reason="missing_keys")
        assert record_error.context["phase"] == "record"
        assert restore_error.context["phase"] == "restore"

    def test_context_extra_diagnostic_keys(self) -> None:
        """context_extra 诊断键合并（session_id/记录数——452 触发场景携带）。"""
        from src.domain.exceptions import EvaluationHistoryError

        error = EvaluationHistoryError(
            reason="save_failed",
            context_extra={"session_id": "agent-evaluation-agent-001", "history_len": "3"},
        )
        assert error.context["session_id"] == "agent-evaluation-agent-001"
        assert error.context["history_len"] == "3"
        assert error.context["reason"] == "save_failed"

    def test_custom_message_override(self) -> None:
        """自定义 message 覆盖默认。"""
        from src.domain.exceptions import EvaluationHistoryError

        error = EvaluationHistoryError(message="评估历史恢复失败（自定义）")
        assert error.message == "评估历史恢复失败（自定义）"

    def test_cause_chain_preserved(self) -> None:
        """cause 异常链保留（StorageError 包装 from error 语义——Recorder 包装链锚）。"""
        from src.domain.exceptions import EvaluationHistoryError, StorageError

        original = StorageError(message="Failed to save snapshot: 连接失败")
        error = EvaluationHistoryError(reason="save_failed", cause=original)
        assert error.cause is original

    def test_str_equals_static_message_with_cause(self) -> None:
        """str(领域异常) 恒等于 message（cause 链只进 to_dict 不进 str——AC-2 warning 文本断言锚的机制保证）。"""
        from src.domain.exceptions import EvaluationHistoryError, StorageError

        original = StorageError(message="Failed to save snapshot: 连接失败")
        error = EvaluationHistoryError(reason="save_failed", cause=original)
        assert str(error) == "评估历史持久化失败"
        assert "Failed to save snapshot" not in str(error)

    def test_inherits_system_exception(self) -> None:
        """继承面：SystemException（评估历史持久化是系统侧可观测行为——450/451 同族论证延续）。"""
        from src.domain.exceptions import EvaluationHistoryError, SystemException
        from src.domain.exceptions.base_exceptions import DomainError

        error = EvaluationHistoryError()
        assert isinstance(error, SystemException)
        assert isinstance(error, DomainError)

    def test_to_dict_serialization(self) -> None:
        """to_dict 序列化（code/message/context 三段）。"""
        from src.domain.exceptions import EvaluationHistoryError

        error = EvaluationHistoryError(agent_id="agent-003", phase="restore", reason="missing_keys")
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_452"
        assert data["context"]["agent_id"] == "agent-003"
        assert data["context"]["phase"] == "restore"
        assert data["context"]["reason"] == "missing_keys"


class TestEvaluationHistoryErrorHttpMapping:
    """HTTP 映射（EXCEPTION_HTTP_MAP 显式注册——452 休眠映射：主链内层 catch 降级无 HTTP 浮现路径，注册是完备性要求）。"""

    def test_maps_to_500_via_function(self) -> None:
        """_get_http_status 正向断言。"""
        from src.domain.exceptions import EvaluationHistoryError
        from src.interfaces.api.exception_handlers import _get_http_status

        error = EvaluationHistoryError()
        assert _get_http_status(error) == 500

    def test_registered_in_exception_http_map(self) -> None:
        """表直查反向断言（防 isinstance 回退歧义——450/451 精确注册惯例延续）。"""
        from fastapi import status

        from src.domain.exceptions import EvaluationHistoryError
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP[EvaluationHistoryError] == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestEvaluationHistoryErrorSubdomainRegistration:
    """子域注册（evaluation 段内取用 452——452-459 预留段首个取用）。"""

    def test_class_to_subdomain_mapping(self) -> None:
        """_CLASS_TO_SUBDOMAIN 映射到 evaluation。"""
        from src.domain.exceptions import EvaluationHistoryError

        assert _CLASS_TO_SUBDOMAIN[EvaluationHistoryError.__name__] == "evaluation"

    def test_code_within_segment(self) -> None:
        """码值 452 落 evaluation 段（450-459）。"""
        from src.domain.exceptions import EvaluationHistoryError

        low, high = CODE_RANGES["evaluation"]
        numeric = int(EvaluationHistoryError.code.removeprefix("EXCEPTION_"))
        assert low <= numeric <= high

    def test_code_distinct_from_450_451(self) -> None:
        """452 与 450/451 语义分立（评估失败/检测失败/历史持久化失败——三层降级网诊断区分）。"""
        from src.domain.exceptions import EvaluationHistoryError

        assert EvaluationHistoryError.code not in {AgentEvaluationError.code, DriftDetectionError.code}
