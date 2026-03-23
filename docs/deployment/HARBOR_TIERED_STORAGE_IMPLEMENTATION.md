# Harbor 分层存储实施细则 (WSL2 + Ubuntu 22.04)

**版本:** 1.0.0
**日期:** 2026-03-23
**环境:** WSL2 Ubuntu 22.04 + K3S 单节点
**存储:** SSD 500GB + HDD 10TB (/mnt/x/hddstorage)
**预计时间:** 2-3 小时
**风险等级:** 中 (需停机迁移)

---

## 📋 实施前检查清单

### 1. 环境验证 (10 分钟)

```bash
# 1.1 确认 WSL2 环境
echo "=== WSL2 环境检查 ==="
cat /proc/version | grep -i microsoft
uname -r

# 预期输出：包含 "microsoft" 或 "WSL"

# 1.2 确认 K3S 集群状态
echo "=== K3S 集群检查 ==="
kubectl cluster-info
kubectl get nodes

# 预期：K3S 单节点 Ready

# 1.3 确认 Harbor 运行状态
echo "=== Harbor 状态检查 ==="
kubectl get pods -n harbor
kubectl get pvc -n harbor

# 预期：所有 Pod Running，PVC Bound

# 1.4 确认 HDD 挂载点
echo "=== HDD 挂载检查 ==="
ls -la /mnt/x/hddstorage/
df -h /mnt/x/hddstorage/

# 预期：HDD 可访问，容量 ~10TB
```

**检查项:**
- [ ] WSL2 环境确认
- [ ] K3S 集群正常
- [ ] Harbor 运行正常
- [ ] HDD 挂载点可访问

---

### 2. 数据备份 (30 分钟) ⚠️ **关键步骤**

```bash
# 2.1 创建备份目录
BACKUP_DIR="/mnt/x/hddstorage/harbor/backup/pre_migration_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# 2.2 备份 Harbor 配置
echo "=== 备份 Harbor 配置 ==="
kubectl get deployment harbor-registry -n harbor -o yaml > "$BACKUP_DIR/harbor-registry-deployment.yaml"
kubectl get pvc -n harbor -o yaml > "$BACKUP_DIR/harbor-pvc.yaml"
kubectl get storageclass -o yaml > "$BACKUP_DIR/storageclass.yaml"

# 2.3 备份 Harbor 数据 (可选，推荐)
echo "=== 备份 Harbor 数据 ==="
# 停止 Harbor 写入
kubectl scale deployment harbor-registry -n harbor --replicas=0

# 等待 Pod 停止
kubectl wait --for=delete pod -l app=harbor-registry -n harbor --timeout=60s

# 备份 PV 数据 (如果使用本地存储)
if [ -d "/var/lib/rancher/k3s/storage/pvc-*harbor*" ]; then
    rsync -avz /var/lib/rancher/k3s/storage/pvc-*harbor*/ "$BACKUP_DIR/k3s-pv-data/"
fi

# 2.4 恢复 Harbor 运行
kubectl scale deployment harbor-registry -n harbor --replicas=1
kubectl wait --for=condition=ready pod -l app=harbor-registry -n harbor --timeout=300s

echo "备份完成：$BACKUP_DIR"
```

**检查项:**
- [ ] 配置备份完成
- [ ] 数据备份完成 (可选)
- [ ] Harbor 已恢复运行
- [ ] 备份目录已记录

---

### 3. 维护窗口申请

**通知模板:**
```
【维护通知】Harbor 分层存储实施

时间：YYYY-MM-DD HH:MM - HH:MM (预计 2-3 小时)
影响：Harbor 服务将暂停 30-60 分钟 (数据迁移期间)
范围：镜像推送/拉取功能暂时不可用

实施内容:
- Harbor Registry 存储迁移到 HDD
- 创建 SSD+HDD 分层存储架构
- 性能优化和监控配置

回滚方案:
- 如实施失败，30 分钟内恢复原配置
- 备份数据保留 7 天

联系人：[姓名/电话]
```

