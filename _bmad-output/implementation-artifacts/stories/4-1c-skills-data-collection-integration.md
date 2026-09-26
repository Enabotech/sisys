# Story 4.1c: Skills 数据采集集成（外部数据型 Skills 完善）

**Status:** `ready-for-dev`

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
- **生产链路接线（关键缺口修复 — 双入口）**：
  - `StrategicAnalysisUseCase` 注入 `extensions["tool_metadata"]`（单 Skill 调用入口）
  - **`RunToolChainUseCase` 注入 `extensions["tool_metadata"]`（多 Skill 链路入口 — Round 1 D2 评审发现 RunToolChainUseCase 存在同类缺口）**
- Skills SOP 单元测试 ×6 + 集成测试 + 架构验证测试 + BDD 验收测试
- 4-1b 推迟项收敛：Marker 字符级扫描专项测试（`data_source_marker._string_literal_spans` 边界场景）

**不在本 Story 范围（明确划出）：**

- **新增数据源适配器 / UNSD / OECD** → 后续 Story（PoC v2 已验证不可用，故 disruptive-innovation 第 3 源 WIPO/EPO 推迟到 Story 4.1d 之后）
- **工具输出 Schema 强制验证执行（Pydantic 运行时校验）** → Story 4.3（本 Story 仅定义 frontmatter JSON Schema 契约，不实现运行时校验器）
- **10 个混合数据型 / 7 个内部框架 Skills** → Story 4.1d / 4.1e
- **数据源治理（配额管理/成本追踪/降级策略编排）** → 后续 Story
- **newsapi/tavily 适配器代码修改** → 无（Key 缺失降级行为仅在 SOP 中文档化）
- **`ToolChainService.execute_chain` 内部节点级 extensions 注入** → 本 Story 由 `RunToolChainUseCase` 调用点前置注入 ToolMetadata 字典后委托，避免侵入 Service 内部循环；如未来节点级独立 metadata 需求浮现则 Story 4.2 收敛

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

- [ ] `grep -rn "EXCEPTION_41[4-9]" src/` 确认 414-419 空闲但**本 Story 不使用**（防止实施中临时新增异常）
- [ ] BDD 异常路径场景纳入 Edge Cases（207/411/412 断言 `error.code` + `error.message`）

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

`run_tool_chain.py` 同步：line 99-109 `skill_metadata` dict 改为 `load_sop` 调用收集；line 114 前基于当前节点 `slug` 的 `ToolMetadata` 通过 `dataclasses.replace(context, extensions={"tool_metadata": node_metadata})` 委托 `execute_chain(context=context)`。`_service.execute_chain` 内部节点循环由 Story 4.2 收敛；本 Story 仅保证 UseCase 入口调用点已正确注入。

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
- [ ] 6 个 Skills 单元测试（`test_<slug>_4_1c.py`）断言白名单解析结果 == SSOT 表
- [ ] 声明 url ↔ 适配器 url 一致性断言通过
- [ ] 23 Skills 全量解析回归通过（含 17 个未触碰 Skill 空 tuple 断言）

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
- [ ] **StrategicAnalysisUseCase** 单元测试 4 场景（load_sop 注入 / 加载失败容错 / 无标记零行为变化 / 空白名单 207）
- [ ] **RunToolChainUseCase** 单元测试 3 场景（多节点并发 load_sop + 任一节点 metadata 注入 / 全部 load_sop 失败时 extensions = {} / 无节点零行为变化）— Round 1 D2 新增
- [ ] `ToolExecutionEngine.__init__` 签名不变（4.4 BDD AC-7.4 回归全绿）
- [ ] 既有 `test_acceptance_strategic_tool_impl` / `test_acceptance_docker_sandbox` 回归全绿
- [ ] **既有 tool_chain 链路验收测试** 零回归（双入口改动影响范围可控）

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
- [ ] 6 个 Skills 单元测试断言 SOP 必备章节存在 + input_examples 非 placeholder + 行数 ≤500
- [ ] frontmatter input_schema/output_schema 含 required 字段断言
- [ ] references/templates 文件存在性断言
- [ ] pestel 既有 references/scripts 资产引用断言（不破坏既有 L3 加载测试）

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
- [ ] 集成测试全绿（真实 Redis 不可用时 `pytest.skip()` 动态跳过）
- [ ] 三角化断言：5 个 Skill 注入源数 == 声明源数；disruptive-innovation == 2
- [ ] `pytest -n 8` 并行通过（`xdist_group("data-source-cache")`），连续 5 次无随机失败

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
- [ ] `tests/acceptance/test_acceptance_skill_data_collection_4_1c.feature`（`# language: zh-CN`，按 AC 分节）
- [ ] `tests/acceptance/test_acceptance_skill_data_collection_4_1c.py`（scenarios() + context dict + 共享 event_loop + 真实服务 + Fake 仅限适配器/LLM/Sandbox）
- [ ] 全部场景通过

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 本 Story 不新增领域事件（复用 `DataSourceFetched`/`DataSourceFetchFailed`），Task 0 显式登记该决策

