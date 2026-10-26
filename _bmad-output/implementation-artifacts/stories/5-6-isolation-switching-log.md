# Story 5.6: 隔离切换日志记录

**Status:** `review`

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

**范围权威**：epics_v1.0.md L1674-1713（AC + 测试要求 + 性能锚 L1695-1697）、L463（FR-AC-06 追踪）、L1442（依赖 5.4 + Story 1.10）；prd.md L1842（FR-AC-06 P0——`[or.md 一.2.(9)]`）；architecture.md §5（L652-653「`IsolationSwitchLog` 切换日志归 Story 5.6」）、§5.3（L693「所有隔离切换自动记录至 IsolationSwitchLog 并归档至 WORM 存储」）、§8.5（L814 IsolationLevelSwitched 24h 内 WORM 归档——**见偏离声明 OD-1**）、§9（L833 实体定义：id/agent_id/from_level/to_level/trigger/worm_ref，存储 L2+L4——**字段命名映射见 OD-4**）、§10.1（L862 事件通道）、arch-appendix.md L9753-9768（规划 DDL——**分歧处置见 OD-4**）；or.md 一.2.(9)（L30 实体七属性——**见 OD-2/OD-3 裁剪**）、一.2.[3].(8)（L48 事件 payload）、一.5.[6].(3)（L125 审计事件 WORM 归档）；sisys-core-domain-design.md §17.3.3（L1253-1261 EIPExecutor 伪码第 4 步 audit_log.save 先例）；5-5 故事范围边界表（L35-36「IsolationSwitchLog 切换日志、多维检索、WORM 归档 ❌ → 5.6」+「隔离切换审计记录（AuditService 调用）❌ → 5.6——**事件 payload 是 5.6 数据源契约**」）。

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
| CLI `set-isolation` `--approval-chain` 参数扩展 | ❌ 不做（既有 CLI 仅 --agent-id/--level/--reason 三参数；MVP 唯一触发通道是用户显式请求，空审批链是真实事实记录——六字段完整记录空集，非字段缺失） | V1 审批工作流（多级审批需求立项时随 CLI 参数与服务通道联动扩展） |
| 规划 DDL 差异项（tenant_id 列/trigger_type NOT NULL/单数表名/worm_storage_ref——arch-appendix L9753-9768） | ❌ 不做（OD-4——命名与列集对齐事件 payload SSOT + 同域 audit_log 先例；created_at **保留**非差异项——行创建审计列对齐 audit_log 先例，与 switch_timestamp 语义分工：切换时刻 vs 入库时刻） | V1 多租户/多通道立项时随迁移扩展（tenant_id 随多租户、trigger_type 随 OD-3 联动） |
| MinIO WORM 24h 归档管线（§8.5） | ❌ 不做（OD-1——DC-7） | V1 合规归档管线（与 1.10 WORMManager 未接线现状对齐） |
| 「切换后协作状态」独立字段（or.md 一.2.(9)） | ❌ 不做（OD-2——to_level 即协作状态语义） | V1 多 Agent 协作组 |
| trigger_type 枚举字段（SYS 命令/关键词频率/任务依赖/用户请求四类） | ❌ 不做（OD-3——MVP 仅用户请求单通道，事件无 type 字段） | V1（FR-AC-09 多通道时随事件 payload 扩展联动） |
| 隔离切换 REST API 查询端点 | ❌ 不做（MVP 检索交付面 = 端口 + CLI；audit router 未挂 create_app 是 1.10 既有形态） | Epic 7（7-2 REST API） |
| 事件订阅消费写日志（EventHandler 形态） | ❌ 不做（DC-2——audit-first 同步写；消费基建归 5.7） | 5.7 Phoenix（事件订阅基建面） |
| 动态触发（SYS 命令/关键词频率/任务依赖）与 30 分钟自动恢复 | ❌ 不做 | V1（FR-AC-09 P1） |

### 偏离声明（Deviation Declarations）

| # | 偏离 | 规划原文 | 偏离理由与归宿 |
|---|------|---------|---------------|
| OD-1 | MinIO WORM 24h 归档管线不在本 Story 实施；`worm_ref` 字段预留（nullable，默认 None） | architecture.md §8.5 L814（IsolationLevelSwitched 切换后 24 小时内归档 MinIO WORM 7 年）、§5.3 L693、or.md 一.5.[6].(3) L125 | epics AC（L1680-1692）未要求 WORM（字段完整+多维检索+持久化）；1.10 WORMManager 同为未接线现状（WORMManager 实例存在于组合根 L406-411，但 audit_service lambda 未注入 worm_manager → `AuditServiceImpl._worm_manager = None`，archive 的 WORM 路径不触发）；防篡改由 PG RLS deny UPDATE/DELETE 等效承载（DC-4）。归 V1 合规归档管线——**承接方 = Story 13-4（sox-compliance-404，V1）**；**补偿控制差距显式登记（四注）**：①RLS 可被 superuser/BYPASSRLS 属性绕过、②PG 备份/导出不受 RLS 约束、③无 7 年保留期限策略、④**TRUNCATE/DROP/REGRANT 不走 RLS**——业界标准做法是 DDL owner 与应用运行角色分离 + 应用角色仅 GRANT INSERT/SELECT（权限级撤销比 RLS deny 更硬），随 13-4 落地；另随 13-4 评估两项：gap-free 序列/链式防篡改（UUID4 主键无序不防间隙——SEC 17a-4 口径通常要求连续序列或 hash-chain，audit_log 单行 SHA-256 checksum 是非链式先例）与表分区（7 年保留 + 高追加量下按 switch_timestamp range 分区是归档管线前置设计约束——立项输入而非届时发现）——监管级 WORM（SEC 17a-4 / ISO 27001 口径）需 MinIO Object Lock COMPLIANCE 管线；**Task 0.8 随 deferred-work.md 登记**（gap 四要素：描述/触发条件/归宿/承接方链接） |
| OD-2 | 「切换后协作状态」不设独立字段 | or.md 一.2.(9) L30（七属性含切换后协作状态） | architecture.md §9 L833 实体定稿字段无此项——`target_level`（§9 名 to_level，命名映射见 OD-4）即协作状态语义（等级=协作模式映射，§5.1 四级表）；MVP 单 Agent 无协作态可记。V1 多 Agent 协作组立项时随需扩展——**承接方 = Story 9-4（联合分析组创建）/ 9-5（公共黑板中间结论交换）**；**Task 0.8 随 deferred-work.md 登记** |
| OD-3 | `trigger_type` 枚举字段不设（SYS 命令/关键词频率/任务依赖/用户请求四类触发源类型化） | or.md 一.2.(9) L30（触发原因括注四类）、core-domain-design §17.3.3 伪码 L1259（trigger_type） | MVP 唯一触发通道为用户显式请求（5-4 既定），`IsolationLevelSwitched` 事件仅 `trigger_reason` 自由文本无 type 字段——单通道下枚举仅一值（YAGNI）；architecture.md L833 定稿字段亦为单 `trigger` 字段。V1 FR-AC-09 多通道立项时随事件 payload 扩展联动（本 Story 实体加字段为非破坏演进）——**承接方 = Story 9-3（dynamic-isolation-level-adjustment，FR-AC-09）**；**Task 0.8 随 deferred-work.md 登记** |
| OD-4 | 实体字段命名与规划权威面映射：`previous_level/target_level/trigger_reason`（非 §9 的 from_level/to_level/trigger）+ 表名复数 `isolation_switch_logs`（非 arch-appendix DDL 单数 `isolation_switch_log`）+ 不落 `tenant_id` 列 + `worm_ref`（非 worm_storage_ref）；created_at **保留**（server_default NOW() 行创建审计列——对齐 audit_log 同域先例；与 switch_timestamp 语义分工：切换时刻 vs 入库时刻，非双时间戳冗余） | architecture.md §9 L833（from_level/to_level/trigger）、arch-appendix.md L9753-9768（规划 DDL：单数表名 + tenant_id NOT NULL + tenant 索引 + trigger_type VARCHAR(50) NOT NULL + 无 approval_chain 列 + worm_storage_ref） | 命名跟随**事件 payload 六字段 SSOT**（5-4 交付——本 Story 数据源契约，from_event 零加工映射）+ core-domain-design §17.3.3 伪码 L1254-1260 同名（previous_level/target_level/trigger_reason）——两套规划命名中事件契约与伪码一致且是活代码；表名复数对齐 5.x 新表惯例（sandbox_sessions/tool_executions/tool_chains）；tenant_id 对齐同域 audit_log 先例（无租户列——isolation/audit 域 Redis 键与表均无租户维度，document 域 tenant_id 是文档 Row-Level Isolation 特例）；approval_chain 是 FR-AC-06 六要素之一不可裁（arch-appendix DDL 漏列属规划缺陷）；trigger_type 归 OD-3。**触发条件 = V1 多租户立项（tenant_id）或多通道立项（trigger_type）时随 alembic 新迁移扩展**（已合入迁移禁改，加列走 ALTER）；**承接方 = 多租户专项（tenant_id，随 13-x 合规管线族评估）+ Story 9-3（trigger_type，OD-3 联动）**；**Task 0.8 随 deferred-work.md 登记** |

> 优先级双锚说明（非偏离）：prd.md L1842 将 FR-AC-06 定级 P0（功能等级），epics_v1.0.md L1442 执行优先级 P1-6（执行序——依赖 5.4/5.5 完成后执行）。两者不矛盾：功能等级遵 prd，执行序遵 epics。

---

## 🔗 前置依赖（全部 ✅ 已完成，无阻塞）

| 依赖 | 组件 | 用途 | 状态 |
|------|------|------|------|
| Story 5.4 | `IsolationLevelSwitched` 事件（domain/events/isolation_events.py L17-50——六字段 payload：agent_id/previous_level/target_level/trigger_reason/approval_chain/switch_timestamp，**本 Story 唯一数据源契约，零改动**）+ `IsolationManagementService.switch_isolation_level`（application/services/isolation_management_service.py L112-177——守卫序 443→447→446 + no-op 零副作用 + approval_chain 显式转发 L153）+ `IsolationManagementServicePort`（application/ports/isolation_management.py L52-130——L100-130 是其中 switch_isolation_level 方法签名区间）+ `IsolationSwitchResult` DTO（L37-49）+ `RedisIsolationRepository`（键空间 `sisys:isolation:{agent_id}`）+ CLI set-isolation/isolation-status（entrypoints/agent_cli.py）+ 组合根注册（composition_root.py L2883-2903） | 切换通道与事件 payload（from_event 映射源） | ✅ done |
| Epic 1 Story 1.10 | `AuditServicePort.record`（domain/ports/audit_service.py L52-60——actor/action_type/target_resource/old_value/new_value/correlation_id）+ `AuditServiceImpl`（infrastructure/security/audit_service_impl.py L23/L49-127——同步 await，失败包装 AuditError）+ `AuditRepository`（infrastructure/security/audit_repository_impl.py——ContextVar session + save(dict) + search(AuditSearchCriteria) 多维检索先例 L96-149）+ `audit_log` PG 表（RLS deny UPDATE/DELETE——002_audit_tables L103-143）+ `AuditActionType` 枚举（domain/events/audit_events.py L31-72）+ 组合根 audit_repo/audit_service 注册（composition_root.py L483-503）+ `resolve_optional` 可选注入先例（composition_root.py L2201——PersistentNoteTaker 降级模式） | 审计联动通道 + 检索/表/RLS 三大照抄模板 | ✅ done |
| Story 5.1 | `Agent` 实体 + `AgentRepository` + `RedisAgentRepository`（键 `sisys:agent:{agent_id}`）+ `InstantiateAgentUseCase`（本 Story 测试用它构造真实 Agent） | 测试 Agent 构造链 | ✅ done |
| 异常体系 | `AgentNotFoundError`(443)/`IsolationStateNotInitializedError`(447)/`IsolationLevelNotSupportedError`(446)/`EntityValidationError`(242)/`StorageError`(103)/`AuditError`(105) 全部复用（DC-8——零新异常；agent 段 440-449 已满，无需开新段） | 守卫/校验/存储失败透传 | ✅ 就绪 |
| Outbox session fallback 先例 | `PostgreSQLOutboxRepository`（infrastructure/messaging/outbox/outbox_repository.py L71-97——请求 session 优先 + `session_factory` fallback 独立会话写入，Story 4-7 修复）+ `session_context()`（infrastructure/storage/postgresql/session_context.py——R3 后台任务独立 scope 规则） | PG 仓储双模式 session 照抄模板（CLI 上下文可写） | ✅ 就绪 |
| 测试基建 | `tests/environments.py` get_test_env()（测试端口 Redis 6380 / PG 5433）/ `tests/integration/conftest.py` real_redis(L193-220) + real_postgres_engine(L254-286) + 事务隔离组 L453-536：pg_config → ensure_alembic_migration(L470-519) → **pg_session(L522-536——begin+rollback 事务隔离)**——注意与 L289-293 的裸 `postgres_session`（无隔离）是两个不同 fixture 勿混用 / `tests/acceptance/conftest.py` acceptance_env_config(L99-106) + 文件名服务 marker 自动挂载(L110-140) | 集成/验收双服务门控与隔离基建 | ✅ 就绪 |

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
| `switch_isolation_level` 切换通道（守卫序/no-op/TTL 重置/事件发布容错——5-4 DC-10） | `src/application/services/isolation_management_service.py` L112-177 | **扩展**——第五/六依赖注入 + audit-first 日志写入插位（L141 no-op return 之后、L146 Redis save 之前）。⚠️ **既有事件构造块（现 L148-155，位于 Redis save 之后）须随插位整体上移至 Redis save 之前**——from_event 消费该事件对象；数据流安全（六字段输入在 no-op 检查后全部就绪，与 Redis save 无依赖）；上移后顺序 = no-op → 构造事件 → from_event → config load（只读）→ log save → Redis save → publish → audit 联动（方法尾部；只读前置最小化误报窗口） |
| `IsolationManagementServicePort` / `IsolationSwitchResult` | `src/application/ports/isolation_management.py` | **扩展**——docstring 更新（ Raises/审计语义）；IsolationSwitchResult **不扩展**（log 不进返回值——调用方经检索面自查，YAGNI） |
| `AuditServicePort.record` + `AuditServiceImpl` | `src/domain/ports/audit_service.py` L52-60 + `src/infrastructure/security/audit_service_impl.py` | **直接复用**——联动审计通道（组合根 resolve_optional 注入先例 L2201） |
| `AuditActionType` 枚举 | `src/domain/events/audit_events.py` L31-72 | **扩展**——追加 isolation 组 `ISOLATION_SWITCH = "isolation:switch"`（第 8 组，DC-9） |
| `AuditSearchCriteria` / `AuditSearchResult` / search 实现 | `src/domain/ports/audit_repository.py` L15-54 + `src/infrastructure/security/audit_repository_impl.py` L96-149 | **参考照抄**——Query Object 字段形态（offset/limit 分页）与动态条件构建 + count + timestamp desc 排序。⚠️ **防呆：勿照抄 match_any 的 or_ 语义**——其 count 分支（L128-130）恒用 and_ 与 or_ 检索不一致（1.10 已知缺陷）；本 Story 检索是纯 AND 组合（AC-3），Query 不设 match_any 字段 |
| audit_log RLS 策略四件套（INSERT/SELECT 放行 + deny UPDATE/DELETE） | `deploy/postgresql/alembic/versions/002_audit_tables.py` L103-143 | **参考照抄**——015 migration RLS 段（注意 DELETE policy 仅 USING 子句——002 已修正的 PG 语法约束）+ **追加 FORCE ROW LEVEL SECURITY**（DC-4——owner 连接不绕过） |
| outbox 双模式 session（请求 ContextVar 优先 + session_factory fallback） | `src/infrastructure/messaging/outbox/outbox_repository.py` L71-97 + `session_context()` | **参考照抄**——PG 仓储 save 的双路径（CLI/后台上下文可写——Story 4-7 修复先例） |
| `PostgreSQLAdapter` 泛型基类 / ContextVar `_session` property | `src/infrastructure/storage/postgresql/repository/postgresql_adapter.py` L24（class）/ L46-64（`_session` property） | **参考照抄**——ORM 模型注册（`models/__init__.py`）与仓储类形态（本仓储有 search 定制查询，不必继承泛型基类——audit_repository_impl 直实现 Port 先例同款，双模式 session 是差异点）。⚠️ **防呆：该基类 `_session` property 会把 RuntimeError 包成 InvalidStateError（L60-64 `from None`）——双模式 fallback 分派必须直调 `session_context.get_session()` 并 catch RuntimeError（outbox L80 形态），经 property 则 except RuntimeError 永不命中** |
| `PortSpec` 注册 + `# === Story 5.x ===` 区段 + `__import__` 延迟导入 + lambda 工厂 | `src/composition_root.py` L2678-2931（5.x 区，isolation_management_service L2883-2903 原文） | **参考照抄**——新端口注册追加至该区段 + 既有 lambda 扩展两依赖 |
| 端口契约测试 11 维度 + `_DummyResolver` | `tests/contracts/test_port_contract_isolation_management_service.py`（137 行全文） | **参考照抄**——同款结构（PORT_NAME/EXPECTED_TAGS/REQUIRED_METHODS 类常量 + 11 维度函数 + Dummy 分发） |
| 集成 `_assemble_real_chain()` 手动组装 + `_PERF_CACHE` 委托计时 + `xdist_group` 同 worker 缓存 | `tests/integration/test_integration_agent_isolation.py` L39-55/L83-123 | **参考照抄**——真实链组装扩展 log 仓储/audit + 新计时组 |
| 验收测试骨架（PG 模板 R6 基准 + 5-4/5-5 Redis 改造形态） | `tests/acceptance/test_acceptance_agent_isolation.py`（5-4，1267 行）/ `test_acceptance_agent_triple_isolation.py`（5-5，1401 行） | **参考照抄**——R6 主体基准（@scenario 多行字面量显式绑定 + context dict fixture + `_run_async` 同循环 + 步骤化门控 skip + 收尾清单场景 + 延迟 import）；PG 模板取 ensure_alembic_migration fixture 形态（test_acceptance_postgresql_relational_layer.py L148-204）；禁 then-pass 占位（PG 模板历史缺陷） |
| `build_key(namespace, *parts)` | `src/infrastructure/storage/redis/key_builder.py` L11-22 | **直接复用**——验收/集成 Redis 双键清理 |
| `_RecordingEventPublisher` 手写替身形态 | `tests/acceptance/test_acceptance_agent_isolation.py` L80-97 | **参考照抄**——同构副本（仓内无共享定义，各文件手写是惯例） |
| 实体形态先例（frozen 日志型 + create 工厂 + `__post_init__` 242 + to_dict） | `src/domain/entities/audit_log.py` L18-142 + `isolation_state.py` L57-176（枚举双条件守卫 R3-F01） | **参考照抄**——IsolationSwitchLog 实体骨架 |

