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

本 Story 是**基础设施层 Story**（R3 主战场）：三个新适配器实现既有 `DataSourcePort`（R1 既有端口零新增），注册进组合根既有聚合链（R2 既有组合注入零改动）；生产代码改动面 = infrastructure 适配器/config + composition_root 注册 + 契约库测试基建（required_fields 按源定制重构）。**唯二内容改动** = 三个受益 Skill 的 SKILL.md 声明/SOP 增补 + tavily/newsapi 适配器 CJK 自适应（~10 行/适配器）。

**来源:** [`epics_v1.0.md`](../../planning-artifacts/epics_v1.0.md) - Epic 4: 战略工具箱，Story 4.1f（P1-8，V1；:1090-1146）
**前置依赖:** 4.1a/4.1b/4.1c/4.1e（✅ 全 done）+ 外部前置（EPO OPS Consumer Key / UN Comtrade key 免费注册——**申请可即刻异步启动，等待期不阻塞 Task 0-1 与 EDGAR 全部工作**；SEC EDGAR 免 key）
**后续依赖:** Phase 2（Google Patents BigQuery/巨潮 cninfo/港交所披露易/协会 crawler/PDF 管道）→ 后续 Story 4.1g

### ⚠️ Story 范围澄清（重要）

**本 Story 交付（范围边界）：**

- 三个新适配器：`epo-ops`（专利域第一优先——OAuth2 + `pa=` 申请人检索）/ `sec-edgar`（企业财报域——免 key + XBRL）/ `comtrade`（行业量化域——HS 商品级）
- tavily/newsapi 适配器中文参数 CJK 自适应（~10 行/适配器 + A/B 实测报告）
- `required_fields` 按源定制联动（ADAPTER_SSOT 三元组 → 四元组重构——承载原 4.3 defer 项）
- 受益 Skill 声明重分配：competitor-analysis（4→6 源，无治理冲突）+ disruptive-innovation / vrio-framework（2→3 源，**D8/D2 决策重开前提——见下**）
- 能力边界声明与合规登记（architecture.md：IDC/Gartner/Euromonitor 不可得 + 新源 UA/署名/配额合规）
- 适配器注册链全触点（组合根条件注册 + `_build_data_source_adapters` 元组表 + shutdown 清理 + `ADAPTER_PORT_SPECS` 契约表 + 架构测试加元组）

**不在本 Story 范围（明确划出）：**

- **Phase 2 适配器**（Google Patents BigQuery/巨潮 cninfo/港交所披露易/中汽协乘联会 crawler/PDF→文本管道）→ Story 4.1g（预筛报告 §四）
- **百度千帆/东财/新浪等专职中文源**——Phase 0 CJK 自适应实测后评估剩余缺口再议（本 Story AC-1 闭环判断，评估结论留痕不实施）
- **OAuth2 共享抽象基类**——单源使用不预抽（YAGNI），未来第二家 OAuth2 源出现时再抽
- **跨进程精确配额计数**（Redis 计数器）——单进程组合根部署下进程内计数够用，多实例部署需求出现时再议
- **既有 8 源的 required_fields 改值**——8 既有源保持 `("indicator","value")` 零漂移（41 处 frontmatter 联动核验，不改值）
- **标记语法第三参数（parameters 透传）**——CJK 自适应方案已绕开此需求（决策 D7）；扩展标记语法属生产链路行为变更，如未来需要独立决策

### ⚠️ 治理前置：D8 决策重开（阻断性——Task 0 必办）

**调研发现的治理冲突（阻断 disruptive/vrio 增源）：** 4-1c Story 文件审查记录（`4-1c-skills-data-collection-integration.md:1180,:1186`）载明——「**D8（Epic 2 源偏差签收）已于 2026-09-28 由 Epic owner（项目负责人）签收：2 源双源交叉验证为终态，不追加第三源**（**WIPO/EPO 适配器排期取消**，Defer 项关闭）」；`architecture.md` D4 决策行同款留痕。

本 Story 给 disruptive-innovation 增补 epo-ops 属于**重开已关闭的 Epic owner 级签收**；vrio-framework 增源则触发 4-1d D2「统一 2 源策略」断言重写（`test_unified_two_source_policy`）。

**处理方式（Task 0 决策项 D-08）：** dev-story 执行到 Task 0 时 **HALT 向 Epic owner（用户）显式请求 D8 重开签收**——签收则 disruptive/vrio 增源按主线执行并在 4-1c Story 文件 D8 条目 + architecture.md D4 行补记重开留痕；**未签收则 disruptive/vrio 增源子任务跳过**（competitor 增源不受影响——4-1c Skill 无「不追加」签收），受益面收敛为 competitor 单 Skill，AC-6 验证标准按实际签收结果记录。适配器交付本身（AC-2/3/4/5）与 D8 无关——三个适配器无论如何都交付并注册。

### ⚠️ 命名规范声明（强制）

**禁止使用故事编号命名编码开发**（4-1c 实施期确立）。全部新增文件功能性命名（无 `_4_1f` 后缀）。新数据源 name（kebab-case，= DataSourceRef.name = frontmatter 声明名 = resolver 映射键 = ADAPTER_SSOT 键，四位一体）：**`epo-ops` / `sec-edgar` / `comtrade`**；组合根端口名 `data_source_epo_ops` / `data_source_sec_edgar` / `data_source_comtrade`；环境变量 `EPO_OPS_*` / `SEC_EDGAR_*` / `COMTRADE_*` 四键模式（API_KEY/API_URL/TIMEOUT/TTL_SECONDS——EDGAR 无 API_KEY）。

---

## 🛡️ 硬约束声明（CLAUDE.md §5）

### 领域零依赖（FR-AR-01）

- 本 Story 生产代码改动**全部位于 infrastructure 层**（适配器/config）+ composition_root（注册）——`src/domain/` 与 `src/application/` 生产代码**零改动**（R1 既有 DataSourcePort 不动、R2 既有组合注入不动）；受益 Skill 的 SKILL.md 是内容资产非代码
- domain 层禁止外部依赖（`.importlinter` 契约）：新适配器禁止 import application（六边形依赖倒置——经组合根注入）
- **新适配器必须完整复用 `_http_helpers.request_json_with_resilience`**（tenacity 重试 + CircuitBreaker + 异常映射集中点）——禁止自写错误映射（411/412/413/101/201/302 的抛出逻辑全在 helper，适配器只做 `_extract_*` 结构校验）

### 异常体系强制

- **本 Story 零新增领域异常**（全部复用既有——见「领域异常契约」节复用表）
- 提交前三条 grep 自查零新引入（既有命中均为历史代码）
- 禁止 `# noqa` / `# type: ignore` / `# pylint: disable`

