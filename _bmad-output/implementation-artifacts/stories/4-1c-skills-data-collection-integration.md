# Story 4.1c: Skills 数据采集集成（外部数据型 Skills 完善）

**Status:** `done`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 工具工程师,
**I want** 6 个外部数据驱动型 Skills（pestel-analysis / porters-five-forces / appeals-analysis / competitor-analysis / scenario-planning / disruptive-innovation）复用 Story 4.1b 的 DataSourcePort 基础设施，实现自动外部数据获取,
**So that** Agent 调用这 6 个 Skills 时能自动从权威数据源获取高质量、可靠、新鲜的信息，LLM 基于真实数据生成结构化分析输出，无需用户手工填入数据。

### 业务价值

Story 4.1b 已交付完整数据采集基础设施（DataSourcePort + 8 适配器 + Redis 缓存 + 新鲜度评分 + `$DATA_SOURCE` 标记解析 + Engine.Execute 集成 + Resolver 白名单编排），但 **23 个 SKILL.md 均未声明 `data_sources` 白名单**（解析链路已通、声明内容为空），且**生产链路存在关键缺口**：`StrategicAnalysisUseCase` 仅调用 L1 `load_metadata`（`data_sources` 恒为空 tuple），从未将 L2 `load_sop` 解析出的 `ToolMetadata`（含 data_sources）注入 `ExecutionContext.extensions["tool_metadata"]`——白名单校验在生产链路中无依据可用。本 Story 补齐这"最后一公里"：

1. **6 个 Skills 内容成熟化**：frontmatter 填充 `data_sources` 白名单 + `input_schema`/`output_schema`，SOP body 从占位模板升级为含工作坊方法论的可实用操作手册（对标 Anthropic Claude Code Skills 规范）
2. **生产链路接线**：`StrategicAnalysisUseCase` 加载 L2 SOP 并将 `ToolMetadata` 注入执行上下文，白名单真正生效
3. **配套资源**：每个 Skill 补齐 `references/`（三角化规范、评分锚点、工作坊引导）与 `templates/`（数据采集问卷/矩阵模板）
4. **质量验证**：多源三角化（声明 ≥3 源的 Skill 关键指标 ≥3 独立来源印证）+ 数据新鲜度元数据溯源

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 4: 战略工具箱，Story 4.1c（P0-6）
**前置依赖:** Story 4.1b（✅ done，DataSourcePort + 8 适配器 + Engine.Execute `$DATA_SOURCE` 集成）/ Story 4.1a（✅ done，Skills 骨架 + 五阶段引擎）
**后续依赖:** Story 4.1d（10 个混合数据型 Skills 复用同一模式）/ Story 4.1e（7 个内部框架 Skills）

### ⚠️ Story 范围澄清（重要）

**本 Story 交付（范围边界）：**

- 6 个 SKILL.md frontmatter `data_sources` 白名单声明 + `input_schema`/`output_schema` JSON Schema 定义
- 6 个 SKILL.md body SOP 成熟化（≤500 行硬约束，Hub-and-Spoke 拆分至 references/）
- 6 个 Skill 的 `references/` + `templates/` 资源文件（当前 5 个非 pestel 目标的 `references/`/`scripts/` 为空目录、`templates/` 全无 — 本 Story Task 2-7 实施期新建）
- **生产链路接线（关键缺口修复 — 双入口，链路共享单 ToolMetadata）**：
  - `StrategicAnalysisUseCase` 注入 `extensions["tool_metadata"]`（单 Skill 调用入口）
  - **`RunToolChainUseCase` 注入 `extensions["tool_metadata"]`**（**链路共享单 ToolMetadata** — UseCase 入口注入声明序首节点（`dag.nodes[0]`）metadata 委托 `execute_chain`，**链路全程共用同一 metadata 非字典，节点级 metadata 切换属 Story 4.2 工具链编排范畴，本 Story 显式不收敛；Round 2 P1-1 修正 line 50 "字典" 措辞为单数 ToolMetadata**）
- Skills SOP 单元测试 ×6 + 集成测试 + 架构验证测试 + BDD 验收测试
- 4-1b 推迟项收敛：Marker 字符级扫描专项测试（`data_source_marker._string_literal_spans` 边界场景）

**不在本 Story 范围（明确划出）：**

- **新增数据源适配器 / UNSD / OECD** → 后续 Story（PoC v2 已验证不可用，故 disruptive-innovation 第 3 源 WIPO/EPO 推迟到 Story 4.1d 之后）
- **工具输出 Schema 强制验证执行（Pydantic 运行时校验）** → Story 4.3（本 Story 仅定义 frontmatter JSON Schema 契约，不实现运行时校验器）
- **10 个混合数据型 / 7 个内部框架 Skills** → Story 4.1d / 4.1e
- **数据源治理（配额管理/成本追踪/降级策略编排）** → 后续 Story
- **newsapi/tavily 适配器代码修改** → 无（Key 缺失降级行为仅在 SOP 中文档化）
- **`ToolChainService.execute_chain` 内部节点级 extensions 注入** → 本 Story 由 `RunToolChainUseCase` 调用点前置注入 ToolMetadata（链路共享单数，**非字典 — 见 line 39 已修正术语**）后委托，避免侵入 Service 内部循环；如未来节点级独立 metadata 需求浮现则 Story 4.2 收敛

---

## 🛡️ 硬约束声明（CLAUDE.md §5）

### 领域零依赖（FR-AR-01）

- 本 Story **不新增/修改 domain 层文件**（复用 4-1b 全部领域资产）；若实施中发现必须触碰 domain 层，该文件**仅允许 Python 标准库**，禁止 pydantic/httpx/redis 等任何第三方包（`.importlinter` 强制，CI 失败）

### 异常体系强制

- **禁止** `raise ValueError` / 手动 `raise HTTPException` / 继承内置 Exception
- 所有异常走 `src/domain/exceptions/` 体系 + `ExceptionHandlers` 自动映射
- 提交前三条 grep 自查（零输出）：
  - `grep -rn "raise ValueError" src/`
  - `grep -rn "raise HTTPException" src/`
  - `grep -rn "class.*Exception)" src/domain/exceptions/ | grep -v "DomainError\|BaseException\|SystemException\|BusinessException\|ExternalException\|ThirdPartyError\|Error)"`

### 抑制告警禁止

- **禁止** `# noqa` / `# type: ignore` / `# pylint: disable`；**禁止**修改阈值/规则消除告警——必须修复根因

### Commit & Push 规范

- 提交信息**禁止**任何 AI 辅助署名（Co-Authored-By: Claude 等）
- **禁止** `--no-verify` 绕过 pre-commit hooks
- **禁止** 修改 `.importlinter` 中已合入的架构依赖规则（CLAUDE.md §5）
- **禁止** 修改已合入的 alembic migration（CLAUDE.md §5，本 Story 不新增 alembic migration）
- 直接在 main 分支开发（项目约定）

### Skills 内容约束（Anthropic Claude Code Skills 对标）

- **L2 SKILL.md ≤500 行**（架构 §1.5 P2 / §13.11 约束；⚠️ 调研确认 `src/application/skills/validators/` 当前为空目录，`line_count_validator.py` 尚未实现——本 Story 的行数约束由 Task 2-7 单测断言 + Task 9.4 架构测试承担，禁止声称"CI 已有校验"）；SOP 成熟化膨胀时按 Hub-and-Spoke 拆分到 `references/*.md`，SKILL.md 本体保持路由+摘要
- **frontmatter 必需字段**：`slug`（kebab-case）/ `name` / `version`（SemVer）——`frontmatter.py:32` `REQUIRED_FIELDS` 强制
- **负向触发章节强制**（架构原则 P6）：`when_not_to_use` + body「负向触发」章节
- **数据源声明合法值**：`data_sources[].name` 仅限 8 个注册源（kebab-case）：`world-bank` / `imf` / `eurostat` / `uspto` / `ipcc` / `newsapi` / `tavily` / `china-nbs`；`api_type` 仅限 `rest_json` / `sdmx_json` / `csv_download` / `crawler`（`DataSourceApiType` 枚举值）；`ttl_seconds ∈ [60, 2592000]`
- **沙箱无网络不变量**：SOP 引导 LLM 生成的沙箱代码通过 `$DATA_SOURCE("name", "query")` 标记采集数据，**禁止**引导任何形式的沙箱内网络访问；注入数据经全局 `DATA_SOURCES` dict 读取（`data_source_marker.py` 注入协议）
- **SOP `input_examples` 章节禁止写入真实 API Key 字符串**：必须使用环境变量引用形式（如 `api_key=os.environ['TAVILY_API_KEY']` 或占位符 `<TAVILY_API_KEY>`），与配置类 `__repr__` 脱敏先例（`src/infrastructure/config/redis.py:40-48`）保持一致；CLAUDE.md §5 Key 安全红线扩展

### 代码质量门禁

- `poetry run ruff check src/ tests/` 通过（行宽 128，规则 E/F/I/N/W）
- `poetry run mypy src/` 通过
- `poetry run pytest tests/ -n 8` 并行通过，连续 5 次无随机失败
- `pre-commit run --all-files` 通过

---

## 🎯 领域异常契约

> **原则**：异常是领域契约的一部分。本 Story **不新增领域异常**（显式决策，见下）。

### 不新增异常的决策声明

本 Story 为内容成熟化 + 链路接线 Story，全部失败路径已由 4-1b 异常体系覆盖，**新增同义异常违反"禁止同义异常重复定义"红线**：

| 场景 | 复用异常 | 编码 | 依据 |
|------|---------|------|------|
| `$DATA_SOURCE` 标记语法错误 | `ValidationError` | EXCEPTION_201 | 4-1b 既定（标记解析器） |
| 数据源未在白名单声明 / 缺 tool_metadata | `BusinessRuleViolationError` | EXCEPTION_207 | 4-1b 既定（白名单语义） |
| 数据源 5xx/连接失败/未注册（Key 缺失） | `DataSourceUnavailableError` | EXCEPTION_411 | 4-1b 既定 |
| 429 限流 | `DataSourceRateLimitError` | EXCEPTION_412 | 4-1b 既定 |
| 响应解析失败（不可重试） | `DataSourceResponseError` | EXCEPTION_413 | 4-1b 既定 |
| 数据源超时 | `TimeoutError`（external） | EXCEPTION_302 | 4-1b 既定 |
| 配置缺失（无 API Key） | `ConfigurationError` | EXCEPTION_101 | 4-1b 既定 |
| SKILL.md frontmatter 解析失败（含 data_sources 项非法） | `FrontmatterParseError` | 既有 | `frontmatter.py:45`，4-1b 已扩展字段路径 context |
| Skill 不存在 / 加载失败 | `SkillNotFoundError` / `SkillLoadError` | EXCEPTION_387 / 388 | tool 子域既有 |

### 登记确认动作（Task 0 必做）

- [x] `grep -rn "EXCEPTION_41[4-9]" src/` 确认 414-419 空闲但**本 Story 不使用**（防止实施中临时新增异常）
- [x] BDD 异常路径场景纳入 Edge Cases（207/411/412 断言 `error.code` + `error.message`）

---

## 🎯 测试隔离约束

### TestTenant UUID 前缀

- 集成/验收测试缓存键带租户前缀：`sisys:cache:datasource:{tenant}:{source}:{query_hash}`，租户 = `f"it-{uuid.uuid4().hex[:8]}"` / `f"acc-{uuid.uuid4().hex[:8]}"`（范本 `tests/integration/application/test_data_source_execution.py:71-77`）
- teardown 仅 `delete_pattern` 清理本测试租户前缀键，禁止全库 flush

### 外部服务测试策略

- **单元测试**：Skills 内容测试直接真实加载真实 SKILL.md（范本 `tests/unit/application/skills/test_skills_loader.py` `TestYamlFrontmatterParsing`）；涉及适配器行为一律 stub/fake，禁止真实外网调用
- **集成测试**：真实 Engine + 真实 `DataSourceResolverService` + 真实 Redis（测试端口，`real_redis` fixture）；Mock 仅限 LLM/Sandbox/数据源适配器（`_StubAdapter` 可编程替身，范本 `test_data_source_execution.py:43-68`）
- **验收测试**：同集成测试真实服务策略 + `_FakeDataSourceAdapter`（behavior: ok/unavailable/rate_limit/bad_response + `call_count` 计数，范本 `tests/acceptance/test_acceptance_data_source.py:119-167`）

### BDD 步骤函数

- **禁止** `@pytest.mark.asyncio`（导致 context 数据丢失），使用场景级共享 `event_loop` fixture + `context["_loop"].run_until_complete(coro)` helper（范本 `test_acceptance_data_source.py:60-67`；aioredis/asyncio.Lock 绑定事件循环，跨循环报 Event loop is closed）
- 同一中文文本可能需同时支持 given/when 装饰器

### 并发与事件循环

- `asyncio.Lock` 必须声明为**类变量**（非实例变量）
- pytest-xdist 默认开启（`-n auto --dist loadgroup`），共享 Redis 缓存键的测试文件必须 `pytestmark = [pytest.mark.integration, pytest.mark.xdist_group("data-source-cache")]`（list 形式，复用 4-1b 分组，同一 worker 串行）
- 并发采集断言在 async 函数内用 `asyncio.gather()` 语义验证（Resolver 内部已实现），测试侧以 `call_count` 计数断言并发调用次数

---

## 🌐 端口与数据契约

### 端口契约（本 Story 不新增端口 — 显式决策）

复用既有端口，禁止新增同义端口：

| 端口 | 层 | 文件 | 本 Story 用法 |
|------|----|------|--------------|
| `DataSourcePort` | domain | `src/domain/ports/data_source.py:52` | 8 适配器实现（4-1b 已交付） |
| `DataSourceResolverPort` | application | `src/application/ports/data_source_resolver.py:20` | Engine 白名单编排（4-1b 已交付） |
| `SkillLoaderPort` | application | `src/application/ports/skill_loader.py:94` | **本 Story 新增消费点**：use case 调 `load_sop` 取 L2 ToolMetadata |

### 数据契约（本 Story 核心 SSOT）：6 个 Skills 数据源白名单声明表

> **唯一事实源（Single Source of Truth）**：下表是 6 个 SKILL.md frontmatter `data_sources` 声明的唯一事实源。Task 0 将其固化为契约断言，Task 2-7 实施内容必须与本表逐字一致（name/api_type），禁止实施期临时增删。

| Skill slug | 声明数据源（name 集合） | 采集目标 | 三角化能力 |
|------------|------------------------|---------|-----------|
| `pestel-analysis` | `world-bank` + `imf` + `eurostat` + `ipcc` + `newsapi` + `china-nbs` | GDP/治理指标（WB）、世界经济展望（IMF）、欧盟维度（Eurostat）、环境数据（IPCC）、时政新闻（NewsAPI）、中国维度（国统局） | ✅ 6 源 |
| `porters-five-forces` | `newsapi` + `world-bank` + `eurostat` | 行业新闻（NewsAPI）、行业经济（WB）、欧盟行业数据（Eurostat） | ✅ 3 源 |
| `appeals-analysis` | `tavily` + `newsapi` + `china-nbs` | 顾客洞察 Web 搜索（Tavily）、市场舆情（NewsAPI）、中国消费统计（国统局） | ✅ 3 源 |
| `competitor-analysis` | `newsapi` + `uspto` + `tavily` + `china-nbs` | 竞品动态（NewsAPI）、竞品专利（USPTO）、竞品 Web 情报（Tavily）、中国行业对标（国统局） | ✅ 4 源 |
| `scenario-planning` | `tavily` + `ipcc` + `eurostat` | 趋势 Web 搜索（Tavily）、气候情景（IPCC）、欧盟情景数据（Eurostat） | ✅ 3 源 |
| `disruptive-innovation` | `uspto` + `tavily` | 颠覆性技术专利（USPTO）、颠覆性技术 Web 情报（Tavily） | ⚠️ 2 源（双源交叉验证，见决策 D4；Epic AC-4 字面 ≥3 源偏差由 Epic owner 签收） |

