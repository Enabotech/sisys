#!/bin/bash
# SISYS 首次启动脚本
# 用途：检测环境、拉取镜像、启动服务、显示访问信息

set -euo pipefail

# ============================================================================
# 配置
# ============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESOURCES_DIR="$APP_DIR/Contents/Resources"
DATA_DIR="$HOME/Library/Application Support/Sisys"
LOG_FILE="$DATA_DIR/first-run.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# 日志函数
# ============================================================================
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
    
    case "$level" in
        INFO)    echo -e "${BLUE}[INFO]${NC} $message" ;;
        SUCCESS) echo -e "${GREEN}[✓]${NC} $message" ;;
        WARNING) echo -e "${YELLOW}[⚠]${NC} $message" ;;
        ERROR)   echo -e "${RED}[✗]${NC} $message" ;;
    esac
}

# ============================================================================
# 进度条函数
# ============================================================================
show_progress() {
    local current=$1
    local total=$2
    local message=$3
    local percent=$((current * 100 / total))
    local filled=$((percent / 2))
    local empty=$((50 - filled))
    
    printf "\r${BLUE}[%-${filled}s%${empty}s]${NC} %3d%% - %s" \
        "$(printf '#%.0s' $(seq 1 $filled))" "" "$percent" "$message"
    
    if [ "$current" -eq "$total" ]; then
        echo ""
    fi
}

# ============================================================================
# 回滚函数
# ============================================================================
rollback() {
    log ERROR "安装失败，正在回滚..."
    
    # 停止并删除容器
    if [ -f "$RESOURCES_DIR/docker-compose.yml" ]; then
        cd "$RESOURCES_DIR"
        docker compose down -v 2>/dev/null || true
    fi
    
    # 删除数据目录
    if [ -d "$DATA_DIR" ]; then
        rm -rf "$DATA_DIR"
    fi
    
    # 删除 LaunchAgent
    local plist_path="$HOME/Library/LaunchAgents/com.sisys.app.plist"
    if [ -f "$plist_path" ]; then
        launchctl unload "$plist_path" 2>/dev/null || true
        rm -f "$plist_path"
    fi
    
    log ERROR "回滚完成。请检查错误信息后重新运行。"
    exit 1
}

# 捕获错误
trap rollback ERR

# ============================================================================
# 步骤 1: 检查系统环境
# ============================================================================
step_check_system() {
    log INFO "步骤 1/5: 正在检查系统环境..."
    
    # 检查 macOS 版本
    local macos_version
    if command -v sw_vers &> /dev/null; then
        macos_version=$(sw_vers -productVersion)
        local major_version=$(echo "$macos_version" | cut -d. -f1)
        if [ "$major_version" -lt 12 ]; then
            log ERROR "macOS 版本过低: $macos_version (需要 12.0+)"
            exit 1
        fi
        log SUCCESS "macOS 版本: $macos_version"
    fi
    
    # 检查磁盘空间 (≥ 40GB)
    local free_space_kb
    free_space_kb=$(df -k / | tail -1 | awk '{print $4}')
    local free_space_gb=$((free_space_kb / 1024 / 1024))
    if [ "$free_space_gb" -lt 40 ]; then
        log ERROR "磁盘空间不足: ${free_space_gb}GB (需要 ≥ 40GB)"
        exit 1
    fi
    log SUCCESS "磁盘空间: ${free_space_gb}GB"
    
    # 检查内存 (≥ 16GB)
    if command -v sysctl &> /dev/null; then
        local memory_bytes
        memory_bytes=$(sysctl -n hw.memsize 2>/dev/null || echo "0")
        local memory_gb=$((memory_bytes / 1024 / 1024 / 1024))
        if [ "$memory_gb" -lt 16 ]; then
            log WARNING "内存较低: ${memory_gb}GB (推荐 ≥ 16GB)"
        else
            log SUCCESS "内存: ${memory_gb}GB"
        fi
    fi
}

