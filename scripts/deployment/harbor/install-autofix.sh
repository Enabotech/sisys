#!/bin/bash
# Harbor 自动修复服务安装脚本
# 用途：安装并启用 Harbor 自动修复服务
#
# 使用方式:
#   ./scripts/deployment/harbor/install-autofix.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "=============================================================================="
echo "Harbor 自动修复服务安装"
echo "=============================================================================="
echo ""

# 检查 sudo
if [[ $EUID -ne 0 ]]; then
    echo "❌ 此脚本需要使用 sudo 运行"
    echo "   请使用：sudo $0"
    exit 1
fi

# 复制服务文件
echo "📋 复制 systemd 服务文件..."
cp "$SCRIPT_DIR/harbor-autofix.service" /etc/systemd/system/harbor-autofix.service
echo "✅ 服务文件已复制到 /etc/systemd/system/harbor-autofix.service"

# 设置脚本权限
echo "🔧 设置自动修复脚本权限..."
chmod +x "$SCRIPT_DIR/harbor-autofix.sh"
echo "✅ 脚本权限已设置"

# 创建日志目录
echo "📁 创建日志目录..."
touch /var/log/harbor-autofix.log
chmod 644 /var/log/harbor-autofix.log
echo "✅ 日志文件已创建：/var/log/harbor-autofix.log"

# 重新加载 systemd
echo "🔄 重新加载 systemd 配置..."
systemctl daemon-reload
echo "✅ systemd 配置已重载"

# 启用服务
echo "⚙️  启用 Harbor 自动修复服务..."
systemctl enable harbor-autofix.service
echo "✅ Harbor 自动修复服务已启用"

# 启动服务（可选，立即运行一次）
echo ""
echo "🚀 启动 Harbor 自动修复服务..."
systemctl start harbor-autofix.service || {
    echo "⚠️  服务启动失败，可能是 WSL 刚启动 K3S 还未就绪"
    echo "   服务将在下次 WSL 启动时自动运行"
}
echo "✅ Harbor 自动修复服务已启动"

# 显示服务状态
echo ""
echo "📊 服务状态:"
systemctl status harbor-autofix.service --no-pager || true

echo ""
echo "=============================================================================="
echo "Harbor 自动修复服务安装完成！"
echo "=============================================================================="
echo ""
echo "📋 使用说明:"
echo ""
echo "  1. 查看服务状态:"
echo "     sudo systemctl status harbor-autofix"
echo ""
echo "  2. 查看日志:"
echo "     sudo journalctl -u harbor-autofix -f"
echo "     或查看日志文件：/var/log/harbor-autofix.log"
echo ""
echo "  3. 手动运行修复:"
echo "     sudo systemctl start harbor-autofix"
echo ""
echo "  4. 禁用服务:"
echo "     sudo systemctl disable harbor-autofix"
echo ""
echo "  5. 卸载服务:"
echo "     sudo systemctl stop harbor-autofix"
echo "     sudo rm /etc/systemd/system/harbor-autofix.service"
echo "     sudo systemctl daemon-reload"
echo ""
echo "🎯 服务特点:"
echo "  ✅ WSL 启动时自动运行（在 k3s.service 之后）"
echo "  ✅ 自动检查并修复 Harbor 配置"
echo "  ✅ 自动删除冲突的旧 Ingress"
echo "  ✅ 自动验证 API 访问"
echo "  ✅ 详细日志记录"
echo ""
echo "访问地址：https://harbor.sisys.local:nodeport"
echo "管理员账号：admin / Harbor@2026Secure!"
echo "=============================================================================="
