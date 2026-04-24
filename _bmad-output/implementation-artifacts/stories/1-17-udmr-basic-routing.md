# Story 1.17: UDMR 基础路由（本地优先静态配置）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 运维工程师,
**I want** 配置本地/云端路由策略（本地优先静态配置）,
**So that** MVP 阶段支持基础成本优化，验证本地路由占比≥80%。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 6（MVP 关键机制增强）的第一个故事，在 Story 1.14b（路由决策日志）完成后实现 UDMR 基础路由。核心价值：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **本地优先路由** | 本地模型优先，降低云端成本 | 本地路由占比≥80% |
| **故障自动切换** | 本地不可用或超时>30 秒时切换云端 | 故障切换时间<30 秒 |
| **路由决策日志** | 记录完整路由决策过程 | WORM 归档 7 年 |
| **静态配置驱动** | MVP 阶段使用静态配置，无需复杂评分算法 | 配置简单、易调试 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 6: MVP 关键机制增强，Story 1.17

**or.md 公理追溯:** 系统公理一（自主调用：trigger→route→execute），覆盖"route"阶段中的 UDMR 路由决策

**前置依赖:** Story 1.14b（路由决策日志已实现）

**后续依赖:** Story 1.19（成本度量基础，依赖 UDMR 路由日志）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 本地优先静态配置路由

**Given** 系统配置了本地模型（Ollama+Qwen2.5）和云端模型（Qwen/Claude）
**When** 执行 LLM 任务
**Then** 根据静态配置路由（本地优先）
**And** 本地不可用或超时>30 秒时切换云端

**验证标准/Validation Criteria:**
- [ ] UDMRouter 静态配置读取（本地模型列表、云端模型列表、超时阈值）
- [ ] 本地模型可用性检查（首次请求前缓存健康状态，TTL 30 秒）
- [ ] 本地优先路由逻辑
- [ ] 超时切换逻辑（>30 秒切换云端）
- [ ] 本地路由占比≥80%（100 次任务中至少 80 次选择本地）
- [ ] **健康检查时机**：首次请求时检查并缓存结果，TTL 30 秒内复用，避免每次请求都调用 Ollama `/api/tags` 导致延迟超标

### AC-2: 故障切换机制

**Given** 本地模型不可用或响应超时
**When** 执行 LLM 任务
**Then** 自动切换到云端模型
**And** 记录切换原因和切换延迟

**验证标准/Validation Criteria:**
- [ ] 本地模型健康检查（首次请求前缓存健康状态，TTL 30 秒）
- [ ] 超时阈值配置（默认 30 秒，可配置，范围 1-300 秒）
- [ ] 自动切换云端逻辑
- [ ] 切换日志记录（切换原因：unavailable/timeout/error）
- [ ] 故障切换时间<30 秒（**⚠️ 边界条件澄清**：LOCAL_TIMEOUT=30s 是等待超时阈值（AC-1），"切换时间<30s"是指**检测到故障后的路由决策执行延迟**（毫秒级），而非总体故障恢复时间。总体故障感知时间 = LOCAL_TIMEOUT + 路由决策延迟）
- [ ] **故障类型区分**：
  - Ollama 服务宕机 → /api/tags 返回 500 错误 → 切换云端，记录 reason="ollama_down"（500 错误立即使缓存失效）
  - 单个模型不存在 → /api/tags 返回 200 但模型不在列表中 → 切换云端，记录 reason="model_not_found"（不是 404，是列表为空或不包含目标模型）
  - 模型正在加载 → /api/tags 返回 200 但模型不在列表中（正在加载中）→ 等待 5 秒重试，仍不在列表则切换云端，记录 reason="model_loading"
- [ ] **恢复机制**：本地模型恢复后（健康检查成功），下一个请求自动切回本地，无需人工干预
- [ ] **⚠️ 持续变慢故障场景（缓存雪崩预防）**：若本地 Ollama 处于"持续变慢但未完全宕机"状态（响应时间 25-35 秒波动），健康检查可能通过但随后 LLM 调用超时——系统会不断在本地/云端之间震荡。解决方案：当连续 3 次 LLM 调用超时时（即使健康检查通过），自动将本地模型标记为 degraded，60 秒内不再尝试本地路由，直接走云端；60 秒后再次尝试健康检查

### AC-3: 路由决策日志

**Given** 路由决策完成
**When** UDMRouter 执行路由决策
**Then** 记录路由决策日志
**And** 日志包含：任务 ID、时间戳、选定路由（local/cloud）、估计成本、实际成本、延迟、切换原因

**验证标准/Validation Criteria:**
- [ ] RoutingDecisionLog 实体扩展（增加 route_location 字段：local/cloud）
- [ ] 路由决策日志存储至 PostgreSQL（复用 Story 1.14b 的 LoggingRepository）
- [ ] **WORM 归档标识**：写入时设置 worm_storage_ref（指向 L4 MinIO WORM 存储路径），Story 1.14b 的 worm_storage_ref 字段需在本 Story 中正确赋值
  - **路径构造规则**：`{bucket}/routing/{year}/{month}/{day}/{task_id}_{timestamp}.json`（bucket 复用 Story 1.14b 的 `audit-worm` bucket）
- [ ] 日志字段完整性校验
- [ ] 路由决策日志可检索性（按任务 ID/时间范围/route_location）

### AC-4: 路由性能要求

**Given** UDMRouter 接收路由请求
**When** 执行路由决策
**Then** 路由决策延迟 P95<100ms（architecture.md §1.4 KPI 表定义 MVP 目标 <100ms，V1 目标 <50ms；⚠️ architecture.md §4 UDMR 章节描述 P95<50ms 与 KPI 表不一致，以 KPI 表为准）

**验证标准/Validation Criteria:**
- [ ] 路由决策延迟 P95<100ms（**测量方法**：1000 次连续请求，前 100 次预热不计入，后 900 次统计 P95 值）
- [ ] 本地模型检查延迟<10ms（健康检查缓存命中时）
- [ ] 路由决策幂等性（相同输入产生相同输出）

### AC-5: 配置管理

**Given** 运维工程师需要调整路由策略
**When** 修改 UDMR 配置
**Then** 配置变更立即生效（无需重启服务）

