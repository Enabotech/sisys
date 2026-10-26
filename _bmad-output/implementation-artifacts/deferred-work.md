# Deferred Work

## 剩余项触发条件时间线（2026-10-10 具备度评定）

> 判定框架：决策触发（材料已具备只欠立项）/ 路线图触发（等特定 Story）/ 数据触发（等生产流量）。
> 锚点：Epic 1-4 done、Epic 5 未启动、V1 覆盖 Epic 1-8。A 类 7 项已于 2026-10-10 启动清偿（见各 RESOLVED 行）。

**决策触发型**：
- ~~SessionMiddleware 接线~~ → **RESOLVED 2026-10-10**（原最佳窗口「Epic 5 启动前」已抓住）
- ~~outbox fallback 扩展至 _persist_execution~~ → **RESOLVED 2026-10-10**；形态②本体 → 策略注记见下
- ~~saga roundtrip / reset_registry~~ → **RESOLVED 2026-10-10**
- ~~ABORTED 第三值~~ → **RESOLVED 2026-10-10**（业务启动指令即触发条件）
- 灰度推进/per-version 统计视图 → **触发 = 产品立项**（功能型非还债；建议 Epic 6 BLM 流程实施时评估——数据面 `list_by_tool` 已就绪，材料依赖度低，纯缺需求方）
- ~~lint-imports BROKEN~~ → **RESOLVED 2026-10-15**（D1 方案 A 落地，3-body 拍板：入口上移 src/entrypoints/ 组装层，interfaces 组合根引用清零；契约还原严格传导禁止 5 kept + CI 直接 blocking + pre-commit 钩子——「CI 长红」前提已消除；决策全记录见 proposals/proposal-d1-importlinter-governance.md，同日决策链含 B 落地后被撤销的过程）

**路线图触发型**：
- langgraph retry/timeout 字段 → **触发 = Story 5.10（CheckpointWithEvaluation）或 6.6（Checkpoint 摘要查看）实施**（epics :2016 规划在案、story 文件未创建——两处是 checkpoint_table/编排引擎行为的规划消费方，届时字段语义定稿）
- 工具熔断 → **触发 = Epic 5 sprint planning 重估归属**（epics 无直接对应 Story——FR-CP-07 是 Epic 11.3 成本熔断非工具执行域；建议 5.4/5.5 EIP 弹性隔离实施时评估挂点或独立小 Story）。**5-4 Task 0 评估（2026-10-22）：挂点不成立**——工具熔断（连续校验失败熔断）属 tool_execution 域装饰链语义，与 EIP 隔离等级无协议耦合；维持 deferred 归 Epic 5 sprint planning 重估/独立小 Story

**数据触发型**（共同链：Epic 5-8 交付 → V1 上线 → 真实失败流量 → 案例库积累；**上线前可提前部署观测脚本**——判据全可由 `EvolutionLogQuery.list_by_tool` + `get_by_natural_key` 量化）：
- fast-fail 尝试缩减 → 就绪判据：每签名 ≥30 次观测且 NEGATIVE_CASE_GUIDED 组样本充足（按 fix_strategy 分组恢复率对照——R8-32）｜上线后 +2~4 周
- fix_summary 进阶聚合 → 判据：高频签名 top-N occurrence 分布稳定｜+4 周
- 采样多样化/去重 → 判据：suggested_fix_excerpt 重复率可测量且偏高｜+2~4 周
- 签名分裂 / 389-LLM 签名细化 → 判据：抽样 stderr_excerpt 人工评估 over-merge/over-split｜+4 周（同窗）
- 真实修复能力基准 → 判据：生产 LLM 流量 + n≥30/组或序贯设计｜+2~4 周
- 向量检索/多案例加权 → 双触发：签名泛化不足实证 + L3 材料复用评估｜归入本组
- N+1（B8）→ 判据：单文档快照数 × 查询延迟超 SLA 的压力实证｜上线后观测

**不应做**（终局判定）：C11/C12（story 1-18b :266 spec 立法两态/不可观察——除非非阻塞执行新 Story 重立语义）；A5 构造期序列化校验（to_dict 探针已是正确失败位置，高频路径负收益）。

## Resolved in Story 1.10 (2026-05-07)

### Transaction Outbox Pattern — RESOLVED
**Detail:** AuditServiceImpl.record() directly calls event_publisher.publish() instead of writing to an outbox table within the same transaction. AuditOutboxModel exists but is not used.
**Original AC Violated:** AC-1 (Audit Logging)
**Resolution:** Implemented event_publisher integration. Transaction outbox within same transaction requires significant architectural change (Story 1.18a).

