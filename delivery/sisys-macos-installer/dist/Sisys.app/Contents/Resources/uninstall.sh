#!/bin/bash
# SISYS 卸载脚本
# 用途：完整清理 SISYS 所有组件

set -euo pipefail

# ============================================================================
# 配置
# ============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESOURCES_DIR="$APP_DIR/Contents/Resources"
DATA_DIR="$HOME/Library/Application Support/Sisys"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# 确认对话框
# ============================================================================
confirm_uninstall() {
    echo ""
    echo -e "${YELLOW}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║${NC}              ${RED}卸载 SISYS 战略规划管理系统${NC}                ${YELLOW}║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${RED}⚠ 此操作将删除：${NC}"
    echo "  - 所有 SISYS Docker 容器"
    echo "  - 所有数据（数据库、缓存、向量、对象存储、图数据）"
    echo "  - 配置文件和日志"
    echo "  - LaunchAgent 注册"
    echo ""

    # 提示备份
    read -p "是否在卸载前备份数据？[y/N]: " backup_choice
    if [[ "$backup_choice" =~ ^[Yy]$ ]]; then
        backup_data
    fi

    read -p "确定要卸载 SISYS 吗？此操作不可逆 [y/N]: " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}卸载已取消${NC}"
        exit 0
    fi
}

# ============================================================================
# 备份数据
# ============================================================================
backup_data() {
    local backup_dir="$HOME/SISYS_Backup_$(date +%Y%m%d_%H%M%S)"

    echo ""
    log INFO "正在备份数据到: $backup_dir"

    mkdir -p "$backup_dir"

    if [ -d "$DATA_DIR" ]; then
        cp -r "$DATA_DIR" "$backup_dir/"
        log SUCCESS "数据备份完成"
    else
        log WARNING "未找到数据目录"
    fi
}

# ============================================================================
# 日志函数
# ============================================================================
log() {
    local level="$1"
    shift
    local message="$*"

    case "$level" in
        INFO)    echo -e "${BLUE}[INFO]${NC} $message" ;;
        SUCCESS) echo -e "${GREEN}[✓]${NC} $message" ;;
        WARNING) echo -e "${YELLOW}[⚠]${NC} $message" ;;
        ERROR)   echo -e "${RED}[✗]${NC} $message" ;;
    esac
}

# ============================================================================
# 步骤 1: 停止并删除 Docker 容器
# ============================================================================
step_stop_containers() {
    log INFO "步骤 1/5: 正在停止 Docker 容器..."

    if [ -f "$DATA_DIR/docker-compose.yml" ]; then
        cd "$DATA_DIR"

        # 停止所有容器
        if docker compose ps 2>/dev/null | grep -q "sisys"; then
            docker compose down -v
            log SUCCESS "容器已停止并删除"
        else
            log INFO "容器未运行"
        fi
    elif [ -f "$RESOURCES_DIR/docker-compose.yml" ]; then
        cd "$RESOURCES_DIR"

        if docker compose ps 2>/dev/null | grep -q "sisys"; then
            docker compose down -v
            log SUCCESS "容器已停止并删除"
        else
            log INFO "容器未运行"
        fi
    else
        log WARNING "未找到 docker-compose.yml"
    fi

    # 确保删除所有相关容器
    docker rm -f sisys-postgres sisys-redis sisys-qdrant sisys-minio sisys-neo4j sisys-app 2>/dev/null || true
    log SUCCESS "残留容器已清理"
}

# ============================================================================
# 步骤 2: 删除数据目录
# ============================================================================
step_remove_data() {
    log INFO "步骤 2/5: 正在删除数据目录..."

    # ⚠ 安全检查: 确保 DATA_DIR 不为空
    if [ -z "$DATA_DIR" ]; then
        log ERROR "DATA_DIR 环境变量未设置，拒绝删除"
        exit 1
    fi

    # ⚠ 安全检查: 确保 DATA_DIR 包含 Sisys 路径
    if [[ "$DATA_DIR" != *"Sisys"* ]]; then
        log ERROR "DATA_DIR 路径不包含 'Sisys'，拒绝删除: $DATA_DIR"
        exit 1
    fi

    if [ -d "$DATA_DIR" ]; then
        rm -rf "$DATA_DIR"
        log SUCCESS "数据目录已删除: $DATA_DIR"
    else
        log INFO "数据目录不存在"
    fi
}

# ============================================================================
# 步骤 3: 清理 LaunchAgent
# ============================================================================
step_remove_launch_agent() {
    log INFO "步骤 3/5: 正在清理 LaunchAgent..."

    local plist_path="$HOME/Library/LaunchAgents/com.sisys.app.plist"

    if [ -f "$plist_path" ]; then
        # 卸载
        launchctl unload "$plist_path" 2>/dev/null || true

        # 删除
        rm -f "$plist_path"

        log SUCCESS "LaunchAgent 已删除"
    else
        log INFO "LaunchAgent 不存在"
    fi
}

# ============================================================================
# 步骤 4: 清理 Keychain 密码
# ============================================================================
step_clear_keychain() {
    log INFO "步骤 4/5: 正在清理 Keychain 密码..."

    # 删除互联网密码
    security delete-internet-password -s "sisys" -a "sisys_admin" 2>/dev/null || true

    # 删除通用密码
    security delete-generic-password -s "sisys" 2>/dev/null || true
    security delete-generic-password -l "SISYS" 2>/dev/null || true

    log SUCCESS "Keychain 密码已清理"
}

# ============================================================================
# 步骤 5: 删除应用
# ============================================================================
step_remove_app() {
    log INFO "步骤 5/5: 正在删除应用..."

    if [ -d "$APP_DIR" ]; then
        rm -rf "$APP_DIR"
        log SUCCESS "应用已删除: $APP_DIR"
    else
        log INFO "应用目录不存在"
    fi
}

# ============================================================================
# 显示完成信息
# ============================================================================
show_completion() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}              ${GREEN}SISYS 卸载完成！${NC}                          ${GREEN}║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    log SUCCESS "所有组件已清理"
    echo ""
    echo -e "${BLUE}如需重新安装，请下载最新的安装包并运行${NC}"
    echo ""
}

# ============================================================================
# 主流程
# ============================================================================
main() {
    confirm_uninstall

    step_stop_containers
    step_remove_data
    step_remove_launch_agent
    step_clear_keychain
    step_remove_app

    show_completion
}

# 运行主流程
main "$@"
