# Story 4.6: 工具版本管理（灰度发布与回滚）

**Status:** `review`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 工具运维工程师,
**I want** 系统管理工具版本，支持版本控制、灰度发布与回滚,
**So that** 工具可以安全迭代，异常版本可快速恢复。

### 业务价值

- 覆盖 **FR-ST-06 (P1)**（prd.md:1821，公理依据 or.md 三.1.(2) 工具实体 + 三.工具箱.1[2] 中央技能仓库）。
- Epic 4「战略工具箱」V1 P1 扩展（执行优先级 P1-6）：23 种战略工具在 Skills 持续迭代（4.1b~4.1f 已交付多轮 Skill 增强）后，需要**安全的版本演进通道**——新版本 Schema 变更可能破坏下游消费者（Agent/工具链 DAG），必须先灰度验证再全量，异常时秒级回滚。
- **在 Epic 中的位置**：Epic 4 收官三故事之一（4.6/4.7），是 4.7 Validation Feedback 闭环的前置（4.7 重试需路由到"4.6 新版本 Tool"，见 Story 4-3 文件「4.6/4.7 架构演进路径」专章）。
- **依赖**：Story 4.1a（Tool 聚合根 / ToolRegistryService / ToolExecutionService 执行链）✅ done + Story 4.3（SchemaValidatorPort.validate_schema_compatibility 兼容性校验）✅ done。

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 工具多版本并存注册

**Given** 战略工具已注册（TOOL_CATALOG 或动态注册的工具，Tool 元数据存在）
**When** 运维为同一 tool_id 依次注册 v1.0.0、v1.1.0、v2.0.0 三个版本
**Then** 三个 ToolVersion 记录并存，`list_versions(tool_id)` 按注册时间返回全部版本
**And** 每个版本携带独立的 input_schema / output_schema 快照与状态（PENDING/CANARY/STABLE/DEPRECATED）
**And** 重复注册相同 (tool_id, version) 抛 `ToolVersionAlreadyExistsError`（EXCEPTION_431，HTTP 409）
**And** 为不存在的 tool_id 注册版本抛 `ToolNotFoundError`（EXCEPTION_380，HTTP 404）

**验证标准/Validation Criteria:**
- [ ] 同一工具 ≥3 个版本并存且互不覆盖
- [ ] (tool_id, version) 唯一性约束（仓储层 + PostgreSQL UNIQUE 索引双重保证）
- [ ] **单活跃不变量守护**：同一工具至多 1 个 STABLE、至多 1 个活跃 CANARY（PG partial unique index ×2 + InMemory save 校验双重保证，见 migration 表设计）
- [ ] 版本号 SemVer `X.Y.Z` 格式强校验（复用 Tool 实体 `_SEMVER_PATTERN` 规则；非法抛 `EntityValidationError` EXCEPTION_242，HTTP 400）
- [ ] Tool 元数据本身不被多版本改动（`ToolRepositoryPort` 零改动——版本归 ToolVersion 聚合根，Tool 保持"一个工具一条元数据"）

### AC-2: Schema 变更兼容性校验拦截（复用 Story 4.3 能力）

**Given** 工具当前存在 STABLE 版本（含旧 input_schema/output_schema）
**When** 注册携带 Schema 变更的新版本
**Then** 系统调用 `SchemaValidatorPort.validate_schema_compatibility(old_schema, new_schema)`（输入/输出双 Schema 均校验），按 `BreakingChange.severity` 最高级分级决策：
- **critical** 破坏性变更 → **拒绝注册**，抛 `ToolSchemaCompatibilityError`（EXCEPTION_397，HTTP 409，构造签名已带 tool_id/old_version/new_version/breaking_changes）
- **major** 破坏性变更 → 允许注册，标记 `required_rollout_mode="canary_only"`（后续发布强制灰度，**仅禁止 PENDING 状态直接全量**；灰度验证通过后 CANARY→STABLE 的 promote 转正放行——业界灰度系统均以"灰度毕业"为终点，Flagger/Argo Rollouts 的 promotion 语义）
- **minor** 或无破坏性变更（`is_compatible=True`）→ 允许注册，`required_rollout_mode="any"`（可直接全量发布）

**And** 兼容性校验的**方向语义**：input_schema 校验 ≈ backward（新版本工具须能接受旧调用方输入）、output_schema 校验 ≈ forward（旧下游须能消费新输出）——两处调用方向不同，结果取双 Schema severity 最高值（Confluent Schema Registry 的 BACKWARD/FORWARD 区分先例）
**And** 对 **PENDING 状态**的 canary_only 版本调用 `publish_version(weight=100)`（直接全量）抛 `ToolVersionTrafficWeightError`（EXCEPTION_432，HTTP 400）；对 **CANARY 状态**的 canary_only 版本调用 `publish_version(weight=100)`（灰度毕业转正）**放行**
**And** 首个版本（无历史 STABLE）跳过兼容性校验直接注册

**验证标准/Validation Criteria:**
- [ ] severity 分级决策与 Story 4-3 文件「4.6 对 4.3 的 API 依赖契约」表完全一致
- [ ] critical 拦截时异常 context 携带 tool_id/old_version/new_version/breaking_changes
- [ ] 决策逻辑为领域层纯函数（`RolloutPolicyService`，stdlib 原生参数，不依赖应用层类型）
- [ ] canary_only 的 432 拦截**仅对 PENDING 直接全量生效**（CANARY 提升放行）——注册→灰度→转正全链路可达（无死锁）
- [ ] 单测对 breaking_changes 断言**存在性与 max severity，不断言条数**（4.3 校验器顶层变更存在双重上报实态——主循环与嵌套递归对同一顶层 properties 各计 1 条，计数非本 Story 契约）

### AC-3: 灰度发布（按流量比例分配版本）

**Given** 工具存在 STABLE 版本 v1.0.0 与 PENDING 版本 v1.1.0（required_rollout_mode=any）
**When** 运维执行 `publish_version(tool_id, "1.1.0", traffic_weight=30)`
**Then** v1.1.0 转为 CANARY 状态、承接 30% 流量，v1.0.0 保持 STABLE 承接剩余 70% 流量
**And** 发起灰度（weight<100）**前置条件：工具存在 STABLE 版本**（灰度必是 stable/canary 二元流量分配；无 STABLE 时请求灰度 → EXCEPTION_432）——防止产生「CANARY 无 STABLE」的不可路由状态
**And** 版本路由是**确定性**的：`TrafficRouter.route(route_key, canary, weight, stable)` 基于稳定散列（hashlib，禁用进程盐化的内建 `hash()`），同一 route_key 永远路由到同一版本
**And** 发布权重域为 **(0, 100]**（traffic_weight <= 0 或 > 100 抛 `ToolVersionTrafficWeightError`，EXCEPTION_432，HTTP 400；weight=0 无业务语义，不采用 dark launch 形态）
**And** 同一工具同时只允许一个活跃 CANARY：已有活跃 CANARY 时对**其他版本**发起灰度 → EXCEPTION_432；对**活跃 CANARY 自身**再次 `publish_version(0<w<100)` 语义为**调档**（渐进放量 30%→50%→80%，CANARY→CANARY 同态迁移——业界灰度标准操作，Flagger stepWeight/Argo setWeight 先例）
**And** 灰度验证通过后 `publish_version(weight=100)` 将 CANARY 提升为 STABLE（promote 转正，any 与 canary_only 版本均放行），原 STABLE 自动降级 DEPRECATED（记录 `last_stable_at`）；事件 `from_status` 区分「PENDING 直接全量」与「CANARY 转正」两种审计语义
**And** 灰度失败可**放弃**：`abort_canary(tool_id)` 将活跃 CANARY 转 DEPRECATED（CANARY→DEPRECATED，不记 last_stable_at——从未稳定），STABLE 不动、流量 100% 回 STABLE（业界 abort 语义：Flagger 回滚=流量回 primary 且 primary 不动）；无活跃 CANARY 时 abort → EXCEPTION_243（无合法迁移）

**验证标准/Validation Criteria:**
- [ ] 1000 个不同 route_key（固定样本集 `f"key-{i}"`，i∈range(1000)——跨次运行/xdist 稳定）的分配比例在 30%±5% 容差内（确定性散列的统计验证）
- [ ] 同一 route_key 重复解析 100 次结果完全一致（确定性）
- [ ] 命中/未命中断言**独立判别**：TrafficRouter 的散列算法与桶映射为**规范条款（非实现自由度）**——`int(hashlib.sha256(route_key.encode()).hexdigest(), 16) % 100 < weight` 命中 canary（实现与测试共用此公式）；测试按该公式独立重算期望桶位与 `resolve_version` 输出比对，**禁止以 `route()` 探测结果作断言锚点**（同源循环论证无判别力）；另加 weight=100（任意 key 必 canary）/灰度不存在（必 stable）两个零散列依赖的边界探针
- [ ] 提升为 STABLE 是原子操作（新 STABLE 写入 + 旧 STABLE 降级在同一事务/savepoint 内——**原子性断言唯一归属 Task 7 集成测试**；单元层仅断言多行 save 全部发生 + 失败不发布事件）
- [ ] 状态迁移非法路径（如 STABLE→CANARY、DEPRECATED→CANARY）抛 `EntityStateTransitionError`（EXCEPTION_243，复用先例）
- [ ] CANARY 调档（30→50）不改变版本状态、事件 from_status==to_status=CANARY 且携带新 weight

### AC-4: 一键回滚至历史稳定版本（保留最近 10 个版本）

**Given** 工具 v2.0.0 为当前 STABLE 且被判定异常，历史存在曾稳定版本 v1.9.0（DEPRECATED，`last_stable_at` 最新）
**When** 运维执行 `rollback(tool_id)`（不指定目标版本）
**Then** 系统一键回滚：v2.0.0 → DEPRECATED（**显式清空 last_stable_at（置 None，含残留戳清除）**——业界 stable 指针原则：指针只在成功 promotion 时推进；清空而非仅"不记录"，确保携带 promote 期残留戳的版本[经回滚恢复后再次被降级者]也真正退出缺省候选与显式目标集——第三次缺省回滚不会 ping-pong 复活），v1.9.0 → STABLE（DEPRECATED→STABLE 回滚恢复迁移，**唯一合法触发方是 rollback 流程**），活跃 CANARY（若有）一并降级 DEPRECATED（不记 last_stable_at，weight 置 0），流量 100% 回到 v1.9.0
**And** 回滚操作原子完成（PostgreSQL 仓储内 savepoint 包裹多行状态变更，参照 domain_dictionary_repository.rollback 先例）
**And** **缺省目标选取（防 ping-pong）**：`last_stable_at` 非空的 DEPRECATED 版本中取 `last_stable_at` 最大者，但**排除本次被降级的当前 STABLE 版本**（否则连续两次回滚会回到刚因异常被放弃的版本——业界 stable 指针只在成功 promotion 时推进，不因回滚更新）
**And** 指定 `rollback(tool_id, target_version)` 时：目标版本**记录不存在** → `ToolVersionNotFoundError`（EXCEPTION_430，HTTP 404——资源定位失败）；记录存在但非"曾稳定"版本（非 DEPRECATED 或 last_stable_at 为空）→ `ToolVersionRollbackError`（EXCEPTION_433，HTTP 409——状态不允许）
**And** 无当前 STABLE 或无任何可回滚的稳定历史版本时抛 `ToolVersionRollbackError`（EXCEPTION_433）
**And** 版本保留策略：每工具版本**总数**（含 STABLE/CANARY/PENDING/DEPRECATED）不超过 `max_retained_versions`（默认 10，`TOOL_VERSION_MAX_RETAINED` 环境变量可覆盖），超出时**仅淘汰 DEPRECATED**（STABLE/CANARY/PENDING 受保护，永不淘汰；**可淘汰 DEPRECATED 不足时上限为软约束——保护态优先于数量上限**，如 11 个全为受保护状态则不淘汰）；淘汰两级排序：第一级 `last_stable_at` 为空者（灰度清场产物，非回滚候选）优先，第二级组内排序——无戳组按 `created_at` 升序（平局裁决键）、带戳组按 `last_stable_at` 升序（淘汰键与回滚价值键对齐）。**淘汰触发点 = register_version**（abort/rollback 不触发，下次注册时收敛）。**审计取舍声明**：物理删除即失去该版本 schema 快照（历史 `ToolExecution.tool_version` 仅存版本号），V1 接受该取舍，4.7 启动前评估是否改为"仅摘路由候选"的软淘汰

**验证标准/Validation Criteria:**
- [ ] 缺省回滚目标 = `last_stable_at` 最新的 DEPRECATED 版本，且**排除本次 from_version**（连续两次缺省回滚不 ping-pong）
- [ ] 缺省目标选取在含 NULL last_stable_at 的集合上排序安全（显式过滤非 NULL 后取最大）
- [ ] 显式目标不存在（404/430）与非可回滚态（409/433）两码分立，响应体均验证 error.code
- [ ] 淘汰从不过半当前 STABLE 与活跃 CANARY；PENDING 同受保护（仅注册未发布的版本不被后续注册静默淘汰）
- [ ] 保留策略由领域纯函数 `VersionRetentionPlanner.plan(全部版本, max_retained)` 计算（可单测）
- [ ] 配置模式遵循 `SandboxConfig.from_env()` 先例（frozen dataclass + ConfigurationError）

### AC-5: 版本化执行集成（执行链透明路由）

**Given** 工具 v1.0.0 STABLE / v1.1.0 CANARY(30%) 并存，ToolExecutionService 已注入 ToolVersionService
**When** Agent 通过 `ToolExecutionService.execute(tool_id, tool_call, context)` 执行工具
**Then** 服务在委托引擎前完成版本路由：`resolve_version(tool_id, requested_version=tool_call.version, route_key=context.trace_id)`
**And** 命中灰度 → 用 `dataclasses.replace(tool, version=tv.version, input_schema=tv.input_schema, output_schema=tv.output_schema)` 派生执行用 Tool 副本（引擎与装饰器链零改动）
**And** `ToolCall.version` 显式指定时跳过流量路由，精确执行该版本（不存在 → EXCEPTION_430）
**And** 引擎创建的 `ToolExecution` 聚合 `tool_version` 快照 = 路由后实际执行版本（engine `tool_execution_engine.py` 以传入的派生副本快照 `tool.version`，零改动即生效）
**And** 未指定版本时的路由兜底规则（三分支，消除歧义）：① **无任何版本记录** → 惰性以 `Tool.version` 当前值注册初始 STABLE 版本（向后兼容：catalog 23 工具首次执行零迁移；**幂等容错**：并发首执行撞 (tool_id,version) 唯一约束得 431 时捕获并重读既有记录返回，不打穿执行链）；② **有版本记录但无活跃版本**（全 PENDING/DEPRECATED）→ `ToolVersionNotFoundError`（EXCEPTION_430，无活跃版本可路由）；③ 有活跃版本 → 正常路由
**And** `ToolCall.version` 显式指定但版本记录不存在 → EXCEPTION_430
**And** 未注入 ToolVersionService 时执行链保持 4.1a 原行为（可选依赖，默认装配后启用）
**And** **route_key 选型声明**：`route_key=context.trace_id` 的粒度是**单次执行确定性**（非会话粘性——一次多 Agent 链路对同一工具的多次调用可能 v1/v2 混杂）。V1 接受该取舍（系统现有执行上下文无更粗粒度的稳定会话 key）；analysis_id 级粘性 key 升级留 4.7/后续演进

**验证标准/Validation Criteria:**
- [ ] ToolExecutionEngine / ToolOutputValidator / SandboxSecurityDecorator 源码零修改
- [ ] tool_execution_service 端口升级 v1.2.0 → v1.3.0（tags 追加 "versioned"，compatibility 声明 "v1.2.0"——**替换语义**：现状 compatibility=("v1.0.0",) 直接替换为新值，非追加）
- [ ] 灰度命中与未命中两个 route_key 分别验证（确定性可测，断言方法见 AC-3 验证标准——独立散列重算，禁止 route() 探测同源锚点）
- [ ] Schema 校验装饰器使用的是路由后版本的 schema（派生副本生效：装饰链顶层收到的已是副本）
- [ ] 惰性注册三分支各有一测：无记录（注册成功）/ 并发同号（431 容错后返回既有）/ 有记录无活跃（430）
- [ ] **事件边界（重要）**：`ToolExecuted` 事件由 `StrategicAnalysisUseCase` / `auto_execute_completed_handler` 发布——前者持有 registry 原始 Tool 对象（路由前，tool_version=路由前版本）；后者不持有 Tool 对象（tool_version 恒为默认空串，实态见 tool_events.py:36 + handler:84-88）。两者的 `tool_version` 字段都**不会**自动变为实际执行版本——实际版本的权威记录是 `ToolExecution.tool_version` 快照。AC-5.4 场景断言后者（引擎聚合快照），不断言前者（见非目标）

### AC-6: 运维 REST API

**Given** 工具运维工程师已通过 OAuth2 认证
**When** 通过 `/api/v1/tools/*` 端点管理版本
**Then** 端点行为如下（全部经认证依赖，统一错误响应 `error.code + error.message + request_id`）：

