#!/bin/bash
# ============================================================================
# GitOps 发布入口脚本
# 职责: 验证格式 + 触发 Gitea Release Workflow
# 用法: ./scripts/release.sh <version> [--dry-run]
# 示例:
#   ./scripts/release.sh v1.1.0           # 发布到生产环境
#   ./scripts/release.sh v1.2.0-beta      # 发布 beta 版本
#   ./scripts/release.sh v1.1.0 --dry-run # 干运行（仅验证）
#
# 流程:
#   1. 验证版本号格式（本地）
#   2. 检查 Tag 是否已存在（本地）
#   3. 调用 Gitea API 触发 Release Workflow
#   4. Release Workflow 负责: VERSION 更新 → commit → tag → push
#   5. Tag push 自动触发 CI Pipeline 构建镜像
# ============================================================================
set -euo pipefail

VERSION="${1:-}"
DRY_RUN=false

if [[ "${2:-}" == "--dry-run" ]]; then
  DRY_RUN=true
fi

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
# 验证
# ============================================================================
if [[ ! "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
  log_error "版本号格式错误，应为 v{major}.{minor}.{patch}[-{suffix}]"
  log_error "示例: v1.1.0, v1.2.0-beta, v2.0.0-rc.1"
  exit 1
fi

if git rev-parse "$VERSION" >/dev/null 2>&1; then
  log_error "Tag $VERSION 已存在"
  exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" != "main" ]]; then
  log_error "必须在 main 分支发布，当前分支: $CURRENT_BRANCH"
  exit 1
fi

# ============================================================================
# 方式 1: 直接通过 Gitea UI 触发（默认，推荐）
# ============================================================================
use_ui() {
  log_info "=========================================="
  log_info "发布 $VERSION"
  log_info "=========================================="
  log_info ""
  log_info "请在 Gitea 中手动触发 Release Workflow:"
  log_info "  1. 打开: https://gitea.sisys.local/sisys/sisys/actions"
  log_info "  2. 点击 'Release' 工作流"
  log_info "  3. 点击 'Run Workflow'"
  log_info "  4. 输入版本号: $VERSION"
  if [[ "$DRY_RUN" == "true" ]]; then
    log_info "  5. 勾选 '干运行'"
  fi
  log_info "  6. 点击运行"
  log_info ""
  log_warn "⚠️  或者使用 API 方式: ./scripts/release.sh $VERSION --api"
}

# ============================================================================
# 方式 2: 通过 Gitea API 触发（需要 token）
# ============================================================================
use_api() {
  local GITEA_URL="${GITEA_API_URL:-https://gitea.sisys.local}"
  local REPO="sisys/sisys"
  local TOKEN="${GITEA_TOKEN:-}"

  if [[ -z "$TOKEN" ]]; then
    log_error "未设置 GITEA_TOKEN 环境变量"
    log_info "获取方式: Gitea 用户设置 → 应用 → 生成 token"
    exit 1
  fi

  log_step "调用 Gitea API 触发 Release Workflow..."

  local payload
  if [[ "$DRY_RUN" == "true" ]]; then
    payload=$(cat <<EOF
{
  "ref": "refs/heads/main",
  "inputs": {
    "version": "$VERSION",
    "dry_run": "true"
  }
}
EOF
)
  else
    payload=$(cat <<EOF
{
  "ref": "refs/heads/main",
  "inputs": {
    "version": "$VERSION"
  }
}
EOF
)
  fi

  local response
  response=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Authorization: token $TOKEN" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    -d "$payload" \
    "$GITEA_URL/api/v1/repos/$REPO/actions/workflows/release.yaml/runs" 2>/dev/null)

  local http_code
  http_code=$(echo "$response" | tail -1)
  local body
  body=$(echo "$response" | sed '$d')

  if [[ "$http_code" -ge 200 && "$http_code" -lt 300 ]]; then
    log_info "✅ Release Workflow 已触发"
    log_info "📊 查看进度: $GITEA_URL/$REPO/actions"
  else
    log_error "API 调用失败 (HTTP $http_code)"
    log_error "响应: $body"
    exit 1
  fi
}

# ============================================================================
# 主流程
# ============================================================================
main() {
  log_info "=========================================="
  log_info "GitOps 发布流程"
  log_info "版本: $VERSION"
  if [[ "$DRY_RUN" == "true" ]]; then
    log_info "模式: 干运行（仅验证，不推送）"
  fi
  log_info "=========================================="

  # 检查是否有 API token，有则自动使用 API，否则提示用 UI
  if [[ -n "${GITEA_TOKEN:-}" ]]; then
    use_api
  else
    log_warn "未配置 GITEA_TOKEN，使用 UI 触发模式"
    log_warn "设置方法: export GITEA_TOKEN=your_token"
    log_info ""
    use_ui
  fi
}

main "$@"