#### 数据模型 (Data Models)
- [ ] 本 Story 不新增值对象/实体（复用 `DataSourceRef`/`ToolMetadata.data_sources`/`EvidencePackage.data_sources`）
- [ ] **6 个 Skills 的 `input_schema`/`output_schema` JSON Schema 字段级定义文档固化**（产出物：`tests/acceptance/contracts/skill_io_schemas_4_1c.yaml` 或 Story 文档独立子表）：
  - 每个 Skill 的 `input_schema.required` 字段（如 pestel-analysis 需 `industry` / `region_scope` / `time_horizon_years` 等）
  - 每个 Skill 的 `output_schema.required` 字段（如 `pestel_dimensions[]` / 各维度指标对象）
  - 字段类型（string / number / enum）+ description
- [ ] 字段级定义作为各 Skill TDD 红阶段断言输入（Task 2-7 [A] 循环断言 input_schema 含 required 字段）

#### 统一端口定义注册与管理 (Port Contract)
- [ ] 本 Story 不新增端口（显式决策）；复用 `DataSourcePort`/`DataSourceResolverPort`/`SkillLoaderPort`
- [ ] 禁止在服务文件中本地定义 Protocol / Port 抽象
- [ ] 既有端口契约测试回归全绿（`test_port_contract_data_source*.py`）

#### 端口契约清单执行约束（强制）
- [ ] 本 Story「端口与数据契约」节是唯一事实源（含 6 Skills 数据源声明 SSOT 表）
- [ ] 禁止新增未登记端口；禁止语义重复端口
- [ ] 6 Skills 声明与 SSOT 表逐字一致，实施期增删源必须先修订本 Story 文档

#### 领域异常契约 (Domain Exception Contract)
- [ ] 见「🎯 领域异常契约」节：不新增异常（显式决策），复用 201/207/101/302/411/412/413 + FrontmatterParseError + 387/388
- [ ] `grep -rn "EXCEPTION_41[4-9]" src/` 确认本 Story 零新增
- [ ] BDD 异常路径场景纳入 Edge Cases（207/411/412）

