# language: zh-CN
# Story 4.1b — Skills 数据采集基础设施（BDD 验收场景，覆盖 AC-1 ~ AC-8）

功能: Skills 数据采集基础设施
  作为工具工程师
  我希望 Skills 系统具备统一数据采集通道（DataSourcePort + 8 适配器 + Redis 缓存 + Engine.Execute $DATA_SOURCE 标记解析）
  以便后续 Skills 复用统一采集通道，Agent 自动获取权威、新鲜、可溯源的外部数据

背景:
  假如 数据采集基础设施已初始化（真实 DataSourceResolverService + 模拟数据源适配器 + 真实缓存 + InMemoryEventBus）

# =============================================================================
# AC-1 DataSourcePort 端口契约与值对象（基础契约）
# =============================================================================

场景: AC-1.1 - DataSourcePort @runtime_checkable Protocol 三方法契约
  假如 定义合规实现 _CompliantAdapter（fetch/get_metadata/health_check 三方法签名齐全）
  那么 isinstance(_CompliantAdapter(), DataSourcePort) 为真
  并且 三方法签名与契约完全一致

# =============================================================================
# AC-2 8 个数据源适配器（异常路径覆盖）
# =============================================================================

场景: AC-2.1 - 429 限流抛 DataSourceRateLimitError
  假如 工具元数据声明数据源 "newsapi"
  并且 数据源 "newsapi" 配置为限流
  当 该数据源唯一标记经 Engine Execute 阶段处理
  那么 抛出 DataSourceRateLimitError
  并且 错误码为 EXCEPTION_412

场景: AC-2.2 - 响应解析失败抛 DataSourceResponseError 且不重试
  假如 工具元数据声明数据源 "world-bank"
  并且 数据源 "world-bank" 配置为返回非法响应
  当 含标记的沙箱代码经 Engine Execute 阶段处理
  那么 抛出 DataSourceResponseError
  并且 错误码为 EXCEPTION_413
  并且 外部采集次数为 1

场景: AC-2.3 - 401/403 鉴权失败归 ConfigurationError
  假如 工具元数据声明数据源 "newsapi"
  并且 数据源 "newsapi" 配置为鉴权失败（401/403）
  当 含标记的沙箱代码经 Engine Execute 阶段处理
  那么 抛出 ConfigurationError
  并且 错误码为 EXCEPTION_101
  并且 异常消息不包含密钥字串

场景: AC-2.4 - TAVILY_API_KEY 缺失时条件注册跳过，Resolver 服务仍可用
  假如 TAVILY_API_KEY 未配置（composition_root 条件注册跳过）
  并且 工具元数据仅声明 "world-bank"
  并且 数据源 "world-bank" 可用且 "tavily" 未注册
  当 经 Resolver 采集通道处理 world-bank 查询
  那么 world-bank 正常采集成功（不抛 ConfigurationError）
  并且 Resolver 仍可解析其他已注册数据源

场景: AC-2.5 - 配置缺失构造 TavilyAdapter 立即抛 ConfigurationError
  当 以缺失 API Key 构造 TavilyAdapter
  那么 抛出 ConfigurationError
  并且 错误码为 EXCEPTION_101
  并且 异常消息不包含密钥字串
  并且 Resolver 数据源映射不含 tavily 时查询返回白名单违规

# =============================================================================
# AC-3 数据缓存层与新鲜度评分
# =============================================================================

场景: AC-3.1 - 缓存命中二次执行不重复采集
  假如 工具元数据声明数据源 "world-bank"
  当 同一查询连续两次经采集通道处理
  那么 第二次结果 cache_hit 为真
  并且 外部采集次数为 1

场景: AC-3.2 - 缓存 TTL 过期触发重新采集
  假如 工具元数据声明数据源 "world-bank"
  并且 查询结果已缓存且已超过 TTL
  当 同一查询再次经采集通道处理
  那么 数据新鲜度判定为 stale
  并且 外部采集次数增加 1

# =============================================================================
# AC-4 Engine.Execute $DATA_SOURCE 增强（Happy Path + 异常路径）
# =============================================================================

场景: AC-4.1 - Happy Path 标记采集与注入
  假如 工具元数据声明数据源 "world-bank"
  当 含标记的沙箱代码经 Engine Execute 阶段处理
  那么 注入后代码包含 DATA_SOURCES 数据前言
  并且 输出元数据含 source 与 freshness 与 confidence
  并且 已发布 DataSourceFetched 事件

场景: AC-4.2 - 白名单外数据源抛 BusinessRuleViolationError
  假如 工具元数据声明数据源 "world-bank"
  当 沙箱代码引用白名单外数据源 "newsapi"
  那么 抛出 BusinessRuleViolationError
  并且 错误码为 EXCEPTION_207

场景: AC-4.3 - 单源不可用部分失败收敛
  假如 工具元数据声明数据源 "world-bank" 与 "eurostat"
  并且 数据源 "eurostat" 配置为不可用
  当 含双源标记的沙箱代码经 Engine Execute 阶段处理
  那么 可用数据源数据已注入
  并且 已发布 DataSourceFetchFailed 事件
