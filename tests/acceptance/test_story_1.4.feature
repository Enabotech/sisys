Feature: Redis Cache Layer (Story 1.4)

  作为系统架构师
  我想要实现 Redis 高速缓存层（L1 存储）
  以便系统可以将会话状态、语义缓存和公共黑板数据存储在高速缓存中

  Background:
    Given Redis 服务可用

  Scenario: 会话状态保存与恢复
    When 调用 SessionStorage.save 保存会话状态
    And 调用 SessionStorage.load 加载同一会话
    Then 返回的会话状态与保存的一致

  Scenario: 会话状态过期
    Given 会话状态已保存并设置短 TTL
    When TTL 过期后调用 SessionStorage.load
    Then 返回 None

  Scenario: 会话状态删除
    Given 会话状态已保存
    When 调用 SessionStorage.delete 删除会话
    And 调用 SessionStorage.load 加载
    Then 返回 None

  Scenario: 语义缓存命中
    Given 语义缓存已存储查询结果
    When 使用相同查询向量调用 SemanticCache.get
    And 相似度阈值满足要求
    Then 返回缓存结果

  Scenario: 语义缓存未命中
    Given 语义缓存无匹配结果
    When 调用 SemanticCache.get
    Then 返回 None

  Scenario: 语义缓存命中率统计
    Given 多次调用 SemanticCache.get
    When 查询 EventMetricsCollector.hit_rate
    Then 返回正确的命中率值 (hits / (hits + misses))

  Scenario: 公共黑板多 Agent 并发写入
    Given 多个 Agent 同时向同一 conversation_id 发布消息
    When 调用 PublicBlackboard.get 读取消息
    Then 返回所有 Agent 发布的消息
    And 消息按时间戳排序

  Scenario: 公共黑板版本号递增
    Given Agent 发布消息到公共黑板
    When 同一 Agent 再次发布消息到同一 conversation_id
    Then 返回的版本号递增

  Scenario: Redis 连接失败优雅降级
    Given Redis 服务不可用
    When 调用存储服务方法
    Then 不抛出异常阻塞业务
    And 记录错误日志

  Scenario: Redis 键命名规范
    Given 所有存储服务使用 KeyBuilder 构建键名
    When 构建键名
    Then 键名遵循 "sisys:{namespace}:{key}" 格式

  Scenario: Redis 键批量清理
    Given 多个 Redis 键属于同一命名空间
    When 调用 RedisCleanup.cleanup_namespace
    Then 返回删除的键数量
    And 所有命名空间下的键被删除