#### API 契约 (API Contract)
- [ ] 本 Story 不新增 REST 端点，无 `openapi.yaml` 变更（纯 Skills 内容 + 内部接线）

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
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_skill_data_collection_4_1c.feature`（`# language: zh-CN`）
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_skill_data_collection_4_1c.py`
- [ ] Happy Path + Edge Cases 全覆盖（白名单外 207 / 部分失败收敛 / Key 缺失降级 / 缓存命中 / 三角化断言 / 空白名单 207 共 6 个 Edge Cases）

**BDD 步骤实现约束：**
- 步骤函数使用场景级共享 `event_loop` + `run_until_complete()`（禁止 `@pytest.mark.asyncio`）
- 同一中文文本可能需要同时支持 given/when 装饰器
- Edge Cases 必须包含异常路径断言 `error.code` + `error.message`

**Task 0 完成标志：**
- [ ] 规范项全部定义完毕（6 Skills Schema 契约 + 声明 SSOT 表固化 + 接线方案评审）
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [ ] "不新增端口/异常/事件"三项显式决策已登记

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

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **应用层 ≥85%**（`make test-cov-application`，4-1b Round 1 已建分层门禁 `Makefile:278-291`）——本 Story 应用层改动仅限 `strategic_analysis.py` 接线 + 纯资源文件，接线分支（成功/容错/None）覆盖率 100%
- [ ] **关键路径 100%**：use case 接线全分支（load_sop 成功/失败容错/extensions 有无注入）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> 见「🎯 测试隔离约束」节全文。核心：TestTenant UUID 前缀、真实 Redis 测试端口 + delete_pattern 租户级清理、适配器一律 Stub/Fake、BDD 禁 @pytest.mark.asyncio、`xdist_group("data-source-cache")` 复用。

**验证要求：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

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
| Task 10 收尾 | `architecture.md` §17.3.3 关键架构决策表追加 6 项新决策（D1 frontmatter SSOT / D2 双入口注入 / D3 L1 vs L2 / D4 三角化务实 / D6 Schema 载体 / D7 双 UseCase 同步接线） | architecture.md | 决策表末尾 |
| Task 10 收尾 | `sisys-uni-exception-design.md` §3.3.2 追加 4-1c 复用声明段落："本 Story 复用 4-1b 既定 410-413/101/302/207/201 + FrontmatterParseError + 387/388 共 9 个异常编码，无新异常编码段（与 line 116 Task 0 grep EXCEPTION_41[4-9] 零碰撞验证对齐）" | sisys-uni-exception-design.md | §3.3.2 末尾或独立段落 |
| Task 10 收尾 | `architecture.md` 修订历史表追加新版本行 + 文档统计版本号/日期更新 | architecture.md | 文末修订历史 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部（AC-1 ~ AC-6 的规范输入）

> **目的：** 在进入内容实施前，固化 6 Skills 数据源声明 SSOT、input/output Schema 契约、接线方案、Gherkin 验收场景与"三不新增"决策登记。

- [ ] Subtask 0.1: 登记三项显式决策（不新增端口 / 不新增异常 / 不新增事件）+ 决策 D1（frontmatter SSOT，不建 data_sources.yaml）+ 决策 D4（三角化务实定义）
- [ ] Subtask 0.2: 定义 6 个 Skills 的 `input_schema`/`output_schema` JSON Schema 契约（字段级：required/properties/类型），作为 Task 2-7 红阶段断言输入
- [ ] Subtask 0.3: 评审接线方案（`strategic_analysis.py` load_sop + extensions 注入），确认 `load_metadata` 原调用点无其他副作用依赖
- [ ] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_skill_data_collection_4_1c.feature`（Happy Path + 6 个 Edge Cases）
- [ ] Subtask 0.5: 编写 BDD 步骤实现骨架 `tests/acceptance/test_acceptance_skill_data_collection_4_1c.py`（scenarios() + context + 共享 event_loop + Fake 适配器）
- [ ] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证，失败原因 = 白名单声明未填写/接线未实施）
- [ ] Subtask 0.7: 确认 6 个声明源的 url 与适配器 `get_metadata().url` 实际值（逐一解析 8 个适配器，固化进 SSOT 表"适配器 url/api_type/ttl/confidence 对齐表" — Round 1 D1-C 视角已固化）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕（Schema 契约 + SSOT 表 + 接线方案 + 三项决策登记）
- [ ] **SSOT 表 url/api_type/ttl/confidence 四列均已从 8 个适配器 `get_metadata()` 实际值固化**（含 pestel-analysis 6 源、porters 3 源、appeals 3 源、competitor 4 源、scenario 3 源、disruptive-innovation 2 源的 url 对齐）
- [ ] 验收测试运行失败（预期行为，红阶段确认）

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

- [ ] Subtask 1.1: 🔴 红 — 编写 StrategicAnalysisUseCase 接线失败测试（4 场景）
- [ ] Subtask 1.2: 🟢 绿 — 实现 StrategicAnalysisUseCase 接线（最小改动，不动 Engine/Loader 接口）

