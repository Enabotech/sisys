#!/bin/bash
# =============================================================================
# K3S VPN 代理配置脚本 - WSL2 + Windows VPN 环境
# =============================================================================
# 用途：自动化配置 WSL2 使用 Windows VPN 代理，同时让 k3s 容器流量直连
# 环境：WSL2 Ubuntu 22.04 + K3S v1.34.5
# 用法：sudo bash scripts/setup-k3s-proxy.sh
# =============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
WINDOWS_HOST=$(grep nameserver /etc/resolv.conf | awk '{print $2}')
PROXY_PORT="${PROXY_PORT:-7890}"  # 可通过环境变量修改
POD_CIDR="10.42.0.0/16"
SERVICE_CIDR="10.43.0.0/16"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检测 Windows 主机连通性
check_windows_host() {
    log_info "检测 Windows 主机连通性..."
    if ping -c 2 -W 2 "$WINDOWS_HOST" > /dev/null 2>&1; then
        log_success "Windows 主机可达：$WINDOWS_HOST"
    else
        log_warning "无法 ping 通 Windows 主机：$WINDOWS_HOST"
        log_warning "请确保 Windows 防火墙允许 ICMP 回显"
    fi
}

# 检测代理端口
check_proxy_port() {
    log_info "检测代理端口 ${PROXY_PORT}..."
    if timeout 2 bash -c "cat < /dev/null > /dev/tcp/$WINDOWS_HOST/$PROXY_PORT" 2>/dev/null; then
        log_success "代理端口 ${PROXY_PORT} 可达"
    else
        log_warning "代理端口 ${PROXY_PORT} 不可达"
        log_warning "请确认："
        log_warning "  1. Windows 代理软件已启动"
        log_warning "  2. 代理端口设置为 $PROXY_PORT"
        log_warning "  3. Windows 防火墙允许该端口"
        log_warning ""
        read -p "是否继续配置？[y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# 配置 WSL 主机代理环境变量
configure_host_proxy() {
    log_info "配置 WSL 主机代理环境变量..."

    local proxy_config="/etc/profile.d/k3s-proxy.sh"

    sudo tee "$proxy_config" > /dev/null << EOF
# K3S VPN 代理配置 - WSL2 + Windows
# 自动生成于：$(date)

WINDOWS_HOST="${WINDOWS_HOST}"
PROXY_PORT="${PROXY_PORT}"

# 代理环境变量
export HTTP_PROXY="http://\${WINDOWS_HOST}:\${PROXY_PORT}"
export HTTPS_PROXY="http://\${WINDOWS_HOST}:\${PROXY_PORT}"
export FTP_PROXY="http://\${WINDOWS_HOST}:\${PROXY_PORT}"
export WS_PROXY="http://\${WINDOWS_HOST}:\${PROXY_PORT}"
export WSS_PROXY="http://\${WINDOWS_HOST}:\${PROXY_PORT}"

# NO_PROXY - k3s 内部流量直连
export NO_PROXY="localhost,127.0.0.1,0.0.0.0,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,*.local,*.svc,*.cluster.local,${POD_CIDR},${SERVICE_CIDR}"

# 小写变量
export http_proxy="\${HTTP_PROXY}"
export https_proxy="\${HTTPS_PROXY}"
export ftp_proxy="\${FTP_PROXY}"
export no_proxy="\${NO_PROXY}"

# 导出给子进程
export HTTP_PROXY HTTPS_PROXY FTP_PROXY WS_PROXY WSS_PROXY NO_PROXY
export http_proxy https_proxy ftp_proxy no_proxy
EOF

    sudo chmod 644 "$proxy_config"

    # 同时添加到用户 bashrc
    if ! grep -q "K3S VPN 代理配置" ~/.bashrc 2>/dev/null; then
        cat >> ~/.bashrc << EOF

# K3S VPN 代理配置
if [ -f /etc/profile.d/k3s-proxy.sh ]; then
    source /etc/profile.d/k3s-proxy.sh
fi
EOF
    fi

    # 立即生效
    export HTTP_PROXY="http://${WINDOWS_HOST}:${PROXY_PORT}"
    export HTTPS_PROXY="http://${WINDOWS_HOST}:${PROXY_PORT}"
    export NO_PROXY="localhost,127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,*.local,*.svc,*.cluster.local,${POD_CIDR},${SERVICE_CIDR}"
    export http_proxy="$HTTP_PROXY"
    export https_proxy="$HTTPS_PROXY"
    export no_proxy="$NO_PROXY"

    log_success "WSL 主机代理配置完成"
}

# 配置 k3s systemd 服务
configure_k3s_service() {
    log_info "配置 K3S systemd 服务代理..."

    sudo mkdir -p /etc/systemd/system/k3s.service.d

    sudo tee /etc/systemd/system/k3s.service.d/proxy.conf > /dev/null << EOF
[Service]
# K3S 服务进程使用 Windows VPN 代理（用于拉取镜像、访问外部 API）
Environment="HTTP_PROXY=http://${WINDOWS_HOST}:${PROXY_PORT}"
Environment="HTTPS_PROXY=http://${WINDOWS_HOST}:${PROXY_PORT}"
Environment="NO_PROXY=localhost,127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,*.local,*.svc,*.cluster.local,${POD_CIDR},${SERVICE_CIDR}"

# 容器运行时不走代理（容器内流量直连）
Environment="CONTAINERD_HTTP_PROXY="
Environment="CONTAINERD_HTTPS_PROXY="
Environment="CONTAINERD_NO_PROXY=localhost,127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,*.local,*.svc,*.cluster.local,${POD_CIDR},${SERVICE_CIDR}"
EOF

    sudo systemctl daemon-reload
    log_success "K3S systemd 配置完成"
}

# 配置 containerd 代理
configure_containerd() {
    log_info "配置 Containerd 代理..."

    sudo mkdir -p /etc/default

    sudo tee /etc/default/containerd > /dev/null << EOF
# Containerd 代理配置 - K3S 环境
# 自动生成于：$(date)

# Containerd 拉取镜像时使用代理
HTTP_PROXY=http://${WINDOWS_HOST}:${PROXY_PORT}
HTTPS_PROXY=http://${WINDOWS_HOST}:${PROXY_PORT}
NO_PROXY=localhost,127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,*.local,*.svc,*.cluster.local,${POD_CIDR},${SERVICE_CIDR}

# 容器运行时不走代理
CONTAINERD_HTTP_PROXY=""
CONTAINERD_HTTPS_PROXY=""
CONTAINERD_NO_PROXY=localhost,127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,*.local,*.svc,*.cluster.local,${POD_CIDR},${SERVICE_CIDR}
EOF

    log_success "Containerd 配置完成"
}

# 为现有工作负载添加 NO_PROXY 环境变量
patch_workloads() {
    log_info "为现有工作负载添加 NO_PROXY 环境变量..."

    local NO_PROXY_VALUE="localhost,127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16,*.local,*.svc,*.cluster.local,${POD_CIDR},${SERVICE_CIDR}"

    # 获取所有命名空间（排除 kube-public 和 kube-node-lease）
    local namespaces=$(kubectl get ns -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep -vE "^kube-(public|node-lease)$")

    for ns in $namespaces; do
        log_info "处理命名空间：$ns"

        # 补丁 Deployments
        for deploy in $(kubectl -n "$ns" get deploy -o jsonpath='{.items[*].metadata.name}' 2>/dev/null); do
            log_info "  补丁 Deployment: $deploy"

            # 检查是否已有 NO_PROXY
            if kubectl -n "$ns" get deployment "$deploy" -o jsonpath='{.spec.template.spec.containers[0].env}' | grep -q "NO_PROXY"; then
                log_info "    已包含 NO_PROXY，跳过"
                continue
            fi

            # 添加环境变量
            kubectl -n "$ns" patch deployment "$deploy" --type='json' -p="[
                {'op': 'add', 'path': '/spec/template/spec/containers/0/env/-', 'value': {'name': 'NO_PROXY', 'value': '${NO_PROXY_VALUE}'}},
                {'op': 'add', 'path': '/spec/template/spec/containers/0/env/-', 'value': {'name': 'no_proxy', 'value': '${NO_PROXY_VALUE}'}},
                {'op': 'add', 'path': '/spec/template/spec/containers/0/env/-', 'value': {'name': 'HTTP_PROXY', 'value': ''}},
                {'op': 'add', 'path': '/spec/template/spec/containers/0/env/-', 'value': {'name': 'HTTPS_PROXY', 'value': ''}}
            ]" 2>/dev/null || log_warning "    补丁失败，可能已有环境变量"
        done

        # 补丁 StatefulSets
        for sts in $(kubectl -n "$ns" get sts -o jsonpath='{.items[*].metadata.name}' 2>/dev/null); do
            log_info "  补丁 StatefulSet: $sts"

            if kubectl -n "$ns" get statefulset "$sts" -o jsonpath='{.spec.template.spec.containers[0].env}' | grep -q "NO_PROXY"; then
                log_info "    已包含 NO_PROXY，跳过"
                continue
            fi

            kubectl -n "$ns" patch statefulset "$sts" --type='json' -p="[
                {'op': 'add', 'path': '/spec/template/spec/containers/0/env/-', 'value': {'name': 'NO_PROXY', 'value': '${NO_PROXY_VALUE}'}},
                {'op': 'add', 'path': '/spec/template/spec/containers/0/env/-', 'value': {'name': 'no_proxy', 'value': '${NO_PROXY_VALUE}'}},
                {'op': 'add', 'path': '/spec/template/spec/containers/0/env/-', 'value': {'name': 'HTTP_PROXY', 'value': ''}},
                {'op': 'add', 'path': '/spec/template/spec/containers/0/env/-', 'value': {'name': 'HTTPS_PROXY', 'value': ''}}
            ]" 2>/dev/null || log_warning "    补丁失败，可能已有环境变量"
        done
    done

    log_success "工作负载补丁完成，Pod 将自动重启"
}

