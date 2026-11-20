# Story 7.1: CLI 命令行接口（统一 sisys 入口）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 企业战略人员,
**I want** 通过统一 `sisys` CLI 执行命令（文档上传/Agent 调用/规划生成/Checkpoint 恢复）,
**So that** 高效操作系统，且 LLM Agent 能以 CLI 为母语言 100% 触达六大服务模块。

### 业务价值

- **Epic 定位：** Epic 7（多触点用户界面与 API 集成）首个 Story，P0-1 优先级入口故事。interface-design.md 实施路线图（:2071-2080）钦定 Story 7.1 交付三件：**6 个服务模块命令骨架 + CLI 基础框架（typer）+ Command Translator（CLI → ApplicationCommand）**。
- **价值组：** 多触点操作与监控能力——用户（人类与 LLM Agent）通过 CLI 操作系统。
- **现状缺口：** 现有 CLI 仅为 `sisys-agent`（argparse，19 子命令，`src/entrypoints/agent_cli.py`）与 `sisys-ocr` 两进程入口；**document/tool 两模块 CLI 面为零**；全仓无统一 `sisys` 主命令；`--yes/--dry-run/--mock` 与 `--format json/table/pretty` 全局参数缺失；`src/interfaces/cli/formatters/` 为空目录。
- **覆盖 FR：** FR-UI-01（CLI 接口）、FR-IF-01（CLI 七原则合规——P1/P4/P7 承载面）；NFR-IF-01（CLI 响应性能）。

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 统一 CLI 入口与命令解析契约

**Given** sisys CLI 已安装（pyproject `[project.scripts]` 注册 `sisys` 入口）
**When** 执行 `sisys --help` 或 `sisys <service> --help`
**Then** 三级命令结构（`sisys <service> <resource> <action>`）自描述完整，document/tool/agent/plan/checkpoint/archive 六模块命令组全部可见
**And** 退出码契约冻结：**0=成功（含空态）/ 1=DomainError（stderr 输出 `[EXCEPTION_NNN] message`）/ 2=用法错误（参数缺失、非法枚举值）**
**And** 存量入口 `sisys-agent` / `sisys-ocr` 零回归（既有单测/验收全绿，存量入口冻结不改动）

**验证标准/Validation Criteria:**
- [ ] `sisys --version` / `sisys --help` / 六模块 `--help` 全部 exit 0 且输出含模块说明
- [ ] 未知命令 / 缺必填参数 / 非法 `--format` 值 → exit 2
- [ ] DomainError → stderr `[EXCEPTION_NNN] message` 格式 + exit 1（与 agent_cli 既有契约逐字一致）
- [ ] 既有 `tests/unit/interfaces/cli/test_agent_cli.py`（4294 行）与 14 个 CLI 形态验收文件零改动零失败

### AC-2: 四大核心工作流端到端

**Given** 系统真实服务（PG/Redis 等）可用且组合根可 bootstrap
**When** 依次执行四条核心工作流命令
**Then** 命令正确解析并真实执行，输出执行结果与进度反馈
- `sisys document upload --file <path> [--business-domain <name>]` → 真实服务上传，输出 document_id
- `sisys document parse --id <doc-id>` → 真实解析链
- `sisys agent run <role> --task <text> --mock --yes --cost-budget <amount>` → Mock 响应模式返回结构化结果
- `sisys plan generate --agent-id <id> --task <text> --mock --yes --cost-budget <amount>` → Mock 响应模式
- `sisys checkpoint recover --id <cp-id> --yes --cost-budget <amount>` → 真实恢复链

**验证标准/Validation Criteria:**
- [ ] document upload/parse 验收场景走真实服务（真实临时文件 → 真实落库 → teardown 定向清理）
- [ ] agent run / plan generate 真实 LLM 面动态跳过（无 Key 环境 `pytest.skip()`），Mock 面（`--mock`）确定性全绿
- [ ] checkpoint recover 验收场景真实链（given 前置真实创建 checkpoint → recover → 断言恢复结果）

### AC-3: 全局参数与 Agent 模式参数契约

**Given** sisys CLI 任一命令
**When** 附加全局参数
**Then** 以下契约生效（interface-design.md §4.4 参数规范冻结）：
- `--yes`：Agent 模式开关。**设置 `--yes` 时必须显式提供 `--cost-budget`，缺失 → 拒绝执行**（ValidationError EXCEPTION_201，stderr 呈现，exit 1）
- `--dry-run`：接口层预览——打印命令解析结果与将调用的用例端口名，**不 bootstrap、不执行**
- `--mock`：Mock 响应模式——controller 短路返回结构化 mock DTO，**不 bootstrap**（面向 LLM 自测与验收确定性；守卫校验仍先于短路执行）
- `--format json|table|pretty`：全命令支持，默认 `table`
- Agent 专用（tool run / tool chain run / agent run / plan generate / checkpoint recover）：`--session <id>`（缺省自动生成 UUID）、`--timeout <seconds>`（缺省 300）、`--cost-budget <amount>`

**验证标准/Validation Criteria:**
- [ ] `--yes` 无 `--cost-budget` → EXCEPTION_201 + exit 1（全 Agent 专用命令一致）
- [ ] `--dry-run` 输出含端口名与归一后参数，且无 bootstrap 副作用（可用 stub resolve 断言零调用）
- [ ] `--mock` 输出为合法 JSON（`--format json` 组合）且零外部服务依赖
- [ ] `--session`/`--timeout` 透传至用例执行上下文

### AC-4: 三态输出格式化器

**Given** 任一命令产生结果 DTO
**When** 指定 `--format json|table|pretty`
**Then** `src/interfaces/cli/formatters/` 三格式化器正确渲染：
- `json`：合法 JSON 单文档输出（可 pipe 给 jq / LLM 直接消费）
- `table`：人类可读表格（列宽自适应，参照 agent_cli `_print_*` 两遍法先例）
- `pretty`：终端美化输出（分组+缩进）

**验证标准/Validation Criteria:**
- [ ] 三格式化器单元测试覆盖：空列表、单条、多条、中文列宽、嵌套字段
- [ ] `json` 输出经 `json.loads` 可解析（验收场景断言）
- [ ] 非法 format 值 → exit 2（typer Enum choice 守卫）

### AC-5: 六模块 100% CLI 入口覆盖（P1 原则）

**Given** sisys 统一入口
**When** 审计六大服务模块命令入口
**Then** 冻结命令矩阵（12 命令，Task 0 冻结表）全部可用，document/tool 两模块 CLI 面从零到一：

| 模块 | 命令 | 消费端口（组合根注册名，已核验行号） |
|------|------|------|
| document | `upload` | `document_upload_service`（composition_root.py:1189） |
| document | `parse` | `document_parsing_service`（:1371） |
| tool | `list` | `tool_registry_service`（:2598） |
| tool | `schema <tool-id>` | `tool_registry_service.get_tool` + skill L1 元数据 |
| tool | `run <tool-id>` | `tool_execution_service`（:2741，`execute(tool_id, tool_call, context)`） |
| tool | `chain run <chain-id>` | `run_tool_chain_use_case`（:2945，`execute(chain_name, parameters, context)`） |
| agent | `run <role>` | `agent_workflow_use_case`（:3178） |
| plan | `generate` | `blm_planning_use_case`（:3518，`execute(agent_id, task, plan_id)`） |
| checkpoint | `list --plan-id` | `checkpoint_list_use_case`（:2524） |
| checkpoint | `show --id` | `checkpoint_use_case`（:2496） |
| checkpoint | `recover --id [--mode]` | `checkpoint_recovery_use_case`（:2508） |
| archive | `query --plan-id` | `blm_chain_trace_use_case`（:2567） |

