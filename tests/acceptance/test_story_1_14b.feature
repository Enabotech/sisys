# language: zh-CN
功能: Story 1.14b - 自主调用循环 route 实现

  作为系统架构师
  我想要实现 session_id 哈希/语义路由机制
  以便任务可以路由至目标 Agent 或工具

  背景:
    假如 Story 1.14a trigger 实现已完成
    假如 Story 1.6 Qdrant bge-m3 嵌入已集成
    假如 RouteService 已实现并配置了事件发布器
    假如 HashRouter 已配置节点列表

  # =========================================================================
  # AC-1: 哈希路由机制
  # =========================================================================

  场景: AC-1 - 相同 session_id 路由到同一节点
    假如 HashRouter 配置了节点列表 [node-A, node-B, node-C]
    假如 我有 session_id 为 "session-consistency-test"
    当 HashRouter 执行路由
    那么 连续 10 次路由调用应该返回相同的节点
    并且 一致性保证应该达到 100%

  场景: AC-1 - 不同 session_id 均匀分布到节点
    假如 HashRouter 配置了 3 个节点
    假如 我有 1000 个不同的 session_id
    当 执行路由操作
    那么 每个节点应该获得约 1/3 的请求（允许 10% 偏差）

  场景: AC-1 - Triggered 事件触发路由决策
    假如 系统接收到 Triggered 事件（session_id: session-001）
    当 RouteService 监听并接收该事件
    那么 RouteService 应该基于 session_id 计算一致性哈希
    并且 应该发布 Routed 事件到下游 execute 机制

  场景: AC-1 - 节点动态添加后最小化重路由
    假如 HashRouter 配置了 [node-A, node-B]
    假如 100 个 session_id 已路由到节点
    当 添加 node-C 到哈希环
    那么 受影响的 session_id 应该少于 50%（一致性哈希特性）

  场景: AC-1 - 节点移除后自动重路由
    假如 HashRouter 配置了 [node-A, node-B, node-C]
    假如 100 个 session_id 已路由到节点
    当 移除 node-B
    那么 受影响的 session_id 应该自动重新路由到 node-A 或 node-C

  # =========================================================================
  # AC-2: 语义路由机制
  # =========================================================================

  场景: AC-2 - 基于任务上下文语义相似度路由
    假如 SemanticRouter 配置了候选列表 [CEO Agent, CFO Agent, CTO Agent]
    假如 我有任务上下文（task_type: financial_analysis）
    当 SemanticRouter 执行语义路由
    那么 应该选择 CFO Agent 作为路由目标

  场景: AC-2 - 语义路由匹配度验证
    假如 SemanticRouter 配置了 10 个候选
    假如 我有 100+ 个测试样本（已人工标注正确答案）
    当 执行语义路由
    那么 匹配度应该达到 95% 或以上（相对于人工标注基准）

  场景: AC-2 - 语义路由无候选时返回空
    假如 SemanticRouter 候选列表为空
    假如 我有任务上下文
    当 SemanticRouter 执行路由
    那么 应该返回空目标和大海捞针

  场景: AC-2 - 语义路由缓存命中
    假如 相同任务上下文已执行过一次路由
    假如 缓存中已存在该上下文的结果
    当 再次执行路由
    那么 第二次路由应该使用缓存结果（延迟应该显著降低）

  场景: AC-2 - 语义路由描述提取优先级
    假如 任务上下文同时包含 description 和 task_type
    当 SemanticRouter 提取描述
    那么 description 应该优先于 task_type

  # =========================================================================
  # AC-3: 路由决策日志
  # =========================================================================

  场景: AC-3 - 路由决策日志记录完成
    假如 RouteService 执行了一次路由决策
    假如 路由结果为 route_type: semantic, route_target: cfo-agent, route_score: 0.95
    当 路由决策完成
    那么 应该创建 RoutingDecisionLog 记录
    并且 记录应该包含 task_id, session_id, route_type, route_target, route_score

  场景: AC-3 - 路由决策日志字段完整性
    假如 我创建 RoutingDecisionLog
    当 验证日志完整性
    那么 应该包含 log_id, task_id, session_id, route_type, route_target, route_score
    并且 应该包含 cost_estimate, latency_ms, timestamp

  场景: AC-3 - 路由决策日志 WORM 归档标识
    假如 RoutingDecisionLog 已创建
    那么 worm_storage_ref 字段应该被设置
    并且 应该支持合规要求的 7 年存储

  场景: AC-3 - 路由决策日志可检索性
    假如 我有多个路由决策日志
    当 按 session_id 查询
    那么 应该返回该 session 的所有路由记录
    当 按时间范围查询
    那么 应该返回该时间范围内的所有路由记录

  # =========================================================================
  # AC-4: 路由与 trigger/execute 解耦
  # =========================================================================

  场景: AC-4 - RouteService 仅发布事件不调用 execute
    假如 RouteService 已完成路由决策
    当 发布 Routed 事件
    那么 不应该直接调用任何 execute 函数
    并且 通信应该通过事件总线异步进行

  场景: AC-4 - Routed 事件定义完整
    假如 我验证 Routed 事件 Schema
    那么 应该包含 event_id, session_id, route_type, route_target, route_score
    并且 应该包含 task_context, trigger_event_type

  场景: AC-4 - 六边形架构合规 - 领域层零依赖
    假如 我验证 RouteService 源代码
    那么 RouteService 不应该导入任何基础设施层模块
    并且 HashRouter 和 SemanticRouter 应该位于基础设施层
    并且 Routed 事件不应该导入任何外部框架

  场景: AC-4 - RouteService 使用 Protocol 依赖倒置
    假如 我检查 RouteService 实现
    那么 应该使用 EventPublisherProtocol 而非具体实现
    并且 应该使用 HashRouterProtocol/SemanticRouterProtocol 而非具体实现
    并且 领域层定义接口，基础设施层实现

  # =========================================================================
  # AC-5: 路由性能要求
  # =========================================================================

  场景: AC-5 - 路由决策延迟 P95 小于 50ms
    假如 我发送 1000 个 Triggered 事件到 RouteService
    当 RouteService 处理每个事件
    那么 端到端路由决策延迟 P95 应该小于 50ms

  场景: AC-5 - 吞吐量支持 1000 decisions/second
    假如 事件总线每秒发送 1000 个 Triggered 事件
    当 RouteService 持续处理这些事件
    那么 系统应该能够实时处理所有事件而不会积压

  场景: AC-5 - 哈希路由延迟 P95 小于 5ms
    假如 我执行 1000 次哈希路由操作
    当 HashRouter 处理每次请求
    那么 P95 延迟应该小于 5ms

  场景: AC-5 - 语义路由延迟 P95 小于 50ms（不含嵌入计算）
    假如 嵌入向量已预计算
    假如 我执行 1000 次语义路由操作
    当 SemanticRouter 计算余弦相似度
    那么 P95 延迟应该小于 50ms

  场景: AC-5 - 路由决策幂等性
    假如 我有相同的 Triggered 事件输入
    当 连续执行 10 次路由决策
    那么 所有 10 次结果应该完全相同
