#!/bin/bash

# =============================================================================
# WSL2 环境检测与配置脚本
# =============================================================================
# 用途：检测 WSL2 环境状态、性能配置和 Harbor 存储优化准备情况
# 关联方案：Harbor 分层存储优化 (WSL2 + SSD + HDD)
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

print_header "WSL2 环境检测"

# =============================================================================
# 1. WSL2 环境检测
# =============================================================================
print_step "步骤 1: WSL2 环境检测..."

echo ""
echo "=== WSL 版本信息 ==="
if command -v wsl &> /dev/null; then
    wsl --list --verbose 2>/dev/null || echo "无法获取 WSL 列表"
fi

echo ""
echo "=== /proc/version ==="
cat /proc/version

if grep -qi microsoft /proc/version || grep -qi wsl /proc/version; then
    print_success "检测到 WSL2 环境"
else
    print_warning "未在 WSL2 环境中运行"
fi

# =============================================================================
# 2. 存储设备检测
# =============================================================================
print_step "步骤 2: 存储设备检测..."

echo ""
echo "=== 文件系统挂载 ==="
df -h | grep -E "Filesystem|/dev|/mnt"

echo ""
echo "=== SSD 存储 (K3S) ==="
if [ -d "/var/lib/rancher/k3s" ]; then
    df -h /var/lib/rancher/k3s
    echo ""
    echo "可用空间:"
    df -h /var/lib/rancher/k3s | tail -1 | awk '{print $4}'
else
    print_warning "K3S 目录不存在"
fi

echo ""
echo "=== HDD 存储 (WSL2 挂载) ==="
for mount in /mnt/x /mnt/hddstorage /mnt/data; do
    if [ -d "$mount" ]; then
        echo "挂载点：$mount"
        df -h "$mount" 2>/dev/null || echo "无法获取信息"
        echo ""
    fi
done

# =============================================================================
# 3. HDD 挂载点检测
# =============================================================================
print_step "步骤 3: HDD 挂载点检测..."

HDD_MOUNT=""
for mount in /mnt/x/hddstorage /mnt/hddstorage /mnt/data/harbor; do
    if [ -d "$mount" ]; then
        HDD_MOUNT="$mount"
        print_success "找到 HDD 挂载点：$mount"
        break
    fi
done

if [ -n "$HDD_MOUNT" ]; then
    echo ""
    echo "=== HDD 目录结构 ==="
    ls -la "$HDD_MOUNT" 2>/dev/null | head -10

    echo ""
    echo "=== HDD 可写性测试 ==="
    TEST_FILE="$HDD_MOUNT/wsl2_test_$$"
    if echo "WSL2 Test" > "$TEST_FILE" 2>/dev/null; then
        print_success "HDD 可写"
        rm -f "$TEST_FILE"
    else
        print_error "HDD 不可写"
    fi
else
    print_warning "未找到 HDD 挂载点"
    print_info "请在 Windows 宿主机创建目录并重启 WSL"
fi

# =============================================================================
# 4. 性能基准测试
# =============================================================================
print_step "步骤 4: 性能基准测试..."

if [ -n "$HDD_MOUNT" ]; then
    echo ""
    echo "=== HDD 顺序写入测试 (10MB) ==="
    TEST_FILE="$HDD_MOUNT/perf_test_$$"
    dd if=/dev/zero of="$TEST_FILE" bs=1M count=10 conv=fdatasync 2>&1 | tail -3
    rm -f "$TEST_FILE"

    echo ""
    echo "=== HDD 顺序读取测试 (10MB) ==="
    TEST_FILE="$HDD_MOUNT/perf_test_$$"
    dd if=/dev/zero of="$TEST_FILE" bs=1M count=10 conv=fdatasync 2>&1 | tail -3
    dd if="$TEST_FILE" of=/dev/null bs=1M 2>&1 | tail -3
    rm -f "$TEST_FILE"

    echo ""
    print_info "WSL2 9P 性能参考:"
    echo "  顺序读写：80-120 MB/s  ✅ 正常"
    echo "  低于 50 MB/s 需要优化配置"
else
    print_warning "跳过性能测试 (HDD 挂载点不存在)"
fi

# =============================================================================
# 5. Kubernetes 状态检测
# =============================================================================
print_step "步骤 5: Kubernetes 状态检测..."

if command -v kubectl &> /dev/null; then
    echo ""
    echo "=== K3S 集群信息 ==="
    kubectl cluster-info 2>/dev/null | head -3

    echo ""
    echo "=== StorageClass ==="
    kubectl get storageclass 2>/dev/null || echo "未找到 StorageClass"

    echo ""
    echo "=== Harbor 命名空间 ==="
    kubectl get namespace harbor 2>/dev/null || echo "Harbor 命名空间不存在"

    echo ""
    echo "=== Harbor Pod 状态 ==="
    kubectl get pods -n harbor 2>/dev/null | head -10 || echo "无法获取 Pod 状态"
else
    print_warning "kubectl 未安装"
fi

# =============================================================================
# 6. WSL2 配置文件检测
# =============================================================================
print_step "步骤 6: WSL2 配置文件检测..."

echo ""
echo "=== /etc/wsl.conf ==="
if [ -f "/etc/wsl.conf" ]; then
    cat /etc/wsl.conf
else
    echo "文件不存在"
fi

echo ""
echo "=== Windows .wslconfig ==="
if [ -f "/mnt/c/Users/$USER/.wslconfig" ]; then
    cat "/mnt/c/Users/$USER/.wslconfig"
elif [ -f "/mnt/c/Users/Administrator/.wslconfig" ]; then
    cat "/mnt/c/Users/Administrator/.wslconfig"
else
    echo "文件不存在 (建议创建以优化性能)"
fi

# =============================================================================
# 7. 优化建议
# =============================================================================
print_header "优化建议"

echo ""
echo "=== WSL2 内存配置 (推荐) ==="
cat << 'EOF'
在 Windows 用户目录创建 C:\Users\<username>\.wslconfig:

[wsl2]
memory=16GB
swap=8GB
processors=4

然后执行:
  wsl --shutdown
  wsl
EOF

echo ""
echo "=== Harbor 存储优化 (推荐) ==="
cat << 'EOF'
1. 在 Windows 宿主机创建存储目录:
   PowerShell: New-Item -ItemType Directory -Path "X:\hddstorage\harbor" -Force

2. 运行 WSL2 实施脚本:
   ./scripts/storage/implement-tiered-storage-wsl2.sh

3. 查看完整方案:
   docs/deployment/HARBOR_TIERED_STORAGE_SOLUTION_WSL2.md
EOF

echo ""
print_info "详细配置指南参考：docs/deployment/HARBOR_TIERED_STORAGE_SOLUTION_WSL2.md"

# =============================================================================
# 总结
# =============================================================================
print_header "检测完成"

echo ""
echo "报告已生成在上方，请根据建议进行优化"
echo ""
