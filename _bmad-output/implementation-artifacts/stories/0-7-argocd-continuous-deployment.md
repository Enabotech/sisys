# Story 0.7: ArgoCD 持续部署

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **DevOps 工程师**,
I want **部署 ArgoCD v3.3.2 持续部署工具**,
so that **实现 GitOps 自动化部署，代码提交后自动同步到 K8s 集群**。

## Acceptance Criteria

1. **Given** K3S 集群已部署 (Story 0.4 ✅ 已完成)
   **When** 运行 ArgoCD 安装脚本
   **Then** ArgoCD v3.3.2 部署成功
   - 所有 Pod 状态为 Running (`kubectl get pods -n argocd`，无 CrashLoopBackOff 或 Error 状态)
   - 健康检查通过 (`curl -k https://argocd.sisys.local/health`，HTTP 200)
   - Pod 启动时间 < 60 秒
   - 无重启次数异常（restart count < 3）

2. **Given** ArgoCD 服务已启动
   **When** 访问 https://argocd.sisys.local
   **Then** ArgoCD Web 界面可正常访问
   - HTTP 200 响应
   - 页面加载时间 < 3 秒
   - 页面标题包含"ArgoCD"
   - 登录表单可正常显示
   - SSL Labs 测试评级 ≥ A（TLS 1.3 强制启用）

3. **Given** ArgoCD 服务运行中
   **When** 使用 admin 账号登录
   **Then** 登录成功并可访问仪表盘
   - 初始密码从 Kubernetes Secret 获取
   - 首次登录强制修改密码
   - 密码复杂度验证通过（12 位 + 大小写 + 数字 + 符号）
   - 登录响应时间 < 2 秒

4. **Given** ArgoCD 配置完成
   **When** 添加 Gitea 代码仓库
   **Then** Git 仓库连接成功
   - Gitea 仓库地址配置正确（https://gitea.sisys.local/sisys/sisys.git）
   - 认证凭据配置（Personal Access Token）
   - 仓库连接测试通过
   - 支持 Webhook 自动触发

5. **Given** ArgoCD 与 Harbor 集成
   **When** 配置 Image Updater
   **Then** 镜像自动更新功能可用
   - Harbor 镜像仓库配置正确
   - Image Updater 检测到新镜像 tag
   - 自动更新 K8s Deployment 镜像
   - 滚动部署成功

6. **Given** ArgoCD Application 创建
   **When** 配置 GitOps 应用
   **Then** 应用同步状态正常
   - Application 状态为 Synced
   - Health 状态为 Healthy
   - 自动同步策略启用（auto-prune, self-heal）
   - 同步历史可追溯

7. **Given** ArgoCD 多环境配置
   **When** 创建 Dev/Test/Prod 环境
   **Then** 多环境隔离成功
   - 各环境独立命名空间
   - 环境间配置差异管理（Kustomize/Helm）
   - 环境晋升流程清晰
   - 权限隔离（RBAC）

## Tasks / Subtasks

- [ ] Task 1: ArgoCD Helm Chart 配置 (AC: 1, 2)
  - [ ] 添加 ArgoCD Helm 仓库
  - [ ] 配置 values.yaml（副本数、资源限制、Ingress）
  - [ ] 配置 Kubernetes Secret（初始密码、认证凭据）
  - [ ] 配置 Traefik Ingress（TLS 证书）
  - [ ] 配置 RBAC 权限

- [ ] Task 2: ArgoCD 部署与验证 (AC: 1, 2, 3)
  - [ ] 执行 helm install 部署 ArgoCD
  - [ ] 验证 Pod 运行状态（Running 1/1）
  - [ ] 验证服务可访问（健康检查通过）
  - [ ] 获取初始 admin 密码（kubectl get secret）
  - [ ] 首次登录修改密码
  - [ ] 绿灯测试通过

- [ ] Task 3: HTTPS 证书配置 (AC: 2)
  - [ ] 配置 Traefik Ingress
  - [ ] 创建自签名 TLS 证书（开发环境）
  - [ ] 配置 HSTS 响应头（Middleware）
  - [ ] 验证 HTTPS 访问（通过 Traefik）
  - [ ] Let's Encrypt 证书（生产环境使用）

