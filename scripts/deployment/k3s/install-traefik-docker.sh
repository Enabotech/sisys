#!/bin/bash
# Traefik 安装脚本 - K3S 多节点（Docker 容器）
# Story 0.4: K3S 集群部署（WSL2 多节点版）
# 技术栈：Traefik v2.10 + K3S v1.34.5

set -e

echo "=== Traefik 安装脚本 (K3S 多节点) ==="
echo "日期：$(date)"
echo ""

# ========== 前置检查 ==========

echo "检查前置条件..."

# 检查 kubectl
if ! command -v kubectl &>/dev/null; then
    echo "⚠️ kubectl 未找到，尝试使用 docker exec..."
    KUBECTL_CMD="docker exec k3s-node-server-1 k3s kubectl"
else
    KUBECTL_CMD="kubectl"
fi

# 检查集群连接
if ! $KUBECTL_CMD get nodes &>/dev/null; then
    echo "❌ 无法连接到 K3S 集群"
    echo "   请确保已运行 install-multi-node.sh"
    exit 1
fi
echo "✅ K3S 集群连接正常"

# 检查 Helm
if ! command -v helm &>/dev/null; then
    echo "❌ Helm 未安装"
    echo "   安装命令：curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
    exit 1
fi
echo "✅ Helm 已安装：$(helm version --short)"

echo ""

# ========== 添加 Helm 仓库 ==========

echo "添加 Traefik Helm 仓库..."
helm repo add traefik https://traefik.github.io/charts
helm repo update
echo "✅ Helm 仓库已添加"

echo ""

# ========== 安装 Traefik ==========

echo "安装 Traefik v2.10..."

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALUES_FILE="$SCRIPT_DIR/traefik-values.yaml"

# 设置 Helm Chart 版本
TRAEFIK_CHART_VERSION="22.5.3"

if [ ! -f "$VALUES_FILE" ]; then
    echo "⚠️ 警告：traefik-values.yaml 不存在，使用默认配置"
    helm install traefik traefik/traefik \
        --namespace traefik \
        --create-namespace \
        --version "$TRAEFIK_CHART_VERSION"
else
    echo "使用配置文件：$VALUES_FILE"
    helm install traefik traefik/traefik \
        --namespace traefik \
        --create-namespace \
        -f "$VALUES_FILE" \
        --version "$TRAEFIK_CHART_VERSION"
fi

echo "等待 Traefik 部署..."
sleep 10

# ========== 验证安装 ==========

echo "验证 Traefik 安装..."

# 检查 Pod 状态
$KUBECTL_CMD get pods -n traefik

# 等待 Pod 运行
echo "等待 Traefik Pod 运行..."
$KUBECTL_CMD wait --for=condition=ready pod \
    --selector=app.kubernetes.io/name=traefik \
    --namespace=traefik \
    --timeout=300s

# 检查服务
echo "检查 Traefik 服务..."
$KUBECTL_CMD get svc -n traefik

# 创建示例 Ingress
echo ""
echo "创建示例 Ingress..."
cat <<EOF | $KUBECTL_CMD apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: example
  namespace: default
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
spec:
  rules:
  - host: example.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: kubernetes
            port:
              number: 443
EOF

echo "✅ 示例 Ingress 已创建（example.local）"

# ========== 访问信息 ==========

echo ""
echo "=== Traefik 安装完成 ==="
echo "✅ Traefik 版本：v2.10"
echo "✅ 入口点：web(80), websecure(443)"
echo ""
echo "访问方式（WSL2 多节点环境）:"
echo "  1. Port-forward（推荐）:"
echo "     $KUBECTL_CMD -n traefik port-forward svc/traefik 8080:80"
echo "     浏览器访问：http://localhost:8080"
echo ""
echo "  2. NodePort（需要修改 service type）:"
echo "     修改 traefik-values.yaml 中 service.type 为 NodePort"
echo ""
echo "下一步:"
echo "  运行健康检查：sudo ./scripts/deployment/k3s/health_check_docker.sh"
echo ""
echo "=== 安装完成 ✅ ==="
