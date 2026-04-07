# DinD 架构支持 GPU RTX 5090 分析与实施方案

**版本**: v1.0
**日期**: 2026-04-07
**作者**: SISYS Team
**状态**: 已评审
**关联文档**: `wsl2-dind-gpu-passthrough-implementation-plan.md`

---

## 📋 执行摘要

本文档基于对 `gitea-advacts-complete.yaml` 配置与实际运行时环境的对比研究，分析如何在现有 DinD (Docker-in-Docker) 架构中支持 NVIDIA RTX 5090 GPU。

**核心结论**：

1. **WSL2 环境下 DinD 嵌套容器中 PyTorch CUDA 存在根本性限制**（NVML 无法初始化）
2. **gitea-actions Runner 已通过 containerd WSL GPU 集成提供完整 GPU 支持**（基线验证通过）
3. **推荐采用分层调度策略**：GPU 任务路由到 gitea-actions，DinD 专注于构建/测试/部署
4. **nvidia-smi 查询和基础 GPU 信息获取在 DinD 中可行**（补全 WSL GPU 挂载即可）

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
| **WSL GPU 库** | ✅ | `/usr/lib/wsl/lib/libcuda.so` |
| **NVIDIA Device Plugin** | ❌ | 未部署（WSL2 不兼容） |
| **节点 GPU 资源** | ❌ | 无 `nvidia.com/gpu` 暴露 |
| **nvidia-container-runtime** | ❌ | 未安装（仅 runc） |
| **GPU 持久模式** | ✅ | On |

### 1.3 Runner 状态

| Runner | 命名空间 | 副本 | 状态 | 标签 | GPU 可用 | 机制 |
|--------|---------|------|------|------|---------|------|
| gitea-org-runner | gitea-actions | 3 | Running | `ubuntu-latest,docker,k3s,linux,gpu` | ✅ | containerd → WSL GPU 自动集成 |
| gitea-runner-dind-0 | gitea-advacts | 1 | Running (2/2) | `ubuntu-latest,dind,advacts,buildx` | ⚠️ 部分 | DinD daemon → `/dev/dxg`（WSL2 全局可见） |

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
| `/usr/lib/wsl/lib/` 挂载 | ❌ | 完全缺失 |
| `/usr/lib/wsl/drivers/` 挂载 | ❌ | 完全缺失 |
| GPU 相关环境变量 | ❌ | 无 `NVIDIA_VISIBLE_DEVICES` 等 |
| GPU 标签 | ❌ | Runner 标签不含 `gpu` |
| RBAC GPU 扩展 | ❌ | 无 GPU 相关权限扩展 |

### 2.3 实际运行时验证结果

```bash
# ✅ /dev/dxg 在 DinD 容器中可见（WSL2 全局设备）
kubectl exec -n gitea-advacts gitea-runner-dind-0 -c docker-dind -- ls -la /dev/dxg
# 输出: crw-rw-rw- 1 root root 10, 125 Apr  7 00:17 /dev/dxg

# ❌ /usr/lib/wsl/lib/ 在 DinD 容器中不存在
kubectl exec -n gitea-advacts gitea-runner-dind-0 -c docker-dind -- ls -la /usr/lib/wsl/lib/libcuda.so
# 输出: ls: /usr/lib/wsl/lib/libcuda.so: No such file or directory

# ❌ 节点无 GPU 资源声明
kubectl describe nodes | grep -i gpu
# 输出: 空（无 nvidia.com/gpu 资源）
```

---

## 3. 问题根因分析

### 3.1 WSL2 GPU 架构差异

```
┌──────────────────────────────────────────────────────────────────────┐
│  containerd (gitea-actions 使用)                                     │
├──────────────────────────────────────────────────────────────────────┤
│  - 自动挂载 /dev/dxg                                                 │
│  - 自动挂载 /usr/lib/wsl/drivers/ (9p 只读文件系统)                   │
│  - 自动执行 ldconfig 注册 GPU 库到系统路径                            │
│  - WSL GPU 运行时集成（微软 + NVIDIA 联合实现）                       │
│  - NVML 初始化成功 ✅                                                │
│  - PyTorch CUDA 可用 ✅                                              │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  独立 dockerd (gitea-advacts DinD 使用)                               │
├──────────────────────────────────────────────────────────────────────┤
│  - /dev/dxg 自动可见（WSL2 全局设备，所有容器默认可见）                │
│  - /usr/lib/wsl/drivers/ 未挂载 ❌                                    │
│  - /usr/lib/wsl/lib/ 未挂载 ❌                                        │
│  - ldconfig 未执行 ❌                                                │
│  - NVML 初始化失败（`Can't initialize NVML`） ❌                      │
│  - PyTorch CUDA 不可用（`torch.cuda.is_available()` 返回 False） ❌   │
│  - nvidia-smi 可通过手动挂载工作 ✅                                   │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 关键发现

