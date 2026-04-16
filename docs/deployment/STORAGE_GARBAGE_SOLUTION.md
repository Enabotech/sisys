# 存储垃圾解决方案

**创建日期:** 2026/04/16
**作者:** Claude (AI Assistant)
**状态:** 实施中

---

## 一、执行摘要

### 问题描述
gitea-runner-dind 在执行 CI/CD 构建任务时会产生大量 Docker 构建垃圾，包括：
- overlay2 层数据（写时复制产生的大量层快照）
- BuildKit 缓存
- 临时容器和镜像
- Docker 日志文件

### 影响范围
| 组件 | 当前状态 | 问题 |
|------|----------|------|
| gitea-runner-dind | 50Gi PVC, 几乎为空 | 频繁 OOM Restart (Exit 137) |
| docker-dind | 8Gi memory limit | 内存不足导致构建失败 |
| Harbor Registry | 48Gi / 2Ti warm storage | 存储利用率低 |
| k3s containerd | 系统组件 | 正常，无垃圾累积 |

---

## 二、系统架构分析

### 2.1 当前存储拓扑

```
sisys-node-01 (k3s v1.34.5)
├── /dev/sdd (1TB SSD) - 系统盘
│   ├── /var/lib/rancher/k3s/          # k3s 系统数据
│   │   └── agent/containerd/          # containerd 快照存储
│   │       └── io.containerd.snapshotter.v1.overlayfs/
│   └── /var/lib/kubelet/pods/         # Pod 存储
│
├── /dev/sde1 (2.5TB HDD) - 数据盘
│   └── /mnt/native-hdd/               # Harbor warm storage
│
└── PVC 存储 (local-path-provisioner)
    ├── docker-graph-gitea-runner-dind-0 (50Gi)
    ├── runner-data-gitea-runner-dind-0 (2Gi)
    └── harbor-registry-warm (2Ti)
```

### 2.2 Overlay2 存储机制

```
┌─────────────────────────────────────────────────────────────────┐
│                    Overlay2 写时复制 (CoW) 机制                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Lower Layer (只读)  ←── Base Image Layers                      │
│        ↑                                                            │
│        │ Copy-on-Write                                            │
│        ↓                                                            │
│   Upper Layer (可写)  ←── 修改的文件、新增的文件                    │
│        ↓                                                            │
│   Work Directory  ←─── 原子操作临时文件                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

问题：删除文件只是在 upper layer 标记删除，实际空间不释放
```

### 2.3 各组件存储使用

| 组件 | 存储路径 | 驱动 | 实际使用 | 分配 |
|------|----------|------|----------|------|
| Docker (dind) | PVC 50Gi | overlay2 | ~700KB | 50Gi |
| Containerd (k3s) | /var/lib/rancher/... | overlay2 | <1Gi | 系统盘 |
| Harbor hot | PVC 50Gi | local-path-ssd | ? | 50Gi |
| Harbor warm | PVC 2Ti | native-hdd-vhdx | 48Gi | 2Ti |

---

## 三、问题根因分析

### 3.1 Docker-in-Docker OOM 问题

```yaml
# 当前资源配置
docker-dind:
  limits:
    cpu: 4
    memory: 8Gi    # ❌ 不足

runner:
  limits:
    cpu: 2
    memory: 4Gi
```

**证据:**
- Exit Code 137 = OOM Kill
- docker-dind 重启 11 次
- runner 重启 18 次

### 3.2 Docker Daemon 配置缺失

```json
// 当前 daemon.json (缺失关键配置)
{
  "insecure-registries": ["harbor.sisys.local"],
  "dns": ["10.43.0.10", "8.8.8.8"],
  "dns-search": ["gitea-advacts.svc.cluster.local", "svc.cluster.local", "cluster.local"],
  "ipv6": false
  // ❌ 缺少 log-opts (日志无限增长)
  // ❌ 缺少 storage-opts size 限制
  // ❌ 缺少 ullimits 配置
}
```

### 3.3 缺少自动清理策略

