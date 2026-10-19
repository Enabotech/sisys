# Story 5.2: Agent 身份档案加载

**Status:** `review`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 本 Story 是 Epic 5 第二个 Story（顺序依赖 5.1），直接构建于 5-1 交付的实例化管线之上。
> 链路接线断言清单（Epic 4 回顾行动项 7.1-1）与变异实证（7.1-2）为强制项（5-1 已验证的落地模板）。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** Agent 工程师,
**I want** 系统加载 Agent 身份档案（IDENTITY.md/CODE.md/SOUL.md/TOOLS.md/USER.md/MEMORY.md/HEARTBEAT.md）,
**So that** Agent 按照预定义的身份和规则执行任务。

### 业务价值

- **覆盖 FR:** FR-AC-02（P0）——「系统可以加载 Agent 身份档案（IDENTITY.md/CODE.md/SOUL.md/TOOLS.md/USER.md/MEMORY.md/HEARTBEAT.md）」（prd.md L1838）；FR-IF-02 的 Agent 侧消费（Skills 三级渐进式加载主归属 Story 4.1a 已交付，本 Story 接通 Agent 启动链路并交付 SkillSelector）
- **Epic 定位:** Epic 5「单 Agent 战略规划能力」价值组第二环——依赖链 `5.1→5.2→5.3→{5.7,5.11}`（epics L1452 顺序依赖「实例化→加载→执行→隔离」）：5.1 交付「Agent 存在」（实体+配置+持久化+事件），本 Story 交付「Agent 是谁」（身份/规则/技能清单），5.3 工作流消费两者执行任务。没有档案加载，5.3 的 LLM 上下文装配无从谈起。
- **价值链:** 身份档案是 Agent 区别于裸 LLM 调用的核心资产——or.md 四.1.[1]（L277）：AGENT 实例化启动时加载身份档案（IDENTITY.md）、行为规范（CODE.md）、人格定义（SOUL.md）、工具集（TOOLS.md）、用户信息（USER.md）、长期记忆（MEMORY.md）、心跳任务配置（HEARTBEAT.md）。
- **Skills 框架激活价值:** Epic 4 交付的 L1/L2/L3 三级加载（InMemorySkillLoader + `src/application/skills/` 下 23 个 SKILL.md）当前仅被 strategic_analysis / run_tool_chain 两用例类型级消费（生产接线仅 run_tool_chain——strategic_analysis 未注册组合根，仅测试构造）；本 Story 把 Skills L1 元数据接入 Agent 启动上下文（Skills 框架的 Agent 侧首个消费方），并按 architecture.md GAP-CRITICAL-08b（L3315）交付 SkillSelector（`list_active_skills()` 形态，消除「硬编码选择器违反 P5 Less scaffolding」GAP）。

### 前置依赖（全部 ✅ 已完成，无阻塞）

| 依赖 | 组件 | 用途 | 状态 |
|------|------|------|------|
| Story 5.1 | `InstantiateAgentUseCase` + `AgentRepository`/`RedisAgentRepository`（键 `sisys:agent:{agent_id}`）+ `AgentConfig`/`AgentConfigLoader` + `AgentInstantiated` 事件 + agent 异常子域（440/441，442-449 预留）+ `sisys-agent` CLI（`src/entrypoints/agent_cli.py`） | 本 Story 直接复用：get_by_id 读 Agent 实体、SUPPORTED_ROLES 守卫模式、异常段 442 起、CLI 子命令骨架 | ✅ done |
| Story 4.1a~4.1f | `SkillLoaderPort`（注册名 `skill_loader`，SCOPED）+ `InMemorySkillLoader`（L1 TOOLS.md 全量缓存 + L2 SKILL.md LRU-100 + L3 按需）+ 23 个 SKILL.md + `skill_manifest.py`（`get_all_slugs()`） | TOOLS.md 档案经此端口消费（R2 组合注入）；SkillSelector 组合它过滤 ACTIVE | ✅ done |
| Story 1.4 | Redis 生态（`RedisAdapter`/`build_key`） | 用例读 Agent 实体的基础设施（经 AgentRepository 端口间接） | ✅ done |
| Epic 4 回顾 | 7.1-1 链路接线断言 / 7.1-2 变异实证 / 团队协议「未接线 ≠ done」 | 本 Story 全程跟踪 | ✅ 落地模板已验证 |

---

## 🔗 现有代码继承（必须复用，禁止重复定义）

> ⚠️ **防重复造轮子清单**——以下组件已存在，dev agent 只可「直接复用 / 参考」，禁止新建同义组件。

| 组件 | 文件路径 | 复用方式 |
|------|---------|---------|
| `AgentRepository` 端口 + `RedisAgentRepository` | `src/domain/ports/agent_repository.py`、`src/infrastructure/storage/redis/redis_agent_repository.py` | **直接复用**——用例经 `get_by_id(agent_id)` 读实体；不新建读取通道 |
| `SUPPORTED_ROLES: frozenset[AgentRole]`（模块级常量真源） | `src/application/use_cases/agent_instantiation.py` L43 | **直接复用**——本 Story 用例角色守卫 import 此常量（V1 开 CFO 只改一处） |
| `AgentConfigLoader` 加载链结构（目录锚定/`asyncio.to_thread`/三阶段异常包装/未知键忽略/相对路径 path_display） | `src/infrastructure/agent_orch/yaml_agent_config_loader.py`（DEFAULT_CONFIG_DIR 四级上溯 L31、`_read_yaml` L156-195） | **参考照抄**——MarkdownAgentProfileLoader 的结构模板（换 .md 文件读取与校验逻辑） |
| agent 异常子域 440/441（442-449 空闲，`_code_ranges.py` L117 注释显式预留「5.2 档案加载」） | `src/domain/exceptions/agent_exceptions.py`、`_code_ranges.py` | **追加**——本 Story 在同文件新增 442/443，`_CLASS_TO_SUBDOMAIN` 同步 |
| `AgentInstantiated` 事件模板（kw_only 必填 + `event_type` init=False + `__post_init__` 设 aggregate） | `src/domain/events/agent_events.py` L39-67 | **参考照抄**——AgentProfileLoaded 事件模板 |
| 事件双登记模式（`configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS`） | configs/event_channels.yaml L182-185、`src/infrastructure/messaging/channel_router.py` L237-242 | **追加登记**（AgentProfileLoaded） |
| `SkillLoaderPort.load_metadata(tool_name)` + `ToolMetadata`（18 字段，含 `status: str = "active"`） | `src/application/ports/skill_loader.py` L28-72/L119 | **直接复用**——L1 元数据单工具查询；slug 直传合法（`_resolve_slug` L403-429 支持） |
| `skill_manifest.get_all_slugs()`（23 slug 全量静态映射，`TOOL_ID_TO_SLUG` L14-38 + `SLUG_TO_TOOL_ID` L41 反向推导） | `src/application/skills/skill_manifest.py` L74-76 | **直接复用**——SkillSelector 的全量枚举真源 |
| `InMemorySkillLoader`（`skill_loader` 端口已注册 SCOPED，两用例消费先例） | `src/application/skills/loader.py` L78（注册 composition_root.py L2528-2540） | **直接复用**——L1 缓存 `__init__` 同步构建（构造期同步读 TOOLS.md 一次——本地静态文件只读，非零 IO 但无网络连接），被本 Story 用例组合注入 |
| `_estimate_tokens` 启发式（`len(content) // 4`） | `src/application/skills/loader.py` L248-260 | **参考**——启动上下文 token 计量同款口径 |
| CLI 骨架（`add_subparsers(required=True)` 已就位 + 退出码 0/1/2 + finally 关池 + 守卫先于 bootstrap） | `src/entrypoints/agent_cli.py`（D1 方案 A 后入口在此，**注意 5-1 故事文中 `src/interfaces/cli/` 路径已过时**） | **扩展**——`subparsers.add_parser("load-profile")` 追加子命令，pyproject script 无需新增 |
| 组合根 Story 5.1 注册段形态（`register_port` + `__import__` 延迟导入 + lambda 工厂 resolve 依赖） | `src/composition_root.py` L2674-2736 | **参考照抄**——5-2 三端口在其后追加 |
| 事件发布两分支模式（`PublishResult.is_success == False` + raise 两路径均记日志不回滚） | `src/application/use_cases/agent_instantiation.py` L128-145 | **参考照抄**——本 Story 用例发布事件同款 |
| 契约测试 11 维度 + `_DummyResolver` 先例 | `tests/contracts/test_port_contract_agent_repository.py`（L27-42 fakeredis 零 IO 替身） | **参考照抄**——三份新契约测试模板 |
| 验收测试骨架（FEATURE 常量 + @scenario 显式绑定 + context dict + `_run_async` + 场景级 Redis 客户端 + 精确删除 + P95 warmup/quantiles 采样） | `tests/acceptance/test_acceptance_agent_instantiation.py`（5-1 最新形态，605 行） | **参考照抄**——R6 主体基准 |
| 测试基建：`get_test_env()`/`SISYS_USE_TEST_PORTS=1`（Redis 6380） | `tests/environments.py`、`tests/isolation.py` | **直接复用** |

**明确不存在、本 Story 需新建**（全仓 grep 验证零先例——`IDENTITY`/`SOUL`/`HEARTBEAT`/`profile` 在 src/ 下与 Agent 档案语义零命中，`SkillSelector` 全仓零命中，`load-profile` 零命中）：

1. 七档案资产文件（IDENTITY.md/CODE.md/SOUL.md/USER.md/MEMORY.md/HEARTBEAT.md 六件；TOOLS.md 经 skill_loader 端口复用不落新文件——见 DC-2）
2. `AgentProfile` 领域值对象 + 档案加载端口（`AgentProfileLoader`）+ Markdown 基础设施实现
3. `SkillSelector`（应用层，`list_active_skills()` 形态——architecture.md GAP-CRITICAL-08b 指定本 Story 交付）
4. `LoadAgentProfileUseCase` 档案加载用例 + `AgentProfileLoaded` 事件
5. 档案异常（EXCEPTION_442/443）
6. CLI `load-profile` 子命令

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 加载 CEO Agent 七档案

**Given** CEO Agent 已实例化（Redis 键 `sisys:agent:{agent_id}` 存在，status=IDLE）
**When** 执行档案加载用例（`LoadAgentProfileUseCase.execute(agent_id)`）
**Then** 加载七档案：IDENTITY.md（身份）、CODE.md（行为准则）、SOUL.md（价值观）、USER.md（用户偏好）、MEMORY.md（记忆）、HEARTBEAT.md（心跳）六份 .md 静态资产 + TOOLS.md 视图（经 `skill_loader` 端口 L1 元数据，23 个战略工具 ACTIVE 清单）
**And** 返回结果含六档案内容（`AgentProfile` 领域值对象）+ L1 工具元数据清单 + 启动上下文 token 计量
**And** 档案文件缺失 / 不可读 / 编码非法 / 内容空白 / 超大小上限 → 抛 `AgentProfileError`（EXCEPTION_442）——（本 And 子句的失败路径由**端口直连场景**（AC-1.2/1.3/2.3）与 Task 2 单测验证，不经本 When 的用例链——见场景表分档）

**验证标准/Validation Criteria:**
- [ ] 六档案从 `configs/agents/profiles/ceo/` 固定名文件读取（目录构造注入可覆盖，测试传 tmp_path）
- [ ] TOOLS.md **不复制物理文件**——数据源为 `skill_loader` 端口 L1 元数据（单一真源，见 DC-2），用例经 `skill_selector.list_active_skills()` 消费（ACTIVE 过滤单点，见 DC-8）
- [ ] 结果 DTO 含 `profile`（AgentProfile）/ `tools_l1`（tuple[ToolMetadata, ...]，仅 status=="active"）/ `startup_context_tokens`（int）
- [ ] 失败路径（文件缺失/空白/超限）均抛 `AgentProfileError`，`error.code == "EXCEPTION_442"`，`error.context` 携带 `role` 与缺失文件名

### AC-2: 档案验证与存在性守卫

**Given** 档案加载请求到达用例
**When** 执行守卫与验证
**Then** agent_id 在仓储中不存在（键不存在或 TTL 过期）→ 抛 `AgentNotFoundError`（EXCEPTION_443）
**And** 角色（实体 role）不在 `SUPPORTED_ROLES`（非 CEO）→ 抛 `AgentRoleNotSupportedError`（EXCEPTION_441，复用 5-1 异常，守卫先于档案加载）
**And** 六档案内容验证通过：每档案非空（非纯空白）且单文件 ≤64KB；验证规则在加载器内实施，验证通过率对内置资产为 100%（确定性静态文件）

**验证标准/Validation Criteria:**
- [ ] 随机 UUID（仓储无键）→ `AgentNotFoundError`，`error.code == "EXCEPTION_443"`，`error.context` 携带 `agent_id`
- [ ] 守卫顺序断言：agent 存在性检查 → 角色守卫 → 档案加载（单测以 Mock 调用序断言，对齐 5-1「守卫先于加载」教训）
- [ ] 档案验证规则：strip 后非空 + 大小上限（`PROFILE_FILE_MAX_BYTES = 65536` 模块常量）——越界抛 442
- [ ] MEMORY.md 档案为 MVP 静态种子（「暂无系统级记忆」占位语义），系统级动态合并不在本 Story（见 DC-6 与偏离声明 D-3）

### AC-3: Skills L1 元数据与 SkillSelector（FR-IF-02 Agent 侧）

**Given** Skills 框架已注册（`skill_loader` 端口，23 个 SKILL.md）
**When** 档案加载用例组装 TOOLS.md 视图 / 调用 SkillSelector
**Then** L1 元数据清单包含 23 个工具（slug + tool_name + description + when_to_use + tags 元数据），仅含 status=="active" 条目
**And** `SkillSelector.list_active_skills()` 返回 ACTIVE 全量列表——**无关键词权重排序、无语义相似度打分**（interface-design.md §5.5 权威口径：Skill 触发由 LLM 基于 L1 description 自主判断，SkillSelector 仅作查询接口；epics L1546 旧文案已废弃，见偏离声明 D-1）
**And** TOOLS.md L1 视图 token 计量 ≤1200 tokens——**计量对象定稿（两口径分述，DC-3）**：① **L1 缓存口径** = `src/application/skills/TOOLS.md` 全文 `len(chars)//4`（现状 1104 tokens，interface-design.md L52/L633「启动全量预加载 ≤1.2K」预算的对象）；② **用例计量口径** = `"\n".join(f"{m.tool_name}: {m.description}" for m in tools_l1)` 拼接文本（现状约 218 tokens，是 TOOLS.md 内容子集——本 Story `startup_context_tokens` 的 L1 部分与 AC-3.1 断言均用此口径）

**验证标准/Validation Criteria:**
- [ ] `tools_l1` 条目数 == 23，全部 `status == "active"`。**⚠️ 23 为当前 Skills 资产状态 tripwire**（23 个 SKILL.md 全 ACTIVE 实测）——任一 SKILL.md status 演进（deprecated 等）时本 Story 全部 `==23` 计数断言（AC-1.1/3.1/3.2/Task 3 红/Task 6 集成都含）随资产同步更新，届时红 = 资产演进确认而非测试缺陷；事件 `active_skill_count` 断言写 `== len(result.tools_l1)` 与 DTO 同源派生，勿新增字面量
- [ ] L1 token 计量用 `_estimate_tokens` 同款启发式（chars//4），**断言对象为用例拼接视图**（`"\n".join(f"{m.tool_name}: {m.description}")`，分隔符定稿换行），断言 ≤1200（拼接视图为 TOOLS.md 子集，实测 ~218，远低于上限——1104 为 TOOLS.md 文件口径参照值，非本断言对象）
- [ ] SkillSelector 为纯过滤（组合 `skill_manifest.get_all_slugs()` + `skill_loader.load_metadata(slug)`，过滤 status），零排序副作用断言（返回顺序与 slug 清单一致或稳定序）
- [ ] **不实现**关键词 40% + 语义 60% 融合（GAP-CRITICAL-08b 明文废弃；语义基础设施零消费属预期）

### AC-4: 启动上下文 token 预算与 AgentProfileLoaded 事件

**Given** 七档案加载与 L1 组装完成
**When** 用例完成计量与发布
**Then** 启动上下文分项计量：IDENTITY.md + SOUL.md 合计 ≤500 tokens；TOOLS.md L1（拼接口径，见 AC-3）≤1200 tokens；总计量（IDENTITY+SOUL+TOOLS_L1 拼接后一次计量）≤1700 tokens——预算口径按 interface-design.md 修订版（PRD NFR-IF-02 旧口径 <500 tokens 偏离声明 D-2）。注：总量为拼接后一次 `//4` 计量，与分项计量之和存在 ≤1 取整差；**分项断言由测试从 `result.profile.identity/soul` 与 `result.tools_l1` 按同款口径现算**（DTO 仅暴露总量 `startup_context_tokens`，无分项字段）
**And** 发布 `AgentProfileLoaded` 领域事件（frozen dataclass：`agent_id`/`role`/`startup_context_tokens`/`active_skill_count`，`aggregate_type="Agent"`；RELIABLE 模式经 RabbitMQ via Outbox——同 5-1 语义）
**And** 事件在 `configs/event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` 双登记（routing key `sisys.events.reliable.agent_profile_loaded`）
**And** 发布失败记日志不回滚（`PublishResult.is_success == False` 与 raise 两分支，对齐 5-1 AC-4 语义）；先加载后发布

**验证标准/Validation Criteria:**
- [ ] 验收测试用真实 `InMemoryEventBus` 注入用例，断言 `published_events` 含 `AgentProfileLoaded` 且四字段正确
- [ ] 双登记两处 grep 可达
- [ ] 内置 CEO 档案资产设计受 IDENTITY+SOUL ≤500 tokens 约束（资产编写红线，Task 2 落实）

### AC-5: 性能指标

**Given** 真实 Redis 服务可用（`SISYS_USE_TEST_PORTS=1` → 6380 端口）与内置档案资产
**When** 执行档案加载全链路（get_by_id → 六文件读 → L1 组装 → 计量 → 发布）
**Then** 档案加载延迟 **P95 < 500ms**（≥20 次采样 + warmup 剔除 1 次 + `statistics.quantiles(n=20)[18]`——5-1 / `tests/acceptance/test_acceptance_docker_sandbox.py` L1001-1012 同款口径（acceptance 版非 benchmark 版）；典型链路 <20ms，约 25 倍余量）
**And** 档案加载成功率 100%（20 次重复加载全部成功——确定性文件 IO + L1 内存缓存命中，无随机失败面）
**And** 复用连接与既有 L1 缓存（**生产语义设计约束**：组合根 SINGLETON 注册 + `InMemorySkillLoader.__init__` 一次性建缓存，禁止每次加载重建；**验证路径为场景级手动组装**——测试内由同一场景单实例跨 20 次调用体现复用，本条无独立断言载体）

**验证标准/Validation Criteria:**
- [ ] 性能测试基于真实 Redis + 真实文件，标记 `benchmark` + `xdist_group` 串行化
- [ ] 20 次重复加载成功率断言（计数 == 20 全成功）

### AC-6: 端口契约、架构合规与 CLI 接线

**Given** 本 Story 新增端口与入口
**When** 契约测试与架构测试运行
**Then** 三个新端口（`agent_profile_loader`/`skill_selector`/`agent_profile_use_case`）在组合根注册为 `PortSpec`，契约测试 11 维度全过（维度清单同 5-1：已注册/name/version/interface 是 Protocol/lifetime/owner/module/tags/impl 工厂 9a+9b/REQUIRED_METHODS/runtime_checkable）
**And** 依赖方向合规：domain 零外部依赖（`agent_profile.py`/`agent_events.py`/`agent_exceptions.py` 零第三方 import）、infrastructure 不 import interfaces、`AgentProfile` **不含 ToolMetadata**（application 层类型，domain 依赖 application 违反方向矩阵——分层裁定见 DC-7）
**And** CLI 入口 `sisys-agent load-profile --agent-id <uuid>` 接线生效（输出六档案加载摘要 + ACTIVE 技能数 + token 计量）——「代码写了但没接线 ≠ done」