| 端点 | 方法 | 成功 | 主要错误 |
|------|------|------|---------|
| `/api/v1/tools/{tool_id}/versions` | POST | 201 版本详情 | 404(380)/409(431/397)/400(242——SemVer/Schema 实体校验失败走 `EntityValidationError`；注册流程无 432 抛出点) |
| `/api/v1/tools/{tool_id}/versions` | GET | 200 版本列表 `{items,total}` | 404(380) |
| `/api/v1/tools/{tool_id}/versions/{version}/publish` | POST | 200 发布结果（含调档） | 404(430)/400(432)/409(243) |
| `/api/v1/tools/{tool_id}/rollback` | POST | 200 回滚结果（body 可选 `target_version`） | 404(380/430——目标版本记录不存在)/409(433——存在但非可回滚态) |
| `/api/v1/tools/{tool_id}/abort-canary` | POST | 200 放弃灰度结果 | 404(380)/409(243——无活跃 CANARY 无合法迁移) |
| `/api/v1/tools/{tool_id}/versions/traffic` | GET | 200 流量分布 `{stable_version,canary_version,canary_weight}`（无活跃版本时 200 全 null 字段） | 404(380) |

**And** 路由工厂模式遵循 `domain_dictionary.py` 先例（`create_tools_router(...)` + 三级降级认证：override → 参数注入 → DI 容器——认证是每路由 `Depends(get_current_user)` 依赖注入形态，非全局中间件），并注册进 `app.py create_app()`（漏挂不产生报错，靠契约测试兜底——Task 6 契约测试必须含端点存在性断言）
**And** `docs/api/openapi.yaml` 同步新增全部端点与 Schema（当前 0 处 tool path；6 端点 / **5 个 path**——GET 与 POST 共享 `/versions` 同一 path）

**验证标准/Validation Criteria:**
- [ ] API 契约测试（`tests/contracts/test_api_contract_tools.py`）通过
- [ ] Edge Cases 至少覆盖 404/409/400 路径（响应体验证 error.code + error.message + request_id）
- [ ] 认证缺失返回 401

### AC-7: 性能要求

**Given** 版本管理服务就绪（PostgreSQL 仓储真实连接 或 验收环境 InMemory 仓储）
**When** 执行版本切换（publish/rollback）与版本路由（resolve_version）
**Then** 满足以下指标（性能断言分级模式，Story 4-5 先例：达标 assert pass；环境不达标 pytest.skip 并留存测量证据，禁止伪造）：

| 指标 | 目标 | 测量方法 |
|------|------|---------|
| 版本切换延迟 | P95 < 500ms | 50 次 publish+rollback 往返计时，`statistics.quantiles(n=20)[18]`（Story 4-4 先例，禁用 `sorted()[19]` P100 冒充） |
| 灰度发布成功率 | ≥ 95% | 50 次发布操作成功数 / 50 |
| 回滚成功率 | 100% | 全部回滚操作要么成功要么明确失败（原子性，无中间态） |
| 版本路由开销 | P95 < 5ms | 1000 次 resolve_version 计时——**仅 InMemory 仓储装配下断言**（内存查表+散列）。PG 装配下 resolve 每次执行含一次 `list_active` DB 往返（本 Story 无路由缓存，见非目标），该基准 skip 并留测量证据，另测单次 list_active 往返作参考值 |

**验证标准/Validation Criteria:**
- [ ] 性能测试结果以测量值断言，不达标时 skip 留证据（诚实工程）
- [ ] 路由开销与切换延迟分开测量、分开断言；路由开销基准标注装配形态（InMemory 断言 / PG 参考值）
- [ ] 性能测量在 `--cov` tracing 开销下运行（pyproject addopts 全局启用），阈值已含该余量

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 事件定义位于 `src/domain/events/tool_version_events.py`
- [ ] 使用标准库实现领域事件校验（dataclass / Enum），禁止在领域层依赖 Pydantic
- [ ] 事件命名符合规范（`[Aggregate][EventName]`，聚合根 = ToolVersion）：

| 事件 | 触发场景 | 关键 payload 字段 |
|------|---------|------------------|
| `ToolVersionRegistered` | register_version 成功 | tool_id, version, required_rollout_mode, breaking_summary |
| `ToolVersionPublished` | publish_version 成功（灰度发起/调档/直接全量/提升转正）与 abort_canary 成功（from=CANARY→to=DEPRECATED） | tool_id, version, from_status, to_status, traffic_weight |
| `ToolRolledBack` | rollback 成功 | tool_id, from_version, to_version, trigger, deprecated_versions |

- **事件语义细则**：`ToolVersionPublished` 的 `from_status` 区分审计语义（PENDING=直接全量 / CANARY=转正或调档）；调档场景 from_status==to_status=CANARY 且 traffic_weight 为新值；`ToolRolledBack.deprecated_versions`（list，截断 ≤10）记录本次被降级的全部版本号（含被清场的 CANARY）——下游可完整重建状态史。`trigger` 枚举值：`"api"` / `"manual"` / `"auto"`（V1 仅 api/manual）。**惰性初始注册不发 `ToolVersionRegistered`**（resolve 惰性分支无事件步骤——审计取舍：catalog 23 工具首次执行不产生事件风暴，显式 register_version 才发事件）
- **`event_type` 字段写法约束（自动注册前提）**：`DomainEvent.__init_subclass__` 仅在子类把 `event_type` 声明为 `field(default="Xxx", init=False)` 时才注册（`tool_events.py:37` 先例）——3 个新事件必须照抄该写法，否则不进事件注册表

- [ ] 继承 `src/domain/events/base.py` 的 `DomainEvent`（frozen dataclass，`__init_subclass__` 自动注册，`aggregate_type="ToolVersion"`）
- [ ] 事件为平台级资源事件（工具版本全局共享，非租户数据），payload 不含 tenant_id——Dev Notes 有理由说明
- [ ] **双通道配置**：`configs/event_channels.yaml`（注意目录是 `configs/` 不是 `config/`）+ `src/infrastructure/messaging/channel_router.py` 的 `DEFAULT_MAPPINGS`（L41 类定义）**两处必须同步更新**（CLAUDE.md 硬约束）。参照 `ToolSchemaValidationFailed` 条目（yaml L107-110）使用 realtime 通道（管理类事件，无可靠投递诉求）

#### 数据模型 (Data Models)
- [ ] `ToolVersion` 聚合根定义位于 `src/domain/entities/tool_version.py`
- [ ] 状态枚举 `ToolVersionStatus(str, Enum)`——**成员显式小写值，与 migration CHECK 值域一一对应**：`PENDING = "pending"`（已注册未发布）/ `CANARY = "canary"`（灰度中）/ `STABLE = "stable"`（当前全量）/ `DEPRECATED = "deprecated"`（已弃用，含"曾稳定"语义）
- [ ] 状态机迁移矩阵（非法迁移抛 `EntityStateTransitionError` EXCEPTION_243，ToolExecution 先例；**7 个合法迁移格 / 8 种触发语义**——STABLE→DEPRECATED 分「被新版本替代」与「被回滚」两支，戳记规则不同）：

```
PENDING --publish(0<w<100)--> CANARY（前置：存在 STABLE，否则 432）
PENDING --publish(w=100, mode=any)--> STABLE（直接全量；canary_only 在此禁止 → 432）
CANARY --publish(0<w<100)--> CANARY（调档：渐进放量，同态迁移）
CANARY --publish(w=100)--> STABLE（promote 转正；any/canary_only 均放行——灰度毕业通道）
CANARY --abort_canary--> DEPRECATED（放弃灰度；不记 last_stable_at）
STABLE --被新版本替代(promote/直接全量)--> DEPRECATED（记录 last_stable_at——曾全量服务标记，回滚候选依据）
STABLE --被回滚--> DEPRECATED（**清空 last_stable_at**——被放弃版本退出候选集，指针原则）
DEPRECATED --rollback 恢复--> STABLE（唯一合法触发方：rollback 流程）
（STABLE→CANARY、DEPRECATED→CANARY、DEPRECATED→DEPRECATED 等其余路径全部非法）
```

- [ ] `transition_to()` 复用 ToolExecution 模式但**不带 `state_version` 乐观锁自增**（ToolVersionRepositoryPort 无乐观锁方法，本 Story 仓储用 savepoint 原子性而非 CAS——与先例的差异点须在实体 docstring 注明）
- [ ] 字段规范：`version_id: UUID`（PK）、`tool_id: UUID`、`version: str`（SemVer 强校验）、`input_schema/output_schema: dict`、`status: ToolVersionStatus`、`traffic_weight: int ∈ [0,100]`（存储当前承接流量比例：PENDING=0、CANARY=灰度权重 w、STABLE 语义恒 100；发布参数域为 (0,100] 由服务层校验——实体层允许 0 是 PENDING 初始态需要）、`required_rollout_mode: Literal["any","canary_only"]`（小写值，同 status）、`last_stable_at: datetime | None`（曾为 STABLE 的时间戳，回滚候选依据；灰度清场降级不记录）、`created_at/updated_at: datetime`
- [ ] 实体不变量：`__post_init__ → validate()`（Tool 先例）；schema 非空时须含 JSON Schema 关键词（复用 Tool 的 `_JSON_SCHEMA_KEYWORDS` 规则）
- [ ] 查询值对象 `ToolVersionQuery`（`@dataclass(frozen=True)`，Query Object 模式）：tool_id / status / version / created_after / created_before / offset / limit——**多字段组合+分页必须用 Query Object**（CLAUDE.md 端口查询参数决策规则）
- [ ] 值对象 `RolloutDecision`（frozen）：`allowed: bool` / `mode: Literal["any","canary_only"]` / `reason: str`
- [ ] **Tool 聚合根与 ToolRepositoryPort 零改动**（多版本归 ToolVersion 新聚合根，不碰 `_tools_by_name` 唯一性语义）

#### 统一端口定义注册与管理 (Port Contract)
- [ ] 端口契约定义位于 `src/domain/ports` 与 `src/application/ports`
- [ ] 端口注册中心位于 `src/domain/ports/registry.py`，所有端口必须登记为 `PortSpec`
- [ ] 端口实现仅可在 `src/composition_root.py` 统一注册，禁止业务代码直接实例化具体实现
- [ ] 端口解析器位于 `src/domain/ports/resolver.py`，业务代码只通过抽象解析实现
- [ ] 端口契约门禁位于 `src/domain/ports/contract_gate.py`，端口变更必须通过兼容性检查
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_tool_version_repository.py` + `test_port_contract_tool_version_service.py`）
- [ ] 接口命名符合单一职责，禁止同义接口重复定义
- [ ] 端口具备唯一名称、版本、owner、兼容策略
- [ ] 跨模块调用仅依赖抽象接口，不直接依赖实现类
- [ ] 端口变更配套契约测试与兼容性检查
- [ ] 禁止在服务文件中本地定义 Protocol / Port 抽象

**本 Story 端口清单（唯一事实源 / Single Source of Truth）：**

| 端口名 | 层 | interface | impl（注册实现） | version | lifetime | owner | tags |
|--------|---|-----------|-----------------|---------|----------|-------|------|
| `tool_version_repository` | domain | `ToolVersionRepositoryPort`（继承 `L2RdbPort[ToolVersion]`，async，含 `ToolVersionQuery`） | `src.infrastructure.storage.postgresql.repository.tool_version_repository.PostgreSQLToolVersionRepository` | v1.0.0 | SCOPED | tool-team | (tool, version, repository, postgresql, sqlalchemy) |
| `tool_version_service` | application | `ToolVersionServicePort` | `src.application.services.tool_version_service.ToolVersionService`（工厂注入 repository + schema_validator + tool_registry + **max_retained_versions 标量**——组合根以 `ToolVersionConfig.from_env().max_retained_versions` 解析后传入） | v1.0.0 | SCOPED | tool-team | (tool, version, service) |
| `tool_execution_service`（升级） | application | `ToolExecutionServicePort` | 同现有，新增可选注入 `tool_version_service` | **v1.2.0 → v1.3.0** | SCOPED | tool-team | 现有 tags + ("versioned",)，compatibility 声明 ("v1.2.0",) |

- [ ] `ToolVersionRepositoryPort` 方法集（对齐 `ToolExecutionRepositoryPort` 先例）：`save` / `get_by_id` / `get_by_tool_and_version(tool_id, version)` / `list_by_query(query)` / `count(query)` / `list_active(tool_id)`（CANARY+STABLE）/ `delete(version_id)`
- [ ] `ToolVersionServicePort` 方法集（7 方法）：`register_version(tool_id, version, input_schema, output_schema)` / `publish_version(tool_id, version, traffic_weight=100)` / `abort_canary(tool_id)` / `rollback(tool_id, target_version=None, trigger="api")` / `resolve_version(tool_id, requested_version=None, route_key=None)` / `list_versions(tool_id)` / `get_version_traffic(tool_id)`
  - `publish_version` 按 tv 当前状态分语义：PENDING+0<w<100=发起灰度（需存在 STABLE）/ PENDING+w=100=直接全量（canary_only 禁）/ CANARY+0<w<100=调档 / CANARY+w=100=promote 转正（any/canary_only 均放行）
  - `abort_canary(tool_id)`：无活跃 CANARY 抛 243（无合法迁移）；成功后 STABLE 不动、流量全回 STABLE
  - **通用前置（AC-6 表 404(380) 的服务层来源）**：除 `resolve_version`（惰性分支内含 get_tool）外，全部公开方法第一步 `tool_registry.get_tool(tool_id=tool_id)` → 380（含 `list_versions` / `get_version_traffic`——不存在的 tool_id 返回 404 而非空列表 200）
  - 初始版本建立**统一走 resolve_version 惰性注册**（无独立 eager 方法——AC-5 三分支规则是唯一入口，避免双初始化策略互竞）
- [ ] R2 组合注入：`ToolVersionService.__init__(repository, schema_validator: SchemaValidatorPort, tool_registry: ToolRegistryServicePort, max_retained_versions: int = 10)`——**注入标量而非 Config 对象**（SandboxConfig 先例的注入形态：`ToolVersionConfig.from_env()` 在组合根解析后传标量；应用层服务**禁止 import `src.infrastructure.*`**——`.importlinter` 契约 `application-no-infrastructure` 强制校验，注入 infrastructure 层 Config 类型会 CI 必炸）

#### 端口契约清单执行约束（强制）
- [ ] 本模板中的端口清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口，禁止未同步更新 registry / resolver / contract test
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增/修改的领域异常必须在 Task 0 中完成设计，禁止在实现 Task 中临时定义。
> **适用范围：** 本清单仅针对定义在 `src/domain/exceptions/` 下、继承自 `DomainError`（别名 `BaseException`）的**领域异常**。
> **不在本清单范围：** FastAPI/Pydantic 框架原生异常、第三方 SDK 原始异常（由 `ErrorMapper` 映射）。
> **禁止 `raise ValueError`：** 所有验证失败（例如：实体不变量、状态转换守卫、业务约束、配置参数、输入校验）均使用领域异常体系。
> 完整检查清单与全量异常分类详见 [`sisys-uni-exception-design.md §3.12`](../../../docs/architecture/sisys-uni-exception-design.md#312-异常注册检查清单)。
> 编码分配策略（人工编码 + CI 自动校验）详见 [`sisys-uni-exception-design.md §3.3`](../../../docs/architecture/sisys-uni-exception-design.md#33-编码分配策略人工编码--ci-自动校验)。

- [ ] **新增子域段 `tool_version (430, 439)`**：现有 tool 段 (380-389) 仅剩 384 保留位、toolchain 段 (390-399) 仅剩 399 且已被 Story 4.7 预占（4.7 另计划扩 400-409），**两个旧段均不可用**。照 `data_source (410,419)` / `debate (420,429)` 独立段先例新开 430-439，预留 434-439 给后续协调（434-439 暂不分配，保持空段预留）
- [ ] 归属模块与基类：

| code | 异常类 | parent class | HTTP | 触发场景 |
|------|--------|-------------|------|---------|
| EXCEPTION_430 | `ToolVersionNotFoundError` | `NotFoundError` | 404 | 版本不存在（精确查找空 / rollback 显式目标无记录 / 有版本记录但无活跃版本可路由） |
| EXCEPTION_431 | `ToolVersionAlreadyExistsError` | `ConflictError` | 409 | (tool_id, version) 重复注册 |
| EXCEPTION_432 | `ToolVersionTrafficWeightError` | `ValidationError` | 400 | 权重非法（<=0 或 >100）、canary_only 版本 PENDING 直接全量、无 STABLE 请求灰度、并存冲突族（活跃 CANARY 并存 / 单 STABLE·单 CANARY 不变量并发破坏——partial unique index 冲突经仓储转换 / InMemory save 守卫） |
| EXCEPTION_433 | `ToolVersionRollbackError` | `InvalidStateError` | 409 | 无可回滚稳定历史 / 目标版本非"曾稳定"版本 |

- [ ] **复用清单（禁止重复造轮子）**：兼容性拦截复用 `ToolSchemaCompatibilityError`（EXCEPTION_397，**已存在**于 `src/domain/exceptions/tool_schema_exceptions.py:116`，构造签名已带 tool_id/old_version/new_version/breaking_changes，docstring 明确"用于 Story 4.6 灰度发布拦截破坏性发布"）；状态机守卫复用 `EntityStateTransitionError`（243）；实体不变量复用 `EntityValidationError`（242）；配置校验复用 `ConfigurationError`（101）；工具不存在复用 `ToolNotFoundError`（380）
- [ ] 唯一编码分配 — 运行 `grep -r "EXCEPTION_43[0-9]" src/domain/exceptions/` 验证无碰撞
- [ ] 构造器参数设计 — 携带领域上下文（tool_id/version/traffic_weight/target_version 等），通过 `context` 字典暴露
- [ ] 消息安全性审查 — 错误消息面向调用方可理解，不泄露 SQL/堆栈等内部实现细节
- [ ] 编码注册 — `_code_ranges.py` 的 `CODE_RANGES` 增加 `tool_version: (430, 439)` + `_CLASS_TO_SUBDOMAIN` 注册 4 类；更新 `sisys-uni-exception-design.md`——**注意该文档存在两个同号 §3.3.2 小节（:649 完整编码分配表 + :781 子域编码范围约束），两表都必须更新**（分配表在 debate 423~429 行后插 430-433 四行 + 434-439 预留行；子域表在 debate 行后加 `tool_version | 430–439` 行），否则 test_code_ranges 与文档漂移
- [ ] 导出完整性 — 模块 `__all__` + `src/domain/exceptions/__init__.py` 导入 + `EXCEPTION_HTTP_MAP` 映射（`src/interfaces/api/exception_handlers.py` L125-251，**注释行号必须与 code 严格一致**——4.1a 曾发生注释偏移 bug）
- [ ] 测试覆盖 — 构造/`to_dict()`/HTTP 映射/编码唯一性 + 子域范围测试全部通过：
    - `poetry run pytest tests/unit/domain/exceptions/ -v`（**「8 项既有测试」口径 = `test_error_code_uniqueness.py` 3 个 + `test_code_ranges.py` 5 个测试函数**；该命令实际运行整个 exceptions 目录 24 文件全量，均须绿）
    - `poetry run pytest tests/unit/interfaces/api/test_exception_handlers.py -v`（**期望集合必须同步扩展**，4-5 教训：新增映射不同步期望集会导致该测试失败）
- [ ] BDD 验收场景 — 异常路径的 Gherkin 场景纳入 Edge Cases（AC-1/3/4 已覆盖 431/432/433 路径）

#### API 契约 (API Contract)
- [ ] 遵循 OpenAPI 标准的 API 契约定义位于 `docs/api/openapi.yaml`（当前 0 处 tool path，全新增）
- [ ] 端点清单见 AC-6 表格（6 端点 / 5 个 path）；`servers.url = http://localhost:8000/api/v1`，path key 不带 `/api/v1` 前缀（除历史遗留 3 个外全库一致）
- [ ] Schema 定义：`ToolVersionCreate`（version/input_schema/output_schema required）、`ToolVersionResponse`、`ToolVersionListResponse{items,total}`、`PublishRequest{traffic_weight: int, minimum: 1, maximum: 100, default 100}`（发布参数域 (0,100]——0 无业务语义）、`RollbackRequest{target_version?: string}`、`TrafficViewResponse{stable_version,canary_version,canary_weight}`（无活跃版本时三字段为 null）
- [ ] 参照 `/documents/{document_id}/versions` + `/versions/snapshot`（openapi.yaml L56-129）的 201/401/404/409 响应模式与 OAuth2 security 声明
- [ ] API 契约测试通过（`tests/contracts/test_api_contract_tools.py`，规范先行模式 B——参照 `test_api_contract_document_version.py` L37-44 注释惯例：路由未实现时先静态断言规范，实现后升级为 TestClient 真实请求）
- [ ] API 版本管理正确（`/api/v1/tools/...`）

