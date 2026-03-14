# Story 0.7: ArgoCD 持续部署

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **DevOps 工程师**,
I want **部署 ArgoCD v3.3.2 持续部署工具**,
So that **实现 GitOps 自动化部署，代码提交后自动同步到 K8s 集群**。

## Acceptance Criteria

**Given** K3S 集群已部署 (Story 0.4 ✅ 已完成) 且 Harbor 镜像仓库已部署 (Story 0.6 ✅ 已完成)
**When** 运行 ArgoCD 安装脚本
**Then** ArgoCD v3.3.2 部署成功
- [ ] 所有 Pod 状态为 Running (`kubectl get pods -n argocd`，无 CrashLoopBackOff 或 Error 状态)
- [ ] 健康检查通过 (`curl -k https://argocd.sisys.local/api/v1/session`, HTTP 200)
- [ ] Pod 启动时间 < 60 秒
- [ ] 无重启次数异常（restart count < 3）

**Given** ArgoCD 服务已启动
**When** 访问 https://argocd.sisys.local
**Then** ArgoCD Web 界面可正常访问
- [ ] HTTP 200 响应
- [ ] 页面加载时间 < 3 秒
- [ ] 页面标题包含"ArgoCD"
- [ ] 登录表单可正常显示
- [ ] TLS 1.3 强制启用，SSL Labs 测试评级 ≥ A

**Given** ArgoCD 初始化配置
**When** 首次启动
**Then** PostgreSQL/Redis 依赖服务连接成功
- [ ] Redis 连接成功 (`kubectl exec -n argocd <argocd-server-pod> -- redis-cli ping` 返回 PONG)
- [ ] 数据库连接延迟 < 100ms
- [ ] 无连接错误日志

**Given** ArgoCD 服务运行中
**When** 创建管理员账号
**Then** 管理员账号创建成功并可登录
- [ ] 初始密码从 Kubernetes Secret 获取 (`kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d`)
- [ ] 登录成功（HTTP 302 重定向到仪表盘）
- [ ] 登录响应时间 < 2 秒
- [ ] 密码复杂度验证通过（12 位 + 大小写 + 数字 + 符号）

**Given** ArgoCD 配置完成
**When** 添加 Git 仓库（Gitea Story 0.5 ✅ 已完成）
**Then** Git 仓库连接成功
- [ ] Gitea 仓库连接成功 (`argocd repo add https://gitea.sisys.local/sisys/sisys.git --username {USER} --password {TOKEN}`)
- [ ] 仓库同步成功（Application 列表可见）
- [ ] Git 认证使用 Personal Access Token（非明文密码）

**Given** ArgoCD 与 Harbor 集成 (Story 0.6 ✅ 已完成)
**When** 配置 Image Updater
**Then** 镜像更新自动触发
- [ ] ArgoCD Image Updater 部署成功
- [ ] Harbor Webhook 配置成功（镜像推送事件 → Image Updater）
- [ ] 新镜像推送后自动更新 K8s Deployment（< 5 分钟）

**Given** ArgoCD Application 创建
**When** 配置自动同步策略
**Then** Git 变更自动同步到集群
- [ ] 自动同步策略配置成功（`syncPolicy.automated.prune = true`, `selfHeal = true`）
- [ ] Git 提交后自动部署（< 2 分钟）
- [ ] 部署失败自动回滚

## SDD 规范定义

### 领域事件 Schema
- [ ] 事件定义（`src/domain/events/`）- 本 Story 为基础设施 Story，领域事件在 Story 1.2 实现
- [ ] Pydantic 验证通过

### API 契约
- [ ] OpenAPI 定义（`docs/api/openapi.yaml`）- ArgoCD 使用原生 API，本 Story重点在 GitOps 流程
- [ ] 契约测试通过

### 验收标准（Gherkin）
- [ ] `tests/acceptance/test_story_0_7.feature`
- [ ] 业务方评审通过

## Tasks / Subtasks

- [ ] Task 1: ArgoCD Helm Chart 配置 (AC: 1, 2)
  - [ ] 添加 ArgoCD Helm 仓库
  - [ ] 配置 values.yaml (副本数、资源限制、Ingress)
  - [ ] 配置 Ingress (Traefik v3.x, TLS 1.3)
  - [ ] 配置 Redis 和 PostgreSQL（内部/外部可选）
  - [ ] 配置 Kubernetes Secret (密钥、密码)

- [ ] Task 2: ArgoCD 部署与验证 (AC: 1, 2, 3, 4)
  - [ ] 执行 helm install 部署 ArgoCD
  - [ ] 验证 Pod 运行状态 (Running 1/1)
  - [ ] 验证服务可访问 (健康检查通过)
  - [ ] 获取初始管理员密码 (argocd-initial-admin-secret)
  - [ ] 验证 Redis/PostgreSQL 连接
  - [ ] 绿灯测试通过