**验证标准/Validation Criteria:**
- [ ] UDMR 配置模型（`src/infrastructure/config/udmr.py`）
- [ ] 环境变量读取（UDMR_ENABLED、LOCAL_MODELS、CLOUD_MODELS、LOCAL_TIMEOUT、CLOUD_ADVANTAGE_THRESHOLD）
- [ ] 配置验证（模型列表格式、阈值范围：LOCAL_TIMEOUT 1-300 秒）
- [ ] **动态生效机制**：每 60 秒自动轮询重载（不使用 SIGHUP，K8s 环境通过 volume mount 或 kubectl rollout restart 生效）
- [ ] 配置变更日志记录（记录重载时间戳和配置值）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] RoutingDecided 事件定义（`src/domain/events/routing_events.py`）
  - 字段: event_id, task_id, session_id, route_location (enum: local/cloud), route_target, cost_estimate, cost_actual, latency_ms, switch_reason (optional), timestamp
  - 事件类型自动设置: `event_type = "RoutingDecided"`
  - 复用 Story 1.14b 的 Triggered/Routed 事件模式

#### 数据模型 (Data Models)
- [ ] UDMRouter 服务类（`src/domain/services/udmr_router.py`）
  - 方法: `route(task_id, task_context) -> RoutingDecision`, `check_local_health(model_id) -> bool`, `execute_with_fallback(task_id, task_context) -> LLMResponse`
  - 职责: 本地优先路由决策、故障切换、日志记录
  - **LLMResponse 类型说明**：定义为 `dataclass` 或 `TypedDict`，包含字段: response_text, model_id, latency_ms, cost_actual（由调用方在异步回调中填充）
  - **execute_with_fallback 流程**：本地优先 → 超时/不可用切换云端 → 返回 LLMResponse（**同步返回**，不等待异步成本回调）→ 应用层在 LLMResponse 返回后**立即**调用 update_cost_actual() 更新实际成本（若 LLM 适配器支持同步返回 cost_actual）；若 LLM 调用是异步的，execute_with_fallback 应等待 LLM 返回实际成本后再返回 LLMResponse，或通过回调机制确保 cost_actual 在 save() 之前被填充
- [ ] ModelConfig 值对象（`src/domain/value_objects/model_config.py`）
  - 字段: model_id, model_type (enum: local/cloud), endpoint, timeout, priority
  - **endpoint 来源**：本地模型的 endpoint 通过 `OLLAMA_BASE_URL` 环境变量指定（如 `http://localhost:11434`），与 model_id 组合成完整地址；云端模型的 endpoint 通过 `CLOUD_MODEL_ENDPOINT` 环境变量指定（或由 LLM 适配器根据 model_id 查询注册表）
  - **priority 说明**：MVP 静态配置不使用，保留字段用于 V1+ 四因子评分接口兼容
  - **模型 ID 映射**：`LOCAL_MODELS`/`CLOUD_MODELS` 环境变量是逗号分隔的模型 ID 列表（如 `qwen2.5-3b,qwen2.5-7b`），直接映射到 ModelConfig.model_id，无需查询注册表
- [ ] RoutingDecision 值对象（`src/domain/value_objects/routing_decision.py`）
  - 字段: task_id, route_location, route_target, cost_estimate, cost_actual, latency_ms, switch_reason
  - **cost_actual 说明**：在 UDMRouter.execute_with_fallback 返回后由应用层更新（异步获取实际成本后调用 update_cost_actual）
  - **cost_estimate 估算方法**：MVP 阶段使用固定成本表（本地模型成本 = 0，云端模型按 API pricing table 查询）；V1+ 若启用 L2 四因子评分，根据模型类型/调用次数/上下文长度动态估算

#### L0 配置管理 (L0 Configuration)

> ⚠️ **MVP 简化说明：** 本 Story 实现的是 UDMR 三层决策架构的**简化版本**（静态配置优先），不实现完整的 L1 合规性检查和 L2 四因子评分。V1+ 将在 Story 11.1/11.2 升级为完整的三层决策。
>
> **L1/L2 跳过说明（MVP）：**
> - L1 合规性网关（PII/商业秘密/数据驻留/白名单校验）：MVP 阶段通过**网络隔离策略**实现（本地 Ollama 与云端网络隔离，敏感数据只能在本地处理），不实现代码层面的合规检查器
> - L2 四因子评分（语义匹配度/历史成功率/响应延迟/成本权重）：MVP 阶段**硬编码为本地优先**，通过静态配置 `LOCAL_MODELS`/`CLOUD_MODELS` 实现，无需评分算法

- [ ] UDMR 配置（`src/infrastructure/config/udmr.py`）
  - 环境变量: `UDMR_ENABLED`（默认 true）, `LOCAL_MODELS`（逗号分隔的本地模型 ID 列表）, `CLOUD_MODELS`（逗号分隔的云端模型 ID 列表）, `LOCAL_TIMEOUT`（默认 30 秒）, `CLOUD_ADVANTAGE_THRESHOLD`（默认 0.15，**仅 V1+ 动态评分使用，MVP 静态配置下此参数不生效但必须存在以保持接口兼容性**）
  - 从环境变量读取（`from_env()` 方法，复用 OtelConfig/RouteConfig 模式）
  - 配置验证：模型列表格式、阈值范围（LOCAL_TIMEOUT: 1-300 秒）
  - **reload() 方法**：实现 `reload()` 方法重新加载环境变量，返回新配置实例，保留旧实例用于回滚
  - **动态生效机制**：每 60 秒调用 `reload()` 重新加载（自动轮询）
  - **配置变更日志**：每次 reload 记录日志（时间戳、旧值、新值），使用 Python logging 模块
  - **reload() 回滚策略**：reload() 内部捕获异常，若新配置验证失败，保留旧配置实例并抛出 `ConfigurationReloadError`，调用方可通过异常感知重载失败；成功则返回新实例
  - **配置重载与健康检查缓存联动**：UDMR 配置重载后（如 LOCAL_MODELS 改变），OllamaHealthAdapter 的缓存应全量失效（clear all），避免旧的模型健康状态污染新的配置上下文。具体实现：UDMRouter 持有 OllamaHealthAdapter 实例，reload() 成功后调用 `health_adapter.clear_cache()` 清空所有缓存条目
  - **⚠️ K8s 环境说明**：Kubernetes 中 ConfigMap/Secret 更新通过 volume mount 热加载或 `kubectl rollout restart` 生效，SIGHUP 信号在 K8s Pod 中不保证可靠传递。MVP 阶段使用**每 60 秒轮询**机制满足动态生效需求；V1+ 可集成 Kubernetes Informer 或 ConfigMap watcher 实现更实时的配置变更通知