# 验证配置
verify_configuration() {
    log_info "验证配置..."

    echo ""
    echo "=== 环境变量检查 ==="
    echo "HTTP_PROXY: $HTTP_PROXY"
    echo "HTTPS_PROXY: $HTTPS_PROXY"
    echo "NO_PROXY: $NO_PROXY"

    echo ""
    echo "=== K3S 集群状态 ==="
    kubectl get nodes

    echo ""
    echo "=== Pod 状态 ==="
    kubectl get pods -A --no-headers | head -10

    echo ""
    echo "=== 测试外部访问（应通过代理）==="
    if timeout 5 curl -I --connect-timeout 3 https://www.google.com 2>&1 | head -1; then
        log_success "外部访问正常"
    else
        log_warning "外部访问失败，请检查代理配置"
    fi

    echo ""
    echo "=== 测试 k3s 内部访问（应直连）==="
    if kubectl run test-proxy --rm -it --image=curlimages/curl:latest --restart=Never -- curl -I --connect-timeout 3 https://kubernetes.default 2>&1 | head -1; then
        log_success "k3s 内部访问正常"
    else
        log_warning "k3s 内部访问失败"
    fi
}

# 显示使用说明
show_usage() {
    echo ""
    echo "================================================================="
    echo "配置完成！"
    echo "================================================================="
    echo ""
    echo "下一步操作："
    echo "1. 重启 k3s 服务以应用 systemd 配置："
    echo "   sudo systemctl restart k3s"
    echo ""
    echo "2. 等待 Pod 重启完成："
    echo "   kubectl get pods -A -w"
    echo ""
    echo "3. 验证代理配置："
    echo "   echo \$HTTP_PROXY"
    echo "   echo \$NO_PROXY"
    echo ""
    echo "4. 如果需要修改代理端口，编辑环境变量 PROXY_PORT 后重新运行脚本"
    echo ""
    echo "================================================================="
}

# 主函数
main() {
    echo "================================================================="
    echo "K3S VPN 代理配置工具 - WSL2 + Windows"
    echo "================================================================="
    echo "Windows 主机：$WINDOWS_HOST"
    echo "代理端口：$PROXY_PORT"
    echo "Pod CIDR: $POD_CIDR"
    echo "Service CIDR: $SERVICE_CIDR"
    echo "================================================================="
    echo ""

    # 检查是否为 root
    if [ "$EUID" -ne 0 ]; then
        log_error "请使用 sudo 运行此脚本"
        exit 1
    fi

    # 检查 kubectl 是否可用
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl 未安装或不在 PATH 中"
        exit 1
    fi

    # 检查 k3s 是否运行
    if ! sudo systemctl is-active --quiet k3s; then
        log_warning "k3s 服务未运行，配置完成后请手动启动"
    fi

    # 执行配置步骤
    check_windows_host
    check_proxy_port
    configure_host_proxy
    configure_k3s_service
    configure_containerd

    # 询问是否补丁现有工作负载
    echo ""
    read -p "是否为现有工作负载添加 NO_PROXY 环境变量？[y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        patch_workloads
    fi

    verify_configuration
    show_usage
}

# 运行主函数
main "$@"