- [ ] Task 3: Git 仓库集成配置 (AC: 5)
  - [ ] 创建 Gitea Personal Access Token
  - [ ] 添加 Gitea 仓库到 ArgoCD (`argocd repo add`)
  - [ ] 验证仓库连接 (`argocd repo get`)
  - [ ] 配置 Webhook（Gitea → ArgoCD）

- [ ] Task 4: ArgoCD Image Updater 配置 (AC: 6)
  - [ ] 部署 ArgoCD Image Updater
  - [ ] 配置 Harbor 镜像仓库凭证
  - [ ] 配置 Harbor Webhook（镜像推送事件 → Image Updater）
  - [ ] 验证镜像自动更新流程

- [ ] Task 5: Application 与自动同步策略 (AC: 7)
  - [ ] 创建示例 Application（GitOps 模式）
  - [ ] 配置自动同步策略（prune=true, selfHeal=true）
  - [ ] 验证 Git 提交后自动部署
  - [ ] 配置部署失败自动回滚

- [ ] Task 6: 安全加固
  - [ ] 配置容器以非 root 用户运行 (securityContext)
  - [ ] 配置 NetworkPolicy (DefaultDeny)
  - [ ] 配置只读根文件系统
  - [ ] 禁用特权模式
  - [ ] 配置 RBAC 权限（项目级隔离）

- [ ] Task 7: 架构合规验证
  - [ ] 验证 TLS 1.3 强制启用
  - [ ] 验证存储使用 local-path (NVMe SSD)
  - [ ] 验证 Ingress 配置 (Traefik 443 → argocd-server:443)
  - [ ] 验证密钥存储于 Kubernetes Secret
  - [ ] 运行所有 TDD 测试

- [ ] Task 8: 代码审查修复
  - [ ] 修复 AI 审查发现的问题
  - [ ] 所有问题 100% 修复

- [ ] Task 9: 功能验证
  - [ ] AC-1: ArgoCD 部署验证
  - [ ] AC-2: Web 界面访问
  - [ ] AC-3: Redis/PostgreSQL 连接
  - [ ] AC-4: 管理员账号
  - [ ] AC-5: Git 仓库集成
  - [ ] AC-6: Harbor Image Updater
  - [ ] AC-7: 自动同步策略

## TDD 测试要求

### 1. 基础设施测试
- [ ] ArgoCD Pod 运行状态测试 - 验证所有 Pod Running
- [ ] 服务可访问性测试 - 验证 HTTPS 访问
- [ ] 数据库连接测试 - 验证 Redis/PostgreSQL 连接
- [ ] Git 仓库连接测试 - 验证 Gitea 集成
- [ ] Image Updater 测试 - 验证镜像自动更新

### 2. 性能要求
- [ ] Pod 启动时间 < 60 秒
- [ ] 页面加载时间 < 3 秒
- [ ] Git 提交后自动部署 < 2 分钟
- [ ] 镜像推送后自动更新 < 5 分钟

### 3. 覆盖率要求
- [ ] 基础设施层覆盖率≥75%
- [ ] 集成测试覆盖率≥70%

### 4. 代码质量
- [ ] Ruff 检查通过
- [ ] MyPy 类型检查通过
- [ ] YAML 语法验证通过（yamllint）

### 5. 测试文件
- [ ] `tests/deployment/test_argocd.py` - 部署测试
- [ ] `tests/integration/test_argocd_gitops.py` - GitOps 集成测试

**实施指南:**
参考 `docs/deployment/ARGOCD_SETUP.md`

## Dev Notes

### 相关架构模式和约束

**来源**: [architecture-epic0.md](../../planning-artifacts/architecture-epic0.md)

**GitOps 模式:**
- Git 作为唯一真相源（Single Source of Truth）
- 声明式配置（YAML/Helm/Kustomize）
- 自动同步（Automated Sync）
- 自我修复（Self-Healing）

**架构约束:**
1. **Ingress 配置**: Traefik v3.x 反向代理，TLS 1.3 强制启用
2. **存储架构**: local-path-provisioner (NVMe SSD)
3. **网络架构**: DefaultDeny NetworkPolicy，仅允许 Traefik 访问
4. **安全配置**: 非 root 用户、只读根文件系统、RBAC 权限隔离