**明确不存在、本 Story 需新建**（全仓 grep 验证：`IsolationSwitchLog|isolation_switch_log|switch_log` 在 `src/` 与 `tests/` **零命中**——防重复造轮子结论成立；docs 规划性出现面：interface-design.md L1377、architecture.md §5/§5.3/§9/L2519、arch-appendix.md L82/L1322/L4927/L9753-9768（规划 DDL）/L10044、sisys-core-domain-design.md §17.3.3 伪码——均为规划文本非代码；`隔离切换与审计零集成`——isolation_management_service.py 全文无 audit 引用）：

1. `IsolationSwitchLog` 实体 + `from_event` 工厂（domain/entities/isolation_switch_log.py）
2. `IsolationSwitchLogQuery` + `IsolationSwitchLogSearchResult` + `IsolationSwitchLogRepository` 端口（domain/ports/isolation_switch_log_repository.py）
3. `IsolationSwitchLogModel` ORM（infrastructure/storage/postgresql/models/isolation_switch_log.py）+ `models/__init__.py` 注册
4. alembic migration `015_isolation_switch_logs`（表 + 5 索引 + CheckConstraint + RLS 四策略 + FORCE）
5. `PostgreSQLIsolationSwitchLogRepository` 仓储实现（双模式 session，infrastructure/storage/postgresql/repository/isolation_switch_log_repository.py）
6. `IsolationManagementService` 第五依赖 `isolation_switch_log_repository`（必填）+ 第六依赖 `audit_service`（可选）+ audit-first 写入 + audit 联动
7. `AuditActionType.ISOLATION_SWITCH` 枚举项
8. CLI `isolation-logs` 子命令（entrypoints/agent_cli.py）
9. 组合根 `isolation_switch_log_repository` 注册 + isolation_management_service lambda 扩展
10. 测试七件（6 新建 + 1 存量追加；另有 `test_audit_events.py` 与既有 CLI 测试文件 `tests/unit/interfaces/cli/test_agent_cli.py` 两处存量追加，见「测试分类与归属」表）：`tests/unit/domain/entities/test_isolation_switch_log.py` / `tests/unit/application/services/test_isolation_management_service.py`（追加）+ 存量构造点同步 / `tests/unit/infrastructure/storage/postgresql/test_isolation_switch_log_repository.py`（薄单测——mock session 逻辑面） / `tests/contracts/test_port_contract_isolation_switch_log_repository.py` / `tests/integration/test_integration_isolation_switch_log.py` / `tests/unit/architecture/test_arch_isolation_switch_log.py` / `tests/acceptance/test_acceptance_isolation_switch_log.{feature,py}`

---

## ✅ Acceptance Criteria 验收标准

### AC-1: IsolationSwitchLog 领域实体与事件映射

**Given** `IsolationLevelSwitched` 事件已定义（5-4 交付，六字段 payload）
**When** 以真实切换事件调用 `IsolationSwitchLog.from_event(event)`
**Then** 产出 frozen 实体，六字段逐项映射完整：`agent_id`（AGENT ID）、`switch_timestamp`（时间戳——**取事件 `switch_timestamp` 而非 event.timestamp**，单钟纪律：事件时刻=状态变更时刻）、`previous_level`（原隔离等级）、`target_level`（目标隔离等级）、`trigger_reason`（触发原因）、`approval_chain`（审批链——**tuple[str, ...] 不可变形态**，事件 list 拷贝冻结）；`log_id` 随机自铸 UUID4；`worm_ref` 默认 None（预留 OD-1）
**And** 实体不变量（`__post_init__` 抛 `EntityValidationError` 242，五场景见「数据模型」节唯一真源；242 context 形态 = `{字段名: 实际值/类型}`——对齐 isolation_state 先例，逐字段名稳定可断言）：agent_id/log_id 非 UUID 实例拒；previous_level/target_level 非 `IsolationLevel` 枚举实例拒（**双条件守卫**——str,Enum 混入语义 hash 穿透，5-4 R3-F01 实测定谳，isinstance 先行）；`previous_level == target_level` 拒（**切换语义不变量**——no-op 不得产生日志，与 CheckConstraint D-4 双层防线）；trigger_reason 空/空白拒；approval_chain 非 tuple 拒 + 元素非 str 或空白串拒；`to_dict()` 全字段可序列化（UUID→str / Enum→value / datetime→ISO 8601 / tuple→list）。注：log_id/approval_chain 两场景的非法值经 **dataclass 直构造注入**（from_event 自铸合法值无法产出非法输入——测试专用通道，生产构造通道唯一性[DC-1]不受影响）

**验证标准/Validation Criteria:**
- [ ] from_event 六字段逐项断言（构造事件 → 映射 → 逐字段相等；approval_chain list→tuple 类型断言）
- [ ] 不变量五场景独立用例（非空/类型/相等枚举逐项）；242 三段式断言（isinstance→code→context）
- [ ] to_dict roundtrip（键集完整 + 类型形态断言）
- [ ] frozen 断言（`dataclasses.FrozenInstanceError` 赋值拒绝——日志不可变性）
- [ ] 纯 domain 零外部依赖（AST 扫描归 AC-6.3 架构验证器）

### AC-2: 切换链 audit-first 日志写入

**Given** 真实 Agent（真实 Redis 构造，默认 L4）+ 真实 PG（isolation_switch_logs 表已迁移）
**When** 调用 `switch_isolation_level(agent_id, target_level, trigger_reason, approval_chain)`（set-isolation 等价服务链）
**Then** **audit-first 顺序**（DC-2）：443→447→446 守卫 → no-op 检查（同等级 **零日志**——`log_repository.save` 零调用）→ 构造事件 → `IsolationSwitchLog.from_event` → config load（既有只读——TTL 真源）→ **`log_repository.save(log)`（失败上抛 = 切换被拒——无审计痕迹的切换不允许发生）** → Redis 状态写（既有）→ 事件发布（既有 5-4 DC-10 容错）→ `audit_service.record` 联动（**可选依赖 + 失败降级** `logger.warning` 不回滚——DC-6，PersistentNoteTaker 先例）
**And** 日志落库六字段与 PG 行逐项一致（检索面取回断言）；审批链非空时（`approval_chain=("合规负责人",)`）完整持久化 JSONB；**日志写失败路径**（注入坏连接仓储实例 → StorageError 上抛 → 切换被拒：Redis `current_level` 未变、零事件发布——fail-closed 审计语义）；audit 联动记录写入 `audit_log` 表（actor=`agent:{agent_id}`、action_type=`isolation:switch`、old_value=`{"level": previous_level.value}`——**.value 字符串形态（JSONB 序列化，传枚举对象会触发降级静默丢失）**、new_value 含 level/reason/approval_chain、correlation_id=str(event.event_id)）

**验证标准/Validation Criteria:**
- [ ] 真实链切换 → PG 检索取回 → 六字段逐项断言（含 approval_chain JSONB roundtrip）
- [ ] no-op 零日志：同等级二次调用 → `search(agent_id=...)` total 不变 + save 零调用计数断言（AsyncMock calls——单测面）
- [ ] audit-first 顺序断言：坏仓储（真实 `PostgreSQLIsolationSwitchLogRepository` 注入指向不可达端口的 session_factory——真实类真实代码仅环境参数坏，非 mock，合规）→ `pytest.raises(StorageError)` + Redis get 回等级未变 + `_RecordingEventPublisher` 零事件。⚠️ **构造前提：本场景不设 ContextVar session（禁 set_session）**——双模式是 get_session 优先，若设了测试 session 会命中好 session 永不触发 StorageError（僵尸场景）；不设则 get_session 抛 RuntimeError → 走坏 factory → 连接失败；坏端点用 `127.0.0.1:1` 类保留端口（connection refused 立即失败，禁不可路由 IP 拖 connect_timeout）
- [ ] audit 联动：真实 audit_service（PG 可用）→ audit_log 表检索 **（测试 session 直查 audit_log 表，action_type + correlation_id 双过滤 SQL——AuditSearchCriteria 无 correlation_id 字段，走 audit_repo.search 需客户端按 items[].correlation_id 匹配，直查表更直接）**action_type=`isolation:switch` 一条 + correlation_id 匹配；降级：audit_service 抛 AuditError（单测 AsyncMock side_effect）→ 切换仍成功 + logger.warning（caplog 断言）
- [ ] 守卫序零回归：443（随机 UUID）/447（删隔离键）路径 **零日志写入**（守卫先于日志位——443/447 拒绝时 save 零调用）

### AC-3: 多维检索

**Given** isolation_switch_logs 表含多 Agent 多条切换日志（测试自造：≥3 Agent × ≥2 条/Agent，等级覆盖 L4→L3 与 L4→L2 两方向）
**When** 以 `IsolationSwitchLogQuery` 各维度组合调用 `search(query)`
**Then** **按 AGENT**：`agent_id=X` → 仅 X 的日志；**按时间**：`start_time`/`end_time` 闭区间过滤（`switch_timestamp >= start` 且 `<= end`）；**按隔离等级**：`level=L3` → **命中语义 = previous_level 或 target_level 任一等于 L3**（DC-3——or.md「按隔离等级检索」语义，切换涉及该等级即命中）；**组合**：多条件 AND；**分页**：`offset`/`limit`（默认 50）+ `total` 独立计数（**非 items 长度——分页语义**）；**排序**：`switch_timestamp` 降序（最新在前）
**And** `IsolationSwitchLogSearchResult`：`items: tuple[IsolationSwitchLog, ...]`（强类型实体非 dict）+ `total: int` + `offset` + `limit`；Query Object frozen（`@dataclass(frozen=True)` 端口文件内定义——多字段组合+分页，Query Object 决策规则命中）；查询条件全空 → 全量分页返回（合法调用）

**验证标准/Validation Criteria:**
- [ ] 四维独立场景 + 组合场景（agent_id + 时间范围 + level 三条件 AND）各独立用例
- [ ] level 命中双向断言：L4→L3 切换在 `level=L3`（target 命中）与 `level=L4`（previous 命中）均返回
- [ ] 分页断言：**独立造数**（单 Agent 5 条——分页场景不共用 AC-3 Given 的 ≥3 Agent×≥2 条统一造数，否则 total=6 全翻车）→ limit=2 offset=0 → items 2 条 + total=5；offset=4 → 1 条；offset==total（空页边界）→ 0 条 + total=5
- [ ] 排序断言：最新 switch_timestamp 在 items[0]（四维独立用例归集成场景⑤，验收 3 场景为抽样面——组合/双向/分页排序）
- [ ] 检索不要求 Agent 现存（Agent TTL 过期后历史日志仍可查——审计要求；**无 443 守卫**，与切换写入面守卫形成对照——单测锁定）

### AC-4: 持久化与不可篡改（合规防篡改底座）