**验证标准/Validation Criteria:**
- [ ] `tests/contracts/test_port_contract_agent_profile_loader.py` 等三份契约测试通过（11 维度）
- [ ] 架构测试断言：`src/domain/value_objects/agent_profile.py` 零第三方 import 且零 application import；`MarkdownAgentProfileLoader` 不 import interfaces；CLI 不 import infrastructure
- [ ] CLI 端到端冒烟：`REDIS_PORT=6380 poetry run sisys-agent load-profile --agent-id <instantiate 产出的 uuid>` 真实执行成功（非法 UUID 字符串 → `ValidationError`（EXCEPTION_201）统一异常体系，禁止裸 ValueError 逃逸）
- [ ] 链路接线断言清单 L1-L8 全部绿灯或显式 deferred 登记（见 Task 0）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→变异→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] 新增 `AgentProfileLoaded`，定义位于 `src/domain/events/agent_events.py`（与 AgentDecided/AgentInstantiated 同文件，agent 聚合事件内聚）
- [ ] frozen dataclass 标准库实现，字段级 Schema：
  - `agent_id: uuid.UUID = field(kw_only=True)`（⚠️ **必填字段必须 kw_only**——DomainEvent 基类字段全带默认值，非 kw_only 必填字段类定义即抛 `TypeError: non-default argument follows default argument`；对齐 AgentInstantiated L56-59 先例）
  - `role: str = field(kw_only=True)`（AgentRole.value）
  - `startup_context_tokens: int = field(kw_only=True)`（启动上下文计量，AC-4 预算可观测）
  - `active_skill_count: int = field(kw_only=True)`（ACTIVE 工具数，5.7 Phoenix 追踪/5.9 漂移检测的消费锚点）
  - `event_type: str = field(default="AgentProfileLoaded", init=False)`（放置位置与 agent_events.py 既有事件对齐）
  - `__post_init__` 设置 `aggregate_id=agent_id`（UUID 对象非 str，含 None 守卫）`aggregate_type="Agent"`
- [ ] 事件命名符合 `[Aggregate][EventName]` 规范（`Agent` + `ProfileLoaded`，过去分词对齐 AgentInstantiated）
- [ ] 双登记：`configs/event_channels.yaml`（`rabbitmq_routing_key: "sisys.events.reliable.agent_profile_loaded"`、`delivery_mode: "reliable"`、`description: "Agent身份档案加载完成"`）+ `src/infrastructure/messaging/channel_router.py` `DEFAULT_MAPPINGS`（对齐 AgentInstantiated 条目结构）
- [ ] 从 `src/domain/events/__init__.py` 导出（`__all__` 同步）
- [ ] `architecture.md` §10.1 领域事件完整列表追加 `AgentProfileLoaded` 行（对齐 AgentInstantiated 行形态——登记类文档随落地 Task 同步）

#### 数据模型 (Data Models)

- [ ] 新增 `AgentProfile` 值对象，位于 `src/domain/value_objects/agent_profile.py`（与 agent_config.py 同目录），frozen dataclass，**零外部依赖**（仅标准库 + `AgentRole`；**禁止引用 ToolMetadata**——它在 application 层，domain 依赖 application 违反方向矩阵，分层裁定见 DC-7）：

```python
@dataclass(frozen=True)
class AgentProfile:
    agent_id: uuid.UUID                 # 必填，档案归属的 Agent 实例
    role: AgentRole                     # 必填，枚举
    identity: str                       # 必填，IDENTITY.md 内容（身份：角色定义/职责/权责边界）
    code_of_conduct: str                # 必填，CODE.md 内容（行为准则）
    soul: str                           # 必填，SOUL.md 内容（价值观/决策风格）
    user_preferences: str               # 必填，USER.md 内容（用户偏好）
    memory: str                         # 必填，MEMORY.md 内容（长期记忆——MVP 静态种子）
    heartbeat: str                      # 必填，HEARTBEAT.md 内容（心跳任务配置）
```

- [ ] `AgentProfile` 自校验（`__post_init__`）：agent_id UUID 类型、role 枚举、六档案字段 `isinstance(str)` 且 strip 后非空——校验失败抛 `AgentProfileError`（EXCEPTION_442，档案资产缺陷语义与 440「配置资产缺陷」同族分码监控）
- [ ] **复用不修改**：`Agent` 实体、`AgentRole`/`AgentStatus`、`AgentConfig` 值对象、`ceo_agent.yaml`
- [ ] 应用层结果 DTO：`AgentProfileLoadResult`（frozen dataclass，定义于 `src/application/use_cases/agent_profile_loading.py` 模块内——对齐 `AgentInstantiationResult` L46-56 先例）：

```python
@dataclass(frozen=True)
class AgentProfileLoadResult:
    agent_id: uuid.UUID
    role: AgentRole
    profile: AgentProfile                          # 六档案（domain VO）
    tools_l1: tuple[ToolMetadata, ...]             # L1 元数据（仅 active，application 层类型）
    startup_context_tokens: int                    # IDENTITY+SOUL+TOOLS_L1 合计计量
```

- [ ] 六档案资产文件新建于 `configs/agents/profiles/ceo/`（固定名：IDENTITY.md/CODE.md/SOUL.md/USER.md/MEMORY.md/HEARTBEAT.md；路径裁定见 DC-1）。**资产内容红线**：
  - IDENTITY.md + SOUL.md 合计 ≤500 tokens（`len(chars)//4` 估算，即**合计 chars ≤2000 为绑定约束，Task 2.4 实测兜底**——「10~40 行」仅为风格指引，与 token 红线冲突时以 chars 上限为准：40 行×60 字×2 文件 = 4800 chars 已超红线一倍）——AC-4 预算约束
  - 每档案 10~40 行精简 Markdown（风格指引），语义锚点：IDENTITY 含角色名「CEO」+ 三条职责（对齐 ceo_agent.yaml responsibilities：战略方向/最终决策/高管协调）；SOUL 含决策价值观（core-domain §17.3.1 CEO 条目 `view: executive` 高管决策视角 + expertise 域：宏观趋势/竞争格局/战略意图——该节无成文价值观清单，以高管视角语义为锚）；CODE 含 5~8 条行为准则（含隔离纪律/证据要求）；USER 为 MVP 默认高管偏好；MEMORY 为静态种子（明示「系统级记忆合并不适用于 MVP」）；HEARTBEAT 为心跳配置文档（默认每日频率占位，**不接线 scheduler**）
  - 单文件 ≤64KB 上限内（正常 <5KB）

> **未知文件策略（定稿）**：加载器**忽略**目录内 Schema 外未知文件（前向兼容——V1 新增档案文件期新旧共存），Task 2 红行含「目录含多余未知文件 → 六档案加载成功」用例锁定。

#### 统一端口定义注册与管理 (Port Contract)

- [ ] 端口契约定义位于 `src/domain/ports` 与 `src/application/ports`
- [ ] 端口注册中心位于 `src/domain/ports/registry.py`，所有端口必须登记为 `PortSpec`
- [ ] 端口实现仅可在 `src/composition_root.py` 统一注册，禁止业务代码直接实例化具体实现
- [ ] 端口解析器位于 `src/domain/ports/resolver.py`，业务代码只通过抽象解析实现
- [ ] 端口契约门禁位于 `src/domain/ports/contract_gate.py`，端口变更必须通过兼容性检查
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_agent_profile_loader.py` 等 3 份；维度 9b 用测试本地 `_DummyResolver`——agent_repository 契约测试 L27-42 fakeredis 先例；`agent_profile_use_case` 的 Dummy 须另提供 `agent_profile_loader`/`agent_repository`/`skill_selector`/`event_publisher` 四依赖名；`skill_selector` 的 Dummy 须提供 `skill_loader`）
- [ ] 接口命名符合单一职责，禁止同义接口重复定义
- [ ] 端口具备唯一名称、版本、owner、兼容策略
- [ ] 跨模块调用仅依赖抽象接口，不直接依赖实现类
- [ ] 端口变更配套契约测试与兼容性检查
- [ ] 禁止在服务文件中本地定义 Protocol / Port 抽象

**本 Story 端口契约清单（唯一事实源）：**

| # | 端口名称（注册名） | 版本 | interface | 实现模块 | lifetime | owner | tags | 状态 |
|---|------------------|------|-----------|---------|----------|-------|------|------|
| 1 | `agent_profile_loader` | v1.0.0 | `AgentProfileLoader`（application/ports/agent_profile_loader.py） | `src.infrastructure.agent_orch.markdown_agent_profile_loader.MarkdownAgentProfileLoader` | SINGLETON | platform | ("agent","profile") | 新建 |
| 2 | `skill_selector` | v1.0.0 | `SkillSelectorPort`（application/ports/skill_selector.py——端口名带 Port 后缀对齐 `SkillLoaderPort` 先例，与实现类 `SkillSelector` 异名防 import 二义） | `src.application.skills.registry.selector.SkillSelector` | SINGLETON | platform | ("skills","selector") | 新建 |
| 3 | `agent_profile_use_case` | v1.0.0 | `LoadAgentProfileUseCase`（application/use_cases/agent_profile_loading.py，interface 绑定自身类型，对齐 5-1 用例端口先例） | 工厂 lambda：resolve agent_profile_loader + agent_repository + skill_selector + event_publisher | SINGLETON | platform | ("agent",) | 新建 |

> lifetime 说明：三端口均 SINGLETON——`MarkdownAgentProfileLoader` 无连接状态（每次调用即时读文件，MVP 无缓存层）；`SkillSelector` 无状态纯查询；用例对齐 5-1 `agent_instantiation_use_case` SINGLETON 先例。`skill_loader`（4-1a，SCOPED）被 SINGLETON 用例捕获属 captive dependency——与 5-1 D7 同款（`InMemorySkillLoader` 无连接状态且其 L1 缓存被钉住反而保证跨调用复用，性能有利），登记注记不处置（D7 留项归 5.4 决策回迁）。

**端口方法签名（Task 0 定稿，实现不得偏离）：**

```python
# src/application/ports/agent_profile_loader.py —— 档案加载端口（R2 应用层具体应用端口，组合消费 R1 基础端口资产目录）
@runtime_checkable
class AgentProfileLoader(Protocol):
    async def load(self, role: AgentRole, agent_id: uuid.UUID) -> AgentProfile: ...
    # 失败统一 AgentProfileError(442)：目录缺失/文件缺失/不可读/编码非法/内容空白/超大小上限
    # agent_id 透传进 VO（档案归属锚点），role 决定寻址目录 profiles/{role.value}/

# src/application/ports/skill_selector.py —— Skill 选择器端口（interface-design.md §5.5 权威口径）
@runtime_checkable
class SkillSelectorPort(Protocol):
    async def list_active_skills(self) -> tuple[ToolMetadata, ...]: ...
    # 返回 status=="active" 的全量 L1 元数据（按 slug 清单稳定序）；无排序打分、无 Top-K
```

- [ ] `MarkdownAgentProfileLoader` 构造注入 `profile_root: Path | None = None`（默认 `Path(__file__).parent.parent.parent.parent / "configs" / "agents" / "profiles"` **仓库根锚定不依赖 cwd**——对齐 YamlAgentConfigLoader L31 四级上溯模式；测试传 tmp_path 覆盖）；文件读取 `asyncio.to_thread(Path.read_text, path, encoding="utf-8")`（不引入 aiofiles；**必须显式 encoding**——裸 read_text 依赖 locale，「非 UTF-8 → 442」契约会环境漂移）；目录寻址 `profile_root / role.value / "IDENTITY.md"` 等六固定名
- [ ] `SkillSelector`（`src/application/skills/registry/selector.py`——architecture.md §13.11 L2299 规划路径，registry/ 目录已存在为空）组合注入 `SkillLoaderPort`，实现为 `get_all_slugs()` 枚举 → 逐 slug `await skill_loader.load_metadata(slug)` → 过滤 `status == "active"` → 按 slug 清单序返回 tuple；**禁止**关键词打分/语义检索/Top-K（GAP-CRITICAL-08b）
- [ ] 组合根注册位置：`src/composition_root.py` Story 5.1 段（L2674-2736）之后新增「=== Story 5.2 ===」段

#### 端口契约清单执行约束（强制）

- [ ] 本清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口，禁止未同步更新 registry / resolver / contract test
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增异常在 Task 0 完成设计，Task 1 实现。
> **禁止 `raise ValueError`**；完整清单见 [`sisys-uni-exception-design.md §3.3.2`](../../../docs/architecture/sisys-uni-exception-design.md)。

**在既有 agent 子域（440-449）内追加**，定义文件：`src/domain/exceptions/agent_exceptions.py`（追加，不新建文件——对齐子域文件先例；442-449 已在 `_code_ranges.py` L117 注释预留「5.2 档案加载」）：

| 异常类 | 编码 | 基类 | 触发场景 | HTTP 映射 |
|--------|------|------|---------|-----------|
| `AgentProfileError` | EXCEPTION_442 | `SystemException` | 档案目录缺失 / 档案文件缺失 / 文件不可读（OSError 家族）/ 编码非法（非 UTF-8）/ 内容纯空白 / 单文件超 64KB 上限 / VO 字段类型非法（六档案非 str）——档案资产属系统资源（部署缺陷非调用方输入错误），同 440 继承链语义分码监控 | 500 |
| `AgentNotFoundError` | EXCEPTION_443 | `BusinessException` | `get_by_id(agent_id)` 返回 None（键不存在或 TTL 过期后重放旧 agent_id）——请求资源不存在语义 | 404 |
| （预留） | EXCEPTION_444~449 | — | 预留给 5.3 工作流 / 5.4-5.5 EIP 隔离 | — |

**继承链选择理由（追加进 agent_exceptions.py 模块 docstring）：** 442 根因是档案资产缺陷（部署/资产错误）故入 SystemException（与 440 同族）；443 是请求方提供的 agent_id 无法定位资源（业务查询未命中）故入 BusinessException——两者延续 5-1「不设 AgentError 子域基类、平铺双分层」决策。

- [ ] 构造器携带领域上下文：`AgentProfileError(role: str = "", profile_path: str = "", reason: str = "", ..., context={role, profile_path, reason})`（对齐 AgentConfigError 构造形态，profile_path 用相对路径形态不泄露绝对路径）；`AgentNotFoundError(agent_id: str, ..., context={agent_id})`
- [ ] 消息安全性：不泄露绝对路径/堆栈/文件全文
- [ ] `_code_ranges.py`：`_CLASS_TO_SUBDOMAIN` 追加两映射（CODE_RANGES 的 agent 段已存在无需改）
- [ ] `src/domain/exceptions/__init__.py` 暴露两异常（`__all__` 同步）+ `src/interfaces/api/exception_handlers.py` 的 `EXCEPTION_HTTP_MAP` 精确注册 `AgentProfileError: 500`、`AgentNotFoundError: 404`
- [ ] 子域码段校验：`poetry run pytest tests/unit/domain/exceptions/ -v`（test_error_code_uniqueness.py + test_code_ranges.py 共 8 项）
- [ ] 同步更新 `docs/architecture/sisys-uni-exception-design.md` §3.3.2 编码分配表（442/443 行，替换 L734 预留行）+ §3.7 注册表
- [ ] BDD 异常路径场景纳入验收（AC-1.2 / AC-1.3 / AC-2.2 / AC-2.3）

#### API 契约 (API Contract)

- [ ] **OpenAPI 不适用**——本 Story 无 REST 端点（架构文档 §13.17.1 的 agent 执行端点属 5.3+；API 路由强制认证中间件成本由 Epic 7 承接）
- [ ] CLI 契约：扩展 `src/entrypoints/agent_cli.py` 追加 `load-profile` 子命令（`sisys-agent load-profile --agent-id <uuid>`，`-a/--agent-id` 必填 str）；输出格式定稿：多行人类可读摘要（六档案逐项 `IDENTITY.md: OK (N chars)`——N 为 `len(profile.<field>)` 字符数直读 + `活跃技能: N`（运行期动态值，不写字面量）+ `启动上下文: N tokens`），成功退出码 0；业务异常退出码 1（stderr `[EXCEPTION_44x] 消息`）；argparse 用法错 2（`add_subparsers(required=True)` 已就位）
- [ ] **UUID 解析守卫（红线）**：`--agent-id` 字符串转 UUID 时**禁止裸 `uuid.UUID(value)`** 逃逸 ValueError——函数体内 try/except 映射 `ValidationError`（EXCEPTION_201，应用层输入校验语义，对齐 ocr_cli D8 清偿后模式：ocr_cli 6 处 ValueError→201 先例）；argparse 的 `type=` 参数**不得**用 `uuid.UUID`（argparse 会把 ValueError 转 usage error exit 2，绕过统一异常体系）
- [ ] **幂等性：`load-profile` 幂等只读**——不创建/修改任何状态（纯读 + 发布事件），agent_cli.py 模块 docstring 明示此语义（与 `instantiate` 非幂等对照）；注：发布事件是副作用——重复调用会重复发布 AgentProfileLoaded（事件带 `event_id`，消费方可按其幂等去重），「幂等只读」指不改变被读状态

#### 六边形架构约束（必须遵守）

**四层架构定义与依赖方向**（同全项目约束，此处列本 Story 涉及面）：

| 层次 | 本 Story 落点 |
|------|-------------|
| domain | `value_objects/agent_profile.py`、`events/agent_events.py`（追加）、`exceptions/agent_exceptions.py`（追加）——全部零第三方依赖、零 application import |
| application | `ports/agent_profile_loader.py`、`ports/skill_selector.py`、`skills/registry/selector.py`、`use_cases/agent_profile_loading.py`——仅依赖 domain + application 既有端口 |
| infrastructure | `agent_orch/markdown_agent_profile_loader.py`——实现端口，不 import application/interfaces（yaml/markdown 解析严格限定此层） |
| interfaces/entrypoints | `src/entrypoints/agent_cli.py`（扩展子命令）——经 `bootstrap()` + `resolve()` 解析用例，不触碰 infrastructure |

- [ ] domain 层禁止 import：yaml、redis、pydantic、**以及 `src.application.*`**（AgentProfile 不含 ToolMetadata 的根因）
- [ ] 组合根 `register_port` 是唯一装配点；CLI/测试经 `Resolver().resolve(...)` 获取

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_agent_profile_loading.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_agent_profile_loading.py`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases + 性能 + 接线）

