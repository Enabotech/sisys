## Epic 1: 企业级架构基础与合规 ✅ 已完成

**目标：** 建立六边形架构基础、事件驱动机制、六层存储架构和基础合规能力，为后续功能提供技术基础。

**包含 FR：** AR-01, AR-02, AR-03, AR-04, SC-01, SC-02, SC-03, SC-07, SC-08, CP-01, CP-04, SA-01

**📦 价值组 1: Iteration 0（开发基础设施）**
> 为团队提供统一的开发环境、CI/CD 和测试框架

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 | 状态 |
|-------|------|---------|---------|-----------|------|
| Story 0.1 | **开发环境搭建** | 提供统一的开发环境和工具链 | 无依赖 | **P0-0（Iteration 0）** | ✅ 保留 (简化为 Python 环境) |
| Story 0.2 | **CI/CD 流水线** | 自动化构建、测试和部署 | 依赖 Story 0.1 | **P0-0（所有 Epic 前置）** | ⚠️ 备份后废弃 (被新 Story 0.1-0.6 替代) |
| Story 0.3 | **测试框架搭建** | 提供单元测试、集成测试框架 | 依赖 Story 0.1 | **P0-0（Iteration 0）** | ✅ 根据新 Story 完善优化 |

**📦 价值组 1: Iteration 1（Epic 0 重构）**

**重构目标：** 建立两套系统 - 开发 CI/CD 系统 + 产品交付系统

**技术栈确认：** ✅ 所有版本已由 Agimtech 测试验证
- Gitea v1.25.4 ✅
- Gitea Runner (最新版) ✅
- Harbor v2.14.3 ✅
- ArgoCD v3.2.7 ✅
- K3S v1.34.5 ✅

***📦 价值组 1.1: 开发 CI/CD 系统***
> 为开发团队提供企业级 CI/CD 基础设施

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 0.4 | **K3S 集群部署** | 提供轻量级 K8s 运行时 | 无依赖 | **P0-0** |
| Story 0.5 | **Gitea 代码托管** | 代码版本管理和协作 | 依赖 Story 0.4 | **P0-1** |
| Story 0.6 | **Harbor 镜像仓库** | 安全存储和分发 Docker 镜像 | 依赖 Story 0.4 | **P0-2** |
| Story 0.7 | **ArgoCD 持续部署** | GitOps 自动化部署 | 依赖 Story 0.5, 0.6 | **P0-3** |
| Story 0.8 | **Gitea Runner 配置** | 自动触发 CI/CD 任务 | 依赖 Story 0.5, 0.7 | **P0-4** |
| Story 0.9 | **CI/CD Pipeline 模板** | 标准化 Pipeline 复用 | 依赖 Story 0.7, 0.8 | **P0-5** |

***📦 价值组 1.2: SISYS 产品交付系统***

> 为客户提供简单快捷的产品部署体验

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 0.14 | **Windows 安装包** | Windows 用户一键安装 | 无依赖 | **P0-6** |
| Story 0.15 | **Mac 安装包** | Mac 用户一键安装 | 无依赖 | **P0-7** |
| Story 0.16 | **Linux 一键脚本** | Linux 用户一键安装 | 无依赖 | **P0-8** |
| Story 0.17 | **自动检测与修复** | 安装问题自动修复 | 依赖 Story 0.14-0.16 | **P0-9** |
| Story 0.18 | **用户友好配置向导** | 图形化配置无需 YAML | 强依赖 Story 1.1 + 0.14/0.15/0.16 + 应用镜像框架；可选依赖 Story 0.17 | **P0-10** |

***📋 原有 Story 处理***

Story 0.1 (开发环境搭建):
- ✅ **保留** - 简化为 Python 环境配置
- 删除 Docker/K3S 相关内容（移到新 Story 0.4）
- 保留：Python 3.11+、Poetry、IDE 配置、SDD 工具链

Story 0.2 (CI/CD 流水线):
- ⚠️ **备份后废弃** - 被新 Story 0.4-0.9 替代
- 归档到 `docs/archive/old-story-0.2.md`
- 保留价值：质量门禁概念、Pipeline 阶段设计

Story 0.3 (测试框架搭建):
- ✅ **根据新 Story 完善优化** - 与新 Story 0.9 配合使用
- 保留：pytest 配置、Fixture 系统、Mock 框架
- 优化：与新 CI/CD 系统集成、增加 K3S 测试支持

**📦 价值组 2: 架构基础与事件驱动**
> 实现六边形架构、领域事件和事件总线

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 1.1 | 六边形架构骨架 | 领域逻辑与技术实现隔离，支持长期演进 | 无依赖（基础） | P0-1 |
| Story 1.2 | 领域事件定义 | 支持事件驱动架构和事件溯源 | 依赖 Story 1.1 | P0-2 |
| Story 1.3 | 事件总线实现 | 实时事件低延迟路由，持久化事件可靠传输 | 依赖 Story 1.2 | P0-3 |
| Story 1.16 | **集成测试框架** | 提供集成测试、E2E 测试框架和测试数据管理 | 依赖 Story 0.3, 1.1 | **P1-16（测试 Story）** |

**📦 价值组 3: 六层存储架构**
> 实现 L0 MEMORY.md 入口 + Redis/PostgreSQL/Qdrant/MinIO/Neo4j（可选）六层存储

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 1.4 | Redis 高速缓存层 | 低延迟会话管理和语义缓存 | 依赖 Story 1.1 | P0-4 |
| Story 1.5 | PostgreSQL 关系存储层 | 支持 ACID 事务和外键约束 | 依赖 Story 1.1 | P0-5 |
| Story 1.6 | Qdrant 向量存储层 | 支持混合检索（Dense + Sparse + Payload 过滤） | 依赖 Story 1.1 | P0-6 |
| Story 1.7 | MinIO 对象存储层 | 支持版本控制和 WORM 存储 | 依赖 Story 1.1 | P0-7 |
| Story 1.8 | Neo4j 图存储层 | 支持 GraphRAG 增强检索和实体关联查询 | 依赖 Story 1.1 | P0-8 |
| Story 1.13 | **K8s 动态扩缩容** | 支持基于负载的自动扩缩容 | 依赖 Story 1.4/1.5 | **P1-13（NFR-SCALE-03）** |

**📦 价值组 4: 安全与合规基础**
> 实现 RBAC、审计日志、数据主权和等保 2.0

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 1.9 | RBAC 权限管理 | 细粒度访问控制，防止越权访问 | 依赖 Story 1.5 | P0-9 |
| Story 1.10 | 统一审计日志 | 满足等保 2.0 和 SOX 合规要求 | 依赖 Story 1.5 | P0-10 |
| Story 1.11 | 数据主权隔离 | 满足数据安全法和 PIPL 要求 | 依赖 Story 1.9, 1.10 | P0-11 |
| Story 1.12 | 等保 2.0 三级基础要求 | 通过公安部指定测评机构测评 | 依赖 Story 1.9, 1.10, 1.11 | P0-12 |

**📦 价值组 5: or.md 系统公理实现**
> 实现自主调用循环和外部化记忆

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 1.14a | **自主调用循环 - trigger** | 实现领域事件/心跳事件触发机制 | 依赖 Story 1.2/1.3 | **P0-14a（or.md 系统公理一）** |
| Story 1.14b | **自主调用循环 - route** | 实现 session_id 哈希/语义路由 | 依赖 Story 1.14a | **P0-14b（or.md 系统公理一）** |
| Story 1.14c | **自主调用循环 - execute** | 实现会话命名空间执行与状态快照 | 依赖 Story 1.14b | **P0-14c（or.md 系统公理一）** |
| Story 1.15a | **外部化记忆 - L1 显式确认压缩** | 用户主动记忆持久化，压缩率≥70% | 依赖 Story 1.4（提供 L1 Redis） | **P0-15a（or.md 系统公理二）** |
| Story 1.15b | **外部化记忆 - L0 入口 + 六层存储协同** | 实现 L0 MEMORY.md 入口与 L1-L5 六层存储协同 | 依赖 Story 1.15a + Story 1.4（提供 L0 文件系统、L1 Redis）、Story 1.5（提供 L2 PostgreSQL 基础表结构） | **P0-15b（or.md 系统公理二）** |

**📦 价值组 6: MVP 关键机制增强（Party Mode 评审新增）**
> 加强 Additional Requirements 覆盖率，验证 MVP 商业假设

| Story | 名称 | 用户价值 | 依赖关系 | 执行优先级 |
|-------|------|---------|---------|-----------|
| Story 1.17 | **UDMR 基础路由（云端优先静态配置）** | MVP 阶段支持云端优先路由，验证云端路由≥60%（V1≥80%） | 依赖 Story 1.14b | **P0-17（ARCH UDMR）** |
| Story 1.18a | **Prefect 工作流引擎集成** | 实现数据管道引擎，支持文档处理/RAG 索引/报告生成 | 依赖 Story 1.1 | **P0-18a（ARCH Prefect）** |
| Story 1.18b | **LangGraph Agent 编排集成** | 实现 Agent 编排引擎，支持 BLM 规划/Agent 协作 | 依赖 Story 1.1, 1.3 | **P0-18b（ARCH LangGraph）** |
| Story 1.19 | **成本度量基础（Token 消耗与成本追踪）** | 验证 MVP 成本优化效果并衡量 ROI | 依赖 Story 1.17 | **P0-19（CFO ROI 验证）** |