**Given** isolation_switch_logs 表经 alembic 015 创建（含 RLS）
**When** 验证表结构与防篡改约束
**Then** **表结构**：`log_id` UUID PK + `agent_id` UUID + `previous_level`/`target_level` String(20) + `trigger_reason` Text + `approval_chain` JSONB + `switch_timestamp` DateTime(tz) + `worm_ref` String(500) nullable + `created_at` DateTime(tz) server_default NOW()；**索引五**：agent_id / switch_timestamp / previous_level / target_level / (agent_id, switch_timestamp) 组合——previous_level 单列与 target_level 对称（level 双向命中 or_ 两臂皆可索引化——PG BitmapOr 可达，生产单维 level 检索 P95<500ms 的结构性前提；单侧索引会使该维度退化为全表扫描）；**CheckConstraint** `previous_level != target_level`（DB 层拒绝 no-op 日志——实体不变量 DB 投影）；**RLS 四策略**：INSERT/SELECT 放行（WITH CHECK true / USING true）+ deny UPDATE + deny DELETE（USING false——002 模式照抄，DELETE policy 仅 USING 子句）；**FORCE ROW LEVEL SECURITY**（DC-4——owner 连接不绕过）
**And** 篡改拒绝实证：非绕过连接（前置探测 **`rolsuper OR rolbypassrls`** + 表 owner 关系——superuser 无论 FORCE 与 rolbypassrls 标志都绕过 RLS，三者任一即绕过环境 `pytest.skip` 动态跳过并注明；⚠️ 本地/CI 默认 `postgres` superuser 连接下本场景恒 skip——绿色路径依赖非 superuser 应用角色环境，skip 分支本身 + 变异实证是 MVP 实证面）下 `UPDATE ... SET target_level=...` 与 `DELETE` 均影响 0 行；CheckConstraint 实证：直插 previous==target 行 → `IntegrityError`

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
**And** 计时委托集成模块 helper（`_PERF_CACHE` 单槽缓存 + `xdist_group("isolation-switch-log-perf")` 同 worker 串行——5-4 委托模式照抄，禁 20 采样双跑）；本地 PG 写 ~3ms + Redis 写 ~4ms（hset+expire 经 MULTI/EXEC 一 RTT——「Redis 两写」实指此两命令）全链 ~7ms，P95 预算 50ms 约 **7 倍裕量**；⚠️ 计时口径注记：集成链按隔离纪律走 set_session → save=add+flush **不含 commit**，生产 CLI 真实形态是 fallback 独立 commit（多一次 RTT）——测得 P95 略优于真实 CLI 路径，docstring 如实注明

**验证标准/Validation Criteria:**
- [ ] 写 P95：常量单源（集成定义/验收 import）+ 委托缓存命中（验收 AC-5.1 不自跑采样）
- [ ] 检索 P95：同款（AC-5.2）
- [ ] 成功率：20 切换 → 20 日志（20/20 分子分母断言；含审批链非空场景混合）
- [ ] 计时场景 benchmark 场景级标记 + xdist_group 同组（与 5-4 agent-isolation-perf / 5-5 agent-triple-isolation-perf 组名互异不冲突）

### AC-6: 端口接线、CLI、架构合规与回归

**Given** 实体、仓储、接线、CLI 全部交付
**When** 验证接线与合规
**Then** 新端口 `isolation_switch_log_repository`（**SINGLETON——5-4 DC-7 新增面政策：新端口从源头避免被 SINGLETON isolation_management_service 捕获形成新 captive；同域先例 isolation_repository L2874 亦 SINGLETON；仓储无状态（session 每调用 ContextVar/fallback 现取），SINGLETON 无共享态风险**）经组合根注册且 resolve 可达（PortSpec 全参数：v1.0.0 / `IsolationSwitchLogRepository` / lambda 注入 session_factory / module / owner=platform / tags=("agent","isolation","audit")）；`IsolationManagementService` lambda 扩展第五依赖 `resolver.resolve("isolation_switch_log_repository")` + 第六依赖 `resolver.resolve_optional("audit_service")`（接线完整）；CLI `isolation-logs` 子命令（--agent-id/--level/--start/--end/--limit/--offset，Typer argparse 形态对齐 set-isolation 先例——agent_cli 用 argparse subparsers）输出多行摘要；domain 零外部依赖（isolation_switch_log.py AST 扫描——仅标准库 + 同层 events/exceptions import）；组合根外零实例化（PostgreSQLIsolationSwitchLogRepository 仅组合根与测试文件）；`AuditActionType.ISOLATION_SWITCH` 值 `"isolation:switch"` 注册
**And** 5-4/5-5 回归面零破坏：`IsolationManagementService` 构造签名扩展（四依赖 → 六依赖）的**全仓构造点全量同步**（实测基准 **14 处 = src 1 + tests 13**：组合根 lambda（composition_root L2893）/ 单测工厂（test_isolation_management_service L155）/ 集成三链（test_integration_agent_isolation L105 / triple L102 / isolation_security L337）/ 验收 8 处五文件（test_acceptance_agent_isolation L172·L491·L908 / triple L212 / workflow L284·L1182 / **agent_instantiation L219 / agent_profile_loading L233——易漏**）/ 契约一处（**test_port_contract_agent_instantiation_use_case L60——该契约测试构造真实服务作依赖，非 isolation_management 契约本身**）；isolation_management 契约测试的 _DummyResolver 是依赖分发需补两分发但不构造服务——Task 3 全仓 grep 登记苦役先例，实施时以 grep 实际清单为准）；5-4 验收（`test_acceptance_agent_isolation`）+ 5-5 验收/探针（`test_acceptance_agent_triple_isolation` / `test_integration_isolation_security`）全量回归绿

**验证标准/Validation Criteria:**
- [ ] 组合根注册 + resolve + isinstance + lifetime==SINGLETON 断言（5-4 AC-6.1 同款）
- [ ] lambda 五/六依赖注入确认——**接线内省锚**（resolve isolation_management_service 后内省服务实例的第五/六依赖属性 isinstance 对应端口类型——lambda 漏注入即红；**禁发真实命令**——与手动组装纪律互斥的「resolve→真实切换」形态已被废除，「真实切换→可检索」端到端语义由 AC-2.1 手动组装链覆盖）
- [ ] CLI isolation-logs 真实链（真实切换造数 → **set_session(test_session) 作用域内 in-process 调 main()**——CLI 代码不触碰 ContextVar，repo 的 get_session 命中测试 session，全链走请求路径 → teardown rollback 零残留（自包含纪律）；fallback 形态由单测 mock factory + 组合根 lambda 断言覆盖 → CLI 检索 stdout 含等级/原因行——argparse 测试形态对齐 5-4 CLI 测试先例 `tests/unit/interfaces/cli/test_agent_cli.py`）
- [ ] 架构验证器：domain 零外部依赖 + 组合根外零实例化 + 端口方向（interfaces→domain 合法——CLI 直消费仓储端口）
- [ ] 回归面清单全量同步登记（构造点 grep 全量 + 逐一修补 + 5-4/5-5 存量测试全绿）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [x] **不新建领域事件、不修改既有事件**——`IsolationLevelSwitched`（5-4 交付）是唯一数据源契约，六字段 payload 已覆盖 FR-AC-06 全部要求，零改动零登记。本 Story 新增的是**事件消费投影**（from_event 工厂——AC-1），不是事件。`event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` 零改动（事件未变，双登记现状保持——`sisys.events.reliable.isolation_level_switched` reliable 单通道）。`AuditEvent` 复用不新建（联动时由 AuditServiceImpl 构造）。

#### 数据模型 (Data Models)

- [x] `IsolationSwitchLog`（`src/domain/entities/isolation_switch_log.py`，`@dataclass(frozen=True)`——追加型日志事实，AuditLog 先例 L18-37）：
  - 字段：`log_id: uuid.UUID`（自铸 UUID4）/ `agent_id: uuid.UUID` / `previous_level: IsolationLevel` / `target_level: IsolationLevel` / `trigger_reason: str` / `approval_chain: tuple[str, ...]` / `switch_timestamp: datetime` / `worm_ref: str | None = None`（预留——OD-1）
  - `@classmethod from_event(cls, event: IsolationLevelSwitched) -> IsolationSwitchLog`——六字段映射工厂（approval_chain `tuple(event.approval_chain)` 冻结拷贝；switch_timestamp 取 `event.switch_timestamp`；log_id `uuid.uuid4()`）
  - `__post_init__` 不变量（失败抛 `EntityValidationError` 242，context 携带字段名与实际类型）：①agent_id/log_id 非 UUID 实例拒；②previous_level/target_level 非 `IsolationLevel` 枚举实例拒（**双条件 isinstance 先行**——5-4 R3-F01 str,Enum hash 混入穿透教训）；③`previous_level == target_level` 拒（切换语义——no-op 不产生日志）；④trigger_reason 非 str 或空白拒；⑤approval_chain 非 tuple 拒 + 元素非 str/空白串拒
  - `to_dict() -> dict[str, Any]`——UUID→str / Enum→value / datetime→`isoformat()` / tuple→list（对齐 audit_log.to_dict 序列化惯例）
- [x] `IsolationSwitchLogQuery`（端口文件内 frozen dataclass——Query Object 决策规则：多字段组合+分页命中）：`agent_id: uuid.UUID | None = None` / `start_time: datetime | None = None` / `end_time: datetime | None = None` / `level: IsolationLevel | None = None`（命中语义 = previous 或 target 任一）/ `offset: int = 0` / `limit: int = 50`；`__post_init__` 守卫：offset<0 / limit<=0 / limit>500 拒（242）
- [x] `IsolationSwitchLogSearchResult`（端口文件内 frozen）：`items: tuple[IsolationSwitchLog, ...]` / `total: int` / `offset: int` / `limit: int`
- [x] PG 表 `isolation_switch_logs`（列/索引/约束见 AC-4——ORM 模型 `IsolationSwitchLogModel` + migration 015 双向一致；**ORM→实体映射丢弃 created_at 列**——实体八字段无 created_at（行创建审计列仅 DB 侧 server_default，检索投影构造实体不传该列即可，非错误；AuditLog 实体含 created_at 是 1.10 形态，本 Story 实体单钟以 switch_timestamp 为时间真源）

#### 统一端口定义注册与管理 (Port Contract)

- [x] `IsolationSwitchLogRepository`（`src/domain/ports/isolation_switch_log_repository.py`，`@runtime_checkable Protocol`——**R1 领域层基础端口**：日志持久化与检索是领域基础能力，同层先例 IsolationRepository/AgentRepository）两方法（**两方法均双模式 session 分派**——请求 ContextVar 优先 + session_factory fallback，DC-5；CLI 检索场景 search 也必须走 fallback 才可达）：
  - `async def save(self, log: IsolationSwitchLog) -> None`——追加写入（日志只增不改——RLS 保证）。Raises 契约：`StorageError`（EXCEPTION_103——PG 连接/写入故障）。⚠️ **异常包装是实现必做项**：outbox/audit 仓储均**不包装**（SQLAlchemy 原生异常透传——照抄模板不带包装），本仓储须自建 `except SQLAlchemyError as exc: raise StorageError(...) from exc` 包装链（redis_isolation_repository L94 `raise StorageError(cause=exc) from exc` 先例的 PG 版）——否则坏连接实际抛 `sqlalchemy.exc.OperationalError`（与 StorageError 无继承关系），AC-2.3 与集成场景③ 的 `pytest.raises(StorageError)` 必红且红错位至 Task 4（仓储薄单测绿、验收红——最难 debug 形态）
  - `async def search(self, query: IsolationSwitchLogQuery) -> IsolationSwitchLogSearchResult`——多维检索。Raises 契约：`StorageError`（同款包装链）
- [x] `IsolationManagementService` 构造签名扩展（**R2 应用层具体应用端口组合注入 R1 基础端口**——5-4 四依赖先例延伸）：
  - 第五依赖 `isolation_switch_log_repository: IsolationSwitchLogRepository`（**必填——弃 None 容忍**：审计日志可被静默跳过是合规缺口，5-5 守卫必填先例同哲学；回归面全量同步一次到位；私有属性名 = `self._isolation_switch_log_repository`——`_` + 参数名，对齐既有四属性惯例 L71-74，接线内省锚断言该属性）
  - 第六依赖 `audit_service: AuditServicePort | None = None`（**可选**——联动审计是增值索引非 SSOT；resolve_optional + 失败降级，DC-6；私有属性名 = `self._audit_service`——与第五依赖对称钉死，接线内省锚断言该属性）
- [x] 组合根注册元数据：`isolation_switch_log_repository`：v1.0.0 / `IsolationSwitchLogRepository` / `PostgreSQLIsolationSwitchLogRepository`（lambda 注入 `session_factory=resolver.resolve("session_factory")`——组合根实际端口名已定谳为 **`session_factory`**（composition_root L232 注册，outbox lambda L621 同款消费；全仓无 `pg_session_factory` 端口））/ module=src.infrastructure.storage.postgresql.repository.isolation_switch_log_repository / **SINGLETON**（DC-11——5-4 DC-7 新增面政策 + 同域 isolation_repository L2874 先例）/ owner=platform / tags=("agent", "isolation", "audit")
- [x] **既有端口消费方变更（契约变更登记 ×1）**：`isolation_management_service` lambda 扩展两依赖（契约测试 impl 维度与组合根同步——`test_port_contract_isolation_management_service.py` _DummyResolver 补两分发 **+ 补 `resolve_optional` 方法**：lambda 将调用 `resolver.resolve_optional("audit_service")` 而 Dummy 现仅定义 `resolve`——不补则维度 9b/10/11 的 `spec.impl(_DummyResolver())` 必 AttributeError；带 resolve_optional 的 Dummy 先例 = test_port_contract_debate_session_repository.py L31）
- [x] 端口契约测试一份（`tests/contracts/test_port_contract_isolation_switch_log_repository.py`，11 维度 + `_DummyResolver`）
- [x] **禁止**在服务文件本地定义 Protocol/Port 抽象；**禁止**新建语义重复端口（审计联动复用 audit_service——禁新建 isolation_audit_service；通用审计检索复用 1.10 audit search——本端口是隔离域专属日志非通用审计）

#### 端口契约清单执行约束（强制）

- [x] 本 Story 端口清单唯一真源 = 本 Task 0 定义（`isolation_switch_log_repository` 一新端口 + 一项既有端口消费方变更：IsolationManagementService 构造签名扩展——契约变更登记）
- [x] 禁止新增未登记端口；禁止未同步 registry/resolver/contract test
- [x] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> 原则/适用范围/禁止条款同模板基线。**本 Story 零新领域异常（DC-8）**——agent 段 440-449 已满（5-5 全分配），本 Story 无需开新段；全部失败面由既有异常覆盖：

