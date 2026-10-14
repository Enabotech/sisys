# Story 5.1: CEO Agent 实例化（MVP 单 Agent）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 本 Story 是 **Epic 5 首个 Story**，也是 Epic 4 回顾行动项 7.1-1（链路接线断言）与 7.1-2（变异实证）落地模板后的**第一个强制执行 Story**。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 系统实例化 Agent 角色基础（CEO Agent，MVP 单 Agent 方案）,
**So that** MVP 阶段支持单 Agent 执行任务。

### 业务价值

- **覆盖 FR:** FR-AC-01（P0）——「系统可以实例化 Agent 角色基础（CEO Agent，MVP 单 Agent 方案）」（prd.md L1837）
- **Epic 定位:** Epic 5「🔑 入口」Story——mermaid 依赖图中 `5.1→5.2→5.3→{5.7,5.11}`、`5.1→5.4→{5.5,5.6}` 全部下游依赖本 Story 交付的实例化基础。Story 6.1（BLM 流程）经 5.3 间接依赖本 Story。
- **价值链:** CEO Agent 是 MVP 阶段唯一的 Agent 执行载体（prd.md L1507：角色演进 MVP=CEO → V1 +CFO/CMO → V2 全 7 角色；L453：MVP 用 CEO Agent 覆盖主要场景）。没有实例化基础，Epic 5 全部下游（身份档案、工作流、隔离、评估）无从谈起。
- **资产激活价值:** Epic 4 回顾普查发现生产活代码仅 50/166 端口。本 Story 是把 Agent 域休眠资产（Agent 实体、AgentEnginePort、Redis 基础设施）接入生产路径的第一步。

### 前置依赖（全部 ✅ 已完成，无阻塞）

| 依赖 | 组件 | 用途 | 状态 |
|------|------|------|------|
| Story 1.1 | Agent 实体 + AgentRole/AgentStatus + 状态机 | 直接复用，**禁止重新定义** | ✅ done |
| Story 1.4 | Redis 存储生态：`RedisAdapter`（L1CachePort）、`build_key` 键规范、`json_dumps/json_loads` | Agent 状态持久化的基础设施 | ✅ done |
| Story 3.2a | `LLMClientPort` + `LLMConfig` 值对象 | 上下文参考：5.1 本身**零 LLM 调用**；`AgentConfig.preferred_model` 为纯 `str \| None` 预留字段（**不引用 LLMConfig 类型**——LLMConfig 无 preferred_model 字段，5.3 引擎消费时映射为 `LLMConfig.model`） | ✅ done（Hard） |
| Story 1.18b | `AgentEnginePort` + `LangGraphEngine` | 仅作上下文——引擎消费属 5.3，5.1 不触碰 | ✅ done |
| Story 90-8 | 事件发布模式（`_publish_agent_decided`）、双通道登记模式 | 事件接线参考 | ✅ done |

**Epic 4 回顾就绪度结论**（epic-4-retro-2026-10-13-datasource.md §五）：「Epic 5 不受数据源影响，可直接启动——Agent 协作/评估零外部数据源依赖」。

---

## 🔗 现有代码继承（必须复用，禁止重复定义）

> ⚠️ **防重复造轮子清单**——以下组件已存在，dev agent 只可「直接复用 / 参考」，禁止新建同义组件。

| 组件 | 文件路径 | 复用方式 |
|------|---------|---------|
| `Agent` 实体（agent_id/role/name/description/status/failure_reason/domain_knowledge/responsibilities/created_at/updated_at + `validate()` + 状态机 `start/complete/fail/restart/wait`） | `src/domain/entities/agent.py` | **直接复用**——实例化即构造此实体 |
| `AgentRole` 枚举（CEO/CFO/CMO/CTO/COO/CHO/AUD/SYS 八角色） | `src/domain/entities/agent.py` L16-26 | **直接复用** |
| `AgentStatus` 五态状态机（IDLE/RUNNING/WAITING/COMPLETED/FAILED，非法迁移抛 `EntityStateTransitionError`） | `src/domain/entities/agent.py` L29-174 | **直接复用**（实例化后初始态 IDLE） |
| `PortSpec`/`register_port`/`Lifetime`/`Resolver` DI 体系 | `src/domain/ports/registry.py`、`resolver.py`、`src/composition_root.py` | **直接复用**（注册模式样例见 Dev Notes §关键代码模式参考） |
| `build_key(namespace, *parts)` → `sisys:{namespace}:{parts}` | `src/infrastructure/storage/redis/key_builder.py` | **直接复用**（Agent 状态键 `sisys:agent:{agent_id}`） |
| `json_dumps`（RedisJSONEncoder：datetime→ISO、UUID→str、Enum→value）/ `json_loads`（**不还原类型**，调用方重建） | `src/infrastructure/utils/json_ser.py` | **直接复用** |
| `RedisAdapter`（组合 `raw_client`，SINGLETON，注册名 `redis_adapter`） | `src/infrastructure/storage/redis/redis_adapter.py` | **组合注入**（RedisAgentRepository 组合它，仿 RedisSnapshotStore） |
| `RedisSnapshotStore` 实体↔Hash 转换模式（`_snapshot_to_hash`/`_hash_to_snapshot` 静态方法 + 单 field `latest` JSON blob 写入 `hset`+`expire`；TTL 范围校验在 `set_ttl`（60~2592000，抛 ValidationError(201)——**本 Story 仓储校验改用 AgentConfigError(440)，仅对齐范围数字不对齐异常类型**）） | `src/infrastructure/storage/redis/redis_snapshot_store.py` | **参考照抄**（RedisAgentRepository 的结构模板） |
| `AgentDecided` 事件结构（frozen dataclass + `agent_id: UUID = field(kw_only=True)` + `__post_init__` 设 aggregate_type） | `src/domain/events/agent_events.py` L15-36 | **参考**（AgentInstantiated 事件模板） |
| `InMemoryEventBus` 真实类（验收事件断言；**未注册端口**——组合根 `event_publisher` 默认 impl 是 `DualChannelEventBus`，验收环境无 RabbitMQ 故验收测试**直接构造注入**） | `src/infrastructure/messaging/inmemory_event_bus.py` + 先例 `tests/acceptance/test_acceptance_strategic_archive.py` L126-137 | **直接复用**（直接构造，不经组合根） |
| `event_channels.yaml` 事件通道结构 + `ChannelRouter.DEFAULT_MAPPINGS` | `configs/event_channels.yaml` L177-180、`src/infrastructure/messaging/channel_router.py` L231 | **追加登记**（AgentInstantiated 双登记） |
| `EntityValidationError`(EXCEPTION_242)/`EntityStateTransitionError`(EXCEPTION_243) | `src/domain/exceptions/business_exceptions.py` | **直接复用**（实体校验/状态迁移守卫） |
| CLI 独立入口模式（`bootstrap()` + `resolve()` + `build_parser()` + `main(argv)->int` + `asyncio.run()` + pyproject `[project.scripts]` 注册 + docstring 架构约束声明） | `src/interfaces/cli/ocr_cli.py`（注册样例 `pyproject.toml` L155-161） | **参考照抄**（agent_cli.py 结构模板）。⚠️ **勿效仿** `commands/document_commands.py`——其 `build_version_parser` 无任何挂载点（未接线资产），不存在集中式 CLI 主入口可挂载 |
| 测试基建：`get_test_env()`/`SISYS_USE_TEST_PORTS=1`（Redis 6380）、`TestTenant.redis_key_prefix`、`real_redis` fixture（**仅 integration conftest 有**——acceptance 侧刻意不提供共享 fixture，验收文件内自建场景级 Redis ping+skip，先例 test_acceptance_autonomous_invocation_execute.py L69-87）、acceptance conftest 自动 marker | `tests/environments.py`、`tests/isolation.py`、`tests/integration/conftest.py`、`tests/acceptance/conftest.py` | **直接复用** |

**明确不存在、本 Story 需新建**（已全仓 grep 验证零先例）：

1. Agent 实例化用例（应用层，零先例）
2. Agent 基础配置体系（无 `AgentConfig`、无 `AGENT_*` 环境变量、无 `configs/agents/` 目录）
3. `AgentRepository` 端口与 Redis 实现（架构文档 §13.2 规划项，未落地）
4. `AgentInstantiated` 事件（事件清单仅有 AgentDecided）
5. `agent` 异常子域（`_code_ranges.py` 无此子域；440-449 空闲）
6. Agent CLI 入口（interfaces 层零 agent 路由）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 接收实例化命令并创建 CEO Agent 实体

**Given** Agent 协作服务已启动（组合根 `bootstrap()` 完成）
**When** 接收 Agent 实例化命令（指定角色 CEO）
**Then** 实例化 CEO Agent——构造 `Agent` 领域实体（复用现有实体，role=CEO，status=IDLE，name/description/domain_knowledge/responsibilities 来自基础配置）
**And** 返回 `agent_id`（`uuid4` 生成），且对 MVP 未开放角色（CFO/CMO/CTO/COO/CHO/AUD/SYS）抛 `AgentRoleNotSupportedError`（EXCEPTION_441）
**And** 两次实例化生成两个独立 Agent（agent_id 不同、Redis 键不互相覆盖）

**验证标准/Validation Criteria:**
- [ ] `InstantiateAgentUseCase.execute(role=AgentRole.CEO)` 返回含 `agent_id` 的结果对象，实体 `role == AgentRole.CEO`、`status == AgentStatus.IDLE`
- [ ] 非 CEO 角色 → `AgentRoleNotSupportedError`，`error.code == "EXCEPTION_441"`，`error.context` 携带 `role`
- [ ] 实体校验失败（如配置产出的字段非法）走既有 `EntityValidationError`（EXCEPTION_242），不新造异常（用例透传实体校验异常，单测断言见 Task 4 红阶段）

### AC-2: 加载 CEO Agent 基础配置

**Given** Agent 配置文件 `configs/agents/ceo_agent.yaml` 随代码分发
**When** 实例化 CEO Agent
**Then** 通过 `AgentConfigLoader` 端口加载 YAML → 构造 `AgentConfig` 领域值对象（纯 dataclass，零外部依赖）
**And** 配置文件缺失 / YAML 解析失败 / 必填字段缺失 / 角色与配置不匹配 → 抛 `AgentConfigError`（EXCEPTION_440）
**And** 有效配置加载成功率 100%（确定性文件 IO，无随机失败面）

**验证标准/Validation Criteria:**
- [ ] `AgentConfig` 为 frozen dataclass，位于 domain 层，仅含标准库类型 + `AgentRole` 枚举
- [ ] YAML 字段→dataclass 映射完整（见 Task 0 数据模型 Schema；`capabilities.*` YAML list → `tuple[str, ...]` 由加载器显式转换）
- [ ] 三类失败路径（文件缺失/解析失败/字段无效）均抛 `AgentConfigError`，`error.code == "EXCEPTION_440"`，消息面向调用方可理解（不泄露堆栈/路径内部细节）
- [ ] `.md` 身份档案（IDENTITY.md 等 7 件，FR-AC-02）**明确不在本 Story 范围**（属 Story 5.2）

### AC-3: Agent 状态持久化至 Redis 并可读回

**Given** CEO Agent 实体已构造
**When** 实例化用例执行持久化
**Then** 经 `AgentRepository` 端口将 Agent 实体完整持久化至 Redis（键 `sisys:agent:{agent_id}`，Redis Hash **单 field `latest` 承载全字段 JSON blob**——`hset(key, "latest", json_dumps(...))` + `expire`，仿 RedisSnapshotStore L116-117 形态，非逐 field Hash）
**And** `get(agent_id)` 读回的实体与原实体字段完全一致（UUID/Enum/datetime 显式序列化与重建——`json_loads` 不还原类型，必须手动重建 `AgentRole`/`AgentStatus`/datetime）
**And** 持久化带 TTL（默认 86400s，由 `AgentConfig.state_ttl` 覆盖，范围校验 60~2592000，越界抛领域异常）
**And** 持久化失败（Redis 不可达）抛领域异常，**禁止静默吞异常**（与 `RedisSessionStorage` 的优雅降级语义刻意区分）