**检查项:**
- [ ] 维护窗口已申请
- [ ] 相关团队已通知
- [ ] 回滚方案已准备

---

## 🔧 实施步骤

### 阶段 1: Windows 宿主机准备 (15 分钟)

**1.1 创建存储目录 (Windows PowerShell 管理员)**

```powershell
# 以管理员身份运行 PowerShell

Write-Host "=== 创建 Harbor 分层存储目录 ===" -ForegroundColor Cyan

# 创建目录结构
$directories = @(
    "X:\hddstorage\harbor\warm",
    "X:\hddstorage\harbor\cold",
    "X:\hddstorage\harbor\backup",
    "X:\hddstorage\harbor\k3s-pv"
)

foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force
        Write-Host "✅ 创建：$dir" -ForegroundColor Green
    } else {
        Write-Host "⚠️  已存在：$dir" -ForegroundColor Yellow
    }
}

# 设置权限 (允许 WSL2 访问)
Write-Host "`n=== 设置 NTFS 权限 ===" -ForegroundColor Cyan
$acl = Get-Acl "X:\hddstorage\harbor"
$accessRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    "Everyone", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
$acl.AddAccessRule($accessRule)
Set-Acl "X:\hddstorage\harbor" $acl
Write-Host "✅ 权限设置完成" -ForegroundColor Green

# 验证目录
Write-Host "`n=== 验证目录结构 ===" -ForegroundColor Cyan
Get-ChildItem "X:\hddstorage\harbor" -Recurse -Depth 1 | Select-Object FullName

Write-Host "`n✅ Windows 宿主机准备完成" -ForegroundColor Green
```

**1.2 验证 WSL2 挂载**

```bash
# 在 WSL2 中验证
echo "=== 验证 WSL2 挂载 ==="
ls -la /mnt/x/hddstorage/harbor/

# 创建测试文件
TEST_FILE="/mnt/x/hddstorage/harbor/wsl2_test_$$"
echo "WSL2 HDD Test $(date)" > "$TEST_FILE"
cat "$TEST_FILE"
rm -f "$TEST_FILE"

echo "✅ WSL2 挂载验证通过"
```

**检查项:**
- [ ] Windows 目录创建完成
- [ ] NTFS 权限设置完成
- [ ] WSL2 挂载验证通过

---

### 阶段 2: HDD 性能测试 (15 分钟)

```bash
echo "=== HDD 性能基准测试 ==="

# 测试目录
TEST_DIR="/mnt/x/hddstorage/harbor/perf_test_$$"
mkdir -p "$TEST_DIR"

# 顺序写入测试 (100MB)
echo "1. 顺序写入测试 (100MB)..."
dd if=/dev/zero of="$TEST_DIR/test_100mb" bs=1M count=100 conv=fdatasync 2>&1 | tail -3

# 顺序读取测试
echo "2. 顺序读取测试 (100MB)..."
dd if="$TEST_DIR/test_100mb" of=/dev/null bs=1M 2>&1 | tail -3

# 随机写入测试 (4K)
echo "3. 随机写入测试 (4K, 1000 次)..."
dd if=/dev/zero of="$TEST_DIR/test_4k" bs=4K count=1000 conv=fdatasync 2>&1 | tail -3

# 随机读取测试 (4K)
echo "4. 随机读取测试 (4K, 1000 次)..."
dd if="$TEST_DIR/test_4k" of=/dev/null bs=4K 2>&1 | tail -3

# 清理
rm -rf "$TEST_DIR"

echo ""
echo "=== 性能评估 ==="
echo "WSL2 9P 参考标准:"
echo "  顺序读写：80-120 MB/s  ✅ 正常"
echo "  随机读写：0.5-2 MB/s   ✅ 正常"
echo "  低于 50 MB/s 需要优化配置"
```

**检查项:**
- [ ] 顺序读写 > 80 MB/s
- [ ] 随机读写 > 0.5 MB/s
- [ ] 性能测试结果已记录

---

### 阶段 3: 创建 StorageClass (10 分钟)

```bash
echo "=== 创建 StorageClass ==="

