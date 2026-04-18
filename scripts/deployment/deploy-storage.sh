#!/bin/bash
# =============================================================================
# SISYS 五层存储统一部署脚本
# =============================================================================
# 用途：一键部署 Redis/PostgreSQL/Qdrant/MinIO/Neo4j
# Story: 1.4-1.8 (五层存储架构)
# =============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 部署模式
MODE="${1:-dev}"  # 默认 dev，可指定 prod

# 部署目录
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../deploy" && pwd)"

# MinIO 版本（统一维护）
MINIO_VERSION="RELEASE.2025-09-07T16-13-09Z"

echo "=========================================="
echo "SISYS 五层存储部署脚本"
echo "=========================================="
echo "部署目录: $DEPLOY_DIR"
echo "部署模式: $MODE"
echo "=========================================="

# -----------------------------------------------------------------------------
# 步骤 1: 环境检查
# -----------------------------------------------------------------------------
echo -e "\n${GREEN}[1/5] 环境检查...${NC}"

# 检查 docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: docker 未安装${NC}"
    exit 1
fi

# 检查 docker compose
if ! docker compose version &> /dev/null; then
    echo -e "${RED}错误: docker compose 未安装${NC}"
    exit 1
fi

echo "  Docker 版本: $(docker --version | cut -d' ' -f3 | tr -d ',')"
echo "  Docker Compose 版本: $(docker compose version | cut -d' ' -f4)"

# -----------------------------------------------------------------------------
# 步骤 2: 创建环境变量文件
# -----------------------------------------------------------------------------
echo -e "\n${GREEN}[2/5] 环境变量配置...${NC}"

ENV_FILE="$DEPLOY_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$DEPLOY_DIR/.env.example" ]; then
        cp "$DEPLOY_DIR/.env.example" "$ENV_FILE"
        echo -e "  ${YELLOW}警告: 已从 .env.example 创建 .env，请检查配置！${NC}"
    else
        echo -e "  ${RED}错误: .env.example 不存在${NC}"
        exit 1
    fi
else
    echo "  .env 文件已存在"
fi

# 检查密码配置（生产环境）
if [ "$MODE" = "prod" ]; then
    source "$ENV_FILE"
    ISSUES=0

    if [ -z "$REDIS_PASSWORD" ] || [ "$REDIS_PASSWORD" = "your-secure-password-here" ]; then  # pragma: allowlist secret
        echo -e "  ${RED}错误: REDIS_PASSWORD 未配置${NC}"
        ISSUES=1
    fi

    if [ -z "$POSTGRES_PASSWORD" ] || [ "$POSTGRES_PASSWORD" = "your-secure-password-here" ]; then  # pragma: allowlist secret
        echo -e "  ${RED}错误: POSTGRES_PASSWORD 未配置${NC}"
        ISSUES=1
    fi

    if [ -z "$QDRANT_API_KEY" ] || [ "$QDRANT_API_KEY" = "your-secure-api-key-here" ]; then  # pragma: allowlist secret
        echo -e "  ${RED}错误: QDRANT_API_KEY 未配置${NC}"
        ISSUES=1
    fi

    if [ -z "$MINIO_ROOT_PASSWORD" ] || [ "$MINIO_ROOT_PASSWORD" = "your-secure-key-here" ]; then # pragma: allowlist secret
        echo -e "  ${RED}错误: MINIO_ROOT_PASSWORD 未配置${NC}"
        ISSUES=1
    fi

    if [ -z "$NEO4J_PASSWORD" ] || [ "$NEO4J_PASSWORD" = "your-secure-password-here" ]; then  # pragma: allowlist secret
        echo -e "  ${RED}错误: NEO4J_PASSWORD 未配置${NC}"
        ISSUES=1
    fi

    if [ $ISSUES -eq 1 ]; then
        echo -e "\n${RED}生产环境部署失败: 请在 .env 中配置所有密码${NC}"
        exit 1
    fi
fi

# -----------------------------------------------------------------------------
# 步骤 3: 选择 docker-compose 文件
# -----------------------------------------------------------------------------
echo -e "\n${GREEN}[3/5] 部署配置...${NC}"

if [ "$MODE" = "prod" ]; then
    echo "  使用独立服务生产配置"
else
    echo "  使用统一开发配置"
fi