### Commit & Push 规范

- 提交信息禁止 AI 署名；禁止 `--no-verify`；main 分支直接开发

### Skills 内容约束

- 受益 Skill SKILL.md 修改保持 ≤500 行（余量充足：competitor 259/disruptive 210/vrio 218）
- **每个新声明源必须在 SKILL.md body 出现 ≥1 个 `$DATA_SOURCE` 标记**（`assert_cross_consistency` 双向断言——标记正则 `[\w-]+` 天然兼容连字符名 `epo-ops`）
- 源数计数表述全量同步（「4 个声明源」→「6 个」等——competitor §5/§7 三处、disruptive「双源」五处（含 yaml 逐字锁死的 L79）、vrio 引言/§5 表）
- **SKILL.md 与 yaml 逐字锁死的 description 双写同步**（disruptive `sources` description「数据来源（双源交叉验证）」与 `skill_io_schemas.yaml:380-384`；competitor `patent_signals` description 与 yaml:257-259——改措辞必须两处同改）

### 代码质量门禁

- `poetry run ruff check src/ tests/`（行宽 128，E/F/I/N/W）+ `poetry run mypy src/` + `pytest tests/ -n 8` 连续 5 次无随机失败 + pre-commit 全过

---

## 🎯 领域异常契约

> **原则**：异常是领域契约的一部分。本 Story **不新增领域异常**（显式决策 D-EX——全部失败路径已由 4.1b 异常体系覆盖，`_http_helpers` 集中映射）。

| 场景 | 复用异常 | 编码 | 依据 |
|------|---------|------|------|
| 新源 HTTP 5xx/连接失败/熔断 | `DataSourceUnavailableError` | EXCEPTION_411 | `_http_helpers.py:192-197,:287-303` 既有 |
| EPO OAuth2 令牌端点 401/403（凭证错误） | `ConfigurationError` | EXCEPTION_101 | helper :219-223 既有（消息零 Key 材料） |
| 新源 HTTP 429 限流 | `DataSourceRateLimitError` | EXCEPTION_412 | helper :211-215 既有 |
| **EPO 4GB/周配额超限（适配器前置守卫）** | `DataSourceRateLimitError` | EXCEPTION_412 | 配额耗尽与限流同族语义（D3 决策）——守卫在 fetch 前置检查抛出，零请求消耗 |
| 新源响应结构异常/缺字段/非法 JSON | `DataSourceResponseError` | EXCEPTION_413 | helper :227-240,:304-311 + 适配器 `_extract_*` 二段校验既有模式 |
| EPO OAuth2 令牌获取网络失败（重试耗尽） | `DataSourceUnavailableError` | EXCEPTION_411 | 令牌获取走同款 resilience helper |
| Comtrade/EPO key 缺失（条件注册下不会发生；构造防御） | `ConfigurationError` | EXCEPTION_101 | newsapi/tavily 构造器先例（:64-70） |
| query 参数非法（如 page_size 非整数） | `ValidationError` | EXCEPTION_201 | `parse_int_param` helper :91-125 既有 |
| EDGAR 请求超时 | `TimeoutError` | EXCEPTION_302 | helper :251-259 既有 |

**提交前自查**：三条 grep 零新引入 + 新适配器文件 grep `raise ` 确认仅 raise 既有异常类型（结构校验的 `DataSourceResponseError` + 守卫的 `DataSourceRateLimitError`）。

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
| `sec-edgar` | `https://efts.sec.gov`（base） | `rest_json` | `2592000`（财报月/季频） | `("company", "form", "filed_at")` | **免 key**（强制 UA 头） | **无条件注册**（A 组范式——worldbank 先例） |
| `comtrade` | `https://comtradeapi.un.org` | `rest_json` | `604800`（月频数据 7 天缓存） | `("cmd_code", "trade_value", "period")` | `COMTRADE_API_KEY` | 条件注册 |

注：ADAPTER_SSOT 由三元组 `(url, api_type, ttl_seconds)` 扩为**四元组** `(url, api_type, ttl_seconds, required_fields)`——8 既有源第四项一律 `("indicator", "value")`（零漂移）；ttl 范围校验 `60 <= ttl <= 2592000` 既有不变。

### 数据契约二：EPO OPS 适配器行为契约（预筛实测依据）

- **认证**：OAuth2 client-credentials——`POST /3.2/auth/token`（Basic auth = consumer_key:consumer_secret，`grant_type=client_credentials`）→ access_token 缓存（进程内 + 过期提前 60s 刷新）；业务请求 `Authorization: Bearer <token>`；401 时令牌失效重取一次
- **检索**：`GET /3.2/published-data/search?q=pa="华为" and ti="battery"`（CQL——`pa=` 申请人（支持中文名）/ `ti=` `ab=` `ta=` 关键词 / `cpc=` 分类 / `pd=` 日期）+ `Accept: application/json` + `Range` 头分页
- **配额守卫（D3）**：进程内周窗口字节累计（周一 00:00 GMT 重置）——累计值 + 预估响应体超过 `4 * 1024**3` 时 fetch 前置抛 `DataSourceRateLimitError`（消息含已用字节数与重置时间）；计数器 `asyncio.Lock` 类变量保护
- **query 规范（写入受益 Skill §5/§6）**：CQL 表达式字符串（如 `pa="BYD" and ti="battery"`）——结构化检索语法（非自然语言，同 world-bank 指标码范式）
- **confidence**：0.9（官方专利局）

### 数据契约三：SEC EDGAR 适配器行为契约

- **UA 强制**：`User-Agent: sisys-tools/1.0 (contact@sisys.local)` 常量（官方 Fair Access 要求「公司名 邮箱」格式——无 UA 实测 403）
- **限速**：进程内令牌桶 `8 req/s`（官方 10 留余量；`asyncio.Semaphore` + 时间窗实现）
- **fetch 双模式（query 前缀分派）**：
  - 检索模式（缺省）：query = 检索词（如 `"market share" forms=10-K` 或纯关键词）→ `GET https://efts.sec.gov/LATEST/search-index?q=...&forms=10-K`（Elasticsearch 风格 JSON → `{"filings": [{"company","cik","form","filed_at","file_url"}]}`）
  - XBRL 模式：query 前缀 `xbrl:` → `xbrl:CIK0001318605:Revenues` 调 `data.sec.gov/api/xbrl/companyconcept/...`（单指标时序）或 `xbrl-frame:us-gaap/Revenues/CY2024Q1` 调 frames（跨公司横截面）→ `{"concept","unit","values":[...]}`
  - 两个 base_url（efts/data.sec.gov/archives）——config 三 URL 字段或单 client 多 base 拼绝对 URL（Task 0 定稿：**绝对 URL 拼接**，单 httpx client）
