# language: zh-CN
功能: 领域事件定义

  作为系统架构师
  我想要定义完整的 10 种领域事件 Schema 与事件发布/订阅基础设施
  以便系统各模块可以通过标准化事件进行异步通信

  背景:
    假如 10 种核心领域事件已定义
    并且 事件发布/订阅基础设施已实现

  # =========================================================================
  # AC-1: 10 种领域事件 Schema 定义
  # =========================================================================

  场景: 定义 DocumentProcessed 事件
    当 创建 DocumentProcessed 事件携带文档 ID、解析结果摘要、嵌入向量引用
    那么 事件类型为 "DocumentProcessed"
    并且 aggregate_id 等于 document_id
    并且 payload 包含解析结果和嵌入向量信息

  场景: 定义 ToolExecuted 事件
    当 创建 ToolExecuted 事件携带工具 ID、执行结果、成本审计信息
    那么 事件类型为 "ToolExecuted"
    并且 aggregate_id 等于 tool_id
    并且 payload 包含执行结果和成本审计信息

  场景: 定义 AgentDecided 事件
    当 创建 AgentDecided 事件携带 Agent ID、决策结果、置信度评分
    那么 事件类型为 "AgentDecided"
    并且 aggregate_id 等于 agent_id (AgentDecided)
    并且 payload 包含决策结果和置信度

  场景: 定义 CheckpointReached 事件
    当 创建 CheckpointReached 事件携带阶段标识、用户反馈请求
    那么 事件类型为 "CheckpointReached"
    并且 aggregate_id 等于 checkpoint_id (CheckpointReached)
    并且 payload 包含阶段标识和反馈请求

  场景: 定义 CorrectionApproved 事件
    当 创建 CorrectionApproved 事件携带修正类型、修正前后值、审批链
    那么 事件类型为 "CorrectionApproved"
    并且 aggregate_id 等于 correction_id
    并且 payload 包含修正类型和审批链

  场景: 定义 StrategicDeviationWarning 事件
    当 创建 StrategicDeviationWarning 事件携带偏差类型、偏差等级、实际值、规划值
    那么 事件类型为 "StrategicDeviationWarning"
    并且 aggregate_id 不为空
    并且 payload 包含偏差类型、等级、实际值和规划值

  场景: 定义 HeartbeatTriggered 事件
    当 创建 HeartbeatTriggered 事件携带心跳 ID、唤醒原因、待办事项列表
    那么 事件类型为 "HeartbeatTriggered"
    并且 aggregate_id 等于 heartbeat_id
    并且 payload 包含唤醒原因和待办事项

  场景: 定义 IsolationLevelSwitched 事件
    当 创建 IsolationLevelSwitched 事件携带 Agent ID、原隔离等级、目标隔离等级
    那么 事件类型为 "IsolationLevelSwitched"
    并且 aggregate_id 等于 agent_id
    并且 payload 包含隔离等级切换信息

  场景: 定义 CheckpointRecovered 事件
    当 创建 CheckpointRecovered 事件携带 Checkpoint ID、恢复模式、修改内容
    那么 事件类型为 "CheckpointRecovered"
    并且 aggregate_id 等于 checkpoint_id
    并且 payload 包含恢复模式和修改内容

  场景: 定义 RoutingDecided 事件
    当 创建 RoutingDecided 事件携带任务 ID、L1 合规性结果、L2 评分、选定模型
    那么 事件类型为 "RoutingDecided"
    并且 aggregate_id 等于 task_id
    并且 payload 包含路由决策信息

  # =========================================================================
  # AC-2: 事件发布与监听
  # =========================================================================

  场景: 事件发布与监听
    假如 InMemoryEventBus 已实现
    当 注册事件监听器并发布时间
    那么 监听器接收到事件
    并且 重复发布同一事件不会重复处理(幂等性)

  # =========================================================================
  # AC-3: 事件序列化与反序列化
  # =========================================================================

  场景: 事件序列化与反序列化
    假如 任意一种领域事件
    当 调用 to_dict() 方法
    那么 返回字典包含 event_type、event_id、occurred_on、payload
    并且 调用 from_dict() 可以重建事件对象
    并且 往返序列化数据无损

  # =========================================================================
  # AC-4: 事件存储与查询
  # =========================================================================

  场景: 事件存储与查询
    假如 InMemoryEventStore 已实现
    当 保存事件并按聚合根 ID 查询
    那么 返回该聚合根的所有事件序列
    并且 按版本号范围查询返回正确的事件子集

  # =========================================================================
  # AC-5: 架构约束
  # =========================================================================

  场景: 领域事件零 Pydantic 依赖
    当 检查 src/domain/events/ 目录下的所有 Python 文件
    那么 不存在 "from pydantic" 或 "import pydantic" 导入
    并且 仅使用 Python 标准库(dataclasses, typing, datetime, uuid, enum, json)
