#!/bin/bash
# =============================================================================
# K3S 多节点集群部署脚本 - 单 WSL2 实例（k3d 风格优化版）
# =============================================================================
# Story 0.4: K3S 集群部署（WSL2 多节点版）
# 技术栈：K3S v1.34.5 + Docker 容器运行多节点
# 设计理念：借鉴 k3d 的自动化 + 手动控制的灵活性
# 文档：docs/deployment/K3S_MULTI_NODE_GUIDE.md
# =============================================================================

# =============================================================================
# 全局配置
# =============================================================================
readonly SCRIPT_VERSION="2.0.0"
readonly SCRIPT_NAME="$(basename "$0")"

# 错误处理配置
DEPLOY_FAILED=0
DEPLOY_ERROR_REASON=""

# =============================================================================
# 颜色定义（终端美化）
# =============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# =============================================================================
# 日志函数
# =============================================================================
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${CYAN}=== $1 ===${NC}"
}

# =============================================================================
# 错误处理函数（trap 回调）
# =============================================================================
error_handler() {
    local line_number=$1
    echo ""
    log_error "脚本执行失败于第 $line_number 行"
    log_error "退出码：$DEPLOY_FAILED"
    log_error "原因：$DEPLOY_ERROR_REASON"
    echo ""
    log_info "故障排除建议："
    echo "  1. 查看容器日志：docker logs k3s-node-server-1"
    echo "  2. 检查集群状态：docker exec k3s-node-server-1 kubectl get nodes"
    echo "  3. 查看 K3S 日志：docker exec k3s-node-server-1 cat /var/log/k3s.log"
    echo "  4. 清理集群：$SCRIPT_NAME delete"
    exit $DEPLOY_FAILED
}

trap 'error_handler $LINENO' ERR

# =============================================================================
# 全局配置（从 CONFIG 数组改为独立变量）
# =============================================================================
# 集群配置
SERVER_NODES=${SERVER_NODES:-1}
AGENT_NODES=${AGENT_NODES:-2}
K3S_VERSION="${K3S_VERSION:-v1.34.5-k3s1}"
# 生成随机 Token（如果未提供）
if [ -z "$TOKEN" ]; then
    TOKEN="k3s-token-$(head -c 16 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 32)"
fi

# 网络配置
NETWORK_NAME="${NETWORK_NAME:-k3s-network}"
NETWORK_SUBNET="${NETWORK_SUBNET:-172.30.0.0/16}"
NETWORK_GATEWAY="${NETWORK_GATEWAY:-172.30.0.1}"
POD_CIDR="${POD_CIDR:-10.42.0.0/16}"
SERVICE_CIDR="${SERVICE_CIDR:-10.43.0.0/16}"
CLUSTER_DNS="${CLUSTER_DNS:-10.43.0.10}"

# 节点配置
NODE_PREFIX="${NODE_PREFIX:-k3s-node}"
SERVER_IP_BASE=${SERVER_IP_BASE:-10}
AGENT_IP_BASE=${AGENT_IP_BASE:-20}

# K3S 配置
FLANNEL_BACKEND="${FLANNEL_BACKEND:-vxlan}"
DISABLE_COMPONENTS="${DISABLE_COMPONENTS:-traefik servicelb metrics-server}"

# 端口映射
API_SERVER_PORT=${API_SERVER_PORT:-6443}
HTTP_PORT=${HTTP_PORT:-80}
HTTPS_PORT=${HTTPS_PORT:-443}
MAP_PORTS="${MAP_PORTS:-true}"

# 路径配置
KUBECONFIG_DIR="${KUBECONFIG_DIR:-$HOME/.kube}"
TEMP_DIR="${TEMP_DIR:-/tmp/k3s-${CLUSTER_NAME:-k3s-default}}"

# 运行模式
QUIET_MODE="${QUIET_MODE:-false}"
COMMAND="${COMMAND:-create}"
# CLUSTER_NAME 在 parse_args 中处理