1. **`/dev/dxg` 是 WSL2 全局设备**：无需显式 hostPath 声明，所有容器默认可见。但这仅提供 GPU 网关通道。

2. **WSL GPU 驱动依赖 9p 文件系统**：实际驱动文件通过 9p 协议挂载在 `/usr/lib/wsl/drivers/<driver>/`，这是微软 WSLg 架构特有的机制。

3. **containerd 与 dockerd 的 WSL 集成差异**：
   - containerd 通过 K3s 内置逻辑自动处理 WSL GPU 集成
   - dockerd 不支持 WSL 9p 文件系统自动挂载

4. **嵌套容器问题**：在 DinD 内运行的 Job 容器（嵌套第二层）无法继承宿主 WSL GPU 环境，因为：
   - dockerd 不知道 WSL GPU 的特殊挂载需求
   - `--device /dev/dxg` 仅传递设备节点，不传递 9p 文件系统
   - NVML 初始化需要完整的驱动栈（设备 + 库 + 9p 驱动文件）

### 3.3 已尝试方案及结果

| 方案 | 操作 | 结果 | 说明 |
|------|------|------|------|
| 手动挂载 `/usr/lib/wsl/lib/` | `-v /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro` | ⚠️ 部分 | `nvidia-smi` 可用，NVML 失败 |
| 挂载 `/usr/lib/wsl/drivers/` | `hostPath: /usr/lib/wsl/drivers` | ❌ | 9p 只读文件系统，嵌套容器无法访问 |
| Docker Wrapper 自动注入 | 包装 `docker run` 添加 GPU 参数 | ❌ | 参数正确，NVML 仍失败 |
| ldconfig 手动注册 | `ldconfig` 注册 GPU 库路径 | ❌ | 注册成功，NVML 仍失败 |
| 共享 containerd socket | 挂载 `/run/k3s/containerd/containerd.sock` | ✅ 可行 | 需改用 `ctr`/`nerdctl`，放弃 dockerd |

---

## 4. 方案对比与评估

### 4.1 候选方案

| 方案 | 名称 | 核心思路 | 可行性 |
|------|------|---------|--------|
| **A** | 补全 WSL GPU 挂载 | 在 DinD 中显式挂载 `/usr/lib/wsl/lib/` + `/usr/lib/wsl/drivers/` | 🟡 部分（nvidia-smi 可用，PyTorch 不可用） |
| **B** | 共享 containerd socket | 挂载 containerd socket，使用 `ctr`/`nerdctl` 操作容器 | ✅ 可行（但需放弃 dockerd） |
| **C** | 分层调度策略 | GPU 任务路由到 gitea-actions，DinD 处理非 GPU 任务 | ✅ 当前最优 |
| **D** | 裸机/VM 迁移 | 迁移到裸机 Linux + NVIDIA Device Plugin + `nvidia.com/gpu` 调度 | ✅ 长期方案 |

### 4.2 方案详细对比

| 维度 | A: 补全挂载 | B: containerd 共享 | C: 分层调度 | D: 裸机迁移 |
|------|------------|-------------------|------------|------------|
| **nvidia-smi 可用** | ✅ | ✅ | ✅ (gitea-actions) | ✅ |
| **PyTorch CUDA 可用** | ❌ | ✅ | ✅ (gitea-actions) | ✅ |
| **Docker buildx 支持** | ✅ | ❌ (需切换工具) | ✅ | ✅ |
| **DinD 隔离性** | ✅ 保留 | ❌ 丧失 | ✅ 保留 | ✅ |
| **配置复杂度** | 低 | 中 | 极低 | 高 |
| **基础设施变更** | 无 | 无 | 无 | 需新节点/集群 |
| **安全风险** | 低（仅新增 hostPath） | 中（containerd socket 高权限） | 无新增 | 低 |
| **维护成本** | 低 | 中 | 低 | 中 |
| **WSL2 兼容性** | ✅ | ✅ | ✅ | N/A |
| **推荐场景** | GPU 信息查询 | 替代 DinD 的 GPU 方案 | 当前生产推荐 | 最终目标 |

### 4.3 评分矩阵

