# Story 7-1: CLI 命令行接口（统一入口与七原则合规）

**Status:** `review`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 企业战略人员（及作为 CLI 母语消费者的 LLM Agent）,
**I want** 通过统一 `sisys` CLI 入口执行命令（文档上传/工具调用/Agent 调用/规划生成/Checkpoint 恢复），所有命令支持 `--format json/table/pretty` 输出格式与 `--yes/--dry-run/--mock` Agent 模式参数,
**So that** 高效操作系统，且 Agent 能以机器可解析格式（JSON）pipe 消费全部内部能力（CLI 是 LLM 的母语，P1 原则）。

### 业务价值

- **Epic 7 首站（P0-1）**：多触点用户界面与 API 集成的第一交付面；FR-UI-01（CLI 接口）+ FR-IF-01（CLI 七原则合规，epics 归 Story 7.1b 无独立条目，验收嵌入本 Story）。
- **收敛入口分散债**：现状三入口（`sisys-agent` 19 子命令 / `sisys-ocr` / `crawler`）无统一 `sisys` 主命令；Epic 6 十连 CLI-only 交付后「agent_cli 19+ 子命令整合面是 7-1 的直接输入」（epic-6-retro-2026-11-09.md:140）；deferred-work L158 D1 治理注记钦定「Epic 7 集中 CLI 时入口在 entrypoints 层内合并即可」。
- **承载 Epic 6 回顾行动项 1**：七条 REST 族/CLI 族留项在 7-1 立项文件逐条落档（成功标准：「Epic 7 首两个 Story 立项文件含该清单且逐条落档」）——见 Dev Notes「锚定义务清单」。
- **触发三项 CLI 入口标准化留项核销**：6.8-R1-DF1（.env 加载）、6.9-R1-DF1（UUID 归一）、5-7 R1-DF6（SIGTERM span 刷盘）。

### 范围边界

| 面向 | 纳入 7-1 | 排除（归宿） |
|------|---------|-------------|
| 入口 | 统一 `sisys` Typer 入口（三级命令结构）+ `sisys-agent` 兼容入口零回归 | REST API 面（7-2）/Gateway（7-3）/仪表盘（7-4） |
| 模块 | document/tool/agent/plan/checkpoint/archive 六核心模块代表命令集（13 命令，见 Task 0 冻结表） | system/config 模块（OD-5，归 7-4/后续）；sisys-agent 其余 12 命令后续整合（deferred 登记） |
| 参数 | `--format json/table/pretty` + `--yes/--dry-run/--mock` | `--cost-budget`/`--session`/`--timeout`/`--format ndjson/csv`（OD-5，归 Agent 成本治理专项） |
| 性能 | in-process 命令执行延迟 P95<500ms + 并发 10（AC-7） | 进程冷启动含 bootstrap 口径（OD-3 观测面声明） |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 统一入口与三级命令结构

**Given** CLI 已安装（`poetry install` 后 `sisys` 命令在 PATH）
**When** 执行 `sisys --help` 及 `sisys <service> --help`（service ∈ document/tool/agent/plan/checkpoint/archive）
**Then** 帮助文本正确显示六服务模块与各模块命令清单（三级结构 `sisys <service> <resource> <action>` 为 §4.2 明文钦定；两级 `sisys <service> <action>` 与四级（`document version list`）为 §4.3 命令清单的事实形态——非 §4.2 规范原文的「退化规则」）
**And** 执行命令（如 `sisys document upload --file docs.zip --business-domain tech --source manual --license internal`——R1-D1：`--source/--license` 为 REQUIRED_METADATA_FIELDS 必供键 Typer 必填）正确解析并执行，输出执行结果和进度反馈（示例省略租户/身份参数——**租户消费型命令**（upload/search/version list/tool run/archive query）统一 `--tenant-id`/`SISYS_TENANT_ID` 双通道必填 fail-loud；**租户可选命令**（tool list——ToolListQuery.tenant_id 为 Optional，缺省全租户视图，传入则过滤）；非租户消费命令（agent×2/plan×3/checkpoint×2——用例签名不收租户）不引入 `--tenant-id`，见 Task 0.1 租户参数栏）

**验证标准/Validation Criteria:**
- [ ] `sisys` console_script 注册（pyproject.toml [project.scripts] + [tool.poetry.scripts] 双段——**断言收窄为 `sisys` 条目双段一致**：现状两段本不对称（crawler 仅 [project.scripts]），全段字典相等断言必红）
- [ ] 六模块全部有命令挂载（P1 字面：覆盖 document/tool/agent/plan/checkpoint/archive 六个服务模块）
- [ ] 13 命令全部可解析执行（Task 0 冻结表为准）
- [ ] 命令命名符合 interface-design.md §4.3 命令清单（偏差处 OD 声明）
- [ ] 真实服务全链集成测试通过（upload 真实落库读回/search 真实检索/tool list 真实元数据/archive query 真实读——Task 3 循环 C 集成场景承载，含 6.4-DF2 核销场景）

### AC-2: 输出格式面（--format json/table/pretty）

**Given** 统一入口任一命令
**When** 传入 `--format json` / `--format table` / `--format pretty`（缺省 pretty）
**Then** 输出按对应格式渲染：json=单行紧凑 JSON（`ensure_ascii=False`）可被 `json.loads` 直接解析；table=动态列宽两遍法表格（`_print_checkpoint_summary_table` 先例形态 agent_cli.py:1495-1518）；pretty=人类可读多行中文（既有 print 形态）
**And** `--format json` 时 stdout 仅含纯 JSON（进度/日志类输出走 stderr，不污染 pipe 消费——**机制钦定 OD-14：json/table 渲染源=controller 返回的 result，禁止经 `_print_*` 人类可读渲染路径**）

**验证标准/Validation Criteria:**
- [ ] 13 命令全部支持 `--format` 三态（epics AC 钦定：「所有命令支持输出格式参数（--format json/table/pretty）」）
- [ ] json 输出 `json.loads(stdout)` 成功且含结构化结果字段（字段面以 Task 0.3 data 白名单冻结表为准）
- [ ] 缺省不传 `--format` 输出与既有形态兼容（pretty——**注记**：「既有形态」基准仅对整合 7 命令有意义；6 个新命令无既有形态，断言形态=「pretty 非 json/table 三态之一」弱断言如实声明）
- [ ] `plan report` 双格式参数并存可解析（`--format json` × `--report-format pdf`——报告内容格式拆分见 OD-13；既有 report-generate `--format markdown|pdf`（agent_cli.py:356-360 choices）在 Typer 面改名 `--report-format`，sisys-agent 兼容入口 `--format` 语义不变）**且输出语义断言**：json 信封 data 含报告产物路径与 report_format 字段（信封包产物——OD-13 拆分的行为语义，非仅「不炸」）

### AC-3: Agent 模式参数面（--yes/--dry-run/--mock）

**Given** 统一入口任一命令
**When** 传入 Agent 模式参数
**Then** `--yes`=非交互确认（对有确认门命令等价既有 `--confirm` 语义，如 checkpoint recover；无门命令幂等接受）；`--dry-run`=**client 语义全局统一**（kubectl `--dry-run=client` 同构——OD-12 定谳）：完整执行输入解析+守卫校验（含校验失败路径真实报错），显示将执行的动作清单，**不 resolve 用例零副作用**，exit 0；`--mock`=不执行真实副作用，返回含 `"mock": true` 标记与命令名/参数回显的结构化模拟输出，exit 0
**And** 三参数对 13 命令全部可用（epics AC 钦定：「所有命令支持 Agent 模式参数（--yes / --dry-run / --mock）」）；**参数注入机制=共享 `Annotated[typer.Option]` 类型别名逐命令签名注入**（命令尾随位置生效——app 级 callback 选项只能出现在子命令之前，与 interface-design §4.3 示例的尾随位置冲突，typer 0.24 venv 实证 callback 级 `--format` 尾随传参 exit 2）

**验证标准/Validation Criteria:**
- [ ] `--dry-run` 下无任何端口副作用（零 resolve——无存储读写/无事件发布；Subtask 2.5 断言全局成立无豁免）
- [ ] `--mock` 输出可被 json.loads 解析且 `mock` 字段为 true
- [ ] `--yes` 与既有 `--confirm` 语义等价（等价性断言跨入口验证：**Typer 面仅暴露 `--yes`**——`--confirm` 为兼容入口 argparse 专属）
- [ ] **短路层结构钦定（OD-12×OD-14 联动）**：dry-run 分叉在 controller 内部（守卫后、bootstrap 前）——controller 加 `dry_run: bool = False` 参数；守卫失败照常 `[code] message` stderr + exit 1（dry-run 不豁免守卫报错，「exit 0」仅守卫通过的短路成功路径）；Typer dispatch 矩阵：`--mock`→信封生成器（先过守卫，非法参数 242 非 exit 0）/`--dry-run`→controller(dry_run=True)+动作清单渲染/缺省→pretty 直调薄壳/`--format json|table`→controller result+formatter；**三参数并存优先级 `--dry-run` > `--mock` > `--yes`**（高优先级生效，冻结表注明）
- [ ] checkpoint recover 的 `--dry-run` 走全局 client 短路层（不触达评估用例）；裸跑（无任何 flag）保留既有缺省评估模式（agent_cli.py:2093 resolve，三零=不落记录/不发事件/不应用修正）——OD-12 双态定谳；recover 双分支 controller 形态按 confirm 位分叉（评估态/执行态各自 bootstrap+asyncio.run——:2276-2334 实态），--dry-run 在守卫后短路不触达任何分支；**dry-run 动作清单三钦定**：①清单分支措辞随 `--yes` 位切换（无 `--yes` 列评估态动作[输出影响评估]/带 `--yes` 列执行态动作[应用修正+落恢复记录]）；②`--mode` 值域校验**前移至守卫段**（现状在 confirm 分支内 :2303-2306 `RecoveryMode(mode_raw)`——dry-run 短路会跳过它致非法 mode exit 0，前移保「守卫全执行」语义）；③dry-run 输出遵循 `--format`（json=data.actions 数组/pretty=动作清单文本）
- [ ] 读命令（list/search/query/trace-tree）的 `--dry-run` 退化为守卫校验+动作回显（统一 Agent 契约面，冻结表注明）；**plan report 是产物写入型命令**（report_generation_service 双写：L0 文件存储 + L2 PG 报告库）——动作清单含「将生成 markdown|pdf 报告并写 L0/L2」非空回显
- [ ] recover 命令 help 三态文案冻结（Typer 面）：缺省=评估模式（输出影响评估，详）/`--yes`=确认执行/`--dry-run`=全局快速回显（零服务调用）——**禁复用兼容入口「dry-run 影响评估」措辞**（argparse 侧 help 的「dry-run」字样指评估模式，同词异义为已接受形态，两入口文案各自冻结）
- [ ] 参数语义在 Task 0 规范冻结表逐命令定义（精确语义见「SDD 规范定义」节）

### AC-4: CLI 七原则合规（FR-IF-01）

**Given** sisys CLI 已安装并配置完成
**When** 验证 CLI 接口合规性
**Then** 满足以下验收标准：
- **P1**（CLI 是 LLM 母语）：六服务模块 100% 有统一入口 CLI 命令（AC-1 断言承载）+ `--format json` 机器可消费（AC-2 承载）
- **P4**（MCP 退居生态层）：MVP 阶段 MCP 相关代码量 = 0——无 `src/**/mcp/` 目录、无 mcp 依赖（grep 断言承载）
- **P5**（Less scaffolding）：SkillSelector 保持「ACTIVE 过滤 + description 触发」现实形态零改动断言（工具选择准确率≥85% 评测锚 Story 5-9 AC-8 既有承载；epics「SkillSelector 推荐 Top-3 命中率」为已废弃旧文案——Story 5-2 偏离声明 D-1 在案，`src/application/skills/registry/selector.py` 头注自证）
- **P7**（input_examples 驱动）：input_examples 覆盖断言——**23/23 全量各 ≥1**（载体=各 SKILL.md `## 8. input_examples` 章节，现状 23/23 全具备各恰 1 条 JSON 示例；ToolMetadata 元数据**无此字段**——src/ 零命中，断言只可锚 SKILL.md 章节，不可写成元数据字段断言；「复杂工具」子集判定标准不存在，全量断言更强更简单；工具调用准确率≥90% 评测同锚 Story 5-9）

**验证标准/Validation Criteria:**
- [ ] P1：六模块命令注册完整性测试通过
- [ ] P4：架构测试 grep 断言零 mcp 目录/依赖
- [ ] P5：SkillSelector 源码形态不变断言（零排序零打分零 Top-K）
- [ ] P7：input_examples 存在性清单断言（23/23 SKILL.md `## 8.` 章节各 ≥1）

### AC-5: 向后兼容（sisys-agent 兼容入口零回归）

**Given** 既有 `sisys-agent` 入口（19 子命令）与其 202 个单测 + 12 个架构测试文件（16 个测试函数字面引用 agent_cli，其中 test_arch_* 4 文件 8 函数）锁定的源码形态
**When** 执行整合改造（7 命令 controller 抽取、UUID 守卫归一升级）
**Then** `sisys-agent` 19 子命令行为零回归（`tests/unit/interfaces/cli/test_agent_cli.py` 202 测试全绿；既有验收测试零修改通过）
**And** UUID 守卫归一化增强：`--plan-id` 命令族对非 canonical UUID 输入（大写/无连字符）从「静默落空态 exit 0」升级为「归一化后正常命中」（6.9-R1-DF1 定谳，行为修复非回归——验收场景显式覆盖两种形态）

**验证标准/Validation Criteria:**
- [ ] `test_agent_cli.py` 全部通过（含既有 argparse 解析契约）
- [ ] 12 个架构测试文件（字面引用 agent_cli 的 16 个测试函数）通过或经 OD 声明的锚点同步
- [ ] 大写/无连字符 plan_id 输入 → 归一命中（新验收场景）
- [ ] 既有命令输出格式（人类可读中文）不变

### AC-6: CLI 入口标准化（三项留项核销）

**Given** 7-1 前的 CLI 入口形态（`python -m src.entrypoints.agent_cli` 时 .env 不加载 → 组合根装配链 201/InvalidPasswordError；SIGTERM 时缓冲 span 丢失）
**When** 统一入口与兼容入口启动
**Then** ①入口显式 `load_dotenv`（显式仓库根路径探测，`override=False` 不覆盖既有 env——TEST 环境变量优先不受影响；**测试形态守卫：`SISYS_USE_TEST_PORTS=1` 时跳过 load_dotenv**——.env 被 git 追踪且进程内注入会泄漏非端口键污染同 worker 后续场景），shell 无 POSTGRES_*/EMBEDDING_* 变量时 CLI 裸跑可完成 bootstrap 并正常执行（6.8-R1-DF1 核销）；②SIGTERM/SIGINT 信号 handler 注册：仅 flush Phoenix span（若 tracer 激活）+ 关闭已实例化连接池（`peek_singleton` 探测，不 resolve 新实例，不触发惰性实例化——agent_cli.py:747-748 禁全量 shutdown 注记约束、peek_singleton 调用 :766），优雅退出（5-7 R1-DF6 核销）；③canonical UUID 归一见 AC-5（6.9-R1-DF1 核销）

**验证标准/Validation Criteria:**
- [ ] 无环境变量 shell 中 `python -m src.entrypoints.cli_main <cmd>` 与 `sisys-agent <cmd>` 正常执行（不再 201/InvalidPasswordError；cli_main.py 需具备 `if __name__ == "__main__"` 守卫——subprocess 冒烟形态）
- [ ] load_dotenv 语义单测：tmp_path 写 .env + monkeypatch 指定路径 → 断言目标键注入 os.environ、override=False 下已设键不被覆盖（删 load_dotenv 调用即红——纯语义红锚；**in-process 红锚不可达定谳**：conftest session autouse `_bootstrap_once`（tests/conftest.py:31）已填充 registry，`_ensure_bootstrapped` 检查即短路、`_clear_resolver_caches` 不清 registry，「.env 失效复现」在 pytest 进程内结构性不可复现——裸跑复现归 subprocess 冒烟/e2e 面）
- [ ] SIGTERM 信号下发时进程优雅退出且已激活 span 刷盘
- [ ] `SISYS_USE_TEST_PORTS=1` 测试形态不受 load_dotenv 影响（override=False 语义断言 + 跳过守卫断言）
- [ ] deferred-work.md 三条台账划线（RESOLVED 前置 + 原描述保留形态）

### AC-7: 性能与并发

**Given** 统一入口命令已实现
**When** 对六模块代表命令做 in-process 计时采样（20 轮、`sorted(durations)[ceil(0.95*n)-1]` P95 数学口径、`_WARMUP_ROUNDS=2`——6-11 S11/S12 先例口径；**每轮采样含双清（池重建成本入窗=单进程 CLI 真实语义，OD-3 附注）**）与 10 并发执行
**Then** 命令执行延迟 P95 < 500ms（epics 钦定口径；计时窗口=bootstrap 完成后的命令执行段，与 6-11「编程面直调免 bootstrap 开销混入计时窗口」先例一致——口径差声明见 OD-3）
**And** 并发执行 10 个 CLI 命令全部正确完成——**定谳=10 独立子进程**（`asyncio.create_subprocess_exec` 并发拉起，业界 CLI 并发验证惯例 xargs -P 同构，OD-15）；**禁止 in-process main() 并发**（`_run_*_cli` 内部 `asyncio.run(...)` 在运行中 event loop 内再调必抛 RuntimeError；线程池形态撞 SINGLETON manager 绑定旧 loop 的跨循环族——本 Story 隔离约束表自证）

**验证标准/Validation Criteria:**
- [ ] 六模块代表命令 P95 采样达标（read 侧命令为主：tool list/document search/checkpoint list/archive query/trace-tree/agent instantiate——trace-tree 需 seeded plan_id 数据预置（进程内直写存储先例 white_label_report.py:799 `_archive_steps` 形态）；**instantiate 采真执行形态**（真服务测试环境+TestTenant 租户自清理），禁 dry-run 形态采样（零 resolve=计时空洞只测解析面）
- [ ] 并发 10 子进程命令零失败零交叉污染（UUID 前缀隔离；**并发命令集钦定=无 LLM 依赖混合面**（写入型 5=document upload ×3 + agent instantiate ×2；读型 5=tool list/document search/checkpoint list/archive query/document version list——**禁含 plan generate/tool run 等 LLM 依赖命令**：子进程无法接收进程内 AsyncMock 替身（既有验收 Fake LLM 唯一豁免形态），真 LLM 子进程=Key 依赖+非确定性+费用，「零失败」结构性不可达；**seeded 数据经 argv 传子进程**（--plan-id/--tenant-id 等参数直传 seeded UUID——SISYS_TENANT_ID env 通道同刻可用）；每进程 bootstrap ~3.9s 属正确性测试成本（并发拉起 wall≈4-8s），与 P95 计时分立——OD-15/OD-3 附注）
- [ ] 性能场景挂 `xdist_group("blm-planning-perf")` 同组串行（挂组依据按场景注明：P95 场景因含 instantiate 真执行（写入面）挂组成立——非「read 侧」整体依据；并发场景含写入成员同理；6-11 OD-13 约束）

### AC-8: 收尾完成清单（开发结束验收）

**Given** Story 全部实现 Task 完成
**When** 运行收尾验收场景
**Then** `src` 与 `tests/unit`、`tests/integration`、`tests/contracts`、`tests/acceptance`、`tests/e2e` 完成清单逐项 `Path.exists()` 确认（6-11 S14 先例形态）
**And** `ruff check src/ tests/` + `mypy src/` + 四目录全量回归通过（`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`——显式四目录，裸 `tests/` 会挂起）

**验证标准/Validation Criteria:**
- [x] 完成清单场景全绿
- [x] 全量回归零失败（预存抖动族甄别归位惯例——pdf_report 采样场景独立复跑绿）
- [x] 红线三查零新增（grep ValueError/HTTPException/内置 Exception 三查——见测试要求门禁节）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [x] **不适用声明**：本 Story 是接口层适配面，零领域事件新增（命令执行触发的事件由被调用用例既有发布，如 checkpoint 恢复的 CheckpointRecovered——CLI 层不定义不发布事件）

#### 数据模型 (Data Models)
- [x] **不适用声明**：零实体/值对象新增。CLI 层新增的均为**输出视图结构**（formatter 渲染用的 dict/dataclass 信封），定义在 `src/interfaces/cli/formatters/`，非领域模型。统一输出信封（json 形态）契约在 Task 0 冻结：`{"ok": bool, "command": str, "data": {...}, "mock": false}` 基本骨架（--mock 时 `"mock": true` + `"echo": {参数回显}`）；**data 载荷白名单原则钦定**：data 装 **CLI 视图 dict 最小字段**（REST 面 DTO 白名单同构——如 upload 的 document_id/filename/status 摘要而非 Document 实体全字段序列化），逐命令白名单随 Task 0.3 冻结表落档，单测/e2e/验收三方断言同源该表防漂移

