#!/bin/bash
# ============================================================================
# GitOps 生产环境一键回滚脚本
# 用法: ./scripts/rollback.sh [target-revision]
# 示例:
#   ./scripts/rollback.sh              # 自动回滚到上一个版本
#   ./scripts/rollback.sh HEAD:abc1234 # 回滚到指定 revision
#
# 前置条件:
#   - argocd CLI 已安装并配置
#   - kubectl 已配置并指向正确的集群
#   - 已登录 ArgoCD (argocd login)
# ============================================================================
set -euo pipefail

APP_NAME="sisys-app-prod"
NAMESPACE="sisys-prod"

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
# 前置检查
# ============================================================================
check_prerequisites() {
  log_step "检查前置条件..."

  if ! command -v argocd &> /dev/null; then
    log_error "argocd CLI 未安装，请先安装: https://argo-cd.readthedocs.io/en/stable/cli_installation/"
    exit 1
  fi

  if ! command -v kubectl &> /dev/null; then
    log_error "kubectl 未安装"
    exit 1
  fi

  if ! command -v jq &> /dev/null; then
    log_error "jq 未安装，请先安装: sudo apt install jq"
    exit 1
  fi

  # 检查 ArgoCD 登录状态
  if ! argocd app get "$APP_NAME" &> /dev/null; then
    log_error "无法访问 ArgoCD Application '$APP_NAME'，请确认已登录"
    log_info "登录命令: argocd login argocd.sisys.local"
    exit 1
  fi

  log_info "✅ 前置条件检查通过"
}

# ============================================================================
# 获取目标 revision
# ============================================================================
get_target_revision() {
  TARGET_REVISION="${1:-}"

  if [[ -n "$TARGET_REVISION" ]]; then
    log_info "使用指定的 revision: $TARGET_REVISION"
    return
  fi

  # 自动选择上一个版本
  log_step "获取 $APP_NAME 发布历史..."
  argocd app history "$APP_NAME" --output wide 2>/dev/null || true

  TARGET_REVISION=$(argocd app history "$APP_NAME" --output json 2>/dev/null \
    | jq -r '.[-2].revision' 2>/dev/null || echo "")

  if [[ -z "$TARGET_REVISION" || "$TARGET_REVISION" == "null" ]]; then
    log_error "无法获取上一个版本，请手动指定 revision"
    log_info "用法: ./scripts/rollback.sh HEAD:abc1234"
    exit 1
  fi

  log_warn "自动选择上一个版本: $TARGET_REVISION"
}

# ============================================================================
# 确认回滚
# ============================================================================
confirm_rollback() {
  log_warn "=========================================="
  log_warn "即将回滚 $APP_NAME"
  log_warn "目标 revision: $TARGET_REVISION"
  log_warn "命名空间: $NAMESPACE"
  log_warn "=========================================="

  read -p "确认执行回滚？(y/N): " confirm
  if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    log_info "取消回滚"
    exit 0
  fi
}

# ============================================================================
# 执行回滚
# ============================================================================
execute_rollback() {
  log_step "设置 revision..."
  argocd app set "$APP_NAME" --revision "$TARGET_REVISION"

  log_step "同步应用..."
  argocd app sync "$APP_NAME" --prune

  # 等待同步完成
  log_step "等待同步完成..."
  sleep 10

  # 检查同步状态
  local sync_status
  sync_status=$(argocd app get "$APP_NAME" -o json 2>/dev/null \
    | jq -r '.status.sync.status' 2>/dev/null || echo "unknown")

  if [[ "$sync_status" == "Synced" ]]; then
    log_info "✅ ArgoCD 同步成功"
  else
    log_warn "⚠️  ArgoCD 同步状态: $sync_status（可能需要等待或手动检查）"
  fi
}

# ============================================================================
# 验证回滚
# ============================================================================
verify_rollback() {
  log_step "检查 Pod 状态..."
  kubectl get pods -n "$NAMESPACE" -o wide 2>/dev/null || {
    log_warn "⚠️  无法获取 Pod 状态，请手动检查"
    return
  }

  # 检查是否有 Pod 处于错误状态
  local error_pods
  error_pods=$(kubectl get pods -n "$NAMESPACE" \
    -o jsonpath='{range .items[*]}{.metadata.name}={.status.phase}{"\n"}{end}' 2>/dev/null \
    | grep -v Running || true)

  if [[ -n "$error_pods" ]]; then
    log_warn "⚠️  以下 Pod 未处于 Running 状态:"
    echo "$error_pods"
  else
    log_info "✅ 所有 Pod 正常运行"
  fi
}

# ============================================================================
# 主流程
# ============================================================================
main() {
  log_info "=========================================="
  log_info "GitOps 生产环境回滚"
  log_info "Application: $APP_NAME"
  log_info "=========================================="

  check_prerequisites
  get_target_revision "$@"
  confirm_rollback
  execute_rollback
  verify_rollback

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
}

main "$@"