- [ ] Task 4: Gitea 仓库集成 (AC: 4)
  - [ ] 创建 Gitea Personal Access Token
  - [ ] ArgoCD 添加 Gitea 仓库凭据
  - [ ] 配置 Webhook 自动触发
  - [ ] 验证 Git 仓库连接
  - [ ] 测试 Webhook 触发

- [ ] Task 5: Harbor 镜像仓库集成 (AC: 5)
  - [ ] 配置 Harbor 仓库凭据
  - [ ] 安装 ArgoCD Image Updater
  - [ ] 配置镜像更新策略
  - [ ] 验证镜像自动更新流程
  - [ ] 测试端到端 GitOps 流程

- [ ] Task 6: Application 配置 (AC: 6)
  - [ ] 创建 ArgoCD Application（声明式）
  - [ ] 配置自动同步策略（self-heal, auto-prune）
  - [ ] 配置健康检查（Health Check）
  - [ ] 验证同步状态
  - [ ] 测试回滚功能

- [ ] Task 7: 多环境配置 (AC: 7)
  - [ ] 创建 Dev/Test/Prod 命名空间
  - [ ] 配置 Kustomize 多环境覆盖
  - [ ] 配置环境晋升流程
  - [ ] 配置 RBAC 环境隔离
  - [ ] 验证环境隔离

- [ ] Task 8: 安全加固
  - [ ] 配置容器以非 root 用户运行
  - [ ] 配置 NetworkPolicy（DefaultDeny）
  - [ ] 配置只读根文件系统
  - [ ] 禁用特权模式
  - [ ] 配置审计日志

- [ ] Task 9: 架构合规验证
  - [ ] 验证 TLS 1.3 强制启用
  - [ ] 验证存储使用 local-path
  - [ ] 验证 Ingress 配置（Traefik 443 → argocd-server:443）
  - [ ] 验证密钥存储于 Kubernetes Secret
  - [ ] 运行所有 TDD 测试

- [ ] Task 10: 代码审查修复
  - [ ] 修复 HIGH 优先级问题
  - [ ] 修复 MEDIUM 优先级问题
  - [ ] 修复 LOW 优先级问题

- [ ] Task 11: 功能验证
  - [ ] AC-1: ArgoCD 部署验证
  - [ ] AC-2: Web 界面访问
  - [ ] AC-3: 管理员登录
  - [ ] AC-4: Gitea 集成
  - [ ] AC-5: Harbor 集成
  - [ ] AC-6: Application 同步
  - [ ] AC-7: 多环境配置

## Dev Notes

### 技术栈

- **ArgoCD**: v3.3.2 ✅ (已由 epics_v1.0.md 确认)
- **Helm**: v3.x
- **Ingress**: Traefik v3.x (Story 0.4 已部署)
- **存储**: local-path-provisioner (Story 0.4 已部署)
- **Git**: Gitea v1.25.4 (Story 0.5 已部署)
- **镜像仓库**: Harbor v2.14.3 (Story 0.6 已部署)

### 网络架构