- 无 `docker system prune` 定时任务
- 无 `docker builder prune` 策略
- 无 Pod 启动时清理机制
- 无存储容量监控告警

---

## 四、解决方案

### 方案 A: Docker Daemon 优化配置 (P0 - 立即实施)

#### 4.1.1 修改 ConfigMap

```yaml
# kubectl get configmap -n gitea-advacts gitea-runner-config -o yaml
# 更新 docker-dind 启动命令中的 daemon.json
```

**优化后的 daemon.json:**
```json
{
  "insecure-registries": ["harbor.sisys.local"],
  "dns": ["10.43.0.10", "8.8.8.8"],
  "dns-search": ["gitea-advacts.svc.cluster.local", "svc.cluster.local", "cluster.local"],
  "ipv6": false,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "storage-opts": [
    "overlay2.size=30G",
    "overlay2.metacopy=on"
  ],
  "live-restore": false,
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 65536,
      "Soft": 65536
    }
  }
}
```

**参数说明:**
| 参数 | 值 | 说明 |
|------|-----|------|
| log-opts.max-size | 100m | 单个日志文件最大 100MB |
| log-opts.max-file | 3 | 最多保留 3 个日志文件 |
| storage-opts.overlay2.size | 30G | 限制 overlay2 存储最大 30GB |
| storage-opts.overlay2.metacopy | on | 减少 metadata 操作 |

#### 4.1.2 部署方式

```bash
# 编辑 ConfigMap
kubectl edit configmap -n gitea-advacts gitea-runner-config

# 或使用补丁方式
kubectl patch configmap gitea-runner-config -n gitea-advacts \
  --type merge \
  -p '{"data":{"daemon.json":"{\"insecure-registries\":[\"harbor.sisys.local\"],\"dns\":[\"10.43.0.10\",\"8.8.8.8\"],\"log-driver\":\"json-file\",\"log-opts\":{\"max-size\":\"100m\",\"max-file\":\"3\"},\"storage-driver\":\"overlay2\",\"storage-opts\":[\"overlay2.size=30G\"]}"}}'
```

---

### 方案 B: 资源限制优化 (P0 - 立即实施)

#### 4.2.1 更新 StatefulSet 配置

```yaml
# gitea-runner-dind StatefulSet
spec:
  template:
    spec:
      containers:
        - name: docker-dind
          resources:
            limits:
              cpu: "4"
              memory: "12Gi"    # 从 8Gi 增加到 12Gi
            requests:
              cpu: "1"
              memory: "4Gi"
          livenessProbe:
            exec:
              command: [sh, -c, "docker info >/dev/null 2>&1"]
            initialDelaySeconds: 90  # 等待 Docker 完全就绪
            periodSeconds: 30
            timeoutSeconds: 10
            failureThreshold: 5

        - name: runner
          resources:
            limits:
              cpu: "2"
              memory: "4Gi"      # 从 4Gi 增加到 8Gi
            requests:
              cpu: "512m"
              memory: "2Gi"
```

**部署命令:**
```bash
kubectl patch statefulset gitea-runner-dind -n gitea-advacts \
  --type strategic-merge-patch -p '
{
  "spec": {
    "template": {
      "spec": {
        "containers": [
          {
            "name": "docker-dind",
            "resources": {
              "limits": {
                "cpu": "4",
                "memory": "12Gi"
              }
            }
          },
          {
            "name": "runner",
            "resources": {
              "limits": {
                "memory": "4Gi"
              }
            }
          }
        ]
      }
    }
  }
}'
```

---

### 方案 C: Pod 启动时自动清理 (P1 - 推荐实施)

#### 4.3.1 添加 InitContainer

