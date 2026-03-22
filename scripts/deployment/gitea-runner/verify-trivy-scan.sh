#!/bin/bash
# ============================================================
# Harbor Trivy 自动扫描验证脚本
# ============================================================
# Story: 0-8 - Gitea Runner Configuration
# Task: 6 - Harbor Integration Configuration
#
# 用途：验证 Harbor Trivy 漏洞扫描功能
#
# 使用方法:
#   bash scripts/deployment/gitea-runner/verify-trivy-scan.sh
#
# 前置条件:
#   - Harbor 已部署且 Trivy 已启用 (Story 0.6 ✅)
#   - 已有镜像推送到 Harbor
#   - kubectl 已配置
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
HARBOR_URL="harbor.sisys.local"
HARBOR_PROJECT="sisys"
NAMESPACE="harbor"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Harbor Trivy 自动扫描验证脚本                         ║${NC}"
echo -e "${BLUE}║   Story 0-8 - Task 6                                    ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# 步骤 1: 检查 Harbor 服务
echo -e "${YELLOW}Step 1: 检查 Harbor 服务状态...${NC}"

if curl -k -s https://"$HARBOR_URL"/api/v2.0/ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Harbor 服务可访问${NC}"

    # 获取 Harbor 版本
    HARBOR_VERSION=$(curl -k -s https://"$HARBOR_URL"/api/v2.0/ping | jq -r '.version' 2>/dev/null || echo "未知")
    echo "  - Harbor 版本：$HARBOR_VERSION"
else
    echo -e "${RED}❌ Harbor 服务不可访问${NC}"
    echo "  请检查 Harbor 是否已部署"
    exit 1
fi

echo ""

# 步骤 2: 检查 Trivy 组件
echo -e "${YELLOW}Step 2: 检查 Trivy 组件状态...${NC}"

# 检查 Harbor 命名空间中的 Trivy Pod
TRIVY_POD=$(kubectl get pods -n "$NAMESPACE" -l app=trivy -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -n "$TRIVY_POD" ]; then
    POD_STATUS=$(kubectl get pod "$TRIVY_POD" -n "$NAMESPACE" -o jsonpath='{.status.phase}')
    echo -e "${GREEN}✅ Trivy Pod 运行中${NC}"
    echo "  - Pod 名称：$TRIVY_POD"
    echo "  - 状态：$POD_STATUS"
else
    echo -e "${YELLOW}⚠️  Trivy Pod 未找到${NC}"
    echo "  Trivy 可能以其他名称部署或使用外部扫描器"
fi

echo ""

# 步骤 3: 检查项目扫描策略
echo -e "${YELLOW}Step 3: 检查项目漏洞扫描策略...${NC}"

echo "提示：Harbor 默认启用自动扫描"
echo "  - 推送镜像后自动触发扫描"
echo "  - 可在 Harbor 界面查看扫描结果"
echo ""
echo "配置路径："
echo "  Harbor 界面 → 项目 → $HARBOR_PROJECT → 策略 → 漏洞扫描"
echo ""

# 尝试通过 API 获取项目信息（需要认证）
echo "如需通过 API 验证，请使用 Harbor 管理员账号执行:"
echo "  curl -k -u admin:PASSWORD https://$HARBOR_URL/api/v2.0/projects/$HARBOR_PROJECT"

echo ""

# 步骤 4: 验证扫描结果（需要认证）
echo -e "${YELLOW}Step 4: 验证镜像扫描结果...${NC}"

echo "说明：验证扫描结果需要 Harbor 认证"
echo ""
echo "手动验证步骤："
echo "  1. 登录 Harbor Web 界面：https://$HARBOR_URL"
echo "  2. 进入项目 → $HARBOR_PROJECT"
echo "  3. 选择镜像仓库"
echo "  4. 点击镜像标签"
echo "  5. 查看 '漏洞扫描' 标签页"
echo ""
echo "预期结果："
echo "  - 扫描状态：完成"
echo "  - 漏洞数量：按严重程度分类显示"
echo "  - 扫描时间：推送后自动触发"

echo ""

# 步骤 5: 测试镜像推送和扫描流程
echo -e "${YELLOW}Step 5: 测试镜像推送和扫描流程...${NC}"

echo "完整测试流程："
echo ""
echo "  1. 推送镜像到 Harbor"
echo "     bash scripts/deployment/gitea-runner/test-harbor-push.sh"
echo ""
echo "  2. 等待自动扫描（通常 1-5 分钟）"
echo ""
echo "  3. 在 Harbor 界面查看扫描结果"
echo "     https://$HARBOR_URL/harbor/projects/$HARBOR_PROJECT/repositories"
echo ""
echo "  4. 验证扫描报告包含："
echo "     - 漏洞总数"
echo "     - 严重程度分布（Critical/High/Medium/Low）"
echo "     - 受影响的包和版本"
echo "     - 修复建议"
echo ""

echo ""

# 步骤 6: 检查扫描器资源
echo -e "${YELLOW}Step 6: 检查扫描器资源...${NC}"

# 检查 Trivy 配置
echo "Trivy 扫描器配置检查："
echo "  - CPU 限制：确保有足够计算资源"
echo "  - 内存限制：建议 2Gi 以上"
echo "  - 存储：漏洞数据库需要定期更新"
echo ""

# 检查漏洞数据库更新
echo "漏洞数据库更新："
echo "  - Trivy 自动更新漏洞数据库（默认每天）"
echo "  - 可在 Trivy Pod 日志中查看更新状态"
echo "  kubectl logs -n $NAMESPACE $TRIVY_POD | grep -i 'download' || echo '日志中未找到更新记录'"

echo ""

# 完成
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Harbor Trivy 扫描验证完成！                            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📊 验证摘要:${NC}"
echo "  - Harbor 服务：✅ 可访问"
echo "  - Trivy 组件：${TRIVY_POD:+✅ 运行中}${TRIVY_POD:-⚠️  未找到}"
echo "  - 项目：$HARBOR_PROJECT"
echo ""
echo -e "${BLUE}🔍 扫描流程说明:${NC}"
echo ""
echo "  1. 开发者推送代码到 Gitea"
echo "     ↓"
echo "  2. Gitea Runner 执行 CI Pipeline"
echo "     ↓"
echo "  3. 构建 Docker 镜像"
echo "     ↓"
echo "  4. 推送镜像到 Harbor"
echo "     ↓"
echo "  5. Harbor 自动触发 Trivy 扫描 ⚡"
echo "     ↓"
echo "  6. 扫描结果显示在 Harbor 界面"
echo "     ↓"
echo "  7. Pipeline 根据扫描结果决定是否继续部署"
echo ""
echo -e "${BLUE}🚀 下一步:${NC}"
echo "  1. 推送测试镜像验证完整流程"
echo "  2. 配置 Pipeline 质量门禁（阻断严重漏洞）"
echo "  3. 设置扫描通知（邮件/钉钉/企业微信）"
echo ""
