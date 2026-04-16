# DinD 架构支持 GPU RTX 5090 分析与实施方案

**版本**: v2.0
**日期**: 2026-04-07
**作者**: SISYS Team
**状态**: 已评审（根因修订版）
**关联文档**: `wsl2-dind-gpu-passthrough-implementation-plan.md`

---

## 📋 执行摘要

本文档基于对 `gitea-advacts-complete.yaml` 配置与实际运行时环境的对比研究，分析如何在现有 DinD (Docker-in-Docker) 架构中支持 NVIDIA RTX 5090 GPU。

**核心结论**：

1. **NVML 初始化失败的根本原因不是镜像选择**，而是 WSL2 GPU 库挂载机制不传递到 DinD 容器内部
2. **`act_runner:0.3.0-dind-rootless` 镜像不是问题所在**，当前部署已以 `privileged: true` + `root` 运行
3. **WSL2 GPU 架构依赖容器运行时的特殊集成**：containerd 自动注入 GPU 库（overlay/9p），dockerd 不支持
4. **gitea-actions Runner 已通过 containerd WSL GPU 集成提供完整 GPU 支持**（基线验证通过）
5. **推荐采用分层调度策略**：GPU 任务路由到 gitea-actions，DinD 专注于构建/测试/部署

---

## 1. 运行时环境清单

### 1.1 集群环境

| 项目 | 实际值 | 验证方式 |
|------|--------|---------|
| **集群** | K3s v1.34.5+k3s1 | `kubectl version` |
| **容器运行时** | containerd://2.1.5-k3s1 | `kubectl get nodes -o wide` |
| **节点** | sisys-node-01 (16 CPU, 32GB RAM) | `kubectl describe nodes` |
| **OS/内核** | Ubuntu 22.04.5 LTS / 6.6.87.2-microsoft-standard-WSL2 | `uname -r` |
| **命名空间** | `gitea-advacts` (PSA: privileged) | `kubectl get ns` |

### 1.2 GPU 环境

| 项目 | 状态 | 详细信息 |
|------|------|---------|
| **GPU 硬件** | ✅ | NVIDIA GeForce RTX 5090 (32GB GDDR7) |
| **Windows 驱动** | ✅ | 581.57 (Blackwell 架构) |
| **CUDA 版本** | ✅ | 13.0 |
| **WSL GPU 设备** | ✅ | `/dev/dxg` (字符设备, 10:125) |
| **WSL GPU 库** | ✅ | `/usr/lib/wsl/lib/libcuda.so` (宿主机) |
| **NVIDIA Device Plugin** | ❌ | 未部署（WSL2 不兼容） |
| **节点 GPU 资源** | ❌ | 无 `nvidia.com/gpu` 暴露 |
| **nvidia-container-runtime** | ❌ | 未安装（仅 runc） |
| **GPU 持久模式** | ✅ | On |

### 1.3 Runner 状态

| Runner | 命名空间 | 副本 | 状态 | 标签 | GPU 可用 | 机制 |
|--------|---------|------|------|------|---------|------|
| gitea-org-runner | gitea-actions | 3 | Running | `ubuntu-latest,docker,k3s,linux,gpu` | ✅ | containerd → WSL GPU 自动集成 |
| gitea-runner-dind-0 | gitea-advacts | 1 | Running (2/2) | `ubuntu-latest,dind,advacts,buildx` | ❌ | DinD daemon → 无 GPU 库 |

### 1.4 gitea-actions GPU 基线验证

```
NVIDIA-SMI 580.102.01 | Driver: 581.57 | CUDA: 13.0
GPU 0: NVIDIA GeForce RTX 5090 | Memory: 1987MiB / 32607MiB | Util: 4%
```

**验证命令**：
```bash
kubectl exec -n gitea-actions gitea-org-runner-0 -- \
  docker run --rm --gpus all harbor.sisys.local/sisys/dependency:l2-latest \
  sh -c 'nvidia-smi | head -12'
```

---

## 2. gitea-advacts DinD 配置分析

### 2.1 当前 StatefulSet 架构

