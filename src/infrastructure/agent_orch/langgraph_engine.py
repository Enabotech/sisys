"""基础设施层 LangGraph 引擎适配器模块

LangGraphEngine 实现 AgentEnginePort Protocol，封装 LangGraph SDK 调用
（Story 1.18b 底座；Story 5-3 扩展：SingleAgentWorkflow 图分派 + agent_id
收敛 + confidence 真实化 + get_graph_result 结果取回 + DomainError 透传）。
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph

from src.domain.exceptions import DomainError, ValidationError
from src.domain.value_objects.flow_status import FlowStatus
from src.infrastructure.config.langgraph import LangGraphConfig

if TYPE_CHECKING:
    from src.application.ports.agent_workflow import AgentWorkflowServicePort
    from src.domain.ports.event_publisher import EventPublisher

logger = logging.getLogger(__name__)


class LangGraphEngine:
    """AgentEnginePort 的 LangGraph 实现

    负责状态图生命周期管理（提交、状态查询、事件发布、终态结果取回）
    所有 LangGraph SDK 导入限定于此模块及子模块

    Args:
        config: LangGraph 连接配置
        event_publisher: 事件发布端口（通过构造函数注入）
        workflow_service: 六阶段工作流服务端口（Story 5-3——默认 None 保持
            BasicAgent 向后兼容；SingleAgentWorkflow 图的节点适配器数据源）
    """

    # 运行记录淘汰策略
    _MAX_RUNS = 1000
    _RUNS_TTL_SECONDS = 3600  # 1 小时

    def __init__(
        self,
        config: LangGraphConfig,
        event_publisher: EventPublisher,
        workflow_service: AgentWorkflowServicePort | None = None,
    ) -> None:
        self._config = config
        self._event_publisher = event_publisher
        self._workflow_service = workflow_service
        self._checkpointer = InMemorySaver()
        # 运行记录：run_id → (FlowStatus, monotonic 时间戳, 终态 state | None)
        # ——Story 5-3 扩展第三位存终态 state（get_graph_result 数据源，
        # DC-11；失败路径无终态 state 为 None）
        self._runs: OrderedDict[str, tuple[FlowStatus, float, dict[str, Any] | None]] = OrderedDict()

    async def submit_graph(self, graph_name: str, parameters: dict[str, Any]) -> str:
        """提交 Agent 状态图执行

        构建 StateGraph、编译并执行，返回运行标识符
        MVP 阶段为阻塞执行（ainvoke 等待完成）
        完成后发布 AgentDecided 事件

        Args:
            graph_name: 状态图名称（如 "BasicAgent" / "SingleAgentWorkflow"）
            parameters: 状态图参数（需包含 task_description；SingleAgentWorkflow
                需包含 agent_id/task/context）

        Returns:
            graph_run_id: 状态图运行标识符

        Raises:
            ValidationError: graph_name 为空或 parameters 为空
            DomainError: 图执行抛出的领域异常原样透传（Story 5-3——444/445
                端到端可达前提，不再被 RuntimeError 改写）
            RuntimeError: LangGraph SDK 调用失败（非 DomainError）
        """
        if not graph_name:
            raise ValidationError(message="graph_name 不能为空")
        if not parameters:
            raise ValidationError(message="parameters 不能为空")

        run_id = str(uuid.uuid4())
        # agent_id 收敛（Story 5-3——DC-5）：parameters 传入实体 agent_id 时
        # 复用（str→UUID 构造），缺失回退自铸保 BasicAgent 兼容——AgentDecided
        # 的 aggregate_id 与 AgentProfileLoaded 可按实体 id 关联（5-2 风险 #2 核销）
        agent_id_raw = parameters.get("agent_id")
        if agent_id_raw is None:
            # 缺失回退自铸（BasicAgent 兼容——存量路径不受守卫影响）
            agent_id = uuid.uuid4()
        else:
            # 收敛位守卫（R1-F4）：键存在但非法（非 str 类型/空串/畸形串——裸
            # uuid.UUID 会抛内置 ValueError/AttributeError 逃逸异常体系）→
            # 统一 201（参数校验位先于 run 记录，与 graph_name/parameters 守卫
            # 同款；DC-5 钦定调用方 str 序列化，UUID 实例直塞拒绝）
            if not isinstance(agent_id_raw, str) or not agent_id_raw.strip():
                raise ValidationError(
                    message=f"parameters.agent_id 必须为非空 UUID 字符串（str 序列化——DC-5）: {agent_id_raw!r}"
                )
            try:
                agent_id = uuid.UUID(agent_id_raw)
            except ValueError as error:
                raise ValidationError(message=f"parameters.agent_id 非法 UUID 字符串: {agent_id_raw!r}") from error

        try:
            compiled_graph = self._build_graph(graph_name, parameters)
            result = await compiled_graph.ainvoke(parameters, config={"configurable": {"thread_id": run_id}})
        except DomainError:
            # 领域异常原样透传（444/445 等统一异常体系——CLI stderr 编码可达）
            self._runs[run_id] = (FlowStatus.FAILED, time.monotonic(), None)
            self._cleanup_runs()
            raise
        except Exception as e:
            self._runs[run_id] = (FlowStatus.FAILED, time.monotonic(), None)
            self._cleanup_runs()
            raise RuntimeError(f"提交状态图失败 [{graph_name}]: {e}") from e

        self._runs[run_id] = (FlowStatus.COMPLETED, time.monotonic(), result)
        self._cleanup_runs()

        # 事件发布独立于图执行状态，失败不回写 FAILED
        try:
            await self._publish_agent_decided(agent_id, result, run_id, graph_name)
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
            ValidationError: graph_run_id 为空
        """
        if not graph_run_id:
            raise ValidationError(message="graph_run_id 不能为空")

        return self._runs.get(graph_run_id, (FlowStatus.FAILED, 0.0, None))[0]

    async def get_graph_result(self, graph_run_id: str) -> dict[str, Any] | None:
        """取回状态图终态 state（Story 5-3——DC-11 既有端口追加方法）

        用例/CLI 的结果组装数据源（AgentWorkflowResult 五字段与摘要输出在
        端口面的数据来源——ainvoke 终态 state 同步存 _runs 第三位）。

        Args:
            graph_run_id: 状态图运行标识符

        Returns:
            终态 state dict；未知/过期 id 或失败路径（无终态）返回 None
            ——与 get_graph_status 的 FAILED 默认语义区分

        Raises:
            ValidationError: graph_run_id 为空
        """
        if not graph_run_id:
            raise ValidationError(message="graph_run_id 不能为空")

        return self._runs.get(graph_run_id, (FlowStatus.FAILED, 0.0, None))[2]

    _SUPPORTED_GRAPHS = {"BasicAgent", "SingleAgentWorkflow"}

    def _build_graph(self, graph_name: str, parameters: dict[str, Any]) -> Any:
        """构建并编译状态图

        根据 graph_name 选择对应的图定义，编译后返回可执行图
        （SingleAgentWorkflow 分派到六阶段图工厂——需 workflow_service 注入；
        不支持的名称记录警告日志并回退 BasicAgent——注册遗漏由验收图身份锚
        断言抓红）

        Args:
            graph_name: 状态图名称
            parameters: 状态图参数

        Returns:
            编译后的 CompiledStateGraph
        """
        if graph_name == "SingleAgentWorkflow":
            if self._workflow_service is None:
                raise ValidationError(message="SingleAgentWorkflow 图需要 workflow_service 注入（组合根 lambda 注入位）")
            from src.infrastructure.agent_orch.graphs.single_agent_workflow_graph import (
                build_single_agent_workflow_graph,
            )

            return build_single_agent_workflow_graph(self._workflow_service)

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

    async def _publish_agent_decided(
        self, agent_id: uuid.UUID, result: dict[str, Any], run_id: str, graph_name: str = ""
    ) -> None:
        """发布 AgentDecided 领域事件

        confidence 真实化（Story 5-3——DC-6）：从终态 state 取验证置信度
        （`state.get("confidence", 0.9)` 双默认——BasicAgent 存量断言 0.9 保持
        绿，范围仅新图）；SingleAgentWorkflow 路径 decision_result 为五键纯
        标量投影（VO 实例禁入 dict——JSON 序列化炸，4-5 UUID 直塞 metadata
        教训），BasicAgent 路径保持 state 全量透传不变。

        投影判别按图名身份（R1-F12：原「evidence in state」键存在性判别脆弱
        ——未来 BasicAgent 扩键即误投影，新图改键名则 VO 实例漏入事件 dict）。

        Args:
            agent_id: Agent 唯一标识符（parameters 传入实体 id 或回退自铸）
            result: 状态图执行终态 state
            run_id: 运行标识符
            graph_name: 状态图名称（投影判别锚——SingleAgentWorkflow 走五键投影）
        """
        from src.domain.events.agent_events import AgentDecided

        decision_result: dict[str, Any] = result
        if graph_name == "SingleAgentWorkflow" and isinstance(result, dict):
            evidence = result.get("evidence")
            chain = result.get("chain")
            # 五键纯标量投影（R3-F5：workflow_status 与 evidence.status/DTO/CLI 四轨同源）
            decision_result = {
                "workflow_status": getattr(evidence, "status", ""),
                "task_summary": (getattr(chain, "input_summary", "") or "")[:200],
                "chain_summary": (getattr(chain, "final_answer", "") or "")[:200],
                "evidence_ref": getattr(evidence, "input_hash", ""),
                "retry_count": result.get("retry_count", 0),
            }

        event = AgentDecided(
            agent_id=agent_id,
            decision_result=decision_result,
            confidence=result.get("confidence", 0.9) if isinstance(result, dict) else 0.9,
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
        expired = [k for k, (_, ts, _) in self._runs.items() if now - ts > self._RUNS_TTL_SECONDS]
        for k in expired:
            del self._runs[k]
        # FIFO 淘汰：超过 _MAX_RUNS 时移除最早的记录
        while len(self._runs) > self._MAX_RUNS:
            self._runs.popitem(last=False)
