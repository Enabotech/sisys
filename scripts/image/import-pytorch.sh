#!/bin/bash
# =============================================================================
# PyTorch 基础镜像导入脚本 (Layer 1)
# =============================================================================
# 功能：从本地备份导入 PyTorch 镜像到 Docker 和 Harbor
# =============================================================================

set -euo pipefail

# 配置
BACKUP_FILE="${BACKUP_FILE:-/mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar}"
HARBOR_URL="${HARBOR_URL:-harbor.sisys.local}"
HARBOR_USERNAME="${HARBOR_USERNAME:-admin}"
HARBOR_PASSWORD="${HARBOR_PASSWORD:-Admin@123456}"
HARBOR_PROJECT="${HARBOR_PROJECT:-sisys}"

# 镜像名称
LOCAL_IMAGE="pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel"
HARBOR_IMAGE="$HARBOR_URL/$HARBOR_PROJECT/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# 步骤 1: 验证备份文件
# =============================================================================

verify_backup() {
    log_info "步骤 1: 验证备份文件..."
    
    if [ ! -f "$BACKUP_FILE" ]; then
        log_error "备份文件不存在：$BACKUP_FILE"
        exit 1
    fi
    
    local file_size
    file_size=$(du -h "$BACKUP_FILE" | cut -f1)
    log_info "  文件路径：$BACKUP_FILE"
    log_info "  文件大小：$file_size"
    
    # 验证文件完整性 (可选)
    if [ -f "${BACKUP_FILE}.sha256" ]; then
        log_info "  验证 SHA256..."
        if sha256sum -c "${BACKUP_FILE}.sha256" &> /dev/null; then
            log_success "  SHA256 验证通过"
        else
            log_error "  SHA256 验证失败，文件可能损坏"
            exit 1
        fi
    else
        log_warning "  未找到 SHA256 校验文件，跳过完整性验证"
    fi
}

# =============================================================================
# 步骤 2: 导入到 Docker
# =============================================================================

import_to_docker() {
    log_info "步骤 2: 导入到 Docker..."
    
    # 检查是否已存在
    if docker image inspect "$LOCAL_IMAGE" &> /dev/null; then
        log_warning "镜像已存在：$LOCAL_IMAGE"
        read -p "是否覆盖？[y/N]: " confirm
        if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
            log_info "跳过导入"
            return 0
        fi
        docker rmi "$LOCAL_IMAGE"
    fi
    
    # 导入镜像
    log_info "  执行导入..."
    docker load -i "$BACKUP_FILE"
    
    # 验证导入
    if docker image inspect "$LOCAL_IMAGE" &> /dev/null; then
        log_success "  导入成功：$LOCAL_IMAGE"
    else
        log_error "  导入失败"
        exit 1
    fi
}

# =============================================================================
# 步骤 3: 验证 GPU 兼容性
# =============================================================================

verify_gpu() {
    log_info "步骤 3: 验证 GPU 兼容性..."
    
    # 检查 NVIDIA Docker
    if ! docker run --rm --gpus all nvidia/cuda:12.8.0-base nvidia-smi &> /dev/null; then
        log_warning "NVIDIA Docker 不可用，跳过 GPU 验证"
        log_info "  请确保已安装 NVIDIA Container Toolkit"
        return 0
    fi
    
    # 测试 PyTorch GPU
    log_info "  测试 PyTorch GPU..."
    local gpu_test
    gpu_test=$(docker run --rm --gpus all "$LOCAL_IMAGE" \
        python3 -c "import torch; print(f'CUDA 可用：{torch.cuda.is_available()}'); print(f'CUDA 版本：{torch.version.cuda}')" 2>&1 || echo "")
    
    if echo "$gpu_test" | grep -q "CUDA 可用：True"; then
        log_success "  GPU 验证通过"
        log_info "  $gpu_test"
    else
        log_warning "  GPU 验证失败或不可用"
        log_info "  $gpu_test"
    fi
}

# =============================================================================
# 步骤 4: 推送到 Harbor
# =============================================================================

push_to_harbor() {
    log_info "步骤 4: 推送到 Harbor..."
    
    # 登录 Harbor
    log_info "  登录 Harbor..."
    if ! docker login "$HARBOR_URL" -u "$HARBOR_USERNAME" -p "$HARBOR_PASSWORD" &> /dev/null; then
        log_error "  Harbor 登录失败"
        exit 1
    fi
    log_success "  Harbor 登录成功"
    
    # 检查项目存在
    log_info "  检查项目：$HARBOR_PROJECT"
    local response
    response=$(curl -k -s -o /dev/null -w "%{http_code}" \
        -u "$HARBOR_USERNAME:$HARBOR_PASSWORD" \
        "https://$HARBOR_URL/api/v2.0/projects/$HARBOR_PROJECT")
    
    if [ "$response" == "404" ]; then
        log_info "    项目不存在，尝试创建..."
        curl -k -s -X POST \
            -u "$HARBOR_USERNAME:$HARBOR_PASSWORD" \
            -H "Content-Type: application/json" \
            -d "{\"project_name\":\"$HARBOR_PROJECT\",\"metadata\":{\"public\":\"false\"}}" \
            "https://$HARBOR_URL/api/v2.0/projects" > /dev/null
        log_success "    项目创建成功"
    else
        log_success "    项目已存在"
    fi
    
    # 标记镜像
    log_info "  标记镜像..."
    docker tag "$LOCAL_IMAGE" "$HARBOR_IMAGE"
    
    # 推送镜像
    log_info "  推送到 Harbor..."
    docker push "$HARBOR_IMAGE"
    
    # 验证推送
    log_info "  验证推送..."
    if docker pull "$HARBOR_IMAGE" &> /dev/null; then
        log_success "  推送成功：$HARBOR_IMAGE"
    else
        log_error "  推送失败或验证失败"
        exit 1
    fi
}

# =============================================================================
# 步骤 5: 生成报告
# =============================================================================

generate_report() {
    log_info "步骤 5: 生成报告..."
    
    cat << EOF

============================================
  PyTorch 镜像导入完成
============================================

镜像信息:
  本地镜像：$LOCAL_IMAGE
  Harbor 镜像：$HARBOR_IMAGE

使用方式:

1. 在 Dockerfile 中使用:
   FROM $HARBOR_IMAGE

2. 在 Gitea Actions 中使用:
   container:
     image: $HARBOR_IMAGE

3. 作为 Layer 1 构建 Layer 2:
   docker build --build-arg PYTORCH_IMAGE=$HARBOR_IMAGE ...

下一步:
  1. 运行 ./scripts/image/build-dependency-image.sh 构建 Layer 2
  2. 验证 CI/CD Pipeline

============================================
EOF
}

# =============================================================================
# 主函数
# =============================================================================

main() {
    echo "=============================================="
    echo "  PyTorch 基础镜像导入工具 (Layer 1)"
    echo "=============================================="
    echo
    echo "备份文件：$BACKUP_FILE"
    echo "Harbor: $HARBOR_URL"
    echo
    
    verify_backup
    import_to_docker
    verify_gpu
    push_to_harbor
    
    generate_report
    
    log_success "所有步骤完成！"
}

main "$@"
