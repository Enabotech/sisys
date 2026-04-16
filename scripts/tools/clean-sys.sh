#!/bin/bash
#===============================================================================
# 系统存储垃圾清理脚本
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
#   -v, --verbose    显示详细输出
#   -n, --dry-run    试运行 (不实际清理)
#
# 示例:
#   ./clean-sys.sh              # 全量清理
#   ./clean-sys.sh -r           # 仅显示存储报告
#   ./clean-sys.sh -d --dry-run # 试运行 Docker 清理
#
#===============================================================================

set -e

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
REGISTRY_POD="harbor-registry-58d6847f5f-q6hl8"

# 选项默认值
MODE="all"
VERBOSE=false
DRY_RUN=false

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

# 解析 kubectl 输出 (处理 Pod 未找到等情况)
kubectl_exec() {
    local pod=$1
    local ns=$2
    local container=$3
    shift 3
    if kubectl get pod "$pod" -n "$ns" &>/dev/null; then
        kubectl exec -n "$ns" "$pod" -c "$container" -- "$@" 2>/dev/null
    else
        echo "Pod $pod not found or not ready"
        return 1
    fi
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
        local dind_info
        dind_info=$(kubectl_exec "$DIND_POD" "$DIND_NS" "docker-dind" docker system df 2>/dev/null || echo "Docker not available")
        echo "$dind_info"

        # overlay2 目录大小
        local overlay_size
        overlay_size=$(kubectl_exec "$DIND_POD" "$DIND_NS" "docker-dind" du -sh /var/lib/docker/overlay2 2>/dev/null || echo "N/A")
        echo "overlay2 总大小: $overlay_size"

        # BuildKit 缓存
        local buildkit_size
        buildkit_size=$(kubectl_exec "$DIND_POD" "$DIND_NS" "docker-dind" du -sh /var/lib/docker/buildkit 2>/dev/null || echo "N/A")
        echo "BuildKit 缓存: $buildkit_size"
    else
        echo "DIND Runner 未运行"
    fi

    #--------- org-runners Docker 存储 ---------
    log_subheader "Org Runners Docker 存储"
    for runner in "${ORG_RUNNERS[@]}"; do
        if kubectl get pod "$runner" -n "$ORG_NS" &>/dev/null; then
            echo "[$runner]"
            kubectl_exec "$runner" "$ORG_NS" "runner" docker system df 2>/dev/null | head -5 || echo "  Docker not available"
        fi
    done

    #--------- Harbor PVC 存储 ---------
    log_subheader "Harbor PVC 存储"
    kubectl get pvc -n "$HARBOR_NS" 2>/dev/null | grep -v "^NAME" | awk '{print $1, $4, $5}'

    #--------- Harbor Trivy 缓存 ---------
    log_subheader "Harbor Trivy 缓存"
    if kubectl get pod "$TRIVY_POD" -n "$HARBOR_NS" &>/dev/null; then
        local trivy_cache
        trivy_cache=$(kubectl_exec "$TRIVY_POD" "$HARBOR_NS" "" du -sh /home/scanner/.cache 2>/dev/null || echo "N/A")
        echo "Trivy 缓存: $trivy_cache"
    fi

    #--------- Harbor Registry 存储 ---------
    log_subheader "Harbor Registry 存储"
    if kubectl get pod "$REGISTRY_POD" -n "$HARBOR_NS" &>/dev/null; then
        local registry_size
        registry_size=$(kubectl_exec "$REGISTRY_POD" "$HARBOR_NS" "registry" du -sh /storage 2>/dev/null || echo "N/A")
        echo "Registry 存储: $registry_size"
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
    $prefix docker system df 2>/dev/null | head -6

    #--------- 1. 清理 BuildKit 缓存 (保留 5GB) ---------
    log_subheader "1. 清理 BuildKit 缓存 (保留 5GB)"
    $prefix docker builder prune -af --reserved-space=5G 2>/dev/null || true
    log_success "BuildKit 缓存已清理"

    #--------- 2. 清理临时容器 ---------
    log_subheader "2. 清理临时容器"
    $prefix docker container prune -f 2>/dev/null || true
    log_success "临时容器已清理"

    #--------- 3. 清理镜像层 ---------
    log_subheader "3. 清理镜像层 (保留使用中的)"
    $prefix docker image prune -af 2>/dev/null || true
    log_success "镜像层已清理"

    #--------- 4. 清理 volumes ---------
    log_subheader "4. 清理 dangling volumes"
    $prefix docker volume prune -f 2>/dev/null || true
    log_success "Volumes 已清理"

    #--------- 5. 清理 overlay2 未引用层 ---------
    log_subheader "5. 清理 overlay2 未引用层"
    $prefix docker system prune -af --volumes 2>/dev/null || true
    log_success "overlay2 层已清理"

    #--------- 6. 清理容器日志 ---------
    log_subheader "6. 清理容器日志"
    $prefix sh -c "find /var/lib/docker/containers -name '*-json.log' -type f -exec truncate -s 0 {} \; 2>/dev/null" || true
    log_success "容器日志已清理"

    #--------- 7. 深度清理 BuildKit ---------
    log_subheader "7. 深度清理 BuildKit 数据库"
    $prefix sh -c "rm -rf /var/lib/docker/buildkit/cache.db /var/lib/docker/buildkit/metadata.db 2>/dev/null || true" || true
    log_success "BuildKit 数据库已重建"

    # 清理后状态
    log_info "清理后存储状态:"
    $prefix docker system df 2>/dev/null | head -6
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

        # 检查是否有 docker 命令
        if ! $prefix docker info &>/dev/null; then
            log_info "$runner 无 Docker (非 DIND 模式), 跳过"
            continue
        fi

        # 清理构建缓存
        $prefix docker builder prune -af --reserved-space=2G 2>/dev/null || true

        # 清理容器和镜像
        $prefix docker system prune -af 2>/dev/null || true

        # 清理日志
        $prefix sh -c "find /var/lib/docker/containers -name '*-json.log' -type f -exec truncate -s 0 {} \; 2>/dev/null" || true

        log_success "$runner 清理完成"
    done
}