#### 统一端口定义注册与管理 (Port Contract)
- [x] **零新增端口声明**：本 Story 全部命令消费组合根既有注册端口（接口层适配器角色，R4；端口复用即 R1/R2 的组合注入）。消费端口清单（13 命令 → 既有注册名）：

| 命令 | resolve 端口（组合根既有注册名） | 锚点（REST 面同源消费先例） |
|------|------|------|
| document upload | `document_upload_service` | src/interfaces/api/document_upload.py:134；**参数映射注记**：`business_domain` 是 `upload()` 的 metadata dict 内键非顶层参数（upload 签名：filename/mime_type/file_size_bytes/tenant_id/uploaded_by/file_path/document_type/metadata——REST 形态全关键字传参，以 document_upload.py:193-200 为契约源）；CLI 面必填 `--tenant-id`/`--uploaded-by`（Task 0.1 租户参数栏） |
| document search | `hybrid_search_service` | 6-1 消费先例（组合根 SCOPED 注册，search 签名含 collection/query_text/limit/tenant_id/filter_payload/weights——以组合根与 REST/用例源码为契约源，勿凭本表签名实施）；CLI 面需 `--collection`（显式参数或配置派生默认名，真实消费方先例 blm_planning_service.py:777 构造期租户隔离装配） |
| document version list | `document_version_service` | src/interfaces/cli/commands/document_commands.py:22（resolve 接线属实但为**未挂载死代码**——无生产 import；「未接线存量（勿仿）」注记实在 src/interfaces/cli/__init__.py:5 非该文件头） |
| tool list | `tool_execution_service`（`list_tools_metadata(ToolListQuery)`） | src/application/ports/tool_execution_service.py:77 + services/tool_execution_service.py:177（Query Object：tenant_id/category/status/offset/limit）；**能力级对账**：`tool_version_service` 全方法按单 tool_id 收窄无「列工具」能力，tools.py:144 是 `POST /{tool_id}/versions` 端点——端口对账=方法签名能力核对，非注册名核对 |
| tool run | `tool_execution_service` | 5-3 激活链在位（agent_workflow_service 注册 lambda 内同 resolve——组合根 grep 定位） |
| agent instantiate | `agent_instantiation_use_case` | agent_cli.py:773 def/:775 resolve 同名消费（**唯一例外**：直调 `bootstrap()` :2355 不走 `_ensure_bootstrapped` 幂等守卫——Typer 新前端走幂等守卫形态，兼容入口现状保留零回归） |
| agent run-task | `agent_workflow_use_case` | agent_cli.py:852 def/:854 resolve 同名消费 |
| plan generate | `blm_planning_use_case` | agent_cli.py 同名消费（执行函数实名 `_run_blm_plan_cli` :966 + 异步内核 `_run_blm_planning` :922——不存在 `_run_plan_generate_cli`，冻结表按实名登记） |
| plan report | `report_generation_use_case` / `pdf_report_generation_use_case` | agent_cli.py:1078 def/:1096 dispatch（report_format 分发——**Typer 面参数名 `--report-format`**，OD-13） |
| plan trace-tree | `traceability_tree_use_case` | 组合根 :2059 注册 |
| checkpoint list | `checkpoint_list_use_case` | 组合根 :2524 注册 |
| checkpoint recover | `checkpoint_recovery_use_case`（裸跑缺省评估模式 resolve）/ `checkpoint_recovery_execute_use_case`（`--confirm` 执行） | agent_cli.py:2093（评估 resolve——**全局 `--dry-run` 短路不触达此用例**，OD-12）/:2105（执行） |
| archive query | `strategic_archive_service` | src/interfaces/api/strategic_archive.py:179 |

- [x] **禁令确认**：禁止在 CLI 服务文件中本地定义 Protocol/Port 抽象（模板约束）；禁止 CLI import `src.infrastructure`（架构测试 test_cli_entrypoint_imports_application_only 先例——tests/unit/architecture/test_arch_agent_isolation.py:180-197）
- [x] 契约测试：`tests/contracts/test_port_contract_*.py` 零新增零改动（零新增端口）；既有 1568 contracts 全绿为回归门禁（2026-11-13 HEAD 实测收集数）

#### 端口契约清单执行约束（强制）
- [x] 本 Story 端口清单零增长（纯消费方）；上表是**消费对账清单**非新增清单
- [x] 实施中若发现需要「新端口」——停：说明需要新端口的场景并回到 Task 0 重新评估（大概率是端口选型错，应复用既有）

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 预计**零新增领域异常**——CLI 输入校验守卫复用既有异常（agent_cli 五步定式先例）：
> - UUID 守卫失败 → `ValidationError`（EXCEPTION_201，`_parse_agent_uuid` 先例 agent_cli.py:152-176）
> - plan_id/实体 ID 守卫失败 → `EntityValidationError`（EXCEPTION_242，agent_cli.py:1451-1460 先例）
> - 枚举值域失败 → 对应子域异常（如 `AgentRoleNotSupportedError` 441 先例）
> - 命令执行期领域错误 → 透传既有异常体系（CLI 层 catch `DomainError` → stderr `[code] message` + exit 1 双层定式）

- [x] 归属模块与基类：零新增（复用上表既有异常）
- [x] 唯一编码分配：零新增（无编码分配需求）
- [x] 构造器参数设计：不适用（零新增）
- [x] 消息安全性审查：CLI 错误输出沿 `[EXCEPTION_code] message` 单行 stderr 定式（不泄露内部细节）
- [x] 编码注册/导出完整性/测试覆盖：零改动——`tests/unit/domain/exceptions/` 既有 8 项全绿即门禁
- [x] BDD 验收场景：异常路径纳入验收（Edge Cases：UUID 非法 242/角色非法 441/文件不存在/守卫先于 bootstrap）
- [x] **若**实施中确需新增异常（预期外）：走完整 4 项 checklist（定义文件/`_code_ranges.py` 子域映射/`__init__.py` 暴露/子域码段校验）+ Story 异常契约文档小节补写

#### API 契约 (API Contract)
- [x] **不适用声明（REST 面）**：本 Story 零 REST 端点（`docs/api/openapi.yaml` 零 diff——CLI 非契约测试守护对象）
- [x] **CLI 契约载体**：命令面清单（13 命令 + 参数 + 三态格式 + 三 Agent 参数语义）以 **Task 0 实施计划与规范冻结表**为唯一事实源（6-11「实施计划与规范冻结」先例形态）；命令面漂移由架构测试 `test_arch_cli_unified_entry.py` 帮助文本漂移锁守护（agent_cli 帮助文本漂移锁同款先例）

#### 六边形架构约束（必须遵守）
> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖（本 Story 零触碰） |
| application | `src/application/` | 用例编排（本 Story 零改动——纯消费） |
| interfaces | `src/interfaces/` | CLI 命令面/格式化器（**本 Story 主战场**，Typer 属于本层可用依赖） |
| infrastructure | `src/infrastructure/` | 技术实现（本 Story 零改动） |
| entrypoints | `src/entrypoints/` | 进程入口组装层（D1 方案 A——统一入口 main 落位处） |

**本 Story 分层落位（R4 接口层适配 + D1 方案 A + OD-16 层位钦定）**
- **新命令**（document/tool/archive 6 命令）命令定义/参数解析 → `src/interfaces/cli/commands/`（照 document_commands 先例 import domain 层 Resolver——interfaces 合法面）
- **整合命令**（agent/plan/checkpoint 7 命令）Typer 命令层 → `src/entrypoints/cli_commands.py`（**OD-16 层位钦定**：依赖 agent_cli 的 controller/守卫/`_print_*`——entrypoints 层内互引合法；interfaces 侧禁 import agent_cli（`agent_cli → composition_root → infrastructure` 传导链重触发 import-linter interfaces-no-infrastructure 契约——.importlinter:74 注记自证该链历史清零，禁回潮）
- 格式化器/输出信封 → `src/interfaces/cli/formatters/`（entrypoints 侧整合命令消费 formatter 属 entrypoints→interfaces 合法方向）
- 进程入口/组装 → `src/entrypoints/cli_main.py`（`sisys` console_script 指向此；装配=import interfaces/cli/main.py 的 app + cli_commands.py 三组子 app 程序化 add_typer 注册）——「CLI main/uvicorn app 工厂，经组合根装配」CLAUDE.md 钦定
- bootstrap/resolve/连接池关闭 → entrypoints 侧直接 import 复用 agent_cli 既有函数（`_ensure_bootstrapped`/`_close_connection_pools`——**钦定 import 复用，非「公共化」**：公共化目标模块无论落哪层均触发同传导链；禁复制粘贴重复实现）

**领域层零依赖原则**
- 领域层（`src/domain/`）仅使用 Python 标准库；本 Story 零触碰 domain（若发现需要动 domain → 范围外，停下报告）
- interfaces 层禁 import infrastructure（`.importlinter` + 架构测试双重守护——Typer/click/rich 是 CLI 框架依赖不是 infrastructure）

**依赖方向矩阵**（同模板；本 Story 新增代码全部在 interfaces/entrypoints 两层，方向合规面窄）

#### 验收标准 Gherkin (Acceptance Tests)
- [x] 功能测试文件：`tests/acceptance/test_acceptance_cli_command_interface.feature`
- [x] 步骤实现文件：`tests/acceptance/test_acceptance_cli_command_interface.py`
- [ ] 业务方评审通过
- [x] 所有场景覆盖（Happy Path + Edge Cases）——**R6 强制**：严格遵循 `tests/acceptance/test_acceptance_postgresql_relational_layer.feature/.py` 模板风格（AC 横幅注释分组 / `# language: zh-CN` / `@scenario` 双行字面量绑定 / 真实服务零 mock / `pytest.skip` 动态跳过 / S 编号禁泄入 Gherkin 场景名与绑定函数名 / 模块级零本 Story 新词族 import / xdist_group 串行约束）；**三件套[module event_loop + `_run_async` + context dict]不在该 R6 模板**（其为旧代 fixture 形态）——三件套先例锚新一代文件 `test_acceptance_white_label_report.py:154/:168/:192`

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径**——每个资源命令的 Gherkin 场景至少覆盖：输入非法（UUID 242/角色 441）、文件不存在（文件类命令）、dry-run 零副作用、mock 输出标记；响应体验证 `[EXCEPTION_code]` stderr + exit code 独立步骤绑定（6-11 教训 #7：exit code 断言不与 stderr 捆绑）
- CLI 调用通道沿用 in-process 直调先例：`agent_cli.main(argv)` 形态扩展为统一入口 main（`_run_cli` helper + SystemExit 捕获 + `_clear_session_ctx()`/`_clear_resolver_caches()` 双清 + capsys——**真实代码先例 tests/acceptance/test_acceptance_consultant_view.py:461-480 `_run_cli_consultant_view`**；双清函数为各验收文件内**私有定义**形态（无共享 conftest 可 import，本 Story 验收文件自带定义，复刻 white_label_report.py :154/:168/:192 形态）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕（命令面冻结表 + 参数语义冻结表 + formatter 契约 + 输出信封契约）
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证——红锚符号表逐场景条件化：CLI 直调无预置场景 → argparse/typer exit 2 → SystemExit 捕获断言；含新模块命令 → 命令未注册形态；6-11 教训 #12）
- [ ] 规范文档通过人工评审或自动化校验
- [ ] **链路接线断言清单**已定义（Epic 4 回顾行动项 7.1-1）：①`sisys` console_script 装配可达（pyproject 双段 + import 链）②13 命令 resolve 目标端口全部组合根在册（消费对账表逐条 grep 验证）③统一入口 bootstrap 接线（load_dotenv → bootstrap → 命令执行 → 连接池关闭全链）④`sisys-agent` 兼容入口同链复用——「已实现未接线」组件（如有）在 deferred-work.md 登记并注明接线条件

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
| **TDD 单元测试** | 统一入口 | 入口装配/六模块挂载/三级解析 | `tests/unit/interfaces/cli/test_cli_unified_entry.py` | Task 1 |
| **TDD 单元测试** | formatters | json/table/pretty 三态渲染/信封契约/stderr 分流 | `tests/unit/interfaces/cli/test_cli_formatters.py` | Task 1 |
| **TDD 单元测试** | Agent 参数面 | --yes/--dry-run/--mock 语义/零副作用断言 | `tests/unit/interfaces/cli/test_cli_agent_params.py` | Task 2 |
| **TDD 单元测试** | 整合命令 | 7 命令 controller 抽取/UUID 归一守卫 | `tests/unit/interfaces/cli/test_agent_cli.py`（扩展） | Task 2 |
| **TDD 单元测试** | document 命令 | upload/search/version list 参数契约/守卫 | `tests/unit/interfaces/cli/test_document_commands.py`（扩展重构） | Task 3 |
| **TDD 单元测试** | tool/archive 命令 | tool list/run、archive query 参数契约/守卫 | `tests/unit/interfaces/cli/test_cli_tool_commands.py` + `test_cli_archive_commands.py` | Task 3 |
| **TDD 单元测试** | 入口标准化 | load_dotenv override 语义/SIGTERM handler | `tests/unit/entrypoints/test_cli_entry_standardization.py` | Task 4 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收（AC-1~AC-8 分组） | `test_acceptance_cli_command_interface.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现（三件套/真实服务/双清） | `test_acceptance_cli_command_interface.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单最终确认 | 同上两文件 | Task 7 |
| **TDD 契约测试** | 端口契约 | 零新增——既有 contracts 全绿回归门禁 | `tests/contracts/`（零改动） | 全程 |
| **TDD 领域异常测试** | 异常体系 | 零新增——既有 8 项全绿回归门禁 | `tests/unit/domain/exceptions/`（零改动） | 全程 |
| **SDD 架构验证** | 六边形/七原则 | Typer 形态/六模块覆盖/import 方向/P4 MCP=0/P5 SkillSelector 不变/帮助文本漂移锁 | `tests/unit/architecture/test_arch_cli_unified_entry.py` | Task 6 |
| **集成测试** | 真实服务全链 | upload/search/tool list/archive query 真实落库读回 + 6.4-DF2 核销场景（无 session 上下文 CLI 归档消费 + 组合根接线守卫断言） | `tests/integration/test_integration_cli_unified_entry.py` | Task 3 |
| **E2E 测试** | 子进程冒烟 | `sisys --help`/六模块 --help/P1 覆盖/sisys-agent 兼容/安装态命令解析 | `tests/e2e/test_cli_e2e.py`（目录首个**测试**文件——tests/e2e/ 已有 __init__.py） | Task 5 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **接口层覆盖率 ≥85%**（`pytest --cov=src/interfaces` 显式附加）- **P1 阻断门禁**（epics 钦定接口层≥85%；注：`scripts/check_coverage_gates.py` 门禁表现状只有 domain 90/application 85/infrastructure 75/整体 80 四条**无 src/interfaces 条目**——Task 7 收尾时补门禁脚本条目固化，非仅一次性命令）
- [ ] **E2E 覆盖率**——声明式收敛口径：**13/13 命令 e2e 冒烟全覆盖**（epics「E2E≥80%」无分母，按命令清单全覆盖=100% 达成；CI 流水线现状无 tests/e2e 执行位——e2e 门禁仅本地成立，CI 增位归 deferred 登记）
- [ ] **关键路径覆盖率 100%**（所有分支覆盖——13 命令 × 三格式 × 三 Agent 参数的矩阵主干路径）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/ tests/`，行宽 128，规则 E/F/I/N/W）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`，禁 `--no-verify`）
- [ ] **红线三查零新增**：`grep -rn "raise ValueError" src/` + `grep -rn "HTTPException" src/interfaces/`（手动 raise 形态）+ `grep -rn "(Exception)" src/`（继承内置 Exception）——三条自查零输出（预存量甄别在案者除外）
- [ ] **注释规范**：Google 风格全中文（文件头/类/函数/方法——`~/.claude/projects/-home-agimtech-sisys/memory/sisys_code_comment_style.md`）
- [ ] **提交信息禁 AI 署名**（无 Co-Authored-By: Claude / anthropic.com 等）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **CLI 直调三清** | 每次 `main(argv)` 直调前 `_clear_session_ctx()` + 调用前后 `_clear_resolver_caches()`（SINGLETON 缓存绑定旧 loop → InterfaceError——驱逐后 resolve 惰性重建） | 跨场景「Event loop is closed」/ InterfaceError |
| **禁二次 bootstrap** | 同进程复用 `_ensure_bootstrapped()` 幂等守卫（lambda 工厂 spec 不幂等 → ConflictError，DC-12③）；**例外注记**：既有 instantiate 直调 `bootstrap()`（agent_cli.py:2355）——测试直调 sisys-agent 侧 instantiate 场景沿用 conftest session 级 registry 已填充形态规避（Typer 新前端走幂等守卫） | ConflictError 假红 |
| **模块级零新词族 import** | 本 Story 新增 src 符号全部延迟到步骤函数内 import（收集期 ImportError 全文件 ERROR——6-9 教训） | 全文件 ERROR |
| **xdist_group 串行** | 提交型写入测试挂 `xdist_group("blm-planning-perf")` 同组（漏挂 → 与 6-10 S3 skip 门/6-7 归档面并行假红） | 并行假红 |
| **子进程 e2e 隔离** | e2e 子进程用独立 env（TEST_PORTS=1 + TestTenant 前缀），不依赖调用方环境残留 | 环境串扰 |
| **资源唯一性** | 测试数据 UUID 前缀隔离（TestTenant 形态）；性能采样数据自建自清 | ID 冲突 |
| **BDD async 配合** | 步骤函数不使用 `@pytest.mark.asyncio`，用 `event_loop.run_until_complete()` | context 数据丢失 |
| **exit code 独立断言** | exit code 断言独立 Then 步骤，不与 stdout/stderr 断言捆绑 | 断言耦合漏检 |
| **共享库读回断言** | 共享 collection/bucket 的存在性断言一律定向过滤（Epic 6 回顾行动项 4——scroll limit 截断假红族） | 假红 |
| **pytest-asyncio** | 删除 scope=module 的 event_loop fixture；自建 loop 与 auto mode 冲突形态规避（6-11 教训 #8） | RuntimeError 双循环 |

