#!/bin/bash
# =============================================================================
# Gitea Actions 离线环境验证脚本
# =============================================================================
# 功能：验证所有 Actions 和 Docker 镜像已本地化，可在无网环境运行
# =============================================================================

set -euo pipefail

# 配置
GITEA_URL="${GITEA_URL:-https://gitea.sisys.local}"
GITEA_TOKEN="${GITEA_TOKEN:-}"
HARBOR_URL="${HARBOR_URL:-harbor.sisys.local}"
HARBOR_USERNAME="${HARBOR_USERNAME:-admin}"
HARBOR_PASSWORD="${HARBOR_PASSWORD:-Admin@123456}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

# =============================================================================
# 验证函数
# =============================================================================

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASS_COUNT++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAIL_COUNT++))
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARN_COUNT++))
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# =============================================================================
# 验证 Gitea 配置
# =============================================================================

verify_gitea_config() {
    echo
    log_info "验证 Gitea 配置..."
    
    # 检查 Gitea 可访问性
    if curl -s -o /dev/null -w "%{http_code}" "$GITEA_URL" | grep -q "200\|302"; then
        log_pass "Gitea 实例可访问：$GITEA_URL"
    else
        log_fail "Gitea 实例无法访问：$GITEA_URL"
        return 1
    fi
    
    # 检查 Actions 是否启用
    local actions_config
    actions_config=$(curl -s "$GITEA_URL/api/v1/settings" | jq -r '.actions.enabled' 2>/dev/null || echo "null")
    
    if [ "$actions_config" == "true" ]; then
        log_pass "Gitea Actions 已启用"
    else
        log_warn "无法验证 Actions 状态 (可能需要管理员权限)"
    fi
    
    # 检查 Actions 组织
    if [ -n "$GITEA_TOKEN" ]; then
        local response
        response=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "Authorization: token $GITEA_TOKEN" \
            "$GITEA_URL/api/v1/orgs/actions")
        
        if [ "$response" == "200" ]; then
            log_pass "Actions 组织存在"
        else
            log_fail "Actions 组织不存在，需要创建"
        fi
    else
        log_warn "未设置 GITEA_TOKEN，跳过详细检查"
    fi
}

# =============================================================================
# 验证 Actions
# =============================================================================

verify_actions() {
    echo
    log_info "验证 Actions..."
    
    # Actions 清单
    local actions=(
        "actions/checkout"
        "actions/upload-artifact"
        "actions/download-artifact"
        "docker/setup-buildx-action"
        "docker/login-action"
        "docker/build-push-action"
        "aquasecurity/trivy-action"
    )
    
    for action in "${actions[@]}"; do
        local repo_name="${action//\//_}"
        
        if [ -n "$GITEA_TOKEN" ]; then
            local response
            response=$(curl -s -o /dev/null -w "%{http_code}" \
                -H "Authorization: token $GITEA_TOKEN" \
                "$GITEA_URL/api/v1/repos/actions/$repo_name")
            
            if [ "$response" == "200" ]; then
                log_pass "Action 已镜像：$action -> actions/$repo_name"
            elif [ "$response" == "404" ]; then
                log_fail "Action 未镜像：$action -> actions/$repo_name"
            else
                log_warn "Action 状态未知：$action (HTTP $response)"
            fi
        else
            # 无 Token 时尝试直接访问
            local url="$GITEA_URL/actions/$repo_name"
            if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "200"; then
                log_pass "Action 可访问：$action"
            else
                log_warn "无法验证 Action (需要 Token): $action"
            fi
        fi
    done
}

# =============================================================================
# 验证 Docker 镜像
# =============================================================================

verify_docker_images() {
    echo
    log_info "验证 Docker 镜像..."
    
    # 镜像清单
    local images=(
        "$HARBOR_URL/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel"
        "$HARBOR_URL/sisys/dependency:latest"
        "$HARBOR_URL/sisys/app:latest"
        "docker:24-dind"
        "bitnami/kubectl:latest"
    )
    
    for image in "${images[@]}"; do
        if docker image inspect "$image" &> /dev/null; then
            log_pass "Docker 镜像已本地化：$image"
        else
            # 尝试从 Harbor 拉取
            log_info "  尝试从 Harbor 拉取：$image"
            if docker pull "$image" &> /dev/null; then
                log_pass "Docker 镜像可从 Harbor 拉取：$image"
            else
                log_fail "Docker 镜像不可用：$image"
            fi
        fi
    done
}

# =============================================================================
# 验证 Harbor
# =============================================================================