**R6 强制要求：** 验收测试以 `tests/acceptance/test_acceptance_agent_instantiation.py`（5-1 最新形态，605 行）为**主体基准**——`# language: zh-CN` 中文 Gherkin、`# Story 5-2` 标识注释行、功能三行叙事、**无背景块**（门控下沉场景级——5-1 R3-F5 后形态：仅含 Redis 依赖的场景前置 `假如 Redis 缓存服务可用`，纯静态/文件场景脱离门控）、`FEATURE` 常量 + `@scenario(FEATURE, "场景名")` 显式绑定、`# ===== AC-N =====` 横幅分节注释、场景名 `AC-N.M - 描述`（ASCII 连字符 + 两侧空格，从 .feature 复制粘贴防收集期 ScenarioNotFound）、context dict（`_tenant`/`_loop`/`_redis_client`/`_agent_ids` 下划线基建 key + 业务裸名 key + `error`/`result` 断言入口）、`_run_async(event_loop, coro)` helper、新模块延迟 import（步骤函数体内 import）、显式 `pytestmark = [pytest.mark.acceptance, pytest.mark.redis, pytest.mark.xdist_group("agent-profile-loading")]`、teardown 逐键精确 delete + 同循环关闭客户端。
**用户指定模板 `test_acceptance_postgresql_relational_layer.{feature,py}` 的继承项**（其为早期范本，5-1 R6 修正后仅以下先例有效，**勿整体照抄**——不继承其背景块整 feature 门控/字面量文件名绑定/空 pass 步骤/顶部全量 import）：① AC 横幅注释分节格式（`# =====` 双行）；② AST 静态扫描架构约束场景写法（L792-819 `ast.parse + ast.walk`——本 Story AC-6 静态场景采用）；③ 真实服务探测 + `pytest.skip` 动态跳过思路（已下沉至场景级 given）。

> 承接说明：AC-2 的「未开放角色守卫（441）」路径由 Task 4 单测承接（Mock 端口单元层允许；验收构造 CFO 实体需绕过 5-1 实例化守卫，不设验收场景）；「读取失败（OSError）/编码非法」由 Task 2 单测承接（tmp_path 真实文件构造）。

**场景清单（Task 0 编写 .feature 时逐场景落地）：**

| 场景 | 覆盖 | 要点 |
|------|------|------|
| AC-1.1 加载 CEO 七档案成功 | AC-1 | 服务级真实组装（**用例级场景**——需先 instantiate 的四场景之一（AC-1.1/4.1/5.1/5.2））：先 5-1 用例真实 instantiate（手动组装：`resolve("agent_config_loader")` + 手动 `RedisAgentRepository(adapter=RedisAdapter(redis_client=ctx["_redis_client"]))` + `InMemoryEventBus()`，⚠️ 禁 resolve `agent_repository`/用例端口——SCOPED 钉住全局 Resolver 跨循环死连接，5-1 文档审查修复 #23 教训）→ 本 Story 用例手动组装（`resolve("agent_profile_loader")` + `resolve("skill_selector")`（无连接构造，本地文件只读）+ 手动仓储 + InMemoryEventBus）→ 断言六档案非空含 CEO 语义锚点 + 23 ACTIVE 工具 + result 三段 |
| AC-1.2 档案文件缺失抛异常 | AC-1 | **loader 端口直连场景**（对齐 5-1 AC-2.2/2.3 破坏场景先例——When 文案用「通过档案加载端口加载」）：tmp_path 构造六档案后删 IDENTITY.md → `MarkdownAgentProfileLoader(profile_root=tmp_path).load(role, agent_id)` 直连 → `AgentProfileError` EXCEPTION_442 且 context 含文件名。**不经用例**（守卫链存在性 443 先行——用例级直连会先抛 443 非 442；442 经用例的传播路径由 Task 4 单测覆盖）；无需 Redis、无需 instantiate（无 Redis 门控行） |
| AC-1.3 档案内容空白抛异常 | AC-1 | **loader 端口直连**（同 AC-1.2 形态）：六档案建于 `tmp_path/"ceo"/` 角色子目录（对齐寻址契约 `profile_root / role.value / 固定名`——写 tmp_path 根级会报「目录缺失」442 假绿）后六文件全为空白（空串/纯换行）→ 442 **且 `error.context["profile_path"]` 含空白文件名 + reason 含空白语义**（同码多因区分断言——442 覆盖七类成因，仅断言错误码无区分力）；无需 Redis |
| AC-2.1 档案内容验证通过 | AC-2 | **loader 端口直连**（默认 profile_root）：内置 `configs/agents/profiles/ceo/` 加载六档案验证全过 + IDENTITY 含「CEO」语义断言 + 单文件 ≤64KB；无需 Redis（纯静态文件场景，脱离门控） |
| AC-2.2 agent_id 不存在抛异常 | AC-2 | **用例级场景**（验证 443 守卫，需 Redis）：真实仓储（场景级客户端手动组装）+ `uuid.uuid4()` 随机 id → `AgentNotFoundError` EXCEPTION_443 + context 携带 agent_id（**断言形态定稿 `error.context["agent_id"] == str(随机id)`**——raise 侧 `str(agent_id)`，对齐 5-1 `role=role.value` 先例）；无需 instantiate（随机 id 本应查无） |
| AC-2.3 档案大小超限抛异常 | AC-2 | **loader 端口直连**（同 AC-1.2 形态，建于 `tmp_path/"ceo"/` 子目录）：构造 >65536 **字节**档案文件（ASCII 写 65537 字节即稳）→ 442 且 `error.context["profile_path"]` 含超限文件名；无需 Redis |
| AC-3.1 Skills L1 元数据与 token 预算 | AC-3 | 23 条 ACTIVE 元数据 + L1 计量 ≤1200 tokens（**断言对象 = 用例拼接视图** `"\n".join(f"{m.tool_name}: {m.description}")`，AC-3 两口径分述的口径②；`resolve("skill_loader")` 本地文件只读无连接，无 Redis 门控；**红绿形态注记**：若步骤内联现算拼接公式则 Task 0 即绿——tripwire 性质（保护既有 Skills 资产，23 条/218 tokens 恒满足），属预期无变异实证覆盖；若 import 新用例模块取拼接函数则红） |
| AC-3.2 SkillSelector 返回 ACTIVE 列表 | AC-3 | `resolve("skill_selector")` → `list_active_skills()` 条目数 23 + 全 active + 与 slug 清单同序（零排序副作用断言） |
| AC-4.1 启动上下文 token 预算与事件发布 | AC-4 | 真实链路计量断言（IDENTITY+SOUL ≤500 **由测试从 `result.profile.identity/soul` 按 `len//4` 现算** / 总量 `result.startup_context_tokens` ≤1700）+ InMemoryEventBus 捕获 AgentProfileLoaded 四字段 |
| AC-5.1 档案加载延迟 P95<500ms | AC-5 | 真实 Redis + 真实文件，warmup 1 + 20 采样 `quantiles(n=20)[18]` |
| AC-5.2 档案加载成功率 100% | AC-5 | 20 次重复加载全成功（同 agent_id 复用，幂等只读） |
| AC-6.1 三端口接线可达 | AC-6 | resolve 三端口 isinstance + PortSpec 元数据（禁对产物发命令） |
| AC-6.2 事件双登记与 CLI 注册 | AC-6 | yaml + DEFAULT_MAPPINGS 两处 grep 可达 + pyproject script 注册断言（静态场景；script 已注册——断言为防误删 tripwire，当前恒真属预期，无变异实证覆盖） |
| AC-6.3 完成清单逐项确认 | AC-6（收尾） | **Task 0 落盘、Task 8 转绿核对**（src/tests 完成清单 + L1-L8 接线终态断言——对齐 5-1 先例：全部场景含收尾在 Task 0 落盘，Task 8 只核对不新增，收集数恒 == 14） |

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试（`_run_async` helper）
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **@scenario 收集期陷阱**：绑定场景名与 .feature 不匹配 → 收集期 `ScenarioNotFound` 整文件炸；反向漏绑定 → 静默不收集无报错。场景名必须从 .feature 复制粘贴（ASCII 连字符 `-` 0x2D + 两侧空格，全角 `－`/`—` 即收集期炸）；Task 0.4 红阶段与 Task 8.6 转绿核对均须校验收集场景数 == 14（`pytest --collect-only -q`）
- **event_loop 来源**：pytest-asyncio 0.24 内建已弃用 `event_loop` fixture（升级前须回归验收目录）
- Redis 客户端**场景级独立创建、同循环 teardown 关闭**（跨循环 "Event loop is closed" 教训）；**分档适用**——需 instantiate 的场景（AC-1.1/4.1/5.1/5.2）两步共用 `ctx["_redis_client"]`；AC-2.2 仅需场景级客户端（无 instantiate）；端口直连与纯 resolve 场景（AC-1.2/1.3/2.1/2.3/3.1/3.2/6.1/6.2/6.3）不创建 Redis 客户端、无 Redis 门控行
- teardown **精确删除**：context 记录本场景 instantiate 产出的 agent_id，teardown 逐个 `delete(build_key("agent", str(agent_id)))`——**禁止** `delete_pattern("sisys:agent:*")`（多 worker 共享 6380 误删并行键）；tmp_path 由 pytest 自动清理零残留；禁止全库 flush
- **bootstrap 禁令**：验收测试禁止调用 `bootstrap()`（tests/conftest.py session 级 `_bootstrap_once` 已引导；同进程二次 bootstrap 抛 ConflictError）；端口获取直接 `from src.domain.ports.resolver import resolve`
- **Edge Cases 必须包含异常路径**（AC-1.2/1.3/2.2/2.3），错误断言 `isinstance` + `error.code` + `error.message` 非空

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（🔴 红阶段验证；**新模块延迟 import** 使失败推迟到场景运行期逐场景呈现——模块顶部 import 会使 pytest 收集期整文件 collection error，先例 test_acceptance_strategic_archive.py L107-108、5-1 全量采用）
- [ ] 规范文档通过人工评审或自动化校验
- [ ] **链路接线断言清单**已定义（Epic 4 回顾行动项 7.1-1）：

**链路接线断言清单（本 Story 范围）：**

| # | 接线项 | 断言内容 | 处置 |
|---|--------|---------|------|
| L1 | `agent_profile_loader` 端口 | 组合根 register_port 装配 + `resolve("agent_profile_loader")` 可达且 isinstance AgentProfileLoader | 本 Story 接线（Task 2） |
| L2 | `skill_selector` 端口 | resolve 可达 + list_active_skills 返回 ACTIVE 清单 | 本 Story 接线（Task 3） |
| L3 | `agent_profile_use_case` 端口 | resolve 可达 + 构造注入四依赖完整 | 本 Story 接线（Task 4） |
| L4 | `AgentProfileLoaded` 事件 | 发布点代码位（LoadAgentProfileUseCase 内）+ yaml/DEFAULT_MAPPINGS 双登记 + InMemoryEventBus 可捕获 | 本 Story 接线（Task 1/4） |
| L5 | CLI `sisys-agent load-profile` 子命令 | 端到端真实执行输出档案摘要（pyproject script 沿用 `sisys-agent`，无新增注册） | 本 Story 接线（Task 5） |
| L6 | `skill_loader` 端口（4.1a 交付） | **新消费方接线验证**——经 `skill_selector` 组合注入（SkillSelector 依赖它）+ AC-3.1 场景直测真实查询 23 条 | 本 Story 接线（Task 3/4，既有端点的消费方扩展） |
| L7 | heartbeat_scheduler / AutoTrigger 三 handler / HeartbeatTriggered 链 | HEARTBEAT.md 仅作静态档案加载，**不接线**消费——deferred 保持（心跳行为属 FR-SA-05 P1 / Epic 5 编排，5-1 L8 同款登记在案） | 不接线 |
| L8 | 系统级记忆链路（l0_storage/MemoryFileStorage/MemoryService/IndexManager） | MEMORY.md 仅静态种子加载，**不接线**系统级动态合并——deferred 保持（architecture.md §11.2.4 完整语义的记忆侧属记忆链路激活 Story）；**Task 0 补登记 deferred-work.md 观察项：组合根 `l0_storage`（L268-276）与 `memory_file_storage`（L1108-1116）impl 字符串指向不存在的模块路径（实际在 storage/fs/ 下）——休眠资产路径失效，激活时必炸，登记防踩坑** | 不接线 + 补登记 |

> L7 已在 deferred-work.md 登记（5-1 Task 0 核对在案）；L8 的组合根 impl 路径失效观察项为**本 Story 新发现**，Task 0 补登记；Task 8 收尾时核对登记仍在且未误删。

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🟡 变异** | 对新行为契约的断言做突变注入-还原实证（Epic 4 回顾行动项 7.1-2） | 改坏生产代码 → 测试红 → 还原 → 绿（证明断言活着） |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试（违反 TDD 测试先行原则）
- ❌ 将测试编写集中到最后一个 Task（违反 TDD 小步快跑原则）
- ❌ 跳过红阶段验证（未确认测试失败就直接写实现）
- ❌ 跳过变异实证（新断言未经突变验证即视为不可信——Epic 4 教训：8/13 Story 存在恒真断言）

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | AgentProfileLoaded 事件 | 字段/默认值/aggregate 设置/冻结性 | `tests/unit/domain/events/test_agent_events.py`（追加） | Task 1 |
| **TDD 领域异常测试** | agent_exceptions（442/443 追加） | 构造/`to_dict()`/HTTP 映射(500/404)/编码唯一/子域范围 | `tests/unit/domain/exceptions/test_agent_exceptions.py`（追加）+ 既有 uniqueness/code_ranges 套件 | Task 1 |
| **TDD 单元测试** | AgentProfile 值对象 | frozen/六字段非空校验/442 路径/agent_id-role 类型校验 | `tests/unit/domain/value_objects/test_agent_profile.py` | Task 1 |
| **TDD 单元测试** | MarkdownAgentProfileLoader | 正常加载（内置资产）/目录缺失/文件缺失/空白/超限/编码非法（tmp_path 真实文件 IO，零 mock）/未知文件忽略 | `tests/unit/infrastructure/agent_orch/test_markdown_agent_profile_loader.py` | Task 2 |
| **TDD 单元测试** | SkillSelector | ACTIVE 过滤/全量 23/稳定序/非 active 排除（Mock skill_loader 或真实 loader——真实优先：resolve 组合根或直构 InMemorySkillLoader） | `tests/unit/application/skills/test_skill_selector.py` | Task 3 |
| **TDD 单元测试** | LoadAgentProfileUseCase | 编排顺序（get_by_id→守卫→加载→L1→计量→发布）/443/441/442 传播/发布失败两分支不回滚/token 计量口径 | `tests/unit/application/use_cases/test_agent_profile_loading.py` | Task 4 |
| **TDD 单元测试** | agent_cli load-profile | parser 契约（子命令+--agent-id 必填）/UUID 守卫（非法串→201）/裸调用 exit 2/成功输出摘要/退出码 0-1-2（monkeypatch 注入先例：5-1 Task 5 定稿模式） | `tests/unit/interfaces/cli/test_agent_cli.py`（**追加**——5-1 CLI 测试在此路径，源已迁 entrypoints 但测试目录未迁，跟随现状不移动） | Task 5 |
| **TDD 契约测试** | agent_profile_loader / skill_selector / agent_profile_use_case | 11 维度断言 | `tests/contracts/test_port_contract_agent_profile_loader.py`、`test_port_contract_skill_selector.py`、`test_port_contract_agent_profile_use_case.py` | Task 2/3/4 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收（AC-1~AC-6 全场景表 14 场景，**含 AC-6.3 收尾场景**——对齐 5-1 先例全部场景 Task 0 一次落盘） | `tests/acceptance/test_acceptance_agent_profile_loading.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数（5-1 模板模式，含收尾场景步骤） | `tests/acceptance/test_acceptance_agent_profile_loading.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | 完成清单最终确认（AC-6.3 场景转绿核对——Task 0 已落盘，Task 8 不新增场景防收集数漂移） | 同上两文件（Task 0 落盘的收尾场景） | Task 0/8 |
| **集成测试** | 真实 Redis + 真实文件全链路 | instantiate→load-profile→读回→清理（TestTenant/uuid 隔离）+ 性能（P95/成功率） | `tests/integration/test_integration_agent_profile_loading.py` | Task 6 |
| **SDD 架构验证** | 六边形约束 | domain 零依赖+零 application import/依赖方向/组合根唯一装配/CLI 边界 | `tests/unit/architecture/test_arch_agent_profile_loading.py` | Task 7 |

> **测试文件命名约束（记忆 feedback_no_story_number_in_filenames）：** 功能性命名，**禁止** `_5_2` 类故事编号后缀。上表文件名均已合规。

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- P0 阻断门禁
- [ ] **应用层覆盖率 ≥85%**（本 Story 核心增量层：LoadAgentProfileUseCase + SkillSelector + 两端口——epics TDD 要求「应用层≥85%」）
- [ ] **基础设施层覆盖率 ≥75%**（MarkdownAgentProfileLoader 归入）
- [ ] **集成测试覆盖率 ≥75%**（epics TDD 要求文字项——仓库无按测试类型分列的覆盖率门禁，实际以整体≥80% + Makefile 分层门禁代偿执行，Task 8 收尾说明口径，对齐 5-1 处理）
- [ ] 覆盖率命令按 Makefile 惯例（分层阈值不用 `--cov=src.<layer>` 形式，Makefile L279 明令禁止）

> 本 Story 为功能 Story（非骨架），**不适用**骨架覆盖率豁免。

#### 代码质量门禁

- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）
- [ ] **并行测试** `poetry run pytest tests/ -n 8` 通过；连续 5 次运行无随机失败
- [ ] 提交信息禁止 AI 署名（记忆 commit_no_coauthor）

#### 测试隔离约束

> ⚠️ **核心原则：测试自包含，不污染共享状态，不依赖执行顺序。**

| 约束类型 | 本 Story 执行规则 |
|---------|-----------------|
| 资源唯一性 | Redis 键经 `build_key("agent", agent_id)`——uuid4 天然唯一（instantiate 产生）；tmp_path 档案目录由 pytest 每测试独立创建自动清理；清理靠 context 记录 agent_id 后逐键精确 delete |
| 外部服务隔离 | 真实 Redis 仅测试环境（`SISYS_USE_TEST_PORTS=1`→6380）；teardown 逐键精确 delete；**禁止** flush/全库 delete/通配 delete_pattern（`sisys:agent:*` 多 worker 共享 6380 会误删并行键） |
| 文件资产隔离 | AC-1.2/1.3/2.3 的档案破坏场景一律 **tmp_path 构造 + 构造注入 profile_root**——**禁止修改内置 `configs/agents/profiles/ceo/` 资产**（内置资产被破坏会污染其他测试且属生产资产损坏） |
| Redis 跨循环 | Redis 客户端**场景级独立创建、同循环 teardown 关闭**（记忆 acceptance_redis_client_cross_loop_issue）；`_run_async` 统一经 `context["_loop"]`；instantiate 与 load-profile 两步共用同一场景级客户端（**仅适用需 instantiate 的四场景 AC-1.1/4.1/5.1/5.2**——其余场景见 BDD 约束节分档） |
| asyncio 约束 | BDD 步骤禁 `@pytest.mark.asyncio`；CLI 入口（独立进程）用 `asyncio.run()` 合法；`asyncio.Lock` 若使用必须类变量 |
| Mock 边界 | **单元测试** Mock 端口（`AsyncMock(spec=Protocol)` + `_make_*` 工厂）；**集成测试**真实 Redis + 真实文件优先；**验收测试禁止 mock**（InMemoryEventBus 是真实实现类非 mock；档案用 tmp_path 真实文件；skill_loader 经组合根 resolve 真实实例） |
| bootstrap 禁令 | **验收测试禁止调用 `bootstrap()`**——组合根已由 tests/conftest.py session 级 `_bootstrap_once` 完成引导；同进程二次 bootstrap 抛 ConflictError。端口获取直接 `from src.domain.ports.resolver import resolve` |
| resolve 纪律 | 功能场景一律手动组装（`MarkdownAgentProfileLoader(profile_root=...)` 直构 / 手动仓储 + 场景级客户端）；`resolve` 仅限**无连接构造**端口（`agent_profile_loader`/`skill_loader`/`skill_selector`——本地静态文件只读、无网络连接，跨循环安全；注意 `skill_loader` 构造期同步读 TOOLS.md 一次，非零 IO 但确定性本地读）且 AC-6.1 接线断言禁发命令——**禁 resolve `agent_repository`（SCOPED）与用例端口**（SINGLETON redis_client 跨循环死连接，5-1 文档审查修复 #23 教训） |
| 清理粒度 | 每个测试只清理自己创建的资源；fixture 显式声明依赖 |
| 性能测试 | `pytestmark` 标记 `benchmark`；xdist 下用 `xdist_group("agent-profile-loading")` 串行化计时场景（仅保同组串行不保独占 CPU；`-n auto` 下抖动超标时以 `-n 0` 结果为准）；硬断言 500ms 对典型 <20ms 链路约 25 倍余量 |

