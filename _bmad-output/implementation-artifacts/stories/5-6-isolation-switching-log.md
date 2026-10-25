# Story 5.6: 隔离切换日志记录

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 合规工程师,
**I want** 系统记录隔离切换日志（AGENT ID、时间戳、原隔离等级、目标隔离等级、触发原因、审批链）并支持按 AGENT/时间/隔离等级多维检索,
**So that** 满足审计追踪要求（FR-AC-06——每次隔离等级变更留有不可篡改的完整审计痕迹）。

### 业务价值

Epic 5「单 Agent 战略规划能力」价值组的合规闭环 Story：5-4 交付了 EIP 协议的**策略声明面与切换通道**（`IsolationLevelSwitched` 事件六字段 payload 已齐备），5-5 交付了**运行时强制执行面**（三重硬隔离判定矩阵+守卫服务），本 Story 交付**审计留痕面**——`IsolationSwitchLog` 领域实体 + 切换链内嵌 audit-first 持久化（PostgreSQL + RLS 防篡改）+ 多维检索（AGENT/时间范围/隔离等级 + 分页）+ 统一审计日志联动（`AuditService.record`——Story 1.10 资产复用）。这是 FR-AC-06 的闭环 Story，也是 or.md L30「隔离切换日志实体：支持 AGENT 隔离等级变更审计追踪」与 architecture.md §9 `IsolationSwitchLog`（L2+L4 存储）的落地。合规价值：任何隔离等级变更（未来 V1 动态升降级 FR-AC-09 的 SYS 命令/关键词频率/任务依赖通道亦复用本底座）均留有审计证据链，支撑 SOX/ISO27001 七年审计追踪要求（architecture.md L118/L132）。

**范围权威**：epics_v1.0.md L1674-1713（AC + 测试要求 + 性能锚 L1695-1697）、L463（FR-AC-06 追踪）、L1442（依赖 5.4 + Story 1.10）；prd.md L1842（FR-AC-06 P0——`[or.md 一.2.(9)]`）；architecture.md §5（L652-653「`IsolationSwitchLog` 切换日志归 Story 5.6」）、§5.3（L693「所有隔离切换自动记录至 IsolationSwitchLog 并归档至 WORM 存储」）、§8.5（L814 IsolationLevelSwitched 24h 内 WORM 归档——**见偏离声明 OD-1**）、§9（L833 实体定义：id/agent_id/from_level/to_level/trigger/worm_ref，存储 L2+L4）、§10.1（L862 事件通道）；or.md 一.2.(9)（L30 实体七属性——**见 OD-2/OD-3 裁剪**）、一.3.(8)（L48 事件 payload）、二.5.(3)（L125 审计事件 WORM 归档）；sisys-core-domain-design.md §17.3.3（L1253-1261 EIPExecutor 伪码第 4 步 audit_log.save 先例）；5-5 故事范围边界表（L35-36「IsolationSwitchLog 切换日志、多维检索、WORM 归档 ❌ → 5.6」+「隔离切换审计记录（AuditService 调用）❌ → 5.6——**事件 payload 是 5.6 数据源契约**」）。

### 范围边界（与后续 Story 的精确切分）

| 能力 | 本 Story（5.6） | 后续 Story |
|------|----------------|-----------|
| IsolationSwitchLog 领域实体（frozen + from_event 工厂） | ✅ domain/entities + 单测 | — |
| IsolationSwitchLogRepository 端口 + Query Object + SearchResult | ✅ domain/ports | — |
| PG 表 + alembic 015 + RLS 防篡改 + CheckConstraint | ✅ infrastructure + migration | — |
| PG 仓储实现（双模式 session——请求 ContextVar 优先 + session_factory fallback） | ✅ | — |
| 切换链 audit-first 写入接线（IsolationManagementService 五/六依赖） | ✅ 含回归面全量同步 | — |
| AuditService.record 联动（action_type=isolation:switch）+ AuditActionType 扩展 | ✅ | — |
| 多维检索（按 AGENT/时间范围/隔离等级 + 分页 + 排序） | ✅ 端口 + PG 实现 + 集成 | — |
| CLI `isolation-logs` 检索命令 | ✅ interfaces/cli（R4 接口层适配） | — |
| worm_ref 字段预留（nullable） | ✅ | — |
| MinIO WORM 24h 归档管线（§8.5） | ❌ 不做（OD-1） | V1 合规归档管线（与 1.10 WORMManager 未接线现状对齐） |
| 「切换后协作状态」独立字段（or.md 一.2.(9)） | ❌ 不做（OD-2——to_level 即协作状态语义） | V1 多 Agent 协作组 |
| trigger_type 枚举字段（SYS 命令/关键词频率/任务依赖/用户请求四类） | ❌ 不做（OD-3——MVP 仅用户请求单通道，事件无 type 字段） | V1（FR-AC-09 多通道时随事件 payload 扩展联动） |
| 隔离切换 REST API 查询端点 | ❌ 不做（MVP 检索交付面 = 端口 + CLI；audit router 未挂 create_app 是 1.10 既有形态） | Epic 7（7-2 REST API） |
| 事件订阅消费写日志（EventHandler 形态） | ❌ 不做（DC-2——audit-first 同步写；消费基建归 5.7） | 5.7 Phoenix（事件订阅基建面） |
| 动态触发（SYS 命令/关键词频率/任务依赖）与 30 分钟自动恢复 | ❌ 不做 | V1（FR-AC-09 P1） |

### 偏离声明（Deviation Declarations）

| # | 偏离 | 规划原文 | 偏离理由与归宿 |
|---|------|---------|---------------|
| OD-1 | MinIO WORM 24h 归档管线不在本 Story 实施；`worm_ref` 字段预留（nullable，默认 None） | architecture.md §8.5 L814（IsolationLevelSwitched 切换后 24 小时内归档 MinIO WORM 7 年）、§5.3 L693、or.md 二.5.(3) L125 | epics AC（L1680-1691）未要求 WORM（字段完整+多维检索+持久化）；1.10 WORMManager/archive 同为未接线现状（组合根未注入）；防篡改由 PG RLS deny UPDATE/DELETE 等效承载（DC-4）。归 V1 合规归档管线——**承接方 = Story 13-4（sox-compliance-404，V1）**；**补偿控制差距显式登记**：RLS 可被 superuser/BYPASSRLS 属性绕过、PG 备份/导出不受 RLS 约束、无 7 年保留期限策略——监管级 WORM（SEC 17a-4 / ISO 27001 口径）需 MinIO Object Lock COMPLIANCE 管线；**Task 0.8 随 deferred-work.md 登记**（gap 四要素：描述/触发条件/归宿/承接方链接） |
| OD-2 | 「切换后协作状态」不设独立字段 | or.md 一.2.(9) L30（七属性含切换后协作状态） | architecture.md §9 L833 实体定稿字段无此项——`target_level` 即协作状态语义（等级=协作模式映射，§5.1 四级表）；MVP 单 Agent 无协作态可记。V1 多 Agent 协作组立项时随需扩展——**承接方 = Story 9-4（联合分析组创建）/ 9-5（公共黑板中间结论交换）**；**Task 0.8 随 deferred-work.md 登记** |
| OD-3 | `trigger_type` 枚举字段不设（SYS 命令/关键词频率/任务依赖/用户请求四类触发源类型化） | or.md 一.2.(9) L30（触发原因括注四类）、core-domain-design §17.3.3 伪码 L1259（trigger_type） | MVP 唯一触发通道为用户显式请求（5-4 既定），`IsolationLevelSwitched` 事件仅 `trigger_reason` 自由文本无 type 字段——单通道下枚举仅一值（YAGNI）；architecture.md L833 定稿字段亦为单 `trigger` 字段。V1 FR-AC-09 多通道立项时随事件 payload 扩展联动（本 Story 实体加字段为非破坏演进）——**承接方 = Story 9-3（dynamic-isolation-level-adjustment，FR-AC-09）**；**Task 0.8 随 deferred-work.md 登记** |

> 优先级双锚说明（非偏离）：prd.md L1842 将 FR-AC-06 定级 P0（功能等级），epics_v1.0.md L1442 执行优先级 P1-6（执行序——依赖 5.4/5.5 完成后执行）。两者不矛盾：功能等级遵 prd，执行序遵 epics。

---

## 🔗 前置依赖（全部 ✅ 已完成，无阻塞）

| 依赖 | 组件 | 用途 | 状态 |
|------|------|------|------|
| Story 5.4 | `IsolationLevelSwitched` 事件（domain/events/isolation_events.py L17-50——六字段 payload：agent_id/previous_level/target_level/trigger_reason/approval_chain/switch_timestamp，**本 Story 唯一数据源契约，零改动**）+ `IsolationManagementService.switch_isolation_level`（application/services/isolation_management_service.py L112-177——守卫序 443→447→446 + no-op 零副作用 + approval_chain 显式转发 L153）+ `IsolationManagementServicePort`（application/ports/isolation_management.py L100-130）+ `IsolationSwitchResult` DTO（L37-49）+ `RedisIsolationRepository`（键空间 `sisys:isolation:{agent_id}`）+ CLI set-isolation/isolation-status（entrypoints/agent_cli.py）+ 组合根注册（composition_root.py L2883-2903） | 切换通道与事件 payload（from_event 映射源） | ✅ done |
| Epic 1 Story 1.10 | `AuditServicePort.record`（domain/ports/audit_service.py L52-60——actor/action_type/target_resource/old_value/new_value/correlation_id）+ `AuditServiceImpl`（infrastructure/security/audit_service_impl.py L23/L49-127——同步 await，失败包装 AuditError）+ `AuditRepository`（infrastructure/security/audit_repository_impl.py——ContextVar session + save(dict) + search(AuditSearchCriteria) 多维检索先例 L96-149）+ `audit_log` PG 表（RLS deny UPDATE/DELETE——002_audit_tables L103-143）+ `AuditActionType` 枚举（domain/events/audit_events.py L31-72）+ 组合根 audit_repo/audit_service 注册（composition_root.py L483-503）+ `resolve_optional` 可选注入先例（composition_root.py L2201——PersistentNoteTaker 降级模式） | 审计联动通道 + 检索/表/RLS 三大照抄模板 | ✅ done |
| Story 5.1 | `Agent` 实体 + `AgentRepository` + `RedisAgentRepository`（键 `sisys:agent:{agent_id}`）+ `InstantiateAgentUseCase`（本 Story 测试用它构造真实 Agent） | 测试 Agent 构造链 | ✅ done |
| 异常体系 | `AgentNotFoundError`(443)/`IsolationStateNotInitializedError`(447)/`IsolationLevelNotSupportedError`(446)/`EntityValidationError`(242)/`StorageError`(103)/`AuditError`(105) 全部复用（DC-8——零新异常；agent 段 440-449 已满，无需开新段） | 守卫/校验/存储失败透传 | ✅ 就绪 |
| Outbox session fallback 先例 | `PostgreSQLOutboxRepository`（infrastructure/messaging/outbox/outbox_repository.py L71-97——请求 session 优先 + `session_factory` fallback 独立会话写入，Story 4-7 修复）+ `session_context()`（infrastructure/storage/postgresql/session_context.py——R3 后台任务独立 scope 规则） | PG 仓储双模式 session 照抄模板（CLI 上下文可写） | ✅ 就绪 |
| 测试基建 | `tests/environments.py` get_test_env()（测试端口 Redis 6380 / PG 5433）/ `tests/integration/conftest.py` real_redis(L193-220) + real_postgres_engine(L254-286) + postgres_session(L289-293，事务隔离 begin+rollback L453-536) + ensure_alembic_migration / `tests/acceptance/conftest.py` acceptance_env_config + 文件名服务 marker 自动挂载（L110-140） | 集成/验收双服务门控与隔离基建 | ✅ 就绪 |

**移交给本 Story 的留项（必须处置）**：