**✅ 依赖关系验证：**
- Epic 1 内部故事依赖均为**组内依赖**，不依赖其他 Epic
- Epic 1 是所有其他 Epic 的**基础依赖**，必须首先完成
- 价值组 1（Iteration 0 + 1）→ 价值组 2（架构基础）→ 价值组 3（六层存储）→ 价值组 4（安全合规）→ 价值组 5（or.md 公理）→ 价值组 6（MVP 关键机制增强）
- 价值组 1（Iteration 0 + 1）可独立交付
- 价值组 2-6 依赖价值组 1 和 2 的架构基础

**📋 Epic 0 和 or.md 追溯说明：**
- **Story 0.1-0.3**：Iteration 0（开发环境、CI/CD、测试框架），必须在 Story 1 前完成
- **Story 0.4-0.9/0.14-0.18**：Iteration 1（开发环境、CI/CD、测试框架），必须在 Story 1 前完成
- **Story 0.2**：CI/CD 流水线是所有 Epic 的前置依赖（自动化构建、测试、部署）
- **Story 1.13**：覆盖 NFR-SCALE-03（Agent 动态扩缩容，基于负载自动伸缩，响应时间<5 分钟）
- **Story 1.14a/b/c**：覆盖 or.md 系统公理一（自主调用：auto-trigger→auto-route→auto-execute）
- **Story 1.15a/b**：覆盖 or.md 系统公理二（外部化记忆：LLM 上下文=缓存，磁盘记忆=真相源）
- **Story 1.16**：集成测试框架，支持所有 Epic 的集成测试和 E2E 测试
- **Story 1.17**：覆盖 ARCH UDMR 基础路由（云端优先静态配置，本地兜底）
- **Story 1.18a**：覆盖 ARCH Prefect（Prefect 3.6+ 数据管道：文档处理/RAG 索引/报告生成）
- **Story 1.18b**：覆盖 ARCH LangGraph（LangGraph 1.0+ Agent 编排：BLM 规划/Agent 协作）
- **Story 1.19**：覆盖 CFO ROI 验证（Token 消耗追踪、成本统计，依赖 Story 1.17 UDMR 路由日志）

---

### Story 0.1: 开发环境搭建

As a **开发工程师**,
I want **统一的开发环境和工具链（Python 3.11+, Poetry, Docker, IDE 配置，SDD 工具链）**,
So that **团队可以高效协作开发，并遵循规范驱动开发流程**。

**Acceptance Criteria:**

**Given** 新项目启动
**When** 运行 `docker-compose up` 和 `poetry install`
**Then** 所有开发依赖安装完成，包括：
- Python 3.11+、Poetry、Docker
- SDD 工具链（pydantic、schemathesis、pytest-bdd、openapi-spec-validator）
- 代码质量工具（ruff、mypy、pytest、pytest-cov）
**And** IDE 配置（.vscode/.idea）提供代码规范、调试配置、SDD 工作流支持
**And** Makefile 命令可用（make setup、make lint、make type-check、make test、make dev）
**And** pre-commit 钩子安装完成（validate-schemas、validate-openapi、pytest-bdd）

**SDD 实施检查清单（开发前）：**
- [ ] 领域事件 Schema 已定义并评审通过
- [ ] API 契约（OpenAPI）已定义并验证通过
- [ ] 测试用例（Gherkin）已编写并业务方确认
- [ ] 数据模型（SQLAlchemy）已定义并评审通过
- [ ] Qwen Code Agent 已激活并理解规范

**SDD 实施检查清单（开发后）：**
- [ ] Schema 验证通过（pydantic validate）
- [ ] 契约测试通过（Schemathesis）
- [ ] 验收测试通过（pytest-bdd）
- [ ] 类型检查通过（mypy）
- [ ] 代码质量检查通过（ruff）
- [ ] 测试覆盖率达标（≥80%）

### Story 0.2: CI/CD 流水线

As a **DevOps 工程师**,
I want **自动化构建、测试和部署的 CI/CD 流水线**,
So that **代码变更可以快速、可靠地发布**。

**Acceptance Criteria:**

**Given** 代码提交到 Git
**When** 触发 CI/CD 流水线（GitHub Actions / GitLab CI）
**Then** 执行以下 5 个阶段：

**阶段 1: 代码质量门禁**
- 运行 `ruff check src/ tests/`（阻断：严重错误>0）
- 运行 `mypy src/`（阻断：错误率>5%）
- 运行 `ruff format --check src/ tests/`（阻断：格式错误>0）

**阶段 2: 单元测试**
- 运行 `pytest tests/unit/ --cov=src --cov-fail-under=80`
- 生成覆盖率报告（XML/HTML）
- 阻断：覆盖率<80% 或测试失败

**阶段 3: 集成测试**
- 启动 Docker Compose 测试环境
- 运行 `pytest tests/integration/`
- 阻断：测试失败

**阶段 4: 安全扫描**
- 运行 `snyk test`（依赖漏洞扫描）
- 运行 `bandit -r src/`（代码安全扫描）
- 阻断：高危漏洞>0

**阶段 5: 构建与部署**
- 构建 Docker 镜像（`docker build -t sisys:commit_sha .`）
- 推送镜像到仓库
- 部署到测试环境（K8s / Docker Swarm）
- 运行健康检查

**And** 所有门禁检查通过后才允许合并代码
**And** 失败时发送通知（Slack / 邮件）
**And** 所有 Epic 的构建和部署都通过此流水线执行

**质量门禁验收标准：**

| 门禁类型 | 工具 | 阈值 | 阻断级别 |
|---------|------|------|---------|
| Ruff 代码检查 | ruff check | 严重错误=0 | P0 阻断 |
| Ruff 格式检查 | ruff format | 格式错误=0 | P0 阻断 |
| MyPy 类型检查 | mypy | 错误率<5% | P0 阻断 |
| 单元测试覆盖率 | pytest-cov | 整体≥80% | P0 阻断 |
| 领域层覆盖率 | pytest-cov | ≥90% | P1 阻断 |
| 应用层覆盖率 | pytest-cov | ≥85% | P1 阻断 |
| 安全漏洞扫描 | snyk/bandit | 高危=0 | P0 阻断 |
| 渗透测试 | OWASP Top 10 | 高危=0, 中危<5 | P0 阻断 |

### Story 0.3: 测试框架搭建

As a **测试工程师**,
I want **单元测试、集成测试框架和测试数据管理**,
So that **可以快速编写和执行测试用例**。

**Acceptance Criteria:**

**Given** 项目初始化完成
**When** 运行 `pytest`
**Then** 单元测试、集成测试框架可正常运行
**And** 测试数据管理支持（Fixture、Mock、测试数据库隔离）
**And** 覆盖率报告生成（HTML/XML）
**And** 测试失败时提供详细错误信息和堆栈跟踪
**And** 支持 pytest-bdd 格式（Given-When-Then）
**And** 支持测试标记（unit/integration/contract/acceptance）

**测试框架配置：**
- pytest.ini / pyproject.toml：pytest 配置
- conftest.py：全局 Fixture 定义
- tests/fixtures/：测试数据 Fixture
- tests/conftest.py：数据库隔离、Mock 配置

**测试覆盖率要求：**
- 整体覆盖率：≥80%
- 领域层覆盖率：≥90%
- 应用层覆盖率：≥85%
- CI/CD 门禁：--cov-fail-under=80 强制执行

### Story 0.4: K3S 集群部署

**As a** DevOps 工程师,
**I want** 在高性能 PC 上部署 K3S 集群,
**So that** 提供轻量级 K8s 运行时环境。

**Acceptance Criteria:**

**Given** 13700K + 32G RAM + 1T SSD + 10T HDD 系统
**When** 运行 K3S 安装脚本
**Then** K3S v1.34.5 安装成功
**And** Longhorn 存储配置完成
**And** Traefik 反向代理配置完成
**And** 集群健康检查通过

**技术栈:**
- K3S v1.34.5
- Longhorn v1.5.3
- Traefik v3.x

**TDD 测试要求:**
1. 集群部署测试 - 验证 K3S 安装成功
2. 存储配置测试 - 验证 Longhorn 可用
3. 网络配置测试 - 验证 Traefik 路由正常

**实施指南:** `docs/deploy/K3S_CLUSTER_SETUP.md`

---

### Story 0.5: Gitea 代码托管

**As a** 开发工程师,
**I want** 部署 Gitea v1.25.4 代码托管平台,
**So that** 团队可以进行代码版本管理和协作。

**Acceptance Criteria:**

**Given** K3S 集群已部署
**When** 运行 Gitea Helm Chart
**Then** Gitea v1.25.4 部署成功
**And** PostgreSQL 数据库配置完成
**And** HTTPS 证书配置完成
**And** 初始管理员账号创建成功

**技术栈:**
- Gitea v1.25.4 ✅ (已验证)
- PostgreSQL 15
- Helm v3

**TDD 测试要求:**
1. Gitea 部署测试 - 验证服务可访问
2. 数据库连接测试 - 验证 PostgreSQL 集成
3. HTTPS 配置测试 - 验证证书有效

**实施指南:** `docs/deploy/GITEA_INSTALLATION.md`

---

### Story 0.6: Harbor 镜像仓库

