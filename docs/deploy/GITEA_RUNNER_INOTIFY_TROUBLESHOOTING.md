# Gitea Act Runner Inotify 限制问题定位与解决指南

## 问题描述

### 典型错误信息

在 Kubernetes 环境中部署 Gitea Act Runner (Docker-in-Docker 模式) 时，Pod 日志可能出现以下错误：

```
Error: too many open files
Failed to create fsnotify watcher: too many open files
failed to initialize builder: too many open files
```

### 影响范围

| 环境 | 影响 |
|------|------|
| **Kubernetes** | Pod 无法正常启动或运行时频繁崩溃 |
| **Docker** | Runner 容器启动失败 |
| **物理机/虚拟机** | Act Runner 无法创建 watcher |

---

## 根因分析

### 1. Linux Inotify 机制简介

Inotify (inode notify) 是 Linux 内核提供的一种文件系统的通知机制，用于监控文件系统的变化。

### 2. 核心内核参数

| 参数 | 默认值 | 说明 | 消耗场景 |
|------|--------|------|----------|
| `fs.inotify.max_user_instances` | 128 | 单个用户（UID）可创建的 inotify 实例上限 | 每个监控实例占用 1 个单位 |
| `fs.inotify.max_user_watches` | 524288 | 单个用户可监控的文件总数 | 每个被监控文件占用 1 个单位 |
| `fs.inotify.max_queued_events` | 16384 | 队列中最大事件数 | 溢出后丢弃事件 |

### 3. 问题成因

在 CI/CD 环境中，以下组件会消耗 inotify 实例：

```
┌─────────────────────────────────────────────────────────────────┐
│                    宿主机节点                                     │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │  Docker dind   │  │  其他容器     │  │  Host 进程    │       │
│  │  (高占用)      │  │  (中占用)     │  │  (低占用)     │       │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘       │
│          │                  │                  │                │
│          └──────────────────┼──────────────────┘                │
│                             │                                   │
│                    max_user_instances=128                       │
│                             │                                   │
│          ┌──────────────────▼──────────────────┐                │
│          │        Gitea Runner Pod             │                │
│          │  ┌─────────────────────────────────┐│                │
│          │  │  act_runner                     ││                │
│          │  │  - 文件监控                     ││                │
│          │  │  - Docker API 监控              ││                │
│          │  │  - 构建日志实时推送             ││                │
│          │  └─────────────────────────────────┘│                │
│          └──────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────────┘
```

**128 个实例的消耗分布估算**：

| 来源 | 消耗实例数 | 说明 |
|------|-----------|------|
| Docker daemon (dind) | ~50-80 | Docker 容器生命周期监控 |
| Docker buildx | ~10-20 | 镜像构建层监控 |
| 构建任务 watcher | ~5-15/任务 | 并行构建时累加 |
| Runner 自身 | ~10-20 | 日志、配置文件监控 |
| **总计** | **75-135+** | 极易超过 128 上限 |

---

## 问题诊断

### 1. 快速诊断命令

```bash
# 检查当前节点的实例限制
cat /proc/sys/fs/inotify/max_user_instances

# 检查当前已使用的实例数量
find /proc/*/fd -lname anon_inode:inotify 2>/dev/null | wc -l

# 查看每个进程占用的实例
find /proc/*/fd -lname anon_inode:inotify 2>/dev/null | \
  sed 's|/proc/\([0-9]*\)/.*|echo "\1: $(cat /proc/\1/comm 2>/dev/null)"|' | \
  bash | sort | uniq -c | sort -rn

# 在 Pod 内检查
kubectl exec -n <namespace> <runner-pod> -c runner -- \
  cat /proc/sys/fs/inotify/max_user_instances
```

### 2. 症状对照表

| 症状 | 可能的根因 | 排查命令 |
|------|-----------|----------|
| Runner 启动即失败 | max_user_instances 过低 | `cat /proc/sys/fs/inotify/max_user_instances` |
| 并行构建时偶发失败 | 实例数不足 | 增加并行度观察 |
| Docker 命令超时 | Docker dind 实例耗尽 | 检查 dind 容器日志 |
| 特定 workflow 失败 | 该任务创建过多 watcher | 代码审查 |

