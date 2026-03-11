#!/bin/bash
# K3S 集群健康检查脚本 - 多节点（Docker 容器）
# Story 0.4: K3S 集群部署（WSL2 多节点版）
# 技术栈：K3S v1.34.5 + Docker 容器

set -e

echo "=== K3S 集群健康检查 (多节点 Docker 版) ==="
echo "日期：$(date)"
echo ""

# ========== 配置 ==========

# 检查 kubectl
if ! command -v kubectl &>/dev/null; then
    echo "⚠️ kubectl 未找到，使用 docker exec..."
    KUBECTL_CMD="docker exec k3s-node-server-1 k3s kubectl"
else
    KUBECTL_CMD="kubectl"
fi

# ========== 1. 检查节点状态 ==========

echo "1. 检查节点状态..."
$KUBECTL_CMD get nodes -o wide

NODE_COUNT=$($KUBECTL_CMD get nodes --no-headers | wc -l)
READY_NODES=$($KUBECTL_CMD get nodes --no-headers | grep -c " Ready " || echo 0)

echo "节点统计：$READY_NODES/$NODE_COUNT 已就绪"

if [ "$READY_NODES" -ne "$NODE_COUNT" ]; then
    echo "❌ 有 $((NODE_COUNT - READY_NODES)) 个节点未就绪"
    exit 1
fi
echo "✅ 所有节点状态：Ready"
echo ""

# ========== 2. 检查系统 Pod ==========

echo "2. 检查系统 Pod..."
$KUBECTL_CMD get pods -n kube-system -o wide

SYSTEM_PODS=$($KUBECTL_CMD get pods -n kube-system --no-headers | grep -v Running | wc -l)
if [ "$SYSTEM_PODS" -ne 0 ]; then
    echo "❌ 有 $SYSTEM_PODS 个系统 Pod 未运行"
    $KUBECTL_CMD get pods -n kube-system --no-headers | grep -v Running
    exit 2
fi
echo "✅ 系统 Pod 全部 Running"
echo ""

# ========== 3. 检查存储类 ==========

echo "3. 检查存储类..."
$KUBECTL_CMD get storageclass

STORAGE_CLASS=$($KUBECTL_CMD get storageclass standard -o jsonpath='{.provisioner}' 2>/dev/null || echo "")
if [ "$STORAGE_CLASS" != "rancher.io/local-path" ]; then
    echo "❌ local-path-provisioner 未配置（当前：$STORAGE_CLASS）"
    exit 3
fi
echo "✅ local-path-provisioner 已配置"

# 检查默认存储类
DEFAULT_CLASS=$($KUBECTL_CMD get storageclass -o jsonpath='{.items[?(@.metadata.annotations.storageclass\.kubernetes\.io/is-default-class=="true")].metadata.name}' 2>/dev/null || echo "")
if [ "$DEFAULT_CLASS" = "standard" ]; then
    echo "✅ standard 是默认存储类"
else
    echo "⚠️ standard 不是默认存储类，当前默认：$DEFAULT_CLASS"
fi
echo ""

# ========== 4. 测试 PVC 创建 ==========

echo "4. 测试 PVC 创建..."
TEST_PVC_FILE="$(dirname "${BASH_SOURCE[0]}")/test-storage.yaml"