# ============================================================================
# 步骤 2: 检查 Docker
# ============================================================================
step_check_docker() {
    log INFO "步骤 2/5: 正在检查 Docker..."
    
    # 检查 Docker 是否安装
    if ! command -v docker &> /dev/null; then
        log ERROR "Docker 未安装"
        echo ""
        echo -e "${YELLOW}SISYS 需要 Docker Desktop 作为运行环境（免费）${NC}"
        echo "请按照以下步骤安装:"
        echo ""
        echo "1. 访问: https://www.docker.com/products/docker-desktop"
        echo "2. 下载并安装 Docker Desktop"
        echo "3. 启动 Docker Desktop 应用程序"
        echo "4. 重新运行 SISYS 安装"
        echo ""
        echo "预计额外需要约 10 分钟完成 Docker 安装"
        exit 1
    fi
    log SUCCESS "Docker 已安装: $(docker --version)"
    
    # 检查 Docker daemon 是否运行
    if ! docker info &> /dev/null; then
        log ERROR "Docker daemon 未运行"
        echo ""
        echo -e "${YELLOW}请启动 Docker Desktop 应用程序${NC}"
        echo "然后重新运行 SISYS 安装"
        exit 1
    fi
    log SUCCESS "Docker daemon: 运行中"
    
    # 检查 Docker Compose
    if ! docker compose version &> /dev/null; then
        log ERROR "Docker Compose 未安装"
        exit 1
    fi
    log SUCCESS "Docker Compose: $(docker compose version)"
}

# ============================================================================
# 步骤 3: 创建数据目录
# ============================================================================
step_create_dirs() {
    log INFO "步骤 3/5: 正在创建数据目录..."
    
    mkdir -p "$DATA_DIR/data"
    mkdir -p "$DATA_DIR/config"
    mkdir -p "$DATA_DIR/logs"
    
    # 复制 docker-compose.yml
    if [ -f "$RESOURCES_DIR/docker-compose.yml" ]; then
        cp "$RESOURCES_DIR/docker-compose.yml" "$DATA_DIR/docker-compose.yml"
        log SUCCESS "数据目录已创建: $DATA_DIR"
    else
        log ERROR "docker-compose.yml 未找到"
        exit 1
    fi
    
    # 复制 .env.example
    if [ -f "$RESOURCES_DIR/.env.example" ]; then
        if [ ! -f "$DATA_DIR/.env" ]; then
            cp "$RESOURCES_DIR/.env.example" "$DATA_DIR/.env"
            log INFO "已创建配置文件: $DATA_DIR/.env"
        fi
    fi
}

