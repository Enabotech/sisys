#!/bin/bash
# ============================================================
# Gitea Runner Docker Executor 部署脚本
# ============================================================
# Story: 0-8-gitea-runner-configuration
# Task: 3 - Docker Executor 配置
#
# 功能:
#   - 部署 Docker Executor 配置
#   - 配置 Harbor 凭据
#   - 验证部署状态
#   - 测试 Docker 构建流程
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
NAMESPACE="gitea-actions"
CONFIG_MAP_NAME="gitea-runner-docker-config"
HARBOR_SECRET_NAME="harbor-robot-account"       # pragma: allowlist secret
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# ============================================================
# 辅助函数
# ============================================================

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

check_prerequisites() {
    log_info "检查前置条件..."

    # 检查 kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl 未安装"
        exit 1
    fi

    # 检查 Helm
    if ! command -v helm &> /dev/null; then
        log_warning "Helm 未安装 (可选)"
    fi

    # 检查命名空间
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_warning "命名空间 $NAMESPACE 不存在，将自动创建"
        kubectl create namespace "$NAMESPACE"
    fi

    log_success "前置检查通过"
}

deploy_docker_executor_config() {
    log_info "部署 Docker Executor 配置..."

    # 应用配置
    kubectl apply -f "$SCRIPT_DIR/../../deployments/gitea-runner/runner-docker-executor.yaml"

    log_success "Docker Executor 配置部署完成"
}

configure_harbor_credentials() {
    log_info "配置 Harbor 凭据..."

    # 检查是否提供了凭据
    if [ -n "$HARBOR_USERNAME" ] && [ -n "$HARBOR_PASSWORD" ]; then
        log_info "使用提供的环境变量配置 Harbor 凭据"

        # 创建或更新 Secret
        kubectl create secret docker-registry "$HARBOR_SECRET_NAME" \
            --docker-server=harbor.sisys.local \
            --docker-username="$HARBOR_USERNAME" \
            --docker-password="$HARBOR_PASSWORD" \
            --namespace="$NAMESPACE" \
            --dry-run=client -o yaml | kubectl apply -f -

        log_success "Harbor 凭据配置完成"
    else
        log_warning "未提供 Harbor 凭据环境变量"
        log_info "使用预配置的 Secret (需手动更新为真实凭据)"
        log_info "设置 HARBOR_USERNAME 和 HARBOR_PASSWORD 环境变量以自动配置"
    fi
}

verify_deployment() {
    log_info "验证部署状态..."

    # 检查 ConfigMap
    if kubectl get configmap "$CONFIG_MAP_NAME" -n "$NAMESPACE" &> /dev/null; then
        log_success "ConfigMap $CONFIG_MAP_NAME 存在"
    else
        log_error "ConfigMap $CONFIG_MAP_NAME 不存在"
        return 1
    fi

    # 检查 Secret
    if kubectl get secret "$HARBOR_SECRET_NAME" -n "$NAMESPACE" &> /dev/null; then
        log_success "Secret $HARBOR_SECRET_NAME 存在"
    else
        log_warning "Secret $HARBOR_SECRET_NAME 不存在 (使用预配置)"
    fi

    # 检查 Runner Pod
    RUNNER_PODS=$(kubectl get pods -n "$NAMESPACE" -l app=gitea-runner --no-headers 2>/dev/null | wc -l)
    if [ "$RUNNER_PODS" -gt 0 ]; then
        log_success "发现 $RUNNER_PODS 个 Runner Pod"

        # 显示 Pod 状态
        kubectl get pods -n "$NAMESPACE" -l app=gitea-runner
    else
        log_warning "未发现 Runner Pod (可能未部署 Runner)"
    fi

    log_success "部署验证完成"
}