### 3. 监控脚本

创建节点级监控脚本 `/opt/scripts/check-inotify.sh`：

```bash
#!/bin/bash
# check-inotify.sh - Inotify 资源监控脚本

INSTANCES_LIMIT=$(cat /proc/sys/fs/inotify/max_user_instances)
INSTANCES_USED=$(find /proc/*/fd -lname anon_inode:inotify 2>/dev/null | wc -l)
WATCHES_LIMIT=$(cat /proc/sys/fs/inotify/max_user_watches)
WATCHES_USED=$(find /proc/*/fd -lname anon_inode:inotify 2>/dev/null | wc -l)

echo "=== Inotify Resource Status ==="
echo "Instances: ${INSTANCES_USED}/${INSTANCES_LIMIT} ($(echo "scale=2; ${INSTANCES_USED}*100/${INSTANCES_LIMIT}" | bc)%)"
echo "Watches: ${WATCHES_USED}/${WATCHES_LIMIT} ($(echo "scale=2; ${WATCHES_USED}*100/${WATCHES_LIMIT}" | bc)%)"

if [ ${INSTANCES_USED} -gt $((INSTANCES_LIMIT * 80 / 100)) ]; then
    echo "WARNING: Instances usage > 80%"
fi
```

---

## 解决方案

### 方案一：节点内核参数调整（推荐）

#### 适用场景

- 有节点 SSH 访问权限
- 需要长期稳定运行
- 多租户环境统一管理

#### 操作步骤

**1. 临时调整（立即生效，重启失效）**

```bash
# 调整实例数限制
sudo sysctl -w fs.inotify.max_user_instances=8192

# 同步调整 watches 限制（推荐）
sudo sysctl -w fs.inotify.max_user_watches=1048576

# 调整事件队列（可选）
sudo sysctl -w fs.inotify.max_queued_events=65536
```

**2. 持久化配置**

```bash
# 方法 A：写入 sysctl.conf
echo "fs.inotify.max_user_instances=8192" | sudo tee -a /etc/sysctl.conf
echo "fs.inotify.max_user_watches=1048576" | sudo tee -a /etc/sysctl.conf

# 方法 B：独立配置文件（推荐）
sudo tee /etc/sysctl.d/99-inotify.conf <<'EOF'
# Inotify settings for CI/CD workloads
fs.inotify.max_user_instances=8192
fs.inotify.max_user_watches=1048576
fs.inotify.max_queued_events=65536
EOF

# 方法 C：Ansible/Puppet 配置管理
```

**3. 验证配置**

```bash
# 重新加载配置
sudo sysctl -p /etc/sysctl.d/99-inotify.conf

# 验证
sysctl fs.inotify.max_user_instances
# 应输出：fs.inotify.max_user_instances = 8192
```

**4. 重建 Pod**

```bash
# 删除 Runner Pod 使其重新加载配置
kubectl delete pod -n <namespace> <runner-pod> --grace-period=30

# 或重启整个 Deployment
kubectl rollout restart deployment -n <namespace> <runner-deployment>
```

### 方案二：Kubernetes DaemonSet 批量调整

#### 适用场景

- 无节点 SSH 权限
- 需要自动化配置所有节点
- 云托管 Kubernetes 环境

#### 部署清单

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: inotify-sysctl
  namespace: kube-system
  labels:
    app: inotify-sysctl
spec:
  selector:
    matchLabels:
      app: inotify-sysctl
  template:
    metadata:
      labels:
        app: inotify-sysctl
    spec:
      hostPID: true
      hostNetwork: true
      containers:
      - name: sysctl
        image: alpine:3.19
        command:
        - /bin/sh
        - -c
        - |
          # 设置内核参数
          sysctl -w fs.inotify.max_user_instances=8192
          sysctl -w fs.inotify.max_user_watches=1048576

          # 持久化配置
          mkdir -p /host/etc/sysctl.d
          cat > /host/etc/sysctl.d/99-inotify.conf <<'EOF'
          # Inotify settings for CI/CD workloads
          fs.inotify.max_user_instances=8192
          fs.inotify.max_user_watches=1048576
          EOF

          # 防止容器退出（守护进程模式）
          tail -f /dev/null
        securityContext:
          privileged: true
        volumeMounts:
        - name: sysctl-conf
          mountPath: /host/etc/sysctl.d
      volumes:
      - name: sysctl-conf
        hostPath:
          path: /etc/sysctl.d
          type: DirectoryOrCreate
      tolerations:
      - operator: Exists