**禁止行为：**
- ❌ 验收/集成测试 mock（`mock` 仅限单元测试——三层策略红线）
- ❌ 集成测试手动 `delete`/`truncate`（transaction rollback / 自清理链）
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`
- ❌ asyncio.Lock 使用实例变量（如引入必须是类变量）
- ❌ `@pytest.mark.skip` 写死跳过（动态 `pytest.skip()`）

**验证要求：**
- [ ] 四目录全量回归通过（`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`——显式四目录，裸 `tests/` 会挂起；2026-11-13 基线 15307 passed + 3 skipped）
- [ ] **e2e 门禁运行命令**（四目录不含 tests/e2e）：`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/e2e`（addopts 的 -n auto/--dist loadgroup/--cov=src 对该目录可跑不阻断；e2e marker 已注册 pyproject:259；CI 无 tests/e2e 执行位——本地门禁，CI 增位归 deferred）
- [ ] 并行测试 `pytest tests/unit tests/integration -n 8` 通过
- [ ] 连续运行无随机失败（预存抖动族甄别归位惯例——analyst_view/checkpoint 族/externalized_memory redis_ttl 隔离复跑绿）
- [ ] `poetry run ruff check` / `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 统一入口/console_script/六模块挂载 | Task 1 | 入口骨架+模块 Typer app | `test_cli_unified_entry.py` |
| AC-1 | 13 命令三级解析执行 | Task 1/2/3 | 入口骨架/整合/新命令 | `test_cli_unified_entry.py` |
| AC-2 | --format 三态渲染 | Task 1 | formatters 三件+信封契约 | `test_cli_formatters.py` |
| AC-2 | json stdout 纯净（stderr 分流） | Task 1 | formatter 契约 | `test_cli_formatters.py` |
| AC-3 | --yes/--dry-run/--mock 语义 | Task 2 | Agent 参数回调层 | `test_cli_agent_params.py` |
| AC-3 | dry-run 零副作用/mock 标记 | Task 2 | 参数语义实现 | `test_cli_agent_params.py` |
| AC-4 | P1 六模块覆盖 | Task 1/6 | 挂载+架构断言 | `test_arch_cli_unified_entry.py` |
| AC-4 | P4 MCP=0 / P5 SkillSelector 不变 / P7 input_examples | Task 6 | 七原则断言族 | `test_arch_cli_unified_entry.py` |
| AC-5 | sisys-agent 19 命令零回归 | Task 2 | controller 抽取保形 | `test_agent_cli.py`（202 既有+扩展） |
| AC-5 | UUID canonical 归一 | Task 2 | 守卫函数升级 | `test_agent_cli.py`（扩展） |
| AC-6 | load_dotenv 显式加载 | Task 4 | 入口标准化① | `test_cli_entry_standardization.py` |
| AC-6 | SIGTERM 优雅退出 | Task 4 | 入口标准化② | `test_cli_entry_standardization.py` |
| AC-7 | P95<500ms 采样 | Task 5 | 性能验收场景 | acceptance 性能场景 |
| AC-7 | 并发 10 命令 | Task 5 | 并发验收场景 | acceptance 并发场景 |
| AC-1 | 真实服务全链+6.4-DF2 核销 | Task 3 | 集成测试 | `test_integration_cli_unified_entry.py` |
| AC-8 | 收尾完成清单 | Task 7 | 收尾场景 | acceptance 收尾场景 |
| AC-8 | 全量回归/ruff/mypy | Task 7 | 收尾校验 | — |
| — | e2e 子进程冒烟 | Task 5 | e2e 首文件 | `tests/e2e/test_cli_e2e.py` |
| — | 架构约束（import 方向/漂移锁） | Task 6 | 架构验证 | `test_arch_cli_unified_entry.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1~AC-8（规范源头）

> **目的：** 在进入代码实现前，冻结命令面清单、参数语义、formatter 契约、输出信封契约与验收标准。这是 SDD 规范驱动的基础。

- [x] Subtask 0.1: 冻结命令面清单——13 命令 × (模块/命令/参数/消费端口/来源[新增|整合|存量接线]/执行函数实名) 实施计划与规范冻结表（上文「消费端口清单」为底稿，实施时逐命令核对组合根注册名与用例签名——**以组合根与 REST 面源码为契约源，勿凭故事表格签名实施**；**端口对账=能力级核对**——逐命令核对所 resolve 端口确有消费的方法签名（tool list 教训：注册名在册≠能力匹配）；**租户/身份参数强制栏**——**租户消费型命令**（upload/search/version list/tool run/archive query——用例签名收租户者）统一钦定 `--tenant-id`（UUID 守卫 242，`SISYS_TENANT_ID` env 回退双通道，两者皆缺 fail-loud；**校验层位钦定=controller 守卫层**（与 242 定式同位，「守卫先于 bootstrap」断言同源）；**`SISYS_TENANT_ID` 是本 Story 新引入 env 约定**（全仓 src/tests/configs 零命中——非既有约定，冻结表注明新引入身份防 dev 误查既有形态）+ upload 专属 `--uploaded-by` + search 专属 `--collection`（显式参数或配置派生默认名）；**租户可选命令**（tool list——ToolListQuery.tenant_id 为 Optional（ports:101），`--tenant-id` 可选传入过滤、缺省全租户视图）；**非租户消费命令**（agent×2/plan×3/checkpoint×2——用例签名不收租户）不引入 `--tenant-id`（必填不消费=Agent 面净噪声）；存量 version list 的 `--tenant` 旗标改名 `--tenant-id` 对齐（document_commands.py:54/:81 现名））
- [x] Subtask 0.2: 冻结参数语义规范——`--format`（缺省 pretty；json 单行紧凑 ensure_ascii=False；table 两遍法；pretty 既有形态；**plan report 内容格式独立 `--report-format markdown|pdf`**——OD-13）/ `--yes`（确认门等价 `--confirm`，无门幂等）/ `--dry-run`（**client 语义全局统一**：守卫全执行+动作清单+零 resolve 零副作用+exit 0——OD-12；checkpoint recover 裸跑=既有缺省评估模式保留，`--dry-run` 走全局短路不触达评估用例；读命令=守卫校验+回显退化态，冻结表逐命令注明）/ `--mock`（零副作用+`"mock": true`+参数回显+exit 0；文件类参数回显含存在性预检提示）；**三参数并存优先级 `--dry-run` > `--mock` > `--yes`**；**短路层结构=controller 内 `dry_run` 参数分叉（守卫后、bootstrap 前）**——dispatch 矩阵与 recover help 三态文案（缺省=评估/--yes=执行/--dry-run=零服务调用回显，禁复用兼容入口「dry-run 影响评估」措辞）随冻结表落档；逐命令标注确认门有无（checkpoint recover 有、其余无——Typer 面仅暴露 `--yes`，`--confirm` 为兼容入口专属）
- [x] Subtask 0.3: 冻结输出信封契约——json 形态 `{"ok": bool, "command": str, "data": {...}, "mock": bool}` 骨架；错误形态 `[EXCEPTION_code] message` stderr + exit 1（沿用定式，不进信封）
- [x] Subtask 0.4: 冻结七条留项处置对表（Dev Notes「锚定义务清单」逐条落档 + 处置注记追加回 deferred-work.md 的写入计划——6-11 Task 0.7 先例形态，行数守恒核验）
- [x] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_cli_command_interface.feature`（R6 模板风格：AC 横幅分组 8 组/Happy+Edge 全覆盖/异常路径场景）
- [x] Subtask 0.6: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_cli_command_interface.py`（三件套[先例锚 white_label_report.py:154/:168/:192 非 R6 模板]/`_run_cli` helper[先例锚 consultant_view.py:461-480]/双清[文件内私有定义复刻]/真实服务预置通道/S 编号索引表入 docstring）
- [x] Subtask 0.7: 运行验收测试，确认失败（🔴 红阶段验证——红锚符号表逐场景条件化**并按时点分段**：Task 0 时点统一入口整体不存在 → 步骤内延迟 import 抛 ModuleNotFoundError（非 exit 2）；Task 1 骨架就位后未挂载命令 → exit 2；新 formatter 未实现 → 属性错误；含 mock 断言场景按形态区分）
- [x] Subtask 0.8: 链路接线断言清单定义（Task 0 完成标志第 4 项——console_script/13 端口在册/bootstrap 全链/兼容入口复用）

**完成标准/Definition of Done:**
- [x] 规范项全部定义完毕（0.1~0.4 四张冻结表入 Story「实施计划与规范冻结」节）
- [x] 验收测试运行失败（预期行为，红阶段确认）
- [x] 七条留项逐条落档（Epic 6 回顾行动项 1 成功标准达成半边——7-2 达成另半边）

---

### Task 1: 统一入口骨架与格式化器

**关联 AC:** AC-1, AC-2

> **工具先行原则**：先立骨架（入口+挂载+formatter 契约），Task 2/3 的命令在此结构上填充。

#### TDD 循环 A：统一入口骨架

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_cli_unified_entry.py`（console_script 指向/import 链/六模块 Typer 子 app 挂载/三级解析缺省 pretty；**断言对象钦定=cli_main 组装后的完整 app**（非 interfaces 裸 app——OD-16 下裸 app 只有 document/tool/archive 三模块，六模块断言恒不可绿；cli_main 暴露模块级 importable 的组装 app 或 assembly 函数） |
| 🟢 绿 | 实现 `src/entrypoints/cli_main.py`（`sisys` 主入口：load_env → bootstrap 惰性 → Typer app 分发）+ `src/interfaces/cli/main.py`（app 骨架：**三模块**（document/tool/archive）add_typer 挂载）+ `src/entrypoints/cli_commands.py`（**三组占位子 app**——agent/plan/checkpoint，Task 1 建骨架 Task 2 填命令，层内互引合法——OD-16）+ interfaces 侧各模块 `*_commands.py` 占位（命令 Task 3 填充）；cli_main 程序化注册两组 |
| 🔄 重构 | 类型注解/Google 中文 docstring/typer.Option 参数描述完备 |

- [x] Subtask 1.1: 🔴 红 — 入口骨架失败测试（app 存在/六模块挂载/帮助文本骨架）
- [x] Subtask 1.2: 🟢 绿 — cli_main + interfaces/cli/main 装配 + pyproject 双段 console_script
- [x] Subtask 1.3: 🔄 重构 — 入口装配收敛（bootstrap/关池与 agent_cli 复用不复制）

#### TDD 循环 B：格式化器三件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_cli_formatters.py`（json 单行可 loads/信封契约/table 两遍法列宽/pretty 中文形态/进度走 stderr 分流/formatter 分发器单态断言——Task 1 时点 dispatch over 真命令尚不存在；**命令级 dispatch json/table 态零 `_print_*` 断言归 Task 2 循环 C 红面与 Task 6.4 架构位**——OD-14） |
| 🟢 绿 | 实现 `src/interfaces/cli/formatters/`（`json_formatter.py`/`table_formatter.py`/`pretty_formatter.py` + 分发器） |
| 🔄 重构 | 信封构造统一（dict 构造内聚 formatter 层） |

- [x] Subtask 1.4: 🔴 红 — formatter 三态失败测试
- [x] Subtask 1.5: 🟢 绿 — 三 formatter + `--format` 分发器最小实现
- [x] Subtask 1.6: 🔄 重构 — formatter 契约与信封骨架对齐冻结表

**完成标准/Definition of Done:**
- [x] `sisys --help` 六模块可见（Typer testing `CliRunner` 断言）
- [x] formatter 三态测试全绿
- [x] 覆盖率门禁在 Task 7 收尾统一验证（增量 Task 无全量分母，此处不以 85% 卡点）

---

### Task 2: 既有命令整合与 Agent 参数面

**关联 AC:** AC-3, AC-5

> **零回归铁律**：整合 7 命令的执行逻辑复用 agent_cli 既有函数（controller 抽取路径——OD-14），sisys-agent 兼容入口缺省 pretty 零行为变化；202 单测全绿是每步门禁。
> **实施顺序钦定 A→B→C**（循环 C 的命令挂载依赖循环 B 的 Annotated 注入层；循环 B 的三参数测试用**测试文件内本地脚手架命令**验证注入层与短路层——全局 13 命令此时未挂载，Task 3 DoD 增「三参数无豁免矩阵复验点」收口）。
> **留驻声明**：controller 与共享守卫**留驻 agent_cli 模块**（202 单测的 73 处 monkeypatch.setattr 全部 patch agent_cli 模块级属性——bootstrap×31/resolve×30/get_resolver×11，controller 挪新模块则 patch 面全破）；循环 A 的新增测试一律经 `main(argv)` 行为面断言（不测内部函数签名——循环 C 重构后签名漂移不破测试）。

#### TDD 循环 A：UUID 守卫归一升级（6.9-R1-DF1 核销）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/interfaces/cli/test_agent_cli.py`（大写/无连字符 plan_id → 归一命中断言；canonical 输入行为不变断言） |
| 🟢 绿 | 守卫函数升级：`uuid.UUID(x)` 解析通过后 `str()` 归一为小写 canonical 再流入服务层（**现状无共享守卫**——plan_id 守卫是 9 处内联 `uuid_module.UUID(plan_id)` try/except（agent_cli.py:1139/1248/1452/1531/1596/1707/1834/1953/2253），实施=抽取共享守卫函数+改 9 处调用点+归一后传 `str(UUID)`，OD-8 波及面校准） |
| 🔄 重构 | 守卫 docstring 归一语义注记 + 台账划线注记 |

- [x] Subtask 2.1: 🔴 红 — 归一化失败测试（大写 UUID → 现状空态 exit 0，期望命中）
- [x] Subtask 2.2: 🟢 绿 — 守卫单点归一实现
- [x] Subtask 2.3: 🟡 变异 — 归一行删除 → 大写场景红（断言活着实证）
- [x] Subtask 2.4: 🔄 重构 — deferred-work 6.9-R1-DF1 划线注记

#### TDD 循环 B：Agent 参数面（--yes/--dry-run/--mock）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_cli_agent_params.py`（三参数语义矩阵：dry-run 零 resolve 零副作用[resolve 调用计数断言]/mock 信封标记/--yes 等价 --confirm；**参数位置=命令尾随**——与 interface-design §4.3 示例一致） |
| 🟢 绿 | 实现公共参数注入层（**共享 `Annotated[typer.Option]` 类型别名逐命令签名注入**——app 级 callback 选项只能出现在子命令之前，尾随位置传参 exit 2（typer 0.24 venv 实证），callback 仅承载 `--version` 类真全局项；dry-run 短路分叉与 mock 信封生成器属 **controller/命令函数注入层**非 callback 承载——AC-3 验证标准 dispatch 矩阵） |
| 🔄 重构 | 参数语义与冻结表逐条对齐 |

- [x] Subtask 2.5: 🔴 红 — 三参数失败测试（dry-run 时 resolve 调用计数为零断言；测试对=本地脚手架命令；**含 recover 双态两用例**——裸跑评估态保留（resolve 视图用例被调）与 `--dry-run` 全局短路（零 resolve）——OD-12 归宿落位）
- [x] Subtask 2.6: 🟢 绿 — 公共回调 + 短路层实现
- [x] Subtask 2.7: 🟡 变异 — dry-run 短路删除 → resolve 计数断言红
- [x] Subtask 2.8: 🔄 重构 — 逐命令确认门标注对齐

#### TDD 循环 C：7 命令整合（controller 抽取——OD-14 路径）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展统一入口测试（agent instantiate/run-task、plan generate/report/trace-tree、checkpoint list/recover 挂载 + 三格式输出 + sisys-agent 同函数双前端零回归） |
| 🟢 绿 | **controller 抽取**（落位 `src/entrypoints/cli_commands.py`——OD-16）：`_run_*_cli` 内部抽出 controller 函数（守卫[含 `dry_run` 分叉——AC-3 dispatch 矩阵]→`_ensure_bootstrapped`→`asyncio.run(异步内核)`→**返回 result 对象**），controller/守卫留驻 agent_cli 模块（202 单测 patch 面前提），原函数退化为 controller+既有 `_print_*` 薄壳（签名/打印/退出码零变化——既有单测 patch 的是模块级 bootstrap/resolve/get_resolver 全局，不破）；Typer 层（cli_commands.py）缺省 pretty 直调 `_run_*_cli`，json/table 消费 controller 返回的 result（**禁经 `_print_*`**——stdout 纯净机制） |
| 🔄 重构 | 双前端共享 controller 收敛（argparse/Typer 解析层差异隔离在各自入口） |

- [x] Subtask 2.9: 🔴 红 — 7 命令挂载与三格式失败测试
- [x] Subtask 2.10: 🟢 绿 — 整合实现（controller 抽取复用不复制；既有 `--confirm` 保留，`--yes` 别名等价；`--report-format` 拆分按 OD-13）
- [x] Subtask 2.11: 🔄 重构 — `test_agent_cli.py` 202 既有全绿确认 + 12 架构测试文件锚点核对（帮助文本漂移锁若因整合变化需 OD 声明同步）

**完成标准/Definition of Done:**
- [x] 三参数注入层全局可用 + 整合 7 命令三参数全可解析（Task 3 新命令逐命令接入同款 Annotated 别名）
- [x] `test_agent_cli.py` 既有 202 + 扩展全绿（零回归铁律）
- [x] UUID 归一台账划线完成

---

### Task 3: document/tool/archive 新命令

**关联 AC:** AC-1, AC-5（存量接线重构保形）

> **消费对账表为契约锚**：每命令 resolve 前先 grep 组合根注册名核对（端口名以组合根为唯一事实源）。

#### TDD 循环 A：document 模块（upload/search/version 接线）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/interfaces/cli/test_document_commands.py`（upload 参数契约/守卫先于 bootstrap/文件不存在 242；search 参数与端口调用形态；version list 接线） |
| 🟢 绿 | 实现 `sisys document upload/search/version list`（upload → `document_upload_service`，`--business-domain` 映射 metadata dict 键；search → `hybrid_search_service` + `--collection`；version list → 存量 document_commands 接线挂载+错误处理对齐 `[EXCEPTION_code]` 定式重构——存量 `print(f"错误: ...")` 5 处偏离定式一并修正；**既有测试适配义务声明**：test_document_commands.py 4 处既有断言必随行为修复而适配——①:99/:152 `assert "无效的文档 ID" in captured.out`（错误输出 stdout→stderr+`[EXCEPTION_code]` 定式，文案与流双改）；②:44-49/:56-57 `--tenant` 参数名与 `args.tenant == "default"` 默认值断言（改名 `--tenant-id`+双通道 fail-loud 无 default 兜底）；③:102-137 patch `document_commands._get_service`/`asyncio.run` 的 patch 点漂移（定式对齐后函数形态变化）——以 OD-10 行为修复为背书同步适配，属义务非回归） |
| 🔄 重构 | 存量注记更新：src/interfaces/cli/__init__.py:5「未接线存量（勿仿）」改为已接线形态（注记实际位置在包 __init__ 非文件头） |

- [x] Subtask 3.1: 🔴 红 — document 三命令失败测试
- [x] Subtask 3.2: 🟢 绿 — upload/search 新增 + version 存量接线重构
- [x] Subtask 3.3: 🟡 变异 — upload 守卫绕过 → 文件不存在场景红
- [x] Subtask 3.4: 🔄 重构 — 接口层导出与 `__init__.py` 注记同步

#### TDD 循环 B：tool 模块（list/run）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_cli_tool_commands.py`（list 参数/`list_tools_metadata(ToolListQuery)` 端口调用形态；run 参数/--dry-run 门/--mock 信封/工具名守卫） |
| 🟢 绿 | 实现 `sisys tool list/run`（list → `tool_execution_service.list_tools_metadata(ToolListQuery)`——`tool_version_service` 无列工具能力（全方法按单 tool_id 收窄），能力级对账定谳；run → `tool_execution_service`——5-3 激活链在位端口，**不经休眠的 StrategicAnalysisUseCase**，其三向定夺锚 7-2 API 入口非本 Story） |
| 🔄 重构 | run 命令 --mock 与工具 Schema 回显对齐；**--dry-run 动作清单一句钦定**：清单=工具名+入参回显+工具 Schema 摘要（与 --mock 的回显区分：dry-run 含「将执行」动作语义） |

- [x] Subtask 3.5: 🔴 红 — tool 两命令失败测试
- [x] Subtask 3.6: 🟢 绿 — tool list/run 实现
- [x] Subtask 3.7: 🔄 重构 — 工具名值域校验形态（choices vs 守卫——对齐 CLI 通用惯例（argparse/Typer 同构）：值域小且稳定用 choices，否则守卫异常）

#### TDD 循环 C：archive 模块（query）+ 集成测试（含 6.4-DF2 核销）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/cli/test_cli_archive_commands.py` + `tests/integration/test_integration_cli_unified_entry.py`（真实服务全链：upload 真实落库读回/search 真实检索/tool list 真实元数据/archive query 真实读——**含 6.4-DF2 核销场景：无 session 上下文的 CLI 归档消费 + 组合根 `resolve("session_factory")` 接线守卫断言**） |
| 🟢 绿 | 实现 `sisys archive query`（→ `strategic_archive_service`，CQRS 读模型面）；集成测试绿 |
| 🔄 重构 | 集成测试自清理链（创建→执行→清理，禁 delete/truncate） |

- [x] Subtask 3.8: 🔴 红 — archive 命令 + 集成全链失败测试
- [x] Subtask 3.9: 🟢 绿 — archive query 实现 + 集成绿
- [x] Subtask 3.10: 🔄 重构 — 6.4-DF2 台账划线注记（核销证据：集成测试文件路径+场景名）

**完成标准/Definition of Done:**
- [x] 六模块 13 命令全部实现（P1 达成）
- [x] 集成测试真实服务全链绿
- [x] 6.4-DF2 核销划线完成
- [x] **三参数无豁免矩阵复验**（13 命令 × `--yes`/`--dry-run`/`--mock` 全可解析——Task 2 循环 B 脚手架面测的全局收口，R2-03 承接位）

---

### Task 4: CLI 入口标准化（6.8-R1-DF1 + R1-DF6 核销）

**关联 AC:** AC-6