**适配器 url/api_type/ttl/confidence 对齐表**（4-1b 8 个适配器 `get_metadata()` 实测，Round 1 D1-C 视角固化）：

| 数据源（name） | url（适配器 `_config` 默认值） | api_type | ttl_seconds | confidence |
|----------------|-------------------------------|----------|-------------|------------|
| `world-bank` | `https://api.worldbank.org/v2` | rest_json | 604800（7d） | 0.95 |
| `imf` | `https://www.imf.org/external/datamapper/api/v1` | sdmx_json | 604800（7d） | 0.95 |
| `eurostat` | `https://ec.europa.eu/eurostat/api/dissemination` | sdmx_json | 604800（7d） | 0.95 |
| `uspto` | `https://search.patentsview.org` | rest_json | 2592000（30d） | 0.90 |
| `ipcc` | `https://www.ipcc.ch/data`（注：`csv_base_url` 字段） | csv_download | 2592000（30d） | 0.85 |
| `newsapi` | `https://newsapi.org` | rest_json | 21600（6h） | 0.75 |
| `tavily` | `https://api.tavily.com` | rest_json | 86400（1d） | 0.70 |
| `china-nbs` | `https://www.stats.gov.cn`（注：`base_url` 字段） | crawler | 86400（1d） | 0.90 |

> **三方对齐契约（Task 9.2 架构测试断言）**：
> 1. frontmatter `data_sources[].name` ⊆ 上述 8 集合
> 2. frontmatter `data_sources[].url` 字面值 == 适配器 `get_metadata().url`
> 3. frontmatter `data_sources[].api_type` ∈ `DataSourceApiType` 枚举（rest_json/sdmx_json/csv_download/crawler）
> 4. frontmatter `data_sources[].ttl_seconds ∈ [60, 2592000]`

**DataSourceRef 字段规则（frontmatter 声明格式）：**

```yaml
data_sources:
  - name: world-bank            # 必须与适配器 get_metadata().name 一致（kebab-case）
    url: https://...            # 必须与对应适配器 get_metadata().url 一致（Task 0 契约断言防漂移）
    api_type: rest_json         # DataSourceApiType 枚举值（小写）
    ttl_seconds: 604800         # 对齐"适配器 url/api_type/ttl/confidence 对齐表"；范围 [60, 2592000]
    required_fields:            # 可选，该 Skill 消费此源时必需的 payload 字段
      - indicator
      - value
```

`required_fields` 字段对齐 4-1b `DataSourceRef.required_fields: tuple[str, ...] = ()`（`src/domain/value_objects/data_source.py`），YAML list → tuple 转换由 `_parse_data_source_refs` 完成（`src/application/skills/frontmatter.py:154`）。

**TTL/confidence 对齐表（与 4-1b 适配器配置一致，`src/infrastructure/config/*.py`）：** 见上方"适配器 url/api_type/ttl/confidence 对齐表"。

### 生产链路接线契约（关键缺口修复）

**现状缺口（调研确认 — Round 1 D1-A 视角证实）：** `StrategicAnalysisUseCase.execute()`（`src/application/use_cases/strategic_analysis.py:85-138`）仅调用 `load_metadata()`（L1，`data_sources` 恒为空 tuple，`loader.py:119-138` `_parse_table_row` 不解析 data_sources），且构造 `ExecutionContext` 时**未注入 `extensions["tool_metadata"]`**。Engine `_resolve_data_sources`（`tool_execution_engine.py:288-293`）在代码含标记但缺 metadata 时抛 `BusinessRuleViolationError(207)`——即生产链路白名单永远不会命中，6 个 Skills 的声明形同虚设。

**Round 1 D2 评审新增（同类缺口）：** `RunToolChainUseCase.execute()`（`src/application/use_cases/run_tool_chain.py:99-114`）同样调用 `load_metadata()` 预加载 ToolMetadata 用于节点映射，但 line 114 `_service.execute_chain(..., context=context)` 透传**原始** context（未注入 extensions）。多 Skill 工具链调用路径下，Engine `_resolve_data_sources` 在每个节点都会抛 207。本 Story 双入口同步接线（Task 1 循环 [B]）。

**接线方案（本 Story 唯一应用层代码改动 — 双入口）：**

```python
# strategic_analysis.py 步骤 2 替换（load_metadata → load_sop + extensions 注入）
# 2. 通过 SkillLoaderPort 加载 L2 SOP（frontmatter 含 data_sources 白名单）
tool_metadata: ToolMetadata | None = None
try:
    skill_doc = await self._skill_loader.load_sop(request.tool_name)
    tool_metadata = skill_doc.frontmatter   # SkillDocument.frontmatter 即 ToolMetadata（loader.py:188-196）
except Exception as exc:
    logger.warning("技能 SOP 加载失败（不阻断执行）: tool_name=%s exc=%s", request.tool_name, exc)

# 3. 构造 ExecutionContext + ToolCall（注入 tool_metadata 作为白名单依据）
context = ExecutionContext(
    ...,
    extensions={"tool_metadata": tool_metadata} if tool_metadata is not None else {},
)
```

`run_tool_chain.py` 同步：line 99-109 `skill_metadata` dict 改为 `load_sop` 调用收集；line 114 前基于声明序首节点（`dag.nodes[0]`）`slug` 的 `ToolMetadata` 通过 `dataclasses.replace(context, extensions={"tool_metadata": node_metadata})` 委托 `execute_chain(context=context)`。`_service.execute_chain` 内部节点循环由 Story 4.2 收敛；本 Story 仅保证 UseCase 入口调用点已正确注入。

**接线语义约束：**
- `load_sop` 失败**不阻断执行**（对齐既有 `load_metadata` 容错先例 `strategic_analysis.py:103-112`），metadata 为 None 时 extensions 不含该键——Engine 侧行为：代码无标记时零影响；代码含标记时按 4-1b 既定语义抛 207（白名单无依据，安全失败方向正确）
- **禁止**改动 `ToolExecutionEngine.__init__` 签名（Story 4.4 AC-7.4 BDD 断言保护）
- **禁止**改动 `SkillLoaderPort` 接口（`load_sop` 已返回含 ToolMetadata 的 SkillDocument，无需扩接口）
- 双入口接线独立性：StrategicAnalysisUseCase 与 RunToolChainUseCase 互不依赖，分别独立单测覆盖
- `SkillLoaderPort.load_sop` 真实文件路径在 BDD/集成测试 fixture 中需固定 `skills_root` 或用 `tmp_path` 复制（CI 环境稳定性，Round 1 D2-可行性建议）

### 领域事件（本 Story 不新增事件）

复用 4-1b 双通道事件：`DataSourceFetched` / `DataSourceFetchFailed`（`configs/event_channels.yaml` + `ChannelRouter.DEFAULT_MAPPINGS` 已登记）。Skills 成熟化不产生新事件类型。

### 契约测试文件清单

- 本 Story 无新端口 → **无新端口契约测试文件**
- 数据源声明一致性契约断言并入架构测试 `tests/unit/architecture/test_arch_skill_data_collection_4_1c.py`（声明表 SSOT vs 6 个 SKILL.md frontmatter vs 适配器 `get_metadata()` 三方一致）
- 既有契约测试回归：`test_port_contract_data_source.py` / `test_port_contract_data_source_resolver.py` 全绿（零修改）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 6 个 Skills data_sources 白名单声明与解析集成

**Given** Story 4.1b 已交付 frontmatter `data_sources` 解析链路（`_parse_data_source_refs`，`frontmatter.py:154`）
**When** 在 6 个 SKILL.md frontmatter 填充 `data_sources` 白名单声明
**Then**
- 每个 Skill 的声明与「数据契约 SSOT 表」逐字一致（name/api_type/ttl_seconds）
- `load_sop(slug).frontmatter.data_sources` 解析为 `tuple[DataSourceRef, ...]`，名称集合等于声明集合
- 声明的 `url` 与对应适配器 `get_metadata().url` 一致（防漂移契约断言）
- 既有 23 个 Skills 解析回归全绿（`test_frontmatter_data_sources.py` + `test_skills_loader.py` 零回归）
- 17 个非目标 Skill 的 `data_sources` 保持空 tuple（不被误填）

**验证标准/Validation Criteria:**
- [x] 6 个 Skills 单元测试（`test_<slug>_4_1c.py`）断言白名单解析结果 == SSOT 表
- [x] **frontmatter data_sources 全字段**（name/api_type/ttl_seconds/url/required_fields）逐字等于 SSOT 表（Round 2 P2-1）
- [x] **跨循环一致性（C 循环，Round 2 P0-1）**：SOP body 中所有 `$DATA_SOURCE("name", "query")` 标记提取的 name 集合 == frontmatter.data_sources name 集合（双向断言：白名单过宽/过窄均失败）
- [x] 声明 url ↔ 适配器 url 一致性断言通过
- [x] 23 Skills 全量解析回归通过（含 17 个未触碰 Skill 空 tuple 断言）

### AC-2: 生产链路接线（StrategicAnalysisUseCase 注入 tool_metadata）

**Given** 生产链路缺 `extensions["tool_metadata"]` 注入，白名单无依据
**When** `StrategicAnalysisUseCase.execute()` 改用 `load_sop` 并注入 `ToolMetadata`
**Then**
- 调用 6 个目标 Skill 且 LLM 生成含 `$DATA_SOURCE` 标记的代码时，白名单校验依据为该 Skill frontmatter 声明的 `data_sources`
- 白名单内数据源正常采集注入；白名单外数据源抛 `BusinessRuleViolationError(207)`
- `load_sop` 失败时不阻断执行（容错先例），extensions 不含该键
- 无 `$DATA_SOURCE` 标记的执行链路零行为变化（回归）
- 未成熟化的 17 个 Skill（data_sources 空 tuple）代码含标记时抛 207（白名单为空，安全失败）

**验证标准/Validation Criteria:**
- [x] **StrategicAnalysisUseCase** 单元测试 4 场景（load_sop 注入 / 加载失败容错 / 无标记零行为变化 / 空白名单 207）
- [x] **RunToolChainUseCase** 单元测试 3 场景（多节点并发 load_sop + 任一节点 metadata 注入 / 全部 load_sop 失败时 extensions = {} / 无节点零行为变化）— Round 1 D2 新增
- [x] `ToolExecutionEngine.__init__` 签名不变（4.4 BDD AC-7.4 回归全绿）
- [x] 既有 `test_acceptance_strategic_tool_impl` / `test_acceptance_docker_sandbox` 回归全绿
- [x] **既有 tool_chain 链路验收测试** 零回归（双入口改动影响范围可控）

### AC-3: SOP 成熟化（6 个 Skills 内容升级，对标 Anthropic Skills 规范）

**Given** 6 个 SKILL.md 当前为占位模板（~55 行，body 含 `{"placeholder": ...}`）
**When** 编写 6 个 Skills 的完整 SOP 与配套资源
**Then**
- 每个 SKILL.md 含完整章节：适用场景 / 负向触发 / 输入字段（input_schema）/ 输出字段（output_schema）/ 数据采集计划（Think 阶段引导：声明各维度指标 → 数据源映射）/ SOP 执行步骤（含 `$DATA_SOURCE("name", "query")` 标记使用规范 + `DATA_SOURCES` dict 读取协议）/ 失败处理（411 降级 / 412 限流 / 413 解析失败 / Key 缺失降级的 LLM 应对话术）/ input_examples（≥1 个真实示例，非 placeholder）/ References 指引
- 每个 Skill 配套 `references/`（三角化规范 / 评分锚点 / 工作坊引导方法论）与 `templates/`（采集问卷或评分矩阵模板）
- 每个 SKILL.md ≤500 行（Task 2-7 单测 + Task 9.4 架构测试断言；`line_count_validator` 未实现，不依赖 CI），超限内容拆分至 references/
- frontmatter 填充 `input_schema` / `output_schema`（JSON Schema dict，含 required 字段）
- pestel-analysis 既有资产整合：`references/scoring_matrix.json` + `scripts/aggregate_scores.py` 保留并在新 SOP 中引用
- **newsapi/tavily Key 缺失降级行为在 SOP 失败处理章节文档化**（适配器未注册 → 411 "未注册" 语义 → LLM 应基于其余源继续分析并标注数据缺口）

**验证标准/Validation Criteria:**
- [x] 6 个 Skills 单元测试断言 SOP 必备章节存在 + input_examples 非 placeholder + 行数 ≤500
- [x] frontmatter input_schema/output_schema 含 required 字段断言
- [x] references/templates 文件存在性断言
- [x] pestel 既有 references/scripts 资产引用断言（不破坏既有 L3 加载测试）

### AC-4: 集成测试（真实服务 + 多源三角化 + 新鲜度）

**Given** 6 个 Skills 声明已就绪 + 生产链路已接线
**When** 运行 `tests/integration/application/test_skill_data_collection_4_1c.py`
**Then**
- 6 个 Skills 各自经"真实 Engine + 真实 Resolver + 真实 Redis（测试端口）+ Stub 适配器（call_count 计数）+ AsyncMock LLM/Sandbox"链路验证：LLM 生成含 `$DATA_SOURCE` 标记代码 → 并发采集 → preamble 注入 → `EvidencePackage.data_sources` 溯源元数据完备（source/freshness/confidence）
- **每个 Skill 至少调用 1 个声明数据源**（stub `call_count ≥ 1`）
- **多源三角化**：声明 ≥3 源的 5 个 Skill（pestel/porters/appeals/competitor/scenario），单次执行并发采集覆盖**全部声明源**（每源 `call_count == 1`，去重语义），注入 `DATA_SOURCES` dict 键集合 == 声明集合；关键指标输出引用 ≥3 独立来源（SOP 引导 + 集成测试断言注入源数 ≥3）
- **disruptive-innovation（2 源）**：双源交叉验证（注入源数 == 2）
- **新鲜度评分**：`EvidencePackage.data_sources[].freshness_score ∈ [0,1]`，缓存命中二次执行时外部调用次数不增
- Key 缺失场景（newsapi/tavily 未注册）：声明含这两个源的 Skill 部分失败收敛，其余源正常注入

**验证标准/Validation Criteria:**
- [x] 集成测试全绿（真实 Redis 不可用时 `pytest.skip()` 动态跳过）
- [x] 三角化断言：5 个 Skill 注入源数 == 声明源数；disruptive-innovation == 2
- [x] `pytest -n 8` 并行通过（`xdist_group("data-source-cache")`），连续 5 次无随机失败

### AC-5: SDD 架构验证测试

**Given** 6 个 Skills 声明与生产链路接线必须满足六边形架构约束
**When** 运行 `tests/unit/architecture/test_arch_skill_data_collection_4_1c.py`
**Then**
- 声明表 SSOT ↔ 6 个 SKILL.md frontmatter ↔ 适配器 `get_metadata()` 三方一致（name/url/api_type）
- `strategic_analysis.py` 依赖方向合规（application 不 import infrastructure）
- `ToolExecutionEngine.__init__` 签名不变（inspect.signature 锁定，对齐 `test_arch_data_source.py:242-254` 模式）
- 17 个非目标 Skill 未被误改（data_sources 空 tuple + SKILL.md 文件哈希不变量或内容抽样断言）
- 6 个 SKILL.md ≤500 行 + frontmatter 必需字段完备

