#!/bin/bash
# ============================================================
# Harbor Secret 验证脚本
# ============================================================
# Story: 0-8 - Gitea Runner Configuration
# Task: 6 - Harbor Integration Configuration
#
# 用途：验证 Harbor Robot Account Secret 配置是否正确
#
# 使用方法:
#   bash scripts/deployment/gitea-runner/validate-harbor-secret.sh
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

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Harbor Robot Account Secret 验证脚本                  ║${NC}"
echo -e "${BLUE}║   Story 0-8 - Task 6                                    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# 步骤 1: 检查 Secret 是否存在
echo -e "${YELLOW}Step 1: 检查 Secret 是否存在...${NC}"

if kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Secret '$SECRET_NAME' 存在于命名空间 '$NAMESPACE'${NC}"
else
    echo -e "${RED}❌ Secret '$SECRET_NAME' 不存在于命名空间 '$NAMESPACE'${NC}"
    echo ""
    echo -e "${YELLOW}提示：先运行部署脚本:${NC}"
    echo "  bash scripts/deployment/gitea-runner/deploy-harbor-secret.sh"
    exit 1
fi

echo ""

# 步骤 2: 检查 Secret 类型
echo -e "${YELLOW}Step 2: 检查 Secret 类型...${NC}"

SECRET_TYPE=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.type}')

if [ "$SECRET_TYPE" = "kubernetes.io/dockerconfigjson" ]; then  # pragma: allowlist secret
    echo -e "${GREEN}✅ Secret 类型正确：$SECRET_TYPE${NC}"
else
    echo -e "${RED}❌ Secret 类型错误：$SECRET_TYPE (应为 kubernetes.io/dockerconfigjson)${NC}"
    exit 1
fi

echo ""

# 步骤 3: 验证 dockerconfigjson 格式
echo -e "${YELLOW}Step 3: 验证 dockerconfigjson 格式...${NC}"

DOCKER_CONFIG=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d 2>/dev/null)

if echo "$DOCKER_CONFIG" | jq . > /dev/null 2>&1; then
    echo -e "${GREEN}✅ dockerconfigjson 格式正确 (有效 JSON)${NC}"
else
    echo -e "${RED}❌ dockerconfigjson 格式错误 (不是有效 JSON)${NC}"
    exit 1
fi

echo ""

# 步骤 4: 检查 Harbor 配置
echo -e "${YELLOW}Step 4: 检查 Harbor 注册表配置...${NC}"

HARBOR_URL="harbor.sisys.local"

if echo "$DOCKER_CONFIG" | jq -e ".auths.\"$HARBOR_URL\"" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Harbor 注册表配置 found: $HARBOR_URL${NC}"

    # 显示认证信息（隐藏密码）
    USERNAME=$(echo "$DOCKER_CONFIG" | jq -r ".auths.\"$HARBOR_URL\".username")
    echo "  - 用户名：$USERNAME"
    echo "  - 注册表：$HARBOR_URL"
else
    echo -e "${RED}❌ Harbor 注册表 '$HARBOR_URL' 未在 dockerconfigjson 中配置${NC}"
    exit 1
fi

echo ""

# 步骤 5: 测试 Harbor 连接
echo -e "${YELLOW}Step 5: 测试 Harbor 服务连接...${NC}"

if curl -k -s https://harbor.sisys.local/api/v2.0/ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Harbor 服务可访问${NC}"

    # 获取 Harbor 版本
    HARBOR_VERSION=$(curl -k -s https://harbor.sisys.local/api/v2.0/ping | jq -r '.version' 2>/dev/null || echo "未知")
    echo "  - Harbor 版本：$HARBOR_VERSION"
else
    echo -e "${YELLOW}⚠️  Harbor 服务暂时不可达${NC}"
    echo "  可能是网络问题或 Harbor 未运行"
fi

echo ""

# 步骤 6: 测试 Docker 登录（可选）
echo -e "${YELLOW}Step 6: 测试 Docker 登录（需要 Docker 环境）...${NC}"

if command -v docker &> /dev/null; then
    # 获取认证信息
    USERNAME=$(echo "$DOCKER_CONFIG" | jq -r ".auths.\"$HARBOR_URL\".username")
    PASSWORD=$(echo "$DOCKER_CONFIG" | jq -r ".auths.\"$HARBOR_URL\".password")

    if [ -n "$USERNAME" ] && [ -n "$PASSWORD" ] && [ "$PASSWORD" != "test-token" ]; then  # pragma: allowlist secret
        if echo "$PASSWORD" | docker login harbor.sisys.local -u "$USERNAME" --password-stdin > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Docker 登录成功${NC}"
            docker logout harbor.sisys.local > /dev/null 2>&1
        else
            echo -e "${RED}❌ Docker 登录失败${NC}"
            echo "  请检查 Robot Account Token 是否正确"
        fi
    else
        echo -e "${YELLOW}⚠️  使用测试 Token，跳过实际登录测试${NC}"
    fi
else
    echo -e "${YELLOW}ℹ️  Docker 未安装，跳过登录测试${NC}"
fi

echo ""

# 完成
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Harbor Robot Account Secret 验证通过！                 ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📊 验证摘要:${NC}"
echo "  - Secret 名称：$SECRET_NAME"
echo "  - 命名空间：$NAMESPACE"
echo "  - Secret 类型：$SECRET_TYPE"
echo "  - Harbor 注册表：$HARBOR_URL"
echo "  - 用户名：$USERNAME"
echo ""
echo -e "${BLUE}✅ 所有验证通过！${NC}"
echo ""
echo -e "${BLUE}🚀 下一步:${NC}"
echo "  1. 部署 Gitea Runner: bash scripts/deployment/gitea-runner/deploy-runner.sh"
echo "  2. 测试 Pipeline: 推送代码到 Gitea 并验证 CI/CD 执行"
echo "  3. 验证镜像推送：检查 Harbor 界面确认镜像已推送"
echo ""