#### 本地模型健康检查 (Local Model Health Check)
- [ ] LocalModelHealthChecker 接口（`src/interfaces/services/local_model_health_port.py`）
  - 方法: `is_healthy(model_id) -> bool`, `get_response_time(model_id) -> float`
  - **⚠️ 职责边界说明**：LocalModelHealthChecker 只负责**预检**（Ollama /api/tags 可达性），不涉及实际 LLM 调用。实际 LLM 调用由 UDMRouter.execute_with_fallback 通过 LLM 适配器执行，两者职责分离：健康检查成功 ≠ LLM 调用必定成功（如模型进程崩溃、OOM 等）；若健康检查通过但 LLM 调用失败，故障切换逻辑在 execute_with_fallback 内部处理
  - **get_response_time 策略**：返回最近一次测量的响应时间（毫秒），**不缓存单一值**——因为响应时间随网络/CPU 抖动变化，缓存单一值无业务意义。MVP 阶段 `get_response_time` 仅用于监控/日志记录，不参与路由决策；V1+ 若用于 L2 四因子评分，需改为滑动窗口平均值
- [ ] OllamaHealthAdapter 实现（`src/infrastructure/services/ollama_health_adapter.py`）
  - 调用 Ollama `/api/tags` 端点检查模型列表
  - 测量响应时间
  - **健康状态缓存**：首次检查后缓存结果，TTL 30 秒，避免每次请求都调用导致延迟超标（P95<100ms 要求）
  - **主动探活机制**：缓存过期前 5 秒（25 秒时）提前异步探活，避免缓存失效瞬间的"缓存雪崩"。**触发机制**：OllamaHealthAdapter 内部维护一个后台任务调度器（`asyncio.create_task`），在缓存写入时调度一个延迟 25 秒的异步探活任务；若在 25 秒内缓存被使用，调度器取消该任务（避免无效探活）；使用单一 `asyncio.Lock` 保护缓存读写，防止并发写
  - **故障快速感知**：当 Ollama 服务返回 500 错误时，立即使缓存失效，下次请求直接探活而非等待 TTL
  - **并发请求处理（防缓存雪崩）**：多个请求同时到达且缓存失效时，使用**单一锁（`asyncio.Lock`）**确保只有一个请求执行健康检查，其他请求等待锁释放后从缓存读取；具体实现：请求进入时先尝试获取锁，若缓存有效则立即返回，若缓存失效则等待持有锁的请求完成健康检查后复用结果。**注意**：`asyncio.Lock` 是协程级别的同步原语，与 TCP 连接池（`aiohttp.ClientSession`）是两个独立的概念：Lock 防止并发探活，连接池管理 HTTP 请求生命周期

#### 路由决策日志存储 (Routing Decision Log Storage)
- [ ] RoutingDecisionLogRepository 仓储接口（`src/domain/repositories/routing_decision_log_repository.py`）
  - 方法: `save(log)`, `update_cost_actual(task_id, cost_actual)`, `find_by_task_id(task_id) -> RoutingDecisionLog`, `find_by_session_id(session_id) -> List[RoutingDecisionLog]`
  - **save() 流程**：初始保存时 cost_actual=None（因为实际成本在 LLM 返回后才可知），保存后返回 log_id
  - **update_cost_actual() 流程**：LLM 调用完成后，应用层调用此方法更新 cost_actual，支持幂等更新（相同值不重复写入）
  - 复用 Story 1.14b 的 LoggingRepository 模式
- [ ] PostgreSQL 实现（`src/infrastructure/repositories/postgres_routing_decision_log_repository.py`）

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1.17.feature`（由 Dev agent 在 Task 0 创建）
- [ ] 步骤实现文件：`tests/acceptance/test_story_1.17_steps.py`（BDD 步骤函数）
- [ ] **AC → Gherkin 场景映射**：

| AC | Gherkin 场景 | 验证内容 |
|----|-------------|---------|
| AC-1 | 配置读取-静态配置 | UDMRouter 从环境变量读取 LOCAL_MODELS/CLOUD_MODELS/LOCAL_TIMEOUT |
| AC-1 | 本地优先路由 | 本地模型可用时选择本地（占比≥80%） |
| AC-1 | 超时切换云端 | 本地响应>30 秒时切换云端 |
| AC-1 | 健康检查缓存 | 首次请求时检查并缓存结果，TTL 30 秒内复用 |
| AC-2 | 不可用切换云端（ollama_down） | Ollama 服务宕机时切换云端 |
| AC-2 | 不可用切换云端（model_not_found） | 单个模型不存在时切换云端 |
| AC-2 | 不可用切换云端（model_loading） | 模型正在加载时等待 5 秒后切换 |
| AC-2 | 恢复切回本地 | 本地模型恢复后自动切回本地 |
| AC-3 | 路由决策日志记录 | 日志包含 task_id、route_location、switch_reason 等 |
| AC-4 | 路由性能 P95<100ms | 1000 次连续请求，前 100 次预热，后 900 次统计 P95；测试用例使用 mock 健康检查（避免真实 Ollama 调用），仅测量 UDMRouter 路由决策延迟，不包含实际 LLM 调用耗时 |
| AC-5 | 配置动态生效 | 修改环境变量后 60 秒内自动重载（轮询机制） |
| AC-5 | 配置验证-阈值范围 | LOCAL_TIMEOUT 超出 1-300 秒范围时抛出 ValidationError |

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）

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

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | UDMRouter | 本地优先路由逻辑 | `tests/unit/domain/test_udmr_router.py` | Task 1 |
| **TDD 单元测试** | UDMRouter | 故障切换与恢复逻辑 | `tests/unit/domain/test_udmr_failover.py` | Task 1 |
| **TDD 单元测试** | UDMRConfig | 配置读取与验证 | `tests/unit/infrastructure/test_udmr_config.py` | Task 1 |
| **TDD 单元测试** | LocalModelHealthChecker | 健康检查接口契约 | `tests/unit/domain/test_local_model_health.py` | Task 1 |
| **TDD 单元测试** | OllamaHealthAdapter | Ollama 适配器（单元） | `tests/unit/infrastructure/test_ollama_health_adapter.py` | Task 1 |
| **TDD 单元测试** | UDMRouter | 路由性能基准测试 | `tests/unit/domain/test_udmr_performance.py` | Task 1 |
| **TDD 单元测试** | RoutingDecisionLogRepository | 日志存储（单元） | `tests/unit/infrastructure/test_routing_decision_log_repo.py` | Task 2 |
| **TDD 集成测试** | OllamaHealthAdapter | Ollama 适配器（集成） | `tests/unit/infrastructure/test_ollama_health_adapter_integration.py` | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `tests/acceptance/test_story_1.17.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `tests/acceptance/test_story_1.17_steps.py` | Task 0 |
| **SDD 架构验证** | 架构约束 | 六边形架构约束 | `tests/unit/architecture/test_udmr_architecture.py` | Task 3 |
| **集成测试** | 端到端流程 | 本地优先路由 + 故障切换 | `tests/integration/test_udmr_integration.py` | Task 3 |

