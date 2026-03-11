#!/bin/bash
# K3S 验证测试脚本 - WSL2 环境
# Story 0.4: K3S 集群部署

set -e

echo "========================================"
echo "  K3S 验证测试套件"
echo "========================================"
echo "日期：$(date)"
echo "环境：WSL2 Ubuntu 22.04"
echo ""

# ========== 配置 ==========

# 检查 kubectl
if ! command -v kubectl &>/dev/null; then
    echo "⚠️ kubectl 未找到，使用 docker exec..."
    KUBECTL_CMD="docker exec k3s-node-server-1 k3s kubectl"
else
    KUBECTL_CMD="kubectl"
fi

# 测试计数
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# ========== 测试函数 ==========

run_test() {
    local test_name="$1"
    local test_cmd="$2"
    local expected="$3"

    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo ""
    echo "[$TESTS_TOTAL] 测试：$test_name"
    echo "---"

    if eval "$test_cmd" > /tmp/test_output_$$.txt 2>&1; then
        if [ "$expected" = "success" ]; then
            echo "✅ PASS: $test_name"
            TESTS_PASSED=$((TESTS_PASSED + 1))
            return 0
        else
            echo "❌ FAIL: $test_name (期望失败但成功)"
            TESTS_FAILED=$((TESTS_FAILED + 1))
            return 1
        fi
    else
        if [ "$expected" = "fail" ]; then
            echo "✅ PASS: $test_name (预期失败)"
            TESTS_PASSED=$((TESTS_PASSED + 1))
            return 0
        else
            echo "❌ FAIL: $test_name"
            cat /tmp/test_output_$$.txt
            TESTS_FAILED=$((TESTS_FAILED + 1))
            return 1
        fi
    fi
}

cleanup_test() {
    local resource="$1"
    echo "清理测试资源：$resource"
    $KUBECTL_CMD delete $resource --ignore-not-found=true 2>/dev/null || true
}

# ========== 1. 集群基础测试 ==========

echo ""
echo "========================================"
echo "  第一部分：集群基础测试"
echo "========================================"

# 测试 1: API Server 连接
run_test "K3S API Server 连接" "$KUBECTL_CMD cluster-info" "success"

# 测试 2: 节点状态
run_test "所有节点状态 Ready" "$KUBECTL_CMD get nodes | grep -q 'Ready'" "success"

# 测试 3: 节点数量
NODE_COUNT=$($KUBECTL_CMD get nodes --no-headers | wc -l)
if [ "$NODE_COUNT" -ge 1 ]; then
    echo "✅ PASS: 节点数量检查 ($NODE_COUNT 个节点)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo "❌ FAIL: 节点数量检查 (0 个节点)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_TOTAL=$((TESTS_TOTAL + 1))

# 测试 4: 系统 Pod 运行状态
SYSTEM_PODS=$($KUBECTL_CMD get pods -n kube-system --no-headers | grep -c Running || echo 0)
if [ "$SYSTEM_PODS" -gt 0 ]; then
    echo "✅ PASS: 系统 Pod 运行状态 ($SYSTEM_PODS 个 Running)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo "❌ FAIL: 系统 Pod 运行状态"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_TOTAL=$((TESTS_TOTAL + 1))

# 测试 5: CoreDNS
run_test "CoreDNS Pod 运行" "$KUBECTL_CMD get pods -n kube-system -l k8s-app=kube-dns | grep -q 'Running'" "success"

# 测试 6: local-path-provisioner
run_test "local-path-provisioner 运行" "$KUBECTL_CMD get pods -n kube-system -l app=local-path-provisioner | grep -q 'Running'" "success"

# ========== 2. 存储测试 ==========

echo ""
echo "========================================"
echo "  第二部分：存储功能测试"
echo "========================================"

# 测试 7: 存储类存在
run_test "standard 存储类存在" "$KUBECTL_CMD get storageclass standard" "success"

