# CI/CD 动态版本号配置方案

本文档介绍如何在 Git 提交或手动触发 CI 时，灵活指定 `IMAGE_TAG_L3_BASE` 版本号（如 `v1.1.0-base-frame`），使生成的镜像标签自动包含该版本号。

## 目录

- [方案概述](#方案概述)
- [实施步骤](#实施步骤)
- [使用指南](#使用指南)
- [完整流程对比](#完整流程对比)
- [验证检查清单](#验证检查清单)
- [进阶建议](#进阶建议)

---

## 方案概述

### 版本号优先级

```
手动输入 (workflow_dispatch) > Git Tag > VERSION 文件 > 默认值 (v1.0.0)
```

### 核心功能

- ✅ 支持 Git Tag 触发 CI，自动匹配版本号
- ✅ 支持手动触发时输入自定义版本号
- ✅ 支持从项目根目录 `VERSION` 文件读取版本号
- ✅ 普通提交使用默认版本号
- ✅ 自动清理版本号中的换行和空格
- ✅ 生成的镜像标签包含完整版本信息

### 三种获取方式

| 方式 | 适用场景 | 推荐度 |
|------|---------|--------|
| **方案 1: Git Tag** | 正式发布、里程碑 | ⭐⭐⭐⭐⭐ |
| **方案 2: 手动输入** | 临时测试、紧急修复 | ⭐⭐⭐⭐ |
| **方案 3: VERSION 文件** | 自动化流程、CI/CD 集成 | ⭐⭐⭐⭐ |

---

## 实施步骤

> 💡 **提示**: 您可以根据需求选择一种或多种组合方式。以下提供完整的三种方案配置。

### 步骤 1: 修改 `on:` 触发器

**文件**: `.gitea/workflows/ci.yaml`

**修改内容**:

```yaml
on:
  push:
    branches:
      - main
      - develop
      - 'feature/**'
    tags:
      - 'v*'  # ✅ 新增：支持 v 开头的 Tag 触发
  pull_request:
    branches:
      - main
      - develop

  # 手动触发
  workflow_dispatch:
    inputs:
      version:  # ✅ 新增：手动指定版本号
        description: '镜像版本号 (如 v1.1.0-base-frame)'
        required: false
        type: string
      force_rebuild:
        description: '强制重新构建'
        required: false
        default: 'false'
        type: boolean
```

---

### 步骤 2: 修改 `env:` 环境变量

**修改位置**: `env:` 区块中的 `IMAGE_TAG_L3_BASE`

```yaml
env:
  # ... 其他配置保持不变 ...

  # =======================================================================
  # Layer 3: 应用镜像版本号 - 动态获取
  # =======================================================================
  # 优先级：手动输入 > Git Tag > 默认值
  IMAGE_TAG_L3_BASE: |
    ${{
      github.event.inputs.version ||
      (startsWith(github.ref, 'refs/tags/') && github.ref_name) ||
      'v1.0.0'
    }}
```

> 💡 **注意**: 上面的语法会自动去除多余空白，确保版本号整洁。

---

### 步骤 3: 修改 `build-image` 任务中的标签生成

**修改位置**: `jobs.build-image.steps` 中的 "生成镜像标签"

```yaml
      - name: 生成镜像标签
        id: meta
        run: |
          GIT_SHA=$(echo "${{ github.sha }}" | cut -c1-7)
          TIMESTAMP=$(date +%Y%m%d%H%M%S)

          # ✅ 使用动态版本号（自动去除换行和空格）
          VERSION=$(echo "${{ env.IMAGE_TAG_L3_BASE }}" | tr -d '[:space:]')

          echo "git_sha=${GIT_SHA}" >> $GITHUB_OUTPUT
          echo "timestamp=${TIMESTAMP}" >> $GITHUB_OUTPUT
          echo "version=${VERSION}" >> $GITHUB_OUTPUT

          # Layer 3 应用镜像标签
          echo "image_tag_l3=${VERSION}-${GIT_SHA}" >> $GITHUB_OUTPUT

          # 测试环境标签
          echo "image_tag_test=test-${VERSION}-${GIT_SHA}" >> $GITHUB_OUTPUT

          echo "✅ 构建版本: ${VERSION}-${GIT_SHA}"
          echo "✅ 测试版本: test-${VERSION}-${GIT_SHA}"
```

---

## 方案 3: 从 VERSION 文件读取（可选）

> 💡 **适用场景**: 希望版本号由项目中的 `VERSION` 文件统一管理，适合自动化流程和 CI/CD 集成。

### 3.1 创建 VERSION 文件

**文件位置**: 项目根目录 `VERSION`

**文件内容**:
```
v1.1.0-base-frame
```

> 💡 **注意**: 文件应只包含一行版本号，不要有多余的空格或换行。

### 3.2 修改 `build-image` 任务

**修改位置**: `jobs.build-image.steps`

```yaml
      - name: 检出代码
        uses: actions/checkout@v4

      - name: 读取版本号
        id: version
        run: |
          # 优先级：VERSION 文件 > 环境变量默认值
          if [ -f VERSION ]; then
            VERSION=$(cat VERSION | tr -d '[:space:]')
            echo "version=${VERSION}" >> $GITHUB_OUTPUT
            echo "✅ 使用 VERSION 文件中的版本号: ${VERSION}"
          else
            VERSION="${{ env.IMAGE_TAG_L3_BASE }}"
            echo "version=${VERSION}" >> $GITHUB_OUTPUT
            echo "⚠️ VERSION 文件不存在，使用默认版本: ${VERSION}"
          fi

      - name: 生成镜像标签
        id: meta
        run: |
          GIT_SHA=$(echo "${{ github.sha }}" | cut -c1-7)
          TIMESTAMP=$(date +%Y%m%d%H%M%S)
          VERSION=${{ steps.version.outputs.version }}

          echo "git_sha=${GIT_SHA}" >> $GITHUB_OUTPUT
          echo "timestamp=${TIMESTAMP}" >> $GITHUB_OUTPUT
          echo "version=${VERSION}" >> $GITHUB_OUTPUT

          # Layer 3 应用镜像标签
          echo "image_tag_l3=${VERSION}-${GIT_SHA}" >> $GITHUB_OUTPUT

          # 测试环境标签
          echo "image_tag_test=test-${VERSION}-${GIT_SHA}" >> $GITHUB_OUTPUT

          echo "✅ 构建版本: ${VERSION}-${GIT_SHA}"
          echo "✅ 测试版本: test-${VERSION}-${GIT_SHA}"
```

### 3.3 使用 VERSION 文件的工作流程

```bash
# 1. 更新 VERSION 文件
echo "v1.1.0-base-frame" > VERSION

# 2. 提交并推送
git add VERSION
git commit -m "bump: version to v1.1.0-base-frame"
git push origin main

# 3. CI 自动读取 VERSION 文件中的版本号并构建
```

---

## 使用指南

### 场景 1: 正式发布（推荐）

使用 Git Tag 触发，版本号自动匹配 Tag 名称。

```bash
# 1. 创建 Tag
git tag -a v1.1.0-base-frame -m "feat: 发布基础框架版本 v1.1.0"

# 2. 推送 Tag 触发 CI
git push origin v1.1.0-base-frame
```

**生成结果**:
- 镜像标签: `harbor.sisys.local/sisys/app:v1.1.0-base-frame-3c8353a`
- 测试标签: `harbor.sisys.local/sisys/app:test-v1.1.0-base-frame-3c8353a`

---

### 场景 2: 临时测试构建

在 Gitea UI 中手动触发并指定任意版本号。

**操作步骤**:

1. 进入 Gitea 仓库 → **Actions** → **CI Pipeline**
2. 点击 **Run Workflow**
3. 在 "镜像版本号" 输入框填写: `v1.2.0-beta`
4. 点击运行

**生成结果**:
- 镜像标签: `harbor.sisys.local/sisys/app:v1.2.0-beta-xxxxxxx`

---

### 场景 3: 普通开发提交

普通 push 到分支，使用默认版本号 `v1.0.0`。

```bash
git commit -m "feat: some feature"
git push origin develop
```

**生成结果**:
- 镜像标签: `harbor.sisys.local/sisys/app:v1.0.0-xxxxxxx`

---

### 场景 4: 使用 VERSION 文件（自动化流程）

通过更新项目根目录的 `VERSION` 文件来管理版本号。

**操作步骤**:

```bash
# 1. 更新 VERSION 文件
echo "v1.1.0-base-frame" > VERSION

# 2. 提交并推送
git add VERSION
git commit -m "bump: version to v1.1.0-base-frame"
git push origin main
```

**生成结果**:
- CI 自动读取 `VERSION` 文件中的版本号
- 镜像标签: `harbor.sisys.local/sisys/app:v1.1.0-base-frame-xxxxxxx`
- 测试标签: `harbor.sisys.local/sisys/app:test-v1.1.0-base-frame-xxxxxxx`

**适用场景**:
- ✅ 自动化发布流程
- ✅ CI/CD 集成
- ✅ 需要与构建脚本集成
- ✅ 团队共享版本号管理

---

## 完整流程对比

| 触发方式 | 操作命令 / UI 操作 | 生成版本号 | 适用场景 |
|---------|-------------------|-----------|---------|
| **Git Tag** | `git push origin v1.1.0-frame` | `v1.1.0-frame` | 正式发布、里程碑 |
| **手动输入** | UI 输入 `v1.2.0-test` | `v1.2.0-test` | 临时测试、紧急修复 |
| **VERSION 文件** | 更新 `VERSION` 文件并推送 | `v1.1.0-base-frame` | 自动化流程、CI/CD |
| **普通 Push** | `git push origin main` | `v1.0.0` (默认) | 日常开发、CI 验证 |

---

## 镜像标签格式说明

### Layer 3 应用镜像标签

```
harbor.sisys.local/sisys/app:{VERSION}-{GIT_SHA}
```

**示例**:
- `v1.1.0-base-frame-3c8353a`
- `v1.0.0-abc1234`
- `v1.2.0-beta-def5678`

### 测试环境镜像标签

```
harbor.sisys.local/sisys/app:test-{VERSION}-{GIT_SHA}
```

**示例**:
- `test-v1.1.0-base-frame-3c8353a`
- `test-v1.0.0-abc1234`

### 开发环境镜像标签

```
harbor.sisys.local/sisys/app:dev-{VERSION}-{GIT_SHA}
```

**示例**:
- `dev-v1.1.0-base-frame-3c8353a`

---

## 验证检查清单

修改完成后，请验证以下内容：

### 通用验证项

- [ ] `ci.yaml` 中添加了 `tags: - 'v*'`
- [ ] `workflow_dispatch` 中添加了 `version` 输入项
- [ ] `IMAGE_TAG_L3_BASE` 使用了动态表达式
- [ ] `build-image` 步骤中使用了 `VERSION` 变量清理空格
- [ ] 推送一个测试 Tag（如 `v0.0.1-test`）并观察 CI 日志中的 "构建版本" 输出
- [ ] 手动触发一次 Workflow，输入自定义版本号，验证是否正确应用

### VERSION 文件方式额外验证项

- [ ] 项目根目录存在 `VERSION` 文件
- [ ] `VERSION` 文件内容仅为版本号，无多余空格或换行
- [ ] `build-image` 步骤中添加了读取 `VERSION` 文件的逻辑
- [ ] 更新 `VERSION` 文件后推送，CI 日志显示 "使用 VERSION 文件中的版本号"
- [ ] 删除 `VERSION` 文件后推送，CI 日志显示 "使用默认版本"

---

## 故障排除

### 问题 1: 版本号包含换行符

**症状**: 镜像标签类似 `v1.1.0\n-3c8353a`

**解决方案**: 确保 `VERSION` 变量使用了 `tr -d '[:space:]'` 清理：

```yaml
VERSION=$(echo "${{ env.IMAGE_TAG_L3_BASE }}" | tr -d '[:space:]')
```

### 问题 2: Git Tag 未触发 CI

**症状**: 推送 Tag 后 CI 没有运行

**检查清单**:
1. 确认 `ci.yaml` 中 `on.push.tags` 配置正确
2. 确认 Tag 格式为 `v*` 开头
3. 检查 Gitea Actions 日志是否有过滤条件

### 问题 3: 手动输入版本号不生效

**症状**: 手动触发时输入版本号，但生成的镜像仍是默认版本

**排查步骤**:
1. 检查 `workflow_dispatch.inputs.version` 是否正确配置
2. 确认 `IMAGE_TAG_L3_BASE` 表达式包含 `github.event.inputs.version`
3. 查看 CI 日志中 "构建版本" 输出

---

### 问题 4: VERSION 文件方式版本号不正确

**症状**: 使用 VERSION 文件时，生成的镜像版本号与预期不符

**排查步骤**:
1. 检查 `VERSION` 文件内容是否仅为版本号，无多余空格或换行
   ```bash
   cat -A VERSION  # 查看隐藏字符
   ```
2. 确认 `build-image` 步骤中使用了 `tr -d '[:space:]'` 清理版本号
3. 查看 CI 日志中是否显示 "使用 VERSION 文件中的版本号" 及具体版本号

**常见问题**:
```bash
# ❌ 错误：包含多余换行
v1.1.0-base-frame


# ✅ 正确：仅一行版本号
v1.1.0-base-frame
```

---

## 进阶建议

### 1. 语义化版本控制

建议遵循以下格式：

```
v{主版本}.{次版本}.{修订版本}-{描述}
```

**示例**:
- `v1.0.0` - 初始版本
- `v1.1.0-base-frame` - 基础框架更新
- `v1.1.1-hotfix` - 紧急修复
- `v2.0.0-major-refactor` - 重大重构

### 2. 与 Git Flow 结合

在 `release/*` 分支合并到 `main` 时打 Tag，确保生产镜像版本可控。

```bash
# 创建 release 分支
git checkout -b release/v1.1.0 main

# 测试完成后合并到 main
git checkout main
git merge release/v1.1.0

# 打 Tag 并发布
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin main --tags
```

### 3. 自动化发布脚本

可以编写一个 `scripts/release.sh` 脚本，一键完成更新 VERSION 文件、打 Tag、Push、通知 ArgoCD 的操作：

#### 方式 A: 使用 Git Tag（推荐）

```bash
#!/bin/bash
# scripts/release.sh - 自动化发布脚本（Git Tag 方式）

VERSION=$1

if [ -z "$VERSION" ]; then
  echo "用法: ./scripts/release.sh <version>"
  echo "示例: ./scripts/release.sh v1.1.0-base-frame"
  exit 1
fi

# 创建 Tag
git tag -a $VERSION -m "Release $VERSION"

# 推送 Tag 和代码
git push origin main --tags

echo "✅ 已推送 $VERSION，CI 将自动构建"
echo "🔍 查看进度: https://gitea.sisys.local/sisys/sisys/actions"
```

#### 方式 B: 使用 VERSION 文件

```bash
#!/bin/bash
# scripts/release.sh - 自动化发布脚本（VERSION 文件方式）

VERSION=$1

if [ -z "$VERSION" ]; then
  echo "用法: ./scripts/release.sh <version>"
  echo "示例: ./scripts/release.sh v1.1.0-base-frame"
  exit 1
fi

# 更新 VERSION 文件
echo "$VERSION" > VERSION

# 提交并推送
git add VERSION
git commit -m "bump: version to $VERSION"
git push origin main

echo "✅ 已更新 VERSION 文件为 $VERSION，CI 将自动构建"
echo "🔍 查看进度: https://gitea.sisys.local/sisys/sisys/actions"
```

**使用方法**:
```bash
# 赋予执行权限
chmod +x scripts/release.sh

# 发布新版本
./scripts/release.sh v1.1.0-base-frame
```

### 4. 与 ArgoCD Image Updater 集成

配合 Image Updater 使用，实现版本自动检测和部署：

```yaml
# ArgoCD Application 注解
annotations:
  argocd-image-updater.argoproj.io/image-list: app=harbor.sisys.local/sisys/app
  argocd-image-updater.argoproj.io/app.allow-tags: regexp:^v.*
  argocd-image-updater.argoproj.io/app.update-strategy: semver
```

---

## 相关文档

- [CI/CD Pipeline 模板](./CI_CD_PIPELINE_TEMPLATE.md)
- [ArgoCD Image Updater 配置](./ARGOCD_IMAGE_UPDATER.md)
- [镜像标签命名规范](../developer/image-tagging-strategy.md)
- [Harbor 镜像仓库指南](./HARBOR_IMAGE_PUSH_GUIDE.md)

---

**文档版本**: 1.0
**最后更新**: 2026-04-04
**维护者**: SISYS 团队