#### 测试隔离约束（必须遵守）

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**
> 参考 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md) §5.5 测试隔离约束。

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **事务隔离** | 集成测试使用 transaction rollback | 数据泄漏导致随机失败 |
| **Schema 自创建** | fixture 内完成 Schema 初始化 | 依赖外部迁移，环境不一致 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符 | ID 冲突或状态污染 |
| **外部服务隔离** | Redis/Neo4j/Qdrant 测试前清理或用 mock | 真实数据被污染 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源；语义缓存测试用不同 embedding 向量 | 资源冲突导致并行失败 |
| **清理粒度** | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| **依赖声明** | Fixture 必须显式声明依赖 | 并行时清理顺序不确定 |
| **asyncio 上下文** | asyncio.Lock 类变量；处理 thread.ident 为 None | 锁失效或类型错误 |
| **pytest-asyncio** | 删除 scope=module 的 event_loop fixture | 与 auto mode 冲突 |
| **BDD async 配合** | BDD 步骤函数不使用 @pytest.mark.asyncio，用 event_loop.run_until_complete() 运行 async | 直接用 @pytest.mark.asyncio 会导致 BDD context 数据丢失 |
| **asyncio.run 使用** | 独立脚本用 asyncio.run()；pytest-xdist 并行测试中 BDD 步骤函数用 event_loop.run_until_complete() | asyncio.run() 创建新循环，并行测试时可能关闭错误循环 |
| **并发测试方法** | 单进程测试用 asyncio.run()；pytest-xdist 并行时 BDD 步骤用 event_loop fixture；真正并发测试在 async 函数内用 asyncio.gather() | 根据场景正确选择否则失败 |
| **外部客户端** | 第三方 API 必须验证方法存在性 | AttributeError |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback）
- ❌ autouse fixture 删除全局匹配资源（如 `test_*`）
- ❌ Fixture 假设清理顺序（必须显式声明依赖）
- ❌ asyncio.Lock 使用实例变量
- ❌ scope=module 的 event_loop fixture
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- ❌ pytest-xdist 并行测试时，BDD 步骤函数内使用 asyncio.run()（应使用 event_loop fixture）

**验证要求：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续5次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 本地优先静态配置路由 | Task 1 | Subtask 1.1-1.3（UDMRouter 本地优先逻辑） | `test_udmr_router.py` |
| AC-2 | 故障切换机制 | Task 1 | Subtask 1.10-1.12（故障切换 + 不可用切换 + 恢复机制） | `test_udmr_failover.py` |
| AC-3 | 路由决策日志 | Task 2 | Subtask 2.1-2.3（RoutingDecisionLog 存储） | `test_routing_decision_log_repo.py` |
| AC-4 | 路由性能要求 | Task 1 | Subtask 1.13（性能基准测试 P95<100ms） | `test_udmr_router.py` |
| AC-5 | 配置管理 | Task 1 | Subtask 1.7-1.9（UDMRConfig 动态生效） | `test_udmr_config.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **目的：** 在进入代码实现前，明确 Schema、API 契约、验收标准。这是 SDD 规范驱动的基础。

- [ ] Subtask 0.1: 定义领域事件 Schema（`src/domain/events/routing_events.py`）
- [ ] Subtask 0.2: 定义数据模型（`ModelConfig`, `RoutingDecision` 值对象）和服务接口（`UDMRouter` 服务类）
- [ ] Subtask 0.3: 定义 UDMR 配置（`src/infrastructure/config/udmr.py`），包括 `from_env()` 和 `reload()` 方法签名
- [ ] Subtask 0.4: 定义本地模型健康检查接口（`src/interfaces/services/local_model_health_port.py`），包括 `is_healthy()` 和 `get_response_time()` 方法签名
- [ ] Subtask 0.5: 定义路由决策日志仓储接口（`src/domain/repositories/routing_decision_log_repository.py`），包括 `save(log)`、`update_cost_actual(task_id, cost_actual)` 和 `find_by_*` 方法
- [ ] Subtask 0.6: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1.17.feature`
- [ ] Subtask 0.7: 编写 BDD 步骤实现 `tests/acceptance/test_story_1.17_steps.py`
- [ ] Subtask 0.8: 运行验收测试，确认失败（🔴 红阶段验证）

**红阶段验证标准：**
- [ ] 运行 `pytest tests/acceptance/test_story_1.17.feature -v` 确认所有场景失败
- [ ] Gherkin 失败原因可能是 `Undefined step`（BDD 步骤未实现）或 `AssertionError`（步骤实现但断言失败），两者都是红阶段预期行为
- [ ] 若失败原因是 `ModuleNotFoundError`（import 失败），说明测试文件本身的 import 路径有问题，需修正
- [ ] 如果测试意外通过（所有 scenario 都是 passed），说明测试没有正确验证实现缺失，需修正测试

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: UDMRouter 本地优先路由实现

**关联 AC:** AC-1, AC-2, AC-4, AC-5

#### TDD 循环 [A]：UDMRouter 本地优先路由

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_udmr_router.py`（测试本地优先路由逻辑） |
| 🟢 绿 | 实现 `UDMRouter` 类最小代码 |
| 🔄 重构 | 优化代码，应用依赖倒置，运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 UDMRouter 本地优先路由失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 UDMRouter 本地优先路由最小代码
- [ ] Subtask 1.3: 🔄 重构 — 优化 UDMRouter 代码（依赖倒置、类型注解）

#### TDD 循环 [B]：LocalModelHealthChecker 接口 + OllamaHealthAdapter

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_local_model_health.py`（使用 `unittest.mock.Mock` mock OllamaHealthAdapter，测试接口契约）和 `test_ollama_health_adapter.py`（OllamaHealthAdapter 单元测试，使用 real Ollama mock server） |
| 🟢 绿 | 实现 `LocalModelHealthChecker` 接口（不涉及具体适配器）和 `OllamaHealthAdapter` 实现 |
| 🔄 重构 | 优化缓存逻辑和重试策略 |

- [ ] Subtask 1.4: 🔴 红 — 编写 LocalModelHealthChecker 接口契约测试（使用 `unittest.mock.Mock` mock 适配器）
- [ ] Subtask 1.5: 🟢 绿 — 实现 LocalModelHealthChecker 接口 + OllamaHealthAdapter（缓存 + TTL + 重试）
- [ ] Subtask 1.6: 🔄 重构 — 优化缓存逻辑和重试策略（指数退避）