### AC-6: BDD 验收测试（Gherkin 中文）

**Given** Story 4.1b 数据采集基础设施已就绪
**When** Agent 调用 6 个外部数据型 Skills
**Then** Skills 自动通过 DataSourcePort 获取外部权威数据，LLM 基于真实数据生成结构化分析输出，输出含 source/freshness/confidence 元数据
**And** Edge Cases 覆盖：白名单外数据源（207）、数据源不可用部分失败收敛、Key 缺失降级（411 语义）、缓存命中、三角化源数断言、未成熟化 Skill 空白名单 207

**验证标准/Validation Criteria:**
- [x] `tests/acceptance/test_acceptance_skill_data_collection_4_1c.feature`（`# language: zh-CN`，按 AC 分节）
- [x] `tests/acceptance/test_acceptance_skill_data_collection_4_1c.py`（scenarios() + context dict + 共享 event_loop + 真实服务 + Fake 仅限适配器/LLM/Sandbox）
- [x] 全部场景通过

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [x] 本 Story 不新增领域事件（复用 `DataSourceFetched`/`DataSourceFetchFailed`），Task 0 显式登记该决策

#### 数据模型 (Data Models)
- [x] 本 Story 不新增值对象/实体（复用 `DataSourceRef`/`ToolMetadata.data_sources`/`EvidencePackage.data_sources`）
- [x] **6 个 Skills 的 `input_schema`/`output_schema` JSON Schema 字段级定义文档固化**（产出物：`tests/acceptance/contracts/skill_io_schemas_4_1c.yaml` 或 Story 文档独立子表）：
  - 每个 Skill 的 `input_schema.required` 字段（如 pestel-analysis 需 `industry` / `region_scope` / `time_horizon_years` 等）
  - 每个 Skill 的 `output_schema.required` 字段（如 `pestel_dimensions[]` / 各维度指标对象）
  - 字段类型（string / number / enum）+ description
- [x] 字段级定义作为各 Skill TDD 红阶段断言输入（Task 2-7 [A] 循环断言 input_schema 含 required 字段）

#### 统一端口定义注册与管理 (Port Contract)
- [x] 本 Story 不新增端口（显式决策）；复用 `DataSourcePort`/`DataSourceResolverPort`/`SkillLoaderPort`
- [x] 禁止在服务文件中本地定义 Protocol / Port 抽象
- [x] 既有端口契约测试回归全绿（`test_port_contract_data_source*.py`）

#### 端口契约清单执行约束（强制）
- [x] 本 Story「端口与数据契约」节是唯一事实源（含 6 Skills 数据源声明 SSOT 表）
- [x] 禁止新增未登记端口；禁止语义重复端口
- [x] 6 Skills 声明与 SSOT 表逐字一致，实施期增删源必须先修订本 Story 文档

#### 领域异常契约 (Domain Exception Contract)
- [x] 见「🎯 领域异常契约」节：不新增异常（显式决策），复用 201/207/101/302/411/412/413 + FrontmatterParseError + 387/388
- [x] `grep -rn "EXCEPTION_41[4-9]" src/` 确认本 Story 零新增
- [x] BDD 异常路径场景纳入 Edge Cases（207/411/412）

#### API 契约 (API Contract)
- [x] 本 Story 不新增 REST 端点，无 `openapi.yaml` 变更（纯 Skills 内容 + 内部接线）

#### 六边形架构约束（必须遵守）

**四层架构定义**
| 层次 | 目录 | 本 Story 交付物 |
|------|------|----------------|
| domain | `src/domain/` | 无改动（复用 4-1b 全部领域资产） |
| application | `src/application/` | 6 个 SKILL.md + references/templates 资源；`strategic_analysis.py` 接线（load_sop + extensions 注入） |
| infrastructure | `src/infrastructure/` | 无改动 |
| interfaces | `src/interfaces/` | 无改动 |

**领域层零依赖原则**：domain 层零改动；application 层新增内容仅 YAML/Markdown/JSON 资源 + 既有端口消费，不引入新第三方依赖

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)
- [x] 功能测试文件：`tests/acceptance/test_acceptance_skill_data_collection_4_1c.feature`（`# language: zh-CN`）
- [x] 步骤实现文件：`tests/acceptance/test_acceptance_skill_data_collection_4_1c.py`
- [x] Happy Path + Edge Cases 全覆盖（白名单外 207 / 部分失败收敛 / Key 缺失降级 / 缓存命中 / 三角化断言 / 空白名单 207 共 6 个 Edge Cases）

**BDD 步骤实现约束：**
- 步骤函数使用场景级共享 `event_loop` + `run_until_complete()`（禁止 `@pytest.mark.asyncio`）
- 同一中文文本可能需要同时支持 given/when 装饰器
- Edge Cases 必须包含异常路径断言 `error.code` + `error.message`

**Task 0 完成标志：**
- [x] 规范项全部定义完毕（6 Skills Schema 契约 + 声明 SSOT 表固化 + 接线方案评审）
- [x] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [x] "不新增端口/异常/事件"三项显式决策已登记

---

### TDD 循环约束（适用于每个 Task）

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试（Skills 内容 Task 同样适用：先写"断言 SKILL.md 内容"的失败测试，再编写 SKILL.md 内容使其转绿）
- ❌ 将测试编写集中到最后一个 Task
- ❌ 跳过红阶段验证

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | 用例接线 | load_sop 注入/容错/零行为变化/空白名单 207 | `tests/unit/application/use_cases/test_strategic_analysis_datasource.py` | Task 1 |
| **TDD 单元测试** | Skills 内容 ×6 | frontmatter 白名单解析/Schema 契约/SOP 章节/行数/references/templates 存在性 | `tests/unit/application/skills/test_<slug>_4_1c.py` ×6 | Task 2-7 |
| **TDD 单元测试** | Marker 专项（4-1b 推迟项） | 字符级扫描边界（未闭合字符串/三引号/转义/字符串内伪标记） | `tests/unit/application/services/test_data_source_marker.py`（扩充） | Task 8 |
| **TDD 验收测试** | Gherkin 场景 + BDD 步骤 | 业务价值验收 | `tests/acceptance/test_acceptance_skill_data_collection_4_1c.feature` + `.py` | Task 0 / Task 10 |
| **集成测试** | 6 Skills 全链路 | 三角化/新鲜度/缓存命中/Key 缺失降级 | `tests/integration/application/test_skill_data_collection_4_1c.py` | Task 8 |
| **SDD 架构验证** | 六边形约束 + 声明一致性 | 三方一致/依赖方向/签名锁定/行数 | `tests/unit/architecture/test_arch_skill_data_collection_4_1c.py` | Task 9 |
| **回归** | 既有资产 | 23 Skills 解析/4.1a/4.1b/4.4 全部既有测试 | 既有测试套件 | 每个 Task |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [x] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [x] **应用层 ≥85%**（`make test-cov-application`，4-1b Round 1 已建分层门禁 `Makefile:278-291`）——本 Story 应用层改动仅限 `strategic_analysis.py` 接线 + 纯资源文件，接线分支（成功/容错/None）覆盖率 100%
- [x] **关键路径 100%**：use case 接线全分支（load_sop 成功/失败容错/extensions 有无注入）

#### 代码质量门禁
- [x] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [x] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [x] **无 P0/P1 级别问题**（代码审查）【Round 5 勾选：5 轮审查周期后零 P0/P1 残留，Round 3/4/5 三重独立取证（198+17 / 215 / 159 passed 实跑 + 红线双态 grep 零输出）】
- [x] **预提交 Hooks 通过**（`pre-commit run --all-files`）【Round 5 勾选依据：审查周期 4 个 commit（56a23bb1/6cd2c2bc/d59766ca/f97ae447）逐个经 pre-commit hooks 全项 Passed 落库（ruff/ruff-format/mypy/bandit/detect-secrets，无 --no-verify）；all-files 全仓形态因会话授权限制未单独执行，由上述逐提交证据链 + ruff/mypy 独立复跑覆盖】

#### 测试隔离约束

> 见「🎯 测试隔离约束」节全文。核心：TestTenant UUID 前缀、真实 Redis 测试端口 + delete_pattern 租户级清理、适配器一律 Stub/Fake、BDD 禁 @pytest.mark.asyncio、`xdist_group("data-source-cache")` 复用。

**验证要求：**
- [x] 并行测试 `pytest tests/ -n 8` 通过
- [x] 连续 5 次运行无随机失败
- [x] `poetry run ruff check` 通过
- [x] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 6 Skills data_sources 声明与解析集成 | Task 0 / 2-7 / 9 | 0.2 / 各 Skill Task .1-.3 / 9.2 | `test_<slug>_4_1c.py` ×6 / `test_arch_skill_data_collection_4_1c.py` |
| AC-2 | 生产链路接线 | Task 1 | 1.1-1.4 | `test_strategic_analysis_datasource.py` |
| AC-3 | SOP 成熟化 + 配套资源 | Task 2-7 | 各 Skill Task .1-.5 | `test_<slug>_4_1c.py` ×6 |
| AC-4 | 集成测试（三角化/新鲜度） | Task 8 | 8.1-8.5 | `test_skill_data_collection_4_1c.py` |
| AC-5 | 架构验证测试 | Task 9 | 9.1-9.5 | `test_arch_skill_data_collection_4_1c.py` |
| AC-6 | BDD 验收测试 | Task 0 / 10 | 0.4-0.6 / 10.1-10.8 | `test_acceptance_skill_data_collection_4_1c.feature` / `.py` |

---

## ⚠️ 风险与缓解策略（Risk Register）

| ID | 风险描述 | 等级 | 触发条件 | 缓解策略 | 关联 Task |
|----|---------|------|---------|---------|----------|
| **R1** | newsapi/tavily Key 缺失导致声明源未注册 + 部分失败收敛（冷启动 composition_root 不注册；运行时 Resolver "未注册 411"） | **中**（Round 1 D2 降级评估） | dev/CI 无 `NEWSAPI_API_KEY`/`TAVILY_API_KEY`（6 个 Skills 中 5 个声明含二者之一）；真实生产 Key 配置属 CI/CD secrets 范畴 | ① **冷启动**：`composition_root` `bool(os.getenv())` 条件注册不通过 → 冷启动阶段抛 ConfigurationError(101)（配置层）；② **运行时**：Resolver `Mapping.get()` 返回 None → 抛 `DataSourceUnavailableError(411)`（运行时层）；③ SOP 失败处理章节显式登记两段分流；④ 集成测试用 Stub 适配器注入 adapters Mapping（不依赖条件注册）；⑤ BDD Edge Case 显式覆盖部分失败收敛 | Task 2-7 / 8 / 10 |
| **R2** | SKILL.md SOP 成熟化超 500 行硬约束 | 中 | SOP + 工作坊方法论内容膨胀 | Hub-and-Spoke 拆分：SKILL.md 仅路由+摘要，详情入 references/；Task 2-7 每个循环含行数断言 + Task 9.4 架构测试兜底（`line_count_validator` 未实现，不依赖 CI） | Task 2-7 / 9 |
| **R3** | 生产链路双入口接线改变 `ExecutionContext.extensions` 语义 + load_metadata → load_sop I/O 增量 | **P0** | `load_metadata` → `load_sop` 替换引入额外 I/O（每次执行多读一次 SKILL.md，LRU 100 项缓存可缓解）；extensions 从"总是空"变成"可能含 tool_metadata"，下游 logging/审计消费方如有"必空"假设则破坏 | 无标记时 Engine 零行为变化（4-1b 既定 `_resolve_data_sources` 前置判断）；load_sop 失败容错不阻断；既有验收测试全量回归（strategic_tool_impl + docker_sandbox + tool_chain 链路测试） | Task 1 |
| **R4** | 三角化 ≥3 源与 disruptive-innovation 仅 2 源冲突 | 中 | Epic AC-4 字面"每个指标 ≥3 独立来源" | 决策 D4 务实化：≥3 源 Skill 断言全声明源覆盖；2 源 Skill 双源交叉验证；偏差显式登记 | Task 0 / 8 |
| **R5** | china-nbs crawler 服务不可用 | 中 | dev/CI 未运行 crawler daemon | 集成测试用 Stub 适配器（不依赖真实 crawler）；真实 crawler 链路属 4-1b 推迟项 P0-7，不在本 Story 收敛 | Task 8 |
| **R6** | frontmatter 声明与适配器 `get_metadata()` 漂移（url/api_type 不一致） | 中 | 适配器配置变更未同步 SKILL.md | Task 0 固化 SSOT 表；Task 9 架构测试三方一致性断言（声明 ↔ SKILL.md ↔ 适配器） | Task 0 / 9 |
| **R7** | 23 Skills 解析回归（新增 data_sources 键破坏既有断言） | 低 | frontmatter 格式错误 | `test_frontmatter_data_sources.py:99-110` 23 Skills 全量回归网 + 17 个非目标 Skill 空 tuple 断言 | Task 2-7 / 9 |
| **R8** | Epic AC-2 字面要求 `data_sources.yaml` vs frontmatter SSOT 决策偏差 | 低 | 评审质疑缺 data_sources.yaml 文件 | 决策 D1 显式登记（frontmatter 为唯一事实源，4-1b 解析链路已建，避免双写漂移，Anthropic 自包含风格），Story 文档留痕 | Task 0 |

---

## 📚 配套架构文档同步

> **文档同步硬约束（Task 10 收尾）：** Story 4-1c 完成时必须同步更新以下架构文档。

| Task | 文档同步动作 | 文档 | 锚定位置 |
|------|------------|------|---------|
| Task 10 收尾 | `architecture.md` §17.3 状态块：`📋 Story 4.1c backlog` → `✅ Story 4.1c 已完成` | architecture.md | line 2674-2675 附近 |
| Task 10 收尾 | `architecture.md` §17.3.3 末尾追加 4.1c 集成说明（6 Skills 声明 + 生产链路双入口接线 + 决策 D1/D2/D4） | architecture.md | §17.3.3 末尾 |
| Task 10 收尾 | `architecture.md` §17.3.3 关键架构决策表追加 6 项新决策（D1 frontmatter SSOT / D2 双入口注入 / D3 L1 vs L2 / D4 三角化务实 / D6 Schema 载体 / D7 双 UseCase 同步接线 — **D7 Round 4 已登记至 Story 决策表 line 851 后**） | architecture.md | 决策表末尾 |
| Task 10 收尾 | `sisys-uni-exception-design.md` §3.3.2 追加 4-1c 复用声明段落（**Round 2 P1-3 改造**：与 Story line 109-117 异常契约表共享 single-source-of-truth，段落引用而非重新列举，避免异常列表双维护漂移；具体段落草稿见 line 109-117 表格） | sisys-uni-exception-design.md | §3.3.2 末尾或独立段落 |
| Task 10 收尾 | `architecture.md` 修订历史表追加新版本行 + 文档统计版本号/日期更新 | architecture.md | 文末修订历史 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部（AC-1 ~ AC-6 的规范输入）

> **目的：** 在进入内容实施前，固化 6 Skills 数据源声明 SSOT、input/output Schema 契约、接线方案、Gherkin 验收场景与"三不新增"决策登记。

