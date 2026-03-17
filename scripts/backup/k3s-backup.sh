#!/bin/bash
# =============================================================================
# K3S 配置备份脚本
# =============================================================================
# 用途：备份 K3S 关键配置，用于灾难恢复
# 作者：AI Architect
# 日期：2026-03-17
# =============================================================================

set -e

BACKUP_DIR="$HOME/k3s-backup"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

echo "============================================================"
echo "K3S 配置备份"
echo "============================================================"
echo ""

# 创建备份目录
mkdir -p $BACKUP_DIR

echo "📦 备份 K3S 配置文件..."
cp /etc/rancher/k3s/config.yaml $BACKUP_DIR/config.yaml.$TIMESTAMP
echo "  ✓ K3S config.yaml"

echo ""
echo "📦 备份 Kubernetes 资源..."

# 备份命名空间
kubectl get namespaces -o yaml > $BACKUP_DIR/namespaces.$TIMESTAMP.yaml
echo "  ✓ Namespaces"

# 备份所有 Ingress
kubectl get ingress --all-namespaces -o yaml > $BACKUP_DIR/ingress.$TIMESTAMP.yaml
echo "  ✓ Ingresses"

# 备份 Traefik 配置
kubectl get deployment traefik -n traefik -o yaml > $BACKUP_DIR/traefik-deployment.$TIMESTAMP.yaml
kubectl get svc traefik -n traefik -o yaml > $BACKUP_DIR/traefik-service.$TIMESTAMP.yaml
echo "  ✓ Traefik 配置"

# 备份 TLS Secrets（只备份元数据，不备份密钥）
kubectl get secret gitea-tls-secret -n gitea -o yaml > $BACKUP_DIR/gitea-tls-secret.$TIMESTAMP.yaml
kubectl get secret argocd-tls-secret -n argocd -o yaml > $BACKUP_DIR/argocd-tls-secret.$TIMESTAMP.yaml
kubectl get secret harbor-tls-secret -n harbor -o yaml > $BACKUP_DIR/harbor-tls-secret.$TIMESTAMP.yaml
echo "  ✓ TLS Secrets 元数据"

# 备份 Middleware
kubectl get middleware --all-namespaces -o yaml > $BACKUP_DIR/middlewares.$TIMESTAMP.yaml
echo "  ✓ Middlewares"

# 备份 TLSOption
kubectl get tlsoption --all-namespaces -o yaml > $BACKUP_DIR/tlsoptions.$TIMESTAMP.yaml
echo "  ✓ TLSOptions"

# 备份 hosts 文件
cp /etc/hosts $BACKUP_DIR/hosts.$TIMESTAMP.backup
echo "  ✓ hosts 文件"

echo ""
echo "============================================================"
echo "✅ 备份完成！"
echo "============================================================"
echo ""
echo "备份位置：$BACKUP_DIR"
echo ""
echo "备份文件列表："
ls -la $BACKUP_DIR/*.$TIMESTAMP.* 2>/dev/null || ls -la $BACKUP_DIR/

echo ""
echo "============================================================"
echo "恢复方法："
echo "============================================================"
echo ""
echo "1. 恢复 K3S 配置："
echo "   sudo cp $BACKUP_DIR/config.yaml.TIMESTAMP /etc/rancher/k3s/config.yaml"
echo "   sudo systemctl restart k3s"
echo ""
echo "2. 恢复 Kubernetes 资源："
echo "   kubectl apply -f $BACKUP_DIR/ingress.TIMESTAMP.yaml"
echo ""
echo "3. 恢复 hosts 文件："
echo "   sudo cp $BACKUP_DIR/hosts.TIMESTAMP.backup /etc/hosts"
echo ""
