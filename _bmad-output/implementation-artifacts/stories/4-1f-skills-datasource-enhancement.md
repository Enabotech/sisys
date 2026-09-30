# Story 4.1f: Skills 数据源扩展（专利/财报/行业量化域适配器 + 中文参数验证）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 工具工程师,
**I want** 新增 EPO Espacenet OPS / SEC EDGAR / UN Comtrade 三个数据源适配器并完成受益 Skills 的声明重分配，同时对现有 tavily/newsapi 适配器启用中文参数自适应,
**So that** Skills 工具箱的维度级「≥3 独立来源」三角化缺口（专利布局 1 源/市场份额无企业级源/行业量化无商品级源/中文媒体盲区）得到实质收敛，竞品分析与行业分析类工具的实证数据质量达到可交付水准。

### 业务价值

4.1c/4.1d/4.1e 完成后 23 Skills 全部成熟化（2026-09-29 done），但评审推广调研暴露「源数量充足性」缺口——现有 8 适配器池语义域分布失衡（专利 1/宏观 4/新闻检索 2/气候 1），维度级 ≥3 达成仅 2/29 处。本 Story 依据四域预筛报告（`planning-artifacts/data-source-expansion-prescreening.md`——19 候选源实测裁定：可行 7/有条件 8/不可行 10）落地第一批：三个零许可成本、实测已通的官方源适配器 + 现有源中文参数自适应 + 声明重分配联动。

本 Story 是**基础设施层 Story**（R3 主战场）：三个新适配器实现既有 `DataSourcePort`（R1 既有端口零新增），注册进组合根既有聚合链（R2 既有组合注入零改动）；生产代码改动面 = infrastructure 适配器/config + composition_root 注册 + 契约库测试基建（required_fields 按源定制重构）。**唯二内容资产改动** = 受益 Skill 内容资产整体（SKILL.md 声明/SOP + references/ 三文件 + yaml 逐字锁死行）+ tavily/newsapi 适配器 CJK 自适应（~10 行/适配器）——注意与「生产链路」节「唯二生产 .py 行为改动」是两个口径（前者内容资产、后者生产代码）。

**来源:** [`epics_v1.0.md`](../../planning-artifacts/epics_v1.0.md) - Epic 4: 战略工具箱，Story 4.1f（P1-8，V1；:1090-1146）
**前置依赖:** 4.1a/4.1b/4.1c/4.1d/4.1e（✅ 全 done——**4.1d 亦为前置**：本 Story 大改其测试资产 test_skill_mixed_data_contracts.py / test_arch_skill_mixed_data.py / 集成与验收联动）+ 外部前置（EPO OPS Consumer Key / UN Comtrade key 免费注册——**申请可即刻异步启动，等待期不阻塞 Task 0-1 与 EDGAR 全部工作**；SEC EDGAR 免 key）
**后续依赖:** Phase 2（Google Patents BigQuery/巨潮 cninfo/港交所披露易/协会 crawler/PDF 管道）→ 后续 Story 4.1g

### ⚠️ Story 范围澄清（重要）

**本 Story 交付（范围边界）：**

- 三个新适配器：`epo-ops`（专利域第一优先——OAuth2 + `pa=` 申请人检索）/ `sec-edgar`（企业财报域——免 key + XBRL）/ `comtrade`（行业量化域——HS 商品级 + 日配额守卫）
- tavily/newsapi 适配器中文参数 CJK 自适应（~10 行/适配器 + A/B 实测报告）
- `required_fields` 按源定制联动（ADAPTER_SSOT 三元组 → 四元组重构——承载原 4.3 defer 项）
- 受益 Skill 声明重分配：competitor-analysis（4→6 源，无治理前提）+ vrio-framework（2→3 源，**epics 4.1f 任务 6 已明文授权——无条件执行，D2 修订留痕**）+ disruptive-innovation（2→3 源，**D8 重开签收前提——见下**）
- Comtrade 语义匹配度评估留痕（appeals/kpi-tree 等其余声明 Skill 是否增补——epics 任务 6 第 3 子项，结论留痕不强行凑源）+ D2 修订评审结论留痕（其余 9 个 4-1d Skill 不放宽理由——epics 任务 6 第 4 子项）
- 能力边界声明与合规登记（architecture.md：IDC/Gartner/Euromonitor 不可得 + 新源 UA/署名/配额合规——含 Comtrade 配额政策）
- 适配器注册链全触点（组合根注册 + `_build_data_source_adapters` 元组表 + shutdown 清理 + `ADAPTER_PORT_SPECS` 契约表 + 架构测试两文件四联动点——`test_arch_skill_data_collection.py` 与 `test_arch_data_source.py`）

**不在本 Story 范围（明确划出）：**

- **Phase 2 适配器**（Google Patents BigQuery/巨潮 cninfo/港交所披露易/中汽协乘联会 crawler/PDF→文本管道）→ Story 4.1g（预筛报告 §四）
- **百度千帆/东财/新浪等专职中文源**——Phase 0 CJK 自适应实测后评估剩余缺口再议（本 Story AC-1 闭环判断，评估结论留痕不实施）
- **OAuth2 共享抽象基类**——单源使用不预抽（YAGNI），未来第二家 OAuth2 源出现时再抽
- **跨进程精确配额计数**（Redis 计数器）——单进程组合根部署下进程内计数够用，多实例部署需求出现时再议
- **既有 8 源的 required_fields 改值**——8 既有源保持 `("indicator","value")` 零漂移（41 处 frontmatter 联动核验，不改值）
- **标记语法第三参数（parameters 透传）**——CJK 自适应方案已绕开此需求（决策 D7）；扩展标记语法属生产链路行为变更，如未来需要独立决策
- **tavily `topic=news|finance` 与 newsapi `domains` 参数**（epics AC-1 列举的另两个质量杠杆）——本 Story 仅做 CJK 门控注入 `country=china`/`language=zh`（确定性规则、英文路径零影响）；topic/domains 属内容质量调优参数，纳入 AC-1 A/B 实测报告的**评估项**（有实测证据再议引入，无证据不预加——避免影响既有 13 个声明 Skill 英文场景）
- **EDGAR required_fields 以检索模式为准**（`("company","form","filed_at")`）——XBRL 模式返回 `{"concept","unit","values"}` 字段形态不同，单一 per-source 元组不覆盖双形态；差异在 SKILL.md §5 显式声明（epics AC-5 示例 `[concept, value, period]` 的偏差在此登记）

### ⚠️ 治理前置：D8 决策重开（阻断性——Task 0 必办）

**调研发现的治理冲突（阻断 disruptive 增源）：** 4-1c Story 文件审查记录（`4-1c-skills-data-collection-integration.md:1180,:1186`）载明——「**D8（Epic 2 源偏差签收）已于 2026-09-28 由 Epic owner（项目负责人）签收：2 源双源交叉验证为终态，不追加第三源**（**WIPO/EPO 适配器排期取消**，Defer 项关闭）」；`architecture.md` D4 决策行（:2829——4.1c 决策表「三角化定义」行，注意 architecture.md 另有 :2842（4.1d）/:2864（4.1e）两处同名 D4，均非本治理留痕目标）同款留痕。

本 Story 给 disruptive-innovation 增补 epo-ops 属于**重开已关闭的 Epic owner 级签收**。

**vrio-framework 与 disruptive 治理分级不同（重要澄清）：** D8 签收射程仅 disruptive-innovation（4-1c 范畴）；vrio-framework 的 2 源策略来自 4-1d **D2「统一 2 源策略」**（Story 级决策），且 epics 4.1f 任务 6（`epics_v1.0.md:1127`）**已明文授权**「disruptive-innovation / vrio-framework：增补 EPO OPS」+ 任务 6 第 4 子项（:1129）授权「D2『统一 2 源』决策修订评审」。Story 级决策的修订由 epics 授权即可闭环——**vrio 增源 + D2 修订（`test_unified_two_source_policy` 豁免表改写）不设签收前提，按 epics 授权无条件执行并在 Dev Agent Record 留痕**（Task 0.1 HALT 时向 owner 知会即可，不构成阻断）。

**D8 重开的优先级论证（为何 epics 授权不构成隐式重开）：** epics 4.1f 立项（2026-09-29）晚于 D8 签收（2026-09-28）一天且任务 6 已明文授权增补 EPO——但 4-1c Story D8 条目与 architecture.md :2829 D4 行至今仍载「终态，不追加第三源」，**记录层冲突未消除**（epics 立项 diff 未触及这两处留痕）。owner 级签收的重开必须同级显式仪式 + 双文件补记，epics 任务表述不能替代——故 HALT 为必办项，请求时可直接引用 epics 4.1f 任务 6 授权加速签认。

**处理方式（Task 0 决策项 D-08）：** dev-story 执行到 Task 0 时 **HALT 向 Epic owner（用户）显式请求 D8 重开签收**（disruptive 重开 + vrio 知会同点进行）——签收则 disruptive 增源按主线执行并在 4-1c Story 文件 D8 条目 + architecture.md :2829 D4 行补记重开留痕；**未签收则 disruptive 增源子任务跳过**（competitor/vrio 增源不受影响——competitor 无「不追加」签收、vrio 有 epics 授权），AC-6 验证标准中 disruptive 相关项按实际签收结果记录。**HALT 等待期不阻塞**：Task 0.2-0.6 与 Task 1-5、Task 6 循环 A-B（competitor/vrio）可先行（适配器交付与 D8 解耦——三个适配器无论如何都交付并注册）。

### ⚠️ 命名规范声明（强制）

**禁止使用故事编号命名编码开发**（4-1c 实施期确立）。全部新增文件功能性命名（无 `_4_1f` 后缀）。新数据源 name（kebab-case，= DataSourceRef.name = frontmatter 声明名 = resolver 映射键 = ADAPTER_SSOT 键，四位一体）：**`epo-ops` / `sec-edgar` / `comtrade`**；组合根端口名 `data_source_epo_ops` / `data_source_sec_edgar` / `data_source_comtrade`；环境变量 `EPO_OPS_*` / `SEC_EDGAR_*` / `COMTRADE_*`（四键模式 API_KEY/API_URL/TIMEOUT/TTL_SECONDS 的变体——**EPO 为 5 变量**：`EPO_OPS_API_URL`/`EPO_OPS_TIMEOUT`/`EPO_OPS_TTL_SECONDS` + `EPO_OPS_CONSUMER_KEY`/`EPO_OPS_CONSUMER_SECRET` 双凭据替代 API_KEY；**EDGAR 为 3 变量**（无任何 Key）：`SEC_EDGAR_API_URL`/`SEC_EDGAR_TIMEOUT`/`SEC_EDGAR_TTL_SECONDS`；**Comtrade 为 4 变量**：`COMTRADE_API_KEY`/`COMTRADE_API_URL`/`COMTRADE_TIMEOUT`/`COMTRADE_TTL_SECONDS`——key 可选提升配额，见数据契约四）。

---

## 🛡️ 硬约束声明（CLAUDE.md §5）

### 领域零依赖（FR-AR-01）

- 本 Story 生产代码改动**全部位于 infrastructure 层**（适配器/config）+ composition_root（注册）——`src/domain/` 与 `src/application/` 生产代码**零改动**（R1 既有 DataSourcePort 不动、R2 既有组合注入不动）；受益 Skill 的 SKILL.md 是内容资产非代码
- domain 层禁止外部依赖（`.importlinter` 契约）：新适配器禁止 import application（六边形依赖倒置——经组合根注入）
- **新适配器必须完整复用 `_http_helpers.request_json_with_resilience`**（tenacity 重试 + CircuitBreaker + 异常映射集中点）——**HTTP 状态码/传输异常 → 领域异常的映射禁止自写**（411/412/413/101/302 的抛出逻辑全在 helper）；适配器仅允许三类**自抛**（非 HTTP 映射）：`ValidationError`(201) 输入参数前置校验（Comtrade 管道串缺 cmd / `parse_int_param` 同族语义）、`DataSourceResponseError`(413) 响应结构校验与非法模式前缀（`_extract_*` 二段校验既有模式）、`DataSourceRateLimitError`(412) 配额守卫前置拦截（EPO 周字节 / Comtrade 日请求数——零请求消耗语义）

### 异常体系强制

- **本 Story 零新增领域异常**（全部复用既有——见「领域异常契约」节复用表）
- 提交前三条 grep 自查零新引入（既有命中均为历史代码）
- 禁止 `# noqa` / `# type: ignore` / `# pylint: disable`

### Commit & Push 规范

- 提交信息禁止 AI 署名；禁止 `--no-verify`；main 分支直接开发

### Skills 内容约束

- 受益 Skill SKILL.md 修改保持 ≤500 行（余量充足：competitor 259/disruptive 210/vrio 218）
- **每个新声明源必须在 SKILL.md body 出现 ≥1 个 `$DATA_SOURCE` 标记**（`assert_cross_consistency` 双向断言——标记正则 `[\w-]+` 天然兼容连字符名 `epo-ops`）
- **源数计数表述全量同步（grep 驱动，SKILL.md 之外还含 references/ 与 templates/ 联动面）**：
  - competitor：「4 个声明源」2 处（SKILL.md L175/L235）+ 维度级计数 L177（「专利布局仅 uspto 1 源」→ 2 源）+ **references/triangulation.md 3 处**（:4「4 个声明源全部参与采集」、:10「4 个声明源中按 §5 维度映射」、:21 标题「## 4 源角色分工」）；「专利维度未三角化」标注撤除 2 处（SKILL.md L178-179 表后段落 + references/triangulation.md:43）
  - disruptive：「双源」**11 处**（SKILL.md L6/L79/L100/L138/L140/L142/L150/L185/L188/L190/L207）+ L188「白名单内 2 源」+ **references/ 三文件联动**（triangulation.md 全文以「双源交叉验证」为方法论标题与规则——L1 标题/L4/L6「双源角色分工」/L16/L21/L34 等，workshop_guide.md :11/:19，scoring_anchors.md **:3/:14/:20/:33**——增源后方法论表述升级为「专利双库 + 市场单源互证」需逐处评估改写）
  - vrio：SKILL.md L138「双源交叉」1 处 + 引言 L98-99 源名二元组表述（USPTO/Tavily → 增 EPO 提及）
- **SKILL.md 与 yaml 逐字锁死的 description 双写同步**（disruptive `sources` description「数据来源（双源交叉验证）」与 `skill_io_schemas.yaml:383-385`；competitor `patent_signals` description 与 yaml:257-259——改措辞必须两处同改）

### 代码质量门禁

- `poetry run ruff check src/ tests/`（行宽 128，E/F/I/N/W）+ `poetry run mypy src/` + `pytest tests/ -n 8` 连续 5 次无随机失败 + pre-commit 全过

---

## 🎯 领域异常契约

> **原则**：异常是领域契约的一部分。本 Story **不新增领域异常**（显式决策 D-EX——全部失败路径已由 4.1b 异常体系覆盖，`_http_helpers` 集中映射）。

