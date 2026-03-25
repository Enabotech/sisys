#!/bin/bash
# =============================================================================
# Gitea Actions 离线下载脚本
# =============================================================================
# 功能：批量下载 GitHub Actions 到本地 Gitea 仓库
# 使用场景：构建完全离线的 CI/CD 环境
# =============================================================================

set -euo pipefail

# 配置项
GITEA_URL="${GITEA_URL:-https://gitea.sisys.local}"
GITEA_TOKEN="${GITEA_TOKEN:-}"
GITEA_ORG="${GITEA_ORG:-actions}"  # Gitea 中存储 Actions 的组织名
LOCAL_ROOT="${LOCAL_ROOT:-./gitea-actions-mirror}"  # 本地镜像根目录

# Actions 清单 (根据项目需求定制)
# 格式：action_name@version
declare -a ACTIONS_LIST=(
    # GitHub 官方 Actions
    "actions/checkout@v4"
    "actions/upload-artifact@v4"
    "actions/download-artifact@v4"
    "actions/setup-python@v5"
    "actions/cache@v4"
    "actions/checkout@v3"  # 兼容旧版本
    "actions/upload-artifact@v3"  # 兼容旧版本

    # Docker 相关 Actions
    "docker/setup-buildx-action@v3"
    "docker/login-action@v3"
    "docker/build-push-action@v5"
    "docker/metadata-action@v5"
    "docker/setup-qemu-action@v3"

    # 安全扫描 Actions
    "aquasecurity/trivy-action@master"
    "aquasecurity/trivy-action@0.14.0"  # 固定版本

    # Kubernetes 相关 Actions
    "azure/k8s-set-image@v2"
    "stefanprodan/k8s-gateway@v2"
)

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# 检查依赖
check_dependencies() {
    log_info "检查依赖工具..."
    
    local deps=("git" "curl" "jq" "tar")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            log_error "缺少依赖：$dep"
            exit 1
        fi
    done
    
    log_success "依赖检查通过"
}

# 验证 Gitea 配置
verify_gitea() {
    if [ -z "$GITEA_TOKEN" ]; then
        log_warning "GITEA_TOKEN 未设置，将只下载不上传到 Gitea"
        return
    fi
    
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
    
    # 检查或创建组织
    log_info "检查组织：$GITEA_ORG"
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: token $GITEA_TOKEN" \
        "$GITEA_URL/api/v1/orgs/$GITEA_ORG")
    
    if [ "$response" == "404" ]; then
        log_info "创建组织：$GITEA_ORG"
        curl -s -X POST \
            -H "Authorization: token $GITEA_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"username\":\"$GITEA_ORG\",\"full_name\":\"Actions Mirror\"}" \
            "$GITEA_URL/api/v1/orgs" > /dev/null
        log_success "组织创建成功"
    else
        log_success "组织已存在"
    fi
}

# 下载单个 Action
download_action() {
    local action="$1"
    local action_name="${action%@*}"
    local action_version="${action@#*}"
    
    log_info "下载 Action: $action"
    
    # 创建本地目录结构
    local local_dir="$LOCAL_ROOT/$action_name"
    mkdir -p "$local_dir"
    
    # 构建 GitHub API URL
    local github_url="https://api.github.com/repos/$action_name"
    
    # 获取 Action 的元数据
    log_info "  获取元数据..."
    local metadata
    metadata=$(curl -s "$github_url")
    
    if echo "$metadata" | jq -e '.message' | grep -q "Not Found"; then
        log_error "  Action 不存在：$action_name"
        return 1
    fi
    
    # 下载指定版本的代码
    local tarball_url
    if [ "$action_version" == "master" ] || [ "$action_version" == "main" ]; then
        tarball_url="$github_url/tarball/$action_version"
    else
        # 尝试获取 tag
        tarball_url="$github_url/tarball/refs/tags/$action_version"
    fi
    
    log_info "  下载代码包：$tarball_url"
    local temp_file="/tmp/${action_name//\//_}-${action_version}.tar.gz"
    
    curl -sL "$tarball_url" -o "$temp_file"
    
    if [ ! -f "$temp_file" ] || [ ! -s "$temp_file" ]; then
        log_error "  下载失败：$action"
        return 1
    fi
    
    # 解压到目标目录
    log_info "  解压到：$local_dir"
    tar -xzf "$temp_file" -C "$local_dir" --strip-components=1
    
    # 清理临时文件
    rm -f "$temp_file"
    
    # 创建 action.yml 的符号链接（如果存在）
    if [ -f "$local_dir/action.yml" ]; then
        log_success "  下载完成：$action (含 action.yml)"
    elif [ -f "$local_dir/action.yaml" ]; then
        log_success "  下载完成：$action (含 action.yaml)"
    else
        log_warning "  未找到 action.yml，可能需要手动验证"
    fi
    
    return 0
}

