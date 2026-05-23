# language: zh-CN
功能: Story 20.8 - 双核引擎集成验证

  作为系统架构师
  我想要实现双核引擎（Prefect + LangGraph）端到端集成验证，补全 PrefectEngine 事件发布
  以便工作流引擎与 Agent 编排引擎通过统一端口集成，六边形架构合规

  背景:
    假如 Story 1.18a Prefect 工作流集成和 Story 1.18b LangGraph Agent 编排已完成
    假如 Story 20-1~20-7 重大重构系列已完成

  # =========================================================================
  # AC-1: PrefectEngine 事件发布补全 + AC-5: 端口签名验证
  # =========================================================================

  场景: 数据管道工作流提交
    假如 WorkflowEnginePort 定义于 src/domain/ports/workflow_engine.py
    并且 PrefectEngine 已注册为 WorkflowEnginePort 实现
    那么 WorkflowEnginePort 应定义 submit_flow 和 get_flow_status 方法
    并且 PrefectEngine 的 submit_flow 成功后应发布 WorkflowSubmitted 事件

  # =========================================================================
  # AC-5: AgentEnginePort 签名验证
  # =========================================================================

  场景: Agent 推理任务提交
    假如 AgentEnginePort 定义于 src/domain/ports/agent_engine.py
    并且 LangGraphEngine 已注册为 AgentEnginePort 实现
    那么 AgentEnginePort 应定义 submit_graph 和 get_graph_status 方法

  # =========================================================================
  # AC-5: 状态映射验证
  # =========================================================================

  场景: 双引擎状态查询
    那么 PrefectEngine 应实现 9 种 StateType 到 5 种 FlowStatus 的映射
    并且 LangGraphEngine 应使用 COMPLETED 和 FAILED 两种状态
    并且 FlowStatus 枚举包含 PENDING/RUNNING/COMPLETED/FAILED/RETRYING 五个状态

  # =========================================================================
  # AC-1: WorkflowSubmitted 事件发布
  # =========================================================================

  场景: PrefectEngine 事件发布
    假如 WorkflowSubmitted 事件定义于 workflow_events.py
    那么 WorkflowSubmitted 应包含 flow_run_id, flow_name, parameters 字段
    并且 WorkflowSubmitted 的 event_type 应为 "WorkflowSubmitted"
    并且 WorkflowSubmitted 的 aggregate_type 应为 "Workflow"
    并且 WorkflowSubmitted 应注册到 DomainEvent._registry

  # =========================================================================
  # AC-2: 双引擎事件发布对称性验证
  # =========================================================================

  场景: 双引擎事件发布对称性验证
    假如 PrefectEngine 和 LangGraphEngine 均注入 EventPublisher
    那么 PrefectEngine 和 LangGraphEngine 应使用相同的事件发布模式
    并且 两者均应使用 try/except Exception 包裹事件发布
    并且 两者均应检查 PublishResult 的 is_full_failure 属性
    并且 事件发布异常不应影响引擎返回值

  # =========================================================================
  # AC-3: 事件总线通道注册
  # =========================================================================

  场景: WorkflowSubmitted 事件总线通道注册
    假如 ChannelRouter 初始化完成
    那么 WorkflowSubmitted 应注册到 ChannelRouter 的 DEFAULT_MAPPINGS
    并且 WorkflowSubmitted 的通道策略应为 RELIABLE
    并且 WorkflowSubmitted 应注册到 config/event_channels.yaml
