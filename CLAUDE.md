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

## 5. Hard Constraints

- **domain 层禁止任何外部依赖**（import-linter 强制校验，包括 pydantic/sqlalchemy/redis 等），违反则 CI 失败
- **禁止** `# noqa`、`# type: ignore`、`# pylint: disable` 等抑制注释，**禁止**修改阈值/规则消除告警——必须修复根因
  - **唯一例外**：`# type: ignore[type-abstract]` — mypy 无法区分"用于实例化"和"用于查找"两种语义，Protocol 类作为 DI 容器查找键时触发误报（业界 DI 框架 Spring/punq 均支持此模式）
- **禁止** 绕过 pre-commit hooks（`--no-verify`），提交必须通过预提交钩子检查
- **禁止** 修改 `.importlinter` 中已合入的架构依赖规则
- 已合入的 alembic migration 禁止修改，只允许新增
- 所有 API 路由必须过认证中间件
- BDD 步骤中**禁止**使用 `@pytest.mark.asyncio`（会导致 context data 丢失，用 `event_loop.run_until_complete()`）

## 6. Gotchas

- 跑测试前必须先执行 `composition_root.bootstrap()` 初始化端口注册表（conftest.py 已自动处理，手动写测试时别忘）
- `asyncio.Lock` 必须声明为**类变量**而非实例变量，否则在协程间不共享
- 本地开发需配置 `.env`（参考 `.env.example`），至少需要 PostgreSQL + Redis 连接信息
- `SISYS_TEST_ENV` 环境变量控制测试环境（local/ci/k8s/test），默认 local；本地跑集成测试需先启动 Docker 服务
- `SISYS_USE_TEST_PORTS=1` 切换到独立测试端口（避免与本地开发服务冲突）
- impl 为字符串的端口是延迟加载（lazy import），调试时注意模块路径写错不会立即报错
- 存储层端口命名：`l0_storage`（文件系统）→ `l1_cache`（Redis）→ `l2_rdb`（PostgreSQL）→ `l3_vector`（Qdrant）→ `l4_object`（MinIO）→ `l5_graph`（Neo4j），不是从 1 开始
