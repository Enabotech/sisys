#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

trap 'log_error "脚本失败：第 $LINENO 行，命令：$BASH_COMMAND"' ERR

# =========================
# 配置区
# =========================
DRY_RUN="${DRY_RUN:-false}"

# 自动分级阈值（按最高磁盘占用率决定）
AUTO_SKIP_BELOW="${AUTO_SKIP_BELOW:-65}"   # < 65%：不清理
AUTO_LIGHT_AT="${AUTO_LIGHT_AT:-65}"       # 65%~79%：轻度
AUTO_NORMAL_AT="${AUTO_NORMAL_AT:-80}"     # 80%~89%：常规
AUTO_AGGRESSIVE_AT="${AUTO_AGGRESSIVE_AT:-90}" # >= 90%：激进

# 手动覆盖：auto / skip / light / normal / aggressive
CLEAN_LEVEL="${CLEAN_LEVEL:-auto}"

# 业务开关
CLEAN_K3S_IMAGES="${CLEAN_K3S_IMAGES:-true}"
CLEAN_RUNNERS="${CLEAN_RUNNERS:-true}"
CLEAN_HOST_DOCKER="${CLEAN_HOST_DOCKER:-true}"
CLEAN_SYSTEM="${CLEAN_SYSTEM:-true}"
CLEAN_K8S_GC="${CLEAN_K8S_GC:-true}"

# 高风险项默认只在 aggressive 执行
DELETE_UNBOUND_PVCS="${DELETE_UNBOUND_PVCS:-false}"
CLEAN_HARBOR="${CLEAN_HARBOR:-false}"
CLEAN_ARGOCD="${CLEAN_ARGOCD:-false}"
CLEAN_GITEA="${CLEAN_GITEA:-false}"
CLEAN_ORPHAN_PODS="${CLEAN_ORPHAN_PODS:-false}"
CLEAR_HISTORY="${CLEAR_HISTORY:-false}"

KEEP_JOURNAL_TIME="${KEEP_JOURNAL_TIME:-8h}"
KEEP_LOG_DAYS="${KEEP_LOG_DAYS:-3}"
KEEP_TMP_DAYS="${KEEP_TMP_DAYS:-1}"
EXEC_TIMEOUT="${EXEC_TIMEOUT:-20s}"

# 监控的磁盘路径
MONITORED_PATHS=(
  /
  /var/lib/docker
  /var/lib/containerd
  /var/lib/rancher/k3s
)

# 业务对象配置
ADV_NS="gitea-advacts"
ADV_POD_PREFIX="gitea-runner-dind-"
ADV_CONTAINER="docker-dind"

ACTIONS_NS="gitea-actions"
ACTIONS_POD_PREFIX="gitea-org-runner-"
ACTIONS_CONTAINER="runner"

ARGOCD_NS="argocd"
GITEA_NS="gitea"

# Harbor / Git 服务可选外部参数
: "${HARBOR_URL:=}"
: "${HARBOR_ADMIN_USER:=}"
: "${HARBOR_ADMIN_PASS:=}"
: "${GITEA_REPO_GC_CMD:=gitea admin repo-gc}"

# =========================
# 颜色输出
# =========================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

is_true() {
  case "${1,,}" in
    true|1|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

have() {
  command -v "$1" >/dev/null 2>&1
}

join_q() {
  local out=""
  local arg
  for arg in "$@"; do
    out+="$(printf '%q ' "$arg")"
  done
  printf '%s' "${out% }"
}

run_cmd() {
  if is_true "$DRY_RUN"; then
    log_info "[dry-run] $(join_q "$@")"
    return 0
  fi

  if "$@"; then
    return 0
  fi

  log_warn "命令失败，已跳过：$(join_q "$@")"
  return 0
}

run_sh() {
  if is_true "$DRY_RUN"; then
    log_info "[dry-run] $*"
    return 0
  fi

  if bash -lc "$*"; then
    return 0
  fi

  log_warn "命令失败，已跳过：$*"
  return 0
}

with_timeout() {
  if have timeout; then
    timeout "$EXEC_TIMEOUT" "$@"
  else
    "$@"
  fi
}

pod_exists() {
  local ns="$1"
  local pod="$2"
  kubectl get pod -n "$ns" "$pod" >/dev/null 2>&1
}

find_pods_by_prefix() {
  local ns="$1"
  local prefix="$2"

  kubectl get pods -n "$ns" -o name 2>/dev/null \
    | sed 's#^pod/##' \
    | awk -v p="$prefix" '$0 ~ "^" p {print}'
}

exec_in_pod() {
  local ns="$1"
  local pod="$2"
  local container="$3"
  shift 3

  if ! pod_exists "$ns" "$pod"; then
    log_warn "跳过：$ns/$pod 不存在"
    return 0
  fi

  local -a cmd=(kubectl exec -n "$ns" "$pod")
  [[ -n "$container" ]] && cmd+=(-c "$container")
  cmd+=(-- "$@")

  if is_true "$DRY_RUN"; then
    log_info "[dry-run] $(join_q "${cmd[@]}")"
    return 0
  fi

  with_timeout "${cmd[@]}" >/dev/null 2>&1 || log_warn "exec 失败：$ns/$pod"
  return 0
}

get_path_usage() {
  local path="$1"
  [[ -e "$path" ]] || return 1
  df -P "$path" 2>/dev/null | awk 'NR==2 {gsub(/%/,"",$5); print $5}'
}

determine_auto_level() {
  local max=0
  local path pct

  for path in "${MONITORED_PATHS[@]}"; do
    pct="$(get_path_usage "$path" || true)"
    [[ -n "${pct:-}" ]] || continue
    [[ "$pct" =~ ^[0-9]+$ ]] || continue
    (( pct > max )) && max="$pct"
  done

  echo "$max"
}

level_rank() {
  case "$1" in
    skip) echo 0 ;;
    light) echo 1 ;;
    normal) echo 2 ;;
    aggressive) echo 3 ;;
    *) echo 0 ;;
  esac
}