**验证标准/Validation Criteria:**
- [ ] 12 命令 `--help` 全部 exit 0
- [ ] 轻量真实链验收：`tool list` / `tool schema` / `checkpoint list` / `archive query` 真实服务执行
- [ ] P1 审计断言：契约测试逐一断言 12 端口 `resolve()` 可达（接线断言清单）

### AC-6: CLI 七原则合规承载（FR-IF-01）

**Given** sisys CLI 已安装并配置完成
**When** 验证 CLI 接口合规性
**Then** 满足以下验收标准（epics_v1.0.md:2610-2622 冻结）：
- **P1**（本 Story 核心）：内部工具 100% 有 CLI 入口，覆盖 document/tool/agent/plan/checkpoint/archive 6 个服务模块（AC-5 承载）
- **P4**：MCP 退居生态层——MVP 阶段 MCP 相关代码量 = 0（架构测试断言：无 `src/infrastructure/mcp/` 目录、pyproject 无 mcp 依赖、全仓无 mcp import）
- **P7**：input_examples 驱动——skill frontmatter 新增 `input_examples` 字段（1-5 条约束校验），`sisys tool schema` 输出该字段，全量 active skills（TOOLS.md 视图 23 条口径）每工具补齐 ≥1 条示例
- **P5/P6**（注记锚，OD-1）：SkillSelector 已于 Story 5-2 交付（`skill_selector` 端口）；「工具选择准确率≥85% / 误触发率<5%」属评估指标面，7-1 不重复建设，锚定 evaluation 专项（`evaluation_harness` 已有基建）

**验证标准/Validation Criteria:**
- [ ] P4 架构断言测试通过（`test_arch_unified_cli.py`）
- [ ] frontmatter `input_examples` 字段校验单测（非 list/超 1-5 条 → EXCEPTION_201 族校验异常）
- [ ] `sisys tool schema <tool-id> --format json` 输出含非空 `input_examples`
- [ ] 全量 active skills 的 SKILL.md frontmatter 含 1-5 条 input_examples（校验器全量跑批断言）

### AC-7: 输入守卫与入口环境装配

**Given** sisys CLI 接收用户/Agent 输入
**When** 输入非规范形态
**Then** 守卫契约生效：
- **UUID canonical 归一**（6.9-R1-DF1 新面清偿）：`--plan-id`/`--id` 等 UUID 参数经共享守卫 `str(uuid.UUID(value))` 归一——大写/URN/无连字符等非 canonical 形态归一后正确命中（与存量 agent_cli 宽松守卫静默空态形成对照）；非 UUID 守卫按参数族分契约：**plan-id 族 → EntityValidationError 242、agent-id 族 → ValidationError 201**（agent_cli 既有分工，R1-F18/_parse_agent_uuid 先例），均 exit 1
- **.env 入口加载**（6.8-R1-DF1 新面清偿，方案一定谳）：`src/entrypoints/main_cli.py` 在 bootstrap 前显式 `load_dotenv`（显式路径，`usecwd=False`）——`python -m src.entrypoints.main_cli` 形态下 .env 注入不再依赖 litellm import 副作用
- 枚举值（--format/--mode 等）由 typer choice 守卫 → exit 2

**验证标准/Validation Criteria:**
- [ ] 大写 UUID 输入 → 归一后真实查询命中（非静默空态）验收场景
- [ ] 非 UUID → plan-id 族 EXCEPTION_242 / agent-id 族 EXCEPTION_201，均 exit 1
- [ ] 单测断言 main_cli 中 load_dotenv 先于 bootstrap 调用（顺序守卫）
- [ ] 非法 `--format`/`--mode` 值 → exit 2

### AC-8: 性能与并发口径

**Given** sisys CLI 框架
**When** 性能采样与并发测试
**Then** NFR-IF-01 V1 口径满足：
- **框架开销 P95 < 500ms**（20 轮采样口径，epics 钦定）：口径锚定**命令解析+装配+格式化路径**（`--help`/`--dry-run`/轻量查询）；重 LLM 命令（agent run/plan generate 真实面）响应时长由各自用例性能窗承载（BLM 60s 窗先例），不在此口径（OD 注记）
- **并发执行 10 个 CLI 命令**：10 个轻量子进程并发全部成功（exit 0）

**验证标准/Validation Criteria:**
- [ ] 验收性能场景：20 轮 `--dry-run` 采样 P95 < 500ms
- [ ] 验收并发场景：10 并发子进程全部 exit 0
- [ ] 可用性≥99% 口径为运维面指标，7-1 以退出码契约+零回归承载（注记）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [x] **本 Story 零新增领域事件**——CLI 是接口层薄壳，领域事件由所消费用例既有发布（ToolExecuted/CheckpointRecovered 等），事件面不变
- [ ] 核验：`configs/event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` 零 diff（无新事件则零改动）

#### 数据模型 (Data Models)
- [ ] **命令对象（Command Translator 载体，DC-4）**：`@dataclass(frozen=True)` 命令值对象定义于各 controller 模块（如 `DocumentUploadCommand`/`ToolRunCommand`/`CheckpointRecoverCommand`），字段=CLI 参数归一后形态（UUID 转 `uuid.UUID`、金额转 `Decimal`、超时转 `int`）
- [ ] **不新建 `src/application/commands/` 包**——路线图「CLI → ApplicationCommand」以接口层命令对象+controller 转换函数承载（YAGNI；application 现无 commands 目录，全仓用例为直接方法签名）
- [ ] **Mock DTO 契约**：`--mock` 短路返回结构固定（`{"mock": true, "command": "<命令名>", "parameters": {...}, "session": "<id>"}`），三格式化器均可渲染

#### 统一端口定义注册与管理 (Port Contract)
- [x] **本 Story 零新增端口**——仅消费既有端口（AC-5 表 12 端口名已核验组合根行号）
- [ ] 端口消费契约测试：`tests/contracts/test_port_contract_unified_cli.py`——逐一断言 12 端口 bootstrap 后 `resolve()` 可达且 isinstance 契约成立（接线断言清单载体；防注册名漂移——6.4-DF2 同族守卫诉求在 CLI 消费面的落地）
- [ ] 控制器依赖注入方向（DC-2）：`src/interfaces/cli` **禁止 import `src.composition_root`**（importlinter 传导禁令，.importlinter:72-78 注释钦定）；采用 `create_cli_app(resolve: Callable[[str], Any]) -> typer.Typer` 工厂——resolve 函数由 `src/entrypoints/main_cli.py` 装配层传入，interfaces 层零组合根知识
- [ ] 跨模块调用仅依赖抽象：controllers 类型注解引用 application 层用例类/Protocol（interfaces → application 方向合法）

