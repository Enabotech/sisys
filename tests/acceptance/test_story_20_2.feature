# language: zh-CN
功能: Story 20.2 - 事件消息体系重构

  作为系统架构师
  我想要重构 SISYS 事件消息体系
  以便对标业界事件驱动设计最佳实践，提升系统可靠性、幂等性、可观测性与可维护性

  背景:
    假如 Story 1.3 事件总线实现和 Story 20-1 测试重构已实现

  # ============================================================================
  # AC-1: PostgreSQL 持久化死信队列
  # ============================================================================

  场景: AC-1 - PostgreSQL DLQ 持久化 (enqueue)
    假如 事件消费者处理失败超过最大重试次数
    当 我将事件持久化到 PostgreSQL dead_letter_queue 表
    那么 事件应该包含 event_id, event_type, payload, error_message, retry_count
    并且 状态应该为 pending
    并且 支持人工干预查询和处理

  场景: AC-1 - PostgreSQL DLQ 持久化 (dequeue)
    假如 DLQ 中有待处理条目
    当 我从 DLQ 取出条目
    那么 应该返回最早的 pending 条目
    并且 条目状态应该更新为 processed

  场景: AC-1 - PostgreSQL DLQ 持久化 (get_all)
    假如 DLQ 中有多个条目
    当 我查询所有 DLQ 条目
    那么 应该返回所有条目按创建时间倒序排列

  场景: AC-1 - PostgreSQL DLQ 持久化 (mark_action_taken)
    假如 DLQ 中有待处理条目
    当 我标记条目已采取行动
    那么 条目状态应该更新为 processed
    并且 action_taken 字段应该记录采取的行动

  # ============================================================================
  # AC-2: Redis 延迟重试队列
  # ============================================================================

  场景: AC-2 - Redis ZSET 延迟重试调度
    假如 事件处理失败需要重试
    当 我将事件放入 Redis ZSET 延迟重试队列
    那么 事件应该在指定延迟时间后可用
    并且 避免 nack(requeue=True) 造成的饥饿问题

  场景: AC-2 - Redis 延迟重试调度 (scheduled retry)
    假如 事件处理失败需要重试
    当 我将事件放入 Redis ZSET 延迟重试队列
    当 延迟时间到达
    那么 事件应该被重新处理

  # ============================================================================
  # AC-3: 双写幂等性检查器
  # ============================================================================

  场景: AC-3 - 双写幂等性检查 (Redis + PostgreSQL)
    假如 事件消费者处理事件
    当 执行幂等性检查
    那么 应该同时使用 Redis 和 PostgreSQL 双写
    并且 Redis 故障时降级至 PostgreSQL

  场景: AC-3 - DualIdempotencyChecker 并存关系
    那么 DualIdempotencyChecker 应该与现有 IdempotencyChecker 并存
    并且 RabbitMQEventListener 应该使用 DualIdempotencyChecker

  # ============================================================================
  # AC-4: 增强 DomainEvent 基类
  # ============================================================================

  场景: AC-4 - DomainEvent 新增 correlation_id 和 causation_id
    假如 事件溯源和链路追踪需求
    当 定义领域事件
    那么 应该支持 correlation_id, causation_id, metadata 字段
    并且 新字段应该位于 payload 之外（顶层字段）

  场景: AC-4 - DomainEvent 序列化支持新字段
    假如 我序列化和反序列化 DomainEvent
    那么 to_dict() / from_dict() 应该正确处理新字段
    并且 向后兼容性应该得到保证

  # ============================================================================
  # AC-5: EventListenerAsync 异步事件处理器接口
  # ============================================================================

  场景: AC-5 - EventListenerAsync 独立接口
    假如 生产环境需要异步事件处理能力
    当 创建 EventListenerAsync 接口
    那么 应该支持异步 async_handle() 方法
    并且 应该是独立接口，不继承 EventListener

  场景: AC-5 - RabbitMQEventListener 实现 EventListenerAsync
    那么 应该实现 EventListenerAsync 接口
    并且 支持异步 async_handle(event) 方法

  # ============================================================================
  # AC-6: UnitOfWork 统一事务边界
  # ============================================================================

  场景: AC-6 - UnitOfWork 事务原子性
    假如 需要保证业务操作与 Outbox 写入原子性
    当 实现工作单元模式
    那么 业务操作与 Outbox 写入应该在同一事务中

  场景: AC-6 - PostgreSQLUnitOfWork 实现
    当 创建 PostgreSQLUnitOfWork
    那么 begin() / commit() / rollback() / close() 方法应该正确工作

  # ============================================================================
  # AC-7: PostgreSQL EventStore 实现
  # ============================================================================

  场景: AC-7 - PostgreSQL EventStore 事件追加
    假如 事件溯源需要持久化存储
    当 追加事件到 EventStore
    那么 事件应该持久化到 event_store 表
    并且 乐观锁版本检查应该防止重复版本

  场景: AC-7 - PostgreSQL EventStore 聚合重建
    假如 需要重建聚合
    当 获取聚合的所有事件
    那么 应该返回按版本号排序的事件列表

  场景: AC-7 - PostgreSQL EventStore 按时间范围查询
    假如 需要按类型和时间范围查询事件
    当 调用 get_events_by_type
    那么 应该返回匹配条件的事件列表

  场景: AC-7 - PostgreSQL EventStore 版本冲突检测
    假如 尝试追加重复的 aggregate_id + version
    当 调用 append 方法
    那么 应该抛出 VersionError

  # ============================================================================
  # AC-8: RabbitMQEventListener 实现
  # ============================================================================

  场景: AC-8 - RabbitMQEventListener 实现 EventListenerAsync
    假如 生产环境需要可靠的事件消费
    当 实现 RabbitMQEventListener
    那么 应该支持手动 ACK/NACK 和死信队列

  场景: AC-8 - RabbitMQEventListener 集成新组件
    那么 应该使用 DualIdempotencyChecker
    并且 应该使用 RedisRetryQueue 处理重试
    并且 应该使用 PostgresDeadLetterQueue 处理死信

  # ============================================================================
  # AC-9: AsyncOutboxPoller 内部方法文档化
  # ============================================================================

  场景: AC-9 - @poller_only 注释标记
    假如 AsyncOutboxPoller 使用 OutboxRepository 内部方法
    当 内部方法添加 @poller_only 注释
    那么 领域层接口与基础设施层实现应该分离

  场景: AC-9 - AsyncOutboxPoller 继续使用内部方法
    那么 AsyncOutboxPoller 应该继续正常工作

  # ============================================================================
  # AC-10: 架构约束验证
  # ============================================================================

  场景: AC-10 - 领域层零外部依赖
    假如 我检查领域层代码
    那么 领域层不应该导入任何外部依赖（除 Python 标准库）

  场景: AC-10 - 领域层不导入基础设施模型
    那么 领域层不应该导入 src.infrastructure.storage.postgresql.models
