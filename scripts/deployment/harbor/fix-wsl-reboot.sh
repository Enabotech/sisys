#!/bin/bash
# Harbor WSL 重启后自动修复脚本
# 用途：WSL 重启后自动修复 Harbor 登录问题
#
# 使用方法:
#   ./scripts/deployment/harbor/fix-wsl-reboot.sh
#
# 自动执行:
#   将此脚本添加到 ~/.bashrc 或创建 systemd 服务在 WSL 启动时自动运行

set -e

HARBOR_NAMESPACE="harbor"
TRAEFIK_NAMESPACE="traefik"
HARBOR_HOST="harbor.sisys.local"
HARBOR_NODEPORT="31448"
HARBOR_NODE_IP="172.21.110.12"
MAX_RETRIES=3
RETRY_DELAY=5

echo "=============================================="
echo "  Harbor WSL 重启后自动修复脚本"
echo "=============================================="
echo ""

# 步骤 1: 检查 Harbor Pod 状态
echo "[1/6] 检查 Harbor Pod 状态..."
kubectl get pods -n $HARBOR_NAMESPACE --no-headers | while read line; do
    echo "  $line"
done

# 等待所有 Harbor Pod 就绪
echo ""
echo "等待 Harbor Pod 就绪..."
kubectl wait --for=condition=Ready pods --all -n $HARBOR_NAMESPACE --timeout=120s > /dev/null 2>&1
echo "✅ Harbor Pod 已就绪"

# 步骤 2: 检查 Traefik 状态
echo ""
echo "[2/6] 检查 Traefik 状态..."
TRAEFIK_POD=$(kubectl get pods -n $TRAEFIK_NAMESPACE -l app.kubernetes.io/name=traefik --no-headers -o custom-columns=":metadata.name" 2>/dev/null | head -1)

if [ -z "$TRAEFIK_POD" ]; then
    echo "❌ 未找到 Traefik Pod"
    exit 1
fi

echo "  Traefik Pod: $TRAEFIK_POD"

# 获取 Traefik 启动时间
TRAEFIK_START_TIME=$(kubectl get pod -n $TRAEFIK_NAMESPACE $TRAEFIK_POD -o jsonpath='{.status.startTime}' 2>/dev/null)
CURRENT_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "  Traefik 启动时间：$TRAEFIK_START_TIME"

# 检查 Traefik 是否需要重启（如果启动时间超过 5 分钟，可能需要刷新）
# 这一步是可选的，用于处理 Traefik 配置缓存问题

# 步骤 3: 测试 API 访问（带重试）
echo ""
echo "[3/6] 测试 Harbor API 访问..."

test_api_access() {
    local ping_response=$(curl -k -s https://$HARBOR_NODE_IP:$HARBOR_NODEPORT/api/v2.0/ping -H "Host: $HARBOR_HOST" 2>/dev/null)
    if [ "$ping_response" = "Pong" ]; then
        return 0
    else
        return 1
    fi
}

API_OK=false
for i in $(seq 1 $MAX_RETRIES); do
    if test_api_access; then
        echo "✅ API 访问正常"
        API_OK=true
        break
    else
        echo "⚠️  API 访问异常 (尝试 $i/$MAX_RETRIES)"
        if [ $i -lt $MAX_RETRIES ]; then
            echo "  等待 ${RETRY_DELAY}s 后重试..."
            sleep $RETRY_DELAY
        fi
    fi
done

if [ "$API_OK" = false ]; then
    echo "  正在重启 Traefik..."
    kubectl rollout restart deployment traefik -n $TRAEFIK_NAMESPACE > /dev/null 2>&1

    echo "  等待 Traefik 重启..."
    kubectl wait --for=condition=Ready pods -l app.kubernetes.io/name=traefik -n $TRAEFIK_NAMESPACE --timeout=60s > /dev/null 2>&1
    sleep 10

    if test_api_access; then
        echo "✅ Traefik 重启成功，API 访问正常"
    else
        echo "❌ Traefik 重启后 API 仍然异常"
        exit 1
    fi
fi

# 步骤 4: 测试登录
echo ""
echo "[4/6] 测试 Harbor 登录..."

test_login() {
    local response=$(curl -k -s -w "%{http_code}" https://$HARBOR_NODE_IP:$HARBOR_NODEPORT/api/v2.0/users/1 \
        -H "Host: $HARBOR_HOST" -u "admin:Admin@123456" 2>/dev/null)
    local http_code="${response: -3}"
    if [ "$http_code" = "200" ]; then
        return 0
    else
        return 1
    fi
}

if test_login; then
    echo "✅ admin 登录成功"
else
    echo "⚠️  admin 登录失败，尝试 sisys_admin..."

    local response=$(curl -k -s -w "%{http_code}" https://$HARBOR_NODE_IP:$HARBOR_NODEPORT/api/v2.0/users/3 \
        -H "Host: $HARBOR_HOST" -u "sisys_admin:Admin@123456" 2>/dev/null)
    local http_code="${response: -3}"

    if [ "$http_code" = "200" ]; then
        echo "✅ sisys_admin 登录成功"
    else
        echo "❌ 所有用户登录失败"
        exit 1
    fi
fi

# 步骤 5: 运行测试用例
echo ""
echo "[5/6] 运行 Harbor 测试用例..."
cd /mnt/g/ai/sisys
if poetry run pytest tests/deployment/test_harbor.py::TestHarborAdminAccount::test_harbor_admin_login -v --tb=no -q 2>/dev/null | grep -q "passed"; then
    echo "✅ 测试用例通过"
else
    echo "⚠️  测试用例执行失败（可手动运行）"
fi

# 步骤 6: 输出总结
echo ""
echo "[6/6] 完成!"
echo ""
echo "=============================================="
echo "  ✅ Harbor 修复完成！"
echo "=============================================="
echo ""
echo "登录凭证:"
echo "  URL: https://$HARBOR_NODE_IP:$HARBOR_NODEPORT"
echo "  用户：admin / Admin@123456"
echo "  用户：sisys_admin / Admin@123456"
echo ""
echo "提示：WSL 重启后运行此脚本修复 Harbor 登录"
echo "  $HOME/ai/sisys/scripts/deployment/harbor/fix-wsl-reboot.sh"
echo ""