if [ -f "$TEST_PVC_FILE" ]; then
    echo "创建测试 PVC..."
    $KUBECTL_CMD apply -f "$TEST_PVC_FILE" 2>/dev/null || true

    echo "等待 PVC 绑定..."
    sleep 5

    PVC_STATUS=$($KUBECTL_CMD get pvc test-pvc -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
    if [ "$PVC_STATUS" = "Bound" ]; then
        echo "✅ PVC 创建成功"

        # 验证 Pod 是否能写入数据
        echo "验证存储写入..."
        sleep 3
        $KUBECTL_CMD wait --for=condition=ready pod test-storage-pod --timeout=60s 2>/dev/null || true
        $KUBECTL_CMD exec test-storage-pod -- sh -c "echo 'Multi-node storage test successful' > /data/test.txt" 2>/dev/null || true
        $KUBECTL_CMD exec test-storage-pod -- cat /data/test.txt 2>/dev/null || echo "⚠️ 无法写入测试数据"

        # 清理测试资源
        echo "清理测试资源..."
        $KUBECTL_CMD delete pod test-storage-pod verify-storage-pod 2>/dev/null || true
        $KUBECTL_CMD delete pvc test-pvc 2>/dev/null || true
        echo "✅ 测试资源已清理"
    else
        echo "⚠️ PVC 创建失败或未绑定（状态：$PVC_STATUS）"
        $KUBECTL_CMD describe pvc test-pvc 2>/dev/null || true
    fi
else
    echo "⚠️ 测试文件不存在：$TEST_PVC_FILE"
    echo "   跳过 PVC 测试"
fi
echo ""

# ========== 5. 检查 Traefik（如果已安装） ==========

echo "5. 检查 Traefik..."
if $KUBECTL_CMD get namespace traefik &>/dev/null; then
    echo "检查 Traefik Pod..."
    $KUBECTL_CMD get pods -n traefik -o wide

    TRAEFIKS=$($KUBECTL_CMD get pods -n traefik --no-headers | grep -v Running | wc -l)
    if [ "$TRAEFIKS" -ne 0 ]; then
        echo "❌ 有 $TRAEFIKS 个 Traefik Pod 未运行"
        $KUBECTL_CMD get pods -n traefik --no-headers | grep -v Running
        exit 4
    fi
    echo "✅ Traefik 全部 Running"

    # 检查 Traefik 服务
    TRAEFIK_SVC=$($KUBECTL_CMD get svc -n traefik traefik --no-headers 2>/dev/null || echo "")
    if [ -n "$TRAEFIK_SVC" ]; then
        echo "✅ Traefik 服务已配置"
        echo "   $TRAEFIK_SVC"
    fi

    # 检查 Ingress
    INGRESS_COUNT=$($KUBECTL_CMD get ingress --all-namespaces --no-headers 2>/dev/null | wc -l)
    if [ "$INGRESS_COUNT" -gt 0 ]; then
        echo "✅ 发现 $INGRESS_COUNT 个 Ingress"
    fi
else
    echo "⚠️ Traefik 命名空间不存在（可能还未安装）"
fi
echo ""

# ========== 6. 检查 Docker 容器 ==========

echo "6. 检查 Docker 容器..."
docker ps --filter "name=k3s-node" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

K3S_CONTAINERS=$(docker ps --filter "name=k3s-node" --no-trunc | grep -c "k3s-node" || echo 0)
RUNNING_CONTAINERS=$(docker ps --filter "name=k3s-node" --no-trunc | grep -c "Up " || echo 0)

echo "容器统计：$RUNNING_CONTAINERS/$K3S_CONTAINERS 运行中"

if [ "$RUNNING_CONTAINERS" -ne "$K3S_CONTAINERS" ]; then
    echo "⚠️ 有 $((K3S_CONTAINERS - RUNNING_CONTAINERS)) 个容器未运行"
fi
echo ""

# ========== 7. 集群诊断 ==========

echo "7. 集群诊断..."
echo "集群信息："
$KUBECTL_CMD cluster-info

echo ""
echo "节点资源使用情况："
$KUBECTL_CMD top nodes 2>/dev/null || echo "⚠️ metrics-server 未安装，无法查看资源使用情况"

echo ""
echo "Pod 资源使用情况："
$KUBECTL_CMD top pods --all-namespaces 2>/dev/null || echo "⚠️ metrics-server 未安装"

echo ""

# ========== 健康检查完成 ==========

echo "=== 健康检查通过 ✅ ==="
echo ""
echo "集群状态总结："
echo "  - K3S 集群：$NODE_COUNT 节点 Ready"
echo "  - 系统 Pod：全部 Running"
echo "  - 存储方案：local-path-provisioner (standard)"
echo "  - Docker 容器：$RUNNING_CONTAINERS/$K3S_CONTAINERS 运行中"
if $KUBECTL_CMD get namespace traefik &>/dev/null; then
    echo "  - Traefik 反向代理：已安装"
else
    echo "  - Traefik 反向代理：未安装"
fi
echo ""
echo "WSL2 多节点环境说明："
echo "  - 部署模式：单 WSL2 实例 + 多 Docker 容器节点"
echo "  - 网络：Docker k3s-network (172.30.0.0/16)"
echo "  - 存储：local-path-provisioner（每个节点独立存储）"
echo "  - 适用场景：开发/测试多节点功能"
echo ""

# 检查关键组件状态，给出明确退出码
FAILED=0

# 检查节点状态
if [ "$READY_NODES" -ne "$NODE_COUNT" ]; then
    echo "❌ 关键检查失败：有节点未就绪"
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
if $KUBECTL_CMD get namespace traefik &>/dev/null; then
    TRAEFIKS=$($KUBECTL_CMD get pods -n traefik --no-headers | grep -v Running | wc -l)
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
if ! $KUBECTL_CMD get namespace traefik &>/dev/null; then
    echo "  1. 安装 Traefik: sudo ./scripts/deployment/k3s/install-traefik-docker.sh"
fi
if $KUBECTL_CMD get namespace traefik &>/dev/null; then
    echo "  ✅ 所有组件已安装完成，可以开始部署应用"
fi

exit 0
