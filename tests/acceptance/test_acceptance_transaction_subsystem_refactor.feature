# language: zh-CN
功能: Story 20-7 - 事务子系统重构

  作为系统架构师
  我要实现事务子系统的完整重构
  以确保事务边界显式化、跨存储操作可靠执行

  背景:
    假如 端口注册中心已初始化

  场景: AC-1 - UoW 不调用 close，由 Middleware 负责
    假如 PostgreSQLUnitOfWork 实例已创建
    当 执行 async with uow 代码块
    那么 uow.__aexit__ 不调用 session.close()

  场景: AC-3 - 多实例状态隔离
    假如 创建两个 PostgreSQLUnitOfWork 实例
    当 第一个实例执行 commit
    那么 第二个实例的 _committed 标志仍为 False

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