**依赖关系:**
- ✅ Story 0.4: K3S 集群部署（已完成）- K3S v1.34.5, Traefik v3.x, local-path-provisioner
- ✅ Story 0.5: Gitea 代码托管（已完成）- Gitea v1.25.4
- ✅ Story 0.6: Harbor 镜像仓库（已完成）- Harbor v2.14.3
- → Story 0.8: Gitea Runner 配置（可并行）
- → Story 0.9: CI/CD Pipeline 模板（依赖本 Story）

### 项目结构说明

**统一项目结构:**

```
sisys/
├── docs/
│   └── deployment/
│       ├── ARGOCD_SETUP.md           # ArgoCD 部署指南
│       ├── ARGOCD_IMAGE_UPDATER.md   # Image Updater 配置
│       └── GITOPS_WORKFLOW.md        # GitOps 工作流
├── deployments/
│   └── argocd/
│       ├── values.yaml              # Helm Chart 配置
│       ├── ingress.yaml             # Ingress 配置
│       ├── rbac.yaml                # RBAC 配置
│       └── kustomization.yaml       # Kustomize 配置
├── apps/
│   └── example-app/                 # 示例应用（GitOps 演示）
│       ├── deployment.yaml
│       ├── service.yaml
│       └── kustomization.yaml
└── tests/
    └── deployment/
        └── test_argocd.py           # ArgoCD 部署测试
```

### 前一个故事学习经验

**来源**: [Story 0.6 (Harbor)](./0-6-harbor-image-registry.md)

**Story 0.6 关键学习:**

1. **代码审查经验:**
   - ✅ 9/9 问题已修复 (100%)
   - ✅ HIGH 优先级问题：AC 测试代码、NetworkPolicy 选择器、存储容量、测试命名
   - ✅ MEDIUM 优先级问题：Robot Account、Trivy 更新策略、集成测试
   - ✅ LOW 优先级问题：File List 一致性、密码历史策略

2. **功能验证经验:**
   - ✅ 保守方案验证：7 项 AC 中 3 项完全通过，4 项部分通过（配置就绪，待依赖 Story）
   - ✅ 关键教训：Ingress 配置需应用简化版（ingress-traefik.yaml）
   - ✅ 关键教训：测试脚本需可执行（chmod +x）

3. **架构合规经验:**
   - ✅ TLS 1.3 强制启用配置成功
   - ✅ NetworkPolicy DefaultDeny 配置成功
   - ✅ local-path-provisioner 存储配置成功
   - ✅ Kubernetes Secret 密钥管理配置成功

**应用到 Story 0.7:**
- 提前应用简化 Ingress 配置，避免访问问题
- 所有测试脚本确保可执行（chmod +x）
- NetworkPolicy 选择器使用正确的命名空间（kube-system for Traefik）
- 存储容量统一配置（50Gi for ArgoCD）
- 所有测试用例在代码审查前完成

### Git 智能分析

**最近提交模式:**
- Story 0.4: K3S 集群部署 - 15/15 测试通过，代码审查 9 个问题 100% 修复
- Story 0.5: Gitea 代码托管 - 12 个问题 100% 修复
- Story 0.6: Harbor 镜像仓库 - 9 个问题 100% 修复

**代码模式:**
- Helm Chart 配置：values.yaml + ingress.yaml + kustomization.yaml
- 测试模式：test_*.py (pytest) + verify_*.sh (bash)
- 文档模式：*_INSTALLATION.md + *_CONFIGURATION.md

**架构决策:**
- 使用 Helm Chart 部署（官方推荐）
- 使用 Traefik Ingress（K3S 默认）
- 使用 local-path-provisioner（NVMe SSD 性能优）
- 使用 Kubernetes Secret 管理密钥

### 最新技术信息

**ArgoCD v3.3.2 关键特性:**
- GitOps 自动化部署
- 多集群管理
- 自动同步策略（prune/selfHeal）
- Webhook 集成（GitHub/Gitea/GitLab）
- Image Updater（自动镜像更新）
- RBAC 权限管理
- SSO 集成（OIDC/SAML）

**ArgoCD Image Updater:**
- 监听镜像仓库标签变更
- 自动更新 K8s Deployment
- 支持 Harbor/Gitea/ACR/ECR
- Webhook 触发（实时）或轮询（定时）

**最佳实践:**
- 使用 Helm Chart 部署（官方维护）
- 配置自动同步策略（prune=true, selfHeal=true）
- 使用 Image Updater 实现镜像自动更新
- 配置 RBAC 项目级隔离
- 启用审计日志

### 最新技术信息研究

**研究内容:**
- ArgoCD v3.3.2 官方文档
- ArgoCD Image Updater 配置
- Harbor Webhook 配置
- GitOps 最佳实践

