#!/bin/bash
# K3S 安装脚本 - 针对 13700K + 32G RAM + 1T SSD + 10T HDD 优化
# Story 0.4: K3S 集群部署
# 技术栈：K3S v1.28.x

set -e

echo "=== K3S 集群安装脚本 ==="
echo "日期：$(date)"
echo "目标版本：K3S v1.28.x"
echo ""

# ========== 前置检查 ==========

echo "检查前置条件..."

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请以 root 用户运行此脚本（使用 sudo）"
    exit 1
fi

# 检查操作系统
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "✅ 操作系统：$NAME $VERSION"
else
    echo "⚠️ 无法识别操作系统"
fi

# 检查内存
TOTAL_MEM=$(free -g | awk '/^Mem:/{print $2}')
echo "✅ 系统内存：${TOTAL_MEM}GB"
if [ "$TOTAL_MEM" -lt 16 ]; then
    echo "⚠️ 警告：内存小于 16GB，可能影响性能"
fi

# 检查磁盘空间
ROOT_SPACE=$(df -h / | awk 'NR==2 {print $4}')
echo "✅ 根分区可用空间：$ROOT_SPACE"

# 检查端口占用
echo "检查端口占用..."
for port in 6443 80 443; do
    if netstat -tlnp 2>/dev/null | grep -q ":$port "; then
        echo "⚠️ 警告：端口 $port 被占用"
    else
        echo "✅ 端口 $port 可用"
    fi
done

echo ""

# ========== 安装 K3S ==========

echo "下载并安装 K3S v1.28.x..."

# 设置 K3S 版本
export INSTALL_K3S_VERSION="v1.28.15+k3s1"

# 下载并运行安装脚本
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=$INSTALL_K3S_VERSION sh -

# 等待 K3S 启动
echo "等待 K3S 服务启动..."
sleep 10

# 验证 K3S 状态
echo "验证 K3S 状态..."
if systemctl is-active --quiet k3s; then
    echo "✅ K3S 服务运行正常"
else
    echo "❌ K3S 服务未运行"
    systemctl status k3s
    exit 1
fi

# 配置 kubectl 别名
if ! grep -q "alias kubectl='sudo kubectl'" /root/.bashrc 2>/dev/null; then
    echo "alias kubectl='sudo kubectl'" >> /root/.bashrc
    echo "✅ 已添加 kubectl 别名到 /root/.bashrc"
fi

# 为普通用户配置 kubectl
if [ -n "$SUDO_USER" ]; then
    USER_HOME=$(eval echo ~$SUDO_USER)
    if [ -f /etc/rancher/k3s/k3s.yaml ]; then
        mkdir -p "$USER_HOME/.kube"
        cp /etc/rancher/k3s/k3s.yaml "$USER_HOME/.kube/config"
        chown -R $SUDO_USER:$SUDO_USER "$USER_HOME/.kube"
        echo "✅ 已配置用户 kubectl 配置"
    fi
fi

echo ""

# ========== 验证集群 ==========

echo "验证 K3S 集群..."

# 检查节点状态
echo "检查节点状态..."
kubectl get nodes

NODE_STATUS=$(kubectl get nodes -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}')
if [ "$NODE_STATUS" = "True" ]; then
    echo "✅ 节点状态：Ready"
else
    echo "❌ 节点未就绪"
    exit 1
fi

# 检查 K3S 版本
K3S_VERSION=$(kubectl get nodes -o jsonpath='{.items[0].status.nodeInfo.kubeletVersion}')
echo "✅ K3S 版本：$K3S_VERSION"

# 检查系统 Pod
echo "检查系统 Pod..."
kubectl get pods -n kube-system

SYSTEM_PODS=$(kubectl get pods -n kube-system --no-headers | grep -v Running | wc -l)
if [ "$SYSTEM_PODS" -eq 0 ]; then
    echo "✅ 所有系统 Pod 运行正常"
else
    echo "⚠️ 有 $SYSTEM_PODS 个系统 Pod 未运行"
fi

echo ""

# ========== 安装完成摘要 ==========

echo "=== K3S 安装完成 ==="
echo "✅ K3S 版本：$K3S_VERSION"
echo "✅ 节点状态：Ready"
echo "✅ 系统 Pod：运行正常"
echo ""
echo "下一步：运行 Longhorn 存储配置脚本"
echo "命令：./scripts/deployment/k3s/install-longhorn.sh"
echo ""
echo "=== 安装完成 ✅ ==="
