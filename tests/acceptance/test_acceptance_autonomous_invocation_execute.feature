# language: zh-CN
功能: Story 1.14c - 自主调用循环 execute 实现

  作为系统架构师
  我想要实现会话命名空间执行与状态快照
  以便任务在隔离环境中执行，状态可持久化和恢复

  背景:
    假如 Story 1.14a trigger 实现已完成
    假如 Story 1.14b route 实现已完成
    假如 ExecuteService 已实现并配置了事件发布器
    假如 DockerSandboxAdapter 已配置

  # =========================================================================
  # AC-1: 会话命名空间隔离
  # =========================================================================

  场景: AC-1 - ExecuteService 在沙箱中执行任务
    假如 沙箱适配器是 DockerSandboxAdapter
    假如 系统接收到 Routed 事件（session_id: test-session-123）
    当 ExecuteService 处理该 Routed 事件
    那么 应该为 session test-session-123 启动沙箱容器
    并且 任务应该在沙箱中执行
    并且 执行后容器应该停止

  场景: AC-1 - 相同 session_id 共享命名空间
    假如 已有运行中的沙箱（session: test-session-123）
    假如 系统接收到新的 Routed 事件（session_id: test-session-123）
    当 ExecuteService 处理该事件
    那么 应该复用同一个沙箱容器
    并且 不应该启动新容器

  场景: AC-1 - 沙箱隔离 100% 无状态泄漏
    假如 沙箱 A 执行任务修改了内部状态
    假如 沙箱 B 执行独立任务
    当 验证两个沙箱的隔离性
    那么 沙箱 A 的状态变化不应该影响沙箱 B

  # =========================================================================
  # AC-2: 状态快照持久化
  # =========================================================================

  场景: AC-2 - 执行后创建 CheckpointSnapshot
    假如 ExecuteService 配置了 RedisSnapshotStore
    假如 任务执行成功完成
    当 状态快照被创建
    那么 CheckpointSnapshot 应该保存到 Redis
    并且 快照应该包含执行结果

  场景: AC-2 - 快照延迟 P95 小于 50ms
    假如 CheckpointSnapshot 已准备好保存
    假如 我执行 1000 次快照保存操作
    那么 P95 延迟应该小于 50ms

  场景: AC-2 - 快照可恢复
    假如 已保存的 CheckpointSnapshot（session: test-session-123）
    当 调用 ExecuteService.restore_snapshot
    那么 原始状态应该被恢复

  场景: AC-2 - 快照版本递增
    假如 session 已存在快照（版本 1）
    当 创建新快照
    那么 新快照版本应该是 2

  # =========================================================================
  # AC-3: 执行事件发布
  # =========================================================================

  场景: AC-3 - Executed 事件在执行完成后发布
    假如 任务执行完成
    当 ExecuteService 发布执行结果
    那么 Executed 事件应该被发布
    并且 事件应该包含 session_id
    并且 事件应该包含 business_event_type

  场景: AC-3 - 下游监听器发布 ToolExecuted
    假如 business_event_type 为 ToolExecuted
    假如 AutoExecuteCompletedListener 收到 Executed 事件
    当 监听器处理该事件
    那么 应该发布 ToolExecuted 领域事件

  场景: AC-3 - 下游监听器发布 DocumentProcessed
    假如 business_event_type 为 DocumentProcessed
    假如 AutoExecuteCompletedListener 收到 Executed 事件
    当 监听器处理该事件
    那么 应该发布 DocumentProcessed 领域事件

  场景: AC-3 - 下游监听器发布 AgentDecided
    假如 business_event_type 为 AgentDecided
    假如 AutoExecuteCompletedListener 收到 Executed 事件
    当 监听器处理该事件
    那么 应该发布 AgentDecided 领域事件

  场景: AC-3 - Executed 携带完整执行上下文
    假如 任务执行完成
    当 发布 Executed 事件
    那么 事件应该包含 execution_result
    并且 事件应该包含 cost_estimate
    并且 事件应该包含 latency_ms

  # =========================================================================
  # AC-4: execute 与 trigger/route 解耦
  # =========================================================================

  场景: AC-4 - ExecuteService 仅发布事件不调用 trigger/route
    假如 ExecuteService 完成执行
    当 发布 Executed 事件
    那么 不应该直接调用任何 trigger 或 route 函数
    并且 通信应该通过事件总线异步进行

  场景: AC-4 - 六边形架构合规 - 领域层零依赖
    假如 我验证 ExecuteService 源代码
    那么 ExecuteService 不应该导入任何基础设施层模块
    并且 SandboxExecutor 端口应该位于 interfaces 层
    并且 DockerSandboxAdapter 应该位于 infrastructure 层

  场景: AC-4 - ExecuteService 使用 Protocol 依赖倒置
    假如 我检查 ExecuteService 实现
    那么 应该使用 SandboxExecutor 而非具体实现
    并且 应该使用 SnapshotRepositoryProtocol 而非具体实现
    并且 领域层定义接口，基础设施层实现

  # =========================================================================
  # AC-5: 执行性能要求
  # =========================================================================

  场景: AC-5 - 沙箱启动延迟 P95 小于 100ms
    假如 我执行 1000 次沙箱启动操作
    那么 沙箱启动延迟 P95 应该小于 100ms

  场景: AC-5 - 状态快照延迟 P95 小于 50ms
    假如 我执行 1000 次快照保存操作
    那么 状态快照延迟 P95 应该小于 50ms

  场景: AC-5 - 吞吐量支持 100 executions/second
    假如 事件总线每秒发送 100 个 Routed 事件
    当 ExecuteService 持续处理这些事件
    那么 系统应该能够实时处理所有事件而不会积压

  场景: AC-5 - 执行幂等性
    假如 我有相同的 Routed 事件输入
    当 连续执行 10 次任务
    那么 所有 10 次结果应该完全相同