#### 六边形架构约束（必须遵守）
> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖 |
| application | `src/application/` | 用例编排 |
| interfaces | `src/interfaces/` | 适配器 |
| infrastructure | `src/infrastructure/` | 技术实现 |

**领域层零依赖原则**
- 领域层（`src/domain/`）仅使用 Python 标准库
- 禁止导入：包括且不限于 langgraph, prefect, fastapi, pydantic, sqlalchemy, typer, redis, qdrant, minio, neo4j, aio_pika, litellm, instructor, requests, httpx, docker, psycopg2

**设计规则映射（用户设计规则 R1-R4）**
- **R1** 领域层统一抽象基础端口 → `ToolVersionRepositoryPort`（domain/ports，含 Query Object）
- **R2** 应用层具体应用端口组合注入基础端口 → `ToolVersionServicePort` 组合注入 `ToolVersionRepositoryPort` + `SchemaValidatorPort` + `ToolRegistryServicePort`；`ToolExecutionServicePort` 组合注入 `ToolVersionServicePort`
- **R3** 基础设施层实现端口、负责技术实现与管理 → `PostgreSQLToolVersionRepository`（SQLAlchemy + migration 016）+ `InMemoryToolVersionRepository`（测试直连实例化，不走组合根），双实现支持扩展其他同类技术
- **R4** 接口层适配外部请求、格式化响应 → `tools.py` 路由工厂 + ExceptionHandlers 自动映射 + openapi 契约

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

> ⚠️ **领域层依赖红线（本 Story 特有）**：`SchemaCompatibilityResult` / `BreakingChange` 定义在 `src/application/ports/schema_validator.py`（应用层）。领域层 `RolloutPolicyService` **禁止 import 该模块**——签名必须用 stdlib 原生参数（`max_severity: str | None`、`breaking_count: int`），由应用层服务从 `SchemaCompatibilityResult` 提取摘要后传入。

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_tool_version_management.feature`（模板：`test_acceptance_postgresql_relational_layer.feature` 的结构风格 + `test_acceptance_tool_io_schema_validation.feature` 的工具系场景组织——`AC-x.y - ` 场景名前缀 + `# ====` AC 分隔注释）
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_tool_version_management.py`（context dict + `scenarios()` 批量注册 + `_make_*()` 工厂 + 模块级 `event_loop` fixture + 真实服务：`InMemoryToolVersionRepository` / `JsonSchemaValidatorImpl` / `ToolRegistryService` / `InMemoryToolRepository` 全真实实例——服务级场景仅 LLM/Sandbox 端口适配器允许 `AsyncMock`；HTTP 级 AC-6 场景按认可子模式用服务 `AsyncMock` + TestClient）
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases，AC-1~AC-7 全量场景见 Task 0 Subtask 清单）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径** — 每个资源端点的 Gherkin 场景至少覆盖：资源不存在（404）、权限不足（403/401）、资源冲突（409），响应体验证 `error.code` + `error.message` + `request_id`
- AC-6 HTTP 级场景用 `@scenario` 显式绑定 + TestClient + 服务 `AsyncMock`（HTTP 级 BDD 认可子模式，参照 `test_api_contract_document_upload.py` 的 `_make_client()`）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [ ] 规范文档通过人工评审或自动化校验

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试（违反 TDD 测试先行原则）
- ❌ 将测试编写集中到最后一个 Task（违反 TDD 小步快跑原则）
- ❌ 跳过红阶段验证（未确认测试失败就直接写实现）

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | ToolVersion 实体 | 构造校验/状态机迁移/不变量 | `tests/unit/domain/entities/test_tool_version.py` | Task 1 |
| **TDD 单元测试** | 领域服务三件套 | RolloutPolicy 决策/TrafficRouter 确定性路由/RetentionPlanner 淘汰规划 | `tests/unit/domain/services/test_tool_version_policy.py` | Task 1 |
| **TDD 单元测试** | 领域事件 | 事件字段/payload/自动注册 | `tests/unit/domain/events/test_tool_version_events.py` | Task 2 |
| **TDD 领域异常测试** | `src/domain/exceptions/tool_version_exceptions.py` | 构造/属性/`to_dict()`/cause 链 | `tests/unit/domain/exceptions/test_tool_version_exceptions.py` | Task 2 |
| **TDD 领域异常测试** | 编码唯一性/子域范围/HTTP 映射期望集合 | 全量异常扫描 + `test_exception_handlers.py` 同步 | `tests/unit/domain/exceptions/test_error_code_uniqueness.py` 等既有 8 项 | Task 2 |
| **TDD 单元测试** | InMemory 仓储 | CRUD/唯一性/Query 过滤/活跃版本查询 | `tests/unit/infrastructure/storage/test_inmemory_tool_version_repository.py` | Task 3 |
| **TDD 单元测试** | ToolVersionService | 注册/发布（状态感知）/abort/回滚/路由/保留全流程（Mock 端口工厂模式） | `tests/unit/application/services/test_tool_version_service.py` | Task 4 |
| **TDD 单元测试** | ToolVersionConfig | 默认值/环境变量覆盖/非法值 101 | `tests/unit/infrastructure/config/test_tool_version_config.py` | Task 4 |
| **TDD 单元测试** | ToolExecutionService 版本集成 | 注入路由/派生副本/未注入回退（**新建**——该文件当前不存在） | `tests/unit/application/services/test_tool_execution_service.py` | Task 5 |
| **TDD 单元测试** | tools API 路由 | 端点行为/错误映射/认证 | `tests/unit/interfaces/api/test_tools_api.py` | Task 6 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_tool_version_management.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_tool_version_management.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | `src` 与测试目录完成清单最终确认 | 同 feature/.py | Task 9 |
| **TDD 契约测试** | API 契约 / openapi 接口 | 请求/响应结构、状态码、Header、字段类型 | `tests/contracts/test_api_contract_tools.py` | Task 0→6 |
| **TDD 契约测试** | 端口契约（仓储） | 端口注册、版本、兼容性、实现解析、重复接口检测 | `tests/contracts/test_port_contract_tool_version_repository.py`（11 维度模式） | Task 0→3 |
| **TDD 契约测试** | 端口契约（服务） | 端口注册、版本、兼容性、实现解析、重复接口检测 | `tests/contracts/test_port_contract_tool_version_service.py`（11 维度模式） | Task 0→4（Task 4 循环 C 转绿） |
| **TDD 契约测试** | 事件契约 | 事件默认值/payload 契约 | `tests/contracts/test_event_contract_tool_version_events.py` | Task 2 |
| **TDD 契约测试** | 事件通道映射 | yaml 与 DEFAULT_MAPPINGS 双登记 | `tests/contracts/test_event_channel_mapping_tool_version.py`（debate 先例） | Task 2 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖、禁止跨层引用、端口元数据、事件通道同步 | `tests/unit/architecture/test_tool_version_management.py`（**epics 硬路径，无 `_arch_` 前缀，4.4/4.5 先例**） | Task 8 |
| **集成测试** | PG 仓储 + 全链路 + 性能 | 真实 PostgreSQL Schema 隔离 / savepoint 回滚 / 性能基准 | `tests/integration/test_tool_version_integration.py`（**epics 硬路径**；Task 3 循环 B 建仓储基础用例，Task 7 扩展全链路与性能） | Task 3→7 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **分层覆盖率** - **P1 阻断门禁**（epics 对本 Story 明确要求：应用层 ≥85%、集成测试覆盖率 ≥75%）：
  - 领域层：≥90%（ToolVersion 实体 + 3 个领域服务为新增核心逻辑）
  - 应用层：≥85%（ToolVersionService 编排逻辑，epics 硬指标）
  - 接口层：≥85%（tools API 路由——Story 自加指标，加严方向）
  - 基础设施层：≥75%（PG/InMemory 仓储适配——Story 自加指标，加严方向）
- [ ] **集成测试覆盖率 ≥75%**（epics 硬指标）
- [ ] **关键路径覆盖率 100%**——三组关键路径就地枚举（可映射到具体测试函数）：
  - 状态机全 7 个合法迁移格（8 种触发语义）+ 全部非法迁移抛 243（`test_tool_version.py`）
  - 灰度决策三分支（critical 拒绝 / major canary_only / minor·无破坏 any）（`test_tool_version_policy.py`）
  - 回滚三路径 = ①缺省目标成功 ②显式目标成功 ③失败路径（430/433 各态）（`test_tool_version_service.py`）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`，禁止 `--no-verify` 绕过）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **事务隔离** | PG 集成测试使用 `session.begin()` + `set_session()` + rollback（savepoint 模式） | 数据泄漏导致随机失败 |
| **Schema 自创建** | fixture 内 `Base.metadata.create_all` 或 `ensure_alembic_migration`（模块级单次标志） | 依赖外部迁移，环境不一致 |
| **资源唯一性** | 测试数据使用 UUID 前缀（tool_id 用 `uuid.uuid4()` 而非 catalog 硬编码 UUID，避免与其他测试的 catalog 注册互撞） | ID 冲突或状态污染 |
| **并行隔离** | pytest-xdist 下集成测试若操作共享表用 `pytestmark = pytest.mark.xdist_group("tool-versions-pg")` 串行化（tool-executions-pg 先例） | 并行冲突 |
| **清理粒度** | 每个测试只清理自己创建的资源；**禁止手动 delete/truncate** | 误删其他测试资源 |
| **依赖声明** | Fixture 必须显式声明依赖 | 并行时清理顺序不确定 |
| **asyncio 上下文** | BDD 步骤函数不用 `@pytest.mark.asyncio`，用模块级 `event_loop` fixture + `run_until_complete()` | context 数据丢失 |
| **确定性路由测试** | TrafficRouter 断言用固定 route_key 样本集（`f"key-{i}"`）；断言锚点=按 AC-3 规范公式独立重算（禁 route() 探测同源）；比例统计断言带 ±5% 容差 + weight=100/无灰度边界探针 | 随机散列漂移导致间歇失败；同源断言无判别力 |
| **性能断言分级** | 达标 assert pass；环境不达标 `pytest.skip` 留测量证据 | 慢环境假红 |
| **外部客户端** | LLM/Sandbox Mock 需验证方法存在性（`_make_mock_llm()`/`_make_mock_sandbox()` 工厂先例） | AttributeError |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback）
- ❌ autouse fixture 删除全局匹配资源
- ❌ Fixture 假设清理顺序（必须显式声明依赖）
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`
- ❌ 在 TrafficRouter 中使用内建 `hash()`（进程盐化不稳定，必须 hashlib）

**验证要求：**
- [ ] 并行测试 `poetry run pytest tests/ -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 多版本并存注册 | Task 1 | ToolVersion 聚合根 + 状态机 | `test_tool_version.py` |
| AC-1 | (tool_id,version) 唯一性 | Task 3 | 仓储唯一性 + migration UNIQUE | `test_inmemory_tool_version_repository.py` / `test_tool_version_integration.py` |
| AC-1 | 404/409 异常路径 | Task 2 | 异常 430/431 定义 | `test_tool_version_exceptions.py` |
| AC-2 | 兼容性分级拦截 | Task 4 | register_version 校验编排 | `test_tool_version_service.py` |
| AC-2 | severity→策略纯函数 | Task 1 | RolloutPolicyService | `test_tool_version_policy.py` |
| AC-2 | critical 拒绝（397 复用） | Task 4 | 抛 ToolSchemaCompatibilityError | `test_tool_version_service.py` + BDD |
| AC-3 | 灰度发布流量分配 | Task 1 | TrafficRouter 确定性路由 | `test_tool_version_policy.py` |
| AC-3 | 发布/提升/调档状态机 | Task 4 | publish_version 状态感知 | `test_tool_version_service.py` |
| AC-3 | 放弃灰度 abort_canary | Task 4 | abort_canary + 端点（Task 6） | `test_tool_version_service.py` + `test_tools_api.py` |
| AC-3 | 权重校验（432） | Task 2+4 | 异常定义 + 发布校验 | `test_tool_version_exceptions.py` |
| AC-4 | 一键回滚 | Task 4 | rollback + last_stable_at 语义 | `test_tool_version_service.py` |
| AC-4 | 原子性（savepoint） | Task 3→7 | PG 仓储事务边界（Task 3 建能力，Task 7 验证原子性） | `test_tool_version_integration.py` |
| AC-4 | 保留最近 10 版 | Task 1+4 | VersionRetentionPlanner + 配置 | `test_tool_version_policy.py` + BDD |
| AC-5 | 执行链透明路由 | Task 5 | resolve + dataclasses.replace 派生 | `test_tool_execution_service.py` 新建 |
| AC-5 | 惰性初始版本 | Task 5 | resolve_version 兜底注册 | 同上 + BDD |
| AC-5 | 装配升级 v1.3.0 | Task 5 | composition_root | 契约测试更新 |
| AC-6 | 6 个 REST 端点 | Task 6 | tools.py 路由 + app 挂载 | `test_tools_api.py` |
| AC-6 | openapi 契约 | Task 0→6 | openapi.yaml + 契约测试 | `test_api_contract_tools.py` |
| AC-7 | P95<500ms 切换延迟 | Task 7 | 性能基准 | `test_tool_version_integration.py` |
| AC-7 | 成功率 ≥95%/100% | Task 7 | 操作成功率统计 | 同上 |
| 全部 | 六边形架构合规 | Task 8 | 架构约束验证 | `test_tool_version_management.py` |
| 全部 | 完成清单收尾 | Task 9 | 收尾验收场景 | feature/.py 收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1 ~ AC-7（全部）

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。这是 SDD 规范驱动的基础。

