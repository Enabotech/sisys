# Story 7.2: REST API 接口（/api/v1 集成入口）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 集成工程师,
**I want** 系统通过 REST API 提供接口（文档管理/工具调用/Agent 协作/规划生成/系统管理）,
**So that** 支持外部系统集成。

### 业务价值

- **Epic 定位：** Epic 7（多触点用户界面与 API 集成）第二 Story，P0-2 优先级。与 7-1（CLI）并行依赖关系（epics:2577——仅依赖 Epic 1 Story 1.1）。覆盖 FR-UI-02（prd.md:1932，P0）+ NFR-IF-05（OpenAPI 3.1 契约测试通过率 100%）。
- **价值组：** 多触点操作与监控能力——第三方系统经 REST API 集成 sisys。
- **现状缺口（四调研 Agent 实测，2026-11-21 时点）：**
  1. **auth 路由存在但未挂载**（`src/interfaces/api/auth.py:198` `create_auth_router` 完整实现 login/refresh/logout/me/roles，`src/entrypoints/api_app.py:75-81` 仅挂 7 router——登录端点不可达，deferred-work:115 钦定「最大单点风险」）；同批未挂载：audit（:124——5 端点零 Depends）/crawler（:108——**4 端点零 Depends 且工厂无认证参数**[R6 实证]）/monitoring（:19——metrics 零认证既有形态）/equilibrium_security（:160，依赖 3 个失效 impl 不可挂载）。
  2. **三大端点族 REST 面为零**：plan（generate/状态查询/导出）、checkpoint（list/show/recover）、agent（run）——interface-design §8.2 钦定 P0 端点无任何 REST 实现。
  3. **tools 路由缺执行面**：`tools.py` 仅版本管理族六端点（versions 注册/列表/publish/rollback/abort-canary/traffic），缺 §8.2.2 钦定的 `/{tool_id}/execute` 与 `/{tool_id}/schema` 两个 P0 端点。
  4. **document 路由缺 parse/versions**：`document_upload.py` 有上传族，缺 `/{id}/parse`、`/{id}/versions`（§8.2.1 钦定的 `/{id}/trace` 因端口域现实迁 plans 域承载——OD-10；既有 `GET /api/v1/search/trace/{document_id}`[引文查询，traceability.py:155] 承载 document 域溯源查询面）。
  5. **openapi.yaml 与实现漂移**：`docs/api/openapi.yaml`（2484 行，34 paths）手工 SSOT——`/documents` GET 列表 yaml 有而实现无、chunked 族实现有而 yaml 无、无 plans/checkpoints/agents 路径。
  6. **长驻面债务激活**：组合根内显式注记「SINGLETON 捕获 SCOPED 依赖——CLI 一次性进程无故障面；未来 7-2 长驻 REST 面改 SCOPED」（traceability_tree_service :2036——**捕获主体**，触发器注记 :2028-2030 所在注册块 / traceability_tree_use_case :2065 / executive_view_service :2087 注册块）；6.1-DF6 三项 REST 并发回头清单触发条件命中。

---

## ✅ Acceptance Criteria 验收标准

### AC-1: API 应用工厂装配与路由挂载契约

**Given** API 服务经 `create_app()`（src/entrypoints/api_app.py:50）装配
**When** 应用启动（lifespan bootstrap → 中间件 → router 挂载）
**Then** 挂载契约生效：
- 既有 7 router（archive/summary/evaluate/trace/document_dictionary/document_upload/tools 版本面）零回归零改动
- **4 个既有 router 挂载激活**：auth（`create_auth_router` auth.py:198——POST /api/v1/auth/login 等端点族可达）、monitoring（`create_metrics_router` monitoring.py:19——router 自身无 prefix、metrics_path 参数默认 `/metrics`，**挂载形态冻结**：`include_router(..., prefix="/api/v1/system")` 拼装为 `/api/v1/system/metrics`）、crawler（crawler.py:108，prefix 已带 `/api/v1/crawler`；**认证实质改造[R6 实证]**：4 端点[submit_task/get_task_status/cancel_task/list_supported_formats]零 get_current_user 零 Depends 且工厂连认证参数都无[create_crawler_router 仅 get_crawler_client 参数]——挂载即激活未认证 POST 任务提交面，须加工厂认证参数+逐端点补挂，对齐 audit 待遇，见 AC-3）、audit（audit.py:124——**前缀统一** `/audit`→`/api/v1/audit` + **认证实质改造**：get_current_user 参数现有但全部端点零 `Depends` 挂载[R1 实证]，须逐端点签名补挂，见 AC-3）
- **equilibrium_security 不挂载**（defer——3 个 impl 字符串指向不存在类，deferred-work:126 等保接线专项；OD-6 登记）
- **新增 system 路由**：GET `/api/v1/system/health`（轻量存活探测——返回 `{"status": "ok", "version": ...}` 形态，不连真实存储；**version 来源钦定**：`importlib.metadata.version("sisys")` 装配期解析[取不到则常量兜底——dev 实测裁定]，R3 补决策点；认证豁免面，见 AC-3）
- 中间件链顺序保持现状（SessionMiddleware → ExceptionContextMiddleware，api_app.py:62-63）+ `register_exception_handlers` 零改动
- **前缀统一纪律**：全部新挂载/新增端点一律 `/api/v1` 前缀（openapi.yaml servers 已含 `/api/v1`）

**验证标准/Validation Criteria:**
- [ ] `create_app()` 挂载断言：4 个激活 router + 既有 7 router + 新增路由族全部在 `app.routes` 可达（单测 test_app.py 扩展——**新建挂载断言**，该文件现仅 3 基础测试无挂载断言）
- [ ] GET `/api/v1/system/health` 返回 200 + status ok（无认证）
- [ ] GET `/api/v1/system/metrics` 返回 Prometheus 文本格式（metrics 端口 :898 真实采集；**承载面钦定[R3]**：单测 test_system_routes.py[metrics 端口 resolve 真实 collect 零 IO]——验收 AC-1×2 场景聚焦挂载可达+health）
- [ ] 既有 API 测试零回归（tests/unit/interfaces/api/ 17 文件 + tests/contracts/ 13 API 契约文件全绿）

### AC-2: P0 核心端点端到端（真实服务）

**Given** 系统真实服务（PG/Redis 等）可用且组合根 bootstrap 完成
**When** 依次调用新增 P0 端点族
**Then** 端点正确路由→消费端口→返回结构化响应（端点冻结矩阵见 SDD 节 SSOT 表）：
- `POST /api/v1/documents/{document_id}/parse` → `document_parsing_service`（:1377）→ 解析后 Document 元数据（**响应序列化注记[R6]**：Document 含 embedding 向量字段 list[float]|None——响应 Schema 剔除向量字段[体积+向量面外泄]）
- `GET /api/v1/plans/{plan_id}/trace` → `traceability_tree_use_case`（:2065，`execute(*, plan_id: str, depth: int = 4)`——plan 域溯源树；**SINGLETON→SCOPED 双对象迁移本 Story 承载**[service :2036+use_case :2065，AC-7]）→ 溯源树视图（**域迁注记 OD-10**：interface-design §8.2.1 钦定 `/documents/{id}/trace` 但仓内零 document 域溯源树端口——7-1 OD-8 端口签名现实层优先原则，CLI `trace-tree --plan-id` 先例同域对齐；**语义分立注记**：与既有 `GET /api/v1/search/trace/{document_id}`[引文查询——3-8 高保真溯源消费面] 不同源不同义，CLI archive query 同款注记形态）
- `GET /api/v1/documents/{document_id}/versions` → `document_repository`（:1180 `list_versions`）→ 版本列表
- `POST /api/v1/tools/{slug}/execute` → slug 解析链（`skill_manifest.SLUG_TO_TOOL_ID` SSOT → `get_tool(tool_id=)`——7-1 冻结链复用）→ `tool_execution_service`（:2747）→ ToolResult
- `GET /api/v1/tools/{slug}/schema` → `tool_registry_service`（:2604）+ `skill_loader`（:2881）→ 含 `input_examples` 的 schema
- `POST /api/v1/agents/{agent_id}/run` → `agent_workflow_use_case`（:3184，`execute(agent_id: UUID, task: str)`）→ AgentWorkflowResult（真实 LLM 面动态 skip——无 Key 环境 `pytest.skip()`，7-1 同款；agent 不存在→AgentNotFoundError 443→404 用例首步自抛[R6 注记]；**深嵌套序列化注记[R6]**：含 ChainOfThought+TaskEvidencePackage——响应字段子集 dev 按可观测需要裁定）
- `POST /api/v1/plans/generate` → `blm_planning_use_case`（:3524，`execute(agent_id, task, plan_id=None)`——**plan_id 为 str 非 UUID**）→ BlmPlanningResult（LLM 面动态 skip）
- `GET /api/v1/plans/{plan_id}` → `blm_planning_status_use_case`（:3548，`execute(plan_id: str) -> BlmPlanningStatus`——**6.1-DF5 首激活清偿**）
- `POST /api/v1/plans/{plan_id}/export` → `report_generation_use_case`（:3610，markdown）/ `pdf_report_generation_use_case`（:3714，pdf；`format` query 参数分派）——**6.5a-DF1 清偿**；**响应语义定谳[R6]**：StrategicReport 元数据 JSON（report_id/file_path/section_count——StrategicReport 为纯元数据实体无内容字段；file_path 为 L0 逻辑路径集成方不可直读，非文件流下载；文件内容获取面 OD-18 登记）
- `GET /api/v1/checkpoints?plan_id={uuid}` → `checkpoint_list_use_case`（:2530）→ CheckpointSummaryView 列表（**分页 YAGNI 注记[R6]**：plan 内 checkpoint 上限 8 条[CP-1..CP-8 编号体系]且端口签名无分页参数——不加 limit/offset）
- `GET /api/v1/checkpoints/{plan_id}/{checkpoint_no}` → `checkpoint_recovery_use_case`（:2514 预览面，`execute(*, plan_id, checkpoint_no)` 两参必填——7-1 R5 终审方案 a 口径）
- `POST /api/v1/checkpoints/recover`（body：plan_id + checkpoint_no + mode? + confirmed_by?）→ `checkpoint_recovery_execute_use_case`（:2542；**created_via 固定传 "api"**——7-1 R4-2 同款触发源审计标识；confirmed_by 缺省取认证用户标识——REST 面有真实身份，优于 CLI 缺省取 session；**recover 后再 list/status 的期望留白[R3 注记]**：dev 设计自由，建议验收场景含 recover 后 checkpoint list 复核）
- `GET /api/v1/archive/query?plan_id={uuid}` → `blm_chain_trace_use_case`（:2573）→ BLM 链路追溯视图（**语义注记**：与既有 `GET /api/v1/archive/plans/{plan_id}`[strategic_archive 档案条目查询，:2405 族] 不同源不同义——CLI archive query 同款消费面）

**验证标准/Validation Criteria:**
- [ ] 全部端点验收场景走真实服务（真实数据 → 真实端口 → teardown 定向清理）；LLM 依赖面（agent run/plan generate）动态 skip + 非依赖面（status/export/checkpoint/archive）确定性全绿
- [ ] checkpoint 族 given 前置经 **checkpoint 仓储/snapshot 直构（dev 实测裁定形态）**——R3 勘正：原引「7-1 R3-7 checkpoint_use_case 直创」先例已被 7-1 CR6 判定为无 Key 环境连带 skip（创建链 OD-12 压缩强制环节依赖 LLM——7-1 验收至今 1 skip 正是它），与本条「非依赖面确定性全绿」口径矛盾，直构绕开 LLM 依赖链；plan 状态查询 given 前置经真实 generate 或 snapshot 测试数据直构（blm_planning_status 依赖 snapshot_repository——dev 实测裁定直构形态）；**trace/archive query given 前置同源 snapshot 直构**（R3 补决策点：溯源树与 BLM 链路均为 plan 域快照族消费——dev 实测裁定直构形态）；**tool execute 走 LLM 工具时 skip 归类同 agent run/plan generate**（R3 补注记；schema 端点零 LLM 确定性全绿）
- [ ] 端点响应体为合法 JSON 且含领域字段（document_id/plan_id/checkpoint_no 等；**parse 断言强度注记[R3]**：断言 `parse_status=completed`+document_id 归一形态[7-1 CR6-1 先例——miss 形态合成 FAILED 文档的 parse_status 即判别锚]，非泛 JSON 字段存在性）
- [ ] 既有 `POST /api/v1/documents`（单传）/`POST /documents/batch`（**同步批量**——`document_upload_service`[注册名，R1 勘正] `upload_batch` 请求内信号量并发同步返回，:1195 注册块的既有形态）零改动零回归；interface-design §8.2.1.1 钦定的 **202 异步 job 契约无基建支撑，defer**（OD-2 登记——无 job 队列框架，Prefect 无 flow-run 端口）

### AC-3: 认证契约（全端点覆盖）

**Given** CLAUDE.md 硬约束「所有 API 路由必须过认证中间件」+ 现实承载形态为 **per-endpoint `get_current_user` dependency**（无全局中间件——auth.py:150-195 工厂先例，document_upload.py:156/tools.py:130 复制同款）
**When** 请求到达 7-2 全部新增端点
**Then** 认证契约生效：
- **全部新增端点必须挂 `get_current_user` dependency**（复用 `get_current_user_dependency(auth_service)` 工厂或 `get_current_user_override` 注入形态——单测/验收 override 注入 TokenPayload，集成面真实 JWT）
- **认证豁免面冻结（三态口径[R6 勘正]）**：①设计豁免 2 面——`POST /api/v1/auth/login`（登录本身）+ `GET /api/v1/system/health`（存活探测）；②既有形态豁免 1 面——`GET /api/v1/system/metrics`（monitoring router 零认证既有形态[R6 实证：get_metrics 无 Depends]——Prometheus 抓取形态，加认证需部署面协同[scrape bearer/网络隔离归 7-3 Gateway，OD-8 关联]，本 Story 不动其认证）；③既有弱形态注记（auth.py 既有语义如实登记，收口归 7-3）——refresh 凭 refresh_token 自凭证换发（无 get_current_user，业界正当形态）、logout 无 token 时静默 204 非 401（`Depends(oauth2_scheme)+if token:` 弱凭证）；openapi.yaml 中设计豁免端点显式写 `security: []`（防未来全局 security 引入时豁免面漂移——R6 措辞钦定），其余新增 path 全部 `security: OAuth2: []`；本 AC 的 401 断言限定「受保护端点」（豁免/弱形态面不写 401 期望——防矩阵误判）
- 无 token / 伪造 token / 过期 token → 401 + `WWW-Authenticate` 头（AuthenticationError→ExceptionHandlers 既有映射）
- **login 端到端链**：POST /auth/login（真实 `auth_service` :514——AuthServiceImpl+JWTService 既有实现零新建）→ AuthTokens → 携带 Bearer token 访问受保护端点成功（**login 为 JSON body**[LoginRequest pydantic——auth.py 既有形态]非 OAuth2 表单——yaml flows 写法按既有 application/json 契约形态[R6 注记]）
- **audit 路由认证补挂**：`create_audit_router`（audit.py:124）的 `get_current_user` 现为可选参数**且全部端点零 `Depends` 挂载（R1 实证：参数声明之外全文件零使用）——须逐端点签名补挂 `Depends(get_current_user)`（5 端点实质改造，Task 1 承载）**
- **crawler 路由认证补挂（R6 勘正）**：`create_crawler_router`（crawler.py:108）**连 get_current_user 工厂参数都无**且 4 端点零 `Depends`（submit_task :135/get_task_status :172/cancel_task :209/list_supported_formats :238——挂载即激活未认证 POST 任务提交面，违 CLAUDE.md「所有 API 路由必须过认证」硬约束）——须加工厂认证参数+4 端点补挂（对齐 audit 待遇，Task 1 同批承载）
- 权限不足 → 403（PermissionDenied→403 既有映射；RBAC 深度面归 7-3/存量 roles 端点，本 Story 仅断言映射正确性）

**验证标准/Validation Criteria:**
- [ ] 架构测试断言：新增全部端点 handler 挂认证 dependency（AST/依赖检查——test_arch_rest_api.py）
- [ ] 无 token → 401 矩阵断言（抽查每端点族 ≥1 **受保护**端点——豁免面 login/health 与既有形态豁免 metrics 不适用[R6 口径]）
- [ ] login→token→受保护端点访问链集成测试全绿（真实 auth_service+真实 user 仓储；测试用户 teardown 定向清理）
- [ ] OAuth 2.1 统一认证体系/令牌桶限流/注入检测**不在本 Story**（7-3 边界——epics:2693-2733 Story 7.3 四能力 + ADR-010；7-2 仅基础认证）

### AC-4: 统一错误响应契约

**Given** 端点消费的用例抛出领域异常
**When** 异常经 `register_exception_handlers`（api_app.py:65 既有装配，签名 `(app, metrics: ExceptionMetricsPort | None = None)` 支持可选接线——:116 留项承载）+ `EXCEPTION_HTTP_MAP`（exception_handlers.py:160，~138 映射）处理
**Then** 错误响应契约生效（sisys-uni-exception-design §响应体规范）：
- 响应体结构：`{"error": {"code": "EXCEPTION_NNN", "message": "...", "context": {...}}, "request_id": "..."}`
- 响应头：`X-Error-Code` + `X-Request-ID`（ExceptionContextMiddleware 从请求头取/生成 request_id——既有机制）
- 关键映射断言：NotFound→404（documents/{id} 不存在——**端点层前置查询锚定**：parse/versions 端点先经 `document_repository.find(DocumentQuery)`（tenant_id 过滤）查存在性，None→端点 raise NotFoundError→404；端口层宽语义不承担 404 契约[parse_document 文档不存在返回合成 FAILED Document——document_parsing_service.py:121-128；list_versions 租户不匹配返回 []——impl :226-227，均 R1 实证]；plans/{plan_id} 状态无记录**实为 PlanningNotFoundError 480→404[R6 勘正——非泛 NotFound 202，用例自抛 get_blm_planning_status.py:56[R7 行号勘正]]**）、Conflict→409（BLM 并发守卫 482）、EntityValidation 242→400、Validation 201→400、AuthenticationError→401、PermissionDenied→403、BusinessRuleViolation→422；**404 首要路径三锚注记[R6]**：未知 slug→ToolNotFoundError 380、agent 不存在→AgentNotFoundError 443（均既有映射，见异常消费表）；**423 行注记[R6]**：login 连败锁定映射（exception_handlers.py:407-420 既有）不单列验收场景
- Pydantic 请求体校验失败 → 422 RequestValidationError（ExceptionHandlers 既有四注册之一）
- **零新增领域异常**（REST 是接口层薄壳，EXCEPTION_HTTP_MAP 全覆盖——异常消费表见 SDD 节）

