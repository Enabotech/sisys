#!/bin/bash
# 本地 PyTorch 镜像导入脚本
# 功能：将本地备份的 PyTorch 镜像导入 Docker 并推送到 Harbor
# 镜像文件：/mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar

set -e  # 遇到错误立即退出

# ===========================================================================
# 配置变量
# ===========================================================================
LOCAL_IMAGE_PATH="/mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar"
HARBOR_REGISTRY="harbor.sisys.local"
HARBOR_PROJECT="sisys"
IMAGE_NAME="pytorch/pytorch"
IMAGE_TAG="2.7.1-cuda12.8-cudnn9-devel"
HARBOR_USERNAME="${HARBOR_USERNAME:-admin}"  # 可从环境变量读取
HARBOR_PASSWORD="${HARBOR_PASSWORD:-}"       # 建议从环境变量读取

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ===========================================================================
# 函数定义
# ===========================================================================
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_file_exists() {
    if [ ! -f "$LOCAL_IMAGE_PATH" ]; then
        log_error "镜像文件不存在：$LOCAL_IMAGE_PATH"
        exit 1
    fi
    log_info "镜像文件存在：$LOCAL_IMAGE_PATH"
}

check_docker_installed() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi
    log_info "Docker 已安装：$(docker --version)"
}

check_gpu_support() {
    if ! command -v nvidia-smi &> /dev/null; then
        log_warn "nvidia-smi 未找到，GPU 支持可能不可用"
        return 1
    fi
    log_info "GPU 支持可用：$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n 1)"
    return 0
}

# ===========================================================================
# 主流程
# ===========================================================================
main() {
    log_info "=========================================="
    log_info "  本地 PyTorch 镜像导入脚本"
    log_info "=========================================="
    
    # 步骤 1: 预检查
    log_info "步骤 1: 预检查..."
    check_file_exists
    check_docker_installed
    check_gpu_support || true  # GPU 可选
    
    # 步骤 2: 导入镜像到 Docker
    log_info "步骤 2: 导入镜像到 Docker..."
    docker load -i "$LOCAL_IMAGE_PATH"
    
    # 步骤 3: 验证导入
    log_info "步骤 3: 验证导入..."
    docker images | grep -E "pytorch.*2.7.1" || {
        log_error "镜像导入失败"
        exit 1
    }
    log_info "镜像导入成功"
    
    # 步骤 4: 标记镜像
    log_info "步骤 4: 标记镜像..."
    FULL_IMAGE_NAME="${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"
    docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "${FULL_IMAGE_NAME}"
    log_info "镜像标记为：${FULL_IMAGE_NAME}"
    
    # 步骤 5: 登录 Harbor
    log_info "步骤 5: 登录 Harbor..."
    if [ -z "$HARBOR_PASSWORD" ]; then
        log_warn "HARBOR_PASSWORD 未设置，请手动输入密码"
        docker login "${HARBOR_REGISTRY}" -u "${HARBOR_USERNAME}" -p "${HARBOR_PASSWORD}"
    else
        docker login "${HARBOR_REGISTRY}" -u "${HARBOR_USERNAME}" -p "${HARBOR_PASSWORD}"
    fi
    
    # 步骤 6: 推送镜像到 Harbor
    log_info "步骤 6: 推送镜像到 Harbor..."
    docker push "${FULL_IMAGE_NAME}"
    
    # 步骤 7: 验证 GPU 兼容性
    log_info "步骤 7: 验证 GPU 兼容性..."
    if check_gpu_support; then
        docker run --rm --gpus all "${FULL_IMAGE_NAME}" \
            python3 -c "import torch; print(f'CUDA 可用：{torch.cuda.is_available()}'); print(f'CUDA 版本：{torch.version.cuda}')" || \
            log_warn "GPU 验证失败，请检查镜像完整性"
    else
        log_warn "跳过 GPU 验证 (GPU 不可用)"
    fi
    
    # 步骤 8: 清理
    log_info "步骤 8: 清理..."
    docker logout "${HARBOR_REGISTRY}"
    
    # 完成
    log_info "=========================================="
    log_info "  导入完成!"
    log_info "=========================================="
    log_info "镜像信息:"
    log_info "  - 本地标签：${IMAGE_NAME}:${IMAGE_TAG}"
    log_info "  - Harbor 标签：${FULL_IMAGE_NAME}"
    log_info ""
    log_info "使用示例:"
    log_info "  docker pull ${FULL_IMAGE_NAME}"
    log_info "  docker run --rm --gpus all ${FULL_IMAGE_NAME} python3 -c 'import torch; print(torch.cuda.is_available())'"
    log_info ""
    log_info "下一步:"
    log_info "  1. 在 CI/CD Pipeline 中使用此镜像作为 Layer 1"
    log_info "  2. 更新 .gitea/workflows/ci.yaml 中的 PYTORCH_IMAGE 变量"
    log_info "  3. 验证 GPU 任务调度正常"
}

# 显示帮助
show_help() {
    cat << EOF
本地 PyTorch 镜像导入脚本

用法：$0 [选项]

选项:
  -h, --help      显示帮助信息
  -u, --username  Harbor 用户名 (默认：admin)
  -p, --password  Harbor 密码 (默认：从环境变量读取)
  -f, --file      镜像文件路径 (默认：/mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar)

示例:
  $0                                    # 使用默认配置
  $0 -u admin -p Harbor123              # 指定用户名和密码
  $0 -f /path/to/image.tar              # 指定镜像文件
  HARBOR_PASSWORD=secret $0             # 通过环境变量传递密码

EOF
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -u|--username)
            HARBOR_USERNAME="$2"
            shift 2
            ;;
        -p|--password)
            HARBOR_PASSWORD="$2"
            shift 2
            ;;
        -f|--file)
            LOCAL_IMAGE_PATH="$2"
            shift 2
            ;;
        *)
            log_error "未知选项：$1"
            show_help
            exit 1
            ;;
    esac
done

# 执行主流程
main