| # | 留项 | 来源 | 本 Story 处置 |
|---|------|------|--------------|
| 1 | **5-4 风险 #7 / 5-5 维持**：同 Agent 并发切换无锁竞态（后写覆盖 + 事件序与终态可能不一致）——deferred-work.md 归 V1 动态触发立项 | 5-5 deferred 处置表 | **Task 0 评估**：本 Story 的 audit-first 日志写入在竞态下同样产生乱序日志（两并发切换 → 两条日志 + Redis 终态取最后写者）。MVP 触发通道仅 CLI 人工单发，并发切换不可达；维持 deferred 登记，**新增注记**：日志序 ≈ 事件序（同一竞态窗口），V1 立项时日志与终态一致性需一并评估 |
| 2 | **R1-DF2**：StorageError(103) 同码双语义分化（触发含新建 PG 仓储面） | 5-4 审查 deferred-work.md L200 | **评估**：本 Story 新建 PG 仓储（save/search 抛 StorageError）+ 切换链 Redis 写（同抛 103）——双存储同码场景扩大。维持 deferred（归存储层异常码专项），Task 0 在 deferred-work.md 原条目追加 5.6 注记 |
| 3 | **audit router 未挂 create_app**（1.10 已知缺口——deferred-work.md L115） | Story 1.10 | **不触发**：本 Story 检索交付面 = 端口 + CLI（DC-10），不新增 REST 端点，不改 api_app.py 挂载面；维持原条目归 Epic 7 |

---

## 🔗 现有代码继承（必须复用，禁止重复定义）

> ⚠️ **防重复造轮子清单**——以下组件已存在，dev agent 只可「直接复用 / 参考照抄」，禁止新建同义组件。

| 组件 | 文件路径 | 复用方式 |
|------|---------|---------|
| `IsolationLevelSwitched` 事件（六字段 payload） | `src/domain/events/isolation_events.py` L17-50 | **直接复用，零改动**——from_event 映射唯一源（5-5 L36「事件 payload 是 5.6 数据源契约」） |
| `IsolationLevel` 枚举（L4_HARD/L3_SOFT/L2_COLLAB/L1_FUSED） | `src/domain/events/enums.py` L39-45 | **直接复用**——等级 SSOT（禁新建） |
| `switch_isolation_level` 切换通道（守卫序/no-op/TTL 重置/事件发布容错 DC-10） | `src/application/services/isolation_management_service.py` L112-177 | **扩展**——第五/六依赖注入 + audit-first 日志写入插位（L141 no-op return 之后、L146 Redis save 之前）+ audit 联动（方法尾部） |
| `IsolationManagementServicePort` / `IsolationSwitchResult` | `src/application/ports/isolation_management.py` | **扩展**——docstring 更新（ Raises/审计语义）；IsolationSwitchResult **不扩展**（log 不进返回值——调用方经检索面自查，YAGNI） |
| `AuditServicePort.record` + `AuditServiceImpl` | `src/domain/ports/audit_service.py` L52-60 + `src/infrastructure/security/audit_service_impl.py` | **直接复用**——联动审计通道（组合根 resolve_optional 注入先例 L2201） |
| `AuditActionType` 枚举 | `src/domain/events/audit_events.py` L31-72 | **扩展**——追加 isolation 组 `ISOLATION_SWITCH = "isolation:switch"`（第 8 组，DC-9） |
| `AuditSearchCriteria` / `AuditSearchResult` / search 实现 | `src/domain/ports/audit_repository.py` L15-54 + `src/infrastructure/security/audit_repository_impl.py` L96-149 | **参考照抄**——Query Object 字段形态（offset/limit 分页 + match_any）与动态条件构建 + count + timestamp desc 排序 |
| audit_log RLS 策略四件套（INSERT/SELECT 放行 + deny UPDATE/DELETE） | `deploy/postgresql/alembic/versions/002_audit_tables.py` L103-143 | **参考照抄**——015 migration RLS 段（注意 DELETE policy 仅 USING 子句——002 已修正的 PG 语法约束）+ **追加 FORCE ROW LEVEL SECURITY**（DC-4——owner 连接不绕过） |
| outbox 双模式 session（请求 ContextVar 优先 + session_factory fallback） | `src/infrastructure/messaging/outbox/outbox_repository.py` L71-97 + `session_context()` | **参考照抄**——PG 仓储 save 的双路径（CLI/后台上下文可写——Story 4-7 修复先例） |
| `PostgreSQLAdapter` 泛型基类 / ContextVar `_session` property | `src/infrastructure/storage/postgresql/repository/postgresql_adapter.py` L14/L41-59 | **参考照抄**——ORM 模型注册（`models/__init__.py`）与仓储类形态（本仓储有 search 定制查询，不必继承泛型基类——audit_repository_impl 直实现 Port 先例同款，双模式 session 是差异点） |
| `PortSpec` 注册 + `# === Story 5.x ===` 区段 + `__import__` 延迟导入 + lambda 工厂 | `src/composition_root.py` L2678-2931（5.x 区，isolation_management_service L2883-2903 原文） | **参考照抄**——新端口注册追加至该区段 + 既有 lambda 扩展两依赖 |
| 端口契约测试 11 维度 + `_DummyResolver` | `tests/contracts/test_port_contract_isolation_management_service.py`（137 行全文） | **参考照抄**——同款结构（PORT_NAME/EXPECTED_TAGS/REQUIRED_METHODS 类常量 + 11 维度函数 + Dummy 分发） |
| 集成 `_assemble_real_chain()` 手动组装 + `_PERF_CACHE` 委托计时 + `xdist_group` 同 worker 缓存 | `tests/integration/test_integration_agent_isolation.py` L39-55/L83-123 | **参考照抄**——真实链组装扩展 log 仓储/audit + 新计时组 |
| 验收测试骨架（PG 模板 R6 基准 + 5-4/5-5 Redis 改造形态） | `tests/acceptance/test_acceptance_agent_isolation.py`（5-4，1267 行）/ `test_acceptance_agent_triple_isolation.py`（5-5，1401 行） | **参考照抄**——R6 主体基准（@scenario 多行字面量显式绑定 + context dict fixture + `_run_async` 同循环 + 步骤化门控 skip + 收尾清单场景 + 延迟 import）；PG 模板取 ensure_alembic_migration fixture 形态（test_acceptance_postgresql_relational_layer.py L148-204）；禁 then-pass 占位（PG 模板历史缺陷） |
| `build_key(namespace, *parts)` | `src/infrastructure/storage/redis/key_builder.py` L11-22 | **直接复用**——验收/集成 Redis 双键清理 |
| `_RecordingEventPublisher` 手写替身形态 | `tests/acceptance/test_acceptance_agent_isolation.py` L80-97 | **参考照抄**——同构副本（仓内无共享定义，各文件手写是惯例） |
| 实体形态先例（frozen 日志型 + create 工厂 + `__post_init__` 242 + to_dict） | `src/domain/entities/audit_log.py` L18-142 + `isolation_state.py` L57-176（枚举双条件守卫 R3-F01） | **参考照抄**——IsolationSwitchLog 实体骨架 |

**明确不存在、本 Story 需新建**（全仓 grep 验证：`IsolationSwitchLog|isolation_switch_log|switch_log` 在 `src/` 与 `tests/` 零命中——唯一出现于 docs 规划性文档 interface-design.md L1377 与 architecture.md §9；`隔离切换与审计零集成`——isolation_management_service.py 全文无 audit 引用）：

1. `IsolationSwitchLog` 实体 + `from_event` 工厂（domain/entities/isolation_switch_log.py）
2. `IsolationSwitchLogQuery` + `IsolationSwitchLogSearchResult` + `IsolationSwitchLogRepository` 端口（domain/ports/isolation_switch_log_repository.py）
3. `IsolationSwitchLogModel` ORM（infrastructure/storage/postgresql/models/isolation_switch_log.py）+ `models/__init__.py` 注册
4. alembic migration `015_isolation_switch_logs`（表 + 4 索引 + CheckConstraint + RLS 四策略 + FORCE）
5. `PostgreSQLIsolationSwitchLogRepository` 仓储实现（双模式 session，infrastructure/storage/postgresql/repository/isolation_switch_log_repository.py）
6. `IsolationManagementService` 第五依赖 `isolation_switch_log_repository`（必填）+ 第六依赖 `audit_service`（可选）+ audit-first 写入 + audit 联动
7. `AuditActionType.ISOLATION_SWITCH` 枚举项
8. CLI `isolation-logs` 子命令（entrypoints/agent_cli.py）
9. 组合根 `isolation_switch_log_repository` 注册 + isolation_management_service lambda 扩展
10. 测试七件：`tests/unit/domain/entities/test_isolation_switch_log.py` / `tests/unit/application/services/test_isolation_management_service.py`（追加）+ 存量构造点同步 / `tests/unit/infrastructure/storage/postgresql/test_isolation_switch_log_repository.py`（薄单测——mock session 逻辑面） / `tests/contracts/test_port_contract_isolation_switch_log_repository.py` / `tests/integration/test_integration_isolation_switch_log.py` / `tests/unit/architecture/test_arch_isolation_switch_log.py` / `tests/acceptance/test_acceptance_isolation_switch_log.{feature,py}`

---

## ✅ Acceptance Criteria 验收标准

### AC-1: IsolationSwitchLog 领域实体与事件映射

**Given** `IsolationLevelSwitched` 事件已定义（5-4 交付，六字段 payload）
**When** 以真实切换事件调用 `IsolationSwitchLog.from_event(event)`
**Then** 产出 frozen 实体，六字段逐项映射完整：`agent_id`（AGENT ID）、`switch_timestamp`（时间戳——**取事件 `switch_timestamp` 而非 event.timestamp**，单钟纪律：事件时刻=状态变更时刻）、`previous_level`（原隔离等级）、`target_level`（目标隔离等级）、`trigger_reason`（触发原因）、`approval_chain`（审批链——**tuple[str, ...] 不可变形态**，事件 list 拷贝冻结）；`log_id` 随机自铸 UUID4；`worm_ref` 默认 None（预留 OD-1）
**And** 实体不变量（`__post_init__` 抛 `EntityValidationError` 242）：agent_id 非 UUID 实例拒；previous_level/target_level 非 `IsolationLevel` 枚举实例拒（**双条件守卫**——str,Enum 混入语义 hash 穿透，5-4 R3-F01 实测定谳，isinstance 先行）；`previous_level == target_level` 拒（**切换语义不变量**——no-op 不得产生日志，与 CheckConstraint D-4 双层防线）；trigger_reason 空/空白拒；approval_chain 元素非 str 或空白串拒；`to_dict()` 全字段可序列化（UUID→str / Enum→value / datetime→ISO 8601 / tuple→list）

**验证标准/Validation Criteria:**
- [ ] from_event 六字段逐项断言（构造事件 → 映射 → 逐字段相等；approval_chain list→tuple 类型断言）
- [ ] 不变量六场景独立用例（非空/类型/相等枚举逐项）；242 三段式断言（isinstance→code→context）
- [ ] to_dict roundtrip（键集完整 + 类型形态断言）
- [ ] frozen 断言（`dataclasses.FrozenInstanceError` 赋值拒绝——日志不可变性）
- [ ] 纯 domain 零外部依赖（AST 扫描归 AC-6.3 架构验证器）

### AC-2: 切换链 audit-first 日志写入

**Given** 真实 Agent（真实 Redis 构造，默认 L4）+ 真实 PG（isolation_switch_logs 表已迁移）
**When** 调用 `switch_isolation_level(agent_id, target_level, trigger_reason, approval_chain)`（set-isolation 等价服务链）
**Then** **audit-first 顺序**（DC-2）：443→447→446 守卫 → no-op 检查（同等级 **零日志**——`log_repository.save` 零调用）→ 构造事件 → `IsolationSwitchLog.from_event` → **`log_repository.save(log)`（失败上抛 = 切换被拒——无审计痕迹的切换不允许发生）** → Redis 状态写（既有）→ 事件发布（既有 DC-10 容错）→ `audit_service.record` 联动（**可选依赖 + 失败降级** `logger.warning` 不回滚——DC-6，PersistentNoteTaker 先例）
**And** 日志落库六字段与 PG 行逐项一致（检索面取回断言）；审批链非空时（`approval_chain=("合规负责人",)`）完整持久化 JSONB；**日志写失败路径**（注入坏连接仓储实例 → StorageError 上抛 → 切换被拒：Redis `current_level` 未变、零事件发布——fail-closed 审计语义）；audit 联动记录写入 `audit_log` 表（actor=`agent:{agent_id}`、action_type=`isolation:switch`、old_value=`{"level": previous}`、new_value 含 level/reason/approval_chain、correlation_id=str(event.event_id)）