**As a** DevOps 工程师,
**I want** 部署 Harbor v2.14.3 镜像仓库,
**So that** 团队可以安全存储和分发 Docker 镜像。

**Acceptance Criteria:**

**Given** K3S 集群已部署
**When** 运行 Harbor Helm Chart
**Then** Harbor v2.14.3 部署成功
**And** 镜像仓库配置完成
**And** Trivy 漏洞扫描配置完成
**And** 镜像签名配置完成

**技术栈:**
- Harbor v2.14.3 ✅
- Trivy (漏洞扫描)
- Cosign (镜像签名)

**TDD 测试要求:**
1. Harbor 部署测试 - 验证服务可访问
2. 镜像推送测试 - 验证镜像可以推送
3. 漏洞扫描测试 - 验证 Trivy 集成

**实施指南:** `docs/deploy/HARBOR_INSTALLATION.md`

---

### Story 0.7: ArgoCD 持续部署

**As a** DevOps 工程师,
**I want** 部署 ArgoCD v3.2.7 持续部署工具,
**So that** 实现 GitOps 自动化部署。

**Acceptance Criteria:**

**Given** K3S 集群已部署
**When** 运行 ArgoCD 安装脚本
**Then** ArgoCD v3.2.7 部署成功
**And** Git 仓库集成配置完成
**And** 多环境 (Dev/Test/Prod) 配置完成
**And** 自动同步策略配置完成

**技术栈:**
- ArgoCD v3.2.7 ✅ (已验证)
- Git (代码仓库)
- Kustomize/Helm

**TDD 测试要求:**
1. ArgoCD 部署测试 - 验证服务可访问
2. Git 集成测试 - 验证仓库连接
3. 自动同步测试 - 验证 GitOps 流程

**实施指南:** `docs/deploy/ARGOCD_SETUP.md`

---

### Story 0.8: Gitea Runner 配置

**As a** DevOps 工程师,
**I want** 配置 Gitea Runner 执行 CI/CD 任务,
**So that** 代码提交后自动触发构建和测试。

**Acceptance Criteria:**

**Given** Gitea 和 K3S 已部署
**When** 注册 Gitea Runner
**Then** Runner 注册成功
**And** Docker Executor 配置完成
**And** Kubernetes Executor 配置完成 (可选)
**And** 并发控制配置完成

**技术栈:**
- Gitea Runner (最新版)
- Docker Executor (稳定)
- Kubernetes Executor (实验性)

**TDD 测试要求:**
1. Runner 注册测试 - 验证 Runner 在线
2. Docker Executor 测试 - 验证容器构建
3. K8s Executor 测试 - 验证 Pod 调度

**实施指南:** `docs/deploy/GITEA_RUNNER_SETUP.md`

---

### Story 0.9: CI/CD Pipeline 模板

**As a** 开发工程师,
**I want** 创建标准化的 CI/CD Pipeline 模板,
**So that** 所有项目可以复用最佳实践。

**Acceptance Criteria:**

**Given** Gitea + Runner + Harbor + ArgoCD 已部署
**When** 创建新项目
**Then** 可以复用 CI/CD 模板
**And** 包含代码质量检查
**And** 包含单元测试
**And** 包含集成测试
**And** 包含安全扫描
**And** 包含镜像构建
**And** 包含自动部署

**Pipeline 阶段:**
1. 代码质量门禁 (Ruff + MyPy)
2. 单元测试 (pytest + 覆盖率)
3. 集成测试 (Docker Compose)
4. 安全扫描 (Trivy + Bandit)
5. 镜像构建 (Docker Build)
6. 镜像推送 (Harbor)
7. 自动部署 (ArgoCD)

**实施指南:** `docs/deploy/CI_CD_PIPELINE_TEMPLATE.md`

---

### Story 0.14: Windows 安装包

**As a** SISYS 客户 (企业用户),
**I want** 通过图形化安装包在 Windows PC 上部署 SISYS,
**So that** 无需专业技术知识即可使用。

**Acceptance Criteria:**

**Given** Windows 10/11 高性能 PC
**When** 双击 sisys-setup.exe
**Then** 安装向导启动
**And** 自动检测 Docker (如未安装则自动安装)
**And** 自动配置端口和存储
**And** 5 分钟内完成部署
**And** 自动打开浏览器显示访问地址

**安装包内容:**
- sisys-setup.exe (150MB)
- 包含 Docker Desktop 安装包
- 包含 SISYS 产品镜像
- 包含自动配置脚本

**用户体验:**
1. 双击运行
2. 点击"下一步"
3. 等待 5 分钟
4. 完成！自动打开浏览器

**实施指南:** `docs/delivery/WINDOWS_INSTALLER.md`

---

### Story 0.15: Mac 安装包

**As a** SISYS 客户 (Mac 用户),
**I want** 通过 DMG 安装包在 macOS 上部署 SISYS,
**So that** 无需专业技术知识即可使用。

**Acceptance Criteria:**

**Given** macOS 12+ 高性能 Mac
**When** 打开 sisys-cicd.dmg
**Then** 拖拽到 Applications 即可
**And** 自动安装依赖
**And** 自动启动服务
**And** 自动打开浏览器

**安装包内容:**
- sisys-cicd.dmg (150MB)
- 包含 Docker Desktop 安装包
- 包含 SISYS 产品镜像
- 包含自动启动脚本

**实施指南:** `docs/delivery/MAC_INSTALLER.md`

---

### Story 0.16: Linux 一键脚本

**As a** SISYS 客户 (Linux 用户),
**I want** 通过一键脚本在 Linux 服务器上部署 SISYS,
**So that** 无需手动配置即可使用。

**Acceptance Criteria:**

**Given** Ubuntu 22.04 / Debian 11+ / CentOS 9
**When** 运行 `curl -sSL https://sisys.example.com/install.sh | bash`
**Then** 自动检测系统和依赖
**And** 自动安装 Docker
**And** 自动拉取镜像
**And** 自动启动服务
**And** 显示访问地址和密码

**脚本功能:**
- 系统检测
- 依赖安装
- 镜像拉取 (国内加速)
- 端口检测 (自动避让)
- 服务启动
- 密码显示

**实施指南:** `docs/delivery/LINUX_INSTALLER.md`

---

### Story 0.17: 自动检测与修复

**As a** SISYS 客户 (技术小白),
**I want** 安装过程自动检测和修复问题,
**So that** 遇到问题时不会卡住。

**Acceptance Criteria:**

**Given** 安装过程中
**When** 检测到问题
**Then** 自动尝试修复
**And** 修复失败时提供人话提示

**自动修复场景:**
1. 端口被占用 → 自动切换端口
2. 镜像下载失败 → 切换国内镜像源
3. 磁盘空间不足 → 提前预警并建议清理
4. 服务启动失败 → 自动重启并诊断

**人话提示示例:**
❌ 错误：Port 3000 already in use
✅ 提示：端口 3000 被占用，已自动改用 3001 端口

**实施指南:** `docs/delivery/AUTO_DIAGNOSE_AND_FIX.md`

---

### Story 0.18: 用户友好配置向导

**As a** SISYS 客户 (非技术人员),
**I want** 通过图形化向导配置系统,
**So that** 无需修改 YAML 配置文件。

**Acceptance Criteria:**

**Given** 安装完成后
**When** 打开配置向导
**Then** 显示图形化界面
**And** 提供预设配置模板
**And** 支持自定义配置
**And** 配置一键生效

**配置向导界面:**
```
┌────────────────────────────────────┐
│  Sisys 配置向导                     │
├────────────────────────────────────┤
│  设置管理员账号：                   │
│  用户名：[admin        ]           │
│  密码：  [••••••••    ]           │
│  邮箱：  [admin@example.com]      │
├────────────────────────────────────┤
│  选择安装路径：                     │
│  [C:\sisys              ] [浏览]  │
├────────────────────────────────────┤
│  选择端口：                         │
│  Gitea:  [3000]                   │
│  Harbor: [8080]                   │
│  ArgoCD: [8088]                   │
├────────────────────────────────────┤
│      [取消]        [应用]          │
└────────────────────────────────────┘
```

### Story 0.30: 应用启动集成

As a **DevOps 工程师**,
I want **系统启动后所有服务组件可用并可验证**,
So that **用户可以正常使用系统所有功能**。

**Acceptance Criteria:**

**Given** Epic 0 Iteration 1 所有基础设施组件已部署（K3S/Gitea/Harbor/ArgoCD）
**When** 执行应用一键启动
**Then** 所有服务健康检查通过
**And** 服务间连通性验证通过
**And** 基础功能端到端可用（CLI 命令执行 / REST API 响应 / 文档上传）

**TDD 测试要求:**
1. **集成测试**
   - [ ] 服务健康检查测试 - 验证所有组件可用（K3S/Gitea/Harbor/ArgoCD/PostgreSQL/Redis）
   - [ ] 服务连通性测试 - 验证组件间网络通信正常
   - [ ] CLI 端到端测试 - 验证 `sisys system health` 命令正确返回各服务状态
   - [ ] REST API 端到端测试 - 验证 `/api/v1/health` 返回 200

2. **性能要求**
   - [ ] 系统启动时间 <5 分钟
   - [ ] 健康检查响应延迟 P95 < 500ms

3. **覆盖率要求**
   - 集成测试覆盖率 >= 75%