#### 端口契约清单执行约束（强制）
- [ ] AC-5 表是唯一事实源（Single Source of Truth）——12 端口名冻结，实现 Task 禁止改用其他注册名或绕过 resolve 直构实例
- [ ] 禁止新增未登记端口，禁止语义重复端口
- [ ] 契约测试与接线断言未通过不得进入实现 Task 收尾

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增/修改的领域异常必须在 Task 0 中完成设计，禁止在实现 Task 中临时定义。

- [x] **本 Story 零新增领域异常**（`src/domain/exceptions/` 零 diff）——消费既有异常体系：

| 异常 | code | 触发场景（本 Story） | 既有锚 |
|------|------|---------------------|--------|
| `EntityValidationError` | EXCEPTION_242 | `--plan-id`/`--id`（checkpoint）等 plan-id 族非 UUID 守卫（R1-F18 统一形态——chain-query 先例 agent_cli.py:1129-1141，6.9-R1-DF1 命令族契约） | business_exceptions.py:106 |
| `ValidationError` | EXCEPTION_201 | `--agent-id` 非 UUID 守卫（`_parse_agent_uuid` 先例 agent_cli.py:156-173）；Agent 模式 `--yes` 缺 `--cost-budget` 拒绝；frontmatter `input_examples` 校验失败 | business_exceptions.py:20 |
| （用例透传） | 482 等 | plan 重跑守卫等由用例层抛出，CLI 只呈现 | blm_planning 既有 |

> **守卫分工注记：** CLI 层双 UUID 守卫契约与 agent_cli 既有分工一致——plan-id 族走 242、agent-id 走 201（ocr_cli D8 清偿后模式：int 转换→201 先例）；新统一入口按参数族对应采用，禁止混用。

- [ ] 消息安全性：CLI stderr 呈现复用 agent_cli 既有格式 `[{code}] {message}`（不泄露堆栈/SQL）
- [ ] 退出码映射：DomainError → exit 1 / typer 用法错误 → exit 2 / 成功 → exit 0
- [ ] 异常路径 Gherkin 场景纳入验收（AC-1/AC-3/AC-7 场景）
- [ ] 既有异常测试零回归：`pytest tests/unit/domain/exceptions/ -v` 全绿

