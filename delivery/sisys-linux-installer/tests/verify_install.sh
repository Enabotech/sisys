#!/bin/bash
###############################################################################
# SISYS 企业应用 - 安装验证脚本
# 用法: bash verify_install.sh
###############################################################################

set -uo pipefail  # P0-4: 移除 -e，避免首个检查失败时直接退出

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0

# P0-5: 从 .env 文件读取实际端口，避免与安装脚本的自动避让不匹配
ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/linux/.env"
if [ -f "$ENV_FILE" ]; then
    # shellcheck source=/dev/null
    source "$ENV_FILE"
else
    # 默认端口
    REDIS_PORT=6379
    POSTGRES_PORT=5432
    QDRANT_PORT=6333
    MINIO_API_PORT=9000
    NEO4J_PORT=7687
    SISYS_APP_PORT=8080
fi

# 验证函数
check_service() {
    local service_name="$1"
    local health_check="$2"
    local description="$3"

    echo -n "检查 $description... "

    # 检查容器是否运行
    if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${service_name}$"; then
        echo -e "${RED}❌ 失败 (容器未运行)${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return 1
    fi

    # 执行健康检查
    if eval "$health_check" &>/dev/null; then
        echo -e "${GREEN}✅ 通过${NC}"
        PASS_COUNT=$((PASS_COUNT + 1))
        return 0
    else
        echo -e "${YELLOW}⚠️  警告 (健康检查未通过)${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return 1
    fi
}

echo "=========================================="
echo "  SISYS 安装验证"
echo "=========================================="
echo

# 1. 检查所有 Docker 容器运行状态
echo "--- Docker 容器状态 ---"
check_service "sisys-redis" "docker inspect --format='{{.State.Health.Status}}' sisys-redis | grep -q healthy" "Redis"
check_service "sisys-postgres" "docker inspect --format='{{.State.Health.Status}}' sisys-postgres | grep -q healthy" "PostgreSQL"
check_service "sisys-qdrant" "docker inspect --format='{{.State.Health.Status}}' sisys-qdrant | grep -q healthy" "Qdrant"
check_service "sisys-minio" "docker inspect --format='{{.State.Health.Status}}' sisys-minio | grep -q healthy" "MinIO"
check_service "sisys-neo4j" "docker inspect --format='{{.State.Health.Status}}' sisys-neo4j | grep -q healthy" "Neo4j"
check_service "sisys-app" "docker inspect --format='{{.State.Health.Status}}' sisys-app 2>/dev/null | grep -q healthy || docker ps --format '{{.Names}}' | grep -q sisys-app" "SISYS App"
check_service "sisys-traefik" "docker inspect --format='{{.State.Health.Status}}' sisys-traefik 2>/dev/null | grep -q healthy || docker ps --format '{{.Names}}' | grep -q sisys-traefik" "Traefik"

echo
echo "--- 组件健康检查 ---"

# 2. 验证各组件端口可达性 + 3. 验证组件健康检查端点

# Redis PING
echo -n "检查 Redis PING... "
if docker exec sisys-redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
    echo -e "${GREEN}✅ PONG${NC}"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo -e "${RED}❌ 无响应${NC}"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

# PostgreSQL pg_isready
echo -n "检查 PostgreSQL 连接... "
if docker exec sisys-postgres pg_isready -U sisys 2>/dev/null | grep -q "accepting connections"; then
    echo -e "${GREEN}✅ accepting connections${NC}"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo -e "${RED}❌ 无法连接${NC}"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

# Qdrant /healthz
echo -n "检查 Qdrant 健康端点... "
if curl -sf "http://localhost:${QDRANT_PORT}/healthz" &>/dev/null; then
    echo -e "${GREEN}✅ 200 OK${NC}"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo -e "${RED}❌ 无法访问${NC}"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

# MinIO /minio/health/live
echo -n "检查 MinIO 健康端点... "
if curl -sf "http://localhost:${MINIO_API_PORT}/minio/health/live" &>/dev/null; then
    echo -e "${GREEN}✅ 200 OK${NC}"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo -e "${RED}❌ 无法访问${NC}"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

# Neo4j Bolt 端口 (P2-14: 使用 /dev/tcp 替代 nc)
echo -n "检查 Neo4j Bolt 端口... "
if (echo > /dev/tcp/localhost/${NEO4J_PORT}) 2>/dev/null; then
    echo -e "${GREEN}✅ 端口可达${NC}"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo -e "${RED}❌ 端口不可达${NC}"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

# SISYS App 首页访问
echo -n "检查 SISYS App 首页... "
if curl -sf "http://localhost:${SISYS_APP_PORT}/" &>/dev/null; then
    echo -e "${GREEN}✅ 可访问${NC}"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo -e "${YELLOW}⚠️  无法访问 (可能正在启动中)${NC}"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

# 4. 输出验证报告
echo
echo "=========================================="
echo "  验证报告"
echo "=========================================="
echo -e "✅ 通过: $PASS_COUNT"
echo -e "❌ 失败: $FAIL_COUNT"
echo

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}🎉 所有检查通过！SISYS 安装成功。${NC}"
    exit 0
else
    echo -e "${RED}⚠️  有 $FAIL_COUNT 项检查未通过。${NC}"
    echo "请查看安装日志: /var/log/sisys/install.log"
    exit 1
fi