**禁止行为：**
- ❌ 验收/集成测试 mock 领域服务/用例/仓储/加载器（真实服务优先）
- ❌ 手动 delete/truncate 全库资源
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`
- ❌ 测试写坏内置生产档案资产（configs/agents/profiles/ceo/）
- ❌ 共享 session 级 Redis 客户端跨场景复用（经 resolve() 获得的有状态 SINGLETON 即此种共享）

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 七档案完整加载（六 .md + TOOLS L1） | Task 2/4 | 加载器 + 用例组装 | test_markdown_agent_profile_loader.py / test_agent_profile_loading.py（unit+acceptance） |
| AC-1 | 档案失败路径（缺失/空白/超限/不可读） | Task 2 | 加载器异常路径 | test_markdown_agent_profile_loader.py / acceptance AC-1.2/1.3/2.3 |
| AC-2 | agent 存在性守卫（443） | Task 1/4 | 异常定义 + 用例第一步 | test_agent_exceptions.py / test_agent_profile_loading.py / acceptance AC-2.2 |
| AC-2 | 角色守卫（441 复用）+ 守卫顺序 | Task 4 | 用例编排（单测 Mock 调用序） | test_agent_profile_loading.py |
| AC-2 | 档案内容验证（非空/64KB） | Task 1/2 | VO 校验 + 加载器实施 | test_agent_profile.py / acceptance AC-2.1 |
| AC-3 | L1 元数据 23 条 + token ≤1200 | Task 4 | 用例 L1 组装与计量 | test_agent_profile_loading.py / acceptance AC-3.1 |
| AC-3 | SkillSelector ACTIVE 过滤 | Task 3 | SkillSelector 实现 | test_skill_selector.py / acceptance AC-3.2 |
| AC-4 | 启动上下文预算（分项+总量） | Task 4 | 用例计量 | test_agent_profile_loading.py / acceptance AC-4.1 |
| AC-4 | AgentProfileLoaded 事件 + 双登记 | Task 1/4 | 事件定义 + 发布点接线 | test_agent_events.py / acceptance AC-4.1/6.2 |
| AC-5 | P95<500ms + 成功率 100% | Task 6 | 性能集成测试 | test_integration_agent_profile_loading.py / acceptance AC-5.1/5.2 |
| AC-6 | 三端口契约 | Task 2/3/4 | 契约测试 | tests/contracts/ 三文件 |
| AC-6 | 架构合规 + CLI 接线 | Task 5/7 | CLI 子命令 + 架构测试 | test_agent_cli.py（追加）/ test_arch_agent_profile_loading.py |
| 收尾 | 完成清单确认 | Task 8 | 收尾验收场景 | acceptance AC-6.3 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 独立完成 红→绿→变异→重构 循环，禁止将测试推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部（AC-1 ~ AC-6）

> **目的：** 在进入代码实现前，落地本 Story SDD 规范节定义的全部 Schema、端口契约、异常契约与 Gherkin，并完成红阶段验证。

- [x] Subtask 0.1: 按「领域事件 Schema」「数据模型」「端口契约清单」「领域异常契约」四节定稿全部契约（逐项核对签名/字段/编码无歧义后确认；特别核对 `ToolMetadata.status` 字段与 `get_all_slugs()` 返回形态——SkillSelector 实现的直接输入）
- [x] Subtask 0.2: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_agent_profile_loading.feature`（14 场景清单，严格按 R6：5-1 主体基准 + postgresql 模板三项继承先例 + AC 编号命名）
- [x] Subtask 0.3: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_agent_profile_loading.py`（@scenario 显式绑定 + context dict + `_run_async` + 场景级 ping 门控下沉 + **新模块延迟 import** + 显式 pytestmark 列表）
- [x] Subtask 0.4: 运行验收测试，确认失败（🔴 红阶段验证；ModuleNotFoundError/AssertionError/未注册端口的解析期错误（registry miss，如 `resolve("skill_selector")` 未注册）三类均为合法红；**红阶段失败形态不能证明断言正确性——断言活性由各 Task 变异阶段与收集数校验背书**；**前提：Redis 在线**——含 Redis 依赖场景 ping 失败则 skip 无失败可确认；**校验收集场景数 == 14**——`pytest --collect-only -q`，防 @scenario 绑定名与 .feature 不匹配的收集期 ScenarioNotFound 或漏绑定静默不收集）
- [x] Subtask 0.5: 链路接线断言清单 L1-L8 逐项确认处置（本 Story 接线 6 项 / deferred 保持 2 项）+ **补登记 deferred-work.md 观察项：组合根 `l0_storage`（L268-276）与 `memory_file_storage`（L1108-1116）impl 字符串指向不存在的模块路径（实际在 `src/infrastructure/storage/fs/` 下）——休眠资产路径失效，激活时必炸**（对齐 5-1 Task 0 补登记 session_storage 先例）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕
- [x] 验收测试运行失败（预期行为，红阶段确认——14 场景全 FAILED，均为 ModuleNotFoundError/registry miss 合法红；收集数 == 14 校验通过）
- [x] deferred-work.md 补登记组合根 impl 路径失效观察项（L7/L8 既有登记核对通过——heartbeat_scheduler/L0/memory 字符串在位）

---

### Task 1: 领域层——档案异常 442/443 + AgentProfileLoaded 事件 + AgentProfile 值对象

**关联 AC:** AC-1（失败路径）、AC-2（443/验证）、AC-4（事件）

> **目的：** 落地领域契约层：档案/未找到异常（442/443）、领域事件（含双通道登记）、档案值对象（六档案 + 自校验），为下游 Task 提供词汇。

#### TDD 循环 A：agent 子域异常追加（442/443）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 追加 `tests/unit/domain/exceptions/test_agent_exceptions.py`（AgentProfileError/AgentNotFoundError：构造/context 暴露 `{role, profile_path, reason}` 与 `{agent_id}`/to_dict/HTTP 映射 500 vs 404/编码 EXCEPTION_442、443；HTTP 映射断言经 `src.interfaces.api.exception_handlers._get_http_status` 反向验证，先例 test_debate_exceptions.py L188） |
| 🟢 绿 | 在 `src/domain/exceptions/agent_exceptions.py` 追加两类（构造形态对齐 AgentConfigError/AgentRoleNotSupportedError；模块 docstring 补 442/443 继承链理由） |
| 🟡 变异 | 突变 `EXCEPTION_HTTP_MAP` 中 443 条目（404→400）→ HTTP 映射测试红 → 还原绿 |
| 🔄 重构 | `_CLASS_TO_SUBDOMAIN` 追加两映射 + domain `__init__.py` 导出 + exception_handlers.py `EXCEPTION_HTTP_MAP` 注册 + 同步 sisys-uni-exception-design.md §3.3.2 表（442/443 行替换预留行）；ruff+mypy |

#### TDD 循环 B：AgentProfileLoaded 事件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 追加 `tests/unit/domain/events/test_agent_events.py`（四 kw_only 必填字段/默认 event_type/aggregate_id UUID 对象/aggregate_type="Agent"/冻结性/缺单字段 TypeError——红阶段自纠先例：类型注解不强制运行时校验，用真正省略字段构造断言） |
| 🟢 绿 | 在 `src/domain/events/agent_events.py` 追加 AgentProfileLoaded（frozen dataclass，Schema 见 Task 0）+ `events/__init__.py` 导出 |
| 🟡 变异 | 突变 `aggregate_type="Agent"` → `"AgentX"` → 断言红 → 还原绿 |
| 🔄 重构 | `configs/event_channels.yaml` + `channel_router.py DEFAULT_MAPPINGS` 双登记（对齐 AgentInstantiated 条目结构）；`architecture.md §10.1` 领域事件列表追加 AgentProfileLoaded 行；ruff+mypy |

#### TDD 循环 C：AgentProfile 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_agent_profile.py`（frozen/agent_id UUID 与 role 枚举类型校验/六字段 isinstance(str) 守卫（**先类型后空值**——truthy str 越过判空的 5-1 R2-F2 教训）/strip 后非空（空串/纯空白/纯换行 → 442）/全字段合法构造往返） |
| 🟢 绿 | 实现 `src/domain/value_objects/agent_profile.py`（Schema 见 Task 0；校验抛 AgentProfileError 442） |
| 🟡 变异 | 突变六字段之一的 strip 判空（删 `not xxx.strip()` 分支）→ 空白档案测试红 → 还原绿 |
| 🔄 重构 | Google 风格全中文注释（docstring 含 or.md 四.1.[1] 与 architecture.md §11.2.2 出处）；ruff+mypy |

