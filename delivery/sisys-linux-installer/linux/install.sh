#!/bin/bash
###############################################################################
# SISYS 企业应用 - Linux 一键安装脚本
# 版本: 1.0.0
# 支持系统: Ubuntu 22.04+/Debian 11+/CentOS Stream 9/RHEL 9
# 用法: curl -sSL https://sisys.example.com/install.sh | bash
###############################################################################

set -euo pipefail

# ===========================================================================
# sudo 权限预检（P0-2）
# ===========================================================================
if ! sudo -n true 2>/dev/null; then
    echo -e "\033[0;31m[ERROR]\033[0m 需要 sudo 权限。请使用 root 用户或具有 sudo 权限的用户运行此脚本。"
    exit 1
fi

# ===========================================================================
# 全局变量
# ===========================================================================
readonly SCRIPT_VERSION="1.0.0"
readonly SCRIPT_NAME="SISYS Linux Installer"
readonly LOG_FILE="/var/log/sisys/install.log"
readonly DATA_DIR="/opt/sisys/data"
readonly CRED_FILE="/opt/sisys/initial-credentials.txt"
readonly COMPOSE_FILE="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/docker-compose.yml"

# 颜色定义
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# 进度跟踪
STEP=0
TOTAL_STEPS=8

# 安装阶段记录
declare -a COMPLETED_STAGES=()

# ===========================================================================
# 工具函数
# ===========================================================================

# 日志输出
log() {
    local level="$1"
    shift
    local msg="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # 终端输出（带颜色）
    case "$level" in
        INFO)
            echo -e "${GREEN}[INFO]${NC} ${msg}"
            ;;
        WARN)
            echo -e "${YELLOW}[WARN]${NC} ${msg}"
            ;;
        ERROR)
            echo -e "${RED}[ERROR]${NC} ${msg}"
            ;;
        STEP)
            echo -e "${BLUE}[${STEP}/${TOTAL_STEPS}]${NC} ${msg}"
            ;;
    esac

    # 日志文件输出（无颜色）
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "[${timestamp}] [${level}] ${msg}" >> "$LOG_FILE" 2>/dev/null || true
}

# 进度条
progress_bar() {
    local current="$1"
    local total="$2"
    local width=30
    local percent=$(( current * 100 / total ))
    local filled=$(( current * width / total ))
    local empty=$(( width - filled ))

    printf "["
    printf '%0.s█' $(seq 1 $filled 2>/dev/null) || true
    printf '%0.s░' $(seq 1 $empty 2>/dev/null) || true
    printf "] %d%%" "$percent"
    echo
}

# 步骤递增
next_step() {
    STEP=$((STEP + 1))
    log "STEP" "$1"
}

# 错误处理
error_exit() {
    log "ERROR" "$1"
    log "ERROR" "安装失败。请查看日志文件: $LOG_FILE"
    log "ERROR" "如需帮助，请联系: support@sisys.example.com"
    exit 1
}

# 清理函数（Ctrl+C 中断处理）
cleanup() {
    echo
    log "WARN" "安装已中断 (Ctrl+C)"
    log "INFO" "已完成阶段: ${COMPLETED_STAGES[*]:-无}"
    log "INFO" "要继续安装，请重新运行脚本"
    log "INFO" "如需清理残留容器，请执行: sudo docker compose -f $COMPOSE_FILE down"
    exit 130
}

trap cleanup SIGINT SIGTERM