# SSD StorageClass
cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: local-path-ssd
provisioner: rancher.io/local-path
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
parameters:
  nodePath: /var/lib/rancher/k3s/storage
  storageType: ssd
EOF

# HDD StorageClass (WSL2)
cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: local-path-hdd
provisioner: rancher.io/local-path
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
parameters:
  nodePath: /mnt/x/hddstorage/harbor/k3s-pv
  storageType: hdd
EOF

# 验证
echo "=== 验证 StorageClass ==="
kubectl get storageclass

echo "✅ StorageClass 创建完成"
```

**检查项:**
- [ ] local-path-ssd 创建成功
- [ ] local-path-hdd 创建成功
- [ ] StorageClass 状态可用

---

### 阶段 4: 创建分层 PVC (15 分钟)

```bash
echo "=== 创建分层 PVC ==="

# 热数据 PVC (SSD, 50Gi)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: harbor-registry-hot
  namespace: harbor
  labels:
    app: harbor-registry
    tier: hot
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path-ssd
  resources:
    requests:
      storage: 50Gi
EOF

# 温数据 PVC (HDD, 2Ti)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: harbor-registry-warm
  namespace: harbor
  labels:
    app: harbor-registry
    tier: warm
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path-hdd
  resources:
    requests:
      storage: 2Ti
EOF

# 冷数据 PVC (HDD, 8Ti)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: harbor-registry-cold
  namespace: harbor
  labels:
    app: harbor-registry
    tier: cold
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path-hdd
  resources:
    requests:
      storage: 8Ti
EOF

# 验证 PVC 状态
echo "=== 等待 PVC 绑定 ==="
kubectl wait --for=condition=bound pvc/harbor-registry-hot -n harbor --timeout=120s
kubectl wait --for=condition=bound pvc/harbor-registry-warm -n harbor --timeout=120s
kubectl wait --for=condition=bound pvc/harbor-registry-cold -n harbor --timeout=120s

# 查看 PV 详情
echo "=== PVC 状态 ==="
kubectl get pvc -n harbor -l app=harbor-registry

echo "=== PV 详情 ==="
kubectl get pv | grep harbor

echo "✅ 分层 PVC 创建完成"
```

**检查项:**
- [ ] harbor-registry-hot Bound (50Gi SSD)
- [ ] harbor-registry-warm Bound (2Ti HDD)
- [ ] harbor-registry-cold Bound (8Ti HDD)
- [ ] PV 路径正确指向 HDD 挂载点

---

### 阶段 5: 停止 Harbor 服务 (5 分钟) ⚠️ **停机窗口开始**

```bash
echo "⚠️  开始停机迁移 - 停止 Harbor 服务"

# 记录开始时间
MIGRATION_START=$(date +%s)

# 停止 Harbor Registry
echo "1. 停止 Harbor Registry..."
kubectl scale deployment harbor-registry -n harbor --replicas=0

# 等待 Pod 完全停止
echo "2. 等待 Pod 停止..."
kubectl wait --for=delete pod -l app=harbor-registry -n harbor --timeout=120s

# 验证 Pod 已停止
echo "3. 验证 Pod 状态..."
kubectl get pods -n harbor -l app=harbor-registry

echo "✅ Harbor 服务已停止"
```

**检查项:**
- [ ] Harbor Registry Pod 已停止
- [ ] 无正在运行的 Registry 进程
- [ ] 记录停机时间

---

### 阶段 6: 数据迁移 (30-90 分钟) ⚠️ **关键步骤**

**6.1 创建迁移 Job**

```bash
echo "=== 创建数据迁移 Job ==="

cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: harbor-data-migration
  namespace: harbor
  labels:
    app: harbor-migration
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

echo "✅ 迁移 Job 已创建"
```

**6.2 监控迁移进度**

```bash
echo "=== 监控迁移进度 ==="

# 实时查看日志
kubectl logs -f job/harbor-data-migration -n harbor

# 或定期检查
# kubectl logs job/harbor-data-migration -n harbor | tail -20

# 等待完成
echo "等待迁移完成..."
kubectl wait --for=condition=complete job/harbor-data-migration -n harbor --timeout=7200s

# 检查 Job 状态
kubectl get job harbor-data-migration -n harbor
```

**6.3 验证数据完整性**

```bash
echo "=== 验证数据完整性 ==="

# 查看迁移统计
kubectl logs job/harbor-data-migration -n harbor | grep -E "Number of files|Total file size|Transferred file"

# 手动验证 (创建临时 Pod)
kubectl run -it --rm --restart=Never --image=alpine:latest -n harbor -- migrate-verify -- \
  sh -c "
  echo '=== 源数据 ==='
  ls -la /source/
  echo ''
  echo '=== 目标数据 ==='
  ls -la /dest/
  "
```

**检查项:**
- [ ] 迁移 Job 完成
- [ ] 数据完整性验证通过
- [ ] 记录迁移时间

---

### 阶段 7: 更新 Harbor 配置 (15 分钟)

**7.1 更新 Harbor Helm Values**

```bash
echo "=== 更新 Harbor 配置 ==="

# 创建新的 Values 文件
cat <<EOF > /tmp/harbor-values-tiered.yaml
registry:
  persistentVolumeClaim:
    registry: harbor-registry-hot
  # 添加温/冷数据挂载
  extraVolumes:
    - name: warm-storage
      persistentVolumeClaim:
        claimName: harbor-registry-warm
    - name: cold-storage
      persistentVolumeClaim:
        claimName: harbor-registry-cold
  extraVolumeMounts:
    - name: warm-storage
      mountPath: /storage/warm
    - name: cold-storage
      mountPath: /storage/cold

database:
  persistentVolumeClaim:
    size: 1Gi
    storageClass: local-path-ssd

redis:
  persistentVolumeClaim:
    size: 1Gi
    storageClass: local-path-ssd

trivy:
  persistentVolumeClaim:
    size: 5Gi
    storageClass: local-path-ssd
EOF

echo "✅ Harbor Values 已更新"
```

**7.2 应用配置**

```bash
# 如果使用 Helm 部署
echo "=== 应用 Helm 配置 ==="
helm upgrade harbor harbor/harbor \
  -n harbor \
  -f /tmp/harbor-values-tiered.yaml \
  --wait \
  --timeout 10m

# 或者手动更新 Deployment
echo "=== 手动更新 Deployment (备选) ==="
kubectl set volume deployment/harbor-registry -n harbor \
  --add --name=warm-storage \
  --claim-name=harbor-registry-warm --mount-path=/storage/warm

kubectl set volume deployment/harbor-registry -n harbor \
  --add --name=cold-storage \
  --claim-name=harbor-registry-cold --mount-path=/storage/cold
```

**检查项:**
- [ ] Helm 升级成功 / Deployment 更新成功
- [ ] 新配置已应用
- [ ] 温/冷数据挂载点正确

---

### 阶段 8: 启动 Harbor 服务 (10 分钟)

```bash
echo "=== 启动 Harbor 服务 ==="

# 恢复 Harbor Registry
kubectl scale deployment harbor-registry -n harbor --replicas=1

# 等待 Pod 就绪
echo "等待 Harbor Registry 就绪..."
kubectl wait --for=condition=ready pod -l app=harbor-registry -n harbor --timeout=300s

# 验证 Pod 状态
echo "=== Harbor Pod 状态 ==="
kubectl get pods -n harbor -l app=harbor-registry

