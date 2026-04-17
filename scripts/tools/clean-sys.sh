#!/bin/bash
#===============================================================================
# 系统存储垃圾清理脚本 v2.6
#
# 整合 gitea-runner-dind, gitea-org-runner, Harbor, Trivy 等组件的
# 全面存储垃圾清理解决方案
#
# 用法:
#   ./clean-sys.sh [选项]
#
# 选项:
#   -a, --all         执行全量清理 (默认)
#   -d, --docker     仅清理 Docker 相关
#   -k, --k3s        仅清理 K3s 容器运行时
#   -h, --harbor     仅清理 Harbor/Trivy
#   -s, --system     仅清理系统日志/缓存
#   -r, --report     仅显示存储状态报告
#   -n, --dry-run    试运行 (不实际清理)
#   -y, --yes        自动确认所有操作
#
# 示例:
#   ./clean-sys.sh              # 全量清理
#   ./clean-sys.sh -r           # 仅显示存储报告
#   ./clean-sys.sh -d --dry-run # 试运行 Docker 清理
#
#===============================================================================

VERSION="2.6"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# 配置
DIND_POD="gitea-runner-dind-0"
DIND_NS="gitea-advacts"
ORG_RUNNERS=("gitea-org-runner-0" "gitea-org-runner-1" "gitea-org-runner-2" "gitea-org-runner-3")
ORG_NS="gitea-actions"
HARBOR_NS="harbor"
TRIVY_POD="harbor-trivy-0"

# 选项默认值
MODE="all"
DRY_RUN=false
CONFIRMED=false

# 全局统计
STATS_CONTAINERS=0

# 脚本锁文件路径
LOCK_FILE="/tmp/clean-sys.lock"
LOCK_FD=200

#===============================================================================
# 辅助函数
#===============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_header() {
    echo ""
    echo -e "${BOLD}${CYAN}========================================${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${CYAN}========================================${NC}"
}

log_subheader() {
    echo ""
    echo -e "${BOLD}--- $1 ---${NC}"
}

# 确认提示
confirm_action() {
    if [ "$CONFIRMED" = true ]; then
        return 0
    fi
    local prompt="${1:-"确认执行?"}"
    local confirmed
    read -p "$prompt (y/N): " confirmed
    if [[ "$confirmed" =~ ^[Yy]$ ]]; then
        return 0
    fi
    return 1
}

# 检查 sudo 是否可用
check_sudo() {
    if ! sudo -n true 2>/dev/null; then
        log_warn "需要 sudo 权限，部分操作可能需要密码"
        return 1
    fi
    return 0
}

# 验证 kubectl 上下文
verify_kubectl_context() {
    local context
    context=$(kubectl config current-context 2>/dev/null)
    if [ -z "$context" ]; then
        log_error "无法获取 kubectl context，请检查配置"
        return 1
    fi
    log_info "kubectl context: $context"
    return 0
}

# 解析 kubectl 输出
kubectl_exec() {
    local pod=$1
    local ns=$2
    local container=$3
    shift 3
    if ! kubectl get pod "$pod" -n "$ns" &>/dev/null; then
        echo "Pod $pod not found or not ready"
        return 1
    fi
    if [ -n "$container" ]; then
        kubectl exec -n "$ns" "$pod" -c "$container" -- "$@" 2>&1
    else
        kubectl exec -n "$ns" "$pod" -- "$@" 2>&1
    fi
}

# 获取 Harbor Registry Pod
get_registry_pod() {
    kubectl get pod -n "$HARBOR_NS" -l component=registry -o jsonpath='{.items[0].metadata.name}' 2>/dev/null
}

