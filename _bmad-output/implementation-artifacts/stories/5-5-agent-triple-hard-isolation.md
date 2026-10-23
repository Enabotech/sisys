# Story 5.5: Agent 三重硬隔离保证

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 安全工程师,
**I want** 系统保证 Agent 默认隔离等级为 L4 硬隔离（Prompt/工具/数据三重硬隔离）的运行时强制执行,
**So that** 防止 Agent 间信息泄露和视角越界。

### 业务价值

Epic 5「单 Agent 战略规划能力」价值组的安全执行环：5-4 交付了 EIP 协议的**策略声明面**（`ISOLATION_POLICIES` 四级三维度表 + `IsolationState` 独立聚合 + 默认 L4 + 切换通道），本 Story 交付**运行时强制执行面**——三重隔离（Prompt/工具/数据）的统一判定核心（领域纯函数矩阵）、守卫服务（应用层 PDP 判定点）、工作流入口 fail-closed 检查与工具执行位白名单拦截、跨 Agent 穿透探针安全套件（20 条探针拦截率 100%）。这是 FR-AC-05（P0）的闭环 Story，也是 EIP 方法专利（prd.md L1164/1364）从「协议模型」到「零信任纵深防御第一层」（or.md L256/L357）的落地。下游 5.6（切换日志审计）、5.11（SAP 协议传输）、V1（动态升降级 FR-AC-09）均以本 Story 的执行面为判定底座。

**范围权威**：epics_v1.0.md L1632-1672（AC + 测试要求 + 性能锚 L1651-1655）、L462（FR-AC-05 追踪）、L1441（依赖 5.4）；prd.md L1841（FR-AC-05 P0）；architecture.md §5（L643-666 四级表——L651 明注「三重隔离的运行时强制拦截归 Story 5.5」）；or.md §八.7 L616-620（AGENT 视角隔离约束——L617 默认 L4 三重硬隔离）、L23（不变约束）、L256/L357（纵深防御第一层）、L578（四级 Prompt/工具/数据边界）；sisys-core-domain-design.md §17.3.3（L1192-1266 EIPExecutor 伪码——策略表已 5.4 交付，触发检测/自动恢复归 V1）、L1455-1460（eip_config）。

### 范围边界（与后续 Story 的精确切分）

| 能力 | 本 Story（5.5） | 后续 Story |
|------|----------------|-----------|
| 三重隔离判定核心（等级×资源×操作矩阵纯函数） | ✅ domain 纯函数 + 单测 | — |
| 守卫服务（ensure_agent_executable / ensure_agent_access / ensure_tool_access） | ✅ 应用层端口 + 实现 | — |
| 工作流入口 fail-closed 检查（447/443 拒执行） | ✅ RunAgentWorkflowUseCase 接线 | — |
| 工具执行位白名单拦截（L4 严格白名单） | ✅ AgentWorkflowService.execute 接线 | — |
| 工具白名单配置真源（eip_config.allowed_tools + ceo_agent.yaml） | ✅ | — |
| 异常 448/449（跨 Agent 越权 / 策略禁止操作） | ✅ 领取 agent 段预留码位 | — |
| 跨 Agent 穿透探针（20 条拦截率 100% + 并发 10×50） | ✅ tests/security 安全套件 | — |
| 安全测试基建（tests/security 目录/marker/CI 挂载/覆盖率口径） | ✅ | — |
| IsolationSwitchLog 切换日志、多维检索、WORM 归档 | ❌ 不做 | 5.6（P1-6） |
| 隔离切换审计记录（AuditService 调用） | ❌ 不做 | 5.6（事件 payload 是 5.6 数据源契约） |
| 违规拦截事件发布（如 IsolationViolationDetected） | ❌ 不做（拦截即异常+日志，事件 YAGNI） | V1 安全专项评估 |
| 动态触发（关键词频率/任务依赖/SYS 命令）与 30 分钟自动恢复 | ❌ 不做 | V1（FR-AC-09 P1） |
| L1 融合态开放 | ❌ MVP 禁用（446 拒绝沿用 5-4） | V2 |
| 公共黑板 API 内嵌属主过滤、get_graph_result 归属校验、L0 记忆 agent 前缀 | ❌ 不做（guard 判定面已覆盖，通道内嵌拦截归协作面 Story） | V1 协作组 / V2（见风险 #4/#5） |
| TOOLS L1 视图按白名单过滤（plan 阶段可见性） | ❌ 不做（执行位硬拦截已闭环） | V1（5-2 skill 选择器演进联动，见 DC-7） |

---

## 🔗 前置依赖（全部 ✅ 已完成，无阻塞）

| 依赖 | 组件 | 用途 | 状态 |
|------|------|------|------|
| Story 5.4 | `IsolationPolicy` VO + `ISOLATION_POLICIES` 四级表 + `MVP_ALLOWED_LEVELS` + `get_isolation_policy`（src/domain/value_objects/isolation_policy.py L27-153——L13 docstring 明示「执行时强制拦截归 Story 5.5」）+ `IsolationState` 聚合（domain/entities/isolation_state.py L57-173）+ `IsolationManagementServicePort` 三方法（application/ports/isolation_management.py L52-130——get_isolation_state L81 守卫序 443→447，docstring 钉明「隔离检查入口——5.5 执行前强制检查消费面」）+ `IsolationManagementService`（application/services/isolation_management_service.py L46-177）+ `RedisIsolationRepository`（infrastructure/storage/redis/redis_isolation_repository.py L42-172，键空间 `sisys:isolation:{agent_id}`）+ CLI set-isolation/isolation-status + 组合根注册（composition_root.py L2858-2901） | 判定输入（策略表+状态查询）与探针场景构造（切换等级）全套复用 | ✅ done |
| Story 5.4（异常段） | agent 子域段 446-447 已用；**448-449 显式预留本 Story**（`src/domain/exceptions/_code_ranges.py` L127 注释「EXCEPTION_448-449 预留（Story 5.5 三重硬隔离强制执行）」） | 新异常 448/449 码位 | ✅ 就绪 |
| Story 5.1 | `Agent` 实体（domain/entities/agent.py L39-175——**不修改**）+ `AgentRepository`（domain/ports/agent_repository.py）+ `RedisAgentRepository`（键 `sisys:agent:{agent_id}`）+ `InstantiateAgentUseCase`（四依赖含隔离初始化——本 Story 探针用它构造真实 A/B Agent）+ `AgentConfig` VO（domain/value_objects/agent_config.py L31-59——本 Story 加 allowed_tools 字段） | Agent 构造链 + 白名单配置载体 | ✅ done |
| Story 5.2 | `LoadAgentProfileUseCase`（档案加载链——本 Story 不修改）+ `AgentProfile` VO + `MarkdownAgentProfileLoader`（configs/agents/profiles/{role}/ 六档案） | Prompt 面资源语义参考 | ✅ done |
| Story 5.3 | `RunAgentWorkflowUseCase`（application/use_cases/run_agent_workflow.py L50-119——四依赖 + 编排骨位「443 存在→441 角色→档案→装配→图执行」，本 Task 3 接线改造）+ `AgentWorkflowService`（application/services/agent_workflow_service.py L102——六阶段；execute L192 起，工具位 L224-246 `get_tool` 前是白名单拦截点；构造四依赖+2 可选参）+ `WorkflowContext`/`build_context`（agent_workflow_context.py L112）+ state 形态（infrastructure/agent_orch/schemas.py L29-81——agent_id str 形态） | 两处接线位 + 回归面 | ✅ done |
| Epic 4 工具链 | `ToolRegistryServicePort`/`ToolRegistryService`（application/services/tool_registry_service.py L21-50，TOOL_CATALOG 23 战略工具）+ `ToolExecutionService`（工具唯一调用通道） | 白名单比对的工具名真源 | ✅ done |
| 异常体系 | `AgentNotFoundError`(443)/`AgentConfigError`(440)/`IsolationLevelNotSupportedError`(446)/`IsolationStateNotInitializedError`(447) 全部复用 | 守卫透传 | ✅ done |
| 测试基建 | `tests/environments.py` get_test_env()（测试端口 6380）/ `tests/integration/conftest.py` real_redis 门控 / 5-4 集成 `_assemble_real_chain()` + `_PERF_CACHE` + `ISOLATION_P95_LIMIT_SECONDS` 委托计时先例（test_integration_agent_isolation.py L47-181）| 探针与性能测试基建 | ✅ 就绪 |

**移交给本 Story 的留项（必须处置）**：

| # | 留项 | 来源 | 本 Story 处置 |
|---|------|------|--------------|
| 1 | **5-4 风险 #6**：孤儿隔离键（切换重置 TTL 使隔离键晚于 Agent 键过期）——「消费方可选自愈策略（服务级同 id 重 initialize 默认 L4）归 5.5/后续决策」 | 5-4 已知下游风险 L649 | **Task 0 评估核销**（DC-12）：本 Story 的入口 fail-closed 检查已闭合其危害面——孤儿态下 Agent 键存活/隔离键缺失 → 执行入口 447 拒（不可用即拒绝，安全方向）；自愈通道 5-4 已实现（initialize upsert 覆盖回 L4），无需新代码——核销登记 |
| 2 | **5-4 风险 #7**：同 Agent 并发切换无锁竞态（后写覆盖 + 事件序与终态可能不一致）——「5.5/V1 自动触发多源并发立项时需评估」 | 5-4 已知下游风险 L650 | **Task 0 评估维持**（DC-12）：本 Story 探针全部为跨 Agent 面（不同 agent_id 键空间天然隔离），不构造同 Agent 并发切换；触发条件（多源并发切换）仍属 V1 动态触发立项——维持 deferred 登记 |
| 3 | **R1-DF2**：StorageError(103) 同码双语义分化（触发=存储层异常码专项或 5.5） | 5-4 代码审查 deferred-work.md L200 | **维持 deferred**（DC-12）：本 Story 零存储层改动（无新仓储、无异常包装面）——触发条件不变，归存储层异常码专项 |

---

## 🔗 现有代码继承（必须复用，禁止重复定义）

> ⚠️ **防重复造轮子清单**——以下组件已存在，dev agent 只可「直接复用 / 参考照抄」，禁止新建同义组件。

| 组件 | 文件路径 | 复用方式 |
|------|---------|---------|
| `IsolationLevel` 枚举（L4_HARD/L3_SOFT/L2_COLLAB/L1_FUSED） | `src/domain/events/enums.py` L39-45 | **直接复用**——等级 SSOT（禁新建） |
| `IsolationPolicy` + `DataIsolationMode` + `ISOLATION_POLICIES` + `get_isolation_policy` | `src/domain/value_objects/isolation_policy.py` L27-153 | **直接复用**——判定矩阵唯一策略输入（三维度 `prompt_isolation`/`tool_isolation`/`data_isolation` 即本 Story 执行依据；**禁止重定义任何等级语义**） |
| `IsolationManagementServicePort.get_isolation_state`（守卫序 443→447 内聚） | `src/application/ports/isolation_management.py` L81-94 | **直接复用**——守卫服务状态入口（ensure_* 系列全部经它取状态，**禁止绕过直查 isolation_repository**——443/447 守卫序复用） |
| `switch_isolation_level`（等级切换通道） | `src/application/services/isolation_management_service.py` L112-177 | **直接复用**——探针场景构造（L2 共享面写放行、L3 受限写矩阵格需先切换等级） |
| `MVP_ALLOWED_LEVELS` | `src/domain/value_objects/isolation_policy.py` L125-127 | **直接复用**——矩阵 MVP 三级判定域 |
| `AgentConfig` + `YamlAgentConfigLoader`（eip_config 段解析先例 L121-136：缺失回落/str→枚举转换 440 守卫） | `src/domain/value_objects/agent_config.py` L31+、`src/infrastructure/agent_orch/yaml_agent_config_loader.py` L35+ | **扩展**——加 `allowed_tools` 字段 + eip_config.allowed_tools 解析（照抄 default_isolation_level 的缺失回落/类型守卫模式） |
| `configs/agents/ceo_agent.yaml`（eip_config 段 L22-24 先例） | `configs/agents/ceo_agent.yaml` | **扩展**——eip_config 追加 allowed_tools 显式清单（DC-5） |
| `PortSpec` 注册 + `# === Story 5.x ===` 区段注释惯例 + lambda 工厂注入 | `src/composition_root.py` L2678-2901（Agent 系列区） | **参考照抄**——isolation_guard_service 注册追加至该区段 |
| 端口契约测试 11 维度 + `_DummyResolver` | `tests/contracts/test_port_contract_isolation_management_service.py` | **参考照抄**——guard 契约测试同款结构 |
| 集成 `_assemble_real_chain()`（手动组装真实链——InstantiateAgentUseCase + IsolationManagementService + 双仓储） | `tests/integration/test_integration_agent_isolation.py` L83-123 | **参考照抄**——探针测试 A/B Agent 构造直接复用该形态 |
| 委托计时模式（`_PERF_CACHE` 单槽缓存 + warmup 1 + 20 采样 `statistics.quantiles(n=20)[18]` + 同名 xdist_group 同 worker 缓存命中） | `tests/integration/test_integration_agent_isolation.py` L39-55/L126-181 | **参考照抄**——新 xdist_group("agent-triple-isolation-perf") + TRIPLE_ISOLATION_P95_LIMIT_SECONDS = 0.05 常量 |
| 并发 10 gather 模式（奇偶互异目标 + keys 即时登记 + finally 批量删除 + exists 复核） | `tests/integration/test_integration_agent_isolation.py` L261-297 | **参考照抄**——并发 10×50 探针场景 |
| 验收测试骨架（PG 模板 R6 形态：多行 @scenario 字面量 + 场景绑定与步骤交替排列 + context dict fixture 场景级 Redis 客户端 + `_run_async` 同循环 + 双键清理 + AC 横幅 + 门控步骤化 skip + 延迟 import） | `tests/acceptance/test_acceptance_agent_isolation.py`（5-4 最新形态，1267 行） | **参考照抄**——R6 主体基准；PG 模板仅取 AC 横幅/门控/AST 扫描三要素（禁 then-pass 占位） |
| 异常四件套流程（定义文件 + `_code_ranges.py` 双映射 + `__init__.py` 暴露 + `EXCEPTION_HTTP_MAP` + §3.3.2 文档表） | 5-4 Task 1 循环 C 交付形态（agent_exceptions.py 446/447 段） | **参考照抄**——448/449 同款四件套 |
| `build_key(namespace, *parts)` | `src/infrastructure/storage/redis/key_builder.py` L11-22 | **直接复用**——探针清理双键构造 |
| pyproject markers 注册表 | `pyproject.toml` L253-278 | **扩展**——注册 `security` marker（`--strict-markers` L286 开启，未注册即收集期炸） |