**验证标准/Validation Criteria:**
- [ ] 真实链切换 → PG 检索取回 → 六字段逐项断言（含 approval_chain JSONB roundtrip）
- [ ] no-op 零日志：同等级二次调用 → `search(agent_id=...)` total 不变 + save 零调用计数断言（AsyncMock calls——单测面）
- [ ] audit-first 顺序断言：坏仓储（连接不可达）→ `pytest.raises(StorageError)` + Redis get 回等级未变 + `_RecordingEventPublisher` 零事件
- [ ] audit 联动：真实 audit_service（PG 可用）→ audit_log 表检索 action_type=`isolation:switch` 一条 + correlation_id 匹配；降级：audit_service 抛 AuditError（单测 AsyncMock side_effect）→ 切换仍成功 + logger.warning（caplog 断言）
- [ ] 守卫序零回归：443（随机 UUID）/447（删隔离键）路径 **零日志写入**（守卫先于日志位——443/447 拒绝时 save 零调用）

### AC-3: 多维检索

**Given** isolation_switch_logs 表含多 Agent 多条切换日志（测试自造：≥3 Agent × ≥2 条/Agent，等级覆盖 L4→L3 与 L4→L2 两方向）
**When** 以 `IsolationSwitchLogQuery` 各维度组合调用 `search(query)`
**Then** **按 AGENT**：`agent_id=X` → 仅 X 的日志；**按时间**：`start_time`/`end_time` 闭区间过滤（`switch_timestamp >= start` 且 `<= end`）；**按隔离等级**：`level=L3` → **命中语义 = previous_level 或 target_level 任一等于 L3**（or.md「按隔离等级检索」语义——切换涉及该等级即命中）；**组合**：多条件 AND；**分页**：`offset`/`limit`（默认 50）+ `total` 独立计数（**非 items 长度——分页语义**）；**排序**：`switch_timestamp` 降序（最新在前）
**And** `IsolationSwitchLogSearchResult`：`items: tuple[IsolationSwitchLog, ...]`（强类型实体非 dict）+ `total: int` + `offset` + `limit`；Query Object frozen（`@dataclass(frozen=True)` 端口文件内定义——多字段组合+分页，Query Object 决策规则命中）；查询条件全空 → 全量分页返回（合法调用）

**验证标准/Validation Criteria:**
- [ ] 四维独立场景 + 组合场景（agent_id + 时间范围 + level 三条件 AND）各独立用例
- [ ] level 命中双向断言：L4→L3 切换在 `level=L3`（target 命中）与 `level=L4`（previous 命中）均返回
- [ ] 分页断言：造 5 条 → limit=2 offset=0 → items 2 条 + total=5；offset=4 → 1 条
- [ ] 排序断言：最新 switch_timestamp 在 items[0]
- [ ] 检索不要求 Agent 现存（Agent TTL 过期后历史日志仍可查——审计要求；**无 443 守卫**，与切换写入面守卫形成对照——单测锁定）

### AC-4: 持久化与不可篡改（合规防篡改底座）

**Given** isolation_switch_logs 表经 alembic 015 创建（含 RLS）
**When** 验证表结构与防篡改约束
**Then** **表结构**：`log_id` UUID PK + `agent_id` UUID + `previous_level`/`target_level` String(20) + `trigger_reason` Text + `approval_chain` JSONB + `switch_timestamp` DateTime(tz) + `worm_ref` String(500) nullable + `created_at` DateTime(tz) server_default NOW()；**索引四**：agent_id / switch_timestamp / target_level / (agent_id, switch_timestamp) 组合；**CheckConstraint** `previous_level != target_level`（DB 层拒绝 no-op 日志——实体不变量 DB 投影）；**RLS 四策略**：INSERT/SELECT 放行（WITH CHECK true / USING true）+ deny UPDATE + deny DELETE（USING false——002 模式照抄，DELETE policy 仅 USING 子句）；**FORCE ROW LEVEL SECURITY**（DC-4——owner 连接不绕过）
**And** 篡改拒绝实证：非绕过连接（前置探测 `rolbypassrls` + 表 owner 关系——绕过环境 `pytest.skip` 动态跳过并注明）下 `UPDATE ... SET target_level=...` 与 `DELETE` 均影响 0 行；CheckConstraint 实证：直插 previous==target 行 → `IntegrityError`

**验证标准/Validation Criteria:**
- [ ] migration upgrade/downgrade 对称（down 先 drop 索引后 drop 表 + DROP POLICY 清单完整）
- [ ] ORM 模型与 migration 列/索引/约束一致（模型 `__table_args__` 断言）
- [ ] RLS UPDATE/DELETE 影响 0 行断言（环境绕过时 skip——动态跳过纪律）
- [ ] CheckConstraint IntegrityError 断言（session.rollback 复位）
- [ ] worm_ref 预留断言：实体默认 None + 列 nullable + 检索 roundtrip None 保持（OD-1 登记面）

### AC-5: 性能与存储成功率

**Given** 真实 Redis + 真实 PG（测试端口 6380/5433，`SISYS_USE_TEST_PORTS=1`）
**When** 测量切换全链与检索
**Then** **日志记录延迟 P95<50ms**（epics L1695——计时锚 = `switch_isolation_level` 服务全链：守卫 + 日志 PG 写 + Redis 写 + 事件发布，warmup 1 + 20 采样 `statistics.quantiles(latencies, n=20)[18] < SWITCH_LOG_WRITE_P95_LIMIT_SECONDS`——常量 0.05）；**检索响应 P95<500ms**（epics L1696——锚 = `search` 全链，`SWITCH_LOG_SEARCH_P95_LIMIT_SECONDS = 0.5`，常量两处均单源定义于集成模块，验收侧 import）；**存储成功率 100%**（epics L1697——连续 20 次真实切换 → 检索 total 恰 +20，分子分母显式断言）
**And** 计时委托集成模块 helper（`_PERF_CACHE` 单槽缓存 + `xdist_group("isolation-switch-log-perf")` 同 worker 串行——5-4 委托模式照抄，禁 20 采样双跑）；本地 PG 写 ~3ms + Redis 两写 ~4ms，写预算 12 倍裕量

**验证标准/Validation Criteria:**
- [ ] 写 P95：常量单源（集成定义/验收 import）+ 委托缓存命中（验收 AC-5.1 不自跑采样）
- [ ] 检索 P95：同款（AC-5.2）
- [ ] 成功率：20 切换 → 20 日志（20/20 分子分母断言；含审批链非空场景混合）
- [ ] 计时场景 benchmark 场景级标记 + xdist_group 同组（与 5-4 agent-isolation-perf / 5-5 agent-triple-isolation-perf 组名互异不冲突）

### AC-6: 端口接线、CLI、架构合规与回归

**Given** 实体、仓储、接线、CLI 全部交付
**When** 验证接线与合规
**Then** 新端口 `isolation_switch_log_repository`（SCOPED——对齐 audit_repo 同域先例；SINGLETON 服务捕获 SCOPED 依赖无实害注记沿 5-4 DC-7 形态）经组合根注册且 resolve 可达（PortSpec 全参数：v1.0.0 / `IsolationSwitchLogRepository` / lambda 注入 session_factory / module / owner=platform / tags=("agent","isolation","audit")）；`IsolationManagementService` lambda 扩展第五依赖 `resolver.resolve("isolation_switch_log_repository")` + 第六依赖 `resolver.resolve_optional("audit_service")`（接线完整）；CLI `isolation-logs` 子命令（--agent-id/--level/--start/--end/--limit/--offset，Typer argparse 形态对齐 set-isolation 先例——agent_cli 用 argparse subparsers）输出多行摘要；domain 零外部依赖（isolation_switch_log.py AST 扫描——仅标准库 + 同层 events/exceptions import）；组合根外零实例化（PostgreSQLIsolationSwitchLogRepository 仅组合根与测试文件）；`AuditActionType.ISOLATION_SWITCH` 值 `"isolation:switch"` 注册
**And** 5-4/5-5 回归面零破坏：`IsolationManagementService` 构造签名扩展（四依赖 → 六依赖）的**全仓构造点全量同步**（组合根 lambda / 单测 AsyncMock 工厂 / 契约 _DummyResolver / 集成 `_assemble_real_chain` / 验收手动组装链 / 5-5 探针套件构造点——Task 3 全仓 grep 登记苦役先例）；5-4 验收（`test_acceptance_agent_isolation`）+ 5-5 验收/探针（`test_acceptance_agent_triple_isolation` / `test_integration_isolation_security`）全量回归绿

**验证标准/Validation Criteria:**
- [ ] 组合根注册 + resolve + isinstance + lifetime==SCOPED 断言（5-4 AC-6.1 同款）
- [ ] lambda 五/六依赖注入确认（resolve isolation_management_service → 真实切换 → 日志可检索——端到端锚）
- [ ] CLI isolation-logs 真实链（真实切换造数 → CLI 检索 stdout 含等级/原因行——argparse 测试形态对齐 5-4 CLI 测试先例）
- [ ] 架构验证器：domain 零外部依赖 + 组合根外零实例化 + 端口方向（interfaces→domain 合法——CLI 直消费仓储端口）
- [ ] 回归面清单全量同步登记（构造点 grep 全量 + 逐一修补 + 5-4/5-5 存量测试全绿）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] **不新建领域事件、不修改既有事件**——`IsolationLevelSwitched`（5-4 交付）是唯一数据源契约，六字段 payload 已覆盖 FR-AC-06 全部要求，零改动零登记。本 Story 新增的是**事件消费投影**（from_event 工厂——AC-1），不是事件。`event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` 零改动（事件未变，双登记现状保持——`sisys.events.reliable.isolation_level_switched` reliable 单通道）。`AuditEvent` 复用不新建（联动时由 AuditServiceImpl 构造）。

#### 数据模型 (Data Models)

- [ ] `IsolationSwitchLog`（`src/domain/entities/isolation_switch_log.py`，`@dataclass(frozen=True)`——追加型日志事实，AuditLog 先例 L18-37）：
  - 字段：`log_id: uuid.UUID`（自铸 UUID4）/ `agent_id: uuid.UUID` / `previous_level: IsolationLevel` / `target_level: IsolationLevel` / `trigger_reason: str` / `approval_chain: tuple[str, ...]` / `switch_timestamp: datetime` / `worm_ref: str | None = None`（预留——OD-1）
  - `@classmethod from_event(cls, event: IsolationLevelSwitched) -> IsolationSwitchLog`——六字段映射工厂（approval_chain `tuple(event.approval_chain)` 冻结拷贝；switch_timestamp 取 `event.switch_timestamp`；log_id `uuid.uuid4()`）
  - `__post_init__` 不变量（失败抛 `EntityValidationError` 242，context 携带字段名与实际类型）：①agent_id/log_id 非 UUID 实例拒；②previous_level/target_level 非 `IsolationLevel` 枚举实例拒（**双条件 isinstance 先行**——5-4 R3-F01 str,Enum hash 混入穿透教训）；③`previous_level == target_level` 拒（切换语义——no-op 不产生日志）；④trigger_reason 非 str 或空白拒；⑤approval_chain 非 tuple 拒 + 元素非 str/空白串拒
  - `to_dict() -> dict[str, Any]`——UUID→str / Enum→value / datetime→`isoformat()` / tuple→list（对齐 audit_log.to_dict 序列化惯例）
- [ ] `IsolationSwitchLogQuery`（端口文件内 frozen dataclass——Query Object 决策规则：多字段组合+分页命中）：`agent_id: uuid.UUID | None = None` / `start_time: datetime | None = None` / `end_time: datetime | None = None` / `level: IsolationLevel | None = None`（命中语义 = previous 或 target 任一）/ `offset: int = 0` / `limit: int = 50`；`__post_init__` 守卫：offset<0 / limit<=0 / limit>500 拒（242）
- [ ] `IsolationSwitchLogSearchResult`（端口文件内 frozen）：`items: tuple[IsolationSwitchLog, ...]` / `total: int` / `offset: int` / `limit: int`
- [ ] PG 表 `isolation_switch_logs`（列/索引/约束见 AC-4——ORM 模型 `IsolationSwitchLogModel` + migration 015 双向一致）

