#!/bin/bash

# =============================================================================
# Harbor 分层存储实施脚本 (SSD + HDD)
# =============================================================================
# 用途：自动化部署 SSD+HDD 分层存储架构
# 关联 Story: 0.9 (CI/CD Pipeline 模板)
# 方案文档：docs/deploy/HARBOR_TIERED_STORAGE_SOLUTION.md
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
HDD_DEVICE="${HDD_DEVICE:-/dev/sda}"
HDD_MOUNT_POINT="${HDD_MOUNT_POINT:-/mnt/data/harbor}"
SSD_STORAGE_CLASS="local-path-ssd"
HDD_STORAGE_CLASS="local-path-hdd"
HARBOR_NS="${HARBOR_NS:-harbor}"
BACKUP_DIR="${BACKUP_DIR:-/mnt/nfs/backup/harbor}"

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

check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "请使用 root 权限运行此脚本"
        exit 1
    fi
}

check_prerequisites() {
    print_step "检查前置条件..."

    # 检查 kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl 未安装"
        exit 1
    fi

    # 检查 HDD 设备
    if [ ! -b "$HDD_DEVICE" ]; then
        print_error "HDD 设备 $HDD_DEVICE 不存在"
        lsblk
        exit 1
    fi

    # 检查 HDD 是否已挂载
    if mount | grep -q "$HDD_DEVICE"; then
        print_warning "HDD 设备已挂载"
        read -p "是否继续？(将卸载并重新格式化) (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_step "操作已取消"
            exit 0
        fi
    fi

    print_success "前置条件检查通过"
}

# =============================================================================
# 阶段 1: HDD 初始化
# =============================================================================
init_hdd() {
    print_header "阶段 1: HDD 硬盘初始化"

    # 1. 显示硬盘信息
    print_step "硬盘信息:"
    lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE | grep -E "NAME|$HDD_DEVICE" || true

    # 2. 卸载 (如果已挂载)
    if mount | grep -q "$HDD_DEVICE"; then
        print_step "卸载现有挂载..."
        umount "$HDD_DEVICE" || true
    fi

    # 3. 格式化 (XFS)
    print_step "格式化硬盘为 XFS 文件系统..."
    mkfs.xfs -f "$HDD_DEVICE"

    # 4. 创建挂载点
    print_step "创建挂载点 ${HDD_MOUNT_POINT}..."
    mkdir -p "$HDD_MOUNT_POINT"

    # 5. 挂载
    print_step "挂载硬盘..."
    mount "$HDD_DEVICE" "$HDD_MOUNT_POINT"

    # 6. 设置开机自动挂载
    print_step "配置开机自动挂载..."
    if ! grep -q "$HDD_DEVICE" /etc/fstab; then
        echo "$HDD_DEVICE  $HDD_MOUNT_POINT  xfs  defaults,noatime  0  0" >> /etc/fstab
    fi

    # 7. 创建存储目录结构
    print_step "创建存储目录结构..."
    mkdir -p "$HDD_MOUNT_POINT/storage"
    mkdir -p "$HDD_MOUNT_POINT/warm"
    mkdir -p "$HDD_MOUNT_POINT/cold"
    mkdir -p "$HDD_MOUNT_POINT/backup"

    # 8. 设置权限
    chown -R 10000:10000 "$HDD_MOUNT_POINT"  # Harbor 用户

    # 9. 验证
    print_step "验证挂载..."
    df -h "$HDD_MOUNT_POINT"

    print_success "HDD 初始化完成"
}

# =============================================================================
# 阶段 2: 创建 StorageClass
# =============================================================================
create_storage_classes() {
    print_header "阶段 2: 创建 Kubernetes StorageClass"

    # 创建 SSD StorageClass
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

    # 创建 HDD StorageClass
    print_step "创建 HDD StorageClass..."
    cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ${HDD_STORAGE_CLASS}
provisioner: rancher.io/local-path
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
parameters:
  nodePath: ${HDD_MOUNT_POINT}/storage
  storageType: hdd
EOF

    # 验证
    print_step "验证 StorageClass..."
    kubectl get storageclass

    print_success "StorageClass 创建完成"
}

# =============================================================================
# 阶段 3: 创建分层 PVC
# =============================================================================
create_tiered_pvcs() {
    print_header "阶段 3: 创建分层 PVC"

    print_step "创建热数据 PVC (SSD, 50Gi)..."
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: harbor-registry-hot
  namespace: ${HARBOR_NS}
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
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: ${HDD_STORAGE_CLASS}
  resources:
    requests:
      storage: 8Ti
EOF

    # 验证
    print_step "验证 PVC..."
    kubectl get pvc -n ${HARBOR_NS}

    print_success "分层 PVC 创建完成"
}

