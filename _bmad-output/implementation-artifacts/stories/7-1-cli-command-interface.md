# Story 7.1: CLI 命令行接口（统一 sisys 入口）

**Status:** `done`

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
- [ ] 既有 `tests/unit/interfaces/cli/test_agent_cli.py`（4294 行，基线 6047e4d4 时点——R1-F29 易腐锚点注记）与 14 个 CLI 形态验收文件（口径=以 agent_cli 为骨架的验收 .py：`grep -l agent_cli tests/acceptance/*.py` 实测 14 件——R1-F22 锚定）零改动零失败；**例外**：`tests/unit/interfaces/cli/test_document_commands.py`（197 行存量，argparse version 命令族）为 Task 3 重写覆盖项，不在零回归面（见 Task 3 存量处置）

### AC-2: 四大核心工作流端到端

**Given** 系统真实服务（PG/Redis 等）可用且组合根可 bootstrap
**When** 依次执行四大核心工作流（document/agent/plan/checkpoint，共五条命令）
**Then** 命令正确解析并真实执行，输出执行结果与进度反馈
- `sisys document upload --file <path> [--business-domain <name>]` → 真实服务上传，输出 document_id
- `sisys document parse --id <doc-id>` → 真实解析链
- `sisys agent run <role> --task <text> --mock --yes --cost-budget <amount>` → Mock 响应模式返回结构化结果
- `sisys plan generate --agent-id <id> --task <text> --mock --yes --cost-budget <amount>` → Mock 响应模式
- `sisys checkpoint recover --plan-id <uuid> --checkpoint-no <CP-N> --yes --cost-budget <amount>` → 真实恢复链（R3-3 参数形态勘正：`--id <cp-id>` 单参数形态与端口签名不匹配——checkpoint 域无 UUID 查询 API，落地为 `--plan-id`+`--checkpoint-no` 复合定位；验收 given 前置经 `checkpoint_use_case`（CreateCheckpointUseCase，:2496）直创 checkpoint（`retrieved_docs` 空列表 CLI 路径构造先例，docstring 明示））

**验证标准/Validation Criteria:**
- [ ] document upload/parse 验收场景走真实服务（真实临时文件 → 真实落库 → teardown 定向清理）
- [ ] agent run / plan generate 真实 LLM 面动态跳过（无 Key 环境 `pytest.skip()`），Mock 面（`--mock`）确定性全绿
- [ ] checkpoint recover 验收场景真实链（given 前置真实创建 checkpoint → recover → 断言恢复结果）

> **Skip 口径归类注记（CR6）：** 验收「Checkpoint 恢复真实链」与集成「checkpoint 族往返」两场景的无 Key 环境 skip，归类为 **checkpoint 创建链 OD-12 五步编排的压缩强制环节依赖连带**（非 AC-2 钦定的「agent run/plan generate 真实 LLM 面」skip——钦定面是被测面即 LLM，此两场景是被测面零 LLM 的前置依赖拖累）；解耦归宿（创建链空 docs 压缩短路）动摇快照完整性语义，deferred 登记 checkpoint 域专项复核。AC-7 大写归一场景已换 document 域前置（CR6，无 Key 环境可跑）。

### AC-3: 全局参数与 Agent 模式参数契约

**Given** sisys CLI 任一命令
**When** 附加全局参数
**Then** 以下契约生效（interface-design.md §4.4 参数规范冻结）：
- `--yes`：Agent 模式开关。**设置 `--yes` 时必须显式提供 `--cost-budget`，缺失 → 拒绝执行**（ValidationError EXCEPTION_201，stderr 呈现，exit 1）
- `--dry-run`：接口层预览——打印命令解析结果与将调用的用例端口名，**不 bootstrap、不执行**
- `--mock`：Mock 响应模式——controller 短路返回结构化 mock DTO，**不 bootstrap**（面向 LLM 自测与验收确定性；守卫校验仍先于短路执行）
- `--format json|table|pretty`：全命令支持，默认 `table`
- Agent 专用参数（`--session <id>` 缺省自动生成 UUID、`--timeout <seconds>` 缺省 300、`--cost-budget <amount>`）——**参数面口径（CR1-F6 勘正）：全部命令支持**（对齐 interface-design §4.4「所有命令必须支持」原文；dev 实现即 §4.4 形态，原「限五命令」系本 Story 文档期收窄偏差）；`--yes` 缺 `--cost-budget` 拒绝守卫经 base 管线（controllers/base.execute_command 入口）**全命令统一**生效（含 list/show 等查询命令——单一可教不变量，实测 checkpoint list --yes 无 budget → 201 exit 1）

**守卫层定义冻结（CR1-F5，dry-run 语义自洽性）：** 先于 `--dry-run`/`--mock` 短路执行的守卫分两类：①**参数归一守卫**（canonical_uuid 实体族/agent 族/budget/format 枚举——_guards.py 统一）；②**命令级输入守卫**（业务输入的 fail-fast 校验，如 document upload 的文件存在性 202——各 controller 自持）。「dry-run = 守卫通过后的执行预览」是单一不变量（预览不跳过输入校验，更安全）；各命令守卫面差异（upload 有文件守卫、list 无输入守卫）是命令语义的自然结果。**recover 特例**：`checkpoint recover --dry-run` 消费 :2508 真实预览视图（需 bootstrap——预览语义需要真实恢复目标状态，:2508 预览面即 dry-run 的领域等价物，AC-5 行注记钦定）。

**全局参数实现机制冻结（R1-F1，P0 修复）：** 全局参数与 Agent 专用参数经**共享 Annotated 类型在各命令签名逐一声明**（typer 标准形态，前置/尾置形态均可解析）；**禁止 `@app.callback()` 承载全局参数**——click group callback 参数在子命令之后的尾置形态（如 `sisys document upload --file x --yes`）实测 exit 2（typer 0.24.2/click 8.4.2 验证），而本 Story 全部用法示例均为尾置形态。共享注解定义于 `src/interfaces/cli/_params.py`（Annotated 类型单一来源，Task 4「四命令共享 Agent 参数注解 DRY」推广至全部全局参数）。**豁免边界（R3-6）：** `--version` 顶层选项经 `app.callback(invoke_without_command=True)` 承载（实测顶层 exit 0）——豁免于上述禁令：version 是顶层前置形态选项（`sisys --version` 无子命令上下文，无尾置可达性问题），与跨子命令全局参数不同类。

**参数互斥/优先级契约（R1-F24）：** `--dry-run` 与 `--mock` 同给时 **`--dry-run` 优先**（最外层短路：打印解析结果与端口名后即返回，不进入 mock 短路），不报互斥错误。

**`--dry-run` 端口名来源机制（R1-F5）：** 端口名唯一来源 = **controller 静态 `PORT_NAME` 类常量**（如 `DocumentUploadController.PORT_NAME = "document_upload_service"`），dry-run 渲染命令对象 + 静态端口名后即返回——**禁止调用 `resolve()`**（resolve 依赖 bootstrap，与「不 bootstrap」契约自洽性硬约束）。

**验证标准/Validation Criteria:**
- [ ] `--yes` 无 `--cost-budget` → EXCEPTION_201 + exit 1（**全部命令一致**——CR2 勘正：base 管线统一守卫，原「全 Agent 专用命令」旧口径随 CR1-F6 参数面放宽同步）
- [ ] `--dry-run` 输出含端口名与归一后参数，且无 bootstrap 副作用（可用 stub resolve 断言零调用）
- [ ] `--mock` 输出为合法 JSON（`--format json` 组合）且零外部服务依赖；`--dry-run`×`--mock` 同给 → `--dry-run` 优先（输出端口名预览非 mock DTO——R2-8 优先级断言）
- [ ] `--session`/`--timeout` 透传至用例执行上下文（真实面断言；`--mock` 面 `--session` 缺省自动生成仍入 Mock DTO 的 `session` 字段——透传语义两态都可达，R2-4）

### AC-4: 三态输出格式化器

**Given** 任一命令产生结果 DTO
**When** 指定 `--format json|table|pretty`
**Then** `src/interfaces/cli/formatters/` 三格式化器正确渲染：
- `json`：合法 JSON 单文档输出（可 pipe 给 jq / LLM 直接消费）
- `table`：人类可读表格（列宽自适应，参照 agent_cli `_print_*` 两遍法先例）
- `pretty`：终端美化输出（分组+缩进）

**序列化契约（R2-1）：** `json_formatter` 序列化策略冻结为 `json.dumps(payload, default=str, ensure_ascii=False)`——命令对象/结果 DTO 含 `uuid.UUID`/`Decimal`/`datetime` 字段（R1 机制面新增 `_params.py`/`PORT_NAME` 契约的同族联动），`default=str` 统一降维（UUID→hex 串、Decimal→十进制串）；`--mock` 短路 DTO 的 `parameters` 同走此策略（R2-2）；全仓无既有 `json.dumps` CLI 先例（agent_cli 纯 print 面零 json.dumps），本 Story 为首个 JSON 输出面——策略在 Task 1 红阶段以「payload 含 UUID/Decimal 字段 → `json.loads` 可解析且值形态正确」断言锚定。

**验证标准/Validation Criteria:**
- [ ] 三格式化器单元测试覆盖：空列表、单条、多条、中文列宽、嵌套字段
- [ ] `json` 输出经 `json.loads` 可解析（验收场景断言）
- [ ] 非法 format 值 → exit 2（typer Enum choice 守卫）

### AC-5: 六模块 100% CLI 入口覆盖（P1 原则）

**Given** sisys 统一入口
**When** 审计六大服务模块命令入口
**Then** 冻结命令矩阵（12 命令，Task 0 冻结表）全部可用，document/tool 两模块 CLI 面从零到一。
**参数语义注记（R1-F4，CR1-F7b 勘正）：** `<tool-id>` 一律为 **TOOLS.md slug**（如 `pestel-analysis`，人类/LLM 可读形态），非 UUID——tool run/schema 内部解析链 = `skill_manifest.SLUG_TO_TOOL_ID`（**仓内钦定生产 SSOT**，4-x 周期先例）→ `tool_registry_service.get_tool(tool_id=<UUID>)`（**禁 `get_tool(tool_name=slug)` 直查——TOOLS.md 的 slug 与 tool_name 是两个不同列，slug≠tool_name 的工具直查必 miss**；registry.get_tool(tool_name=) 能力存在但 CLI 面统一走 SSOT 映射防两源分叉使用）；**禁止对 tool-id 参数套用 canonical_uuid 守卫**（slug 非 UUID 形态）。

| 模块 | 命令 | 消费端口（组合根注册名，已核验行号） |
|------|------|------|
| document | `upload` | `document_upload_service`（composition_root.py:1189） |
| document | `parse` | `document_parsing_service`（:1371） |
| tool | `list` | `tool_registry_service`（:2598） |
| tool | `schema <tool-id>` | `tool_registry_service.get_tool` + `skill_loader`（:2875，`load_sop`→`SkillDocument.input_examples`——R1-F3 补登记，input_examples 运行时数据通路唯一载体） |
| tool | `run <tool-id>` | `tool_execution_service`（:2741，`execute(tool_id, tool_call, context)`） |
| tool | `chain run <chain-id>` | `run_tool_chain_use_case`（:2945，`execute(chain_name, parameters, context)`） |
| agent | `run <role>` | `agent_workflow_use_case`（:3178） |
| plan | `generate` | `blm_planning_use_case`（:3518，`execute(agent_id, task, plan_id)`） |
| checkpoint | `list --plan-id` | `checkpoint_list_use_case`（:2524） |
| checkpoint | `show --plan-id --checkpoint-no <CP-N>` | `checkpoint_recovery_use_case`（:2508——RecoverCheckpointUseCase 预览面，`execute(*, plan_id, checkpoint_no)` 两参 keyword-only 必填→`CheckpointRecoveryView` 详情视图；**两参均必填**——R5 改判方案 a：不设「缺省取最新」合成层（两步合成有 list↔:2508 间 TOCTOU 语义模糊+无钦定依据+无验收牵引）。R3-1 勘正：原写 `show --id`→`checkpoint_use_case`(:2496) 系端口错位——该端口实为 CreateCheckpointUseCase 纯创建零查询，无 `--id` 查询可达面） |
| checkpoint | `recover --plan-id --checkpoint-no [--mode replay\|override] [--confirmed-by <id>]` | `checkpoint_recovery_execute_use_case`（:2536——ExecuteCheckpointRecoveryUseCase 执行面，`execute(plan_id, checkpoint_no, correction, mode, confirmed_by, created_via)`；`confirmed_by` 非空强制——空串→242 用例守卫。R3-2 勘正：原写 `recover --id [--mode]`→checkpoint_recovery_use_case(:2508) 系预览/执行面错位——:2508 无 mode 无恢复副作用。`--confirmed-by` 缺省取 `--session` 标识（**解析时点**：守卫层随参数归一完成，`--mock` 面 parameters 含解析后值——R4-3）；controller 固定传 `created_via="cli"`（缺省 "use_case" 会落错触发源审计标识——R4-2）；`--dry-run` 面消费 :2508 预览视图天然对齐） |
| archive | `query --plan-id` | `blm_chain_trace_use_case`（:2567） |

**验证标准/Validation Criteria:**
- [ ] 12 命令 `--help` 全部 exit 0
- [ ] 轻量真实链验收：`tool list` / `tool schema` / `checkpoint list` / `archive query` 真实服务执行——**承载位注记（CR2）：** AC-5 场景为三命令（tool list/checkpoint list/archive query——feature 场景名已勘正），`tool schema` 的验收承载位由 AC-6×1 场景承载（input_examples 非空断言内含真实执行）；**名实注记（R3-9）：**「轻量」指命令逻辑轻（查询/展示类），bootstrap 仍装配全组合根（五存储可达性），动态 skip 机制照常生效，不可绕 bootstrap
- [ ] P1 审计断言：契约测试逐一断言 **12 唯一端口**注册面可达（接线断言清单；R5-1 口径勘正：12 命令构成 13 个命令-端口消费对——`tool_registry_service` 被 tool list/schema 双命令消费，唯一注册名 12 个，契约测试按 12 唯一名断言）