| 场景 | 复用异常 | 编码 | 依据 |
|------|---------|------|------|
| 新源 HTTP 5xx/连接失败/熔断 | `DataSourceUnavailableError` | EXCEPTION_411 | `_http_helpers.py:192-197,:287-303` 既有 |
| EPO OAuth2 令牌端点 401/403（凭证错误） | `ConfigurationError` | EXCEPTION_101 | helper :219-223 既有（消息零 Key 材料） |
| **EPO 业务请求 401（令牌过期失效）** | `ConfigurationError` | EXCEPTION_101 | helper :219-223 将 401 统一抛 101——适配器在 helper 之上实现重取：**捕获 `ConfigurationError` → 判别 `exc.context.get("status_code") == 401`（区分 403 凭证拒绝与 URL 畸形——`base_exceptions.py:63` context 公开可读）→ 强制刷新令牌 → 重发一次 → 仍 401 上抛 101**；禁止为看状态码绕开 helper 用裸 client（401 走 `on_ignored()` :249，重取不污染熔断统计） |
| 新源 HTTP 429 限流 | `DataSourceRateLimitError` | EXCEPTION_412 | helper :211-215 既有 |
| **EPO 4GB/周配额超限（适配器前置守卫）** | `DataSourceRateLimitError` | EXCEPTION_412 | 配额耗尽与限流同族语义（D3 决策）——守卫在 fetch 前置检查抛出，零请求消耗 |
| **Comtrade 500 次/天配额超限（适配器前置守卫）** | `DataSourceRateLimitError` | EXCEPTION_412 | epics AC-4「配额守卫」承载——进程内日窗口请求计数（UTC 00:00 重置），守卫在 fetch 前置检查抛出（守卫模式复用 EPO 周窗口设计，仅计数口径为请求数非字节） |
| 新源响应结构异常/缺字段/非法 JSON | `DataSourceResponseError` | EXCEPTION_413 | helper :227-240,:304-311 + 适配器 `_extract_*` 二段校验既有模式 |
| EPO OAuth2 令牌获取网络失败（重试耗尽） | `DataSourceUnavailableError` | EXCEPTION_411 | 令牌获取走同款 resilience helper（令牌获取与业务请求**共用同一 CircuitBreaker**——单上游服务语义；401 刷新走 on_ignored 不计数） |
| Comtrade key 缺失 | （不抛——key 可选） | 不适用 | Comtrade 无条件注册 + preview 端点免 key 兜底（数据契约四）；构造器不因 key 缺失抛 101（与 newsapi/tavily 条件注册形态不同——见 D5 决策） |
| query 参数非法（page_size 非整数 / Comtrade 管道串缺 cmd / EDGAR 非法模式前缀） | `ValidationError` | EXCEPTION_201 | `parse_int_param` helper :91-125 既有 + 适配器输入前置校验同族自抛（非 HTTP 映射——见硬约束节三类自抛边界） |
| EDGAR 请求超时 | `TimeoutError` | EXCEPTION_302 | helper :251-259 既有 |

**提交前自查**：三条 grep 零新引入 + 新适配器文件 grep `raise ` 确认仅 raise 既有异常类型（结构校验的 `DataSourceResponseError` + 守卫的 `DataSourceRateLimitError` + 输入校验的 `ValidationError`）。

---

## 🎯 测试隔离约束

- **适配器单测零外网**：`httpx.MockTransport` 工厂注入（`_make_adapter(handler, ...)` 范本——`test_uspto_adapter.py:33-41`；`retry_min_wait=0.01/retry_max_wait=0.02` 测试加速）
- **OAuth2 令牌流单测**：MockTransport 拦截 `/3.2/auth/token` 断言 Basic auth 头 + 令牌缓存命中不重复请求（capture handler 计数）
- **配额守卫单测**：守卫计数器可注入初始值（构造参数 `quota_bytes_used` 或测试直接操作计数器）——避免单测烧真实配额
- **集成/验收**：key 就绪时真实端点连通 + TestTenant UUID 前缀隔离（`sisys:cache:datasource:{tenant}:*` teardown）；**key 未就绪 `pytest.skip()` 动态跳**（禁止写死 skip——EDGAR 免 key 可无条件真实连）
- BDD 步骤禁 `@pytest.mark.asyncio`（`event_loop.run_until_complete`）；`asyncio.Lock` 类变量；假 Key 低熵常量 `"fake-epo-key-test1234"` 规避 detect-secrets
- 条件注册验证用子进程探针先例（`test_acceptance_data_source.py:606-637`——本进程 bootstrap 已执行无法回滚）

---

## 🌐 端口与数据契约

### 端口契约（本 Story 零端口新增 — 显式决策）

- **R1 符合性**：`DataSourcePort`（`src/domain/ports/data_source.py`）为既有领域端口，零修改；`DataSourceQuery.parameters` 既有字段零修改
- **R2 符合性**：`DataSourceResolverService` 既有组合注入（adapters + cache + event_publisher）零修改；新适配器经 `_build_data_source_adapters` 元组表进入聚合
- **R3 符合性（本 Story 主战场）**：三个新实现于 `src/infrastructure/external_services/datasources/`——与既有 8 适配器同目录同模式（支持扩展其他同类技术实现）
- **R4**：无接口层改动

### 数据契约一：三新源元数据表（ADAPTER_SSOT 扩展条目——Task 0 定稿基线）

| name | url | api_type | ttl_seconds | required_fields（按源定制——D6） | Key | 注册形态 |
|---|---|---|---|---|---|---|
| `epo-ops` | `https://ops.epo.org` | `rest_json` | `604800`（周更数据） | `("title", "applicant", "filing_date")` | Consumer Key/Secret（OAuth2） | 条件注册（`EPO_OPS_CONSUMER_KEY` + `EPO_OPS_CONSUMER_SECRET` 双门） |
| `sec-edgar` | `https://efts.sec.gov`（base） | `rest_json` | `2592000`（财报月/季频） | `("company", "form", "filed_at")`（检索模式为准——XBRL 模式字段差异见契约三声明） | **免 key**（强制 UA 头） | **无条件注册**（A 组范式——worldbank 先例） |
| `comtrade` | `https://comtradeapi.un.org` | `rest_json` | `604800`（数据周/月频，7 天缓存保守值） | `("cmd_code", "trade_value", "period")` | `COMTRADE_API_KEY`（可选——有 key 加 `Ocp-Apim-Subscription-Key` 头提升 500 次/天配额） | **无条件注册**（preview 端点免 key 兜底——与 EDGAR 统一「官方免费通道可达即无条件注册，key 为增强」逻辑，Story 层定稿见 D5） |

注：ADAPTER_SSOT 由三元组 `(url, api_type, ttl_seconds)` 扩为**四元组** `(url, api_type, ttl_seconds, required_fields)`——8 既有源第四项一律 `("indicator", "value")`（零漂移）；ttl 范围校验 `60 <= ttl <= 2592000` 既有不变（强制点 `DataSourceRef.__post_init__`，`src/domain/value_objects/data_source.py:135-144`）。

### 数据契约二：EPO OPS 适配器行为契约（预筛实测依据）

- **认证**：OAuth2 client-credentials——`POST /3.2/auth/token`（Basic auth = consumer_key:consumer_secret，`grant_type=client_credentials`）→ access_token 缓存（进程内 + 过期提前 60s 刷新）；业务请求 `Authorization: Bearer <token>`；**401 时令牌失效重取一次**（实现路径见异常契约表「EPO 业务请求 401」行——helper 抛 101 后按 `context.status_code == 401` 判别重取，禁止裸 client 绕行）；令牌获取走同款 resilience helper 并与业务请求共用 CircuitBreaker，**`retry_*` 参数经适配器构造器透传至令牌管理器**（测试注入 `retry_min_wait=0.01` 同样生效于令牌端点——避免单测退避拖秒）
- **检索**：`GET /3.2/published-data/search?q=pa="华为" and ti="battery"`（CQL——`pa=` 申请人（支持中文名）/ `ti=` `ab=` `ta=` 关键词 / `cpc=` 分类 / `pd=` 日期）+ `Accept: application/json` + `Range` 头分页
- **配额守卫（D3）**：进程内周窗口字节累计（周一 00:00 GMT 重置）——累计值超过 `4 * 1024**3` 时 fetch 前置抛 `DataSourceRateLimitError`（消息含已用量与重置时间）；**字节计量口径 = 响应 JSON 序列化字节数**（`len(json.dumps(data).encode())`——helper 只返回解析后 JSON，序列化近似是唯一 helper 兼容口径；事后累计 + 前置按累计值拦截，不做响应体预估）；计数器 `asyncio.Lock` 类变量保护；**构造注入 `now_fn`（与令牌管理器同款 clock）**——周窗口重置单测通过注入时间函数验证（freezegun 无项目先例，不引入）
- **query 规范（写入受益 Skill §5/§6）**：CQL 表达式字符串（如 `pa="BYD" and ti="battery"`）——结构化检索语法（非自然语言，同 world-bank 指标码范式）
- **confidence**：0.9（官方专利局）

### 数据契约三：SEC EDGAR 适配器行为契约

- **UA 强制**：`User-Agent: sisys-tools/1.0 (contact@sisys.local)` 常量（官方 Fair Access 要求「公司名 邮箱」格式——无 UA 实测 403）
- **限速**：进程内令牌桶 `8 req/s`（官方 10 留余量；`asyncio.Semaphore` + 时间窗实现）
- **fetch 双模式（query 前缀分派）**：
  - 检索模式（缺省）：query = 检索词（如 `"market share" forms=10-K` 或纯关键词）→ `GET https://efts.sec.gov/LATEST/search-index?q=...&forms=10-K`（Elasticsearch 风格 JSON → `{"filings": [{"company","cik","form","filed_at","file_url"}]}`）
  - XBRL 模式：query 前缀 `xbrl:` → `xbrl:CIK0001318605:Revenues` 调 `data.sec.gov/api/xbrl/companyconcept/...`（单指标时序）或 `xbrl-frame:us-gaap/Revenues/CY2024Q1` 调 frames（跨公司横截面）→ `{"concept","unit","values":[...]}`
  - 两个 base_url（efts/data.sec.gov/archives）——config 三 URL 字段或单 client 多 base 拼绝对 URL（Task 0 定稿：**绝对 URL 拼接**，单 httpx client——httpx 传绝对 URL 时忽略 base_url，双 host 直连成立；无重定向环节与 `follow_redirects` 禁用约束无冲突）
- **query 规范**：检索词（自然语言或 `"关键词" forms=表单类型` 语法）或 `xbrl:CIK:概念` 前缀；**非法前缀（非 `xbrl:`/`xbrl-frame:` 起始且非检索模式缺省语义）→ `ValidationError`(201) 输入前置校验**（query 语法错误归 201，非响应结构 413——与异常契约表「query 参数非法」行对齐）
- **required_fields 双模式声明**：契约一定值 `("company","form","filed_at")` 以**检索模式**（缺省主力模式）为准；XBRL 模式返回 `{"concept","unit","values"}` 字段形态不同——差异在受益 Skill §5 口径段显式声明（LLM 字段指引不失真）；epics AC-5 示例 `[concept, value, period]` 的偏差在此登记留痕
- **confidence**：0.95（美政府法定披露）

### 数据契约四：UN Comtrade 适配器行为契约

- **注册形态（Story 层定稿——D5）**：**无条件注册**——preview 端点免 key 兜底可达（实测 195 条真实记录），`COMTRADE_API_KEY` 为可选增强（有 key 时请求加 `Ocp-Apim-Subscription-Key` 头，配额提升至 500 次/天）；与 EDGAR 统一「官方免费通道可达即无条件注册，key 为配额增强」逻辑；构造器 key 可选（缺失不抛 101，裸 preview 模式）
- **日配额守卫（epics AC-4 承载）**：进程内日窗口请求计数（UTC 00:00 重置）——计数达 500 时 fetch 前置抛 `DataSourceRateLimitError`(412)（消息含当日已用次数与重置时间；守卫模式复用 EPO 周窗口设计：`asyncio.Lock` 类变量 + 构造注入 `now_fn` + 可注入初始计数——仅计数口径为请求数非字节，无 key 时同守卫按 preview 低配额更保守值 100 次/天可选，Task 0 定稿具体值）
- **检索**：`GET /public/v1/preview/C/A/HS?reporterCode=156&period=2024&cmdCode=8703&flowCode=X`（实测无 key 亦通——key 提升 500 次/天配额；路径 `C/A/HS` = typeCode/freqCode/classificationCode，月频数据用 `C/M/HS`——query 示例 period 按实际频率给年或月值）
- **query 规范**：管道分隔参数串 `reporter=156|cmd=8703|flow=X|period=2024`（适配器解析为 query params——HS 商品码 `cmd` 必填（缺失→201 输入前置校验），reporter 缺省 156 中国口径）（Task 0 定稿：**结构化管道串**，同 china-nbs 路径范式「机器码非自然语言」）
- **confidence**：0.9（联合国官方统计）

### 数据契约五：中文参数 CJK 自适应（D7——tavily/newsapi 扩展）

- **规则**：适配器 fetch 内检测 `query.query` 是否含 CJK 字符（`any("一" <= ch <= "鿿" for ch in query.query)`）：
  - tavily：含 CJK → 请求体加 `"country": "china"`（官方全名枚举——官方文档确认 country 参数存在且枚举含 china；**限定 topic=general 时可用**，适配器现不传 topic（默认 general）故生效）；不含 → 行为零变化
  - newsapi：含 CJK → params 加 `"language": "zh"`（ISO 639-1，`/v2/everything` 端点官方支持；注意 `country` 参数属 `/v2/top-headlines` 端点不适用）；不含 → 行为零变化
- **理由**：零链路改动（标记语法不传 parameters——`src/application/services/data_source_marker.py:211` 既有两参数形态，`_MARKER_PATTERN :43` 恰两个字符串字面量参数）+ 零既有影响（英文 query 路径请求体逐键不变）+ 确定性规则不依赖 LLM 判断
- **epics AC-1 参数面偏差登记**：epics 列举的 tavily `language=zh-cn`/`topic=news|finance` 与 newsapi `domains` 未纳入本 Story 自动注入（CJK 门控仅注入确定性单参数）——topic/domains 纳入 A/B 实测报告**评估项**（有实测证据再议引入，见范围澄清节）；Tavily 官方「query 用与 language 相同语言书写」建议针对 language 参数（备选方案），本 Story 选 country 参数是地域加权方案——两者互补不互斥，A/B 报告一并评估
- A/B 实测报告（AC-1）：扩展前后同 query 对比（真实 key 时实测；key 未就绪则以 MockTransport 断言请求体参数构造正确 + 报告留待 key 就绪补）——归档路径 `_bmad-output/planning-artifacts/`（与预筛报告同目录）

### 数据契约六：受益 Skill 声明重分配表

| Skill | 现源 | 新源序 | 治理前提 | 联动面 |
|---|---|---|---|---|
| competitor-analysis | newsapi, uspto, tavily, china-nbs | + `epo-ops` + `sec-edgar`（6 源：newsapi, uspto, epo-ops, sec-edgar, tavily, china-nbs——声明序即断言序） | **无**（4-1c Skill 无「不追加」签收） | 契约库 SSOT 元组（`SKILL_DATA_SOURCES`）+ frontmatter data_sources 块 + §5 映射表（专利布局 uspto+epo-ops 2 源——「未三角化」标注撤除 **2 处**：SKILL.md L178-179 表后段落 + references/triangulation.md:43 + 新增 EDGAR 财报印证行）+ §5 口径段（EPO 欧洲口径 + 合并后仍缺 CNIPA 声明 / EDGAR 美股上市公司口径 + XBRL 模式字段差异）+ §6 标记示例（+2 标记）+ §7 计数（「4 个声明源」2 处 L175/L235 + 维度级 L177「仅 uspto 1 源」→ 2 源 + 未注册行扩列）+ **references/triangulation.md 3 处**（:4/:10「4 个声明源」→ 6 个 + :21 标题「4 源角色分工」→ 6 源） |
| vrio-framework | uspto, tavily | + `epo-ops`（3 源：uspto, epo-ops, tavily） | **无签收前提**（4-1d D2「统一 2 源」为 Story 级决策，epics 4.1f 任务 6 :1127 已明文授权 vrio 增源 + :1129 授权 D2 修订——按授权无条件执行，Dev Agent Record 留痕） | 4-1d 侧契约库 `MIXED_SKILL_DATA_SOURCES` 元组 + 测试基准 `STORY_SSOT`（单侧——4-1c 侧 `SKILL_DATA_SOURCES` 不含 vrio）+ frontmatter + §5 表加行（L142 uspto 与 L143 tavily 之间）+ **L138「双源交叉」表述** + 引言 L98-99 源名二元组增 EPO 提及 + `test_unified_two_source_policy` 豁免改写（D2 修订） |
| disruptive-innovation | uspto, tavily | + `epo-ops`（3 源：uspto, epo-ops, tavily） | **D8 重开签收**（Epic owner 级——4-1c :1180/:1186「不追加第三源」签收重开，Task 0.1 HALT） | 同构 + **「双源」11 处全量改写**（L6/L79/L100/L138/L140/L142/L150/L185/L188/L190/L207 + L188「白名单内 2 源」）+ **references/ 三文件联动**（triangulation.md 方法论表述「双源交叉验证」逐处评估改「专利双库 + 市场单源互证」/workshop_guide.md :11/:19/scoring_anchors.md :3/:14）+ yaml 头注 :349 + sources description :383-385 逐字同步 + D4 表述改「专利双库 + 市场单源，评级互证跨域」 |

