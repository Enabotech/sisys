#!/bin/bash
# =============================================================================
# Gitea Actions 镜像配置工具
# =============================================================================
# 功能：使用 Gitea 原生仓库镜像功能同步 GitHub Actions
# 参考：https://docs.gitea.com/zh-cn/usage/repo-mirror
# =============================================================================

set -euo pipefail

# 配置
GITEA_URL="${GITEA_URL:-https://gitea.sisys.local}"
GITEA_TOKEN="${GITEA_TOKEN:-}"
GITEA_ORG="${GITEA_ORG:-actions}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"  # GitHub 个人访问令牌 (需要 public_repo 权限)

# Actions 镜像清单
# 格式：github_repo -> gitea_repo
declare -A ACTIONS_MIRROR=(
    ["actions/checkout"]="checkout"
    ["actions/upload-artifact"]="upload-artifact"
    ["actions/download-artifact"]="download-artifact"
    ["actions/setup-python"]="setup-python"
    ["actions/cache"]="cache"
    ["docker/setup-buildx-action"]="setup-buildx-action"
    ["docker/login-action"]="login-action"
    ["docker/build-push-action"]="build-push-action"
    ["docker/metadata-action"]="metadata-action"
    ["docker/setup-qemu-action"]="setup-qemu-action"
    ["aquasecurity/trivy-action"]="trivy-action"
    ["Azure/k8s-set-context"]="k8s-set-context"
    ["Azure/k8s-deploy"]="k8s-deploy"
)

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%H:%M:%S') $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%H:%M:%S') $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%H:%M:%S') $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%H:%M:%S') $1"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $(date '+%H:%M:%S') $1"
}

# =============================================================================
# 前置检查
# =============================================================================

check_prerequisites() {
    log_step "检查前置条件..."

    # 检查 Gitea Token
    if [ -z "$GITEA_TOKEN" ]; then
        log_error "GITEA_TOKEN 未设置"
        echo
        echo "请在 Gitea 设置中创建访问令牌："
        echo "  设置 → 应用 → 生成新令牌 (勾选 repo 权限)"
        echo
        exit 1
    fi

    # 检查 GitHub Token
    if [ -z "$GITHUB_TOKEN" ]; then
        log_warning "GITHUB_TOKEN 未设置"
        echo
        echo "提示：设置 GITHUB_TOKEN 可自动创建镜像仓库"
        echo "创建方式：https://github.com/settings/tokens"
        echo "需要权限：public_repo"
        echo
    fi

    # 验证 Gitea 连接
    log_info "验证 Gitea 连接..."
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: token $GITEA_TOKEN" \
        "$GITEA_URL/api/v1/user")

    if [ "$response" != "200" ]; then
        log_error "Gitea 认证失败 (HTTP $response)"
        exit 1
    fi
    log_success "Gitea 连接成功"

    # 检查或创建 actions 组织
    log_info "检查组织：$GITEA_ORG"
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: token $GITEA_TOKEN" \
        "$GITEA_URL/api/v1/orgs/$GITEA_ORG")

    if [ "$response" == "404" ]; then
        log_info "  创建组织..."
        curl -s -X POST \
            -H "Authorization: token $GITEA_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"username\":\"$GITEA_ORG\",\"full_name\":\"GitHub Actions Mirror\"}" \
            "$GITEA_URL/api/v1/orgs" > /dev/null
        log_success "  组织创建成功"
    else
        log_success "  组织已存在"
    fi
}

# =============================================================================
# 核心功能
# =============================================================================

# 创建镜像仓库 (通过 Gitea API)
create_mirror_repo() {
    local github_repo="$1"
    local gitea_repo="$2"

    log_info "创建镜像仓库：$gitea_repo"

    # 检查仓库是否已存在
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: token $GITEA_TOKEN" \
        "$GITEA_URL/api/v1/repos/$GITEA_ORG/$gitea_repo")

    if [ "$response" == "200" ]; then
        log_warning "  仓库已存在，跳过创建"
        return 0
    fi

    # 通过 Gitea 迁移 API 创建镜像
    local github_url="https://github.com/$github_repo.git"

    log_info "  迁移源：$github_url"

    # 使用 Gitea 迁移 API
    local migrate_data
    migrate_data=$(cat << EOF
{
    "clone_addr": "$github_url",
    "service": "github",
    "auth_token": "$GITHUB_TOKEN",
    "repo_name": "$gitea_repo",
    "repo_owner": "$GITEA_ORG",
    "mirror": true,
    "private": false,
    "include_issues": false,
    "include_pull_requests": false,
    "include_releases": false
}
EOF
)

    local migrate_response
    migrate_response=$(curl -s -X POST \
        -H "Authorization: token $GITEA_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$migrate_data" \
        "$GITEA_URL/api/v1/repos/migrate")

    # 检查迁移状态
    if echo "$migrate_response" | jq -e '.id' > /dev/null; then
        local repo_name
        repo_name=$(echo "$migrate_response" | jq -r '.name')
        log_success "  镜像仓库创建成功：$repo_name"
        return 0
    else
        log_error "  迁移失败：$(echo "$migrate_response" | jq -r '.message')"
        return 1
    fi
}