# 获取 Trivy 缓存路径
get_trivy_cache_path() {
    local pod=$1
    local ns=$2
    # 尝试从环境变量获取缓存路径
    local cache_path
    # SCANNER_TRIVY_CACHE_DIR 是 Harbor Trivy 的标准环境变量
    cache_path=$(kubectl exec -n "$ns" "$pod" -- printenv SCANNER_TRIVY_CACHE_DIR 2>/dev/null || echo "")
    if [ -z "$cache_path" ]; then
        # 回退到默认路径
        cache_path="/home/scanner/.cache/trivy"
    else
        # 追加 trivy 子目录（Trivy 实际缓存位置）
        cache_path="$cache_path/trivy"
    fi
    echo "$cache_path"
}

# 统计助手 - 安全的 wc -l
safe_wc() {
    local text="$1"
    if [ -z "$text" ]; then
        echo 0
    else
        echo -n "$text" | wc -l
    fi
}

# 安全的 du 格式化输出
# 用法: safe_du "du -sh /path"
# 返回: "size" 或 "N/A"
safe_du() {
    local output
    output=$("$@" 2>&1)
    if [ $? -ne 0 ]; then
        echo "N/A"
        return 1
    fi
    # du -sh 输出格式: "size\tpath"
    echo "$output" | awk '{print $1}'
}

# 安全的命令执行 (支持 dry-run)
run_cmd() {
    if [ "$DRY_RUN" = true ]; then
        log_warn "[DRY-RUN] Would execute: $*"
        return 0
    fi
    "$@"
}

# 获取 Docker 存储状态
docker_df() {
    local prefix="$1"
    local output
    local ret
    output=$($prefix docker system df 2>&1)
    ret=$?
    if [ $ret -ne 0 ]; then
        echo "Docker not available"
        return 1
    fi
    echo "$output"
    return 0
}

# 显示存储状态报告
show_report() {
    log_header "存储状态报告"

    #--------- 节点磁盘总体情况 ---------
    log_subheader "节点磁盘使用情况"
    df -h | grep -E "/dev/sd|native-hdd" | head -10

    #--------- DIND Runner Docker 存储 ---------
    log_subheader "DIND Runner Docker 存储 (${DIND_POD})"
    if kubectl get pod "$DIND_POD" -n "$DIND_NS" &>/dev/null; then
        local prefix="kubectl exec $DIND_POD -n $DIND_NS -c docker-dind --"
        docker_df "$prefix"
        echo ""
        echo "overlay2: $($prefix du -sh /var/lib/docker/overlay2 2>&1 | cut -f1)"
        echo "BuildKit: $($prefix du -sh /var/lib/docker/buildkit 2>&1 | cut -f1)"
    else
        echo "DIND Runner 未运行"
    fi

    #--------- org-runners Docker 存储 ---------
    log_subheader "Org Runners Docker 存储"
    for runner in "${ORG_RUNNERS[@]}"; do
        if kubectl get pod "$runner" -n "$ORG_NS" &>/dev/null; then
            echo "[$runner]"
            local prefix="kubectl exec $runner -n $ORG_NS -c runner --"
            docker_df "$prefix" 2>/dev/null || echo "  Docker not available"
        fi
    done

    #--------- Harbor PVC 存储 ---------
    log_subheader "Harbor PVC 存储"
    kubectl get pvc -n "$HARBOR_NS" 2>/dev/null | grep -v "^NAME" | awk '{print $1, $4, $5}'

    #--------- Harbor Trivy 缓存 ---------
    log_subheader "Harbor Trivy 缓存"
    if kubectl get pod "$TRIVY_POD" -n "$HARBOR_NS" &>/dev/null; then
        local trivy_path
        trivy_path=$(get_trivy_cache_path "$TRIVY_POD" "$HARBOR_NS")
        if [ -n "$trivy_path" ]; then
            local trivy_size
            trivy_size=$(safe_du kubectl_exec "$TRIVY_POD" "$HARBOR_NS" "" du -sh "$trivy_path")
            echo "Trivy 缓存 ($trivy_path): $trivy_size"
        else
            echo "Trivy 缓存: 无法确定路径"
        fi
    fi

    #--------- Harbor Registry 存储 ---------
    log_subheader "Harbor Registry 存储"
    local registry_pod
    registry_pod=$(get_registry_pod)
    if [ -n "$registry_pod" ]; then
        echo "Registry 存储: $(safe_du kubectl_exec "$registry_pod" "$HARBOR_NS" "registry" du -sh /storage)"
    fi
}