**声明重分配断言联动清单（24 项——dev 实施时逐项执行并勾选，Task 6.5 核验对象即本表；标注「无自动断言」的项以 grep 核验 + review 保障——契约库对 references/ 与断言消息文案无内容扫描）：**

> 竞争源数/表述类（competitor）：
> 1. `SKILL_DATA_SOURCES["competitor-analysis"]` 4 元组 → 6 元组（`skill_data_collection_contracts.py:50`）
> 2. competitor frontmatter data_sources +2 块（epo-ops/sec-edgar，required_fields 用契约一定值）
> 3. competitor §5 映射表专利布局行 2 源 + EDGAR 财报印证新行
> 4. competitor §5 口径段（EPO 欧洲/仍缺 CNIPA/EDGAR 美股/XBRL 字段差异 + **412 配额超限降级话术条目**——epics AC-2「超限熔断降级话术」承载：§7 失败处理表 EPO/Comtrade 超限降级引导行）
> 5. competitor §6 标记 +2（`$DATA_SOURCE("epo-ops", ...)` / `$DATA_SOURCE("sec-edgar", ...)`）
> 6. competitor §7 计数 2 处（L175/L235）+ 维度级 L177 + 未注册行扩列
> 7. competitor「未三角化」撤除 2 处（SKILL.md L178-179 + references/triangulation.md:43）
> 8. references/triangulation.md 3 处源数（:4/:10/:21）——**本项与第 7 项的 references 改写无自动断言红——grep 核验 + review 保障**
> 9. yaml 头注 L218「4 源」→「6 源」+ patent_signals description L259（USPTO 口径表述含 EPO 时双写同步 SKILL.md L93）
>
> vrio 类（无签收前提）：
> 10. `MIXED_SKILL_DATA_SOURCES["vrio-framework"]` 2→3 元组（`skill_mixed_data_contracts.py:77`）
> 11. `STORY_SSOT["vrio-framework"]` 2→3（`test_skill_mixed_data_contracts.py:32`——基准侧同步）
> 12. `test_unified_two_source_policy` 豁免表改写（`test_skill_mixed_data_contracts.py:56-60`——「2 源基线 + 4-1f 增补豁免表」，未登记增补即红）
> 13. vrio frontmatter +1 块 + §5 表加行（L142/L143 之间）+ L138「双源交叉」表述 + 引言 L98-99 源名增 EPO
> 14. vrio 集成 `len(metas) == 2` 参数化改 `== len(declared)`（`test_skill_mixed_data.py:236`——10 Skill 全体，vrio 3 源后其余 9 Skill 仍 2）
> 15. vrio 验收场景名「双源」→「三源」（feature L63 + `.py` **三联动位**：@scenario 绑定串 L450 / 函数名 `test_vrio_framework_dual_source_chain` L451 / docstring L452——**本项无自动断言红（步骤声明驱动）——grep 核验 + review 保障**）+ feature L5 总述「（双源交叉）」措辞评估
> 16. `test_arch_skill_mixed_data.py`：`_build_involved_adapters()` 加 `EpoOpsAdapter`（占位凭据）+ import 行 + docstring/注释「6 个」→「7 个」（:55/:79/:113）——`MIXED_INVOLVED_SOURCES` :56 为派生量自动扩，:115 集合断言驱动同步
>
> disruptive 类（D-08 签收前提）：
> 17. `SKILL_DATA_SOURCES["disruptive-innovation"]` 2→3 元组（`skill_data_collection_contracts.py:52`）
> 18. disruptive frontmatter +1 块 + 「双源」11 处 + L188「2 源」全量改写（签收态）
> 19. disruptive references/ 三文件（triangulation/workshop_guide/scoring_anchors）「双源」表述逐处评估改写（签收态——**无自动断言红，grep 核验 + review 保障**）
> 20. yaml 头注 :349「2 源：uspto / tavily，双源交叉验证」→ 3 源 + sources description :383-385 逐字同步（含 SKILL.md L79 双写）
> 21. disruptive 集成 `test_disruptive_innovation_dual_source` 按签收结果（签收→`== 3` + 改名评估；未签收→该项跳过留痕）
>
> 通用类：
> 22. `test_skill_mixed_data_contracts.py:54` 断言消息「不在 8 个注册适配器中」→「11 个」（文案同步，ADAPTER_SSOT 11 源后——纯失败消息文案无红绿语义，grep 核验）
> 23. **4-1c 侧验收场景名「四源」→「六源」**（`test_acceptance_skill_data_collection.feature:38`「competitor-analysis 四源并发采集链路」+ `.py:345` @scenario 绑定串 + `:347` docstring + `:553`「多源三角化」场景 docstring「（competitor-analysis 四源）」——三联动位同步，否则场景绑定断裂）
> 24. **4-1c 侧验收场景名「双源交叉验证」→「三源」（D-08 签收态）**（同文件 `:52`「disruptive-innovation 双源交叉验证采集链路」+ `.py:357` @scenario 串 + `:359` docstring；未签收则维持不动留痕）

### 领域事件（本 Story 不新增事件）

零事件新增：无新采集语义（复用 DataSourceFetched/DataSourceFetchFailed）；`config/event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` 零改动。

### 生产链路（引擎链路零改动声明）

- 五阶段引擎/标记解析/Resolver/缓存键零改动——新适配器经既有注册链即生效（`_build_data_source_adapters` 元组表追加即进 resolver.adapters）
- **唯二生产 .py 行为改动**：① tavily/newsapi fetch 内 CJK 自适应（各 ~10 行）② composition_root 注册段追加（新增代码块，既有零改动）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 中文参数 CJK 自适应与缺口实证（Phase 0）

**Given** tavily/newsapi 适配器现请求体不含任何语言/区域参数
**When** fetch 的 query 含 CJK 字符
**Then** tavily 请求体自动加 `country: "china"`、newsapi params 自动加 `language: "zh"`；query 不含 CJK 时请求体 dict 与改动前逐键一致（零新键）

**验证标准/Validation Criteria:**
- [ ] 两适配器单测：CJK query 断言请求体含新参数（MockTransport capture）/ 非 CJK query 断言请求体 dict 与既有形态逐键一致（回归负例）
- [ ] A/B 实测报告归档 `_bmad-output/planning-artifacts/`（key 就绪时真实对比「比亚迪 战略动态」类 query 质量 + topic/domains 评估项；key 未就绪则断言层验证 + 报告标注待补——**此时 AC-1 记「部分完成」，专职中文源缺口判断 defer 至 key 就绪，owner 知情**）
- [ ] 剩余缺口结论留痕（是否需要专职中文源——结论须标注证据等级（实测/官方文档分析），零实测不得下否定结论；不实施新源）

### AC-2: EPO OPS 适配器（OAuth2 + 配额守卫 + 申请人检索）

**Given** EPO OPS Consumer Key/Secret 已配置（或单测 MockTransport）
**When** 适配器 fetch CQL 检索（`pa=` 申请人 / `ti=` 关键词）
**Then** OAuth2 令牌自动获取/缓存/刷新；4GB/周配额守卫前置（超限抛 EXCEPTION_412 零请求消耗）；结果结构化为 `{"patents": [{"title","applicant","filing_date"}]}`

**验证标准/Validation Criteria:**
- [ ] 单测全绿：令牌流（Basic auth 头/缓存命中不重复请求/401 重取一次/令牌端点失败映射全覆盖——走 helper 后 401/403→101、网络耗尽→411、429→412、超时→302）、检索成功、CQL query 直通断言、配额守卫（注入计数器超限→412 + 消息含已用量）、失败矩阵（201/302/411/412/413/熔断）、config repr 脱敏、`isinstance(adapter, DataSourcePort)`
- [ ] key 就绪时集成实测 `pa="华为"` 返回真实结果（key 未就绪 skip 留痕——**AC-2 完成判定以单测矩阵为准，集成实测登记 Defer 台账追认（owner 知情），不阻塞 AC-2 勾选**——与 AC-1 的「部分完成」降级不同：AC-2 无缺口结论要下）
- [ ] **412 超限降级话术**（epics AC-2「超限熔断降级话术」承载）：受益 Skill §5/§7 失败处理表含 EPO 配额超限（EXCEPTION_412）降级引导条目（随 Task 6 清单 4 口径段一并落）

### AC-3: SEC EDGAR 适配器（UA 规范 + 限速 + 双模式）

**Given** EDGAR 免 key（无条件注册）
**When** fetch 检索模式（关键词/`forms=` 语法）或 XBRL 模式（`xbrl:CIK:概念` 前缀）
**Then** 全部请求带规范 UA 头；限速 ≤8 req/s；检索模式返回 `{"filings": [...]}`、XBRL 模式返回 `{"concept","unit","values"}`

**验证标准/Validation Criteria:**
- [ ] 单测全绿：UA 头断言（capture）、限速令牌桶（并发 10 请求实测节流）、双模式分派、XBRL CIK/概念解析、失败矩阵、结构校验（缺 filings/concept 字段→413）
- [ ] 集成实测（免 key 无条件）：`q="market share" forms=10-K` 真实返回 + `xbrl:CIK0001318605:Revenues` 营收时序（Tesla CIK 实测锚点——预筛已验证端点）

### AC-4: UN Comtrade 适配器（key 可选 + HS 商品级 + 日配额守卫）

**Given** Comtrade 无条件注册（key 可选——preview 端点免 key 兜底，有 key 加 Ocp 头提升配额）
**When** fetch 结构化管道串 query（`reporter=156|cmd=8703|flow=X|period=2024`）
**Then** 适配器解析为 API params（cmd 必填校验→201）；500 次/天日配额守卫前置（超限抛 EXCEPTION_412 零请求消耗）；结果结构化 `{"records": [{"cmd_code","trade_value","period"}]}`

**验证标准/Validation Criteria:**
- [ ] 单测全绿：管道串解析（完整四参/缺省 reporter=156/缺 cmd 抛 201 负例）、Ocp 头断言（有 key 时附加/无 key 不附）、成功/失败矩阵、结构校验、**日配额守卫两分支（放行计数/超限抛 412 含已用次数与重置时间 + 注入初始计数/now_fn 测日窗口重置）**、key 缺失构造成功（preview 模式）
- [ ] 集成实测：`reporter=156|cmd=8703` 中国整车出口真实记录（preview 端点免 key 可测——预筛实测锚点）

### AC-5: required_fields 按源定制联动（ADAPTER_SSOT 四元组重构）

**Given** ADAPTER_SSOT 现为三元组 + EXPECTED_REQUIRED_FIELDS 统一常量
**When** 重构为四元组（8 既有源第四项 `("indicator","value")` 零漂移 + 3 新源定制值）
**Then** 两个契约库 `assert_data_sources_contract` 改按 `ADAPTER_SSOT[ref.name][3]` 查表断言；41 处既有 frontmatter 核验零漂移；两处设计绊线显式改

**验证标准/Validation Criteria:**
- [ ] `test_expected_required_fields_value_locked`（值级基准）与 `test_shared_constants_are_imported_not_copied`（identity）两绊线按重构语义显式更新（R2-F12「变更登记绊线」设计意图）
- [ ] 判别力负例保活：`required_fields=("indicator",)` 漂移副本注入仍红（match 串同步改）
- [ ] 4-1d 库 `__all__` 与 import 链核验（EXPECTED_REQUIRED_FIELDS 常量保留为「legacy 8 源统一值」语义注释更新或移除——Task 0 定稿）
- [ ] 16 Skill × 41 处 frontmatter 联动核验零漂移（grep 计数 + 契约断言）

### AC-6: 受益 Skill 声明重分配（治理分级 + 断言联动 24 项）

**Given** 治理分级已明确（competitor/vrio 无签收前提直接做；disruptive 按 Task 0 HALT 的 D-08 签收结果）
**When** competitor（无前提）+ vrio（epics 授权留痕）+ disruptive（按签收结果）完成声明重分配
**Then** SSOT 元组/frontmatter/§5-§7 表述/§6 标记/口径段/references/yaml 逐字锁死行全量同步；断言联动 24 项清单（数据契约六）全绿

**验证标准/Validation Criteria:**
- [ ] `assert_data_sources_contract`（声明序元组相等）+ `assert_cross_consistency`（每新源 ≥1 标记）+ `assert_sop_maturity`（源数计数表述同步后全绿）
- [ ] `test_triangulation_competitor_four_sources` 改 6 源语义（名/docstring/断言 `>= 3` 升格强断言 `== 6`）；`test_disruptive_innovation_dual_source` 按 D-08 结果（签收→`== 3` + D4 表述同步；未签收→维持 `== 2` 零改动 + 留痕）
- [ ] `test_unified_two_source_policy` 改「2 源基线 + 4-1f 增补豁免表」（vrio——epics 授权，无签收前提）；`MIXED_SKILL_DATA_SOURCES`（契约库）与 `STORY_SSOT`（测试基准）双侧同步
- [ ] 4-1d 集成 `len(metas) == 2` 参数化改 `== len(declared)`（`test_skill_mixed_data.py:236`）；4-1d 验收 vrio 场景名「双源」→「三源」（feature L63 + `.py` 三联动位 L450-452：@scenario 串/函数名/docstring）
- [ ] yaml 头注释源数同步（competitor L218「4 源」→「6 源」/vrio L732「2 源」→「3 源」/disruptive L349「2 源」→「3 源」**——签收态，未签收不动**）+ 逐字锁死 description 双写同步（vrio 侧 + disruptive :383-385 含 SKILL.md L79**——签收态**）
- [ ] 受益 Skill references/ 联动（competitor triangulation.md 3 处源数 + :43 未三角化撤除；disruptive 三文件「双源」表述改写——签收态）
- [ ] **Comtrade 语义匹配度评估留痕**（epics 任务 6 第 3 子项：appeals/kpi-tree 等其余声明 Skill 按语义匹配度评估是否增补——结论与理由留 Dev Agent Record，不强行凑源）+ **D2 修订评审结论留痕**（epics 任务 6 第 4 子项：其余 9 个 4-1d Skill 不放宽的评审结论——产品判断留痕）
- [ ] **D8 留痕**：签收则 4-1c Story D8 条目（:1186 决策项）+ architecture.md :2829 D4 行补记重开（未签收则本 Story Dev Agent Record 登记决策结果）

### AC-7: 注册链全触点与能力边界声明