- **query 规范**：检索词（自然语言或 `"关键词" forms=表单类型` 语法）或 `xbrl:CIK:概念` 前缀
- **confidence**：0.95（美政府法定披露）

### 数据契约四：UN Comtrade 适配器行为契约

- **认证**：`Ocp-Apim-Subscription-Key` 请求头（Azure APIM）
- **检索**：`GET /public/v1/preview/C/A/HS?reporterCode=156&period=2024&cmdCode=8703&flowCode=X`（实测无 key 亦通——key 提升 500 次/天配额）
- **query 规范**：管道分隔参数串 `reporter=156|cmd=8703|flow=X|period=2024`（适配器解析为 query params——HS 商品码必填，reporter 缺省 156 中国口径）或直接完整 query string 透传（Task 0 定稿：**结构化管道串**，同 china-nbs 路径范式「机器码非自然语言」）
- **confidence**：0.9（联合国官方统计）

### 数据契约五：中文参数 CJK 自适应（D7——tavily/newsapi 扩展）

- **规则**：适配器 fetch 内检测 `query.query` 是否含 CJK 字符（`any("一" <= ch <= "鿿" for ch in query.query)`）：
  - tavily：含 CJK → 请求体加 `"country": "china"`（官方全名枚举）；不含 → 行为零变化
  - newsapi：含 CJK → params 加 `"language": "zh"`；不含 → 行为零变化
- **理由**：零链路改动（标记语法不传 parameters——`data_source_marker.py:211` 既有两参数形态）+ 零既有影响（英文 query 路径 byte-for-byte 不变）+ 与 Tavily 官方「query 用与 language 相同语言书写」建议一致
- A/B 实测报告（AC-1）：扩展前后同 query 对比（真实 key 时实测；key 未就绪则以 MockTransport 断言请求体参数构造正确 + 报告留待 key 就绪补）

### 数据契约六：受益 Skill 声明重分配表

| Skill | 现源 | 新源序 | 治理前提 | 联动面 |
|---|---|---|---|---|
| competitor-analysis | newsapi, uspto, tavily, china-nbs | + `epo-ops` + `sec-edgar`（6 源：newsapi, uspto, epo-ops, sec-edgar, tavily, china-nbs——声明序即断言序） | **无**（4-1c Skill 无「不追加」签收） | 契约库 SSOT 元组 + frontmatter data_sources 块 + §5 映射表（专利布局 uspto+epo-ops 2 源——「未三角化」标注撤除 + 新增 EDGAR 财报印证行）+ §5 口径段（EPO 欧洲口径 + 合并后仍缺 CNIPA 声明 / EDGAR 美股上市公司口径）+ §6 标记示例（+2 标记）+ §7 计数（「4 个声明源」→「6 个」×3 处 + 未注册行扩列） |
| disruptive-innovation | uspto, tavily | + `epo-ops`（3 源：uspto, epo-ops, tavily） | **D8 重开签收**（Epic owner） | 同构 + 「双源」五处表述（L6/L79/L140-143/L188/L190）+ yaml:347-348/:380-384 逐字同步 + D4 表述改「专利双库 + 市场单源，评级互证跨域」 |
| vrio-framework | uspto, tavily | + `epo-ops`（3 源：uspto, epo-ops, tavily） | **D2 修订**（统一 2 源 → 2 源基线 + 增补豁免表——Story 级决策，epics 4.1f 任务 6 已授权） | 同构 + 引言 L98-99 + §5 表加行 + `test_unified_two_source_policy` 豁免改写 |

**断言联动 20 项清单**（调研 3 §7 全表——dev 实施时逐项执行，见 Task 6）。

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
**Then** tavily 请求体自动加 `country: "china"`、newsapi params 自动加 `language: "zh"`；query 不含 CJK 时行为与改动前 byte-for-byte 一致

**验证标准/Validation Criteria:**
- [ ] 两适配器单测：CJK query 断言请求体含新参数（MockTransport capture）/ 非 CJK query 断言请求体与既有形态完全一致（回归负例）
- [ ] A/B 实测报告归档 `planning-artifacts/`（key 就绪时真实对比「比亚迪 战略动态」类 query 质量；key 未就绪则断言层验证 + 报告标注待补）
- [ ] 剩余缺口结论留痕（是否需要专职中文源——本 Story 内闭环判断，不实施）

### AC-2: EPO OPS 适配器（OAuth2 + 配额守卫 + 申请人检索）

**Given** EPO OPS Consumer Key/Secret 已配置（或单测 MockTransport）
**When** 适配器 fetch CQL 检索（`pa=` 申请人 / `ti=` 关键词）
**Then** OAuth2 令牌自动获取/缓存/刷新；4GB/周配额守卫前置（超限抛 EXCEPTION_412 零请求消耗）；结果结构化为 `{"patents": [{"title","applicant","filing_date"}]}`

**验证标准/Validation Criteria:**
- [ ] 单测全绿：令牌流（Basic auth 头/缓存命中不重复请求/401 重取一次/令牌端点失败→101 或 411）、检索成功、CQL query 直通断言、配额守卫（注入计数器超限→412 + 消息含已用量）、失败矩阵（201/302/411/412/413/熔断）、config repr 脱敏、`isinstance(adapter, DataSourcePort)`
- [ ] key 就绪时集成实测 `pa="华为"` 返回真实结果（key 未就绪 skip 留痕）

### AC-3: SEC EDGAR 适配器（UA 规范 + 限速 + 双模式）

**Given** EDGAR 免 key（无条件注册）
**When** fetch 检索模式（关键词/`forms=` 语法）或 XBRL 模式（`xbrl:CIK:概念` 前缀）
**Then** 全部请求带规范 UA 头；限速 ≤8 req/s；检索模式返回 `{"filings": [...]}`、XBRL 模式返回 `{"concept","unit","values"}`

**验证标准/Validation Criteria:**
- [ ] 单测全绿：UA 头断言（capture）、限速令牌桶（并发 10 请求实测节流）、双模式分派、XBRL CIK/概念解析、失败矩阵、结构校验（缺 filings/concept 字段→413）
- [ ] 集成实测（免 key 无条件）：`q="market share" forms=10-K` 真实返回 + `xbrl:CIK0001318605:Revenues` 营收时序（Tesla CIK 实测锚点——预筛已验证端点）

### AC-4: UN Comtrade 适配器（key + HS 商品级）

