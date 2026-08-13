"""RoutingDecisionLogRepository 端口契约测试

验证 RoutingDecisionLogRepository Protocol 和 CostSummary 的结构化子类型合规性。
"""

from __future__ import annotations

import inspect
from datetime import datetime

from src.domain.ports.routing_decision_log_repository import (
    CostSummary,
    RoutingDecisionLogRepository,
)


class TestCostSummary:
    """测试 CostSummary 值对象"""

    def test_default_values(self) -> None:
        cs = CostSummary()
        assert cs.total_cost == 0.0
        assert cs.total_prompt_tokens == 0
        assert cs.total_completion_tokens == 0
        assert cs.record_count == 0

    def test_frozen_dataclass(self) -> None:
        cs = CostSummary(total_cost=1.5, total_prompt_tokens=100, total_completion_tokens=50, record_count=10)
        assert cs.total_cost == 1.5
        assert cs.total_prompt_tokens == 100
        assert cs.total_completion_tokens == 50
        assert cs.record_count == 10


class TestRoutingDecisionLogRepositoryContract:
    """测试 RoutingDecisionLogRepository 端口契约"""

    def test_protocol_is_runtime_checkable(self) -> None:
        assert hasattr(RoutingDecisionLogRepository, "_is_runtime_protocol")
        assert RoutingDecisionLogRepository._is_runtime_protocol is True

    def test_save_method_exists(self) -> None:
        assert hasattr(RoutingDecisionLogRepository, "save")
        method = getattr(RoutingDecisionLogRepository, "save")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_find_by_task_id_method_exists(self) -> None:
        assert hasattr(RoutingDecisionLogRepository, "find_by_task_id")
        method = getattr(RoutingDecisionLogRepository, "find_by_task_id")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_query_cost_summary_method_exists(self) -> None:
        assert hasattr(RoutingDecisionLogRepository, "query_cost_summary")
        method = getattr(RoutingDecisionLogRepository, "query_cost_summary")
        assert callable(method)
        assert inspect.iscoroutinefunction(method)

    def test_query_cost_summary_signature(self) -> None:
        method = getattr(RoutingDecisionLogRepository, "query_cost_summary")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "start_time" in params
        assert "end_time" in params
        assert "route_type" in params

    def test_compliant_implementation(self) -> None:
        class MockRepo:
            async def save(self, log) -> None:
                pass

            async def find_by_task_id(self, task_id: str):
                return None

            async def query_cost_summary(
                self, start_time: datetime, end_time: datetime, route_type: str | None = None
            ) -> CostSummary:
                return CostSummary()

        repo = MockRepo()
        assert isinstance(repo, RoutingDecisionLogRepository)

    def test_noncompliant_implementation_fails(self) -> None:
        class BadRepo:
            pass

        assert not isinstance(BadRepo(), RoutingDecisionLogRepository)


__all__ = ["TestCostSummary", "TestRoutingDecisionLogRepositoryContract"]