#===============================================================================
# DIND Runner 清理
#===============================================================================

clean_dind_runner() {
    log_header "清理 DIND Runner (${DIND_POD})"

    if ! kubectl get pod "$DIND_POD" -n "$DIND_NS" &>/dev/null; then
        log_warn "DIND Runner 未运行, 跳过"
        return
    fi

    local prefix="kubectl exec $DIND_POD -n $DIND_NS -c docker-dind --"

    # 清理前状态
    log_info "清理前存储状态:"
    docker_df "$prefix"
    echo ""

    #--------- 0. 停止并删除所有容器 ---------
    log_subheader "0. 停止并删除所有容器"
    local containers
    containers=$($prefix docker ps -aq 2>/dev/null || echo "")
    local container_count
    container_count=$(safe_wc "$containers")

    if [ -n "$containers" ]; then
        if [ "$DRY_RUN" = true ]; then
            log_warn "[DRY-RUN] Would stop and remove $container_count containers"
        else
            echo "$containers" | xargs -r $prefix docker stop 2>/dev/null || true
            log_success "容器已停止"
            containers=$($prefix docker ps -aq 2>/dev/null || echo "")
            if [ -n "$containers" ]; then
                echo "$containers" | xargs -r $prefix docker rm -f 2>/dev/null || true
            fi
            STATS_CONTAINERS=$((STATS_CONTAINERS + container_count))
        fi
    else
        log_info "无运行中的容器"
    fi

    #--------- 1. 清理 BuildKit 缓存 ---------
    log_subheader "1. 清理 BuildKit 缓存 (保留 5GB)"
    run_cmd $prefix docker builder prune -af --reserved-space=5g 2>/dev/null || true
    log_success "BuildKit 缓存已清理"

    #--------- 2. 清理镜像 ---------
    log_subheader "2. 清理镜像"
    run_cmd $prefix docker image prune -af 2>/dev/null || true
    log_success "镜像已清理"

    #--------- 3. 清理 overlay2 ---------
    log_subheader "3. 清理 overlay2 未引用层"
    run_cmd $prefix docker system prune -f 2>/dev/null || true
    log_success "overlay2 层已清理"

    #--------- 4. 清理未使用 volumes ---------
    log_subheader "4. 清理未使用 volumes"
    run_cmd $prefix docker volume prune -af 2>/dev/null || true
    log_success "未使用 volumes 已清理"

    #--------- 5. 清理容器日志 ---------
    log_subheader "5. 清理容器日志"
    run_cmd $prefix sh -c "find /var/lib/docker/containers -name '*-json.log' -type f -exec truncate -s 0 {} \; 2>/dev/null" || true
    log_success "容器日志已清理"

    # 清理后状态
    log_info "清理后存储状态:"
    docker_df "$prefix"
    log_success "DIND Runner 清理完成"
}

#===============================================================================
# Org Runners 清理
#===============================================================================