- [x] 复用清单（零新增）：`EntityValidationError`(242——实体/Query 不变量)、`StorageError`(103——PG 仓储读写故障透传)、`AgentNotFoundError`(443)/`IsolationStateNotInitializedError`(447)/`IsolationLevelNotSupportedError`(446)（切换守卫序透传——零改动）、`AuditError`(105——audit 联动失败，**被降级捕获记日志不上抛**，DC-6）
- [x] 零新异常论证：写入失败=存储故障（103 语义精确）；检索无业务异常面（空结果非异常）；实体校验=不变量（242 语义精确）；无新业务规则失败面。`_code_ranges.py` / `exceptions/__init__.py` / `EXCEPTION_HTTP_MAP` / §3.3.2 文档表**零改动**（异常契约四件套豁免——无新增即无登记）
- [x] BDD 异常路径：StorageError 拒绝路径（AC-2.3）+ 242 不变量路径（AC-1.2）纳入验收 Edge Cases

#### API 契约 (API Contract)

- [x] 本 Story 无 REST API（检索交付面 = 端口 + CLI；REST 端点归 Epic 7-2——audit router 未挂 create_app 是 1.10 既有形态，维持）。`docs/api/openapi.yaml` 零改动
- [x] CLI 契约：`sisys-agent isolation-logs --agent-id <uuid> [--level <L4|L3|L2>] [--start <ISO>] [--end <ISO>] [--limit N] [--offset N]`——argparse subparsers 形态对齐 5-4 set-isolation/isolation-status 先例（agent_cli.py L280+）；**测试注入形态**：CLI 测试追加于 `tests/unit/interfaces/cli/test_agent_cli.py`（56 存量测试——monkeypatch bootstrap/resolve/get_resolver 三件套 + 进程内 main(argv) + capsys，无 Typer CliRunner 先例）；**联动面**：该文件 L78-83「帮助文本漂移锁」五子命令清单须随第六子命令扩展（+ parser description/epilog 更新）——漏改不红但漂移锁退化；无结果输出「无隔离切换日志记录」单行；有结果输出多行摘要（log_id 缩短形态 / previous → target / switch_timestamp ISO / trigger_reason 截断 / approval_chain 空显 `-` 非空显 `→` 连接）+ 尾行总数；**level 参数校验**：非法等级值退出码非 0 + 错误提示（str→枚举转换守卫在 CLI 层——5-4 先例，服务不重复校验）；**审批链口径**：set-isolation 不扩展 --approval-chain 参数（范围边界表裁剪——MVP 用户请求通道空审批链是真实事实记录）

#### 六边形架构约束（必须遵守）

> 四层定义/零依赖原则/依赖方向矩阵同模板基线。本 Story 特别注意：

- [x] `isolation_switch_log.py`（实体）+ `isolation_switch_log_repository.py`（端口 + Query/Result）全部 domain 层，仅标准库 + 同层 events（IsolationLevelSwitched/IsolationLevel import——from_event 工厂消费事件类型）/ exceptions / entities——`.importlinter` domain 契约（禁 pydantic/sqlalchemy/redis）
- [x] `PostgreSQLIsolationSwitchLogRepository`（infrastructure）实现 domain 端口——SQLAlchemy async session + outbox 双模式 fallback 先例；禁 import application
- [x] `IsolationManagementService`（application）构造注入一 domain 基础端口（log repo）+ 一 domain 服务端口（audit_service——AuditServicePort 在 domain/ports）+ 既有四依赖——application→domain 合法；audit_service 类型注解用 domain 端口（**非 infrastructure AuditServiceImpl**——依赖方向）
- [x] CLI（entrypoints/interfaces）消费 domain 仓储端口（isolation_switch_log_repository）+ application 服务端口（isolation_management_service）——interfaces/entrypoints→domain+application 合法；组合根装配经 lambda

#### 验收标准 Gherkin (Acceptance Tests)

- [x] 功能测试文件：`tests/acceptance/test_acceptance_isolation_switch_log.feature`
- [x] 步骤实现文件：`tests/acceptance/test_acceptance_isolation_switch_log.py`
- [x] 场景组织：AC 注释横幅分组（带层级标注）+ 全场景逐一 `@scenario` 显式绑定（多行字面量路径 + 场景绑定与步骤交替排列——5-4/5-5 R6 改造后形态，禁 `scenarios()` 批量绑定与 then-pass 占位）；场景名 `AC-x.y - 中文描述`（feature 与 .py 逐字一致）；**禁 Background 背景块门控**（PG 模板形态已废弃——服务依赖场景各自步骤化门控）
- [x] 18 场景规划（终态 = Task 0 编写 17 + Task 6 追加收尾 1；三属性分档表 Task 0.6 定稿落 docstring）：
  - AC-1 ×2（端口级，无服务依赖，脱离门控）：from_event 六字段映射与审计字段完整 / 实体不变量（242 五场景参数化）
  - AC-2 ×4（服务级；AC-2.1/2.2/2.4 真实 Redis+PG 双门控，AC-2.3 **Redis 单门控**——断言面全在 Redis/事件侧对好 PG 零依赖，坏端点 127.0.0.1:1 即被测面）：切换成功六字段落库 / no-op 零日志新增 / audit-first 拒绝路径（坏仓储→StorageError→切换被拒 Redis 未变零事件——**本场景不设 ContextVar session（走 fallback）+ 坏端点 127.0.0.1:1 快速失败，见 AC-2 验证标准前提**）/ audit 联动记录（audit_log 表 isolation:switch 一条 + correlation_id 匹配）
  - AC-3 ×3（服务级，真实 PG 门控）：按 AGENT 检索 / 按时间范围+隔离等级组合检索（level 双向命中）/ 分页与排序（total/offset/limit + 最新在前）
  - AC-4 ×2（真实 PG 门控）：RLS 篡改拒绝（UPDATE/DELETE 0 行——绕过环境 skip）+ CheckConstraint 拒 no-op 直插 / worm_ref 预留与表结构（ORM `__table_args__` 断言）
  - AC-5 ×2（委托集成计时）：写 P95<50ms（委托 helper）/ 检索 P95<500ms + 成功率 20/20
  - AC-6 ×4（端口级 + 服务级 + 静态）：组合根接线（resolve 可达 + PortSpec 元数据 + **接线内省锚**——resolve 服务后内省第五/六依赖属性 isinstance，禁发真实命令）/ CLI isolation-logs 真实链（set_session 作用域内 in-process 调 main——rollback 零残留）/ 架构合规静态扫描（AST——domain 零依赖 + 组合根外零实例化）/ 回归面资产在位（5-4/5-5 验收与探针文件存在 + AuditActionType 枚举项注册）
  - 收尾 ×1：完成清单逐项确认（src + tests 四目录文件存在性——5-5 收尾同款）
- [x] BDD 步骤约束：全部同步 `def` + `_run_async(context["_loop"], ...)`（禁 `@pytest.mark.asyncio`——context 数据丢失）；Redis 场景前置「假如 Redis 缓存服务可用」ping 门控（失败 `pytest.skip` 动态跳过）+ PG 场景前置「假如 PostgreSQL 服务可用」连接门控（asyncpg/引擎探测——PG 模板 L110-135 形态；双服务场景两级门控串联）；参数化步骤显式 `parsers.parse`；异常断言三段式（raises 捕获存 `context["caught"]` → then 断言 code + context）
- [x] **场景三属性分档表**（Task 0.6 定稿落 docstring）：每场景「层级（端口级/服务级）+ 服务依赖（Redis+PG/PG/无）+ 断言面（字段完整性/顺序与计数/检索矩阵/防篡改/性能/静态扫描）」
- [x] 显式 `pytestmark = [pytest.mark.acceptance, pytest.mark.redis, pytest.mark.database, pytest.mark.xdist_group("isolation-switch-log-perf")]`（文件名不含 redis/postgres 关键词——显式声明双服务 marker；组名与集成计时场景逐字同组——loadgroup 同 worker 委托缓存命中前提；marker 只用已注册集合——`--strict-markers`）+ 延迟 import 纪律（本 Story 新模块一律步骤函数体内延迟 import）
- [x] teardown 双面清理：Redis 双键（`build_key("agent", ...)` + `build_key("isolation", ...)`——`_agent_ids` 登记 + exists 复核删净，禁 delete_pattern/flush/全库 scan_iter）+ PG 事务隔离（场景级 session `set_session(token)` + teardown `rollback()` + close + **`reset_session(token)`**——ContextVar 完整复位是 AC-2.3「不设 session」前提的硬依赖：前序 set_session 场景若泄漏 ContextVar（只 close 不 reset），AC-2.3 的 get_session 返回僵尸 session 抛 SessionClosedError（非 RuntimeError）不走 fallback——token 复位形态对齐 PG 模板 L98-100；日志写走请求 session 路径 flush，同事务断言可见，rollback 零残留；**RLS/CheckConstraint 场景的 rollback 复位**）；443 拒绝路径预生成随机 uuid 不登记

#### 审计联动契约（Task 0 定稿——DC-6/DC-9）

- [x] `AuditActionType` 追加 isolation 组：`ISOLATION_SWITCH = "isolation:switch"`（第 8 组——注释组风格对齐既有七组；值格式 `{域}:{动作}` 小写惯例）
- [x] 联动调用形态（isolation_management_service 切换方法尾部）：
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
- [x] 降级语义：联动失败不回滚不重试（主日志 SSOT 已在 log_repository 落盘；audit_log 是联动索引——PersistentNoteTaker L248-268 先例同款）；组合根 `resolve_optional("audit_service")` 注入
- [x] actor 语义注记（V1 迁移预留）：MVP CLI 无用户上下文，`actor="agent:{agent_id}"` 记的是被操作对象而非发起主体（可接受——单用户系统）；V1 动态触发/REST 化时应改记真实发起者（actor=用户/系统命令源），agent 保留为 target_resource——届时 actor 语义迁移随 7-2 REST 化立项评估，避免历史记录两种 actor 语义混读

**Task 0 完成标志：**
- [x] 上述规范项全部定义完毕
- [x] Gherkin 验收测试已编写，运行确认失败（红阶段验证——ModuleNotFoundError/断言红为合法红）
- [x] 规范文档通过人工评审或自动化校验
- [x] **链路接线断言清单**已定义（Epic 4 回顾行动项 7.1-1）：①`isolation_switch_log_repository` 组合根 register_port 装配验证（resolve 可达 + isinstance + PortSpec 元数据 + SINGLETON）②`isolation_management_service` lambda 五/六依赖注入确认——**接线内省锚**（resolve 服务后内省实例第五/六依赖属性 isinstance 对应端口——lambda 漏注入即红，**禁发真实命令**（手动组装纪律——SINGLETON 跨循环死连接）；「真实切换→可检索」端到端语义由 AC-2.1 手动组装链承载）③audit 联动接线（resolve_optional 可达性 + 降级路径）④CLI isolation-logs 命令注册（--help 可见）⑤事件面零改动复验（IsolationLevelSwitched 双登记不漂移——yaml + DEFAULT_MAPPINGS 断言沿用 5-4 验收锚）

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
| TDD 单元测试 | PG 仓储逻辑面 | **save/search 双模式分派**（两方法各：ContextVar 命中→add+flush/查询；未命中→session_factory fallback——CLI 检索可达性前提）/**StorageError 包装链**（SQLAlchemyError side_effect → StorageError + __cause__ 链接）/search 条件构建（mock session/AsyncMock——薄单测，真实 PG 断言归集成） | `tests/unit/infrastructure/storage/postgresql/test_isolation_switch_log_repository.py` | Task 2 |
| TDD 契约测试 | isolation_switch_log_repository | 11 维度 + _DummyResolver | `tests/contracts/test_port_contract_isolation_switch_log_repository.py` | Task 2 |
| TDD 契约测试 | isolation_management_service（存量） | impl 维度与 lambda 同步（_DummyResolver 补两分发 + 补 resolve_optional 方法——debate_session L31 先例） | `tests/contracts/test_port_contract_isolation_management_service.py`（追加） | Task 3 |
| TDD 单元测试 | AuditActionType 扩展 | ISOLATION_SWITCH 枚举值注册 | `tests/unit/domain/events/audit_events/test_audit_events.py`（追加） | Task 3 |
| TDD 验收测试 | Gherkin + BDD | 17 场景 Task 0 编写（收尾 Task 6 追加成 18 终态）；各 Task 转绿——AC-1 随 Task 1、AC-2 随 Task 3、AC-3 随 Task 2/4、AC-4 随 Task 4、AC-5 随 Task 4、AC-6 随 Task 3/5 | `test_acceptance_isolation_switch_log.feature/.py` | Task 0-6 |
| 集成测试 | 全链（真实 Redis+PG） | 切换→日志落库六字段/检索矩阵/RLS+CheckConstraint/P95 双指标/成功率 20/20/no-op 零新增/audit-first 拒绝真实链 | `tests/integration/test_integration_isolation_switch_log.py` | Task 4 |
| SDD 架构验证 | 六边形约束 | domain 零外部依赖/组合根外零实例化/端口方向/接线静态锚 | `tests/unit/architecture/test_arch_isolation_switch_log.py` | Task 5 |
| CLI 单元测试 | isolation-logs 命令 | 参数解析/level 校验/输出形态/空结果（对齐 5-4 CLI 测试先例——追加于 `tests/unit/interfaces/cli/test_agent_cli.py`，monkeypatch 三件套 + 进程内 main(argv) + capsys；同步 L78-83 帮助文本漂移锁五子命令清单扩展） | `tests/unit/interfaces/cli/test_agent_cli.py`（追加） | Task 3 |

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

- [ ] **PG 事务隔离**：集成/验收场景级 session `set_session(test_session)` → 日志写走请求 session 路径（add+flush——不走 fallback）→ 同事务断言可见 → teardown `rollback()` + close + **`reset_session(token)`（ContextVar 完整复位——AC-2.3 不设 session 前提的硬依赖，泄漏时 get_session 返回僵尸 session 抛 SessionClosedError 非 RuntimeError 不走 fallback）**——**零残留零 delete/truncate**（集成 conftest `pg_session` begin+rollback 先例 L522-536——⚠️ 勿混用同文件 L289-293 的裸 `postgres_session`（无事务隔离））；RLS/CheckConstraint 触发 IntegrityError 后必须 `session.rollback()` 复位再继续；**例外：AC-2.3 坏仓储拒绝场景不设 ContextVar session**（双模式 get_session 优先——设了测试 session 则坏仓储命中好 session 永不红；不设 → RuntimeError → 走坏 factory → StorageError，见 AC-2 验证标准前提）
- [ ] **Redis 双键清理**：`_agent_ids` 全登记（InstantiateAgentUseCase 构造的每个真实 Agent），teardown 逐 agent 删 `build_key("agent", ...)` + `build_key("isolation", ...)` 双键 + exists 复核删净
- [ ] **场景级独立 Redis 客户端 + `_run_async` 同循环**（session 级客户端跨场景 "Event loop is closed"——禁共享 fixture）
- [ ] **手动组装纪律**：验收/集成禁 `resolve("isolation_management_service")` 发真实命令——SINGLETON 跨 function-scope 循环复用死连接 + 其 PG 依赖生命周期不可控；一律场景级客户端手动组装（IsolationManagementService + 双 Redis 仓储 + PG 日志仓储[测试 session 注入] + 真实/降级 audit_service 全真实链——`_assemble_real_chain` 形态扩展）；resolve 仅 AC-6.1 接线断言且禁发命令
- [ ] **audit 联动验收面**：真实 audit_service（PG session 同事务——audit_log 写入同 rollback 回收）；降级场景归单测（AsyncMock side_effect AuditError——验收禁 mock，降级是异常注入面）
- [ ] **计时场景**：新 `xdist_group("isolation-switch-log-perf")` 串行 + benchmark 场景级标记；`SWITCH_LOG_WRITE_P95_LIMIT_SECONDS = 0.05` / `SWITCH_LOG_SEARCH_P95_LIMIT_SECONDS = 0.5` 常量单源（集成定义/验收共享 import）
- [ ] **RLS 环境敏感**：deny 断言前置探测连接角色（**`rolsuper OR rolbypassrls`** 或表 owner 绕过——superuser 无论 FORCE 与否都绕过 RLS，探测漏 rolsuper 会误判为非绕过 → UPDATE 实际成功 → 断言红而非 skip）→ 绕过环境 `pytest.skip` 动态跳过（禁写死 skip；⚠️ 本地/CI 默认 `postgres` superuser 连接下本场景恒 skip——绿色路径依赖非 superuser 应用角色环境）
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
| AC-2 | 守卫序零日志（443/447 零 save） | Task 3 | 守卫先于日志位 | test_isolation_management_service（追加）+ 验收 AC-2 场景内 |
| AC-3 | 四维检索 + 分页排序 | Task 2/4 | Query/Result + search 实现 | 仓储单测 + test_integration_* + 验收 AC-3×3 |
| AC-4 | RLS 防篡改 + CheckConstraint 拒 no-op（deny UPDATE/DELETE） | Task 2/4 | migration RLS 段 + 实证 | 集成 + 验收 AC-4.1 |
| AC-4 | 表结构/索引五/worm_ref 预留 | Task 2 | ORM + migration 015 | 仓储单测 + 集成 + 验收 AC-4.2 |
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

- [x] Subtask 0.1: 定义数据模型规范——IsolationSwitchLog（frozen 八字段 + from_event + 不变量五场景 + to_dict）+ IsolationSwitchLogQuery/IsolationSwitchLogSearchResult + PG 表结构（本文件「数据模型」节为唯一真源）
- [x] Subtask 0.2: 定义端口契约——IsolationSwitchLogRepository 两方法 + IsolationManagementService 五/六依赖签名扩展 + 组合根注册元数据（契约变更登记 ×1）
- [x] Subtask 0.3: 定义异常契约——零新异常复用清单（242/103/443/446/447/105）+ 零新增论证
- [x] Subtask 0.4: 定义审计联动契约——AuditActionType.ISOLATION_SWITCH + record 调用形态 + 降级语义（DC-6/DC-9 节）
- [x] Subtask 0.5: 定义 migration 015 契约——列/索引五（含 previous_level——level 双向命中 or_ 两臂索引化）/CheckConstraint/RLS 四策略 + FORCE + downgrade 对称（AC-4 节）
- [x] Subtask 0.6: 编写 Gherkin `test_acceptance_isolation_switch_log.feature`（17 场景）+ BDD 步骤实现骨架 `.py`（@scenario 全显式绑定 + context dict fixture + Redis/PG 双门控 + 双面清理）+ **17 场景三属性分档表**定稿（docstring）
- [x] Subtask 0.7: 运行验收测试确认失败（🔴 红阶段——ModuleNotFoundError/断言红为合法红）
- [x] Subtask 0.8: 移交留项与偏离声明处置落盘（deferred-work.md：#7 竞态注记追加 + R1-DF2 5.6 注记——Task 0 评估表；**偏离声明 OD-1/OD-2/OD-3/OD-4 四项同步登记**——OD-1 WORM gap 链接 Story 13-4（SOX）承接方 + RLS 补偿控制差距四注（BYPASSRLS 绕过/备份导出不受约束/无保留期限/**TRUNCATE·DROP 不走 RLS——业界标准是 DDL owner 与应用角色分离 + 应用角色仅 GRANT INSERT/SELECT，归 13-4 落地**）/ OD-2 链接 9-4·9-5 协作组 / OD-3 链接 9-3（FR-AC-09）/ OD-4 命名映射与 DDL 分歧链接多租户专项 + 9-3——gap 四要素齐备：描述/触发条件/归宿/承接方链接；注：CLI --approval-chain 裁剪属范围边界非规划偏离（规划对 set-isolation 参数集零约束），不进台账）

**完成标准/Definition of Done:**
- [x] 规范项全部定义；验收测试红阶段确认；链路接线断言清单 L1-L5 定义

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

- [x] Subtask 1.1: 🔴 红 — 编写实体失败测试（六字段/五不变量/to_dict/frozen）
- [x] Subtask 1.2: 🟢 绿 — 实现最小代码
- [x] Subtask 1.3: 🟡 变异 — 映射/不变量突变实证
- [x] Subtask 1.4: 🔄 重构 — docstring/导出/ruff+mypy

**完成标准/Definition of Done:**
- [x] 实体实现完成；验收 AC-1×2 场景转绿；domain 覆盖率 ≥90%

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
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/postgresql/test_isolation_switch_log_repository.py`（模型 `__table_args__` 断言：约束/索引名（五索引）；**save/search 双模式分派**——两方法各：ContextVar 命中→add+flush/查询，未命中→session_factory fallback（CLI 检索可达性前提——search 漏 fallback 则 AC-6.2 CLI 场景必炸 RuntimeError）；**StorageError 包装链**——save/search 各注入 SQLAlchemyError side_effect → 断言 raises StorageError 且 `__cause__` 链接原异常（redis_isolation_repository L94 先例的 PG 版——outbox 模板不带包装，是本仓储相对模板的必做增量）；search 条件构建：mock session 断言 where 子句组装（level 双向 or_）——薄单测） |
| 🟢 绿 | 实现 `IsolationSwitchLogModel` + `015_isolation_switch_logs` migration + `PostgreSQLIsolationSwitchLogRepository`（双模式 session + **SQLAlchemyError→StorageError 包装链（save/search 两方法）** + 动态条件 + count + timestamp desc + offset/limit + **ORM→实体映射丢弃 created_at 列**——实体八字段无 created_at（行创建审计列仅 DB 侧，检索投影不含——构造实体不传即可，非错误）） |
| 🟡 变异 | RLS deny 策略删一行→集成 0 行断言红（归 Task 4 实证）；level 命中条件从 or_ 改 eq→集成双向断言红；还原→绿 |
| 🔄 重构 | `models/__init__.py` 注册 + docstring + ruff+mypy |

#### TDD 循环 C：组合根注册 + 契约测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/contracts/test_port_contract_isolation_switch_log_repository.py`（11 维度 + _DummyResolver） |
| 🟢 绿 | 组合根 `# === Story 5.x ===` 区段追加注册（SINGLETON + owner=platform + tags——DC-11） |
| 🔄 重构 | lambda 注入 session_factory（组合根实际端口名已定谳 `session_factory`——L232 注册，outbox L621 同款） |

- [x] Subtask 2.1: 🔴 红 — 端口/Query/Result 测试
- [x] Subtask 2.2: 🟢 绿 — 端口定义
- [x] Subtask 2.3: 🔴 红 — 模型/迁移/仓储测试
- [x] Subtask 2.4: 🟢 绿 — 模型 + migration 015 + 仓储实现
- [x] Subtask 2.5: 🟡 变异 — 双模式/命中条件突变实证
- [x] Subtask 2.6: 🔴🔴🟢 — 契约测试 + 组合根注册
- [x] Subtask 2.7: 🔄 重构 — 导出/注册/docstring/门禁

**完成标准/Definition of Done:**
- [x] 仓储三件（端口/模型+迁移/实现）交付；`alembic upgrade head` 全新库可执行（本地验证）；契约 11 维度绿；验收 AC-3×3、AC-4×2 随 Task 4 集成面转绿（端口级断言本轮即绿）

---

### Task 3: 切换链接线——audit-first 写入 + audit 联动 + AuditActionType + CLI + 回归面

**关联 AC:** AC-2（全部）、AC-6.1/6.2/6.4

#### TDD 循环 A：IsolationManagementService 五/六依赖 + audit-first 插位

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `tests/unit/application/services/test_isolation_management_service.py` 追加：audit-first 顺序（save 先于 Redis save——AsyncMock calls 顺序断言）/ no-op 零 save / 443·447 零 save / 坏仓储 StorageError 上抛且零 Redis 写零事件 / audit 联动调用参数 + 降级（side_effect AuditError → 切换成功 + caplog warning）/ 存量构造点全量补两依赖 |
| 🟢 绿 | 构造签名扩展 + switch 方法插位（**既有事件构造块 L148-155 上移至 Redis save 之前** → from_event → config load → log save → 既有 Redis save → publish → 联动——见「现有代码继承」表插位注记）|
| 🟡 变异 | audit-first 顺序对调（save 移到 Redis 后）→ calls 顺序断言红；联动 except 删除→降级用例红；还原→绿 |
| 🔄 重构 | docstring 更新（模块头 Raises 契约 + audit-first 叙事）+ ruff+mypy |

#### TDD 循环 B：AuditActionType 扩展 + 组合根 lambda + CLI

| 阶段 | 动作 |
|------|------|
| 🔴 红 | test_audit_events.py 追加 ISOLATION_SWITCH 枚举断言；CLI 测试追加 isolation-logs（参数解析/level 校验/输出/空结果）|
| 🟢 绿 | 枚举第 8 组 + 组合根 lambda 扩展（resolve + resolve_optional）+ agent_cli 子命令 |
| 🟡 变异 | 枚举值改错→断言红；lambda 漏注入第六依赖→接线内省锚红（resolve 服务实例内省属性——禁发真实命令）；还原→绿 |
| 🔄 重构 | CLI --help 文本 + 模块头使用示例更新 |

#### TDD 循环 C：回归面全量同步（苦役先例——5-5 Task 3）

| 阶段 | 动作 |
|------|------|
| 🔴→🟢 | 全仓 grep `IsolationManagementService(` 构造点逐一登记修补（**实测基准 14 处**，见 AC-6.4 清单）：组合根 lambda（L2893）/ 单测工厂 / 集成三链（agent_isolation / triple / isolation_security）/ 验收 8 处五文件（agent_isolation ×3 / triple / workflow ×2 / **agent_instantiation / agent_profile_loading——易漏**）/ 契约一处（test_port_contract_agent_instantiation_use_case L60）；另有 isolation_management 契约测试 _DummyResolver 补两依赖分发（依赖分发面非构造点）——**实施时以 grep 实际清单为准逐一修补并登记**；5-4/5-5 存量测试全量回归绿 |

- [ ] Subtask 3.1: 🔴 红 — 服务接线失败测试（顺序/零调用计数/降级/参数）
- [ ] Subtask 3.2: 🟢 绿 — 五/六依赖 + audit-first 插位 + 联动
- [ ] Subtask 3.3: 🟡 变异 — 顺序对调/降级删除实证
- [ ] Subtask 3.4: 🔴🟢 — 枚举扩展 + lambda + CLI 子命令
- [ ] Subtask 3.5: 🟡 变异 — 接线内省锚（漏注入红——resolve 服务实例属性内省，禁发命令）
- [x] Subtask 3.6: 🟢 — 回归面构造点全量同步 + 5-4/5-5 存量全绿
- [x] Subtask 3.7: 🔄 重构 — docstring/门禁

**完成标准/Definition of Done:**
- [x] 接线完成；验收 AC-2×4、AC-6.1/6.2 转绿；5-4/5-5 回归零破坏；应用层覆盖率 ≥85%

---

### Task 4: 集成测试与性能——全链断言 + 检索矩阵 + RLS/CheckConstraint 实证 + P95

**关联 AC:** AC-3（集成面）、AC-4.1、AC-5（全部）

> 性质说明：本 Task 对 Task 1-3 已交付链编写验证型测试（套件型豁免——红由 Task 0 前置，活性由变异保证）。

- [x] Subtask 4.1: 编写 `tests/integration/test_integration_isolation_switch_log.py`——真实 Redis+PG（real_redis + real_postgres_engine/postgres_session 门控）：场景① 切换全链→检索六字段逐项（含 approval_chain JSONB roundtrip）② no-op 零新增 ③ audit-first 拒绝（坏连接仓储实例——真实类注入不可达 session_factory（127.0.0.1:1）+ **场景不设 ContextVar session（走 fallback）**→StorageError→Redis 等级未变+零事件——_RecordingEventPublisher）④ audit 联动真实 audit_service→audit_log 表 isolation:switch 记录 ⑤ 检索矩阵（四维独立+组合+分页+排序——3 Agent×2 条造数）⑥ RLS deny UPDATE/DELETE 0 行（绕过环境 skip）+ CheckConstraint IntegrityError ⑦ 写 P95（`_PERF_CACHE` + 20 采样 + 0.05 常量）⑧ 检索 P95（0.5 常量）⑨ 成功率 20/20
- [x] Subtask 4.2: 变异实证——RLS deny 行删除→场景⑥红；level 命中 or_→eq→场景⑤双向断言红；阈值常量突变→⑦⑧红；还原→绿
- [x] Subtask 4.3: 验收 AC-3×3/AC-4×2/AC-5×2 场景转绿（委托计时缓存命中验证）

**完成标准/Definition of Done:**
- [x] 集成九场景全绿；P95 双指标达标；验收对应场景全绿；计时组与 5-4/5-5 组不冲突

---

### Task 5: SDD 架构约束验证测试

**关联 AC:** AC-6.3

> 性质说明：SDD 规范验证测试（验证架构约束是否被遵守），非 TDD 单元测试。

- [x] Subtask 5.1: 创建 `tests/unit/architecture/test_arch_isolation_switch_log.py`——验证器 A：domain 零外部依赖（isolation_switch_log.py/isolation_switch_log_repository.py AST 扫描——白名单标准库+同层 import；黑名单 pydantic/sqlalchemy/redis 等）；验证器 B：组合根外零实例化（PostgreSQLIsolationSwitchLogRepository 实例化点仅 composition_root.py + tests/——src/ 扫描）；验证器 C：端口方向（agent_cli import 白名单——domain/application 合法、infrastructure 禁入）
- [x] Subtask 5.2: 变异实证——实体文件注入 sqlalchemy import→验证器 A 红；还原→绿
- [x] Subtask 5.3: 验收 AC-6.3 场景转绿

**完成标准/Definition of Done:**
- [x] 架构验证器三件全绿；违规即红；循环依赖检测沿用 ruff/isort（不引入新工具）

---

### Task 6: 开发结束验收测试

**关联 AC:** 全部

> 性质说明：对 Story 收尾阶段的交付物与完成清单进行最终验收。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 feature 收尾验收场景（完成清单） |
| 🟢 绿 | 编写 BDD 步骤实现（文件存在性检查——src 文件清单 + tests 四目录清单，missing 断言） |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [x] Subtask 6.1: 收尾场景步骤 1 — src 完成清单逐项确认（实体/端口/模型/迁移/仓储/服务/CLI/组合根 8 文件）
- [x] Subtask 6.2: 收尾场景步骤 2 — tests 四目录（unit/contracts/integration/acceptance）完成清单逐项确认（同一收尾场景内的两份清单——收尾 ×1 计数不变）
- [x] Subtask 6.3: 运行全量验收（18 场景终态）+ `pytest tests/` + `ruff check` + `mypy` 收尾校验 + 5-4/5-5 回归终验
- [x] Subtask 6.4: 文档与台账终态更新——deferred-work.md 留项终态（#7 注记/R1-DF2 注记/OD-1~OD-4 落盘确认）+ architecture.md §5 注记（5.6 交付）+ §13 目录树 + sprint-status.yaml 状态流转

**完成标准/Definition of Done:**
- [x] 18 场景全绿；全量回归零 5.6 面新失败；Story 可进入 `review`

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
- 论证：①审计不丢要求——同步写最可靠，失败即拒绝切换（无审计痕迹的切换不允许发生）；②reliable 事件**不能**经 `DualChannelEventBus.subscribe` 订阅（dual_channel_event_bus.py L82-83 抛 InvalidStateError），消费需 RabbitMQ 消费侧/Outbox 轮询基建——**归 5.7**（5-4 L284「接线归消费方 Story 立项时决定」）；③Outbox 表已存在事件持久化落点（event_outbox）但为投递中间态非审计载体——`cleanup_old_published_records` 默认保留 **30 天**且**全仓零调用接线**（无 Prefect flow/定时任务，published 行实际无限累积）、archived 是重试耗尽的状态迁移非时间驱动——**中间态生命周期无保证，更不可作审计存储**；④simplicity first——内嵌 4 行核心逻辑 vs 消费者+幂等+重试一套基建
- 顺序论证（audit-first vs state-first）：state-first 在日志失败时丢审计（合规红线）；audit-first 在「日志写成功+Redis 写失败」窗口产生未生效切换的日志记录（误报）——**两害相权：审计合规宁可多记不可漏记**，误报窗口登记风险 #1（PG 可用而 Redis 故障的极窄窗口，StorageError 上抛调用方可见切换失败）。**插位细则**：既有事件构造块（现 L148-155，位于 Redis save 之后）随插位整体上移至 Redis save 之前；只读操作前置（构造事件 → from_event → config load 只读 → log save → Redis save → publish → audit）最小化误报窗口——config load（AgentConfigError 440）失败发生于 log save **之前**：零日志/零 Redis 写/零事件发布，无副作用泄漏（事件对象纯内存构造，state 内存态变异随本地对象丢弃）——440 路径是干净拒绝，已随只读前置**退出**误报窗口（原「440 已留日志」系插位前旧序残留，勘误）
- 事务语义限定：HTTP 请求上下文（ContextVar session）下 log save 是 add+flush 不 commit——fail-closed 在 flush 失败时成立，但**持久性随外层请求事务**（请求回滚则日志与状态同回滚——与风险 #1 对称的反向窗口，当前 MVP 交付面仅 CLI fallback 独立 commit 故不可达）；Epic 7-2 REST 化立项时需评估请求事务边界（交接注记）
- 备选：事件订阅 handler 异步写——弃（DC-2 论证②③）；装饰器包装服务——弃（组合根 lambda 复杂化+顺序不透明）

**DC-3 检索端口——save/search 两方法 + level 双向命中**
- `search` 单方法承载四维+分页（Query Object）；level 命中语义 = previous 或 target 任一（or.md「按隔离等级检索」——切换涉及该等级即命中；单侧命中会漏「从 L3 切出」或「切到 L3」半边审计面）
- 结果强类型 `tuple[IsolationSwitchLog, ...]`（audit search 返回 dict 是 1.10 历史形态——新端口用实体，类型安全）
- 检索**无 443 守卫**（Agent TTL 过期后历史日志仍可查——审计要求；与写入面守卫形成对照，单测锁定该差异）

**DC-4 防篡改——RLS（ENABLE + **FORCE**）+ CheckConstraint 双层**
- RLS 四策略照抄 002_audit_tables（INSERT/SELECT 放行 + deny UPDATE/DELETE——DELETE policy 仅 USING 子句，002 已修正的 PG 语法约束）；**追加 `FORCE ROW LEVEL SECURITY`**（表 owner 默认绕过 RLS——FORCE 后受约束；superuser BYPASSRLS 属性仍绕过——环境敏感性登记，测试动态探测 skip）
- CheckConstraint `previous_level != target_level`：DB 层拒绝 no-op 日志（实体不变量的 DB 投影——双层防线，直插旁路也被拦）
- WORM 等效性论证：RLS deny UPDATE/DELETE = 追加型不可改写（应用连接面）；MinIO Object Lock 7 年归档是 §8.5 运营管线（OD-1 裁剪归 V1）——与 1.10 audit_log 现状对齐（audit WORMManager 未接线，audit_log 防篡改同为 RLS）

**DC-5 PG 仓储双模式 session（CLI 上下文可写可读）**
- 照抄 `PostgreSQLOutboxRepository`（Story 4-7 修复形态）：`get_session()` 命中（HTTP 请求事务内 add+flush）→ `RuntimeError` 时经注入 `session_factory` 走 `session_context()` 独立会话 commit（CLI/后台路径）；**save 与 search 两方法均双模式分派**——CLI isolation-logs 检索也必须走 fallback（否则进程内无 ContextVar session 时 search 撞 RuntimeError）；只读 search 经 session_context 正常退出的 commit 是无害空 commit
- ⚠️ **防呆：fallback 分派必须直调 `session_context.get_session()` 并 catch `RuntimeError`**（outbox L80 形态）——`PostgreSQLAdapter._session` property（L46-64）会把 RuntimeError 包成 InvalidStateError（`from None`），经 property 则 except RuntimeError 永不命中
- 不沿用 `PostgreSQLAdapter` 泛型基类（audit_repository_impl 直实现 Port 先例——本仓储有 search 定制查询与 fallback 双路径，基类 get_by_id/list_all 面板冗余）；**相对模板的必做增量——SQLAlchemyError→StorageError 包装链**（outbox/audit 模板均不包装；redis_isolation_repository L94 先例的 PG 版——端口契约 Raises 契约的实现载体，AC-2.3 断言可满足性前提）
- 测试策略：集成/验收走请求 session 路径（set_session 测试 session → flush → rollback 零残留；AC-6.2 CLI 场景同路径——set_session 作用域内 in-process 调 main）；fallback 路径薄单测（mock factory，save/search 两分派维度 + 包装链维度）+ CLI 真实链（E2E 面）

**DC-6 audit 联动——可选注入 + 降级容错（双层审计：SSOT + 联动索引）**
- 主日志 `IsolationSwitchLog`（隔离域 SSOT——六字段强类型+多维检索）+ 联动 `audit_service.record`（1.10 统一审计流索引——action_type=`isolation:switch` 使隔离切换进入全局审计检索面）
- audit_service **可选注入**（`AuditServicePort | None` + 组合根 `resolve_optional`——composition_root L2201 PersistentNoteTaker 先例）+ 失败降级（try/except logger.warning 不回滚不重试）——论证：主日志已落盘（SSOT），联动是增值索引；且 AuditServiceImpl→audit_repo 走请求 ContextVar session（audit_repository_impl 无 fallback），CLI 上下文无 session 时 get_session 抛 RuntimeError 被 record 的 except Exception 兜底**包装成 AuditError(105) 上抛**——必填+上抛会使 CLI set-isolation 在无 PG 请求环境崩溃，降级保切换主链可用（降级 except Exception 对 AuditError 包装形态兼容）
- 与第五依赖（log repo 必填）的差异化论证：log repo 是合规 SSOT（静默跳过=合规缺口→必填上抛）；audit 联动是 best-effort 索引（降级容忍）

**DC-7 WORM 归档裁剪（偏离声明 OD-1）**——worm_ref 字段预留（nullable，检索 roundtrip 保持 None）；MinIO WORM 24h 管线归 V1 合规归档管线（触发条件：审计归档批处理立项；与 1.10 WORMManager/archive 未接线现状对齐；防篡改由 RLS 等效承载——DC-4）

**DC-8 零新领域异常**——agent 段 440-449 已满（5-5 全分配）；失败面全覆盖于既有异常（242 不变量/103 存储/443·446·447 守卫/105 audit 降级捕获）；避免开 450-459 新段子域归属争议（隔离日志实体在 agent 域与 audit 域交界——复用既有异常是最小侵入解）

**DC-9 AuditActionType.ISOLATION_SWITCH**——枚举第 8 组 isolation（值 `isolation:switch`——`{域}:{动作}` 小写惯例）；1.10 资产合法扩展（枚举组追加不破坏既有 consumer）

**DC-10 CLI isolation-logs 检索命令**——MVP 检索交付面 = 端口 + CLI（REST 归 Epic 7-2；audit router 未挂 create_app 是 1.10 既有形态——本 Story 不扩大 REST 面）；argparse subparsers 对齐 5-4 先例；level 参数 CLI 层枚举转换守卫（服务不重复校验——5-4 DC-5 纪律）；set-isolation 不扩展 --approval-chain 参数（既有三参数形态保持——空审批链是 MVP 单用户请求通道的真实事实记录，见范围边界表）

**DC-11 组合根生命周期——SINGLETON（新端口从源头避免 captive）**——5-4 DC-7 新增面政策：「新增端口直接 SINGLETON，新增面从源头避免 SINGLETON 服务捕获 SCOPED 依赖形成新 captive」（isolation_repository L2874 同款）；本端口将被 SINGLETON isolation_management_service 捕获——选 SINGLETON 则该捕获零 captive 零注记；仓储无状态（session 每调用 ContextVar/fallback 现取），SINGLETON 无共享态风险。注记：本仓储 lambda 自身捕获 `resolver.resolve("session_factory")` 而 session_factory 注册未指定 lifetime（PortSpec 默认 SCOPED）——SINGLETON→SCOPED 捕获是 outbox_repo（L611-625）存量同款形态，sessionmaker 无状态引擎惰性连接，无实害（对标本 DC 时勿将「零 captive」误读为捕获链全零）。备选 SCOPED（对齐 audit_repo L489 先例）——弃：audit_repo 的 SCOPED 是 1.10 存量形态（audit_service SINGLETON 捕获它已成既有 captive），新增面不应复制该形态

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
| 1 | audit-first 误报窗口（日志写成功+Redis 写失败→记录未生效切换；config load 440 失败路径已随只读前置**退出**误报窗口——440 发生于 log save 之前，零日志零 Redis 写零事件的干净拒绝） | 登记窗口（PG 可用而 Redis 故障极窄）；StorageError 上抛调用方可见；V1 动态触发立项时评估补偿（延迟确认/状态回写）。**对称反向窗口**：HTTP 请求上下文下日志持久性随外层事务（请求回滚→日志与状态同回滚——MVP 仅 CLI fallback 独立 commit 故不可达；7-2 REST 化时评估，DC-2 交接注记） |
| 2 | RLS 环境敏感（superuser/owner/BYPASSRLS 绕过→deny 断言 flaky——**探测必须含 rolsuper**：superuser 无论 FORCE 与否都绕过，漏探测会误判非绕过→UPDATE 实际成功→断言红而非 skip） | FORCE ROW LEVEL SECURITY + 测试动态探测（rolsuper OR rolbypassrls / owner 检查）→ 绕过环境 pytest.skip 动态跳过（合规纪律；本地/CI 默认 postgres superuser 下恒 skip 属预期——skip 分支 + 变异实证是 MVP 实证面） |
| 3 | 构造签名扩展回归面遗漏（5-4/5-5 手动组装链漏补→存量红） | Task 3 循环 C 全仓 grep `IsolationManagementService(` 登记修补苦役先例；5-4/5-5 存量全量回归终验 |
| 4 | PG 仓储 fallback 在测试中真写库（session_factory 注入生产 factory→集成测试污染） | 测试一律走请求 session 路径（set_session）；手动组装链注入测试 session_factory 或仅请求路径；验收 teardown rollback 复核 |
| 5 | 并发切换日志乱序（5-4 风险 #7 延伸——日志序=事件序同竞态窗口） | MVP CLI 单发不可达；deferred-work #7 追加 5.6 注记（Task 0.8） |
| 6 | 组合根生命周期 captive 面 | **已从源头规避**——新端口 SINGLETON（DC-11，5-4 DC-7 新增面政策），SINGLETON 服务捕获 SINGLETON 依赖零 captive 零注记 |

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── entities/
│   │   ├── isolation_switch_log.py            # 新建：IsolationSwitchLog（frozen + from_event）
│   │   └── __init__.py                        # 修改：实体导出
│   └── ports/
│       ├── isolation_switch_log_repository.py # 新建：端口 + Query + Result
│       └── __init__.py                        # 修改：端口导出（如有聚合导出文件）
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
└── （回归面同步：test_acceptance_agent_isolation/triple/workflow/instantiation/profile_loading、
    test_integration_agent_isolation/triple/isolation_security、
    test_port_contract_agent_instantiation_use_case、既有 CLI 测试 test_agent_cli——Task 3 grep 清单为准）

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

- [x] **Task 0 完成（2026-10-25 dev-story）**：五视角并行调研全部锚点核验（隔离切换链路/审计日志体系/PG 存储与 migration/组合根与契约/测试模板——14 处构造点逐一命中零偏移）；Gherkin 17 场景 + BDD 骨架（含三属性分档表 docstring）；红阶段确认 **17 failed / 0 skipped**（全为合法红）；deferred-work.md 三处登记（#7 注记/R1-DF2 注记/OD-1~OD-4 区段）。**实施裁定一条**：AC-6.2 CLI 场景形态经跨循环实验证伪（CLI 内部 asyncio.run 新循环与 ContextVar session 绑定循环冲突——RuntimeError/InterfaceError 实证），裁定采用生产真实形态（造数 fallback 独立 commit + CLI fallback 全链 + superuser 清理——非绕过环境动态 skip），feature 文案与 .py docstring 实施注记同步。测试环境：redis-test/postgres-test 容器已启动（6380/5433），alembic 基线 001→014 全新库执行成功。
- [x] 故事需求从 `epics_v1.0.md` 提取（含范围边界表——与 5.7/V1/Epic 7 精确切分）
- [x] 架构约束从 architecture.md/core-domain-design/or.md/prd.md 提取
- [x] 前一个故事学习经验整合（5-5 教训链 + 移交留项三项处置 + 专项裁撤纪律）
- [x] 五视角并行代码调研（隔离切换链路 / 审计日志体系 / 事件总线与 Outbox / 端口注册与异常编码 / 验收测试模板风格——关键事实独立验证：事件六字段/切换通道/实体守卫/session fallback/RLS/枚举）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（含 DC-1~DC-11 设计决策 + OD-1~OD-3 偏离声明 + 风险六项）
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/5-6-isolation-switching-log.md`（本文件）
- `src/domain/entities/isolation_switch_log.py` — IsolationSwitchLog frozen 实体（from_event 六字段映射 + 242 不变量五场景 + to_dict）
- `src/domain/ports/isolation_switch_log_repository.py` — R1 基础端口（save/search 两方法 + IsolationSwitchLogQuery 四维检索 + IsolationSwitchLogSearchResult）
- `src/infrastructure/storage/postgresql/models/isolation_switch_log.py` — IsolationSwitchLogModel ORM（九列 + 索引五 + CheckConstraint）
- `src/infrastructure/storage/postgresql/repository/isolation_switch_log_repository.py` — PG 仓储（双模式 session + SQLAlchemyError/OSError→StorageError 包装链）
- `deploy/postgresql/alembic/versions/015_isolation_switch_logs.py` — migration 015（表 + 索引五 + CheckConstraint + RLS 四策略 + FORCE + downgrade 对称）
- `tests/unit/domain/entities/test_isolation_switch_log.py` — 实体单测（21 用例）
- `tests/unit/domain/ports/test_isolation_switch_log_repository_port.py` — 端口/Query/Result 单测（16 用例）
- `tests/unit/infrastructure/storage/postgresql/test_isolation_switch_log_repository.py` — 仓储薄单测（19 用例——双模式/包装链/条件构建/映射）
- `tests/contracts/test_port_contract_isolation_switch_log_repository.py` — 端口契约 11 维度（12 用例）
- `tests/integration/test_integration_isolation_switch_log.py` — 集成九场景 + 委托计时三 helper + 双 P95 常量单源
- `tests/unit/architecture/test_arch_isolation_switch_log.py` — 架构验证器 A/B/C（7 用例）
- `tests/acceptance/test_acceptance_isolation_switch_log.feature` — Gherkin 18 场景（17 + 收尾）
- `tests/acceptance/test_acceptance_isolation_switch_log.py` — BDD 步骤实现（@scenario 全显式绑定 + 双面清理 + 委托计时）

> 注：测试文件命名遵循仓内既有惯例（`test_arch_*` / `test_integration_*` 前缀形态），与 epics L1709-1710 的占位名（`test_isolation_switch_log.py` / `test_isolation_switch_log_integration.py`）不同——属规划占位名与仓内惯例的正常偏差，随 OD-4 一并知悉。

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

**已修改的文件/Modified (dev-story 实施完成 2026-10-25):**
- `src/application/services/isolation_management_service.py`（五/六依赖构造签名扩展 + 事件构造块上移 + audit-first 日志插位 + audit 联动可选降级）
- `src/application/ports/isolation_management.py`（docstring 契约更新——未改动签名，扩展仅实现侧）
- `src/domain/events/audit_events.py`（AuditActionType 第 8 组 ISOLATION_SWITCH = "isolation:switch"）
- `src/domain/entities/__init__.py`（IsolationSwitchLog 导出）
- `src/infrastructure/storage/postgresql/models/__init__.py`（IsolationSwitchLogModel 注册）
- `src/entrypoints/agent_cli.py`（isolation-logs 第六子命令 + 六参数 + ISO 时间守卫 + epilog 更新）
- `src/composition_root.py`（isolation_switch_log_repository SINGLETON 注册 + isolation_management_service lambda 五/六依赖扩展[resolve + resolve_optional]）
- `tests/unit/application/services/test_isolation_management_service.py`（_make_service 六替身扩展 + TestAuditFirstLogging 10 用例）
- `tests/unit/domain/events/audit_events/test_audit_events.py`（isolation 组枚举断言）
- `tests/unit/interfaces/cli/test_agent_cli.py`（漂移锁六子命令 + TestIsolationLogsCommand 7 用例）
- `tests/contracts/test_port_contract_isolation_management_service.py`（_DummyResolver 补 isolation_switch_log_repository 分发 + resolve_optional 方法）
- `tests/contracts/test_port_contract_agent_instantiation_use_case.py`（_StubIsolationSwitchLogRepository + 构造点两依赖）
- 回归面同步 8 文件（14 处构造点 + stub/AsyncMock 替身注入）：`tests/acceptance/test_acceptance_agent_isolation.py`（3 处）/ `test_acceptance_agent_triple_isolation.py` / `test_acceptance_agent_workflow.py`（2 处）/ `test_acceptance_agent_instantiation.py` / `test_acceptance_agent_profile_loading.py` / `tests/integration/test_integration_agent_isolation.py` / `test_integration_agent_triple_isolation.py` / `test_integration_isolation_security.py`
- `docs/architecture/architecture.md`（§5 交付注记 + §13 目录树 entities/ports 两处落位注记）
- `_bmad-output/implementation-artifacts/deferred-work.md`（#7 竞态注记 + R1-DF2 5.6 注记 + OD-1~OD-4 四项偏离声明区段）
- `_bmad-output/implementation-artifacts/sprint-status.yaml`（5-6 状态流转）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 5.6 |
| **Story Key** | 5-6-isolation-switching-log |
| **File** | `_bmad-output/implementation-artifacts/stories/5-6-isolation-switching-log.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 5: Agent 协作系统（价值组：单 Agent 战略规划能力） |
| **优先级** | P1-6（epics 执行序；prd.md FR-AC-06 功能等级 P0——双锚不矛盾，见「偏离声明」节尾优先级双锚说明） |
| **覆盖 FR** | FR-AC-06（prd P0——`[or.md 一.2.(9)]`） |
| **性能锚** | epics L1695-1697（日志记录 P95<50ms@L1695 / 日志检索 P95<500ms@L1696 / 日志存储成功率 100%@L1697） |
| **覆盖率锚** | 应用层 ≥85%（domain ≥90 / infrastructure ≥75——四层门禁） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | OD-1 WORM gap 未进 deferred-work 台账、未链接 V1 承接方——V1 立项方经 deferred-work.md 追不到 WORM 裁剪；RLS 补偿控制与监管级 WORM 的差距（BYPASSRLS 绕过 / PG 备份导出不受 RLS 约束 / 无 7 年保留期限）未显式登记（来源：Epic 5 偏离声明同步动作对标审查 2026-10-25，业界 gap-management 四要素基准） | P2 | 偏离声明表 OD-1 行补承接方链接（Story 13-4 SOX）+ 补偿控制差距三注；Subtask 0.8 增加 deferred-work.md 登记动作 |
| 2 | OD-2/OD-3 同类缺口——偏离归宿仅文字描述「归 V1」，无 deferred-work 登记（承接 Story 可达性依赖读者偶然读到本文件） | P2 | Subtask 0.8 一并登记（OD-2 链接 9-4/9-5、OD-3 链接 9-3[FR-AC-09]） |
| 3 | 偏离声明编号 D-n 与代码审查留项 D# 撞名（5-1 实害先例：偏离声明 D-7「AgentService 回迁评估」被同号审查留项 D7 核销记录淹没而遗漏执行） | P3 | 本 Story 起偏离声明编号改 **OD-n**（Original-plan Deviation）前缀全量重命名；历史 Story（5-1~5-5）不动；编号规范写入项目记忆供后续 create-story 遵循 |
| 4 | **R1-A** DC-2 论证③失实：「outbox 24h 归档/cleanup 会清理」——实测 `cleanup_old_published_records` 默认保留 **30 天**且全仓零调用接线（无 flow/定时任务），archived 是重试耗尽状态迁移非时间驱动（grep 独立定谳） | P1 | DC-2 论证③改写为真实事实（30 天 + 零接线 + published 无限累积——中间态生命周期无保证，更不可作审计存储；结论方向不变且更强） |
| 5 | **R1-B** search 双模式缺口：DC-5/Task 2 仅操作化 save 的双模式分派——CLI isolation-logs 检索时进程内无 ContextVar session，search 撞 RuntimeError（规范与 AC-6.2 硬需求脱节） | P1 | 端口契约/DC-5/Task 2 红阶段/仓储单测维度均改为「save/search 两方法均双模式分派」；只读 search 经 session_context 的 commit 是无害空 commit |
| 6 | **R1-C** AC-6.1 端到端锚与手动组装纪律互斥：链路接线断言清单②要求「resolve 服务→真实切换→search 可检索」，而测试隔离纪律明令「resolve 禁发真实命令」——同文互斥 | P1 | 端到端锚改**接线内省**（resolve 后内省服务实例第五/六依赖属性 isinstance，漏注入即红，禁发命令）；「真实切换→可检索」语义由 AC-2.1 手动组装链承载（L195/L277/L308/L497/L510 五处同步） |
| 7 | **R1-D** AC-2.3 坏仓储拒绝场景构造前提缺失：双模式 get_session 优先——按隔离纪律常规 set_session(test_session) 会使命中好 session，坏仓储永不触发 StorageError（僵尸场景） | P1 | AC-2.3/集成场景③/隔离约束节三处显式注明「本场景不设 ContextVar session（走 fallback）+ 坏端点 127.0.0.1:1 快速失败（connection refused，禁不可路由 IP）」 |
| 8 | **R1-E** AC-1 不变量计数错账：验证标准「六场景」vs 唯一真源「五场景」（L219 恰五项凑不出第六）；AC 正文清单漏 log_id 与 approval_chain 非 tuple 两面 | P1 | L126 改「五场景」；AC-1 And 清单补齐 log_id / approval_chain 非 tuple 与「数据模型」节对字 |
| 9 | **R1-F** 事件构造块位置未钉死：真实代码事件构造在 Redis save **之后**（L148-155），audit-first 插位（L141-L146 间）要求其上移——故事未明说，dev 按字面插入会 NameError 或破坏顺序 | P2 | 「现有代码继承」表/DC-2 插位细则/Task 3 绿阶段三处显式「事件构造块上移 + 只读前置（config load 随行其后）」 |
| 10 | **R1-G** 构造点回归面清单遗漏 3 文件：实测基准 14 处（src 1 + tests 13），故事清单漏 test_acceptance_agent_instantiation（L219）/ agent_profile_loading（L233）/ test_port_contract_agent_instantiation_use_case（L60） | P2 | AC-6.4 与 Task 3 循环 C 清单补全至 14 处基准（含行号与「易漏」标注；保留 grep 兜底条款） |
| 11 | **R1-H** 组合根端口名猜测：`pg_session_factory` 全仓不存在——实际端口名 `session_factory`（L232 注册，outbox L621 同款消费） | P2 | L233/L463 两处定谳改写（废除「实施时核对」对冲——事实已定） |
| 12 | **R1-I** CLI 帮助文本漂移锁联动未点名：test_agent_cli.py L78-83 五子命令清单断言 + parser description/epilog——第六子命令加入须同步扩展（漏改不红但漂移锁退化） | P2 | CLI 契约节点名联动面（漂移锁清单扩展 + epilog 更新 + 56 存量测试回归） |
| 13 | **R1-J** RLS 探测条件不完整：探测仅查 rolbypassrls + owner——superuser 无论 rolbypassrls 标志与 FORCE 都绕过 RLS，漏 rolsuper 会误判非绕过→UPDATE 实际成功→断言红而非 skip；本地/CI 默认 postgres superuser 连接下场景恒 skip 未注明 | P2 | AC-4/隔离约束/风险 #2 三处探测条件改「rolsuper OR rolbypassrls」+ 环境形态注记（恒 skip 属预期） |
| 14 | **R1-K** previous_level 无索引：level 双向命中 or_ 只索引 target_level 臂——生产单维 level 检索（审计高频）退化为全表扫描，P95<500ms 声明结构性不可达 | P2 | 索引四→五（补 previous_level 单列，与 target_level 对称——BitmapOr 两臂可达；AC-4/Subtask 0.5/Task 2/新建清单/矩阵五处同步） |
| 15 | **R1-L** DC-11 先例引用失准：5-4 DC-7 的操作性决策是「新增端口直接 SINGLETON 从源头避免 captive」（isolation_repository L2874 同款）——故事新建端口选 SCOPED 再注记无实害恰是该政策明确要避免的路径；audit_repo SCOPED 是 1.10 存量 captive 形态 | P2 | DC-11 翻转为 SINGLETON（5-4 DC-7 新增面政策 + 同域先例）；AC-6/L233/L308/L462/风险 #6 六处同步；captive 注记需求消失 |
| 16 | **R1-M** 规划权威面分歧零登记：architecture.md §9 字段名（from_level/to_level/trigger）与故事实体命名差异、arch-appendix L9753-9768 规划 DDL（单数表名/tenant_id NOT NULL/trigger_type NOT NULL/无 approval_chain 列/worm_storage_ref）分歧未登记 | P2 | 新增 **OD-4**（命名映射 + DDL 分歧处置——跟随事件 payload SSOT + 伪码同名 + 同域 audit_log 无租户列先例；gap 四要素齐备）；or.md 章节编号修正（一.3.(8)→一.2.[3].(8)、二.5.(3)→一.5.[6].(3)）；「唯一出现于 docs」过强声明修正（arch-appendix/伪码均有出现） |
| 17 | **R1-N** DC-10 同号错位（L84/L135 裸引 DC-10 指向 5-4 事件发布容错，与本文 DC-10 CLI 命令撞号）；CheckConstraint 场景归属错位（场景规划 vs 矩阵分属不同场景号）；audit search match_any count 缺陷防呆；fixture 名混淆（postgres_session 裸 session vs pg_session 事务隔离）；P95 裕量算术（12 倍实为 ~7 倍）+ 计时口径（不含 commit）；完成清单勾选矛盾；12 项 P3 记录级（Port/Adapter 行号、Subtask 6.1/6.2 命名、DC-3/DC-7 回指、新建十件口径、目录树 __init__、architecture.md 归属 Task 6、review 状态链、矩阵守卫序行、OD-1 区间/WORMManager 措辞/补偿差距第 4 注 TRUNCATE+gap-free+retention、actor 语义注记、CLI --approval-chain 裁剪登记、epics 文件名占位注记） | P2/P3 | 逐处修正（见 v1.1.0 变更行）；DC-10 两处补「5-4」前缀；CheckConstraint 归 AC-4.1 对齐；match_any/直调 get_session 两防呆注记；fixture 名修正；裕量改 7 倍+口径注；完成清单勾选；P3 逐项落地 |
| 18 | **R2-A（R1-M 自引入）** OD-4「不落 created_at 双时间戳」与 AC-4 表结构 created_at 列（v1.0.2 既有，server_default NOW()）直接互斥——dev 二选一盲区且 AC-4.2「ORM↔migration 一致」断言两读法皆绿（分歧静默落库） | P1 | 定谳方向：created_at **保留**非差异项（行创建审计列对齐 audit_log 同域先例；与 switch_timestamp 语义分工：切换时刻 vs 入库时刻）——OD-4 行与范围边界差异项清单同步改写（剔除 created_at 出差异项） |
| 19 | **R2-B（R1-F 自引入）** DC-2 尾句与风险 #1「config load 440 失败时已留日志属风险 #1 邻接变体」与 R1 钉死的顺序（config load 前置于 log save）矛盾——新顺序下 440 时零日志/零 Redis 写/零事件（干净拒绝，无副作用泄漏）；AC-2 Then 顺序链漏列 config load 使字面读法可反向实现出旧行为（440 时有日志 vs 无日志的可观察分歧） | P2 | AC-2 Then 顺序链补插「config load（既有只读——TTL 真源）」；DC-2 插位细则尾句与风险 #1 邻接变体改写为「440 路径零副作用干净拒绝，已随只读前置**退出**误报窗口（原句系插位前旧序残留，勘误）」 |
| 20 | **R2-C~R2-L（P3 批量）**：验收链计数陈旧（六链实为 8 处五文件——两处）；目录树/File List 回归面清单缺 3 新发现文件（两处）；AC-2 old_value 简写未标 .value（JSONB 序列化传枚举对象会触发降级静默丢失——反向风险）；L87 句尾「audit 联动」重复残句；测试分类表 CLI 行 grep 对冲残留；第五依赖私有属性名未钉死（内省锚依赖）+ _DummyResolver 缺 resolve_optional 方法（lambda 扩展后维度 9b/10/11 必 AttributeError——debate_session L31 先例）；AC-2.4 检索面未钉死（AuditSearchCriteria 无 correlation_id 字段）；DC-11「零 captive」漏 session_factory SCOPED 默认捕获注记（outbox L611 存量同款）；AC-2.3 过度门控（断言面零好 PG 依赖——精化 Redis 单门控）；Subtask 0.8 补 CLI 裁剪不进台账切分说明 | P3 | 逐处落地（见 v1.1.1 变更行）；另 6 项组合疑点证伪不成立留痕（AC-2.3×门控正交/5-4 同款断言引用准确/AC-6.2 三面分层闭合/rolsuper 三处互恰/CLI 裁剪非规划偏离/构造点×验证器 B 两类两断言不相交） |
| 21 | **R3-F1（推演二·断言可满足性断层）** PG 仓储 StorageError 包装链无设置点：端口契约声明「Raises: StorageError」且 AC-2.3/集成③ 断言 `pytest.raises(StorageError)`——但 outbox/audit 仓储模板均**不包装**（SQLAlchemy 原生异常透传），坏连接实际抛 `sqlalchemy.exc.OperationalError`（与 StorageError 无继承关系）——照抄模板实现下断言必红且红错位至 Task 4（薄单测绿、验收红） | P1 | 端口契约/Task 2 红绿/仓储单测分类/DC-5 四处补「except SQLAlchemyError → raise StorageError(...) from exc 包装链」必做项（redis_isolation_repository L94 先例的 PG 版——相对模板的实现增量显式化） |
| 22 | **R3-F2** 分页断言造数矛盾：「造 5 条→total=5；offset=4→1 条」与 AC-3 Given 统一造数「≥3 Agent×≥2 条（≥6 条）」冲突——按统一 Given 实现则 total=6 全翻车 | P2 | AC-3 验证标准明示分页场景**独立造数**（单 Agent 5 条）+ 补 offset==total 空页边界 + 四维独立用例归集成场景⑤的分工说明 |
| 23 | **R3-F3** teardown 漏 `reset_session(token)`：AC-2.3「不设 ContextVar session」依赖同文件前序 set_session 场景完整复位——泄漏时 get_session 返回僵尸 session 抛 SessionClosedError（非 RuntimeError）不走 fallback，AC-2.3 前提被静默破坏 | P2 | teardown 双面清理与隔离约束两处补 reset_session(token)（ContextVar 完整复位——AC-2.3 前提硬依赖，PG 模板 L98-100 token 形态） |
| 24 | **R3-F4~F8（P3 批量）**：AC-1.2 log_id/approval_chain 非 tuple 场景须 dataclass 直构造注入非法值（from_event 自铸合法值——与 DC-1 唯一构造通道的张力注记）；242 context 形态未钉死（{字段名: 值} vs {entity,field} 两先例并存——钉 isolation_state 形态）；ORM→实体映射丢弃 created_at 列形态未定义（实体八字段 vs ORM 九列不对称）；第六依赖属性名未对称钉死；offset==total 空页边界未测 | P3 | 逐处落地：直构造注入注记（生产通道唯一性不受影响）+ context 形态钉死 + 映射形态定义（数据模型/Task 2 绿两处显式 + AC-4 列定义支撑——R4 验证口径勘误）+ `_audit_service` 对称钉死 + 空页边界补测；18 场景三轴终推演 17✅1❌（AC-2.3 因 F1/F3 双因——修复后可达）+ 7 项证伪留痕（caplog 可观测/单门控正确/quantiles[18]=P95/IntegrityError 无需 pgcode/resolve 级联惰性/委托缓存不要求集成先跑/18 计数无漂移） |

### 🏁 循环审查收敛声明（Round 5 独立终审——2026-10-25）

> Story 5.6 文档审查周期经 1 轮基线对标（v1.0.1/v1.0.2）与 4 轮循环审查（R1 五视角调研+三视角审查 / R2 回归核查+组合交互 / R3 单深度推演 / R4 纯验证）收敛于 v1.2.2，四轮提交（151d8996 / 3967673c / 685eb4fe / 6cbd24f5）全部仅触及本 Story 文件，无游离变更。周期累计发现并修复 **P1×7**（R1×5 + R2×1 + R3×1）、**P2×17**、P3 批量 20+，另留 13 项证伪不成立留痕与 24 行修复台账。R5 终审（不轻信自报）对 10 项关键修复做「Story 记录 vs 文档现实 vs 代码现实」双向取证全部属实且行号精确（含构造点 14 处逐字命中、outbox cleanup 30 天零接线、StorageError 包装先例 redis L94、RLS rolsuper 语义、session_factory 端口名等）；独立快扫五维（AC↔Task 完整性 / 18 场景 BDD 自洽 / OD 承接方 13-4·9-3·9-4·9-5 双源可达 / 覆盖率门禁四档一致 / 硬约束合规）全部通过；留项台账无未核销无归宿项。终态质量判定：**零 P0/P1 残留**（仅一项保守方向的 RLS 探测冗余观察项——owner 在 FORCE 下实际不绕过，多 skip 不误红，无需处理）。**本 Story 可进入 dev-story 实施。**

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
| 2026-10-25 | v1.1.0 | **循环文档审查 Round 1**（D1 五视角代码调研 + D2 三视角并行审查——一致性/正确性[规划锚点]/可行性[科学性推演]，发现 P1×5 + P2×14 + P3 批量，见「文档审查修复」表 R1-A~R1-N）：①R1-A DC-2 论证③改写（outbox cleanup 实为 30 天+零接线——「24h 清理」失实）；②R1-B save/search 双模式分派补全（CLI 检索可达性）；③R1-C AC-6.1 端到端锚→接线内省（消解与手动组装纪律互斥，五处同步）；④R1-D AC-2.3 构造前提（不设 ContextVar session + 127.0.0.1:1）；⑤R1-E AC-1 计数错账修正；⑥R1-F 事件构造块上移显式化（L148-155 位于 Redis save 之后）；⑦R1-G 构造点基准 14 处补全（3 遗漏文件）；⑧R1-H session_factory 端口名定谳；⑨R1-I CLI 帮助文本漂移锁联动；⑩R1-J RLS 探测补 rolsuper + 环境注记；⑪R1-K 索引四→五（previous_level——or_ 两臂索引化）；⑫R1-L DC-11 翻转 SINGLETON（5-4 DC-7 新增面政策，六处同步）；⑬R1-M 新增 OD-4（§9 命名映射 + arch-appendix DDL 分歧）+ or.md 章节编号修正；⑭R1-N 同号错位/场景归属/防呆注记/fixture 名/裕量算术/完成清单/P3 批量修正 |
| 2026-10-25 | v1.1.1 | **循环文档审查 Round 2**（D1 回归核查视角 + D2 组合交互推演双审查，发现 P1×1 + P2×1 + P3×10，6 项疑点证伪留痕，见「文档审查修复」表 #18-#20）：①R2-A（R1-M 自引入）OD-4 created_at 裁剪与 AC-4 列集互斥——定谳 created_at 保留非差异项（行创建审计列对齐 audit_log 先例，与 switch_timestamp 语义分工）；②R2-B（R1-F 自引入）「config load 440 已留日志」与钉死顺序矛盾——AC-2 Then 补 config load + DC-2/风险 #1 改写「440 零副作用干净拒绝，退出误报窗口」；③R2-C~L P3 批量：验收 8 处五文件计数/回归面清单补 3 文件（两处）/old_value .value 形态（降级静默丢失防呆）/残句/CLI 行定谳/第五依赖属性名 `self._isolation_switch_log_repository` 钉死 + _DummyResolver 补 resolve_optional（debate_session 先例）/AC-2.4 检索面钉死（直查表双过滤）/DC-11 补 session_factory 捕获注记/AC-2.3 精化 Redis 单门控/0.8 补 CLI 裁剪切分说明 |
| 2026-10-25 | v1.2.0 | **循环文档审查 Round 3**（单深度推演——18 场景三轴终推演/断言可满足性设置点核对/数学完备性/R2 修复深化，发现 P1×1 + P2×2 + P3×5，7 项证伪留痕，见「文档审查修复」表 #21-#24）：①R3-F1 StorageError 包装链无设置点（P1）——outbox/audit 模板均不包装 SQLAlchemy 异常，照抄实现下 AC-2.3 断言必红且红错位至 Task 4；四处补「except SQLAlchemyError → raise StorageError from exc」必做增量（redis L94 先例 PG 版）；②R3-F2 分页造数矛盾（5 条 vs 统一 ≥6 条）——独立造数明示 + 空页边界补测；③R3-F3 teardown 漏 reset_session（AC-2.3 前提被 ContextVar 泄漏静默破坏）——两处补 token 复位；④R3-F4~F8：直构造注入注记/242 context 形态钉死/created_at 映射形态三处定义/_audit_service 对称钉死/四维归集成分工。18 场景三轴推演 17✅ + AC-2.3（F1/F3 修复后可达） |
| 2026-10-25 | v1.2.1 | **循环文档审查 Round 4 纯验证轮**（锚点存续核验 + R3 修复传播 + 计数终验算 + 台账对照——**75 锚点 74 精确 + 1 偏移 + 0 失实，零台账错账，R2/R3 全部修复存续，全部计数验算通过**）：两项记录级留项随本轮清偿——①postgresql_adapter `from None` 行号偏移勘误（L53-59 → L60-64）；②修复表 #24 created_at 映射「三处定义」口径勘误（两处显式 + AC-4 列定义支撑）。验证声明：v1.2.0 声明存续性与精确性成立 |
| 2026-10-25 | v1.2.2 | **循环文档审查 Round 5 独立终审收敛**（不轻信自报——五节取证：周期闭合[4 提交无游离]/关键修复双向取证[10/10 属实行号精确]/独立快扫五维全过/留项台账零未核销/收敛判据判定）：**零 P0/P1 残留**，收敛声明入 Story（见「循环审查收敛声明」节）——周期累计 P1×7 + P2×17 + P3 批量 20+ + 13 项证伪留痕；**本 Story 可进入 dev-story 实施** |
| 2026-10-25 | v1.3.0 | **dev-story 实施完成**（Task 0-6 全勾选，Status → review）：Task 0 SDD 规范 + Gherkin 17 场景红阶段确认[17 failed/0 skipped] + deferred-work 三处登记；Task 1 实体[frozen+from_event+242 五场景，21 单测]；Task 2 端口+ORM+migration 015[RLS 四策略+FORCE 升降级对称]+仓储[双模式+SQLAlchemyError/**OSError** 包装链]+契约 11 维度+SINGLETON 注册；Task 3 五/六依赖+audit-first 插位[事件构造块上移]+AuditActionType 第 8 组+CLI isolation-logs+**14 处构造点全量同步**；Task 4 集成九场景+P95 双指标[写 ~7ms/检索 ~2ms]+成功率 20/20+RLS 非 superuser 拦截实证[UPDATE 0/DELETE 0]；Task 5 架构验证器 A/B/C；Task 6 收尾 18 场景[17 passed+1 RLS skip 属预期]。**两条 dev 阶段实施裁定**：①AC-6.2 CLI 形态经跨循环实验证伪（asyncio.run 新循环 vs ContextVar session 绑定冲突），改生产真实形态[fallback commit + superuser 清理]；②StorageError 包装链扩 OSError 面（asyncpg connect 阶段 ConnectionRefused 穿透 SQLAlchemy 包装——实测发现，故事 R3-F1 预判的 OperationalError 与实测形态不同） |

---

**故事版本/Story Version:** v1.2.2
**创建日期/Created:** 2026-10-25
**最后更新/Last Updated:** 2026-10-25
**更新说明/Description:**
- v1.0.0: 创建故事文件
- v1.0.1: 偏离声明同步动作对标审查修复（OD 登记/承接方链接/编号 OD-n 重命名）
- v1.0.2: agent_service.py 下沉触发条件可判定化（三信号 + VO 优先 + Epic 9 候选触发面）
- v1.1.0: 循环文档审查 Round 1（P1×5 + P2×14 + P3 批量——DC-2 论证事实修正/search 双模式/接线内省锚/AC-2.3 构造前提/AC-1 计数/事件构造上移/构造点 14 处/session_factory 定谳/漂移锁/rolsuper/索引五/DC-11 SINGLETON/OD-4/批量 P3）
- v1.1.1: 循环文档审查 Round 2（回归核查+组合交互——R1 修复自引入 P1×1[created_at 互斥]+P2×1[440 已留日志矛盾]+P3×10；6 项疑点证伪留痕）
- v1.2.0: 循环文档审查 Round 3（单深度推演——P1×1[StorageError 包装链断言可满足性断层]+P2×2[分页造数矛盾/reset_session 泄漏]+P3×5；18 场景三轴 17✅+AC-2.3 修复后可达；7 项证伪留痕）
- v1.2.1: 循环文档审查 Round 4 纯验证轮（75 锚点 74 精确+1 偏移+0 失实，零台账错账，全部修复存续，计数验算通过；两项记录级留项随轮清偿）
- v1.2.2: 循环文档审查 Round 5 独立终审收敛（五节取证全过，零 P0/P1 残留，收敛声明入 Story——可进入 dev-story）