**验证标准/Validation Criteria:**
- [ ] Redis 中键 `sisys:agent:{agent_id}` 存在且 TTL > 0
- [ ] 读回实体 `role/status/created_at` 等全字段与写入一致（Enum/datetime 重建正确）
- [ ] `ttl` 越界（<60 或 >2592000）→ `AgentConfigError`（EXCEPTION_440，配置参数越界语义；`AgentConfig.__post_init__` 校验为主，仓储层防御性二次校验同异常）
- [ ] Redis 不可达时用例抛异常退出（不返回假成功）

### AC-4: 实例化发布 AgentInstantiated 领域事件

**Given** Agent 实体持久化成功
**When** 实例化用例完成
**Then** 发布 `AgentInstantiated` 领域事件（frozen dataclass，`agent_id`/`role`/`name`/`config_version`，`aggregate_type="Agent"`）
**And** 事件在 `configs/event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` **双登记**（reliable 通道，routing key `sisys.events.reliable.agent_instantiated`，对齐 AgentDecided 先例）
**And** 发布点在 `InstantiateAgentUseCase` 内真实调用（Epic 4 教训：事件零发布是 P0 重灾区——发布点代码位 + 订阅方可达必须进入链路接线断言清单）

**验证标准/Validation Criteria:**
- [ ] 验收测试用真实 `InMemoryEventBus` 注入用例，断言 `published_events` 含 `AgentInstantiated` 实例且字段正确
- [ ] `configs/event_channels.yaml` 与 `channel_router.py DEFAULT_MAPPINGS` 均含 AgentInstantiated（两处 grep 可达）
- [ ] 事件发布失败不中断实例化结果返回？——**按 AgentDecided 先例**：发布失败 `logger.exception` 记录不回滚业务状态（对齐 LangGraphEngine L84-88——注释明示「事件发布独立于图执行状态，失败不回写 FAILED」，日志级别为 exception 非 warning），但持久化成功是发布前提（先持久化后发布）

### AC-5: 性能指标

**Given** 真实 Redis 服务可用（`SISYS_USE_TEST_PORTS=1` → 6380 端口）
**When** 执行实例化全链路（配置加载 → 实体构造 → Redis 持久化 → 事件发布）
**Then** 实例化延迟 **P95 < 200ms**（≥20 次采样取 P95，`time.perf_counter` 计时——本 Story 对 epics L1472「P95<200ms」门禁的采样方法细化，epics 原文未规定采样法）
**And** **并发 ≥10** 个 Agent 同时实例化全部成功且互不干扰（NFR-PERF-04 MVP 档：asyncio.gather 10 并发，键天然隔离）
**And** 配置加载成功率 100%（AC-2 确定性）

**验证标准/Validation Criteria:**
- [ ] 性能测试基于真实 Redis（非 fakeredis），标记 `benchmark`，采样 ≥20 次断言 P95<200ms
- [ ] 10 并发 gather 全部返回不同 agent_id，Redis 键数 =10，无相互覆盖
- [ ] 复用 SINGLETON `redis_adapter` 连接（禁止每次实例化新建 Redis 连接——性能前提）

### AC-6: 端口契约与六边形架构合规

**Given** 本 Story 新增端口与入口
**When** 契约测试与架构测试运行
**Then** 三个新端口（`agent_repository`/`agent_config_loader`/`agent_instantiation_use_case`）在组合根注册为 `PortSpec`，契约测试 11 维度全过（维度清单：端口已注册/name/version/interface 是 Protocol/lifetime/owner/module/tags/impl 工厂可调用且产出 isinstance/REQUIRED_METHODS/Protocol runtime_checkable——见 test_port_contract_tool_execution_repository.py docstring）
**And** 依赖方向合规：domain 零外部依赖、infrastructure 不 import application/interfaces、CLI 仅依赖应用层端口
**And** CLI 入口 `sisys-agent instantiate --role ceo` 接线生效（pyproject script 注册 + 命令输出 agent_id）——「代码写了但没接线 ≠ done」（Epic 4 团队协议）

**验证标准/Validation Criteria:**
- [ ] `tests/contracts/test_port_contract_agent_repository.py` 等契约测试通过（11 维度：已注册/name/version/interface/lifetime/owner/module/tags/impl 工厂 9a+9b/REQUIRED_METHODS/runtime_checkable）
- [ ] 架构测试断言：`src/domain/value_objects/agent_config.py` 与 `src/domain/events/agent_events.py` 零第三方 import；`src/domain/` 全目录零 `import yaml`/`yaml.safe_load`；Agent 配置解析链的 yaml 用法仅新增于 `yaml_agent_config_loader.py`（⚠️ `src/application/skills/frontmatter.py` L22/L94 与 `event_bus_config_loader.py` 为既有合法存量，不在断言面——**禁止写「全仓仅命中一处」**）
- [ ] CLI 入口接线生效：`poetry run sisys-agent instantiate --role ceo` 输出 agent_id（pyproject script 注册 + 端到端真实执行）
- [ ] 链路接线断言清单全部绿灯或显式 deferred 登记（见 Task 0）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] 新增 `AgentInstantiated`，定义位于 `src/domain/events/agent_events.py`（与 AgentDecided 同文件，agent 聚合事件内聚）
- [ ] frozen dataclass 标准库实现，字段级 Schema：
  - `agent_id: uuid.UUID = field(kw_only=True)`（对齐 AgentDecided 的 kw_only 风格）
  - `role: str`（AgentRole.value）
  - `name: str`
  - `config_version: str`
  - `event_type: str = field(default="AgentInstantiated", init=False)`（**放置位置与 agent_events.py 既有事件风格对齐**）
  - `__post_init__` 设置 `aggregate_id=str(agent_id)`、`aggregate_type="Agent"`（对齐 AgentDecided）
- [ ] 事件命名符合 `[Aggregate][EventName]` 规范（`Agent` + `Instantiated`）
- [ ] 双登记：`configs/event_channels.yaml`（`rabbitmq_routing_key: "sisys.events.reliable.agent_instantiated"`、`delivery_mode: "reliable"`、`description`）+ `src/infrastructure/messaging/channel_router.py` `DEFAULT_MAPPINGS`（对齐 L231 AgentDecided 条目结构）
- [ ] 从 `src/domain/events/__init__.py` 导出（`__all__` 同步）

#### 数据模型 (Data Models)

- [ ] 新增 `AgentConfig` 值对象，位于 `src/domain/value_objects/agent_config.py`（目录已存在），frozen dataclass，**零外部依赖**（仅标准库 + `AgentRole`）：

```python
@dataclass(frozen=True)
class AgentConfig:
    role: AgentRole                    # 必填，枚举
    name: str                          # 必填，如 "CEO Agent"
    description: str                   # 必填
    version: str                       # 必填，配置版本（如 "1.0.0"），写入 AgentInstantiated.config_version
    responsibilities: tuple[str, ...]  # 必填，非空
    domain_knowledge: tuple[str, ...]  # 必填，非空
    preferred_model: str | None        # 可选，纯 str 预留（不引用 LLMConfig 类型——其无该字段）；5.3 消费时映射 LLMConfig.model
    state_ttl: int = 86400             # Agent 状态 TTL 秒，范围 60~2592000
    default_isolation_level: str = "L4"  # 5.4 EIP 消费，本 Story 仅承载
```

- [ ] `AgentConfig` 自校验（`__post_init__` 或 `validate()`）：role 合法、必填非空、state_ttl 范围——校验失败抛 `AgentConfigError`（EXCEPTION_440）
- [ ] **复用不修改**：`Agent` 实体（`src/domain/entities/agent.py`）、`AgentRole`、`AgentStatus`、状态机方法
- [ ] `configs/agents/ceo_agent.yaml` 新建，YAML 结构（core-domain §17.3.6 最小子集）：

```yaml
agent:
  name: "CEO Agent"
  version: "1.0.0"
  description: "首席执行官 Agent，MVP 单 Agent 方案的战略规划执行者"
identity:
  role: "ceo"
capabilities:
  responsibilities: ["战略方向", "最终决策", "高管协调"]        # core-domain §17.3.1 CEO 条目
  domain_knowledge: ["宏观趋势", "竞争格局", "战略意图"]        # §17.3.1 expertise
llm_config:
  preferred_model: null    # 留空时 5.3 回退 UDMR 路由；本 Story 不调用 LLM
eip_config:
  default_isolation_level: "L4"
memory_config:
  state_ttl: 86400
```

#### 统一端口定义注册与管理 (Port Contract)

- [ ] 端口契约定义位于 `src/domain/ports` 与 `src/application/ports`
- [ ] 端口注册中心位于 `src/domain/ports/registry.py`，所有端口必须登记为 `PortSpec`
- [ ] 端口实现仅可在 `src/composition_root.py` 统一注册，禁止业务代码直接实例化具体实现
- [ ] 端口解析器位于 `src/domain/ports/resolver.py`，业务代码只通过抽象解析实现
- [ ] 端口契约门禁位于 `src/domain/ports/contract_gate.py`，端口变更必须通过兼容性检查
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_agent_repository.py` 等 3 个）
- [ ] 接口命名符合单一职责，禁止同义接口重复定义
- [ ] 端口具备唯一名称、版本、owner、兼容策略
- [ ] 跨模块调用仅依赖抽象接口，不直接依赖实现类
- [ ] 端口变更配套契约测试与兼容性检查
- [ ] 禁止在服务文件中本地定义 Protocol / Port 抽象

**本 Story 端口契约清单（唯一事实源）：**

| # | 端口名称（注册名） | 版本 | interface | 实现模块 | lifetime | owner | tags | 状态 |
|---|------------------|------|-----------|---------|----------|-------|------|------|
| 1 | `agent_repository` | v1.0.0 | `AgentRepository`（domain/ports/agent_repository.py） | `src.infrastructure.storage.redis.redis_agent_repository.RedisAgentRepository` | SCOPED | platform | ("redis","agent") | 新建 |
| 2 | `agent_config_loader` | v1.0.0 | `AgentConfigLoader`（application/ports/agent_config_loader.py） | `src.infrastructure.agent_orch.yaml_agent_config_loader.YamlAgentConfigLoader` | SINGLETON | platform | ("agent","config") | 新建 |
| 3 | `agent_instantiation_use_case` | v1.0.0 | `InstantiateAgentUseCase`（application/use_cases/agent_instantiation.py，interface 绑定自身类型，对齐 orchestration_service 先例） | 工厂 lambda：resolve agent_config_loader + agent_repository + event_publisher | SINGLETON | platform | ("agent",) | 新建 |

**端口方法签名（Task 0 定稿，实现不得偏离）：**

```python
# src/domain/ports/agent_repository.py —— 仓储端口（R1 领域层基础端口；单字段标识查找用直接参数）
@runtime_checkable
class AgentRepository(Protocol):
    async def save(self, agent: Agent, ttl: int | None = None) -> None: ...
    async def get(self, agent_id: UUID) -> Agent | None: ...
    async def delete(self, agent_id: UUID) -> None: ...
    async def exists(self, agent_id: UUID) -> bool: ...

# src/application/ports/agent_config_loader.py —— 配置加载端口（R2 应用层具体应用端口）
@runtime_checkable
class AgentConfigLoader(Protocol):
    async def load(self, role: AgentRole) -> AgentConfig: ...
