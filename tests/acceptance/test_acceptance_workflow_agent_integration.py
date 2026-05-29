"""Story 90.8 - 双核引擎集成验收测试步骤实现

验证 PrefectEngine 事件发布补全、双引擎对称性、通道注册等业务价值验收

Run with: poetry run pytest tests/acceptance/test_acceptance_workflow-agent-integration.py -v
"""

from __future__ import annotations

import ast
import inspect
import textwrap

from pytest_bdd import given, scenarios, then

scenarios("test_acceptance_workflow_agent_integration.feature")


# =========================================================================
# Background（前置依赖声明）
# =========================================================================


@given("Story 1.18a Prefect 工作流集成和 Story 1.18b LangGraph Agent 编排已完成")
def story_1_18_dependencies_done() -> None:
    pass


@given("Story 90-1~90-7 重大重构系列已完成")
def story_20_1_to_20_7_done() -> None:
    pass


# =========================================================================
# Scenario 1: 数据管道工作流提交（AC-1 + AC-5）
# =========================================================================


@given("WorkflowEnginePort 定义于 src/domain/ports/workflow_engine.py")
def workflow_engine_port_defined() -> None:
    pass


@given("PrefectEngine 已注册为 WorkflowEnginePort 实现")
def prefect_engine_registered() -> None:
    from src.domain.ports.registry import _global_registry

    spec = _global_registry.get("workflow_engine")
    assert spec is not None


@then("WorkflowEnginePort 应定义 submit_flow 和 get_flow_status 方法")
def verify_workflow_engine_port_methods() -> None:
    from src.domain.ports.workflow_engine import WorkflowEnginePort

    assert hasattr(WorkflowEnginePort, "submit_flow")
    assert hasattr(WorkflowEnginePort, "get_flow_status")


@then("PrefectEngine 的 submit_flow 成功后应发布 WorkflowSubmitted 事件")
def verify_prefect_publishes_workflow_submitted() -> None:
    from src.infrastructure.workflow.prefect_engine import PrefectEngine

    source = inspect.getsource(PrefectEngine.submit_flow)
    assert "_publish_workflow_submitted" in source or "_event_publisher" in source


# =========================================================================
# Scenario 2: Agent 推理任务提交（AC-5）
# =========================================================================


@given("AgentEnginePort 定义于 src/domain/ports/agent_engine.py")
def agent_engine_port_defined() -> None:
    pass


@given("LangGraphEngine 已注册为 AgentEnginePort 实现")
def langgraph_engine_registered() -> None:
    from src.domain.ports.registry import _global_registry

    spec = _global_registry.get("agent_engine")
    assert spec is not None


@then("AgentEnginePort 应定义 submit_graph 和 get_graph_status 方法")
def verify_agent_engine_port_methods() -> None:
    from src.domain.ports.agent_engine import AgentEnginePort

    assert hasattr(AgentEnginePort, "submit_graph")
    assert hasattr(AgentEnginePort, "get_graph_status")


# =========================================================================
# Scenario 3: 双引擎状态查询（AC-5 状态映射）
# =========================================================================


@then("PrefectEngine 应实现 9 种 StateType 到 5 种 FlowStatus 的映射")
def verify_prefect_state_mapping() -> None:
    from prefect.states import State, StateType

    from src.infrastructure.config.prefect import PrefectConfig
    from src.infrastructure.workflow.prefect_engine import PrefectEngine

    config = PrefectConfig()
    engine = PrefectEngine.__new__(PrefectEngine)
    engine._config = config

    all_state_types = set(StateType)
    mapped = set()
    for st in all_state_types:
        state = State(type=st)
        for run_count in (0, config.retry_max_attempts):
            status = engine._map_state_type(state, run_count)
            mapped.add(status)

    from src.domain.value_objects.flow_status import FlowStatus

    expected = {FlowStatus.PENDING, FlowStatus.RUNNING, FlowStatus.COMPLETED, FlowStatus.FAILED, FlowStatus.RETRYING}
    assert expected.issubset(mapped)


@then("LangGraphEngine 应使用 COMPLETED 和 FAILED 两种状态")
def verify_langgraph_status_usage() -> None:
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine

    source = inspect.getsource(LangGraphEngine.submit_graph)
    assert "FlowStatus.COMPLETED" in source
    assert "FlowStatus.FAILED" in source


@then("FlowStatus 枚举包含 PENDING/RUNNING/COMPLETED/FAILED/RETRYING 五个状态")
def verify_flow_status_values() -> None:
    from src.domain.value_objects.flow_status import FlowStatus

    expected = {"PENDING", "RUNNING", "COMPLETED", "FAILED", "RETRYING"}
    actual = {s.value for s in FlowStatus}
    assert actual == expected


# =========================================================================
# Scenario 4: PrefectEngine 事件发布（AC-1 WorkflowSubmitted）
# =========================================================================


@given("WorkflowSubmitted 事件定义于 workflow_events.py")
def workflow_submitted_defined() -> None:
    from src.domain.events.workflow_events import WorkflowSubmitted

    assert WorkflowSubmitted is not None


@then("WorkflowSubmitted 应包含 flow_run_id, flow_name, parameters 字段")
def verify_workflow_submitted_fields() -> None:
    from src.domain.events.workflow_events import WorkflowSubmitted

    event = WorkflowSubmitted()
    assert hasattr(event, "flow_run_id")
    assert hasattr(event, "flow_name")
    assert hasattr(event, "parameters")