### Story 1.1: 六边形架构骨架

As a **系统架构师**,
I want **实现领域驱动六边形架构骨架**,
So that **领域逻辑与技术实现隔离，支持独立演进和测试**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构约束测试**
   - [ ] 领域层零依赖测试（FR-AR-01）- 验证领域层仅使用 Python 标准库
   - [ ] 依赖方向测试 - 验证基础设施层→应用层→领域层的依赖方向
   - [ ] 基础设施层不依赖接口层测试 - 验证 infrastructure 不 import interfaces
   - [ ] 应用层不依赖基础设施层测试 - 验证 application 不 import infrastructure
   - [ ] 接口层不依赖基础设施层测试 - 验证 interfaces 不 import infrastructure
   - [ ] 导入检查测试 - 使用 ast 模块扫描导入语句

2. **覆盖率要求**
   - [ ] 领域层覆盖率≥90%
   - [ ] 应用层覆盖率≥85%
   - [ ] 整体覆盖率≥80%

3. **代码质量**
   - [ ] Ruff 检查通过（严重错误=0）
   - [ ] MyPy 类型检查通过（错误率<5%）
   - [ ] 安全扫描通过（高危漏洞=0）

4. **测试文件**
   - [ ] `tests/unit/architecture/test_hexagonal_architecture.py` - 架构约束测试
   - [ ] `tests/unit/domain/test_strategic_plan.py` - 领域实体测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - TDD 红 - 绿 - 重构循环

**Given** 项目初始化完成
**When** 创建领域层、应用层、接口层、基础设施层目录结构
**Then** 领域层仅依赖 Python 标准库，不包含任何外部框架导入
**And** 各层之间依赖方向正确（基础设施层→应用层→领域层）

### Story 1.2: 领域事件定义

As a **领域工程师**,
I want **定义核心领域事件（DocumentProcessed, ToolExecuted, AgentDecided, CheckpointReached, CorrectionApproved）**,
So that **系统支持事件驱动架构和事件溯源**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **领域事件测试**
   - [ ] DomainEvent 基类测试 - 验证 event_id、occurred_on、aggregate_id
   - [ ] 事件子类测试 - 验证自定义事件类型正确继承
   - [ ] 事件序列化测试 - 验证事件可以序列化和反序列化

2. **覆盖率要求**
   - [ ] 领域事件层覆盖率≥90%
   - [ ] 事件发布测试覆盖率≥85%

3. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 事件 Schema 通过验证

4. **测试文件**
   - [ ] `tests/unit/domain/events/test_events_base.py` - 事件基类测试
   - [ ] `tests/unit/domain/events/test_plan_events.py` - 计划事件测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 领域事件测试示例

**Given** 领域层已创建
**When** 定义领域事件的 Schema（事件 ID、类型、时间戳、载荷、来源、Schema 版本、聚合根 ID、聚合根类型、版本号）
**Then** 所有事件继承自统一的 DomainEvent 基类
**And** 领域层中的 Domain Event 必须使用标准库类型定义，不依赖 Pydantic 或其他第三方库
**And** Pydantic 仅用于应用层/基础设施层的边界校验、序列化与反序列化
**And** 领域事件与传输 DTO 必须分离，必要时通过 TypeAdapter 做无样板转换
**And** 事件 Schema 通过验证

### Story 1.3: 事件总线实现

As a **后端工程师**,
I want **实现双通道事件总线（Redis 发布/订阅 + RabbitMQ + 事务发件箱）**,
So that **实时事件低延迟路由，持久化事件可靠传输**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **事件总线测试**
   - [ ] Redis 发布/订阅测试 - 验证实时事件传输延迟<50ms
   - [ ] RabbitMQ 持久化测试 - 验证事件 100% 可靠传输
   - [ ] 事务发件箱测试 - 验证事件与业务操作原子性

2. **性能要求**
   - [ ] 实时事件延迟 P95<50ms
   - [ ] 持久化事件成功率 100%
   - [ ] 事件总线吞吐量≥1000 事件/秒

3. **覆盖率要求**
   - [ ] 领域层覆盖率≥90%（事件发布端口接口定义在 domain 层）
   - [ ] 事件总线层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_event_bus.py` - 事件总线单元测试
   - [ ] `tests/integration/test_integration_event_bus.py` - 事件总线集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - 集成测试要求

**Given** 领域事件已定义
**When** 发布领域事件至事件总线
**Then** 实时通知型事件通过 Redis 发布/订阅通道传输（延迟<50ms）
**And** 持久化事件通过 PostgreSQL event_outbox 表 + RabbitMQ 传输（100% 可靠）
**And** 支持 10 种领域事件监听（DocumentProcessed/ToolExecuted/AgentDecided/CheckpointReached/CorrectionApproved/StrategicDeviationWarning/HeartbeatTriggered/IsolationLevelSwitched/CheckpointRecovered/RoutingDecided）
**And** 事件处理幂等性保证：基于 event_id 的 Redis 缓存检查（TTL 7 天），事件处理成功率≥99%

### Story 1.4: 六层存储架构 - Redis 高速缓存层

As a **存储工程师**,
I want **实现 Redis 高速缓存层（会话状态、语义缓存、公共黑板）**,
So that **支持低延迟会话管理和语义缓存**。

**L1 Redis 缓存职责说明**：
- **会话状态缓存**：Agent 会话状态（TTL 24h-30d），由 Story 6.3 Checkpoint 写入
- **语义缓存**：RAG 检索加速（相似度>0.9 命中，TTL 24h），由 Epic 3 实现
- **公共黑板**：多 Agent 共享中间状态（TTL 1h），由 Epic 5 Agent 协作写入
- **注意**：记忆系统 L1 缓存由 Story 1.15b 独立管理（memory:xxx key）

**Acceptance Criteria:**

**TDD 测试要求:**

1. **基础设施测试**
   - [ ] Redis 连接测试 - 验证连接池
   - [ ] 序列化测试 - 验证对象序列化/反序列化
   - [ ] TTL 测试 - 验证过期策略

2. **性能要求**
   - [ ] 序列化/反序列化时间<10ms
   - [ ] 读取延迟 P95<5ms
   - [ ] 写入延迟 P95<10ms

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_redis_cache.py` - 单元测试
   - [ ] `tests/integration/test_integration_redis.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - 基础设施测试要求

**Given** Redis 7.0+ 已部署
**When** 存储会话状态快照至 Redis Hash
**Then** 序列化/反序列化时间<10ms，TTL 可配置（24h-30d）
**And** 支持主从复制与故障转移

### Story 1.5: 六层存储架构 - PostgreSQL 关系存储层

As a **存储工程师**,
I want **实现 PostgreSQL 关系存储层（用户/RBAC、审计元数据、业务实体）**,
So that **支持 ACID 事务和外键约束**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **基础设施测试**
   - [ ] 数据库连接测试 - 验证连接池
   - [ ] 事务测试 - 验证 ACID 特性
   - [ ] 迁移测试 - 验证 Alembic 迁移

2. **性能要求**
   - [ ] 查询延迟 P95<50ms
   - [ ] 事务提交成功率 100%
   - [ ] 并发连接支持≥100
   - [ ] 数据备份测试 - 验证每日全量 + 实时增量备份执行
   - [ ] RPO 测试 - 验证恢复点目标 <1 小时
   - [ ] RTO 测试 - 验证恢复时间目标 <4 小时

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_postgresql.py` - 单元测试
   - [ ] `tests/integration/test_integration_postgresql.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - 基础设施测试要求

**Given** PostgreSQL 15+ 已部署
**When** 创建用户表、角色表、权限表、审计日志表、业务实体表
**Then** 所有表通过外键约束关联，支持 ACID 事务
**And** 使用 Alembic 管理数据库迁移
**And** 支持 Schema per Tenant 多租户隔离（每个租户独立 Schema）
**And** 业务实体表启用 Row-Level Security（RLS）策略，确保租户间数据隔离（NFR-SCALE-04）

### Story 1.6: 六层存储架构 - Qdrant 向量存储层

As a **存储工程师**,
I want **实现 Qdrant 向量存储层（嵌入向量、混合检索 payload）**,
So that **支持混合检索（Dense + Sparse + Payload 过滤）**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **基础设施测试**
   - [ ] Qdrant 连接测试 - 验证 Collection 创建
   - [ ] 向量插入测试 - 验证嵌入向量存储
   - [ ] 检索测试 - 验证相似度搜索

2. **性能要求**
   - [ ] 向量插入延迟 P95<20ms
   - [ ] 检索延迟 P95<200ms
   - [ ] 支持并发查询≥50

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_qdrant.py` - 单元测试
   - [ ] `tests/integration/test_integration_qdrant.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - 基础设施测试要求

**Given** Qdrant 1.7+ 已部署
**When** 存储 bge-m3 嵌入向量（维度 1024）至 Collection
**Then** 支持 COSINE 相似度度量和 Payload 过滤
**And** 混合检索延迟 P95<200ms（初检）

### Story 1.7: 六层存储架构 - MinIO 对象存储层

As a **存储工程师**,
I want **实现 MinIO 对象存储层（原始文档、证据包、审计归档）**,
So that **支持版本控制和 WORM 存储**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **基础设施测试**
   - [ ] MinIO 连接测试 - 验证 Bucket 创建
   - [ ] 文件上传测试 - 验证分片上传
   - [ ] WORM 测试 - 验证对象锁定

2. **性能要求**
   - [ ] 上传延迟 P95<100ms
   - [ ] 下载延迟 P95<50ms
   - [ ] 支持并发上传≥20

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_minio.py` - 单元测试
   - [ ] `tests/integration/test_minio_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - 基础设施测试要求

**Given** MinIO 已部署
**When** 上传文档至 Bucket
**Then** 支持分片上传和断点续传，版本控制启用
**And** 审计日志 Bucket 启用 Object Lock（COMPLIANCE 模式，保留期限 7 年）

### Story 1.8: 六层存储架构 - Neo4j 图存储层

As a **存储工程师**,
I want **实现 Neo4j 图存储层（知识图谱、实体关系、依赖图）**,
So that **支持 GraphRAG 增强检索和实体关联查询**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **基础设施测试**
   - [ ] Neo4j 连接测试 - 验证图数据库连接
   - [ ] 节点创建测试 - 验证实体节点
   - [ ] 关系创建测试 - 验证关系边

2. **性能要求**
   - [ ] 简单查询延迟 P95<200ms
   - [ ] 复杂查询延迟 P95<800ms
   - [ ] 支持并发查询≥30

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_neo4j.py` - 单元测试
   - [ ] `tests/integration/test_integration_neo4j.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - 基础设施测试要求

**Given** Neo4j 5.x 已部署
**When** 创建实体节点和关系边
**Then** 支持 Cypher 查询（实体关联查询、路径查询）
**And** 简单图遍历查询延迟 P95<200ms

### Story 1.9: RBAC 权限管理

As a **安全工程师**,
I want **实现用户认证与 RBAC 权限管理**,
So that **系统支持细粒度访问控制**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **安全测试**
   - [ ] 认证测试 - 验证身份验证
   - [ ] 授权测试 - 验证权限控制
   - [ ] 越权访问测试 - 验证无法越权访问

2. **合规要求**
   - [ ] 权限测试 100% 通过
   - [ ] 越权访问 0 次
   - [ ] 安全扫描通过（高危漏洞=0）

3. **覆盖率要求**
   - [ ] 安全层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 安全扫描通过

5. **测试文件**
   - [ ] `tests/unit/security/test_rbac.py` - 单元测试
   - [ ] `tests/integration/test_security_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - 安全测试要求