```

- [ ] `RedisAgentRepository` 组合 `RedisAdapter`（构造注入 `adapter=resolver.resolve("redis_adapter")`，仿组合根 snapshot_repository 注册样例——composition_root.py L941-955）；Hash 操作走 `adapter.raw_client`；静态方法 `_agent_to_hash`/`_hash_to_agent` 做实体↔Hash 转换（UUID→str、Enum→value、datetime→ISO；读回显式重建）；键 `build_key("agent", str(agent_id))`
- [ ] `YamlAgentConfigLoader` 的 YAML 解析用 `asyncio.to_thread(yaml.safe_load, ...)` 包装（不引入 aiofiles 新依赖）；配置目录路径构造函数注入（默认 `configs/agents/`，测试传 tmp_path）

#### 端口契约清单执行约束（强制）

- [ ] 本清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口，禁止未同步更新 registry / resolver / contract test
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增异常在 Task 0 完成设计，Task 1 实现。
> **禁止 `raise ValueError`**；完整清单见 [`sisys-uni-exception-design.md §3.12`](../../../docs/architecture/sisys-uni-exception-design.md)。

**新建 `agent` 子域，编码段 EXCEPTION_440 ~ 449**（440-449 当前空闲，全仓 grep 验证无碰撞；遵循 data_source(410-419)/debate(420-429)/tool_version(430-439) 独立物理段先例）。定义文件：`src/domain/exceptions/agent_exceptions.py`（对齐 `debate_exceptions.py`/`data_source_exceptions.py` 独立子域文件先例）。

| 异常类 | 编码 | 基类 | 触发场景 | HTTP 映射 |
|--------|------|------|---------|-----------|
| `AgentConfigError` | EXCEPTION_440 | `SystemException` | 配置文件缺失 / YAML 解析失败 / 必填字段无效 / role 与配置不匹配 / state_ttl 越界（配置资产属系统资源，同 ConfigurationError(101) 继承链；HTTP 500） | 500 |
| `AgentRoleNotSupportedError` | EXCEPTION_441 | `BusinessException` | 请求实例化 MVP 未开放角色（非 CEO）——业务能力范围规则违反（同 DebateLowDivergenceError(422)→422 先例） | 422 |
| （预留） | EXCEPTION_442~449 | — | 预留给 5.2 档案加载 / 5.4-5.5 EIP 隔离 / 5.3 工作流异常 | — |

**继承链选择理由（写入 agent_exceptions.py 模块 docstring，仿 debate_exceptions.py 风格）：** 440 根因是系统配置资产缺陷（部署错误，非调用方输入错误）故入 SystemException；441 是 MVP 阶段性业务规则限制故入 BusinessException——两者无法共享子域基类，**不设 AgentError 子域基类**（项目规范必须继承三大抽象分层之一，relevance/debate 平铺无基类先例支持）。

- [ ] 定义文件 `src/domain/exceptions/agent_exceptions.py`（模块 docstring 含编码范围/继承链理由/消息安全性声明，Google 风格全中文注释）
- [ ] `_code_ranges.py`：CODE_RANGES 增加 `agent(440-449)` + `_CLASS_TO_SUBDOMAIN` 注册两异常
- [ ] `src/domain/exceptions/__init__.py` 暴露两异常（`__all__` 同步）+ **`src/interfaces/api/exception_handlers.py` 的 `EXCEPTION_HTTP_MAP`（L130-262）精确注册**：追加 `AgentConfigError: 500`、`AgentRoleNotSupportedError: 422` 两行（对齐 debate L253-255 条目形态；`_get_http_status` 先精确 type 匹配再 isinstance 回退，441 未注册将回退基类 BusinessException→400）
- [ ] 子域码段校验：`poetry run pytest tests/unit/domain/exceptions/ -v`（test_error_code_uniqueness.py + test_code_ranges.py 共 8 项）
- [ ] 构造器携带领域上下文：`AgentConfigError(context={"role": ..., "config_path": ..., "reason": ...})`、`AgentRoleNotSupportedError(context={"role": ..., "supported_roles": ["ceo"]})`
- [ ] 消息安全性：不泄露 YAML 全文/绝对路径/堆栈
- [ ] 同步更新 `docs/architecture/sisys-uni-exception-design.md` §3.3.2 编码分配表（agent 440-449 行）
- [ ] BDD 异常路径场景纳入验收（AC-1.2 / AC-2.2 / AC-2.3）

#### API 契约 (API Contract)

- [ ] **OpenAPI 不适用**——本 Story 无 REST 端点（架构文档 §13.17.1 的 `POST /api/v1/agents/{agent_id}/execute` 是执行端点属 5.3+，MVP 不建 API 路由，所有 API 路由必须过认证中间件的成本在 Epic 7 承接）
- [ ] CLI 契约：新建独立入口 `src/interfaces/cli/agent_cli.py`（**仿 ocr_cli.py 接线模式**，勿仿 document_commands.py——后者无挂载点属未接线资产）；命令形态 `sisys-agent instantiate --role ceo`；`pyproject.toml` 的 `[project.scripts]` 与 `[tool.poetry.scripts]` 双注册 `sisys-agent = "src.interfaces.cli.agent_cli:main"`；输出 agent_id；异常经统一异常体系展示
- [ ] **角色字符串转换守卫（红线）**：CLI 层将 `--role` 字符串转 `AgentRole` 枚举时，**禁止裸 `AgentRole(value)`**（Enum 原生抛 ValueError 逃逸，违反异常红线）——必须捕获并映射为 `AgentRoleNotSupportedError`（EXCEPTION_441），`context` 携带原始输入字符串与支持列表

#### 六边形架构约束（必须遵守）

**四层架构定义与依赖方向**（同全项目约束，此处列本 Story 涉及面）：

| 层次 | 本 Story 落点 |
|------|-------------|
| domain | `value_objects/agent_config.py`、`ports/agent_repository.py`、`events/agent_events.py`（追加）、`exceptions/agent_exceptions.py`——全部零第三方依赖 |
| application | `ports/agent_config_loader.py`、`use_cases/agent_instantiation.py`——仅依赖 domain |
| infrastructure | `storage/redis/redis_agent_repository.py`、`agent_orch/yaml_agent_config_loader.py`——实现端口，不 import application/interfaces |
| interfaces | `cli/agent_cli.py`——经 `bootstrap()`+`resolve()` 解析用例，不触碰 infrastructure |

- [ ] domain 层禁止 import：yaml、redis、litellm、pydantic 等（YAML 解析严格限定在 infrastructure——core-domain §17.3.6 的 `AgentConfig(BaseModel)` 示例**不得照搬入 domain**，见偏离声明 D-2）
- [ ] 组合根 `register_port` 是唯一装配点；CLI/测试经 `Resolver().resolve(...)` 获取

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_agent_instantiation.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_agent_instantiation.py`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases + 性能 + 接线）

**R6 强制要求：** 验收测试**严格模仿** `tests/acceptance/test_acceptance_skill_data_collection.py`（结构范本，L8 自述以 postgresql 为基础演进）+ `tests/acceptance/test_acceptance_data_source.py`（场景命名与断言风格）最新范本——`# language: zh-CN` 中文 Gherkin、功能三行叙事、`背景:` 仅放服务可用性（对应 `pytest.skip` 动态跳过）、`FEATURE` 常量 + `@scenario(FEATURE, "场景名")` **显式绑定**（skill_data_collection L72/L335 先例；data_source 用 `scenarios()` 一次绑定**勿仿**）、`# ===== AC-N =====` 注释分节、场景名带 AC 编号（data_source.feature L16 `场景: AC-1.1 - ...` 风格）、context dict（`_tenant`/`_loop` 下划线基建 key + 业务裸名 key + `error`/`result` 断言入口）、`_run_async(event_loop, coro)` helper、teardown 仅清本场景租户前缀资源 + 同循环关闭 Redis 客户端。（postgresql_relational_layer 为早期范本：字面量文件名绑定、无 context dict、teardown 事务回滚、场景名无 AC 编号——仅其 Background 动态 skip 与 AC 分节注释先例被上述范本继承，**勿整体照抄**。）

> 承接说明：AC-2 的「YAML 解析失败（语法错）」路径由 Task 2 单测（tmp_path 语法错用例）承接、AC-3 的「TTL 越界」「Redis 不可达」路径由 Task 2/3/4 单测承接（见追溯矩阵），均不设独立验收场景。

**场景清单（Task 0 编写 .feature 时逐场景落地）：**

| 场景 | 覆盖 | 要点 |
|------|------|------|
| AC-1.1 实例化 CEO Agent 成功 | AC-1 | 服务级：真实组装（resolve `agent_config_loader`+`agent_repository` 两端口 + `InMemoryEventBus` 直接构造 + 手动实例化用例）→ 断言实体 role/status/agent_id |
| AC-1.2 实例化未开放角色抛异常 | AC-1 | `AgentRoleNotSupportedError` + `error.code == EXCEPTION_441` |
| AC-1.3 两次实例化相互独立 | AC-1 | agent_id 不同 + Redis 两键并存 |
| AC-2.1 加载 CEO 基础配置成功 | AC-2 | 内置 configs/agents/ceo_agent.yaml，断言字段映射 |
| AC-2.2 配置文件缺失抛异常 | AC-2 | tmp 目录无文件 → `AgentConfigError` EXCEPTION_440 |
| AC-2.3 配置字段无效抛异常 | AC-2 | role 不匹配/必填缺失 → EXCEPTION_440 |
| AC-3.1 Agent 状态持久化并可读回 | AC-3 | 键存在 + TTL>0 + 实体全字段重建一致 |
| AC-4.1 实例化发布 AgentInstantiated 事件 | AC-4 | 真实 InMemoryEventBus 直接构造注入 → published_events 断言 |
| AC-4.2 事件通道双登记 | AC-4 | yaml + DEFAULT_MAPPINGS 两处可达断言 |
| AC-5.1 实例化延迟 P95<200ms | AC-5 | 真实 Redis ≥20 采样 perf_counter |
| AC-5.2 十个并发实例化全部成功 | AC-5 | asyncio.gather(10) 全成功且键数=10 |
| AC-6.1 三端口接线可达 | AC-6 | resolve 三端口 isinstance + PortSpec 元数据 |
| AC-6.2 完成清单逐项确认 | AC-6（收尾） | Task 8 收尾场景（src/tests 完成清单 + L1-L8 接线终态断言） |

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试（`_run_async` helper）
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **文件名不含服务关键词，acceptance conftest 不会自动打 marker**——文件内显式 `pytestmark = [pytest.mark.acceptance, pytest.mark.redis]`（两 marker 均已注册于 pyproject markers；与 conftest 自动添加重复无害）+ Background 双保险动态 skip（文件内自建场景级 Redis ping+skip fixture——acceptance conftest 刻意不提供共享 `real_redis`，先例 test_acceptance_autonomous_invocation_execute.py L69-87）
- Redis 客户端**场景级独立创建、同循环 teardown 关闭**（跨循环 "Event loop is closed" 教训，见记忆 acceptance_redis_client_cross_loop_issue）
- teardown 仅 `delete_pattern(f"{tenant 前缀}:agent:*")` 本租户键，禁止全库 flush
- **Edge Cases 必须包含异常路径**（AC-1.2/2.2/2.3），错误断言 `isinstance` + `error.code` + `error.message` 非空

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（🔴 红阶段验证；**ModuleNotFoundError 为合法红**——若步骤实现文件在模块顶部 import 新模块，pytest 收集期即整文件 collection error（已实现/未实现场景一起炸，无法逐场景转绿）；**故对新模块延迟 import（步骤函数体内 import）**，使失败推迟到场景运行期逐场景呈现（合法红），逐 Task 实现后逐场景转绿，先例 test_acceptance_strategic_archive.py L107-108）
- [ ] 规范文档通过人工评审或自动化校验
- [ ] **链路接线断言清单**已定义（Epic 4 回顾行动项 7.1-1）：

**链路接线断言清单（本 Story 范围）：**