should_run_level() {
  local current="$1"
  local need="$2"
  [[ "$(level_rank "$current")" -ge "$(level_rank "$need")" ]]
}

choose_level() {
  if [[ "$CLEAN_LEVEL" != "auto" ]]; then
    case "$CLEAN_LEVEL" in
      skip|light|normal|aggressive) echo "$CLEAN_LEVEL" ;;
      *)
        log_warn "CLEAN_LEVEL 非法，改为 auto"
        echo "auto"
        ;;
    esac
    return
  fi

  local max_usage
  max_usage="$(determine_auto_level)"

  log_info "监控磁盘最高占用率：${max_usage}%"
  if (( max_usage < AUTO_SKIP_BELOW )); then
    echo "skip"
  elif (( max_usage < AUTO_NORMAL_AT )); then
    echo "light"
  elif (( max_usage < AUTO_AGGRESSIVE_AT )); then
    echo "normal"
  else
    echo "aggressive"
  fi
}

# =========================
# 清理项
# =========================
cleanup_k3s_images() {
  is_true "$CLEAN_K3S_IMAGES" || return 0

  log_info "清理 K3s / containerd 无用镜像..."
  if have sudo && have k3s; then
    run_sh "sudo k3s crictl rmi --prune >/dev/null 2>&1 || true"
  fi

  if have sudo && have crictl; then
    run_sh "sudo crictl rmi --prune >/dev/null 2>&1 || true"
    run_sh "sudo crictl images -q --filter 'reference=harbor.sisys.local/sisys/app:*' | xargs -r sudo crictl rmi >/dev/null 2>&1 || true"
  fi
}

cleanup_runners() {
  is_true "$CLEAN_RUNNERS" || return 0

  log_info "清理 gitea runners 内部缓存..."
  local pods pod
  for ns_prefix in "$ADV_NS:$ADV_POD_PREFIX:$ADV_CONTAINER:advacts Runner" "$ACTIONS_NS:$ACTIONS_POD_PREFIX:$ACTIONS_CONTAINER:actions Runner"; do
    IFS=':' read -r ns prefix container label <<<"$ns_prefix"
    mapfile -t pods < <(find_pods_by_prefix "$ns" "$prefix" || true)
    if [[ "${#pods[@]}" -eq 0 ]]; then
      log_warn "未找到匹配 Pod：$ns/${prefix}*"
      continue
    fi

    for pod in "${pods[@]}"; do
      log_info "清理 $label：$ns/$pod"
      exec_in_pod "$ns" "$pod" "$container" docker system prune -af
      exec_in_pod "$ns" "$pod" "$container" docker volume prune -f
      exec_in_pod "$ns" "$pod" "$container" sh -lc 'docker ps -a --filter "name=buildx_buildkit" -q | xargs -r docker rm -f'
    done
  done
}

cleanup_host_docker() {
  is_true "$CLEAN_HOST_DOCKER" || return 0
  have docker || { log_warn "未找到 docker，跳过宿主机 Docker 清理"; return 0; }

  log_info "清理宿主机 Docker..."

  # 轻度：只清 builder cache
  run_cmd docker builder prune -af

  # 常规：清 dangling/unused，但不带 volumes
  if should_run_level "$CURRENT_LEVEL" "normal"; then
    run_cmd docker system prune -af
  fi

  # 激进：连 volumes 一起清
  if should_run_level "$CURRENT_LEVEL" "aggressive"; then
    run_cmd docker system prune -af --volumes
  fi
}