**明确不存在、本 Story 需新建**（全仓 grep 验证：`src/` 下 `IsolationGuard|isolation_guard|ensure_agent_access|ensure_tool_access|IsolationResource|allowed_tools|IsolationAccessViolation|IsolationOperationForbidden|tests/security` 零命中；`get_isolation_state` 在 run_agent_workflow.py / agent_workflow_service.py 全文零引用——执行链零隔离消费；`tests/security/` 目录不存在）：

1. `IsolationResource` + `AccessOperation` + `IsolationAccessDecision` + `IsolationViolationKind` + `decide_isolation_access()` / `decide_tool_access()` 纯函数（domain/value_objects/isolation_access.py——判定矩阵核心）
2. `IsolationGuardPort`（application/ports/isolation_guard.py——三方法端口）
3. `IsolationGuardService`（application/services/isolation_guard_service.py——三方法实现）
4. 异常 448 `IsolationAccessViolationError` / 449 `IsolationOperationForbiddenError`
5. `AgentConfig.allowed_tools` 字段 + `YamlAgentConfigLoader` eip_config.allowed_tools 解析 + ceo_agent.yaml 白名单清单
6. `RunAgentWorkflowUseCase` 第五依赖接线（isolation_guard）+ `AgentWorkflowService` 第五依赖接线（isolation_guard + execute 工具位拦截）
7. 组合根 `isolation_guard_service` 注册
8. `tests/security/` 目录（`__init__.py` + `conftest.py` + `test_isolation_security.py`）+ pyproject `security` marker + CI integration job 挂载 `tests/security`
9. `tests/unit/application/services/test_isolation_guard_service.py` / `tests/unit/domain/value_objects/test_isolation_access.py` / `tests/unit/architecture/test_arch_agent_triple_isolation.py` / `tests/integration/test_integration_agent_triple_isolation.py` / `tests/acceptance/test_acceptance_agent_triple_isolation.{feature,py}`

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 三重隔离判定核心（domain 纯函数矩阵）

**Given** EIP 判定核心已定义（`src/domain/value_objects/isolation_access.py`）
**When** 以任意（等级 × 资源归属 × 操作 × 跨 Agent 标志）组合调用 `decide_isolation_access(policy, cross_agent=..., resource=..., operation=...)`
**Then** 判定矩阵逐格正确：**private 资源跨 Agent 访问**（L4/L3/L2 全等级全资源全操作）→ 拒绝（violation=ACCESS_VIOLATION）；**private 资源自身访问**（actor==target）→ 放行；**shared 资源读**（全等级）→ 放行；**shared 资源写**按 `data_isolation`（READ_ONLY→拒 OPERATION_FORBIDDEN / RESTRICTED_WRITE→拒[MVP 受限写白名单未定义，D-4] / FREE_WRITE→放行 / FULL_SHARED→放行）；**L1 前向语义**（private 跨 Agent→放行，FULL_SHARED 自洽——MVP 禁用但矩阵格完整，单测锁定防 V2 开放时漏改）
**And** `decide_tool_access(policy, tool_name=..., allowed_tools=...)`：`tool_isolation=False`（L3/L2/L1）→ 放行（共享工具池语义）；`tool_isolation=True`（L4）→ `tool_name ∈ allowed_tools` 放行，否则拒绝（OPERATION_FORBIDDEN）；11 种资源归属分类正确（9 private + 2 shared）

**验证标准/Validation Criteria:**
- [ ] 矩阵全格单测：MVP 三级（L4/L3/L2）× private/shared × READ/WRITE × cross/self 逐格断言 + L1 前向格
- [ ] 资源归属断言：`IsolationResource` 恰 11 成员（PROFILE/SYSTEM_PROMPT/WORKFLOW_CONTEXT/AGENT_STATE/ISOLATION_STATE/SESSION/SANDBOX_SESSION/TOOL_EXECUTION_HISTORY/MEMORY = private；BLACKBOARD/SHARED_WORKSPACE = shared）
- [ ] 决策对象字段断言（allowed/violation/reason 三件套）；violation 枚举恰两值 + None（放行）
- [ ] 纯函数零 IO（domain 零外部依赖 AST 扫描归 AC-6.3）
- [ ] **判定唯一真源**：矩阵从 `ISOLATION_POLICIES` 策略维度派生（`prompt_isolation`/`data_isolation` 字段消费），禁止在矩阵内重定义等级语义（策略表是 5-4 契约——本 AC 是其第一个执行消费方）

### AC-2: 工作流入口 fail-closed 隔离检查

**Given** Agent 已实例化且隔离状态在案（L4）
**When** 发起工作流执行（`run-task` 等价链：`RunAgentWorkflowUseCase.execute`）
**Then** 编排骨位「443 存在守卫 → 441 角色守卫 → **isolation_guard.ensure_agent_executable(agent_id)** → 档案加载 → 装配 → 图执行」——检查放行返回该 Agent 当前等级的 `IsolationPolicy`（调用方可消费三维度）；隔离状态缺失（TTL 过期/未初始化）→ `IsolationStateNotInitializedError`（447）**先于档案加载抛出**（fail-closed：隔离态不可证明即拒绝执行）；Agent 不存在 → 443（既有守卫零回归）
**And** 447 拒绝路径零副作用（无档案读取、无图执行、无事件发布——fail-closed 于最早可判定点）

**验证标准/Validation Criteria:**
- [ ] 接线序单测：构造 state 缺失场景（删隔离键）→ execute 抛 447 且 profile_use_case/agent_engine 零调用（calls 计数断言）
- [ ] 放行路径：L4 Agent execute 正常进入档案加载（既有 5-3 全量测试零回归即端到端锚）
- [ ] ensure_agent_executable 返回策略断言（L4 → prompt_isolation=True/tool_isolation=True/data_isolation=READ_ONLY）
- [ ] 443/441 既有守卫序零回归（5-3 存量测试全绿）
- [ ] P95 计时锚 = 本方法全链（AC-5.1）

### AC-3: 三面运行时守卫

**Given** 真实 A/B 两 Agent（真实 Redis 构造，均默认 L4）
**When** 调用守卫服务三方法
**Then** **Prompt 面**：`ensure_agent_access(A, B, resource=PROFILE|SYSTEM_PROMPT|WORKFLOW_CONTEXT|SESSION|SANDBOX_SESSION, operation=READ|WRITE)` → 全部 `IsolationAccessViolationError`（448，context 携带 actor_agent_id/target_agent_id/resource/operation 四字段）；**数据面**：AGENT_STATE/ISOLATION_STATE/MEMORY/TOOL_EXECUTION_HISTORY 跨 Agent 读写 → 448；**共享面矩阵**：BLACKBOARD READ（L4）→ 放行、BLACKBOARD WRITE（L4）→ 449（READ_ONLY）、BLACKBOARD WRITE（切换 L2 后）→ 放行（FREE_WRITE）、BLACKBOARD WRITE（切换 L3 后）→ 449（受限写 MVP 拒，D-4）；**工具面**：`ensure_tool_access(A, tool)`（L4）白名单外 → 449（context 携带 agent_id/tool_name/allowed_tools）、白名单内 → 放行；`ensure_tool_access(A, tool)`（切换 L3 后，tool_isolation=False）→ 放行（共享池）；**自身资源**：actor==target 全资源全操作 → 放行
**And** 守卫透传序：actor 状态获取经 `get_isolation_state`（443/447 全继承——447 场景 = 隔离键缺失时任何 ensure_* 均拒）

**验证标准/Validation Criteria:**
- [ ] 三面各至少一条真实链断言（真实 Redis 构造 A/B，非纯单测——归 AC-4 探针矩阵全量覆盖）
- [ ] 448/449 context 字段逐项断言（isinstance → code → context 三段式——Agent 验收惯例）
- [ ] 等级切换后矩阵随动（L4→L2 切换后共享面写放行——策略表活消费实证）
- [ ] 白名单判定经 `AgentConfig.allowed_tools` 真源（config_loader.load(agent.role)——禁硬编码）
- [ ] 放行对照场景 ≥4（自身资源/共享读/L2 共享写/白名单内工具）——证明判定非一刀切

### AC-4: 跨 Agent 穿透探针矩阵（安全套件）

**Given** 真实 A/B 两 Agent（真实 Redis 6380，`SISYS_USE_TEST_PORTS=1`），A 为 L4 硬隔离（默认），B 为探针目标
**When** 执行 20 条跨 Agent 穿透探针（Task 0 定稿矩阵——P-01~06 Prompt 面 6 条 / T-01~04 工具面 4 条 / D-01~10 数据面 10 条）
**Then** 拦截率 100%：15 条 → 448（跨 Agent 越权）、5 条 → 449（T-01/T-04 白名单外工具 + D-08/D-09 共享面写 L4/L3 + D-10 共享工作区写 L4）；每条探针断言异常类型 + code + context 关键字段
**And** 探针用例形态：真实隔离状态 + 真实守卫服务链（手动组装——`_assemble_real_chain` 形态扩展 guard），**禁 mock**（安全测试 = 验收级真实服务纪律）；未注册工具名探针（T-04）取 TOOL_CATALOG 真实存在的白名单外工具名（判别力——假名会先炸「工具不存在」而非白名单拒绝）

**验证标准/Validation Criteria:**
- [ ] 20 条探针逐条独立断言（非循环套表弱断言——每条探针独立测试函数或参数化用例带 id）
- [ ] 拦截率分子分母显式断言（20/20——与 AC-5.2 通过率分立）
- [ ] T-01/T-04 白名单外工具经「配置篡改」构造（ceo_agent.yaml 全文复制到 tmp、收窄 allowed_tools——5-4 AC-2.3 驱动先例）；生产 yaml 保持宽白名单（5-3 主链兼容）
- [ ] 探针矩阵定义即文档（docstring 内 20 条清单表——安全审计资产）

### AC-5: 性能与并发

**Given** 真实 Redis（测试端口 6380）
**When** 测量隔离检查与并发穿透
**Then** 隔离检查延迟 P95<50ms（epics L1653——计时锚 = `ensure_agent_executable` 服务全链：get_isolation_state[443 守卫 + 隔离态读两次真实 Redis 读] + 策略联查，warmup 1 + 20 采样 `statistics.quantiles(n=20)[18] < 0.05`）；隔离检查通过率 100%（20 次连续检查全放行，分子分母断言）；并发 Agent≥10 无泄露（epics L1655：10 个 Agent 并行，每 Agent 发起 50 次跨隔离探针 = 500 探针，拦截率 100%）
**And** 计时委托集成模块 helper（`_PERF_CACHE` 单槽缓存 + `xdist_group("agent-triple-isolation-perf")` 同 worker 串行——5-4 委托模式照抄，禁 20 采样双跑）；并发场景 `asyncio.gather` + 探针键即时登记清理

**验证标准/Validation Criteria:**
- [ ] P95：TRIPLE_ISOLATION_P95_LIMIT_SECONDS = 0.05 常量单源（验收/集成共享 import）；本地 Redis 两读 ~2ms，预算 25 倍裕量
- [ ] 通过率：20 次连续 ensure_agent_executable（20 个真实 Agent 或同 Agent 20 轮）全放行 20/20
- [ ] 并发 10×50：10 Agent 并发构造 + 每 Agent 对固定探针目标集发 50 探针（448/449 断言）+ 拦截率 500/500 + 双键清理 exists 复核
- [ ] 并发探针目标等级互异设计（奇数目标 L4/偶数目标 L3——矩阵判定在并发下不串扰）
- [ ] 计时场景 xdist_group 串行 + benchmark 场景级标记（验收侧不打文件级——5-2 R1-F8 先例）

### AC-6: 端口接线、架构合规与安全测试基建

**Given** 判定核心、守卫服务、接线、安全基建全部交付
**When** 验证接线与合规
**Then** 新端口 `isolation_guard_service`（SINGLETON）经组合根注册且 resolve 可达（PortSpec 全参数含 module/owner）；`RunAgentWorkflowUseCase` 与 `AgentWorkflowService` 组合根 lambda 注入第五依赖（接线完整）；domain 零外部依赖（isolation_access.py/guard 异常 AST 扫描）；组合根外零实例化；**安全测试基建就绪**：`tests/security/` 目录 + conftest 存在、pyproject markers 注册 `security`、CI integration job pytest 路径含 `tests/security`（探针需真实 Redis——挂载有服务栈的 job）、安全覆盖率口径落地（专项命令对执行面模块 fail-under 90）
**And** 白名单接线行为锚：`AgentWorkflowService.execute` 中 plan 步骤的工具名先过 `ensure_tool_access`（白名单外 → 449 真实拒，ToolNotFoundError 不再先炸）；既有 5-3 工作流全量测试零回归（CEO 白名单覆盖其工具面）

**验证标准/Validation Criteria:**
- [ ] 组合根注册 + resolve + isinstance + lifetime==SINGLETON 断言（5-4 AC-6.1 同款）
- [ ] 两接线点 lambda 注入确认（构造签名扩展——回归面清单全量同步见 Task 3）
- [ ] 架构验证器：domain 零外部依赖 + 组合根外零实例化（IsolationGuardService）+ 端口方向（application 服务 import 白名单含 application.ports）
- [ ] 基建四件套断言（文件存在性 + pyproject `security` marker 在注册表 + ci.yaml integration job pytest 命令含 tests/security + 专项覆盖率命令可执行）
- [ ] 5-3 验收/集成存量测试零回归（run-task 主链 + 工具执行链）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] **不新建领域事件**——本 Story 是拦截执行面（拦截即异常 + logger.warning，违规事件发布 YAGNI——归 V1 安全专项评估，范围边界表已列）。既有 `IsolationLevelSwitched` 仅在探针场景构造（切换等级用）时被真实发布，零改动零登记。

#### 数据模型 (Data Models)

- [ ] `IsolationResource(str, Enum)`（domain/value_objects/isolation_access.py 内定义）——11 成员两归属类：
  - **private（9，Agent 命名空间私有）**：`PROFILE`（身份档案）/ `SYSTEM_PROMPT`（运行时系统提示词）/ `WORKFLOW_CONTEXT`（工作流上下文与六阶段中间产物）/ `AGENT_STATE`（Agent 实体状态）/ `ISOLATION_STATE`（隔离状态）/ `SESSION`（会话与快照）/ `SANDBOX_SESSION`（沙箱会话）/ `TOOL_EXECUTION_HISTORY`（工具执行历史）/ `MEMORY`（L0 记忆与记忆缓存）
  - **shared（2，协作共享面）**：`BLACKBOARD`（公共黑板）/ `SHARED_WORKSPACE`（共享工作区）
  - 值用小写下划线形态（`profile`/`system_prompt`/...——对齐 DataIsolationMode 命名风格）
