# Story 5.4: EIP 弹性隔离协议基础

**Status:** `done`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 安全工程师,
**I want** 系统执行弹性视角隔离协议基础（L4 硬隔离默认）,
**So that** MVP 阶段支持 Agent 隔离。

### 业务价值

Epic 5「单 Agent 战略规划能力」价值组的安全基座环：5-1/5-2/5-3 交付了 Agent 实例化→档案加载→任务执行闭环，本 Story 交付**弹性隔离协议（EIP）基础**——四级隔离等级模型（L4/L3/L2/L1）、Agent 出生即 L4 硬隔离默认、隔离状态 Redis 持久化、用户显式请求的隔离等级切换与 `IsolationLevelSwitched` 领域事件发布。这是下游 5.5（三重硬隔离强制执行与穿透测试）、5.6（隔离切换日志审计）、5.11（SAP 传输，SAPMessage.isolation_level 已复用同一枚举）与 V1 FR-AC-09（动态升降级触发）的协议底座。EIP 是项目申报的方法专利之一（prd.md L1164/1364），本 Story 落地其 MVP 骨架。

**范围权威**：epics_v1.0.md L1591-1630（AC + 测试要求）；or.md §一.1.[5]（L18 四级等级与触发条件）、§四.1.[4]/§四.3.[3]（L280/L288 弹性隔离动态调整与三重硬约束）、§八.7（L616-620 AGENT 视角隔离约束——L617 默认 L4 硬隔离）、§一.2.(9)（L30 IsolationSwitchLog 实体——归 5.6）、L48（IsolationLevelSwitched 事件）、L135-136（隔离切换事件流转——注意 L136 链中的 `IsolationLevelSwitchRequired` 是规划中间事件，代码骨架未定义，MVP 用户请求通道直发 Switched 不经 Required）；architecture.md §5（L643-666 四级表/触发/自动恢复）；sisys-core-domain-design.md §17.3.3（L1192-1266 EIPExecutor 伪码）与 L1455-1460（eip_config）。

### 范围边界（与后续 Story 的精确切分）

| 能力 | 本 Story（5.4） | 后续 Story |
|------|----------------|-----------|
| 四级隔离等级模型（策略表：Prompt/工具/数据三维度） | ✅ 领域模型 + 查询 | 5.5 消费 |
| 默认 L4 硬隔离（实例化即初始化） | ✅ | — |
| 隔离状态 Redis 持久化（含 TTL） | ✅ | — |
| 隔离状态查询（隔离检查入口，P95<100ms） | ✅ | 5.5 执行前强制检查消费 |
| 用户显式请求切换等级 + `IsolationLevelSwitched` 事件发布 | ✅（MVP 唯一触发通道） | — |
| 三重硬隔离**强制执行**（Prompt/工具/数据访问拦截、跨 Agent 探针） | ❌ 不做 | 5.5（P0-5） |
| IsolationSwitchLog 切换日志实体、多维检索、WORM 归档 | ❌ 不做 | 5.6（P1-6） |
| 动态触发（关键词频率>5%/任务依赖>0.7/SYS 命令）与 30 分钟自动恢复 | ❌ 不做 | V1（FR-AC-09 P1）/V2 |
| L1 融合态开放 | ❌ MVP 禁用（446 拒绝） | V2（SYS 监督+强制审计设施先行） |

---

## 🔗 前置依赖（全部 ✅ 已完成，无阻塞）

| 依赖 | 组件 | 用途 | 状态 |
|------|------|------|------|
| Story 5.1 | `Agent` 实体（`src/domain/entities/agent.py` L39-175，**无隔离字段——本 Story 不修改该实体**）+ `AgentRepository`（domain/ports/agent_repository.py L31-84：save(agent, ttl)/get_by_id/delete/exists）+ `RedisAgentRepository`（src/infrastructure/storage/redis/redis_agent_repository.py L40-185——本 Story 仓储照抄模式）+ `InstantiateAgentUseCase`（src/application/use_cases/agent_instantiation.py L59-147，现三依赖——本 Task 4 注入改造）+ agent 异常段 440-443 + CLI 骨架（`src/entrypoints/agent_cli.py`，instantiate/load-profile/run-task 三子命令） | 实例化链路与隔离初始化接线位；443 AgentNotFoundError 复用；CLI 子命令模式照抄 | ✅ done |
| Story 5.2 | `AgentProfileUseCase` 等档案链（本 Story 无直接消费）+ 验收测试形态基准（FEATURE 常量 + @scenario 显式绑定 + context dict） | 验收测试形态 | ✅ done |
| Story 5.3 | `AgentWorkflowService`/`RunAgentWorkflowUseCase`（本 Story 不修改）+ 事件 kw_only 必填纪律（agent_events.py L70-100 AgentProfileLoaded 先例）+ `_RecordingEventPublisher` 手工装配先例 + SCOPED 捕获留项移交（风险 #4「其 SCOPED 归属同评估」） | 事件纪律收紧基准；D7 评估义务 | ✅ done |
| Story 1.2 | `IsolationLevel` 枚举（`src/domain/events/enums.py` L39-45：L4_HARD/L3_SOFT/L2_COLLAB/L1_FUSED，str,Enum）——**SSOT 唯一定义点，直接复用禁止新建** | 等级枚举 | ✅ done |
| Story 1.x 骨架 | `IsolationLevelSwitched` 事件预置（`src/domain/events/isolation_events.py` L16-43，**旧风格 default_factory——本 Story 纪律收紧**）+ yaml/channel_router 双登记已就绪（configs/event_channels.yaml L197-201 + src/infrastructure/messaging/channel_router.py L255-260，RELIABLE 单通道）+ `AutoTriggerHandler._registered_event_types` 字符串清单已含该事件（auto_trigger_handler.py L68） | 事件复用（零新建零登记，仅收紧纪律） | ✅ done |
| 事件总线 | `EventPublisher.publish(event) -> PublishResult`（domain/ports/event_publisher.py L26）+ `DualChannelEventBus`（infrastructure/messaging/dual_channel_event_bus.py L20-65）+ `InMemoryEventBus`（真实类——inmemory_event_bus.py L19；子类捕获先例是 5-1/5-2 单测 `_TracingEventBus`，5-3 验收/集成的 `_RecordingEventPublisher`/`_RecordingEventBus` 为手写 duck-typing 类，非子类——R1-F14 校准；R4-N3 行号终校） | 切换事件发布 | ✅ done |
| 异常体系 | agent 子域段 446-449 **显式预留「5.4-5.5 EIP 隔离」**（`src/domain/exceptions/_code_ranges.py` L122） | 新异常 446/447 码位 | ✅ 就绪 |

**移交给本 Story 的留项（必须处置）**：

| # | 留项 | 来源 | 本 Story 处置 |
|---|------|------|--------------|
| 1 | **D6 残余**：`AgentConfig` 直构造守卫缺口——`default_isolation_level` 无枚举校验（裸 str）/ 标量字段非 str 直构造（name=123 裸 AttributeError）/ 空白串未归一 / `_required_str` 不 strip | 5-1 R2 收窄（触发=5.3/5.4；5-3 未处置） | **Task 1 TDD 循环 E 全量回填核销**（isolation 枚举校验 + 标量类型守卫——统一 440 分码对齐文件先例 R1-F03；「空白串未归一」经核实为「拦截语义已存在（440）」——钉子测试锁定即核销） |
| 2 | **D7**：SINGLETON 用例捕获 SCOPED 仓储（captive dependency；R2 科学性复审判明无状态仓储翻 SINGLETON 可廉价消解但属架构级 lifetime 决策） | 5-1（触发=5.4 决策回迁评估）；5-3 风险 #4（skill_loader/tool_execution_service SCOPED 归属同评估） | **Task 0 评估 + DC-7 决策落地**（新增 isolation_repository 直接 SINGLETON 从源头避免；存量 agent_repository/skill_loader 维持注记——评估关闭） |
| 3 | `session_storage` + RedisSessionStorage 休眠（deferred-work.md L130，5-3 续期触发=5-4+ 多轮会话） | 5-1→5-3 | **再续期**：本 Story 是隔离协议非多轮会话（IsolationState 是协议状态非会话状态，见 DC-1）；触发移至真正的多轮会话 Story |
| 4 | 工具熔断挂点评估（deferred-work.md L18：建议 5.4/5.5 EIP 实施时评估挂点或独立小 Story） | Epic 4 | **Task 0 评估登记**：工具熔断（连续 3 次校验失败熔断）属 tool_execution 域装饰链，与 EIP 隔离等级无协议耦合——挂点不成立，维持 deferred 归独立小 Story |

---

## 🔗 现有代码继承（必须复用，禁止重复定义）

> ⚠️ **防重复造轮子清单**——以下组件已存在，dev agent 只可「直接复用 / 参考照抄」，禁止新建同义组件。

| 组件 | 文件路径 | 复用方式 |
|------|---------|---------|
| `IsolationLevel` 枚举（L4_HARD="L4"/L3_SOFT="L3"/L2_COLLAB="L2"/L1_FUSED="L1"） | `src/domain/events/enums.py` L39-45 | **直接复用**——等级枚举 SSOT（实体/VO/事件/CLI 全部引用此枚举；SAPMessage.isolation_level 同源） |
| `IsolationLevelSwitched` 事件 + yaml/DEFAULT_MAPPINGS 双登记 | `src/domain/events/isolation_events.py` L16-43、`configs/event_channels.yaml` L197-201、`src/infrastructure/messaging/channel_router.py` L255-260 | **复用 + 纪律收紧**（不新建事件、不新增登记——DC-6：agent_id/previous_level/target_level/trigger_reason 收紧 kw_only 必填，对齐 AgentProfileLoaded 先例） |
| `RedisAgentRepository` 仓储模式（build_key namespace + Hash 单 field latest JSON + MULTI/EXEC hset/expire 原子提交 + TTL 防御校验闭区间 60~2592000 抛 440 + 显式重建 UUID/Enum/datetime + 连接异常包装 `StorageError(cause=exc)` 禁静默——**注意 `from exc` 仅设 `__cause__`，DomainError.cause 属性须构造参数传递**） | `src/infrastructure/storage/redis/redis_agent_repository.py` L40-185 | **参考照抄**——`RedisIsolationRepository` 同款形态（namespace 换 "isolation"） |
| `build_key(namespace, *parts)` 键构建（`sisys:{namespace}:{parts}`） | `src/infrastructure/storage/redis/key_builder.py` L11-22 | **直接复用**——隔离键 `build_key("isolation", str(agent_id))` → `sisys:isolation:{agent_id}` |
| `RedisAdapter`（L1CachePort 实现 + `raw_client` property 逃生口供 Hash/pipeline） | `src/infrastructure/storage/redis/redis_adapter.py` L16-111 | **直接复用**——仓储构造注入（组合根 SINGLETON redis_adapter） |
| `AgentRepository` 端口四方法形态（save(ttl)/get_by_id/delete/exists + docstring 异常契约） | `src/domain/ports/agent_repository.py` L31-84 | **参考照抄**——`IsolationRepository` Protocol 同款四方法形态 |
| `PortSpec` 全参数注册 + `# === Story 5.x ===` 区段注释惯例 | `src/composition_root.py` L2678-2849（Agent 系列注册区） | **参考照抄**——`isolation_repository`/`isolation_management_service` 两端口注册追加至该区段 |
| 端口契约测试 11 维度 + `_DummyResolver`（fakeredis 注入 redis_adapter） | `tests/contracts/test_port_contract_agent_repository.py`（116 行样板——R4-N4 行数终校） | **参考照抄**——两份新契约测试同款结构 |
| `register_port` / `resolve` / `Lifetime` | `src/domain/ports/registry.py` L27-53/L132-158、`src/domain/ports/resolver.py` L63-109 | **直接复用** |
| `AgentNotFoundError`(443)/`AgentConfigError`(440) | `src/domain/exceptions/agent_exceptions.py` L164-197/L40-78 | **直接复用**——切换时 agent 不存在→443；TTL 越界→440（仓储防御校验同款） |
| `AgentRoleNotSupportedError`(441) 构造器形态（level + supported 列表 + context 结构化） | `src/domain/exceptions/agent_exceptions.py` L81-116 | **参考照抄**——`IsolationLevelNotSupportedError`(446) 同款形态 |
| CLI 子命令骨架（argparse + 守卫先于 bootstrap + `_parse_role` 两道守卫模式 + 退出码 + `_close_connection_pools`） | `src/entrypoints/agent_cli.py`（instantiate/load-profile/run-task 三子命令） | **扩展**——追加 `isolation-status`/`set-isolation` 两子命令；`_parse_isolation_level` 照抄 `_parse_role` 两道守卫 |
| `_RecordingEventPublisher`（手写 duck-typing 事件捕获类——`published_events` 列表 + `publish` 返回真实 `PublishResult`，直接实现 EventPublisher 端口契约；如需真实类子类形态参照 `_TracingEventBus`——test_agent_instantiation.py L50-69） | 5-3 验收/集成先例（`tests/integration/test_integration_agent_workflow.py` L76-93 等，全仓 4 处先例均手写类） | **参考照抄**——切换事件捕获（手动装配服务注入） |
| 验收测试骨架（FEATURE 常量 + @scenario 全量显式绑定 + context dict fixture（场景级独立 Redis 客户端 + `_run_async` 同循环）+ Redis 门控步骤化动态 skip + teardown 逐键精确删除 + AC 注释横幅分组 + 延迟 import 纪律 + 显式 pytestmark） | `tests/acceptance/test_acceptance_agent_workflow.py`（5-3 最新形态） | **参考照抄**——R6 主体基准；PG 模板（test_acceptance_postgresql_relational_layer.feature/.py）仅取三要素（AC 横幅分组/背景门控/AST 静态扫描写法），**禁复制其 then-pass 占位与场景悬空**（PG 模板历史缺陷） |
| 集成测试形态（手动组装仓储/服务 + 真实 Redis + 逐键删除 + `exists` 复核自产键删净 + P95 计时 warmup 1 + 20 采样 `statistics.quantiles(n=20)[18]`） | `tests/integration/test_integration_agent_profile_loading.py` | **参考照抄** |
| 测试基建：`get_test_env()`/`SISYS_USE_TEST_PORTS=1`/xdist_group/`acceptance_env_config` | `tests/environments.py`、`tests/acceptance/conftest.py` | **直接复用** |

**明确不存在、本 Story 需新建**（全仓 grep 验证：`src/` 下 `IsolationState|IsolationPolicy|isolation_repository|isolation_management|MVP_ALLOWED|set-isolation|isolation-status` 零命中；隔离状态无持久化位——RedisAgentRepository 序列化字段清单（L151-162）无 isolation 字段；InstantiateAgentUseCase 完全未消费 `default_isolation_level`；`IsolationLevelSwitched` 全仓零发布方）：

1. `IsolationPolicy` VO + `DataIsolationMode` 枚举 + `ISOLATION_POLICIES` 四级策略表 + `MVP_ALLOWED_LEVELS`（domain/value_objects/isolation_policy.py）
2. `IsolationState` 实体（initialize 工厂 + switch_to 领域行为，domain/entities/isolation_state.py）
3. `IsolationRepository` 端口（domain/ports/isolation_repository.py）
4. `RedisIsolationRepository`（infrastructure/storage/redis/redis_isolation_repository.py）
5. `IsolationManagementServicePort` + `IsolationSwitchResult`（application/ports/isolation_management.py）
6. `IsolationManagementService`（application/services/isolation_management_service.py）
7. 异常 446 `IsolationLevelNotSupportedError` / 447 `IsolationStateNotInitializedError`
8. CLI `isolation-status`/`set-isolation` 子命令 + `_parse_isolation_level` 守卫
9. 组合根两端口注册 + `InstantiateAgentUseCase` 注入改造（lambda 追加第四依赖）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: EIP 四级隔离协议模型

**Given** EIP 协议领域模型已定义
**When** 查询任一等级的隔离策略
**Then** `ISOLATION_POLICIES` 表完备覆盖四级（L4 硬隔离/L3 软隔离/L2 协作态/L1 融合态），每级含三重隔离维度声明：`prompt_isolation`（bool）/`tool_isolation`（bool）/`data_isolation`（DataIsolationMode 四值枚举），与 architecture.md §5.1 表逐行一致（L4=独立/严格隔离/只读、L3=独立/共享工具/受限写入、L2=独立身份/共享工具池/自由写入、L1=共享上下文/完全共享/完全共享）
**And** 默认等级为 `IsolationLevel.L4_HARD`；MVP 允许等级集 `MVP_ALLOWED_LEVELS = {L4_HARD, L3_SOFT, L2_COLLAB}`（L1 融合态 V2 开放——core-domain-design L1455-1460 eip_config.allowed_levels 先例；落位决策 DC-2）

**验证标准/Validation Criteria:**
- [ ] 四级策略表逐行断言（三维度 × 四级共 12 项 + 每级名称）
- [ ] `get_isolation_policy(L4_HARD).is_default` 为 True，其余三级为 False
- [ ] `MVP_ALLOWED_LEVELS` 集合断言（恰三值，不含 L1_FUSED）
- [ ] `DataIsolationMode` 枚举四值断言（READ_ONLY/RESTRICTED_WRITE/FREE_WRITE/FULL_SHARED）
- [ ] **边界声明**：本 AC 交付三重隔离维度的**策略声明**（数据模型层）；执行时强制拦截（Prompt/工具/数据访问探针拦截率 100%）归 Story 5.5

### AC-2: 默认 L4 初始化与 Redis 持久化

**Given** Agent 已实例化（`sisys-agent instantiate --role ceo`）
**When** 实例化完成
**Then** 隔离状态自动初始化为默认等级 L4 硬隔离（真源 `AgentConfig.default_isolation_level`）并持久化至 Redis 键 `sisys:isolation:{agent_id}`（独立键空间，与 `sisys:agent:{agent_id}` 并存互不侵入）
**And** 隔离键 TTL 与 Agent 键同源（`AgentConfig.state_ttl`，默认 86400 秒——TTL 策略决策 DC-9）；初始化失败时实例化 fail-fast 失败（安全基线优先——残键由 TTL 自然回收，DC-3）

**验证标准/Validation Criteria:**
- [ ] 实例化后 Redis 真实存在隔离键且 `current_level == L4`；`last_trigger_reason == "initial_default"`
- [ ] 隔离键与 Agent 键并存（两键各自独立存在，隔离键不写入 Agent 键空间）
- [ ] TTL 断言用 `redis.ttl(key)` 校验区间（禁真实等待过期——redis_cache_layer 先例）
- [ ] 持久化往返：save → get_by_agent_id 重建的 `IsolationState` 字段逐项相等（UUID/IsolationLevel/datetime 显式重建——RedisAgentRepository 同款纪律）
- [ ] 初始化等级非法（配置 L1——合法枚举越 MVP 白名单，loader 放行后由实体 initialize 446 拒绝；**非法枚举串如 "L9" 在 loader 层即 440 属循环 E 单测面，不进本验收断言**——R2-组合-3 输入通道分层收口）→ 446 拒绝（**验收禁 mock 下的合规驱动（R1-F35 + R3-F02/F03 细化）**：临时 yaml = **configs/agents/ceo_agent.yaml 全文基线复制到 tmp 目录、仅改 eip_config.default_isolation_level: L1**（loader 逐段强校验——最小 yaml 在 440 先炸）；加载经 **`YamlAgentConfigLoader(config_dir=tmp_path)` 构造注入**（resolve 全局 loader 固定读仓库配置 L4，446 恒不可达）；**446 断言经服务级真实链直调**：真实 loader 读临时 yaml → `initialize_agent_isolation(agent_id=<场景预生成 UUID>, default_level=config.default_isolation_level, ttl=config.state_ttl)` → 446 且零残留键——**不经 InstantiateAgentUseCase**（用例路径 446 时 agent_id 在 execute 内部生成不可回收、agent 残键违自包含纪律——用例编排骨位的参数传递归 Task 4 单测断言）
- [ ] 仓储 TTL 越界（<60 或 >2592000）→ 440（防御校验复用语义）

### AC-3: 隔离状态查询（隔离检查入口）

**Given** Agent 已实例化且隔离状态已持久化
**When** 查询隔离状态（`isolation-status` 或 `get_isolation_state(agent_id)`）
**Then** 返回完整 `IsolationState`（current_level/initialized_at/updated_at/last_trigger_reason）；三重隔离策略由入口/消费方持 state 联查 `get_isolation_policy(state.current_level)` 派生（服务返回值不含策略——端口签名 `-> IsolationState`，R1-F18 措辞校准）
**And** 隔离状态缺失（TTL 过期漂移/未初始化）→ `IsolationStateNotInitializedError`（447）；Agent 本身不存在 → `AgentNotFoundError`（443，复用）

**验证标准/Validation Criteria:**
- [ ] 查询返回字段逐项断言（含策略联查：L4 状态 → prompt_isolation=True/tool_isolation=True/data_isolation=READ_ONLY）
- [ ] 447 触发路径：删除隔离键后查询 → `[EXCEPTION_447]`，context 携带 agent_id
- [ ] 443 触发路径：随机 UUID 查询 → `[EXCEPTION_443]`
- [ ] 本方法是隔离检查入口（P95 计时锚——AC-5.1）

### AC-4: 隔离等级切换与事件发布

**Given** Agent 已实例化（隔离状态 L4）
**When** 用户显式请求切换等级（`set-isolation --agent-id <uuid> --level L3 --reason "<原因>"`——MVP 唯一触发通道，architecture.md §5.2「用户请求」）
**Then** 守卫序执行：Agent 存在（443）→ 隔离状态存在（447）→ 目标等级合法（446：非法枚举值或 L1 融合态均拒绝）；通过后切换等级、刷新 TTL、发布 `IsolationLevelSwitched` 事件（携带 agent_id/previous_level/target_level/trigger_reason/approval_chain/switch_timestamp，kw_only 必填形态）
**And** 同等级切换为 no-op（`switched=False`，零副作用——不写仓储不发布事件，幂等语义）；切换到 L1 或非法等级 → 446（context 携带原始输入与支持列表）

**验证标准/Validation Criteria:**
- [ ] L4→L3→L2 合法链切换成功，Redis 状态与返回结果一致，`updated_at`/`last_trigger_reason` 更新
- [ ] 事件断言：`IsolationLevelSwitched` 恰好发布一次（no-op 零发布），字段六项逐项断言（previous/target 枚举值、trigger_reason 非空、aggregate_id==agent_id、aggregate_type=="Agent"）
- [ ] 事件经 `EventPublisher.publish` 真实通道发布（reliable 单通道——yaml/routing_key 已登记复验）
- [ ] no-op 语义：L4 状态切 L4 → switched=False 且仓储未被重写（**判别锚 = 单测层 repo.save 零调用计数**；TTL 断言需先 elapsed ≥ 2s（初始化后 sleep）才可区分误重置——Redis TTL 秒级粒度，R1-F41 注记）且零事件
- [ ] 446 双路径：CLI 层非法字符串（`--level L9`）映射 446；服务/实体层 L1_FUSED（合法枚举但 MVP 禁用）→ 446
- [ ] 发布失败语义：publish 抛异常 → 记日志不回滚（状态已切换是事实——5-1 AgentInstantiated 先例，DC-10）
- [ ] **不含**：切换日志持久化与多维检索（归 5.6）、自动触发与 30 分钟恢复（归 V1）

### AC-5: 性能指标

**Given** 真实 Redis（测试端口 6380，`SISYS_USE_TEST_PORTS=1`）
**When** 测量隔离检查与持久化
**Then** 隔离检查延迟 P95<100ms（epics L1612）；隔离状态持久化成功率 100%；并发隔离 Agent≥10（epics L1614 / NFR-PERF-04 MVP 档）