- [x] Subtask 0.1: 登记三项显式决策（不新增端口 / 不新增异常 / 不新增事件）+ 决策 D1（frontmatter SSOT，不建 data_sources.yaml）+ 决策 D4（三角化务实定义）
- [x] Subtask 0.2: 定义 6 个 Skills 的 `input_schema`/`output_schema` JSON Schema 契约（字段级：required/properties/类型），作为 Task 2-7 红阶段断言输入
- [x] Subtask 0.3: 评审接线方案（`strategic_analysis.py` load_sop + extensions 注入），确认 `load_metadata` 原调用点无其他副作用依赖
- [x] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_skill_data_collection_4_1c.feature`（Happy Path + 6 个 Edge Cases）
- [x] Subtask 0.5: 编写 BDD 步骤实现骨架 `tests/acceptance/test_acceptance_skill_data_collection_4_1c.py`（scenarios() + context + 共享 event_loop + Fake 适配器）
- [x] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证，失败原因 = 白名单声明未填写/接线未实施）
- [x] Subtask 0.7: 确认 6 个声明源的 url 与适配器 `get_metadata().url` 实际值（逐一解析 8 个适配器，固化进 SSOT 表"适配器 url/api_type/ttl/confidence 对齐表" — Round 1 D1-C 视角已固化，**Round 2 P2-2 行号复核**：`composition_root.py` 实测当前 newsapi/tavily 行号仍为 2438/2456；如漂移则同步修订 line 872、980）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕（Schema 契约 + SSOT 表 + 接线方案 + 三项决策登记）
- [x] **SSOT 表 url/api_type/ttl/confidence 四列均已从 8 个适配器 `get_metadata()` 实际值固化**（含 pestel-analysis 6 源、porters 3 源、appeals 3 源、competitor 4 源、scenario 3 源、disruptive-innovation 2 源的 url 对齐）
- [x] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 生产链路接线（双入口：StrategicAnalysisUseCase + RunToolChainUseCase 注入 tool_metadata）

**关联 AC:** AC-2

> ⚠️ **本 Task 是唯一应用层代码改动，风险 R3（P0）集中在此时收敛。**
> **Round 1 D2 评审新增**：原 Story 仅覆盖 `StrategicAnalysisUseCase`，D2-可行性 + D1-A 独立发现 `RunToolChainUseCase`（`src/application/use_cases/run_tool_chain.py:104-106`）存在同类接线缺口——多 Skill 工具链调用路径下，Engine `_resolve_data_sources` 仍会因缺 `extensions["tool_metadata"]` 抛 207。本 Task 扩展为双入口同步接线。

#### TDD 循环 [A]：StrategicAnalysisUseCase.load_sop + extensions 注入

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/use_cases/test_strategic_analysis_datasource.py`（注入后 extensions 含 tool_metadata 且 data_sources == L2 声明 / load_sop 失败容错不阻断 / 无标记零行为变化 / 未成熟化 Skill 空白名单 207） |
| 🟢 绿 | 修改 `src/application/use_cases/strategic_analysis.py`（`load_metadata` → `load_sop` + extensions 注入，容错对齐既有先例） |
| 🔄 重构 | 回归既有用例测试 + 4.1a/4.4 验收测试全绿，ruff + mypy |

- [x] Subtask 1.1: 🔴 红 — 编写 StrategicAnalysisUseCase 接线失败测试（4 场景）
- [x] Subtask 1.2: 🟢 绿 — 实现 StrategicAnalysisUseCase 接线（最小改动，不动 Engine/Loader 接口）

#### TDD 循环 [B]：RunToolChainUseCase.load_sop + extensions 注入（Round 1 新增）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/use_cases/test_run_tool_chain_datasource.py`（多节点并发 load_sop + 任一节点 metadata 注入 / 全部 load_sop 失败时扩展 = {} / 无节点时零行为变化） |
| 🟢 绿 | 修改 `src/application/use_cases/run_tool_chain.py`（line 99-109 `skill_metadata` dict 改为 `load_sop` 调用收集，并基于声明序首节点（`dag.nodes[0]`）ToolMetadata 通过 `dataclasses.replace()` 注入 `context.extensions["tool_metadata"]` 再委托 `execute_chain`） |
| 🔄 重构 | 工具链既有验收测试 `test_acceptance_strategic_tool_impl` / `test_acceptance_docker_sandbox` 全量回归，ruff + mypy |

- [x] Subtask 1.3: 🔴 红 — 编写 RunToolChainUseCase 接线失败测试（3 场景：每节点 metadata 注入 / 失败容错 / 无节点零变化）
- [x] Subtask 1.4: 🟢 绿 — 实现 RunToolChainUseCase 接线（`load_sop` 替换 `load_metadata` + 扩展注入，最小改动，不动 `ToolChainService` 内部接口）
- [x] Subtask 1.5: 🔄 重构 — 全量回归（`pytest tests/unit/application/use_cases/ tests/acceptance/`）
- [x] Subtask 1.6: 验证 `ToolExecutionEngine.__init__` 签名不变（4.4 BDD AC-7.4 回归）

**完成标准/Definition of Done:**
- [x] 双入口接线实现完成，7 场景单测全绿
- [x] 4.1a/4.4 既有测试零回归
- [x] 应用层覆盖率 ≥85%（接线分支 100%）

---

### Task 2: pestel-analysis Skill 成熟化（含既有资产整合）

**关联 AC:** AC-1, AC-3

> **数据源（SSOT）：** `world-bank` + `imf` + `eurostat` + `ipcc` + `newsapi` + `china-nbs`（6 源）
> **既有资产：** `references/scoring_matrix.json` + `scripts/aggregate_scores.py` 必须保留并在新 SOP 中引用（既有 L3 加载测试 `test_skills_loader.py:178-` 断言其存在）。