#### API 契约 (API Contract)
- [x] **openapi.yaml 零 diff**——本 Story CLI-only 入口（6.1-DF5 起十连 CLI-only 先例延续；REST 面归 Story 7-2），契约测试守护既有契约不被误改

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
- 进程入口位于 `src/entrypoints/main_cli.py`（组装层：load_dotenv → bootstrap → create_cli_app(resolve) → 派发）；entrypoints 不在 importlinter 三层 source 面
- `src/interfaces/cli/` 目录结构按 architecture.md:2073-2100 钦定：`main.py`（CLI 主入口工厂）+ `commands/`（6 模块命令定义）+ `controllers/`（6 控制器）+ `formatters/`（3 格式化器）
- typer 依赖仅入 interfaces/entrypoints 层，application/domain 零感知

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_unified_cli.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_unified_cli.py`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases，~23 场景：AC-1×4 / AC-2×5 / AC-3×4 / AC-4×2 / AC-5×1 / AC-6×1 / AC-7×2 / AC-8×2 / 收尾×2）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径** — 至少覆盖：非 UUID→242（plan-id 族）/201（agent-id 族）+exit 1、缺 cost-budget→201+exit 1、非法 format→exit 2、未知命令→exit 2
- **6-x 样板三件套**（test_acceptance_analyst_view.py:144-179 先例）：模块级 `event_loop` fixture + `_run_async` helper + 场景级 `context` dict
- **in-process 直调**：`main_cli.main([...])` 断言 exit_code（agent_cli.main 先例，checkpoint_recovery.py:1135）；直调前 `clear_singleton()`+`clear_scoped()` 双清、禁二次 bootstrap
- **延迟 import 纪律**：新交付模块一律步骤函数体内 import（收集期零 error，红形态=运行期 ImportError）
- **CLI 面 teardown**：「断言失败也执行」+ commit+定向 DELETE 先例（analyst_view PG 三分面 B 面）；document upload 场景创建的 PG 行/L0 文件定向清理
- `pytestmark` = markers + `xdist_group(...)` 串行组

#### 前置留项清单（Epic 6 回顾行动项 1 承载——七条逐条裁定落档）

> **来源：** epic-6-retro-2026-11-09.md 行动项 1（:124）+ §5.3（:102-104）+ §八（:140「agent_cli 19+ 子命令整合面是 7-1 的直接输入」）。
> **成功标准：** Epic 7 首两个 Story 立项文件含该清单且逐条落档（本表即 7-1 落档；6-1 单 Story 八条裁定为范本）。

| # | 留项（deferred-work.md 行号） | 裁定 | 处置与依据 |
|---|------------------------------|------|-----------|
| 1 | 6.1-DF5 BLM 状态查询生产入口零消费（:330） | **顺延 7-2** | 触发条件=REST 入口立项；7-1 CLI 同步阻塞语义不变，无中途查询场景，不新增 plan status 命令 |
| 2 | 6.1-DF6 REST 前置回头清单三项（:331） | **顺延 7-2** | 并发双跑/failsafe 缺口在 REST 并发入口激活；CLI 一次性进程不可达维持 |
| 3 | 6.4-DF2 fallback 分支覆盖缺口+组合根接线无守卫（:362） | **部分清偿** | 7-1 `sisys archive query` 验收经真实 bootstrap 的 CLI 面（无 session 上下文）天然覆盖 fallback **find 读路径**；新增契约测试落组合根接线守卫（resolve 可达断言）。残余（save 写路径 fallback 集成场景）顺延 7-2。触发条件「下一 CLI 归档消费 Story」经裁定命中读面不命中写面 |
| 4 | 6.5a-DF1 REST 导出面无契约（:369） | **顺延 7-2** | 7-1 零 REST 面，openapi.yaml 零 diff |
| 5 | 6.5a-DF2 L0 撕裂文件（:370） | **顺延 7-2** | 义务随 Epic 7 REST 面立项维持；7-1 CLI-only 并发纪律既有（同 plan_id 并发禁止 help 明示） |
| 6 | 6.8-R1-DF1 CLI 入口 .env 不加载（:402） | **触发，7-1 清偿（新入口面）** | 三选一定谳**方案一**：`main_cli.py` 入口显式 `load_dotenv`（显式路径，usecwd=False）先于 bootstrap。存量 `sisys-agent`/`sisys-ocr` 入口残余 → 新登记 deferred（归宿：命令族迁移专项） |
| 7 | 6.9-R1-DF1 `--plan-id` 宽松 UUID 守卫静默空态（:409） | **触发，7-1 部分清偿（新入口面）** | 新统一入口共享守卫 canonical 归一 `str(uuid.UUID(x))`（非 UUID→242 既有契约）；大写等非 canonical 形态归一命中。存量 agent_cli 命令族宽松守卫维持 → 新登记 deferred（归宿：命令族迁移专项） |

- [ ] 范围外注记：deferred-work.md:125/:129（StrategicAnalysisUseCase/orchestration_service/data_pipeline 三向定夺）锚定 **7-2 API 入口立项**，7-1 非触发面；:115（create_app 5 router 未挂载）归 7-2/7-3；:117（RabbitMQ 消费基建）归 7-x 首个消费 Story
- [ ] Task 0 将 #3/#6/#7 处置注记与 #1/#2/#4/#5 顺延注记逐条写入 `deferred-work.md` 对应条目（历史行不改写，追加处置注记——先例形态）
- [ ] 新登记 deferred：**7-1-DF1** 19 子命令迁移收敛专项（agent_cli → sisys 统一入口；sisys-agent 保留冻结直至迁移完成；含存量入口 .env 等价修复与宽松 UUID 守卫收敛——承接 #6/#7 残余）；**7-1-DF2** system/config 辅助模块命令组（归宿 7-4/后续）；**7-1-DF3** ndjson/csv 格式与 `--cost-budget` 三级熔断执行面（归宿后续扩展）；**7-1-DF4** plan generate `<type>` SP/BP 分叉参数（BLM 现形态无 type 分叉）——四条 gap 四要素齐备且 V1 归宿入 deferred-work

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕（命令矩阵冻结表 + 全局参数契约表 + 退出码契约表 + 异常消费表 + 端口消费表）
- [ ] Gherkin 验收测试已编写，运行确认失败（🔴 红阶段验证——延迟 import 纪律下红形态=运行期 ImportError/命令不存在）
- [ ] 规范文档通过人工评审或自动化校验
- [ ] **链路接线断言清单**已定义——本 Story 零新增端口/事件/中间件；消费面清单=AC-5 表 12 端口：契约测试逐一 resolve 可达断言（Task 0 编写，绿色门禁形态——防注册名漂移守卫，非红绿 TDD 面）

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

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | formatters | json/table/pretty 三态渲染（空/单条/多条/中文列宽/嵌套） | `tests/unit/interfaces/cli/test_cli_formatters.py` | Task 1 |
| **TDD 单元测试** | CLI 框架 | create_cli_app 工厂/全局参数/守卫（UUID 归一→242、缺 budget→201）/退出码矩阵/load_dotenv 先于 bootstrap 顺序 | `tests/unit/interfaces/cli/test_cli_framework.py` | Task 2 |
| **TDD 单元测试** | document 命令 | upload/parse 命令解析+controller+translator（stub resolve 直注） | `tests/unit/interfaces/cli/test_document_commands.py` | Task 3 |
| **TDD 单元测试** | tool 命令 | list/schema/run/chain run 四命令 + input_examples 字段校验 | `tests/unit/interfaces/cli/test_tool_commands.py` | Task 4 |
| **TDD 单元测试** | skill frontmatter | input_examples 字段解析与 1-5 条校验 | `tests/unit/application/skills/test_frontmatter_input_examples.py` | Task 4 |
| **TDD 单元测试** | agent/plan 命令 | agent run/plan generate + Agent 专用参数透传 | `tests/unit/interfaces/cli/test_agent_plan_commands.py` | Task 5 |
| **TDD 单元测试** | checkpoint/archive 命令 | list/show/recover/query 四命令 | `tests/unit/interfaces/cli/test_checkpoint_archive_commands.py` | Task 6 |
| **TDD 契约测试** | 端口消费接线 | 12 端口 bootstrap 后 resolve 可达 + isinstance 契约 | `tests/contracts/test_port_contract_unified_cli.py` | Task 0 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收（~23 场景） | `tests/acceptance/test_acceptance_unified_cli.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 三件套+in-process 直调+双清+延迟 import | `tests/acceptance/test_acceptance_unified_cli.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单最终确认 | 同上两文件追加场景 | Task 9 |
| **SDD 架构验证** | 六边形+七原则 | P4 MCP=0 断言/interfaces 零 composition_root 引用/typer 不入 application/domain/退出码契约矩阵/存量入口零回归 | `tests/unit/architecture/test_arch_unified_cli.py` | Task 8 |
| **集成测试** | CLI×真实服务 | document upload 真实 PG 链/archive query fallback 读链/checkpoint 族真实链 | `tests/integration/test_integration_unified_cli.py` | Task 7 |

> **注记（epics 名义文件 ↔ 实际落位映射）：** epics_v1.0.md 钦定 `tests/unit/interfaces/test_cli.py`/`tests/integration/test_cli_integration.py`/`tests/e2e/test_cli_e2e.py`——实际落位按仓内目录现实与功能性命名规范调整如上表；**E2E 语义由验收测试承载**（in-process 真实服务全链=端到端），`tests/e2e/`（现仅 `__init__.py` 空壳）维持空置（OD-5，与全仓四目录回归口径一致：`pytest tests/unit tests/integration tests/acceptance tests/contracts`）。

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（基线不破坏——当前全量基线 ~93% 实测口径）- **P0 阻断门禁**
- [ ] **接口层覆盖率 ≥85%**（epics 7.1 钦定）- **P1 阻断门禁**
- [ ] **新增文件行覆盖率 ≥95%**（6-9 先例口径）
- [ ] mypy 基线零新增错误

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|----------|
| **事务隔离** | 集成测试使用 transaction rollback | 数据泄漏导致随机失败 |
| **Schema 自创建** | fixture 内完成 Schema 初始化 | 依赖外部迁移，环境不一致 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符（TestTenant 租户隔离） | ID 冲突或状态污染 |
| **外部服务隔离** | 真实服务面验收 teardown 定向清理自建资源 | 真实数据被污染 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突导致并行失败 |
| **清理粒度** | 每个测试只清理自己创建的资源（CLI 面 commit+定向 DELETE 先例） | 误删其他测试资源 |
| **依赖声明** | Fixture 必须显式声明依赖 | 并行时清理顺序不确定 |
| **asyncio 上下文** | asyncio.Lock 类变量；BDD 步骤用 `event_loop.run_until_complete()` | 锁失效或 context 丢失 |
| **pytest-asyncio** | 删除 scope=module 的 event_loop fixture；BDD 步骤禁 `@pytest.mark.asyncio` | 与 auto mode 冲突 |
| **CLI 进程态** | in-process 直调前 `clear_singleton()`+`clear_scoped()` 双清；禁二次 bootstrap | ConflictError 假红 |
| **子进程形态** | 并发场景子进程缺 `sisys` script 时动态降级 `python -m src.entrypoints.main_cli` | 环境差异失败 |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback）
- ❌ autouse fixture 删除全局匹配资源（如 `test_*`）
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- ❌ 验收/集成测试 mock（真实服务强制；`pytest.skip()` 动态跳过）

**验证要求：**
- [ ] 并行测试 `pytest tests/unit tests/integration tests/acceptance tests/contracts -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 统一入口/三级结构/退出码契约/存量零回归 | Task 2 | 2.1-2.4 | `test_cli_framework.py` |
| AC-1 | 命令组骨架可见性 | Task 3-6 | 各组 1.1 | 各命令组测试 |
| AC-2 | document upload/parse 端到端 | Task 3 / Task 7 | 3.1-3.3 / 7.1 | `test_document_commands.py` + 验收 |
| AC-2 | agent run / plan generate（Mock 面） | Task 5 | 5.1-5.3 | `test_agent_plan_commands.py` + 验收 |
| AC-2 | checkpoint recover 端到端 | Task 6 / Task 7 | 6.1-6.3 / 7.3 | `test_checkpoint_archive_commands.py` + 验收 |
| AC-3 | 全局参数四件套契约 | Task 2 | 2.2-2.3 | `test_cli_framework.py` |
| AC-3 | Agent 专用参数透传 | Task 4-6 | 各组 2.x | 各命令组测试 |
| AC-4 | 三态格式化器 | Task 1 | 1.1-1.3 | `test_cli_formatters.py` |
| AC-5 | 12 命令全可用 + 契约接线断言 | Task 0 / Task 3-6 | 0.x 契约 / 各组 | `test_port_contract_unified_cli.py` |
| AC-6 | P4 MCP=0 架构断言 | Task 8 | 8.2 | `test_arch_unified_cli.py` |
| AC-6 | P7 input_examples 字段+暴露+补齐 | Task 4 | 4.1-4.4 | `test_frontmatter_input_examples.py` + `test_tool_commands.py` |
| AC-7 | UUID canonical 归一/242 | Task 2 | 2.3 | `test_cli_framework.py` |
| AC-7 | .env 入口加载 | Task 2 | 2.4 | `test_cli_framework.py`（顺序守卫）+ Task 7 集成 |
| AC-8 | 框架开销 P95/并发 10 | Task 9 | 9.x 验收性能场景 | 验收文件 |
| 全 AC | 收尾完成清单 | Task 9 | 9.1-9.4 | 验收文件收尾场景 |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部（规范源头）；AC-5（契约接线断言）；前置留项清单

