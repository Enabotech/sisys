# language: zh-CN
功能: Story 90-7 - 事务子系统重构

  作为系统架构师
  我要实现事务子系统的完整重构
  以确保事务边界显式化、跨存储操作可靠执行

  背景:
    假如 端口注册中心已初始化

  # ============================================================================
  # AC-1: Session 生命周期职责分离
  # ============================================================================

  场景: AC-1 - UoW 不调用 close，由 Middleware 负责
    假如 PostgreSQLUnitOfWork 实例已创建
    当 执行 async with uow 代码块
    那么 uow.__aexit__ 不调用 session.close()

  # ============================================================================
  # AC-2: UnitOfWorkFactory Protocol + DI 注册
  # ============================================================================

  场景: AC-2 - UnitOfWorkFactory 可通过 DI 获取
    当 调用 resolver.resolve("uow_factory")
    那么 返回 PostgreSQLUnitOfWork 类
    并且 UnitOfWorkFactory Protocol 接口已定义

  # ============================================================================
  # AC-3: UoW 实例级标志位
  # ============================================================================

  场景: AC-3 - 多实例状态隔离
    假如 创建两个 PostgreSQLUnitOfWork 实例
    当 第一个实例执行 commit
    那么 第二个实例的 _committed 标志仍为 False

  # ============================================================================
  # AC-4: Outbox archived 状态修复 + 状态机修复
  # ============================================================================

  场景: AC-4 - Outbox archived 状态可持久化
    假如 OutboxEntity 实例已创建
    当 依次标记为 failed 和 archived
    那么 OutboxEntity 状态变为 archived

  场景: AC-4 - Outbox 状态机阻止非法转换
    假如 OutboxEntity 实例状态为 pending
    当 尝试直接标记为 archived
    那么 抛出 InvalidStateTransitionError

  场景: AC-4 - InMemoryOutboxRepository 状态转换
    假如 InMemoryOutboxRepository 包含一个 pending 事件
    当 调用 mark_published
    那么 事件状态变为 published

  # ============================================================================
  # AC-5: Outbox 清理策略 + RetryPolicy 集成
  # ============================================================================

  场景: AC-5 - Outbox 清理已发布记录
    假如 InMemoryOutboxRepository 包含已发布和未发布事件
    当 调用 cleanup_old_published_records
    那么 仅已发布记录被清理
    并且 pending 事件不受影响

  场景: AC-5 - RetryPolicy 指数退避计算
    假如 RetryPolicy 配置已创建
    当 计算多次重试的退避时间
    那么 退避时间按指数增长
    并且 不超过最大延迟

  # ============================================================================
  # AC-6: 事务隔离级别配置 + 审计专用 UoW
  # ============================================================================

  场景: AC-6 - PostgreSQLManager 支持隔离级别
    假如 PostgreSQLManager 类已加载
    那么 支持 get_session_with_isolation 方法
    并且 支持 SERIALIZABLE 和 REPEATABLE READ 隔离级别

  场景: AC-6 - AuditUnitOfWork 使用 SERIALIZABLE 隔离级别
    假如 AuditUnitOfWork 类已加载
    那么 构造器注入 PostgreSQLManager
    并且 定义了 begin/commit/rollback 方法

  # ============================================================================
  # AC-7: Saga 基础设施
  # ============================================================================

  场景: AC-7 - Saga 正向执行成功
    假如 SagaOrchestrator 和 2 个 SagaStep 已创建
    当 执行 orchestrator.execute 步骤
    那么 两个 Step 按顺序执行
    并且 SagaContext 状态为 COMPLETED

  场景: AC-7 - Saga Step 失败触发补偿
    假如 SagaOrchestrator 和 3 个 SagaStep（第 2 个失败）已创建
    当 执行 orchestrator.execute 步骤
    那么 Step 1 的 compensate 被调用
    并且 SagaContext 状态为 COMPENSATED

  场景: AC-7 - SagaStatusChanged 事件定义
    假如 SagaStatusChanged 事件类已加载
    那么 事件包含 saga_id 和 saga_type 字段
    并且 事件类型为 SagaStatusChanged

  场景: AC-7 - SagaContext 不可变状态管理
    假如 SagaContext 实例已创建
    当 调用 update_status 方法
    那么 返回新的 SagaContext 实例
    并且 原实例状态不变

  # ============================================================================
  # AC-8: Saga 场景落地
  # ============================================================================

  场景: AC-8 - S01 文档处理 Saga 正向流程
    假如 4 个文档处理 SagaStep 已创建
    当 执行文档处理 Saga
    那么 所有步骤按序执行
    并且 SagaContext 状态为 COMPLETED

  场景: AC-8 - S01 文档处理 Saga 补偿流程
    假如 4 个文档处理 SagaStep（第 3 个失败）已创建
    当 执行文档处理 Saga
    那么 前 2 个步骤的 compensate 被调用
    并且 SagaContext 状态为 COMPENSATED
