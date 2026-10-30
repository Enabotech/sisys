# Story 5.1: CEO Agent 实例化（MVP 单 Agent）

**Status:** `done`

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
| 测试基建：`get_test_env()`/`SISYS_USE_TEST_PORTS=1`（Redis 6380）、`TestTenant.redis_key_prefix`、`real_redis` fixture（**仅 integration conftest 有**——acceptance 侧刻意不提供共享 fixture，验收文件内自建场景级异步客户端模板 = skill_data_collection L82-113 context fixture：`aioredis.Redis(decode_responses=True)` + Background ping+skip + 同循环 close）、acceptance conftest 自动 marker | `tests/environments.py`、`tests/isolation.py`、`tests/integration/conftest.py`、`tests/acceptance/conftest.py`、`tests/acceptance/test_acceptance_skill_data_collection.py` | **直接复用** |
| 值对象内抛子域异常先例（校验方法 raise 领域异常，非 ValueError） | `src/domain/value_objects/document_metadata.py` L100-104（MetadataValidationError 217） | **参考**（AgentConfig `__post_init__` 抛 AgentConfigError 440 同款路线；VO 主流是 242，见领域异常契约节边界说明） |

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
**Then** 经 `AgentRepository` 端口将 Agent 实体完整持久化至 Redis（键 `sisys:agent:{agent_id}`，Redis Hash **单 field `latest` 承载全字段 JSON blob**——`hset` 与 `expire` 经 **MULTI/EXEC pipeline 原子提交**（R1-F3 修复：两命令分离的崩溃窗口会留下无 TTL 孤儿键，击穿「非幂等 + TTL 自然回收」假设；语义仿 RedisSnapshotStore L116-117 形态，非逐 field Hash）
**And** `get_by_id(agent_id)` 读回的实体与原实体字段完全一致（UUID/Enum/datetime 显式序列化与重建——`json_loads` 不还原类型，必须手动重建 `AgentRole`/`AgentStatus`/datetime）
**And** 持久化带 TTL（`save(agent, ttl)` **必填参数**，用例从 `AgentConfig.state_ttl` 显式传入——值对象默认 86400 是唯一默认值真源，仓储签名无默认值避免双真源；仓储防御性校验范围 60~2592000，越界抛 `AgentConfigError`（EXCEPTION_440））
**And** 持久化失败（Redis 不可达）抛领域异常，**禁止静默吞异常**（与 `RedisSessionStorage` 的优雅降级语义刻意区分）

**验证标准/Validation Criteria:**
- [ ] Redis 中键 `sisys:agent:{agent_id}` 存在且 TTL > 0
- [ ] 读回实体 `role/status/created_at` 等全字段与写入一致（Enum/datetime 重建正确）
- [ ] `ttl` 越界（<60 或 >2592000）→ `AgentConfigError`（EXCEPTION_440，配置参数越界语义；`AgentConfig.__post_init__` 校验为主，仓储层防御性二次校验同异常）
- [ ] Redis 不可达时用例抛异常退出（不返回假成功；仓储层包装为 `StorageError`——对齐 RedisSnapshotStore.save L126-128 先例，连接类故障不落入 440/441 语义）

### AC-4: 实例化发布 AgentInstantiated 领域事件

**Given** Agent 实体持久化成功
**When** 实例化用例完成
**Then** 发布 `AgentInstantiated` 领域事件（frozen dataclass，`agent_id`/`role`/`name`/`config_version`，`aggregate_type="Agent"`；RELIABLE 模式经 RabbitMQ **via Outbox**——组合根 `event_publisher` 默认实现 DualChannelEventBus 的 RELIABLE 分支调 RabbitMQEventBus.publish → `outbox_repo.save(event)`（rabbitmq_event_bus.py L57），生产路径自动获得 Transactional Outbox 保证，非「直接发布」）
**And** 事件在 `configs/event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` **双登记**（reliable 通道，routing key `sisys.events.reliable.agent_instantiated`，对齐 AgentDecided 先例）
**And** 发布点在 `InstantiateAgentUseCase` 内真实调用（Epic 4 教训：事件零发布是 P0 重灾区——发布点代码位 + 订阅方可达必须进入链路接线断言清单）

**验证标准/Validation Criteria:**
- [ ] 验收测试用真实 `InMemoryEventBus` 注入用例，断言 `published_events` 含 `AgentInstantiated` 实例且字段正确
- [ ] `configs/event_channels.yaml` 与 `channel_router.py DEFAULT_MAPPINGS` 均含 AgentInstantiated（两处 grep 可达）
- [ ] 事件发布失败不中断实例化结果返回？——**按 AgentDecided 先例**：发布失败记日志不回滚业务状态（对齐 run_tool_chain L180-185 用例先例 `logger.error(exc_info=True)`），但持久化成功是发布前提（先持久化后发布——Agent 聚合在 Redis、发件箱在 PG **跨存储无 ACID**，此序保证「无持久化即无事件」（无幽灵事件），反向丢失（持久化成功、发件箱写失败）降级为日志）

### AC-5: 性能指标

**Given** 真实 Redis 服务可用（`SISYS_USE_TEST_PORTS=1` → 6380 端口）
**When** 执行实例化全链路（配置加载 → 实体构造 → Redis 持久化 → 事件发布）
**Then** 实例化延迟 **P95 < 200ms**（≥20 次采样取 P95，`time.perf_counter` 计时 + **warmup 剔除 1 次** + `statistics.quantiles(latencies, n=20)[18]` 取 P95——先例 `tests/acceptance/test_acceptance_docker_sandbox.py` L1001-1012（⚠️ 与 `tests/benchmark/test_performance_docker_sandbox.py` 是两个文件，后者 L71-85 亦有同款方法可参照）；本 Story 对 epics L1472「P95<200ms」门禁的采样方法细化，epics 原文未规定采样法；200ms 对典型 <20ms 链路约 10 倍余量）
**And** **并发 ≥10** 个 Agent 同时实例化全部成功且互不干扰（NFR-PERF-04 MVP 档：asyncio.gather 10 并发，键天然隔离）
**And** 配置加载成功率 100%（AC-2 确定性）

**验证标准/Validation Criteria:**
- [ ] 性能测试基于真实 Redis（非 fakeredis），标记 `benchmark`，采样 ≥20 次断言 P95<200ms
- [ ] 10 并发 gather 全部返回不同 agent_id，对记录的 10 个 agent_id 逐一 `exists(build_key("agent", str(aid)))` 断言 + agent_id 全互异（**禁止 scan 模式计数**——多 worker 共享同一 Redis 实例会误计并行场景键）
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
  - `role: str = field(kw_only=True)`（AgentRole.value；⚠️ **必填字段必须 kw_only**——DomainEvent 基类字段全带默认值，子类无默认值的非 kw_only 字段跟在其后时类定义即抛 `TypeError: non-default argument follows default argument`；对齐 AgentDecided「kw_only 必填」先例 agent_events.py L26）
  - `name: str = field(kw_only=True)`
  - `config_version: str = field(kw_only=True)`（= `AgentConfig.version` 配置资产版本，5.6/5.7 观测追溯「哪个配置版本产出该 Agent」消费）
  - `event_type: str = field(default="AgentInstantiated", init=False)`（**放置位置与 agent_events.py 既有事件风格对齐**）
  - `__post_init__` 设置 `aggregate_id=agent_id`（**UUID 对象非 str**，含 `if self.aggregate_id is None` 守卫——对齐 AgentDecided L31-36 与基类 `uuid.UUID | None` 类型契约，`to_dict` 序列化时自转 str）、`aggregate_type="Agent"`
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
    preferred_model: str | None        # 可选，纯 str 预留（不引用 LLMConfig 类型——其无该字段）；空串 "" 在 VO 归一化为 None（与 YAML null 等价，5.3 消费方只见 None | str 两态）；5.3 消费时映射 LLMConfig.model
    state_ttl: int = 86400             # Agent 状态 TTL 秒，范围 60~2592000
    default_isolation_level: str = "L4"  # 5.4 EIP 消费，本 Story 仅承载
```

- [ ] `AgentConfig` 自校验（`__post_init__` 或 `validate()`）：role 合法、必填非空、state_ttl 范围——校验失败抛 `AgentConfigError`（EXCEPTION_440）（值对象内抛子域异常先例：`document_metadata.py` L100-104 `raise MetadataValidationError`(217)——VO 校验异常主流是 EntityValidationError(242)（10 文件），AgentConfig 走子域异常因「配置资产缺陷」语义与 242「实体不变量违反」需分码监控；440/242 边界：AgentConfig 自校验→440，Agent 实体 validate()→242）
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

> **未知键策略（定稿）**：加载器**忽略** Schema 外未知键（前向兼容——DC-3 回填期新旧配置共存），Task 2 红行含「YAML 多余未知键 → 加载成功且字段不受污染」用例锁定该行为。

#### 统一端口定义注册与管理 (Port Contract)

- [ ] 端口契约定义位于 `src/domain/ports` 与 `src/application/ports`
- [ ] 端口注册中心位于 `src/domain/ports/registry.py`，所有端口必须登记为 `PortSpec`
- [ ] 端口实现仅可在 `src/composition_root.py` 统一注册，禁止业务代码直接实例化具体实现
- [ ] 端口解析器位于 `src/domain/ports/resolver.py`，业务代码只通过抽象解析实现
- [ ] 端口契约门禁位于 `src/domain/ports/contract_gate.py`，端口变更必须通过兼容性检查
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_agent_repository.py` 等 3 个；维度 9b 用测试本地 `_DummyResolver`（tool_execution_repository L120-125 先例）——`agent_repository` 的 Dummy 须提供 `resolve("redis_adapter")`（stub 或 fakeredis 包装的 RedisAdapter，构造零 IO）；`agent_instantiation_use_case` 的 Dummy 须另提供 `agent_config_loader`/`agent_repository`/`event_publisher` 三依赖名；契约测试在 CI docker compose 服务环境运行）
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

> lifetime 说明：`agent_repository` SCOPED 对齐仓储端口主流惯例与 snapshot_repository 注册样例；在 `clear_scoped` 未接线环境下 SCOPED 与 SINGLETON 等效，实例被 SINGLETON 用例首次 resolve 钉住（生产先例：auto_execute_service SINGLETON ← snapshot_repository SCOPED）——若未来启用请求级 scope，需改为用例内按调用解析。

**端口方法签名（Task 0 定稿，实现不得偏离）：**

```python
# src/domain/ports/agent_repository.py —— 仓储端口（R1 领域层基础端口；单字段标识查找用直接参数；get_by_id 命名对齐项目仓储端口主流命名——10+ 端口直接定义、另有经 L2RdbPort 继承者）
@runtime_checkable
class AgentRepository(Protocol):
    async def save(self, agent: Agent, ttl: int) -> None: ...  # TTL 必填——Agent 实体无 TTL 载体（复用不修改），持久化策略由调用方显式声明；范围 60~2592000 防御性校验抛 AgentConfigError(440)
    async def get_by_id(self, agent_id: UUID) -> Agent | None: ...
    async def delete(self, agent_id: UUID) -> None: ...
    async def exists(self, agent_id: UUID) -> bool: ...

# src/application/ports/agent_config_loader.py —— 配置加载端口（R2 应用层具体应用端口）
@runtime_checkable
class AgentConfigLoader(Protocol):
    async def load(self, role: AgentRole) -> AgentConfig: ...
```

- [ ] `RedisAgentRepository` 组合 `RedisAdapter`（构造注入 `adapter=resolver.resolve("redis_adapter")`，仿组合根 snapshot_repository 注册样例——composition_root.py L941-955）；Hash 操作走 `adapter.raw_client`；静态方法 `_agent_to_hash`/`_hash_to_agent` 做实体↔Hash 转换（UUID→str、Enum→value、datetime→ISO；读回显式重建）；键 `build_key("agent", str(agent_id))`
- [ ] `YamlAgentConfigLoader` 的 YAML 解析用 `asyncio.to_thread(yaml.safe_load, ...)` 包装（不引入 aiofiles 新依赖）；配置目录路径构造函数注入（默认 `Path(__file__).parent.parent.parent.parent / "configs" / "agents"` **仓库根锚定不依赖 cwd**——对齐 event_bus_config_loader.py L18 `DEFAULT_CONFIG_PATH` 上溯模式，CLI 任意 cwd 可用；构造注入可覆盖，测试传 tmp_path）

#### 端口契约清单执行约束（强制）

- [ ] 本清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口，禁止未同步更新 registry / resolver / contract test
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增异常在 Task 0 完成设计，Task 1 实现。
> **禁止 `raise ValueError`**；完整清单见 [`sisys-uni-exception-design.md §3.3.2`](../../../docs/architecture/sisys-uni-exception-design.md)。

**新建 `agent` 子域，编码段 EXCEPTION_440 ~ 449**（440-449 当前空闲，全仓 grep 验证无碰撞；遵循 data_source(410-419)/debate(420-429)/tool_version(430-439) 独立物理段先例）。定义文件：`src/domain/exceptions/agent_exceptions.py`（对齐 `debate_exceptions.py`/`data_source_exceptions.py` 独立子域文件先例）。

| 异常类 | 编码 | 基类 | 触发场景 | HTTP 映射 |
|--------|------|------|---------|-----------|
| `AgentConfigError` | EXCEPTION_440 | `SystemException` | 配置文件缺失 / YAML 解析失败 / 配置文件不可读（目录占位、权限、TOCTOU）/ 编码非法（非 UTF-8）/ 必填字段无效 / role 与配置不匹配 / 可选字段类型非法（preferred_model、default_isolation_level 非 null 非 str）/ 可选段非映射结构（llm_config/eip_config/memory_config 非 dict，R2-F9）/ VO 字段类型非法（responsibilities/domain_knowledge 非 tuple，R2-F2）/ state_ttl 非整数或越界（R1 审查补强：全部失败路径统一 440，禁裸内置异常逃逸）（配置资产属系统资源，同 ConfigurationError(101) 继承链；HTTP 500） | 500 |
| `AgentRoleNotSupportedError` | EXCEPTION_441 | `BusinessException` | 请求实例化 MVP 未开放角色（非 CEO）——业务能力范围规则违反（同 DebateLowDivergenceError(422)→422 先例） | 422 |
| （预留） | EXCEPTION_442~449 | — | 预留给 5.2 档案加载 / 5.4-5.5 EIP 隔离 / 5.3 工作流异常 | — |

**继承链选择理由（写入 agent_exceptions.py 模块 docstring，仿 debate_exceptions.py 风格）：** 440 根因是系统配置资产缺陷（部署错误，非调用方输入错误）故入 SystemException；441 是 MVP 阶段性业务规则限制故入 BusinessException——两者无法共享子域基类，**不设 AgentError 子域基类**（项目规范必须继承三大抽象分层之一，relevance/debate 平铺无基类先例支持）。

- [ ] 定义文件 `src/domain/exceptions/agent_exceptions.py`（模块 docstring 含编码范围/继承链理由/消息安全性声明，Google 风格全中文注释）
- [ ] `_code_ranges.py`：CODE_RANGES 增加 `agent(440-449)` + `_CLASS_TO_SUBDOMAIN` 注册两异常
- [ ] `src/domain/exceptions/__init__.py` 暴露两异常（`__all__` 同步）+ **`src/interfaces/api/exception_handlers.py` 的 `EXCEPTION_HTTP_MAP`（L130-262）精确注册**：追加 `AgentConfigError: 500`、`AgentRoleNotSupportedError: 422` 两行（对齐 debate L253-255 条目形态；`_get_http_status` 先精确 type 匹配再 isinstance 回退，441 未注册将回退基类 BusinessException→400）
- [ ] 子域码段校验：`poetry run pytest tests/unit/domain/exceptions/ -v`（test_error_code_uniqueness.py + test_code_ranges.py 共 8 项）
- [ ] 构造器携带领域上下文：`AgentConfigError(context={"role": ..., "config_path": ..., "reason": ...})`、`AgentRoleNotSupportedError(context={"role": ..., "supported_roles": ...})`（supported_roles 从用例模块级常量 `SUPPORTED_ROLES` 派生——见 Task 4 绿行，勿硬编码字面量列表）
- [ ] 消息安全性：不泄露 YAML 全文/绝对路径/堆栈
- [ ] 同步更新 `docs/architecture/sisys-uni-exception-design.md` §3.3.2 编码分配表（agent 440-449 行）
- [ ] BDD 异常路径场景纳入验收（AC-1.2 / AC-2.2 / AC-2.3）

