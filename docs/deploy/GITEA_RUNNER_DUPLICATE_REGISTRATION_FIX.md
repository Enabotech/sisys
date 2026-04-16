# Gitea Runner 重复注册问题修复指南

## 🔍 问题描述

**症状**：每次系统重启后，Gitea Web 界面中出现 3 个新的离线 Runner，导致 Runner 列表中存在大量重复的离线 Runner。

**原因**：Runner 的注册信息（`.runner` 文件）存储在容器内，容器重启后丢失，导致每次启动都被当作新 Runner 注册。

## 📋 影响范围

| 项目 | 说明 |
|------|------|
| **受影响版本** | 使用 Deployment + ConfigMap 部署的 Gitea Runner |
| **受影响配置** | Runner 配置未持久化到 PVC |
| **表现** | 每次 Pod 重启增加 3 个离线 Runner（副本数=3） |

## 🔧 解决方案

### 方案概述

使用 **StatefulSet** 替代 **Deployment**，配合 **PersistentVolumeClaim (PVC)** 持久化 Runner 注册信息。

### 关键变更

| 变更项 | Deployment 配置 | StatefulSet 配置 |
|--------|----------------|-----------------|
| **资源类型** | Deployment | StatefulSet |
| **Pod 名称** | gitea-runner-xxxxx (随机) | gitea-runner-0,1,2 (固定) |
| **存储** | ConfigMap (只读) | PVC (可读写，持久化) |
| **注册信息** | 容器内，重启丢失 | PVC 中，重启保留 |
| **IP 地址** | 每次变化 | 相对稳定 |

### 架构对比

**Deployment (有问题)**:
```
┌─────────────────────┐
│  Deployment         │
│  replicas: 3        │
│                     │
│  ┌───────────────┐  │
│  │ Pod: random   │  │  ← Pod 名称随机
│  │ ConfigMap RO  │  │  ← ConfigMap 只读
│  │ .runner 丢失  │  │  ← 重启后注册信息丢失
│  └───────────────┘  │
└─────────────────────┘
```

**StatefulSet (修复后)**:
```
┌─────────────────────┐
│  StatefulSet        │
│  replicas: 3        │
│                     │
│  ┌───────────────┐  │
│  │ pod-0         │──┼──→ PVC-0 (1Gi)  ← 持久化 .runner
│  └───────────────┘  │
│  ┌───────────────┐  │
│  │ pod-1         │──┼──→ PVC-1 (1Gi)  ← 持久化 .runner
│  └───────────────┘  │
│  ┌───────────────┐  │
│  │ pod-2         │──┼──→ PVC-2 (1Gi)  ← 持久化 .runner
│  └───────────────┘  │
└─────────────────────┘
```

## 📦 部署文件

### 1. PVC 配置

文件：`deploy/kubernetes/gitea-runner/gitea-runner-pvc.yaml`

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: gitea-runner-data-0
  namespace: gitea-actions
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: local-path
---
# gitea-runner-data-1, gitea-runner-data-2 (共 3 个)
```

### 2. StatefulSet 配置

文件：`deploy/kubernetes/gitea-runner/gitea-actions-complete.yaml`

关键配置：
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: gitea-runner
  namespace: gitea-actions
spec:
  replicas: 3
  serviceName: gitea-runner

  volumeClaimTemplates:
    - metadata:
        name: runner-data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 1Gi
        storageClassName: local-path

  template:
    spec:
      containers:
        - name: runner
          image: docker.io/gitea/act_runner:0.3.0
          volumeMounts:
            - name: runner-data
              mountPath: /root/.config/act_runner
              subPath: act_runner
```

### 3. 清理和部署脚本

文件：`scripts/deployment/gitea-runner/fix-duplicate-registration.sh`

功能：
- 清理旧 Deployment
- 清理离线 Runner
- 清理旧 PVC
- 部署 StatefulSet 和新 PVC
- 验证 Runner 注册

## 🚀 部署步骤

### 前置条件

1. K3s 集群运行正常
2. Kubectl 已配置
3. Gitea 已部署并可访问
4. 有 Gitea 管理员权限

### 步骤 1：备份当前配置

```bash
# 备份当前 Deployment 配置
kubectl get deployment gitea-runner -n gitea-actions -o yaml > deployment-backup.yaml

# 导出当前 Runner 列表（手动截图或记录）
# Gitea 管理页面 → 设置 → Actions → 截图保存
```

### 步骤 2：运行修复脚本

```bash
cd /mnt/g/ai/sisys
./scripts/deployment/gitea-runner/fix-duplicate-registration.sh
```

脚本会自动：
1. 删除旧 Deployment
2. 清理 Gitea 中的离线 Runner
3. 删除旧 PVC
4. 创建新 PVC (3 个)
5. 部署 StatefulSet
6. 等待 Pod 启动
7. 验证 Runner 注册