cleanup_system() {
  is_true "$CLEAN_SYSTEM" || return 0
  have sudo || { log_warn "未找到 sudo，跳过系统级清理"; return 0; }

  log_info "清理系统缓存和日志..."
  run_sh "sudo apt-get clean"
  run_sh "sudo apt-get autoclean"
  run_sh "sudo journalctl --rotate >/dev/null 2>&1 || true"
  run_sh "sudo journalctl --vacuum-time=${KEEP_JOURNAL_TIME} >/dev/null 2>&1 || true"
  run_sh "sudo find /var/log -type f -name '*.log' -mtime +${KEEP_LOG_DAYS} -delete >/dev/null 2>&1 || true"
  run_sh "sudo find /tmp /var/tmp -mindepth 1 -maxdepth 1 -mtime +${KEEP_TMP_DAYS} -exec rm -rf {} + >/dev/null 2>&1 || true"

  log_info "清理用户回收站..."
  run_sh 'find "$HOME/.local/share/Trash" -mindepth 1 -maxdepth 1 -exec rm -rf {} + >/dev/null 2>&1 || true'

  if is_true "$CLEAR_HISTORY"; then
    log_warn "清理历史命令记录..."
    run_sh 'rm -f "$HOME/.bash_history" >/dev/null 2>&1 || true'
    run_sh 'history -c >/dev/null 2>&1 || true'
  fi
}

cleanup_k8s_gc() {
  is_true "$CLEAN_K8S_GC" || return 0
  have kubectl || { log_warn "未找到 kubectl，跳过 K8s 清理"; return 0; }

  # 轻度/常规：只清理已完成/失败的 Pod 和 Job
  if should_run_level "$CURRENT_LEVEL" "normal"; then
    log_info "清理已完成 / 失败的 Pod..."
    run_sh "kubectl get pods -A -o json | jq -r '.items[] | select(.status.phase==\"Succeeded\" or .status.phase==\"Failed\") | [.metadata.namespace,.metadata.name] | @tsv' | while IFS=\$'\\t' read -r ns name; do kubectl delete pod -n \"\$ns\" \"\$name\" >/dev/null 2>&1 || true; done"

    log_info "清理已完成 / 失败的 Job..."
    if have jq; then
      run_sh "kubectl get jobs -A -o json | jq -r '.items[] | select((.status.succeeded // 0) > 0 or (.status.failed // 0) > 0) | [.metadata.namespace,.metadata.name] | @tsv' | while IFS=\$'\\t' read -r ns name; do kubectl delete job -n \"\$ns\" \"\$name\" >/dev/null 2>&1 || true; done"
    else
      log_warn "未找到 jq，跳过 Job 清理"
    fi

    log_info "清理副本数为 0 的 ReplicaSet（仅较旧对象）..."
    if have jq; then
      run_sh "kubectl get rs -A -o json | jq -r --arg cutoff \"\$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)\" '.items[] | select((.status.replicas // 0) == 0 and .metadata.creationTimestamp < \$cutoff) | [.metadata.namespace,.metadata.name] | @tsv' | while IFS=\$'\\t' read -r ns name; do kubectl delete rs -n \"\$ns\" \"\$name\" >/dev/null 2>&1 || true; done"
    else
      log_warn "未找到 jq，跳过 ReplicaSet 清理"
    fi
  fi

  # 激进：只删 Lost PVC，避免误伤 Pending
  if should_run_level "$CURRENT_LEVEL" "aggressive" && is_true "$DELETE_UNBOUND_PVCS"; then
    log_warn "删除 Lost PVC（高风险）..."
    if have jq; then
      run_sh "kubectl get pvc -A -o json | jq -r '.items[] | select(.status.phase==\"Lost\") | [.metadata.namespace,.metadata.name] | @tsv' | while IFS=\$'\\t' read -r ns name; do kubectl delete pvc -n \"\$ns\" \"\$name\" >/dev/null 2>&1 || true; done"
    else
      log_warn "未找到 jq，跳过 PVC 清理"
    fi
  fi
}

cleanup_harbor() {
  is_true "$CLEAN_HARBOR" || return 0
  should_run_level "$CURRENT_LEVEL" "aggressive" || return 0

  log_info "触发 Harbor 垃圾回收..."
  if [[ -n "$HARBOR_URL" && -n "$HARBOR_ADMIN_USER" && -n "$HARBOR_ADMIN_PASS" ]] && have curl; then
    run_sh "curl -fsSk -u '${HARBOR_ADMIN_USER}:${HARBOR_ADMIN_PASS}' -X POST '${HARBOR_URL%/}/api/v2.0/system/gc/schedule' -H 'Content-Type: application/json' -d '{\"schedule\":null}'"
  else
    log_warn "未配置 Harbor API 参数，跳过 Harbor GC"
  fi
}