**Given** COMTRADE_API_KEY 已配置（或 preview 端点免 key 实测）
**When** fetch 结构化管道串 query（`reporter=156|cmd=8703|flow=X|period=2024`）
**Then** 适配器解析为 API params（cmd 必填校验→201）；结果结构化 `{"records": [{"cmd_code","trade_value","period"}]}`

**验证标准/Validation Criteria:**
- [ ] 单测全绿：管道串解析（含缺 cmd 抛 201 负例）、Ocp 头断言、成功/失败矩阵、结构校验
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

### AC-6: 受益 Skill 声明重分配（治理前提 + 断言联动 20 项）

**Given** D8 重开签收决策已执行（Task 0 HALT——签收/未签收两态留痕）
**When** competitor（无前提直接做）+ disruptive/vrio（按签收结果）完成声明重分配
**Then** SSOT 元组/frontmatter/§5-§7 表述/§6 标记/口径段/yaml 逐字锁死行全量同步；断言联动 20 项清单全绿

**验证标准/Validation Criteria:**
- [ ] `assert_data_sources_contract`（声明序元组相等）+ `assert_cross_consistency`（每新源 ≥1 标记）+ `assert_sop_maturity`（源数计数表述同步后全绿）
- [ ] `test_triangulation_competitor_four_sources` 改 6 源语义（名/docstring/强断言 `== 6`）；`test_disruptive_innovation_dual_source` 按 D8 结果（签收→`== 3` + D4 表述同步；未签收→跳过该项）
- [ ] `test_unified_two_source_policy` 改「2 源基线 + 4-1f 增补豁免表」（vrio 签收前提）；`STORY_SSOT` 双侧同步
- [ ] 4-1d 集成 `len(metas) == 2` 参数化改 `== len(declared)`；4-1d 验收 feature 场景名「双源」→「三源」（vrio 场景）
- [ ] yaml 头注释源数同步（competitor「4 源」→「6 源」/disruptive/vrio「2 源」→「3 源」）+ 逐字锁死 description 双写同步
- [ ] **D8 留痕**：签收则 4-1c Story D8 条目 + architecture.md D4 行补记重开（未签收则本 Story Dev Agent Record 登记决策结果）

### AC-7: 注册链全触点与能力边界声明

**Given** 三个新适配器实现完成
**When** 注册进组合根并同步全部触点
**Then** 条件注册（epo-ops/comtrade）与无条件注册（sec-edgar）正确；`_build_data_source_adapters` 元组表 8→11；shutdown 清理列表追加；`ADAPTER_PORT_SPECS` 契约表 +3；架构测试三方一致

**验证标准/Validation Criteria:**
- [ ] `test_arch_skill_data_collection.py`：`_build_adapters` 同步后 `set(adapters.keys()) == set(ADAPTER_SSOT.keys())`（8→11 双向）；`test_keyed_adapters_conditional_registration` 加 epo-ops/comtrade 元组（EDGAR 免 key 不入条件表）
- [ ] 契约测试 `ADAPTER_PORT_SPECS` +3 条目（env_key：EDGAR 为 None）
- [ ] 子进程探针：三源注册态双向（key 有/无）
- [ ] `__init__.py` docstring 8→11；`.env`/`.env.example` 数据源 key 区段补三源样例（root `.env` L113 附近 + 安装器模板评估）
- [ ] architecture.md §17.3.3：适配器表 +3（含条件注册标注）+ 能力边界声明（IDC/Gartner/Euromonitor 独家份额数据不可得——合同与技术双重壁垒，代理指标组合替代）+ 合规登记（EDGAR UA 规范/Comtrade 署名/EPO 配额政策）+ defer 清账（4.1f 承载项完成留痕）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

#### 领域事件 Schema (Domain Events)

- 本 Story 零事件新增（「领域事件」节声明）；Task 0 checklist 该项填「不适用——零事件」

#### 数据模型 (Data Models)

- [ ] 三新源元数据表定稿（上文「数据契约一」为基线——url/api_type/ttl/required_fields 四值经适配器 get_metadata() 实测校准后冻结进 ADAPTER_SSOT 四元组）
- [ ] EPO 令牌管理设计定稿（进程内缓存结构/过期刷新阈值 60s/401 重取一次上限）
- [ ] EPO 配额守卫设计定稿（周窗口重置点周一 00:00 GMT/字节累计含响应体/Lock 保护/守卫可注入性）
- [ ] EDGAR 双模式分派语法定稿（检索模式缺省 + `xbrl:` 前缀；UA 常量值定稿）
- [ ] Comtrade 管道串语法定稿（`reporter=156|cmd=8703|flow=X|period=2024`——cmd 必填）
- [ ] CJK 自适应规则定稿（检测函数/两适配器参数映射/非 CJK 零变化回归基线）
- [ ] required_fields 四元组重构方案定稿（EXPECTED_REQUIRED_FIELDS 常量去向：保留 legacy 注释 or 移除——含 4-1d 库 import/`__all__`/绊线三处联动定稿）
- [ ] 受益 Skill 声明序定稿（competitor 6 元组序 / disruptive/vrio 3 元组序——声明序即断言序）

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

- [ ] 编写 `tests/acceptance/test_acceptance_data_source_expansion.feature`（zh-CN，按 AC 分节：三新源 Happy 各场景 + Edge：key 缺失条件注册跳过/配额超限 412/令牌失效重取/CJK 自适应双态/EDGAR 免 key 直连——**范本 `test_acceptance_data_source.feature`**（4.1b 验收，`context` dict + `_FakeDataSourceAdapter` 仅限端口替身 + 真实 Resolver/Redis + xdist_group））
- [ ] 编写 BDD 步骤实现骨架（新源场景用真实新适配器实例 + MockTransport 注入——适配器构造支持 client 注入是既有模式；key 就绪场景动态 skip）
- [ ] 运行确认失败（🔴 红阶段验证——适配器模块不存在的 ModuleNotFoundError 亦为合法红）

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
| SDD 架构验证 | 适配器注册链 | 三方一致/条件注册双向/元数据对齐 | `test_arch_skill_data_collection.py` 扩展 | Task 7 |
| 集成测试 | 真实端点 | 三源真实连通（key 门控 skip） | `tests/integration/external_services/data_sources/test_new_sources_integration.py` | Task 7 |
| TDD 验收测试 | Gherkin/BDD | AC 全场景 | `test_acceptance_data_source_expansion.feature`/`.py` | Task 0/8 |

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] 整体 ≥80% 不降；**基础设施层 ≥75%**（本 Story 主战场——新适配器语句级覆盖由单测矩阵保证）
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
| AC-6 | 受益 Skill 声明重分配 | Task 6 | 6.1-6.8 | 三 Skill 单测 + 集成/验收联动 20 项 |
| AC-7 | 注册链全触点 + 能力边界 | Task 7 | 7.1-7.6 | `test_port_contract_data_source.py`/`test_arch_skill_data_collection.py` 扩展 |
| 全 AC | 收尾验收 + 文档同步 | Task 8 | 8.1-8.5 | BDD 全场景 + architecture.md 同步 |

