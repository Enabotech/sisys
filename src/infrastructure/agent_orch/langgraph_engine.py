"""基础设施层 LangGraph 引擎适配器模块

LangGraphEngine 实现 AgentEnginePort Protocol，封装 LangGraph SDK 调用
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph

from src.domain.value_objects.flow_status import FlowStatus
from src.infrastructure.config.langgraph import LangGraphConfig

if TYPE_CHECKING:
    from src.domain.ports.event_publisher import EventPublisher

logger = logging.getLogger(__name__)


class LangGraphEngine:
    """AgentEnginePort 的 LangGraph 实现

    负责状态图生命周期管理（提交、状态查询、事件发布）
    所有 LangGraph SDK 导入限定于此模块及子模块

    Args:
        config: LangGraph 连接配置
        event_publisher: 事件发布端口（通过构造函数注入）
    """

    # 运行记录淘汰策略
    _MAX_RUNS = 1000
    _RUNS_TTL_SECONDS = 3600  # 1 小时

    def __init__(self, config: LangGraphConfig, event_publisher: EventPublisher) -> None:
        self._config = config
        self._event_publisher = event_publisher
        self._checkpointer = InMemorySaver()
        self._runs: OrderedDict[str, tuple[FlowStatus, float]] = OrderedDict()

    async def submit_graph(self, graph_name: str, parameters: dict[str, Any]) -> str:
        """提交 Agent 状态图执行

        构建 StateGraph、编译并执行，返回运行标识符
        MVP 阶段为阻塞执行（ainvoke 等待完成）
        完成后发布 AgentDecided 事件

        Args:
            graph_name: 状态图名称（如 "BasicAgent"）
            parameters: 状态图参数（需包含 task_description）

        Returns:
            graph_run_id: 状态图运行标识符

        Raises:
            ValueError: graph_name 为空或 parameters 为空
            RuntimeError: LangGraph SDK 调用失败
        """
        if not graph_name:
            raise ValueError("graph_name 不能为空")
        if not parameters:
            raise ValueError("parameters 不能为空")

        run_id = str(uuid.uuid4())
        agent_id = uuid.uuid4()

        try:
            compiled_graph = self._build_graph(graph_name, parameters)
            result = await compiled_graph.ainvoke(parameters, config={"configurable": {"thread_id": run_id}})
        except Exception as e:
            self._runs[run_id] = (FlowStatus.FAILED, time.monotonic())
            raise RuntimeError(f"提交状态图失败 [{graph_name}]: {e}") from e

        self._runs[run_id] = (FlowStatus.COMPLETED, time.monotonic())
        self._cleanup_runs()

        # 事件发布独立于图执行状态，失败不回写 FAILED
        try:
            await self._publish_agent_decided(agent_id, result, run_id)
        except Exception:
            logger.exception("AgentDecided 事件发布异常 [run_id=%s]", run_id)

        return run_id

    async def get_graph_status(self, graph_run_id: str) -> FlowStatus:
        """查询状态图执行状态

        Args:
            graph_run_id: 状态图运行标识符

        Returns:
            FlowStatus 枚举值

        Raises:
            ValueError: graph_run_id 为空
        """
        if not graph_run_id:
            raise ValueError("graph_run_id 不能为空")

        return self._runs.get(graph_run_id, (FlowStatus.FAILED, 0.0))[0]

    _SUPPORTED_GRAPHS = {"BasicAgent"}

    def _build_graph(self, graph_name: str, parameters: dict[str, Any]) -> Any:
        """构建并编译状态图

        根据 graph_name 选择对应的图定义，编译后返回可执行图
        MVP 阶段仅支持 BasicAgent，不支持的名称记录警告日志

        Args:
            graph_name: 状态图名称
            parameters: 状态图参数

        Returns:
            编译后的 CompiledStateGraph
        """
        if graph_name not in self._SUPPORTED_GRAPHS:
            logger.warning(
                "未知的 graph_name '%s'，当前仅支持 %s，将使用 BasicAgent",
                graph_name,
                self._SUPPORTED_GRAPHS,
            )

        from src.infrastructure.agent_orch.graphs.basic_agent_graph import (
            BasicAgentState,
            build_basic_agent_graph,
        )

        graph = StateGraph(BasicAgentState)
        graph_builder = build_basic_agent_graph(graph)
        return graph_builder.compile(checkpointer=self._checkpointer)

    async def _publish_agent_decided(self, agent_id: uuid.UUID, result: dict[str, Any], run_id: str) -> None:
        """发布 AgentDecided 领域事件

        Args:
            agent_id: Agent 唯一标识符
            result: 状态图执行结果
            run_id: 运行标识符
        """
        from src.domain.events.agent_events import AgentDecided

        event = AgentDecided(
            agent_id=agent_id,
            decision_result=result,
            confidence=0.9,
        )
        publish_result = await self._event_publisher.publish(event)
        if publish_result is None:
            logger.warning("AgentDecided 事件发布返回 None [run_id=%s]", run_id)
        elif publish_result.is_full_failure:
            logger.warning(
                "AgentDecided 事件发布全部失败 [run_id=%s]: %s",
                run_id,
                publish_result,
            )

    def _cleanup_runs(self) -> None:
        """淘汰过期和超量的运行记录

        策略：TTL 过期 + FIFO 超量淘汰，保证 _runs 不会无限增长
        """
        now = time.monotonic()
        # TTL 淘汰：移除超过 _RUNS_TTL_SECONDS 的记录
        expired = [k for k, (_, ts) in self._runs.items() if now - ts > self._RUNS_TTL_SECONDS]
        for k in expired:
            del self._runs[k]
        # FIFO 淘汰：超过 _MAX_RUNS 时移除最早的记录
        while len(self._runs) > self._MAX_RUNS:
            self._runs.popitem(last=False)
