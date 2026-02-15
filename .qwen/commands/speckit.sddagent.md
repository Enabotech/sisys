---
description: 端到端 Spec 驱动开发（SDD）总控智能体：specify → clarify → plan → tasks → analyze → implement（可往返，不包含 constitution）。
---

---
description: 端到端 Spec 驱动开发（SDD）总控智能体：specify → clarify → plan → tasks → analyze → implement（可往返，不包含 constitution）。
handoffs:
  - label: 需求分析（specify）
    agent: speckit.specify
    prompt: 根据功能描述创建/更新规范
    send: true
  - label: 需求澄清（clarify）
    agent: speckit.clarify
    prompt: 澄清规范中的关键不确定点
    send: true
  - label: 方案设计（plan）
    agent: speckit.plan
    prompt: 生成实现计划与设计工件
    send: true
  - label: 任务分解（tasks）
    agent: speckit.tasks
    prompt: 基于工件生成 tasks.md
    send: true
  - label: 一致性检查（analyze）
    agent: speckit.analyze
    prompt: 只读分析 spec/plan/tasks 一致性
    send: true
  - label: 开发实现（implement）
    agent: speckit.implement
    prompt: 按 tasks.md 分阶段实现
    send: true
---
## 用户输入
```text
$ARGUMENTS
```
如果用户输入不为空，你**必须**在继续之前考虑用户输入。
## 目标
把你当前仓库里的 6 个核心命令编排成一个“可往返”的端到端工作流：  
**specify（需求分析）→ clarify（澄清）→ plan（方案设计）→ tasks（任务分解）→ analyze（一致性检查）→ implement（开发实现）**。
> 说明：本总控命令**不包含** `constitution` 作为步骤，但其他命令如果自身需要读取宪法文件，遵循其自身规则即可。
## 使用方式（输入协议）
你可以用任意一种方式驱动本命令：
1. **自然语言**：直接描述你想做的功能（若当前未初始化 feature，将默认进入 specify）。
2. **显式步骤**：在 `$ARGUMENTS` 里指定要执行的步骤名（大小写不敏感）：
   - `specify` / `clarify` / `plan` / `tasks` / `analyze` / `implement`
3. **快捷格式**：`<step>: <text>`，例如：`specify: 新增图书借阅功能`
## 总控流程（必须遵守）
### A. 先做“状态探测”（尽量自动）
1. 尝试从仓库根目录运行 `.specify.specify/scripts/powershell/check-prerequisites.ps1 -Json -PathsOnly`（PathsOnly + JSON）以确定当前活动 feature 的路径（REPO_ROOT / FEATURE_DIR / FEATURE_SPEC / IMPL_PLAN / TASKS）。
2. 如果脚本失败（例如尚未创建 feature / 未设置 SPECIFY_FEATURE / 不在 feature 环境）：
   - 视为 **未初始化**，推荐进入 `specify`。
3. 如果脚本成功：
   - 使用返回的绝对路径，检查以下文件是否存在并可读（用“能否读取”来判断即可）：
     - `FEATURE_SPEC`（通常是 `spec.md`）
     - `IMPL_PLAN`（通常是 `plan.md`）
     - `TASKS`（通常是 `tasks.md`）
   - 额外对 `spec.md` 扫描是否存在 `[需要澄清`、`TODO`、`TKTK`、`???` 或明显占位符（只作为推荐依据，不自动改写）。
4. 输出一段**简短状态摘要**（不要泄漏整篇文档内容），包含：
   - 是否已初始化 feature
   - spec/plan/tasks 是否存在
   - 是否检测到明显的“需要澄清”信号
### B. 选择下一步（友好 + 推荐 + 默认）
在执行任何会写文件的步骤前，你必须给出一个“下一步菜单”，并给出推荐与默认值：
| 选项 | 步骤 | 适用场景 |
|------|------|----------|
| 1 | specify | 还没 feature/spec，或需求范围需要重写/补全 |
| 2 | clarify | spec 有关键歧义/占位符，需要问答收敛 |
| 3 | plan | spec 足够清晰，开始做技术方案与设计工件 |
| 4 | tasks | plan 工件已就绪，把方案拆成可执行任务 |
| 5 | analyze | tasks 已生成，做只读一致性/覆盖分析 |
| 6 | implement | tasks 质量可接受，进入分阶段实现 |
并按如下格式收尾（必须原样包含“默认”行）：
- **推荐**：选项 X（1 句话说明理由）
- **默认**：选项 X
- **请回复**：`1`/`2`/`3`/`4`/`5`/`6`（你也可以直接回复步骤名）
如果用户在本轮 `$ARGUMENTS` 已经显式指定了步骤，则跳过菜单，直接进入对应步骤执行。
### C. 执行选定步骤（复用现有命令定义）
一旦选定步骤，你必须**读取并遵循**对应命令文件的全部规则来执行（相当于在本命令内“内联执行”该命令）：
- `specify` → 读取：`.cursor/commands/specify.md`
- `clarify` → 读取：`.cursor/commands/clarify.md`
- `plan` → 读取：`.cursor/commands/plan.md`
- `tasks` → 读取：`.cursor/commands/tasks.md`
- `analyze` → 读取：`.cursor/commands/analyze.md`
- `implement` → 读取：`.cursor/commands/implement.md`
**关键约束**：
- 本总控命令不执行 `constitution`（不读取 `.cursor/commands/constitution.md` 作为步骤）。
- 每次只执行**一个**步骤；如果该步骤本身是交互式（例如 clarify 会提问），按它的规则完成该交互。
- 步骤执行结束后，必须再次回到“状态探测 → 下一步菜单”，并根据最新结果给出**可能的回退建议**：
  - 例如：在 plan 中发现大量 NEEDS CLARIFICATION → 推荐回到 clarify 或 specify。
  - 在 analyze 中发现关键覆盖缺口/冲突 → 推荐回到 tasks 或 plan 或 specify（按问题性质）。
### D. 结束条件
当且仅当以下两者同时满足，你可以提示“端到端流程已完成”：
- `implement` 已完成所有必须任务，并且
- 用户确认功能按 spec 的成功标准工作（用一句话让用户确认即可）。

