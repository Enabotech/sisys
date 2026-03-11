#!/bin/bash
# K3S 集群健康检查脚本 - WSL2 适配版
# Story 0.4: K3S 集群部署（WSL2 重构版）
# 技术栈：K3S v1.34.5 + local-path-provisioner

set -e

echo "=== K3S 集群健康检查 (WSL2 版) ==="
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
    exit 2
fi
echo "✅ 系统 Pod 全部 Running"
echo ""

# ========== 3. 检查存储类（local-path-provisioner） ==========

echo "3. 检查存储类..."
kubectl get storageclass

STORAGE_CLASS=$(kubectl get storageclass standard -o jsonpath='{.provisioner}' 2>/dev/null || echo "")
if [ "$STORAGE_CLASS" != "rancher.io/local-path" ]; then
    echo "❌ local-path-provisioner 未配置（当前：$STORAGE_CLASS）"
    exit 3
fi
echo "✅ local-path-provisioner 已配置（storageClassName: standard）"

# 检查默认存储类
DEFAULT_CLASS=$(kubectl get storageclass -o jsonpath='{.items[?(@.metadata.annotations.storageclass\.kubernetes\.io/is-default-class=="true")].metadata.name}' 2>/dev/null || echo "")
if [ "$DEFAULT_CLASS" = "standard" ]; then
    echo "✅ standard 是默认存储类"
else
    echo "⚠️ standard 不是默认存储类，当前默认：$DEFAULT_CLASS"
fi
echo ""

# ========== 4. 测试 PVC 创建（可选） ==========

echo "4. 测试 PVC 创建..."
TEST_PVC_FILE="$(dirname "${BASH_SOURCE[0]}")/test-storage.yaml"

if [ -f "$TEST_PVC_FILE" ]; then
    echo "创建测试 PVC..."
    kubectl apply -f "$TEST_PVC_FILE" 2>/dev/null || true

    echo "等待 PVC 绑定..."
    sleep 5

    PVC_STATUS=$(kubectl get pvc test-pvc -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
    if [ "$PVC_STATUS" = "Bound" ]; then
        echo "✅ PVC 创建成功"

        # 验证 Pod 是否能写入数据
        echo "验证存储写入..."
        sleep 3
        kubectl wait --for=condition=ready pod test-storage-pod --timeout=60s 2>/dev/null || true
        kubectl exec test-storage-pod -- sh -c "echo 'WSL2 storage test successful' > /data/test.txt" 2>/dev/null || true
        kubectl exec test-storage-pod -- cat /data/test.txt 2>/dev/null || echo "⚠️ 无法写入测试数据"

        # 清理测试资源
        echo "清理测试资源..."
        kubectl delete pod test-storage-pod verify-storage-pod 2>/dev/null || true
        kubectl delete pvc test-pvc 2>/dev/null || true
        echo "✅ 测试资源已清理"
    else
        echo "⚠️ PVC 创建失败或未绑定（状态：$PVC_STATUS）"
        kubectl describe pvc test-pvc 2>/dev/null || true
    fi
else
    echo "⚠️ 测试文件不存在：$TEST_PVC_FILE"
    echo "   跳过 PVC 测试"
fi
echo ""

# ========== 5. 检查 Traefik（如果已安装） ==========

echo "5. 检查 Traefik..."
if kubectl get namespace traefik &>/dev/null; then
    echo "检查 Traefik Pod..."
    kubectl get pods -n traefik

    TRAEFIKS=$(kubectl get pods -n traefik --no-headers | grep -v Running | wc -l)
    if [ "$TRAEFIKS" -ne 0 ]; then
        echo "❌ 有 $TRAEFIKS 个 Traefik Pod 未运行"
        kubectl get pods -n traefik --no-headers | grep -v Running
        exit 4
    fi
    echo "✅ Traefik 全部 Running"

    # 检查 Traefik 服务
    TRAEFIK_SVC=$(kubectl get svc -n traefik traefik --no-headers 2>/dev/null || echo "")
    if [ -n "$TRAEFIK_SVC" ]; then
        echo "✅ Traefik 服务已配置"
        echo "   $TRAEFIK_SVC"
    fi

    # 检查 Ingress
    INGRESS_COUNT=$(kubectl get ingress --all-namespaces --no-headers 2>/dev/null | wc -l)
    if [ "$INGRESS_COUNT" -gt 0 ]; then
        echo "✅ 发现 $INGRESS_COUNT 个 Ingress"
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
echo "  - 存储方案：local-path-provisioner (standard)"
if kubectl get namespace traefik &>/dev/null; then
    echo "  - Traefik 反向代理：已安装"
else
    echo "  - Traefik 反向代理：未安装"
fi
echo ""
echo "WSL2 环境说明："
echo "  - 存储类型：hostPath（绑定到 WSL2 VHDX 虚拟磁盘）"
echo "  - 适用场景：开发/测试环境"
echo "  - 生产环境：建议迁移到 NFS/Ceph 等分布式存储"
echo ""

# 检查关键组件状态，给出明确退出码
FAILED=0

# 检查 K3S 节点状态
if [ "$NODE_STATUS" != "True" ]; then
    echo "❌ 关键检查失败：K3S 节点未就绪"
    FAILED=1
fi

# 检查系统 Pod
if [ "$SYSTEM_PODS" -ne 0 ]; then
    echo "❌ 关键检查失败：有 $SYSTEM_PODS 个系统 Pod 未运行"
    FAILED=2
fi

# 检查存储类
if [ "$STORAGE_CLASS" != "rancher.io/local-path" ]; then
    echo "❌ 关键检查失败：local-path-provisioner 未配置"
    FAILED=3
fi

# 如果 Traefik 命名空间存在但 Pod 未运行，报告失败
if kubectl get namespace traefik &>/dev/null; then
    TRAEFIKS=$(kubectl get pods -n traefik --no-headers | grep -v Running | wc -l)
    if [ "$TRAEFIKS" -ne 0 ]; then
        echo "❌ 关键检查失败：有 $TRAEFIKS 个 Traefik Pod 未运行"
        FAILED=4
    fi
fi

# 根据检查结果退出
if [ "$FAILED" -ne 0 ]; then
    echo ""
    echo "❌ 健康检查失败（退出码：$FAILED）"
    echo "   1=节点未就绪，2=系统 Pod 异常，3=存储配置异常，4=Traefik 异常"
    exit $FAILED
fi

echo "下一步："
if ! kubectl get namespace traefik &>/dev/null; then
    echo "  1. 安装 Traefik：./scripts/deployment/k3s/install-traefik.sh"
fi
if kubectl get namespace traefik &>/dev/null; then
    echo "  ✅ 所有组件已安装完成，可以开始部署应用"
fi

exit 0