#===============================================================================
# K3s 容器运行时清理
#===============================================================================

clean_k3s() {
    log_header "清理 K3s 容器运行时"

    #--------- 显示当前镜像状态 ---------
    log_subheader "Harbor 镜像状态"
    echo "--- harbor.sisys.local/sisys/app (可清理) ---"
    sudo k3s crictl images 2>/dev/null | grep "harbor.sisys.local/sisys/app" | awk '{print $1":"$2, "(" $3 ")"}' | sort -u || echo "  无"
    echo ""
    echo "--- harbor.sisys.local/sisys/tools (禁止清理) ---"
    sudo k3s crictl images 2>/dev/null | grep "harbor.sisys.local/sisys/tools" | awk '{print $1":"$2}' | sort -u | head -10 || echo "  无"
    echo ""
    echo "--- docker.io/goharbor/* (禁止清理) ---"
    sudo k3s crictl images 2>/dev/null | grep "docker.io/goharbor" | awk '{print $1":"$2}' | sort -u || echo "  无"

    #--------- crictl prune (清理所有未使用的镜像) ---------
    log_subheader "执行 crictl rmi --prune (清理未使用镜像)"
    sudo k3s crictl rmi --prune 2>/dev/null || true
    log_success "K3s 未使用镜像已清理"

    #--------- crictl rmi (清理 sisys/app 镜像) ---------
    log_subheader "执行 crictl rmi (清理 sisys/app 镜像)"
    sudo crictl images -q --filter "reference=harbor.sisys.local/sisys/app:*" | xargs sudo crictl rmi
    log_success "sisys/app 镜像已清理"

    #--------- 清理后状态 ---------
    log_subheader "清理后 harbor.sisys.local/sisys/app 状态"
    sudo k3s crictl images 2>/dev/null | grep "harbor.sisys.local/sisys/app" | awk '{print $1":"$2, "(" $3 ")"}' | sort -u || echo "  无"

    log_success "K3s 清理完成"
}

#===============================================================================
# Harbor / Trivy 清理
#===============================================================================

clean_harbor() {
    log_header "清理 Harbor / Trivy"

    #--------- Trivy 缓存清理 ---------
    log_subheader "Trivy 缓存清理"

    if kubectl get pod "$TRIVY_POD" -n "$HARBOR_NS" &>/dev/null; then
        # 清理前大小
        local before_size
        before_size=$(kubectl_exec "$TRIVY_POD" "$HARBOR_NS" "" du -sh /home/scanner/.cache 2>/dev/null || echo "N/A")
        log_info "Trivy 缓存清理前: $before_size"

        # 执行清理
        kubectl_exec "$TRIVY_POD" "$HARBOR_NS" "" trivy clean --all 2>/dev/null || true

        # 清理后大小
        local after_size
        after_size=$(kubectl_exec "$TRIVY_POD" "$HARBOR_NS" "" du -sh /home/scanner/.cache 2>/dev/null || echo "N/A")
        log_info "Trivy 缓存清理后: $after_size"
        log_success "Trivy 缓存已清理"
    else
        log_warn "Trivy Pod 未运行"
    fi

    #--------- Harbor Registry 垃圾回收 ---------
    log_subheader "Harbor Registry 垃圾回收"

    if kubectl get pod "$REGISTRY_POD" -n "$HARBOR_NS" &>/dev/null; then
        local registry_before
        registry_before=$(kubectl_exec "$REGISTRY_POD" "$HARBOR_NS" "registry" du -sh /storage 2>/dev/null || echo "N/A")
        log_info "Registry 清理前: $registry_before"

        # 执行 garbage collect (compact 模式)
        kubectl_exec "$REGISTRY_POD" "$HARBOR_NS" "registry" \
            /bin/registry garbage-collect /etc/registry/config.yml -m compact 2>/dev/null || true

        local registry_after
        registry_after=$(kubectl_exec "$REGISTRY_POD" "$HARBOR_NS" "registry" du -sh /storage 2>/dev/null || echo "N/A")
        log_info "Registry 清理后: $registry_after"
        log_success "Registry 垃圾回收完成"
    else
        log_warn "Registry Pod 未运行"
    fi

    #--------- 清理 Registry 上的 Trivy 缓存 ---------
    log_subheader "清理 Registry 上的 Trivy 扫描缓存"
    if kubectl get pod "$REGISTRY_POD" -n "$HARBOR_NS" &>/dev/null; then
        kubectl_exec "$REGISTRY_POD" "$HARBOR_NS" "registry" \
            sh -c "find /storage -name '.trivy' -type d -exec rm -rf {} + 2>/dev/null || true" || true
        log_success "Registry Trivy 缓存已清理"
    fi
}

