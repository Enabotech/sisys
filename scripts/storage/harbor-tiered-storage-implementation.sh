#!/bin/bash

# =============================================================================
# Harbor 分层存储实施脚本 (WSL2 + Ubuntu 22.04) - 详细实施版
# =============================================================================
# 用途：自动化实施 Harbor SSD+HDD 分层存储
# 环境：WSL2 Ubuntu 22.04 + K3S 单节点
# 存储：SSD 500GB + HDD 10TB (/mnt/x/hddstorage)
# 预计时间：2-3 小时
# =============================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# 配置变量
HDD_MOUNT_POINT="${HDD_MOUNT_POINT:-/mnt/x/hddstorage/harbor}"
HDD_WINDOWS_PATH="${HDD_WINDOWS_PATH:-X:\\hddstorage\\harbor}"
SSD_STORAGE_CLASS="local-path-ssd"
HDD_STORAGE_CLASS="local-path-hdd"
HARBOR_NS="${HARBOR_NS:-harbor}"
BACKUP_DIR="/mnt/x/hddstorage/harbor/backup/pre_migration_$(date +%Y%m%d_%H%M%S)"

# 计时
START_TIME=$(date +%s)

# =============================================================================
# 函数定义
# =============================================================================
print_header() {
    echo -e "${CYAN}=========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}=========================================${NC}"
}

print_step() {
    echo -e "${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

check_prerequisites() {
    print_step "检查前置条件..."

    # 检查 WSL2
    if grep -qi microsoft /proc/version || grep -qi wsl /proc/version; then
        print_success "WSL2 环境检测通过"
    else
        print_error "未在 WSL2 环境中运行"
        exit 1
    fi

    # 检查 kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl 未安装"
        exit 1
    fi

    # 检查 HDD 挂载点
    if [ ! -d "$HDD_MOUNT_POINT" ]; then
        print_error "HDD 挂载点 $HDD_MOUNT_POINT 不存在"
        print_info "请在 Windows 中创建：$HDD_WINDOWS_PATH"
        exit 1
    fi

    # 检查 HDD 可写性
    if ! touch "$HDD_MOUNT_POINT/.wsl2_test" 2>/dev/null; then
        print_error "HDD 挂载点不可写"
        exit 1
    else
        rm -f "$HDD_MOUNT_POINT/.wsl2_test"
    fi

    # 检查 K3S
    if ! kubectl cluster-info &> /dev/null; then
        print_error "无法连接到 K3S 集群"
        exit 1
    fi

    # 检查 Harbor 命名空间
    if ! kubectl get namespace "$HARBOR_NS" &> /dev/null; then
        print_error "Harbor 命名空间不存在"
        exit 1
    fi

    print_success "前置条件检查通过"
}

backup_harbor_config() {
    print_header "阶段 1: 备份 Harbor 配置"

    mkdir -p "$BACKUP_DIR"

    # 备份配置
    kubectl get deployment harbor-registry -n "$HARBOR_NS" -o yaml > "$BACKUP_DIR/harbor-registry-deployment.yaml"
    kubectl get pvc -n "$HARBOR_NS" -o yaml > "$BACKUP_DIR/harbor-pvc.yaml"
    kubectl get storageclass -o yaml > "$BACKUP_DIR/storageclass.yaml"

    print_success "配置备份完成：$BACKUP_DIR"
}

prepare_windows_dirs() {
    print_header "阶段 2: Windows 宿主机目录准备"

    print_info "请在 Windows PowerShell (管理员) 执行以下命令:"
    echo ""
    cat << 'POWERSHELL'
# Windows PowerShell (管理员)
$directories = @(
    "X:\hddstorage\harbor\warm",
    "X:\hddstorage\harbor\cold",
    "X:\hddstorage\harbor\backup",
    "X:\hddstorage\harbor\k3s-pv"
)
foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force
    }
}
$acl = Get-Acl "X:\hddstorage\harbor"
$accessRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    "Everyone", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
$acl.AddAccessRule($accessRule)
Set-Acl "X:\hddstorage\harbor" $acl
POWERSHELL
    echo ""

    read -p "是否已在 Windows 中完成目录创建？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_step "请先在 Windows 中创建目录"
        exit 0
    fi

    # 验证
    if [ -d "$HDD_MOUNT_POINT" ]; then
        print_success "HDD 挂载点验证通过"
    else
        print_error "HDD 挂载点不可访问"
        exit 1
    fi
}

