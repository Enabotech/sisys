# 镜像标签命名策略

> 文档版本：1.0.0  
> 创建日期：2026-03-31  
> 最后更新：2026-03-31

## 概述

本文档定义 SISYS 项目的 Docker 镜像标签命名规范，确保 CI/CD 流程中镜像版本的一致性和可追溯性。

## 镜像分层架构

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: 应用镜像 (Application Image)                        │
│ 镜像名：harbor.sisys.local/sisys/app                         │
│ 标签格式：l3-v{major}.{minor}.{patch}-{git_sha}             │
│ 构建触发：代码提交 (main/develop 分支)                        │
└─────────────────────────────────────────────────────────────┘
                              ↑
                              │ 基于
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: CI/CD 依赖镜像 (CI/CD Dependency Image)             │
│ 镜像名：harbor.sisys.local/sisys/dependency                  │
│ 标签格式：l2-v{major}.{minor}.{patch}-{git_sha}             │
│ 构建触发：pyproject.toml 变更                                │
└─────────────────────────────────────────────────────────────┘
                              ↑
                              │ 基于
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: 基础依赖镜像 (Base Dependency Image)                │
│ 镜像名：harbor.sisys.local/sisys/dependency                  │
│ 标签格式：l1-v{major}.{minor}.{patch}-{timestamp}           │
│ 构建触发：基础工具链变更 (Python/Node.js/Poetry)            │
└─────────────────────────────────────────────────────────────┘
```

## 标签命名规则

### 通用格式

```
{layer}-v{semver}-{identifier}
```

### CI/CD 引用标签

在 CI/CD 流程中，使用 `latest` 标签引用最新稳定版本：

| 层级 | CI 引用标签 | 用途 | 说明 |
|------|-----------|------|------|
| L1 | `l1-latest` | CI 构建时引用 | 指向最新基础依赖镜像 |
| L2 | `l2-latest` | CI 构建时引用 | 指向最新 CI/CD 依赖镜像 |
| L3 | `l3-latest` | CD 部署时引用 | 指向最新应用镜像 (测试环境) |

### 版本标签 vs Latest 标签

```
┌─────────────────────────────────────────────────────────────┐
│ 版本标签 (唯一，不可变)                                      │
│ l1-v1.0.0-a1b2c3d  ← 每次构建生成唯一标签，永久保留          │
│ l2-v1.0.0-a1b2c3d                                           │
│ l3-v1.0.0-a1b2c3d                                           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Latest 标签 (可变，指向最新稳定版本)                          │
│ l1-latest  ← 始终指向最新的 l1-v{version}-{sha}             │
│ l2-latest  ← 始终指向最新的 l2-v{version}-{sha}             │
│ l3-latest  ← 始终指向最新的 l3-v{version}-{sha}             │
└─────────────────────────────────────────────────────────────┘
```

**使用原则：**
- **CI 构建**：使用 `l1-latest`/`l2-latest` 引用基础镜像
- **CD 部署**：测试环境使用 `l3-latest`，生产环境使用 `v{semver}`
- **版本追溯**：每次构建生成带 SHA 的唯一版本标签，永久保留

### 各层详细规则

#### Layer 1: 基础依赖镜像

```bash
# 格式
l1-v{major}.{minor}.{patch}-{git_sha}

# 示例
l1-v1.0.0-a1b2c3d
l1-v1.0.0-08058ac

# 说明
# - layer: l1 (固定)
# - semver: 基础镜像版本号
# - git_sha: Git 提交 SHA (前 7 位)

# 包含内容
# - Ubuntu 22.04
# - Python 3.11.15 (源码编译)
# - Node.js 20.x
# - Poetry 2.3.2
# - Docker 24.0.9 (含 buildx 和 compose 插件)
```

#### Layer 2: CI/CD 依赖镜像

```bash
# 格式
l2-v{major}.{minor}.{patch}-{git_sha}

# 示例
l2-v1.0.0-a1b2c3d
l2-v1.0.0-08058ac

# 说明
# - layer: l2 (固定)
# - semver: 依赖镜像版本号
# - git_sha: Git 提交 SHA (前 7 位)
```

#### Layer 3: 应用镜像

```bash
# 格式
l3-v{major}.{minor}.{patch}-{git_sha}