cleanup_argocd() {
  is_true "$CLEAN_ARGOCD" || return 0
  should_run_level "$CURRENT_LEVEL" "normal" || return 0
  have kubectl || { log_warn "未找到 kubectl，跳过 Argo CD 清理"; return 0; }

  log_info "重启 Argo CD repo-server..."
  run_cmd kubectl rollout restart deployment/argocd-repo-server -n "$ARGOCD_NS"

  if should_run_level "$CURRENT_LEVEL" "aggressive"; then
    local redis_pod
    redis_pod="$(kubectl get pods -n "$ARGOCD_NS" -o name 2>/dev/null | sed 's#^pod/##' | awk '/redis/ {print; exit}')"
    if [[ -n "$redis_pod" ]]; then
      log_warn "清理 Argo CD Redis（FLUSHALL，激进）..."
      exec_in_pod "$ARGOCD_NS" "$redis_pod" "" redis-cli FLUSHALL
    fi
  fi
}

cleanup_gitea() {
  is_true "$CLEAN_GITEA" || return 0
  should_run_level "$CURRENT_LEVEL" "aggressive" || return 0
  have kubectl || { log_warn "未找到 kubectl，跳过 Gitea 清理"; return 0; }

  log_info "执行 Gitea 仓库垃圾收集..."
  local gitea_pod
  gitea_pod="$(kubectl get pods -n "$GITEA_NS" -o name 2>/dev/null | sed 's#^pod/##' | awk '/^gitea-/ {print; exit}')"

  if [[ -z "$gitea_pod" ]]; then
    log_warn "未找到 Gitea Pod，跳过 repo-gc"
    return 0
  fi

  exec_in_pod "$GITEA_NS" "$gitea_pod" "" sh -lc "$GITEA_REPO_GC_CMD"
}

cleanup_orphan_pod_dirs() {
  is_true "$CLEAN_ORPHAN_PODS" || return 0
  should_run_level "$CURRENT_LEVEL" "aggressive" || return 0
  have kubectl || { log_warn "未找到 kubectl，跳过 kubelet 孤儿目录清理"; return 0; }

  [[ -d /var/lib/kubelet/pods ]] || { log_warn "/var/lib/kubelet/pods 不存在，跳过"; return 0; }

  log_warn "清理 kubelet 孤儿 Pod 目录（仅当前节点，激进）..."
  local uid_file="/tmp/active_pod_uids.$$"
  run_sh "kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.uid}{\"\\n\"}{end}' > '$uid_file'"

  [[ -s "$uid_file" ]] || { log_warn "未获取到活跃 Pod UID，跳过"; rm -f "$uid_file" >/dev/null 2>&1 || true; return 0; }

  local dir uid
  for dir in /var/lib/kubelet/pods/*/; do
    [[ -d "$dir" ]] || continue
    uid="${dir%/}"
    uid="${uid##*/}"
    if ! grep -Fxq "$uid" "$uid_file"; then
      if is_true "$DRY_RUN"; then
        log_info "[dry-run] 将删除孤儿目录：$dir"
      else
        log_warn "删除孤儿目录：$dir"
        rm -rf "$dir" >/dev/null 2>&1 || true
      fi
    fi
  done

  rm -f "$uid_file" >/dev/null 2>&1 || true
}

show_disk_usage() {
  log_info "当前磁盘使用情况："
  run_sh "df -h / /var/lib/docker /var/lib/containerd /var/lib/rancher/k3s 2>/dev/null || df -h /"
}

main() {
  if is_true "$DRY_RUN"; then
    log_warn "DRY-RUN 模式启用，不会执行实际删除"
  fi

  CURRENT_LEVEL="$(choose_level)"
  if [[ "$CURRENT_LEVEL" == "auto" ]]; then
    CURRENT_LEVEL="skip"
  fi

  log_info "本次清理级别：$CURRENT_LEVEL"

  if [[ "$CURRENT_LEVEL" == "skip" ]]; then
    log_ok "磁盘压力不高，跳过清理。"
    show_disk_usage
    exit 0
  fi

  cleanup_k3s_images
  cleanup_system
  cleanup_host_docker
  cleanup_runners
  cleanup_k8s_gc
  cleanup_argocd
  cleanup_harbor
  cleanup_gitea
  cleanup_orphan_pod_dirs

  show_disk_usage
  log_ok "脚本执行完毕。"
}

main "$@"
