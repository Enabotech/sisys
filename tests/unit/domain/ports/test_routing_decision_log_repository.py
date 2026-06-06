"""RoutingDecisionLogRepository 聚合查询单元测试.

验证内存实现的聚合查询能力：
- 按时间范围查询成本摘要
- 按 route_type 过滤
- 空结果返回零值摘要
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.domain.entities.routing_decision_log import RoutingDecisionLog
from src.domain.ports.routing_decision_log_repository import CostSummary
from src.infrastructure.messaging.inmemory_routing_decision_log_repository import (
    InMemoryRoutingDecisionLogRepository,
)


class TestCostSummaryDataclass:
    """CostSummary 数据类测试."""

    def test_default_values(self) -> None:
        """默认值应为零."""
        summary = CostSummary()
        assert summary.total_cost == 0.0
        assert summary.total_prompt_tokens == 0
        assert summary.total_completion_tokens == 0
        assert summary.record_count == 0

    def test_custom_values(self) -> None:
        """自定义值应正确."""
        summary = CostSummary(
            total_cost=1.5,
            total_prompt_tokens=1000,
            total_completion_tokens=2000,
            record_count=5,
        )
        assert summary.total_cost == 1.5
        assert summary.total_prompt_tokens == 1000
        assert summary.total_completion_tokens == 2000
        assert summary.record_count == 5


def _make_log(
    task_id: str = "test-task",
    route_type: str = "local",
    cost_actual: float = 0.0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    timestamp: datetime | None = None,
) -> RoutingDecisionLog:
    """创建测试用 RoutingDecisionLog."""
    return RoutingDecisionLog(
        log_id=uuid.uuid4(),
        task_id=task_id,
        session_id="test-session",
        route_type=route_type,
        route_target="test-target",
        route_score=1.0,
        cost_actual=cost_actual,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        timestamp=timestamp or datetime.now(UTC),
    )


class TestInMemoryRoutingDecisionLogRepositoryAggregation:
    """聚合查询测试."""

    @pytest.fixture
    def repo(self) -> InMemoryRoutingDecisionLogRepository:
        """创建仓储实例."""
        return InMemoryRoutingDecisionLogRepository()

    async def test_query_cost_summary_empty(self, repo: InMemoryRoutingDecisionLogRepository) -> None:
        """空仓储返回零值摘要."""
        now = datetime.now(UTC)
        summary = await repo.query_cost_summary(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        assert summary.total_cost == 0.0
        assert summary.record_count == 0

    async def test_query_cost_summary_with_records(self, repo: InMemoryRoutingDecisionLogRepository) -> None:
        """包含记录时返回正确聚合."""
        now = datetime.now(UTC)
        await repo.save(_make_log(task_id="t1", cost_actual=0.5, prompt_tokens=100, completion_tokens=200, timestamp=now))
        await repo.save(_make_log(task_id="t2", cost_actual=1.5, prompt_tokens=300, completion_tokens=400, timestamp=now))

        summary = await repo.query_cost_summary(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        assert summary.total_cost == 2.0
        assert summary.total_prompt_tokens == 400
        assert summary.total_completion_tokens == 600
        assert summary.record_count == 2

    async def test_query_cost_summary_filter_by_route_type(self, repo: InMemoryRoutingDecisionLogRepository) -> None:
        """按 route_type 过滤."""
        now = datetime.now(UTC)
        await repo.save(_make_log(task_id="t1", route_type="local", cost_actual=0.5, timestamp=now))
        await repo.save(_make_log(task_id="t2", route_type="cloud", cost_actual=1.5, timestamp=now))

        summary = await repo.query_cost_summary(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            route_type="local",
        )
        assert summary.total_cost == 0.5
        assert summary.record_count == 1

    async def test_query_cost_summary_out_of_range(self, repo: InMemoryRoutingDecisionLogRepository) -> None:
        """时间范围外的记录不计入."""
        now = datetime.now(UTC)
        old_time = now - timedelta(days=7)
        await repo.save(_make_log(task_id="t1", cost_actual=1.0, timestamp=old_time))

        summary = await repo.query_cost_summary(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        assert summary.record_count == 0


class TestInMemoryRoutingDecisionLogRepositoryConcurrency:
    """asyncio.Lock 并发安全测试."""

    async def test_concurrent_saves(self) -> None:
        """并发写入不应丢失数据."""
        repo = InMemoryRoutingDecisionLogRepository()
        now = datetime.now(UTC)

        await asyncio.gather(*[repo.save(_make_log(task_id=f"t{i}", timestamp=now)) for i in range(50)])

        summary = await repo.query_cost_summary(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        assert summary.record_count == 50


class TestInMemoryRoutingDecisionLogRepositoryEviction:
    """容量控制和淘汰测试."""

    async def test_max_size_fifo_eviction(self) -> None:
        """超过 max_size 时 FIFO 淘汰最早记录."""
        repo = InMemoryRoutingDecisionLogRepository(max_size=3)
        now = datetime.now(UTC)

        log1 = _make_log(task_id="first", timestamp=now)
        log2 = _make_log(task_id="second", timestamp=now)
        log3 = _make_log(task_id="third", timestamp=now)
        log4 = _make_log(task_id="fourth", timestamp=now)

        await repo.save(log1)
        await repo.save(log2)
        await repo.save(log3)
        # 第 4 条写入后，第 1 条应被淘汰
        await repo.save(log4)

        assert await repo.find_by_task_id("first") is None
        assert await repo.find_by_task_id("fourth") is not None

    async def test_ttl_eviction(self) -> None:
        """过期记录应在下次写入时被淘汰."""
        repo = InMemoryRoutingDecisionLogRepository(ttl_seconds=0.01)
        now = datetime.now(UTC)

        await repo.save(_make_log(task_id="expired", timestamp=now))
        # 等待 TTL 过期
        time.sleep(0.02)
        # 写入新记录触发 cleanup
        await repo.save(_make_log(task_id="fresh", timestamp=now))

        assert await repo.find_by_task_id("expired") is None
        assert await repo.find_by_task_id("fresh") is not None


class TestCostSummaryImmutability:
    """CostSummary 不可变性测试."""

    def test_cost_summary_is_frozen(self) -> None:
        """CostSummary 是不可变数据类（可哈希）"""
        from src.domain.ports.routing_decision_log_repository import CostSummary

        s1 = CostSummary(total_cost=1.0, record_count=5)
        s2 = CostSummary(total_cost=1.0, record_count=5)
        assert hash(s1) == hash(s2)


class TestRoutingDecisionLogRepositoryProtocol:
    """Protocol 端口契约测试."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol 应支持运行时检查."""
        from src.domain.ports.routing_decision_log_repository import RoutingDecisionLogRepository

        assert hasattr(RoutingDecisionLogRepository, "_is_runtime_protocol")

    def test_implementation_passes_isinstance(self) -> None:
        """符合协议的实现应通过 isinstance 检查."""
        from src.domain.ports.routing_decision_log_repository import RoutingDecisionLogRepository
        from src.infrastructure.messaging.inmemory_routing_decision_log_repository import (
            InMemoryRoutingDecisionLogRepository,
        )

        repo = InMemoryRoutingDecisionLogRepository()
        assert isinstance(repo, RoutingDecisionLogRepository)

    def test_non_conforming_class_fails_isinstance(self) -> None:
        """不符合协议的类应无法通过 isinstance 检查."""
        from src.domain.ports.routing_decision_log_repository import RoutingDecisionLogRepository

        class NonConforming:
            pass

        assert not isinstance(NonConforming(), RoutingDecisionLogRepository)

    def test_protocol_methods_exist(self) -> None:
        """协议应定义 save、find_by_task_id、query_cost_summary 方法."""
        from src.domain.ports.routing_decision_log_repository import RoutingDecisionLogRepository

        assert hasattr(RoutingDecisionLogRepository, "save")
        assert hasattr(RoutingDecisionLogRepository, "find_by_task_id")
        assert hasattr(RoutingDecisionLogRepository, "query_cost_summary")
