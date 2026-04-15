#!/bin/bash
# Gitea Runner SSL 证书修复脚本
# 用于信任自签名 SSL 证书

set -e

echo "=========================================="
echo "Gitea Runner SSL 证书修复脚本"
echo "=========================================="

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then
  echo "❌ 请以 root 权限运行此脚本 (sudo)"
  exit 1
fi

# 配置
GITEA_HOST="gitea.sisys.local"
HARBOR_HOST="harbor.sisys.local"
CA_DIR="/usr/local/share/ca-certificates"

echo ""
echo "📋 配置信息:"
echo "  Gitea: $GITEA_HOST"
echo "  Harbor: $HARBOR_HOST"
echo "  CA 目录：$CA_DIR"
echo ""

# 创建 CA 目录
echo "📁 创建 CA 目录..."
mkdir -p "$CA_DIR"

# 获取 Gitea 证书
echo ""
echo "🔐 获取 Gitea SSL 证书..."
if openssl s_client -showcerts -connect "$GITEA_HOST:443" </dev/null 2>/dev/null | \
   openssl x509 -outform PEM > "$CA_DIR/gitea-sisys.crt"; then
  echo "✅ Gitea 证书已保存"
else
  echo "⚠️  Gitea 证书获取失败，尝试直接复制..."
  # 备用方案：如果有本地证书文件
  if [ -f "/root/certs/gitea.crt" ]; then
    cp /root/certs/gitea.crt "$CA_DIR/gitea-sisys.crt"
    echo "✅ 已从本地复制 Gitea 证书"
  else
    echo "❌ 无法获取 Gitea 证书"
  fi
fi

# 获取 Harbor 证书
echo ""
echo "🔐 获取 Harbor SSL 证书..."
if openssl s_client -showcerts -connect "$HARBOR_HOST:443" </dev/null 2>/dev/null | \
   openssl x509 -outform PEM > "$CA_DIR/harbor-sisys.crt"; then
  echo "✅ Harbor 证书已保存"
else
  echo "⚠️  Harbor 证书获取失败"
fi

# 更新 CA 证书库
echo ""
echo "🔄 更新 CA 证书库..."
if command -v update-ca-certificates &> /dev/null; then
  update-ca-certificates
  echo "✅ CA 证书已更新 (Debian/Ubuntu)"
elif command -v update-ca-trust &> /dev/null; then
  update-ca-trust extract
  echo "✅ CA 证书已更新 (RHEL/CentOS)"
else
  echo "⚠️  未找到证书更新工具，请手动操作"
fi

# 配置 Docker 信任 Harbor
echo ""
echo "🐳 配置 Docker 信任 Harbor..."
mkdir -p /etc/docker/certs.d/$HARBOR_HOST
cp "$CA_DIR/harbor-sisys.crt" /etc/docker/certs.d/$HARBOR_HOST/ca.crt 2>/dev/null || \
  ln -sf "$CA_DIR/harbor-sisys.crt" /etc/docker/certs.d/$HARBOR_HOST/ca.crt 2>/dev/null || \
  echo "⚠️  Docker 证书配置失败，请手动复制"

# 重启 Gitea Runner
echo ""
echo "🔄 重启 Gitea Runner..."
if systemctl is-active --quiet gitea-runner; then
  systemctl restart gitea-runner
  echo "✅ Gitea Runner 已重启"
elif systemctl is-active --quiet gitea-actions-runner; then
  systemctl restart gitea-actions-runner
  echo "✅ Gitea Actions Runner 已重启"
else
  echo "⚠️  未找到 Gitea Runner 服务，请手动重启"
fi

# 验证
echo ""
echo "=========================================="
echo "✅ 修复完成！"
echo "=========================================="
echo ""
echo "验证步骤:"
echo "1. 检查证书是否安装:"
echo "   ls -la $CA_DIR/"
echo ""
echo "2. 测试 Gitea 连接:"
echo "   curl -I https://$GITEA_HOST"
echo ""
echo "3. 测试 Harbor 登录:"
echo "   docker login https://$HARBOR_HOST"
echo ""
echo "4. 重新运行工作流"
echo ""