**Given** PostgreSQL 用户表已创建
**When** 用户登录并获取 JWT 令牌
**Then** 验证用户凭证，加载 RBAC 权限（用户 - 角色 - 权限关联）
**And** 权限测试 100% 通过，越权访问 0 次

### Story 1.10: 统一审计日志

As a **合规工程师**,
I want **实现统一审计日志（log_id/timestamp/actor/action_type/target_resource/old_value/new_value）**,
So that **满足等保 2.0 和 SOX 合规要求**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **安全测试**
   - [ ] 审计日志测试 - 验证日志记录
   - [ ] 检索测试 - 验证多维检索
   - [ ] 完整性测试 - 验证日志完整性

2. **合规要求**
   - [ ] 日志完整性 100%
   - [ ] 支持按时间/角色/任务类型检索
   - [ ] 等保 2.0 合规

3. **覆盖率要求**
   - [ ] 安全层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 安全扫描通过

5. **测试文件**
   - [ ] `tests/unit/security/test_audit_log.py` - 单元测试
   - [ ] `tests/integration/test_audit_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - 安全测试要求

**Given** 审计日志表已创建
**When** 记录用户操作至审计日志
**Then** 日志完整性 100%，支持按时间/角色/任务类型多维检索
**And** 审计日志写入 PostgreSQL（MVP），V2 升级至 WORM 存储

### Story 1.11: 数据主权隔离

As a **合规工程师**,
I want **实现数据主权隔离（敏感数据本地优先，外部网络调用需审计与白名单批准）**,
So that **满足数据安全法和 PIPL 要求**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **安全测试**
   - [ ] 数据主权测试 - 验证敏感数据本地优先
   - [ ] 白名单测试 - 验证外部调用校验
   - [ ] 跨境传输测试 - 验证审批流程

2. **合规要求**
   - [ ] 数据境内存储 100%
   - [ ] 跨境传输审批率 100%
   - [ ] PIPL 合规
   - [ ] 个人信息脱敏率 100%（敏感字段识别 + 脱敏规则执行验证）
   - [ ] 删除请求响应时间 <24 小时（SLA 监控）

3. **覆盖率要求**
   - [ ] 安全层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 安全扫描通过

5. **测试文件**
   - [ ] `tests/unit/security/test_data_sovereignty.py` - 单元测试
   - [ ] `tests/integration/test_data_sovereignty_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - 安全测试要求

**Given** 敏感数据标签已定义
**When** 处理敏感数据或发起外部网络调用
**Then** 敏感数据默认本地优先处理，外部调用需通过白名单校验
**And** 数据境内存储 100%，跨境传输审批率 100%

### Story 1.12: 等保 2.0 三级基础要求

As a **安全工程师**,
I want **实现等保 2.0 三级基础要求（身份鉴别/访问控制/安全审计/入侵防范/数据完整性/备份恢复）**,
So that **通过公安部指定测评机构测评**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **安全测试**
   - [ ] 身份鉴别测试 - 验证双因子认证
   - [ ] 访问控制测试 - 验证细粒度 RBAC
   - [ ] 安全审计测试 - 验证审计日志
   - [ ] 渗透测试 - 验证入侵防范

2. **合规要求**
   - [ ] 无高风险项
   - [ ] 中危漏洞<5 个
   - [ ] 等保 2.0 三级通过

3. **覆盖率要求**
   - [ ] 安全层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 安全扫描通过

5. **测试文件**
   - [ ] `tests/unit/security/test_equilibrium.py` - 单元测试
   - [ ] `tests/integration/test_security_compliance.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - 安全测试要求

**Given** 所有安全控制已实现
**When** 执行等保 2.0 测评
**Then** 无高风险项，中危漏洞<5 个
**And** 身份鉴别支持双因子认证，访问控制支持细粒度 RBAC

### Story 1.13: K8s 动态扩缩容

As a **运维工程师**,
I want **系统支持基于负载的自动扩缩容**,
So that **系统可以应对流量高峰并优化资源成本**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **基础设施测试**
   - [ ] K8s 连接测试 - 验证集群连接
   - [ ] 扩缩容测试 - 验证自动扩容
   - [ ] 缩容测试 - 验证自动缩容

2. **性能要求**
   - [ ] 响应时间<5 分钟
   - [ ] 扩容决策成功率≥95%
   - [ ] 缩容决策成功率≥95%

3. **覆盖率要求**
   - [ ] 基础设施层覆盖率≥75%
   - [ ] 集成测试覆盖率≥70%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 性能基准测试通过

5. **测试文件**
   - [ ] `tests/unit/infrastructure/test_k8s.py` - 单元测试
   - [ ] `tests/integration/test_k8s_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - 基础设施测试要求

**Given** 系统部署在 K8s 集群
**When** 负载增加（CPU>70% 或 请求队列>100）
**Then** 自动扩容 Pod 数量（响应时间<5 分钟）
**And** 负载降低后自动缩容

### Story 1.14a: 自主调用循环 - trigger 实现

As a **系统架构师**,
I want **实现领域事件/心跳事件触发机制**,
So that **系统可以基于事件或周期性心跳自主启动任务**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] 事件触发测试 - 验证领域事件触发
   - [ ] 心跳触发测试 - 验证周期性心跳
   - [ ] 上下文提取测试 - 验证 session_id 提取

2. **性能要求**
   - [ ] 触发延迟 P95<10ms
   - [ ] 上下文提取准确率 100%

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_trigger.py` - 单元测试
   - [ ] `tests/integration/test_integration_trigger.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 领域事件触发（DocumentProcessed/ToolExecuted/AgentDecided 等）或周期性心跳事件
**When** trigger 机制检测到事件
**Then** 解析事件类型，提取 session_id 和任务上下文
**And** 触发 route 机制（Story 1.14b）

### Story 1.14b: 自主调用循环 - route 实现

As a **系统架构师**,
I want **实现 session_id 哈希/语义路由机制**,
So that **任务可以路由至目标 Agent 或工具**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] 哈希路由测试 - 验证 session_id 哈希路由
   - [ ] 语义路由测试 - 验证语义相似度路由
   - [ ] 路由决策日志测试 - 验证日志存储

2. **性能要求**
   - [ ] 路由决策延迟 P95<50ms
   - [ ] 路由准确率≥95%

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_route.py` - 单元测试
   - [ ] `tests/integration/test_integration_route.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** trigger 机制传递的任务上下文
**When** route 机制执行
**Then** 基于 session_id 哈希或语义相似度路由至目标 Agent/工具
**And** 路由决策日志存储（任务 ID、时间戳、L1 结果、L2 评分、选定路由、成本、延迟）

### Story 1.14c: 自主调用循环 - execute 实现

As a **系统架构师**,
I want **实现会话命名空间执行与状态快照**,
So that **任务在隔离环境中执行，状态可持久化和恢复**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] 会话命名空间测试 - 验证隔离环境
   - [ ] 状态快照测试 - 验证状态持久化
   - [ ] 恢复测试 - 验证状态恢复

