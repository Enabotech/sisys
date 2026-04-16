#!/bin/bash

# =============================================================================
# Harbor 分层存储实施脚本 (WSL2 + SSD + HDD)
# =============================================================================
# 用途：在 WSL2 环境中自动化部署 SSD+HDD 分层存储架构
# 关联 Story: 0.9 (CI/CD Pipeline 模板)
# 方案文档：docs/deploy/HARBOR_TIERED_STORAGE_SOLUTION_WSL2.md
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

# 配置变量 (WSL2 适配)
HDD_MOUNT_POINT="${HDD_MOUNT_POINT:-/mnt/x/hddstorage/harbor}"
HDD_WINDOWS_PATH="${HDD_WINDOWS_PATH:-X:\\hddstorage\\harbor}"
SSD_STORAGE_CLASS="local-path-ssd"
HDD_STORAGE_CLASS="local-path-hdd"
HARBOR_NS="${HARBOR_NS:-harbor}"
WSL2_MODE="${WSL2_MODE:-true}"

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

check_wsl2() {
    print_step "检查 WSL2 环境..."

    if grep -qi microsoft /proc/version 2>/dev/null || grep -qi wsl /proc/version 2>/dev/null; then
        print_success "检测到 WSL2 环境"
        WSL2_MODE="true"
    else
        print_warning "未在 WSL2 环境中运行，部分功能可能不适用"
        WSL2_MODE="false"
    fi
}

check_prerequisites() {
    print_step "检查前置条件..."

    # 检查 kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl 未安装"
        exit 1
    fi

    # 检查 HDD 挂载点
    if [ ! -d "$HDD_MOUNT_POINT" ]; then
        print_error "HDD 挂载点 $HDD_MOUNT_POINT 不存在"
        echo ""
        print_info "请在 Windows 宿主机创建目录:"
        echo "  PowerShell: New-Item -ItemType Directory -Path \"${HDD_WINDOWS_PATH}\" -Force"
        echo ""
        exit 1
    fi

    # 检查 HDD 可写性
    if ! touch "$HDD_MOUNT_POINT/.wsl2_test" 2>/dev/null; then
        print_error "HDD 挂载点不可写"
        echo ""
        print_info "请检查 Windows 权限设置"
        exit 1
    else
        rm -f "$HDD_MOUNT_POINT/.wsl2_test"
    fi

    # 检查 K3S
    if ! kubectl cluster-info &> /dev/null; then
        print_error "无法连接到 K3S 集群"
        exit 1
    fi

    print_success "前置条件检查通过"
}

# =============================================================================
# 阶段 1: Windows 宿主机目录准备指导
# =============================================================================
prepare_windows_dirs() {
    print_header "阶段 1: Windows 宿主机目录准备"

    print_info "请在 Windows 宿主机 PowerShell (管理员) 中执行以下命令:"
    echo ""
    cat << 'POWERSHELL'
# Windows PowerShell (管理员权限)

# 1. 创建存储目录
New-Item -ItemType Directory -Path "X:\hddstorage\harbor\warm" -Force
New-Item -ItemType Directory -Path "X:\hddstorage\harbor\cold" -Force
New-Item -ItemType Directory -Path "X:\hddstorage\harbor\backup" -Force
New-Item -ItemType Directory -Path "X:\hddstorage\harbor\k3s-pv" -Force

# 2. 设置权限 (允许 WSL2 访问)
$acl = Get-Acl "X:\hddstorage\harbor"
$accessRule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
$acl.AddAccessRule($accessRule)
Set-Acl "X:\hddstorage\harbor" $acl

# 3. 验证目录
Get-ChildItem "X:\hddstorage\harbor" -Recurse -Depth 1
POWERSHELL
    echo ""

    read -p "是否已在 Windows 中完成目录创建？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_step "请先在 Windows 中创建目录"
        exit 0
    fi

    # 验证 WSL2 挂载
    print_step "验证 WSL2 挂载..."
    if [ -d "$HDD_MOUNT_POINT" ]; then
        print_success "HDD 挂载点可访问"
        ls -la "$HDD_MOUNT_POINT" | head -10
    else
        print_error "HDD 挂载点不可访问"
        print_info "请检查 WSL2 自动挂载配置"
        exit 1
    fi
}

