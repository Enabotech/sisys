"""应用层档案事件处理器单元测试（扩展）

验证 ArchiveValidityHandler 的 L3/L5 同步、降权标记和 _run_async 适配。
Story 3.12 AC-2 / AC-3 覆盖。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.event_handlers.archive_handlers import ArchiveValidityHandler
from src.domain.entities.strategic_archive import ArchiveType
from src.domain.events.archive_events import FactBecameStale, ValidityPeriodSet
from src.domain.ports.l3_vector import L3VectorPort
from src.domain.ports.l5_graph import L5GraphPort


def _make_listener() -> MagicMock:
    """创建 Mock 事件监听器（EventListener 端口）"""
    return MagicMock()


def _make_l3_vector() -> AsyncMock:
    """创建 Mock L3VectorPort 实例"""
    mock = AsyncMock(spec=L3VectorPort)
    mock.get_point.return_value = {
        "id": "strategic_archive:test",
        "vector": [0.1] * 1024,
        "payload": {"archive_id": "test", "plan_id": "test"},
    }
    return mock


def _make_l5_graph() -> AsyncMock:
    """创建 Mock L5GraphPort 实例"""
    return AsyncMock(spec=L5GraphPort)


class TestArchiveValidityHandler:
    """ArchiveValidityHandler 事件处理器测试"""

    def test_register_handlers_subscribes_events(self) -> None:
        """register_handlers 注册 ValidityPeriodSet 和 FactBecameStale"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(event_listener=listener)
        handler.register_handlers()
        # on_event 触发两次：ValidityPeriodSet + FactBecameStale
        assert listener.on_event.call_count == 2
        event_types = [call.args[0] for call in listener.on_event.call_args_list]
        assert "ValidityPeriodSet" in event_types
        assert "FactBecameStale" in event_types

    def test_handle_validity_period_set_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """ValidityPeriodSet 事件处理记录日志"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(event_listener=listener)
        handler.register_handlers()
        event = ValidityPeriodSet(
            archive_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            archive_type=ArchiveType.ASSUMPTION,
            valid_from=datetime(2026, 1, 1, tzinfo=UTC),
            valid_until=datetime(2027, 12, 31, tzinfo=UTC),
        )
        with caplog.at_level(logging.INFO, logger="src.application.event_handlers.archive_handlers"):
            handler._handle_validity_period_set(event)
        assert "Validity period set for archive" in caplog.text

    # ===================================================================
    # AC-2: ValidityPeriodSet → L3/L5 同步
    # ===================================================================

    def test_validity_period_syncs_l3(self, caplog: pytest.LogCaptureFixture) -> None:
        """ValidityPeriodSet 事件同步 L3 payload（读-改-写三步）"""
        listener = _make_listener()
        l3 = _make_l3_vector()
        handler = ArchiveValidityHandler(
            event_listener=listener,
            l3_vector=cast(L3VectorPort, l3),
            l5_graph=None,
        )
        archive_id = uuid.uuid4()
        event = ValidityPeriodSet(
            archive_id=archive_id,
            plan_id=uuid.uuid4(),
            archive_type=ArchiveType.ASSUMPTION,
            valid_from=datetime(2026, 1, 1, tzinfo=UTC),
            valid_until=datetime(2027, 12, 31, tzinfo=UTC),
        )
        with caplog.at_level(logging.INFO, logger="src.application.event_handlers.archive_handlers"):
            handler._handle_validity_period_set(event)

        # 读-改-写三步：get_point → 合并 payload → upsert_points
        assert l3.get_point.called
        assert l3.get_point.call_args[1]["collection"] == "strategic_archive"
        assert l3.upsert_points.called
        call_args = l3.upsert_points.call_args[1]
        assert call_args["collection"] == "strategic_archive"
        point = call_args["points"][0]
        payload = point["payload"]
        # 合并后的 payload 包含原有字段和新字段
        assert payload["archive_id"] == "test"
        assert payload["valid_from"] == "2026-01-01T00:00:00+00:00"
        assert payload["valid_until"] == "2027-12-31T00:00:00+00:00"
        assert "Validity period set for archive" in caplog.text

    def test_validity_period_syncs_l5(self) -> None:
        """ValidityPeriodSet 事件同步 L5 properties（Cypher SET）"""
        listener = _make_listener()
        l5 = _make_l5_graph()
        handler = ArchiveValidityHandler(
            event_listener=listener,
            l3_vector=None,
            l5_graph=cast(L5GraphPort, l5),
        )
        archive_id = uuid.uuid4()
        valid_from = datetime(2026, 1, 1, tzinfo=UTC)
        valid_until = datetime(2027, 12, 31, tzinfo=UTC)
        event = ValidityPeriodSet(
            archive_id=archive_id,
            plan_id=uuid.uuid4(),
            archive_type=ArchiveType.ASSUMPTION,
            valid_from=valid_from,
            valid_until=valid_until,
        )
        handler._handle_validity_period_set(event)

        assert l5.execute_write_query.called
        call_args = l5.execute_write_query.call_args[1]
        assert "MATCH (n {memory_id: $memory_id})" in call_args["cypher"]
        assert call_args["params"]["memory_id"] == str(archive_id)
        assert call_args["params"]["valid_from"] == "2026-01-01T00:00:00+00:00"
        assert call_args["params"]["valid_until"] == "2027-12-31T00:00:00+00:00"

    def test_l3_unavailable_degrades_gracefully(self, caplog: pytest.LogCaptureFixture) -> None:
        """L3 不可用（None）时降级记录 WARNING"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(
            event_listener=listener,
            l3_vector=None,
            l5_graph=None,
        )
        event = ValidityPeriodSet(archive_id=uuid.uuid4())
        with caplog.at_level(logging.WARNING, logger="src.application.event_handlers.archive_handlers"):
            handler._handle_validity_period_set(event)
        # 不抛出异常，正常完成
        assert "L3 vector storage not available" in caplog.text

    def test_l5_unavailable_degrades_gracefully(self, caplog: pytest.LogCaptureFixture) -> None:
        """L5 不可用（None）时降级记录 WARNING"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(
            event_listener=listener,
            l3_vector=None,
            l5_graph=None,
        )
        event = ValidityPeriodSet(archive_id=uuid.uuid4())
        with caplog.at_level(logging.WARNING, logger="src.application.event_handlers.archive_handlers"):
            handler._handle_validity_period_set(event)
        assert "L5 graph storage not available" in caplog.text

    def test_l3_exception_logged_not_raised(self, caplog: pytest.LogCaptureFixture) -> None:
        """L3 同步异常记录 WARNING，不抛出"""
        listener = _make_listener()
        l3 = _make_l3_vector()
        l3.upsert_points.side_effect = RuntimeError("qdrant timeout")
        handler = ArchiveValidityHandler(
            event_listener=listener,
            l3_vector=cast(L3VectorPort, l3),
            l5_graph=None,
        )
        event = ValidityPeriodSet(archive_id=uuid.uuid4())
        # 不应抛出异常
        handler._handle_validity_period_set(event)
        # 验证日志包含 WARNING
        assert any("L3" in msg and "sync" in msg for msg in caplog.messages)

    def test_l5_exception_logged_not_raised(self, caplog: pytest.LogCaptureFixture) -> None:
        """L5 同步异常记录 WARNING，不抛出"""
        listener = _make_listener()
        l5 = _make_l5_graph()
        l5.execute_write_query.side_effect = RuntimeError("neo4j timeout")
        handler = ArchiveValidityHandler(
            event_listener=listener,
            l3_vector=None,
            l5_graph=cast(L5GraphPort, l5),
        )
        event = ValidityPeriodSet(archive_id=uuid.uuid4())
        handler._handle_validity_period_set(event)
        assert any("L5" in msg and "sync" in msg for msg in caplog.messages)

    # ===================================================================
    # AC-3: FactBecameStale → L3 降权标记
    # ===================================================================

    def test_fact_stale_marks_l3_payload(self) -> None:
        """FactBecameStale 事件更新 L3 payload 标记 is_stale/stale_reason/stale_since"""
        listener = _make_listener()
        l3 = _make_l3_vector()
        handler = ArchiveValidityHandler(
            event_listener=listener,
            l3_vector=cast(L3VectorPort, l3),
            l5_graph=None,
        )
        event = FactBecameStale(
            archive_id=uuid.uuid4(),
            stale_reason="expired",
            stale_since=datetime(2026, 8, 15, 12, 0, 0, tzinfo=UTC),
        )
        handler._handle_fact_became_stale(event)

        # 读-改-写三步
        assert l3.get_point.called
        assert l3.upsert_points.called
        call_args = l3.upsert_points.call_args[1]
        point = call_args["points"][0]
        payload = point["payload"]
        assert payload["is_stale"] is True
        assert payload["stale_reason"] == "expired"
        assert payload["stale_since"] == "2026-08-15T12:00:00+00:00"
        # 原始字段保留
        assert payload["archive_id"] == "test"

    def test_fact_stale_l3_unavailable_degrades(self, caplog: pytest.LogCaptureFixture) -> None:
        """FactBecameStale 事件 L3 不可用时降级记录 WARNING"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(
            event_listener=listener,
            l3_vector=None,
            l5_graph=None,
        )
        event = FactBecameStale(archive_id=uuid.uuid4(), stale_reason="expired")
        handler._handle_fact_became_stale(event)
        assert "L3 vector storage not available" in caplog.text

    def test_fact_stale_l3_exception_logged_not_raised(self, caplog: pytest.LogCaptureFixture) -> None:
        """FactBecameStale 事件 L3 异常记录 WARNING，不抛出"""
        listener = _make_listener()
        l3 = _make_l3_vector()
        l3.upsert_points.side_effect = RuntimeError("qdrant timeout")
        handler = ArchiveValidityHandler(
            event_listener=listener,
            l3_vector=cast(L3VectorPort, l3),
            l5_graph=None,
        )
        event = FactBecameStale(archive_id=uuid.uuid4(), stale_reason="expired")
        # 不应抛出
        handler._handle_fact_became_stale(event)
        assert any("L3" in msg for msg in caplog.messages)

    def test_fact_stale_already_marked_idempotent(self) -> None:
        """已标记 is_stale 的档案跳过重复更新（幂等）"""
        listener = _make_listener()
        l3 = _make_l3_vector()
        # 已标记 is_stale=True
        l3.get_point.return_value = {
            "id": "strategic_archive:test",
            "vector": [0.1] * 1024,
            "payload": {"archive_id": "test", "is_stale": True, "stale_reason": "expired"},
        }
        handler = ArchiveValidityHandler(
            event_listener=listener,
            l3_vector=cast(L3VectorPort, l3),
            l5_graph=None,
        )
        event = FactBecameStale(
            archive_id=uuid.uuid4(),
            stale_reason="expired",
            stale_since=datetime(2026, 8, 15, 12, 0, 0, tzinfo=UTC),
        )
        handler._handle_fact_became_stale(event)

        # get_point 被调用，但 upsert_points 未被调用（跳过更新）
        assert l3.get_point.called
        assert not l3.upsert_points.called

    def test_fact_stale_point_not_found_skips(self, caplog: pytest.LogCaptureFixture) -> None:
        """L3 点不存在时记录 WARNING 并跳过"""
        listener = _make_listener()
        l3 = _make_l3_vector()
        l3.get_point.return_value = None  # 点不存在
        handler = ArchiveValidityHandler(
            event_listener=listener,
            l3_vector=cast(L3VectorPort, l3),
            l5_graph=None,
        )
        event = FactBecameStale(archive_id=uuid.uuid4(), stale_reason="expired")
        handler._handle_fact_became_stale(event)
        assert l3.get_point.called
        assert not l3.upsert_points.called
        assert "not found" in caplog.text.lower() or "skip" in caplog.text.lower()

    # ===================================================================
    # _run_async 适配
    # ===================================================================

    def test_run_async_no_running_loop(self) -> None:
        """无运行循环时 _run_async 使用 asyncio.run()"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(event_listener=listener)

        async def dummy_coro() -> str:
            return "done"

        result = handler._run_async(dummy_coro())
        assert result == "done"

    @pytest.mark.asyncio
    async def test_run_async_with_running_loop(self) -> None:
        """有运行循环时 _run_async 使用 create_task"""
        listener = _make_listener()
        l3 = _make_l3_vector()
        handler = ArchiveValidityHandler(
            event_listener=listener,
            l3_vector=cast(L3VectorPort, l3),
            l5_graph=None,
        )

        results = []

        async def dummy_coro() -> None:
            results.append("executed")

        handler._run_async(dummy_coro())
        # create_task 是 fire-and-forget，需要 await 让 task 执行
        await asyncio.sleep(0)
        assert "executed" in results

    @pytest.mark.asyncio
    async def test_run_async_with_running_loop_handles_exception(self) -> None:
        """有运行循环时 _run_async 的异常不传播到调用方"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(event_listener=listener)

        async def failing_coro() -> None:
            raise RuntimeError("async error")

        # 不应抛出异常
        handler._run_async(failing_coro())
        await asyncio.sleep(0)  # 让 task 执行

    @pytest.mark.asyncio
    async def test_run_async_logs_task_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        """_run_async create_task 路径下异常被记录 WARNING 日志"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(event_listener=listener)

        async def failing_coro() -> None:
            raise RuntimeError("async error logged")

        with caplog.at_level(logging.WARNING):
            handler._run_async(failing_coro())
            await asyncio.sleep(0.05)

        assert "异步任务执行失败" in caplog.text

    # ===================================================================
    # 回调包装（同步回调 + _run_async 集成）
    # ===================================================================

    def test_wrapped_callback_handles_validity_event(self) -> None:
        """包装回调正确处理 ValidityPeriodSet"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(event_listener=listener)
        handler.register_handlers()
        validity_cb = None
        for call in listener.on_event.call_args_list:
            if call.args[0] == "ValidityPeriodSet":
                validity_cb = call.args[1]
                break
        assert validity_cb is not None
        event = ValidityPeriodSet(archive_id=uuid.uuid4())
        validity_cb(event)

    def test_wrapped_callback_handles_fact_stale(self) -> None:
        """包装回调正确处理 FactBecameStale"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(event_listener=listener)
        handler.register_handlers()
        stale_cb = None
        for call in listener.on_event.call_args_list:
            if call.args[0] == "FactBecameStale":
                stale_cb = call.args[1]
                break
        assert stale_cb is not None
        event = FactBecameStale(archive_id=uuid.uuid4(), stale_reason="expired")
        stale_cb(event)

    def test_wrapped_callback_swallows_unknown_event(self) -> None:
        """未知事件类型被安全忽略"""
        from src.domain.events.base import DomainEvent

        listener = _make_listener()
        handler = ArchiveValidityHandler(event_listener=listener)
        handler.register_handlers()
        validity_cb = None
        for call in listener.on_event.call_args_list:
            if call.args[0] == "ValidityPeriodSet":
                validity_cb = call.args[1]
                break
        unknown = DomainEvent(event_type="UnknownEvent")
        assert validity_cb is not None
        validity_cb(unknown)

    def test_handle_fact_became_stale_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """FactBecameStale 事件处理记录日志"""
        listener = _make_listener()
        handler = ArchiveValidityHandler(event_listener=listener)
        event = FactBecameStale(
            archive_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            archive_type=ArchiveType.ASSUMPTION,
            valid_until=None,
            stale_reason="archived_too_long",
        )
        with caplog.at_level(logging.INFO, logger="src.application.event_handlers.archive_handlers"):
            handler._handle_fact_became_stale(event)
        assert "Fact became stale for archive" in caplog.text
        assert "archived_too_long" in caplog.text
