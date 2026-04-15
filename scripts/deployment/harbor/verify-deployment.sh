#!/bin/bash
# Harbor 部署验证脚本
# 用途：验证所有配置已正确应用
#
# 使用方式:
#   ./scripts/deployment/harbor/verify-deployment.sh
#
# 返回码:
#   0 - 所有检查通过
#   1 - 存在检查失败

set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
HARBOR_NS="harbor"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 计数器
check_count=0
pass_count=0
fail_count=0
warn_count=0

# =============================================================================
# 函数定义
# =============================================================================

log_info() {
    echo -e "${BLUE}ℹ️  $*${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $*${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $*${NC}"
    warn_count=$((warn_count + 1))
}

log_error() {
    echo -e "${RED}❌ $*${NC}"
}

# 检查函数
check() {
    local name="$1"
    local command="$2"
    local hint="${3:-}"

    check_count=$((check_count + 1))

    echo -n "  检查：$name ... "

    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 通过${NC}"
        pass_count=$((pass_count + 1))
        return 0
    else
        echo -e "${RED}❌ 失败${NC}"
        fail_count=$((fail_count + 1))
        if [[ -n "$hint" ]]; then
            echo -e "       ${YELLOW}提示：$hint${NC}"
        fi
        return 1
    fi
}

# 检查 kubectl 是否可用
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl 未安装"
        exit 1
    fi

    if ! kubectl cluster-info &> /dev/null; then
        log_error "无法连接到 Kubernetes 集群"
        echo ""
        echo "请检查:"
        echo "  1. K3S 集群是否运行：sudo systemctl status k3s"
        echo "  2. kubeconfig 配置：~/.kube/config 或 /etc/rancher/k3s/k3s.yaml"
        echo "  3. 使用 sudo: export KUBECONFIG=/etc/rancher/k3s/k3s.yaml"
        exit 1
    fi
}

# =============================================================================
# 主流程
# =============================================================================