2. **性能要求**
   - [ ] 状态快照延迟 P95<50ms
   - [ ] 恢复成功率 100%
   - [ ] 沙箱隔离 100%

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_execute.py` - 单元测试
   - [ ] `tests/integration/test_integration_execute.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** route 机制传递的目标 Agent/工具
**When** execute 机制执行
**Then** 在会话命名空间中执行任务（Docker/gVisor 沙箱）
**And** 状态快照序列化至 Redis Hash（支持主从复制与故障转移，TTL 24h-30d）
**And** 执行完成后发布领域事件（DocumentProcessed/ToolExecuted/AgentDecided）

### Story 1.15a: 外部化记忆 - L1 显式确认压缩实现

As a **系统架构师**,
I want **实现 L1 显式确认压缩机制（用户主动说"记住..."）**,
So that **用户主动记忆得到持久化，上下文压缩率≥70%**。

**三层触发机制概述**（详见 architecture.md §11.2.6）：

| 层次 | 触发类型 | 触发条件 | 写入目标 | 版本 |
|------|---------|---------|---------|------|
| **L1 显式确认** | 用户主动 | 用户说"记住..."、"以后用 X" | L0 + L2 | **MVP（本 Story）** |
| **L2 语义建议** | 系统建议+用户确认 | 检测重复偏好 | L0 草稿（待确认） | V2 |
| **L3 压缩触发** | 系统自动 | Checkpoint 创建 | StrategicArchive | **Epic 6/Story 6.3** |