# 验证服务可访问
echo "=== 验证服务访问 ==="
kubectl get svc -n harbor harbor-registry

echo "✅ Harbor 服务已启动"
```

**检查项:**
- [ ] Harbor Registry Pod Running
- [ ] 服务端口可访问
- [ ] 记录恢复时间

---

### 阶段 9: 功能验证 (20 分钟)

**9.1 推送测试**

```bash
echo "=== 镜像推送测试 ==="

# 登录 Harbor
docker login harbor.sisys.local -u admin -p [密码]

# 准备测试镜像
docker pull alpine:latest
docker tag alpine:latest harbor.sisys.local/sisys/test-tiered-storage:$(date +%Y%m%d_%H%M%S)

# 推送测试
echo "推送测试镜像..."
docker push harbor.sisys.local/sisys/test-tiered-storage:$(date +%Y%m%d_%H%M%S)

echo "✅ 推送测试通过"
```

**9.2 拉取测试**

```bash
echo "=== 镜像拉取测试 ==="

# 拉取测试
echo "拉取测试镜像..."
docker pull harbor.sisys.local/sisys/test-tiered-storage:$(date +%Y%m%d_%H%M%S)

echo "✅ 拉取测试通过"
```

**9.3 存储验证**

```bash
echo "=== 存储使用验证 ==="

# 查看新镜像存储位置
kubectl exec -it deployment/harbor-registry -n harbor -- \
  sh -c "ls -lh /storage/docker/registry/v2/repositories/sisys/test-tiered-storage/"

# 查看 SSD 使用
echo "SSD 使用:"
df -h /var/lib/rancher/k3s

# 查看 HDD 使用
echo "HDD 使用:"
df -h /mnt/x/hddstorage

echo "✅ 存储验证通过"
```

**检查项:**
- [ ] 推送测试通过
- [ ] 拉取测试通过
- [ ] 存储位置正确
- [ ] SSD/HDD 使用正常

---

### 阶段 10: 监控配置 (15 分钟)

**10.1 创建监控 ConfigMap**

```bash
echo "=== 配置监控脚本 ==="

cat <<'EOF' | kubectl create configmap harbor-storage-monitor -n harbor --from-file=monitor.sh=/dev/stdin --dry-run=client -o yaml | kubectl apply -f -
#!/bin/bash
# Harbor 存储监控脚本

