#!/bin/bash
# Gitea Variables 验证脚本

set -e

echo "=========================================="
echo "Gitea Variables 验证脚本"
echo "=========================================="
echo ""

# 配置
GITEA_URL="https://gitea.sisys.local"
GITEA_TOKEN="1f182aca3d38b66f7e49c034d98fb15bf02434b7"  # Gitea Admin Token

# 获取仓库列表
echo "📋 获取仓库列表..."
REPOS=$(curl -k -s -H "Authorization: token $GITEA_TOKEN" \
  "$GITEA_URL/api/v1/user/repos" | jq -r '.[].full_name')

echo "找到的仓库:"
echo "$REPOS"
echo ""

# 提示用户选择仓库
echo "请选择要检查的仓库（输入完整名称，如：owner/repo）:"
read -r REPO_NAME

# 检查 Variables
echo ""
echo "🔍 检查 Variables 配置..."
echo ""

# 检查 HARBOR_REGISTRY
echo "1. 检查 HARBOR_REGISTRY..."
VAR_VALUE=$(curl -k -s -H "Authorization: token $GITEA_TOKEN" \
  "$GITEA_URL/api/v1/repos/$REPO_NAME/actions/variables/HARBOR_REGISTRY" 2>/dev/null | jq -r '.value' 2>/dev/null || echo "NOT_FOUND")

if [ "$VAR_VALUE" = "NOT_FOUND" ] || [ -z "$VAR_VALUE" ]; then
  echo "   ❌ HARBOR_REGISTRY 未配置"
else
  echo "   ✅ HARBOR_REGISTRY = $VAR_VALUE"
fi

# 检查 HARBOR_PROJECT
echo "2. 检查 HARBOR_PROJECT..."
VAR_VALUE=$(curl -k -s -H "Authorization: token $GITEA_TOKEN" \
  "$GITEA_URL/api/v1/repos/$REPO_NAME/actions/variables/HARBOR_PROJECT" 2>/dev/null | jq -r '.value' 2>/dev/null || echo "NOT_FOUND")

if [ "$VAR_VALUE" = "NOT_FOUND" ] || [ -z "$VAR_VALUE" ]; then
  echo "   ❌ HARBOR_PROJECT 未配置"
else
  echo "   ✅ HARBOR_PROJECT = $VAR_VALUE"
fi

# 检查 Secrets
echo ""
echo "🔐 检查 Secrets 配置..."
echo ""

# 检查 HARBOR_ROBOT_USERNAME
echo "1. 检查 HARBOR_ROBOT_USERNAME..."
SECRET_EXISTS=$(curl -k -s -H "Authorization: token $GITEA_TOKEN" \
  "$GITEA_URL/api/v1/repos/$REPO_NAME/actions/secrets/HARBOR_ROBOT_USERNAME" 2>/dev/null | jq -r '.name' 2>/dev/null || echo "NOT_FOUND")

if [ "$SECRET_EXISTS" = "NOT_FOUND" ]; then
  echo "   ❌ HARBOR_ROBOT_USERNAME 未配置"
else
  echo "   ✅ HARBOR_ROBOT_USERNAME 已配置"
fi

# 检查 HARBOR_ROBOT_PASSWORD
echo "2. 检查 HARBOR_ROBOT_PASSWORD..."
SECRET_EXISTS=$(curl -k -s -H "Authorization: token $GITEA_TOKEN" \
  "$GITEA_URL/api/v1/repos/$REPO_NAME/actions/secrets/HARBOR_ROBOT_PASSWORD" 2>/dev/null | jq -r '.name' 2>/dev/null || echo "NOT_FOUND")

if [ "$SECRET_EXISTS" = "NOT_FOUND" ]; then
  echo "   ❌ HARBOR_ROBOT_PASSWORD 未配置"
else
  echo "   ✅ HARBOR_ROBOT_PASSWORD 已配置"
fi

echo ""
echo "=========================================="
echo "验证完成！"
echo "=========================================="
echo ""
echo "如果以上任何项显示 ❌，请在 Gitea UI 中配置:"
echo "  1. 访问：https://gitea.sisys.local/$REPO_NAME/settings/actions/variables"
echo "  2. 添加缺失的 Variables 和 Secrets"
echo ""
