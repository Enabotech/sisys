#!/bin/bash

# Gitea Runner 部署脚本
# Story: 0-8-gitea-runner-configuration
# Task: 2 - Gitea Runner 部署

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置变量
NAMESPACE="gitea-actions"
RELEASE_NAME="gitea-runner"
CHART_PATH="deployments/gitea-runner"
VALUES_FILE="deployments/gitea-runner/values.yaml"
KUBECTL_MANIFEST="deployments/gitea-runner/gitea-runner-deployment.yaml"

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查前置条件
check_prerequisites() {
    print_info "========== 检查前置条件 =========="

    # 检查 kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl 未安装"
        exit 1
    fi
    print_success "kubectl 已安装"

    # 检查 Helm（可选）
    if command -v helm &> /dev/null; then
        print_success "Helm 已安装（推荐使用 Helm 部署）"
        USE_HELM=true
    else
        print_warning "Helm 未安装，将使用 kubectl 部署"
        USE_HELM=false
    fi

    # 检查 K8s 集群连接
    if ! kubectl cluster-info &> /dev/null; then
        print_error "无法连接到 K8s 集群"
        exit 1
    fi
    print_success "已连接到 K8s 集群"

    # 检查 Secret 是否存在
    if ! kubectl get secret gitea-runner-token -n "$NAMESPACE" &> /dev/null; then
        print_error "Secret 'gitea-runner-token' 不存在"
        print_info "请先运行：bash scripts/deployment/gitea-runner/configure-token.sh"
        exit 1
    fi
    print_success "Secret 'gitea-runner-token' 已存在"
}

# 使用 Helm 部署
deploy_with_helm() {
    print_info "========== 使用 Helm 部署 =========="

    # 检查 values 文件
    if [ ! -f "$VALUES_FILE" ]; then
        print_error "Values 文件不存在：$VALUES_FILE"
        exit 1
    fi

    # 添加 Gitea Helm 仓库（如果需要）
    if ! helm repo list | grep -q "gitea"; then
        print_info "添加 Gitea Helm 仓库..."
        helm repo add gitea https://dl.gitea.com/charts/
        helm repo update
    fi

    # 部署
    print_info "部署 Gitea Runner..."
    helm upgrade --install "$RELEASE_NAME" "$CHART_PATH" \
        -n "$NAMESPACE" \
        -f "$VALUES_FILE" \
        --create-namespace

    print_success "Helm 部署完成"
}

# 使用 kubectl 部署
deploy_with_kubectl() {
    print_info "========== 使用 kubectl 部署 =========="

    # 检查 manifest 文件
    if [ ! -f "$KUBECTL_MANIFEST" ]; then
        print_error "Manifest 文件不存在：$KUBECTL_MANIFEST"
        exit 1
    fi

    # 创建命名空间
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    print_success "命名空间 $NAMESPACE 已创建/存在"

    # 应用 manifest
    print_info "应用 Gitea Runner 配置..."
    kubectl apply -f "$KUBECTL_MANIFEST"

    print_success "kubectl 部署完成"
}

# 验证部署
verify_deployment() {
    print_info "========== 验证部署 =========="

    # 等待 Pod 启动
    print_info "等待 Pod 启动（最多 120 秒）..."
    kubectl wait --for=condition=Ready pods \
        -l app=gitea-runner \
        -n "$NAMESPACE" \
        --timeout=120s || {
        print_warning "部分 Pod 未就绪，继续检查..."
    }

    # 显示 Pod 状态
    print_info "Pod 状态："
    kubectl get pods -n "$NAMESPACE" -l app=gitea-runner

    # 显示 Deployment 状态
    print_info "Deployment 状态："
    kubectl get deployment gitea-runner -n "$NAMESPACE"

    # 检查 Runner 状态
    print_info ""
    print_info "请前往 Gitea 管理页面验证 Runner 状态："
    print_info "  https://gitea.sisys.local/-/admin/actions/runners"
    print_info ""
    print_info "预期状态：Runner 应显示为'空闲'或'在线'"
}

# 显示下一步
print_next_steps() {
    echo ""
    print_success "========== Gitea Runner 部署完成 =========="
    echo ""
    echo "常用命令："
    echo ""
    echo "  # 查看 Pod 状态"
    echo "  kubectl get pods -n $NAMESPACE -l app=gitea-runner"
    echo ""
    echo "  # 查看日志"
    echo "  kubectl logs -n $NAMESPACE -l app=gitea-runner -f"
    echo ""
    echo "  # 重启 Runner"
    echo "  kubectl rollout restart deployment/gitea-runner -n $NAMESPACE"
    echo ""
    echo "  # 扩容/缩容"
    echo "  kubectl scale deployment/gitea-runner --replicas=5 -n $NAMESPACE"
    echo ""
    echo "下一步："
    echo "  1. 验证 Runner 在 Gitea 管理页面显示为'空闲'"
    echo "  2. 继续执行 Task 3: Docker Executor 配置"
    echo "  3. 继续执行 Task 4: K8s Executor 配置"
    echo ""
}

# 主函数
main() {
    echo ""
    print_info "========================================"
    print_info "  Gitea Runner 部署脚本"
    print_info "  Story: 0-8-gitea-runner-configuration"
    print_info "  Task: 2 - Gitea Runner 部署"
    print_info "========================================"
    echo ""

    # 前置检查
    check_prerequisites

    # 选择部署方式
    if [ "$USE_HELM" = true ]; then
        read -p "选择部署方式 (Helm=1, kubectl=2): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[2]$ ]]; then
            USE_HELM=false
        fi
    fi

    # 执行部署
    if [ "$USE_HELM" = true ]; then
        deploy_with_helm
    else
        deploy_with_kubectl
    fi

    # 验证
    verify_deployment

    # 下一步
    print_next_steps
}

# 执行
main