# =============================================================================
# 阶段 2: HDD 性能测试
# =============================================================================
test_hdd_performance() {
    print_header "阶段 2: HDD 性能测试"

    TEST_FILE="$HDD_MOUNT_POINT/performance_test_$$"

    print_step "顺序写入测试 (100MB)..."
    dd if=/dev/zero of="$TEST_FILE" bs=1M count=100 conv=fdatasync 2>&1 | tail -3

    print_step "顺序读取测试 (100MB)..."
    dd if="$TEST_FILE" of=/dev/null bs=1M 2>&1 | tail -3

    # 清理
    rm -f "$TEST_FILE"

    print_info "WSL2 9P 挂载性能参考:"
    echo "  顺序读写：80-120 MB/s  ✅ 正常"
    echo "  随机读写：0.5-2 MB/s   ✅ 正常"
    echo ""
    echo "如果性能低于参考标准，请检查:"
    echo "  1. Windows 磁盘健康状态"
    echo "  2. WSL2 内存配置 (.wslconfig)"
    echo "  3. 网络延迟"
    echo ""
}

# =============================================================================
# 阶段 3: 创建 StorageClass
# =============================================================================
create_storage_classes() {
    print_header "阶段 3: 创建 Kubernetes StorageClass"

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
    print_step "创建 HDD StorageClass (WSL2 挂载)..."
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

    # 验证
    print_step "验证 StorageClass..."
    kubectl get storageclass

    print_success "StorageClass 创建完成"
}

# =============================================================================
# 阶段 4: 创建分层 PVC
# =============================================================================
create_tiered_pvcs() {
    print_header "阶段 4: 创建分层 PVC"

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
# 阶段 5: 创建存储目录结构
# =============================================================================
create_storage_structure() {
    print_header "阶段 5: 创建存储目录结构"

    print_step "创建 HDD 目录结构..."
    mkdir -p "$HDD_MOUNT_POINT/warm"
    mkdir -p "$HDD_MOUNT_POINT/cold"
    mkdir -p "$HDD_MOUNT_POINT/backup"
    mkdir -p "$HDD_MOUNT_POINT/k3s-pv"

    print_step "设置权限 (Harbor UID 10000)..."
    # WSL2 环境中，使用 chmod 而不是 chown
    chmod -R 755 "$HDD_MOUNT_POINT"

    print_step "验证目录结构..."
    ls -la "$HDD_MOUNT_POINT"

    print_success "存储目录结构创建完成"
}

# =============================================================================
# 阶段 6: 验证与测试
# =============================================================================
verify_and_test() {
    print_header "阶段 6: 验证与测试"

    # 1. 验证存储
    print_step "验证存储配置..."
    echo ""
    echo "=== SSD 存储使用情况 ==="
    df -h /var/lib/rancher/k3s
    echo ""
    echo "=== HDD 存储使用情况 ==="
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

    # 4. WSL2 特定测试
    print_step "WSL2 9P 挂载测试..."
    TEST_FILE="$HDD_MOUNT_POINT/wsl2_test_$$"
    echo "WSL2 Test $(date)" > "$TEST_FILE"
    cat "$TEST_FILE"
    rm -f "$TEST_FILE"
    print_success "WSL2 挂载测试通过"

    print_success "验证与测试完成"
}

# =============================================================================
# 主流程
# =============================================================================
main() {
    print_header "Harbor 分层存储实施脚本 (WSL2 + SSD + HDD)"
    echo ""
    echo "配置信息:"
    echo "  HDD 挂载点：$HDD_MOUNT_POINT"
    echo "  HDD Windows 路径：$HDD_WINDOWS_PATH"
    echo "  SSD StorageClass: $SSD_STORAGE_CLASS"
    echo "  HDD StorageClass: $HDD_STORAGE_CLASS"
    echo "  Harbor 命名空间：$HARBOR_NS"
    echo "  WSL2 模式：$WSL2_MODE"
    echo ""

    # 检查 WSL2 环境
    check_wsl2

    # 检查前置条件
    check_prerequisites

    # 确认执行
    print_warning "此脚本将修改存储配置并创建 Kubernetes 资源"
    print_warning "请确保已备份重要数据"
    echo ""
    read -p "是否继续执行？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_step "操作已取消"
        exit 0
    fi

    # 执行各阶段
    prepare_windows_dirs
    test_hdd_performance
    create_storage_structure
    create_storage_classes
    create_tiered_pvcs
    verify_and_test

    # 完成
    print_header "✅ Harbor 分层存储实施完成 (WSL2)"
    echo ""
    echo "下一步:"
    echo "  1. 查看 WSL2 方案文档：docs/deploy/HARBOR_TIERED_STORAGE_SOLUTION_WSL2.md"
    echo "  2. 更新 Harbor Helm 配置：参考方案文档 5.2 节"
    echo "  3. 执行功能测试：推送/拉取镜像"
    echo "  4. 配置监控告警：参考方案文档监控章节"
    echo ""
    echo "WSL2 特定说明:"
    echo "  - HDD 性能可能低于原生 Linux (9P 协议开销)"
    echo "  - 建议顺序读写 > 80MB/s"
    echo "  - 如遇性能问题，检查 .wslconfig 配置"
    echo ""
}

# 执行主流程
main "$@"
