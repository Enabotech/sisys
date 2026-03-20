#!/bin/bash
# ============================================================
# Gitea TLS CA 证书提取和配置脚本
# ============================================================
# 用途：从 Traefik 或浏览器获取 Gitea 的 TLS CA 证书
#       并配置到 Gitea Runner 中
# ============================================================

set -e

NAMESPACE="gitea-actions"
GITEA_NAMESPACE="gitea"
CA_CONFIGMAP="gitea-tls-ca"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║         Gitea TLS CA 证书配置脚本                        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# 方法 1: 从 Traefik Secret 获取证书
echo "📋 方法 1: 从 Traefik Secret 获取证书"
echo "   请提供 Traefik TLS Secret 名称和命名空间"
echo ""
read -p "Traefik TLS Secret 名称 [gitea-tls]: " TRAEFIK_SECRET
TRAEFIK_SECRET=${TRAEFIK_SECRET:-gitea-tls}

read -p "Traefik 命名空间 [traefik]: " TRAEFIK_NS
TRAEFIK_NS=${TRAEFIK_NS:-traefik}

echo ""
echo "🔍 尝试从 Traefik Secret 获取证书..."
if kubectl get secret "$TRAEFIK_SECRET" -n "$TRAEFIK_NS" &>/dev/null; then
    kubectl get secret "$TRAEFIK_SECRET" -n "$TRAEFIK_NS" \
        -o jsonpath='{.data.tls\.crt}' | base64 -d > /tmp/gitea-ca.crt
    echo "✅ 证书已提取到 /tmp/gitea-ca.crt"
else
    echo "❌ 未找到 Traefik Secret，请使用方法 2"
fi

# 方法 2: 手动提供证书
echo ""
echo "📋 方法 2: 手动提供证书文件"
echo "   从浏览器导出证书或提供证书文件路径"
echo ""
read -p "证书文件路径 [/tmp/gitea-ca.crt]: " CERT_PATH
CERT_PATH=${CERT_PATH:-/tmp/gitea-ca.crt}

if [ ! -f "$CERT_PATH" ]; then
    echo "⚠️  证书文件不存在，请从浏览器导出："
    echo "   1. 访问 https://gitea.sisys.local"
    echo "   2. 点击地址栏锁图标"
    echo "   3. 导出证书为 PEM 格式"
    echo "   4. 保存为 $CERT_PATH"
    exit 1
fi

# 创建 ConfigMap
echo ""
echo "📦 创建 ConfigMap: $CA_CONFIGMAP"
kubectl create configmap "$CA_CONFIGMAP" \
    --from-file=ca.crt="$CERT_PATH" \
    -n "$NAMESPACE" \
    --dry-run=client -o yaml | kubectl apply -f -

echo "✅ ConfigMap 创建成功"

# 验证
echo ""
echo "🔍 验证 ConfigMap..."
kubectl get configmap "$CA_CONFIGMAP" -n "$NAMESPACE" -o yaml | head -20

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  下一步：更新 gitea-runner.yaml 挂载 CA 证书              ║"
echo "╚══════════════════════════════════════════════════════════╝"