```
Pod: gitea-runner-dind-0 (gitea-advacts)
├── Container 1: runner (act_runner, 非特权)
│   ├── image: act_runner:0.3.0-dind-rootless
│   ├── securityContext: privileged=false, drop ALL, seccomp=RuntimeDefault
│   ├── DOCKER_HOST: tcp://127.0.0.1:2375
│   └── 功能: 接收 Workflow Job, 通过 TCP 调度 Docker
│
└── Container 2: docker-dind (Docker Daemon, 受限特权)
    ├── image: act_runner:0.3.0-dind-rootless
    ├── securityContext: privileged=true, add=[SYS_ADMIN,NET_ADMIN], drop=6项
    ├── 监听: unix:///var/run/docker.sock + tcp://127.0.0.1:2375
    ├── 存储: overlay2, docker-graph PVC 50Gi
    └── 功能: 提供独立 Docker Daemon, 支持 buildx
```

### 2.2 当前 GPU 相关配置状态

| 配置项 | 是否存在 | 说明 |
|--------|---------|------|
| `/dev/dxg` 显式 hostPath | ❌ | 未声明，但 WSL2 全局设备自动可见 |
| `/usr/lib/wsl/lib/` 挂载 | ❌ | 完全缺失（且 DinD 中该目录为空） |
| `/usr/lib/wsl/drivers/` 挂载 | ❌ | 完全缺失（且 DinD 中该目录为空） |
| GPU 相关环境变量 | ❌ | 无 `NVIDIA_VISIBLE_DEVICES` 等 |
| GPU 标签 | ❌ | Runner 标签不含 `gpu` |
| RBAC GPU 扩展 | ❌ | 无 GPU 相关权限扩展 |

### 2.3 实际运行时验证结果

```bash
# ✅ /dev/dxg 在 DinD 容器中可见（WSL2 全局设备）
kubectl exec -n gitea-advacts gitea-runner-dind-0 -c docker-dind -- ls -la /dev/dxg
# 输出: crw-rw-rw- 1 root root 10, 125 Apr  7 00:17 /dev/dxg

# ❌ /usr/lib/wsl/lib/ 在 DinD 容器中是空目录
kubectl exec -n gitea-advacts gitea-runner-dind-0 -c docker-dind -- ls -la /usr/lib/wsl/lib/
# 输出:
# total 8
# drwxr-xr-x 2 root root 4096 .
# drwxr-xr-x 4 root root 4096 ..
# ← 空！没有任何 GPU 库

# ❌ 节点无 GPU 资源声明
kubectl describe nodes | grep -i gpu
# 输出: 空（无 nvidia.com/gpu 资源）
```

---

## 3. 问题根因分析

### 3.1 NVML 初始化失败的根本原因

> **直接回答用户问题**：NVML 初始化失败**不是**因为使用了 `act_runner:0.3.0-dind-rootless` 镜像。根本原因是 **WSL2 的 GPU 库挂载（9p/overlay）不传递到 DinD 容器内部**。

#### 实验验证结果

**WSL2 宿主机**（真实环境）：
```bash
# /usr/lib/wsl/lib/ 包含完整 GPU 库（overlay 挂载）
$ ls -la /usr/lib/wsl/lib/
libcuda.so, libnvidia-ml.so.1, libnvidia-encode.so, libdxcore.so, ...
# 共 389MB+ GPU 库文件

# /usr/lib/wsl/drivers/ 包含 Windows 驱动文件（9p 挂载）
$ ls -la /usr/lib/wsl/drivers/
nv_dispsi.inf_amd64_*/libcuda.so.1.1, libnvidia-ptxjitcompiler.so.1, ...

# mount 类型
$ mount | grep -E "wsl|9p|overlay"
drivers on /usr/lib/wsl/drivers type 9p (ro, aname=drivers, trans=fd)
none on /usr/lib/wsl/lib type overlay (ro, lowerdir=/gpu_lib_packaged:/gpu_lib_inbox)
```

**DinD docker-dind 容器**（第一层嵌套）：
```bash
# /usr/lib/wsl/lib/ 和 /usr/lib/wsl/drivers/ 是**空目录**
$ ls -la /usr/lib/wsl/lib/
total 8
drwxr-xr-x 2 root root 4096 .
drwxr-xr-x 4 root root 4096 ..
# ← 空！

$ ls -la /usr/lib/wsl/drivers/
total 8
drwxr-xr-x 2 root root 4096 .
drwxr-xr-x 4 root root 4096 ..
# ← 空！

# mount 输出中**没有** 9p 或 WSL GPU overlay 挂载
$ mount | grep -E "wsl|9p|overlay"
# ← 无 WSL GPU 相关挂载
```