# =============================================================================
# 帮助信息
# =============================================================================
show_help() {
    cat << EOF
${CYAN}用法:${NC} $SCRIPT_NAME [command] [options]

${CYAN}命令:${NC}
  create      创建集群（默认）
  delete      删除集群
  list        列出所有集群
  show        显示集群详情
  help        显示此帮助信息

${CYAN}选项:${NC}
  -n, --servers NUM     Server 节点数量（默认：1）
  -a, --agents NUM      Agent 节点数量（默认：2）
  -v, --version VER     K3S 版本（默认：v1.34.5+k3s1）
  -t, --token TOKEN     集群 Token（默认：自动生成）
  --pod-cidr CIDR       Pod CIDR（默认：10.42.0.0/16）
  --service-cidr CIDR   Service CIDR（默认：10.43.0.0/16）
  --network NAME        Docker 网络名称（默认：k3s-network）
  --subnet SUBNET       Docker 网络子网（默认：172.30.0.0/16）
  --no-ports            不映射端口（用于多集群）
  -q, --quiet           静默模式
  -h, --help            显示帮助

${CYAN}示例:${NC}
  # 创建默认集群（1 Server + 2 Agent）
  sudo $SCRIPT_NAME

  # 创建自定义集群
  sudo $SCRIPT_NAME create --servers 3 --agents 5

  # 指定 K3S 版本
  sudo $SCRIPT_NAME --version v1.35.0+k3s1

  # 删除集群
  sudo $SCRIPT_NAME delete

  # 查看集群列表
  sudo $SCRIPT_NAME list

EOF
}

# =============================================================================
# 工具函数
# =============================================================================

# 生成随机 Token
generate_token() {
    local chars="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    local token="k3s-token-"
    for i in {1..32}; do
        token+="${chars:RANDOM%${#chars}:1}"
    done
    echo "$token"
}

# 检查命令是否存在
command_exists() {
    command -v "$1" &>/dev/null
}

# 等待条件满足（带超时）
wait_for() {
    local condition="$1"
    local timeout="${2:-60}"
    local interval="${3:-2}"
    local elapsed=0

    while ! eval "$condition" &>/dev/null; do
        if [ $elapsed -ge $timeout ]; then
            return 1
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
    done
    return 0
}

# =============================================================================
# 前置检查
# =============================================================================
check_prerequisites() {
    log_step "前置检查"

    # 检查 root 权限
    if [ "$EUID" -ne 0 ]; then
        log_error "请以 root 用户运行此脚本（使用 sudo）"
        DEPLOY_FAILED=1
        DEPLOY_ERROR_REASON="权限不足"
        exit 1
    fi
    log_success "Root 权限检查通过"

    # 检查 Docker
    if ! command_exists docker; then
        log_error "Docker 未安装"
        log_info "安装命令：curl -fsSL https://get.docker.com | sh"
        DEPLOY_FAILED=1
        DEPLOY_ERROR_REASON="Docker 未安装"
        exit 1
    fi
    log_success "Docker 已安装：$(docker --version)"

    # 检查 Docker 服务
    if ! docker info &>/dev/null; then
        log_error "Docker 服务未运行"
        DEPLOY_FAILED=1
        DEPLOY_ERROR_REASON="Docker 服务未运行"
        exit 1
    fi
    log_success "Docker 服务运行正常"

    # 检查 kubectl（可选）
    if command_exists kubectl; then
        log_success "kubectl 已安装：$(kubectl version --client --short 2>/dev/null || kubectl version --client)"
    else
        log_warn "kubectl 未安装，将使用 docker exec 执行 kubectl 命令"
    fi

    # 检查端口占用
    log_info "检查端口占用..."
    local ports=($API_SERVER_PORT $HTTP_PORT $HTTPS_PORT)
    for port in "${ports[@]}"; do
        if ss -tlnp 2>/dev/null | grep -q ":$port " || netstat -tlnp 2>/dev/null | grep -q ":$port "; then
            log_warn "端口 $port 被占用"
        else
            log_success "端口 $port 可用"
        fi
    done
}