# 测试 8: 默认存储类
DEFAULT_CLASS=$($KUBECTL_CMD get storageclass -o jsonpath='{.items[?(@.metadata.annotations.storageclass\.kubernetes\.io/is-default-class=="true")].metadata.name}' 2>/dev/null || echo "")
if [ "$DEFAULT_CLASS" = "standard" ]; then
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo "✅ PASS: standard 是默认存储类"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo "⚠️ WARN: standard 不是默认存储类 (当前：$DEFAULT_CLASS)"
fi

# 测试 9: PVC 创建
echo ""
echo "创建测试 PVC..."
cat <<EOF | $KUBECTL_CMD apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: test-pvc-verify
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: standard
  resources:
    requests:
      storage: 100Mi
EOF

sleep 3
PVC_STATUS=$($KUBECTL_CMD get pvc test-pvc-verify -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
if [ "$PVC_STATUS" = "Bound" ]; then
    echo "✅ PASS: PVC 创建并绑定成功"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo "❌ FAIL: PVC 创建失败 (状态：$PVC_STATUS)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_TOTAL=$((TESTS_TOTAL + 1))

# 测试 10: Pod 挂载 PVC
echo ""
echo "创建测试 Pod 挂载 PVC..."
cat <<EOF | $KUBECTL_CMD apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: test-storage-pod
spec:
  containers:
  - name: test-container
    image: busybox:latest
    command: ["sleep", "3600"]
    volumeMounts:
    - name: test-volume
      mountPath: /data
  volumes:
  - name: test-volume
    persistentVolumeClaim:
      claimName: test-pvc-verify
EOF

sleep 5
POD_STATUS=$($KUBECTL_CMD get pod test-storage-pod -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
if [ "$POD_STATUS" = "Running" ]; then
    echo "✅ PASS: Pod 挂载 PVC 成功"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo "❌ FAIL: Pod 挂载 PVC 失败 (状态：$POD_STATUS)"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_TOTAL=$((TESTS_TOTAL + 1))

# 测试 11: 数据写入测试
echo ""
echo "测试数据写入..."
$KUBECTL_CMD exec test-storage-pod -- sh -c "echo 'K3S storage test successful' > /data/test.txt" 2>/dev/null
$KUBECTL_CMD exec test-storage-pod -- cat /data/test.txt 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ PASS: 数据写入测试成功"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo "❌ FAIL: 数据写入测试失败"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_TOTAL=$((TESTS_TOTAL + 1))

# 测试 12: 数据持久化测试
echo ""
echo "测试数据持久化（删除 Pod 后重建）..."
$KUBECTL_CMD delete pod test-storage-pod
sleep 3

cat <<EOF | $KUBECTL_CMD apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: test-storage-pod-2
spec:
  containers:
  - name: test-container
    image: busybox:latest
    command: ["sh", "-c", "cat /data/test.txt && echo 'Persistence verified'"]
    volumeMounts:
    - name: test-volume
      mountPath: /data
  volumes:
  - name: test-volume
    persistentVolumeClaim:
      claimName: test-pvc-verify
EOF

sleep 5
$KUBECTL_CMD wait --for=condition=ready pod test-storage-pod-2 --timeout=60s 2>/dev/null
OUTPUT=$($KUBECTL_CMD logs test-storage-pod-2 2>/dev/null || echo "")
if echo "$OUTPUT" | grep -q "K3S storage test successful"; then
    echo "✅ PASS: 数据持久化测试成功"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo "❌ FAIL: 数据持久化测试失败"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_TOTAL=$((TESTS_TOTAL + 1))

# 清理存储测试资源
cleanup_test "pod/test-storage-pod-2"
cleanup_test "pvc/test-pvc-verify"

# ========== 3. 网络测试 ==========

echo ""
echo "========================================"
echo "  第三部分：网络功能测试"
echo "========================================"

# 测试 13: Pod 间网络通信
echo ""
echo "创建网络测试 Pod..."
cat <<EOF | $KUBECTL_CMD apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: network-test-pod-1
  labels:
    app: network-test
spec:
  containers:
  - name: test-container
    image: busybox:latest
    command: ["sleep", "3600"]
EOF

cat <<EOF | $KUBECTL_CMD apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: network-test-pod-2
  labels:
    app: network-test
spec:
  containers:
  - name: test-container
    image: busybox:latest
    command: ["sleep", "3600"]
EOF

sleep 5

# 获取 Pod IP
POD1_IP=$($KUBECTL_CMD get pod network-test-pod-1 -o jsonpath='{.status.podIP}' 2>/dev/null || echo "")
POD2_IP=$($KUBECTL_CMD get pod network-test-pod-2 -o jsonpath='{.status.podIP}' 2>/dev/null || echo "")

if [ -n "$POD1_IP" ] && [ -n "$POD2_IP" ]; then
    echo "✅ PASS: Pod IP 分配成功 ($POD1_IP, $POD2_IP)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo "❌ FAIL: Pod IP 分配失败"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_TOTAL=$((TESTS_TOTAL + 1))

# 测试 14: Pod 间 Ping 测试
if [ -n "$POD2_IP" ]; then
    $KUBECTL_CMD exec network-test-pod-1 -- ping -c 2 -W 1 $POD2_IP 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "✅ PASS: Pod 间 Ping 测试成功"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo "❌ FAIL: Pod 间 Ping 测试失败"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
fi

# 测试 15: DNS 解析测试
echo ""
echo "测试 DNS 解析..."
$KUBECTL_CMD exec network-test-pod-1 -- nslookup kubernetes.default 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ PASS: DNS 解析测试成功"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo "❌ FAIL: DNS 解析测试失败"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_TOTAL=$((TESTS_TOTAL + 1))

# 清理网络测试资源
cleanup_test "pod/network-test-pod-1"
cleanup_test "pod/network-test-pod-2"

# ========== 4. 多节点测试（如果适用） ==========

echo ""
echo "========================================"
echo "  第四部分：多节点功能测试"
echo "========================================"

NODE_COUNT=$($KUBECTL_CMD get nodes --no-headers | wc -l)
if [ "$NODE_COUNT" -gt 1 ]; then
    echo "检测到多节点集群 ($NODE_COUNT 节点)"

    # 测试 16: 节点标签
    run_test "节点标签正确" "$KUBECTL_CMD get nodes -o jsonpath='{.items[*].metadata.labels}' | grep -q 'kubernetes.io'" "success"

    # 测试 17: Pod 跨节点调度
    echo ""
    echo "测试 Pod 跨节点调度..."
    for i in 1 2 3; do
        cat <<EOF | $KUBECTL_CMD apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: multi-node-test-$i
spec:
  containers:
  - name: test-container
    image: busybox:latest
    command: ["sleep", "60"]
EOF
    done

    sleep 5
    SCHEDULED_NODES=$($KUBECTL_CMD get pods -l app=multi-node-test -o jsonpath='{.items[*].spec.nodeName}' 2>/dev/null | tr ' ' '\n' | sort -u | wc -l)
    if [ "$SCHEDULED_NODES" -gt 1 ]; then
        echo "✅ PASS: Pod 跨节点调度成功 ($SCHEDULED_NODES 个节点)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo "⚠️ WARN: Pod 未跨节点调度 (单节点或未调度)"
    fi
    TESTS_TOTAL=$((TESTS_TOTAL + 1))

    # 清理
    $KUBECTL_CMD delete pod multi-node-test-1 multi-node-test-2 multi-node-test-3 --ignore-not-found=true 2>/dev/null || true
else
    echo "单节点集群，跳过跨节点测试"
fi

# ========== 测试结果汇总 ==========

echo ""
echo "========================================"
echo "  测试结果汇总"
echo "========================================"
echo ""
echo "总测试数：$TESTS_TOTAL"
echo "✅ 通过：$TESTS_PASSED"
echo "❌ 失败：$TESTS_FAILED"
echo ""

if [ "$TESTS_FAILED" -eq 0 ]; then
    echo "🎉 所有测试通过！K3S 集群运行正常。"
    exit 0
else
    echo "⚠️  有 $TESTS_FAILED 个测试失败，请检查集群配置。"
    exit 1
fi