| # | 接线项 | 断言内容 | 处置 |
|---|--------|---------|------|
| L1 | `agent_repository` 端口 | 组合根 register_port 装配 + `resolve("agent_repository")` 可达且 isinstance AgentRepository | 本 Story 接线（Task 3） |
| L2 | `agent_config_loader` 端口 | 同上模式 | 本 Story 接线（Task 2） |
| L3 | `agent_instantiation_use_case` | resolve 可达 + 构造注入三依赖完整 | 本 Story 接线（Task 4） |
| L4 | `AgentInstantiated` 事件 | 发布点代码位（InstantiateAgentUseCase 内）+ yaml/DEFAULT_MAPPINGS 双登记 + InMemoryEventBus 可捕获 | 本 Story 接线（Task 1/4） |
| L5 | CLI `sisys-agent instantiate` 入口 | pyproject script 注册 + 端到端输出 agent_id | 本 Story 接线（Task 5） |
| L6 | `session_storage` 端口（1.4） | 首个消费方 | **不接线**——**Task 0 补登记** deferred-work.md（2026-10-12 普查中该条目缺席，见 Subtask 0.5），预计消费方 Story 5.3（会话状态），本 Story 用新建 AgentRepository（见决策表 DC-1） |
| L7 | `agent_engine`/`orchestration_service` agent_reasoning 链 | 引擎消费 | **不接线**——deferred 保持，属 Story 5.3 |
| L8 | AutoTriggerHandler 三 handler / 工具执行链 / RabbitMQ 消费方 / MemoryChangedHandler / ToolExecutedEventHandler | Epic 5 触发但非 5.1 范围 | **不接线**——deferred 保持（随 5.3+/消费方 Story 接线） |

> L7/L8 已在 deferred-work.md 登记确认（无需新增）；**L6 `session_storage` 当前未登记，Task 0 补登记**（见 Subtask 0.5）；Task 8 收尾时核对三条登记仍在且未误删。

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

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | AgentInstantiated 事件 | 字段/默认值/aggregate 设置/冻结性 | `tests/unit/domain/events/test_agent_events.py`（追加，若已有则并入） | Task 1 |
| **TDD 领域异常测试** | agent_exceptions | 构造/`to_dict()`/HTTP 映射(500/422)/编码唯一/子域范围 | `tests/unit/domain/exceptions/test_agent_exceptions.py` + 既有 uniqueness/code_ranges 套件 | Task 1 |
| **TDD 单元测试** | AgentConfig 值对象 | frozen/字段校验/state_ttl 范围/AgentConfigError 路径 | `tests/unit/domain/value_objects/test_agent_config.py` | Task 2 |
| **TDD 单元测试** | YamlAgentConfigLoader | 正常加载/文件缺失/解析失败/字段无效（tmp_path 注入，真实文件 IO，无 mock） | `tests/unit/infrastructure/agent_orch/test_yaml_agent_config_loader.py` | Task 2 |
| **TDD 单元测试** | RedisAgentRepository | 实体↔Hash 转换（UUID/Enum/datetime 重建）/TTL 传递（fakeredis 或 Mock 工厂 `AsyncMock(spec=...)`+`_make_*` 工厂） | `tests/unit/infrastructure/storage/redis/test_redis_agent_repository.py` | Task 3 |
| **TDD 单元测试** | InstantiateAgentUseCase | 编排顺序（加载→构建→持久化→发布）/角色限制/持久化失败传播（Mock 端口，单元层允许） | `tests/unit/application/use_cases/test_agent_instantiation.py` | Task 4 |
| **TDD 单元测试** | agent_cli CLI | parser 契约/角色字符串守卫/服务解析/输出（Mock 用例，单元层允许） | `tests/unit/interfaces/cli/test_agent_cli.py` | Task 5 |
| **TDD 契约测试** | agent_repository / agent_config_loader / agent_instantiation_use_case | 11 维度断言（参照 `test_port_contract_tool_execution_repository.py` 模式） | `tests/contracts/test_port_contract_agent_repository.py`、`test_port_contract_agent_config_loader.py`、`test_port_contract_agent_instantiation_use_case.py` | Task 2/3/4 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收（AC-1~AC-6 全场景表） | `test_acceptance_agent_instantiation.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数（模板模式） | `test_acceptance_agent_instantiation.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | 完成清单最终确认 | 同上两文件追加收尾场景 | Task 8 |
| **集成测试** | 真实 Redis 全链路 | 实例化→持久化→读回→清理（TestTenant 隔离）+ 性能（P95/并发） | `tests/integration/test_integration_agent_instantiation.py` | Task 6 |
| **SDD 架构验证** | 六边形约束 | domain 零依赖/依赖方向/YAML 限定 infrastructure/组合根唯一装配 | `tests/unit/architecture/test_arch_agent_instantiation.py` | Task 7 |

> **测试文件命名约束（记忆 feedback_no_story_number_in_filenames）：** 功能性命名，**禁止** `_5_1` 类故事编号后缀。上表文件名均已合规。

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- P0 阻断门禁
- [ ] **应用层覆盖率 ≥85%**（本 Story 核心增量层，epics TDD 要求）
- [ ] **基础设施层覆盖率 ≥75%**（RedisAgentRepository/YamlAgentConfigLoader 归入）
- [ ] **集成测试覆盖率 ≥75%**（epics TDD 要求文字项——仓库无按测试类型分列的覆盖率门禁，实际以整体≥80% + Makefile 分层门禁代偿执行，Task 8 收尾说明口径）
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
| 资源唯一性 | Redis 键经 `build_key("agent", agent_id)`——agent_id 为 uuid4 天然唯一；验收/集成再叠加 TestTenant 前缀或场景级 UUID 命名空间 |
| 外部服务隔离 | 真实 Redis 仅测试环境（`SISYS_USE_TEST_PORTS=1`→6380）；teardown 仅 `delete_pattern` 本租户键，**禁止 flush/全库 delete** |
| Redis 跨循环 | Redis 客户端**场景级独立创建、同循环 teardown 关闭**（记忆 acceptance_redis_client_cross_loop_issue）；`_run_async` 统一经 `context["_loop"]` |
| asyncio 约束 | BDD 步骤禁 `@pytest.mark.asyncio`；CLI 入口（独立进程）用 `asyncio.run()` 合法；并发测试在 async 函数内 `asyncio.gather()`；`asyncio.Lock` 若使用必须类变量 |
| Mock 边界 | **单元测试** Mock 端口（`AsyncMock(spec=Protocol)` + `_make_*` 工厂）；**集成测试**真实 Redis 优先；**验收测试禁止 mock**（InMemoryEventBus 是真实实现类，非 mock；YAML 加载用 tmp_path 真实文件） |
| bootstrap 禁令 | **验收测试禁止调用 `bootstrap()`**——组合根已由 `tests/conftest.py` session 级 `_bootstrap_once`（L20-27）完成引导；同进程二次 bootstrap 因 lambda 工厂 spec 不幂等必抛 ConflictError（registry 仅字符串 impl 幂等，实测二次调用即抛）。端口获取直接 `from src.domain.ports.resolver import resolve`；CLI 入口在独立进程内 bootstrap 合法 |
| 清理粒度 | 每个测试只清理自己创建的资源；fixture 显式声明依赖 |
| 性能测试 | `pytestmark` 标记 `benchmark`；xdist 下用 `xdist_group` 串行化计时场景避免抖动误报 |

**禁止行为：**
- ❌ 验收/集成测试 mock 领域服务/用例/仓储（真实服务优先）
- ❌ 手动 delete/truncate 全库资源
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`
- ❌ 共享 session 级 Redis 客户端跨场景复用

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 实例化 CEO Agent 实体 + 角色限制 | Task 4 | 用例编排 + 角色守卫（含 242 透传用例） | test_agent_instantiation.py（unit+acceptance） |
| AC-1 | 两次实例化独立 | Task 3/4 | uuid4 生成 + 键隔离 | test_acceptance（AC-1.3）/ test_integration |
| AC-2 | 配置加载端口与 YAML | Task 2 | AgentConfig + Loader + ceo_agent.yaml | test_agent_config.py / test_yaml_agent_config_loader.py |
| AC-2 | 配置失败异常路径 | Task 1/2 | AgentConfigError 三路径 | 同上 + test_agent_exceptions.py |
| AC-3 | Redis 持久化与读回 | Task 3/4/6 | AgentRepository 端口 + Redis 实现 + 用例编排 + 真实集成 | test_redis_agent_repository.py / test_agent_instantiation.py / test_integration_agent_instantiation.py |
| AC-3 | TTL 管理 | Task 2/3 | state_ttl 传递与范围校验（值对象边界单测 + 仓储传递） | test_agent_config.py / test_redis_agent_repository.py |
| AC-3 | Redis 不可达异常传播 | Task 3/4 | save 失败传播不返回假成功 | test_redis_agent_repository.py / test_agent_instantiation.py（unit） |
| AC-4 | AgentInstantiated 事件 | Task 1 | 事件定义 + 双登记 | test_agent_events.py |
| AC-4 | 发布点接线 | Task 4 | 用例内真实发布 | test_acceptance（AC-4.1/4.2） |
| AC-5 | P95<200ms + 并发≥10 | Task 6 | 性能集成测试 | test_integration_agent_instantiation.py |
| AC-6 | 端口契约 | Task 2/3/4 | 三端口契约测试 | tests/contracts/ 三文件 |
| AC-6 | 架构合规 + CLI 接线 | Task 5/7 | CLI 命令 + 架构测试 | test_agent_cli.py / test_arch_agent_instantiation.py |
| 收尾 | 完成清单确认 | Task 8 | 收尾验收场景 | acceptance 收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 独立完成 红→绿→变异→重构 循环，禁止将测试推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部（AC-1 ~ AC-6）

> **目的：** 在进入代码实现前，落地本 Story SDD 规范节定义的全部 Schema、端口契约、异常契约与 Gherkin，并完成红阶段验证。

- [ ] Subtask 0.1: 按「领域事件 Schema」「数据模型」「端口契约清单」「领域异常契约」四节定稿全部契约（如本 Story 已定稿，逐项核对签名/字段/编码无歧义后确认）
- [ ] Subtask 0.2: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_agent_instantiation.feature`（13 场景清单，严格模仿 data_source/skill_data_collection 最新范本 + AC 编号命名，见 R6）
- [ ] Subtask 0.3: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_agent_instantiation.py`（@scenario 显式绑定 + context dict + `_run_async` + Background 动态 skip + **新模块延迟 import** + 显式 pytestmark）
- [ ] Subtask 0.4: 运行验收测试，确认失败（🔴 红阶段验证；ModuleNotFoundError 为合法红，记录失败形态）
- [ ] Subtask 0.5: 链路接线断言清单 L1-L8 逐项确认处置（本 Story 接线 5 项 / deferred 保持 3 项）+ **补登记 deferred-work.md**：`session_storage` 端口 + RedisSessionStorage 未接线（处置：5.1 用新建 AgentRepository，见 DC-1；触发=Story 5.3 会话状态）——该条目在 2026-10-12 普查中缺席，L7/L8 已登记核对通过

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）
- [ ] deferred-work.md 补登记 L6 `session_storage` 条目（L7/L8 已登记核对通过）

---

### Task 1: 领域层——agent 异常子域 + AgentInstantiated 事件

**关联 AC:** AC-1（角色限制）、AC-2（配置异常）、AC-4（事件）

> **目的：** 落地领域契约层：异常子域（440/441）与领域事件（含双通道登记），为下游 Task 提供异常/事件词汇。

#### TDD 循环 A：agent 子域异常

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_agent_exceptions.py`（构造/context 暴露/to_dict/HTTP 映射 500 vs 422/编码 EXCEPTION_440、441；HTTP 映射断言经 `src.interfaces.api.exception_handlers._get_http_status` 反向验证，先例 test_debate_exceptions.py L188） |
| 🟢 绿 | 实现 `src/domain/exceptions/agent_exceptions.py`（模块 docstring 仿 debate_exceptions.py：编码范围/继承链理由/消息安全性） |
| 🟡 变异 | 突变 `src/interfaces/api/exception_handlers.py` `EXCEPTION_HTTP_MAP` 中 440 条目（500→502）→ HTTP 映射测试红 → 还原绿 |
| 🔄 重构 | `_code_ranges.py` 双表登记（CODE_RANGES + `_CLASS_TO_SUBDOMAIN`）+ domain `__init__.py` 导出 + exception_handlers.py `EXCEPTION_HTTP_MAP` 注册 + 同步 sisys-uni-exception-design.md §3.3.2 表；ruff+mypy |