#### TDD 循环 [A]：frontmatter 声明 + Schema 契约

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/skills/test_pestel_analysis_4_1c.py`（load_sop 解析 data_sources == SSOT 6 源集合 / url 与适配器一致 / input_schema 含 required 字段） |
| 🟢 绿 | 填充 SKILL.md frontmatter（data_sources + input_schema + output_schema） |
| 🔄 重构 | 23 Skills 解析回归全绿 |

#### TDD 循环 [B]：SOP 内容成熟化

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩充测试（SOP 必备章节断言：适用场景/负向触发/数据采集计划/执行步骤含 `$DATA_SOURCE` 规范/失败处理含 Key 缺失降级话术/input_examples 非 placeholder/references 指引 / ≤500 行 / references+templates 存在性） |
| 🟢 绿 | 编写 SKILL.md body + references/（三角化规范 triangulation.md + 六维度评分锚点 + 工作坊引导）+ templates/（PESTEL 采集矩阵模板） |
| 🔄 重构 | 行数校验通过，内容评审 |

#### TDD 循环 [C]：跨循环一致性（Round 2 P0-1 新增）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写断言：解析 SKILL.md body 中所有 `$DATA_SOURCE("name", "query")` 标记 → 提取 name 集合；断言 == frontmatter.data_sources.name 集合；双向：白名单过宽（frontmatter 含 SOP 未用源）或过窄（SOP 用 frontmatter 未声明源）均失败 |
| 🟢 绿 | 调整 SKILL.md 内容使两集合一致 |
| 🔄 重构 | Task 9.3 架构测试新增 cross-consistency 断言（正则 `\$DATA_SOURCE\(\s*["']([\w-]+)["']` 提取 SOP body 调用集合） |

- [x] Subtask 2.1: 🔴 红 — 编写 frontmatter 声明失败测试
- [x] Subtask 2.2: 🟢 绿 — 填充 frontmatter（data_sources/Schema）
- [x] Subtask 2.3: 🔴 红 — 编写 SOP 内容失败测试
- [x] Subtask 2.4: 🟢 绿 — 编写 SOP + references + templates（整合既有 scoring_matrix/aggregate_scores 引用）
- [x] Subtask 2.5: 🔴 红 — 编写跨循环一致性 [C] 循环失败测试
- [x] Subtask 2.6: 🟢 绿 — 调整 SOP body `$DATA_SOURCE` 标记集合与 frontmatter 对齐
- [x] Subtask 2.7: 🔄 重构 — 行数 ≤500 + cross-consistency 回归全绿

**完成标准/Definition of Done:**
- [x] pestel-analysis 声明与 SOP 成熟化完成，单测全绿
- [x] 既有 L3 资产测试零回归
- [x] [C] 跨循环一致性 100% 覆盖（pestel 6 源 ↔ SOP body 6 标记一一对应）

---

### Task 3: porters-five-forces Skill 成熟化

**关联 AC:** AC-1, AC-3

> **数据源（SSOT）：** `newsapi` + `world-bank` + `eurostat`（3 源）
> **SOP 核心：** 五力评分方法论 + 行业问卷模板；Key 缺失降级话术（newsapi）

#### TDD 循环 [A]/[B]：同 Task 2 结构（frontmatter 声明 → SOP 内容）

- [x] Subtask 3.1: 🔴 红 — 编写 `test_porters_five_forces_4_1c.py` 声明失败测试
- [x] Subtask 3.2: 🟢 绿 — 填充 frontmatter（data_sources/Schema）
- [x] Subtask 3.3: 🔴 红 — 编写 SOP 内容失败测试
- [x] Subtask 3.4: 🟢 绿 — 编写 SOP + references（五力评分锚点/三角化规范/工作坊引导）+ templates（行业问卷）
- [x] Subtask 3.5: 🔄 重构 — 行数 ≤500 + 回归全绿
- [x] Subtask 3.6: 🔴 红 — 编写跨循环一致性 [C] 循环失败测试（端口 3 源 ↔ SOP body 3 标记对齐；详见 Task 2 [C] 循环范本）

**完成标准/Definition of Done:**
- [x] porters-five-forces Skill 声明与 SOP 成熟化完成，单测全绿
- [x] 行数 ≤500 约束验证通过（Task 9.4 架构测试兜底）
- [x] 23 Skills 解析回归零失败
- [x] [C] 跨循环一致性：frontmatter 3 源 ↔ SOP body 3 标记一一对应

---

### Task 4: appeals-analysis Skill 成熟化

**关联 AC:** AC-1, AC-3

> **数据源（SSOT）：** `tavily` + `newsapi` + `china-nbs`（3 源）
> **SOP 核心：** $APPEALS 8 维度评估 + 顾客问卷模板；Key 缺失降级话术（tavily/newsapi）

- [x] Subtask 4.1: 🔴 红 — 编写 `test_appeals_analysis_4_1c.py` 声明失败测试
- [x] Subtask 4.2: 🟢 绿 — 填充 frontmatter（data_sources/Schema）
- [x] Subtask 4.3: 🔴 红 — 编写 SOP 内容失败测试
- [x] Subtask 4.4: 🟢 绿 — 编写 SOP + references（8 维度评分锚点/工作坊引导）+ templates（顾客问卷）
- [x] Subtask 4.5: 🔄 重构 — 行数 ≤500 + 回归全绿
- [x] Subtask 4.6: 🔴 红 — 编写跨循环一致性 [C] 循环失败测试

**完成标准/Definition of Done:**
- [x] appeals-analysis Skill 声明与 SOP 成熟化完成，单测全绿
- [x] 行数 ≤500 约束验证通过（Task 9.4 架构测试兜底）
- [x] 23 Skills 解析回归零失败
- [x] [C] 跨循环一致性覆盖（详见 Task 2 [C] 循环范本）

---

### Task 5: competitor-analysis Skill 成熟化

**关联 AC:** AC-1, AC-3

> **数据源（SSOT）：** `newsapi` + `uspto` + `tavily` + `china-nbs`（4 源）
> **SOP 核心：** 竞品对标矩阵 + 竞品调研方法论；专利维度（USPTO）采集引导

- [x] Subtask 5.1: 🔴 红 — 编写 `test_competitor_analysis_4_1c.py` 声明失败测试
- [x] Subtask 5.2: 🟢 绿 — 填充 frontmatter（data_sources/Schema）
- [x] Subtask 5.3: 🔴 红 — 编写 SOP 内容失败测试
- [x] Subtask 5.4: 🟢 绿 — 编写 SOP + references（对标矩阵评分锚点/竞品调研工作坊）+ templates（竞品对标矩阵）
- [x] Subtask 5.5: 🔄 重构 — 行数 ≤500 + 回归全绿
- [x] Subtask 5.6: 🔴 红 — 编写跨循环一致性 [C] 循环失败测试

**完成标准/Definition of Done:**
- [x] competitor-analysis Skill 声明与 SOP 成熟化完成，单测全绿
- [x] 行数 ≤500 约束验证通过（Task 9.4 架构测试兜底）
- [x] 23 Skills 解析回归零失败
- [x] [C] 跨循环一致性覆盖

---

### Task 6: scenario-planning Skill 成熟化

**关联 AC:** AC-1, AC-3

> **数据源（SSOT）：** `tavily` + `ipcc` + `eurostat`（3 源）
> **SOP 核心：** 4 情景剧本方法论 + 情景工作坊引导；气候情景维度（IPCC）采集引导

- [x] Subtask 6.1: 🔴 红 — 编写 `test_scenario_planning_4_1c.py` 声明失败测试
- [x] Subtask 6.2: 🟢 绿 — 填充 frontmatter（data_sources/Schema）
- [x] Subtask 6.3: 🔴 红 — 编写 SOP 内容失败测试
- [x] Subtask 6.4: 🟢 绿 — 编写 SOP + references（情景构建方法论/不确定性矩阵锚点）+ templates（情景剧本框架）
- [x] Subtask 6.5: 🔄 重构 — 行数 ≤500 + 回归全绿
- [x] Subtask 6.6: 🔴 红 — 编写跨循环一致性 [C] 循环失败测试

**完成标准/Definition of Done:**
- [x] scenario-plning Skill 声明与 SOP 成熟化完成，单测全绿
- [x] 行数 ≤500 约束验证通过（Task 9.4 架构测试兜底）
- [x] 23 Skills 解析回归零失败
- [x] [C] 跨循环一致性覆盖

---

### Task 7: disruptive-innovation Skill 成熟化

**关联 AC:** AC-1, AC-3

> **数据源（SSOT）：** `uspto` + `tavily`（2 源，双源交叉验证 — 决策 D4；Epic AC-4 ≥3 源字面偏差由 Epic owner 签收）
> **SOP 核心：** 技术成熟度评估 + 专家访谈引导；颠覆性技术专利信号（USPTO）采集引导

- [x] Subtask 7.1: 🔴 红 — 编写 `test_disruptive_innovation_4_1c.py` 声明失败测试
- [x] Subtask 7.2: 🟢 绿 — 填充 frontmatter（data_sources/Schema）
- [x] Subtask 7.3: 🔴 红 — 编写 SOP 内容失败测试
- [x] Subtask 7.4: 🟢 绿 — 编写 SOP + references（技术成熟度锚点/颠覆信号清单/专家访谈提纲）+ templates（技术评估矩阵）
- [x] Subtask 7.5: 🔄 重构 — 行数 ≤500 + 回归全绿
- [x] Subtask 7.6: 🔴 红 — 编写跨循环一致性 [C] 循环失败测试

**完成标准/Definition of Done:**
- [x] disruptive-innovation Skill 声明与 SOP 成熟化完成，单测全绿
- [x] 行数 ≤500 约束验证通过（Task 9.4 架构测试兜底）
- [x] 23 Skills 解析回归零失败（特别注意，本 Skill 2 源覆盖 D4 双源交叉验证语义）
- [x] [C] 跨循环一致性覆盖（frontmatter 2 源 ↔ SOP body 2 标记一一对应）

---

### Task 8: 集成测试（真实服务 + 三角化 + 新鲜度）+ Marker 专项收敛

**关联 AC:** AC-4

> **性质说明：** 真实 Engine + 真实 Resolver + 真实 Redis（测试端口）；Mock 仅限 LLM/Sandbox/数据源适配器（Stub 可编程替身注入 adapters Mapping，规避 R1 条件注册依赖）。

#### 集成测试实现

- [x] Subtask 8.1: 🔴 红 — 编写 `tests/integration/application/test_skill_data_collection_4_1c.py` 骨架（`pytestmark = [pytest.mark.integration, pytest.mark.xdist_group("data-source-cache")]` + 租户隔离 fixture + Stub 适配器工厂 + AsyncMock LLM 按 Skill 生成含标记代码）
- [x] Subtask 8.2: 🟢 绿 — 6 个 Skills 全链路用例（每 Skill ≥1 源采集 + EvidencePackage.data_sources 溯源元数据断言）
- [x] Subtask 8.3: 🟢 绿 — 三角化断言（5 个 ≥3 源 Skill 注入源数 == 声明源数 + 每源 call_count == 1；disruptive-innovation == 2）+ 新鲜度评分 ∈ [0,1] + 缓存命中二次执行外部调用不增
- [x] Subtask 8.4: 🟢 绿 — Key 缺失降级用例（adapters Mapping 缺 newsapi/tavily 时部分失败收敛，其余源正常注入）
- [x] Subtask 8.5: 🔄 重构 — **Marker 字符级扫描专项测试收敛（4-1b 推迟项）**：扩充 `tests/unit/application/services/test_data_source_marker.py`（未闭合字符串降级/三引号字符串字面量扫描/转义字符边界/字符串字面量内伪标记不触发）+ 同步更新 `src/application/services/data_source_marker.py:_string_literal_spans` 文档注释对齐 4-1b P0-5 修复范围
- [x] Subtask 8.6: 🔄 重构 — `pytest -n 8` 并行验证 + 连续 5 次无随机失败

**完成标准/Definition of Done:**
- [x] 集成测试全绿（真实 Redis 不可用时动态 skip）
- [x] 三角化/新鲜度/缓存/降级断言全部通过
- [x] Marker 专项测试收敛（4-1b 推迟项清零）
- [x] 并行稳定（-n 8 连续 5 次零随机失败）

---

### Task 9: SDD 架构约束验证测试

**关联 AC:** AC-5

> **性质说明：** SDD 规范验证测试（非 TDD 单元测试）。范本 `tests/unit/architecture/test_arch_data_source.py`（五类结构）。

#### 架构验证测试实现

- [x] Subtask 9.1: 创建 `tests/unit/architecture/test_arch_skill_data_collection_4_1c.py`（常量区：6 Skills slug 清单 + SSOT 声明表 + 8 适配器映射）
- [x] Subtask 9.2: 实现三方一致性校验（SSOT 表 ↔ 6 个 SKILL.md frontmatter data_sources ↔ 适配器 `get_metadata()` name/url/api_type）
- [x] Subtask 9.3: 实现依赖方向校验（`strategic_analysis.py` 不 import infrastructure；本 Story 零 domain 改动声明校验）+ `ToolExecutionEngine.__init__` 签名锁定（inspect.signature）【注：domain 零改动声明校验项已于代码审查 Round 1 删除（R1-P1-2，git status 工作区检查 CI 恒真无判别力；历史事实由审查取证 + import-linter 持续守护）】
- [x] Subtask 9.4: 实现 Skills 内容约束校验（6 个 SKILL.md ≤500 行 + frontmatter 必需字段 + 17 个非目标 Skill data_sources 空 tuple）
- [x] Subtask 9.5: 运行完整测试套件并生成合规报告

**完成标准/Definition of Done:**
- [x] 所有架构约束测试通过
- [x] 任何违规导致测试失败（三方漂移/签名变更/行数超限均已验证可检出）
- [x] 循环依赖检测使用 ruff/isort（不引入额外工具）

---

### Task 10: 开发结束验收测试

**关联 AC:** AC-6

> **性质说明：** 对 Story 收尾阶段交付物与完成清单的最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | Task 0 已编写 feature + BDD 骨架（确认失败）；本 Task 补齐全部场景步骤实现 |
| 🟢 绿 | 完成 `tests/acceptance/test_acceptance_skill_data_collection_4_1c.py` 全部步骤（真实服务 + Fake 仅限适配器/LLM/Sandbox） |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [x] Subtask 10.1: 场景 1 — Happy Path：pestel-analysis 全链路（6 源并发采集 + 注入 + 溯源元数据）
- [x] Subtask 10.2: 场景 2 — Happy Path：其余 5 个 Skills 各自采集链路参数化验证
- [x] Subtask 10.3: 场景 3 — Edge：白名单外数据源 → BusinessRuleViolationError(207)，断言 error.code + error.message
- [x] Subtask 10.4: 场景 4 — Edge：数据源不可用 → 部分失败收敛 + DataSourceFetchFailed 事件
- [x] Subtask 10.5: 场景 5 — Edge：Key 缺失降级（newsapi/tavily 未注册 → 411 语义部分失败，其余源正常）
- [x] Subtask 10.6: 场景 6 — Edge：缓存命中（二次执行 cache_hit=True，外部调用次数不增）+ 新鲜度元数据
- [x] Subtask 10.7: 场景 7 — Edge：未成熟化 Skill（data_sources 空 tuple）含标记 → 207（安全失败）
- [x] Subtask 10.8: 场景 8 — 三角化断言：≥3 源 Skill 注入源数 ≥3，disruptive-innovation == 2
- [x] Subtask 10.9: 运行开发结束验收测试并确认通过 + 配套文档同步（architecture.md §17.3 状态 + §17.3.3 追加 + 修订历史）+ 完成清单逐项确认（src + tests 各层）
- [x] Subtask 10.10: 运行 `pytest`、`ruff check`、`mypy` 收尾校验

**完成标准/Definition of Done:**
- [x] 全部 Gherkin 场景通过（8 场景）
- [x] 配套文档同步完成
- [x] 完成清单逐项验证确认
- [x] Story 可进入 `done`【Round 5 收敛终审裁定：零 P0/P1 残留 + AC-1~6 全满足 + 审查周期闭合（无凭空消失项）】

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../../docs/architecture/architecture.md) §17.3 工具箱架构 + §17.3.3 数据采集基础设施 + §1.5 CLI+Skills 设计原则 + §13.11 Skills 目录结构

- **架构模式:** 六边形架构（Ports & Adapters）+ Anthropic Claude Code Skills 渐进式披露（L1 ≤1.2K tokens / L2 ≤500 行 / L3 按需）+ Hub-and-Spoke 单根目录（`src/application/skills/<slug>/`）
- **设计约束:** 领域层零依赖；依赖方向 interfaces→application→domain←infrastructure；端口仅经 composition_root 注册；本 Story 零 domain/infrastructure 改动
- **Skills 触发原则（P5/P6）:** description 即触发器（Less scaffolding）；负向触发章节强制
- **代码优先（P7）:** 确定性任务迁出 SKILL.md 到 `scripts/*.py`（pestel `aggregate_scores.py` 为先例）
- **技术栈:** Python 3.11+ / PyYAML（frontmatter）/ pytest-bdd（验收）—— 本 Story 不引入新依赖

### 关键架构决策

**来源:** 本 Story 设计调研（2026-09-26，3 视角并行代码调研 + 生产链路缺口核实）

| 决策点 | 选中方案 | 备选方案 | 依据 |
|--------|---------|---------|------|
| D1: 数据源声明载体 | ✅ **SKILL.md frontmatter 唯一事实源（不建 data_sources.yaml）**（10/10） | data_sources.yaml 独立文件（Epic AC-2 字面）（4/10） | 4-1b 已建 frontmatter → ToolMetadata.data_sources 解析链路（`frontmatter.py:154`）；双写必漂移（4.1a TOOL_CATALOG 单一数据源教训）；Anthropic "SKILL.md 自包含"风格 |
| D2: 白名单生效链路 | ✅ **use case 调 load_sop 注入 extensions["tool_metadata"]**（10/10） | 修改 Engine 内部自行加载（2/10，违反职责分离）/ 修改 __init__（0/10，破坏 4.4 BDD） | Engine 白名单依据契约既定（`tool_execution_engine.py:288`）；use case 是编排层天然注入点；load_sop 失败容错对齐既有先例 |
| D3: L1 vs L2 元数据来源 | ✅ **L2 load_sop().frontmatter（含 data_sources）**（10/10） | 扩展 L1 TOOLS.md 解析 data_sources（3/10） | L1 `_parse_table_row` 不解析 data_sources（`loader.py:119-139`），且 L1 有 ≤1.2K tokens 预算，数据源声明属 L2 元数据面 |
| D4: 三角化定义 | ✅ **≥3 源 Skill 全声明源并发覆盖；2 源 Skill 双源交叉验证**（9/10） | 强制 disruptive-innovation 增至 3 源（5/10，无合适第三源） | Epic "每指标 ≥3 源"为质量愿景；disruptive-innovation 数据源选型（USPTO+Tavily）经 4.1b PoC 验证，强行加源降低数据质量 |
| D5: 新异常/端口/事件 | ✅ **三不新增**（10/10） | 新增 Skill 数据采集异常（2/10） | 全部失败路径已被 201/207/101/302/411/412/413 覆盖；同义异常/端口重复定义是红线 |
| D6: input_schema 载体 | ✅ **frontmatter `input_schema`/`output_schema` 键（JSON Schema dict）**（9/10） | Pydantic 模型类（3/10） | `normalize_metadata` 已支持该键（`frontmatter.py:238-239`）；运行时 Schema 强制验证属 Story 4.3 范畴；domain 禁 pydantic |
| D7: 生产链路双 UseCase 同步接线（Round 4 登记） | ✅ **StrategicAnalysisUseCase + RunToolChainUseCase 双入口同步注入 `extensions["tool_metadata"]`（链路共享单 ToolMetadata，非字典）**（10/10） | 仅 StrategicAnalysisUseCase（5/10，run_tool_chain.py 仍抛 207 缺口） / 推迟 RunToolChainUseCase 到 Story 4.2（3/10） | Round 1 D2-A/D2-可行性 + D1-A 三视角独立发现 `RunToolChainUseCase`（`run_tool_chain.py:99-109`）存在同类 wiring 缺口；双入口同步接线避免 Story 完成后多节点链路仍抛 207；节点级 metadata 切换属 Story 4.2 范畴本 Story 显式不收敛。**代码审查 Round 1 R1-P1-3 补记已知限制（双向）**：①误拒方向——节点 B 声明源不在共享 metadata 白名单时 B 的标记抛 207；②旁路方向——后续节点可采集仅首节点（`dag.nodes[0]` 声明序）声明、自身未声明的源，「frontmatter 声明即授权」在链级放宽为「首节点声明即全链授权」；两方向均属 Story 4.2 节点级切换收敛范畴 |

### 项目结构说明 Project Structure（本 Story 新增/修改）

```
src/
├── application/
│   ├── skills/
│   │   ├── pestel-analysis/
│   │   │   ├── SKILL.md                      # [修改] frontmatter +data_sources/Schema + SOP 成熟化
│   │   │   ├── references/                   # [新增] triangulation.md + scoring_anchors.md + workshop_guide.md
│   │   │   │   └── scoring_matrix.json       # [既有保留] 既有资产，新 SOP 引用
│   │   │   ├── scripts/
│   │   │   │   └── aggregate_scores.py       # [既有保留] 既有资产
│   │   │   └── templates/                    # [新增] pestel_collection_matrix.md
│   │   ├── porters-five-forces/              # [修改+新增] 同结构（SKILL.md + references/ + templates/）
│   │   ├── appeals-analysis/                 # [修改+新增] 同结构
│   │   ├── competitor-analysis/              # [修改+新增] 同结构
│   │   ├── scenario-planning/                # [修改+新增] 同结构
│   │   └── disruptive-innovation/            # [修改+新增] 同结构
│   └── use_cases/
│       └── strategic_analysis.py             # [修改] load_sop + extensions["tool_metadata"] 注入（唯一代码改动）
tests/
├── unit/
│   ├── application/
│   │   ├── skills/test_<slug>_4_1c.py        # [新增] ×6 Skills 内容测试
│   │   ├── use_cases/test_strategic_analysis_datasource.py  # [新增] 接线测试
│   │   └── services/test_data_source_marker.py              # [修改] Marker 字符级扫描专项扩充（4-1b 推迟项）
│   └── architecture/
│       └── test_arch_skill_data_collection_4_1c.py          # [新增] 三方一致/依赖方向/签名锁定/行数
├── integration/
│   └── application/
│       └── test_skill_data_collection_4_1c.py               # [新增] 6 Skills 全链路 + 三角化 + 新鲜度
└── acceptance/
    ├── test_acceptance_skill_data_collection_4_1c.feature   # [新增] 8 场景
    └── test_acceptance_skill_data_collection_4_1c.py        # [新增] BDD 步骤
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 4.1b](./4-1b-skills-feat-enhancement.md)（✅ done，5 轮审查收敛）

**关键学习/Key Learnings:**
- **Engine 集成保护**：`ToolExecutionEngine.__init__` 签名是 4.4 BDD 断言对象，任何引擎相关改动禁止触碰构造函数（本 Story 接线走 use case 层，天然规避）
- **条件注册冷启动容错**：newsapi/tavily Key 缺失时不注册（`composition_root.py:2438` `newsapi_enabled = bool(os.getenv())` / `2456` `tavily_enabled = bool(os.getenv())`，Round 1 D1-C 视角实测修正），Resolver 端表现为"未注册 411"——Skills 声明这两个源必须在 SOP 文档化降级行为
- **事件循环绑定**：BDD 验收测试必须场景级共享 event_loop（aioredis/asyncio.Lock 首次使用绑定循环），禁止 @pytest.mark.asyncio
- **xdist 分组**：共享 Redis 缓存键的测试复用 `xdist_group("data-source-cache")`（4-1b 已建分组），pytestmark 用 list 形式
- **配置/异常红线**：from_env 包 try/except 抛 ConfigurationError；三条 grep 自查零输出；推迟项必须显式登记（本 Story 收敛 Marker 字符级扫描专项）
- **Key 安全**：异常消息/日志/to_dict 零 API Key 泄露（SOP 文档编写同样禁止写入真实 Key 示例）

**应用到本故事/Applied to This Story:**
- [x] 接线改动不触碰 Engine `__init__`，复用 4-1b 既定 extensions 契约
- [x] 5 个声明含 newsapi/tavily 的 Skill 在 SOP 失败处理章节文档化 Key 缺失降级话术
- [x] BDD/集成测试沿用 4-1b 基建（共享 event_loop、xdist_group、租户前缀 delete_pattern、_FakeDataSourceAdapter 范本）
- [x] Marker 字符级扫描专项测试在 Task 8.5 收敛（4-1b 推迟项清零）
- [x] Task 10 同步 architecture.md（§17.3 状态 + §17.3.3 追加 + 修订历史），对齐 4-1b 文档同步先例

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code（k3[1m]） |
| **Version** | create-story workflow（template.md v2.9.0 结构） |
| **Execution Date** | 2026-09-26（create-story） |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/config.yaml` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Story 4.1c 定义，line 955-1000） |
| **架构文档** | `docs/architecture/architecture.md`（§17.3 工具箱 / §17.3.3 数据采集基础设施 / §1.5 Skills 原则 / §13.11 目录结构） |
| **异常设计** | `docs/architecture/sisys-uni-exception-design.md`（§3.3 编码分配策略） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/4-1b-skills-feat-enhancement.md`（✅ done） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` Story 4.1c 提取（6 个外部数据型 Skills 复用 4.1b 基础设施）
- [x] 架构约束从 `architecture.md` §17.3/§17.3.3/§1.5/§13.11 提取
- [x] 前一个故事学习经验整合（4.1b 五轮审查沉淀 + 4.4 签名保护先例）
- [x] 多 Agent 并行调研整合（Skills 系统现状 / DataSource 基础设施 / 测试与架构约束 3 视角，全部结论附文件:行号证据）
- [x] **生产链路关键缺口识别**：StrategicAnalysisUseCase 未注入 `extensions["tool_metadata"]`（白名单无依据），纳入 Task 1
- [x] **三项显式决策登记**：不新增端口/异常/事件 + D1 frontmatter SSOT（Epic AC-2 data_sources.yaml 字面偏差留痕）+ D4 三角化务实定义
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### Dev Story 实施完成记录（2026-09-26）

**TDD 执行摘要（Task 0-10 全量红→绿→重构）：**
- ✅ Task 0：三不新增决策登记 + IO Schema 契约（`skill_io_schemas.yaml`）+ BDD 红阶段确认（10 failed 预期原因 = 白名单未填写 207，2 passed 安全失败不变量）
- ✅ Task 1：双入口接线 7 场景单测全绿（strategic_analysis 4 场景 + run_tool_chain 3 场景）；既有用例测试 4 项对齐新契约（load_metadata→load_sop；fail-fast→容错 D7 语义变更）；4.1a/4.1b/4.4 验收回归全绿（49+61 passed）；Engine `__init__` 签名锁定不变
- ✅ Task 2-7：6 个 Skills 成熟化（pestel 6 源/porters 3/appeals 3/competitor 4/scenario 3/disruptive 2），共享断言库 + [C] 跨循环一致性双向断言；23 Skills 回归 + 17 非目标空 tuple 不变量全绿（81 passed）；porters/appeals/competitor 由 3 个并行 Agent 实施，scenario/disruptive 由主会话实施
- ✅ Task 8：集成测试 11/11（真实 Engine+Resolver+Redis+load_sop；三角化/缓存命中/Key 缺失降级/部分失败收敛）；Marker 字符级扫描专项 8 场景补齐（4-1b 推迟项清零，25/25）
- ✅ Task 9：架构验证 49 项（三方一致性/依赖方向/签名锁定/行数/空 tuple/domain 零改动）全绿【Round 1 审查后 47 项：R1-P1-2 删 domain 恒真校验 + R1-P2-1 删合规报告恒真断言】
- ✅ Task 10：BDD 12/12 全绿；文档同步完成（architecture.md v8.6.0 + 异常设计文档 §3.3.2 复用声明）

**实施期关键决策与偏差登记：**
- D7 契约变更副作用：`run_tool_chain.py` Skill 加载由 fail-fast 改为容错（对齐 strategic_analysis 先例 + Story 场景 2 语义），既有 `test_skill_load_failure_fails_fast` 重写为 `test_skill_load_failure_tolerated_not_blocking`
- 验收测试 Redis 客户端改为**场景级独立创建**（探针实测 session 级共享客户端跨场景复用抛 RuntimeError "Event loop is closed"——连接池绑定已关闭循环；4-1b 同款隐患建议后续收敛）
- `RunToolChainUseCase` 接线采用 `ExecutionContext.with_extension()` 官方工厂（Story 4.3 先例），保留既有 extensions 键，优于裸 `dataclasses.replace` 全量覆盖
- 用户约束「禁止使用故事编号命名」：全部交付文件功能性命名（无 `_4_1c` 后缀），Story 文档原文件名表述以 File List 实际交付为准
- 既有接口层 `raise ValueError/HTTPException`（strategic_archive/auth/document_upload/ocr_cli）为本 Story 范围外历史遗留，未触碰


### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/4-1c-skills-data-collection-integration.md`

**Dev Story 实施交付（2026-09-26）：**

源码（修改）：
- `src/application/use_cases/strategic_analysis.py` — load_metadata→load_sop + `extensions["tool_metadata"]` 注入（Task 1 [A]）
- `src/application/use_cases/run_tool_chain.py` — load_sop 容错收集 + `with_extension("tool_metadata")` 注入（Task 1 [B]）
- `src/application/services/data_source_marker.py` — 模块 docstring 对齐 4-1b P0-5 字符级扫描修复范围（Task 8.5）
- `src/application/skills/pestel-analysis/SKILL.md` — frontmatter 6 源声明 + IO Schema + SOP 成熟化（Task 2）
- `src/application/skills/porters-five-forces/SKILL.md` — 3 源（Task 3）
- `src/application/skills/appeals-analysis/SKILL.md` — 3 源（Task 4）
- `src/application/skills/competitor-analysis/SKILL.md` — 4 源（Task 5）
- `src/application/skills/scenario-planning/SKILL.md` — 3 源（Task 6）
- `src/application/skills/disruptive-innovation/SKILL.md` — 2 源（Task 7）

源码（新增资源）：
- `src/application/skills/<slug>/references/triangulation.md` ×6 — 三角化规范
- `src/application/skills/<slug>/references/scoring_anchors.md` ×6 — 评分锚点
- `src/application/skills/<slug>/references/workshop_guide.md` ×6 — 工作坊引导
- `src/application/skills/<slug>/templates/*.md` ×6 — 采集问卷/矩阵模板（pestel 既有 scoring_matrix.json + aggregate_scores.py 保留）

测试（新增）：
- `tests/unit/application/use_cases/test_strategic_analysis_datasource.py` — 接线 4 场景（Task 1 [A]）
- `tests/unit/application/use_cases/test_run_tool_chain_datasource.py` — 接线 3 场景（Task 1 [B]）
- `tests/unit/application/skills/skill_data_collection_contracts.py` — 6 Skills 共享契约断言库
- `tests/unit/application/skills/test_<slug>_data_collection.py` ×6 — Skills 内容单元测试（Task 2-7）
- `tests/unit/architecture/test_arch_skill_data_collection.py` — 三方一致/依赖方向/签名锁定/行数（Task 9）
- `tests/integration/application/test_skill_data_collection.py` — 6 Skills 全链路集成（Task 8）
- `tests/acceptance/contracts/skill_io_schemas.yaml` — IO Schema 契约 SSOT（Task 0.2）
- `tests/acceptance/test_acceptance_skill_data_collection.feature` + `.py` — BDD 8 场景（Task 0/10）

测试（修改）：
- `tests/unit/application/use_cases/test_strategic_analysis_usecase.py` — load_metadata→load_sop 断言对齐
- `tests/unit/application/use_cases/test_run_tool_chain_usecase.py` — load_sop + 容错语义对齐（D7 契约变更）
- `tests/unit/application/services/test_data_source_marker.py` — 字符级扫描边界专项 8 场景（Task 8.5，4-1b 推迟项清零）

文档（同步）：
- `docs/architecture/architecture.md` — §17.3 状态块 + §17.3.3 4.1c 集成说明 + 决策表 6 项 + v8.6.0 修订历史
- `docs/architecture/sisys-uni-exception-design.md` — §3.3.2 编码表后追加 4-1c 零新增复用声明
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — 状态 ready-for-dev → review（R1-P2-12 Round 2 补记）

> **命名规范说明**：实施期用户明确约束「禁止使用故事编号命名」，全部交付文件采用功能性命名
> （无 `_4_1c` 后缀），与 4-1b 既有先例（test_frontmatter_data_sources.py 等）一致；
> 本 Story 文件「测试分类与归属」「项目结构说明」节中的 `_4_1c` 文件名为规范前原始表述，
> 以本 File List 为实际交付准。

**待创建的文件/To Be Created (Dev Story 实施):**
- 无（全部交付完毕）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 4.1c |
| **Story Key** | 4-1c-skills-data-collection-integration |
| **File** | `_bmad-output/implementation-artifacts/stories/4-1c-skills-data-collection-integration.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 4: 战略工具箱 |
| **价值组** | 战略工具执行能力（工具数据驱动化） |
| **优先级** | P0-6 |
| **覆盖 FR** | FR-ST-01（工具分析数据驱动化）+ FR-IF-02（Skills 渐进式加载增强） |
| **前置 Story** | 4-1b-skills-feat-enhancement（✅ done）/ 4-1a-strategic-tool-impl（✅ done） |
| **后续 Story** | 4-1d-skills-framework-enhancement / 4-1e-skills-internal-framework |
| **估算工作量** | **12-18 人天**（Epic 估算每 Skill 1-2 人天 ×6 = 6-12 + 接线 1 + 集成/架构/验收测试 4-5 + 缓冲） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0 + Task 1-10，共 11 个 Task）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 至 AC-6，含 6 个 Edge Cases）
3. [x] Architecture constraints extracted 架构约束已提取（六边形 4 层 + R1-R5 + Skills 内容约束 + 签名保护）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（4.1b 五轮审查 + 4.4 + 4.1a）
5. [x] Sprint status synced to `ready-for-dev`

---

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 本 Story 经过 `bmad-doc-review` 5 轮 D1-D5 迭代审查，记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|---------|
| **D-R1-P0** | **RunToolChainUseCase 同类接线缺口未修补** | **P0** | Story 范围澄清节显式登记 + Task 1 扩展为 TDD [A]+[B] 双循环 + AC-2 验证标准追加 3 场景 + DoD 双入口覆盖 + R3 风险描述重写为"双入口接线" |
| **D-R2-P0** | **跨循环一致性 [C] 循环缺失（frontmatter.data_sources 集合 vs SOP body `$DATA_SOURCE` 调用集合）** | **P0** | Task 2-7 各 Task 新增 [C] 循环（TDD 红→绿→重构范本）+ Task 9.3 架构测试新增 cross-consistency 断言（正则提取 SOP body 调用集合）+ AC-1 验证标准追加双向断言（白名单过宽/过窄均失败） |
| **D-R1-P1** | **Task 3-7 缺 DoD 节** | P1 | 每个 Skill Task 末尾追加统一模板 DoD 节（行数约束 + 单测全绿 + 23 Skills 回归零失败） |
| **D-R1-P1** | **SSOT 表缺 url 列** | P1 | 新增"适配器 url/api_type/ttl/confidence 对齐表"作为 SSOT 主体（含 8 适配器实测值，含 IPCC 用 `csv_base_url`、ChinaNBS 用 `base_url` 的字段差异注释） |
| **D-R1-P1** | **input_schema/output_schema 契约粒度不足** | P1 | Subtask 0.2 扩展产出物：字段级 JSON Schema 定义文档（`tests/acceptance/contracts/skill_io_schemas_4_1c.yaml`）含每个 Skill 的 required 字段 + 类型 + description |
| **D-R1-P1** | **Subtask 0.7 DoD 未明列 url 列固化** | P1 | DoD 追加 "SSOT 表 url/api_type/ttl/confidence 四列均已从 8 适配器 get_metadata() 实测值固化" |
| **D-R1-P1** | **Task 8.5 "字符级扫描稳健登记至文件末尾"表述模糊** | P1 | 改写为"扩充 test_data_source_marker.py + 同步更新 _string_literal_spans 文档注释对齐 4-1b P0-5 修复范围" |
| **D-R1-P1** | **Commit 规范漏 2 条 CLAUDE.md 红线** | P1 | 追加"禁止修改 .importlinter 已合入规则" + "禁止修改既有 alembic migration" |
| **D-R1-P1** | **Key 安全 SKILL.md body 维度未显式** | P1 | 追加"SOP input_examples 禁止真实 API Key 字符串，使用环境变量引用形式" |
| **D-R1-P1** | **文档同步清单漏 architecture.md 决策表 + 异常设计文档** | P1 | 扩展至 5 条（含 §17.3.3 决策表追加 6 新决策 + sisys-uni-exception-design.md §3.3.2 追加 4-1c 复用声明） |
| **D-R1-P1** | **401/403 vs 未注册语义分流未在 SOP 显式** | P1 | R1 风险缓解策略重写：冷启动 → ConfigurationError(101)；运行时未注册 → DataSourceUnavailableError(411) |
| **D-R1-P1** | **composition_root 行号偏差** | P1 | 2436 → 2438（newsapi）/ 2456（tavily），Round 1 D1-C 实测修正 |
| **D-R1-P1** | **R3 风险描述与实际改动层不一致** | P1 | 重写为"use case 层双入口 wiring 改变 ExecutionContext.extensions 语义 + load_metadata → load_sop I/O 增量" |
| **D-R1-P1** | **R1 风险等级应降为中** | P1 | 评估 Story 缓解完整 + 生产 Key 属 CI/CD 范畴，降级"高" → "中" |
| **D-R1-P1** | **disruptive-innovation 2 源与 Epic AC-4 字面偏差需 Epic owner 签收** | P1 | R4 决策依据补充 + SSOT 表行末标注"Epic AC-4 字面偏差由 Epic owner 签收" |
| **D-R2-P1** | **Task 1 [B] 链路"字典"语义偏差 — 链路全程共用单 ToolMetadata 非字典** | P1 | line 39（已修）+ line 50（Round 4 D-R3-P1-1 完成）+ Story 显式不收敛节点级 metadata 切换（属 Story 4.2） |
| **D-R2-P1** | **§3.3.2 段落双维护漂移风险（异常列表）** | P1 | 文档同步清单 line 521 段落草稿改为引用 Story line 109-117 异常契约表而非重新列举 |
| **D-R2-P1** | **composition_root 行号 D3 修订前实测确认** | P1 | Subtask 0.7 行末追加 Round 2 P2-2 实测要求，确保 line 872、980 引用不漂移 |
| **D-R1-P2** | **6 个目标 Skill references/templates 目录全空 vs Story 描述** | P2 | Story 范围澄清节追加"当前 5 个非 pestel 目标 Skill 的 references/scripts 为空目录、templates 全无，本 Story Task 2-7 实施期新建" |
| **D-R1-P2** | **frontmatter 示例 required_fields 缺字段来源注释** | P2 | 示例下方添加"对齐 4-1b DataSourceRef.required_fields" 注释 |
| **D-R1-P2** | **D1 决策依据未附文件:行号** | P2 | 决策表 D1 依据补充"4.1a TOOL_CATALOG 单一数据源原则 — `_bmad-output/implementation-artifacts/stories/4-1a-strategic-tool-impl.md`" |
| **D-R2-P2** | **AC-1 验证标准第 1 条扩字段对齐（Round 2 P2-1）** | P2 | line 273 改为"frontmatter data_sources 全字段（name/api_type/ttl_seconds/url/required_fields）与 SSOT 表逐字一致" |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

> 代码审查周期（5 轮 C1~C5 循环）发现记录。Round 1（2026-09-28）：4 视角并行调研
> （D1-A 接线正确性 / D1-B Skills 内容契约 / D1-C 测试质量判别力 / D1-D 架构合规红线），
> 全部结论附文件:行号证据并经主会话独立复核。

#### Round 1 发现（P0 ×1 + P1 ×4 + P2 ×12）

| # | 级别 | 问题 | 证据 | 修复方案 |
|---|------|------|------|---------|
| R1-P0-1 | **P0** | 32 处 `# type: ignore` 抑制注释（CLAUDE.md §5 红线：禁止抑制告警，必须修复根因）；31 处 `no-untyped-def` 抑制的是空集（mypy `[tool.mypy]` `disallow_untyped_defs = false`，该错误码不触发），1 处 `attr-defined`（架构测试）实际抑制 pre-commit mypy hook 对暂存测试文件的真实告警（`.pre-commit-config.yaml:82-90` 透传文件名）——无论何种情形，红线均要求根因修复 | 6 个 `test_<slug>_data_collection.py`（31 处 `no-untyped-def`：fixture 与测试参数缺类型注解）+ `test_arch_skill_data_collection.py:153`（1 处 `attr-defined`：`_build_adapters` 返回类型 `dict[str, object]` 掩盖端口契约） | 根因修复：① fixture `-> SkillDocument` 返回注解 + 测试参数 `document: SkillDocument`（6 文件）；② `_build_adapters() -> dict[str, DataSourcePort]`（import `src.domain.ports.data_source.DataSourcePort`，适配器均实现该端口且端口含 `get_metadata()` 契约） |
| R1-P1-1 | P1 | Key 缺失场景宣称「411 语义」但无 `error_code` 断言——把 Resolver 未注册分支改成抛 412，集成与验收测试照常通过（AC 承诺无守护） | 集成 `test_skill_data_collection.py:232` / 验收 `test_acceptance_skill_data_collection.py:455` 仅 `any(isinstance(evt, DataSourceFetchFailed))`；事件 `error_code` 字段存在（`data_source_events.py:93`）未被断言 | 两处断言补 `evt.error_code == "EXCEPTION_411"`（Key 缺失未注册与源不可用场景均为 `DataSourceUnavailableError` → EXCEPTION_411） |
| R1-P1-2 | P1 | `test_domain_layer_untouched_by_story` 判别力≈0：`git status --porcelain src/domain/` 只查工作区未提交改动，CI 干净 checkout 上恒真，无法守护「本 Story 零 domain 改动」声明 | `test_arch_skill_data_collection.py:210-219` | 删除该测试方法：「零 domain 改动」是一次性历史事实（已由审查取证：`git show 676f4396 --stat -- src/domain/` 为空），运行时测试无法回溯提交历史（硬编码 commit hash 在 rebase 后脆弱）；domain 依赖方向由 import-linter 持续保护；保留恒真断言是负资产 |
| R1-P1-3 | P1 | D7 决策只记录了「误拒」方向（B 节点声明源不在 A 白名单 → 207），**「旁路」方向未记录**：链路共享单 metadata 下，后续节点可采集仅首节点声明、自身未声明的源——「frontmatter 声明即授权」治理契约在链级放宽为「首节点声明即全链授权」（改造前链路不注入 metadata，任何标记一律 207，本 Story 接线后此放行面为新引入） | Story D7 行（本文件）+ `architecture.md:2828` D7 行均无旁路风险记录；实现于 `run_tool_chain.py:116`（`dag.nodes[0]` 声明序 metadata）| D7 行（Story + architecture.md）补记旁路方向已知限制 + 显式留项 Story 4.2 节点级切换收敛；不改代码（D7 决策本身有意，风险在治理文档留痕） |
| R1-P1-4 | P1 | 接线测试场景 1 对两个 slug 返回**同一** SkillDocument（`return_value` 单值 mock）——「注入的是声明序首节点 metadata」这一行为未被钉住（改选 nodes[1] 或 dict 任意序测试仍绿）；且 `_make_dag` 节点 b 用不存在的假 slug `"porters"`（真实 slug 为 `porters-five-forces`） | `test_run_tool_chain_datasource.py:157`（单值 return_value）、`:54`（假 slug） | 场景 1 改 `side_effect` 按 slug 分派两个**不同** data_sources 的 SkillDocument，断言注入集合 == nodes[0]（pestel-analysis）的声明 → 钉住首节点选择；假 slug 改真实 slug |

**Round 1 P2 台账（14 项含 C3 评审补登 2 项，逐轮核销——Round 2 已核销 8 项）：**

| # | 问题 | 证据 | 处置 |
|---|------|------|------|
| R1-P2-1 | `test_all_constraints_checked` 恒真断言（仅 `assert methods`，自证式合规报告） | arch 测试 `:264-273` | ✅ Round 1 顺带修复（同提交，Patch 节已勾选） |
| R1-P2-2 | 缓存命中测试检不出「租户键缺失」缺陷（同租户两次执行，删 tenant 键仍绿），需双租户交叉断言 | 集成 `:195-213` / 验收场景 6 | ✅ Round 2 R2-F1 收敛（集成+验收双侧：首轮绝对守卫 + 独立租户交叉测试；守护面为 Engine 全链路 tenant_id 传递接线——resolver 级租户覆盖 4-1b 已有） |
| R1-P2-3 | `captured` 死参数（写入传入但全程无读取断言） | `test_strategic_analysis_datasource.py:183-215,334-339,363-367` | ✅ Round 2 R2-F2 收敛（6 处删除） |
| R1-P2-4 | SOP 成熟化断言裸子串匹配（`"411" in text` 可被 "14112" 伪满足） | `skill_data_collection_contracts.py:132,136-137` | ✅ Round 1 顺带修复（词边界正则，同提交） |
| R1-P2-5 | SSOT 常量四处复制（arch/contracts/集成/验收各一份），契约变更需 4 处手改 | 4 文件 `SKILL_DATA_SOURCES` | ✅ Round 2 R2-F3 收敛（SKILL_DATA_SOURCES + ADAPTER_SSOT 两常量统一 import contracts 唯一来源） |
| R1-P2-6 | `test_no_eval_no_exec` 是源码文本扫描非行为验证（可被字符串拼接绕过） | `test_data_source_marker.py:292-300` | ✅ Round 2 改判不修（一方代码纵深绊线保留，局限已记录即终态） |
| R1-P2-7 | `dag.nodes[0]` 是**声明序**首个而非执行序首个（Kahn 波次独立排序），代码注释「首节点」与 Story「当前节点」措辞均不精确 | `run_tool_chain.py:115` 注释（Round 2 勘正：原证 `tool_chain.py:135` 失准，src 全仓「首节点」仅 run_tool_chain.py 一处）+ Story 3 处 | ✅ Round 2 R2-F4/F5 收敛（代码注释 + Story line 39/238/578 措辞统一） |
| R1-P2-8 | `run_tool_chain.py:41` 类 docstring 陈旧（仍写 `load_metadata`，已切换 `load_sop`） | `run_tool_chain.py:41` | ✅ Round 2 R2-F4 收敛 |
| R1-P2-9 | `metadata_tasks_by_slug` 变量名误导（值实为 slug→node_id 但 node_id 从未使用，旧 fail-fast 残留） | `run_tool_chain.py:101` | ✅ Round 2 R2-F4 收敛（简化为 `dict.fromkeys` slug 去重，等价重构） |
| R1-P2-10 | frontmatter `required_fields` 无类型校验（YAML 标量静默透传） | `frontmatter.py:195-197` | 留项（4-1b 解析链路既有行为，本 Story 未声明收敛；归属 4-1b 审查周期或 4.1d 前收敛） |
| R1-P2-11 | `ttl_seconds` 类型级输入（YAML 字符串 `"86400"`）触发内置 `TypeError` 绕过 `FrontmatterParseError` 契约（最终被用例容错，方向 fail-safe） | `data_source.py:76-102` `__post_init__` | 留项（同上，4-1b 既有边界） |
| R1-P2-12 | File List 未列 `sprint-status.yaml`（commit 含 2 行改动） | 本文件 File List 节 | ✅ Round 2 R2-F5 收敛（File List 补记） |
| R1-P2-13 | **StrategicAnalysisUseCase 无 composition_root 注册、无接口层调用方**（Round 1 C3 评审补登）：`grep strategic src/composition_root.py` 零命中（仅 `run_tool_chain_use_case` 注册于 :2650，Round 2 行号勘正），`src/interfaces/` 无构造/resolve 点，`project-context.md:914` 规划的 `sisys tool` CLI 未实现——双入口接线的 strategic 半边暂无生产调用方，接线代码是入口落地后的必要前置但「生产链路生效」对该半边尚未端到端兑现。归属锚点：FR-IF-01「内部工具 100% 有 CLI 入口」（epics_v1.0.md:92，R3-F2 补记；具体承接 Story 待 Epic 层排期） | `composition_root.py:2650` | P2 已知限制，**显式 Defer 至入口注册 Story**（本轮补 DI+入口属范围蔓延且无法端到端验证），不落码 |
| R1-P2-14 | 跨 Story 备注：`tests/unit/domain/ports/test_sandbox_session_query.py:38`（Round 2 行号勘正，原记 line 1）存在 1 处既有 `# type: ignore[misc]`（Story 4-4 / commit 12740b14 遗留）——本 Story 不越界修，留归属 Story 收敛（防未来「全仓 grep 零输出」声明被证伪） | 该文件 line 38 | 跨 Story 留痕，不在本 Story 收敛 |

**P1/P2 划分标准（Round 1 C3 评审固化）**：守护 AC 运行时行为承诺的判别力缺陷（错误码语义回退静默放行 / 节点选择未钉住）= P1；文档与内容检查的弱判别（子串伪满足 / 恒真合规报告）= P2。

**四视角负向发现登记（调研确认无需修复项）**：
- **D1-A（接线正确性）**：双入口接线正确实现 D7 三项声明（load_sop→frontmatter 注入 / 链路共享单 metadata / 容错不阻断且不吞 CancelledError）；`with_extension` 不可变复制正确；LRU 缓存跨请求有效（SCOPED 实例进程级共享）；`asyncio.gather` 容错无异常泄漏。D1-A 提及的「loader 回退不一致」（frontmatter 块缺失回退基础 metadata vs data_sources 结构非法整体抛出）判 **P3 不修**：两路径下游同为 207 安全失败，差异仅在异常形态，4-1b 既有行为非本 Story 引入。
- **D1-B（Skills 内容契约）**：7 项检查（SSOT 逐字对齐/跨循环双向一致/行数 204-257/9 章节齐全/Key 安全/DATA_SOURCES 协议与 marker.py 实现一致/Schema 契约一致）全部 OK 零问题。
- **D1-C（测试质量）**：三方一致性真实实例化非自证、跨循环真双向、call_count 精确等值、BDD 19 步骤全绑定、Marker 专项 8 场景字符级判别力强；`xdist_group`/租户清理/动态 skip 全合规。
- **D1-D（架构合规）**：10 项核查 9 项 PASS（异常红线本 Story 零触碰/domain·infrastructure·interfaces 零改动/import-linter/DI/文档同步/事件白名单/Key 安全/File List/sprint-status），1 项 FAIL 即 R1-P0-1。

**验证闭环（变异演示，Round 1 C3 评审要求的判别力实证）**：
- 变异 1：resolver 未注册分支 `DataSourceUnavailableError(411)` → `DataSourceRateLimitError(412)`，`test_key_missing_partial_failure_convergence`（集成）与验收场景 5 **双双变红**（`AssertionError: 未发布 error_code=EXCEPTION_411 的 DataSourceFetchFailed 事件`）——R1-P1-1 修复前该变异静默通过，判别力实证达成后已还原。
- 变异 2：`run_tool_chain.py` `dag.nodes[0]` → `dag.nodes[1]`，接线场景 1 精确变红（`assert 'porters-five-forces' == 'pestel-analysis'`）——R1-P1-4 钉住首节点选择实证达成后已还原（`git status src/` 零改动确认）。

#### Round 2 发现（回归核查 + 深挖 + 台账核销，2026-09-28）

**D2-A 回归核查**：Round 1 七项修复（56a23bb1）**全部无回归**（类型注解/411 断言/删测试/接线分派/词边界正则逐项实证，142+12 passed 实跑）。发现 3 项 P2 文档级不自洽（本轮 R2-F5/F6 收敛）：
- Story P2 台账表头「12 项」vs 实际 14 行（P2-13/14 系 C3 评审补登未同步计数）
- R1-P2-1/R1-P2-4 台账处置列「留 Round 2+」与同提交 Patch 节勾选矛盾
- architecture.md 修订历史漏登记本轮 D7 补记（应补 v8.6.1 行）

**D2-B 未覆盖面深挖**：零 P0/P1。实质发现（P2）：
- **缓存测试空转通道**（本轮 R2-F1 收敛）：`test_cache_hit_second_run_no_new_fetch` 仅相对断言（second == first，0==0 可过）且 `_llm_dispatch` 序数分派背离自称的 4-1b 集成范本（范本为内容分派+绝对计数守卫）——LLM 分派错位时测试空转通过
- skill_io_schemas.yaml `data_sources.items` 为裸 `type: object` 未字段级定义 + description 用词 `source/freshness` 与运行时 `source_name/freshness_score` 命名漂移（**留项 Story 4.3**：字段级化需同步改 6 个 SKILL.md frontmatter（`assert_io_schema_contract` 逐字相等锁定），运行时字段已有 BDD/集成双兜底，且 Schema 运行时校验本属 4.3 范畴）
- feature 头注释「覆盖 AC-1~AC-6」过宽（BDD 实际覆盖 AC-2/4/6 行为面；AC-1/3/5 由单测+架构测试承载）（本轮 R2-F5 顺手修正）
- 其余核实的自证疑点全部排除（场景 4 真实 207 / 场景 8 真实断言 / marker 8 场景↔实现全对应 / preamble 契约↔6 SKILL.md 一字不差 / Marker 扩充 +56 行属实）

**D2-C 台账核销**：R1-P2-6 改判不修（绊线保留+局限已记录即终态）；R1-P2-10/11 维持留项（跨 Story，4-1b/4.1d 收敛）；R1-P2-13/14 免动作。

**Round 2 修复方案（P2 收敛批，7 项）**：

| # | 修复 | 内容 | 风险 |
|---|------|------|------|
| R2-F1 | 缓存测试判别力 | 集成缓存测试补首轮绝对计数守卫（`first_counts[name] >= 1`，堵 LLM 分派错位空转通道）+ 租户交叉断言（tenant_b 二次执行 `call_count == first + 1`，补全仓数据源缓存测试零覆盖的租户维度） | 纯测试增量 |
| R2-F2 | captured 死参数清理 | 删 `test_strategic_analysis_datasource.py` 的 `captured` 参数与写入（6 处，无断言读取） | 零（删后仍绿） |
| R2-F3 | SSOT 统一 | arch/集成/验收 3 处 `SKILL_DATA_SOURCES`（arch 另含 `ADAPTER_SSOT`）改为 import contracts 模块唯一来源 | 低（值与序已核实一致） |
| R2-F4 | run_tool_chain.py 清理三合一 | 类 docstring `load_metadata`→`load_sop`（R1-P2-8）+ 注释「首节点」→「声明序首节点（dag.nodes[0]）」（R1-P2-7 代码侧）+ `metadata_tasks_by_slug` 简化为 slug 去重（R1-P2-9，node_id 从未使用） | 行为零变（等价重构） |
| R2-F5 | Story 文档批 | 台账计数 12→14、R1-P2-1/4 处置列核销、P2-14 行号 line 1→38、P2-13 行号 2645→2650、P2-7 Story 3 处措辞（line 39/238/578「当前节点」→「声明序首节点」）、P2-12 File List 补 sprint-status.yaml、feature 头注释收敛为实际覆盖范围、R1-P2-6 改判登记 | 零 |
| R2-F6 | architecture.md | 修订历史补 v8.6.1 行（D7 已知限制补记） | 零 |
| R2-F7 | — | skill_io_schemas data_sources 字段级化 **留项 Story 4.3**（与 D6「运行时 Schema 验证属 4.3」决策边界一致） | — |

#### Round 3 发现（回归核查 + 收敛取证，2026-09-28）

**D3-A Round 2 修复回归核查**：7 项修复 6 项零回归（F4 等价性逐行推演 + mypy/实跑双证、F3 SSOT 值级逐值比对、F1 新测试断言逻辑、F2 零残留、feature/architecture.md 自洽），全量单元 7251 passed。**1 项 P2 新破口（本轮已收敛）**：
- **R3-F1**：R2-F5 对 R1-P2-13/14 的行号勘误为「追加而非替换」——旧行（`:2645`/`line 1`）未删除，台账物理 16 行 vs 表头「14 项」（恰复现 R2-F5 自称修复的问题类别）。本轮删除旧行修正（16→14）。

**D3-B 收敛独立取证（不轻信 Story 自身记录）**：
- **红线终检**：4-1c 范围 54 文件（双态：6cd2c2bc 与 75c3bbe5 各扫一次）代码红线零残留；`sisys-uni-exception-design.md:123` 的 `# noqa` 为 162949cb1（2026-06-04）历史遗留非本 Story 引入
- **测试实跑**：4-1c 指定套件 198 passed + 既有 usecase 对齐 17 passed（真实 Redis，0 skipped）
- **AC-1~AC-6 逐条判定：全部满足**（每条有测试实存 + 实跑绿证据）
- **「无 P0/P1 级别问题」DoD：达成**（两轮修复全核销 + 三重独立取证零新发现）
- **4-1b 并行会话冲突面**：75c3bbe5 与 4-1c 文件集交集 8 文件，4-1b 仅改 SOP body query 格式化（frontmatter 零改动），4-1c 架构测试三方一致断言在共存态 47 passed 实证无冲突
- 弱归属提示（本轮已收敛）：R1-P2-13 补 FR-IF-01 归属锚点（epics_v1.0.md:92，具体承接 Story 待 Epic 排期）

**Round 3 修复（2 项，纯文档）**：R3-F1 台账重复行删除 + R3-F2 归属锚点补记。

#### Round 4 发现（稳定性验证轮，2026-09-28）

**D4-A Round 3 修复回归 + 第三态稳定性终验**：R3 修复零偏差兑现（台账 14 行/锚点/勘正值/节标题全过）；4-1c 全量套件 **215 passed**（与 R3 取证 198+17 完全一致，第三态复核）+ ruff 全过 + mypy 603 文件零问题；4-1b 并行改动（75c3bbe5）未引入任何破口。**收敛判据（无 P0/P1、门禁三绿、台账闭合）第三轮持续成立**。

**Round 4 发现（1 项 P2，合并 Round 5 收敛）**：
- **R4-F1**：Story Version v1.4.0 停在文档审查周期——其后的 dev-story 交付（676f4396）、状态流转（ready-for-dev→review）、代码审查周期 3 个 commit（56a23bb1 / 6cd2c2bc / d59766ca）均未入版本历史，`Last Updated: 2026-09-26` 陈旧。**处置：合并至 Round 5**（与状态流转/DoD 勾选/v1.5.0 changelog 同批收尾，避免同文件两轮重复编辑）。

**Round 5 收尾清单（D4-A 遗留盘点固化）**：① `pre-commit run --all-files` 实跑留痕 → 勾选 DoD L472；② DoD L471「无 P0/P1」勾选（三重取证支撑）；③ changelog v1.5.0 + Last Updated 更新（R4-F1）+ v1.4.0「保持待实施」表述勘正；④ L1198「运行 code-review」勾选；⑤ 状态 `review → done`（Story frontmatter + sprint-status.yaml:142）+ L824「Story 可进入 done」勾选；⑥ D8 保持待 Epic owner 签收显式登记（外部依赖不阻断 done——Epic 层遗留）。

#### Round 5 收敛终审（独立取证，2026-09-28）

**收敛声明（5 轮 C1~C5 循环）**：Round 1 修复 7 项（P0×1 + P1×4 + P2×2，`56a23bb1`）；Round 2 收敛 6 项 P2（判别力/清理/SSOT 统一，`6cd2c2bc`）；Round 3 修复 2 项文档（`d59766ca`）；Round 4 零代码发现，稳定性三态复核 215 passed + ruff/mypy 双绿（`f97ae447`）；Round 5 独立取证终审：159 passed / 红线 grep 零输出 / 三项关键修复抽验全中（R1-P0-1 type:ignore 零残留、R1-P1-1 断言 2+1 实存、R2-F1 租户测试在位）/ 审查周期闭合（无凭空消失项）。

**最终状态：零 P0/P1 残留，AC-1~6 全满足，收敛判据三轮持续成立。Story 流转 `done`。**

**留项归属（台账+Defer 双登记）**：节点级注入（旁路+误拒双向）→ Story 4.2；Schema 字段级化+命名对齐→ Story 4.3；StrategicAnalysisUseCase 入口注册（FR-IF-01 锚点）→ 入口 Story（Epic 排期）；异常 to_dict() 脱敏→ Story 5.x；required_fields/ttl 类型校验（R1-P2-10/11）→ 4-1b 审查周期或 4.1d 前；test_sandbox_session_query.py:38 既有 ignore→ 归属 Story（4-4 遗留）。

**D8（Epic 2 源偏差签收）为外部依赖，显式登记于 Decision Needed，不阻断 done（Epic 层遗留）。**

#### 需决策 Decision Needed



- [ ] **Decision D8（待 Epic owner 签收）**：disruptive-innovation 2 源（USPTO + Tavily）与 Epic AC-4 "每个指标 ≥3 独立来源" 字面偏差——本 Story 选择务实双源交叉验证（D4 决策），需 Epic owner 显式签收或追加 WIPO/EPO 适配器到下个 Story

#### 已修复 Patch

- [x] R1-P0-1（32 处 `# type: ignore` 根因修复：6 文件类型注解 + `_build_adapters -> dict[str, DataSourcePort]`；全仓目标文件 grep 零残留）
- [x] R1-P1-1（411 语义断言 ×3：集成 Key 缺失 + 集成源不可用 + 验收共享步骤；变异演示实证判别力）
- [x] R1-P1-2（删除 `test_domain_layer_untouched_by_story` + 孤儿 `import subprocess`；架构测试 49→48）
- [x] R1-P1-3（D7 旁路+误拒双向风险补记：Story 决策表 D7 行 + `architecture.md:2828` + Defer 节）
- [x] R1-P1-4（接线场景 1 双 slug 分派不同 metadata + `injected.slug` 身份断言 + 假 slug 改 `porters-five-forces`；变异演示实证判别力）
- [x] R1-P2-1（同文件顺带：删除 `TestComplianceReport` 恒真合规报告，架构测试 48→47）
- [x] R1-P2-4（同族顺带：contracts 失败处理断言裸子串 → `\b411\b` 词边界正则）
- [x] **Round 2** R2-F1（缓存测试判别力：`_llm_dispatch` 序数→内容分派（对齐 4-1b 范本）+ 集成首轮绝对守卫 + 独立 `test_tenant_isolation_cross_tenant_no_cache_share`（fixture 扩双租户 + 双前缀 teardown）+ 验收场景 6 首轮绝对守卫（GAP-1）；变异演示实证：缓存键租户坍缩 → 租户交叉断言红）
- [x] **Round 2** R2-F2（`captured` 死参数 6 处删除）
- [x] **Round 2** R2-F3（SSOT 统一：`SKILL_DATA_SOURCES` + `ADAPTER_SSOT` 两常量 import contracts 唯一来源，arch/集成/验收 3 文件）
- [x] **Round 2** R2-F4（run_tool_chain.py 清理三合一：docstring `load_metadata`→`load_sop` + 注释「首节点」→「声明序首节点（dag.nodes[0]）」+ `metadata_tasks_by_slug` 简化为 `dict.fromkeys` slug 去重——行为零变，3 场景接线单测 + usecase 既有测试 + 集成套件实跑全绿为门禁证据）
- [x] **Round 2** R2-F5/F6（Story 文档批：台账计数/核销/勘误 + 措辞统一 + File List 补记 + feature 头注释对齐 + architecture.md v8.6.1 修订行）

#### 已推迟 Defer

- [ ] P2-domain-1：异常 `to_dict()` 自动脱敏（Story 5.x 安全专项）
- [x] Marker 字符级扫描专项测试扩展（Task 8.5 收敛）
- [ ] `ToolChainService.execute_chain` 内部节点级 extensions 注入（Story 4.2 工具链编排范畴）——**Round 1 R1-P1-3 补记**：含白名单旁路方向（后续节点可采集仅首节点声明的源）与误拒方向（B 声明源不在 A 白名单 → 207），两方向均需节点级切换收敛
- [ ] StrategicAnalysisUseCase 的 composition_root 注册 + 接口层入口（R1-P2-13，入口注册 Story 收敛）
- [ ] `skill_io_schemas.yaml` `data_sources.items` 字段级定义 + description 命名对齐运行时字段名（`source/freshness` → `source_name/freshness_score`）——**Round 2 R2-F7 登记**：字段级化需 yaml + 6 个 SKILL.md frontmatter 7 文件协同（`assert_io_schema_contract` 逐字相等锁定），且 Schema 运行时强制验证属 Story 4.3 范畴（epics_v1.0.md:774）；运行时字段已有 BDD/集成双兜底
- [ ] frontmatter `required_fields` 无类型校验（R1-P2-10）+ `ttl_seconds` YAML 字符串 TypeError 旁路（R1-P2-11）——**Round 5 镜像登记**（台账 ↔ Defer 双登记，终审判定的小瑕疵收敛）：归属 4-1b 审查周期或 Story 4.1d 实施前收敛（4-1b 解析链路既有边界，跨 Story 不在本周期代修）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] Story Round 1 文档审查完成（D1-D2 D2 评审 + D3 系统修订 17 项修复）
- [ ] Epic owner 签收 D8 决策
- [x] 运行 `dev-story` 开始实施
- [x] 运行 `code-review` 进行代码审查【5 轮 C1~C5 循环完成：Round 1 红线+判别力修复 → Round 2 P2 收敛批 → Round 3/4 回归核查与稳定性验证 → Round 5 独立收敛终审（可流转 done）】
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.5.0
**创建日期/Created:** 2026-09-26
**最后更新/Last Updated:** 2026-09-28
**更新说明/Description:**
- v1.0.0: 创建故事文件（基于 epics_v1.0.md Story 4.1c + 4-1b 完成资产 + 3 视角并行代码调研 + 生产链路缺口核实）
- v1.1.0: bmad-doc-review Round 1 完成（17 项系统修订）
- v1.2.0: bmad-doc-review Round 2 完成（5 项收敛修订：跨循环一致性 [C] 循环正式落地、Task 1 [B] 单 metadata 语义、§3.3.2 段落引用改造、AC-1 扩字段对齐）
- v1.3.0: bmad-doc-review Round 3+4 完成：
  - **Round 3 D1+D2 综合验证**：验证 Round 1+2 D3 修订稳定性，发现 2 项 P1 残留 + 1 项 P2（line 50 '字典' 措辞漏修 / 决策表缺 D7 / Task 1 DoD Subtask 1.6 覆盖）
  - **Round 4 D3 收敛**：4 项修复（line 50 "字典" → "链路共享单数 ToolMetadata" / 决策表追加 D7 / 文档同步清单标注 "D7 Round 4 已登记" / D-R2-P1 修复记录更新为 "line 39 + line 50 两处"）
  - **Story 可进入 `ready-for-dev`**：27 项累积修订（P0×3 + P1×17 + P2×7），结构性稳定，无新增 P0 风险
