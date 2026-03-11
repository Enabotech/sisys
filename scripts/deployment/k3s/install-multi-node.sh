#!/bin/bash
# K3S 多节点集群部署脚本 - 单 WSL2 实例
# Story 0.4: K3S 集群部署（WSL2 多节点版）
# 技术栈：K3S v1.34.5 + Docker 容器运行多节点

set -e

echo "=== K3S 多节点集群部署脚本 (WSL2 单实例) ==="
echo "日期：$(date)"
echo "目标版本：K3S v1.34.5"
echo "部署模式：单 WSL2 实例 + 多 Docker 容器节点"
echo ""

# ========== 配置参数 ==========

# 节点数量配置
SERVER_NODES=1
AGENT_NODES=2
TOTAL_NODES=$((SERVER_NODES + AGENT_NODES))

# 网络配置
POD_CIDR="10.42.0.0/16"
SERVICE_CIDR="10.43.0.0/16"
CLUSTER_DNS="10.43.0.10"

# 节点配置
NODE_PREFIX="k3s-node"
K3S_VERSION="v1.34.5+k3s1"
TOKEN="k3s-multi-node-token-2026"

# ========== 前置检查 ==========

echo "检查前置条件..."

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请以 root 用户运行此脚本（使用 sudo）"
    exit 1
fi

# 检查 Docker 是否安装
if ! command -v docker &>/dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    echo "   安装命令：curl -fsSL https://get.docker.com | sh"
    exit 1
fi
echo "✅ Docker 已安装：$(docker --version)"

# 检查 Docker 是否运行
if ! docker info &>/dev/null; then
    echo "❌ Docker 服务未运行"
    exit 1
fi
echo "✅ Docker 服务运行正常"

# 检查 K3S 是否已安装（用于 kubectl 命令）
if ! command -v kubectl &>/dev/null; then
    echo "⚠️ kubectl 未安装，将在第一个节点创建后使用 docker exec"
fi

# 检查端口占用
echo "检查端口占用..."
for port in 6443 8443; do
    if ss -tlnp 2>/dev/null | grep -q ":$port " || netstat -tlnp 2>/dev/null | grep -q ":$port "; then
        echo "⚠️ 警告：端口 $port 被占用"
    else
        echo "✅ 端口 $port 可用"
    fi
done

echo ""

# ========== 清理旧集群（如果存在） ==========

echo "检查是否存在旧集群..."
EXISTING_NODES=$(docker ps -a --filter "name=${NODE_PREFIX}" --format "{{.Names}}" | wc -l)
if [ "$EXISTING_NODES" -gt 0 ]; then
    echo "⚠️ 发现 $EXISTING_NODES 个旧节点"
    read -p "是否删除旧节点并重新部署？(y/n): " confirm
    if [ "$confirm" = "y" ]; then
        echo "删除旧节点..."
        docker rm -f $(docker ps -a --filter "name=${NODE_PREFIX}" --format "{{.Names}}") 2>/dev/null || true
        echo "✅ 旧节点已清理"
    else
        echo "取消部署"
        exit 0
    fi
fi

echo ""

# ========== 创建 Docker 网络 ==========

echo "创建 Docker 网络..."
if ! docker network inspect k3s-network &>/dev/null; then
    docker network create \
        --driver bridge \
        --subnet=172.30.0.0/16 \
        --gateway=172.30.0.1 \
        k3s-network
    echo "✅ Docker 网络已创建：k3s-network (172.30.0.0/16)"
else
    echo "✅ Docker 网络已存在：k3s-network"
fi

echo ""

# ========== 部署 Server 节点 ==========

echo "部署 K3S Server 节点..."

for i in $(seq 1 $SERVER_NODES); do
    NODE_NAME="${NODE_PREFIX}-server-$i"
    NODE_IP="172.30.0.$((10 + i))"

    echo "创建 Server 节点：$NODE_NAME ($NODE_IP)..."

    docker run -d \
        --name $NODE_NAME \
        --hostname $NODE_NAME \
        --net k3s-network \
        --ip $NODE_IP \
        --privileged \
        -e K3S_TOKEN=$TOKEN \
        -e K3S_KUBECONFIG_OUTPUT=/output/kubeconfig.yaml \
        -v ${NODE_NAME}-data:/var/lib/rancher/k3s \
        -v ${NODE_NAME}-output:/output \
        --tmpfs /run \
        --tmpfs /var/run \
        -p 6443:6443 \
        -p 80:80 \
        -p 443:443 \
        rancher/k3s:${K3S_VERSION} server \
        --cluster-init \
        --token $TOKEN \
        --node-ip $NODE_IP \
        --node-external-ip $NODE_IP \
        --flannel-backend=none \
        --disable-network-policy \
        --disable=servicelb \
        --disable=traefik \
        --disable=metrics-server \
        --cluster-cidr $POD_CIDR \
        --service-cidr $SERVICE_CIDR \
        --cluster-dns $CLUSTER_DNS \
        --node-name $NODE_NAME

    echo "✅ Server 节点已创建：$NODE_NAME"
done

# 等待 Server 节点启动
echo "等待 Server 节点启动..."
sleep 15

# 检查 Server 节点状态
echo "检查 Server 节点状态..."
docker exec ${NODE_PREFIX}-server-1 k3s kubectl get nodes

echo ""

# ========== 部署 Agent 节点 ==========

