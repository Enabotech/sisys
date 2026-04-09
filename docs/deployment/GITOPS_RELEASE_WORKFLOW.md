# GitOps 发布流程设计

> 本文档定义了基于 CI/CD + ArgoCD 的完整 GitOps 发布流程，涵盖标签策略、动态版本号、Feature 关联、环境晋级等核心设计决策。

## 目录

- [现状分析](#现状分析)
- [设计目标](#设计目标)
- [核心设计决策](#核心设计决策)
- [镜像标签策略](#镜像标签策略)
- [CI Pipeline 改造](#ci-pipeline-改造)
- [ArgoCD 配置修复](#argocd-配置修复)
- [Feature 信息关联](#feature-信息关联)
- [环境晋级流程](#环境晋级流程)
- [回滚策略](#回滚策略)
- [质量门禁](#质量门禁)
- [发布节奏](#发布节奏)
- [发布脚本](#发布脚本)
- [实施清单](#实施清单)
- [验证检查清单](#验证检查清单)

---

## 现状分析

### 当前 CI 配置

| 配置项 | 当前状态 | 问题 |
|--------|---------|------|
| 版本号 | 硬编码 `v1.0.0` | 无法区分不同发布版本 |
| Tag 触发 | 未配置 `tags: v*` | Git Tag 推送不会触发 CI |
| 手动输入 | 只有 `force_rebuild` | 无法手动指定版本号 |
| 标签格式 | `v1.0.0-{SHA}` | 包含 Git SHA，ArgoCD Prod 的 `semver` 策略无法识别 |

### 当前 ArgoCD 配置

| 环境 | 更新策略 | 标签过滤 | 问题 |
|------|---------|---------|------|
| Dev | `newest-build` | `regexp:^dev-.*` | ✅ 基本可用 |
| Test | `newest-build` | `regexp:^test-.*` | ⚠️ 同步策略被注释，实际为手动 |
| Prod | `semver` | `regexp:^v[0-9]+\.[0-9]+\.[0-9]+$` | ❌ 与 CI 标签格式冲突 |

### 核心冲突

```
CI 生成:     v1.0.0-3c8353a      ← 包含 Git SHA
ArgoCD 期望: v1.0.0               ← 纯 SemVer
结果:        生产环境无法自动发现新镜像
```

---

## 设计目标

1. **动态版本号** — 支持 Git Tag、手动输入、VERSION 文件三种方式指定版本号
2. **标签策略统一** — CI 生成的标签与 ArgoCD 各环境过滤策略完全匹配
3. **Feature 可追溯** — 每个镜像标签都能追溯到具体的 feature 分支、作者、构建时间
4. **环境晋级清晰** — Dev → Test → Prod 的发布路径明确，审批流程清晰
5. **一键发布** — 提供标准化发布脚本，减少人工操作失误

---

## 核心设计决策

### 决策 1: 单分支策略

**背景：** main 和 develop 是同一个分支。

**影响：**
- 不再区分 `dev-main` 和 `dev-develop` 标签
- develop/main 统一使用 `dev-{version}-{sha}` 格式
- 只有 feature 分支需要额外标识 feature 名称

### 决策 2: Digest + 多标签引用（不可变制品策略）

**核心思想：** 标签是**可变指针**，Digest 是**不可变事实源**。两者共存，兼顾可读性与安全性。

```
CI 构建同一镜像 → 推送多标签 + 记录 Digest
                      │
    ┌─────────────────┼──────────────────┐
    ▼                 ▼                  ▼
 dev-v1.1.0-xxx   test-v1.1.0-xxx    v1.1.0
       │              │                  │
       └──────────────┴──────────────────┘
                      │
                      └──→ sha256:8f2e3d... (不可变)
                              │
                              └── K8s 实际拉取的镜像
```

**CI 构建时同时推送：**
- 多标签：`dev-{version}-{sha}`、`test-{version}-{sha}`、`v{version}`（可读性）
- Digest：`sha256:xxx`（不可变性，K8s 实际拉取）

**Kustomize 配置格式（两字段共存）：**
```yaml
kustomize:
  images:
  - name: harbor.sisys.local/sisys/app
    newTag: v1.1.0                # ← 人看的（审批、追溯）
    newDigest: sha256:8f2e3d...   # ← K8s 实际拉的（不可变）
```

**Harbor 不可变标签策略：**
- 所有标签（`v*`、`dev-*`、`test-*`）一旦推送即不可覆盖
- 同名标签推送 → Harbor 直接拒绝
- `git_sha` + 不可变标签 = 等价于 Digest 的不可变性

### 决策 3: Feature 信息通过 OCI 注解 + K8s 注解双重记录

**不扩展标签名**（避免超过 128 字符限制），改为：
- Docker 构建时写入 OCI labels（Harbor 可查询）
- Kustomize 部署时写入 K8s annotations（集群内可查询）
- 应用暴露 `/version` 端点（运行时可查询）

---

## 镜像标签策略

### 标签格式规范

| 场景 | 标签格式 | 示例 | 触发条件 | ArgoCD 匹配 |
|------|---------|------|---------|------------|
| **feature 分支** | `dev-feature-{name}-{version}-{sha}` | `dev-feature-login-page-v1.1.0-3c8353a` | push to `feature/*` | `regexp:^dev-feature-.*` |
| **develop/main** | `dev-{version}-{sha}` | `dev-v1.1.0-3c8353a` | push to `develop`/`main` | `regexp:^dev-v[0-9]+.*` |
| **测试环境** | `test-{version}-{sha}` | `test-v1.1.0-3c8353a` | CI 自动构建 | `regexp:^test-.*` |
| **发布溯源** | `{version}-{sha}` | `v1.1.0-3c8353a` | push tag `v*` | 不匹配（仅追溯用） |
| **生产发布** | `v{major}.{minor}.{patch}` | `v1.1.0` | push tag `v*` | `regexp:^v[0-9]+\.[0-9]+\.[0-9]+$` |

### Digest 标签（所有场景）

| 维度 | 说明 | 示例 |
|------|------|------|
| **格式** | `sha256:{64 位 hex}` | `sha256:8f2e3d4a1b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1` |
| **来源** | Docker Buildx 构建输出 `steps.build-l3.outputs.digest` | 自动生成 |
| **用途** | K8s 实际拉取镜像（不可变）、审计追溯、供应链安全 | K8s 优先使用 Digest |
| **生命周期** | 永久不变（镜像内容的 SHA-256 哈希） | 即使标签被覆盖，Digest 仍指向原镜像 |

### 标签说明

| 标签类型 | 用途 | 生命周期 |
|---------|------|---------|
| `dev-*` | 开发环境自动部署 | 随 push 更新，`latest` 指向最新稳定版 |
| `test-*` | 测试环境验证 | QA 验证后可保留 |
| `v{semver}` | 生产发布 | 永久保留，不可变 |
| `{version}-{sha}` | 构建溯源 | 永久保留，关联 CI 构建记录 |

### 标签推送示例

**feature 分支推送：**
```bash
git push origin feature/login-page
# CI 生成: dev-feature-login-page-v1.1.0-3c8353a
# ArgoCD Dev 自动同步
```

**develop/main 分支推送：**
```bash
git push origin develop
# CI 生成: dev-v1.1.0-3c8353a
# ArgoCD Dev 自动同步
```

**生产发布（Git Tag）：**
```bash
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin v1.1.0
# CI 生成:
#   - v1.1.0-3c8353a      （溯源标签）
#   - v1.1.0              （纯 SemVer，ArgoCD Prod 识别）
#   - test-v1.1.0-3c8353a （测试标签）
```

---

## CI Pipeline 改造

### 1. 触发器扩展

**文件：** `.gitea/workflows/ci.yaml`

```yaml
on:
  push:
    branches:
      - main
      - develop
      - 'feature/**'
    tags:
      - 'v*'  # ✅ 新增：支持 Git Tag 触发
  pull_request:
    branches:
      - main
      - develop

  # 手动触发
  workflow_dispatch:
    inputs:
      version:  # ✅ 新增：手动指定版本号
        description: '镜像版本号 (如 v1.1.0)'
        required: false
        type: string
      force_rebuild:
        description: '强制重新构建'
        required: false
        default: 'false'
        type: boolean
```

### 2. 动态版本号

**修改 `env` 区块：**

```yaml
env:
  # Layer 3: 应用镜像版本号 - 动态获取
  # 优先级：手动输入 > Git Tag > VERSION 文件 > 默认值
  IMAGE_TAG_L3_BASE: |
    ${{
      github.event.inputs.version ||
      (startsWith(github.ref, 'refs/tags/') && github.ref_name) ||
      'v1.0.0'
    }}
```

**新增 VERSION 文件支持（可选）：**

```bash
# 项目根目录创建 VERSION 文件
echo "v1.1.0" > VERSION
```

### 3. 构建上下文提取

**新增步骤：**

```yaml
      - name: 提取构建上下文
        id: context
        run: |
          GIT_SHA=$(echo "${{ github.sha }}" | cut -c1-7)
          TIMESTAMP=$(date +%Y%m%d%H%M%S)

          # 提取分支名 / feature 信息
          if [[ "${{ github.ref }}" == refs/heads/feature/* ]]; then
            # feature/login-page → login-page
            FEATURE_NAME=$(echo "${{ github.ref }}" | sed 's|refs/heads/feature/||')
            IMAGE_PREFIX="dev-feature"
          elif [[ "${{ github.ref }}" == refs/heads/develop ]] || \
               [[ "${{ github.ref }}" == refs/heads/main ]]; then
            FEATURE_NAME="develop"
            IMAGE_PREFIX="dev"
          elif [[ "${{ github.ref }}" == refs/tags/v* ]]; then
            FEATURE_NAME="release"
            IMAGE_PREFIX=""
          else
            FEATURE_NAME="unknown"
            IMAGE_PREFIX="dev"
          fi

          # 提取提交作者
          AUTHOR=$(git log -1 --pretty=format:'%an')

          echo "git_sha=${GIT_SHA}" >> $GITHUB_OUTPUT
          echo "timestamp=${TIMESTAMP}" >> $GITHUB_OUTPUT
          echo "feature_name=${FEATURE_NAME}" >> $GITHUB_OUTPUT
          echo "author=${AUTHOR}" >> $GITHUB_OUTPUT
          echo "image_prefix=${IMAGE_PREFIX}" >> $GITHUB_OUTPUT
          echo "build_time=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> $GITHUB_OUTPUT
```

### 4. 标签生成逻辑

**修改 L3 构建步骤：**

```yaml
      - name: 构建 L3 镜像
        id: build-l3
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./docker/dockerfile.app
          push: true
          tags: |
            # === 稳定标签（latest 指向最新开发版）===
            ${{ vars.HARBOR_REGISTRY }}/${{ vars.HARBOR_PROJECT }}/app:latest

            # === 开发环境标签 ===
            ${{ vars.HARBOR_REGISTRY }}/${{ vars.HARBOR_PROJECT }}/app:${{ steps.context.outputs.image_prefix }}-${{ steps.context.outputs.feature_name }}-${{ env.IMAGE_TAG_L3_BASE }}-${{ steps.context.outputs.git_sha }}

            # === 测试环境标签 ===
            ${{ vars.HARBOR_REGISTRY }}/${{ vars.HARBOR_PROJECT }}/app:test-${{ env.IMAGE_TAG_L3_BASE }}-${{ steps.context.outputs.git_sha }}

            # === 发布标签（Git Tag 触发时生成）===
            # 溯源标签（带 SHA）
            ${{ vars.HARBOR_REGISTRY }}/${{ vars.HARBOR_PROJECT }}/app:${{ env.IMAGE_TAG_L3_BASE }}-${{ steps.context.outputs.git_sha }}
            # 纯 SemVer 标签（ArgoCD Prod 识别用）
            ${{ vars.HARBOR_REGISTRY }}/${{ vars.HARBOR_PROJECT }}/app:${{ env.IMAGE_TAG_L3_BASE }}
          labels: |
            org.opencontainers.image.source=${{ github.server_url }}/${{ github.repository }}
            org.opencontainers.image.revision=${{ github.sha }}
            org.opencontainers.image.created=${{ steps.context.outputs.timestamp }}
            sisys.image.layer="l3"
            sisys.image.type="application"
            # Feature 信息
            sisys.io/feature=${{ steps.context.outputs.feature_name }}
            sisys.io/author=${{ steps.context.outputs.author }}
            sisys.io/build-time=${{ steps.context.outputs.build_time }}
            sisys.io/branch=${{ github.ref_name }}
          cache-from: type=registry,ref=${{ vars.HARBOR_REGISTRY }}/sisys/buildcache:app-cache
          cache-to: type=registry,ref=${{ vars.HARBOR_REGISTRY }}/sisys/buildcache:app-cache,mode=min
          provenance: false
          platforms: linux/amd64
          build-args: |
            DEPENDENCY_IMAGE=${{ vars.HARBOR_REGISTRY }}/${{ vars.HARBOR_PROJECT }}/dependency:${{ env.IMAGE_TAG_L2_LATEST }}

      # 记录 Digest 信息（用于 Kustomize 写回 + 审计追溯）
      - name: 记录 Digest 信息
        run: |
          DIGEST="${{ steps.build-l3.outputs.digest }}"
          echo "构建 Digest: ${DIGEST}"

          # 写入构建元数据文件
          cat > build-metadata.json <<EOF
          {
            "version": "${{ env.IMAGE_TAG_L3_BASE }}",
            "git_sha": "${{ steps.context.outputs.git_sha }}",
            "digest": "${DIGEST}",
            "image": "${{ vars.HARBOR_REGISTRY }}/${{ vars.HARBOR_PROJECT }}/app",
            "tags": [
              "latest",
              "${{ steps.context.outputs.image_prefix }}-${{ steps.context.outputs.feature_name }}-${{ env.IMAGE_TAG_L3_BASE }}-${{ steps.context.outputs.git_sha }}",
              "test-${{ env.IMAGE_TAG_L3_BASE }}-${{ steps.context.outputs.git_sha }}",
              "${{ env.IMAGE_TAG_L3_BASE }}-${{ steps.context.outputs.git_sha }}",
              "${{ env.IMAGE_TAG_L3_BASE }}"
            ],
            "build_time": "${{ steps.context.outputs.build_time }}",
            "feature": "${{ steps.context.outputs.feature_name }}",
            "author": "${{ steps.context.outputs.author }}"
          }
          EOF

          # 上传为 artifact
          mkdir -p reports/build
          mv build-metadata.json reports/build/
          echo "✅ 元数据已保存到 reports/build/build-metadata.json"
```

---

## ArgoCD 配置修复

### 1. Test 环境同步策略

**问题：** `syncPolicy.automated` 被注释，实际为全手动。

**文件：** `deployments/argocd/applications/sisys-app-test.yaml`

**修复：**

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: false  # 测试环境不需要自我修复
    allowEmpty: true
```

### 2. 启用 Digest 不可变性（所有环境）

**为每个 Application 添加 `force-digest` 注解：**

```yaml
annotations:
  # 强制使用 Digest（确保不可变性）
  argocd-image-updater.argoproj.io/app.force-digest: "true"
```

**`.argocd-source-*.yaml` 格式变更（由 Image Updater 自动写回）：**

```yaml
# 当前格式（仅标签）
kustomize:
  images:
  - harbor.sisys.local/sisys/app:v1.0.2

# Digest 格式（Image Updater 自动写回 newTag + newDigest）
kustomize:
  images:
  - name: harbor.sisys.local/sisys/app
    newTag: v1.1.0                # 人看的（审批、追溯）
    newDigest: sha256:8f2e3d...   # K8s 实际拉的（不可变）
```

**各环境配置汇总：**

| 环境 | 文件 | `force-digest` | 预期 `.argocd-source-*.yaml` 格式 |
|------|------|---------------|----------------------------------|
| Dev | `sisys-app-dev.yaml` | `"true"` | `newTag: dev-v1.1.0-xxx` + `newDigest: sha256:xxx` |
| Test | `sisys-app-test.yaml` | `"true"` | `newTag: test-v1.1.0-xxx` + `newDigest: sha256:xxx` |
| Prod | `sisys-app-prod.yaml` | `"true"` | `newTag: v1.1.0` + `newDigest: sha256:xxx` |

### 3. Prod 环境标签过滤

**问题：** 正则表达式 `^v[0-9]+\.[0-9]+\.[0-9]+$` 无法匹配 CI 生成的 `v1.1.0-3c8353a`。

**方案 A：修改正则（推荐，向后兼容）**

**文件：** `deployments/argocd/applications/sisys-app-prod.yaml`

```yaml
# 修改前
argocd-image-updater.argoproj.io/app.allow-tags: regexp:^v[0-9]+\.[0-9]+\.[0-9]+$

# 修改后（兼容带 SHA 的标签）
argocd-image-updater.argoproj.io/app.allow-tags: regexp:^v[0-9]+\.[0-9]+\.[0-9]+(-[a-f0-9]{1,7})?$
```

**方案 B：CI 额外推送纯 SemVer 标签（已在上面实现）**

如果采用方案 B，则 Prod 正则保持不变，CI 会额外推送 `v1.1.0`（无 SHA）标签。

### 4. Dev 环境标签过滤

**修改以精确匹配 feature 标签：**

**文件：** `deployments/argocd/applications/sisys-app-dev.yaml`

```yaml
# 修改前
argocd-image-updater.argoproj.io/app.allow-tags: regexp:^dev-.*

# 修改后（区分 feature 和 develop/main）
argocd-image-updater.argoproj.io/app.allow-tags: regexp:^dev-(feature-)?v[0-9]+.*
```

### 5. Harbor 不可变标签策略（安全基石）

**问题：** 当前 Harbor 未启用不可变标签策略，同名标签可被覆盖。

**配置步骤（Harbor UI）：**

```
1. 登录 Harbor → 项目 "sisys"
2. 左侧菜单 → 策略 → 不可变标签
3. 添加规则:
   - 仓库匹配: **
   - 标签匹配: v*
   - 标签匹配: dev-*
   - 标签匹配: test-*
   - 标签匹配: latest
4. 保存
```

**效果：**

```bash
# 首次推送 → ✅ 成功
$ docker push harbor.sisys.local/sisys/app:v1.1.0

# 同名再次推送 → ❌ 拒绝
Error: tag 'v1.1.0' is immutable, cannot be overridden
```

**验证：**

```bash
# Harbor API 查询不可变规则
curl -s -u "$USER:$PASS" \
  "https://harbor.sisys.local/api/v2.0/projects/sisys/immutabletag/rules" \
  | jq '.[] | {id, tag_pattern, scope}'
```

---

## 各角色 TAG 全景图（Digest + 标签共存）

### 核心原则

```
标签 (newTag)    → 人看的（审批、追溯、可读性）
Digest (newDigest) → K8s 实际拉的（不可变、安全、审计）
```

### 各角色视角

| 角色/场景 | 主要看到的 | 补充信息 |
|-----------|-----------|---------|
| **CI 构建日志** | `dev-feature-xxx-v1.1.0-3c8353a` | `sha256:8f2e3d...` (输出 digest) |
| **Harbor UI** | 标签列表: `dev-xxx`, `test-xxx`, `v1.1.0` | 点击详情显示: Digest, Size, Labels |
| **kubectl get pods** | `sha256:8f2e3d...` (默认显示 Digest) | 需要 annotation 或自定义命令补回标签 |
| **ArgoCD UI** | `sha256:8f2e3d... (v1.1.0)` | 通常同时显示标签和 Digest |
| **Git 配置 (.argocd-source-*.yml)** | `newTag: v1.1.0` + `newDigest: sha256:xxx` | 审批人看 newTag，K8s 用 newDigest |
| **/version 端点** | `"image": "v1.1.0"` | `"digest": "sha256:8f.."`, `"git_sha": "3c8353a"` |
| **最终用户** | `v1.1.0` (应用层自行暴露) | 与镜像拉取方式无关 |

### kubectl 可读性增强

**自定义列输出（推荐添加到 ~/.bashrc）：**

```bash
function k8s-img() {
  local ns="${1:-default}"
  kubectl get pods -n "$ns" \
    -o custom-columns=\
'NAME:.metadata.name,\
IMAGE:.spec.containers[0].image,\
FEATURE:.metadata.annotations.sisys\.io/feature,\
BUILD_TIME:.metadata.annotations.sisys\.io/build-time'
}

# 使用效果
$ k8s-img sisys-dev

NAME                         IMAGE                           FEATURE                  BUILD_TIME
dev-sisys-app-6d8f9a7b5c-abc12   sha256:8f2e3d...   feature/login-page       2026-04-09T10:00:00Z
```

### 发布审批体验

**ArgoCD 审批人看到的（Prod）：**

```
Application: sisys-app-prod
Source: deployments/apps/sisys/prod

Pending Image Update:
  Current: harbor.sisys.local/sisys/app@sha256:1a2b3c... (v1.0.9)
  New:     harbor.sisys.local/sisys/app@sha256:8f2e3d... (v1.1.0)

Git Diff:
  deployments/apps/sisys/prod/.argocd-source-sisys-app-prod.yaml
  - newTag: v1.0.9
  + newTag: v1.1.0
  - newDigest: sha256:1a2b3c...
  + newDigest: sha256:8f2e3d...
```

**审批人确认项：**
- ✅ `newTag` 从 `v1.0.9` → `v1.1.0`（可读，一眼确认版本）
- ✅ `newDigest` 变了（不可变，保证是这个具体构建）
- ✅ CI 门禁全部通过
- ✅ QA 签字确认

---

## Feature 信息关联

### 架构设计

```
开发者 push feature/xxx
         │
         ▼
┌─────────────────────────────────┐
│ CI 提取分支名                     │
│ FEATURE_NAME=xxx                 │
│ AUTHOR=agimtech                  │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ Docker Build → 写入 OCI Labels           │
│ sisys.io/feature=feature/login-page     │
│ sisys.io/author=agimtech                │
│ sisys.io/build-time=2026-04-09T...      │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ Harbor 镜像元数据（可查询）               │
│ harbor.sisys.local/sisys/app:dev-...     │
│   → Annotations → feature/login-page     │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ Kustomize → K8s Annotations             │
│ deployment.annotations:                  │
│   sisys.io/feature=feature/login-page    │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ 应用 /version 端点（运行时可查询）         │
│ {"feature": "login-page", ...}           │
└─────────────────────────────────────────┘
```

### 查询方式

#### 方式 1：kubectl 查询

```bash
kubectl get deploy dev-sisys-app -n sisys-dev \
  -o custom-columns=\
'NAME:.metadata.name,\
IMAGE:.spec.template.spec.containers[0].image,\
FEATURE:.metadata.annotations.sisys\.io/feature,\
AUTHOR:.metadata.annotations.sisys\.io/author,\
BUILD_TIME:.metadata.annotations.sisys\.io/build-time'
```

**输出示例：**
```
NAME               IMAGE                                                          FEATURE                  AUTHOR      BUILD_TIME
dev-sisys-app      harbor.sisys.local/sisys/app:dev-feature-login-page-v1.1.0...   feature/login-page       agimtech    2026-04-09T10:00:00Z
```

#### 方式 2：应用内查询

**新增 `/version` 端点：**

```python
from fastapi import APIRouter
import os

router = APIRouter()

@router.get("/version")
def version():
    return {
        "image": os.getenv("IMAGE_TAG", "unknown"),
        "feature": os.getenv("SISYS_IO_FEATURE", "unknown"),
        "author": os.getenv("SISYS_IO_AUTHOR", "unknown"),
        "build_time": os.getenv("SISYS_IO_BUILD_TIME", "unknown"),
        "git_sha": os.getenv("GIT_SHA", "unknown"),
    }
```

**访问：**
```bash
curl http://dev-sisys-app.sisys-dev/version
```

**响应：**
```json
{
  "image": "dev-feature-login-page-v1.1.0-3c8353a",
  "feature": "feature/login-page",
  "author": "agimtech",
  "build_time": "2026-04-09T10:00:00Z",
  "git_sha": "3c8353a"
}
```

#### 方式 3：Harbor API 查询

```bash
# 查询指定镜像的 feature 信息
curl -s -u "$HARBOR_USER:$HARBOR_PASSWORD" \
  "https://harbor.sisys.local/api/v2.0/projects/sisys/repositories/app/artifacts" \
  | jq '.[] | select(.tags[].name | startswith("dev-feature")) | {
      name: .tags[].name,
      feature: .extra_attrs.sisys_io_feature,
      author: .extra_attrs.sisys_io_author
    }'
```

---

## 环境晋级流程

### 流程图

```
┌──────────────────────────────────────────────────────────────────┐
│                        镜像晋级路径                               │
│                                                                  │
│  开发者 push feature/xxx                                          │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────────┐                                         │
│  │ CI 构建              │                                         │
│  │ dev-feature-xxx-... │                                         │
│  └────────┬────────────┘                                         │
│           │ 自动部署                                              │
│           ▼                                                       │
│  ┌─────────────────────┐      验证通过      ┌──────────────┐      │
│  │ ArgoCD Dev          │ ────────────────→  │ merge to      │      │
│  │ 自动同步             │                   │ develop/main  │      │
│  └─────────────────────┘                   └──────┬───────┘      │
│                                                   │               │
│                                                   ▼               │
│                                          ┌─────────────────┐     │
│                                          │ CI 构建          │     │
│                                          │ dev-v{ver}-...   │     │
│                                          │ test-v{ver}-...  │     │
│                                          └────────┬────────┘     │
│                                                   │ 手动同步      │
│                                                   ▼               │
│                                          ┌─────────────────┐     │
│                                          │ ArgoCD Test     │     │
│                                          │ QA 验证          │     │
│                                          └────────┬────────┘     │
│                                                   │ 验证通过      │
│                                                   ▼               │
│                                          ┌─────────────────┐     │
│                                          │ git tag v{x.y.z} │     │
│                                          └────────┬────────┘     │
│                                                   │ CI 构建       │
│                                                   ▼               │
│                                          ┌─────────────────┐     │
│                                          │ ArgoCD Prod     │     │
│                                          │ 手动审批 → 同步   │     │
│                                          └─────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

### 晋级规则

| 阶段 | 触发条件 | 镜像标签 | 验证要求 | 审批 |
|------|---------|---------|---------|------|
| **Dev** | push to `feature/*` 或 `develop` | `dev-feature-{name}-{ver}-{sha}` / `dev-{ver}-{sha}` | CI 测试通过 | 自动 |
| **Test** | merge to `develop`/`main` | `test-{ver}-{sha}` | 集成测试通过 | 手动同步 |
| **Prod** | push tag `v{x.y.z}` | `v{x.y.z}` | QA 签字确认 | ArgoCD 手动审批 |

### 环境职责

| 环境 | 用途 | 同步方式 | 副本数 | 数据 |
|------|------|---------|--------|------|
| **Dev** | 开发自测、Feature 验证 | 全自动 | 1-2 | Mock / 测试数据 |
| **Test** | QA 集成测试、回归测试 | 手动同步 | 2-3 | 类生产数据（脱敏） |
| **Prod** | 线上服务 | 手动审批 | 3-10 | 真实数据 |

---

## 回滚策略

> 🔴 **生产安全的底线** — 没有回滚策略的发布流程就是裸奔。

### 回滚场景与响应

| 场景 | 严重等级 | 响应时间 | 回滚方式 | 负责人 |
|------|---------|---------|---------|--------|
| 应用 CrashLoopBackOff | P0 | 5 分钟 | ArgoCD 一键回滚 | On-call |
| 核心接口 5xx 率 > 5% | P0 | 10 分钟 | ArgoCD 回滚 + 流量切换 | On-call |
| 数据不一致 | P1 | 30 分钟 | 数据回滚 + 应用回滚 | 开发 + DBA |
| 安全漏洞 (CVE Critical) | P1 | 2 小时 | 构建热修复版本 → 发布 | 安全团队 |
| 功能异常（非核心） | P2 | 4 小时 | 下个 Sprint 修复 | 开发团队 |

### 回滚方式详解

#### 方式 1：ArgoCD 一键回滚（应用层异常）

**适用场景：** 新镜像部署后应用启动失败、接口报错、功能异常。

**原理：** ArgoCD 保留历史 Revision 记录，可直接回退到上一个健康版本。

**操作步骤：**

```bash
# 1. 查看发布历史
argocd app history sisys-app-prod

# 输出示例：
# ID  REV                           DEPLOYED
# 12  HEAD:abc1234                  2026-04-08 10:00:00 (v1.0.9)
# 13  HEAD:3c8353a                  2026-04-09 14:30:00 (v1.1.0) ← 当前版本（异常）

# 2. 回滚到上一个版本
argocd app set sisys-app-prod --revision HEAD:abc1234
argocd app sync sisys-app-prod

# 3. 确认回滚成功
argocd app get sisys-app-prod
kubectl get pods -n sisys-prod
```

**ArgoCD UI 操作：**
1. 进入 `https://argocd.sisys.local/applications/sisys-app-prod`
2. 点击 **App Details** → **History**
3. 选择上一个健康版本，点击 **Rollback**
4. 确认同步

**回滚脚本（推荐添加到 `scripts/rollback.sh`）：**

```bash
#!/bin/bash
# ============================================================================
# 生产环境一键回滚脚本
# 用法: ./scripts/rollback.sh [target-revision]
# 示例:
#   ./scripts/rollback.sh              # 自动回滚到上一个版本
#   ./scripts/rollback.sh HEAD:abc1234 # 回滚到指定版本
# ============================================================================
set -euo pipefail

APP_NAME="sisys-app-prod"
NAMESPACE="sisys-prod"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 获取发布历史
log_info "获取 $APP_NAME 发布历史..."
argocd app history "$APP_NAME" --output wide

TARGET_REVISION="${1:-}"

if [[ -z "$TARGET_REVISION" ]]; then
  # 自动选择上一个版本
  TARGET_REVISION=$(argocd app history "$APP_NAME" --output json \
    | jq -r '.[-2].revision')

  if [[ -z "$TARGET_REVISION" ]]; then
    log_error "无法获取上一个版本，请手动指定 revision"
    exit 1
  fi

  log_warn "自动选择上一个版本: $TARGET_REVISION"
fi

# 确认回滚
log_warn "=========================================="
log_warn "即将回滚 $APP_NAME 到 $TARGET_REVISION"
log_warn "=========================================="
read -p "确认执行回滚？(y/N): " confirm
if [[ "$confirm" != "y" ]]; then
  log_info "取消回滚"
  exit 0
fi

# 执行回滚
log_info "设置 revision..."
argocd app set "$APP_NAME" --revision "$TARGET_REVISION"

log_info "同步应用..."
argocd app sync "$APP_NAME"

# 等待完成
log_info "等待回滚完成..."
sleep 10

# 验证
log_info "检查 Pod 状态..."
kubectl get pods -n "$NAMESPACE"

log_info "=========================================="
log_info "✅ 回滚完成！"
log_info "=========================================="
log_info ""
log_info "📊 请验证："
log_info "  1. 应用是否正常响应"
log_info "  2. 监控指标是否恢复正常"
log_info "  3. 日志是否有异常"
log_info ""
log_info "🔗 ArgoCD: https://argocd.sisys.local/applications/$APP_NAME"
```

#### 方式 2：镜像回滚（Harbor 标签回退）

**适用场景：** 镜像本身有问题（如依赖漏洞、构建错误），需要重新部署旧版本镜像。

**操作步骤：**

```bash
# 1. 查询上一个稳定版本的镜像标签
# 在 Harbor 中查找 v1.0.9 或 v1.0.9-xxxxxxx

# 2. 手动更新 Kustomize 配置
cat > deployments/apps/sisys/prod/.argocd-source-sisys-app-prod.yaml <<EOF
kustomize:
  images:
  - harbor.sisys.local/sisys/app:v1.0.9
EOF

# 3. 提交并推送
git add deployments/apps/sisys/prod/.argocd-source-sisys-app-prod.yaml
git commit -m "revert: rollback prod to v1.0.9"
git push origin main

# 4. ArgoCD 自动检测到 Git 变更并同步
```

#### 方式 3：数据库回滚（数据异常）

**适用场景：** 新版本执行了不兼容的数据库迁移（migration），导致数据异常。

**前置条件：**
- 所有数据库迁移必须有对应的 `down` 脚本
- 迁移前自动备份相关表

**操作步骤：**

```bash
# 1. 停止应用（防止写入）
kubectl scale deployment prod-sisys-app -n sisys-prod --replicas=0

# 2. 执行数据库回滚
# （根据具体 ORM/迁移工具调整）
poetry run alembic downgrade -1  # Alembic 回滚一步
# 或
poetry run flyway undo             # Flyway 回滚

# 3. 部署旧版本镜像
# （参考方式 2）

# 4. 恢复应用副本
kubectl scale deployment prod-sisys-app -n sisys-prod --replicas=3

# 5. 验证数据一致性
```

### 回滚决策树

```
部署后发现异常
     │
     ├─ 应用无法启动 / CrashLoop?
     │     │
     │     └──→ ArgoCD 一键回滚（方式 1）
     │           │
     │           └──→ 失败？ → 镜像回滚（方式 2）
     │
     ├─ 接口 5xx 率升高？
     │     │
     │     └──→ 检查日志 → 代码 bug？
     │               │
     │               ├──→ 是 → ArgoCD 回滚（方式 1）
     │               └──→ 否 → 检查依赖（DB/Redis/外部 API）
     │
     └─ 数据不一致？
           │
           └──→ 停止写入 → 数据库回滚（方式 3）
                         → 镜像回滚（方式 2）
```

### 回滚演练

**要求：** 每季度至少一次回滚演练，确保：
- 回滚脚本可用
- 团队熟悉回滚流程
- 回滚时间 < 15 分钟

**演练检查清单：**
- [ ] ArgoCD 历史记录可查
- [ ] 一键回滚成功
- [ ] 回滚后应用健康检查通过
- [ ] 监控指标恢复正常
- [ ] 回滚过程有日志记录

---

## 质量门禁

> 🔴 **定量门禁** — 不达标则阻断发布，不是"尽量"而是"必须"。

### CI 质量门禁

| 门禁项 | 阈值 | 工具 | 阻断级别 |
|--------|------|------|---------|
| **Linting** | 0 Error | Ruff | 🔴 阻断 |
| **Format** | 通过 | Ruff Format | 🔴 阻断 |
| **类型检查** | 0 Error | MyPy | 🔴 阻断 |
| **单元测试覆盖率** | ≥ 80% | pytest-cov | 🔴 阻断 |
| **集成测试通过率** | 100% | pytest | 🔴 阻断 |
| **安全漏洞（Critical）** | 0 | Bandit + Trivy | 🔴 阻断 |
| **安全漏洞（High）** | ≤ 3 | Bandit + Trivy | 🟡 告警 |
| **依赖漏洞（Critical）** | 0 | pip-audit / safety | 🔴 阻断 |
| **构建成功率** | 100% | Docker Buildx | 🔴 阻断 |

### 当前 CI 门禁状态

| 门禁项 | 当前配置 | 达标？ | 问题 |
|--------|---------|--------|------|
| Ruff Linting | ✅ 执行，`|| true` | ❌ **未阻断** | 需要移除 `|| true` |
| MyPy | ✅ 执行，`|| true` | ❌ **未阻断** | 需要移除 `|| true` |
| 单元测试覆盖率 | ≥ 80% | ✅ 已阻断 | `coverage report --fail-under=80` |
| Bandit | ✅ 执行，`|| true` | ❌ **未阻断** | 需要改为阻断 Critical |
| Trivy | ✅ 执行， severity CRITICAL+HIGH | ⚠️ 未阻断 | 需要加 `exit-code: 1` |
| pip-audit | ✅ 执行，检测 Critical 时 exit 1 | ✅ 已阻断 | — |

### 门禁修复方案

#### 修复 1：移除 Ruff/MyPy/Bandit 的 `|| true`

**文件：** `.gitea/workflows/ci.yaml`

```yaml
# 修改前（不阻断）
- name: 代码检查 ( Ruff )
  run: |
    poetry run ruff check . --output-format=github > reports/linting/ruff-check.txt || true

# 修改后（阻断）
- name: 代码检查 ( Ruff )
  run: |
    mkdir -p reports/linting
    poetry run ruff check . --output-format=github
    poetry run ruff format --check .
```

#### 修复 2：Trivy 文件系统扫描改为阻断

```yaml
# 修改前（不阻断）
- name: 文件系统扫描 ( Trivy )
  with:
    scan-type: 'fs'
    severity: 'CRITICAL,HIGH'
    # 缺少 exit-code

# 修改后（阻断 Critical）
- name: 文件系统扫描 ( Trivy )
  uses: aquasecurity/trivy-action@v0.35.0
  with:
    scan-type: 'fs'
    scan-ref: '.'
    format: 'sarif'
    output: 'reports/security/trivy-fs.sarif'
    severity: 'CRITICAL'
    exit-code: '1'  # ✅ 发现 Critical 级别漏洞时阻断
```

#### 修复 3：Bandit 改为阻断 Critical

```yaml
# 修改前
- name: 代码安全扫描 ( Bandit )
  run: |
    poetry run bandit -r src/ -f json -o reports/security/bandit-report.json || true

# 修改后
- name: 代码安全扫描 ( Bandit )
  run: |
    mkdir -p reports/security
    # 仅阻断 High 及以上
    poetry run bandit -r src/ -f json -o reports/security/bandit-report.json \
      --severity-level high
```

### 发布预检清单（Release Readiness Checklist）

> 🟡 **在发布前必须逐项确认**，建议作为 PR 模板或发布脚本的自动检查项。

#### 代码质量

- [ ] 所有 CI 门禁通过（Lint、类型、测试、安全）
- [ ] 无未解决的 Critical/High 级别 Code Review 评论
- [ ] 分支已与 `develop`/`main` 同步，无冲突

#### 测试验证

- [ ] 单元测试覆盖率 ≥ 80%（新增代码不低于 70%）
- [ ] 集成测试全部 通过
- [ ] Dev 环境验证通过（功能、接口、UI）
- [ ] Test 环境 QA 签字确认

#### 安全合规

- [ ] 无 Critical 级别依赖漏洞（pip-audit 通过）
- [ ] 无 Critical 级别代码漏洞（Bandit + Trivy 通过）
- [ ] 数据库迁移有 `down` 脚本，已验证可回滚
- [ ] 敏感配置已通过 Secret 管理，未硬编码

#### 运维就绪

- [ ] 监控告警规则已配置/更新
- [ ] 日志级别正确（生产环境 `warn`）
- [ ] HPA 配置正确，副本数满足预期流量
- [ ] 回滚方案已确认，团队知晓

#### 发布协调

- [ ] 发布窗口已通知相关团队（避免冲突）
- [ ] 发布记录已填写（变更内容、影响范围、风险点）
- [ ] On-call 人员已安排

---

## 发布节奏

> 🟢 **与 Sprint 节奏对齐**，避免"随时发布"导致的质量失控。

### 建议发布窗口

| 环境 | 发布频率 | 推荐窗口 | 审批 |
|------|---------|---------|------|
| **Dev** | 随时 | push 即发 | 自动 |
| **Test** | 每周 2-3 次 | 周二、四 上午 | QA 手动同步 |
| **Prod** | 每 Sprint 1 次 | Sprint 最后一天 14:00-16:00 | 双人审批 |

### 紧急发布（Hotfix）

| 条件 | 流程 | 审批 |
|------|------|------|
| P0 故障（线上 Crash、安全漏洞） | 从 `main` 创建 `hotfix/xxx` → 修复 → 合并 → Tag 发布 | 1 人审批 + 事后复盘 |

### 发布冻结期

| 时间段 | 策略 | 原因 |
|--------|------|------|
| 周五 18:00 后 | 🚫 禁止 Prod 发布 | 避免周末 On-call |
| 节假日前 1 天 | 🚫 禁止 Prod 发布 | 人员不齐 |
| 大促/活动期间 | 🚫 禁止 Prod 发布 | 稳定性优先 |

---

## 发布脚本

### `scripts/release.sh`

```bash
#!/bin/bash
# ============================================================================
# GitOps 发布脚本
# 用法: ./scripts/release.sh <version> [environment]
# 示例:
#   ./scripts/release.sh v1.1.0        # 发布到生产环境
#   ./scripts/release.sh v1.2.0-beta   # 发布 beta 版本
# ============================================================================
set -euo pipefail

VERSION="${1:-}"
ENVIRONMENT="${2:-prod}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${BLUE}[STEP]${NC} $1"; }

# 验证参数
if [[ ! "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
  log_error "版本号格式错误，应为 v{major}.{minor}.{patch}[-{suffix}]，如 v1.1.0 或 v1.2.0-beta"
  exit 1
fi

# 安全检查
if [[ -n "$(git status --porcelain)" ]]; then
  log_error "有未提交的更改，请先提交或暂存"
  git status --short
  exit 1
fi

if git rev-parse "$VERSION" >/dev/null 2>&1; then
  log_error "Tag $VERSION 已存在"
  exit 1
fi

# 获取当前分支
CURRENT_BRANCH=$(git branch --show-current)
log_info "当前分支: $CURRENT_BRANCH"

# 执行发布
log_info "=========================================="
log_info "开始发布 $VERSION 到 $ENVIRONMENT 环境"
log_info "=========================================="

# Step 1: 更新 VERSION 文件
log_step "更新 VERSION 文件..."
echo "$VERSION" > VERSION
git add VERSION
git commit -m "chore(release): bump version to $VERSION"

# Step 2: 推送到远程
log_step "推送到远程仓库..."
git push origin "$CURRENT_BRANCH"

# Step 3: 创建并推送 Tag
log_step "创建 Tag: $VERSION..."
git tag -a "$VERSION" -m "Release $VERSION to $ENVIRONMENT"
git push origin "$VERSION"

log_info "=========================================="
log_info "✅ 发布完成！"
log_info "=========================================="
log_info ""
log_info "📊 查看 CI 进度: https://gitea.sisys.local/sisys/sisys/actions"
log_info "🏷️  镜像标签: harbor.sisys.local/sisys/app:$VERSION"

if [[ "$ENVIRONMENT" == "prod" ]]; then
  log_warn ""
  log_warn "⚠️  生产环境需要手动在 ArgoCD 中审批同步"
  log_warn "🔗 ArgoCD Prod: https://argocd.sisys.local/applications/sisys-app-prod"
fi
```

**使用方法：**
```bash
# 赋予执行权限
chmod +x scripts/release.sh

# 发布到生产
./scripts/release.sh v1.1.0

# 发布 beta 版本
./scripts/release.sh v1.2.0-beta
```

---

## 实施清单

### 改动总览

| 优先级 | 文件 | 改动类型 | 说明 |
|--------|------|---------|------|
| **P0** | `.gitea/workflows/ci.yaml` | 修改 | 动态版本号 + 构建上下文提取 + 标签逻辑 |
| **P0** | `deployments/argocd/applications/sisys-app-prod.yaml` | 修改 | 标签过滤正则（可选，如果 CI 推送纯 SemVer 则不需要） |
| **P0** | `deployments/argocd/applications/sisys-app-test.yaml` | 修改 | 恢复 `syncPolicy.automated` |
| **P0** | `deployments/argocd/applications/sisys-app-dev.yaml` | 修改 | 标签过滤正则精确匹配 |
| **P1** | `scripts/release.sh` | 新建 | 一键发布脚本 |
| **P1** | `VERSION` | 新建 | 版本号文件 |
| **P2** | `src/api/version.py` | 新建 | 应用 `/version` 端点 |
| **P2** | `deployments/apps/sisys/base/deployment.yaml` | 修改 | 注入 OCI 注解为环境变量 |

### 详细改动

#### P0: CI Pipeline 改造

- [ ] 添加 `tags: v*` 触发器
- [ ] 添加 `workflow_dispatch.inputs.version`
- [ ] 修改 `IMAGE_TAG_L3_BASE` 为动态表达式
- [ ] 新增 "提取构建上下文" 步骤
- [ ] 修改 L3 构建标签逻辑（含 OCI labels）
- [ ] 移除 Ruff/MyPy/Bandit 的 `|| true`
- [ ] Trivy 添加 `exit-code: 1` 阻断 Critical

#### P0: ArgoCD 配置修复

- [ ] 修复 Test 环境 `syncPolicy.automated`
- [ ] 为 Dev/Test/Prod 添加 `force-digest: "true"` 注解
- [ ] 清空现有 `.argocd-source-*.yaml`（让 Image Updater 重建为 Digest 格式）
- [ ] （可选）修改 Prod 标签过滤正则
- [ ] 修改 Dev 标签过滤正则
- [ ] Harbor 启用不可变标签策略（v*, dev-*, test-*, latest）

#### P0: 回滚与门禁（新增）

- [ ] 创建 `scripts/rollback.sh` 一键回滚脚本
- [ ] 验证 ArgoCD Revision 回滚功能
- [ ] CI 门禁全部改为阻断模式
- [ ] 发布预检清单集成到 PR 模板

#### P1: 发布脚本

- [ ] 创建 `scripts/release.sh`
- [ ] 创建 `VERSION` 文件（初始值 `v1.0.0`）
- [ ] 测试脚本各种场景（正常发布、Tag 已存在、未提交更改）

#### P2: Feature 信息注入

- [ ] 修改 Kustomize 配置注入 K8s 注解
- [ ] 修改 Deployment 注入环境变量
- [ ] 创建 `/version` 端点（如应用尚未提供）

---

## 验证检查清单

### CI 验证

- [ ] push 到 feature 分支，确认生成 `dev-feature-{name}-...` 标签
- [ ] push 到 develop/main，确认生成 `dev-{version}-...` 标签
- [ ] push tag `v1.1.0`，确认生成 `v1.1.0` 和 `v1.1.0-{sha}` 两个标签
- [ ] 手动触发 Workflow 并输入版本号，确认标签正确
- [ ] 检查 Harbor 中 OCI labels 是否正确（feature、author、build_time）
- [ ] 确认 CI 构建日志中输出了 `sha256:xxx` Digest
- [ ] 确认 `reports/build/build-metadata.json` 包含 version、digest、tags 字段

### ArgoCD 验证

- [ ] Dev 环境自动同步 feature 分支镜像
- [ ] Dev 环境自动同步 develop/main 镜像
- [ ] Test 环境手动同步生效
- [ ] Prod 环境手动审批生效
- [ ] kubectl 查询 K8s annotations 中 feature 信息正确
- [ ] 确认 `.argocd-source-*.yaml` 格式为 `newTag` + `newDigest` 双字段
- [ ] 确认 `kubectl get pods` 显示的是 `@sha256:xxx` 而非标签名
- [ ] ArgoCD UI 中同时显示标签和 Digest

### Harbor 验证

- [ ] 不可变标签策略已启用（v*, dev-*, test-*, latest）
- [ ] 尝试推送同名标签被拒绝（验证不可变性）
- [ ] Harbor UI 中标签详情页显示正确的 Digest 和 OCI labels

### 发布脚本验证

- [ ] 正常发布流程成功（更新 VERSION → push → 创建 Tag → 推送）
- [ ] Tag 已存在时报错退出
- [ ] 有未提交更改时报错退出
- [ ] 版本号格式错误时报错退出

---

## 相关文档

- [CI/CD 动态版本号配置方案](./CI_CD_DYNAMIC_VERSIONING.md) — 本文档的前身，部分设计已被本方案替代
- [ArgoCD Image Updater 配置](./ARGOCD_IMAGE_UPDATER.md)
- [CI/CD Pipeline 模板](./CI_CD_PIPELINE_TEMPLATE.md)
- [Harbor 镜像仓库指南](./HARBOR_IMAGE_PUSH_GUIDE.md)

---

**文档版本**: 1.2
**最后更新**: 2026-04-09
**维护者**: SISYS 团队
**状态**: ✅ 待审批
**变更日志**:
- v1.2: 引入 Digest + 多标签引用策略（不可变制品）；新增 Harbor 不可变标签策略；新增各角色 TAG 全景图；更新 CI 构建输出 Digest 元数据；更新 ArgoCD 配置（force-digest + newTag/newDigest 双字段）；更新验证清单
- v1.1: 新增回滚策略、质量门禁、发布节奏章节（评审改进）
- v1.0: 初始版本（标签策略、动态版本号、Feature 关联、环境晋级）