> **目的：** 在进入代码实现前，明确命令矩阵、参数契约、退出码契约、异常消费契约、端口消费清单、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 冻结统一命令矩阵表（AC-5 表 12 命令 + 框架面 `--help/--version`）——实现禁增删命令名
- [ ] Subtask 0.2: 冻结全局参数契约表（`--yes/--dry-run/--mock/--format`）与 Agent 专用参数表（`--session/--cost-budget/--timeout`）及语义（AC-3 冻结语义为准）
- [ ] Subtask 0.3: 冻结退出码契约表（0/1/2）与 DomainError stderr 呈现格式（`[EXCEPTION_NNN] message`）
- [ ] Subtask 0.4: 编写端口消费契约测试 `tests/contracts/test_port_contract_unified_cli.py`（12 端口 resolve 可达+isinstance；绿色门禁守卫形态，跑通即过）
- [ ] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_unified_cli.feature`（~21 业务场景，按 AC 分节横幅注释组织）
- [ ] Subtask 0.6: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_unified_cli.py`（三件套+@scenario 逐场景绑定+延迟 import；本轮步骤实现可仅含 given 前置与调用骨架）
- [ ] Subtask 0.7: 运行验收测试，确认失败（🔴 红阶段验证——红形态=运行期 ImportError：`src.entrypoints.main_cli` 不存在）
- [ ] Subtask 0.8: 前置留项清单七条处置注记落档 `deferred-work.md`（#3 部分清偿/#6/#7 触发清偿注记+#1/#2/#4/#5 顺延注记——历史行不改写追加注记）+ 新登记 7-1-DF1~DF4（gap 四要素+V1 归宿）
- [ ] Subtask 0.9: 锚点行号复核（本 Story 引用的组合根行号/importlinter 行号/文档行号实测核对）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕（五张冻结表）
- [ ] 契约测试通过（既有端口注册态验证）
- [ ] 验收测试运行失败（预期行为，红阶段确认）
- [ ] deferred-work.md 处置注记与新登记落档

---

### Task 1: 输出格式化器（json/table/pretty）— 含完整 TDD 循环

**关联 AC:** AC-4

#### TDD 循环 A：三格式化器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_cli_formatters.py`（json 合法性/表格列宽中文对齐/pretty 分组缩进/空态/单条/多条/嵌套） |
| 🟢 绿 | 实现 `src/interfaces/cli/formatters/{__init__,json_formatter,table_formatter,pretty_formatter}.py` 最小代码 |
| 🟡 变异 | 改坏 JSON 序列化键→json 格式断言红；改坏列宽计算→table 断言红；还原绿 |
| 🔄 重构 | 统一渲染入口签名 `render(payload: Mapping) -> str`、类型注解、中文 docstring |

- [ ] Subtask 1.1: 🔴 红 — 编写三格式化器失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现三格式化器最小代码
- [ ] Subtask 1.3: 🟡 变异 — 断言突变注入-还原实证
- [ ] Subtask 1.4: 🔄 重构 — 统一签名与导出（formatters 按 format 值分发）

**完成标准/Definition of Done:**
- [ ] 三格式化器实现完成（纯函数，零外部服务依赖）
- [ ] TDD 循环全部通过
- [ ] 新增文件覆盖率 ≥95%

---

### Task 2: CLI 基础框架（typer 工厂+全局参数+守卫+进程入口）— 含完整 TDD 循环

**关联 AC:** AC-1 / AC-3 / AC-7

#### TDD 循环 A：create_cli_app 工厂与全局参数

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_cli_framework.py`（stub resolve 直注 create_cli_app：六模块子 app 挂载/--help 自描述/--format 值域 exit 2/--dry-run 输出端口名且 resolve 零调用/--mock 短路 JSON/--yes 缺 budget→201+exit 1） |
| 🟢 绿 | 实现 `src/interfaces/cli/main.py`（typer 工厂+全局参数回调+退出码处理）最小代码 |
| 🟡 变异 | 删六模块挂载→help 断言红；删 budget 守卫→拒绝断言红；还原绿 |
| 🔄 重构 | 类型注解/中文 docstring/参数 DRY |

#### TDD 循环 B：共享守卫与进程入口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 追加框架测试（UUID canonical 归一大写/URN/无连字符形态命中+非 UUID 双契约：plan-id 族→242/agent-id 族→201；`main_cli` load_dotenv 先于 bootstrap 顺序断言——monkeypatch 记录调用序） |
| 🟢 绿 | 实现 `src/interfaces/cli/_guards.py`（`canonical_uuid`/`require_agent_budget`）+ `src/entrypoints/main_cli.py`（load_dotenv→bootstrap→create_cli_app(resolve)→main）+ pyproject `[project.scripts]` 增 `sisys` 入口 |
| 🟡 变异 | 守卫去归一直传→大写形态断言红；load_dotenv 移 bootstrap 后→顺序断言红；还原绿 |
| 🔄 重构 | 守卫住位 _guards.py 单一职责、入口五步定式对齐 agent_cli 先例（幂等 bootstrap 守卫/finally 关闭连接池） |

- [ ] Subtask 2.1: 🔴 红 — 工厂/全局参数失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 main.py 工厂
- [ ] Subtask 2.3: 🔴 红 — 守卫/入口失败测试
- [ ] Subtask 2.4: 🟢 绿 — 实现 _guards.py + main_cli.py + pyproject scripts
- [ ] Subtask 2.5: 🟡 变异 + 🔄 重构 — 两循环收尾（ruff+mypy）

**完成标准/Definition of Done:**
- [ ] `sisys --help` 六模块可见、退出码契约矩阵测试全绿
- [ ] `poetry install` 后 `sisys` script 可执行
- [ ] 存量 agent_cli 测试零回归

---

### Task 3: document 命令组 — 含完整 TDD 循环

**关联 AC:** AC-2 / AC-5

> **存量处置：** `src/interfaces/cli/commands/document_commands.py` 为未接线存量（`__init__.py:5` 明示「勿仿」：裸 `except ValueError`+直接 `Resolver(_global_registry)` 违反现行规范）——本 Task **重写该文件**（architecture.md:2073-2100 钦定路径语义恢复），同步更新 `src/interfaces/cli/__init__.py` 勿仿告示。

#### TDD 循环 A：upload / parse

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_document_commands.py`（stub resolve：upload 参数解析→DocumentUploadCommand 冻结字段/文件不存在领域异常呈现/parse --id 守卫/mock 短路/dry-run 端口名） |
| 🟢 绿 | 实现 `commands/document_commands.py`（typer 定义）+ `controllers/document_controller.py`（命令对象+转换+调用 document_upload_service/document_parsing_service+格式化输出） |
| 🟡 变异 | controller 改直传未归一参数→命令对象断言红；还原绿 |
| 🔄 重构 | controller 与命令组职责分界（commands 只定义参数、controller 只编排） |