#### TDD 循环 [B]：RunToolChainUseCase.load_sop + extensions 注入（Round 1 新增）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/use_cases/test_run_tool_chain_datasource.py`（多节点并发 load_sop + 任一节点 metadata 注入 / 全部 load_sop 失败时扩展 = {} / 无节点时零行为变化） |
| 🟢 绿 | 修改 `src/application/use_cases/run_tool_chain.py`（line 99-109 `skill_metadata` dict 改为 `load_sop` 调用收集，并基于当前节点 ToolMetadata 通过 `dataclasses.replace()` 注入 `context.extensions["tool_metadata"]` 再委托 `execute_chain`） |
| 🔄 重构 | 工具链既有验收测试 `test_acceptance_strategic_tool_impl` / `test_acceptance_docker_sandbox` 全量回归，ruff + mypy |

- [ ] Subtask 1.3: 🔴 红 — 编写 RunToolChainUseCase 接线失败测试（3 场景：每节点 metadata 注入 / 失败容错 / 无节点零变化）
- [ ] Subtask 1.4: 🟢 绿 — 实现 RunToolChainUseCase 接线（`load_sop` 替换 `load_metadata` + 扩展注入，最小改动，不动 `ToolChainService` 内部接口）
- [ ] Subtask 1.5: 🔄 重构 — 全量回归（`pytest tests/unit/application/use_cases/ tests/acceptance/`）
- [ ] Subtask 1.6: 验证 `ToolExecutionEngine.__init__` 签名不变（4.4 BDD AC-7.4 回归）

**完成标准/Definition of Done:**
- [ ] 双入口接线实现完成，7 场景单测全绿
- [ ] 4.1a/4.4 既有测试零回归
- [ ] 应用层覆盖率 ≥85%（接线分支 100%）

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

- [ ] Subtask 2.1: 🔴 红 — 编写 frontmatter 声明失败测试
- [ ] Subtask 2.2: 🟢 绿 — 填充 frontmatter（data_sources/Schema）
- [ ] Subtask 2.3: 🔴 红 — 编写 SOP 内容失败测试
- [ ] Subtask 2.4: 🟢 绿 — 编写 SOP + references + templates（整合既有 scoring_matrix/aggregate_scores 引用）
- [ ] Subtask 2.5: 🔄 重构 — 行数 ≤500 + 回归全绿

**完成标准/Definition of Done:**
- [ ] pestel-analysis 声明与 SOP 成熟化完成，单测全绿
- [ ] 既有 L3 资产测试零回归

---

### Task 3: porters-five-forces Skill 成熟化

**关联 AC:** AC-1, AC-3

> **数据源（SSOT）：** `newsapi` + `world-bank` + `eurostat`（3 源）
> **SOP 核心：** 五力评分方法论 + 行业问卷模板；Key 缺失降级话术（newsapi）

#### TDD 循环 [A]/[B]：同 Task 2 结构（frontmatter 声明 → SOP 内容）

- [ ] Subtask 3.1: 🔴 红 — 编写 `test_porters_five_forces_4_1c.py` 声明失败测试
- [ ] Subtask 3.2: 🟢 绿 — 填充 frontmatter（data_sources/Schema）
- [ ] Subtask 3.3: 🔴 红 — 编写 SOP 内容失败测试
- [ ] Subtask 3.4: 🟢 绿 — 编写 SOP + references（五力评分锚点/三角化规范/工作坊引导）+ templates（行业问卷）
- [ ] Subtask 3.5: 🔄 重构 — 行数 ≤500 + 回归全绿

**完成标准/Definition of Done:**
- [ ] porters-five-forces Skill 声明与 SOP 成熟化完成，单测全绿
- [ ] 行数 ≤500 约束验证通过（Task 9.4 架构测试兜底）
- [ ] 23 Skills 解析回归零失败

---

### Task 4: appeals-analysis Skill 成熟化

**关联 AC:** AC-1, AC-3

