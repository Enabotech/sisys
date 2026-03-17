#!/bin/bash
# Harbor 部署验证与修复脚本
# 用途：WSL 重启后验证 Harbor 部署状态，并自动修复可能的问题
#
# 使用方式:
#   ./scripts/deployment/harbor/verify-and-fix.sh

set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

HARBOR_NS="harbor"
FIX_NEEDED=false

log_info() { echo -e "${BLUE}ℹ️  $*${NC}"; }
log_success() { echo -e "${GREEN}✅ $*${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $*${NC}"; }
log_error() { echo -e "${RED}❌ $*${NC}"; }

echo "=============================================================================="
echo "Harbor 部署验证与修复"
echo "=============================================================================="
echo ""

# 检查 K3S 状态
log_info "检查 K3S 状态..."
if ! sudo systemctl is-active k3s &>/dev/null; then
    log_error "K3S 未运行，启动 K3S..."
    sudo systemctl start k3s
    sleep 5
fi
log_success "K3S 运行正常"

# 检查 Harbor 命名空间
log_info "检查 Harbor 命名空间..."
if ! sudo kubectl get namespace $HARBOR_NS &>/dev/null; then
    log_error "Harbor 命名空间不存在，Harbor 可能未部署"
    exit 1
fi
log_success "Harbor 命名空间存在"

# 检查 Harbor Pods
log_info "检查 Harbor Pods..."
POD_COUNT=$(sudo kubectl get pods -n $HARBOR_NS --no-headers 2>/dev/null | wc -l)
RUNNING_COUNT=$(sudo kubectl get pods -n $HARBOR_NS --no-headers 2>/dev/null | grep -c "Running" || echo "0")

if [[ $RUNNING_COUNT -lt 8 ]]; then
    log_warning "Harbor Pods 未完全运行 ($RUNNING_COUNT/8)"
    FIX_NEEDED=true
else
    log_success "Harbor Pods: $RUNNING_COUNT/8 Running"
fi

# 检查 IngressRoute
log_info "检查 IngressRoute..."
if ! sudo kubectl get ingressroute harbor-ingressroute -n $HARBOR_NS &>/dev/null; then
    log_warning "IngressRoute 不存在，需要重新应用配置"
    FIX_NEEDED=true
else
    log_success "IngressRoute 存在"
fi

# 检查旧的 Ingress (可能导致冲突)
log_info "检查旧的 Ingress..."
if sudo kubectl get ingress harbor-ingress -n $HARBOR_NS &>/dev/null; then
    log_warning "发现旧的 Ingress，可能导致冲突，删除中..."
    sudo kubectl delete ingress harbor-ingress -n $HARBOR_NS
    log_success "已删除旧的 Ingress"
fi

# 检查 TLS Secret
log_info "检查 TLS Secret..."
if ! sudo kubectl get secret harbor-tls-secret -n $HARBOR_NS &>/dev/null; then
    log_error "TLS Secret 不存在，HTTPS 将无法工作"
    FIX_NEEDED=true
else
    log_success "TLS Secret 存在"
fi

# 检查 Traefik
log_info "检查 Traefik..."
if ! sudo kubectl get pods -n traefik -l app.kubernetes.io/name=traefik --no-headers 2>/dev/null | grep -q "Running"; then
    log_warning "Traefik 未运行"
    FIX_NEEDED=true
else
    log_success "Traefik 运行正常"
fi

echo ""
echo "=============================================================================="

# 如果需要修复
if [[ "$FIX_NEEDED" == "true" ]]; then
    log_warning "检测到问题，开始修复..."
    echo ""
    
    # 重新应用 IngressRoute
    if [[ -f "deployments/harbor/ingress-route.yaml" ]]; then
        log_info "应用 IngressRoute 配置..."
        sudo kubectl apply -f deployments/harbor/ingress-route.yaml -n $HARBOR_NS
        log_success "IngressRoute 已应用"
    fi
    
    # 等待 Traefik 同步
    log_info "等待 Traefik 同步 (10 秒)..."
    sleep 10
    
    echo ""
    log_success "修复完成！"
else
    log_success "所有检查通过，无需修复"
fi

echo ""
echo "=============================================================================="
echo "验证 API 访问"
echo "=============================================================================="

# 测试 API 访问
log_info "测试 Harbor API..."
API_RESPONSE=$(curl -k -s --connect-timeout 5 "https://172.21.110.12:31448/api/v2.0/ping" -H "Host: harbor.sisys.local" 2>/dev/null || echo "")

if [[ "$API_RESPONSE" == "Pong" ]]; then
    log_success "Harbor API 访问正常：$API_RESPONSE"
else
    log_warning "Harbor API 响应异常：$API_RESPONSE"
    log_info "等待 30 秒后重试..."
    sleep 30
    API_RESPONSE=$(curl -k -s --connect-timeout 5 "https://172.21.110.12:31448/api/v2.0/ping" -H "Host: harbor.sisys.local" 2>/dev/null || echo "")
    if [[ "$API_RESPONSE" == "Pong" ]]; then
        log_success "Harbor API 访问正常：$API_RESPONSE"
    else
        log_error "Harbor API 仍然无法访问，请检查 Traefik 日志"
        exit 1
    fi
fi

echo ""
echo "=============================================================================="
echo "部署状态总结"
echo "=============================================================================="
echo "Harbor Pods: $RUNNING_COUNT/8 Running"
INGRESS_EXISTS=$([ "$(sudo kubectl get ingressroute harbor-ingressroute -n $HARBOR_NS &>/dev/null && echo yes)" ] || echo no)
TLS_EXISTS=$([ "$(sudo kubectl get secret harbor-tls-secret -n $HARBOR_NS &>/dev/null && echo yes)" ] || echo no)
echo "IngressRoute: $INGRESS_EXISTS"
echo "TLS Secret: $TLS_EXISTS"
if [ "$API_RESPONSE" == "Pong" ]; then
    echo "API 访问：✅ 正常"
else
    echo "API 访问：❌ 异常"
fi
echo ""
log_success "Harbor 部署验证完成！"
echo "访问地址：https://harbor.sisys.local"
echo "管理员账号：admin / Harbor@2026Secure!"
echo "=============================================================================="