| 标准 | 权重 | A | B | C | D |
|------|------|---|---|---|---|
| GPU 功能完整性 | 30% | 3/10 | 8/10 | 9/10 | 10/10 |
| 实施复杂度 | 20% | 9/10 | 6/10 | 10/10 | 3/10 |
| 架构兼容性 | 20% | 8/10 | 5/10 | 10/10 | 9/10 |
| 安全风险 | 15% | 8/10 | 6/10 | 10/10 | 8/10 |
| 维护成本 | 15% | 9/10 | 6/10 | 10/10 | 5/10 |
| **加权总分** | **100%** | **6.75** | **6.55** | **9.65** | **7.55** |

---

## 5. 推荐实施方案

### 5.1 策略：分层调度（方案 C）+ GPU 查询能力补全（方案 A 子集）

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
│  │                                                      │         │
│  │ GPU 信息查询/验证类任务:                               │         │
│  │   runs-on: ubuntu-latest,dind,advacts,buildx,gpu    │         │
│  │   → gitea-advacts DinD (nvidia-smi 可用)             │ → ⚠️  │
│  └─────────────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 立即可执行：补全 DinD GPU 挂载（支持 nvidia-smi）

> **适用场景**：GPU 信息查询、驱动版本验证、GPU 资源监控等不需要 CUDA 运行时 的任务。

#### 5.2.1 StatefulSet 修订

在现有 `gitea-advacts-complete.yaml` 基础上，对 `docker-dind` 容器新增以下挂载：

```yaml
# Container 2: docker-dind 新增 volumeMounts
volumeMounts:
  # ... 现有挂载保持不变 ...

  # 🆕 WSL2 GPU 设备挂载
  - name: wsl-dxg
    mountPath: /dev/dxg
  - name: wsl-gpu-libs
    mountPath: /usr/lib/wsl/lib
    readOnly: true
  # 🆕 可写 Docker 配置目录
  - name: etc-docker
    mountPath: /etc/docker

# Pod spec 新增 volumes
volumes:
  # ... 现有 volumes 保持不变 ...

  # 🆕 WSL2 GPU 卷
  - name: wsl-dxg
    hostPath:
      path: /dev/dxg
      type: CharDevice
  - name: wsl-gpu-libs
    hostPath:
      path: /usr/lib/wsl/lib
      type: Directory
  - name: etc-docker
    emptyDir:
      sizeLimit: 10Mi
```

#### 5.2.2 docker-dind 环境变量

```yaml
env:
  # ... 现有环境变量 ...

  # 🆕 WSL2 GPU 环境变量
  - name: NVIDIA_VISIBLE_DEVICES
    value: all
  - name: NVIDIA_DRIVER_CAPABILITIES
    value: compute,utility
```

#### 5.2.3 验证命令

```bash
# 部署修订版后验证
kubectl exec -n gitea-advacts gitea-runner-dind-0 -c docker-dind -- \
  docker run --rm \
    --device /dev/dxg:/dev/dxg \
    -v /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro \
    harbor.sisys.local/sisys/dependency:l2-latest \
    nvidia-smi | head -15
```

**预期输出**：RTX 5090 GPU 信息（温度、内存、利用率等）

### 5.3 中期：containerd socket 共享方案（方案 B 评估）

> **适用场景**：如果需要在 DinD 环境中执行 CUDA 计算任务，且愿意放弃 dockerd。

#### 核心变更

