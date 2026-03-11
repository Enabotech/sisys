#!/bin/bash
# K3S 安装脚本 - 针对 13700K + 32G RAM + 1T SSD + 10T HDD 优化
# Story 0.4: K3S 集群部署
# 技术栈：K3S v1.34.5

set -e

echo "=== K3S 集群安装脚本 ==="
echo "日期：$(date)"
echo "目标版本：K3S v1.34.5"
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

# 检查 Longhorn 数据目录空间（重要！）
if df -h /var/lib/longhorn &>/dev/null; then
    LONGHORN_SPACE=$(df -h /var/lib/longhorn | awk 'NR==2 {print $4}')
    echo "✅ Longhorn 数据目录可用空间：$LONGHORN_SPACE"
else
    echo "⚠️ 警告：/var/lib/longhorn 未独立挂载，将使用根分区空间"
fi

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

echo "下载并安装 K3S v1.34.5..."

# 设置 K3S 版本
export INSTALL_K3S_VERSION="v1.34.5+k3s1"

# 下载并运行安装脚本（带重试机制）
echo "下载 K3S 安装脚本（最多重试 3 次）..."
if ! curl --retry 3 --retry-delay 5 --retry-max-time 60 -sfL https://get.k3s.io -o /tmp/k3s-install.sh; then
    echo "❌ 下载 K3S 安装脚本失败"
    exit 1
fi
echo "✅ K3S 安装脚本下载成功"

# 执行安装脚本
echo "执行 K3S 安装..."
if ! INSTALL_K3S_VERSION=$INSTALL_K3S_VERSION sh /tmp/k3s-install.sh; then
    echo "❌ K3S 安装失败"
    rm -f /tmp/k3s-install.sh
    exit 1
fi

# 清理临时文件
rm -f /tmp/k3s-install.sh

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

# 部署 K3S 配置文件（重要！）
echo "部署 K3S 配置文件..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.yaml"

if [ -f "$CONFIG_FILE" ]; then
    echo "复制配置文件到 /etc/rancher/k3s/config.yaml..."
    mkdir -p /etc/rancher/k3s

    # 备份现有配置（如果存在）
    if [ -f /etc/rancher/k3s/config.yaml ]; then
        cp /etc/rancher/k3s/config.yaml /etc/rancher/k3s/config.yaml.bak.$(date +%Y%m%d%H%M%S)
        echo "✅ 已备份现有配置"
    fi

    # 复制新配置
    cp "$CONFIG_FILE" /etc/rancher/k3s/config.yaml
    chmod 600 /etc/rancher/k3s/config.yaml
    echo "✅ K3S 配置文件已部署"

    # 重启 K3S 服务使配置生效
    echo "重启 K3S 服务使配置生效..."
    systemctl restart k3s
    sleep 10

    # 验证重启后状态
    if systemctl is-active --quiet k3s; then
        echo "✅ K3S 服务重启成功，配置已生效"
    else
        echo "❌ K3S 服务重启失败"
        systemctl status k3s
        exit 1
    fi
else
    echo "⚠️ 警告：config.yaml 不存在，使用默认配置"
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