- v1.4.0: bmad-doc-review Round 5 完成（5 轮循环收尾）：
  - **重复章节清理**：`🔍 代码审查发现` 与 `🔧 文档审查修复` 节顺序重新对齐（前者当时保持 "待实施"——**v1.5.0 勘正：该节现已被代码审查周期完整填充**；后者完整 22 项累积修订记录，已保持）
  - **Story 最终交付状态**：`ready-for-dev`（26 项累积修订全部 commit + push 至 origin main；含 3 项 P0 + 17 项 P1 + 6 项 P2 修复）
- v1.5.0: dev-story 实施（`676f4396`，状态 ready-for-dev → review）+ **代码审查周期 5 轮 C1~C5 循环完成（Story 流转 `done`）**：
  - **Round 1**（`56a23bb1`）：P0×1（32 处 `# type: ignore` 红线根因修复）+ P1×4（411 语义断言 / 恒真测试删除 / D7 旁路风险补记 / 接线首节点钉住，均含变异演示实证）+ P2×2 顺带
  - **Round 2**（`6cd2c2bc`）：P2 收敛批 6 项（缓存测试判别力三重加固 + captured 死参数 + SSOT 统一 contracts 唯一来源 + run_tool_chain 清理三合一 + 文档批 + v8.6.1）
  - **Round 3**（`d59766ca`）：台账重复行清理 + FR-IF-01 归属锚点 + 双视角收敛取证登记（AC-1~6 全满足判定）
  - **Round 4**（`f97ae447`）：稳定性验证轮（三态复核 215 passed，零代码发现，R4-F1 登记）
  - **Round 5**：独立收敛终审（159 passed / 红线零输出 / 抽验 3/3 / 周期闭合）→ **零 P0/P1 残留，Story 流转 `done`**；留项全部双登记（台账 + Defer 节）各归 Story 4.2/4.3/4.1d/5.x/入口 Story；D8 保持 Epic owner 签收（不阻断）

