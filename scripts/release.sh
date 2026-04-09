#!/bin/bash
# ============================================================================
# GitOps 发布脚本
# 用法: ./scripts/release.sh <version>
# 示例:
#   ./scripts/release.sh v1.1.0        # 发布到生产环境
#   ./scripts/release.sh v1.2.0-beta   # 发布 beta 版本
#
# 流程:
#   1. 安全检查（未提交更改、Tag 不存在）
#   2. 更新 VERSION 文件
#   3. 提交并推送到远程
#   4. 创建并推送 Git Tag（触发 CI 构建）
#   5. 提示 ArgoCD 审批链接
# ============================================================================
set -euo pipefail

VERSION="${1:-}"

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

# ============================================================================
# 验证版本号格式
# ============================================================================
if [[ ! "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
  log_error "版本号格式错误，应为 v{major}.{minor}.{patch}[-{suffix}]"
  log_error "示例: v1.1.0, v1.2.0-beta, v2.0.0-rc.1"
  exit 1
fi

# ============================================================================
# 安全检查
# ============================================================================
log_step "安全检查..."

if [[ -n "$(git status --porcelain)" ]]; then
  log_error "有未提交的更改，请先提交或暂存"
  git status --short
  exit 1
fi

if git rev-parse "$VERSION" >/dev/null 2>&1; then
  log_error "Tag $VERSION 已存在"
  log_info "查看已有 Tag: git show $VERSION"
  exit 1
fi

# ============================================================================
# 获取当前分支
# ============================================================================
CURRENT_BRANCH=$(git branch --show-current)
log_info "当前分支: $CURRENT_BRANCH"

# ============================================================================
# 执行发布
# ============================================================================
log_info "=========================================="
log_info "开始发布 $VERSION"
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
git tag -a "$VERSION" -m "Release $VERSION"
git push origin "$VERSION"

# ============================================================================
# 发布完成
# ============================================================================
log_info "=========================================="
log_info "✅ 发布完成！"
log_info "=========================================="
log_info ""
log_info "📊 查看 CI 进度: https://gitea.sisys.local/sisys/sisys/actions"
log_info "🏷️  镜像标签: harbor.sisys.local/sisys/app:$VERSION"
log_info ""
log_warn "⚠️  生产环境需要手动在 ArgoCD 中审批同步"
log_warn "🔗 ArgoCD Prod: https://argocd.sisys.local/applications/sisys-app-prod"