test_hdd_performance() {
    print_header "阶段 3: HDD 性能测试"

    TEST_DIR="$HDD_MOUNT_POINT/perf_test_$$"
    mkdir -p "$TEST_DIR"

    # 顺序写入
    print_step "顺序写入测试 (100MB)..."
    dd if=/dev/zero of="$TEST_DIR/test_100mb" bs=1M count=100 conv=fdatasync 2>&1 | tail -3

    # 顺序读取
    print_step "顺序读取测试 (100MB)..."
    dd if="$TEST_DIR/test_100mb" of=/dev/null bs=1M 2>&1 | tail -3

    # 清理
    rm -rf "$TEST_DIR"

    print_info "WSL2 9P 参考标准:"
    echo "  顺序读写：80-120 MB/s  ✅ 正常"
    echo "  低于 50 MB/s 需要优化配置"
}

create_storage_classes() {
    print_header "阶段 4: 创建 StorageClass"

    print_step "创建 SSD StorageClass..."
    cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ${SSD_STORAGE_CLASS}
provisioner: rancher.io/local-path
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
parameters:
  nodePath: /var/lib/rancher/k3s/storage
  storageType: ssd
EOF

    print_step "创建 HDD StorageClass (WSL2)..."
    cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ${HDD_STORAGE_CLASS}
provisioner: rancher.io/local-path
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
parameters:
  nodePath: ${HDD_MOUNT_POINT}/k3s-pv
  storageType: hdd
EOF

    print_step "验证 StorageClass..."
    kubectl get storageclass

    print_success "StorageClass 创建完成"
}

create_tiered_pvcs() {
    print_header "阶段 5: 创建分层 PVC"

    print_step "创建热数据 PVC (SSD, 50Gi)..."
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: harbor-registry-hot
  namespace: ${HARBOR_NS}
  labels:
    app: harbor-registry
    tier: hot
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: ${SSD_STORAGE_CLASS}
  resources:
    requests:
      storage: 50Gi
EOF

    print_step "创建温数据 PVC (HDD, 2Ti)..."
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: harbor-registry-warm
  namespace: ${HARBOR_NS}
  labels:
    app: harbor-registry
    tier: warm
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: ${HDD_STORAGE_CLASS}
  resources:
    requests:
      storage: 2Ti
EOF

    print_step "创建冷数据 PVC (HDD, 8Ti)..."
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: harbor-registry-cold
  namespace: ${HARBOR_NS}
  labels:
    app: harbor-registry
    tier: cold
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: ${HDD_STORAGE_CLASS}
  resources:
    requests:
      storage: 8Ti
EOF

    print_step "等待 PVC 绑定..."
    kubectl wait --for=condition=bound pvc/harbor-registry-hot -n "$HARBOR_NS" --timeout=120s
    kubectl wait --for=condition=bound pvc/harbor-registry-warm -n "$HARBOR_NS" --timeout=120s
    kubectl wait --for=condition=bound pvc/harbor-registry-cold -n "$HARBOR_NS" --timeout=120s

    print_step "验证 PVC 状态..."
    kubectl get pvc -n "$HARBOR_NS" -l app=harbor-registry

    print_success "分层 PVC 创建完成"
}

stop_harbor_service() {
    print_header "阶段 6: 停止 Harbor 服务 ⚠️"

    print_warning "停机迁移开始 - Harbor 服务将暂停"

    print_step "停止 Harbor Registry..."
    kubectl scale deployment harbor-registry -n "$HARBOR_NS" --replicas=0

    print_step "等待 Pod 停止..."
    kubectl wait --for=delete pod -l app=harbor-registry -n "$HARBOR_NS" --timeout=120s

    print_success "Harbor 服务已停止"
}