- [x] Subtask 0.1: 定义领域事件 Schema —— `ToolVersionRegistered` / `ToolVersionPublished` / `ToolRolledBack`（字段规范见 SDD 节；继承 DomainEvent，aggregate_type="ToolVersion"）
- [x] Subtask 0.2: 定义数据模型规范 —— `ToolVersion` 聚合根 + `ToolVersionStatus` 状态机 + `ToolVersionQuery` + `RolloutDecision`（字段与迁移矩阵见 SDD 节）
- [x] Subtask 0.3: 端口契约清单定稿 —— 2 个新端口 + 1 个升级端口的 PortSpec 全字段（见端口清单表）
- [x] Subtask 0.4: 领域异常契约定稿 —— tool_version 子域 (430,439) + 4 个新异常 + 复用清单（见异常契约节）
- [x] Subtask 0.5: 创建/更新 `docs/api/openapi.yaml` —— 新增 5 个 `/tools` path + 6 组 Schema（见 API 契约节）
- [x] Subtask 0.6: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_tool_version_management.feature` —— 场景集（AC-x.y 前缀命名）：
  - AC-1.1 多版本并存注册可见 / AC-1.2 重复版本号冲突 409 / AC-1.3 工具不存在 404
  - AC-2.1 critical 拒绝注册 409 / AC-2.2 major 强制灰度（PENDING 直接全量被拒 400）/ AC-2.3 minor 直接全量 / AC-2.4 首版本跳过校验（**判别性构造**：新版本 Schema 若经校验必为 critical——以「注册成功」断言「跳过」本身） / AC-2.5 canary_only 灰度毕业（CANARY 提升为 STABLE 放行——无死锁链路验证）
  - AC-3.1 按比例分配流量 / AC-3.2 旧版本服务剩余流量 / AC-3.3 权重非法 400（含 w=0）/ AC-3.4 灰度转全量提升 / AC-3.5 灰度调档（30→50 渐进放量，状态不变）/ AC-3.6 放弃灰度 abort-canary（STABLE 不动）/ AC-3.7 无 STABLE 请求灰度 400
  - AC-4.1 一键回滚至最近稳定 / AC-4.2 回滚后流量全回目标版本 / AC-4.3 无可回滚版本 409 / AC-4.4 保留策略（先淘汰灰度清场产物[无 last_stable_at]再淘汰最旧曾稳定版）/ AC-4.5 连续两次缺省回滚不 ping-pong / AC-4.6 显式目标不存在 404 与非可回滚态 409 分立
  - AC-5.1 执行命中灰度版本 / AC-5.2 执行路由稳定版本 / AC-5.3 显式指定版本执行 / AC-5.4 执行聚合快照携带实际版本（断言 ToolExecution.tool_version，非 ToolExecuted 事件——见 AC-5 事件边界）/ AC-5.5 惰性初始版本注册（首次执行自动建立 STABLE）
  - AC-6.1~6.6 六端点各一条契约场景（6.1 注册 201 / 6.2 列表 200 / 6.3 发布 200 / 6.4 回滚 200+409 / 6.5 abort-canary 200 / 6.6 traffic 视图 200）+ AC-6.7 无认证 401（201/200/404/409/400 + error.code/message/request_id）
  - AC-7.1 切换延迟 / AC-7.2 灰度发布成功率 / AC-7.3 回滚成功率 / AC-7.4 路由开销——与 AC-7 表四项指标一一对应（分级断言）
  - **场景覆盖分工注记**：SemVer 非法（242）、非法状态迁移（243）由单元测试覆盖（Task 1/4），不入 Gherkin；433 的细分各态（PENDING/CANARY 目标、last_stable_at 为空、目标=当前 STABLE）不入 Gherkin，粗分两码由 AC-4.6 覆盖——避免场景集与单测重复膨胀
- [x] Subtask 0.7: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_tool_version_management.py` —— context dict + `scenarios()` + 模块级 event_loop fixture（**先例在 `test_acceptance_domain_dictionary.py:53` 等 11 个验收文件——第一模板 tool_io 自身不定义该 fixture**，靠 pytest-asyncio 已废弃内建机制，不可照抄）+ 真实服务 given（含 `_make_tool(version=...)` / `_make_mock_llm()` / `_make_mock_sandbox()` 工厂；服务级场景真实服务，HTTP 级 AC-6 场景按认可子模式用服务 `AsyncMock`）
- [x] Subtask 0.8: 编写契约测试（红）—— `tests/contracts/test_api_contract_tools.py`（openapi 静态断言，**Task 0.5 写完 openapi 后该部分即绿——规范先行模式 B 预期**）+ `test_port_contract_tool_version_repository.py` + `test_port_contract_tool_version_service.py`（11 维度类模板：PORT_NAME/IMPL_CLS_NAME/MODULE_PATH/EXPECTED_TAGS/EXPECTED_OWNER/REQUIRED_METHODS 类常量 + `_DummyResolver`——257 行，参照 `test_port_contract_tool.py`）
- [x] Subtask 0.9: 运行验收测试与端口契约测试，确认失败（🔴 红阶段验证；预期失败形态：验收 .py 与端口契约测试 **collection ERROR**（import 的模块不存在）；**API 契约静态断言不在此列**——openapi 已在 0.5 写好，其静态断言 Task 0 即绿属预期中间态，Task 6 路由实现后 TestClient 断言转绿）
- [x] Subtask 0.10: **4.3 遗留缺口实地验证**（关键前置）—— 运行 `src/infrastructure/validation/jsonschema_validator.py` 的 `JsonSchemaValidatorImpl.validate_schema_compatibility` 冒烟验证，三分支预期处置：① 嵌套检测**已实现生效**（Round 1 调研实证 `_check_nested_schema_changes` :340-466 真实调用，4-3 文档 P1-12「仅注释占位」表述已过时）——验证记录实态即可；② **顶层变更双重上报**（主循环与嵌套递归对同一顶层 properties 各计 1 条 breaking_change——实测顶层 type 变更产出 2 条）——记录实态并**确认 AC-2 单测按「存在性+max severity」断言而非计数**（计数非本 Story 契约，不修 4.3 已交付行为）；③ 若发现其他占位/死代码路径（预期不会），在 Task 4 接线前先补齐并补测试。同时验证 **397 现状**：`ToolSchemaCompatibilityError` 已定义+已映射 HTTP 但 src 全库无 raise 点（4-3 P1-13 的「死代码注释」在当前代码不存在）——本 Story 由 ToolVersionService 抛出即为其首个 raise 点；验证结论记录进 Dev Agent Record

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕
- [x] 验收测试运行失败（预期行为，红阶段确认；Task 0 存在"登记先行/实现滞后"的中间态红窗口，不追求虚假全时绿——4-5 先例）
- [x] 4.3 兼容性校验实际行为已验证并记录

---

### Task 1: 领域模型与领域服务

**关联 AC:** AC-1, AC-2, AC-3, AC-4

> **目的：** 纯领域层实现——ToolVersion 聚合根、状态机、三个领域服务（发布策略/流量路由/保留规划）。全部 stdlib，零外部依赖。

#### TDD 循环 A：ToolVersion 聚合根 + 状态机

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/entities/test_tool_version.py`（构造校验：SemVer/schema 关键词/weight 范围 [0,100]/required_rollout_mode 枚举/状态枚举小写值；状态机：**7 个合法迁移格全过**（含 CANARY→CANARY 调档、DEPRECATED→STABLE 回滚恢复；STABLE→DEPRECATED 两支触发语义各测一条）+ 非法迁移抛 EntityStateTransitionError(EXCEPTION_243)；DEPRECATED 化三分戳记规则——被新版本替代记 last_stable_at、被回滚**清空（置 None，含残留戳清除）**、灰度清场不记） |
| 🟢 绿 | 实现 `src/domain/entities/tool_version.py` 最小代码（Tool/ToolExecution 双先例风格：dataclass + `__post_init____ → validate()` + `transition_to()` + `VALID_TRANSITIONS` 模块级矩阵） |
| 🔄 重构 | 类型注解、中文 docstring（Google 风格）、`__init__.py` 导出（若领域实体有集中导出） |

- [x] Subtask 1.1: 🔴 红 — 编写 ToolVersion 失败测试
- [x] Subtask 1.2: 🟢 绿 — 实现 ToolVersion 聚合根
- [x] Subtask 1.3: 🔄 重构 — 优化 ToolVersion 代码

#### TDD 循环 B：领域服务三件套

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_tool_version_policy.py`（RolloutPolicyService：critical→allowed=False / major→canary_only / minor·无破坏→any；TrafficRouter：固定 route_key 样本确定性（断言锚点=按 AC-3 规范公式独立重算，禁 route() 探测同源）+ 1000 固定样本 `f"key-{i}"` 30%±5% 统计 + weight=100/无灰度两个边界探针 + 无 canary 回 stable；VersionRetentionPlanner：总数>10 仅淘汰 DEPRECATED（先 last_stable_at 为空者再最旧者）+ STABLE/CANARY/PENDING 受保护 + 不足 10 不淘汰） |
| 🟢 绿 | 实现 `src/domain/services/tool_version_policy.py`（RolloutPolicyService / TrafficRouter（**hashlib 稳定散列，禁内建 hash()**）/ VersionRetentionPlanner + RolloutDecision 值对象） |
| 🔄 重构 | 纯函数化、类型注解、docstring |

- [x] Subtask 1.4: 🔴 红 — 编写领域服务失败测试
- [x] Subtask 1.5: 🟢 绿 — 实现三个领域服务
- [x] Subtask 1.6: 🔄 重构 — 优化领域服务代码

**完成标准/Definition of Done:**
- [x] ToolVersion + 三服务实现完成，domain 层零外部依赖（AST 验证待 Task 8 统一做）
- [x] TDD 循环全部通过
- [x] 领域层覆盖率 ≥90%（本 Task 新增代码）

---

### Task 2: 领域事件与异常体系

**关联 AC:** AC-2, AC-3, AC-4

> **目的：** 3 个领域事件 + tool_version 子域 4 个异常 + 全链路登记（双通道配置 + 编码注册 + HTTP 映射 + 期望集合同步）。**登记类配置全部在本 Task 完成，避免实现 Task 混入多职责（4-1a Task 8 爆 P0 教训）。**

#### TDD 循环 A：领域事件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/events/test_tool_version_events.py` + `tests/contracts/test_event_contract_tool_version_events.py`（字段默认值/payload 契约/event_type 命名） |
| 🟢 绿 | 实现 `src/domain/events/tool_version_events.py`（3 事件，继承 DomainEvent）+ `src/domain/events/__init__.py` 导出 |
| 🔄 重构 | docstring、payload 精简（防撑爆 Redis：列表类字段 ≤10 条，4-3 P0-H 先例） |

- [x] Subtask 2.1: 🔴 红 — 编写事件失败测试
- [x] Subtask 2.2: 🟢 绿 — 实现 3 个事件 + 导出
- [x] Subtask 2.3: 🔄 重构 — 优化事件代码

#### TDD 循环 B：异常体系 + 登记

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_tool_version_exceptions.py`（4 异常：继承链/code 430-433/context 字段/to_dict()；parametrize 子域归属）——此时模块不存在，红 |
| 🟢 绿 | 实现 `src/domain/exceptions/tool_version_exceptions.py` + 四处登记：`_code_ranges.py`（CODE_RANGES + _CLASS_TO_SUBDOMAIN）+ `src/domain/exceptions/__init__.py` + `exception_handlers.py` EXCEPTION_HTTP_MAP（430→404/431→409/432→400/433→409，**注释与 code 对齐**）+ `sisys-uni-exception-design.md §3.3.2` 分配表；同步扩展 `tests/unit/interfaces/api/test_exception_handlers.py` 期望集合 |
| 🔄 重构 | 运行异常全量测试（`pytest tests/unit/domain/exceptions/ tests/unit/interfaces/api/test_exception_handlers.py -v`）确认 8 项既有测试仍绿 |

- [x] Subtask 2.4: 🔴 红 — 编写异常失败测试
- [x] Subtask 2.5: 🟢 绿 — 实现 4 异常 + 五处登记 + 期望集合同步
- [x] Subtask 2.6: 🔄 重构 — 全量异常测试回归

#### TDD 循环 C：事件通道双登记

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 新建 `tests/contracts/test_event_channel_mapping_tool_version.py`（**专测落点，参照 `test_event_channel_mapping_debate.py` 先例**——不落在 Task 8 架构测试文件，避免与 8.1「创建」叙述冲突）：断言 3 事件在 `configs/event_channels.yaml` 与 `channel_router.py DEFAULT_MAPPINGS` 中均有映射 |
| 🟢 绿 | 两处配置同步新增（realtime 通道，参照 ToolSchemaValidationFailed 条目格式） |
| 🔄 重构 | yaml 格式与相邻条目一致性检查 |

- [x] Subtask 2.7: 🔴 红 — 通道同步断言失败确认
- [x] Subtask 2.8: 🟢 绿 — 双登记完成
- [x] Subtask 2.9: 🔄 重构 — 配置格式统一

**完成标准/Definition of Done:**
- [ ] 事件契约测试 + 异常 8 项既有测试全绿
- [x] `grep -r "EXCEPTION_43[0-9]" src/domain/exceptions/` 无碰撞
- [x] 事件通道双登记完成

---

### Task 3: 仓储端口与存储双实现

**关联 AC:** AC-1, AC-4

> **目的：** R1 领域基础端口 + R3 基础设施双实现（InMemory + PostgreSQL）+ migration 016 + 组合根注册。

#### TDD 循环 A：端口 + InMemory 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/test_inmemory_tool_version_repository.py`（save/get_by_id/get_by_tool_and_version/list_by_query（Query 全字段过滤+分页）/count/list_active（CANARY+STABLE）/delete；(tool_id,version) 唯一性抛 431；**单 STABLE/单活跃 CANARY 不变量守护**（save 第二个同状态版本拒绝，抛 432 并存冲突族）；Protocol runtime_checkable） |
| 🟢 绿 | 实现 `src/domain/ports/tool_version_repository.py`（端口 + ToolVersionQuery，继承 L2RdbPort[ToolVersion] 先例）+ `src/infrastructure/storage/inmemory/tool_version_repository.py` |
| 🔄 重构 | 索引结构优化（`_by_id: dict` + `_by_tool_version: dict[tuple]` 双索引，InMemoryToolRepository 先例） |

- [x] Subtask 3.1: 🔴 红 — 编写端口与 InMemory 失败测试
- [x] Subtask 3.2: 🟢 绿 — 实现端口 + InMemory 仓储
- [x] Subtask 3.3: 🔄 重构 — 双索引优化

#### TDD 循环 B：PostgreSQL 实现 + migration 016

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_tool_version_integration.py` 的仓储基础用例（真实 PG：CRUD/唯一约束/Query/活跃查询；**唯一约束断言口径 = 仓储转换后的领域异常**——(tool_id,version) 冲突 431、partial index 冲突 432（并发守卫单测直连构造），非原生 IntegrityError；`repo_session` fixture = begin + set_session + rollback 隔离模式，探活失败 pytest.skip） |
| 🟢 绿 | 实现 `src/infrastructure/storage/postgresql/models/tool_version.py`（SQLAlchemy 模型）+ `src/infrastructure/storage/postgresql/repository/tool_version_repository.py`（继承 PostgreSQLAdapter 泛型基类：`pk_column`/`_to_entity`/`_to_model` + list_by_query/_apply_filters 扩展，SchemaValidationRecordRepository 先例）+ `deploy/postgresql/alembic/versions/016_tool_versions.py`（revision="016", down_revision="015"；表结构见 Dev Notes；UNIQUE(tool_id,version) + **2 个 partial unique index（单 STABLE/单 CANARY 并发守护，011 已有 partial index 先例）** + 2 普通索引 + CHECK 约束） |
| 🔄 重构 | JSONB ↔ dict 转换、时区处理（DateTime(timezone=True)） |

- [x] Subtask 3.4: 🔴 红 — 编写 PG 仓储集成测试（红：模型/仓储/migration 不存在）
- [x] Subtask 3.5: 🟢 绿 — 实现模型 + 仓储 + migration 016
- [x] Subtask 3.6: 🔄 重构 — 转换层优化

#### TDD 循环 C：组合根注册 + 契约测试转绿

| 阶段 | 动作 |
|------|------|
| 🔴 红 | Task 0 编写的 `test_port_contract_tool_version_repository.py` 运行确认红（端口未注册） |
| 🟢 绿 | `src/composition_root.py` 注册 `tool_version_repository`（v1.0.0, SCOPED, owner="tool-team", tags=(tool,version,repository,postgresql,sqlalchemy)，impl 为 **lambda 工厂**——composition_root 全部条目均为 lambda 而非字符串 impl，契约测试维度 9 的 `callable(spec.impl)` 依赖它；参照 tool_execution_repository 条目 L2259-2271 格式）；端口契约测试转绿 |
| 🔄 重构 | 注册条目注释与相邻条目风格统一 |

- [x] Subtask 3.7: 🔴 红 — 契约测试失败确认
- [x] Subtask 3.8: 🟢 绿 — 注册完成、契约测试通过
- [x] Subtask 3.9

**完成标准/Definition of Done:**
- [x] InMemory + PostgreSQL 双实现 + migration 016 就绪
- [x] 端口契约测试 11 维度全绿
- [x] `poetry run alembic -c deploy/postgresql/alembic/alembic.ini upgrade head` 成功（015→016）

---

### Task 4: 应用层版本管理服务

**关联 AC:** AC-1, AC-2, AC-3, AC-4

> **目的：** R2 组合注入的核心编排服务——注册（含兼容性拦截）/ 发布（灰度/全量/提升）/ 回滚 / 保留策略执行。

#### TDD 循环 A：ToolVersionServicePort + ToolVersionService

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_tool_version_service.py`（Mock 工厂模式：`MagicMock(spec=ToolVersionRepositoryPort)` + `_make_repo_mock()` + `_make_registry_mock()` + `_make_validator_mock()` 工厂；覆盖：register（431 重复/380 工具不存在/397 critical 拦截且 context 带 breaking_changes——**断言存在性与 max severity，不断言条数**/canary_only 标记/首版本跳过校验）、publish 状态感知（PENDING 发起灰度 w∈(0,100)/PENDING 无 STABLE 灰度 432/PENDING canary_only 直接全量 432/PENDING any 直接全量/CANARY 调档 w∈(0,100) 状态不变/CANARY promote w=100（canary_only 放行——毕业通道）/权重越界含 w=0 → 432/其他版本灰度并存 432/243 非法迁移（STABLE·DEPRECATED 上 publish）/全量档旧 STABLE 降级记录 last_stable_at）、abort_canary（成功清场不记 last_stable_at/无活跃 CANARY 243）、rollback（缺省 target=last_stable_at 最新且排除 from_version——连续两次不 ping-pong/回滚降级 current **清空戳（置 None，含残留戳清除——指针原则）**/显式目标不存在 430/非可回滚态 433/无 STABLE 433/清场 CANARY 不记戳 weight 置 0）、resolve（精确 430/确定性路由/惰性初始版本三分支：无记录注册、并发 431 容错重读、有记录无活跃 430）、retention（第 11 版仅淘汰 DEPRECATED，先无 last_stable_at 者再最旧者）。**单元层不写"原子"断言**——多行变更原子性唯一归属 Task 7 savepoint 集成测试，单元层仅断言全部 save 调用发生 + 失败路径不发布事件） |
| 🟢 绿 | 实现 `src/application/ports/tool_version_service.py` + `src/application/services/tool_version_service.py`（编排流程见 Dev Notes「核心编排流程」节；schema_validator 调用输入+输出双 Schema） |
| 🔄 重构 | 决策提纯（severity 摘要提取 → RolloutPolicyService）、类型注解 |

