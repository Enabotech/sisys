#!/bin/bash
# =============================================================================
# Gitea Webhook 配置脚本
# Story 0.7: Task 4 - Gitea 仓库集成
# 描述：配置 Gitea Webhook 触发 ArgoCD 自动同步
# =============================================================================

set -e

# 配置变量
GITEA_URL="${GITEA_URL:-https://gitea.sisys.local}"
GITEA_TOKEN="${GITEA_TOKEN:-}"
REPO="${REPO:-sisys/sisys}"
WEBHOOK_URL="${WEBHOOK_URL:-https://argocd.sisys.local/api/webhook}"
INSECURE="${INSECURE:-true}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "Gitea Webhook 配置脚本"
echo "========================================"
echo ""

# 检查 GITEA_TOKEN 是否已设置
if [ -z "$GITEA_TOKEN" ]; then
    echo -e "${RED}错误：GITEA_TOKEN 环境变量未设置${NC}"
    echo ""
    echo "获取 Token 步骤："
    echo "1. 登录 Gitea: $GITEA_URL"
    echo "2. 用户设置 → Applications → Generate New Token"
    echo "3. 权限：repository, user"
    echo "4. 复制 Token 并设置环境变量："
    echo "   export GITEA_TOKEN=<your_token>"
    echo ""
    exit 1
fi

# 检查 curl 是否已安装
if ! command -v curl &> /dev/null; then
    echo -e "${RED}错误：curl 未安装${NC}"
    exit 1
fi

# 配置 curl 参数
CURL_ARGS="-s"
if [ "$INSECURE" = "true" ]; then
    CURL_ARGS="$CURL_ARGS -k"
fi

echo "配置信息："
echo "  Gitea URL: $GITEA_URL"
echo "  仓库：$REPO"
echo "  Webhook URL: $WEBHOOK_URL"
echo "  跳过 TLS 验证：$INSECURE"
echo ""

# Step 1: 测试 Gitea API 连接
echo -e "${YELLOW}Step 1: 测试 Gitea API 连接...${NC}"
RESPONSE=$(curl $CURL_ARGS -w "\n%{http_code}" -X GET \
    -H "Authorization: token $GITEA_TOKEN" \
    -H "Content-Type: application/json" \
    "$GITEA_URL/api/v1/user")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ Gitea API 连接成功${NC}"
    USERNAME=$(echo "$BODY" | grep -o '"login":"[^"]*"' | cut -d'"' -f4)
    echo "  当前用户：$USERNAME"
else
    echo -e "${RED}✗ Gitea API 连接失败 (HTTP $HTTP_CODE)${NC}"
    echo "响应：$BODY"
    exit 1
fi
echo ""

# Step 2: 检查仓库是否存在
echo -e "${YELLOW}Step 2: 检查仓库是否存在...${NC}"
RESPONSE=$(curl $CURL_ARGS -w "\n%{http_code}" -X GET \
    -H "Authorization: token $GITEA_TOKEN" \
    -H "Content-Type: application/json" \
    "$GITEA_URL/api/v1/repos/$REPO")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ 仓库 $REPO 存在${NC}"
else
    echo -e "${RED}✗ 仓库 $REPO 不存在 (HTTP $HTTP_CODE)${NC}"
    echo "响应：$BODY"
    exit 1
fi
echo ""

# Step 3: 检查是否已存在 Webhook
echo -e "${YELLOW}Step 3: 检查是否已存在 Webhook...${NC}"
RESPONSE=$(curl $CURL_ARGS -w "\n%{http_code}" -X GET \
    -H "Authorization: token $GITEA_TOKEN" \
    -H "Content-Type: application/json" \
    "$GITEA_URL/api/v1/repos/$REPO/hooks")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" -eq 200 ]; then
    # 检查是否已存在相同 URL 的 Webhook
    if echo "$BODY" | grep -q "$WEBHOOK_URL"; then
        echo -e "${YELLOW}⚠ Webhook 已存在，跳过创建${NC}"
        echo ""
        echo "现有 Webhooks:"
        echo "$BODY" | grep -o '"url":"[^"]*"' | cut -d'"' -f4 | sed 's/^/  - /'
        echo ""
        echo -e "${YELLOW}如需删除现有 Webhook 并重新创建，请先运行：${NC}"
        echo "  $0 --delete"
        exit 0
    fi
    echo -e "${GREEN}✓ 未发现现有 Webhook${NC}"
else
    echo -e "${YELLOW}⚠ 无法获取 Webhook 列表 (HTTP $HTTP_CODE)${NC}"
fi
echo ""

# Step 4: 创建 Webhook
echo -e "${YELLOW}Step 4: 创建 Webhook...${NC}"

# 构建 JSON payload (修复：使用 Gitea API 正确的字段格式)
# Gitea API 参考：https://docs.gitea.io/api/1.20/#tag/repository/operation/repoCreateHook
PAYLOAD=$(cat <<EOF
{
  "type": "gitea",
  "config": {
    "url": "$WEBHOOK_URL",
    "content_type": "json"
  },
  "events": [
    "push"
  ],
  "active": true
}
EOF
)

RESPONSE=$(curl $CURL_ARGS -w "\n%{http_code}" -X POST \
    -H "Authorization: token $GITEA_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    "$GITEA_URL/api/v1/repos/$REPO/hooks")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" -eq 201 ]; then
    echo -e "${GREEN}✓ Webhook 创建成功${NC}"
    WEBHOOK_ID=$(echo "$BODY" | grep -o '"id":[0-9]*' | cut -d':' -f2)
    echo "  Webhook ID: $WEBHOOK_ID"
    echo "  目标 URL: $WEBHOOK_URL"
    echo "  触发事件：Push"
else
    echo -e "${RED}✗ Webhook 创建失败 (HTTP $HTTP_CODE)${NC}"
    echo "响应：$BODY"
    exit 1
fi
echo ""

# Step 5: 验证 Webhook
echo -e "${YELLOW}Step 5: 验证 Webhook 配置...${NC}"
RESPONSE=$(curl $CURL_ARGS -w "\n%{http_code}" -X GET \
    -H "Authorization: token $GITEA_TOKEN" \
    -H "Content-Type: application/json" \
    "$GITEA_URL/api/v1/repos/$REPO/hooks/$WEBHOOK_ID")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ Webhook 验证成功${NC}"
    ACTIVE=$(echo "$BODY" | grep -o '"active":true')
    if [ -n "$ACTIVE" ]; then
        echo "  状态：激活"
    else
        echo "  状态：未激活"
    fi
else
    echo -e "${YELLOW}⚠ Webhook 验证失败 (HTTP $HTTP_CODE)${NC}"
fi
echo ""

# 完成
echo "========================================"
echo -e "${GREEN}✓ Webhook 配置完成${NC}"
echo "========================================"
echo ""
echo "下一步："
echo "1. 在 ArgoCD 中创建 Application 并配置 Git 仓库"
echo "2. 推送代码到 Gitea 仓库测试 Webhook 触发"
echo "3. 观察 ArgoCD 日志确认同步成功"
echo ""
echo "测试命令："
echo "  kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller -f"
echo ""