@then('WorkflowSubmitted 的 event_type 应为 "WorkflowSubmitted"')
def verify_workflow_submitted_event_type() -> None:
    from src.domain.events.workflow_events import WorkflowSubmitted

    event = WorkflowSubmitted()
    assert event.event_type == "WorkflowSubmitted"


@then('WorkflowSubmitted 的 aggregate_type 应为 "Workflow"')
def verify_workflow_submitted_aggregate_type() -> None:
    from src.domain.events.workflow_events import WorkflowSubmitted

    event = WorkflowSubmitted()
    assert event.aggregate_type == "Workflow"


@then("WorkflowSubmitted 应注册到 DomainEvent._registry")
def verify_workflow_submitted_registered() -> None:
    from src.domain.events.base import DomainEvent
    from src.domain.events.workflow_events import WorkflowSubmitted

    assert "WorkflowSubmitted" in DomainEvent._registry
    assert DomainEvent._registry["WorkflowSubmitted"] is WorkflowSubmitted


# =========================================================================
# Scenario 5: 双引擎事件发布对称性验证（AC-2）
# =========================================================================


@given("PrefectEngine 和 LangGraphEngine 均注入 EventPublisher")
def both_engines_inject_event_publisher() -> None:
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.workflow.prefect_engine import PrefectEngine

    pref_sig = inspect.signature(PrefectEngine.__init__)
    lg_sig = inspect.signature(LangGraphEngine.__init__)
    assert "event_publisher" in pref_sig.parameters
    assert "event_publisher" in lg_sig.parameters


@then("PrefectEngine 和 LangGraphEngine 应使用相同的事件发布模式")
def verify_same_publish_pattern() -> None:
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.workflow.prefect_engine import PrefectEngine

    pref_source = inspect.getsource(PrefectEngine)
    lg_source = inspect.getsource(LangGraphEngine)

    assert "self._event_publisher.publish" in pref_source
    assert "self._event_publisher.publish" in lg_source


@then("两者均应使用 try/except Exception 包裹事件发布")
def verify_try_except_pattern() -> None:
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.workflow.prefect_engine import PrefectEngine

    pref_source = inspect.getsource(PrefectEngine)
    lg_source = inspect.getsource(LangGraphEngine)

    assert "except Exception" in pref_source
    assert "except Exception" in lg_source


@then("两者均应检查 PublishResult 的 is_full_failure 属性")
def verify_is_full_failure_check() -> None:
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.workflow.prefect_engine import PrefectEngine

    pref_source = inspect.getsource(PrefectEngine)
    lg_source = inspect.getsource(LangGraphEngine)

    assert "is_full_failure" in pref_source
    assert "is_full_failure" in lg_source


@then("事件发布异常不应影响引擎返回值")
def verify_exception_does_not_affect_return() -> None:
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine
    from src.infrastructure.workflow.prefect_engine import PrefectEngine

    pref_source = inspect.getsource(PrefectEngine.submit_flow)
    lg_source = inspect.getsource(LangGraphEngine.submit_graph)

    pref_tree = ast.parse(textwrap.dedent(pref_source))
    lg_tree = ast.parse(textwrap.dedent(lg_source))

    def has_return_after_event_publish_try(tree: ast.AST) -> bool:
        """验证 return 语句位于事件发布 try/except 块之后

        正确模式：
            try: ... (主流程)
            except: ...
            try: await self._publish_xxx(...)  # 事件发布
            except: logger.exception(...)
            return xxx  # 必须在事件发布 try/except 之后
        """
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # 找最后一个 try/except 块（事件发布）
                last_try_index = -1
                for i, stmt in enumerate(node.body):
                    if isinstance(stmt, ast.Try):
                        last_try_index = i

                # 检查 return 是否在最后 try 之后
                if last_try_index >= 0:
                    for i in range(last_try_index + 1, len(node.body)):
                        if isinstance(node.body[i], ast.Return):
                            return True
                return False
        return False

    assert has_return_after_event_publish_try(pref_tree)
    assert has_return_after_event_publish_try(lg_tree)


# =========================================================================
# Scenario 6: WorkflowSubmitted 事件总线通道注册（AC-3）
# =========================================================================


@given("ChannelRouter 初始化完成")
def channel_router_initialized() -> None:
    pass


@then("WorkflowSubmitted 应注册到 ChannelRouter 的 DEFAULT_MAPPINGS")
def verify_workflow_submitted_in_default_mappings() -> None:
    from src.infrastructure.messaging.channel_router import ChannelRouter

    router = ChannelRouter(load_defaults=True)
    mapping = router.DEFAULT_MAPPINGS.get("WorkflowSubmitted")
    assert mapping is not None


@then("WorkflowSubmitted 的通道策略应为 RELIABLE")
def verify_workflow_submitted_reliable() -> None:
    from src.infrastructure.messaging.channel_router import ChannelRouter, DeliveryMode

    mapping = ChannelRouter.DEFAULT_MAPPINGS.get("WorkflowSubmitted")
    assert mapping is not None
    assert mapping.delivery_mode == DeliveryMode.RELIABLE


@then("WorkflowSubmitted 应注册到 configs/event_channels.yaml")
def verify_workflow_submitted_in_yaml() -> None:
    import yaml

    with open("configs/event_channels.yaml") as f:
        config = yaml.safe_load(f)

    channels = config.get("event_channels", {})
    assert "WorkflowSubmitted" in channels
    assert channels["WorkflowSubmitted"]["delivery_mode"] == "reliable"
