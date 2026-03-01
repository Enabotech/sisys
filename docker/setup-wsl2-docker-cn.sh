#!/bin/bash
# sisys - WSL 2 Docker Engine 一键设置脚本（中国大陆）
# 运行环境：WSL 2 Ubuntu 22.04

set -e

echo "============================================================"
echo "  sisys - WSL 2 Docker Engine 设置（中国大陆）"
echo "============================================================"
echo ""

# 检查是否在 WSL 中
if ! grep -qi microsoft /proc/version; then
    echo "[WARN] 似乎不在 WSL 中运行，但继续执行..."
fi

# 步骤 1: 检查 Docker 是否安装
echo "[STEP 1/5] 检查 Docker 安装..."
if command -v docker &> /dev/null; then
    echo "[OK] Docker 已安装：$(docker --version)"
else
    echo "[ERROR] Docker 未安装，请先运行 setup-wsl2-docker.sh"
    exit 1
fi
echo ""

# 步骤 2: 启用 systemd（如果需要）
echo "[STEP 2/5] 检查 systemd 状态..."
if ps aux | grep -v grep | grep systemd > /dev/null; then
    echo "[OK] systemd 已启用"
else
    echo "[INFO] systemd 未启用，正在配置..."
    
    # 创建 wsl.conf
    if [ ! -f /etc/wsl.conf ]; then
        sudo bash -c 'cat > /etc/wsl.conf << EOF
[boot]
systemd=true

[automount]
enabled = true
root = /mnt/
options = "metadata"
EOF'
        echo "[OK] /etc/wsl.conf 已创建"
        echo "[WARN] 请重启 WSL 后重新运行此脚本："
        echo "       exit"
        echo "       wsl --shutdown"
        echo "       wsl"
        echo "       bash docker/setup-wsl2-docker-cn.sh"
        exit 0
    else
        echo "[INFO] /etc/wsl.conf 已存在"
        if grep -q "systemd=true" /etc/wsl.conf; then
            echo "[OK] systemd 已在配置中启用"
        else
            echo "[WARN] /etc/wsl.conf 存在但未启用 systemd"
        fi
    fi
fi
echo ""

# 步骤 3: 配置 Docker 镜像加速器
echo "[STEP 3/5] 配置 Docker 镜像加速器..."

sudo mkdir -p /etc/docker

# 创建 daemon.json
sudo bash -c 'cat > /etc/docker/daemon.json << EOF
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://docker.m.daocloud.io",
    "https://hub-mirror.c.163.com"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  }
}
EOF'

echo "[OK] Docker daemon.json 已配置"

# 重启 Docker
echo "[INFO] 重启 Docker 服务..."
sudo systemctl restart docker

# 验证配置
echo "[INFO] 验证配置..."
if docker info 2>/dev/null | grep -q "Registry Mirrors"; then
    echo "[OK] 镜像加速器已配置"
    docker info 2>/dev/null | grep -A 3 "Registry Mirrors"
else
    echo "[WARN] 镜像加速器可能未生效，请手动检查"
fi
echo ""

# 步骤 4: 拉取镜像
echo "[STEP 4/5] 拉取 Docker 镜像..."

# 定义镜像列表
IMAGES=(
    "docker.m.daocloud.io/library/redis:7.2-alpine:redis:7.2-alpine"
    "docker.m.daocloud.io/library/postgres:15-alpine:postgres:15-alpine"
    "docker.m.daocloud.io/library/minio:latest:minio:latest"
    "docker.m.daocloud.io/qdrant/qdrant:v1.7.0:qdrant/qdrant:v1.7.0"
    "docker.m.daocloud.io/library/neo4j:5.15:neo4j:5.15"
)

cd "$(dirname "$0")"

for image_map in "${IMAGES[@]}"; do
    IFS=':' read -r mirror_repo mirror_tag official_repo official_tag <<< "$image_map"
    
    mirror_image="${mirror_repo}:${mirror_tag}"
    official_image="${official_repo}:${official_tag}"
    
    echo ""
    echo "[PULL] 拉取：$official_image"
    
    if docker image inspect "$official_image" &> /dev/null; then
        echo "[OK] 镜像已存在：$official_image"
    else
        if docker pull "$mirror_image"; then
            # 重新标记
            docker tag "$mirror_image" "$official_image"
            echo "[OK] 成功拉取并标记：$official_image"
        else
            echo "[FAIL] 拉取失败：$mirror_image"
        fi
    fi
done

echo ""
echo "[OK] 镜像拉取完成"
echo ""

# 步骤 5: 启动服务
echo "[STEP 5/5] 启动 Docker Compose 服务..."

if [ -f "docker-compose.yml" ]; then
    docker compose up -d
    
    # 等待服务启动
    echo "[INFO] 等待服务启动..."
    sleep 10
    
    # 检查状态
    echo ""
    echo "=== 服务状态 ==="
    docker compose ps
else
    echo "[WARN] docker-compose.yml 未找到"
fi

echo ""
echo "============================================================"
echo "  设置完成！"
echo "============================================================"
echo ""
echo "常用命令:"
echo "  docker compose ps          # 查看服务状态"
echo "  docker compose logs -f     # 查看日志"
echo "  docker compose down        # 停止服务"
echo "  docker compose up -d       # 启动服务"
echo ""
echo "镜像源配置:"
echo "  /etc/docker/daemon.json"
echo ""
echo "如果拉取失败，可以手动更换镜像源:"
echo "  - https://docker.m.daocloud.io"
echo "  - https://hub-mirror.c.163.com"
echo "  - https://registry.cn-hangzhou.aliyuncs.com"
echo ""
