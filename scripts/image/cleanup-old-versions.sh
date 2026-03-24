#!/bin/bash
# 镜像清理脚本
# 功能：清理 Harbor 中的旧版本镜像，保留最近 N 个版本
# 保留策略：保留最近 5 个版本

set -e  # 遇到错误立即退出

# ===========================================================================
# 配置变量
# ===========================================================================
HARBOR_REGISTRY="${HARBOR_REGISTRY:-harbor.sisys.local}"
HARBOR_PROJECT="${HARBOR_PROJECT:-sisys}"
HARBOR_USERNAME="${HARBOR_USERNAME:-admin}"
HARBOR_PASSWORD="${HARBOR_PASSWORD:-}"
KEEP_COUNT="${KEEP_COUNT:-5}"  # 保留的镜像数量

# 要清理的镜像仓库
REPOSITORIES=("dependency" "app")

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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

# 获取镜像标签列表
get_image_tags() {
    local repo=$1
    local url="https://${HARBOR_REGISTRY}/api/v2.0/projects/${HARBOR_PROJECT}/repositories/${repo}/artifacts?with_tag=true&page=1&page_size=100"
    
    # 调用 Harbor API 获取标签
    local response=$(curl -k -s -u "${HARBOR_USERNAME}:${HARBOR_PASSWORD}" "$url")
    
    # 解析 JSON 获取标签名称
    echo "$response" | jq -r '.[].tags[].name' | grep -v 'latest\|weekly' | sort -r
}

# 删除镜像标签
delete_tag() {
    local repo=$1
    local tag=$2
    local url="https://${HARBOR_REGISTRY}/api/v2.0/projects/${HARBOR_PROJECT}/repositories/${repo}/tags/${tag}"
    
    log_info "删除：${repo}:${tag}"
    curl -k -s -X DELETE -u "${HARBOR_USERNAME}:${HARBOR_PASSWORD}" "$url"
}

# 清理单个仓库
cleanup_repository() {
    local repo=$1
    
    log_info "处理仓库：${repo}"
    
    # 获取所有标签
    local tags=($(get_image_tags "$repo"))
    local total=${#tags[@]}
    
    log_info "  总标签数：${total}"
    
    if [ $total -le $KEEP_COUNT ]; then
        log_info "  标签数 ≤ ${KEEP_COUNT}，无需清理"
        return
    fi
    
    # 计算需要删除的数量
    local delete_count=$((total - KEEP_COUNT))
    log_info "  需要删除：${delete_count} 个旧版本"
    
    # 删除旧版本 (保留最新的 KEEP_COUNT 个)
    for ((i=KEEP_COUNT; i<total; i++)); do
        local tag=${tags[$i]}
        log_warn "  删除旧版本：${tag}"
        delete_tag "$repo" "$tag" || log_error "删除失败：${tag}"
    done
    
    log_info "  清理完成"
}

# 显示磁盘使用情况
show_disk_usage() {
    log_info "Harbor 磁盘使用情况:"
    curl -k -s -u "${HARBOR_USERNAME}:${HARBOR_PASSWORD}" \
        "https://${HARBOR_REGISTRY}/api/v2.0/statistics" | \
        jq -r '.project_count, .repo_count, .artifact_count' | \
        xargs printf "  项目数：%s\n  仓库数：%s\n  镜像数：%s\n"
}

# ===========================================================================
# 主流程
# ===========================================================================
main() {
    log_info "=========================================="
    log_info "  Harbor 镜像清理脚本"
    log_info "=========================================="
    log_info "配置:"
    log_info "  - Harbor: ${HARBOR_REGISTRY}"
    log_info "  - 项目：${HARBOR_PROJECT}"
    log_info "  - 保留数量：${KEEP_COUNT}"
    log_info "  - 清理仓库：${REPOSITORIES[*]}"
    log_info ""
    
    # 预检查
    if ! command -v curl &> /dev/null; then
        log_error "curl 未安装"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_error "jq 未安装"
        exit 1
    fi
    
    # 显示清理前的磁盘使用情况
    show_disk_usage || true
    
    # 清理每个仓库
    for repo in "${REPOSITORIES[@]}"; do
        cleanup_repository "$repo"
        echo ""
    done
    
    # 显示清理后的磁盘使用情况
    log_info "清理完成!"
    show_disk_usage || true
    
    log_info ""
    log_info "=========================================="
    log_info "  清理完成!"
    log_info "=========================================="
}

# 显示帮助
show_help() {
    cat << EOF
Harbor 镜像清理脚本

用法：$0 [选项]

选项:
  -h, --help          显示帮助信息
  -r, --registry      Harbor 地址 (默认：harbor.sisys.local)
  -p, --project       项目名称 (默认：sisys)
  -u, --username      Harbor 用户名 (默认：admin)
  -P, --password      Harbor 密码 (默认：从环境变量读取)
  -k, --keep          保留的镜像数量 (默认：5)
  --repos             要清理的仓库列表 (默认：dependency app)

示例:
  $0                                    # 使用默认配置
  $0 -k 10                              # 保留 10 个版本
  $0 -r harbor.example.com -p myproject # 指定 Harbor 和项目
  HARBOR_PASSWORD=secret $0             # 通过环境变量传递密码
  $0 --repos dependency                 # 只清理 dependency 仓库

EOF
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -r|--registry)
            HARBOR_REGISTRY="$2"
            shift 2
            ;;
        -p|--project)
            HARBOR_PROJECT="$2"
            shift 2
            ;;
        -u|--username)
            HARBOR_USERNAME="$2"
            shift 2
            ;;
        -P|--password)
            HARBOR_PASSWORD="$2"
            shift 2
            ;;
        -k|--keep)
            KEEP_COUNT="$2"
            shift 2
            ;;
        --repos)
            REPOSITORIES=($2)
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
