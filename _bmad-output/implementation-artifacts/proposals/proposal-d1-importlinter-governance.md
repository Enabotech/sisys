# 方议案 D1：import-linter `interfaces-no-infrastructure` 契约治理

> **状态**：✅ 已实施（2026-10-15，3-body 批准方案 B——.importlinter 契约已改直接依赖禁止语义，CI non-blocking 观察期至 2026-10-29；§5 决策请求点 1/3 已裁定，2 按两步节奏执行中）
> **来源**：Story 5-1 代码审查 R1 留项 D1【P1】；deferred-work.md「Deferred from: code review of 5-1 Round 1」节
> **作者**：5-1 审查周期（2026-10-14）；事实均经 lint-imports 实测与 git 历史核验
> **约束**：CLAUDE.md 明令「禁止修改 .importlinter 中已合入的架构依赖规则」——本文档仅为决策材料，任何方案落地均需架构评审批准后实施

---

## 1. 问题陈述

`lint-imports` 实测 `Contracts: 4 kept, 1 broken`（exit 1）——`interfaces-no-infrastructure` 契约 BROKEN，违规链三条：

| 链 | 路径 | 引入时间 |
|----|------|---------|
| 1 | `src.interfaces.api.app` (:15, :26) → `src.composition_root` → `src.infrastructure.config.qdrant` 等多条 infrastructure 边 | 存量（早于 5-1） |
| 2 | `src.interfaces.cli.ocr_cli` (:39) → `src.composition_root` → infrastructure | 存量 |
| 3 | `src.interfaces.cli.agent_cli` (:32) → `src.composition_root` → infrastructure（含 `config.rabbitmq`） | Story 5-1 新增（按 Story 契约「仿 ocr_cli 接线模式」交付） |

**关键事实**：
- 三条链均为**传递性违规**（`forbidden` 契约默认含间接依赖）——interfaces 文件**零直接** `import src.infrastructure`
- 该契约**未纳入** CI/pre-commit 门禁（`.pre-commit-config.yaml` 与 `.gitea/workflows/` 均无 lint-imports 环节），当前不影响流水线
- 契约与项目自身 DI 模式存在**结构性张力**：六边形架构规定「所有装配经 composition_root、业务代码经 bootstrap()+resolve() 获取实现」（CLAUDE.md §4）——按此模式编写的任何 CLI/API 入口**必然**产生此传递链。即：**契约文本与项目宪法（组合根唯一装配）互相矛盾**，agent_cli 只是按宪法交付后让矛盾显形

## 2. 方案对比

### 方案 A：entrypoint 层上移（结构重组）

CLI/API 启动器移出 `src/interfaces/`，在 `src/` 根与 composition_root 同层新建 `entrypoints/`（或 `src/main.py` 形态），层规则将 entrypoints 视为与 composition_root 同级的「组装层」。

- ✅ 语义最彻底：interfaces 层回归「纯适配器」（FastAPI 路由/Typer 命令定义），进程入口与组装职责独立成层
- ❌ 改动面大：`app.py`/`ocr_cli.py`/`agent_cli.py` 迁移 + pyproject scripts 双注册改写 + 全部引用测试路径更新 + `.importlinter` 层定义扩充——预计 15+ 文件
- ❌ 历史成本：`ocr_cli`/`app` 为存量结构，迁移属架构级重构，收益/风险比在 MVP 阶段不占优
- 适用：若未来要求「interfaces 层可独立于进程入口复用」（如 API 挂多宿主）时再启动

### 方案 B：契约语义改为「直接依赖禁止」（`allow_indirect_imports = True`，**推荐**）

> **勘正（2026-10-15 对标分析轮）**：本方案初稿机制为 `exclude_modules = src.composition_root`——经 import-linter v2.13 源码核查与最小实验双重证实，**`exclude_modules` 并非 forbidden 契约的配置选项**（置于契约节内为惰性配置，契约行为不变）；正确机制是一等公民选项 `allow_indirect_imports`。

契约保持 `forbidden` 类型，增加 `allow_indirect_imports = True`——语义从「传导性禁止」收窄为「**直接**依赖禁止」：interfaces 直接 `import src.infrastructure` 仍违规，经 composition_root 的间接链合法。