#### TDD 循环 B：AgentInstantiated 事件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写/追加 `tests/unit/domain/events/` 中事件测试（字段默认值/aggregate_id/aggregate_type/event_type/冻结性） |
| 🟢 绿 | 在 `src/domain/events/agent_events.py` 追加 AgentInstantiated（frozen dataclass，Schema 见 Task 0）+ `events/__init__.py` 导出 |
| 🟡 变异 | 突变 `aggregate_type="Agent"` → `"AgentX"` → 断言红 → 还原绿 |
| 🔄 重构 | `configs/event_channels.yaml` + `channel_router.py DEFAULT_MAPPINGS` 双登记（对齐 AgentDecided 条目结构）；ruff+mypy |

- [ ] Subtask 1.1: 🔴 红 — 异常测试（循环 A）
- [ ] Subtask 1.2: 🟢 绿 — agent_exceptions.py 实现
- [ ] Subtask 1.3: 🟡 变异 + 🔄 重构 — 登记四处（_code_ranges/__init__/HTTP_MAP/设计文档）
- [ ] Subtask 1.4: 🔴 红 — 事件测试（循环 B）
- [ ] Subtask 1.5: 🟢 绿 — AgentInstantiated 实现
- [ ] Subtask 1.6: 🟡 变异 + 🔄 重构 — 事件双登记
- [ ] Subtask 1.7: 运行 `poetry run pytest tests/unit/domain/ -v` 全绿（含既有 8 项异常套件不回归）

**完成标准/Definition of Done:**
- [ ] 异常/事件契约实现且既有套件零回归
- [ ] `grep -r "EXCEPTION_44[01]" src/domain/exceptions/` 无碰撞
- [ ] 双登记两处 grep 可达

---

### Task 2: AgentConfig 值对象 + 配置加载端口与 YAML 实现

**关联 AC:** AC-2

> **目的：** 交付基础配置加载链：domain 值对象 + application 端口 + infrastructure YAML 加载器 + ceo_agent.yaml 资产。

#### TDD 循环 A：AgentConfig 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_agent_config.py`（frozen/必填非空/state_ttl 60~2592000 边界/越界抛 AgentConfigError EXCEPTION_440） |
| 🟢 绿 | 实现 `src/domain/value_objects/agent_config.py`（Schema 见 Task 0） |
| 🟡 变异 | 突变 ttl 上界 2592000→259200 → 边界测试红 → 还原绿 |
| 🔄 重构 | Google 风格全中文注释；ruff+mypy |

#### TDD 循环 B：YamlAgentConfigLoader + ceo_agent.yaml

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/agent_orch/test_yaml_agent_config_loader.py`（tmp_path 真实文件：正常映射/文件缺失/YAML 语法错/role 不匹配/必填缺失 → 各异常路径断言 error.code==EXCEPTION_440） |
| 🟢 绿 | 实现 `src/application/ports/agent_config_loader.py`（Protocol）+ `src/infrastructure/agent_orch/yaml_agent_config_loader.py`（`asyncio.to_thread(yaml.safe_load, ...)`，目录构造注入默认 `configs/agents/`；`capabilities.*` list→tuple 显式转换）+ 新建 `configs/agents/ceo_agent.yaml`（内容见 Task 0） |
| 🟡 变异 | 突变 role 映射键（identity.role→identity.roleX）→ 加载测试红 → 还原绿 |
| 🔄 重构 | 组合根注册 `agent_config_loader`（SINGLETON，lambda + `__import__` 延迟加载，仿 snapshot 样例）+ 契约测试 `tests/contracts/test_port_contract_agent_config_loader.py`（11 维度）；ruff+mypy |

- [ ] Subtask 2.1: 🔴 红 — 值对象测试
- [ ] Subtask 2.2: 🟢 绿 — AgentConfig 实现
- [ ] Subtask 2.3: 🟡 变异 + 🔄 重构 — 值对象收敛
- [ ] Subtask 2.4: 🔴 红 — 加载器测试（真实文件 IO，零 mock）
- [ ] Subtask 2.5: 🟢 绿 — 端口 + 实现 + ceo_agent.yaml
- [ ] Subtask 2.6: 🟡 变异 + 🔄 重构 — 组合根注册 + 契约测试
- [ ] Subtask 2.7: 内置 `configs/agents/ceo_agent.yaml` 加载冒烟（`load(AgentRole.CEO)` 成功，字段映射正确）

**完成标准/Definition of Done:**
- [ ] 配置加载三失败路径 + 成功路径全覆盖
- [ ] 契约测试通过，`resolve("agent_config_loader")` 可达（链路 L2 绿灯）
- [ ] domain 层零第三方依赖（agent_config.py 仅标准库 + AgentRole）

---

### Task 3: AgentRepository 端口 + RedisAgentRepository 实现

**关联 AC:** AC-3、AC-1（键隔离基础）

> **目的：** 交付 Agent 聚合的 Redis 仓储：端口 + 实体序列化实现 + 组合根注册。

#### TDD 循环 A：仓储端口与 Redis 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/redis/test_redis_agent_repository.py`（Mock 工厂模式：`AsyncMock(spec=...)` raw_client + `_make_agent()` 工厂；save/get/exists/delete；`_agent_to_hash`/`_hash_to_agent` 往返：UUID/AgentRole/AgentStatus/datetime 重建；TTL 传递；ttl 越界抛异常） |
| 🟢 绿 | 实现 `src/domain/ports/agent_repository.py`（Protocol，签名见 Task 0）+ `src/infrastructure/storage/redis/redis_agent_repository.py`（组合 RedisAdapter、`build_key("agent", str(agent_id))`、Hash 读写走 `raw_client`、静态转换方法仿 RedisSnapshotStore） |
| 🟡 变异 | 突变 `_hash_to_agent` 的 `AgentStatus(status_str)` 重建（改为透传 str）→ 往返断言红（`isinstance(status, AgentStatus)` 失败）→ 还原绿 |
| 🔄 重构 | 组合根注册 `agent_repository`（SCOPED，lambda 工厂 `adapter=resolver.resolve("redis_adapter")`，仿组合根 snapshot_repository 注册样例 composition_root.py L941-955）+ 契约测试 `tests/contracts/test_port_contract_agent_repository.py`；ruff+mypy |

- [ ] Subtask 3.1: 🔴 红 — 仓储单元测试（含序列化往返矩阵）
- [ ] Subtask 3.2: 🟢 绿 — 端口 + RedisAgentRepository
- [ ] Subtask 3.3: 🟡 变异 — Enum 重建突变实证（防恒真断言核心点）
- [ ] Subtask 3.4: 🔄 重构 — 组合根注册 + 契约测试 + 注释规范
- [ ] Subtask 3.5: fakeredis 快速回归（可选：`mock_redis` fixture 佐证 TTL 行为）

**完成标准/Definition of Done:**
- [ ] 序列化往返全字段一致（UUID/Enum/datetime 显式重建断言，非恒真）
- [ ] 契约测试通过，`resolve("agent_repository")` 可达（链路 L1 绿灯）
- [ ] Redis 错误不静默（连接异常向上传播为领域异常体系映射）

---

### Task 4: InstantiateAgentUseCase 应用服务 + 事件发布接线

**关联 AC:** AC-1、AC-3（编排）、AC-4（发布点）

> **目的：** 交付实例化用例编排：加载配置 → 角色守卫 → 构建实体 → 持久化 → 发布事件；完成用例端口注册。

#### TDD 循环 A：用例编排

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/use_cases/test_agent_instantiation.py`（Mock 端口：`AsyncMock(spec=AgentConfigLoader)`、`AsyncMock(spec=AgentRepository)`、InMemoryEventBus 真实类；成功编排顺序断言（加载→构建→save→publish 调用序）；非 CEO → AgentRoleNotSupportedError；配置失败传播；save 失败传播不发布事件；publish 失败（bus.publish raise）→ 结果仍返回且 `logger.exception` 记录不回滚；实体校验 `EntityValidationError`(242) 透传不包装；返回对象含 agent_id/实体） |
| 🟢 绿 | 实现 `src/application/use_cases/agent_instantiation.py` `InstantiateAgentUseCase`（构造注入 loader/repository/event_publisher；`async execute(role: AgentRole) -> AgentInstantiationResult`；`uuid.uuid4()` 显式生成 agent_id（实体无默认生成）；`responsibilities`/`domain_knowledge` 以 `list(config.xxx)` 显式转换注入实体——实体字段为 `list[str]`，tuple 直传将使读写往返类型不对称、全字段相等断言红；先持久化后发布，发布失败 `logger.exception` 记录不回滚——对齐 LangGraphEngine AgentDecided 发布先例 L84-88） |
| 🟡 变异 | 突变发布调用行（注释掉 publish）→ 「事件已发布」断言红 → 还原绿（Epic 4 零发布教训的直接防线） |
| 🔄 重构 | `AgentInstantiationResult` dataclass（agent_id + Agent 实体引用，**定稿：应用层 DTO，定义于 use_cases/agent_instantiation.py 模块内**——对齐 strategic_analysis.py L36-51 请求 dataclass 模块内定义先例，不新增 domain 文件）；组合根注册 `agent_instantiation_use_case`（SINGLETON，工厂 resolve 三依赖）+ 契约测试；ruff+mypy |

- [ ] Subtask 4.1: 🔴 红 — 用例单元测试（含编排顺序与异常传播）
- [ ] Subtask 4.2: 🟢 绿 — InstantiateAgentUseCase 实现
- [ ] Subtask 4.3: 🟡 变异 — 发布点突变实证（链路 L4 核心）
- [ ] Subtask 4.4: 🔄 重构 — 结果对象 + 组合根注册 + 契约测试 `test_port_contract_agent_instantiation_use_case.py`
- [ ] Subtask 4.5: 验收场景 AC-1.1/1.2/3.1/4.1 转绿核对（服务级真实组装：resolve `agent_config_loader`+`agent_repository` 两端口 + `InMemoryEventBus` 直接构造 + 手动实例化 `InstantiateAgentUseCase`——**不 resolve 用例端口**，其工厂注入的组合根默认 event_publisher 是 DualChannelEventBus，验收环境无 RabbitMQ；先例 test_acceptance_strategic_archive.py L126-137；遵守 bootstrap 禁令见测试隔离约束表）

**完成标准/Definition of Done:**
- [ ] 用例四步编排顺序有断言守护（非仅结果断言）
- [ ] `resolve("agent_instantiation_use_case")` 可达（链路 L3 绿灯）
- [ ] 发布点变异实证记录在案

---

### Task 5: CLI 入口 agent_cli

**关联 AC:** AC-6（接线）、AC-1（角色守卫）

> **目的：** 接口层最小入口，兑现「接收 Agent 任务命令」（R4 接口适配）；消除「已实现未接线」。
> **接线模式：** 仿 `src/interfaces/cli/ocr_cli.py`（项目唯一真实接线范本：`bootstrap()` + `resolve()` + `build_parser()` + `main(argv)->int` + pyproject script 注册）。**禁止**参照 `commands/document_commands.py`——其 parser 无任何挂载点（未接线资产），项目不存在集中式 CLI 主入口。

#### TDD 循环 A：CLI 命令

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_agent_cli.py`（build_parser 参数契约：`instantiate` 子命令 + `--role` 必填；角色字符串守卫：`"ceo"` 合法、`"cfo"`/`"xyz"` → `AgentRoleNotSupportedError` EXCEPTION_441 且 context 携带原始输入；main 成功路径输出 agent_id（注入 Mock 用例，单元层允许）；异常路径退出码非零 + 错误码展示） |
| 🟢 绿 | 实现 `src/interfaces/cli/agent_cli.py`（模块 docstring 仿 ocr_cli.py 含架构约束声明：interfaces 层不 import infrastructure、经 `bootstrap()` + `resolve("agent_instantiation_use_case")` 获取用例、`asyncio.run()` 执行；`--role` 字符串→枚举守卫：try `AgentRole(value.lower())` except ValueError → 映射 `AgentRoleNotSupportedError`，**禁止裸枚举构造导致 ValueError 逃逸**） |
| 🟡 变异 | 突变角色守卫映射（删 except 分支）→ 非法字符串测试红（ValueError 逃逸被断言捕获）→ 还原绿 |
| 🔄 重构 | `pyproject.toml` `[project.scripts]` + `[tool.poetry.scripts]` 双注册 `sisys-agent = "src.interfaces.cli.agent_cli:main"`（对齐 sisys-ocr L155-161 双段先例）；ruff+mypy |