# ============================================================================
# 步骤 4: 拉取镜像
# ============================================================================
step_pull_images() {
    log INFO "步骤 4/5: 正在拉取 Docker 镜像..."
    echo ""

    cd "$DATA_DIR"

    # 验证 docker-compose.yml 语法
    log INFO "验证 Docker Compose 配置..."
    if ! docker compose config > /dev/null 2>&1; then
        log ERROR "Docker Compose 配置有语法错误"
        docker compose config 2>&1 || true
        exit 1
    fi
    log SUCCESS "Docker Compose 配置验证通过"

    # 加载环境变量
    if [ -f "$DATA_DIR/.env" ]; then
        export $(cat "$DATA_DIR/.env" | grep -v '#' | xargs)
    fi
    
    # 显示进度
    local services=("postgres" "redis" "qdrant" "minio" "neo4j" "sisys")
    local total=${#services[@]}
    local current=0
    
    for service in "${services[@]}"; do
        current=$((current + 1))
        show_progress $current $total "正在拉取 $service 镜像..."
        
        if ! docker compose pull "$service" 2>/dev/null; then
            log WARNING "拉取 $service 失败，尝试使用国内镜像源..."
            
            # 提示配置国内镜像
            echo ""
            echo -e "${YELLOW}建议配置 Docker 国内镜像源以加速下载${NC}"
            echo "请参考: https://github.com/moby/moby/issues/47150"
            echo ""
            
            log ERROR "镜像拉取失败: $service"
            exit 1
        fi
    done
    
    echo ""
    log SUCCESS "所有镜像拉取完成"
}

# ============================================================================
# 步骤 5: 启动服务
# ============================================================================
step_start_services() {
    log INFO "步骤 5/5: 正在启动服务..."
    echo ""
    
    cd "$DATA_DIR"
    
    # 启动服务
    docker compose up -d
    
    # 等待服务就绪
    log INFO "等待服务健康检查..."
    local max_wait=120
    local waited=0
    
    while [ $waited -lt $max_wait ]; do
        local healthy_count=0
        local total_services=6
        
        for service in postgres redis qdrant minio neo4j sisys; do
            if docker compose ps "$service" 2>/dev/null | grep -q "healthy"; then
                healthy_count=$((healthy_count + 1))
            fi
        done
        
        if [ $healthy_count -eq $total_services ]; then
            break
        fi
        
        show_progress $((waited * 100 / max_wait)) 100 "服务启动中... ($healthy_count/$total_services 就绪)"
        sleep 5
        waited=$((waited + 5))
    done
    
    echo ""
    
    if [ $waited -ge $max_wait ]; then
        log WARNING "服务启动超时，部分服务可能未就绪"
    else
        log SUCCESS "所有服务已就绪 ($waited 秒)"
    fi
}

# ============================================================================
# 显示完成信息
# ============================================================================
show_completion() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}              ${GREEN}SISYS 安装完成！${NC}                          ${GREEN}║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # 检测实际端口
    local port=${SISYS_PORT:-8080}
    local actual_port=$(docker compose port sisys 8080 2>/dev/null | cut -d: -f2 || echo "$port")
    
    echo -e "${BLUE}访问地址:${NC} http://localhost:$actual_port"
    echo ""
    
    # 生成初始密码
    if [ -z "$SISYS_ADMIN_PASSWORD" ]; then
        local admin_password=""
        
        # 尝试多种方法生成随机密码
        if command -v openssl &> /dev/null; then
            admin_password=$(openssl rand -base64 12 2>/dev/null | tr -d '\n')
        elif [ -c /dev/urandom ]; then
            admin_password=$(head -c 16 /dev/urandom | base64 | tr -d '\n')
        fi
        
        # 验证密码不为空
        if [ -z "$admin_password" ] || [ ${#admin_password} -lt 12 ]; then
            log ERROR "无法生成安全的随机密码"
            exit 1
        fi
        
        export SISYS_ADMIN_PASSWORD="$admin_password"
    fi
    
    echo -e "${YELLOW}⚠ 重要：请保存初始管理员密码${NC}"
    echo "密码: $SISYS_ADMIN_PASSWORD"
    echo ""
    echo -e "${YELLOW}首次登录后需修改此密码${NC}"
    echo ""
    
    # 自动打开浏览器
    if command -v open &> /dev/null; then
        log INFO "正在打开浏览器..."
        open "http://localhost:$actual_port" 2>/dev/null || {
            log WARNING "无法自动打开浏览器"
            echo "请手动访问: http://localhost:$actual_port"
        }
    fi
    
    echo ""
    log SUCCESS "安装完成！"
    echo ""
    echo -e "${BLUE}常用命令:${NC}"
    echo "  sisys status   # 查看服务状态"
    echo "  sisys stop     # 停止服务"
    echo "  sisys start    # 启动服务"
    echo ""
}

# ============================================================================
# 主流程
# ============================================================================
main() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}         ${GREEN}SISYS 战略规划管理系统 v0.15${NC}                    ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}              首次安装向导                          ${BLUE}║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # 创建日志目录
    mkdir -p "$(dirname "$LOG_FILE")"
    
    step_check_system
    step_check_docker
    step_create_dirs
    step_pull_images
    step_start_services
    show_completion
}

# 运行主流程
main "$@"
