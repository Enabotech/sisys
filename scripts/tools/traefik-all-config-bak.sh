#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR/traefik-all-config-backup"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$BACKUP_DIR"

# Helm 备份
helm get values traefik -n traefik -o yaml > "$BACKUP_DIR/traefik-values-$TIMESTAMP.yaml"
helm get manifest traefik -n traefik > "$BACKUP_DIR/traefik-manifest-$TIMESTAMP.yaml"
helm get all traefik -n traefik > "$BACKUP_DIR/traefik-release-$TIMESTAMP.yaml"

# Kubernetes 资源备份
kubectl get all -n traefik -o yaml > "$BACKUP_DIR/traefik-k8s-all-$TIMESTAMP.yaml"

# Traefik CRD 资源（全局）
kubectl get ingressroute,ingressroutetcp,middleware,tlsoption,tlsstore,serverstransport -A -o yaml > "$BACKUP_DIR/traefik-crd-global-$TIMESTAMP.yaml"

echo "备份完成：$BACKUP_DIR"