### AC-6: CLI 七原则合规承载（FR-IF-01）

**Given** sisys CLI 已安装并配置完成
**When** 验证 CLI 接口合规性
**Then** 满足以下验收标准（epics_v1.0.md:2610-2622 冻结）：
- **P1**（本 Story 核心）：内部工具 100% 有 CLI 入口，覆盖 document/tool/agent/plan/checkpoint/archive 6 个服务模块（AC-5 承载）
- **P4**：MCP 退居生态层——MVP 阶段 MCP 相关代码量 = 0（架构测试断言：无 `src/infrastructure/mcp/` 目录、pyproject 无 mcp 依赖、全仓无 mcp import）
- **P7**：input_examples 驱动——skill frontmatter 新增 `input_examples` 字段（1-5 条约束校验），`sisys tool schema` 输出该字段，全量 active skills（TOOLS.md 视图 23 条口径）每工具补齐 ≥1 条示例；P7 量化指标「工具调用准确率≥90%」（epics:2618/interface-design:57）属评估指标面，7-1 仅承载机制面（R1-F12）
- **P5/P6/P7 量化指标**（注记锚，OD-1）：SkillSelector 已于 Story 5-2 交付（`skill_selector` 端口）；「工具选择准确率≥85% / 误触发率<5% / 工具调用准确率≥90%」三指标同属评估指标面，7-1 不重复建设，统一锚定 evaluation 专项（`evaluation_harness` 已有基建）

**验证标准/Validation Criteria:**
- [ ] P4 架构断言测试通过（`test_arch_unified_cli.py`）——架构测试承载（非验收场景）
- [ ] frontmatter `input_examples` 字段校验单测（非 list/超 1-5 条 → EXCEPTION_201 族校验异常）——unit 承载（非验收场景）
- [ ] `sisys tool schema <tool-id> --format json` 输出含非空 `input_examples`——验收场景×1 承载（AC-6×1）
- [ ] 全量 active skills 的 SKILL.md frontmatter 含 1-5 条 input_examples（校验器全量跑批断言）——跑批断言承载（Task 4.4 收尾，非验收场景）；**承载面注记（R2-9）：四验证项分属架构测试/unit/验收场景/跑批四承载面，仅第三项入 23 场景计数**

### AC-7: 输入守卫与入口环境装配

**Given** sisys CLI 接收用户/Agent 输入
**When** 输入非规范形态
**Then** 守卫契约生效：
- **UUID canonical 归一**（6.9-R1-DF1 新面清偿）：`--plan-id` 等 UUID 参数经共享守卫 `str(uuid.UUID(value))` 归一——大写/URN/无连字符等非 canonical 形态归一后正确命中（与存量 agent_cli 宽松守卫静默空态形成对照）；非 UUID 守卫按参数族分契约：**实体 ID 族（`--plan-id`）→ EntityValidationError 242、agent-id 族（`--agent-id`）→ ValidationError 201**（agent_cli 既有分工，R1-F18/_parse_agent_uuid 先例），均 exit 1；`--checkpoint-no` 为 "CP-N" 编号非 UUID（不套 UUID 守卫，格式校验仅前缀锚定）；**UUID 守卫仅适用 UUID 族参数——`<tool-id>` 为 slug 禁套守卫（见 AC-5 注记）**
- **.env 入口加载**（6.8-R1-DF1 新面清偿，方案一定谳）：`src/entrypoints/main_cli.py` 在 bootstrap 前显式 `load_dotenv`（显式路径，`usecwd=False`）——`python -m src.entrypoints.main_cli` 形态下 .env 注入不再依赖 litellm import 副作用。**路径推导与可测注入（R2-11）：** 显式路径 = 模块级常量 `ENV_FILE = Path(__file__).resolve().parents[2] / ".env"`（仓库根推导，main_cli.py 位于 src/entrypoints/ 下两层）；集成测试 Task 7.4 经 monkeypatch 该常量指向临时 .env 文件注入（不改仓库根 .env，零污染），单测顺序守卫同锚该常量。**调用位置钉死（R3-5）：** `load_dotenv(ENV_FILE)` 必须在 `main()` 函数体内、bootstrap 之前调用——**禁止模块级 import 副作用形态**（模块级执行会使 pytest 收集期即加载、monkeypatch 不可达、in-process 二次直调不再执行，顺序守卫断言形态崩坏）
- 枚举值（--format/--mode 等）由 typer choice 守卫 → exit 2

**验证标准/Validation Criteria:**
- [x] 大写 UUID 输入 → 归一后真实查询命中（非静默空态）验收场景——**前置数据链（CR6 换域改造）：** 经 document 域真实 upload（零 LLM 依赖）产出 document_id 后，以大写 `--id` 形态执行 `document parse --format json` 断言 `parse_status=completed`+`document_id` 归一小写形态（锚同一 canonical_uuid 实体族守卫——R5-3 点名 document parse --id 属实体族；原 R3-7 的 checkpoint 前置因创建链 OD-12 压缩强制环节依赖 LLM 而在无 Key 环境连带 skip，本清偿面曾零验收覆盖——换域后无 Key 环境可跑，miss 形态合成 FAILED 文档的 parse_status 即判别锚）
- [ ] 非 UUID → plan-id 族 EXCEPTION_242 / agent-id 族 EXCEPTION_201，均 exit 1
- [ ] 单测断言 main_cli 中 load_dotenv 先于 bootstrap 调用（顺序守卫）
- [ ] 非法 `--format`/`--mode` 值 → exit 2

### AC-8: 性能与并发口径

**Given** sisys CLI 框架
**When** 性能采样与并发测试
**Then** NFR-IF-01 V1 口径满足：
- **框架开销 P95 < 500ms**——P95 值为 epics/prd.md:2553（NFR-IF-01「<500ms（V1）」）钦定；**20 轮采样为 Story 验收自定口径**（R1-F9 勘正：epics 无「20 轮」钦定）。口径锚定**命令解析+CLI 工厂装配（create_cli_app+子命令挂载）+格式化路径**（`--help`/`--dry-run`），**不含组合根 bootstrap**（R1-F17 勘正「装配」语义）；重 LLM 命令（agent run/plan generate 真实面）响应时长由各自用例性能窗承载（BLM 60s 窗先例），不在此口径（OD 注记）
- **采样调用形态冻结（R1-F6）：** 子进程直调 `.venv/bin/sisys --dry-run`（或 `python -m src.entrypoints.main_cli --dry-run`）——**禁 `poetry run` 包装**（包装自身开销实测 ~300ms，10 轮实测 P95≈422ms 逼近红线，污染采样；裸 `python -m` 实测 38-43ms 余量充足）
- **并发执行 10 个 CLI 命令**：10 个轻量子进程并发全部成功（exit 0）——**并发命令面冻结 = `--help` 与 `--dry-run` 组合**（零 bootstrap 零服务依赖，R1-F25）
- **编号消歧注记（R1-F10）：** NFR-IF-01 在 prd.md:2553（CLI 延迟）与 epics_v1.0.md:336/:669/:3466（仪表盘加载 <2s，语义实为 NFR-IF-06）双源冲突，本 Story 以 **prd 口径**为准

**验证标准/Validation Criteria:**
- [ ] 验收性能场景：20 轮 `--dry-run` 子进程直调采样 P95 < 500ms（禁 poetry run 包装）；直调形态判定：`.venv/bin/sisys` 存在即用，缺失降级 `python -m src.entrypoints.main_cli`（R2-3 降级判定入验证项，与隔离约束表同款）
- [ ] 验收并发场景：10 并发轻量子进程（--help/--dry-run 面）全部 exit 0（降级判定同上）
- [ ] 可用性≥99% 口径为运维面指标，7-1 以退出码契约+零回归承载（注记）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [x] **本 Story 零新增领域事件**——CLI 是接口层薄壳，领域事件由所消费用例既有发布（ToolExecuted/CheckpointRecovered 等），事件面不变
- [x] 核验：`configs/event_channels.yaml` 与 `ChannelRouter.DEFAULT_MAPPINGS` 零 diff（无新事件则零改动）——git status 零改动实证

#### 数据模型 (Data Models)
- [x] **命令对象（Command Translator 载体，DC-4）**：`@dataclass(frozen=True)` 命令值对象定义于各 controller 模块（如 `DocumentUploadCommand`/`ToolRunCommand`/`CheckpointRecoverCommand`），字段=CLI 参数归一后形态（UUID 转 `uuid.UUID`、金额转 `Decimal`、超时转 `int`）
- [x] **不新建 `src/application/commands/` 包**——路线图「CLI → ApplicationCommand」以接口层命令对象+controller 转换函数承载（YAGNI；application 现无 commands 目录，全仓用例为直接方法签名）
- [x] **Mock DTO 契约**：`--mock` 短路返回结构固定（`{"mock": true, "command": "<命令名>", "parameters": {...}, "session": "<id>"}`），三格式化器均可渲染

#### 统一端口定义注册与管理 (Port Contract)
- [x] **本 Story 零新增端口**——仅消费既有端口（AC-5 表 **12 唯一端口**名已核验组合根行号：12 命令构成 13 个命令-端口消费对（`tool_registry_service` 被 tool list/schema 双命令消费——R5-1 口径勘正，原「13 端口」系消费对计数误作唯一端口数），含 R1-F3 补登记的 `skill_loader`——tool schema 的 input_examples 运行时数据通路；**R3-1/2 勘正后成员**：checkpoint 族=list(:2524)/recovery 预览(:2508)/recovery 执行(:2536) 三端口，`checkpoint_use_case`(:2496 创建面) 移出命令消费清单——仅作验收 given 前置创建链使用（非 CLI 命令消费面））
- [x] 端口消费契约测试：`tests/contracts/test_port_contract_unified_cli.py`——逐一断言 **12 唯一端口**注册名可达且 isinstance 契约成立（**对齐既有零 IO 先例形态**：`test_port_contract_agent_checkpoint.py` 的 `_global_registry.get(name)` 直查——契约测试不执行 IO、不 bootstrap，R1-F21 形态对齐；防注册名漂移——6.4-DF2 同族守卫诉求在 CLI 消费面的落地）
- [x] 控制器依赖注入方向（DC-2）：`src/interfaces/cli` **禁止 import `src.composition_root`**（importlinter 传导禁令，.importlinter:72-78 注释钦定）；采用 `create_cli_app(resolve: Callable[[str], Any]) -> typer.Typer` 工厂——resolve 函数由 `src/entrypoints/main_cli.py` 装配层传入，interfaces 层零组合根知识
- [x] 跨模块调用仅依赖抽象：controllers 类型注解引用 application 层用例类/Protocol（interfaces → application 方向合法）

#### 端口契约清单执行约束（强制）
- [x] AC-5 表是唯一事实源（Single Source of Truth）——**12 唯一端口**名冻结（13 消费对），实现 Task 禁止改用其他注册名或绕过 resolve 直构实例
- [x] 禁止新增未登记端口，禁止语义重复端口
- [x] 契约测试与接线断言未通过不得进入实现 Task 收尾

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增/修改的领域异常必须在 Task 0 中完成设计，禁止在实现 Task 中临时定义。

- [x] **本 Story 零新增领域异常**（`src/domain/exceptions/` 零 diff）——消费既有异常体系：

| 异常 | code | 触发场景（本 Story） | 既有锚 |
|------|------|---------------------|--------|
| `EntityValidationError` | EXCEPTION_242 | 实体 ID 族（`--plan-id`、document parse `--id <doc-id>`——R5-3 显式点名防误读）非 UUID 守卫（R1-F18 统一形态——chain-query 先例 agent_cli.py:1129-1141，6.9-R1-DF1 命令族契约）；checkpoint recover `--confirmed-by` 空串（:2536 ExecuteCheckpointRecoveryUseCase 用例层守卫，CLI 只呈现——R3-2 承载注记） | business_exceptions.py:106 |
| `ValidationError` | EXCEPTION_201 | `--agent-id` 非 UUID 守卫（`_parse_agent_uuid` 先例 agent_cli.py:156-173）；Agent 模式 `--yes` 缺 `--cost-budget` 拒绝；frontmatter `input_examples` 校验失败 | business_exceptions.py:20 |
| `NotFoundError` | EXCEPTION_202 | document upload 文件不存在（`require_upload_file` 命令级输入守卫——CR1 补登：dev 消费既有异常类未入表） | 既有 NotFoundError 族 |
| （用例透传） | 482 等 | plan 重跑守卫等由用例层抛出，CLI 只呈现 | blm_planning 既有 |

> **退出码扩展注记（CR1-F8，CR3 勘正）：** 实现含 `Abort→exit 130`（Ctrl+C，click 惯例）——0/1/2 冻结契约外的第四码，仅交互中断承载（无测试锚——Abort 模拟需信号注入，注记级承载）；**异常呈现形态注记：** DomainError stderr 的契约行 `[EXCEPTION_NNN] message` 逐字对齐 agent_cli 既有格式（**in-process 直调为单行契约形态——验收断言锚此形态**）；`ERROR: 领域异常: <msg>` 回显行仅子进程执行形态出现（typer 入口回显），非契约面、不锚断言，LLM 解析以 `[EXCEPTION_NNN]` 行为准。