**验证标准/Validation Criteria:**
- [ ] 404/401/409/422 四态验收场景（资源不存在/无 token/并发冲突/请求体缺字段）——响应体三字段+双头断言（**断言形态先实测锚定**——7-1 CR3 教训：ExceptionHandlers 实际响应体形态以实测为准再冻结断言；**AC-4×2 场景分组建议[R3]**：404+422 同场景[请求校验族]/401+409 同场景[认证与并发族]——dev 可调；**404 锚定对象三选一注记[R6]**：documents find None/未知 slug 380/agent 不存在 443；**380/443 验收面不单列场景[R8 注记]**——单测承载足够，AC-2×8 场景映射不含未知 slug 步骤为有意设计）
- [ ] 单测矩阵：领域异常族→HTTP 状态码逐一断言（test_exception_handlers.py 既有文件扩展或新文件）
- [ ] 错误消息不泄露堆栈/SQL（消息安全性——**新增断言[R6 勘正：全仓零既有承载，「既有契约复验」前提失实]**：主路径 to_dict 三字段断言无堆栈/SQL 子串；fallback 分支 str(exc)[:500]+cause 的 str(cause) 直透泄露面登记 OD-17 专项加固，本 Story 不动生产行为）

### AC-5: 租户契约（X-Tenant-ID）

**Given** 多租户传播链路（arch-appendix 附录 H——Gateway 提取 JWT→注入 X-Tenant-ID→中间件；MVP 无 Gateway）
**When** 请求携带 `X-Tenant-ID` header
**Then** 租户契约生效：
- **消费形态对齐存量先例**：per-endpoint Header 参数 `x_tenant_id: str = Header(..., alias="X-Tenant-ID")`（document_upload.py 6 处先例——:174/:220/:266/:297/:329/:384，R1 勘正计数）——7-2 新增 document 族端点（parse/versions）必填透传；plan 族 trace 端点按端口现实无租户参数（`execute(*, plan_id, depth)`——透传面注记）；tool/plan/checkpoint/agent 族按各端口 `ExecutionContext.tenant_id`/参数现实透传（UUID 常量 00000000-0000-0000-0000-000000000101 文档化缺省——7-1 OD-10 已定谳口径，缺省策略在端点内显式构造）
- 验收租户隔离：UUID 前缀租户（TestTenant 先例）数据互不可见（A 租户上传 → B 租户查询 404——**经端点层前置 `find()` 租户过滤锚定**：find 按 tenant_id 过滤返回 None→端点 404；`list_versions` 租户不匹配返回 [] 的宽语义不承载 404，R1 实证）
- **PT-03 防伪造 X-Tenant-ID（arch-appendix:2264，P0）归 7-3 Gateway**（JWT 提取注入是 Gateway 职责——7-2 注记边界，MVP 直传 header 信任形态维持——OD-8 登记）

**验证标准/Validation Criteria:**
- [ ] document parse/versions 端点 X-Tenant-ID 必填断言（缺头 → 422）
- [ ] 跨租户隔离验收场景（上传→异租户查询 404；**given 形态与防坑注记[R3]**：A 租户上传走真实 document_upload_service 链；**同租户正查 200 对照断言必须有**——7-1 CR6-2 假绿先例[given 租户与请求头租户分叉→find miss→弱断言恒绿]，A/B 两租户显式分置+正查对照防分叉）
- [ ] 6.1-DF4（BLM 租户维度贯通）注记顺延维持（多租户 Story V1 归宿——本 Story 仅 header 透传面）

### AC-6: openapi.yaml 契约与 API 契约测试

**Given** docs/api/openapi.yaml 为手工维护 SSOT（openapi: 3.1.0，34 paths，servers `http://localhost:8000/api/v1`）
**When** 7-2 新增端点族
**Then** 契约治理生效：
- **新增 14 个 path 补入 openapi.yaml**：/documents/{document_id}/parse、/documents/{document_id}/versions、/plans/{plan_id}/trace、/tools/{slug}/execute、/tools/{slug}/schema、/agents/{agent_id}/run、/plans/generate、/plans/{plan_id}、/plans/{plan_id}/export、/checkpoints、/checkpoints/{plan_id}/{checkpoint_no}、/checkpoints/recover、/archive/query（13 域 path——R1 勘正补入 /archive/query）+ /system/health（**新增**——R1 勘正：yaml 既有 `/health` 实为 embedding API server 契约[tags [embedding]+EmbeddingHealthResponse，:1031-1050]，消费方 `test_api_contract_embedding.py:34` 断言存在，**原样保留不改名**；本 Story /system/health 以新 path 入 yaml）——**path 不带 /api/v1 前缀**（servers 已含——新增 path 按规范形态写；注记：yaml 既有 /api/v1/search×3 自带前缀与 servers 拼接构成双前缀预存怪癖，预存不一致归 OD-5 契约治理专项不动）
- **漂移修正（仅一处，存量其余漂移 defer）**：`/documents` GET 列表 yaml 有而实现无——裁定从 yaml 删除（无实现契约即死契约；OD-5 登记；R1 实测 grep 零契约消费方，删除零波及）
- 新增 path 全部含 OpenAPI 3.1 契约要素：operationId/请求体 Schema/响应 Schema/错误响应（401/404/422 引用 components）/security 声明（豁免面除外）；**成功状态码钦定[R6]**：新增端点成功响应全部 200（动作执行/查询语义非资源创建——yaml 既有 201 仅资源创建型先例[创建快照 :115/创建角色 :274/工具版本注册 :1209——R7 补全枚举]，本 Story 13 端点无资源创建型；既有 crawler POST /tasks 201 不动）；**设计豁免端点（login/health）显式 `security: []` 写法**（防全局 security 引入时豁免面漂移——R6 措辞；metrics 无 yaml 契约[OD-14 确定缺口=monitoring 1]不适用本条款[R8 限定——防 dev 误补 metrics 契约与 OD-14 冲突]）
- API 契约测试（`tests/contracts/test_api_contract_rest_api.py`）双形态对齐先例：yaml 消费型（`read_from_filename` + `openapi_spec_validator.validate` + expected_paths 断言）+ TestClient 行为型（端点存在性+响应格式——test_api_contract_document_upload.py:79-162 先例；**行为型按端点 Task 逐族补入——R3 拆分定谳**：Task 0 仅 yaml 消费型+既有端点行为型，新端点行为型随 Task 1-5 落地）
- **Schemathesis 深度契约测试归 Story 7-6**（schemathesis ^3.19 已在 dev 依赖但零使用——7-2 不启用，7-6 专项承载；epics NFR 覆盖注记）

**验证标准/Validation Criteria:**
- [ ] openapi_spec_validator 校验通过（3.1.0 合法性）
- [ ] 新增 14 path 契约断言全绿（yaml 消费型）
- [ ] TestClient 行为型断言：每端点族 ≥1 端点存在性+响应格式
- [ ] 既有 13 API 契约测试文件零回归（R1 实测锚定：/health 消费方 test_api_contract_embedding.py:34 存在→**保留不改**；/documents GET 零消费方→删除零波及）

### AC-7: REST 并发安全与长驻面适配

**Given** API 服务为长驻进程（与 CLI 一次性进程的本质差异——组合根内显式触发器注记命中）
**When** REST 并发入口激活
**Then** 长驻面适配生效：
- **6.1-DF6① 清偿（并发双跑守卫）**：BLM 同 plan_id 并发双跑的 482 守卫竞态（守卫竞态窗口=全程，asyncio.gather 实证双过守卫）——**API 层 per-plan_id 互斥**：plans 路由内 `dict[str, asyncio.Lock]` + 全局 `asyncio.Lock`（保护字典本身）实现 plan 级串行化；**asyncio.Lock 必须类变量/模块级**（CLAUDE.md Gotcha——实例变量协程间不共享）
- **SINGLETON→SCOPED 迁移（7-2 消费面，双对象——R1 重设计）**：`traceability_tree_service`（:2036——**捕获主体**：SINGLETON 捕获 strategic_archive_service/document_repository 等 SCOPED 依赖，触发器注记 :2028-2030 所在注册块）+ `traceability_tree_use_case`（:2065——GET /plans/{plan_id}/trace 消费方）**双注册块 lifetime 迁移 SCOPED**（仅迁 use_case 不解决捕获——R1 评审员定谳）；**机制诚实注记**：`clear_scoped()` 生产零调用（resolver 生产未接线——resolver.py:253；组合根 5-4 DC-7/:3258 同款先例注记「SCOPED≡SINGLETON」），当前 SCOPED 与 SINGLETON 行为等价——本迁移为**生命周期声明语义正确化**（触发器注记兑现+未来接线时自动生效），真实 per-request 隔离归 clear_scoped 接线专项（OD-15 defer；per-request clear 中间件**并发不安全**[进程级 `_scoped_context` dict 在途请求互毁，R1 推演定谳]，contextvar 级 scope 绑定为正解=真重构超 Story 面）；`executive_view_service` :2087 等非 7-2 消费面注记顺延（surgical）——**传播注记**：`analyst_view_service`（:2133，SINGLETON）捕获 traceability_tree_service，迁移后成为新 SINGLETON-captures-SCOPED 实例，注记顺延同待遇；`document_repository` 已有 `_SessionScopedDocumentRepository` 包装（:2048-2055）会话按调用创建——捕获的实际风险本已被工程化缓解（比例感注记，迁移为声明正确化非紧急修复）
- **6.1-DF6②③ 注记 defer（OD-7）**：`BlmPlanningService._runs` 零治理×长驻无界增长与孤儿 PlanningStarted 事件序——修复波及 BLM 服务层/图节点拓扑，超出接口层 Story 面，defer 至 BLM 长驻专项（deferred-work 处置注记承载）
- **6.5a-DF2 注记（L0 撕裂文件）**：同 plan_id 同秒并发导出的 L0 撕裂风险在 REST 并发面同样可达——Markdown 链撕裂窗口注记维持 defer（修复路径受端口契约 docstring 冻结表述制约——台账既有裁定维持）
- **6.4-DF2 残余（save 写路径 fallback 集成场景）**：本 Story 集成测试面覆盖（REST 长驻会话与 CLI 无会话双形态交叉）→ 顺手清偿或注记残余（dev 实测裁定）

**验证标准/Validation Criteria:**
- [ ] 并发双跑验收/集成场景：同 plan_id 两并发 generate 请求——恰一成功一 409（482 经 API 锁前置化；per-plan 锁突变注入验证判别力；**时序注记**：B 阻塞时长=A 全程[真实 LLM 60s 级]，409 来自锁释放后 482 守卫见已完成态[blm_planning_service.py:254-260 `_runs.get(plan_id).completed_steps > 0`]非超时——R1 推演定谳；409 响应可附 Retry-After 头（业界惯例[IETF idempotency-key 草案]——dev 实测裁定，成本趋零，R6-11 注记随 R7 补传；Retry-After 为**可选实现不进 AC-4 双头断言**[双头不扩三头——R8 注记]）；无 Key 环境动态 skip 归类）
- [ ] traceability_tree_service+traceability_tree_use_case lifetime=SCOPED **双断言**（组合根 PortSpec lifetime 字段——声明面锚定，归 Task 2 🔴红阶段编写）
- [ ] SCOPED 迁移零回归：既有 traceability 消费方（CLI/单测）全绿（行为等价下天然成立——声明面迁移注记）

### AC-8: 性能与并发口径

**Given** REST API 框架（create_app 装配 + 路由 + 认证 + 序列化路径）
**When** 性能采样与并发测试
**Then** epics:2672-2674 口径满足：
- **API 响应延迟 P95 < 800ms**——口径锚定 epics Story 7.2 TDD 要求（prd 无 API 专用 P95；**可用性双源消歧注记**：epics「≥99%」vs prd NFR-IF-05「≥99.5% V1」——以 prd 为准口径注记，可用性属运维面指标，7-2 以错误响应契约+零回归承载）
- **采样面冻结**：轻量查询端点（/system/health、/tools/{slug}/schema、/checkpoints 列表类）——**经 `httpx.AsyncClient(transport=ASGITransport(app))` in-process 形态**（排除 uvicorn/网络开销，测 API 层自身开销；httpx ^0.27 既有依赖；**20 轮采样为 Story 自定口径**——7-1 R1-F9 同款注记；P95 取法：升序第 `ceil(0.95×20)=19` 个 1-based、`time.monotonic()` 差值——7-1 R3-8 先例）
- **并发请求 ≥50**：50 并发轻量请求（asyncio.gather + AsyncClient）全部成功（2xx）
- 重 LLM 端点（agents/run、plans/generate 真实面）响应时长由各自用例性能窗承载（BLM 60s 窗先例），不在此口径

**验证标准/Validation Criteria:**
- [ ] 验收性能场景：20 轮 in-process 采样 P95 < 800ms
- [ ] 验收并发场景：50 并发全部 2xx
- [ ] 采样含认证路径（token 注入 header——认证 dependency 开销计入口径）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] **本 Story 零新增领域事件**——REST 是接口层薄壳，领域事件由所消费用例既有发布（DocumentParsed/ToolExecuted/CheckpointRecovered 等），事件面不变
- [ ] 核验：`configs/event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` 零 diff

#### 数据模型 (Data Models)
- [ ] **请求/响应 Pydantic Schema**：新增端点族各定义请求体（PlanGenerateRequest{agent_id, task, plan_id?}/CheckpointRecoverRequest{plan_id, checkpoint_no, mode?, confirmed_by?}[用例另有 correction: CorrectionRecord|None 缺省 None——REST 请求体静默裁剪注记，R6]/ToolExecuteRequest{input_data, session_id?, timeout?}——**cost_budget 删除[R6 勘正]**：ToolCall 四键/ExecutionContext 六键均无该字段无透传落点（CLI 侧 CommandContext 预算台账是另一体系，禁塞 extensions——发明语义），timeout→ExecutionContext.timeout_sec 为合法可选映射[dev 裁定] 等）与响应 Schema（对齐用例返回类型字段——BlmPlanningStatus/CheckpointSummaryView/ToolResult 序列化形态）——文件位 `src/interfaces/api/` 各域路由文件内或 `schemas` 集中（**裁定：随域路由文件内聚定义**，对齐存量 auth.py/tools.py 内聚先例；architecture.md:2143-2153 钦定的 v1/schemas/ 目录结构 defer——存量平铺形态现实层优先，OD-4 登记）
- [ ] **统一错误响应模型**：新增端点错误响应统一 import 共享 ErrorResponse（`src/interfaces/api/shared_models.py:12` 唯一定义——R1 勘正：sisys-uni-exception-design「5 文件重复应合并」债务**已清偿**[设计文档 :30 标注 ✅]，auth/equilibrium_security 等均 import 共享；零新建零收敛动作）
- [ ] UUID/Decimal/datetime 序列化：Pydantic jsonable_encoder 既有机制（FastAPI 内建）——无需 CLI 侧 default=str 等价特判（框架红利注记）

#### 统一端口定义注册与管理 (Port Contract)
- [ ] **本 Story 零新增端口**——仅消费既有端口（下表 SSOT，行号 2026-11-21 主会话独立实测）+ **2 处 lifetime 迁移**（traceability_tree_service :2036 + traceability_tree_use_case :2065 双对象——AC-7 R1 重设计）

**端口消费 SSOT 表（唯一事实源——15 行消费对，18 唯一端口——R1 勘正计数）：**

| 端点族 | 端点 | 消费端口（组合根注册名:行号） | 签名要点 |
|--------|------|------|----------|
| auth | login/refresh/logout/me | `auth_service`（:514）+ `permission_service`（:530，roles 端点族） | authenticate/verify_token/refresh_token/logout 既有 |
| system | metrics | `metrics`（:898） | collect() -> bytes Prometheus |
| document | parse | `document_parsing_service`（:1377） | parse_document(document_id: UUID, tenant_id: str) -> Document |
| plan | trace | `traceability_tree_use_case`（:2065，**SCOPED 双对象迁移**——service :2036 同迁） | execute(*, plan_id: str, depth: int = 4)——plan 域（OD-10 域迁） |
| document | versions | `document_repository`（:1180） | list_versions(document_id, tenant_id) |
| tool | execute | `tool_execution_service`（:2747） | execute(tool_id: UUID, tool_call, context) -> ToolResult |
| tool | schema | `tool_registry_service`（:2604）+ `skill_loader`（:2881） | slug→SLUG_TO_TOOL_ID→get_tool(tool_id=)；load_sop→input_examples |
| agent | run | `agent_workflow_use_case`（:3184） | execute(agent_id: UUID, task: str) —— **agent_id 非 role**（OD-1） |
| plan | generate | `blm_planning_use_case`（:3524） | execute(agent_id: UUID, task: str, plan_id: str \| None = None) —— **plan_id 为 str** |
| plan | status | `blm_planning_status_use_case`（:3548） | execute(plan_id: str) -> BlmPlanningStatus —— **6.1-DF5 首激活** |
| plan | export | `report_generation_use_case`（:3610）+ `pdf_report_generation_use_case`（:3714） | execute(*, plan_id: str) / (+brand_template_name) —— **6.5a-DF1 清偿**；响应=StrategicReport 元数据 JSON（R6 定谳） |
| checkpoint | list | `checkpoint_list_use_case`（:2530） | execute(*, plan_id) -> list[CheckpointSummaryView] |
| checkpoint | show | `checkpoint_recovery_use_case`（:2514 预览面） | execute(*, plan_id, checkpoint_no) 两参必填 |
| checkpoint | recover | `checkpoint_recovery_execute_use_case`（:2542） | execute(*, plan_id, checkpoint_no, correction=None, mode=None, confirmed_by="", created_via="use_case")——confirmed_by 空串 242；**REST 端点显式传 created_via="api"**（覆盖 use_case 缺省）/confirmed_by 取认证用户标识（覆盖空串缺省） |
| archive | query | `blm_chain_trace_use_case`（:2573） | execute(*, plan_id, include_blob=False) |

