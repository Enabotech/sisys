#!/bin/bash
# 清理两层容器运行时
echo "🧹 清理 K3s containerd..."
sudo k3s crictl rmi --prune 2>/dev/null || true
echo "🧹 清理 DinD 内部..."
kubectl exec gitea-runner-dind-0 -n gitea-advacts -c docker-dind -- \
  docker system prune -f --volumes 2>/dev/null || true
echo "🧹 清理 Docker 构建缓存..."
docker builder prune -f --filter "until=72h"
echo "✅ 两层清理完成！"