#### TDD 循环 A：显式 load_dotenv

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/entrypoints/test_cli_entry_standardization.py`（**纯语义红锚**——tmp_path 写 .env + monkeypatch 指定路径 → 断言 main() 调用后目标键注入 os.environ、override=False 下已设键不被覆盖；in-process「.env 失效复现」结构性不可达：conftest session autouse `_bootstrap_once`（tests/conftest.py:31）已填充 registry，`_ensure_bootstrapped` 即短路，**裸跑复现归 subprocess 冒烟/e2e 面**——AC-6 验证标准①） |
| 🟢 绿 | 统一入口与兼容入口显式 `load_dotenv(dotenv_path=<仓库根探测>, override=False)`（python-dotenv；仓库根以 `Path(__file__)` 上溯定位——解 `python -m` 形态 `find_dotenv` 从 site-packages 向上遍历永不经过仓库目录的三层根因；**测试形态守卫：`SISYS_USE_TEST_PORTS=1` 时跳过**——.env 被 git 追踪，进程内注入会泄漏非端口键污染同 worker 后续场景） |
| 🔄 重构 | 加载点收敛单函数双入口复用 |

- [x] Subtask 4.1: 🔴 红 — load_dotenv 语义失败测试（删 load_dotenv 调用即红——键注入断言/override 断言两锚）
- [x] Subtask 4.2: 🟢 绿 — load_dotenv 实现双入口挂载
- [x] Subtask 4.3: 🟡 变异 — load_dotenv 删除 → 装配失败测试红
- [x] Subtask 4.4: 🔄 重构 — 6.8-R1-DF1 台账划线（三选一定谳=入口显式 load_dotenv，落档理由）

#### TDD 循环 B：SIGTERM 优雅退出

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 同文件扩展（signal handler 注册断言/信号触发时 span flush 与连接池关闭调用计数/未激活 tracer 时零动作；**handler 直调单测形态**——不依赖真实信号时序） |
| 🟢 绿 | 实现 signal handler（SIGTERM/SIGINT；**机制钦定**：`signal.signal` 同步 handler 内——①PhoenixTracer.shutdown() **同步 API 直调**（phoenix_tracer.py:179，span flush 同步可行）；②池关闭是 async（`_close_connection_pools` agent_cli.py:740）——handler 内 `asyncio.get_running_loop()` 取运行中 loop → `asyncio.run_coroutine_threadsafe(池关闭协程, loop)` 调度并等待完成再退出；无运行 loop（bootstrap 前信号）仅同步面 flush 后退出。**禁止** handler 内直接 asyncio.run/新 loop（另一 loop 运行中必抛 RuntimeError）。**复用钦定**：优先复用组合根 `shutdown()`（composition_root.py:3832，peek agent_tracing 刷盘+关池——其注释明示「CLI 面不调本函数的 SIGTERM 缺口见 5-7 R1-DF6」即本 Story 缺口预留）——实施核对其 peek 语义与 OD-9 一致后经 run_coroutine_threadsafe 采用；不一致则独立调度 `_close_connection_pools`[peek_singleton 探测已实例化，禁 resolve 新实例——agent_cli.py:747-748 注记约束、peek 调用 :766]） |
| 🔄 重构 | handler 双入口复用 + 5-7 R1-DF6 台账划线；**验收载体钦定**：单测=handler 函数直调调用计数；subprocess 冒烟=bootstrap ~3.9s 窗口内发 SIGTERM 验证优雅退出（退出码非 traceback 崩溃形态；span 尚未产生的弱化断言已注明） |

- [x] Subtask 4.5: 🔴 红 — handler 失败测试
- [x] Subtask 4.6: 🟢 绿 — handler 实现
- [x] Subtask 4.7: 🔄 重构 — R1-DF6 台账划线

**完成标准/Definition of Done:**
- [x] 无环境变量 shell 裸跑两入口正常执行（AC-6 验证标准①）
- [x] SIGTERM 优雅退出实证
- [x] 两条台账划线完成

---

### Task 5: 性能/并发验收与 E2E

**关联 AC:** AC-7

#### TDD 循环 A：P95 采样与并发场景

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 验收文件扩展性能/并发场景（20 轮 P95 数学口径+_WARMUP_ROUNDS=2+每轮采样含双清（池重建入窗=进程语义，OD-3 附注）+六模块 read 侧代表命令[agent instantiate 真执行+租户自清理，禁 dry-run 采样]；**并发=10 独立子进程**（asyncio.create_subprocess_exec——OD-15，命令集=混合面：写入型 5+读型 5——AC-7 验证标准钦定清单），每进程独立 UUID 前缀隔离） |
| 🟢 绿 | 场景步骤实现（计时窗口=bootstrap 后执行段——6-11 编程面直调免 bootstrap 混入先例；性能场景挂 xdist_group） |
| 🔄 重构 | 超标时的性能归因路径（in-process 口径下超标=实现缺陷，禁口径放水；并发子进程 bootstrap ~3.9s/进程属正确性测试成本，与 P95 计时分立） |

- [x] Subtask 5.1: 🔴 红 — 性能/并发场景（阈值断言）
- [x] Subtask 5.2: 🟢 绿 — 步骤实现 + 采样达标
- [x] Subtask 5.3: 🔄 重构 — 采样命令矩阵与 OD-3 口径声明对齐

#### TDD 循环 B：E2E 子进程冒烟（tests/e2e 首个测试文件——目录已有 __init__.py）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/e2e/test_cli_e2e.py`（subprocess 真进程，**13/13 冒烟形态钦定**：每命令 `--help` exit 0 全集 + 真实只读命令冒烟子集（tool list/archive query 等）+ 写命令 `--dry-run` 冒烟（兼验短路层子进程面接线）；`.env` 加载后真实只读命令冒烟——tool list 等；**双通道机制**：`shutil.which("sisys")` 探测 console_script（可用时 script 通道与 `-m` 通道**均执行**）+不可用时 `sys.executable -m src.entrypoints.cli_main` 回退+仍不可用 pytest.skip 动态降级；真实服务冒烟依赖 PG/Redis 可用性——不可用时 pytest.skip 动态跳过） |
| 🟢 绿 | e2e 通过（subprocess env 构造：TEST_PORTS=1 + TestTenant 前缀；安装态 console_script 可用性验证；e2e marker 已注册（pyproject :259）无需新增） |
| 🔄 重构 | e2e 环境构造收敛（环境不依赖调用方残留；CI 无 tests/e2e 执行位现状注记——CI 增位归 deferred） |

- [x] Subtask 5.4: 🔴 红 — e2e 失败测试
- [x] Subtask 5.5: 🟢 绿 — e2e 全绿（13/13 命令冒烟全覆盖=E2E 声明式口径达成）
- [x] Subtask 5.6: 🔄 重构 — e2e 分层标记（独立 marker，避免误入四目录全量窗口时长）

**完成标准/Definition of Done:**
- [x] P95<500ms 六模块采样达标
- [x] 并发 10 零失败
- [x] e2e 全绿

---

### Task 6: SDD 架构约束验证测试

**关联 AC:** AC-4, AC-5

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。

#### 架构验证测试实现

- [x] Subtask 6.1: 创建 `tests/unit/architecture/test_arch_cli_unified_entry.py`
- [x] Subtask 6.2: 验证器——六模块挂载完整性（13 命令注册断言，帮助文本漂移锁——agent_cli 同款先例）
- [x] Subtask 6.3: 验证器——七原则断言族：P1 挂载断言/P4 grep mcp 零目录零依赖/P5 SkillSelector 源码形态不变（零排序零打分零 Top-K AST 断言）/P7 input_examples 存在性清单断言（**23/23 全量** SKILL.md `## 8.` 章节各 ≥1——ToolMetadata 无此字段，断言只可锚 SKILL.md 章节）
- [x] Subtask 6.4: 验证器——import 方向（interfaces/cli 文件 AST 断言**禁 import src.infrastructure 与 src.entrypoints 与 src.composition_root**——OD-16 传导链守卫；Typer 形态[app 构造/Option 使用]断言；**dispatch 层 json/table 态零 `_print_*` 调用 AST 断言**——OD-14 机制升架构位）
- [x] Subtask 6.5: 验证器——console_script 双段一致（**断言收窄为 `sisys` 条目**——现状两段不对称（crawler 仅 [project.scripts]），全段相等断言必红）+ 消费端口对账表 grep 断言（13 resolve 目标组合根在册）
- [x] Subtask 6.6: 运行完整测试套件并生成报告（12 个既有 agent_cli 架构测试文件（16 个测试函数）全绿核对——锚点漂移 OD 声明）

**完成标准/Definition of Done:**
- [x] 所有架构/约束测试通过
- [x] 测试输出清晰的合规报告
- [x] 任何违规都会导致测试失败
- [x] 循环依赖检测使用 ruff/isort（不引入额外工具）

---

### Task 7: 开发结束验收测试

**关联 AC:** AC-8

> **性质说明：** 本 Task 不是功能实现，而是对 Story 收尾阶段的交付物与完成清单进行最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 feature 收尾验收场景（src/tests 五目录完成清单逐项；**红阶段仪式性声明**——断言对象是已存在文件，Task 7 时点结构性无红，6-11 S14 同款形态，如实标注非虚报红） |
| 🟢 绿 | 编写 BDD 步骤实现（`_COMPLETION_SRC_FILES`/`_COMPLETION_TEST_FILES` dict 逐项 `Path.exists()`——6-11 S14 先例） |
| 🔄 重构 | 收敛场景命名、统一断言表达 |

- [x] Subtask 7.1: 场景 1 — 验证 `src` 完成清单（cli_main/interfaces/cli 模块文件/formatters/entrypoints）
- [x] Subtask 7.2: 场景 2 — 验证 `tests` 五目录完成清单（unit/integration/contracts[零改动声明]/acceptance/e2e）
- [x] Subtask 7.3: 运行开发结束验收测试并确认通过
- [x] Subtask 7.4: 运行四目录全量 + `ruff check src/ tests/` + `mypy src/` 收尾校验（红线三查零新增）
- [x] Subtask 7.5: deferred-work.md 处置注记终核（七条对表全部落档形态核验——划线条目 RESOLVED 前置+原描述保留；顺延条目注记在位；行数守恒核对）

**完成标准/Definition of Done:**
- [x] `src` 完成清单已逐项验证确认
- [x] `tests` 五目录完成清单已逐项验证确认
- [x] 开发结束验收测试通过
- [x] 四目录全量零失败 + 红线三查零新增
- [x] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../planning-artifacts/architecture.md) + [`interface-design.md`](../../../docs/architecture/interface-design.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ D1 方案 A（进程入口组装层）+ CQRS 读模型（archive）
- **设计约束:** 领域层零依赖（本 Story 零触碰 domain）；interfaces 禁 import infrastructure；组合根唯一注册（本 Story 零新注册）；CLI 五步定式（守卫先于 bootstrap → `_ensure_bootstrapped` → resolve → asyncio.run → DomainError stderr exit 1；**例外注记**：既有 instantiate 直调 `bootstrap()`（agent_cli.py:2355）为唯一不走幂等守卫的命令——兼容入口现状保留，Typer 新前端统一走幂等守卫形态）
- **接口治理:** 本 Story 是纯消费方（13 端口全部既有）；不新增 Protocol 定义；CLI 契约载体=命令面冻结表+帮助文本漂移锁
- **技术栈:** Python 3.11+ / **Typer `^0.24.0`**（pyproject.toml:21 已声明（caret 上界 <0.25——0.24.x 线），本 Story 首次生产消费——架构钦定 or.md L79）/ rich（Typer 传递依赖，table 渲染可用其 Rich 库或纯标准库两遍法——实施定夺，两遍法有 `_print_checkpoint_summary_table` 先例）

### 关键架构决策

**来源:** [`architecture.md`](../../planning-artifacts/architecture.md) §13.5 / [`interface-design.md`](../../../docs/architecture/interface-design.md) §4 / epic-6-retro-2026-11-09.md

| # | 决策 | 内容与理由 |
|---|------|-----------|
| **DC-1** | Typer 统一入口（vs 维持 argparse） | 架构钦定（or.md L79/interface-design §2.1/architecture §13.5/CLAUDE.md 技术栈「FastAPI + Typer」）+ 依赖已声明未消费；既有 agent_cli argparse 前端保留为兼容入口（双前端共享执行函数——argparse 解析层差异隔离在 sisys-agent 入口） |
| **DC-2** | 分层整合（vs 全量 19 命令整合） | 7-1 挂载 13 命令（六模块全覆盖满足 P1）；sisys-agent 其余 12 命令（load-profile/chain-query/三视图×3/isolation×3/brand×2/checkpoint-create/checkpoint-show——19−整合7=12）后续整合归 deferred 微 Story——全量整合单 Story 不可行（19 命令 × controller 抽取 × 202 单测适配爆炸半径） |
| **DC-3** | controller 抽取复用不复制（OD-14 详化） | 整合命令执行逻辑复用 `_run_*_cli` 系函数（202 单测锤炼的生产代码）——**但复用层级=controller 抽取**：`_run_*_cli` 现状返回 int 退出码且 `_print_*` 渲染内嵌（字面包装拿不到 result），实施=函数内抽出 controller（守卫→幂等 bootstrap→asyncio.run 异步内核→返回 result），原函数退化为 controller+既有 `_print_*` 薄壳零行为变化；render 层新增 formatter；json/table 消费 controller result 禁经 `_print_*`；缺省 pretty=既有形态（sisys-agent 零回归的结构保证） |
| **DC-4** | tool run 消费 tool_execution_service（vs StrategicAnalysisUseCase） | 后者组合根未注册（休眠，三向定夺锚 7-2 API 入口——6-11 Task 0 处置注记钦定「Epic 7 API 入口立项」字面不含 CLI 入口）；tool_execution_service 5-3 激活链在位 |

### 偏离声明（OD）

| # | 偏离 | 四要素（gap/触发/理由/归宿） |
|---|------|------------------------------|
| **OD-1** | epics 命令示例 `sisys upload --file docs.zip`（一级命令） | gap：与 interface-design §4.2 三级结构不一致；理由：epics「如」字示意简化，以 §4.2/§4.3 钦定 `sisys document upload` 为准；归宿：本 Story 命令面冻结表 |
| **OD-2** | P5 验收口径不沿用 epics「SkillSelector 推荐 Top-3 命中率」 | gap：该文案已废弃（Story 5-2 偏离声明 D-1 + selector.py 头注自证——现实为 ACTIVE 过滤零 Top-K，interface-design §5.5 钦定 description 触发免硬编码）；理由：沿旧口径=要求实现已废弃行为；归宿：AC-4 P5 改为 SkillSelector 形态不变断言 + 评测锚 Story 5-9 AC-8 |
| **OD-3** | P95 计时口径=in-process（bootstrap 后执行段） | gap：epics P95<500ms 未注阶段与计时窗口，且 PRD(<1s MVP)/architecture(<200ms V2)/interface-design(告警>1s) 四处口径不一（**同号消歧**：NFR-IF-01 在 prd=CLI 延迟、在 epics L336=决策舱加载<2s——本 Story 覆盖溯源按 prd 条目）；理由：bootstrap ~3.9s（cf6a6f7b 优化后复测）进程级不可达，6-11「编程面直调免 bootstrap 混入」先例钦定命令执行延迟语义；**附注**：每轮采样含双清（池重建成本入窗=单进程 CLI 真实语义）；agent 模块采样=instantiate 真执行（禁 dry-run——零 resolve=计时空洞）；归宿：AC-7 口径声明 + 冷启动观测面另行登记（deferred：CLI 冷启动优化专项锚） |
| **OD-4** | 七原则 P7 双版本 | gap：interface-design §1.2（input_examples 驱动）vs architecture §1.5（代码优先于 Prompt）；理由：PRD FR-IF-01/or.md/epics 三处均 input_examples 版本（FR 溯源链一致）；归宿：AC-4 采 input_examples 口径 |
| **OD-5** | system/config 模块 + `--cost-budget`/`--session`/`--timeout` + `--format ndjson/csv` 排除 | gap：interface-design §4.3.7/4.3.8/§4.4/§4.5 全量规范 vs epics AC 钦定子集（三参数三格式六模块）；**补注**：§4.4「--yes 必填=是（未设→拒绝执行）」语义一并顺延（本 Story --yes=确认门可选别名非拒绝门）；理由：epics AC 是 Story 验收边界，全量参数面依赖 Agent 成本治理（三级熔断）与 7-4 仪表盘面；归宿：deferred-work 登记（Agent 参数全量面专项 / system 模块归 7-4） |
| **OD-6** | 测试文件名对 epics 钦定名的偏离 | gap：epics 钦定 `tests/unit/interfaces/test_cli.py`/`tests/integration/test_cli_integration.py` vs 仓规（unit 按层目录 `tests/unit/interfaces/cli/`、integration `test_integration_*` 前缀——OD-9 先例[6-11]）；理由：仓规目录先例在案（test_agent_cli.py 同目录）；归宿：本 Story 测试分类表文件名（e2e 位 `tests/e2e/test_cli_e2e.py` 保留 epics 钦定——目录仅 __init__.py 无测试先例冲突） |
| **OD-7** | 6.8-R1-DF1 三选一定谳=入口显式 load_dotenv | gap：三选一（入口显式 load_dotenv/装配链惰性化/部署侧 env 注入）；理由：最小修复面直接解 `python -m` 根因（find_dotenv 从 site-packages 上溯不达仓库根），override=False 保护测试形态 env 优先；装配链惰性化波及组合根宽树（cf6a6f7b 刚做四入口下沉，再动风险大）；部署侧注入是部署面非代码面；归宿：Task 4 实施 + 台账划线 |
| **OD-8** | 6.9-R1-DF1 定谳=canonical 归一（vs 保持宽松） | gap：非 canonical UUID 输入静默空态（现状）vs 归一命中（修复）；理由：静默空态违反 fail-loud 精神（大写 UUID → exit 0 空输出是欺骗性成功）；**波及面校准**：现状无共享守卫——plan_id 守卫为 9 处内联 try/except（agent_cli.py:1139/1248/1452/1531/1596/1707/1834/1953/2253），实施=抽取共享守卫+改 9 处调用点+归一传 `str(UUID)`，行为只增强不破坏（canonical 输入不变）；归宿：Task 2 循环 A + 台账划线 |
| **OD-9** | R1-DF6 最小处置=信号 handler 精确刷盘（vs 全量 shutdown） | gap：agent_cli.py:747-748 禁全量 shutdown 注记（退出路径惰性实例化风险；peek_singleton 调用 :766）；理由：SIGTERM 面仅需 span flush + 已实例化连接池关闭（peek 不 resolve）；归宿：Task 4 循环 B + 台账划线 |
| **OD-10** | document_commands 存量「勿仿」注记解除 | gap：存量文件错误处理（print "错误:"）偏离 `[EXCEPTION_code]` 定式且无挂载点；理由：7-1 接线即继承生产责任，错误处理对齐定式后注记更新；归宿：Task 3 循环 A |
| **OD-11** | 三向定夺（StrategicAnalysisUseCase/orchestration_service/data_pipeline）7-1 不触发 | gap：台账锚「Epic 7 API 入口立项」；理由：7-1 是 CLI 入口，字面与实质（消费方为零 resolve 的 REST 编排面）均不触发；归宿：deferred-work 注记顺延 7-2（7-2 立项时三向定夺） |
| **OD-12** | `--dry-run` 语义定谳=client 语义全局统一（recover 裸跑保留既有评估缺省态） | gap：checkpoint-recover 既有缺省态（无 `--confirm`）=use-case 级评估模式（resolve checkpoint_recovery_use_case agent_cli.py:2093，三零=不落记录/不发事件/不应用修正）且既有 help 自称「缺省为 dry-run 影响评估」——与 AC-3 新全局 `--dry-run`「不 resolve 用例」同名不同义；定谳（对标 kubectl `--dry-run=client`）：全局 `--dry-run`=client 语义（守卫+动作回显+零 resolve+exit 0）13 命令统一（Agent 消费面统一契约，Subtask 2.5 零 resolve 断言全局成立无豁免）；recover 裸跑=既有评估模式保留（人类用户信息量更大的缺省态），`--dry-run` 走全局短路不触达评估用例（帮助文本自洽：缺省=评估（详）；--dry-run=快速回显（零服务调用））；归宿：AC-3/消费端口表/Subtask 0.2/2.5 同步 |
| **OD-13** | plan report 内容格式拆分 `--report-format`（vs `--format` 五值并集） | gap：既有 report-generate `--format` choices=("markdown","pdf")（agent_cli.py:356-360，语义=报告内容格式）与 AC-2 `--format json/table/pretty`（语义=输出信封格式）同一 flag 双正交语义 choices 互斥；定谳：Typer 面 `--format`=输出三态、报告内容格式独立 `--report-format markdown\|pdf`（缺省 markdown 对齐既有）；sisys-agent 兼容入口 `--format` 语义不变（argparse 前端零改动）；§4.3.4 plan export 的同类撞名顺延（export 非 13 命令，7-2/后续 export 立项时定夺）；归宿：AC-2 验证标准/Task 0.2 冻结表/Task 2.10 |
| **OD-14** | controller 抽取路径 + §13.5 controllers/×8 规划位偏离 | gap①：`_run_*_cli` 返回 int 退出码且 `_print_*` 渲染内嵌——「包装既有执行函数→result→formatter」字面不可满足（拿 int 当 result）；gap②：architecture §13.5 为 interfaces/cli 规划 controllers/×8 独立层，本 Story 不新建该层；定谳：controller 职能经「`_run_*_cli` 函数内抽取 controller（返回 result）+原函数退化为 controller+`_print_*` 薄壳」内聚消解（双前端共享、既有 202 单测 patch 面不破）；json/table 渲染源=controller result 禁经 `_print_*`（stdout 纯净机制）；理由：双前端共享执行函数形态下 controllers/ 独立层无增量价值，避免三层薄壳；归宿：DC-3/Task 2 循环 C/Task 6.4 架构断言锚 |
| **OD-15** | 并发验收形态定谳=10 独立子进程（vs in-process gather） | gap：AC-7 原文「asyncio.gather / 独立子进程两形态任证其一」两形态不等价——gather 聚合 CLI main() 结构性不可行（`_run_*_cli` 内 `asyncio.run` 在运行中 loop 内再调必抛 RuntimeError；线程池形态撞 SINGLETON manager 绑定旧 loop 跨循环族）；定谳（对标业界 CLI 并发验证惯例 xargs -P/subprocess 并发）：10 独立子进程经 `asyncio.create_subprocess_exec` 并发拉起（兼得两词面）；每进程 bootstrap ~3.9s 属正确性测试成本与 P95 计时分立；归宿：AC-7/Task 5 循环 A |
| **OD-16** | 整合命令 Typer 层落位 entrypoints（vs interfaces/cli/commands） | gap：7 整合命令依赖 agent_cli（entrypoints）的 controller/守卫/`_print_*`——若命令文件落 interfaces/cli/commands 则 `interfaces → entrypoints → composition_root → infrastructure` 传导链重触发 import-linter interfaces-no-infrastructure 契约（.importlinter:74 注记自证该链历史清零，CI 必红）；定谳：整合命令 Typer 模块落 `src/entrypoints/cli_commands.py`（agent/plan/checkpoint 三组子 app，entrypoints 层内互引合法）；interfaces/cli 保留新命令（document/tool/archive——domain 层 Resolver 先例）+ formatters + main.py app 骨架；cli_main 程序化注册装配（entrypoints→interfaces 合法方向）；理由：controller 无法合法移入 interfaces（bootstrap 链），注入间接层为 7 命令引入无价值复杂度；归宿：分层落位节/项目结构/Task 6.4 import 方向断言面（interfaces 文件 AST 断言禁 import entrypoints+composition_root）/文件清单 |

### 项目结构说明 Project Structure

```
src/
├── entrypoints/
│   ├── agent_cli.py              # ▲ 扩展（UUID 守卫归一/SIGTERM/load_dotenv/controller 抽取；19 子命令保留）
│   ├── cli_commands.py           # ★ 新建——7 整合命令 Typer 模块（agent/plan/checkpoint 三组子 app；OD-16 层位——import agent_cli controller/守卫/_print_*，entrypoints 层内互引合法）
│   ├── cli_main.py               # ★ 新建——sisys 统一入口（console_script 目标；load_env→signal→bootstrap 惰性→装配 interfaces app + cli_commands 注册→分发；含 `if __name__ == "__main__"` 守卫支持 python -m 形态——AC-6 验证标准①）
│   └── ocr_cli.py                # 不动
├── interfaces/cli/
│   ├── __init__.py               # ▲ 注记更新（document_commands 接线形态——「勿仿」注记现位置 :5）
│   ├── main.py                   # ★ 新建——Typer app 骨架（document/tool/archive 三模块 add_typer 挂载；整合三组由 cli_main 注册注入）
│   ├── commands/
│   │   ├── __init__.py           # 既有（不动——包标记已在）
│   │   ├── document_commands.py  # ▲ 扩展重构（upload/search 新增 + version 接线 + 错误处理定式对齐；--tenant 改名 --tenant-id 注记）
│   │   ├── tool_commands.py      # ★ 新建——tool list/run（import domain 层 Resolver——document_commands 先例）
│   │   └── archive_commands.py   # ★ 新建——archive query（同上先例形态）
│   └── formatters/
│       ├── __init__.py           # ★ 新建——分发器
│       ├── json_formatter.py     # ★ 新建
│       ├── table_formatter.py    # ★ 新建
│       └── pretty_formatter.py   # ★ 新建
└── composition_root.py           # 不动（零新注册）
```

（★ 新建 ▲ 扩展；pyproject.toml ▲ [project.scripts]+[tool.poetry.scripts] 双段加 `sisys = "src.entrypoints.cli_main:main"`）

### 六模块 CLI 覆盖矩阵（P1 达成形态）

| 模块 | 7-1 前 | 7-1 后（统一入口命令） |
|------|--------|----------------------|
| document | 无接线 CLI（存量未挂载死代码） | upload / search / version list |
| tool | 无 CLI（仅 REST） | list / run |
| agent | sisys-agent agent 类 6 命令（核心 3+隔离 3） | instantiate / run-task（+sisys-agent 19 全保留） |
| plan | sisys-agent plan 类 4 命令（blm-plan/chain-query/report-generate/trace-tree） | generate / report / trace-tree（+兼容入口全保留） |
| checkpoint | sisys-agent 4 命令（create/list/show/recover） | list / recover（+兼容入口全保留） |
| archive | 无 CLI（仅 REST） | query |

> 注：19 子命令全量归类=agent 6（核心 3+隔离 3）+plan 4+checkpoint 4+视图 3+品牌 2=19；视图 3/品牌 2/隔离 3/load-profile/chain-query/checkpoint-create/checkpoint-show 属「其余 12 命令」后续整合面（DC-2）。

### 锚定义务清单（deferred-work 台账——Task 0.4 逐条处置 / Task 7.5 终核）

> Epic 6 回顾行动项 1 强制承载（成功标准：Epic 7 首两个 Story 立项文件含该清单且逐条落档）。处置动作=实施核销（划线）或顺延注记（追加处置注记回台账，行数守恒）。

| # | 台账锚位 | 留项内容（摘要） | 7-1 处置 |
|---|---------|-----------------|---------|
| 1 | L330（6.1-DF5） | BLM 状态查询生产入口零消费 | **顺延 7-2**（CLI 阻塞语义无中途查询场景；REST GET /plans/{id} 立项时接线）——注记「7-1 CLI 入口立项评估：不触发」 |
| 2 | L331（6.1-DF6） | REST 并发入口前置三项（双跑守卫竞态/_runs 零治理/孤儿事件） | **顺延 7-2**（CLI 一次性进程三项均不可达）——同款注记 |
| 3 | L362（6.4-DF2） | CR1-F1 fallback 集成/验收零覆盖 + 组合根接线无守卫 | **核销**（Task 3 循环 C：archive query 构成无 session 上下文 CLI 归档消费——补集成场景 + `resolve("session_factory")` 接线守卫断言） |
| 4 | L369（6.5a-DF1） | REST 导出面 /plans/{id}/export 无契约 | **顺延 7-2**（CLI 面零 REST 契约）——注记 |
| 5 | L370（6.5a-DF2） | 同 plan 并发 L0 撕裂（「REST 读侧上线前必须处置」） | **顺延 7-2**（7 条中唯一「必须」义务，约束 REST 面；7-1 CLI 单次进程不激活并发形态）——注记义务随 7-2 维持 |
| 6 | L402（6.8-R1-DF1） | CLI python -m .env 不加载（embedding 201/InvalidPasswordError 两呈现） | **核销**（Task 4 循环 A：OD-7 三选一定谳=入口显式 load_dotenv） |
| 7 | L409（6.9-R1-DF1） | --plan-id 族非 canonical UUID 静默空态 | **核销**（Task 2 循环 A：OD-8 canonical 归一） |
| 8 | L254（5-7 R1-DF6） | SIGTERM 面 span 刷盘缺口（唯一显式点名 7-1 的开口条目） | **核销**（Task 4 循环 B：OD-9 信号 handler 精确刷盘） |
| 9 | L158（D1 治理注记） | 「Epic 7 集中 CLI 时入口在 entrypoints 层内合并即可」 | **知悉消费**（台账已 RESOLVED 2026-10-15 方案 A——零动账；DC-1/DC-2 按「entrypoints 层内合并」钦定执行 cli_main.py 统一入口；归 Task 7.5 终核引用核对） |
| 10 | L125/L129（三向定夺） | StrategicAnalysisUseCase/orchestration_service/data_pipeline 废弃定夺锚「Epic 7 API 入口立项」 | **顺延 7-2**（OD-11：CLI 入口≠API 入口）——注记 |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 6-11 白标报告](./6-11-white-label-report-basic.md)（v1.9.0，文档审查五轮 61 项+代码审查五轮 22 项收敛）+ Epic 6 十连 CLI-only 实践

