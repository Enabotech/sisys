# language: zh-CN
功能: Story 1.3 - 双通道事件总线实现

  作为系统架构师
  我想要实现双通道事件总线（Redis Pub/Sub + RabbitMQ + Outbox）
  以便系统模块可以通过标准化的异步事件进行通信

  背景:
    假如 Story 1.1 六边形架构骨架和 Story 1.2 领域事件已实现

  场景: AC-1 - Redis Pub/Sub 实时通知通道 (DocumentProcessed)
    当 我发布一个 DocumentProcessed 事件到 Redis channel
    那么 订阅者应该接收到该事件
    并且 事件应该被正确序列化为 JSON
    并且 Redis channel 名称应该遵循 sisys:rt:documentprocessed 约定

  场景: AC-1 - Redis Pub/Sub 实时通知通道 (HeartbeatTriggered)
    当 我发布一个 HeartbeatTriggered 事件到 Redis channel
    那么 订阅者应该接收到该事件
    并且 事件应该被正确序列化为 JSON
    并且 Redis channel 名称应该遵循 sisys:rt:heartbeattriggered 约定

  场景: AC-2 - RabbitMQ 可靠事件通道 (DocumentProcessed)
    当 我异步发布一个 DocumentProcessed 事件到 RabbitMQ
    那么 异步消费者应该接收到该事件
    并且 消息应该是持久化的 (durable=True, delivery_mode=2)
    并且 路由键应该遵循 sisys.events.reliable.DocumentProcessed 约定

  场景: AC-2 - RabbitMQ 可靠事件通道 (AgentDecided)
    当 我异步发布一个 AgentDecided 事件到 RabbitMQ
    那么 异步消费者应该接收到该事件
    并且 消息应该是持久化的 (durable=True, delivery_mode=2)
    并且 路由键应该遵循 sisys.events.reliable.AgentDecided 约定

  场景: AC-3 - 事务 Outbox 模式 (DocumentProcessed)
    当 我保存一个 DocumentProcessed 事件到 OutboxRepository
    那么 事件应该以 pending 状态存储
    并且 AsyncOutboxPoller 应该拾取该事件
    并且 事件应该被发布到 RabbitMQ
    并且 事件状态应该更新为 published

  场景: AC-3 - 事务 Outbox 模式 (ToolExecuted)
    当 我保存一个 ToolExecuted 事件到 OutboxRepository
    那么 事件应该以 pending 状态存储
    并且 AsyncOutboxPoller 应该拾取该事件
    并且 事件应该被发布到 RabbitMQ
    并且 事件状态应该更新为 published

  场景: AC-4 - 事件处理幂等性检查
    当 我首次处理一个事件
    那么 try_acquire 应该返回 True
    当 我第二次处理相同事件
    并且 try_acquire 应该返回 False
    并且 事件应该只被处理一次

  场景: AC-5 - 事件处理监控和可观测性
    当 事件被成功处理
    那么 events_processed_total 计数器应该递增
    当 事件处理失败
    并且 events_failed_total 计数器应该递增
    并且 当 EVENT_BUS_OTEL_TRACE_ENABLED=true 时应该创建 OpenTelemetry span

  场景: AC-6 - 架构约束验证
    当 我运行架构约束验证测试
    那么 领域层不应该导入 OutboxEntity
    并且 Redis/RabbitMQ 客户端导入应该只在基础设施层
    并且 Ruff 检查应该通过 (0 errors)
    并且 MyPy 类型检查应该通过 (0 issues)

  场景: AC-7 - 事件处理重试机制（指数退避 + 抖动）
    当 事件处理失败并触发重试
    那么 重试延迟应该遵循指数退避: min(base * 2^retry_count * jitter, max)
    并且 jitter 应该在 0.5 和 1.5 之间
    并且 超过最大重试次数后事件应该进入死信队列