```yaml
# 在 StatefulSet 中添加 initContainers
spec:
  initContainers:
    - name: cleanup-old-data
      image: harbor.sisys.local/sisys/tools/act_runner:0.3-dind-rootless
      command: ["/bin/sh", "-c"]
      args:
        - |
          echo "🧹 清理历史构建缓存..."
          # 等待 Docker daemon 就绪
          for i in {1..30}; do
            if docker info >/dev/null 2>&1; then
              echo "✅ Docker daemon ready"
              break
            fi
            echo "⏳ Waiting for Docker... ($i/30)"
            sleep 2
          done

          # 执行清理
          docker system prune -af --volumes || true
          docker builder prune -af --keep-storage=5G || true
          docker image prune -af || true

          # 显示清理后状态
          echo "📊 清理后存储状态:"
          docker system df

          echo "✅ 清理完成"
      volumeMounts:
        - name: docker-graph
          mountPath: /var/lib/docker
      securityContext:
        privileged: true
```

#### 4.3.2 完整 StatefulSet YAML

```yaml
# gitea-runner-dind StatefulSet (优化后完整配置)
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: gitea-runner-dind
  namespace: gitea-advacts
  labels:
    app: gitea-runner-dind
    env: advacts
    org: sisys
    runner-type: dind
spec:
  serviceName: gitea-runner-dind
  replicas: 1
  selector:
    matchLabels:
      app: gitea-runner-dind
  template:
    metadata:
      labels:
        app: gitea-runner-dind
    spec:
      initContainers:
        - name: cleanup-old-data
          image: harbor.sisys.local/sisys/tools/act_runner:0.3-dind-rootless
          command: ["/bin/sh", "-c"]
          args:
            - |
              echo "🧹 清理历史构建缓存..."
              for i in {1..30}; do
                if docker info >/dev/null 2>&1; then
                  echo "✅ Docker daemon ready"
                  break
                fi
                sleep 2
              done
              docker system prune -af --volumes || true
              docker builder prune -af --keep-storage=5G || true
              docker image prune -af || true
              docker system df
              echo "✅ 清理完成"
          volumeMounts:
            - name: docker-graph
              mountPath: /var/lib/docker
          securityContext:
            privileged: true
          resources:
            limits:
              cpu: "1"
              memory: "2Gi"
            requests:
              cpu: "100m"
              memory: "512Mi"
      containers:
        - name: docker-dind
          image: harbor.sisys.local/sisys/tools/gitea/act_runner:0.3-dind-rootless
          command: [sh, -c]
          args:
            - |
              echo "🚀 Starting Docker Daemon..."
              mkdir -p /var/run
              rm -f /var/run/docker.pid 2>/dev/null || true

              # 创建优化的 daemon.json
              mkdir -p /etc/docker
              cat > /etc/docker/daemon.json <<'EOF'
              {
                "insecure-registries": ["harbor.sisys.local"],
                "dns": ["10.43.0.10", "8.8.8.8"],
                "dns-search": ["gitea-advacts.svc.cluster.local", "svc.cluster.local", "cluster.local"],
                "ipv6": false,
                "log-driver": "json-file",
                "log-opts": {
                  "max-size": "100m",
                  "max-file": "3"
                },
                "storage-driver": "overlay2",
                "storage-opts": [
                  "overlay2.size=30G",
                  "overlay2.metacopy=on"
                ]
              }
              EOF

              dockerd \
                --log-level=error \
                --storage-driver=overlay2 \
                --host=unix:///var/run/docker.sock \
                --host=tcp://127.0.0.1:2375 \
                &

              for i in {1..30}; do
                if docker -H unix:///var/run/docker.sock info >/dev/null 2>&1; then
                  echo "✅ Docker daemon ready"
                  break
                fi
                sleep 1
              done

              tail -f /dev/null
          securityContext:
            privileged: true
          resources:
            limits:
              cpu: "4"
              memory: "12Gi"
            requests:
              cpu: "500m"
              memory: "2Gi"
          livenessProbe:
            exec:
              command: [sh, -c, "docker info >/dev/null 2>&1"]
            initialDelaySeconds: 90
            periodSeconds: 30
            timeoutSeconds: 10
            failureThreshold: 5
          volumeMounts:
            - name: docker-graph
              mountPath: /var/lib/docker
            - name: var-run
              mountPath: /var/run

        - name: runner
          image: harbor.sisys.local/sisys/tools/gitea/act_runner:0.3-dind-rootless
          command: ["/bin/sh", "-c"]
          env:
            - name: GITEA_INSTANCE_URL
              value: "https://gitea.sisys.local"
            - name: GITEA_RUNNER_NAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
            - name: GITEA_RUNNER_LABELS
              value: "advacts,dind,ubuntu2204,buildx"
            - name: GITEA_RUNNER_REGISTRATION_TOKEN
              valueFrom:
                secretKeyRef:
                  name: gitea-org-runner-token
                  key: token
            - name: DOCKER_HOST
              value: "tcp://127.0.0.1:2375"
          resources:
            limits:
              cpu: "2"
              memory: "4Gi"
            requests:
              cpu: "512m"
              memory: "1Gi"
          livenessProbe:
            exec:
              command: [sh, -c, "pgrep -f act_runner"]
            initialDelaySeconds: 60
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 5
          volumeMounts:
            - name: runner-data
              mountPath: /data
            - name: runner-config
              mountPath: /etc/act-runner/config.yaml
              readOnly: true
              subPath: config.yaml

      volumes:
        - name: runner-data
          persistentVolumeClaim:
            claimName: runner-data-gitea-runner-dind-0
        - name: runner-config
          configMap:
            name: gitea-runner-config
        - name: docker-graph
          persistentVolumeClaim:
            claimName: docker-graph-gitea-runner-dind-0
        - name: var-run
          emptyDir: {}
        - name: tmp
          emptyDir: {}
        - name: ca-certificates
          secret:
            secretName: ca-certificates
  volumeClaimTemplates:
    - metadata:
        name: runner-data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: "local-path"
        resources:
          requests:
            storage: 2Gi
    - metadata:
        name: docker-graph
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: "local-path"
        resources:
          requests:
            storage: 50Gi
```

