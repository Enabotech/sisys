#!/bin/bash
# ============================================================
# Gitea 离线 Runner 清理脚本
# ============================================================
# 用途：批量删除 Gitea 中离线的 Runner
# ============================================================

set -e

# 配置
GITEA_URL="https://gitea.sisys.local"
GITEA_TOKEN="YOUR_GITEA_ADMIN_TOKEN"  # 替换为 Gitea Admin Token

echo "╔══════════════════════════════════════════════════════════╗"
echo "║         Gitea 离线 Runner 清理脚本                         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# 忽略 TLS 证书验证（自签名证书）
CURL_OPTS="-k -s"

# 获取所有 Runner
echo "📋 获取 Runner 列表..."
RUNNERS=$(curl $CURL_OPTS -H "Authorization: token $GITEA_TOKEN" \
  "$GITEA_URL/api/v1/admin/runners" | jq -r '.runners[]')

echo ""
echo "当前 Runner 状态："
echo "$RUNNERS" | jq -r '"\(.name): \(.status)"' 2>/dev/null || echo "无法解析 Runner 列表"

echo ""
echo "⚠️  操作确认："
echo "   此操作将删除所有离线的 Runner"
echo "   在线的 Runner 将被保留"
echo ""
read -p "是否继续？(y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 操作已取消"
    exit 0
fi

echo ""
echo "🗑️  开始清理离线 Runner..."

# 遍历 Runner 并删除离线的
echo "$RUNNERS" | jq -r '.[] | "\(.id) \(.name) \(.status)"' 2>/dev/null | while read -r ID NAME STATUS; do
    if [ "$STATUS" == "offline" ] || [ "$STATUS" == "inactive" ]; then
        echo "   删除：$NAME (ID: $ID)"
        curl $CURL_OPTS -X DELETE \
          -H "Authorization: token $GITEA_TOKEN" \
          "$GITEA_URL/api/v1/admin/runners/$ID"
        echo "   ✅ 已删除"
    else
        echo "   ⏭️  跳过：$NAME (状态：$STATUS)"
    fi
done

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  清理完成！                                              ║"
echo "╚══════════════════════════════════════════════════════════╝"