migrate_data() {
    print_header "阶段 7: 数据迁移"

    print_step "创建迁移 Job..."
    cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: harbor-data-migration
  namespace: ${HARBOR_NS}
spec:
  template:
    spec:
      containers:
      - name: rsync
        image: alpine/rsync:latest
        command: ["rsync", "-avz", "--progress", "--stats"]
        args:
          - /source/
          - /dest/
        volumeMounts:
        - name: source-storage
          mountPath: /source
        - name: dest-storage
          mountPath: /dest
      volumes:
      - name: source-storage
        persistentVolumeClaim:
          claimName: harbor-registry
      - name: dest-storage
        persistentVolumeClaim:
          claimName: harbor-registry-hot
      restartPolicy: Never
  backoffLimit: 3
EOF

    print_step "监控迁移进度..."
    echo "实时日志:"
    kubectl logs -f job/harbor-data-migration -n "$HARBOR_NS" &
    LOG_PID=$!

    print_step "等待迁移完成 (预计 30-90 分钟)..."
    kubectl wait --for=condition=complete job/harbor-data-migration -n "$HARBOR_NS" --timeout=7200s

    # 停止日志进程
    kill $LOG_PID 2>/dev/null || true

    print_success "数据迁移完成"
}

start_harbor_service() {
    print_header "阶段 8: 启动 Harbor 服务"

    print_step "启动 Harbor Registry..."
    kubectl scale deployment harbor-registry -n "$HARBOR_NS" --replicas=1

    print_step "等待 Pod 就绪..."
    kubectl wait --for=condition=ready pod -l app=harbor-registry -n "$HARBOR_NS" --timeout=300s

    print_step "验证 Pod 状态..."
    kubectl get pods -n "$HARBOR_NS" -l app=harbor-registry

    print_success "Harbor 服务已启动"
}

verify_implementation() {
    print_header "阶段 9: 功能验证"

    print_step "存储使用验证..."
    echo "SSD 使用:"
    df -h /var/lib/rancher/k3s
    echo ""
    echo "HDD 使用:"
    df -h "$HDD_MOUNT_POINT"

    print_success "验证完成"
}

print_summary() {
    print_header "✅ Harbor 分层存储实施完成"

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo ""
    echo "实施时间：$((DURATION / 3600)) 小时 $(( (DURATION % 3600) / 60 )) 分钟"
    echo ""
    echo "存储架构:"
    echo "  SSD (热数据): 50Gi"
    echo "  HDD (温数据): 2Ti"
    echo "  HDD (冷数据): 8Ti"
    echo ""
    echo "备份位置：$BACKUP_DIR"
    echo ""
    echo "下一步:"
    echo "  1. 查看监控：kubectl get cronjob -n harbor"
    echo "  2. 功能测试：docker push/pull 测试镜像"
    echo "  3. 更新文档：记录实施结果"
    echo ""
}

# =============================================================================
# 主流程
# =============================================================================
main() {
    print_header "Harbor 分层存储实施脚本 (WSL2 + Ubuntu 22.04)"
    echo ""
    echo "配置信息:"
    echo "  HDD 挂载点：$HDD_MOUNT_POINT"
    echo "  HDD Windows 路径：$HDD_WINDOWS_PATH"
    echo "  Harbor 命名空间：$HARBOR_NS"
    echo ""

    # 确认执行
    print_warning "此脚本将修改 Harbor 存储配置并暂停服务"
    print_warning "预计耗时：2-3 小时"
    print_warning "请确保已备份重要数据"
    echo ""
    read -p "是否继续执行？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_step "操作已取消"
        exit 0
    fi

    # 执行各阶段
    check_prerequisites
    backup_harbor_config
    prepare_windows_dirs
    test_hdd_performance
    create_storage_classes
    create_tiered_pvcs
    stop_harbor_service
    migrate_data
    start_harbor_service
    verify_implementation
    print_summary
}

# 执行主流程
main "$@"