**验证标准/Validation Criteria:**
- [ ] P95：`get_isolation_state` 服务全链真实 Redis 计时（R1-F02：443 存在性守卫 + 隔离态读——**共两次真实 Redis 读**（R2-回归-10 措辞校准），DC-11 口径），warmup 剔除 1 次 + 20 采样 + `statistics.quantiles(n=20)[18] < 0.1s`（`perf_counter` 计时——profile_loading 先例；计时含协议解析与 VO 重建全链）。**验收 AC-5.1/5.2 委托集成模块计时 helper**（20 采样同批派生 P95 与成功率分子分母——helper 每轮 initialize+读回即成功率采样面，20 次全成功即 20/20；模块级采样缓存共享同批结果 + 验收与集成同名 xdist_group("agent-isolation-perf") 同 worker 串行缓存命中——禁 20 采样双跑拖慢套件，5-3 先例跨套件 import L633；R1-F23 + R3-F05 委托分界细化）；**AC-5.3 并发 10 验收自跑**（计时 helper 无并发数据不可派生；10 agent gather 秒级无拖慢面）
- [ ] 持久化成功率：20 次连续 save+读回验证全成功（分母 20 分子 20）
- [ ] 并发 10：10 个 agent_id 并发 initialize+switch+get（`asyncio.gather`）全部成功且状态互不串扰（单进程并发先例）
- [ ] 计时场景 xdist_group 串行（`agent-isolation-perf`）+ benchmark 场景级标记（**验收侧不打文件级**——5-2 R1-F8 先例（R2-回归-6 归属勘误：原写「5-3 验收 R1-F8」，该先例属 5-2，5-3 L281 是转引）；集成侧 Task 6 按集成先例（profile_loading L45-50——R4-N5 行号终校）文件级 pytestmark 含 benchmark+xdist_group——两层各自对齐本层先例，R1-F16 口径注记）

### AC-6: 端口接线、架构合规与 CLI 全链

**Given** 协议模型、仓储、服务、CLI 全部交付
**When** 验证接线
**Then** 新端口（`isolation_repository` SINGLETON / `isolation_management_service` SINGLETON）经组合根 `register_port` 注册且 resolve 可达（PortSpec 全参数含 module/owner）；`InstantiateAgentUseCase` 组合根 lambda 注入第四依赖（隔离初始化接线）；CLI `isolation-status`/`set-isolation` 全链贯通（instantiate→isolation-status→set-isolation 可连续执行）；domain 零外部依赖（新增 VO/实体/异常/端口 AST 扫描）

**验证标准/Validation Criteria:**
- [ ] 组合根注册 + resolve + isinstance 合规断言（5-3 AC-6.1 同款；isolation_repository lifetime==SINGLETON——DC-7 D7 评估落地）
- [ ] `InstantiateAgentUseCase` resolve 可达且注入链完整（实例化→隔离键真实出现——端到端锚）
- [ ] CLI 全链：instantiate 产出 agent_id（手动组装实例化——不经 main()，R1-F06）→ isolation-status 输出 L4（main() exit 0）→ set-isolation L3 输出切换摘要（main() exit 0）→ isolation-status 输出 L3；守卫路径 443/446/447/201 退出码 1 + stderr 编码断言 `\[EXCEPTION_(?:201|4[0-9]{2})\]`（R1-F15——正则须同时匹配 201 与 4xx 两族）
- [ ] 架构验证器：domain 零外部依赖（isolation_policy.py/isolation_state.py/isolation_events.py/agent_exceptions.py AST 扫描禁 pydantic/redis）+ 组合根外零实例化 + 端口方向（application 服务依赖 domain 端口合法）
- [ ] CLI 成功路径验收 = 进程内 `main()` 调用（**5-3 测试序形态（R2-回归-7 + R3-F09 归称终校准）**：`clear_singleton()` + `clear_scoped()` **双清对齐 5-3 既有实码**（test_acceptance_agent_workflow.py L791-793——第三次 main() 前已是双清，注释明写「clear_singleton 不覆盖 SCOPED 缓存」；DC-12 四件套 given 步骤 ⓪ docstring 仅单清是描述滞后）→ conftest 已 bootstrap → 按需覆写 → main()；**每次 main() 调用前重执行双清**。**instantiate 步骤不经 main()**——手动组装实例化产出 agent_id（5-3 AC-6.3 同款先例：`_run_instantiate_cli` 直调 `bootstrap()` 与 conftest session 级 bootstrap 二重注册必抛 ConflictError——registry 同名异 spec 守卫）。本 Story 无 LLM 依赖，仅需关注 resolve 链与 Redis 门控）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [x] **不新建领域事件**——复用既有 `IsolationLevelSwitched`（`src/domain/events/isolation_events.py` L16-43；yaml L197-201 + channel_router L255-260 双登记已就绪，**零登记改动**，Task 0 仅复验）
- [x] **既有事件纪律收紧（DC-6，契约变更登记）**：`agent_id: uuid.UUID = field(default_factory=uuid.uuid4)` → `field(kw_only=True)`；`previous_level`/`target_level` 去掉 `= IsolationLevel.L4_HARD` 默认值改 kw_only 必填；`trigger_reason: str = ""` → kw_only 必填（切换必须有原因——空串是无意义的切换事件）；`approval_chain: list[str]`（default_factory=list）与 `switch_timestamp`（default_factory now(UTC)）保留默认（MVP 用户请求无审批链）。依据：DomainEvent 基类字段全带默认值，子类无默认值的非 kw_only 字段跟在其后类定义即抛 TypeError（AgentProfileLoaded 先例注释——agent_events.py L87-88）。**收紧时保留既有 `__post_init__` 的 aggregate_id←agent_id 派生与 aggregate_type="Agent"（isolation_events.py L38-43——AC-4 aggregate 断言依赖此派生，重写类体时禁丢失——R1-F12）**
- [x] **回归面清单（事件收紧全量同步，Task 1 循环 D）**：`tests/unit/domain/events/test_new_events.py` L79-108（TestIsolationLevelSwitched 构造/默认值断言形态同步）；`tests/unit/domain/events/test_event_serialization.py` L67-75/L145-146/L221-222（三处构造补必填参数）；`tests/acceptance/test_acceptance_domain_event_definition.py` L35/L150-279/L465-467（事件定义验收——构造形态同步）；`tests/unit/architecture/test_event_architecture.py` L129（导出断言——不受影响，复验）。src 侧零发布方、AutoTriggerHandler 引用是字符串（auto_trigger_handler.py L60-72）——零 src 回归
- [x] `src/domain/events/__init__.py` 无需改动（已导出 L31/L69）

#### 数据模型 (Data Models)

- [x] `DataIsolationMode(str, Enum)`（domain/value_objects/isolation_policy.py 内定义）：`READ_ONLY = "read_only"` / `RESTRICTED_WRITE = "restricted_write"` / `FREE_WRITE = "free_write"` / `FULL_SHARED = "full_shared"`（core-domain-design §17.3.3 L1204/1211/1217/1225 四值）
- [x] `IsolationPolicy` VO（frozen dataclass，同文件）：`level: IsolationLevel` / `name: str` / `prompt_isolation: bool` / `tool_isolation: bool` / `data_isolation: DataIsolationMode` / `is_default: bool = False`——`__post_init__` 校验（name 非空 strip / level 是 IsolationLevel 实例）
- [x] `ISOLATION_POLICIES: dict[IsolationLevel, IsolationPolicy]` 模块常量（四级逐行对齐 architecture.md §5.1：L4=硬隔离/True/True/READ_ONLY/is_default=True；L3=软隔离/True/False/RESTRICTED_WRITE；L2=协作态/True/False/FREE_WRITE；L1=融合态/False/False/FULL_SHARED）+ `get_isolation_policy(level) -> IsolationPolicy`（枚举键必命中；防御守卫：非 IsolationLevel 实例抛 `EntityValidationError` 242）
- [x] `MVP_ALLOWED_LEVELS: frozenset[IsolationLevel] = frozenset({L4_HARD, L3_SOFT, L2_COLLAB})`（L1 排除——SYS 监督/紧急态/强制审计设施均 V2）
- [x] `IsolationState` 实体（domain/entities/isolation_state.py，**非 frozen dataclass**——对齐 Agent 实体可变状态机形态，有切换生命周期）：`agent_id: uuid.UUID` / `current_level: IsolationLevel` / `initialized_at: datetime` / `updated_at: datetime` / `last_trigger_reason: str`；`__post_init__` 校验（agent_id 是 UUID / current_level 是 IsolationLevel 实例 / last_trigger_reason 非空 strip——失败抛 `EntityValidationError` 242）
- [x] `IsolationState.initialize(agent_id, level, *, now=None) -> IsolationState` 类方法工厂：等级守卫双条件（`not isinstance(level, IsolationLevel) or level not in MVP_ALLOWED_LEVELS` → 446——**R3-F01 实测定谳**：str,Enum 混入语义下 `hash("L3")==hash(L3_SOFT)`，合法值域裸 str 经 `in frozenset` 判定为 True，单 `not in` 守卫拦不住会放行为 242/类型污染——isinstance 先行是唯一可靠子类型防线，实测 Python 3.11.15）；`last_trigger_reason="initial_default"`；`initialized_at=updated_at=now or datetime.now(UTC)`（单 now 双用——初始化两时刻严格相等）
- [x] `IsolationState.switch_to(target_level, trigger_reason, *, now=None) -> bool` 实例方法：等级守卫同上（446 双条件——**switch_to 路径更关键**：dataclass 赋值不触发 `__post_init__`，裸 str 穿透单守卫后 `self.current_level = target_level` 即静默类型污染持久化，isinstance 先行封死）；`trigger_reason` 非空校验（空/空白 → `EntityValidationError` 242——原因缺失是实体不变量问题，与等级非法 446 语义区分）；`target_level == current_level` → 返回 `False`（no-op 零变更）；否则更新 `current_level`/`updated_at`/`last_trigger_reason` 返回 `True`（**领域行为内聚：等级合法性校验在实体**——DC-5）
- [x] `AgentConfig.default_isolation_level` 类型收紧：`str = "L4"` → `IsolationLevel = IsolationLevel.L4_HARD`（D6 isolation 项核销——SSOT 枚举绑定；`__post_init__` 增 `isinstance IsolationLevel` 守卫）

#### 统一端口定义注册与管理 (Port Contract)

- [x] `IsolationRepository`（`src/domain/ports/isolation_repository.py`，`@runtime_checkable Protocol`，docstring 注明键空间 `sisys:isolation:{agent_id}` 与异常契约——**R1 领域层基础端口**，AgentRepository/SessionStorage 同款先例）：
  - `async def save(self, state: IsolationState, ttl: int) -> None`（upsert 语义，TTL 必填——真源 `AgentConfig.state_ttl`；越界 60~2592000 抛 440）
  - `async def get_by_agent_id(self, agent_id: uuid.UUID) -> IsolationState | None`
  - `async def delete(self, agent_id: uuid.UUID) -> None`（幂等）
  - `async def exists(self, agent_id: uuid.UUID) -> bool`
- [x] `IsolationManagementServicePort`（`src/application/ports/isolation_management.py`，`@runtime_checkable Protocol`——**R2 应用层具体应用端口，组合注入 R1 仓储端口**）：
  - `async def initialize_agent_isolation(self, agent_id: UUID, default_level: IsolationLevel, ttl_seconds: int) -> IsolationState`（upsert——重复初始化覆盖；**前置条件 docstring 注明（R1-F32）**：调用方须保证 agent 已持久化——本方法无 443 前置守卫，MVP 唯一调用方 InstantiateAgentUseCase 刚 save 完 agent 满足前提；重复初始化覆盖回默认等级是安全方向设计意图——DC-3/R1-F33）
  - `async def get_isolation_state(self, agent_id: UUID) -> IsolationState`（**守卫序同 switch 前置**：Agent 不存在抛 443 → 隔离态缺失抛 447——隔离检查入口，AC-5.1 计时锚含两次真实 Redis 读）
  - `async def switch_isolation_level(self, agent_id: UUID, target_level: IsolationLevel, trigger_reason: str, approval_chain: Sequence[str] = ()) -> IsolationSwitchResult`
- [x] `IsolationSwitchResult` dataclass（端口文件内定义——多字段组合载体放端口文件先例）：`switched: bool` / `state: IsolationState` / `event: IsolationLevelSwitched | None`（no-op 时 event=None）
- [x] 端口注册中心/解析器/契约门禁纪律照旧（`src/domain/ports/registry.py` 体系）；组合根注册名与元数据：
  - `isolation_repository`：v1.0.0 / `IsolationRepository` / `RedisIsolationRepository`（lambda 工厂注入 `resolver.resolve("redis_adapter")`）/ module=src.infrastructure.storage.redis.redis_isolation_repository / **SINGLETON**（DC-7——D7 评估落地：无状态仓储构造零 IO，被 SINGLETON 服务捕获无 captive 实害）/ owner=platform / tags=("redis", "agent", "isolation")
  - `isolation_management_service`：v1.0.0 / `IsolationManagementServicePort` / `IsolationManagementService`（lambda 注入 isolation_repository + agent_repository + event_publisher + **agent_config_loader**）/ module=src.application.services.isolation_management_service / SINGLETON / owner=platform / tags=("agent", "isolation")
- [x] **TTL 真源通道（R1-F01 定稿，不留 Task 3 临场决策）**：switch 重置 TTL 的取值链 = 复用 443 守卫已取的 agent → `(await agent_config_loader.load(agent.role)).state_ttl`——服务第四依赖注入同层应用端口 `AgentConfigLoader`（组合根注册名 `agent_config_loader`，`load(role) -> AgentConfig` 单方法——src/application/ports/agent_config_loader.py L23-30；InstantiateAgentUseCase 注入同款先例），零第二真源、零额外 Redis 读
- [x] **既有端口消费**：`agent_repository`（443 守卫与初始化前置校验）、`event_publisher`（切换事件发布）、`agent_config_loader`（switch 重置 TTL 真源）、`agent_instantiation_use_case`（**构造签名扩展**——第四依赖 `isolation_management_service`，组合根 lambda 同步；契约测试 impl 维度同步——契约变更登记）
- [x] 端口契约测试两份（`tests/contracts/test_port_contract_isolation_repository.py` / `test_port_contract_isolation_management_service.py`，11 维度 + DummyResolver——agent_repository 样板同款）
- [x] **禁止**在服务文件本地定义 Protocol / Port 抽象；**禁止**新建语义重复端口（Agent 存在性查询复用 agent_repository，事件发布复用 event_publisher）

#### 端口契约清单执行约束（强制）

- [x] 本 Story 端口清单唯一真源 = 本 Task 0 定义（`isolation_repository` + `isolation_management_service` 两新端口 + **一项既有端口消费方变更**：`agent_instantiation_use_case` 构造签名扩展注入隔离服务——契约变更登记，`tests/contracts/test_port_contract_agent_instantiation_use_case.py` impl 维度与组合根 lambda 同步）
- [x] 禁止新增未登记端口；禁止未同步 registry/resolver/contract test
- [x] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> 原则/适用范围/禁止条款同模板基线（`sisys-uni-exception-design.md §3.12`）。本 Story 使用 agent 子域预留段 446-449（`_code_ranges.py` L122 注释显式预留「5.4-5.5 EIP 隔离」）；448-449 留给 5.5。设计决策见 DC-8。

- [x] `IsolationLevelNotSupportedError`（EXCEPTION_446，BusinessException）——隔离等级不合法（两种触发：CLI/调用方传入非法枚举值；合法枚举但不在 `MVP_ALLOWED_LEVELS`——即 L1 融合态）。构造器对齐 441 实际形态（R1-F45 校准：441 首参必填、supported 接受 tuple 或 list）：`(level: str, supported_levels: tuple[str, ...] | list[str] = (), message=None, cause=None)`——level 必填（441 `role: str` 同款无默认值），context 携带 `{level, supported_levels: list}`；HTTP 422（**对齐 441 精确注册 422 先例**——exception_handlers.py L269「MVP 未开放角色（精确注册，避免回退 400）」，「不支持的取值」族语义一致）。**CLI `_parse_isolation_level` 转换守卫的唯一出口**（禁裸 `IsolationLevel(value)`——Enum 原生 ValueError 逃逸，5-1 `_parse_role` 红线同款）
- [x] `IsolationStateNotInitializedError`（EXCEPTION_447，BusinessException）——隔离状态缺失，三种成因（R1-F09 + R3-F07 方向修正）：①**存量 Agent 无隔离键**（5.4 部署前实例化的 agent 被查询——注：「TTL 漂移致隔离键先过期」经写序推演不可构造，见风险 #6）；②未初始化查询；③**实例化 fail-fast 后键残留**（DC-3 残留态：agent 键存活 → 443 守卫通过 → 隔离键缺失 → 447——**服务级以同 id 重新 initialize 可自愈**（upsert 覆盖回 L4）；用例/CLI 通道每次 execute 生成新 uuid4、残留态在新 id 下不可达靠 TTL 自然回收（R3-F08）——运维见 447 时排查配置 L1 反复失败实例化，必要时服务级同 id 重初始化）。构造器：`(agent_id: str = "", message=None, cause=None)`，context 携带 `{agent_id}`；HTTP 404（对齐 443 NotFound 族语义）
- [x] 复用不新建：`AgentNotFoundError`（443——切换/查询前置 Agent 存在守卫）、`AgentConfigError`（440——仓储 TTL 越界 + YAML loader 非法等级字符串转换失败 + **AgentConfig D6 守卫回填**）、`EntityValidationError`（242——**新建非配置实体/VO 不变量**：IsolationPolicy/IsolationState——entities/agent.py L82-84 先例）、`StorageError`（103——Redis 连接异常包装，仓储层）
- [x] **242/440 分界原则（R1-F03）**：配置资产类 VO（AgentConfig——yaml 载入）校验失败固定 440（AgentConfigError 家族，HTTP 500 系统资源缺陷语义）；非配置实体/VO 不变量用 242。**非法等级字符串的口径分叉是设计意图**：CLI 交互输入非法串 → 446（422，运行时用户错误族）；yaml 部署配置非法串 → 440（500，部署资产缺陷族）——输入通道决定异常族，禁止「修平」；loader 只做字符串→枚举转换合法性（"L9"→440），**不做 MVP 白名单**（"L1" 合法枚举放行 → 实体 initialize 446 拒绝——AC-2 路径）
- [x] 强制 4 项 checklist：定义文件（agent_exceptions.py 追加）/ `_code_ranges.py` CODE_RANGES 注释预留改已分配 + `_CLASS_TO_SUBDOMAIN` 两映射 / `__init__.py` 暴露（import 块 agent 段 + `__all__`）/ `EXCEPTION_HTTP_MAP` 精确注册 446→422、447→404（防回退歧义）；`sisys-uni-exception-design.md` §3.3.2 编码分配表同步（446/447 两行，448-449 预留注记保留给 5.5）
- [x] 测试覆盖：`tests/unit/domain/exceptions/test_agent_exceptions.py` 追加（构造/context/to_dict/HTTP 映射 + 446 双触发路径参数化）+ `test_code_ranges.py` 子域校验自然覆盖（Rule 4 漏登记 `_CLASS_TO_SUBDOMAIN` 直接红）+ `test_exception_handlers.py` expected_types 同步
- [x] BDD 异常路径：446（非法等级/L1 拒绝）/447（状态缺失）/443（Agent 不存在）纳入 Edge Cases（AC-3/AC-4 场景）

#### API 契约 (API Contract)

- [x] 本 Story 无 REST API（CLI 入口；Agent 域 REST 规划位归 7-2）
- [x] CLI 契约：`sisys-agent isolation-status --agent-id <uuid>`（输出：等级/策略三维度/初始化与更新时间/最近触发原因；**时间输出钉 `isoformat()` 全格式（R3-F11）——stdout 断言以场景持有 state 字段的 `isoformat()` 值或 `^\d{4}-\d{2}-\d{2}T` 正则锚定，禁整行精确匹配（微秒位脆弱）**；exit 0；443/447/201 → exit 1）+ `sisys-agent set-isolation --agent-id <uuid> --level <L4|L3|L2> --reason "<文本>"`（输出：切换摘要或 no-op 提示；exit 0 含 no-op；443/446/447/201 → exit 1）。`--level` 不暴露 L1（`SUPPORTED_ISOLATION_LEVELS` 帮助文本只列 MVP 三级——但传入 L1 字符串仍走 446 路径而非 argparse choices 静默拒绝，保持统一异常出口）
- [x] `--approval-chain` 参数不暴露（MVP 用户直切无审批链，YAGNI——V1 SYS 命令通道立项时扩展）

#### 六边形架构约束（必须遵守）

> 四层定义/零依赖原则/依赖方向矩阵同模板基线。本 Story 特别注意：

- [x] `IsolationPolicy`/`IsolationState`/`DataIsolationMode`/异常/`IsolationRepository` 端口全部 domain 层，仅标准库（dataclasses/enum/uuid/datetime）——`.importlinter` domain-no-external-dependencies 契约（禁 pydantic/redis 等）
- [x] `IsolationManagementService`（application）构造注入三个 domain 端口（isolation_repository/agent_repository[domain 端口]/event_publisher[domain 端口]）+ 一个同层应用端口 `AgentConfigLoader`（TTL 真源通道——R1-F01；InstantiateAgentUseCase 注入先例同款，application→application 同层合法）——application→domain 合法；**禁 import infrastructure**
- [x] `RedisIsolationRepository`（infrastructure）实现 domain 端口；CLI（entrypoints）resolve 应用端口——interfaces/entrypoints→application 合法
- [x] `InstantiateAgentUseCase`（application）注入 `IsolationManagementServicePort`（application 端口）——同层端口组合注入合法（R2）
- [x] 架构树偏离登记（D-2）：architecture.md L1749 规划 `domain/services/isolation_service.py`（EIP 隔离服务接口）——实际落位 `application/ports/isolation_management.py`：隔离管理需编排仓储读写与事件发布，属应用编排关注点非纯领域逻辑；纯策略表（`ISOLATION_POLICIES`）已留 domain（value_objects）

#### 验收标准 Gherkin (Acceptance Tests)

- [x] 功能测试文件：`tests/acceptance/test_acceptance_agent_isolation.feature`
- [x] 步骤实现文件：`tests/acceptance/test_acceptance_agent_isolation.py`
- [x] 场景组织：AC 注释横幅分组（PG 模板形态）+ 全场景逐一 @scenario 显式绑定（5-3 形态，**禁 scenarios() 批量绑定与 then-pass 占位**）；场景名带 AC 编号前缀（`AC-1.1 - <描述>`，ASCII 连字符两侧空格，feature 与 .py 逐字一致）
- [x] 覆盖：AC-1×2（四级策略表完备/默认 L4 与 MVP 等级集）+ AC-2×3（实例化即 L4 持久化/双键空间并存与 TTL/往返重建与初始化异常）+ AC-3×2（查询与策略联查/447 与 443 异常路径）+ AC-4×4（合法切换与事件/事件字段精确断言/no-op 幂等/446 双路径与 443）+ AC-5×3（P95/持久化成功率/并发 10）+ AC-6×3（组合根接线/CLI 全链/架构合规静态扫描）= **17 场景**（Task 8 追加收尾场景后全量 18——收尾场景按模板钦定归 Task 8）
- [x] BDD 步骤约束：`event_loop.run_until_complete()`（禁 `@pytest.mark.asyncio`）；本 Story **零 LLM 依赖**（隔离协议不触 LLM——分档表比 5-3 简化一档）；Redis 依赖场景前置「假如 Redis 缓存服务可用」门控步骤（ping 失败 `pytest.skip` 动态跳过，禁写死）；纯端口级场景（AC-1×2 策略表、架构扫描）脱离门控
- [x] **场景三属性分档表**（Task 0.6 定稿，docstring 落盘）：每场景「层级（端口级/服务级/CLI 级）+ Redis 依赖（真实/无）+ 事件断言（recording/无）」
- [x] 显式 `pytestmark = [pytest.mark.acceptance, pytest.mark.redis, ...]`（文件名不含 "redis" 关键词，conftest 自动 marker 不生效）+ 计时场景 `xdist_group("agent-isolation-perf")`
- [x] 延迟 import 纪律：本 Story 新模块一律步骤函数体内延迟 import（顶部 import 收集期炸文件，无法逐 Task 转绿）
- [x] teardown 逐键精确删除：context 记录 `_agent_ids`，删除 `build_key("agent", ...)` + `build_key("isolation", ...)` **双键** + `exists` 复核自产键删净（禁 delete_pattern/flush/全库 scan_iter——多 worker 共享 6380 实例）

**Task 0 完成标志：**

- [x] 规范项全部定义；Gherkin 已编写且运行确认失败（红阶段验证——ModuleNotFoundError/断言红为合法红）
- [x] **链路接线断言清单**（Epic 4 行动项 7.1-1）：
  1. `isolation_repository`/`isolation_management_service` 组合根 register_port 装配验证（resolve 可达 + isinstance + PortSpec 元数据）
  2. `agent_instantiation_use_case` 组合根 lambda 注入 `isolation_management_service` 确认（**端到端锚：resolve 用例 → instantiate → Redis 隔离键真实出现**——lambda 漏注入则实例化链静默无隔离键，验收 AC-2.1 抓红）
  3. `IsolationLevelSwitched` 发布点代码位（`IsolationManagementService.switch_isolation_level` 内）+ 真实触发验证（switch → recording publisher 捕获断言六字段）+ 订阅方可达性注记（`AutoTriggerHandler._registered_event_types` 字符串清单已含——注册≠订阅；**消费方归属口径统一（R1-F39）**：5.6 切换日志是首个业务消费方，5.7 是事件订阅基建面——接线归消费方 Story 立项时决定，同 5-3 风险 #2 形态）
  4. yaml/DEFAULT_MAPPINGS 双登记复验（已就绪零改动——复验断言防漂移）
  5. CLI isolation-status/set-isolation 全链
