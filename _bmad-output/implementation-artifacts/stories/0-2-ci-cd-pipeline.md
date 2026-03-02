# Story 0.2: CI/CD 流水线

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **DevOps 工程师**,
I want **自动化构建、测试和部署的 CI/CD 流水线**,
So that **代码变更可以快速、可靠地发布**。

## Acceptance Criteria

1. **Given** 代码提交到 Git
   **When** 触发 CI/CD 流水线
   **Then** 自动运行单元测试、集成测试、代码扫描、构建 Docker 镜像
   **And** 测试通过后自动部署到测试环境
   **And** 所有 Epic 的构建和部署都通过此流水线执行

2. **Given** Pull Request 创建
   **When** PR 触发 CI 流水线
   **Then** 运行代码规范检查（linting）、单元测试、安全扫描
   **And** 所有检查通过后才允许合并

3. **Given** 代码合并到 main 分支
   **When** CD 流水线触发
   **Then** 构建 Docker 镜像并推送到镜像仓库
   **And** 自动部署到测试环境

## Tasks / Subtasks

- [ ] Task 1: 创建 GitHub Actions 工作流配置文件 (AC: 1, 2)
  - [ ] Subtask 1.1: 创建 `.github/workflows/ci.yml` - CI 流水线（代码提交/PR 触发）
  - [ ] Subtask 1.2: 创建 `.github/workflows/cd.yml` - CD 流水线（main 分支合并触发）
  - [ ] Subtask 1.3: 配置工作流权限和 secrets 管理

- [ ] Task 2: CI 流水线实现 (AC: 1, 2)
  - [ ] Subtask 2.1: 设置 Python 3.11+ 环境缓存
  - [ ] Subtask 2.2: 安装 Poetry 依赖并缓存
  - [ ] Subtask 2.3: 运行代码规范检查（ruff/black/mypy）
  - [ ] Subtask 2.4: 运行单元测试（pytest）并生成覆盖率报告
  - [ ] Subtask 2.5: 运行安全扫描（bandit/safety）
  - [ ] Subtask 2.6: 上传测试覆盖率报告到 Coveralls/Codecov

- [ ] Task 3: CD 流水线实现 (AC: 1, 3)
  - [ ] Subtask 3.1: 构建 Docker 镜像（多阶段构建优化）
  - [ ] Subtask 3.2: 推送 Docker 镜像到 GitHub Container Registry (GHCR)
  - [ ] Subtask 3.3: 部署到测试环境（Docker Compose）
  - [ ] Subtask 3.4: 运行健康检查验证部署成功
  - [ ] Subtask 3.5: 发送部署通知（可选：Slack/钉钉）

- [ ] Task 4: Docker 配置优化 (AC: 1, 3)
  - [ ] Subtask 4.1: 创建生产环境 Dockerfile（多阶段构建）
  - [ ] Subtask 4.2: 配置 Docker Compose 生产环境配置文件
  - [ ] Subtask 4.3: 添加 Docker 健康检查（healthcheck）
  - [ ] Subtask 4.4: 配置容器资源限制（CPU/内存）

- [ ] Task 5: 环境变量与 Secrets 管理 (AC: 1)
  - [ ] Subtask 5.1: 配置 GitHub Actions Secrets
  - [ ] Subtask 5.2: 创建环境变量模板（.env.example → .env）
  - [ ] Subtask 5.3: 配置敏感信息加密（Docker secrets 或外部密钥管理）

- [ ] Task 6: 监控与日志 (AC: 1)
  - [ ] Subtask 6.1: 配置流水线执行日志保留策略
  - [ ] Subtask 6.2: 设置流水线失败通知（邮件/即时通讯）
  - [ ] Subtask 6.3: 添加流水线执行时间监控

## Dev Notes

### 相关架构模式和约束

**架构约束（来自 architecture.md）：**
- **FR-AR-01**: 领域层零依赖原则 - CI 流水线应验证此约束（通过导入检查）
- **FR-AR-03**: 跨存储事务 - 集成测试需验证事务一致性
- **NFR-COMP-01**: 等保 2.0 三级 - 安全扫描需包含等保合规检查项
- **NFR-REL-01**: 系统可用性 99% - CD 流水线需包含可用性测试