- [x] Subtask 4.1: 🔴 红 — 编写服务失败测试
- [x] Subtask 4.2: 🟢 绿 — 实现端口 + 服务
- [x] Subtask 4.3: 🔄 重构 — 编排与决策分离优化

#### TDD 循环 B：ToolVersionConfig 配置

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/config/test_tool_version_config.py`（默认 max_retained_versions=10；TOOL_VERSION_MAX_RETAINED 环境变量覆盖；非法值抛 ConfigurationError(EXCEPTION_101)） |
| 🟢 绿 | 实现 `src/infrastructure/config/tool_version.py`（frozen dataclass + from_env() 抄 SandboxConfig 形态；**注意 SandboxConfig 本身未走 `__init__.py` 导出**——ToolVersionConfig 按 11 个已导出配置类的多数惯例加入 `__init__.py`） |
| 🔄 重构 | `__repr__` 脱敏检查 |

- [x] Subtask 4.4: 🔴 红 — 编写配置失败测试
- [x] Subtask 4.5: 🟢 绿 — 实现配置类
- [x] Subtask 4.6: 🔄 重构 — 配置代码优化

#### TDD 循环 C：服务注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `test_port_contract_tool_version_service.py` 确认红 |
| 🟢 绿 | composition_root 注册 `tool_version_service`（工厂 lambda 注入 resolver.resolve("tool_version_repository") + "schema_validator" + "tool_registry_service" + `max_retained_versions=ToolVersionConfig.from_env().max_retained_versions` 标量——组合根 import infrastructure 配置类合法（组合根是装配层），应用层服务只收 int；tool_registry_service 条目 L2238-2252 格式）；契约测试转绿 |
| 🔄 重构 | 注册条目风格统一 |

- [x] Subtask 4.7: 🔴 红 — 契约测试失败确认
- [x] Subtask 4.8: 🟢 绿 — 注册完成
- [x] Subtask 4.9: 🔄 重构 — 风格统一

**完成标准/Definition of Done:**
- [x] ToolVersionService 七方法全部实现且测试通过
- [x] 应用层覆盖率 ≥85%（epics 硬指标）
- [x] 端口契约测试 11 维度全绿

---

### Task 5: 执行链集成

**关联 AC:** AC-5

> **目的：** 版本路由接入执行链——最小侵入设计：ToolExecutionService 组合注入 + dataclasses.replace 派生副本，引擎/装饰器零改动。

#### TDD 循环 A：ToolCall.version + 服务集成

| 阶段 | 动作 |
|------|------|
| 🔴 红 | **新建** `tests/unit/application/services/test_tool_execution_service.py`（**该文件当前不存在**——单元层无既有同名文件，Mock 工厂模式先例取 `test_input_output_validator_chain.py:42-62` 的 `_make_tool()/_make_context()/_make_tool_call()`；含 TestToolVersionIntegration 测试类：注入 version service → 命中 canary 路由且 engine 收到的 Tool 副本 version/schema 已替换；route_key 未命中 → stable schema；ToolCall.version 显式 → 精确版本且跳过路由；未注入 → 原行为回归；惰性初始版本注册三分支） |
| 🟢 绿 | 修改 `src/domain/value_objects/tool_execution.py`（ToolCall 加 `version: str | None = None`，frozen 带默认向后兼容）+ `src/application/services/tool_execution_service.py`（`__init__` 加 `tool_version_service: ToolVersionServicePort | None = None` 可选参数；execute 内 get_tool 后注入路由 + 派生副本） |
| 🔄 重构 | 派生逻辑提纯为私有方法 `_resolve_execution_tool()` |

- [x] Subtask 5.1: 🔴 红 — 编写执行链集成失败测试
- [x] Subtask 5.2: 🟢 绿 — 实现 ToolCall.version + 服务集成
- [x] Subtask 5.3: 🔄 重构 — 路由逻辑提纯

#### TDD 循环 B：装配升级 v1.3.0

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 更新 `tests/contracts/test_port_contract_tool_execution_service.py` 期望（version v1.3.0 + tags 含 "versioned" + compatibility 含 "v1.2.0"）→ 红 |
| 🟢 绿 | composition_root `tool_execution_service` 条目升级（**L2294 起，终审核准**；终审留项修正：原文档 L2316-2352 系对含临时未提交改动的工作区核验所致漂移——dev 一律以端口名 grep 定位）：工厂追加 `tool_version_service=resolver.resolve("tool_version_service")`，version v1.2.0→v1.3.0，tags += ("versioned",)，compatibility=("v1.2.0",)（4-3 P0-A 修复先例：改装配链必须升级 version 并同步契约测试） |
| 🔄 重构 | 装配注释更新（链路描述补 version router 层） |

- [x] Subtask 5.4: 🔴 红 — 契约期望更新后红
- [x] Subtask 5.5: 🟢 绿 — 装配升级完成
- [x] Subtask 5.6: 🔄 重构 — 注释同步

**完成标准/Definition of Done:**
- [ ] ToolExecutionEngine / ToolOutputValidator / SandboxSecurityDecorator 源码零修改（git diff 验证）
- [x] ToolExecutionService 向后兼容回归绿——**真实回归锚**：`tests/acceptance/test_acceptance_tool_io_schema_validation.py:121`（构造真实 `ToolExecutionService(registry, engine)`）+ `test_input_output_validator_chain.py` + `test_port_contract_tool_execution_service.py` 全部仍绿
- [x] tool_execution_service v1.3.0 契约测试通过

---

### Task 6: REST API 接口层

**关联 AC:** AC-6

> **目的：** R4 接口适配——tools 路由工厂 + openapi 契约对齐 + app 挂载。

#### TDD 循环 A：tools 路由

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/api/test_tools_api.py`（TestClient + `AsyncMock(spec=ToolVersionServicePort)` + get_current_user_override：6 端点正常路径 + 404(380/430)/409(431/397/433/243)/400(432/242) 错误映射 + 401 无认证 + 响应模型字段） |
| 🟢 绿 | 实现 `src/interfaces/api/tools.py`（`create_tools_router(tool_version_service=None, auth_service=None, get_current_user_override=None)`，prefix `/api/v1/tools`，tags ["tools"]；Pydantic schema 定义在路由文件内——domain_dictionary 先例（该文件工厂实名 `create_document_dictionary_router`）；三级降级认证；`_to_version_response()` 显式映射 helper）+ `app.py create_app()` 挂载（**挂载漏写无报错**——契约测试须含 6 端点存在性断言兜底，auth.py 等 5 个路由未挂载是既有前车之鉴） |
| 🔄 重构 | 响应转换统一、状态码语义复查 |

- [x] Subtask 6.1: 🔴 红 — 编写 API 失败测试
- [x] Subtask 6.2: 🟢 绿 — 实现路由工厂 + 挂载
- [x] Subtask 6.3: 🔄 重构 — 响应层优化

#### TDD 循环 B：API 契约测试转绿

| 阶段 | 动作 |
|------|------|
| 🔴 红 | Task 0 的 `test_api_contract_tools.py` 当前状态确认（规范断言应已绿——Task 0.5 已写 openapi；若含 TestClient 部分则红） |
| 🟢 绿 | 路由实现后全部断言通过（openapi 静态断言 + 端点存在性） |
| 🔄 重构 | 契约断言与 openapi.yaml 的 schema 引用一致性 |

- [x] Subtask 6.4: 🔴 红 — 契约测试状态确认
- [x] Subtask 6.5: 🟢 绿 — 契约测试全绿
- [x] Subtask 6.6: 🔄 重构 — 契约断言精炼

**完成标准/Definition of Done:**
- [ ] 6 端点全部可用且经认证
- [x] API 契约测试通过
- [x] 接口层覆盖率 ≥85%

---

### Task 7: 集成测试与性能基准

**关联 AC:** AC-1, AC-3, AC-4, AC-7

> **性质说明：** 真实服务集成（PostgreSQL Schema 隔离 + InMemory 全链路）+ epics 硬路径文件 + 性能指标验证。

- [x] Subtask 7.1: 完成 `tests/integration/test_tool_version_integration.py` PG 部分（Task 3 已建基础用例）：发布/回滚多行状态变更原子性（savepoint 内）、UNIQUE 约束真实生效、版本保留策略真实淘汰、`pytestmark = pytest.mark.xdist_group("tool-versions-pg")`
- [x] Subtask 7.2: 全链路集成场景：真实 InMemory 仓储 + JsonSchemaValidatorImpl + ToolRegistryService + ToolVersionService + ToolExecutionService（LLM/Sandbox Mock 适配器）——注册→灰度→执行（命中/未命中）→提升→回滚闭环
- [x] Subtask 7.3: 性能基准（AC-7 表格逐项）：50 次 publish+rollback P95（`statistics.quantiles(n=20)[18]`；**构造约束：每轮消耗新版本号**——回滚降级版本为 DEPRECATED 再 publish 会 243，复用版本号第二轮即失败，register 构造开销不计入计时窗口）；50 次发布成功率；回滚 100% 原子；1000 次 resolve P95<5ms（**InMemory 装配断言**；PG 装配 skip 留测量证据并附单次 list_active 往返参考值）；全部采用性能断言分级（不达标 skip 留证据）
- [x] Subtask 7.4: 连续运行 5 次无随机失败 + `pytest tests/ -n 8` 并行通过

**完成标准/Definition of Done:**
- [ ] 集成测试覆盖率 ≥75%（epics 硬指标）
- [x] 性能指标全部有测量证据
- [x] 无随机失败

---

### Task 8: SDD 架构约束验证测试

**关联 AC:** 全部 AC（架构合规）

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [x] Subtask 8.1: 创建 `tests/unit/architecture/test_tool_version_management.py`（**epics 硬路径**，4.4/4.5 先例无 `_arch_` 前缀）
- [x] Subtask 8.2: 实现领域零依赖验证器（AST 扫描 tool_version 相关 domain 文件禁止外部 import——pydantic/sqlalchemy/redis/fastapi/pytest/httpx/aiohttp，`test_arch_tool.py` 先例）
- [x] Subtask 8.3: 实现端口元数据验证器（`_global_registry.get("tool_version_repository")` / `("tool_version_service")` 的 PortSpec 全字段断言 + tool_execution_service v1.3.0 断言）
- [x] Subtask 8.4: 实现事件通道同步验证器（3 事件在 event_channels.yaml 与 ChannelRouter.DEFAULT_MAPPINGS 双登记）
- [x] Subtask 8.5: 实现执行链零改动验证（ToolExecutionEngine/ToolOutputValidator/SandboxSecurityDecorator 无版本路由代码——import 检查：不 import tool_version_service）
- [x] Subtask 8.6: 运行完整测试套件并生成合规报告（任何违规 pytest.fail）

**完成标准/Definition of Done:**
- [ ] 所有架构/约束测试通过
- [ ] 每条断言失败消息包含违规文件路径与违规 import/元数据项（pytest.fail 消息可定位到文件）
- [x] 任何违规都会导致测试失败
- [x] 循环依赖检测使用 ruff/isort（不引入额外工具）

---

### Task 9: 开发结束验收测试

**关联 AC:** 全部 AC（收尾）

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_acceptance_tool_version_management.feature` 中的收尾验收场景（src 完成清单 / tests 完成清单逐项确认） |
| 🟢 绿 | 编写 `.py` 的 BDD 步骤实现（文件存在性 + 导入性断言） |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [x] Subtask 9.1: 场景 1 — 验证 `src` 完成清单的逐项确认（本 Story 文件清单「待创建」全部存在且可导入）
- [x] Subtask 9.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单的逐项确认
- [x] Subtask 9.3: 运行开发结束验收测试并确认通过
- [x] Subtask 9.4: 运行 `pytest`、`ruff check`、`mypy` 进行收尾校验（三条异常自查 grep 零输出：`grep -rn "raise ValueError" src/`、`grep -rn "HTTPException" src/interfaces/api/tools.py | grep -v "401"`（**可执行豁免口径**：过滤认证 401 行——domain_dictionary 先例 :161/211/223 本就有 3 处认证 HTTPException，其余零输出）、`grep -rn "noqa\|type: ignore\|pylint: disable" src/`）

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [x] `tests` 四目录完成清单已逐项验证确认
- [x] 开发结束验收测试通过
- [x] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md) + [`sisys-core-domain-design.md §17.2`](../../../docs/architecture/sisys-core-domain-design.md) + [`sisys-port-management-design.md`](../../../docs/architecture/sisys-port-management-design.md)

- **架构模式:** 六边形架构（Ports & Adapters）、DDD 聚合根、领域事件双通道（realtime Redis + reliable RabbitMQ）、装饰器执行链
- **设计约束:** 领域层零依赖（import-linter 强制）；依赖方向 domain ← application ← interfaces/infrastructure；端口统一注册 PortSpec（name/version/interface/impl/module/lifetime/owner/compatibility/tags/deprecated 十字段）；Query Object 模式（多字段+分页查询）
- **存储架构:** Tool 实体设计为 **L2（PostgreSQL）+ L1（Redis）**（architecture.md §9）——本 Story 落地 L2 持久化（migration 016）；L1 缓存非本 Story 范围（**PG 装配下 resolve_version 每次执行含一次 list_active DB 往返**——有意取舍：路由查询走 (tool_id,status) 索引代价可控，进程内路由快照缓存（事件失效型）留有真实性能诉求时追加；AC-7 路由开销基准相应分层）
- **接口治理:** 统一端口注册、契约优先、版本化兼容（tool_execution_service 升级示范）、禁止跨模块直接依赖实现类
- **技术栈:** Python 3.11+ / SQLAlchemy 2.0 async / alembic / FastAPI / pytest-bdd 8.1.0（pyproject `^8.0.0`）/ jsonschema Draft 7（复用 4.3 的 JsonSchemaValidatorImpl）

### 关键架构决策

| # | 方案 | 优点 | 缺点 | 评分 |
|---|------|------|------|------|
| 1 | **ToolVersion 独立聚合根**（Tool 元数据不动） | ToolRepositoryPort 零改动；语义清晰（工具 vs 版本）；避免破坏 `_tools_by_name` 唯一性 | 需 join 语义（resolve 时以 ToolVersion 为准） | ✅ 9/10 |
|   | Tool 实体内嵌版本列表 | 单聚合查询 | 破坏 Tool 不变量；TOOL_CATALOG 23 实例全需改；save 同名冲突语义崩坏 | 4/10 |
| 2 | **确定性流量路由（hashlib 稳定散列）** | 可测试（同 key 同结果）；统计可验证；无随机漂移 | 无法精确控制恰好 N% | ✅ 9/10 |
|   | 加权随机（random） | 简单 | 断言无判别力（4-5 教训）；不可复现 | 3/10 |
|   | hash_router 加权一致性哈希复用 | 现成设施 | 语义是节点路由非版本灰度；引入不必要耦合 | 5/10 |
| 3 | **指针切换回滚**（状态翻转，非快照重建） | O(1) 操作；无数据复制；last_stable_at 精确候选 | 需要"曾稳定"标记字段 | ✅ 9/10 |
|   | 词典式快照重建（domain_dictionary 先例） | 全量快照 | 版本本身已是快照，重建冗余；10 版保留语义不匹配 | 5/10 |
| 4 | **执行链服务层注入 + dataclasses.replace 派生副本** | 引擎/装饰器零改动；ToolExecution 聚合快照自动带实际版本（事件字段不自动变——见 AC-5 事件边界）；向后兼容（可选注入） | Tool 副本非聚合根身份（仅执行视图，可接受） | ✅ 9/10 |
|   | 引擎层改造（execute 接收 ToolVersion） | 类型更显式 | engine + 2 装饰器 + 全部测试连坐改动，违反最小侵入 | 4/10 |
|   | 新装饰器 ToolVersionRouter 包裹最外层 | 4-4 "就地嵌套"先例 | 装饰器包裹的是 Port 层，需新端口定义，过度设计 | 6/10 |
| 5 | **PG 为主注册实现 + InMemory 测试直连**（schema_validation_record_repository 先例） | 与 4.1a/4.3 仓储模式一致；灰度配置重启不丢 | bootstrap 时 PG 不可用需惰性兜底（已设计：resolve 惰性注册） | ✅ 8/10 |
|   | 仅 InMemory（tool_repository 现状） | 零 migration | 灰度/回滚状态重启即失——违背"异常版本可快速恢复"的业务价值 | 3/10 |
| 6 | **新子域段 tool_version (430,439)** | 不与 4.7 的 399/400-409 计划冲突；预留 6 位扩展 | 新增子域登记成本 | ✅ 9/10 |
|   | 挤用 tool 段 384 保留位 / toolchain 399 | 零登记 | 位数不够（需 4 个）；与 4.7 预占冲突 | 2/10 |
| 7 | **canary_only 仅拦"直接全量"，promote 放行**（Flagger/Argo Rollouts 灰度毕业语义） | major 版本有毕业通道，无死锁；审计用 from_status 区分 | 拦截规则带状态条件（非单纯 mode 判断） | ✅ 9/10 |
|   | canary_only 无条件禁 w=100（v1.0.0 原案） | 规则简单 | **死锁**：major 版本终身 CANARY 且永久占用唯一灰度位，绿地场景全 API 锁死 | 2/10 |
| 8 | **CANARY→CANARY 调档同态迁移 + abort_canary 操作**（渐进放量/放弃灰度，业界灰度四动词：切流→观察→调档→promote/abort） | 运维完整；abort 清场不动 STABLE（Flagger abort 语义） | 状态机多 1 条同态迁移 + 1 方法 1 端点 | ✅ 9/10 |
|   | 单档定格（v1.0.0 原案：灰度发起后仅 promote/回滚两路） | 状态机更简 | 无渐进放量路径；灰度失败只能整体回滚（误伤 STABLE） | 3/10 |
| 9 | **缺省回滚目标排除 from_version**（防 ping-pong；业界 stable 指针只在成功 promotion 时推进） | 连续回滚逐版本后退，不回到刚放弃的故障版本 | 目标选取多一个排除条件 | ✅ 9/10 |
|   | last_stable_at 全局取最大（v1.0.0 原案） | 规则简单 | 被回滚版本获得最新时间戳，连按两次回到故障版本 | 4/10 |
| 10 | **PG partial unique index 守护单 STABLE/单 CANARY**（存储层硬约束） | 并发下不变量不破；rollback/resolve 单数假设安全 | InMemory 需另做软校验（双实现不对齐风险由单测覆盖） | ✅ 9/10 |
|   | 仅服务层校验（v1.0.0 原案） | 零 DDL | SCOPED 实例无锁，并发 publish 可产生双 STABLE，下游单数假设塌陷 | 3/10 |

### 核心编排流程（ToolVersionService 实现蓝图）

```
register_version(tool_id, version, input_schema, output_schema):
  1. tool_registry.get_tool(tool_id=tool_id)          # 380 if 不存在
  2. repo.get_by_tool_and_version(tool_id, version)    # 431 if 已存在
  3. stable = repo.list_active(tool_id) 中 status==STABLE 者（至多 1 个——partial unique index 守护）
  4. 若 stable 存在:
     compat_in  = schema_validator.validate_schema_compatibility(stable.input_schema,  input_schema)   # ≈backward
     compat_out = schema_validator.validate_schema_compatibility(stable.output_schema, output_schema)  # ≈forward
     摘要 = max_severity(compat_in, compat_out)        # 双 Schema severity 取最大；breaking 计数不作决策输入
                                                        #（4.3 校验器顶层变更存在双重上报实态，计数非稳定契约）
     decision = RolloutPolicyService.decide(摘要)      # 领域纯函数
     if not decision.allowed: raise ToolSchemaCompatibilityError(tool_id, old, new, breaking_changes)  # 397
                                                        # breaking_changes = compat_in/compat_out 双结果中
                                                        # critical 条目的合并清单（context 携带）
  else: decision = RolloutDecision(any)                # 首版本
  5. tv = ToolVersion(PENDING, required_rollout_mode=decision.mode, ...)
  6. repo.save(tv)
  7. retention: VersionRetentionPlanner.plan(repo.list_by_query(该 tool 全部版本), self._max_retained_versions)
     → 仅淘汰 DEPRECATED，两级排序：第一级 无戳组（last_stable_at 为空的清场产物）优先于带戳组（曾稳定版）；
       第二级 组内排序键——无戳组按 created_at 升序（平局裁决键），带戳组按 last_stable_at 升序
       （淘汰键与回滚价值键对齐；两组排序键不同，各自最旧者先淘汰）→ repo.delete(淘汰)
  8. publish ToolVersionRegistered