---

## ⚠️ 风险与缓解策略（Risk Register）

| # | 风险 | 概率 | 影响 | 缓解措施 | 触发 Task |
|---|------|------|------|---------|----------|
| **R1** | D8 重开未获签收（disruptive/vrio 增源半途受阻） | 中 | 中 | Task 0 HALT 显式决策；未签收路径设计完备（competitor 独行 + 适配器照常交付 + AC-6 按 RESULT 记录）；断言联动清单标注两态分支 | Task 0/6 |
| **R2** | EPO OAuth2 令牌流复杂度（缓存/刷新/401 重取三分支） | 中 | 中 | 令牌管理内聚为适配器私有类 `_EpoTokenManager`（构造注入 clock 便于测试）；单测三分支强制；不抽共享基类（YAGNI） | Task 2 |
| **R3** | 配额守卫进程内计数在测试并行下竞态 | 低 | 中 | `asyncio.Lock` 类变量；守卫计数构造可注入；单测串行验证 + 并发测试用 `asyncio.gather` 真并发断言 | Task 2 |
| **R4** | required_fields 重构破坏 41 处既有断言链 | 中 | 高 | 四元组扩展向后兼容设计（8 既有源值零漂移）；绊线显式改 + 判别力负例保活；41 处 grep 计数核验；全量回归门禁 | Task 5 |
| **R5** | 声明重分配断言联动面广（20 项）漏改 | 中 | 高 | 调研 3 §7 清单作为 Task 6 的执行 checklist 逐项勾选；每改一处跑对应单测；集成/架构/验收三层回归 | Task 6 |
| **R6** | EDGAR 双模式分派语法被 LLM 误用（xbrl: 前缀拼写） | 低 | 低 | query 规范写入 SKILL.md §5/§6（结构化语法非自然语言）；非法前缀→413 结构校验负例 | Task 3/6 |
| **R7** | key 申请周期阻塞集成实测 | 中 | 低 | 单测全 MockTransport 不依赖 key；集成/验收动态 skip 留痕；EDGAR 免 key 可全程实测；key 到位后补测（AC 验证标准已留两态） | Task 7/8 |
| **R8** | 中文 A/B 实测被 key 阻塞（newsapi 商用限制） | 中 | 低 | AC-1 验证标准两态设计（断言层验证先行 + 报告标注待补）；CJK 规则的正确性不依赖实测 | Task 1 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ TDD 循环内化原则：每个 Task 独立完成红→绿→重构；每个 Subtask 组按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置 + D8 治理决策）

**关联 AC:** 全部（AC-1 ~ AC-7 的规范输入）

> 目的：进入实现前钉死三源元数据/行为契约/重构方案/声明序 + 执行 D8 重开 HALT 决策。

- [ ] Subtask 0.1: **D-08 治理决策执行（HALT）**——向 Epic owner 显式请求 D8 重开签收（disruptive 2 源终态签收的重开 + vrio D2 修订确认）；签收结果与两态执行路径留痕 Dev Agent Record
- [ ] Subtask 0.2: 三源元数据表定稿（数据契约一为基线——url 经实测校准；ttl/required_fields 冻结）；声明序定稿（competitor 6 元组/disruptive/vrio 3 元组）
- [ ] Subtask 0.3: 行为契约细化定稿（EPO 令牌管理/配额守卫、EDGAR 双模式语法与 UA 常量、Comtrade 管道串语法、CJK 规则）+ required_fields 重构方案（含 EXPECTED_REQUIRED_FIELDS 常量去向三处联动定稿）
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

- [ ] Subtask 1.1: 🔴 红 — CJK 双态 + 回归基线测试
- [ ] Subtask 1.2: 🟢 绿 — 两适配器自适应实现
- [ ] Subtask 1.3: 🔄 重构 — 提炼与全量回归（既有 10 个 newsapi/tavily 声明 Skill 测试零回归）
- [ ] Subtask 1.4: A/B 实测报告（key 就绪真实对比 / 未就绪断言层验证 + 标注待补）+ 剩余缺口结论留痕

**完成标准/Definition of Done:**
- [ ] CJK 双态测试绿 + 既有回归零破坏 + 报告归档

---

### Task 2: EPO OPS 适配器（含 OAuth2 令牌管理与配额守卫）

**关联 AC:** AC-2

#### TDD 循环 [A]：令牌管理器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `test_epo_ops_adapter.py`：`_EpoTokenManager` 三分支（首次获取 Basic auth 头断言/缓存命中不重复请求/401 失效重取一次）+ 令牌端点 401→101 + 网络耗尽→411 |
| 🟢 绿 | 令牌管理私有类（进程内缓存 + 过期提前 60s 刷新 + 构造注入 clock） |

#### TDD 循环 [B]：配额守卫

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 守卫两分支（放行累计/超限抛 412 含已用量与重置时间）+ 周窗口重置 + 并发安全（gather 竞态） |
| 🟢 绿 | 周窗口字节累计（`asyncio.Lock` 类变量 + 可注入初始值） |

#### TDD 循环 [C]：适配器主体

| 阶段 | 动作 |
|------|------|
| 🔴 红 | fetch 成功（CQL 直通 + Bearer 头 + `Accept: application/json` + Range 分页）+ 结构校验（缺 patents→413）+ get_metadata（四元组对齐 Task 0 冻结值）+ 失败矩阵（201/302/411/412/413/熔断）+ key 缺失构造→101 + repr 脱敏 + isinstance(DataSourcePort) |
| 🟢 绿 | 适配器实现（复用 `request_json_with_resilience`——令牌获取亦走 resilience） |
| 🔄 重构 | `src/infrastructure/config/epo_ops.py`（四键 + consumer_key/consumer_secret 双凭据字段）+ docstring 中文注释 + ruff/mypy |

- [ ] Subtask 2.1: 🔴 红 — 令牌管理三分支测试
- [ ] Subtask 2.2: 🟢 绿 — `_EpoTokenManager` 实现
- [ ] Subtask 2.3: 🔴🟢 — 配额守卫（守卫测试→实现）
- [ ] Subtask 2.4: 🔴🟢 — 适配器主体（全矩阵测试→实现 + config）
- [ ] Subtask 2.5: 🔄 重构 — 全绿 + key 就绪集成实测（`pa="华为"`）