**核心实现内容：**
- **用户主动记忆（L1）**：用户说"记住 X"时触发
  1. 提取"记住 X"中的 X 作为记忆核心内容（轻量级提取，≤500 字）
  2. 压缩 X 至 ~150 字（保留核心语义，压缩率≥70%）
  3. **L0 文件系统写入**（同步，强一致）：写入 ~/.sisys/memory/*.md
  4. **L0 索引更新**（同步）：更新 MEMORY.md 索引
  5. **发布 MemoryChanged 事件**（事务发件箱）：写入 Outbox 表（同一事务）
  6. **MemoryChangedListener.handle() 异步消费**：
     - L1 Redis 缓存失效（同步，立即）：保证"上下文≠缓存"公理
     - L2 PostgreSQL 写入：`metadata_repository.upsert()` + `history_repository.append()`
     - L3 Qdrant 向量（按需，内容>500 tokens）：`vector_store.embed()`
     - L5 Neo4j 图谱（按需）：`entity_extractor.extract()`
- **L1 操作类型**：保存（记住）、删除（不要记住）、修改（改成）、查询（你记得什么）
- **L1 vs L3 分离**：L1 是用户主动触发（"记住..."），L3 是 Checkpoint 自动触发（Epic 6/Story 6.3）

**注意**：L3 Checkpoint 压缩由 Epic 6 / Story 6.3 实现（50K tokens → ~2K tokens），不在本故事范围内。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] L1 压缩测试 - 验证用户说"记住 X"时触发压缩
   - [ ] 压缩率测试 - 验证压缩率≥70%（允许误差 -5%）
   - [ ] 用户主动记忆流程测试 - 验证 MemoryService.save()
   - [ ] MemoryChanged 事件发布测试（is_automatic=False）
   - [ ] L1 四种操作测试 - 验证保存/删除/修改/查询

2. **性能要求**
   - [ ] L1 信息压缩率≥70%（信息压缩率 = 1 - 压缩后字符数/原始字符数，即 500 字输入压缩至≤150 字）
   - [ ] 语义保留率≥0.85（通过 LLM-as-Judge 评估压缩前后语义等价性，测试集≥20 条样本覆盖保存/修改/查询操作和 50/200/500 字长度）
   - [ ] 压缩延迟 P95<3s（LLM 语义压缩，测量方式：20 条样本集覆盖 50/200/500 字长度，P95 采样）
   - [ ] 记忆保存成功率 100%

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_context_compression.py` - 单元测试
   - [ ] `tests/integration/test_integration_compression.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 用户说"记住，以后用 bun 而不是 npm"
**When** 用户主动记忆触发 L1 显式确认压缩
**Then** 执行步骤：
  1. MemoryService.save() 保存用户记忆
  2. 提取"以后用 bun 而不是 npm"作为记忆核心（≤500 字）
  3. 压缩 X 至 ~150 字（压缩率≥70%）
  4. 写入 ~/.sisys/memory/*.md（实际内容）
  5. 更新 MEMORY.md 索引
  6. MemoryChanged 事件发布（is_automatic=False）
**And** 记忆持久化至 L0 文件系统 + L2 PostgreSQL
**And** LLM 上下文仅保留压缩后的相关信息

### Story 1.15b: 外部化记忆 - L0 记忆入口 + 六层存储协同实现

As a **系统架构师**,
I want **实现 L0 MEMORY.md 记忆入口与 L1-L5 六层存储协同**,
So that **记忆分离原则得到实现，磁盘记忆=真相源**。

**三层触发机制概述**（详见 architecture.md §11.2.6）：

| 层次 | 触发类型 | 触发条件 | 写入目标 | 版本 |
|------|---------|---------|---------|------|
| **L1 显式确认** | 用户主动 | 用户说"记住..."、"以后用 X" | L0 + L2 | **MVP（本 Story 聚焦 L1 CRUD）** |
| **L2 语义建议** | 系统建议+用户确认 | 检测重复偏好 | L0 草稿（待确认） | **V2（不在本 Story 范围）** |
| **L3 压缩触发** | 系统自动 | Checkpoint 创建 | StrategicArchive | **Epic 6/Story 6.3** |

**核心实现内容：**
- **L0 MEMORY.md**：索引入口（最多 200 行，超出自动截断保留最新）、路由策略、文本扫描
- **Private/Group 记忆分离**：
  - private 记忆：`~/.sisys/memory/*.md`（仅当前用户可见）
  - group 记忆：`~/.sisys/memory/group/*.md`（团队共享）
- **L2 PostgreSQL 表设计**：
  - `memory_metadata`：记忆元数据索引（name, description, type, path, version, mtime, owner, group_id）
  - `memory_change_history`：记忆变更历史（append-only，change_type: create/update/delete）
- **L1 CRUD 操作**：完整创建/读取/更新/删除，带版本冲突处理（乐观锁）
- **事件驱动**：MemoryChanged 事件触发元数据同步、缓存失效

**MemoryChanged 事件下游用例（MemoryChangedListener.handle()）**：
  - 在 Listener.handle() 中执行：
    1. **L1 Redis 缓存失效**（同步，立即）：`storage_coordinator.invalidate(layer="L1", ...)`
       - 保证"上下文≠缓存"公理
    2. **L2 PostgreSQL 写入**（通过 Repository 调用）：
       - `metadata_repository.upsert(event)` - 写入 memory_metadata
       - `history_repository.append(event)` - 记录 memory_change_history（append-only）
    3. **L3 Qdrant 向量**（按需，内容>500 tokens）：`vector_store.embed(event)`
    4. **L5 Neo4j 图谱**（按需，EntityExtractor）：`entity_extractor.extract(event)`
  - **L4 MinIO** 不在本流程范围内，由 Checkpoint 持久化流程独立触发（Story 6.3）

**RBAC 校验**：
  - private 记忆（group_id=NULL）：
    - 读取：验证当前用户是所有者（owner == user_id）
    - 写入：验证当前用户是所有者
  - group 记忆（group_id != NULL）：
    - 读取：验证当前用户是 group 成员
    - 写入：验证当前用户是 group 成员或有管理员权限
  - 校验失败：抛出 MemoryAccessDeniedError

**错误处理**：
  - VersionConflictError：并发更新同一记忆时，提示用户确认后强制覆盖
  - MemoryAccessDeniedError：RBAC 校验失败
  - MemoryNotFoundError：删除或更新不存在的记忆
  - StorageWriteError：L0/L2 写入失败，保留重试机制（最多 3 次）

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] L0 MEMORY.md 测试 - 验证索引、路由、文本扫描
   - [ ] L0 MEMORY.md 截断测试 - 验证超出 200 行时自动截断（保留最新 200 条，按 updated_at 倒序）
   - [ ] 六层存储测试 - 验证各层存储
   - [ ] 协同测试 - 验证层间单向依赖链
   - [ ] Private/Group 分离测试 - 验证权限隔离
   - [ ] CRUD 测试 - 验证完整记忆操作
   - [ ] 版本冲突测试 - 验证乐观锁处理

2. **性能要求**
   - [ ] Redis TTL 24h-30d（测量方式：redis TTL 命令验证）
   - [ ] MinIO WORM 7 年（测量方式：Object Lock 配置验证）
   - [ ] L0→L2 元数据同步延迟 <100ms（异步写入，不阻塞主流程）
   - [ ] 记忆保存成功率 100%（测量方式：memory_metadata 记录存在）

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_six_layer_storage.py` - 单元测试
   - [ ] `tests/integration/test_integration_storage.py` - 集成测试
   - [ ] `tests/unit/architecture/test_memory_crud.py` - CRUD 测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 用户通过 CLI 执行以下命令：
  - private 记忆：`sisys memory save "记住以后用 bun" --type feedback`
  - group 记忆：`sisys memory save "记住团队用 docker" --type feedback --group team-A`
**When** 六层存储协同机制执行
**Then** 执行步骤：
  1. 验证用户 RBAC 权限（private 验证所有者，group 验证成员）
  2. 写入记忆文件（private: ~/.sisys/memory/*.md, group: ~/.sisys/memory/group/*.md）
  3. 更新 MEMORY.md 索引（private 或 group 独立索引）
  4. 异步写入 memory_metadata（version=1, mtime=NOW(), owner/group_id）
  5. 异步写入 memory_change_history（change_type='create'）
  6. L1 Redis 缓存新记忆内容（TTL 24h-30d）
**And** L0→L2 元数据同步延迟 <100ms
**And** Private 记忆仅用户自己可写，Group 记忆团队共享
**And** MemoryChanged 事件触发 L2 元数据同步

### Story 1.16: 集成测试框架

As a **测试工程师**,
I want **集成测试、E2E 测试框架和测试数据管理**,
So that **可以快速编写和执行集成测试和 E2E 测试**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **测试框架**
   - [ ] 集成测试框架测试 - 验证跨组件测试
   - [ ] E2E 测试框架测试 - 验证 API/UI 测试
   - [ ] 测试数据管理测试 - 验证 Fixture/Mock

2. **覆盖率要求**
   - [ ] 集成测试覆盖率≥75%
   - [ ] E2E 测试覆盖率≥70%

3. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 测试框架文档完整

4. **测试文件**
   - [ ] `tests/integration/test_integration_framework.py` - 框架测试
   - [ ] `tests/e2e/test_e2e_framework.py` - E2E 框架测试

**实施指南:**
参考 `docs/developer/sdd-tdd-checklist.md` - 集成测试要求

**Given** 测试框架搭建完成（Story 0.3）
**When** 运行集成测试或 E2E 测试
**Then** 测试框架支持跨组件测试、API 测试、UI 测试
**And** 测试数据管理支持（Fixture、Mock、测试数据库隔离）
**And** 所有 Epic 的集成测试和 E2E 测试都通过此框架执行

### Story 1.17: UDMR 基础路由（云端优先静态配置）

As a **运维工程师**,
I want **配置云端/本地路由策略（云端优先静态配置）**,
So that **MVP 阶段支持云端优先路由，本地兜底，验证云端路由占比≥60%（V1 目标≥80%）**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] 路由策略测试 - 验证本地/云端路由
   - [ ] 故障切换测试 - 验证超时切换
   - [ ] 路由决策日志测试 - 验证日志存储

2. **性能要求**
   - [ ] 云端路由占比≥80%
   - [ ] 路由决策延迟 P95<100ms
   - [ ] 故障切换时间<30 秒

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_udmr.py` - 单元测试
   - [ ] `tests/integration/test_udmr_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 系统配置了本地模型（Ollama+Qwen2.5）和云端模型（MiniMax-M2.7/deepseek-v4-flash等主流模型）
**When** 执行 LLM 任务
**Then** 根据静态配置路由（云端优先；云端所有模型都不可用或超时>600 秒时切换本地；云端正常后恢复使用云端，每隔300秒检测云端是否健康）
**And** 记录路由决策日志（任务 ID、时间戳、选定路由、估计成本、实际成本、延迟）
**And** 路由决策延迟 P95<100ms（MVP 静态配置）

**依赖关系：** 依赖 Story 1.14b（路由决策日志）
**执行优先级：** P0-17（MVP，ARCH UDMR 基础）

### Story 1.18a: Prefect 工作流引擎集成

As a **系统架构师**,
I want **集成 Prefect 3.6+ 工作流引擎（数据管道）**,
So that **系统支持确定性数据流，包括文档处理、RAG 索引、报告生成**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] Prefect 工作流测试 - 验证数据管道
   - [ ] 任务编排测试 - 验证任务调度
   - [ ] 错误处理测试 - 验证失败重试

2. **性能要求**
   - [ ] 工作流执行延迟 P95<500ms
   - [ ] 任务调度准确率 100%
   - [ ] 失败重试成功率≥95%

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_prefect.py` - 单元测试
   - [ ] `tests/integration/test_prefect_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 架构骨架已实现（Story 1.1）
**When** 执行数据管道任务（文档处理/RAG 索引/报告生成）
**Then** Prefect 3.6+ 执行流程，支持任务重试、失败恢复、状态追踪
**And** 流程状态持久化至 Redis（TTL 24h-30d）
**And** 发布领域事件（DocProcessed/RAGIndexed/ReportGenerated）

**依赖关系：** 依赖 Story 1.1（架构骨架）、Story 1.3（事件总线）
**执行优先级：** P0-18a（MVP，ARCH Prefect）

### Story 1.18b: LangGraph Agent 编排集成

As a **系统架构师**,
I want **集成 LangGraph 1.0+ 工作流引擎（Agent 编排）**,
So that **系统支持认知密集型推理，包括 BLM 规划、Agent 协作、多视角分析**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] LangGraph 状态机测试 - 验证状态转换
   - [ ] 多 Agent 协作测试 - 验证协作机制
   - [ ] Checkpoint 测试 - 验证持久化

2. **性能要求**
   - [ ] 状态机执行延迟 P95<500ms
   - [ ] Agent 协作成功率≥90%
   - [ ] Checkpoint 成功率 100%

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_langgraph.py` - 单元测试
   - [ ] `tests/integration/test_langgraph_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 架构骨架已实现（Story 1.1），事件总线就绪（Story 1.3）
**When** 执行 Agent 编排任务（BLM 规划/Agent 协作/多视角分析）
**Then** LangGraph 1.0+ 执行状态机，支持多 Agent 协作、Checkpoint 机制
**And** Agent 状态持久化至 Redis（TTL 24h-30d）
**And** 发布领域事件（AgentDecided/CheckpointReached）
**And** 与 Prefect 通过编排服务协调（无直接耦合，通过领域事件通信）

**依赖关系：** 依赖 Story 1.1（架构骨架）、Story 1.3（事件总线）
**执行优先级：** P0-18b（MVP，ARCH LangGraph）

### Story 1.19: 成本度量基础（Token 消耗与成本追踪）

As a **运维工程师**,
I want **追踪每个任务的 Token 消耗和成本**,
So that **验证 MVP 路由效果并衡量 ROI，支持云端优先路由目标验证**。

**Acceptance Criteria:**

**TDD 测试要求:**

1. **架构测试**
   - [ ] Token 消耗测试 - 验证记录准确性
   - [ ] 成本计算测试 - 验证成本计算
   - [ ] 聚合查询测试 - 验证查询功能

2. **性能要求**
   - [ ] Token 记录准确率 100%
   - [ ] 成本计算准确率 100%
   - [ ] 查询延迟 P95<100ms

3. **覆盖率要求**
   - [ ] 应用层覆盖率≥85%
   - [ ] 集成测试覆盖率≥75%

4. **代码质量**
   - [ ] Ruff 检查通过
   - [ ] MyPy 类型检查通过
   - [ ] 架构约束验证

5. **测试文件**
   - [ ] `tests/unit/architecture/test_cost_metrics.py` - 单元测试
   - [ ] `tests/integration/test_cost_metrics_integration.py` - 集成测试

**实施指南:**
参考 `docs/developer/sdd-tdd-fusion-guide.md` - 架构层测试示例

**Given** 系统执行 LLM 任务
**When** 任务完成
**Then** 记录 Token 消耗（prompt_tokens + completion_tokens + total_tokens）
**And** 记录成本（基于模型单价计算：本地¥0.002/1K tokens，云端¥0.02/1K tokens）
**And** 健康度仪表盘显示 Token 消耗趋势和成本统计（Story 7.4 集成）
**And** 支持按任务类型/Agent/时间范围聚合查询

**依赖关系：** 依赖 Story 1.17（UDMR 基础路由）
**执行优先级：** P0-19（MVP，CFO ROI 验证）

---

## Epic 1 依赖关系存档（已完成，2026-05-29 存档）

以下内容原位于 `epics_v1.0.md` 的"📊 全部 Epic 依赖关系验证总结"章节，因 Epic 1 已完成而存档至此。

### Epic 1 开发阶段执行记录

**阶段 1: Epic 0 Iteration 1 冲刺 (2026-03-12 ~ 2026-03-30)** ✅ 已完成

| AI AGENT | 分配 Story | 预计工期 | 依赖关系 | 优先级 |
|---------|-----------|---------|---------|-------|
| **Agent-01** | Story 0.5 (Gitea) | 3 天 | Story 0.4 ✅ | P0 |
| **Agent-02** | Story 0.6 (Harbor) | 3 天 | Story 0.4 ✅ | P0 |
| **Agent-03** | Story 0.7 (ArgoCD) | 4 天 | Story 0.5 + Story 0.6 | P0 |
| **Agent-04** | Story 0.8 (Gitea Runner) | 3 天 | Story 0.5 | P0 |
| **Agent-05** | Story 0.9 (Pipeline 模板) | 5 天 | Story 0.7 + Story 0.8 | P0 |
| **Agent-06** | Story 0.14-0.18 (产品交付系统) | 5 天 | Story 0.4 ✅ | P1 |

**阶段 2: Epic 1 架构基础 (2026-04-01 ~ 2026-04-20)** ✅ 已完成

| AI AGENT | 分配 Story | 预计工期 | 依赖关系 | 优先级 |
|---------|-----------|---------|---------|-------|
| **Agent-01** | Story 1.1 (六边形架构) | 5 天 | Story 0.9 ✅ | P0 |
| **Agent-02** | Story 1.2 (领域事件) | 3 天 | Story 1.1 | P0 |
| **Agent-03** | Story 1.3 (事件总线) | 5 天 | Story 1.2 | P0 |
| **Agent-04** | Story 1.4 (Redis 缓存) | 4 天 | Story 0.9 ✅ | P0 |
| **Agent-05** | Story 1.5 (PostgreSQL) | 5 天 | Story 1.1 ✅ | P0 |
| **Agent-06** | Story 1.6 (Qdrant) | 4 天 | Story 1.1 ✅ | P0 |
| **Agent-07** | Story 1.7 (MinIO) | 3 天 | Story 1.1 ✅ | P0 |
| **Agent-08** | Story 1.8 (Neo4j) | 4 天 | Story 1.1 ✅ | P0 |

**阶段 3: Epic 1 安全合规与系统公理 (2026-04-21 ~ 2026-05-10)** ✅ 已完成

| AI AGENT | 分配 Story | 预计工期 | 依赖关系 | 优先级 |
|---------|-----------|---------|---------|-------|
| **Agent-01** | Story 1.9 (RBAC) | 4 天 | Story 1.5 ✅ | P0 |
| **Agent-02** | Story 1.10 (审计日志) | 4 天 | Story 1.9 | P0 |
| **Agent-03** | Story 1.11 (数据主权) | 3 天 | Story 1.10 | P0 |
| **Agent-04** | Story 1.12 (等保 2.0) | 5 天 | Story 1.11 | P0 |
| **Agent-05** | Story 1.14a/b/c (自主调用) | 5 天 | Story 1.3 ✅ | P0 |
| **Agent-06** | Story 1.15a/b (外部化记忆) | 5 天 | Story 1.14c | P0 |
| **Agent-07** | Story 1.17 (UDMR 路由) | 4 天 | Story 1.14b | P0 |
| **Agent-08** | Story 1.18a (Prefect) | 5 天 | Story 1.3 ✅ | P0 |
| **Agent-09** | Story 1.18b (LangGraph) | 5 天 | Story 1.3 ✅ | P0 |
| **Agent-10** | Story 1.19 (成本度量) | 3 天 | Story 1.17 | P1 |

### Epic 1 关键依赖路径（已完成）

**关键路径 1: Epic 0 Iteration 1** ✅ 已完成

```
Story 0.17 (自动诊断修复 - ready-for-dev)
Story 0.18 (配置向导 - ready-for-dev)
Story 0.30 (应用启动集成 - ready-for-dev)
```

**关键路径 2: Epic 1 安全合规** ✅ 已完成

```
Story 1.9 (RBAC 权限 - ✅ Done)
  → Story 1.10 (审计日志 - ✅ Done)
  → Story 1.11 (数据主权隔离 - ✅ Done)
  → Story 1.12 (等保 2.0 三级 - ✅ Done)
```

**关键路径 3: Epic 1 外部化记忆与工作流引擎** ✅ 已完成

```
Story 1.15b (外部化记忆协同 - ✅ Done)
  → Story 1.18a (Prefect 工作流 - ✅ Done)
  → Story 1.19 (成本度量 - ✅ Done)
Story 1.3 (事件总线 - ✅ Done)
  → Story 1.18b (LangGraph 编排 - ✅ Done)
```

**关键路径 4: Epic 1 六层存储** ✅ 已完成

```
Story 1.1 (六边形架构)
  ├→ Story 1.4 (Redis) ─────→ Story 1.7 (MinIO) ──→ Story 1.8 (Neo4j)
  ├→ Story 1.5 (PostgreSQL) ─→ Story 1.6 (Qdrant) ─┘
  └→ Story 1.2 (领域事件) → Story 1.3 (事件总线)
```

### Epic 1 详细依赖矩阵（已完成）

**Epic 0 Iteration 1 依赖矩阵**

| Story | 前置依赖 | 后置依赖 | 依赖类型 | 关键路径 |
|-------|---------|---------|---------|---------|
| **0.4** (K3S) | 0.1, 0.3 ✅ | 0.5, 0.6, 0.7, 0.8, 0.14-0.18, 0.30 | Hard | ✅ 已完成 |
| **0.5** (Gitea) | 0.4 ✅ | 0.7, 0.8, 0.9 ✅ | Hard | ✅ 已完成 |
| **0.6** (Harbor) | 0.4 ✅ | 0.7, 0.9 ✅ | Hard | ✅ 已完成 |
| **0.7** (ArgoCD) | 0.5, 0.6 ✅ | 0.9 ✅ | Hard | ✅ 已完成 |
| **0.8** (Runner) | 0.5 ✅ | 0.9 ✅ | Hard | ✅ 已完成 |
| **0.9** (Pipeline) | 0.7, 0.8 ✅ | Epic 1 所有 Story | Hard | ✅ 已完成 |
| **0.14** (Windows) | 0.4 ✅ | - | Soft | ✅ 已完成 |
| **0.15** (Mac) | 0.4 ✅ | - | Soft | ✅ 已完成 |
| **0.16** (Linux) | 0.4 ✅ | - | Soft | ✅ 已完成 |
| **0.17** (自动诊断) | 0.4 ✅ | - | Soft | 📋 ready-for-dev |
| **0.18** (配置向导) | 0.4, 1.1 ✅ | - | Soft | 📋 ready-for-dev |
| **0.30** (应用启动) | 0.4 ✅ | - | Soft | 📋 ready-for-dev |

**Epic 1 价值组 2 (架构基础) 依赖矩阵**

| Story | 前置依赖 | 后置依赖 | 依赖类型 | 关键路径 |
|-------|---------|---------|---------|---------|
| **1.1** (六边形架构) | 0.9 ✅ | 1.2, 1.16, Epic 2-8 | Hard | ✅ 已完成 |
| **1.2** (领域事件) | 1.1 ✅ | 1.3 | Hard | ✅ 已完成 |
| **1.3** (事件总线) | 1.2 ✅ | 1.14a, 1.18a, 1.18b | Hard | ✅ 已完成 |
| **1.16** (集成测试) | 1.1 ✅ | - | Soft | ✅ 已完成 |

**Epic 1 价值组 3 (六层存储) 依赖矩阵**

| Story | 前置依赖 | 后置依赖 | 依赖类型 | 关键路径 |
|-------|---------|---------|---------|---------|
| **1.4** (Redis) | 1.1 ✅ | - | Hard | ✅ 已完成 |
| **1.5** (PostgreSQL) | 1.1 ✅ | 1.9 | Hard | ✅ 已完成 |
| **1.6** (Qdrant) | 1.1 ✅ | Epic 3 | Hard | ✅ 已完成 |
| **1.7** (MinIO) | 1.1 ✅ | Epic 2 | Hard | ✅ 已完成 |
| **1.8** (Neo4j) | 1.1 ✅ | Epic 3 | Hard | ✅ 已完成 |
| **1.13** (K8s 扩缩容) | 0.4 ✅ | - | Soft | ✅ 已完成 |

**Epic 1 价值组 4 (安全合规) 依赖矩阵**

| Story | 前置依赖 | 后置依赖 | 依赖类型 | 关键路径 |
|-------|---------|---------|---------|---------|
| **1.9** (RBAC) | 1.5 ✅ | 1.10, Epic 7 | Hard | ✅ 已完成 |
| **1.10** (审计日志) | 1.9 ✅ | 1.11, Epic 8 | Hard | ✅ 已完成 |
| **1.11** (数据主权) | 1.10 ✅ | 1.12 | Hard | ✅ 已完成 |
| **1.12** (等保 2.0) | 1.11 ✅ | - | Hard | ✅ 已完成 |

**Epic 1 价值组 5 (系统公理) 依赖矩阵**

| Story | 前置依赖 | 后置依赖 | 依赖类型 | 关键路径 |
|-------|---------|---------|---------|---------|
| **1.14a** (trigger) | 1.3 ✅ | 1.14b | Hard | ✅ 已完成 |
| **1.14b** (route) | 1.14a ✅ | 1.14c, 1.17 | Hard | ✅ 已完成 |
| **1.14c** (execute) | 1.14b ✅ | - | Hard | ✅ 已完成 |
| **1.15a** (L1 压缩) | 1.4 ✅ | 1.15b | Hard | ✅ 已完成 |
| **1.15b** (六层协同) | 1.15a, 1.4, 1.5 ✅ | - | Hard | ✅ 已完成 |

**Epic 1 价值组 6 (关键机制) 依赖矩阵**

| Story | 前置依赖 | 后置依赖 | 依赖类型 | 关键路径 |
|-------|---------|---------|---------|---------|
| **1.17** (UDMR) | 1.14b ✅ | 1.19, Epic 3 | Hard | ✅ 已完成 |
| **1.18a** (Prefect) | 1.3 ✅ | Epic 2, Epic 6 | Hard | ✅ 已完成 |
| **1.18b** (LangGraph) | 1.3 ✅ | Epic 4, Epic 5, Epic 6 | Hard | ✅ 已完成 |
| **1.19** (成本度量) | 1.17 ✅ | - | Soft | ✅ 已完成 |
