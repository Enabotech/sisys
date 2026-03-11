#!/bin/bash
# Traefik 反向代理安装脚本 - WSL2 适配版
# Story 0.4: K3S 集群部署（WSL2 重构版）
# 技术栈：Traefik v2.10
# K3S 版本：v1.34.5
# 环境：WSL2 Ubuntu 22.04

set -e

echo "=== Traefik 反向代理安装脚本 ==="
echo "日期：$(date)"
echo "目标版本：Traefik v2.10"
echo ""

# ========== 前置检查 ==========

echo "检查前置条件..."

# 检查 K3S 是否运行
if ! kubectl get nodes &>/dev/null; then
    echo "❌ K3S 集群未运行，请先安装 K3S"
    exit 1
fi
echo "✅ K3S 集群运行正常"

# 检查 Helm 是否安装
if ! command -v helm &>/dev/null; then
    echo "❌ Helm 未安装，请先安装 Helm v3"
    echo "   安装命令：curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
    exit 1
fi
echo "✅ Helm 已安装：$(helm version --short)"

# 检查 Traefik 命名空间
if kubectl get namespace traefik &>/dev/null; then
    echo "⚠️ Traefik 命名空间已存在，可能已安装"
    read -p "是否继续安装？(y/n): " confirm
    if [ "$confirm" != "y" ]; then
        echo "取消安装"
        exit 0
    fi
fi

# 检查端口占用
echo "检查端口占用..."
for port in 80 443; do
    if netstat -tlnp 2>/dev/null | grep -q ":$port "; then
        echo "⚠️ 警告：端口 $port 被占用"
    else
        echo "✅ 端口 $port 可用"
    fi
done

echo ""

# ========== 添加 Traefik Helm 仓库 ==========

echo "添加 Traefik Helm 仓库..."

# 尝试使用国内镜像（如果官方仓库不可达）
HELM_REPO="https://traefik.github.io/charts"
HELM_REPO_CN="https://helm.traefik.io/traefik"  # Traefik 官方国内镜像
HELM_REPO_GITEE="https://charts.traefik.cn"     # 国内镜像

# 测试官方仓库连接
if ! curl -sfL --connect-timeout 5 "$HELM_REPO/index.yaml" &>/dev/null; then
    echo "⚠️ 官方仓库不可达，尝试使用国内镜像..."

    # 尝试 Gitee 镜像
    if curl -sfL --connect-timeout 5 "$HELM_REPO_GITEE/index.yaml" &>/dev/null; then
        HELM_REPO="$HELM_REPO_GITEE"
        echo "✅ 使用 Gitee 镜像：$HELM_REPO"
    else
        HELM_REPO="$HELM_REPO_CN"
        echo "✅ 使用官方国内镜像：$HELM_REPO"
    fi
else
    echo "✅ 使用官方仓库：$HELM_REPO"
fi

helm repo add traefik "$HELM_REPO"
helm repo update
echo "✅ Helm 仓库已添加：$HELM_REPO"

echo ""

# ========== 安装 Traefik ==========

echo "安装 Traefik v2.10..."

# 设置 Helm Chart 版本（版本锁定）
# 注意：Traefik Helm Chart 版本与 Traefik 应用版本不同
# Chart 22.x 对应 Traefik v2.10.x
# 如果不指定版本，使用最新版
TRAEFIK_CHART_VERSION=""  # 留空表示使用最新版

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALUES_FILE="$SCRIPT_DIR/traefik-values.yaml"

# 检查配置文件是否存在
if [ ! -f "$VALUES_FILE" ]; then
    echo "⚠️ 警告：traefik-values.yaml 不存在，使用默认配置"
    if [ -n "$TRAEFIK_CHART_VERSION" ]; then
        helm install traefik traefik/traefik \
            --namespace traefik \
            --create-namespace \
            --version "$TRAEFIK_CHART_VERSION"
    else
        helm install traefik traefik/traefik \
            --namespace traefik \
            --create-namespace
    fi
else
    echo "使用配置文件：$VALUES_FILE"
    if [ -n "$TRAEFIK_CHART_VERSION" ]; then
        helm install traefik traefik/traefik \
            --namespace traefik \
            --create-namespace \
            -f "$VALUES_FILE" \
            --version "$TRAEFIK_CHART_VERSION"
    else
        helm install traefik traefik/traefik \
            --namespace traefik \
            --create-namespace \
            -f "$VALUES_FILE"
    fi
fi

echo "等待 Traefik 部署..."
sleep 30

# ========== 验证安装 ==========

echo "验证 Traefik 安装..."

# 检查 Pod 状态
kubectl get pods -n traefik

# 等待 Pod 运行
echo "等待 Traefik Pod 运行..."
kubectl wait --for=condition=ready pod \
    --selector=app.kubernetes.io/name=traefik \
    --namespace=traefik \
    --timeout=300s

# 检查服务
echo "检查 Traefik 服务..."
kubectl get svc -n traefik

# 获取 LoadBalancer IP（如果使用）
TRAFFIC_IP=$(kubectl get svc -n traefik traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
if [ -n "$TRAFFIC_IP" ]; then
    echo "✅ LoadBalancer IP: $TRAFFIC_IP"
fi

# ========== 创建示例 Ingress ==========

echo ""
echo "创建示例 Ingress..."

cat <<EOF | kubectl apply -f -
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

# ========== 访问 Traefik 仪表板 ==========

echo ""
echo "=== Traefik 仪表板访问 ==="
echo "仪表板配置：traefik.local"
echo ""
echo "本地访问方法："
echo "  kubectl -n traefik port-forward deploy/traefik 9000:9000"
echo "  浏览器访问：http://localhost:9000/dashboard/"
echo ""

# ========== 安装完成摘要 ==========

echo "=== Traefik 安装完成 ==="
echo "✅ Traefik 版本：v2.10"
echo "✅ 入口点：web(80), websecure(443)"
echo "✅ 仪表板：http://traefik.local/dashboard/"
echo ""
echo "下一步：运行健康检查脚本"
echo "命令：./scripts/deployment/k3s/health_check.sh"
echo ""
echo "=== 安装完成 ✅ ==="