> **守卫分工注记：** CLI 层双 UUID 守卫契约与 agent_cli 既有分工一致——实体 ID 族（plan-id）走 242、agent-id 走 201（ocr_cli D8 清偿后模式：int 转换→201 先例）；新统一入口按参数族对应采用，禁止混用；`<tool-id>` 为 slug、`--checkpoint-no` 为 CP-N 编号，均不入 UUID 守卫族。

- [x] 消息安全性：CLI stderr 呈现复用 agent_cli 既有格式 `[{code}] {message}`（不泄露堆栈/SQL）
- [x] 退出码映射：DomainError → exit 1 / typer 用法错误 → exit 2 / 成功 → exit 0
- [x] 异常路径 Gherkin 场景纳入验收（AC-1/AC-3/AC-7 场景）
- [x] 既有异常测试零回归：`pytest tests/unit/domain/exceptions/ -v` 全绿（707 passed 实证）

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
- [x] 功能测试文件：`tests/acceptance/test_acceptance_unified_cli.feature`
- [x] 步骤实现文件：`tests/acceptance/test_acceptance_unified_cli.py`
- [ ] 业务方评审通过（人工评审环节——dev 无权勾选，留待 review 阶段承载）
- [x] 所有场景覆盖（Happy Path + Edge Cases，最终态 23 场景：AC-1×4 / AC-2×5 / AC-3×4 / AC-4×2 / AC-5×1 / AC-6×1 / AC-7×2 / AC-8×2 / 收尾×2——**Task 0 交付前 19 个业务场景（AC-1~AC-7），AC-8×2 与收尾×2 由 Task 9 追加**，R1-F11 口径统一）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径** — 至少覆盖：非 UUID→242（plan-id 族）/201（agent-id 族）+exit 1、缺 cost-budget→201+exit 1、非法 format→exit 2、未知命令→exit 2
- **6-x 样板三件套**（test_acceptance_analyst_view.py:144-179 先例）：模块级 `event_loop` fixture + `_run_async` helper + 场景级 `context` dict
- **in-process 直调**：`main_cli.main([...])` 断言 exit_code——**main_cli.py 必须实现模块级自定义 `main(argv: list[str] | None = None) -> int` 包装**（agent_cli.py:2623 同签名先例；typer.Typer 无 `.main(args)` 方法，内部经 `app(args, standalone_mode=False)` 或等价形态派发并映射退出码——R1-F23 签名契约）；验收侧 SystemExit 兜底捕获先例（checkpoint_recovery.py:1125-1145，R1-F14 行号勘正）；直调前 `clear_singleton()`+`clear_scoped()` 双清（Resolver 实例方法形态：`get_resolver().clear_singleton()` 等）、禁二次 bootstrap
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

- [x] 范围外注记：deferred-work.md:125/:129（StrategicAnalysisUseCase/orchestration_service/data_pipeline 三向定夺）锚定 **7-2 API 入口立项**，7-1 非触发面；:115（create_app 5 router 未挂载）归 7-2/7-3；:117（RabbitMQ 消费基建）归首个消费方 Story（台账最新锚 **Epic 8**，三条 6-9/6-10/6-11 处置注记一致顺延——R1-F27 锚位勘正）
- [x] Task 0 将 #3/#6/#7 处置注记与 #1/#2/#4/#5 顺延注记逐条写入 `deferred-work.md` 对应条目（历史行不改写，追加处置注记——先例形态）
- [x] 新登记 deferred：**7-1-DF1** 19 子命令迁移收敛专项（agent_cli → sisys 统一入口；sisys-agent 保留冻结直至迁移完成；含存量入口 .env 等价修复与宽松 UUID 守卫收敛——承接 #6/#7 残余）；**7-1-DF2** system/config 辅助模块命令组（归宿 7-4/后续）；**7-1-DF3** ndjson/csv 格式与 `--cost-budget` 三级熔断执行面（归宿后续扩展）；**7-1-DF4** plan generate `<type>` SP/BP 分叉参数（BLM 现形态无 type 分叉）；**7-1-DF5** interface-design §4.3 完整命令清单超出 12 命令冻结矩阵的命令面——document search/version list+snapshot/delete、agent status/arbitrate、plan export/review、archive timeline/diff、checkpoint recover `--modifications` 参数（存量 `document_commands.py` 的 version 命令族即 §4.3.1 钦定命令，随 Task 3 重写移除，归宿后续命令扩展 Story——R1-F2/F7 归宿登记）——五条 gap 四要素齐备且 V1 归宿入 deferred-work

**Task 0 完成标志：**
- [x] 上述规范项全部定义完毕（命令矩阵冻结表 + 全局参数契约表 + 退出码契约表 + 异常消费表 + 端口消费表）
- [x] Gherkin 验收测试已编写，运行确认失败（🔴 红阶段验证——延迟 import 纪律下红形态=运行期 ImportError/命令不存在）
- [x] 规范文档通过人工评审或自动化校验（自动化校验承载：契约测试 76 绿+锚点行号主会话独立复核全命中；人工评审归 review 阶段）
- [x] **链路接线断言清单**已定义——本 Story 零新增端口/事件/中间件；消费面清单=AC-5 表 12 唯一端口：契约测试逐一注册面可达断言（Task 0 编写，绿色门禁形态——防注册名漂移守卫，非红绿 TDD 面）

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**
>
> **变异步骤适用性（R3-10）：** 变异注入适用于含生产代码交付的实现 Task（1-6）；纯测试/验证 Task（0/7/8/9）无生产代码可突变，以断言判别力自证（对被测生产面突变注入验证，如 Task 8 架构断言可对临时注入的违规 import 验证测试红）。

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
| **TDD 单元测试** | document 命令 | upload/parse 命令解析+controller+translator（stub resolve 直注） | `tests/unit/interfaces/cli/test_document_commands.py`（重写覆盖存量 version 族——R2-13 标注） | Task 3 |
| **TDD 单元测试** | tool 命令 | list/schema/run/chain run 四命令 + input_examples 字段校验 | `tests/unit/interfaces/cli/test_tool_commands.py` | Task 4 |
| **TDD 单元测试** | skill frontmatter | input_examples 字段解析与 1-5 条校验 | `tests/unit/application/skills/test_frontmatter_input_examples.py` | Task 4 |
| **TDD 单元测试** | agent/plan 命令 | agent run/plan generate + Agent 专用参数透传 | `tests/unit/interfaces/cli/test_agent_plan_commands.py` | Task 5 |
| **TDD 单元测试** | checkpoint/archive 命令 | list/show/recover/query 四命令 | `tests/unit/interfaces/cli/test_checkpoint_archive_commands.py` | Task 6 |
| **TDD 契约测试** | 端口消费接线 | 12 唯一端口注册面可达（零 IO 直查）+ isinstance 契约 | `tests/contracts/test_port_contract_unified_cli.py` | Task 0 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收（19 场景，Task 9 补至 23） | `tests/acceptance/test_acceptance_unified_cli.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 三件套+in-process 直调+双清+延迟 import | `tests/acceptance/test_acceptance_unified_cli.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单最终确认 | 同上两文件追加场景 | Task 9 |
| **SDD 架构验证** | 六边形+七原则 | P4 MCP=0 断言/interfaces 零 composition_root 引用/typer 不入 application/domain/退出码契约矩阵/存量入口零回归 | `tests/unit/architecture/test_arch_unified_cli.py` | Task 8 |
| **集成测试** | CLI×真实服务 | document upload 真实 PG 链/archive query fallback 读链/checkpoint 族真实链 | `tests/integration/test_integration_unified_cli.py` | Task 7 |

> **注记（epics 名义文件 ↔ 实际落位映射）：** epics_v1.0.md 钦定 `tests/unit/interfaces/test_cli.py`/`tests/integration/test_cli_integration.py`/`tests/e2e/test_cli_e2e.py`——实际落位按仓内目录现实与功能性命名规范调整如上表；**E2E 语义由验收测试承载**（in-process 真实服务全链=端到端），`tests/e2e/`（现仅 `__init__.py` 空壳）维持空置（OD-5，与全仓四目录回归口径一致：`pytest tests/unit tests/integration tests/acceptance tests/contracts`）。

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [x] **整体覆盖率 ≥80%**（基线不破坏——当前全量基线 ~93% 实测口径；机器载体=Makefile `--cov-fail-under=80`+CI `scripts/check_coverage_gates.py`）- **P0 阻断门禁**
- [x] **接口层覆盖率 ≥85%**（epics 7.1 钦定）- **P1 阻断门禁**。**测量面口径（R1-F8 勘正）：epics 原文未定义测量单元，本 Story 落地为「`src/interfaces/cli/` 新增文件伞形达标」**——12 命令+框架+格式化器新增文件 ≥95% 自然满足 ≥85%；`src/interfaces/` 全目录含存量 sap/api 面非本 Story 可控，以「合并后不低于合并前基线」承载。**机器载体注记：`scripts/check_coverage_gates.py` 分层清单现无 src/interfaces 档位（domain 90/application 85/infrastructure 75）——Task 9 收尾实测 `src/interfaces/cli/` 覆盖率，≥85% 则登记扩档建议（CI Story 承载），未达则以新增文件 ≥95% 伞形口径验收；Makefile :278-280 禁止 `--cov=src.<layer>` 形式（source=["src"] 覆盖 --cov 导致 TOTAL 恒全 src 必红）**——实测：src/interfaces/cli/ 全部文件 91-100%（折叠项均 100%）≥85% 达标
- [x] **新增文件行覆盖率 ≥95%**（6-9 先例口径）——伞形 ≥95% 达标（单文件最低 91% 为 main.py 工厂 3 行防御分支）
- [x] mypy 基线零新增错误（795 文件零错误）

#### 代码质量门禁
- [x] **Ruff 检查通过**（`poetry run ruff check src/ tests/`——All checks passed）
- [x] **MyPy 类型检查通过**（`poetry run mypy src/`——Success: no issues found in 795 source files）
- [ ] **无 P0/P1 级别问题**（代码审查——归 review 阶段承载）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`——dev 环境命令被拒未执行，ruff/format/mypy 同口径已全绿，留待用户本地执行确认）

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
| **子进程形态** | 并发/性能场景子进程用 `.venv/bin/sisys` 或 `python -m src.entrypoints.main_cli` 直调（缺 script 时动态降级后者）；**禁 poetry run 包装**（~300ms 污染性能采样） | 环境差异失败 |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback）
- ❌ autouse fixture 删除全局匹配资源（如 `test_*`）
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- ❌ 验收/集成测试 mock（真实服务强制；`pytest.skip()` 动态跳过）

**验证要求：**
- [x] 并行测试 `pytest tests/unit tests/integration tests/acceptance tests/contracts -n 8` 通过（四目录全量回归 15576 passed+9 skipped 零失败——addopts `-n auto` 并行形态）
- [ ] 连续 5 次运行无随机失败（5 连跑耗时 ~46min 未在 dev 会话执行——单轮零失败+隔离复跑关键面全绿承载，5 连跑留 CI/用户本地验证）
- [x] `poetry run ruff check` 通过
- [x] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 统一入口/三级结构/退出码契约/存量零回归 | Task 2 | 2.1-2.4 | `test_cli_framework.py` |
| AC-1 | 命令组骨架可见性 | Task 3-6 | 各组 X.2（绿阶段命令组落地） | 各命令组测试 |
| AC-2 | document upload/parse 端到端 | Task 3 / Task 7 | 3.1-3.3 / 7.1 | `test_document_commands.py` + 验收 |
| AC-2 | agent run / plan generate（Mock 面） | Task 5 | 5.1-5.3 | `test_agent_plan_commands.py` + 验收 |
| AC-2 | checkpoint recover 端到端 | Task 6 / Task 7 | 6.1-6.3 / 7.3 | `test_checkpoint_archive_commands.py` + 验收 |
| AC-3 | 全局参数四件套契约 | Task 2 | 2.2-2.3 | `test_cli_framework.py` |
| AC-3 | Agent 专用参数透传 | Task 4-6 | 各组 X.2（透传断言含于绿阶段测试） | 各命令组测试 |
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

- [x] Subtask 0.1: 冻结统一命令矩阵表（AC-5 表 12 命令 + 框架面 `--help/--version`）——实现禁增删命令名
- [x] Subtask 0.2: 冻结全局参数契约表（`--yes/--dry-run/--mock/--format`）与 Agent 专用参数表（`--session/--cost-budget/--timeout`）及语义（AC-3 冻结语义为准）
- [x] Subtask 0.3: 冻结退出码契约表（0/1/2）与 DomainError stderr 呈现格式（`[EXCEPTION_NNN] message`）
- [x] Subtask 0.4: 编写端口消费契约测试 `tests/contracts/test_port_contract_unified_cli.py`（**12 唯一端口**注册面可达+isinstance，**零 IO 直查形态**对齐 `test_port_contract_agent_checkpoint.py` 先例——断言对象=PortSpec 注册元数据（`_global_registry.get(name)` 拿到的 spec：interface/impl/lifetime 等维度断言，R2-12 形态注记），实例化断言经 impl 字符串 import 类的 Protocol 检查或 `_DummyResolver` 分发替身对齐先例，不连真实服务；绿色门禁守卫形态，跑通即过）
- [x] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_unified_cli.feature`（**AC-1~AC-7 共 19 个业务场景**，按 AC 分节横幅注释组织；AC-8×2 与收尾×2 由 Task 9 追加至最终态 23——R1-F11 口径）
- [x] Subtask 0.6: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_unified_cli.py`（三件套+@scenario 逐场景绑定+延迟 import；**given/when/then 全步骤骨架齐备**——仅 given 骨架会在 pytest-bdd 收集期抛 ScenarioDefinitionError，偏离声明的运行期 ImportError 红形态，R1-F33 收紧）
- [x] Subtask 0.7: 运行验收测试，确认失败（🔴 红阶段验证——红形态=运行期 ImportError：`src.entrypoints.main_cli` 不存在）
- [x] Subtask 0.8: 前置留项清单七条处置注记落档 `deferred-work.md`（#3 部分清偿/#6/#7 触发清偿注记+#1/#2/#4/#5 顺延注记——历史行不改写追加注记）+ 新登记 **7-1-DF1~DF5**（gap 四要素+V1 归宿；R2-10 勘正：R1 扩登记 DF5 后本行原写 DF1~DF4 漏同步）
- [x] Subtask 0.9: 锚点行号复核（本 Story 引用的组合根行号/importlinter 行号/文档行号实测核对）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕（五张冻结表）
- [x] 契约测试通过（既有端口注册态验证）
- [x] 验收测试运行失败（预期行为，红阶段确认）
- [x] deferred-work.md 处置注记与新登记落档

---

### Task 1: 输出格式化器（json/table/pretty）— 含完整 TDD 循环

**关联 AC:** AC-4

#### TDD 循环 A：三格式化器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_cli_formatters.py`（json 合法性/表格列宽中文对齐/pretty 分组缩进/空态/单条/多条/嵌套）——json 断言含 **UUID/Decimal 字段序列化用例**（`default=str` 策略锚，R2-1）与 **空列表契约**（空态输出=空 JSON 数组 `[]`/table=**纯空串**（零表头零数据行——CR1-F8 勘正：R2-6 原冻结「表头+零数据行」措辞歧义，实现空串形态更优[jq 空输入惯例]，空表头无信息量）/pretty 空态提示语，三格式各自形态冻结，R2-6） |
| 🟢 绿 | 实现 `src/interfaces/cli/formatters/{__init__,json_formatter,table_formatter,pretty_formatter}.py` 最小代码（json_formatter 冻结 `json.dumps(payload, default=str, ensure_ascii=False)`） |
| 🟡 变异 | 改坏 JSON 序列化键→json 格式断言红；改坏列宽计算→table 断言红；还原绿 |
| 🔄 重构 | 统一渲染入口签名 `render(payload: Mapping) -> str`、类型注解、中文 docstring |