- [x] Subtask 1.1: 🔴 红 — 异常测试（循环 A）
- [x] Subtask 1.2: 🟢 绿 — 442/443 实现
- [x] Subtask 1.3: 🟡 变异 + 🔄 重构 — 登记五处（`_CLASS_TO_SUBDOMAIN`/`exceptions __init__`/`exception_handlers.py EXCEPTION_HTTP_MAP`/**`tests/unit/interfaces/api/test_exception_handlers.py` Map 完备性期望集补 442/443 行**（既有测试期望集枚举断言，漏改不红——显式列入防漏）/设计文档 §3.3.2）——变异实证：443 HTTP 映射 404→400 突变使 2 测试红、还原绿
- [x] Subtask 1.4: 🔴 红 — 事件测试（循环 B）
- [x] Subtask 1.5: 🟢 绿 — AgentProfileLoaded 实现
- [x] Subtask 1.6: 🟡 变异 + 🔄 重构 — 事件双登记 + §10.1——变异实证：AgentProfileLoaded aggregate_type "Agent"→"AgentX" 突变使 2 测试红、还原绿（注：sed 首次误突变 AgentDecided 位——其断言在 test_core_events.py，修正为精确突变 AgentProfileLoaded 位）
- [x] Subtask 1.7: 🔴🟢🟡🔄 — AgentProfile 值对象完整循环（循环 C）——变异实证：strip 判空分支突变使 18 测试红、还原绿；修正两处误写 `# type: ignore`（项目红线零容忍）
- [x] Subtask 1.8: 运行 `poetry run pytest tests/unit/domain/ -v` 全绿（含既有 8 项异常套件与 5-1 全部测试不回归——2975 passed 零回归；ruff/mypy 全过）

**完成标准/Definition of Done:**
- [x] 异常/事件/值对象契约实现且既有套件零回归
- [x] `grep -r "EXCEPTION_44[23]" src/domain/exceptions/` 无碰撞
- [x] 双登记两处 grep 可达

---

### Task 2: 档案资产 + MarkdownAgentProfileLoader + 端口

**关联 AC:** AC-1（六档案加载/失败路径）、AC-2（内容验证）

> **目的：** 交付六档案静态资产（CEO）+ 档案加载端口 + Markdown 基础设施实现 + 组合根注册。

#### TDD 循环 A：加载器与内置资产

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/agent_orch/test_markdown_agent_profile_loader.py`（tmp_path 真实文件 IO 零 mock，档案一律建于 `tmp_path/"ceo"/` 角色子目录：正常六档案构造 → AgentProfile 全字段一致/**目录缺失**（profile_root 指向不存在路径）→ 442/**单文件缺失**（删 IDENTITY.md）→ 442 且 context 含文件名/**内容空白**（空串/纯空白/纯换行三形态）→ 442 **且 context.profile_path 含对应文件名**（钉住判空主检在加载器——DC-5 观测锚点，防实现滑入 VO 兜底路径致 context 失文件名）/**大小超限**（>65536 字节文件）→ 442/**编码非法**（GBK 字节写文件）→ 442/**未知文件忽略**（目录多放 README.md → 六档案加载成功且字段不受污染——前向兼容策略）/**agent_id/role 透传**（VO 归属锚点断言）；另内置资产冒烟：默认 profile_root 加载 `profiles/ceo/` 六档案成功且 IDENTITY 含「CEO」） |
| 🟢 绿 | 实现 `src/application/ports/agent_profile_loader.py`（Protocol，签名见 Task 0）+ `src/infrastructure/agent_orch/markdown_agent_profile_loader.py`（`profile_root` 构造注入默认仓库根四级上溯锚定 `configs/agents/profiles`——对齐 YamlAgentConfigLoader L31；`asyncio.to_thread(Path.read_text, path, encoding="utf-8")` 逐档案读取——**必须显式 encoding**，对齐 yaml_agent_config_loader `_read_yaml` 与 InMemorySkillLoader 先例（裸 read_text 依赖 locale，非 UTF-8 locale 下中文资产会误判 442）；大小上限 `PROFILE_FILE_MAX_BYTES = 65536` 模块常量（**字节口径**：读前 `stat().st_size` 或读后 `len(content.encode("utf-8"))` 判定——`len(content)` 字符口径中文下差至 3 倍不用，与常量名 MAX_BYTES 对齐；资产随代码分发无恶意大文件面）；`Path.read_text` 的 OSError/UnicodeDecodeError 逐类包装 442（reason 分列「档案不可读/编码非法」）；VO 构造在加载器内（六字段齐后一次构造，VO 校验兜底））+ 新建六档案资产 `configs/agents/profiles/ceo/{IDENTITY,CODE,SOUL,USER,MEMORY,HEARTBEAT}.md`（内容红线见 Task 0 数据模型节；IDENTITY+SOUL 合计 ≤500 tokens——编写后以 `len(chars)//4` 实测断言） |
| 🟡 变异 | 突变固定名映射（"IDENTITY.md"→"IDENTITY_X.md"）→ 加载测试红 → 还原绿 |
| 🔄 重构 | 组合根注册 `agent_profile_loader`（SINGLETON，lambda + `__import__` 延迟加载，仿 5-1 段形态）+ 契约测试 `tests/contracts/test_port_contract_agent_profile_loader.py`（11 维度；DummyResolver 零依赖直构）；ruff+mypy |

- [x] Subtask 2.1: 🔴 红 — 加载器测试（正常加载 + 七类边界：目录缺失/单文件缺失/内容空白/大小超限/编码非法/未知文件忽略/agent_id-role 透传；另含内置资产冒烟——红阶段失败形态与其余用例同为 ModuleNotFoundError（模块先于资产缺失暴露），属合法红——14 failed 确认）
- [x] Subtask 2.2: 🟢 绿 — 端口 + MarkdownAgentProfileLoader + 六档案资产（14 passed；大小上限读前 stat 字节口径；GBK/不可解码双形态编码测试；恰好 65536 字节边界通过用例）
- [x] Subtask 2.3: 🟡 变异 + 🔄 重构 — 组合根注册 + 契约测试——变异实证：固定名映射 "IDENTITY.md"→"IDENTITY_X.md" 突变使 11 测试红、还原绿；契约测试 12 项全过；resolve("agent_profile_loader") 可达 isinstance 合规（链路 L1 绿灯）
- [x] Subtask 2.4: 内置资产 token 实测（IDENTITY 322 chars + SOUL 192 chars = 514 chars / 128 tokens——远低于 chars≤2000 / tokens≤500 红线，PASS）

**完成标准/Definition of Done:**
- [x] 七类失败/边界路径 + 成功路径 + 未知文件忽略全覆盖（真实文件 IO，见 Subtask 2.1 清单）
- [x] 契约测试通过，`resolve("agent_profile_loader")` 可达（链路 L1 绿灯）
- [x] domain 层零依赖（agent_profile.py 仅标准库 + AgentRole——ruff/mypy 全过）

---

### Task 3: SkillSelector（GAP-CRITICAL-08b 交付）

**关联 AC:** AC-3（ACTIVE 列表）

> **目的：** 按 interface-design.md §5.5 权威口径交付 SkillSelector——`list_active_skills()` 纯查询（ACTIVE 过滤），消除「硬编码选择器违反 P5」GAP。
> ⚠️ **禁止实现**关键词权重/语义相似度/Top-K 推荐（epics L1546 旧文案已废弃——偏离声明 D-1）。

#### TDD 循环 A：SkillSelector

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/skills/test_skill_selector.py`（真实 `InMemorySkillLoader` 直构组合（真实服务优先——`InMemorySkillLoader()` 无参可用，构造期同步读 TOOLS.md 一次（本地静态文件只读、无连接），单测可接受）: `list_active_skills()` 返回 23 条/全部 `status == "active"`/与 `get_all_slugs()` 清单同序（零排序副作用断言——`[m.slug for m in result] == get_all_slugs()`）/返回类型 tuple；Mock 分支：`AsyncMock(spec=SkillLoaderPort)` side_effect 阶段化——某 slug 元数据 status="deprecated" → 结果不含该条（过滤行为断言）/skill_loader 抛 SkillNotFoundError → 传播不静默） |
| 🟢 绿 | 实现 `src/application/ports/skill_selector.py`（Protocol，签名见 Task 0）+ `src/application/skills/registry/__init__.py`（包入口——目录已存在为空）+ `src/application/skills/registry/selector.py`（`SkillSelector` 组合注入 `skill_loader: SkillLoaderPort`；实现 = `get_all_slugs()` 枚举 → 逐 slug `await skill_loader.load_metadata(slug)` → `status == "active"` 过滤 → 按 slug 清单序 tuple 返回；模块 docstring 引用 interface-design.md §5.5 与 GAP-CRITICAL-08b） |
| 🟡 变异 | 突变过滤条件（`== "active"` → `!= "active"`）→ 23 条断言红（结果为 0 条）→ 还原绿 |
| 🔄 重构 | 组合根注册 `skill_selector`（SINGLETON，lambda resolve `skill_loader`）+ 契约测试 `tests/contracts/test_port_contract_skill_selector.py`（11 维度；DummyResolver 提供 `skill_loader` 依赖名——直构 `InMemorySkillLoader()` 本地文件只读、契约测试可接受）；ruff+mypy |

- [x] Subtask 3.1: 🔴 红 — Selector 测试（真实 + Mock 双分支——8 failed 确认）
- [x] Subtask 3.2: 🟢 绿 — 端口 + SkillSelector 实现（含 registry/__init__.py 包入口；8 passed）
- [x] Subtask 3.3: 🟡 变异 + 🔄 重构 — 组合根注册 + 契约测试——变异实证：过滤条件 `== "active"` → `!= "active"` 突变使 4 测试红（23 条断言结果为 0 条）、还原绿；契约测试 12 项全过；resolve("skill_selector") 可达 + list_active_skills() 实测返回 23 条（链路 L2 绿灯 + L6 skill_loader 新消费方接线验证）

**完成标准/Definition of Done:**
- [x] ACTIVE 过滤行为有断言守护（变异实证记录在案）
- [x] `resolve("skill_selector")` 可达（链路 L2 绿灯）
- [x] 零排序/零打分代码（GAP-CRITICAL-08b 合规——selector.py 仅枚举+过滤+tuple，无 sorted/score/weight）

---

### Task 4: LoadAgentProfileUseCase 应用服务 + L1 组装 + 事件发布接线

**关联 AC:** AC-1（编排）、AC-2（守卫）、AC-3（L1）、AC-4（计量/发布）

> **目的：** 交付档案加载用例编排：**agent 存在性守卫 → 角色守卫 → 六档案加载 → L1 组装 → token 计量 → 发布事件**；完成用例端口注册。
> ⚠️ **守卫顺序**：存在性（443）→ 角色（441）→ 加载（442）——存在性必须最先（不存在实体的 role 无从判定）；角色守卫先于档案加载（非 CEO 角色的档案目录不存在，先 441 才可达——对齐 5-1「守卫先于加载」教训的级联应用）。

#### TDD 循环 A：用例编排

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/use_cases/test_agent_profile_loading.py`（Mock 端口：`AsyncMock(spec=AgentProfileLoader)`、`AsyncMock(spec=AgentRepository)`、`AsyncMock(spec=SkillSelectorPort)`；**发布方分两类**——成功编排与事件字段断言用 InMemoryEventBus 真实类（捕获 `published_events`），**publish 失败两分支换 `AsyncMock(spec=EventPublisher)` 注入**（raise 分支 `side_effect=RuntimeError`；is_success==False 分支返回空 results 的 `PublishResult`——5-1 test_agent_instantiation.py L264-277 先例。⚠️ 真实总线的失败面从用例不可达：新 event_id 不触发去重、成功路径 is_success 恒 True，勿在真实总线上构造失败分支）；成功编排顺序断言（**get_by_id → 守卫 → loader.load → list_active_skills → publish 调用序**——Mock calls 序断言 + `_TracingEventBus(InMemoryEventBus)` 子类记录 publish 段（5-1 L50-67 先例，真实总线非 Mock 其调用不入 Mock calls））；get_by_id 返回 None → AgentNotFoundError 443 且 loader 未被调用（context 断言 `error.context["agent_id"] == str(agent_id)`——raise 侧 `str(agent_id)`，对齐 5-1 `role=role.value` 先例）；非 CEO 实体（Mock get_by_id 返回 role=CFO 实体）→ AgentRoleNotSupportedError 441 且 loader 未被调用；loader 失败（442）传播；list_active_skills 恰被调用一次且其返回值进入 DTO tools_l1（ACTIVE 过滤逻辑单点在 SkillSelector——用例透传不断言过滤，Task 3 已覆盖）；token 计量 = (identity+soul+L1 视图 chars)//4 口径断言；publish 失败两分支 → 结果仍返回且记日志不回滚；返回 DTO 四字段；事件 `active_skill_count` 断言写 `== len(result.tools_l1)` 同源派生，勿写字面量） |
| 🟢 绿 | 实现 `src/application/use_cases/agent_profile_loading.py` `LoadAgentProfileUseCase`（构造注入 profile_loader/repository/skill_selector/event_publisher 四端口；`async execute(agent_id: uuid.UUID) -> AgentProfileLoadResult`；守卫链如上；L1 组装：`tools = await self._skill_selector.list_active_skills()` 一次调用（**注入 SkillSelector 而非直组 skill_loader**——ACTIVE 过滤逻辑单点在 SkillSelector，依赖数与直组相同而消重，DC-8）；计量：`startup_context_tokens = _estimate(profile.identity + profile.soul + L1 视图文本)`（L1 视图文本 = `"\n".join(f"{m.tool_name}: {m.description}" for m in tools)` 换行拼接——**分隔符定稿 `\n`，AC-3 口径②**，`_estimate_tokens` 同款 chars//4，模块内私有函数）；事件构造四字段 + 发布两分支记日志不回滚（照抄 5-1 L128-145 形态——`is_success==False` 分支普通 `logger.error`、raise 分支带 `exc_info=True`，两分支形态照旧不要统一）） |
| 🟡 变异 | 突变发布调用行（注释掉 publish）→ 「事件已发布」断言红 → 还原绿（Epic 4 零发布教训防线）；突变守卫顺序（**将角色守卫移至 `loader.load` 之后**——「441 检查移到 get_by_id 前」不可编码：role 取自 get_by_id 返回的实体）→ 「非 CEO 实体 → 441 且 loader 未被调用」断言红（结果型断言：错误码 + Mock 未调用，非字面调用序）→ 还原绿 |
| 🔄 重构 | `AgentProfileLoadResult` DTO（模块内定义，Schema 见 Task 0）；组合根注册 `agent_profile_use_case`（SINGLETON，工厂 resolve 四依赖）+ 契约测试 `tests/contracts/test_port_contract_agent_profile_use_case.py`（DummyResolver 提供四依赖名）；ruff+mypy |

- [x] Subtask 4.1: 🔴 红 — 用例单元测试（含编排顺序与异常传播——12 failed 确认）
- [x] Subtask 4.2: 🟢 绿 — LoadAgentProfileUseCase 实现（12 passed；发布两分支形态照抄 5-1——is_success False 普通 logger.error / raise 带 exc_info=True）
- [x] Subtask 4.3: 🟡 变异 — 发布点 + 守卫顺序双突变实证（① 注释 publish 调用 → 事件断言 + 编排顺序断言双红、还原绿；② 角色守卫移至 loader.load 之后 → 「441 且 loader 未被调用」断言红、还原绿）
- [x] Subtask 4.4: 🔄 重构 — DTO + 组合根注册 + 契约测试（12 项全过；resolve("agent_profile_use_case") 可达 isinstance 合规——链路 L3 绿灯；修复 E402/F841 两处 ruff 根因）
- [x] Subtask 4.5: 验收场景 AC-1.1/2.2/3.1/4.1 转绿核对（**按场景分档组装**——12/14 转绿：AC-1.1/1.2/1.3/2.1/2.2/2.3/3.1/3.2/4.1/5.1/5.2/6.1 全绿；余 AC-6.2/6.3 为 Task 5-7 预期未交付；**实施注记**：AC-3.1 步骤文本「L1 元数据清单…」与 AC-1.1「L1 工具元数据清单…」异文，补独立 then 绑定后转绿）

**完成标准/Definition of Done:**
- [x] 用例六步编排顺序有断言守护（calls 序断言非仅结果断言——`calls == ["get_by_id", "load", "list_active_skills", "publish"]`）
- [x] `resolve("agent_profile_use_case")` 可达（链路 L3 绿灯）+ skill_loader 新消费方接线（链路 L6 绿灯）
- [x] 发布点变异实证记录在案

---

### Task 5: CLI 子命令 load-profile

**关联 AC:** AC-6（接线）、AC-2（UUID 守卫）

> **目的：** 接口层最小入口扩展，兑现 CLI 侧「档案加载」可操作性（R4 接口适配）；消除「已实现未接线」。
> **接线模式：** 扩展 `src/entrypoints/agent_cli.py`（D1 方案 A 后入口位置）——`subparsers.add_parser("load-profile")` + `--agent-id` 必填；`bootstrap()` + `resolve("agent_profile_use_case")` + 退出码契约沿用。

#### TDD 循环 A：CLI 子命令

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 追加 `tests/unit/interfaces/cli/test_agent_cli.py`（**新增 load-profile 用例的红形态 = SystemExit 2**——argparse 未注册子命令即拒，UUID 守卫同（守卫代码尚未触达）；属单元层合法红（Task 0.4 三类合法红为验收域清单，不含此形态故此处显式注明）。build_parser 参数契约：`load-profile` 子命令 + `--agent-id` 必填；**UUID 守卫红线**：合法 UUID 字符串成功、非法串（"not-a-uuid"/空串）→ `ValidationError` EXCEPTION_201 且 context 携带原始输入（**禁止裸 uuid.UUID ValueError 逃逸**）；裸调用 `main([])` → SystemExit 2（既有断言不回归）；成功路径输出多行摘要含「IDENTITY.md: OK」「活跃技能」「启动上下文」字样（monkeypatch `agent_cli` 模块级 `bootstrap`/`resolve` 属性——5-1 Task 5 定稿的唯一可行注入）；业务异常路径退出码 1 且 stderr 含 `EXCEPTION_44`；`instantiate` 子命令既有测试零回归） |
| 🟢 绿 | 在 `src/entrypoints/agent_cli.py` 追加 `load-profile` 子命令处理（`--agent-id` str 参数；函数体内 `try: agent_id = uuid.UUID(value.strip()) except ValueError: raise ValidationError(...201)`——**argparse type= 不用 uuid.UUID**（会把 ValueError 转 usage error exit 2 绕过统一异常体系）；`asyncio.run()` 执行用例；输出：六档案逐行 `IDENTITY.md: OK (N chars)` + `活跃技能: N` + `启动上下文: N tokens`；Redis 池 finally 关闭沿用 `_close_redis_pool`（本子命令同样读 Redis）；模块 docstring 补 load-profile 幂等只读语义声明） |
| 🟡 变异 | 突变 UUID 守卫（删 except 分支）→ 非法串测试红（ValueError 逃逸被断言捕获）→ 还原绿 |
| 🔄 重构 | 输出格式收敛、docstring 规范；pyproject script 无需改动（`sisys-agent` 已注册）核对；ruff+mypy |

- [x] Subtask 5.1: 🔴 红 — CLI 追加测试（含 UUID 守卫红线用例——11 failed 确认：SystemExit 2/AttributeError 合法红）
- [x] Subtask 5.2: 🟢 绿 — load-profile 子命令实现（32 passed——含 instantiate 21 项零回归；`_parse_agent_uuid` 守卫映射 ValidationError(201) context 携带原始输入；`_print_profile_summary` 六档案逐项 `(N chars)` + 动态活跃技能数 + token 计量）
- [x] Subtask 5.3: 🟡 变异 — UUID 守卫突变实证（删 except 分支 → 3 测试红（ValueError 逃逸被 pytest.raises(ValidationError) 捕获）、还原绿）
- [x] Subtask 5.4: 🔄 重构 — main 分发重构为 `_run_load_profile_cli`/`_run_instantiate_cli` 两私有函数（根因修复 mypy Optional 类型错误——守卫与执行同分支作用域，类型自然收窄）；模块 docstring 补 load-profile 幂等只读语义；ruff/mypy 全过
- [x] Subtask 5.5: 端到端冒烟——`REDIS_PORT=6380 poetry run sisys-agent instantiate --role ceo` 产出 agent_id → `load-profile --agent-id <uuid>` 真实执行输出六档案摘要（IDENTITY 322 chars…HEARTBEAT 223 chars + 活跃技能: 23 + 启动上下文: 346 tokens）exit 0（链路 L5 绿灯）；失败路径实测：非法 UUID → `[EXCEPTION_201]` exit 1（无 ValueError 逃逸）、不存在 agent_id → `[EXCEPTION_443]`、缺参数 → argparse usage error exit 2；冒烟键精确清理 deleted=1

**完成标准/Definition of Done:**
- [x] `sisys-agent load-profile` 端到端可执行（摘要 stdout、退出码 0/1/2 三路径实测）
- [x] 非法 UUID 统一 ValidationError(201)（无 ValueError 逃逸）
- [x] `instantiate` 子命令零回归

---

### Task 6: 集成测试 + 性能验收（真实 Redis + 真实文件）

**关联 AC:** AC-5

> **目的：** 真实环境全链路集成验证 + 性能门禁（P95<500ms、成功率 100%）。
> **性质说明：** 验证型集成/性能测试（非先红后绿循环）——被测链路已由 Task 2-4 交付，**测试编写后直接转绿为合法预期**；若编写后即红则暴露真实集成缺陷须修复至绿；断言活性由变异阶段（阈值突变）背书。

#### TDD 循环 A：集成与性能

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_agent_profile_loading.py`（fixture 链：`get_test_env()` → `real_redis`（integration conftest L193-220，ping 失败 pytest.skip）→ 手动组装 `RedisAgentRepository(adapter=RedisAdapter(real_redis))` + `resolve("agent_profile_loader")` + `resolve("skill_selector")`（均无连接构造、跨循环安全）+ `InMemoryEventBus` + 5-1 用例（先 instantiate 产生 agent）+ 本 Story 用例手动实例化；场景：① instantiate→load-profile 全链路→六档案内容非空+23 工具+计量断言→teardown 按 context 记录的 agent_id 逐键精确 delete ② P95 计时（perf_counter，warmup 剔除 1 次 + ≥20 采样 + `statistics.quantiles(n=20)[18]` < 500ms，`benchmark` marker + `xdist_group("agent-profile-loading")` 串行化）③ 20 次重复加载成功率 100%（同 agent_id 复用——幂等只读设计行为）） |
| 🟢 绿 | 全链路已由 Task 2-4 交付，测试应直接转绿（若红则暴露真实集成缺陷，修复至绿） |
| 🟡 变异 | 突变 P95 断言阈值（500→0.5）→ 性能测试红（证明计时断言活着）→ 还原绿 |
| 🔄 重构 | 场景命名收敛、超时防护；ruff+mypy |

- [x] Subtask 6.1: 🔴 红 — 集成与性能测试编写（验证型——直接转绿为合法预期，3 passed）
- [x] Subtask 6.2: 🟢 绿 — 真实 Redis + 真实文件全链路通过（全链路含收尾 scan_iter 复核零残留 + P95 + 20 次成功率 + 事件计数 20）
- [x] Subtask 6.3: 🟡 变异 — 阈值突变实证（500→0.5 → P95 测试红、还原绿）
- [x] Subtask 6.4: 🔄 重构 — 隔离与稳定性（连续运行 5 次全绿无随机失败；ruff 全过）
- [x] Subtask 6.5: 验收场景 AC-5.1/5.2 转绿核对（2 passed）

**完成标准/Definition of Done:**
- [x] 真实 Redis 环境全绿（不可用时动态 skip 而非失败——real_redis fixture ping 失败 pytest.skip）
- [x] P95<500ms 与成功率 100% 断言有变异实证背书
- [x] teardown 零残留（按 context 记录的 agent_id 逐键精确清理，无通配删除——收尾 scan_iter 复核残留 0）

---

### Task 7: SDD 架构约束验证测试

**关联 AC:** AC-6

> **性质说明：** SDD 规范验证测试（非 TDD 单元测试）——验证前序 Task 产出是否符合六边形架构规则。**断言对象已由 Task 1-5 交付，编写后直接转绿为合法预期**（同 Task 6 形态——不构造合法红）；断言活性由变异阶段背书（四验证器均为恒真风险池——Epic 4 教训「8/13 Story 恒真断言」的直接暴露面）。

#### TDD 循环（验证型形态）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | （无——验证型测试，见性质说明） |
| 🟢 绿 | 编写四验证器并直接转绿（若红则暴露 Task 1-5 产出的真实架构违规，修复至绿） |
| 🟡 变异 | 突变 `selector.py` 加一处 `sorted(` 调用 → 验证器 D 红 → 还原绿；突变 `agent_profile.py` 加一行第三方 import（如 `import yaml`）→ 验证器 A 红 → 还原绿（证明 AST 扫描断言活着） |
| 🔄 重构 | 验证器断言表达收敛（扫描豁免清单注释化） |

#### 架构验证测试实现

- [x] Subtask 7.1: 创建 `tests/unit/architecture/test_arch_agent_profile_loading.py`
- [x] Subtask 7.2: 验证器 A——domain 零依赖 + 零 application import（agent_profile.py 白名单式收紧断言：仅标准库 {uuid, dataclasses, __future__} + src.domain；DC-7 架构防线）
- [x] Subtask 7.3: 验证器 B——依赖方向（MarkdownAgentProfileLoader 仅 domain + application.ports 合法方向；agent_cli 零 infrastructure；用例仅 domain + application）
- [x] Subtask 7.4: 验证器 C——组合根唯一装配（AST Call 扫描三实现类——func.id/func.attr 命中类名，跳过定义文件与 composition_root.py；组合根注册 grep 三端口）
- [x] Subtask 7.5: 验证器 D——SkillSelector 无打分断言（sorted/sort/score/weight/ranking/top_k 标识符 AST 零命中 + get_all_slugs 枚举真源 + 无 reverse）
- [x] Subtask 7.6: 循环依赖检测用 ruff/isort（subprocess ruff --select I，不引入 pylint）
- [x] Subtask 7.7: 运行完整测试套件并生成报告（完整套件归并 Task 8 Subtask 8.4 全量回归执行）
- [x] 双变异实证：① selector.py 注入 `sorted(` → 验证器 D 红、还原绿；② agent_profile.py 注入 `import yaml` → 验证器 A 双断言红、还原绿（证明 AST 扫描断言活着）——12 架构测试 + 37 相关单测还原后全绿

**完成标准/Definition of Done:**
- [x] 所有架构约束测试通过，任何违规导致测试失败
- [x] 输出清晰合规报告（验证器 A-E 分节——A domain 零依赖 4 项 / B 依赖方向 3 项 / C 组合根唯一装配 2 项 / D 无打分 2 项 / E 循环依赖 1 项，共 12 项）
- [x] 循环依赖检测不引入额外工具（subprocess ruff --select I）

---

### Task 8: 开发结束验收测试

**关联 AC:** 全部收尾

> **性质说明：** Story 收尾最终验收——src 与 tests 四目录完成清单逐项确认，确保进入 `done` 前无遗漏。收尾场景为验证型测试：断言对象此时均已存在，**编写后直接转绿为合法预期**，断言活性由变异（文件名突变）背书。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | （AC-6.3 收尾场景与步骤已在 Task 0 落盘并验证红——本 Task 无新增场景，防收集数漂移） |
| 🟢 绿 | AC-6.3 收尾场景全量转绿核对（文件存在性/关键符号/接线 grep 断言此时全应通过） |
| 🟡 变异 | 突变一处预期文件名（改为不存在路径）→ 收尾场景红 → 还原绿 |
| 🔄 重构 | 场景命名与断言表达收敛 |

- [x] Subtask 8.1: 场景 1 — 验证 `src` 完成清单（AC-6.3 场景断言全过：10 处 src 产出 + 六档案资产 + 组合根三端口注册 grep）
- [x] Subtask 8.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单（AC-6.3 场景断言全过：12 处测试文件逐项存在）
- [x] Subtask 8.3: 链路接线断言清单 L1-L8 终态核对（L1-L6 绿灯实证 grep 可达 + L7/L8 deferred-work.md 登记仍在且未误删——含 Task 0 补登记的组合根 impl 路径失效观察项；AC-6.3 场景断言全过）
- [x] Subtask 8.4: 运行 `poetry run pytest tests/`、`poetry run ruff check src/ tests/`、`poetry run mypy src/` 收尾校验——**ruff 全仓通过 + mypy 672 文件零错误 + pytest 全量 12363 passed / 32 failed / 46 skipped**；32 个失败逐一分类定谳为**环境性失败与改动面零交集**（Neo4j 测试端口 7475/7688 不可达×10、Qdrant 测试端口 6335 不可达×7、GPU 不可用×1、OCR benchmark 外部模型环境×14；redis_cache P95 ×2 为 -n 8 并行负载抖动——串行重跑 12 passed 全过实证；git status 改动面与失败文件零交集验证；--lf 串行复跑确认）
- [x] Subtask 8.5: 更新 sprint-status.yaml（5-2 → review）；同步设计文档：interface-design.md §5.5 注记更新为已实现 + 实现形态标注（实际注入 skill_loader 端口、返回 tuple[ToolMetadata, ...]、纯 status 过滤，示意骨架 SkillRepositoryPort/Skill 形态未采纳）；§17.1 两行勘正（TOOLS.md 不落物理文件 DC-2 / SkillSelector 5.2 交付提前于 5.3）；architecture.md §11.2.2 MVP 路径注记（D-4：configs/agents/profiles/ 静态资产 + 工作目录形态延后 + DC-2 TOOLS.md 视图）；§10.1 事件行 Task 1 已同步终态核对通过
- [x] Subtask 8.6: 验收场景全量转绿核对（**14/14 场景全绿 + 收集场景数 == 14 校验通过**；补齐 AC-1.2/1.3/2.1/2.3/3.2/6.1/6.2 逐一绿）——变异实证：SOUL.md 临时重命名 → AC-6.3 收尾场景红、还原绿

**完成标准/Definition of Done:**
- [x] src 与 tests 完成清单逐项验证确认
- [x] 开发结束验收测试通过（变异实证：文件名突变→红→还原绿）
- [x] 三项质量门禁全绿（ruff / mypy 零错误；pytest 全量回归——5-2 相关测试全绿，32 失败均为环境性零交集定谳）
- [x] Story 可进入 `review`/`done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ DDD 聚合（Agent 实体为聚合根，档案为其启动上下文资产）+ 组合根 DI（PortSpec/Registry/Resolver/ContractGate）
- **设计约束:** domain 零外部依赖（import-linter 强制）+ **domain 零 application import**（本 Story 特有防线：ToolMetadata 属 application 层）；infrastructure 实现 application 端口；所有装配经 `src/composition_root.py`
- **接口治理:** 统一端口注册（name/version/interface/impl/module/lifetime/owner/compatibility/tags/deprecated）、契约优先、版本化兼容、禁止跨模块直接依赖实现类
- **技术栈:** Python 3.11+ / Path 文件 IO（`asyncio.to_thread` 包装）/ PyYAML 仅 infrastructure / pytest-bdd 8.x / pytest-xdist
- **档案加载权威流程:** architecture.md §11.2.4（L1041-1052）「会话初始化 → 加载系统级 MEMORY.md → 加载 Agent 配置集（七档案）→ Agent 实例化 → 合并上下文 → 任务执行」——**本 Story 覆盖「加载 Agent 配置集」一步**（系统级 MEMORY.md 动态索引部分 deferred，见 D-3；任务执行/合并上下文属 5.3）。**顺序差异注记**：§11.2.4 为会话级终态流程（加载配置集在实例化前）；本 Story 以 agent_id 为锚（DC-10）先实例化（5-1）后加载——MVP 实施序与终态流程序的差异属实现形态选择，语义等价（档案为静态资产与实例化无数据依赖）
- **档案语义权威约定:** architecture.md §11.2.2（L998-1023）+ §11.2.8（L1304-1309）——七档案**启动时一次性加载，不在运行时动态更新**；Agent 的「学习」走 StrategicArchive + MemoryMetadata，不走档案文件更新
- **Skills L1 权威口径:** architecture.md §17.3（L2685-2688）+ interface-design.md §2.1/§5——L1 ≤1.2K tokens 启动全量预加载、LLM 基于 description 自主判断（P5 Less scaffolding）、SkillSelector 仅查询接口（§5.5）

### 关键架构决策

| # | 决策点 | 选定方案 | 备选方案（弃用理由） | 依据 |
|---|--------|---------|---------------------|------|
| DC-1 | 七档案存放路径 | **`configs/agents/profiles/{role}/`** 固定名六文件（CEO: `configs/agents/profiles/ceo/`） | a) 「Agent 工作目录」规划位（弃用：运行时概念，MVP 无 Agent 工作目录基础设施，且档案需随代码分发；登记偏离 D-4）；b) `src/application/skills/` 同级（弃用：混淆 Skills 静态资源与 Agent 档案两个资产域）；c) `~/.sisys/`（弃用：用户目录属运行时记忆域，1.15b 已占用语义） | YamlAgentConfigLoader 的 `configs/agents/` 锚定一致（四级上溯）；D12 wheel 缺口同域已知登记不新增风险类型 |
| DC-2 | TOOLS.md 双角色冲突（七档案之一 vs Skills L1 既有文件） | **不复制物理文件**——档案链路的 TOOLS.md 视图 = `skill_loader` 端口 L1 元数据（23 条 ToolMetadata），加载用例组合注入 | a) 在 profiles/ceo/ 落一份精简派生 TOOLS.md（弃用：双真源——23 个 SKILL.md 演进时派生文件必漂移）；b) 瘦身既有 `src/application/skills/TOOLS.md`（8 列 1104 tokens = 全文 `len(chars)//4` 实测）至 4 列 <200 tokens（弃用：是 4-1a 交付资产且两用例消费中；瘦身属破坏性变更无 Story 认领） | R2 应用层端口组合注入原则；epics L3431「Epic 5 对 Epic 4 依赖为可选 TOOLS.md 元数据」；单一真源 |
| DC-3 | token 预算口径（旧 <200/<500 vs 新 ≤1.2K 冲突） | **按 interface-design.md 修订版**，两口径分述（AC-3 定稿）：① L1 缓存口径——TOOLS.md 全文 ≤1200 tokens（现状 1104，interface-design 启动预加载预算的对象）；② 用例计量口径——`"\n".join(f"{m.tool_name}: {m.description}")` 拼接视图（现状约 218，TOOLS.md 内容子集，`startup_context_tokens` 的 L1 部分）；IDENTITY+SOUL ≤500 tokens（保留 PRD 精神的身份档案精简约束）；总计量 ≤1700 tokens 可观测 | 严格执行 PRD NFR-IF-02「启动上下文 <500 tokens」（弃用：L1 现实 1104 tokens 已超其 2 倍+，23 工具描述无法压进 200 tokens——旧口径基于「L1 <200」假设已被 interface-design §2.1「23 工具 ≈1150 tokens」推翻；登记偏离 D-2） | interface-design.md L52/L633/L723；architecture.md §17.3 L2686；GAP-CRITICAL-08b 同源决策链 |
| DC-4 | SkillSelector 形态（epics vs interface-design 冲突） | **`list_active_skills()` 纯查询**（get_all_slugs 枚举 → load_metadata → status 过滤；零排序零打分零 Top-K）；触发由 LLM 基于 L1 description 自主判断（5.3 实现） | epics L1546「关键词匹配 40% + 语义相似度 60% 融合排序推荐 Top-K」（弃用：interface-design.md §5.5 L920-990 明文废弃——违反 P5「Less scaffilling」+ 双重不必要复杂度；architecture.md GAP-CRITICAL-08b 指定本 Story「删除硬编码，模型自决」；登记偏离 D-1） | interface-design.md §5.5；architecture.md L3315；Anthropic Skills 设计哲学 |
| DC-5 | 档案验证规则（无文档定义，本 Story 设计） | **六档案非空（strip 后）+ 单文件 ≤64KB（字节口径：`stat().st_size` 或 `len(content.encode("utf-8"))`——与 `PROFILE_FILE_MAX_BYTES` 常量语义对齐；`len(content)` 字符口径在中文下差至 3 倍，不用）**；无 frontmatter 强制（纯 Markdown）；**判空主检在加载器**（逐文件、`context.profile_path` 携带文件名——AC-2「加载器内实施」的观测锚点，AC-1.3 场景断言依赖）；VO `__post_init__` 二次校验为直接构造场景的纵深兜底（兜底路径 profile_path 可空——5-1 yaml loader 的「剩余校验 VO 兜底」模式在 5-2 不适用主检位，因 442 的 context 契约需要文件名） | a) 强制 YAML frontmatter（弃用：frontmatter 解析在 application 层（skills/frontmatter.py），infrastructure 加载器跨层引用；且档案是人写文档非机器路由配置，无消费方需要结构化元数据）；b) 每档案最少行数/必需章节（弃用：无 LLM 消费契约支撑，YAGNI——5.3 注入 LLM 时按需收紧） | Simplicity First；5-1 未知键忽略前向兼容同族 |
| DC-6 | MEMORY.md 档案语义（系统级动态 vs 静态种子） | **MVP 静态种子文件**（profiles/ceo/MEMORY.md，内容明示「暂无系统级记忆，此为加载占位」）；系统级 `~/.sisys/memory/MEMORY.md` 动态索引合并不在本 Story（记忆链路休眠：MemoryConfig 零生产 from_env + l0_storage impl 路径失效，deferred-work 在案） | 经 L0StoragePort/IndexManager 读系统级真源（弃用：L0StoragePort 寻址 `{type}/{uuid}.md` 不适配固定名根级文件；且记忆链路整体休眠，激活属独立 Story） | architecture.md §11.2.2 L1021「Agent 的 MEMORY.md 来自系统级，无独立索引」——MVP 先落「加载」语义，「系统级合并」deferred（D-3） |
| DC-7 | AgentProfile VO 分层（ToolMetadata 不可入 domain） | **domain VO 仅六档案 str** + **应用层 DTO `AgentProfileLoadResult` 组装**（profile + tools_l1 + 计量）——ToolMetadata 属 application 层（`src/application/ports/skill_loader.py`），domain 引用即违反方向矩阵（domain ✗→ application） | a) ToolMetadata 下沉 domain（弃用：4-1a 交付资产大迁移，破坏 33 个测试文件消费面）；b) AgentProfile 含 `tuple[str, ...]` slug 列表（弃用：丢失 description/when_to_use 元数据，5.3 LLM 上下文装配无材料） | 依赖方向矩阵（CLAUDE.md Hard Constraints）；R1/R2 分层设计规则 |
| DC-8 | 用例是否注入 SkillSelector | **注入 SkillSelector**（四依赖：profile_loader/repository/skill_selector/event_publisher；ACTIVE 过滤逻辑单点在 SkillSelector，用例一次调用消费） | 用例直组 skill_loader（get_all_slugs + load_metadata + 过滤逻辑在用例内重复实现——弃用：依赖数与注入 Selector 相同（4 个）而过滤逻辑双份，DRY 违反；且 SkillSelector 作为「查询接口」需要首个真实消费方验证其形态，用例即天然消费方） | R2 应用层端口组合注入；接口单一职责 + DRY；GAP-CRITICAL-08b 交付物的消费验证 |
| DC-9 | CLI 入口位置与子命令 | **扩展 `src/entrypoints/agent_cli.py`**（D1 方案 A 后入口事实）追加 `load-profile --agent-id` 子命令；pyproject script 沿用不新增 | a) `src/interfaces/cli/`（弃用：D1 方案 A 已迁移，5-1 故事文路径过时）；b) 新建独立 `sisys-agent-profile` 入口（弃用：pyproject 双注册冗余，同一聚合域共享入口） | D1 方案 A 落地（v1.13.0）；ocr_cli/agent_cli 同域单入口先例 |
| DC-10 | 档案加载用例入口签名 | **`execute(agent_id)`**（get_by_id 读实体 → 取 role 寻址档案目录）——对齐 epics「Given Agent 已实例化 / When 加载身份档案」语义 | `execute(role)` 直载（弃用：绕过存在性守卫，443 不可达；档案与具体 Agent 实例的归属锚点（agent_id 入 VO）丢失） | epics L1533 Gherkin；443 异常可达性 |

### 已知下游风险（本 Story 不处置，消费方 Story 决策）

1. **启动上下文的 LLM 注入契约未定**：本 Story 交付 `AgentProfileLoadResult`（六档案 str + L1 元数据 + 计量），但「如何拼装为 LLM 系统提示」（IDENTITY/SOUL/USER 的模板化、L1 description 的注入格式、核心约束文本从哪来）属 5.3 工作流——5.3 立项时定上下文装配契约，届时可能需要本 Story 结果对象的字段演进（DTO 字段追加零成本，非端口签名变更）。**口径警示**：`startup_context_tokens` 只计 IDENTITY+SOUL+L1 拼接视图（不含 CODE/USER/MEMORY/HEARTBEAT 四档案，L1 为拼接口径 ~218 非 TOOLS.md 全文 1104）——5.3 六档案全量装配时实际上下文将显著大于该计量，装配契约订立时须重定义口径；且 `chars//4` 对中文显著低估（`_estimate_tokens` docstring 自述中文约 1.5 token/字符，估算口径 0.25 token/字符——中文内容低估可达数倍），真实 tokenizer 语义下预算偏松，5.3 注入 LLM 前需按真实 tokenizer 复算。
2. **LangGraph 引擎 agent_id 双轨道**（5-1 遗留风险的 5-2 延续）：本 Story 用例以实体 agent_id 为锚（get_by_id），而 `LangGraphEngine`（langgraph_engine.py L71-72）执行时自铸 agent_id——5.3 引擎消费档案时必须收敛（复用实例化 agent_id 或桥接映射），否则 AgentProfileLoaded（实体 id）与 AgentDecided（引擎铸 id）无法按 aggregate_id 关联。
3. **`skill_loader` SCOPED 被 SINGLETON 用例捕获**（captive dependency，5-1 D7 同款）：`InMemorySkillLoader` 无连接状态（有 L1/L2 缓存但只读复用）、L1 缓存在 `__init__` 构建——被钉住反而保证缓存跨调用复用（性能有利），但请求级 scope 启用时需改为用例内按调用解析。归 5-1 D7 留项（5.4 lifetime 语义决策回迁时一并评估）。
4. **MEMORY.md 系统级合并缺失**：MVP 静态种子不含任何真实记忆——5.3+ 若期望 Agent 带记忆启动，需先激活记忆链路（l0_storage impl 路径修复 + MemoryConfig from_env）并在档案加载用例中插入合并步骤（本 Story 的 loader 端口签名 `load(role, agent_id)` 不变，合并发生在用例编排层）。
5. **档案资产的单角色覆盖**：仅 CEO 档案落地——V1 开放 CFO/CMO 等角色时需按 DC-1 路径补 `profiles/{role}/` 六件 + `configs/agents/{role}_agent.yaml`（5-1 DC-3 回填同步），`SUPPORTED_ROLES` 常量扩展（5-1 留好的单点）。

### 设计文档偏离声明

> 90-8 先例机制：实施与设计文档冲突时显式声明，实施后同步更新文档。

| # | 冲突点 | 偏离内容 | 实施后同步动作 |
|---|--------|---------|---------------|
| D-1 | epics_v1.0.md L1546「SkillSelector 基于 L1 元数据推荐 Top-K Skills（关键词匹配 40% + 语义相似度 60%）」 | 按 interface-design.md §5.5 + architecture.md GAP-CRITICAL-08b 新权威口径实现：`list_active_skills()` 纯查询，无权重融合/排序/Top-K；Skill 触发由 LLM 自主判断（5.3） | 不修改 epics（历史规划文档，同 5-1 D-4 处置）；Task 8 更新 interface-design.md §5.5「⚠️ 设计示意，未实现」注记为已实现；dev agent 勿据 epics 旧文案实现选择器 |
| D-2 | prd.md NFR-IF-02（L2554）「Agent 启动上下文 <500 tokens（L1 TOOLS.md <200 tokens）」+ epics L1542/L1545 同口径 | 预算按 interface-design.md 修订版执行：L1 ≤1200 tokens（现实 1104，23 工具无法压入 200）+ IDENTITY+SOUL ≤500 tokens（保留精简精神）+ 总计量 ≤1700 可观测 | 不修改 prd/epics（历史规划文档）；AC-4 与 Task 2/4 以新口径为验收真源；5.7+ 若有 token 预算审计需求以 result.startup_context_tokens 计量值为准 |
| D-3 | architecture.md §11.2.4 流程首步「加载系统级 MEMORY.md → 索引 → user/project/feedback/reference」 | MVP 的 Agent MEMORY.md 为静态种子（DC-6）——系统级动态索引合并 deferred（记忆链路休眠：MemoryConfig 零生产 from_env、l0_storage/memory_file_storage 组合根 impl 字符串路径失效——Task 0 补登记 deferred-work 观察项） | 不修改 architecture.md（§11.2.4 描述的是终态架构）；deferred-work.md 登记合并缺失 + 组合根路径失效观察项，触发=记忆链路激活 Story |
| D-4 | architecture.md §11.2.2 档案位于「Agent 工作目录」（规划位） | MVP 落地 `configs/agents/profiles/{role}/`（静态资产随代码分发，DC-1）；Agent 工作目录属运行时概念（5.3+ 若引入会话级档案覆写再评估迁移） | Task 8 在 architecture.md §11.2.2 目录树旁补注「MVP 静态资产位于 configs/agents/profiles/，工作目录形态延后」 |
| D-5 | prd.md L1838（FR-AC-02 行尾）对「[or.md 四.4.(1)]」的引用编号偏差 | 七档案完整枚举实际在 or.md 四.1.[1]（L277）；四.4.(1)（L293）是「初始化」步骤未列档案名——PRD 宽松引用，非内容冲突 | 无需动作（注记性声明，防 dev agent 按 四.4.(1) 找不到档案定义） |
| D-6 | interface-design.md L93-99 Skills 层列表（含 AGENT.md、无 CODE.md/USER.md）vs or.md 七档案 | 以 or.md 七档案（FR-AC-02 P0 权威）为准；AGENT.md（<150 行）属 interface-design §5.6 规划的扩展档案，无 FR 认领不在本 Story（5.3 上下文装配立项时评估） | 不修改 interface-design.md；5.3 Story 引用本声明评估 AGENT.md 必要性 |
| D-7 | epics_v1.0.md L1527-1528 建议测试路径 `tests/unit/architecture/test_agent_profile_loading.py`、`tests/integration/test_agent_profile_loading_integration.py` | 以项目实际目录结构为准（本 Story 测试分类表全套路径）——同 5-1 D-5 处置（unit 下按层分目录、integration 无 `_integration` 后缀惯例、架构测试命名 `test_arch_*`） | 不修改 epics；dev 以本 Story 测试分类表为准 |
| D-8 | NFR-IF-02 编号冲突（prd.md L2554 = Skills 加载上下文；epics L337 = 三重评分延迟，Epic 21 PRD v1.1.0 复用） | 本 Story 覆盖的 NFR-IF-02 以 prd.md 口径为准 | 无需动作（注记性声明，防混淆） |
| D-9 | epics Story 5.2 Gherkin（约 L1536）Then 字面枚举七文件含「TOOLS.md（技能）」物理文件语义 | 按 DC-2 交付 TOOLS.md **视图**（skill_loader 端口 L1 元数据 23 条，不落 profiles/ceo/TOOLS.md 物理文件）——单一真源，防 23 个 SKILL.md 演进时派生文件漂移 | 不修改 epics（历史规划文档）；Task 8.5 已含 interface-design §17.1「TOOLS.md 元数据清单」行勘正；dev agent 勿按 Gherkin 字面在 profiles/ceo/ 落 TOOLS.md 文件 |

### 关键代码模式参考

**组合根注册样例（5-1 段形态，composition_root.py L2677-2692）——Task 2 照抄结构：**

```python
register_port(
    name="agent_profile_loader",
    version="v1.0.0",
    interface=__import__(
        "src.application.ports.agent_profile_loader",
        fromlist=["AgentProfileLoader"],
    ).AgentProfileLoader,
    impl=lambda resolver: __import__(
        "src.infrastructure.agent_orch.markdown_agent_profile_loader",
        fromlist=["MarkdownAgentProfileLoader"],
    ).MarkdownAgentProfileLoader(),
    module="src.infrastructure.agent_orch.markdown_agent_profile_loader",
    lifetime=Lifetime.SINGLETON,
    owner="platform",
    tags=("agent", "profile"),
)
```

**AgentProfileLoaded 事件模板（`src/domain/events/agent_events.py` L39-67 AgentInstantiated）——照抄结构：** frozen dataclass；`agent_id: uuid.UUID = field(kw_only=True)` 等四必填 kw_only；`event_type` init=False 默认；`__post_init__` 设 `aggregate_id`（UUID 对象 + None 守卫）/`aggregate_type="Agent"`。

**事件通道登记（configs/event_channels.yaml L182-185 AgentInstantiated 条目）——照抄结构：**

```yaml
  AgentProfileLoaded:
    rabbitmq_routing_key: "sisys.events.reliable.agent_profile_loaded"
    delivery_mode: "reliable"
    description: "Agent身份档案加载完成"
```

（同步 `src/infrastructure/messaging/channel_router.py` `DEFAULT_MAPPINGS` 对齐条目。）

**加载器结构模板（`yaml_agent_config_loader.py`）——MarkdownAgentProfileLoader 照抄骨架：** 构造器 `profile_root: Path | None = None` 默认 `Path(__file__).parent.parent.parent.parent / "configs" / "agents" / "profiles"`；`asyncio.to_thread` 包装同步 IO；失败统一 `_fail` 闭包（role/profile_path 相对形态/reason 三键 context）；OSError/UnicodeDecodeError 逐类包装；未知文件忽略。

**用例编排模板（`agent_instantiation.py` L89-147）——LoadAgentProfileUseCase 照抄：** 守卫链（5-1 的「守卫→加载」扩展为「存在性→角色→加载」）；事件发布两分支（`publish_result.is_success` + `except Exception` 双路径均 `logger.error(...)` 不回滚——**5-1 实际形态**：`is_success==False` 分支为普通 `logger.error(...)`，仅 raise/except 分支带 `exc_info=True`，照抄勿统一）；DTO 模块内定义。

**SkillSelector 实现骨架（Task 3）：**

```python
from src.application.ports.skill_selector import SkillSelectorPort  # 端口 Protocol（本 Story 新建）

class SkillSelector(SkillSelectorPort):
    def __init__(self, skill_loader: SkillLoaderPort) -> None:
        self._skill_loader = skill_loader

    async def list_active_skills(self) -> tuple[ToolMetadata, ...]:
        result: list[ToolMetadata] = []
        for slug in get_all_slugs():
            meta = await self._skill_loader.load_metadata(slug)
            if meta.status == "active":
                result.append(meta)
        return tuple(result)
```

（`load_metadata(slug)` 直传 slug 合法——loader `_resolve_slug` L403-429 支持 slug/tool_name/UUID 三形态寻址。）

**CLI 子命令扩展模式（`src/entrypoints/agent_cli.py`）：** `subparsers.add_parser("load-profile", help=...)` + `add_argument("-a", "--agent-id", required=True, metavar="AGENT_ID")`；UUID 守卫 try/except ValueError → ValidationError(201)；`_close_redis_pool` finally 沿用；输出多行摘要；退出码 0/1/2。

**验收测试骨架（5-1 `test_acceptance_agent_instantiation.py` 605 行）——R6 主体基准：** FEATURE 常量 + `@scenario` 显式绑定（**5-1 为 13 场景形态；本 Story 为 14 场景——收集数校验按 14**）；context fixture（场景级 `redis.asyncio.Redis(decode_responses=True)`（5-1 代码字面别名 `aioredis` 即 `redis.asyncio`）+ `_agent_ids` 记录列表）；`_run_async` helper；场景级 ping 门控（`pytest.skip(f"Redis not available: {exc}")`）；服务组装按场景分档（需 instantiate 的 AC-1.1/4.1/5.1/5.2 = 5-1 用例真实 instantiate → 本 Story 用例手动组装；其余场景见 BDD 约束节分档，端口直连/纯 resolve 场景无服务组装）；异常断言 `isinstance` + `error.code`；teardown 逐 agent_id 精确 delete + 同循环 close；AST 静态扫描场景写法参照 postgresql 模板 L792-819。

**单元测试 Mock 工厂模式（5-1 `test_agent_instantiation.py`）：** `AsyncMock(spec=Protocol)` + `_make_*` 工厂 + `pytest.raises(X) as exc_info` + `exc_info.value.code`/`context.get(...)` 断言 + Mock calls 编排顺序断言。

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 5-1](./5-1-ceo-agent-instantiation-mvp.md)（五轮代码审查 + 五轮文档审查 + v1.13-v1.14 留项清偿全记录）

**关键学习/Key Learnings:**
- **7.1-1 链路接线断言（P0）**：事件零发布/装配断线是 Epic 4 重灾区——Task 0 链路清单 + Task 8 终态核对强制（本 Story L1-L8）
- **7.1-2 变异实证（P0）**：8/13 Story 存在恒真断言——每个 TDD 循环的 🟡 变异阶段不可跳过（本 Story 重点：过滤条件、发布点、守卫顺序、P95 阈值、档案判空五处）
- **kw_only 必填字段**：DomainEvent 基类字段全带默认值，非 kw_only 必填字段类定义即抛 TypeError（5-1 Docs Review #14）
- **守卫先于加载**：顺序倒置会使下游异常不可达（5-1 Docs Review #15）——本 Story 级联为存在性→角色→加载
- **resolve 跨循环死连接**：SCOPED/SINGLETON 有状态端口 resolve 后发命令会钉住全局 Resolver（5-1 文档审查修复 #23）——验收手动组装纪律
- **验收门控下沉**：背景块整 feature 门控会让静态场景被整批 skip（5-1 R3-F5/D4 核销）——无背景块 + 场景级 given
- **@scenario 收集期陷阱**：场景名不匹配整文件炸/漏绑定静默不收集——收集数校验进 Task 0.4/8.6
- **truthy 标量越过判空**（5-1 R2-F2）：`responsibilities="战略方向"` 静默通过——VO 先 isinstance 类型守卫再判空
- **失败路径统一异常**（5-1 R1-F2）：OSError/UnicodeDecodeError 家族逐类包装，禁裸内置异常逃逸
- **CLI 守卫**：枚举/UUID 字符串转换必须 except 映射领域/应用异常，禁裸 ValueError 逃逸（5-1 Task 5 枚举→441 先例 + D8 清偿后 ocr_cli int 页码转换→201 先例——UUID 转换无既有先例，本 Story 新建同款模式）
- **团队协议**：「Done = 接线生效 + 资产在库」；「已实现未接线」零容忍
- **D12/D13 治理项**：configs/ wheel 分发缺口（profiles/ 六档案同域适用，不新增处置）；CLI bootstrap 10.4s 开销（核销触发 5.3 批量消费前——本 Story 单次调用同 5-1 语义）

**应用到本故事/Applied to This Story:**
- [ ] 链路接线断言清单 L1-L8 全程跟踪（Task 0 定义 → Task 8 终态）
- [ ] 每个 TDD 循环含 🟡 变异阶段（重点五处：过滤/发布/守卫序/阈值/判空）
- [ ] 事件四字段全 kw_only + aggregate UUID 对象
- [ ] 验收测试每个 then 步骤有真实断言（禁 pass 占位）
- [ ] 验收禁 mock：InMemoryEventBus/真实文件/组合根真实 loader
- [ ] tmp_path 构造档案破坏场景，禁改内置资产
- [ ] deferred 处置透明化（L7/L8 保持登记 + 组合根 impl 路径失效补登记）

### deferred-work 处置（Epic 5 触发项分流）

> 原则：本 Story 只接线自己的六项（L1-L6），不为「顺手」扩大范围——扩大范围须经 deferred-work.md 台账决策。

| 休眠资产 | 5-2 处置 | 预计接线 |
|---------|---------|---------|
| heartbeat_scheduler / HeartbeatTriggered / AutoTrigger 三 handler | **不接线**——HEARTBEAT.md 仅静态加载（心跳行为属 FR-SA-05 P1） | Story 5.3+（Agent 编排） |
| 系统级记忆链路（l0_storage/MemoryFileStorage/MemoryService/IndexManager） | **不接线**——MEMORY.md 静态种子；**Task 0 补登记观察项**（组合根 impl 路径失效两处） | 记忆链路激活 Story |
| `session_storage` 端口 + RedisSessionStorage（5-1 L6 登记） | 不接线（本 Story 无会话语义） | Story 5.3（会话状态） |
| `agent_engine`/`orchestration_service` agent_reasoning 链 | 不接线（引擎消费属 5.3——启动上下文注入契约是 5.3 核心决策） | Story 5.3 |
| 语义检索基础设施（embedding_service/Qdrant L3） | 不接线——SkillSelector 无语义打分（DC-4），零消费属预期 | 若 5.9 验收需要语义评估再评估 |
| 工具熔断（or.md 四.7.(3)，deferred-work L18 主登记） | 不处置——**随行评估结论：维持挂 5.4/5.5 EIP 弹性隔离**（本 Story 档案加载无工具执行面，无熔断挂点） | Story 5.4/5.5 |

### 项目结构说明 Project Structure

```
src/
├── composition_root.py                                  # [修改] Story 5.2 段追加 3 端口注册
├── domain/
│   ├── events/agent_events.py                           # [修改] 追加 AgentProfileLoaded
│   ├── exceptions/agent_exceptions.py                   # [修改] 追加 442/443（docstring 补继承链理由）
│   │   └── （_code_ranges.py 的 _CLASS_TO_SUBDOMAIN / __init__.py 随之修改）
│   ├── value_objects/agent_profile.py                   # [新建] AgentProfile frozen dataclass（六档案）
│   └── （ports/ 无新增——档案加载端口在 application 层，对齐 5-1 AgentConfigLoader 先例）
├── application/
│   ├── ports/agent_profile_loader.py                    # [新建] AgentProfileLoader Protocol
│   ├── ports/skill_selector.py                          # [新建] SkillSelectorPort Protocol
│   ├── skills/registry/__init__.py                      # [新建] 包初始化（registry/ 目录已存在为空，selector.py 需包入口）
│   ├── skills/registry/selector.py                      # [新建] SkillSelector 实现（GAP-CRITICAL-08b）
│   └── use_cases/agent_profile_loading.py               # [新建] LoadAgentProfileUseCase + AgentProfileLoadResult
├── infrastructure/
│   └── agent_orch/markdown_agent_profile_loader.py      # [新建] MarkdownAgentProfileLoader
└── entrypoints/agent_cli.py                             # [修改] 追加 load-profile 子命令（D1 方案 A 后入口）
configs/
├── agents/ceo_agent.yaml                                # [不动] 5-1 资产
├── agents/profiles/ceo/IDENTITY.md                      # [新建] 六档案资产
├── agents/profiles/ceo/CODE.md                          # [新建]
├── agents/profiles/ceo/SOUL.md                          # [新建]
├── agents/profiles/ceo/USER.md                          # [新建]
├── agents/profiles/ceo/MEMORY.md                        # [新建]（静态种子）
├── agents/profiles/ceo/HEARTBEAT.md                     # [新建]（心跳配置文档，不接线）
└── event_channels.yaml                                  # [修改] AgentProfileLoaded 登记
tests/
├── unit/
│   ├── domain/{events/test_agent_events.py,             # [追加]
│   │           exceptions/test_agent_exceptions.py,     # [追加]
│   │           value_objects/test_agent_profile.py}     # [新建]
│   ├── application/{skills/test_skill_selector.py,      # [新建]
│   │                use_cases/test_agent_profile_loading.py}  # [新建]
│   ├── infrastructure/agent_orch/test_markdown_agent_profile_loader.py  # [新建]
│   ├── interfaces/cli/test_agent_cli.py                 # [追加]（5-1 测试路径现状，源已迁 entrypoints）
│   └── architecture/test_arch_agent_profile_loading.py  # [新建]
├── contracts/（test_port_contract_agent_profile_loader.py 等 3 个）# [新建]
├── integration/test_integration_agent_profile_loading.py # [新建] 真实 Redis + 性能
└── acceptance/test_acceptance_agent_profile_loading.{feature,py} # [新建] 14 场景
同步文档：
├── docs/architecture/sisys-uni-exception-design.md       # [修改] §3.3.2 表 442/443 行
├── docs/architecture/architecture.md                    # [修改] §10.1 事件表 + §11.2.2 MVP 路径注记（D-4）
└── docs/architecture/interface-design.md                # [修改] §5.5 未实现注记更新（Task 8）
```

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (glm-5.3) |
| **Version** | create-story workflow v6.3.0 |
| **Execution Date** | 2026-10-15 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Template** | `docs/developer/story-template.md`（`.claude/skills/bmad-create-story/template.md` 同源） |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Epic 5 头部 + Story 5.2 节 L1497-1547） |
| **架构文档** | `docs/architecture/architecture.md`（§11.2 记忆入口层/§13.11 Skills 目录/§17.3 工具箱/§19.4 GAP 表）、`sisys-core-domain-design.md` §17.3、`interface-design.md` §5（Skills 渐进式加载/SkillSelector 权威新口径） |
| **需求** | `_bmad-output/planning-artifacts/prd.md` FR-AC-02（L1838）/FR-IF-02（L2181-2185）/NFR-IF-02（L2554） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/5-1-ceo-agent-instantiation-mvp.md`（五轮审查台账 + D1-D13 留项） |
| **运营方法原文** | `_bmad-output/planning-artifacts/or.md`（四.1.[1] L277 七档案枚举 / 四.4.(1) L293 初始化步骤——D-5 偏离声明依据） |
| **统一异常设计** | `docs/architecture/sisys-uni-exception-design.md` §3.3.2/§3.7（442/443 编码分配与注册表——领域异常契约依据） |
| **Deferred 台账** | `_bmad-output/implementation-artifacts/deferred-work.md`（L7/L8 心跳与记忆链路登记 + Task 0 补登记观察项） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **调研输入** | 5 并行调研 Agent 报告（规划文档全景 / 5-1 交付物代码现状 / Skills 基础设施 / 记忆心跳基础设施 / 验收模板与测试规范）+ 关键签名人工核验（ToolMetadata 字段/load_metadata 签名/事件发布形态/TOOLS.md 实测） |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` Story 5.2 提取（含 prd.md FR-AC-02/FR-IF-02/NFR-IF-02 与 epics L1537-1547 Skills 三级加载验收交叉验证）
- [x] 架构约束从 architecture.md §11.2/§13.11/§17.3/§19.4 + interface-design.md §5 + core-domain §17.3 提取
- [x] 现有代码继承清单完成（5 并行 Agent 全仓调研 + 关键签名人工核验：ToolMetadata.status 字段存在、load_metadata 单查询签名、get_all_slugs 真源、CLI 入口 entrypoints 位置）
- [x] 前一个故事学习经验整合（5-1 五轮代码审查 + 五轮文档审查关键教训 12 条逐项应用）
- [x] 规划冲突裁决入表（DC-3 token 预算口径 / DC-4 SkillSelector 形态——epics 旧文案 vs interface-design 新权威，偏离声明 D-1/D-2）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（含链路接线断言清单 L1-L8 与每循环变异阶段）
- [x] 项目结构对齐统一规范（R1/R2/R4 层归属 + DC-7 分层裁定防 domain→application 违规）
- [x] 验收测试规范对齐模板（R6：5-1 最新形态为主体基准 + 用户指定 postgresql 模板三项继承先例显式声明）

### Dev Story 实施记录（2026-10-19）

- [x] Task 0-8 全部完成（每 Task 独立红→绿→变异→重构循环，变异实证 9 处记录在案：443 HTTP 映射/事件 aggregate_type/VO strip 判空/固定名映射/过滤条件/发布点/守卫顺序/UUID 守卫/P95 阈值/验证器 sorted+import yaml/收尾文件名）
- [x] 14/14 验收场景全绿 + 收集数 == 14 校验
- [x] 全部 6 项接线（L1-L6）绿灯：三端口 resolve 可达 + 事件双登记 + CLI 端到端真实执行 + skill_loader 新消费方
- [x] 六档案资产落地（IDENTITY+SOUL 实测 514 chars / 128 tokens，远低于 2000/500 红线）
- [x] SkillSelector 交付（GAP-CRITICAL-08b 消除：纯 ACTIVE 过滤，23 条，零排序零打分）
- [x] 质量门禁：ruff 全仓通过 / mypy 672 文件零错误 / 全量 pytest 12363 passed（32 failed 全为环境性零交集定谳：Neo4j 7475/7688 + Qdrant 6335 测试端口不可达、GPU 不可用、OCR benchmark 外部模型、redis_cache 并行 P95 抖动串行全过）
- [x] 文档同步：sisys-uni-exception-design §3.3.2（442/443 行）+ architecture.md §10.1 事件行 + §11.2.2 MVP 路径注记（D-4）+ interface-design.md §5.5 已实现注记 + §17.1 两行勘正
- [x] deferred-work.md 补登记组合根 impl 路径失效观察项（l0_storage/memory_file_storage 指向不存在路径）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/5-2-agent-identity-profile-loading.md`

**已创建的文件/Created Files（Dev Story 实施，2026-10-19）:**
- `src/domain/value_objects/agent_profile.py` - AgentProfile 值对象（frozen + 六字段自校验）
- `src/application/ports/agent_profile_loader.py` - 档案加载端口（AgentProfileLoader Protocol）
- `src/application/ports/skill_selector.py` - Skill 选择器端口（SkillSelectorPort Protocol）
- `src/application/skills/registry/__init__.py` - registry 包初始化
- `src/application/skills/registry/selector.py` - SkillSelector 实现（GAP-CRITICAL-08b）
- `src/application/use_cases/agent_profile_loading.py` - LoadAgentProfileUseCase + AgentProfileLoadResult DTO
- `src/infrastructure/agent_orch/markdown_agent_profile_loader.py` - Markdown 加载器（UTF-8 显式/64KB 字节口径/判空主检）
- `configs/agents/profiles/ceo/IDENTITY.md` - 六档案资产（322 chars）
- `configs/agents/profiles/ceo/CODE.md` - 行为准则（288 chars）
- `configs/agents/profiles/ceo/SOUL.md` - 决策价值观（192 chars）
- `configs/agents/profiles/ceo/USER.md` - 用户偏好（160 chars）
- `configs/agents/profiles/ceo/MEMORY.md` - 静态种子（233 chars）
- `configs/agents/profiles/ceo/HEARTBEAT.md` - 心跳配置占位（223 chars）
- `tests/unit/domain/value_objects/test_agent_profile.py` - 单元测试（29 项）
- `tests/unit/application/skills/test_skill_selector.py` - 单元测试（8 项）
- `tests/unit/application/use_cases/test_agent_profile_loading.py` - 单元测试（12 项）
- `tests/unit/infrastructure/agent_orch/test_markdown_agent_profile_loader.py` - 单元测试（14 项）
- `tests/unit/architecture/test_arch_agent_profile_loading.py` - 架构测试（12 项验证器 A-E）
- `tests/contracts/test_port_contract_agent_profile_loader.py` - 契约测试（12 项）
- `tests/contracts/test_port_contract_skill_selector.py` - 契约测试（12 项）
- `tests/contracts/test_port_contract_agent_profile_use_case.py` - 契约测试（12 项）
- `tests/integration/test_integration_agent_profile_loading.py` - 集成测试（3 场景）
- `tests/acceptance/test_acceptance_agent_profile_loading.feature` - Gherkin 场景（14 场景）
- `tests/acceptance/test_acceptance_agent_profile_loading.py` - BDD 步骤实现

**已修改的文件/Modified Files（Dev Story 实施）:**
- `src/domain/events/agent_events.py`（追加 AgentProfileLoaded）+ `src/domain/events/__init__.py`（导出）
- `src/domain/exceptions/agent_exceptions.py`（追加 442/443 + docstring 继承链理由）
- `src/domain/exceptions/_code_ranges.py`（预留注释改逐码登记 + _CLASS_TO_SUBDOMAIN 两映射）
- `src/domain/exceptions/__init__.py`（import + __all__）
- `src/entrypoints/agent_cli.py`（load-profile 子命令 + _parse_agent_uuid 守卫 + main 分发重构）
- `src/composition_root.py`（Story 5.2 段：3 端口注册）
- `configs/event_channels.yaml` + `src/infrastructure/messaging/channel_router.py`（AgentProfileLoaded 双登记）
- `src/interfaces/api/exception_handlers.py`（EXCEPTION_HTTP_MAP 442→500/443→404）
- `tests/unit/domain/events/test_agent_events.py`（追加 AgentProfileLoaded 9 项）
- `tests/unit/domain/exceptions/test_agent_exceptions.py`（追加 442/443 测试）
- `tests/unit/interfaces/api/test_exception_handlers.py`（Map 完备性期望集补 442/443）
- `tests/unit/interfaces/cli/test_agent_cli.py`（追加 load-profile 11 项）
- `docs/architecture/sisys-uni-exception-design.md`（§3.3.2 编码分配表 442/443 + 子域范围表）
- `docs/architecture/architecture.md`（§10.1 事件表 AgentProfileLoaded 行 + §11.2.2 MVP 路径注记）
- `docs/architecture/interface-design.md`（§5.5 已实现注记 + 实现形态标注 + §17.1 两行勘正）
- `_bmad-output/implementation-artifacts/deferred-work.md`（组合根 impl 路径失效观察项补登记）

### 变更日志 Change Log

- 2026-10-19: Story 5.2 dev-story 实施完成（Task 0-8 全绿）——领域契约（442/443 + AgentProfileLoaded + AgentProfile）、六档案资产、MarkdownAgentProfileLoader、SkillSelector（GAP-CRITICAL-08b）、LoadAgentProfileUseCase、CLI load-profile、三端口组合根注册、14 验收场景全绿、集成性能（P95<500ms 实测 ~10ms 级）、架构验证器 A-E、文档四处同步；状态 ready-for-dev → review

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 5.2 |
| **Story Key** | 5-2-agent-identity-profile-loading |
| **File** | `_bmad-output/implementation-artifacts/stories/5-2-agent-identity-profile-loading.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 5: Agent 协作系统（单 Agent 战略规划能力价值组，P0-2） |
| **价值组** | 单 Agent 战略规划能力 |
| **优先级** | P0（FR-AC-02） |
| **覆盖 FR** | FR-AC-02；FR-IF-02 Agent 侧消费；关联 NFR-IF-02（Skills 加载上下文，口径偏离声明 D-2） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-8，每 Task 含完整 TDD 循环 + 变异阶段）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-6 + 14 Gherkin 场景）
3. [x] Architecture constraints extracted 架构约束已提取（R1/R2/R4 层归属 + DC-1~DC-10 决策 + 偏离声明 D-1~D-8）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（5-1 五轮审查 12 条教训）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。
> （本节与版本历史为审查追溯记录，dev agent 实施时无需阅读。）

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | 【Round 1】档案破坏场景（AC-1.2/1.3/2.1/2.3）「场景层级」未定——走用例级且无 agent 前置会落入 443 先于 442 的守卫陷阱（守卫链 存在性→角色→加载），场景期望必炸；AC-1 When 用例级文案与场景表「手动组装 loader」端口级表述方向相反 | P0 | 四场景定稿为 **loader 端口直连**（对齐 5-1 AC-2.2/2.3 破坏场景先例），When 文案「通过档案加载端口加载」，不经用例（442 经用例传播由 Task 4 单测覆盖），无需 Redis/instantiate；AC-2.2 单独定稿为用例级（需 Redis 无需 instantiate）；AC-1.1/4.1 为用例级（先 instantiate） |
| 2 | 【Round 1】SkillSelector 端口 Protocol 与实现类同名（import/mypy/契约测试维度 4 二义），且 Dev Notes 骨架 `class SkillSelector(SkillSelectorPort)` 引用全仓不存在的基类——端口契约表与骨架自相矛盾 | P0 | 端口 Protocol 定名 `SkillSelectorPort`（对齐 `SkillLoaderPort` 先例），实现类名 `SkillSelector`（对齐 architecture.md §13.11 L2299 注释）；契约表/Task 0 签名块/结构图/Task 4 红行 AsyncMock spec 四处同步，骨架补 import 行自然成立 |
| 3 | 【Round 1】AC-6.3 收尾场景编写时点自相矛盾——Task 0「14 场景落盘 + 收集数 == 14」与测试分类表/Task 8「追加/编写收尾场景」互斥（按其一执行则另一门禁必炸） | P1 | 对齐 5-1 先例定稿：Task 0 一次落盘全部 14 场景（含 AC-6.3），Task 8 只转绿核对不新增——分类表行、Task 8 红绿行、场景表 AC-6.3 行三处同步 |
| 4 | 【Round 1】token 计量口径混用——AC-3「现状 1104」是 TOOLS.md **文件**口径（len(chars)//4），Task 4 计量是 `tool_name: description` **拼接视图**口径（实测 ~218，内容子集）——断言对象不明 + 总预算叙事（1104+500→1700）与实际计量脱节 + 分项断言无数据来源 | P1 | AC-3 定稿两口径分述（①L1 缓存口径 = TOOLS.md 全文 1104；②用例计量口径 = `"\n".join(f"{m.tool_name}: {m.description}")` 拼接 ~218——startup_context_tokens 与 AC-3.1 断言均用②）；分隔符定稿 `\n`；AC-4 补「分项由测试从 result.profile 现算」+ 取整差 ≤1 注记；DC-3 同步；下游风险#1 补口径范围警示（不含 CODE/USER/MEMORY/HEARTBEAT，5.3 装配须重定义） |
| 5 | 【Round 1】档案读取 `asyncio.to_thread(Path.read_text, ...)` 未指定 encoding——裸 read_text 依赖 locale，「非 UTF-8 → 442」契约会环境漂移（非 UTF-8 locale 下合法中文资产误判 442） | P1 | Task 0/Task 2 两处规范改为 `asyncio.to_thread(Path.read_text, path, encoding="utf-8")`（对齐 yaml_agent_config_loader/InMemorySkillLoader 显式 UTF-8 先例） |
| 6 | 【Round 1】Task 4 守卫顺序变异「441 检查移到 get_by_id 前」不可编码（role 取自 get_by_id 返回的实体，调用前无 role 可检） | P1 | 改述为「将角色守卫移至 `loader.load` 之后」→「441 且 loader 未被调用」断言红（结果型断言：错误码 + Mock 未调用） |
| 7 | 【Round 1】「零 IO/无状态」表述失实——`InMemorySkillLoader()` 构造期同步读 TOOLS.md（本地文件 IO），持有 L1/L2 缓存 | P2 | 五处措辞统一改「本地静态文件只读（构造期读 TOOLS.md 一次），无网络连接、跨循环安全」；「无状态」改「无连接状态」 |
| 8 | 【Round 1】ToolMetadata「19 字段」实为 18 字段；load_metadata L112→L119、get_all_slugs L44-109→L74-76、event_channels.yaml L177-180→L182-185（原引用是 AgentDecided 条目）、channel_router L231→L237-242、skill_loader 注册 L2529-2539→L2528-2540 | P2 | 现有代码继承表与 Dev Notes 各处行号/计数逐一勘正（主会话实测定谳） |
| 9 | 【Round 1】CLI 输出格式两处矛盾：Task 0「(N tokens)」vs Task 5「(N chars)」；「活跃技能: 23」写字面量 | P2 | 统一为 `(N chars)`（profile 字段 len 直读有据；用例无分档 token 数据来源）+ 动态值 N |
| 10 | 【Round 1】Subtask 4.5 统一「先 instantiate」配方错套 AC-2.2（无需 instantiate）与 AC-3.1（不走用例无 Redis） | P2 | 分列三档：AC-1.1/4.1 先 instantiate；AC-2.2 真实仓储+随机 uuid；AC-3.1 仅 resolve("skill_loader") 直查 |
| 11 | 【Round 1】Task 8.5 遗漏 D-4 的 architecture.md §11.2.2 注记动作；interface-design §17.1 路线图两行过期（「TOOLS.md 元数据清单 Story 5.2」「实现 SkillSelector Story 5.3」）无登记；§5.5 注记翻转无适配声明（示意 SkillRepositoryPort/Skill 形态 ≠ 实现） | P2 | 8.5 显式补三项：§11.2.2 注记（D-4）、§17.1 两行勘正、§5.5 附实现形态标注 |
| 12 | 【Round 1】溯源失实三处：「5-1 R3-F5 教训」用于死连接语义（实为 #23，R3-F5 是 Background 下沉）；D-5「or.md L1838」（实为 prd.md L1838，or.md 全文 626 行）；「5-1 修正后形态是 logger.error(exc_info=True)」（实际仅 except 分支带） | P2 | 三处逐一勘正（#23/prd.md L1838/两分支形态分述） |
| 13 | 【Round 1】Task 0.4 合法红形态缺「未注册端口解析期错误」类；红阶段区分度边界未声明 | P2 | 补第三类合法红 + 「红阶段失败形态不能证明断言正确性——活性由变异阶段背书」声明 |
| 14 | 【Round 1】P3 批量清偿：R6「14 个 @scenario」（5-1 实为 13）；资产红线「10~40 行」与 token 红线优先级未分（绑定约束是 chars≤2000）；AC-6.2 pyproject 断言标注 tripwire；幂等补「重复发布事件消费方按 event_id 幂等」；64KB 检测时机注记；registry/__init__.py 补文件清单与结构图；8.6 枚举补 AC-1.2/1.3/3.2；Task 5.5「沿用三条」实为两条+新增；AC-2.1「<64KB」→「≤64KB」；Subtask 1.3 四处→五处（EXCEPTION_HTTP_MAP 期望集测试联动）；ocr_cli 先例是 int 页码转换注记；Task 2.1 八类边界→七类计数澄清；aioredis 实为 redis.asyncio 别名注记 | P3 | 逐项修订入正文（见对应行；「chars≤2000 优先级」与「无状态→无连接状态」两子项 R1 漏落地，R2 补齐——见 #15/#16） |
| 15 | 【Round 2】BDD 步骤约束节与测试隔离表两处「本 Story 场景需先 instantiate 再 load-profile / 两步共用客户端」全局表述与场景三档定稿矛盾——9 个无 Redis 场景会被强加 instantiate 前置（复现 5-1 R3-F5 修掉的静态场景门控问题） | P2 | 两处分档化：需 instantiate 的**四**场景（AC-1.1/4.1/5.1/5.2）共用 `ctx["_redis_client"]`；AC-2.2 仅场景级客户端；端口直连/纯 resolve 九场景不创建 Redis 客户端 |
| 16 | 【Round 2】R1 修复台账两子项零落地：「无状态」→「无连接状态」（L240/L790 残留）；资产红线 chars≤2000 绑定约束未入正文 | P3 | 两子项补落地（台账声称与实际不符的 R2 勘误） |
| 17 | 【Round 2】TOOL_ID_TO_SLUG L14-38 行号错配（R1 勘正自引入——SLUG_TO_TOOL_ID 本体在 L41）；L330「唯一需要先 instantiate」与 AC-4.1/5.1/5.2 矛盾；v1.1.0 版本说明「6 P2」算术错误（实为 7 P2） | P3 | 三处勘正 |
| 18 | 【Round 2】调试日志引用表缺正文重度引用的三份文档（or.md/deferred-work.md/sisys-uni-exception-design.md）；AC-5「复用 SINGLETON 连接」混入生产语义（验证路径为场景级手动组装，无独立断言载体）；SOUL 锚点 core-domain §17.3.1 内容空洞（view 仅 "executive" 标签）；epics Gherkin TOOLS.md 物理文件语义偏离未入 D 表；§11.2.4 顺序差异（加载先于实例化 vs 本 Story DC-10 反序）未注记；中文 token 低估倍数误引（docstring 是 1.5 token/字符 vs 估算 0.25，达数倍非 1.5~2 倍）；docker_sandbox 缩写引用歧义（acceptance 版非 benchmark 版）；AC-3.1 红绿形态未定（内联现算即绿的 tripwire 无注记）；AC-1 块 And 子句仍挂用例语境；R6 骨架「服务组装」整体配方表述；Task 3 绿行缺 registry/__init__.py | P3 | 十一项逐一修订入正文（D-9 偏离声明新增） |
| 19 | 【Round 3】Task 4「发布失败两分支」测试在处方的真实 InMemoryEventBus 上不可达——`is_success==False` 唯一路径是 event_id 去重命中（用例每次新建事件无法预知 id）、raise 仅 `publish(None)`/listener 异常（文档未载）——dev 按字面实施 TDD 中段撞墙 | P1 | Task 4 红行定稿：失败两分支**换 `AsyncMock(spec=EventPublisher)`**（raise 用 side_effect / is_success=False 用空 results 的 PublishResult——5-1 test_agent_instantiation.py L264-277 先例）；真实总线仅用于成功路径与事件字段断言（失败面从用例不可达的机理注明）；编排调用序补 `_TracingEventBus` 子类先例（5-1 L50-67） |
| 20 | 【Round 3】空白校验主检位置两读缝隙——「加载器内实施」（AC-2）vs「VO 兜底」（DC-5/Task 2 绿）双读下 442 的 context 形状不同（VO 路径 profile_path 失文件名），AC-1 checklist「context 携带缺失文件名」在读法 B 下不可满足；两种实现全测绿但期望不唯一 | P2 | DC-5 定稿「判空**主检在加载器**（context.profile_path 携带文件名——AC-2 观测锚点），VO 为直接构造兜底（profile_path 可空）」；Task 2 红行空白用例补 context 断言钉住加载器实施 |
| 21 | 【Round 3】AC-1.3/2.3 同码多因断言不足——442 覆盖七类成因，仅断言错误码无区分力；场景未写明 `tmp_path/"ceo"/` 角色子目录（fixture 写根级报目录缺失 442 亦假绿）；`==23` 计数七处无 tripwire 注记（4-1f 验收资产计数联动同款教训未吸收） | P2 | AC-1.3/2.3 补 context 区分断言 + 子目录层级写明；AC-3 checklist 补 23-tripwire 全局注记（资产演进同步更新 + active_skill_count 写 `== len(result.tools_l1)` 同源派生） |
| 22 | 【Round 3】Task 7 无 TDD 循环表/无转绿声明/无变异背书（四验证器为恒真风险池——违反 Story 自身「每 Task 完整循环」全局约束）；64KB「读后 len 判定」字符/字节歧义（中文差 3 倍，与 MAX_BYTES 常量名冲突）；Task 5 新增用例红形态（SystemExit 2）未注明；AC-2.2 断言 str/UUID 形态未定稿 | P2/P3 | Task 7 补四行验证型循环表（转绿声明 + sorted/import 双变异）；DC-5/Task 2 定稿字节口径（stat 或 encode 后 len）；Task 5 红行注明 SystemExit 2 合法红；AC-2.2 定稿 `== str(agent_id)` 断言形态 |
| 23 | 【Round 5】独立终审移交簿记：v1.3.0 版本行「4 P3」计数偏差（可枚举实为 3 项，第 4 项已并入 #21）；收敛声明落盘 | P3 | 版本行内联勘误（标注 R5）；收敛声明节新增 |

### 🏁 收敛声明（Round 5 独立终审，2026-10-19）

> Story 5.2 审查周期五轮收敛：R1 文档审查 2P0+4P1+7P2+1P3（#1~14）、R2 回归核查 1P2+13P3（#15~18）、R3 深度推演 1P1+4P2+3P3（#19~22）另附 15 项证伪留痕、R4 纯验证零发现（24 组锚点抽验全精确 + 结构完整性 + 台账存续 + 游离残留零）、R5 独立终审双向取证：三个修订提交（8719b7ad/a6ffed8f/eb4e74ba）均仅含本文件且无 AI 署名；六项关键修复抽验全属实（SkillSelectorPort 四处一致、token 双口径 1104/218 与仓库实测逐字符吻合、UTF-8 两规范位、AsyncMock(EventPublisher) 先例 5-1 L264-277/L50-67 实证且「空 results」处方经 PublishResult 实现 L36-38 定谳可执行、23-tripwire 在位、Task 7 四行循环表完整）；语义层快扫零新硬伤，三处照抄先例与十余处行号锚点全部实证。**结论：收敛，保持 `ready-for-dev` 交付 `dev-story`。** 移交簿记：v1.3.0 版本行 P3 计数勘误一处（已内联标注），无阻断项。

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

> （实施后由 code-review 工作流填写。）

#### 需决策 Decision Needed

- [ ] （待实施后审查）

#### 已修复 Patch

- [ ] （待实施后审查）

#### 已推迟 Defer

- [ ] （待实施后审查）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施（从 Task 0 开始）
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.3.1
**创建日期/Created:** 2026-10-15
**最后更新/Last Updated:** 2026-10-19
**更新说明/Description:**
- v1.0.0: 创建故事文件（5 并行调研 Agent 全仓代码/规划文档/Skills 基础设施/记忆心跳基础设施/测试模板调研 + 关键签名人工核验；含链路接线断言清单 L1-L8、10 项关键架构决策 DC-1~DC-10、8 项偏离声明 D-1~D-8（SkillSelector 新旧口径/token 预算口径两处规划冲突裁决）、组合根 impl 路径失效观察项登记要求、deferred-work 分流处置）
- v1.1.0: Round 1 文档审查修订（5 调研 Agent + 2 审查 Agent 并行 + 主会话实测定谳；2 P0 + 4 P1 + 7 P2 + 1 P3 批量 = 修复表 #1~#14）——档案破坏场景定稿 loader 端口直连（443/442 守卫陷阱）、SkillSelectorPort 端口定名（同名矛盾消除）、AC-6.3 时点对齐 5-1（Task 0 落盘 14 场景）、token 两口径分述（文件 1104 vs 拼接 ~218）、read_text 显式 UTF-8、守卫变异可编码改述、行号/计数/溯源逐项勘正（19→18 字段、event_channels L182-185、#23 教训、prd.md L1838 等）
- v1.2.0: Round 2 回归核查修订（传播核查 + 增量面双 Agent；1 P2 + 13 P3）——BDD 约束/隔离表两处「先 instantiate」全局表述分档化（P0 修复的同语义漏网，适用范围定为四场景 AC-1.1/4.1/5.1/5.2）；R1 台账两子项补落地（「无状态」→「无连接状态」两处、资产红线 chars≤2000 绑定约束入正文）；TOOL_ID_TO_SLUG 行号勘正、AC-3.1 tripwire 红绿形态注记、AC-5 生产语义注记、§11.2.4 顺序差异注记、D-9 偏离声明（epics TOOLS.md 物理文件语义）、调试日志表补三行（or.md/异常设计/deferred-work）、中文 token 低估倍数勘正、docker_sandbox 全路径、AC-1 块 And 子句端口级限定、「唯一 instantiate」措辞、R6 骨架组装分档、registry/__init__.py 入 Task 3 绿行
- v1.3.0: Round 3 深度推演修订（单深度 Agent：14 场景三轴推演 + TDD 时序 + 生产失败语义对照；1 P1 + 4 P2 + **3** P3 + 15 项证伪留痕——R5 勘误：原文误记「4 P3」，可枚举实为 3 项，第 4 项 active_skill_count 同源已并入 #21 tripwire 注记）——Task 4 发布失败两分支定稿换 AsyncMock(spec=EventPublisher)（真实总线失败面不可达机理 + 5-1 L264-277 先例）；判空主检定稿在加载器（DC-5 观测锚点 + Task 2 红行 context 断言）；AC-1.3/2.3 补同码多因区分断言与 tmp_path/ceo/ 子目录层级；23 计数 tripwire 全局注记 + active_skill_count 同源派生；Task 7 补验证型四行循环表（转绿声明 + sorted/import 双变异）；64KB 字节口径定稿；Task 5 SystemExit 2 合法红注明；AC-2.2 断言 str 形态定稿
- v1.3.1: Round 4/5 收敛轮（R4 纯验证零发现——24 组锚点全精确/结构完整/台账存续/零游离；R5 独立终审六节双向取证判收敛——六项关键修复抽验全属实/红线全绿）——v1.3.0 P3 计数勘误（4→3，内联标注）+ 修复表 #23 + 收敛声明节落盘