**关键学习/Key Learnings:**
- CLI 直调三清纪律（`_clear_session_ctx` + `_clear_resolver_caches` 双清——单清形态 6-6 R3-1 已证伪）；禁二次 bootstrap（ConflictError DC-12③）
- 模块级零新词族 import（收集期 ImportError 全文件 ERROR）；exit code 断言独立步骤绑定；S 编号禁泄入场景名/函数名
- 提交型写入测试挂 `xdst_group("blm-planning-perf")` 同组串行；共享库读回断言定向过滤（行动项 4）
- 红锚符号表逐场景条件化（CLI 直调 exit 2 / 延迟 import ImportError / 参数断言 AssertionError 三形态区分）
- P95 采样 20 轮 + `_WARMUP_ROUNDS=2` + 编程面直调免 bootstrap 混入计时窗口；性能口径差逐段 OD+docstring 声明
- argparse choices 不可经 CLI 触达的负例走编程面直调（choices 是 exit 2 硬拦截）
- 「Agent 误报主会话复核」纪律：调研结论关键锚点主会话亲验后方可入 Story（6-11 亲验 20 组）

**应用到本故事/Applied to This Story:**
- [x] 验收测试三件套+双清+`_run_cli` helper 复刻真实代码先例（consultant_view.py:461-480 `_run_cli_consultant_view` / white_label_report.py:154/:168/:192——测试分类表与 BDD 约束节已固化）
- [x] 性能口径 OD-3 显式声明（四处口径差入档）
- [x] 锚定义务清单表复刻 6-11 Task 0.7 既有实践形态（十行对表）
- [x] 消费端口表锚点主会话亲验（document_upload.py:134/tools.py:144/strategic_archive.py:179/document_commands.py:22 四处 grep 定谳）

### 其他关键约束速查

- **CLI 认证形态**：CLI 面无认证（agent_cli 19 命令先例——CLI 非 HTTP 面不受「API 路由必须过认证中间件」约束；本 Story 沿用）
- **禁 argparse `type=uuid.UUID`**（ValueError→exit 2 绕过统一异常体系——agent_cli.py:17-20 注记；Typer 同理用守卫函数）
- **Typer `raise typer.Exit(code=1)`**（crawler 插件 plugins/crawler/cli.py 先例）或返回 int 退出码——双前端共享执行函数时以返回 int 为准（argparse 侧 main 返回链兼容）
- **CLI 打印面用 `getattr(result, "field")`** 属性访问避免实体 import 依赖（agent_cli _print_* 全系先例）
- **事件不阻塞 CLI 响应**：fire-and-forget（interface-design §3.3 规则 4——`--wait-for-events` 是 V1+ 可选，MVP 不实现）
- **组合根不动**：本 Story 零注册变更；若实施中发现"必须注册新端口"——停（见端口契约清单执行约束）
- **基准 commit**：6fdbc143（2026-11-13，Epic 1~6 例行核销后 clean main）——锚点表行号以本基准为准，组合根行号随演进以 grep 为准

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (GLM) |
| **Version** | create-story workflow v2.9.0 |
| **Execution Date** | 2026-11-13 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Epic 7 节 L2565-2996；Story 7.1 节 L2597-2649） |
| **架构文档** | `docs/architecture/architecture.md`（§1.4/§1.5/§13.5）+ `docs/architecture/interface-design.md`（§1.2/§3.3/§4/§15.2/§16.2） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/6-11-white-label-report-basic.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **调研基线** | 三路并行调研（CLI 代码现状/七原则与规范/留项台账与测试风格）+ 主会话亲验（消费端口四处 grep/休眠台账/tool 执行链激活态） |

### 实现计划与规范冻结 Implementation Plan & Frozen Specs（Task 0——dev-story 实施时落档）

> 基准：2026-11-13 HEAD（202 基线全绿实测 15.08s；15 端口注册名组合根在册亲验；Typer 0.24.2 venv 双实证——命令级 Annotated 尾随 Option 三级结构 exit 0 / callback 级尾随 exit 2）。四路调研 Agent + 主会话亲验双轨核实。

#### Task 0.1 命令面冻结表（13 命令——实现禁增删；执行函数实名以 agent_cli.py 为准）

| # | 命令（Typer 面） | 来源 | 执行函数实名/落位 | resolve 端口（组合根注册名） | 命令参数（*必填） |
|---|---|---|---|---|---|
| 1 | `sisys document upload` | 新增 | 新写 `document_commands.py` | `document_upload_service`（:1189，SCOPED） | `--file*` `--business-domain*` `--source*` `--license*`（REQUIRED_METADATA_FIELDS 五键之必供三键——R1-D1 表同步）`--document-type`（缺省 other）`--tenant-id*†` `--uploaded-by*†` |
| 2 | `sisys document search` | 新增 | 新写 `document_commands.py` | `hybrid_search_service`（:1854，SCOPED） | `--query*` `--collection`（缺省 documents）`--limit`（缺省 10）`--tenant-id*†` |
| 3 | `sisys document version list` | 存量接线重构 | 存量 `_handle_list` Typer 化（`document_commands.py`） | `document_version_service`（:1410，SCOPED） | `--id*` `--tenant-id*†` |
| 4 | `sisys tool list` | 新增 | 新写 `tool_commands.py` | `tool_execution_service.list_tools_metadata(ToolListQuery)`（:2741，SCOPED；**同步方法**） | `--category` `--status` `--tenant-id`（**可选**——ToolListQuery.tenant_id: uuid.UUID\|None）`--offset`（0）`--limit`（100） |
| 5 | `sisys tool run` | 新增 | 新写 `tool_commands.py` | `tool_execution_service.execute(tool_id, tool_call, context)` | `--tool-id*` `--input*`（JSON 串）`--tenant-id*†` |
| 6 | `sisys agent instantiate` | 整合 | `_run_instantiate_cli`（agent_cli.py:2337；异步内核 `_instantiate` :773） | `agent_instantiation_use_case`（:3065，SINGLETON） | `--role*` |
| 7 | `sisys agent run-task` | 整合 | `_run_task_cli`（:883；内核 `_run_task` :852） | `agent_workflow_use_case`（:3178，SINGLETON） | `--agent-id*` `--task*` |
| 8 | `sisys plan generate` | 整合 | `_run_blm_plan_cli`（:966；内核 `_run_blm_planning` :922） | `blm_planning_use_case`（:3518，SINGLETON） | `--agent-id*` `--task*` `--plan-id` |
| 9 | `sisys plan report` | 整合 | `_run_report_generate_cli`（:1212；内核 `_run_report_generate` :1078，:1096 format dispatch） | `report_generation_use_case`（:3604）/ `pdf_report_generation_use_case`（:3708）——按 `--report-format` 分发 | `--plan-id*` `--report-format`（markdown\|pdf，缺省 markdown——OD-13）`--brand-template`（仅 pdf 合法） |
| 10 | `sisys plan trace-tree` | 整合 | `_run_trace_tree_cli`（:1694；内核 `_run_trace_tree` :1621） | `traceability_tree_use_case`（:2059，SINGLETON） | `--plan-id*` `--depth`（缺省全深度）`--stage`（可选过滤） |
| 11 | `sisys checkpoint list` | 整合 | `_run_checkpoint_list_cli`（:1521；内核 `_run_checkpoint_list` :1481） | `checkpoint_list_use_case`（:2524，SINGLETON） | `--plan-id*` |
| 12 | `sisys checkpoint recover` | 整合 | `_run_checkpoint_recover_cli`（:2221；双内核 `_run_checkpoint_recovery_view` :2087/`_run_checkpoint_recover` :2099） | `checkpoint_recovery_use_case`（:2508，裸跑评估）/ `checkpoint_recovery_execute_use_case`（:2536，`--yes` 执行） | `--plan-id*` `--checkpoint-no*` `--correction-type`/`--previous-value`/`--new-value`/`--applied-by`（四参成组）`--mode`（replay\|override）`--yes` `--confirmed-by` |
| 13 | `sisys archive query` | 新增 | 新写 `archive_commands.py` | `strategic_archive_service.query_archive(ArchiveQuery)`（:2399，SCOPED） | `--plan-id` `--archive-type` `--limit`（缺省 20）`--offset` `--tenant-id*†` |

**†租户/身份参数强制栏（校验层位=controller 守卫层，242 同位「守卫先于 bootstrap」）**：
- **租户消费型命令**（#1 upload/#2 search/#3 version list/#5 tool run/#13 archive query）：`--tenant-id` **非空守卫（双缺 242 fail-loud）**+ `SISYS_TENANT_ID` env 回退双通道（**R1-F13 定谳**：原「UUID 守卫（242）」钦定与全仓 TestTenant hex 前缀租户实态/端口 opaque str 契约/REST 面零校验矛盾——收窄为非空守卫，租户形态 UUID 化归 7-x 平台治理 deferred；#5 tool run 额外 UUID 转换——ExecutionContext 契约硬校验）。**`SISYS_TENANT_ID` 是本 Story 新引入 env 约定**（全仓 src/tests/configs 零命中亲验——非既有约定）。
- **租户可选命令**（#4 tool list）：`--tenant-id` 可选传入过滤（构造 ToolListQuery 时 str→UUID 转换）、缺省全租户视图。
- **非租户消费命令**（#6~#12 agent×2/plan×3/checkpoint×2）：不引入 `--tenant-id`（用例签名不收租户）。
- search 专属 `--collection` 缺省值 "documents"（配置派生默认名——真实消费方先例 blm_planning_service 构造期租户隔离装配）。

**version snapshot 存量保形注记**：存量 `document_commands.py` 含 `version snapshot` 子命令（不在 13 命令验收面）。处置=**一并 Typer 化保形挂载**（第 14 命令，存量生产代码零删除——理由：①Task 3「5 处 print 错误修正」横跨 snapshot handler（:120/:141/:144 三处）；②test_document_commands.py 存量 10 测试函数大半覆盖 snapshot（适配义务非删除）；③消除死代码）。验收断言锚 13 命令不变（多挂载不破断言）；snapshot 参数面：`--id*` `--tenant-id*†` `--user`（缺省 cli）`--description*`（原 default="" 改必填——空描述快照无审计语义，fail-loud 对齐）。

#### Task 0.2 参数语义冻结表（Annotated 类型别名逐命令签名注入——venv 实证命令尾随位置生效）

**三参数与格式参数注入层**（`src/interfaces/cli/formatters/params.py` 或 commands 共享模块定义类型别名，13+1 命令签名统一注入）：

```python
# 共享类型别名（命令级注入——app 级 callback 选项只能出现在子命令之前，
# 与尾随位置冲突（typer 0.24.2 venv 实证 exit 2），故逐命令签名注入）
# R1-F2：--format 值域解析层 Enum 化（typer 原生 Enum 注解自动渲染 choices
# 并在解析层拒绝非法值 exit 2——原裸 str 形态非法值静默落 pretty 真实执行）
class OutputFormat(str, enum.Enum):
    JSON = "json"
    TABLE = "table"
    PRETTY = "pretty"


FormatOption = Annotated[OutputFormat, typer.Option("--format", help="输出格式：json/table/pretty（缺省 pretty）")]
YesOption = Annotated[bool, typer.Option("--yes", help="非交互确认（对有确认门命令等价兼容入口 --confirm）")]
DryRunOption = Annotated[bool, typer.Option("--dry-run", help="仅校验与回显动作清单，不执行真实调用（client 语义）")]
MockOption = Annotated[bool, typer.Option("--mock", help="模拟执行：零副作用返回 mock 标记输出（输出恒为 JSON 信封——与 --format 无关，机器可读钦定）")]
```

| 参数 | 语义（冻结） |
|------|------|
| `--format json` | 单行紧凑 JSON（`ensure_ascii=False`）→ stdout 纯净；渲染源=controller 返回的 result（**禁经 `_print_*`**——OD-14）；进度/日志走 stderr |
| `--format table` | 两遍法动态列宽表格（`_print_checkpoint_summary_table` :1495-1518 先例形态） |
| `--format pretty`（缺省） | 既有形态（`_print_*` 人类可读中文多行）；整合 7 命令直调 `_run_*_cli` 薄壳 |
| `--yes` | 确认门命令（仅 checkpoint recover）等价兼容入口 `--confirm`；无门命令幂等接受（接受但不改变行为）；**Typer 面仅暴露 `--yes`** |
| `--dry-run` | **client 语义全局统一**（kubectl `--dry-run=client` 同构——OD-12）：守卫全执行（含校验失败真实报错 `[code]` stderr + exit 1）+动作清单回显+**零 resolve 零副作用**+exit 0；短路层=controller 内 `dry_run: bool = False` 参数分叉（守卫后、bootstrap 前） |
| `--mock` | 零副作用+`"mock": true` 信封+参数回显 echo+exit 0；**先过守卫**（非法参数 242 → exit 1 非 exit 0）；文件类参数回显含存在性预检提示 |
| 优先级 | `--dry-run` > `--mock` > `--yes`（并存时高优先级生效） |

