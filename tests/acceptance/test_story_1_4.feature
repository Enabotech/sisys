Feature: Redis Cache Layer (Story 1.4)

  作为系统架构师
  我想要实现 Redis 高速缓存层（L1 存储）
  以便系统可以将会话状态、语义缓存和公共黑板数据存储在高速缓存中

  Background:
    Given 所有存储服务使用 fakeredis

  # =========================================================================
  # AC-2: 会话状态存储
  # =========================================================================

  Scenario: 会话状态保存与恢复
    When 调用 SessionStorage.save 保存会话 "session-001"
    And 调用 SessionStorage.load 加载会话 "session-001"
    Then 返回的会话状态与保存的一致

  Scenario: 会话状态删除
    Given 会话状态 "session-002" 已保存
    When 调用 SessionStorage.delete 删除会话 "session-002"
    And 调用 SessionStorage.load 加载会话 "session-002"
    Then 返回 None

  Scenario: 会话状态过期
    Given 会话状态 "session-003" 已保存并设置 TTL 为 1 秒
    When 推进 fakeredis 时间使 TTL 过期
    And 调用 SessionStorage.load 加载会话 "session-003"
    Then 返回 None

  # =========================================================================
  # AC-3: 语义缓存服务
  # =========================================================================

  Scenario: 语义缓存命中
    Given 语义缓存已存储查询结果
    When 使用相同查询向量调用 SemanticCache.get
    And 相似度阈值满足要求
    Then 返回缓存结果

  Scenario: 语义缓存未命中
    Given 语义缓存无匹配结果
    When 调用 SemanticCache.get 查询缓存（无匹配）
    Then 返回 None

  Scenario: 语义缓存命中率统计
    Given 注入 EventMetricsCollector 到 SemanticCache
    And 执行 3 次缓存命中和 2 次缓存未命中
    When 查询 EventMetricsCollector.hit_rate
    Then 返回命中率 0.6

  # =========================================================================
  # AC-4: 公共黑板服务
  # =========================================================================

  Scenario: 公共黑板多 Agent 并发写入
    Given Agent "agent-A" 和 Agent "agent-B" 向 conversation "conv-001" 发布消息
    When 调用 PublicBlackboard.get 读取 conversation "conv-001"
    Then 返回所有 Agent 发布的消息
    And 消息按时间戳排序

  Scenario: 公共黑板版本号递增
    Given Agent "agent-A" 向 conversation "conv-002" 发布第 1 条消息
    When Agent "agent-A" 再次向 conversation "conv-002" 发布消息
    Then 返回的版本号递增为 2

  # =========================================================================
  # AC-1: 优雅降级（细化为 3 个子场景）
  # =========================================================================

  Scenario: SessionStorage 连接失败优雅降级
    Given Redis 服务不可用
    When 调用 SessionStorage.save 保存会话
    Then 不抛出异常
    And 返回 None

  Scenario: SemanticCache 连接失败优雅降级
    Given Redis 服务不可用
    When 调用 SemanticCache.get 查询缓存
    Then 不抛出异常
    And 返回 None

  Scenario: PublicBlackboard 连接失败优雅降级
    Given Redis 服务不可用
    When 调用 PublicBlackboard.post 发布消息
    Then 不抛出异常
    And 返回 0

  # =========================================================================
  # AC-5: Redis 键命名规范与清理
  # =========================================================================

  Scenario: Redis 键命名规范
    Given 所有存储服务使用 KeyBuilder 构建键名
    When 构建键名 namespace="session", key="abc-123"
    Then 键名遵循 "sisys:{namespace}:{key}" 格式

  Scenario: Redis 键批量清理
    Given 命名空间 "session" 下有 5 个键
    When 调用 RedisCleanup.cleanup_namespace("session")
    Then 返回删除的键数量为 5
    And 所有 "session" 命名空间下的键被删除