#### API 契约 (API Contract)

- [ ] **OpenAPI 不适用**——本 Story 无 REST 端点（架构文档 §13.17.1 的 `POST /api/v1/agents/{agent_id}/execute` 是执行端点属 5.3+，MVP 不建 API 路由，所有 API 路由必须过认证中间件的成本在 Epic 7 承接）
- [ ] CLI 契约：新建独立入口 `src/interfaces/cli/agent_cli.py`（**仿 ocr_cli.py 接线模式**，勿仿 document_commands.py——后者无挂载点属未接线资产）；命令形态 `sisys-agent instantiate --role ceo`；`pyproject.toml` 的 `[project.scripts]` 与 `[tool.poetry.scripts]` 双注册 `sisys-agent = "src.interfaces.cli.agent_cli:main"`；输出 agent_id；异常经统一异常体系展示；**幂等性：`instantiate` 非幂等**——每次调用创建新 Agent 与新 Redis 键（AC-1.3 设计行为，靠 TTL 自然回收），agent_cli.py 模块 docstring 明示此语义
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
| AC-1.1 实例化 CEO Agent 成功 | AC-1 | 服务级：真实组装——`resolve("agent_config_loader")`（无连接安全）+ **手动组装** `RedisAgentRepository(adapter=RedisAdapter(redis_client=ctx["_redis_client"]))` + `InMemoryEventBus()` 直接构造 + 手动实例化用例（⚠️ **禁 resolve("agent_repository")**：SCOPED 实例钉住全局 Resolver，其 SINGLETON redis_client 跨 function-scope 循环复用必抛 "Event loop is closed"）→ 断言实体 role/status/agent_id |
| AC-1.2 实例化未开放角色抛异常 | AC-1 | `AgentRoleNotSupportedError` + `error.code == EXCEPTION_441` |
| AC-1.3 两次实例化相互独立 | AC-1 | agent_id 不同 + 两键各自 `exists()` 断言 + `get_by_id` 各读回自己的 id（禁 scan 计数；两 id 记入 context 供 teardown 精确删） |
| AC-2.1 加载 CEO 基础配置成功 | AC-2 | 内置 configs/agents/ceo_agent.yaml，断言字段映射 |
| AC-2.2 配置文件缺失抛异常 | AC-2 | tmp 目录无文件 → `AgentConfigError` EXCEPTION_440 |
| AC-2.3 配置字段无效抛异常 | AC-2 | role 不匹配/必填缺失 → EXCEPTION_440 |
| AC-3.1 Agent 状态持久化并可读回 | AC-3 | 键存在 + TTL>0 + 实体全字段重建一致（断言经 `ctx["_redis_client"]` 场景级同循环客户端；`get_by_id` 用场景内手动组装仓储） |
| AC-4.1 实例化发布 AgentInstantiated 事件 | AC-4 | 真实 InMemoryEventBus 直接构造注入 → published_events 断言 |
| AC-4.2 事件通道双登记 | AC-4 | yaml + DEFAULT_MAPPINGS 两处可达断言 |
| AC-5.1 实例化延迟 P95<200ms | AC-5 | 真实 Redis ≥20 采样 perf_counter |
| AC-5.2 十个并发实例化全部成功 | AC-5 | asyncio.gather(10) 全成功 + 10 agent_id 逐一 exists() 互异（禁 scan 计数） |
| AC-6.1 三端口接线可达 | AC-6 | resolve 三端口 isinstance + PortSpec 元数据（resolve 全链构造零 IO 已代码级验证——RedisManager 建池不连接、DualChannelEventBus/Outbox 惰性；**禁止对 resolve 产物发命令**——一旦发命令 SINGLETON 池绑定本场景循环贻害后续场景） |
| AC-6.2 完成清单逐项确认 | AC-6（收尾） | Task 8 收尾场景（src/tests 完成清单 + L1-L8 接线终态断言） |

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试（`_run_async` helper）
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **文件名不含服务关键词，acceptance conftest 不会自动打 marker**——文件内显式 `pytestmark = [pytest.mark.acceptance, pytest.mark.redis]`（两 marker 均已注册于 pyproject markers；与 conftest 自动添加重复无害）+ Background 双保险动态 skip（文件内自建场景级 Redis ping+skip——异步客户端模板照抄 `test_acceptance_skill_data_collection.py` L82-113：context fixture 内 `aioredis.Redis(..., decode_responses=True)` 创建 + Background 步骤 ping 失败 `pytest.skip` + teardown 同循环 `close()`；⚠️ autonomous_invocation_execute L69-87 是**同步** `redis.Redis` 客户端，勿作异步模板）
- **@scenario 收集期陷阱**：绑定场景名与 .feature 不匹配 → 收集期 `ScenarioNotFound` **整文件炸**（已绿场景连带挂，破坏逐场景转绿）；反向漏绑定 → **静默不收集无报错**。场景名必须从 .feature 复制粘贴（ASCII 连字符 `-` 0x2D + 两侧空格，全角 `－`/`—` 即收集期炸）；Task 0.4 红阶段与 Task 8.6 转绿核对均须校验收集场景数 == 13（`pytest --collect-only -q`）
- **event_loop 来源**：模板依赖 pytest-asyncio 0.24 内建已弃用 `event_loop` fixture（pyproject 锁 `^0.24.0`，1.0 将移除——升级 pytest-asyncio 前须回归验收目录）
- Redis 客户端**场景级独立创建、同循环 teardown 关闭**（跨循环 "Event loop is closed" 教训，见记忆 acceptance_redis_client_cross_loop_issue）
- teardown **精确删除**：context 记录本场景创建的 agent_id 列表，teardown 逐个 `delete(build_key("agent", str(agent_id)))`（经 `ctx["_redis_client"]` 同循环执行）——`build_key` 产出 `sisys:agent:{uuid}` **无租户维度**，TestTenant 前缀 `test:{id}:` 无任何存储层叠加机制（delete_pattern 租户前缀模式匹配不到本 Story 的键）；**禁止** `delete_pattern("sisys:agent:*")`——多 worker 共享同一 Redis 实例（6380）会误删并行场景正使用的键；禁止全库 flush
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
| 资源唯一性 | Redis 键经 `build_key("agent", agent_id)`——agent_id 为 uuid4 天然唯一即隔离机制本身（**无租户前缀叠加机制**：build_key 不含 tenant 维度、TestTenant 前缀仅测试侧字符串）；清理靠 context 记录 agent_id 后逐键精确 delete |
| 外部服务隔离 | 真实 Redis 仅测试环境（`SISYS_USE_TEST_PORTS=1`→6380，仅 pytest 会话内生效）；teardown 逐键精确 delete（见 BDD 约束），**禁止 flush/全库 delete/通配 delete_pattern** |
| Redis 跨循环 | Redis 客户端**场景级独立创建、同循环 teardown 关闭**（记忆 acceptance_redis_client_cross_loop_issue）；`_run_async` 统一经 `context["_loop"]` |
| asyncio 约束 | BDD 步骤禁 `@pytest.mark.asyncio`；CLI 入口（独立进程）用 `asyncio.run()` 合法；并发测试在 async 函数内 `asyncio.gather()`；`asyncio.Lock` 若使用必须类变量 |
| Mock 边界 | **单元测试** Mock 端口（`AsyncMock(spec=Protocol)` + `_make_*` 工厂）；**集成测试**真实 Redis 优先；**验收测试禁止 mock**（InMemoryEventBus 是真实实现类，非 mock；YAML 加载用 tmp_path 真实文件） |
| bootstrap 禁令 | **验收测试禁止调用 `bootstrap()`**——组合根已由 `tests/conftest.py` session 级 `_bootstrap_once`（L20-27）完成引导；同进程二次 bootstrap 因 lambda 工厂 spec 不幂等必抛 ConflictError（registry 仅字符串 impl 幂等，实测二次调用即抛）。端口获取直接 `from src.domain.ports.resolver import resolve`；CLI 入口在独立进程内 bootstrap 合法 |
| 清理粒度 | 每个测试只清理自己创建的资源；fixture 显式声明依赖 |
| 性能测试 | `pytestmark` 标记 `benchmark`；xdist 下用 `xdist_group` 串行化计时场景（仅保**同组串行**不保独占 CPU；benchmark marker 自述建议性能专项 `-n 0` 复跑确认——`-n auto` 下抖动超标时以 `-n 0` 结果为准）；硬断言依赖 200ms 对典型 <20ms 链路约 10 倍余量 |

**禁止行为：**
- ❌ 验收/集成测试 mock 领域服务/用例/仓储（真实服务优先）
- ❌ 手动 delete/truncate 全库资源
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`
- ❌ 共享 session 级 Redis 客户端跨场景复用（**经 `resolve()` 获得的 SINGLETON `redis_client` 即此种共享**——功能场景一律手动组装 `RedisAgentRepository(adapter=RedisAdapter(redis_client=ctx["_redis_client"]))`，resolve 仅做 AC-6.1 接线断言且禁发命令）

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 实例化 CEO Agent 实体 + 角色限制 | Task 4 | 用例编排 + 角色守卫（含 242 透传用例） | test_agent_instantiation.py（unit+acceptance） |
| AC-1 | 两次实例化独立 | Task 3/4 | uuid4 生成 + 键隔离 | test_acceptance（AC-1.3）/ test_integration |
| AC-2 | 配置加载端口与 YAML | Task 2 | AgentConfig + Loader + ceo_agent.yaml | test_agent_config.py / test_yaml_agent_config_loader.py |
| AC-2 | 配置失败异常路径 | Task 1/2 | AgentConfigError 三路径 | 同上 + test_agent_exceptions.py |
| AC-3 | Redis 持久化与读回 | Task 3/4/6 | AgentRepository 端口 + Redis 实现 + 用例编排 + 真实集成 | test_redis_agent_repository.py / test_agent_instantiation.py / test_integration_agent_instantiation.py |
| AC-3 | TTL 管理 | Task 2/3/4 | state_ttl 传递与范围校验（值对象边界单测 + 仓储防御校验 + 用例显式传 ttl） | test_agent_config.py / test_redis_agent_repository.py / test_agent_instantiation.py |
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

- [x] Subtask 0.1: 按「领域事件 Schema」「数据模型」「端口契约清单」「领域异常契约」四节定稿全部契约（如本 Story 已定稿，逐项核对签名/字段/编码无歧义后确认）
- [x] Subtask 0.2: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_agent_instantiation.feature`（13 场景清单，严格模仿 data_source/skill_data_collection 最新范本 + AC 编号命名，见 R6）
- [x] Subtask 0.3: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_agent_instantiation.py`（@scenario 显式绑定 + context dict + `_run_async` + Background 动态 skip + **新模块延迟 import** + 显式 pytestmark）
- [x] Subtask 0.4: 运行验收测试，确认失败（🔴 红阶段验证；ModuleNotFoundError 为合法红，记录失败形态；**前提：Redis 在线**——Background ping 失败则全 skip 无失败可确认；**校验收集场景数 == 13**——`pytest --collect-only -q`，防 @scenario 绑定名与 .feature 不匹配的收集期 ScenarioNotFound 或漏绑定静默不收集）
- [x] Subtask 0.5: 链路接线断言清单 L1-L8 逐项确认处置（本 Story 接线 5 项 / deferred 保持 3 项）+ **补登记 deferred-work.md**：`session_storage` 端口 + RedisSessionStorage 未接线（处置：5.1 用新建 AgentRepository，见 DC-1；触发=Story 5.3 会话状态）——该条目在 2026-10-12 普查中缺席，L7/L8 已登记核对通过

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕
- [x] 验收测试运行失败（预期行为，红阶段确认）
- [x] deferred-work.md 补登记 L6 `session_storage` 条目（L7/L8 已登记核对通过）

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
| 🔄 重构 | `configs/event_channels.yaml` + `channel_router.py DEFAULT_MAPPINGS` 双登记（对齐 AgentDecided 条目结构）；`architecture.md §10.1` 领域事件完整列表追加 `AgentInstantiated` 行（RabbitMQ + Outbox / 7 年存储 / 审计合规型，对齐 AgentDecided 行形态——登记类文档随落地 Task 同步，与异常文档 §3.3.2 同模式）；ruff+mypy |

- [x] Subtask 1.1: 🔴 红 — 异常测试（循环 A）
- [x] Subtask 1.2: 🟢 绿 — agent_exceptions.py 实现
- [x] Subtask 1.3: 🟡 变异 + 🔄 重构 — 登记四处（_code_ranges/__init__/HTTP_MAP/设计文档）
- [x] Subtask 1.4: 🔴 红 — 事件测试（循环 B）
- [x] Subtask 1.5: 🟢 绿 — AgentInstantiated 实现
- [x] Subtask 1.6: 🟡 变异 + 🔄 重构 — 事件双登记
- [x] Subtask 1.7: 运行 `poetry run pytest tests/unit/domain/ -v` 全绿（含既有 8 项异常套件不回归）

**完成标准/Definition of Done:**
- [x] 异常/事件契约实现且既有套件零回归（tests/unit/domain/ 2888 passed）
- [x] `grep -r "EXCEPTION_44[01]" src/domain/exceptions/` 无碰撞
- [x] 双登记两处 grep 可达（AC-4.2 验收场景已转绿）

---

### Task 2: AgentConfig 值对象 + 配置加载端口与 YAML 实现

**关联 AC:** AC-2

> **目的：** 交付基础配置加载链：domain 值对象 + application 端口 + infrastructure YAML 加载器 + ceo_agent.yaml 资产。

#### TDD 循环 A：AgentConfig 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_agent_config.py`（frozen/必填非空（含空列表/空串 falsy 判空）/state_ttl 边界**钉端点**：60 与 2592000 恰好合法、59 与 2592001 抛 440（含闭区间，防 off-by-one——变异只改上界刻度抓不到）/越界抛 AgentConfigError EXCEPTION_440/preferred_model 空串归一化为 None） |
| 🟢 绿 | 实现 `src/domain/value_objects/agent_config.py`（Schema 见 Task 0） |
| 🟡 变异 | 突变 ttl 上界 2592000→259200 → 边界测试红 → 还原绿 |
| 🔄 重构 | Google 风格全中文注释；ruff+mypy |