# 配置推送镜像 (从 Gitea 到 GitHub)
configure_push_mirror() {
    local gitea_repo="$1"

    log_info "配置推送镜像：$gitea_repo"

    # 注意：Gitea API 不直接支持配置镜像，需要通过 Web UI
    # 这里提供说明
    log_warning "  推送镜像需要通过 Web UI 配置"
    log_info "  步骤:"
    log_info "    1. 访问 $GITEA_URL/$GITEA_ORG/$gitea_repo/settings"
    log_info "    2. 仓库 → 镜像设置"
    log_info "    3. 添加推送镜像：https://github.com/$GITEA_ORG/$gitea_repo.git"
}

# 手动同步镜像
sync_mirror() {
    local gitea_repo="$1"

    log_info "同步镜像：$gitea_repo"

    # 通过 Gitea API 触发同步
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST \
        -H "Authorization: token $GITEA_TOKEN" \
        "$GITEA_URL/api/v1/repos/$GITEA_ORG/$gitea_repo/mirror-sync")

    if [ "$response" == "204" ] || [ "$response" == "200" ]; then
        log_success "  同步成功"
    else
        log_error "  同步失败 (HTTP $response)"
        return 1
    fi
}

# 检查镜像状态
check_mirror_status() {
    local gitea_repo="$1"

    log_info "检查镜像状态：$gitea_repo"

    local repo_info
    repo_info=$(curl -s \
        -H "Authorization: token $GITEA_TOKEN" \
        "$GITEA_URL/api/v1/repos/$GITEA_ORG/$gitea_repo")

    local is_mirror
    is_mirror=$(echo "$repo_info" | jq -r '.mirror')

    local mirror_address
    mirror_address=$(echo "$repo_info" | jq -r '.mirror_url')

    if [ "$is_mirror" == "true" ]; then
        log_success "  是镜像仓库"
        log_info "  镜像源：$mirror_address"
    else
        log_warning "  不是镜像仓库"
    fi
}

# =============================================================================
# 命令
# =============================================================================

# 创建所有 Actions 镜像
cmd_create_all() {
    log_step "开始创建所有 Actions 镜像..."
    echo

    local success=0
    local failed=0
    local skipped=0

    for github_repo in "${!ACTIONS_MIRROR[@]}"; do
        local gitea_repo="${ACTIONS_MIRROR[$github_repo]}"

        echo "----------------------------------------"
        log_info "处理：$github_repo -> $gitea_repo"

        if [ -n "$GITHUB_TOKEN" ]; then
            if create_mirror_repo "$github_repo" "$gitea_repo"; then
                ((success++))
            else
                ((failed++))
            fi
        else
            log_warning "跳过自动创建 (未设置 GITHUB_TOKEN)"
            log_info "请手动创建镜像仓库:"
            log_info "  1. 访问 $GITEA_URL/repo/migrate"
            log_info "  2. 输入 URL: https://github.com/$github_repo"
            log_info "  3. 组织：$GITEA_ORG"
            log_info "  4. 仓库名：$gitea_repo"
            log_info "  5. ✅ 勾选 '此仓库将成为镜像'"
            ((skipped++))
        fi

        echo
    done

    echo "=============================================="
    log_info "创建完成统计:"
    log_success "  成功：$success"
    log_error "  失败：$failed"
    log_warning "  跳过：$skipped"
}

# 同步所有镜像
cmd_sync_all() {
    log_step "开始同步所有 Actions 镜像..."
    echo

    for github_repo in "${!ACTIONS_MIRROR[@]}"; do
        local gitea_repo="${ACTIONS_MIRROR[$github_repo]}"

        log_info "同步：$gitea_repo"
        sync_mirror "$gitea_repo" || true
        echo
    done

    log_success "同步完成"
}