#### TDD 循环 [C]：UDMR 配置管理

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_udmr_config.py`（测试配置读取与验证） |
| 🟢 绿 | 实现 `UDMRConfig` 从环境变量读取 |
| 🔄 重构 | 添加配置验证逻辑 |

- [ ] Subtask 1.7: 🔴 红 — 编写 UDMR 配置测试
- [ ] Subtask 1.8: 🟢 绿 — 实现 UDMRConfig.from_env()
- [ ] Subtask 1.9: 🔄 重构 — 添加配置验证

#### TDD 循环 [D]：故障切换与恢复机制

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_udmr_failover.py`（测试故障切换与恢复逻辑） |
| 🟢 绿 | 实现故障切换逻辑（本地→云端）和恢复逻辑（云端→本地自动恢复） |
| 🔄 重构 | 优化重试和超时逻辑 |

- [ ] Subtask 1.10: 🔴 红 — 编写故障切换与恢复失败测试
- [ ] Subtask 1.11: 🟢 绿 — 实现故障切换与恢复逻辑
- [ ] Subtask 1.12: 🔄 重构 — 优化重试和超时逻辑

#### TDD 循环 [E]：路由性能基准测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_udmr_performance.py`（测试路由决策延迟 P95<100ms） |
| 🟢 绿 | 验证 UDMRouter 静态配置路由性能达标 |
| 🔄 重构 | 优化性能瓶颈（如缓存逻辑） |

- [ ] Subtask 1.13: 🔴 红 — 编写路由性能基准测试
- [ ] Subtask 1.14: 🟢 绿 — 验证 P95<100ms 达标
- [ ] Subtask 1.15: 🔄 重构 — 优化性能瓶颈

**完成标准/Definition of Done:**
- [ ] UDMRouter 实现完成
- [ ] 本地优先路由逻辑正确
- [ ] 故障切换机制正确
- [ ] 路由性能 P95<100ms
- [ ] 所有 TDD 循环测试通过
- [ ] 架构层覆盖率≥85%

---

### Task 2: 路由决策日志存储实现

**关联 AC:** AC-3

#### TDD 循环 [A]：RoutingDecisionLogRepository

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_routing_decision_log_repo.py`（测试日志存储） |
| 🟢 绿 | 实现 PostgreSQL 仓储 |
| 🔄 重构 | 优化 SQL 和错误处理 |

- [ ] Subtask 2.1: 🔴 红 — 编写路由决策日志仓储测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 PostgreSQL RoutingDecisionLogRepository
- [ ] Subtask 2.3: 🔄 重构 — 优化 SQL 查询和错误处理

#### TDD 循环 [B]：OllamaHealthAdapter 集成测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_ollama_health_adapter_integration.py`（测试 Ollama 适配器与 Ollama 服务交互） |
| 🟢 绿 | 实现 OllamaHealthAdapter（调用 /api/tags，缓存健康状态，TTL 30 秒） |
| 🔄 重构 | 添加重试逻辑和错误处理（指数退避，最多 3 次） |

- [ ] Subtask 2.4: 🔴 红 — 编写 OllamaHealthAdapter 集成测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 OllamaHealthAdapter（缓存 + TTL + 重试）
- [ ] Subtask 2.6: 🔄 重构 — 添加重试逻辑

> **说明：** OllamaHealthAdapter 的单元测试在 Task 1 Subtask 1.4-1.6，集成测试在 Task 2 Subtask 2.4-2.6。两者测试视角不同：
> - Subtask 1.4-1.6 **单元测试**：使用 mock Ollama server，验证接口契约和缓存逻辑
> - Subtask 2.4-2.6 **集成测试**：Subtask 2.5 的"实现"是指**通过集成测试验证**（而非重新实现）——确保 OllamaHealthAdapter 在真实 Ollama 服务下工作正常，包含真实网络的延迟、错误处理和重试行为

**完成标准/Definition of Done:**
- [ ] RoutingDecisionLogRepository 实现完成
- [ ] 日志存储正确（WORM 归档标识）
- [ ] 所有 TDD 循环测试通过

---

### Task 3: SDD 架构约束验证测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。
> 它验证前面 Task 创建的代码是否符合架构规则。

#### 架构验证测试实现

- [ ] Subtask 3.1: 创建 `tests/unit/architecture/test_udmr_architecture.py`
- [ ] Subtask 3.2: 实现六边形架构约束验证（依赖方向、无循环依赖）
- [ ] Subtask 3.3: 实现集成测试 `tests/integration/test_udmr_integration.py`（本地优先路由 + 故障切换端到端，与 Subtask 3.1-3.2 的架构验证测试路径不同，职责也不同：前者验证架构约束，后者验证端到端功能）

**完成标准/Definition of Done:**
- [ ] 所有架构/约束测试通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何违规都会导致测试失败

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（依赖倒置）、事件驱动架构
- **设计约束:**
  - 领域层零依赖（UDMRouter 位于**应用层**而非领域层——因为 UDMRouter 依赖 LocalModelHealthChecker 接口（接口层）和 RoutingDecisionLogRepository（仓储层），若放领域层会导致领域层依赖接口层，违反六边形架构）
  - 依赖方向：接口层 → 应用层 → 领域层 ← 基础设施层（UDMRouter 在应用层，RoutingDecision 值对象在领域层）
  - 路由决策日志必须 WORM 归档（7 年）
- **技术栈:** Python 3.11+, Pydantic V2, SQLAlchemy 2.0, aio-pika

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - UDMR 三层决策架构

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **本地优先静态配置（选中）** | 实现简单、易调试、满足 MVP 需求 | 灵活性低，无法动态调整 | ✅ 8/10（MVP） |
| 动态四因子评分 | 灵活性高、可优化路由决策 | 实现复杂、延迟可能超标 | 5/10（MVP 阶段） |
| 纯云端路由 | 无本地部署复杂度 | 成本高、延迟高 | 3/10 |