clean_org_runners() {
    log_header "清理 Org Runners"

    for runner in "${ORG_RUNNERS[@]}"; do
        log_subheader "清理 $runner"

        if ! kubectl get pod "$runner" -n "$ORG_NS" &>/dev/null; then
            log_warn "$runner 未运行, 跳过"
            continue
        fi

        local prefix="kubectl exec $runner -n $ORG_NS -c runner --"

        if ! $prefix docker info &>/dev/null; then
            log_info "$runner 无 Docker (非 DIND 模式), 跳过"
            continue
        fi

        #--------- 0. 停止并删除所有容器 ---------
        log_info "停止并删除所有容器..."
        local containers
        containers=$($prefix docker ps -aq 2>/dev/null || echo "")
        local container_count
        container_count=$(safe_wc "$containers")

        if [ -n "$containers" ]; then
            if [ "$DRY_RUN" = true ]; then
                log_warn "[DRY-RUN] Would stop/remove $container_count containers"
            else
                echo "$containers" | xargs -r $prefix docker stop 2>/dev/null || true
                containers=$($prefix docker ps -aq 2>/dev/null || echo "")
                [ -n "$containers" ] && echo "$containers" | xargs -r $prefix docker rm -f 2>/dev/null || true
                STATS_CONTAINERS=$((STATS_CONTAINERS + container_count))
            fi
        fi

        #--------- 1. 清理 BuildKit ---------
        log_info "清理 BuildKit..."
        run_cmd $prefix docker builder prune -af --reserved-space=2g 2>/dev/null || true

        #--------- 2. 清理镜像 ---------
        log_info "清理镜像..."
        run_cmd $prefix docker image prune -af 2>/dev/null || true

        #--------- 3. 清理 volumes ---------
        log_info "清理 volumes..."
        run_cmd $prefix docker volume prune -af 2>/dev/null || true

        #--------- 4. 清理日志 ---------
        log_info "清理日志..."
        run_cmd $prefix sh -c "find /var/lib/docker/containers -name '*-json.log' -type f -exec truncate -s 0 {} \; 2>/dev/null" || true

        log_success "$runner 清理完成"
    done
}

#===============================================================================
# K3s 容器运行时清理
#===============================================================================

clean_k3s() {
    log_header "清理 K3s 容器运行时"

    if ! check_sudo; then
        log_error "sudo 权限不可用，K3s 清理需要 sudo 权限"
        return 1
    fi

    if ! confirm_action "确认清理 K3s 未使用镜像?"; then
        log_info "已取消"
        return
    fi

    #--------- 显示镜像状态 (sudo 检查后执行) ---------
    log_subheader "K3s 镜像状态概览"

    echo "--- harbor.sisys.local/sisys/app ---"
    sudo k3s crictl images 2>/dev/null | grep "harbor.sisys.local/sisys/app" | awk '{print $1":"$2, "(" $4 ")"}' | sort -u || echo "  无"
    echo ""
    echo "--- harbor.sisys.local/sisys/tools (系统工具) ---"
    sudo k3s crictl images 2>/dev/null | grep "harbor.sisys.local/sisys/tools" | awk '{print $1":"$2}' | sort -u | head -10 || echo "  无"
    echo ""
    echo "--- docker.io/goharbor/* (Harbor 组件) ---"
    sudo k3s crictl images 2>/dev/null | grep "docker.io/goharbor" | awk '{print $1":"$2}' | sort -u || echo "  无"

    #--------- crictl prune ---------
    log_subheader "执行 crictl rmi --prune"
    log_warn "注意: 仅删除完全未使用的镜像，正在使用的镜像不会被删除"
    run_cmd sudo k3s crictl rmi --prune 2>/dev/null || true
    log_success "K3s 未使用镜像已清理"

    #--------- 清理后状态 ---------
    log_subheader "清理后 harbor.sisys.local/sisys/app 状态"
    sudo k3s crictl images 2>/dev/null | grep "harbor.sisys.local/sisys/app" | awk '{print $1":"$2, "(" $4 ")"}' | sort -u || echo "  无 (已清理)"

    log_success "K3s 清理完成"
}

#===============================================================================
# Harbor / Trivy 清理
#===============================================================================

check_harbor_gc_lock() {
    # 检查 Harbor Registry 是否有正在运行的 GC 或推送操作
    # 通过检查进程存在性和 API 可用性来判断
    local registry_pod=$1

    # 检查 GC 锁文件是否存在 (Harbor Registry GC 期间会创建锁文件)
    if kubectl exec -n "$HARBOR_NS" "$registry_pod" -c registry -- \
        sh -c "test -f /storage/.registry.gc.lock" 2>/dev/null; then
        log_error "Harbor Registry 正在执行 GC 或镜像推送，请稍后重试"
        return 1
    fi

    # 检查 Registry 进程是否运行
    if ! kubectl exec -n "$HARBOR_NS" "$registry_pod" -c registry -- \
        pgrep -x registry >/dev/null 2>&1; then
        log_error "Registry 进程未运行，GC 无法执行"
        return 1
    fi

    return 0
}

