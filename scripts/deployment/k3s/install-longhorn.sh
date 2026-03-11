#!/bin/bash
# Longhorn 存储安装脚本
# Story 0.4: K3S 集群部署
# 技术栈：Longhorn v1.5.3
# K3S 版本：v1.34.5

set -e

echo "=== Longhorn 存储安装脚本 ==="
echo "日期：$(date)"
echo "目标版本：Longhorn v1.5.3"
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

# 检查 Longhorn 命名空间
if kubectl get namespace longhorn-system &>/dev/null; then
    echo "⚠️ Longhorn 命名空间已存在，可能已安装"
    read -p "是否继续安装？(y/n): " confirm
    if [ "$confirm" != "y" ]; then
        echo "取消安装"
        exit 0
    fi
fi

echo ""

# ========== 添加 Longhorn Helm 仓库 ==========

echo "添加 Longhorn Helm 仓库..."
helm repo add longhorn https://charts.longhorn.io
helm repo update
echo "✅ Helm 仓库已添加"

echo ""

# ========== 安装 Longhorn ==========

echo "安装 Longhorn v1.5.3..."

# 设置 Helm Chart 版本（版本锁定）
LONGHORN_CHART_VERSION="1.5.3"

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALUES_FILE="$SCRIPT_DIR/longhorn-values.yaml"

# 检查配置文件是否存在
if [ ! -f "$VALUES_FILE" ]; then
    echo "⚠️ 警告：longhorn-values.yaml 不存在，使用默认配置"
    helm install longhorn longhorn/longhorn \
        --namespace longhorn-system \
        --create-namespace \
        --version "$LONGHORN_CHART_VERSION"
else
    echo "使用配置文件：$VALUES_FILE"
    helm install longhorn longhorn/longhorn \
        --namespace longhorn-system \
        --create-namespace \
        -f "$VALUES_FILE" \
        --version "$LONGHORN_CHART_VERSION"
fi

echo "等待 Longhorn 部署..."
sleep 30

# ========== 验证安装 ==========

echo "验证 Longhorn 安装..."

# 检查 Pod 状态
kubectl get pods -n longhorn-system

# 等待所有 Pod 运行
echo "等待所有 Pod 运行..."
kubectl wait --for=condition=ready pod \
    --selector=app=longhorn-manager \
    --namespace=longhorn-system \
    --timeout=300s

kubectl wait --for=condition=ready pod \
    --selector=app=longhorn-ui \
    --namespace=longhorn-system \
    --timeout=300s

kubectl wait --for=condition=ready pod \
    --selector=app=longhorn-driver \
    --namespace=longhorn-system \
    --timeout=300s

# 检查存储类
echo "检查存储类..."
kubectl get storageclass

# 设置 Longhorn 为默认存储类
kubectl patch storageclass longhorn \
    -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

echo "✅ Longhorn 已设置为默认存储类"

# ========== 访问 Longhorn UI ==========

echo ""
echo "=== Longhorn UI 访问 ==="
echo "Ingress 配置：longhorn.local"
echo ""
echo "本地访问方法："
echo "  kubectl -n longhorn-system port-forward svc/longhorn-frontend 8080:80"
echo "  浏览器访问：http://localhost:8080"
echo ""

# ========== 安装完成摘要 ==========

echo "=== Longhorn 安装完成 ==="
echo "✅ Longhorn 版本：v1.5.3"
echo "✅ 存储类：longhorn (default)"
echo "✅ UI 访问：http://longhorn.local"
echo ""
echo "下一步：运行 Traefik 安装脚本"
echo "命令：./scripts/deployment/k3s/install-traefik.sh"
echo ""
echo "=== 安装完成 ✅ ==="