# 示例
l3-v1.0.0-a1b2c3d
l3-v1.0.0-08058ac

# 说明
# - layer: l3 (固定)
# - semver: 应用版本号
# - git_sha: Git 提交 SHA (前 7 位)
```

## 环境标签策略

### 开发环境 (dev)

```bash
# 标签格式
dev-{branch_name}-{git_sha}

# 示例
dev-main-08058ac
dev-feature-user-login-a1b2c3d

# ArgoCD 策略
# - 更新策略：latest (按推送时间)
# - 允许标签：regexp:^dev-.*
# - 忽略标签：regexp:^dev-temp-.*
```

### 测试环境 (test)

```bash
# 标签格式
test-v{semver}-{git_sha}

# 示例
test-v1.0.0-08058ac
test-v1.0.1-a1b2c3d

# ArgoCD 策略
# - 更新策略：latest (按推送时间)
# - 允许标签：regexp:^test-.*
```

### 生产环境 (prod)

```bash
# 标签格式
v{semver}

# 示例
v1.0.0
v1.0.1

# ArgoCD 策略
# - 更新策略：semver
# - 允许标签：regexp:^v[0-9]+\.[0-9]+\.[0-9]+$
# - 忽略标签：regexp:.*-(test|rc|beta|alpha).*
```

## CI/CD 流程中的标签使用

### CI Pipeline

```yaml
# 使用 latest 标签引用最新稳定版本
env:
  IMAGE_TAG_L1: l1-latest
  IMAGE_TAG_L2: l2-latest
  IMAGE_TAG_L3_BASE: l3-latest

# 构建阶段
build-image:
  steps:
    # 1. 构建镜像 (带版本标签)
    - name: 构建并推送 Docker 镜像
      uses: docker/build-push-action@v5
      with:
        tags: ${{ vars.HARBOR_REGISTRY }}/sisys/app:${{ steps.meta.outputs.image_tag_l3 }}
        push: false  # 先不推送
    
    # 2. 标记 latest 标签
    - name: 标记 L3 latest 标签
      run: |
        docker tag ${{ vars.HARBOR_REGISTRY }}/sisys/app:${{ steps.meta.outputs.image_tag_l3 }} \
                   ${{ vars.HARBOR_REGISTRY }}/sisys/app:l3-latest
    
    # 3. 推送所有标签
    - name: 推送镜像到 Harbor
      run: |
        docker push ${{ vars.HARBOR_REGISTRY }}/sisys/app:${{ steps.meta.outputs.image_tag_l3 }}
        docker push ${{ vars.HARBOR_REGISTRY }}/sisys/app:l3-latest
```

### CD Pipeline

```yaml
# 使用 latest 标签引用最新稳定版本
env:
  IMAGE_TAG_L3_BASE: l3-latest

deploy-test:
  steps:
    # 使用 l3-latest 标签部署
    - name: 更新测试环境镜像版本
      run: |
        IMAGE_FULL_TAG="${{ env.HARBOR_REGISTRY }}/sisys/app:${{ env.IMAGE_TAG_L3_BASE }}"
        kubectl set image deployment/sisys-app app=${IMAGE_FULL_TAG} -n sisys-test
```

## Kustomize 配置

### Base 配置

```yaml
# deployments/apps/sisys/base/kustomization.yaml
images:
  - name: harbor.sisys.local/sisys/app
    newTag: l3-v1.0.0-placeholder  # 占位符，会被 overlay 覆盖
```

### Dev Overlay

```yaml
# deployments/apps/sisys/dev/kustomization.yaml
images:
  - name: harbor.sisys.local/sisys/app
    newTag: dev-main-initial-0000000
```

### Test Overlay

```yaml
# deployments/apps/sisys/test/kustomization.yaml
images:
  - name: harbor.sisys.local/sisys/app
    newTag: test-v1.0.0-0000000
```

### Prod Overlay

```yaml
# deployments/apps/sisys/prod/kustomization.yaml
images:
  - name: harbor.sisys.local/sisys/app
    newTag: v1.0.0