- **语义正当性**：composition_root 本就不属于三层中任何一层（`dependency-direction` layers 契约也未包含它），它是 Clean Architecture 所述 Main 组件（"the dirtiest, lowest-level component"，架构圈外的终极细节）——其 import infrastructure 是设计使然而非违规。「interfaces 不得**直接**触碰 infrastructure、必须经组合根」正是项目的真实架构规则，`allow_indirect_imports = True` 是该规则的一等编码（非豁免 hack）
- ✅ 改动面最小：`.importlinter` 该契约节 +2 行（选项 + 注释）
- ✅ 保护力实证（最小实验 /tmp 三模块对照，2026-10-15）：开启后经组合根的间接链不再报、`interfaces → infrastructure` **直接** import 仍被捕获（`app.direct -> infra` 形态在开启状态下依然 broken）
- ⚠️ 语义代价：任何经 composition_root 传递触达 infrastructure 的链均放行——组合根自身引入错误边的检测由此契约让渡给 code review 承接
- 配套：lint-imports 纳入 CI（先 non-blocking 报告两周后转 blocking），让 4 kept 契约获得持续执行

### 方案 C：显式白名单（`ignore_imports` 逐边豁免）

为本契约列出 `ignore_imports = src.composition_root -> src.infrastructure.config.qdrant` 等全部边。

- ❌ 脆：组合根新增 infrastructure import（常态，如本轮的 `config.rabbitmq`）即重新 BROKEN，白名单需持续维护
- ❌ 噪声大：当前需列 ~6+ 条边且随演进增长
- 仅当评审认为「组合根的每一条 infrastructure 边都应显式受控」时采用（那实际上是给组合根加变更门禁，可另行以 code review 规则承接）

### 方案 D：维持现状 + 文档化接受

不修契约、不进门禁，D1 台账持续挂账。

- ❌ 与「已合入规则必须被满足」的治理直觉相悖；后续任何按宪法编写的入口都会继续「违规」，契约信誉持续折旧
- 仅在评审认为 MVP 阶段不值得动任何配置时采用（零成本，但债务只增不减）

## 3. 推荐与实施清单（方案 B）

1. `.importlinter` `interfaces-no-infrastructure` 契约节增加：
   ```ini
   # 语义：直接依赖禁止（间接经 composition_root 合法）。composition_root 是
   # 宪法授权的组装层（Clean Architecture Main 组件——架构圈外的终极细节，
   # 不属于三层任一层），其 import infrastructure 为设计使然。开启本选项 =
   # 「interfaces 不得直接 import infrastructure、必须经组合根」的真实规则编码。
   # 注：exclude_modules 非 forbidden 契约选项（2026-10-15 源码核查勘正）。
   # 架构评审批准（2026-XX-XX）。
   allow_indirect_imports = True
   ```
2. 本地验证：`poetry run lint-imports` → 5 kept / 0 broken；再加临时直接违规用例验证直接依赖仍被捕获（同 /tmp 实验形态）
3. CI 接入（分两步）：
   - 第一步：`.gitea/workflows/ci.yml` 增加 `poetry run lint-imports`（non-blocking / allow-failure，观察期两周）
   - 第二步：观察期满转 blocking（同时给 pre-commit 增加同款本地钩子）
4. 回归面：无生产代码变更；架构测试（test_hexagonal_architecture_constraints.py 等）全量复跑
5. 台账：D1 核销（deferred-work.md 对应条目标记 RESOLVED + 方案 B 引用）

## 4. 方案 A 的保留触发条件（供远期参考）

- API 需要多宿主部署（uvicorn 之外的嵌入式/Serverless 宿主）
- CLI 集中式主入口立项（Epic 7 `sisys` 主命令——届时 entrypoints 层一次性成型，迁移成本被摊薄）

## 5. 决策请求点

| # | 需拍板项 | 选项 |
|---|---------|------|
| 1 | 治理方案选型 | A（重组）/ **B（直接依赖禁止，推荐·已裁定实施）** / C（白名单）/ D（接受现状） |
| 2 | 若选 B：CI 接入节奏 | 立即 blocking / 两周观察期后 blocking（推荐） |
| 3 | 组合根 infrastructure 边的变更管控 | code review 承接（推荐）/ 另立契约白名单（方案 C 形态） |

## 6. 证据附录

- `poetry run lint-imports` 输出（2026-10-14 实测）：`Contracts: 4 kept, 1 broken`，三条违规链如 §1 表
- `.importlinter` 全文五契约：domain-no-external-dependencies / dependency-direction / infrastructure-does-not-depend-on-interfaces / application-no-infrastructure / interfaces-no-infrastructure
- 基线核验：`git show ed3a2053` 上 app/ocr_cli 链已存在（5-1 之前契约即 BROKEN）