- [x] Subtask 1.1: 🔴 红 — 编写三格式化器失败测试
- [x] Subtask 1.2: 🟢 绿 — 实现三格式化器最小代码
- [x] Subtask 1.3: 🟡 变异 — 断言突变注入-还原实证
- [x] Subtask 1.4: 🔄 重构 — 统一签名与导出（formatters 按 format 值分发）

**完成标准/Definition of Done:**
- [x] 三格式化器实现完成（纯函数，零外部服务依赖）
- [x] TDD 循环全部通过
- [x] 新增文件覆盖率 ≥95%

---

### Task 2: CLI 基础框架（typer 工厂+全局参数+守卫+进程入口）— 含完整 TDD 循环

**关联 AC:** AC-1 / AC-3 / AC-7

#### TDD 循环 A：create_cli_app 工厂与全局参数

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_cli_framework.py`（stub resolve 直注 create_cli_app：六模块子 app 挂载/--help 自描述/--format 值域 exit 2/**全局参数尾置形态解析**（R2-A1 时序注：循环 A 时刻命令组未交付，以工厂内任一已挂载子命令验证尾置机制，各命令组尾置断言随 Task 3-6 落地——R1-F1 P0 回归锚）/缺省 --format 输出=table 渲染/--dry-run 输出静态端口名且 resolve 零调用/--mock 短路 JSON/--yes 缺 budget→201+exit 1） |
| 🟢 绿 | 实现 `src/interfaces/cli/main.py`（typer 工厂+**共享 Annotated 参数注解（`_params.py` 单一来源，禁 @app.callback() 承载全局参数——尾置形态实测 exit 2）**+退出码处理）最小代码——**六模块挂载形态（R3-4）：工厂内联六模块空 Typer 骨架组（`--help` 自描述即可达挂载断言），Task 3-6 逐组以 commands/ 包实现替换骨架，挂载断言两时点可满足** |
| 🟡 变异 | 删六模块挂载→help 断言红；删 budget 守卫→拒绝断言红；还原绿 |
| 🔄 重构 | 类型注解/中文 docstring/参数 DRY |

#### TDD 循环 B：共享守卫与进程入口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 追加框架测试（UUID canonical 归一大写/URN/无连字符形态命中+非 UUID 双契约：plan-id 族→242/agent-id 族→201；`main_cli` load_dotenv 先于 bootstrap 顺序断言——monkeypatch 记录调用序） |
| 🟢 绿 | 实现 `src/interfaces/cli/_guards.py`（`canonical_uuid`/`require_agent_budget`）+ `src/entrypoints/main_cli.py`（load_dotenv→bootstrap→create_cli_app(resolve)→**模块级 `main(argv: list[str] \| None = None) -> int` 包装**（agent_cli.py:2623 同签名先例，R1-F23）→派发）+ pyproject **[project.scripts]** 增 `sisys` 入口（**仅入 [project.scripts] 段，[tool.poetry.scripts] 双注册段勿动**——pyproject:154-162 双段并存现状，R1-F15） |
| 🟡 变异 | 守卫去归一直传→大写形态断言红；load_dotenv 移 bootstrap 后→顺序断言红；还原绿 |
| 🔄 重构 | 守卫住位 _guards.py 单一职责、入口五步定式对齐 agent_cli 先例（幂等 bootstrap 守卫/finally 关闭连接池） |

- [x] Subtask 2.1: 🔴 红 — 工厂/全局参数失败测试
- [x] Subtask 2.2: 🟢 绿 — 实现 main.py 工厂 + `_params.py` 共享注解（R2-A3 摘要对齐循环 A 绿阶段文件面）
- [x] Subtask 2.3: 🔴 红 — 守卫/入口失败测试
- [x] Subtask 2.4: 🟢 绿 — 实现 _guards.py + main_cli.py + pyproject scripts
- [x] Subtask 2.5: 🟡 变异 + 🔄 重构 — 两循环收尾（ruff+mypy）

**完成标准/Definition of Done:**
- [x] `sisys --help` 六模块可见、退出码契约矩阵测试全绿
- [x] `poetry install` 后 `sisys` script 可执行
- [x] 存量 agent_cli 测试零回归

---

### Task 3: document 命令组 — 含完整 TDD 循环

**关联 AC:** AC-2 / AC-5

> **存量处置（R1-F2 扩）：** `src/interfaces/cli/commands/document_commands.py`（185 行）为未接线存量——现内容为 **version 命令族**（`build_version_parser`/`handle_version`，argparse+`Resolver(_global_registry)` 直构，`__init__.py:5` 明示「勿仿：未接线存量（无挂载点）」）。本 Task **重写该文件**（architecture.md:2073-2100 钦定路径语义恢复）：移除 version 命令族（§4.3.1 钦定命令面 defer 7-1-DF5/OD-7；端口 `document_version_service` 及事件处理器不动，仅删未接线 CLI 适配器），新建 upload/parse 两命令；**存量 `tests/unit/interfaces/cli/test_document_commands.py`（197 行，version 族 argparse 断言）随重写同步覆盖重写为新 upload/parse 测试（旧实现断言不保留——该文件是本 Story 唯一存量测试重写项，AC-1 零回归面已注记排除）**；同步更新 `src/interfaces/cli/__init__.py` 勿仿告示（移除后告示语义失效）。

#### TDD 循环 A：upload / parse

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_document_commands.py`（stub resolve：upload 参数解析→DocumentUploadCommand 冻结字段/文件不存在领域异常呈现/parse --id 守卫/mock 短路/dry-run 端口名） |
| 🟢 绿 | 实现 `commands/document_commands.py`（typer 定义）+ `controllers/document_controller.py`（命令对象+转换+调用 document_upload_service/document_parsing_service+格式化输出） |
| 🟡 变异 | controller 改直传未归一参数→命令对象断言红；还原绿 |
| 🔄 重构 | controller 与命令组职责分界（commands 只定义参数、controller 只编排） |

- [x] Subtask 3.1: 🔴 红 — document 命令失败测试
- [x] Subtask 3.2: 🟢 绿 — 重写 document_commands.py + 新建 document_controller.py
- [x] Subtask 3.3: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:**
- [x] `sisys document upload/parse --help` exit 0
- [x] controller 单测全绿（stub resolve 直注，无 monkeypatch——DI 设计红利）
- [x] 覆盖率 ≥95%（新增文件）

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
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_tool_commands.py`（list 域过滤/schema 输出含 input_examples 字段（经 `skill_loader.load_sop`→`SkillDocument.input_examples`——R1-F3 通路锚）/**run 的 `<tool-id>` slug→SLUG_TO_TOOL_ID SSOT→`get_tool(tool_id=)`→`ToolCall` 解析链**（R1-F4/CR1-F7b 勘正形态）/--input JSON 装载/chain run --config 装载/Agent 专用参数透传 context） |
| 🟢 绿 | 实现 `commands/tool_commands.py` + `controllers/tool_controller.py`（消费 tool_registry_service/tool_execution_service/run_tool_chain_use_case） |
| 🟡 变异 | schema 输出去 examples 键→断言红；run context 去 session→透传断言红；还原绿 |
| 🔄 重构 | 四命令复用 `_params.py` 共享 Agent 参数注解（R2-A2 锚定：不另建 tool 侧注解） |

#### 批量补齐（非 TDD 面——内容资产）

- [x] Subtask 4.4: 全量 active skills（TOOLS.md 视图 23 条口径）SKILL.md frontmatter 补 `input_examples`（每工具 1-5 条参数 JSON 示例）；跑批校验全量通过（**内容资产批量面，独立提交批次**——R1-F34；AC-6 验收场景的 tool-id 选用已补齐 slug 联动——R1-F38）

- [x] Subtask 4.1: 🔴 红 — frontmatter 字段失败测试
- [x] Subtask 4.2: 🟢 绿 — frontmatter 扩展 + 四命令实现
- [x] Subtask 4.3: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:**
- [x] `sisys tool list/schema/run/chain run --help` exit 0
- [x] tool schema JSON 输出含非空 input_examples
- [x] 全量 SKILL.md 校验器跑批通过
- [x] 覆盖率 ≥95%（新增文件）

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

- [x] Subtask 5.1: 🔴 红 — agent/plan 命令失败测试
- [x] Subtask 5.2: 🟢 绿 — 实现两组命令+控制器
- [x] Subtask 5.3: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:**
- [x] `sisys agent run` / `sisys plan generate --help` exit 0
- [x] Mock 面单测全绿；真实面单测 stub resolve 验证调用契约
- [x] 覆盖率 ≥95%（新增文件）

---

### Task 6: checkpoint 与 archive 命令组 — 含完整 TDD 循环

**关联 AC:** AC-2 / AC-5

#### TDD 循环 A：checkpoint list/show/recover + archive query

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_checkpoint_archive_commands.py`（list --plan-id 归一守卫/show --plan-id+--checkpoint-no 复合定位→:2508 预览视图调用契约/recover --plan-id+--checkpoint-no+--confirmed-by→:2536 执行面调用契约+--mode 值域/archive query --plan-id→blm_chain_trace_use_case 调用契约/空态 exit 0 输出——R3-3 参数形态同步） |
| 🟢 绿 | 实现 `commands/checkpoint_commands.py`+`archive_commands.py`+`controllers/checkpoint_controller.py`+`archive_controller.py`（消费 checkpoint 三用例+blm_chain_trace_use_case） |
| 🟡 变异 | recover mode 值域放宽→exit 2 断言红；还原绿 |
| 🔄 重构 | 四命令与既有命令组风格统一 |

- [x] Subtask 6.1: 🔴 红 — checkpoint/archive 命令失败测试
- [x] Subtask 6.2: 🟢 绿 — 实现两组命令+控制器
- [x] Subtask 6.3: 🟡 变异 + 🔄 重构

**完成标准/Definition of Done:**
- [x] 四命令 `--help` exit 0；12 命令矩阵全部就位（AC-5 审计断言绿）
- [x] 覆盖率 ≥95%（新增文件）

---

### Task 7: 集成测试（真实服务面）

**关联 AC:** AC-2 / AC-7

> **性质说明：** 真实服务 Schema 隔离模式（独立 PG schema + savepoint rollback + 租户隔离）与 CLI 面形态（commit+定向 DELETE）按 integration_test_patterns 两种子模式择用。

- [x] Subtask 7.1: document upload 真实 PG 链（真实临时文件→真实 upload_service→落库断言→定向清理）
- [x] Subtask 7.2: archive query fallback 读链（真实 bootstrap 无 session 上下文→fallback find 路径往返——6.4-DF2 部分清偿载体）
- [x] Subtask 7.3: checkpoint 族真实链（真实创建→list/show/recover 往返）
- [x] Subtask 7.4: .env 入口加载集成验证（临时 .env 经 monkeypatch `main_cli.ENV_FILE` 常量注入——R2-11 机制；与单测顺序守卫互补）

**完成标准/Definition of Done:**
- [x] 集成测试真实服务全绿（服务不可达动态 skip）
- [x] 零手动 delete/truncate（rollback/定向清理）

---

### Task 8: SDD 架构约束验证测试