#### TDD 循环 B：YamlAgentConfigLoader + ceo_agent.yaml

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/agent_orch/test_yaml_agent_config_loader.py`（tmp_path 真实文件：正常映射/文件缺失/YAML 语法错/role 不匹配/必填缺失/**空列表（`capabilities.responsibilities: []` → 440，防 `is None` 式漏检——Agent.validate() 不校验非空，VO 是唯一防线）**/**`capabilities.*` 非列表标量（字符串 → 440——禁止 `tuple(str)` 逐字符静默展开成 ('战','略',…)）**/**state_ttl 非整数（字符串/浮点 → 440，禁止裸 TypeError 逃逸）**/**YAML 空文件（safe_load 返回 None → 440 非 AttributeError）**/**未知键（Schema 外多余键 → 加载成功且字段不受污染——前向兼容策略，防 DC-3 回填期新旧配置共存被 strict 校验破坏）** → 各异常路径断言 error.code==EXCEPTION_440） |
| 🟢 绿 | 实现 `src/application/ports/agent_config_loader.py`（Protocol）+ `src/infrastructure/agent_orch/yaml_agent_config_loader.py`（`asyncio.to_thread(yaml.safe_load, ...)`，目录构造注入——默认 `Path(__file__)` 四级上溯锚定仓库根 `configs/agents/`，对齐 event_bus_config_loader.py L18，可覆盖；`capabilities.*` **先 `isinstance(x, list)` 守卫再转 tuple**；VO 空值校验用 falsy 判空（`not xxx`）而非 `is None`）+ 新建 `configs/agents/ceo_agent.yaml`（内容见 Task 0） |
| 🟡 变异 | 突变 role 映射键（identity.role→identity.roleX）→ 加载测试红 → 还原绿 |
| 🔄 重构 | 组合根注册 `agent_config_loader`（SINGLETON，lambda + `__import__` 延迟加载，仿 snapshot 样例）+ 契约测试 `tests/contracts/test_port_contract_agent_config_loader.py`（11 维度）；ruff+mypy |

- [x] Subtask 2.1: 🔴 红 — 值对象测试
- [x] Subtask 2.2: 🟢 绿 — AgentConfig 实现
- [x] Subtask 2.3: 🟡 变异 + 🔄 重构 — 值对象收敛
- [x] Subtask 2.4: 🔴 红 — 加载器测试（真实文件 IO，零 mock）
- [x] Subtask 2.5: 🟢 绿 — 端口 + 实现 + ceo_agent.yaml
- [x] Subtask 2.6: 🟡 变异 + 🔄 重构 — 组合根注册 + 契约测试
- [x] Subtask 2.7: 内置 `configs/agents/ceo_agent.yaml` 加载冒烟（`load(AgentRole.CEO)` 成功，字段映射正确）

**完成标准/Definition of Done:**
- [x] 配置加载三失败路径 + 成功路径全覆盖（值对象 20 + 加载器 18 用例）
- [x] 契约测试通过，`resolve("agent_config_loader")` 可达（链路 L2 绿灯——11 维度契约 12 用例 passed）
- [x] domain 层零第三方依赖（agent_config.py 仅标准库 + AgentRole）

---

### Task 3: AgentRepository 端口 + RedisAgentRepository 实现

**关联 AC:** AC-3、AC-1（键隔离基础）

> **目的：** 交付 Agent 聚合的 Redis 仓储：端口 + 实体序列化实现 + 组合根注册。

#### TDD 循环 A：仓储端口与 Redis 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/redis/test_redis_agent_repository.py`（Mock 工厂模式：`AsyncMock(spec=...)` raw_client + `_make_agent()` 工厂；save/get_by_id/exists/delete；**同 agent_id 二次 save（不同实体/ttl）→ get_by_id 读回第二实体、TTL 重置为第二次值（save 的 upsert 语义契约）**；`_agent_to_hash`/`_hash_to_agent` 往返：UUID/AgentRole/AgentStatus/datetime 重建；TTL 必填传递（缺参 TypeError 契约）；ttl 越界（<60 或 >2592000）抛 AgentConfigError(EXCEPTION_440)；**Redis 连接异常（raw_client 抛 aioredis.ConnectionError——AsyncMock side_effect 模拟）→ save 包装 `StorageError` 向上传播不静默**——对齐 RedisSnapshotStore.save L126-128 先例，AC-3 第 4 条验证标准与追溯矩阵的落点用例） |
| 🟢 绿 | 实现 `src/domain/ports/agent_repository.py`（Protocol，签名见 Task 0）+ `src/infrastructure/storage/redis/redis_agent_repository.py`（组合 RedisAdapter、`build_key("agent", str(agent_id))`、Hash 读写走 `raw_client`、静态转换方法仿 RedisSnapshotStore） |
| 🟡 变异 | 突变 `_hash_to_agent` 的 `AgentStatus(status_str)` 重建（改为透传 str）→ 往返断言红（`isinstance(status, AgentStatus)` 失败）→ 还原绿 |
| 🔄 重构 | 组合根注册 `agent_repository`（SCOPED，lambda 工厂 `adapter=resolver.resolve("redis_adapter")`，仿组合根 snapshot_repository 注册样例 composition_root.py L941-955）+ 契约测试 `tests/contracts/test_port_contract_agent_repository.py`；ruff+mypy |

- [x] Subtask 3.1: 🔴 红 — 仓储单元测试（含序列化往返矩阵）
- [x] Subtask 3.2: 🟢 绿 — 端口 + RedisAgentRepository
- [x] Subtask 3.3: 🟡 变异 — Enum 重建突变实证（防恒真断言核心点）
- [x] Subtask 3.4: 🔄 重构 — 组合根注册 + 契约测试 + 注释规范
- [x] Subtask 3.5: fakeredis 快速回归（可选：fakeredis 实测支持 `hset`+`expire`+`ttl` 语义，TTL 断言先例 test_redis_cache.py L276/L295；⚠️ `mock_redis` fixture 在 `tests/integration/conftest.py` L87，unit 目录不可见——unit 文件内自建 `fakeredis.aioredis.FakeRedis(decode_responses=True)`）

**完成标准/Definition of Done:**
- [x] 序列化往返全字段一致（UUID/Enum/datetime 显式重建断言，非恒真）
- [x] 契约测试通过，`resolve("agent_repository")` 可达（链路 L1 绿灯——11 维度契约 12 用例 passed）
- [x] Redis 错误不静默（连接异常包装 StorageError(cause=exc) 向上传播——绿阶段自纠：`from exc` 仅设 __cause__，DomainError.cause 属性须构造参数显式传递）

---

### Task 4: InstantiateAgentUseCase 应用服务 + 事件发布接线

**关联 AC:** AC-1、AC-3（编排）、AC-4（发布点）

> **目的：** 交付实例化用例编排：**角色守卫 → 加载配置** → 构建实体 → 持久化 → 发布事件；完成用例端口注册。
> ⚠️ **守卫必须先于加载**——若先加载，`execute(CFO)` 会先触发 `cfo_agent.yaml` 缺失的 `AgentConfigError`(440)，AC-1.2 的 `AgentRoleNotSupportedError`(441) 将不可达（CLI `"cfo"` 是合法枚举值，字符串守卫拦不住它）。

#### TDD 循环 A：用例编排

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/use_cases/test_agent_instantiation.py`（Mock 端口：`AsyncMock(spec=AgentConfigLoader)`、`AsyncMock(spec=AgentRepository)`、InMemoryEventBus 真实类；成功编排顺序断言（**守卫→加载→构建→save→publish 调用序**，guard 先于 loader.load、save 断言以 `ttl=config.state_ttl` 调用）；非 CEO → AgentRoleNotSupportedError 且 **loader 未被调用**；配置失败传播；save 失败传播不发布事件；publish 失败→结果仍返回且记录日志不回滚——**raise 路径仅由 Mock side_effect 触发，真实 EventPublisher 返回 `PublishResult` 不 raise，失败面为 `is_success == False`（publish_result.py L33-38），两分支都需断言**；实体校验 `EntityValidationError`(242) 透传不包装；返回对象含 agent_id/实体） |
| 🟢 绿 | 实现 `src/application/use_cases/agent_instantiation.py` `InstantiateAgentUseCase`（构造注入 loader/repository/event_publisher；`async execute(role: AgentRole) -> AgentInstantiationResult`；**角色守卫集合定义为用例模块级常量 `SUPPORTED_ROLES: frozenset[AgentRole] = frozenset({AgentRole.CEO})`，441 的 `context["supported_roles"]` 从常量派生——V1 开放 CFO 时仅改此一处**；`uuid.uuid4()` 显式生成 agent_id（实体无默认生成）；`responsibilities`/`domain_knowledge` 以 `list(config.xxx)` 显式转换注入实体——实体字段为 `list[str]`，tuple 直传将使读写往返类型不对称、全字段相等断言红；`save(agent, ttl=config.state_ttl)` 显式传入（端口 ttl 必填，无仓储默认值）；先持久化后发布，发布失败 `logger.error(exc_info=True)` 记录不回滚——对齐 run_tool_chain L180-185 用例先例） |
| 🟡 变异 | 突变发布调用行（注释掉 publish）→ 「事件已发布」断言红 → 还原绿（Epic 4 零发布教训的直接防线） |
| 🔄 重构 | `AgentInstantiationResult` dataclass（agent_id + Agent 实体引用，**定稿：应用层 DTO，定义于 use_cases/agent_instantiation.py 模块内**——对齐 strategic_analysis.py L36-51 请求 dataclass 模块内定义先例，不新增 domain 文件）；组合根注册 `agent_instantiation_use_case`（SINGLETON，工厂 resolve 三依赖）+ 契约测试；ruff+mypy |

- [x] Subtask 4.1: 🔴 红 — 用例单元测试（含编排顺序与异常传播）
- [x] Subtask 4.2: 🟢 绿 — InstantiateAgentUseCase 实现
- [x] Subtask 4.3: 🟡 变异 — 发布点突变实证（链路 L4 核心）
- [x] Subtask 4.4: 🔄 重构 — 结果对象 + 组合根注册 + 契约测试 `test_port_contract_agent_instantiation_use_case.py`
- [x] Subtask 4.5: 验收场景 AC-1.1/1.2/3.1/4.1 转绿核对（服务级真实组装：`resolve("agent_config_loader")`（无连接安全）+ **手动组装** `RedisAgentRepository(adapter=RedisAdapter(redis_client=ctx["_redis_client"]))` + `InMemoryEventBus()` 直接构造 + 手动实例化 `InstantiateAgentUseCase`——⚠️ **不 resolve `agent_repository` 与用例端口**：前者 SINGLETON redis_client 跨 function-scope 循环复用必抛 "Event loop is closed"（记忆 acceptance_redis_client_cross_loop_issue），后者工厂注入的组合根默认 event_publisher 是 DualChannelEventBus，验收环境无 RabbitMQ；组装先例 test_acceptance_skill_data_collection.py L318（`RedisAdapter(redis_client=context["_redis_client"])`）；遵守 bootstrap 禁令见测试隔离约束表）

**完成标准/Definition of Done:**
- [x] 用例四步编排顺序有断言守护（非仅结果断言——calls 序 ["load","save:777","publish"]）
- [x] `resolve("agent_instantiation_use_case")` 可达（链路 L3 绿灯——11 维度契约 12 用例 passed）
- [x] 发布点变异实证记录在案（注释发布调用→2 断言红→还原绿）

---

### Task 5: CLI 入口 agent_cli

**关联 AC:** AC-6（接线）、AC-1（角色守卫）

> **目的：** 接口层最小入口，兑现「接收 Agent 任务命令」（R4 接口适配）；消除「已实现未接线」。
> **接线模式：** 仿 `src/interfaces/cli/ocr_cli.py`（项目唯一真实接线范本：`bootstrap()` + `resolve()` + `build_parser()` + `main(argv)->int` + pyproject script 注册）。**禁止**参照 `commands/document_commands.py`——其 parser 无任何挂载点（未接线资产），项目不存在集中式 CLI 主入口。

#### TDD 循环 A：CLI 命令

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_agent_cli.py`（build_parser 参数契约：`instantiate` 子命令 + `--role` 必填；角色字符串守卫：`"ceo"` 合法、**`"CEO"`（大写）→ 归一化成功实例化（`.lower()` 防漏——漏写时合法输入误报 441，小写/非法用例均无法暴露）**、`"cfo"`/`"xyz"` → `AgentRoleNotSupportedError` EXCEPTION_441 且 context 携带原始输入；**裸调用 `main([])` → SystemExit 退出码 2 且 stderr 含 usage（argparse 用法错——`add_subparsers` 默认非必选，漏 `required=True` 时会取 `args.role` 抛 AttributeError 裸崩逃逸统一异常体系；ocr_cli 无子命令先例，此点不可从模板继承）**；main 成功路径输出 agent_id（纯 UUID 单行 stdout）——**注入机制：monkeypatch `agent_cli` 模块级 `bootstrap`/`resolve` 属性**替换为 stub（项目无 Resolver override 公开 API、双 bootstrap 抛 ConflictError、ocr_cli 单测只测纯函数无 main() 注入先例，monkeypatch 是唯一可行注入）；业务异常路径退出码钉死 **1** 且输出含 `EXCEPTION_441`（对齐 ocr_cli 0/1 先例；argparse 用法错为自动 2）） |
| 🟢 绿 | 实现 `src/interfaces/cli/agent_cli.py`（模块 docstring 仿 ocr_cli.py 含架构约束声明：interfaces 层不 import infrastructure、经 `bootstrap()` + `resolve("agent_instantiation_use_case")` 获取用例、`asyncio.run()` 执行；`--role` 字符串→枚举守卫：try `AgentRole(value.lower())` except ValueError → 映射 `AgentRoleNotSupportedError`，**禁止裸枚举构造导致 ValueError 逃逸**；`add_subparsers(required=True, dest="command")` **必设 required**——argparse 子命令默认可选，裸调用 `sisys-agent` 会因取 `args.role` 抛 AttributeError 裸崩（ocr_cli 无子命令先例，此点不可从模板继承）；输出格式定稿：成功路径 `print(str(result.agent_id))` 纯 UUID 单行至 stdout（日志走 stderr）；⚠️ **Redis 池清理**：async 执行核的 finally 内 `resolver.peek_singleton("redis_connection_manager")` 非空则 `await manager.close()`——agent_cli 是首个打开 Redis 池的 CLI（ocr_cli 不触碰 Redis 无此问题）；**禁用全量 `shutdown()`**——它会在退出路径惰性实例化 PG/Qdrant/Neo4j manager） |
| 🟡 变异 | 突变角色守卫映射（删 except 分支）→ 非法字符串测试红（ValueError 逃逸被断言捕获）→ 还原绿 |
| 🔄 重构 | `pyproject.toml` `[project.scripts]` + `[tool.poetry.scripts]` 双注册 `sisys-agent = "src.interfaces.cli.agent_cli:main"`（对齐 sisys-ocr L155-161 双段先例）；ruff+mypy |

- [x] Subtask 5.1: 🔴 红 — CLI 单元测试（含角色守卫红线用例）
- [x] Subtask 5.2: 🟢 绿 — agent_cli.py 实现
- [x] Subtask 5.3: 🟡 变异 — 守卫映射突变实证（防 ValueError 逃逸防线）
- [x] Subtask 5.4: 🔄 重构 — pyproject 双注册 + docstring 规范
- [x] Subtask 5.5: 端到端冒烟——`REDIS_PORT=6380 poetry run sisys-agent instantiate --role ceo` 真实执行输出 agent_id，Redis 键可查（链路 L5 绿灯）。**三个前置**：① `SISYS_USE_TEST_PORTS=1` 仅 pytest 会话内生效、CLI 子进程只读 `REDIS_PORT`（默认 6379）——冒烟须显式传 `REDIS_PORT=6380`；② pyproject 修改后先 `poetry install` 重生成 entry point（否则 `sisys-agent` Command not found，勿误判为接线失败）；③ 无 PG 环境下 RELIABLE 发布走 Outbox 落库失败仅记日志、exit 0 属预期（AC-4 发布失败不回滚语义），勿误判为故障

**完成标准/Definition of Done:**
- [x] `sisys-agent` 入口注册生效、端到端可执行（UUID 单行 stdout；退出码 0/1/2 三路径实测 ok=0/441=1/裸调用=2；Redis 池 close 正常；Outbox 失败仅记日志 exit 0 属预期行为实证）
- [x] 非法/未开放角色字符串统一抛 EXCEPTION_441（无 ValueError 逃逸——绿阶段设计裁定：`_parse_role` 两道防线=枚举转换 except ValueError 映射 + SUPPORTED_ROLES 预检拦合法枚举未开放角色，用例守卫仍是 441 真源）
- [x] CLI 错误展示走统一异常体系（无裸 print 堆栈——stderr `[EXCEPTION_441] 消息 (role='cfo')` 形态）