### Audit API Route Handler — RESOLVED
**Detail:** OpenAPI defines endpoints at /audit/* but no route handler file found at src/interfaces/api/audit.py.
**Original AC Violated:** AC-2, AC-3, AC-4
**Resolution:** Created src/interfaces/api/audit.py with 5 endpoints (GET /logs, GET /logs/{log_id}, POST /verify, GET /archive/status, POST /archive).

### WORM Manager Not Called During Archive — RESOLVED
**Detail:** AuditServiceImpl.archive() only updates the archived flag in PostgreSQL but never calls WORMManager.archive_object().
**Original AC Violated:** AC-4 (WORM Archival)
**Resolution:** Added worm_manager integration to archive() method. WORM archival now called when configured.

## Deferred from: code review of 1-18b-langgraph-agent-orchestration (2026-05-20)

- ~~`_runs` 字典无限增长（内存泄漏）~~ — **RESOLVED** (2026-05-25)：引入 OrderedDict + TTL(3600s) + FIFO(1000) 淘汰机制。`src/infrastructure/agent_orch/langgraph_engine.py`
- `LangGraphConfig` 配置字段从未被 `LangGraphEngine` 使用 — retry/timeout 配置为 MVP 预留，后续实现重试/超时逻辑时使用。`src/infrastructure/agent_orch/langgraph_engine.py:42`
- `get_graph_status` 对未知 ID 返回 FAILED 而非抛异常 — MVP 设计选择，spec 明确说"仅返回 COMPLETED 或 FAILED"。`src/infrastructure/agent_orch/langgraph_engine.py:102`
- 阻塞式执行导致 RUNNING/PENDING 不可观察 — spec 明确说"MVP 阻塞语义...RUNNING/PENDING 在本地模式下不可观察"。`src/infrastructure/agent_orch/langgraph_engine.py:76-77`
- 缺少 Graph 编译缓存机制 — spec 要求 graph_name→CompiledGraph 映射，MVP 图构建开销小，后续 Epic 扩展时优化。`src/infrastructure/agent_orch/langgraph_engine.py:104-123`

## Deferred from: code review of 20-8-workflow-agent-integration (2026-05-23)

- 可变字典引用 — frozen dataclass 的 `parameters`/`decision_result` 字段存储可变引用，调用方可在构造后修改。AgentDecided 同样有此问题。预存，非本 Story 引入。`src/domain/events/workflow_events.py:31`（**2026-10-10 具备度调查注记**：部分具备维持 deferred——修复形态已实证（`_serialize_value` 增 `isinstance(value, Mapping)` 分支 + `__post_init__` MappingProxyType 包装），但无任何「构造后篡改」真实场景~~；附带发现 saga_events init=False 形态 `from_dict(to_dict())` roundtrip 实测 TypeError，若启动本项须先修 base.py from_dict 联动~~（**2026-10-15 全量台账审查勘误**：该附带发现已被消解——2026-10-10 A 类清偿修了 base.py from_dict 的 init=False 过滤（本文件 20-8 节 L63 条目 RESOLVED），且 5-1 R1-F4 类型还原进一步增强；实测 `SagaStatusChanged.from_dict(to_dict())` roundtrip OK、saga_id 正确还原 UUID——本项启动的联动前提不复存在，维持 deferred 仅为「无真实篡改场景」单一理由）
- ~~flow_run_id 默认工厂误导~~ — **RESOLVED**（2026-10-10 技术债清偿）：生产 4 构造点（WorkflowSubmitted/RAGIndexed/AgentDecided×2——ReportGenerated 零构造点）全显式传参已实证——4 字段改 `field(kw_only=True)` 必填化，13 处测试无参构造补显式 id；漏传立即 TypeError 不再静默铸造。
- aggregate_type 可被覆盖 — `if not self.aggregate_type:` 条件允许调用方传入自定义值。所有事件都有此模式。预存。`src/domain/events/workflow_events.py:35-38`
- ~~DomainEvent 注册表无隔离~~ — **RESOLVED**（2026-10-10 技术债清偿）：`tests/unit/domain/events/conftest.py` autouse 快照/恢复 fixture（tests/conftest.py 会话 ContextVar 先例同款）；注记——import 期污染源（test_redis_event_bus_subscribe_fix 模块级 register 等 2 处）发生在 fixture 之前，需其文件内自理（附注已写入 conftest docstring）。
- 不可序列化参数延迟失败 — parameters 包含 Prefect 对象时仅在 `to_dict()` 时报错。预存问题。`src/domain/events/workflow_events.py:31`（**2026-10-10 具备度调查判定：不应做**——to_dict json.dumps 探针（4-5 清偿成果）已是正确失败位置且有绊线钉死；构造期校验是高频路径负收益）
- ~~【调查附带发现·2026-10-10】`SagaStatusChanged.from_dict(to_dict())` roundtrip 实测 TypeError~~ — **RESOLVED**（2026-10-10 A 类清偿）：`base.py` from_dict 核心字段按 target_class 的 `init=False` 声明过滤（init=False 成员保持类默认值）+ roundtrip 回归用例。
- ~~【调查附带发现·2026-10-10】`DomainEvent.reset_registry()` 零调用且具破坏性（清空后不自动恢复）~~ — **勘误 + 处置完毕**（2026-10-10）：「零调用」判定失实（src 零调用但**测试有 2 处消费方**——test_outbox_entity:189/test_event_outbox_adapter:112）；处置改为 docstring 破坏性语义警示 + 指引快照/恢复形态（tests/unit/domain/events/conftest.py），方法保留。
- ~~【A 类清偿附带发现·2026-10-10】alembic 全新库链挂在 002~~ — **RESOLVED 2026-10-15**（全量台账审查轮提前处置，一次性 PG 容器实证三炸点后修复 002 本体而非新增 fixup——fixup 救不了全新库（002 先炸），唯一有效修法是改 002。**红线豁免论证**：002 在任何全新库必然炸=从未被任何环境成功应用（修改零影响）+ alembic 无 checksum 机制 + 删除的 WITH CHECK 子句本就被 PG 拒绝（零语义变化），红线「禁改已合入 migration」的保护对象（已应用环境一致性）在本例为零。三处修正：①②两条 deny_delete policy 去 WITH CHECK（DELETE policy 仅允许 USING）；③update_status policy 的 old.status/NEW.status 改裸列名（PG policy 单行作用域不支持 OLD/NEW 限定引用——USING 裸列名=旧行、WITH CHECK 裸列名=新行；精确状态迁移由应用层 InvalidStateTransitionError 守卫承担，RLS 保底「非终态行可更新+新值合法集」）。实证：全新库 001→018 全链跑通 + 8 policy 建成 + downgrade/upgrade 双向可重放）。 **【2026-10-16 migration 链重构】**18→14 文件：008 吸收 009（3 索引）+010（validity 列+4 索引）；011 吸收 014（GIN）；014 吸收 018（ABORTED CHECK 直接建表）；011-017 重编号为 009-014——消除 4 个纯补丁型 migration（同表二次修补合并为主题完整交付）。Schema 等价性 diff 实证：新旧链 pg_dump 仅差 validity 列 COMMENT（合并新增注释，非结构差异）+ 空行；downgrade 014→base 全链可逆 + upgrade 可重放。同款红线豁免：全持久环境（dev 5432）无 alembic_version（链零注册），重构零影响。

## Deferred from: code review of 2-6-document-version-snapshot (2026-08-02)

- ~~缺少性能基准测试（P95 指标未验证）~~ — **半数 RESOLVED**（2026-08-03 commit 8bfcc472 已交付 domain 口径 5 项基准——值对象构造/元数据 diff/内容 diff 等；**2026-10-10 技术债清偿补齐残余**：AC-1 create_snapshot 端到端 P95<100ms 基准（4-6/4-7 基准先例同款分级断言形态）。
- ~~缺少并发版本控制测试（≥10 并发操作）~~ — **RESOLVED**（台账过时勘误）：`tests/integration/test_integration_document_version_concurrent.py:195` 的 `test_10_concurrent_saves_only_one_succeeds`（2026-08-03 commit 8bfcc472 交付）精确覆盖 AC-3「10 并发只有 1 个成功」+ 串行 10 次 + 5 文档并发首快照三用例——登记时点（2026-08-02）早于交付次日。
- `list_versions`/`get_version` N+1 查询问题 — 先查 documents 验证租户，再查 snapshots，可用 JOIN 优化。预存，当前数据量小，性能影响可接受。（**2026-10-10 具备度调查注记**：实为固定 2 查询非经典 N+1，JOIN 等价改写回归面 32 处——机会性优化维持 deferred）
- ~~内联 import 散落问题~~ — **RESOLVED**（2026-10-10 技术债清偿）：「规避循环依赖」论据经调查失实（被导入全为 domain 层，六边形契约下结构不可能循环）——6 个内联块全部上提模块顶部并与 TYPE_CHECKING 块去重，12 测试全绿。

- ~~InMemoryRoutingDecisionLogRepository 非线程安全~~ — **RESOLVED** (2026-05-25)：引入 asyncio.Lock + max_size(1000) + TTL(24h) 淘汰。`src/infrastructure/messaging/inmemory_routing_decision_log_repository.py`

## Deferred from: code review of 4-6-tool-version-management (2026-10-07)

- ~~lint-imports「Interfaces layer must not depend on infrastructure」broken~~ — **RESOLVED 2026-10-15**（与时间线节同项：D1 方案 A 落地——app/ocr_cli/agent_cli 三入口上移 src/entrypoints/，本条所记两条链的入口文件已不在 interfaces 层，传导链消失；契约 5 kept + CI blocking。决策记录见 proposals/proposal-d1-importlinter-governance.md）
- ~~根 `.env.example` 从未被 git 跟踪（git ls-files 仅 deploy/delivery 组件级样例）~~ — **RESOLVED**（2026-10-10 技术债清偿）：根 `.env.example` 创建——全仓 `os.getenv` 两轮 grep 提取 163 键按 14 域分组收录（字面默认值与各 from_env 一致；数据源 URL/TTL 类默认在 config/datasources 模块的键留空注记指引；敏感键留空）；`TOOL_VERSION_MAX_RETAINED`/`SANDBOX_*` 同步收录。

## Deferred from: Story 4-7 Validation Feedback 闭环 (2026-10-09)

- ~~outbox 形态②「业务 session 异常回滚连带丢失已 flush 事件」（session_context rollback 连带）~~ — **部分 RESOLVED**（2026-10-10 A 类清偿）：fallback 扩展至 `_persist_execution` 已落地（`PostgreSQLToolExecutionRepository` 注入 session_factory + 无请求 session 独立写入——outbox 同构，后台路径 FAILED 聚合行不再 RuntimeError 丢失）。**形态②本体（有 session 且回滚连带）策略注记**：SessionMiddleware 接线后 HTTP 失败路径的 FAILED 持久化随主事务回滚——若需「失败观测在回滚后存活」，须决策「失败路径写入一律独立事务」（放弃同事务原子性换取观测存活）——策略级取舍待真实失败观测需求驱动，非材料缺失。
- ~~SessionMiddleware 生产接线（独立技术债）~~ — **RESOLVED**（2026-10-10 A 类清偿）：`create_app()` 接线落地（lazy `_request_session_factory` 经组合根 SINGLETON 解析；SessionMiddleware 内层/ExceptionContextMiddleware 外层——Starlette insert(0) 语义核验）；接线冒烟 4 用例（中间件链 200/ContextVar reset 无泄漏/层序断言/factory 可解析）；既有 3 个 create_app 测试消费方均零真实请求、零影响；`strategic_archive_service:269` 的事务原子性承诺自此成立。
- ~~中止遥测 ABORTED 第三值（R3-3）~~ — **RESOLVED**（2026-10-10 A 类清偿，重开 R3-3 中止半边）：FeedbackOutcome 加 ABORTED（ErrorCase 域收窄排除）/ EvolutionLogEntry 不变量分支化（ABORTED count∈[0,3]、条数≤count）/ migration 018（CHECK swap，行为验证①②③④全过）/ `_finish_aborted` 写中止遥测行（不回填案例、不发事件）/ 短路条件收窄为终态行（ABORTED 重放全量重跑、upsert 覆盖——#17② 直传维持零终态）；**附带暴露并修复 BDD AC-2.18 构造缺陷**（code_outputs 队列被触发段消费、实际测「触发前 201 直传」——零观测立法下两路径同绿掩盖走偏 8 个月，ABORTED 观测面使路径可区分；改状态化 side_effect 构造）。
- fast-fail 尝试缩减半边（R8-2） — 负样本信息注入已交付（NEGATIVE_CASE_GUIDED）；attempt 上限缩减待真实负样本效用对照数据（R8-32）落地后采纳。
- 修复循环采样多样化/生成相似度去重（R8-17） — V1 指令级强度 + suggested_fix_excerpt 指涉对象已就位；机制性兜底待真实失败率数据。
- fix_summary 进阶聚合（R8-20） — V1 为最近一次成功覆写；跨轨迹归纳/多数次验证后覆写待案例库规模支撑。
- 签名分裂低频形态（R8-30） — dict/set repr 键序不稳定、异常链层数漂移；随真实语料评估。
- 真实修复能力观察基准（R8-31/R8-32） — mock 基准度量编排机制正确性；真实观测需更大样本/序贯设计 + 按 fix_strategy 分组对照统计。
- 多案例加权检索与向量相似检索（L3 Qdrant） — V1 精确签名匹配；签名泛化不足时再立项。
- 工具熔断（or.md 四.7.(3)） — 建议挂 Story 5.x Agent 弹性隔离；ToolExecutionQuery.state 过滤材料已齐备（纯范围决策）。（**2026-10-15 全量台账审查去重注记**：与时间线节 L18 同项重复登记——触发「Epic 5 sprint planning 重估」已到期（Epic 5 已启动、5.1 done），评估窗口=5.2+ create-story 时随行；主登记位定为时间线节 L18）
- 自动灰度推进与 per-version 统计视图 — 演进日志数据面已就绪（tool_evolution_logs + list_by_tool）。
- FAIL_FAST 同波取消优化 — 纯算力节约可选优化（CONTINUE/SKIP 场景本不该取消，禁做成无条件）。
- ~~mid-attempt 389-Schema 新 violations 进跨尝试反馈（代码审查 CR-R1-22）~~ — **RESOLVED**（2026-10-10 技术债清偿）：具备度调查证「演进日志 schema 联动」论据在 DB 层失实（fix_attempts 为 JSONB，`_attempt_from_dict` 全 `.get()` 缺省读，旧行向后兼容零迁移）——FixAttempt 加 `violations_excerpt` 字段（条数≤3/message≤200 截断）+ service mid-attempt 捕获 + prior_summaries/render_prior_attempts 渲染。
- ~~duration_sec 计量点覆盖终态副作用（代码审查 CR-R1-23）~~ — **RESOLVED**（2026-10-10 技术债清偿）：`_finish_*` 签名族改收 `start_time`、在案例回填之后自算——duration 覆盖回填段；物理边界注记（日志行自身写库与事件发布时长不可计入本行）。
- ~~fix_strategy 格④⑤ 运行时可观测载体（代码审查 CR-R1-24）~~ — **RESOLVED**（2026-10-10 技术债清偿）：具备度调查证「PG enum 迁移」论据失实（fix_strategy 无列无 enum 类型，JSONB 内字符串前向兼容）——FixStrategy 升格五值（PURE_LLM_NO_RECIPE/PURE_LLM_COLLISION），格③④⑤演进日志可区分；穷举断言×2 + 单测×2 + BDD 三联动位同步。
- 389-LLM 子路径签名输入细化（代码审查 CR-R1-25） — 现用外层 389 消息（同工具全部 389-LLM 失败收敛一个签名桶）；仅影响 occurrence 聚合粒度，随真实语料评估。
- 引擎聚合 id 的 session_id 回退语义（代码审查 CR-R1-26/D-P3a） — `extract_schema_execution_id` 三级优先（extensions>session_id>新铸）使直连+UUID session_id 时聚合 id=session_id 非「兜底新铸」字面；生产全路径经链入口注入不受影响，`test_execution_id_same_source.py` 断言④已按优先级链钉死。
- ~~VFD 触发谓词提为端口方法（代码审查 CR-R1-27/D-P3b）~~ — **RESOLVED**（2026-10-10 技术债清偿）：端口 Protocol 增 staticmethod 声明 + VFD 改经 `self._feedback.should_enter_feedback_loop` 调用（删内联 import）+ 契约测试 REQUIRED_METHODS 增项；装饰器测试替身挂真实谓词（AsyncMock 属性恒真陷阱注记）。
- ~~`validation_feedback_service` 端口与 `tool_execution_service` 双链构造注记（代码审查 CR-R1-28/M4）~~ — **RESOLVED**（2026-10-10 技术债清偿）：`build_validation_feedback_service` 改一行委托 `build_tool_execution_chain(...).service`——service 构造唯一 SSOT 在链工厂（消除逐字重复；双链实例形态为 SCOPED 既有语义维持注记）。
- `_finish_recovered` 读-后-记 TOCTOU（代码审查 CR-R1-29） — fix_summary 快照与 record_case 间并发写窗口极小；计数由仓储 merge 保护。
- ~~后台发布任务 set 跨事件循环滞留（代码审查 CR-R3-4）~~ — **RESOLVED**（2026-10-10 技术债清偿）：统一治理落地——`drain_schema_events` 核心抽参数化 `drain_background_tasks(tasks, timeout, op_name)` 共享 helper（stale task 过滤/跨 loop 丢弃/超时取消原样保留），`drain_feedback_events` 薄壳复用，`composition_root.shutdown()` 增第二挂点。
- 【UDMR 审计发现·2026-10-11】UDMR 带外→在环消费方接线 — Story 1-17 交付的 RoutingDecided 事件无 LLM 调用消费方（CostMetricsListener 仅做成本估算）；**F1 已完成配置层 SSOT 接线**（组合根 UDMR 云端配置优先 + F2 激活 handler），但路由决策仍为静态（单指针——StaticUdmrPolicy.route 忽略 UDMRTask.preferred_model/allowed_models），待 Epic 11 Story 11.1 L2 四因子评分实现真正的多模型动态路由。
- 【UDMR 审计发现·2026-10-11】CloudHealthChecker HEAD 探测 405 问题 — 多数 LLM 网关对 HEAD 返回 405（1-17 review 已 defer）；**F6 已修正超时 600→30s**（对齐 1-17 AC-5），探测方案从 HEAD 换为 GET /models 待 Epic 11 处理。
- 【路线 B 决策·2026-10-13】china-nbs 数据链 B1 已闭环（3-body 裁定：crawler 保持纯文件采集层、解析归 SISYS——业界采集/解析分离 + raw-first 对齐，Epic 2 解析栈复用） — **B1 交付**：crawler API files 明细（stored_path 经 StoragePipeline 写回 item → task_runner → CrawlTaskResponse.files）+ ChinaNBSAdapter 契约从 result.pages（从未被 crawler 实现过——mock 双侧同错掩盖 8 个月）改为文件清单 + 端到端实证（fetch → HttpCrawlerClient → 真实爬取 stats.gov.cn 13 文件 13/13 落盘，page_title/link_text 公告级元数据完整）。
- 【路线 B 决策·2026-10-13】**B2 事件驱动摄取 + 持续数据供给（Epic 6 实施时评估，勿提前接线）** — ①摄取桥：crawl 产物（files[].stored_path）注册进文档管道（复用 Epic 2 解析：2-2a/b 解析/2-4 表格语义/2-8 分块），触发条件 = Epic 6 首个 Skills 消费场景定型（消费形态决定注册粒度与解析深度）；②NotificationPipeline 从 hardcode ConsolePublisher 改接 RabbitMQEventBus（crawler 侧 rabbitmq_publisher.py 已有未接线）→ 爬取完成事件驱动摄取；③定时调度（统计数据月度发布节奏，heartbeat_scheduler 或 Prefect）；④增量采集/去重（当前每次全量重爬，TTL 86400s 仅 Resolver 层缓存）。关联遗留：spider 四个契约谎言字段（max_files/max_file_size_mb/url_include/url_exclude 标注 NOTE 未实现但 API 已暴露——max_files 传 3 被静默忽略实证）；HttpCrawlerClient.submit_task 不支持 use_browser 透传（WAF 绕行模式 SISYS 侧不可达）+ chromium 二进制漂移 1223≠1228 待 `playwright install chromium`。
- 【数据源可用性核查·2026-10-12】Epic 6 市场洞察前数据源可用性清单 — **A 组 6 源全部 API 可达**（worldbank 200 / imf 200 / eurostat 200 / ipcc 200 / comtrade 200；sec-edgar 403 需 User-Agent 头适配器应已携带，待真实调用验证）；**B 组 4 源缺 Key**（uspto/newsapi/epo-ops/google-patents）；~~tavily~~ **已配置**（2026-10-12——API 探活 200 + 适配器已注册，key 仅在本地 .env 不入库）；~~china-nbs crawler 未部署~~ **已启动 + 端到端实证**（2026-10-12——`plugins/crawler` 自研插件；修复三重缺陷：①HttpCrawlerClient API 路径 `/api/v1/*`→`/*` ②CrawlerProcess 后台线程运行违反 Scrapy 主线程契约（signal 安装 ValueError + uvicorn loop 冲突）→ 重构为 task_runner 子进程隔离 ③pydispatcher 弱引用 lambda 被 GC 静默断连致 files_crawled 恒 0 → 具名函数强引用；实证 stats.gov.cn 真实爬取 13 文件/56MB + 连续任务不崩；遗留注记：stats.gov.cn WAF 间歇性 JS 挑战壳页，Playwright browser 模式可绕但 chromium 二进制版本漂移 1223≠1228 待 `playwright install`）。Epic 6 前置：剩余 4 源按需申请 Key。

## Deferred from: 技术债扫描——已实现未接线组件普查 (2026-10-12)

> Epic 4 回顾行动项 7.1-3 执行。基线 main@cda34bf2，生产路径 = create_app() + sisys-ocr CLI + bootstrap() handler_names。**核心结论：生产活代码约 50/166 端口（三分之一）**。

### 入口面缺口（最高优先）
- create_app() 仅挂 7 路由，5 个已实现 router 未挂载：**auth（登录端点缺失——最大单点风险）**、audit（1.10 交付）、crawler、monitoring（/metrics）、equilibrium_security — 触发=V1 API 可用性立项时统一接线（auth 建议先行）
- exception_metrics 端口零消费 + register_exception_handlers(app) 未传 metrics — 异常遥测静默关闭；接线成本一行
- RabbitMQConsumer/RabbitMQEventListener/EventBusFactory 零接线 — reliable 通道只发不收；触发=首个消费方 Story

### 事件 handler 未激活（注册≠激活——UDMR F2 同款）
- AutoTriggerHandler 有 register_handlers 但不在 handler_names — Story 1.14 trigger→route→execute 管线三 handler + heartbeat_scheduler + session_namespace_manager 整体生产休眠；触发=Epic 5 Agent 编排
- MemoryChangedHandler（1.15a）未注册端口零引用；ToolExecutedEventHandler（4.1a AC-5 工具统计投影）零引用 — Tool.reliability_score 生产永不更新
- CacheInvalidationHandler 构造期自注册+端口惰性实例化=永不注册（结构性陷阱）— Story 3-9 缓存失效失效

### 端口链路休眠（实现完整、无入口）
- **Epic 4 工具执行链零入口**：tool_execution_service/tool_execution_engine/validation_feedback_service/StrategicAnalysisUseCase/run_tool_chain_use_case/red_blue_debate_service/sandbox 链/12 个 data_source_* 适配器/schema_validation_record_repository — 触发=Epic 5；sandbox_session_reaper 接线时须补启动挂点
- 等保三级合规 11 端口 + permission/role_repo/password_validation/token_blacklist 休眠（**token_blacklist 死=JWT 吊销不存在**）— 触发=equilibrium_security/auth 路由接线
- unified_storage + L0/memory 子系统 12 端口休眠 — 触发=Epic 6
- semantic_cache_middleware/cache_metrics/semantic_cache 休眠 — Story 3-9 缓存整体未运行；触发=检索性能需求
- orchestration_service/workflow_engine/agent_engine 休眠 — document_tasks.py 随之死链；触发=Epic 5
- session_storage 端口 + RedisSessionStorage 休眠（2026-10-12 普查遗漏项，Story 5-1 Task 0 补登记）— Story 5.1 Agent 状态持久化用新建 AgentRepository（决策 DC-1：session_id 主键语义不匹配 Agent 聚合仓储，且其吞连接异常的优雅降级语义与状态持久化确定性冲突）；触发=Story 5.3（会话状态消费方）。**5-3 Task 0 处置（2026-10-20）：续期**——触发移至 5-4+/多轮会话需求 Story（5-3 DC-9：MVP 单次 CLI 调用内会话闭合，无跨调用状态需求；九步可选步「持久化沙箱内存变量」同批续期见 5-3 D-6）。**5-4 Task 0 处置（2026-10-22）：再续期**——5-4 隔离状态（IsolationState）是 EIP 协议状态非会话状态（5-4 DC-1：独立聚合 + 独立键空间 sisys:isolation:*，不经 session_storage）；触发移至真正的多轮会话需求 Story
- uow_factory/saga_repository 零 resolve — 事务子系统待首个真实事务用例
- compressor/text_extractor/context_compressor/persistent_note_taker/compression_quality_evaluator — 检索-压缩循环待接线

### 配置类零消费
- AutoExecuteConfig/AutoTriggerConfig/MetricsConfig from_env 零调用；MemoryConfig 零生产 from_env — 随对应链路接线或确认废弃

### 部署面注记
- deploy/app/docker-compose.yml 无 sisys-api 服务（create_app 零部署引用）— V1 上线前需补

## Deferred from: Epic 4 专题回顾——数据源可用性 (2026-10-13)

> 全量取证与裁定见 `epic-4-retro-2026-10-13-datasource.md`。核心结论：tavily 配置后零 Key 全坍塌 Skill 数已降为 0，Epic 5/6 均不阻塞。

- 【行动项#1·3-body】三源 Key 申请（~~EPO OPS~~ **已配置 2026-10-14** → uspto → GCP） — EPO OPS 部分闭环：Key 配置后首跑暴露两处 R7 待锚定契约并已修复实证（①token 端点 grant_type 走 form body 而非 query params——实测 400 vs 200；②检索端点切 search/biblio 变体 + 响应解析按真实 JSON 化 XML 结构 ops:world-patent-data→ops:biblio-search→exchange-documents 重写，含单元素 dict 折叠容错与 YYYYMMDD→ISO 归一化）——`test_pa_chinese_applicant_real_patents` 真实端点转绿（pa="华为" 命中 110760 条）；uspto/GCP 仍待申请。google-patents 外部前置显式标注：大陆部署需代理/专线（bigquery.googleapis.com GFW 确定性封锁，配齐凭据连接层仍 411）
- ~~【行动项#2·P0】cninfo 巨潮资讯接入立项（Epic 6 Story 6.2 前置）~~ — **RESOLVED**（2026-10-13 D-10 落地：Story 4-1f Task 10 增量交付——CninfoAdapter 免 key A 组无条件注册 + 两段式公告检索 + 真实端点集成实测 2 passed；competitor-analysis 8 源（市场份额 4 源）；适配器池 13 终态；PDF 内容下载拆期归 B2 摄取桥）
- 【行动项#3】comtrade 零 Skill 引用（4-1f「受益 Skill 声明重分配」遗漏面） — ansoff-matrix/space-matrix 等行业量化 Skill 补声明 + 四方联动断言；触发= 下一数据源域 Story 或独立微 Story
- 【行动项#4】fetch_many 执行前预检门 — 「声明源 ∩ 已注册适配器」交集空时输出数据缺口报告（标注休眠源+激活条件）而非 503 硬失败；同步修正 vrio SKILL.md:205「Key 敏感降级」话术与机制落差（话术声称休眠保留、机制实际全败硬失败）
- ~~【行动项#5】sec-edgar UA 头真实调用验证~~ — **RESOLVED 2026-10-15**（四层实证：curl 直访 200 / httpx 裸测 200 / 适配器 fetch 全链 200+10.5KB / 集成测试 2 passed（search 模式 filings 非空 + XBRL 模式 Revenues 时序非空）——UA_HEADER「sisys-tools/1.0 (contact@sisys.local)」Fair Access 格式正确且真实生效；当日曾现 TimeoutError 波动（Fair Access 临时限流），复跑即恢复——外部端点波动属性非代码缺陷，重跑即绿）
- 【行动项#6】tavily 单点集中依赖 — 10/16 Skill 依赖（全部降级路径经它），配额耗尽/可达性劣化将波及全部外部数据 Skills；触发条件= tavily 月度配额 >80% 或连续探活失败 2 次
- 【裁定记录】newsapi 实质非必配 — 8 个引用 Skill 全有 A 组源或 tavily 伴随；Key 申请优先级降至最低（大陆普遍不可达 + 覆盖面被 tavily 含盖）
- 【裁定记录】专利域维持三源计划（3-body 2026-10-13 拍板） — B/C 组条件注册设计天然支撑休眠语义（Key 未到位零代码成本）；大陆部署专利域可得上限= EPO OPS（含 CN 数据）+ 代理侧 uspto/google-patents；中国专利无免费公开 API 为显式能力边界

## Deferred from: code review of 5-1-ceo-agent-instantiation-mvp Round 1 (2026-10-14)

> 审查台账见 Story 5-1「Review Findings」节（5 并行视角调研 + C3 三视角评审，P0×4/P1×4 已当轮修复，以下为留项分流）。

- ~~【D1·P1】import-linter `interfaces-no-infrastructure` 契约 BROKEN~~ — **RESOLVED**（2026-10-15 **方案 A** 落地，3-body 拍板；同日决策链：B 早间先行落地（契约改 `allow_indirect_imports = True` + CI 观察期）后被用户撤销——观察期流程价值低 + A 实测改动面可控（deploy 零引用/src 零反向依赖/测试真实引用 12 文件），改由 A 终态实施：入口上移 `src/entrypoints/` 组装层（agent_cli/ocr_cli/api_app 三文件 git mv，interfaces 组合根引用清零）→ 契约还原**严格传导禁止**（5 kept；注入直接违规仍捕获）→ CI 直接 blocking + pre-commit 钩子；Epic 7 集中 CLI 时入口在 entrypoints 层内合并即可；决策全记录见 proposals/proposal-d1-importlinter-governance.md）
- ~~【D2·P2】EPO `_parse_biblio_document` 静默空记录 + `_fail` 消息层名错位~~ — **RESOLVED**（2026-10-14 留项清偿轮：`_fail(missing_layer, actual)` 消息点名真实缺失层 + NoReturn 注解 + 无 bibliographic-data 文档跳过（返回 None 过滤）；新增层名准确化与毒文档跳过两用例；EPO 全消费方回归绿——原触发器「4-1f 跟进」因 4-1f 已 done 悬空，改由清偿轮直接处置）
- 【D8·P3·范围收窄】存量技术债汇总 — **2026-10-15 D8 清偿轮已清偿**：①ocr_cli 6 处 `raise ValueError` → ValidationError(201)（含调用方 except 与 8 测试断言同步）；②circuit_breaker 3 处 → ConfigurationError(101)；③3 文件 `# noqa` 死注释清除（saga_status F401 经 `__all__` 消除/inmemory_event_listener BLE001/otel_config PLW0603×3+SLF001——均属未启用规则，删除零行为影响；src 层 noqa/pylint 现零命中）；④`RedisSnapshotStore.save` pipeline 原子化（MULTI/EXEC，修法平移 5-1 R1-F3，测试替身同款改造）；⑤存量 FakeRedis 未关闭 13 用例 fixture 化（teardown aclose）。**甄别剔除**：strategic_archive 2 处 ValueError 属 Pydantic validator 契约合法形态（validator 抛 ValueError 才被收集为 422，改造反而破坏校验流）；schema_validation_record_repository 1 处为注释提及非代码。**剩余归专项**：~41 处裸 HTTPException（9 个 API 路由文件，需逐处语义判断+异常域扩充+ExceptionHandlers 注册+全路由回归）— **已立项 Story 91-1**（2026-10-15，91-1-api-auth-unification：立项调研修正——26 处 raise 实测全为 HTTP_401 认证守卫且为同段 get_current_user 依赖的 9 文件复制粘贴；AuthenticationError→401 映射与 WWW-Authenticate header 先例已完备，改造为抽取共享依赖+单点接线）

## Deferred from: code review of 5-1-ceo-agent-instantiation-mvp Round 2/3 (2026-10-14)

- 【D11·P3·范围收窄至①】outbox 毒消息终态机制 — 2026-10-14 清偿轮清偿②④⑤⑥；**2026-10-15 D11-a 微 Story 清偿③+巡检面**：③DLQ dequeue 毒隔离（队头畸形 payload 标 error 终态+action_taken 记毒因+继续取下一条——修「先行改标+from_dict 裸调致毒条目每轮重炸队头」）+ `count_by_status()` 按状态分组巡检方法（pending 滞留/failed 存量/archived 终态一查可见）。**剩余①归 D11-b 专项**：超限行 archived 终态迁移 + requeue 入口 + archived→pending 状态机迁移评审——设计方案见 proposals/proposal-d11-outbox-dead-letter.md（PG 环境前置：本地 5433 认证修复）——**已立项 Story 91-2**（2026-10-15，91-2-outbox-dead-letter-termination）——**已核销于 Story 91-2（2026-10-15 实施完成）**
- 【D12·P2】wheel 形态 configs/ 分发缺口 — pyproject packages=[{include="src"}] 不含 configs/（非 Python 包），wheel/pip 安装形态 agent CLI 必现 440；源码树/Docker/k8s 三形态自洽，CI 零 wheel 构建环节无消费方 — 核销触发：发布/打包专项立项 或 首个 wheel 消费方出现（README 已声明部署形态限定）
- 【D13·P2】CLI 全量 bootstrap 启动开销 — 单次调用墙钟 10.4s（bootstrap 7.7s≈157 端口注册 + litellm import 出网拉取价目表 + BGE tokenizer 加载；实际用例 ~2.5ms；2026-10-14 本机实测）——agent_cli 是首个全量付费的 Redis CLI，组合根瘦身/lazy 化属架构级决策；短期缓解已落地（2026-10-14）：.env.example 增 LITELLM_LOCAL_MODEL_COST_MAP=1 样例项 — 核销触发：5.3 批量实例化消费前。**5-3 Task 0 处置（2026-10-20）：知悉不处置**——run-task 单次调用阻塞语义下无批量消费面（非阻断）；组合根瘦身属架构级决策，登记保持
- 【D11 补强】超限毒行恢复唯一路径=运维 SQL 重置（mark_pending >=max 硬抛 + 无终态迁移）；SELECT 过滤后超限行零日志为监控盲区（专项需提供 pending 滞留巡检面）；另 `_mark_failed_entity`/`AuditOutboxModel.mark_failed` 两处 error_message VARCHAR(1000) 未截断潜伏面同批收敛
- 【D6·P3·已核销·索引行】AgentConfig 直构造守卫残余（主登记位 = 5-1 story 留项台账 D6 条）→ **核销于 Story 5.4（2026-10-22）Task 1 循环 E**：default_isolation_level 枚举化 + 标量类型守卫统一 440 分码；空白串拦截语义核实已存在钉子锁定（详见 5-4 story D6 处置行）
- 【D7·P3·已核销·索引行】SINGLETON 用例捕获 SCOPED 仓储 captive dependency 评估（主登记位 = 5-1 story 留项台账 D7 条）→ **核销于 Story 5.4（2026-10-22）Task 0 评估 + DC-7**：isolation_repository SINGLETON 新增面从源头避免 + 存量维持注记 + 验证器 D lifetime 架构锚（详见 5-4 story D7 处置行）
- 【部署面注记补充】outbox 无 poller 宿主叠加 CLI 路径：sisys-agent 产出的 AgentInstantiated RELIABLE 事件在 event_outbox 持续 pending 累积（sisys-api 服务缺失既有登记）——短期 ops 可用 SQL 巡检 pending 数。**5-2 R1 追记（2026-10-19，编号锚 R1-DF2）**：AgentProfileLoaded（5-2 交付，reliable 单通道同族）同形态累积；且发布失败（outbox 写失败/raise）在 CLI 路径仅 stderr 日志 + exit 0，无程序化可观测信号（exit 码/输出标记均无）——观测面增强（发布失败退码化/结果对象标记/指标计数）与 poller 宿主同归 — 核销触发：5.3 首个事件消费 Story 立项时一并定夺。**5-3 Task 0 处置（2026-10-20）：登记保持**——5-3 是 AgentDecided 的生产方（confidence 真实化写入）而非任何事件的消费方，无事件订阅面，锚位顺延至 5.7 Phoenix 追踪立项

## Deferred from: Story 5-2 Task 0 链路普查 (2026-10-19)

> Story 5-2（Agent 身份档案加载）Task 0 链路接线断言清单 L8 普查新发现——L7（心跳链路）与 L8（系统级记忆）deferred 保持既有登记（2026-10-13 普查段 + 5-1 Task 0 补登记段），本段为 L8 新增观察项。

- 【L8·观察项·P2】组合根休眠记忆端口 impl 路径失效（激活时必炸）— `l0_storage`（组合根 L268-276）impl 字符串 `"src.infrastructure.storage.file_memory_adapter.FileMemoryAdapter"` 与 `memory_file_storage`（组合根 L1111-1119）impl 字符串 `"src.infrastructure.storage.memory_file_storage.MemoryFileStorage"` 均指向不存在的模块路径——实际实现在 `src/infrastructure/storage/fs/` 下（`fs/file_memory_adapter.py`、`fs/memory_file_storage.py`），模块路径缺 `fs` 层级。两端口当前零 resolve 消费（休眠），字符串 impl 延迟导入不触发即不炸；首个消费方 resolve 时 ImportError。触发=记忆链路激活 Story（Story 5-2 的 MEMORY.md 为静态种子，不走系统级动态合并——DC-6/D-3）

## Deferred from: code review of 5-2-agent-identity-profile-loading Round 1 (2026-10-19)

> 审查台账见 Story 5-2「Review Findings」节（4 并行视角调研 + C3 双评审员评审，零 P0/P1，4 P2 + 10 P3；8 项落码修复 + 2 项 P2 改判 + 1 项 P3 登记 deferred + 3 项维持——改判裁定见该节）。本段为改判/登记留项分流。

- 【R1-DF1·P2】InMemorySkillLoader L1 缓存表头幽灵条目（4-1a 遗留，非 5-2 引入）— `src/application/skills/loader.py` `_init_metadata_cache`（L126-141 附近）的行跳过条件只拦 `#`/`---`/空行，TOOLS.md 表头行 `| slug | tool_name | ... |` 被 `_TABLE_ROW_PATTERN` 解析为数据条目——实测 L1 缓存 24 条（manifest 23 + ghost `slug='slug'`，ghost status='active'）；`match_by_tag`/`match_by_capability` 等直接遍历缓存的接口会命中幽灵（当前生产消费方为零——grep 实证仅契约测试/单测引用）。5-2 的 SkillSelector 经 `get_all_slugs()` 静态清单枚举天然免疫（tools_l1==23 不受影响）。修复形态：`_init_metadata_cache` 增表头行过滤（如 `cells[0] == 'slug'` 跳过）——属 4-1a 交付资产域（回归面含 4-1a 套件），审查周期不动他 Story 文件 — 核销触发：下次 Skills 资产演进（SKILL.md 增删/TOOLS.md 改版）或 5.9 漂移检测立项（ACTIVE 基线数消费该面）
- 【R1-DF3·P3】AC-5 性能门禁计时口径不含生产发布链路 — 集成/验收 P95<500ms 计时注入 `InMemoryEventBus`（内存发布），生产 CLI 路径发布经 DualChannelEventBus→PG outbox 写入（网络 RTT + 失败重试面），口径差余量约 25 倍（实测 P95 ~10ms 级）大概率覆盖但无证据背书 — 核销触发：5.3 批量消费前补含真实发布链路的计时（或明示口径差）。**5-3 Task 0 处置（2026-10-20）：本 Story 处置**——Task 7 集成场景⑤真实发布链路单次时序验证（resolve 真实 event_publisher/DualChannelEventBus + PG event_outbox 落行断言，PG 门控动态 skip）+ P95 主口径的发布面口径差声明随测试 docstring 落盘（场景①②为内存/替身发布面）；完整生产口径计时（真实 LLM+真实发布 P95 采样）续期至部署验证
- 【R3-DF1·P3】L1 组装失败语义契约沉默（387 路径根因不可观测）— `src/application/skills/loader.py` L111-124 对 TOOLS.md 缺失/读取 OSError 仅记日志后**降级回退空 L1 索引**；skill_manifest（23 slug 静态清单）与空索引漂移时 `load_metadata` 抛 SkillNotFoundError(387) 穿透 SkillSelector/use_case 到 CLI `[EXCEPTION_387]` exit 1——运维只见 "Skill not found" 无 TOOLS.md 根因指向（4-1a 的吞错降级行为因 5-2 首次接线成为承载面）。R3-F2 已补 use_case docstring Raises 契约（传播语义显式化），根因可观测性（387 context 携带 TOOLS.md 状态/加载器 fail-loud 化）待消费方定义 — 核销触发：5.3 上下文装配契约订立时定义 L1 失败语义（与 R1-DF2 同锚 5.3）。**5-3 Task 0 处置（2026-10-20）：本 Story 处置**——Task 3 循环 B 交付 L1 失败语义测试（TOOLS.md 缺失/降级空 L1 时装配行为：387 传播或显式降级注记）+ 装配契约 DC-3 定稿核销

## Deferred from: code review of 5-3-single-agent-workflow Round 1 (2026-10-21)

> 审查台账见 Story 5-3「Review Findings」节（四视角并行调研 + 双评审员 C3 门禁，零 P0；P1×3 + P2×6 + P3 批 12 + 耗时优化 2 落地 1 改判）。本段为登记留项分流（详尽机理见 Story 已知下游风险区 #6-#8）。

- 【R1-DF1·P2】幻觉工具名 380 穿透反思-重试闭环 — plan 阶段 LLM 自主选名（DC-10）幻觉未命中 registry 时 ToolNotFoundError(380) 直接穿透整链（execute 服务 L226 已声明决策），verify→reflect 重试只覆盖验证失败不覆盖工具解析失败；LLM 名字幻觉是结构化输出高频失败模式 — 核销触发：工具选择韧性 Story（步级捕获 380 记入 step_summaries 继续，或作为 reflect 闭环触发信号）
- 【R1-DF2·P2】谓词键可经 parameters 预设（外部可控内部控制流初值）— 引擎 ainvoke 将 parameters 原样作初始 state，外部可预设 retry_count/executed_phases 初值（用例链路只传 agent_id/task/context 三键不触发；orchestration_service API 面直通）— 核销触发：7-2 REST 入口立项时初始 state 键白名单过滤
- 【R1-DF3·P3】ChainOfThoughtSchema.input_summary 必填与「系统覆写」语义冗余 — R1-F8 采用文案修正（最小面），Schema 给 default（回声面字段值不被消费）为更根治形态 — 核销触发：下次 Schema 演进（联动既有 5 测试面）
- 【R1-DF4·P3】测试基建耗时债：session autouse bootstrap() 7.35s×worker（D13 既有登记的 pytest 形态）— 纯 domain/SAP 单测 worker 被强制付组合根全量注册成本；本 Story 测试自身执行全亚秒（D 视角实证），耗时大头为共享基建 — 核销触发：组合根瘦身（D13 架构级决策）或 conftest 按需 bootstrap 分层（影响全仓测试，需专项评估）
- 【R3-DF1·P3】终局合成多轮反思素材截断 — package 阶段终局 prompt 的 reflection 素材仅取 state["reflection"]（末次 reflect 产物），两轮重试时间线中第 1 轮的 error_analysis/revised_plan 不进终局 prompt（「历经 N 次重试」描述与单轮素材不完全对应——素材真实无虚构，属总结素材不完整的简化面）；完整化需 reflection 历史聚合设计（state 键扩展或服务侧聚合） — 核销触发：反思轮信息流扩展时（与 R1-DF1 工具选择韧性同 Story 评估）
- 【R1-DF5·P3】SingleAgentWorkflow 新图 compile 无 checkpointer（R5 终审补录——Story 风险区 #8 此前未入台账） — 图工厂裸 compile 与 BasicAgent `compile(checkpointer=...)` 编译策略分叉，thread_id 被静默忽略（langgraph 1.2.9 实测无害）；DC-1 选型理由之一的 checkpoint 中断恢复需 checkpointer 注入基础 — 核销触发：5-10 checkpoint 系列立项（图工厂接受可选 checkpointer 参数由引擎传入，与 BasicAgent 对齐）
- 【R4-OBS·P3】red_blue 真实辩论场景打满 180s 防挂死上限才 skip — `tests/integration/test_red_blue_debate_integration.py` 三重门探测只验 LLM 可用性不验延迟，UDMR GLM-5.3 环境下单次结构化调用 30s+，`run_debate` 每次跑满 180s wait_for 后走 TimeoutError→skip（2026-10-21 集成面实测 180.03s 全程耗时）——每次集成/全量跑白付 180s；改进形态=辩论前单调用延迟预探测（如 elapsed>15s 即判「30s 目标前提不成立」提前 skip，省 ~170s/次）— 核销触发：4-5 资产面下次维护或 5.7 批量基准立项（属 4-5 Story 文件域，5-3 审查周期内不动）。**2026-10-21 已清偿（用户授权跨 Story 耗时优化任务）**：辩论前 `PerspectiveAnalysisSchema` 同 Schema 延迟预探测（25s 上限，单次 ≥10s 即按「3×单次 ≥30s 目标前提不成立」提前 skip，语义同既有 elapsed≥30s 分支）——实测 186.49s→25.04s（省 86%）；首版独立小 Schema 探测因下界过松漏放行（d_probe 8s 放行而 d_debate 40s+）——代表性探测必须同 Schema 的教训入函数 docstring

## Deferred from: code review of 5-4-eip-basic-elastic-isolation Round 1 (2026-10-22)

- 【R1-DF1·P3】clear_scoped 接线纪律约束（captive dependency 缓解前提）— DC-7 的「无实害」论证依赖「clear_scoped 生产未接线（SCOPED≡SINGLETON 进程级共享）」环境前提（组合根 isolation_management_service 注册注释自认；retry_helpers.py:66 同款注释）；未来接线请求作用域清理时若只调 clear_scoped 不调 clear_singleton，SINGLETON isolation_management_service 将持有绑已关闭事件循环的死亡 RedisAgentRepository（"Event loop is closed"——测试环境验收 _run_cli 双清正是此形态的规避）— 核销触发：请求作用域接线立项（接线时 clear_scoped 必须连同 clear_singleton，或评估 agent_repository 翻 SINGLETON）
- 【R1-DF2·P3】StorageError(103) 同码双语义分化 — ①构造纪律分化：redis_snapshot_store.py:133/183 `raise StorageError(...) from e` 不带 cause= 构造参数，与 agent/isolation 仓储 cause=exc 形态（5-1 Task 3 教训）同码两种构造纪律（snapshot 域归他 Story 资产不动）；②语义分化：数据损坏与连接故障同码 103，监控维度不可区分（可观测性分化形态=except 内分支 context 标记 data_corrupt 或专用码）— 核销触发：存储层异常码专项或 5.5（与 agent_repository 先例统一行动，单仓先例不孤立改）。**5-5 Task 0 处置（2026-10-23）：维持 deferred**——5-5 零存储层改动（无新仓储、无异常包装面），触发条件不变，归存储层异常码专项（5-5 DC-12）。**5-6 Task 0 处置（2026-10-25）：维持 deferred + 扩面注记**——5-6 新建 PostgreSQLIsolationSwitchLogRepository（save/search 均带 SQLAlchemyError→StorageError(cause=exc) 包装链，redis_isolation_repository L94 构造纪律先例的 PG 版）+ 切换链 Redis 写同抛 103，双存储同码场景进一步扩大；新仓储已采 cause=exc 构造纪律（不新增分化形态），语义分化仍归存储层异常码专项

## Deferred from: Story 5-5 Task 0 移交三项处置 (2026-10-23)

- 【5-4 风险 #6·已核销】孤儿隔离键自愈策略（原登记位 = 5-4 story 已知下游风险 #6：切换重置 TTL 使隔离键晚于 Agent 键过期，消费方可选自愈策略归 5.5/后续决策）— **核销于 Story 5-5（2026-10-23）Task 0（DC-12）**：5-5 交付的工作流入口 fail-closed 检查已闭合其危害面——孤儿态下 Agent 键存活/隔离键缺失 → 执行入口 447 拒（不可用即拒绝，安全方向）；自愈通道 5-4 已实现（initialize upsert 覆盖回 L4），无需新代码。**Task 7 终态确认（2026-10-23）**：入口 fail-closed 已随 Task 3 交付并经验收 AC-2.2/AC-6.2 双锚验证——核销成立
- 【5-4 风险 #7·维持】同 Agent 并发切换无锁竞态（原登记位 = 5-4 story 已知下游风险 #7：后写覆盖 + 事件序与终态可能不一致，5.5/V1 自动触发多源并发立项时需评估）— **5-5 Task 0 处置（2026-10-23）：维持 deferred**——5-5 探针全部为跨 Agent 面（不同 agent_id 键空间天然隔离），不构造同 Agent 并发切换；触发条件（多源并发切换）仍属 V1 动态触发立项（5-5 DC-12）。**Task 7 终态确认（2026-10-23）**：实施未涉同 Agent 并发切换面（探针/并发场景均为跨 Agent 面）——维持登记在案（**5-5 代码审查 R2 互链**：同族新增 5-5 风险 #8——判定-执行时间窗 TOCTOU 升档方向 fail-open，见 5-5 故事风险表，同归 V1 动态升降级立项）。**5-6 Task 0 处置（2026-10-25）：维持 deferred + 新增注记**——5-6 的 audit-first 日志写入在竞态下同样产生乱序日志（两并发切换 → 两条日志 + Redis 终态取最后写者），**日志序 ≈ 事件序（同一竞态窗口）**；MVP 触发通道仅 CLI 人工单发，并发切换不可达；V1 动态触发立项时日志与终态一致性需与终态竞态一并评估
- 【5-4 R1-DF2·维持】见上区段原条目 5-5 处置注记（零存储层改动，维持归存储异常码专项）。**Task 7 终态确认（2026-10-23）**：实施零存储层改动（组合根外零新仓储）——维持登记在案，终态与 Task 0 处置一致

## Deferred from: Story 5-6 Task 0 偏离声明处置 (2026-10-25)

> Story 5.6（隔离切换日志记录——FR-AC-06）SDD 规范定义阶段的偏离声明落盘（OD-n 编号规范——与审查留项 D# 消歧）。gap 四要素：描述/触发条件/归宿/承接方链接。audit-first 写入链（DC-2）等设计决策见 5-6 故事文件，不在此重复。

- 【OD-1·P2】MinIO WORM 24h 归档管线不在 Story 5.6 实施（`worm_ref` 字段预留 nullable 默认 None）— 描述：architecture.md §8.5 L814（IsolationLevelSwitched 切换后 24h 内归档 MinIO WORM 7 年）与 §5.3 L693 的归档管线未随 5.6 交付，防篡改由 PG RLS（ENABLE+FORCE+deny UPDATE/DELETE）+ CheckConstraint 等效承载（DC-4）；1.10 WORMManager 同为未接线现状（实例在组合根存在但 audit_service lambda 未注入）。**补偿控制差距四注（RLS 与监管级 WORM 的差距，随承接方落地）**：①RLS 可被 superuser/BYPASSRLS 属性绕过；②PG 备份/导出不受 RLS 约束；③无 7 年保留期限策略；④TRUNCATE/DROP/REGRANT 不走 RLS——业界标准做法是 DDL owner 与应用运行角色分离 + 应用角色仅 GRANT INSERT/SELECT（权限级撤销比 RLS deny 更硬）。**随承接方另评估两项**：gap-free 序列/链式防篡改（UUID4 主键无序不防间隙——SEC 17a-4 口径通常要求连续序列或 hash-chain）与表分区（7 年保留 + 高追加量下按 switch_timestamp range 分区是归档管线前置设计约束）；监管级 WORM（SEC 17a-4 / ISO 27001 口径）需 MinIO Object Lock COMPLIANCE 管线 — 触发条件：V1 合规归档管线（审计归档批处理）立项 — 归宿：V1 — 承接方：Story 13-4（sox-compliance-404——FR-SC-12 SOX 404，epics_v1.0.md L557 映射 Epic 13 Story 13.4）
- 【OD-2·P3】「切换后协作状态」不设独立字段 — 描述：or.md 一.2.(9) L30 实体七属性含「切换后协作状态」，5.6 实体以 target_level 承载协作状态语义（等级=协作模式映射，architecture.md §5.1 四级表），MVP 单 Agent 无协作态可记；architecture.md §9 L833 定稿字段亦无此项 — 触发条件：V1 多 Agent 协作组立项 — 归宿：V1 — 承接方：Story 9-4（联合分析组创建——FR-AC-10，epics_v1.0.md L525 映射 Epic 9 Story 9.4）/ Story 9-5（公共黑板中间结论交换）
- 【OD-3·P3】`trigger_type` 枚举字段不设（SYS 命令/关键词频率/任务依赖/用户请求四类触发源类型化）— 描述：MVP 唯一触发通道为用户显式请求（5-4 既定），`IsolationLevelSwitched` 事件仅 trigger_reason 自由文本无 type 字段——单通道下枚举仅一值（YAGNI）；5.6 实体加字段为非破坏演进 — 触发条件：V1 FR-AC-09 多通道立项（随事件 payload 扩展联动） — 归宿：V1 — 承接方：Story 9-3（dynamic-isolation-level-adjustment——FR-AC-09，epics_v1.0.md L524 映射 Epic 9 Story 9.3）
- 【OD-4·P2】实体字段命名与规划权威面映射 + 规划 DDL 差异项 — 描述：实体采用 `previous_level/target_level/trigger_reason`（非 architecture.md §9 L833 的 from_level/to_level/trigger——跟随事件 payload 六字段 SSOT + core-domain-design §17.3.3 伪码同名）+ 表名复数 `isolation_switch_logs`（非 arch-appendix L9753-9768 单数）+ 不落 `tenant_id` 列（对齐同域 audit_log 无租户列先例）+ `worm_ref`（非 worm_storage_ref）；created_at 保留（行创建审计列，与 switch_timestamp 语义分工：切换时刻 vs 入库时刻，非差异项）。规划 DDL 其余差异项（trigger_type NOT NULL/tenant_id NOT NULL/单数表名/worm_storage_ref/无 approval_chain 列——最后者属规划缺陷，approval_chain 是 FR-AC-06 六要素不可裁）随各自触发条件以 alembic 新迁移扩展（已合入迁移禁改） — 触发条件：V1 多租户立项（tenant_id 随 13-x 合规管线族评估）或多通道立项（trigger_type 随 9-3 联动） — 归宿：V1 — 承接方：多租户专项（tenant_id）+ Story 9-3（trigger_type，OD-3 联动）

## Deferred from: code review of 5-4-eip-basic-elastic-isolation R5 终审特权发现 (2026-10-22)

- 【R5-DF1·P3·已核销】5-3 集成场景⑤ outbox PG 连接级门控缺口（5-4 R1-F07 同型）— `tests/integration/test_integration_agent_workflow.py::test_scenario_5_real_publish_outbox_row` 的 PG 门控仅拦 import 失败不拦连接失败（5-3 资产面）；5-4 R1-F02 端口隔离修复后该测试从「假打 dev 5432 绿」转为「正确探测 5433 不可达红」——诚实暴露但违 DoD「PG 缺席 skip」形态 — 核销触发：5-3 资产维护或测试基建门控专项（修复形态照抄 5-4 R1-F07）。**已核销于 5-4 R7（2026-10-22）**：用户实测踩中触发条件（PG 可达但 event_outbox 表缺失形态——比原登记更进一层的缺席），同款升级为连接+表存在双预检 + R7-F02 跨 loop SINGLETON publisher 清理防线（详见 5-4 story R7 表）

## Deferred from: code review of 5-6-isolation-switching-log Round 1 (2026-10-26)

> 审查台账见 Story 5-6「代码审查发现 Review Findings」节（四视角并行调研 + C3 双评审员门禁——P1×3 + P2×9 + P3×24，修复 21 项 + 改判/证伪 6 项 + 登记 4 项本段）。F7/F8 两项 P2 被并行会话超集方案取代（d6ea8892 SET ROLE 降权实证 + ORM after_create 钩子/pg_policies 幂等补建），非本段登记项。

- 【R1-DF1·P2】audit_repo 无 session_factory fallback——隔离切换 audit 联动在唯一 MVP 运行通道（CLI set-isolation）下结构性 100% 降级且每次成功切换必出 WARNING「联动审计记录失败」：`AuditRepository._session` 仅 `get_session()`（ContextVar），CLI 上下文无 session → RuntimeError 被 record 的 except Exception 包成 AuditError → 服务层 DC-6 降级（audit_repository_impl.py:34 直调实证）。后果三连：①DC-6「隔离切换进入 1.10 统一审计检索面」在全部当前生产运行路径不可达（audit_log 永无 isolation:switch 行——集成场景④仅测试 set_session 上下文验证过）；②结构性降级与真实审计故障共用同一 warning（告警疲劳淹没真故障）；③与本 Story DC-5 给日志仓储补的双模式 fallback 形成不对称。修复形态 = audit_repo 补 session_factory fallback（照抄 DC-5/outbox 形态 ~20-30 行 + 测试）——属 1-10 交付资产域，审查周期不动他 Story 文件 — 核销触发：7-2 REST 化立项（HTTP 路径 audit 联动真实可达性需求）或 13-x 合规专项（统一审计检索面完整性）；主日志 isolation_switch_logs（SSOT）不受影响，本项是联动索引面的运行面可达性缺口
- 【R1-DF2·P3】`ix_isolation_switch_logs_agent` 单列索引被组合索引 `ix_isolation_switch_logs_agent_ts` 最左前缀完全覆盖——纯冗余写税（审计表高追加量场景每行多维护一棵 B-tree）；另 previous/target 单列索引基数仅 4 值，大表上选择性差，「BitmapOr 可达」主张在大表下不必然成立（PG 优化器可能弃用）。002 audit_log 先例同款沿袭 — 核销触发：V1 表分区评估时（OD-1 承接方 13-4 立项输入）一并复查索引集；已合入 015 禁改，删索引走新迁移
- 【R1-DF3·P3】PG 仓储无 factory 且无 ContextVar session 时 RuntimeError 裸上抛 vs 端口契约声明 `Raises: StorageError`——`test_save_without_factory_reraises_runtime_error` 单测钉死为有意设计（「配置缺失显式失败」，outbox L80 先例同款）；组合根恒注入 factory 生产近不可达；改契约（RuntimeError→StorageError 103）语义存疑（wiring error ≠ 连接故障）且需翻转既有单测。代码审查 C3 双评审员分歧，主会话裁决维持有意设计 — 核销触发：存储层异常码专项（与 5-4 R1-DF2 同锚——语义分化可观测性一并定夺）
- 【R1-DF4·P2】isolation_switch_logs 检索面租户谓词缺失——`IsolationSwitchLogQuery` 无租户维度（全字段 None=全量分页合法）+ RLS SELECT `USING(true)` 全放行 + CLI `isolation-logs --agent-id` 可缺省：多租户部署下任意操作员可逐页拉取全部租户的切换审计（trigger_reason 自由文本）。MVP 单租户不可达；OD-4 已裁 tenant_id 列归 V1 多租户专项 — 核销触发：V1 多租户立项（tenant_id 加列 + 检索面租户谓词 + RLS SELECT 策略收窄三联动——13-x 合规管线族）；本项是 OD-4 的检索面补充登记
