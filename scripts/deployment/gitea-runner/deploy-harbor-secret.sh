#!/bin/bash
# ============================================================
# Harbor Secret 部署脚本
# ============================================================
# Story: 0-8 - Gitea Runner Configuration
# Task: 6 - Harbor Integration Configuration
#
# 用途：部署 Harbor Robot Account Secret 到 Kubernetes 集群
#
# 使用方法:
#   bash scripts/deployment/gitea-runner/deploy-harbor-secret.sh
#
# 前置条件:
#   - kubectl 已配置并可以访问 K8s 集群
#   - Harbor 已部署并可访问 (Story 0.6 ✅)
#   - 已创建 Harbor Robot Account Token
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
CONFIG_FILE="deploy/kubernetes/gitea-runner/harbor-robot-secret.yaml"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Harbor Robot Account Secret 部署脚本                  ║${NC}"
echo -e "${BLUE}║   Story 0-8 - Task 6                                    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# 步骤 1: 检查前置条件
echo -e "${YELLOW}Step 1: 检查前置条件...${NC}"

# 检查 kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✅ kubectl 已安装${NC}"

# 检查集群连接
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ 无法连接到 Kubernetes 集群${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Kubernetes 集群连接成功${NC}"

# 检查配置文件
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}❌ 配置文件不存在：$CONFIG_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}✅ 配置文件存在：$CONFIG_FILE${NC}"

echo ""

# 步骤 2: 创建命名空间（如果不存在）
echo -e "${YELLOW}Step 2: 确保命名空间 '$NAMESPACE' 存在...${NC}"

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - > /dev/null 2>&1
echo -e "${GREEN}✅ 命名空间 '$NAMESPACE' 已准备就绪${NC}"

echo ""

# 步骤 3: 应用 Secret 配置
echo -e "${YELLOW}Step 3: 应用 Harbor Secret 配置...${NC}"

kubectl apply -f "$CONFIG_FILE"

echo -e "${GREEN}✅ Secret 配置已应用${NC}"

echo ""

# 步骤 4: 验证 Secret 已创建
echo -e "${YELLOW}Step 4: 验证 Secret 已创建...${NC}"

sleep 2

if kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Secret '$SECRET_NAME' 创建成功${NC}"
else
    echo -e "${RED}❌ Secret 创建失败${NC}"
    exit 1
fi

echo ""

# 步骤 5: 显示 Secret 信息
echo -e "${YELLOW}Step 5: Secret 信息...${NC}"

kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o yaml | head -20

echo ""

# 步骤 6: 验证 Harbor 连接
echo -e "${YELLOW}Step 6: 测试 Harbor 连接...${NC}"

if curl -k -s https://harbor.sisys.local/api/v2.0/ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Harbor 服务可访问${NC}"
else
    echo -e "${YELLOW}⚠️  Harbor 服务暂时不可达（可能是网络问题）${NC}"
fi

echo ""

# 完成
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Harbor Robot Account Secret 部署完成！                 ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📊 摘要:${NC}"
echo "  - Secret 名称：$SECRET_NAME"
echo "  - 命名空间：$NAMESPACE"
echo "  - 配置文件：$CONFIG_FILE"
echo ""
echo -e "${BLUE}🚀 下一步:${NC}"
echo "  1. 验证 Secret: bash scripts/deployment/gitea-runner/validate-harbor-secret.sh"
echo "  2. 部署 Gitea Runner: bash scripts/deployment/gitea-runner/deploy-runner.sh"
echo "  3. 测试 Pipeline: 推送代码到 Gitea 并验证 CI/CD 执行"
echo ""