clean_harbor() {
    log_header "清理 Harbor / Trivy"

    if ! confirm_action "确认清理 Harbor/Trivy?"; then
        log_info "已取消"
        return
    fi

    local registry_pod
    registry_pod=$(get_registry_pod)

    #--------- Trivy 缓存清理 ---------
    log_subheader "Trivy 缓存清理"

    if kubectl get pod "$TRIVY_POD" -n "$HARBOR_NS" &>/dev/null; then
        local trivy_path
        trivy_path=$(get_trivy_cache_path "$TRIVY_POD" "$HARBOR_NS")
        local before_size
        before_size=$(safe_du kubectl_exec "$TRIVY_POD" "$HARBOR_NS" "" du -sh "$trivy_path")
        log_info "Trivy 缓存清理前: $before_size"

        run_cmd kubectl_exec "$TRIVY_POD" "$HARBOR_NS" "" trivy clean --all 2>/dev/null || true

        local after_size
        after_size=$(safe_du kubectl_exec "$TRIVY_POD" "$HARBOR_NS" "" du -sh "$trivy_path")
        log_info "Trivy 缓存清理后: $after_size"
        log_success "Trivy 缓存已清理"
    else
        log_warn "Trivy Pod 未运行"
    fi

    #--------- Harbor Registry 垃圾回收 ---------
    if [ -n "$registry_pod" ]; then
        log_subheader "Harbor Registry 垃圾回收"

        if ! check_harbor_gc_lock "$registry_pod"; then
            log_error "Harbor 正在执行其他操作，请稍后重试"
            return 1
        fi

        log_warn "⚠️ 重要: GC 期间请勿推送镜像，可能导致数据不一致"

        local registry_before
        registry_before=$(safe_du kubectl_exec "$registry_pod" "$HARBOR_NS" "registry" du -sh /storage)
        log_info "Registry 清理前: $registry_before"

        # 使用长参数避免歧义
        run_cmd kubectl_exec "$registry_pod" "$HARBOR_NS" "registry" \
            /bin/registry garbage-collect /etc/registry/config.yml --compact 2>/dev/null || true

        local registry_after
        registry_after=$(safe_du kubectl_exec "$registry_pod" "$HARBOR_NS" "registry" du -sh /storage)
        log_info "Registry 清理后: $registry_after"
        log_success "Registry 垃圾回收完成"
    else
        log_warn "Registry Pod 未运行"
    fi

    #--------- 清理 Registry 上的 Trivy 缓存 ---------
    if [ -n "$registry_pod" ]; then
        log_subheader "清理 Registry 上的 Trivy 扫描缓存"
        run_cmd kubectl_exec "$registry_pod" "$HARBOR_NS" "registry" \
            sh -c "find /storage -name '.trivy' -type d -exec rm -rf {} + 2>/dev/null" || true
        log_success "Registry Trivy 缓存已清理"
    fi
}

#===============================================================================
# 本地 Docker 清理
#===============================================================================