#===============================================================================
# Docker Builder 清理 (本地 Docker)
#===============================================================================

clean_local_docker() {
    log_header "清理本地 Docker (如果有)"

    if command -v docker &>/dev/null; then
        log_info "本地 Docker 可用, 执行清理..."

        log_subheader "BuildKit 缓存"
        docker builder prune -af --reserved-space=10G 2>/dev/null || true

        log_subheader "系统 prune"
        docker system prune -af --volumes 2>/dev/null || true

        log_info "本地 Docker 清理完成"
    else
        log_info "本地无 Docker, 跳过"
    fi
}

#===============================================================================
# 系统清理
#===============================================================================

clean_system() {
    log_header "清理系统日志和缓存"

    #--------- apt 缓存 ---------
    log_subheader "APT 缓存清理"
    sudo apt clean 2>/dev/null || true
    sudo apt autoclean 2>/dev/null || true
    sudo apt autoremove -y 2>/dev/null || true
    log_success "APT 缓存已清理"

    #--------- 系统日志 ---------
    log_subheader "系统日志清理"
    sudo journalctl --vacuum-time=8h 2>/dev/null || true
    sudo find /var/log -type f -name "*.log" -mtime +7 -delete 2>/dev/null || true
    log_success "系统日志已清理"

    #--------- 临时文件 ---------
    log_subheader "临时文件清理"
    sudo rm -rf /tmp/* 2>/dev/null || true
    sudo rm -rf /var/tmp/* 2>/dev/null || true
    log_success "临时文件已清理"

    #--------- WSL 回收站 ---------
    log_subheader "回收站清理"
    rm -rf ~/.local/share/Trash/* 2>/dev/null || true
    log_success "回收站已清理"

    #--------- pip 缓存 (如果有) ---------
    if command -v pip3 &>/dev/null; then
        log_subheader "pip 缓存清理"
        pip3 cache purge 2>/dev/null || true
        log_success "pip 缓存已清理"
    fi

    #--------- npm 缓存 (如果有) ---------
    if command -v npm &>/dev/null; then
        log_subheader "npm 缓存清理"
        npm cache clean --force 2>/dev/null || true
        log_success "npm 缓存已清理"
    fi

    log_success "系统清理完成"
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
    echo "  -v, --verbose     显示详细输出"
    echo "  -n, --dry-run     试运行 (不实际清理)"
    echo "  --help            显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0              # 全量清理"
    echo "  $0 -r           # 仅显示存储报告"
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
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -n|--dry-run)
            DRY_RUN=true
            shift
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
    log_header "系统存储垃圾清理开始"
    echo "模式: $MODE"
    [ "$DRY_RUN" = true ] && log_warn "DRY-RUN 模式: 不会实际执行清理"
    echo ""

    case $MODE in
        report)
            show_report
            ;;
        all)
            show_report
            echo ""
            read -p "是否执行全量清理? (y/N): " confirm
            if [[ "$confirm" =~ ^[Yy]$ ]]; then
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
            read -p "是否清理 Docker 相关? (y/N): " confirm
            if [[ "$confirm" =~ ^[Yy]$ ]]; then
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
            read -p "是否清理 Harbor/Trivy? (y/N): " confirm
            if [[ "$confirm" =~ ^[Yy]$ ]]; then
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
    echo ""

    # 最终状态
    if [[ "$MODE" == "all" || "$MODE" == "report" ]]; then
        show_report
    fi
}

# 执行
main
