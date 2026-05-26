"""LangGraphEngine 单元测试

验证 submit_graph/get_graph_status、状态映射、AgentEnginePort 一致性
使用 mock LangGraph SDK，不启动真实 server
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.value_objects.flow_status import FlowStatus
from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
from src.infrastructure.config.langgraph import LangGraphConfig


@pytest.fixture
def mock_event_publisher() -> AsyncMock:
    publisher = AsyncMock()
    publish_result = AsyncMock()
    publish_result.is_full_failure = False
    publisher.publish = AsyncMock(return_value=publish_result)
    return publisher


@pytest.fixture
def config() -> LangGraphConfig:
    return LangGraphConfig()


@pytest.fixture
def engine(config: LangGraphConfig, mock_event_publisher: AsyncMock) -> LangGraphEngine:
    return LangGraphEngine(config, mock_event_publisher)


class TestLangGraphEngineProtocolCompliance:
    """LangGraphEngine 满足 AgentEnginePort Protocol"""

    def test_is_agent_engine_port(self, engine: LangGraphEngine) -> None:
        from src.domain.ports.agent_engine import AgentEnginePort

        assert isinstance(engine, AgentEnginePort)


class TestLangGraphEngineSubmitGraph:
    """submit_graph 测试"""

    async def test_submit_graph_returns_string_id(self, engine: LangGraphEngine) -> None:
        """submit_graph 应返回 graph_run_id 字符串"""
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "test task",
                "agent_role": "analyst",
                "analysis_result": "分析完成",
                "synthesis_result": "综合完成",
            }
        )

        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            result = await engine.submit_graph(
                "BasicAgent",
                {"task_description": "test task", "agent_role": "analyst"},
            )

        assert isinstance(result, str)
        assert len(result) > 0

    async def test_submit_graph_rejects_empty_graph_name(self, engine: LangGraphEngine) -> None:
        """空 graph_name 应抛出 ValueError"""
        with pytest.raises(ValueError, match="graph_name"):
            await engine.submit_graph("", {})

    async def test_submit_graph_rejects_empty_parameters(self, engine: LangGraphEngine) -> None:
        """空 parameters 应抛出 ValueError"""
        with pytest.raises(ValueError, match="parameters"):
            await engine.submit_graph("BasicAgent", {})

    async def test_submit_graph_runtime_error_on_exception(self, engine: LangGraphEngine) -> None:
        """SDK 异常应转换为 RuntimeError"""
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(side_effect=Exception("SDK error"))

        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            with pytest.raises(RuntimeError, match="提交状态图失败"):
                await engine.submit_graph("BasicAgent", {"task_description": "test"})


class TestLangGraphEngineEventPublishing:
    """AgentDecided 事件发布测试"""

    async def test_submit_graph_publishes_agent_decided(self, engine: LangGraphEngine, mock_event_publisher: AsyncMock) -> None:
        """submit_graph 完成后应发布 AgentDecided 事件"""
        from src.domain.events.agent_events import AgentDecided

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "test",
                "agent_role": "analyst",
                "analysis_result": "分析完成",
                "synthesis_result": "综合完成",
            }
        )

        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            await engine.submit_graph("BasicAgent", {"task_description": "test"})

        mock_event_publisher.publish.assert_called_once()
        event = mock_event_publisher.publish.call_args[0][0]
        assert isinstance(event, AgentDecided)
        assert event.confidence == 0.9

    async def test_submit_graph_no_event_on_failure(self, engine: LangGraphEngine, mock_event_publisher: AsyncMock) -> None:
        """submit_graph 失败时不应发布事件"""
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(side_effect=Exception("SDK error"))

        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            with pytest.raises(RuntimeError):
                await engine.submit_graph("BasicAgent", {"task_description": "test"})

        mock_event_publisher.publish.assert_not_called()

    async def test_submit_graph_remains_completed_on_publish_exception(
        self, engine: LangGraphEngine, mock_event_publisher: AsyncMock
    ) -> None:
        """事件发布异常不应覆写 COMPLETED 状态"""
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "test",
                "agent_role": "analyst",
                "analysis_result": "分析完成",
                "synthesis_result": "综合完成",
            }
        )
        mock_event_publisher.publish = AsyncMock(side_effect=ConnectionError("network"))

        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            run_id = await engine.submit_graph("BasicAgent", {"task_description": "test"})

        status = await engine.get_graph_status(run_id)
        assert status == FlowStatus.COMPLETED

    async def test_submit_graph_handles_publish_returning_none(
        self, engine: LangGraphEngine, mock_event_publisher: AsyncMock
    ) -> None:
        """publish 返回 None 时应记录警告但不影响状态"""
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "test",
                "agent_role": "analyst",
                "analysis_result": "分析完成",
                "synthesis_result": "综合完成",
            }
        )
        mock_event_publisher.publish = AsyncMock(return_value=None)

        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            run_id = await engine.submit_graph("BasicAgent", {"task_description": "test"})

        status = await engine.get_graph_status(run_id)
        assert status == FlowStatus.COMPLETED

    async def test_submit_graph_logs_warning_on_full_failure(
        self, engine: LangGraphEngine, mock_event_publisher: AsyncMock
    ) -> None:
        """publish 返回 is_full_failure=True 时应记录警告"""
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "test",
                "agent_role": "analyst",
                "analysis_result": "分析完成",
                "synthesis_result": "综合完成",
            }
        )
        publish_result = AsyncMock()
        publish_result.is_full_failure = True
        mock_event_publisher.publish = AsyncMock(return_value=publish_result)

        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            run_id = await engine.submit_graph("BasicAgent", {"task_description": "test"})

        status = await engine.get_graph_status(run_id)
        assert status == FlowStatus.COMPLETED


class TestLangGraphEngineGetGraphStatus:
    """get_graph_status 测试"""

    async def test_get_graph_status_completed(self, engine: LangGraphEngine) -> None:
        """已完成的 run_id 返回 COMPLETED"""
        run_id = str(uuid.uuid4())
        # 模拟 submit_graph 将结果存入 _runs
        engine._runs[run_id] = (FlowStatus.COMPLETED, 0.0)

        status = await engine.get_graph_status(run_id)
        assert status == FlowStatus.COMPLETED

    async def test_get_graph_status_failed(self, engine: LangGraphEngine) -> None:
        """失败的 run_id 返回 FAILED"""
        run_id = str(uuid.uuid4())
        engine._runs[run_id] = (FlowStatus.FAILED, 0.0)

        status = await engine.get_graph_status(run_id)
        assert status == FlowStatus.FAILED

    async def test_get_graph_status_rejects_empty_id(self, engine: LangGraphEngine) -> None:
        """空 graph_run_id 应抛出 ValueError"""
        with pytest.raises(ValueError, match="graph_run_id"):
            await engine.get_graph_status("")

    async def test_get_graph_status_unknown_id_returns_failed(self, engine: LangGraphEngine) -> None:
        """未知 run_id 返回 FAILED"""
        status = await engine.get_graph_status(str(uuid.uuid4()))
        assert status == FlowStatus.FAILED


class TestLangGraphEngineRunsEviction:
    """_runs 字典淘汰机制测试"""

    async def test_cleanup_evicts_expired_entries(self, engine: LangGraphEngine) -> None:
        """TTL 过期的记录应被淘汰"""
        run_id = str(uuid.uuid4())
        # 插入一条 timestamp=0 的过期记录（epoch 起点，远超 TTL）
        engine._runs[run_id] = (FlowStatus.COMPLETED, 0.0)

        # 触发一次 submit_graph 以执行 _cleanup_runs
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "t",
                "agent_role": "a",
                "analysis_result": "r",
                "synthesis_result": "s",
            }
        )
        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            await engine.submit_graph("BasicAgent", {"task_description": "test"})

        # 过期记录应被淘汰
        assert run_id not in engine._runs

    async def test_cleanup_keeps_fresh_entries(self, engine: LangGraphEngine) -> None:
        """未过期的记录应保留"""
        run_id = str(uuid.uuid4())
        engine._runs[run_id] = (FlowStatus.COMPLETED, time.monotonic())

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "t",
                "agent_role": "a",
                "analysis_result": "r",
                "synthesis_result": "s",
            }
        )
        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            await engine.submit_graph("BasicAgent", {"task_description": "test"})

        # 新鲜记录应保留
        assert run_id in engine._runs

    async def test_max_size_fifo_eviction(self) -> None:
        """超过 max_size 时 FIFO 淘汰最早记录"""
        config = LangGraphConfig()
        publisher = AsyncMock()
        publish_result = AsyncMock()
        publish_result.is_full_failure = False
        publisher.publish = AsyncMock(return_value=publish_result)
        engine = LangGraphEngine(config, publisher)
        engine._MAX_RUNS = 3

        now = time.monotonic()
        # 手动填满 _runs 到 max_size
        engine._runs["old-1"] = (FlowStatus.COMPLETED, now)
        engine._runs["old-2"] = (FlowStatus.COMPLETED, now)
        engine._runs["old-3"] = (FlowStatus.COMPLETED, now)

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke = AsyncMock(
            return_value={
                "task_description": "t",
                "agent_role": "a",
                "analysis_result": "r",
                "synthesis_result": "s",
            }
        )
        with patch.object(engine, "_build_graph", return_value=mock_compiled):
            await engine.submit_graph("BasicAgent", {"task_description": "test"})

        # 最早记录应被淘汰
        assert "old-1" not in engine._runs
        # 较新记录保留
        assert "old-2" in engine._runs
        assert len(engine._runs) <= engine._MAX_RUNS