**gitea-actions Job 容器**（containerd 创建，通过 `--gpus all`）：
```bash
# GPU 库通过 overlay/9p 挂载到容器系统路径
$ mount | grep -E "wsl|overlay|9p"
drivers on /usr/bin/nvidia-smi type 9p (ro, aname=drivers, trans=fd)
none on /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1 type overlay (ro, lowerdir=/gpu_lib_packaged:/gpu_lib_inbox)
none on /usr/lib/x86_64-linux-gnu/libcuda.so.1 type overlay (ro, lowerdir=/gpu_lib_packaged:/gpu_lib_inbox)
drivers on /usr/lib/wsl/drivers/nv_dispsi.inf_amd64_*/libcuda.so.1.1 type 9p (ro)
drivers on /usr/lib/wsl/drivers/nv_dispsi.inf_amd64_*/libnvidia-ptxjitcompiler.so.1 type 9p (ro)
```

#### 根因链条

```
WSL2 宿主机
├── /dev/dxg (字符设备 10:125)          ← 全局可见，所有容器可访问
├── /usr/lib/wsl/lib/ (overlay 挂载)     ← 仅 WSL2 宿主机直接可见
│   └── lowerdir=/gpu_lib_packaged:/gpu_lib_inbox  ← WSLg 特殊机制
└── /usr/lib/wsl/drivers/ (9p 挂载)      ← 仅 WSL2 宿主机直接可见
    └── trans=fd, aname=drivers          ← WSLg 特殊机制

K3s containerd 创建容器时（gitea-actions --gpus all）
├── 检测到 WSL2 环境
├── 自动将 GPU 库以 overlay 形式挂载到容器系统路径 ✅
│   └── /usr/lib/x86_64-linux-gnu/libcuda.so.1
│   └── /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1
│   └── /usr/lib/x86_64-linux-gnu/libnvidia-gpucomp.so
│   └── /usr/bin/nvidia-smi (9p 直接挂载)
├── 自动挂载 /usr/lib/wsl/drivers/ (9p) ✅
├── 自动执行 ldconfig 注册 GPU 库 ✅
└── NVML 初始化成功 ✅ → PyTorch CUDA 可用 ✅

DinD docker-dind 容器（containerd 创建的第一层容器）
├── DinD 容器根文件系统是 containerd overlay
├── 但 containerd **不会**自动为 DinD 容器注入 WSL GPU 挂载
│   └── WSL GPU 注入仅在 Job Pod 级别，DinD 不是 Job Pod
├── /usr/lib/wsl/lib/ 是镜像中的空目录 ❌
├── /usr/lib/wsl/drivers/ 是镜像中的空目录 ❌
├── mount 中无 9p/overlay GPU 挂载 ❌
└── NVML 在 DinD 容器本身就无法初始化 ❌

DinD dockerd 创建嵌套 Job 容器（第二层）
├── DinD 宿主机本身就没有 GPU 库
├── --device /dev/dxg 仅传递设备节点 ✅（设备可见）
├── -v /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro 挂载空目录 ❌
├── 嵌套容器同样没有 GPU 库 ❌
└── NVML 初始化失败 ❌（找不到 libnvidia-ml.so）
```

### 3.2 `act_runner:0.3.0-dind-rootless` 镜像的影响

**结论**：该镜像**不是** NVML 失败的直接原因。

| 维度 | dind-rootless | 标准 dind | 对 GPU 的影响 |
|------|--------------|-----------|--------------|
| 默认用户 | 非 root | root | 无影响（当前以 root 运行） |
| dockerd 模式 | rootless | 标准 | 无影响（当前 `privileged: true`） |
| GPU 库内置 | 无 | 无 | 两者都没有 GPU 库 |
| 当前实际运行 | `runAsUser: 0`, `privileged: true` | 相同 | **已覆盖 rootless 限制** |

