# ArgoCD Application 配置指南

本文档介绍如何配置和使用 ArgoCD Application 管理 SISYS 应用。

## 目录结构

```
deploy/kubernetes/
├── argocd/
│   └── applications/
│       ├── sisys-app-of-apps.yaml   # App of Apps - 管理所有子应用
│       ├── sisys-app-dev.yaml       # Dev 环境 Application
│       ├── sisys-app-test.yaml      # Test 环境 Application
│       └── sisys-app-prod.yaml      # Prod 环境 Application
└── apps/
    └── sisys/
        ├── base/                    # 基础配置
        │   └── kustomization.yaml
        ├── dev/                     # 开发环境
        │   └── kustomization.yaml
        ├── test/                    # 测试环境
        │   └── kustomization.yaml
        └── prod/                    # 生产环境
            └── kustomization.yaml
```

## 快速开始

### 1. 部署 App of Apps

```bash
# 使用 App of Apps 模式部署所有环境
kubectl apply -f deploy/kubernetes/argocd/applications/sisys-app-of-apps.yaml
```

### 2. 验证 Application 状态

```bash
# 查看 App of Apps 状态
kubectl get application sisys-app-of-apps -n argocd

# 查看所有子应用
kubectl get application -n argocd -l app.kubernetes.io/part-of=sisys

# 查看详细信息
kubectl get application sisys-app-dev -n argocd -o yaml

# 使用 ArgoCD CLI
argocd app list -n argocd | grep sisys
```

### 3. 查看同步状态

```bash
# 查看同步状态
argocd app list -n argocd

# 等待应用同步完成
argocd app wait sisys-app-dev --health -n argocd
```

## Application 配置说明

### 核心配置

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: sisys-app-dev
  namespace: argocd
spec:
  project: default

  # 源代码配置
  source:
    repoURL: https://gitea.sisys.local/sisys/sisys.git
    targetRevision: HEAD
    path: deploy/kubernetes/apps/sisys/dev

    # Kustomize 配置
    kustomize:
      images:
        - sisys/harbor.sisys.local/sisys/app:latest

  # 目标配置
  destination:
    server: https://kubernetes.default.svc
    namespace: sisys-dev

  # 同步策略
  syncPolicy:
    automated:
      prune: true      # 自动删除不存在于 Git 的资源
      selfHeal: true   # 自动修复偏离 Git 的状态
      allowEmpty: true # 允许空列表
```

### 自动同步策略

| 选项 | 说明 | 推荐值 |
|------|------|--------|
| `prune` | 自动删除 Git 中不存在的资源 | `true` |
| `selfHeal` | 检测到偏离时自动同步 | `true` |
| `allowEmpty` | 允许同步空列表（删除所有资源） | `true` |

### 同步选项

```yaml
syncPolicy:
  syncOptions:
    - CreateNamespace=true           # 自动创建命名空间
    - PrunePropagationPolicy=foreground  # 前景传播（顺序删除）
    - PruneLast=true                 # 最后修剪
    - Validate=true                  # 验证 webhook
    - Retry=true                     # 失败时重试
    - ServerSideApply=true           # 服务端应用
```

## 多环境配置

### 环境隔离

使用 Kustomize 实现多环境隔离：

| 环境 | Application | 命名空间 | 副本数 | 资源限制 | 镜像 Tag | 同步策略 |
|------|------------|---------|--------|---------|---------|---------|
| Dev | `sisys-app-dev` | `sisys-dev` | 1 | 200m CPU / 256Mi Mem | `latest` | 完全自动 |
| Test | `sisys-app-test` | `sisys-test` | 2 | 500m CPU / 512Mi Mem | `v1.0.0` | 自动 + 审批 |
| Prod | `sisys-app-prod` | `sisys-prod` | 3 | 1000m CPU / 1Gi Mem | `v1.0.0` | 手动同步 |

### 环境 Application

每个环境独立的 Application：

```bash
# 开发环境 - 完全自动同步
kubectl apply -f deploy/kubernetes/argocd/applications/sisys-app-dev.yaml

# 测试环境 - 自动同步但需要审批
kubectl apply -f deploy/kubernetes/argocd/applications/sisys-app-test.yaml

# 生产环境 - 手动同步（需要人工批准）
kubectl apply -f deploy/kubernetes/argocd/applications/sisys-app-prod.yaml
```

### App of Apps 模式

使用 App of Apps 模式统一管理所有环境：

```bash
# 部署 App of Apps
kubectl apply -f deploy/kubernetes/argocd/applications/sisys-app-of-apps.yaml