publish_version(tool_id, version, traffic_weight=100):   # 状态感知：PENDING=发起/直接全量；CANARY=调档/转正
  0. tool_registry.get_tool(tool_id=tool_id)                    # 380 if 不存在
  1. tv = repo.get_by_tool_and_version(...)            # 430 if 不存在
  2. 0 < weight <= 100 else 432
  3. weight < 100（灰度档）:
       tv.status==PENDING: 无 STABLE 存在 → 432（灰度前置）；活跃 canary 存在且 != tv → 432
                            → tv.transition_to(CANARY)（PENDING→CANARY 发起灰度）
       tv.status==CANARY: 调档（同态迁移 CANARY→CANARY，仅更新 weight；此时活跃 canary 必 == tv）
       tv.status ∈ {STABLE, DEPRECATED}: transition_to 抛 243（非法迁移）
     weight == 100（全量档）:
       tv.status==PENDING 且 mode=="canary_only" → 432（禁止直接全量）
       tv.status==PENDING 且 mode=="any" → tv.transition_to(STABLE)（直接全量）
       tv.status==CANARY → tv.transition_to(STABLE)（promote 转正——canary_only 灰度毕业通道，放行）
       全量档同时：旧 STABLE.transition_to(DEPRECATED) 并记录 last_stable_at（曾全量服务标记）；
       新 STABLE 的 traffic_weight 置 100（数据卫生——与「STABLE 语义恒 100」一致）
  4. repo.save（多行变更在同一 session 事务/savepoint 内；**保存顺序：先 save 降级行（旧 STABLE），
     后 save 提升行（新 STABLE）——partial unique index 逐语句校验，反序必撞单 STABLE 索引；InMemory 同序**）
  5. publish ToolVersionPublished(from_status, to_status, weight)

abort_canary(tool_id):                                   # 放弃灰度：STABLE 不动、流量全回 STABLE
  0. tool_registry.get_tool(tool_id=tool_id)                    # 380 if 不存在
  1. active = repo.list_active(tool_id)；canary = status==CANARY 者
  2. canary 不存在 → 243（无合法迁移）
  3. canary.transition_to(DEPRECATED)（不记 last_stable_at）；weight 置 0
  4. repo.save；publish ToolVersionPublished(from=CANARY, to=DEPRECATED, weight=0)

rollback(tool_id, target_version=None, trigger="api"):
  0. tool_registry.get_tool(tool_id=tool_id)                    # 380 if 不存在
  1. current = repo.list_active(tool_id) 中 STABLE 者；无 STABLE → 433（无可回滚）
  2. target 缺省 = list_by_query(status=DEPRECATED, last_stable_at 非空) 中 last_stable_at 最大者
     且排除 current.version（防御：current 若带历史戳也排除自身）；无 → 433
     target 显式 = repo.get_by_tool_and_version(...)；记录不存在 → 430；非 DEPRECATED 或 last_stable_at 为 None → 433
  3. current.transition_to(DEPRECATED) 且**清空 last_stable_at（置 None——含 promote 期残留戳
     清除；指针原则：只在成功 promotion 时推进。跨步/连按/第三次的 ping-pong 均不可达）；
     weight 置 0
     活跃 CANARY → DEPRECATED（不记 last_stable_at，weight 置 0）
     target.transition_to(STABLE)（DEPRECATED→STABLE 回滚恢复迁移，唯一合法触发方）
  4. repo.save ×N（同一事务/savepoint；**保存顺序：先降级/清场行（current、CANARY），后提升行
     （target）——partial unique index 逐语句即时校验，反序在事务内即撞单 STABLE 索引**）
  5. publish ToolRolledBack(trigger, deprecated_versions=[...])

resolve_version(tool_id, requested_version=None, route_key=None):
  1. requested_version 指定 → repo.get_by_tool_and_version 精确；不存在 → 430
  2. active = repo.list_active(tool_id)；canary, stable = 拆分
  3. canary 存在（灰度前置校验保证 stable 同时存在）→
     TrafficRouter.route(route_key, canary.version, canary.traffic_weight, stable.version)
  4. 仅 stable → stable
  5. active 为空 且 未指定版本:
     无任何版本记录（count==0）→ 惰性：tool = tool_registry.get_tool(tool_id)（380 自然传播）
       → 以 tool.version / tool.input_schema / tool.output_schema 构造 STABLE 记录
       （幂等：并发撞 431 时捕获重读返回既有）→ 返回
     有版本记录但全非活跃 → 430（无活跃版本可路由）
```

### 数据库表设计（migration 016: `tool_versions`）

```
version_id        UUID PK
tool_id           UUID NOT NULL                      -- 无 FK（011 先例：等 tools 表落地后补强，文件头注释说明）
version           VARCHAR(20) NOT NULL               -- SemVer
input_schema      JSONB NOT NULL DEFAULT '{}'
output_schema     JSONB NOT NULL DEFAULT '{}'
status            VARCHAR(16) NOT NULL CHECK (status IN ('pending','canary','stable','deprecated'))
traffic_weight    INTEGER NOT NULL DEFAULT 0 CHECK (traffic_weight BETWEEN 0 AND 100)
required_rollout_mode VARCHAR(16) NOT NULL DEFAULT 'any' CHECK (required_rollout_mode IN ('any','canary_only'))
last_stable_at    TIMESTAMPTZ NULL
created_at        TIMESTAMPTZ NOT NULL server_default=now()
updated_at        TIMESTAMPTZ NOT NULL server_default=now()
UNIQUE (tool_id, version)
UNIQUE INDEX uq_tool_versions_single_stable (tool_id) WHERE status = 'stable'    -- 单 STABLE 不变量（并发守护）
UNIQUE INDEX uq_tool_versions_single_canary (tool_id) WHERE status = 'canary'   -- 单活跃 CANARY 不变量（并发守护）
INDEX ix_tool_versions_tool_status (tool_id, status)
INDEX ix_tool_versions_tool_last_stable (tool_id, last_stable_at DESC)
```

平台级资源，无 tenant_id 列（与 TOOL_CATALOG 语义一致：工具定义全局共享，非租户数据；区别于 schema_validation_records 的租户校验记录）。

### ⚠️ 实现陷阱提示（Pitfalls）

1. **PG session 上下文前提**：`PostgreSQLAdapter` 经 ContextVar `get_session()` 取会话，未激活时抛 `InvalidStateError`。`resolve_version` 的惰性初始版本注册会走 `repo.save()`——在 PG 仓储装配下，该路径仅在 API 请求上下文（SessionMiddleware）或显式 session fixture 内可用。**集成测试必须复用 `repo_session`/`pg_session` fixture 模式**；单元/验收测试用 InMemory 仓储天然无此约束。
2. **frozen dataclass 加字段顺序**：`ToolCall` 是 `@dataclass(frozen=True)`，新增 `version: str | None = None` 必须放在已有默认值字段之后（带默认值字段后置规则），保证既有位置参数调用零破坏。
3. **内建 `hash()` 禁用**：`TrafficRouter` 若用内建 `hash(str)`，PYTHONHASHSEED 进程盐化使**跨次运行**结果漂移（单次运行内单 worker 结果一致——真实风险是"连续 5 次无随机失败"验收被击穿，而非同次 xdist 多 worker 间歇失败）。**散列算法为规范条款（见 AC-3 验证标准——sha256 + `% 100 < weight` 桶映射，实现与测试共用，非 md5/sha256 任选）**，样本集用固定 `f"key-{i}"` 而非随机生成。
3a. **并发不变量的双层守护与异常转换**：单 STABLE/单活跃 CANARY 由 PG partial unique index（WHERE status='...'）在存储层硬守护，InMemory 仓储在 save 时软校验（**双 STABLE/双 CANARY 并存破坏抛 432**——并入「并存冲突」族；单测可直连构造）——服务层（SCOPED 每请求一实例）不依赖进程内锁。**仓储层 IntegrityError→领域异常转换规则**（document_repository.py:156 / role_repository.py:225 / domain_dictionary_repository.py:132 先例）：`(tool_id,version)` 唯一冲突 → 431；两个 partial unique index 冲突（并发双 promote/双灰度发起）→ 432（并存冲突族）——并发失败方收到业务 400 而非裸 500，**PG 集成测试断言转换后的领域异常而非原生 IntegrityError**。惰性初始注册必须 catch 431 重读返回（并发首执行竞态），否则 431 会从无辜的 `execute()` 打穿执行链。多行 save 顺序：先降级/清场行、后提升行（partial index 逐语句即时校验，反序在事务内即撞单 STABLE 索引；InMemory 同序）。
4. **EXCEPTION_HTTP_MAP 注释对齐**：追加 430-433 四条映射时，行内注释的编码必须与常量一致（4.1a 偏移 bug 先例），并同步 `test_exception_handlers.py` 的期望集合（漏同步 = 该文件测试失败）。
5. **resolve("tool_registry_service") 装配顺序**：`tool_version_service` 工厂 lambda 引用 `resolver.resolve("tool_registry_service")` 与 `resolver.resolve("schema_validator")`——两端口均已注册（composition_root **L2238 精确 / schema_validator 实为 L2368——终审核准，以端口名 grep 定位**），但注册条目顺序须在其之前或使用延迟 lambda 求值（现有 tool_registry_service 条目即为 lambda 工厂先例）。
6. **事件 payload 体积**：`ToolVersionRegistered.breaking_summary` 列表字段截断 ≤10 条（4-3 P0-H 先例，防撑爆 Redis pub/sub）。

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── entities/tool_version.py                  # 🆕 ToolVersion 聚合根 + 状态机
│   ├── events/tool_version_events.py             # 🆕 3 领域事件
│   ├── exceptions/tool_version_exceptions.py     # 🆕 4 异常（430-433）
│   ├── ports/tool_version_repository.py          # 🆕 端口 + ToolVersionQuery
│   ├── services/tool_version_policy.py           # 🆕 RolloutPolicy/TrafficRouter/RetentionPlanner
│   └── value_objects/tool_execution.py           # ✏️ ToolCall.version 可选字段
├── application/
│   ├── ports/tool_version_service.py             # 🆕 应用端口
│   ├── services/tool_version_service.py          # 🆕 编排服务
│   └── services/tool_execution_service.py        # ✏️ 可选注入 + 派生副本
├── infrastructure/
│   ├── storage/inmemory/tool_version_repository.py        # 🆕
│   ├── storage/postgresql/models/tool_version.py          # 🆕 SQLAlchemy 模型
│   ├── storage/postgresql/repository/tool_version_repository.py  # 🆕
│   └── config/tool_version.py                    # 🆕 ToolVersionConfig
├── interfaces/api/tools.py                       # 🆕 路由工厂
├── composition_root.py                           # ✏️ 3 端口条目（2 新 + 1 升级）
└── infrastructure/messaging/channel_router.py    # ✏️ DEFAULT_MAPPINGS +3
deploy/postgresql/alembic/versions/016_tool_versions.py    # 🆕
configs/event_channels.yaml                       # ✏️ +3 事件
docs/api/openapi.yaml                             # ✏️ +5 path +6 schema
```

### 已有资产复用清单（防重复造轮子 —— 实现前必读）

| 资产 | 位置 | 本 Story 用法 |
|------|------|--------------|
| `SchemaValidatorPort.validate_schema_compatibility` | `src/application/ports/schema_validator.py:148`（12 规则，实现 `src/infrastructure/validation/jsonschema_validator.py:153`——**嵌套检测 `_check_nested_schema_changes` :340-466 已实现生效**，顶层变更存在双重上报实态：主循环与嵌套递归对同一顶层 properties 各计 1 条） | register_version 直接调用，**禁止重写兼容性检测**；断言按存在性+max severity（不断言条数） |
| `BreakingChange.severity` 分级 | 同上 :47-67 | severity 摘要传入 RolloutPolicyService |
| `ToolSchemaCompatibilityError`（397） | `src/domain/exceptions/tool_schema_exceptions.py:116`（构造签名已带 tool_id/old_version/new_version/breaking_changes） | critical 拦截直接抛，**禁止新造同类异常** |
| `Tool.version` SemVer 校验 | `src/domain/entities/tool.py:53,156-160` | ToolVersion 校验规则照搬（`_SEMVER_PATTERN` 模式） |
| `ToolExecutionRepositoryPort` Query Object 先例 | `src/domain/ports/tool_execution_repository.py`（L2RdbPort 继承 + list_by_query + count + 乐观锁） | ToolVersionRepositoryPort 结构模板 |
| `PostgreSQLAdapter` 泛型基类 | `src/infrastructure/storage/postgresql/repository/postgresql_adapter.py:24`（merge upsert + ContextVar session） | PG 仓储继承，只写 `_to_entity/_to_model/_apply_filters` |
| `PostgreSQLSchemaValidationRecordRepository` | 同目录（list_by_query/order_by/分页实现） | 最贴近的仓储仿写对象 |
| domain_dictionary 回滚先例 | `domain_dictionary_service.py:158` + `domain_dictionary_repository.py:276`（savepoint 原子多行变更）+ API `/rollback/{version}`（`domain_dictionary.py:412`） | rollback 事务边界 + API 形态 |
| `create_*_router` 三级降级认证工厂 | `src/interfaces/api/domain_dictionary.py:136-227` | tools.py 路由模板 |
| `EXCEPTION_HTTP_MAP` + 统一错误响应 | `src/interfaces/api/exception_handlers.py:125-251`（工具映射已存在至 398） | 只追加 430-433 四条 |
| `DomainEvent` 基类 | `src/domain/events/base.py:41`（frozen + `__init_subclass__` 自动注册） | 3 事件继承 |
| `SandboxConfig.from_env()` 配置先例 | `src/infrastructure/config/sandbox.py` | ToolVersionConfig 模板 |
| 端口契约测试 11 维度模板 | `tests/contracts/test_port_contract_tool.py`（257 行） | 两个新端口契约测试照写 |
| BDD 工具系验收模板 | `tests/acceptance/test_acceptance_tool_io_schema_validation.py`（680 行，context dict + scenarios() + `_make_tool(version=...)`） | 验收测试第一模板 |
| HTTP 级 BDD/契约 `_make_client()` | `tests/contracts/test_api_contract_document_upload.py:55-73` | AC-6 TestClient 模式 |
| PG 集成隔离 fixture | `tests/integration/test_integration_domain_dictionary.py`（repo_session：begin+set_session+rollback）+ `tests/integration/conftest.py:522`（pg_session） | Task 3/7 集成测试 |
| 异常测试模板 | `tests/unit/domain/exceptions/test_tool_execution_exceptions.py` | 4 新异常测试照写 |
| xdist_group 串行化先例 | `test_integration_strategic_tool_e2e.py`（`pytestmark = pytest.mark.xdist_group("tool-executions-pg")`） | tool-versions-pg |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 4-5](./4-5-red-blue-debate-basic.md)（review）+ [Story 4-3](./4-3-tool-io-schema-validation.md)（done）+ [Story 4-1a](./4-1a-strategic-tool-impl.md)（done）+ [Story 4-4](./4-4-docker-sandbox-execution.md)（done）