LOG_FILE="/var/log/harbor/storage-monitor.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 检查 SSD 使用率
SSD_USAGE=$(df /var/lib/rancher/k3s | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$SSD_USAGE" -gt 80 ]; then
    log "⚠️  WARNING: SSD 使用率 ${SSD_USAGE}%"
fi

# 检查 HDD 使用率
HDD_USAGE=$(df /mnt/x/hddstorage | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$HDD_USAGE" -gt 80 ]; then
    log "⚠️  WARNING: HDD 使用率 ${HDD_USAGE}%"
fi

log "存储检查完成 - SSD: ${SSD_USAGE}%, HDD: ${HDD_USAGE}%"
EOF

echo "✅ 监控脚本已配置"
```

**10.2 创建 CronJob**

```bash
cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: CronJob
metadata:
  name: harbor-storage-monitor
  namespace: harbor
spec:
  schedule: "0 */6 * * *"  # 每 6 小时执行
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: monitor
            image: alpine:latest
            command: ["/bin/sh", "-c"]
            args:
              - |
                apk add --no-cache coreutils
                echo "=== Harbor 存储监控 ==="
                echo "SSD: $(df /var/lib/rancher/k3s | tail -1)"
                echo "HDD: $(df /mnt/x/hddstorage | tail -1)"
          restartPolicy: OnFailure
EOF

echo "✅ 监控 CronJob 已创建"
```

**检查项:**
- [ ] 监控脚本已部署
- [ ] CronJob 已创建
- [ ] 告警阈值已配置

---

## ✅ 实施完成检查

### 最终验证清单

```bash
echo "=== Harbor 分层存储实施 - 最终验证 ==="

# 1. StorageClass
echo "1. StorageClass:"
kubectl get storageclass | grep local-path

# 2. PVC 状态
echo "2. PVC 状态:"
kubectl get pvc -n harbor -l app=harbor-registry

# 3. Pod 状态
echo "3. Pod 状态:"
kubectl get pods -n harbor -l app=harbor-registry

# 4. 存储使用
echo "4. 存储使用:"
df -h /var/lib/rancher/k3s
df -h /mnt/x/hddstorage

# 5. 功能测试
echo "5. 功能测试:"
docker login harbor.sisys.local -u admin -p [密码] && echo "✅ 登录成功"

# 6. 监控配置
echo "6. 监控配置:"
kubectl get cronjob -n harbor harbor-storage-monitor

echo ""
echo "=========================================="
echo "✅ Harbor 分层存储实施完成!"
echo "=========================================="
echo ""
echo "存储架构:"
echo "  SSD (热数据): 50Gi"
echo "  HDD (温数据): 2Ti"
echo "  HDD (冷数据): 8Ti"
echo ""
echo "下一步:"
echo "  1. 查看监控仪表板"
echo "  2. 配置告警通知"
echo "  3. 更新运维文档"
```

---

## 🔄 回滚方案 (如需)

### 触发条件

- 数据迁移失败 > 10%
- Harbor 服务不可用 > 60 分钟
- 数据完整性验证失败

### 回滚步骤

```bash
echo "⚠️  开始回滚..."

# 1. 停止 Harbor
kubectl scale deployment harbor-registry -n harbor --replicas=0

# 2. 恢复备份数据
BACKUP_DIR="/mnt/x/hddstorage/harbor/backup/pre_migration_YYYYMMDD_HHMMSS"
rsync -avz "$BACKUP_DIR/k3s-pv-data/" /var/lib/rancher/k3s/storage/pvc-*harbor*/

# 3. 恢复原 PVC
kubectl delete pvc harbor-registry-hot harbor-registry-warm harbor-registry-cold -n harbor
kubectl apply -f "$BACKUP_DIR/harbor-pvc.yaml"

# 4. 恢复原配置
kubectl apply -f "$BACKUP_DIR/harbor-registry-deployment.yaml"

# 5. 重启 Harbor
kubectl scale deployment harbor-registry -n harbor --replicas=1

echo "✅ 回滚完成"
```

---

## 📊 实施时间估算

| 阶段 | 预计时间 | 实际时间 |
|------|---------|---------|
| 1. 环境验证 | 10 分钟 | |
| 2. 数据备份 | 30 分钟 | |
| 3. Windows 准备 | 15 分钟 | |
| 4. HDD 测试 | 15 分钟 | |
| 5. StorageClass | 10 分钟 | |
| 6. PVC 创建 | 15 分钟 | |
| 7. 停止服务 | 5 分钟 | |
| 8. 数据迁移 | 30-90 分钟 | |
| 9. 配置更新 | 15 分钟 | |
| 10. 启动服务 | 10 分钟 | |
| 11. 功能验证 | 20 分钟 | |
| 12. 监控配置 | 15 分钟 | |
| **总计** | **2.5-4 小时** | |

---

## 📞 应急联系

| 角色 | 联系人 | 电话 |
|------|--------|------|
| 实施负责人 | | |
| 技术支持 | | |
| 业务负责人 | | |

---

**实施文档:** [HARBOR_TIERED_STORAGE_SOLUTION.md](./HARBOR_TIERED_STORAGE_SOLUTION.md)
**快速参考:** [TIERED_STORAGE_QUICKREF_WSL2.md](./TIERED_STORAGE_QUICKREF_WSL2.md)
**脚本位置:** `./scripts/storage/implement-tiered-storage-wsl2.sh`

**最后更新:** 2026-03-23