**Given** 三个新适配器实现完成
**When** 注册进组合根并同步全部触点
**Then** 条件注册（epo-ops）与无条件注册（sec-edgar/comtrade）正确；`_build_data_source_adapters` 元组表 8→11；shutdown 清理列表追加（现 7 项→10 项——china_nbs 复用 CrawlerClientPort 不在列）；`ADAPTER_PORT_SPECS` 契约表 +3；架构测试**两文件**四方一致

**验证标准/Validation Criteria:**
- [ ] `test_arch_skill_data_collection.py`：`_build_adapters` 同步后 `set(adapters.keys()) == set(ADAPTER_SSOT.keys())`（:121，8→11 双向）；**:124/:138 两处三元组解包随 Task 5 四元组化改写**（适配器 get_metadata 与 frontmatter 三方一致测试体内）
- [ ] `test_arch_data_source.py` **四联动点**：`ADAPTER_PORT_NAMES`（:71-77 无条件组）+ EDGAR/comtrade 两端口；`KEYED_ADAPTER_PORT_NAMES`（:81）+ epo-ops；`ADAPTER_IMPL_MODULES`（:85-94 静态映射）+3 条；`test_keyed_adapters_conditional_registration`（:184，参数化元组 :191-195）+ epo-ops——**注意该测试现结构为 `(port_name, env_key)` 单键循环，承载 epo-ops 需扩展为多键合取语义**（参数化改为 `(port_name, env_keys: tuple)` + `all(os.getenv(k) for k in env_keys)`——单凭据态（CONSUMER_KEY 有而 SECRET 无）实际不注册，单键断言会假红）；**该文件为静态表驱动，漏改是静默的（parametrize 不含新端口即不检查），逐点核验**
- [ ] 契约测试 `ADAPTER_PORT_SPECS` +3 条目（env_key：EDGAR 为 None——worldbank 先例；comtrade key 可选语义在 tags/说明标注）
- [ ] 子进程探针：注册态双向（epo-ops 双凭据**成对**有/无——with_key 分支注入 `EPO_OPS_CONSUMER_KEY` + `EPO_OPS_CONSUMER_SECRET` **两个**假常量，单凭据态不注册；EDGAR/comtrade 恒注册——探针 scrub 全部条件注册数据源 env 键确保「无 key」分支纯净）
- [ ] `__init__.py` docstring 8→11；root `.env` 数据源 key 区段补三源样例（L112 `CLOUD_LLM_API_KEY` 附近；**root 无 `.env.example`**——deploy/*/ 下为基础设施服务模板不涉及应用 key，评估结论留 Dev Agent Record 即可，不新建文件）
- [ ] architecture.md §17.3.3：适配器表 +3（含注册形态标注）+ 能力边界声明（IDC/Gartner/Euromonitor 独家份额数据不可得——合同与技术双重壁垒，代理指标组合替代）+ 合规登记（EDGAR UA 规范/Comtrade 署名与配额政策/EPO 配额政策）+ defer 清账（4.1f 承载项完成留痕）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

#### 领域事件 Schema (Domain Events)

- 本 Story 零事件新增（「领域事件」节声明）；Task 0 checklist 该项填「不适用——零事件」

#### 数据模型 (Data Models)

- [ ] 三新源元数据表定稿（上文「数据契约一」为基线——url/api_type/ttl 三值经适配器 get_metadata() 实测校准 + required_fields 为**声明面定值**（契约一直接冻结，不经适配器——get_metadata 不填该字段，见 Task 5 适配器侧定稿），四项冻结进 ADAPTER_SSOT 四元组）
- [ ] EPO 令牌管理设计定稿（进程内缓存结构/过期刷新阈值 60s/401 重取一次上限）
- [ ] EPO 配额守卫设计定稿（周窗口重置点周一 00:00 GMT/字节累计含响应体/Lock 保护/守卫可注入性）
- [ ] EDGAR 双模式分派语法定稿（检索模式缺省 + `xbrl:` 前缀；UA 常量值定稿；required_fields 双模式声明——检索模式为准 + XBRL 差异进 SKILL.md §5）
- [ ] Comtrade 管道串语法定稿（`reporter=156|cmd=8703|flow=X|period=2024`——cmd 必填）+ 日配额守卫阈值定稿（有 key 500 次/天；无 key preview 低配额保守值）
- [ ] CJK 自适应规则定稿（检测函数/两适配器参数映射/非 CJK 零变化回归基线）
- [ ] required_fields 四元组重构方案定稿（EXPECTED_REQUIRED_FIELDS 常量去向：保留 legacy 注释 or 移除——含 4-1d 库 import/`__all__`/绊线三处联动定稿）
- [ ] 受益 Skill 声明序定稿（competitor 6 元组序 / disruptive/vrio 3 元组序——声明序即断言序）
- [ ] KEY_SENSITIVE_SOURCES 登记评估（4-1c 库 :56 现 `("newsapi","tavily")`——epo-ops（consumer key/secret）与 comtrade（subscription key）是否纳入 Key 敏感源断言）——**两态连锁必须知情**：①不登记（**推荐**——循 uspto 先例：同为 keyed 条件注册源且不在登记表；Skill §7「未注册行」扩列已承载降级引导，漏登记仅静默语义漂移无测试红）；②登记则 `test_key_sensitive_skills_count`（`test_skill_mixed_data_contracts.py:63-75` 精确集合断言——vrio（含 epo-ops+tavily）将移入 dual 集合两条断言全红，disruptive 签收态同理）+ `skill_mixed_data_contracts.py:380-384` 失败处理话术断言连锁红——**须同步扩入断言联动清单**，Task 0 决策时二选一并留痕

#### 统一端口定义注册与管理 (Port Contract)

- 本 Story 零端口新增/修改（「端口契约」节声明）；Task 0 checklist 填「不适用——零端口（R1/R2 既有零触碰）」+ 既有 `DataSourcePort` 协议测试零回归确认
- 端口契约测试：`tests/contracts/test_port_contract_data_source.py` 的 `ADAPTER_PORT_SPECS` 表 +3 条目（本 Story 唯一契约测试改动）

#### 领域异常契约 (Domain Exception Contract)

- 本 Story 零新增异常（「领域异常契约」节复用表）；Task 0 checklist 逐项填「不适用——零新增」+ 复用表确认（尤其配额守卫→412 与 OAuth2 401→101 两个新语义映射的既有归属核实）

#### API 契约 (API Contract)

- 不适用——零 API 变更（基础设施层 Story）

#### 六边形架构约束（必须遵守）

- 按 template.md 四层定义与依赖方向矩阵执行；本 Story src/ 生产改动仅限 infrastructure（适配器/config）+ composition_root（注册追加）——其余生产 .py 一律禁止触碰（唯二行为改动：tavily/newsapi fetch 的 CJK 自适应——属 infrastructure 适配器内）；若实施中发现必须改 domain/application 生产代码，先停下核对本文档「端口与数据契约」节

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 编写 `tests/acceptance/test_acceptance_data_source_expansion.feature`（zh-CN，按 AC 分节：三新源 Happy 各场景 + Edge：key 缺失条件注册跳过（epo-ops）/配额超限 412（EPO 周/Comtrade 日）/令牌失效重取/CJK 自适应双态/EDGAR 与 Comtrade 免 key 直连——**范本 `test_acceptance_data_source.feature`**（4.1b 验收，`context` dict + `_FakeDataSourceAdapter` 仅限端口替身 + 真实 Resolver/Redis + xdist_group））
- [ ] 编写 BDD 步骤实现骨架（新源场景用真实新适配器实例 + MockTransport 注入——适配器构造支持 client 注入是既有模式；key 就绪场景动态 skip）——**三个新适配器模块一律步骤函数内延迟 import**（先例 `test_acceptance_data_source.py:560-561` newsapi 形态）：顶部 import 会使整文件收集期失败（collect error），阻塞 Task 1-3 期间同文件 CJK 场景运行且与逐 Task 全绿矛盾；延迟 import 使红收敛到新源场景本身
- [ ] 运行确认失败（🔴 红阶段验证——新源场景步骤内 `ModuleNotFoundError` 为合法红；CJK 场景此时应可运行（改前行为绿）——收集无错）

**Task 0 完成标志：**
- [ ] 上述规范项全部定稿（含 D-08 D8 重开 HALT 决策执行留痕）
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）

---

### TDD 循环约束（适用于每个 Task）

> 每个 Task 依次执行：🔴 红（失败测试）→ 🟢 绿（最小实现）→ 🔄 重构（ruff + mypy + pytest 全绿）。禁止先码后测/跳过红阶段。

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| TDD 单元测试 | epo-ops 适配器 | 令牌流/配额守卫/检索/失败矩阵 | `test_epo_ops_adapter.py` | Task 2 |
| TDD 单元测试 | sec-edgar 适配器 | UA/限速/双模式/失败矩阵 | `test_sec_edgar_adapter.py` | Task 3 |
| TDD 单元测试 | comtrade 适配器 | 管道串解析/Ocp 头/失败矩阵 | `test_comtrade_adapter.py` | Task 4 |
| TDD 单元测试 | tavily/newsapi CJK | 自适应双态/回归基线 | 既有 `test_tavily_adapter.py`/`test_newsapi_adapter.py` 扩展 | Task 1 |
| TDD 单元测试 | 契约库重构 | 四元组查表断言/绊线/负例 | `test_skill_mixed_data_contracts.py` 扩展 | Task 5 |
| TDD 契约测试 | 端口注册 | ADAPTER_PORT_SPECS +3 | `tests/contracts/test_port_contract_data_source.py` | Task 7 |
| SDD 架构验证 | 适配器注册链（4-1c 侧） | 三方一致/元数据对齐 + 三元组解包四元组化 | `test_arch_skill_data_collection.py` 扩展（:121/:124/:138） | Task 7 |
| SDD 架构验证 | 适配器注册链（静态表四联动点） | 无条件组/keyed 组/impl 映射/条件注册断言 | `test_arch_data_source.py` 扩展（:71/:81/:85/:184） | Task 7 |
| SDD 架构验证 | 混合数据三方一致（4-1d 侧） | involved 源集合/适配器实例化 + 三元组解包四元组化 | `test_arch_skill_mixed_data.py` 扩展（:115/:118/:132） | Task 5/6 |
| 集成测试 | 真实端点 | 三源真实连通（key 门控 skip） | `tests/integration/external_services/data_sources/test_new_sources_integration.py` | Task 7 |
| TDD 验收测试 | Gherkin/BDD | AC 全场景 | `test_acceptance_data_source_expansion.feature`/`.py` | Task 0/8 |

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] 整体 ≥80% 不降；**基础设施层 ≥75%**（本 Story 主战场——测量方式：`poetry run pytest tests/unit/infrastructure --cov=src/infrastructure --cov-report=term`（pyproject addopts 仅 `--cov=src` 全局报告无分层门禁，分层值以本命令单独核验；新适配器语句级覆盖由单测矩阵保证——测试分类表五文件全覆盖令牌流/守卫/双模式/解析/失败矩阵））
- [ ] 关键路径 100%：令牌流三分支（获取/缓存命中/401 重取）+ 配额守卫两分支（放行/超限）+ CJK 两态 + 双模式分派

#### 代码质量门禁

- [ ] ruff / mypy / 无 P0-P1 / pre-commit 全过；`pytest -n 8` 连续 5 次无随机失败

#### 测试隔离约束

- 详见「测试隔离约束」节（MockTransport 零外网/守卫计数注入/key 动态 skip/子进程探针）

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 中文参数 CJK 自适应 + 缺口实证 | Task 1 | 1.1-1.4 | `test_tavily_adapter.py`/`test_newsapi_adapter.py` 扩展 + A/B 报告 |
| AC-2 | EPO OPS 适配器 | Task 2 | 2.1-2.5 | `test_epo_ops_adapter.py` |
| AC-3 | SEC EDGAR 适配器 | Task 3 | 3.1-3.5 | `test_sec_edgar_adapter.py` |
| AC-4 | UN Comtrade 适配器 | Task 4 | 4.1-4.4 | `test_comtrade_adapter.py` |
| AC-5 | required_fields 四元组重构 | Task 5 | 5.1-5.5 | `test_skill_mixed_data_contracts.py` 扩展 |
| AC-6 | 受益 Skill 声明重分配 | Task 6 | 6.1-6.8 | 三 Skill 单测 + 集成/验收联动 24 项 |
| AC-7 | 注册链全触点 + 能力边界 | Task 7 | 7.1-7.6 | `test_port_contract_data_source.py` + 架构测试三文件（`test_arch_skill_data_collection.py`/`test_arch_data_source.py`/`test_arch_skill_mixed_data.py`）扩展 |
| 全 AC | 收尾验收 + 文档同步 | Task 8 | 8.1-8.5 | BDD 全场景 + architecture.md 同步 |

---

## ⚠️ 风险与缓解策略（Risk Register）

| # | 风险 | 概率 | 影响 | 缓解措施 | 触发 Task |
|---|------|------|------|---------|----------|
| **R1** | D8 重开未获签收（disruptive 增源受阻） | 中 | 中 | Task 0 HALT 显式决策；未签收路径设计完备（competitor/vrio 按 epics 授权独行 + 适配器照常交付 + AC-6 disruptive 项按结果记录）；断言联动清单标注两态分支；HALT 等待期不阻塞 Task 0.2-0.6/1-5/6 循环 A-B | Task 0/6 |
| **R2** | EPO OAuth2 令牌流复杂度（缓存/刷新/401 重取三分支） | 中 | 中 | 令牌管理内聚为适配器私有类 `_EpoTokenManager`（构造注入 clock 便于测试；`retry_*` 参数透传防单测退避拖秒）；单测三分支强制；业务 401 重取路径显式（异常契约表——捕获 101 按 `context.status_code` 判别，禁止裸 client 绕行 helper）；不抽共享基类（YAGNI） | Task 2 |
| **R3** | 配额守卫进程内计数在测试并行下竞态 | 低 | 中 | `asyncio.Lock` 类变量；守卫计数构造可注入 + `now_fn` 时钟注入（周/日窗口重置可测）；单测串行验证 + 并发测试用 `asyncio.gather` 真并发断言 | Task 2/4 |
| **R4** | required_fields 重构破坏 41 处既有断言链 | 中 | 高 | 四元组扩展向后兼容设计（8 既有源值零漂移）；绊线显式改 + 判别力负例保活；41 处 grep 计数核验；**三元组解包 6 处全量枚举**（两契约库 + 两架构测试文件）；全量回归门禁 | Task 5 |
| **R5** | 声明重分配断言联动面广（24 项 + references/ 联动）漏改 | 中 | 高 | 数据契约六「断言联动 24 项清单」作为 Task 6 的执行 checklist 逐项勾选；「双源」/源数 grep 全量出现位驱动（SKILL.md + references/ + templates/ + yaml）；每改一处跑对应单测；集成/架构/验收三层回归 | Task 6 |
| **R6** | EDGAR 双模式分派语法被 LLM 误用（xbrl: 前缀拼写） | 低 | 低 | query 规范写入 SKILL.md §5/§6（结构化语法非自然语言）；非法前缀→201 输入校验负例 | Task 3/6 |
| **R7** | key 申请周期阻塞集成实测 | 中 | 低 | 单测全 MockTransport 不依赖 key；集成/验收动态 skip 留痕；EDGAR/comtrade 免 key 可全程实测；**key 到位后人工补跑锚点**：AC-2 EPO 集成 + AC-1 A/B 报告实测面——登记 Defer 台账并在 Story 留痕（key 是外部申请，CI 无 secret 恒 skip） | Task 7/8 |
| **R8** | 中文 A/B 实测被 key 阻塞（newsapi 商用限制） | 中 | 低 | AC-1 验证标准两态设计（断言层验证先行 + 报告标注待补——AC-1 记部分完成，缺口判断 defer 且 owner 知情）；CJK 规则的正确性不依赖实测 | Task 1 |
| **R9** | Comtrade preview 端点仅近期样本子集（非全量历史） | 中 | 低 | 预筛实测 195 条真实记录可用；集成实测锚点用近期 period；SKILL.md §5 口径声明数据窗口限制；正式 key 通道评估留 Task 6.8 | Task 4/6 |
| **R10** | CJK 检测对中英混合 query 的质量反效果（`country=china` 地域收窄可能漏英文权威源） | 中 | 中 | A/B 实测报告必须含混合语料对比组；实测证明反效果则回退方案（仅 tavily 加 `language=zh-cn` 替代 country——两参数互补，数据契约五已登记）；CJK 规则单点可回退（~10 行改动） | Task 1 |
| **R11** | EPO 仅 EP 申请口径——对中国企业全球专利布局代表性有限 | 高 | 中 | competitor §5 口径段已有「仍缺 CNIPA」声明；disruptive/vrio 增源后同款口径声明跟进（Phase 2 BigQuery 补 CN 全景——4.1g）；引用侧双库（uspto 美国口径 + epo 欧洲口径）显式标注 | Task 6 |
| **R12** | Task 5→7 架构测试红窗口在 main 直接开发下破坏 CI（中间态提交触发流水线红） | 中 | 中 | 红窗口分两类：**解包红**（`url, api_type, ttl = SSOT[...]` 三元组 vs 四元组 ValueError）——Task 5 提交时将 6 处解包一并在本 Task 改写即消（不依赖适配器注册）；**set 断言红**（`set(adapters.keys()) == set(ADAPTER_SSOT.keys())` 8≠11）——依赖 Task 7 `_build_adapters` 加 3 适配器，无法前置。提交策略：Task 5 与 Task 7 的架构测试同步**同批提交**（Task 5 只提交契约库与解包改写、Task 7 提交注册与 set 断言收口——两次提交间 CI 红在 commit message 标注「预期中间态：Task 7 收口」；或两 Task 合并单次提交）；4-1d「一次性预调整」先例（彼 Story D8 决策，非本 Story 治理 D8——一词两义注意区分） | Task 5/7 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ TDD 循环内化原则：每个 Task 独立完成红→绿→重构；每个 Subtask 组按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置 + D8 治理决策）

**关联 AC:** 全部（AC-1 ~ AC-7 的规范输入）

> 目的：进入实现前钉死三源元数据/行为契约/重构方案/声明序 + 执行 D8 重开 HALT 决策。

- [ ] Subtask 0.1: **D-08 治理决策执行（HALT）**——向 Epic owner 显式请求 D8 重开签收（disruptive「不追加第三源」owner 级签收重开——请求时引用 epics 4.1f 任务 6 :1127 授权加速签认；vrio 增源 + D2 修订按 epics 授权无签收前提，同点**知会**留痕）；签收结果与两态执行路径留痕 Dev Agent Record；HALT 等待期不阻塞 Task 0.2-0.6 与 Task 1-5/6 循环 A-B
- [ ] Subtask 0.2: 三源元数据表定稿（数据契约一为基线——url 经实测校准；ttl/required_fields 冻结）；声明序定稿（competitor 6 元组/disruptive/vrio 3 元组）
- [ ] Subtask 0.3: 行为契约细化定稿（EPO 令牌管理/配额守卫、**EpoOpsAdapter 构造器 config 语义（config 必填、空凭据即抛 101——无 uspto 式 `config or USPTOConfig()` 缺省回退：空凭据回退将推迟到首个请求才炸，构造期即炸更符合 fail-fast）**、EDGAR 双模式语法与 UA 常量、Comtrade 管道串语法与**日配额阈值 + `ComtradeConfig.from_env` key 缺失语义（缺省空串 = 无 key 走 preview 裸模式——newsapi `api_key: str = field(default="", repr=False)` 先例，但构造器不抛）**、CJK 规则）+ required_fields 重构方案（含 EXPECTED_REQUIRED_FIELDS 常量去向三处联动定稿）
- [ ] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_data_source_expansion.feature`（zh-CN 按 AC 分节——三源 Happy + Edge：key 缺失跳过/配额 412/令牌失效/CJK 双态/EDGAR 直连）
- [ ] Subtask 0.5: 编写 BDD 步骤实现骨架（`test_acceptance_data_source_expansion.py`——context dict 模式 + 真实适配器实例 MockTransport 注入 + key 动态 skip + xdist_group）
- [ ] Subtask 0.6: 运行验收测试确认失败（🔴 红阶段——ModuleNotFoundError 合法红）

**完成标准/Definition of Done:**
- [ ] 规范项全部定稿 + D-08 决策留痕
- [ ] Gherkin 红阶段确认

---

### Task 1: 中文参数 CJK 自适应（Phase 0）

**关联 AC:** AC-1

#### TDD 循环 [A]：tavily/newsapi CJK 自适应

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 既有 `test_tavily_adapter.py`/`test_newsapi_adapter.py` 扩展：CJK query 断言请求体/params 含 `country: "china"` / `language: "zh"`（capture handler）；**非 CJK query 回归基线断言（请求体与既有形态逐字一致）** |
| 🟢 绿 | 两适配器 fetch 加 CJK 检测（`_contains_cjk(query)` 私有函数）与条件参数注入（各 ~10 行） |
| 🔄 重构 | CJK 检测函数复用（两适配器各自实现 or 提 `_http_helpers` 共享——单行函数倾向各自私有，Task 内裁定）；ruff/mypy |

- [ ] Subtask 1.1: 🔴 红 — CJK 双态 + 回归基线测试（非 CJK 断言请求体 dict 逐键一致——基准即现状三键/四键手写期望，`json.loads(request.content)` capture 先例 `test_tavily_adapter.py:47-48`）
- [ ] Subtask 1.2: 🟢 绿 — 两适配器自适应实现
- [ ] Subtask 1.3: 🔄 重构 — 提炼与全量回归（**受影响声明 Skill = 13 个**（newsapi 8 ∪ tavily 10 去重）——appeals-analysis/change-management/competitor-analysis/disruptive-innovation/ge-mckinsey-matrix/kpi-tree/pestel-analysis/porters-five-forces/scenario-planning/swot-tows/value-chain-analysis/value-curve-analysis/vrio-framework 的声明与采集测试零回归）
- [ ] Subtask 1.4: A/B 实测报告（key 就绪真实对比 / 未就绪断言层验证 + 标注待补——**未就绪态 AC-1 记「部分完成」，缺口判断 defer 至 key 就绪（owner 知情），不得凭零实测下「无需专职中文源」结论**）+ 剩余缺口结论留痕（结论须标注证据等级：实测/官方文档覆盖面分析）+ topic/domains 参数评估项（epics AC-1 偏差登记——见数据契约五）

**完成标准/Definition of Done:**
- [ ] CJK 双态测试绿 + 既有回归零破坏 + 报告归档

---

### Task 2: EPO OPS 适配器（含 OAuth2 令牌管理与配额守卫）

**关联 AC:** AC-2

#### TDD 循环 [A]：令牌管理器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `test_epo_ops_adapter.py`：`_EpoTokenManager` 三分支（首次获取 Basic auth 头断言/缓存命中不重复请求/401 失效重取一次——业务请求 401 重取按异常契约表路径：捕获 101 + `context.status_code==401` 判别）+ 令牌端点 401→101 + 网络耗尽→411 |
| 🟢 绿 | 令牌管理私有类（进程内缓存 + 过期提前 60s 刷新 + 构造注入 clock + **`retry_*` 参数经适配器透传**——单测注入 `retry_min_wait=0.01` 同样作用于令牌端点） |

#### TDD 循环 [B]：配额守卫

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 守卫两分支（放行累计/超限抛 412 含已用量与重置时间）+ 周窗口重置（**注入 `now_fn`** 跨周一 00:00 GMT——契约二设计）+ 并发安全（gather 竞态） |
| 🟢 绿 | 周窗口字节累计（`asyncio.Lock` 类变量 + 可注入初始值 + `now_fn` 时钟注入） |

#### TDD 循环 [C]：适配器主体

| 阶段 | 动作 |
|------|------|
| 🔴 红 | fetch 成功（CQL 直通 + Bearer 头 + `Accept: application/json` + Range 分页）+ 结构校验（缺 patents→413）+ get_metadata（对齐 SSOT 条目的 name/url/api_type/ttl 四值——**required_fields 不在适配器侧断言，见 Task 5 适配器侧解包定稿**）+ 失败矩阵（201/302/411/412/413/熔断）+ key 缺失构造→101 + repr 脱敏 + isinstance(DataSourcePort) |
| 🟢 绿 | 适配器实现（复用 `request_json_with_resilience`——令牌获取亦走 resilience） |
| 🔄 重构 | `src/infrastructure/config/epo_ops.py`（**5 变量**：API_URL/TIMEOUT/TTL_SECONDS + consumer_key/consumer_secret 双凭据字段——命名规范节口径）+ docstring 中文注释 + ruff/mypy |

- [ ] Subtask 2.1: 🔴 红 — 令牌管理三分支测试
- [ ] Subtask 2.2: 🟢 绿 — `_EpoTokenManager` 实现
- [ ] Subtask 2.3: 🔴🟢 — 配额守卫（守卫测试→实现）
- [ ] Subtask 2.4: 🔴🟢 — 适配器主体（全矩阵测试→实现 + config）
- [ ] Subtask 2.5: 🔄 重构 — 全绿 + key 就绪集成实测（`pa="华为"`）

**完成标准/Definition of Done:**
- [ ] 三循环全绿 + 关键路径 100%（令牌三分支/守卫两分支）
- [ ] config 5 变量（API_URL/TIMEOUT/TTL_SECONDS + 双凭据）+ 条件注册预备（双凭据门）

---

### Task 3: SEC EDGAR 适配器（UA + 限速 + 双模式）

**关联 AC:** AC-3

#### TDD 循环 [A]：限速令牌桶 + UA 规范

| 阶段 | 动作 |
|------|------|
| 🔴 红 | UA 头常量断言（全部请求）+ 令牌桶节流（并发 10 请求**断言仅下界**：elapsed ≥ 节流理论耗时（8 rps × 10 请求 ≈ 1.125s 下取 1.0s）证明确实节流——上界不设紧凑值防 CI 慢机 flaky；refill 逻辑另做可注入 clock 的纯函数单测，真实时钟测试仅此一条） |
| 🟢 绿 | 进程内令牌桶（Semaphore + 时间窗）+ UA 常量 |

#### TDD 循环 [B]：双模式 fetch

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 检索模式（缺省——efts search-index + forms 解析）/ XBRL 模式（`xbrl:CIK:概念` 前缀分派 + companyconcept/frames 两形态）/ 非法前缀→201（query 语法输入校验）/ 结构校验双模式（缺 filings/concept→413——响应侧）+ 失败矩阵 |
| 🟢 绿 | 适配器实现（绝对 URL 拼接——efts/data 两 base） |
| 🔄 重构 | config（无 API_KEY——三键 API_URL/TIMEOUT/TTL_SECONDS）+ ruff/mypy |

- [ ] Subtask 3.1: 🔴 红 — UA + 令牌桶测试
- [ ] Subtask 3.2: 🟢 绿 — 节流与 UA 实现
- [ ] Subtask 3.3: 🔴🟢 — 双模式 fetch（测试→实现）
- [ ] Subtask 3.4: 🔄 重构 — 全绿
- [ ] Subtask 3.5: 集成实测（免 key 无条件——`q="market share" forms=10-K` + `xbrl:CIK0001318605:Revenues` Tesla 锚点）

**完成标准/Definition of Done:**
- [ ] 全绿 + 免 key 真实端点实测通过

---

### Task 4: UN Comtrade 适配器

**关联 AC:** AC-4

#### TDD 循环 [A]：管道串解析 + 日配额守卫 + 适配器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 管道串解析（完整四参/缺省 reporter=156/缺 cmd→201 负例）+ Ocp 头断言（有 key 附加/无 key 不附）+ 成功（records 结构化）+ 结构校验 + 失败矩阵 + **key 缺失构造成功**（无条件注册 + preview 兜底——D5 定稿） |
| 🟢 绿 | 适配器实现 + config 四键 |
| 🔄 重构 | ruff/mypy |

#### TDD 循环 [B]：日配额守卫（epics AC-4 承载）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 守卫两分支（放行计数累计/超限抛 412 含已用次数与重置时间）+ 日窗口重置（注入 `now_fn` 跨 UTC 00:00）+ 并发安全（gather 竞态）——守卫计数构造可注入初始值 |
| 🟢 绿 | 进程内日窗口请求计数（`asyncio.Lock` 类变量 + `now_fn` 注入——模式复用 EPO 周窗口守卫，Task 2 已建） |

- [ ] Subtask 4.1: 🔴 红 — 解析与矩阵测试（循环 A）
- [ ] Subtask 4.2: 🟢 绿 — 适配器实现（循环 A）
- [ ] Subtask 4.3: 🔴🟢 — 日配额守卫（循环 B：测试→实现）
- [ ] Subtask 4.4: 🔄 重构 — 全绿
- [ ] Subtask 4.5: 集成实测（preview 免 key——`reporter=156|cmd=8703` 中国整车出口）

**完成标准/Definition of Done:**
- [ ] 全绿 + preview 端点真实记录实测 + 日配额守卫两分支覆盖

---

### Task 5: required_fields 按源定制联动（契约库重构）

**关联 AC:** AC-5

#### TDD 循环 [A]：ADAPTER_SSOT 四元组 + 断言查表

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `test_skill_mixed_data_contracts.py`：四元组结构断言（11 源 × 4 项）+ 查表断言改写预演（按 `ADAPTER_SSOT[ref.name][3]`）+ 绊线两处新语义测试（`test_expected_required_fields_value_locked` 改为「8 既有源值锁定 + 3 新源定制值锁定」or 常量移除后的替代锚点——Task 0 定稿方案的红测试） |
| 🟢 绿 | `skill_data_collection_contracts.py`：ADAPTER_SSOT 扩四元组（+3 新源条目——依赖 Task 2/3/4 的 get_metadata 实测值）+ `assert_data_sources_contract` 查表化（:109 解包 + :114-116 统一比对两处改写）；**4-1d 库经 import 自动继承四元组变更（R2-F3 单一来源——非复制体，禁止复制）**，仅需改本库自身断言（`skill_mixed_data_contracts.py:339` 解包 + `:344` required_fields 比对查表化） |
| 🔄 重构 | 判别力负例保活（漂移副本 match 串同步）+ **三元组解包 6 处全量改写**（两契约库 :109/:339 + `test_arch_skill_data_collection.py:124/:138` + `test_arch_skill_mixed_data.py:118/:132`——后者两处在 Task 6 vrio 增源后另有 involved 适配器联动，见断言联动清单 16）——**适配器侧解包定稿（2 处 :124/:118）**：四元组解包后第 4 项以 `_` 弃用并注释「required_fields 属声明面，由 frontmatter↔SSOT 双方断言承载（既有 8 适配器 get_metadata 均不填该字段——`DataSourceRef` docstring :84 声明性元数据归声明面的既有架构语义；若适配器侧断言第 4 项则 8 既有源 `()` ≠ `("indicator","value")` 必红且需扩 8 个生产文件改动面——显式排除）**；frontmatter 侧解包（:138/:132/:109/:339）第 4 项入断言（查表比对）+ 注册侧 `_build_adapters` 同步依赖 Task 7——**本 Task 先行改契约侧，注册侧 Task 7 收口**；两 Task 间架构测试暂红属预期中间态，Task 7 全绿 |

- [ ] Subtask 5.1: 🔴 红 — 四元组 + 查表 + 绊线新语义测试
- [ ] Subtask 5.2: 🟢 绿 — 契约库两版重构（4-1c 改值 + 4-1d 断言侧）
- [ ] Subtask 5.3: 🔄 重构 — 负例保活 + 41 处既有 frontmatter grep 计数核验零漂移
- [ ] Subtask 5.4: 全量 skills 测试回归（既有 16 Skill 断言零破坏）
- [ ] Subtask 5.5: EXPECTED_REQUIRED_FIELDS 常量去向落地（Task 0 方案——含 4-1d 库 import 名单与 `__all__` 联动）

**完成标准/Definition of Done:**
- [ ] 四元组重构全绿（6 处解包改写本 Task 完成；注册侧 set 断言除外——Task 7 收口，见 R12 提交策略）+ 41 处零漂移实证

---

### Task 6: 受益 Skill 声明重分配（断言联动 24 项）

**关联 AC:** AC-6

> 前提：Task 0.1 D-08 决策结果（仅门控 disruptive）；契约侧 SSOT 元组在 Task 5 已四元组化——本 Task 改声明元组（源序）并同步全部内容面。

#### TDD 循环 [A]：competitor-analysis（4→6 源，无治理前提）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `test_competitor_analysis_data_collection.py` 全红（SSOT 元组 6 化后 frontmatter 仍 4 源——name 集合断言红） |
| 🟢 绿 | SKILL.md：frontmatter data_sources +2 块（epo-ops/sec-edgar 定制 required_fields）/ §5 映射表（专利布局 2 源 + 「未三角化」标注撤除 2 处 + EDGAR 财报印证新行）/ §5 口径段（EPO 欧洲 + 合并仍缺 CNIPA / EDGAR 美股口径 + XBRL 字段差异）/ §6 标记 +2 / §7 计数 2 处 + 维度级 + 未注册行扩列 / **references/triangulation.md 3 处源数 + :43 撤除** |
| 🔄 重构 | 契约库 SSOT 元组 6 化 + 集成测试改 6 源语义（`test_triangulation_competitor_four_sources` 改名/断言 `>= 3` 升格 `== 6`） |

#### TDD 循环 [B]：vrio-framework（2→3 源，epics 授权——无签收前提）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | vrio 单测红（`MIXED_SKILL_DATA_SOURCES`/`STORY_SSOT` 3 化后 frontmatter 仍 2 源） |
| 🟢 绿 | SKILL.md：frontmatter +1 块 / §5 表加行（L142-143 之间）/ L138「双源交叉」表述 / 引言 L98-99 源名增 EPO / query 规范条目（CQL `pa=` 语法） |
| 🔄 重构 | D2 断言改写（`test_unified_two_source_policy` 豁免表 + `len(metas)==2` 参数化改 `== len(declared)` + 4-1d feature 场景名「双源」→「三源」+ `.py` 三联动位 L450-452）+ `test_arch_skill_mixed_data.py` involved 联动（断言联动清单 16）+ epics 授权留痕（Dev Agent Record） |

#### TDD 循环 [C]：disruptive-innovation（2→3 源，D-08 签收前提——未签收则跳过并留痕）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | disruptive 单测红（签收态） |
| 🟢 绿 | SKILL.md：「双源」11 处 + L188「2 源」全量改写 + yaml 逐字锁死行双写（:383-385 + SKILL.md L79）+ D4 表述改「专利双库 + 市场单源，评级互证跨域」+ **references/ 三文件「双源」表述评估改写** |
| 🔄 重构 | D8 留痕（4-1c Story D8 条目 :1186 + architecture.md :2829 D4 行补记——签收态） |

- [ ] Subtask 6.1: 🔴🟢 — competitor 声明与内容全量（循环 A）
- [ ] Subtask 6.2: competitor 集成断言 6 源化
- [ ] Subtask 6.3: 🔴🟢 — vrio（循环 B——无签收前提，epics 授权留痕）
- [ ] Subtask 6.4: 🔴🟢 — disruptive（循环 C——D-08 签收态；未签收跳过留痕，`test_disruptive_innovation_dual_source` 维持 `== 2` 零改动）
- [ ] Subtask 6.5: 断言联动 24 项清单逐项勾选核验（**本 Story「数据契约六」内嵌清单**——非外部调研文档）
- [ ] Subtask 6.6: yaml 头注释源数（L218/L732 恒改；L349 **disruptive 项签收态**）+ 逐字锁死 description 双写同步（vrio 恒改；disruptive :383-385 签收态）
- [ ] Subtask 6.7: 三 Skill 全链路（声明/标记/口径/行数 ≤500）全绿
- [ ] Subtask 6.8: **Comtrade 语义匹配度评估留痕**（epics 任务 6 第 3 子项——appeals/kpi-tree 等其余 13 个声明 Skill 按 Comtrade 商品级语义匹配度逐个评估，增补/不增补结论与理由留 Dev Agent Record，不强行凑源）+ **D2 修订评审结论留痕**（epics 任务 6 第 4 子项——其余 9 个 4-1d Skill 不放宽至 3 源的评审结论留痕）
- [ ] Subtask 6.9: 全量回归（4-1c/4-1d/4-1e 三层测试零破坏）

**完成标准/Definition of Done:**
- [ ] 声明重分配全绿 + 24 项清单全勾 + D-08 结果留痕 + 两个 epics 评估留痕

---

### Task 7: 注册链全触点 + 集成实测（SDD 架构约束验证）

**关联 AC:** AC-7

- [ ] Subtask 7.1: composition_root 三注册块（epo-ops 条件注册——EDGAR/comtrade 无条件 A 组范式，与 worldbank 同构）+ `_build_data_source_adapters` 元组表 8→11 + shutdown 清理列表 +3（自持 httpx——现 7 项→10 项）
- [ ] Subtask 7.2: `tests/contracts/test_port_contract_data_source.py` 的 `ADAPTER_PORT_SPECS` +3（env_key：EDGAR None；comtrade key 可选语义标注）+ 探针脚本 env 注入行
- [ ] Subtask 7.3: **架构测试两文件同步**：① `test_arch_skill_data_collection.py`——`_build_adapters` 同步（import + 实例化 + dict 11 键——EDGAR 免 key 直接实例化/EPO+Comtrade 占位 key `NewsAPIConfig(api_key="arch-test-placeholder")` 先例）+ :124/:138 三元组解包四元组化 → `set(keys) == set(ADAPTER_SSOT.keys())`（:121）全绿（Task 5 中间态收口）；② **`test_arch_data_source.py` 四联动点**——`ADAPTER_PORT_NAMES`（:71-77）+ EDGAR/comtrade、`KEYED_ADAPTER_PORT_NAMES`（:81）+ epo-ops、`ADAPTER_IMPL_MODULES`（:85-94）+3 条映射、`test_keyed_adapters_conditional_registration`（:184/:191-195）+ epo-ops（参数化结构扩展为多键合取——epo-ops 双凭据 `("EPO_OPS_CONSUMER_KEY", "EPO_OPS_CONSUMER_SECRET")` 成对判定，见 AC-7；该文件静态表驱动，漏改静默——逐点核验）
- [ ] Subtask 7.4: 集成实测文件 `tests/integration/external_services/data_sources/test_new_sources_integration.py`（三源真实端点——EDGAR/comtrade 无条件可测/EPO key 动态 skip；TestTenant 前缀；目录与既有 `tests/integration/external_services/` 结构对齐）
- [ ] Subtask 7.5: `__init__.py` docstring 8→11 + root `.env` 数据源 key 区段补样例（L112 `CLOUD_LLM_API_KEY` 附近；root 无 `.env.example`，deploy/*/ 模板为基础设施服务不涉及应用 key——评估结论留 Dev Agent Record，不新建文件）
- [ ] Subtask 7.6: 子进程探针注册态（epo-ops key 有/无双向；EDGAR/comtrade 恒注册单态验证；without 分支 scrub 全部条件注册数据源 env 键——含既有 TAVILY/NEWSAPI/USPTO——先例 `test_acceptance_data_source.py:606-637`）