clean_local_docker() {
    log_header "清理本地 Docker"

    if ! command -v docker &>/dev/null; then
        log_info "本地无 Docker, 跳过"
        return
    fi

    if ! confirm_action "确认清理本地 Docker?"; then
        log_info "已取消"
        return
    fi

    log_info "本地 Docker 可用, 执行清理..."

    # #--------- 0. 停止并删除所有容器 ---------
    # log_subheader "停止并删除所有容器"
    # local containers
    # containers=$(docker ps -aq 2>/dev/null || echo "")
    # local container_count
    # container_count=$(safe_wc "$containers")

    # if [ -n "$containers" ]; then
    #     if [ "$DRY_RUN" = true ]; then
    #         log_warn "[DRY-RUN] Would stop/remove $container_count containers"
    #     else
    #         echo "$containers" | xargs -r docker stop 2>/dev/null || true
    #         containers=$(docker ps -aq 2>/dev/null || echo "")
    #         [ -n "$containers" ] && echo "$containers" | xargs -r docker rm -f 2>/dev/null || true
    #         STATS_CONTAINERS=$((STATS_CONTAINERS + container_count))
    #     fi
    # else
    #     log_info "无运行中的容器"
    # fi

    #--------- 1. 清理 BuildKit ---------
    log_subheader "BuildKit 缓存"
    run_cmd docker builder prune -af 2>/dev/null || true

    #--------- 2. 清理镜像 ---------
    log_subheader "镜像 prune"
    run_cmd docker image prune -af 2>/dev/null || true

    #--------- 3. 清理 overlay2 ---------
    log_subheader "系统 prune (overlay2)"
    run_cmd docker system prune -af 2>/dev/null || true

    #--------- 4. 清理未使用 volumes ---------
    log_subheader "Volumes prune"
    run_cmd docker volume prune -af 2>/dev/null || true

    log_success "本地 Docker 清理完成"
}

#===============================================================================
# 系统清理
#===============================================================================

clean_system() {
    log_header "清理系统日志和缓存"

    if ! check_sudo; then
        log_error "sudo 权限不可用，系统清理需要 sudo 权限"
        return 1
    fi

    if ! confirm_action "确认清理系统日志/缓存?"; then
        log_info "已取消"
        return
    fi

    #--------- apt 缓存 ---------
    log_subheader "APT 缓存清理"
    run_cmd sudo apt clean 2>/dev/null || true
    run_cmd sudo apt autoclean 2>/dev/null || true
    run_cmd sudo apt autoremove -y 2>/dev/null || true
    log_success "APT 缓存已清理"

    #--------- 系统日志 ---------
    log_subheader "系统日志清理 (保留最近 8 小时)"
    run_cmd sudo journalctl --vacuum-time=8h 2>/dev/null || true
    # 安全删除: 只删除 .log 文件，且至少 7 天未修改
    run_cmd sudo find /var/log -type f -name "*.log" -mtime +7 -delete 2>/dev/null || true
    log_success "系统日志已清理"

    #--------- 临时文件 ---------
    log_subheader "临时文件清理 (仅删除 systemd 临时文件和 tmp.*.tmp)"
    # 清理 systemd 生成的临时目录 (占用大量空间)
    run_cmd sudo find /tmp -maxdepth 1 -type d -name "systemd-*" -mtime +1 -exec rm -rf {} \; 2>/dev/null || true
    run_cmd sudo find /var/tmp -maxdepth 1 -type d -name "systemd-*" -mtime +1 -exec rm -rf {} \; 2>/dev/null || true
    log_success "systemd 临时文件已清理"

    #--------- WSL 回收站 ---------
    log_subheader "回收站清理"
    if [ -d "$HOME/.local/share/Trash" ]; then
        run_cmd rm -rf "$HOME/.local/share/Trash/"* 2>/dev/null || true
    fi
    log_success "回收站已清理"

    #--------- pip 缓存 ---------
    if command -v pip3 &>/dev/null; then
        log_subheader "pip 缓存清理"
        run_cmd pip3 cache purge 2>/dev/null || true
        log_success "pip 缓存已清理"
    fi

    #--------- npm 缓存 ---------
    if command -v npm &>/dev/null; then
        log_subheader "npm 缓存清理"
        run_cmd npm cache clean --force 2>/dev/null || true
        log_success "npm 缓存已清理"
    fi

    log_success "系统清理完成"
}

#===============================================================================
# 清理统计
#===============================================================================