---

### 方案 D: 定期清理 CronJob (P1 - 补充方案)

#### 4.4.1 创建清理 CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: dind-storage-cleanup
  namespace: gitea-advacts
spec:
  schedule: "0 3 * * *"  # 每天凌晨 3 点
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
  jobTemplate:
    spec:
      backoffLimit: 1
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: cleanup
              image: harbor.sisys.local/sisys/tools/act_runner:0.3-dind-rootless
              command: ["/bin/sh", "-c"]
              args:
                - |
                  echo "🧹 开始清理 Docker 存储..."
                  echo "📊 清理前状态:"
                  docker system df

                  # 清理未使用的镜像、容器、构建缓存
                  docker system prune -af --volumes || true
                  docker builder prune -af --keep-storage=10G || true

                  # 清理日志文件
                  find /var/lib/docker/containers -name "*.log" -delete 2>/dev/null || true

                  echo "📊 清理后状态:"
                  docker system df
                  echo "✅ 清理完成"
              env:
                - name: DOCKER_HOST
                  value: "tcp://docker-dind:2375"
              resources:
                limits:
                  cpu: "1"
                  memory: "2Gi"
                  ephemeral-storage: "1Gi"
                requests:
                  cpu: "100m"
                  memory: "512Mi"
          nodeSelector:
            kubernetes.io/hostname: sisys-node-01
```

#### 4.4.2 部署 CronJob

```bash
kubectl apply -f - <<'EOF'
apiVersion: batch/v1
kind: CronJob
metadata:
  name: dind-storage-cleanup
  namespace: gitea-advacts
spec:
  schedule: "0 3 * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
  jobTemplate:
    spec:
      backoffLimit: 1
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: cleanup
              image: harbor.sisys.local/sisys/tools/act_runner:0.3-dind-rootless
              command: ["/bin/sh", "-c"]
              args:
                - |
                  echo "🧹 开始清理 Docker 存储..."
                  docker system df
                  docker system prune -af --volumes || true
                  docker builder prune -af --keep-storage=10G || true
                  echo "✅ 清理完成"
              env:
                - name: DOCKER_HOST
                  value: "tcp://docker-dind:2375"
          nodeSelector:
            kubernetes.io/hostname: sisys-node-01
