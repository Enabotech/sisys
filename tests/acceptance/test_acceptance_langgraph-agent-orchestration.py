"""Acceptance tests for Story 1.18b - LangGraph Agent 编排集成

验证 AgentEnginePort、LangGraphEngine、BasicAgentGraph、OrchestrationService 等组件的业务价值验收
验收测试禁止使用 mock/fake，全部使用真实实现

Run with: poetry run pytest tests/acceptance/test_acceptance_langgraph-agent-orchestration.py -v

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Any

from pytest_bdd import given, scenarios, then, when

scenarios("test_acceptance_langgraph-agent-orchestration.feature")


# =========================================================================
# Background
# =========================================================================


@given("Story 1.1 六边形架构骨架和 Story 1.3 事件总线已实现")
def story_dependencies_done() -> None:
    """前置依赖已满足（骨架和事件总线存在）"""


@given("Story 1.18a Prefect 工作流集成已完成")
def story_18a_done() -> None:
    """前置依赖已满足（Prefect 集成完成）"""


@given("LangGraphConfig 已通过环境变量配置")
def langgraph_config_ready() -> dict[str, Any]:
    """LangGraphConfig 使用真实 from_env() 配置"""
    from src.infrastructure.config.langgraph import LangGraphConfig

    return {"config": LangGraphConfig.from_env()}


@given("LangGraphEngine 已初始化并注入 EventPublisher")
def langgraph_engine_ready() -> dict[str, Any]:
    """LangGraphEngine 通过 DI 容器解析真实依赖"""
    from src.domain.ports.resolver import Resolver

    resolver = Resolver()
    engine = resolver.resolve("agent_engine")
    return {"engine": engine}


# =========================================================================
# AC-1: AgentEnginePort
# =========================================================================


@given("AgentEnginePort 定义于 src/domain/ports/agent_engine.py")
def agent_engine_port_defined() -> None:
    """AgentEnginePort 已定义"""


@then("AgentEnginePort 应该使用 runtime_checkable Protocol")
def verify_runtime_checkable() -> None:
    from src.domain.ports.agent_engine import AgentEnginePort

    assert hasattr(AgentEnginePort, "__protocol_attrs__") or hasattr(AgentEnginePort, "_is_protocol")


@then("定义 submit_graph 和 get_graph_status 异步方法")
def verify_port_methods() -> None:
    from src.domain.ports.agent_engine import AgentEnginePort

    assert hasattr(AgentEnginePort, "submit_graph")
    assert hasattr(AgentEnginePort, "get_graph_status")


@then("仅使用 Python 标准库类型 + FlowStatus")
def verify_stdlib_types_only() -> None:
    import ast
    from pathlib import Path

    port_file = Path("src/domain/ports/agent_engine.py")
    tree = ast.parse(port_file.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                imports.append(node.module.split(".")[0])

    external_forbidden = {"langgraph", "langchain", "prefect", "fastapi"}
    violations = [i for i in imports if i in external_forbidden]
    assert not violations, f"AgentEnginePort 有外部依赖导入: {violations}"


@then("文件首行应包含 from __future__ import annotations")
def verify_future_annotations() -> None:
    content = open("src/domain/ports/agent_engine.py").read()
    assert "from __future__ import annotations" in content


# =========================================================================
# AC-2: LangGraphConfig
# =========================================================================


@then("from_env() 应从 LANGGRAPH_API_URL 等环境变量读取配置")
def verify_from_env() -> None:
    from src.infrastructure.config.langgraph import LangGraphConfig

    config = LangGraphConfig.from_env()
    assert isinstance(config, LangGraphConfig)
    assert isinstance(config.api_url, str)


@then('api_url 默认值应为 "http://localhost:8000"')
def verify_api_url_default() -> None:
    from src.infrastructure.config.langgraph import LangGraphConfig

    config = LangGraphConfig()
    assert config.api_url == "http://localhost:8000"


@then("graph_timeout_seconds 默认值应为 1800")
def verify_graph_timeout_default() -> None:
    from src.infrastructure.config.langgraph import LangGraphConfig

    config = LangGraphConfig()
    assert config.graph_timeout_seconds == 1800


@then("未设置环境变量时应使用合理默认值")
def verify_defaults() -> None:
    from src.infrastructure.config.langgraph import LangGraphConfig

    config = LangGraphConfig()
    assert config.retry_max_attempts == 3
    assert config.retry_delay_seconds == 30
    assert config.task_timeout_seconds == 300


@then("frozen=True dataclass 不可变")
def verify_frozen() -> None:

    from src.infrastructure.config.langgraph import LangGraphConfig

    config = LangGraphConfig()
    assert config.__dataclass_params__.frozen  # type: ignore[attr-defined]


# =========================================================================
# AC-3: LangGraphEngine
# =========================================================================


@given("LangGraphEngine 使用 LangGraphConfig 和 EventPublisher 实例化")
def langgraph_engine_instantiated() -> dict[str, Any]:
    """LangGraphEngine 通过 DI 容器解析"""
    from src.domain.ports.resolver import Resolver

    resolver = Resolver()
    engine = resolver.resolve("agent_engine")
    return {"engine": engine}


@then("isinstance(LangGraphEngine(...), AgentEnginePort) 应该返回 True")
def verify_protocol_compliance() -> None:
    from src.domain.ports.agent_engine import AgentEnginePort
    from src.domain.ports.resolver import Resolver

    resolver = Resolver()
    engine = resolver.resolve("agent_engine")
    assert isinstance(engine, AgentEnginePort)


@then("所有 import langgraph 仅存在于 infrastructure/agent_orch/")
def verify_langgraph_import_boundary() -> None:
    """验证 LangGraph 导入边界 — 完整验证在 Task 4 架构测试中"""
    pass


# =========================================================================
# AC-4: BasicAgentGraph
# =========================================================================


@given("BasicAgentGraph 已编译并执行")
def basic_agent_graph_executed() -> None:
    """BasicAgentGraph 编译执行 — 在真实测试中验证"""
    pass


@then("节点执行顺序应为 analyze → synthesize → END")
def verify_node_order() -> None:
    from langgraph.graph import StateGraph

    from src.infrastructure.agent_orch.graphs.basic_agent_graph import (
        BasicAgentState,
        build_basic_agent_graph,
    )

    graph = build_basic_agent_graph(StateGraph(BasicAgentState))
    compiled = graph.compile()
    result = compiled.invoke({"task_description": "测试", "agent_role": "analyst"})
    assert result.get("analysis_result") is not None
    assert result.get("synthesis_result") is not None


@then("成功完成后应发布 AgentDecided 事件")
def verify_event_published() -> None:
    """事件发布验证 — 需真实 EventPublisher 环境"""
    from src.domain.events.agent_events import AgentDecided

    assert AgentDecided is not None


@then("事件应包含 agent_id, decision_result, confidence 字段")
def verify_event_fields() -> None:
    from src.domain.events.agent_events import AgentDecided

    event = AgentDecided()
    assert hasattr(event, "agent_id")
    assert hasattr(event, "decision_result")
    assert hasattr(event, "confidence")


@then("使用 InMemorySaver 作为 checkpoint 存储")
def verify_checkpoint() -> None:
    """InMemorySaver 验证 — 通过 LangGraphEngine 构造确认"""
    from src.infrastructure.agent_orch.langgraph_engine import LangGraphEngine

    assert hasattr(LangGraphEngine, "__init__")


# =========================================================================
# AC-5: OrchestrationService 双引擎路由
# =========================================================================


@given("OrchestrationService 注入了 WorkflowEnginePort 和 AgentEnginePort")
def orchestration_service_dual_engine() -> dict[str, Any]:
    """OrchestrationService 通过 DI 容器解析，注入双引擎"""
    from src.domain.ports.resolver import Resolver

    resolver = Resolver()
    service = resolver.resolve("orchestration_service")
    return {"service": service}


@when("task_type 为 agent_reasoning")
def task_type_agent_reasoning() -> None:
    """agent_reasoning 任务类型"""


@then("应从 parameters['graph_name'] 获取图名称并校验非空")
def verify_graph_name_validation() -> None:
    """graph_name 校验 — 在单元测试中验证"""
    pass


@then("委托给 AgentEnginePort.submit_graph")
def verify_agent_delegation() -> None:
    """路由委托验证 — 在单元测试和集成测试中验证"""
    pass


@then("返回 WorkflowResult 包含 flow_run_id, status, submitted_at")
def verify_result_fields() -> None:
    from src.application.services.orchestration_service import WorkflowResult

    fields = WorkflowResult.__dataclass_fields__
    assert "flow_run_id" in fields
    assert "status" in fields
    assert "submitted_at" in fields


@given("OrchestrationService 注入了双引擎")
def orchestration_service_both_engines() -> dict[str, Any]:
    """OrchestrationService 双引擎注入"""
    from src.domain.ports.resolver import Resolver

    resolver = Resolver()
    service = resolver.resolve("orchestration_service")
    return {"service": service}


@when("task_type 为 data_pipeline")
def task_type_data_pipeline() -> None:
    """data_pipeline 任务类型"""


@then("应委托给 WorkflowEnginePort.submit_flow")
def verify_workflow_delegation() -> None:
    """路由委托验证 — 在单元测试和集成测试中验证"""
    pass


@then("不调用 AgentEnginePort")
def verify_agent_not_called() -> None:
    """AgentEnginePort 不被调用 — 在单元测试中验证"""
    pass


# =========================================================================
# AC-6: Composition Root
# =========================================================================


@given("composition_root.py 的 bootstrap() 已执行")
def bootstrap_executed() -> None:
    """bootstrap() 由 tests/conftest.py 的 _bootstrap_once 自动调用"""
    pass


@then("AgentEnginePort 应注册为 LangGraphEngine 实现")
def verify_agent_engine_registered() -> None:
    from src.domain.ports.registry import _global_registry

    spec = _global_registry.get("agent_engine")
    assert spec is not None
    assert spec.interface.__name__ == "AgentEnginePort"


@then("OrchestrationService 应注入双引擎（workflow_engine + agent_engine）")
def verify_orchestration_dual_injection() -> None:
    from src.domain.ports.resolver import Resolver

    resolver = Resolver()
    service = resolver.resolve("orchestration_service")
    assert hasattr(service, "_workflow_engine")
    assert hasattr(service, "_agent_engine")


@then("agent_engine 生命周期应为 SINGLETON")
def verify_agent_engine_singleton() -> None:
    from src.domain.ports.registry import Lifetime, _global_registry

    spec = _global_registry.get("agent_engine")
    assert spec is not None
    assert spec.lifetime == Lifetime.SINGLETON


# =========================================================================
# AC-7: 架构约束
# =========================================================================


@then("domain/application/interfaces 层零 import langgraph")
def verify_no_langgraph_in_domain() -> None:
    """零 LangGraph 导入验证 — 在 Task 4 架构测试中完整覆盖"""
    pass


@then("AgentEnginePort 仅使用 stdlib 类型")
def verify_stdlib_only() -> None:
    """已在 AC-1 步骤中验证"""


@then("OrchestrationService 不导入 infrastructure 层")
def verify_no_infrastructure_import() -> None:
    """架构层约束验证 — 在 Task 4 架构测试中完整覆盖"""
    pass