- [x] **D7 评估落盘**（DC-7 决策表 + 核销登记——R1-F27 落点校准：D6/D7 留项登记于 5-1 story 留项台账 L1143/L1144（deferred-work.md 无此二条目），核销动作 = 5-1 台账勾选注记 + deferred-work.md 补登记索引行）；session_storage 再续期与工具熔断挂点评估登记（deferred-work 处置表）

---

### TDD 循环约束（适用于每个 Task）

> 每 Task 依次执行 🔴红→🟢绿→🟡变异→🔄重构；变异实证 = 对新行为契约的断言改坏→红→还原→绿（Epic 4 行动项 7.1-2 强制）。禁止行为四条同模板基线（先码后测/测试后置/跳红/跳变异）。

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| TDD 单元测试 | IsolationPolicy VO + 策略表 | 四级 12 维度逐行/默认标记/MVP 等级集/get 工厂守卫 | `tests/unit/domain/value_objects/test_isolation_policy.py` | Task 1 |
| TDD 单元测试 | IsolationState 实体 | initialize 工厂/switch_to 行为与守卫/no-op/242 不变量 | `tests/unit/domain/entities/test_isolation_state.py` | Task 1 |
| TDD 单元测试 | AgentConfig D6 回填 | default_isolation_level 枚举化/标量类型守卫（440 分码）/空白串现状钉子 | `tests/unit/domain/value_objects/test_agent_config.py`（追加） | Task 1 |
| TDD 单元测试 | yaml loader 等级转换守卫 | str→IsolationLevel 非法值 440/合法转换/空串回落语义钉子 | `tests/unit/infrastructure/agent_orch/test_yaml_agent_config_loader.py`（追加） | Task 1 |
| TDD 领域异常测试 | 446/447 | 构造/context/to_dict/HTTP 映射/446 双触发路径 | `tests/unit/domain/exceptions/test_agent_exceptions.py`（追加）+ `tests/unit/interfaces/api/test_exception_handlers.py`（追加——R1-F43 路径补全：expected_types 显式清单双向锁定，新增 446/447 须同步清单否则 set 相等断言红） | Task 1 |
| TDD 单元测试 | IsolationLevelSwitched 纪律收紧 | kw_only 必填/缺参 TypeError/序列化 roundtrip 保持 | `tests/unit/domain/events/test_new_events.py`（同步）+ `test_event_serialization.py`（同步）+ `tests/acceptance/test_acceptance_domain_event_definition.py`（同步——回归面第三文件，R1-F17 补录） | Task 1 |
| TDD 单元测试 | RedisIsolationRepository | save/get 往返/TTL 校验 440/显式重建/delete 幂等/StorageError 包装（fakeredis） | `tests/unit/infrastructure/storage/redis/test_redis_isolation_repository.py` | Task 2 |
| TDD 契约测试 | isolation_repository | 11 维度 + DummyResolver | `tests/contracts/test_port_contract_isolation_repository.py` | Task 2 |
| TDD 单元测试 | IsolationManagementService | 守卫序 443→447→446/初始化/get 447/切换 no-op/事件发布与发布失败容错/调用轨迹断言（AsyncMock spec 端口） | `tests/unit/application/services/test_isolation_management_service.py` | Task 3 |
| TDD 契约测试 | isolation_management_service | 11 维度 + DummyResolver | `tests/contracts/test_port_contract_isolation_management_service.py` | Task 3 |
| TDD 单元测试 | InstantiateAgentUseCase 注入改造 | 第四依赖调用断言/初始化失败 fail-fast/既有守卫零回归 | `tests/unit/application/use_cases/test_agent_instantiation.py`（追加+同步） | Task 4 |
| TDD 单元测试 | CLI 子命令 | 参数解析/`_parse_isolation_level` 两道守卫/退出码/no-op 输出 | `tests/unit/interfaces/cli/test_agent_cli.py`（追加） | Task 5 |
| TDD 验收测试 | Gherkin + BDD | 17 场景 Task 0 编写 + 收尾场景 Task 8 追加（全量 18；各 Task 转绿——AC-1 随 Task 1、AC-2 随 Task 2/4、AC-3/AC-4 随 Task 3/5、AC-5×3 随 Task 6、AC-6 随 Task 4/5/7、收尾场景 Task 8——R1-F43 补 AC-6 归属 + R2-组合-7 口径收口：原「18 场景（Task 0 编写」把收尾错归 Task 0，与 L386/L610 冲突） | `test_acceptance_agent_isolation.feature/.py` | Task 0-8 |
| SDD 架构验证 | 六边形约束 | domain 零外部依赖/组合根外零实例化/端口方向/lifetime 决策落地 | `tests/unit/architecture/test_arch_agent_isolation.py` | Task 7 |
| 集成测试 | 全链（真实 Redis） | 实例化→隔离→切换→事件/性能三指标/并发 10 | `tests/integration/test_integration_agent_isolation.py` | Task 6 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] 整体 ≥80%（P0 阻断）；**应用层 ≥85%**（本 Story 主战场之一）；domain ≥90%（协议模型主战场）；infrastructure ≥75%——四档与仓库 `scripts/check_coverage_gates.py` 门禁一致（interfaces 无独立门禁档：CLI 面单测全覆盖代偿）
- [ ] 集成测试覆盖率 ≥75%（epics L1618 TDD 要求口径——R1-F13 行号勘误：L1617 是应用层覆盖率行；沿 5-2/5-3 先例）；关键路径分支覆盖的可执行口径（R1-F24——pyproject coverage `branch` 未启用，无分支命中数据）：switch_to 守卫三分支（446 守卫/242 守卫/no-op 返回 False）+ 初始化 fail-fast 分支各配**独立命名测试用例**（用例名即分支清单——test_isolation_state.py / test_agent_instantiation.py 追加组），语句级覆盖由分层门禁（domain ≥90%）背书

#### 代码质量门禁

- [ ] `ruff check src/ tests/` + `mypy src/`（pre-commit mypy 覆盖 tests/）+ `pre-commit run` 全过
- [ ] 三条红线自查零输出（`raise ValueError`/手动 `HTTPException`/继承内置 Exception）+ 零抑制注释
- [ ] 提交信息零 AI 署名

#### 测试隔离约束

> 基线同模板（事务隔离/UUID 唯一/并行隔离/清理粒度/asyncio 纪律全表）。本 Story 特别注意：

- [ ] **验收/集成 Redis 双键清理**：context/fixture 记录 `_agent_ids`，teardown 逐个删除 `sisys:agent:{id}` 与 `sisys:isolation:{id}` 双键 + `exists` 复核删净（禁 delete_pattern/flush/全库 scan_iter——5-2 R1-F1 教训：与并行组共享键空间耦合假红）
- [ ] **场景级独立 Redis 客户端 + 同循环关闭**（session 级客户端跨场景 "Event loop is closed"——4-1b R2-2-C2 移除共享 fixture 的原因，R1-F40 出处补注）；`_run_async(context["_loop"], coro)` 同循环纪律
- [ ] **手动组装纪律（5-1 文档审查 Round 3 发现 #23 教训——R1-F40 编号可追溯化：原写「R3-F23」在 5-1 story 不可 grep）**：验收/集成禁 `resolve("isolation_repository")`/`resolve("agent_instantiation_use_case")` 发真实命令——SCOPED/SINGLETON 实例钉住全局 Resolver，SINGLETON redis_client 跨 function-scope 循环复用抛 "Event loop is closed"；一律场景级客户端手动组装（`RedisIsolationRepository(adapter=RedisAdapter(redis_client=ctx["_redis_client"]))` + 手动实例化服务/用例）；resolve 仅做 AC-6.1 接线断言且禁发命令
- [ ] **事件捕获替身**：`_RecordingEventPublisher`（手写 duck-typing 类，直接实现 EventPublisher 端口契约——5-3 先例；全仓 4 处同款，非 InMemoryEventBus 子类——R1-F14 校准）手动装配注入服务；断言「恰好一次/零次」而非「至少一次」（no-op 判别力）
- [ ] **计时场景**：xdist_group("agent-isolation-perf") 串行 + benchmark 场景级标记；P95 断言同源派生阈值（`< 0.1` 常量与采样口径一处定义）
- [ ] **447 场景键处理**：删除隔离键制造缺失态的场景，agent 键仍需常规清理（双键清单不含被测删除键的二次删除——delete 幂等无害，保留统一循环）
- [ ] BDD 步骤禁 `@pytest.mark.asyncio`（context 数据丢失）；步骤函数同步 def + `_run_async` 调度

**验证要求：** `pytest tests/ -n 8` 通过；连续 5 次无随机失败；ruff/mypy 通过。

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 四级策略表 12 维度逐行 | Task 1 | IsolationPolicy VO + 常量表 | test_isolation_policy |
| AC-1 | 默认 L4 与 MVP 等级集 | Task 1 | is_default 标记 + MVP_ALLOWED_LEVELS | test_isolation_policy |
| AC-2 | 实例化即 L4 持久化 | Task 4 | InstantiateAgentUseCase 注入改造 + 组合根 | test_agent_instantiation（追加）+ 验收 AC-2.1 |
| AC-2 | 双键空间并存与 TTL | Task 2 | RedisIsolationRepository 键空间 | test_redis_isolation_repository |
| AC-2 | 往返重建/初始化 446/TTL 440 | Task 1/2 | 实体工厂守卫 + 仓储防御校验 | test_isolation_state + test_redis_isolation_repository |
| AC-3 | 查询与策略联查 | Task 3 | get_isolation_state | test_isolation_management_service |
| AC-3 | 447/443 异常路径 | Task 1/3 | 异常 447 + 服务守卫序 | test_agent_exceptions + test_isolation_management_service |
| AC-4 | 合法切换 + 事件发布 | Task 3 | switch_isolation_level + 事件 | test_isolation_management_service |
| AC-4 | 事件字段精确断言 | Task 3/1 | 事件 kw_only 收紧 + 发布 | test_isolation_management_service + test_new_events |
| AC-4 | no-op 幂等 | Task 1/3 | switch_to False + 服务零副作用 | test_isolation_state + test_isolation_management_service |
| AC-4 | 446 双路径 + 443 | Task 1/3/5 | 实体守卫 + 服务守卫序 + CLI 守卫 | test_isolation_state + test_isolation_management_service + test_agent_cli |
| AC-5 | P95<100ms | Task 6 | 集成计时 | test_integration_agent_isolation |
| AC-5 | 持久化成功率 100% | Task 6 | 20 次连续写入 | test_integration_agent_isolation |
| AC-5 | 并发隔离 Agent≥10 | Task 6 | gather 并发 | test_integration_agent_isolation |
| AC-6 | 组合根接线 + 注入链 | Task 4 | 两端口注册 + lambda 注入 | 契约测试 + 验收 AC-6.1 |
| AC-6 | CLI 全链 | Task 5 | isolation-status/set-isolation | test_agent_cli + 验收 AC-6.2 |
| AC-6 | 架构合规 | Task 7 | 验证器 A-D | test_arch_agent_isolation |
| 全 AC | 收尾清单 | Task 8 | 完成清单场景 | 验收收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ TDD 循环内化原则同模板。每 Subtask 组内按领域粒度拆分红绿循环。

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部

- [x] Subtask 0.1: 定义数据模型规范——IsolationPolicy VO（六字段）+ DataIsolationMode 四值 + ISOLATION_POLICIES 四级表 + MVP_ALLOWED_LEVELS + IsolationState 实体（五字段 + initialize/switch_to 行为契约）字段表定稿（本文件「数据模型」节为唯一真源）
- [x] Subtask 0.2: 定义端口契约——IsolationRepository 四方法 + IsolationManagementServicePort 三方法 + IsolationSwitchResult + 组合根注册元数据（含 lifetime 决策 DC-7）
- [x] Subtask 0.3: 定义异常契约——446/447（code/parent/context/触发场景表 + HTTP 映射 422/404——R1-F08 勘误：原「400/404」笔误，权威口径 446→422 对齐 441 先例）
- [x] Subtask 0.4: 定义事件纪律收紧契约——IsolationLevelSwitched kw_only 必填形态 + 回归面四文件清单
- [x] Subtask 0.5: 定义 CLI 契约——isolation-status/set-isolation 参数与退出码表 + `_parse_isolation_level` 两道守卫
- [x] Subtask 0.6: 编写 Gherkin `test_acceptance_agent_isolation.feature`（17 场景——收尾场景按模板归 Task 8 追加）+ BDD 步骤实现骨架 `test_acceptance_agent_isolation.py`（@scenario 全显式绑定 + context dict fixture + 双键清理）+ **17 场景三属性分档表**定稿（docstring）
- [x] Subtask 0.7: 运行验收测试确认失败（🔴 红阶段——ModuleNotFoundError/断言红为合法红）
- [x] Subtask 0.8: D7 评估落盘（DC-7 决策 + isolation_repository SINGLETON 依据）+ 留项核销交叉登记四项（D7 核销/D6 核销预告/session_storage 再续期/工具熔断挂点评估结论——R1-F27：D6/D7 核销落点 = 5-1 story 台账 L1143/L1144 勾选注记 + deferred-work.md 补索引；session_storage/工具熔断落点 = deferred-work.md 原条目更新）

**完成标准/Definition of Done:**
- [x] 规范项全部定义；验收测试红阶段确认；链路接线断言清单 L1-L5 定义

---

### Task 1: 领域层——策略表 VO / IsolationState 实体 / 事件收紧 / 异常 446/447 / AgentConfig D6 回填

**关联 AC:** AC-1、AC-2（初始化守卫）、AC-4（实体守卫）

#### TDD 循环 A：IsolationPolicy VO + 策略表

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_isolation_policy.py`（DataIsolationMode 四值集合/ISOLATION_POLICIES 恰四键且键==level 字段自洽/四级 12 维度逐行断言（L4: prompt=True tool=True data=READ_ONLY；L3: True/False/RESTRICTED_WRITE；L2: True/False/FREE_WRITE；L1: False/False/FULL_SHARED）/L4 is_default=True 其余 False/get_isolation_policy 四级命中 + 非 IsolationLevel 实例入参抛 242/MVP_ALLOWED_LEVELS 恰三值不含 L1_FUSED/VO 构造 name 空白抛 242） |
| 🟢 绿 | 实现 `src/domain/value_objects/isolation_policy.py`（frozen dataclass + 模块常量 + 工厂函数——AgentProfile VO 校验风格）+ `src/domain/value_objects/__init__.py` 导出 |
| 🟡 变异 | 策略表某维度翻转（如 L4 tool_isolation→False）→ 逐行断言红 → 还原 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 B：IsolationState 实体

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/entities/test_isolation_state.py`（initialize：默认 now UTC/last_trigger_reason=="initial_default"/initialized_at==updated_at（单 now 双用——R3 时间线1）/等级守卫——**L1（合法枚举越 MVP 白名单）→ 446；非枚举实例参数化双入参：裸 str "L3"（合法值域——**str,Enum 混入语义下 in frozenset 判定 True，单 not in 守卫拦不住，双条件 isinstance 先行才使断言成立——R3-F01**）与裸 str "L9"（值域外）→ 均 446**；switch_to：合法切换返回 True 且 current_level/updated_at/last_trigger_reason 更新/同等级返回 False 且字段零变更（updated_at 不变——now 注入同值断言）/L1 → 446 context 携带 level 与 supported_levels/裸 str "L3" 经 switch_to → 446（**类型污染防线断言**——dataclass 赋值不触发 __post_init__，双条件守卫是唯一防线）/trigger_reason 空白 → 242/__post_init__：**绕过工厂直构造** agent_id 非 UUID/current_level 非枚举/last_trigger_reason 空 → 242/now 参数注入确定性断言） |
| 🟢 绿 | 实现 `src/domain/entities/isolation_state.py`（非 frozen dataclass + 类方法工厂 + 实例方法——Agent 实体风格）+ `src/domain/entities/__init__.py` 导出 |
| 🟡 变异 | switch_to 同等级分支删除断言 no-op 用例红 → 还原；446 守卫移除 → L1 用例红 → 还原 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 C：异常 446/447

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/domain/exceptions/test_agent_exceptions.py` 追加（446：code/继承 BusinessException/context {level, supported_levels}/双触发路径参数化——非法字符串 "L9" 与合法枚举 L1_FUSED；447：code/context {agent_id}/to_dict 含编码）+ `test_exception_handlers.py` 追加 446→422、447→404 精确注册断言 |
| 🟢 绿 | `agent_exceptions.py` 追加两类（构造器对齐 441/443 形态）+ `_code_ranges.py` CODE_RANGES 注释改已分配 + `_CLASS_TO_SUBDOMAIN` 两映射 + `__init__.py` 暴露 + `EXCEPTION_HTTP_MAP` 两行 + 设计文档 §3.3.2 两行 |
| 🟡 变异 | 码值突变 → 唯一性测试红 → 还原 |
| 🔄 重构 | 全套异常测试（`tests/unit/domain/exceptions/`）绿（test_code_ranges Rule 4 自动覆盖新类登记） |

#### TDD 循环 D：IsolationLevelSwitched 事件纪律收紧

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/domain/events/test_new_events.py` TestIsolationLevelSwitched 同步改写（kw_only 必填构造形态：显式传 agent_id/previous_level/target_level/trigger_reason；缺任一必填 → TypeError 断言；approval_chain/switch_timestamp 默认值保留断言）+ `test_event_serialization.py` 三处构造补参（序列化 roundtrip 保持绿） |
| 🟢 绿 | 修改 `src/domain/events/isolation_events.py`（agent_id/previous_level/target_level/trigger_reason → `field(kw_only=True)`；docstring 补「Story 5-4 纪律收紧：切换事件核心字段必填」注记） |
| 🟡 变异 | 某字段默认值回退 → TypeError 断言红 → 还原 |
| 🔄 重构 | 事件全套测试绿（test_event_architecture 导出断言复验 + `tests/acceptance/test_acceptance_domain_event_definition.py` 构造形态同步——回归面四文件全绿） |

#### TDD 循环 E：AgentConfig D6 残余回填（DC-12 回填边界定稿）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/domain/value_objects/test_agent_config.py` 追加 + `tests/unit/infrastructure/agent_orch/test_yaml_agent_config_loader.py` 追加（loader 用例与 VO 用例同批先行——禁先码后测）。**异常分码原则（R1-F03 定稿）**：AgentConfig 是配置资产类 VO，其全部校验失败统一抛 **440 AgentConfigError**（文件 `_fail` 先例——test_agent_config.py L146-148 已钉死空白 name→440）；242 EntityValidationError 仅用于新建 IsolationPolicy/IsolationState（非配置实体不变量——entities/agent.py L82-84 先例）。用例清单：①default_isolation_level 类型收紧：构造传 IsolationLevel.L4_HARD 正常 / 传裸字符串 "L4" → **440**（reason 含 isolation 语义）/传非法枚举实例外值 → 440；②标量字段类型守卫：name=123 / description=123 → **440**（`_fail` 新增 isinstance str 守卫，reason 中文自然语言——原裸 AttributeError 逃逸是 D6 残余核销锚）；③空白串现状钉子：name="  " → **440**（现有防线已拦截——D6「空白串未归一」子项经核实现状为「拦截语义已存在」，钉子测试锁定即核销，存储值不做 strip 归一）；④loader 转换：合法 "L4" → IsolationLevel.L4_HARD / 非法枚举值字符串 "L9" → 440（reason 中文：`f"eip_config.default_isolation_level 非法隔离等级值: {raw}"` 对齐 role 先例 L82-87 风格）/ **空串/缺失/None 回落 "L4"→L4_HARD 语义原样保留**（loader L128 既有定稿语义——钉子用例锁定）/ **loader 不做 MVP 白名单**（"L1" 是合法枚举值，loader 放行 → 由实体 initialize 446 拒绝——AC-2「配置 L1→446」路径依赖此分层，禁止 loader 拦 L1） |
| 🟢 绿 | 修改 `src/domain/value_objects/agent_config.py`（字段类型 `IsolationLevel = IsolationLevel.L4_HARD` + `__post_init__` 守卫增强——注意 `src/domain/value_objects/` 引 `src/domain/events/enums.py` 同层跨模块合法）+ 同步 `src/infrastructure/agent_orch/yaml_agent_config_loader.py`（str→IsolationLevel 转换守卫：**禁裸 `IsolationLevel(value)`**，对齐 role 先例 `except ValueError → _fail`（440）——仅拦非法枚举值字符串；非字符串类型沿用既有 L126-127 守卫不动；空串/缺失回落语义保留 L128 不动） |
| 🟡 变异 | 枚举守卫删除 → 裸 str 构造用例红 → 还原；loader 转换守卫删除 → "L9" 用例红（ValueError 逃逸）→ 还原 |
| 🔄 重构 | 既有用例同步（"L4" 值经 loader 转换后 AgentConfig.default_isolation_level==L4_HARD；既有 loader 测试全绿——空串回落用例是既有语义锁定）全绿 |

- [x] Subtask 1.1-1.5: 五循环各红绿变异重构
- [x] Subtask 1.6: 领域层覆盖率 ≥90% 维持确认

**完成标准/Definition of Done:** 协议模型/实体/事件/异常/配置全绿；domain 覆盖率 ≥90%；D6 残余全核销

---

### Task 2: RedisIsolationRepository 仓储 + 契约测试

**关联 AC:** AC-2（持久化/TTL/键空间）