EOF
```

---

### 方案 E: Harbor Registry 优化 (P2 - 可选实施)

#### 4.5.1 分析当前存储

```bash
# 查看 Harbor 存储使用
kubectl exec -n harbor harbor-registry-58d6847f5f-q6hl8 -c registry -- du -sh /storage

# 查看镜像列表
kubectl exec -n harbor harbor-registry-58d6847f5f-q6hl8 -c registry -- \
  /bin/registry garbage-collect /etc/registry/config.yml --dry-run
```

#### 4.5.2 清理 Harbor 孤立 Blob

```bash
# 执行垃圾回收 (生产环境请先 --dry-run)
kubectl exec -n harbor harbor-registry-58d6847f5f-q6hl8 -c registry -- \
  /bin/registry garbage-collect /etc/registry/config.yml
```

#### 4.5.3 调整 Harbor PVC 大小

```bash
# 当前 warm storage 分配 2Ti，实际使用 48Gi
# 可以考虑缩减 PVC 或重建为更小的容量

# 注意: 需要先备份数据，再重建 PVC
kubectl patch pvc harbor-registry-warm -n harbor \
  -p '{"spec":{"resources":{"requests":{"storage":"100Gi"}}}}'
```

---

## 五、监控系统配置

### 5.1 存储告警规则

```yaml
# PrometheusRule for storage monitoring
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: dind-storage-alerts
  namespace: gitea-advacts
spec:
  groups:
    - name: dind-storage
      rules:
        - alert: DINDStorageUsageHigh
          expr: |
            (kubelet_volume_stats_used_bytes{namespace="gitea-advacts", persistentvolumeclaim=~"docker-graph.*"}
            /
            kubelet_volume_stats_capacity_bytes{namespace="gitea-advacts", persistentvolumeclaim=~"docker-graph.*"}) > 0.8
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "DIND Docker Graph storage usage above 80%"
            description: "PVC {{ $labels.persistentvolumeclaim }} 使用率 {{ $value | humanizePercentage }}"

        - alert: DINDStorageUsageCritical
          expr: |
            (kubelet_volume_stats_used_bytes{namespace="gitea-advacts", persistentvolumeclaim=~"docker-graph.*"}
            /
            kubelet_volume_stats_capacity_bytes{namespace="gitea-advacts", persistentvolumeclaim=~"docker-graph.*"}) > 0.9
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "DIND Docker Graph storage usage above 90%"
            description: "PVC {{ $labels.persistentvolumeclaim }} 使用率 {{ $value | humanizePercentage }}，即将满！"

        - alert: DINDPodRestarting
          expr: |
            rate(kube_pod_container_status_restarts_total{namespace="gitea-advacts", pod=~"gitea-runner-dind.*"}[1h]) > 0.1
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "DIND Pod 频繁重启"
            description: "Pod {{ $labels.pod }} 重启频率异常"
```

### 5.2 Grafana Dashboard 查询

```promql
# DIND Docker 存储使用
sum(container_fs_usage_bytes{namespace="gitea-advacts", pod="gitea-runner-dind-0", container="docker-dind"}) by (pod)

# DIND Pod 重启次数
sum(kube_pod_container_status_restarts_total{namespace="gitea-advacts", pod=~"gitea-runner-dind.*"}) by (pod, container)