# -----------------------------------------------------------------------------
# 步骤 4: 拉取镜像
# -----------------------------------------------------------------------------
echo -e "\n${GREEN}[4/5] 拉取镜像...${NC}"

echo "  拉取 Redis 7.2.5..."
docker pull harbor.sisys.local/sisys/tools/redis/redis:7.2.5 2>/dev/null || true

echo "  拉取 PostgreSQL 15.4..."
docker pull harbor.sisys.local/sisys/tools/postgres/postgres:15.4 2>/dev/null || true

echo "  拉取 Qdrant v1.7.1..."
docker pull harbor.sisys.local/sisys/tools/qdrant/qdrant:v1.7.1 2>/dev/null || true

echo "  拉取 MinIO ${MINIO_VERSION}..."
docker pull harbor.sisys.local/sisys/tools/minio:${MINIO_VERSION} 2>/dev/null || true

echo "  拉取 Neo4j 5.15..."
docker pull harbor.sisys.local/sisys/tools/neo4j/neo4j:5.15 2>/dev/null || true

# -----------------------------------------------------------------------------
# 步骤 5: 启动服务
# -----------------------------------------------------------------------------
echo -e "\n${GREEN}[5/5] 启动服务...${NC}"

echo "  创建网络..."
docker network create sisys-network 2>/dev/null || echo "  网络已存在"

# 根据模式选择不同的启动方式
if [ "$MODE" = "prod" ]; then
    # 生产环境：使用各服务独立的 docker-compose.prod.yml
    for svc in redis postgresql qdrant minio neo4j; do
        if [ -f "$DEPLOY_DIR/$svc/docker-compose.prod.yml" ]; then
            echo "  启动 $svc (prod)..."
            docker compose -f "$DEPLOY_DIR/$svc/docker-compose.prod.yml" up -d
        fi
    done
else
    # 开发环境：使用统一配置
    docker compose -f "$DEPLOY_DIR/docker-compose.yml" up -d
fi

# -----------------------------------------------------------------------------
# 健康检查
# -----------------------------------------------------------------------------
echo -e "\n${GREEN}等待服务就绪...${NC}"

sleep 10

# Redis 健康检查
echo -n "  Redis: "
if docker exec sisys-redis redis-cli ping &>/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
elif docker exec sisys-redis-prod redis-cli ping &>/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⏳${NC}"
fi

# PostgreSQL 健康检查
echo -n "  PostgreSQL: "
if docker exec sisys-postgres pg_isready -U postgres &>/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
elif docker exec sisys-postgres-prod pg_isready -U postgres &>/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⏳${NC}"
fi

# Qdrant 健康检查
echo -n "  Qdrant: "
if curl -sf http://localhost:6333/healthz &>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⏳${NC}"
fi

# MinIO 健康检查
echo -n "  MinIO: "
if docker exec sisys-minio mc ready local &>/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
elif docker exec sisys-minio-prod mc ready local &>/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⏳${NC}"
fi

# Neo4j 健康检查
echo -n "  Neo4j: "
if curl -sf http://localhost:7474/health &>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⏳${NC}"
fi

# -----------------------------------------------------------------------------
# 完成信息
# -----------------------------------------------------------------------------
echo ""
echo "=========================================="
echo -e "${GREEN}部署完成！${NC}"
echo "=========================================="
echo ""
echo "服务访问地址:"
echo "  Redis:     localhost:6379"
echo "  PostgreSQL: localhost:5432"
echo "  Qdrant:    localhost:6333 (REST), 6334 (gRPC)"
echo "  MinIO:     localhost:9000 (API), 9001 (Console)"
echo "  Neo4j:     localhost:7474 (HTTP), 7687 (Bolt)"
echo ""
echo "常用命令:"
if [ "$MODE" = "prod" ]; then
    echo "  查看状态: docker compose -f deploy/\$svc/docker-compose.prod.yml ps"
    echo "  查看日志: docker compose -f deploy/\$svc/docker-compose.prod.yml logs -f \$svc"
    echo "  停止服务: docker compose -f deploy/\$svc/docker-compose.prod.yml down"
else
    echo "  查看状态: docker compose -f $DEPLOY_DIR/docker-compose.yml ps"
    echo "  查看日志: docker compose -f $DEPLOY_DIR/docker-compose.yml logs -f"
    echo "  停止服务: docker compose -f $DEPLOY_DIR/docker-compose.yml down"
fi
echo ""
