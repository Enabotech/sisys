#!/bin/bash

# Gitea Runner Token 配置脚本
# Story: 0-8-gitea-runner-configuration
# Task: 1 - Gitea Runner Token 配置

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
NAMESPACE="gitea-actions"
SECRET_NAME="gitea-runner-token"
GITEA_URL="https://gitea.sisys.local"

# 打印带颜色的消息
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

# 检查 kubectl 是否可用
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl 未安装，请先安装 kubectl"
        exit 1
    fi
    print_success "kubectl 已安装"
}

# 检查 K8s 集群连接
check_cluster() {
    if ! kubectl cluster-info &> /dev/null; then
        print_error "无法连接到 K8s 集群，请检查 kubeconfig 配置"
        exit 1
    fi
    print_success "已连接到 K8s 集群"
}

# 检查命名空间是否存在
check_namespace() {
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        print_warning "命名空间 $NAMESPACE 不存在，正在创建..."
        kubectl create namespace "$NAMESPACE"
        print_success "命名空间 $NAMESPACE 创建成功"
    else
        print_success "命名空间 $NAMESPACE 已存在"
    fi
}

# 指导用户创建 Token
guide_create_token() {
    echo ""
    print_info "========== 步骤 1: 在 Gitea 管理页面创建 Runner Token =========="
    echo ""
    echo "请按照以下步骤操作："
    echo ""
    echo "1. 打开浏览器访问：$GITEA_URL"
    echo "2. 使用管理员账号登录（默认：gitea_admin）"
    echo "3. 点击右上角头像 → 站点管理"
    echo "4. 左侧菜单选择 设置 → Actions"
    echo "5. 点击 添加 Runner 按钮"
    echo "6. 填写 Runner 信息："
    echo "   - Runner 名称：k8s-runner-01"
    echo "   - Runner 标签：docker,k8s,standard"
    echo "   - Runner 类型：组织级别"
    echo "7. 点击 生成 Token"
    echo "8. **重要**: 复制生成的 Token（类似：1f182aca3d38b66f7e49c034d98fb15bf02434b7）"
    echo "   ⚠️ Token 只会显示一次，请立即保存"
    echo ""

    read -p "是否已完成 Token 创建？(y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "请先完成 Token 创建"
        exit 1
    fi
    print_success "Token 创建完成"
}

# 获取用户输入的 Token
get_token() {
    echo ""
    print_info "========== 步骤 2: 输入 Token =========="
    echo ""

    # 使用 -s 隐藏输入
    read -s -p "请输入 Gitea Runner Token: " TOKEN
    echo ""

    if [ -z "$TOKEN" ]; then
        print_error "Token 不能为空"
        exit 1
    fi

    # 验证 Token 格式（40 位字母数字）
    if [[ ! "$TOKEN" =~ ^[a-zA-Z0-9]{40}$ ]]; then
        print_warning "Token 格式可能不正确（应为 40 位字母数字）"
        read -p "是否继续？(y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    print_success "Token 已输入"
}

# 创建 Kubernetes Secret
create_secret() {
    print_info "========== 步骤 3: 创建 Kubernetes Secret =========="
    echo ""

    # 检查 Secret 是否已存在
    if kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" &> /dev/null; then
        print_warning "Secret $SECRET_NAME 已存在，正在更新..."
    fi

    # 创建 Secret
    kubectl create secret generic "$SECRET_NAME" \
        --from-literal=token="$TOKEN" \
        -n "$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -

    print_success "Secret 创建成功"
}

# 验证 Secret
verify_secret() {
    print_info "========== 步骤 4: 验证 Secret =========="
    echo ""

    # 检查 Secret 是否存在
    if kubectl get secret "$SECRET_NAME" -n "$NAMESPACE"; then
        print_success "Secret 已创建"
    else
        print_error "Secret 创建失败"
        exit 1
    fi

    # 验证 Token 值（可选）
    echo ""
    read -p "是否验证 Token 值？(y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        STORED_TOKEN=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" \
            -o jsonpath='{.data.token}' | base64 -d)

        if [ "$STORED_TOKEN" == "$TOKEN" ]; then
            print_success "Token 值验证通过"
        else
            print_error "Token 值不匹配"
            exit 1
        fi
    fi
}

# 测试 Token 连接
test_token() {
    print_info "========== 步骤 5: 测试 Token 连接（可选） =========="
    echo ""

    read -p "是否测试 Token 连接？(y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "跳过 Token 连接测试"
        return
    fi

    # 使用 Token 测试 Gitea API
    RESPONSE=$(curl -k -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: token $TOKEN" \
        "$GITEA_URL/api/v1/admin/runners")

    if [ "$RESPONSE" == "200" ]; then
        print_success "Token 连接测试通过"
    elif [ "$RESPONSE" == "401" ]; then
        print_error "Token 认证失败，请检查 Token 是否正确"
        exit 1
    elif [ "$RESPONSE" == "000" ]; then
        print_warning "无法连接到 Gitea API，请检查网络或 Gitea 服务状态"
    else
        print_warning "Gitea API 返回未知状态码：$RESPONSE"
    fi
}

# 输出摘要
print_summary() {
    echo ""
    print_success "========== Gitea Runner Token 配置完成 =========="
    echo ""
    echo "配置摘要："
    echo "  - Secret 名称：$SECRET_NAME"
    echo "  - 命名空间：$NAMESPACE"
    echo "  - Gitea URL: $GITEA_URL"
    echo ""
    echo "下一步操作："
    echo "  1. 运行以下命令验证 Secret："
    echo "     kubectl get secret $SECRET_NAME -n $NAMESPACE"
    echo ""
    echo "  2. 继续执行 Task 2: Gitea Runner 部署"
    echo "     bash scripts/deployment/gitea-runner/deploy-runner.sh"
    echo ""
    echo "  3. 查看配置文档："
    echo "     cat docs/deployment/GITEA_RUNNER_TOKEN_CONFIG.md"
    echo ""
}

# 主函数
main() {
    echo ""
    print_info "========================================"
    print_info "  Gitea Runner Token 配置脚本"
    print_info "  Story: 0-8-gitea-runner-configuration"
    print_info "  Task: 1 - Gitea Runner Token 配置"
    print_info "========================================"
    echo ""

    # 前置检查
    check_kubectl
    check_cluster
    check_namespace

    # 配置步骤
    guide_create_token
    get_token
    create_secret
    verify_secret
    test_token

    # 输出摘要
    print_summary
}

# 执行主函数
main