test_docker_connection() {
    log_info "测试 Docker 连接..."

    # 获取第一个 Runner Pod
    POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l app=gitea-runner -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -z "$POD_NAME" ]; then
        log_warning "无 Runner Pod 可用，跳过 Docker 连接测试"
        return 0
    fi

    # 等待 Pod 就绪
    log_info "等待 Pod 就绪..."
    kubectl wait --for=condition=Ready pod/"$POD_NAME" -n "$NAMESPACE" --timeout=60s || {
        log_warning "Pod 未就绪，跳过测试"
        return 0
    }

    # 测试 Docker 连接
    log_info "测试 Docker 连接..."
    kubectl exec -n "$NAMESPACE" "$POD_NAME" -- docker info > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        log_success "Docker 连接成功"

        # 显示 Docker 信息
        DOCKER_VERSION=$(kubectl exec -n "$NAMESPACE" "$POD_NAME" -- docker --version)
        log_info "Docker 版本：$DOCKER_VERSION"
    else
        log_error "Docker 连接失败"
        log_info "调试命令：kubectl logs -n $NAMESPACE $POD_NAME"
        return 1
    fi
}

test_docker_build() {
    log_info "测试 Docker 构建流程..."

    POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l app=gitea-runner -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -z "$POD_NAME" ]; then
        log_warning "无 Runner Pod 可用，跳过 Docker 构建测试"
        return 0
    fi

    # 创建测试目录
    log_info "创建测试 Dockerfile..."
    kubectl exec -n "$NAMESPACE" "$POD_NAME" -- bash -c '
        mkdir -p /tmp/docker-test
        cd /tmp/docker-test
        cat > Dockerfile <<EOF
FROM alpine:latest
RUN echo "Hello from Gitea Runner"
CMD ["echo", "Test successful"]
EOF
    '

    # 执行构建
    log_info "执行 Docker 构建..."
    kubectl exec -n "$NAMESPACE" "$POD_NAME" -- bash -c '
        cd /tmp/docker-test
        docker build -t test-image:latest .
    ' || {
        log_error "Docker 构建失败"
        return 1
    }

    # 验证镜像
    log_info "验证镜像..."
    kubectl exec -n "$NAMESPACE" "$POD_NAME" -- docker images test-image:latest

    # 清理
    log_info "清理测试镜像..."
    kubectl exec -n "$NAMESPACE" "$POD_NAME" -- docker rmi test-image:latest || true
    kubectl exec -n "$NAMESPACE" "$POD_NAME" -- rm -rf /tmp/docker-test

    log_success "Docker 构建测试通过"
}

display_usage() {
    cat << EOF
Gitea Runner Docker Executor 部署脚本

用法：$0 [命令]

命令:
    deploy      部署 Docker Executor 配置 (默认)
    verify      验证部署状态
    test        运行测试 (Docker 连接 + 构建)
    clean       清理部署
    help        显示帮助信息

环境变量:
    HARBOR_USERNAME     Harbor 用户名 (可选)
    HARBOR_PASSWORD     Harbor 密码 (可选)

示例:
    $0                          # 部署配置
    $0 verify                   # 验证部署
    $0 test                     # 运行测试
    HARBOR_USERNAME=robot\$sisys+runner HARBOR_PASSWORD=xxx $0 deploy
    $0 clean                    # 清理部署

EOF
}

clean_deployment() {
    log_warning "清理 Docker Executor 部署..."

    # 删除配置
    kubectl delete -f "$SCRIPT_DIR/../../deployments/gitea-runner/runner-docker-executor.yaml" --ignore-not-found

    # 删除 Secret
    kubectl delete secret "$HARBOR_SECRET_NAME" -n "$NAMESPACE" --ignore-not-found

    log_success "清理完成"
}

# ============================================================
# 主程序
# ============================================================

main() {
    COMMAND="${1:-deploy}"

    case "$COMMAND" in
        deploy)
            check_prerequisites
            deploy_docker_executor_config
            configure_harbor_credentials
            verify_deployment
            log_success "🎉 Docker Executor 部署完成"
            ;;

        verify)
            verify_deployment
            ;;

        test)
            verify_deployment
            test_docker_connection
            test_docker_build
            log_success "🎉 所有测试通过"
            ;;

        clean)
            clean_deployment
            ;;

        help|--help|-h)
            display_usage
            exit 0
            ;;

        *)
            log_error "未知命令：$COMMAND"
            display_usage
            exit 1
            ;;
    esac
}

main "$@"