当前部署配置已经**完全覆盖**了 rootless 模式的限制：
```yaml
securityContext:
  runAsUser: 0              # root 用户
  runAsGroup: 0
  fsGroup: 0
  privileged: true          # 特权模式
```

**即使换用标准 `docker:28-dind` 镜像，NVML 初始化仍然会失败**，因为根本问题是 WSL2 GPU 挂载机制不传递到容器内部，与镜像无关。

### 3.3 三层环境 GPU 能力对比（实测）

| GPU 组件 | WSL2 宿主机 | containerd Job 容器 | DinD docker-dind | DinD 嵌套 Job |
|---------|:----------:|:------------------:|:---------------:|:------------:|
| `/dev/dxg` | ✅ | ✅ | ✅ | ✅ (--device) |
| GPU 库 (libcuda.so) | ✅ (overlay) | ✅ (overlay 注入) | ❌ (空目录) | ❌ (空目录) |
| `nvidia-smi` | ✅ | ✅ (9p 注入) | ❌ | ❌ |
| `/usr/lib/wsl/drivers/` | ✅ (9p) | ✅ (9p) | ❌ (空) | ❌ (空) |
| 9p/overlay mount | ✅ | ✅ | ❌ | ❌ |
| NVML 初始化 | ✅ | ✅ | ❌ | ❌ |
| PyTorch CUDA | ✅ | ✅ | ❌ | ❌ |
| `nvidia-smi` 查询 | ✅ | ✅ | ❌ | ❌ |

### 3.4 关键发现

1. **WSL2 GPU 库注入是容器运行时级别的行为**：只有 containerd（通过 WSLg 集成）能在创建容器时自动注入 GPU 库到系统路径（`/usr/lib/x86_64-linux-gnu/`）。dockerd 不支持此机制。

2. **9p/overlay 挂载不传递到 DinD 容器内部**：WSL2 的 9p 挂载（`/usr/lib/wsl/drivers/`）和 overlay 挂载（`/usr/lib/wsl/lib/`）仅在 WSL2 宿主机级别可见。containerd 为 DinD Pod 创建容器时，不会触发 WSL GPU 注入逻辑（因为 DinD 不是 GPU Job Pod）。

3. **DinD 容器的 "空壳" 问题**：DinD 容器虽然运行在 WSL2 宿主机上，但其根文件系统是 containerd 创建的 overlay，其中 `/usr/lib/wsl/` 目录来自镜像（空目录），不会自动继承宿主机的 9p/overlay 挂载。

4. **`--device /dev/dxg` 仅传递设备节点**：这提供了 GPU 网关通道，但没有 GPU 驱动库（`libcuda.so`, `libnvidia-ml.so` 等），NVML 无法初始化。

### 3.5 已尝试方案及结果

| 方案 | 操作 | 结果 | 说明 |
|------|------|------|------|
| 手动挂载 `/usr/lib/wsl/lib/` | `-v /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro` | ❌ | DinD 中该目录为空，挂载后仍为空 |
| 挂载 `/usr/lib/wsl/drivers/` | `hostPath: /usr/lib/wsl/drivers` | ❌ | DinD 中该目录为空 |
| Docker Wrapper 自动注入 | 包装 `docker run` 添加 GPU 参数 | ❌ | 参数正确，但源目录为空 |
| ldconfig 手动注册 | `ldconfig` 注册 GPU 库路径 | ❌ | 无库可注册 |
| 共享 containerd socket | 挂载 `/run/k3s/containerd/containerd.sock` | ✅ 理论可行 | 需改用 `ctr`/`nerdctl`，放弃 dockerd |

---

## 4. 方案对比与评估

### 4.1 候选方案

| 方案 | 名称 | 核心思路 | 可行性 |
|------|------|---------|--------|
| **A** | DinD 中注入 GPU 库 | 通过 init container 或 sidecar 将 GPU 库复制到 DinD 可访问路径 | 🟡 复杂但可能 |
| **B** | 共享 containerd socket | 挂载 containerd socket，使用 `ctr`/`nerdctl` 操作容器 | ✅ 可行（但需放弃 dockerd） |
| **C** | 分层调度策略 | GPU 任务路由到 gitea-actions，DinD 处理非 GPU 任务 | ✅ 当前最优 |
| **D** | 裸机/VM 迁移 | 迁移到裸机 Linux + NVIDIA Device Plugin + `nvidia.com/gpu` 调度 | ✅ 长期方案 |