# =============================================================================
# 清理旧集群
# =============================================================================
cleanup_existing_cluster() {
    log_step "检查旧集群"

    local existing_nodes=$(docker ps -a --filter "name=${NODE_PREFIX}" --format "{{.Names}}" | wc -l)

    if [ "$existing_nodes" -gt 0 ]; then
        log_warn "发现 $existing_nodes 个旧节点"

        if [ "$QUIET_MODE" = true ]; then
            log_info "静默模式：自动删除旧节点"
            docker rm -f $(docker ps -a --filter "name=${NODE_PREFIX}" --format "{{.Names}}") 2>/dev/null || true
            log_success "旧节点已清理"
        else
            read -p "是否删除旧节点并重新部署？(y/n): " confirm
            if [ "$confirm" = "y" ]; then
                log_info "删除旧节点..."
                docker rm -f $(docker ps -a --filter "name=${NODE_PREFIX}" --format "{{.Names}}") 2>/dev/null || true
                log_success "旧节点已清理"
            else
                log_info "取消部署"
                exit 0
            fi
        fi
    else
        log_success "未发现旧集群"
    fi
}

# =============================================================================
# 创建 Docker 网络
# =============================================================================
create_network() {
    log_step "创建 Docker 网络"

    if ! docker network inspect "$NETWORK_NAME" &>/dev/null; then
        log_info "创建网络：$NETWORK_NAME ($NETWORK_SUBNET)"
        docker network create \
            --driver bridge \
            --subnet="$NETWORK_SUBNET" \
            --gateway="$NETWORK_GATEWAY" \
            "$NETWORK_NAME"
        log_success "Docker 网络已创建"
    else
        log_success "Docker 网络已存在：$NETWORK_NAME"
    fi
}

# =============================================================================
# 部署 Server 节点
# =============================================================================
deploy_server_nodes() {
    log_step "部署 K3S Server 节点"

    for i in $(seq 1 $SERVER_NODES); do
        local node_name="${NODE_PREFIX}-server-$i"
        local node_ip="$NETWORK_GATEWAY"
        node_ip="${node_ip%.*}.$((SERVER_IP_BASE + i))"

        log_info "创建 Server 节点：$node_name ($node_ip)"

        # 构建端口映射参数
        local port_mappings=""
        if [ "$i" -eq 1 ] && [ "$MAP_PORTS" = true ]; then
            port_mappings="-p $API_SERVER_PORT:6443 -p $HTTP_PORT:80 -p $HTTPS_PORT:443"
        fi

        # 构建禁用组件参数
        local disable_args=""
        for component in $DISABLE_COMPONENTS; do
            disable_args+="--disable=$component "
        done

        docker run -d \
            --name "$node_name" \
            --hostname "$node_name" \
            --net "$NETWORK_NAME" \
            --ip "$node_ip" \
            --privileged \
            -e K3S_TOKEN="$TOKEN" \
            -e K3S_KUBECONFIG_OUTPUT=/output/kubeconfig.yaml \
            -v "${node_name}-data:/var/lib/rancher/k3s" \
            -v "${node_name}-output:/output" \
            --tmpfs /run:exec \
            --tmpfs /var/run:exec \
            $port_mappings \
            rancher/k3s:$K3S_VERSION server \
            --cluster-init \
            --token "$TOKEN" \
            --node-ip "$node_ip" \
            --node-external-ip "$node_ip" \
            --flannel-backend="$FLANNEL_BACKEND" \
            --disable-network-policy=false \
            $disable_args \
            --cluster-cidr "$POD_CIDR" \
            --service-cidr "$SERVICE_CIDR" \
            --cluster-dns "$CLUSTER_DNS" \
            --node-name "$node_name"

        log_success "Server 节点已创建：$node_name"
    done
}

# =============================================================================
# 部署 Agent 节点
# =============================================================================
deploy_agent_nodes() {
    log_step "部署 K3S Agent 节点"

    local server_ip="$NETWORK_GATEWAY"
    server_ip="${server_ip%.*}.$SERVER_IP_BASE"

    for i in $(seq 1 $AGENT_NODES); do
        local node_name="${NODE_PREFIX}-agent-$i"
        local node_ip="$NETWORK_GATEWAY"
        node_ip="${node_ip%.*}.$((AGENT_IP_BASE + i))"

        log_info "创建 Agent 节点：$node_name ($node_ip)"

        docker run -d \
            --name "$node_name" \
            --hostname "$node_name" \
            --net "$NETWORK_NAME" \
            --ip "$node_ip" \
            --privileged \
            -e K3S_TOKEN="$TOKEN" \
            -v "${node_name}-data:/var/lib/rancher/k3s" \
            --tmpfs /run:exec \
            --tmpfs /var/run:exec \
            rancher/k3s:$K3S_VERSION agent \
            --server "https://$server_ip:6443" \
            --token "$TOKEN" \
            --node-ip "$node_ip" \
            --node-name "$node_name"

        log_success "Agent 节点已创建：$node_name"
    done
}

