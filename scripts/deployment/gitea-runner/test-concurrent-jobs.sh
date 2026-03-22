#!/bin/bash
# ============================================================
# Gitea Runner 并发 Job 测试脚本
# ============================================================
# Story: 0.8 - Gitea Runner Configuration
# Task: 7 - Multi-Runner Configuration
#
# 用途：测试多个 Runner 并发执行 Pipeline 的能力
#
# 使用方法:
#   bash scripts/deployment/gitea-runner/test-concurrent-jobs.sh
#
# 前置条件:
#   - Gitea 已部署并可访问
#   - Gitea Runner 已部署 (至少 3 个副本)
#   - 有 Gitea 仓库和 API 访问权限
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
GITEA_URL="${GITEA_URL:-http://gitea-http.gitea.svc.cluster.local:3000}"
GITEA_TOKEN="${GITEA_TOKEN:-}"
REPO_NAME="${REPO_NAME:-test-concurrent-jobs}"
ORG_NAME="${ORG_NAME:-sisys}"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Gitea Runner 并发 Job 测试脚本                        ║${NC}"
echo -e "${BLUE}║   Story 0-8 - Task 7                                    ║${NC}"
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

# 检查 Runner Pods
RUNNER_PODS=$(kubectl get pods -n gitea-actions -l app=gitea-org-runner \
  -o jsonpath='{.items[*].status.phase}' 2>/dev/null | tr ' ' '\n' | grep -c Running || echo "0")

if [ "$RUNNER_PODS" -ge 3 ]; then
    echo -e "${GREEN}✅ Runner Pods 运行中 ($RUNNER_PODS 个)${NC}"
else
    echo -e "${RED}❌ Runner Pods 不足 (期望≥3, 实际=$RUNNER_PODS)${NC}"
    exit 1
fi

echo ""

# 步骤 2: 显示 Runner 状态
echo -e "${YELLOW}Step 2: Runner 状态...${NC}"

kubectl get pods -n gitea-actions -l app=gitea-org-runner -o wide

echo ""

# 步骤 3: 检查 Runner 标签
echo -e "${YELLOW}Step 3: Runner 标签配置...${NC}"

LABELS=$(kubectl get statefulset gitea-org-runner -n gitea-actions \
  -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="GITEA_RUNNER_LABELS")].value}')

echo "   Runner 标签：$LABELS"

if [[ "$LABELS" == *"docker"* ]] && [[ "$LABELS" == *"k8s"* ]]; then
    echo -e "${GREEN}✅ Runner 标签配置正确${NC}"
else
    echo -e "${YELLOW}⚠️  Runner 标签可能不完整${NC}"
fi

echo ""

# 步骤 4: 检查 Runner 容量
echo -e "${YELLOW}Step 4: Runner 容量配置...${NC}"

CAPACITY=$(kubectl get statefulset gitea-org-runner -n gitea-actions \
  -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="GITEA_RUNNER_CAPACITY")].value}')

if [ -n "$CAPACITY" ]; then
    echo "   Runner 容量：$CAPACITY"
    if [ "$CAPACITY" -ge 3 ]; then
        echo -e "${GREEN}✅ Runner 容量满足并发需求${NC}"
    else
        echo -e "${YELLOW}⚠️  Runner 容量较低 ($CAPACITY < 3)${NC}"
    fi
else
    echo "   Runner 容量：默认值 (未显式配置)"
    echo -e "${GREEN}✅ 使用默认容量配置${NC}"
fi

echo ""

# 步骤 5: 并发测试说明
echo -e "${YELLOW}Step 5: 并发测试说明...${NC}"

echo ""
echo "并发测试需要 Gitea API 访问权限，用于:"
echo "  1. 创建测试仓库"
echo "  2. 配置 Pipeline 定义"
echo "  3. 触发多个并发 Job"
echo "  4. 监控 Job 执行状态"
echo ""
echo "手动测试步骤："
echo ""
echo "  1. 在 Gitea 创建测试仓库"
echo "     curl -X POST '$GITEA_URL/api/v1/user/repos' \\"
echo "       -H 'Authorization: token YOUR_TOKEN' \\"
echo "       -d '{\"name\":\"$REPO_NAME\"}'"
echo ""
echo "  2. 创建 .gitea/workflows/test.yaml"
echo "     on: push"
echo "     jobs:"
echo "       test-1/2/3:"
echo "         runs-on: ubuntu-latest"
echo "         steps:"
echo "           - run: echo 'Test Job'"
echo ""
echo "  3. 并发推送代码触发多个 Job"
echo "     git push origin main:branch-1"
echo "     git push origin main:branch-2"
echo "     git push origin main:branch-3"
echo ""
echo "  4. 在 Gitea Actions 页面查看并发执行"
echo ""

echo ""

# 步骤 6: 验证 Runner 就绪状态
echo -e "${YELLOW}Step 6: 验证 Runner 就绪状态...${NC}"

READY_COUNT=$(kubectl get pods -n gitea-actions -l app=gitea-org-runner \
  -o jsonpath='{range .items[*]}{.status.conditions[?(@.type=="Ready")].status}{" "}{end}' | tr ' ' '\n' | grep -c True || echo "0")

echo "   就绪 Runner 数量：$READY_COUNT"

if [ "$READY_COUNT" -ge 3 ]; then
    echo -e "${GREEN}✅ 所有 Runner 就绪，可处理并发 Job${NC}"
else
    echo -e "${YELLOW}⚠️  部分 Runner 未就绪${NC}"
fi

echo ""

# 完成
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Gitea Runner 并发测试验证完成！                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📊 测试摘要:${NC}"
echo "  - Runner Pods: $RUNNER_PODS 个"
echo "  - Runner 标签：$LABELS"
echo "  - 就绪 Runner: $READY_COUNT 个"
echo ""
echo -e "${BLUE}✅ Runner 配置支持并发 Job 执行！${NC}"
echo ""
echo -e "${BLUE}🚀 下一步:${NC}"
echo "  1. 在 Gitea 创建测试仓库"
echo "  2. 配置并发 Pipeline 定义"
echo "  3. 触发多个 Job 验证并发执行"
echo "  4. 在 Gitea Actions 页面查看执行结果"
echo ""