**Typer dispatch 矩阵**（冻结——AC-3 验证标准钦定）：

| 传入 | 分发路径 |
|------|---------|
| `--mock` | 信封生成器（守卫→mock 信封+echo→exit 0） |
| `--dry-run` | controller(dry_run=True)→动作清单渲染（遵循 --format：json=data.actions 数组/pretty=清单文本/table=动作表）→exit 0 |
| 缺省（pretty） | pretty 直调 `_run_*_cli` 薄壳（零回归保证） |
| `--format json\|table` | controller result + formatter（stdout 纯净） |

**checkpoint recover help 三态文案**（Typer 面冻结；禁复用兼容入口「dry-run 影响评估」措辞）：
- 缺省=「输出恢复影响评估（不落记录/不发事件/不应用修正——评估模式）」
- `--yes`=「确认执行恢复（应用修正+落恢复记录+发布事件）」
- `--dry-run`=「快速回显将执行的动作清单（零服务调用）」

**`--dry-run` 逐命令动作清单**（冻结——回显内容语义）：
| 命令 | 动作清单内容 |
|------|------------|
| document upload | 「将上传文件 {filename}（{size}B）至租户 {tenant_id}，业务域 {business_domain}」 |
| document search | 「将在 collection {collection} 执行混合检索：query={query!r} limit={limit}」 |
| version list/snapshot | 「将查询/创建文档 {document_id} 版本快照（租户 {tenant_id}）」 |
| tool list | 「将查询工具元数据清单（category={category} tenant={tenant_id}）」 |
| tool run | 工具名+入参回显+工具 Schema 摘要+「将执行」语义（Task 3.7 重构步钦定） |
| agent instantiate | 「将实例化 {role} 角色 Agent」 |
| agent run-task | 「将派发任务至 Agent {agent_id}: {task!r}」 |
| plan generate | 「将执行 BLM 规划（Agent {agent_id}，plan_id={plan_id or 自动生成}）」 |
| plan report | **产物写入型**（report_generation_service 双写 L0 文件+L2 PG）：「将生成 {report_format} 报告并写 L0/L2（plan_id={plan_id}）」 |
| plan trace-tree | 「将查询追溯树（plan_id={plan_id} depth={depth}）」 |
| checkpoint list | 「将查询 Checkpoint 清单（plan_id={plan_id}）」 |
| checkpoint recover | **清单分支随 `--yes` 切换**：无 `--yes` 列评估态动作[输出影响评估]；带 `--yes` 列执行态动作[应用修正+落恢复记录+发布事件]；**`--mode` 值域校验前移至守卫段**（现状 :2303-2306 在 confirm 分支内——dry-run 短路会跳过致非法 mode exit 0） |
| archive query | 「将查询战略归档（plan_id={plan_id} archive_type={archive_type} limit={limit}）」 |

**读命令退化态**：list/search/query/trace-tree 的 `--dry-run` = 守卫校验+动作回显（统一 Agent 契约面）。

#### Task 0.3 输出信封契约冻结

**json 信封骨架**（`--format json` 时 stdout 唯一内容）：

```json
{"ok": true, "command": "sisys document upload", "data": {...}, "mock": false}
```

- `--mock` 时：`{"ok": true, "command": "...", "data": {}, "mock": true, "echo": {"参数名": "回显值", ...}}`
- 错误形态：`[EXCEPTION_code] message` 单行 stderr + exit 1（**不进信封**——沿用定式）
- **data 载荷白名单原则**：CLI 视图 dict 最小字段（REST DTO 白名单同构），逐命令冻结如下（单测/e2e/验收三方断言同源本表防漂移）：

| 命令 | data 白名单（最小字段集） |
|------|--------------------------|
| document upload | document_id / filename / tenant_id / document_type / status |
| document search | total / results[]（document_id / score / collection / snippet） |
| version list | document_id / versions[]（version / created_by / created_at / diff_summary） |
| version snapshot | snapshot_id / document_id / version / created_by |
| tool list | total / tools[]（tool_id / name / category / status——枚举字段以 .value 形态入信封，R1-F4） |
| tool run | tool_id / status / output（输出摘要——status 枚举 .value，R1-F4） |
| agent instantiate | agent_id / role |
| agent run-task | agent_id / workflow_status / task |
| plan generate | plan_id / degraded_steps（降级步骤计数——R1-D2 表修：实现形态比 stage_status 全量 dict 更符合最小字段白名单原则） |
| plan report | **report_path / report_format**（产物路径+格式字段——AC-2 钦定断言）+ plan_id |
| plan trace-tree | plan_id / total / build_degraded（R1-D2 表修：计数+降级标记——同上最小字段原则；`--depth` 缺省 4=全深度 R1-F5/F10 值域 1-4） |
| checkpoint list | plan_id / checkpoints[]（checkpoint_no / stage / completed / sync_status） |
| checkpoint recover（评估态） | plan_id / checkpoint_no / assessment{recommended_mode(.value)/subsequent_count}（R1-F7 对表收口） |
| checkpoint recover（执行态） | plan_id / checkpoint_no / recovery{mode(.value)/corrected/new_state_version/affected_count}（R1-F7 对表收口——outcome 实际字段名） |
| archive query | total / archives[]（archive_id / plan_id / archive_type / created_at） |

#### Task 0.4 七条留项处置对表（deferred-work.md 写入计划——行数守恒）

处置动作两形态（6-11 Task 0.7 先例 + L403 RESOLVED 划线既有形态亲验）：
- **核销（划线）**：标题与描述 `~~划线~~` + `**RESOLVED（2026-11-13，Story 7-1 核销——xx）**：处置说明` + 原四要素与历史注记保留；
- **顺延（注记追加）**：行尾追加 `**7-1 Task 0 处置（2026-11-13，OD-n）**：顺延 7-2——理由` 注记。

| # | 台账锚位 | 处置 | 落账时点 |
|---|---------|------|---------|
| 1 | L330（6.1-DF5） | 顺延注记（7-2 REST GET /plans/{id} 立项时接线） | Task 0.4 |
| 2 | L331（6.1-DF6） | 顺延注记（CLI 一次性进程三项均不可达） | Task 0.4 |
| 3 | L362（6.4-DF2） | **核销划线**（Task 3 循环 C 集成场景+接线守卫断言承载——证据=集成测试文件路径+场景名） | Task 3.10 |
| 4 | L369（6.5a-DF1） | 顺延注记（CLI 面零 REST 契约） | Task 0.4 |
| 5 | L370（6.5a-DF2） | 顺延注记（义务随 7-2 维持——唯一「必须」义务约束 REST 面） | Task 0.4 |
| 6 | L402（6.8-R1-DF1） | **核销划线**（Task 4 循环 A：OD-7 入口显式 load_dotenv override=False + SISYS_USE_TEST_PORTS=1 跳过守卫） | Task 4.4 |
| 7 | L409（6.9-R1-DF1） | **核销划线**（Task 2 循环 A：OD-8 canonical 归一——共享守卫抽取+9 处调用点+归一传 str(UUID)） | Task 2.4 |
| 8 | L254（5-7 R1-DF6） | **核销划线**（Task 4 循环 B：OD-9 signal handler——Phoenix 同步直调+run_coroutine_threadsafe 调度 `_close_connection_pools`；组合根 shutdown() 连接池段 resolve 非 peek 亲验不合 peek 语义→按故事钦定独立调度分支） | Task 4.7 |
| 9 | L158（D1 治理注记） | 知悉消费零动账（cli_main.py 统一入口=「entrypoints 层内合并」钦定执行；Task 7.5 终核引用核对） | Task 7.5 |
| 10 | L125/L129（三向定夺） | 顺延注记（OD-11：CLI 入口≠API 入口字面甄别） | Task 0.4 |

#### Task 0.8 链路接线断言清单（Epic 4 回顾行动项 7.1-1——架构测试 Task 6.5 承载）

1. `sisys` console_script 装配可达：pyproject **`sisys` 条目双段一致**（[project.scripts]+[tool.poetry.scripts] 均 `sisys = "src.entrypoints.cli_main:main"`；断言收窄为 sisys 条目——现状两段不对称 crawler 仅 [project.scripts]）+ import 链 `src.entrypoints.cli_main:main` 存在；
2. 13 命令 resolve 目标端口全部组合根在册（消费对账表 Task 0.1 逐条——15 注册名 :1189~:3708 亲验在册）；6.4-DF2 核销加 `resolve("session_factory")`（:225）接线守卫断言；
3. 统一入口 bootstrap 接线全链：load_dotenv → bootstrap 惰性（`_ensure_bootstrapped`）→ 命令执行 → 连接池关闭（`_close_connection_pools` import 复用 agent_cli——钦定非复制）；
4. `sisys-agent` 兼容入口同链复用（argparse 前端保留；202 单测全绿零回归）。

#### Task 0.6 逐场景红锚符号表（按时点分段——R3-07）

| 场景组 | Task 0 时点预期红形态 |
|--------|----------------------|
| CLI 统一入口直调类（--help/挂载断言） | 步骤内延迟 import `src.entrypoints.cli_main` → **ModuleNotFoundError**（非 exit 2——统一入口整体不存在） |
| Task 1 骨架就位后命令未挂载类 | typer 无此命令 → **exit 2**（Usage error）→ SystemExit 捕获断言 |
| formatter 类 | `src.interfaces.cli.formatters` 延迟 import → ModuleNotFoundError / 属性错误 |
| mock 信封断言类 | 输出不可 json.loads → json.JSONDecodeError（或按形态 AttributeError） |
| 既有命令（sisys-agent）类 | 兼容入口在位——红锚为**行为升级断言**（UUID 归一大写命中——现状空态 exit 0 → 断言失败 AssertionError） |
| 完成清单类 | `_COMPLETION_SRC_FILES` 文件不存在 AssertionError（6-11 S14/consultant_view S12 形态） |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` Epic 7 Story 7.1 提取（含 FR-IF-01 七原则验收嵌入）
- [x] 架构约束从 `architecture.md`/`interface-design.md` 提取（§13.5 目录/§4 命令规范/§4.4/§4.5 参数）
- [x] 前一个故事学习经验整合（6-11 教训 20 条提炼应用）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（Task 0 冻结表 + 7 Task TDD 循环 + 变异实证）
- [x] 项目结构对齐统一规范（D1 方案 A + §13.5 规划位）
- [x] Epic 6 回顾行动项 1 承载（锚定义务清单十行对表——七条留项 + R1-DF6 + L158 + 三向定夺）
- [x] 口径不一致定谳（P95 四处/P7 双版本/P5 废弃文案——OD-2/3/4 入档）

**Task 0 实施记录（dev-story 2026-11-13）:**

- **调研基线（四路并行 Agent + 主会话亲验双轨）**：①agent_cli 深度结构（19 子命令表/7 整合命令五步定式/UUID 守卫 9 处/recover 双分支/公共设施）；②interfaces/cli 现状与测试基线（存量 document_commands 186 行形态/test_agent_cli.py 195 函数 73 处 monkeypatch 面/12 架构测试文件锚形态）；③组合根 15 端口注册与消费先例（含**组合根 shutdown() 连接池段 resolve 非 peek 亲验**——Task 4 按钦定「不一致则独立调度」分支）；④测试模板与台账（R6 模板/三件套/_run_cli/完成清单/xdist_group/P95 先例/deferred-work 锚位零漂移）。主会话亲验：202 基线全绿（15.08s）、9 处 UUID 守卫行号 9/9 全中、pyproject 双段不对称、Typer 0.24.2 venv 双实证（**三级结构命令级 Annotated 尾随 Option exit 0 可行**——补充确认故事 AC-3 钦定；callback 级尾随 exit 2 复现）。
- **执行函数实名修正**：agent instantiate=`_run_instantiate_cli`（:2337）/agent run-task=`_run_task_cli`（:883）——故事端口表 :773/:852 为异步内核行号，冻结表已按 CLI 执行函数实名登记。
- **四张冻结表落档**：命令面 13 命令（+version snapshot 存量保形挂载第 14 命令——Task 3「5 处错误修正」横跨 snapshot handler 背书）/参数语义（dispatch 矩阵+recover help 三态+dry-run 逐命令动作清单）/输出信封（data 白名单 14 命令）/留项处置对表（10 行）。
- **红阶段验证**：38 场景全红（38 failed in 12.28s）——红形态 `ImportError: cannot import name 'cli_main'`（背景步骤延迟 import 触发，与符号表「Task 0 时点统一入口整体不存在→ModuleNotFoundError 形态」吻合——ImportError 为其父类具体呈现）。
- **deferred-work 落账**：6 处顺延注记实际动账（L330/L331/L369/L370/L125/L129——行数守恒 467 行）；4 条核销划线（L362/L402/L409/L254）留对应 Task 实施时落。
- **验收场景规模**：38 场景 = AC-1×9 + AC-2×5 + AC-3×7 + AC-4×4 + AC-5×4 + AC-6×4 + AC-7×2 + AC-8×2 + 1 信号联动场景；S 编号仅 docstring 索引表（禁泄入场景名/函数名）。

**Task 1~5 阶段性实施记录（dev-story 2026-11-13，上下文压缩前收束）:**

- **Task 1 完成**（入口骨架+formatter 三件）：cli_main（get_app 组装+main int 契约）/interfaces/cli/main（三模块）/cli_commands（三组占位）/pyproject 双段；formatter 四件（json/table/pretty+分发器）；18+17 单测全绿；变异实证（agent 组注册移除→3 红→还原绿）。
- **Task 2 完成**（UUID 归一+Agent 参数面+7 命令整合）：`_validate_plan_uuid` 共享守卫（9 处内联收敛）+归一传 canonical（206 passed 零回归）；dispatch.py（四路分发+Annotated 别名+invoke_command 适配——**venv 实证：Typer 命令函数返回 int 会 exit 2，须 raise typer.Exit**）；7 个 controller 抽取（agent_cli 留驻——202 单测 patch 面不破）；cli_commands 7 命令实装（to_view 白名单转换）；架构测试 1121 全绿零漂移。
- **Task 3 完成**（document/tool/archive+集成）：document_commands Typer 化（upload 加 --source/--license 必填——REQUIRED_METADATA_FIELDS 五键契约亲验；version snapshot+list 保形挂载第 14 命令）；tool_commands（list 同步端口+run execute 契约）；archive_commands（query ArchiveQuery）；**dispatch 三钩子注入机制**（bootstrap/cleanup/session_scope——interfaces 零 import 违规，OD-16 规避）；集成测试 4 场景（upload 真实读回/tool list/archive query 无 session 上下文=6.4-DF2 核销/session_factory 接线守卫）；三参数无豁免矩阵复验（42 参数化）；**CLI 直调跨 loop 族修复**（预置与直调分 loop→SCOPED 池驱逐双清纪律）。
- **Task 4 完成**（load_dotenv+SIGTERM）：agent_cli.load_env（单函数双入口复用——Path(__file__) 上溯+override=False+TEST_PORTS 守卫）；cli_main 信号 handler（Phoenix 同步直调+run_coroutine_threadsafe 调度关池协程尾部 os._exit——**handler 内同步等待会死锁**（loop 与 handler 同主线程）定谳；组合根 shutdown() 连接池段 resolve 非 peek 亲验→独立调度分支）；**register_signal_handlers 测试形态守卫**（TEST_PORTS=1 跳过——注册劫持 pytest/xdist worker 信号致 execnet 挂起实证）；10 单测全绿；L402/L254 双划线核销。
- **Task 5 进行中**（验收 32/38 绿 + e2e/性能未完成）：验收场景稳定性修复九轮——①同文本双 @then 绑定→pytest-bdd fixture 死锁（根因级发现）；②Fake LLM 豁免装配链移植（checkpoint 预置——CreateCheckpointUseCase 压缩链 LLM 依赖，_CORPUS_TEXTS 语料+Fake embedding 6-3 同款）；③预置链资源收尾（session/engine 跨 loop greenlet 族）；④CP-1 格式/document_type 值域/metadata 五键/archive 签名逐项对齐；⑤请求路径仓储测试侧 session_context 供给。**剩余 6 失败**：S40 P95/S41 并发（Task 5 本体——需长时间真实采样）、S13 report（BLM 预置链）、S05 search（查询侧 embedding 环境依赖——探活 skip 已加但本机仍触发）、S43 completion（Task 6 文件依赖）。
- **下一步**（压缩后续接）：①Task 5 循环 A 性能/并发场景真实采样跑通；②Task 5 循环 B e2e 首文件（tests/e2e/test_cli_e2e.py）；③Task 6 架构验证测试；④Task 7 收尾；⑤S13/S05 两场景环境面复核。

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/7-1-cli-command-interface.md`
- `src/entrypoints/cli_main.py` - 统一入口（get_app 组装+main int 契约+load_env 挂载+信号 handler）
- `src/entrypoints/cli_commands.py` - 7 整合命令 Typer 模块（agent/plan/checkpoint——OD-16 层位）
- `src/interfaces/cli/main.py` - Typer app 骨架（document/tool/archive 三模块挂载）
- `src/interfaces/cli/dispatch.py` - 四路分发+共享参数别名+三钩子注入（bootstrap/cleanup/session_scope）
- `src/interfaces/cli/formatters/__init__.py` / `json_formatter.py` / `table_formatter.py` / `pretty_formatter.py` - 格式化器四件
- `src/interfaces/cli/commands/tool_commands.py` / `archive_commands.py` - tool/archive 新命令
- `tests/unit/interfaces/cli/test_cli_unified_entry.py` - 统一入口+整合命令+三参数矩阵单测
- `tests/unit/interfaces/cli/test_cli_formatters.py` - formatter 三态单测
- `tests/unit/interfaces/cli/test_cli_agent_params.py` - Agent 参数面单测（脚手架）
- `tests/unit/interfaces/cli/test_cli_tool_commands.py` / `test_cli_archive_commands.py` - tool/archive 单测
- `tests/unit/entrypoints/test_cli_entry_standardization.py` - load_dotenv+SIGTERM 单测
- `tests/unit/architecture/test_arch_cli_unified_entry.py` - 架构验证（七原则/import 方向/对账）
- `tests/integration/test_integration_cli_unified_entry.py` - 集成真实服务全链（6.4-DF2 核销）
- `tests/acceptance/test_acceptance_cli_command_interface.feature` - 验收 Gherkin（38 场景）
- `tests/acceptance/test_acceptance_cli_command_interface.py` - 验收 BDD 步骤实现
- `tests/e2e/test_cli_e2e.py` - E2E 冒烟（13+1 命令全覆盖双通道）

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/entrypoints/cli_main.py` - 统一入口
- `src/entrypoints/cli_commands.py` - 7 整合命令 Typer 模块（agent/plan/checkpoint 三组子 app——OD-16 层位）
- `src/interfaces/cli/main.py` - Typer app 骨架（document/tool/archive 挂载 + cli_main 注册整合组）
- `src/interfaces/cli/commands/tool_commands.py` / `archive_commands.py` - 新命令面（domain 层 Resolver 先例）
- `src/interfaces/cli/formatters/__init__.py` / `json_formatter.py` / `table_formatter.py` / `pretty_formatter.py` - 格式化器
- `tests/unit/interfaces/cli/test_cli_unified_entry.py` / `test_cli_formatters.py` / `test_cli_agent_params.py` / `test_cli_tool_commands.py` / `test_cli_archive_commands.py` - 单元测试
- `tests/unit/entrypoints/test_cli_entry_standardization.py` - 入口标准化单测
- `tests/unit/architecture/test_arch_cli_unified_entry.py` - 架构验证
- `tests/integration/test_integration_cli_unified_entry.py` - 集成测试
- `tests/acceptance/test_acceptance_cli_command_interface.feature` / `.py` - 验收测试（R6 模板风格）
- `tests/e2e/test_cli_e2e.py` - E2E 冒烟（目录首个测试文件）

**待修改的文件/To Be Modified:**
- `pyproject.toml` - console_script 双段加 `sisys`（已改）
- `src/entrypoints/agent_cli.py` - UUID 守卫归一（`_validate_plan_uuid` 共享守卫 9 处收敛）/ `load_env`（双入口复用单函数）/ main() 挂载（已改）
- `src/interfaces/cli/commands/document_commands.py` - Typer 化重构（upload/search/version snapshot+list——已改）
- `src/interfaces/cli/__init__.py` - 注记更新为已接线形态（已改）
- `tests/unit/interfaces/cli/test_agent_cli.py` / `test_document_commands.py` - 扩展（归一 4 测试 / Typer 化适配重写）（已改）
- `scripts/check_coverage_gates.py` - interfaces ≥85% 门禁条目固化（已改）
- `_bmad-output/implementation-artifacts/deferred-work.md` - 处置注记与划线（行数守恒 467——6 处顺延注记+4 处核销划线全部落账）

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 7.1 |
| **Story Key** | 7-1-cli-command-interface |
| **File** | `_bmad-output/implementation-artifacts/stories/7-1-cli-command-interface.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 7: 多触点用户界面与 API 集成 |
| **价值组** | 多触点操作与监控能力（用户可以通过 CLI/API/仪表盘操作系统） |
| **优先级** | P0-1 |
| **覆盖 FR** | FR-UI-01（CLI 接口）+ FR-IF-01（CLI 七原则合规）+ NFR-IF-01（CLI 响应延迟——**prd 语义**；epics 同号条目为决策舱加载<2s 属同名异义，本 Story 不覆盖） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0~7）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-8）
3. [x] Architecture constraints extracted 架构约束已提取（六边形/D1 方案 A/五步定式/双前端）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（6-11 二十条提炼）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。
> **编号规则**：R<轮>-<序号>（本文档审查周期专用；与 deferred-work 台账 DF 编号、先例 Story 的 D-1/OD 编号空间互不相干）。