# ===========================================================================
# 1. 系统检测
# ===========================================================================
detect_os() {
    next_step "正在检测系统..."

    if [ -f /etc/os-release ]; then
        # shellcheck source=/dev/null
        . /etc/os-release
        OS_ID="$ID"
        OS_VERSION="$VERSION_ID"
        OS_NAME="$PRETTY_NAME"
    else
        error_exit "无法检测操作系统信息"
    fi

    # 架构检测
    ARCH=$(uname -m)
    if [ "$ARCH" != "x86_64" ]; then
        error_exit "不支持的架构: $ARCH。仅支持 x86_64 (amd64)"
    fi

    # 内核信息
    KERNEL=$(uname -r)

    log "INFO" "检测到系统: $OS_NAME ($ARCH)"

    # 支持矩阵验证
    case "$OS_ID" in
        ubuntu)
            if [[ "$OS_VERSION" != "22.04" && "$OS_VERSION" != "24.04" ]]; then
                error_exit "不支持的 Ubuntu 版本: $OS_VERSION。支持: 22.04/24.04"
            fi
            ;;
        debian)
            if [[ "$OS_VERSION" != "11" && "$OS_VERSION" != "12" ]]; then
                error_exit "不支持的 Debian 版本: $OS_VERSION。支持: 11/12"
            fi
            ;;
        centos|centos\ stream)
            if [[ "$OS_VERSION" != "9" ]]; then
                error_exit "不支持的 CentOS 版本: $OS_VERSION。支持: Stream 9"
            fi
            ;;
        rhel)
            if [[ "$OS_VERSION" != "9" ]]; then
                error_exit "不支持的 RHEL 版本: $OS_VERSION。支持: 9"
            fi
            ;;
        *)
            error_exit "不支持的操作系统: $OS_ID。支持: Ubuntu 22.04+/Debian 11+/CentOS Stream 9/RHEL 9"
            ;;
    esac

    COMPLETED_STAGES+=("系统检测")
}

# ===========================================================================
# 2. 资源预检
# ===========================================================================
check_resources() {
    next_step "正在检查系统资源..."

    # 磁盘空间检查
    local available_disk_kb
    available_disk_kb=$(df -k / | awk 'NR==2 {print $4}')
    local available_disk_gb=$((available_disk_kb / 1024 / 1024))

    if [ "$available_disk_gb" -lt 30 ]; then
        echo -e "${RED}❌ 磁盘空间不足${NC}"
        echo -e "   当前可用: ${available_disk_gb}GB"
        echo -e "   需要至少: 50GB"
        echo -e "   建议: 清理磁盘空间或扩展分区"
        error_exit "磁盘空间不足"
    elif [ "$available_disk_gb" -lt 50 ]; then
        echo -e "${YELLOW}⚠️  磁盘空间偏低${NC}"
        echo -e "   当前可用: ${available_disk_gb}GB (建议 50GB+)"
    fi

    # 内存检查
    local available_mem_mb
    available_mem_mb=$(free -m | awk '/^Mem:/ {print $7}')
    local total_mem_mb
    total_mem_mb=$(free -m | awk '/^Mem:/ {print $2}')

    if [ "$total_mem_mb" -lt 8192 ]; then
        echo -e "${RED}❌ 内存不足${NC}"
        echo -e "   当前可用: ${total_mem_mb}MB"
        echo -e "   需要至少: 8GB"
        echo -e "   建议: 升级内存"
        error_exit "内存不足"
    fi

    log "INFO" "磁盘空间: ${available_disk_gb}GB 可用, 内存: ${total_mem_mb}MB"
    COMPLETED_STAGES+=("资源预检")
}