- [ ] 端口消费契约测试：`tests/contracts/test_port_contract_rest_api.py`——逐一断言 **18 注册名**可达（**零 IO 直查形态**，`_global_registry.get(name)` PortSpec 断言——7-1 Subtask 0.4 同款；**全绿入库**）+ lifetime **双断言**（traceability_tree_service+use_case SCOPED——**归 Task 2 🔴红阶段编写**[迁移未做时断言红]，防 Task 0→2 间 CI 可见红窗：7-1 验收红为 CI 不可见形态[服务不可达即 skip]，契约红不同构——R1 评审定谳）
- [ ] 控制器依赖注入方向：路由工厂函数形态 `create_*_router(service=..., get_current_user_override=None)`（存量 create_auth_router/create_document_upload_router 双先例）——**interfaces 层禁止 import composition_root**（importlinter 传导禁令）；服务经工厂参数注入，装配发生在 entrypoints/api_app.py 或路由模块内的 lazy resolve 三级 fallback（document_upload.py:150-160 先例：override > 注入 > resolver lazy）
- [ ] 跨模块调用仅依赖抽象：路由类型注解引用 application/domain 层类型（interfaces → application/domain 方向合法）

#### 端口契约清单执行约束（强制）
- [ ] 上表是唯一事实源——**15 行消费对 18 唯一端口**（R1 勘正计数：tool schema 1 端点消费 2 端口[registry+loader]、plan export 1 端点消费 2 用例[markdown+pdf]、auth 族 1 行消费 2 端口[auth_service+permission_service]——3 行双端口使端口实例 18=15+3；激活面 3 端口[auth/permission/metrics]+新增端点消费 15 端口），实现 Task 禁止改用其他注册名或绕过 resolve 直构实例
- [ ] 禁止新增未登记端口，禁止语义重复端口
- [ ] 契约测试未通过不得进入实现 Task 收尾

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增/修改的领域异常必须在 Task 0 中完成设计，禁止在实现 Task 中临时定义。

- [ ] **本 Story 零新增领域异常**（`src/domain/exceptions/` 零 diff）——消费既有异常体系（**消费面 10 行——R6 扩**：补登 PlanningNotFound 480/ToolNotFound 380/AgentNotFound 443 三行既有异常，均为端点首要 miss 态），经 EXCEPTION_HTTP_MAP（exception_handlers.py:160）自动映射：

| 异常 | code | HTTP | 触发场景（本 Story） |
|------|------|------|---------------------|
| `NotFoundError` | EXCEPTION_202 | 404 | documents/{id} 不存在（parse/versions **端点层 find() 前置查询锚定**——端口宽语义不承担，AC-4） |
| `PlanningNotFoundError` | EXCEPTION_480 | 404 | plans/{plan_id} 状态无记录——用例自抛（get_blm_planning_status.py:56[R7 勘正行号]），映射 exception_handlers.py:314（**R6 勘正**：原表归 NotFound 202 错位——断言 error.code 须精确 480） |
| `ToolNotFoundError` | EXCEPTION_380 | 404 | /tools/{slug} 未知 slug——get_tool_id miss 返 None（skill_manifest.py:49）**端点自 raise ToolNotFoundError**（与仓储 get_by_id miss 同码一致，映射 :256；**R6 补行**——注意其继承 NotFoundError 但 code 独立，断言须精确 380） |
| `AgentNotFoundError` | EXCEPTION_443 | 404 | /agents/{agent_id} 不存在——用例首步 get_by_id None 自抛（run_agent_workflow.py:136 raise 行[R7 精确化，调用行 :134]，映射 :295；**R6 补行**） |
| `ValidationError` | EXCEPTION_201 | 400 | 请求语义校验（用例层透传） |
| `EntityValidationError` | EXCEPTION_242 | 400 | checkpoint recover confirmed_by 空串（:2542 用例守卫）/plan_id 值域（用例层共面守卫——6.9-R1-DF1 共面注记） |
| `AuthenticationError` | EXCEPTION_401 族 | 401 | token 缺失/伪造/过期（get_current_user 守卫） |
| `PermissionDeniedError` | EXCEPTION_403 族 | 403 | 角色不足（roles 端点族） |
| `ConflictError`（BLM 并发 482） | EXCEPTION_482 | 409 | 同 plan_id 并发双跑（AC-7 per-plan 锁前置化后仍保留——锁防竞态窗口，482 为语义兜底） |
| `BusinessRuleViolationError` | EXCEPTION_422 族 | 422 | 业务约束（用例透传） |

- [ ] **零手动 HTTPException**（R1 勘正：auth.py 全文件零 HTTPException 实证——认证失败 raise AuthenticationError[oauth2_scheme auto_error=False 形态，:147]，401+`WWW-Authenticate` 头由 ExceptionHandlers :453-454 统一附加；本 Story 全端点同形态零例外，**禁止任何 handler raise HTTPException**）
- [ ] 消息安全性：错误响应体三字段（code/message/context）既有机制复验
- [ ] 异常路径 Gherkin 场景纳入验收（AC-4 场景）
- [ ] 既有异常测试零回归：`pytest tests/unit/domain/exceptions/ tests/unit/interfaces/api/test_exception_handlers.py -v` 全绿

#### API 契约 (API Contract)
- [ ] `docs/api/openapi.yaml` 新增 14 path + 单漂移修正（AC-6 冻结面——R1 勘正口径）——**本 Story 是 Epic 7 内唯一动 openapi.yaml 的面**（7-1 零 diff 先例终结；7-3 Gateway 不扩契约）
- [ ] API 契约测试：`tests/contracts/test_api_contract_rest_api.py`（双形态——AC-6 冻结）
- [ ] API 版本管理：`/api/v1/[resource]` URL 路径版本（既有 servers 声明）

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

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

**本 Story 附加分层约束（D1 方案 A）**
- `create_app()` 工厂住 `src/entrypoints/api_app.py`（既有 D1 方案 A 上移形态——本 Story 扩展挂载，不动工厂位置）；路由/中间件适配器住 `src/interfaces/api/`（**新增文件平铺对齐存量 15 个 .py 形态**——architecture.md:2102-2153 钦定的 api/v1/ 子目录结构 defer，OD-4 登记）
- `src/interfaces/api/` **禁止 import `src.composition_root`**（importlinter 传导禁令——.importlinter:72-78 同款）；服务注入经工厂参数或 lazy resolve 三级 fallback（document_upload.py:150-160 先例）
- fastapi/httpx 依赖仅入 interfaces/entrypoints/tests 层

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_rest_api.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_rest_api.py`
- [ ] 业务方评审通过（人工评审环节——dev 无权勾选，留待 review 阶段承载）
- [ ] 所有场景覆盖（Happy Path + Edge Cases，**最终态 21 场景**：AC-1×2 / AC-2×8 / AC-3×3 / AC-4×2 / AC-5×1 / AC-7×1 / AC-8×2 / 收尾×2，AC-6 契约面由 contracts 目录承载不入场景计数——Task 0 交付 17 个业务场景，AC-8×2 与收尾×2 由 Task 9 追加；**AC-2×8 场景↔13 端点覆盖映射**[R1 补注记，Subtask 0.4 按此撰写防漏]：parse+versions 同场景[document 域前置查询链]、trace 独场景、execute+schema 同场景[slug 链]、run+generate 同场景[LLM skip 同类]、status+export 同场景、checkpoint list/show 同场景+recover 独场景[2]、archive query 独场景）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试；**禁 `@pytest.mark.asyncio`**（context 数据丢失）
- **R6 模板对齐七要点**（模板 test_acceptance_postgresql_relational_layer.feature/.py + 7-1 R6 实战）：①`# language: zh-CN` 头+功能/背景块；②场景按 AC 三行横幅注释分节；③场景命名中文短句无 AC 前缀（条件-结果命名法）；④步骤文本纯中文业务语言+参数内嵌（**禁引号字面量/parsers.re**）；⑤`@scenario` 显式逐场景绑定（**禁 scenarios() 自动绑定**——pytest-bdd 双收集陷阱）；⑥fixture 驱动分区结构+文件头 docstring（Story 号+真实服务声明+运行命令+租户隔离说明）；⑦共享 dict 跨步状态（response: dict[str, Any] fixture）
- **HTTP 级装配形态**（test_acceptance_document_upload.py:50-78 先例[R6 勘正起点行]）：`test_client` fixture 装配链=裸 FastAPI → add ExceptionContextMiddleware → register_exception_handlers → **路由工厂 DI**（服务 AsyncMock/真实实例注入）→ include_router → TestClient；认证 override（`get_current_user_override` 返回固定 TokenPayload）；`X-Tenant-ID` header 承载租户
- **真实服务面**：验收对真实可达面（health/login 链/document parse 真实链/checkpoint 族/plan 状态/export）走真实服务+动态 skip（`_require_services` 形态探活——CI root 恒 skip 教训 efd0f11d）；纯 HTTP 适配层断言（路由/状态码/错误体）可用 AsyncMock 子模式（CLAUDE.md 验收强制真实服务的例外=HTTP 适配层既定子模式，记忆 acceptance_test_patterns 口径）
- **延迟 import 纪律**：新交付模块一律步骤函数体内 import（收集期零 error，红形态=运行期 ImportError）
- **teardown**：真实服务面创建的资源（PG 行/测试用户/L0 文件）定向清理（「断言失败也执行」）
- `pytestmark` = markers + `xdist_group(...)` 串行组

#### 前置留项清单（14 条逐条裁定落档）

> **来源：** deferred-work.md 六条直接锚定 7-2 条目 + 7-1 顺延注记 + 组合根触发器注记 + 三向定夺（调研 Agent C 全文摘录+主会话核验）。
> **成功标准：** Task 0 将本表裁定逐条落档 deferred-work.md（历史行不改写，追加处置注记——先例形态）。

| # | 留项（行号） | 裁定 | 处置与依据 |
|---|-------------|------|-----------|
| 1 | 6.1-DF5 BLM 状态查询零消费（:330） | **触发，7-2 清偿** | GET /plans/{plan_id} 首激活 blm_planning_status_use_case（:3548）——AC-2/SSOT 表承载 |
| 2 | 6.1-DF6 REST 回头清单三项（:331） | **部分清偿** | ①并发双跑守卫（482 竞态）→ API 层 per-plan_id 锁清偿（AC-7）；②_runs 零治理×长驻无界增长与③孤儿 PlanningStarted 事件序 → defer BLM 长驻专项（OD-7——修复波及 BLM 服务层超出接口层面） |
| 3 | 6.4-DF2 残余 save 写路径 fallback（:362） | **顺手清偿** | 集成测试双形态交叉面（REST 长驻会话×CLI 无会话）覆盖 save fallback；dev 实测裁定清偿或注记残余 |
| 4 | 6.5a-DF1 REST 导出面无契约（:369） | **触发，7-2 清偿** | POST /plans/{plan_id}/export（markdown+pdf 双用例）+ openapi.yaml 契约——AC-2/AC-6 承载 |
| 5 | 6.5a-DF2 L0 撕裂文件（:370） | **注记维持 defer** | 义务随 REST 面立项维持；修复路径受端口契约冻结表述制约（台账既有裁定）；7-2 注记并发面可达性 |
| 6 | 6.9-R1-DF1 守卫共面（:409） | **注记（共面确认）** | REST 输入 UUID 校验经 Pydantic 类型注解 422 承载（与 CLI 242 形态不同）；领域守卫在用例层共面不变 |
| 7 | 6.1-DF4 BLM 租户维度（:329） | **顺延** | 7-2 仅 X-Tenant-ID header 透传面（AC-5）；多租户贯通归 V1 Story |
| 8 | 6.1-DF7③ 错误响应设计（:332） | **触发注记** | 7-2 错误响应体含 context 字段（失败信息不丢失面）；①②残余归可观测性专项维持 |
| 9 | 6.3-R1-DF2 stage_id 值域（:349） | **顺延** | 7-2 端点面不引入 stage_id 参数（checkpoint 入参=plan_id+checkpoint_no 复合定位） |
| 10 | :115 create_app 5 router 未挂载 | **触发，7-2 清偿（4/5）** | auth/monitoring/crawler/audit 挂载（AC-1——audit 5+crawler 4 端点认证实质改造[R6 勘正：crawler 连工厂认证参数都无]+monitoring 挂载形态冻结）；equilibrium_security defer（3 失效 impl——:126 等保专项，OD-6） |
| 11 | :116 exception_metrics 未接线 | **顺手清偿或注记** | 一行接线成本（register_exception_handlers 传 metrics）；dev Task 1 实测裁定（metrics 端口可用即接线） |
| 12 | :125/:129 三向定夺（StrategicAnalysisUseCase/orchestration_service/data_pipeline） | **触发，Task 0 定夺承载（R1 预判改判：defer 为大概率落点）** | 7-2 端点矩阵零消费三者；R1 实测引用面：StrategicAnalysisUseCase src 仅 2 处 docstring 但 **tests 7 文件实质引用**（test_strategic_analysis_usecase/datasource 实例化+4 架构断言文件）、orchestration_service **tests 3 文件 resolve 消费**（prefect/langgraph 集成+单测）、data_pipeline 为 orchestration_service 内 task_type Literal（:26/:68-71）随主体一体定夺——「零生产引用」删除前提不成立（测试爆炸半径非零）；Task 0 按 grep 全仓（含 tests）执行定夺：零引用则删、有引用则 defer 落档（R1 预判后者） |
| 13 | :191 谓词键预设白名单 | **触发注记** | 7-2 REST 入口不预设 retry_count/executed_phases 初始 state 键（agent run 请求体不含引擎内部键——白名单过滤注记落档） |
| 14 | 组合根 SINGLETON→SCOPED 触发器（traceability :2065/executive_view :2087 注记） | **部分清偿** | traceability_tree_service（:2036 捕获主体）+traceability_tree_use_case（:2065）**双对象迁移 SCOPED**（7-2 消费面——AC-7 R1 重设计）；executive_view_service（:2087）/analyst_view_service（:2133 新捕获实例，R1 传播注记）等非消费面注记顺延（surgical） |

- [ ] 范围外注记：7-1-DF1（agent_cli 迁移）/DF2（system/config CLI 命令组——**REST 面的 /auth/login、/system/health、/system/metrics 归本 Story**，interface-design §8.2.10 钦定；CLI 面维持 DF2 归宿）——7-1 OD-8/OD-9 的「端口签名现实层优先」原则在本 Story 端点参数设计中直接继承（agent_id 非 role、plan_id+checkpoint_no 复合定位）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕（端点冻结矩阵 + 端口消费 SSOT 表 + 异常消费表 + openapi.yaml 契约面 + 前置留项 14 条裁定）
- [ ] Gherkin 验收测试已编写，运行确认失败（🔴 红阶段验证——延迟 import 纪律下红形态=运行期 ImportError/路由不存在）
- [ ] 规范文档通过自动化校验（契约测试绿+锚点行号主会话独立复核全命中；人工评审归 review 阶段）
- [ ] **链路接线断言清单**已定义——2 处 lifetime 迁移（traceability service+use_case SCOPED——断言归 Task 2 红阶段）+ 4 处 router 挂载（auth/monitoring/crawler/audit）组合根/api_app 装配验证；零新增端口/事件/中间件

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**
>
> **变异步骤适用性：** 变异注入适用于含生产代码交付的实现 Task（1-6）；纯测试/验证 Task（0/7/8/9）无生产代码可突变，以断言判别力自证（7-1 R3-10 先例）。

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
| **TDD 单元测试** | 应用工厂 | create_app 挂载扩展（4 router+新路由族）/health/metrics 可达 | `tests/unit/interfaces/api/test_app.py`（既有扩展） | Task 1 |
| **TDD 单元测试** | document 端点 | parse/versions 两端点+find() 前置查询 404 锚（_make_app 工厂+AsyncMock 服务注入——test_archive_routes.py 先例） | `tests/unit/interfaces/api/test_document_routes.py` | Task 2 |
| **TDD 单元测试** | tool 执行端点 | execute/schema（slug 解析链/input_examples 透传） | `tests/unit/interfaces/api/test_tool_execution_routes.py` | Task 3 |
| **TDD 单元测试** | agent/plan 端点 | run/generate/status/export/trace（per-plan 锁含于此） | `tests/unit/interfaces/api/test_agent_plan_routes.py` | Task 4 |
| **TDD 单元测试** | checkpoint/archive 端点 | list/show/recover/query（created_via="api"/confirmed_by 缺省） | `tests/unit/interfaces/api/test_checkpoint_archive_routes.py` | Task 5 |
| **TDD 单元测试** | system 路由 | health 轻量形态 | `tests/unit/interfaces/api/test_system_routes.py` | Task 1 |
| **TDD 单元测试** | 错误响应矩阵 | 异常族→HTTP 状态码/响应体三字段/双头 | `tests/unit/interfaces/api/test_exception_handlers.py`（既有扩展） | Task 6 |
| **TDD 契约测试** | 端口消费接线 | 18 唯一端口注册面可达（零 IO 直查；lifetime 双断言归 Task 2 红） | `tests/contracts/test_port_contract_rest_api.py` | Task 0 |
| **TDD 契约测试** | API 契约 | yaml 消费型（14 新 path+validator，Task 0）+TestClient 行为型（**按端点 Task 逐族补入**——R3 拆分定谳） | `tests/contracts/test_api_contract_rest_api.py` | Task 0+1-5 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收（17 场景，Task 9 补至 21） | `tests/acceptance/test_acceptance_rest_api.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | R6 七要点+HTTP 级装配+真实服务动态 skip | `tests/acceptance/test_acceptance_rest_api.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单+性能并发 | 同上两文件追加场景 | Task 9 |
| **SDD 架构验证** | 六边形+认证覆盖 | 分层断言/全端点认证 dependency 断言/fastapi 零入 domain-application/既有测试零回归 | `tests/unit/architecture/test_arch_rest_api.py` | Task 8 |
| **集成测试** | REST×真实服务 | 真实 bootstrap+TestClient 全链（login→token→端点/document 真实链/checkpoint 族/并发双跑） | `tests/integration/test_integration_rest_api.py` | Task 7 |