- [ ] `AccessOperation(str, Enum)`：`READ = "read"` / `WRITE = "write"`（写涵盖增删改——MVP 不细分）
- [ ] `IsolationViolationKind(str, Enum)`：`ACCESS_VIOLATION = "access_violation"`（对应 448）/ `OPERATION_FORBIDDEN = "operation_forbidden"`（对应 449）
- [ ] `IsolationAccessDecision` frozen dataclass：`allowed: bool` / `violation: IsolationViolationKind | None`（放行时 None）/ `reason: str`（中文判定依据——审计可读）——`__post_init__` 不变量（allowed=True 时 violation 必为 None；allowed=False 时 violation 必非 None——失败抛 242）
- [ ] `decide_isolation_access(policy: IsolationPolicy, *, cross_agent: bool, resource: IsolationResource, operation: AccessOperation) -> IsolationAccessDecision` 模块级纯函数——判定矩阵（唯一真源，禁止在 guard/测试中重写矩阵逻辑）：
  1. `resource` 是 shared：READ → 放行（全等级）；WRITE → 按 `policy.data_isolation`（READ_ONLY→拒[OPERATION_FORBIDDEN] / RESTRICTED_WRITE→拒[OPERATION_FORBIDDEN，MVP 受限写白名单未定义 D-4] / FREE_WRITE→放行 / FULL_SHARED→放行）
  2. `resource` 是 private 且 `not cross_agent`：放行（自身资源自由读写）
  3. `resource` 是 private 且 `cross_agent`：`policy.prompt_isolation` 为 True（L4/L3/L2——三级全部独立）→ 拒[ACCESS_VIOLATION]；False（L1 融合态）→ 放行（FULL_SHARED 语义自洽——MVP 禁用但矩阵格完整，单测锁定 V2 前向）
  - **矩阵从策略字段派生**（prompt_isolation/data_isolation 消费 5-4 契约），本函数零等级硬编码
- [ ] `decide_tool_access(policy: IsolationPolicy, *, tool_name: str, allowed_tools: Collection[str]) -> IsolationAccessDecision` 纯函数：`policy.tool_isolation` False（L3/L2/L1 共享池）→ 放行；True（L4 严格隔离）→ `tool_name in allowed_tools` 放行 else 拒[OPERATION_FORBIDDEN]（reason 携带工具名与白名单规模——禁泄露全白名单内容进 reason，白名单明细走异常 context）
- [ ] `resource_is_private(resource: IsolationResource) -> bool` helper（矩阵第 1/2 步分类依据 + AC-1.2 断言面）
- [ ] `AgentConfig.allowed_tools: tuple[str, ...] = ()` 字段扩展（domain/value_objects/agent_config.py——frozen VO 惯例 tuple 形态；默认空元组 = L4 下全部工具被拒的 fail-closed 安全默认）：`__post_init__` 守卫——元素非 str / 空白串元素 → `AgentConfigError`（440，配置资产 VO 分码——5-4 R1-F03 分界原则沿用）；去重归一由 loader 承载（重复项去重保序——配置容错）
- [ ] `YamlAgentConfigLoader` 扩展：eip_config 段解析 `allowed_tools`（缺失 → 空元组；类型守卫非 list → 440；元素空串/空白 → 440——reason 中文自然语言）——照抄 default_isolation_level 解析形态（yaml_agent_config_loader.py L121-136 先例）

#### 统一端口定义注册与管理 (Port Contract)

- [ ] `IsolationGuardPort`（`src/application/ports/isolation_guard.py`，`@runtime_checkable Protocol`——**R2 应用层具体应用端口，组合注入下层端口**）三方法：
  - `async def ensure_agent_executable(self, agent_id: uuid.UUID) -> IsolationPolicy`——工作流执行前置检查（fail-closed）。内部：`get_isolation_state(agent_id)`（443→447 守卫序全继承）→ `get_isolation_policy(state.current_level)` 返回策略。Raises 契约：443/447 透传
  - `async def ensure_agent_access(self, actor_agent_id: uuid.UUID, target_agent_id: uuid.UUID, resource: IsolationResource, operation: AccessOperation) -> None`——跨 Agent 资源访问守卫。内部：actor 状态获取（经 isolation_management_service——443/447 透传）→ `decide_isolation_access(policy, cross_agent=(actor != target), ...)` → 拒绝时按 violation 抛 448/449。放行静默返回 None
  - `async def ensure_tool_access(self, agent_id: uuid.UUID, tool_name: str) -> None`——工具白名单守卫。内部：状态获取（443/447）→ agent（经 agent_repository.get_by_id 取 role）→ `config = agent_config_loader.load(agent.role)` → `decide_tool_access(policy, tool_name=tool_name, allowed_tools=config.allowed_tools)` → 拒绝抛 449
- [ ] `IsolationGuardService`（application/services/isolation_guard_service.py）实现类——**三依赖组合注入（R2）**：`isolation_management_service: IsolationManagementServicePort`（应用端口——状态+守卫序复用，禁绕过直查仓储）/ `agent_repository: AgentRepository`（domain R1 基础端口——role 取得）/ `agent_config_loader: AgentConfigLoader`（应用端口——白名单真源）
- [ ] 端口注册中心/解析器/契约门禁纪律照旧；组合根注册元数据：
  - `isolation_guard_service`：v1.0.0 / `IsolationGuardPort` / `IsolationGuardService`（lambda 注入 isolation_management_service + agent_repository + agent_config_loader 三依赖）/ module=src.application.services.isolation_guard_service / SINGLETON（无状态纯判定服务——agent_repository SCOPED 捕获关系无实害注记沿 5-4 DC-7 形态）/ owner=platform / tags=("agent", "isolation", "security")
- [ ] **既有端口消费方变更（契约变更登记 ×2）**：
  - `RunAgentWorkflowUseCase` 构造签名扩展第五依赖 `isolation_guard: IsolationGuardPort`（必填——**弃 None 容忍**：守卫可被绕过是安全缺口，回归面全量同步一次到位，5-4 Task 4 苦役先例）+ execute 编排骨位插入（441 后、档案加载前：`await self._isolation_guard.ensure_agent_executable(agent_id)`——结果策略 MVP 暂不消费，前置 fail-closed 是目的）
  - `AgentWorkflowService` 构造签名扩展第五依赖 `isolation_guard: IsolationGuardPort`（必填，同上）+ execute 工具位拦截（`get_tool` 前：`await self._isolation_guard.ensure_tool_access(uuid.UUID(state["agent_id"]), tool_name)`——state["agent_id"] 是 str 形态[schemas.py L67]，需 UUID 显式转换）
- [ ] 端口契约测试一份（`tests/contracts/test_port_contract_isolation_guard.py`，11 维度 + DummyResolver 三依赖）
- [ ] **禁止**在服务文件本地定义 Protocol / Port 抽象；**禁止**新建语义重复端口（状态查询复用 isolation_management_service、白名单取值复用 agent_config_loader、工具存在性查询归 tool_registry_service——guard 不查注册表，白名单比对是配置面判定）

#### 端口契约清单执行约束（强制）

- [ ] 本 Story 端口清单唯一真源 = 本 Task 0 定义（`isolation_guard_service` 一新端口 + 两项既有端口消费方变更：RunAgentWorkflowUseCase / AgentWorkflowService 构造签名扩展——契约变更登记，既有两用例/服务的契约测试 impl 维度与组合根 lambda 同步）
- [ ] 禁止新增未登记端口；禁止未同步 registry/resolver/contract test
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> 原则/适用范围/禁止条款同模板基线。本 Story 领取 agent 子域预留段 448-449（`_code_ranges.py` L127 显式预留本 Story）。设计决策见 DC-4。

- [ ] `IsolationAccessViolationError`（EXCEPTION_448，BusinessException）——**跨 Agent 私有资源访问越权**（Prompt/数据面全资源：actor ≠ target 且目标资源归属 private 类）。构造器（对齐 446/441 家族形态——首参必填）：`(actor_agent_id: str, target_agent_id: str, resource: str, operation: str, message=None, cause=None)`，context 携带 `{actor_agent_id, target_agent_id, resource, operation}`；HTTP **403**（权限不足族——Forbidden 语义，非 404 资源不存在也非 422 取值非法）。消息面向调用方可理解（如「Agent 间私有资源访问被隔离策略拒绝」——**禁泄露资源内容/内部键名**，仅资源类别）
- [ ] `IsolationOperationForbiddenError`（EXCEPTION_449，BusinessException）——**当前隔离等级策略禁止的操作**（两类触发：L4 白名单外工具请求；READ_ONLY/RESTRICTED_WRITE 等级下共享面写）。构造器：`(agent_id: str, operation: str, reason: str = "", message=None, cause=None)`，context 携带 `{agent_id, operation, reason}`（工具场景 reason 形如 `tool_not_in_allowlist:{tool_name}`；共享面写场景 reason 形如 `data_isolation:read_only`）；HTTP **403**。与 448 的分界：448 = **跨主体**越权（actor≠target 私有资源）；449 = **单主体**操作被自身等级策略禁止——两个语义轴正交，禁混用
- [ ] 复用不新建：`AgentNotFoundError`(443)/`IsolationStateNotInitializedError`(447)（守卫透传）/`AgentConfigError`(440)（allowed_tools 配置校验）/`EntityValidationError`(242)（IsolationAccessDecision 不变量）
- [ ] 强制 4 项 checklist：定义文件（agent_exceptions.py 追加）/ `_code_ranges.py` CODE_RANGES 注释「预留」改「已分配」+ `_CLASS_TO_SUBDOMAIN` 两映射 / `__init__.py` 暴露（import 块 + `__all__`）/ `EXCEPTION_HTTP_MAP` 精确注册 448→403、449→403；`sisys-uni-exception-design.md` §3.3.2 编码分配表同步（448/449 两行，agent 段 440-449 至此全分配）
- [ ] 测试覆盖：`tests/unit/domain/exceptions/test_agent_exceptions.py` 追加（构造/context/to_dict/HTTP 映射 + 448 四字段 context + 449 双触发路径参数化）+ `test_code_ranges.py` 子域校验自然覆盖 + `test_exception_handlers.py` expected_types 同步双锁
- [ ] BDD 异常路径：448（探针矩阵 15 条）/449（探针矩阵 5 条）纳入安全套件与验收 Edge Cases

#### API 契约 (API Contract)

- [ ] 本 Story 无 REST API、无新 CLI 子命令（守卫是内嵌执行面非用户功能——探针是测试面）。CLI 既有 `set-isolation`/`isolation-status` 零改动（探针场景经服务级调用构造等级）
- [ ] 配置契约：`configs/agents/ceo_agent.yaml` eip_config 段追加 `allowed_tools` 显式清单——**初值 = TOOL_CATALOG ACTIVE 全集**（保证 5-3 主链与既有验收/集成测试零回归——plan 阶段 LLM 可选工具均在白名单内）；探针判别力经「配置篡改」获得（tmp 目录收窄白名单——AC-4 验证标准）。清单按 `strategic_tool_catalog.py` 实际 tool_name 逐项列出（dev 实施时从 `TOOL_CATALOG` 提取，**禁省略号/通配**——显式性即审计性）

#### 六边形架构约束（必须遵守）

> 四层定义/零依赖原则/依赖方向矩阵同模板基线。本 Story 特别注意：

