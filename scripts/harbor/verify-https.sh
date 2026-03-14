#!/bin/bash
# Harbor HTTPS 访问验证脚本
# Story 0.6: Harbor 镜像仓库部署
# 用途：验证 Harbor HTTPS 访问和证书配置

set -e

HARBOR_HOST="harbor.sisys.local"
HARBOR_URL="https://${HARBOR_HOST}"

echo "=========================================="
echo "Harbor HTTPS 访问验证"
echo "=========================================="
echo ""

# 1. 检查 DNS 解析
echo "1. 检查 DNS 解析..."
if command -v dig &> /dev/null; then
    dig "${HARBOR_HOST}" +short
elif command -v nslookup &> /dev/null; then
    nslookup "${HARBOR_HOST}"
else
    echo "⚠️ 未找到 dig 或 nslookup，跳过 DNS 检查"
fi
echo ""

# 2. 检查证书（如果已配置）
echo "2. 检查 SSL 证书..."
if command -v openssl &> /dev/null; then
    echo | openssl s_client -connect "${HARBOR_HOST}:443" -servername "${HARBOR_HOST}" 2>/dev/null | \
      openssl x509 -noout -subject -dates 2>/dev/null || echo "⚠️ 无法获取证书信息"
else
    echo "⚠️ 未找到 openssl，跳过证书检查"
fi
echo ""

# 3. 检查 TLS 版本
echo "3. 检查 TLS 版本..."
if command -v curl &> /dev/null; then
    curl -vI "${HARBOR_URL}" 2>&1 | grep -E "(TLS|SSL)" || echo "⚠️ 无法获取 TLS 信息"
else
    echo "⚠️ 未找到 curl"
fi
echo ""

# 4. 检查 HSTS 响应头
echo "4. 检查 HSTS 响应头..."
if command -v curl &> /dev/null; then
    HSTS_HEADER=$(curl -sI "${HARBOR_URL}" 2>/dev/null | grep -i "Strict-Transport-Security" || echo "")
    if [ -n "${HSTS_HEADER}" ]; then
        echo "✅ HSTS 已启用：${HSTS_HEADER}"
    else
        echo "❌ HSTS 未启用"
    fi
fi
echo ""

# 5. 检查 Harbor API
echo "5. 检查 Harbor API..."
if command -v curl &> /dev/null; then
    # 忽略证书错误（开发环境）
    RESPONSE=$(curl -sk "${HARBOR_URL}/api/v2.0/ping" 2>/dev/null || echo "")
    if [ "${RESPONSE}" = "Pong" ]; then
        echo "✅ Harbor API 响应正常"
    else
        echo "❌ Harbor API 无响应"
    fi
fi
echo ""

# 6. SSL Labs 测试（可选）
echo "6. SSL Labs 测试..."
echo "   访问：https://www.ssllabs.com/ssltest/analyze.html?d=${HARBOR_HOST}"
echo "   期望评级：A+"
echo ""

# 7. 证书有效期检查
echo "7. 证书有效期检查..."
if command -v openssl &> /dev/null; then
    EXPIRY_DATE=$(echo | openssl s_client -connect "${HARBOR_HOST}:443" -servername "${HARBOR_HOST}" 2>/dev/null | \
      openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2 || echo "")
    if [ -n "${EXPIRY_DATE}" ]; then
        echo "✅ 证书到期时间：${EXPIRY_DATE}"

        # 检查是否在 30 天内到期
        EXPIRY_EPOCH=$(date -d "${EXPIRY_DATE}" +%s 2>/dev/null || echo "0")
        NOW_EPOCH=$(date +%s)
        DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))

        if [ ${DAYS_LEFT} -lt 30 ]; then
            echo "⚠️  警告：证书将在 ${DAYS_LEFT} 天后到期"
        else
            echo "✅ 证书有效期充足（${DAYS_LEFT} 天）"
        fi
    fi
fi
echo ""

echo "=========================================="
echo "验证完成"
echo "=========================================="
