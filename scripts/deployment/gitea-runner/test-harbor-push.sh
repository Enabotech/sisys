#!/bin/bash
# ============================================================
# Harbor Docker Push 测试脚本
# ============================================================
# Story: 0-8 - Gitea Runner Configuration
# Task: 6 - Harbor Integration Configuration
#
# 用途：测试 Docker 推送镜像到 Harbor
#
# 使用方法:
#   bash scripts/deployment/gitea-runner/test-harbor-push.sh
#
# 前置条件:
#   - Docker 已安装并运行
#   - Harbor Secret 已部署
#   - Harbor 服务可访问
#
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
NAMESPACE="gitea-actions"
SECRET_NAME="harbor-robot-account"  # pragma: allowlist secret
HARBOR_URL="harbor.sisys.local"
HARBOR_PROJECT="sisys"
TEST_IMAGE_TAG="test-push-$(date +%Y%m%d-%H%M%S)"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Harbor Docker Push 测试脚本                           ║${NC}"
echo -e "${BLUE}║   Story 0-8 - Task 6                                    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# 步骤 1: 检查前置条件
echo -e "${YELLOW}Step 1: 检查前置条件...${NC}"

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker 已安装${NC}"

# 检查 kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✅ kubectl 已安装${NC}"

# 检查 Secret
if ! kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" > /dev/null 2>&1; then
    echo -e "${RED}❌ Secret '$SECRET_NAME' 不存在于命名空间 '$NAMESPACE'${NC}"
    echo ""
    echo -e "${YELLOW}提示：先运行部署脚本:${NC}"
    echo "  bash scripts/deployment/gitea-runner/deploy-harbor-secret.sh"
    exit 1
fi
echo -e "${GREEN}✅ Secret 存在${NC}"

echo ""

# 步骤 2: 获取 Harbor 认证信息
echo -e "${YELLOW}Step 2: 获取 Harbor 认证信息...${NC}"

DOCKER_CONFIG=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d 2>/dev/null)

USERNAME=$(echo "$DOCKER_CONFIG" | jq -r ".auths.\"$HARBOR_URL\".username")
PASSWORD=$(echo "$DOCKER_CONFIG" | jq -r ".auths.\"$HARBOR_URL\".password")

if [ -z "$USERNAME" ] || [ -z "$PASSWORD" ]; then
    echo -e "${RED}❌ 无法从 Secret 获取认证信息${NC}"
    exit 1
fi

# 检查是否是测试 Token
if [ "$PASSWORD" = "test-token" ]; then  # pragma: allowlist secret
    echo -e "${YELLOW}⚠️  使用测试 Token，无法进行实际推送测试${NC}"
    echo ""
    echo -e "${YELLOW}请更新 Secret 中的 Robot Account Token:${NC}"
    echo "  1. 在 Harbor 界面创建 Robot Account"
    echo "  2. 复制 Token"
    echo "  3. 更新 deploy/kubernetes/gitea-runner/harbor-robot-secret.yaml"
    echo "  4. 重新部署：kubectl apply -f deploy/kubernetes/gitea-runner/harbor-robot-secret.yaml"
    echo ""
    echo -e "${YELLOW}跳过实际推送测试...${NC}"
    exit 0
fi

echo -e "${GREEN}✅ 认证信息获取成功${NC}"
echo "  - 用户名：$USERNAME"
echo "  - 注册表：$HARBOR_URL"

echo ""

# 步骤 3: Docker 登录 Harbor
echo -e "${YELLOW}Step 3: Docker 登录 Harbor...${NC}"

if echo "$PASSWORD" | docker login "$HARBOR_URL" -u "$USERNAME" --password-stdin > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Docker 登录成功${NC}"
else
    echo -e "${RED}❌ Docker 登录失败${NC}"
    echo "  请检查 Robot Account Token 是否正确"
    exit 1
fi

echo ""

# 步骤 4: 创建测试镜像
echo -e "${YELLOW}Step 4: 创建测试镜像...${NC}"

# 创建临时目录
TEMP_DIR=$(mktemp -d)
cat > "$TEMP_DIR/Dockerfile" << 'EOF'
FROM alpine:latest
LABEL test="harbor-push-test"
RUN echo "Harbor Push Test Image" > /test.txt
CMD ["cat", "/test.txt"]
EOF

# 构建镜像
IMAGE_NAME="$HARBOR_URL/$HARBOR_PROJECT/test-push:$TEST_IMAGE_TAG"
echo "构建镜像：$IMAGE_NAME"

if docker build -t "$IMAGE_NAME" "$TEMP_DIR" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 镜像构建成功${NC}"
else
    echo -e "${RED}❌ 镜像构建失败${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# 清理临时文件
rm -rf "$TEMP_DIR"

echo ""

# 步骤 5: 推送镜像到 Harbor
echo -e "${YELLOW}Step 5: 推送镜像到 Harbor...${NC}"

START_TIME=$(date +%s)

if docker push "$IMAGE_NAME" > /dev/null 2>&1; then
    END_TIME=$(date +%s)
    PUSH_TIME=$((END_TIME - START_TIME))
    echo -e "${GREEN}✅ 镜像推送成功${NC}"
    echo "  - 推送耗时：${PUSH_TIME}秒"
else
    echo -e "${RED}❌ 镜像推送失败${NC}"
    docker logout "$HARBOR_URL"
    exit 1
fi

echo ""

# 步骤 6: 验证镜像已推送
echo -e "${YELLOW}Step 6: 验证镜像已推送...${NC}"

# 尝试拉取镜像
if docker pull "$IMAGE_NAME" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 镜像拉取成功${NC}"
else
    echo -e "${RED}❌ 镜像拉取失败${NC}"
    docker logout "$HARBOR_URL"
    exit 1
fi

# 清理：删除本地镜像
docker rmi "$IMAGE_NAME" > /dev/null 2>&1

echo ""

# 步骤 7: 清理：删除远程镜像（可选）
echo -e "${YELLOW}Step 7: 清理测试镜像...${NC}"

echo "提示：测试镜像保留在 Harbor 中，可手动删除或设置保留策略"
echo "  - 登录 Harbor Web 界面"
echo "  - 进入项目 → sisys → 镜像仓库"
echo "  - 找到 test-push 并删除"

# Docker 登出
docker logout "$HARBOR_URL" > /dev/null 2>&1

echo ""

# 完成
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Harbor Docker Push 测试通过！                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📊 测试摘要:${NC}"
echo "  - 镜像名称：$IMAGE_NAME"
echo "  - 推送耗时：${PUSH_TIME}秒"
echo "  - 测试结果：✅ 通过"
echo ""
echo -e "${BLUE}✅ Harbor 集成验证成功！${NC}"
echo ""
echo -e "${BLUE}🚀 下一步:${NC}"
echo "  1. 配置 CI/CD Pipeline: 创建 .gitea/workflows/ci.yaml"
echo "  2. 测试 Pipeline: 推送代码到 Gitea 并验证自动构建"
echo "  3. 验证 Trivy 扫描：在 Harbor 界面查看漏洞扫描结果"
echo ""