#### TDD 循环 A：仓储实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/redis/test_redis_isolation_repository.py`（fakeredis——save→get_by_agent_id 往返字段逐项相等（UUID/IsolationLevel/datetime 显式重建断言——透传 str 必红，5-1 变异先例）/键形态断言 `sisys:isolation:{agent_id}`（禁侵入 agent namespace）/save 后 `redis.ttl` 落在 [ttl-5, ttl] 容差区间/TTL 越界 <60 与 >2592000 → 440（reason 语义）/upsert：二次 save 覆盖且 TTL 重置/get 不存在返回 None/delete 幂等（删除不存在键无异常）/exists/连接异常注入（fakeredis 断连模拟或 Mock adapter 抛异常）→ `StorageError(cause=exc)` 包装且 cause 属性经构造参数传递（`from exc` 仅设 `__cause__` 不够——5-1 Task 3 实测教训）/Hash 单 field latest 形态断言（raw_client hget） |
| 🟢 绿 | 实现 `src/infrastructure/storage/redis/redis_isolation_repository.py`（RedisAgentRepository L40-185 照抄模式：构造注入 adapter/`_ISOLATION_NAMESPACE = "isolation"`/`_state_to_hash`/`_hash_to_state` 显式重建/MULTI/EXEC hset+expire pipeline/异常包装禁静默） |
| 🟡 变异 | 重建函数 Enum 透传 str（不转 IsolationLevel）→ isinstance 断言红 → 还原；TTL 校验删除 → 越界用例红 → 还原 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 B：端口契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/contracts/test_port_contract_isolation_repository.py`（11 维度 + `_DummyResolver` fakeredis 注入 redis_adapter——agent_repository 样板逐维度） |
| 🟢 绿 | 组合根注册 `isolation_repository`（PortSpec 全参数：v1.0.0/SINGLETON（DC-7）/owner=platform/tags=("redis","agent","isolation")/lambda 工厂 `adapter=resolver.resolve("redis_adapter")` + 区段注释含 D7 评估结论） |
| 🟡 变异 | impl 路径突变 → resolve 失败红 → 还原；lifetime 突变 SCOPED → 契约维度红 → 还原 |
| 🔄 重构 | 契约 11 项绿 |

- [x] Subtask 2.1-2.2: 两循环红绿变异重构

**完成标准/Definition of Done:** 仓储 fakeredis 全绿 + 契约绿；infrastructure 覆盖率 ≥75% 维持

---

### Task 3: IsolationManagementService 应用服务 + 契约测试

**关联 AC:** AC-3、AC-4

#### TDD 循环 A：服务实现（三方法 + 守卫序 + 事件发布）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_isolation_management_service.py`（`AsyncMock(spec=IsolationRepository)` + `AsyncMock(spec=AgentRepository)` + `AsyncMock(spec=EventPublisher)` + `AsyncMock(spec=AgentConfigLoader)` 四替身——单测 Mock 端口合规；config stub 携带 state_ttl。initialize：构建状态→repo.save(state, ttl) 调用断言（参数含 TTL）/返回 IsolationState/非法等级由实体工厂 446 拦截（服务不重复校验——向上透传）。get **守卫序同 switch 前置（R1-F02——含同款 calls 顺序断言，R2-组合-2 显式化）**：agent_repository.get_by_id None → 443 且 isolation_repository 未被调（calls 顺序断言——变异可红前提）/isolation repo.get 返回状态→透传/repo.get 返回 None → 抛 447（context agent_id）/repo 异常透传。switch **守卫序 calls 断言**（5-2 先例）：agent_repository.get_by_id None → 443（isolation repo 未被调——calls 顺序断言）/状态 None → 447/实体 switch_to 返回 False → switched=False + event=None + **repo.save 零调用 + publisher 零调用**（no-op 零副作用——calls 计数断言）/返回 True → repo.save 恰一次且 **ttl 参数 == config stub 的 state_ttl（R1-F01 TTL 真源断言——config_loader.load(agent.role) 恰一次）** + publisher.publish 恰一次（事件六字段断言：previous==旧等级/target==新等级/trigger_reason/approval_chain==传入链/aggregate_id==agent_id）/publish 抛异常 → 记日志不回滚（结果正常返回——publish 失败容错，DC-10；logger 断言或 caplog）/**publish 返回 is_success=False 失败结果 → 结果正常返回（switched=True）+ repo.save 恰一次保持 + logger.warning 断言**（R2-组合-5：真实总线失败不抛异常——先例 test_agent_instantiation.py test_publish_is_success_false_path_returns_result 同款独立命名用例，两分支各配独立用例） |
| 🟢 绿 | 实现 `src/application/ports/isolation_management.py`（Protocol + IsolationSwitchResult）+ `src/application/services/isolation_management_service.py`（构造注入 isolation_repository/agent_repository/event_publisher/agent_config_loader——R2 组合四依赖；switch 内 TTL 取值 `config = await self._config_loader.load(agent.role)`（agent 复用 443 守卫已取实例——R1-F01）+ `datetime.now(UTC)` 单次取值传实体（initialized/updated 一致性）；发布失败容错双分支对齐 InstantiateAgentUseCase 先例：`try/except Exception` 记日志 **+ `publish_result.is_success == False` 分支记日志**——真实总线发布失败不抛异常而返回失败结果，单分支 except 在真实链路不可达） |
| 🟡 变异 | 守卫顺序交换（447 先于 443）→ calls 断言红 → 还原；no-op 分支误调 save → 计数断言红 → 还原 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 B：端口契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/contracts/test_port_contract_isolation_management_service.py`（11 维度——impl 是 application 服务类，DummyResolver 提供 isolation_repository/agent_repository/event_publisher/agent_config_loader 四依赖） |
| 🟢 绿 | 组合根注册 `isolation_management_service`（PortSpec 全参数 + lambda 四依赖注入（isolation_repository/agent_repository/event_publisher/agent_config_loader——R1-F01）+ 区段注释） |
| 🟡 变异 | 注册名突变 → resolve 红 → 还原 |
| 🔄 重构 | 契约绿 |

- [x] Subtask 3.1-3.2: 两循环红绿变异重构

**完成标准/Definition of Done:** 服务三方法全绿（守卫序/no-op/事件/容错四类断言活）；契约绿；application 覆盖率 ≥85%

---

### Task 4: InstantiateAgentUseCase 注入改造 + 组合根接线

**关联 AC:** AC-2（实例化即隔离）、AC-6（接线）

#### TDD 循环 A：用例改造（第四依赖 + fail-fast）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/application/use_cases/test_agent_instantiation.py` 追加 + 存量同步（构造签名四依赖——存量用例构造处补 `AsyncMock(spec=IsolationManagementServicePort)`；新断言：成功路径 repository.save 后 `isolation.initialize_agent_isolation(agent_id, config.default_isolation_level, config.state_ttl)` 恰一次（参数断言——等级与 TTL 均来自 config，双消费闭环）/初始化抛异常 → execute 向上抛（fail-fast——DC-3）且 AgentInstantiated 未发布（发布在其后——顺序断言）/既有守卫 441/440 零回归/发布失败记日志不回滚保持） |
| 🟢 绿 | 修改 `src/application/use_cases/agent_instantiation.py`（构造注入 `isolation_service: IsolationManagementServicePort` 第四依赖 + execute 编排骨位：save → isolation initialize（fail-fast）→ publish；docstring 注记隔离初始化语义）+ 组合根 `agent_instantiation_use_case` lambda 注入改造 |
| 🟡 变异 | 注入调用删除 → 恰一次断言红 → 还原；调用顺序交换（先 publish 后 initialize）→ 顺序断言红 → 还原 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 B：契约回归 + resolve 冒烟

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/contracts/test_port_contract_agent_instantiation_use_case.py` impl 维度同步（工厂签名四依赖）；组合根注册测试（如有）同步 |
| 🟢 绿 | 组合根 lambda 四依赖完整；`resolve("agent_instantiation_use_case")` 冒烟（链路接线断言清单 L2——**端到端锚**：真实 Redis 下 instantiate → 隔离键真实出现，归验收 AC-2.1 场景） |
| 🟡 变异 | lambda 漏注入 isolation 依赖 → resolve 构造失败红 → 还原 |
| 🔄 重构 | **回归面清单全量跑**（适配器契约变更回归规则——R1-F05 补全：`InstantiateAgentUseCase(` 全仓 8 处构造点 + 3 处联动测试——R2-回归-5 计数勘误：7 手动构造 + 组合根 lambda，契约测试经 spec.impl 反射构造不入 grep 面）。**手动构造点 7 处（第四依赖必填，全部需同步补依赖）**：①单测 `tests/unit/application/use_cases/test_agent_instantiation.py:121`（_make_use_case 工厂）；②验收 `test_acceptance_agent_instantiation.py:214`；③验收 `test_acceptance_agent_profile_loading.py:228`；④验收 `test_acceptance_agent_workflow.py:564`（5-3 AC-6.3 场景手动组装）；⑤集成 `test_integration_agent_workflow.py:227`（`_instantiate_agent` helper——**手动组装非 resolve 链**，场景①②③⑤共用）；⑥集成 `test_integration_agent_profile_loading.py:64`（assembled fixture）；⑦集成 `test_integration_agent_instantiation.py:68`。**联动测试 3 处**：test_agent_cli（instantiate 部分）/test_port_contract_agent_instantiation_use_case（_DummyResolver 按名提供依赖分支 L27-51 同步）/test_yaml_agent_config_loader/test_agent_config。**第四依赖分派（R2-回归-2 + R2-组合-1 + R3-F04 定稿）**：既有**三验收文件（②③④）回归同步用真实 `IsolationManagementService` 手动组装**（isolation_repository/agent_repository 场景级客户端 + `_RecordingEventPublisher` + agent_config_loader 经 resolve——5-1 验收 L214 全真实组装先例同款；**CLAUDE.md「验收禁 mock」硬约束**——R2-F02 原分派的验收侧 AsyncMock 违反该约束，R3-F04 改判；实例化步骤是场景 Given 前置非断言面，真实组装成本仅 4 行依赖装配）；**三集成文件（⑤⑥⑦）维持 `AsyncMock(spec=IsolationManagementServicePort)`**（集成 Mock 工厂子模式合规——验收与集成分界清晰）；本 Story 新验收场景（AC-2.1/AC-4×4/AC-6.2）与集成场景①同样用**真实 IsolationManagementService 完整四依赖手动组装**（隔离键必须真实写入——其四依赖：isolation_repository/agent_repository 场景级客户端、event_publisher=_RecordingEventPublisher、agent_config_loader 经 resolve("agent_config_loader") 取——无状态零连接 resolve 安全，5-3 集成 `_instantiate_agent` L227 同款） |

- [x] Subtask 4.1-4.2: 两循环红绿变异重构
- [x] Subtask 4.3: 回归面清单全绿确认

**完成标准/Definition of Done:** 注入链完整；回归面全绿；隔离初始化端到端可达

---

### Task 5: CLI isolation-status / set-isolation 子命令

**关联 AC:** AC-3、AC-4（CLI 面）、AC-6

#### TDD 循环 A：子命令 + 守卫

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/interfaces/cli/test_agent_cli.py` 追加（`_parse_isolation_level` 两道守卫——**顺序对齐 `_parse_role` 先例（R1-F07）**：第一道 `try IsolationLevel(raw) except ValueError` 映射 446 `from None`（唯一拦截非法字符串的活路径）/第二道 `SUPPORTED_ISOLATION_LEVELS` 预检（唯一拦截「合法枚举但未开放」即 L1 的活路径）；context 携带原始输入与支持列表/isolation-status：参数必填 --agent-id/成功输出等级+三维度策略+时间（stdout 断言）/443/447/201 → exit 1 + stderr 编码断言 `\[EXCEPTION_(?:201\|4[0-9]{2})\]` 精确匹配（R1-F15：201 是 ValidationError 族须同匹配；R2-回归-4 表格内转义修正）/set-isolation：--agent-id/--level/--reason 三参数必填/成功输出切换摘要（previous→target）/no-op 输出提示且 exit 0/443/446/447/201 → exit 1/`--level L1` 字符串 → 446（统一异常出口，argparse 不做 choices 静默拒绝） |
| 🟢 绿 | `src/entrypoints/agent_cli.py` 追加两子命令（骨架模板照抄 **load-profile/run-task 的 `_ensure_bootstrapped()` 幂等形态**——R1-F06：禁照抄 instantiate 直调 `bootstrap()`，conftest 已 bootstrap 的进程内二次调用必抛 ConflictError；**禁照抄 `_parse_role` 的 `.lower()` 归一**——R2-组合-4：AgentRole 枚举值全小写而 IsolationLevel 枚举值全大写，lower 化将拒绝全部合法输入（"L4"→"l4"→ValueError→446）；--level 大小写敏感（契约 `<L4|L3|L2>`）；守卫先于 bootstrap/退出码/`_close_connection_pools`；main() 分发分支插在既有 fallback `_run_instantiate_cli` 之前；resolve `isolation_management_service`；`SUPPORTED_ISOLATION_LEVELS` 模块常量 = 显式元组字面量 `("L4", "L3", "L2")`——**禁从 frozenset 迭代派生**（迭代序不稳定致帮助文本漂移，R1-F34），测试断言 `set(SUPPORTED_ISOLATION_LEVELS) == {l.value for l in MVP_ALLOWED_LEVELS}` 双锁防 V2 开放 L1 时漏改） |
| 🟡 变异 | 删第一道 except 分支 → "L9" 非法字符串用例红（ValueError 逃逸被断言捕获——5-1 Task 5 变异同款）→ 还原；删第二道预检 → `--level L1` 用例红 → 还原 |
| 🔄 重构 | ruff + mypy |

- [x] Subtask 5.1: 🔴 红 — CLI 测试
- [x] Subtask 5.2: 🟢 绿 — 子命令实现
- [x] Subtask 5.3: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:** CLI 全退出码路径绿

---

### Task 6: 集成测试 + 性能验收

**关联 AC:** AC-5（+ AC-2/AC-4 真实 Redis 全链）

#### TDD 循环 A：全链集成 + 性能三指标

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_agent_isolation.py`（真实 Redis 6380 门控 ping 失败 skip + 手动组装全链 + `pytestmark = [pytest.mark.integration, pytest.mark.redis, pytest.mark.benchmark, pytest.mark.xdist_group("agent-isolation-perf")]`。场景①全链：真实 `InstantiateAgentUseCase`（手动组装：config_loader/repository/isolation_service[真实服务+真实隔离仓储]/InMemoryEventBus 或 recording）→ instantiate → 隔离键 L4 断言 → set-isolation 等价服务调用切 L3 → 键 L3 + recording 恰一次事件 → 双键 teardown + exists 复核。场景②P95：`get_isolation_state` warmup 1 + 20 采样 `quantiles(n=20)[18] < 0.1`（perf_counter；计时含 VO 重建全链；同源派生阈值常量；**交付形态（R2-回归-8）**：模块级采样缓存计时 helper（`_PERF_CACHE` 单槽缓存——供验收 AC-5×3 委托共享，同 xdist_group 同 worker 缓存命中，5-3 集成 test_integration_agent_workflow.py L71/L300 先例；helper 内 sample_keys **双键登记**——每轮 initialize 产生 agent+isolation 双键即时清理，5-3 单键形态的双键扩展——R2-组合-9）。场景③持久化成功率：20 次连续 initialize+读回全成功（分母分子断言 20/20）。场景④并发 10：10 agent_id `asyncio.gather` 并发 init+switch+get 全成功且各自状态独立（互不串扰断言——agent_i 状态==各自目标等级；**目标等级互异设计（R1-F42）**：奇数 agent 切 L3、偶数切 L2，使串扰在主断言即可红而非仅靠变异兜底）。场景⑤事件真实发布链路（5-3 场景⑤先例）：resolve 真实 `event_publisher`（DualChannelEventBus）+ 真实服务 switch 一次 → PG `event_outbox` 落行断言（`event_type=="IsolationLevelSwitched" and aggregate_id==str(agent_id)` 精确查询禁全表计数；outbox 追加语义无清理面；PG 门控动态 skip——构造 try/except 形态对齐 5-3 先例；**RabbitMQ 缺席不影响本场景（R1-F31）**：reliable 通道 publish 链路只写 PG outbox，实际投递归 AsyncOutboxPoller 异步侧，无需 rabbitmq 门控）。发布面口径差声明随 docstring（场景①recording 替身 vs 场景⑤生产 outbox） |
| 🟢 绿 | 全场景转绿（验证型——被测链路已由 Task 1-5 交付） |
| 🟡 变异 | P95 阈值突变（0.1→0.0001）→ 红 → 还原；并发断言弱化为聚合无个体 → 串扰用例红设计验算（构造两 agent 切不同等级断言互不影响——仓储键隔离的判别力实证）→ 还原 |
| 🔄 重构 | xdist_group + benchmark 场景级标记收敛 |

- [x] Subtask 6.1: 🔴 红 — 五场景编写（含场景⑤真实发布链路）
- [x] Subtask 6.2: 🟢 绿 — 转绿 + 计时校准
- [x] Subtask 6.3: 🟡 变异 + 🔄 重构（双键清理纪律 + Redis 门控封装）

**完成标准/Definition of Done:** 集成 5 场景绿（PG 缺席时 4 绿 + 1 skip）；性能三指标断言活

---

### Task 7: SDD 架构约束验证测试

**关联 AC:** AC-6

#### 架构验证测试实现（验证器 A-D）

- [x] Subtask 7.1: 创建 `tests/unit/architecture/test_arch_agent_isolation.py`
- [x] Subtask 7.2: 验证器 A——domain 零外部依赖（isolation_policy.py/isolation_state.py/isolation_events.py/agent_exceptions.py/isolation_repository.py AST 扫描禁 pydantic/redis/langgraph import）
- [x] Subtask 7.3: 验证器 B——组合根外零实例化（RedisIsolationRepository/IsolationManagementService 全仓 AST 扫描禁业务代码直接实例化；tests 白名单前缀）
- [x] Subtask 7.4: 验证器 C——端口方向（application 服务与 use_cases import 白名单：domain.ports/domain.entities/domain.value_objects/domain.events/**application.ports**（R1-F19 补——IsolationManagementService 实现 application 端口、InstantiateAgentUseCase 注入它均必然 import src.application.ports，白名单缺它则合法代码被误判红）合法 / src.infrastructure 非法；CLI entrypoints→application 合法）
- [x] Subtask 7.5: 验证器 D——lifetime 决策落地（两行式收窄——R1-F29：`spec = _global_registry.get("isolation_repository")` → `assert spec is not None` → `assert spec.lifetime == Lifetime.SINGLETON`——registry.get 返回 `PortSpec | None`，一行式链式取属性会被 pre-commit mypy（覆盖 tests/）打 None 访问红；test_arch_data_source.py L159 先例形态；DC-7 D7 核销的架构锚，防回退 SCOPED 无声复发）
- [x] Subtask 7.6: 循环依赖检测用 ruff/isort（不引入 pylint）+ 全套报告

**完成标准/Definition of Done:** 验证器 A-D 全绿；违规即红

---

### Task 8: 开发结束验收测试

**关联 AC:** 全部

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 验收 feature 追加收尾场景（src 完成清单/tests 四目录完成清单逐项确认——AC-6.4 形态） |
| 🟢 绿 | BDD 步骤实现（文件存在性 + 关键符号 grep 断言——5-2/5-3 AC-6.3 同款） |
| 🔄 重构 | 场景命名收敛 |

- [x] Subtask 8.1: 收尾场景红绿
- [x] Subtask 8.2: 全量回归（`pytest tests/ -n 8` + 连续 5 次稳定）+ ruff/mypy 收尾校验 + 三条红线自查
- [x] Subtask 8.3: 文档同步（architecture.md §5 EIP 实现状态注记 + §13 目录树 isolation_* 落位注记 + sisys-uni-exception-design.md §3.3.2 已随 Task 1 同步复验）+ 留项终态更新（D6/D7 核销 = 5-1 story 台账 L1143/L1144 勾选注记 + deferred-work.md 补索引行；session_storage 续期/工具熔断评估结论 = deferred-work.md 原条目更新）

**完成标准/Definition of Done:**
- [x] 全量 18 场景（17 + 收尾 1）全绿；Story 可进入 review

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md) §5（L643-666 EIP 四级表/触发/自动恢复）、§13（L1733-1772 isolation_* 目录树规划）、§4.4（L420-424 EIP 隔离管理流程）；[`sisys-core-domain-design.md`](../../../docs/architecture/sisys-core-domain-design.md) §17.3.3（L1192-1266 EIPExecutor 伪码）、L1455-1460（eip_config）；or.md L18/L23/L30/L35/L48/L280-289。

- **架构模式：** 六边形（Ports & Adapters）；EIP 协议 = 领域模型（策略表+状态聚合）+ 应用编排（管理服务）+ 基础设施持久化（Redis 仓储）——严格 R1（domain 基础端口 IsolationRepository）/ R2（application 端口组合注入——三 domain 端口 + agent_config_loader 同层应用端口，R1-F01）/ R3（infrastructure RedisIsolationRepository 技术实现）/ R4（CLI 接口适配）
- **设计约束：** domain 零外部依赖（AST 门禁）；Agent 实体不修改（5-1「复用不修改」纪律）；隔离状态独立键空间
- **接口治理：** 新端口两枚走 PortSpec 全套（registry/resolver/contract gate/契约测试）；既有端口消费方变更一项（agent_instantiation_use_case 注入扩展——契约变更登记）
- **技术栈：** Python 3.11+ / redis-py asyncio（Hash + MULTI/EXEC pipeline）/ 标准库 dataclasses+Enum（domain）

### 关键架构决策

| # | 决策点 | 选定方案 | 备选方案（弃用理由） | 依据 |
|---|--------|---------|---------------------|------|
| DC-1 | 隔离状态承载形态 | **独立 `IsolationState` 聚合 + 独立 Redis 键空间 `sisys:isolation:{agent_id}`**（domain/entities/isolation_state.py + domain/ports/isolation_repository.py + Redis 仓储——AgentRepository 同款模式照抄）。不改 Agent 实体（5-1「复用不修改」纪律）；隔离状态有独立生命周期（切换/过期）与独立读写面（检查入口 P95 计时锚），与 Agent 实体状态机解耦；5.6 IsolationSwitchLog 亦为独立实体（architecture.md L806）——EIP 族独立聚合对齐 | a) Agent 实体加 isolation_level 字段（弃用：修改 5-1 已 done 实体+序列化，回归面大且耦合两聚合生命周期；架构 L797 规划 Agent 含 isolation_level——偏离声明 D-1）；b) 塞进 WorkflowAgentState 图状态（弃用：图状态是单次执行态非跨执行协议态，且 InMemorySaver 无持久化——调研实证）；c) 复用 session_storage（弃用：会话状态≠协议状态，session_storage 本身休眠中） | or.md L23（隔离是不变约束独立维度）；RedisAgentRepository 先例；5-1 纪律 |
| DC-2 | 四级策略表落位与 L1 排除 | **domain/value_objects/isolation_policy.py 常量表**（ISOLATION_POLICIES + get_isolation_policy + MVP_ALLOWED_LEVELS={L4,L3,L2}）——纯静态领域规则零 IO，常量表+工厂足够（不建领域服务类）。L1 融合态 MVP 禁用：其开放前提（SYS AGENT 监督/紧急态/强制审计——core-domain L1221-1228）全是 V2 设施 | a) 逐 Agent 实例化策略对象（弃用：策略是无状态共享规则，实例化冗余）；b) 配置文件承载等级表（弃用：四级表是协议契约非部署参数——架构 §5.1 硬编码表；allowed_levels 的 per-agent 配置化归 V1 需求出现时再做）；c) L1 开放（弃用：无 SYS 监督的 L1=无监督完全共享，安全 Story 不可接受） | architecture.md §5.1；core-domain eip_config.allowed_levels=[L4,L3,L2] 先例；Simplicity First |
| DC-3 | 隔离初始化时机与失败语义 | **InstantiateAgentUseCase 注入改造（实例化即隔离）+ fail-fast**：execute 编排骨位 save agent → isolation initialize（等级=config.default_isolation_level、TTL=config.state_ttl 双消费）→ publish AgentInstantiated；初始化失败 → 实例化失败向上抛（安全基线优先——静默成功=安全默认破洞埋雷到运行时）；残留 agent 键由 TTL 86400 自然回收（注记，不做补偿删除——R1-F22 措辞校准：Redis 有 MULTI/Lua 跨键原子性但**无跨键回滚**，补偿需应用侧逆向写、复杂度不值 TTL 兜底）。**残留态推演（R1-F09 + R3-F08 通道澄清）**：初始化失败后 agent 键存活 ≤24h，期间该 agent_id 的隔离查询/切换走 443 通过 → 447（447 第三成因，见异常契约节）；**服务级以同 id 重新 initialize 可自愈**（upsert 覆盖写）——用例/CLI 通道每次 execute 生成新 uuid4，残留态在新 id 下不可达、靠 TTL 自然回收。**重复实例化语义注记（R1-F33）**：同 agent_id 二次 instantiate 会将已显式切换的隔离态覆盖回默认 L4——方向安全（回最严格等级），设计意图，initialize 端口 docstring 注明 | a) 惰性 get_or_initialize（弃用：「Agent 已实例化→默认 L4 生效」语义弱化为首次访问生效；且每读路径都要处理初始化竞态）；b) 初始化失败记日志继续（弃用：5-1 事件发布容错先例不适用——发布是通知可丢，隔离是安全基线不可缺）；c) 补偿删除已写 agent 键再抛（弃用：复杂度>收益，TTL 兜底） | epics 5.4 AC「Given Agent 已实例化…默认隔离等级 L4」；安全内建（prd 安全基线） |
| DC-4 | 应用层端口形态 | **单端口 `IsolationManagementServicePort` 三方法（initialize/get/switch）+ CLI 直消费**：三操作同聚合（IsolationState）同关注点（EIP 管理）；AgentWorkflowServicePort 七方法多方法端口先例；避免三个微用例类蔓延；interfaces→application 方向合法（依赖方向矩阵）。实现类构造四依赖（三 domain 端口 + agent_config_loader——R1-F01 TTL 真源通道） | a) 三独立用例类（InitializeIsolation/GetIsolation/SwitchIsolation UseCase——弃用：类蔓延，三操作共享守卫序与依赖，拆分重复装配）；b) domain/services/isolation_service.py 接口（弃用：架构树 L1749 规划位——但隔离管理需编排仓储/事件发布，属应用编排关注点；纯策略已留 domain——偏离声明 D-2）；c) 塞进 AgentService 大端口（弃用：语义重复端口违模板纪律） | 5-3 AgentWorkflowServicePort 先例；R2 组合注入；依赖方向矩阵 |
| DC-5 | 切换守卫序与 no-op 语义 | **守卫序：Agent 存在(443) → 隔离状态存在(447) → 等级合法(446)**（服务层序 + 实体内等级守卫）；等级合法性校验内聚实体 `switch_to`（领域不变量——initialize/switch_to 两入口统一守卫，CLI 只做字符串→枚举转换守卫）。**同等级 no-op**：switch_to 返回 False → switched=False + 零仓储写 + 零事件发布（幂等；「切换」事件语义要求前后等级相异；TTL 不刷新——no-op 非活跃信号） | a) no-op 也刷新 TTL（弃用：查询型重复调用会无限续期，状态永不过期）；b) no-op 抛 409 冲突（弃用：幂等重试场景下 no-op 是正常态非错误）；c) 等级校验放服务层（弃用：initialize 与 switch 两入口要重复校验，实体内聚单点真源） | or.md L48 事件语义；REST 幂等惯例；领域不变量内聚原则 |
| DC-6 | 事件复用与纪律收紧 | **复用 `IsolationLevelSwitched` 零新建零登记**（骨架+双登记 1.x 已就绪）；**收紧四字段 kw_only 必填**（agent_id/previous_level/target_level/trigger_reason——切换事件核心语义必填；approval_chain/switch_timestamp 保留默认）；回归面四测试文件同步（test_new_events/test_event_serialization/test_acceptance_domain_event_definition/test_event_architecture——src 零发布方 + AutoTriggerHandler 字符串引用零 src 回归） | a) 新建 AgentIsolationSwitched 事件（弃用：与既有事件语义重复——禁止同义事件；且 yaml/router 已登记旧名）；b) 维持 default_factory 旧形态（弃用：切换事件 agent_id 可缺省自铸=断链 aggregate 关联；5-2 已立 kw_only 纪律，旧风格是 1.x 骨架遗留） | events/enums.py L39-45；agent_events.py L87-88 纪律注释（R1-F12 行号勘误：原引 L77-79 实为 docstring 区）；模板「禁止同义接口重复定义」 |
| DC-7 | isolation_repository lifetime 与 D7 核销 | **SINGLETON**：无状态仓储 + adapter（SINGLETON）构造注入零 IO，被 SINGLETON 服务捕获无 captive 实害——**D7 评估落地：新增面从源头避免**。**新捕获关系显式登记（R1-F20）**：新 SINGLETON isolation_management_service 捕获存量 SCOPED agent_repository——无实害（agent_repository 无状态 + clear_scoped 未接线环境下 SCOPED≡SINGLETON，与 isolation_repository 同款理由），属「新增消费面沿既有端口形态」非「新增 SCOPED 端口」。**存量处置**：agent_repository（SCOPED）/skill_loader（SCOPED）维持现状（组合根 L2697-2699 lifetime 注记已在；翻存量=改 5-1/5-2 契约断言+偏离 77 处 SCOPED 仓储主流惯例，收益低于回归面）。**D7 以「评估完成+决策+新增面避免+新捕获登记」核销**，架构锚=验证器 D（lifetime 断言防回退） | a) isolation_repository SCOPED 跟随主流（弃用：被 SINGLETON 服务捕获=captive 复发，D7 触发 Story 又造新 D7）；b) 存量 agent_repository/skill_loader 一并翻 SINGLETON（弃用：违反 surgical changes——存量属 5-1/5-2 交付面且无实害；R2 科学性复审已判明属架构级决策，本 Story 决策=不动存量） | deferred-work D7；5-1 R2 科学性复审；组合根 lifetime 注记 |
| DC-8 | 异常 446/447 设计 | **446 IsolationLevelNotSupportedError（BusinessException，422——441 精确注册先例对齐，「不支持的取值」族）**：双触发（非法枚举值字符串 + 合法枚举但 MVP 禁用即 L1）——441 AgentRoleNotSupportedError 构造器同款（level+supported 列表 context）；CLI 转换守卫唯一出口。**447 IsolationStateNotInitializedError（BusinessException，404——443 NotFound 族语义对齐）**：隔离状态缺失。**复用**：443（Agent 不存在）/440（TTL 越界 + loader 非法等级）/242（实体不变量）/103 StorageError（连接异常） | a) 等级非法复用 201 ValidationError（弃用：441 先例已定「不支持的取值」用专用异常带 supported 列表 context——CLI stderr 编码断言与 5-1 一致性）；b) 状态缺失复用 443（弃用：Agent 存在与隔离状态缺失是两个聚合两个语义，447 是 TTL 漂移的精确诊断）；c) 新增状态转换异常（弃用：等级切换无非法转换对——MVP 内 {L4,L3,L2} 任意互切合法，243 无触发面） | 441→422/443→404 精确注册先例（exception_handlers.py L269/L271——R1-F11 行号勘误）；_code_ranges L122 预留段 |
| DC-9 | TTL 策略 | **隔离键 TTL=AgentConfig.state_ttl 同源**（初始化时与 Agent 键同值写入；switch 重置时经服务第四依赖 agent_config_loader 重取真源——R1-F01）；**切换 save 重置 TTL**（RedisAgentRepository save 语义同款。R1-F10 论证修正：Agent 键全仓唯一 save 点=实例化（agent_instantiation.py L126），无续期方——原「活跃 Agent 续期」前提不成立；切换重置的真实语义是隔离键生命周期独立延长，Agent 键先亡态由 443 前置守卫拦截（无害），孤儿隔离键由自身 TTL 回收——良性单向漂移，风险 #6 已补双向注记）；TTL 越界防御校验抛 440（真源是配置——配置语义异常） | a) 隔离键独立 TTL 配置项（弃用：YAGNI——无独立过期需求）；b) 切换不重置 TTL（弃用：与仓储 save 重置语义分叉需签名 `ttl: int \| None`，隔离协议 MVP 保持与 AgentRepository 同款 save 语义更一致）；c) 服务侧硬编码默认 TTL（弃用：第二真源违 SSOT） | AgentConfig.state_ttl 唯一真源；RedisAgentRepository save 重置语义 |
| DC-10 | 切换事件发布失败语义 | **记日志不回滚**：switch 内 repo.save 成功后 publish 失败 → logger.warning + 正常返回结果（状态已切换是事实、事件是通知——与仓储写不一致的补偿归 5.6 审计链与 outbox 死信专项）；reliable 通道下 publish 即 outbox 写入，失败罕见 | a) 发布失败回滚等级（弃用：Redis 无事务回滚已写状态；为通知回滚事实是本末倒置）；b) 发布失败抛出（弃用：切换本身成功，抛出让 CLI 误报系统错误） | 5-1 AgentInstantiated 发布容错先例；outbox 可靠通道设计 |
| DC-11 | 性能验收口径 | **P95 = `get_isolation_state` 服务全链真实 Redis 计时**（R1-F02 修订：443 存在性守卫 + 隔离态读**两次读**，含协议解析+VO 重建；warmup 1 + 20 采样 quantiles[18] < 0.1s——本地 Redis RTT ~1ms，两次读预算仍 50 倍宽裕，断言真实下界=计时含 fakeredis 替身不可——集成必须真实 Redis）；**持久化成功率 = 20 次连续 initialize+读回全成功**；**并发 10 = 10 agent 并发 init+switch+get gather 全成功 + 状态互不串扰**（个体等级断言非聚合断言 + 目标等级互异——键隔离判别力） | a) P95 测纯 Redis GET（弃用：不含 VO 重建的口径低估实际检查成本）；b) 并发只断言全成功（弃用：聚合断言对键串扰不敏感——变异不可红） | epics L1612-1614；profile_loading P95 先例；epics「并发隔离 Agent≥10」语义=隔离互不干扰 |
| DC-12 | AgentConfig D6 回填边界 | **回填两项 + 钉子两项**（R2-回归-1 口径收口，对齐 R1-F03/F04 定稿）：回填 = isolation 枚举化 + 标量类型守卫（统一 440 分码对齐 `_fail` 文件先例）；钉子 = 空白串与 strip 现状（拦截语义已存在——钉子测试锁定即核销，存储值不做 strip 归一）。5-4 是 D6 最后触发（5.3/5.4），不回填则永久悬空；字段类型 `str→IsolationLevel` 是 SSOT 收紧（yaml loader str→enum 转换守卫映射 440——"L4"→L4_HARD，非法值 reason 中文自然语言弃 snake_case——R1-F04）；ceo_agent.yaml 值 "L4" 合法零改动 | a) 仅回填 isolation 项（弃用：D6 其余三项是同一留项的组成部分，拆半核销台账不闭合）；b) 保留 str 类型+值域校验（弃用：枚举类型才是 SSOT——裸 str 是 5-1 遗留形态，AgentConfig docstring 已注明 5.4 消费） | 5-1 D6 残余清单；AgentConfig L46/L57 docstring；events/enums.py SSOT |

### 已知下游风险（本 Story 不处置，消费方 Story 决策）

1. **IsolationLevelSwitched 无活跃订阅者**：AutoTriggerHandler 字符串清单已含但未进 handler_names 订阅列表（注册≠订阅——5-3 风险 #2 同形态）；黑板权限更新/协作状态同步（or.md L48 触发动作）归 5.11/V1；**5.6 切换日志是首个业务消费方**（订阅接线归消费方 Story——5.6/5.7 口径统一见 R1-F39）。
2. **三重隔离策略无执行面**：本 Story 交付策略声明（数据模型）；Prompt/工具/数据访问的运行时强制拦截归 5.5（其 P0 验收=探针拦截率 100%）。`tool_isolation` 等维度当前无消费方——策略表是 5.5 的契约输入。
3. **自动恢复未实现**：30 分钟无活动恢复 L4（architecture §5.3）依赖"活动"信号定义与 L2 协作态任务（V1 联合分析组）——MVP 无降级发生源（仅用户显式切换），无恢复需求；V1 FR-AC-09 立项时连带实现。
4. **切换审计仅事件通道**：切换历史目前只经 reliable 事件进 outbox；IsolationSwitchLog 实体/多维检索/WORM 归档归 5.6——事件 payload 是 5.6 的数据源契约。
5. **approval_chain 恒空**：MVP 用户直切无审批链；SYS 命令通道与审批链填充归 V1（FR-AC-09）。事件字段已预留。
6. **〔预防性登记〕隔离键与 Agent 键 TTL 漂移（双向——R1-F30 补注 + R3-F07 方向修正）**：两键独立 expire——①「Agent 键存活而隔离键先过期」方向**经写序推演不可构造**（agent 键 T0 写、隔离键 T1>T0 写同 TTL，隔离键过期恒晚于 Agent 键；R1-F30 原注「成因仅限创建时序微秒差」方向写反——微秒差方向正是隔离键晚亡，即下条孤儿方向），447 真实成因收敛为「存量 Agent 无隔离键（5.4 部署前实例化）」与「fail-fast 残留」两因（AC-3.2 人工删键路径不受影响）；②**切换重置 TTL 使隔离键晚于 Agent 键过期**（孤儿隔离键）→ Agent 已 443 前置守卫拦截不可达，孤儿键由自身 TTL 回收——良性单向漂移，无需处置。消费方可选自愈策略（服务级同 id 重 initialize 默认 L4）归 5.5/后续决策——MVP fail-fast 语义即设计意图。
7. **〔预防性登记〕同 Agent 并发切换无锁竞态（R3-F06）**：两并发 switch 同 agent 均过 443/447 守卫（各自 get_by_agent_id 重建独立实例）→ 后写覆盖终态、两事件均发布——事件序与终态可能不一致且无检测面。MVP 唯一触发通道为单用户 CLI 显式请求，接受「单 Agent 串行操作」假设；5.5/V1 自动触发多源并发立项时需评估（Agent 级锁或版本号乐观并发）。AC-5.3 按设计只测互异个体不测同 agent 并发。

### 设计文档偏离声明

> 90-8 先例机制：实施与设计文档冲突时显式声明，实施后同步更新文档。

| # | 冲突点 | 偏离内容 | 实施后同步动作 |
|---|--------|---------|---------------|
| D-1 | architecture.md L797（Agent 实体存储映射含 isolation_level 字段） | 隔离状态独立聚合 + 独立键空间（DC-1），Agent 实体不加字段 | Task 8 在 architecture.md §5 补「MVP 隔离状态独立持久化，Agent 实体字段规划归 V1 评估」注记 |
| D-2 | architecture.md L1749（规划 domain/services/isolation_service.py EIP 隔离服务接口） | 应用编排端口落 application/ports/isolation_management.py（DC-4）；纯策略表留 domain value_objects | Task 8 在 §13 目录树补落位注记 |
| D-3 | or.md §17.3.3 EIPExecutor 伪码（evaluate_and_switch 含触发检测/审计日志/自动恢复） | MVP 交付协议基础：触发检测仅「用户显式请求」通道（architecture §5.2 四触发之一）；关键词频率/任务依赖/SYS 命令/自动恢复归 V1；IsolationSwitchLog 归 5.6 | Task 8 在 architecture.md §5 补 MVP 范围注记（范围边界表已列） |
| D-4 | epics L1626-1627 建议测试路径 `tests/unit/architecture/test_eip_isolation.py`/`tests/integration/test_eip_isolation_integration.py` | 按项目实际目录结构与命名（unit 按层分目录/test_arch_* 前缀/集成无后缀 + agent_isolation 家族命名——与 test_acceptance_agent_* 三先例一致）——5-3 D-5 同款 | 不修改 epics（历史规划文档）；dev 以本 Story 测试分类表为准 |
| D-5 | core-domain-design §17.3.3 策略表 dict 字符串键（"L4": {...prompt_isolation: True...}） | 枚举键 + 类型化 VO（IsolationPolicy frozen dataclass + DataIsolationMode 枚举）——domain 禁裸 dict 契约载体 | 无需动作（设计伪码→实现的正常类型化） |
| D-6 | IsolationLevelSwitched 1.x 骨架 default_factory 形态 | kw_only 必填收紧（DC-6）——5-2 新事件纪律对齐 | isolation_events.py docstring 注记（Task 1 循环 D 绿阶段） |

### 关键代码模式参考

**IsolationState 实体骨架（domain/entities/isolation_state.py——非 frozen 对齐 Agent 实体，领域守卫内聚）：**

```python
@dataclass
class IsolationState:
    """Agent EIP 隔离状态聚合（独立于 Agent 实体的协议状态）。

    每个 Agent 一条，键空间 sisys:isolation:{agent_id}；等级合法性守卫内聚本类
    （initialize/switch_to 两入口统一），MVP 允许等级集见 MVP_ALLOWED_LEVELS。
    """

    agent_id: uuid.UUID
    current_level: IsolationLevel
    initialized_at: datetime
    updated_at: datetime
    last_trigger_reason: str

    def __post_init__(self) -> None:
        """不变量校验：UUID/枚举实例/非空触发原因（失败抛 EntityValidationError 242）。"""
        ...

    @classmethod
    def initialize(cls, agent_id, level, *, now=None) -> "IsolationState":
        """工厂：默认等级初始化（非法等级值或非枚举实例 → IsolationLevelNotSupportedError 446）。"""
        if not isinstance(level, IsolationLevel) or level not in MVP_ALLOWED_LEVELS:  # 双条件（R3-F01）
            raise IsolationLevelNotSupportedError(level=str(getattr(level, "value", level)), supported_levels=...)
        now = now or datetime.now(UTC)                                                 # 单 now 双用
        return cls(agent_id=agent_id, current_level=level,
                   initialized_at=now, updated_at=now, last_trigger_reason="initial_default")

    def switch_to(self, target_level, trigger_reason, *, now=None) -> bool:
        """切换等级：同等级 no-op 返回 False（零变更）；合法切换更新三字段返回 True。"""
        if not isinstance(target_level, IsolationLevel) or target_level not in MVP_ALLOWED_LEVELS:
            raise IsolationLevelNotSupportedError(...)  # 446 双条件（R3-F01——isinstance 先行防裸 str 穿透）
        if not str(trigger_reason).strip():
            raise EntityValidationError(...)             # 242
        if target_level == self.current_level:
            return False
        self.current_level = target_level
        self.updated_at = now or datetime.now(UTC)
        self.last_trigger_reason = trigger_reason.strip()
        return True
```

**IsolationManagementService.switch 流程（application/services/isolation_management_service.py——守卫序 + no-op 零副作用 + 发布容错）：**

```python
async def switch_isolation_level(self, agent_id, target_level, trigger_reason, approval_chain=()):
    """守卫序：Agent 存在(443) → 隔离状态存在(447) → 等级合法(446，实体内聚)。"""
    agent = await self._agent_repository.get_by_id(agent_id)
    if agent is None:
        raise AgentNotFoundError(agent_id=str(agent_id))          # 443 复用
    state = await self._isolation_repository.get_by_agent_id(agent_id)
    if state is None:
        raise IsolationStateNotInitializedError(agent_id=str(agent_id))  # 447
    switched = state.switch_to(target_level, trigger_reason)      # 446 守卫在实体
    if not switched:
        return IsolationSwitchResult(switched=False, state=state, event=None)  # no-op 零副作用
    config = await self._config_loader.load(agent.role)           # TTL 真源（R1-F01——agent 复用 443 守卫实例）
    await self._isolation_repository.save(state, ttl=config.state_ttl)
    event = IsolationLevelSwitched(agent_id=agent_id, previous_level=..., target_level=...,
                                   trigger_reason=..., approval_chain=list(approval_chain))  # kw_only 必填（DC-6；approval_chain 显式转发）
    try:
        publish_result = await self._event_publisher.publish(event)
    except Exception:                                             # 发布失败记日志不回滚（DC-10）
        logger.warning("隔离切换事件发布失败（状态已切换）: agent_id=%s", agent_id, exc_info=True)
    else:
        if not publish_result.is_success:                         # 真实总线失败面（RabbitMQEventBus 捕获异常返回失败结果不抛出）
            logger.warning("隔离切换事件发布失败结果（状态已切换）: agent_id=%s", agent_id)
    return IsolationSwitchResult(switched=True, state=state, event=event)
```

> 注（R1-F01 定稿，原「Task 3 设计时定稿」占位已闭合）：TTL 真源是 AgentConfig.state_ttl，服务第四依赖 `agent_config_loader` 取得（真源单点、服务侧无默认值）；服务构造签名 = isolation_repository / agent_repository / event_publisher / agent_config_loader 四依赖。

**CLI `_parse_isolation_level` 两道守卫（agent_cli.py——`_parse_role` 同款，禁裸 `IsolationLevel(value)`）：**

```python
SUPPORTED_ISOLATION_LEVELS = ("L4", "L3", "L2")   # 显式字面量（禁 frozenset 迭代派生——迭代序不稳定）；测试断言与 MVP_ALLOWED_LEVELS 集合相等双锁

def _parse_isolation_level(raw: str) -> IsolationLevel:
    """CLI 等级字符串转换守卫：非法值映射 IsolationLevelNotSupportedError(446)——_parse_role 同款两道守卫（R1-F07 顺序对齐先例）。"""
    try:
        level = IsolationLevel(raw.strip())
    except ValueError:                                            # 第一道：非法枚举字符串（"L9"）
        raise IsolationLevelNotSupportedError(level=raw, supported_levels=SUPPORTED_ISOLATION_LEVELS) from None
    if level not in MVP_ALLOWED_LEVELS:                           # 第二道：合法枚举但未开放（L1 融合态）——此处 level 已是枚举实例（第一道转换），in 判定语义正常，不受 R3-F01 裸 str 穿透影响
        raise IsolationLevelNotSupportedError(level=raw, supported_levels=SUPPORTED_ISOLATION_LEVELS)
    return level
```

**验收 context fixture 双键清理骨架（test_acceptance_agent_isolation.py——5-3 形态 + 双 namespace）：**

```python
@pytest.fixture
def context(event_loop, acceptance_env_config):
    """场景级独立 Redis 客户端 + 同循环关闭 + 双键精确清理（agent/isolation 两 namespace）+ 覆写还原挂点。"""
    redis_client = aioredis.Redis(host=..., port=..., password=..., decode_responses=True)
    ctx = {"_loop": event_loop, "_redis_client": redis_client, "_agent_ids": [], "_restorers": []}
    yield ctx
    for restore in ctx["_restorers"]:          # R1-F25：先还原端口覆写再删键（5-3 先例 L227-232——防覆写泄漏污染后续场景）
        restore()
    for agent_id in ctx["_agent_ids"]:
        for ns in ("agent", "isolation"):
            _run_async(event_loop, redis_client.delete(build_key(ns, str(agent_id))))
    _run_async(event_loop, redis_client.close())
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 5.3](./5-3-single-agent-workflow.md)（文档审查 4 轮+终审 61 表行 + 代码审查 5 轮收敛的完整教训链——R1-F48 口径校准）+ 5-1 遗留（文档审查 Round 3 发现 #23 resolve 死连接/Task 3 StorageError cause 教训）

**关键学习/Key Learnings:**
- **场景三属性分档是验收设计的第一分叉**（层级/依赖/替身——本 Story 简化为层级+Redis+事件三档）
- **断言锚点与替身分派键独立** + no-op/零副作用断言用「恰一次/零次」计数而非「至少一次」
- **手动组装纪律**：resolve SCOPED/SINGLETON 钉住全局 Resolver → 跨循环死连接（"Event loop is closed"）——验收/集成一律场景级客户端手动组装；resolve 仅接线断言
- **teardown 逐键精确删除 + exists 复核**（禁 delete_pattern/flush/全库 scan_iter）
- **`from exc` 仅设 `__cause__`**——DomainError.cause 属性须构造参数传递（5-1 Task 3 实测）
- **每 then 真实断言（禁 pass 占位）+ 全场景显式绑定（禁悬空）**；BDD 禁 `@pytest.mark.asyncio`
- **同码多因断言带 context 区分锚**（446 双触发路径参数化）
- **既有契约变更必须全量回归面清单**（适配器契约变更回归规则——本 Story 三处：事件收紧/用例构造扩展/AgentConfig 类型收紧）

**应用到本故事/Applied to This Story:**
- [ ] 17 场景三属性分档表（Task 0.6 定稿）
- [ ] no-op/守卫序 calls 计数断言（Task 3）
- [ ] 双键清理 + 手动组装（Task 6/验收）
- [ ] 三处契约变更回归面清单（Task 1 循环 D / Task 4 循环 B / Task 1 循环 E）

### deferred-work 处置（5-4 触发项分流）

| 项 | 处置 |
|----|------|
| D7 captive dependency（5-1，触发=5.4 评估） | **本 Story 核销**（Task 0 评估 + DC-7 决策：isolation_repository SINGLETON 新增面避免 + 存量维持注记 + 验证器 D 架构锚；核销落点 = 5-1 story 留项台账 L1144 勾选注记 + deferred-work.md 补索引行——R1-F27：原写「deferred-work 登记核销」落点错位，deferred-work.md 无 D7 条目） |
| D6 AgentConfig 直构造残余（5-1，触发=5.3/5.4） | **本 Story 核销**（Task 1 循环 E 全量回填四项（440 分码对齐文件先例——R1-F03）；核销落点 = 5-1 story 留项台账 L1143 勾选注记 + deferred-work.md 补索引行——R1-F27 同上） |
| session_storage + RedisSessionStorage（deferred-work L130，5-3 续期触发=5-4+） | **再续期**（DC-1：IsolationState 是协议状态非会话状态；触发移至多轮会话需求 Story——多轮会话功能立项时） |
| 工具熔断挂点（deferred-work L18，建议 5.4/5.5 评估） | **Task 0 评估登记**：工具熔断属 tool_execution 装饰链域，与 EIP 隔离等级无协议耦合——挂点不成立，维持 deferred（独立小 Story 或 Epic 11.3 评估） |
| 5-3 风险 #4 skill_loader/tool_execution_service SCOPED 归属 | **随 D7 评估一并关闭**（DC-7 存量维持——skill_loader 有 LRU 缓存状态，翻 SINGLETON 有缓存共享语义变化风险，维持注记；无实害） |
| 5-3 其余移交（思维链持久化 6-4/AgentDecided 订阅 5.7/SAP 消费 5.11/checkpointer 5-10/谓词键 7-2/380 穿透） | **不涉及**（与本 Story 无交集，维持各自触发） |

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── entities/
│   │   └── isolation_state.py           # 新建：IsolationState 聚合（initialize/switch_to）
│   ├── value_objects/
│   │   ├── isolation_policy.py          # 新建：IsolationPolicy VO + DataIsolationMode + ISOLATION_POLICIES + MVP_ALLOWED_LEVELS
│   │   └── agent_config.py              # 修改：default_isolation_level 枚举化 + D6 守卫回填
│   ├── ports/
│   │   └── isolation_repository.py      # 新建：IsolationRepository Protocol（四方法）
│   ├── events/
│   │   └── isolation_events.py          # 修改：IsolationLevelSwitched kw_only 必填收紧
│   └── exceptions/
│       ├── agent_exceptions.py          # 追加：446/447
│       ├── _code_ranges.py              # 修改：预留段改已分配 + 双映射
│       └── __init__.py                  # 追加导出
├── application/
│   ├── ports/
│   │   └── isolation_management.py      # 新建：IsolationManagementServicePort + IsolationSwitchResult
│   ├── services/
│   │   └── isolation_management_service.py  # 新建：三方法实现（守卫序/no-op/发布容错）
│   └── use_cases/
│       └── agent_instantiation.py       # 修改：第四依赖注入 + initialize 编排骨位
├── infrastructure/
│   ├── storage/redis/
│   │   └── redis_isolation_repository.py  # 新建：Redis 仓储（RedisAgentRepository 模式）
│   └── agent_orch/
│       └── yaml_agent_config_loader.py    # 修改：str→IsolationLevel 转换守卫（440）
├── interfaces/
│   └── api/exception_handlers.py        # 追加：EXCEPTION_HTTP_MAP 446→422/447→404
└── entrypoints/
    └── agent_cli.py                     # 扩展：isolation-status/set-isolation + _parse_isolation_level

src/composition_root.py                  # 追加：两端口注册 + 用例 lambda 注入改造（R1-F38：组合根在 src/ 根，不属 entrypoints——单独列示防误导）

tests/
├── unit/domain/{value_objects/test_isolation_policy.py, entities/test_isolation_state.py,
│   exceptions/test_agent_exceptions.py（追加）, events/test_new_events.py（同步）,
│   events/test_event_serialization.py（同步）, value_objects/test_agent_config.py（追加）}
├── unit/infrastructure/storage/redis/test_redis_isolation_repository.py
├── unit/infrastructure/agent_orch/test_yaml_agent_config_loader.py（追加）
├── unit/application/services/test_isolation_management_service.py
├── unit/application/use_cases/test_agent_instantiation.py（追加+同步）
├── unit/interfaces/cli/test_agent_cli.py（追加）
├── unit/interfaces/api/test_exception_handlers.py（同步）
├── unit/architecture/test_arch_agent_isolation.py
├── contracts/test_port_contract_isolation_{repository,management_service}.py（+ agent_instantiation_use_case 同步）
├── integration/test_integration_agent_isolation.py
├── acceptance/test_acceptance_domain_event_definition.py（同步）
└── acceptance/test_acceptance_agent_isolation.{feature,py}
```

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (glm-5.3) |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-10-21 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（L1591-1630） |
| **架构文档** | `docs/architecture/architecture.md`（§5/§13/L420-424/L797-806） |
| **核心域设计** | `docs/architecture/sisys-core-domain-design.md`（§17.3.3/L1455-1460） |
| **前一个 Story** | `5-3-single-agent-workflow.md`（v1.3.1 收敛态）+ `5-1-ceo-agent-instantiation-mvp.md`（D6/D7 留项） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（含范围边界表——与 5.5/5.6/V1 精确切分）
- [x] 架构约束从 architecture.md/core-domain-design/or.md 提取
- [x] 前一个故事学习经验整合（5-3 教训链 + 5-1 D6/D7 留项 + session_storage/工具熔断 deferred 处置）
- [x] 四视角并行代码调研（Agent 实体与工作流链路 / 端口注册与组合根 / 验收与集成测试模板 / 异常体系与事件通道）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

**dev-story 实施完成清单（2026-10-22）:**

- [x] Task 0: SDD 规范复验 + Gherkin 17 场景 + BDD 骨架（红确认）+ D7 评估落盘 + 留项核销四项（5-1 台账 D6/D7 勾选 + deferred-work 索引行/session_storage 再续期/工具熔断挂点不成立结论）
- [x] Task 1: 五循环 A-E 全红绿变异重构（执行序调换 C→B——实体 import 446 硬依赖，每循环仍完整 TDD）：
  IsolationPolicy VO（97% 覆盖）/ IsolationState 实体（100%——`_mvp_allowed_levels()`
  方法内延迟 import 打破 entities→value_objects→events→entities 包初始化环）/
  异常 446/447 四件套（含 EXCEPTION_HTTP_MAP 422/404 + expected_types 双锁 + 设计文档 §3.3.2）/
  IsolationLevelSwitched kw_only 收紧（回归面四文件全绿）/ AgentConfig D6 全量回填
  （枚举化 + 标量 isinstance 守卫统一 440 + loader str→enum 转换守卫——空白串/回落语义原样保留钉子锁定）
- [x] Task 2: RedisIsolationRepository（15 用例 fakeredis——TTL/键空间/往返/StorageError cause 构造传递）+ 契约 11 维度 + 组合根 SINGLETON 注册
- [x] Task 3: IsolationManagementService（17 用例——守卫序 calls 断言/no-op 零副作用/TTL 真源 config.state_ttl/事件六字段/publish 双分支容错）+ 契约 11 维度 + 组合根四依赖注册
- [x] Task 4: InstantiateAgentUseCase 第四依赖 + fail-fast 编排骨位（save→iso.init→publish）+ 组合根 lambda + 回归面 8 处构造点全量同步（三验收真实组装 + 三集成 AsyncMock + 契约 DummyResolver + 存量 teardown 双键化）+ resolve 冒烟
- [x] Task 5: CLI isolation-status/set-isolation + _parse_isolation_level 两道守卫（62 用例全退出码路径）+ SUPPORTED_ISOLATION_LEVELS 双锁
- [x] Task 6: 集成 5 场景（全链/P95 0.1s 同源常量/成功率 20/20/并发 10 互异/PG outbox 真实落行——_PERF_CACHE 委托 helper + 双键登记清理）
- [x] Task 7: 架构验证器 A-D（15 断言——含 isolation_state 延迟 import 实现锚与 lambda 注入静态锚；pydantic 注入变异实证红）
- [x] Task 8: 收尾场景（18/18 全绿）+ 全量回归 + ruff/mypy 零告警 + 三条红线自查（本次变更零违规——存量 4 处命中均为非本 Story 文件）+ 文档同步（architecture.md §5 MVP 状态注记[DC-1/D-3] + §13 目录树 D-2 落位注记 + isolation_repository 新行）
- [x] R6 改造（用户裁定 2026-10-22）: 验收测试组织结构对齐 PG 模板（多行 @scenario 字面量路径 + 场景绑定与步骤交替排列），保留真实断言/AC 前缀/步骤化门控（弃 FEATURE 常量形态）
- [x] 实施期新发现修复: BDD 参数化步骤须显式 `parsers.parse`（pytest-bdd 默认 re parser——{level} 为字面量，对齐 data_source_expansion 先例）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/5-4-eip-basic-elastic-isolation.md`（本文件）

**dev-story 实施交付（2026-10-22）:**

src 新建 6:
- `src/domain/entities/isolation_state.py` - IsolationState 聚合（initialize/switch_to 双条件守卫 + 延迟 import 环破解）
- `src/domain/value_objects/isolation_policy.py` - IsolationPolicy VO + DataIsolationMode + ISOLATION_POLICIES + MVP_ALLOWED_LEVELS + get_isolation_policy
- `src/domain/ports/isolation_repository.py` - IsolationRepository Protocol（四方法）
- `src/application/ports/isolation_management.py` - IsolationManagementServicePort + IsolationSwitchResult
- `src/application/services/isolation_management_service.py` - 三方法实现（守卫序/no-op/TTL 真源/发布容错）
- `src/infrastructure/storage/redis/redis_isolation_repository.py` - Redis 仓储（namespace=isolation，MULTI/EXEC pipeline）

src 修改 10:
- `src/domain/value_objects/agent_config.py` - D6 回填（default_isolation_level 枚举化 + 标量 isinstance 守卫）
- `src/domain/events/isolation_events.py` - IsolationLevelSwitched kw_only 收紧（DC-6）
- `src/domain/exceptions/agent_exceptions.py` - 446/447 两异常
- `src/domain/exceptions/_code_ranges.py` - 预留段改已分配 + 双映射
- `src/domain/exceptions/__init__.py` - 446/447 导出
- `src/domain/entities/__init__.py` - IsolationState 导出
- `src/domain/value_objects/__init__.py` - isolation_policy 五符号导出
- `src/application/use_cases/agent_instantiation.py` - 第四依赖 + fail-fast 编排骨位
- `src/infrastructure/agent_orch/yaml_agent_config_loader.py` - str→IsolationLevel 转换守卫
- `src/interfaces/api/exception_handlers.py` - 446→422/447→404 精确注册
- `src/entrypoints/agent_cli.py` - isolation-status/set-isolation 两子命令 + _parse_isolation_level + SUPPORTED_ISOLATION_LEVELS
- `src/composition_root.py` - 两端口注册 + 用例 lambda 四依赖

tests 新建 10:
- `tests/unit/domain/value_objects/test_isolation_policy.py`（24 用例）
- `tests/unit/domain/entities/test_isolation_state.py`（24 用例）
- `tests/unit/infrastructure/storage/redis/test_redis_isolation_repository.py`（15 用例）
- `tests/unit/application/services/test_isolation_management_service.py`（17 用例）
- `tests/unit/architecture/test_arch_agent_isolation.py`（15 断言——验证器 A-D）
- `tests/contracts/test_port_contract_isolation_repository.py`（11 维度）
- `tests/contracts/test_port_contract_isolation_management_service.py`（11 维度）
- `tests/integration/test_integration_agent_isolation.py`（5 场景 + sample_isolation_perf/_PERF_CACHE/ISOLATION_P95_LIMIT_SECONDS 委托面）
- `tests/acceptance/test_acceptance_agent_isolation.feature`（18 场景）
- `tests/acceptance/test_acceptance_agent_isolation.py`（18 场景 PG 模板形态）

tests 修改 12:
- `tests/unit/application/use_cases/test_agent_instantiation.py` - 工厂四依赖 + iso.init 编排断言 + 第四依赖测试组
- `tests/unit/domain/events/test_new_events.py` - TestIsolationLevelSwitched kw_only 改写
- `tests/unit/domain/events/test_event_serialization.py` - 三处构造补参
- `tests/unit/domain/exceptions/test_agent_exceptions.py` - 446/447 测试段
- `tests/unit/domain/value_objects/test_agent_config.py` - D6 回填测试组
- `tests/unit/infrastructure/agent_orch/test_yaml_agent_config_loader.py` - 转换守卫测试组
- `tests/unit/interfaces/api/test_exception_handlers.py` - expected_types 双锁同步
- `tests/unit/interfaces/cli/test_agent_cli.py` - 两子命令测试组
- `tests/acceptance/test_acceptance_agent_instantiation.py` - 第四依赖真实组装 + teardown 双键化
- `tests/acceptance/test_acceptance_agent_profile_loading.py` - 同上
- `tests/acceptance/test_acceptance_agent_workflow.py` - 同上
- `tests/contracts/test_port_contract_agent_instantiation_use_case.py` - DummyResolver 四依赖分支
- `tests/integration/test_integration_agent_workflow.py` / `test_integration_agent_profile_loading.py` / `test_integration_agent_instantiation.py` - AsyncMock 第四依赖（集成 Mock 工厂子模式）

文档 3:
- `docs/architecture/architecture.md` - §5 MVP 实现状态注记 + §13 目录树 D-2 落位注记 + isolation_repository 新行
- `docs/architecture/sisys-uni-exception-design.md` - §3.3.2 446/447 两行 + 448-449 预留改 5.5
- `_bmad-output/implementation-artifacts/deferred-work.md` - D6/D7 索引行 + session_storage 再续期 + 工具熔断评估结论
- `_bmad-output/implementation-artifacts/stories/5-1-ceo-agent-instantiation-mvp.md` - D6/D7 台账勾选核销注记

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 5.4 |
| **Story Key** | 5-4-eip-basic-elastic-isolation |
| **File** | `_bmad-output/implementation-artifacts/stories/5-4-eip-basic-elastic-isolation.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 5: Agent 协作系统（价值组：单 Agent 战略规划能力） |
| **优先级** | P0-4 |
| **覆盖 FR** | FR-AC-04（P0） |
| **性能锚** | epics L1612-1614（隔离检查 P95<100ms / 持久化成功率 100% / 并发≥10）/ NFR-PERF-04 MVP 档 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-8）
2. [x] All acceptance criteria specified（AC-1~AC-6）
3. [x] Architecture constraints extracted
4. [x] Previous story learnings integrated（5-3 教训链 + 5-1/5-3 留项四项全处置）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。
> **编号规则（R1 起）**：R<轮>-F<序号>——轮次与修复序号双段；R<轮> 勘误类用 R<轮>-FM<序号>。

#### Round 1（2026-10-21，四视角调研 + 三视角审查：科学性/一致性/可行性，P0×1 + P1×8 + P2×20 + P3×19 去重后修复 48 表行——R2-回归-3 计数对账勘误：原「P1×7 + P2×14 + P3×20 修复 32 项」分布与总数三数字互斥，逐行实点为本口径（F08/F27 为 P1 按 P2 实质、F36 为 P2 升格））

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-F01 | DC-9/Task 0/Task 3 TTL 链闭合缺口：switch 重置 TTL 的真源 AgentConfig.state_ttl（per-role）在钉死的三依赖形态下不可达，`_ttl_for(agent_id)` 骨架不可实现，L729「Task 3 定稿」违反 Task 0 唯一真源纪律 | **P0** | 服务加第四依赖 `agent_config_loader`（同层应用端口，InstantiateAgentUseCase 注入先例同款）；switch 复用 443 守卫已取 agent → `config_loader.load(agent.role).state_ttl`——真源单点零额外读；端口契约/六边形注记/Task 3 红绿/契约测试/骨架/DC-4/DC-9 七处同步回写 |
| R1-F02 | get_isolation_state 的 443 守卫三方矛盾：AC-3 要求随机 UUID→443，但 Task 3 红的 get 无 agent 守卫、DC-11 称「单次读」 | P1 | 定稿 get 含 443 守卫（语义正确——隔离检查入口先验 Agent 合法性，5.5 消费方受益）；Task 3 红阶段补守卫序断言；DC-11/AC-5 计时口径改「服务全链两次读」（预算仍裕量 50 倍） |
| R1-F03 | Task 1 循环 E 将 AgentConfig 守卫定向 242：与文件先例（全部 440）及钉死测试（空白 name→440）冲突，照文执行断言不可满足；242/440 分界原则缺失 | P1 | AgentConfig 全部新守卫统一 440（`_fail` 家族）；「空白串未归一」核实为「拦截已存在」钉子测试锁定即核销；异常契约节补分界原则（配置资产 VO→440 / 非配置实体不变量→242） |
| R1-F04 | loader 同步未声明「空串/缺失回落 L4」既有语义保留——dev 照文会把回落改 440 静默破坏 1.x 定稿语义；loader 用例后置到重构行违禁先码后测 | P1 | 绿阶段明确「仅拦非法枚举值字符串（"L9"）→440；非字符串沿用既有守卫；空串/缺失回落语义原样保留」+「loader 不做 MVP 白名单（"L1" 放行→实体 446——AC-2 路径）」；loader 用例并入红阶段同批先行；reason 改中文自然语言风格弃 snake_case |
| R1-F05 | Task 4 回归面清单漏 4 处构造点（验收 profile_loading:228/workflow:564 + 集成 profile_loading:64/instantiation:68），且「5-3 集成场景① resolve 链自动携带」表述错误（实为手动组装 helper）——第四依赖必填则 5 处必红 | P1 | 回归面清单全量重写：8 处构造点显式列出（7 手动构造 + 组合根——R2-回归-5 计数勘误：原写 9 处，契约测试反射构造不入 grep 面），5-3 集成 helper 表述改正（手动组装非 resolve） |
| R1-F06 | CLI 验收三连坑：instantiate 经进程内 main() 必 ConflictError（直调 bootstrap() 与 conftest 二重注册）；新子命令形态未指明（照抄 instantiate 直调 bootstrap 会炸）；多次 main() 间只 clear_singleton 不清 SCOPED agent_repository（跨循环死实例） | P1 | AC-6.3 改双清（clear_singleton+clear_scoped）+「instantiate 不经 main()（手动组装产出 agent_id——5-3 先例）」+「每次 main() 前重执行双清」；Task 5 绿阶段明确照抄 load-profile/run-task 的 `_ensure_bootstrapped()` 幂等形态 |
| R1-F07 | `_parse_isolation_level` 拟稿守卫顺序与 `_parse_role` 先例相反（先例 except 转换在前、SUPPORTED 预检在后）——拟稿顺序下 except 成死代码，预设变异「删 except→红」不可红 | P1 | 骨架对齐先例顺序（第一道 try/except ValueError→446 from None 拦非法串；第二道 MVP 预检拦 L1）；变异行改双变异（删第一道→"L9" 红；删第二道→L1 红） |
| R1-F08 | Subtask 0.3「HTTP 映射 400/404」与四处 446→422 权威口径矛盾 | P1（按 P2 实质） | 改「422/404」+ 勘误注记 |
| R1-F09 | 447 触发场景缺第三成因（实例化 fail-fast 后键残留）；DC-3 残留态组合语义（443 过→447）未推演 | P2 | 447 契约补三成因；DC-3 补残留态推演 + 自愈路径 |
| R1-F10 | DC-9 论证前提不成立：「活跃 Agent 续期」无事实支撑（Agent 键全仓唯一 save 点=实例化）；切换重置实际制造「隔离键晚于 Agent 键」孤儿方向（良性但未登记） | P2 | DC-9 论证重写为诚实版本；备选 b 弃用理由改签名分叉口径 |
| R1-F11 | exception_handlers.py 行号引用偏差：441→422 实为 L269、443→404 实为 L271（原引 L268/L270） | P2 | 两处行号勘误（DC-8 依据列 + 446 异常契约行） |
| R1-F12 | agent_events.py 纪律注释实为 L87-88（原引 L77-79 是 docstring 区）；事件收紧未点名保留 `__post_init__` 的 aggregate_id←agent_id 派生（AC-4 断言依赖） | P2 | 行号勘误；DC-6 依据列与 Task 0 事件契约补「保留 __post_init__ 派生」 |
| R1-F13 | epics 集成覆盖率 ≥75% 实为 L1618（原引 L1617 是应用层覆盖率行） | P2 | 行号勘误 |
| R1-F14 | `_RecordingEventPublisher`「InMemoryEventBus 真实类子类」三处失实（全仓 4 处均为手写 duck-typing 类；子类先例实为 `_TracingEventBus`） | P2 | 三处表述修正（L48/L80/L339——R2-回归-9 台账自报行号勘误）——手写类 + `_TracingEventBus` 子类先例双注 |
| R1-F15 | CLI stderr 断言正则 `\[EXCEPTION_4[0-9][0-9]\]` 不匹配 201（ValidationError 族是隔离 CLI 合法退出码路径之一） | P2 | 正则改 `\[EXCEPTION_(?:201\|4[0-9]{2})\]`（AC-6.2 + Task 5 红两处） |
| R1-F16 | 集成 pytestmark 文件级 benchmark 与验收「场景级不打文件级」表述歧义（两层先例各自成立但未注记分界） | P2 | AC-5 注记两层各自对齐本层先例（验收场景级 5-2 R1-F8——R2-回归-6 归属勘误 / 集成文件级 profile_loading） |
| R1-F17 | 测试分类表缺两行（yaml loader 追加 + acceptance domain_event_definition 同步）——六面交叉破口 | P2 | 补两行 |
| R1-F18 | AC-3「返回…及三重隔离策略」与端口签名 `-> IsolationState` 不一致（策略联查实为消费方派生） | P2 | AC-3 Then 措辞校准 |
| R1-F19 | Task 7.4 验证器 C 白名单缺 `src.application.ports`——服务实现 application 端口、用例注入它均必然 import，按原白名单合法代码被判红 | P2 | 白名单补 application.ports + 扫描对象含 services 与 use_cases |
| R1-F20 | DC-7「新增面从源头避免 captive」不完整：新 SINGLETON 服务捕获存量 SCOPED agent_repository 是新建立捕获关系，未登记 | P2 | DC-7 显式登记新捕获关系 + 无实害论证 |
| R1-F21 | Task 1 循环 B「等级 L1 或非枚举实例 → 446/242」斜杠歧义（未指明哪条路径哪个码） | P2 | 改「经工厂/方法入参非枚举 → 446（守卫先行）；绕过工厂直构造 → 242」 |
| R1-F22 | DC-3「Redis 无跨键事务」措辞不准（MULTI/Lua 有跨键原子性，缺的是回滚） | P2 | 改「无跨键回滚」 |
| R1-F23 | AC-5 三指标验收与集成双份 20 采样双跑（违 5-3「委托集成计时 helper + 采样缓存」先例纪律） | P2 | AC-5 验证标准补「验收委托集成模块计时 helper + 同名 xdist_group 同 worker 缓存命中」 |
| R1-F24 | 「关键路径 100% 分支覆盖」不可度量（pyproject coverage branch 未启用） | P2 | 改可执行口径：各分支独立命名测试用例 + 语句覆盖由分层门禁背书 |
| R1-F25 | 验收 context fixture 骨架缺 `_restorers` 覆写还原挂点（AC-6 CLI 场景双清/覆写后无还原位，泄漏污染后续场景） | P2 | 骨架补 `"_restorers": []` + teardown 先还原再删键 |
| R1-F26 | File List 计数错账：「新建 8 + 修改 8」实为新建 6 + 修改 10；「tests 新建 9」实为 10 | P2 | 计数勘误 + 分项列出 |
| R1-F27 | D6/D7 核销落点错位：写「deferred-work 登记核销」，实际登记在 5-1 story 留项台账 L1143/L1144（deferred-work.md 无此二条目）——核销链断裂 | P1（按 P2 实质） | 五处（Task 0 完成标志/Subtask 0.8/Task 8.3/处置表两行）统一改「5-1 台账勾选注记 + deferred-work.md 补索引行」 |
| R1-F28 | CLI 常量名三种写法混用（SUPPORTED_LEVELS/SUPPORTED_ISOLATION_LEVELS） | P3 | 统一 SUPPORTED_ISOLATION_LEVELS |
| R1-F29 | 验证器 D 一行式 `.lifetime` 链式取属性会被 mypy（覆盖 tests/）打 None 访问红（registry.get 返回 Optional） | P3 | 两行式收窄（spec is not None 断言先行） |
| R1-F30 | 风险 #6 TTL 漂移只登记单向（隔离键先过期）；no-op 语义洞经推演证伪留痕 | P3 | 双向登记（补孤儿键良性方向）+ 证伪结论入注 |
| R1-F31 | Task 6 场景⑤未注记「RabbitMQ 缺席不影响 publish→outbox 落行」（publish 只写 PG outbox，投递归 poller 异步侧） | P3 | docstring 注记补 |
| R1-F32 | initialize 无 443 前置守卫、前置条件未注明（公共端口契约可为幻影 agent 建态） | P3 | 端口行补前置条件 docstring 要求 |
| R1-F33 | 重复实例化静默重置隔离回 L4 未声明（5.6 审计消费方可能误报 bug） | P3 | DC-3 + initialize 端口行补「安全方向设计意图」注记 |
| R1-F34 | SUPPORTED_ISOLATION_LEVELS 派生方式未注明（frozenset 迭代派生会致帮助文本顺序漂移） | P3 | 显式元组字面量 + 与 MVP_ALLOWED_LEVELS 集合相等断言双锁 |
| R1-F35 | AC-2「初始化等级非法→446」在验收禁 mock 约束下驱动机制未指明 | P3 | 补「临时 yaml(L1) + 真实 config_loader 驱动」 |
| R1-F36 | 事件骨架省略号掩盖 approval_chain 端口参数→事件字段转发；publish 容错缺 is_success=False 分支（真实总线失败不抛异常，单 except 在真实链路不可达） | P2（升格） | 骨架补显式转发 + 双分支容错（对齐 InstantiateAgentUseCase 先例） |
| R1-F37 | or.md 范围权威编号双重错位（L18 属 §一.1.[5] 非 §四.1.[5]；L280-289 属 §四 非 §八.7；§八.7 实为 L616-620） | P2 | 范围权威行编号+行号全面校准 + IsolationLevelSwitchRequired 防混淆注记 |
| R1-F38 | 项目结构树把 composition_root.py 画在 entrypoints/ 分支下（实际在 src/ 根） | P3 | 移出分支单独列示 |
| R1-F39 | IsolationLevelSwitched 订阅接线归属两处分叉（L282 指 5.7 / L641 指 5.6） | P3 | 口径统一：5.6 首个业务消费方，接线归消费方 Story |
| R1-F40 | 「R3-F23」「R2-2-C2」编号在出处 story 不可 grep（可追溯性断裂） | P3 | 改实名引用（5-1 文档审查 Round 3 发现 #23 / 4-1b R2-2-C2） |
| R1-F41 | no-op 验收「TTL 不变可断言」判别力弱（Redis TTL 秒级粒度，<2s 不可区分） | P3 | 判别锚改单测 calls 计数 + TTL 断言需 elapsed≥2s 注记 |
| R1-F42 | 并发 10 场景主断言未用互异目标等级（串扰仅变异步可抓） | P3 | 主场景奇偶 agent 切 L3/L2 互异 |
| R1-F43 | 测试分类表验收行漏 AC-6 转绿归属；test_exception_handlers 路径未补全且「追加/同步」措辞不一 | P3 | 补归属 + 全路径统一「追加」 |
| R1-F44 | DC-2/DC-8/DC-9/DC-11 四项决策无正文回指（决策表孤岛） | P3 | AC-1/AC-2/AC-5/异常契约节补四处回指（DC-11 已随 F02 落） |
| R1-F45 | 446 构造器「对齐 441 形态」却给 level 默认值（441 实际首参必填）；supported 参数实际接受 tuple 或 list | P3 | 446 签名校准为 level 必填 + tuple/list 联合 |
| R1-F46 | Subtask 0.8「三项交叉登记」实列四项 | P3 | 计数勘误 |
| R1-F47 | 「组合合根」错别字 | P3 | 勘误 |
| R1-F48 | 「文档审查 4 轮 61 表行」压缩失实（5-3 实为 4 轮+终审） | P3 | 口径校准 |

> R1 证伪留痕（审查员推演不成立的疑点，与问题同价值）：no-op/查询不刷新 TTL 不会致隔离键先过期（两键同刻同值写入、Agent 键无续期方）；`quantiles(n=20)[18]` 数学正确即 P95；AC-1 策略表与 architecture.md §5.1 六格逐行一致；kw_only 对 frozen dataclass 收紧正确；R1/R2/R3/R4 分层矩阵整体正确；aggregate_id 无需显式传（__post_init__ 自动派生——但派生本身需保留，见 R1-F12）。

#### Round 2（2026-10-21，回归核查 + 组合交互面双审查：P2×5 + P3×12 修复 17 表行）

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R2-F01 | DC-12 决策行残留 R1 前旧口径（「空白归一 + strip」回填 + snake_case reason）——与 R1-F03/F04 定稿三处互相矛盾，dev 读决策表会与循环 E 断言冲突 | P2 | DC-12 改「回填两项 + 钉子两项」口径对齐 R1-F03/F04 |
| R2-F02 | L527「AsyncMock（既有验收 mock 形态——5-1 验收先例 L214 同款）」引证失实（L214 实为全真实组装，验收目录用例组装 AsyncMock 零先例）；第四依赖「真实/mock」分派在 8 处构造点未定稿 | P2 | 分派定稿：既有六文件回归同步用 AsyncMock（集成 Mock 工厂子模式合规——本 Story 新增回归形态决策，如实注明无验收组装先例）；本 Story 新验收场景与集成场景①用真实服务四依赖手动组装（隔离键真实性硬依赖——四依赖逐一列出，config_loader 经 resolve 取） |
| R2-F03 | R1 计数对账三数字互斥（标题「32 项」/日志「48 表行」/分布合计 42）——逐行实点为 P0×1 + P1×8 + P2×20 + P3×19 = 48 | P2 | R1 标题计数勘误 + 勘误注记 |
| R2-F04 | AC-2「非 MVP 等级→446」与 R1-F03/F04 输入通道分层冲突——照字面在验收写 "L9" yaml 断 446 必红（"L9" 在 loader 层 440） | P2 | AC-2 表述收口（L1 越白名单→446 进验收；"L9"→440 归循环 E 单测面） |
| R2-F05 | R1-F36 双分支容错只落骨架与绿阶段，Task 3 红阶段缺 is_success=False 独立用例（先例两分支各有独立命名用例——红先性破口） | P2 | Task 3 红阶段补独立用例断言 |
| R2-F06 | R1-F15 在 Task 5 红行写入裸管道正则（表格内未转义——GFM 按裸 \| 切单元格，表格断 5 列错位） | P3 | `(?:201\|4[0-9]{2})` 转义修正 |
| R2-F07 | 「全仓 9 处构造点」计数错账（R1-F05 自引入；实为 8 处——契约测试经 spec.impl 反射构造不入 grep 面）且传播进变更日志 | P3 | 两处 9→8 勘误 |
| R2-F08 | 「验收侧不打文件级」先例归属张冠李戴（属 5-2 R1-F8；5-3 自己的 R1-F8 是 LLM 冒烟恒真项，5-3 L281 是转引） | P3 | 两处归属勘误（AC-5 注记 + R1-F16 台账行） |
| R2-F09 | 「5-3 DC-12 四件套同款」归称失实——双清是本 Story 扩展（5-3 原四件套仅 clear_singleton 单清） | P3 | 改「扩展 5-3 DC-12 四件套：单清同款 + 新增 clear_scoped」（**R3-F09 再勘误**：同文件 L791-793 第三次 main() 前已双清——「本 Story 新增」失实，归称终校准为「对齐 5-3 既有双清实码」；**R4-N1 行号终校**：原引 L549 是 import 行——四件套 given 步骤 docstring 在 L533-543（⓪ 单清句 L535）、单清实码在 L560） |
| R2-F10 | AC-5 委托集成计时 helper 口径单侧悬挂（委托方有要求、Task 6 被委托方无交付物——5-3 先例写在集成 Task 红阶段内） | P3 | Task 6 场景②补交付形态（模块级 _PERF_CACHE helper） |
| R2-F11 | get 守卫序 calls 断言以引用式传递（「同 switch 前置」），变异「守卫顺序交换」在 get 方法不可红 | P3 | calls 断言显式化（443 时 isolation_repository 未被调） |
| R2-F12 | 「照抄 _parse_role」未警示 .lower() 归一不可照抄（AgentRole 全小写 vs IsolationLevel 全大写——照抄则全部合法输入误拒）；--level 大小写敏感性未声明 | P3 | 绿阶段补禁抄警示 + 大小写敏感契约 |
| R2-F13 | DC-12 是 12 项决策中唯一无正文锚的（且与 L182「5-3 DC-12」编号碰撞致 grep 假阳性） | P3 | 循环 E 标题补「DC-12 回填边界定稿」 |
| R2-F14 | 测试分类表「18 场景（Task 0 编写」与三处「Task 0 编写 17、Task 8 追加」口径冲突 | P3 | 改「17 场景 Task 0 编写 + 收尾 Task 8 追加（全量 18）」 |
| R2-F15 | 委托计时 helper 采样键清理未注记双键扩展（照抄 5-3 单键形态漏删隔离键——helper 内轮次不经场景 teardown） | P3 | 场景②补 sample_keys 双键登记说明 |
| R2-F16 | R1-F14 台账自报行号漂移（第三处实落 L339 非 L336）；L48 InMemoryEventBus 行号 off-by-one（类定义 L18） | P3 | 两处行号勘误 |
| R2-F17 | AC-5「隔离态读两次读」措辞粘连病句 | P3 | 改「443 存在性守卫 + 隔离态读——共两次真实 Redis 读」 |

> R2 证伪留痕（推演不成立，与发现同价值）：①「两次读」口径在 get 路径准确（config_loader 仅 switch 路径，yaml 文件读不在 get 计时面——YamlAgentConfigLoader 无缓存每次真实读文件）；②多命令连接生命周期闭合（双清后 re-resolve 全链新实例新循环，_close_connection_pools 不清 registry 缓存、双清补位——R1-F06×R1-F36×R1-F31 正交互补成立；set-isolation 在 PG/RabbitMQ 缺席时由双分支容错兜底 exit 0）；③L1 双断言守卫序正确（两道均传 raw 原文，446 context 语义无影响）；④委托计时缓存共享疑点不成立（_PERF_CACHE 单槽固定 key 无 agent_id 维度，验收/集成 agent_id 不同不妨碍共享）；⑤DC-1~DC-11 正文锚齐全（唯 DC-12 缺——R2-F13）；⑥四依赖 11 处表述全一致。

#### Round 3（2026-10-21，单深度推演：17+1 场景三轴 + 5 时间线 + 数学完备性（含 Python 3.11.15 实测），P1×1 + P2×3 + P3×6 修复 10 项 + 误报改判 1 项——R4-N2 计数勘误：原写「P3×7」与表内实点 P3×6 及「修复 10 项」自相矛盾）

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R3-F01 | **str,Enum 混入语义下单 `not in MVP_ALLOWED_LEVELS` 守卫拦不住合法值域裸 str**（实测：`hash("L3")==hash(L3_SOFT)`、`"L3" in frozenset == True`、`isinstance("L3", IsolationLevel) == False`）——裸 "L3" 穿透守卫落 __post_init__ 242（循环 B「非枚举→446」断言不可满足）；switch_to 路径更甚：dataclass 赋值不触发 __post_init__，裸 str 静默类型污染持久化 | **P1** | initialize/switch_to 守卫双条件化 `not isinstance(level, IsolationLevel) or level not in MVP_ALLOWED_LEVELS`（数据模型两行 + 骨架两处）；循环 B 红补「非枚举双入参参数化（裸 "L3" 合法值域 + "L9" 值域外）→ 均 446」+ switch_to 类型污染防线断言；initialize 单 now 双用（initialized_at==updated_at） |
| R3-F02 | AC-2.3 临时 yaml 驱动两个前置可达缺口：resolve 全局 loader 恒读仓库配置（L4）446 不可达；最小 yaml 过不了 loader 逐段强校验（440 先炸） | P2 | 补「ceo_agent.yaml 全文基线复制到 tmp 仅改 isolation 值 + `YamlAgentConfigLoader(config_dir=tmp_path)` 构造注入」 |
| R3-F03 | 446 fail-fast 用例路径残留 agent 键不可回收（agent_id 在 execute 内部生成、异常 context 不携带、禁 scan_iter）——违验收自包含纪律 | P2 | 446 断言改服务级真实链直调（场景预生成 UUID 零残留）；用例编排骨位归 Task 4 单测 |
| R3-F04 | R2-F02 分派的「既有三验收文件用 AsyncMock」违反 CLAUDE.md「验收禁 mock」硬约束（未做合规论证） | P2 | 改判：三验收文件真实 IsolationManagementService 手动组装（5-1 L214 全真实先例同款，Given 前置非断言面）；三集成文件维持 AsyncMock（集成 Mock 工厂子模式合规） |
| R3-F05 | 「AC-5×3 委托计时 helper」字面不可执行（helper 无并发数据；5.2 自跑则双跑复发） | P3 | 委托分界细化：5.1/5.2 委托（成功率分子分母同批派生）；5.3 并发自跑 |
| R3-F06 | 同 Agent 并发切换无锁竞态未声明（后写覆盖 + 事件序与终态可能不一致） | P3 | 风险清单补第 7 条（设计接受 + 5.5/V1 立项评估） |
| R3-F07 | 447 成因①「TTL 漂移」经写序推演不可构造（隔离键恒晚亡）；R1-F30 微秒差方向写反 | P3 | 成因①改「存量 Agent 无隔离键」；风险 #6 方向修正 |
| R3-F08 | 「重实例化同 id 可自愈」经用例/CLI 通道不可达（execute 恒生成新 uuid4） | P3 | 措辞改「服务级同 id 重 initialize 可自愈；用例/CLI 通道靠 TTL 回收」（异常契约 + DC-3 两处） |
| R3-F09 | R2-F09 修复自身归称失实：5-3 验收 L791-793 第三次 main() 前已是双清实码（四件套 given 步骤 docstring 仅单清是描述滞后非行为缺失——docstring 实际位于 L533-543、单清实码 L560，R4-N1 终校） | P3 | 归称终校准「对齐 5-3 既有双清实码」+ R2-F09 行补勘误注记 |
| R3-F11 | isolation-status 时间输出格式未钉死——stdout 断言写法悬空（isoformat 微秒/时区脆弱） | P3 | 钉 isoformat() 全格式 + 正则/字段值锚定（禁整行精确匹配） |
| ~~R3-F10~~ | ~~441→422 行号「勘误之勘误」（称 L268/L270 才对）~~ | 误报改判 | **主会话第三次实测定谳：L269/L271 正确**（grep 双重确认；R3 推演员 sed 窗口行看偏——窗口首行 266 使第 4 行显示为 441 行但实为 L269）。R1-F11 勘误维持，不落码——留痕防 R4/R5 再翻 |

> R3 证伪留痕（推演不成立的疑点）：①resolve 即构造即连接不成立（RedisAdapter/RedisManager/RabbitMQEventBus/DualChannelEventBus 构造全零 IO——L25-31/L43-70 实证，5-3 AC-6.1 resolve 全链验收先例已跑通）；②CLI 双清与 instantiate 不经 main() 论证成立（L401 直调 bootstrap/_ensure_bootstrapped L65-76 实证）；③回归面 8 处行号全部命中；④事件收紧回归面偏保守无害（test_event_serialization L67-75 与 domain_event_definition L273-278 构造已传全四参——多跑不漏跑）；⑤`quantiles(n=20)[18]` = P95 数学正确；⑥CLI --level L1 第二道预检拦截与服务层枚举直调双路径分层清晰；⑦范围权威与先例行号抽查全部命中（or.md L18/L48/L616-620/L280-289、epics L1612/L1614/L1618、ceo_agent.yaml L24 等）；⑧场景三轴推演 17+1 全表：除 F02/F03/F05 对应场景外全 PASS——AC-3.2 随机 UUID 断言对守卫序有判别力、AC-4.3 判别锚单测 calls 计数、AC-6.3 红阶段文件缺失合法红；⑨B.1-B.5 时间线逐字段推演：B.2 set-isolation 删键态 447（守卫序定义一致）、B.3 AgentInstantiated 未发布（Task 4 顺序断言定义 ✓）。

#### Round 4（2026-10-21，纯验证轮：96 锚点向 HEAD 实地核验 + 交叉计数终验 + 红线终扫——**零规范级修复，5 项台账级 P3/P4 留项随 R5 收敛提交清偿**）

| 验证项 | 结果 |
|--------|------|
| file:line 锚点核验（96 单元：领域 15/interfaces 2/application+infra+组合根+CLI 27/tests 21/设计文档 25） | **95 精确（98.9%）**；1 偏移封闭在台账自报行号内（R4-N1）；规范正文锚全部命中 |
| 三次定谳项（exception_handlers L269/L271） | 实地复核正确——R3-F10 误报改判维持 |
| R3 修复结构落地 | 双条件守卫无裸残留（5 出现位：3 双条件 + CLI 1 注记 + 台账 1）/AsyncMock 分派定稿（验收真实组装 + 集成 Mock 工厂）/AC-2.3 驱动链四要素完整 |
| 交叉计数 | 17 场景三处一致 / 8 构造点与实地 grep 一致 / 台账 48+17+10+1 行 / 版本链四行 / DC-1~12 正文锚齐全（含 DC-12 循环 E 标题回指） |
| 红线终扫 | 无 AI 署名（Model 字段为模板惯例）/ 抑制注释零命中 / 审查标记未泄漏进规范语义（四处抽验剥离标记后语义自洽） |

**R4 留项台账（已随 R5 收敛提交清偿）**：R4-N1（R2-F09/R3-F09 台账自报 L549 错位——docstring 实际 L533-543/L535、单清实码 L560）/ R4-N2（R3 标题「P3×7」实为 P3×6 计数不符——两处勘误）/ R4-N3（inmemory_event_bus L18→L19）/ R4-N4（契约样板 117→116 行）/ R4-N5（profile_loading L46-51→L45-50）——五项均为台账级，不动规范正文语义。

#### Round 5（2026-10-21，独立终审五节取证——不轻信 Story 自报，全部实地核验）

| 节 | 取证项 | 结果 |
|----|--------|------|
| 1 | 周期闭合 | ✓ 三提交序列精确匹配（R1=dba26b0a/R2=2fe4005a/R3=7339094a）+ R4 零提交（留项随 R5 清偿）；文件清单逐一核对无游离提交、无第三方文件混入 |
| 2 | 关键修复双向取证（6 项抽验） | ✓ 全部双向一致：agent_config_loader 端口 L23-30/组合根 L2682；test_agent_config L146-148 钉子+_fail 440；agent_cli L401 直调 bootstrap+5-3 L792-793 双清实码；守卫双条件 5 出现位；YamlAgentConfigLoader(config_dir) L40/agent_id L116 内部生成；空串回落 L128/非字符串 440 L126-127 |
| 3 | 文档-仓库事实（5 高风险锚） | ✓ L269/L271 三次定谳最终复核正确 / agent_events L87-88 / epics L1618 / or.md L616-620 / 5-1 L1143-L1144 |
| 4 | 红线终扫 + 台账 | ✓ AI 署名零命中 / 抑制注释零命中 / 台账 48+17+11 行实测一致 / R4 五项清偿新行号实地复核全中（L533-543/L535/L560、L19、116 行、L45-50） |
| 5 | 收敛判定 | **收敛**：零 P0/P1/P2 残留；R3-F10 误报留痕在位；移交留项四项处置记录完整；文档声明与仓库现实零冲突 |

> **文档审查周期收敛声明（R5 终审）**：Story 5.4 经 R1-R3 三轮审查（48+17+10+1 表行修复 + 1 误报改判）、R4 纯验证（96 锚点 98.9% 精确、5 项台账级留项）、R5 独立终审五节取证（周期闭合/六项关键修复双向比对/五高风险锚实地复核/红线终扫/留项台账完整性）——全部证据与仓库现实一致，零 P0/P1/P2 残留，R4 五项留项清偿行号经实地复核无误。**文档审查周期正式收敛，Story 5.4 自本提交起进入 dev-story 实施。**

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 2026-10-22 起（Round 1）
**审查模式:** 四视角并行调研（领域模型/服务编排/Redis 仓储/CLI 与测试实跑）+ 双评审员（技术正确性/纪律合规）+ 主会话事实裁决

> **编号规则**：R<轮>-F<序号> 修复落码 / R<轮>-DF<序号> deferred 登记 / 维持项入证伪留痕段。

#### Round 1（2026-10-22，四视角调研 + 双评审：P1×2 + P2×5 + P3×7 落码 14 项 + 登记 2 项 + 维持 8 项）

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| R1-F01 | P1 | MULTI/EXEC pipeline 原子性契约零判别力锁定——仓储 docstring 明言原子提交防孤儿键，但单测无 pipeline 交互断言，save 降级为两条独立 await 命令后全部测试仍绿（5-1 先例 test_save_uses_single_pipeline_transaction 漏抄） | 移植先例 _PipelineStub 形态至 test_redis_isolation_repository.py（pipeline 恰一次 + transaction=True + ops 恰 [hset,expire] + 同键 + execute awaited） |
| R1-F02 | P1 | **SISYS_USE_TEST_PORTS 端口隔离被 litellm load_dotenv 静默击穿**：conftest 模块级 `_disable_litellm_logging_worker()` → import litellm → load_dotenv 将 .env 的 dev 端口注入 os.environ → `_override_config_from_env` 端口无守卫 → 6380/5433 翻回 6379/5432，验收/集成实际读写 dev 实例（实测：6380 未运行时 23 测全过；dev PG outbox 出现测试写入行） | tests/environments.py 双向修复：①`_override_config_from_env` 门控 `config.env==LOCAL and 开关` 下端口类覆盖跳过（含 MinIO host 分支内联重建 endpoint 的绕过洞）；②`_sync_config_to_environ` 端口类从 setdefault 改强制覆写（防生产 Config.from_env 与测试端口 split-brain——评审员甲抓的 P0 级遗漏联动面）；③三层 docstring 开例外注记；④tests/unit/shared/test_test_env_port_isolation.py 双向锁定 4 用例（含 dev 模式显式端口语义保留——防过度修复）。修复位选 environments.py 端口权威守卫而非 conftest（对任意第三方 import 副作用鲁棒——评审员乙合规裁定附四条件） |
| R1-F03 | P2 | 脏数据 fail-loud 契约零测试锁定——实现侧 get_by_agent_id except Exception 已包装脏数据为 103（视角 A 静态误报「裸转换逃逸」，主会话实测定谳），但未来 except 收窄为 redis.RedisError 时脏数据将裸逃逸且测试全绿 | 3 用例锁定（非法 JSON/非法枚举值 "L9"/缺字段 → StorageError(103) + cause is not None）；实现零改动 |
| R1-F04 | P2 | TTL 边界接受值与 bool/float 形态测试缺失——实现 L75 的 isinstance(ttl, bool) 守卫零测试（死代码态）；闭区间端点 60/2592000 无接受用例 | parametrize 补 [60,86400,2592000] 接受 + [True,3600.5] 拒绝 440（对齐 5-1 先例） |
| R1-F05 | P2 | 446 docstring「supported_levels 从 MVP_ALLOWED_LEVELS 派生，勿硬编码」承诺与现实相悖——_SUPPORTED_LEVEL_VALUES 硬编码三枚举 .value，V2 开放 L1 需改 3 处（承诺为虚） | 改函数 `_supported_level_values()` 真派生（定义序过滤迭代——L4,L3,L2 序稳定；延迟 import 同 _mvp_allowed_levels 环约束形态）；CLI 侧 SUPPORTED_ISOLATION_LEVELS 维持字面量+双锁（R1-F34 决策在案——评审员乙裁定 A 方案正确：441 家族先例真派生 + 承诺是 5-4 自己立的） |
| R1-F06 | P2 | 组合根 stale 注释「工厂 resolve 三依赖」vs lambda 实际四依赖（8af9a17a 只改 lambda 未改注释） | 注释改四依赖（+isolation_management_service——Story 5.4） |
| R1-F07 | P2 | 集成场景⑤「PG 缺席动态 skip」仅拦 import 失败不拦连接失败——PG 端口不可达时测试 FAILED 而非 SKIP（违 DoD「PG 缺席 4 绿+1 skip」；对照 Redis 侧 ping→skip 门控） | 查询前连接预检（SELECT 1 失败 → dispose 引擎 + pytest.skip） |
| R1-F08 | P3 | test_event_serialization.py L70-71 残留裸 str 构造（previous_level="L4"/target_level="L2"——8af9a17a 漏改的第三处构造点，与本 Story「裸 str 是缺陷面」纪律叙事自相矛盾） | 两行改传 IsolationLevel 枚举 |
| R1-F09 | P3 | switch_timestamp 与 state.updated_at 两次独立取钟——一次切换三个时钟读数（事件基类 timestamp/state.updated_at/switch_timestamp），审计回溯（5.6 WORM 归档）时状态时刻与事件时刻可能不一致，背离本 Story initialize「单 now 双用」纪律 | 事件构造改 switch_timestamp=state.updated_at（事件时刻=状态变更时刻）+ import 清理 + 单测补 `is` 恒等断言（单钟纪律锚） |
| R1-F10 | P3 | 包初始化环 docstring 链路方向叙述失实（原称 entities-first 断环）——主会话独立实验定谳（副本注入模块级 import 两方向实测）：唯一断环方向是 value_objects-first，链路经 events/__init__ L7 **archive_events**（调研视角 A 报的 tool_chain_events 亦误——events/__init__ 不导入它；评审员甲真实文件副本实证 + 主会话复现三方一致；评审员乙自建同构模拟「两方向均不断环」为方法学误报） | docstring 改实证链（value_objects-first，经 events/__init__ L7 archive_events 触发 entities/__init__） |
| R1-F11 | P3 | 端口/服务 switch 方法 Raises 契约缺 242——空 trigger_reason 经实体 switch_to 抛 EntityValidationError 242 透传（CLI `--reason "  "` 真实可达），异常契约文档面不完整 | 两处 Raises 补 EntityValidationError 行 |
| R1-F12 | P3 | 服务单测两缺口：①config_loader.load 抛 440 分支（端口 Raises 明文列出）零用例；②test_initialize_upsert_semantics 名为 upsert 却无 save 计数断言（判别力弱于命名承诺） | 补 test_switch_config_load_failure_propagates_440（透传 + save/publish 零调用——load 先于 save 编排骨位锚）；upsert 用例补 save.await_count == 2 |
| R1-F13 | P3 | 集成场景① execute 段与场景④ gather 在 try 之外——中途异常时 finally 不执行/已完成写键不在清理面（违自包含纪律异常路径；朴素移入有 finally UnboundLocalError 机械坑——评审员甲注记） | 场景①预绑定 agent_id/isolation_key=None + finally 守卫 + 成功路径收窄断言；场景④ key 即时登记模式（_one_agent 内写键即入册——gather 部分失败时已完成 agent 双键仍清理） |
| R1-F14 | P3 | CLI 帮助文本漂移——description「实例化与身份档案加载」+ epilog 仅两命令示例，未含 run-task/isolation 两代子命令（5-3 起陈旧） | description/epilog 更新含五子命令 |

#### Round 2（2026-10-22，回归核查 + 组合交互面双审查：P0×1 + P2×1 + P3×4 落码 6 项 + 3 注记维持——R1 修复的回归核查 13/14 干净、台账一致性全过、组合 1/4/5/6 自洽、6380 MONITOR 实证端口隔离生效、变异 a 判别力实证）

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| R2-F01 | **P0** | R1-F02 锁定用例击穿 CI 门禁——4 用例未处理 `SISYS_TEST_ENV`（CI 下 resolve_env 最高优先级走 CI 分支，TEST_CONFIG 永不被选中，3/4 用例断言 6380 得 6379——组合交互 Agent 以 CI 精确 env 实测复现；ci.yaml push-main 单测门 + cr.yaml 每日回归均中招）| 评审修正两处：①delenv 不够（CI 容器 GITHUB_ACTIONS 注入 + /.dockerenv 双重兜底仍判 CI——评审实证）→ 全部用例 `setenv("SISYS_TEST_ENV", "local")` 显式锚定；②新增 CI 形态反向锁定用例（注入端口 6390 差异化防恒真 + host 断言锁死 CI_CONFIG 选择——门控误扩 CI 时红）。CI 形态复跑 5 passed（P0 闭合实证） |
| R2-F02 | P2 | MinIO environ 腿不完备——生产 `MinIOConfig.from_env` 读 `MINIO_HOST`+`MINIO_API_PORT`（.env:67 有 9000），sync 只强覆写 `MINIO_ENDPOINT`（src 零消费方死键）→ MinIO 生产路径 split-brain 未闭合（双 Agent 一致发现；评审实证 split-brain 形态与修复推演） | `_sync_config_to_environ` 测试端口模式下补 MINIO_HOST/MINIO_API_PORT 强覆写（endpoint rsplit 解析回填 + len 守卫）；锁定测试断言面扩展两键；CI/远程分支不动（动会改 CI 现行为——遗留缺口注记：CI 形态 MINIO_HOST 从不同步，归存储测试基建专项） |
| R2-F03 | P3 | CLI 帮助文本无漂移锁——R1-F14 只改文本未加锁，两代子命令漂移成因原样敞开 | test_agent_cli 补 test_help_text_lists_all_registered_subcommands（五子命令名均现于 format_help()——usage choices 与 epilog 双通道） |
| R2-F04 | P3 | 446 异常 docstring「勿硬编码/仅改一处」写在两路径共享的异常类上未按位点区分（CLI 位点合法违反——R1-F34 在案；「仅改一处」对 CLI 路径不实） | agent_exceptions.py 两处 docstring 补位点区分注记（实体/服务侧真派生；CLI 侧字面量双锁形态） |
| R2-F05 | P3 | `_use_test_ports` 判定式三处复制（get_test_env L376/_override/_sync）——真值集/合取漂移即层间分叉 | 提 `_use_test_ports_active(config)` 单一真源 helper（config=None 时仅判开关——Layer 1 选择位语义）；三调用位替换 |
| R2-OBS | P3 | R1-F05 派生的同值字面量替换零判别力（变异 b 实证 57 测全绿——回归核查 Agent 定性为固有形态非双锁恒真） | test_isolation_state 补 monkeypatch 真源性行为锁（MVP_ALLOWED_LEVELS 扩 L1[枚举成员形态——str,Enum hash 语义硬约束] → 446 context 随动含 "L1"——硬编码形态红） |

> R2 证伪留痕（维持注记）：NEO4J_HTTP_PORT 被 sync 但 .env.example 无此键且生产不读（近死键，维持）；场景⑤「短超时」注释无显式 connect timeout 背书（OS refused 即时，维持）；显式端口+开关 on 被覆写（6399→6380 有意权衡，注释在案）；Layer 2 host 填充在测试端口模式未门控（host 类不在 F02 声明范围，.env 全 localhost 无实害，注记）。
> R2 评审过程记录：单评审快评给两处实质修正（R2-F01 delenv→setenv[CI 容器双重兜底实证]/CI 用例端口 6379→6390 差异化防恒真）+ R2-OBS 枚举成员硬约束——全部吸收后落码。

#### Round 3（2026-10-22，单深度推演：16 格环境矩阵 + CLI 三路径时间线 + 八路径事件矩阵 + 9 格实体异码矩阵 + fakeredis 边界实测——零 P0/P1，P3×3 落码 + P3×1 维持 + 7 疑点证伪留痕）

| # | 级别 | 问题 | 修复 |
|---|------|------|------|
| R3-F01 | P3 | 锁定测试 monkeypatch 恢复键集 ⊋ 缺口——sync 强覆写写集 11 键而注入集仅 8 键：测试后 NEO4J_HTTP/BOLT 等 3 键无人恢复（进程内单向污染——后续 ambient 解析被静默漂到测试端口；NEO4J 两键 sync 写但 Layer 3 不读——翻转后 config/environ 真分裂）；当前爆炸半径 ≈0（该文件是收集序最后文件），触发条件=shared 目录加排序在后文件/显式 argv 顺序 | `_inject_dev_port_pollution` 注入集扩至 sync 写集全量 11 键（monkeypatch teardown 恢复全部被覆写键——恢复面=覆写面闭合） |
| R3-F03 | P3 | trigger_reason 双投影分歧——事件携带原文 reason、state 存 `.strip()` 后文本（带空白包裹的 reason 使审计事件与持久化状态两份记录不一致） | 服务事件构造改传 `state.last_trigger_reason`（strip 后文本——与持久化态单源） |
| R3-F04 | P3 | R1 新增 pipeline 测试 stub 的 lambda 形态产生未 await 协程（`AsyncMock(side_effect=lambda: apply(...))`——iscoroutinefunction(lambda)=False 使返回的裸协程被丢弃：RuntimeWarning "coroutine never awaited"[全 unit 面唯一 warning] + apply 副作用空洞；5-1 先例 partial(async) 形态被正确 await——实测对照定谳） | `_PipelineStub.execute` 改 partial 绑定真 async 方法（对齐 5-1 先例）——复跑 24 passed 零 warning |
| R3-OBS | P3 | instantiate 路径 bootstrap 幂等守卫缺失（五命令唯一不对称——裸 `bootstrap()` vs 其余四命令 `_ensure_bootstrapped()`；进程内二次 instantiate 必 ConflictError，验收被迫手动组装绕过 main()——instantiate 的 CLI 主入口无 main() 级验收覆盖） | **维持注记**：5-1 交付面资产（agent_cli.py instantiate 段），非本 Story 引入；行为修复（改幂等形态）涉 5-1 语义变更，归 5-1 资产维护或 CLI 专项评估 |

> R3 证伪留痕（7 疑点推演+实测不成立）：①xdist import 序不一致——load_dotenv 默认 override=False（litellm/__init__.py:20 实证）+ 双向守卫，两种序均收敛；②CLI 池关闭不完备（含 rabbitmq 腿）——三路径零缺口、RELIABLE 发布无带内 AMQP；③双清与关池序错用已关池——清在 main 前关在 main 内 finally；④TTL 双向漂移——agent 键全仓唯一 save 点=实例化，漂移严格单向良性（风险 #6 结论在实现终态成立）；⑤kw_only+aggregate_id 交互破坏——7 处构造全 UUID、from_dict 类型还原完备；⑥固定模式下 config/environ 分裂格——8 关键格全一致（分裂仅进程内模式翻转，R3-F01）；⑦事件双注册缺失——yaml+DEFAULT_MAPPINGS 双位点齐备。附注：Layer 2 MinIO 填充分支硬编码 :9000 忽略 .env（90-1 遗留，Layer 3 自愈，仅记录）。
> R3 实测：特殊字符/emoji/超长 reason 4 形态往返保真 PASS；9 格异码矩阵与文档契约逐格一致（L1 直构造 SUCCESS 是有意 V2 前向兼容形态）；TTL 单调性/upsert 重置/纯 get 不重置 PASS；验收+集成 22+1skip、unit 9374 passed、ruff/mypy 干净。

#### Round 4（2026-10-22，纯验证轮：锚点存续 + 计数对账 + 门禁实跑 + 结构连续性——**零规范级发现，不造提交**）

| 验证项 | 结果 |
|--------|------|
| 三轮修复锚点存续（helper/门控/派生/单钟/partial/11 键/锚定/CI 用例） | 全部 ✅（R4 Agent 中断前 + 主会话接续完成） |
| 计数对账 | R1-F 表行 62 = 文档审查 48 + 代码审查 14；R2-F 22 = 17+5；R3-F 13 = 10+3；DF 2——全吻合 |
| 门禁实跑 | unit 全量 **9374 passed 零 warning**（R3-F04 消除的最终态）；验收集成 22+1skip；ruff/mypy 干净；红线零新增（3 处 ValueError 均预存非 5-4 面）；CI 形态 5 passed |
| 结构连续性 | 八轮 Round 标题齐全（文档审查 R1-R5 + 代码审查 R1-R3）无 Edit 吞噬 |

#### Round 5（2026-10-22，独立终审五节取证——不轻信 Story 自报，全部实地核验）

| 节 | 取证项 | 结果 |
|----|--------|------|
| 1 | 周期闭合 | ✓ 三提交序列精确（R1=f9da030e/R2=109b0c0c/R3=d5a3d99d）+ R4 零提交；文件面与台账三轮描述交叉核对无游离提交、无第三方文件混入 |
| 2 | 关键修复双向取证（8 项抽验） | ✓ 全部双向一致：R1-F02 门控/R2-F02 MinIO 两键/R2-F01 锚定+6390 用例/R1-F05 真派生/R1-F09+R3-F03 服务事件三字段/R1-F01+R3-F04 pipeline 测试/R1-F13 try-finally+key 登记/R3-F01 11 键 |
| 3 | 全量实跑 | ✓ agent 域相关面 1364 passed + 1 failed（唯一失败 = 5-3 outbox 场景既有门控缺口——R1-F02 修复后从「假打 dev 5432 绿」转为「正确探测 5433 不可达红」的诚实暴露，5-3 资产面非本周期回归，已登记 R5-DF1）；unit 9374 零 warning；contracts 绿；CI 形态 5 passed |
| 4 | 留项台账完整性 | ✓ R1-DF1/DF2 镜像一致 + 触发条件在案；R3-OBS 维持注记在 Story；R5 特权发现 R5-DF1 补登记（5-3 门控缺口台账化——照抄 R1-F07 形态的触发器在案）；版本链 v2.1.0/v2.2.0/v2.3.0 + 底部字段一致 |
| 5 | 红线终扫 + 状态流转 | ✓ 红线计数 HEAD 与基线 8af9a17a 逐文件完全一致（零新增）；提交信息零 AI 署名；状态流转判定：**review → done**（对照 5-2 [3e067395]/5-3 [3b0b6e1a] 先例——代码审查 R5 收敛提交随附流转） |

> **代码审查周期收敛声明（R5 终审）**：Story 5.4 代码审查周期经 R1（四视角调研 + 双评审 + 主会话事实裁决——P1×2 + P2×5 + P3×7 落码 14 项）、R2（回归核查 + 组合交互面——P0×1 + P2×1 + P3×4 落码 6 项，其中 P0 为 R1 修复自引入的 CI 门禁击穿）、R3（单深度推演——16 格环境矩阵/CLI 三路径/八路径事件矩阵/9 格异码矩阵全闭合，P3×3 落码）、R4（纯验证——零规范级发现，9374 passed 零 warning）、R5（独立终审五节取证全过）——共 23 项落码修复 + 3 项 deferred 登记（R1-DF1/DF2/R5-DF1）+ 9 项维持（证伪留痕在案）。核心修复：SISYS_USE_TEST_PORTS 端口隔离击穿闭合（双向修复链经 R1→R2→R3 三轮深化收敛——Layer 3 守卫/sync 强覆写/MinIO 腿/CI 门禁/恢复键集）、pipeline 原子性等六类判别力锁定、446 真派生与单钟纪律兑现。全部证据与仓库现实一致，零 P0/P1/P2 残留。**代码审查周期正式收敛，Story 5.4 状态 review → done。**

**登记（deferred-work.md 镜像）**：

| # | 项 | 处置 |
|---|----|------|
| R1-DF1 | clear_scoped 接线纪律约束：DC-7 captive 缓解依赖「clear_scoped 生产未接线（SCOPED≡SINGLETON）」前提——组合根 L2879 注释自认；未来接线请求作用域时若只清 SCOPED 不清 SINGLETON，isolation_management_service 将持有绑已关闭事件循环的死亡 RedisAgentRepository（"Event loop is closed"） | deferred 登记（触发=请求作用域接线立项；接线时 clear_scoped 必须连同 clear_singleton 或翻 agent_repository SINGLETON） |
| R1-DF2 | StorageError(103) 同码双语义分化：①构造纪律分化——redis_snapshot_store.py:133/183 `raise StorageError(...) from e` 不带 cause= 构造参数（agent/isolation 仓储 cause=exc 形态——5-1 Task 3 教训）同码两种构造纪律（snapshot 域他 Story 资产）；②语义分化——数据损坏与连接故障同码 103，监控维度不可区分（context 标记 data_corrupt 或专用码） | deferred 登记（触发=存储层异常码专项或 5.5；与 agent_repository 先例统一行动——单仓先例不动） |

> **R1 证伪留痕（维持现状项——评审在案）**：①并发竞态（风险 #7 已登记，MVP 单用户 CLI 设计接受）；②publish 失败 warning 级别 vs 5-1 error 分裂已知——归属后续统一评估（DC-10 决策在案，修复需动 5-1 文件）；③get 443 守卫用 get_by_id 而非 exists（switch 需 role、单次取实例无多余往返）；④loader 放行 L1 到运行时 446（分层设计——440 配置无效 vs 446 阶段不支持语义区分）；⑤447 agent_id 默认空串（444/445 家族形态对齐，测试锁定）；⑥AC-6.2 stderr 正则宽匹配（R1-F15 文档审查定稿决策）；⑦aggregate_type="Agent"（__post_init__ 派生在位，弱观察）；⑧_print_switch_summary 防御回退/_PERF_CACHE 入参忽略（恒填充/前提文档化——弱观察）。
> **R1 评审过程记录**：双评审员对方案给出 4 条最小修正（甲：F02 补 _sync_config_to_environ 强覆写[P0 级遗漏联动面——只修 Layer 3 会产生 split-brain 红两个真实测试]/F02 补 MinIO endpoint 洞+门控收窄/F10 链路中间环节 archive_events/F13 预绑定守卫；乙：F02 双向修复裁定/D02 钉死所指+DF 命名/DC-10 维持注记/F05 保序勿 sorted）全部吸收；评审员甲乙在环方向上事实冲突由主会话副本实验定谳（甲对）。

#### 需决策 Decision Needed

- [ ] （无——Round 1 无需用户决策项）

#### 已修复 Patch

- [x] R1-F01~F14 全部落码（14 项——详见 Round 1 表；全量回归验证见提交）

#### 已推迟 Defer

- [x] R1-DF1/DF2 登记 deferred-work.md（触发条件在案）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] 运行 `dev-story` 开始实施（从 Task 0 开始）
- [x] 运行 `code-review` 进行代码审查（五轮收敛 v2.3.1——2026-10-22）
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

### 📋 变更日志 Change Log [dev-story 必填]

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-10-21 | v1.0.0 | 创建故事文件（四视角并行调研：Agent 实体与工作流链路 / 端口注册与组合根规范 / 验收与集成测试模板 / 异常体系与事件通道；12 项关键架构决策 DC-1~DC-12 + 6 项偏离声明 D-1~D-6；5-1 D6/D7 留项核销 + session_storage 再续期 + 工具熔断挂点评估；IsolationLevelSwitched 复用收紧 + 446/447 预留段核销 + AgentConfig D6 回填；范围边界表与 5.5/5.6/V1 精确切分） |
| 2026-10-21 | v1.1.0 | 文档审查周期 Round 1（四视角调研 + 三视角审查——科学性/一致性/可行性）：P0×1 + P1×8 + P2×20 + P3×19 去重后修复 48 表行。核心修复：R1-F01 TTL 链闭合（服务第四依赖 agent_config_loader——Task 0 钉死契约与 Task 3 骨架矛盾消解）；R1-F02 get 加 443 守卫（三方矛盾定稿）；R1-F03 AgentConfig 守卫统一 440 分码（242 破坏钉死测试风险消除）+ 242/440 分界原则入契约；R1-F05 回归面补全 8 处构造点；R1-F06 CLI 验收双清+instantiate 不经 main()；R1-F07 _parse_isolation_level 顺序对齐先例（变异可红）；R1-F27 D6/D7 核销落点校正（5-1 台账）；DC-3/DC-9/DC-7 论证修正与补登记；行号勘误五处；_RecordingEventPublisher 定性校正三处 |
| 2026-10-21 | v1.2.0 | 文档审查周期 Round 2（回归核查 + 组合交互面双审查）：P2×5 + P3×12 修复 17 表行。核心：R2-F02 第四依赖分派定稿（既有六文件 AsyncMock 回归同步 / 新验收场景真实四依赖组装——L214 引证失实校正）；R2-F01 DC-12 旧口径残留收口；R2-F04 AC-2 输入通道分层收口（"L9"→440 归单测面）；R2-F05 is_success=False 独立用例补红阶段；R2-F10 计时 helper 交付形态落 Task 6；.lower() 照抄警示；计数与归属勘误五项；R1 修复自引入破口清偿（表格转义/9→8 计数/先例归属） |
| 2026-10-21 | v1.3.0 | 文档审查周期 Round 3（单深度推演：17+1 场景三轴 + 5 时间线 + 数学完备性——含 Python 3.11.15 实测）：P1×1 + P2×3 + P3×6 修复 10 项 + 误报改判 1 项。核心：R3-F01 守卫双条件化（str,Enum 混入语义实测：合法值域裸 str "L3" in frozenset == True 穿透单守卫——isinstance 先行是唯一防线，switch_to 路径防静默类型污染）；R3-F02/F03 446 验收驱动细化（完整 yaml 基线 + config_dir 注入 + 服务级直调零残键）；R3-F04 验收侧分派改真实组装（CLAUDE.md 验收禁 mock 硬约束）；R3-F07 447 成因①方向修正（TTL 漂移不可构造）；R3-F06 并发竞态风险 #7 登记；R3-F09 双清归称终校准；R3-F10 误报留痕（L269/L271 三次定谳维持） |
| 2026-10-21 | v1.3.1 | 文档审查周期 R4 纯验证 + R5 独立终审判收敛：R4 零规范级修复（96 锚点 98.9% 精确/红线零违规/交叉计数全过——5 项台账级 P3/P4 留项）；R5 五节取证全过（周期闭合/六项关键修复双向一致/五高风险锚全中/红线零命中/R4 留项清偿行号复核无误）——零 P0/P1/P2 残留，**收敛声明入 Story，进入 dev-story 实施**；R4 五项留项随本收敛提交清偿 |
| 2026-10-22 | v2.0.0 | **dev-story 实施完成（Task 0-8 全勾选）**: src 新建 6 + 修改 12、tests 新建 10 + 修改 15、文档 4；验收 18/18 场景全绿（含 Task 8 收尾）、集成 5/5 绿、契约 24 断言绿、架构验证器 A-D 15 断言绿；每 Task 完整红绿变异循环（变异实证 13 项全部先红后还原）；D6/D7 留项核销落盘（5-1 台账勾选 + deferred-work 索引）；R6 改造——验收测试组织结构对齐 PG 模板（用户裁定）；实施期两发现: BDD 参数化步骤须 parsers.parse 显式声明 / isolation_state 对 isolation_policy 依赖经方法内延迟 import 打破包初始化环 |
| 2026-10-22 | v2.1.0 | **代码审查周期 Round 1**（四视角调研 + 双评审 + 主会话事实裁决）：P1×2 + P2×5 + P3×7 落码 14 项 + 登记 DF×2 + 维持 8 项（证伪留痕）。核心：R1-F02 SISYS_USE_TEST_PORTS 端口隔离被 conftest 模块级 litellm import 的 load_dotenv 副作用静默击穿（测试实读写 dev 6379/5432——environments.py 双向修复：Layer 3 端口守卫 + sync 强覆写 + MinIO endpoint 洞 + 4 用例锁定）；R1-F01 pipeline 原子性契约判别力锁定（5-1 先例移植）；R1-F05 446 supported_levels 真派生兑现 docstring 承诺；R1-F10 环方向 docstring 主会话副本实验定谳（value_objects-first 经 archive_events 断环——三方交叉验证，调研与评审员乙的两版链路均为误报）；R1-F13 集成异常路径清理闭合（key 即时登记模式）；双评审 4 条修正全吸收（甲 P0 级 split-brain 联动面最高价值） |
| 2026-10-22 | v2.2.0 | **代码审查周期 Round 2**（回归核查 + 组合交互面双审查 + 单评审快评）：P0×1 + P2×1 + P3×4 落码 6 项。核心：R2-F01 R1-F02 锁定用例击穿 CI 门禁（SISYS_TEST_ENV=ci 下 3/4 用例必红——实测复现；修复=显式锚定 local[delenv 被 CI 容器双重兜底击穿——评审实证] + CI 形态反向锁定用例[6390 差异化防恒真]）；R2-F02 MinIO 生产路径 split-brain 闭合（from_env 读 HOST/API_PORT 非 ENDPOINT——sync 补两键覆写）；R2-F05 判定式 helper 单一化；R2-OBS monkeypatch 真源性行为锁；R1 修复回归核查 13/14 干净 + 台账一致性全过 + 6380 MONITOR 实证 |
| 2026-10-22 | v2.3.0 | **代码审查周期 Round 3**（单深度推演）：零 P0/P1，P3×3 落码。R3-F01 锁定测试恢复键集缺口闭合（注入集扩至 sync 写集全量 11 键——进程内单向污染与 NEO4J 腿分裂触发条件消除）；R3-F03 trigger_reason 双投影统一（事件传 state.last_trigger_reason 单源）；R3-F04 R1 引入的 pipeline stub lambda 协程丢弃缺陷修复（partial 绑定真 async——全 unit 面唯一 RuntimeWarning 消除）；16 格环境矩阵/CLI 三路径/八路径事件/9 格异码矩阵全推演闭合 + 7 疑点证伪留痕 |
| 2026-10-22 | v2.3.1 | **代码审查周期 R4 纯验证 + R5 独立终审判收敛**：R4 零规范级发现（锚点全存续/计数全对账/unit 9374 passed 零 warning）；R5 五节取证全过（周期闭合/8 项关键修复双向一致/agent 域 1364 passed[唯一失败为 5-3 既有门控缺口→R5-DF1 台账化]/台账完整/红线零新增）——**收敛声明入 Story，状态 review → done**；R5 特权发现 R5-DF1（5-3 outbox 场景同型门控缺口）随收敛提交登记 |

---

**故事版本/Story Version:** v2.3.1
**创建日期/Created:** 2026-10-21
**最后更新/Last Updated:** 2026-10-22
**更新说明/Description:**
- v1.0.0: 创建故事文件
- v1.1.0: 文档审查周期 Round 1（48 表行修复——详见 Docs Review Fixes R1 表）
- v1.2.0: 文档审查周期 Round 2（17 表行修复——详见 Docs Review Fixes R2 表）
- v1.3.0: 文档审查周期 Round 3（10 项修复 + 1 误报改判——详见 Docs Review Fixes R3 表）
- v1.3.1: R4 纯验证 + R5 独立终审判收敛（收敛声明入 Story + R4 五项留项清偿）
- v2.0.0: dev-story 实施完成（Task 0-8 全交付）
- v2.1.0: 代码审查周期 Round 1（14 落码 + 2 登记 + 8 维持——详见 Review Findings R1 表）
- v2.2.0: 代码审查周期 Round 2（P0×1 + P2×1 + P3×4 落码——详见 Review Findings R2 表）
- v2.3.0: 代码审查周期 Round 3（零 P0/P1，P3×3 落码 + P3×1 维持——详见 Review Findings R3 表）
- v2.3.1: R4 纯验证 + R5 独立终审判收敛（收敛声明入 Story + 状态 review → done + R5-DF1 登记）