- [ ] Subtask 3.1: 🔴 红 — document 命令失败测试
- [ ] Subtask 3.2: 🟢 绿 — 重写 document_commands.py + 新建 document_controller.py
- [ ] Subtask 3.3: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:**
- [ ] `sisys document upload/parse --help` exit 0
- [ ] controller 单测全绿（stub resolve 直注，无 monkeypatch——DI 设计红利）
- [ ] 覆盖率 ≥95%（新增文件）

---

### Task 4: tool 命令组 + P7 input_examples — 含完整 TDD 循环

**关联 AC:** AC-5 / AC-6（P7）

#### TDD 循环 A：frontmatter input_examples 字段

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/skills/test_frontmatter_input_examples.py`（字段解析 list-of-str/1-5 条边界/零条与六条→校验异常/缺省缺字段容忍度——存量 SKILL.md 无该字段的兼容语义按「缺省=空元组不报错、tool schema 输出空」设计，批量补齐后收紧为全量断言） |
| 🟢 绿 | 修改 `src/application/skills/frontmatter.py`（input_examples 归一化+校验）+ `skill_manifest.py` 透传 |
| 🟡 变异 | 校验边界 5→6 放宽→六条断言红；还原绿 |
| 🔄 重构 | 校验逻辑与既有 LIST_FIELDS 归一风格对齐 |

#### TDD 循环 B：tool list / schema / run / chain run 四命令

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_tool_commands.py`（list 域过滤/schema 输出含 input_examples 字段/run 的 --input JSON 装载与 ToolCall 构造/chain run --config 装载/Agent 专用参数透传 context） |
| 🟢 绿 | 实现 `commands/tool_commands.py` + `controllers/tool_controller.py`（消费 tool_registry_service/tool_execution_service/run_tool_chain_use_case） |
| 🟡 变异 | schema 输出去 examples 键→断言红；run context 去 session→透传断言红；还原绿 |
| 🔄 重构 | 四命令共享 Agent 参数注解 DRY |

#### 批量补齐（非 TDD 面——内容资产）

- [ ] Subtask 4.4: 全量 active skills（TOOLS.md 视图 23 条口径）SKILL.md frontmatter 补 `input_examples`（每工具 1-5 条参数 JSON 示例）；跑批校验全量通过

- [ ] Subtask 4.1: 🔴 红 — frontmatter 字段失败测试
- [ ] Subtask 4.2: 🟢 绿 — frontmatter 扩展 + 四命令实现
- [ ] Subtask 4.3: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:**
- [ ] `sisys tool list/schema/run/chain run --help` exit 0
- [ ] tool schema JSON 输出含非空 input_examples
- [ ] 全量 SKILL.md 校验器跑批通过
- [ ] 覆盖率 ≥95%（新增文件）

---

### Task 5: agent 与 plan 命令组 — 含完整 TDD 循环

**关联 AC:** AC-2 / AC-5

#### TDD 循环 A：agent run / plan generate

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_agent_plan_commands.py`（agent run role/task 参数→命令对象/mock 短路形态冻结/plan generate --agent-id --task [--plan-id] 守卫/两命令 Agent 参数契约/真实面 stub resolve 调用形态） |
| 🟢 绿 | 实现 `commands/agent_commands.py`+`planning_commands.py`+`controllers/agent_controller.py`+`planning_controller.py`（消费 agent_workflow_use_case/blm_planning_use_case） |
| 🟡 变异 | mock 短路 payload 改键→冻结形态断言红；还原绿 |
| 🔄 重构 | 两 controller 共享 Mock DTO 构造 |

- [ ] Subtask 5.1: 🔴 红 — agent/plan 命令失败测试
- [ ] Subtask 5.2: 🟢 绿 — 实现两组命令+控制器
- [ ] Subtask 5.3: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:**
- [ ] `sisys agent run` / `sisys plan generate --help` exit 0
- [ ] Mock 面单测全绿；真实面单测 stub resolve 验证调用契约
- [ ] 覆盖率 ≥95%（新增文件）

---

### Task 6: checkpoint 与 archive 命令组 — 含完整 TDD 循环

**关联 AC:** AC-2 / AC-5

#### TDD 循环 A：checkpoint list/show/recover + archive query

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_checkpoint_archive_commands.py`（list --plan-id 归一守卫/show --id/recover --mode 值域/archive query --plan-id→blm_chain_trace_use_case 调用契约/空态 exit 0 输出） |
| 🟢 绿 | 实现 `commands/checkpoint_commands.py`+`archive_commands.py`+`controllers/checkpoint_controller.py`+`archive_controller.py`（消费 checkpoint 三用例+blm_chain_trace_use_case） |
| 🟡 变异 | recover mode 值域放宽→exit 2 断言红；还原绿 |
| 🔄 重构 | 四命令与既有命令组风格统一 |

- [ ] Subtask 6.1: 🔴 红 — checkpoint/archive 命令失败测试
- [ ] Subtask 6.2: 🟢 绿 — 实现两组命令+控制器
- [ ] Subtask 6.3: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:**
- [ ] 四命令 `--help` exit 0；12 命令矩阵全部就位（AC-5 审计断言绿）
- [ ] 覆盖率 ≥95%（新增文件）

---

### Task 7: 集成测试（真实服务面）

**关联 AC:** AC-2 / AC-7

> **性质说明：** 真实服务 Schema 隔离模式（独立 PG schema + savepoint rollback + 租户隔离）与 CLI 面形态（commit+定向 DELETE）按 integration_test_patterns 两种子模式择用。

- [ ] Subtask 7.1: document upload 真实 PG 链（真实临时文件→真实 upload_service→落库断言→定向清理）
- [ ] Subtask 7.2: archive query fallback 读链（真实 bootstrap 无 session 上下文→fallback find 路径往返——6.4-DF2 部分清偿载体）
- [ ] Subtask 7.3: checkpoint 族真实链（真实创建→list/show/recover 往返）
- [ ] Subtask 7.4: .env 入口加载集成验证（临时 .env 形态或既有 .env.test 口径——与单测顺序守卫互补）

**完成标准/Definition of Done:**
- [ ] 集成测试真实服务全绿（服务不可达动态 skip）
- [ ] 零手动 delete/truncate（rollback/定向清理）

---

### Task 8: SDD 架构约束验证测试

