#!/bin/bash
# K3S 集群健康检查脚本
# Story 0.4: K3S 集群部署
# 验证：K3S/Longhorn/Traefik 状态

set -e

echo "=== K3S 集群健康检查 ==="
echo "日期：$(date)"
echo ""

# ========== 1. 检查节点状态 ==========

echo "1. 检查节点状态..."
kubectl get nodes

NODE_STATUS=$(kubectl get nodes -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}')
if [ "$NODE_STATUS" != "True" ]; then
    echo "❌ 节点未就绪"
    exit 1
fi
echo "✅ 节点状态：Ready"
echo ""

# ========== 2. 检查系统 Pod ==========

echo "2. 检查系统 Pod..."
kubectl get pods -n kube-system

SYSTEM_PODS=$(kubectl get pods -n kube-system --no-headers | grep -v Running | wc -l)
if [ "$SYSTEM_PODS" -ne 0 ]; then
    echo "❌ 有 $SYSTEM_PODS 个系统 Pod 未运行"
    kubectl get pods -n kube-system --no-headers | grep -v Running
    exit 1
fi
echo "✅ 系统 Pod 全部 Running"
echo ""

# ========== 3. 检查存储类 ==========

echo "3. 检查存储类..."
kubectl get storageclass

LONGHORN_DEFAULT=$(kubectl get storageclass longhorn -o jsonpath='{.metadata.annotations.storageclass\.kubernetes\.io/is-default-class}' 2>/dev/null || echo "")
if [ "$LONGHORN_DEFAULT" != "true" ]; then
    echo "⚠️ Longhorn 不是默认存储类（可能还未安装 Longhorn）"
else
    echo "✅ Longhorn 存储类已配置为默认"
fi
echo ""

# ========== 4. 检查 Longhorn（如果已安装） ==========

echo "4. 检查 Longhorn..."
if kubectl get namespace longhorn-system &>/dev/null; then
    kubectl get pods -n longhorn-system

    LONGHORNS=$(kubectl get pods -n longhorn-system --no-headers | grep -v Running | wc -l)
    if [ "$LONGHORNS" -ne 0 ]; then
        echo "❌ 有 $LONGHORNS 个 Longhorn Pod 未运行"
        kubectl get pods -n longhorn-system --no-headers | grep -v Running
        exit 1
    fi
    echo "✅ Longhorn 全部 Running"

    # 检查 Longhorn UI
    if kubectl get ingress -n longhorn-system longhorn-ingress &>/dev/null; then
        echo "✅ Longhorn UI Ingress 已配置"
        echo "   访问地址：http://longhorn.local"
    fi
else
    echo "⚠️ Longhorn 命名空间不存在（可能还未安装）"
fi
echo ""

# ========== 5. 检查 Traefik（如果已安装） ==========

echo "5. 检查 Traefik..."
if kubectl get namespace traefik &>/dev/null; then
    kubectl get pods -n traefik

    TRAEFIKS=$(kubectl get pods -n traefik --no-headers | grep -v Running | wc -l)
    if [ "$TRAEFIKS" -ne 0 ]; then
        echo "❌ 有 $TRAEFIKS 个 Traefik Pod 未运行"
        kubectl get pods -n traefik --no-headers | grep -v Running
        exit 1
    fi
    echo "✅ Traefik 全部 Running"

    # 检查 Traefik 服务
    TRAEFIK_SVC=$(kubectl get svc -n traefik traefik --no-headers 2>/dev/null || echo "")
    if [ -n "$TRAEFIK_SVC" ]; then
        echo "✅ Traefik 服务已配置"
        echo "   $TRAEFIK_SVC"
    fi
else
    echo "⚠️ Traefik 命名空间不存在（可能还未安装）"
fi
echo ""

# ========== 6. 集群诊断 ==========

echo "6. 集群诊断..."
echo "集群信息："
kubectl cluster-info

echo ""
echo "节点资源使用情况："
kubectl top nodes 2>/dev/null || echo "⚠️ metrics-server 未安装，无法查看资源使用情况"

echo ""
echo "Pod 资源使用情况："
kubectl top pods --all-namespaces 2>/dev/null || echo "⚠️ metrics-server 未安装"

echo ""

# ========== 健康检查完成 ==========

echo "=== 健康检查通过 ✅ ==="
echo ""
echo "集群状态总结："
echo "  - K3S 集群：Ready"
echo "  - 系统 Pod：全部 Running"
if [ "$LONGHORN_DEFAULT" = "true" ]; then
    echo "  - Longhorn 存储：已配置（默认存储类）"
else
    echo "  - Longhorn 存储：未安装"
fi
if kubectl get namespace traefik &>/dev/null; then
    echo "  - Traefik 反向代理：已安装"
else
    echo "  - Traefik 反向代理：未安装"
fi
echo ""
echo "下一步："
if [ "$LONGHORN_DEFAULT" != "true" ]; then
    echo "  1. 安装 Longhorn：./scripts/deployment/k3s/install-longhorn.sh"
fi
if ! kubectl get namespace traefik &>/dev/null; then
    echo "  2. 安装 Traefik：./scripts/deployment/k3s/install-traefik.sh"
fi
if [ "$LONGHORN_DEFAULT" = "true" ] && kubectl get namespace traefik &>/dev/null; then
    echo "  ✅ 所有组件已安装完成，可以开始部署应用"
fi