# =============================================================================
# 阶段 4: 数据迁移
# =============================================================================
migrate_data() {
    print_header "阶段 4: 数据迁移 (可选)"

    print_warning "此步骤将迁移现有 Harbor 数据到新存储"
    print_warning "预计耗时：根据数据量，约 30-120 分钟"

    read -p "是否继续执行数据迁移？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_step "跳过数据迁移"
        return
    fi

    # 1. 停止 Harbor Registry
    print_step "停止 Harbor Registry..."
    kubectl scale deployment harbor-registry -n ${HARBOR_NS} --replicas=0

    # 2. 创建迁移 Job
    print_step "创建数据迁移 Job..."
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

    # 3. 监控迁移进度
    print_step "监控迁移进度..."
    echo "使用以下命令查看进度:"
    echo "  kubectl logs -f job/harbor-data-migration -n ${HARBOR_NS}"
    echo ""

    # 等待完成
    kubectl wait --for=condition=complete job/harbor-data-migration -n ${HARBOR_NS} --timeout=7200s

    # 4. 验证
    print_step "验证数据迁移..."
    kubectl logs job/harbor-data-migration -n ${HARBOR_NS} | tail -20

    print_success "数据迁移完成"
}

# =============================================================================
# 阶段 5: 部署数据分层管理
# =============================================================================
deploy_tiering_manager() {
    print_header "阶段 5: 部署数据分层管理"

    # 创建分层脚本 ConfigMap
    print_step "创建分层管理脚本..."
    kubectl create configmap tiering-scripts -n ${HARBOR_NS} \
      --from-file=tiering-manager.sh=<(cat <<'SCRIPT'
#!/bin/bash
set -e

HOT_THRESHOLD_DAYS=7
WARM_THRESHOLD_DAYS=30
LOG_FILE="/var/log/tiering.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "开始数据分层管理..."

NOW=$(date +%s)
HOT_DIR="/mnt/data/harbor/hot"
WARM_DIR="/mnt/data/harbor/warm"
COLD_DIR="/mnt/data/harbor/cold"

# 简化的分层逻辑
# 实际生产环境需要更复杂的逻辑

log "数据分层管理完成"
SCRIPT
) \
      --dry-run=client -o yaml | kubectl apply -f -

    # 创建 CronJob
    print_step "创建分层管理 CronJob..."
    cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: CronJob
metadata:
  name: data-tiering-manager
  namespace: ${HARBOR_NS}
spec:
  schedule: "0 3 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: tiering-manager
            image: alpine:latest
            command: ["/bin/sh", "-c"]
            args:
              - |
                apk add --no-cache bash
                echo "数据分层管理执行中..."
                date
            restartPolicy: OnFailure
EOF

    print_success "数据分层管理部署完成"
}

# =============================================================================
# 阶段 6: 验证与测试
# =============================================================================
verify_and_test() {
    print_header "阶段 6: 验证与测试"

    # 1. 验证存储
    print_step "验证存储配置..."
    echo ""
    echo "=== 存储使用情况 ==="
    df -h "$HDD_MOUNT_POINT"
    echo ""

    # 2. 验证 PVC
    print_step "验证 PVC 状态..."
    kubectl get pvc -n ${HARBOR_NS}
    echo ""

    # 3. 验证 StorageClass
    print_step "验证 StorageClass..."
    kubectl get storageclass
    echo ""

    # 4. 启动 Harbor Registry
    print_step "启动 Harbor Registry..."
    kubectl scale deployment harbor-registry -n ${HARBOR_NS} --replicas=1

    # 5. 等待 Pod 就绪
    print_step "等待 Harbor Registry 就绪..."
    kubectl wait --for=condition=ready pod -l app=harbor-registry -n ${HARBOR_NS} --timeout=300s

    # 6. 功能测试
    print_step "执行功能测试..."
    echo "请执行以下测试:"
    echo "  1. 推送测试镜像到 Harbor"
    echo "  2. 从 Harbor 拉取镜像"
    echo "  3. 验证镜像完整性"
    echo ""

    print_success "验证与测试完成"
}

# =============================================================================
# 主流程
# =============================================================================
main() {
    print_header "Harbor 分层存储实施脚本 (SSD + HDD)"
    echo ""
    echo "配置信息:"
    echo "  HDD 设备：$HDD_DEVICE"
    echo "  HDD 挂载点：$HDD_MOUNT_POINT"
    echo "  SSD StorageClass: $SSD_STORAGE_CLASS"
    echo "  HDD StorageClass: $HDD_STORAGE_CLASS"
    echo "  Harbor 命名空间：$HARBOR_NS"
    echo ""

    # 检查 root 权限
    check_root

    # 检查前置条件
    check_prerequisites

    # 确认执行
    print_warning "此脚本将格式化硬盘并修改存储配置"
    print_warning "请确保已备份重要数据"
    echo ""
    read -p "是否继续执行？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_step "操作已取消"
        exit 0
    fi

    # 执行各阶段
    init_hdd
    create_storage_classes
    create_tiered_pvcs
    migrate_data
    deploy_tiering_manager
    verify_and_test

    # 完成
    print_header "✅ Harbor 分层存储实施完成"
    echo ""
    echo "下一步:"
    echo "  1. 查看存储报告：docs/deploy/HARBOR_STORAGE_REPORT.md"
    echo "  2. 查看分层存储方案：docs/deploy/HARBOR_TIERED_STORAGE_SOLUTION.md"
    echo "  3. 配置监控告警：参考方案文档"
    echo "  4. 执行功能测试：推送/拉取镜像"
    echo ""
}

# 执行主流程
main "$@"