# =============================================================================
# 等待节点启动
# =============================================================================
wait_for_nodes() {
    log_step "等待节点启动"

    local total_nodes=$((SERVER_NODES + AGENT_NODES))
    local ready_nodes=0
    local max_retries=10
    local retry_count=0

    log_info "等待 Server 节点启动..."
    sleep 10

    log_info "等待所有节点 Ready..."
    while [ $ready_nodes -lt $total_nodes ] && [ $retry_count -lt $max_retries ]; do
        sleep 5
        ready_nodes=$(docker exec "${NODE_PREFIX}-server-1" kubectl get nodes --no-headers 2>/dev/null | grep -c " Ready " || echo "0")
        ready_nodes=$(echo "$ready_nodes" | tr -d '[:space:]')
        retry_count=$((retry_count + 1))
        log_info "  第 $retry_count 次检查：$ready_nodes/$total_nodes 节点已就绪..."
    done

    if [ "$ready_nodes" -eq "$total_nodes" ]; then
        log_success "所有节点已就绪"
    else
        log_warn "超时：$ready_nodes/$total_nodes 节点已就绪"
        DEPLOY_FAILED=2
        DEPLOY_ERROR_REASON="节点启动超时"
    fi
}

# =============================================================================
# 配置 kubectl
# =============================================================================
configure_kubectl() {
    log_step "配置 kubectl"

    # 创建临时目录
    mkdir -p "$TEMP_DIR"

    # 获取 kubeconfig
    log_info "获取 kubeconfig..."
    if docker exec "${NODE_PREFIX}-server-1" cat /output/kubeconfig.yaml > "$TEMP_DIR/kubeconfig.yaml" 2>/dev/null; then
        log_success "kubeconfig 已获取"
    else
        log_warn "无法获取 kubeconfig，使用 kubectl config view"
        docker exec "${NODE_PREFIX}-server-1" kubectl config view --raw > "$TEMP_DIR/kubeconfig.yaml"
    fi

    # 配置本地 kubectl
    if ! command_exists kubectl; then
        log_warn "kubectl 未安装，跳过本地配置"
        log_info "可使用 docker exec 执行 kubectl 命令："
        echo "  docker exec ${NODE_PREFIX}-server-1 kubectl get nodes"
        return
    fi

    # 备份现有配置
    if [ -f "$KUBECONFIG_DIR/config" ]; then
        cp "$KUBECONFIG_DIR/config" "$KUBECONFIG_DIR/config.bak.$(date +%Y%m%d%H%M%S)"
        log_info "已备份现有 kubeconfig"
    fi

    # 更新服务器地址
    local server_ip="$NETWORK_GATEWAY"
    server_ip="${server_ip%.*}.$SERVER_IP_BASE"
    sed -i "s|https://127.0.0.1:6443|https://$server_ip:6443|g" "$TEMP_DIR/kubeconfig.yaml"

    # 复制配置
    mkdir -p "$KUBECONFIG_DIR"
    cp "$TEMP_DIR/kubeconfig.yaml" "$KUBECONFIG_DIR/config"
    chmod 600 "$KUBECONFIG_DIR/config"

    if [ -n "$SUDO_USER" ]; then
        chown "$SUDO_USER:$SUDO_USER" "$KUBECONFIG_DIR/config" 2>/dev/null || true
    fi

    log_success "kubectl 配置已更新"
    log_info "测试命令：kubectl get nodes"
}

# =============================================================================
# 验证集群
# =============================================================================
verify_cluster() {
    log_step "验证集群"

    local server_node="${NODE_PREFIX}-server-1"

    # 节点状态
    log_info "检查节点状态..."
    docker exec "$server_node" kubectl get nodes -o wide

    # 系统 Pod
    log_info "检查系统 Pod..."
    docker exec "$server_node" kubectl get pods -n kube-system -o wide

    # 存储类
    log_info "检查存储类..."
    docker exec "$server_node" kubectl get storageclass

    # 集群信息
    log_info "集群信息："
    docker exec "$server_node" kubectl cluster-info
}