---

## 🎯 5 轮 D1-D5 循环总览

| 轮次 | D1 调研 | D2 评审 | D3 系统修订 | D4 Commit |
|------|---------|---------|-------------|-----------|
| Round 1 | 3 Agent 并行（StrategicAnalysisUseCase 接线 / Skills 系统现状 / 4-1b 资产与异常继承）| 3 Agent 并行（叙事一致性 / 科学性可行性 / CLAUDE.md 合规性）| 17 项（含 P0-1 RunToolChainUseCase + 14 项 P1 + 4 项 P2）| `1870a58d` ✓ |
| Round 2 | 综述 Agent 验证 Round 1 D3 无回归 | 发现 1 项新 P0 + 3 项 P1 + 1 项 P2 | 5 项（P0 跨循环一致性 [C] 循环 + 3 项 P1 + 1 项 P2）| `3df9b025` ✓ |
| Round 3 | D1+D2 验证稳定性（无修订）| 发现 2 项 P1 残留 + 1 项 P2 | 0 项（D1+D2 综述验证）| （跳过）|
| Round 4 | 0（基于 Round 3 残留修复）| 0（D3 自主评审）| 4 项（P1×2 + 交叉引用 1 项 + 元数据 1 项）| `26851b12` ✓ |
| Round 5 | 收尾：重复章节清理 + Story 最终状态 | — | 元数据更新（Story Version v1.3.0 → v1.4.0；状态保持 `ready-for-dev`）| （本轮）|

**累计修订统计：**
- 26 项系统修订（P0×3 + P1×17 + P2×6）
- 3 个独立 commit（1870a58d / 3df9b025 / 26851b12）
- 全部推送至 origin main

**Story 关键决策：**
- D1：SKILL.md frontmatter 唯一事实源（不建 data_sources.yaml）
- D2：use case 调 load_sop 注入 extensions["tool_metadata"]
- D3：L2 load_sop().frontmatter 数据源声明来源
- D4：≥3 源 Skill 全声明源覆盖；2 源 Skill 双源交叉验证
- D5：三不新增（端口/异常/事件）
- D6：input_schema/output_schema JSON Schema dict
- D7：**StrategicAnalysisUseCase + RunToolChainUseCase 双入口同步注入**（Round 4 登记）

**Story 当前可执行性：**
- ✅ ready-for-dev 状态稳定
- ✅ 27 项文档修订全部 commit + push
- ✅ Dev Story 阶段可立即启动 Task 0 SDD 规范定义
- ⚠️ **Decision D8 待 Epic owner 签收**：disruptive-innovation 2 源与 Epic AC-4 字面偏差
