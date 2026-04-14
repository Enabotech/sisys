#!/usr/bin/env bash
# =============================================================================
# Qdrant 健康检查脚本
# =============================================================================
# 用途：验证 Qdrant 服务是否正常运行并满足 Story 1.6 要求
# 用法：./scripts/check-qdrant.sh
# =============================================================================

set -euo pipefail

# 配置
QDRANT_HOST="${QDRANT_HOST:-localhost}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
QDRANT_URL="http://${QDRANT_HOST}:${QDRANT_PORT}"
TIMEOUT=10
MAX_RETRIES=5

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "Qdrant 健康检查"
echo "========================================="
echo "URL: ${QDRANT_URL}"
echo "超时: ${TIMEOUT}s"
echo "最大重试次数: ${MAX_RETRIES}"
echo ""

# 检查 1: Qdrant 服务是否可访问
echo -n "检查 1/5: Qdrant 服务连接... "
for i in $(seq 1 $MAX_RETRIES); do
    if curl -sf --max-time $TIMEOUT "${QDRANT_URL}/healthz" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 通过${NC}"
        break
    fi
    if [ $i -eq $MAX_RETRIES ]; then
        echo -e "${RED}❌ 失败（重试 $i/$MAX_RETRIES）${NC}"
        echo "错误：无法连接到 Qdrant 服务"
        echo "请确认："
        echo "  1. Qdrant 服务已启动：docker compose -f deploy/qdrant/docker-compose.yml up -d"
        echo "  2. 端口未被占用：lsof -i :${QDRANT_PORT}"
        exit 1
    fi
    echo -n "."
    sleep 2
done

# 检查 2: Qdrant 版本是否正确（需要 v1.7.0+）
echo -n "检查 2/5: Qdrant 版本验证... "
VERSION=$(curl -sf --max-time $TIMEOUT "${QDRANT_URL}" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
if [ -z "$VERSION" ]; then
    echo -e "${YELLOW}⚠️  无法获取版本信息${NC}"
else
    MAJOR=$(echo $VERSION | cut -d'.' -f1)
    MINOR=$(echo $VERSION | cut -d'.' -f2)
    if [ "$MAJOR" -ge 1 ] && [ "$MINOR" -ge 7 ]; then
        echo -e "${GREEN}✅ 版本 ${VERSION}（满足 v1.7+ 要求）${NC}"
    else
        echo -e "${RED}❌ 版本 ${VERSION}（需要 v1.7+）${NC}"
        exit 1
    fi
fi

# 检查 3: REST API 是否正常
echo -n "检查 3/5: REST API 健康... "
if curl -sf --max-time $TIMEOUT "${QDRANT_URL}/collections" | grep -q '"status":"ok"'; then
    echo -e "${GREEN}✅ 通过${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
    exit 1
fi

# 检查 4: 创建测试 Collection 验证写入
echo -n "检查 4/5: Collection 创建测试... "
TEST_COLLECTION="sisys:healthcheck:test"
curl -sf --max-time $TIMEOUT -X PUT "${QDRANT_URL}/collections/${TEST_COLLECTION}" \
    -H "Content-Type: application/json" \
    -d '{
        "vectors": {
            "size": 1024,
            "distance": "Cosine"
        }
    }' > /dev/null 2>&1

if curl -sf --max-time $TIMEOUT "${QDRANT_URL}/collections/${TEST_COLLECTION}" | grep -q '"status":"green"'; then
    echo -e "${GREEN}✅ 通过${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
    exit 1
fi

# 检查 5: 清理测试 Collection
echo -n "检查 5/5: Collection 清理... "
if curl -sf --max-time $TIMEOUT -X DELETE "${QDRANT_URL}/collections/${TEST_COLLECTION}" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 通过${NC}"
else
    echo -e "${YELLOW}⚠️  清理失败（可手动删除）${NC}"
fi

echo ""
echo "========================================="
echo -e "${GREEN}✅ 所有检查通过！Qdrant 服务正常${NC}"
echo "========================================="
echo ""
echo "下一步："
echo "  1. 运行集成测试: poetry run pytest tests/integration/test_qdrant_integration.py -v"
echo "  2. 查看文档: cat docs/infrastructure/qdrant-deployment-guide.md"
echo ""