# 推送到 Gitea
push_to_gitea() {
    local action="$1"
    local action_name="${action%@*}"
    
    if [ -z "$GITEA_TOKEN" ]; then
        log_warning "跳过推送到 Gitea (未设置 GITEA_TOKEN)"
        return
    fi
    
    log_info "推送到 Gitea: $action_name"
    
    local repo_name="${action_name//\//_}"  # 替换 / 为 _ 避免命名冲突
    local local_dir="$LOCAL_ROOT/$action_name"
    
    # 检查或创建仓库
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: token $GITEA_TOKEN" \
        "$GITEA_URL/api/v1/repos/$GITEA_ORG/$repo_name")
    
    if [ "$response" == "404" ]; then
        log_info "  创建仓库：$GITEA_ORG/$repo_name"
        curl -s -X POST \
            -H "Authorization: token $GITEA_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"name\":\"$repo_name\",\"private\":false,\"auto_init\":false}" \
            "$GITEA_URL/api/v1/orgs/$GITEA_ORG/repos" > /dev/null
    fi
    
    # 推送代码到 Gitea
    log_info "  推送代码..."
    cd "$local_dir"
    
    git init -q
    git config user.email "actions-sync@sisys.local"
    git config user.name "Actions Sync Bot"
    git add .
    git commit -m "chore: mirror $action_name from GitHub" -q
    
    local gitea_repo_url="$GITEA_URL/$GITEA_ORG/$repo_name.git"
    git remote add origin "$gitea_repo_url" 2>/dev/null || true
    git push -f origin main -q 2>/dev/null || git push -f origin master -q 2>/dev/null || true
    
    cd - > /dev/null
    
    log_success "  推送完成：$repo_name"
}

# 生成 Actions 清单
generate_manifest() {
    log_info "生成 Actions 清单..."
    
    local manifest_file="$LOCAL_ROOT/manifest.json"
    local timestamp
    timestamp=$(date -Iseconds)
    
    cat > "$manifest_file" << EOF
{
    "generated_at": "$timestamp",
    "gitea_url": "$GITEA_URL",
    "gitea_org": "$GITEA_ORG",
    "actions": [
EOF
    
    local first=true
    for action in "${ACTIONS_LIST[@]}"; do
        local action_name="${action%@*}"
        local action_version="${action@#*}"
        local repo_name="${action_name//\//_}"
        
        if [ "$first" = true ]; then
            first=false
        else
            echo "," >> "$manifest_file"
        fi
        
        cat >> "$manifest_file" << EOF
        {
            "name": "$action_name",
            "version": "$action_version",
            "gitea_repo": "$GITEA_ORG/$repo_name",
            "gitea_url": "$GITEA_URL/$GITEA_ORG/$repo_name"
        }
EOF
    done
    
    cat >> "$manifest_file" << EOF

    ]
}
EOF
    
    log_success "清单已生成：$manifest_file"
}

# 生成使用指南
generate_usage_guide() {
    log_info "生成使用指南..."
    
    local guide_file="$LOCAL_ROOT/USAGE.md"
    
    cat > "$guide_file" << 'EOF'
# Gitea Actions 离线使用指南

## 配置 Gitea

在 Gitea 实例的 `app.ini` 中配置：

```ini
[actions]
ENABLED = true
DEFAULT_ACTIONS_URL = self
```

## 在工作流中使用本地 Actions

### 方式 1: 使用镜像仓库名

```yaml
jobs:
  build:
    steps:
      # 原始：uses: actions/checkout@v4
      - uses: actions/checkout@v4
      
      # 本地：uses: {GITEA_ORG}/{repo_name}@{version}
      - uses: actions/actions_checkout@v4
```

### 方式 2: 使用完整 URL（推荐）

```yaml
jobs:
  build:
    steps:
      - uses: https://gitea.sisys.local/actions/actions_checkout@v4
```

## Actions 清单

| 原始 Action | 本地仓库 | 本地 URL |
|------------|---------|---------|
| actions/checkout@v4 | actions/actions_checkout | https://gitea.sisys.local/actions/actions_checkout@v4 |
| actions/upload-artifact@v4 | actions/actions_upload-artifact | https://gitea.sisys.local/actions/actions_upload-artifact@v4 |

## 更新 Actions

重新运行下载脚本以更新所有 Actions：

```bash
./scripts/actions/download-actions.sh
```

## 故障排查

### Action 无法找到

1. 检查 Gitea 中是否存在对应仓库
2. 检查 `DEFAULT_ACTIONS_URL` 配置
3. 使用完整 URL 代替短格式

### Action 执行失败

1. 检查 action.yml 是否存在
2. 验证 Action 的依赖是否也已本地化
3. 查看 Gitea Runner 日志
EOF
    
    log_success "使用指南已生成：$guide_file"
}

# 主函数
main() {
    echo "=============================================="
    echo "  Gitea Actions 离线下载工具"
    echo "=============================================="
    echo
    
    check_dependencies
    verify_gitea
    
    echo
    log_info "开始下载 Actions..."
    echo
    
    local success_count=0
    local fail_count=0
    
    for action in "${ACTIONS_LIST[@]}"; do
        if download_action "$action"; then
            push_to_gitea "$action"
            ((success_count++))
        else
            ((fail_count++))
        fi
        echo
    done
    
    echo
    echo "=============================================="
    echo "  下载完成"
    echo "=============================================="
    echo "  成功：$success_count"
    echo "  失败：$fail_count"
    echo
    
    generate_manifest
    generate_usage_guide
    
    if [ "$fail_count" -gt 0 ]; then
        log_warning "部分 Actions 下载失败，请检查日志"
        exit 1
    fi
    
    log_success "所有 Actions 下载完成！"
}

# 执行
main "$@"
