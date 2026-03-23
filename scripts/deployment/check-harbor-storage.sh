#!/bin/bash

# =============================================================================
# Harbor 镜像存储位置检查脚本
# =============================================================================
# 用途：检查 Harbor 仓库的镜像存储位置和占用情况
# 关联 Story: 0.9 (CI/CD Pipeline 模板)
# =============================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}=========================================${NC}"
}

print_step() {
    echo -e "${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${GREEN}ℹ️  $1${NC}"
}

print_header "Harbor 镜像存储位置检查"

# -----------------------------------------------------------------------------
# 方法 1: 检查 K8s PersistentVolume (推荐)
# -----------------------------------------------------------------------------
print_step "方法 1: 检查 Kubernetes PersistentVolume..."

if command -v kubectl &> /dev/null; then
    # 检查 Harbor 命名空间
    HARBOR_NS=$(kubectl get ns | grep -E "harbor|gitea" | head -1 | awk '{print $1}')

    if [ -n "$HARBOR_NS" ]; then
        print_info "Harbor 命名空间：$HARBOR_NS"

        # 获取 PersistentVolumeClaims
        print_step "PersistentVolumeClaims:"
        kubectl get pvc -n $HARBOR_NS -o wide

        # 获取 PersistentVolumes
        print_step "PersistentVolumes:"
        kubectl get pv -o wide | grep -E "harbor|registry"

        # 获取存储路径
        print_step "存储路径详情:"
        kubectl get pv -o jsonpath='{range .items[?(@.spec.claimRef.namespace=="'$HARBOR_NS'")]}{"\nPV Name: "}{.metadata.name}{"\nStorage Path: "}{.spec.local.path}{"\nNode: "}{.spec.nodeAffinity.required.nodeSelectorTerms[0].matchExpressions[0].values[0]}{"\n---\n"}{end}' 2>/dev/null || echo "未找到本地存储路径"

        # 检查 Harbor Registry Pod
        print_step "Harbor Registry Pod 信息:"
        kubectl get pods -n $HARBOR_NS -l "app=registry" -o wide 2>/dev/null || \
        kubectl get pods -n $HARBOR_NS -l "app.kubernetes.io/name=registry" -o wide 2>/dev/null || \
        echo "未找到 Registry Pod"

    else
        print_error "未找到 Harbor 命名空间"
    fi
else
    print_error "kubectl 未安装"
fi

echo ""

# -----------------------------------------------------------------------------
# 方法 2: 检查 Docker 卷
# -----------------------------------------------------------------------------
print_step "方法 2: 检查 Docker 卷..."

if command -v docker &> /dev/null; then
    # 查找 Harbor 相关的 Docker 卷
    print_info "Harbor 相关的 Docker 卷:"
    docker volume ls | grep -i harbor || echo "未找到 Harbor 相关的 Docker 卷"

    # 检查 registry 数据卷
    print_info "Registry 数据卷:"
    docker volume ls | grep -i registry || echo "未找到 Registry 卷"

    # 查看卷的详细信息
    VOLUME_NAME=$(docker volume ls | grep -i harbor | head -1 | awk '{print $2}')
    if [ -n "$VOLUME_NAME" ]; then
        print_step "卷详情 ($VOLUME_NAME):"
        docker volume inspect $VOLUME_NAME | jq '.[0].Mountpoint'
    fi
else
    print_error "Docker 未安装"
fi

echo ""

# -----------------------------------------------------------------------------
# 方法 3: 检查常见 Harbor 安装路径
# -----------------------------------------------------------------------------
print_step "方法 3: 检查常见 Harbor 安装路径..."

HARBOR_PATHS=(
    "/data/harbor"
    "/opt/harbor"
    "/var/lib/harbor"
    "/srv/harbor"
    "$HOME/harbor"
    "/mnt/data/harbor"
    "/var/lib/docker/volumes"
)