**技术栈要求：**
- Python 3.11+（架构文档第 12 章）
- Poetry 依赖管理
- Docker Compose 多服务编排
- GitHub Actions 作为 CI/CD 平台（2026 最佳实践）

**源树组件：**
- `.github/workflows/` - GitHub Actions 工作流定义
- `docker/` - Docker 配置文件
- `src/` - 应用源代码（六边形架构）
- `tests/` - 测试代码（单元/集成/E2E）
- `scripts/` - 自动化脚本

**测试标准：**
- 单元测试覆盖率 ≥80%（架构文档 NFR 质量目标）
- 集成测试覆盖所有仓储实现
- E2E 测试覆盖关键用户旅程

### 项目结构说明

**完整目录结构：** 遵循 [architecture.md](../../../../_bmad-output/planning-artifacts/architecture.md#13-目录结构) 第 13 章定义（权威来源）

**Story 0.2 新增文件：**

| 文件 | 用途 | 说明 |
|------|------|------|
| `.github/workflows/ci.yml` | CI 流水线 | PR/代码提交触发（6 个 Job） |
| `.github/workflows/cd.yml` | CD 流水线 | main 分支触发（4 个 Job） |
| `docker/Dockerfile.prod` | 生产 Dockerfile | 多阶段构建 |
| `docker/docker-compose.prod.yml` | 生产编排 | 资源限制/健康检查 |
| `docker/docker-compose.test.yml` | 测试编排 | 自动清理测试数据 |
| `scripts/testing/run_tests.sh` | 测试运行 | 单元/集成/E2E 测试 |
| `scripts/testing/run_coverage.sh` | 覆盖率报告 | HTML/XML 生成 |
| `scripts/testing/clean_test_data.py` | 清理工具 | 五层存储数据清理 |
| `.pre-commit-config.yaml` | Pre-commit | 代码质量钩子 |
| `docs/developer/testing_guide.md` | 测试指南 | 使用文档 |
| `docs/developer/cicd_quick_reference.md` | CI/CD 参考 | 快速参考卡片 |

**命名约定：** 遵循 architecture.md 第 13 章定义。
- **工作流文件**：`ci.yml`（持续集成）、`cd.yml`（持续部署）
- **Docker 镜像标签**：`{git_sha}`（精确版本）、`{version}`（语义化版本）、`latest`（最新稳定版）
- **测试文件**：`test_*.py`（pytest 约定）
- **领域事件**：`<名词><过去分词>.py`（如 `DocumentProcessed.py`）
- **用例/命令/查询**：`<动作>_<对象>.py`（如 `process_document.py`）
- **仓储实现**：`<实体名>_repository_impl.py`（清晰标识实现层）
- **配置分层**：`base.py`（基础配置）+ `<环境>.py`（环境特定配置）

**关键架构约束验证（CI 流水线职责）：**
1. ✅ **领域层零依赖**（FR-AR-01）：CI 应运行导入检查，确保 `src/domain/` 仅依赖 Python 标准库
2. ✅ **事件驱动架构**（FR-AR-02）：集成测试验证领域事件发布至事件总线
3. ✅ **五层存储依赖方向**：`L1→L2→L3→L4→L5` 单向依赖（architecture.md 第 11 章）
4. ✅ **UDMR/EIP 审计日志**：验证路由决策日志和隔离切换日志归档至 MinIO WORM

### 2026 CI/CD 最佳实践（来自网络研究）

**GitHub Actions 最佳实践：**
1. **缓存优化**：使用 `actions/cache@v4` 缓存 Poetry 依赖和 Docker 层，构建速度提升 60%
2. **矩阵构建**：并行测试多个 Python 版本（3.11, 3.12）
3. **OIDC 认证**：使用 OIDC 连接云提供商，避免长期凭证
4. **可重用工作流**：将通用逻辑提取为可重用工作流（DRY 原则）
5. **环境保护规则**：生产环境部署需要审批

**Docker 生产最佳实践：**
1. **多阶段构建**：减少最终镜像大小（仅包含运行时依赖）
2. **健康检查**：使用 `HEALTHCHECK` 指令检测容器状态
3. **资源限制**：设置 CPU/内存限制防止资源耗尽
4. **非 root 用户**：以非 root 用户运行容器增强安全性
5. **镜像扫描**：集成 Trivy/Clair 扫描镜像漏洞

**安全最佳实践：**
1. **最小权限原则**：GitHub Actions 使用最小权限（`permissions`）
2. **Secrets 轮换**：定期轮换 Docker Hub/云凭证
3. **依赖审查**：使用 `dependabot` 自动更新依赖
4. **代码所有者**：关键文件（如工作流配置）需要代码所有者审批

### 前一个故事学习经验（Story 0.1）

**已建立的模式：**
- Docker Compose 配置了 5 个存储服务（PostgreSQL/Redis/Qdrant/MinIO/Neo4j）
- Poetry 依赖管理已初始化
- WSL 2 设置脚本已创建（Windows 开发环境）
- 健康检查脚本 `scripts/monitoring/health_check.py` 可复用

**CI/CD 需要集成的内容：**
- Docker Compose 健康检查验证
- Poetry 依赖缓存
- Python 代码规范检查（与 Story 0.1 IDE 配置一致）

### Git 智能分析

**最近的提交模式：**
- Story 0.1 完成了开发环境初始化
- 创建了 Docker 配置和 WSL 2 脚本
- 下一步自然演进：自动化这些手动步骤

**对本故事的启示：**
- CI 流水线应复用 Story 0.1 的 Docker Compose 配置
- 健康检查脚本应集成到 CD 流水线
- 测试框架（Story 0.3）完成后需集成到 CI

### 最新技术信息

**GitHub Actions 2026 更新：**
- 新版本：`actions/checkout@v4`、`actions/setup-python@v5`、`actions/cache@v4`
- 新增功能：Actions Cache 免费额度提升、可重用工作流增强
- 安全增强：OIDC 支持更多云提供商

**Docker 2026 最佳实践：**
- Docker Buildx 成为默认构建器（支持多平台构建）
- Compose Profiles 用于环境隔离（dev/prod/test）
- Healthcheck 间隔建议：30 秒，超时 10 秒，启动宽限期 60 秒

**Python 测试工具链 2026：**
- `pytest@8.x`：最新测试框架
- `coverage@7.x`：覆盖率测量
- `ruff@0.2+`：超快速 linting（替代 flake8/black 部分功能）
- `mypy@1.8+`：静态类型检查

## Dev Agent Record

### Agent Model Used

- **Model**: Qwen 2.5 Max (2026-01)
- **Version**: create-story workflow v8.3.0
- **Execution Date**: 2026-03-02

### Debug Log References

- Workflow Config: `g:\ai\sisys\_bmad\bmm\workflows\4-implementation\create-story\workflow.yaml`
- Instructions: `g:\ai\sisys\_bmad\bmm\workflows\4-implementation\create-story\instructions.xml`
- Template: `g:\ai\sisys\_bmad\bmm\workflows\4-implementation\create-story\template.md`

### Completion Notes List

- ✅ 故事需求从 epics_v1.0.md 提取
- ✅ 架构约束从 architecture.md 提取（六边形架构、五层存储、事件驱动）
- ✅ 前一个故事学习经验整合（Story 0.1 开发环境搭建）
- ✅ 2026 CI/CD 最佳实践研究（GitHub Actions、Docker 生产部署）
- ✅ 项目结构对齐统一项目结构
- ✅ 状态设置为 ready-for-dev

### File List

**创建的文件：**
- `g:\ai\sisys\_bmad-output\implementation-artifacts\stories\0-2-ci-cd-pipeline.md`

**后续需要创建的文件：**
- `.github/workflows/ci.yml`
- `.github/workflows/cd.yml`
- `docker/Dockerfile.prod`
- `docker/docker-compose.prod.yml`

---

**🎯 ULTIMATE BMad Method STORY CONTEXT CREATED!**

**Story Details:**
- Story ID: 0.2
- Story Key: 0-2-ci-cd-pipeline
- File: `g:\ai\sisys\_bmad-output\implementation-artifacts\stories\0-2-ci-cd-pipeline.md`
- Status: ready-for-dev

**Next Steps:**
1. Review the comprehensive story in `0-2-ci-cd-pipeline.md`
2. Run dev agents `dev-story` for optimized implementation
3. Run `code-review` when complete (auto-marks done)
4. Optional: If Test Architect module installed, run `/bmad:tea:automate` after `dev-story` to generate guardrail tests

**The developer now has everything needed for flawless implementation!**