**关联 AC:** AC-1 / AC-6（P4）

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [ ] Subtask 8.1: 创建 `tests/unit/architecture/test_arch_unified_cli.py`
- [ ] Subtask 8.2: P4 MCP=0 断言（无 `src/infrastructure/mcp/` 目录、pyproject 无 mcp 依赖、src 全仓无 mcp import）
- [ ] Subtask 8.3: 分层断言（`src/interfaces/cli` 零 `composition_root`/`infrastructure` import；typer 零入 `src/domain`/`src/application`——domain 零依赖全仓断言既有测试自然覆盖，此处加 CLI 面专项）
- [ ] Subtask 8.4: 退出码契约矩阵与存量入口零回归（`sisys-agent`/`sisys-ocr` 入口 script 仍在+agent_cli 全量单测引用零改动）
- [ ] Subtask 8.5: 运行完整测试套件并生成报告（循环依赖检测沿用 ruff/isort 既有面，不引入新工具）

**完成标准/Definition of Done:**
- [ ] 所有架构/约束测试通过
- [ ] 任何违规都会导致测试失败
- [ ] 存量 CLI 测试全量零回归

---

### Task 9: 开发结束验收测试

**关联 AC:** 全部

> **性质说明：** 本 Task 对 Story 收尾阶段的交付物与完成清单进行最终验收，并补齐性能/并发验收场景。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_acceptance_unified_cli.feature` 收尾场景（src 完成清单/测试目录完成清单）+ AC-8 性能并发场景（20 轮 P95 采样/10 并发子进程） |
| 🟢 绿 | 编写/补齐对应 BDD 步骤实现，全场景转绿 |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [ ] Subtask 9.1: 性能场景 — 20 轮 `--dry-run` 采样 P95 < 500ms 断言
- [ ] Subtask 9.2: 并发场景 — 10 并发轻量子进程全部 exit 0
- [ ] Subtask 9.3: 收尾场景 1 — src 完成清单逐项确认；场景 2 — 四测试目录完成清单逐项确认
- [ ] Subtask 9.4: 运行 `pytest tests/unit tests/integration tests/acceptance tests/contracts`（四目录全量）+ `ruff check` + `mypy` 收尾校验；全量回归甄别失败项（DF 族/预存抖动形态对照 epic-6 先例归位）

**完成标准/Definition of Done:**
- [ ] 全部验收场景通过（含动态跳过项甄别）
- [ ] 四目录全量回归零未甄别失败
- [ ] Story 可进入 `review`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../planning-artifacts/architecture.md) + [`interface-design.md`](../../../docs/architecture/interface-design.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ D1 方案 A 组装层；CLI 属接口层适配器
- **设计约束:** 领域层零依赖；interfaces 禁 import composition_root/infrastructure（importlinter 传导禁令）；进程入口住 `src/entrypoints/`
- **接口治理:** 统一端口注册 PortSpec/组合根装配/契约优先；本 Story 零新增端口，消费 AC-5 表 12 端口
- **技术栈:** Python 3.11+ / typer ^0.24.0（pyproject.toml:21 已在依赖，此前零使用——本 Story 首次启用）；table 渲染沿用 agent_cli 纯标准库两遍法先例（`_print_checkpoint_summary_table` :1495-1518）——**不引入 rich**（零新增依赖，typer 本身不强制 rich）

### 关键架构决策

| # | 方案 | 优点 | 缺点 | 评分 |
|---|------|------|------|------|
| **DC-1（选中）** | 新统一入口用 typer（架构文档钦定），存量 `sisys-agent` argparse 冻结不迁移 | 遵守 architecture.md:2073-2100 与路线图（:2071-2080「typer 基础框架=Story 7.1」）；typer 已在依赖；新面零回归风险 | 双栈并存期（迁移专项收敛，7-1-DF1 登记） | ✅ 9/10 |
| 备选：延续 argparse 统一 | 与存量一致 | 违反架构钦定需 OD；类型注解驱动优势弃用；argparse 手写量大 | 5/10 |
| **DC-2（选中）** | `create_cli_app(resolve)` 工厂注入解析器函数 | interfaces 零组合根知识（importlinter 合规）；单测 stub 直注免 monkeypatch（优于 agent_cli 模式） | 入口层多一层装配 | ✅ 9/10 |
| 备选：模块级 resolve 调用（agent_cli 式） | 简单 | interfaces 引 composition_root 违约；测试须 monkeypatch | 4/10 |
| **DC-3（选中）** | 存量 19 子命令保留冻结，迁移收敛入 deferred | 零回归（4294 行单测+14 验收文件不动）；surgical | 双入口并存期 | ✅ 8/10 |
| 备选：本 Story 全量迁移 | 单入口一步到位 | 2720 行重构+14 验收文件波及，超出单 Story 可交付面；回归风险不可控 | 3/10 |
| **DC-4（选中）** | Command Translator 以接口层 frozen dataclass 命令对象承载 | 路线图交付物兑现；不新建 application/commands 包（YAGNI——全仓用例为直接方法签名） | 命令对象与用例签名双轨维护 | ✅ 8/10 |
| **DC-5（选中）** | `--mock`=命令级 Mock 响应（不 bootstrap）；`--dry-run`=接口层预览（不 bootstrap） | 语义确定可测；验收确定性；零基础设施耦合 | 深度 mock（真实服务+mock LLM）不在 7-1（7-1-DF3 关联） | ✅ 8/10 |
| **DC-6（选中）** | .env 清偿采方案一（入口显式 load_dotenv） | 一行修复根因；6.8-R1-DF1 三选一中最小面 | 存量入口残余待迁移专项 | ✅ 9/10 |

### 偏离声明预告（Task 0 落档确认，OD-n 前缀）

| OD | Gap（四要素） | V1 归宿 |
|----|--------------|--------|
| OD-1 | P5 工具选择准确率≥85%/P6 误触发率<5% 指标不在 7-1 验收——SkillSelector 机制已交付（5-2），指标属评估面 | evaluation 专项 |
| OD-2 | ndjson/csv 输出格式 defer——epics 7.1 AC 仅列 json/table/pretty | 后续格式扩展 |
| OD-3 | `--cost-budget` 三级熔断（Level 1/2/3）执行面 defer——7-1 仅参数契约+Agent 模式缺省拒绝 | 成本熔断专项 |
| OD-4 | plan generate `<type>` SP/BP 分叉参数 defer——BLM 现形态无 type 分叉 | BLM 类型分叉 Story |
| OD-5 | tests/e2e 空置——E2E 语义由验收（in-process 真实服务全链）承载 | 维持四目录口径 |
| OD-6 | system/config 辅助模块命令组 defer（sisys system auth/monitor/route/health、sisys config 族） | 7-4/后续 |

### 项目结构说明 Project Structure（本 Story 相关面）

```
src/
├── entrypoints/
│   ├── agent_cli.py                  # 存量冻结（零改动）
│   ├── ocr_cli.py                    # 存量冻结（零改动）
│   └── main_cli.py                   # ★新建：sisys 进程入口（load_dotenv→bootstrap→create_cli_app→派发）
├── interfaces/cli/
│   ├── __init__.py                   # 更新：移除 document_commands「勿仿」告示
│   ├── _guards.py                    # ★新建：共享守卫（canonical_uuid/require_agent_budget）
│   ├── main.py                       # ★新建：create_cli_app 工厂+全局参数+退出码处理
│   ├── commands/
│   │   ├── document_commands.py      # ★重写存量（upload/parse）
│   │   ├── tool_commands.py          # ★新建（list/schema/run/chain run）
│   │   ├── agent_commands.py         # ★新建（run）
│   │   ├── planning_commands.py      # ★新建（generate）
│   │   ├── checkpoint_commands.py    # ★新建（list/show/recover）
│   │   └── archive_commands.py       # ★新建（query）
│   ├── controllers/                  # ★新建包：6 控制器（命令对象+translator+编排+DomainError 呈现）
│   └── formatters/                   # ★新建：json/table/pretty 三格式化器
└── application/skills/
    ├── frontmatter.py                # 修改：input_examples 字段
    └── */SKILL.md                    # 修改：全量补 input_examples（23 条口径）