> **注记（epics 名义文件 ↔ 实际落位映射）：** epics_v1.0.md 钦定 `tests/unit/interfaces/test_rest_api.py`/`test_rest_api_integration.py`/`test_rest_api_e2e.py`——实际落位按仓内目录现实与域拆分调整如上表；**E2E 语义由验收测试承载**（7-1 OD-5 同款），`tests/e2e/` 维持空置；四目录回归口径 `pytest tests/unit tests/integration tests/acceptance tests/contracts`。

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（基线不破坏——当前全量基线 15581 passed 时点 ~93%；机器载体=Makefile `--cov-fail-under=80`+CI `scripts/check_coverage_gates.py`）- **P0 阻断门禁**
- [ ] **接口层覆盖率 ≥85%**（epics 7.2 钦定）- **P1 阻断门禁**。**测量面口径（7-1 R1-F8 先例沿用）：落地为「本 Story 新增 `src/interfaces/api/` 文件伞形达标 ≥95%」**——`src/interfaces/api/` 全目录含存量 15 文件非本 Story 可控，以「合并后不低于合并前基线」承载；**机器载体注记：`scripts/check_coverage_gates.py` 分层清单无 src/interfaces 档位**——Task 9 收尾实测新增文件覆盖率，≥85% 达标则登记扩档建议（CI Story 承载）；Makefile :279-281 禁止 `--cov=src.<layer>` 形式
- [ ] **新增文件行覆盖率 ≥95%**（6-9 先例口径）
- [ ] mypy 基线零新增错误（795 文件零错误基线）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查——归 review 阶段承载）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|----------|
| **事务隔离** | 集成测试使用 transaction rollback / savepoint | 数据泄漏导致随机失败 |
| **Schema 自创建** | fixture 内完成 Schema 初始化 | 依赖外部迁移，环境不一致 |
| **资源唯一性** | 测试数据使用 UUID 前缀租户（TestTenant）+ X-Tenant-ID header | ID 冲突或状态污染 |
| **外部服务隔离** | 真实服务面验收 teardown 定向清理自建资源（PG 行/测试用户/L0 文件） | 真实数据被污染 |
| **并行隔离** | 并行测试 UUID 前缀隔离资源 | 资源冲突导致并行失败 |
| **清理粒度** | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| **依赖声明** | Fixture 必须显式声明依赖 | 并行时清理顺序不确定 |
| **asyncio 上下文** | asyncio.Lock 类变量/模块级（**per-plan 锁纪律**——AC-7）；BDD 步骤用 `event_loop.run_until_complete()` | 锁失效或 context 丢失 |
| **pytest-asyncio** | BDD 步骤禁 `@pytest.mark.asyncio`；删除 scope=module 的 event_loop fixture | 与 auto mode 冲突 |
| **TestClient 形态** | 验收/单测 in-process TestClient（同步）+ 性能面 httpx.AsyncClient+ASGITransport（异步）| 环境差异失败 |
| **app 装配隔离** | 每测试自持 `_make_app()` 工厂（test_archive_routes.py 先例）——**禁共享全局 app 实例**（路由/中间件状态污染） | 测试间耦合 |
| **真实 bootstrap** | 集成/验收真实面经 lifespan bootstrap——**禁二次 bootstrap**（ConflictError 203——7-1 懒 bootstrap 幂等双守卫教训；TestClient with 语句触发 lifespan） | ConflictError 假红 |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback/定向清理）
- ❌ autouse fixture 删除全局匹配资源（如 `test_*`）
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- ❌ 验收/集成测试 mock 领域行为（真实服务强制；HTTP 适配层 AsyncMock 子模式除外——BDD 约束节口径）
- ❌ asyncio.Lock 实例变量形态（per-plan 锁必须模块级/类变量）

**验证要求：**
- [ ] 并行测试 `pytest tests/unit tests/integration tests/acceptance tests/contracts -n 8` 通过（四目录全量回归——**裸 tests/ 会挂起**，记忆口径）
- [ ] 连续 5 次运行无随机失败（5 连跑留 CI/用户本地验证——7-1 同款承载：单轮零失败+隔离复跑关键面全绿）
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 4 router 挂载+health+前缀统一 | Task 1 | 1.1-1.3 | test_app.py / test_system_routes.py |
| AC-2 | document parse/versions+前置查询 404 | Task 2 | 2.1-2.3 | test_document_routes.py + 验收 |
| AC-2 | tool execute/schema | Task 3 | 3.1-3.3 | test_tool_execution_routes.py + 验收 |
| AC-2 | agent run + plan generate/status/export/trace | Task 4 | 4.1-4.5 | test_agent_plan_routes.py + 验收 |
| AC-2 | checkpoint list/show/recover + archive query | Task 5 | 5.1-5.3 | test_checkpoint_archive_routes.py + 验收 |
| AC-3 | 认证全覆盖+login 链+豁免面 | Task 1-6 | 各 Task 端点内 + Task 6 集中 | 架构断言 + 集成 |
| AC-4 | 错误响应契约矩阵 | Task 6 | 6.1-6.3 | test_exception_handlers.py + 验收 |
| AC-5 | X-Tenant-ID 租户契约 | Task 2 | 2.2 | test_document_routes.py + 验收 |
| AC-6 | openapi.yaml+API 契约测试 | Task 0 | 0.4-0.5 | test_api_contract_rest_api.py |
| AC-7 | per-plan 锁+SCOPED 迁移 | Task 4 / Task 2 | 4.2 / 2.2 | 单测+集成+契约 lifetime 断言 |
| AC-8 | P95<800ms+并发 50 | Task 9 | 9.1-9.2 | 验收性能并发场景 |
| 全 AC | 收尾完成清单 | Task 9 | 9.3-9.4 | 验收收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部（规范源头）；AC-6（契约）；前置留项清单

> **目的：** 在进入代码实现前，明确端点冻结矩阵、端口消费 SSOT、异常消费契约、openapi.yaml 契约面、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 冻结端点矩阵表（AC-2 列 13 端点 + 挂载激活 4 router + health——实现禁增删端点路径）
- [ ] Subtask 0.2: 编写端口消费契约测试 `tests/contracts/test_port_contract_rest_api.py`（**18 唯一端口注册面可达断言——全绿入库**；零 IO 直查形态对齐 7-1 Subtask 0.4 先例；lifetime 双断言归 Task 2 🔴红阶段编写[见 Task 2]——防 Task 0→2 间 CI 可见红窗，R1 定谳）
- [ ] Subtask 0.3: 编写 API 契约测试 `tests/contracts/test_api_contract_rest_api.py`（yaml 消费型 14 新 path+validator——**红形态**：yaml 未补 path 时断言红，红绿同 Subtask 闭合[7-1 Task 0 绿色门禁先例同构]；**TestClient 行为型按端点 Task 逐族补入**——R3 定谳：先例 test_api_contract_document_upload.py:28 顶部 import 路由模块（R6 勘正：原 :20 为 fastapi import，路由模块 import 在 :28），新路由模块 Task 0 不存在→收集期 ImportError 连坐 yaml 断言，故 Task 0 仅写 yaml 消费型+既有端点行为型，新端点行为型随 Task 1-5 各族落地补入）+ openapi.yaml 补 14 path（13 域 path+/system/health）+ 单漂移修正（/documents GET 删除——R1 实测零消费方；**/health 保留**[embedding 契约，test_api_contract_embedding.py:34 消费方，R1 勘正]）+ yaml 响应契约按 AC-6 成功码钦定撰写（新增端点全部 200——R6-8 随 R7 补传）
- [ ] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_rest_api.feature`（AC-1~AC-7 共 17 个业务场景[AC-1×2/AC-2×8/AC-3×3/AC-4×2/AC-5×1/AC-7×1]，按 AC 分节横幅注释组织；AC-8×2 与收尾×2 由 Task 9 追加至最终态 21；**按 Gherkin 节的 AC-2×8↔13 端点覆盖映射撰写**——R1 注记）
- [ ] Subtask 0.5: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_rest_api.py`（R6 七要点+HTTP 级装配形态+given/when/then 全步骤骨架齐备——**若仅 given 骨架则收集期抛 ScenarioDefinitionError**[7-1 R1-F31 教训]，故要求全骨架：红形态=运行期 ImportError[新增路由模块不存在]）
- [ ] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证——红形态=运行期 ImportError：新增路由模块不存在）
- [ ] Subtask 0.7: 前置留项清单 14 条处置注记落档 `deferred-work.md`（历史行不改写追加注记）+ **三向定夺执行**（:125/:129——grep 全仓核验 StrategicAnalysisUseCase/orchestration_service/data_pipeline 引用[R1 预判：tests 7+3 文件引用实证，大概率 defer]，零引用则删除类文件+注册行并落档，有引用则改判 defer 并注记）+ 新登记 7-2-DF 族（**R1 对齐版 8 项+1 归宿，R2 勘正**：异步 job+agents status[DF1——OD-2/OD-3]、3-8 高保真 REST 面[DF2——OD-10 后段]、equilibrium_security 挂载[DF3——OD-6]、BLM 长驻含锁字典淘汰[DF4——OD-7]、compare+financial+documents 元数据查询族[DF5——OD-12，R2 增补]、P1 端点族含 /archive/timeline[R2 勘正端点名][DF6——OD-13]、激活面契约缺口[DF7 关联——OD-14]、clear_scoped 接线[DF8——OD-15]、PT-03→7-3 Gateway 面[OD-8]——OD 表对应）
- [ ] Subtask 0.8: 锚点行号复核（本 Story 引用的组合根行号/api_app 行号/openapi path 消费方实测核对——主会话独立复核）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕（端点冻结矩阵+端口 SSOT+异常消费表+契约面）
- [ ] 契约测试通过（18 端口注册面可达——**全绿入库**；lifetime 双断言归 Task 2 红阶段[R1 定谳]，无 CI 可见红窗）
- [ ] 验收测试运行失败（预期行为，红阶段确认）
- [ ] deferred-work.md 处置注记与新登记落档

---

### Task 1: 应用工厂装配扩展（挂载+health+metrics）— 含完整 TDD 循环

**关联 AC:** AC-1 / AC-3（豁免面）

#### TDD 循环 A：4 router 挂载与 health 端点

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写/扩展 `tests/unit/interfaces/api/test_app.py`（挂载断言：auth/metrics/crawler/audit router 在 app.routes 可达+路径前缀断言 /api/v1/audit、/api/v1/system/metrics）+ 新建 `tests/unit/interfaces/api/test_system_routes.py`（health 返回 200+status ok+无认证可达）+ test_crawler.py 最小 401 断言（crawler 1 端点无 token→401——**R8 补**：变异第三项「摘除认证→红」的可红锚点，原 AC-3 401 断言承载在 Task 6 时间线断链） |
| 🟢 绿 | 修改 `src/entrypoints/api_app.py`（include 4 router——audit 挂载 prefix="/api/v1/audit"；monitoring 挂载形态冻结 `include_router(create_metrics_router(...), prefix="/api/v1/system")`[router 自身无 prefix]；auth/router 工厂调用需服务注入——**lazy resolve 三级 fallback 形态** document_upload.py:150-163 先例）+ 修改 `src/interfaces/api/audit.py`（**5 端点签名补 Depends(get_current_user)——认证实质改造，R1 实证端点零挂载**）+ 修改 `src/interfaces/api/crawler.py`（**认证实质改造[R6]**：工厂加 get_current_user 可选参数+4 端点补挂 Depends——对齐 audit 同款）+ **既有 test_crawler.py 适配[R8]**（_create_app 裸装配零认证 override——改造后 23 测试函数中 ~14 端点测试 200→401 全红；适配=工厂注入 `get_current_user_override` stub TokenPayload[document_upload.py:113/:150 先例形态]，DoD「17 文件全绿」经适配达成）+ 新建 `src/interfaces/api/system.py`（create_system_router：GET /system/health 轻量实现——认证豁免） |
| 🟡 变异 | 去掉 auth 挂载→挂载断言红；health 加认证→无认证断言红；摘除 crawler 端点认证→test_crawler.py 401 断言红[R8 锚点勘正]；还原绿 |
| 🔄 重构 | 挂载段注释分节（既有 7 router / 激活 4 router / 新增路由族）；audit+crawler 认证改造收尾核验（每端点 Depends 在位——9 端点） |

- [ ] Subtask 1.1: 🔴 红 — 挂载/health 失败测试
- [ ] Subtask 1.2: 🟢 绿 — api_app 挂载扩展 + system.py
- [ ] Subtask 1.3: 🟡 变异 + 🔄 重构 — 含 :116 exception_metrics 接线裁定（metrics 端口 :898 可用即一行接线）

**完成标准/Definition of Done:**
- [ ] 4 router 全部可达 + health 端点 200
- [ ] 既有 API 测试零回归（test_app.py 既有断言+17 文件全绿）
- [ ] 覆盖率 ≥95%（新增文件）

---

### Task 2: document 端点族（parse/versions + 前置查询 404 + SCOPED 双对象迁移 + 租户头）— 含完整 TDD 循环

**关联 AC:** AC-2 / AC-5 / AC-7（SCOPED 双对象）

#### TDD 循环 A：两端点 + 前置查询 404 + 租户头 + lifetime 双对象迁移

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/api/test_document_routes.py`（_make_app 工厂+AsyncMock 服务：parse 参数透传[document_id+X-Tenant-ID]/versions 调用 list_versions/**端点层 find() 前置查询锚**：find 返回 None→端点 raise NotFoundError→404[租户过滤语义，AC-4]/认证 dependency 挂载断言/X-Tenant-ID 缺头→422）+ **lifetime 双断言红**（traceability_tree_service+use_case PortSpec lifetime==SCOPED——迁移未做时红；从 Task 0 移入，R1 定谳防 CI 可见红窗） |
| 🟢 绿 | 新建 `src/interfaces/api/documents.py`（create_documents_router：parse/versions 两端点——X-Tenant-ID Header 参数透传先例形态[6 处]+端点内 find() 前置查询）+ **组合根双对象 lifetime SINGLETON→SCOPED 迁移**（traceability_tree_service :2036+traceability_tree_use_case :2065——转绿 lifetime 双断言） |
| 🟡 变异 | parse 去租户头透传→参数断言红；find 前置查询删除→404 断言红；lifetime 改回 SINGLETON（任一对象）→契约双断言红；还原绿 |
| 🔄 重构 | 两端点共享认证/租户头构造 DRY；Schema 内聚定义 |

- [ ] Subtask 2.1: 🔴 红 — document 端点失败测试+lifetime 双断言
- [ ] Subtask 2.2: 🟢 绿 — documents.py + SCOPED 双对象迁移
- [ ] Subtask 2.3: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:**
- [ ] 两端点 OpenAPI docs 可见 + 单测全绿
- [ ] traceability service+use_case lifetime=SCOPED 双断言绿 + 既有 traceability 消费方零回归（行为等价下天然成立——声明面迁移注记）
- [ ] 覆盖率 ≥95%（新增文件）

---

### Task 3: tool 执行端点族（execute/schema + slug 链）— 含完整 TDD 循环

**关联 AC:** AC-2

#### TDD 循环 A：execute + schema

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/api/test_tool_execution_routes.py`（slug→SLUG_TO_TOOL_ID SSOT→get_tool(tool_id=) 解析链断言[**禁 get_tool(tool_name=slug) 直查——7-1 CR1-F7b 勘正同款**]/**未知 slug→get_tool_id miss 返 None→端点 raise ToolNotFoundError→404+error.code=380 断言[R6]**/execute 构造 ToolCall+ExecutionContext 透传 session+**timeout→ExecutionContext.timeout_sec==请求值断言锚定[R8]**[cost_budget 已删，R6]/schema 输出含 input_examples[skill_loader.load_sop 通路]/认证断言/ToolExecuted 结果序列化） |
| 🟢 绿 | 新建 `src/interfaces/api/tool_execution.py`（create_tool_execution_router：两端点——与既有 tools.py 版本管理面共 prefix /api/v1/tools 但独立文件独立 router） |
| 🟡 变异 | slug 解析链改直查→断言红；schema 去 input_examples 键→断言红；还原绿 |
| 🔄 重构 | slug 解析链按 SSOT 映射重写（`skill_manifest.SLUG_TO_TOOL_ID`[skill_manifest.py:41]→`get_tool(tool_id=)`[tool_registry_service.py:52 二选一签名]——**唯一映射源；禁止从 `src/interfaces/cli/` 包 import 复用**[interfaces 内跨接口子包耦合]，REST 侧独立实现同链；{slug} vs 钦定 {id} 偏离 OD-11 登记） |

- [ ] Subtask 3.1: 🔴 红 — tool 执行端点失败测试
- [ ] Subtask 3.2: 🟢 绿 — tool_execution.py 实现
- [ ] Subtask 3.3: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:**
- [ ] 两端点可达 + slug 解析链断言绿 + input_examples 透传断言绿
- [ ] 既有 tools.py 版本管理面零回归
- [ ] 覆盖率 ≥95%（新增文件）

---

### Task 4: agent 与 plan 端点族（run/generate/status/export/trace + per-plan 锁）— 含完整 TDD 循环

**关联 AC:** AC-2 / AC-7