**完成标准/Definition of Done:**
- [ ] 注册链全触点落地 + 三方一致全绿 + 真实端点实测（可测面）

---

### Task 8: 开发结束验收测试 + 文档同步

**关联 AC:** 全部收尾

| 阶段 | 动作 |
|------|------|
| 🔴 红 | feature 收尾场景（src + tests 四目录完成清单逐项确认） |
| 🟢 绿 | BDD 全场景通过（含 4.1b 既有验收零回归）+ 三层全量回归 |
| 🔄 重构 | 场景命名收敛 |

- [ ] Subtask 8.1: 收尾场景 + 完成清单勾选
- [ ] Subtask 8.2: architecture.md §17.3.3 同步（适配器表 +3/能力边界声明/合规登记/defer 清账——AC-7 验证标准全项）+ §17.3 状态表 4.1f 行（L2658-2679 列表项格式仿 4.1e 行）+ **版本号 8.9.0 三处同步**（:17 头部「版本：」+ :3600 修订历史表 + :3613 尾部版本表）
- [ ] Subtask 8.3: 异常设计文档零新增声明（§3.3.2 复用表追加——412/101 新语义映射归属既有）
- [ ] Subtask 8.4: 全量 `pytest -n 8` + ruff + mypy + pre-commit + 连续 5 次
- [ ] Subtask 8.5: A/B 报告与 D-08 决策记录归档核验 + **两个 epics 评估留痕核验**（Task 6.8 Comtrade 语义匹配度评估结论 + D2 修订评审结论——均在 Dev Agent Record）