# =============================================================================
# 显示部署摘要
# =============================================================================
show_summary() {
    log_step "部署完成"

    local total_nodes=$((SERVER_NODES + AGENT_NODES))
    local server_ip="$NETWORK_GATEWAY"
    server_ip="${server_ip%.*}.$SERVER_IP_BASE"

    cat << EOF

${GREEN}=== K3S 多节点集群部署完成 ===${NC}

${CYAN}集群配置:${NC}
  集群名称：$CLUSTER_NAME
  Server 节点：$SERVER_NODES
  Agent 节点：$AGENT_NODES
  总节点数：$TOTAL_NODES
  K3S 版本：$K3S_VERSION
  Docker 网络：$NETWORK_NAME ($NETWORK_SUBNET)

${CYAN}节点信息:${NC}
  Server:
EOF

    for i in $(seq 1 $SERVER_NODES); do
        local node_ip="$NETWORK_GATEWAY"
        node_ip="${node_ip%.*}.$((SERVER_IP_BASE + i))"
        echo "    - ${NODE_PREFIX}-server-$i ($node_ip)"
    done

    cat << EOF
  Agent:
EOF

    for i in $(seq 1 $AGENT_NODES); do
        local node_ip="$NETWORK_GATEWAY"
        node_ip="${node_ip%.*}.$((AGENT_IP_BASE + i))"
        echo "    - ${NODE_PREFIX}-agent-$i ($node_ip)"
    done

    cat << EOF

${CYAN}管理命令:${NC}
  kubectl get nodes                    # 查看节点
  kubectl get pods -A                  # 查看所有 Pod
  docker ps | grep k3s-node            # 查看容器
  docker logs k3s-node-server-1        # 查看日志

${CYAN}访问 Traefik（安装后）:${NC}
  kubectl port-forward -n traefik svc/traefik 8080:80
  浏览器访问：http://localhost:8080

${CYAN}下一步:${NC}
  1. 安装 Traefik: sudo ./scripts/deployment/k3s/install-traefik-docker.sh
  2. 运行健康检查：sudo ./scripts/deployment/k3s/health_check_docker.sh
  3. 部署应用：kubectl apply -f <your-app>.yaml

${GREEN}=== 部署成功 ✅ ===${NC}
EOF
}

# =============================================================================
# 删除集群
# =============================================================================
delete_cluster() {
    log_step "删除集群"

    log_info "删除所有节点容器..."
    docker rm -f $(docker ps -a --filter "name=${NODE_PREFIX}" --format "{{.Names}}") 2>/dev/null || true

    log_info "删除数据卷..."
    docker volume rm $(docker volume ls --filter "name=${NODE_PREFIX}" --format "{{.Name}}") 2>/dev/null || true

    log_info "删除 Docker 网络..."
    docker network rm "$NETWORK_NAME" 2>/dev/null || true

    log_info "清理 kubeconfig..."
    rm -f "$KUBECONFIG_DIR/config" 2>/dev/null || true
    rm -rf "$TEMP_DIR" 2>/dev/null || true

    log_success "集群已删除"
}

# =============================================================================
# 列出集群
# =============================================================================
list_clusters() {
    log_info "K3S 集群列表："
    echo ""

    # 查找所有 k3s-node 容器
    local clusters=$(docker ps -a --filter "name=k3s-node" --format "{{.Names}}" | \
        sed 's/-server-[0-9]*$//' | sort -u)

    if [ -z "$clusters" ]; then
        echo "  未发现集群"
        return
    fi

    echo "  集群名称          节点数    状态"
    echo "  ─────────────────────────────────"

    for cluster in $clusters; do
        local node_count=$(docker ps -a --filter "name=${cluster}-" --format "{{.Names}}" | wc -l)
        local status="Unknown"

        if docker ps --filter "name=${cluster}-server-1" --format "{{.Status}}" | grep -q "Up"; then
            status="${GREEN}Running${NC}"
        else
            status="${RED}Stopped${NC}"
        fi

        printf "  %-18s %-9s %b\n" "$cluster" "$node_count" "$status"
    done
}

