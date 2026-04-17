# language: zh-CN
功能: Redis 缓存层

  作为系统架构师
  我想要实现 Redis 高速缓存层（L1 存储）
  以便系统可以将会话状态、语义缓存和公共黑板数据存储在高速缓存中

  背景:
    假如 所有存储服务使用 fakeredis

  # =========================================================================
  # AC-2: 会话状态存储
  # =========================================================================

  场景: 会话状态保存与恢复
    当 调用 SessionStorage.save 保存会话 "session-001"
    并且 调用 SessionStorage.load 加载会话 "session-001"
    那么 返回的会话状态与保存的一致

  场景: 会话状态删除
    假如 会话状态 "session-002" 已保存
    当 调用 SessionStorage.delete 删除会话 "session-002"
    并且 调用 SessionStorage.load 加载会话 "session-002"
    那么 返回 None

  场景: 会话状态过期
    假如 会话状态 "session-003" 已保存并设置 TTL 为 1 秒
    当 推进 fakeredis 时间使 TTL 过期
    并且 调用 SessionStorage.load 加载会话 "session-003"
    那么 返回 None

  # =========================================================================
  # AC-3: 语义缓存服务
  # =========================================================================

  场景: 语义缓存命中
    假如 语义缓存已存储查询结果
    当 使用相同查询向量调用 SemanticCache.get
    并且 相似度阈值满足要求
    那么 返回缓存结果

  场景: 语义缓存未命中
    假如 语义缓存无匹配结果
    当 调用 SemanticCache.get 查询缓存（无匹配）
    那么 返回 None

  场景: 语义缓存命中率统计
    假如 注入 EventMetricsCollector 到 SemanticCache
    并且 执行 3 次缓存命中和 2 次缓存未命中
    当 查询 EventMetricsCollector.hit_rate
    那么 返回命中率 0.6

  # =========================================================================
  # AC-4: 公共黑板服务
  # =========================================================================

  场景: 公共黑板多 Agent 并发写入
    假如 Agent "agent-A" 和 Agent "agent-B" 向 conversation "conv-001" 发布消息
    当 调用 PublicBlackboard.get 读取 conversation "conv-001"
    那么 返回所有 Agent 发布的消息
    并且 消息按时间戳排序

  场景: 公共黑板版本号递增
    假如 Agent "agent-A" 向 conversation "conv-002" 发布第 1 条消息
    当 Agent "agent-A" 再次向 conversation "conv-002" 发布消息
    那么 返回的版本号递增为 2

  # =========================================================================
  # AC-1: 优雅降级（细化为 3 个子场景）
  # =========================================================================

  场景: SessionStorage 连接失败优雅降级
    假如 Redis 服务不可用
    当 调用 SessionStorage.save 保存会话
    那么 不抛出异常
    并且 返回 None

  场景: SemanticCache 连接失败优雅降级
    假如 Redis 服务不可用
    当 调用 SemanticCache.get 查询缓存
    那么 不抛出异常
    并且 返回 None

  场景: PublicBlackboard 连接失败优雅降级
    假如 Redis 服务不可用
    当 调用 PublicBlackboard.post 发布消息
    那么 不抛出异常
    并且 返回 0

  # =========================================================================
  # AC-5: Redis 键命名规范与清理
  # =========================================================================

  场景: Redis 键命名规范
    假如 所有存储服务使用 KeyBuilder 构建键名
    当 构建键名 namespace="session", key="abc-123"
    那么 键名遵循 "sisys:{namespace}:{key}" 格式

  场景: Redis 键批量清理
    假如 命名空间 "session" 下有 5 个键
    当 调用 RedisCleanup.cleanup_namespace("session")
    那么 返回删除的键数量为 5
    并且 所有 "session" 命名空间下的键被删除