**完成标准/Definition of Done:**
- [ ] 全部完成清单验证确认 + Story 可进入 review

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) + 预筛报告 + 三视角代码调研（2026-09-30）

- **架构模式:** 六边形（Ports & Adapters）；本 Story = R3 基础设施层新增实现（R1/R2 零改动、R4 无涉）
- **设计约束:** 新适配器必须复用 `_http_helpers.request_json_with_resilience`（错误映射集中——禁止自写 411/412/413 映射）；`parse_int_param` 参数校验前置；httpx 禁 `follow_redirects`（跨域转发 Key 头安全约束）
- **技术栈:** Python 3.11+ / httpx（AsyncClient + MockTransport 测试）/ tenacity（resilience helper 内聚）
- **接口治理:** 零端口变更——新适配器经组合根既有聚合链注入（`_build_data_source_adapters` 元组表）

### 关键架构决策

**来源:** 预筛报告（19 源实测裁定）+ 三视角调研（2026-09-30）

| 决策 | 选中方案 ✅ | 备选 | 理由 |
|------|-----------|------|------|
| D1: 三源选型 | EPO OPS + SEC EDGAR + UN Comtrade（预筛 Phase 1） | CNIPA（无 API WAF 全拦截）/ WIPO（600-2000 CHF + 无检索端点 + 无 CN 数据）/ BigQuery·cninfo·HKEX（Phase 2→4.1g） | 三者零许可成本 + 实测已通 + 语义补缺精准（专利归因/企业级财报/商品级行业量化） |
| D2: EPO OAuth2 模式 | 适配器内私有 `_EpoTokenManager`（缓存 + 过期刷新 + 401 重取一次） | 共享 OAuth 基类（YAGNI）/ parameters 传 token（越层） | 单源使用不预抽；构造注入 clock 可测试；Bearer 头与「Key 不入 URL」约束兼容 |
| D3: EPO 4GB/周配额守卫 | 进程内周窗口字节累计 + 超限前置抛 412 + Lock 类变量 + 可注入 | Redis 跨进程计数（多实例需求未现）/ 不守卫（违反 Fair Access） | 单进程组合根部署够用；412 与限流同族语义；前置零请求消耗 |
| D4: EDGAR 注册形态 | 免 key 无条件注册（A 组范式）+ UA 常量 + 进程内 8 req/s 令牌桶 | 条件注册（无 key 概念不适用） | 官方 Fair Access 免费；UA 与限速是唯一义务 |
| D5: Comtrade 形态 | **无条件注册 + key 可选增强**（preview 端点免 key 兜底；有 key 加 Ocp 头提升 500 次/天配额 + 日配额守卫——epics AC-4 承载） | 条件注册（key 缺失时 preview 能力不可达——功能闲置）/ 全量条件化（与 EDGAR 免 key 形态不一致） | **Story 层定稿**（不留 Task 0）：与 EDGAR 统一「官方免费通道可达即无条件注册，key 为增强」逻辑；构造器 key 可选不抛 101；此前三处表述矛盾（契约一/Task 4 红测试/异常表）已统一 |
| D6: required_fields 重构 | ADAPTER_SSOT 三元组→四元组（8 既有零漂移 + 3 新源定制）+ 断言查表化 + 绊线显式改 | 独立 REQUIRED_FIELDS_SSOT 表（双表漂移风险）/ 保留统一常量（违背按源定制目标） | 单表四元组最小改动面；R1-F5 收紧→4-1f 定制是既定演进路径（契约库 :60 注释预案落地） |
| D7: 中文参数方案 | CJK 检测自适应（query 含 CJK → tavily country=china / newsapi language=zh） | parameters 透传（标记语法不支持——`data_source_marker.py:211` 两参数形态）/ 适配器默认值一刀切（影响既有 13 个声明 Skill（newsapi 8 ∪ tavily 10）英文场景） | 零链路改动 + 零既有影响 + 确定性规则；确定性规则零既有影响（Tavily 官方 language 参数建议为备选——A/B 报告评估，见数据契约五） |
| D-08: D8 重开治理 | Task 0 HALT 显式签收（两态路径设计完备） | 静默重开（违反治理）/ 永久跳过（epics 4.1f 任务 6 已列） | 4-1c D8 为 Epic owner 级签收（:1180「不追加第三源，EPO 排期取消」）——重开需同级仪式；适配器交付与 D8 解耦 |
| D9: D2 修订形态 | 「2 源基线 + 4-1f 增补豁免表」（`test_unified_two_source_policy` 豁免化） | 全量放宽（丧失基线守护）/ 不改断言（vrio 必红） | epics 4.1f 任务 6 已授权修订；豁免表保留「未登记增补即红」防漂移语义 |
| D10: 能力边界声明 | architecture.md 显式登记 IDC/Gartner/Euromonitor 不可得 + 代理指标组合 | 不声明（后续 Story 重复踩坑） | 预筛致命证据（IDC ToS §2.2(g) 禁爬 + 禁 AI 平台；Gartner Cloudflare 全拦截）——边界留痕防重调研 |

### 项目结构说明 Project Structure（本 Story 新增/修改）

