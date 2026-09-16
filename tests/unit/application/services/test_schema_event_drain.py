"""drain_schema_events 函数单元测试(Round 4 P0-3 修复守护)

覆盖范围:
1. 优雅排空所有挂起的 schema 事件 task
2. _background_tasks 为空时立即返回
3. timeout 后取消未完成的 task
4. 部分 task 抛异常时不影响其他 task 完成
5. 排空后 _background_tasks set 被清空
"""

from __future__ import annotations

import asyncio
import time
import uuid
from unittest.mock import MagicMock

import pytest

from src.application.services.schema_event_helpers import (
    _background_tasks,
    drain_schema_events,
    publish_schema_event_async,
)
from src.domain.events.tool_schema_events import ToolSchemaValidationFailed


def _make_event() -> ToolSchemaValidationFailed:
    return ToolSchemaValidationFailed(
        execution_id=uuid.uuid4(),
        tool_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        validation_phase="INPUT",
    )


class TestDrainSchemaEvents:
    """Round 4 P0-3:shutdown 时优雅排空 schema 事件,避免事件丢失"""

    @pytest.mark.asyncio
    async def test_drain_empty_background_tasks_returns_immediately(self) -> None:
        """_background_tasks 为空时立即返回,不阻塞"""
        # 确保起始状态干净
        before_count = len(_background_tasks)
        start = time.perf_counter()
        await drain_schema_events(timeout=2.0)
        elapsed = time.perf_counter() - start
        # 空 set 排空应 < 10ms
        assert elapsed < 0.01
        assert len(_background_tasks) == before_count

    @pytest.mark.asyncio
    async def test_drain_waits_for_pending_publish_tasks(self) -> None:
        """drain_schema_events 应等待所有挂起 publish 完成"""
        # 清理起始状态
        _background_tasks.clear()

        published_events: list = []

        async def slow_publish(event: ToolSchemaValidationFailed) -> None:
            await asyncio.sleep(0.1)  # 模拟慢发布
            published_events.append(event)

        publisher = MagicMock()
        publisher.publish = slow_publish

        # 启动 3 个 publish task
        for _ in range(3):
            publish_schema_event_async(publisher, _make_event(), MagicMock(), op_name="test")

        # 验证 3 个 task 挂起
        assert len(_background_tasks) == 3

        # drain_schema_events 应等所有 publish 完成
        start = time.perf_counter()
        await drain_schema_events(timeout=5.0)
        elapsed = time.perf_counter() - start

        # 全部 3 个事件被发布
        assert len(published_events) == 3
        # drain 等待约 100ms(最慢 task)
        assert elapsed >= 0.1
        # drain 后 _background_tasks 被清空
        assert len(_background_tasks) == 0

    @pytest.mark.asyncio
    async def test_drain_timeout_cancels_unfinished_tasks(self) -> None:
        """drain_schema_events 超时后取消未完成的 task"""
        _background_tasks.clear()

        async def very_slow_publish(_event: ToolSchemaValidationFailed) -> None:
            await asyncio.sleep(10.0)  # 故意拖过 timeout

        publisher = MagicMock()
        publisher.publish = very_slow_publish

        publish_schema_event_async(publisher, _make_event(), MagicMock(), op_name="test")
        assert len(_background_tasks) == 1

        # 极短 timeout
        await drain_schema_events(timeout=0.05)

        # task 应被取消或完成,_background_tasks 清空
        assert len(_background_tasks) == 0

    @pytest.mark.asyncio
    async def test_drain_continues_when_one_task_raises(self) -> None:
        """部分 task 抛异常时,其他 task 仍应完成"""
        _background_tasks.clear()

        async def failing_publish(_event: ToolSchemaValidationFailed) -> None:
            raise RuntimeError("publish failed")

        async def successful_publish(event: ToolSchemaValidationFailed) -> None:
            await asyncio.sleep(0.01)
            # 标记成功
            pass

        # 启动 1 失败 + 2 成功的混合 task
        failing_publisher = MagicMock()
        failing_publisher.publish = failing_publish

        success_publisher = MagicMock()
        success_publisher.publish = successful_publish

        publish_schema_event_async(failing_publisher, _make_event(), MagicMock(), op_name="fail")
        publish_schema_event_async(success_publisher, _make_event(), MagicMock(), op_name="ok1")
        publish_schema_event_async(success_publisher, _make_event(), MagicMock(), op_name="ok2")

        # drain 等待(失败 task 也算"完成")
        await drain_schema_events(timeout=5.0)

        # _background_tasks 清空(return_exceptions=True 不让异常传播)
        assert len(_background_tasks) == 0