**关键学习/Key Learnings:**
- **4-3 的「4.6/4.7 架构演进路径」专章（文件 :1600-1669）是本 Story 的正式设计输入**——severity→发布策略映射表即来源于此，实现时如与本 Story 冲突以本 Story 为准（更新时间更晚）
- **4-3 遗留缺口 Task 0 实地复核（Round 1 调研已实证，验证表述按实态更新）**：P1-12 `_check_nested_schema_changes` **已实现生效**（:340-466 真实调用，含 Round 2 P0-3 修复——4-3 文档"仅注释占位"表述过时）；实态是**顶层变更双重上报**（主循环 + 嵌套递归同路径各计 1 条）——AC-2 断言按存在性+max severity 书写；P1-13 的「死代码注释」在当前代码不存在，实态是 **397 全 src 无 raise 点**（本 Story ToolVersionService 抛出即首个 raise 点）
- **装配纪律（4-3 P0-A 教训）**：改装配链必须升级端口 version + 同步契约测试 + tags/compatibility 字段更新
- **性能断言分级（4-5 教训）**：达标 pass / 不达标 skip 留测量证据；P95 用 `statistics.quantiles(n=20)[18]`（4-4 教训：`sorted()[19]` 是 P100 冒充）
- **断言判别力（4-5 教训）**：流量路由断言必须预置已知分配的 route_key 样本（命中/未命中各一），不能只断言集合成员
- **EXCEPTION_HTTP_MAP 注释与 code 必须严格对齐**（4-1a 偏移 bug）；新增映射必须同步 `test_exception_handlers.py` 期望集合（4-5 教训）
- **Task 划分聚焦**（4-1a Task 8 教训）：登记类配置集中在 Task 2，不在实现 Task 混入多职责
- **注入可选配置对象用"继承+派生"而非"整体替换"**（4-5 LLMConfig 教训）——本 Story 派生 Tool 副本用 `dataclasses.replace` 即此原则
- **写装配样例前实地核实 resolver API**（4-4 Round 7 教训：虚构 `resolver.resolve("settings")`）——本 Story 给出的 composition_root 行号均已实地核实
- **ToolExecuted 事件无 tenant_id**（4-3 :219 提出的回填决策）：本 Story **不回填**（平台级资源事件语义，且改动会波及 2 个既有发布方），遗留为独立决策项

**应用到本故事/Applied to This Story:**
- [x] Task 0.10 前置验证 4.3 缺口
- [x] Task 5 装配升级 v1.3.0 + 契约同步
- [x] Task 7 性能断言分级 + quantiles P95
- [x] Task 2 集中登记 + 期望集合同步
- [x] AC-5 确定性路由保证断言判别力

### 非目标（Out of Scope）

- ❌ 多租户版本策略（每租户不同灰度比例）——版本为平台级
- ❌ 多 CANARY 并存（同工具多版本同时灰度）——V1 限定单活跃 CANARY，冲突抛 432
- ❌ 自动灰度推进（按成功率自动 promote）——人工触发；自动闭环属 4.7/后续
- ❌ CLI 命令（`sisys tool version ...`）——项目无统一主命令入口（document_commands.py 先例也仅测试引用）；REST API 已覆盖运维触点
- ❌ L1 Redis 缓存/进程内路由快照（PG 装配下 resolve 每执行查一次库是有意取舍，见存储架构）、`validate_compatibility_batch` 批量校验、`dry_run` 标志位（4-3 提议的可选 P2 API）——留待有真实性能/运维诉求时追加
- ❌ per-version 执行统计视图（执行次数/成功率——数据源 `tool_executions.tool_version` 聚合查询，支撑人工 promote 决策的观测面）——V1 人工决策凭 `GET /versions/traffic` + 日志；4.7 反馈闭环启动时按需实现（业界 promote 前均有 per-version 指标，登记为 4.7 输入）
- ❌ ToolExecuted 事件 tenant_id 回填（独立决策项）
- ❌ PENDING 版本主动撤销 API——误注册的版本号永久占用 (tool_id,version) 唯一槽位（重注册同号 431），以换版本号绕行；撤销能力留有真实运维诉求时评估
- ❌ `ToolExecuted` 事件 `tool_version` 反映实际执行版本——事件发布方（StrategicAnalysisUseCase / auto_execute_completed_handler）持有路由前 Tool 对象；实际版本以 `ToolExecution.tool_version` 快照为权威记录。事件级回填需改造 2 个既有发布方，遗留独立决策项（与 tenant_id 回填同批评估）
- ❌ tools 表 PG 持久化与 ToolRepositoryPort PostgreSQL 实现（Tool 元数据仍以 TOOL_CATALOG 为 SSOT；migration 011 注释中的"后续补强 FK"继续遗留）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | glm-5.3（Claude Code dev-story workflow） |
| **Version** | create-story workflow v6.3.0 |
| **Execution Date** | 2026-10-07 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Story 4.6 定义 L1318-1358；Epic 4 总表 L765-785） |
| **架构文档** | `docs/architecture/architecture.md`（§9 实体定义 L798）+ `docs/architecture/sisys-core-domain-design.md` §17.2 |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/4-5-red-blue-debate-basic.md`（依赖 Story：4-1a / 4-3） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **设计预留** | `4-3-tool-io-schema-validation.md` L1600-1669「4.6/4.7 架构演进路径」专章 |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（L1318-1358 + FR-ST-06 L517/L1821 + or.md 三.1.(2)/三.工具箱.1[2]）
- [x] 架构约束从 `architecture.md` + `sisys-core-domain-design.md` 提取
- [x] 前一个故事学习经验整合（4-1a/4-3/4-4/4-5 四故事 + deferred-work.md 已核查无相关延期项）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 多 Agent 并行代码调研（领域层/应用+基础设施/接口层/测试模式/前序经验 5 视角，全部结论带文件行号实证）

### Dev 实施记录（dev-story）

**Task 0（2026-10-07）：**
- 0.10 冒烟实证三分支：① `_check_nested_schema_changes` 已实现生效（嵌套 type 变更检出 `/properties/user/properties/email/type` severity=critical——4-3 文档 P1-12 表述过时确认）；② **顶层双重上报实态**：顶层 type 变更产出 2 条 breaking_change 且 **path 相同**（`/properties/name/type` ×2，实测比审查轮认知更精确——两条 path 完全一致），AC-2 断言按「存在性+max severity 不断言条数」正确；③ major/minor 判别性构造实证：新增 required=REQUIRED_FIELD_ADDED(major)、新增可选=OPTIONAL_FIELD_ADDED(非破坏)。397 无 raise 点（前轮终审 grep 实证，本 Story ToolVersionService 抛出即首个 raise 点）
- 0.5 openapi：5 path + 6 schema 落地，契约静态断言 9 项全绿（规范先行模式 B——Task 0 即绿符合预期）
- 0.6/0.7：feature 37 场景（zh-CN 中文 Gherkin，R6 模板 test_acceptance_postgresql_relational_layer 结构风格 + AC-x.y 前缀）+ .py 完整步骤实现（真实服务链 + _RecordingEngine 子类观测面 + AC-6 TestClient/AsyncMock 子模式）
- 0.8/0.9：3 契约测试落地；红窗口确认 = 端口契约×2 与验收 collection error（ModuleNotFoundError 预期形态）+ API 静态断言绿（预期中间态）

**Task 1-9 实施总录（2026-10-07，9 commits）：**
- **实施期发现的文档外事实**：① 事件业务字段命名 `tool_version`（避开 DomainEvent 基类 `version: int` 核心字段冲突——ToolExecuted 先例同款）；② schema 判别性构造中「minor 变体含 optional 字段 + 后续 BASE 注册」会被真实校验器判为破坏性（FIELD_REMOVED）→ canary_only——性能场景初始 STABLE 统一用 base schema；③ 跨子域继承白名单 `(tool_version, business)` 登记（审查轮预警实施期实证）；④ PG 时间戳列须显式 `DateTime(timezone=True)`（asyncpg aware/naive 冲突）
- **红线修复实录**：`# type: ignore[arg-type]` → 类型收窄（datetime.min 兜底 key）；`# noqa: PLR0913` → 删除（构造器注释化）；HTTPException 仅认证路径（domain_dictionary 先例豁免口径）
- **回归联动**：既有测试 2 处旧断言同步（composition_root_assembly v1.2.0→v1.3.0、test_arch_strategic_tool tags +versioned）；openapi path parameter 声明补全（UnresolvableParameterError 修复——openapi-spec-validator OK）
- **最终全量**：`pytest tests/unit tests/contracts tests/integration tests/acceptance` = **11191 passed, 4 skipped**（动态 skip 为环境依赖项）；三条异常 grep 自查本 Story 文件零输出；ruff/mypy 全绿（pre-commit hooks 全 Passed × 9 commits）
- **AC 覆盖**：AC-1（59 实体+31 仓储测）AC-2（判别构造+397 context）AC-3（规范散列独立重算+统计 30%±5%+调档+abort）AC-4（防 ping-pong 两连回滚+清空戳+两级淘汰+430/433 分立）AC-5（_RecordingEngine 派生副本+惰性三分支+未注入回退）AC-6（6 端点+全错误映射+401）AC-7（P95 切换<500ms/路由<5ms 全达标未触发 skip）——37+2 收尾场景全绿
- **模块依赖窗口提交策略（4-1f 先例）**：验收 .py 与 2 个端口契约 .py 顶部 import 待建模块会使 mypy hook 挂全仓提交——红窗口确认（0.9）后暂缓入库，随对应模块落地批提交（仓储契约随 Task 3 / 服务契约与验收 .py 随 Task 4/5）；feature 与 openapi/API 契约（已绿）本批入库

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/4-6-tool-version-management.md`

**待创建的文件/To Be Created (Dev Story 实施):**

src（12 个）+ migration（1 个）:
- `src/domain/entities/tool_version.py` - ToolVersion 聚合根 + 状态机
- `src/domain/events/tool_version_events.py` - 3 领域事件
- `src/domain/exceptions/tool_version_exceptions.py` - 4 异常（430-433）
- `src/domain/ports/tool_version_repository.py` - 端口 + ToolVersionQuery
- `src/domain/services/tool_version_policy.py` - RolloutPolicy/TrafficRouter/RetentionPlanner
- `src/application/ports/tool_version_service.py` - 应用端口
- `src/application/services/tool_version_service.py` - 编排服务
- `src/infrastructure/storage/inmemory/tool_version_repository.py` - InMemory 仓储
- `src/infrastructure/storage/postgresql/models/tool_version.py` - SQLAlchemy 模型
- `src/infrastructure/storage/postgresql/repository/tool_version_repository.py` - PG 仓储
- `src/infrastructure/config/tool_version.py` - ToolVersionConfig
- `src/interfaces/api/tools.py` - 版本管理路由（6 端点含 abort-canary）
- `deploy/postgresql/alembic/versions/016_tool_versions.py` - migration

修改的文件/Modified Files:
- `src/domain/value_objects/tool_execution.py` - ToolCall.version 可选字段
- `src/application/services/tool_execution_service.py` - 版本路由注入 + 派生副本
- `src/composition_root.py` - 3 端口条目（2 新 + tool_execution_service 升级 v1.3.0）
- `src/infrastructure/messaging/channel_router.py` - DEFAULT_MAPPINGS +3
- `src/domain/exceptions/_code_ranges.py` - tool_version (430,439) 子域
- `src/domain/exceptions/__init__.py` - 导出 4 异常
- `src/domain/events/__init__.py` - 导出 3 事件
- `src/interfaces/api/exception_handlers.py` - HTTP 映射 +4（注释对齐）
- `src/interfaces/api/app.py` - 挂载 tools router
- `src/infrastructure/config/__init__.py` - 导出 ToolVersionConfig
- `configs/event_channels.yaml` - 3 事件通道
- `docs/api/openapi.yaml` - 5 path + 6 schema
- `docs/architecture/sisys-uni-exception-design.md` - §3.3.2 编码分配表
- `tests/unit/interfaces/api/test_exception_handlers.py` - 期望集合同步

测试（18 个新文件）:
- `tests/acceptance/test_acceptance_tool_version_management.feature` + `.py` - BDD 验收
- `tests/unit/architecture/test_tool_version_management.py` - 架构验证（epics 硬路径）
- `tests/unit/domain/entities/test_tool_version.py` - 实体测试
- `tests/unit/domain/services/test_tool_version_policy.py` - 领域服务测试
- `tests/unit/domain/events/test_tool_version_events.py` - 事件测试
- `tests/unit/domain/exceptions/test_tool_version_exceptions.py` - 异常测试
- `tests/unit/application/services/test_tool_version_service.py` - 服务测试
- `tests/unit/application/services/test_tool_execution_service.py` - 执行链版本集成（**新建**——原文件不存在）
- `tests/unit/infrastructure/storage/test_inmemory_tool_version_repository.py` - InMemory 仓储测试
- `tests/unit/infrastructure/config/test_tool_version_config.py` - 配置测试
- `tests/unit/interfaces/api/test_tools_api.py` - API 测试
- `tests/contracts/test_port_contract_tool_version_repository.py` - 仓储端口契约
- `tests/contracts/test_port_contract_tool_version_service.py` - 服务端口契约
- `tests/contracts/test_api_contract_tools.py` - API 契约
- `tests/contracts/test_event_contract_tool_version_events.py` - 事件契约
- `tests/contracts/test_event_channel_mapping_tool_version.py` - 事件通道映射（debate 先例）
- `tests/integration/test_tool_version_integration.py` - 集成 + 性能（epics 硬路径）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 4.6 |
| **Story Key** | 4-6-tool-version-management |
| **File** | `_bmad-output/implementation-artifacts/stories/4-6-tool-version-management.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 4: 战略工具箱 |
| **价值组** | 战略工具执行能力（V1 P1 工具箱增强） |
| **优先级** | P1-6（V1） |
| **覆盖 FR** | FR-ST-06 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-9，10 个任务全含 TDD 循环）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-7 含异常路径与性能指标）
3. [x] Architecture constraints extracted 架构约束已提取（R1-R4 设计规则显式映射）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（4 故事 + 4.3 演进专章）
5. [x] Sprint status synced to `ready-for-dev`（sprint-status.yaml:151 已登记）

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 编号规则：`R<轮>-<序号>`（R=审查轮次）。Round 1 = 四视角代码调研（领域层/应用+基础设施/接口层+事件链/测试+epics）+ 三视角文档审查（逻辑自洽性/TDD 可行性/业界最佳实践对标——Flagger/Argo/Confluent/LaunchDarkly 实证）。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-1 | rollback 需要 DEPRECATED→STABLE 迁移，状态机明文禁止 `DEPRECATED→*`——标题功能不可实现 | P0 | 状态机补第 7 条合法迁移（唯一触发方 rollback 流程）；AC-4/蓝图/Task 1 同步 |
| R1-2 | canary_only 无条件禁 w=100 → major 版本终身 CANARY 无毕业通道，绿地场景全 API 死锁（唯一灰度位被永久占用） | P0 | 拦截规则改状态感知：仅 PENDING 直接全量禁 432，CANARY promote 放行（决策表 #7）；AC-2.5 毕业链路场景 |
| R1-3 | CANARY 权重调整（渐进放量）无合法路径：蓝图 `!= tv` 豁免与矩阵 CANARY→CANARY 非法自相矛盾 | P0 | 状态机补 CANARY→CANARY 调档同态迁移；publish 对活跃 CANARY 语义=调档（决策表 #8）；AC-3.5 场景 |
| R1-4 | weight=0 五处规范互相矛盾（AC-3/蓝图/openapi/字段规范/CHECK） | P1 | 统一：发布参数域 (0,100]（服务层+openapi min 1）；实体存储 [0,100]（PENDING=0 初始态需要）；语义分离写明 |
| R1-5 | rollback ping-pong：被回滚版本获最新 last_stable_at 成为下次缺省目标，连按两次回故障版本 | P1 | 缺省目标排除本次 from_version（决策表 #9）；AC-4.5 场景 |
| R1-6 | resolve_version「有记录但无活跃版本」三分叉（AC-5/蓝图/异常表三处行为互斥）；惰性注册并发撞 431 打穿执行链 | P1 | 统一三分支规则 + 431 catch-and-refetch 幂等；AC-5 验证标准细化 |
| R1-7 | rollback 显式目标不存在：AC-6 表 404(430) vs 蓝图 433(409) 直接冲突 | P1 | 分立裁决：记录不存在→430(404)、非可回滚态→433(409)（404/409 各司其职） |
| R1-8 | 三项并发不变量（单 STABLE/单 CANARY/惰性幂等）无守护机制，SCOPED 实例无锁，并发 publish 可双 STABLE | P1 | migration 补 2 个 partial unique index（WHERE status=...）+ InMemory save 校验；Pitfall 3a |
| R1-9 | 「CANARY 无 STABLE」可达（首版本 publish(w=30) 全程无拦截），route(stable=None) 未定义 | P1 | publish(w<100) 前置「存在 STABLE」→ 432；AC-3.7 场景 |
| R1-10 | 缺 abort_canary 操作：灰度失败只能 rollback（无历史时 433 不可用，误伤 STABLE）；CANARY→DEPRECATED 迁移无 API 触发 | P1 | 新增 abort_canary 方法 + `/abort-canary` 端点（Flagger/Argo abort 语义，STABLE 不动）；决策表 #8 |
| R1-11 | Task 0.10 预期失实：P1-12 嵌套检测实际已实现生效（4-3 文档表述过时）；顶层变更双重上报（**同一顶层字段** 2 条 breaking_change，path 分别为 `/properties/{key}` 与 `/properties/{key}/type`）未在预期内 | P1 | 0.10 改三分支处置；AC-2 断言改「存在性+max severity 不断言条数」；Lessons Learned 按实态更新 |
| R1-12 | `test_tool_execution_service.py` 不存在，三处按「扩展/修改」表述，File List 分类错误 | P1 | 全部改「新建」；DoD 指认真实回归锚（tool_io 验收 :121 等三处） |
| R1-13 | AC-5 命中/未命中断言无推导方法，route() 探测同源=循环论证无判别力 | P1 | 验证标准补独立 sha256 重算法 + weight=100/无灰度边界探针；Task 1 同步 |
| R1-14 | AC-7 路由开销「内存查表」与蓝图每次 list_active 查库矛盾（PG 装配 5ms 物理边缘） | P1 | 基准分层：InMemory 断言 / PG skip 留证据+往返参考值；存储架构与非目标论断同步修正 |
| R1-15 | 保留策略四处模糊：PENDING 被静默淘汰、淘汰键(created_at)与回滚价值键(last_stable_at)错位、计数口径、plan 输入未定义 | P2 | 统一：总数口径、仅淘汰 DEPRECATED（PENDING 保护）、先无 last_stable_at 者再最旧者、plan 输入=全部版本；审计取舍声明 |
| R1-16 | 事件盲区：rollback 清场 CANARY 不在事件任何字段；调档 from==to 语义未定义 | P2 | ToolRolledBack +deprecated_versions（≤10）；调档事件语义写明 |
| R1-17 | ensure_initial_versions() 在 SSOT 端口清单但全文档零行为定义（与惰性注册互竞） | P2 | 从端口方法集删除（初始版本统一走惰性注册单入口） |
| R1-18 | register 端点 400(432) 无来源（注册流程无 weight 参数；SemVer 失败应 242） | P2 | AC-6 表改 400(242) |
| R1-19 | ToolVersionStatus 枚举值大小写未定义 vs migration CHECK 小写（集成期炸弹） | P2 | 枚举显式小写值，与 CHECK 一一对应 |
| R1-20 | Task 0.9 红窗口预期失实（openapi 静态断言 Task 0 即绿，"path 不存在"不可复现） | P2 | 预期改「验收/端口契约 collection ERROR；API 静态断言绿属预期中间态」 |
| R1-21 | 通道同步断言落点在 Task 2/Task 8 间摇摆 | P2 | 指定专测落点 test_event_channel_mapping_tool_version.py（debate 先例） |
| R1-22 | Mock 层「原子性」伪断言诱导（无事务语义恒真） | P2 | Task 4 删原子字样，原子性唯一归属 Task 7 savepoint 集成测试 |
| R1-23 | 「回滚三路径」全文无定义、覆盖率不可机械判定 | P2 | 覆盖率节就地枚举三路径映射测试文件 |
| R1-24 | Task 9.4 grep #2「认证除外」无可执行豁免口径（先例本就有 3 处认证 HTTPException） | P2 | 给出 `\| grep -v "401"` 可执行口径 |
| R1-25 | 场景集映射缺口：AC-5 惰性注册/AC-6 401 无场景；SemVer/243 分工未声明 | P2 | 补 AC-2.5/3.5/3.6/3.7/4.5/4.6/5.5/6.6 共 8 个场景 + 分工注记 |
| R1-26 | 归属表三列不自洽（service 契约 Task 0→3 实为 0→4；integration Task 7 实为 3→7；config 测试行缺失） | P2 | 分类表全列修正 |
| R1-27 | §3.3.2 双编号（分配表+子域表两张同号表），只更新一处会漂移 | P2 | 异常契约节写明两表都更新 |
| R1-28 | route_key=trace_id 无会话粘性的取舍未声明（业界按 context key 粘性分桶） | P2 | AC-5 写明选型理由与升级路径 |
| R1-29 | input/output Schema 兼容方向未区分（≈backward/≈forward，同变更两方向判定相反） | P2 | AC-2/蓝图注明方向语义（Confluent 先例） |
| R1-30 | 文件清单计数与分类错误（src 14 实 13；测试 14 实 18；填充语行会被机械迭代） | P3 | 清单修正 + 填充语删除 |
| R1-31 | 杂项失实：258→257 行；「impl 模块字符串」实为 lambda；xdist 归因错误（真实风险=跨次运行漂移）；jsonschema_validator 缺目录；SandboxConfig 恰是不导出反例；compatibility 替换语义；event_loop fixture 归属错误；auto_execute_completed_handler tool_version 恒空串论据不精确 | P3 | 逐项修正（7 处） |
| R1-32 | 「架构层 ≥85%」概念不存在；「全局 70% 标准」无出处 | P3 | 删除架构层行；自加指标标注「Story 自加，加严方向」 |
| R2-1 | **R1-5 修复自拆（勘误并补修）**：「被回滚记 last_stable_at」+「排除 from_version」组合下跨步 ping-pong 仍复现（回滚#2 候选池 max 恰为回滚#1 放弃的故障版本）——与决策表 #9 自引的业界指针原则矛盾 | P1 | 裁决为指针原则：**回滚降级不记录 last_stable_at**（只在被新版本替代/promotion 时记录），5 处传播位同步（状态机拆两行/AC-4/蓝图/Task 1/Task 4） |
| R2-2 | **R1-8 修复缺口**：partial unique index 逐语句即时校验，promote/rollback 同事务「先提升后降级」必撞单 STABLE 索引（保存顺序约束缺失） | P1 | 蓝图 publish/rollback 补保存顺序（先降级/清场行后提升行，InMemory 同序）+ Pitfall 3a 补注 |
| R2-3 | AC-6 表 4 端点（rollback/abort/GET versions/traffic）404(380) 无蓝图抛出点；traffic 行与自身「200 全 null」互斥（双评审员独立发现） | P2 | 端口方法集补通用前置规则（除 resolve 外全部方法第一步 get_tool → 380，含 list/traffic——不存在 tool_id 返回 404 而非空 200）+ 蓝图 publish/rollback/abort 补 step 0 |
| R2-4 | **R1-13 修复缺口**：sha256 重算示例是示例非规范（算法/桶映射未定为规范，实现自由度使重算断言假红）且示例缺 `.encode()` 不可执行；Pitfall 3「md5/sha256」与 Task 1「sha256」不一致 | P2 | 升格规范条款：`int(sha256(route_key.encode()).hexdigest(),16)%100 < weight` 为 TrafficRouter 规范算法（实现与测试共用）；4 处传播同步 |
| R2-5 | **R1-10 传播漏网（path 口径）**：AC-6 行/API 契约节写「6 个 path」，实际 GET/POST 共享 path，distinct path=5（Subtask 0.5/结构/清单三处的 5 本正确） | P2 | 统一「6 端点 / 5 个 path」两处 |
| R2-6 | 场景计数断链：「24→32」漏 AC-7 的 3 个；AC-7 表 4 项指标 vs 3 场景编号；AC-6 六端点 vs 5 场景编号 | P2 | AC-7 扩 7.1~7.4 四条对应四指标；AC-6 扩为 6.1~6.6 六端点各一条 + 6.7 401；总数 27→37 |
| R2-7 | Round 1 遗留 P3 批：src 计数 13 实为 12（R1-30 修复自身 off-by-one）；258→257 复用清单漏改；AC-4.4 场景名与细化规则口径不一；resolve 惰性分支缺 Tool 来源；433 分工注记与 AC-4.6 表述冲突；保留策略软上限未声明；PENDING 无退场路径未声明；R1-11「同路径」措辞（两条 path 实不同）；追溯矩阵原子性行 Task 归属；验收文件 10→11；8 项测试口径；Task 8 DoD 模糊词；Sprint 勾选失实；pytest-bdd 版本；AsyncMock 限定 | P3 | 15 处逐项修正 |
| R3-1 | **Task 4 配置注入分层矛盾（CI 必炸）**：`config: ToolVersionConfig \| None` 签名要求应用层服务 import `src.infrastructure.*`——违反 `.importlinter` 契约 `application-no-infrastructure` 与本 Story 依赖方向矩阵；SandboxConfig 先例实为组合根提取标量注入；且循环 A（服务）先于循环 B（config 模块）任务内倒挂 | P1 | 改注入标量 `max_retained_versions: int = 10`；ToolVersionConfig 留 infrastructure 仅供组合根 from_env 解析（四处传播：R2 注入行/端口清单 impl 列/循环 C/蓝图 step 7）；顺序倒挂随之消解 |
| R3-2 | **残留戳两读分歧——第 3 次缺省回滚 ping-pong 复活（R2-1 修复旁路）**：promote 期带戳→rollback 恢复→再次被回滚降级的版本，「不记录」有保留/置空两读；保留读法下候选池 max 恰为刚放弃版本，与 AC-4 自述不变量矛盾；Task 1 实体断言在残留情形不可唯一书写（37 场景推演 B1 时间线步骤 14 实证） | P1 | 裁决：rollback 降级**显式清空 last_stable_at（置 None，含残留戳清除）**——5 处传播（AC-4/状态机/蓝图/Task 1/Task 4） |
| R3-3 | 保留策略无戳 DEPRECATED 组内无平局裁决键（两轮 R+P+AB 即可达 ≥2 无戳，淘汰对象在合规实现间不同——AC-4.4 期望不可唯一书写） | P2 | 两级排序：第一级无戳组优先；第二级组内键——无戳组 created_at 升序、带戳组 last_stable_at 升序（蓝图/AC-4/Task 1 同步） |
| R3-4 | partial unique index 冲突→业务异常转换零定义（并发双 promote 撞索引裸抛 IntegrityError→500；431 转换也仅隐含未落断言口径） | P2 | 仓储层转换规则：(tool_id,version) 冲突→431、partial index 冲突→432 并存冲突族（document_repository:156 等先例）；PG 集成断言转换后领域异常；InMemory 守卫抛 432；异常表 432 场景扩 |
| R3-5 | Round 3 P3 批（37 场景/6 时间线/Task 干跑产出）：惰性注册不发 ToolVersionRegistered（审计取舍声明）；397 breaking_changes 来源未定义（补合并清单说明）；AC-2.4 判别性构造未指定（补 Given 约束）；rollback 清场 CANARY weight 未置 0（补）；promote 后 STABLE weight 存储值未定义（置 100 数据卫生）；AC-7.1/7.2 每轮需新版本号的构造约束未提示（补）；retention 触发点仅 register 未声明（补口径） | P3 | 7 处逐项补充 |
| R3-正 | **正向结论**：37 场景无死锁、35 个期望唯一可写、前置全部可达；6 条时间线中 B1 前 13 步/B2/B3/B5/B6 全部走通；Task 0→9 跨任务实质倒挂为零（红窗口均明示）；`.importlinter` 契约/migration 链/异常段/组合根条目全部实测核验 | — | 仅记录 |
| R5-1 | 终审特权发现：决策表 #4 优点列「ToolExecuted 自动带实际版本」与 AC-5 事件边界权威口径（事件字段不会自动变）矛盾 | P3 | 已修正为「ToolExecution 聚合快照自动带实际版本（事件字段不自动变——见 AC-5 事件边界）」 |
| R5-2 | 终审核准：组合根 2/4 行号锚点漂移（tool_execution_service 实为 L2294 起、schema_validator 实为 L2368——原文档 L2316-2352/L2394 系对含临时未提交改动的工作区核验所致） | P3 | 两处已按 HEAD 实态修正并注明「以端口名 grep 定位」；L2238/L2259 精确无需改 |