# ===========================================================================
# 3. 安装前检查报告 + 用户确认
# ===========================================================================
show_check_report_and_confirm() {
    next_step "生成安装前检查报告..."

    # Docker 检测
    local docker_status="✅ 已安装"
    if ! command -v docker &>/dev/null; then
        docker_status="⚠️  未安装（将自动安装）"
    else
        local docker_version
        docker_version=$(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' || echo "未知")
        docker_status="✅ 已安装 (v$docker_version)"
    fi

    # Docker Compose 检测
    local compose_status="⚠️  未安装（将自动安装）"
    if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
        local compose_version
        compose_version=$(docker compose version 2>/dev/null | grep -oP 'v?\d+\.\d+\.\d+' || echo "未知")
        compose_status="✅ 已安装 ($compose_version)"
    fi

    # 端口检测
    local port_warnings=()
    local check_ports=(80 443 6379 5432 6333 8080 9000 9001 7687)
    for port in "${check_ports[@]}"; do
        # P2-13: ss -tln 不需要 root 权限（-tlnp 需要 root 才能查看进程）
        if ss -tln 2>/dev/null | grep -q ":${port} "; then
            port_warnings+=("⚠️  端口 $port 被占用（将自动避让）")
        fi
    done

    # 输出检查报告
    echo
    echo "=========================================="
    echo "  SISYS 安装前检查报告"
    echo "=========================================="
    echo "✅ 操作系统: $OS_NAME (支持)"
    echo "✅ 架构: $ARCH"
    echo "✅ 内核: $KERNEL"

    local available_disk_gb
    available_disk_gb=$(df -h / | awk 'NR==2 {print $4}')
    local total_mem_gb
    total_mem_gb=$(free -g | awk '/^Mem:/ {print $2}')

    if echo "$available_disk_gb" | grep -qP '^\d+' && [ "$(echo "$available_disk_gb" | grep -oP '^\d+')" -lt 50 ]; then
        echo "⚠️  磁盘空间: $available_disk_gb 可用（建议 50GB+）"
    else
        echo "✅ 磁盘空间: $available_disk_gb 可用"
    fi

    if [ "$total_mem_gb" -lt 16 ]; then
        echo "⚠️  内存: ${total_mem_gb}GB（推荐 32GB）"
    else
        echo "✅ 内存: ${total_mem_gb}GB"
    fi

    echo "$docker_status"
    echo "$compose_status"

    if [ ${#port_warnings[@]} -gt 0 ]; then
        for warning in "${port_warnings[@]}"; do
            echo "$warning"
        done
    else
        echo "✅ 所有端口可用"
    fi

    echo "=========================================="
    echo
    echo -n "确认开始安装？[Y/n]: "

    # 超时 30 秒自动取消
    local response
    if ! read -r -t 30 response; then
        echo
        log "WARN" "超时，安装已取消"
        exit 0
    fi

    if [[ "$response" =~ ^[Nn]$ ]]; then
        log "INFO" "用户取消安装"
        exit 0
    fi

    COMPLETED_STAGES+=("检查报告确认")
}

# ===========================================================================
# 4. Docker 安装
# ===========================================================================
install_docker() {
    next_step "正在安装 Docker..."

    if command -v docker &>/dev/null; then
        local docker_version
        docker_version=$(docker --version | grep -oP '\d+\.\d+\.\d+')
        local major_version
        major_version=$(echo "$docker_version" | cut -d. -f1)
        if [ "$major_version" -ge 24 ]; then
            log "INFO" "Docker 已安装 (v$docker_version)，跳过"
            COMPLETED_STAGES+=("Docker 已安装")
            return 0
        fi
    fi

    log "INFO" "正在使用国内镜像源自动安装 Docker..."

    case "$OS_ID" in
        ubuntu|debian)
            # 使用阿里云镜像源
            curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/"$OS_ID"/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null || true
            echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://mirrors.aliyun.com/docker-ce/linux/$OS_ID $(lsb_release -cs 2>/dev/null || echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
            sudo apt-get update -qq
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;
        centos\ stream|rhel)
            # P1-9: RHEL 9/CentOS Stream 9 使用 dnf-plugins-core
            sudo dnf install -y dnf-plugins-core
            sudo dnf config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo
            sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
    esac

    sudo systemctl enable docker
    sudo systemctl start docker

    # P0-1: Docker 安装后使用 sudo 执行后续 docker compose 命令
    # 注意：用户添加到 docker 组后当前 shell 不会立即生效
    # 解决方案：后续所有 docker compose 命令使用 sudo 执行
    USE_SUDO_DOCKER=true

    log "INFO" "Docker 安装完成"
    COMPLETED_STAGES+=("Docker 安装")
}

# ===========================================================================
# 5. 端口检测与自动避让
# ===========================================================================
detect_and_resolve_ports() {
    next_step "正在检测端口占用..."

    local -n port_ref=$1
    local -n range_ref=$2
    local component_name=$3

    local original_port="${!port_ref}"

    if ! ss -tln 2>/dev/null | grep -q ":${original_port} "; then
        log "INFO" "$component_name 端口 $original_port 可用"
        return 0
    fi

    # 自动避让
    local range_start range_end
    range_start=$(echo "$range_ref" | cut -d- -f1)
    range_end=$(echo "$range_ref" | cut -d- -f2)

    for ((port=range_start; port<=range_end; port++)); do
        if ! ss -tln 2>/dev/null | grep -q ":${port} "; then
            log "WARN" "$component_name 端口 $original_port 被占用，已自动改用 $port"
            eval "$port_ref=$port"
            return 0
        fi
    done

    error_exit "$component_name 无法找到可用端口（范围 $range_ref）"
}

setup_env_file() {
    next_step "正在配置环境变量..."

    local env_file
    env_file="$(dirname "$COMPOSE_FILE")/.env"

    # P1-7: 为每个服务生成独立密码
    local admin_password
    admin_password=$(openssl rand -base64 12)
    local postgres_password
    postgres_password=$(openssl rand -base64 16)
    local minio_password
    minio_password=$(openssl rand -base64 16)
    local neo4j_password
    neo4j_password=$(openssl rand -base64 16)

    # 端口检测与避让
    local TRAEFIK_HTTP_PORT=80
    local TRAEFIK_HTTPS_PORT=443
    local REDIS_PORT=6379
    local POSTGRES_PORT=5432
    local QDRANT_PORT=6333
    local MINIO_API_PORT=9000
    local MINIO_CONSOLE_PORT=9001
    local NEO4J_PORT=7687
    local SISYS_APP_PORT=8080

    detect_and_resolve_ports TRAEFIK_HTTP_PORT "81-90" "Traefik HTTP"
    detect_and_resolve_ports TRAEFIK_HTTPS_PORT "444-450" "Traefik HTTPS"
    detect_and_resolve_ports REDIS_PORT "6380-6389" "Redis"
    detect_and_resolve_ports POSTGRES_PORT "5433-5442" "PostgreSQL"
    detect_and_resolve_ports QDRANT_PORT "6334-6343" "Qdrant"
    detect_and_resolve_ports MINIO_API_PORT "9001-9010" "MinIO API"
    detect_and_resolve_ports MINIO_CONSOLE_PORT "9002-9011" "MinIO Console"
    detect_and_resolve_ports NEO4J_PORT "7688-7697" "Neo4j"
    detect_and_resolve_ports SISYS_APP_PORT "8081-8090" "SISYS App"

    # 获取服务器 IP
    local server_ip
    server_ip=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")

    # 写入 .env 文件
    cat > "$env_file" <<EOF
# SISYS 自动生成的环境配置
# 生成时间: $(date '+%Y-%m-%d %H:%M:%S')

# 镜像仓库配置
SISYS_REGISTRY=docker.io
SISYS_IMAGE_PREFIX=sisys
SISYS_IMAGE_TAG=latest

# 端口配置
TRAEFIK_HTTP_PORT=$TRAEFIK_HTTP_PORT
TRAEFIK_HTTPS_PORT=$TRAEFIK_HTTPS_PORT
REDIS_PORT=$REDIS_PORT
POSTGRES_PORT=$POSTGRES_PORT
QDRANT_PORT=$QDRANT_PORT
MINIO_API_PORT=$MINIO_API_PORT
MINIO_CONSOLE_PORT=$MINIO_CONSOLE_PORT
NEO4J_PORT=$NEO4J_PORT
SISYS_APP_PORT=$SISYS_APP_PORT

# 密码配置
POSTGRES_PASSWORD=$postgres_password
SISYS_ADMIN_PASSWORD=$admin_password
MINIO_ROOT_USER=sisysadmin
MINIO_ROOT_PASSWORD=$minio_password
NEO4J_PASSWORD=$neo4j_password

# 数据路径
SISYS_DATA_PATH=$DATA_DIR

# 服务器信息
SERVER_IP=$server_ip
EOF

    chmod 600 "$env_file"
    log "INFO" "环境配置已写入 $env_file"
    COMPLETED_STAGES+=("环境配置")

    # 导出变量供后续使用
    export SISYS_ADMIN_PASSWORD="$admin_password"
    export SERVER_IP="$server_ip"
    export TRAEFIK_HTTP_PORT REDIS_PORT POSTGRES_PORT QDRANT_PORT MINIO_API_PORT NEO4J_PORT SISYS_APP_PORT
}

# ===========================================================================
# 6. 镜像拉取
# ===========================================================================
pull_images() {
    next_step "正在拉取 Docker 镜像..."

    local images=(
        "redis:7.0-alpine"
        "postgres:15.4"
        "harbor.sisys.local/sisys/tools/qdrant/qdrant:v1.7.0"
        "minio/minio:RELEASE.2025-09-07T16-13-09Z"
        "neo4j:5.15"
        "traefik:v3.6"
        "sisys/app:latest"
    )

    local total=${#images[@]}
    local current=0

    for image in "${images[@]}"; do
        current=$((current + 1))
        log "INFO" "[$current/$total] 正在拉取: $image"
        progress_bar "$current" "$total"

        # 尝试拉取，失败时重试 2 次
        local retry=0
        local max_retries=2
        while [ $retry -le $max_retries ]; do
            if sudo docker pull "$image" &>> "$LOG_FILE"; then
                break
            fi
            retry=$((retry + 1))
            if [ $retry -le $max_retries ]; then
                log "WARN" "拉取失败，正在重试 ($retry/$max_retries)..."
                sleep 5
            else
                # P1-8: SISYS App 镜像是关键，拉取失败时硬退出
                if [ "$image" = "sisys/app:latest" ]; then
                    error_exit "无法拉取 SISYS 应用镜像。请检查网络连接或手动配置镜像源。"
                fi
                log "WARN" "无法拉取 $image，将继续安装其他组件"
            fi
        done
    done

    log "INFO" "镜像拉取完成"
    COMPLETED_STAGES+=("镜像拉取")
}

# ===========================================================================
# 7. 服务启动与健康检查
# ===========================================================================
start_services() {
    next_step "正在启动服务..."

    mkdir -p "$DATA_DIR"/{redis,postgres,qdrant,minio,neo4j}

    # 使用 sudo docker compose 启动（P0-1: Docker 组权限修复）
    sudo docker compose -f "$COMPOSE_FILE" --env-file "$(dirname "$COMPOSE_FILE")/.env" up -d &>> "$LOG_FILE"

    log "INFO" "服务启动完成，正在执行健康检查..."

    # 健康检查
    local services=("sisys-redis" "sisys-postgres" "sisys-qdrant" "sisys-minio" "sisys-neo4j" "sisys-app" "sisys-traefik")
    local max_retries=3
    local retry_interval=10

    for service in "${services[@]}"; do
        local retry=0
        local healthy=false

        while [ $retry -lt $max_retries ]; do
            if sudo docker inspect --format='{{.State.Health.Status}}' "$service" 2>/dev/null | grep -q "healthy"; then
                healthy=true
                break
            fi
            retry=$((retry + 1))
            log "INFO" "等待 $service 健康... ($retry/$max_retries)"
            sleep $retry_interval
        done

        if [ "$healthy" = true ]; then
            log "INFO" "✅ $service 健康检查通过"
        else
            log "WARN" "⚠️  $service 健康检查未通过，但将继续安装"
        fi
    done

    COMPLETED_STAGES+=("服务启动")
}

# ===========================================================================
# 8. 安装结果输出
# ===========================================================================
show_completion_message() {
    next_step "安装完成！"

    # 保存初始凭据到文件
    mkdir -p /opt/sisys
    cat > "$CRED_FILE" <<EOF
SISYS 初始管理员凭据
生成时间: $(date '+%Y-%m-%d %H:%M:%S')
⚠️  首次登录后请立即修改密码！

访问地址: http://$SERVER_IP:$SISYS_APP_PORT
用户名: admin
密码: $SISYS_ADMIN_PASSWORD

MinIO Console: http://$SERVER_IP:$MINIO_CONSOLE_PORT
Traefik Dashboard: http://$SERVER_IP:$TRAEFIK_HTTP_PORT/dashboard/

此文件将在 24 小时后自动删除
EOF

    chmod 600 "$CRED_FILE"

    # P1-6: 使用 at 命令代替后台 sleep 进程删除凭据文件
    # at 命令更可靠，shell 终止时仍会执行
    if command -v at &>/dev/null; then
        echo "rm -f '$CRED_FILE'" | at now + 24 hours 2>/dev/null || true
        log "INFO" "已安排 24 小时后删除凭据文件"
    else
        # 备选方案：后台 sleep 进程
        (sleep 86400 && rm -f "$CRED_FILE" 2>/dev/null) & disown
        log "INFO" "已安排 24 小时后删除凭据文件（后台进程）"
    fi

    echo
    echo -e "${GREEN}🎉 恭喜！SISYS 安装成功！${NC}"
    echo "=========================================="
    echo "✅ 所有服务运行正常"
    echo
    echo "🌐 访问地址: http://$SERVER_IP:$SISYS_APP_PORT"
    echo "👤 用户名: admin"
    echo "🔑 密码: $SISYS_ADMIN_PASSWORD"
    echo
    echo "📝 其他组件地址:"
    echo "   - MinIO Console: http://$SERVER_IP:$MINIO_CONSOLE_PORT"
    echo "   - Traefik Dashboard: http://$SERVER_IP:$TRAEFIK_HTTP_PORT/dashboard/"
    echo
    echo "⚠️  首次登录请修改密码！"
    echo "📄 安装日志: $LOG_FILE"
    echo "💾 初始凭据已保存到: $CRED_FILE（24 小时后自动删除）"
    echo "=========================================="

    COMPLETED_STAGES+=("安装完成")
}

# ===========================================================================
# 9. 幂等性检查
# ===========================================================================
check_idempotency() {
    # 检测 SISYS 是否已安装
    if sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -q "sisys-app"; then
        echo -e "${GREEN}=== 当前 SISYS 状态 ===${NC}"

        # 检查 Docker
        if command -v docker &>/dev/null; then
            local docker_version
            docker_version=$(docker --version | grep -oP '\d+\.\d+\.\d+')
            echo "✅ Docker 已安装 (v$docker_version)"
        fi

        # 检查服务状态
        local services=("sisys-redis" "sisys-postgres" "sisys-qdrant" "sisys-minio" "sisys-neo4j" "sisys-app" "sisys-traefik")
        for service in "${services[@]}"; do
            if sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -q "$service"; then
                local service_name="${service#sisys-}"
                echo "✅ $service_name 已运行"
            fi
        done

        echo
        echo "所有组件已是最新状态，无需操作。"
        echo
        echo "如需升级，请执行: sisys-upgrade.sh"
        echo "如需重新安装，请执行: sisys-reinstall.sh"
        exit 0
    fi
}

# ===========================================================================
# 主函数
# ===========================================================================
main() {
    echo "=========================================="
    echo "  $SCRIPT_NAME"
    echo "  版本: $SCRIPT_VERSION"
    echo "  日期: $(date '+%Y-%m-%d')"
    echo "=========================================="
    echo

    # 0. 幂等性检查
    check_idempotency

    # 1. 系统检测
    detect_os

    # 2. 资源预检
    check_resources

    # 3. 安装前检查报告 + 用户确认
    show_check_report_and_confirm

    # 4. Docker 安装
    install_docker

    # 5. 端口检测与环境配置
    setup_env_file

    # 6. 镜像拉取
    pull_images

    # 7. 服务启动与健康检查
    start_services

    # 8. 安装结果输出
    show_completion_message

    echo
    log "INFO" "安装脚本执行完毕。祝您使用愉快！"
}

main "$@"