#### TDD 循环 A：agent run + plan generate（含 per-plan 锁）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/api/test_agent_plan_routes.py`（agent run：agent_id UUID path 参数[非 UUID→422 Pydantic]+task 请求体+调用契约断言+**agent 不存在→AgentNotFoundError 443→404 断言[R6]**；plan generate：三参数透传[plan_id 为 str]+**per-plan_id 锁断言：同 plan_id 并发两请求串行化——mock 服务侧记录进入序**；482 Conflict→409 映射） |
| 🟢 绿 | 新建 `src/interfaces/api/agents.py` + `src/interfaces/api/plans.py`（generate 部分）——**per-plan 锁模块级实现**：`_plan_locks: dict[str, asyncio.Lock]` + `_locks_guard: asyncio.Lock`（模块级纪律——CLAUDE.md Gotcha；**无界增长注记**：锁字典只增不减与 6.1-DF6② _runs 同域同性质，淘汰策略归 BLM 长驻专项[OD-7 关联]） |
| 🟡 变异 | 去锁→并发串行化断言红（mock side_effect 内 `await asyncio.sleep(0)` 让渡控制+记录进入/退出序，断言区间不重叠——确定性形态）；锁改实例变量→隔离断言红（**两 app 实例共享同一 mock 服务**并发打点判别——单 app 实例下实例级锁同样串行化不可判别，R1 具体化）；还原绿 |
| 🔄 重构 | 锁逻辑收敛单一模块级函数 |

#### TDD 循环 B：plan status + export + trace（DF5/DF1 清偿+trace 端点）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 追加测试（status：plan_id str path 参数→blm_planning_status_use_case 调用契约+BlmPlanningStatus 序列化+**PlanningNotFoundError(480)→404 断言[R6 勘正——非泛 NotFound]**；export：format query 参数 markdown\|pdf 分派双用例+brand_template_name 可选透传[仅 pdf]+StrategicReport 元数据 JSON 响应[非文件流——R6 定谳]；**trace：plan_id str path 参数→traceability_tree_use_case[execute(*, plan_id, depth)] 调用契约+溯源树视图序列化[空树 build_degraded 哨兵为合法响应非 404——R6 注记]+与 /search/trace/{document_id} 语义分立注记锚——R1 域迁[OD-10]**） |
| 🟢 绿 | plans.py 扩展（status/export/trace 端点——report_generation_use_case/pdf_report_generation_use_case 分派；trace 消费 traceability_tree_use_case） |
| 🟡 变异 | format 分派错置→断言红；status 用例替换→断言红；trace 用例替换→断言红；还原绿 |
| 🔄 重构 | export 双用例分派收敛；trace 与 status 共享 plan_id 参数构造 |

- [ ] Subtask 4.1: 🔴 红 — agent/plan generate 失败测试
- [ ] Subtask 4.2: 🟢 绿 — agents.py + plans.py（generate+锁）
- [ ] Subtask 4.3: 🔴 红 — status/export/trace 失败测试
- [ ] Subtask 4.4: 🟢 绿 — plans.py 扩展（status/export/trace）
- [ ] Subtask 4.5: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:**
- [ ] 五端点可达（run/generate/status/export/trace）+ per-plan 锁并发断言绿 + 482→409 映射断言绿
- [ ] 覆盖率 ≥95%（新增文件）

---

### Task 5: checkpoint 与 archive 端点族 — 含完整 TDD 循环

**关联 AC:** AC-2

#### TDD 循环 A：checkpoint list/show/recover + archive query

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/api/test_checkpoint_archive_routes.py`（list：plan_id query 参数→checkpoint_list_use_case/空态 200+[]；show：plan_id+checkpoint_no 双 path 参数→:2514 预览面调用契约；recover：body 复合定位+mode 枚举[replay\|override]+confirmed_by 缺省取认证用户标识[TokenPayload]+**created_via 固定 "api" 断言**+242→400；archive query：plan_id→:2573 调用契约+与 /archive/plans/{plan_id} 语义分立注记锚） |
| 🟢 绿 | 新建 `src/interfaces/api/checkpoints.py` + 扩展既有 strategic_archive.py 同族或新建 archive_query 端点（**裁定：新建独立 router 挂 /api/v1/archive/query**——不动既有 strategic_archive.py 防回归；挂载在 api_app.py） |
| 🟡 变异 | recover 去 created_via="api"→断言红；show 单参数化→签名断言红；还原绿 |
| 🔄 重构 | confirmed_by 缺省链（认证用户→必填兜底）收敛 |

- [ ] Subtask 5.1: 🔴 红 — checkpoint/archive 端点失败测试
- [ ] Subtask 5.2: 🟢 绿 — checkpoints.py + archive query 端点 + 挂载
- [ ] Subtask 5.3: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:**
- [ ] 四端点可达 + created_via/confirmed_by 契约断言绿
- [ ] 既有 strategic_archive 端点零回归
- [ ] 覆盖率 ≥95%（新增文件）

---

### Task 6: 认证契约与错误响应矩阵 — 含完整 TDD 循环

**关联 AC:** AC-3 / AC-4

#### TDD 循环 A：认证矩阵 + 错误响应矩阵集中验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/interfaces/api/test_exception_handlers.py`（异常族→HTTP 矩阵：202→404/380→404/443→404/480→404[R6 三行补登——矩阵为**映射断言**（直构异常过 handler），端点单测（Task 3/4 红）为**调用契约断言**，双承载语义不同非重复，R8 注记]/201→400/242→400/482→409/401 族/403 族/422 族逐一断言+响应体三字段 error.code/error.message/error.context[或既有实际形态——**先实测锚定**]+X-Error-Code/X-Request-ID 头断言+**消息安全新增断言[R6]**：主路径 to_dict 三字段无堆栈/SQL 子串——fallback 泄露面归 OD-17 不在此断言）；新建认证矩阵断言（每端点族 ≥1 **受保护**端点无 token→401+WWW-Authenticate；伪造 token→401；豁免面 login/health 无 token→2xx+metrics 无 token→200[既有形态豁免——R6]） |
| 🟢 绿 | 修正各路由认证 dependency 遗漏面（红阶段暴露的缺口——**预期每端点 Task 已挂，本 Task 为集中矩阵验证+补漏**）；Pydantic 422 断言（请求体缺字段→422 RequestValidationError 响应体） |
| 🟡 变异 | 摘除某端点认证 dependency→对应 401 断言红；EXCEPTION_HTTP_MAP 摘除一条映射→矩阵断言红；还原绿 |
| 🔄 重构 | 新增端点统一 import `shared_models.ErrorResponse`（R1 勘正：共享定义已存在[shared_models.py:12]，零新建零收敛动作） |

- [ ] Subtask 6.1: 🔴 红 — 认证/错误矩阵失败测试
- [ ] Subtask 6.2: 🟢 绿 — 补漏 + 统一模型
- [ ] Subtask 6.3: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:**
- [ ] 认证矩阵全绿（含架构断言 Task 8 的全端点覆盖交叉验证）
- [ ] 错误响应矩阵全绿（断言形态实测锚定）
- [ ] 既有 exception_handlers 测试零回归

---

### Task 7: 集成测试（真实服务面）

**关联 AC:** AC-2 / AC-3 / AC-7

> **性质说明：** 真实服务面（真实 bootstrap+TestClient lifespan 触发+真实端口往返）；6.4-DF2 残余顺手清偿裁定面。

- [ ] Subtask 7.1: login→token→受保护端点真实链（真实 auth_service+测试用户创建/teardown 定向清理——**测试用户经 user 仓储直创，password_hash 经同一 EncryptionService[bcrypt] 生成**[R1 勘正：真实约束是 verify_password 通过（auth_service_impl.py:120），login_attempt 是锁定追踪非哈希约束]；**一次性用户名**防 record_attempt_and_check_lockout 连败锁定[auth_service_impl.py:106]）
- [ ] Subtask 7.2: document parse 真实链（真实上传→parse→状态断言→teardown 定向清理）+ trace/versions 真实读面
- [ ] Subtask 7.3: checkpoint 族真实链（真实创建→list/show→recover 往返——7-1 集成先例）+ plan status/export 真实读面
- [ ] Subtask 7.4: 并发双跑真实链（同 plan_id 两并发请求——恰一 200 一 409；per-plan 锁+482 兜底双机制验证；**时序注记[R1]**：B 阻塞时长=A 全程[真实 LLM 60s 级]——409 来自锁释放后 482 守卫见已完成态非超时；409 可附 Retry-After 头[dev 裁定——AC-7 注记]；无 Key 环境动态 skip）
- [ ] Subtask 7.5: 6.4-DF2 残余裁定（REST 长驻会话×fallback save 路径交叉覆盖——实测清偿或注记残余落档）

**完成标准/Definition of Done:**
- [ ] 集成测试真实服务全绿（服务不可达动态 skip——`_require_services` 探活形态）
- [ ] 零手动 delete/truncate（rollback/定向清理）

---

### Task 8: SDD 架构约束验证测试

**关联 AC:** AC-3（认证覆盖）/ 六边形约束

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [ ] Subtask 8.1: 创建 `tests/unit/architecture/test_arch_rest_api.py`
- [ ] Subtask 8.2: 分层断言（`src/interfaces/api` 零 `composition_root`/`infrastructure` import——AST 扫描；fastapi/httpx 零入 `src/domain`/`src/application`）
- [ ] Subtask 8.3: 认证覆盖断言（**断言作用域钦定[R8]=本 Story 冻结端点矩阵清单遍历**：新增全部端点+改造端点[audit 5+crawler 4] handler 挂 get_current_user dependency——AST/依赖树检查；**作用域内豁免=health 一项**[新增+设计豁免]；login 既有激活/metrics 未改造不在断言作用域——AC-3 三态注册表是**验收口径**非断言口径[R8 机制钦定，防 dev 在全 app 路由遍历[则 logout/refresh 弱形态也要豁免处理]与矩阵遍历间发明机制]）
- [ ] Subtask 8.4: 既有测试零回归（17 unit api 文件+13 契约文件+7 HTTP 验收文件引用面）
- [ ] Subtask 8.5: 运行完整测试套件并生成报告（循环依赖检测沿用 ruff/isort 既有面）

**完成标准/Definition of Done:**
- [ ] 所有架构/约束测试通过
- [ ] 任何违规都会导致测试失败
- [ ] 存量 API 测试全量零回归

---

### Task 9: 开发结束验收测试

**关联 AC:** 全部