```
src/infrastructure/config/
├── epo_ops.py                    # Task 2：5 变量（API_URL/TIMEOUT/TTL_SECONDS + consumer_key/consumer_secret 双凭据）
├── sec_edgar.py                  # Task 3：三键（无 API_KEY）
└── comtrade.py                   # Task 4：四键

src/infrastructure/external_services/datasources/
├── epo_ops_adapter.py            # Task 2：_EpoTokenManager + 配额守卫 + CQL 检索
├── sec_edgar_adapter.py          # Task 3：UA + 令牌桶 + 双模式（检索/xbrl: 前缀）
├── comtrade_adapter.py           # Task 4：管道串解析 + Ocp 头
├── tavily_adapter.py             # Task 1：CJK 自适应（~10 行）
├── newsapi_adapter.py            # Task 1：CJK 自适应（~10 行）
└── __init__.py                   # Task 7：docstring 8→11

src/composition_root.py           # Task 7：三注册块 + 元组表 8→11 + shutdown 清理 +3

src/application/skills/
├── competitor-analysis/
│   ├── SKILL.md                  # Task 6：4→6 源声明 + SOP 全量
│   └── references/triangulation.md  # Task 6：3 处源数（:4/:10/:21）+ :43「未三角化」撤除
├── disruptive-innovation/
│   ├── SKILL.md                  # Task 6：2→3 源（D-08 前提）——「双源」11 处
│   └── references/{triangulation,workshop_guide,scoring_anchors}.md  # Task 6：三文件「双源」表述评估改写（签收态）
└── vrio-framework/SKILL.md       # Task 6：2→3 源（epics 授权——无签收前提）

tests/
├── unit/infrastructure/external_services/datasources/
│   ├── test_epo_ops_adapter.py   # Task 2
│   ├── test_sec_edgar_adapter.py # Task 3
│   └── test_comtrade_adapter.py  # Task 4（管道串 + 日配额守卫）
│   （tavily/newsapi 既有文件扩展——Task 1）
├── unit/application/skills/
│   ├── skill_data_collection_contracts.py   # Task 5：四元组 + 断言查表 + SSOT 元组（competitor/disruptive）
│   ├── skill_mixed_data_contracts.py        # Task 5：断言侧四元组化解包（import 继承——非复制体）+ Task 6：vrio 元组
│   └── test_skill_mixed_data_contracts.py   # Task 5：绊线 + 负例保活 / Task 6：D2 豁免 + STORY_SSOT vrio
├── unit/architecture/test_arch_skill_data_collection.py  # Task 5/7：解包四元组化 + _build_adapters 11 键
├── unit/architecture/test_arch_skill_mixed_data.py       # Task 5：解包四元组化 + Task 6：involved 加 EpoOpsAdapter
├── unit/architecture/test_arch_data_source.py            # Task 7：静态表四联动点（:71/:81/:85/:184）
├── contracts/test_port_contract_data_source.py           # Task 7：ADAPTER_PORT_SPECS +3
├── integration/external_services/data_sources/test_new_sources_integration.py  # Task 7
├── integration/application/test_skill_data_collection.py # Task 6：competitor 6 源/disruptive 3 源断言
├── integration/application/test_skill_mixed_data.py      # Task 6：len(metas) 参数化改写
├── acceptance/test_acceptance_data_source_expansion.feature/.py  # Task 0/8（新适配器步骤内延迟 import）
├── acceptance/test_acceptance_skill_mixed_data.feature   # Task 6：vrio 场景名
├── acceptance/test_acceptance_skill_mixed_data.py        # Task 6：vrio @scenario 串/函数名/docstring 三联动位
└── acceptance/contracts/skill_io_schemas.yaml            # Task 6：头注释源数（L218/L349/L732）+ 逐字锁死行同步
```

### 新增数据源完整触点清单（21 触点——dev 逐项核验）

适配器/config/组合根注册（条件块或无条件块）/组合根 `_build_data_source_adapters` 元组表/组合根 shutdown 清理列表/`__init__.py` docstring/单测/集成测试/ADAPTER_SSOT 四元组/契约断言两库解包（6 处之一）/架构测试 `test_arch_skill_data_collection.py`（`_build_adapters` + :124/:138 解包）/**架构测试 `test_arch_data_source.py` 静态表三常量 + 条件注册测试**/**架构测试 `test_arch_skill_mixed_data.py`（vrio 增源 involved 联动——两态均执行，见断言联动清单 16）**/`ADAPTER_PORT_SPECS` 契约表/子进程探针 env 注入行/受益 Skill frontmatter/SOP body 标记/**受益 Skill references/ 表述**/**4-1c 侧验收 feature/.py 场景名（清单 23/24）**/yaml（增源不触发——仅头注释与逐字锁死行）/root `.env` 样例/文档（architecture.md）。（manifest 不涉及——无新 Skill）

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 4.1e](./4-1e-skills-internal-framework.md)（五轮代码审查收敛）+ [4.1b/4.1c 遗产]

**关键学习/Key Learnings:**
- **共享文件一次性前置**（4-1d D8 先例）：Task 5（契约库）与 Task 7（注册链）跨 Task 中间态红窗口已显式声明（Task 5 DoD「注册侧除外——Task 7 收口」）——不追求虚假的全时绿
- **断言绊线是设计意图不是障碍**（4-1d R2-F12）：EXPECTED_REQUIRED_FIELDS 两绊线显式改 + 判别力负例保活——重构时保活改写而非删除
- **文档级语义与运行时行为分层**（4-1e R1-2 教训）：INSUFFICIENT_DATA 类语义在本 Story 无涉，但同理——配额守卫的 412 是真实运行时行为（适配器前置抛出），与 SOP 文档级降级话术分层清晰
- **变异演示判别力实证**（4-1c/4-1d 先例）：CJK 回归基线（非 CJK 请求体逐字一致断言）就是本 Story 的「变异演示」形态
- **治理签收不可静默绕过**（本次调研发现）：D8 重开必须同级仪式——HALT 决策 + 双文件留痕
- **条件注册闭包陷阱**（composition_root 先例）：注册块 lambda 内 import + `from_env()` 延迟执行，config import 放 if 块内
- **行号引用先读代码再动手**（4-1e v1.1.0 教训）：本 Story 文档行号来自 2026-09-30 三视角调研（Round 1 审查已实地复核校正）——实施时凡引用 file:line 先核实