---

### Task 6: 集成测试 + 性能验收（真实 Redis）

**关联 AC:** AC-3、AC-5

> **目的：** 真实 Redis 全链路集成验证 + 性能门禁（P95<200ms、并发≥10）。
> **性质说明：** 验证型集成/性能测试（非先红后绿循环）——被测链路已由 Task 2-4 交付，**测试编写后直接转绿为合法预期**；「红」仅指测试尚未编写，若编写后即红则暴露真实集成缺陷须修复至绿；断言活性由变异阶段（阈值突变 + Enum 重建突变）背书。

#### TDD 循环 A：集成与性能

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_agent_instantiation.py`（fixture 链：`get_test_env()` → `real_redis`（integration conftest L193-220，async fixture 返回 aioredis 客户端，ping 失败 pytest.skip）→ **手动组装** `RedisAgentRepository(adapter=RedisAdapter(real_redis))` + `resolve("agent_config_loader")` + `InMemoryEventBus` + 手动实例化 UseCase（integration 无共享 resolve() fixture 基建——inline resolve 用法见 test_integration_traceability.py L171-174；组装先例为 `RedisAdapter(real_redis)`，test_integration_storage.py L79）；场景：① 实例化→键存在→读回一致→teardown 按 context 记录的 agent_id 逐键精确 delete ② P95 计时（perf_counter，warmup 剔除 1 次 + ≥20 采样 + `statistics.quantiles(n=20)[18]`，`benchmark` marker + `xdist_group` 串行化）③ `asyncio.gather` 10 并发全成功 + 10 agent_id 逐一 exists() 互异（禁 scan 计数）） |
| 🟢 绿 | 全链路已由 Task 2-4 交付，测试应直接转绿（若红则暴露真实集成缺陷，修复至绿） |
| 🟡 变异 | 突变 P95 断言阈值（200→2）→ 性能测试红（证明计时断言活着，非恒真 sleep 通过）→ 还原绿 |
| 🔄 重构 | 场景命名收敛、超时防护（对齐 acceptance `run_with_bdd_timeout` 思路）；ruff+mypy |

- [x] Subtask 6.1: 🔴 红 — 集成与性能测试编写
- [x] Subtask 6.2: 🟢 绿 — 真实 Redis 全链路通过
- [x] Subtask 6.3: 🟡 变异 — 阈值突变实证
- [x] Subtask 6.4: 🔄 重构 — 隔离与稳定性（TestTenant/场景前缀、连续运行 5 次无随机失败）
- [x] Subtask 6.5: 验收场景 AC-5.1/5.2 转绿核对（注：两场景组装仅需 Task 2-4 产物，Task 4 后即可绿——本 Subtask 是核对点非依赖断点）

**完成标准/Definition of Done:**
- [x] 真实 Redis 环境全绿（不可用时动态 skip 而非失败——real_redis fixture ping 失败 pytest.skip）
- [x] P95<200ms 与 10 并发断言有变异实证背书（阈值 200→2 突变红→还原绿；连续 5 次运行全绿 ~10.5s 稳定）
- [x] teardown 零残留（按 context 记录的 agent_id 逐键精确清理，无通配删除——收尾 scan_iter 复核残留 0）

---

### Task 7: SDD 架构约束验证测试

**关联 AC:** AC-6

> **性质说明：** SDD 规范验证测试（非 TDD 单元测试）——验证前序 Task 产出是否符合六边形架构规则。

#### 架构验证测试实现

- [x] Subtask 7.1: 创建 `tests/unit/architecture/test_arch_agent_instantiation.py`
- [x] Subtask 7.2: 验证器 A——domain 零依赖（`agent_config.py`/`agent_repository.py`/`agent_events.py`/`agent_exceptions.py` 无第三方 import，AST 或 import 扫描，参照 `test_hexagonal_architecture_constraints.py` 既有实现）
- [x] Subtask 7.3: 验证器 B——YAML 解析边界两断言：① `src/domain/` 全目录 grep `import yaml`/`yaml.safe_load` 零命中；② Agent 配置解析链 yaml 用法仅 `yaml_agent_config_loader.py` 一处新增（**禁止断言「全仓仅命中一处」**——`src/application/skills/frontmatter.py` L22/L94 与 `event_bus_config_loader.py` 为既有合法存量，不在断言面）
- [x] Subtask 7.4: 验证器 C——依赖方向（RedisAgentRepository 不 import application/interfaces；agent_cli 不 import infrastructure；用例仅依赖 domain + application 端口）
- [x] Subtask 7.5: 验证器 D——组合根唯一装配（`RedisAgentRepository`/`YamlAgentConfigLoader`/`InstantiateAgentUseCase` 在 src/ 下仅 composition_root.py 与测试中实例化；**属新增断言形态**——现有架构测试无同等先例，用 rglob 全仓扫描类名实例化实现，扫描技术参照 test_arch_data_source.py）
- [x] Subtask 7.6: 循环依赖检测用 ruff/isort（不引入 pylint）
- [x] Subtask 7.7: 运行完整测试套件并生成报告（含本 Story 全部测试文件清单核对）——完整套件归并 Task 8 Subtask 8.4 全量回归执行

**完成标准/Definition of Done:**
- [x] 所有架构约束测试通过，任何违规导致测试失败（13 passed——编写期自纠 1 处：YAML 断言初版全文文本匹配误伤 docstring 提及，改 import 级检查）
- [x] 输出清晰合规报告（五验证器 A-E 分节：domain 零依赖×4 用例/YAML 边界×2/依赖方向×4/组合根唯一装配×2/ruff isort×1）
- [x] 循环依赖检测不引入额外工具（subprocess ruff --select I）

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

- [x] Subtask 8.1: 场景 1 — 验证 `src` 完成清单（value_objects/ports/events/exceptions/application/infrastructure/cli/composition_root 九处产出逐项确认）
- [x] Subtask 8.2: 场景 2 — 验证 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance` 完成清单（测试分类表全文件逐项确认）
- [x] Subtask 8.3: 链路接线断言清单 L1-L8 终态核对（L1-L5 绿灯实证、L6-L8 deferred-work.md 登记仍在且未误删——含 Task 0 补登记的 `session_storage` 条目）
- [x] Subtask 8.4: 运行 `poetry run pytest tests/`、`poetry run ruff check src/ tests/`、`poetry run mypy src/` 收尾校验
- [x] Subtask 8.5: 更新 sprint-status.yaml（5-1 → review）；同步设计文档偏离项（D-1/D-2 的文档更新动作——D-2 含层归属 + 字段裁剪语义改写注记，见 Dev Notes 偏离声明；D-3 无文档动作；D-4/D-5/D-6 不改历史规划文档（epics/or.md）；D-7 无 Task 8 文档动作，5.4 时决策回迁；§10.1 事件行已在 Task 1 同步，此处终态核对）
- [x] Subtask 8.6: 验收场景全量转绿核对（13 场景逐一绿 + **收集场景数 == 13 校验**（`pytest --collect-only -q`，防漏绑定静默不收集）——补齐 Task 2/3/5 未显式核对的 AC-1.3 / AC-2.1 / AC-2.2 / AC-2.3 / AC-4.2 / AC-6.1）

**完成标准/Definition of Done:**
- [x] src 与 tests 完成清单逐项验证确认（AC-6.2 场景 22 项清单 + 组合根/CLI 注册 grep 断言全绿）
- [x] 开发结束验收测试通过（AC-6.2 变异实证：文件名突变→红→还原绿）
- [x] 三项质量门禁全绿（ruff All checks passed / mypy 664 files no issues / pytest 全量回归）
- [x] Story 可进入 `review`/`done`

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
| DC-3 | 基础配置体系 | **YAML 最小子集**（`configs/agents/ceo_agent.yaml`，core-domain §17.3.6 schema 裁剪，偏离声明 D-2）。**取舍标准：保留有近期 Story 消费方的字段**（responsibilities/domain_knowledge→实体构造、version→config_version、state_ttl→TTL、preferred_model→5.3 映射 LLMConfig.model、default_isolation_level→5.4 EIP），**裁剪无认领方字段**（id/display_name/icon、communication、principles、capabilities.tools/max_context_length/reasoning_mode、llm_config 其余子字段、eip_config 其余子字段、memory_config L0/L2-L5）；**回填时机：消费方 Story 立项时回填对应子集**（5.3 回填 llm_config 子字段、5.4 回填 eip_config 子字段、5.10 视需要回填 memory_config）。端口方法全集（save/get_by_id/delete/exists）一次定全的理由不同：端口契约发布后追加方法需过 ContractGate 兼容评审，配置字段后补零成本 | a) `.md` 七档案（弃用：FR-AC-02 属 Story 5.2，5.1 明确边界）；b) 全量 §17.3.6 schema（弃用：无认领字段 YAGNI——配置身份键为 `identity.role`） | prd.md FR-AC-01/FR-AC-02 边界；epics 5.1/5.2 划分 |
| DC-4 | 实例化事件 | **新增 `AgentInstantiated`（reliable 单通道）** | 不发事件（弃用：Agent 生命周期可观测是 5.6 隔离日志/5.7 Phoenix 追踪的基础；审计合规型事件与 AgentDecided 同族）；双通道（弃用：`DualChannelEventBus` RELIABLE 模式只走 Outbox/RabbitMQ 路径（dual_channel_event_bus.py L58-65），登记 redis_channel 只会产生死配置——51 个既有登记中 reliable 单通道 25 个是最大组） | architecture.md §10.1 事件审计定位；AgentDecided 通道先例；事件命名偏离 or.md 见 D-6 |
| DC-5 | 异常子域 | **新建 agent 子域 440-449**（440/441 两个异常平铺，不设子域基类） | 复用 entity/business 通用异常（弃用：配置资产错误与角色限制语义无法由 242/243 精确表达，监控无法精确告警） | `_code_ranges.py` 独立段先例（data_source/debate/tool_version）；debate 继承链先例 |
| DC-6 | 入口形态 | **CLI 独立入口**（`sisys-agent instantiate --role ceo`，agent_cli.py 仿 ocr_cli.py + pyproject script 注册） | a) REST API（弃用：架构文档执行端点属 5.3+，且 API 强制认证中间件成本由 Epic 7 承接）；b) 纯服务无入口（弃用：违反 Epic 4「未接线 ≠ done」团队协议，用例将成为第 51 个休眠端口）；c) document_commands.py 式 subparsers（弃用：该文件 parser 无挂载点，属未接线资产，照抄即制造死代码） | NFR-IF-01（CLI 覆盖 agent 模块）；ocr_cli.py 唯一真实接线先例 |
| DC-7 | AgentConfig 加载器层归属 | **domain 纯 dataclass + application 端口 + infrastructure YAML 解析** | core-domain §17.3.6 的 `AgentConfig(BaseModel)+from_yaml`（弃用：Pydantic 入 domain 违反零依赖硬约束，CI 必挂） | CLAUDE.md Hard Constraints；偏离声明 D-2 |
| DC-8 | TTL 收敛 | **state_ttl 默认 86400（AgentConfig 值对象层唯一默认值真源），范围 60~2592000，`save(agent, ttl)` 必填参数化由用例显式传入** | 三处文档不一致值（24h-30d / 3600 / 86400）——以 SessionStorage 默认 86400 为基准收敛，范围数字对齐 RedisSnapshotStore `set_ttl`（其抛 ValidationError(201)；本 Story 异常类型为 AgentConfigError(440)——**仅对齐范围数字，不对齐异常类型**） | architecture.md §11.2.5；core-domain §17.3.6；SessionStorage 默认值 |

### 已知下游风险（本 Story 不处置，消费方 Story 决策）

1. **双 agent_id 轨道**：`LangGraphEngine`（`src/infrastructure/agent_orch/langgraph_engine.py` L71-72）执行时自铸 `agent_id = uuid.uuid4()` 并据此发布 AgentDecided——与本 Story 用例 `uuid.uuid4()` 生成的实体 agent_id（Redis 键 `sisys:agent:{agent_id}`）是两条互不相通的轨道。若 5.3 不收敛，`AgentDecided`（引擎铸 ID）与 `AgentInstantiated`（实体 ID）将无法按 aggregate_id 关联，5.6/5.7 观测链路断裂——5.3 引擎消费 Agent 实例时必须决策收敛方案（复用实例化产出的 agent_id 或显式桥接映射）。
2. **`AgentRepository.get_by_id` 消费契约未定**：5.1 仅有实例化写入 + 验收读回；`Agent | None` 的 None 语义（键不存在 vs TTL 过期失效）与读回契约的消费方（预计 5.3 工作流加载 Agent）尚未定义，5.3 立项时定契约。**（R4 补）持久化丢失窗口**：测试实例实测 `appendonly no` + `save 3600 1 300 100 60 10000`（Redis 默认策略，无配置挂载）——MVP 演示稀疏写入下 Redis 重启最坏丢失 ≤60 分钟键；生产配置以部署 redis.conf 为准（部署文件为 `save 900 1` 形态——两者不一致属部署配置治理项）。TTL 到期/重启丢失后重跑 `sisys-agent instantiate` 即恢复（单次用例 ~2.5ms）。
3. **组合根 resolve 缓存残留**：AC-6.1 的 resolve 将 `redis_adapter`（SINGLETON）、`agent_repository`（SCOPED）、`agent_instantiation_use_case`（SINGLETON，含 DualChannelEventBus→RabbitMQEventBus/Outbox 链）钉入全局 Resolver 的 `_instances`/`_scoped_context`，在同一 xdist worker 进程内跨测试文件存活（四构造器均零 IO 已核验，仅首次发命令时绑定事件循环）。后续 Story 测试若 resolve 同名端口需沿用「手动组装」纪律，或届时经 `clear_singleton()`+`clear_scoped()` 显式清理——本 Story「resolve 产物禁发命令」约束已闭环，无需额外处理。

### 设计文档偏离声明

> 90-8 先例机制：实施与设计文档冲突时显式声明，实施后同步更新文档。

