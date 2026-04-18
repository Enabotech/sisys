#!/bin/bash
# ============================================================
# Gitea Runner 部署脚本 - 组织级 Runner
# ============================================================
# Story: 0-8-gitea-runner-configuration
# 部署：组织级 Runner (gitea-org-runner)
#
# 功能:
#   - 部署组织级 Runner StatefulSet
#   - 验证 Runner 注册状态
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
NAMESPACE="gitea-actions"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================
# 辅助函数
# ============================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================================
# 部署组织级 Runner
# ============================================================

deploy_org_runner() {
    log_info "部署组织级 Runner..."

    # 应用 Token Secret
    kubectl apply -f "$SCRIPT_DIR/../../deploy/kubernetes/gitea-runner/gitea-org-runner-token-secret.yaml"

    # 应用 StatefulSet 配置
    kubectl apply -f "$SCRIPT_DIR/../../deploy/kubernetes/gitea-runner/gitea-actions-complete.yaml"

    log_success "组织级 Runner 部署完成"
}

wait_for_runners() {
    log_info "等待 Runner Pod 启动..."

    # 等待 StatefulSet 就绪
    kubectl rollout status statefulset gitea-org-runner -n "$NAMESPACE" --timeout=300s

    # 检查 Pod 状态
    log_info "检查 Runner Pod 状态..."
    kubectl get pods -n "$NAMESPACE" -l app=gitea-org-runner

    # 检查 PVC 状态
    log_info "检查 PVC 状态..."
    kubectl get pvc -n "$NAMESPACE" -l app=gitea-org-runner

    log_success "Runner Pod 已启动"
}

# ============================================================
# 验证 Runner 注册
# ============================================================

verify_runner_registration() {
    log_info "验证 Runner 注册状态..."

    # 等待 30 秒让 Runner 完成注册
    sleep 30

    # 检查 Runner 日志
    log_info "检查 Runner 日志..."
    for i in 0 1 2; do
        POD_NAME="gitea-org-runner-$i"
        log_info "Pod: $POD_NAME"
        kubectl logs -n "$NAMESPACE" "$POD_NAME" --tail=20 || true
    done

    log_success "Runner 注册验证完成"
    log_info ""
    log_info "=============================================="
    log_info "✅ 部署完成！"
    log_info "=============================================="
    log_info ""
    log_info "下一步操作："
    log_info "1. 访问 Gitea 组织页面 → Settings → Actions → Runners"
    log_info "2. 确认有 3 个 Runner (名称：gitea-org-runner-0/1/2)"
    log_info "3. 观察 Runner 状态应为 '空闲' 或 '忙碌'"
    log_info ""
    log_info "验证命令："
    log_info "  kubectl get pods -n gitea-actions -l app=gitea-org-runner"
    log_info "  kubectl get pvc -n gitea-actions -l app=gitea-org-runner"
    log_info ""
}

# ============================================================
# 主程序
# ============================================================

main() {
    log_info "=============================================="
    log_info "Gitea 组织级 Runner 部署"
    log_info "=============================================="
    log_info ""

    # 部署组织级 Runner
    deploy_org_runner

    # 等待启动
    wait_for_runners

    # 验证注册
    verify_runner_registration
}

main "$@"