main() {
    echo "=============================================================================="
    echo -e "${BLUE}🔍 Harbor 部署验证${NC}"
    echo "=============================================================================="
    echo ""

    # 检查 kubectl
    log_info "检查 Kubernetes 连接..."
    check_kubectl
    log_success "Kubernetes 连接正常"
    echo ""

    # 1. 命名空间检查
    echo -e "${BLUE}📦 命名空间检查${NC}"
    check "命名空间存在" "kubectl get namespace $HARBOR_NS" "运行：kubectl create namespace $HARBOR_NS"
    echo ""

    # 2. Secret 检查
    echo -e "${BLUE}🔐 Secret 检查${NC}"
    check "harbor-secret 存在" "kubectl get secret harbor-secret -n $HARBOR_NS" "运行：kubectl apply -f .secrets/harbor-secret.yaml"
    check "Secret 包含 SECRET_KEY" "kubectl get secret harbor-secret -n $HARBOR_NS -o jsonpath='{.data.SECRET_KEY}' | grep -q ." "检查 Secret 是否正确生成"
    check "Secret 包含 HARBOR_ADMIN_PASSWORD" "kubectl get secret harbor-secret -n $HARBOR_NS -o jsonpath='{.data.HARBOR_ADMIN_PASSWORD}' | grep -q ." "检查管理员密码是否配置"
    echo ""

    # 3. NetworkPolicy 检查
    echo -e "${BLUE}🛡️  NetworkPolicy 检查${NC}"
    POLICY_COUNT=$(kubectl get networkpolicy -n $HARBOR_NS --no-headers 2>/dev/null | wc -l || echo "0")
    check "NetworkPolicy 已应用 (期望>=8 个，实际${POLICY_COUNT}个)" "[[ $POLICY_COUNT -ge 8 ]]" "运行：kubectl apply -k deployments/harbor/"

    if [[ $POLICY_COUNT -lt 8 ]]; then
        echo -e "       ${YELLOW}当前 NetworkPolicy 列表:${NC}"
        kubectl get networkpolicy -n $HARBOR_NS --no-headers 2>/dev/null || echo "       (无)"
    fi
    echo ""

    # 4. IngressRoute 检查
    echo -e "${BLUE}🌐 IngressRoute 检查${NC}"
    if kubectl get crd ingressroutes.traefik.io &> /dev/null; then
        check "IngressRoute CRD 存在" "kubectl get ingressroute harbor-ingressroute -n $HARBOR_NS" "运行：kubectl apply -f deployments/harbor/ingress-route.yaml"
        check "IngressRoute 配置正确" "kubectl get ingressroute harbor-ingressroute -n $HARBOR_NS -o jsonpath='{.spec.entryPoints}' | grep -q websecure"
    else
        log_warning "Traefik IngressRoute CRD 未安装，跳过 IngressRoute 检查"
    fi
    echo ""

    # 5. Middleware 检查
    echo -e "${BLUE}⚙️  Middleware 检查${NC}"
    if kubectl get crd middlewares.traefik.io &> /dev/null; then
        check "安全头 Middleware 存在" "kubectl get middleware harbor-security-headers -n $HARBOR_NS" "运行：kubectl apply -f deployments/harbor/middleware.yaml"
        check "Middleware 链存在" "kubectl get middleware harbor-middleware-chain -n $HARBOR_NS" "运行：kubectl apply -f deployments/harbor/middleware.yaml"
    else
        log_warning "Traefik Middleware CRD 未安装，跳过 Middleware 检查"
    fi
    echo ""

    # 6. Pod 状态检查
    echo -e "${BLUE}📊 Pod 状态检查${NC}"
    POD_COUNT=$(kubectl get pods -n $HARBOR_NS --no-headers 2>/dev/null | wc -l || echo "0")
    check "Pod 已部署 (实际${POD_COUNT}个)" "[[ $POD_COUNT -gt 0 ]]" "运行：helm install harbor harbor/harbor -n harbor -f deployments/harbor/values.yaml"

    if [[ $POD_COUNT -gt 0 ]]; then
        RUNNING_COUNT=$(kubectl get pods -n $HARBOR_NS --no-headers 2>/dev/null | grep -c "Running" || echo "0")
        check "所有 Pod Running (期望 8 个，实际${RUNNING_COUNT}个)" "[[ $RUNNING_COUNT -ge 8 ]]" "检查 Pod 日志：kubectl logs -n $HARBOR_NS <pod-name>"

        # 显示 Pod 状态
        echo -e "       ${BLUE}Pod 状态:${NC}"
        kubectl get pods -n $HARBOR_NS --no-headers 2>/dev/null | while read -r line; do
            echo "       $line"
        done
    fi
    echo ""

    # 7. 服务连通性检查
    echo -e "${BLUE}🔗 服务连通性检查${NC}"
    check "Harbor Core 服务存在" "kubectl get service harbor-core -n $HARBOR_NS" "运行：kubectl apply -f deployments/harbor/values.yaml (Helm 部署)"

    if [[ $POD_COUNT -gt 0 ]]; then
        # 尝试 API Ping 检查
        CORE_POD=$(kubectl get pods -n $HARBOR_NS -l app=harbor-core -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
        if [[ -n "$CORE_POD" ]]; then
            check "API Ping 响应" "kubectl exec -n $HARBOR_NS $CORE_POD -- curl -sf http://localhost:8080/api/v2.0/ping | grep -q Pong" "检查 Harbor Core 是否正常运行"
        fi
    fi
    echo ""

    # 8. PVC 检查
    echo -e "${BLUE}💾 PVC 检查${NC}"
    PVC_COUNT=$(kubectl get pvc -n $HARBOR_NS --no-headers 2>/dev/null | wc -l || echo "0")
    BOUND_COUNT=$(kubectl get pvc -n $HARBOR_NS --no-headers 2>/dev/null | grep -c "Bound" || echo "0")
    check "PVC 已绑定 (期望>=5 个，实际${BOUND_COUNT}/${PVC_COUNT}个)" "[[ $BOUND_COUNT -ge 5 ]]" "检查存储类：kubectl get storageclass"

    if [[ $PVC_COUNT -gt 0 ]]; then
        echo -e "       ${BLUE}PVC 状态:${NC}"
        kubectl get pvc -n $HARBOR_NS --no-headers 2>/dev/null | while read -r line; do
            echo "       $line"
        done
    fi
    echo ""

    # 总结
    echo "=============================================================================="
    echo -e "${BLUE}验证总结${NC}"
    echo "=============================================================================="
    echo "总检查项：$check_count"
    echo -e "通过：${GREEN}$pass_count${NC}"
    echo -e "失败：${RED}$fail_count${NC}"
    echo -e "警告：${YELLOW}$warn_count${NC}"
    echo ""

    if [[ $fail_count -gt 0 ]]; then
        echo -e "${RED}❌ 验证失败：$fail_count 项检查未通过${NC}"
        echo ""
        echo "建议执行:"
        echo "  1. 生成密码：./scripts/security/generate-harbor-secrets.sh"
        echo "  2. 应用配置：kubectl apply -k deployments/harbor/"
        echo "  3. 部署 Harbor: helm install harbor harbor/harbor -n harbor -f deployments/harbor/values.yaml"
        echo "  4. 重新验证：./scripts/deployment/harbor/verify-deployment.sh"
        echo ""
        exit 1
    else
        echo -e "${GREEN}✅ 所有检查通过！${NC}"
        echo ""
        echo "Harbor 部署完成！访问地址：https://harbor.sisys.local"
        echo "管理员账号：admin / (查看 .secrets/harbor-credentials.txt)"
        echo ""
        exit 0
    fi
}

# 执行主流程
main "$@"