- [ ] Subtask 5.1: 🔴 红 — CLI 单元测试（含角色守卫红线用例）
- [ ] Subtask 5.2: 🟢 绿 — agent_cli.py 实现
- [ ] Subtask 5.3: 🟡 变异 — 守卫映射突变实证（防 ValueError 逃逸防线）
- [ ] Subtask 5.4: 🔄 重构 — pyproject 双注册 + docstring 规范
- [ ] Subtask 5.5: 端到端冒烟——`poetry run sisys-agent instantiate --role ceo` 真实执行输出 agent_id，Redis 键可查（链路 L5 绿灯）

**完成标准/Definition of Done:**
- [ ] `sisys-agent` 入口注册生效、端到端可执行
- [ ] 非法/未开放角色字符串统一抛 EXCEPTION_441（无 ValueError 逃逸）
- [ ] CLI 错误展示走统一异常体系（无裸 print 堆栈）

---

### Task 6: 集成测试 + 性能验收（真实 Redis）

**关联 AC:** AC-3、AC-5

> **目的：** 真实 Redis 全链路集成验证 + 性能门禁（P95<200ms、并发≥10）。
> **性质说明：** 验证型集成/性能测试（非先红后绿循环）——被测链路已由 Task 2-4 交付，**测试编写后直接转绿为合法预期**；「红」仅指测试尚未编写，若编写后即红则暴露真实集成缺陷须修复至绿；断言活性由变异阶段（阈值突变 + Enum 重建突变）背书。

#### TDD 循环 A：集成与性能

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_agent_instantiation.py`（fixture 链：`get_test_env()` → `real_redis`（ping 失败 pytest.skip）→ 组装真实 RedisAgentRepository/Loader/InMemoryEventBus/UseCase；场景：① 实例化→键存在→读回一致→teardown delete_pattern 本租户 ② P95 计时（perf_counter，≥20 采样，`benchmark` marker + `xdist_group` 串行化）③ `asyncio.gather` 10 并发全成功键数=10） |
| 🟢 绿 | 全链路已由 Task 2-4 交付，测试应直接转绿（若红则暴露真实集成缺陷，修复至绿） |
| 🟡 变异 | 突变 P95 断言阈值（200→2）→ 性能测试红（证明计时断言活着，非恒真 sleep 通过）→ 还原绿 |
| 🔄 重构 | 场景命名收敛、超时防护（对齐 acceptance `run_with_bdd_timeout` 思路）；ruff+mypy |

- [ ] Subtask 6.1: 🔴 红 — 集成与性能测试编写
- [ ] Subtask 6.2: 🟢 绿 — 真实 Redis 全链路通过
- [ ] Subtask 6.3: 🟡 变异 — 阈值突变实证
- [ ] Subtask 6.4: 🔄 重构 — 隔离与稳定性（TestTenant/场景前缀、连续运行 5 次无随机失败）
- [ ] Subtask 6.5: 验收场景 AC-5.1/5.2 转绿核对

**完成标准/Definition of Done:**
- [ ] 真实 Redis 环境全绿（不可用时动态 skip 而非失败）
- [ ] P95<200ms 与 10 并发断言有变异实证背书
- [ ] teardown 零残留（仅本租户键清理）

---

### Task 7: SDD 架构约束验证测试

**关联 AC:** AC-6

> **性质说明：** SDD 规范验证测试（非 TDD 单元测试）——验证前序 Task 产出是否符合六边形架构规则。

#### 架构验证测试实现

- [ ] Subtask 7.1: 创建 `tests/unit/architecture/test_arch_agent_instantiation.py`
- [ ] Subtask 7.2: 验证器 A——domain 零依赖（`agent_config.py`/`agent_repository.py`/`agent_events.py`/`agent_exceptions.py` 无第三方 import，AST 或 import 扫描，参照 `test_hexagonal_architecture_constraints.py` 既有实现）
- [ ] Subtask 7.3: 验证器 B——YAML 解析边界两断言：① `src/domain/` 全目录 grep `import yaml`/`yaml.safe_load` 零命中；② Agent 配置解析链 yaml 用法仅 `yaml_agent_config_loader.py` 一处新增（**禁止断言「全仓仅命中一处」**——`src/application/skills/frontmatter.py` L22/L94 与 `event_bus_config_loader.py` 为既有合法存量，不在断言面）
- [ ] Subtask 7.4: 验证器 C——依赖方向（RedisAgentRepository 不 import application/interfaces；agent_cli 不 import infrastructure；用例仅依赖 domain + application 端口）
- [ ] Subtask 7.5: 验证器 D——组合根唯一装配（`RedisAgentRepository`/`YamlAgentConfigLoader`/`InstantiateAgentUseCase` 在 src/ 下仅 composition_root.py 与测试中实例化；**属新增断言形态**——现有架构测试无同等先例，用 rglob 全仓扫描类名实例化实现，扫描技术参照 test_arch_data_source.py）
- [ ] Subtask 7.6: 循环依赖检测用 ruff/isort（不引入 pylint）
- [ ] Subtask 7.7: 运行完整测试套件并生成报告（含本 Story 全部测试文件清单核对）

**完成标准/Definition of Done:**
- [ ] 所有架构约束测试通过，任何违规导致测试失败
- [ ] 输出清晰合规报告
- [ ] 循环依赖检测不引入额外工具

---

### Task 8: 开发结束验收测试

**关联 AC:** 全部收尾

> **性质说明：** Story 收尾最终验收——src 与 tests 四目录完成清单逐项确认，确保进入 `done` 前无遗漏。收尾场景为验证型测试：断言对象此时均已存在，**编写后直接转绿为合法预期**，断言活性由变异（文件名突变）背书。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 acceptance 收尾场景（AC-6.2 完成清单逐项确认） |
| 🟢 绿 | BDD 步骤实现（文件存在性/关键符号/接线 grep 断言） |
| 🟡 变异 | 突变一处预期文件名（改为不存在路径）→ 收尾场景红 → 还原绿 |
| 🔄 重构 | 场景命名与断言表达收敛 |

- [ ] Subtask 8.1: 场景 1 — 验证 `src` 完成清单（value_objects/ports/events/exceptions/application/infrastructure/cli/composition_root 九处产出逐项确认）
- [ ] Subtask 8.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单（测试分类表全文件逐项确认）
- [ ] Subtask 8.3: 链路接线断言清单 L1-L8 终态核对（L1-L5 绿灯实证、L6-L8 deferred-work.md 登记仍在且未误删——含 Task 0 补登记的 `session_storage` 条目）
- [ ] Subtask 8.4: 运行 `poetry run pytest tests/`、`poetry run ruff check src/ tests/`、`poetry run mypy src/` 收尾校验
- [ ] Subtask 8.5: 更新 sprint-status.yaml（5-1 → review）；同步设计文档偏离项（D-1/D-2 的文档更新动作，见 Dev Notes 偏离声明；D-3 无文档动作、D-4/D-5 不改 epics）
- [ ] Subtask 8.6: 验收场景全量转绿核对（13 场景逐一绿——补齐 Task 2/3/5 未显式核对的 AC-1.3 / AC-2.1 / AC-2.2 / AC-2.3 / AC-4.2 / AC-6.1）

**完成标准/Definition of Done:**
- [ ] src 与 tests 完成清单逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] 三项质量门禁全绿
- [ ] Story 可进入 `review`/`done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ DDD 聚合（Agent 实体为聚合根）+ 组合根 DI（PortSpec/Registry/Resolver/ContractGate）
- **设计约束:** domain 零外部依赖（import-linter 强制）；infrastructure 实现 domain/application 端口；所有装配经 `src/composition_root.py`
- **接口治理:** 统一端口注册（name/version/interface/impl/module/lifetime/owner/compatibility/tags/deprecated）、契约优先、版本化兼容、禁止跨模块直接依赖实现类
- **技术栈:** Python 3.11+ / redis-py async / PyYAML（仅 infrastructure）/ pytest-bdd 8.x / pytest-xdist
- **Agent 架构定位:** architecture.md §2 拓扑——应用层 AgentUC → 领域层 Agent 实体/AgentService/AgentRepo → 基础设施层 LangGraph 引擎与 Agent 协作图；§17.4 AGENT 架构 7 角色 + SYS（本 Story 仅 CEO 实例化，不实现编排）
- **实例化流程权威描述:** architecture.md §11.2.4「会话初始化 → 加载系统级 MEMORY.md → 加载 Agent 配置集 → Agent 实例化 → 合并上下文 → 任务执行 → Checkpoint → 持久化」——**本 Story 仅覆盖「加载基础配置 + Agent 实例化 + 状态持久化」三步**，MEMORY.md/身份档案（5.2）、任务执行（5.3）、Checkpoint（5.10）为后续 Story

### 关键架构决策

| # | 决策点 | 选定方案 | 备选方案（弃用理由） | 依据 |
|---|--------|---------|---------------------|------|
| DC-1 | Agent 状态持久化通道 | **新建 `AgentRepository` 端口 + `RedisAgentRepository`**（键 `sisys:agent:{agent_id}`，仿 RedisSnapshotStore） | 复用 `SessionStorage`（弃用：session_id 主键语义不匹配聚合仓储；其吞连接异常的优雅降级语义与「状态持久化确定性」冲突；架构文档 §13.2 明确规划 agent_repository.py、§13.17.3 Redis 键含 agent_state） | architecture.md §13.2/§13.17.3；R1 领域层统一抽象基础端口 |
| DC-2 | Agent 状态机模型 | **复用现有 `AgentStatus` 五态**（IDLE/RUNNING/WAITING/COMPLETED/FAILED） | core-domain §17.3.2 六态含 CHECKPOINTED（弃用：CHECKPOINTED 属 CheckpointWithEvaluation 即 Story 5.10；现有实体状态机已含守卫且有测试，改动属回归风险） | 代码现状 `src/domain/entities/agent.py`；偏离声明 D-1 |
| DC-3 | 基础配置体系 | **YAML 最小子集**（`configs/agents/ceo_agent.yaml`，core-domain §17.3.6 schema 裁剪） | a) `.md` 七档案（弃用：FR-AC-02 属 Story 5.2，5.1 明确边界）；b) 全量 §17.3.6 schema（弃用：communication/principles/prompts 及 `id` 字段等无 5.1 消费方，YAGNI——配置身份键为 `identity.role`，`id` 字段裁剪不入 YAML） | prd.md FR-AC-01/FR-AC-02 边界；epics 5.1/5.2 划分 |
| DC-4 | 实例化事件 | **新增 `AgentInstantiated`（reliable 单通道）** | 不发事件（弃用：Agent 生命周期可观测是 5.6 隔离日志/5.7 Phoenix 追踪的基础；审计合规型事件与 AgentDecided 同族） | architecture.md §10.1 事件审计定位；AgentDecided 通道先例 |
| DC-5 | 异常子域 | **新建 agent 子域 440-449**（440/441 两个异常平铺，不设子域基类） | 复用 entity/business 通用异常（弃用：配置资产错误与角色限制语义无法由 242/243 精确表达，监控无法精确告警） | `_code_ranges.py` 独立段先例（data_source/debate/tool_version）；debate 继承链先例 |
| DC-6 | 入口形态 | **CLI 独立入口**（`sisys-agent instantiate --role ceo`，agent_cli.py 仿 ocr_cli.py + pyproject script 注册） | a) REST API（弃用：架构文档执行端点属 5.3+，且 API 强制认证中间件成本由 Epic 7 承接）；b) 纯服务无入口（弃用：违反 Epic 4「未接线 ≠ done」团队协议，用例将成为第 51 个休眠端口）；c) document_commands.py 式 subparsers（弃用：该文件 parser 无挂载点，属未接线资产，照抄即制造死代码） | NFR-IF-01（CLI 覆盖 agent 模块）；ocr_cli.py 唯一真实接线先例 |
| DC-7 | AgentConfig 加载器层归属 | **domain 纯 dataclass + application 端口 + infrastructure YAML 解析** | core-domain §17.3.6 的 `AgentConfig(BaseModel)+from_yaml`（弃用：Pydantic 入 domain 违反零依赖硬约束，CI 必挂） | CLAUDE.md Hard Constraints；偏离声明 D-2 |
| DC-8 | TTL 收敛 | **state_ttl 默认 86400，范围 60~2592000，配置可覆盖** | 三处文档不一致值（24h-30d / 3600 / 86400）——以 SessionStorage 默认 86400 为基准收敛，范围数字对齐 RedisSnapshotStore `set_ttl`（其抛 ValidationError(201)；本 Story 异常类型为 AgentConfigError(440)——**仅对齐范围数字，不对齐异常类型**） | architecture.md §11.2.5；core-domain §17.3.6；SessionStorage 默认值 |