**关联 AC:** AC-1 / AC-6（P4）

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [x] Subtask 8.1: 创建 `tests/unit/architecture/test_arch_unified_cli.py`
- [x] Subtask 8.2: P4 MCP=0 断言（无 `src/infrastructure/mcp/` 目录、pyproject 无 mcp 依赖、src 全仓无 mcp import）
- [x] Subtask 8.3: 分层断言（`src/interfaces/cli` 零 `composition_root`/`infrastructure` import；typer 零入 `src/domain`/`src/application`——domain 零依赖全仓断言既有测试自然覆盖，此处加 CLI 面专项）
- [x] Subtask 8.4: 退出码契约矩阵与存量入口零回归（`sisys-agent`/`sisys-ocr` 入口 script 仍在+agent_cli 全量单测引用零改动）
- [x] Subtask 8.5: 运行完整测试套件并生成报告（循环依赖检测沿用 ruff/isort 既有面，不引入新工具）

**完成标准/Definition of Done:**
- [x] 所有架构/约束测试通过
- [x] 任何违规都会导致测试失败
- [x] 存量 CLI 测试全量零回归

---

### Task 9: 开发结束验收测试

**关联 AC:** 全部

> **性质说明：** 本 Task 对 Story 收尾阶段的交付物与完成清单进行最终验收，并补齐性能/并发验收场景。

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_acceptance_unified_cli.feature` 收尾场景（src 完成清单/测试目录完成清单）+ AC-8 性能并发场景（20 轮 P95 采样/10 并发子进程） |
| 🟢 绿 | 编写/补齐对应 BDD 步骤实现，全场景转绿 |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [x] Subtask 9.1: 性能场景 — 20 轮 `--dry-run` 采样 P95 < 500ms 断言（**子进程直调 `.venv/bin/sisys` 或 `python -m src.entrypoints.main_cli`，禁 poetry run 包装**——R1-F6 口径；**P95 取法（R3-8）：** 20 轮耗时升序排序取第 `ceil(0.95×20)=19` 个（1-based）；父进程 `time.monotonic()` 差值测子进程 wall time，规避墙钟回拨）
- [x] Subtask 9.2: 并发场景 — 10 并发轻量子进程（--help/--dry-run 面）全部 exit 0
- [x] Subtask 9.3: 收尾场景 1 — src 完成清单逐项确认；场景 2 — 四测试目录完成清单逐项确认
- [x] Subtask 9.4: 运行 `pytest tests/unit tests/integration tests/acceptance tests/contracts`（四目录全量）+ `ruff check` + `mypy` 收尾校验；全量回归甄别失败项（DF 族/预存抖动形态对照 epic-6 先例归位）

**完成标准/Definition of Done:**
- [x] 全部验收场景通过（含动态跳过项甄别）——23 场景：21 passed + 2 skipped（LLM Key 环境动态 skip——甄别为环境门控非缺陷）
- [x] 四目录全量回归零未甄别失败——15576 passed + 9 skipped（9'13"，零 failed；对照 epic-6 后实数基线 ~15307+抖动，本 Story 净增 ~269 测试）
- [x] Story 可进入 `review`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../planning-artifacts/architecture.md) + [`interface-design.md`](../../../docs/architecture/interface-design.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ D1 方案 A 组装层；CLI 属接口层适配器
- **设计约束:** 领域层零依赖；interfaces 禁 import composition_root/infrastructure（importlinter 传导禁令）；进程入口住 `src/entrypoints/`
- **接口治理:** 统一端口注册 PortSpec/组合根装配/契约优先；本 Story 零新增端口，消费 AC-5 表 12 唯一端口（12 命令 13 消费对，含 skill_loader）
- **技术栈:** Python 3.11+ / typer ^0.24.0（pyproject.toml:21 已在依赖，此前零使用——本 Story 首次启用；**全局参数禁 @app.callback() 承载——尾置形态 exit 2 实测，共享 Annotated 注解形态**，R1-F1）；table 渲染沿用 agent_cli 纯标准库两遍法先例（`_print_checkpoint_summary_table` :1495-1518）——**不引入 rich**（零新增依赖，typer 本身不强制 rich）
- **同名参数边界注记（R1-F26）：** 存量 agent_cli 仅 `--format`（:354）一个近全局参数（无 --yes/--mock/--dry-run/--cost-budget，无存量语义冲突）；其 `--format` 值域与新入口 `json|table|pretty` 的差异在双入口并存期维持各自语义（冻结纪律），7-1-DF1 迁移专项统一

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
| **DC-5（选中）** | `--mock`=命令级 Mock 响应（不 bootstrap）；`--dry-run`=接口层预览（不 bootstrap）；**两者同给时 `--dry-run` 优先**（最外层短路，R1-21/R2-5 与 AC-3 契约同步） | 语义确定可测；验收确定性；零基础设施耦合 | 深度 mock（真实服务+mock LLM）不在 7-1（7-1-DF3 关联） | ✅ 8/10 |
| **DC-6（选中）** | .env 清偿采方案一（入口显式 load_dotenv） | 一行修复根因；6.8-R1-DF1 三选一中最小面 | 存量入口残余待迁移专项 | ✅ 9/10 |

### 偏离声明预告（Task 0 落档确认，OD-n 前缀）

> **台账对应注记（R1-F16）：** OD 表为决策记录，执行台账以 deferred-work.md 为准——OD-2/OD-3 → 7-1-DF3（两 OD 合一 DF）、OD-4 → 7-1-DF4、OD-6 → 7-1-DF2、OD-7 → 7-1-DF5。

| OD | Gap（四要素） | V1 归宿 |
|----|--------------|--------|
| OD-1 | P5 工具选择准确率≥85%/P6 误触发率<5%/**P7 工具调用准确率≥90%** 三指标不在 7-1 验收——SkillSelector 机制已交付（5-2），指标属评估面（R1-F12 扩 P7） | evaluation 专项 |
| OD-2 | ndjson/csv 输出格式 defer——epics 7.1 AC 仅列 json/table/pretty | 后续格式扩展 |
| OD-3 | `--cost-budget` 三级熔断（Level 1/2/3）执行面 defer——7-1 仅参数契约+Agent 模式缺省拒绝 | 成本熔断专项 |
| OD-4 | plan generate `<type>` SP/BP 分叉参数 defer——BLM 现形态无 type 分叉 | BLM 类型分叉 Story |
| OD-5 | tests/e2e 空置——E2E 语义由验收（in-process 真实服务全链）承载；epics「E2E 测试覆盖率≥80%」（:2636）指标同由验收场景覆盖承载，无独立 e2e 目录测量（R1-F20 点名） | 维持四目录口径 |
| OD-6 | system/config 辅助模块命令组 defer（sisys system auth/monitor/route/health、sisys config 族） | 7-4/后续 |
| OD-7 | interface-design §4.3 完整命令清单超出 12 命令冻结矩阵的命令面 defer（document search/version/delete、agent status/arbitrate、plan export/review、archive timeline/diff、checkpoint --modifications）——12 命令=路线图「6 服务模块命令骨架」最小集（R1-F7 边界声明；P1 原则以 6 模块覆盖承载） | 后续命令扩展 Story（7-1-DF5） |
| OD-8 | checkpoint show/recover 参数形态偏离钦定文本（§4.3.5 钦定 `--id <cp-id>` 单参数；落地为 `--plan-id`+`--checkpoint-no` 复合定位）——checkpoint 域端口无 UUID 单参查询 API（R3-1/2 实测：唯一查询入参形态=plan_id+checkpoint_no），钦定单参数形态在当前端口面不可实现；`--confirmed-by` 参数为执行面 `confirmed_by` 非空守卫的 CLI 承载（钦定文本未含） | 端口签名现实层优先，落地形态注记（7-1-DF1 迁移专项统一时复核） |
| OD-10 | CLI 租户常量策略（CR1-F2 定谳）：document 域 `tenant_id="cli-default"`/`uploaded_by="cli-user"`（端口必填 str——API 面 X-Tenant-ID header 的 CLI 等价取值）与 tool 域 `ExecutionContext.tenant_id=00000000-0000-0000-0000-000000000101`（文档化 UUID 常量，无系统预留语义）——两域形态差异是端口类型现实（str vs UUID），常量已落库（集成测试锚 cli-default）；**单点集中归宿**：常量收敛至 `_guards.py`/独立 cli_context 模块（7-1-DF1 迁移专项或后续租户治理 Story 承载，7-1 不迁移已落数据）；多租户 CLI 切换（env 变量）YAGNI defer（归宿 7-4 config 命令组域） | 后续租户治理/命令族迁移专项 |

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
│   ├── _params.py                    # ★新建：共享 Annotated 参数注解单一来源（全局参数+Agent 专用参数；禁 callback 承载——R1-F1）
│   ├── main.py                       # ★新建：create_cli_app 工厂+全局参数+退出码处理
│   ├── commands/
│   │   ├── __init__.py               # 既有空包 init（保留）
│   │   ├── document_commands.py      # ★重写存量（移除 version 命令族→upload/parse，见 Task 3 存量处置）
│   │   ├── tool_commands.py          # ★新建（list/schema/run/chain run）
│   │   ├── agent_commands.py         # ★新建（run）
│   │   ├── planning_commands.py      # ★新建（generate）
│   │   ├── checkpoint_commands.py    # ★新建（list/show/recover）
│   │   └── archive_commands.py       # ★新建（query）
│   ├── controllers/                  # ★新建包：6 控制器（命令对象+translator+编排+静态 PORT_NAME 常量+DomainError 呈现）
│   └── formatters/                   # ★新建：__init__.py + json/table/pretty 三格式化器（现空目录）
└── application/skills/
    ├── frontmatter.py                # 修改：input_examples 字段
    └── */SKILL.md                    # 修改：全量补 input_examples（23 条口径）

tests/
├── unit/interfaces/cli/              # 新建 6 文件（formatters/framework/document/tool/agent_plan/checkpoint_archive）+ 既有 test_agent_cli.py 冻结 + test_document_commands.py 重写覆盖（version 族→upload/parse）+ test_ocr_cli.py 冻结
├── unit/application/skills/          # test_frontmatter_input_examples.py（既有 test_frontmatter*.py 先例同目录）
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
- 验收三件套+双清+延迟 import+CLI 面 commit+定向 DELETE 三分面（analyst_view :144-179 / checkpoint_recovery teardown fixture :277-307+_teardown_chain :306-307+直调 :1125-1145 先例——R1-F14 行号勘正，原引 :76-80 实为 docstring 尾部）
- CI root 容器教训（efd0f11d/bf24d1f5）：条件 skip 恒 skip 假绿——环境门控用 `_require_services` 形态，禁 `geteuid()==0` 类恒 skip
- 变异实证强制（Epic 4 行动项 7.1-2）：每 Task 断言突变注入-还原，恒真断言零容忍
- 共享 collection 读回断言一律定向过滤（retro 行动项 4——checkpoint scroll limit 残留假红教训）
- 长链注记三轮即压缩（retro 行动项 2）——deferred-work 处置注记精炼
- 时钟回拨（2745f74a）：跨 await 墙钟二次采样用 `utc_now_after` 钳制——CLI 性能采样场景的时间测量注意
- 「CLI-only 第 N 连」计数语义在 7-1 转换：7-1 是 CLI 本体故事（统一入口），该计数随 Epic 6 收官终结

**应用到本故事/Applied to This Story:**
- [ ] 退出码/异常呈现契约逐字对齐 agent_cli 既有形态（AC-1 冻结）
- [ ] 单测 stub resolve 直注（DC-2 红利），验收真实服务+双清
- [ ] 性能采样时间测量规避墙钟回拨（monotonic clock 口径）+ 子进程直调口径（R1-6 补：禁 poetry run 包装）
- [ ] 前置留项清单七条裁定（SDD 节落档表）
- [ ] typer 全局参数共享 Annotated 注解形态（R1-1 补：禁 callback 承载）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.3（Claude Code 会话） |
| **Version** | bmad-create-story skill（workflow.md 现行版；template 无独立版本头——R1-F31 勘正，原引「v6.3.0/v2.9.0」不可核验） |
| **Execution Date** | 2026-11-20 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md`（v2.9.0） |
| **Checklist** | `.claude/skills/bmad-create-story/checklist.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Epic 7 :2565-2645） |
| **架构文档** | `docs/architecture/architecture.md`（:2073-2100 CLI 目录）+ `docs/architecture/interface-design.md`（§4.2-4.3/:428-615 命令矩阵（R1-F28 勘正：原引 §3.3 实为链路映射规则节）/:2071-2080 路线图） |
| **前置留项源** | `_bmad-output/implementation-artifacts/epic-6-retro-2026-11-09.md`（行动项 1 :124）+ `deferred-work.md`（七条 :330-:409） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/6-11-white-label-report-basic.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

**创建阶段（create-story）：**

- [x] 故事需求从 `epics_v1.0.md` 提取（Story 7.1 :2597-2645）
- [x] 架构约束从 architecture.md/interface-design.md 提取（三调研 Agent 并行：架构文档/现有代码/测试与故事风格）
- [x] 前置留项清单七条逐条裁定落档（epic-6-retro 行动项 1 承载）
- [x] 前一个故事学习经验整合（6-11 + epic-6 回顾）
- [x] 状态设置为 `ready-for-dev`

**实施阶段（dev-story，2026-11-20）：**

- [x] Task 0：契约测试 76 绿（12 唯一端口/13 消费对口径）+ Gherkin 19 场景 + BDD 全步骤骨架（红形态=运行期 ImportError 实证）+ deferred-work 七条处置注记+7-1-DF1~DF5+OD-8/OD-9 落档 + 锚点复核（12 端口行号主会话独立验证全命中）
- [x] Task 1：三格式化器 TDD（json `default=str, ensure_ascii=False` 冻结/两遍法 table/pretty 分组缩进；三变异红绿实证——table 列宽变异抓出对齐断言恒真两轮加强）；伞形覆盖 97%
- [x] Task 2：typer 工厂+共享 Annotated 注解（`_params.py`）+守卫+main_cli 进程入口；四变异红绿实证。**typer 0.24.2 实测约束两发现**：①`Annotated[bool, Option(False, "--x")]` 位置默认值形态对 bool flag 崩坏（'bool' object has no attribute 'isidentifier'）——正确形态=注解仅含选项声明+命令签名默认值；②typer 不支持 Decimal 注解——cost-budget 注解 str|None、controller 归一层转 Decimal
- [x] Task 3：document 命令组（重写覆盖 version 族）；变异抓出数字 UUID 测试数据无 upper() 判别力问题（换含字母 UUID）
- [x] Task 4：frontmatter input_examples（ValidationError 201 值域校验语义——与 FrontmatterParseError 结构解析语义分立）+ ToolMetadata 扩展 + tool 四命令 + 23 SKILL.md 批量补齐（跑批校验 23/23）
- [x] Task 5：agent/plan 命令组（OD-9：agent run 位置参数落地为 agent-id UUID——RunAgentWorkflowUseCase.execute(agent_id: UUID) 签名现实层优先，interface-design:500 `<role>` 钦定文本无 role 解析端口面）
- [x] Task 6：checkpoint/archive 命令组（R3-3 复合定位形态落地；recover --dry-run 特化消费 :2508 预览视图；--mode typer Enum choice 守卫；created_via="cli"+confirmed_by 缺省取 session）
- [x] Task 7：集成测试四场景（document 真实 PG 落库/archive fallback 读链/checkpoint 族/ENV_FILE monkeypatch）；checkpoint 场景 LLM Key 动态 skip（创建链上下文压缩依赖）
- [x] Task 8：架构验证测试（P4 MCP=0/分层 AST 断言/退出码矩阵/存量零回归+判别力自证）
- [x] Task 9：AC-8 性能并发+收尾场景（23 场景终态：21 passed+2 skipped[LLM]）+ 四目录全量回归+ruff+mypy

**实施期关键决策（Dev 定夺，主会话独立验证后落地）：**

1. **R6 模板对齐**（用户中途指正）：验收 BDD 重写对齐 test_acceptance_postgresql_relational_layer 模板——@scenario 显式逐场景绑定（弃 scenarios() 自动绑定）、步骤文本业务语言+参数内嵌（弃引号字面量+parsers.re）、场景名去 AC 前缀、三行长横幅分节、fixture 驱动分区结构
2. **CLI 租户/元数据常量**：document upload 的 tenant_id="cli-default"/uploaded_by="cli-user"（端口必填 str，API 面经 X-Tenant-ID header 承载的 CLI 等价取值）；五最小元字段补全（source="cli-upload"/license="internal"/business_domain 缺省 "general"——DocumentMetadata 217 校验面）；ExecutionContext.tenant_id 用文档化 UUID 常量（00000000-0000-0000-0000-000000000101）
3. **document_repository 双模式 session**（Task 7 集成发现的架构缺口）：CLI 面无 ContextVar 会话 → 206 不可达。对齐 archive/report 仓储双模式族先例（CR1-F1）落地 save/find 双模式（活动会话优先行为不变——API 零影响；CLI/后台经注入 session_factory 独立会话 commit）；组合根 document_repository 注册 impl 字符串→lambda（session_factory 注入装配位）；联动更新 test_arch_document_upload.py impl 形态断言（isinstance 产物断言）
4. **懒 bootstrap 幂等双守卫**：conftest session bootstrap 与 main_cli 懒 bootstrap 共存时 ConflictError 203——对齐 agent_cli _ensure_bootstrapped 先例（模块 flag+注册表探测任一命中即跳过）
5. **tool slug 解析链修正**：get_by_name 匹配中文名非 slug——真实链经 skill_manifest.get_tool_id(slug)→get_tool(tool_id=UUID)（SLUG_TO_TOOL_ID 静态映射单源）；真实 PG 工具表空 → tool list/schema/run 幂等 register_all() 先行（register_all 重复注册 debug 跳过幂等语义）；slug 完整形态 "pestel-analysis"（非 "pestel"）
6. **input_examples 异常族**：故事 AC-6 钦定 EXCEPTION_201 族——落地 ValidationError(201)（值域校验语义）与存量 FrontmatterParseError（结构解析语义）分立，零新增异常合规
7. **skill_manifest.py 零改动勘正**：故事「skill_manifest.py 透传」表述与现状不符（实为 tool_id↔slug 映射表）——透传经 frontmatter.normalize_metadata→ToolMetadata.input_examples 承载，skill_manifest.py 无需改动（文档表述偏差按现实层优先）
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范（architecture.md:2073-2100 钦定目录）
- [x] 现有代码资产盘点完成（agent_cli 19 子命令/formatters 空目录/document_commands 未接线存量/六模块端口行号核验）

### 文件清单 File List

**创建的文件/Created Files（dev-story 实施）:**

src 面（20 文件）：
- `src/entrypoints/main_cli.py` - sisys 进程入口（load_dotenv→懒 bootstrap 幂等→create_cli_app→派发→统一异常出口映射；模块级 main(argv)->int）
- `src/interfaces/cli/main.py` - create_cli_app 工厂（六模块挂载+--version 顶层选项）
- `src/interfaces/cli/_guards.py` - 共享守卫（require_agent_budget/canonical_uuid/parse_agent_uuid）
- `src/interfaces/cli/_params.py` - 共享 Annotated 参数注解（四全局+三 Agent 专用）
- `src/interfaces/cli/controllers/__init__.py` / `base.py` - 控制器包+共享短路执行基建（CommandContext/execute_command）
- `src/interfaces/cli/controllers/{document,tool,agent,planning,checkpoint,archive}_controller.py` - 6 控制器（静态 PORT_NAME 常量）
- `src/interfaces/cli/commands/{tool,agent,planning,checkpoint,archive}_commands.py` - 5 命令组
- `src/interfaces/cli/formatters/{__init__,json_formatter,table_formatter,pretty_formatter}.py` - 三格式化器+分发

测试面（12 文件）：
- `tests/unit/interfaces/cli/test_cli_formatters.py` / `test_cli_framework.py` / `test_tool_commands.py` / `test_agent_plan_commands.py` / `test_checkpoint_archive_commands.py`
- `tests/unit/application/skills/test_frontmatter_input_examples.py`
- `tests/unit/architecture/test_arch_unified_cli.py`
- `tests/contracts/test_port_contract_unified_cli.py`
- `tests/integration/test_integration_unified_cli.py`
- `tests/acceptance/test_acceptance_unified_cli.feature` + `.py`（23 场景终态）

**修改的文件/Modified Files:**
- `pyproject.toml`（[project.scripts] 增 `sisys = "src.entrypoints.main_cli:main"`——仅该段）
- `src/interfaces/cli/__init__.py`（移除勿仿告示）
- `src/interfaces/cli/commands/document_commands.py`（重写：version 族 185 行→upload/parse，Task 3 存量处置）
- `tests/unit/interfaces/cli/test_document_commands.py`（重写覆盖：version 族断言→upload/parse 断言）
- `src/application/skills/frontmatter.py`（input_examples 归一化+1-5 条 ValidationError 201 校验+normalize_metadata 透传）
- `src/application/ports/skill_loader.py`（ToolMetadata 尾部默认值扩展 input_examples: tuple[str, ...] = ()）
- `src/application/skills/*/SKILL.md`（全量 23 文件补 input_examples——每工具 1 条参数 JSON 示例，跑批校验 23/23）
- `src/infrastructure/storage/postgresql/repository/document_repository.py`（save/find 双模式 session——Task 7 集成发现的 CLI 面可达性缺口，archive/report 仓储族先例对齐）
- `src/composition_root.py`（document_repository 注册 impl 字符串→lambda，session_factory 注入装配位）
- `tests/unit/architecture/test_arch_document_upload.py`（document_repository impl 形态断言联动更新）
- `_bmad-output/implementation-artifacts/deferred-work.md`（七条处置注记+新登记 7-1-DF1~DF5+OD-8/OD-9）
- `_bmad-output/implementation-artifacts/sprint-status.yaml`（7-1 状态推进）

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

> 五轮循环文档审查（D1 多视角调研→D2 多视角审查→D3 修订→D4 提交推送→D5 循环）修复记录。R1 = 2026-11-20 第一轮（4 调研 Agent + 3 审查 Agent 并行 + 主会话定谳）。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-1 | typer `@app.callback()` 承载全局参数在尾置形态（AC-2 全部用法示例形态）实测 exit 2——Task 2 绿阶段机制与用法示例直接矛盾 | P0 | AC-3 增「全局参数实现机制冻结」：共享 Annotated 注解逐命令声明（`_params.py` 单一来源）+ 禁 callback 承载；Task 2 红/绿阶段同步（含尾置回归锚断言）；项目结构/File List 补 `_params.py` |
| R1-2 | 存量 `test_document_commands.py`（197 行，version 命令族）与 Task 3 同名新建冲突未处置；version 命令族（§4.3.1 钦定命令）删除无 defer 归宿 | P1 | Task 3 存量处置节扩写（重写移除 version 族+测试同步覆盖重写）；AC-1 零回归面注记排除；新增 7-1-DF5/OD-7 登记 §4.3 超出 12 命令冻结矩阵的全部命令面（含 version/search/delete/status/arbitrate/export/review/timeline/diff/--modifications）；File List 待修改补两文件 |
| R1-3 | AC-5 端口 SSOT 漏 `skill_loader`——tool schema 的 input_examples 运行时数据通路无载体，dev 按自家「禁止新增未登记端口」禁令无法实现 | P1 | AC-5 表 tool schema 行补登记（组合根 :2875）；端口口径 12→13（全出现位 8 处同步）；Task 4 红阶段补通路锚 |
| R1-4 | `<tool-id>` 值语义未钉死（slug vs UUID）+ slug→Tool.id 解析链缺失（execute 硬要求 UUID，人类/LLM 输入必为 slug）；AC-7 守卫若误套 tool-id 即全崩 | P1 | AC-5 参数语义注记（slug 唯一形态+解析链+禁套 canonical_uuid）；AC-7/异常表守卫分工注记同步；Task 4 红阶段补解析链断言 |
| R1-5 | `--dry-run`「打印端口名」机制未定义——若经 resolve() 获取则需 bootstrap，与「不 bootstrap」契约自相矛盾 | P1 | AC-3 增机制冻结：controller 静态 PORT_NAME 类常量为唯一来源，禁 resolve；controllers 职责描述同步 |
| R1-6 | AC-8 性能口径未钉死调用形态——`poetry run` 包装实测 ~300ms（10 轮 P95≈422ms 逼近红线），验收若用包装即假红 | P1 | AC-8/Task 9.1/隔离表冻结：子进程直调 `.venv/bin/sisys` 或 `python -m`，禁 poetry run 包装 |
| R1-7 | 「20 轮采样口径，epics 钦定」失实（epics 无 20 轮；P95 值出处为 prd.md:2553）；NFR-IF-01 编号双源冲突（prd=CLI 延迟 vs epics:336=仪表盘语义） | P1 | AC-8 勘正：P95 值锚 epics+prd.md:2553，20 轮为 Story 自定口径；编号消歧注记（以 prd 为准） |
| R1-8 | 场景计数三口径冲突（~23/~21/Task 0 与 Task 9 编写边界模糊） | P1 | 统一：Task 0 交付 AC-1~AC-7 共 19 场景，Task 9 补 AC-8×2+收尾×2 至最终态 23（三处出现位同步） |
| R1-9 | P7 量化指标「工具调用准确率≥90%」（epics:2618/interface-design:57）既未承载也无 defer（OD-1 只覆盖 P5/P6） | P1 | OD-1 扩为 P5/P6/P7 三指标统一锚 evaluation 专项；AC-6 P7 行注记 |
| R1-10 | AC→Task 追溯矩阵引用不存在的子任务编号（「各组 1.1」「各组 2.x」） | P1 | 改为实际编号形态（各组 X.2 绿阶段） |
| R1-11 | 接口层覆盖率 ≥85% 测量面未定义（epics 原文亦未定义）+ 机器载体缺位（check_coverage_gates.py 无 src/interfaces 档） | P1 | 覆盖率节勘正：测量面=src/interfaces/cli/ 新增文件伞形达标（≥95% 自然满足）；机器载体注记（现状无档位+Task 9 实测后登记扩档建议+Makefile :278-280 禁 --cov=src.\<layer\> 陷阱） |
| R1-12 | 契约测试「bootstrap 后 resolve()」形态与既有零 IO 先例（test_port_contract 族 `_global_registry.get` 直查）相悖——contracts 目录连真实服务会环境依赖超时 | P1 | SDD 端口契约节/Subtask 0.4/测试分类表对齐零 IO 直查先例形态 |
| R1-13 | checkpoint_recovery :76-80 锚点失实（实为 docstring 尾部；teardown 真实锚 :277-307、直调 :1125-1145） | P2 | BDD 约束节/学习经验节行号勘正 |
| R1-14 | pyproject 双 scripts 段并存（[project.scripts]:155-158 + [tool.poetry.scripts]:160-162）无处置指引 | P2 | Task 2 循环 B/File List 注记：仅入 [project.scripts]，poetry 段勿动 |
| R1-15 | OD 表与 DF 台账双轨对应关系不明（OD-2/3↔DF3、OD-4↔DF4、OD-6↔DF2） | P2 | OD 表头增台账对应注记 |
| R1-16 | AC-8「装配」与 --dry-run「不 bootstrap」歧义 | P2 | AC-8 明确「装配=CLI 工厂装配（create_cli_app+子命令挂载），不含组合根 bootstrap」 |
| R1-17 | checkpoint `--id` 归入「plan-id 族」命名与实体语义错位 | P2 | 异常表/AC-7 改「实体 ID 族（--plan-id、checkpoint --id）」（R3-3 进一步收敛——checkpoint `--id` 形态已废除，现行实体族=`--plan-id`+document `--id`，R4-5 内联勘误注） |
| R1-18 | AC-2「四大核心工作流」vs Then 列 5 条命令 | P2 | 改「四大核心工作流（document/agent/plan/checkpoint，共五条命令）」 |
| R1-19 | epics「E2E 测试覆盖率≥80%」（:2636）钦定项无点名归宿 | P2 | OD-5 Gap 补该指标由验收场景承载声明 |
| R1-20 | `main_cli.main([...])` 直调对 typer 无现成 API（typer.Typer 无 .main 方法） | P2 | BDD 约束/Task 2 循环 B 增模块级 `main(argv)->int` 签名契约（agent_cli:2623 同签名先例+standalone_mode 派发注记） |
| R1-21 | `--mock`×`--dry-run` 组合优先级未定义 | P2 | AC-3 增互斥/优先级契约（--dry-run 最外层短路优先） |
| R1-22 | 并发场景「轻量子进程」命令面未钉死（误含 bootstrap 命令则撞连接并发） | P2 | AC-8/Task 9.2 冻结并发面=--help/--dry-run |
| R1-23 | 存量 agent_cli `--format`（:354）与新入口同名参数语义边界无注记 | P2 | Dev Notes 技术栈节补双入口并存期各自语义冻结注记 |
| R1-24 | 「14 个 CLI 形态验收文件」口径不可 grep 复原（文件名不含 cli） | P2 | AC-1 验证项注明口径+grep 锚（`grep -l agent_cli tests/acceptance/*.py`=14） |
| R1-25 | deferred-work :117 RabbitMQ 消费基建注记锚「7-x」与台账最新锚（Epic 8，三条处置注记一致）不一致 | P3 | 留项范围外注记勘正为「首个消费方 Story（台账最新锚 Epic 8）」 |
| R1-26 | 调试日志引「§3.3 命令矩阵」失准（§3.3 实为链路映射规则节；命令矩阵在 §4.2-4.3） | P3 | 调试日志引用勘正 |
| R1-27 | `test_agent_cli.py（4294 行）`硬编码行数易腐 | P3 | AC-1 注明基线（6047e4d4 时点） |
| R1-28 | formatters/__init__.py 在 Task 1 文件清单有、项目结构与 File List 缺 | P3 | 项目结构/File List 补齐（4 文件口径） |
| R1-29 | Dev Agent Record「workflow v6.3.0/template v2.9.0」不可核验（template 无版本头） | P3 | 改为可核验引用形态 |
| R1-30 | 缺省 `--format`=table 无断言锚（AC-3 定义、Task 2/AC-4 无断言） | P3 | Task 2 循环 A 红阶段补「缺省 --format 输出=table 渲染断言」 |
| R1-31 | Subtask 0.6「可仅含 given 前置与调用骨架」会致 pytest-bdd 收集期 ScenarioDefinitionError（偏离运行期 ImportError 红形态声明） | P3 | 收紧为 given/when/then 全步骤骨架齐备 |
| R1-32 | Subtask 4.4 内容资产批量面（23 SKILL.md）无独立提交批次注记；AC-6 验收 tool-id 未与补齐清单联动 | P3 | Subtask 4.4 补两注记 |
| R1-33 | epics:2606 示例命令为二级形态（`sisys upload`）与三级结构钦定差异无注记 | P3 | （本轮以 OD-7 范围声明覆盖命令面差异；epics 示例为缩写形态，以 interface-design §4.2 三级结构为准——Dev Notes 架构约束已锚 interface-design） |
| R2-1 | json_formatter 对 UUID/Decimal/datetime 非原生类型序列化策略未定义（`json.dumps` 直接 TypeError；命令对象字段明文 UUID/Decimal 形态）——主会话预验先行发现，R2-B Agent 独立同报（P1 级） | P1 | AC-4 增序列化契约冻结：`json.dumps(payload, default=str, ensure_ascii=False)`；Task 1 红阶段补 UUID/Decimal 序列化断言。**方案裁定注记：** R2-B 建议 DTO 层 `to_payload()` 预归一（formatter 零特判）——裁定取 `default=str`（最小实现面：12+ 命令对象无需各建 to_payload；table/pretty 侧 f-string 内建支持 UUID/Decimal 转展，formatter 层无需特判；语义等价——UUID→hex/Decimal→十进制串） |
| R2-2 | `--mock` 短路 DTO 的 `parameters` 含归一后类型同样需序列化策略 | P1 | 并入 R2-1 契约（Mock DTO 同走 default=str） |
| R2-3 | AC-8 性能场景「.venv/bin/sisys 直调」的降级判定（缺 script 时）只在隔离表、验证项不可操作 | P2 | AC-8 验证项补降级判定（存在即用/缺失降级 python -m，与隔离表同款） |
| R2-4 | `--session` 透传验证项未区分真实面/mock 面两态（mock 不 bootstrap 时透传断言不可达） | P2 | AC-3 验证项注记两态：真实面透传用例上下文；mock 面缺省生成入 DTO session 字段 |
| R2-5 | DC-5 决策行未同步 --dry-run×--mock 优先级契约（R1-21 新增） | P3 | DC-5 方案列补「两者同给 --dry-run 优先」 |
| R2-6 | 三格式化器空态渲染契约未冻结（json `[]` vs `{"items":[]}`、table 表头 vs 提示行、pretty 文案——三种自由实现致验收断言无锚） | P2 | Task 1 红阶段冻结空态契约：json=空数组 `[]`/table=表头+零数据行/pretty=空态提示语（CR2 内联勘误：table 空态实现形态为**纯空串**——CR1-F8 勘正正文 Task 1 行，空表头无信息量，jq 空输入惯例） |
| R2-7 | File List「7 个测试文件」口径模糊（unit 7 个还是全量 12 个） | P3 | File List 拆分：7 unit（含 application/skills 1 个）+ 架构/契约/集成/验收 5 文件 |
| R2-8 | `--dry-run`×`--mock` 优先级契约（R1-21）无对应验证项 | P2 | AC-3 验证项补优先级断言 |
| R2-9 | AC-6 四验证项分属架构测试/unit/验收场景/跑批四承载面但未区分（场景计数×1 与四验证项的对应关系不明） | P3 | AC-6 验证项逐条标注承载面；仅 tool schema 项入 23 场景计数 |
| R2-10 | Subtask 0.8 执行行「新登记 7-1-DF1~DF4」在 R1 扩登记 DF5 后漏同步——R1 修复自身犯「声称联动位未执行」缺陷类（R2-B 发现，主会话漏网） | P1 | 0.8 改「7-1-DF1~DF5」+ 勘正注记 |
| R2-11 | .env 显式路径的推导值未定义 + Task 7.4 临时 .env 在显式路径语义下无注入机制（改仓库根 .env 污染开发环境）（R2-B 发现） | P2 | AC-7 钉死 `ENV_FILE = Path(__file__).resolve().parents[2] / ".env"` 模块常量；Task 7.4 经 monkeypatch 常量注入临时 .env |
| R2-12 | 契约测试「零 IO 直查+isinstance」的断言对象形态未钉死（直查拿到 PortSpec 元数据非实例）（R2-B 发现） | P3 | Subtask 0.4 补断言对象注记（PortSpec 维度断言+impl 类 Protocol 检查/DummyResolver 替身对齐先例） |
| R2-13 | 测试分类表 document 行未标注重写覆盖语义（R2-B 发现） | P3 | 表格行尾加「（重写覆盖存量 version 族）」 |
| R2-A1 | Task 2 循环 A 尾置断言示例 `... upload --file x --yes` 时序矛盾（循环 A 时刻 upload 未交付）（R2-A 回归核查发现） | P3 | 补时序注：以工厂内任一已挂载子命令验证机制，命令组尾置断言随 Task 3-6 落地 |
| R2-A2 | Task 4 循环 B 重构行「四命令共享 Agent 参数注解 DRY」可误读为 tool 侧新建注解（R2-A 发现，与 R2-B#6 同） | P3 | 改「四命令复用 `_params.py` 共享注解（不另建）」 |
| R2-A3 | Subtask 2.2 摘要「实现 main.py 工厂」未列 _params.py（R2-A 发现） | P3 | 摘要补「main.py + _params.py」 |

> **R2 审查方法注记：** 双 Agent 并行（R2-A 回归核查：git diff 逐项比对 R1 台账+六组合交互面扫描——R1 的 33 项修复与 diff 完全一致、零 P0/P1/P2 新破口；R2-B 传播完备性+深度推演：10+ 关键词面传播一致、新发现 P1×2/P2×2/P3×5）+ 主会话等待期独立预验（R2-1 序列化问题实测先行，与 R2-B#2 独立同报互证）。R2 合计 16 项修复（P1×3 计入 R2-1/2/10、P2×5、P3×8）。

| R3-1 | `checkpoint show --id`→`checkpoint_use_case`(:2496) 端口错位——该端口实为 CreateCheckpointUseCase 纯创建零查询（无 UUID 查询 API），dev 按表实现 show 无方法可调（R3 签名级核验发现——R1 行号核验只证注册存在未证签名匹配的盲区） | P1 | AC-5 表 show 行重设计：`show --plan-id [--checkpoint-no]`→`checkpoint_recovery_use_case`(:2508 预览视图)；主会话独立实证（组合根 :2496-2500 interface=CreateCheckpointUseCase） |
| R3-2 | `checkpoint recover --id [--mode]`→`checkpoint_recovery_use_case`(:2508) 预览/执行面错位——:2508 无 mode 无恢复副作用；真实执行面 `checkpoint_recovery_execute_use_case`(:2536) 参数三缺口（--plan-id/--checkpoint-no/`confirmed_by` 非空强制 242） | P1 | recover 行重设计：`--plan-id --checkpoint-no [--mode] [--confirmed-by]`→:2536；:2508 转任 show/--dry-run 预览面；confirmed_by 缺省取 --session 标识；主会话独立实证（checkpoint_approval.py:56-110 签名+空串 242 守卫） |
| R3-3 | checkpoint `--id` 参数形态错位传播面五处（AC-2 示例/AC-5 表/AC-7 守卫族/异常表/Task 6 红阶段——R4-4 计数勘正：原写四处漏计 Task 6 随动位） | P1 | 五处联动修订（AC-2 示例复合定位+given 前置创建链注记；AC-5 表两行重设计；AC-7 守卫族收敛 --plan-id；异常表实体族改写+confirmed_by 242 承载注记；Task 6 红阶段测试清单同步）+OD-8 偏离登记（钦定 --id 单参形态在端口面不可实现） |
| R3-4 | Task 2「六模块子 app 挂载」断言时序缺口（命令组 Task 3-6 才交付，Task 2 挂载断言红→绿路径断裂） | P2 | Task 2 绿阶段注明工厂内联六模块空骨架组（--help 可达），Task 3-6 逐组替换 |
| R3-5 | load_dotenv 调用位置未钉死（模块级 import 副作用形态会崩坏顺序守卫断言与 monkeypatch 可达性） | P2 | AC-7 钉死 main() 函数体内+bootstrap 前，禁止模块级副作用形态 |
| R3-6 | `sisys --version` 实现机制与 R1-1 callback 禁令冲突（typer 无内建 --version，标准实现恰是 callback） | P2 | AC-3 机制节补豁免边界（顶层 invoke_without_command 形态，无尾置可达性问题）——主会话实测顶层 exit 0 支撑 |
| R3-7 | AC-7 大写 UUID 归一命中场景前置数据面未指明 | P3 | 验证项补前置创建链（checkpoint_use_case 直创+大写 --plan-id 查询） |
| R3-8 | 20 轮 P95 取值方法未钉死（index 18/19 两可） | P3 | Task 9.1 钉死升序第 ceil(0.95×20)=19 个（1-based）+monotonic 差值 |
| R3-9 | 「轻量真实链」名实差未注记（命令逻辑轻≠绕 bootstrap） | P3 | AC-5 验证项补名实注记 |
| R3-10 | TDD 变异步骤对纯测试 Task（0/7/8/9）字面不可执行 | P3 | TDD 约束节补适用性注记（变异限实现 Task；纯测试 Task 以断言判别力自证） |

> **R3 审查方法注记：** 单深度推演 Agent（递减投入：23 场景三轴推演[前置可达/期望唯一/可观测]+Task 0→9 依赖干跑+组合交互面第二层）——三 P1 全部主会话独立实证后落码（组合根 :2496/:2508/:2536 三端口 interface/签名/守卫逐一定谳）；轴 1 快扫表+轴 2/3 核过面见 Agent 报告归档。R3 合计 10 项修复（P1×3+P2×3+P3×4），checkpoint 命令族是本轮最大破口。

| R4-1 | AC-5 show 行「缺省 checkpoint_no 取最新一条」与 :2508 签名（两参 keyword-only 必填）不直配（R4 纯验证发现，移交 R5） | P2 | R5 终审改判**方案 a（两参必填）**：不设合成层——两步合成（list 取最新→:2508）有 TOCTOU 语义模糊+无钦定依据（§4.3.5 为显式定位语义）+无验收牵引；主会话原预案 b 弃用 |
| R4-2 | recover `created_via` CLI 侧取值未注记（缺省 "use_case" 会落错触发源审计标识） | P3 | AC-5 recover 行注记：controller 固定传 `created_via="cli"` |
| R4-3 | `--confirmed-by` 缺省取 --session 的解析时点未钉死（影响 --mock 面 parameters 内容） | P3 | AC-5 recover 行注记：守卫层随参数归一完成，mock 面 parameters 含解析后值 |
| R4-4 | 修复表 R3-3 行 Problem 列「四处」与 Fix 列实际五处联动不符（台账描述与实际修复形态不符先例） | P3 | R3-3 行勘正为五处（含 Task 6 随动位） |
| R4-5 | 修复表 R1-17 行 Fix 列保留「checkpoint --id」旧表述与 R3-3 后正文现状失配 | P3 | R1-17 行尾内联勘误注（历史行不改写惯例） |
| R5-1 | 「12 命令消费 13 端口」口径错误——tool_registry_service 被 tool list/schema 双命令消费，**唯一端口 12 个、命令-端口消费对 13 个**；契约测试按 13 唯一名断言会对不上（R5 独立终审发现——R1 引入 skill_loader 时以消费对计数误作唯一端口数，R1-R4 四轮未察觉） | P2 | 8 处出现位统一改「12 唯一端口（13 命令-端口消费对——tool_registry_service 双命令消费）」；Subtask 0.4 断言清单口径同步 |
| R5-2 | AC-5 show 行采纳 R5 终审方案 a（并入 R4-1 处置） | P3 | show 两参必填 `--plan-id --checkpoint-no` |
| R5-3 | 异常契约表实体 ID 族未显式点名 document parse `--id <doc-id>`（合法 UUID 族参数靠「等」涵盖） | P3 | 异常表显式列名 |

> **R4/R5 审查方法注记：** R4 纯验证 Agent（零修复纪律：R1-R3 台账 59 行 git diff 比对零失实+20+ 契约锚点存续核验+组合交互四疑点实测定谳，5 项发现移交）；R5 独立终审 Agent（不轻信自报：周期闭合/关键修复双向抽验 10 项/独立特权快扫/R4 预案复核[改判 R4-1]/file:line 锚点 10 组零失实/收敛判定六节）。R5 合计清偿 8 项（P2×2 计入 R4-1/R5-1、P3×6）。

### 🏁 审查周期收敛声明（R5 终审产出）

> Story 7-1 文档五轮循环审查周期（R1 调研审查 33 项 / R2 回归传播 16 项 / R3 深度推演 10 项 / R4 纯验证 5 项移交 / R5 独立终审清偿 8 项）共 67 项处置，P0×1 与 P1×17 全部修复入库（d791f5df/c28bce93/58ed8cb2+本轮收敛提交），R4 零提交（纯验证纪律）。终审双向取证：修复台账 59+8 行与文档现状零失实、10 组 file:line 锚点全部精确、周期闭合无游离提交、sprint 状态一致（epic-7 in-progress / 7-1 ready-for-dev）。**零 P0/P1 残留，文档就绪度达 ready-for-dev 交付标准，审查周期收敛。**

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 2026-11-20（Round 1，五轮 C1~C5 循环代码审查周期）
**审查模式:** full（C1 四视角并行调研[契约符合性/越界面/测试质量/运行面实测] → C2 P0 定级方案 → C3 双评审员评审[正确性+破坏性] → C4 提交推送）

#### 需决策 Decision Needed

- [x] ~~CR1-F2 租户常量分裂（cli-default vs UUID101 两 controller 各自定义）~~ 已定谳 OD-10：两域形态差异是端口类型现实；常量单点集中归宿迁移专项；多租户切换 YAGNI defer 7-4
- [x] ~~CR1-F6 Agent 专用参数面（实现全命令 vs story 五命令冻结）~~ 已定谳：story 勘正为全部命令（对齐 interface-design §4.4 原文——dev 实现即钦定形态，story 文档期收窄才是偏差）
- [x] ~~CR1-F7 slug 解析链（实现 SSOT 映射 vs story 冻结 get_tool(tool_name=)）~~ 双评审员改判定谳：SLUG_TO_TOOL_ID 系仓内钦定 SSOT 且 slug≠tool_name 双列实证直查必 miss——**story 原冻结契约才是错的**，勘正为 SSOT 解析链

#### 已修复 Patch

- [x] CR1-F1（P0 红线）：7 处多余 `# noqa` 删除（BLE001×6/S603×1——规则集 E/F/I/N/W 未启用这些规则，纯冗余+违反 CLAUDE.md 禁 noqa 红线；B017 处 dev 已自修精确断言）——生产 2+测试 5 文件
- [x] CR1-F9a：集成测试 3 处裸 `asyncio.new_event_loop().run_until_complete()` 补 loop.close()（:111/:206/:259——资源泄漏；第 4 处 :152 dev 已自修）
- [x] CR1-F9b：framework:394 冗余自我赋值行删除
- [x] CR1-A1：守卫统一性命令级锚补充（checkpoint list --yes 无 budget→201 单测——防未来 base 管线守卫移位）
- [x] CR1-F4b：feature 场景名「轻量真实链四命令」→「三命令」（名实勘正，.feature+.py 绑定串双锁步）
- [x] story 侧：守卫层两类定义冻结（CR1-F5）/参数面勘正（CR1-F6）/slug 解析链勘正（CR1-F7b）/异常表补 202+退出码 130+异常呈现双行注记（CR1-F8）/table 空态措辞勘正（空串形态）/OD-10 登记

#### 已推迟 Defer

- [x] CLI 租户常量单点集中（`_guards.py`/cli_context 模块收敛）→ 7-1-DF1 迁移专项或后续租户治理 Story（OD-10——不迁移已落库数据）
- [x] 多租户 CLI 切换（SISYS_TENANT_ID env）→ 7-4 config 命令组域（YAGNI）

> **R1/C3 评审改判记录（评审否决的修复方向）：** F7a（slug 改直查 get_tool(tool_name=)）被双评审员一致否决——若落码即引入 P0 回归（slug≠tool_name 的工具直查必 miss）；F6 改码部分收缩为空集（base.py:86 守卫实测已全命令统一）。C1 报告两项前提被评审实测推翻（「checkpoint list --yes 静默通过」不成立/「SLUG_TO_TOOL_ID 自创双源」不成立）——评审员否决权与实测定谳的价值实证。

#### 收敛后追加固化 CR6（2026-11-21，用户授权选项 1：skip 面治理）

- [x] CR6-1 大写 UUID 归一场景换 document 域前置：原 checkpoint 前置（创建链 OD-12 压缩强制环节依赖 LLM → 无 Key 环境连带 skip，6.9-R1-DF1 清偿面曾零验收覆盖）→ 换 document 真实 upload（零 LLM）+ 大写 `--id` parse，断言升级 `parse_status=completed`+`document_id` 归一小写（miss 形态合成 FAILED 文档的状态即判别锚——比原「CP-1 in stdout」更强的归一命中证明）；验收 21+2 skip → **22 passed+1 skip**
- [x] CR6-2 验收 given 租户分叉修复（**预存缺陷①**，强断言暴露）：given upload 用 `cli-acceptance` vs CLI 常量 `cli-default` → find miss → 既有「文档解析真实链」场景一直是 miss 形态假绿（弱断言 exit 0 恒真从未暴露）——given 租户对齐 `cli-default`（与集成侧一致，teardown 按 id 删租户无关，既有场景零破坏且从假绿变真实绿）
- [x] CR6-3 OCR 增强 mime 门控修复（**预存生产缺陷②**，强断言暴露）：`_apply_ocr` 缺「仅 PDF」门控（兄弟 `_apply_layout/_apply_table_detection` 均有）——md/txt 短文本页字符数 <50 被 `detect_scanned_pages` 误判扫描页 → 进 OCR recognize 抛 OCRProcessingError → 非 PDF 文档在 OCR 端口注入环境解析恒 FAILED；补 `application/pdf` 门控一行（既有 OCR 测试面全用 PDF，38 passed 零回归）
- [x] Skip 口径归类勘正：checkpoint 族两场景 skip 归「创建链 OD-12 压缩依赖连带」非「AC-2 钦定 LLM 面」（AC-2 节注记）+解耦归宿 deferred 登记
- 验证：四目录全量 **15583 passed + 4 skipped** 零失败（基线 15581+大写转绿+新增 1）+ruff/mypy 全绿

> **CR6 方法论注记：** 弱断言（exit 0 恒真）掩盖「场景从未真正走通」的两层实证——既有解析场景 miss 假绿（租户分叉）+非 PDF 解析恒 FAILED（OCR 门控缺失）均被强断言一次暴露；「换域改造」的断言升级是发现预存缺陷的探针。

#### 代码审查周期收敛声明（R5 终审产出，CR5）

> Story 7-1 代码五轮循环审查周期（R1 四视角+双评审[含 2 项评审改判]/R2 回归核查+判别力[3 项 P3]/R3 深度推演[断言覆盖矩阵 10 契约 7 锚齐+三突变红绿闭环零恒真+全量 15581 passed]/R4 纯验证零发现[20+ 锚点存续]/R5 独立终审六节）收敛。提交链：dev 三批（327247c2/8a43262c/70e49b1f）+审查三批（6ac22a19/67e57dbc/67d36818），周期闭合无游离（6047e4d4..HEAD 十提交全对应轮记录）。处置合计：P0×1（noqa 红线）+P1 级定谳修复 4 项（租户常量 OD-10/File List 补登/agent-id OD-9 对齐/dry-run 守卫层冻结）+P2/P3 清偿 12 项+评审否决 2 项（防 P0 回归）+断言锚新增 2 处（守卫统一性/202×dry-run——均突变或实测验证判别力）。门禁：ruff 全仓+mypy 795 文件零错误+四目录全量 15581 passed+5 skipped 零回归。**零 P0/P1 残留，Status→done，7-1 交付收敛。**（R5 终审 Agent 因 API 配额 429 中断，六节取证由主会话基于 R1-R4 已收集证据完成——降级先例 4-1d/4-6 同款）



---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] 运行 `dev-story` 开始实施（2026-11-20 完成——10 Task 全勾，23 验收场景终态，四目录回归 15576 passed 零失败）
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.4.0
**创建日期/Created:** 2026-11-20
**最后更新/Last Updated:** 2026-11-20
**更新说明/Description:**
- v1.0.0: 创建故事文件（三 Agent 并行调研：架构文档/现有代码/测试与故事风格；前置留项清单七条裁定落档；DC-1~DC-6 架构决策+OD-1~OD-6 偏离预告；12 命令冻结矩阵+全局参数契约+退出码契约）
- v1.1.0: Round 1 五轮循环文档审查修订（4 调研+3 审查 Agent 并行，33 项修复：P0×1 typer callback 尾置矛盾/P1×11/P2×13/P3×8，详见 Docs Review Fixes 表）——核心：全局参数机制冻结（Annotated 共享注解）、端口 SSOT 13 化（补 skill_loader）、tool-id slug 语义+解析链、存量 test_document_commands.py/version 命令族处置+7-1-DF5、dry-run 静态 PORT_NAME 机制、性能口径冻结（禁 poetry run）+出处勘正（prd.md:2553）、场景计数统一（Task 0=19→Task 9 补至 23）、接口层覆盖率测量面落地、契约测试零 IO 对齐、OD-7/DF5 登记
- v1.2.0: Round 2 回归核查+传播完备性修订（双 Agent：R2-A 证实 R1 修复 33 项与 diff 零偏差+六组合交互面零新破口；R2-B 新发现 8 项；主会话预验独立同报序列化缺口；16 项修复：P1×3/P2×5/P3×8）——核心：json_formatter 序列化契约冻结（default=str，UUID/Decimal 降维——首个 JSON 输出面）、三格式化器空态契约冻结、Subtask 0.8 漏 DF5 同步勘正（R1 修复自身联动位未执行缺陷类）、.env ENV_FILE 模块常量+monkeypatch 注入机制、AC-8 降级判定入验证项、--session 两态透传、优先级断言、AC-6 承载面注记、契约测试断言对象形态
- v1.3.0: Round 3 深度推演修订（单 Agent 三轴推演：23 场景前置可达/期望唯一/可观测+Task 0→9 依赖干跑+组合交互面第二层；10 项修复：P1×3/P2×3/P3×4）——核心：checkpoint show/recover 端口消费契约错位修正（show→:2508 预览视图复合定位、recover→:2536 执行面+confirmed_by 非空承载；原 :2496 创建面移出命令消费清单——R1 行号核验未证签名匹配的盲区由签名级核验补上）+OD-8 偏离登记（钦定 --id 单参形态在端口面不可实现）、Task 2 六模块骨架组时序、load_dotenv main() 体内钉死、--version callback 豁免边界、P95 取法钉死、变异步骤适用性注记
- v1.3.1: Round 4 纯验证+Round 5 独立终审收敛（R4 零提交纯验证：台账 59 行零失实+锚点全存续，5 项移交；R5 六节终审：双向抽验 10 项+锚点 10 组零失实+R4-1 改判方案 a+R5-1 端口口径勘正；8 项清偿：P2×2+P3×6）——核心：端口口径勘正（12 唯一端口/13 消费对——tool_registry_service 双命令消费，R1 消费对计数误作唯一端口数的四轮未察盲区）、show 两参必填（R5 改判：TOCTOU+无钦定依据）、created_via="cli"+confirmed_by 解析时点注记、台账两处勘误（R3-3 五处/R1-17 内联注）、审查周期收敛声明入档（67 项处置，零 P0/P1 残留）
- v1.4.0: dev-story 实施完成（10 Task 全勾：Task 0 SDD 契约/Gherkin 23 场景+Task 1-6 六模块 12 命令 TDD+Task 7 集成四场景+Task 8 架构验证+Task 9 收尾；四目录全量回归 15576 passed+9 skipped 零失败；ruff/mypy 全仓通过；CLI 新增文件覆盖率 91-100%；实施期关键决策七项与两处架构落地（document_repository 双模式 session/tool slug 解析链）见 Completion Notes；新登记 OD-9 agent run 位置参数偏离——状态推进 review）