echo "部署 K3S Agent 节点..."

SERVER_IP="172.30.0.10"

for i in $(seq 1 $AGENT_NODES); do
    NODE_NAME="${NODE_PREFIX}-agent-$i"
    NODE_IP="172.30.0.$((20 + i))"

    echo "创建 Agent 节点：$NODE_NAME ($NODE_IP)..."

    docker run -d \
        --name $NODE_NAME \
        --hostname $NODE_NAME \
        --net k3s-network \
        --ip $NODE_IP \
        --privileged \
        -e K3S_TOKEN=$TOKEN \
        -v ${NODE_NAME}-data:/var/lib/rancher/k3s \
        --tmpfs /run \
        --tmpfs /var/run \
        rancher/k3s:${K3S_VERSION} agent \
        --server https://$SERVER_IP:6443 \
        --token $TOKEN \
        --node-ip $NODE_IP \
        --node-name $NODE_NAME

    echo "✅ Agent 节点已创建：$NODE_NAME"
done

# 等待 Agent 节点启动
echo "等待 Agent 节点启动..."
sleep 10

echo ""

# ========== 验证集群 ==========

echo "验证 K3S 集群..."

# 获取 kubeconfig
echo "获取 kubeconfig..."
docker exec ${NODE_PREFIX}-server-1 cat /output/kubeconfig.yaml > /tmp/k3s-kubeconfig.yaml 2>/dev/null || \
    docker exec ${NODE_PREFIX}-server-1 k3s kubectl config view --raw > /tmp/k3s-kubeconfig.yaml

# 检查节点状态
echo "检查节点状态..."
docker exec ${NODE_PREFIX}-server-1 k3s kubectl get nodes -o wide

# 等待所有节点 Ready
echo "等待所有节点 Ready..."
READY_NODES=0
MAX_RETRIES=12
RETRY_COUNT=0

while [ $READY_NODES -lt $TOTAL_NODES ] && [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    sleep 5
    READY_NODES=$(docker exec ${NODE_PREFIX}-server-1 k3s kubectl get nodes --no-headers | grep -c " Ready " || echo 0)
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "  第 $RETRY_COUNT 次检查：$READY_NODES/$TOTAL_NODES 节点已就绪..."
done

if [ $READY_NODES -eq $TOTAL_NODES ]; then
    echo "✅ 所有节点已就绪"
else
    echo "⚠️ 超时：$READY_NODES/$TOTAL_NODES 节点已就绪"
fi

# 检查系统 Pod
echo "检查系统 Pod..."
docker exec ${NODE_PREFIX}-server-1 k3s kubectl get pods -n kube-system -o wide

# 检查存储类
echo "检查存储类..."
docker exec ${NODE_PREFIX}-server-1 k3s kubectl get storageclass

echo ""

# ========== 配置本地 kubectl（可选） ==========

echo "配置本地 kubectl..."
KUBECONFIG_DIR="$HOME/.kube"
if [ ! -d "$KUBECONFIG_DIR" ]; then
    mkdir -p "$KUBECONFIG_DIR"
fi

# 备份现有配置
if [ -f "$KUBECONFIG_DIR/config" ]; then
    cp "$KUBECONFIG_DIR/config" "$KUBECONFIG_DIR/config.bak.$(date +%Y%m%d%H%M%S)"
fi

# 更新 kubeconfig 中的服务器地址
sed -i 's|https://127.0.0.1:6443|https://172.30.0.10:6443|g' /tmp/k3s-kubeconfig.yaml
cp /tmp/k3s-kubeconfig.yaml "$KUBECONFIG_DIR/config"
chown $SUDO_USER:$SUDO_USER "$KUBECONFIG_DIR/config" 2>/dev/null || true

echo "✅ kubectl 配置已更新"
echo "   测试命令：kubectl get nodes"

echo ""

# ========== 部署完成摘要 ==========

echo "=== K3S 多节点集群部署完成 ==="
echo "✅ Server 节点：$SERVER_NODES"
echo "✅ Agent 节点：$AGENT_NODES"
echo "✅ 总节点数：$TOTAL_NODES"
echo "✅ K3S 版本：$K3S_VERSION"
echo "✅ 网络：Docker k3s-network (172.30.0.0/16)"
echo ""
echo "节点信息:"
echo "  Server:"
for i in $(seq 1 $SERVER_NODES); do
    echo "    - ${NODE_PREFIX}-server-$i (172.30.0.$((10 + i)))"
done
echo "  Agent:"
for i in $(seq 1 $AGENT_NODES); do
    echo "    - ${NODE_PREFIX}-agent-$i (172.30.0.$((20 + i)))"
done
echo ""
echo "管理命令:"
echo "  kubectl get nodes                    # 查看节点"
echo "  kubectl get pods -A                  # 查看所有 Pod"
echo "  docker ps | grep k3s-node            # 查看容器"
echo ""
echo "访问 Traefik（安装后）:"
echo "  kubectl port-forward -n traefik svc/traefik 8080:80"
echo "  浏览器访问：http://localhost:8080"
echo ""
echo "下一步:"
echo "  1. 安装 Traefik: sudo ./scripts/deployment/k3s/install-traefik-docker.sh"
echo "  2. 运行健康检查：sudo ./scripts/deployment/k3s/health_check_docker.sh"
echo ""
echo "=== 部署完成 ✅ ==="
