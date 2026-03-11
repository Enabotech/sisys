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

# 添加仓库（忽略已存在的错误）
helm repo add traefik "$HELM_REPO" 2>/dev/null || echo "✅ Helm 仓库已存在"
helm repo update
echo "✅ Helm 仓库已添加：$HELM_REPO"

echo ""

# ========== 安装 Traefik ==========

echo "安装 Traefik v2.10..."

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALUES_FILE="$SCRIPT_DIR/traefik-values.yaml"

# 检查配置文件
if [ ! -f "$VALUES_FILE" ]; then
    echo "⚠️ 警告：traefik-values.yaml 不存在，使用默认配置"
    VALUES_FILE=""
fi

# 使用国内镜像源下载 Chart
echo "准备 Helm Chart..."
CHART_URL="https://traefik.github.io/charts/traefik-39.0.5.tgz"
CHART_URL_CN="https://helm.traefik.io/traefik/traefik-39.0.5.tgz"
TEMP_CHART="/tmp/traefik-39.0.5.tgz"

# 尝试下载 Chart（优先国内镜像）
if curl -sfL --connect-timeout 10 -o "$TEMP_CHART" "$CHART_URL_CN"; then
    echo "✅ 从国内镜像下载 Chart 成功"
elif curl -sfL --connect-timeout 10 --retry 3 -o "$TEMP_CHART" "$CHART_URL"; then
    echo "✅ 从官方仓库下载 Chart 成功"
else
    echo "❌ 无法下载 Helm Chart，请检查网络连接"
    echo "   手动下载：wget $CHART_URL_CN -O $TEMP_CHART"
    exit 1
fi

# 执行安装
echo "安装 Traefik..."
if [ -n "$VALUES_FILE" ]; then
    echo "使用配置文件：$VALUES_FILE"
    helm install traefik "$TEMP_CHART" \
        --namespace traefik \
        --create-namespace \
        -f "$VALUES_FILE"
else
    helm install traefik "$TEMP_CHART" \
        --namespace traefik \
        --create-namespace
fi

# 清理临时文件
rm -f "$TEMP_CHART"

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