- [ ] `isolation_access.py`（枚举 + 决策 + 纯函数）全部 domain 层，仅标准库 + 同层 isolation_policy/events.enums/exceptions——`.importlinter` domain 契约（禁 pydantic/redis）
- [ ] `IsolationGuardService`（application）构造注入一应用端口（isolation_management_service）+ 一 domain 端口（agent_repository）+ 一应用端口（agent_config_loader）——application→application 同层合法（5-4 先例）+ application→domain 合法；禁 import infrastructure
- [ ] 两接线点（use_case/services）注入 `IsolationGuardPort`（application 端口）——同层端口组合注入合法（R2）
- [ ] tests/security/ 是测试目录不属四层；探针测试手动组装（组合根外实例化白名单覆盖 tests/ 前缀——test_arch 验证器 B 白名单惯例）

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_agent_triple_isolation.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_agent_triple_isolation.py`
- [ ] 场景组织：AC 注释横幅分组 + 全场景逐一 `@scenario` 显式绑定（多行字面量路径 + 场景绑定与步骤交替排列——5-4 R6 改造后形态，禁 `scenarios()` 批量绑定与 then-pass 占位）；场景名 `AC-x.y - 中文描述`（ASCII 连字符两侧空格，feature 与 .py 逐字一致）
- [ ] 20 场景规划（Task 0 定稿分档表）：
  - AC-1 ×2（端口级，无 Redis）：判定矩阵完备性（MVP 三级全格 + L1 前向）/ 资源归属与工具判定
  - AC-2 ×3（服务级，真实 Redis）：L4 放行返回策略 / 447 拒执行（删隔离键）/ 443 拒执行（随机 UUID）
  - AC-3 ×5（服务级，真实 Redis）：Prompt 面 448 / 私有数据面 448（读+写）/ 共享面矩阵（L4 读放行 + L4 写 449 + L2 写放行）/ 工具白名单（449 + 白名单内放行）/ 自身资源放行
  - AC-4 ×2（安全套件资产面——验收侧断言套件存在与探针矩阵定义完备性[文件 + 场景计数 + 20 条清单]，20 探针实跑归 tests/security——分档口径 DC-10）：探针矩阵资产就绪 / 拦截率断言口径
  - AC-5 ×3（委托集成计时 + 并发自跑）：P95<50ms（委托 helper）/ 检查通过率 100% / 并发 10×50 零泄露
  - AC-6 ×4（端口级 + 服务级）：组合根接线 / 入口接线真实链（instantiate→run-task 主链零回归 + 447 fail-closed 验收面）/ 架构合规静态扫描 / 安全测试基建就绪（四件套）
  - 收尾 ×1：完成清单逐项确认
- [ ] BDD 步骤约束：`event_loop.run_until_complete()`（禁 `@pytest.mark.asyncio`）；Redis 依赖场景前置「假如 Redis 缓存服务可用」门控步骤（ping 失败 `pytest.skip` 动态跳过）；纯端口级场景（AC-1×2、AC-6 部分扫描）脱离门控；参数化步骤显式 `parsers.parse`（5-4 实施期发现——pytest-bdd 默认 re parser）
- [ ] **场景三属性分档表**（Task 0.6 定稿落 docstring）：每场景「层级（端口级/服务级）+ Redis 依赖（真实/无）+ 断言面（异常矩阵/放行对照/性能/静态扫描）」
- [ ] 显式 `pytestmark = [pytest.mark.acceptance, pytest.mark.redis, pytest.mark.xdist_group(...)]`（文件名不含服务关键词）+ 延迟 import 纪律（本 Story 新模块一律步骤函数体内延迟 import）
- [ ] teardown 双键精确清理：context 记录 `_agent_ids`（A/B/并发 10 全登记），删 `build_key("agent", ...)` + `build_key("isolation", ...)` 双键 + `exists` 复核删净（禁 delete_pattern/flush/全库 scan_iter）；探针拒绝路径预生成 uuid 不登记（零残留断言面）

#### 20 条探针矩阵定稿（Task 0 唯一真源——安全审计资产）

| # | 面 | 资源 | 操作 | 前置等级 | 预期 |
|---|-----|------|------|---------|------|
| P-01 | Prompt | PROFILE | READ | A=L4 | 448 |
| P-02 | Prompt | SYSTEM_PROMPT | READ | A=L4 | 448 |
| P-03 | Prompt | WORKFLOW_CONTEXT | READ | A=L4 | 448 |
| P-04 | Prompt | WORKFLOW_CONTEXT | WRITE | A=L4 | 448 |
| P-05 | Prompt | SESSION | READ | A=L4 | 448 |
| P-06 | Prompt | SANDBOX_SESSION | READ | A=L4 | 448 |
| T-01 | 工具 | 白名单外工具（窄配置） | EXECUTE | A=L4 | 449 |
| T-02 | 工具 | TOOL_EXECUTION_HISTORY | READ | A=L4 | 448 |
| T-03 | 工具 | TOOL_EXECUTION_HISTORY | WRITE | A=L4 | 448 |
| T-04 | 工具 | 白名单外工具（TOOL_CATALOG 真实名，窄配置） | EXECUTE | A=L4 | 449 |
| D-01 | 数据 | AGENT_STATE | READ | A=L4 | 448 |
| D-02 | 数据 | AGENT_STATE | WRITE | A=L4 | 448 |
| D-03 | 数据 | ISOLATION_STATE | READ | A=L4 | 448 |
| D-04 | 数据 | ISOLATION_STATE | WRITE | A=L4 | 448 |
| D-05 | 数据 | SESSION | WRITE | A=L4 | 448 |
| D-06 | 数据 | MEMORY | READ | A=L4 | 448 |
| D-07 | 数据 | MEMORY | WRITE | A=L4 | 448 |
| D-08 | 数据 | BLACKBOARD（shared） | WRITE | A=L4 | 449（READ_ONLY） |
| D-09 | 数据 | BLACKBOARD（shared） | WRITE | A=L3（切换） | 449（受限写 MVP 拒） |
| D-10 | 数据 | SHARED_WORKSPACE（shared） | WRITE | A=L4 | 449（READ_ONLY） |

> 统计：448×15 + 449×5 = 20，拦截率 100% 断言面 = 20/20。放行对照（不在 20 条内，AC-3 场景断言）：自身资源全操作 / BLACKBOARD READ（L4）/ BLACKBOARD WRITE（L2 切换后）/ 白名单内工具（L4）/ 共享池工具（L3 切换后）。T-01 与 T-04 的区分：T-01 用任意窄白名单外名（构造简单），T-04 强约束 TOOL_CATALOG 真实存在名（判别力锁定——证明白名单判定先于工具存在性判定，非靠「工具不存在」误拦截）。

#### 安全测试基建契约（Task 0 定稿——DC-8）

- [ ] `tests/security/__init__.py` + `tests/security/conftest.py`（场景级 Redis 客户端 fixture + ping 门控 skip——对齐 tests/integration/conftest.py real_redis 形态的精简版）+ `tests/security/test_isolation_security.py`
- [ ] pyproject `[tool.pytest.ini_options].markers` 追加 `"security: 安全探针套件（跨 Agent 穿透/隔离强制执行验证）"`（`--strict-markers` 下未注册即收集期炸——必改）
- [ ] CI 挂载：`.gitea/workflows/ci.yaml` integration-tests job 的 pytest 命令 `tests/integration tests/contracts` 扩展为 `tests/integration tests/contracts tests/security`（探针需真实 Redis——该 job 已 compose 起服务栈；unit-tests job 不动[无服务栈，探针全 skip 造成假绿幻觉]；security-scan job 是纯静态扫描[Bandit/detect-secrets/Trivy]不混入 pytest 面）
- [ ] 安全覆盖率口径（epics「安全测试覆盖率≥90%」实例化——D-2 偏离声明）：专项命令 `poetry run pytest tests/security --cov=src.application.services.isolation_guard_service --cov=src.domain.value_objects.isolation_access --cov-fail-under=90`（安全套件对**三重隔离执行面模块集**的语句覆盖率 ≥90%）——落地为 Makefile target `test-security`（含覆盖率门禁）+ CI integration job 内联同款 step；与四层门禁（check_coverage_gates.py）并存不替代
- [ ] 安全套件 pytestmark：`[pytest.mark.security, pytest.mark.redis, pytest.mark.integration]`（语义上属集成族——CI 挂 integration job 一致）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕；Gherkin 已编写且运行确认失败（红阶段验证——ModuleNotFoundError/断言红为合法红）
- [ ] **链路接线断言清单**（Epic 4 行动项 7.1-1）：
  1. `isolation_guard_service` 组合根 register_port 装配验证（resolve 可达 + isinstance + PortSpec 元数据 + lifetime）
  2. `RunAgentWorkflowUseCase` lambda 注入 isolation_guard 确认（**端到端锚：resolve 用例 → 删隔离键 → run-task 抛 447**——lambda 漏注入则入口检查静默缺失，验收 AC-2.2 抓红）
  3. `AgentWorkflowService` lambda 注入 isolation_guard 确认（**端到端锚：窄白名单配置 → execute 传白名单外工具步骤 → 449**）
  4. 事件面：本 Story 零新事件零登记（复验既有 IsolationLevelSwitched 双登记不漂移——探针构造切换时真实发布）
  5. tests/security 四件套（目录/marker/CI/覆盖率命令）接线断言（AC-6.4）
- [ ] **移交三项处置落盘**（DC-12：#6 核销登记 + #7 维持 + R1-DF2 维持——deferred-work.md 原条目更新）

---

### TDD 循环约束（适用于每个 Task）

> 每 Task 依次执行 🔴红→🟢绿→🟡变异→🔄重构；变异实证 = 对新行为契约的断言改坏→红→还原→绿（Epic 4 行动项 7.1-2 强制）。禁止行为四条同模板基线（先码后测/测试后置/跳红/跳变异）。

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| TDD 单元测试 | isolation_access 纯函数 | 判定矩阵全格/资源归属/决策不变量/工具判定 | `tests/unit/domain/value_objects/test_isolation_access.py` | Task 1 |
| TDD 单元测试 | AgentConfig.allowed_tools | 字段守卫 440/loader 解析（缺失回落空/类型守卫/去重保序）/ceo_agent.yaml 集成值 | `tests/unit/domain/value_objects/test_agent_config.py`（追加）+ `tests/unit/infrastructure/agent_orch/test_yaml_agent_config_loader.py`（追加） | Task 1 |
| TDD 领域异常测试 | 448/449 | 构造/context/to_dict/HTTP 映射/双触发路径参数化 | `tests/unit/domain/exceptions/test_agent_exceptions.py`（追加）+ `tests/unit/interfaces/api/test_exception_handlers.py`（追加） | Task 1 |
| TDD 单元测试 | IsolationGuardService | 三方法守卫序/矩阵消费/白名单真源/443·447 透传/异常分码（AsyncMock spec 三端口——单测 Mock 端口合规） | `tests/unit/application/services/test_isolation_guard_service.py` | Task 2 |
| TDD 契约测试 | isolation_guard_service | 11 维度 + DummyResolver 三依赖 | `tests/contracts/test_port_contract_isolation_guard.py` | Task 2 |
| TDD 单元测试 | RunAgentWorkflowUseCase 接线 | 第五依赖/447 fail-closed 先于档案/443·441 零回归/放行策略断言 | `tests/unit/application/use_cases/test_run_agent_workflow.py`（追加 + 存量同步——存量构造点补依赖） | Task 3 |
| TDD 单元测试 | AgentWorkflowService 工具位 | 第五依赖/白名单外 449 先于 get_tool/白名单内放行/L3 共享池放行/无工具步骤直推理零守卫调用 | `tests/unit/application/services/test_agent_workflow_service.py`（追加 + 存量同步——文件名以仓库实际为准） | Task 3 |
| TDD 验收测试 | Gherkin + BDD | 20 场景 Task 0 编写（收尾场景 Task 7 追加）；各 Task 转绿——AC-1 随 Task 1、AC-2/AC-3 随 Task 2/3、AC-4 随 Task 4、AC-5×3 随 Task 5、AC-6 随 Task 3/6 | `test_acceptance_agent_triple_isolation.feature/.py` | Task 0-7 |
| 安全测试（探针套件） | 跨 Agent 穿透 | 20 探针矩阵 100% 拦截/真实 A/B 链/矩阵定义资产 | `tests/security/test_isolation_security.py` | Task 4 |
| SDD 架构验证 | 六边形约束 | domain 零外部依赖/组合根外零实例化/端口方向/接线静态锚 | `tests/unit/architecture/test_arch_agent_triple_isolation.py` | Task 6 |
| 集成测试 | 全链（真实 Redis） | A/B 构造 + 守卫矩阵抽查/P95<50ms/通过率 20/20/并发 10×50/入口 fail-closed 真实链/execute 白名单 449 真实拒 | `tests/integration/test_integration_agent_triple_isolation.py` | Task 5 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] 整体 ≥80%（P0 阻断）；domain ≥90%（判定矩阵主战场）；**应用层 ≥85%**（守卫服务主战场）；infrastructure ≥75%（本 Story 零新仓储——维持）；四档与 `scripts/check_coverage_gates.py` 一致
- [ ] **安全覆盖率专项 ≥90%**：`pytest tests/security --cov=<执行面模块集> --cov-fail-under=90`（D-2 口径——Makefile `test-security` target + CI integration job step）
- [ ] 集成测试覆盖率 ≥75%（沿 5-2/5-3/5-4 先例）；关键分支可执行口径：矩阵四分支（shared-write/private-cross/private-self/工具白名单）各配独立命名测试用例（用例名即分支清单）

#### 代码质量门禁

- [ ] `ruff check src/ tests/` + `mypy src/`（pre-commit mypy 覆盖 tests/）+ `pre-commit run` 全过
- [ ] 三条红线自查零输出（`raise ValueError`/手动 `HTTPException`/继承内置 Exception）+ 零抑制注释
- [ ] 提交信息零 AI 署名

#### 测试隔离约束

> 基线同模板（事务隔离/UUID 唯一/并行隔离/清理粒度/asyncio 纪律全表）。本 Story 特别注意：

- [ ] **验收/集成/安全三面双键清理**：A/B/并发 10 全部 `_agent_ids` 登记，teardown 逐 agent 删双键 + exists 复核（探针 448 拒绝路径的 target Agent 也要清理——它被真实创建）
- [ ] **场景级独立 Redis 客户端 + `_run_async` 同循环**（session 级客户端跨场景 "Event loop is closed"——禁共享 fixture）
- [ ] **手动组装纪律**：验收/安全探针禁 `resolve("isolation_guard_service")` 发真实命令——SINGLETON 跨 function-scope 循环复用死连接；一律场景级客户端手动组装（IsolationManagementService + RedisAgentRepository + RedisIsolationRepository + IsolationGuardService 全真实链——`_assemble_real_chain` 形态扩展 guard；agent_config_loader 经 resolve 取无状态实例合法）；resolve 仅 AC-6.1 接线断言且禁发命令
- [ ] **配置篡改探针**：ceo_agent.yaml 全文复制 tmp 仅改 allowed_tools（5-4 AC-2.3 先例——最小 yaml 过不了 loader 逐段强校验）；篡改前基线锚断言（loader 读回白名单恰为收窄集）
- [ ] **计时场景**：新 `xdist_group("agent-triple-isolation-perf")` 串行 + benchmark 场景级标记；`TRIPLE_ISOLATION_P95_LIMIT_SECONDS = 0.05` 常量单源（验收/集成共享 import）
- [ ] **并发探针**：keys 即时登记（gather 部分失败时已完成 agent 双键仍清理——5-4 R1-F13 模式）；探针目标等级互异（奇 L4 偶 L3——矩阵判定并发不串扰）
- [ ] BDD 步骤禁 `@pytest.mark.asyncio`；步骤函数同步 def + `_run_async` 调度
- [ ] 安全套件计时面与 5-4 计时组（agent-isolation-perf）xdist_group 名不同不冲突（loadgroup 各自串行）

**验证要求：** `pytest tests/ -n 8` 通过；连续 5 次无随机失败；ruff/mypy 通过；`make test-security`（或等价命令）通过。

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 判定矩阵全格（MVP 三级 + L1 前向） | Task 1 | decide_isolation_access 纯函数 | test_isolation_access |
| AC-1 | 资源归属 + 工具判定 | Task 1 | IsolationResource 分类 + decide_tool_access | test_isolation_access |
| AC-2 | 入口 fail-closed（447/443） | Task 3 | RunAgentWorkflowUseCase 接线 | test_run_agent_workflow（追加）+ 验收 AC-2.2/2.3 |
| AC-2 | 放行返回策略 | Task 2 | ensure_agent_executable | test_isolation_guard_service + 验收 AC-2.1 |
| AC-3 | Prompt/数据面 448 | Task 2 | ensure_agent_access | test_isolation_guard_service + 验收 AC-3.1/3.2 |
| AC-3 | 共享面矩阵（449/放行） | Task 1/2 | data_isolation 分支 + ensure_agent_access | test_isolation_access + 验收 AC-3.3 |
| AC-3 | 工具白名单 449/放行 | Task 1/2 | decide_tool_access + ensure_tool_access | test_isolation_access + 验收 AC-3.4 |
| AC-3 | 自身资源放行 | Task 1 | cross_agent=False 分支 | test_isolation_access + 验收 AC-3.5 |
| AC-4 | 20 探针矩阵 100% 拦截 | Task 4 | tests/security 套件 | test_isolation_security + 验收 AC-4×2 |
| AC-4 | 白名单判别力（窄配置） | Task 1/4 | 配置篡改 + T-04 真实名 | test_yaml_agent_config_loader（追加）+ 安全套件 |
| AC-5 | P95<50ms | Task 5 | 委托计时 helper | test_integration_agent_triple_isolation + 验收 AC-5.1 |
| AC-5 | 通过率 100% | Task 5 | 20 采样分子分母 | test_integration_agent_triple_isolation + 验收 AC-5.2 |
| AC-5 | 并发 10×50 零泄露 | Task 5 | gather 并发探针 | test_integration_agent_triple_isolation + 验收 AC-5.3 |
| AC-6 | 组合根接线 + resolve | Task 2 | PortSpec 注册 | 契约测试 + 验收 AC-6.1 |
| AC-6 | 两接线点端到端锚 | Task 3 | lambda 注入 + 行为锚 | test_run_agent_workflow/test_agent_workflow_service + 验收 AC-6.2 |
| AC-6 | 架构合规 | Task 6 | 验证器 A-D | test_arch_agent_triple_isolation + 验收 AC-6.3 |
| AC-6 | 安全测试基建四件套 | Task 4 | 目录/marker/CI/覆盖率 | 文件存在性断言 + 验收 AC-6.4 |
| 全 AC | 收尾清单 | Task 7 | 完成清单场景 | 验收收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ TDD 循环内化原则同模板。每 Subtask 组内按领域粒度拆分红绿循环。

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部

- [ ] Subtask 0.1: 定义数据模型规范——IsolationResource（11 成员两归属）/ AccessOperation / IsolationViolationKind / IsolationAccessDecision / decide_isolation_access 矩阵三步 / decide_tool_access / resource_is_private / AgentConfig.allowed_tools（本文件「数据模型」节为唯一真源）
- [ ] Subtask 0.2: 定义端口契约——IsolationGuardPort 三方法 + IsolationGuardService 三依赖 + 组合根注册元数据 + 两接线点签名扩展（契约变更登记）
- [ ] Subtask 0.3: 定义异常契约——448/449（code/parent/context 字段/HTTP 403/双触发场景表 + 448-449 分界原则）
- [ ] Subtask 0.4: 定义 20 条探针矩阵定稿表 + 放行对照清单（本文件「探针矩阵」节——安全审计资产）
- [ ] Subtask 0.5: 定义安全测试基建契约——tests/security 四件套 + marker 注册 + CI 挂载 + 覆盖率专项口径
- [ ] Subtask 0.6: 编写 Gherkin `test_acceptance_agent_triple_isolation.feature`（19 场景——收尾场景按模板归 Task 7 追加）+ BDD 步骤实现骨架 `.py`（@scenario 全显式绑定 + context dict fixture + 双键清理）+ **19 场景三属性分档表**定稿（docstring）
- [ ] Subtask 0.7: 运行验收测试确认失败（🔴 红阶段——ModuleNotFoundError/断言红为合法红）
- [ ] Subtask 0.8: 移交三项处置落盘（DC-12——5-4 风险 #6 核销登记/#7 维持/R1-DF2 维持，deferred-work.md 原条目更新）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义；验收测试红阶段确认；链路接线断言清单 L1-L5 定义

---

### Task 1: 领域层——isolation_access 判定核心 / 异常 448/449 / AgentConfig.allowed_tools

**关联 AC:** AC-1（全部）、AC-3（矩阵格）、AC-4（白名单判别力基础）

#### TDD 循环 A：IsolationResource + 判定矩阵纯函数

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_isolation_access.py`（IsolationResource 恰 11 成员 + 值形态断言/resource_is_private 11 项逐成员断言[9 True + 2 False]/AccessOperation 两值/IsolationViolationKind 两值/矩阵全格参数化：MVP 三级[L4/L3/L2] × {PROFILE,AGENT_STATE,BLACKBOARD} × {READ,WRITE} × {cross,self} 逐格——private+cross 全拒 ACCESS_VIOLATION、private+self 放行、shared+READ 放行、shared+WRITE 按 data_isolation[L4 拒/L3 拒/L2 放行]/L1 前向格：private+cross 放行 + shared+WRITE 放行[FULL_SHARED]/decide_tool_access：L4 白名单内放行 + 白名单外拒 OPERATION_FORBIDDEN + L3/L2 放行[tool_isolation=False 共享池]/IsolationAccessDecision 不变量：allowed=True 带 violation → 242、allowed=False 无 violation → 242/矩阵从策略表派生锚：monkeypatch ISOLATION_POLICIES 某 L4 维度翻转（tool_isolation→False）→ 对应判定随动[禁等级硬编证据]) |
| 🟢 绿 | 实现 `src/domain/value_objects/isolation_access.py`（枚举×3 + frozen dataclass + 两纯函数 + helper——注意跨模块 import isolation_policy/events.enums 属 domain 同层合法；**若触发包初始化环**照抄 isolation_state.py 的方法内延迟 import 破环先例）+ `src/domain/value_objects/__init__.py` 导出 |
| 🟡 变异 | 矩阵 private+cross 分支改放行 → 探针 448 用例红 → 还原；shared WRITE 的 FREE_WRITE 格改拒 → L2 放行用例红 → 还原 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 B：异常 448/449

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/domain/exceptions/test_agent_exceptions.py` 追加（448：code/继承 BusinessException/context 四字段/构造首参必填[缺 actor_agent_id → TypeError]；449：code/context 三字段/reason 双形态[tool_not_in_allowlist/data_isolation]/参数化双触发路径）+ `test_exception_handlers.py` 追加 448→403、449→403 精确注册断言 + expected_types 清单同步 |
| 🟢 绿 | `agent_exceptions.py` 追加两类（构造器对齐 446/447 形态）+ `_code_ranges.py` 预留改已分配 + 双映射 + `__init__.py` 暴露 + `EXCEPTION_HTTP_MAP` 两行 + 设计文档 §3.3.2 两行 |
| 🟡 变异 | 码值突变 → 唯一性测试红 → 还原 |
| 🔄 重构 | 全套异常测试绿（test_code_ranges Rule 4 自动覆盖新类登记） |

#### TDD 循环 C：AgentConfig.allowed_tools + loader 解析

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/domain/value_objects/test_agent_config.py` 追加（默认空元组/合法清单构造/元素非 str → 440/空白串元素 → 440/tuple 形态断言）+ `tests/unit/infrastructure/agent_orch/test_yaml_agent_config_loader.py` 追加（eip_config.allowed_tools 缺失 → 空元组/合法清单解析 + 去重保序/非 list 类型 → 440/元素空白 → 440/ceo_agent.yaml 真实加载白名单非空且 ⊆ TOOL_CATALOG 名集——**基线锚，防白名单配置漂移到不存在的工具名**） |
| 🟢 绿 | 修改 `src/domain/value_objects/agent_config.py`（字段 + `__post_init__` 守卫——440 分码）+ `src/infrastructure/agent_orch/yaml_agent_config_loader.py`（eip_config.allowed_tools 解析——缺失回落空、去重保序、类型守卫 440）+ `configs/agents/ceo_agent.yaml`（eip_config 追加 allowed_tools 显式清单 = TOOL_CATALOG ACTIVE 全集——dev 从 strategic_tool_catalog.py 逐名提取） |
| 🟡 变异 | loader 守卫删除 → 非 list 用例红（裸 AttributeError/TypeError 逃逸）→ 还原；白名单 yaml 某名写错 → 基线锚用例红 → 还原 |
| 🔄 重构 | 既有 AgentConfig/loader 测试全绿（默认空元组不破坏既有构造——向后兼容确认） |

