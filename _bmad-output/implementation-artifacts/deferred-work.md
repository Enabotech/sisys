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
- lint-imports BROKEN → **触发 = 架构重构专项立项**（组合根 lazy import 链重构，`.importlinter` 已合入规则禁改；CI 长红但稳定不恶化、无时限压力——被动等待需改规则或新增 interfaces→组合根 import 时被迫处理）

**路线图触发型**：
- langgraph retry/timeout 字段 → **触发 = Story 5.10（CheckpointWithEvaluation）或 6.6（Checkpoint 摘要查看）实施**（epics :2016 规划在案、story 文件未创建——两处是 checkpoint_table/编排引擎行为的规划消费方，届时字段语义定稿）
- 工具熔断 → **触发 = Epic 5 sprint planning 重估归属**（epics 无直接对应 Story——FR-CP-07 是 Epic 11.3 成本熔断非工具执行域；建议 5.4/5.5 EIP 弹性隔离实施时评估挂点或独立小 Story）

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

- 可变字典引用 — frozen dataclass 的 `parameters`/`decision_result` 字段存储可变引用，调用方可在构造后修改。AgentDecided 同样有此问题。预存，非本 Story 引入。`src/domain/events/workflow_events.py:31`（**2026-10-10 具备度调查注记**：部分具备维持 deferred——修复形态已实证（`_serialize_value` 增 `isinstance(value, Mapping)` 分支 + `__post_init__` MappingProxyType 包装），但无任何「构造后篡改」真实场景；附带发现 saga_events init=False 形态 `from_dict(to_dict())` roundtrip 实测 TypeError，若启动本项须先修 base.py from_dict 联动）
- ~~flow_run_id 默认工厂误导~~ — **RESOLVED**（2026-10-10 技术债清偿）：生产 4 构造点（WorkflowSubmitted/RAGIndexed/AgentDecided×2——ReportGenerated 零构造点）全显式传参已实证——4 字段改 `field(kw_only=True)` 必填化，13 处测试无参构造补显式 id；漏传立即 TypeError 不再静默铸造。
- aggregate_type 可被覆盖 — `if not self.aggregate_type:` 条件允许调用方传入自定义值。所有事件都有此模式。预存。`src/domain/events/workflow_events.py:35-38`
- ~~DomainEvent 注册表无隔离~~ — **RESOLVED**（2026-10-10 技术债清偿）：`tests/unit/domain/events/conftest.py` autouse 快照/恢复 fixture（tests/conftest.py 会话 ContextVar 先例同款）；注记——import 期污染源（test_redis_event_bus_subscribe_fix 模块级 register 等 2 处）发生在 fixture 之前，需其文件内自理（附注已写入 conftest docstring）。
- 不可序列化参数延迟失败 — parameters 包含 Prefect 对象时仅在 `to_dict()` 时报错。预存问题。`src/domain/events/workflow_events.py:31`（**2026-10-10 具备度调查判定：不应做**——to_dict json.dumps 探针（4-5 清偿成果）已是正确失败位置且有绊线钉死；构造期校验是高频路径负收益）
- ~~【调查附带发现·2026-10-10】`SagaStatusChanged.from_dict(to_dict())` roundtrip 实测 TypeError~~ — **RESOLVED**（2026-10-10 A 类清偿）：`base.py` from_dict 核心字段按 target_class 的 `init=False` 声明过滤（init=False 成员保持类默认值）+ roundtrip 回归用例。
- ~~【调查附带发现·2026-10-10】`DomainEvent.reset_registry()` 零调用且具破坏性（清空后不自动恢复）~~ — **勘误 + 处置完毕**（2026-10-10）：「零调用」判定失实（src 零调用但**测试有 2 处消费方**——test_outbox_entity:189/test_event_outbox_adapter:112）；处置改为 docstring 破坏性语义警示 + 指引快照/恢复形态（tests/unit/domain/events/conftest.py），方法保留。
- 【A 类清偿附带发现·2026-10-10】alembic 全新库链挂在 002 — `WITH CHECK cannot be applied to SELECT or DELETE`（002 audit RLS policy 语句）；本地 dev 库无 alembic_version 表（历史 create_all 建）从未暴露。全新环境初始化（CI 重建/新部署）将无法 `upgrade head`——需专项修复 002（RLS policy 语句语法），建议随下一次 alembic 触达时处理。

## Deferred from: code review of 2-6-document-version-snapshot (2026-08-02)

- ~~缺少性能基准测试（P95 指标未验证）~~ — **半数 RESOLVED**（2026-08-03 commit 8bfcc472 已交付 domain 口径 5 项基准——值对象构造/元数据 diff/内容 diff 等；**2026-10-10 技术债清偿补齐残余**：AC-1 create_snapshot 端到端 P95<100ms 基准（4-6/4-7 基准先例同款分级断言形态）。
- ~~缺少并发版本控制测试（≥10 并发操作）~~ — **RESOLVED**（台账过时勘误）：`tests/integration/test_integration_document_version_concurrent.py:195` 的 `test_10_concurrent_saves_only_one_succeeds`（2026-08-03 commit 8bfcc472 交付）精确覆盖 AC-3「10 并发只有 1 个成功」+ 串行 10 次 + 5 文档并发首快照三用例——登记时点（2026-08-02）早于交付次日。
- `list_versions`/`get_version` N+1 查询问题 — 先查 documents 验证租户，再查 snapshots，可用 JOIN 优化。预存，当前数据量小，性能影响可接受。（**2026-10-10 具备度调查注记**：实为固定 2 查询非经典 N+1，JOIN 等价改写回归面 32 处——机会性优化维持 deferred）
- ~~内联 import 散落问题~~ — **RESOLVED**（2026-10-10 技术债清偿）：「规避循环依赖」论据经调查失实（被导入全为 domain 层，六边形契约下结构不可能循环）——6 个内联块全部上提模块顶部并与 TYPE_CHECKING 块去重，12 测试全绿。

- ~~InMemoryRoutingDecisionLogRepository 非线程安全~~ — **RESOLVED** (2026-05-25)：引入 asyncio.Lock + max_size(1000) + TTL(24h) 淘汰。`src/infrastructure/messaging/inmemory_routing_decision_log_repository.py`

## Deferred from: code review of 4-6-tool-version-management (2026-10-07)

- lint-imports「Interfaces layer must not depend on infrastructure」broken（入口稳定为 `src.interfaces.api.app -> src.composition_root (l.24)` 与 `src.interfaces.cli.ocr_cli -> src.composition_root (l.39)` 两条链） — 经基线 5b96e75a 比对确认为**预存量**（非 4-6 引入），main 上该 CI 门禁为红。根因：interfaces 层 import 组合根，而组合根内部大量 infrastructure lazy import 被传递检出（组合根具体中转模块随构建漂移——jwt_service/prefect/rabbitmq_publisher 等多次实测各不相同，以 lint-imports 实时输出为准，不锁行号）。涉及组合根 lazy import 链的架构级重构，需单独立项处置（`.importlinter` 已合入规则禁止改动）。
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
- 工具熔断（or.md 四.7.(3)） — 建议挂 Story 5.x Agent 弹性隔离；ToolExecutionQuery.state 过滤材料已齐备（纯范围决策）。
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
