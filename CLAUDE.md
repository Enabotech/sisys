# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 1. Project Overview

面向企业高管的 AI 驱动战略规划与决策智能平台。通过多 Agent 协作（CEO/CFO/CMO/CTO/COO/CHO/AUD 七角色）+ BLM/BEM 方法论，实现 SP→BP 全链路战略规划闭环。

技术栈：Python 3.11+ / FastAPI + Typer / LangGraph + Prefect / 五层存储（Redis / PostgreSQL / Qdrant / MinIO / Neo4j）/ RabbitMQ 事件总线。

## 2. Commands

```bash
# 开发环境
poetry install --with dev,test       # 安装依赖

# 代码质量
poetry run ruff check src/ tests/    # Lint
poetry run ruff format src/ tests/   # 格式化
poetry run mypy src/                 # 类型检查

# 测试
poetry run pytest tests/                                  # 全部测试

# 数据库
poetry run alembic -c deploy/postgresql/alembic/alembic.ini upgrade head
```

## 3. Architecture

严格六边形架构（Ports & Adapters），四层分层：`domain`（纯业务，零外部依赖）→ `application`（用例编排）→ `infrastructure`（端口实现）/ `interfaces`（API/CLI 入口）。所有端口在 `src/composition_root.py` 统一注册，通过 `resolve()` 自动注入。依赖方向由 `.importlinter` 强制校验。

详细架构设计见 `docs/architecture/architecture.md`。

```
src/
├── domain/          # 实体、值对象、领域事件、端口接口（Protocol）、领域服务
├── application/     # 用例、应用服务、事件处理器、应用层端口
├── infrastructure/  # 五层存储实现、RabbitMQ/Redis 事件总线、LangGraph/Prefect 引擎
└── interfaces/      # FastAPI 路由、Typer CLI、SAP 适配器
```

## 4. Conventions

- Story 开发遵循 SDD+TDD 融合流程：Task 0 定义规范 → 每个任务内含完整 TDD 红/绿/重构循环 → 最后任务做验收测试
- 代码注释：Google 风格全中文详见`~/.claude/projects/-home-agimtech-sisys/memory/sisys_code_comment_style.md`
- 行宽 128 字符，ruff 规则 E/F/I/N/W
- 领域事件双通道投递：realtime（Redis pub/sub）+ reliable（RabbitMQ + Outbox），通道配置在 `config/event_channels.yaml`
- 端口注册带元数据（`PortSpec`）：name / version / interface / impl / lifetime / tags，支持 SINGLETON / SCOPED / TRANSIENT 三种生命周期
- 新事件必须同时更新 `config/event_channels.yaml` 和 `ChannelRouter.DEFAULT_MAPPINGS`
- 测试租户隔离：`TestTenant` 生成 UUID 前缀，覆盖 Redis key / PG schema / Qdrant collection / MinIO bucket / RabbitMQ queue
- 覆盖率门禁：整体 ≥80%，domain ≥90%，application ≥85%
- 端口查询参数决策规则（DDD Query Object 模式）：
  - **多字段组合 + 分页** → `@dataclass(frozen=True)` Query 值对象（如 `DocumentQuery`、`AuditSearchCriteria`），定义在端口文件中
  - **单字段标识查找** → 直接参数（如 `get_by_id(id)`、`get_by_username(name)`）
  - **命令型操作** → 直接参数（如 `assign_role(user_id, role_id)`、`record_attempt(username, ...)`)
  - 不强制全量统一，按查询特征选择模式；新增端口含多字段查询时必须使用 Query Object
- 验收测试：参考现有用例实现；按 AC 组织，边界明确且覆盖完整；真实服务优先：使用 scenarios() + context dict + 真实服务实例；动态跳过；自包含
- 集成测试：参考现有用例实现；尽可能使用真实服务；领域服务用真实实例；真实服务 Schema 隔离（独立 PG schema + savepoint rollback + 租户隔离 bucket）和Mock 工厂（`AsyncMock(spec=ProtocolClass)` + `_make_*()` 工厂函数）两种子模式；**禁止**手动 delete/truncate

## 5. Hard Constraints

- **domain 层禁止任何外部依赖**（import-linter 强制校验，包括 pydantic/sqlalchemy/redis 等），违反则 CI 失败
- **禁止** `# noqa`、`# type: ignore`、`# pylint: disable` 等抑制注释，**禁止**修改阈值/规则消除告警——必须修复根因
  - **`import-untyped` 修复**：第三方库缺少类型注解（无 `py.typed`、无 types-* 包）时，**禁止**用 `ignore_missing_imports=true` 豁免。必须在 `stubs/<package>/__init__.pyi` 创建 PEP 561 类型存根，仅覆盖项目实际使用的 API 面
- **验收/集成测试禁止 mock**：必须尽量用真实服务调用验证真实代码行为，`mock`仅限单元测试
- **异常是领域契约** 禁止 raise ValueError、手动 raise HTTPException、继承内置 Exception，所有异常必须走 src/domain/exceptions/ 体系 + ExceptionHandlers 自动映射，提交前三条 grep 自查必须零输出。必须遵守 `docs/architecture/sisys-uni-exception-design.md`
- **禁止** 绕过 pre-commit hooks（`--no-verify`），提交必须通过预提交钩子检查
- **禁止** git commit 信息中包含任何 AI 辅助署名（如 `Co-Authored-By: Claude`、`anthropic.com` 等），提交信息保持纯净
- **禁止** 修改 `.importlinter` 中已合入的架构依赖规则
- 已合入的 alembic migration 禁止修改，只允许新增
- 所有 API 路由必须过认证中间件
- BDD 步骤中**禁止**使用 `@pytest.mark.asyncio`（会导致 context data 丢失，用 `event_loop.run_until_complete()`）
- **Mock/Fake/Real 三层策略** 单元测试 Mock 端口，禁止真实服务；集成测试真实服务优先，自包含（创建→执行→清理），Mock 仅例外；验收测试：强制真实服务，自包含（创建→执行→清理），禁止 mock，`pytest.skip()` 动态跳过，禁止 `@pytest.mark.skip` 写死。[详情翻阅记忆]

## 6. Gotchas

- `asyncio.Lock` 必须声明为**类变量**而非实例变量，否则在协程间不共享
- 本地开发需配置 `.env`（参考 `.env.example`），至少需要 PostgreSQL + Redis 连接信息
- `SISYS_USE_TEST_PORTS=1` 切换到独立测试端口（避免与本地开发服务冲突）
- impl 为字符串的端口是延迟加载（lazy import），调试时注意模块路径写错不会立即报错
- 存储层端口命名：`l0_storage`（文件系统）→ `l1_cache`（Redis）→ `l2_rdb`（PostgreSQL）→ `l3_vector`（Qdrant）→ `l4_object`（MinIO）→ `l5_graph`（Neo4j），不是从 1 开始
- **Agent worktree 清理**：Agent 使用 worktree 隔离开发后，必须彻底清理（`git worktree unlock` → `git worktree remove --force` → `git branch -D` → 验证 `git worktree list` 仅剩 main），残留 worktree 会被意外 `git add -A` 添加为 submodule 污染仓库