> **数据源（SSOT）：** `tavily` + `newsapi` + `china-nbs`（3 源）
> **SOP 核心：** $APPEALS 8 维度评估 + 顾客问卷模板；Key 缺失降级话术（tavily/newsapi）

- [ ] Subtask 4.1: 🔴 红 — 编写 `test_appeals_analysis_4_1c.py` 声明失败测试
- [ ] Subtask 4.2: 🟢 绿 — 填充 frontmatter（data_sources/Schema）
- [ ] Subtask 4.3: 🔴 红 — 编写 SOP 内容失败测试
- [ ] Subtask 4.4: 🟢 绿 — 编写 SOP + references（8 维度评分锚点/工作坊引导）+ templates（顾客问卷）
- [ ] Subtask 4.5: 🔄 重构 — 行数 ≤500 + 回归全绿

**完成标准/Definition of Done:**
- [ ] appeals-analysis Skill 声明与 SOP 成熟化完成，单测全绿
- [ ] 行数 ≤500 约束验证通过（Task 9.4 架构测试兜底）
- [ ] 23 Skills 解析回归零失败

---

### Task 5: competitor-analysis Skill 成熟化

**关联 AC:** AC-1, AC-3

> **数据源（SSOT）：** `newsapi` + `uspto` + `tavily` + `china-nbs`（4 源）
> **SOP 核心：** 竞品对标矩阵 + 竞品调研方法论；专利维度（USPTO）采集引导

- [ ] Subtask 5.1: 🔴 红 — 编写 `test_competitor_analysis_4_1c.py` 声明失败测试
- [ ] Subtask 5.2: 🟢 绿 — 填充 frontmatter（data_sources/Schema）
- [ ] Subtask 5.3: 🔴 红 — 编写 SOP 内容失败测试
- [ ] Subtask 5.4: 🟢 绿 — 编写 SOP + references（对标矩阵评分锚点/竞品调研工作坊）+ templates（竞品对标矩阵）
- [ ] Subtask 5.5: 🔄 重构 — 行数 ≤500 + 回归全绿

**完成标准/Definition of Done:**
- [ ] competitor-analysis Skill 声明与 SOP 成熟化完成，单测全绿
- [ ] 行数 ≤500 约束验证通过（Task 9.4 架构测试兜底）
- [ ] 23 Skills 解析回归零失败

---

### Task 6: scenario-planning Skill 成熟化

**关联 AC:** AC-1, AC-3

> **数据源（SSOT）：** `tavily` + `ipcc` + `eurostat`（3 源）
> **SOP 核心：** 4 情景剧本方法论 + 情景工作坊引导；气候情景维度（IPCC）采集引导

- [ ] Subtask 6.1: 🔴 红 — 编写 `test_scenario_planning_4_1c.py` 声明失败测试
- [ ] Subtask 6.2: 🟢 绿 — 填充 frontmatter（data_sources/Schema）
- [ ] Subtask 6.3: 🔴 红 — 编写 SOP 内容失败测试
- [ ] Subtask 6.4: 🟢 绿 — 编写 SOP + references（情景构建方法论/不确定性矩阵锚点）+ templates（情景剧本框架）
- [ ] Subtask 6.5: 🔄 重构 — 行数 ≤500 + 回归全绿

**完成标准/Definition of Done:**
- [ ] scenario-planning Skill 声明与 SOP 成熟化完成，单测全绿
- [ ] 行数 ≤500 约束验证通过（Task 9.4 架构测试兜底）
- [ ] 23 Skills 解析回归零失败

---

### Task 7: disruptive-innovation Skill 成熟化

**关联 AC:** AC-1, AC-3

> **数据源（SSOT）：** `uspto` + `tavily`（2 源，双源交叉验证 — 决策 D4；Epic AC-4 ≥3 源字面偏差由 Epic owner 签收）
> **SOP 核心：** 技术成熟度评估 + 专家访谈引导；颠覆性技术专利信号（USPTO）采集引导