**应用到本故事/Applied to This Story:**
- [x] Task 5/7 中间态显式声明（不虚假全绿）
- [x] 绊线显式改 + 负例保活
- [x] D-08 HALT 治理决策两态设计
- [x] CJK 回归基线断言（变异演示形态）
- [x] 断言联动 24 项清单（数据契约六内嵌）作为 Task 6 执行 checklist

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code（GLM-5.3 驱动） |
| **Version** | create-story workflow v6.3.0 |
| **Execution Date** | 2026-09-30 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md:1090-1146`（Story 4.1f） |
| **预筛报告** | `_bmad-output/planning-artifacts/data-source-expansion-prescreening.md`（19 源实测裁定） |
| **架构文档** | `docs/architecture/architecture.md`（§17.3.3 + :2855 defer 登记） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/4-1e-skills-internal-framework.md` |
| **治理冲突源** | `4-1c-skills-data-collection-integration.md:1180,:1186`（D8 签收） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **三视角调研** | 2026-09-30：①适配器基建面（8 适配器范本/注册链/测试模式）②契约联动面（41 处 required_fields/三元组解包 6 处/触点清单）③受益 Skill 与参数面（断言联动清单/D8 冲突发现/parameters 链路约束）——**Round 1 审查（2026-09-30）三视角复审 + 外部 API 实测（EPO 4GB/周与 token 端点/SEC 10 rps 与 UA 规范/Tavily country 枚举/Comtrade preview 端点）校正** |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（Story 4.1f 七组 AC 扩展）
- [x] 架构约束从 `architecture.md` + 预筛报告提取（含能力边界/合规）
- [x] 前一个故事学习经验整合（4.1e 五轮审查 + 4.1b/c 遗产）
- [x] 三视角代码调研落档（适配器基建/契约联动/受益面——含 D8 治理冲突发现）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/4-1f-skills-datasource-enhancement.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/infrastructure/config/epo_ops.py` / `sec_edgar.py` / `comtrade.py`
- `src/infrastructure/external_services/datasources/epo_ops_adapter.py` / `sec_edgar_adapter.py` / `comtrade_adapter.py`
- `tests/unit/infrastructure/external_services/datasources/test_epo_ops_adapter.py` / `test_sec_edgar_adapter.py` / `test_comtrade_adapter.py`
- `tests/integration/external_services/data_sources/test_new_sources_integration.py`
- `tests/acceptance/test_acceptance_data_source_expansion.feature` / `.py`
- `planning-artifacts/` 中文参数 A/B 实测报告

**待修改的文件（关键）:**
- `src/infrastructure/external_services/datasources/tavily_adapter.py` / `newsapi_adapter.py`（CJK 自适应）
- `src/composition_root.py`（三注册块 + 元组表 + shutdown）
- `tests/unit/application/skills/skill_data_collection_contracts.py` / `skill_mixed_data_contracts.py` / `test_skill_mixed_data_contracts.py`（四元组 + SSOT + 绊线 + D2 豁免）
- `tests/unit/architecture/test_arch_skill_data_collection.py`（解包 + _build_adapters）/ **`test_arch_skill_mixed_data.py`**（解包 + involved 联动）/ **`test_arch_data_source.py`**（静态表四联动点）+ `tests/contracts/test_port_contract_data_source.py`（契约表）
- `tests/integration/application/test_skill_data_collection.py` / `test_skill_mixed_data.py`（6 源/3 源断言）
- `tests/acceptance/test_acceptance_skill_mixed_data.feature`（vrio 场景名）+ **`tests/acceptance/test_acceptance_skill_mixed_data.py`**（@scenario 串/函数名/docstring 三联动位）+ **`tests/acceptance/test_acceptance_skill_data_collection.feature`/`.py`**（competitor「四源」场景 :38/:345/:347/:553 恒改 + disruptive「双源交叉验证」场景 :52/:357/:359 签收态——清单 23/24）+ `tests/acceptance/contracts/skill_io_schemas.yaml`（头注释 + 逐字锁死行）
- `src/application/skills/{competitor-analysis,disruptive-innovation,vrio-framework}/SKILL.md`（声明重分配）+ **受益 Skill references/**（competitor `references/triangulation.md` 3 处源数 + :43；disruptive 三文件「双源」表述——签收态）
- root `.env`（数据源 key 区段样例——本地文件不进 git，留 Dev Agent Record 记录）
- `docs/architecture/architecture.md`（适配器表 + 能力边界 + defer 清账 + 8.9.0 + :2829 D4 行重开留痕——签收态）+ `sisys-uni-exception-design.md`（零新增声明）
- `_bmad-output/implementation-artifacts/stories/4-1c-skills-data-collection-integration.md`（D8 条目 :1186 重开补记——签收态）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 4.1f |
| **Story Key** | 4-1f-skills-datasource-enhancement |
| **File** | `_bmad-output/implementation-artifacts/stories/4-1f-skills-datasource-enhancement.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 4: 战略工具箱 |
| **价值组** | Skills 数据供给质量（源数量充足性收敛） |
| **优先级** | P1-8（V1） |
| **覆盖 FR** | 评审催生专项（非 PRD FR 直映射——epics 4.1f 登记） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-8）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-7）
3. [x] Architecture constraints extracted 架构约束已提取（R3 主战场/R1R2 零改动）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。
> 编号规则：`R<轮>-<序号>`（R = 文档审查 Round；与代码审查周期的 R<n>-F/P/D 命名空间区分）。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-1 | `test_keyed_adapters_conditional_registration` 归属文件写错（实在 `test_arch_data_source.py:184` 非标注的 `test_arch_skill_data_collection.py`）；该文件另有 `ADAPTER_PORT_NAMES`(:71)/`KEYED_ADAPTER_PORT_NAMES`(:81)/`ADAPTER_IMPL_MODULES`(:85) 三联动点整体缺席——静态表驱动漏改是**静默的**（parametrize 不含新端口即不检查） | **P0** | AC-7/Task 7.3/测试分类表/追溯矩阵/项目结构/File List/触点清单七处同步：Task 7.3 拆为架构测试两文件同步（`test_arch_skill_data_collection.py` + `test_arch_data_source.py` 四联动点） |
| R1-2 | 「断言联动 20 项清单」声称「内嵌」实则不存在正文，「调研 3 §7 全表」无归档文件——Task 6.5 不可执行、AC-6 不可验收 | **P0** | 数据契约六实体化「断言联动 22 项清单」（按 competitor/vrio/disruptive/通用分组，含行号与两态标注）；Task 6.5/AC-6/DoD 指向本 Story 内嵌清单 |
| R1-3 | `test_arch_skill_mixed_data.py` 完全遗漏（:118/:132 三元组解包第 5/6 处炸点 + vrio 增源后 `_build_involved_adapters`/`:115` 集合断言/「6 个」注释联动无人认领）——Task 5 DoD「全绿」在该文件上必假 | P1 | Task 5 重构行「三元组解包 6 处全量枚举」+ 测试分类表/项目结构/File List/触点清单补该文件 + 断言联动清单第 16 项 |
| R1-4 | vrio 治理门内部矛盾：数据契约六 vrio 行称「Story 级决策 epics 已授权（无需签收）」vs AC-6/Task 6/治理节「disruptive/vrio 按 D-08 签收结果」——未签收时 epics 已授权的 vrio 增源被静默收缩 | P1 | 治理分级定稿：D8 射程仅 disruptive（owner 级签收重开 HALT 门控）；vrio 按 epics 4.1f 任务 6 :1127/:1129 授权**无条件执行 + 留痕**——治理前置/范围澄清/数据契约六/AC-6/Task 0.1/Task 6（循环 B 解绑）/R1 风险七处统一 |
| R1-5 | epics AC-4「Comtrade 500 次/天配额守卫」被静默删除；epics 任务 6 第 3/4 子项（Comtrade 语义匹配度评估留痕 + D2 修订评审结论留痕）漏承载 | P1 | 数据契约四补日配额守卫设计（复用 EPO 守卫模式，请求计数口径）+ AC-4/Task 4 TDD 循环 B + 异常表行；Task 6.8 补两个评估留痕 subtask + AC-6 验证标准 |
| R1-6 | Comtrade 构造行为三处互斥矛盾（契约一「条件注册」vs D5「倾向宽松 key 缺失仍 preview」vs Task 4 红测试「key 缺失构造→101」+ 异常表同款） | P1 | Story 层定稿（不留 Task 0）：**无条件注册 + key 可选增强**（preview 免 key 兜底，与 EDGAR 统一「官方免费通道可达即注册」逻辑）——契约一/数据契约四/AC-4/Task 4/异常表/7.1/7.6/探针八处统一；D5 决策改写 |
| R1-7 | EPO 业务请求 401 重取与 helper 101 映射交互路径未写——dev 三种解读中两种错误（裸 catch 误重试/绕开 helper 违反硬约束——最可能绕行方向） | P1 | 异常契约表补「EPO 业务请求 401」行（捕获 101 → `context.status_code==401` 判别 → 强制刷新 → 重发一次 → 仍失败上抛）+ 数据契约二/Task 2 循环 A/R2 同步 |
| R1-8 | disruptive「双源」实为 11 处（+「2 源」1 处）只列五处；references/ 三文件（triangulation/workshop_guide/scoring_anchors）「双源」表述与 competitor references/triangulation.md「4 个声明源」3 处 + :43「未三角化」均未入联动面 | P1 | 硬约束节源数计数小节全量重列（SKILL.md + references/ + templates/）+ 数据契约六联动面/断言联动清单 7-8/18-19 项 + R5 风险更新 |
| R1-9 | 「既有 10 个 newsapi/tavily 声明 Skill」口径错误（newsapi 8 ∪ tavily 10 = **13 个**）——回归范围漏 3 个 Skill | P1 | Task 1.3 显式枚举 13 Skill 清零歧义 + D7 备选列口径修正 |
| R1-10 | 4-1d 验收联动只提 feature 场景名——`.py` 三联动位（@scenario 绑定串/函数名/docstring）与 feature L5 总述未列；File List 漏 `.py` 文件 | P1 | AC-6 验证标准补三联动位 + 项目结构/File List/断言联动清单 15 项 |
| R1-11 | Task 5「4-1d 库同步（复制体同改）」事实错误——4-1d 库 import 4-1c 契约库（R2-F3 单一来源），identity 绊线强制禁止复制；按字面执行会弄红绊线 | P1 | 改写为「经 import 自动继承四元组变更，仅改本库断言侧（:339 解包 + :344 查表化）」+ 项目结构注释同步 |
| R1-12 | 前置依赖漏 4.1d（本 Story 大改其测试资产） | P2 | :24 补「4.1d 亦为前置」及理由 |
| R1-13 | EDGAR「非法前缀→413」与异常契约表「query 非法→201」冲突；「自写错误映射」约束句与自身三处设计（201/413/412 自抛）矛盾 | P2 | 统一：非法前缀归 201（输入前置校验）；约束句改写为「HTTP 映射禁止自写 + 适配器三类自抛白名单」 |
| R1-14 | 守卫设计缺 clock 注入与字节计量口径（「周窗口重置」单测不可测；「预估响应体」在 helper 抽象下不可实现） | P2 | 数据契约二补：`now_fn` 注入（与令牌管理器同款）+ 字节口径 = 响应 JSON 序列化字节数（事后累计）+ Task 0/2/4 同步 |
| R1-15 | Task 0 验收骨架若顶部 import 新适配器→整文件收集错误持续到 Task 4，阻塞 Task 1-3 同文件场景且与逐 Task 全绿矛盾 | P2 | Task 0.5 强制「步骤内延迟 import」（先例 `test_acceptance_data_source.py:560-561`）——红收敛到新源场景本身 |
| R1-16 | root `.env.example` 不存在（AC-7 引用会让 dev 困惑或误建）；A/B 报告归档路径 `planning-artifacts/` 二义 | P2 | AC-7/7.5 改 root `.env` 单点 + deploy 模板评估结论留痕说明；AC-1 归档路径改 `_bmad-output/planning-artifacts/` |
| R1-17 | EDGAR required_fields 单元组不覆盖双模式形态（检索/XBRL 字段不同）+ epics 示例偏差未登记 | P2 | 契约一/契约三声明「检索模式为准 + XBRL 差异进 §5 口径段」+ epics 偏差留痕 |
| R1-18 | AC-1 允许「零实证闭环」（key 未就绪也勾选完成）且缺口结论无判定标准；epics AC-1 的 topic/domains 参数收窄未登记 | P2 | AC-1 未就绪态降级「部分完成 + 缺口 defer（owner 知情）」+ 结论须标证据等级；topic/domains 入范围划出清单与 A/B 评估项 |
| R1-19 | 风险表遗漏 4 项（preview 样本子集/CJK 混合反效果/EPO 仅 EP 口径代表性/Task 5-7 红窗口 CI 破坏） | P2 | 风险表 +R9~R12（R12 含红窗口两类区分与提交策略） |
| R1-20 | 「architecture.md D4 行」三处 D4 未钉行号；vrio 引言 L98-99 无数字与 L138「双源交叉」混列；STORY_SSOT「双侧」口径含混；yaml 行号偏移（:347-348→:349、:380-384→:383-385）；EPO env 变量数（5 个非四键）；shutdown 基数（7 项非 8）；`data_source_marker.py` 路径（services/ 非 skills/）；断言消息「8 个」文案；日期不一致；覆盖率 75% 无测量方式；KEY_SENSITIVE_SOURCES 未评估登记 | P2/P3 | 逐处精确化（:2829 钉行/vrio 联动分开表述/单侧双侧澄清/行号校正/5 变量清单/7→10/路径补全/清单 22 项/日期统一 09-30/AC 覆盖率节补测量方式（`--cov=src/infrastructure`）/Task 0 补 KEY_SENSITIVE 评估项） |
| R1-21 | EPO 令牌端点失败枚举不完整（「101 或 411」漏 412/413/302）；令牌管理器 retry 参数未透传（单测退避拖秒）；令牌桶断言方向未约束（CI flaky）；探针 without 分支 scrub 范围；CJK「byte-for-byte」措辞过强；AC-2 超限降级话术未安排；skip 补跑无锚点 | P3 | 异常表补枚举/契约二 retry 透传/Task 3 断言仅下界/7.6 scrub-all/1.1 措辞改 dict 逐键/R7 补跑锚点（P3 级部分随相关章节改写收口，其余留 Round 2+ 台账） |
| R2-1 | 19 触点清单将 `test_arch_skill_mixed_data.py` involved 联动误标「D8 签收态」——与断言联动清单 16（vrio 组·无签收前提）矛盾：未签收世界线照做则 `:115` 集合断言必红（R1-4 漏网第 8 处） | P2 | 触点清单改「vrio 增源 involved 联动——两态均执行」；计数 19→21（增 4-1c 验收 feature/.py 与 references 表述后逐段清点校准） |
| R2-2 | AC-6 第 5 条（yaml 双写）与 Task 6.6 无两态标注——未签收世界线字面执行会把 disruptive yaml 改 3 源，与「维持 2 源」矛盾（同 checkbox 第 6 条有标注，粒度不一致） | P2 | 两处补「disruptive 项签收态」限定（L349/:383-385 与 L732/vrio 侧分开表述） |
| R2-3 | 4-1c 侧验收场景联动位整体缺席：competitor「四源并发采集链路」（feature :38 + py :345/:347/:553——**无条件漏项**）与 disruptive「双源交叉验证采集链路」（:52 + py :357/:359——签收态）不在 24 项清单，File List 亦漏 feature/.py 两文件 | P2 | 断言联动清单补第 23/24 项 + File List/触点清单/测试分类表联动（vrio 同款有清单 15 三处覆盖，本次消除非对称遗漏） |
| R2-4 | `test_keyed_adapters_conditional_registration` 现 `(port_name, env_key)` 单键结构承载不了 epo-ops 双门合取——半凭据态（KEY 有 SECRET 无）实际不注册而单键断言「应注册」→ 假红；7.6 with_key 分支双常量未显式 | P2 | AC-7/Task 7.3 注明参数化结构扩展为 `(port_name, env_keys)` 多键合取（`all()`）；探针双凭据**成对**注入显式化 |
| R2-5 | scoring_anchors.md「双源」实测 4 行（:3/:14/:20/:33）只列 2 行（枚举失真——对照 triangulation/workshop 全对） | P2 | 硬约束节补 :20/:33 |
| R2-6 | Task 7.4 集成测试目录 `external_sources` 与实际目录结构/测试分类表/项目结构（`external_services`）不一致——按字面执行会建错目录（v1.0.0 遗留） | P3 | 7.4 路径改 `tests/integration/external_services/data_sources/` |
| R2-7 | 「循环 A（competitor）+ vrio 循环」「循环 A + vrio」与 R1 风险行「循环 A-B」三种写法并存（语义均正确，风格不齐） | P3 | 统一「循环 A-B（competitor/vrio）」 |
| R2-8 | R1-20 修复表承诺的覆盖率测量方式未落入正文覆盖率节 | P3 | 补 `pytest tests/unit/infrastructure --cov=src/infrastructure` 测量命令与分层说明 |
| R2-9 | AC-1 Then「byte-for-byte」与 Task 1.1「dict 逐键」措辞不一；AC-2 令牌端点枚举局部矛盾（「101 或 411」vs 后半全枚举）；AC-2 完成态歧义（skip 即完成 vs AC-1 式降级）；epics AC-2「超限熔断降级话术」（epics :1107 明文）无承载位 | P3 | AC-1 Then 改「dict 逐键一致」；AC-2 枚举补全 + 完成判定声明（单测矩阵为准，集成 Defer 追认——与 AC-1 降级的差异理由）+ 412 降级话术挂 Task 6 清单 4 |
| R2-10 | 「唯二内容改动」粒度滞后 R1-8（仅写 SKILL.md）且与「唯二生产 .py 行为改动」存在同词头混淆风险；Task 2「config 四键 + 双凭据字段」与命名规范「5 变量」有 6 键误读空间；Comtrade from_env key 缺失语义（空串=无 key）未逐字写 | P3 | :21 改「唯二内容资产改动」（SKILL.md + references/ + yaml）+ 两口径区分说明；Task 2 改「5 变量」；Task 0.3 补 from_env 空串语义钉死 |
| R3-1 | **Task 5 四元组化的「适配器侧不对称」未定稿（dev 必撞分叉）**：既有 8 适配器 `get_metadata()` 均不填 required_fields（省略→默认 `()`——`DataSourceRef` docstring :84 声明性元数据归声明面的既有架构语义），frontmatter 侧是 `("indicator","value")`；6 处解包中 2 处适配器侧（`test_arch_skill_data_collection.py:124`/`test_arch_skill_mixed_data.py:118`）若断言第 4 项则 8 既有源必红且需扩 8 个生产文件改动面（不在 File List/触点清单） | **P1** | Task 5 重构行定稿：适配器侧 2 处解包第 4 项以 `_` 弃用 + 注释（required_fields 由 frontmatter↔SSOT 双方承载）；Task 2/3/4 红测试「四元组对齐」措辞改为「对齐 SSOT name/url/api_type/ttl 四值（required_fields 不在适配器侧断言）」 |
| R3-2 | Task 0 KEY_SENSITIVE_SOURCES 评估只写单向后果「漏登记无测试红」——登记方向的连锁红未登记：`test_key_sensitive_skills_count`（:63-75）为精确集合断言（dual/single/7），epo-ops 入表则 vrio 移入 dual 集合断言全红；`:380-384` 失败处理话术断言同红——该测试不在 24 项清单 | P2 | Task 0 评估项补两态（推荐循 uspto 先例不登记——同为 keyed 条件注册源且不在表，Skill §7 未注册行已承载降级；登记则 count 测试 + 话术断言须扩入清单） |
| R3-3 | 清单 7/8/19/22 项与 vrio 验收场景（15 项）无自动断言红（references 仅存在性断言/断言消息文案/场景步骤声明驱动）——AC-6「全绿」措辞对这些项是空诺 | P3 | 清单头部声明保障机制 + 第 7/8/19/22/15 项逐项标注「无自动断言——grep 核验 + review 保障」 |
| R3-4 | EpoOpsAdapter 构造器 config 缺省行为未定稿（uspto 式 `config or Config()` 回退对 EPO 是错误模式——空凭据回退推迟爆炸到首个请求） | P3 | Task 0.3 定稿：config 必填、空凭据构造期即抛 101（fail-fast 优于延迟炸） |
| R3-5 | architecture.md 版本号 8.9.0 实为三处同步点（:17 头部/:3600 修订表/:3613 尾部表），Story 只列修订历史一处 | P3 | Task 8.2 补三处同步清单 |
| R3-6 | vrio 验收 .py 三联动位行号实测 L449-451（Story 写 L450-452，±1）；Task 2 DoD 与项目结构两处「四键」残留（4+2=6 键误读——R2-10 修复不彻底）；R12「4-1e D8 先例」归属错（实测源头 4-1d `:611`——「D8」一词三义易混） | P3 | 行号校正（清单 15/AC-6/循环 B）；两处「四键」→「5 变量」；R12 改「4-1d『一次性预调整』先例（彼 Story D8，非本 Story 治理 D8）」 |
| R4-1 | R3-6 的行号「校正」反向偏移——主会话实测定谳：`@scenario` L450 / `def` L451 / docstring L452（v1.2.0 原行号本正确，R3 终审员误报 ±1）；R3-1 修复方案列「Task 2/3/4 红测试措辞」范围夸大（实测仅 Task 2 红行含「四元组对齐」措辞，Task 3/4 从未含——记录级出入） | P3 | 三处行号回正 L450-452（清单 15/AC-6/Task 6 循环 B）；R3-1 范围夸大作记录级注记不改正文（正文语义无冲突） |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** （待 dev-story 完成后填写）
**审查模式:** （待填写）

#### 需决策 Decision Needed

- [ ] （待填写）

#### 已修复 Patch

- [ ] （待填写）

#### 已推迟 Defer

- [ ] Phase 2 适配器（BigQuery/cninfo/HKEX/协会 crawler/PDF 管道）→ Story 4.1g
- [ ] 专职中文源（百度千帆/东财/新浪）→ AC-1 缺口结论后评估
- [ ] OAuth2 共享抽象 → 第二家 OAuth2 源出现时
- [ ] 跨进程精确配额计数（Redis）→ 多实例部署需求出现时
- [ ] yaml data_sources.items 字段级化的输出侧描述精化残余 → 随 4.1g/后续（本 Story 承载 required_fields 定制主项）
- [ ] SPACE 分档斜线双语义 → space-matrix 下次触碰（4-1d 既有 defer 维持）
- [ ] token 预算门禁 → Story 4.3/Epic 5（4-1d R3 defer 维持）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] **外部前置即刻启动（不占带宽）：EPO OPS key（developers.epo.org）/ UN Comtrade key（comtradedeveloper.un.org）注册申请**
- [ ] 运行 `validate-create-story` 进行质量检查（可选）
- [ ] 运行 `dev-story` 开始实施（Task 0 含 D-08 治理 HALT 决策——需 Epic owner 在场）
- [ ] 运行 `code-review` 进行代码审查（建议换用不同 LLM）

---

**故事版本/Story Version:** v1.3.1
**创建日期/Created:** 2026-09-30
**最后更新/Last Updated:** 2026-09-30
**更新说明/Description:**
- v1.0.0: 创建故事文件（基于 epics 4.1f 定义 + 四域预筛报告实测裁定 + 三视角代码调研（适配器基建/契约联动/受益面——发现 D8 治理冲突并设计两态处理）+ 4.1e 五轮审查 Lessons；10 项决策登记；8 Task / 7 AC）
- v1.1.0: **Round 1 文档审查修订**（三视角代码调研复审 + 外部 API 实测 + 三视角并行审查）：P0×2（`test_arch_data_source.py` 四联动点归属与缺席 / 断言联动清单实体化 22 项）+ P1×9（vrio 治理门解绑统一 / Comtrade 配额守卫与无条件注册定稿 / EPO 401 重取路径 / epics 三子项漏承载 / `test_arch_skill_mixed_data.py` 遗漏 / 复制体误述 / 双源 11 处与 references 联动 / 13 Skill 口径 / 验收 .py 三联动位）+ P2/P3 系列精确化——详见 Docs Review Fixes R1-1~R1-21
- v1.2.0: **Round 2 回归核查 + 组合可达性审查修订**（R1 修复 21 项逐项核验：17 完整/4 部分 + 8 组合场景推演：两态世界线/双门合取/时序闭合）：P2×5（R2-1 触点清单 vrio 联动误标签收态 / R2-2 yaml 双写两态标注缺失 / R2-3 4-1c 验收场景漏项——清单扩至 24 项 / R2-4 双门合取参数化结构 / R2-5 scoring_anchors 枚举补全）+ P3×5（R2-6~R2-10 路径/风格/覆盖率命令/措辞系列收口）——主线组合自洽（R1 五组核心变更互不拆台）
- v1.3.0: **Round 3 dev 执行视角可满足性终审修订**（24 项清单逐项红绿推演 + 关键架构声明实测验证）：**P1×1**（R3-1 Task 5 四元组适配器侧断言语义定稿——既有 8 适配器 get_metadata 不填声明性字段的架构语义显式化，适配器侧第 4 项弃用断言，避免 8 生产文件意外扩面）+ P2×1（R3-2 KEY_SENSITIVE 登记两态连锁红登记）+ P3×4（R3-3~R3-6 无断言项标注/EPO config 必填定稿/8.9.0 三处同步/行号与措辞校正）；「零 domain 改动」声明经 `DataSourceRef.required_fields` 字段（:96）与 frontmatter 加载链（:195-205）实测成立
- v1.3.1: **Round 4 纯验证轮**（七维度快扫：三轮 37 项修复落地/计数一致性/行号抽查/两态标注 46 处/内部引用闭合/结构完整/格式卫生——全部通过，**零 P0/P1 残留**）+ R4-1 行号回正（R3-6 校正反向偏移，主会话实测定谳 L450-452）