```

#### 部署验证

```bash
# 部署 DaemonSet
kubectl apply -f inotify-daemonset.yaml

# 检查 Pod 运行状态
kubectl get pods -n kube-system -l app=inotify-sysctl

# 验证所有节点配置
for node in $(kubectl get nodes -o name); do
  echo "=== $node ==="
  kubectl debug node/$node -it --image=alpine -- cat /proc/sys/fs/inotify/max_user_instances
done
```

### 方案三：Pod 层面限制（临时缓解）

#### 适用场景

- 紧急临时修复
- 无法修改节点配置
- 只想影响特定 Pod

#### 部署清单

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gitea-runner
  namespace: gitea
spec:
  securityContext:
    sysctls:
    - name: fs.inotify.max_user_instances
      value: "8192"
      # 注意：这需要 Pod 使用 hostNetwork 并具备特权
```

> **警告**：Pod 级别的 sysctls 需要 Kubernetes 启用相关特性，且某些集群策略可能禁止。

### 方案四：Docker 层面优化

#### 适用场景

- 非 Kubernetes 环境
- Docker Compose 部署
- 减少 inotify 消耗

#### 优化 Docker daemon 配置

```json
{
  "storage-driver": "overlay2",
  "live-restore": true,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

#### 减少 Runner 日志输出

减少日志输出可以降低 watcher 数量：

```yaml
# act_runner 配置
---
log:
  level: warn
  format: json
  # 减少不必要的文件监控
```

---

## 验证与测试

### 1. 基础验证

```bash
# 检查节点参数
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.capacity.pods}{"\n"}'

# 在 Pod 内验证
kubectl exec -n gitea gitea-runner-0 -c runner -- \
  sh -c 'cat /proc/sys/fs/inotify/max_user_instances && echo ""'

# 期望输出：8192 或更高
```

### 2. 压测验证

创建压力测试脚本 `/opt/scripts/inotify-stress.sh`：

```bash
#!/bin/bash
# inotify-stress.sh - 模拟高并发场景

echo "Starting inotify stress test..."
echo "Target: $(cat /proc/sys/fs/inotify/max_user_instances) instances allowed"

SUCCESS=0
FAIL=0

for i in $(seq 1 1000); do
  # 创建 inotify 实例
  if inotifywait -t 1 -e modify /tmp/testfile 2>/dev/null; then
    ((SUCCESS++))
  else
    ((FAIL++))
  fi

  # 每 100 次报告一次
  if [ $((i % 100)) -eq 0 ]; then
    echo "Progress: $i/1000 | Success: $SUCCESS | Fail: $FAIL"
  fi
done

echo "=== Stress Test Results ==="
echo "Success: $SUCCESS"
echo "Fail: $FAIL"
echo "Success Rate: $(echo "scale=2; $SUCCESS*100/1000" | bc)%"
```

### 3. Runner 功能验证

```bash
# 检查 Runner 状态
kubectl exec -n gitea gitea-runner-0 -c runner -- act_runner status

# 检查 Runner 日志无错误
kubectl logs -n gitea gitea-runner-0 -c runner --tail=100 | grep -i "error\|fail\|warn"

# 触发测试 workflow
kubectl create job -n gitea test-runner --from=cronjob/ci-pipeline --dry-run=client -o yaml | \
  kubectl apply -f -
```

---

## 预防措施

### 1. 节点初始化配置

在节点加入集群前，在初始化脚本中设置：

```bash
# /etc/sysctl.d/99-inotify.conf
cat > /etc/sysctl.d/99-inotify.conf <<'EOF'
# Kernel parameters for CI/CD workloads
fs.inotify.max_user_instances=8192
fs.inotify.max_user_watches=1048576
fs.inotify.max_queued_events=65536
EOF

