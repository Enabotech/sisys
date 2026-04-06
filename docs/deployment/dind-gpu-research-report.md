# DinD 支持 GPU 方案研究报告

**版本**: v1.0
**日期**: 2026-04-06
**作者**: SISYS Team
**状态**: 待评审
**关联 Story**: 0-8-gitea-runner-configuration

---

## 📋 目录

- [1. 背景与问题定义](#1-背景与问题定义)
- [2. 现状分析](#2-现状分析)
- [3. 方案 A：K8s Native GPU Pod（最安全）](#3-方案-ak8s-native-gpu-pod最安全)
- [4. 方案 B：Rootless DinD + CDI 设备注入（较安全）](#4-方案-brootless-dind--cdi-设备注入较安全)
- [5. 方案 C：受限特权 DinD + seccomp 白名单（中等安全）](#5-方案-c受限特权-dind--seccomp-白名单中等安全)
- [6. 方案对比矩阵](#6-方案对比矩阵)
- [7. WSL2 兼容性评估](#7-wsl2-兼容性评估)
- [8. 实施建议与路线图](#8-实施建议与路线图)
- [9. 参考资料](#9-参考资料)

---

## 1. 背景与问题定义

### 1.1 系统环境

| 组件 | 配置 |
|------|------|
| **操作系统** | WSL2 Ubuntu 22.04 |
| **内核版本** | 6.6.87.2-microsoft-standard |
| **容器运行时** | K3s containerd://2.1.5-k3s1 |
| **GPU 硬件** | NVIDIA RTX 5090 |
| **GPU 驱动** | NVIDIA Driver（宿主机安装） |
| **GPU 插件** | NVIDIA Device Plugin（kube-system 命名空间） |

### 1.2 问题定义

当前系统部署了两套 Gitea Runner：

| Runner | 架构 | GPU 支持 | 状态 |
|--------|------|---------|------|
| **gitea-actions** | 单容器 + hostPath `/var/run/docker.sock` | ✅ 直通 GPU | 已工作 |
| **gitea-advacts** | 双容器 DinD Sidecar | ❌ 无 GPU 能力 | 新部署 |

**核心问题**：如何让 `gitea-advacts` DinD Runner 也能安全地访问 GPU RTX 5090？

### 1.3 安全约束

- DinD 容器目前使用 `privileged: true`，已属安全妥协
- 全量 `/dev` 直通不可接受（暴露所有主机设备）
- 需要最小权限原则（Principle of Least Privilege）
- WSL2 环境下 GPU 直通有特殊性（微软 WSLg 架构）

---

## 2. 现状分析

### 2.1 gitea-actions GPU 直通机制

现有 gitea-actions runner 能使用 GPU，依赖以下三层链路：

```
┌─────────────────────────────────────────────────────────────┐
│  宿主机 (WSL2 Ubuntu 22.04)                                 │
│  GPU: RTX 5090                                              │
│  驱动: NVIDIA Driver (宿主机安装)                            │
│  NVIDIA Device Plugin: 向 K8s 暴露 nvidia.com/gpu: 1        │
├─────────────────────────────────────────────────────────────┤
│  K3s containerd (宿主进程)                                   │
│  - 已配置 nvidia-container-runtime                           │
│  - 默认运行时: nvidia                                        │
│  - 设备注入: 自动挂载 /dev/nvidia*                           │
├─────────────────────────────────────────────────────────────┤
│  Pod: gitea-org-runner-XX                                   │
│  - hostPath: /var/run/docker.sock → K3s containerd shim     │
│  - docker run --gpus all → containerd → nvidia-runtime → GPU│
│  - 标签: ubuntu-latest,docker,k3s,linux,gpu                 │
└─────────────────────────────────────────────────────────────┘
```

**关键配置**（`gitea-org-runner-statefulset.yaml`）：

```yaml
containers:
  - name: runner
    image: docker.io/gitea/act_runner:0.3.0
    volumeMounts:
      - name: docker-sock
        mountPath: /var/run/docker.sock
        readOnly: false
volumes:
  - name: docker-sock
    hostPath:
      path: /var/run/docker.sock
      type: Socket
```

**GPU 传递链**：
```
workflow 请求 --gpus all
  → act_runner 执行 docker run
    → /var/run/docker.sock (hostPath)
      → K3s containerd shim
        → nvidia-container-runtime
          → /dev/nvidia0 注入
            → 容器内 nvidia-smi 可见
```

### 2.2 gitea-advacts DinD 当前配置

```yaml
# docker-dind 容器
containers:
  - name: docker-dind
    securityContext:
      privileged: true
    command: |
      dockerd \
        --host=unix:///var/run/docker.sock \
        --host=tcp://127.0.0.1:2375
    # daemon.json 无 GPU 配置
```

**缺失项清单**：

| 缺失项 | 作用 | 当前状态 |
|--------|------|---------|
| **nvidia-container-runtime** | 容器内 GPU 访问运行时 | ❌ 未安装 |
| **daemon.json GPU 配置** | Docker 识别 GPU 运行时 | ❌ 无 |
| **/dev/nvidia* 设备挂载** | GPU 设备直通 | ❌ 未挂载 |
| **NVIDIA_VISIBLE_DEVICES** | 环境变量传递 | ❌ 未配置 |
| **NVIDIA Driver 库挂载** | 用户态驱动库 | ❌ 未挂载 |
| **CDI 设备注入** | 标准化设备接口 | ❌ 未配置 |

### 2.3 根本原因分析

```
┌─────────────────────────────────────────────────────────────┐
│  Pod: gitea-runner-dind-0                                   │
│  Network: bridge (隔离)                                      │
├─────────────────────────────────────────────────────────────┤
│  Container: docker-dind                                     │
│  - 独立 Docker daemon (dockerd)                             │
│  - Storage Driver: overlay2                                 │
│  - ❌ 无 nvidia-container-runtime                           │
│  - ❌ daemon.json 无 GPU 配置                               │
│  - ❌ 未挂载 /dev/nvidia* 设备                              │
│  - ❌ 无 NVIDIA_VISIBLE_DEVICES 环境变量                    │
│                                                             │
│  结果: docker run --gpus all → 报错                         │
│        "could not select device driver with capabilities"   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 方案 A：K8s Native GPU Pod（最安全）

### 3.1 架构原理

放弃 DinD，让 act_runner 作为 **K8s Controller**，每个 workflow job 动态创建独立 Pod，由 K8s 原生调度 GPU。

```
┌─────────────────────────────────────────────────────────────┐
│  K3s Node (WSL2)                                            │
│  NVIDIA Device Plugin → 暴露 nvidia.com/gpu: 1              │
├─────────────────────────────────────────────────────────────┤
│  act_runner (K8s Executor 模式)                             │
│  - 不使用 Docker executor                                   │
│  - 直接创建 K8s Pod 执行 workflow                           │
│  - Pod spec 中声明 nvidia.com/gpu: 1                        │
│  - NVIDIA Device Plugin 自动注入 GPU                        │
└─────────────────────────────────────────────────────────────┘
```

**数据流**：
```
workflow 触发
  → act_runner 收到 Job
    → 创建 K8s Pod (含 GPU 资源声明)
      → K8s Scheduler 调度到 GPU 节点
        → NVIDIA Device Plugin 注入 /dev/nvidia0
          → Pod 内 nvidia-smi 可见
            → Job 执行完成
              → Pod 自动清理 (TTL)
```

### 3.2 配置实现

#### 3.2.1 Runner 配置（config.yaml）

```yaml
# gitea-runner-k8s-config ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: gitea-runner-k8s-config
  namespace: gitea-advacts
data:
  config.yaml: |
    log:
      level: info
      format: text
      output: stdout

    runner:
      file: /data/.runner
      workdir: /data/workdir
      tempdir: /data/tmp
      timeout: 30m

    # K8s Executor 配置
    container:
      kubernetes:
        namespace: gitea-advacts
        service_account: gitea-runner-dind

        image_pull_secrets:
          - harbor-robot-account

        pod_template: |
          apiVersion: v1
          kind: Pod
          spec:
            serviceAccountName: gitea-runner-dind
            imagePullSecrets:
              - name: harbor-robot-account

            securityContext:
              runAsNonRoot: false
              runAsUser: 0
              fsGroup: 1000

            containers:
              - name: job
                image: harbor.sisys.local/sisys/dependency:l2-latest
                workingDir: /workspace

                resources:
                  requests:
                    cpu: 500m
                    memory: 2Gi
                    nvidia.com/gpu: "1"     # ← GPU 资源申请
                  limits:
                    cpu: 4000m
                    memory: 8Gi
                    nvidia.com/gpu: "1"     # ← GPU 资源限制

                # 安全上下文（非特权）
                securityContext:
                  allowPrivilegeEscalation: false
                  capabilities:
                    drop:
                      - ALL

                env:
                  - name: WORKSPACE
                    value: /workspace
                  - name: RUNNER_TEMP
                    value: /tmp
                  - name: NVIDIA_VISIBLE_DEVICES
                    value: all
                  - name: NVIDIA_DRIVER_CAPABILITIES
                    value: compute,utility

                volumeMounts:
                  - name: workspace
                    mountPath: /workspace
                  - name: tmp
                    mountPath: /tmp

            volumes:
              - name: workspace
                emptyDir: {}
              - name: tmp
                emptyDir:
                  medium: Memory

            # 调度到 GPU 节点
            nodeSelector:
              nvidia.com/gpu.present: "true"

            tolerations:
              - key: nvidia.com/gpu
                operator: Exists
                effect: NoSchedule

            restartPolicy: Never
```

#### 3.2.2 RBAC 配置（需扩展）

```yaml
# 扩展 runner RBAC 以创建 Pod/Job
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: gitea-runner-k8s-job-role
  namespace: gitea-advacts
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "pods/exec"]
    verbs: ["create", "get", "list", "watch", "delete"]
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list"]
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["create", "get", "list", "watch", "delete"]
```

#### 3.2.3 Workflow 触发方式

在 `.gitea/workflows/gpu-test.yml` 中指定标签：

```yaml
name: GPU Test
on: [push]

jobs:
  gpu-test:
    runs-on: ubuntu-latest,gpu,k8s,native   # ← 使用 K8s Executor 标签
    steps:
      - uses: actions/checkout@v4
      - name: Check GPU
        run: |
          nvidia-smi
          python3 -c "import torch; print(torch.cuda.is_available())"
```

### 3.3 安全分析

| 维度 | 评估 | 说明 |
|------|------|------|
| **特权容器** | ✅ 不需要 | Job Pod 无需 privileged |
| **设备直通** | ✅ K8s 原生 | NVIDIA Device Plugin 自动注入 |
| **网络隔离** | ✅ Cluster 网络 | Pod 使用 K8s CNI |
| **资源隔离** | ✅ 天然隔离 | 每个 Job 独立 Pod |
| **清理机制** | ✅ 自动清理 | TTL 后自动删除 |
| **攻击面** | ✅ 最小 | 无 Docker daemon 暴露 |

### 3.4 优势与劣势

**优势**：
- ✅ **零特权容器** - Job Pod 不需要 privileged
- ✅ **天然隔离** - 每个 Job 独立 Pod，互不影响
- ✅ **K8s 原生 GPU 调度** - NVIDIA Device Plugin 自动注入
- ✅ **资源配额可控** - LimitRange/ResourceQuota 限制
- ✅ **自动清理** - Job 完成后 Pod 自动删除
- ✅ **项目已有基础配置** - `runner-k8s-executor.yaml` 已存在

**劣势**：
- ⚠️ 需要 act_runner 0.3.0+ 支持 K8s executor
- ⚠️ 需要额外 RBAC 权限（创建 Pod/Job）
- ⚠️ 多 Pod 创建/销毁开销（约 2-5 秒）

---

## 4. 方案 B：Rootless DinD + CDI 设备注入（较安全）

### 4.1 架构原理

使用 NVIDIA **CDI (Container Device Interface)** 在 rootless DinD 中注入 GPU，无需特权模式。

```
┌─────────────────────────────────────────────────────────────┐
│  宿主机 (WSL2)                                              │
│  - NVIDIA Driver + CDI 配置                                 │
│  - /var/run/cdi/nvidia.yaml (CDI spec)                      │
├─────────────────────────────────────────────────────────────┤
│  Pod: gitea-runner-dind-0                                   │
├─────────────────────────────────────────────────────────────┤
│  Container: docker-dind (rootless)                          │
│  - 非特权 (privileged: false)                               │
│  - 仅需 SYS_ADMIN 能力                                      │
│  - 挂载 /var/run/cdi (CDI 设备规范)                         │
│  - 挂载 /run/nvidia/driver (用户态驱动库)                   │
│                                                             │
│  daemon.json:                                               │
│    "features": {"cdi": true}                                │
│    "runtimes": {"nvidia": {...}}                            │
├─────────────────────────────────────────────────────────────┤
│  Container: runner                                          │
│  - 通过 TCP 调用 docker-dind                                │
│  - docker run --device nvidia.com/gpu=all → CDI 注入        │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 配置实现

#### 4.2.1 宿主机 CDI 配置

创建 `/etc/cdi/nvidia.yaml`：

```yaml
cdiVersion: 0.5.0
kind: nvidia.com/gpu
devices:
  - name: all
    annotations:
      nvidia.com/gpu.count: "1"
    containerEdits:
      deviceNodes:
        - path: /dev/nvidia0
          type: char
        - path: /dev/nvidiactl
          type: char
        - path: /dev/nvidia-uvm
          type: char
        - path: /dev/nvidia-uvm-tools
          type: char
      mounts:
        - hostPath: /usr/lib/x86_64-linux-gnu
          containerPath: /usr/lib/x86_64-linux-gnu
          options: [ro]
        - hostPath: /usr/share/glvnd
          containerPath: /usr/share/glvnd
          options: [ro]
      env:
        - NVIDIA_VISIBLE_DEVICES=all
        - NVIDIA_DRIVER_CAPABILITIES=compute,utility
```

#### 4.2.2 DinD StatefulSet 配置

```yaml
containers:
  - name: docker-dind
    image: harbor.sisys.local/sisys/tools/gitea/act_runner:0.3.0-dind-rootless
    imagePullPolicy: IfNotPresent

    securityContext:
      privileged: false           # ← 非特权
      allowPrivilegeEscalation: true
      capabilities:
        add:
          - SYS_ADMIN             # ← 仅需此权限
        drop:
          - NET_RAW
      seccompProfile:
        type: RuntimeDefault

    command:
      - sh
      - -c
      - |
        echo "🚀 Starting Rootless Docker Daemon with CDI GPU support..."

        mkdir -p /etc/docker
        cat > /etc/docker/daemon.json <<'EOF'
        {
          "default-runtime": "nvidia",
          "runtimes": {
            "nvidia": {
              "path": "nvidia-container-runtime",
              "runtimeArgs": []
            }
          },
          "features": {
            "cdi": true
          },
          "insecure-registries": ["harbor.sisys.local"],
          "dns": ["10.43.0.10", "8.8.8.8"],
          "dns-search": ["gitea-advacts.svc.cluster.local", "svc.cluster.local", "cluster.local"],
          "ipv6": false
        }
        EOF

        # 安装 nvidia-container-toolkit（如果镜像中没有）
        if [ ! -f /usr/bin/nvidia-container-runtime ]; then
          echo "📦 Installing nvidia-container-toolkit..."
          apk add --no-cache nvidia-container-toolkit || \
          curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg && \
          curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
            sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
            tee /etc/apt/sources.list.d/nvidia-container-toolkit.list && \
          apt-get update && apt-get install -y nvidia-container-toolkit
        fi

        # 配置 CDI
        export CDI_SPEC_DIRS=/var/run/cdi
        export NVIDIA_VISIBLE_DEVICES=all

        # 启动 rootless dockerd
        dockerd \
          --log-level=error \
          --storage-driver=overlay2 \
          --host=unix:///var/run/docker.sock \
          --host=tcp://127.0.0.1:2375 \
          &

        # 等待 Docker 就绪
        for i in {1..30}; do
          if docker -H unix:///var/run/docker.sock info >/dev/null 2>&1; then
            echo "✅ Docker daemon ready"
            break
          fi
          sleep 1
        done

        # 验证 GPU
        echo "🔍 Verifying GPU access..."
        docker run --rm --device nvidia.com/gpu=all \
          harbor.sisys.local/sisys/dependency:l2-latest \
          nvidia-smi || echo "⚠️ GPU verification failed"

        tail -f /dev/null

    volumeMounts:
      - name: var-run
        mountPath: /var/run
      - name: docker-graph
        mountPath: /var/lib/docker
      - name: tmp
        mountPath: /tmp
      # CDI 设备规范
      - name: cdi-nvidia
        mountPath: /var/run/cdi
        readOnly: true
      # NVIDIA 驱动库（用户态）
      - name: nvidia-driver-libs
        mountPath: /run/nvidia/driver
        readOnly: true
      # NVIDIA 工具
      - name: nvidia-container-toolkit
        mountPath: /usr/bin/nvidia-container-runtime
        subPath: nvidia-container-runtime
        readOnly: true

    env:
      - name: CDI_SPEC_DIRS
        value: "/var/run/cdi"
      - name: NVIDIA_VISIBLE_DEVICES
        value: all

volumes:
  - name: cdi-nvidia
    hostPath:
      path: /var/run/cdi
      type: DirectoryOrCreate
  - name: nvidia-driver-libs
    hostPath:
      path: /run/nvidia/driver
      type: DirectoryOrCreate
  - name: nvidia-container-toolkit
    hostPath:
      path: /usr/bin/nvidia-container-runtime
      type: File
```

### 4.3 安全分析

| 维度 | 评估 | 说明 |
|------|------|------|
| **特权容器** | ✅ 不需要 | 仅需 SYS_ADMIN |
| **设备直通** | ⚠️ 受控 | CDI 规范定义设备，非全量 /dev |
| **网络隔离** | ✅ bridge | Pod 内部网络 |
| **攻击面** | ⚠️ 中等 | SYS_ADMIN 权限较高 |
| **WSL2 兼容** | ⚠️ 需验证 | CDI 在 WSL2 上支持待确认 |

### 4.4 优势与劣势

**优势**：
- ✅ 非特权容器（仅需 SYS_ADMIN）
- ✅ CDI 标准化设备注入
- ✅ DinD 隔离保留
- ✅ 设备访问可控（CDI spec 定义）

**劣势**：
- ⚠️ WSL2 上 CDI 支持需验证
- ⚠️ 需要安装 nvidia-container-toolkit 到 DinD 镜像中
- ⚠️ SYS_ADMIN 权限仍然较高
- ⚠️ 配置复杂度高

---

## 5. 方案 C：受限特权 DinD + seccomp 白名单（中等安全）

### 5.1 架构原理

保留特权模式，但用 **seccomp profile** 限制系统调用，用 **设备白名单** 限制 GPU 设备访问。

```
┌─────────────────────────────────────────────────────────────┐
│  Pod: gitea-runner-dind-0                                   │
│  Network: bridge                                             │
├─────────────────────────────────────────────────────────────┤
│  Container: docker-dind                                     │
│  - privileged: true (必需)                                  │
│  - seccomp: 自定义 profile (白名单)                         │
│  - capabilities: 添加必需，丢弃不必要                       │
│  - volumes: 仅挂载必要 GPU 设备                             │
│    - /dev/nvidia0 (GPU 计算)                                │
│    - /dev/nvidiactl (控制)                                  │
│    - /dev/nvidia-uvm (统一内存)                             │
│    ❌ 不挂载 /dev/mem, /dev/kmem 等敏感设备                 │
│                                                             │
│  daemon.json:                                               │
│    "default-runtime": "nvidia"                              │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 配置实现

#### 5.2.1 Seccomp Profile 配置

创建 `dind-gpu-seccomp.json`：

```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "archMap": [
    {
      "architecture": "SCMP_ARCH_X86_64",
      "subArchitectures": [
        "SCMP_ARCH_X86",
        "SCMP_ARCH_X32"
      ]
    }
  ],
  "syscalls": [
    {
      "names": [
        "accept",
        "accept4",
        "access",
        "adjtimex",
        "alarm",
        "bind",
        "brk",
        "capget",
        "capset",
        "chdir",
        "chmod",
        "chown",
        "chown32",
        "clock_adjtime",
        "clock_adjtime64",
        "clock_getres",
        "clock_getres_time64",
        "clock_gettime",
        "clock_gettime64",
        "clock_nanosleep",
        "clock_nanosleep_time64",
        "clone",
        "clone3",
        "close",
        "close_range",
        "connect",
        "copy_file_range",
        "creat",
        "dup",
        "dup2",
        "dup3",
        "epoll_create",
        "epoll_create1",
        "epoll_ctl",
        "epoll_ctl_old",
        "epoll_pwait",
        "epoll_pwait2",
        "epoll_wait",
        "epoll_wait_old",
        "eventfd",
        "eventfd2",
        "execve",
        "execveat",
        "exit",
        "exit_group",
        "faccessat",
        "faccessat2",
        "fadvise64",
        "fadvise64_64",
        "fallocate",
        "fanotify_mark",
        "fchdir",
        "fchmod",
        "fchmodat",
        "fchmodat2",
        "fchown",
        "fchown32",
        "fchownat",
        "fcntl",
        "fcntl64",
        "fdatasync",
        "fgetxattr",
        "flistxattr",
        "flock",
        "fork",
        "fremovexattr",
        "fsetxattr",
        "fstat",
        "fstat64",
        "fstatat64",
        "fstatfs",
        "fstatfs64",
        "fsync",
        "ftruncate",
        "ftruncate64",
        "futex",
        "futex_time64",
        "futimesat",
        "getcpu",
        "getcwd",
        "getdents",
        "getdents64",
        "getegid",
        "getegid32",
        "geteuid",
        "geteuid32",
        "getgid",
        "getgid32",
        "getgroups",
        "getgroups32",
        "getitimer",
        "getpeername",
        "getpgid",
        "getpgrp",
        "getpid",
        "getppid",
        "getpriority",
        "getrandom",
        "getresgid",
        "getresgid32",
        "getresuid",
        "getresuid32",
        "getrlimit",
        "get_robust_list",
        "getrusage",
        "getsid",
        "getsockname",
        "getsockopt",
        "get_thread_area",
        "gettid",
        "gettimeofday",
        "getuid",
        "getuid32",
        "getxattr",
        "inotify_add_watch",
        "inotify_init",
        "inotify_init1",
        "inotify_rm_watch",
        "io_cancel",
        "ioctl",
        "io_destroy",
        "io_getevents",
        "io_pgetevents",
        "io_pgetevents_time64",
        "ioprio_get",
        "ioprio_set",
        "io_setup",
        "io_submit",
        "io_uring_enter",
        "io_uring_register",
        "io_uring_setup",
        "ipc",
        "kill",
        "lchown",
        "lchown32",
        "lgetxattr",
        "link",
        "linkat",
        "listen",
        "listxattr",
        "llistxattr",
        "_llseek",
        "lremovexattr",
        "lseek",
        "lsetxattr",
        "lstat",
        "lstat64",
        "madvise",
        "map_shadow_stack",
        "mbind",
        "membarrier",
        "memfd_create",
        "memfd_secret",
        "mincore",
        "mkdir",
        "mkdirat",
        "mknod",
        "mknodat",
        "mlock",
        "mlock2",
        "mlockall",
        "mmap",
        "mmap2",
        "mount",
        "move_mount",
        "mprotect",
        "mq_getsetattr",
        "mq_notify",
        "mq_open",
        "mq_timedreceive",
        "mq_timedreceive_time64",
        "mq_timedsend",
        "mq_timedsend_time64",
        "mq_unlink",
        "mremap",
        "msgctl",
        "msgget",
        "msgrcv",
        "msgsnd",
        "msync",
        "munlock",
        "munlockall",
        "munmap",
        "name_to_handle_at",
        "nanosleep",
        "newfstatat",
        "_newselect",
        "open",
        "openat",
        "openat2",
        "open_by_handle_at",
        "pause",
        "pidfd_getfd",
        "pidfd_open",
        "pidfd_send_signal",
        "pipe",
        "pipe2",
        "pivot_root",
        "pkey_alloc",
        "pkey_free",
        "pkey_mprotect",
        "poll",
        "ppoll",
        "ppoll_time64",
        "prctl",
        "pread64",
        "preadv",
        "preadv2",
        "prlimit64",
        "process_mrelease",
        "process_vm_readv",
        "process_vm_writev",
        "pselect6",
        "pselect6_time64",
        "pwrite64",
        "pwritev",
        "pwritev2",
        "read",
        "readahead",
        "readlink",
        "readlinkat",
        "readv",
        "recv",
        "recvfrom",
        "recvmmsg",
        "recvmmsg_time64",
        "recvmsg",
        "remap_file_pages",
        "removexattr",
        "rename",
        "renameat",
        "renameat2",
        "restart_syscall",
        "rmdir",
        "rseq",
        "rt_sigaction",
        "rt_sigpending",
        "rt_sigprocmask",
        "rt_sigqueueinfo",
        "rt_sigreturn",
        "rt_sigsuspend",
        "rt_sigtimedwait",
        "rt_sigtimedwait_time64",
        "rt_tgsigqueueinfo",
        "sched_getaffinity",
        "sched_getattr",
        "sched_getparam",
        "sched_get_priority_max",
        "sched_get_priority_min",
        "sched_getscheduler",
        "sched_rr_get_interval",
        "sched_rr_get_interval_time64",
        "sched_setaffinity",
        "sched_setattr",
        "sched_setparam",
        "sched_setscheduler",
        "sched_yield",
        "seccomp",
        "select",
        "semctl",
        "semget",
        "semop",
        "semtimedop",
        "semtimedop_time64",
        "send",
        "sendfile",
        "sendfile64",
        "sendmmsg",
        "sendmsg",
        "sendto",
        "setfsgid",
        "setfsgid32",
        "setfsuid",
        "setfsuid32",
        "setgid",
        "setgid32",
        "setgroups",
        "setgroups32",
        "setitimer",
        "setns",
        "setpgid",
        "setpriority",
        "setregid",
        "setregid32",
        "setresgid",
        "setresgid32",
        "setresuid",
        "setresuid32",
        "setreuid",
        "setreuid32",
        "setrlimit",
        "set_robust_list",
        "setsid",
        "setsockopt",
        "set_thread_area",
        "set_tid_address",
        "setuid",
        "setuid32",
        "setxattr",
        "shmat",
        "shmctl",
        "shmdt",
        "shmget",
        "shutdown",
        "sigaltstack",
        "signalfd",
        "signalfd4",
        "sigprocmask",
        "sigreturn",
        "socket",
        "socketcall",
        "socketpair",
        "splice",
        "stat",
        "stat64",
        "statfs",
        "statfs64",
        "statx",
        "symlink",
        "symlinkat",
        "sync",
        "sync_file_range",
        "syncfs",
        "sysinfo",
        "tee",
        "tgkill",
        "time",
        "timer_create",
        "timer_delete",
        "timer_getoverrun",
        "timer_gettime",
        "timer_gettime64",
        "timer_settime",
        "timer_settime64",
        "timerfd_create",
        "timerfd_gettime",
        "timerfd_gettime64",
        "timerfd_settime",
        "timerfd_settime64",
        "times",
        "tkill",
        "truncate",
        "truncate64",
        "ugetrlimit",
        "umask",
        "uname",
        "unlink",
        "unlinkat",
        "unshare",
        "utime",
        "utimensat",
        "utimensat_time64",
        "utimes",
        "vfork",
        "vmsplice",
        "wait4",
        "waitid",
        "waitpid",
        "write",
        "writev"
      ],
      "action": "SCMP_ACT_ALLOW"
    }
  ]
}
```

**注意**：此 profile **明确禁止** 以下危险系统调用：
- `init_module` - 加载内核模块
- `delete_module` - 删除内核模块
- `kexec_load` - 加载新内核
- `open_by_handle_at` - 通过句柄访问文件
- `ptrace` - 进程跟踪
- `mount`（部分场景允许）

#### 5.2.2 StatefulSet 配置

```yaml
containers:
  - name: docker-dind
    image: harbor.sisys.local/sisys/tools/gitea/act_runner:0.3.0-dind-rootless
    imagePullPolicy: IfNotPresent

    securityContext:
      privileged: true            # ← 特权模式（必需）
      allowPrivilegeEscalation: true
      capabilities:
        add:
          - SYS_ADMIN
          - SYS_PTRACE
          - NET_ADMIN
        drop:
          - NET_RAW               # ← 禁止原始网络
          - SYS_MODULE            # ← 禁止内核模块
          - SYS_RAWIO             # ← 禁止原始 IO
          - DAC_OVERRIDE          # ← 禁止覆盖权限检查
      seccompProfile:
        type: LocalObject
        localhostProfile: runtime/default  # 或自定义 profile

    command:
      - sh
      - -c
      - |
        echo "🚀 Starting Docker Daemon with restricted GPU access..."

        # 清理旧 PID
        rm -f /var/run/docker.pid 2>/dev/null || true
        rm -f /var/run/docker/*.pid 2>/dev/null || true

        mkdir -p /etc/docker
        cat > /etc/docker/daemon.json <<'EOF'
        {
          "default-runtime": "nvidia",
          "runtimes": {
            "nvidia": {
              "path": "nvidia-container-runtime",
              "runtimeArgs": []
            }
          },
          "insecure-registries": ["harbor.sisys.local"],
          "dns": ["10.43.0.10", "8.8.8.8"],
          "dns-search": ["gitea-advacts.svc.cluster.local", "svc.cluster.local", "cluster.local"],
          "ipv6": false
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

        # 验证 GPU
        docker run --rm --gpus all \
          harbor.sisys.local/sisys/dependency:l2-latest \
          nvidia-smi || echo "⚠️ GPU verification failed"

        tail -f /dev/null

    env:
      - name: NVIDIA_VISIBLE_DEVICES
        value: all
      - name: NVIDIA_DRIVER_CAPABILITIES
        value: compute,utility

    volumeMounts:
      - name: var-run
        mountPath: /var/run
      - name: docker-graph
        mountPath: /var/lib/docker
      - name: tmp
        mountPath: /tmp
      # ✅ 仅挂载必要 GPU 设备（非 /dev 全量）
      - name: nvidia-gpu
        mountPath: /dev/nvidia0
      - name: nvidia-ctl
        mountPath: /dev/nvidiactl
      - name: nvidia-uvm
        mountPath: /dev/nvidia-uvm

volumes:
  - name: nvidia-gpu
    hostPath:
      path: /dev/nvidia0
      type: CharDevice
  - name: nvidia-ctl
    hostPath:
      path: /dev/nvidiactl
      type: CharDevice
  - name: nvidia-uvm
    hostPath:
      path: /dev/nvidia-uvm
      type: CharDevice
```

### 5.3 安全分析

| 维度 | 评估 | 说明 |
|------|------|------|
| **特权容器** | ⚠️ 需要 | dockerd 必需 privileged |
| **设备直通** | ⚠️ 受控 | 仅挂载 3 个必要设备 |
| **系统调用** | ✅ 受限 | seccomp 白名单 |
| **能力** | ⚠️ 部分受限 | 丢弃 NET_RAW/SYS_MODULE 等 |
| **网络隔离** | ✅ bridge | Pod 内部网络 |

### 5.4 优势与劣势

**优势**：
- ✅ 实现简单（仅需 daemon.json + 设备挂载）
- ✅ seccomp 白名单限制攻击面
- ✅ GPU 设备受控（非全量 /dev）
- ✅ WSL2 兼容性最好

**劣势**：
- ⚠️ 仍需 privileged 模式
- ⚠️ seccomp profile 维护成本高
- ⚠️ 特权容器被突破风险仍然存在

---

## 6. 方案对比矩阵

### 6.1 安全维度

| 维度 | 方案 A (K8s Native) | 方案 B (Rootless + CDI) | 方案 C (受限特权 DinD) |
|------|---------------------|-------------------------|----------------------|
| **特权容器** | ✅ 不需要 | ✅ 不需要 | ⚠️ 需要 |
| **设备直通** | ✅ K8s 原生注入 | ⚠️ CDI 规范注入 | ⚠️ 受控 hostPath |
| **网络隔离** | ✅ K8s CNI | ✅ bridge | ✅ bridge |
| **资源隔离** | ✅ 天然隔离 | ⚠️ 共享 DinD daemon | ⚠️ 共享 DinD daemon |
| **攻击面** | ✅ 最小 | ⚠️ SYS_ADMIN | ⚠️ privileged + seccomp |
| **seccomp** | ✅ RuntimeDefault | ✅ RuntimeDefault | ⚠️ 自定义白名单 |
| **capabilities** | ✅ drop ALL | ⚠️ 保留 SYS_ADMIN | ⚠️ 保留 SYS_ADMIN 等 |

### 6.2 功能维度

| 维度 | 方案 A (K8s Native) | 方案 B (Rootless + CDI) | 方案 C (受限特权 DinD) |
|------|---------------------|-------------------------|----------------------|
| **GPU 性能** | ✅ 原生 | ✅ 原生 | ✅ 原生 |
| **Docker CLI 兼容** | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| **DinD 隔离** | ❌ 无 DinD | ✅ 保留 | ✅ 保留 |
| **多 Job 并发** | ✅ 天然支持 | ✅ 单 DinD 支持 | ✅ 单 DinD 支持 |
| **WSL2 兼容** | ✅ 已验证 | ⚠️ 需验证 | ✅ 已验证 |

### 6.3 运维维度

| 维度 | 方案 A (K8s Native) | 方案 B (Rootless + CDI) | 方案 C (受限特权 DinD) |
|------|---------------------|-------------------------|----------------------|
| **配置复杂度** | 🟢 低 | 🔴 高 | 🟡 中 |
| **维护成本** | 🟢 低 | 🔴 高 | 🟡 中 |
| **镜像修改** | ❌ 不需要 | ✅ 需要安装 toolkit | ❌ 不需要 |
| **宿主机依赖** | ✅ Device Plugin | ⚠️ CDI + toolkit | ⚠️ 仅设备文件 |
| **升级风险** | 🟢 低 | 🔴 高 | 🟡 中 |

### 6.4 综合评分

| 方案 | 安全 (40%) | 功能 (30%) | 运维 (30%) | 总分 |
|------|-----------|-----------|-----------|------|
| **A. K8s Native** | 9/10 | 8/10 | 9/10 | **8.7/10** |
| **B. Rootless + CDI** | 7/10 | 8/10 | 5/10 | **6.7/10** |
| **C. 受限特权 DinD** | 5/10 | 9/10 | 7/10 | **6.8/10** |

---

## 7. WSL2 兼容性评估（v3.0 运行时修订）

### 7.1 🚨 关键发现：WSL2 GPU 直通特殊性

**经过实际运行时验证（2026-04-06），发现与之前所有假设完全不同的事实**：

| 维度 | 之前假设 | **实际运行时情况** |
|------|---------|-------------------|
| NVIDIA Device Plugin | ✅ 已部署 | ❌ **未部署** |
| 节点 `nvidia.com/gpu` 资源 | ✅ 已暴露 | ❌ **未暴露** |
| nvidia-container-runtime | ✅ 已配置 | ❌ **未安装** |
| `/dev/nvidia0` 设备 | ✅ 存在 | ❌ **不存在** |
| GPU 可用机制 | Device Plugin 注入 | **WSL2 `/dev/dxg` 直通** |

**实际 GPU 可用链路**：

```
Windows Host (RTX 5090, Driver 581.57)
    ↓ Hyper-V 虚拟化
WSL2 VM
    ↓ /dev/dxg (DirectX GPU Paravirtualization, 10:125)
    ↓ /usr/lib/wsl/lib/libcuda.so (WSL GPU 用户态库)
容器（无需 NVIDIA Device Plugin，无需 nvidia-container-runtime）
    ↓ docker run --device /dev/dxg:/dev/dxg -v /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro
nvidia-smi 可用，CUDA 可用
```

### 7.2 WSL2 GPU 设备清单

| 设备/路径 | 类型 | 作用 | WSL2 特殊性 |
|-----------|------|------|------------|
| `/dev/dxg` | Char Device (10:125) | DirectX GPU 网关 | ✅ 存在，WSL2 特有 |
| `/usr/lib/wsl/lib/libcuda.so` | Shared Library | CUDA 用户态库 | ✅ 存在，WSL 提供 |
| `/usr/lib/wsl/lib/libnvidia-ml.so.1` | Shared Library | NVML 库 | ✅ 存在 |
| `/dev/nvidia0` | Char Device | GPU 计算 | ❌ **WSL2 不存在** |
| `/dev/nvidiactl` | Char Device | GPU 控制 | ❌ **WSL2 不存在** |
| `/dev/nvidia-uvm` | Char Device | 统一内存 | ❌ **WSL2 不存在** |

### 7.3 各方案 WSL2 兼容性（v3.0 修订）

| 方案 | 兼容性 | 注意事项 |
|------|--------|---------|
| **A. K8s Native** | ❌ **不适用** | WSL2 无 `nvidia.com/gpu` 资源，Device Plugin 未部署 |
| **B. Rootless + CDI** | ❌ **不适用** | CDI 规范依赖 `/dev/nvidia*`，WSL2 不存在 |
| **C. DinD + WSL2 GPU 直通** | ✅ **唯一可行方案** | 仅需挂载 `/dev/dxg` + WSL GPU 库 |

### 7.4 验证命令

```bash
# 1. 检查 WSL2 GPU 设备
ls -la /dev/dxg
ls -la /usr/lib/wsl/lib/libcuda.so

# 2. 确认 NVIDIA Device Plugin 未部署
kubectl get daemonsets -n kube-system | grep nvidia  # 应为空

# 3. 确认节点无 GPU 资源
kubectl describe nodes | grep "nvidia.com/gpu"  # 应为空

# 4. 测试 WSL2 GPU 直通
docker run --rm --device /dev/dxg:/dev/dxg \
  -v /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro \
  harbor.sisys.local/sisys/dependency:l2-latest nvidia-smi

# 5. 测试 gitea-actions runner GPU 访问
kubectl exec -n gitea-actions gitea-org-runner-0 -- \
  docker run --rm --gpus all harbor.sisys.local/sisys/dependency:l2-latest nvidia-smi
```

---

## 8. 实施建议与路线图（v4.0 修订版）

### 8.1 推荐策略（宗师级评审结论）

基于 WSL2 实际运行时环境的深入验证，**方案 A（K8s Native GPU Pod）不适用**。

**唯一可行方案**：方案 C 简化版（WSL2 DinD GPU 直通）

```
Job 类型              →  Runner 方案
─────────────────────────────────────────
GPU 密集型 (AI/ML)    →  方案 C 简化版 (WSL2 DinD GPU 直通)
普通 CI (构建/测试)    →  DinD (当前配置)
Docker Buildx         →  DinD (当前配置)
安全扫描              →  DinD (当前配置)
```

**详细实施方案**：参考 `docs/deployment/wsl2-dind-gpu-passthrough-implementation-plan.md` (v4.0)

### 8.2 实施路线图

#### Phase 0: 运行时验证（0.5 天）

```bash
# 1. 验证 WSL2 GPU 设备
ls -la /dev/dxg
ls -la /usr/lib/wsl/lib/libcuda.so

# 2. 验证 gitea-actions GPU 基线
kubectl exec -n gitea-actions gitea-org-runner-0 -- \
  docker run --rm --gpus all harbor.sisys.local/sisys/dependency:l2-latest nvidia-smi

# 3. 验证 DinD 中 GPU 传递（临时挂载测试）
kubectl exec -n gitea-advacts gitea-runner-dind-0 -c docker-dind -- \
  docker run --rm --device /dev/dxg:/dev/dxg \
  -v /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro \
  harbor.sisys.local/sisys/dependency:l2-latest nvidia-smi
```

#### Phase 1: GPU DinD 部署（1 天）

```bash
# 1. 复制 harbor-robot-account Secret
kubectl get secret harbor-robot-account -n gitea-actions -o yaml | \
  sed 's/namespace: gitea-actions/namespace: gitea-advacts/' | \
  sed '/resourceVersion/d; /uid/d; /creationTimestamp/d' | \
  kubectl apply -f - -n gitea-advacts

# 2. 扩展 RBAC
kubectl apply -f deployments/gitea-runner/gitea-runner-dind-role-extended.yaml

# 3. 部署 GPU DinD StatefulSet
kubectl apply -f deployments/gitea-runner/gitea-runner-dind-gpu-statefulset.yaml

# 4. 验证 GPU
kubectl exec -n gitea-advacts gitea-runner-dind-0 -c docker-dind -- \
  docker run --rm --device /dev/dxg:/dev/dxg \
  -v /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro \
  harbor.sisys.local/sisys/dependency:l2-latest nvidia-smi
```

#### Phase 2: Workflow 验证（0.5 天）

```bash
# 触发测试 Workflow
git checkout -b test/gpu-wsl2-verify
git add .gitea/workflows/gpu-test.yml
git commit -m "test: verify GPU in DinD runner"
git push origin test/gpu-wsl2-verify
```

#### Phase 3: 安全验证（0.5 天）

- 容器逃逸测试
- seccomp profile 验证
- 性能基线对比

### 8.3 回滚方案

```bash
# 如 GPU DinD 失败，回退到 gitea-actions
kubectl scale statefulset gitea-runner-dind -n gitea-advacts --replicas=0
# Workflow 使用 runs-on: ubuntu-latest,docker,k3s,linux,gpu
```

---

## 9. 参考资料

### 9.1 官方文档

- [act_runner 官方文档](https://github.com/go-gitea/act_runner)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/index.html)
- [NVIDIA Device Plugin for K8s](https://github.com/NVIDIA/k8s-device-plugin)
- [CDI (Container Device Interface)](https://tags.cncf.io/container-device-interface)

### 9.2 项目内部文档

- `docs/deployment/dind-implementation-final-report.md` - DinD 架构最终实施报告
- `docs/deployment/CI_CD_TROUBLESHOOTING.md` - GPU 故障排查指南
- `docs/deployment/CONFIG_ASSESSMENT_REPORT.md` - 配置评估报告
- `deployments/gitea-runner/runner-k8s-executor.yaml` - K8s Executor 配置
- `deployments/gitea-runner/gitea-advacts-complete.yaml` - DinD Runner 完整配置

### 9.3 安全最佳实践

- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [seccomp profiles for containers](https://kubernetes.io/docs/tutorials/security/seccomp/)
- [NVIDIA GPU Security Best Practices](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/security.html)

---

**报告完成，等待评审与下一步指示。** 🎯