# 检查所有镜像状态
cmd_status() {
    log_step "Actions 镜像状态:"
    echo

    printf "%-35s %-30s %-10s\n" "GITHUB" "GITEA" "STATUS"
    printf "%s\n" "$(printf '=%.0s' {1..80})"

    for github_repo in "${!ACTIONS_MIRROR[@]}"; do
        local gitea_repo="${ACTIONS_MIRROR[$github_repo]}"

        # 检查仓库是否存在
        local response
        response=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "Authorization: token $GITEA_TOKEN" \
            "$GITEA_URL/api/v1/repos/$GITEA_ORG/$gitea_repo")

        local status
        if [ "$response" == "200" ]; then
            status="✅ OK"
        else
            status="❌ MISSING"
        fi

        printf "%-35s %-30s %-10s\n" "$github_repo" "$gitea_repo" "$status"
    done
}

# 生成配置指南
cmd_guide() {
    cat << 'EOF'
# Gitea Actions 镜像配置指南

## 方式一：自动创建 (推荐)

```bash
# 设置 Token
export GITEA_TOKEN="your_gitea_token"
export GITHUB_TOKEN="your_github_token"

# 运行脚本
./scripts/actions/gitea-mirror-actions.sh create-all
```

## 方式二：手动创建

### 步骤 1: 创建 GitHub 访问令牌

1. 访问 https://github.com/settings/tokens
2. 生成新令牌 (classic)
3. 勾选 `public_repo` 权限
4. 复制令牌并保存

### 步骤 2: 在 Gitea 中创建镜像

对每个 Action 重复以下步骤：

1. 访问 Gitea → 创建... → 新迁移
2. 输入 GitHub URL:
   ```
   https://github.com/actions/checkout.git
   ```
3. 认证信息:
   - 用户名：你的 GitHub 用户名
   - 密码：步骤 1 创建的令牌
4. ✅ **重要**: 勾选 "此仓库将成为镜像"
5. 组织：actions
6. 仓库名：checkout
7. 点击 "迁移仓库"

### 步骤 3: 验证镜像

```bash
# 检查镜像状态
./scripts/actions/gitea-mirror-actions.sh status
```

## 方式三：使用 Git 命令手动克隆推送

```bash
# 克隆 GitHub 仓库
git clone https://github.com/actions/checkout.git /tmp/checkout

# 推送到 Gitea
cd /tmp/checkout
git remote add gitea https://gitea.sisys.local/actions/checkout.git
git push gitea main
```

## 配置 Gitea Actions

编辑 `app.ini`:

```ini
[actions]
ENABLED = true
DEFAULT_ACTIONS_URL = self
```

## 在工作流中使用

```yaml
jobs:
  build:
    steps:
      # 自动使用本地镜像
      - uses: actions/checkout@v4
```

## 定期同步

```bash
# 手动同步所有镜像
./scripts/actions/gitea-mirror-actions.sh sync-all

# 或设置定时任务 (每周执行)
0 2 * * 0 /path/to/gitea-mirror-actions.sh sync-all
```
EOF
}

# 显示帮助
cmd_help() {
    cat << EOF
Gitea Actions 镜像配置工具

用法：$0 <command>

命令:
  create-all    创建所有 Actions 镜像仓库
  sync-all      同步所有镜像
  status        显示所有镜像状态
  guide         显示配置指南
  help          显示此帮助信息

环境变量:
  GITEA_TOKEN   Gitea API Token (必需)
  GITHUB_TOKEN  GitHub Personal Access Token (可选，用于自动创建)
  GITEA_URL     Gitea 实例 URL (默认：https://gitea.sisys.local)
  GITEA_ORG     Gitea 组织名 (默认：actions)

示例:
  $0 status              # 查看镜像状态
  $0 create-all          # 创建所有镜像
  $0 sync-all            # 同步所有镜像
  $0 guide               # 查看配置指南

EOF
}

# =============================================================================
# 主函数
# =============================================================================

main() {
    if [ $# -eq 0 ]; then
        cmd_help
        exit 0
    fi

    check_prerequisites

    local command="$1"
    shift

    case "$command" in
        create-all)
            cmd_create_all
            ;;
        sync-all)
            cmd_sync_all
            ;;
        status)
            cmd_status
            ;;
        guide)
            cmd_guide
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            log_error "未知命令：$command"
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