- [ ] Subtask 1.1-1.3: 三循环各红绿变异重构
- [ ] Subtask 1.4: 领域层覆盖率 ≥90% 维持确认

**完成标准/Definition of Done:** 判定核心/异常/白名单配置全绿；domain ≥90%；ceo_agent.yaml 白名单基线锚生效

---

### Task 2: IsolationGuardService 守卫服务 + 契约测试 + 组合根注册

**关联 AC:** AC-2（放行返回策略）、AC-3（三方法）

#### TDD 循环 A：守卫服务实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_isolation_guard_service.py`（`AsyncMock(spec=IsolationManagementServicePort)` + `AsyncMock(spec=AgentRepository)` + `AsyncMock(spec=AgentConfigLoader)` 三替身 + stub config 携带 allowed_tools——单测 Mock 端口合规。ensure_agent_executable：get_isolation_state 返回 L4 state → 返回策略断言[三维度]且恰一次调用/443 透传[get 抛 443 → 原样向上]/447 透传。ensure_agent_access：cross（actor≠target）+ private 资源 → 448 且 context 四字段/cross + shared READ → 放行静默/cross + shared WRITE + L4 → 449/data_isolation:read_only/self（actor==target）+ private → 放行/actor 状态获取经 isolation_management_service 恰一次[禁直查仓储——calls 断言]/448 抛出前决策函数消费断言。ensure_tool_access：L4 + 白名单内 → 放行且 config_loader.load(role) 恰一次/L4 + 白名单外 → 449 context {agent_id, operation, reason 含工具名}/L3[tool_isolation=False] → 放行且 config_loader 零调用[短路优化断言——共享池不查白名单]/443/447 透传/agent_repository.get_by_id 取 role 链路断言[None → 443 由 isolation_management 先拦——顺序断言：isolation_management 先于 agent_repository]) |
| 🟢 绿 | 实现 `src/application/ports/isolation_guard.py`（Protocol 三方法 + docstring 异常契约）+ `src/application/services/isolation_guard_service.py`（三依赖构造 + 三方法——异常构造传 context 完整、reason 按 DC-4 形态、443/447 零改写透传） |
| 🟡 变异 | cross_agent 判定翻转（== 改 !=）→ 448 用例红 → 还原；448/449 分码互换 → 探针分码断言红 → 还原 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 B：端口契约测试 + 组合根注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/contracts/test_port_contract_isolation_guard.py`（11 维度——DummyResolver 提供 isolation_management_service/agent_repository/agent_config_loader 三依赖） |
| 🟢 绿 | 组合根注册 `isolation_guard_service`（PortSpec 全参数 + lambda 三依赖 + 区段注释） |
| 🟡 变异 | impl 路径突变 → resolve 失败红 → 还原；lifetime 突变 → 契约维度红 → 还原 |
| 🔄 重构 | 契约 11 项绿 |

- [ ] Subtask 2.1-2.2: 两循环红绿变异重构

**完成标准/Definition of Done:** 三方法全绿（守卫序/矩阵消费/白名单真源/分码）；契约绿；application ≥85%

---

### Task 3: 双接线点改造 + 回归面全量同步

**关联 AC:** AC-2（fail-closed）、AC-6（接线端到端锚）

#### TDD 循环 A：RunAgentWorkflowUseCase 第五依赖 + 入口 fail-closed

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/application/use_cases/test_run_agent_workflow.py` 追加 + 存量同步（构造签名五依赖——存量用例构造处补 `AsyncMock(spec=IsolationGuardPort)`）。新断言：放行路径 ensure_agent_executable 恰一次且先于 profile_use_case[顺序断言]/guard 抛 447 → execute 向上抛且 profile_use_case/agent_engine 零调用[fail-closed]/guard 抛 443 → 透传/既有 443/441 守卫零回归[441 仍先于 guard——角色守卫在前的既有序保持]） |
| 🟢 绿 | 修改 `src/application/use_cases/run_agent_workflow.py`（第五依赖 + 编排骨位：443 守卫 → 441 守卫 → guard.ensure_agent_executable → 档案加载）+ 组合根 lambda 注入改造 |
| 🟡 变异 | 接线调用删除 → 恰一次断言红 → 还原；接线移到档案后 → 顺序断言红 → 还原 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 B：AgentWorkflowService 第五依赖 + 工具位拦截

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/application/services/test_agent_workflow_service.py`（或仓库实际文件）追加 + 存量同步（五依赖——补 AsyncMock guard）。新断言：plan 步骤含工具名 → ensure_tool_access 恰一次且参数 tool_name 逐名[多步骤多调用]/白名单外 → 449 向上抛且 get_tool 零调用[拦截先于存在性——判别锚]/无工具名步骤[直接推理] → guard 零调用/agent_id 从 state 取且 UUID 转换[str→UUID]断言） |
| 🟢 绿 | 修改 `src/application/services/agent_workflow_service.py`（第五依赖 + execute 工具位拦截——`uuid.UUID(state["agent_id"])` 转换在 try 外先取，449 先于 get_tool）+ 组合根 lambda 注入改造 |
| 🟡 变异 | 拦截移到 get_tool 后 → 「先于存在性」断言红 → 还原；拦截删除 → 恰一次断言红 → 还原 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 C：回归面全量同步 + 契约回归

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 既有契约测试 impl 维度同步（两用例/服务的契约测试构造签名——若有） |
| 🟢 绿 | **回归面清单全量同步**（适配器契约变更回归规则——`RunAgentWorkflowUseCase(` + `AgentWorkflowService(` 全仓 grep 构造点，逐一补第五依赖）：①组合根 lambda ×2；②5-3 验收 test_acceptance_agent_workflow.py 手动组装点——**真实 IsolationGuardService 手动组装**（三依赖真实链 + agent_config_loader 经 resolve——验收禁 mock 硬约束，5-4 R3-F04 改判先例同款）；③5-3 集成 test_integration_agent_workflow.py `_instantiate_agent`/组装 fixture——**AsyncMock(spec=IsolationGuardPort)**（集成 Mock 工厂子模式合规——guard 方法放行语义默认：ensure_agent_executable 返回 ISOLATION_POLICIES[L4_HARD]、ensure_tool_access 返回 None）；④单测存量构造点（test_run_agent_workflow/test_agent_workflow_service 及其它 grep 命中）——AsyncMock 同款；⑤验收/集成既有 InstantiateAgentUseCase 构造点**零改动**（本 Story 不改实例化用例签名）。**精确清单 dev 实施时以 grep 输出为准逐一登记**（5-4 Task 4 模式——7 处+先例；禁凭记忆漏点） |
| 🟡 变异 | lambda 漏注入 isolation_guard → resolve 构造失败红 → 还原 |
| 🔄 重构 | **回归面全量跑**（5-3 验收/集成存量测试全绿 + 组合根冒烟） |

- [ ] Subtask 3.1-3.3: 三循环红绿变异重构
- [ ] Subtask 3.4: 回归面清单全绿确认（含 5-3 全量存量）

**完成标准/Definition of Done:** 双接线完整；fail-closed 端到端可达；回归面全绿

---

### Task 4: 安全测试基建 + 20 探针矩阵套件

**关联 AC:** AC-4（全部）、AC-6.4（基建四件套）

#### TDD 循环 A：基建四件套

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写基建断言用例（文件存在性：`tests/security/__init__.py` + `conftest.py` + `test_isolation_security.py` 存在且可收集/pyproject markers 含 "security"[文本断言防漏注册——`--strict-markers` 收集期守卫]/ci.yaml integration job pytest 命令含 tests/security[文本断言]/Makefile 含 test-security target）——本循环用例先行钉死基建预期形态 |
| 🟢 绿 | 创建 `tests/security/__init__.py`（空）+ `tests/security/conftest.py`（场景级 Redis 客户端 fixture——tests/environments.py get_test_env() 取连接信息 + ping 门控 pytest.skip；对齐验收 context fixture 同循环纪律）+ pyproject markers 追加 + ci.yaml integration job 命令扩展 + Makefile target |
| 🟡 变异 | marker 行删除 → 收集期炸（红）→ 还原；CI 命令回缩 → 文本断言红 → 还原 |
| 🔄 重构 | ruff + mypy |

#### TDD 循环 B：20 探针矩阵套件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/security/test_isolation_security.py`（pytestmark = [security, redis, integration]；docstring 内嵌 20 条探针矩阵表[安全审计资产]；`_assemble_guard_chain()` 手动组装 helper——真实 RedisAgentRepository + RedisIsolationRepository + IsolationManagementService + IsolationGuardService + InstantiateAgentUseCase 全真实链 + `_RecordingEventPublisher`；A/B 构造 fixture[双 agent instantiate + `_agent_ids` 登记 + teardown 双键删除 + exists 复核]；**20 条探针 = 20 个独立参数化用例**[pytest.param(id="P-01")...——逐条断言异常类型 + code + context 关键字段]；窄白名单构造[T-01/T-04]：ceo_agent.yaml 复制 tmp 收窄 allowed_tools + `YamlAgentConfigLoader(config_dir=tmp_path)` 构造注入 + 基线锚断言；D-09 前置：A 切 L3[服务级 switch 真实调用]；拦截率汇总断言[20 用例全绿即 20/20——分子分母以模块级收集计数呈现]） |
| 🟢 绿 | 全 20 探针转绿（被测链已由 Task 1-3 交付——验证型转绿；红阶段若因链路缺陷失败则回修上游） |
| 🟡 变异 | 矩阵某探针预期码改错（448→449）→ 对应用例红 → 还原[探针断言活性证明]；guard cross 判定翻转 → 15 条 448 探针集体红 → 还原[矩阵判别力实证] |
| 🔄 重构 | 探针用例命名收敛（id 即矩阵编号——审计可对照）+ 安全覆盖率专项跑通（`pytest tests/security --cov=... --cov-fail-under=90` ≥90 达标） |

- [ ] Subtask 4.1-4.2: 两循环红绿变异重构
- [ ] Subtask 4.3: 安全覆盖率专项 ≥90% 确认

**完成标准/Definition of Done:** 四件套就绪；20 探针 20/20 拦截；安全覆盖率 ≥90%

---

### Task 5: 集成测试 + 性能验收

**关联 AC:** AC-5（+ AC-2/AC-3 真实 Redis 全链）

#### TDD 循环 A：全链集成 + 性能三指标

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_agent_triple_isolation.py`（真实 Redis 6380 门控 ping 失败 skip + 手动组装全链[guard 链四件 + 窄白名单 loader 通道] + `pytestmark = [integration, redis, benchmark, xdist_group("agent-triple-isolation-perf")]`。场景①守卫矩阵真实链抽查：A/B 构造 → ensure_agent_access 三面 6 断言[448×4 + 449×1 + 放行×1] + ensure_tool_access 三路[449/放行/L3 放行] + 双键 teardown。场景②P95：ensure_agent_executable 全链计时 warmup 1 + 20 采样 `quantiles(n=20)[18] < TRIPLE_ISOLATION_P95_LIMIT_SECONDS(0.05)`（perf_counter；计时含 443 守卫 + 隔离态读 + 策略联查全链；**交付形态**：模块级 `_TRIPLE_PERF_CACHE` 单槽缓存 helper——验收 AC-5.1/5.2 委托共享，同 xdist_group 同 worker 缓存命中，5-4 `_PERF_CACHE` 先例；helper 内 sample_keys 双键登记即时清理）。场景③通过率：helper 每轮 initialize + ensure 全放行即采样分子——20 轮 20/20 显式断言。场景④并发 10×50：10 agent `asyncio.gather` 并发构造 + 每 agent 对固定探针目标集[奇数目标 L4/偶数 L3——等级互异]发 50 跨 Agent 探针 → 全部 448/449 断言 + 拦截率 500/500 + keys 即时登记 + finally 批量双键删除 + exists 复核。场景⑤入口 fail-closed 真实链：真实 RunAgentWorkflowUseCase[guard 真实]→ 正常 instantiate 的 agent execute 放行锚[LLM 面以 AsyncMock llm_client 隔离——集成 Mock 工厂子模式，或按 5-3 集成既有形态] → 删隔离键 → execute 抛 447。场景⑥execute 白名单 449 真实拒：真实 AgentWorkflowService[guard 真实 + 窄白名单 loader] + 构造 state{agent_id, context, plan[白名单外工具步骤]} → execute 抛 449 且注册表零调用) |
| 🟢 绿 | 全场景转绿（验证型——被测链已交付） |
| 🟡 变异 | P95 阈值突变（0.05→0.0001）→ 红 → 还原；并发探针断言弱化为聚合 → 个体判别力验算[两 agent 不同等级探针互异断言] → 还原 |
| 🔄 重构 | xdist_group + benchmark 标记收敛；委托 helper 文档化（验收侧 import 姿态） |

- [ ] Subtask 5.1: 🔴 红 — 六场景编写
- [ ] Subtask 5.2: 🟢 绿 — 转绿 + 计时校准
- [ ] Subtask 5.3: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:** 集成 6 场景绿；性能三指标断言活；委托 helper 可共享

---

### Task 6: SDD 架构约束验证测试

**关联 AC:** AC-6.3

#### 架构验证测试实现（验证器 A-D）

- [ ] Subtask 6.1: 创建 `tests/unit/architecture/test_arch_agent_triple_isolation.py`（REPO_ROOT 四层 parent 锚定——5-4 同款）
- [ ] Subtask 6.2: 验证器 A——domain 零外部依赖（isolation_access.py/agent_exceptions.py AST 扫描禁 pydantic/redis import）
- [ ] Subtask 6.3: 验证器 B——组合根外零实例化（IsolationGuardService 全仓 AST 扫描禁业务代码直接实例化；tests 白名单前缀）
- [ ] Subtask 6.4: 验证器 C——端口方向（isolation_guard_service.py 与两接线点 import 白名单：domain.*/application.ports 合法 / src.infrastructure 非法；**接线静态锚**：run_agent_workflow.py 与 agent_workflow_service.py 均含 isolation_guard 引用[AST 属性扫描——lambda 漏注入的架构面防线，验收 AC-6.2 行为锚的静态互补]）
- [ ] Subtask 6.5: 验证器 D——lifetime 决策落地（`_global_registry.get("isolation_guard_service")` 两行式收窄断言 SINGLETON——mypy Optional 纪律，5-4 R1-F29 先例）
- [ ] Subtask 6.6: 循环依赖检测用 ruff/isort（不引入 pylint）+ 全套报告

**完成标准/Definition of Done:** 验证器 A-D 全绿；违规即红

---

### Task 7: 开发结束验收测试

**关联 AC:** 全部

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 验收 feature 追加收尾场景（src 完成清单/tests 四目录 + tests/security 完成清单逐项确认——AC-6.4 形态） |
| 🟢 绿 | BDD 步骤实现（文件存在性 + 关键符号 grep/AST 断言——5-4 AC-6.3 同款） |
| 🔄 重构 | 场景命名收敛 |

- [ ] Subtask 7.1: 收尾场景红绿（全量 20 场景）
- [ ] Subtask 7.2: 全量回归（`pytest tests/ -n 8` + 连续 5 次稳定）+ ruff/mypy 收尾校验 + 三条红线自查 + 安全覆盖率专项复跑
- [ ] Subtask 7.3: 文档同步（architecture.md §5 注记更新[三重隔离运行时强制拦截已交付——Story 5.5] + §13 目录树 isolation_access/isolation_guard 落位 + sisys-uni-exception-design.md §3.3.2 已随 Task 1 同步复验 + deferred-work.md 三处置终态更新）+ 留项终态核对

**完成标准/Definition of Done:**
- [ ] 全量 20 场景（19 + 收尾 1）全绿；Story 可进入 review

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md) §5（L643-666）、§13（L1733-1772 目录树）、§4.4（L419-424 EIP 流程 39-43）；[`sisys-core-domain-design.md`](../../../docs/architecture/sisys-core-domain-design.md) §17.3.3（L1192-1266）；or.md L23/L256/L357/L578/L605/L616-620。

- **架构模式：** 六边形（Ports & Adapters）；三重隔离执行面 = **PDP/PEP 分离**——判定核心（domain 纯函数矩阵 = Policy Decision Point，零 IO 可穷举测试）+ 守卫服务（application = Policy Enforcement Point，IO 编排[状态获取/配置加载] + 异常抛出）+ 接线点（两用例/服务 = Enforcement 挂载位）——严格 R1（domain 统一抽象：isolation_access 纯判定 + 448/449 异常 + AgentConfig 白名单 VO）/ R2（application IsolationGuardPort 组合注入 isolation_management_service[应用] + agent_repository[domain R1] + agent_config_loader[应用]）/ R3（本 Story 零新基础设施实现——判定面无新技术依赖；探针基建是测试资产非生产 infra）/ R4（零接口层改动——守卫是内嵌执行面，探针是测试面）
- **设计约束：** domain 零外部依赖（AST 门禁）；判定矩阵唯一真源 = decide_isolation_access（禁在 guard/测试/接线点重写矩阵逻辑）；策略语义唯一真源 = ISOLATION_POLICIES（矩阵从策略字段派生，零等级硬编码）
- **接口治理：** 新端口一枚走 PortSpec 全套；既有端口消费方变更两项（两接线点构造签名扩展——契约变更登记 + 回归面全量同步）
- **技术栈：** Python 3.11+ 标准库（dataclasses/Enum/uuid——domain 判定核心）；redis-py asyncio（探针/性能真实链）；pytest 参数化探针矩阵

### 关键架构决策

| # | 决策点 | 选定方案 | 备选方案（弃用理由） | 依据 |
|---|--------|---------|---------------------|------|
| DC-1 | 执行面架构形态 | **domain 纯判定函数 + application 守卫服务（PDP/PEP 分离）**：`decide_isolation_access`/`decide_tool_access` 纯函数承载矩阵（零 IO——全格穷举单测，L1 前向格可锁定）；`IsolationGuardService` 承载 IO 编排（状态经 isolation_management_service[443/447 复用] + 白名单经 agent_config_loader）；异常抛出在守卫（决策对象→异常的翻译单点） | a) 矩阵逻辑写入守卫服务（弃用：判定与 IO 耦合——L1 前向格/矩阵派生锚无法零 IO 穷举测试）；b) 矩阵做成领域服务类（弃用：纯函数足够——DC-2[5-4] 常量表同款 Simplicity）；c) 拦截内嵌各资源 API（仓储/黑板/引擎逐点改造——弃用：改 5-1~5-3 资产回归面巨大且授权检查错位[仓储是应用内部设施非授权点]——六边形授权语义在应用层入口） | PDP/PEP 分离惯例；矩阵可穷举性；surgical changes |
| DC-2 | 三面判定语义矩阵 | **资源归属二分[private×9/shared×2] × 操作[READ/WRITE] × 跨主体[cross/self] 三轴矩阵**：private+cross → 448（L4/L3/L2 全拒——「独立」贯穿三级）；private+self → 放行；shared+READ → 放行（全等级）；shared+WRITE → 按 data_isolation（L4 READ_ONLY→449 / L3 RESTRICTED_WRITE→449[MVP 拒，D-4] / L2 FREE_WRITE→放行）；工具独立轴：tool_isolation=True→白名单 else 449。**epics「A 无法读取 B 的数据」语义 = private 面**；§5.1「L4 数据只读」语义 = shared 面写约束——两语义轴正交统一进矩阵 | a) 资源逐一定义许可表（弃用：11 资源×4 等级×2 操作×2 主体=176 格显式表——维护灾难；三轴派生仅 ~10 条规则）；b) shared 面写全等级放行（弃用：READ_ONLY 策略维度无消费方——策略表沦为声明摆设违本 Story 使命）；c) private 面按等级差异化（L2 允许跨 Agent 读 private——弃用：违反 AC「A 无法读取 B 数据」字面且 L2 语义是共享面自由写非私有面开放） | architecture §5.1 三维度表；epics AC 探针语义；5-4 策略表三维度 |
| DC-3 | 端口形态 | **单端口 `IsolationGuardPort` 三方法**（ensure_agent_executable/ensure_agent_access/ensure_tool_access——ensure_* 断言型[deny 即抛]，无 check_*/decision 双方法[check 返回决策+ensure 抛异常的双套 API 冗余——YAGNI；放行场景以「不抛」断言]）+ 三依赖组合（isolation_management_service + agent_repository + agent_config_loader） | a) check + ensure 双方法六件套（弃用：API 面翻倍，MVP 无「查询判定结果不执行」消费方）；b) 三端口分立（弃用：三方法同关注点[隔离守卫]同依赖集——类蔓延）；c) 守卫塞进 IsolationManagementService（弃用：管理[切换/查询]与守卫[拦截]两关注点混一端口——违单一职责） | 5-4 DC-4 单端口先例；ensure 命名惯例 |
| DC-4 | 异常 448/449 | **448 IsolationAccessViolationError（跨主体越权——actor≠target 私有资源，403）+ 449 IsolationOperationForbiddenError（单主体操作被自身等级禁止——白名单外工具/READ_ONLY·RESTRICTED_WRITE 写，403）**：两轴正交分码——探针矩阵 448×15/449×5 各归其位；context 携带判定位（448 四字段 actor/target/resource/operation；449 三字段 agent_id/operation/reason[reason 编码触发细分：tool_not_in_allowlist:{name} / data_isolation:{mode}]——同码多因 context 区分锚，5-4 446 双路径先例） | a) 单异常 448 全包（弃用：跨主体 vs 单主体语义混杂——监控/审计维度不可分；449 码位空置浪费预留段）；b) 449 用 446 IsolationLevelNotSupportedError（弃用：446 是「等级值不合法」输入校验族，非「操作被等级禁止」运行时拦截族——语义错位）；c) HTTP 401/422（弃用：403 Forbidden 是越权标准码；鉴权未失败非 401；请求格式无错非 422） | _code_ranges L127 预留；403 权限族惯例；441→422/443→404 精确注册先例 |
| DC-5 | 工具白名单真源 | **AgentConfig.allowed_tools（eip_config.allowed_tools per-role yaml 配置）**：配置资产随角色（or.md L23 技能列表是角色属性）；默认空元组（fail-closed——忘配即全拒，集成测试红即暴露）；ceo_agent.yaml 初值 = TOOL_CATALOG ACTIVE 全集（5-3 主链零回归）；探针判别力经配置篡改（tmp 收窄——5-4 AC-2.3 先例）；loader 缺失回落空 + 去重保序 + 类型守卫 440 | a) Agent 实体加 tools 字段（弃用：改 5-1 实体+序列化——回归面大且白名单是部署配置非实例状态）；b) 域常量表 per-role 工具映射（弃用：硬编码配置语义——增删工具要改代码；yaml 是既有角色配置通道先例）；c) TOOLS.md 档案承载（弃用：档案是 Prompt 注入文本资产，结构化配置语义错位） | AgentConfig eip_config 先例；fail-closed 安全默认；配置篡改测试先例 |
| DC-6 | 入口接线序与 fail-closed | **RunAgentWorkflowUseCase 编排骨位：443 存在 → 441 角色 → guard.ensure_agent_executable → 档案加载 → 装配 → 图执行**：guard 在角色守卫后（441 是既有序——非 CEO 角色的档案目录不存在先 441 才可达，guard 依赖隔离态与角色无关但保持既有序零回归）、档案加载前（档案 = Prompt 面资产——fail-closed 于最早可判定点，447 时零档案读取零图执行零事件）。**fail-closed 语义兑现 5-4 端口 docstring 预留的「执行前强制检查消费面」** | a) guard 放最前（443 前——弃用：447 依赖 agent 存在语义，443 先行是 get_isolation_state 内部守卫序一致）；b) guard 放图执行前最后（弃用：档案/装配已执行——LLM 配额/资产访问已发生，fail-closed 名存实亡）；c) 惰性检查图节点内（弃用：LangGraph 节点内异常处理复杂化重试语义；入口单点拦截更清晰） | run_agent_workflow.py L93-119 既有编排骨位；isolation_management.py L82 docstring 预留 |
| DC-7 | 工具位接线 + L1 视图边界 | **AgentWorkflowService.execute 工具位硬拦截**（get_tool 前 ensure_tool_access——449 先于工具存在性[白名单外名不炸 ToolNotFound 而炸 449，判别锚]）+ **TOOLS L1 视图按白名单过滤归 V1**（plan 阶段可见性是软优化——L1 视图来自 SkillSelector 全局 ACTIVE[5-2 资产]，过滤需 per-role 白名单注入档案链[改动 LoadAgentProfileUseCase + SkillSelector 两 5-2 资产]；执行位硬拦截已闭环 P0 验收——即使 LLM 选了白名单外工具也 449 硬拒；L1 过滤提升效率与提示一致性，V1 与 5-2 演进联动） | a) L1 视图过滤一并做（弃用：改 5-2 档案链两资产——surgical 越界且 P0 验收不依赖；登记 V1 联动）；b) 仅 L1 过滤无执行位拦截（弃用：视图过滤可被 LLM 输出绕过——无硬防线）；c) 拦截放 ToolExecutionService（弃用：ExecutionContext 无 agent_id 字段——身份不可得需改 Epic 4 VO；且工具执行服务是通用通道[辩论/工具链也走]非 Agent 专用位——AgentWorkflowService 是 Agent 链工具唯一调用编排位） | agent_workflow_service.py L224-246 工具位；skill 链 5-2 资产边界 |
| DC-8 | 安全测试基建 | **tests/security 新目录四件套**（目录+conftest / pyproject security marker / CI integration job 挂载 / 安全覆盖率专项）：探针需真实 Redis → 挂有 compose 栈的 integration job（unit job 无栈全 skip = 假绿幻觉）；marker 必注册（--strict-markers 收集期守卫）；覆盖率口径 = 专项命令对执行面模块集 fail-under 90（epics 字面实例化——D-2 偏离声明）；Makefile test-security 本地等价通道 | a) 探针并入 tests/integration（弃用：epics 明确要求 tests/security/test_isolation_security.py 独立文件[epics L1669 命名保真]；安全套件独立成目录是可审计资产边界）；b) 挂 security-scan job（弃用：该 job 是纯静态扫描无服务栈——探针全 skip）；c) 安全覆盖率并入四层门禁（弃用：check_coverage_gates 是全量跑口径，安全专项是 tests/security 单独跑的覆盖贡献——分母口径不同不可合并；并存不替代） | epics L1666-1669；pyproject L286 strict-markers；ci.yaml L290-397 job 划分 |
| DC-9 | 性能口径 | **P95<50ms 计时锚 = ensure_agent_executable 服务全链**（443 存在性守卫 + 隔离态读[两次真实 Redis 读] + 策略联查——「隔离检查」即入口检查，与 AC-2 语义同锚；warmup 1 + 20 采样 quantiles[18] < 0.05；本地 Redis 两读 ~2ms 预算 25 倍裕量）；通过率 = 20 轮全放行分子分母显式；并发 = 10 agent × 50 探针 gather（拦截率 500/500 + 目标等级互异[奇 L4 偶 L3]）；委托模式沿 5-4（_TRIPLE_PERF_CACHE + 新 xdist_group 与 5-4 组不冲突） | a) P95 测纯 decide 纯函数（弃用：纳秒级纯函数无意义——口径必须含 IO 全链才是「隔离检查」成本）；b) 并发仅断言全成功（弃用：聚合断言对串扰不敏感——变异不可红，5-4 DC-11 同款论证）；c) 复用 5-4 计时组（弃用：xdist_group 同名会与 5-4 计时面互相串行拖慢——新组隔离） | epics L1653-1655；5-4 DC-11/委托先例 |
| DC-10 | 探针矩阵与验收分档 | **20 条探针 = 15×448 + 5×449 三面分布（P×6/T×4/D×10——Task 0 定稿表）实跑归 tests/security**（安全套件 = 独立可审计资产 + CI 独立挂载面）；**验收侧 AC-4×2 只断言资产完备性**（文件存在 + 20 用例计数 + 矩阵定义与故事一致——探针实跑不在验收重复[双跑拖慢]；验收 AC-3×5 场景覆盖守卫放行/拒绝代表性抽查——两层互补不重复）；T-04 强约束 TOOL_CATALOG 真实名（判别力——证明白名单判定独立于存在性） | a) 20 探针全放验收（弃用：验收+安全双跑 40 用例——拖慢且边界模糊；epics 把安全测试列为独立文件即意图独立资产）；b) 探针循环套表生成（弃用：弱断言[循环内 assert 失败定位差]——参数化独立用例 id 可对照矩阵审计）；c) 探针全 mock（弃用：安全测试 = 验收级真实服务纪律——mock 掉守卫依赖即 mock 掉被测面） | epics L1647-1670；R6 验收纪律；安全审计资产定位 |
| DC-11 | 深度加固边界（威胁模型） | **本 Story 防线 = 应用层强制拦截面（guard + 双接线）**；**登记不做的深度项**：黑板 API 属主过滤（PublicBlackboard.get 返回会话全部条目——V1 协作组 Story[黑板是 L2 协作资产，MVP 无消费链]）/ get_graph_result(run_id) 归属校验（持 run_id 可读终态 state——run_id 是不可枚举随机 UUID，越权前提是能力泄露非直接越权；引擎 _runs 1h TTL——V2 引擎加固）/ L0 记忆 agent 前缀 / ExecutionContext/沙箱 agent 身份贯通（沙箱容器名仅 tenant 维度——Epic 4 资产，Docker 沙箱本身已是纵深第二层）。**威胁模型声明**：本 Story 拦截「Agent 运行时经应用层通道的越权」；基础设施直读（redis-cli/DBA）与「持有不可枚举 id 的越权」不在 MVP 威胁模型内（分别归运维边界与 V1/V2 加固项） | a) 本 Story 一并加固黑板/引擎（弃用：三项全是既有 Story 资产深改[5-3/Epic4/V1 协作面]——surgical 越界且黑板/引擎的协作消费方尚未立项[改了无验收方]；登记移交）；b) 不登记裸放（弃用：已知限制必须台账化——否则 V1 协作组立项时无人知道防线缺口） | or.md L256 五层纵深[第一层隔离即本 Story，二~五层各有归属]；风险登记纪律 |
| DC-12 | 5-4 移交三项处置 | **#6 孤儿隔离键：核销**——入口 fail-closed（447 拒执行）已闭合危害面[Agent 键存活/隔离键缺失 → 拒执行 → TTL 自然回收]；自愈通道 5-4 已实现（initialize upsert）——无需新代码，核销登记。**#7 并发切换竞态：维持**——本 Story 探针全跨 Agent 面（键空间天然隔离），不涉同 Agent 并发切换；触发条件（多源并发）归 V1 动态触发立项。**R1-DF2 StorageError 语义：维持**——本 Story 零存储层改动，触发条件不变归存储异常码专项 | a) #7 本 Story 加 Agent 级锁（弃用：MVP 单用户 CLI 通道无并发切换源——为不存在的并发加锁违 YAGNI；5-4 风险 #7 已论证）；b) R1-DF2 顺手改（弃用：零存储改动面——无顺手位） | 5-4 风险 #6/#7/R1-DF2 台账 |

### 已知下游风险（本 Story 不处置，消费方 Story 决策）

1. **守卫覆盖面 = 应用层通道**：guard 是显式调用防线——新资源通道（未来的 Agent 间消息/SAP 消费）必须自觉经 guard（5.11 SAP 实现时的接线义务）。架构面无「强制全通道过 guard」的机制保证（Python 无 capability 系统）——依赖 code review + 架构测试静态锚（验证器 C 扩展新接线位时同步）。
2. **黑板/引擎/L0/沙箱四处深度缺口**（DC-11 登记不做的四项）：V1 协作组立项时黑板属主过滤是**前置义务**（L2 协作态真实消费黑板时，`PublicBlackboard.get` 全量返回与 FREE_WRITE 放行叠加 = 跨 Agent 输出可见——但那是 L2 语义[共享]非缺陷；需过滤的是「协作组外成员」维度——届时 guard 矩阵需扩 conversation 维度）；get_graph_result 归属校验归 V2 引擎加固。
3. **TOOLS L1 视图未过滤**（DC-7）：plan 阶段 LLM 可见全部 ACTIVE 工具——白名单外工具会被选中然后在执行位 449 拒（浪费一轮 plan token）。V1 做 L1 过滤时需同步 SkillSelector per-role 维度（5-2 资产演进）。
4. **L3 RESTRICTED_WRITE 语义 MVP 收窄为全拒**（D-4）：受限写白名单（写哪些共享资源可豁免）V1 定义——届时 decide 矩阵第 1 步需扩白名单参数（矩阵签名预留 Collection 参数位即可，无需重构）。
5. **探针矩阵静态性**：20 条是 MVP 威胁模型快照——IsolationResource 新增成员（V1 协作资源）时矩阵表与探针集须同步扩（矩阵派生自策略表的部分自动随动，探针是手工资产需人工扩——审计文档即 Task 0 定稿表，扩资源时先扩表）。
6. **安全覆盖率口径的窄分母**：专项 cov 分母仅两执行面模块（guard + access）——未来执行面扩模块（如黑板过滤器）须同步扩 cov 模块集，否则新模块逃逸在 90% 门禁外。

### 设计文档偏离声明

> 90-8 先例机制：实施与设计文档冲突时显式声明，实施后同步更新文档。

| # | 冲突点 | 偏离内容 | 实施后同步动作 |
|---|--------|---------|---------------|
| D-1 | epics L1666-1669 测试路径 `tests/unit/architecture/test_triple_isolation.py` / `tests/integration/test_triple_isolation_integration.py` | 按项目实际目录与命名惯例：架构验证 `test_arch_agent_triple_isolation.py`（test_arch_* 前缀 + agent 域家族命名）、集成 `test_integration_agent_triple_isolation.py`（集成无 "integration" 后缀惯例）；`tests/security/test_isolation_security.py` 按 epics 原名保真（新目录新文件）——5-4 D-4 同款 | 不修改 epics（历史规划文档）；dev 以本 Story 测试分类表为准 |
| D-2 | epics L1659「安全测试覆盖率≥90%」字面模糊（无口径） | 实例化为：`pytest tests/security --cov=src.application.services.isolation_guard_service --cov=src.domain.value_objects.isolation_access --cov-fail-under=90`（安全套件对执行面模块集的语句覆盖率）——与四层门禁并存 | Makefile test-security target + CI step 落地即口径文档化 |
| D-3 | or.md L617「Prompt 三重硬隔离」在角色级共享档案（configs/agents/profiles/{role}/）架构下的语义 | Prompt 隔离的 MVP 执行语义 = **实例级越权拦截**（actor≠target 的 PROFILE/SYSTEM_PROMPT/WORKFLOW_CONTEXT 访问 448）——同角色多实例共享静态档案文本是 5-1/5-2 既有架构（档案是 role 资产非实例资产），「隔离」防的是跨 Agent 实例的运行时上下文/输出越权非静态文本重数 | Task 7 在 architecture.md §5 注记「Prompt 隔离 MVP 语义 = 实例级越权拦截」 |
| D-4 | architecture §5.1 L3「受限写入」白名单未定义 | MVP 口径：RESTRICTED_WRITE 等级下 shared 面写一律 449 拒（受限写白名单归 V1——矩阵签名预留扩展位） | D-4 随 D-2 一并入 §5 注记 |
| D-5 | epics L1648「构造 20 条跨 Agent 数据访问探针」未列清单 | 本 Story Task 0 定稿 20 条矩阵表（P×6/T×4/D×10，15×448+5×449）——探针矩阵即安全审计资产 | 定稿表随 Story 归档即文档化 |

### 关键代码模式参考

**decide_isolation_access 判定核心骨架（domain/value_objects/isolation_access.py——三步矩阵，从策略字段派生零等级硬编码）：**

```python
def decide_isolation_access(
    policy: IsolationPolicy,
    *,
    cross_agent: bool,
    resource: IsolationResource,
    operation: AccessOperation,
) -> IsolationAccessDecision:
    """三重隔离判定矩阵（Prompt/数据面——纯函数零 IO，唯一真源）。

    矩阵三步（等级语义从 ISOLATION_POLICIES 策略字段派生，本函数零等级硬编码）：
    shared 面 → 读放行 / 写按 data_isolation；private 面 → 跨主体按 prompt_isolation / 自身放行。
    """
    if not resource_is_private(resource):
        if operation is AccessOperation.READ:
            return IsolationAccessDecision(allowed=True, violation=None, reason="共享面读开放")
        if policy.data_isolation is DataIsolationMode.FREE_WRITE or policy.data_isolation is DataIsolationMode.FULL_SHARED:
            return IsolationAccessDecision(allowed=True, violation=None, reason=f"共享面写允许（{policy.data_isolation.value}）")
        return IsolationAccessDecision(  # READ_ONLY / RESTRICTED_WRITE（MVP 拒——D-4）
            allowed=False, violation=IsolationViolationKind.OPERATION_FORBIDDEN,
            reason=f"data_isolation:{policy.data_isolation.value}",
        )
    if not cross_agent:
        return IsolationAccessDecision(allowed=True, violation=None, reason="自身资源访问")
    if policy.prompt_isolation:  # L4/L3/L2 全 True——「独立」贯穿三级
        return IsolationAccessDecision(
            allowed=False, violation=IsolationViolationKind.ACCESS_VIOLATION,
            reason=f"跨 Agent 私有资源访问被拒（{policy.name}）",
        )
    return IsolationAccessDecision(allowed=True, violation=None, reason="融合态前向语义（V2）")  # L1 FULL_SHARED 自洽
```

**IsolationGuardService.ensure_agent_access 骨架（application——IO 编排 + 异常翻译单点）：**

```python
async def ensure_agent_access(self, actor_agent_id, target_agent_id, resource, operation) -> None:
    """跨 Agent 资源访问守卫：拒绝时按判定 violation 抛 448/449（443/447 经状态入口透传）。"""
    state = await self._isolation_management.get_isolation_state(actor_agent_id)   # 443→447 守卫序复用（禁直查仓储）
    policy = get_isolation_policy(state.current_level)
    decision = decide_isolation_access(policy, cross_agent=(actor_agent_id != target_agent_id),
                                       resource=resource, operation=operation)
    if decision.allowed:
        return
    if decision.violation is IsolationViolationKind.ACCESS_VIOLATION:
        raise IsolationAccessViolationError(                                    # 448（跨主体越权）
            actor_agent_id=str(actor_agent_id), target_agent_id=str(target_agent_id),
            resource=resource.value, operation=operation.value)
    raise IsolationOperationForbiddenError(                                     # 449（等级策略禁止）
        agent_id=str(actor_agent_id), operation=operation.value, reason=decision.reason)
```

**AgentWorkflowService.execute 工具位拦截骨架（agent_workflow_service.py——449 先于工具存在性）：**

```python
for description, tool_name, arguments in plan.steps:
    if not tool_name:
        step_summaries.append(f"{description}（直接推理，无工具调用）")
        continue
    # Story 5-5 三重硬隔离：L4 白名单守卫先于注册表查询（白名单外名炸 449 而非 ToolNotFound——判别锚）
    agent_uuid = uuid.UUID(state["agent_id"])                                   # state 是 str 形态（schemas.py L67）
    await self._isolation_guard.ensure_tool_access(agent_uuid, tool_name)
    tool = self._tool_registry_service.get_tool(tool_name=tool_name)            # 既有链零改动
```

**探针参数化形态骨架（tests/security/test_isolation_security.py——20 条独立用例 id 可对照矩阵审计）：**

```python
@pytest.mark.parametrize(
    ("resource", "operation", "level", "expected_code"),
    [
        pytest.param(IsolationResource.PROFILE, AccessOperation.READ, None, "EXCEPTION_448", id="P-01"),
        pytest.param(IsolationResource.WORKFLOW_CONTEXT, AccessOperation.WRITE, None, "EXCEPTION_448", id="P-04"),
        pytest.param(IsolationResource.BLACKBOARD, AccessOperation.WRITE, None, "EXCEPTION_449", id="D-08"),
        pytest.param(IsolationResource.BLACKBOARD, AccessOperation.WRITE, IsolationLevel.L3_SOFT, "EXCEPTION_449", id="D-09"),
        # ... 20 条与 Task 0 定稿表逐条对应（id 即矩阵编号）
    ],
)
def test_probe_cross_agent_access(...):
    """单条穿透探针：断言异常类型 + code + context 关键字段（安全审计资产——矩阵见模块 docstring）。"""
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 5.4](./5-4-eip-basic-elastic-isolation.md)（文档审查 5 轮 + 代码审查 7 轮收敛的完整教训链——v2.3.1 收敛态）

**关键学习/Key Learnings:**
- **策略表是契约输入，执行面是其第一个消费方**——5-4 风险 #2「三重隔离策略无执行面」即本 Story 存在理由；矩阵必须从策略字段派生（派生锚测试防硬编码漂移）
- **str,Enum 混入语义**：`hash("L3")==hash(L3_SOFT)` 裸 str 穿透 `in frozenset` 判定——枚举入参守卫一律 `not isinstance(x, Enum) or ...` 双条件（5-4 R3-F01 实测定谳）
- **手动组装纪律**：resolve SCOPED/SINGLETON 钉住全局 Resolver → 跨循环死连接——验收/安全探针一律场景级客户端手动组装；resolve 仅接线断言
- **配置篡改驱动**：完整 yaml 基线复制 tmp + 仅改目标字段 + 构造注入 loader（5-4 AC-2.3/R3-F02——最小 yaml 过不了逐段强校验）
- **委托计时模式**：模块级单槽缓存 helper + 同名 xdist_group 同 worker 缓存命中——验收/集成共享采样禁双跑（5-4 R1-F23）
- **构造签名扩展 = 回归面苦役**：全仓 grep 构造点逐一登记补依赖（5-4 Task 4——8 处先例）；验收侧真实组装（禁 mock）、集成侧 AsyncMock 工厂合规的分层分派
- **BDD 参数化步骤须显式 `parsers.parse`**（pytest-bdd 默认 re parser——{level} 为字面量，5-4 实施期发现）
- **同码多因断言带 context 区分锚**（446 双触发先例——本 Story 449 双形态 reason）
- **变异实证判别力优先**：「先于存在性」「恰一次/零次计数」等顺序/计数断言是变异可红的前提（5-4 R1-F01 pipeline 先例）

**应用到本故事/Applied to This Story:**
- [ ] 矩阵派生锚测试（monkeypatch 策略维度翻转 → 判定随动——Task 1 循环 A）
- [ ] 手动组装 + 配置篡改 + 委托计时三先例（Task 4/5 + 验收）
- [ ] 双接线构造扩展回归面 grep 全量登记（Task 3 循环 C）
- [ ] 449 双形态 reason context 断言（Task 1 循环 B + 探针）

### deferred-work 处置（5-5 触发项分流）

| 项 | 处置 |
|----|------|
| 5-4 风险 #6 孤儿隔离键自愈（移交 5.5 决策） | **核销**（DC-12——入口 fail-closed 闭合危害面 + 5-4 upsert 自愈通道已在；Task 0.8 登记 + Task 7.3 终态更新） |
| 5-4 风险 #7 并发切换竞态（5.5/V1 评估） | **维持 deferred**（DC-12——探针不涉同 Agent 并发；归 V1 动态触发立项） |
| R1-DF2 StorageError(103) 同码双语义（触发含 5.5） | **维持 deferred**（DC-12——零存储层改动；归存储异常码专项） |
| R1-DF1 clear_scoped 接线纪律（触发=请求作用域接线） | **不触发**（本 Story 无请求作用域新端口——guard SINGLETON；维持原触发条件） |
| 工具熔断挂点（Epic 4 移交，5-4 评估不成立） | **不涉及**（5-4 已定论——tool_execution 装饰链域与 EIP 无耦合；维持 Epic 5 sprint planning 重估） |
| session_storage + RedisSessionStorage 休眠（续期触发=多轮会话 Story） | **不涉及**（SESSION 资源在 guard 判定面覆盖——判定层不依赖存储实现；存储激活归多轮会话 Story） |

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── value_objects/
│   │   ├── isolation_access.py        # 新建：IsolationResource/AccessOperation/IsolationViolationKind/
│   │   │                              #       IsolationAccessDecision/decide_isolation_access/decide_tool_access
│   │   └── agent_config.py            # 修改：allowed_tools 字段 + 守卫（440）
│   ├── exceptions/
│   │   ├── agent_exceptions.py        # 追加：448/449
│   │   ├── _code_ranges.py            # 修改：448-449 预留改已分配 + 双映射
│   │   └── __init__.py                # 追加导出
│   └── ports/
│       └── agent_repository.py        # 复用（零改动）
├── application/
│   ├── ports/
│   │   └── isolation_guard.py         # 新建：IsolationGuardPort（三方法）
│   ├── services/
│   │   ├── isolation_guard_service.py # 新建：三方法实现（三依赖）
│   │   ├── agent_workflow_service.py  # 修改：第五依赖 + execute 工具位拦截
│   │   └── isolation_management_service.py  # 复用（零改动）
│   └── use_cases/
│       ├── run_agent_workflow.py      # 修改：第五依赖 + 入口 fail-closed 接线
│       └── agent_instantiation.py     # 复用（零改动——探针用它构造 A/B）
├── infrastructure/
│   └── agent_orch/
│       └── yaml_agent_config_loader.py  # 修改：eip_config.allowed_tools 解析
├── interfaces/api/
│   └── exception_handlers.py          # 追加：EXCEPTION_HTTP_MAP 448→403/449→403
└── composition_root.py                # 追加：isolation_guard_service 注册 + 两 lambda 注入改造

configs/agents/ceo_agent.yaml          # 修改：eip_config.allowed_tools 显式清单（ACTIVE 全集）

tests/
├── unit/domain/value_objects/test_isolation_access.py          # 新建（矩阵全格）
├── unit/domain/value_objects/test_agent_config.py（追加）
├── unit/domain/exceptions/test_agent_exceptions.py（追加）
├── unit/infrastructure/agent_orch/test_yaml_agent_config_loader.py（追加）
├── unit/application/services/test_isolation_guard_service.py   # 新建（三方法守卫序）
├── unit/application/use_cases/test_run_agent_workflow.py（追加+同步）
├── unit/application/services/test_agent_workflow_service.py（追加+同步——文件名以仓库实际为准）
├── unit/interfaces/api/test_exception_handlers.py（追加）
├── unit/architecture/test_arch_agent_triple_isolation.py       # 新建（验证器 A-D）
├── contracts/test_port_contract_isolation_guard.py             # 新建（11 维度）
├── integration/test_integration_agent_triple_isolation.py      # 新建（6 场景 + 委托计时）
├── acceptance/test_acceptance_agent_triple_isolation.feature   # 新建（20 场景）
├── acceptance/test_acceptance_agent_triple_isolation.py        # 新建（BDD 步骤）
└── security/                                                     # 新建目录
    ├── __init__.py
    ├── conftest.py                                               # 场景级 Redis 客户端 + 门控
    └── test_isolation_security.py                                # 20 探针矩阵套件

pyproject.toml                        # 修改：markers 注册 security
Makefile                              # 修改：test-security target
.gitea/workflows/ci.yaml              # 修改：integration job 挂载 tests/security
docs/architecture/architecture.md     # 修改：§5 注记 + §13 目录树（Task 7）
docs/architecture/sisys-uni-exception-design.md  # 修改：§3.3.2 448/449（Task 1）
_bmad-output/implementation-artifacts/deferred-work.md  # 修改：三处置终态（Task 0/7）
```

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (glm-5.3) |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-10-23 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（L1632-1672） |
| **架构文档** | `docs/architecture/architecture.md`（§5/§13/L419-424） |
| **核心域设计** | `docs/architecture/sisys-core-domain-design.md`（§17.3.3/L1455-1460） |
| **前一个 Story** | `5-4-eip-basic-elastic-isolation.md`（v2.3.1 收敛态——风险 #6/#7 + R1-DF1/DF2 移交） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（含范围边界表——与 5.6/V1/V2/5.11 精确切分）
- [x] 架构约束从 architecture.md/core-domain-design/or.md/prd.md 提取
- [x] 前一个故事学习经验整合（5-4 教训链 + 移交三项处置 + deferred 六项分流）
- [x] 四视角并行代码调研（EIP 隔离实现 / Agent 编排与三面现状 / 安全测试与隔离设施 / 验收测试模板风格）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（含 20 探针矩阵定稿表——安全审计资产）
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/5-5-agent-triple-hard-isolation.md`（本文件）

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/value_objects/isolation_access.py` - 三重隔离判定核心（纯函数矩阵）
- `src/application/ports/isolation_guard.py` - 守卫端口（三方法）
- `src/application/services/isolation_guard_service.py` - 守卫服务实现
- `src/domain/exceptions/agent_exceptions.py`（追加 448/449）
- `tests/unit/domain/value_objects/test_isolation_access.py` - 矩阵全格单测
- `tests/unit/application/services/test_isolation_guard_service.py` - 守卫服务单测
- `tests/contracts/test_port_contract_isolation_guard.py` - 端口契约
- `tests/security/{__init__.py,conftest.py,test_isolation_security.py}` - 安全探针套件
- `tests/unit/architecture/test_arch_agent_triple_isolation.py` - 架构验证
- `tests/integration/test_integration_agent_triple_isolation.py` - 集成与性能
- `tests/acceptance/test_acceptance_agent_triple_isolation.{feature,py}` - 验收（20 场景）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 5.5 |
| **Story Key** | 5-5-agent-triple-hard-isolation |
| **File** | `_bmad-output/implementation-artifacts/stories/5-5-agent-triple-hard-isolation.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 5: Agent 协作系统（价值组：单 Agent 战略规划能力） |
| **优先级** | P0-5 |
| **覆盖 FR** | FR-AC-05（P0） |
| **性能锚** | epics L1651-1655（隔离检查 P95<50ms / 隔离测试通过率 100% / 并发 Agent≥10×50 探针拦截率 100%） |
| **覆盖率锚** | 应用层 ≥85% + 安全测试覆盖率 ≥90%（D-2 口径） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-7）
2. [x] All acceptance criteria specified（AC-1~AC-6）
3. [x] Architecture constraints extracted（PDP/PEP 分离 + R1-R4 分层落位）
4. [x] Previous story learnings integrated（5-4 教训链 + 移交三项处置 + deferred 六项分流）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | （待审查轮填充） | | |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** （待 dev-story 实施后）
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor）

#### 需决策 Decision Needed

- [ ] （无）

#### 已修复 Patch

- [ ] （待审查轮填充）

#### 已推迟 Defer

- [ ] （待审查轮填充）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施（从 Task 0 开始）
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

### 📋 变更日志 Change Log [dev-story 必填]

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-10-23 | v1.0.0 | 创建故事文件（四视角并行调研：EIP 隔离实现 / Agent 编排与三面现状 / 安全测试与隔离设施 / 验收测试模板风格；12 项关键架构决策 DC-1~DC-12 + 5 项偏离声明 D-1~D-5；20 条探针矩阵定稿[15×448+5×449]；三重隔离 PDP/PEP 分离架构[domain 纯判定矩阵 + application 守卫服务 + 双接线点]；448/449 领码 + agent 段 440-449 全分配；tests/security 四件套基建[目录/marker/CI 挂载/覆盖率专项]；5-4 移交三项处置[#6 核销/#7 维持/R1-DF2 维持] + deferred 六项分流；范围边界与 5.6/V1/V2/5.11 精确切分） |

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-10-23
**最后更新/Last Updated:** 2026-10-23
**更新说明/Description:**
- v1.0.0: 创建故事文件
