#!/bin/bash
# 清理容器运行时
echo "🧹 清理 K3s 容器无用镜像..."
sudo k3s crictl rmi --prune 2>/dev/null || true
echo "🧹 清理 DinD 内部..."
kubectl exec gitea-runner-dind-0 -n gitea-advacts -c docker-dind -- \
  docker system prune -af 2>/dev/null || true
echo "🧹 清理 Docker 超72h构建缓存..."
docker builder prune -f --filter "until=72h"
echo "🧹 清理 Docker 容器无用数据..."
docker system prune -af

# 清理系统运行时
echo "🧹 清理所有缓存包..."
sudo apt clean
echo "🧹 清理无法下载的过时包..."
sudo apt autoclean
echo "🧹 清理超8h的系统日志..."
sudo journalctl --vacuum-time=8h
sudo find /var/log -type f -name "*.log" -mtime +1 -delete   # 删除 7 天前的 .log 文件
echo "🧹 清理temp文件..."
sudo rm -rf /tmp/*
sudo rm -rf /var/tmp/*
echo "🧹 清理回收站..."
rm -rf ~/.local/share/Trash/*          # 回收站（如果 WSL 启用了回收站）
echo "🧹 清理历史命令记录..."
rm -f ~/.bash_history                  # 清除历史命令（可选）
echo "🧹 清理当前会话..."
history -c                             # 清空当前会话历史
# rm -rf ~/.cache/*                     # 用户级缓存

echo "✅ 清理完成！"