> **性质说明：** 本 Task 对 Story 收尾阶段的交付物与完成清单进行最终验收，并补齐性能/并发验收场景。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_acceptance_rest_api.feature` 收尾场景（src 完成清单/测试目录完成清单）+ AC-8 性能并发场景（20 轮 P95 采样/50 并发） |
| 🟢 绿 | 编写/补齐对应 BDD 步骤实现，全场景转绿 |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [ ] Subtask 9.1: 性能场景 — 20 轮轻量端点 in-process 采样（httpx.AsyncClient+ASGITransport；P95 升序第 19 个 1-based；monotonic 差值；含认证 header）<800ms 断言
- [ ] Subtask 9.2: 并发场景 — 50 并发轻量请求（asyncio.gather）全部 2xx
- [ ] Subtask 9.3: 收尾场景 1 — src 完成清单逐项确认；场景 2 — 四测试目录完成清单逐项确认
- [ ] Subtask 9.4: 运行 `pytest tests/unit tests/integration tests/acceptance tests/contracts`（四目录全量）+ `ruff check` + `mypy` 收尾校验；全量回归甄别失败项（DF 族/预存抖动形态对照 epic-6 先例归位）；新增文件覆盖率实测（≥85% 门禁+扩档建议登记）

**完成标准/Definition of Done:**
- [ ] 全部验收场景通过（含动态跳过项甄别）
- [ ] 四目录全量回归零未甄别失败
- [ ] Story 可进入 `review`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../planning-artifacts/architecture.md) + [`interface-design.md`](../../../docs/architecture/interface-design.md) §8 + [`arch-appendix.md`](../../../docs/architecture/arch-appendix.md) 附录 H

- **架构模式:** 六边形架构（Ports & Adapters）+ D1 方案 A 组装层；REST 属接口层适配器（外部触发器——interface-design §3.3 规则 5「CLI 是点火开关」同款，REST 亦然）
- **设计约束:** 领域层零依赖；interfaces 禁 import composition_root/infrastructure（importlinter 传导禁令）；create_app 工厂住 entrypoints（D1 方案 A 既有形态）
- **接口治理:** 统一端口注册 PortSpec/组合根装配；本 Story 零新增端口消费 18 既有端口+2 处 lifetime 迁移（R1 口径）
- **技术栈:** Python 3.11+ / FastAPI ^0.111.0（pyproject:16 实装——**architecture.md:236 钦定 0.111+ 为准**，interface-design §2.1「0.104+」为下界表述）/ uvicorn[standard] ^0.24.0 / httpx ^0.27.0（性能采样面）/ Schemathesis ^3.19（dev 依赖零使用——7-6 归宿）
- **7-3 边界铁律:** OAuth 2.1 统一认证体系/令牌桶限流/路径-方法-角色路由/注入检测/Kong/Traefik 部署**全归 Story 7-3**（epics:2693-2733 + ADR-010）——7-2 仅基础认证（既有 auth_service per-endpoint dependency 形态）
- **可观测性注记（R6）:** request_id 链路响应头/响应体已闭环（ExceptionContextMiddleware 取/生成→state→响应头回写）但**日志侧零关联**（infrastructure/logging 无 request_id）——归可观测性专项（OD-9 关联）；CORS 零配置（全仓无 CORSMiddleware——服务器间集成不受影响，浏览器跨域不可用）——归 7-3/部署面

### 关键架构决策

| # | 方案 | 优点 | 缺点 | 评分 |
|---|------|------|------|------|
| **DC-1（选中）** | 7-2=P0 端点子集+4 router 挂载激活+health（7-3 四能力零承载） | 边界清晰（epics 7.3 定义钦定）；既有资产最大化复用 | 双 Story 切分期认证深度有限 | ✅ 9/10 |
| 备选：7-2 含 Gateway 能力 | 单 Story 交付完整 API 面 | 范围蔓延；7-3 无独立交付物；OAuth 2.1 体系超出单 Story | 3/10 |
| **DC-2（选中）** | 认证=per-endpoint `get_current_user` dependency（存量形态沿用+audit/crawler 零挂载端点实质改造）+ 豁免白名单三态（login/health 设计豁免+metrics 既有形态豁免+refresh/logout 既有弱形态注记——R6 勘正） | 零新建中间件；存量先例（auth.py:150-195）；架构断言可机械化 | 「认证中间件」字面语义以「全端点 dependency 覆盖」承载（注记） | ✅ 8/10 |
| 备选：新建全局认证中间件 | 字面合规 | 与存量 15 个 .py 形态冲突；7-3 Gateway 统一面重复建设 | 4/10 |
| **DC-3（选中）** | 端点参数=端口签名现实层优先（agent_id UUID/plan_id str/checkpoint 复合定位/slug） | 7-1 OD-8/OD-9 原则直接继承；签名级核验完成零错位 | 与 interface-design 钦定文本有偏离（OD 表登记） | ✅ 9/10 |
| 备选：钦定文本优先+适配层 | 文档忠实 | 适配层无先例；role→agent_id 解析引入额外端口消费 | 5/10 |
| **DC-4（选中）** | 新增文件平铺 `src/interfaces/api/`（对齐存量 15 个 .py） | 一致性；零迁移成本 | architecture.md:2102-2153 钦定 v1/ 子目录 defer（OD-4） | ✅ 8/10 |
| 备选：按钦定新建 api/v1/ 子目录 | 蓝图忠实 | 平铺+v1/ 并存割裂；存量迁移超出 Story 面 | 5/10 |
| **DC-5（选中）** | /documents/batch 维持既有同步形态（202 异步契约 defer） | 零基建（无 job 队列框架）；upload_batch 既有同步语义零回归 | 钦定 202 契约 OD-2 登记 | ✅ 8/10 |
| 备选：本 Story 建 job 基建 | 契约忠实 | job 框架选型+持久化+轮询器超 Story 体量；YAGNI | 3/10 |
| **DC-6（选中）** | per-plan 锁住 API 层（plans 路由模块级 dict[str, Lock]） | 482 竞态窗口（守卫深居图节点）从入口关闭；不动 BLM 服务层 | 锁字典自身需 guard 锁；进程内有效（多 worker 部署归 7-3/运维面注记） | ✅ 8/10 |
| 备选：BLM 服务层加锁 | 根因层修复 | 修改 BLM 服务超出接口层 Story 面；6.1-DF6②③ 同域债务交织 | 5/10 |
| **DC-7（选中，R1 重设计）** | traceability service（:2036 捕获主体）+use_case（:2065）双对象 SINGLETON→SCOPED | 捕获主体与消费面一并兑现触发器注记；surgical；行为等价零回归风险（声明面迁移） | clear_scoped 生产未接线下 SCOPED≡SINGLETON——迁移为生命周期声明语义正确化，真实 per-request 隔离归 OD-15 专项；executive_view/analyst_view 顺延（注记） | ✅ 8/10 |
| 备选：per-request clear_scoped 中间件 | 真隔离 | 进程级 `_scoped_context` dict 在途请求互毁（并发不安全，R1 推演定谳）；contextvar 级 scope 绑定为正解=真重构超 Story 面；与「零新增中间件」立场冲突 | 4/10 |

### 偏离声明预告（Task 0 落档确认，OD-n 前缀）

> **台账对应注记（R1 对齐版，R2 勘正）：** OD 表为决策记录，执行台账以 deferred-work.md 为准——OD-2/OD-3 → 7-2-DF1（异步 job+agents status 端点族）、OD-10 后段 → 7-2-DF2（3-8 高保真 REST 面）、OD-6 → 7-2-DF3（equilibrium_security 挂载）、OD-7 → 7-2-DF4（BLM 长驻含锁字典淘汰）、OD-12 → 7-2-DF5（compare+financial+documents 元数据查询族）、OD-13 → 7-2-DF6（P1 端点族含 /archive/timeline）、OD-14 → 7-2-DF7 关联（激活面契约，归宿 OD-5 契约治理）、OD-15 → 7-2-DF8（clear_scoped 接线）、OD-8（PT-03）→ 7-3 Gateway 面、OD-1/OD-11/OD-16 → 7-1-DF1 迁移专项统一复核。

| OD | Gap（四要素） | V1 归宿 |
|----|--------------|--------|
| OD-1 | agents 端点参数 `agent_id: UUID` 非 `{role}`（interface-design §8.2.3/§13.3 钦定 `{role}/run`）——端口签名 `execute(agent_id: UUID, task)`（agent_workflow_use_case :3184）无 role 解析面；architecture.md:2475 `{agent_id}` 形态一致（R6 勘正：原 :2465 为 documents 上传行）；动词保留 run（interface-design 双处+CLI agent run 三源一致；**R1 注记**：architecture:2475 第四源用 `{agent_id}/execute` 动词[R6 勘正行号]——上游四源不一致归上游契约澄清） | 7-1-DF1 迁移专项统一时复核 |
| OD-2 | /documents/batch 同步批量形态（interface-design §8.2.1.1 钦定 202 Accepted+job_id 异步契约）——仓内无 job 队列框架（upload_batch 请求内信号量并发同步返回，:1195 注册块既有形态） | 异步 job 基建专项（7-2-DF1） |
| OD-3 | /agents/{role}/status 端点 defer——全仓无 agent run 状态查询端口（agent_workflow_service 六阶段无 status 方法，结果即时返回无持久化 run 实体）；**业界对标注记[R6]**：202+轮询为 >10s 长时操作主流形态（Stripe/Fabric 先例）——本 Story 同步形态是有基建缺口（run 持久化）的偏离而非忽视；B 请求经 per-plan 锁阻塞 A 全程（60s 级）为同步方案真实代价（网关/客户端超时面归 7-3） | Agent run 持久化专项 |
| OD-4 | 新增文件平铺对齐存量（architecture.md:2102-2153 钦定 api/v1/ 子目录结构 defer）——存量 15 个 .py 平铺+create_app 在 entrypoints 的演化态现实 | API 面结构重构专项 |
| OD-5 | openapi.yaml 漂移修正仅一处（/documents GET 删除——R1 勘正：/health 保留为 embedding 契约）——chunked 族 yaml 缺失、/api/v1/search×3 双前缀怪癖等存量漂移不动（防 13 契约测试连锁回归）；激活面端点（metrics/crawler/roles 族）yaml 无契约缺口同归本项 | 契约治理专项（7-6 协同） |
| OD-6 | equilibrium_security router 不挂载——3 个 impl 字符串指向不存在类（storage_encryption/api_security/container_security，deferred-work:126 脚手架遗留，接线必 RuntimeError） | 等保接线专项 |
| OD-7 | 6.1-DF6② `_runs` 零治理×长驻无界增长与③孤儿 PlanningStarted 事件序 defer——修复波及 BlmPlanningService/图节点拓扑，超出接口层 Story 面 | BLM 长驻专项 |
| OD-8 | PT-03 防伪造 X-Tenant-ID 归 7-3（arch-appendix:2264 P0）——JWT 提取注入是 Gateway 职责；MVP 直传 header 信任形态维持 | 7-3 Gateway |
| OD-9 | 可用性口径双源消歧（epics:2662「≥99%」vs prd NFR-IF-05「≥99.5% V1」）——以 prd 为准；运维面指标 7-2 以错误响应契约+零回归承载 | 运维监控专项（7-4 协同） |
| OD-10（R1） | trace 端点域迁 plans（interface-design §8.2.1 钦定 `/documents/{id}/trace`=高保真溯源 vs 仓内端口现实：TraceabilityTreePort 为 plan 域[execute(*, plan_id, depth)]、3-8 TraceabilityPort.trace(claim: str) 入参为 claim 文本——document 域溯源树端口为零）——端点 `GET /plans/{plan_id}/trace` 对齐端口现实+CLI `trace-tree --plan-id` 先例；**3-8 高保真溯源 REST 面零承载**（claim 入参与钦定 {id} path 形态的上游双源不一致待澄清） | 上游契约澄清+3-8 REST 面专项（7-2-DF2） |
| OD-11（R1） | tools 端点参数 `{slug}` vs 钦定 `{id}`/`{tool_id}`（interface-design §8.2.2+architecture:2466 双源）——slug SSOT 链理由（`skill_manifest.SLUG_TO_TOOL_ID`→`get_tool(tool_id=)`，7-1 CR1-F7b 勘正同链） | 7-1-DF1 迁移专项统一时复核 |
| OD-12（R1，R2 增补） | 钦定 P0 端点不承载集：`GET /plans/{id}/compare`（§8.2.5 情景对比 P0）+ financial 族 `POST /financial/analyze`/`/sensitivity`（§8.2.4 双 P0）+ `GET /documents/{id}`（§8.2.1 P0 查询文档元数据——7-2 document 族仅承载 parse/versions，元数据查询端点零承载[R2 二次差集补登]）——R1 覆盖差集补登 | 后续 Story 立项承载（7-2-DF5 登记） |
| OD-13（R1，R2 勘正） | 钦定 P1 端点族不承载集：`/agents/arbitrate`（§8.2.3）、`/tool-chains/{id}/execute`（§8.2.2）、`/reports/regulatory`（§8.2.8）、`/risk/heatmap`（§8.2.9）、`/routing-decisions`（architecture:2496[R6 勘正行号]）、`/archive/timeline`（§8.2.7 时间轴演进 P1——R2 勘正：原「timeline-diff §8.2.6」节号与端点名双失实，系旧 DF 清单不精确继承名）+ `GET /plans`/`POST /plans`（architecture:2483/:2484[R6 勘正行号——原 :2479/:2480 实为 financial 族行] 与 interface-design 双上游不一致待消歧[R2 增补 POST]） | Epic 7 后续 Story 承载 |
| OD-14（R1，R2 精确化） | 激活面契约缺口：激活面 21 端点中确定缺口=crawler 4+monitoring 1（auth 11/audit 5 已有 yaml 契约覆盖；roles permissions 子面 dev 期核验）——NFR-IF-05「OpenAPI 3.1 契约测试通过率 100%」在激活面不闭环 | 契约治理专项（OD-5 关联，7-6 协同） |
| OD-15（R1） | clear_scoped 生产接线（真实 per-request SCOPED 隔离）——per-request clear 中间件并发不安全（进程级 `_scoped_context` dict 在途请求互毁，R1 推演定谳），contextvar 级 scope 绑定为正解（4-7 周期 `_RETRY_POLICY_OVERRIDE` 同款机制先例） | scope 机制重构专项（7-2-DF8 登记——R2 勘正编号） |
| OD-16（R2） | checkpoint 端点参数 `{plan_id}/{checkpoint_no}` 复合双参 vs §8.2.6 钦定 `/checkpoints/{id}` 单参——7-1 OD-8 端口签名现实层优先原则继承（checkpoint_recovery_use_case execute(*, plan_id, checkpoint_no) 两参必填，无 id 单参解析面） | 7-1-DF1 迁移专项统一时复核（同 OD-1/OD-11 归宿） |
| OD-17（R6） | exception_handlers fallback 分支消息泄露面：to_dict() 失败罕见路径 str(exc)[:500]+cause 的 str(cause) 直透响应体（exception_handlers.py:433/:438-443——R6 实证），主路径安全但兜底无脱敏；全仓零消息安全断言（7-2 Task 6 仅补主路径断言，生产行为不动——surgical） | exception_handlers 安全加固专项（脱敏白名单/cause 截断策略） |
| OD-18（R6） | export 文件内容获取面零承载：export 响应=StrategicReport 元数据 JSON（report_id/file_path[L0 逻辑路径——集成方不可直读]/section_count——实体无内容字段），文件流下载端点无契约（6.5a-DF1 清偿面为元数据契约非内容传输） | 文件下载端点专项（7-6 协同） |

### 项目结构说明 Project Structure（本 Story 相关面）

```
src/
├── entrypoints/
│   ├── api_app.py                   # ★修改：4 router 挂载（auth/monitoring/crawler/audit）+ 新路由族挂载
│   ├── agent_cli.py                 # 存量冻结（零改动）
│   ├── ocr_cli.py                   # 存量冻结（零改动）
│   └── main_cli.py                  # 存量冻结（零改动）
├── interfaces/api/
│   ├── auth.py                      # 既有零改动（挂载激活）
│   ├── monitoring.py                # 既有零改动（挂载激活）
│   ├── crawler.py                   # ★实质改造：4 端点补 Depends(get_current_user)+工厂加认证参数（R6：零挂载+工厂无认证参数实证）
│   ├── audit.py                     # ★实质改造：5 端点签名补 Depends(get_current_user)+前缀统一 /api/v1/audit（R1：端点零挂载实证）
│   ├── equilibrium_security.py      # 既有零改动（不挂载——OD-6）
│   ├── exception_handlers.py        # 既有零改动（:116 metrics 接线视裁定）
│   ├── documents.py                 # ★新建：parse/versions 两端点+find() 前置查询
│   ├── tool_execution.py            # ★新建：execute/schema 两端点
│   ├── agents.py                    # ★新建：run 端点
│   ├── plans.py                     # ★新建：generate/status/export/trace 端点+per-plan 锁
│   ├── checkpoints.py               # ★新建：list/show/recover 端点
│   ├── archive_query.py             # ★新建：archive query 端点（blm_chain_trace 消费面）
│   └── system.py                    # ★新建：health 端点
└── composition_root.py              # ★小改：traceability_tree_service（:2036）+traceability_tree_use_case（:2065）lifetime SCOPED 双迁移

docs/api/openapi.yaml                # ★修改：14 新 path+单漂移修正（/documents GET 删除）

tests/
├── unit/interfaces/api/             # 新建 5 文件（document_routes/tool_execution_routes/agent_plan_routes/checkpoint_archive_routes/system_routes）+ test_app.py/test_exception_handlers.py 扩展
├── unit/architecture/               # test_arch_rest_api.py
├── contracts/                       # test_port_contract_rest_api.py + test_api_contract_rest_api.py
├── integration/                     # test_integration_rest_api.py
└── acceptance/                      # test_acceptance_rest_api.feature/.py
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 7-1 CLI 命令行接口](./7-1-cli-command-interface.md)（Epic 7 前序故事，五轮文档审查+五轮代码审查收敛）

**关键学习/Key Learnings:**
- **端口签名级核验纪律**（7-1 R3-1/2 教训——行号核验只证注册存在未证签名匹配）：本 Story 端口 SSOT 表已签名级核验（4 调研 Agent+主会话双重复核——agent_id 非 role/plan_id 为 str/checkpoint 复合定位三处防错位；**R1 补教训**：签名级核验还须含**参数域匹配**——创建期 trace 行端口 execute(*, plan_id) 与端点 document_id 错配漏网，D1 调研+双评审抓出[OD-10 域迁清偿]）
- **断言补充必须先实测锚定形态**（7-1 CR3 教训）：错误响应体/头断言在 Task 6 红阶段先实测 ExceptionHandlers 实际形态再冻结断言
- **DI 工厂红利**（7-1 DC-2）：路由工厂参数注入+三级 fallback——单测 stub 直注免 monkeypatch；`_make_app()` 自持工厂（test_archive_routes.py 先例）禁共享全局 app
- **验收 R6 模板七要点**+HTTP 级装配形态（TestClient+get_current_user_override+X-Tenant-ID——document_upload 验收先例）
- **变异实证强制**：每实现 Task 断言突变注入-还原（Epic 4 行动项——8/13 Story 恒真断言教训）
- **CI root 容器教训**（efd0f11d）：环境门控用 `_require_services` 探活形态，禁恒 skip
- **懒 bootstrap 幂等**（7-1 冲突 203 教训）：TestClient with 语句触发 lifespan bootstrap——conftest 已 bootstrap 场景需幂等守卫核验
- **性能采样纪律**：monotonic 差值+P95 升序取法+子进程/in-process 直调形态（排除包装开销）
- **created_via 审计标识**（7-1 R4-2）：REST 面固定 "api"；confirmed_by 缺省取认证用户（优于 CLI session 缺省——REST 有真实身份）
- **slug SSOT 链**（7-1 CR1-F7b）：`skill_manifest.SLUG_TO_TOOL_ID`→`get_tool(tool_id=)`——禁 `get_tool(tool_name=slug)` 直查（slug≠tool_name 双列实证）