### 4.2 方案详细对比

| 维度 | A: DinD 注入 GPU 库 | B: containerd 共享 | C: 分层调度 | D: 裸机迁移 |
|------|------------|-------------------|------------|------------|
| **nvidia-smi 可用** | ✅ (如果注入成功) | ✅ | ✅ (gitea-actions) | ✅ |
| **PyTorch CUDA 可用** | ⚠️ 不确定 | ✅ | ✅ (gitea-actions) | ✅ |
| **Docker buildx 支持** | ✅ | ❌ (需切换工具) | ✅ | ✅ |
| **DinD 隔离性** | ✅ 保留 | ❌ 丧失 | ✅ 保留 | ✅ |
| **配置复杂度** | 高 | 中 | 极低 | 高 |
| **基础设施变更** | 无 | 无 | 无 | 需新节点/集群 |
| **安全风险** | 中（hostPath 注入） | 中（containerd socket 高权限） | 无新增 | 低 |
| **维护成本** | 高 | 中 | 低 | 中 |
| **WSL2 兼容性** | ⚠️ 需持续适配 | ✅ | ✅ | N/A |
| **推荐场景** | 需要 DinD GPU 支持 | 替代 DinD 的 GPU 方案 | 当前生产推荐 | 最终目标 |

### 4.3 评分矩阵

| 标准 | 权重 | A | B | C | D |
|------|------|---|---|---|---|
| GPU 功能完整性 | 30% | 5/10 | 8/10 | 9/10 | 10/10 |
| 实施复杂度 | 20% | 4/10 | 6/10 | 10/10 | 3/10 |
| 架构兼容性 | 20% | 6/10 | 5/10 | 10/10 | 9/10 |
| 安全风险 | 15% | 6/10 | 6/10 | 10/10 | 8/10 |
| 维护成本 | 15% | 4/10 | 6/10 | 10/10 | 5/10 |
| **加权总分** | **100%** | **5.30** | **6.55** | **9.65** | **7.55** |

---

## 5. 推荐实施方案

### 5.1 策略：分层调度（方案 C）为主

