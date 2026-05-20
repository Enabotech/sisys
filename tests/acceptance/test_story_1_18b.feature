# language: zh-CN
功能: Story 1.18b - LangGraph Agent 编排集成

  作为系统架构师
  我想要集成 LangGraph 1.0+ 作为 Agent 编排引擎
  以便系统支持认知密集型推理，包括 Agent 协作与 Checkpoint 机制

  背景:
    假如 Story 1.1 六边形架构骨架和 Story 1.3 事件总线已实现
    假如 Story 1.18a Prefect 工作流集成已完成
    假如 LangGraphConfig 已通过环境变量配置
    假如 LangGraphEngine 已初始化并注入 EventPublisher

  # =========================================================================
  # AC-1: AgentEnginePort 端口定义
  # =========================================================================

  场景: AC-1 - AgentEnginePort 满足 Protocol 接口
    假如 AgentEnginePort 定义于 src/domain/ports/agent_engine.py
    那么 AgentEnginePort 应该使用 runtime_checkable Protocol
    并且 定义 submit_graph 和 get_graph_status 异步方法
    并且 仅使用 Python 标准库类型 + FlowStatus
    并且 文件首行应包含 from __future__ import annotations

  # =========================================================================
  # AC-2: LangGraphConfig 配置
  # =========================================================================

  场景: AC-2 - LangGraphConfig 从环境变量加载
    那么 from_env() 应从 LANGGRAPH_API_URL 等环境变量读取配置
    并且 api_url 默认值应为 "http://localhost:8000"
    并且 graph_timeout_seconds 默认值应为 1800
    并且 未设置环境变量时应使用合理默认值
    并且 frozen=True dataclass 不可变

  # =========================================================================
  # AC-3: LangGraphEngine 实现
  # =========================================================================

  场景: AC-3 - LangGraphEngine 满足 AgentEnginePort Protocol
    假如 LangGraphEngine 使用 LangGraphConfig 和 EventPublisher 实例化
    那么 isinstance(LangGraphEngine(...), AgentEnginePort) 应该返回 True
    并且 所有 import langgraph 仅存在于 infrastructure/agent_orch/

  # =========================================================================
  # AC-4: BasicAgentGraph 执行
  # =========================================================================

  场景: AC-4 - BasicAgent 状态图执行 analyze → synthesize
    假如 BasicAgentGraph 已编译并执行
    那么 节点执行顺序应为 analyze → synthesize → END
    并且 成功完成后应发布 AgentDecided 事件
    并且 事件应包含 agent_id, decision_result, confidence 字段
    并且 使用 InMemorySaver 作为 checkpoint 存储

  # =========================================================================
  # AC-5: OrchestrationService 双引擎路由
  # =========================================================================

  场景: AC-5 - OrchestrationService 路由 agent_reasoning 任务
    假如 OrchestrationService 注入了 WorkflowEnginePort 和 AgentEnginePort
    当 task_type 为 agent_reasoning
    那么 应从 parameters['graph_name'] 获取图名称并校验非空
    并且 委托给 AgentEnginePort.submit_graph
    并且 返回 WorkflowResult 包含 flow_run_id, status, submitted_at

  场景: AC-5 - OrchestrationService 路由 data_pipeline 任务回归验证
    假如 OrchestrationService 注入了双引擎
    当 task_type 为 data_pipeline
    那么 应委托给 WorkflowEnginePort.submit_flow
    并且 不调用 AgentEnginePort

  # =========================================================================
  # AC-6: Composition Root 注册
  # =========================================================================

  场景: AC-6 - Composition Root 注册 agent 端口
    假如 composition_root.py 的 bootstrap() 已执行
    那么 AgentEnginePort 应注册为 LangGraphEngine 实现
    并且 OrchestrationService 应注入双引擎（workflow_engine + agent_engine）
    并且 agent_engine 生命周期应为 SINGLETON

  # =========================================================================
  # AC-7: 架构约束验证
  # =========================================================================

  场景: AC-7 - 六边形架构约束
    那么 domain/application/interfaces 层零 import langgraph
    并且 AgentEnginePort 仅使用 stdlib 类型
    并且 OrchestrationService 不导入 infrastructure 层