- [ ] Subtask 7.1: 🔴 红 — 编写 `test_disruptive_innovation_4_1c.py` 声明失败测试
- [ ] Subtask 7.2: 🟢 绿 — 填充 frontmatter（data_sources/Schema）
- [ ] Subtask 7.3: 🔴 红 — 编写 SOP 内容失败测试
- [ ] Subtask 7.4: 🟢 绿 — 编写 SOP + references（技术成熟度锚点/颠覆信号清单/专家访谈提纲）+ templates（技术评估矩阵）
- [ ] Subtask 7.5: 🔄 重构 — 行数 ≤500 + 回归全绿

**完成标准/Definition of Done:**
- [ ] disruptive-innovation Skill 声明与 SOP 成熟化完成，单测全绿
- [ ] 行数 ≤500 约束验证通过（Task 9.4 架构测试兜底）
- [ ] 23 Skills 解析回归零失败（特别注意，本 Skill 2 源覆盖 D4 双源交叉验证语义）

---

### Task 8: 集成测试（真实服务 + 三角化 + 新鲜度）+ Marker 专项收敛

**关联 AC:** AC-4

> **性质说明：** 真实 Engine + 真实 Resolver + 真实 Redis（测试端口）；Mock 仅限 LLM/Sandbox/数据源适配器（Stub 可编程替身注入 adapters Mapping，规避 R1 条件注册依赖）。

#### 集成测试实现

- [ ] Subtask 8.1: 🔴 红 — 编写 `tests/integration/application/test_skill_data_collection_4_1c.py` 骨架（`pytestmark = [pytest.mark.integration, pytest.mark.xdist_group("data-source-cache")]` + 租户隔离 fixture + Stub 适配器工厂 + AsyncMock LLM 按 Skill 生成含标记代码）
- [ ] Subtask 8.2: 🟢 绿 — 6 个 Skills 全链路用例（每 Skill ≥1 源采集 + EvidencePackage.data_sources 溯源元数据断言）
- [ ] Subtask 8.3: 🟢 绿 — 三角化断言（5 个 ≥3 源 Skill 注入源数 == 声明源数 + 每源 call_count == 1；disruptive-innovation == 2）+ 新鲜度评分 ∈ [0,1] + 缓存命中二次执行外部调用不增
- [ ] Subtask 8.4: 🟢 绿 — Key 缺失降级用例（adapters Mapping 缺 newsapi/tavily 时部分失败收敛，其余源正常注入）
- [ ] Subtask 8.5: 🔄 重构 — **Marker 字符级扫描专项测试收敛（4-1b 推迟项）**：扩充 `tests/unit/application/services/test_data_source_marker.py`（未闭合字符串降级/三引号字符串字面量扫描/转义字符边界/字符串字面量内伪标记不触发）+ 同步更新 `src/application/services/data_source_marker.py:_string_literal_spans` 文档注释对齐 4-1b P0-5 修复范围
- [ ] Subtask 8.6: 🔄 重构 — `pytest -n 8` 并行验证 + 连续 5 次无随机失败

**完成标准/Definition of Done:**
- [ ] 集成测试全绿（真实 Redis 不可用时动态 skip）
- [ ] 三角化/新鲜度/缓存/降级断言全部通过
- [ ] Marker 专项测试收敛（4-1b 推迟项清零）
- [ ] 并行稳定（-n 8 连续 5 次零随机失败）

---

### Task 9: SDD 架构约束验证测试

**关联 AC:** AC-5

> **性质说明：** SDD 规范验证测试（非 TDD 单元测试）。范本 `tests/unit/architecture/test_arch_data_source.py`（五类结构）。

#### 架构验证测试实现

