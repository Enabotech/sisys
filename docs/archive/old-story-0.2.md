# 原 Story 0.2: CI/CD 流水线 (已废弃)

**状态：** ⚠️ 已废弃 (被 Epic 0 新 Story 0.1-0.6 替代)
**归档日期：** 2026-03-05
**废弃原因：** 技术栈更新为 Gitea + K3S + Harbor + ArgoCD

---

## 原 Story 定义

### Story 0.2: CI/CD 流水线

**As a** DevOps 工程师,
**I want** 自动化构建、测试和部署的 CI/CD 流水线,
**So that** 代码变更可以快速、可靠地发布。

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

---

## 保留价值

**可复用的设计：**
- ✅ 代码质量门禁概念
- ✅ Pipeline 阶段设计
- ✅ 质量门禁阈值
- ✅ 测试覆盖率要求

**被替代的内容：**
- ❌ GitHub Actions → Gitea Actions
- ❌ K8s/Swarm → K3S + ArgoCD
- ❌ 通用镜像仓库 → Harbor
- ❌ 手动部署 → GitOps 自动部署

---

## 新 Story 替代关系

| 原 Story 0.2 内容 | 新 Story | 状态 |
|----------------|---------|------|
| CI/CD 触发 | Story 0.5 (Gitea Runner) | ✅ 替代 |
| 代码质量门禁 | Story 0.6 (Pipeline 模板) | ✅ 继承 |
| 单元测试 | Story 0.3 (测试框架) + Story 0.6 | ✅ 保留 |
| 集成测试 | Story 0.6 (Pipeline 模板) | ✅ 保留 |
| 安全扫描 | Story 0.6 (Trivy+Bandit) | ✅ 增强 |
| 镜像构建 | Story 0.6 (Docker Build) | ✅ 保留 |
| 镜像推送 | Story 0.3 (Harbor) | ✅ 增强 |
| 自动部署 | Story 0.4 (ArgoCD) | ✅ 增强 |

---

## 迁移指南

**从 GitHub Actions 迁移到 Gitea Actions:**

```yaml
# 原 GitHub Actions
on:
  push:
    branches: [main]

# 新 Gitea Actions
on:
  push:
    branches: [main]
# 配置相同，语法兼容
```

**从 K8s/Swarm 迁移到 K3S + ArgoCD:**

```bash
# 原 K8s 部署
kubectl apply -f deployment.yaml

# 新 ArgoCD GitOps
argocd app sync sisys-app
# 自动同步 Git 配置到 K3S
```

**从通用镜像仓库迁移到 Harbor:**

```bash
# 原 Docker Hub
docker push sisys:latest

# 新 Harbor
docker push harbor.local/library/sisys:latest
# 镜像签名 + 漏洞扫描
```

---

**归档完成** ✅
**新 Story 参考：** `docs/developer/EPIC_0_REFACTORED.md`