**应用到本故事/Applied to This Story:**
- [ ] 端口 SSOT 表签名级事实为唯一源（实现 Task 禁换端口/禁绕 resolve）
- [ ] 错误响应断言先实测锚定（Task 6 红阶段）
- [ ] per-plan 锁模块级+变异验证判别力
- [ ] 验收 R6 七要点+真实服务动态 skip+HTTP 适配层 AsyncMock 子模式口径
- [ ] 前置留项 14 条 Task 0 落档+三向定夺执行

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.3（Claude Code 会话） |
| **Version** | bmad-create-story skill（workflow.md 现行版） |
| **Execution Date** | 2026-11-21 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Checklist** | `.claude/skills/bmad-create-story/checklist.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Epic 7 :2565-2692；Story 7.2 :2651-2691） |
| **架构文档** | `docs/architecture/architecture.md`（:2102-2153 API 目录/:2465-2496 端点清单）+ `docs/architecture/interface-design.md`（§8 :1383-1515[R6 勘正区间尾]）+ `docs/architecture/arch-appendix.md`（附录 H 租户传播） |
| **前置留项源** | `_bmad-output/implementation-artifacts/deferred-work.md`（:115-:129/:191/:329-:332/:349/:362/:369-:370/:409） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/7-1-cli-command-interface.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

**创建阶段（create-story）：**

- [x] 故事需求从 `epics_v1.0.md` 提取（Story 7.2 :2651-2691）
- [x] 架构约束从 architecture.md/interface-design.md/arch-appendix.md 提取（4 调研 Agent 并行：REST 资产盘点/端口签名核验/留项与验收风格/架构边界深读——2026-11-21）
- [x] 前置留项清单 14 条逐条裁定落档（含 :125/:129 三向定夺承载）
- [x] 前一个故事学习经验整合（7-1 五轮文档+五轮代码审查沉淀）
- [x] 端口消费 SSOT 表签名级核验（15 行消费对 18 唯一端口——主会话独立实测行号；R1 勘正计数）
- [x] 状态设置为 `ready-for-dev`

### 文件清单 File List

**创建的文件/Created Files:**

- `_bmad-output/implementation-artifacts/stories/7-2-rest-api-interface.md`

**待创建的文件/To Be Created (Dev Story 实施):**

- `src/interfaces/api/documents.py` - parse/versions 端点+find() 前置查询
- `src/interfaces/api/tool_execution.py` - execute/schema 端点
- `src/interfaces/api/agents.py` - run 端点
- `src/interfaces/api/plans.py` - generate/status/export/trace 端点+per-plan 锁
- `src/interfaces/api/checkpoints.py` - list/show/recover 端点
- `src/interfaces/api/archive_query.py` - archive query 端点
- `src/interfaces/api/system.py` - health 端点
- `tests/unit/interfaces/api/test_document_routes.py` 等 5 个新建单测文件（R1 勘正计数）
- `tests/unit/architecture/test_arch_rest_api.py`
- `tests/contracts/test_port_contract_rest_api.py` / `test_api_contract_rest_api.py`
- `tests/integration/test_integration_rest_api.py`
- `tests/acceptance/test_acceptance_rest_api.feature` / `.py`

**待修改的文件/To Be Modified:**

- `src/entrypoints/api_app.py`（4 router 挂载+新路由族挂载——monitoring prefix 形态冻结）
- `src/interfaces/api/audit.py`（5 端点 Depends 认证实质改造+前缀统一）
- `src/interfaces/api/crawler.py`（4 端点 Depends 认证实质改造+工厂加认证参数——R6 勘正）
- `src/composition_root.py`（traceability service+use_case lifetime SCOPED 双迁移）
- `docs/api/openapi.yaml`（14 新 path+单漂移修正）
- `_bmad-output/implementation-artifacts/deferred-work.md`（14 条处置注记+7-2-DF 登记）
- `_bmad-output/implementation-artifacts/sprint-status.yaml`（7-2 状态推进）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 7.2 |
| **Story Key** | 7-2-rest-api-interface |
| **File** | `_bmad-output/implementation-artifacts/stories/7-2-rest-api-interface.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 7: 多触点用户界面与 API 集成 |
| **价值组** | 多触点操作与监控能力 |
| **优先级** | P0-2 |
| **覆盖 FR** | FR-UI-02；NFR-IF-05（OpenAPI 3.1 契约 100% 承载面） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-9）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-8）
3. [x] Architecture constraints extracted 架构约束已提取（六边形+D1 方案 A+7-3 边界铁律+importlinter 传导禁令）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（7-1 全审查周期沉淀）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。
>
> **编号规则（R6 增注）：** 本表 R<轮>-<序号> 与先例 Story 的 R<n>-F/P/D 为不同命名空间；R1~R5=第一审查周期（v1.0.0→v1.3.1）、R6~=第二审查周期（续编号）。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-1 | trace 端点域错配：AC-2 钦定 GET /documents/{document_id}/trace 但 traceability_tree_use_case 为 plan 域（execute(*, plan_id, depth)），document_id 无处传入；且与既有 /search/trace/{document_id} 引文端点形成第三种 trace 语义 | P0 | 端点迁 GET /plans/{plan_id}/trace（端口现实+CLI trace-tree --plan-id 先例）；OD-10 登记（含 3-8 高保真溯源 REST 面零承载 defer）；SSOT 表/Task 2/Task 4/AC-6 path/File List/追溯矩阵联动（D2-A 传播位 10 处全改） |
| R1-2 | /health 漂移修正方案双重失实：yaml /health 实为 embedding server 契约（消费方 test_api_contract_embedding.py:34），改名破坏测试且语义错置 | P0 | 改为新增 /system/health 新 path、/health 原样保留；漂移修正仅剩 /documents GET 删除；新 path 计数 12→14（AC-6/Subtask 0.3/API 契约节三处） |
| R1-3 | SCOPED 迁移双缺陷：迁移对象错位（捕获主体是 traceability_tree_service :2036 非 use_case :2065）+ 机制前提不成立（clear_scoped 生产零调用，SCOPED≡SINGLETON——组合根 :3258 注记自证） | P0 | 双对象迁移（service+use_case）+ 机制诚实注记（声明语义正确化/per-request clear 中间件并发不安全推演定谳/真实隔离归 OD-15）；analyst_view_service :2133 新捕获实例传播注记；lifetime 双断言移 Task 2 红阶段（防 CI 可见红窗——P2-1 联动清偿） |
| R1-4 | 上游钦定端点覆盖差集零登记：/plans/{id}/compare（§8.2.5 P0）三层全漏、financial 族（§8.2.4 双 P0）DF 清单提及但 OD 无行、tools {slug} 偏离无登记、P1 端点族（arbitrate/tool-chains/reports regulatory/risk heatmap/routing-decisions/timeline-diff）与 GET /plans 列表零消歧 | P0 | OD 表补 OD-10~OD-15 六行（R1 勘正版）+ DF 映射句重写对齐（8 项+1 归宿）+ Subtask 0.7 DF 清单对齐 |
| R1-5 | 「手动 HTTPException 边界沿用 auth.py 既有形态」与代码现实相反（auth.py 全文件零 HTTPException——401+WWW-Authenticate 由 ExceptionHandlers :453-454 统一） | P1 | 勘正为「零手动 HTTPException」+实证行号（异常契约节） |
| R1-6 | audit「挂载时必填化传入」无认证效果：get_current_user 参数在全部端点从未使用（零 Depends） | P1 | 如实写 5 端点签名实质改造（AC-1/AC-3/Task 1/项目结构/待修改清单 5 处联动） |
| R1-7 | 端口计数口径失实：「13 唯一端口 14 消费对」无法从表体导出（实为 15 行消费对/18 唯一端口） | P1 | 全文 6 处勘正+口径推导注记（3 行双端口使 18=15+3） |
| R1-8 | openapi 12 path 清单漏 /archive/query（13 端点仅 12 path 契约） | P1 | 补入+计数 14（与 R1-2 合并清偿） |
| R1-9 | document 族 404 契约与端口语义错配：list_versions 租户不匹配返回 [] 非 404、parse_document 不存在返回合成 FAILED Document 非 202——AC-4/AC-5 两契约面落空 | P1 | 端点层 find() 前置查询→None raise NotFoundError→404 写为设计决策（AC-4/AC-5/异常表/Task 2 红·绿·变异/测试分类表联动；主会话实测定谳：端口无 get_by_id，find(DocumentQuery) 为正确前置面） |
| R1-10 | ErrorResponse「存量 5 文件重复 defer」前提失实（已收敛 shared_models.py:12，设计文档 :30 标清偿） | P1 | 三处勘正为直接 import 共享模型（数据模型节/Task 6 重构行/OD-5） |
| R1-11 | upload_service 注册名漂移（实为 document_upload_service） | P2 | AC-2 验证标准勘正 |
| R1-12 | test_app_routing.py vs test_app.py 文件名矛盾（test_app.py 现无挂载断言，「扩展」实为新建断言） | P2 | 统一 test_app.py+新建断言注记（AC-1 验证标准） |
| R1-13 | 三向定夺裁定「删除」的依据漏 tests 引用面（StrategicAnalysisUseCase 7 测试文件、orchestration_service 3 文件 resolve 消费——删除前提注定不成立） | P2 | #12 裁定改「R1 预判 defer 为大概率落点」+引用面实证入表 |
| R1-14 | 计数/行号微漂移族：X-Tenant-ID 先例 8→6 处、「存量 13 文件」→15 个 .py（4 处）、EXCEPTION_HTTP_MAP :161→:160（2 处）、tools.py 端点枚举 3→6、「6 单测文件」→5（2 处）、Task 2「--help 等价」CLI 残留措辞、留项 #2 序号错乱、验收先例 :51-78→:49-78、Makefile :278-280→:279-281、auth 工厂 :150-186→:150-195 | P3 | 逐处勘正（本轮全部清偿） |
| R1-15 | 可行性补强注记族：monitoring 挂载形态未冻结（无 prefix router）、per-plan 锁字典无界增长、锁变异「如可测」模糊、密码哈希归因失实（真约束=EncryptionService bcrypt+防锁定一次性用户名）、并发双跑 409 时序（锁释放后守卫非超时）、Subtask 0.5 骨架表述防误读、AC-2×8↔13 端点覆盖映射 | P2/P3 | 逐项注记/具体化（本轮全部清偿：AC-1/Task 1/Task 4/Task 7/Subtask 0.4/0.5/Gherkin 节） |
| R2-1 | OD-13「/archive timeline-diff（§8.2.6）」双失实：节号错（§8.2.6=Checkpoint 管理，archive 在 §8.2.7）+端点名不精确（钦定 `/archive/timeline`——timeline-diff 系旧 DF 清单不精确继承名） | P2 | OD-13 行+Subtask 0.7 DF6+映射句三处勘正（interface-design §8 实测定谳） |
| R2-2 | 覆盖差集二次漏网：`GET /documents/{id}`（§8.2.1 P0 文档元数据查询）未承载且 OD 零登记（R1 补登差集仍漏）；`POST /plans`（architecture:2480）未入双源不一致清单 | P2 | OD-12 增补 GET /documents/{id}（DF5 联动）+OD-13 增补 POST /plans |
| R2-3 | OD-14「~14 端点」模糊数：实测激活面 21 端点（auth 11+monitoring 1+crawler 4+audit 5），其中 auth/audit 已有 yaml 契约——确定缺口=crawler 4+monitoring 1 | P3 | OD-14 精确化口径（roles permissions 子面 dev 期核验注记） |
| R2-4 | checkpoint 参数偏离无 OD 行：§8.2.6 钦定 `/checkpoints/{id}` 单参 vs 本 Story 复合双参（7-1 OD-8 原则继承但偏离未登记） | P3 | 新增 OD-16 行（归宿 7-1-DF1 统一复核，同 OD-1/OD-11） |
| R3-1 | checkpoint given 前置引用过时先例：原引「7-1 R3-7 checkpoint_use_case 直创」已被 7-1 CR6 判定为无 Key 环境连带 skip（创建链 OD-12 压缩强制环节依赖 LLM——7-1 验收至今 1 skip 正是它），与 AC-2「非依赖面确定性全绿」口径直接矛盾 | P1 | given 前置改 checkpoint 仓储/snapshot 直构（绕开 LLM 依赖链——dev 实测裁定形态）；AC-2 验证标准②重写 |
| R3-2 | Task 0 TestClient 行为型契约测试 import 形态未定谳：先例 test_api_contract_document_upload.py:20 顶部 import 路由模块——新路由模块 Task 0 不存在→收集期 ImportError 连坐同文件 yaml 断言（比断言红更糟） | P2 | 定谳拆分：Task 0 仅 yaml 消费型+既有端点行为型，新端点行为型随 Task 1-5 逐族补入（Subtask 0.3/AC-6/测试分类表三处联动） |
| R3-3 | trace/archive query 场景 given 前置零交代（「确定性全绿」口径受 given 前置制约） | P2 | 补决策点：同源 snapshot 直构（plan 域快照族——dev 实测裁定直构形态） |
| R3-4 | tool execute 场景 LLM 依赖归类缺失（skip 口径只列 agent run/plan generate） | P2 | 补注记：走 LLM 工具时同款 skip 归类（schema 端点零 LLM 确定性全绿） |
| R3-5 | health 场景 version 来源未定义 | P3 | 钦定 importlib.metadata.version 装配期解析+常量兜底（dev 实测裁定）——AC-1 端点描述 |
| R3-6 | metrics 真实采集承载面未明（单测/验收未定） | P3 | 钦定单测 test_system_routes.py（零 IO resolve+真实 collect）——验收聚焦挂载可达+health |
| R3-7 | AC-4 四态↔2 场景分组映射未写 | P3 | 分组建议注记（404+422 请求校验族/401+409 认证并发族——dev 可调） |
| R3-8 | 跨租户 given 上传形态未写+租户分叉防坑注记缺失（7-1 CR6-2 假绿先例：given 租户与请求头租户分叉→find miss→弱断言恒绿） | P3 | given 钦定真实 upload 链+同租户正查 200 对照断言必须有（A/B 显式分置） |
| R3-9 | parse 断言强度（7-1 CR6-1 parse_status 锚先例未采纳）+recover 后查询期望留白 | P3 | parse_status=completed 判别锚注记+recover 后 list 复核建议注记 |
| R4-1 | L101 AC-4 NotFound 行中文圆括号不平衡（`均 R1 实证]）/plans` 多一个 `）`——R1-9 修复引入的排版残留，语义无损 | P3 | 随 R5 收敛提交清偿（改分号分隔——成本趋零应做） |
| R5-1 | 收敛终审：六节取证全过（周期闭合[3 提交零游离]/双向抽验 8⁄8/台账完整/门禁如实/锚点 17⁄17 精确零失实/收敛判定可收敛） | — | 收敛声明入 Story（本节下方）+版本 v1.3.1 |
| R6-1 | crawler.py 4 端点零认证+工厂无认证参数，Story 却写「既有零改动（挂载激活）」——挂载即激活未认证 POST 任务提交面，违 CLAUDE.md「所有 API 路由必须过认证」硬约束，且与 audit 补挂待遇不对称（R6-D 调研发现，主会话 grep 实锤零 Depends） | P0 | Story 承载认证实质改造（工厂加认证参数+4 端点补挂——Task 1 与 audit 同批同款，评审 B 三选项裁定[a]承载：defer 自相矛盾[audit 先例在面+硬约束违反发生在挂载瞬间]、不挂载违背 deferred-work:115 钦定）；传播 9 处（现状缺口#1/AC-1/AC-3 新增 bullet/留项#10/Task 1 绿·变异·重构/项目结构/待修改清单/Task 8.3） |
| R6-2 | metrics 零认证（get_metrics 无 Depends——R6-B/D 双调研独立发现）与「豁免面仅 2 类」矛盾：第三类未登记豁免——dev 误挂认证破坏 Prometheus 抓取/架构断言误纳管红双风险 | P1 | 豁免面三态口径（设计豁免 login/health+既有形态豁免 metrics[Prometheus 抓取形态，scrape bearer/网络隔离归 7-3 OD-8 关联]+既有弱形态注记 refresh/logout）——AC-3 主条改写+401 断言限定受保护端点+Task 6 红豁免断言[metrics 无 token→200]+Task 8.3 白名单三态+DC-2 行同步 |
| R6-3 | 异常消费表 plans status 无记录写 NotFoundError/202——实际 PlanningNotFoundError(EXCEPTION_480)（get_blm_planning_status.py:66 用例自抛，映射 exception_handlers.py:314 收 404）——dev 按表断言 error.code=202 必红（R6-C 发现，主会话实锤映射行） | P1 | 表行勘正+AC-4 表述+Task 4 红 B 表述+Task 6 红矩阵 480 行——签名级核验原则在异常消费面的失效修复 |
| R6-4 | 未知 slug 与 agent 不存在两 404 首要路径零承载：ToolNotFoundError(380→404 映射 :256)/AgentNotFoundError(443→404 映射 :295) 均既有异常既有映射但不在异常表——dev 须发明契约（R6-C 发现，主会话实锤双映射行） | P1 | 表补两行（slug miss=get_tool_id 返 None 端点自 raise 380[与仓储 get_by_id miss 同码]；agent 用例首步自抛 443）+Task 3/4 红断言位+AC-4 404 锚定三选一注记；零新增领域异常声明不变（既有异常消费补行） |
| R6-5 | refresh（凭 refresh_token 自凭证换发）/logout（无 token 静默 204 非 401）弱形态与豁免面表述差集——AC-3 401 矩阵抽查误写期望风险（R6-D 发现） | P2 | AC-3 既有弱形态注记如实登记（4 认证形态并存，收口归 7-3）+401 断言限定「受保护端点」；不改生产行为（收紧超 surgical 面） |
| R6-6 | 「消息安全既有契约复验」前提失实（全仓零此类断言）+fallback 分支 str(exc)[:500]/str(cause) 直透泄露路径（exception_handlers.py:433/:438-443——R6-D 发现，主会话实锤） | P2 | AC-4 验证标准勘正为「新增断言」（主路径 to_dict 三字段无堆栈/SQL）+Task 6 红补承载+泄露面登记 OD-17（生产行为不动——评审 B 裁定拒顺手修代码） |
| R6-7 | ToolExecuteRequest.cost_budget 无透传落点：ToolCall 四键/ExecutionContext 六键均无该字段（CLI 侧 CommandContext 预算台账另一体系——R6-C 发现，主会话实锤 VO 字段） | P2 | 删 cost_budget+timeout→ExecutionContext.timeout_sec 合法可选映射注记（数据模型节+Task 3 红）；禁塞 extensions（评审 A 补禁令——Story 4.3 装饰器通道，塞入属发明语义） |
| R6-8 | POST 成功状态码 200/201 未钦定（AC-6 yaml 契约必填项——R6-C 发现） | P2 | 一句钦定「新增端点成功响应全部 200」（201 仅资源创建型——yaml 既有先例创建快照/创建角色；本 Story 13 端点无资源创建型；crawler 既有 201 不动）——AC-6+Subtask 0.3 场景注记；评审 A 证伪 D1 逐端点设计（惯例已答）轻量化 |
| R6-9 | export 响应语义未消歧（元数据 JSON vs 文件流误读）——StrategicReport 实为纯元数据实体无内容字段（评审 B worktree 实测字段清单） | P2 | 定谳：StrategicReport 元数据 JSON+file_path 为 L0 逻辑路径注记（集成方不可直读）+文件内容获取面 OD-18 登记——AC-2/Task 4 红/SSOT 行三处（评审 A 半证伪：Task 4 已隐含 JSON，本修复为一句消歧非零钦定） |
| R6-10 | 锚点行号族 8 处失实：OD-1 architecture :2465/:2474→:2475×2、OD-13 :2479/:2480→:2483/:2484（原行恰 financial 族串位）+:2494→:2496、R3-2 先例 :20→:28、§8 区间尾→1515、验收先例 :49→:50、DC-2 行 auth.py:150-186 残留（R1-14 传播漏网）（R6-A 实测 65+ 锚点精确、7 失实集中 architecture.md 端点清单族——机理断言无一失实；R5 抽验 17/17 未覆盖该族=抽验面盲区实证） | P3 | 逐处勘正（Subtask 0.3/OD-1/OD-13/调试日志/Gherkin 节/DC-2 六处位） |
| R6-11 | 业界对标注记 4 条补强（R6-B 七主题对标）：OD-3 增 202+轮询主流论据+B 请求 60s 阻塞窗口/checkpoint 上限 8 分页 YAGNI 实证/豁免端点显式 security: [] 写法/409 Retry-After dev 裁定 | P3 | 注记入对应节（OD-3/AC-2 checkpoints/AC-6/AC-7 时序注记）；health-liveness 与 RFC 9457 两条对标注记被评审证伪拒绝（添噪——AC-1「轻量不连存储」已是 liveness 语义/AC-4 已声明不动） |
| R6-12 | 可观测性三注记：request_id 日志侧零关联/CORS 零配置/AC-4 矩阵缺 423（锁定）行（R6-D 取证） | P3 | Dev Notes 可观测性注记（归可观测性专项/7-3）+AC-4 423 行注记（映射 :407-420 既有不单列场景） |
| R6-13 | 序列化四注记：Document.embedding 响应剔除锚定/AgentWorkflowResult 深嵌套字段子集裁定/CheckpointRecoverRequest 静默裁剪 correction/login JSON body+yaml flows 写法（R6-C 消费者视角） | P3 | 对应端点 bullet 注记（AC-2 parse/run+数据模型节+AC-3 login——防 dev 发明契约） |
| R7-1 | R6-8 成功码钦定未联动 Subtask 0.3（钦定本体在 AC-6 主位，副位漏传——R7-A git 取证发现） | P3 | Subtask 0.3 补「yaml 响应契约按 AC-6 成功码钦定撰写」一句（成本趋零应做） |
| R7-2 | R6-11 Retry-After 注记未写入 AC-7 时序注记与 Subtask 7.4（台账自提及而正文两副位漏传——R7-A 发现） | P3 | AC-7 时序注记+Subtask 7.4 两处补写（半句级） |
| R7-3 | R6 新写入锚点 3 项行号级失实（R7-B 核验）：get_blm_planning_status.py:66 实为 :56（:64-68 是 docstring 尾——R6-C 调研原报即误，主会话当日实锤定义/映射但漏抛出行）；yaml 201 先例枚举漏 /tools/{tool_id}/versions :1209（三处 201 定性全成立仅枚举不全）；run_agent_workflow.py:134 为 get_by_id 调用行、raise 在 :136 | P3 | :56 两处勘正（AC-4+异常表）+201 枚举补全 :115/:274/:1209（AC-6）+:136 精确化（异常表，调用行 :134 保留注记）——机理断言零失实，成本趋零随轮清偿 |
| R8-1 | crawler 既有测试面适配零承载：test_crawler.py `_create_app`（:225-235）裸装配零认证 override——4 端点补挂后 23 测试函数中 ~14 端点测试 200→401 全红，Task 1 DoD「17 文件全绿」被 R6-1 改造直接打破（audit 无 test_audit.py 零破坏——两 router 测试面差异） | P1 | Task 1 绿补适配承载：工厂注入 `get_current_user_override` stub TokenPayload（document_upload.py:113/:150 先例）——主会话实锤 _create_app 裸装配与 23 测试函数 |
| R8-2 | Task 1 变异第三项时间线断链：「摘除 crawler 端点认证→AC-3 401 断言红」——AC-3 401 矩阵承载在 Task 6 红，Task 1 时点无可红锚点 | P2 | Task 1 红补最小 401 断言（crawler 1 端点无 token→401）+变异锚点改「test_crawler.py 401 断言红」 |
| R8-3 | Task 8.3 白名单三态与断言作用域不匹配：断言作用域（新增+改造端点）内唯一无认证端点是 health——login 既有激活/metrics 未改造均不在作用域；三态注册表是 AC-3 验收口径，误植进架构断言会迫使 dev 发明白名单机制（全 app 遍历则 logout/refresh 弱形态也要豁免处理） | P2 | 机制钦定：断言按本 Story 冻结端点矩阵清单遍历+作用域内豁免=health 一项；三态注册表归 AC-3 验收口径注记区分（Subtask 8.3 重写） |
| R8-4 | AC-6「豁免端点显式 security: []」未限定——metrics 无 yaml 契约（OD-14 确定缺口），dev 按字面可能误补 metrics 契约与 OD-14 冲突 | P3 | 限定「设计豁免端点（login/health）」+metrics 不适用注记（AC-6） |
| R8-5 | Task 6 红矩阵与 Task 3/4 端点单测对 380/443/480 双承载区分未显式——防「重复承载？」型重问需半句注记 | P3 | Task 6 红补注记（矩阵=映射断言/端点单测=调用契约断言，语义不同非重复） |
| R8-6 | 380/443 验收面零承载无显式注记（AC-2×8 场景映射不含未知 slug 步骤为合理设计但口径未声明） | P3 | AC-4 验证标准补注记（验收不单列场景——单测承载足够，有意设计） |
| R8-7 | timeout 断言形态半具体（映射目标已命名但断言锚未写） | P3 | Task 3 红补断言锚（ExecutionContext.timeout_sec==请求值） |
| R8-8 | Retry-After 可选实现与 AC-4 双头断言的关系未注记（dev 疑惑是否扩三头） | P3 | AC-7 Retry-After 注记补「可选实现不进 AC-4 断言（双头不扩三头）」 |