| # | 冲突点 | 偏离内容 | 实施后同步动作 |
|---|--------|---------|---------------|
| D-1 | core-domain §17.3.2 六态 AgentState（含 CHECKPOINTED） | 采用代码五态 AgentStatus | Task 8 在 core-domain-design.md §17.3.2 补注「CHECKPOINTED 延至 5.10，五态为 MVP 事实标准」 |
| D-2 | core-domain §17.3.6 `AgentConfig(BaseModel)` + `from_yaml()`（L1478/L1497）+ 全量 schema（identity.role 自由文本「战略决策者」/ capabilities.tools+max_context_length+reasoning_mode / llm_config.preferred_models 列表） | ① 层归属：domain 纯 dataclass，Pydantic/YAML 全部下沉 infrastructure；② 字段裁剪与语义改写（非仅层归属）：role 枚举键化（「战略决策者」→「ceo」）、capabilities 重组（→ responsibilities/domain_knowledge，语义取自 §17.3.1）、preferred_models 单值化（列表→preferred_model 单值，5.3 映射 LLMConfig.model） | Task 8 在 §17.3.6 补注层归属修正 + 字段裁剪与语义改写注记（取舍标准见 DC-3） |
| D-3 | architecture.md §11.2.4 实例化含 MEMORY.md/七档案加载 | 5.1 仅基础配置（YAML）；`.md` 档案属 5.2（FR-AC-02） | 无需改文档（Story 边界划分，非设计冲突），在 5.2 Story 引用即可 |
| D-4 | epics_v1.0.md L2030 将 5.3 描述为「CEO Agent 实例化」 | 系 epics 笔误（5.3 实为单 Agent 工作流） | 不修改 epics（历史规划文档）；dev agent 勿据此误解范围 |
| D-5 | epics_v1.0.md Story 5.1 建议测试路径 `tests/unit/architecture/test_agent_instantiation.py`、`tests/integration/test_agent_instantiation_integration.py` | 以项目实际目录结构为准（本 Story 测试分类表的全套路径）——epics 建议路径未对齐项目 tests/ 实际组织（unit 下按层分目录、integration 无 `_integration` 后缀惯例、架构测试命名 `test_arch_*`） | 不修改 epics；dev 以本 Story 测试分类表为准 |
| D-6 | or.md（`_bmad-output/planning-artifacts/or.md` L134 AGENT 协作事件流转）规划事件名 `AgentInitialized`（链上 AgentTaskAssigned 等其余事件亦未在任何事件清单登记，属规划稿命名） | 采用 `AgentInstantiated`——对齐 FR-AC-01「实例化 Agent 角色基础」术语与 `[Aggregate][EventName]` 命名规范（Agent + Instantiated，与 AgentDecided 过去分词同族） | 不修改 or.md（历史规划文档，同 D-4 处置）；dev agent 勿据 or.md 误解事件名 |
| D-7 | architecture.md §2 拓扑「应用层 AgentUC → 领域层 Agent 实体/AgentService/AgentRepo」三层规划（另见 §13.2 L1738 agent_service.py、§13.18.1 L2529 映射表；or.md 三.1.(4) 将「AGENT 实例化」列为 AgentService 领域接口；`src/domain/services/agent_service.py` 现状未落地） | MVP 以 `application/use_cases/agent_instantiation.py` 应用层用例实现实例化编排（R2 应用层用例先例，orchestration_service/run_tool_chain_use_case 同构），不新建 domain AgentService | 无即时文档修改；Story 5.4（EIP/Agent 服务接口消费方）立项时决策回迁——届时评估用例逻辑是否下沉领域服务 |

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

**验收测试骨架（data_source + skill_data_collection 最新范本）——R6 强制：** `FEATURE` 常量 + `@scenario(FEATURE, "场景名")` 显式绑定（场景名从 .feature 复制粘贴，收集数 ==13 校验）；`context` fixture（`_tenant`/`_loop`/`_redis_client`——场景级 `aioredis.Redis(decode_responses=True)`，skill_data_collection L82-113）；服务级组装 = `resolve("agent_config_loader")` + `RedisAgentRepository(adapter=RedisAdapter(redis_client=ctx["_redis_client"]))` 手动组装 + `InMemoryEventBus()`；`_run_async` helper；Background given 内 `pytest.skip(f"Redis not available: {exc}")`；断言客户端一律 `ctx["_redis_client"]`；teardown 逐 agent_id 精确 delete + 同循环 close；异常断言 `isinstance(context["error"], AgentRoleNotSupportedError)` + `error.code == "EXCEPTION_441"`。

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
| **事件流转规划** | `_bmad-output/planning-artifacts/or.md` L134（D-6 冲突点：规划名 AgentInitialized） |
| **调研输入** | 5 并行调研 Agent 报告（agent_orch 代码现状 / Redis-LLM 基础设施 / 验收测试模板 / 架构文档 / 前序 Story 经验）+ 全仓 grep 核验 |

### 完成清单 Completion Notes List

- [x] **Task 8（2026-10-14 收尾）**: AC-6.2 收尾场景直接转绿（验证型合法预期；22 项清单+组合根/CLI 注册 grep 断言）；变异实证：文件名突变 agent_config→agent_config_MUTATED→红→还原绿；13 场景全量转绿 13 passed（收集数 == 13 校验通过）；三项质量门禁全绿——ruff src/+tests/ All checks passed、mypy 664 files no issues、pytest 全量回归（unit+contracts 9998+96 passed / integration+acceptance 1810 passed，12 failed 全部确证为预存环境缺失：six_layer PG 5433 连接拒绝 / neo4j_graph_layer 7688 连接拒绝 / epo-ops HTTP 400 外部 Key 缺失——三文件与 Story 5.1 改动域零交集，失败形态均为连接拒绝/外部 API 非 assert 回归；回归中同步修复 1 个既有配套测试 test_exception_handlers Map 完备性清单——新增异常注册的合法配套维护）；分层覆盖率门禁全过（domain 97%≥90 / application 90%≥85 / infrastructure 86%≥75 / overall 89%≥80）；文档同步：core-domain-design §17.3.2 D-1 五态注记 + §17.3.6 D-2 层归属/字段裁剪注记、sprint-status 5-1→review、Story Status→review、§10.1 事件行终态核对在案
- [x] **Task 7（2026-10-14）**: tests/unit/architecture/test_arch_agent_instantiation.py 五验证器 13 用例（A domain 零依赖×4 / B YAML 边界×2——domain 全目录 rglob 零 yaml+解析链新增仅加载器一处（限定断言面，不触 frontmatter/event_bus_config_loader 存量）/ C 依赖方向×4 / D 组合根唯一装配×2（rglob 扫描类名实例化）/ E ruff isort×1）；编写期自纠 1 处：YAML 断言初版全文文本匹配误伤 docstring 提及 yaml 字样，改 import 级检查
- [x] **Task 6（2026-10-14）**: tests/integration/test_integration_agent_instantiation.py 落地（assembled fixture=real_redis+手动组装仓储+inline resolve loader+InMemoryEventBus+手动实例化用例；三场景：全链路读回一致+TTL 区间断言/exists-delete 幂等往返、P95 warmup+20 采样 quantiles[18]<200ms、gather 10 并发全成功互异+逐一 exists 禁 scan；pytestmark=[integration, redis, benchmark, xdist_group("agent-instantiation")]；验证型直接转绿 4 passed；变异实证：阈值 200→2 红→还原绿；连续 5 次全绿 ~10.5s；验收场景 AC-5.1/5.2/6.1/1.3 转绿 4 passed；teardown 残留复核 0；ruff 通过——编写期自纠 1 处（初版 case._repository 私有访问+noqa 违红线，重构为 fixture 显式返回仓储））
- [x] **Task 5（2026-10-14）**: agent_cli.py 落地（仿 ocr_cli 接线模式：bootstrap+resolve+build_parser+main(argv)->int+asyncio.run；add_subparsers(required=True) 防裸调用 AttributeError 裸崩；_parse_role 两道守卫=except ValueError 映射 441+SUPPORTED_ROLES 预检；finally peek_singleton("redis_connection_manager") 关池禁全量 shutdown；红 18→绿——红阶段自纠 2 处测试用例缺陷（UUID/AgentRole 误比较、"CEO " 误入非法穷举）；变异实证：删 except 分支→3 断言捕获 ValueError 逃逸、还原绿）；pyproject [project.scripts]+[tool.poetry.scripts] 双注册；poetry install 重生成 entry point 后端到端冒烟通过（/tmp 独立 cwd：UUID 单行 stdout、Redis 6380 键存在 TTL 86390、退出码 0/1/2 实测、Outbox 失败仅记日志 exit 0——Subtask 5.5 前置 ③ 预期行为实证、is_success=False 真实失败面分支亦实证）；链路 L5 绿灯
- [x] **Task 4（2026-10-14）**: InstantiateAgentUseCase 落地（守卫 SUPPORTED_ROLES frozenset 常量真源→加载→构建 list 转换→save(ttl=config.state_ttl)→publish 失败两分支记日志不回滚；242 透传用例以 object.__setattr__ 绕过 VO 模拟极端缺陷；红 20→绿；变异实证：注释发布调用→编排顺序+事件字段 2 断言红、还原绿）；AgentInstantiationResult DTO 模块内定义；组合根注册 agent_instantiation_use_case（SINGLETON 工厂 resolve 三依赖，interface 绑定自身类型）+ 契约测试 11 维度 12 用例 passed（链路 L3 绿灯）；验收场景 AC-1.1/1.2/3.1/4.1 转绿（4 passed，服务级真实组装）
- [x] **Task 3（2026-10-14）**: AgentRepository 端口（domain Protocol 四方法）+ RedisAgentRepository（组合 RedisAdapter+build_key("agent",...)+单 field latest JSON blob+expire+显式重建 UUID/Enum/datetime/list；红 22→绿；变异实证：AgentStatus 重建改透传 str→isinstance 断言红、还原绿；连接异常→StorageError(cause=exc) 包装（绿阶段自纠：from exc 仅设 __cause__，DomainError.cause 属性须构造参数传递）；TTL 防御校验 440+upsert 语义+fakeredis 回归全覆盖）；组合根注册 agent_repository（SCOPED）+ 契约测试 11 维度 12 用例 passed（链路 L1 绿灯）
- [x] **Task 2（2026-10-14）**: 循环 A——AgentConfig 值对象（frozen+falsy 判空+state_ttl 闭区间 60~2592000 钉端点+preferred_model 空串归一 None；红 20→绿；变异实证：上界 2592000→259200 突变后 test_ttl_2592000_upper_bound_valid 红、还原绿）；循环 B——AgentConfigLoader 端口（application Protocol）+ YamlAgentConfigLoader（asyncio.to_thread+仓库根四级上溯锚定+isinstance(list) 守卫+未知键忽略+NoReturn 流分析修复 mypy）+ configs/agents/ceo_agent.yaml 生产资产（红 18→绿 38；变异实证：identity.role→roleX 突变后 6 用例红、还原绿）；组合根注册 agent_config_loader（SINGLETON）+ 契约测试 11 维度 12 用例 passed（链路 L2 绿灯）；验收场景 AC-2.1/2.2/2.3 转绿（3 passed）
- [x] **Task 1（2026-10-14）**: 循环 A——agent 子域异常 440/441 落地（AgentConfigError→SystemException→500、AgentRoleNotSupportedError→BusinessException→422；红 20 用例→绿；变异实证：HTTP_MAP 440 条目 500→502 突变后 test_config_error_maps_500 红、还原绿；四处登记=_code_ranges 双表+exceptions/__init__+EXCEPTION_HTTP_MAP+设计文档 §3.3.2 两处表）；循环 B——AgentInstantiated 事件落地（frozen dataclass 四 kw_only 必填+event_type init=False+aggregate UUID 对象守卫；红 11 用例→绿——其中 test_missing_single_required_field 红阶段自纠：dataclass 类型注解不强制运行时校验，改为真正省略字段构造；变异实证：aggregate_type→"AgentMutated" 突变后 2 断言红、还原绿）；双登记 event_channels.yaml+DEFAULT_MAPPINGS+architecture.md §10.1 事件表；tests/unit/domain/ 全量 2888 passed 零回归；AC-4.2 验收场景转绿
- [x] **Task 0（2026-10-14）**: 4 并行调研 Agent 全仓核验先例（领域契约/基础设施/测试模板/CLI 应用层四视角）；Gherkin 13 场景 + BDD 步骤实现落盘（@scenario 显式绑定 + context dict + 新模块延迟 import + pytestmark=[acceptance, redis, xdist_group("agent-instantiation")]）；红阶段验证通过（`pytest --collect-only` 收集数 == 13；`SISYS_USE_TEST_PORTS=1` 运行 13 场景全 FAILED 非 skip——ModuleNotFoundError/AssertionError 合法红，Redis 6380 在线前提成立）；deferred-work.md 补登记 L6 `session_storage`（L7 agent_engine/L8 AutoTriggerHandler 既有登记核对在案）；环境准备：sisys-redis-test 容器（6380）已启动
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
- `src/domain/exceptions/agent_exceptions.py`（440/441 两异常 + 继承链理由 docstring）
- `src/domain/value_objects/agent_config.py`（AgentConfig frozen dataclass + TTL 边界常量）
- `src/domain/ports/agent_repository.py`（AgentRepository Protocol 四方法）
- `src/application/ports/agent_config_loader.py`（AgentConfigLoader Protocol）
- `src/application/use_cases/agent_instantiation.py`（InstantiateAgentUseCase + AgentInstantiationResult + SUPPORTED_ROLES）
- `src/infrastructure/agent_orch/yaml_agent_config_loader.py`（YAML 加载器 + DEFAULT_CONFIG_DIR）
- `src/infrastructure/storage/redis/redis_agent_repository.py`（Redis 仓储 + 序列化静态方法）
- `src/interfaces/cli/agent_cli.py`（sisys-agent CLI 入口）（**路径迁移注记 2026-10-31**：D1 方案 A 入口上移后现位于 `src/entrypoints/agent_cli.py`——c176da99，本 File List 记录创建时点路径，pyproject 双注册已同步；Epic 5 终局审查 R1-N9）
- `configs/agents/ceo_agent.yaml`（CEO 基础配置资产）
- `tests/unit/domain/exceptions/test_agent_exceptions.py`（20 用例）
- `tests/unit/domain/events/test_agent_events.py`（11 用例）
- `tests/unit/domain/value_objects/test_agent_config.py`（20 用例）
- `tests/unit/infrastructure/agent_orch/test_yaml_agent_config_loader.py`（18 用例）
- `tests/unit/infrastructure/storage/redis/test_redis_agent_repository.py`（22 用例）
- `tests/unit/application/use_cases/test_agent_instantiation.py`（20 用例）
- `tests/unit/interfaces/cli/test_agent_cli.py`（18 用例）
- `tests/unit/architecture/test_arch_agent_instantiation.py`（13 用例）
- `tests/contracts/test_port_contract_agent_repository.py`（11 维度/12 用例）
- `tests/contracts/test_port_contract_agent_config_loader.py`（11 维度/12 用例）
- `tests/contracts/test_port_contract_agent_instantiation_use_case.py`（11 维度/12 用例）
- `tests/integration/test_integration_agent_instantiation.py`（4 用例：全链路×2 + P95 + 10 并发）
- `tests/acceptance/test_acceptance_agent_instantiation.feature`（13 场景）
- `tests/acceptance/test_acceptance_agent_instantiation.py`（13 @scenario 绑定 + 全部步骤实现）