**Round 1（2026-11-13，D1 四路调研 + D2 双评审 + 主会话定谳，P0×5 + P1×15 + P2/P3 簇）：**

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R1-01 | Task 2「整合 6 命令」与循环 C 枚举 7 命令、13 命令构成自相矛盾（6 处） | P0 | 统一改 7 命令（7+6=13 闭合）；DoD 时序同步（整合 7+参数层全局可用） |
| R1-02 | checkpoint recover 既有缺省评估模式（resolve :2093，help 自称 dry-run）与 AC-3 全局 --dry-run（零 resolve）同名不同义 | P0 | 新增 OD-12：client 语义全局统一（kubectl --dry-run=client 同构）；recover 裸跑保留评估缺省态；AC-3/端口表/Subtask 0.2/2.5 同步 |
| R1-03 | plan report 既有 `--format markdown\|pdf` choices（:356-360）与 AC-2 `--format json/table/pretty` 同 flag 双语义互斥 | P0 | 新增 OD-13：内容格式拆 `--report-format`；兼容入口 argparse 语义不变；AC-2 验证标准补双参数并存断言 |
| R1-04 | DC-3「包装既有执行函数→result→formatter」字面不可满足（`_run_*_cli` 返回 int、`_print_*` 内嵌） | P0 | DC-3 扩写+新增 OD-14：controller 抽取路径（原函数退化薄壳零行为变化）；json/table 禁经 _print_*；§13.5 controllers/ 层偏离声明 |
| R1-05 | AC-7 并发「gather/子进程任证其一」——gather 聚合 CLI main() 结构性不可行（asyncio.run 嵌套禁律+SINGLETON 跨循环族） | P0 | 新增 OD-15：定谳 10 独立子进程（asyncio.create_subprocess_exec） |
| R1-06 | tool list 端口映射错误：tool_version_service 无「列工具」能力（全方法按单 tool_id 收窄） | P1 | 改 tool_execution_service.list_tools_metadata(ToolListQuery)（ports:77/services:177）；Task 0.1 增「能力级对账」纪律 |
| R1-07 | Typer app 级 callback 注入三参数与尾随参数位置冲突（typer 0.24 venv 实证 exit 2） | P1 | 改共享 Annotated[typer.Option] 类型别名逐命令签名注入；callback 仅承载 --version 类 |
| R1-08 | Task 4.1 in-process 红锚不可达（conftest session autouse _bootstrap_once 填充 registry 即短路） | P1 | 改纯语义单测（tmp_path .env+键注入/override 断言，删 load_dotenv 即红）；裸跑复现归 subprocess/e2e |
| R1-09 | 租户/身份/collection 参数面整体缺失（upload 必填 tenant_id/uploaded_by、search 必填 collection 与 AC-1 示例冲突） | P1 | Task 0.1 增「租户/身份参数强制栏」：--tenant-id（UUID 守卫+SISYS_TENANT_ID env 回退双通道 fail-loud）+--uploaded-by+--collection；AC-1 示例注记 |
| R1-10 | 「195 单测」实为 202（8 处传播） | P1 | 全文 8 处同步 202 |
| R1-11 | 「12 个架构测试」单位错（12=文件数；函数 16 个/test_arch_* 8 个）（4 处） | P1 | 统一「12 架构测试文件（16 测试函数）」 |
| R1-12 | agent_cli.py:395 锚点错误（禁全量 shutdown 注记实在 :747-748、peek :766）（3 处，含调研漏掉的 Task 4 :559） | P1 | 三处同步 :747-748 |
| R1-13 | 消费端口表 :1565 锚点错指 checkpoint-show（recover 评估 resolve 实在 :2093） | P1 | 端口表改 :2093/:2105 并随 OD-12 定稿注记 |
| R1-14 | R6 模板「三件套」错误归属（该文件为旧代无三件套）+「6-11 :883-899 _run_cli helper」引散文段非代码 | P1 | 三件套先例锚 white_label_report.py:154/:168/:192；helper 先例锚 consultant_view.py:461-480（3 处同步） |
| R1-15 | 追溯矩阵 AC-7 行错挂集成测试（AC-7 验证标准无此面；Task 5 悬空）+ 测试分类表「Task 3/5」 | P1 | 统一挂 AC-1/Task 3 |
| R1-16 | Typer「0.24+」表述偏宽（^0.24.0 上界 <0.25）+ business_domain 顶层参数误导 + contracts 1593 实为 1568 | P2 | 措辞/注记/数字修正（端口表 upload 行映射注记） |
| R1-17 | P7「复杂工具各 ≥1」判定标准不存在且 ToolMetadata 无 input_examples 字段 | P2 | 断言升级 23/23 全量（载体=SKILL.md `## 8.` 章节，现状全具备各 1 条） |
| R1-18 | AC-7 采样「agent instantiate dry-run」计时空洞（零 resolve 只测解析） | P2 | 改真执行+租户自清理（OD-3 附注） |
| R1-19 | load_dotenv 进程内泄漏（.env 被 git 追踪，非端口键污染同 worker） | P2 | SISYS_USE_TEST_PORTS=1 跳过守卫（AC-6/Task 4） |
| R1-20 | E2E≥80% 无分母 + CI 无 tests/e2e 执行位；interfaces≥85% 无门禁脚本载体 | P2 | 声明式收敛 13/13 + deferred 注记；Task 7 补门禁脚本条目说明 |
| R1-21 | 六模块矩阵「plan 6 命令」实为 4、视图/品牌无归落（16≠19）；「其余 8 命令」实为 12；:1078「OD-11 分发表」编号误标 | P2 | 矩阵修正+全量归落注（19=6+4+4+3+2）；DC-2 两处改 12；:1078 行改 def/dispatch 实锚 |
| R1-22 | instantiate 唯一直调 bootstrap() 不走幂等守卫（五步定式概括失真）；plan_id 守卫 9 处内联非「单点升级」 | P2 | 端口表/隔离表/设计约束三处例外注记；OD-8/Subtask 2.2 波及面校准 |
| R1-23 | 锚表 #9 对已 RESOLVED 条目含动账动作；双清函数来源形态未注明；勿仿注记位置错标文件头 | P2/P3 | #9 改知悉消费零动账；双清/三件套注明私有定义复刻形态；__init__.py:5 实位 |
| R1-24 | NFR-IF-01 prd/epics 同号不同义未声明；「两级退化」非 §4.2 明文；Epic 7 节行号范围过窄；Subtask 3.7 措辞；:235 文件限定；e2e 双通道/服务可用性 skip；cli_main __main__ 守卫；OD-5 补 --yes 必填偏离 | P3 | 逐项措辞/注记修正（**勘误**：「两级退化」措辞与 Epic 7 节行号两子项 R1 实未落地，R2 补修——A-3/A-4） |

**Round 2（2026-11-13，双 Agent 回归核查+组合可达性 + 主会话 importlinter 定谳，P0×1 + P1×4 + P2×10 + P3×3 + 回归漏网勘误）：**

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R2-01 | interfaces/cli/commands 整合命令 import agent_cli → composition_root → infrastructure 传导链重触发 import-linter 契约（.importlinter:74 注记自证历史清零——CI 必红） | P0 | 新增 OD-16 层位钦定：7 整合命令 Typer 模块落 src/entrypoints/cli_commands.py（层内互引合法）；interfaces/cli 保留新命令+formatters+app 骨架；结构树/分层落位/循环 C/文件清单/Task 6.4 断言面（interfaces AST 断言禁 import entrypoints+composition_root）五处同步；「_ensure_bootstrapped 提公共化或 import 复用——实施定夺」改为钦定 import 复用（公共化目标模块无论落哪层均触发同链） |
| R2-02 | dry-run 短路层结构落点未钦定（Typer 层短路会跳过守卫致 AC-3 守卫锚失守；callback 承载短路层与 Annotated 注入自相矛盾）+ dispatch 矩阵/recover 双分支形态/三参数优先级/mock×守卫全未定义 | P1 | AC-3 验证标准增「短路层结构钦定」条：controller 内 dry_run 参数分叉（守卫后 bootstrap 前）+四行 dispatch 矩阵+优先级 --dry-run>--mock>--yes+mock 先过守卫+recover 双分支按 confirm 分叉+守卫失败 exit 1 澄清；Subtask 0.2/2.6 同步；callback 承载清单修正（A-9） |
| R2-03 | Task 2 循环 B 三参数测试时命令未挂载（红因错误）+ 循环顺序未声明 + controller/守卫留驻模块未声明（202 单测 73 处 monkeypatch 模块级属性实测前提） | P1 | Task 2 头部增「实施顺序 A→B→C」+「循环 B 测试对=本地脚手架命令+Task 3 DoD 复验点」+「留驻 agent_cli 模块」+「循环 A 测试经 main(argv) 行为面」四声明 |
| R2-04 | 租户口径互斥（AC-1「全命令统一必填」vs Task 0.1「逐命令钦定」；实测 7 命令用例签名不收租户） | P1 | 合一为「租户消费型命令（6 命令清单）必填双通道 fail-loud；非租户消费命令不引入」；存量 --tenant 改名 --tenant-id 注记 |
| R2-05 | OD-14 归宿「Task 6.4 架构断言锚」虚指（6.4 无 controller 相关断言）+ OD-12 归宿「Subtask 2.5」半虚指 | P1 | Subtask 6.4 增「dispatch 层 json/table 态零 _print_* AST 断言（OD-14 升架构位）」+ interfaces 禁 import entrypoints/composition_root；Subtask 2.5 补 recover 双态两用例；Task 1 循环 B 红面 dispatch 断言改分层时点注记（命令级归循环 C/6.4） |
| R2-06 | R1 修复回归漏网：AC-5「controller/render 分离」术语残留 1 处（A-1）；Typer「0.24+」措辞未修（A-2）；commands/__init__.py 误标 ★新建（A-7——R1 引入新错误，文件实已存在）；「目录首个文件」×3（A-10——tests/e2e 已有 __init__.py） | P1 | 逐处修正；R1-24 两子项（两级退化措辞/Epic 7 节行号 L2565-2996）补修+修复表勘误注记 |
| R2-07 | 追溯矩阵集成测试行挂 AC-1 但 AC-1 验证标准无对应面（弱错挂——R1-15 搬移未闭合） | P2 | AC-1 验证标准补第 5 条「真实服务全链集成测试通过」承接 |
| R2-08 | plan report 误分类读命令（实测 report_generation_service 双写 L0 文件+L2 PG） | P2 | 读命令清单剔除 report；补「产物写入型——动作清单含格式与落盘目标」注记 |
| R2-09 | AC-2 验证标准④只有解析断言缺输出语义断言（信封包产物） | P2 | 补「json 信封 data 含报告产物路径与 report_format 字段」断言 |
| R2-10 | Task 6.5 双段一致断言若写全段字典相等必红（现状 crawler 两段不对称） | P2 | 断言收窄为 sisys 条目双段一致（AC-1 验证标准①同步） |
| R2-11 | xdist_group 挂组依据「read 侧」不精确（P95 场景实因 instantiate 写入挂组）+ 并发命令集未钦定 | P2 | 按场景注明依据；并发命令集钦定混合面（写入 5+读 5） |
| R2-12 | recover help 三态文案未冻结（兼容入口「dry-run 影响评估」同词异义横跨两入口） | P2 | Typer 面三态文案模板入 AC-3/Subtask 0.2；禁复用兼容入口措辞；argparse 侧原样保留注记 |
| R2-13 | e2e 运行命令配套缺口（四目录不含 e2e，无可复现调用面）+ 13/13 冒烟形态未钦定 + which 可用时双通道执行未述 | P2/P3 | 验证要求节补 e2e 门禁命令；冒烟形态三段式（--help 全集+只读子集+写命令 --dry-run）；双通道均执行注记 |
| R2-14 | Typer 面 --confirm/--yes 暴露面未钦定（双旗标并存 vs 仅 --yes） | P3 | 钦定 Typer 面仅 --yes（--confirm 兼容入口专属），等价性断言跨入口 |

**Round 3（2026-11-13，单深度推演 Agent——AC 可满足性逐条+Task 0→7 依赖干跑+5 长链，P0×1 + P1×3 + P2×4 + P3×4）：**

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R3-01 | Task 1 绿步「main.py 六模块 add_typer 挂载+各模块 *_commands.py 占位」与 OD-16 结构直接矛盾（main.py 只挂三模块；占位未覆盖 entrypoints 侧 cli_commands.py；六模块断言对象未钦定——裸 app 恒不可绿） | P0 | 绿步重写：main.py 三模块 + cli_commands.py 三组占位子 app（Task 1 建骨架 Task 2 填命令）+ cli_main 程序化注册两组；断言对象钦定=cli_main 组装后完整 app（暴露模块级 importable app/assembly 函数） |
| R3-02 | AC-7 并发命令集含 plan generate——子进程无法接收进程内 AsyncMock LLM 替身（既有验收 Fake LLM 唯一豁免形态），真 LLM=Key 依赖+非确定性，「零失败」结构性不可达；seeded 数据传子进程通道未定义 | P1 | 命令集重组为无 LLM 依赖混合面（写 5=upload×3+instantiate×2；读 5=tool list/search/checkpoint list/archive query/version list）；seeded 数据经 argv 直传 + SISYS_TENANT_ID env 同刻可用 |
| R3-03 | SIGTERM 机制与验收载体双未定义：`_close_connection_pools` 是 async 而 sync handler 不可 await（handler 内 asyncio.run 必抛 RuntimeError）；`loop.add_signal_handler` 需运行中 loop（dispatch 前无 loop） | P1 | 机制钦定：signal.signal 同步 handler 内 PhoenixTracer.shutdown() 同步直调（:179）+ asyncio.get_running_loop→run_coroutine_threadsafe 调度池关闭；复用钦定组合根 shutdown()（:3832 注释明示为本缺口预留）；载体钦定：handler 直调单测 + bootstrap 窗口 subprocess 冒烟（弱化断言注明） |
| R3-04 | test_document_commands.py 4 处既有断言必随 Task 3 行为修复而破（错误输出 stdout→stderr+定式 / --tenant 改名+无 default / patch 点漂移）而适配义务零声明 | P1 | Task 3 循环 A 绿步增「既有测试适配义务声明」（OD-10 行为修复背书，属义务非回归）——4 处逐点列明 |
| R3-05 | recover dry-run 动作清单三未定义：双分支措辞（评估态/执行态清单内容）/--mode 值域校验在 confirm 分支内 :2298（dry-run 短路跳过→非法 mode exit 0 与「守卫全执行」冲突）/dry-run×--format 输出形态 | P2 | AC-3 三钦定：清单随 --yes 位切换；--mode 校验前移守卫段；dry-run 遵循 --format（json=data.actions 数组） |
| R3-06 | json 信封 data 载荷形态未冻结（实体全字段 vs CLI 视图 dict——三方断言必漂移）；--tenant-id 校验层位未钦定；SISYS_TENANT_ID 系新引入约定未注明 | P2 | Task 0.3 补 data 白名单原则（CLI 视图 dict 最小字段，REST DTO 白名单同构）+逐命令冻结；Task 0.1 校验层位钦定 controller 守卫层（242 同位）+新引入 env 约定注记 |
| R3-07 | Task 0.7 红锚未按时点分段（Task 0 时点统一入口整体不存在=ModuleNotFoundError 非 exit 2） | P2 | 红锚表补时点分段（Task 0=ImportError；Task 1 后未挂载=exit 2） |
| R3-08 | tool run --dry-run 动作清单内容未冻结（与 --mock 回显区分度） | P2 | Task 3 循环 B 重构步补一句钦定（工具名+入参回显+Schema 摘要+「将执行」语义） |
| R3-09 | P3 簇：Task 7 收尾红阶段仪式性未声明；AC-2「既有形态兼容」对 6 新命令无基准（弱断言）；trace-tree 采样数据预置链未点名；整合命令短旗标保留面未进冻结表 | P3 | Task 7 红面仪式性声明（6-11 S14 同款）；AC-2③ 弱断言如实注记；trace-tree 预置先例锚 white_label_report.py:799；短旗标归 Task 0.1 冻结表逐命令栏 |

**Round 4（纯验证轮，零新发现零提交）：** 七维度快扫全过——结构完整（8 一级/38 二级节/AC-8/Task-8/OD-16 行/修复表 47 行=R1 24+R2 14+R3 9 精确吻合）；cli_commands.py 六处落位一致；旧值仅存修复表历史记录；关键术语自洽无新旧并存。按纪律不强行造提交。

**Round 5（2026-11-13，独立终审 Agent 六节取证——不轻信自报）：**

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| R5-01 | Task 2 头部声称「Task 3 DoD 增三参数无豁免矩阵复验点」但 Task 3 DoD 无该条目（修复表自报与文档现实脱钩——R2-03 承接位虚指） | P1 | Task 3 DoD 增该行清偿 |
| R5-02 | :2298 锚位微偏（--mode 值域转换实在 :2303-2306 RecoveryMode(mode_raw)；:2298 是审批人守卫 print 行——论断实质不变） | P3 | 锚位更正 :2303-2306 |
| R5-03 | 租户二分枚举漏 tool list（ToolListQuery.tenant_id Optional 落两桶之外） | P3 | 增「租户可选命令」第三桶（AC-1 注记+Task 0.1 租户栏同步） |

### 收敛声明（R5 终审 2026-11-13）

1. **周期概览**：五轮循环——R1 修复 24 项（P0×5）/R2 修复 14 项（P0×1）/R3 修复 9 行 12 项（P0×1）/R4 纯验证零发现/R5 终审清偿 P1×1+P3×3；版本链 v1.0.0→v1.1.0→v1.2.0→v1.3.0→v1.3.1；三轮修复 commit（f4d3a956/1a4ee807/b6eada55）均单文件动账、无游离提交。
2. **关键定谳**：OD-12 `--dry-run`=client 语义全局统一（recover 裸跑保留评估缺省态）；OD-13 报告内容格式拆 `--report-format`；OD-14 controller 抽取路径（json/table 禁经 `_print_*`）；OD-15 并发=10 独立子进程（无 LLM 混合面）；OD-16 整合命令 Typer 层落 entrypoints/cli_commands.py（import-linter 传导链规避）。
3. **R5 验证面**：10 项双向抽验+约 40 个先例锚全中；202/1568 收集数、12 文件 16 架构函数、23/23 SKILL `## 8.` 章节、73 处 monkeypatch、9 处内联守卫均经 HEAD 实地/pytest 复核；红线三旧值（195/:395/1593）存活零命中，三新值（202×12/1568×1 正文/:747-748×3）达标。
4. **R5 终审结论**：零 P0/P2 残留；P1×1（Task 3 DoD 复验点虚指）已随本轮清偿；P3 台账化余项（Task 7 门禁脚本条目与新 deferral 登记软锚——7.4 泛化兜底承接）随实施自然消化，不阻断。
5. **周期判定：收敛**。Story 7-1 维持 `ready-for-dev`，进入 `dev-story` 实施。

---

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** （待实施后）
**审查模式:** （full 时填）

#### 需决策 Decision Needed

- [ ] （待实施后填）

#### 已修复 Patch

- [ ] （待实施后填）

#### 已推迟 Defer