**完成标准/Definition of Done:**
- [ ] 三循环全绿 + 关键路径 100%（令牌三分支/守卫两分支）
- [ ] config 四键 + 条件注册预备（双凭据门）

---

### Task 3: SEC EDGAR 适配器（UA + 限速 + 双模式）

**关联 AC:** AC-3

#### TDD 循环 [A]：限速令牌桶 + UA 规范

| 阶段 | 动作 |
|------|------|
| 🔴 红 | UA 头常量断言（全部请求）+ 令牌桶节流（并发 10 请求实测 ≤8/s 窗口） |
| 🟢 绿 | 进程内令牌桶（Semaphore + 时间窗）+ UA 常量 |

#### TDD 循环 [B]：双模式 fetch

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 检索模式（缺省——efts search-index + forms 解析）/ XBRL 模式（`xbrl:CIK:概念` 前缀分派 + companyconcept/frames 两形态）/ 非法前缀→413 / 结构校验双模式（缺 filings/concept→413）+ 失败矩阵 |
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

#### TDD 循环 [A]：管道串解析 + 适配器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 管道串解析（完整四参/缺省 reporter=156/缺 cmd→201 负例）+ Ocp 头断言 + 成功（records 结构化）+ 结构校验 + 失败矩阵 + key 缺失构造→101（preview 端点免 key 语义：key 可选但配额提升——Task 0 定稿构造行为） |
| 🟢 绿 | 适配器实现 + config 四键 |
| 🔄 重构 | ruff/mypy |

- [ ] Subtask 4.1: 🔴 红 — 解析与矩阵测试
- [ ] Subtask 4.2: 🟢 绿 — 适配器实现
- [ ] Subtask 4.3: 🔄 重构 — 全绿
- [ ] Subtask 4.4: 集成实测（preview 免 key——`reporter=156|cmd=8703` 中国整车出口）

**完成标准/Definition of Done:**
- [ ] 全绿 + preview 端点真实记录实测

---

### Task 5: required_fields 按源定制联动（契约库重构）

**关联 AC:** AC-5

#### TDD 循环 [A]：ADAPTER_SSOT 四元组 + 断言查表

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `test_skill_mixed_data_contracts.py`：四元组结构断言（11 源 × 4 项）+ 查表断言改写预演（按 `ADAPTER_SSOT[ref.name][3]`）+ 绊线两处新语义测试（`test_expected_required_fields_value_locked` 改为「8 既有源值锁定 + 3 新源定制值锁定」or 常量移除后的替代锚点——Task 0 定稿方案的红测试） |
| 🟢 绿 | `skill_data_collection_contracts.py`：ADAPTER_SSOT 扩四元组（+3 新源条目——依赖 Task 2/3/4 的 get_metadata 实测值）+ `assert_data_sources_contract` 查表化；4-1d 库同步（复制体同改 + import/`__all__` 联动） |
| 🔄 重构 | 判别力负例保活（漂移副本 match 串同步）+ `test_arch_skill_data_collection.py` 的 `_build_adapters` 同步（依赖 Task 7 注册——**本 Task 先行改契约侧，注册侧 Task 7 收口**；两 Task 间架构测试暂红属预期中间态，Task 7 全绿） |

- [ ] Subtask 5.1: 🔴 红 — 四元组 + 查表 + 绊线新语义测试
- [ ] Subtask 5.2: 🟢 绿 — 契约库两版重构
- [ ] Subtask 5.3: 🔄 重构 — 负例保活 + 41 处既有 frontmatter grep 计数核验零漂移
- [ ] Subtask 5.4: 全量 skills 测试回归（既有 16 Skill 断言零破坏）
- [ ] Subtask 5.5: EXPECTED_REQUIRED_FIELDS 常量去向落地（Task 0 方案）

**完成标准/Definition of Done:**
- [ ] 四元组重构全绿（注册侧除外——Task 7 收口）+ 41 处零漂移实证

---

### Task 6: 受益 Skill 声明重分配（断言联动 20 项）

**关联 AC:** AC-6

> 前提：Task 0.1 D-08 决策结果；契约侧 SSOT 元组在 Task 5 已四元组化——本 Task 改声明元组（源序）并同步全部内容面。

#### TDD 循环 [A]：competitor-analysis（4→6 源，无治理前提）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | `test_competitor_analysis_data_collection.py` 全红（SSOT 元组 6 化后 frontmatter 仍 4 源——name 集合断言红） |
| 🟢 绿 | SKILL.md：frontmatter data_sources +2 块（epo-ops/sec-edgar 定制 required_fields）/ §5 映射表（专利布局 2 源 + 「未三角化」标注撤除 + EDGAR 财报印证新行）/ §5 口径段（EPO 欧洲 + 合并仍缺 CNIPA / EDGAR 美股口径）/ §6 标记 +2 / §7 计数三处 + 未注册行扩列 |
| 🔄 重构 | 契约库 SSOT 元组 6 化 + 集成测试改 6 源语义（`test_triangulation_competitor_four_sources` 改名/强断言 `== 6`） |

#### TDD 循环 [B]：disruptive/vrio（2→3 源，D-08 签收前提——未签收则跳过并留痕）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 两 Skill 单测红（同构） |
| 🟢 绿 | 两 SKILL.md 同构修改（含 disruptive「双源」五处 + yaml 逐字锁死行双写 + vrio §5 表加行 + query 规范条目） |
| 🔄 重构 | D2 断言改写（`test_unified_two_source_policy` 豁免表 + `STORY_SSOT` 双侧 + `len(metas)==2` 参数化改 `== len(declared)` + 4-1d feature 场景名「双源」→「三源」）+ D8 留痕（4-1c Story D8 条目 + architecture.md D4 行补记——签收态） |

- [ ] Subtask 6.1: 🔴🟢 — competitor 声明与内容全量（循环 A）
- [ ] Subtask 6.2: competitor 集成断言 6 源化
- [ ] Subtask 6.3: 🔴🟢 — disruptive/vrio（D-08 签收态；未签收跳过留痕）
- [ ] Subtask 6.4: D2 断言改写 + 4-1d 联动（集成/验收/architecture D4 行）
- [ ] Subtask 6.5: 断言联动 20 项清单逐项勾选核验（调研 3 §7 全表）
- [ ] Subtask 6.6: yaml 头注释源数 + 逐字锁死 description 双写同步
- [ ] Subtask 6.7: 三 Skill 全链路（声明/标记/口径/行数 ≤500）全绿
- [ ] Subtask 6.8: 全量回归（4-1c/4-1d/4-1e 三层测试零破坏）

