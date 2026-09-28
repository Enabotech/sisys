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
  假如 构造 _FakeDataSourceAdapter 行为为 auth_failed（401/403）
  当 调用 fake adapter fetch 方法
  那么 抛出 ConfigurationError
  并且 错误码为 EXCEPTION_101
  并且 context 含 status_code 字段
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

# =============================================================================
# AC-5 领域异常与事件契约（异常 to_dict + 双通道配置）
# =============================================================================

场景: AC-5.1 - 异常 to_dict 序列化无敏感字段泄露
  假如 构造 ConfigurationError 含敏感 Key 字段 example.com 含 fake_test_marker
  当 调用异常 to_dict 序列化
  那么 序列化字典存在 context 键且 source_name 等于 tavily
  并且 序列化字典中不出现敏感 API Key 字串

场景: AC-5.2 - 异常 code 与子域归属一致（Code Range 校验）
  假如 遍历 src/domain/exceptions/data_source_exceptions.py 全部异常类
  当 用 _code_ranges.py 校验每个类的 code 字段所在子域
  那么 所有 4 个 DataSource 子域异常（EXCEPTION_410-413）code 与子域段 [410, 419] 一致
  并且 _CLASS_TO_SUBDOMAIN 注册条目与异常类数匹配

场景: AC-5.3 - 双通道事件登记一致性（yaml 与 ChannelRouter DEFAULT_MAPPINGS）
  假如 加载 configs/event_channels.yaml 的 events 块
  当 提取 yaml 中所有 event_type 与 ChannelRouter.DEFAULT_MAPPINGS 键对比
  那么 DataSourceFetched 事件在 yaml 与 DEFAULT_MAPPINGS 两处均登记
  并且 DataSourceFetchFailed 事件在 yaml 与 DEFAULT_MAPPINGS 两处均登记

# =============================================================================
# AC-6 集成测试（真实服务链路 + xdist_group 协作）
# =============================================================================

场景: AC-6.1 - 集成测试目录存在（tests/integration/external_services/data_sources）
  假如 检查 tests/integration/external_services/data_sources/ 路径
  当 列出该目录下所有 .py 测试文件
  那么 至少存在 test_adapters_http_chain.py
  并且 至少存在 test_china_nbs_crawler.py
  并且 这些测试文件声明 xdist_group("data-source-cache")（与 4-1b 验收测试共享组）

场景: AC-6.2 - 真实 Engine+Resolver+Redis 完整链路（已在 AC-4.x 覆盖，此场景断言集成测试调用分层一致）
  假如 检查所有 acceptance test 中 _run_engine 调用
  那么 _run_engine 调用次数 >= 4
  并且 integration 测试也使用 pytestmark 列表双标记

# =============================================================================
# AC-7 SDD 架构验证测试（六边形约束 + 端口注册 + 域零依赖）
# =============================================================================

场景: AC-7.2 - 8 个数据源端口全部注册到 composition_root（反射 _global_registry）
  假如 导入 src.composition_root._global_registry 模块级全局注册中心
  当 反射获取所有 name 以 data_source_ 开头且非 data_source_resolver 的端口
  那么 端口数 = 8 个含 worldbank imf eurostat uspto ipcc newsapi tavily china_nbs

场景: AC-7.3 - data_source 域层文件零外部依赖（AST 扫描）
  假如 收集 src/domain/{ports,value_objects,events,exceptions} 下 data_source 相关文件
  当 AST 扫描每个文件的 import 语句
  那么 所有 import 仅来自 typing/dataclasses/datetime/uuid/abc/enum 或 src.domain.* 项目内
  并且 零 httpx/redis/tenacity/sqlalchemy/pydantic 等第三方依赖
