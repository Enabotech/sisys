# language: zh-CN
功能: Story 1.14a - 自主调用循环 trigger 实现

  作为系统架构师
  我想要实现领域事件/心跳事件触发机制
  以便系统可以基于事件或周期性心跳自主启动任务

  背景:
    假如 Story 1.2 领域事件定义和 Story 1.3 事件总线实现已完成
    假如 TriggerService 已实现并配置了事件发布器
    假如 HeartbeatScheduler 已配置心跳间隔为 60 秒

  # =========================================================================
  # AC-1: 领域事件触发机制
  # =========================================================================

  场景: AC-1 - 领域事件 DocumentProcessed 触发 Triggered 事件
    假如 系统接收到 DocumentProcessed 领域事件
    当 TriggerService 监听并接收该事件
    那么 TriggerService 应该解析事件类型为 DocumentProcessed
    并且 应该提取 session_id 和任务上下文
    并且 应该发布 Triggered 事件到下游 route 机制
    并且 触发延迟 P95 应该小于 10ms

  场景: AC-1 - 领域事件 ToolExecuted 触发 Triggered 事件
    假如 系统接收到 ToolExecuted 领域事件（包含 tool_name: web_search, session_id: session-001）
    当 TriggerService 处理该事件
    那么 应该提取 tool_name 和 session_id 到任务上下文
    并且 应该发布 Triggered 事件
    并且 触发器不直接调用任何 route 函数

  场景: AC-1 - 领域事件 AgentDecided 触发 Triggered 事件
    假如 系统接收到 AgentDecided 领域事件（包含 agent_id: agent-001, routing_decision: route-to-specialist）
    当 TriggerService 处理该事件
    那么 应该提取 agent_id 和路由决策上下文
    并且 应该发布 Triggered 事件

  场景: AC-1 - 支持 12 种领域事件类型
    当 我发布每种事件类型到事件总线
    那么 TriggerService 应该能正确处理每种事件
    并且 每种事件都应该触发 Triggered 事件发布

  场景: AC-1 - 触发器无循环依赖
    假如 TriggerService 已配置事件发布器
    当 TriggerService 发布 Triggered 事件
    那么 不应该直接调用任何 route 函数
    并且 通信应该通过事件总线异步进行

  # =========================================================================
  # AC-2: 心跳事件触发机制
  # =========================================================================

  场景: AC-2 - 心跳定时器触发生成 HeartbeatTriggered 事件
    当 心跳定时器触发（间隔 60 秒到期）
    那么 HeartbeatScheduler 应该生成 HeartbeatTriggered 事件
    并且 HeartbeatScheduler 应该发布 HeartbeatTriggered 到事件总线
    并且 心跳漏检率应该为 0%

  场景: AC-2 - 心跳间隔可配置
    假如 我配置心跳间隔为 30 秒
    当 启动 HeartbeatScheduler
    那么 心跳应该每 30 秒触发一次

  场景: AC-2 - 心跳唤醒原因分类 - scheduled
    当 wake_reason 为 scheduled
    那么 TriggerService 应该处理并提取 scheduled 上下文

  场景: AC-2 - 心跳唤醒原因分类 - user_request
    当 wake_reason 为 user_request
    那么 TriggerService 应该处理并提取 user_request 上下文

  场景: AC-2 - 心跳唤醒原因分类 - system_recovery
    当 wake_reason 为 system_recovery
    那么 TriggerService 应该处理并提取 system_recovery 上下文

  场景: AC-2 - 心跳待办事项提取
    当 HeartbeatScheduler 生成 HeartbeatTriggered（包含 todo_items: task1, task2, task3）
    那么 应该提取 todo_items 到任务上下文

  场景: AC-2 - 心跳成本预算提取
    当 HeartbeatScheduler 生成 HeartbeatTriggered（包含 cost_budget: 250.0）
    那么 应该提取 cost_budget 到任务上下文

  # =========================================================================
  # AC-3: 会话上下文提取
  # =========================================================================

  场景: AC-3 - session_id 优先从 payload 获取
    假如 系统接收到包含 session_id 的领域事件（session_id: session-payload-123）
    当 TriggerService 解析该事件
    那么 提取的 session_id 应该为 session-payload-123

  场景: AC-3 - session_id 回退到 aggregate_id
    假如 系统接收到包含 aggregate_id 但不包含 session_id 的领域事件（aggregate_id: agg-456）
    当 TriggerService 解析该事件
    那么 提取的 session_id 应该回退到 aggregate_id 值

  场景: AC-3 - session_id 缺省时使用 default
    假如 系统接收到不包含 session_id 也不包含 aggregate_id 的领域事件
    当 TriggerService 解析该事件
    那么 提取的 session_id 应该为 default

  场景: AC-3 - 完整上下文字段提取
    假如 系统接收到包含完整上下文字段的领域事件
    当 TriggerService 提取上下文
    那么 应该提取 session_id
    并且 应该提取 agent_id（如果存在）
    并且 应该提取 task_context（task_type, priority, tool_name 等）
    并且 应该提取 trigger_type（domain_event）
    并且 应该提取 timestamp

  场景: AC-3 - 心跳上下文提取
    假如 系统接收到 HeartbeatTriggered 事件（heartbeat_id: hb-123, wake_reason: user_request）
    当 TriggerService 提取上下文
    那么 session_id 应该为 heartbeat-scheduler
    并且 trigger_type 应该为 heartbeat
    并且 task_context 应该包含 heartbeat_id, wake_reason, todo_items, cost_budget

  # =========================================================================
  # AC-4: 触发器与路由解耦
  # =========================================================================

  场景: AC-4 - 触发器通过事件总线与路由通信
    假如 TriggerService 已完成上下文提取
    当 发布 Triggered 事件
    那么 应该通过事件总线异步发布
    并且 不应该直接调用 route 函数

  场景: AC-4 - 六边形架构合规 - 领域层零依赖
    假如 我验证 TriggerService 源代码
    那么 TriggerService 不应该导入任何基础设施层模块
    并且 TriggerContext 不应该导入任何基础设施层模块
    并且 Triggered 事件不应该导入任何外部框架

  场景: AC-4 - TriggerService 使用 Protocol 依赖倒置
    假如 我检查 TriggerService 实现
    那么 应该使用 EventPublisherProtocol 而非具体实现
    并且 领域层定义接口，基础设施层实现

  # =========================================================================
  # AC-5: 触发器性能要求
  # =========================================================================

  场景: AC-5 - 触发延迟 P95 小于 10ms
    假如 我发送 1000 个领域事件到事件总线
    当 TriggerService 处理每个事件
    那么 端到端触发延迟 P95 应该小于 10ms

  场景: AC-5 - 吞吐量支持 1000 events/second
    假如 事件总线每秒接收 1000 个事件
    当 TriggerService 持续处理这些事件
    那么 系统应该能够实时处理所有事件而不会积压

  场景: AC-5 - TriggerContext 创建延迟小于 1ms
    假如 我创建 10000 次 TriggerContext
    当 从领域事件提取上下文
    那么 平均延迟应该小于 1ms

  场景: AC-5 - Triggered 事件序列化延迟小于 0.5ms
    假如 我序列化 10000 次 Triggered 事件
    当 事件转 JSON 格式
    那么 平均延迟应该小于 0.5ms

  场景: AC-5 - Triggered 事件反序列化延迟小于 1ms
    假如 我反序列化 10000 次 Triggered 事件
    当 JSON 格式转事件对象
    那么 平均延迟应该小于 1ms
