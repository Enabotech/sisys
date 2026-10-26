"""IsolationSwitchLogQuery / IsolationSwitchLogSearchResult / IsolationSwitchLogRepository
端口单元测试（Story 5.6 — Task 2 TDD 循环 A）

纯领域层端口契约验证（与组合根契约测试分离）:
- IsolationSwitchLogQuery: frozen + 多字段组合（agent_id/start_time/end_time/level
  双向命中语义）+ offset/limit 默认（0/50）+ __post_init__ 守卫（offset<0 /
  limit<=0 / limit>500 → 242）——Query Object 决策规则命中（多字段组合+分页）
- IsolationSwitchLogSearchResult: frozen + items 强类型 tuple[IsolationSwitchLog, ...]
  + total/offset/limit
- IsolationSwitchLogRepository: @runtime_checkable Protocol + save/search 两方法
  签名存在性（双模式 session 分派是实现契约——DC-5）

Run with:
    poetry run pytest tests/unit/domain/ports/test_isolation_switch_log_repository_port.py -v
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime
from typing import Any, get_type_hints

import pytest

from src.domain.entities.isolation_switch_log import IsolationSwitchLog
from src.domain.events.enums import IsolationLevel
from src.domain.events.isolation_events import IsolationLevelSwitched
from src.domain.exceptions import EntityValidationError
from src.domain.ports.isolation_switch_log_repository import (
    IsolationSwitchLogQuery,
    IsolationSwitchLogRepository,
    IsolationSwitchLogSearchResult,
)


def _make_log() -> IsolationSwitchLog:
    """合法日志实体构造辅助（from_event 通道）."""
    event = IsolationLevelSwitched(
        agent_id=uuid.uuid4(),
        previous_level=IsolationLevel.L4_HARD,
        target_level=IsolationLevel.L3_SOFT,
        trigger_reason="端口测试",
        approval_chain=["审批人"],
        switch_timestamp=datetime(2026, 10, 25, 10, 0, 0, tzinfo=UTC),
    )
    return IsolationSwitchLog.from_event(event)


class TestIsolationSwitchLogQueryDefaults:
    """Query 默认值与字段形态。"""

    def test_all_none_defaults(self) -> None:
        """四过滤维度默认 None（全量分页返回——合法调用）."""
        query = IsolationSwitchLogQuery()
        assert query.agent_id is None
        assert query.start_time is None
        assert query.end_time is None
        assert query.level is None

    def test_pagination_defaults(self) -> None:
        """分页默认 offset=0 / limit=50."""
        query = IsolationSwitchLogQuery()
        assert query.offset == 0
        assert query.limit == 50

    def test_frozen(self) -> None:
        """Query Object frozen（不可变查询契约）."""
        query = IsolationSwitchLogQuery()
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(query, "limit", 10)

    def test_all_fields_assignable(self) -> None:
        """多字段组合构造（四维 + 分页——AC-3 组合场景形态）."""
        now = datetime.now(UTC)
        agent_id = uuid.uuid4()
        query = IsolationSwitchLogQuery(
            agent_id=agent_id,
            start_time=now,
            end_time=now,
            level=IsolationLevel.L3_SOFT,
            offset=10,
            limit=100,
        )
        assert query.agent_id == agent_id
        assert query.level is IsolationLevel.L3_SOFT
        assert query.offset == 10
        assert query.limit == 100


class TestIsolationSwitchLogQueryGuards:
    """Query __post_init__ 守卫（242——分页边界 + 类型/时区/区间，R1-F5）."""

    def test_negative_offset_rejected(self) -> None:
        """offset<0 → 242."""
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLogQuery(offset=-1)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_non_int_offset_rejected(self) -> None:
        """offset 非 int（str）→ 242（R3-F3：比较运算对非 int 抛裸 TypeError——
        与同 __post_init__ 的 isinstance 先行哲学对齐）。"""
        bad: dict[str, Any] = {"offset": "5"}
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLogQuery(**bad)
        assert exc_info.value.code == "EXCEPTION_242"
        assert "offset" in exc_info.value.context

    def test_none_limit_rejected(self) -> None:
        """limit=None → 242（非 int 形态——同 R3-F3）。"""
        bad: dict[str, Any] = {"limit": None}
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLogQuery(**bad)
        assert exc_info.value.code == "EXCEPTION_242"
        assert "limit" in exc_info.value.context

    def test_bool_offset_rejected(self) -> None:
        """offset=True（bool 是 int 子类）→ 242（显式拒——bool 传分页位是
        调用 bug 形态，合法 UUID 字符串同拒的严格类型面哲学）。"""
        bad: dict[str, Any] = {"offset": True}
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLogQuery(**bad)
        assert exc_info.value.code == "EXCEPTION_242"
        assert "offset" in exc_info.value.context

    def test_zero_limit_rejected(self) -> None:
        """limit<=0 → 242（limit=0 形态）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLogQuery(limit=0)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_negative_limit_rejected(self) -> None:
        """limit<=0 → 242（limit=-5 形态）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLogQuery(limit=-5)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_limit_over_500_rejected(self) -> None:
        """limit>500 → 242（上限 500——防失控全表拉取）."""
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLogQuery(limit=501)
        assert exc_info.value.code == "EXCEPTION_242"

    def test_limit_boundary_500_accepted(self) -> None:
        """limit=500 边界合法（闭区间上限）."""
        assert IsolationSwitchLogQuery(limit=500).limit == 500

    def test_offset_zero_accepted(self) -> None:
        """offset=0 边界合法."""
        assert IsolationSwitchLogQuery(offset=0).offset == 0

    def test_bare_str_level_rejected(self) -> None:
        """level 裸 str → 242（str,Enum 混入 hash 穿透的 Query 侧防线——
        裸 str 深入 PG 实现以 ``.value`` AttributeError 逃逸异常体系，
        5-4 R3-F01 教训延伸，R1-F5）。"""
        bad: dict[str, Any] = {"level": "L4"}  # 裸 str 形态（dict 注入——运行时类型面）
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLogQuery(**bad)
        assert exc_info.value.code == "EXCEPTION_242"
        assert "level" in exc_info.value.context

    def test_agent_id_non_uuid_rejected(self) -> None:
        """agent_id 非 UUID 实例 → 242（与实体场景①对称——asyncpg 绑定错误
        fail-loud 但语义错标为 103，Query 层前置归因，R1-F5）。"""
        bad: dict[str, Any] = {"agent_id": "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"}
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLogQuery(**bad)
        assert exc_info.value.code == "EXCEPTION_242"
        assert "agent_id" in exc_info.value.context

    def test_start_time_naive_rejected(self) -> None:
        """start_time naive datetime → 242（跨时区部署过滤语义歧义）。"""
        bad: dict[str, Any] = {"start_time": datetime(2026, 10, 25, 0, 0, 0)}
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLogQuery(**bad)
        assert exc_info.value.code == "EXCEPTION_242"
        assert "start_time" in exc_info.value.context

    def test_end_time_non_datetime_rejected(self) -> None:
        """end_time 非 datetime 实例（ISO 字符串）→ 242."""
        bad: dict[str, Any] = {"end_time": "2026-10-26T00:00:00+00:00"}
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLogQuery(**bad)
        assert exc_info.value.code == "EXCEPTION_242"
        assert "end_time" in exc_info.value.context

    def test_inverted_time_window_rejected(self) -> None:
        """start_time > end_time → 242（反转窗以空结果静默呈现会与「该时段
        确无切换」不可区分——调用错误应显式拒绝）。"""
        with pytest.raises(EntityValidationError) as exc_info:
            IsolationSwitchLogQuery(
                start_time=datetime(2026, 10, 26, 0, 0, 0, tzinfo=UTC),
                end_time=datetime(2026, 10, 25, 0, 0, 0, tzinfo=UTC),
            )
        assert exc_info.value.code == "EXCEPTION_242"
        assert "start_time" in exc_info.value.context

    def test_equal_time_window_accepted(self) -> None:
        """start_time == end_time 边界合法（闭区间单点查询）."""
        moment = datetime(2026, 10, 25, 0, 0, 0, tzinfo=UTC)
        query = IsolationSwitchLogQuery(start_time=moment, end_time=moment)
        assert query.start_time == moment


class TestIsolationSwitchLogSearchResult:
    """SearchResult 强类型结果（items 为实体 tuple 非 dict——DC-3）."""

    def test_construction_with_entity_tuple(self) -> None:
        """items: tuple[IsolationSwitchLog, ...] 强类型 + total/offset/limit."""
        log = _make_log()
        result = IsolationSwitchLogSearchResult(items=(log,), total=1, offset=0, limit=50)
        assert result.items == (log,)
        assert isinstance(result.items, tuple)
        assert isinstance(result.items[0], IsolationSwitchLog)
        assert result.total == 1
        assert result.offset == 0
        assert result.limit == 50

    def test_empty_result(self) -> None:
        """空结果形态（items 空 tuple + total 0——空结果非异常）。"""
        result = IsolationSwitchLogSearchResult(items=(), total=0, offset=0, limit=50)
        assert result.items == ()
        assert result.total == 0

    def test_frozen(self) -> None:
        """Result frozen（不可变检索事实）."""
        result = IsolationSwitchLogSearchResult(items=(), total=0, offset=0, limit=50)
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(result, "total", 99)


class TestRepositoryProtocol:
    """IsolationSwitchLogRepository 端口定义（R1 领域层基础端口）。"""

    def test_runtime_checkable(self) -> None:
        """@runtime_checkable Protocol（isinstance 判定可用——契约测试基础）。"""

        class _DummyRepo:
            async def save(self, log: IsolationSwitchLog) -> None:
                return None

            async def search(self, query: IsolationSwitchLogQuery) -> IsolationSwitchLogSearchResult:
                return IsolationSwitchLogSearchResult(items=(), total=0, offset=0, limit=50)

        assert isinstance(_DummyRepo(), IsolationSwitchLogRepository)

    def test_protocol_methods_declared(self) -> None:
        """save/search 两方法签名存在（端口契约面完整）。"""
        hints: dict[str, Any] = get_type_hints(IsolationSwitchLogRepository.save)
        assert "log" in hints
        assert hints["return"] is type(None)
        search_hints = get_type_hints(IsolationSwitchLogRepository.search)
        assert "query" in search_hints
        assert search_hints["return"] is IsolationSwitchLogSearchResult

    def test_two_methods_only(self) -> None:
        """端口面最小（save/search 两方法——无 get/delete/update：追加型日志只增不改）."""
        methods = [name for name in dir(IsolationSwitchLogRepository) if not name.startswith("_")]
        assert "save" in methods
        assert "search" in methods
