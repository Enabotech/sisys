#!/bin/bash

# =============================================================================
# PyTorch 镜像导入脚本
# =============================================================================
# 用途：将本地备份的 PyTorch 镜像导入 Docker 并推送到 Harbor
# 关联 Story: 0.9 (CI/CD Pipeline 模板)
# 文档：docs/deployment/LOCAL_PYTORCH_IMPORT.md
# =============================================================================

set -e  # 遇到错误立即退出

# -----------------------------------------------------------------------------
# 配置变量
# -----------------------------------------------------------------------------
SOURCE_FILE="/mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar"
HARBOR_REGISTRY="${HARBOR_REGISTRY:-harbor.sisys.local}"
HARBOR_PROJECT="${HARBOR_PROJECT:-sisys}"
IMAGE_NAME="pytorch-base"
IMAGE_TAG="2.7.1-cuda12.8"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# 函数定义
# -----------------------------------------------------------------------------
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

check_prerequisites() {
    print_step "检查前置条件..."

    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi

    # 检查 nvidia-docker
    if ! docker info 2>&1 | grep -q "NVIDIA"; then
        print_error "NVIDIA Docker 未配置，请安装 NVIDIA Container Toolkit"
        exit 1
    fi

    # 检查源文件
    if [ ! -f "${SOURCE_FILE}" ]; then
        print_error "源文件不存在：${SOURCE_FILE}"
        exit 1
    fi

    print_success "前置条件检查通过"
}

# -----------------------------------------------------------------------------
# 主流程
# -----------------------------------------------------------------------------
print_header "PyTorch 镜像导入脚本"
echo "源文件：${SOURCE_FILE}"
echo "目标：${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"
echo ""

# 步骤 0: 检查前置条件
check_prerequisites

# 步骤 1: 验证源文件
print_step "步骤 1: 验证源文件..."
if [ ! -f "${SOURCE_FILE}" ]; then
    print_error "源文件不存在 ${SOURCE_FILE}"
    exit 1
fi

FILE_SIZE=$(du -h "${SOURCE_FILE}" | cut -f1)
print_success "文件大小：${FILE_SIZE}"

# 步骤 2: 导入到 Docker
print_step "步骤 2: 导入到 Docker..."
docker load -i "${SOURCE_FILE}"
print_success "导入完成"

# 步骤 3: 本地验证
print_step "步骤 3: 本地 GPU 验证..."
docker run --rm --gpus all \
  pytorch/pytorch:${IMAGE_TAG}-devel \
  python3 -c "
import torch
print(f'✅ PyTorch 版本：{torch.__version__}')
print(f'✅ CUDA 版本：{torch.version.cuda}')
print(f'✅ CUDA 可用：{torch.cuda.is_available()}')
"

# 步骤 4: 推送到 Harbor
print_step "步骤 4: 推送到 Harbor..."

# 检查是否已登录
if ! docker info 2>&1 | grep -q "${HARBOR_REGISTRY}"; then
    print_error "未登录 Harbor"
    echo ""
    echo "请先执行以下命令之一："
    echo ""
    echo "  # 方式 1: 命令行登录"
    echo "  docker login ${HARBOR_REGISTRY}"
    echo ""
    echo "  # 方式 2: 设置环境变量"
    echo "  export HARBOR_USERNAME=xxx"
    echo "  export HARBOR_PASSWORD=xxx"
    echo "  docker login -u \${HARBOR_USERNAME} -p \${HARBOR_PASSWORD} ${HARBOR_REGISTRY}"
    echo ""
    exit 1
fi

# 打标签
docker tag pytorch/pytorch:${IMAGE_TAG}-devel \
  ${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}

print_success "镜像标签：${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"

# 推送
print_step "推送到 Harbor..."
docker push ${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}

print_success "推送完成"

# 步骤 5: 最终验证
print_step "步骤 5: 最终验证..."
docker pull ${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}
docker run --rm --gpus all \
  ${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG} \
  python3 -c "import torch; print('✅ Harbor 镜像验证通过')"

print_success "验证完成"

# 完成
echo ""
print_header "✅ PyTorch 镜像导入完成！"
echo ""
echo "使用示例:"
echo "  docker run --rm --gpus all ${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG} python3"
echo ""
echo "下一步:"
echo "  1. 验证 CI/CD Pipeline 配置"
echo "  2. 运行依赖镜像构建"
echo "  3. 测试完整 CI 流程"
echo ""
echo "相关文档:"
echo "  - docs/deployment/LOCAL_PYTORCH_IMPORT.md"
echo "  - docs/deployment/PREBUILT_IMAGE_MAINTENANCE.md"
echo "  - docs/deployment/CI_CD_PIPELINE_TEMPLATE.md"
echo ""
