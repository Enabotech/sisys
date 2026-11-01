"""Story 6-1 — planning 子域异常单元测试（480~482 新子域段 (480,489) 开段）。

TDD 循环 B 载体：构造/context 领域上下文/to_dict/cause 链/编码唯一性。
五件套齐备性由 test_code_ranges.py（Rule 1~5）与
test_error_code_uniqueness.py（3 项）联动承载——本文件聚焦异常类自身行为。
"""

from __future__ import annotations

import pytest

from src.domain.exceptions import (
    PlanningExecutionError,
    PlanningNotFoundError,
    PlanningStateError,
)
from src.domain.exceptions.business_exceptions import BusinessException


class TestPlanningExceptions:
    """planning 子域三异常（480~482）。"""

    def test_planning_not_found_code_480(self) -> None:
        """480 编码 + 404 语义（plan_id 不存在）。"""
        exc = PlanningNotFoundError(plan_id="plan-123")
        assert exc.code == "EXCEPTION_480"
        assert exc.context["plan_id"] == "plan-123"

    def test_planning_execution_error_code_481(self) -> None:
        """481 编码（全流程失败终态——RunBlmPlanningUseCase 终态组装处抛出）。"""
        exc = PlanningExecutionError(agent_id="agent-1", plan_id="plan-123", reason="全部 8 步降级")
        assert exc.code == "EXCEPTION_481"
        assert exc.context["plan_id"] == "plan-123"
        assert exc.context["agent_id"] == "agent-1"
        assert "8 步" in exc.context["reason"]

    def test_planning_state_error_code_482(self) -> None:
        """482 编码（状态机非法推进——预留）。"""
        exc = PlanningStateError(plan_id="plan-123", transition="market_insight→performance_gap")
        assert exc.code == "EXCEPTION_482"
        assert exc.context["transition"] == "market_insight→performance_gap"

    def test_business_exception_inheritance(self) -> None:
        """语义继承 BusinessException 基类（非内置 Exception——红线）。"""
        assert issubclass(PlanningNotFoundError, BusinessException)
        assert issubclass(PlanningExecutionError, BusinessException)
        assert issubclass(PlanningStateError, BusinessException)

    def test_to_dict_shape(self) -> None:
        """to_dict 含 code/message/context 三键（DomainError 契约）。"""
        exc = PlanningNotFoundError(plan_id="plan-1")
        payload = exc.to_dict()
        assert payload["code"] == "EXCEPTION_480"
        assert payload["message"]
        assert payload["context"]["plan_id"] == "plan-1"

    def test_cause_chain(self) -> None:
        """cause 链构造（底层异常上下文不丢失）。"""
        root = RuntimeError("底层存储故障")
        exc = PlanningExecutionError(agent_id="a", plan_id="p", reason="级联失败", cause=root)
        assert exc.cause is root
        payload = exc.to_dict()
        assert payload.get("cause") is not None

    def test_message_does_not_leak_internals(self) -> None:
        """静态消息不含内部实现细节（领域契约——消息模板 + context 分离）。"""
        exc = PlanningExecutionError(agent_id="a", plan_id="p", reason="x" * 300)
        # message 是静态领域文案；动态细节进 context（reason 截断防泄漏面）
        assert exc.message == "规划执行失败"

    def test_context_extra_merge(self) -> None:
        """context_extra 合并（调用方附加领域上下文）。"""
        exc = PlanningNotFoundError(plan_id="p", context_extra={"source": "cli"})
        assert exc.context["source"] == "cli"

    def test_codes_unique_across_planning(self) -> None:
        """三异常编码互异（480/481/482）。"""
        codes = {PlanningNotFoundError.code, PlanningExecutionError.code, PlanningStateError.code}
        assert codes == {"EXCEPTION_480", "EXCEPTION_481", "EXCEPTION_482"}


class TestPlanningExceptionRegistration:
    """五件套注册面（_code_ranges/HTTP 映射/子域段——联动校验）。"""

    def test_code_ranges_has_planning_segment(self) -> None:
        """CODE_RANGES 含 planning 段 (480,489)（第八段——410/420/430/440/450/460/470 先例链）。"""
        from src.domain.exceptions._code_ranges import CODE_RANGES

        assert CODE_RANGES.get("planning") == (480, 489)

    def test_planning_range_not_overlapping_financial(self) -> None:
        """planning 段与 financial 段 (470,479) 不重叠（双重成文预留不侵占）。"""
        from src.domain.exceptions._code_ranges import CODE_RANGES

        planning_start, planning_end = CODE_RANGES["planning"]
        financial_start, financial_end = CODE_RANGES["financial"]
        assert planning_start > financial_end, "planning 段不得与 financial 预留段重叠"

    def test_class_to_subdomain_registered(self) -> None:
        """_CLASS_TO_SUBDOMAIN 三条齐备。"""
        from src.domain.exceptions._code_ranges import _CLASS_TO_SUBDOMAIN

        assert _CLASS_TO_SUBDOMAIN.get("PlanningNotFoundError") == "planning"
        assert _CLASS_TO_SUBDOMAIN.get("PlanningExecutionError") == "planning"
        assert _CLASS_TO_SUBDOMAIN.get("PlanningStateError") == "planning"

    def test_http_map_registered(self) -> None:
        """EXCEPTION_HTTP_MAP 三异常登记（精确注册 + 值级断言——改挂状态码即红，R1-9④）。"""
        from fastapi import status

        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert PlanningNotFoundError in EXCEPTION_HTTP_MAP
        assert PlanningExecutionError in EXCEPTION_HTTP_MAP
        assert PlanningStateError in EXCEPTION_HTTP_MAP
        assert EXCEPTION_HTTP_MAP[PlanningNotFoundError] == status.HTTP_404_NOT_FOUND
        assert EXCEPTION_HTTP_MAP[PlanningExecutionError] == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert EXCEPTION_HTTP_MAP[PlanningStateError] == status.HTTP_409_CONFLICT

    def test_no_placeholder_codes(self) -> None:
        """具体类零占位编码（EXCEPTION_000/_2XX 族——Rule 3）。"""
        for exc_cls in (PlanningNotFoundError, PlanningExecutionError, PlanningStateError):
            assert exc_cls.code not in {"EXCEPTION_000", "EXCEPTION_1XX", "EXCEPTION_2XX", "EXCEPTION_3XX"}


@pytest.mark.parametrize(
    "exc_cls",
    [PlanningNotFoundError, PlanningExecutionError, PlanningStateError],
    ids=["480", "481", "482"],
)
def test_exception_is_domain_error_subclass(exc_cls: type) -> None:
    """三异常均为 DomainError 子类（统一异常体系根）。"""
    from src.domain.exceptions.base_exceptions import DomainError

    assert issubclass(exc_cls, DomainError)