#### 收敛终审（独立取证 · 2026-10-07 · Round 5）

**审查周期概览**：本 Story 经 5 轮收敛——v1.0.0 创建（五视角调研）→ R1 四视角代码调研 + 三视角审查（逻辑自洽性/TDD 可行性/业界对标 Flagger·Argo·Confluent·LaunchDarkly）修 32 项（P0×3/P1×11/P2×15/P3×3）→ R2 回归核查（修复交互面 + 全文一致性）修 21 项（P1×2/P2×4/P3×15）→ R3 单深度推演（37 场景期望唯一性 + 6 条状态时间线 + Task 依赖干跑）修 11 项（P1×2/P2×2/P3×7）→ R4 纯验证轮（多维度快扫零修复）→ R5 独立终审。累计修复 66 项，修订提交 a3144e83/c18eed2a/e50f562e 与台账逐笔对应，无游离提交（交错的 4-5 会话提交经 name-only 核验零 4-6 文件混入）。

**终审判定**：独立取证通过——① 周期闭合（3 笔提交对账 + 零游离）；② 台账抽验 10/10 修复真实且传播完整（含 R2-1/R3-2 两次「修复自拆」后二次裁决链条，最终口径收敛到「回滚降级显式清空戳置 None」强语义）；③ 28+ 行号锚点与 HEAD 代码实态吻合（状态机 7 合法迁移格/8 触发语义全文自洽、异常段 430-439 空闲、397 无 raise 点现状、migration 链 015→016、tool_execution_service v1.2.0 现版本、测试先例 257/680 行）；④ 门禁三项 epics 硬约束齐备（覆盖率应用层 ≥85%/集成 ≥75%、两个 epics 硬路径测试文件逐字一致、性能指标对齐）；⑤ sprint-status:151 ready-for-dev 三处同步。**零 P0/P1 残留，Story 4-6 维持 `ready-for-dev`，可直接进入 dev-story。**

**留项清单（P3 记录级，不阻断实施，已随本收敛提交清偿 2 项）**：
1. ~~决策表 #4 措辞矛盾~~ → 已修正（R5-1）
2. ~~组合根行号漂移~~ → 已修正（R5-2）
3. Dev Agent Record "create-story workflow v6.3.0" 版本号未能在 workflow.md 中定位证实/证伪——纯元数据无实施影响，登记不修

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** [待 code-review]
**审查模式:** [待 code-review]

#### 需决策 Decision Needed

- [ ] [4-6-P0~2-N][Review][Patch | Defer] [待 code-review 填充] [blind | edge | audit] `[相对路径]:[行号范围]`

#### 已修复 Patch

- [ ] [待 code-review 填充]

#### 已推迟 Defer

- [ ] [待 code-review 填充]

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.3.1
**创建日期/Created:** 2026-10-07
**最后更新/Last Updated:** 2026-10-07
**更新说明/Description:**
- v1.0.0: 创建故事文件（多 Agent 五视角并行调研：领域层 / 应用+基础设施 / 接口层 / 测试模式 / 前序经验；设计预留来自 Story 4-3 演进专章）
- v1.1.0: Round 1 循环审查修订（D1 四视角代码调研 + D2 三视角审查：逻辑自洽性/TDD 可行性/业界对标）——修复 P0×3（rollback 迁移矛盾 / canary_only 死锁 / 调档不可达）+ P1×11 + P2×15 + P3×3 共 32 项；新增 abort_canary 能力（Flagger/Argo abort 语义）、并发守护 partial unique index、防 ping-pong 回滚目标规则；状态机 6→7 条合法迁移（CANARY 调档同态 + DEPRECATED 回滚恢复）；端点 5→6；场景 24→32
- v1.2.0: Round 2 循环审查修订（D1 回归核查视角 + D2 双视角：修复交互面审查 + 全文一致性快扫）——P1×2（R1-5 跨步 ping-pong 修复自拆→裁决业界指针原则「回滚降级不记戳」；R1-8 缺保存顺序约束→先降级后提升）+ P2×4（4 端点 380 前置通用规则 / sha256 升格规范算法 / path 口径 6→5 / 场景计数 27→37）+ P3×15；16 格状态机双向差集验证干净、30+ 行号引用实证吻合
- v1.3.0: Round 3 循环审查修订（单深度：37 场景期望唯一性推演 + 6 条状态时间线全推演 + Task 0→9 依赖干跑）——P1×2（Task 4 config 注入分层矛盾 CI 必炸→改标量 max_retained_versions 注入[贴合 SandboxConfig 先例]；残留戳两读分歧致第 3 次回滚 ping-pong 复活→裁决 rollback 降级显式清空戳）+ P2×2（保留策略无戳组平局键→两级排序；partial index 冲突异常转换零定义→仓储层 431/432 转换规则）+ P3×7；37 场景无死锁、35 期望唯一、跨任务零倒挂
- v1.3.1: Round 4 纯验证（多维度快扫零修复）+ Round 5 独立终审五节全过（周期闭合/10/10 修复取证/28+ 锚点吻合/门禁就绪/收敛判定）——终审留项 2 项 P3 随收敛提交清偿（决策表 #4 措辞、组合根行号）；收敛声明入 Story；**审查周期正式收敛，累计 66 项修复，零 P0/P1 残留，维持 ready-for-dev**