**MVP 阶段决策：** MVP 使用本地优先静态配置，V1+ 升级为四因子动态评分（Story 11.2）

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── entities/
│   │   │   └── routing_decision_log.py      # ✅ 已存在（Story 1.14b）- 扩展 route_location, switch_reason 字段
│   │   ├── events/
│   │   │   └── routing_events.py           # ✅ 已存在（Story 1.14b）- RoutingDecided 事件
│   │   ├── repositories/
│   │   │   └── routing_decision_log_repository.py  # 仓储接口
│   │   └── value_objects/
│   │       ├── model_config.py              # ModelConfig
│   │       └── routing_decision.py          # RoutingDecision
│   ├── application/
│   │   └── use_cases/
│   │       └── routing_use_case.py          # 应用层用例：协调 UDMRouter + 发布 RoutingDecided 事件 + 更新 cost_actual
│   │   └── services/
│   │       └── udmr_router.py               # UDMRouter 应用服务（依赖接口层和仓储层，放应用层而非领域层）
│   ├── application/
│   │   └── use_cases/
│   │       └── routing_use_case.py          # 应用层用例：协调 UDMRouter + 发布 RoutingDecided 事件 + 更新 cost_actual
│   ├── interfaces/
│   │   └── services/
│   │       └── local_model_health_port.py   # 本地模型健康检查接口
│   └── infrastructure/
│       ├── config/
│       │   └── udmr.py                      # UDMR 配置
│       ├── repositories/
│       │   └── postgres_routing_decision_log_repository.py  # PostgreSQL 实现
│       └── services/
│           └── ollama_health_adapter.py     # Ollama 健康检查适配器
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── test_udmr_router.py          # UDMRouter 本地优先路由单元测试
│   │   │   ├── test_udmr_failover.py        # 故障切换与恢复单元测试
│   │   │   ├── test_udmr_performance.py     # 路由性能基准测试
│   │   │   └── test_local_model_health.py   # LocalModelHealthChecker 接口契约测试（使用 mock）
│   │   └── infrastructure/
│   │       ├── test_udmr_config.py         # UDMR 配置单元测试
│   │       ├── test_ollama_health_adapter.py        # Ollama 适配器单元测试
│   │       ├── test_ollama_health_adapter_integration.py  # Ollama 适配器集成测试
│   │       └── test_routing_decision_log_repo.py       # 仓储单元测试
│   ├── integration/
│   │   └── test_udmr_integration.py        # 端到端集成测试
│   └── acceptance/
│       ├── test_story_1.17.feature
│       └── test_story_1.17_steps.py
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.14b - 自主调用循环 - route 实现](./1-14b-autonomous-invocation-route.md)

**关键学习/Key Learnings:**
- **路由决策日志必须 WORM 归档**：Story 1.14b 已实现 `RoutingDecisionLog` 实体，本 Story 需扩展 `route_location` 和 `switch_reason` 字段
- **复用现有模式**：事件定义、服务模式、仓储模式都遵循统一规范
- **配置管理遵循 `from_env()` 模式**：复用 OtelConfig/RouteConfig 的环境变量读取模式
- **六边形架构合规**：RouteService 位于领域层，定义接口，基础设施层实现

**应用到本故事/Applied to This Story:**
- [ ] 复用 `RoutingDecisionLog` 实体，扩展字段（route_location, switch_reason）
- [ ] 复用 `LoggingRepository` 模式实现 `RoutingDecisionLogRepository`
- [ ] 复用 `RouteConfig.from_env()` 模式实现 `UDMRConfig.from_env()`
- [ ] UDMRouter 遵循六边形架构：领域层定义服务，基础设施层实现健康检查适配器

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Qwen Code |
| **Version** | create-story workflow v2.5.0 |
| **Execution Date** | 2026-04-24 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-14b-autonomous-invocation-route.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] 故事需求从 `epics_v1.0.md` 提取
- [ ] 架构约束从 `architecture.md` 提取
- [ ] 前一个故事学习经验（1.14b）整合
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-17-udmr-basic-routing.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/services/udmr_router.py` - UDMRouter 服务
- `src/domain/value_objects/model_config.py` - ModelConfig
- `src/domain/value_objects/routing_decision.py` - RoutingDecision
- `src/domain/repositories/routing_decision_log_repository.py` - 仓储接口
- `src/interfaces/services/local_model_health_port.py` - 健康检查接口（LocalModelHealthChecker）
- `src/application/use_cases/routing_use_case.py` - 应用层用例（协调 UDMRouter + 事件发布）
- `src/infrastructure/config/udmr.py` - UDMR 配置
- `src/infrastructure/repositories/postgres_routing_decision_log_repository.py` - PostgreSQL 实现
- `src/infrastructure/services/ollama_health_adapter.py` - Ollama 适配器
- `tests/unit/domain/test_udmr_router.py` - UDMRouter 单元测试
- `tests/unit/domain/test_udmr_failover.py` - 故障切换单元测试
- `tests/unit/infrastructure/test_udmr_config.py` - 配置单元测试
- `tests/unit/infrastructure/test_ollama_health_adapter.py` - Ollama 适配器单元测试
- `tests/unit/infrastructure/test_ollama_health_adapter_integration.py` - Ollama 适配器集成测试
- `tests/unit/infrastructure/test_routing_decision_log_repo.py` - 仓储单元测试
- `tests/integration/test_udmr_integration.py` - 集成测试
- `tests/acceptance/test_story_1.17.feature` - Gherkin 场景
- `tests/acceptance/test_story_1.17_steps.py` - BDD 步骤实现
- `tests/unit/architecture/test_udmr_architecture.py` - 架构验证

**已存在文件（需扩展）:**
- `src/domain/entities/routing_decision_log.py` - ✅ 已存在（Story 1.14b）- 扩展 route_location, switch_reason 字段
- `src/domain/events/routing_events.py` - ✅ 已存在（Story 1.14b）- RoutingDecided 事件

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.17 |
| **Story Key** | 1-17-udmr-basic-routing |
| **File** | `_bmad-output/implementation-artifacts/stories/1-17-udmr-basic-routing.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 6: MVP 关键机制增强 |
| **优先级** | P0-17（MVP，ARCH UDMR 基础） |
| **覆盖 FR** | FR-CP-01（路由决策日志） |
| **层类型** | 架构层（Architecture） |

### 完成总结 Completion Summary

1. [ ] All tasks defined 所有任务定义完成
2. [ ] All acceptance criteria specified 所有验收标准已定义
3. [ ] Architecture constraints extracted 架构约束已提取
4. [ ] Previous story learnings integrated 前一个故事学习经验已整合
5. [ ] Sprint status synced to `ready-for-dev`