**关键发现:**
1. ArgoCD v3.3.2 支持 K8s v1.34
2. Image Updater 需要配置 Harbor 凭证
3. Harbor Webhook 需配置镜像推送事件
4. GitOps 最佳实践：prune=true, selfHeal=true

## Dev Agent Record

### Agent Model Used

- **Model**: Qwen Code (AI 开发助手)
- **Version**: create-story workflow v6.0.1
- **Execution Date**: 2026-03-14

### Debug Log References

- Workflow Config: `g:\ai\sisys\_bmad\bmm\workflows\4-implementation\create-story\workflow.yaml`
- Instructions: `g:\ai\sisys\_bmad\bmm\workflows\4-implementation\create-story\instructions.xml`
- Template: `g:\ai\sisys\docs\developer\story-template.md`
- Epics: `g:\ai\sisys\_bmad-output\planning-artifacts\epics_v1.0.md`
- Architecture: `g:\ai\sisys\_bmad-output\planning-artifacts\architecture-epic0.md`
- Previous Story: `g:\ai\sisys\_bmad-output\implementation-artifacts\stories\0-6-harbor-image-registry.md`
- Sprint Status: `g:\ai\sisys\_bmad-output\implementation-artifacts\sprint-status.yaml`

### Completion Notes List

- [x] 故事需求从 epics_v1.0.md 提取
- [x] 架构约束从 architecture-epic0.md 提取
- [x] 前一个故事学习经验整合（Story 0.6 Harbor）
- [x] 最新技术信息研究（ArgoCD v3.3.2, Image Updater）
- [x] 状态设置为 ready-for-dev
- [x] TDD 测试要求定义完成
- [x] 项目结构对齐统一项目结构

### File List

**创建的文件：**
- `g:\ai\sisys\_bmad-output\implementation-artifacts\stories\0-7-argocd-continuous-deployment.md`

**待创建的文件（Dev Story 实施）:**
- `docs/deployment/ARGOCD_SETUP.md` - ArgoCD 部署指南
- `docs/deployment/ARGOCD_IMAGE_UPDATER.md` - Image Updater 配置
- `docs/deployment/GITOPS_WORKFLOW.md` - GitOps 工作流
- `deployments/argocd/values.yaml` - Helm Chart 配置
- `deployments/argocd/ingress.yaml` - Ingress 配置
- `deployments/argocd/rbac.yaml` - RBAC 配置
- `tests/deployment/test_argocd.py` - ArgoCD 部署测试
- `tests/integration/test_argocd_gitops.py` - GitOps 集成测试

---

**Story Details:**
- Story ID: 0.7
- Story Key: 0-7-argocd-continuous-deployment
- File: `g:\ai\sisys\_bmad-output\implementation-artifacts\stories\0-7-argocd-continuous-deployment.md`
- Status: ready-for-dev

**Completion Summary:**
1. [x] All tasks defined
2. [x] All acceptance criteria defined
3. [x] Architecture compliance verified
4. [x] Sprint status synced

**Next Steps:**
1. Review the comprehensive story document
2. Run `dev-story` for implementation
3. Run `code-review` when complete
4. Optional: Run `/bmad:tea:automate` to generate guardrail tests

---

## 模板使用说明

### 适用场景

本 Story 为**基础设施层 Story**，适用于：
- K8s 持续部署工具部署
- GitOps 流程实施
- 自动化部署流程

### TDD 测试要求模板

**基础设施层 Story：**
```markdown
### 1. 基础设施测试
- [ ] ArgoCD Pod 运行状态测试 - 验证所有 Pod Running
- [ ] 服务可访问性测试 - 验证 HTTPS 访问
- [ ] 数据库连接测试 - 验证 Redis/PostgreSQL 连接
- [ ] Git 集成测试 - 验证 Gitea 仓库连接
- [ ] Image Updater 测试 - 验证镜像自动更新

### 2. 性能要求
- [ ] Pod 启动时间 < 60 秒
- [ ] 页面加载时间 < 3 秒
- [ ] Git 提交后自动部署 < 2 分钟
- [ ] 镜像推送后自动更新 < 5 分钟

### 3. 覆盖率要求
- [ ] 基础设施层覆盖率≥75%
- [ ] 集成测试覆盖率≥70%
```

### 相关文档

- [Story 0.4: K3S 集群部署](./0-4-k3s-cluster-deployment.md)
- [Story 0.5: Gitea 代码托管](./0-5-gitea-code-hosting.md)
- [Story 0.6: Harbor 镜像仓库](./0-6-harbor-image-registry.md)
- [architecture-epic0.md](../../planning-artifacts/architecture-epic0.md)

---

**模板版本:** 1.0.0
**创建日期:** 2026-03-14
**最后更新:** 2026-03-14
