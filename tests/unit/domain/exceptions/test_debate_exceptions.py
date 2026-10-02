"""Story 4.5 — 辩论领域异常单元测试

验证 DebateGenerationError(420) / DebateSynthesisError(421) / DebateLowDivergenceError(422)
的构造器契约、context 组装、to_dict 序列化（含 cause 链解析）与 HTTP 映射反向验证。

约束：
- 420/421 继承 ExternalException、422 继承 BusinessException（无共同基类，relevance 平铺先例）
- HTTP 映射经 _get_http_status 私有纯函数反向验证（500/500/422，精确注册避免 isinstance 回退）
- topic_title/red_summary/blue_summary 截断至 100 字符（异常 context 惯例）
"""

from __future__ import annotations

import uuid

import pytest

from src.domain.exceptions import (
    DebateGenerationError,
    DebateLowDivergenceError,
    DebateSynthesisError,
    ExternalException,
    LLMAPIError,
)
from src.domain.exceptions.business_exceptions import BusinessException

_LONG_TEXT = "长" * 150  # 超 100 字符截断验证用


def _make_llm_cause() -> LLMAPIError:
    """构造 LLM 底层异常（cause 链注入用）"""
    return LLMAPIError(message="模拟 LLM API 失败")


# ===================================================================
# DebateGenerationError (EXCEPTION_420)
# ===================================================================


class TestDebateGenerationError:
    def test_code_and_message(self) -> None:
        """编码 420 + 默认消息"""
        error = DebateGenerationError(debate_id="d-1", perspective="red_aggressive", topic_title="议题")
        assert error.code == "EXCEPTION_420"
        assert error.message == "红蓝辩论视角生成失败"

    def test_inherits_external_exception(self) -> None:
        """继承 ExternalException（LLM 调用失败属外部异常范畴）"""
        error = DebateGenerationError(debate_id="d-1", perspective="red_aggressive", topic_title="议题")
        assert isinstance(error, ExternalException)

    def test_context_fields(self) -> None:
        """context 携带 debate_id/perspective/topic_title"""
        debate_id = str(uuid.uuid4())
        error = DebateGenerationError(
            debate_id=debate_id,
            perspective="blue_conservative",
            topic_title="东南亚市场进入议题",
        )
        assert error.context["debate_id"] == debate_id
        assert error.context["perspective"] == "blue_conservative"
        assert error.context["topic_title"] == "东南亚市场进入议题"

    def test_topic_title_truncated_to_100(self) -> None:
        """topic_title 截断至 100 字符"""
        error = DebateGenerationError(debate_id="d-1", perspective="red_aggressive", topic_title=_LONG_TEXT)
        assert len(error.context["topic_title"]) == 100

    def test_cause_chain_preserved(self) -> None:
        """LLM 底层异常经 cause 链入（不吞异常）"""
        cause = _make_llm_cause()
        error = DebateGenerationError(debate_id="d-1", perspective="red_aggressive", topic_title="议题", cause=cause)
        assert error.cause is cause
        data = error.to_dict()
        assert data["cause"]["code"] == "EXCEPTION_330"  # LLMAPIError 是 DomainError 子类，cause 递归 to_dict

    def test_to_dict_structure(self) -> None:
        """to_dict 含 code/message/context 全字段"""
        error = DebateGenerationError(
            debate_id="d-1",
            perspective="red_aggressive",
            topic_title="议题",
            cause=_make_llm_cause(),
        )
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_420"
        assert set(data["context"]) == {"debate_id", "perspective", "topic_title"}
        assert "cause" in data

    def test_custom_message(self) -> None:
        """自定义消息覆盖默认值"""
        error = DebateGenerationError(
            debate_id="d-1", perspective="red_aggressive", topic_title="议题", message="自定义失败描述"
        )
        assert error.message == "自定义失败描述"


# ===================================================================
# DebateSynthesisError (EXCEPTION_421)
# ===================================================================


class TestDebateSynthesisError:
    def test_code_and_message(self) -> None:
        """编码 421 + 默认消息"""
        error = DebateSynthesisError(debate_id="d-1", topic_title="议题")
        assert error.code == "EXCEPTION_421"
        assert error.message == "红蓝辩论风险视图合成失败"

    def test_inherits_external_exception(self) -> None:
        """继承 ExternalException（与 420 分立以区分监控面）"""
        error = DebateSynthesisError(debate_id="d-1", topic_title="议题")
        assert isinstance(error, ExternalException)
        assert not isinstance(error, DebateGenerationError)

    def test_context_fields(self) -> None:
        """context 携带 debate_id/topic_title（无 perspective——合成不分视角）"""
        debate_id = str(uuid.uuid4())
        error = DebateSynthesisError(debate_id=debate_id, topic_title="议题")
        assert set(error.context) == {"debate_id", "topic_title"}
        assert error.context["debate_id"] == debate_id

    def test_topic_title_truncated_to_100(self) -> None:
        """topic_title 截断至 100 字符"""
        error = DebateSynthesisError(debate_id="d-1", topic_title=_LONG_TEXT)
        assert len(error.context["topic_title"]) == 100

    def test_cause_chain_preserved(self) -> None:
        """cause 链保留 + to_dict 解析"""
        cause = _make_llm_cause()
        error = DebateSynthesisError(debate_id="d-1", topic_title="议题", cause=cause)
        data = error.to_dict()
        assert data["cause"]["code"] == "EXCEPTION_330"  # LLMAPIError 是 DomainError 子类，cause 递归 to_dict
        assert data["cause"]["message"]