**完成标准/Definition of Done:**
- [ ] 声明重分配全绿 + 20 项清单全勾 + D-08 结果留痕

---

### Task 7: 注册链全触点 + 集成实测（SDD 架构约束验证）

**关联 AC:** AC-7

- [ ] Subtask 7.1: composition_root 三注册块（epo-ops/comtrade 条件注册——EDGAR 无条件 A 组范式）+ `_build_data_source_adapters` 元组表 8→11 + shutdown 清理列表 +3（自持 httpx）
- [ ] Subtask 7.2: `tests/contracts/test_port_contract_data_source.py` 的 `ADAPTER_PORT_SPECS` +3（env_key/EDGAR None）+ 探针脚本 env 注入行
- [ ] Subtask 7.3: `test_arch_skill_data_collection.py`：`_build_adapters` 同步（import + 实例化 + dict 11 键——EDGAR 免 key 直接实例化/EPO+Comtrade 占位 key `NewsAPIConfig(api_key="arch-test-placeholder")` 先例）+ `test_keyed_adapters_conditional_registration` +2 元组 → 三方一致断言 `set(keys) == set(ADAPTER_SSOT.keys())` 全绿（Task 5 中间态收口）
- [ ] Subtask 7.4: 集成实测文件 `tests/integration/external_sources/data_sources/test_new_sources_integration.py`（三源真实端点——EDGAR 无条件/EPO+Comtrade key 动态 skip；TestTenant 前缀）
- [ ] Subtask 7.5: `__init__.py` docstring 8→11 + `.env`/`.env.example` 数据源 key 区段补样例（root `.env` L113 CLOUD_LLM_API_KEY 附近 + 安装器模板评估——若安装器模板不涉及数据源则仅 root 层留痕说明）
- [ ] Subtask 7.6: 子进程探针三源注册态双向（key 有/无——EDGAR 恒注册）

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
- [ ] Subtask 8.2: architecture.md §17.3.3 同步（适配器表 +3/能力边界声明/合规登记/defer 清账——AC-7 验证标准全项）+ §17.3 状态表 4.1f 行 + 修订历史 8.9.0
- [ ] Subtask 8.3: 异常设计文档零新增声明（§3.3.2 复用表追加——412/101 新语义映射归属既有）
- [ ] Subtask 8.4: 全量 `pytest -n 8` + ruff + mypy + pre-commit + 连续 5 次
- [ ] Subtask 8.5: A/B 报告与 D-08 决策记录归档核验

**完成标准/Definition of Done:**
- [ ] 全部完成清单验证确认 + Story 可进入 review

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) + 预筛报告 + 三视角代码调研（2026-09-29）

- **架构模式:** 六边形（Ports & Adapters）；本 Story = R3 基础设施层新增实现（R1/R2 零改动、R4 无涉）
- **设计约束:** 新适配器必须复用 `_http_helpers.request_json_with_resilience`（错误映射集中——禁止自写 411/412/413 映射）；`parse_int_param` 参数校验前置；httpx 禁 `follow_redirects`（跨域转发 Key 头安全约束）
- **技术栈:** Python 3.11+ / httpx（AsyncClient + MockTransport 测试）/ tenacity（resilience helper 内聚）
- **接口治理:** 零端口变更——新适配器经组合根既有聚合链注入（`_build_data_source_adapters` 元组表）

### 关键架构决策

**来源:** 预筛报告（19 源实测裁定）+ 三视角调研（2026-09-29）

| 决策 | 选中方案 ✅ | 备选 | 理由 |
|------|-----------|------|------|
| D1: 三源选型 | EPO OPS + SEC EDGAR + UN Comtrade（预筛 Phase 1） | CNIPA（无 API WAF 全拦截）/ WIPO（600-2000 CHF + 无检索端点 + 无 CN 数据）/ BigQuery·cninfo·HKEX（Phase 2→4.1g） | 三者零许可成本 + 实测已通 + 语义补缺精准（专利归因/企业级财报/商品级行业量化） |
| D2: EPO OAuth2 模式 | 适配器内私有 `_EpoTokenManager`（缓存 + 过期刷新 + 401 重取一次） | 共享 OAuth 基类（YAGNI）/ parameters 传 token（越层） | 单源使用不预抽；构造注入 clock 可测试；Bearer 头与「Key 不入 URL」约束兼容 |
| D3: EPO 4GB/周配额守卫 | 进程内周窗口字节累计 + 超限前置抛 412 + Lock 类变量 + 可注入 | Redis 跨进程计数（多实例需求未现）/ 不守卫（违反 Fair Access） | 单进程组合根部署够用；412 与限流同族语义；前置零请求消耗 |
| D4: EDGAR 注册形态 | 免 key 无条件注册（A 组范式）+ UA 常量 + 进程内 8 req/s 令牌桶 | 条件注册（无 key 概念不适用） | 官方 Fair Access 免费；UA 与限速是唯一义务 |
| D5: Comtrade 形态 | 条件注册（COMTRADE_API_KEY）+ Ocp 头 + preview 端点免 key 兜底 | 无条件（key 缺失时配额骤降） | key 可选语义——Task 0 定稿构造行为（倾向宽松：key 缺失仍可 preview 模式） |
| D6: required_fields 重构 | ADAPTER_SSOT 三元组→四元组（8 既有零漂移 + 3 新源定制）+ 断言查表化 + 绊线显式改 | 独立 REQUIRED_FIELDS_SSOT 表（双表漂移风险）/ 保留统一常量（违背按源定制目标） | 单表四元组最小改动面；R1-F5 收紧→4-1f 定制是既定演进路径（契约库 :60 注释预案落地） |
| D7: 中文参数方案 | CJK 检测自适应（query 含 CJK → tavily country=china / newsapi language=zh） | parameters 透传（标记语法不支持——`data_source_marker.py:211` 两参数形态）/ 适配器默认值一刀切（影响既有 10 个声明 Skill 英文场景） | 零链路改动 + 零既有影响 + 确定性规则；Tavily 官方「query 同语言书写」建议对齐 |
| D-08: D8 重开治理 | Task 0 HALT 显式签收（两态路径设计完备） | 静默重开（违反治理）/ 永久跳过（epics 4.1f 任务 6 已列） | 4-1c D8 为 Epic owner 级签收（:1180「不追加第三源，EPO 排期取消」）——重开需同级仪式；适配器交付与 D8 解耦 |
| D9: D2 修订形态 | 「2 源基线 + 4-1f 增补豁免表」（`test_unified_two_source_policy` 豁免化） | 全量放宽（丧失基线守护）/ 不改断言（vrio 必红） | epics 4.1f 任务 6 已授权修订；豁免表保留「未登记增补即红」防漂移语义 |
| D10: 能力边界声明 | architecture.md 显式登记 IDC/Gartner/Euromonitor 不可得 + 代理指标组合 | 不声明（后续 Story 重复踩坑） | 预筛致命证据（IDC ToS §2.2(g) 禁爬 + 禁 AI 平台；Gartner Cloudflare 全拦截）——边界留痕防重调研 |