### 步骤 3：验证部署

```bash
# 检查 StatefulSet 状态
kubectl get statefulset gitea-runner -n gitea-actions

# 检查 Pod 状态
kubectl get pods -n gitea-actions -l app=gitea-runner

# 检查 PVC 状态
kubectl get pvc -n gitea-actions -l app=gitea-runner

# 检查 Pod 日志
kubectl logs -n gitea-actions gitea-runner-0 --tail=50
```

### 步骤 4：验证 Runner 注册

1. 访问 Gitea 管理页面
2. 进入 **设置 → Actions**
3. 确认只有 3 个 Runner，名称为：
   - `gitea-runner-0`
   - `gitea-runner-1`
   - `gitea-runner-2`
4. 状态应为 **空闲** 或 **忙碌**

### 步骤 5：测试持久化

```bash
# 重启一个 Pod
kubectl delete pod gitea-runner-0 -n gitea-actions

# 等待 Pod 重启
kubectl wait --for=condition=Ready pod/gitea-runner-0 -n gitea-actions --timeout=120s

# 验证 .runner 文件存在
kubectl exec -n gitea-actions gitea-runner-0 -- ls -la /root/.config/act_runner/.runner

# 检查 Gitea Web 界面，确认没有新增离线 Runner
```

## ✅ 验证清单

- [ ] StatefulSet 已部署 (`kubectl get statefulset`)
- [ ] 3 个 Pod 运行中 (`kubectl get pods`)
- [ ] 3 个 PVC 已绑定 (`kubectl get pvc`)
- [ ] Gitea 中只有 3 个 Runner（无离线重复）
- [ ] Pod 重启后 Runner 不重复注册
- [ ] .runner 文件存在于 PVC 中

## 🐛 故障排除

### 问题 1：PVC 无法绑定

**症状**：PVC 状态为 Pending

**原因**：StorageClass 不可用

**解决**：
```bash
# 检查 StorageClass
kubectl get storageclass

# 如果没有 local-path，使用其他可用 StorageClass
# 修改 PVC 配置中的 storageClassName
```

### 问题 2：Runner 无法注册

**症状**：Pod 运行但 Gitea 中无 Runner

**原因**：Token 无效或网络问题

**解决**：
```bash
# 检查 Token Secret
kubectl get secret gitea-runner-token -n gitea-actions

# 检查 Runner 日志
kubectl logs -n gitea-actions gitea-runner-0

# 验证 Gitea 可访问性
kubectl exec -n gitea-actions gitea-runner-0 -- curl http://gitea-http.gitea.svc.cluster.local:3000
```

### 问题 3：旧 Runner 未清理

**症状**：Gitea 中仍有离线 Runner

**原因**：脚本未成功清理

**解决**：
1. 手动清理：Gitea 管理页面 → 设置 → Actions → 删除离线 Runner
2. 或使用 Gitea API：
```bash
# 获取 Runner 列表
curl -H "Authorization: token <ADMIN_TOKEN>" \
  http://<GITEA_URL>/api/v1/admin/runners

# 删除离线 Runner
curl -X DELETE \
  -H "Authorization: token <ADMIN_TOKEN>" \
  http://<GITEA_URL>/api/v1/admin/runners/<RUNNER_ID>
```

### 问题 4：StatefulSet 部署失败

**症状**：StatefulSet 创建失败

**原因**：与现有资源冲突

**解决**：
```bash
# 彻底清理
kubectl delete deployment gitea-runner -n gitea-actions
kubectl delete statefulset gitea-runner -n gitea-actions
kubectl delete pvc -n gitea-actions -l app=gitea-runner

# 重新部署
kubectl apply -f deploy/kubernetes/gitea-runner/gitea-runner-pvc.yaml
kubectl apply -f deploy/kubernetes/gitea-runner/gitea-actions-complete.yaml
```

## 📊 预期效果

### 修复前

```
每次重启后：
- 新增 3 个离线 Runner
- Runner 列表持续增长
- 需要手动清理
```

### 修复后

```
每次重启后：
- Runner 复用原有注册
- 始终保持 3 个 Runner
- 无需手动清理
```

## 🔗 相关文档

- [Kubernetes StatefulSet 文档](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [Gitea Runner 文档](https://docs.gitea.com/usage/actions/runner)
- [Story 文件](./0-8-gitea-runner-configuration.md)

## 📝 变更记录

| 日期 | 变更内容 | 负责人 |
|------|---------|--------|
| 2026-03-20 | 初始修复方案 | Qwen Code |
| 2026-03-20 | 添加自动化脚本 | Qwen Code |
| 2026-03-20 | 添加测试用例 | Qwen Code |