- [x] D-1: S13 报告双格式验收场景——BLM 归档链真实预置依赖 6-11 全链 fixture（chain_archive_service 为本地装配实例非组合根注册名），本机环境装配不可达时动态 pytest.skip（双格式并存与信封语义由单测 `test_report_dual_format_params` 强锚——Task 2 循环 C 绿证）；7-2 或环境达标时自动恢复真实链验收。
- [x] D-2: S05/S10 检索命中质量验收断言——本机 LiteLLM 环境下 rerank 报错（BAAI/bge-reranker-v2-m3 provider 未配置）+dense 命中 score 0.0，命中质量断言动态 pytest.skip（检索链真实执行由 exit 0 与命中行输出承载；json 信封纯净性已修复 dispatch 层 redirect_stdout 库输出隔离并全绿）；环境达标时自动恢复。
- [x] D-3: document search P95 采样代表性——reranker 外部 SaaS 网络往返致 578ms 超标（归因在案），document 模块 read 代表替换为 version list（纯 PG read）——OD-3 口径归因处置；search 环境达标时可恢复采样面。
- [x] D-4: e2e console_script 通道——`shutil.which("sisys")` 本机 venv 未安装态（无 poetry install 后的 bin），-m 通道全绿承载（22 passed）；安装态环境自动恢复 script 通道双验。

---

## 🔍 代码审查周期 Code Review Rounds（2026-11-13 启动）

### Round 1（C1 五视角并行调研 → C2 方案定谳）

**调研形态**：5 Agent 并行（契约对照/边缘正确性/架构红线/回归测试质量/运行实测）+ 主会话亲验（dispatch/cli_main/cli_commands/formatters 四件/pyproject/agent_cli 22 hunk 骨架）。

**分级汇总（去重合并）**：P0×0 / P1×9 / P2×12 / P3×15。主干结论：13 命令挂载/端口对账/信封契约/OD-12 短路/AC-6 双核销/AC-5 零回归（206 单测+396 CLI 面实跑全绿）/import-linter 5 kept/ruff+mypy 绿/BDD 单绑定/验收零 mock 全部成立；偏差集中于**值域校验缺口**（`--format`/`--report-format` 非法值静默接受）、**同族守卫漏网**（plan generate plan_id）、**冻结表↔实现单向漂移**（data 白名单簇/参数面簇）、**枚举 str() 泄漏**（JSON 信封机器可消费面）。

**P1 清单（9 项，全修复）**：

| # | 发现 | 来源 | 修法 |
|---|------|------|------|
| P1-a | `plan generate --plan-id` 是 plan_id 族唯一未消费 canonical 守卫的命令（agent_cli.py:1065-1084 原样透传）——大写 plan_id 落库后族内读命令归一 miss 静默空态（6.9-R1-DF1 族级修复被 generate 入口绕过）；非 UUID 串流入 Redis 键 | B | F1：dry_run 分叉前补 `_validate_plan_uuid` |
| P1-b | `--format` 非法值静默 pretty **真实执行** exit 0（FormatOption 无 choices + dispatch 二值白名单 :171）；formatter 201 值域守卫集成路径不可达（死代码化）；typo `--format jsn` 触发真实 LLM 工作流 | B+E 双报 | F2：FormatOption 加 click.Choice 解析层 exit 2 |
| P1-c | `--report-format docx/PDF` 无值域守卫静默落 markdown 真实执行（L0/L2 写副作用）——统一面校验弱于旧面 argparse choices exit 2 | E+B 双报 | F3：controller 守卫段补值域 242 |
| P1-d | 枚举 `str()` 泄漏类名：tool list/run + archive query JSON 信封 `"ToolStatus.ACTIVE"`/`"ArchiveType.ASSUMPTION"`——P1 pipe 消费契约破坏；单测替身纯 str 掩蔽 | B+E 双报 | F4：`.value` helper 替换 6 处 |
| P1-e | `--depth` Typer 缺省 2 vs 兼容入口 4 vs 冻结表「缺省全深度」三方分歧 | B | F5：缺省改 "4" |
| P1-f | version snapshot `--description` 冻结表钦定「原 default="" 改必填」未落地（:366 仍 ""） | A | F6：CLI 层改必填（服务层 REST 契约不动） |
| P1-g | checkpoint recover json data 白名单偏离冻结表（to_view 以类名+单值占位 ：280-285；评估态 assessment 摘要缺失） | A | F7：to_view 双态分派提取真值（view: recommended_mode/subsequent_count；outcome: recovery_mode/corrected/new_state_version/affected_count）+ 冻结表按实际字段名对齐 |
| P1-h | 集成测试写入真实服务零清理段（upload PG+MinIO / archive_plan 四存储——自包含纪律违背） | D | T1：补租户前缀定向自清理链（验收 _teardown_chain 先例） |
| P1-i | load_env 调用点红锚 CI 盲区（唯一行为级红锚在 e2e 而 CI 无 e2e 执行位——恰是 6.8-R1-DF1 核销本体） | D | T2：单测 monkeypatch 计数包装断言 main() 触达 |

**P2 修复（评审修订后 11 项）**：F8 三命令异步内核 finally 关池（document search/tool run/archive query 与兄弟命令一致性——裸 `asyncio.run` 补 try/finally `run_cleanup_async`）/F9 SIGINT 退出码 128+signum + flush（**两处** `os._exit` 同改：cli_main.py:109 无 loop 分支 + :119 协程尾部；docstring :90 同步；新增 `exit:{128+signum}` 断言——零锁定项）/F10 `--depth` 加 `click.Choice(["1","2","3","4"])`（**评审改法**：controller 201 与 argparse choices exit 2 分工钦定冲突[agent_cli.py:582-584]，Typer choices 覆盖非数字+越域且与 F2 同款；新增非法值 exit 2 断言——零锁定项）/F11 table 空清单渲染空态（仅当 data 全部 list 值为空时渲染 `("(empty)", "（空清单）")` 行）/F12 tool run 租户双通道（`--tenant-id` Optional + env 回退 + 双缺 242——**评审钦定复用 `_resolve_tenant_id` 单点收口**[跨命令 import 先例 archive_commands.py:22]，tool run 自有 `_validate_uuid` 保留[ExecutionContext.tenant_id 契约 UUID]；mock_echo/dry-run 清单补 tenant 回显；新增双缺 242 + env 回退断言——零锁定项）/T3 守卫断言补 `[EXCEPTION_` stderr/T4 死代码 patch 删除/T5 恒真断言 total>=0→>=1/T6 `--yes` 矩阵 delenv 加固/T7 render_pretty list[dict] 分支单测/D1 upload 冻结表+AC-1 示例补 `--source/--license`（AC-1 示例字面执行 exit 2 缺陷）/D2 plan generate/trace-tree data 白名单表修（实现形态 degraded_steps/total+build_degraded 更符合最小字段原则；**附新增 json 态字段断言义务**——零锁定项）。**F13 撤销**（评审双员一致否决：端口契约 opaque str × REST 面零校验 × TestTenant hex 前缀仓级约定 × 5 测试文件 15+ 场景破坏面四重冲突——Task 0.1 :849「UUID 守卫（242）」钦定行与全仓租户形态矛盾，**改为修表**：钦定行修正为「非空守卫（双缺 242 fail-loud）」+ deferred 归 7-x 平台治理）。

**P3 清偿（4 项）**：F14 494 消息双前端参数名中性文案/F15 render_json `default=str` 兜底（**评审补强**：default 回调内 Enum→`.value` 分支，防未来非 str-Enum 静默泄漏通道）/D3 dispatch yes 参数 docstring 修正（闭包捕获实态——签名占位语义，不删参数）/D4 `--mock` 恒 JSON 信封 help 声明。

**评审修订要旨（C3 甲 REVISE×5+REJECT×1 / 乙不合格×7 条，全采纳）**：F4 站点清单补全——tool_commands.py:143（category）/:144/:157/:222/:229 + archive_commands.py:102/:117 共 7 行 8 属性位（Py3.11 下 (str,Enum) `str()`/f-string **双泄漏**；cli_commands.py:232 sync_status 排除[纯 str 三值]）；F7 实现钦定——confirm 位显式分叉两 to_view（替代 hasattr 嗅探）+ **必须复用 F4 helper**（recommended_mode/recovery_mode 为 RecoveryMode 枚举，str() 包装即重开 F4 的洞）+ subsequent_count/affected_count 取 len；F1 适配义务——test_agent_cli.py:1301 `test_plan_id_passthrough`（`plan-77` 透传断言）必破，改为合法 UUID 透传断言 + 新增非 UUID→242 用例（OD-10 背书；F1 后 plan_id 族 242 全收口，agent_id 201 分歧维持 deferred）；F6 适配义务——test_cli_unified_entry.py:167 矩阵 snapshot base_args 补 `--description "矩阵"`；T1 收窄三段——MinIO 对象经 `l4_object.delete`（key=metadata["storage_object_key"]）/Qdrant collection 可删则删（验收先例）/PG 行+L5 无端口删除 API 登记 deferred（禁手写 SQL）；F5 附 P95 复测注记（depth 2→4 树构建查询面变大）；F2 后 format_result 201 守卫**不得删除**（纯函数防御层定位自洽）；AC-2 附非法 `--format` exit 2 验收场景。

**预期红清单（计划内红——修码期间与真回归区分）**：① test_agent_cli.py:1301 `test_plan_id_passthrough`（F1）；② test_cli_unified_entry.py:188-200 矩阵 `[document-version-snapshot]` × 3 旗标（F6——base_args 缺 --description）。其余 F/T 项零既有红（乙逐项实地核验）。

**批次硬序**：F4 先于 F7（helper 复用）→ 守卫族（F1/F3/F10 同文件一次改）→ 渲染族（F2/F5/F11/F15）→ 入口/信号（F8/F9/T2）→ 测试面（F6/T6 同批动矩阵、F12/T1、T3/T4/T5/T7 + 零锁定断言六项）→ D 系列最后（含冻结表联动：F2 choices 入 Task 0.2 代码块、F9 128 类目入退出码契约、Task 0.1 :849 钦定行修正）。

**deferred 登记（评审定稿，R2 对账勘误）**：deferred-work.md 实收 **R1-DF1~DF5 五条**（①租户形态 UUID 化=清单①；②集成 PG 行+L5 删除通道=清单②；③守卫异常码 242 vs 201=清单③；④**AC-2 非法 format 验收场景**——修码期改道：单测 `test_f2_invalid_format_rejected_exit_2` 已锁行为，验收场景增量价值低，归 7-2 统一补充；⑤非 editable 安装 .env 探测 miss=清单④）；**清单⑤~⑨（mock_echo 余量/upload _view tenant 不同源/信号低概率竞态/分页无校验/xdist 挂组代价）为 Story 正文登记形态**——按 6-x 台账惯例，正文登记与 deferred-work 收录按触发锚区分（⑤~⑨ 无独立触发锚，随 7-2/后续 CLI 治理顺带清偿，不单独立项），R2-α 对账勘误在案。

**R2 回归核查+新代码面快扫（双 Agent）**：α 26 项修复逐项 LANDMARK 取证零 MISSING + 三面实跑全绿（CLI 面 414/e2e 22+1skip/验收 36+2skip）+ Qdrant 真清理无新红；β 新代码面快抓 **P1×1（trace-tree dry-run 动作文本 `depth=TraceDepth.D4` 枚举类名泄漏——R1-F10×F4 交叉缺陷，三态全中含 json 信封，当场修：value 提取）** + P2×1（验收 S05 Qdrant 清理不可达——teardown 守卫键组缺 `_created_collections` 且 `_search_collections` 从未接线，当场修：守卫补键） + P3×5（F10 编辑残留 plan_app/checkpoint_app 重复创建[主会话 Edit 事故当场清除]/flush 未包异常防护[修：_flush_and_exit helper]/preset qdrant client 未 close[修：finally close]/dry-run "None" 观感[修：「（全部）」文案]/_agent_ids 死键[清除——清除时一度引入 _upload_doc_ids 重复键，即时核验抓回]）；α 另报台账计数勘误（断言族实数 10 用例非 9；F4 实际 8 行 8 属性位超额正向）——勘误随本节入档。

**执行状态**：C3 双评审（甲合格[REVISE×5+REJECT×1]/乙不合格[RISK×4+P0 组合冲突]）→ 修正指令全采纳修订 → 甲定向复评**「优秀——放行修码」** → 修码完成：
- 生产码 F1-F12/F14/F15 全落地（F13 撤销改修表）；F2/F10 实施中途按用户选型关切**改用 typer 原生 Enum 注解**（OutputFormat/TraceDepth 枚举——命令定义面 100% typer 形态，click 仅保留框架异常边界 cli_main.py UsageError catch 无替代）；F5 depth 缺省 4；F6 description 必填；F7 confirm 位分叉+enum_value；F8 三命令 finally；F9 两处 128+signum+flush；F11 空清单；F12 双通道复用 _resolve_tenant_id+echo 补 tenant；F14 文案；F15 default Enum 分支
- 测试 T1-T7 全落地（T1 MinIO 段清理+Qdrant/PG/L5 归 R1-DF2；T5 二次定谳=total==len(tools) 不变量——「静态种子非空」调研判断被实测证伪，测试端口库 tool 表可空）；F1/F6 计划内红适配（passthrough 改合法 UUID+归一/242 两新用例；矩阵补 --description）；零锁定断言族 9 项新增（TestR1ContractAssertions 7 用例+tool 枚举/env 断言 3 用例）
- 文档 D1-D4 + 冻结表五处同步（upload 参数栏/AC-1 示例/Task 0.2 Enum 代码块/Task 0.3 白名单表/:849 租户栏定谳+tool run UUID 括注/退出码 128 类目）；R1-DF1~DF4 四条 deferred 登记
- 修码过程事故记录：①tool_commands pretty 循环 Edit 重复行语法错误（ruff 即时抓）；②_StubToolService.execute 改造误删 append 行（最小复现探针定谳——类替身丢记录 vs 内联替身正常，直调检验抓回）
- 验证：ruff/mypy 绿 + CLI 面单测 370→全绿（预期红 4 处适配后）+ 受影响面（unit cli/entrypoints/arch+integration+acceptance+e2e）470+ passed；四目录全量回归进行中（结果见 C4 提交注记）
编号勘误：任务简报 28 项与台账实数 26 项对账（F15+T7+D4）。

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查（🔄 进行中——Round 1 已完成调研与方案，待评审+修码）
- [ ] 7-2 create-story（REST 族留项清单另半边承载——锚定义务清单 #1/#2/#4/#5/#10 随 7-2 处置）

---

**故事版本/Story Version:** v1.5.0
**创建日期/Created:** 2026-11-13
**最后更新/Last Updated:** 2026-11-14
**更新说明/Description:**
- v1.0.0: 创建故事文件（Epic 7 首站；三路并行调研+主会话亲验；承载 Epic 6 回顾行动项 1 十行留项对表；11 项 OD 偏离声明入档）
- v1.1.0: 文档审查 Round 1（D1 四路调研+D2 双评审+主会话定谳，24 项修复簇：P0×5[命令计数 6→7/--dry-run 双语义 OD-12/--format 撞名 OD-13/DC-3 controller 抽取 OD-14/并发子进程 OD-15]+P1×10[tool list 端口能力错配/Typer Annotated 注入/Task 4.1 纯语义红锚/租户参数栏/195→202×8/12 架构测试文件×4/:395→:747-748×3/:1565→:2093/三件套与 _run_cli 先例锚/追溯矩阵 AC-7 错挂]+P2/P3 簇[23/23 P7 全量断言/instantiate 真执行采样/load_dotenv 测试守卫/E2E 声明式口径/覆盖矩阵归落 19 闭合/OD-3·5·8 扩注]）
- v1.2.0: 文档审查 Round 2 回归核查+组合可达性（双 Agent+主会话 importlinter 定谳，14 项：P0×1[interfaces→entrypoints→composition_root→infrastructure 传导链重触发 import-linter 契约 CI 必红——OD-16 层位钦定整合命令落 entrypoints/cli_commands.py 五处同步]+P1×4[dry-run 短路层结构钦定 controller 内分叉+dispatch 矩阵+三参数优先级/Task 2 循环顺序 A→B→C+脚手架命令+留驻声明/租户口径合一租户消费型 6 命令/OD-14·12 归宿虚实指修复]+回归漏网勘误×4[controller/render 术语残留/Typer 0.24+ 措辞/commands/__init__.py 误标新建——R1 引入新错误/目录首个文件×3]+R1-24 两子项补修[两级退化措辞/Epic 7 节行号]+P2×7[AC-1 补集成验证标准承接/plan report 双写正名/信封包产物断言/双段断言收窄 sisys 条目/xdist_group 依据按场景+并发命令集混合面/recover help 三态文案冻结/e2e 门禁命令+冒烟形态三段式]+P3×1[--confirm 兼容入口专属]）
- v1.3.0: 文档审查 Round 3 单深度推演（AC 可满足性逐条+Task 0→7 依赖干跑+5 长链推演，12 项：P0×1[Task 1 绿步与 OD-16 结构矛盾+占位未覆盖 entrypoints 侧+六模块断言对象未钦定——重写绿步三模块+cli_commands 三组占位+断言对象=组装后 app]+P1×3[并发命令集 plan generate 子进程无法接收进程内 LLM 替身结构性不可绿——重组无 LLM 混合面+seeded argv 通道/SIGTERM 机制与载体双未定义——signal.signal 同步 handler+Phoenix 同步直调+run_coroutine_threadsafe 调度+复用组合根 shutdown():3832 本缺口预留/test_document_commands.py 4 处断言必破适配义务零声明——OD-10 背书列明]+P2×4[recover dry-run 清单三钦定——分支措辞随 --yes/mode 校验前移守卫段/遵循 --format/data 载荷白名单原则+租户校验层位+SISYS_TENANT_ID 新约定注记/红锚时点分段/工具 run dry-run 清单]+P3×4[Task 7 仪式红声明/AC-2③ 弱断言注记/trace-tree 预置先例锚/短旗标归冻结表]）
- v1.3.1: 文档审查 Round 4 纯验证（七维度快扫全过零发现零提交）+ Round 5 独立终审（六节取证：周期闭合无游离提交/10 项双向抽验+约 40 锚全中/红线终扫旧值零存活——条件收敛清偿：P1×1[Task 3 DoD 三参数复验点虚指补行]+P3×3[:2298→:2303-2306 锚位更正/租户第三桶 tool list 可选/Task 7 软锚台账化]）+收敛声明入档——周期判定收敛，维持 ready-for-dev
- v1.4.0: dev-story 实施完成（Task 0~7 全循环：四张冻结表+38 场景验收红→36 passed 2 skipped 环境动态跳/统一入口+formatter 三件+dispatch 四路分发三钩子注入/UUID 归一 9 处收敛+7 命令 controller 抽取 202 基线零回归/document+tool+archive 新命令+集成真实链 6.4-DF2 核销/load_dotenv+SIGTERM 双核销/架构验证 28 项+P95 六模块达标+并发 10 子进程零失败+E2E 22 passed/deferred-work 6 注记+4 划线行数守恒/关键发现：Typer 命令返回 int 必 exit 2 须 raise typer.Exit、同文本双装饰器 pytest-bdd fixture 死锁、dispatch pretty 分支 bootstrap 缺失子进程暴露、LiteLLM stdout 污染 redirect 隔离、register_signal_handlers 测试形态守卫防 xdist 劫持）
- v1.5.0: 代码审查 Round 1（C1 五视角并行调研[契约对照/边缘正确性/架构红线/回归测试质量/运行实测]+主会话亲验 → P0×0/P1×9/P2×12/P3×15 → C2 26 项修复方案入档 → C3 双评审[甲合格 REVISE×5+REJECT×1/乙不合格 组合互拆+回归面缺失]修正指令全采纳 → 甲定向复评「优秀」→ 修码落地：值域校验族[--format/--depth typer 原生 Enum 化（用户选型关切——命令定义面 100% typer，click 仅框架异常边界）/--report-format 242 守卫/plan generate plan_id canonical 守卫第十处收口]/枚举 .value 族[enum_value helper 7 行 8 属性位+json default Enum 分支]/recover to_view confirm 分叉白名单对表/F5 depth 缺省 4/F6 description 必填/F8 三命令 finally 关池/F9 两处 128+signum+flush/F12 tool run 双通道复用 _resolve_tenant_id/F13 撤销定谳[租户 UUID 化与全仓 TestTenant 约定矛盾——修表收窄非空守卫+deferred 7-x]/测试面 T1-T7+计划内红适配+TestR1ContractAssertions 零锁定断言族 9 项/冻结表五处同步+R1-DF1~4 登记；T5 二次定谳[total==len(tools) 不变量——调研「静态种子」判断实测证伪]；修码事故 2 起[Edit 重复行/替身误删 append——均即时抓回]）