**修改的文件/Modified Files:**
- `src/composition_root.py`（Story 5.1 段：3 端口注册——agent_config_loader/agent_repository/agent_instantiation_use_case）
- `pyproject.toml`（`[project.scripts]` + `[tool.poetry.scripts]` 双注册 `sisys-agent`）
- `src/domain/events/agent_events.py`（追加 AgentInstantiated）+ `src/domain/events/__init__.py`（导出）
- `src/domain/exceptions/_code_ranges.py`（agent 440-449 双表登记）+ `src/domain/exceptions/__init__.py`（导出）
- `src/interfaces/api/exception_handlers.py`（EXCEPTION_HTTP_MAP 精确注册 440→500/441→422 + import）
- `tests/unit/interfaces/api/test_exception_handlers.py`（Map 完备性清单配套维护 +4 行——Task 8 完成清单有记录，R5 终审补列 File List）
- `configs/event_channels.yaml` + `src/infrastructure/messaging/channel_router.py`（AgentInstantiated 双登记）
- `docs/architecture/sisys-uni-exception-design.md`（§3.3.2 编码分配表 agent 行 + 子域范围表 agent 行）
- `docs/architecture/architecture.md`（§10.1 领域事件列表补 AgentInstantiated 行）
- `docs/architecture/sisys-core-domain-design.md`（§17.3.2 D-1 五态注记 + §17.3.6 D-2 层归属/字段裁剪注记）
- `_bmad-output/implementation-artifacts/deferred-work.md`（补登记 L6 session_storage）
- `_bmad-output/implementation-artifacts/sprint-status.yaml`（5-1 → in-progress → review）

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
3. [x] Architecture constraints extracted 架构约束已提取（R1/R2/R4 层归属 + 偏离声明 D-1~D-7）
4. [x] Previous story learnings integrated Epic 4 回顾教训已整合（7.1-1/7.1-2/7.1-3 + 团队协议）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。
> （本节与版本历史为审查追溯记录，dev agent 实施时无需阅读。）

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
| 14 | 【Round 2】事件 Schema 三必填字段（role/name/config_version）非 kw_only 裸声明——DomainEvent 基类字段全带默认值，类定义即抛 `TypeError: non-default argument follows default argument` | P0 | 三字段加 `field(kw_only=True)`（对齐 AgentDecided「kw_only 必填」先例）；`aggregate_id=str(agent_id)` 改 UUID 对象（基类契约 `uuid.UUID \| None`） |
| 15 | 【Round 2】Task 4 编排顺序「加载配置→角色守卫」倒置——`execute(CFO)` 先触发 cfo_agent.yaml 缺失的 440，AC-1.2 的 441 不可达 | P0 | 编排改为「角色守卫→加载配置」，单测断言 guard 先于 loader.load 且非 CEO 时 loader 未被调用 |
| 16 | 【Round 2】`save(agent, ttl=None)` None 语义未定义且 TTL 进仓储签名零先例（10+ 实体仓储端口无 TTL；TTL 属缓存/会话端口；模板 RedisSnapshotStore 用 set_ttl+实体字段携带，Agent 实体无 TTL 载体） | P1 | `save(agent, ttl: int)` 必填参数化——用例从 `AgentConfig.state_ttl` 显式传入（值对象是唯一默认值真源），AC-3/端口签名/Task 3/Task 4/矩阵五处同步 |
| 17 | 【Round 2】Loader 默认目录 cwd 相对 `configs/agents/` 零先例（全仓文件加载先例均 `Path(__file__)` 锚定）——CLI 任意 cwd 运行断链 | P1 | 改 `Path(__file__).parent.parent.parent.parent / "configs" / "agents"` 仓库根锚定（对齐 event_bus_config_loader.py L18），构造注入可覆盖 |
| 18 | 【Round 2】`get(agent_id)` 命名偏离项目主流（11 个仓储端口均 `get_by_id`；`get` 是缓存端口命名） | P1 | 改名 `get_by_id`（端口签名/AC-3/Task 3/签名注释四处；契约测试 REQUIRED_METHODS 以签名为唯一事实源传导） |
| 19 | 【Round 2】两项规划偏离未声明：or.md L134 规划事件名 `AgentInitialized`；architecture.md §2/§13.2/§13.18.1 三层规划 AgentService 含实例化领域接口（未落地） | P1 | 新增偏离声明 D-6（命名对齐 FR-AC-01「实例化」术语）、D-7（MVP 应用层用例实现，5.4 决策回迁）；连带 D-1~D-7 计数、Subtask 8.5、调试日志表 or.md 行 |
| 20 | 【Round 2】architecture.md §10.1 领域事件完整列表（26 事件）不含 AgentInstantiated——新增事件绕过权威清单登记 | P1 | 待修改清单补 §10.1 行；Task 1 循环 B 重构行同步追加（对齐异常文档 §3.3.2 随 Task 1 同步模式） |
| 21 | 【Round 2】科学性补强 5 项：D-2 未涵盖 §17.3.6 schema 语义改写（role 枚举键化/capabilities 重组/preferred_models 单值化）；DC-3 取舍标准隐式；双 agent_id 轨道（引擎 L71-72 自铸 vs 实体 uuid4）与 get_by_id 消费契约未定的下游风险零记录；publish 失败真实面是 `PublishResult.is_success=False` 非 raise；Outbox 语义（RELIABLE via Outbox）与跨存储无 ACID 边界未注记 | P1 | D-2 措辞扩展；DC-3 补「保留有近期消费方/裁剪无认领方 + 回填时机」标准；Dev Notes 新增「已知下游风险」小节；Task 4 红行补两分支断言；AC-4 补 via Outbox 与跨存储次序理由；CLI 契约补非幂等明示；440 维持并补 document_metadata.py 先例与 440/242 边界说明 |
| 22 | 【Round 3】teardown 自相矛盾：`delete_pattern(f"{tenant 前缀}:agent:*")` 匹配不到任何键（build_key 产出 `sisys:agent:{uuid}` 无租户维度，TestTenant 前缀无存储层叠加机制）；通配 `sisys:agent:*` 在多 worker 共享 6380 下会误删并行键 | P0 | BDD 约束改为「context 记录 agent_id，逐键精确 delete」；隔离表资源唯一性/外部服务隔离两行同步；Task 6 红行与 DoD 同口径 |
| 23 | 【Round 3】验收组装 `resolve("agent_repository")` 跨循环死连接：SCOPED 实例钉住全局 Resolver，SINGLETON redis_client 跨 function-scope 循环复用，redis-py 5.3.1 检测不到池内死连接，后续场景抛 "Event loop is closed"（仓库存档教训） | P0 | AC-1.1/AC-3.1 场景与 Subtask 4.5 改为手动组装 `RedisAgentRepository(adapter=RedisAdapter(redis_client=ctx["_redis_client"]))`（skill_data_collection L318 先例）；resolve 仅做 AC-6.1 接线断言且禁发命令（全链构造零 IO 已代码级验证）；禁止行为清单点名 |
| 24 | 【Round 3】Task 5 红阶段「main 注入 Mock 用例」不可写：registry 无 override 公开 API、双 bootstrap 抛 ConflictError、ocr_cli 单测只测纯函数无 main() 注入先例 | P0 | 注入机制定稿为 monkeypatch `agent_cli` 模块级 `bootstrap`/`resolve` 属性 |
| 25 | 【Round 3】AC-5.2「Redis 键数=10」scan 计数会误计并行 worker 键 | P0 | 改为对记录的 10 个 agent_id 逐一 `exists()` + 互异断言（AC-5.2 验证标准/场景行/Task 6 三处） |
| 26 | 【Round 3】agent_cli 是首个打开 Redis 池的 CLI：退出不关池留 ResourceWarning；全量 shutdown() 会惰性实例化 PG/Qdrant/Neo4j manager | P1 | 绿阶段补 finally `peek_singleton("redis_connection_manager")` + close()，禁用全量 shutdown() |
| 27 | 【Round 3】冒烟三前置缺失：SISYS_USE_TEST_PORTS 对 CLI 子进程无效（只读 REDIS_PORT 默认 6379）；pyproject 改后须 poetry install 重生成 entry point；无 PG 时 RELIABLE→Outbox 落库失败仅记日志 exit 0 属预期 | P1 | Subtask 5.5 补三个前置说明，防误判 |
| 28 | 【Round 3】可行性补强 8 项：P95 采样缺 warmup+quantiles 法（docker_sandbox L1001-1012 先例）；xdist_group 不保独占 CPU（-n 0 复跑口径）；@scenario 收集期陷阱（ScenarioNotFound 整文件炸/漏绑定静默不收集，收集数==13 校验进 Task 0.4/8.6）；红阶段前提 Redis 在线；event_loop 来源 pytest-asyncio 0.24 弃用 fixture 注记；autonomous_invocation_execute L69-87 实为同步客户端（异步模板勘正为 skill_data_collection L82-113）；mock_redis fixture unit 不可见；契约测试 DummyResolver 须提供 redis_adapter 等依赖名 | P1/P2 | AC-5.1 补采样法；性能隔离行补 CPU 口径；R6/BDD 约束补收集陷阱与 event_loop 注记；Subtask 0.4 补前提与校验；复用表/BDD 约束勘正模板指向；Subtask 3.5 补可见性说明 |
| 29 | 【Round 4】skill_data_collection 组装先例行号失实：L362 实为场景绑定 pass，`RedisAdapter(redis_client=context["_redis_client"])` 在 L318（Round 3 修复 #23 自身引入） | P1 | Subtask 4.5 与台账 #23 两处改 L318（回归验证 Agent 实测） |
| 30 | 【Round 4】边界缺口 P1×4：①`capabilities.responsibilities: []` 空列表漏检风险（Agent.validate() 不校验非空，VO falsy 判空是唯一防线）；②`capabilities.*` 标量字符串静默陷阱（`tuple("战略方向")` 逐字符展开无异常）；③`--role CEO` 大写归一化无测试（漏 `.lower()` 时合法输入误报 441，现有用例无法暴露）；④argparse `add_subparsers` 默认非必选，裸调用 `sisys-agent` 取 args.role 抛 AttributeError 裸崩逃逸统一异常体系 | P1 | Task 2 红行补空列表/标量/state_ttl 非整数/YAML 空文件/未知键五类用例 + 绿行补 isinstance(list) 守卫与 falsy 判空；Task 5 红行补 "CEO" 大写与 main([]) 裸调用用例 + 绿行补 `add_subparsers(required=True)`；Task 2 值对象红行补 TTL 端点值（60/2592000 合法、59/2592001 抛） |
| 31 | 【Round 4】边界补强 P2×7：preferred_model 空串语义未定稿；YAML 未知键策略未定义；supported_roles 真源未指定（V1 扩展维护性）；二次 save upsert 语义无测试；CLI 退出码未定值（0/1/2 契约）；输出格式未定形（UUID 单行 stdout）；组合根 resolve 缓存跨测试文件残留无注记 | P2 | preferred_model 空串归一化 None 定稿（Schema 注释+VO 测试）；未知键策略定稿「忽略」（Task 0 YAML 块下声明+Task 2 用例）；SUPPORTED_ROLES frozenset 常量真源（Task 4 绿行+异常契约节）；Task 3 红行补 upsert 用例；退出码 0/1/2 与 UUID 单行输出定稿（Task 5 红绿行）；已知下游风险补第 3 条 resolve 缓存注记 |
| 32 | 【Round 4】回归修正：「integration 目录零 resolve() 先例」言过其实（traceability L171-174 与 session_middleware_wiring L75 有 inline 先例）；「11 个仓储端口」计数口径不唯一（10 直写/12-13 含继承）；document_metadata raise 闭合行 L104 | P2 | 措辞收敛「无共享 resolve() fixture 基建 + inline 用例见 traceability」；改「10+ 端口直接定义」；L100-104 |
| 33 | 【Round 5】终态微修 4 项：复用表 document_metadata 行号传播不全（L100-103→L100-104）；AC-5 docker_sandbox 引用未指明文件（acceptance 版 L1001-1012 与 benchmark 版 L71-85 是两个文件）；Task 3 红行缺「连接异常→StorageError 包装」用例（AC-3 第 4 条/追溯矩阵/DoD 三处要求但红行漏列，dev 照红行实现会漏测）；修复台账对 dev agent 无实施价值未标注 | P3 | L59 行号补传播；AC-5 补完整路径消除歧义；Task 3 红行补 StorageError 用例（AsyncMock side_effect 模拟连接异常）；台账节加「dev agent 实施时无需阅读」标注 |

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 2026-10-14（Round 1 / Round 2 / Round 3）
**审查模式:** R1=5 并行视角调研（正确性契约审计 / 边界缺陷猎手 / 架构规范一致性 / 测试质量审计 / 盲审冷审）+ C3 三视角方案评审；R2=双视角（R1 修复回归核查 + 科学性复审）+ C3 双视角评审（往返一轮裁定「优秀」）；R3=双视角（R2 修复回归核查 + R1/R2 累计一致性/D4 设计）+ C3 合并评审（合格+实测修订指令，明示修订后可直接实施）
**审查范围:** R1=`git diff ed3a2053..1376dd81`（实施提交 ea0c0564 + be17899c）；R2=commit 1376dd81 修复自身的回归面与残留项；R3=commit cc0a25f1 修复自身的回归面 + 累计一致性终查

#### 已修复 Patch（Round 1 — P0×4 + P1×3 + P2×1，逐项含来源视角/证据/修复）

- [x] **R1-F1【P0·红线】测试文件 6 处 `# type: ignore` 抑制注释**（来源：盲审+测试质量审计；grep 证实全 tests/ 树仅 5-1 新增 4 文件存在，违反 Hard Constraint 且与 Story 自身 Task 6 自纠 noqa 先例矛盾）→ 六种等价重构消除：`_TracingEventBus` 子类替代实例方法赋值（+删孤儿 `Any` import+补 `DomainEvent` import）、空 dict 动态解包 ×2、内建 `setattr` ×2、纯删死注释 ×1；mypy 四文件基线全绿验证
- [x] **R1-F2【P0·契约逃逸】`_read_yaml` 未捕获 OSError/UnicodeDecodeError**（来源：边界猎手+盲审+正确性审计三视角独立实测——目录占位抛裸 `IsADirectoryError`、GBK 内容抛裸 `UnicodeDecodeError`（ValueError 子类），打破「全部失败路径统一 440」成文承诺且零测试覆盖）→ `open()` 移入 try + 三异常类逐类包装 440（reason 分列「YAML 解析失败/编码非法/不可读」），role 上下文透传（顺带修复 P3「440 丢失 role」）；新增目录占位+GBK 两用例（红→绿）
- [x] **R1-F3【P0·原子性】save 的 hset+expire 两命令分离**（来源：边界猎手；崩溃窗口产生无 TTL 永不回收孤儿键，击穿「非幂等+TTL 自然回收」设计假设——agent_instantiation/agent_cli docstring 双处声明；次要：非 int TTL 裸 TypeError 逃逸）→ MULTI/EXEC pipeline 原子提交（`async with raw_client.pipeline(transaction=True)`，对齐 semantic_cache 先例）+ TTL 类型校验（isinstance int 拒 bool，与 VO 同式）+ 移除死分支 `except AgentConfigError: raise`；测试工厂 pipeline 替身（22 用例断言不变）+ 非整数三形态/原子提交/连接异常 execute 注入新用例；RedisSnapshotStore 同款存量缺陷登记 deferred-work
- [x] **R1-F4【P0·事件类型漂移】`DomainEvent.from_dict` PEP 563 字符串注解失效**（来源：边界猎手实测——`AgentInstantiated` 往返后 `agent_id` 为 str、`≠ aggregate_id`；根因 base.py `f.type` 字符串 vs 类型对象 `is` 比较恒 False，全部 28 个 PEP 563 事件模块 UUID/datetime/Enum 还原分支为死代码；RELIABLE 生产链路 Outbox 轮询真实经过；EntityValidationError/已修复形态双先例佐证）→ `_field_type_hints` 类级缓存（get_type_hints，GIL 良性竞争注释）+ 畸形 payload 包装 242（`(ValueError, TypeError)`，实测 Enum 非法值抛 ValueError）；新增往返 UUID 保真+畸形 242 两用例；**闭式必红清单 8 断言/5 文件同步类型化**（archive×3/debate 单测/契约×2/red_blue 验收 + 2 处「项目历史行为」docstring 口径改写）；src 侧佐证：ToolRegistryService 声明 UUID 而回放路径传 str 属存量缺陷现形（契约方向：声明类型为准）
- [x] **R1-F5【P1】agent_cli 健壮性**（来源：边界猎手；bootstrap 在 try 外 ImportError 裸 traceback；finally 关池异常反噬主结果——成功被误报 exit 1/失败丢根因）→ bootstrap 移入 try（成功后路径逐字不变）+ `_close_redis_pool` 内部防御记 warning（含异常类型）；新增两用例（红→绿）
- [x] **R1-F6【P1】加载器可选字段静默类型收编**（来源：三视角；`preferred_model: 123` 静默变 None、`default_isolation_level: 5` 静默回落 L4，配置手误无感知）→ 非 null 非 str 显式 440 + 两用例
- [x] **R1-F7【P1】测试断言卫生**（来源：测试质量审计；:256 死消息裸元组、:148 命名对调）→ `await_count == 1` 活断言 + 更名
- [x] **R1-F8【P2】并发场景失败路径键泄漏**（来源：测试质量+盲审；gather 在 try/登记之外，部分失败时已落库键逃逸 teardown）→ 协程内即时登记 + gather 移入 try（integration+acceptance 两处）；验证性质：结构性加固经代码审查+happy path 实跑（集成层 mock 禁令不做故障注入），与 F3 原子 pipeline 协同兜底
- 变更文件清单（R1）：`src/domain/events/base.py`（唯一共享代码变更——F4 根因修复）、`src/infrastructure/agent_orch/yaml_agent_config_loader.py`、`src/infrastructure/storage/redis/redis_agent_repository.py`、`src/interfaces/cli/agent_cli.py`、tests 13 文件（含 F4 必红清单 5 文件——R5 终审计数勘正）、Story 文件本节、deferred-work.md