### 设计文档偏离声明

> 90-8 先例机制：实施与设计文档冲突时显式声明，实施后同步更新文档。

| # | 冲突点 | 偏离内容 | 实施后同步动作 |
|---|--------|---------|---------------|
| D-1 | core-domain §17.3.2 六态 AgentState（含 CHECKPOINTED） | 采用代码五态 AgentStatus | Task 8 在 core-domain-design.md §17.3.2 补注「CHECKPOINTED 延至 5.10，五态为 MVP 事实标准」 |
| D-2 | core-domain §17.3.6 `AgentConfig(BaseModel)` + `from_yaml()` | domain 纯 dataclass；Pydantic/YAML 全部下沉 infrastructure | Task 8 在 §17.3.6 补注层归属修正 |
| D-3 | architecture.md §11.2.4 实例化含 MEMORY.md/七档案加载 | 5.1 仅基础配置（YAML）；`.md` 档案属 5.2（FR-AC-02） | 无需改文档（Story 边界划分，非设计冲突），在 5.2 Story 引用即可 |
| D-4 | epics_v1.0.md L2030 将 5.3 描述为「CEO Agent 实例化」 | 系 epics 笔误（5.3 实为单 Agent 工作流） | 不修改 epics（历史规划文档）；dev agent 勿据此误解范围 |
| D-5 | epics_v1.0.md Story 5.1 建议测试路径 `tests/unit/architecture/test_agent_instantiation.py`、`tests/integration/test_agent_instantiation_integration.py` | 以项目实际目录结构为准（本 Story 测试分类表的全套路径）——epics 建议路径未对齐项目 tests/ 实际组织（unit 下按层分目录、integration 无 `_integration` 后缀惯例、架构测试命名 `test_arch_*`） | 不修改 epics；dev 以本 Story 测试分类表为准 |

### 关键代码模式参考

**组合根注册样例（snapshot_repository，`src/composition_root.py:941-955`）——Task 2/3 照抄结构：**

```python
register_port(
    name="agent_repository",
    version="v1.0.0",
    interface=AgentRepository,
    impl=lambda resolver: __import__(
        "src.infrastructure.storage.redis.redis_agent_repository",
        fromlist=["RedisAgentRepository"],
    ).RedisAgentRepository(
        adapter=resolver.resolve("redis_adapter"),
    ),
    module="src.infrastructure.storage.redis.redis_agent_repository",
    lifetime=Lifetime.SCOPED,
    owner="platform",
    tags=("redis", "agent"),
)
```

**AgentDecided 事件模板（`src/domain/events/agent_events.py:15-36`）——AgentInstantiated 照抄结构：** frozen dataclass；`agent_id: uuid.UUID = field(kw_only=True)`；`__post_init__` 设 `aggregate_id`/`aggregate_type="Agent"`；`event_type` 默认字段放置位置与同文件既有事件对齐。

**事件通道登记（`configs/event_channels.yaml:177-180`）——照抄结构：**

```yaml
  AgentInstantiated:
    rabbitmq_routing_key: "sisys.events.reliable.agent_instantiated"
    delivery_mode: "reliable"
    description: "Agent实例化完成"
```

（同步 `src/infrastructure/messaging/channel_router.py` `DEFAULT_MAPPINGS`，对齐 L231 AgentDecided 条目。注意实际路径是 `configs/`，CLAUDE.md 中 `config/` 为过时写法。）

**实体↔Hash 序列化模式（`RedisSnapshotStore`）——RedisAgentRepository 照抄：** 静态 `_agent_to_hash`（UUID→str、Enum→.value、datetime→isoformat、tuple→json_dumps）/ `_hash_to_agent`（显式重建 `AgentRole(v)`/`AgentStatus(v)`/`datetime.fromisoformat(v)`；`responsibilities`/`domain_knowledge` 重建为 `list[str]` 与实体类型一致）；写入形态：`hset(build_key("agent", str(agent_id)), "latest", json_dumps(hash_dict))` + `expire(key, ttl)`——**单 field JSON blob**（RedisSnapshotStore L116-117 形态，非逐 field Hash）；`json_loads` 不还原类型是**调用方重建责任**。

**验收测试骨架（data_source + skill_data_collection 最新范本）——R6 强制：** `FEATURE` 常量 + `@scenario(FEATURE, "场景名")` 显式绑定；`context` fixture（`_tenant`/`_loop`）；`_run_async` helper；Background given 内 `pytest.skip(f"Redis not available: {exc}")`；异常断言 `isinstance(context["error"], AgentRoleNotSupportedError)` + `error.code == "EXCEPTION_441"`。

**单元测试 Mock 工厂模式（`tests/unit/application/services/test_tool_execution_engine_datasource.py`）：** `_StubAdapter` 实现 Port 契约、`AsyncMock()` + `side_effect` 阶段化分发、`pytest.raises(X) as exc_info` + `exc_info.value.code`/`exc_info.value.context.get(...)` 断言。

**CLI 独立入口模式（`src/interfaces/cli/ocr_cli.py`，注册样例 `pyproject.toml` L155-161）：** `bootstrap()` + `from src.domain.ports.resolver import resolve` + `build_parser()` + `main(argv) -> int` + `asyncio.run()`；模块 docstring 首部含架构约束声明。⚠️ `commands/document_commands.py` 的 `build_version_parser` 全仓无挂载点（未接线资产）——不存在「CLI 主入口」可挂载，勿照抄其 subparsers 模式。

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** Epic 4 回顾（`epic-4-retro-2026-10-12.md`、`epic-4-retro-2026-10-13-datasource.md`）+ deferred-work.md 普查 + Story 4-1f/90-8

**关键学习/Key Learnings:**
- **7.1-1 链路接线断言（P0）**：事件零发布/装配断线贯穿 Epic 4 六个 Story（4-3 核心价值未装配、4-6 三事件零发射、4-7 SessionMiddleware 休眠）——Task 0 链路清单 + Task 8 终态核对是强制项
- **7.1-2 变异实证（P0）**：8/13 Story 存在恒真断言——每个 TDD 循环的 🟡 变异阶段不可跳过（尤其 Enum 重建、事件发布、P95 阈值三处）
- **7.1-3 未接线组件登记**：「配置了但未生效」零容忍——本 Story L6-L8 不接线项必须保持 deferred-work.md 登记
- **团队协议**：「Done = 接线生效 + 资产在库」；「真实服务烟雾是新引擎功能验收门禁」——本 Story 实例化路径**零 LLM 调用**（显式声明：LLM 烟雾门禁不适用，LLM 调用始于 5.3；7.1-4 LLM mock 分派键规则同理不适用）
- **Redis 跨循环教训**：session 级共享客户端跨场景抛 "Event loop is closed"——场景级独立创建 + 同循环关闭
- **枚举加值须全仓 grep 断言位**（retro「六、关键洞察」第 5 条）：本 Story 不给 AgentRole 加值（八角色已全），但新增 AgentStatus 消费方时注意既有 `tests/unit/domain/entities/test_agent.py` 断言不回归
- **文档审查最高价值是「可满足性推演」**：场景期望唯一性/时间线终态/Task 依赖干跑（retro「六、关键洞察」第 4 条）

**应用到本故事/Applied to This Story:**
- [ ] 链路接线断言清单 L1-L8 全程跟踪（Task 0 定义 → Task 8 终态）
- [ ] 每个 TDD 循环含 🟡 变异阶段（模板已强制）
- [ ] 验收测试每个 then 步骤有真实断言（模板较老文件有 `pass` 占位——**禁止效仿**，data_source/skill_data_collection 最新风格为准则）
- [ ] 验收禁 mock：InMemoryEventBus 是真实实现类（非 mock），YAML 用 tmp_path 真实文件
- [ ] deferred 处置透明化（L6-L8 保持登记，不静默扩大范围）

### deferred-work 处置（Epic 5 触发项分流）

> Epic 4 回顾普查：生产活代码 50/166 端口。以下「触发=Epic 5」的休眠资产在本 Story 的处置：

| 休眠资产 | 5.1 处置 | 预计接线 |
|---------|---------|---------|
| `session_storage` 端口 + RedisSessionStorage | **不接线**（5.1 用 AgentRepository，见 DC-1） | Story 5.3（会话状态） |
| `agent_engine`/`LangGraphEngine`/`orchestration_service` agent_reasoning 链 | 不接线（引擎消费属工作流） | Story 5.3 |
| AutoTriggerHandler 三 handler / heartbeat_scheduler / session_namespace_manager | 不接线 | Story 5.3+ |
| 工具执行链（tool_execution_service/engine、red_blue、sandbox 链、12 个 data_source 适配器） | 不接线 | Story 5.3+/5.12 |
| RabbitMQ 消费方（RabbitMQConsumer/EventListener/EventBusFactory） | 不接线（本 Story 事件只发不收） | 首个消费方 Story |
| MemoryChangedHandler / ToolExecutedEventHandler | 不接线 | 随消费方 |
| langgraph retry/timeout 字段未消费 | 不接线 | Story 5.10/6.6 |

**原则：本 Story 只接线自己的五项（L1-L5），不为「顺手」扩大范围——扩大范围须经 deferred-work.md 台账决策。**

### 项目结构说明 Project Structure