tests/
├── unit/interfaces/cli/              # test_cli_formatters/test_cli_framework/test_*_commands.py（6 文件）
├── unit/application/skills/          # test_frontmatter_input_examples.py
├── unit/architecture/                # test_arch_unified_cli.py
├── contracts/                        # test_port_contract_unified_cli.py
├── integration/                      # test_integration_unified_cli.py
└── acceptance/                       # test_acceptance_unified_cli.feature/.py

pyproject.toml                        # [project.scripts] 增 sisys 入口
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 6-11 白标报告基础](./6-11-white-label-report-basic.md)（Epic 6 收官故事）+ [epic-6-retro-2026-11-09.md](../epic-6-retro-2026-11-09.md)

**关键学习/Key Learnings:**
- CLI 层异常契约先例：`[EXCEPTION_NNN] message` stderr + exit 1；argparse `type=` 禁 `uuid.UUID`（agent_cli.py:15-24）；brand-template-save 242 stub 格先例（c427a14a）
- 单测注入模式：agent_cli 用 monkeypatch 模块级 bootstrap/resolve（无 Resolver override 公开 API）——本 Story DI 工厂设计后 **stub resolve 直注即可，禁再走 monkeypatch**
- 验收三件套+双清+延迟 import+CLI 面 commit+定向 DELETE 三分面（analyst_view :144-179 / checkpoint_recovery :76-80 先例）
- CI root 容器教训（efd0f11d/bf24d1f5）：条件 skip 恒 skip 假绿——环境门控用 `_require_services` 形态，禁 `geteuid()==0` 类恒 skip
- 变异实证强制（Epic 4 行动项 7.1-2）：每 Task 断言突变注入-还原，恒真断言零容忍
- 共享 collection 读回断言一律定向过滤（retro 行动项 4——checkpoint scroll limit 残留假红教训）
- 长链注记三轮即压缩（retro 行动项 2）——deferred-work 处置注记精炼
- 时钟回拨（2745f74a）：跨 await 墙钟二次采样用 `utc_now_after` 钳制——CLI 性能采样场景的时间测量注意
- 「CLI-only 第 N 连」计数语义在 7-1 转换：7-1 是 CLI 本体故事（统一入口），该计数随 Epic 6 收官终结

**应用到本故事/Applied to This Story:**
- [ ] 退出码/异常呈现契约逐字对齐 agent_cli 既有形态（AC-1 冻结）
- [ ] 单测 stub resolve 直注（DC-2 红利），验收真实服务+双清
- [ ] 性能采样时间测量规避墙钟回拨（ monotonic clock 口径）
- [ ] 前置留项清单七条裁定（SDD 节落档表）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.3（Claude Code 会话） |
| **Version** | create-story workflow v6.3.0（bmad-create-story skill） |
| **Execution Date** | 2026-11-20 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md`（v2.9.0） |
| **Checklist** | `.claude/skills/bmad-create-story/checklist.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Epic 7 :2565-2645） |
| **架构文档** | `docs/architecture/architecture.md`（:2073-2100 CLI 目录）+ `docs/architecture/interface-design.md`（§3.3/:428-615 命令矩阵/:2071-2080 路线图） |
| **前置留项源** | `_bmad-output/implementation-artifacts/epic-6-retro-2026-11-09.md`（行动项 1 :124）+ `deferred-work.md`（七条 :330-:409） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/6-11-white-label-report-basic.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取（Story 7.1 :2597-2645）
- [x] 架构约束从 architecture.md/interface-design.md 提取（三调研 Agent 并行：架构文档/现有代码/测试与故事风格）
- [x] 前置留项清单七条逐条裁定落档（epic-6-retro 行动项 1 承载）
- [x] 前一个故事学习经验整合（6-11 + epic-6 回顾）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范（architecture.md:2073-2100 钦定目录）
- [x] 现有代码资产盘点完成（agent_cli 19 子命令/formatters 空目录/document_commands 未接线存量/六模块端口行号核验）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/7-1-cli-command-interface.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/entrypoints/main_cli.py` - sisys 进程入口
- `src/interfaces/cli/main.py` - CLI 工厂
- `src/interfaces/cli/_guards.py` - 共享守卫
- `src/interfaces/cli/commands/{tool,agent,planning,checkpoint,archive}_commands.py` - 5 命令组（document_commands.py 重写）
- `src/interfaces/cli/controllers/` - 6 控制器
- `src/interfaces/cli/formatters/{json,table,pretty}_formatter.py` - 3 格式化器
- `tests/unit/interfaces/cli/test_cli_formatters.py` 等 7 个测试文件
- `tests/unit/architecture/test_arch_unified_cli.py`
- `tests/contracts/test_port_contract_unified_cli.py`
- `tests/integration/test_integration_unified_cli.py`
- `tests/acceptance/test_acceptance_unified_cli.feature` + `.py`

**待修改的文件/To Be Modified:**
- `pyproject.toml`（[project.scripts] 增 sisys）
- `src/application/skills/frontmatter.py` + `skill_manifest.py`（input_examples）
- `src/application/skills/*/SKILL.md`（全量补示例，23 条口径）
- `src/interfaces/cli/__init__.py`（移除勿仿告示）
- `_bmad-output/implementation-artifacts/deferred-work.md`（处置注记+新登记 7-1-DF1~DF4）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 7.1 |
| **Story Key** | 7-1-cli-command-interface |
| **File** | `_bmad-output/implementation-artifacts/stories/7-1-cli-command-interface.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `review` → `done` |
| **Epic** | Epic 7: 多触点用户界面与 API 集成 |
| **价值组** | 多触点操作与监控能力 |
| **优先级** | P0-1（Epic 7 入口故事） |
| **覆盖 FR** | FR-UI-01、FR-IF-01（P1/P4/P7 承载面）；NFR-IF-01 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-9）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-8）
3. [x] Architecture constraints extracted 架构约束已提取（六边形+D1 方案 A+importlinter 传导禁令）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（6-11+epic-6 回顾）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | （待审查） | - | - |

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 待定
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor）

#### 需决策 Decision Needed

- [ ] （待审查）

#### 已修复 Patch

- [ ] （待审查）

#### 已推迟 Defer

- [ ] （待审查）

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-11-20
**最后更新/Last Updated:** 2026-11-20
**更新说明/Description:**
- v1.0.0: 创建故事文件（三 Agent 并行调研：架构文档/现有代码/测试与故事风格；前置留项清单七条裁定落档；DC-1~DC-6 架构决策+OD-1~OD-6 偏离预告；12 命令冻结矩阵+全局参数契约+退出码契约）