# ===================================================================
# DebateLowDivergenceError (EXCEPTION_422)
# ===================================================================


class TestDebateLowDivergenceError:
    def test_code_and_message(self) -> None:
        """编码 422 + 默认消息"""
        error = DebateLowDivergenceError(debate_id="d-1", overlap_rate=0.97, red_summary="红", blue_summary="蓝")
        assert error.code == "EXCEPTION_422"
        assert error.message == "红蓝辩论视角分化不足"

    def test_inherits_business_exception(self) -> None:
        """继承 BusinessException（业务规则违反，非外部故障）"""
        error = DebateLowDivergenceError(debate_id="d-1", overlap_rate=0.97, red_summary="红", blue_summary="蓝")
        assert isinstance(error, BusinessException)
        assert not isinstance(error, ExternalException)

    def test_context_fields(self) -> None:
        """context 携带 debate_id/overlap_rate/red_summary/blue_summary"""
        debate_id = str(uuid.uuid4())
        error = DebateLowDivergenceError(
            debate_id=debate_id, overlap_rate=0.96, red_summary="红方论点", blue_summary="蓝方论点"
        )
        assert error.context["debate_id"] == debate_id
        assert error.context["overlap_rate"] == 0.96
        assert error.context["red_summary"] == "红方论点"
        assert error.context["blue_summary"] == "蓝方论点"

    def test_summaries_truncated_to_100(self) -> None:
        """red/blue summary 截断至 100 字符"""
        error = DebateLowDivergenceError(debate_id="d-1", overlap_rate=0.97, red_summary=_LONG_TEXT, blue_summary=_LONG_TEXT)
        assert len(error.context["red_summary"]) == 100
        assert len(error.context["blue_summary"]) == 100

    def test_to_dict_serializable(self) -> None:
        """to_dict 全字段可序列化（无 cause 时无 cause 键）"""
        error = DebateLowDivergenceError(debate_id="d-1", overlap_rate=0.99, red_summary="红", blue_summary="蓝")
        data = error.to_dict()
        assert data["code"] == "EXCEPTION_422"
        assert "cause" not in data


# ===================================================================
# HTTP 映射反向验证（精确注册，避免 isinstance 回退）
# ===================================================================


class TestHttpMapping:
    def test_generation_error_maps_500(self) -> None:
        """420 → 500（精确注册，避免回退 ExternalException 基类 502）"""
        from src.interfaces.api.exception_handlers import _get_http_status

        error = DebateGenerationError(debate_id="d-1", perspective="red_aggressive", topic_title="议题")
        assert _get_http_status(error) == 500

    def test_synthesis_error_maps_500(self) -> None:
        """421 → 500"""
        from src.interfaces.api.exception_handlers import _get_http_status

        error = DebateSynthesisError(debate_id="d-1", topic_title="议题")
        assert _get_http_status(error) == 500

    def test_low_divergence_error_maps_422(self) -> None:
        """422 → 422（精确注册，避免回退 BusinessException 基类 400）"""
        from src.interfaces.api.exception_handlers import _get_http_status

        error = DebateLowDivergenceError(debate_id="d-1", overlap_rate=0.97, red_summary="红", blue_summary="蓝")
        assert _get_http_status(error) == 422

    def test_no_isinstance_fallback_to_base(self) -> None:
        """反向验证：ExternalException 基类映射 502，但 420 精确注册为 500（不回退）"""
        from src.interfaces.api.exception_handlers import _get_http_status

        base_like = DebateGenerationError(debate_id="d-1", perspective="red_aggressive", topic_title="议题")
        assert isinstance(base_like, ExternalException)
        assert _get_http_status(base_like) == 500  # 若无精确注册，isinstance 扫描会得到 502


# ===================================================================
# 子域登记一致性
# ===================================================================


class TestSubdomainRegistration:
    @pytest.mark.parametrize(
        ("class_name", "expected_code"),
        [
            ("DebateGenerationError", 420),
            ("DebateSynthesisError", 421),
            ("DebateLowDivergenceError", 422),
        ],
        ids=["generation", "synthesis", "low-divergence"],
    )
    def test_class_to_subdomain_registered(self, class_name: str, expected_code: int) -> None:
        """_CLASS_TO_SUBDOMAIN 登记 Debate 子域 + 编码落段"""
        from src.domain.exceptions._code_ranges import (
            CODE_RANGES,
            get_range_for_subdomain,
            get_subdomain_for_class,
        )

        assert get_subdomain_for_class(class_name) == "debate"
        debate_range = get_range_for_subdomain("debate")
        assert debate_range is not None
        start, end = debate_range
        assert (start, end) == (420, 429)
        assert start <= expected_code <= end
        assert CODE_RANGES["debate"] == (420, 429)
