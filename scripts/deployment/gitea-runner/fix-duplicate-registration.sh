#!/bin/bash
# ============================================================
# Gitea Runner 修复重复注册问题部署脚本
# ============================================================
# Story: 0-8-gitea-runner-configuration
# 问题修复：Runner 重复注册问题
#
# 功能:
#   - 清理旧的 Deployment 和离线 Runner
#   - 部署 StatefulSet 和 PVC
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
GITEA_URL="http://gitea-http.gitea.svc.cluster.local:3000"
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
# 步骤 1: 清理旧配置
# ============================================================

cleanup_old_deployment() {
    log_info "清理旧的 Deployment 配置..."

    # 删除旧 Deployment
    kubectl delete deployment gitea-runner -n "$NAMESPACE" --ignore-not-found

    # 删除旧 ConfigMap (不再需要)
    kubectl delete configmap gitea-runner-config -n "$NAMESPACE" --ignore-not-found

    log_success "旧配置已清理"
}

cleanup_offline_runners() {
    log_info "清理 Gitea 中的离线 Runner..."

    # 获取 Gitea 管理员 Token (需要从 Secret 读取)
    GITEA_ADMIN_TOKEN=$(kubectl get secret gitea-admin-token -n gitea -o jsonpath='{.data.token}' 2>/dev/null | base64 -d 2>/dev/null || echo "")

    if [ -z "$GITEA_ADMIN_TOKEN" ]; then
        log_warning "无法获取 Gitea 管理员 Token，跳过离线 Runner 清理"
        log_info "请手动清理：Gitea 管理页面 → 设置 → Actions → 删除离线 Runner"
        return 0
    fi

    # 获取所有 Runner
    RUNNERS=$(curl -sf -H "Authorization: token $GITEA_ADMIN_TOKEN" \
        "${GITEA_URL}/api/v1/admin/runners" 2>/dev/null || echo "")

    if [ -z "$RUNNERS" ]; then
        log_warning "无法获取 Runner 列表"
        return 0
    fi

    # 解析并删除离线 Runner (简化处理，使用 jq)
    if command -v jq &> /dev/null; then
        OFFLINE_RUNNERS=$(echo "$RUNNERS" | jq -r '.[] | select(.status == "offline") | .id' 2>/dev/null || echo "")

        if [ -n "$OFFLINE_RUNNERS" ]; then
            for RUNNER_ID in $OFFLINE_RUNNERS; do
                log_info "删除离线 Runner ID: $RUNNER_ID"
                curl -sf -X DELETE \
                    -H "Authorization: token $GITEA_ADMIN_TOKEN" \
                    "${GITEA_URL}/api/v1/admin/runners/$RUNNER_ID" 2>/dev/null || true
            done
            log_success "已清理离线 Runner"
        else
            log_success "无离线 Runner 需要清理"
        fi
    else
        log_warning "jq 未安装，跳过离线 Runner 清理"
        log_info "请手动清理：Gitea 管理页面 → 设置 → Actions → 删除离线 Runner"
    fi
}

cleanup_old_pvcs() {
    log_info "清理旧的 PVC..."

    # 删除可能存在的旧 PVC
    kubectl delete pvc gitea-runner-data-0 -n "$NAMESPACE" --ignore-not-found
    kubectl delete pvc gitea-runner-data-1 -n "$NAMESPACE" --ignore-not-found
    kubectl delete pvc gitea-runner-data-2 -n "$NAMESPACE" --ignore-not-found

    log_success "旧 PVC 已清理"
}

# ============================================================
# 步骤 2: 部署新配置
# ============================================================

deploy_statefulset() {
    log_info "部署 StatefulSet 和 PVC..."

    # 应用 PVC 配置
    kubectl apply -f "$SCRIPT_DIR/../../deployments/gitea-runner/gitea-runner-pvc.yaml"

    # 应用 StatefulSet 配置
    kubectl apply -f "$SCRIPT_DIR/../../deployments/gitea-runner/gitea-runner-statefulset.yaml"

    log_success "StatefulSet 部署完成"
}

wait_for_runners() {
    log_info "等待 Runner Pod 启动..."

    # 等待 StatefulSet 就绪
    kubectl rollout status statefulset gitea-runner -n "$NAMESPACE" --timeout=300s

    # 检查 Pod 状态
    log_info "检查 Runner Pod 状态..."
    kubectl get pods -n "$NAMESPACE" -l app=gitea-runner

    # 检查 PVC 状态
    log_info "检查 PVC 状态..."
    kubectl get pvc -n "$NAMESPACE" -l app=gitea-runner

    log_success "Runner Pod 已启动"
}

# ============================================================
# 步骤 3: 验证 Runner 注册
# ============================================================

verify_runner_registration() {
    log_info "验证 Runner 注册状态..."

    # 等待 30 秒让 Runner 完成注册
    sleep 30

    # 检查 Runner 日志
    log_info "检查 Runner 日志..."
    for i in 0 1 2; do
        POD_NAME="gitea-runner-$i"
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
    log_info "1. 访问 Gitea 管理页面 → 设置 → Actions"
    log_info "2. 确认只有 3 个 Runner (名称：gitea-runner-0, gitea-runner-1, gitea-runner-2)"
    log_info "3. 观察 Runner 状态应为 '空闲' 或 '忙碌'"
    log_info "4. 重启 Pod 后，Runner 不应重复注册"
    log_info ""
    log_info "验证命令："
    log_info "  kubectl get pods -n gitea-actions -l app=gitea-runner"
    log_info "  kubectl get pvc -n gitea-actions -l app=gitea-runner"
    log_info ""
}

# ============================================================
# 主程序
# ============================================================

main() {
    log_info "=============================================="
    log_info "Gitea Runner 重复注册问题修复"
    log_info "=============================================="
    log_info ""

    # 确认操作
    read -p "此操作将清理旧的 Deployment 和离线 Runner，是否继续？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warning "操作已取消"
        exit 0
    fi

    # 执行清理
    cleanup_old_deployment
    cleanup_offline_runners
    cleanup_old_pvcs

    # 部署新配置
    deploy_statefulset

    # 等待启动
    wait_for_runners

    # 验证注册
    verify_runner_registration
}

main "$@"