- [ ] Subtask 9.1: 创建 `tests/unit/architecture/test_arch_skill_data_collection_4_1c.py`（常量区：6 Skills slug 清单 + SSOT 声明表 + 8 适配器映射）
- [ ] Subtask 9.2: 实现三方一致性校验（SSOT 表 ↔ 6 个 SKILL.md frontmatter data_sources ↔ 适配器 `get_metadata()` name/url/api_type）
- [ ] Subtask 9.3: 实现依赖方向校验（`strategic_analysis.py` 不 import infrastructure；本 Story 零 domain 改动声明校验）+ `ToolExecutionEngine.__init__` 签名锁定（inspect.signature）
- [ ] Subtask 9.4: 实现 Skills 内容约束校验（6 个 SKILL.md ≤500 行 + frontmatter 必需字段 + 17 个非目标 Skill data_sources 空 tuple）
- [ ] Subtask 9.5: 运行完整测试套件并生成合规报告

**完成标准/Definition of Done:**
- [ ] 所有架构约束测试通过
- [ ] 任何违规导致测试失败（三方漂移/签名变更/行数超限均已验证可检出）
- [ ] 循环依赖检测使用 ruff/isort（不引入额外工具）

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

- [ ] Subtask 10.1: 场景 1 — Happy Path：pestel-analysis 全链路（6 源并发采集 + 注入 + 溯源元数据）
- [ ] Subtask 10.2: 场景 2 — Happy Path：其余 5 个 Skills 各自采集链路参数化验证
- [ ] Subtask 10.3: 场景 3 — Edge：白名单外数据源 → BusinessRuleViolationError(207)，断言 error.code + error.message
- [ ] Subtask 10.4: 场景 4 — Edge：数据源不可用 → 部分失败收敛 + DataSourceFetchFailed 事件
- [ ] Subtask 10.5: 场景 5 — Edge：Key 缺失降级（newsapi/tavily 未注册 → 411 语义部分失败，其余源正常）
- [ ] Subtask 10.6: 场景 6 — Edge：缓存命中（二次执行 cache_hit=True，外部调用次数不增）+ 新鲜度元数据
- [ ] Subtask 10.7: 场景 7 — Edge：未成熟化 Skill（data_sources 空 tuple）含标记 → 207（安全失败）
- [ ] Subtask 10.8: 场景 8 — 三角化断言：≥3 源 Skill 注入源数 ≥3，disruptive-innovation == 2
- [ ] Subtask 10.9: 运行开发结束验收测试并确认通过 + 配套文档同步（architecture.md §17.3 状态 + §17.3.3 追加 + 修订历史）+ 完成清单逐项确认（src + tests 各层）
- [ ] Subtask 10.10: 运行 `pytest`、`ruff check`、`mypy` 收尾校验