> **R1 审查组织：** D1 四调研 Agent（REST 资产/端口 SSOT/契约测试/规格留项）+ D2 双评审（A 正确性+一致性：P0×4+P1×7+P2×6+P3×9+传播位清单 10 组；B 可行性+科学性：两大 P0 方案定谳+Task 级干跑+场景可满足性推演）+主会话实测定谳 3 项（N13 traceability 路由面/get_by_id 不存在/find 租户语义）。评审员间零事实冲突，D1 发现全部采信。
> **R2 审查组织：** 双调研 Agent——R2-A 修复回归核查（git 取证：R1-1~R1-15 逐项 15/15 完备零漏网+新破口零发现+残留终扫零残留+场景算术复核自洽）+ R2-B 新增内容事实核验（OD 新行节号/端点名/行号族/组合交互面——R1 新写入声明中 4 项缺陷：OD-13 双失实/差集二次漏网/模糊数/checkpoint 偏离无登记；14 path 七处一致+SCOPED 双对象 11 处一致+trace 三角一致+created_via 三处一致等组合面全通过；附加正向事实：parse_document :119 内部已 find()——端点前置查询与内部构成双查询无害）。
> **R3 审查组织：** 单深度推演 Agent 四轴（Task 依赖干跑[import 闭合全通过+port_contract 文件时间线自洽]/17 场景期望唯一性[期望唯一性机制成立，given 前置三处缺口]/AC↔测试承载矩阵[28 条 25 闭合，3 条 P3 承载面未明]/长状态时间线[document 链可观测 ✓，plan 链 recover 后留白]）——9 项发现（P1×1+P2×3+P3×5）+5 个缺失决策点全部补决策；7-1 CR6 最新教训三条直接反哺（R3-1 过时先例/R3-8 租户分叉假绿/R3-9 parse_status 判别锚）。
> **R4 审查组织：** 纯验证 Agent 七维度（R1-R3 修复存续 26 组锚点/台账可追溯 10 行抽验 10⁄10/数字口径互证/结构完整性/状态字段/Task 链自洽/红线终扫）——6 通过+1 项 P3 排版级（R4-1），零实质发现不造独立提交轮（4-x 周期先例）。
> **R5 审查组织：** 独立终审 Agent 六节取证（不轻信自报）——周期闭合[3 提交与版本说明一一对应零游离、文件面纯 .md/.yaml]/关键修复双向抽验[8⁄8：trace 签名/双对象注册块现值 SINGLETON=待迁移正确态/EXCEPTION_HTTP_MAP/shared_models//health 消费方/find 租户过滤/slug SSOT/482 守卫]/台账完整[29 行修复+OD 16 行+DF 双侧同号]/门禁如实[三提交 hooks 全 Passed、ruff-mypy 不适用 .md 如实注明]/锚点实测[17⁄17 精确零失实]/收敛判定[可收敛]。
> **R6 审查组织（第二周期 Round 1）：** D1 四调研 Agent（A 代码锚点终局复核[65+ 精确/7 失实集中 architecture.md 端点清单行号族+R5 抽验盲区实证]/B 业界最佳实践对标[7 主题网络+代码双源——metrics 口径缝隙最有价值]/C 消费者可实施性[13 端点逐个走查——错误面系统性薄面：三 404 异常缺席+状态码/export 语义/cost_budget 落点]/D 安全与可观测性[4 router 认证全谱——crawler 零认证 P0+豁免面三处差集+消息安全零承载+request_id/CORS 取证]）+ D2 双评审（A 正确性一致性：逐项传播位清单+组合交互四组[白名单三口径/AC-6 零冲突/场景计数不变声明/DF1 清偿主张]+F8 证伪轻量化+F9 半证伪+F6 部分证伪；B 合理可行性：F1 三选项裁定承载[defer 自相矛盾论证]+crawler 工厂实测[连参数都无——加参成本]+StrategicReport 字段实测[F9 定谳依据]+拒绝 F6/F9 代码级诱惑方案+2 条添噪注记）+主会话实测定谳 9 组（crawler/monitoring 零 Depends、480/380/443 映射行、get_tool_id None、fallback 透传、cost_budget 全仓落点、ToolCall/ExecutionContext 字段、auth refresh/logout 形态）。修复 13 项（P0×1+P1×3+P2×5+P3×4）+OD 表扩至 18 行（OD-17 fallback 泄露/OD-18 export 文件面）+DC-2 勘正。**场景计数 17/21 不变**（全部修复并入既有断言面/注记位，无新场景——防回归核查重问，评审 A 组合交互③）。
> **R7 审查组织（第二周期 Round 2）：** 双调研 Agent——R7-A 修复回归核查（git 取证 9ec4764c：R6-1~R6-13 传播完备性 11/13 完备[P0/P1 全部传播到位——R6-1 九处/R6-2 六处/R6-3 四处/R6-4 五处逐点验证]+新破口零发现[表格列数/旧表述残留/结构/Subtask 42 连续全查]+场景算术三处一致+残留终扫零 TODO）+ R7-B 新增内容核验（30+ 新锚点逐项对照 HEAD：crawler 行号族 5/5 精确/异常链路定义+映射全中/StrategicReport 8 字段纯元数据实证/CP-1..CP-8 值域守卫实证/architecture.md 勘正后四行全中/三态口径六处互洽——3 项行号级失实[:66→:56/201 枚举漏 :1209/:134→:136]机理断言零失实）。修复 3 项（P3×3——两处副位传播补写+三处行号勘正，成本趋零随轮清偿）。
> **R8 审查组织（第二周期 Round 3）：** 单深度推演 Agent 新轴四轴（不重复第一周期 R3 四轴——聚焦 R6/R7 修复的新执行面）：轴 1 crawler 补挂回归爆炸半径[发现 P1×1+P2×1]/轴 2 三态豁免执行链[P2×1+P3×1]/轴 3 新错误面承载映射收口[P3×2]/轴 4 R6-R7 组合自拆[P3×2]——8 项发现全部为 R6/R7 修复衍生（「修复的修复」模式），无一触及第一周期已收敛面；通过面登记 4 项留痕（AC-8 采样端点与 timeout 零交互/metrics 断言承载闭合/工厂加参对既有调用零破坏/audit 测试面差异由 R8-1 承载非 Story 矛盾）。主会话实测定谳 1 项（test_crawler.py `_create_app` 裸装配+23 测试函数+document_upload override 先例行号）。修复 8 项（P1×1+P2×2+P3×5）。

**收敛声明（R5 终审，2026-11-21）：** 本 Story 文档审查周期五轮收敛（v1.0.0→v1.3.1，提交 9f1325df/6fc540f6/f7b7fcea/本轮收敛批与轮记录一一对应零游离）。周期总账：R1 四调研+双评审（P0×4：trace 端点域错配迁 plans//health 双错勘正/SCOPED 双缺陷重设计/上游端点覆盖差集登记）、R2 回归核查 15⁄15 完备+新增内容核验 4 项清偿、R3 四轴推演 9 项清偿（含 7-1 CR6 三条教训反哺）、R4 纯验证 6 通过+1 项 P3、R5 六节全过（双向 8⁄8+锚点 17⁄17 精确零失实）——修复台账 30 行（P0×4+P1×7+P2×9+P3×10，全部清偿零残留）；OD 表扩至 16 行+DF 登记句 8+1 项。零 P0/P1/P2 残留；R4-1 排版级随本收敛提交清偿。Story 维持 `ready-for-dev`，可进入 dev-story。

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

（dev-story 实施后代码审查轮次填充）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.5.0
**创建日期/Created:** 2026-11-21
**最后更新/Last Updated:** 2026-11-21
**更新说明/Description:**
- v1.5.0: 第二审查周期 Round 3（R8：单深度推演新轴四轴——crawler 补挂回归爆炸半径/三态豁免执行链/新错误面承载映射收口/R6-R7 组合自拆）——8 项发现全部清偿（全部为 R6/R7 修复的新执行面衍生，无一触及第一周期已收敛面）：P1×1（crawler 既有测试面适配零承载——test_crawler.py `_create_app` 裸装配零认证 override，4 端点补挂后 ~14 端点测试 200→401 全红打破 Task 1 DoD「17 文件全绿」[audit 无 test_audit.py 零破坏——两 router 测试面差异]——Task 1 绿补适配承载[工厂注入 get_current_user_override stub——document_upload 先例]）+P2×2（Task 1 变异第三项时间线断链[401 矩阵承载在 Task 6]——Task 1 红补最小 401 断言+变异锚点勘正/Task 8.3 白名单三态与断言作用域不匹配[作用域内唯一无认证端点是 health——三态注册表是 AC-3 验收口径误植进架构断言]——机制钦定按冻结端点矩阵清单遍历+作用域内豁免=health）+P3×5（AC-6 security:[] 限定设计豁免端点[metrics 无 yaml 契约不适用防误补与 OD-14 冲突]/矩阵与端点单测双承载语义区分注记/380+443 验收不单列场景注记[单测承载足够有意设计]/timeout 断言锚 ExecutionContext.timeout_sec==请求值/Retry-After 可选不进 AC-4 双头断言）；通过面登记 4 项留痕（AC-8 采样端点与 timeout 零交互/metrics 断言承载闭合/工厂加参零破坏/audit 测试面差异归 R8-1）
- v1.4.1: 第二审查周期 Round 2（R7：双调研——R7-A 修复回归核查[R6-1~R6-13 git 取证 11/13 传播完备、P0/P1 全部到位、新破口零发现、场景算术三处一致]+R7-B 新增内容核验[30+ 新锚点对照 HEAD：crawler 行号族 5/5、异常链路全中、StrategicReport 纯元数据实证、三态口径六处互洽——3 项行号级失实]）——3 项 P3 随轮清偿：成功码钦定联动 Subtask 0.3+Retry-After 补传 AC-7 时序注记/Subtask 7.4 两副位（R6-8/R6-11 传播漏网——台账自提及而正文副位漏传）+get_blm_planning_status.py:56 行号勘正×2+yaml 201 先例枚举补全 :1209+AgentNotFoundError :136 精确化（机理断言零失实）
- v1.0.0: 创建故事文件（4 调研 Agent 并行：REST 资产盘点/端口签名核验/留项与验收风格/架构边界深读；前置留项 14 条裁定落档含三向定夺承载；DC-1~DC-7 架构决策+OD-1~OD-9 偏离预告；13 端点冻结矩阵+13 唯一端口 14 消费对 SSOT 表[签名级核验]+认证/错误响应/租户/契约四契约面+6.1-DF5/6.5a-DF1 清偿承载+per-plan 锁+SCOPED 迁移）
- v1.4.0: 第二审查周期 Round 1（R6：D1 四调研[锚点终局复核/业界最佳实践对标/消费者可实施性/安全与可观测性]+D2 双评审[A 正确性一致性+B 合理可行性对抗裁定]+主会话实测定谳 9 组）——13 项修复：P0×1（crawler 4 端点零认证+工厂无认证参数而 Story 写「既有零改动」——勘正为认证实质改造承载[工厂加参+4 端点补挂，Task 1 与 audit 同批；评审 B 三选项裁定 defer 自相矛盾]）+P1×3（metrics 零认证豁免面三态口径[设计豁免 login/health+既有形态豁免 metrics+弱形态注记 refresh/logout]/异常表 480 勘正[PlanningNotFoundError 非 NotFound 202——dev 按表断言必红]/380+443 两行补登[未知 slug 与 agent 不存在 404 首要路径]）+P2×5（消息安全「复验」勘正为新增断言+OD-17/cost_budget 删字段无透传落点/成功码钦定全部 200/export 语义定谳元数据 JSON+OD-18）+P3×4（锚点 8 处勘正[architecture.md 端点清单行号族+DC-2 :150-195 残留]/业界注记 4 条[2 条证伪拒绝]/可观测性 3 注记/序列化 4 注记）；OD 表扩至 18 行；场景计数 17/21 不变
- v1.3.1: 文档审查周期收敛（R4 纯验证七维度 6 通过+1 项 P3[R4-1 L101 括号排版残留——随本批清偿]+R5 独立终审六节全过[周期闭合 3 提交零游离/双向抽验 8⁄8/台账完整/门禁如实/锚点 17⁄17 精确零失实/收敛判定可收敛]——收敛声明入 Story；周期总账：五轮 30 修复行[P0×4+P1×7+P2×9+P3×10]全清偿+OD 扩至 16 行+DF 8+1 项登记句；Story 维持 ready-for-dev 可进入 dev-story）
- v1.3.0: 文档审查 Round 3（单深度推演 Agent 四轴：Task 依赖干跑/17 场景期望唯一性/AC↔测试承载矩阵/长状态时间线）——9 项发现全部清偿：P1×1[R3-1 checkpoint given 引用 7-1 R3-7 过时先例已被 CR6 判连带 skip与「确定性全绿」口径矛盾——改仓储/snapshot 直构绕开 LLM 依赖链]+P2×3[R3-2 Task 0 行为型契约测试 import 形态定谳拆分[顶部 import 连坐 yaml 断言——Task 0 仅 yaml 消费型，行为型随 Task 1-5 逐族补入]/R3-3 trace+archive given 前置补决策[R3-4 同源 snapshot 直构]/R3-4 tool execute LLM skip 归类补注记]+P3×5[health version 来源钦定 importlib.metadata/metrics 承载面钦定单测/AC-4 四态分组建议/跨租户 given 真实 upload+同租户正查对照防 CR6-2 假绿/parse_status 判别锚+recover 后 list 复核建议]；推演通过面：Task 序 import 闭合全过+port_contract 时间线自洽+28 条承载 25 闭合+期望唯一性机制成立；7-1 CR6 三条最新教训直接反哺（过时先例/租户分叉假绿/parse_status 锚）
- v1.2.0: 文档审查 Round 2（双调研 Agent：R2-A 回归核查[R1-1~R1-15 逐项 git 取证 15/15 完备+新破口零发现+残留终扫零残留+场景算术自洽]+R2-B 新增内容事实核验[R1 新写入声明核出 4 项：OD-13 节号端点名双失实勘正[§8.2.7 /archive/timeline——旧 timeline-diff 系不精确继承名]/覆盖差集二次漏网补登[GET /documents/{id} §8.2.1 P0 入 OD-12+POST /plans 入 OD-13]/OD-14 模糊数精确化[激活面 21 端点确定缺口 crawler 4+monitoring 1——auth 11/audit 5 已有契约]/checkpoint 参数偏离新增 OD-16[复合双参 vs §8.2.6 钦定单参]]；组合交互面全通过[14 path 七处一致/SCOPED 双对象 11 处一致/trace 三角/created_via 三处]；OD-15 DF 编号勘正+映射句增 OD-16 归宿）
- v1.1.0: 文档审查 Round 1（D1 四调研+D2 双评审）——P0×4 清偿：①trace 端点域错配（迁 GET /plans/{plan_id}/trace，OD-10——端口 plan 域现实+CLI 先例+与 /search/trace/{document_id} 引文端点语义分立）②/health 改名方案双错勘正（实为 embedding server 契约有消费方——改为新增 /system/health 保留 /health，漂移修正缩至一处，新 path 12→14）③SCOPED 迁移双缺陷重设计（双对象 service :2036+use_case :2065+机制诚实注记[clear_scoped 生产零接线下 SCOPED≡SINGLETON——声明语义正确化，真实隔离归 OD-15]+analyst_view 传播注记+lifetime 断言移 Task 2 红阶段防 CI 可见红窗）④上游端点覆盖差集登记（OD-10~OD-15 六行：compare/financial P0 不承载+P1 端点族+slug 偏离+激活面契约缺口+clear_scoped 专项+DF 映射句对齐）；P1×6：零手动 HTTPException 勘正（auth.py 实证）/audit 5 端点 Depends 实质改造/端口计数 15 对 18 端口/archive-query path 补入/端点层 find() 前置查询 404 设计决策（list_versions 返 [] 与 parse 合成 FAILED 的宽语义不承担 404——主会话实测定谳）/ErrorResponse 已收敛勘正（shared_models.py:12）；P2/P3 15 项（注册名/文件名/三向定夺预判改判/计数行号族/可行性注记族——monitoring 挂载形态冻结/锁字典无界增长/密码哈希归因/并发 409 时序/场景覆盖映射等）