#### 统一端口定义注册与管理 (Port Contract)

- [ ] `IsolationSwitchLogRepository`（`src/domain/ports/isolation_switch_log_repository.py`，`@runtime_checkable Protocol`——**R1 领域层基础端口**：日志持久化与检索是领域基础能力，同层先例 IsolationRepository/AgentRepository）两方法：
  - `async def save(self, log: IsolationSwitchLog) -> None`——追加写入（日志只增不改——RLS 保证）。Raises 契约：`StorageError`（EXCEPTION_103——PG 连接/写入故障）
  - `async def search(self, query: IsolationSwitchLogQuery) -> IsolationSwitchLogSearchResult`——多维检索。Raises 契约：`StorageError`
- [ ] `IsolationManagementService` 构造签名扩展（**R2 应用层具体应用端口组合注入 R1 基础端口**——5-4 四依赖先例延伸）：
  - 第五依赖 `isolation_switch_log_repository: IsolationSwitchLogRepository`（**必填——弃 None 容忍**：审计日志可被静默跳过是合规缺口，5-5 守卫必填先例同哲学；回归面全量同步一次到位）
  - 第六依赖 `audit_service: AuditServicePort | None = None`（**可选**——联动审计是增值索引非 SSOT；resolve_optional + 失败降级，DC-6）
- [ ] 组合根注册元数据：`isolation_switch_log_repository`：v1.0.0 / `IsolationSwitchLogRepository` / `PostgreSQLIsolationSwitchLogRepository`（lambda 注入 `session_factory=resolver.resolve("pg_session_factory")`——**实施时核对组合根既有 session factory 端口名**，以仓库实际为准）/ module=src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository / **SCOPED**（audit_repo 同域先例；SINGLETON isolation_management_service 捕获 SCOPED 无实害注记——5-4 DC-7 形态）/ owner=platform / tags=("agent", "isolation", "audit")
- [ ] **既有端口消费方变更（契约变更登记 ×1）**：`isolation_management_service` lambda 扩展两依赖（契约测试 impl 维度与组合根同步——`test_port_contract_isolation_management_service.py` _DummyResolver 补两分发）
- [ ] 端口契约测试一份（`tests/contracts/test_port_contract_isolation_switch_log_repository.py`，11 维度 + `_DummyResolver`）
- [ ] **禁止**在服务文件本地定义 Protocol/Port 抽象；**禁止**新建语义重复端口（审计联动复用 audit_service——禁新建 isolation_audit_service；通用审计检索复用 1.10 audit search——本端口是隔离域专属日志非通用审计）

#### 端口契约清单执行约束（强制）

- [ ] 本 Story 端口清单唯一真源 = 本 Task 0 定义（`isolation_switch_log_repository` 一新端口 + 一项既有端口消费方变更：IsolationManagementService 构造签名扩展——契约变更登记）
- [ ] 禁止新增未登记端口；禁止未同步 registry/resolver/contract test
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> 原则/适用范围/禁止条款同模板基线。**本 Story 零新领域异常（DC-8）**——agent 段 440-449 已满（5-5 全分配），本 Story 无需开新段；全部失败面由既有异常覆盖：