```
src/
├── composition_root.py                                  # [修改] 注册 3 新端口
├── domain/
│   ├── events/agent_events.py                           # [修改] 追加 AgentInstantiated
│   ├── exceptions/agent_exceptions.py                   # [新建] 440/441（含 docstring 契约说明）
│   │   └── （_code_ranges.py / __init__.py 随之修改）
│   ├── ports/agent_repository.py                        # [新建] AgentRepository Protocol
│   ├── value_objects/agent_config.py                    # [新建] AgentConfig frozen dataclass
│   └── entities/agent.py                                # [参考] 复用不修改
├── application/
│   ├── ports/agent_config_loader.py                     # [新建] AgentConfigLoader Protocol
│   └── use_cases/agent_instantiation.py                 # [新建] InstantiateAgentUseCase
├── infrastructure/
│   ├── agent_orch/yaml_agent_config_loader.py           # [新建] YamlAgentConfigLoader
│   └── storage/redis/redis_agent_repository.py          # [新建] RedisAgentRepository
└── interfaces/cli/agent_cli.py                         # [新建] sisys-agent 独立入口（仿 ocr_cli.py）
configs/
├── agents/ceo_agent.yaml                                # [新建] CEO 基础配置资产
└── event_channels.yaml                                  # [修改] AgentInstantiated 登记
pyproject.toml                                           # [修改] sisys-agent script 双注册（L155-161 两段）
tests/
├── unit/
│   ├── domain/{events/test_agent_events.py,             # [新建/追加]
│   │           exceptions/test_agent_exceptions.py,     # [新建]
│   │           value_objects/test_agent_config.py}      # [新建]
│   ├── application/use_cases/test_agent_instantiation.py# [新建]
│   ├── infrastructure/{agent_orch/test_yaml_agent_config_loader.py,
│   │                    storage/redis/test_redis_agent_repository.py}  # [新建]
│   ├── interfaces/cli/test_agent_cli.py                 # [新建]
│   └── architecture/test_arch_agent_instantiation.py    # [新建]
├── contracts/（test_port_contract_agent_repository.py 等 3 个）# [新建]
├── integration/test_integration_agent_instantiation.py  # [新建] 真实 Redis + 性能
└── acceptance/test_acceptance_agent_instantiation.{feature,py} # [新建]
```

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (glm-5.3) |
| **Version** | create-story workflow v6.3.0 |
| **Execution Date** | 2026-10-14 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Template** | `docs/developer/story-template.md`（`.claude/skills/bmad-create-story/template.md` 符号链接） |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Epic 5 头部 + Story 5.1 节 L1420-1496） |
| **架构文档** | `docs/architecture/architecture.md`、`sisys-core-domain-design.md` §17.3、`sisys-workflow-agent-integration-design.md` |
| **需求** | `_bmad-output/planning-artifacts/prd.md` FR-AC-01/NFR-PERF-04/NFR-IF-02 |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **调研输入** | 5 并行调研 Agent 报告（agent_orch 代码现状 / Redis-LLM 基础设施 / 验收测试模板 / 架构文档 / 前序 Story 经验）+ 全仓 grep 核验 |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` Story 5.1 提取（含 prd.md FR-AC-01 与 NFR 指标交叉验证）
- [x] 架构约束从 architecture.md / core-domain-design.md §17.3 / workflow-agent-integration-design.md 提取
- [x] 现有代码继承清单完成（5 并行 Agent 全仓调研 + 人工核验目录/类名/行号）
- [x] 前一个故事学习经验整合（Epic 4 回顾 7.1-1/7.1-2/7.1-3 + 团队协议 + deferred-work 分流）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（含链路接线断言清单与变异阶段）
- [x] 项目结构对齐统一规范（R1/R2/R4 层归属 + 命名先例核验）
- [x] 验收测试规范对齐模板（R6：data_source + skill_data_collection 最新范本 + AC 编号风格；R1 审查修正模板指向）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/5-1-ceo-agent-instantiation-mvp.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- 见「项目结构说明」全部 [新建] 项（src 8 处 + configs 1 处 + tests 14 处：unit 8 + contracts 3 + integration 1 + acceptance 2）

**待修改的文件/To Be Modified:**
- `src/composition_root.py`（3 端口注册）
- `pyproject.toml`（`[project.scripts]` + `[tool.poetry.scripts]` 双注册 `sisys-agent`，L155-161 两段）
- `src/domain/events/agent_events.py` + `events/__init__.py`（AgentInstantiated）
- `src/domain/exceptions/_code_ranges.py` + `__init__.py`（agent 子域 440-449）
- `configs/event_channels.yaml` + `src/infrastructure/messaging/channel_router.py`（双登记）
- `docs/architecture/sisys-uni-exception-design.md` §3.3.2（编码表 agent 行）
- `docs/architecture/sisys-core-domain-design.md` §17.3.2/§17.3.6（偏离声明 D-1/D-2 落注，Task 8）
- `_bmad-output/implementation-artifacts/deferred-work.md`（Task 0 补登记 `session_storage` 条目）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 5.1 |
| **Story Key** | 5-1-ceo-agent-instantiation-mvp |
| **File** | `_bmad-output/implementation-artifacts/stories/5-1-ceo-agent-instantiation-mvp.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 5: Agent 协作系统（🔑 入口 Story，P0-1） |
| **价值组** | 单 Agent 战略规划能力 |
| **优先级** | P0（FR-AC-01） |
| **覆盖 FR** | FR-AC-01；关联 NFR-PERF-04（并发≥10）、NFR-IF-01（CLI 覆盖 agent 模块，DC-6 依据）、NFR-IF-02（启动上下文，5.2 消费） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-8，每 Task 含完整 TDD 循环）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-6 + 13 Gherkin 场景）
3. [x] Architecture constraints extracted 架构约束已提取（R1/R2/R4 层归属 + 偏离声明 D-1~D-5）
4. [x] Previous story learnings integrated Epic 4 回顾教训已整合（7.1-1/7.1-2/7.1-3 + 团队协议）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | `EXCEPTION_HTTP_MAP` 登记位置失实：不在 domain/exceptions/__init__.py，实际在 `src/interfaces/api/exception_handlers.py` L130-262（domain 层零 HTTP 关注点） | P0 | 领域异常契约检查项 + Task 1 变异/重构两行改为指明 interfaces 层 Map 位置与 debate L253-255 条目形态；HTTP 映射单测经 `_get_http_status` 反向验证（先例 test_debate_exceptions.py L188） |
| 2 | 「YAML 解析仅存在于 infrastructure」断言会误伤 `src/application/skills/frontmatter.py` L22/L94（application 层既有合法存量） | P0 | AC-6 验证标准与 Subtask 7.3 断言收窄为「`src/domain/` 全目录零 yaml + Agent 配置解析链仅新增于 yaml_agent_config_loader.py」，显式禁止「全仓仅命中一处」表述 |
| 3 | `session_storage` 在 deferred-work.md 实际未登记（L6「已登记无需新增」声称不成立，其余 6 类属实） | P0 | L6 处置/Subtask 0.5/Task 0 DoD 改为「Task 0 补登记」；Subtask 8.3 与待修改清单同步 |
| 4 | R6 验收模板指向错误：postgresql_relational_layer 是早期范本（字面量绑定/无 context dict/事务回滚 teardown/无 AC 编号），所列特征实来自 data_source + skill_data_collection；且 data_source 用 `scenarios()` 绑定与「显式绑定」要求冲突 | P0 | R6 整段重写：结构范本 skill_data_collection（FEATURE 常量 + @scenario 显式绑定）、场景命名与断言风格 data_source（AC 编号场景名），postgresql 仅 Background 动态 skip 先例被继承；Subtask 0.2/验收骨架/L928 连带修正 |
| 5 | InMemoryEventBus 未注册端口（组合根 `event_publisher` 默认 impl 是 DualChannelEventBus），「Resolver resolve 三端口 + InMemoryEventBus 注入」组装自相矛盾；验收环境无 RabbitMQ | P1 | 复用表/Subtask 4.5/场景 AC-1.1 统一改为「resolve 两基础设施端口 + InMemoryEventBus 直接构造 + 手动实例化用例」（strategic_archive L126-137 先例） |
| 6 | `bootstrap()` 同进程二次调用必抛 ConflictError（lambda spec 不幂等，实测复现） | P1 | 测试隔离约束表新增「bootstrap 禁令」行：验收测试禁止调用 bootstrap（session 级 `_bootstrap_once` 已引导），端口直接 resolve |
| 7 | Task 6/8 的「🔴 红」结构性不可达（验证型测试，实现已存在直接转绿）与 TDD 循环约束自相矛盾 | P1 | Task 6/8 增加性质说明（对齐 Task 7 先例）：直接转绿为合法预期，断言活性由变异阶段背书 |
| 8 | 「发布失败记 warning」失实：LangGraphEngine L84-88 实为 `logger.exception`（ERROR 级） | P1 | AC-4/Task 4 绿行改为 `logger.exception` 记录不回滚 |
| 9 | TTL 校验位置（在 set_ttl 非转换方法）与异常类型（ValidationError(201) 非 440）捆绑表述有照抄风险；DC-8「对齐」无限定语 | P1 | 复用表 RedisSnapshotStore 行与 DC-8 明确「仅对齐范围数字 60~2592000，不对齐异常类型」 |
| 10 | 验收侧 `real_redis` fixture 不可用（仅 integration conftest 有；acceptance 刻意无共享 fixture） | P1 | 复用表与 BDD 约束注明「验收文件内自建场景级 Redis ping+skip fixture」（autonomous_invocation_execute L69-87 先例） |
| 11 | L351 延迟 import 因果颠倒（「收集期报错是预期，故延迟 import」矛盾） | P1 | 重写为「延迟 import 使失败推迟到场景运行期，避免收集期整文件 collection error 炸掉已实现场景」 |
| 12 | `execute(role="ceo")` 与端口签名 `execute(role: AgentRole)` 不一致；YAML `agent.id` 无 dataclass 映射与「映射完整」矛盾；L31「AgentConfig 引用 LLMConfig」错误归因（LLMConfig 无 preferred_model） | P1 | L82 改 `execute(role=AgentRole.CEO)`；YAML 删除 `agent.id` 行（DC-3 补 YAGNI 裁剪说明）；L31 改「preferred_model 纯 str 预留，不引用 LLMConfig 类型」 |
| 13 | 内部一致性缺陷 18 处：待修改清单漏 pyproject.toml、偏离声明计数 D-1~D-4 应为 D-1~D-5（两处）、Subtask 8.5 误含 D-3、R3 未定义、`AgentInstantiationResult` 归属未定稿、11 维度枚举只列 10 项、pyproject 行号 L156-161/L155-161 不统一、L942 指称歧义、configs 计数（1 新建+1 修改）、矩阵 AC-3 缺「Redis 不可达」行、转绿核对仅 7/13 场景、AC-2 解析失败与 AC-3 TTL 越界无承接说明、NFR-IF-01 未入覆盖行、§6.4/§6.5 非字面章节号、Epic 5 行号范围、Subtask 7.5 无先例注记、覆盖率「集成测试≥75%」无执行口径、`-n 8` 出处 | P2 | 逐项修正：补 pyproject 行/改为 D-1~D-5/8.5 改 D-1/D-2/R1-R4 改 R1/R2/R4/结果 DTO 定稿应用层/枚举补全/行号统一 L155-161/指称统一 composition_root.py L941-955/计数修正/矩阵补行与 Task 归属补全/新增 Subtask 8.6 全场景转绿核对/场景表前加承接说明/IF-01 入覆盖行/改「retro 六、关键洞察第 4/5 条」/Epic 行号范围限定/7.5 注明新增断言形态/覆盖率口径注明代偿机制 |

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** （待实施后审查）
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor）

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

**故事版本/Story Version:** v1.1.0
**创建日期/Created:** 2026-10-14
**最后更新/Last Updated:** 2026-10-14
**更新说明/Description:**
- v1.0.0: 创建故事文件（5 并行调研 Agent 全仓代码/文档/模板/经验调研 + 人工事实核验；含链路接线断言清单 L1-L8、8 项关键架构决策 DC-1~DC-8、4 项偏离声明 D-1~D-4、deferred-work 分流处置）
- v1.1.0: Round 1 审查修订（正确性视角：5 并行调研 Agent 代码事实核对 + 3 并行审查 Agent 对抗复核/一致性/遗漏扫描；修复 P0×4（EXCEPTION_HTTP_MAP 定位、YAML 断言误伤、session_storage 缺登记、验收模板指向）+ P1×8 + P2×18，详见「文档审查修复」表）