# =============================================================================
# 显示集群详情
# =============================================================================
show_cluster() {
    local cluster_name="${1:-k3s-default}"
    NODE_PREFIX="${cluster_name}-node"

    log_step "集群详情：$cluster_name"

    # 节点信息
    log_info "节点容器："
    docker ps -a --filter "name=${NODE_PREFIX}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

    # 数据卷
    log_info "数据卷："
    docker volume ls --filter "name=${NODE_PREFIX}" --format "table {{.Name}}\t{{.Driver}}"

    # 网络
    log_info "网络："
    docker network inspect "${NETWORK_NAME}" --format '{{.Name}}: {{.IPAM.Config}}' 2>/dev/null || echo "  网络不存在"

    # 集群状态
    if docker ps --filter "name=${NODE_PREFIX}-server-1" --format "{{.Names}}" | grep -q .; then
        log_info "集群状态："
        docker exec "${NODE_PREFIX}-server-1" k3s kubectl get nodes 2>/dev/null || log_warn "无法获取集群状态"
    fi
}

# =============================================================================
# 解析命令行参数
# =============================================================================
parse_args() {
    # 设置默认集群名称
    CLUSTER_NAME="${CLUSTER_NAME:-k3s-default}"
    NODE_PREFIX="${CLUSTER_NAME}-node"

    while [[ $# -gt 0 ]]; do
        case $1 in
            create)
                COMMAND="create"
                shift
                ;;
            delete)
                COMMAND="delete"
                shift
                ;;
            list)
                COMMAND="list"
                shift
                ;;
            show)
                COMMAND="show"
                shift
                ;;
            help|--help|-h)
                show_help
                exit 0
                ;;
            --servers|-n)
                SERVER_NODES="$2"
                shift 2
                ;;
            --agents|-a)
                AGENT_NODES="$2"
                shift 2
                ;;
            --version|-v)
                K3S_VERSION="$2"
                shift 2
                ;;
            --token|-t)
                TOKEN="$2"
                shift 2
                ;;
            --pod-cidr)
                POD_CIDR="$2"
                shift 2
                ;;
            --service-cidr)
                SERVICE_CIDR="$2"
                shift 2
                ;;
            --network)
                NETWORK_NAME="$2"
                shift 2
                ;;
            --subnet)
                NETWORK_SUBNET="$2"
                shift 2
                ;;
            --no-ports)
                MAP_PORTS=false
                shift
                ;;
            --quiet|-q)
                QUIET_MODE=true
                shift
                ;;
            --cluster-name)
                CLUSTER_NAME="$2"
                NODE_PREFIX="${CLUSTER_NAME}-node"
                shift 2
                ;;
            *)
                log_error "未知参数：$1"
                show_help
                exit 1
                ;;
        esac
    done
}

# =============================================================================
# 主函数
# =============================================================================
main() {
    # 解析参数
    parse_args "$@"

    # 设置 NODE_PREFIX（如果未通过 cluster-name 设置）
    if [ -z "$NODE_PREFIX" ]; then
        NODE_PREFIX="${CLUSTER_NAME}-node"
    fi

    # 显示版本和模式
    if [ "$COMMAND" = "create" ] || [ "$COMMAND" = "deploy" ]; then
        log_step "K3S 多节点集群部署 v$SCRIPT_VERSION"
        log_info "集群名称：$CLUSTER_NAME"
        log_info "节点配置：$SERVER_NODES Server + $AGENT_NODES Agent"
        log_info "K3S 版本：$K3S_VERSION"
    fi

    # 执行命令
    case $COMMAND in
        create|deploy|"")
            check_prerequisites
            cleanup_existing_cluster
            create_network
            deploy_server_nodes
            deploy_agent_nodes
            wait_for_nodes
            configure_kubectl
            verify_cluster
            show_summary
            ;;
        delete)
            delete_cluster
            ;;
        list)
            list_clusters
            ;;
        show)
            show_cluster "${2:-k3s-default}"
            ;;
        help)
            show_help
            ;;
        *)
            log_error "未知命令：$COMMAND"
            show_help
            exit 1
            ;;
    esac
}

# =============================================================================
# 入口点
# =============================================================================
main "$@"
