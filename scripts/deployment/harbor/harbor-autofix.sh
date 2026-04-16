#!/bin/bash
# Harbor 自动修复 systemd 服务脚本
# 用途：WSL 启动时自动验证并修复 Harbor 部署
#
# 安装方式:
#   sudo cp scripts/deployment/harbor/harbor-autofix.service /etc/systemd/system/
#   sudo systemctl enable harbor-autofix
#   sudo systemctl start harbor-autofix

set -euo pipefail

# =============================================================================
# 配置 - 支持环境变量覆盖
# =============================================================================
HARBOR_NODE_IP="${HARBOR_NODE_IP:-localhost}"
HARBOR_NODEPORT="${HARBOR_NODEPORT:-31448}"
HARBOR_INGRESS_HOST="${HARBOR_INGRESS_HOST:-harbor.sisys.local}"
HARBOR_NS="harbor"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/harbor-autofix.log"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=========================================="
log "Harbor 自动修复服务启动"
log "=========================================="

# 等待 K3S 完全启动 (最多等待 60 秒)
log "等待 K3S 启动..."
for i in {1..30}; do
    if sudo systemctl is-active k3s &>/dev/null; then
        log "✅ K3S 已启动"
        break
    fi
    if [[ $i -eq 30 ]]; then
        log "❌ K3S 未在 60 秒内启动，退出"
        exit 1
    fi
    log "  等待中... ($i/30)"
    sleep 2
done

# 等待 Kubernetes API 可用
log "等待 Kubernetes API 可用..."
for i in {1..30}; do
    if sudo kubectl get namespace &>/dev/null; then
        log "✅ Kubernetes API 可用"
        break
    fi
    if [[ $i -eq 30 ]]; then
        log "❌ Kubernetes API 未在 60 秒内可用，退出"
        exit 1
    fi
    log "  等待中... ($i/30)"
    sleep 2
done

# 检查 Harbor 命名空间
log "检查 Harbor 命名空间..."
if ! sudo kubectl get namespace $HARBOR_NS &>/dev/null; then
    log "⚠️  Harbor 命名空间不存在，Harbor 可能未部署，跳过修复"
    exit 0
fi
log "✅ Harbor 命名空间存在"

# 等待 Harbor Pods 就绪 (最多等待 120 秒)
log "等待 Harbor Pods 就绪..."
for i in {1..60}; do
    RUNNING=$(sudo kubectl get pods -n $HARBOR_NS --no-headers 2>/dev/null | grep -c "Running" || echo "0")
    if [[ $RUNNING -ge 8 ]]; then
        log "✅ Harbor Pods 已就绪 ($RUNNING/8 Running)"
        break
    fi
    if [[ $i -eq 60 ]]; then
        log "⚠️  Harbor Pods 未在 120 秒内就绪，当前状态：$RUNNING/8"
    fi
    log "  等待中... ($i/60) - $RUNNING/8 Running"
    sleep 2
done

# 检查并删除旧的 Ingress (可能导致冲突)
log "检查旧的 Ingress..."
if sudo kubectl get ingress harbor-ingress -n $HARBOR_NS &>/dev/null; then
    log "⚠️  发现旧的 Ingress，删除中..."
    sudo kubectl delete ingress harbor-ingress -n $HARBOR_NS
    log "✅ 已删除旧的 Ingress"
fi

# 检查 IngressRoute
log "检查 IngressRoute..."
if ! sudo kubectl get ingressroute harbor-ingressroute -n $HARBOR_NS &>/dev/null; then
    log "⚠️  IngressRoute 不存在，重新应用配置..."
    cd "$SCRIPT_DIR/../../.."
    sudo kubectl apply -f deploy/kubernetes/harbor/ingress-route.yaml -n $HARBOR_NS
    log "✅ IngressRoute 已重新应用"
else
    log "✅ IngressRoute 存在"
fi

# 等待 Traefik 同步
log "等待 Traefik 同步 (10 秒)..."
sleep 10

# 验证 API 访问
log "验证 Harbor API 访问..."
for i in {1..5}; do
    API_RESPONSE=$(curl -k -s --connect-timeout 5 "https://${HARBOR_NODE_IP}:${HARBOR_NODEPORT}/api/v2.0/ping" \
      -H "Host: ${HARBOR_INGRESS_HOST}" 2>/dev/null || echo "")
    if [[ "$API_RESPONSE" == "Pong" ]]; then
        log "✅ Harbor API 访问正常：$API_RESPONSE"
        break
    fi
    if [[ $i -eq 5 ]]; then
        log "⚠️  Harbor API 在 5 次尝试后仍无法访问：$API_RESPONSE"
    else
        log "  重试 ($i/5)..."
        sleep 5
    fi
done

log "=========================================="
log "Harbor 自动修复完成"
log "=========================================="
log ""
log "部署状态:"
log "  Harbor Pods: $(sudo kubectl get pods -n $HARBOR_NS --no-headers 2>/dev/null | grep -c 'Running' || echo '0')/8 Running"
log "  IngressRoute: $([ $(sudo kubectl get ingressroute harbor-ingressroute -n $HARBOR_NS &>/dev/null && echo '✅') || echo '❌' ])"
log "  TLS Secret: $([ $(sudo kubectl get secret harbor-tls-secret -n $HARBOR_NS &>/dev/null && echo '✅') || echo '❌' ])"
log "  API 访问：$([ "$API_RESPONSE" == "Pong" ] && echo '✅ 正常' || echo '❌ 异常')"
log ""
log "访问地址：https://harbor.sisys.local:nodeport"
log "管理员账号：admin / Harbor@2026Secure!"