sysctl -p /etc/sysctl.d/99-inotify.conf
```

### 2. 监控告警

配置 Prometheus 告警规则：

```yaml
groups:
- name: inotify
  rules:
  - alert: InotifyInstancesHigh
    expr: |
      (count by (instance) (find /proc/*/fd -lname anon_inode:inotify 2>/dev/null))
      / on(instance) group_left()
      (cat /proc/sys/fs/inotify/max_user_instances)
      > 0.8
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Inotify instances usage > 80%"
      description: "Node {{ $labels.instance }} inotify usage is high"

  - alert: InotifyInstancesCritical
    expr: |
      (count by (instance) (find /proc/*/fd -lname anon_inode:inotify 2>/dev/null))
      / on(instance) group_left()
      (cat /proc/sys/fs/inotify/max_user_instances)
      > 0.95
    for: 1m
    labels:
      severity: critical
```

### 3. 容量规划

| 集群规模 | 建议 max_user_instances | 建议 max_user_watches |
|----------|------------------------|----------------------|
| 单节点 / Dev | 8192 | 524288 |
| 小型集群 (3-5 节点) | 8192 | 1048576 |
| 中型集群 (10+ 节点) | 16384 | 1048576 |
| 大型集群 (50+ 节点) | 32768 | 2097152 |

### 4. 最佳实践

1. **隔离 Docker dind**：使用独立节点运行 CI/CD 工作负载
2. **限制并行度**：在 Runner 配置中限制同时运行的 job 数量
3. **日志优化**：使用结构化日志，减少文件监控开销
4. **定期巡检**：建立周期性检查机制

---

## 常见问题

### Q1: 为什么调整后仍然失败？

**检查项**：
- Pod 是否重建？（配置需要 Pod 重启才能生效）
- 是否所有节点都已调整？（使用 DaemonSet 确保覆盖）
- 是否有其他限制？（ulimit、cgroup 等）

```bash
# 检查容器 ulimit
kubectl exec -it <pod> -c runner -- ulimit -n

# 检查 cgroup 限制
cat /sys/fs/cgroup/pids/pids.max
```

### Q2: 云服务商不支持修改节点参数怎么办？

| 云服务商 | 解决方案 |
|----------|----------|
| AWS EKS | 使用节点用户数据添加 sysctl 命令 |
| Azure AKS | 通过节点池扩展设置 |
| GCP GKE | 使用节点污点 + DaemonSet |
| 阿里云 ACK | 通过节点池配置 |

### Q3: 能否在不重启 Pod 的情况下生效？

**不能**。内核参数 `max_user_instances` 是系统级限制，Pod 启动时读取，无法动态生效。必须重建 Pod。

### Q4: 设置过高有什么风险？

过高的值会占用内核内存。每个 inotify 实例占用少量内核内存（约几十字节），8192 个实例约占用 < 1MB，风险较低。

---

## 参考资料

| 资料 | 链接 |
|------|------|
| Linux Kernel inotify 文档 | [内核文档](https://www.kernel.org/doc/Documentation/filesystems/inotify.txt) |
| Gitea Actions 官方文档 | [docs.gitea.com/usage/actions](https://docs.gitea.com/usage/actions) |
| Gitea Act Runner 项目 | [gitea.com/gitea/act_runner](https://gitea.com/gitea/act_runner) |
| Docker 存储优化 | [docs.docker.com/engine/optimize](https://docs.docker.com/engine/optimize/) |
| Kubernetes Sysctl 文档 | [kubernetes.io/docs/concepts/management/sysctl](https://kubernetes.io/docs/concepts/management/sysctl/) |

---

## 变更记录

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|----------|
| 1.0.0 | 2026-04-18 | Claude | 初始版本 |

---

**宗师点评**：此问题本质上是传统服务器运维经验在云原生环境下的延伸。内核参数的调整虽然涉及节点层面，但通过 DaemonSet 等机制完全可以实现自动化运维。关键在于建立完善的监控体系，在问题发生前就能预警。记住：**优秀的运维不是在故障发生后救火，而是让故障根本不发生**。