#### 已修复 Patch（Round 2 — P2×3 + P3×6；R1 修复回归核查零 P0/P1 回归、科学性 9/10）

- [x] **R2-F1【P2】outbox `get_unpublished` 毒消息隔离**（来源：回归核查——R1-F4 使 payload 反序列化 fail-loud（242）后，既有批量裸推导被放大：单条畸形 payload 卡 FIFO 队头每轮重炸、其后全部合法 pending 事件永久阻塞 reliable 通道；R1 前形态（字符串注解静默透传）不可能触发，属 R1 回归面闭环责任；git 历史级因果链证成）→ 逐条 try/except 隔离：未超限毒行 mark_failed 记 error、超限（retry_count ≥ max_retries）降级单行 warning 不写库（毒 payload 静态垃圾 vs 发布失败可恢复的对比论据）；新增毒消息隔离+有界化两用例（红→绿）；**变更 `outbox_repository.py`（第二个共享文件，单方法限定）**；残余写放大登记 D11
- [x] **R2-F2【P2】AgentConfig VO tuple 类型守卫**（来源：科学性实测——`responsibilities="战略方向"` truthy str 越过 falsy 判空静默通过，用例层 `list()` 逐字符展开为 `['战','略',...]` 静默数据损坏，与加载器标量陷阱同款；VO 是运行时唯一防线）→ `isinstance(tuple)` 守卫（类型错先于空值错）+ str/list 两形态用例（红→绿）；全仓 3 处构造点均传 tuple 零回归（grep 证实）
- [x] **R2-F3【P2】测试断言活性（D9(a)(b) 核销）**：subdomain 区间断言锚定类 `code` 属性真源（防参数字面量恒真）+ StorageError `code=="EXCEPTION_103"` 断言三位点补齐
- [x] **R2-F4【P3】correlation_id/causation_id 包装 242**（来源：回归核查——R1「与核心字段同构」宣称不完整，两追踪字段仍裸 `uuid.UUID()` ValueError 逃逸）→ `_parse_optional_uuid` 助手（三元组对齐 timestamp 式）+ 两用例（红→绿）
- [x] **R2-F5【P3】`get_type_hints` NameError 包装 242**（来源：双视角共同发现——解析调用点在 242 包装圈外；49 事件类实测零失败，防御性闭合）→ `_field_type_hints` 内 except NameError 包装（缓存未写入无毒化）+ 动态类注入字符串注解用例（红→绿；不使用注解字面量语法——静态检查器对字符串注解做未定义名检查）
- [x] **R2-F6【P3】pipeline 测试补「两命令同 key」断言**（堵「hset A 键 + expire B 键」退化盲点）
- [x] **R2-F7【P3】GBK 用例补 reason 分级断言**（防 PyYAML 行为漂移致 reason 分级静默劣化）
- [x] **R2-F8【P3】文档卫生**：`_read_yaml` 删「先于 ValueError 家族」残留措辞（三分支互不相交实测成立）；`_deserialize_value` docstring 注记非 str 标量放行策略（有意宽容非遗漏）
- [x] **R2-F9【P3】加载器 section 级守卫**（来源：回归核查——F6 只闭合标量面，`llm_config: 123`/`eip_config: []`/`memory_config: "86400"` 仍静默吞）→ 语义表定稿（None/缺失/`{}` 合法回落 vs 非 None 非 dict 440）+ 守卫作用于 `or {}` 之前的 raw 值 + 三形态用例（红→绿）+ **「三可选段缺失→默认值」正向锚定用例**（原验证门盲区——误实现下全门静默绿）
- 变更文件清单（R2）：`src/infrastructure/messaging/outbox/outbox_repository.py`（共享文件）、`src/domain/events/base.py`、`src/domain/value_objects/agent_config.py`、`src/infrastructure/agent_orch/yaml_agent_config_loader.py`、tests 7 文件、Story 本节
- **R2 终态**：5-1 自身可处置的 P0/P1/P2 全部清零；跨 Story/治理域留项 D1(P1)/D2(P2) 于 deferred-work.md 登记且带核销触发器

#### 已修复 Patch（Round 3 — P1×1 + P2×1 + P3×4；R2 修复回归核查揪出 R2-F1 两处新破口并闭环）

