#!/bin/bash
# Trivy 漏洞扫描验证脚本
# Story 0.6: Harbor 镜像仓库部署
# 用途：验证 Trivy 漏洞扫描功能

set -e

HARBOR_HOST="harbor.sisys.local"
# pragma: allowlist secret
HARBOR_USER="admin"
# pragma: allowlist secret
HARBOR_PASSWORD="Harbor@2026Secure!"
TEST_IMAGE="nginx:latest"
TEST_PROJECT="sisys"

echo "=========================================="
echo "Trivy 漏洞扫描验证"
echo "=========================================="
echo ""

# 1. 检查 Trivy Pod 状态
echo "1. 检查 Trivy Pod 状态..."
TRIVY_POD=$(kubectl get pods -n harbor -l app=trivy -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
if [ -n "${TRIVY_POD}" ]; then
    TRIVY_STATUS=$(kubectl get pod "${TRIVY_POD}" -n harbor -o jsonpath='{.status.phase}')
    echo "✅ Trivy Pod: ${TRIVY_POD} (${TRIVY_STATUS})"
else
    echo "❌ Trivy Pod 未找到"
    echo "   请确认 Harbor 已部署 Trivy 组件"
    exit 1
fi
echo ""

# 2. 检查 Trivy 日志
echo "2. 检查 Trivy 日志..."
TRIVY_LOGS=$(kubectl logs -n harbor "${TRIVY_POD}" --tail=20 2>/dev/null || echo "")
if echo "${TRIVY_LOGS}" | grep -q "Starting API server"; then
    echo "✅ Trivy API 服务器已启动"
else
    echo "⚠️  Trivy API 服务器状态未知"
fi

if echo "${TRIVY_LOGS}" | grep -q "vulnerability database"; then
    echo "✅ 漏洞数据库已加载"
else
    echo "⚠️  漏洞数据库状态未知"
fi
echo ""

# 3. 检查漏洞数据库版本
echo "3. 检查漏洞数据库版本..."
kubectl exec -n harbor "${TRIVY_POD}" -- trivy --version 2>/dev/null || echo "⚠️  无法获取 Trivy 版本"
echo ""

# 4. 推送测试镜像
echo "4. 推送测试镜像..."
echo "   镜像：${HARBOR_HOST}/${TEST_PROJECT}/test-scan:latest"
echo ""
echo "   请执行以下命令推送测试镜像："
echo "   docker login ${HARBOR_HOST} -u ${HARBOR_USER} -p ${HARBOR_PASSWORD}"
echo "   docker tag ${TEST_IMAGE} ${HARBOR_HOST}/${TEST_PROJECT}/test-scan:latest"
echo "   docker push ${HARBOR_HOST}/${TEST_PROJECT}/test-scan:latest"
echo ""
read -p "推送完成后按回车继续..." -n 1 -r
echo ""

# 5. 触发扫描
echo "5. 触发扫描..."
echo "   在 Harbor Web 界面操作："
echo "   1. 访问 https://${HARBOR_HOST}"
echo "   2. 进入项目：${TEST_PROJECT}"
echo "   3. 点击镜像：test-scan"
echo "   4. 点击'扫描'按钮"
echo ""

# 6. 验证扫描结果
echo "6. 验证扫描结果..."
echo "   在 Harbor Web 界面查看："
echo "   - 漏洞数量"
echo "   - 严重程度分布"
echo "   - 修复建议"
echo ""

# 7. 检查扫描策略
echo "7. 检查扫描策略配置..."
echo "   在 Harbor Web 界面操作："
echo "   1. 进入项目：${TEST_PROJECT}"
echo "   2. 点击'配置'标签"
echo "   3. 检查'自动扫描'是否启用"
echo ""

echo "=========================================="
echo "验证完成"
echo "=========================================="
echo ""
echo "下一步："
echo "1. 配置自动扫描策略（推送时扫描）"
echo "2. 配置定时扫描（每天凌晨 3 点）"
echo "3. 配置漏洞告警（HIGH/CRITICAL）"
echo "4. 配置漏洞数据库自动更新（每天凌晨 4 点）"
