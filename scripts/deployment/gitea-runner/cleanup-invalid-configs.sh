#!/bin/bash
# ============================================================
# Gitea Runner 配置清理脚本
# ============================================================
# 功能：分析并清理无效配置
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

PROJECT_ROOT="/mnt/g/ai/sisys"
DEPLOY_DIR="$PROJECT_ROOT/deployments/gitea-runner"
SCRIPT_DIR="$PROJECT_ROOT/scripts/deployment/gitea-runner"
TEST_DIR="$PROJECT_ROOT/tests/deployment"

echo "=============================================="
echo "Gitea Runner 配置清理分析"
echo "=============================================="
echo ""

# ============================================================
# 配置文件分析
# ============================================================
log_info "=== 配置文件分析 ==="
echo ""

# 1. gitea-runner.yaml - 旧 Deployment 配置（已废弃）
log_info "1. gitea-runner.yaml"
log_warning "   状态：已废弃 (使用 Deployment，无持久化)"
log_info "   替代：gitea-runner-statefulset.yaml"
read -p "   是否删除？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f "$DEPLOY_DIR/gitea-runner.yaml"
    log_success "   已删除"
else
    log_info "   保留"
fi
echo ""

# 2. gitea-runner-pvc.yaml - 手动 PVC 配置（已废弃）
log_info "2. gitea-runner-pvc.yaml"
log_warning "   状态：已废弃 (StatefulSet 使用 volumeClaimTemplates 自动创建 PVC)"
log_info "   替代：gitea-runner-statefulset.yaml 中的 volumeClaimTemplates"
read -p "   是否删除？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f "$DEPLOY_DIR/gitea-runner-pvc.yaml"
    log_success "   已删除"
else
    log_info "   保留"
fi
echo ""

# 3. gitea-runner-https.yaml - HTTPS 配置（可选）
log_info "3. gitea-runner-https.yaml"
log_warning "   状态：可选配置 (当前使用 HTTP)"
log_info "   用途：HTTPS 环境下的 CA 证书挂载配置"
read -p "   是否保留作为参考？(y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    rm -f "$DEPLOY_DIR/gitea-runner-https.yaml"
    log_success "   已删除"
else
    log_info "   保留作为参考"
fi
echo ""

# 4. gitea-runner-statefulset.yaml - 当前有效配置
log_info "4. gitea-runner-statefulset.yaml"
log_success "   状态：✅ 有效 (当前运行配置)"
log_info "   保留"
echo ""

# 5. runner-config.yaml - Runner 配置文件
log_info "5. runner-config.yaml"
log_success "   状态：✅ 有效 (ConfigMap 源文件)"
log_info "   保留"
echo ""

# 6. runner-docker-executor.yaml - Docker Executor 配置
log_info "6. runner-docker-executor.yaml"
log_warning "   状态：未使用 (Docker Executor 配置，当前使用标准模式)"
log_info "   说明：当前配置使用 K3s containerd socket，无需独立 Docker Executor"
read -p "   是否删除？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f "$DEPLOY_DIR/runner-docker-executor.yaml"
    log_success "   已删除"
else
    log_info "   保留作为参考"
fi
echo ""

# 7. runner-k8s-executor.yaml - K8s Executor 配置
log_info "7. runner-k8s-executor.yaml"
log_warning "   状态：未使用 (K8s Executor 配置，当前使用标准模式)"
log_info "   说明：当前配置使用 K3s containerd socket，无需独立 K8s Executor"
read -p "   是否删除？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f "$DEPLOY_DIR/runner-k8s-executor.yaml"
    log_success "   已删除"
else
    log_info "   保留作为参考"
fi
echo ""

# 8. Chart.yaml 和 values.yaml - Helm Chart 配置
log_info "8. Chart.yaml + values.yaml"
log_warning "   状态：未使用 (当前使用 kubectl 部署)"
log_info "   说明：Helm Chart 部署方式未被采用"
read -p "   是否删除？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f "$DEPLOY_DIR/Chart.yaml" "$DEPLOY_DIR/values.yaml"
    log_success "   已删除"
else
    log_info "   保留作为参考"
fi
echo ""

# ============================================================
# 脚本文件分析
# ============================================================
log_info "=== 脚本文件分析 ==="
echo ""

# 1. deploy-runner.sh
log_info "1. deploy-runner.sh"
log_warning "   状态：已废弃 (部署旧 Deployment 配置)"
log_info "   替代：直接应用 statefulset 配置"
read -p "   是否删除？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f "$SCRIPT_DIR/deploy-runner.sh"
    log_success "   已删除"
else
    log_info "   保留作为参考"
fi
echo ""

# 2. configure-token.sh
log_info "2. configure-token.sh"
log_success "   状态：✅ 有效 (Token 配置脚本)"
log_info "   保留"
echo ""

# 3. configure-docker-executor.sh
log_info "3. configure-docker-executor.sh"
log_warning "   状态：未使用 (Docker Executor 配置脚本)"
read -p "   是否删除？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f "$SCRIPT_DIR/configure-docker-executor.sh"
    log_success "   已删除"
else
    log_info "   保留作为参考"
fi
echo ""

# 4. fix-duplicate-registration.sh
log_info "4. fix-duplicate-registration.sh"
log_success "   状态：✅ 有效 (修复重复注册问题脚本)"
log_info "   保留"
echo ""

# 5. cleanup-offline-runners.sh
log_info "5. cleanup-offline-runners.sh"
log_success "   状态：✅ 有效 (清理离线 Runner 脚本)"
log_info "   保留"
echo ""

# ============================================================
# 测试文件分析
# ============================================================
log_info "=== 测试文件分析 ==="
echo ""

# 1. test_gitea_runner_token.py
log_info "1. test_gitea_runner_token.py"
log_success "   状态：✅ 有效 (Token 配置测试)"
log_info "   保留"
echo ""

# 2. test_gitea_runner_deployment.py
log_info "2. test_gitea_runner_deployment.py"
log_warning "   状态：部分过时 (测试旧 Deployment 配置)"
log_info "   说明：需要更新为测试 StatefulSet 配置"
read -p "   是否删除并重新编写？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f "$TEST_DIR/test_gitea_runner_deployment.py"
    log_success "   已删除 (需要重新编写)"
else
    log_info "   保留 (需要更新)"
fi
echo ""

# 3. test_gitea_runner_persistence.py
log_info "3. test_gitea_runner_persistence.py"
log_success "   状态：✅ 有效 (持久化测试)"
log_info "   保留"
echo ""

# ============================================================
# 总结
# ============================================================
echo "=============================================="
echo "清理完成！"
echo "=============================================="
echo ""
log_info "保留的有效文件："
echo "  - gitea-runner-statefulset.yaml (主配置)"
echo "  - runner-config.yaml (Runner 配置)"
echo "  - gitea-runner-token-secret.yaml (Token Secret)"
echo "  - configure-token.sh (Token 配置脚本)"
echo "  - fix-duplicate-registration.sh (修复脚本)"
echo "  - cleanup-offline-runners.sh (清理脚本)"
echo "  - test_gitea_runner_token.py (Token 测试)"
echo "  - test_gitea_runner_persistence.py (持久化测试)"
echo ""
log_warning "需要手动清理的 K8s 资源："
echo "  - PVC: gitea-runner-data-0/1/2 (未使用的 PVC)"
echo "  - ConfigMap: gitea-runner-config (如有旧配置)"
echo ""