# PVC 使用率
kubelet_volume_stats_used_bytes{namespace="gitea-advacts", persistentvolumeclaim=~"docker-graph.*"}
/
kubelet_volume_stats_capacity_bytes{namespace="gitea-advacts", persistentvolumeclaim=~"docker-graph.*"}
```

---

## 六、实施检查清单

### 6.1 实施前检查

- [ ] 备份当前 StatefulSet 配置
- [ ] 检查 PVC 可用空间
- [ ] 确认 Harbor 镜像仓库可访问
- [ ] 通知相关团队 (如有 CI/CD 流水线运行)

### 6.2 实施步骤

| 步骤 | 操作 | 命令 | 验证 |
|------|------|------|------|
| 1 | 备份配置 | `kubectl get statefulset gitea-runner-dind -n gitea-advacts -o yaml > backup.yaml` | ✅ |
| 2 | 部署 CronJob | `kubectl apply -f cleanup-cronjob.yaml` | `kubectl get cronjob -n gitea-advacts` |
| 3 | 更新 StatefulSet | `kubectl apply -f optimized-statefulset.yaml` | `kubectl rollout status statefulset gitea-runner-dind -n gitea-advacts` |
| 4 | 验证 Pod 重启 | `kubectl get pods -n gitea-advacts -w` | Pod 状态变为 Running |
| 5 | 检查 Docker 存储 | `kubectl exec -it gitea-runner-dind-0 -n gitea-advacts -c docker-dind -- docker system df` | 显示正确配置 |
| 6 | 触发一次测试构建 | 通过 Gitea 触发 Actions | 构建成功完成 |

### 6.3 回滚方案

```bash
# 如果出现问题，回滚到备份的配置
kubectl apply -f backup.yaml

# 或者快速回滚资源限制
kubectl patch statefulset gitea-runner-dind -n gitea-advacts \
  --type strategic-merge-patch -p '
{
  "spec": {
    "template": {
      "spec": {
        "containers": [
          {
            "name": "docker-dind",
            "resources": {
              "limits": {
                "memory": "8Gi"
              }
            }
          }
        ]
      }
    }
  }
}'
```

---

## 七、预期效果

### 7.1 存储效果

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| overlay2 存储上限 | 无限制 (50Gi) | 30Gi |
| 日志文件上限 | 无限增长 | 300MB (100m x 3) |
| 启动时清理 | 无 | ✅ 自动清理 |
| 定期清理 | 无 | ✅ 每天凌晨 3 点 |

### 7.2 稳定性效果

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| docker-dind 重启频率 | 11+ 次 | < 1 次/周 |
| OOM Kill 次数 | 频繁 | 极少 |
| 构建成功率 | 受影响 | 正常 |

### 7.3 监控效果

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 存储告警 | 无 | ✅ 支持 |
| 异常重启告警 | 无 | ✅ 支持 |
| Dashboard | 无 | ✅ 可视化 |

---

## 八、附录

### 8.1 相关文档

- [Gitea Runner Cleanup Report](./GITEA_RUNNER_CLEANUP_REPORT.md)
- [Harbor Architecture](./HARBOR_ARCHITECTURE.md)
- [Harbor Tiered Storage Solution](./HARBOR_TIERED_STORAGE_SOLUTION.md)

### 8.2 相关命令速查

```bash
# 查看 Docker 存储使用
kubectl exec -it gitea-runner-dind-0 -n gitea-advacts -c docker-dind -- docker system df -v

# 查看 overlay2 层
kubectl exec -it gitea-runner-dind-0 -n gitea-advacts -c docker-dind -- ls -la /var/lib/docker/overlay2/

# 手动清理
kubectl exec -it gitea-runner-dind-0 -n gitea-advacts -c docker-dind -- docker system prune -af
kubectl exec -it gitea-runner-dind-0 -n gitea-advacts -c docker-dind -- docker builder prune -af

# 查看 Pod 日志
kubectl logs -n gitea-advacts gitea-runner-dind-0 -c docker-dind --tail=100
kubectl logs -n gitea-advacts gitea-runner-dind-0 -c runner --tail=100

# 查看 PVC 使用
kubectl get pvc -n gitea-advacts -o wide
kubectl describe pvc docker-graph-gitea-runner-dind-0 -n gitea-advacts
```

### 8.3 版本信息

| 组件 | 版本 |
|------|------|
| Kubernetes | v1.34.5+k3s1 |
| K3s | v1.34.5 |
| Docker | act_runner:0.3-dind-rootless |
| Gitea Runner | v0.3.1 |
| Containerd | 内置于 k3s |

---

**文档结束**