**来源**: [architecture-epic0.md](../../planning-artifacts/architecture-epic0.md#网络架构)

```
互联网 (80/443)
    │
    ▼
Traefik v3.x 反向代理
    │
    ├─→ argocd.sisys.local:443 (TLS 1.3)
    │         │
    │         ▼
    │   argocd-server:443 (容器内部端口)
    │
    ├─→ harbor.sisys.local:443 (Story 0.6 ✅ 已完成)
    │
    └─→ gitea.sisys.local:443 (Story 0.5 ✅ 已完成)
```

**网络配置详情:**

| 配置项 | 值 | 说明 |
|--------|-----|------|
| **外部访问 URL** | https://argocd.sisys.local | Traefik Ingress 443 端口 |
| **内部服务名** | argocd-server | K8s Service 名称 |
| **容器端口** | 443 | ArgoCD HTTPS 服务端口 |
| **TLS 版本** | TLS 1.3 | 强制启用，禁用 TLS 1.2 以下 |
| **证书颁发机构** | Let's Encrypt | 自动续期 (90 天) |
| **网络策略** | DefaultDeny | 仅允许 Traefik Ingress 访问 |

### 架构合规要求

**来源**: [architecture.md](../../planning-artifacts/architecture.md)

1. **六边形架构原则**: ArgoCD 作为外部系统，通过适配器模式集成
   - ArgoCD Webhook → 事件总线 (RabbitMQ)
   - ArgoCD API → 应用层服务调用

2. **事件驱动架构**:
   - Gitea 代码推送事件 → 触发 ArgoCD 同步
   - Harbor 镜像推送事件 → 触发 ArgoCD 部署

3. **存储要求**:
   - ArgoCD 配置存储：local-path-provisioner (NVMe SSD)
   - 备份存储：10T HDD (K3S 定时备份)

### 安全配置

**来源**: [architecture-epic0.md](../../planning-artifacts/architecture-epic0.md#开发-ci-cd-系统安全架构)

**TLS/SSL 安全:**
- TLS 1.3 强制启用 (禁用 TLS 1.2 及以下版本)
- HSTS (HTTP Strict Transport Security) 启用
- 证书自动续期 (Let's Encrypt 90 天)
- 安全密码套件 (仅允许 AEAD 加密算法)

**RBAC 权限控制:**
- 管理员密码复杂度要求：
  - 最小长度：12 位
  - 必须包含：大写字母 + 小写字母 + 数字 + 特殊符号
  - 密码历史：不得重复最近 5 次密码
- 启用双因素认证 (2FA) - 推荐管理员强制启用

**密钥管理:**
- ArgoCD Secret 密钥 (至少 32 字节随机字符串)
- 数据库密码存储于 Kubernetes Secret
- 禁用配置文件中的明文密码

**容器安全:**
- 使用非 root 用户运行 ArgoCD 容器
- 只读根文件系统 (readOnlyRootFilesystem: true)
- 禁用特权模式 (privileged: false)
- 限制 Linux Capabilities

**网络安全:**
- NetworkPolicy 默认拒绝 (DefaultDeny)
- 仅允许 Traefik Ingress 访问 ArgoCD HTTPS 端口
- 仅允许 Gitea Runner 访问 ArgoCD API (如启用)

**安全扫描:**
- 镜像漏洞扫描 (Trivy - Story 0.6)
- 依赖漏洞扫描 (ArgoCD 内置)
- 定期安全审计 (每季度)

### 依赖关系

**前置依赖:**
- ✅ Story 0.4: K3S 集群部署 (已完成)
  - K3S v1.34.5 ✅
  - Traefik v3.x ✅
  - local-path-provisioner ✅
- ✅ Story 0.5: Gitea 代码托管 (已完成)
- ✅ Story 0.6: Harbor 镜像仓库 (已完成)

**后置依赖:**
- → Story 0.8: Gitea Runner 配置 (可并行)
- → Story 0.9: CI/CD Pipeline 模板 (依赖本 Story + Story 0.8)

### 与 Gitea/Harbor 集成

**来源**: [architecture-epic0.md](../../planning-artifacts/architecture-epic0.md#开发-ci-cd-系统组件架构)

**集成架构图:**

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Gitea     │─────▶│   Harbor    │─────▶│   ArgoCD    │
│  v1.25.4    │      │  v2.14.3    │      │  v3.3.2     │
│  代码托管    │      │  镜像仓库    │      │  持续部署    │
└─────────────┘      └─────────────┘      └─────────────┘
      │                    │                    │
      │ 1. 代码推送         │ 2. 镜像推送         │ 3. 自动部署
      │    Webhook         │    Robot Account   │    GitOps
      ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────┐
│                    K3S 集群                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Gitea Runner (Story 0.8)                        │   │
│  │  - 监听 Gitea Webhook                            │   │
│  │  - 执行 CI/CD Pipeline                           │   │
│  │  - 构建镜像并推送 Harbor                         │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**集成配置详情:**

| 集成项 | 配置内容 | 用途 | 归属 Story |
|--------|---------|------|-----------|
| **Gitea → ArgoCD** | Webhook 配置 | CI/CD 触发 | Story 0.8 |
| **Harbor → ArgoCD** | Image Updater Webhook | 自动触发部署 | 本 Story |
| **ArgoCD → Gitea** | Git 仓库凭据 | GitOps 配置 | 本 Story |
| **ArgoCD → Harbor** | 镜像拉取凭据 | 部署认证 | 本 Story |

**本 Story (0.7) 集成工作:**

1. **ArgoCD → Gitea 集成**
   - 创建 Gitea Personal Access Token
   - ArgoCD 添加 Gitea 仓库凭据
   - 配置 Webhook 自动触发

2. **ArgoCD → Harbor 集成**
   - 配置 Harbor 仓库凭据
   - 安装 ArgoCD Image Updater
   - 配置镜像更新策略

3. **Git 仓库结构规划**
   ```
   sisys/
   ├── deployments/
   │   ├── harbor/          # Story 0.6: Harbor 部署配置
   │   ├── gitea/           # Story 0.5: Gitea 部署配置
   │   └── argocd/          # 本 Story: ArgoCD 部署配置
   │   └── apps/            # ArgoCD Application 配置
   │       ├── dev/         # 开发环境
   │       ├── test/        # 测试环境
   │       └── prod/        # 生产环境
   └── docs/
       └── deployment/      # 部署文档
   ```

### 存储架构

**来源**: [architecture-epic0.md](../../planning-artifacts/architecture-epic0.md#存储架构)

```
┌─────────────────────┐
│   1T NVMe SSD       │
│                     │
│  ┌───────────────┐  │
│  │ ArgoCD 配置    │  │ ← 10Gi PVC
│  │ Git 仓库缓存   │  │
│  └───────────────┘  │
│                     │
│  ┌───────────────┐  │
│  │ Harbor 镜像    │  │ ← 500Gi PVC (Story 0.6)
│  │ Docker 镜像    │  │
│  └───────────────┘  │
│                     │
│  ┌───────────────┐  │
│  │ PostgreSQL    │  │ ← 10Gi PVC (Story 0.4/0.6)
│  │ 数据库         │  │
│  └───────────────┘  │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│   10T HDD (备份)    │
│                     │
│  ┌───────────────┐  │
│  │ K3S 备份       │  │
│  │ etcd 快照      │  │
│  └───────────────┘  │
└─────────────────────┘
```

**存储配置详情:**

| 存储项 | 类型 | 容量 | 存储类 | 说明 |
|--------|------|------|--------|------|
| **ArgoCD 配置存储** | PVC | 10Gi | local-path (NVMe SSD) | Git 仓库缓存、应用配置 |
| **ArgoCD Secret** | Secret | - | - | 密钥、密码、Token |
| **Harbor 镜像存储** | PVC | 500Gi | local-path (NVMe SSD) | Docker 镜像、Helm Chart |
| **PostgreSQL 数据** | PVC | 10Gi | local-path (NVMe SSD) | Harbor 数据库 |
| **K3S 备份** | CronJob | - | 10T HDD | K3S 定时备份 (etcd-snapshot) |

### 资源分配

**来源**: [architecture-epic0.md](../../planning-artifacts/architecture-epic0.md#资源分配)

| 资源 | 分配量 | 说明 |
|------|--------|------|
| CPU | 2 核 | ArgoCD 核心服务 |
| 内存 | 4GB | ArgoCD 运行时内存 |
| 存储 | 10Gi | 配置存储 (NVMe SSD) |

**MVP 临时配置 vs 架构规划:**

| 资源项 | MVP 配置 | 架构规划 (architecture-epic0.md) | 说明 |
|--------|---------|--------------------------------|------|
| **CPU** | 2 Cores | 2 核 | 符合架构规划 |
| **内存** | 4Gi | 4GB | 符合架构规划 |
| **存储** | 10Gi | 10Gi | 符合架构规划 |

**扩容触发条件:**
- CPU 使用率持续>80% (5 分钟平均)
- 内存使用率持续>85% (5 分钟平均)
- 存储使用率>80%
- 用户反馈性能问题

**扩容目标值:**
- CPU: 4 Cores (保留增长空间)
- 内存: 8Gi (保留增长空间)
- 存储: 20Gi (根据 GitOps 配置使用情况)

### 实施指南

**参考文档**: `docs/deployment/ARGOCD_INSTALLATION.md` (待创建)

**实施步骤**:

1. **添加 Helm 仓库**
   ```bash
   helm repo add argo https://argoproj.github.io/argo-helm
   helm repo update
   ```

2. **创建命名空间**
   ```bash
   kubectl create namespace argocd
   ```

3. **配置 values.yaml**
   - 副本数：1 (MVP)
   - 资源限制：CPU 2Core, Memory 4Gi
   - 存储：10Gi (local-path-provisioner)

4. **部署 ArgoCD**
   ```bash
   helm install argocd argo/argo-cd -n argocd -f values.yaml
   ```

5. **配置 Ingress**
   - Host: argocd.sisys.local
   - TLS: Let's Encrypt
   - Backend: argocd-server:443

6. **初始化配置**
   - 获取初始 admin 密码
   - 访问 https://argocd.sisys.local
   - 修改 admin 密码
   - 配置 Gitea/Harbor 集成

### 测试要求

**TDD 测试用例**:

#### 基础功能测试（6 个）

1. **ArgoCD 部署测试**
   ```python
   def test_argocd_pod_running():
       """验证 ArgoCD Pod 运行状态"""
       # kubectl get pods -n argocd
       # 期望：STATUS=Running，无 CrashLoopBackOff 或 Error 状态
       # 验收：所有 Pod Running，restart count < 3
   ```

2. **服务可访问性测试**
   ```python
   def test_argocd_web_accessible():
       """验证 ArgoCD Web 界面可访问"""
       # curl -k https://argocd.sisys.local
       # 期望：HTTP 200, 包含"ArgoCD"标题，页面加载时间 < 3 秒
   ```

3. **管理员登录测试**
   ```python
   def test_argocd_admin_login():
       """验证 admin 账号登录"""
       # 获取初始密码：kubectl get secret argocd-initial-admin-secret -n argocd
       # 登录测试：argocd login argocd.sisys.local --username admin --password {PASSWORD}
       # 期望：登录成功，首次登录强制修改密码
   ```

4. **Git 仓库连接测试**
   ```python
   def test_argocd_gitea_connection():
       """验证 Gitea 仓库连接"""
       # argocd repo add https://gitea.sisys.local/sisys/sisys.git --username {USER} --password {TOKEN}
       # 期望：仓库连接成功，无认证错误
   ```

5. **镜像更新测试**
   ```python
   def test_argocd_image_update():
       """验证 ArgoCD Image Updater 功能"""
       # 推送新镜像到 Harbor
       # 期望：Image Updater 检测到新 tag，自动更新 Deployment
   ```

6. **HTTPS 证书测试**
   ```python
   def test_argocd_https_certificate():
       """验证 HTTPS 证书有效"""
       # openssl s_client -connect argocd.sisys.local:443
       # 期望：证书有效，Issuer=Let's Encrypt，TLS 1.3，SSL Labs 评级 ≥ A
   ```

#### 集成测试场景（4 个）

7. **Gitea Webhook 集成测试**
   ```python
   def test_gitea_webhook_trigger_argocd():
       """验证 Gitea 代码推送触发 ArgoCD 同步"""
       # 步骤 1: 配置 Gitea Webhook（代码推送事件 → ArgoCD）
       # 步骤 2: 推送代码到 Gitea 仓库
       #   git push gitea.sisys.local/sisys/sisys.git main
       # 步骤 3: ArgoCD 检测到 Git 变更
       # 步骤 4: ArgoCD 自动同步应用配置
       # 期望：
       # - Gitea Webhook 触发成功（HTTP 200）
       # - ArgoCD 检测到 Git 变更（< 1 分钟）
       # - ArgoCD 同步成功（Application Synced）
       # - K8s 资源更新成功
   ```

8. **Harbor 镜像更新测试**
   ```python
   def test_harbor_image_trigger_argocd():
       """验证 Harbor 镜像推送触发 ArgoCD 部署"""
       # 步骤 1: 配置 ArgoCD Image Updater 监听 Harbor 镜像
       # 步骤 2: 推送新镜像到 Harbor（带新 tag）
       #   docker push harbor.sisys.local/sisys/app:v1.0.1
       # 步骤 3: ArgoCD Image Updater 检测到新镜像
       # 步骤 4: ArgoCD 自动更新 K8s Deployment 镜像 tag
       # 期望：
       # - Image Updater 检测到新镜像（Webhook 触发 < 1 分钟）
       # - ArgoCD 自动更新 Deployment 镜像 tag
       # - K3S 滚动更新成功（新 Pod Running，旧 Pod Terminated）
       # - 应用健康检查通过（/health 端点 HTTP 200）
       # - 部署时间 < 5 分钟（从镜像推送到应用可用）
   ```

9. **多环境配置测试**
   ```python
   def test_argocd_multi_environment():
       """验证多环境（Dev/Test/Prod）配置"""
       # 步骤 1: 创建 Dev/Test/Prod 命名空间
       # 步骤 2: 配置 Kustomize 多环境覆盖
       # 步骤 3: 创建 ArgoCD Application（各环境独立）
       # 步骤 4: 验证环境隔离
       # 期望：
       # - 各环境独立命名空间
       # - Kustomize 覆盖正确应用
       # - 环境间配置差异正确
       # - RBAC 权限隔离有效
   ```

10. **端到端 GitOps 测试**
    ```python
    def test_e2e_gitops_pipeline():
        """验证完整 GitOps Pipeline 流程"""
        # 步骤 1: 代码提交到 Gitea
        #   git commit -m "feat: add new feature" && git push
        # 步骤 2: Gitea Runner 触发 CI/CD Pipeline（Story 0.9）
        #   - 代码质量 (Ruff + MyPy)
        #   - 单元测试 (pytest + cov≥80%)
        #   - 集成测试 (Docker Compose/K3S)
        #   - 安全扫描 (Trivy + Bandit)
        #   - 镜像构建 (Docker Build)
        #   - 镜像推送 (Harbor with Robot Account)
        # 步骤 3: Harbor 镜像推送触发 ArgoCD 部署
        # 步骤 4: 验证应用部署成功并可访问
        # 期望：
        # - Pipeline 触发成功（Webhook 延迟 < 10 秒）
        # - 代码质量阶段通过（Ruff 无 error，MyPy 类型检查通过）
        # - 单元测试通过（覆盖率≥80%）
        # - 集成测试通过（所有 E2E 测试用例通过）
        # - 安全扫描通过（Trivy 高危漏洞=0，Bandit 无 high severity）
        # - 镜像构建成功（Docker image 创建成功）
        # - 镜像推送成功（Harbor 接收镜像）
        # - ArgoCD 自动部署成功（Synced + Healthy）
        # - 应用健康检查通过（/health 端点 HTTP 200）
        # - 总 Pipeline 时间 < 15 分钟
    ```

#### 架构合规验证测试（5 个）

11. **TLS 配置验证测试**
    ```python
    def test_argocd_tls_configuration():
        """验证 TLS 1.3 强制启用"""
        # 步骤 1: 使用 openssl 测试 TLS 版本
        #   openssl s_client -connect argocd.sisys.local:443 -tls1_3
        # 步骤 2: 测试 TLS 1.2 被拒绝
        #   openssl s_client -connect argocd.sisys.local:443 -tls1_2
        # 步骤 3: 检查 HSTS 响应头
        #   curl -I https://argocd.sisys.local
        # 期望：
        # - TLS 1.3 连接成功
        # - TLS 1.2 连接被拒绝（或降级警告）
        # - HSTS 响应头存在（Strict-Transport-Security: max-age=31536000）
        # - 仅允许 AEAD 加密套件
    ```

12. **存储配置验证测试**
    ```python
    def test_argocd_storage_configuration():
        """验证存储使用 local-path (NVMe SSD)"""
        # 步骤 1: 检查 PVC 存储类
        #   kubectl get pvc -n argocd -o jsonpath='{.items[*].spec.storageClassName}'
        # 步骤 2: 验证 PVC 绑定状态
        #   kubectl get pvc -n argocd
        # 步骤 3: 检查实际存储路径
        #   kubectl exec -n argocd <argocd-repo-server-pod> -- df -h
        # 期望：
        # - 存储类为 local-path
        # - PVC 状态为 Bound
        # - 存储路径挂载正确（/var/lib/rancher/k3s/storage）
        # - 存储容量符合预期（10Gi）
    ```

13. **Ingress 配置验证测试**
    ```python
    def test_argocd_ingress_configuration():
        """验证 Ingress 配置 (Traefik 443 → argocd-server:443)"""
        # 步骤 1: 检查 Ingress 规则
        #   kubectl get ingress -n argocd -o yaml
        # 步骤 2: 验证 Traefik 路由配置
        #   kubectl get traefikservices -n argocd
        # 步骤 3: 测试外部访问
        #   curl -k https://argocd.sisys.local/api/version
        # 期望：
        # - Ingress 规则正确（host: argocd.sisys.local）
        # - Backend 服务为 argocd-server:443
        # - TLS 配置正确（secretName: argocd-tls-secret）
        # - 外部访问成功（HTTP 200）
    ```

14. **密钥管理验证测试**
    ```python
    def test_argocd_secret_management():
        """验证密钥存储于 Kubernetes Secret"""
        # 步骤 1: 检查 Secret 列表
        #   kubectl get secrets -n argocd
        # 步骤 2: 验证 Secret 内容（无明文密码）
        #   kubectl get secret <secret-name> -n argocd -o jsonpath='{.data}'
        # 步骤 3: 检查配置文件引用 Secret
        #   kubectl get deployment argocd-server -n argocd -o yaml
        # 期望：
        # - 所有敏感信息存储于 Secret（argocd-secret, argocd-initial-admin-secret 等）
        # - Secret 数据为 base64 编码（无明文）
        # - Deployment 通过 envFrom 或 volumeMounts 引用 Secret
        # - 配置文件中无明文密码
    ```

15. **网络安全验证测试**
    ```python
    def test_argocd_network_security():
        """验证 NetworkPolicy 安全配置"""
        # 步骤 1: 检查 NetworkPolicy
        #   kubectl get networkpolicy -n argocd
        # 步骤 2: 验证 DefaultDeny 策略
        #   kubectl get networkpolicy default-deny -n argocd -o yaml
        # 步骤 3: 测试仅 Traefik 可访问 ArgoCD
        #   kubectl run test-pod --rm -it --image=busybox --restart=Never -- \
        #     nc -zv argocd-server.argocd.svc.cluster.local 443
        # 期望：
        # - NetworkPolicy 存在（default-deny + allow-traefik）
        # - 默认拒绝所有入站流量
        # - 仅允许 Traefik Ingress 访问 ArgoCD HTTPS 端口
        # - 非授权 Pod 无法访问 ArgoCD（连接被拒绝）
    ```

### 项目结构对齐

**统一项目结构**:

```
sisys/
├── docs/
│   └── deployment/
│       ├── ARGOCD_INSTALLATION.md       # ArgoCD 部署指南
│       ├── ARGOCD_IMAGE_UPDATER.md      # Image Updater 配置
│       └── ARGOCD_MULTI_ENV.md          # 多环境配置
├── deployments/
│   └── argocd/
│       ├── values.yaml                  # Helm Chart 配置
│       ├── ingress.yaml                 # Ingress 配置
│       ├── rbac.yaml                    # RBAC 配置
│       └── kustomization.yaml           # Kustomize 配置
├── apps/
│   ├── dev/                             # 开发环境配置
│   ├── test/                            # 测试环境配置
│   └── prod/                            # 生产环境配置
└── tests/
    └── deployment/
        └── test_argocd.py               # ArgoCD 部署测试
```

### 已知风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| Gitea 认证失败 | 无法连接仓库 | 中 | 验证 Personal Access Token 权限，检查网络策略 |
| HTTPS 证书申请失败 | 无法 HTTPS 访问 | 中 | 检查 Traefik cert-manager 配置，确认 DNS 解析 |
| Image Updater 不工作 | 无法自动更新 | 中 | 验证 Harbor Webhook 配置，检查 Image Updater 日志 |
| 多环境配置混乱 | 环境间污染 | 低 | 严格 Kustomize 覆盖，RBAC 隔离 |

### 验收标准检查清单

**功能验收:**
- [ ] ArgoCD Pod 运行正常 (kubectl get pods -n argocd)
- [ ] ArgoCD Web 界面可访问 (https://argocd.sisys.local)
- [ ] admin 账号登录成功
- [ ] Gitea 仓库连接成功
- [ ] Harbor 镜像更新功能可用
- [ ] Application 同步状态正常
- [ ] 多环境配置成功
- [ ] 所有 TDD 测试通过

**安全验收:**
- [ ] TLS 1.3 强制启用 (SSL Labs 测试 A+ 评级)
- [ ] HSTS 启用 (Strict-Transport-Security 响应头)
- [ ] admin 密码符合复杂度要求 (12 位 + 大小写 + 数字 + 符号)
- [ ] 2FA 已配置 (管理员强制启用)
- [ ] 容器以非 root 用户运行
- [ ] NetworkPolicy 已配置 (DefaultDeny)
- [ ] 审计日志功能可用

**架构验收:**
- [ ] 存储使用 local-path (NVMe SSD)
- [ ] Ingress 配置正确 (Traefik 443 → argocd-server:443)
- [ ] 密钥存储于 Kubernetes Secret (无明文配置)
- [ ] 资源限制已配置 (CPU 2Core, Memory 4Gi)

## Dev Agent Record

### Agent Model Used

Qwen Code (AI 开发助手)

### Debug Log References

- K3S 集群状态：Story 0.4 完成记录 ✅
- Helm Chart 版本：argo/argo-cd v7.x (ArgoCD v3.3.2) ✅
- Traefik Ingress 配置：Story 0.4 已验证 ✅
- Gitea 部署状态：Story 0.5 完成记录 ✅
- Harbor 部署状态：Story 0.6 完成记录 ✅

### Implementation Notes

**Session Date:** 2026-03-15

**故事创建完成:**
- ✅ 故事需求分析完成
- ✅ 验收标准定义完成（7 项 AC）
- ✅ 任务分解完成（11 个 Task）
- ✅ 技术栈确认（ArgoCD v3.3.2）
- ✅ 依赖关系确认（Story 0.4/0.5/0.6 已完成）
- ✅ 架构合规要求提取完成
- ✅ 安全配置要求提取完成
- ✅ 测试用例定义完成（15 个测试）
- ✅ 项目结构对齐完成
- ✅ 风险评估完成

**下一步:**
1. 运行 `dev-story` 执行开发实施
2. 完成后运行 `code-review` 进行代码审查
3. 可选：运行 `validate-create-story` 进行质量检查

### File List

- `/mnt/g/ai/sisys/_bmad-output/implementation-artifacts/stories/0-7-argocd-continuous-deployment.md` - 故事文件
- `/mnt/g/ai/sisys/_bmad-output/implementation-artifacts/sprint-status.yaml` - Sprint 状态（已更新）

### Completion Notes

**故事创建完成时间:** 2026-03-15
**故事状态:** ready-for-dev
**下一步执行:** dev-story（开发实施）