- [ ] 复用清单（零新增）：`EntityValidationError`(242——实体/Query 不变量)、`StorageError`(103——PG 仓储读写故障透传)、`AgentNotFoundError`(443)/`IsolationStateNotInitializedError`(447)/`IsolationLevelNotSupportedError`(446)（切换守卫序透传——零改动）、`AuditError`(105——audit 联动失败，**被降级捕获记日志不上抛**，DC-6）
- [ ] 零新异常论证：写入失败=存储故障（103 语义精确）；检索无业务异常面（空结果非异常）；实体校验=不变量（242 语义精确）；无新业务规则失败面。`_code_ranges.py` / `exceptions/__init__.py` / `EXCEPTION_HTTP_MAP` / §3.3.2 文档表**零改动**（异常契约四件套豁免——无新增即无登记）
- [ ] BDD 异常路径：StorageError 拒绝路径（AC-2.3）+ 242 不变量路径（AC-1.2）纳入验收 Edge Cases

#### API 契约 (API Contract)

- [ ] 本 Story 无 REST API（检索交付面 = 端口 + CLI；REST 端点归 Epic 7-2——audit router 未挂 create_app 是 1.10 既有形态，维持）。`docs/api/openapi.yaml` 零改动
- [ ] CLI 契约：`sisys-agent isolation-logs --agent-id <uuid> [--level <L4|L3|L2>] [--start <ISO>] [--end <ISO>] [--limit N] [--offset N]`——argparse subparsers 形态对齐 5-4 set-isolation/isolation-status 先例（agent_cli.py L280+）；无结果输出「无隔离切换日志记录」单行；有结果输出多行摘要（log_id 缩短形态 / previous → target / switch_timestamp ISO / trigger_reason 截断 / approval_chain 空显 `-` 非空显 `→` 连接）+ 尾行总数；**level 参数校验**：非法等级值退出码非 0 + 错误提示（str→枚举转换守卫在 CLI 层——5-4 先例，服务不重复校验）

#### 六边形架构约束（必须遵守）

> 四层定义/零依赖原则/依赖方向矩阵同模板基线。本 Story 特别注意：

- [ ] `isolation_switch_log.py`（实体）+ `isolation_switch_log_repository.py`（端口 + Query/Result）全部 domain 层，仅标准库 + 同层 events（IsolationLevelSwitched/IsolationLevel import——from_event 工厂消费事件类型）/ exceptions / entities——`.importlinter` domain 契约（禁 pydantic/sqlalchemy/redis）
- [ ] `PostgreSQLIsolationSwitchLogRepository`（infrastructure）实现 domain 端口——SQLAlchemy async session + outbox 双模式 fallback 先例；禁 import application
- [ ] `IsolationManagementService`（application）构造注入一 domain 基础端口（log repo）+ 一 domain 服务端口（audit_service——AuditServicePort 在 domain/ports）+ 既有四依赖——application→domain 合法；audit_service 类型注解用 domain 端口（**非 infrastructure AuditServiceImpl**——依赖方向）
- [ ] CLI（entrypoints/interfaces）消费 domain 仓储端口（isolation_switch_log_repository）+ application 服务端口（isolation_management_service）——interfaces/entrypoints→domain+application 合法；组合根装配经 lambda

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_isolation_switch_log.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_isolation_switch_log.py`
- [ ] 场景组织：AC 注释横幅分组（带层级标注）+ 全场景逐一 `@scenario` 显式绑定（多行字面量路径 + 场景绑定与步骤交替排列——5-4/5-5 R6 改造后形态，禁 `scenarios()` 批量绑定与 then-pass 占位）；场景名 `AC-x.y - 中文描述`（feature 与 .py 逐字一致）；**禁 Background 背景块门控**（PG 模板形态已废弃——服务依赖场景各自步骤化门控）
- [ ] 18 场景规划（终态 = Task 0 编写 17 + Task 6 追加收尾 1；三属性分档表 Task 0.6 定稿落 docstring）：
  - AC-1 ×2（端口级，无服务依赖，脱离门控）：from_event 六字段映射与审计字段完整 / 实体不变量（242 五场景参数化）
  - AC-2 ×4（服务级，真实 Redis+PG 双门控）：切换成功六字段落库 / no-op 零日志新增 / audit-first 拒绝路径（坏仓储→StorageError→切换被拒 Redis 未变零事件）/ audit 联动记录（audit_log 表 isolation:switch 一条 + correlation_id 匹配）
  - AC-3 ×3（服务级，真实 PG 门控）：按 AGENT 检索 / 按时间范围+隔离等级组合检索（level 双向命中）/ 分页与排序（total/offset/limit + 最新在前）
  - AC-4 ×2（真实 PG 门控）：RLS 篡改拒绝（UPDATE/DELETE 0 行——绕过环境 skip）+ CheckConstraint 拒 no-op 直插 / worm_ref 预留与表结构（ORM `__table_args__` 断言）
  - AC-5 ×2（委托集成计时）：写 P95<50ms（委托 helper）/ 检索 P95<500ms + 成功率 20/20
  - AC-6 ×4（端口级 + 服务级 + 静态）：组合根接线（resolve 可达 + PortSpec 元数据 + 端到端锚——resolve isolation_management_service 真实切换→日志可检索）/ CLI isolation-logs 真实链 / 架构合规静态扫描（AST——domain 零依赖 + 组合根外零实例化）/ 回归面资产在位（5-4/5-5 验收与探针文件存在 + AuditActionType 枚举项注册）
  - 收尾 ×1：完成清单逐项确认（src + tests 四目录文件存在性——5-5 收尾同款）
- [ ] BDD 步骤约束：全部同步 `def` + `_run_async(context["_loop"], ...)`（禁 `@pytest.mark.asyncio`——context 数据丢失）；Redis 场景前置「假如 Redis 缓存服务可用」ping 门控（失败 `pytest.skip` 动态跳过）+ PG 场景前置「假如 PostgreSQL 服务可用」连接门控（asyncpg/引擎探测——PG 模板 L110-135 形态；双服务场景两级门控串联）；参数化步骤显式 `parsers.parse`；异常断言三段式（raises 捕获存 `context["caught"]` → then 断言 code + context）
- [ ] **场景三属性分档表**（Task 0.6 定稿落 docstring）：每场景「层级（端口级/服务级）+ 服务依赖（Redis+PG/PG/无）+ 断言面（字段完整性/顺序与计数/检索矩阵/防篡改/性能/静态扫描）」
- [ ] 显式 `pytestmark = [pytest.mark.acceptance, pytest.mark.redis, pytest.mark.database, pytest.mark.xdist_group("isolation-switch-log-perf")]`（文件名不含 redis/postgres 关键词——显式声明双服务 marker；组名与集成计时场景逐字同组——loadgroup 同 worker 委托缓存命中前提；marker 只用已注册集合——`--strict-markers`）+ 延迟 import 纪律（本 Story 新模块一律步骤函数体内延迟 import）
- [ ] teardown 双面清理：Redis 双键（`build_key("agent", ...)` + `build_key("isolation", ...)`——`_agent_ids` 登记 + exists 复核删净，禁 delete_pattern/flush/全库 scan_iter）+ PG 事务隔离（场景级 session `set_session` + teardown `rollback()` + close——日志写走请求 session 路径 flush，同事务断言可见，rollback 零残留；**RLS/CheckConstraint 场景的 rollback 复位**）；443 拒绝路径预生成随机 uuid 不登记

#### 审计联动契约（Task 0 定稿——DC-6/DC-9）

- [ ] `AuditActionType` 追加 isolation 组：`ISOLATION_SWITCH = "isolation:switch"`（第 8 组——注释组风格对齐既有七组；值格式 `{域}:{动作}` 小写惯例）
- [ ] 联动调用形态（isolation_management_service 切换方法尾部）：
  ```python
  if self._audit_service is not None:
      try:
          await self._audit_service.record(
              actor=f"agent:{agent_id}",
              action_type=AuditActionType.ISOLATION_SWITCH.value,
              target_resource=f"agent:{agent_id}",
              old_value={"level": previous_level.value},
              new_value={"level": target_level.value, "reason": trigger_reason, "approval_chain": list(approval_chain)},
              correlation_id=str(event.event_id),
          )
      except Exception:
          logger.warning("隔离切换联动审计记录失败（主日志已落盘）: agent_id=%s", agent_id, exc_info=True)
  ```
- [ ] 降级语义：联动失败不回滚不重试（主日志 SSOT 已在 log_repository 落盘；audit_log 是联动索引——PersistentNoteTaker L248-268 先例同款）；组合根 `resolve_optional("audit_service")` 注入

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证——ModuleNotFoundError/断言红为合法红）
- [ ] 规范文档通过人工评审或自动化校验
- [ ] **链路接线断言清单**已定义（Epic 4 回顾行动项 7.1-1）：①`isolation_switch_log_repository` 组合根 register_port 装配验证（resolve 可达 + isinstance + PortSpec 元数据 + SCOPED）②`isolation_management_service` lambda 五/六依赖注入确认（**端到端锚：resolve 服务 → 真实切换 → search 可检索——lambda 漏注入则日志静默缺失**）③audit 联动接线（resolve_optional 可达性 + 降级路径）④CLI isolation-logs 命令注册（--help 可见）⑤事件面零改动复验（IsolationLevelSwitched 双登记不漂移——yaml + DEFAULT_MAPPINGS 断言沿用 5-4 验收锚）

---

### TDD 循环约束（适用于每个 Task）

> 每 Task 依次执行 🔴红→🟢绿→🟡变异→🔄重构；变异实证 = 对新行为契约的断言改坏→红→还原→绿（Epic 4 行动项 7.1-2 强制）。禁止行为四条同模板基线（先码后测/测试后置/跳红/跳变异）。
>
> **套件型 Task 豁免条款**（Task 4 性能/防篡改场景 / Task 5 架构验证 / Task 6 收尾场景）：这类 Task 编写的是**验证型测试层**（对 Task 1-3 已交付链编写断言——首跑即绿，无设计红可先）。其红由 Task 0 验收红阶段前置承担；断言活性由 🟡 变异实证强制保证（如：from_event 字段映射改错→六字段断言红；audit-first 顺序对调→顺序断言红；RLS 策略删除→0 行断言红）——变异是该类 Task 的红替代物，不可跳过。

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| TDD 单元测试 | IsolationSwitchLog 实体 | from_event 六字段/不变量五场景/to_dict/frozen | `tests/unit/domain/entities/test_isolation_switch_log.py` | Task 1 |
| TDD 单元测试 | IsolationManagementService 审计接线 | audit-first 顺序/no-op 零日志/443·447 零日志/audit 联动+降级/坏仓储拒绝（AsyncMock spec 端口——单测 Mock 端口合规）+ 存量构造点同步 | `tests/unit/application/services/test_isolation_management_service.py`（追加） | Task 3 |
| TDD 单元测试 | PG 仓储逻辑面 | save 双模式分派/search 条件构建（mock session/AsyncMock——薄单测，真实 PG 断言归集成） | `tests/unit/infrastructure/storage/postgresql/test_isolation_switch_log_repository.py` | Task 2 |
| TDD 契约测试 | isolation_switch_log_repository | 11 维度 + _DummyResolver | `tests/contracts/test_port_contract_isolation_switch_log_repository.py` | Task 2 |
| TDD 契约测试 | isolation_management_service（存量） | impl 维度与 lambda 同步（_DummyResolver 补两分发） | `tests/contracts/test_port_contract_isolation_management_service.py`（追加） | Task 3 |
| TDD 单元测试 | AuditActionType 扩展 | ISOLATION_SWITCH 枚举值注册 | `tests/unit/domain/events/audit_events/test_audit_events.py`（追加） | Task 3 |
| TDD 验收测试 | Gherkin + BDD | 17 场景 Task 0 编写（收尾 Task 6 追加成 18 终态）；各 Task 转绿——AC-1 随 Task 1、AC-2 随 Task 3、AC-3 随 Task 2/4、AC-4 随 Task 4、AC-5 随 Task 4、AC-6 随 Task 3/5 | `test_acceptance_isolation_switch_log.feature/.py` | Task 0-6 |
| 集成测试 | 全链（真实 Redis+PG） | 切换→日志落库六字段/检索矩阵/RLS+CheckConstraint/P95 双指标/成功率 20/20/no-op 零新增/audit-first 拒绝真实链 | `tests/integration/test_integration_isolation_switch_log.py` | Task 4 |
| SDD 架构验证 | 六边形约束 | domain 零外部依赖/组合根外零实例化/端口方向/接线静态锚 | `tests/unit/architecture/test_arch_isolation_switch_log.py` | Task 5 |
| CLI 单元测试 | isolation-logs 命令 | 参数解析/level 校验/输出形态/空结果（对齐 5-4 CLI 测试先例——grep `test_agent_cli` 或 `test_*cli*` 定位既有 CLI 测试文件追加） | 既有 CLI 测试文件（追加） | Task 3 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] 整体 ≥80%（P0 阻断）；domain ≥90%（实体不变量主战场）；**应用层 ≥85%**（audit-first 接线主战场）；infrastructure ≥75%（PG 仓储）；四档与 `scripts/check_coverage_gates.py` 一致
- [ ] 集成测试覆盖率 ≥75%（沿 5-2/5-3/5-4/5-5 先例）；关键分支可执行口径：audit-first 四分支（成功落库/no-op 拒/守卫拒/仓储故障拒）+ 检索四维各配独立命名测试用例（用例名即分支清单）

#### 代码质量门禁

- [ ] `ruff check src/ tests/` + `mypy src/`（pre-commit mypy 覆盖 tests/）+ `pre-commit run` 全过
- [ ] 三条红线自查零输出（`raise ValueError`/手动 `HTTPException`/继承内置 Exception）+ 零抑制注释
- [ ] 提交信息零 AI 署名

#### 测试隔离约束

> 基线同模板（事务隔离/UUID 唯一/并行隔离/清理粒度/asyncio 纪律全表）。本 Story 特别注意：

- [ ] **PG 事务隔离**：集成/验收场景级 session `set_session(test_session)` → 日志写走请求 session 路径（add+flush——不走 fallback）→ 同事务断言可见 → teardown `rollback()` + close——**零残留零 delete/truncate**（集成 postgres_session begin+rollback 先例 L453-536）；RLS/CheckConstraint 触发 IntegrityError 后必须 `session.rollback()` 复位再继续
- [ ] **Redis 双键清理**：`_agent_ids` 全登记（InstantiateAgentUseCase 构造的每个真实 Agent），teardown 逐 agent 删 `build_key("agent", ...)` + `build_key("isolation", ...)` 双键 + exists 复核删净
- [ ] **场景级独立 Redis 客户端 + `_run_async` 同循环**（session 级客户端跨场景 "Event loop is closed"——禁共享 fixture）
- [ ] **手动组装纪律**：验收/集成禁 `resolve("isolation_management_service")` 发真实命令——SINGLETON 跨 function-scope 循环复用死连接 + 其 PG 依赖生命周期不可控；一律场景级客户端手动组装（IsolationManagementService + 双 Redis 仓储 + PG 日志仓储[测试 session 注入] + 真实/降级 audit_service 全真实链——`_assemble_real_chain` 形态扩展）；resolve 仅 AC-6.1 接线断言且禁发命令
- [ ] **audit 联动验收面**：真实 audit_service（PG session 同事务——audit_log 写入同 rollback 回收）；降级场景归单测（AsyncMock side_effect AuditError——验收禁 mock，降级是异常注入面）
- [ ] **计时场景**：新 `xdist_group("isolation-switch-log-perf")` 串行 + benchmark 场景级标记；`SWITCH_LOG_WRITE_P95_LIMIT_SECONDS = 0.05` / `SWITCH_LOG_SEARCH_P95_LIMIT_SECONDS = 0.5` 常量单源（集成定义/验收共享 import）
- [ ] **RLS 环境敏感**：deny 断言前置探测连接角色（`rolbypassrls` 或表 owner 绕过）→ 绕过环境 `pytest.skip` 动态跳过（禁写死 skip——CI compose 应用连接非 superuser 为绿色路径）
- [ ] BDD 步骤禁 `@pytest.mark.asyncio`；步骤函数同步 def + `_run_async` 调度
- [ ] 本 Story 计时组与 5-4（agent-isolation-perf）/5-5（agent-triple-isolation-perf）xdist_group 名互异不冲突

**验证要求：** `pytest tests/` 通过（仓库默认 `-n auto --dist loadgroup`——pyproject addopts；无需显式 `-n 8`）；连续 5 次无随机失败；`ruff check` + `mypy` 通过；5-4/5-5 验收与探针套件全量回归绿。

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | from_event 六字段映射 | Task 1 | IsolationSwitchLog.from_event | test_isolation_switch_log + 验收 AC-1.1 |
| AC-1 | 实体不变量（242 五场景） | Task 1 | `__post_init__` 守卫 | test_isolation_switch_log + 验收 AC-1.2 |
| AC-2 | audit-first 顺序与落库六字段 | Task 3 | switch 方法日志插位 | test_isolation_management_service（追加）+ 验收 AC-2.1 |
| AC-2 | no-op 零日志 | Task 3 | no-op 分支零 save | 同上 + 验收 AC-2.2 |
| AC-2 | 日志失败切换被拒 | Task 3 | save 上抛 fail-closed | 同上 + 验收 AC-2.3 |
| AC-2 | audit 联动与降级 | Task 3 | record + try/except 降级 | 同上 + test_audit_events（追加）+ 验收 AC-2.4 |
| AC-3 | 四维检索 + 分页排序 | Task 2/4 | Query/Result + search 实现 | 仓储单测 + test_integration_* + 验收 AC-3×3 |
| AC-4 | 表结构/索引/CheckConstraint | Task 2 | ORM + migration 015 | 仓储单测 + 集成 + 验收 AC-4.2 |
| AC-4 | RLS 防篡改（deny UPDATE/DELETE） | Task 2/4 | migration RLS 段 + 实证 | 集成 + 验收 AC-4.1 |
| AC-5 | 写 P95<50ms | Task 4 | 委托计时 helper | test_integration_* + 验收 AC-5.1 |
| AC-5 | 检索 P95<500ms + 成功率 | Task 4 | 计时 + 20/20 | 同上 + 验收 AC-5.2 |
| AC-6 | 组合根接线 + resolve | Task 2/3 | 注册 + lambda 扩展 | 契约测试 + 验收 AC-6.1 |
| AC-6 | CLI isolation-logs | Task 3 | argparse 子命令 | CLI 测试（追加）+ 验收 AC-6.2 |
| AC-6 | 架构合规 | Task 5 | 验证器 A-C | test_arch_* + 验收 AC-6.3 |
| AC-6 | 回归面零破坏 | Task 3 | 构造点全量同步 | 5-4/5-5 存量全绿 + 验收 AC-6.4 |
| 全 AC | 收尾清单 | Task 6 | 完成清单场景 | 验收收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则同模板。每 Subtask 组内按领域粒度拆分红绿循环。

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部

- [ ] Subtask 0.1: 定义数据模型规范——IsolationSwitchLog（frozen 八字段 + from_event + 不变量五场景 + to_dict）+ IsolationSwitchLogQuery/IsolationSwitchLogSearchResult + PG 表结构（本文件「数据模型」节为唯一真源）
- [ ] Subtask 0.2: 定义端口契约——IsolationSwitchLogRepository 两方法 + IsolationManagementService 五/六依赖签名扩展 + 组合根注册元数据（契约变更登记 ×1）
- [ ] Subtask 0.3: 定义异常契约——零新异常复用清单（242/103/443/446/447/105）+ 零新增论证
- [ ] Subtask 0.4: 定义审计联动契约——AuditActionType.ISOLATION_SWITCH + record 调用形态 + 降级语义（DC-6/DC-9 节）
- [ ] Subtask 0.5: 定义 migration 015 契约——列/索引四/CheckConstraint/RLS 四策略 + FORCE + downgrade 对称（AC-4 节）
- [ ] Subtask 0.6: 编写 Gherkin `test_acceptance_isolation_switch_log.feature`（17 场景）+ BDD 步骤实现骨架 `.py`（@scenario 全显式绑定 + context dict fixture + Redis/PG 双门控 + 双面清理）+ **17 场景三属性分档表**定稿（docstring）
- [ ] Subtask 0.7: 运行验收测试确认失败（🔴 红阶段——ModuleNotFoundError/断言红为合法红）
- [ ] Subtask 0.8: 移交留项与偏离声明处置落盘（deferred-work.md：#7 竞态注记追加 + R1-DF2 5.6 注记——Task 0 评估表；**偏离声明 OD-1/OD-2/OD-3 三项同步登记**——OD-1 WORM gap 链接 Story 13-4（SOX）承接方 + RLS 补偿控制差距三注 / OD-2 链接 9-4·9-5 协作组 / OD-3 链接 9-3（FR-AC-09）——gap 四要素齐备：描述/触发条件/归宿/承接方链接）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义；验收测试红阶段确认；链路接线断言清单 L1-L5 定义

---

### Task 1: 领域层——IsolationSwitchLog 实体

**关联 AC:** AC-1（全部）

#### TDD 循环 A：IsolationSwitchLog 实体

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/entities/test_isolation_switch_log.py`（from_event 六字段映射 / 不变量五场景 / to_dict / frozen 断言） |
| 🟢 绿 | 实现 `src/domain/entities/isolation_switch_log.py`（frozen + from_event + `__post_init__` + to_dict） |
| 🟡 变异 | from_event 某字段映射改错→六字段断言红；不变量条件删除→对应用例红；还原→绿 |
| 🔄 重构 | 类型注解 + Google 风格全中文 docstring + `entities/__init__.py` 导出 |

- [ ] Subtask 1.1: 🔴 红 — 编写实体失败测试（六字段/五不变量/to_dict/frozen）
- [ ] Subtask 1.2: 🟢 绿 — 实现最小代码
- [ ] Subtask 1.3: 🟡 变异 — 映射/不变量突变实证
- [ ] Subtask 1.4: 🔄 重构 — docstring/导出/ruff+mypy

**完成标准/Definition of Done:**
- [ ] 实体实现完成；验收 AC-1×2 场景转绿；domain 覆盖率 ≥90%

---

### Task 2: 端口与存储——仓储端口 + PG 模型 + migration 015 + 仓储实现 + 契约测试

**关联 AC:** AC-3（端口面）、AC-4（表结构）、AC-6.1（注册）

#### TDD 循环 A：端口 + Query/Result

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 Query/Result 守卫测试（offset/limit 边界 242）+ 端口 Protocol 定义测试（runtime_checkable） |
| 🟢 绿 | 实现 `src/domain/ports/isolation_switch_log_repository.py` |
| 🔄 重构 | docstring（Raises 契约）+ `ports` 导出 |

#### TDD 循环 B：ORM 模型 + migration + 仓储实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/postgresql/test_isolation_switch_log_repository.py`（模型 `__table_args__` 断言：约束/索引名；save 双模式分派：ContextVar 命中→add+flush，未命中→session_factory fallback；search 条件构建：mock session 断言 where 子句组装——薄单测） |
| 🟢 绿 | 实现 `IsolationSwitchLogModel` + `015_isolation_switch_logs` migration + `PostgreSQLIsolationSwitchLogRepository`（双模式 session + 动态条件 + count + timestamp desc + offset/limit） |
| 🟡 变异 | RLS deny 策略删一行→集成 0 行断言红（归 Task 4 实证）；level 命中条件从 or_ 改 eq→集成双向断言红；还原→绿 |
| 🔄 重构 | `models/__init__.py` 注册 + docstring + ruff+mypy |

#### TDD 循环 C：组合根注册 + 契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/contracts/test_port_contract_isolation_switch_log_repository.py`（11 维度 + _DummyResolver） |
| 🟢 绿 | 组合根 `# === Story 5.x ===` 区段追加注册（SCOPED + owner=platform + tags） |
| 🔄 重构 | lambda 注入 session_factory（核对组合根既有 PG session factory 端口名——以仓库实际为准） |

- [ ] Subtask 2.1: 🔴 红 — 端口/Query/Result 测试
- [ ] Subtask 2.2: 🟢 绿 — 端口定义
- [ ] Subtask 2.3: 🔴 红 — 模型/迁移/仓储测试
- [ ] Subtask 2.4: 🟢 绿 — 模型 + migration 015 + 仓储实现
- [ ] Subtask 2.5: 🟡 变异 — 双模式/命中条件突变实证
- [ ] Subtask 2.6: 🔴🔴🟢 — 契约测试 + 组合根注册
- [ ] Subtask 2.7: 🔄 重构 — 导出/注册/docstring/门禁

**完成标准/Definition of Done:**
- [ ] 仓储三件（端口/模型+迁移/实现）交付；`alembic upgrade head` 全新库可执行（本地验证）；契约 11 维度绿；验收 AC-3×3、AC-4×2 随 Task 4 集成面转绿（端口级断言本轮即绿）

---

### Task 3: 切换链接线——audit-first 写入 + audit 联动 + AuditActionType + CLI + 回归面

**关联 AC:** AC-2（全部）、AC-6.1/6.2/6.4

#### TDD 循环 A：IsolationManagementService 五/六依赖 + audit-first 插位

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/application/services/test_isolation_management_service.py` 追加：audit-first 顺序（save 先于 Redis save——AsyncMock calls 顺序断言）/ no-op 零 save / 443·447 零 save / 坏仓储 StorageError 上抛且零 Redis 写零事件 / audit 联动调用参数 + 降级（side_effect AuditError → 切换成功 + caplog warning）/ 存量构造点全量补两依赖 |
| 🟢 绿 | 构造签名扩展 + switch 方法插位（from_event → save → 既有链 → 联动）|
| 🟡 变异 | audit-first 顺序对调（save 移到 Redis 后）→ calls 顺序断言红；联动 except 删除→降级用例红；还原→绿 |
| 🔄 重构 | docstring 更新（模块头 Raises 契约 + audit-first 叙事）+ ruff+mypy |

#### TDD 循环 B：AuditActionType 扩展 + 组合根 lambda + CLI

| 阶段 | 动作 |
|------|------|
| 🔴 红 | test_audit_events.py 追加 ISOLATION_SWITCH 枚举断言；CLI 测试追加 isolation-logs（参数解析/level 校验/输出/空结果）|
| 🟢 绿 | 枚举第 8 组 + 组合根 lambda 扩展（resolve + resolve_optional）+ agent_cli 子命令 |
| 🟡 变异 | 枚举值改错→断言红；lambda 漏注入第六依赖→端到端锚红（resolve→切换→audit_log 无记录）；还原→绿 |
| 🔄 重构 | CLI --help 文本 + 模块头使用示例更新 |

#### TDD 循环 C：回归面全量同步（苦役先例——5-5 Task 3）

| 阶段 | 动作 |
|------|------|
| 🔴→🟢 | 全仓 grep `IsolationManagementService(` 构造点逐一登记修补：组合根 lambda / 契约 _DummyResolver（test_port_contract_isolation_management_service.py）/ 单测工厂 / 集成 `_assemble_real_chain`（test_integration_agent_isolation.py）+ 5-5 集成（test_integration_agent_triple_isolation.py / test_integration_isolation_security.py）/ 验收手动组装（test_acceptance_agent_isolation.py / test_acceptance_agent_triple_isolation.py / test_acceptance_agent_workflow.py）——**实施时以 grep 实际清单为准逐一修补并登记**；5-4/5-5 存量测试全量回归绿 |

- [ ] Subtask 3.1: 🔴 红 — 服务接线失败测试（顺序/零调用计数/降级/参数）
- [ ] Subtask 3.2: 🟢 绿 — 五/六依赖 + audit-first 插位 + 联动
- [ ] Subtask 3.3: 🟡 变异 — 顺序对调/降级删除实证
- [ ] Subtask 3.4: 🔴🟢 — 枚举扩展 + lambda + CLI 子命令
- [ ] Subtask 3.5: 🟡 变异 — 端到端锚（漏注入红）
- [ ] Subtask 3.6: 🟢 — 回归面构造点全量同步 + 5-4/5-5 存量全绿
- [ ] Subtask 3.7: 🔄 重构 — docstring/门禁

**完成标准/Definition of Done:**
- [ ] 接线完成；验收 AC-2×4、AC-6.1/6.2 转绿；5-4/5-5 回归零破坏；应用层覆盖率 ≥85%

---

### Task 4: 集成测试与性能——全链断言 + 检索矩阵 + RLS/CheckConstraint 实证 + P95

**关联 AC:** AC-3（集成面）、AC-4.1、AC-5（全部）

> 性质说明：本 Task 对 Task 1-3 已交付链编写验证型测试（套件型豁免——红由 Task 0 前置，活性由变异保证）。

- [ ] Subtask 4.1: 编写 `tests/integration/test_integration_isolation_switch_log.py`——真实 Redis+PG（real_redis + real_postgres_engine/postgres_session 门控）：场景① 切换全链→检索六字段逐项（含 approval_chain JSONB roundtrip）② no-op 零新增 ③ audit-first 拒绝（坏连接仓储实例→StorageError→Redis 等级未变+零事件——_RecordingEventPublisher）④ audit 联动真实 audit_service→audit_log 表 isolation:switch 记录 ⑤ 检索矩阵（四维独立+组合+分页+排序——3 Agent×2 条造数）⑥ RLS deny UPDATE/DELETE 0 行（绕过环境 skip）+ CheckConstraint IntegrityError ⑦ 写 P95（`_PERF_CACHE` + 20 采样 + 0.05 常量）⑧ 检索 P95（0.5 常量）⑨ 成功率 20/20
- [ ] Subtask 4.2: 变异实证——RLS deny 行删除→场景⑥红；level 命中 or_→eq→场景⑤双向断言红；阈值常量突变→⑦⑧红；还原→绿
- [ ] Subtask 4.3: 验收 AC-3×3/AC-4×2/AC-5×2 场景转绿（委托计时缓存命中验证）

**完成标准/Definition of Done:**
- [ ] 集成九场景全绿；P95 双指标达标；验收对应场景全绿；计时组与 5-4/5-5 组不冲突

---

### Task 5: SDD 架构约束验证测试

**关联 AC:** AC-6.3

> 性质说明：SDD 规范验证测试（验证架构约束是否被遵守），非 TDD 单元测试。

- [ ] Subtask 5.1: 创建 `tests/unit/architecture/test_arch_isolation_switch_log.py`——验证器 A：domain 零外部依赖（isolation_switch_log.py/isolation_switch_log_repository.py AST 扫描——白名单标准库+同层 import；黑名单 pydantic/sqlalchemy/redis 等）；验证器 B：组合根外零实例化（PostgreSQLIsolationSwitchLogRepository 实例化点仅 composition_root.py + tests/——src/ 扫描）；验证器 C：端口方向（agent_cli import 白名单——domain/application 合法、infrastructure 禁入）
- [ ] Subtask 5.2: 变异实证——实体文件注入 sqlalchemy import→验证器 A 红；还原→绿
- [ ] Subtask 5.3: 验收 AC-6.3 场景转绿

**完成标准/Definition of Done:**
- [ ] 架构验证器三件全绿；违规即红；循环依赖检测沿用 ruff/isort（不引入新工具）

---

### Task 6: 开发结束验收测试

**关联 AC:** 全部

> 性质说明：对 Story 收尾阶段的交付物与完成清单进行最终验收。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 feature 收尾验收场景（完成清单） |
| 🟢 绿 | 编写 BDD 步骤实现（文件存在性检查——src 文件清单 + tests 四目录清单，missing 断言） |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [ ] Subtask 6.1: 场景 1 — src 完成清单逐项确认（实体/端口/模型/迁移/仓储/服务/CLI/组合根 8 文件）
- [ ] Subtask 6.2: 场景 2 — tests 四目录（unit/contracts/integration/acceptance）完成清单逐项确认
- [ ] Subtask 6.3: 运行全量验收（18 场景终态）+ `pytest tests/` + `ruff check` + `mypy` 收尾校验 + 5-4/5-5 回归终验
- [ ] Subtask 6.4: deferred-work.md 留项终态更新（#7 注记/R1-DF2 注记落盘确认）

**完成标准/Definition of Done:**
- [ ] 18 场景全绿；全量回归零 5.6 面新失败；Story 可进入 `review`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ 事件驱动（reliable 单通道——RabbitMQ + PG Outbox）+ 审计防篡改（PG RLS 追加型日志）
- **设计约束:** 领域层零依赖（实体/端口仅标准库）；依赖方向矩阵（interfaces→domain 合法——CLI 直消费仓储端口）；端口注册 PortSpec 元数据 + 组合根唯一实例化点；Query Object 决策规则（多字段+分页命中）
- **接口治理:** 统一端口注册/Registry/Resolver/ContractGate、Composition Root 装配、契约优先（11 维度契约测试）、版本化兼容、禁止跨模块直接依赖实现类
- **技术栈:** Python 3.11+（`datetime.UTC`）/ SQLAlchemy 2.0 async（JSONB/UUID PG 方言）/ alembic（head 014 → 015）/ Typer CLI（agent_cli 为 argparse subparsers 形态）/ PostgreSQL + Redis

### 关键架构决策 Key Design Decisions

**DC-1 实体形态——frozen + from_event 工厂（事件 payload 单一真源）**
- 实体 `@dataclass(frozen=True)`（追加型日志事实不可变——AuditLog 先例；与 IsolationState 可变聚合对照）；`from_event` 是唯一构造通道（事件 payload 六字段 = FR-AC-06 六要素，映射零加工——审批链 list→tuple 冻结、时间戳取 `switch_timestamp` 非 `event.timestamp`——单钟纪律）
- 备选：直构造多参数工厂——弃（事件是 5-5 钉明的数据源契约，from_event 保证日志与事件双投影一致）

**DC-2 写入链路——audit-first 同步内嵌（vs 事件订阅异步消费）**
- 选定：`switch_isolation_level` 内嵌同步写（构造事件 → from_event → **log save（失败上抛=切换被拒）** → Redis save → 事件发布 → audit 联动）
- 论证：①审计不丢要求——同步写最可靠，失败即拒绝切换（无审计痕迹的切换不允许发生）；②reliable 事件**不能**经 `DualChannelEventBus.subscribe` 订阅（dual_channel_event_bus.py L82-83 抛 InvalidStateError），消费需 RabbitMQ 消费侧/Outbox 轮询基建——**归 5.7**（5-4 L284「接线归消费方 Story 立项时决定」）；③Outbox 表已存在事件持久化落点（event_outbox）但为投递中间态非审计载体（24h 归档/cleanup 会清理）；④simplicity first——内嵌 4 行核心逻辑 vs 消费者+幂等+重试一套基建
- 顺序论证（audit-first vs state-first）：state-first 在日志失败时丢审计（合规红线）；audit-first 在「日志写成功+Redis 写失败」窗口产生未生效切换的日志记录（误报）——**两害相权：审计合规宁可多记不可漏记**，误报窗口登记风险 #1（PG 可用而 Redis 故障的极窄窗口，StorageError 上抛调用方可见切换失败）
- 备选：事件订阅 handler 异步写——弃（DC-2 论证②③）；装饰器包装服务——弃（组合根 lambda 复杂化+顺序不透明）

**DC-3 检索端口——save/search 两方法 + level 双向命中**
- `search` 单方法承载四维+分页（Query Object）；level 命中语义 = previous 或 target 任一（or.md「按隔离等级检索」——切换涉及该等级即命中；单侧命中会漏「从 L3 切出」或「切到 L3」半边审计面）
- 结果强类型 `tuple[IsolationSwitchLog, ...]`（audit search 返回 dict 是 1.10 历史形态——新端口用实体，类型安全）
- 检索**无 443 守卫**（Agent TTL 过期后历史日志仍可查——审计要求；与写入面守卫形成对照，单测锁定该差异）

**DC-4 防篡改——RLS（ENABLE + **FORCE**）+ CheckConstraint 双层**
- RLS 四策略照抄 002_audit_tables（INSERT/SELECT 放行 + deny UPDATE/DELETE——DELETE policy 仅 USING 子句，002 已修正的 PG 语法约束）；**追加 `FORCE ROW LEVEL SECURITY`**（表 owner 默认绕过 RLS——FORCE 后受约束；superuser BYPASSRLS 属性仍绕过——环境敏感性登记，测试动态探测 skip）
- CheckConstraint `previous_level != target_level`：DB 层拒绝 no-op 日志（实体不变量的 DB 投影——双层防线，直插旁路也被拦）
- WORM 等效性论证：RLS deny UPDATE/DELETE = 追加型不可改写（应用连接面）；MinIO Object Lock 7 年归档是 §8.5 运营管线（OD-1 裁剪归 V1）——与 1.10 audit_log 现状对齐（audit WORMManager 未接线，audit_log 防篡改同为 RLS）

**DC-5 PG 仓储双模式 session（CLI 上下文可写）**
- 照抄 `PostgreSQLOutboxRepository`（Story 4-7 修复形态）：`get_session()` 命中（HTTP 请求事务内 add+flush）→ `RuntimeError` 时经注入 `session_factory` 走 `session_context()` 独立会话 commit（CLI/后台路径）
- 不沿用 `PostgreSQLAdapter` 泛型基类（audit_repository_impl 直实现 Port 先例——本仓储有 search 定制查询与 fallback 双路径，基类 get_by_id/list_all 面板冗余）
- 测试策略：集成/验收走请求 session 路径（set_session 测试 session → flush → rollback 零残留）；fallback 路径薄单测（mock factory）+ CLI 真实链（E2E 面）

**DC-6 audit 联动——可选注入 + 降级容错（双层审计：SSOT + 联动索引）**
- 主日志 `IsolationSwitchLog`（隔离域 SSOT——六字段强类型+多维检索）+ 联动 `audit_service.record`（1.10 统一审计流索引——action_type=`isolation:switch` 使隔离切换进入全局审计检索面）
- audit_service **可选注入**（`AuditServicePort | None` + 组合根 `resolve_optional`——composition_root L2201 PersistentNoteTaker 先例）+ 失败降级（try/except logger.warning 不回滚不重试）——论证：主日志已落盘（SSOT），联动是增值索引；且 AuditServiceImpl→audit_repo 走请求 ContextVar session，CLI 上下文无 session 时 record 抛错——必填+上抛会使 CLI set-isolation 在无 PG 请求环境崩溃，降级保切换主链可用
- 与第五依赖（log repo 必填）的差异化论证：log repo 是合规 SSOT（静默跳过=合规缺口→必填上抛）；audit 联动是 best-effort 索引（降级容忍）

**DC-7 WORM 归档裁剪（偏离声明 OD-1）**——worm_ref 字段预留（nullable，检索 roundtrip 保持 None）；MinIO WORM 24h 管线归 V1 合规归档管线（触发条件：审计归档批处理立项；与 1.10 WORMManager/archive 未接线现状对齐；防篡改由 RLS 等效承载——DC-4）

**DC-8 零新领域异常**——agent 段 440-449 已满（5-5 全分配）；失败面全覆盖于既有异常（242 不变量/103 存储/443·446·447 守卫/105 audit 降级捕获）；避免开 450-459 新段子域归属争议（隔离日志实体在 agent 域与 audit 域交界——复用既有异常是最小侵入解）

**DC-9 AuditActionType.ISOLATION_SWITCH**——枚举第 8 组 isolation（值 `isolation:switch`——`{域}:{动作}` 小写惯例）；1.10 资产合法扩展（枚举组追加不破坏既有 consumer）

**DC-10 CLI isolation-logs 检索命令**——MVP 检索交付面 = 端口 + CLI（REST 归 Epic 7-2；audit router 未挂 create_app 是 1.10 既有形态——本 Story 不扩大 REST 面）；argparse subparsers 对齐 5-4 先例；level 参数 CLI 层枚举转换守卫（服务不重复校验——5-4 DC-5 纪律）

**DC-11 组合根生命周期——SCOPED + captive 注记**——对齐 audit_repo 同域先例（PG ContextVar session 域）；SINGLETON isolation_management_service 捕获 SCOPED 依赖无实害注记（5-4 DC-7 形态——仓储无状态，session 每调用现取）

**关键决策对照表（选中方案 vs 备选）：**

| 决策点 | 选中 | 备选（弃因） |
|--------|------|-------------|
| 写入链路 | audit-first 同步内嵌（DC-2） | 事件订阅异步（reliable 不可订阅+基建归 5.7）；装饰器（顺序不透明） |
| 主存储 | 独立 PG 表（架构 §9 钉死 L2） | 复用 audit_log 表（无等级列——JSONB 检索性能差+违背独立实体定义）；Redis（无多维检索+TTL 失效违审计） |
| 防篡改 | RLS+FORCE+CheckConstraint（DC-4） | MinIO Object Lock（归档管线 OD-1）；应用层 checksum（拦不住 SQL 直改） |
| audit 联动 | 可选+降级（DC-6） | 必填上抛（CLI 无 session 崩溃）；不做联动（5-5 移交明确要求 AuditService 调用） |
| 实体构造 | from_event 工厂（DC-1） | 多参直构造（双投影漂移风险） |

### 风险登记

| # | 风险 | 处置 |
|---|------|------|
| 1 | audit-first 误报窗口（日志写成功+Redis 写失败→记录未生效切换） | 登记窗口（PG 可用而 Redis 故障极窄）；StorageError 上抛调用方可见；V1 动态触发立项时评估补偿（延迟确认/状态回写） |
| 2 | RLS 环境敏感（owner/BYPASSRLS 绕过→deny 断言 flaky） | FORCE ROW LEVEL SECURITY + 测试动态探测（rolbypassrls/owner 检查）→ 绕过环境 pytest.skip 动态跳过（合规纪律） |
| 3 | 构造签名扩展回归面遗漏（5-4/5-5 手动组装链漏补→存量红） | Task 3 循环 C 全仓 grep `IsolationManagementService(` 登记修补苦役先例；5-4/5-5 存量全量回归终验 |
| 4 | PG 仓储 fallback 在测试中真写库（session_factory 注入生产 factory→集成测试污染） | 测试一律走请求 session 路径（set_session）；手动组装链注入测试 session_factory 或仅请求路径；验收 teardown rollback 复核 |
| 5 | 并发切换日志乱序（5-4 风险 #7 延伸——日志序=事件序同竞态窗口） | MVP CLI 单发不可达；deferred-work #7 追加 5.6 注记（Task 0.8） |
| 6 | SINGLETON×SCOPED captive（isolation_management_service 捕获 log repo） | DC-11 无实害注记（仓储无状态 session 现取）；5-4 DC-7 先例 |

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── entities/
│   │   └── isolation_switch_log.py            # 新建：IsolationSwitchLog（frozen + from_event）
│   └── ports/
│       └── isolation_switch_log_repository.py # 新建：端口 + Query + Result
├── application/
│   ├── ports/
│   │   └── isolation_management.py            # 修改：docstring（审计语义/Raises）
│   └── services/
│       └── isolation_management_service.py    # 修改：五/六依赖 + audit-first 插位 + audit 联动
├── domain/events/
│   └── audit_events.py                        # 修改：AuditActionType.ISOLATION_SWITCH（第 8 组）
├── infrastructure/
│   └── storage/postgresql/
│       ├── models/
│       │   ├── isolation_switch_log.py        # 新建：IsolationSwitchLogModel
│       │   └── __init__.py                    # 修改：模型注册
│       └── repository/
│           └── isolation_switch_log_repository.py  # 新建：双模式 session 仓储实现
├── entrypoints/
│   └── agent_cli.py                           # 修改：isolation-logs 子命令
└── composition_root.py                        # 修改：新端口注册 + isolation_management lambda 扩展

deploy/postgresql/alembic/versions/
└── 015_isolation_switch_logs.py               # 新建：表+索引+CheckConstraint+RLS(+FORCE)

tests/
├── unit/domain/entities/test_isolation_switch_log.py          # 新建
├── unit/domain/events/audit_events/test_audit_events.py       # 追加
├── unit/application/services/test_isolation_management_service.py  # 追加+存量同步
├── unit/infrastructure/storage/postgresql/test_isolation_switch_log_repository.py  # 新建（薄单测）
├── unit/architecture/test_arch_isolation_switch_log.py        # 新建（验证器 A-C）
├── contracts/test_port_contract_isolation_switch_log_repository.py  # 新建（11 维度）
├── contracts/test_port_contract_isolation_management_service.py     # 追加（_DummyResolver 两分发）
├── integration/test_integration_isolation_switch_log.py      # 新建（九场景+计时）
├── acceptance/test_acceptance_isolation_switch_log.feature   # 新建（17+收尾=18 场景）
├── acceptance/test_acceptance_isolation_switch_log.py        # 新建（BDD 步骤）
└── （回归面同步：test_acceptance_agent_isolation/triple、test_integration_agent_isolation/
    triple、isolation_security、agent_workflow、既有 CLI 测试——Task 3 grep 清单为准）

docs/architecture/architecture.md              # 修改：§5 注记（5.6 交付）+ §13 目录树（Task 6）
_bmad-output/implementation-artifacts/deferred-work.md  # 修改：#7/R1-DF2 注记（Task 0/6）
_bmad-output/implementation-artifacts/sprint-status.yaml  # 修改：5-6 状态流转
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 5.5](./5-5-agent-triple-hard-isolation.md)（v2.2.1 收敛态——文档审查 5 轮 + 代码审查 5 轮完整教训链）

**关键学习/Key Learnings:**
- **构造签名扩展 = 回归面苦役**——全仓 grep 构造点逐一登记补依赖（5-5 Task 3 十二构造点先例）；验收侧真实组装（禁 mock）、集成侧 AsyncMock 工厂合规的分层分派
- **str,Enum 混入语义**——hash 穿透 `in frozenset` 判定，枚举入参守卫一律 `not isinstance(x, Enum) or ...` 双条件（5-4 R3-F01——本 Story 实体不变量②直接应用）
- **手动组装纪律**——resolve SCOPED/SINGLETON 钉住全局 Resolver 跨循环死连接；验收/集成一律场景级客户端手动组装；resolve 仅接线断言
- **委托计时模式**——模块级单槽缓存 helper + 同名 xdist_group 同 worker 缓存命中；验收/集成共享采样禁双跑
- **必填 vs 可选依赖的语义分界**——守卫可被绕过是安全缺口→必填（5-5）；降级不破坏主链→可选+容错（PersistentNoteTaker 先例）——本 Story 第五必填/第六可选（DC-6）
- **专项裁撤裁定**（v2.1.0 用户裁定）——「总是搞专项很不合适，应该放到集成测试或验收测试范畴。marker 非必要也不要新增」——本 Story 零新 marker、零新目录、零 CI 专项（pyproject/Makefile/ci.yaml 对本 Story 改动归零）
- **审计断言三段式**（isinstance→code→context）与计数断言（恰一次/零次）是变异可红的前提

**应用到本故事/Applied to This Story:**
- [ ] 构造点全仓 grep 登记修补（Task 3 循环 C）+ 5-4/5-5 存量全量回归
- [ ] 实体枚举双条件守卫（Task 1 不变量②）
- [ ] 手动组装 + 委托计时三先例（Task 4 + 验收）
- [ ] 零新 marker/目录/CI 专项（测试全部落位既有四目录 + 集成/验收范畴）
- [ ] 计数断言（no-op 零 save/443·447 零 save/恰一次联动）+ 三段式异常断言

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (glm-5.3) |
| **Version** | create-story workflow（bmad-create-story skill） |
| **Execution Date** | 2026-10-25 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（L1674-1713） |
| **架构文档** | `docs/architecture/architecture.md`（§5/§8.5/§9/§10.1） |
| **核心域设计** | `docs/architecture/sisys-core-domain-design.md`（§17.3.3 EIPExecutor 伪码） |
| **前一个 Story** | `5-5-agent-triple-hard-isolation.md`（v2.2.1 收敛态——范围边界 L35-36 移交） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] 故事需求从 `epics_v1.0.md` 提取（含范围边界表——与 5.7/V1/Epic 7 精确切分）
- [ ] 架构约束从 architecture.md/core-domain-design/or.md/prd.md 提取
- [ ] 前一个故事学习经验整合（5-5 教训链 + 移交留项三项处置 + 专项裁撤纪律）
- [ ] 五视角并行代码调研（隔离切换链路 / 审计日志体系 / 事件总线与 Outbox / 端口注册与异常编码 / 验收测试模板风格——关键事实独立验证：事件六字段/切换通道/实体守卫/session fallback/RLS/枚举）
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成（含 DC-1~DC-11 设计决策 + OD-1~OD-3 偏离声明 + 风险六项）
- [ ] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/5-6-isolation-switching-log.md`（本文件）

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/entities/isolation_switch_log.py` - 实体（frozen + from_event）
- `src/domain/ports/isolation_switch_log_repository.py` - 端口 + Query + Result
- `src/infrastructure/storage/postgresql/models/isolation_switch_log.py` - ORM 模型
- `src/infrastructure/storage/postgresql/repository/isolation_switch_log_repository.py` - PG 仓储（双模式）
- `deploy/postgresql/alembic/versions/015_isolation_switch_logs.py` - migration（表+RLS+FORCE）
- `tests/unit/domain/entities/test_isolation_switch_log.py` - 实体单测
- `tests/unit/infrastructure/storage/postgresql/test_isolation_switch_log_repository.py` - 仓储薄单测
- `tests/unit/architecture/test_arch_isolation_switch_log.py` - 架构验证
- `tests/contracts/test_port_contract_isolation_switch_log_repository.py` - 端口契约
- `tests/integration/test_integration_isolation_switch_log.py` - 集成（九场景+计时）
- `tests/acceptance/test_acceptance_isolation_switch_log.feature` - Gherkin（17+收尾）
- `tests/acceptance/test_acceptance_isolation_switch_log.py` - BDD 步骤

**待修改的文件/To Be Modified (Dev Story 实施):**
- `src/application/services/isolation_management_service.py`（五/六依赖 + audit-first 插位 + 联动）
- `src/application/ports/isolation_management.py`（docstring 契约更新）
- `src/domain/events/audit_events.py`（AuditActionType 第 8 组）
- `src/domain/entities/__init__.py` + `src/domain/ports/__init__.py`（导出——如 ports 有聚合导出文件）
- `src/infrastructure/storage/postgresql/models/__init__.py`（模型注册）
- `src/entrypoints/agent_cli.py`（isolation-logs 子命令 + 使用示例）
- `src/composition_root.py`（新端口注册 + lambda 扩展）
- 既有测试追加/同步：`test_isolation_management_service.py` / `test_audit_events.py` / `test_port_contract_isolation_management_service.py`（_DummyResolver）/ 既有 CLI 测试文件
- 回归面同步（Task 3 grep 清单为准）：`test_acceptance_agent_isolation.py` / `test_acceptance_agent_triple_isolation.py` / `test_acceptance_agent_workflow.py` / `test_integration_agent_isolation.py` / `test_integration_agent_triple_isolation.py` / `test_integration_isolation_security.py`
- `docs/architecture/architecture.md`（§5 注记 + §13 目录树）+ `deferred-work.md`（#7/R1-DF2 注记）+ `sprint-status.yaml`（5-6 状态流转）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 5.6 |
| **Story Key** | 5-6-isolation-switching-log |
| **File** | `_bmad-output/implementation-artifacts/stories/5-6-isolation-switching-log.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 5: Agent 协作系统（价值组：单 Agent 战略规划能力） |
| **优先级** | P1-6（epics 执行序；prd.md FR-AC-06 功能等级 P0——双锚不矛盾，见「偏离声明」节尾优先级双锚说明） |
| **覆盖 FR** | FR-AC-06（prd P0——`[or.md 一.2.(9)]`） |
| **性能锚** | epics L1695-1697（日志记录 P95<50ms@L1695 / 日志检索 P95<500ms@L1696 / 日志存储成功率 100%@L1697） |
| **覆盖率锚** | 应用层 ≥85%（domain ≥90 / infrastructure ≥75——四层门禁） |

### 完成总结 Completion Summary

1. [ ] All tasks defined 所有任务定义完成
2. [ ] All acceptance criteria specified 所有验收标准已定义
3. [ ] Architecture constraints extracted 架构约束已提取
4. [ ] Previous story learnings integrated 前一个故事学习经验已整合
5. [ ] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | OD-1 WORM gap 未进 deferred-work 台账、未链接 V1 承接方——V1 立项方经 deferred-work.md 追不到 WORM 裁剪；RLS 补偿控制与监管级 WORM 的差距（BYPASSRLS 绕过 / PG 备份导出不受 RLS 约束 / 无 7 年保留期限）未显式登记（来源：Epic 5 偏离声明同步动作对标审查 2026-10-25，业界 gap-management 四要素基准） | P2 | 偏离声明表 OD-1 行补承接方链接（Story 13-4 SOX）+ 补偿控制差距三注；Subtask 0.8 增加 deferred-work.md 登记动作 |
| 2 | OD-2/OD-3 同类缺口——偏离归宿仅文字描述「归 V1」，无 deferred-work 登记（承接 Story 可达性依赖读者偶然读到本文件） | P2 | Subtask 0.8 一并登记（OD-2 链接 9-4/9-5、OD-3 链接 9-3[FR-AC-09]） |
| 3 | 偏离声明编号 D-n 与代码审查留项 D# 撞名（5-1 实害先例：偏离声明 D-7「AgentService 回迁评估」被同号审查留项 D7 核销记录淹没而遗漏执行） | P3 | 本 Story 起偏离声明编号改 **OD-n**（Original-plan Deviation）前缀全量重命名；历史 Story（5-1~5-5）不动；编号规范写入项目记忆供后续 create-story 遵循 |

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** （待代码审查）
**审查模式:** （待定）

#### 需决策 Decision Needed

- [ ] （待登记）

#### 已修复 Patch

- [ ] （待登记）

#### 已推迟 Defer

- [ ] （待登记）

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
| 2026-10-25 | v1.0.0 | 创建故事文件（五视角并行调研：隔离切换链路 / 审计日志体系 / 事件总线与 Outbox / 端口注册与异常编码 / 验收测试模板风格；11 项关键架构决策 DC-1~DC-11 + 3 项偏离声明 OD-1~OD-3 + 风险六项；audit-first 同步内嵌写入链路[DC-2——reliable 事件不可订阅+消费基建归 5.7 论证]；独立 PG 表 + RLS(+FORCE) 防篡改 + CheckConstraint 双层[DC-4]；双模式 session 仓储[DC-5]；audit 联动可选降级[DC-6]；零新异常[DC-8]；CLI isolation-logs[DC-10]；5-5 移交三项处置[#7 注记/R1-DF2 注记/audit router 不触发]；范围边界与 5.7/V1/Epic 7 精确切分） |
| 2026-10-25 | v1.0.1 | **偏离声明同步动作对标审查修复**（Epic 5 全量 37 项审查之 5-6 面三项，见「文档审查修复」表）：①OD-1/OD-2/OD-3 补 deferred-work.md 登记动作（Subtask 0.8）+ 承接方链接（13-4 SOX / 9-4·9-5 / 9-3 FR-AC-09）+ OD-1 补 RLS 补偿控制差距三注（BYPASSRLS 绕过/备份导出不受约束/无保留期限——监管级 WORM 差距显式化）；②偏离声明编号 D-n→OD-n 全量重命名（与审查留项 D# 消歧——5-1 D-7 撞名实害先例；v1.0.0 行原文「D-1~D-3」随全量重命名同步为 OD 形态，历史指代关系由本行留痕）；③配套 architecture.md §13.2 agent_service.py 补 MVP 落位注记（5-1 D-7 回迁承诺闭环——审查问题②，非本 Story 文件内动作，此处登记联动关系） |
| 2026-10-25 | v1.0.2 | architecture.md §13.2 agent_service.py 注记增强（v1.0.1③ 的延续，用户指示）——「V1 再议下沉」升级为**可判定触发条件**：三信号同时满足方可立项评估（①跨两个以上聚合协作 / ②纯领域计算零 IO / ③领域语言中有独立概念名），缺一即维持现状；满足时首选 VO/纯函数归宿（isolation_access.py 判定矩阵先例），仅当多聚合状态输入且纯函数签名不可表达时才建领域服务；候选触发面 = Epic 9 多 Agent 协作（9-1/9-2/9-6） |

---

**故事版本/Story Version:** v1.0.2
**创建日期/Created:** 2026-10-25
**最后更新/Last Updated:** 2026-10-25
**更新说明/Description:**
- v1.0.0: 创建故事文件
- v1.0.1: 偏离声明同步动作对标审查修复（OD 登记/承接方链接/编号 OD-n 重命名）
- v1.0.2: agent_service.py 下沉触发条件可判定化（三信号 + VO 优先 + Epic 9 候选触发面）
