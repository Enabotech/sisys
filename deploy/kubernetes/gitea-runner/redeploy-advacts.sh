#!/bin/bash
# ============================================================
# Gitea Advanced Act Runner 重新部署 - 快速命令清单
# ============================================================
# 执行：bash deploy/kubernetes/gitea-runner/redeploy-advacts.sh
# ============================================================

set -e

echo "═══════════════════════════════════════════════════════════"
echo "🚀 Gitea Advanced Act Runner 重新部署"
echo "═══════════════════════════════════════════════════════════"
echo ""

# 步骤 1: 删除现有 StatefulSet
echo "📦 步骤 1: 删除现有 StatefulSet..."
kubectl delete statefulset gitea-runner-dind -n gitea-advacts --wait=true || echo "⚠️ StatefulSet 不存在"
echo "✅ StatefulSet 已删除"
echo ""

# 步骤 2: 删除旧 Pod
echo "📦 步骤 2: 删除旧 Pod..."
kubectl delete pod -n gitea-advacts --all --wait=true --grace-period=30 || echo "⚠️ 无 Pod 可删除"
echo "✅ Pod 已删除"
echo ""

# 步骤 3: 确认 PVC 状态
echo "📦 步骤 3: 检查 PVC 状态..."
kubectl get pvc -n gitea-advacts
echo ""
read -p "是否删除 PVC 重新注册？(y/N): " choice
if [[ "$choice" =~ ^[Yy]$ ]]; then
    kubectl delete pvc -n gitea-advacts --all --wait=true
    echo "✅ PVC 已删除，Runner 将重新注册"
else
    echo "⏭️ 保留 PVC，Runner 将使用已有注册信息"
fi
echo ""

# 步骤 4: 应用配置
echo "📦 步骤 4: 应用 gitea-advacts-complete.yaml..."
cd /mnt/g/ai/sisys/deploy/kubernetes/gitea-runner/
kubectl apply -f gitea-advacts-complete.yaml
echo "✅ 配置已应用"
echo ""

# 步骤 5: 等待 Pod 就绪
echo "📦 步骤 5: 等待 Pod 就绪 (最多 5 分钟)..."
kubectl wait --for=condition=Ready pod -l app=gitea-runner-dind -n gitea-advacts --timeout=300s
echo ""

# 显示 Pod 状态
echo "═══════════════════════════════════════════════════════════"
echo "📊 Pod 状态:"
kubectl get pods -n gitea-advacts -o wide
echo ""

# 步骤 6: 验证 Docker 功能
echo "═══════════════════════════════════════════════════════════"
echo "🔍 验证 Docker 功能..."
echo ""
echo "Docker 信息:"
kubectl exec gitea-runner-dind-0 -n gitea-advacts -c runner -- docker -H tcp://127.0.0.1:2375 info 2>&1 | head -15
echo ""
echo "Buildx 版本:"
kubectl exec gitea-runner-dind-0 -n gitea-advacts -c runner -- docker buildx version
echo ""

# 步骤 7: 验证 Runner 注册
echo "═══════════════════════════════════════════════════════════"
echo "🔍 验证 Runner 注册..."
echo ""
echo "Runner 日志:"
kubectl logs gitea-runner-dind-0 -n gitea-advacts -c runner --tail=15
echo ""

# 完成
echo "═══════════════════════════════════════════════════════════"
echo "✅ 重新部署完成！"
echo ""
echo "下一步:"
echo "  1. 访问 Gitea UI: https://gitea.sisys.local/-/runners"
echo "  2. 验证 Runner 在线状态"
echo "  3. 触发 CI Workflow 测试"
echo "═══════════════════════════════════════════════════════════"
