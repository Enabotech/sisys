#!/bin/bash
# Harbor Ingress 自动应用脚本
# 用途：在 Harbor Helm 部署后自动应用正确的 Ingress 配置
# 这确保了 Traefik 始终使用最新的正确配置

set -euo pipefail

HARBOR_NAMESPACE="harbor"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INGRESS_FILE="$SCRIPT_DIR/../ingress.yaml"
LOG_FILE="/var/log/harbor-ingress-apply.log"

# 日志函数
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg" | tee -a "$LOG_FILE"
}

log "=============================================="
log "Harbor Ingress 自动配置"
log "=============================================="

# 检查 Harbor 是否已部署
if ! kubectl get deployment -n $HARBOR_NAMESPACE harbor-core &>/dev/null; then
    log "Harbor 未部署，跳过 Ingress 配置"
    exit 0
fi

# 等待 Harbor Core 就绪（最多 60 秒）
log "等待 Harbor Core 就绪..."
if kubectl wait --for=condition=Ready deployment/harbor-core -n $HARBOR_NAMESPACE --timeout=60s &>/dev/null; then
    log "Harbor Core 已就绪"
else
    log "Harbor Core 未就绪，退出"
    exit 0
fi

# 应用 Ingress 配置
log "应用 Ingress 配置..."
if [ -f "$INGRESS_FILE" ]; then
    if kubectl apply -f "$INGRESS_FILE" &>/dev/null; then
        log "Ingress 已应用"
    else
        log "Ingress 应用失败，但不影响 Harbor 运行"
        exit 0
    fi
else
    log "Ingress 文件不存在：$INGRESS_FILE"
    exit 0
fi

# 短暂等待 Traefik 同步
sleep 3

# 验证 API 访问
log "验证 API 访问..."
HARBOR_HOST="harbor.sisys.local"
HARBOR_NODEPORT="31448"
HARBOR_NODE_IP="172.21.110.12"

ping_response=$(curl -k -s --connect-timeout 3 https://$HARBOR_NODE_IP:$HARBOR_NODEPORT/api/v2.0/ping -H "Host: $HARBOR_HOST" 2>/dev/null || echo "")

if [ "$ping_response" = "Pong" ]; then
    log "API 访问正常"
    log "Harbor Ingress 配置完成！"
else
    log "API 访问异常，Traefik 可能正在同步"
fi

log "=============================================="