for path in "${HARBOR_PATHS[@]}"; do
    if [ -d "$path" ]; then
        print_success "找到路径：$path"
        # 显示目录大小
        du -sh "$path" 2>/dev/null | awk '{print "  目录大小："$1}'
        # 显示内容
        ls -la "$path" 2>/dev/null | head -10
    fi
done

echo ""

# -----------------------------------------------------------------------------
# 方法 4: 检查 Harbor 配置
# -----------------------------------------------------------------------------
print_step "方法 4: 检查 Harbor 配置文件..."

HARBOR_CONFIGS=(
    "/etc/harbor/harbor.yml"
    "/opt/harbor/harbor.yml"
    "$HOME/harbor/harbor.yml"
)

for config in "${HARBOR_CONFIGS[@]}"; do
    if [ -f "$config" ]; then
        print_success "找到配置文件：$config"
        print_info "数据目录配置:"
        grep -E "data_volume|storage_path" "$config" 2>/dev/null || echo "未找到存储路径配置"
    fi
done

echo ""

# -----------------------------------------------------------------------------
# 方法 5: 通过 Harbor API 检查
# -----------------------------------------------------------------------------
print_step "方法 5: 通过 Harbor API 检查存储统计..."

# 检查是否设置了 Harbor 认证信息
if [ -n "$HARBOR_USERNAME" ] && [ -n "$HARBOR_PASSWORD" ]; then
    HARBOR_REGISTRY="${HARBOR_REGISTRY:-harbor.sisys.local}"

    print_info "Harbor Registry: $HARBOR_REGISTRY"

    # 获取项目统计
    print_info "项目存储统计:"
    curl -sf -u "${HARBOR_USERNAME}:${HARBOR_PASSWORD}" \
      "https://${HARBOR_REGISTRY}/api/v2.0/statistics" 2>/dev/null | \
      jq '.' || echo "无法连接到 Harbor API"

    # 获取 sisys 项目详情
    print_info "SISYS 项目详情:"
    curl -sf -u "${HARBOR_USERNAME}:${HARBOR_PASSWORD}" \
      "https://${HARBOR_REGISTRY}/api/v2.0/projects/sisys" 2>/dev/null | \
      jq '.metadata | {storage_quota: .storage_quota, storage_usage: .storage_usage}' || \
      echo "无法获取项目信息"
else
    print_info "未设置 HARBOR_USERNAME 和 HARBOR_PASSWORD，跳过 API 检查"
    print_info "使用方法:"
    echo "  export HARBOR_USERNAME=admin"
    echo "  export HARBOR_PASSWORD=your_password"
    echo "  export HARBOR_REGISTRY=harbor.sisys.local"
fi

echo ""

# -----------------------------------------------------------------------------
# 方法 6: 检查本地 Docker 镜像
# -----------------------------------------------------------------------------
print_step "方法 6: 检查本地 Docker 镜像存储..."

if command -v docker &> /dev/null; then
    print_info "Docker 镜像存储位置:"
    docker info | grep "Docker Root Dir"

    print_info "Harbor 相关镜像:"
    docker images | grep -E "harbor|sisys" || echo "未找到 Harbor 相关镜像"

    print_info "本地镜像总大小:"
    docker images --format "{{.Size}}" | awk '{sum+=$1} END {print sum}' 2>/dev/null || echo "无法计算"
fi

echo ""

# -----------------------------------------------------------------------------
# 总结
# -----------------------------------------------------------------------------
print_header "检查完成"

print_info "总结:"
echo "  1. K8s PV/PVC: 查看方法 1 输出"
echo "  2. Docker 卷：查看方法 2 输出"
echo "  3. 文件系统：查看方法 3 输出"
echo "  4. 配置文件：查看方法 4 输出"
echo "  5. Harbor API: 查看方法 5 输出"
echo "  6. Docker 镜像：查看方法 6 输出"

echo ""
print_info "如需清理空间，参考:"
echo "  - docs/deployment/PREBUILT_IMAGE_MAINTENANCE.md"
echo "  - ./scripts/image/cleanup-old-versions.sh"

echo ""