**完成标准/Definition of Done:**
- [ ] 全部 Gherkin 场景通过（8 场景）
- [ ] 配套文档同步完成
- [ ] 完成清单逐项验证确认
- [ ] Story 可进入 `done`

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
- [ ] 接线改动不触碰 Engine `__init__`，复用 4-1b 既定 extensions 契约
- [ ] 5 个声明含 newsapi/tavily 的 Skill 在 SOP 失败处理章节文档化 Key 缺失降级话术
- [ ] BDD/集成测试沿用 4-1b 基建（共享 event_loop、xdist_group、租户前缀 delete_pattern、_FakeDataSourceAdapter 范本）
- [ ] Marker 字符级扫描专项测试在 Task 8.5 收敛（4-1b 推迟项清零）
- [ ] Task 10 同步 architecture.md（§17.3 状态 + §17.3.3 追加 + 修订历史），对齐 4-1b 文档同步先例

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

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/4-1c-skills-data-collection-integration.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/application/skills/<slug>/SKILL.md` ×6 — [修改] frontmatter 声明 + SOP 成熟化
- `src/application/skills/<slug>/references/*.md` ×6 组 — [新增] 三角化规范/评分锚点/工作坊引导
- `src/application/skills/<slug>/templates/*` ×6 组 — [新增] 采集问卷/矩阵模板
- `src/application/use_cases/strategic_analysis.py` — [修改] 唯一应用层代码改动（load_sop + extensions 注入）
- `tests/unit/application/skills/test_<slug>_4_1c.py` ×6 — Skills 内容单元测试
- `tests/unit/application/use_cases/test_strategic_analysis_datasource.py` — 接线单元测试
- `tests/unit/application/services/test_data_source_marker.py` — [修改] 字符级扫描专项扩充
- `tests/unit/architecture/test_arch_skill_data_collection_4_1c.py` — 架构验证测试
- `tests/integration/application/test_skill_data_collection_4_1c.py` — 集成测试
- `tests/acceptance/test_acceptance_skill_data_collection_4_1c.feature` + `.py` — BDD 验收测试

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

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 本 Story 经过 `bmad-review-adversarial-general` 5 轮 D1-D5 迭代审查，记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|---------|
| **D-R1-P0** | **RunToolChainUseCase 同类接线缺口未修补** | **P0** | Story 范围澄清节显式登记 + Task 1 扩展为 TDD [A]+[B] 双循环 + AC-2 验证标准追加 3 场景 + DoD 双入口覆盖 + R3 风险描述重写为"双入口接线" |
| **D-R1-P0** | **Task 3-7 缺 DoD 节** | P1 | 每个 Skill Task 末尾追加统一模板 DoD 节（行数约束 + 单测全绿 + 23 Skills 回归零失败） |
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
| **D-R1-P2** | **6 个目标 Skill references/templates 目录全空 vs Story 描述** | P2 | Story 范围澄清节追加"当前 5 个非 pestel 目标 Skill 的 references/scripts 为空目录、templates 全无，本 Story Task 2-7 实施期新建" |
| **D-R1-P2** | **frontmatter 示例 required_fields 缺字段来源注释** | P2 | 示例下方添加"对齐 4-1b DataSourceRef.required_fields" 注释 |
| **D-R1-P2** | **D1 决策依据未附文件:行号** | P2 | 决策表 D1 依据补充"4.1a TOOL_CATALOG 单一数据源原则 — `_bmad-output/implementation-artifacts/stories/4-1a-strategic-tool-impl.md`" |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

> 待 dev-story 实施后填写。

#### 需决策 Decision Needed

- [ ] **Decision D8（待 Epic owner 签收）**：disruptive-innovation 2 源（USPTO + Tavily）与 Epic AC-4 "每个指标 ≥3 独立来源" 字面偏差——本 Story 选择务实双源交叉验证（D4 决策），需 Epic owner 显式签收或追加 WIPO/EPO 适配器到下个 Story

#### 已修复 Patch

- [ ] 无（待 dev-story 实施）

#### 已推迟 Defer

- [ ] P2-domain-1：异常 `to_dict()` 自动脱敏（Story 5.x 安全专项）
- [ ] Marker 字符级扫描专项测试扩展（Task 8.5 收敛）
- [ ] `ToolChainService.execute_chain` 内部节点级 extensions 注入（Story 4.2 工具链编排范畴）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] Story Round 1 文档审查完成（D1-D2 D2 评审 + D3 系统修订 17 项修复）
- [ ] Epic owner 签收 D8 决策
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.1.0
**创建日期/Created:** 2026-09-26
**最后更新/Last Updated:** 2026-09-26
**更新说明/Description:**
- v1.0.0: 创建故事文件（基于 epics_v1.0.md Story 4.1c + 4-1b 完成资产 + 3 视角并行代码调研 + 生产链路缺口核实）
- v1.1.0: bmad-doc-review Round 1 完成：
  - **D1 调研**：3 Agent 并行（StrategicAnalysisUseCase 接线 / Skills 系统现状与ACES 规范 / 4-1b 资产与异常继承）
  - **D2 评审**：3 Agent 并行（叙事一致性 + 科学性可行性 + CLAUDE.md 合规性）
  - **D3 系统修订**：17 项修复（含 P0-1 双入口接线缺口 / P0-2 跨循环一致性 / 14 项 P1 修复 / 4 项 P2 修订）
  - **关键发现**：`RunToolChainUseCase`（`run_tool_chain.py:104-106`）存在同类 wiring 缺口，被 3 Agent 独立发现（最高优先级 P0 修复）
  - 验证：ruff 全绿 + 三条红线零输出（CLAUDE.md §5）+ 文档内 line 引用全部基于 D1 实测（composition_root 行号偏差已修正）