- [x] **R3-F1【P1】outbox SELECT 增加 retry_count < max_retries 过滤**（来源：回归核查——R2-F1 隔离意图落地但未闭合：超限毒行永不退出选择集（无终态迁移路径：mark_pending 前置封死/cleanup 只清 published/DLQ 仅消费侧调用），累积至 batch_size 后 get_unpublished 恒返回空批、合法事件静默停发——队头阻塞以隐蔽形态复发；测试盲区：SELECT WHERE 语义全 mock）→ 列比较过滤 + 白盒语句构造断言（compile 文本锚定列比较，mock 模式可达）；超限 Python 分支防御性保留（注释勘正：非竞态防御，真实流程经 SELECT 物化不可达）；D11 随之收敛为惰性滞留形态
- [x] **R3-F2【P2】mark_failed 错误消息按列宽截断**（来源：回归核查——R2 新调用内嵌任意长 payload repr，error_message VARCHAR(1000) PG 超长抛错不截断 → 整周期事务失败回滚 → 毒标记丢弃 + 下轮同形失败 = 永久活锁；既有 poller 路径同款暴露 R2 结构性加宽）→ `error[:_ERROR_MESSAGE_MAX_LENGTH]`（isinstance(String) 收窄取列宽，mypy 零告警形态经评审实测验证；一处收口覆盖新旧调用点）+ 超长截断用例
- [x] **R3-F3【P3】get_type_hints 病态注解扩捕**（来源：回归核查+主审/评审双实测——R2-F5 只捕 NameError；裸 TypeError（字符串注解求值为裸特殊形式如 Optional 漏 [None]）会击穿 redis_subscriber 逐消息隔离（仅捕 ValueError/DomainError）；主审另实测 SyntaxError 形态（畸形表达式如 list[int[））→ `except (NameError, SyntaxError, TypeError)` 三形态均实测锚定 + 两红用例（裸特殊形式/畸形表达式，动态类 __annotations__ 注入——注解字面量语法会在类定义期求值不触发解析）
- [x] **R3-F4【P3】correlation_id/causation_id 空串容忍恢复**（来源：回归核查——R2-F4 把 "" 从「视同未提供」变为 242 拒收，外部生产方写 "" 的互操作事件将被消费侧隔离静默丢弃（比容忍更糟））→ `if not value: return None`（falsy 家族等价旧语义，fail-loud 收缩至非空畸形）+ ""→None 锚定用例；裁定理由入 docstring
- [x] **R3-F5【P3·D4 核销】验收 Background 下沉**（方案②——一致性 Agent 三候选对比推荐：删背景块 + 7 组装场景各前置 ping 行；.py 零改动/收集数 13 不变/Gherkin 文本与实际依赖一一对应；双态实证：有 Redis 13 passed、无 Redis 6 passed + 7 skipped——静态 6 场景脱离门控，验收信号恢复 ~46%）+ R6 模板级观察提炼
- [x] **R3-F6【P3】文档卫生**：v1.7.0 计数勘正三处（P1×4→P1×3，防 P2 双计）；尾部重复「更新说明」残块删除；440 触发面全子集回填（Story 异常契约表 + sisys-uni-exception-design.md §3.3.2——后者补齐 R1 起累计四批触发面）；D9(c) 补核销触发器；D11 重写（R3-F1 后形态）+ 补登记 deferred-work.md（含 InMemory 分叉/DLQ dequeue/process_one 伪 mark_pending/max_retries=0 病态参考）
- 变更文件清单（R3）：`src/infrastructure/messaging/outbox/outbox_repository.py`（共享文件）、`src/domain/events/base.py`（共享文件）、`tests/acceptance/test_acceptance_agent_instantiation.feature`、tests 2 文件、Story 本节 + sisys-uni-exception-design.md + deferred-work.md
- **R3 终态**：R2 引入的回归面（P1×1/P2×1）清零；5-1 可处置项累计全清；留项 D1/D2/D3/D6 残余/D7/D8/D9(c)/D11 均带核销触发器

#### 已修复 Patch（Round 4 — 纯文档/台账轮：P2×2 留项登记 + P3×4 文档处置；代码零变更）

- [x] **R4-F1【P2→D12】wheel 形态 configs/ 分发缺口**（来源：运维审计 F1——pyproject packages 不含 configs/，wheel/pip 形态 CLI 必现 440；Docker/k8s/源码树三形态自洽、全仓无 wheel 消费方证实）→ 登记留项 D12（核销触发：发布/打包专项 或 首个 wheel 消费方）；README Agent CLI 小节声明部署形态——**裁定不冒改打包配置**（改错形态比不改糟）
- [x] **R4-F2【P2→D13】CLI 全量 bootstrap 启动开销 10.4s**（来源：运维审计 F2——import 0.2s + bootstrap 7.7s≈157 端口注册 + litellm 出网拉取 + BGE tokenizer；实际用例 2.5ms；非 5-1 引入）→ 登记留项 D13（短期缓解 LITELLM_LOCAL_MODEL_COST_MAP=1 入条目；根治属组合根瘦身架构决策）——核销触发：5.3 批量消费前
- [x] **R4-F3【P3】D11 台账补强四处**（来源：回归核查 P3-1/P3-5 + 运维 F3——`_mark_failed_entity` :258 未截断（零生产调用方潜伏）、AuditOutboxModel.mark_failed 同款、运维 SQL 唯一恢复路径+零日志监控盲区、InMemory 分叉保持）→ D11 条目扩为六项收敛范围（①-⑥），Story 与 deferred-work 双同步
- [x] **R4-F4【P3】README 补「Agent 实例化 CLI」小节**（来源：运维审计 F6——README/部署指南零 sisys-agent 覆盖）→ 快速开始追加已交付命令块（UUID stdout/退出码 0-1-2/REDIS_PORT 前置/440·441·103 错误码速查/部署形态声明）+ 区分「路线图命令 vs 已交付入口」注记
- [x] **R4-F5【P3】下游风险 #2 补持久化丢失窗口**（来源：运维审计 F5；**C3 评审纠错**：原拟「RDB 900s/≤15 分钟」为部署配置文件值非测试实例实测——实测 `save 3600 1 300 100 60 10000` + `appendonly no`）→ 按实测写入（稀疏写入最坏丢失 ≤60 分钟；生产以部署 redis.conf 为准；两者不一致属部署配置治理项；重跑 instantiate 2.5ms 即恢复）
- [x] **R4-F6【P3】观察项登记**：F7 验收首跑疑似单键泄漏（未复现/差集=0/24h TTL 兜底——Round 5 收敛评审复现则升级）；F4 outbox 无 poller 宿主（RELIABLE 事件 pending 累积实证——deferred-work 部署面注记点名 CLI 路径）；F8 引导噪声（cost_metrics_handler 未注册 WARNING 预存 + litellm 价目表——归 D13/D8 相邻）
- 变更文件清单（R4）：README.md、Story 本节 + deferred-work.md——**生产代码与测试零变更**（HEAD 代码 bef902ad 经 R4 双视角实测 10083 passed + 双态验收 + CLI 冒烟全绿）
- **R4 终态**：运维就绪总评通过（P95 独立复测 3.57ms 远优 200ms 门限、退出码/错误码/可观测性实跑验证）；5-1 可处置项保持全清；新增 D12/D13 均带核销触发器

#### 收敛声明（Round 5 终审 · 2026-10-14 · 独立取证）

> **Story 5-1 代码审查收敛声明**
>
> 五轮审查闭环：**实施（ea0c0564，Task 0-8 + 9 处变异实证）→ R1（1376dd81，P0×4/P1×3/P2×1——事件类型漂移根因修复/管道原子化/440 契约闭合/红线清除）→ R2（cc0a25f1，P2×3/P3×6——outbox 毒隔离/VO tuple 守卫）→ R3（bef902ad，P1×1/P2×1/P3×4——重试耗尽过滤/错误串截断/D4 核销）→ R4（e60844d3，纯文档台账轮——D12/D13 登记+运维就绪落账）→ R5（终审，独立取证零 P0/P1/P2 新发现）**。P0 曲线 4→0→0→0→0，R2 起自身可处置 P0/P1/P2 持续清零，四轮修复无回归（终审全量实跑 10030+53 passed、CLI 冒烟退出码 0/1 实证、red_blue 回归面 36 用例全绿）。
>
> **残留清单（全部带核销触发器，非 5-1 可处置）**：D1（import-linter BROKEN，架构评审立项）、D2（EPO 4-1f 域）、D3（StorageError 语义拆分，5.3）、D6（VO 直构造残余，5.3/5.4）、D7（captive dependency，5.4）、D8（存量技术债，专项）、D9(c)（验证器 AST 化，下次触碰）、D11（outbox 终态六项，dead-letter 专项）、D12（wheel configs 分发，发布专项）、D13（CLI bootstrap 10.4s，5.3 批量消费前）；已核销 D4/D5/D10 无残留；F7 疑似泄漏观察项终审未复现（3 键全带 24h TTL），随收敛关闭。
>
> **终审遗留微修（本轮落账时已处置）**：R1 文件计数 10→13 勘正；File List 补 test_exception_handlers.py；终审发现 #3（§3.12 引用）经复核为**误报**（L276 原文已是 §3.3.2，如实记录不盲改）。
>
> **Story 状态处置：review → done**。依据：六项终审取证全部通过——周期五提交闭合无游离、关键修复逐项重取证成立、全量实跑零失败、留项台账 D1-D13 完整带核销触发器、文档终态与仓库事实一致；无任何需要代码变更的残留。

#### 需决策 Decision Needed

- [x] D4【P2·已核销】验收 Background ping 波及纯静态场景 → ✅ 核销于 Round 3（方案②背景下沉：删全 feature 背景块，7 个含服务组装场景（AC-1.1/1.2/1.3/3.1/4.1/5.1/5.2）各前置「假如 Redis 缓存服务可用」，静态 6 场景（AC-2.1/2.2/2.3/4.2/6.1/6.2——**勘正：原条目低估为 3 个**）脱离门控；收集数 13 不变（计数对象是 @scenario 函数非 feature 文件）；双态实证：有 Redis 13 passed / 无 Redis 6 passed + 7 skipped；.py 零改动）。**R6 模板级观察提炼（非 5-1 义务）**：零外部服务依赖的接线/登记类场景不应与服务可用性门控背景同 feature

#### 已推迟 Defer（留项台账——标注核销轮次或触发 Story）

- [x] D1【P1·已核销】import-linter `interfaces-no-infrastructure` 契约 BROKEN → ✅ 核销于 2026-10-15（**方案 A**：入口上移 `src/entrypoints/` 组装层——agent_cli/ocr_cli/api_app 迁移、interfaces 组合根引用清零、契约还原严格传导禁止；3-body 拍板（B 曾同日早间落地后被撤销，完整决策链见 proposal）；活体验证直接违规仍捕获；CI 直接 blocking + pre-commit 钩子）
- [x] D2【P2·已核销】EPO `_parse_biblio_document` 静默空记录 + `_fail` 消息层名错位 → ✅ 核销于 2026-10-14 留项清偿轮（原触发器「4-1f 跟进」因其 done 悬空改直接处置：`_fail(missing_layer, actual)` 消息点名真实缺失层 + 无 bibliographic-data 文档跳过 + 两用例；EPO 消费方回归绿）
- [ ] D3【P3】`get_by_id` 数据损坏误报 StorageError(103) 语义错位（**R2 补注：现粗粒度包装使内置异常不裸逃逸——红线合规非缺陷；5.3 定的是「损坏 vs 连接」拆分契约而非修复**）→ 本节登记——核销：Story 5.3 消费契约定时
- [x] D5【P3·已核销】`publish` 返回 None 静默视为成功 → ✅ 核销于 Round 2（裁定：EventPublisher Protocol 返回类型由 mypy src 门禁编译期覆盖，全部 5 个实现均返回 PublishResult；运行时 warn 防御边际价值不足）
- [x] D6【P3·R2 收窄】AgentConfig 直构造残余缺口（**R2-F2 已清偿 responsibilities/domain_knowledge tuple 守卫**；残余=标量字段非 str 直构造（name=123 裸 AttributeError）/ isolation 无枚举校验 / 空白串未归一 / `_required_str` 不 strip）→ 核销：5.3/5.4 消费方 Story 回填。**✅ 核销于 Story 5.4（2026-10-22）Task 1 循环 E 全量回填**：default_isolation_level 枚举化（str→IsolationLevel SSOT + isinstance 守卫）+ 标量字段类型守卫（统一 440 分码对齐 `_fail` 文件先例）；「空白串未归一」经核实现状为「拦截语义已存在（440）」钉子测试锁定即核销（存储值不做 strip 归一）——详见 5-4 story D6 处置行
- [x] D7【P3】SINGLETON 用例捕获 SCOPED 仓储（captive dependency；clear_scoped 未接线暂无实害；R2 科学性复审判明无状态仓储翻 SINGLETON 可廉价消解但属架构级 lifetime 语义决策）→ 已有 lifetime 注记，5.4 决策回迁时评估。**✅ 核销于 Story 5.4（2026-10-22）Task 0 评估 + DC-7 决策落地**：新增 isolation_repository 直接 SINGLETON 从源头避免 captive；新捕获关系显式登记（isolation_management_service SINGLETON 捕获存量 SCOPED agent_repository——无实害论证）；存量 agent_repository/skill_loader 维持现状注记（翻 SINGLETON 属架构级决策且无实害，surgical changes 原则不动存量）；架构锚 = 5-4 验证器 D lifetime 断言防回退——评估关闭
- [ ] D8【P3·范围收窄至 HTTPException 专项】存量技术债——**2026-10-15 D8 清偿轮已清偿大部分**（ocr_cli 6 处 ValueError→201、circuit_breaker 3 处→101、noqa 死注释×3 文件清除（src 层现零命中）、RedisSnapshotStore pipeline 原子化、FakeRedis 13 用例 fixture 化 aclose；**甄别剔除**：strategic_archive 2 处属 Pydantic validator 契约合法形态）；剩余 ~41 处裸 HTTPException（9 路由文件）归专项——核销：专项技术债 Story（附存量无 TTL 孤儿键 SCAN 清理建议）
- [x] D9【P3·全部核销】测试 P3 群：(a)(b) Round 2 核销；(c) 架构验证器 D AST 化 → ✅ 核销于 2026-10-14 留项清偿轮（ast.Call func 名/属性名扫描替代子串匹配，堵 FakeXxx(Cls 前缀误报）
- [ ] D11【P3·范围收窄至①】outbox 毒消息终态机制——②④⑤⑥ 已于 2026-10-14 核销；**③DLQ dequeue 毒隔离 + count_by_status 巡检面已于 2026-10-15 D11-a 微 Story 核销**（毒条目标 error 终态+action_taken 记毒因；按状态分组巡检）；剩余 ①超限行 archived 终态迁移+requeue → D11-b 专项（方案见 proposals/proposal-d11-outbox-dead-letter.md，PG 环境前置）
- [ ] D12【P2·R4 新增】wheel 形态 configs/ 分发缺口：pyproject `packages=[{include="src"}]` 不含 configs/（configs 非 Python 包），wheel/pip 安装形态 CLI 必现 440「配置文件不存在」；源码树/Docker（dockerfile COPY configs/）/k8s（挂载 /app/configs）三形态自洽，全仓无 wheel 消费方（CI 零 poetry build 环节）——裁定不冒改打包配置（非包数据分发细节+构建验证成本，改错比不改糟）→ 核销触发：发布/打包专项立项 或 首个 wheel 消费方出现（README 已声明部署形态）
- [ ] D13【P2·R4 新增】CLI 全量 bootstrap 启动开销：单次调用墙钟 10.4s（import 0.2s + bootstrap 7.7s≈157 端口注册 + litellm import 触发远端价目表拉取出网 + BGE tokenizer 加载），实际用例 ~2.5ms（2026-10-14 本机实测，环境限定）；非 5-1 引入（组合根预存成本，agent_cli 是首个全量付费的 Redis CLI）——短期缓解：部署环境设 `LITELLM_LOCAL_MODEL_COST_MAP=1` 防出网阻塞；根治（组合根瘦身/lazy 化）属架构级决策 → 核销触发：5.3 批量实例化消费前
- [ ] D10【P3·已核销】Story「12 维度」vs 契约测试「11 维度」计数矛盾 → 本轮已统一为「11 维度/12 用例（9a/9b）」（✅ 核销于 Round 1）
- [ ] 【R2 口径澄清】R1 提交信息「全 tests 树仅 5-1 新增文件存在 type: ignore」经 git 实证**属实**（98f3e742 时点恰 4 文件且全 5-1）；本台账 R1-F1 条在 Hard Constraint 三形态语境下易被扩大解读为「全部抑制注释形态」——补记：tests 树存量 12 文件含 noqa/pylint 形态抑制注释（归 D8 域，非 type: ignore 形态）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] 运行 `dev-story` 开始实施（从 Task 0 开始）——**已完成（2026-10-14）：Task 0-8 全部实施，Status → review**
- [x] 运行 `code-review` 进行代码审查——**五轮循环审查闭环（2026-10-14）：R1 五视角调研（P0×4/P1×3/P2×1）→ R2 回归核查+科学性（P2×3/P3×6）→ R3 一致性+D4 核销（P1×1/P2×1/P3×4）→ R4 运维就绪落账（纯文档）→ R5 独立收敛终审（裁定收敛达成），每轮 C3 评审门禁「优秀」后修码、逐轮提交推送；见 Review Findings 四轮台账 + 收敛声明**
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.14.1
**创建日期/Created:** 2026-10-14
**最后更新/Last Updated:** 2026-10-31
**更新说明/Description:**
- v1.0.0: 创建故事文件（5 并行调研 Agent 全仓代码/文档/模板/经验调研 + 人工事实核验；含链路接线断言清单 L1-L8、8 项关键架构决策 DC-1~DC-8、4 项偏离声明 D-1~D-4、deferred-work 分流处置）
- v1.1.0: Round 1 审查修订（正确性视角：5 并行调研 Agent 代码事实核对 + 3 并行审查 Agent 对抗复核/一致性/遗漏扫描；修复 P0×4（EXCEPTION_HTTP_MAP 定位、YAML 断言误伤、session_storage 缺登记、验收模板指向）+ P1×8 + P2×18，详见「文档审查修复」表）
- v1.2.0: Round 2 审查修订（科学性视角：2 调研 Agent 设计边界/先例基准 + 3 审查 Agent 决策裁定/事件异常体系/影响面核查；修复 P0×2（事件字段 kw_only、守卫顺序倒置）+ P1×6（save(ttl) 必填、路径锚定、get_by_id 改名、D-6/D-7 偏离声明、§10.1 登记）+ 补强 5 项，详见「文档审查修复」表 #14-21）
- v1.3.0: Round 3 审查修订（可行性视角：2 调研 Agent BDD/工具链实测 + 1 终审 Agent 13 场景可满足性推演与 Task 0-8 依赖干跑；修复 P0×4（teardown 自相矛盾、resolve 跨循环死连接、Task 5 main 注入不可写、AC-5.2 scan 误计）+ P1×2 + 补强 8 项（warmup+quantiles 采样法、@scenario 收集陷阱、冒烟三前置、Redis 池清理等），详见「文档审查修复」表 #22-28）
- v1.4.0: Round 4 审查修订（回归核查+边界视角：1 回归验证 Agent 全量复核三轮修复引用（#1-28 抽查全部落地、口径统一、结构完整）+ 1 边界审查 Agent 七维度边界推演；修复 P1×5（L362→L318 行号、空列表漏检、标量静默陷阱、--role 大写归一化、子命令 required 裸崩）+ P2×7 边界定稿（空串归一化/未知键策略/SUPPORTED_ROLES 常量/upsert 语义/退出码 0-1-2/UUID 输出/resolve 缓存注记），详见「文档审查修复」表 #29-32）
- v1.5.0: Round 5 终态收敛（1 竞争性终检 Agent 按 checklist.md 框架以 dev agent 视角终检——无 Critical 缺陷、约 40 处引用抽查仅 1 处歧义、防重复清单完整；1 收敛验证 Agent——台账 #1-32 全部落地无假修复、内部计数终态一致、模板章节零缺失、正文零未决问题；P0 收敛曲线 4→2→4→0，终态「dev agent 可直接实施」；微修 P3×4 见台账 #33。**审查闭环：五轮 34 项修复台账，Story 可进入 dev-story**）
- v1.6.0: **dev-story 实施完成**（2026-10-14：Task 0-8 全部实施且 DoD 达成——4 并行调研先例核验 → SDD 规范与 Gherkin 13 场景红阶段验证 → 领域层异常子域 440/441 + AgentInstantiated 事件双登记 → AgentConfig/加载器/ceo_agent.yaml → AgentRepository/Redis 仓储 → 实例化用例与发布接线 → sisys-agent CLI 端到端 → 集成与性能（P95<200ms + 10 并发）→ 架构五验证器 → 收尾验收；每个 TDD 循环含变异实证共 9 处；三质量门禁全绿 + 分层覆盖率全过（97/90/86/89%）；13 验收场景全绿；Status → review）
- v1.7.0: **代码审查 Round 1**（2026-10-14：C1 五视角并行调研——正确性契约/边界缺陷/架构规范/测试质量/盲审冷审；C2-C3 方案经三视角评审往返一轮裁定「优秀」后修码；修复 P0×4（type: ignore 红线×6 处、_read_yaml 契约逃逸、hset/expire 非原子孤儿键、from_dict PEP 563 类型漂移——base.py 根因修复惠及全事件族）+ P1×3 + P2×1 + P3 文档口径（11 维度统一/异常契约表补强/AC-3 pipeline 措辞）；留项 D1-D10 台账；详见 Review Findings 节）
- v1.8.0: **代码审查 Round 2**（2026-10-14：C1 双视角——R1 修复回归核查（F1-F8 逐项 ✅ 零 P0/P1 回归，redis-py 源码级验证）+ 科学性复审（R1 修复 9/10，缓存 9.6µs/pipeline RTT 2→1 实测背书）；C3 双视角评审往返一轮裁定「优秀」；修复 P2×3（outbox 毒消息隔离——R1-F4 fail-loud 放大的队头阻塞回归面、VO tuple 守卫——str 静默逐字符展开、测试断言活性 D9(a)(b)）+ P3×6（追踪字段/NameError 包装 242、pipeline 同 key 断言、GBK reason 断言、文档卫生、加载器 section 级守卫+正向锚定）；台账勘误五项（D5 核销/D9(d) 归 D8/D3 补注/D6 收窄/口径澄清）+ D11 新增；R2 终态：5-1 可处置的 P0/P1/P2 全部清零）
- v1.9.0: **代码审查 Round 3**（2026-10-14：C1 双视角——R2 修复回归核查（揪出 R2-F1 两处新破口：超限毒行永不退出 SELECT 致队头阻塞隐蔽复发 P1、mark_failed 无界错误串 VARCHAR 溢出活锁 P2）+ R1/R2 累计一致性终查（from_dict 全消费方自洽/17 项修复宣称落点全部实证/D4 三候选方案设计）；C3 合并评审实测修订（F2 isinstance 收窄过 mypy/F3 红测形态勘正——int 注入不抛异常改裸特殊形式）；修复 P1×1+P2×1（outbox SELECT 过滤/错误消息截断）+ P3×4（病态注解三形态扩捕/空串容忍恢复/D4 核销——验收 Background 下沉双态实证 13 passed 与 6+7/文档卫生六项）；D11 收敛+补登记；v1.7.0 计数勘正；R3 终态：R2 回归面清零、可处置项累计全清）
- v1.10.0: **代码审查 Round 4**（2026-10-14：C1 双视角——R3 修复回归核查（零 P0/P1/P2 新破口，10083 passed 实测+双态验收+CLI 冒烟）+ 可行性/运维审计（运维就绪总评通过，P95 独立复测 3.57ms 远优门限）；C3 轻量评审纠错一处（RDB 窗口按实测改写 ≤60 分钟）；纯文档/台账轮代码零变更：P2×2 留项登记（D12 wheel configs 分发缺口——裁定不冒改打包配置、D13 CLI bootstrap 10.4s 开销——组合根瘦身架构决策 5.3 前核销）+ P3×4（D11 扩为六项收敛范围、README 补 Agent CLI 小节、下游风险 #2 补持久化丢失窗口、三项观察登记））
- v1.11.0: **代码审查 Round 5 收敛终审**（2026-10-14：独立收敛终审 Agent 不轻信台账全量重取证——周期闭合（5 提交无游离）/关键修复抽验（R1-F4 往返 UUID·R1-F3 pipeline·R2/R3 outbox 过滤与隔离·R2-F2 VO 守卫，代码形态+行为实测双确认）/全量实跑（10030+53 passed·CLI 退出码 0/1 实证·收集数 13）/台账 D1-D13 完整带核销触发器/文档终态一致——**裁定收敛达成**；终审新发现 P3×3（R1 文件计数勘正+File List 补列已处置；§3.12 引用经复核为误报如实记录）；收敛声明入账；**Status: review → done**）
- v1.12.0: **留项清偿轮**（2026-10-14：D2/D9(c) 核销 + D11 四子项清偿（②④⑤⑥）范围收窄至①③ + D13 短期缓解落地（.env.example）；TDD 红 7 用例→绿；unit+contracts 10038 + EPO 消费方验收 35 全绿；D1/D11 治理方案件两份入 proposals/（供架构评审与立项））
- v1.13.0: **D1 方案 A 落地**（2026-10-15：3-body 拍板——同日决策链 B 落地→用户撤销→A 终态实施。入口上移 src/entrypoints/ 组装层（agent_cli/ocr_cli/api_app git mv，interfaces 组合根引用清零）+ 契约还原严格传导禁止（5 kept，注入直接违规仍捕获）+ CI 直接 blocking + pre-commit 钩子 + 12 测试引用面更新 + CLAUDE.md 目录树同步；受影响面 798 passed）
- v1.14.0: **D8 清偿轮 + D11-a 微 Story + R1-F4 集成层补漏**（2026-10-15：①R1-F4 integration 层两处 str 锚漏网类型化（archive_validity/data_staleness——回归面静态全扫教训入记忆）；②D8 清偿：ocr_cli 6 处 ValueError→ValidationError(201)、circuit_breaker 3 处→ConfigurationError(101)、noqa 死注释×3 文件清除、RedisSnapshotStore pipeline 原子化、FakeRedis 13 用例 fixture 化（strategic_archive 2 处经甄别属 Pydantic validator 契约合法形态剔除）；③D11-a：DLQ dequeue 毒隔离（error 终态）+ outbox count_by_status 巡检面——每项 TDD 红绿；验证：受影响面全绿 + snapshot 真实链路验收 19 passed）
- v1.14.1: Epic 5 终局审查 Round 1 修复 F10（File List agent_cli.py 行加路径迁移注记——interfaces/cli → entrypoints，D1 方案 A c176da99；台账见 epic-5-final-review-2026-10-30.md R1-N9）