### 🔧 对抗性审查修复（Adversarial Review Fixes）

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | Task 1 Subtask 编号错误（1.7→1.9 跳跃，1.8 缺失） | P1 | 新增 TDD 循环 [D] 故障切换与恢复机制（Subtask 1.10-1.12），修正编号连续性 |
| 2 | UDMR 三层决策架构未说明 MVP 简化版本 | P2 | SDD 规范定义增加"MVP 简化说明"，明确本地优先静态配置是简化版 |
| 3 | 健康检查时机不明确（每次请求前 vs 缓存） | P2 | AC-1 增加健康检查时机说明（首次请求前缓存，TTL 30 秒） |
| 4 | 故障类型区分缺失（ollama_down/model_not_found/model_loading） | P2 | AC-2 增加三种故障类型区分和各自处理逻辑 |
| 5 | 恢复机制未定义（本地恢复后是否自动切回） | P2 | AC-2 增加恢复机制说明（自动切回本地，无需人工干预） |
| 6 | Task 0 Subtask 0.8 红阶段验证标准缺失 | P2 | 增加红阶段验证标准（失败原因必须是 ModuleNotFoundError 或 AssertionError） |
| 7 | 配置动态生效机制未定义 | P2 | AC-5 增加动态生效机制（每 60 秒重载或 SIGHUP 信号） |
| 8 | AC → Gherkin 场景映射缺失 | P2 | SDD 规范定义增加 AC → Gherkin 场景映射表 |
| 9 | PRIORITY_THRESHOLD 与 CLOUD_ADVANTAGE_THRESHOLD 命名混淆 | P3 | 重命名为 CLOUD_ADVANTAGE_THRESHOLD，与 architecture.md 一致 |
| 10 | 并行请求处理未覆盖 | P3 | 本地模型健康检查增加并发请求处理说明（asyncio.Semaphore 或连接池） |
| 11 | 项目结构说明未标注已存在文件 | P3 | 项目结构说明增加 ✅ 已存在标注，注明需扩展的字段 |
| 12 | 路由性能目标与架构不一致说明 | P3 | AC-4 增加说明（MVP P95<100ms 是静态配置特供，V1 升级后需回到 <50ms） |
| 13 | 文件清单与项目结构不一致（routing_use_case.py） | P2 | 文件清单明确 routing_use_case.py 为应用层用例，协调 UDMRouter + 事件发布 |
| 14 | test_udmr_failover.py 在测试分类表中缺失 | P2 | 测试分类表增加 UDMRouter 故障切换测试 |
| 15 | OllamaHealthAdapter 在 Task 1 和 Task 2 重复说明不清 | P2 | Task 1 说明为单元测试（接口契约），Task 2 说明为集成测试（与 Ollama 服务交互） |
| 16 | AC-3 WORM 归档实现未明确 | P2 | AC-3 增加 WORM 归档标识说明（worm_storage_ref 字段赋值） |
| 17 | 验收标准 Gherkin 场景覆盖不完整 | P2 | Gherkin 场景映射表增加"配置读取"和"占比≥80%"场景 |
| 18 | 本地模型配置与云端模型配置的映射未说明 | P3 | ModelConfig 增加模型 ID 映射说明（环境变量直接映射，无需注册表） |
| 19 | 健康检查缓存的失效机制未定义 | P2 | OllamaHealthAdapter 增加主动探活机制（25 秒时提前异步探活）和故障快速感知（500 错误立即失效） |
| 20 | Task 3 集成测试文件路径不一致 | P3 | Task 3 明确架构验证测试路径 `tests/unit/architecture/test_udmr_architecture.py` |
| 21 | AC → Task 追溯矩阵与实际 Subtask 分配不一致（AC-4 性能测试无位置） | P2 | 新增 TDD 循环 [E] 路由性能基准测试（Subtask 1.13-1.15），修正 AC → Subtask 映射 |
| 22 | 项目结构说明缺少 test_udmr_failover.py 和 test_ollama_health_adapter_integration.py | P2 | 项目结构说明增加这两个测试文件的路径 |
| 23 | TDD 循环 [A] 表头说测试"故障切换、性能要求"但实际是纯本地优先路由 | P3 | TDD 循环 [A] 表头修正为只测试"本地优先路由逻辑" |
| 24 | LocalModelHealthChecker 接口的单元测试文件缺失 | P2 | 测试分类表增加 LocalModelHealthChecker 接口契约测试 `test_local_model_health.py` |
| 25 | cost_actual 字段缺失 | P2 | RoutingDecision 值对象增加 cost_actual 字段，说明由应用层异步更新 |
| 26 | CLOUD_ADVANTAGE_THRESHOLD 环境变量 MVP 阶段不生效但未说明 | P3 | 配置说明明确此参数仅 V1+ 使用，MVP 静态配置下不生效 |
| 27 | LLMResponse 类型来源未定义 | P2 | UDMRouter 说明增加 LLMResponse 类型定义（dataclass/TypedDict） |
| 28 | routing_use_case.py（应用层）与 UDMRouter（领域层）关系未说明 | P2 | 应用层用例说明增加：协调 UDMRouter + 发布 RoutingDecided 事件 + 更新 cost_actual |
| 29 | Subtask 0.2 任务描述错误（UDMRouter 是服务类不是数据模型） | P2 | Subtask 0.2 修正为"定义数据模型（ModelConfig, RoutingDecision 值对象）和服务接口（UDMRouter 服务类）" |
| 30 | Subtask 1.4-1.6 测试 LocalModelHealthChecker 接口但无 mock 说明 | P2 | TDD 循环 [B] 增加 mock 说明（使用 unittest.mock.Mock）和 OllamaHealthAdapter 单元测试 |
| 31 | AC-5 配置变更日志与实现不对应（缺少 reload() 方法） | P2 | UDMR 配置增加 reload() 方法说明和配置变更日志实现（logging 模块） |
| 32 | RoutingDecisionLogRepository 的 update_cost_actual 方法缺失 | P2 | 仓储接口增加 update_cost_actual(task_id, cost_actual) 方法，说明初始 save() 时 cost_actual=None |
| 33 | test_local_model_health.py 路径不一致 | P3 | 项目结构说明将 test_local_model_health.py 移至 tests/unit/domain/（接口在 domain/ interfaces 层） |
| 34 | Subtask 0.3 与 Subtask 1.7-1.9 重复（规范 vs 实现） | P2 | Subtask 0.3 增加说明：定义 UDMR 配置的 from_env() 和 reload() 方法签名（规范），Task 1 实现 |
| 35 | AC-4 路由延迟测量方法不明确（预热后如何测量 P95） | P2 | AC-4 增加测量方法说明（1000 次请求，预热 100 次，后 900 次统计 P95） |
| 36 | ModelConfig.priority 在静态配置中无意义 | P3 | ModelConfig 增加 priority 说明（保留用于 V1+ 接口兼容，MVP 不使用） |
| 37 | execute_with_fallback 后 cost_actual 更新时序不清 | P2 | execute_with_fallback 流程增加说明：返回 LLMResponse → 应用层调用 update_cost_actual() 更新实际成本 |
| 38 | SIGHUP 信号处理机制未定义 | P2 | ~~UDMR 配置增加 SIGHUP 信号处理说明（使用 signal 模块，收到信号调用 reload()）~~ **已废弃**：Issue 44 中已移除 SIGHUP 依赖，改为每 60 秒轮询机制 |
| 39 | Subtask 1.5 和 1.6 矛盾（实现 vs 重构边界不清） | P3 | TDD 循环 [B] 重构说明：Subtask 1.5 实现接口和缓存基本逻辑，Subtask 1.6 优化缓存策略（指数退避） |
| 40 | AC-4 P95<100ms 与 architecture.md §4 描述 P95<50ms 冲突 | P1 | AC-4 澄清：architecture.md §1.4 KPI 表定义 MVP<100ms，§4 UDMR 章节描述 <50ms 与 KPI 表不一致，以 KPI 表为准；增加脚注说明架构文档内部不一致 |
| 41 | L1/L2 合规性检查跳过时 MVP 如何处理敏感数据未说明 | P1 | L0 配置管理增加"L1/L2 跳过说明（MVP）"：L1 通过网络隔离策略（本地 Ollama 与云端隔离）实现，L2 硬编码为本地优先 |
| 42 | AC-2 "故障切换时间<30秒"与 AC-1 "超时>30秒切换"矛盾 | P2 | AC-2 澄清："切换时间<30s"是指检测到故障后的路由决策执行延迟（毫秒级），总体故障感知时间 = LOCAL_TIMEOUT + 路由决策延迟 |
| 43 | 主动探活触发机制未定义（谁在 25 秒时触发？后台线程？） | P2 | OllamaHealthAdapter 增加触发机制说明：asyncio.create_task 调度延迟 25s 探活任务，缓存使用时取消任务，单一 asyncio.Lock 保护缓存读写 |
| 44 | SIGHUP 与 Kubernetes 环境不兼容 | P2 | UDMR 配置移除 SIGHUP 依赖，改为每 60 秒轮询机制；增加 K8s 环境说明（ConfigMap/Secret 通过 volume mount 或 kubectl rollout restart 生效）；增加 reload() 回滚策略 |
| 45 | WORM 归档路径构造逻辑缺失 | P2 | AC-3 增加路径构造规则：`{bucket}/routing/{year}/{month}/{day}/{task_id}_{timestamp}.json`，bucket 复用 Story 1.14b 的 audit-worm |
| 46 | 缓存失效时并发风暴未解决（asyncio.Semaphore 不能防止所有请求同时探活） | P2 | 并发请求处理改为"单一锁 asyncio.Lock 确保只有一个请求执行健康检查，其他等待锁释放后复用结果" |
| 47 | Subtask 0.6-0.7 Gherkin 红阶段失败原因是 undefined step 而非 assertion | P2 | 红阶段验证标准修正：Gherkin 失败原因可能是 Undefined step 或 AssertionError，都是红阶段预期行为；ModuleNotFoundError 才需要修正 |
| 48 | LLMResponse 与 LocalModelHealthChecker 接口存在逻辑断层 | P3 | LocalModelHealthChecker 增加职责边界说明：只负责预检，实际 LLM 调用由 execute_with_fallback 执行，两者职责分离 |
| 49 | Subtask 2.4-2.6 与 Subtask 1.4-1.6 边界不清（都说"实现 OllamaHealthAdapter"） | P3 | 说明 Subtask 1.4-1.6 是单元测试+mock 实现，Subtask 2.4-2.6 是集成测试验证（验证真实 Ollama 服务下的行为），不是重新实现 |
| 50 | 故障类型"model_not_found"不会返回 500，与 AC-2 描述不符 | P3 | 故障类型区分修正：model_not_found 是 /api/tags 返回 200 但模型不在列表中（不是 404），model_loading 同理 |
| 51 | 架构验证测试路径矛盾（unit/architecture vs integration） | P3 | Subtask 3.3 增加说明：两者路径和职责不同，architecture 验证架构约束，integration 验证端到端功能 |
| 52 | reload() 失败时的回滚策略不完整 | P3 | 随 issue 44 一起修复：reload() 内部捕获异常，验证失败时保留旧实例并抛出 ConfigurationReloadError |
| 53 | Issue 38 fix 与 Issue 44 fix 互相矛盾（Issue 38 增加 SIGHUP vs Issue 44 移除 SIGHUP） | P1 | Issue 38 fix 标注已废弃，实际已按 Issue 44 移除 SIGHUP |
| 54 | get_response_time 缓存单一浮点数毫无意义（响应时间随抖动变化） | P2 | get_response_time 不缓存单一值，仅返回最近一次测量；MVP 用于监控日志，V1+ 用于滑动窗口平均 |
| 55 | ModelConfig.endpoint 字段未说明来源（环境变量中无 Ollama endpoint 配置） | P2 | endpoint 来源：OLLAMA_BASE_URL（本地）和 CLOUD_MODEL_ENDPOINT（云端）环境变量 |
| 56 | 配置重载后健康检查缓存未联动失效（旧模型健康状态污染新配置） | P2 | UDMR 配置重载后调用 health_adapter.clear_cache() 清空所有缓存条目 |
| 57 | 持续变慢但未完全宕机场景导致本地/云端震荡 | P2 | 连续 3 次 LLM 超时时自动标记本地为 degraded，60 秒内直接走云端 |
| 58 | cost_estimate 估算方法未定义（是固定值还是公式？） | P3 | MVP 使用固定成本表（本地=0，云端按 API pricing）；V1+ 动态估算 |
| 59 | P95 测量方法在实现层面缺失（test_udmr_performance.py 如何判定 pass/fail？） | P3 | 测试用例使用 mock 健康检查，仅测 UDMRouter 路由决策延迟，测量前 100 次预热，后 900 次统计 P95 |
| 60 | asyncio.Lock 与连接池是两个不同概念但描述混用 | P3 | 澄清：Lock 防止并发探活，连接池管理 HTTP 请求生命周期；两者独立 |
| 61 | 测试分类表路径与项目结构不一致（test_local_model_health.py 等） | P3 | 统一测试文件路径为 tests/unit/domain/ 和 tests/unit/infrastructure/ |
| 62 | execute_with_fallback 返回后立即 update_cost_actual 存在竞态（LLM 异步回调未完成） | P3 | execute_with_fallback 应等待 LLM 返回实际成本后再返回，或通过回调机制确保 cost_actual 在 save() 前被填充 |
| 63 | UDMRouter 位于领域层还是应用层存在矛盾（项目结构放 domain/services/） | P3 | 明确 UDMRouter 放应用层 services/（依赖接口层和仓储层，放领域层违反六边形架构）；routing_use_case.py 协调 UDMRouter + 事件发布 |

### 下一步 Next Steps

- [ ] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `validate-create-story` 质量检查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**模板版本/Template Version:** 2.5.0
**创建日期/Created:** 2026-04-24
**最后更新/Last Updated:** 2026-04-24
**更新说明:**
- v2.5.0: 初始创建 Story 1.17 UDMR 基础路由