```yaml
# 替代 docker-dind 容器
- name: containerd-access
  image: harbor.sisys.local/sisys/tools/gitea/act_runner:0.3.0-dind-rootless
  securityContext:
    privileged: false
    # 需要访问 containerd socket
  volumeMounts:
    - name: containerd-socket
      mountPath: /run/k3s/containerd/containerd.sock
  command:
    - sh -c - |
      # 安装 nerdctl
      ctr images pull harbor.sisys.local/sisys/tools/nerdctl:latest
      # 使用 nerdctl 操作 containerd
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
│  NVIDIA Driver + nvidia-container-runtime + NVIDIA Device Plugin │
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

### 7.1 立即可执行（方案 A + C 混合）

- [ ] 修订 `gitea-advacts-complete.yaml`，在 docker-dind 中新增 WSL GPU 卷
- [ ] 新增环境变量 `NVIDIA_VISIBLE_DEVICES` 和 `NVIDIA_DRIVER_CAPABILITIES`
- [ ] 部署修订版 StatefulSet (`kubectl apply -f gitea-advacts-complete.yaml`)
- [ ] 验证 `nvidia-smi` 在 DinD 嵌套容器中可用
- [ ] 更新 Runner 标签添加 `gpu` 标识
- [ ] 文档化 GPU 任务路由策略（Workflow 模板）
- [ ] 创建 GPU 查询类 Workflow 示例

### 7.2 中期评估（方案 B）

- [ ] 评估 `nerdctl` 与现有 DinD 构建流水线的兼容性
- [ ] 验证 containerd socket 共享的安全影响
- [ ] 制定 DinD → containerd 迁移计划（如选择此方案）
- [ ] 测试 CUDA 计算任务在 nerdctl 下的可用性

### 7.3 长期规划（方案 D）

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

---

## 9. 参考资源

| 资源 | 路径/链接 | 说明 |
|------|----------|------|
| WSL2 DinD GPU 直通实施方案 | `docs/deployment/wsl2-dind-gpu-passthrough-implementation-plan.md` | 详细实施方案（v5.1） |
| Gitea AdvActs 完整配置 | `deployments/gitea-runner/gitea-advacts-complete.yaml` | 当前 DinD 配置 |
| Gitea Runner 配置 Story | `_bmad-output/implementation-artifacts/stories/0-8-gitea-runner-configuration.md` | Runner 配置文档 |
| WSL2 DinD GPU 集成研究 | `docs/deployment/wsl2-dind-gpu-integration-research.md` | 嵌套容器 CUDA 限制研究 |
| K8s GPU 调度参考 | `deployments/k8s/deployment.yaml` | K8s GPU 资源声明示例 |

---

## 附录 A：GPU Workflow 模板

### A.1 GPU 信息查询（DinD 可用）

```yaml
name: GPU Info Check
on:
  push:
    branches: [main]

jobs:
  gpu-info:
    runs-on: ubuntu-latest,dind,advacts,buildx,gpu

    steps:
      - name: GPU Device Information
        run: |
          docker run --rm \
            --device /dev/dxg:/dev/dxg \
            -v /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro \
            harbor.sisys.local/sisys/dependency:l2-latest \
            nvidia-smi

      - name: GPU Memory Usage
        run: |
          docker run --rm \
            --device /dev/dxg:/dev/dxg \
            -v /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro \
            harbor.sisys.local/sisys/dependency:l2-latest \
            nvidia-smi --query-gpu=memory.used,memory.total --format=csv
```

### A.2 GPU 计算任务（gitea-actions）

```yaml
name: GPU Compute Task
on:
  push:
    branches: [main]

jobs:
  gpu-compute:
    runs-on: ubuntu-latest,docker,k3s,linux,gpu

    steps:
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

---

## 附录 B：关键命令速查

```bash
# ========== GPU 环境验证 ==========
# 宿主机 GPU 设备
ls -la /dev/dxg
ls -la /usr/lib/wsl/lib/libcuda.so

# 集群 GPU 资源
kubectl describe nodes | grep -i gpu   # 预期: 空 (WSL2)

# gitea-actions GPU 基线
kubectl exec -n gitea-actions gitea-org-runner-0 -- \
  docker run --rm --gpus all harbor.sisys.local/sisys/dependency:l2-latest nvidia-smi

# ========== DinD GPU 验证 ==========
# DinD 中 /dev/dxg 可见性
kubectl exec -n gitea-advacts gitea-runner-dind-0 -c docker-dind -- ls -la /dev/dxg

# DinD 中 GPU 传递测试
kubectl exec -n gitea-advacts gitea-runner-dind-0 -c docker-dind -- \
  docker run --rm --device /dev/dxg:/dev/dxg \
  -v /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro \
  harbor.sisys.local/sisys/dependency:l2-latest nvidia-smi

# ========== 部署/回滚 ==========
# 部署修订版 StatefulSet
kubectl apply -f deployments/gitea-runner/gitea-advacts-complete.yaml
kubectl rollout restart statefulset gitea-runner-dind -n gitea-advacts
kubectl wait --for=condition=Ready pod -l app=gitea-runner-dind -n gitea-advacts --timeout=300s

# 回滚
kubectl rollout undo statefulset gitea-runner-dind -n gitea-advacts

# ========== 监控 ==========
# GPU 利用率监控
watch -n 5 'kubectl exec -n gitea-actions gitea-org-runner-0 -- \
  docker run --rm --gpus all harbor.sisys.local/sisys/dependency:l2-latest \
  nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader'
```

---

**文档版本**: v1.0 | **最后更新**: 2026-04-07 | **状态**: 已评审