```

## ArgoCD Image Updater 配置

### 测试环境

```yaml
# deployments/argocd/applications/sisys-app-test.yaml
metadata:
  annotations:
    argocd-image-updater.argoproj.io/app.update-strategy: latest
    argocd-image-updater.argoproj.io/app.allow-tags: regexp:^test-.*
```

### 生产环境

```yaml
# deployments/argocd/applications/sisys-app-prod.yaml
metadata:
  annotations:
    argocd-image-updater.argoproj.io/app.update-strategy: semver
    argocd-image-updater.argoproj.io/app.allow-tags: regexp:^v[0-9]+\.[0-9]+\.[0-9]+$
    argocd-image-updater.argoproj.io/app.ignore-tags: regexp:.*-(test|rc|beta|alpha).*
```

## Makefile 命令

### 构建 Layer 1 镜像

```bash
# 构建基础依赖镜像
make docker-build-l1

# 推送基础依赖镜像
make docker-push-l1
```

### 构建 Layer 2 镜像

```bash
# 构建 CI/CD 依赖镜像
make docker-build-l2

# 推送 CI/CD 依赖镜像
make docker-push-l2
```

### 构建 Layer 3 镜像

```bash
# 构建应用镜像 (CI 自动触发)
make docker-build-l3

# 推送应用镜像
make docker-push-l3
```

## 标签清理策略

### Harbor 保留策略

```yaml
# 保留规则
- 生产标签 (v*): 永久保留
- 测试标签 (test-*): 保留最近 10 个
- 开发标签 (dev-*): 保留最近 5 个
- 临时标签 (l*-latest): 保留 7 天
```

### 本地清理

```bash
# 清理本地旧镜像
docker image prune -a --filter "until=168h"
```

## 版本发布流程

### 1. 更新版本号

```bash
# 在 pyproject.toml 中更新版本
version = "1.0.0"
```

### 2. 构建并推送镜像

```bash
# 构建 L2 镜像 (依赖变更时)
make docker-build-l2
make docker-push-l2

# CI 自动构建 L3 镜像
git push origin main
```

### 3. 更新 Kustomize 配置

```bash
# 更新生产环境配置
# deployments/apps/sisys/prod/kustomization.yaml
images:
  - name: harbor.sisys.local/sisys/app
    newTag: v1.0.0
```

### 4. 触发 ArgoCD 同步

```bash
# 触发同步
argocd app sync sisys-app-production
```

## 最佳实践

### ✅ 推荐做法

1. **使用固定标签** - 生产环境永远使用语义化版本标签
2. **标签不可变** - 已推送的标签不应被覆盖
3. **清晰命名** - 标签应清晰反映镜像用途和版本
4. **自动化** - CI/CD 自动处理标签生成和推送

### ❌ 避免做法

1. **滥用 latest** - 生产环境禁止使用 `latest` 标签
2. **标签覆盖** - 不要重复使用相同的标签名
3. **模糊命名** - 避免使用无意义的标签如 `test1`, `final`, `real`
4. **手动标签** - 尽量避免手动打标签，使用 CI/CD 自动化

## 故障排查

### 问题：镜像标签不一致

```bash
# 检查 Harbor 中的标签
curl -k -u "admin:password" \
  "https://harbor.sisys.local/api/v2.0/projects/sisys/repositories/app/artifacts"

# 检查 Kustomize 配置
cat deployments/apps/sisys/test/kustomization.yaml | grep newTag

# 检查 ArgoCD 应用状态
argocd app get sisys-app-test
```

### 问题：ArgoCD 未自动更新

```bash
# 检查 Image Updater 日志
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-image-updater

# 检查注解配置
kubectl get application sisys-app-test -n argocd -o yaml | grep annotations

# 手动触发同步
argocd app sync sisys-app-test
```

## 相关文档

- [CI/CD Pipeline 文档](../cicd/ci-cd-pipeline.md)
- [ArgoCD 配置指南](../deployment/argocd-config.md)
- [Harbor 镜像仓库管理](../deployment/harbor-config.md)
- [Kustomize 最佳实践](../deployment/kustomize-best-practices.md)