### 项目结构说明 Project Structure（本 Story 新增/修改）

```
src/infrastructure/config/
├── epo_ops.py                    # Task 2：四键 + consumer_key/consumer_secret 双凭据
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
├── competitor-analysis/SKILL.md  # Task 6：4→6 源声明 + SOP 全量
├── disruptive-innovation/SKILL.md# Task 6：2→3 源（D-08 前提）
└── vrio-framework/SKILL.md       # Task 6：2→3 源（D-08 前提）

tests/
├── unit/infrastructure/external_services/datasources/
│   ├── test_epo_ops_adapter.py   # Task 2
│   ├── test_sec_edgar_adapter.py # Task 3
│   └── test_comtrade_adapter.py  # Task 4
│   （tavily/newsapi 既有文件扩展——Task 1）
├── unit/application/skills/
│   ├── skill_data_collection_contracts.py   # Task 5：四元组 + 断言查表 + SSOT 元组
│   ├── skill_mixed_data_contracts.py        # Task 5：同构 + vrio 元组
│   └── test_skill_mixed_data_contracts.py   # Task 5：绊线 + 负例保活 / Task 6：D2 豁免
├── unit/architecture/test_arch_skill_data_collection.py  # Task 7：_build_adapters 11 键 + 条件表
├── contracts/test_port_contract_data_source.py           # Task 7：ADAPTER_PORT_SPECS +3
├── integration/external_services/data_sources/test_new_sources_integration.py  # Task 7
├── integration/application/test_skill_data_collection.py # Task 6：competitor 6 源/disruptive 3 源断言
├── integration/application/test_skill_mixed_data.py      # Task 6：len(metas) 参数化改写
├── acceptance/test_acceptance_data_source_expansion.feature/.py  # Task 0/8
├── acceptance/test_acceptance_skill_mixed_data.feature   # Task 6：vrio 场景名（+py docstring）
└── acceptance/contracts/skill_io_schemas.yaml            # Task 6：头注释源数 + 逐字锁死行同步
```

### 新增数据源完整触点清单（16 触点——调研 2 §7，dev 逐项核验）

适配器/config/组合根注册/`__init__` docstring/单测/集成测试/ADAPTER_SSOT/架构测试 `_build_adapters` 同步/声明表登记/受益 Skill frontmatter/SOP body 标记/yaml（增源不触发——仅头注释与逐字锁死行）/契约常量与绊线/架构内容断言（自动循环）/manifest（不涉及——无新 Skill）/文档（architecture.md）。

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 4.1e](./4-1e-skills-internal-framework.md)（五轮代码审查收敛）+ [4.1b/4.1c 遗产]

**关键学习/Key Learnings:**
- **共享文件一次性前置**（4-1d D8 先例）：Task 5（契约库）与 Task 7（注册链）跨 Task 中间态红窗口已显式声明（Task 5 DoD「注册侧除外——Task 7 收口」）——不追求虚假的全时绿
- **断言绊线是设计意图不是障碍**（4-1d R2-F12）：EXPECTED_REQUIRED_FIELDS 两绊线显式改 + 判别力负例保活——重构时保活改写而非删除
- **文档级语义与运行时行为分层**（4-1e R1-2 教训）：INSUFFICIENT_DATA 类语义在本 Story 无涉，但同理——配额守卫的 412 是真实运行时行为（适配器前置抛出），与 SOP 文档级降级话术分层清晰
- **变异演示判别力实证**（4-1c/4-1d 先例）：CJK 回归基线（非 CJK 请求体逐字一致断言）就是本 Story 的「变异演示」形态
- **治理签收不可静默绕过**（本次调研发现）：D8 重开必须同级仪式——HALT 决策 + 双文件留痕
- **条件注册闭包陷阱**（composition_root 先例）：注册块 lambda 内 import + `from_env()` 延迟执行，config import 放 if 块内
- **行号引用先读代码再动手**（4-1e v1.1.0 教训）：本 Story 文档行号来自 2026-09-29 三视角调研——实施时凡引用 file:line 先核实

**应用到本故事/Applied to This Story:**
- [x] Task 5/7 中间态显式声明（不虚假全绿）
- [x] 绊线显式改 + 负例保活
- [x] D-08 HALT 治理决策两态设计
- [x] CJK 回归基线断言（变异演示形态）
- [x] 断言联动 20 项清单作为 Task 6 执行 checklist

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
| **三视角调研** | 2026-09-30：①适配器基建面（8 适配器范本/注册链/测试模式）②契约联动面（41 处 required_fields/触点 16 项/len==16 锚点）③受益 Skill 与参数面（断言联动 20 项/D8 冲突发现/parameters 链路约束） |

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
- `tests/unit/architecture/test_arch_skill_data_collection.py` / `tests/contracts/test_port_contract_data_source.py`（注册链 + 契约表）
- `tests/integration/application/test_skill_data_collection.py` / `test_skill_mixed_data.py`（6 源/3 源断言）
- `tests/acceptance/test_acceptance_skill_mixed_data.feature`（vrio 场景名）+ `tests/acceptance/contracts/skill_io_schemas.yaml`（头注释 + 逐字锁死行）
- `src/application/skills/{competitor-analysis,disruptive-innovation,vrio-framework}/SKILL.md`（声明重分配）
- `docs/architecture/architecture.md`（适配器表 + 能力边界 + defer 清账 + 8.9.0）+ `sisys-uni-exception-design.md`（零新增声明）

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

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| （待审查） | | | |

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

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-09-30
**最后更新/Last Updated:** 2026-09-30
**更新说明/Description:**
- v1.0.0: 创建故事文件（基于 epics 4.1f 定义 + 四域预筛报告实测裁定 + 三视角代码调研（适配器基建/契约联动/受益面——发现 D8 治理冲突并设计两态处理）+ 4.1e 五轮审查 Lessons；10 项决策登记；8 Task / 7 AC / 断言联动 20 项清单内嵌）
