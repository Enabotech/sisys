#!/bin/bash

# ==================== 配置区 ====================
BACKUP_DIR="docker-images-backup"
# ===============================================

mkdir -p "${BACKUP_DIR}"

docker image ls --format '{{.Repository}}:{{.Tag}}' | grep -v '<none>' | while read img; do
    filename=$(echo "$img" | tr '/' '_' | tr ':' '_')
    sudo docker save "$img" -o "${BACKUP_DIR}"/"$filename".tar
    echo "已导出: $img -> $filename.tar"
done
