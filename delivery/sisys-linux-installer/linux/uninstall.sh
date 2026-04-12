#!/bin/bash
###############################################################################
# SISYS 企业应用 - Linux 卸载脚本
# 用法: sudo bash uninstall.sh [--purge]
###############################################################################

set -euo pipefail

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m'

PURGE_MODE=false

# 解析参数
if [[ "${1:-}" == "--purge" ]]; then
    PURGE_MODE=true
fi

echo -e "${GREEN}=== SISYS 卸载程序 ===${NC}"
echo

# 1. 停止服务
echo -e "${YELLOW}正在停止 SISYS 服务...${NC}"
if command -v docker &>/dev/null; then
    docker compose -f "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/docker-compose.yml" down 2>/dev/null || true
    echo -e "${GREEN}✅ 服务已停止${NC}"
else
    echo -e "${YELLOW}⚠️  Docker 未安装，跳过${NC}"
fi

# 2. 删除 Docker 容器/镜像/网络
echo -e "${YELLOW}正在清理 Docker 资源...${NC}"
if command -v docker &>/dev/null; then
    docker compose -f "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/docker-compose.yml" down --rmi local --remove-orphans 2>/dev/null || true
    echo -e "${GREEN}✅ Docker 资源已清理${NC}"
fi

# 3. 数据清理
if [ "$PURGE_MODE" = true ]; then
    echo -e "${RED}⚠️  警告: 将删除所有 SISYS 数据（不可恢复）${NC}"
    echo -n "确认删除所有数据？[y/N]: "
    read -r confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}正在删除数据目录...${NC}"
        rm -rf /opt/sisys
        rm -f /var/log/sisys/install.log
        echo -e "${GREEN}✅ 所有数据已删除${NC}"
    else
        echo -e "${YELLOW}取消删除数据${NC}"
    fi
else
    echo -e "${GREEN}✅ 用户数据已保留 (/opt/sisys/data/)${NC}"
    echo -e "   如需彻底删除，请执行: sudo bash $(basename "$0") --purge"
fi

echo
echo -e "${GREEN}=== SISYS 卸载完成 ===${NC}"