verify_harbor() {
    echo
    log_info "验证 Harbor..."
    
    # 检查 Harbor 可访问性
    if curl -k -s -o /dev/null -w "%{http_code}" "https://$HARBOR_URL" | grep -q "200"; then
        log_pass "Harbor 可访问：$HARBOR_URL"
    else
        log_fail "Harbor 无法访问：$HARBOR_URL"
        return 1
    fi
    
    # 验证认证
    local response
    response=$(curl -k -s -o /dev/null -w "%{http_code}" \
        -u "$HARBOR_USERNAME:$HARBOR_PASSWORD" \
        "https://$HARBOR_URL/api/v2.0/users/me")
    
    if [ "$response" == "200" ]; then
        log_pass "Harbor 认证成功"
    else
        log_fail "Harbor 认证失败 (HTTP $response)"
        return 1
    fi
    
    # 检查项目存在
    response=$(curl -k -s -o /dev/null -w "%{http_code}" \
        -u "$HARBOR_USERNAME:$HARBOR_PASSWORD" \
        "https://$HARBOR_URL/api/v2.0/projects/sisys")
    
    if [ "$response" == "200" ]; then
        log_pass "Harbor 项目 sisys 存在"
    else
        log_fail "Harbor 项目 sisys 不存在"
    fi
}

# =============================================================================
# 验证 Runner
# =============================================================================

verify_runner() {
    echo
    log_info "验证 Gitea Runner..."
    
    if [ -n "$GITEA_TOKEN" ]; then
        # 检查 Runner 注册
        local response
        response=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "Authorization: token $GITEA_TOKEN" \
            "$GITEA_URL/api/v1/orgs/actions/runners")
        
        if [ "$response" == "200" ]; then
            log_pass "可访问 Runner API"
            
            # 检查 Runner 在线状态
            local runners
            runners=$(curl -s \
                -H "Authorization: token $GITEA_TOKEN" \
                "$GITEA_URL/api/v1/orgs/actions/runners" | jq -r '.runners[] | "\(.name): \(.status)"' 2>/dev/null || echo "")
            
            if [ -n "$runners" ]; then
                log_info "Runner 状态:"
                while IFS= read -r line; do
                    if echo "$line" | grep -q "online"; then
                        log_pass "  $line"
                    else
                        log_warn "  $line"
                    fi
                done <<< "$runners"
            else
                log_warn "未找到 Runner 信息"
            fi
        else
            log_warn "无法访问 Runner API (HTTP $response)"
        fi
    else
        log_warn "未设置 GITEA_TOKEN，跳过 Runner 检查"
    fi
}

# =============================================================================
# 网络连通性测试
# =============================================================================

verify_network() {
    echo
    log_info "网络连通性测试..."
    
    # 测试 GitHub 连接 (可选，离线环境应该失败)
    if curl -s -o /dev/null -w "%{http_code}" "https://github.com" | grep -q "200\|301"; then
        log_warn "可访问 GitHub (离线环境应该无法访问)"
    else
        log_pass "已断开 GitHub 连接 (符合离线环境要求)"
    fi
    
    # 测试 Google DNS
    if ping -c 1 8.8.8.8 &> /dev/null; then
        log_warn "可访问外网 (离线环境应该无法访问)"
    else
        log_pass "已断开外网连接 (符合离线环境要求)"
    fi
}

# =============================================================================
# 生成报告
# =============================================================================

generate_report() {
    echo
    echo "=============================================="
    echo "  验证报告"
    echo "=============================================="
    echo
    echo -e "  ${GREEN}通过${NC}: $PASS_COUNT"
    echo -e "  ${RED}失败${NC}: $FAIL_COUNT"
    echo -e "  ${YELLOW}警告${NC}: $WARN_COUNT"
    echo
    
    if [ "$FAIL_COUNT" -gt 0 ]; then
        echo -e "${RED}❌ 验证失败${NC} - 存在 $FAIL_COUNT 个关键问题"
        echo
        echo "建议操作:"
        echo "1. 运行 ./scripts/actions/download-actions.sh 下载缺失的 Actions"
        echo "2. 运行 ./scripts/image/import-pytorch.sh 导入 PyTorch 镜像"
        echo "3. 参考 docs/deployment/GITEA_ACTIONS_OFFLINE_DEPLOYMENT.md"
        exit 1
    elif [ "$WARN_COUNT" -gt 0 ]; then
        echo -e "${YELLOW}⚠️  验证通过但有警告${NC}"
        echo
        echo "建议操作:"
        echo "1. 检查警告项并酌情处理"
        echo "2. 运行测试工作流验证实际功能"
        exit 0
    else
        echo -e "${GREEN}✅ 验证完全通过${NC}"
        echo
        echo "下一步:"
        echo "1. 运行测试工作流：.gitea/workflows/test-offline.yml"
        echo "2. 提交代码触发完整 Pipeline"
        exit 0
    fi
}

# =============================================================================
# 主函数
# =============================================================================

main() {
    echo "=============================================="
    echo "  Gitea Actions 离线环境验证"
    echo "=============================================="
    echo "  Gitea URL: $GITEA_URL"
    echo "  Harbor URL: $HARBOR_URL"
    echo "  验证时间：$(date '+%Y-%m-%d %H:%M:%S')"
    echo "=============================================="
    
    verify_gitea_config
    verify_actions
    verify_docker_images
    verify_harbor
    verify_runner
    verify_network
    
    generate_report
}

main "$@"
