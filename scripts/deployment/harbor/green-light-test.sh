#!/bin/bash
# Harbor 绿灯测试报告
# Story 0.6: Harbor 镜像仓库部署
# 用途：记录绿灯测试验证结果

set -e

echo "=========================================="
echo "Harbor 绿灯测试报告"
echo "=========================================="
echo ""
echo "测试时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo "Harbor 版本：v2.14.3"
echo "K3S 版本：v1.34.5+k3s1"
echo ""

# 1. Pod 状态验证
echo "1. Pod 状态验证..."
POD_COUNT=$(echo 'H9yglwH7sdyj' | sudo -S kubectl get pods -n harbor -o jsonpath='{.items[*].status.phase}' 2>/dev/null | tr ' ' '\n' | grep -c Running || echo "0")
EXPECTED_PODS=8

if [ "${POD_COUNT}" -eq "${EXPECTED_PODS}" ]; then
    echo "   ✅ PASS: ${POD_COUNT}/${EXPECTED_PODS} Pod Running"
else
    echo "   ❌ FAIL: ${POD_COUNT}/${EXPECTED_PODS} Pod Running"
fi
echo ""

# 2. 健康检查验证
echo "2. 健康检查验证..."
HEALTH_CHECK=$(echo 'H9yglwH7sdyj' | sudo -S kubectl exec -n harbor harbor-core-6565b9d464-2gd82 -- curl -s http://localhost:8080/api/v2.0/ping 2>/dev/null || echo "")

if [ "${HEALTH_CHECK}" = "Pong" ]; then
    echo "   ✅ PASS: Harbor API 健康检查通过"
else
    echo "   ❌ FAIL: Harbor API 健康检查失败"
fi
echo ""

# 3. 数据库连接验证
echo "3. 数据库连接验证..."
DB_LOGS=$(echo 'H9yglwH7sdyj' | sudo -S kubectl logs -n harbor harbor-database-0 2>/dev/null | grep -c "ready to accept connections" || echo "0")

if [ "${DB_LOGS}" -gt 0 ]; then
    echo "   ✅ PASS: PostgreSQL 数据库连接正常"
else
    echo "   ❌ FAIL: PostgreSQL 数据库连接异常"
fi
echo ""

# 4. Trivy 漏洞扫描器验证
echo "4. Trivy 漏洞扫描器验证..."
TRIVY_LOGS=$(echo 'H9yglwH7sdyj' | sudo -S kubectl logs -n harbor harbor-trivy-0 2>/dev/null | grep -c "Starting API server" || echo "0")

if [ "${TRIVY_LOGS}" -gt 0 ]; then
    echo "   ✅ PASS: Trivy 漏洞扫描器运行正常"
else
    echo "   ❌ FAIL: Trivy 漏洞扫描器运行异常"
fi
echo ""

# 5. Registry 验证
echo "5. Registry 验证..."
REGISTRY_POD=$(echo 'H9yglwH7sdyj' | sudo -S kubectl get pods -n harbor -l component=registry -o jsonpath='{.items[*].status.phase}' 2>/dev/null | grep -c Running || echo "0")

if [ "${REGISTRY_POD}" -gt 0 ]; then
    echo "   ✅ PASS: Harbor Registry 运行正常"
else
    echo "   ❌ FAIL: Harbor Registry 运行异常"
fi
echo ""

# 6. 服务验证
echo "6. 服务验证..."
SERVICE_COUNT=$(echo 'H9yglwH7sdyj' | sudo -S kubectl get svc -n harbor --no-headers 2>/dev/null | wc -l || echo "0")
EXPECTED_SERVICES=8

if [ "${SERVICE_COUNT}" -ge "${EXPECTED_SERVICES}" ]; then
    echo "   ✅ PASS: ${SERVICE_COUNT} 个服务已创建"
else
    echo "   ❌ FAIL: ${SERVICE_COUNT}/${EXPECTED_SERVICES} 个服务"
fi
echo ""

# 7. PVC 验证
echo "7. PVC 验证..."
PVC_COUNT=$(echo 'H9yglwH7sdyj' | sudo -S kubectl get pvc -n harbor --no-headers 2>/dev/null | wc -l || echo "0")
PVC_BOUND=$(echo 'H9yglwH7sdyj' | sudo -S kubectl get pvc -n harbor -o jsonpath='{.items[*].status.phase}' 2>/dev/null | tr ' ' '\n' | grep -c Bound || echo "0")

if [ "${PVC_COUNT}" -eq "${PVC_BOUND}" ] && [ "${PVC_COUNT}" -gt 0 ]; then
    echo "   ✅ PASS: ${PVC_BOUND}/${PVC_COUNT} PVC 已绑定"
else
    echo "   ❌ FAIL: ${PVC_BOUND}/${PVC_COUNT} PVC 已绑定"
fi
echo ""

# 8. Ingress 验证
echo "8. Ingress 验证..."
INGRESS_EXISTS=$(echo 'H9yglwH7sdyj' | sudo -S kubectl get ingress -n harbor harbor-ingress --no-headers 2>/dev/null | wc -l || echo "0")

if [ "${INGRESS_EXISTS}" -gt 0 ]; then
    echo "   ✅ PASS: Harbor Ingress 已创建"
else
    echo "   ❌ FAIL: Harbor Ingress 未创建"
fi
echo ""

# 总结
echo "=========================================="
echo "测试总结"
echo "=========================================="
echo ""

PASSED=0
FAILED=0

# 简单统计
[ "${POD_COUNT}" -eq "${EXPECTED_PODS}" ] && ((PASSED++)) || ((FAILED++))
[ "${HEALTH_CHECK}" = "Pong" ] && ((PASSED++)) || ((FAILED++))
[ "${DB_LOGS}" -gt 0 ] && ((PASSED++)) || ((FAILED++))
[ "${TRIVY_LOGS}" -gt 0 ] && ((PASSED++)) || ((FAILED++))
[ "${REGISTRY_POD}" -gt 0 ] && ((PASSED++)) || ((FAILED++))
[ "${SERVICE_COUNT}" -ge "${EXPECTED_SERVICES}" ] && ((PASSED++)) || ((FAILED++))
[ "${PVC_COUNT}" -eq "${PVC_BOUND}" ] && [ "${PVC_COUNT}" -gt 0 ] && ((PASSED++)) || ((FAILED++))
[ "${INGRESS_EXISTS}" -gt 0 ] && ((PASSED++)) || ((FAILED++))

echo "通过：${PASSED}/8"
echo "失败：${FAILED}/8"
echo ""

if [ "${FAILED}" -eq 0 ]; then
    echo "🎉 绿灯测试全部通过！Harbor 部署成功！"
    exit 0
else
    echo "⚠️  有 ${FAILED} 项测试失败，请检查配置"
    exit 1
fi

exit 0