show_stats() {
    log_header "清理统计"
    echo "停止的容器: $STATS_CONTAINERS"
}

#===============================================================================
# 主函数
#===============================================================================

show_usage() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -a, --all         执行全量清理 (默认)"
    echo "  -d, --docker      仅清理 Docker 相关"
    echo "  -k, --k3s         仅清理 K3s 容器运行时"
    echo "  -h, --harbor      仅清理 Harbor/Trivy"
    echo "  -s, --system      仅清理系统日志/缓存"
    echo "  -r, --report      仅显示存储状态报告"
    echo "  -n, --dry-run     试运行 (不实际清理)"
    echo "  -y, --yes         自动确认所有操作"
    echo "  --version         显示版本信息"
    echo "  --help            显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0              # 全量清理"
    echo "  $0 -r           # 仅显示存储报告"
    echo "  $0 -d -y        # 清理 Docker (无需确认)"
    echo "  $0 -d --dry-run # 试运行 Docker 清理"
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -a|--all)
            MODE="all"
            shift
            ;;
        -d|--docker)
            MODE="docker"
            shift
            ;;
        -k|--k3s)
            MODE="k3s"
            shift
            ;;
        -h|--harbor)
            MODE="harbor"
            shift
            ;;
        -s|--system)
            MODE="system"
            shift
            ;;
        -r|--report)
            MODE="report"
            shift
            ;;
        -n|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -y|--yes)
            CONFIRMED=true
            shift
            ;;
        --version)
            echo "clean-sys.sh version $VERSION"
            exit 0
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            echo "未知选项: $1"
            show_usage
            exit 1
            ;;
    esac
done

# 主流程
main() {
    local start_time=$(date +%s)

    echo ""
    log_header "系统存储垃圾清理 v${VERSION}"

    # 检查脚本是否已运行 (使用 flock 原子锁)
    exec {LOCK_FD}>"$LOCK_FILE"
    if ! flock -n "$LOCK_FD"; then
        log_error "检测到清理脚本正在运行 (锁文件: $LOCK_FILE)"
        log_error "如果确认没有其他实例在运行，请删除锁文件后重试"
        exit 1
    fi
    # 设置退出时释放锁和关闭文件描述符
    trap "flock -u $LOCK_FD; exec $LOCK_FD>&-; rm -f '$LOCK_FILE' 2>/dev/null" EXIT

    # 验证 kubectl 上下文
    if [[ "$MODE" != "report" ]]; then
        if ! verify_kubectl_context; then
            log_error "kubectl context 验证失败，请检查集群配置"
            exit 1
        fi
    fi

    echo "模式: $MODE"
    [ "$DRY_RUN" = true ] && log_warn "DRY-RUN 模式: 仅显示将要执行的操作"
    echo ""

    if [ "$DRY_RUN" = true ]; then
        show_report
        log_warn "DRY-RUN: 实际清理未执行"
        return
    fi

    case $MODE in
        report)
            show_report
            ;;
        all)
            show_report
            echo ""
            if confirm_action "是否执行全量清理?"; then
                clean_dind_runner
                clean_org_runners
                clean_k3s
                clean_harbor
                clean_local_docker
                clean_system
            else
                log_info "已取消"
            fi
            ;;
        docker)
            show_report
            echo ""
            if confirm_action "是否清理 Docker 相关?"; then
                clean_dind_runner
                clean_org_runners
                clean_local_docker
            else
                log_info "已取消"
            fi
            ;;
        k3s)
            clean_k3s
            ;;
        harbor)
            show_report
            echo ""
            if confirm_action "是否清理 Harbor/Trivy?"; then
                clean_harbor
            else
                log_info "已取消"
            fi
            ;;
        system)
            clean_system
            ;;
    esac

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    echo ""
    log_header "清理完成!"
    echo "耗时: ${duration} 秒"

    show_stats
    echo ""

    if [[ "$MODE" != "report" ]]; then
        show_report
    fi
}

# 执行
main
