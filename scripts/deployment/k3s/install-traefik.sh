#!/bin/bash
# Traefik 反向代理安装脚本 - WSL2 适配版
# Story 0.4: K3S 集群部署（WSL2 重构版）
# 技术栈：Traefik v3.x (Helm Chart 39.0.5+)
# K3S 版本：v1.34.5
# 环境：WSL2 Ubuntu 22.04

# 错误处理配置
TRAEFIK_FAILED=0
TRAEFIK_ERROR_REASON=""

# 错误处理函数
error_handler() {
    local line_number=$1
    echo ""
    echo "❌ 脚本执行失败于第 $line_number 行"
    echo "   退出码：$TRAEFIK_FAILED"
    echo "   原因：$TRAEFIK_ERROR_REASON"
    echo ""
    echo "故障排除建议："
    echo "  1. 检查 Helm 状态：helm list -n traefik"
    echo "  2. 查看 Traefik Pod：kubectl get pods -n traefik"
    echo "  3. 查看 Pod 日志：kubectl logs -n traefik -l app.kubernetes.io/name=traefik"
    echo "  4. 检查事件：kubectl get events -n traefik --sort-by='.lastTimestamp'"
    exit $TRAEFIK_FAILED
}

trap 'error_handler $LINENO' ERR

echo "=== Traefik 反向代理安装脚本 ==="
echo "日期：$(date)"
echo "目标版本：Traefik v3.x"
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

echo "安装 Traefik v3.x..."

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALUES_FILE="$SCRIPT_DIR/traefik-values.yaml"

# 检查配置文件
if [ ! -f "$VALUES_FILE" ]; then
    echo "⚠️ 警告：traefik-values.yaml 不存在，使用默认配置"
    VALUES_FILE=""
fi

# 动态获取最新稳定版本（避免硬编码版本号）
echo "准备 Helm Chart..."
echo "获取最新 Traefik Chart 版本..."

# 从 Helm 仓库获取最新版本
TRAEFIK_VERSION=$(helm search repo traefik/traefik --versions 2>/dev/null | grep "^traefik/traefik" | head -1 | awk '{print $2}')

if [ -z "$TRAEFIK_VERSION" ]; then
    echo "⚠️ 无法获取最新版本，使用备用方案..."
    # 备用方案：直接从 GitHub 获取 releases
    TRAEFIK_VERSION=$(curl -s https://api.github.com/repos/traefik/traefik-helm-chart/releases/latest 2>/dev/null | grep '"tag_name"' | cut -d'"' -f4 | sed 's/^traefik-//')
fi

if [ -z "$TRAEFIK_VERSION" ]; then
    echo "❌ 无法获取 Traefik 版本，使用默认版本：39.0.5"
    TRAEFIK_VERSION="39.0.5"
fi

echo "✅ 使用 Traefik Chart 版本：$TRAEFIK_VERSION"

# 使用 helm install 直接安装（推荐方式，无需手动下载）
echo "使用 Helm 安装 Traefik..."
if [ -n "$VALUES_FILE" ]; then
    echo "使用配置文件：$VALUES_FILE"
    helm install traefik traefik/traefik \
        --namespace traefik \
        --create-namespace \
        --version "$TRAEFIK_VERSION" \
        -f "$VALUES_FILE"
else
    helm install traefik traefik/traefik \
        --namespace traefik \
        --create-namespace \
        --version "$TRAEFIK_VERSION"
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