```
┌──────────────────────────────────────────────────────────────────┐
│  Workflow 任务提交                                                │
│      ↓                                                           │
│  ┌─────────────────────────────────────────────────────┐         │
│  │ runs-on 标签选择 Runner                              │         │
│  ├─────────────────────────────────────────────────────┤         │
│  │ GPU 训练/推理/计算密集型:                             │         │
│  │   runs-on: ubuntu-latest,docker,k3s,linux,gpu       │         │
│  │   → gitea-actions Runner (containerd, 完整 GPU)      │ → ✅  │
│  │                                                      │         │
│  │ DinD 特色任务 (镜像构建/集成测试/部署):                │         │
│  │   runs-on: ubuntu-latest,dind,advacts,buildx        │         │
│  │   → gitea-advacts Runner (DinD, 构建加速)            │ → ✅  │
│  └─────────────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 方案 A 探索：在 DinD 中注入 GPU 库

> **适用场景**：如果需要在 DinD 环境中获取 GPU 信息（nvidia-smi、驱动版本等），不需要 CUDA 运行时。

由于 DinD 容器中 `/usr/lib/wsl/lib/` 是空目录，核心挑战是如何将宿主机的 GPU 库传递到 DinD 容器内部。

#### 5.2.1 思路：Init Container 复制 GPU 库

```yaml
spec:
  initContainers:
    - name: gpu-lib-injector
      image: harbor.sisys.local/sisys/dependency:l2-latest
      command:
        - sh -c - |
          # 从宿主机复制 GPU 库到共享 volume
          if [ -d /usr/lib/wsl/lib ] && [ "$(ls -A /usr/lib/wsl/lib)" ]; then
            cp -a /usr/lib/wsl/lib/* /gpu-libs/
            echo "GPU libs copied successfully"
            ls -la /gpu-libs/
          else
            echo "WARNING: No GPU libs found on host"
          fi
      volumeMounts:
        - name: gpu-libs-staging
          mountPath: /gpu-libs
      securityContext:
        privileged: true  # 需要访问 hostPath

  containers:
    - name: docker-dind
      # ... 现有配置 ...
      volumeMounts:
        # ... 现有挂载 ...
        - name: gpu-libs-staging
          mountPath: /usr/lib/wsl/lib
          readOnly: true

  volumes:
    - name: gpu-libs-staging
      emptyDir:
        sizeLimit: 500Mi
```

**限制**：
- 此方法可复制 `/usr/lib/wsl/lib/` 中的 GPU 库
- 但 **9p 挂载的 `/usr/lib/wsl/drivers/`** 中的文件**无法复制**（9p 在容器内不可见）
- NVML 可能仍需要 9p 挂载的驱动文件（`libnvidia-ptxjitcompiler.so` 等）
- **不能保证 PyTorch CUDA 可用**

#### 5.2.2 思路二：直接挂载宿主机 GPU 库路径

```yaml
volumeMounts:
  - name: host-gpu-libs
    mountPath: /usr/lib/x86_64-linux-gnu/nvidia
    readOnly: true

volumes:
  - name: host-gpu-libs
    hostPath:
      path: /usr/lib/x86_64-linux-gnu
      type: Directory
```

**问题**：DinD 容器中挂载的是宿主机的完整 `/usr/lib/x86_64-linux-gnu/`，其中包含 GPU 库（因为宿主机有 overlay 挂载）。但嵌套 Job 容器通过 docker-dind 访问时，这些库的路径映射可能不一致。

### 5.3 中期：containerd socket 共享方案（方案 B 评估）

> **适用场景**：如果需要在 DinD 环境中执行 CUDA 计算任务，且愿意放弃 dockerd。

#### 核心变更

```yaml
# 替代 docker-dind 容器
- name: containerd-access
  image: harbor.sisys.local/sisys/tools/gitea/act_runner:0.3.0-dind-rootless
  securityContext:
    privileged: false
  volumeMounts:
    - name: containerd-socket
      mountPath: /run/k3s/containerd/containerd.sock
  command:
    - sh -c - |
      # 安装 nerdctl
      # 使用 nerdctl 操作 containerd（复用 WSL GPU 集成）
      nerdctl run --rm --gpus all <image> nvidia-smi

volumes:
  - name: containerd-socket
    hostPath:
      path: /run/k3s/containerd/containerd.sock
      type: Socket
```

**注意事项**：
- 此方案实质上放弃了 DinD，直接复用 K3s containerd
- 需要评估与现有 DinD 构建流水线的兼容性
- `nerdctl` 的 Docker Compose 兼容性需验证

### 5.4 长期：裸机 Linux 迁移（方案 D）

> **适用场景**：生产环境需要完整 K8s GPU 调度能力（资源声明、自动调度、MIG 隔离）。

#### 目标架构

```
┌──────────────────────────────────────────────────────────────────┐
│  裸机/VM Linux 节点池                                             │
├──────────────────────────────────────────────────────────────────┤
│  NVIDIA Driver + Container Toolkit + NVIDIA Device Plugin        │
├──────────────────────────────────────────────────────────────────┤
│  K8s 节点暴露资源: nvidia.com/gpu: 1                             │
├──────────────────────────────────────────────────────────────────┤
│  Pod GPU 资源声明:                                               │
│    resources:                                                    │
│      limits:                                                     │
│        nvidia.com/gpu: "1"                                       │
│      requests:                                                   │
│        nvidia.com/gpu: "1"                                       │
├──────────────────────────────────────────────────────────────────┤
│  自动调度: K8s 将 GPU Pod 调度到 GPU 节点                         │
│  设备注入: Device Plugin 自动注入 /dev/nvidia* 设备              │
│  CUDA 可用: PyTorch/TensorFlow 开箱即用                         │
└──────────────────────────────────────────────────────────────────┘
```

#### 迁移步骤（概要）

1. 部署裸机 GPU 节点（或支持 GPU 的 VM 提供商）
2. 安装 NVIDIA Driver + Container Toolkit
3. 部署 NVIDIA Device Plugin DaemonSet
4. 配置节点标签 `nvidia.com/gpu.present=true`
5. 验证 `kubectl describe nodes` 暴露 `nvidia.com/gpu` 资源
6. 将 gitea-advacts Runner 迁移到新节点（或多集群部署）
7. 更新 Workflow `runs-on` 标签选择器

---

## 6. RTX 5090 特定考量

### 6.1 GPU 特性

| 特性 | RTX 5090 | 影响 |
|------|---------|------|
| **架构** | Blackwell (GB202) | 需要 Driver ≥ 570.x ✅ |
| **CUDA Compute Capability** | 12.0 | 需要 CUDA Toolkit ≥ 12.8 |
| **显存** | 32GB GDDR7 | 支持大模型训练/推理 ✅ |
| **MIG 支持** | ❌ 不支持（GeForce 系列均不支持） | 无法硬件级 GPU 隔离 |
| **NVLink** | ❌ 取消（消费级） | 无法多卡互联 |
| **持久模式** | 支持 | 已启用 ✅ |

### 6.2 无 MIG 的调度影响

RTX 5090 **不支持 MIG (Multi-Instance GPU)**，意味着：

| 问题 | 影响 | 缓解策略 |
|------|------|---------|
| **多任务争用** | 多个 Pod 共享同一 GPU | 软件级排队 + 优先级调度 |
| **无硬件隔离** | 一个 Pod 可影响其他 Pod | ResourceQuota + LimitRange |
| **显存竞争** | 32GB 共享 | 监控显存使用，限制单任务上限 |
| **算力竞争** | 480W TDP 共享 | 无硬件限制，需应用层控制 |

**推荐**：
- 单 Runner 副本策略（当前已实施）
- GPU 任务队列化（通过 Gitea Workflow 串行化）
- 定期监控 GPU 利用率和显存使用

### 6.3 性能基线

```bash
# GPU 计算基准测试（4096x4096 矩阵乘法）
kubectl exec -n gitea-actions gitea-org-runner-0 -- \
  docker run --rm --gpus all harbor.sisys.local/sisys/dependency:l2-latest \
  python3 -c "
import torch, time
x = torch.randn(4096, 4096, device='cuda')
y = torch.randn(4096, 4096, device='cuda')
torch.cuda.synchronize()
start = time.time()
z = x @ y
torch.cuda.synchronize()
print(f'4096x4096 Matrix Multiplication: {time.time()-start:.4f}s')
"
```

---

## 7. 实施检查清单

### 7.1 立即可执行（方案 C 分层调度）

- [ ] 文档化 GPU 任务路由策略
- [ ] 创建 GPU 计算 Workflow 模板（指向 gitea-actions）
- [ ] 创建 DinD 构建/测试 Workflow 模板
- [ ] 更新团队文档说明两种 Runner 的用途区分

### 7.2 中期探索（方案 A GPU 库注入）

- [ ] 测试 Init Container GPU 库复制方案
- [ ] 验证复制后的 GPU 库在嵌套容器中是否可用
- [ ] 评估 9p 驱动文件依赖程度
- [ ] 如可行，创建 DinD GPU 查询 Workflow 模板

### 7.3 中期评估（方案 B）

- [ ] 评估 `nerdctl` 与现有 DinD 构建流水线的兼容性
- [ ] 验证 containerd socket 共享的安全影响
- [ ] 制定 DinD → containerd 迁移计划（如选择此方案）
- [ ] 测试 CUDA 计算任务在 nerdctl 下的可用性

### 7.4 长期规划（方案 D）

- [ ] 评估裸机 GPU 节点方案（自建 vs 云服务）
- [ ] 制定 NVIDIA Device Plugin 部署计划
- [ ] 评估多 GPU 节点池的调度策略
- [ ] 规划 gitea-advacts 迁移路径

---

## 8. 风险矩阵

| 风险 | 概率 | 影响 | 严重度 | 缓解措施 |
|------|------|------|--------|---------|
| WSL2 更新破坏 GPU 直通 | 中 | 高 | 🔴 | 监控 WSL 更新日志，回滚机制 |
| GPU 库版本不匹配 | 低 | 中 | 🟡 | 使用 WSL 官方路径，定期更新 |
| 多 Runner GPU 争用 | 中 | 中 | 🟡 | 单副本策略 + ResourceQuota |
| 恶意容器滥用 GPU | 低 | 中 | 🟡 | 安全上下文约束 + 监控 |
| DinD 嵌套容器 GPU 不可用 | 高 | 中 | 🟡 | 路由到 gitea-actions（方案 C） |
| WSL2 9p 文件系统变更 | 低 | 高 | 🔴 | 关注微软 WSLg 更新 |
| GPU 库注入方案不兼容 | 高 | 中 | 🟡 | 方案 A 仅作为探索方向 |

---

## 9. 参考资源

| 资源 | 路径/链接 | 说明 |
|------|----------|------|
| WSL2 DinD GPU 直通实施方案 | `docs/deployment/wsl2-dind-gpu-passthrough-implementation-plan.md` | 详细实施方案（v5.1） |
| Gitea AdvActs 完整配置 | `deploy/kubernetes/gitea-runner/gitea-advacts-complete.yaml` | 当前 DinD 配置 |
| Gitea Runner 配置 Story | `_bmad-output/implementation-artifacts/stories/0-8-gitea-runner-configuration.md` | Runner 配置文档 |
| K8s GPU 调度参考 | `deploy/kubernetes/k8s/deployment.yaml` | K8s GPU 资源声明示例 |

---

## 附录 A：GPU Workflow 模板

### A.1 GPU 计算任务（gitea-actions，推荐）

```yaml
name: GPU Compute Task
on:
  push:
    branches: [main]

jobs:
  gpu-compute:
    runs-on: ubuntu-latest,docker,k3s,linux,gpu

    steps:
      - name: GPU Device Information
        run: |
          docker run --rm --gpus all \
            harbor.sisys.local/sisys/dependency:l2-latest \
            nvidia-smi

      - name: PyTorch CUDA Verification
        run: |
          docker run --rm --gpus all \
            harbor.sisys.local/sisys/dependency:l2-latest \
            python3 -c "
            import torch
            print(f'PyTorch version: {torch.__version__}')
            print(f'CUDA available: {torch.cuda.is_available()}')
            print(f'GPU name: {torch.cuda.get_device_name(0)}')
            "
```

### A.2 DinD 构建任务（gitea-advacts，无 GPU）

```yaml
name: Docker Build
on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest,dind,advacts,buildx

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Build Image
        run: |
          docker buildx build \
            --push \
            -t harbor.sisys.local/sisys/myapp:latest \
            .
```

---

## 附录 B：关键命令速查

```bash
# ========== GPU 环境验证 ==========
# 宿主机 GPU 设备
ls -la /dev/dxg
ls -la /usr/lib/wsl/lib/

# 集群 GPU 资源
kubectl describe nodes | grep -i gpu   # 预期: 空 (WSL2)

# gitea-actions GPU 基线
kubectl exec -n gitea-actions gitea-org-runner-0 -- \
  docker run --rm --gpus all harbor.sisys.local/sisys/dependency:l2-latest nvidia-smi

# ========== DinD GPU 诊断 ==========
# DinD 中 /dev/dxg 可见性
kubectl exec -n gitea-advacts gitea-runner-dind-0 -c docker-dind -- ls -la /dev/dxg

# DinD 中 GPU 库检查
kubectl exec -n gitea-advacts gitea-runner-dind-0 -c docker-dind -- ls -la /usr/lib/wsl/lib/
# 预期: 空目录（根因确认）

# DinD mount 信息
kubectl exec -n gitea-advacts gitea-runner-dind-0 -c docker-dind -- mount | grep -E "wsl|9p|overlay"
# 预期: 无 WSL GPU 相关挂载

# ========== 部署/回滚 ==========
kubectl apply -f deploy/kubernetes/gitea-runner/gitea-advacts-complete.yaml
kubectl rollout restart statefulset gitea-runner-dind -n gitea-advacts
kubectl wait --for=condition=Ready pod -l app=gitea-runner-dind -n gitea-advacts --timeout=300s

# 回滚
kubectl rollout undo statefulset gitea-runner-dind -n gitea-advacts

# ========== 监控 ==========
watch -n 5 'kubectl exec -n gitea-actions gitea-org-runner-0 -- \
  docker run --rm --gpus all harbor.sisys.local/sisys/dependency:l2-latest \
  nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader'
```

---

**文档版本**: v2.0（根因修订版） | **最后更新**: 2026-04-07 | **状态**: 已评审