# App of Apps 将自动创建和管理所有子应用
# 子应用列表:
# - sisys-app-dev
# - sisys-app-test
# - sisys-app-prod
```

## 健康检查配置

### 忽略差异配置

```yaml
spec:
  ignoreDifferences:
    # 忽略 HPA 管理的副本数
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas

    # 忽略 ConfigMap 的注解
    - group: ""
      kind: ConfigMap
      jsonPointers:
        - /metadata/annotations
```

### 健康检查端点

| 端点 | 用途 | 配置 |
|------|------|------|
| `/health` | 存活探针 | 初始延迟 30s，周期 10s |
| `/ready` | 就绪探针 | 初始延迟 5s，周期 5s |

## 回滚操作

### 查看历史版本

```bash
# 查看同步历史
argocd app history sisys-app-dev -n argocd

# 输出示例:
# ID  DATE                           REVISION
# 0   2026-03-16 10:00:00 +0000 UTC  main
# 1   2026-03-16 11:00:00 +0000 UTC  main
```

### 执行回滚

```bash
# 回滚到指定版本
argocd app rollback sisys-app-dev 1 -n argocd

# 回滚并等待完成
argocd app rollback sisys-app-dev 1 -n argocd --wait

# 回滚并修剪资源
argocd app rollback sisys-app-dev 1 -n argocd --prune
```

### 使用 Git 回滚

```bash
# 在 Git 仓库中 revert 提交
cd /path/to/sisys
git revert <commit-hash>
git push origin main

# ArgoCD 将自动检测并同步
```

## 监控和告警

### 查看 Application 日志

```bash
# 查看 ArgoCD 控制器日志
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller

# 查看 Application 事件
kubectl get events -n argocd --field-selector involvedObject.name=sisys-app-dev
```

### Prometheus 指标

```yaml
# 关键指标
argocd_app_info{sync_status="Synced"}      # 同步状态
argocd_app_info{health_status="Healthy"}   # 健康状态
argocd_app_operation_running             # 同步操作进行中
```

## 故障排除

### 常见问题

#### 1. Application 无法同步

**症状**: Application 状态为 `OutOfSync`

**排查步骤**:
```bash
# 查看详细状态
argocd app get sisys-app-dev -n argocd

# 查看同步日志
argocd app logs sisys-app-dev -n argocd

# 检查 Git 仓库连接
argocd repo list -n argocd
```

#### 2. 健康检查失败

**症状**: Health 状态为 `Degraded` 或 `Missing`

**排查步骤**:
```bash
# 检查 Pod 状态
kubectl get pods -n sisys-dev

# 查看 Pod 日志
kubectl logs -n sisys-dev -l app.kubernetes.io/name=sisys-app

# 检查服务配置
kubectl get svc -n sisys-dev
```

#### 3. 镜像拉取失败

**症状**: `ImagePullBackOff` 或 `ErrImagePull`

**排查步骤**:
```bash
# 检查镜像拉取密钥
kubectl get secrets -n sisys-dev

# 验证镜像存在
curl -u admin:password https://harbor.sisys.local/v2/sisys/app/tags/list
```

## 最佳实践

### 1. Git 仓库结构

```
sisys/
├── deploy/kubernetes/
│   ├── argocd/
│   │   └── applications/
│   │       ├── sisys-app-of-apps.yaml
│   │       ├── sisys-app-dev.yaml
│   │       ├── sisys-app-test.yaml
│   │       └── sisys-app-prod.yaml
│   └── apps/
│       └── sisys/
│           ├── base/
│           ├── dev/
│           ├── test/
│           └── prod/
```

### 2. 分支策略

| 环境 | 分支 | 触发条件 |
|------|------|---------|
| Dev | `main` | 每次提交自动部署 |
| Test | `release/*` | 创建 release 分支 |
| Prod | `tags/v*` | 打版本 tag |

### 3. 同步策略

- **Dev**: 完全自动同步（self-heal + auto-prune）
- **Test**: 自动同步 + 手动审批
- **Prod**: 手动同步 + 双人审批

### 4. 安全配置

- 使用 Kubernetes Secret 存储敏感信息
- 启用 RBAC 权限控制
- 配置 NetworkPolicy 限制访问
- 定期轮换 Git Token 和镜像仓库密码

## 相关文档

- [ArgoCD 官方文档](https://argo-cd.readthedocs.io/)
- [Kustomize 文档](https://kustomize.io/)
- [ArgoCD Application 管理](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/)
- [ArgoCD App of Apps 模式](https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/)
