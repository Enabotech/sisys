# K3S 部署完整指南

**文档版本:** 3.0.0
**更新日期:** 2026-03-12
**适用环境:** WSL2 Ubuntu 22.04 / Ubuntu 22.04 LTS
**K3S 版本:** v1.34.5

---

## 📋 目录

1. [概述](#概述)
2. [方案选择](#方案选择)
3. [前置准备](#前置准备)
4. [单节点部署](#单节点部署)
5. [多节点部署](#多节点部署)
6. [多集群管理](#多集群管理)
7. [运维管理](#运维管理)
8. [故障排查](#故障排查)
9. [性能优化](#性能优化)
10. [FAQ](#faq)

---

## 概述

本指南提供 K3S 集群的完整部署方案，包含：
- **单节点集群** - 适合个人开发、功能测试
- **多节点集群** - 适合团队开发、高可用测试
- **多集群管理** - 支持同时管理多个集群

**技术栈:**
- K3S v1.34.5
- local-path-provisioner (K3S 内置存储)
- Traefik v3.x (反向代理)

---

## 方案选择

| 方案 | 适用场景 | 优点 | 限制 | 推荐配置 |
|------|---------|------|------|---------|
| **单节点** | 个人开发、功能测试 | 简单快速、资源占用少 | 无法测试多节点功能 | 4GB+ RAM, 2 核 + |
| **多节点** | 团队开发、高可用测试 | 模拟真实集群、测试节点故障 | 资源占用较多 | 8GB+ RAM, 4 核 + |

**推荐:**
- 个人开发：单节点（1 Server）
- 团队开发：多节点（1 Server + 2 Agent）
- 高可用测试：多节点（3 Server + N Agent）

---

## 前置准备

### 硬件要求

| 资源 | 单节点最低 | 单节点推荐 | 多节点最低 | 多节点推荐 |
|------|-----------|-----------|-----------|-----------|
| **内存** | 4GB | 8GB+ | 8GB | 16GB+ |
| **CPU** | 2 核 | 4 核+ | 4 核 | 8 核+ |
| **磁盘** | 20GB | 50GB+ | 50GB | 100GB+ |

### 软件要求

```bash
# 检查 Docker
docker --version  # 需要 Docker 20.10+

# 检查 WSL2 (Windows)
wsl --version  # 需要 WSL2

# 检查 kubectl（可选）
kubectl version --client
```

### 安装 Docker（如果未安装）

**Ubuntu/Debian:**
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

**Windows 11 + WSL2:**
```powershell
# 在 PowerShell 中执行
wsl --install
wsl --set-default-version 2

# 然后在 WSL2 中安装 Docker
curl -fsSL https://get.docker.com | sh
```

---

## 单节点部署

### 快速部署（推荐）

```bash
# 使用自动化脚本
cd scripts/deployment/k3s
sudo ./install.sh

# 验证安装
kubectl get nodes
# 输出：NAME       STATUS   ROLES                  AGE   VERSION
#       sisys-pc   Ready    control-plane,master   1m    v1.34.5+k3s1
```

### 手动部署

```bash
# 下载并运行安装脚本
curl -sfL https://get.k3s.io | sh -

# 配置 kubectl 别名
echo 'alias kubectl="sudo kubectl"' >> ~/.bashrc
source ~/.bashrc

# 验证安装
kubectl get nodes
```

### 配置 K3S（可选）

针对 13700K + 32G RAM 优化：

```bash
# 创建 K3S 配置文件
sudo mkdir -p /etc/rancher/k3s

cat > /etc/rancher/k3s/config.yaml <<EOF
# 节点配置
node-name: sisys-pc
cluster-init: true

# 网络配置
flannel-backend: vxlan
disable-network-policy: false

# 禁用不需要的组件
disable:
  - traefik
  - servicelb
  - metrics-server

# 资源限制（针对 32G RAM 优化）
etcd-memory-limit: 2048Mi
apiserver-memory-limit: 2048Mi
controller-manager-memory-limit: 1024Mi
scheduler-memory-limit: 512Mi

# Kubelet 配置
kubelet-arg:
  - max-pods=110

# 系统预留资源
system-reserved:
  - cpu=2000m
  - memory=4Gi

kube-reserved:
  - cpu=1000m
  - memory=2Gi
EOF

# 重启 K3S 服务
sudo systemctl restart k3s
```

### 资源分配建议

| 硬件配置 | etcd 内存 | API Server | Controller | Scheduler | 可用 Pod |
|---------|----------|-----------|------------|-----------|---------|
| 8 核 + 16G | 1Gi | 1Gi | 512Mi | 256Mi | ~50 |
| 16 核 + 32G | 2Gi | 2Gi | 1Gi | 512Mi | ~110 |
| 32 核 + 64G | 4Gi | 4Gi | 2Gi | 1Gi | ~250 |

**13700K + 32G RAM 推荐:**
- K3S 系统总占用：约 5.5GB
- 可用工作负载：约 24.5GB
- 可部署 Pod 数：约 100-110 个

### 安装 Traefik

```bash
# 使用自动化脚本
sudo ./scripts/deployment/k3s/install-traefik.sh

# 或手动安装
helm repo add traefik https://helm.traefik.io/traefik
helm repo update

helm install traefik traefik/traefik \
  --namespace traefik \
  --create-namespace \
  -f scripts/deployment/k3s/traefik-values.yaml

# 验证安装
kubectl get pods -n traefik
kubectl get svc -n traefik
```

### 验证存储

```bash
# 运行存储测试
kubectl apply -f scripts/deployment/k3s/test-storage.yaml

# 等待 PVC 绑定
sleep 10
kubectl get pvc test-pvc
kubectl get pods test-storage-pod

# 验证存储功能
kubectl exec test-storage-pod -- sh -c "echo 'test' > /data/test.txt && cat /data/test.txt"

# 清理测试资源
kubectl delete -f scripts/deployment/k3s/test-storage.yaml
```

---

## 多节点部署

### 架构概述

```
┌──────────────────────────────────────────────────────┐
│              WSL2 Ubuntu 22.04                        │
│                                                       │
│  ┌────────────────────────────────────────────────┐  │
│  │         Docker k3s-network (172.30.0.0/16)     │  │
│  │                                                 │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────┐│  │
│  │  │   Server    │  │    Agent    │  │  Agent  ││  │
│  │  │   Node 1    │  │    Node 2   │  │  Node 3 ││  │
│  │  │ 172.30.0.10 │  │ 172.30.0.21 │  │172.30.0.││  │
│  │  └─────────────┘  └─────────────┘  └─────────┘│  │
│  │         │                  │             │     │  │
│  │         └──────────────────┴─────────────┘     │  │
│  │                   Flannel VXLAN                │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

### 快速部署

```bash
# 进入脚本目录
cd scripts/deployment/k3s

# 部署多节点集群（1 Server + 2 Agent = 3 节点）
sudo ./install-multi-node.sh

# 验证集群
kubectl get nodes -o wide
# 输出示例:
# NAME                 STATUS   ROLES                  AGE   VERSION        INTERNAL-IP
# k3s-node-server-1    Ready    control-plane,master   2m    v1.34.5+k3s1   172.30.0.10
# k3s-node-agent-1     Ready    <none>                 90s   v1.34.5+k3s1   172.30.0.21
# k3s-node-agent-2     Ready    <none>                 60s   v1.34.5+k3s1   172.30.0.22
```

### 自定义配置

```bash
# 自定义节点数量
export SERVER_NODES=3    # Server 节点数（高可用）
export AGENT_NODES=5     # Agent 节点数

# 自定义 K3S 版本
export K3S_VERSION="v1.35.0+k3s1"

# 自定义集群名称
export CLUSTER_NAME="production-sim"

# 部署集群
sudo ./scripts/deployment/k3s/install-multi-node.sh
```

### 安装 Traefik（多节点）

```bash
sudo ./scripts/deployment/k3s/install-traefik-docker.sh

# 验证安装
kubectl get pods -n traefik
kubectl get svc -n traefik
```

### 运行健康检查

```bash
sudo ./scripts/deployment/k3s/health_check_docker.sh
```

---

## 多集群管理

### 命令语法

```bash
sudo ./scripts/deployment/k3s/install-multi-node.sh [command] [options]
```

### 命令

| 命令 | 说明 |
|------|------|
| `create` | 创建集群（默认，可省略） |
| `delete` | 删除集群 |
| `list` | 列出所有集群 |
| `show` | 显示集群详情 |
| `help` | 显示帮助信息 |

### 选项

| 选项 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--servers` | `-n` | Server 节点数量 | 1 |
| `--agents` | `-a` | Agent 节点数量 | 2 |
| `--version` | `-v` | K3S 版本 | v1.34.5+k3s1 |
| `--token` | `-t` | 集群 Token | 自动生成 |
| `--cluster-name` | | 集群名称 | k3s-default |
| `--no-ports` | | 不映射端口 | false |
| `--quiet` | `-q` | 静默模式 | false |
| `--help` | `-h` | 显示帮助 | - |

### 多集群示例

```bash
# 创建开发集群
sudo ./install-multi-node.sh \
  --cluster-name dev \
  --servers 1 \
  --agents 2

# 创建测试集群（不映射端口，避免冲突）
sudo ./install-multi-node.sh \
  --cluster-name test \
  --servers 1 \
  --agents 2 \
  --no-ports

# 查看集群列表
sudo ./install-multi-node.sh list

# 查看集群详情
sudo ./install-multi-node.sh show dev

# 删除测试集群
sudo ./install-multi-node.sh delete --cluster-name test
```

---

## 运维管理

### 查看集群状态

```bash
# 查看节点
kubectl get nodes

# 查看系统 Pod
kubectl get pods -n kube-system

# 查看资源使用（需安装 metrics-server）
kubectl top nodes
kubectl top pods -A
```

### 清理集群

**单节点清理:**
```bash
# 卸载 K3S
/usr/local/bin/k3s-uninstall.sh

# 或手动清理
sudo systemctl stop k3s
sudo rm -rf /var/lib/rancher/k3s
sudo rm -rf /etc/rancher/k3s
```

**多节点清理:**
```bash
# 使用脚本清理
sudo ./scripts/deployment/k3s/install-multi-node.sh delete

# 或手动清理
docker rm -f $(docker ps -a -q --filter "name=k3s-node")
docker volume rm $(docker volume ls -q --filter "name=k3s-node")
docker network rm k3s-network
rm -rf ~/.kube/config
```

### 备份与恢复

```bash
# 备份 kubeconfig
cp ~/.kube/config ~/.kube/config.bak.$(date +%Y%m%d%H%M%S)

# 恢复 kubeconfig
cp ~/.kube/config.bak.$(date +%Y%m%d%H%M%S) ~/.kube/config
```

---

## 故障排查

### Pod 无法调度

```bash
# 查看 Pod 事件
kubectl describe pod <pod-name>

# 查看节点状态
kubectl describe nodes

# 检查资源配额
kubectl top nodes
```

### PVC 无法绑定

```bash
# 查看 PVC 详情
kubectl describe pvc <pvc-name>

# 检查存储类
kubectl get storageclass
kubectl describe storageclass local-path

# 查看 local-path-provisioner 日志
kubectl logs -n kube-system -l app=local-path-provisioner
```

### 节点无法启动

**单节点:**
```bash
# 查看 K3S 日志
sudo journalctl -u k3s -f

# 检查端口占用
sudo ss -tlnp | grep -E '6443|80|443'
```

**多节点:**
```bash
# 查看容器日志
docker logs k3s-node-server-1

# 查看 K3S 日志
docker exec k3s-node-server-1 cat /var/log/k3s.log

# 检查端口占用
sudo ss -tlnp | grep -E '6443|80|443'
```

### kubectl 无法连接

```bash
# 重新配置 kubeconfig
docker exec k3s-node-server-1 cat /output/kubeconfig.yaml > ~/.kube/config
chmod 600 ~/.kube/config

# 或使用 sudo
sudo kubectl get nodes
```

---

## 性能优化

### 单节点优化

```yaml
# /etc/rancher/k3s/config.yaml
node-name: sisys-pc
cluster-init: true
flannel-backend: vxlan
disable:
  - traefik
  - servicelb
  - metrics-server

# 资源限制
etcd-memory-limit: 2048Mi
apiserver-memory-limit: 2048Mi
```

### 多节点优化

```bash
# 调整节点数量
export SERVER_NODES=1
export AGENT_NODES=2  # 根据资源调整

# 优化 Docker 网络
docker network create \
  --driver bridge \
  --subnet=172.30.0.0/16 \
  --gateway=172.30.0.1 \
  k3s-network
```

### WSL2 优化（Windows）

创建 `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
memory=16GB
processors=8
swap=4GB
```

重启 WSL2:
```powershell
wsl --shutdown
wsl
```

---

## FAQ

### Q1: 端口冲突

**错误:** `端口 6443 被占用`

**解决:**
```bash
# 方案 1: 使用 --no-ports
sudo ./scripts/deployment/k3s/install-multi-node.sh --no-ports

# 方案 2: 删除占用端口的进程
sudo ss -tlnp | grep :6443
sudo kill <PID>
```

### Q2: 节点无法启动

**错误:** `超时：0/3 节点已就绪`

**解决:**
```bash
# 查看容器日志
docker logs k3s-node-server-1

# 查看 K3S 日志
docker exec k3s-node-server-1 cat /var/log/k3s.log

# 清理后重试
sudo ./scripts/deployment/k3s/install-multi-node.sh delete
sudo ./scripts/deployment/k3s/install-multi-node.sh
```

### Q3: kubectl 无法连接

**错误:** `Unable to connect to the server`

**解决:**
```bash
# 重新配置 kubeconfig
docker exec k3s-node-server-1 cat /output/kubeconfig.yaml > ~/.kube/config

# 或使用脚本重新部署
sudo ./scripts/deployment/k3s/install-multi-node.sh delete
sudo ./scripts/deployment/k3s/install-multi-node.sh
```

### Q4: 资源不足

**错误:** `Insufficient memory` 或 `Insufficient cpu`

**解决:**
```bash
# 查看资源使用
kubectl top nodes
kubectl top pods -A

# 清理不需要的 Pod
kubectl delete pod <pod-name> -n <namespace>

# 调整 K3S 资源限制
# 编辑 /etc/rancher/k3s/config.yaml
```

### Q5: 多集群端口冲突

**错误:** `端口 6443 已被占用`

**解决:**
```bash
# 第二个集群使用 --no-ports
sudo ./scripts/deployment/k3s/install-multi-node.sh \
  --cluster-name test \
  --no-ports

# 或使用不同端口
# 编辑 install-multi-node.sh，修改端口映射
```

### Q6: Docker 容器没有期望的镜像

```bash
# =============================================================================
# 步骤 1：给镜像打正确的 TAG（匹配 K3S 期望的名称）
# =============================================================================
docker tag docker.m.daocloud.io/rancher/mirrored-pause:3.6 rancher/mirrored-pause:3.6
docker tag docker.m.daocloud.io/rancher/mirrored-coredns-coredns:1.14.1 rancher/mirrored-coredns-coredns:1.14.1
docker tag docker.m.daocloud.io/rancher/local-path-provisioner:v0.0.34 rancher/local-path-provisioner:v0.0.34
docker tag docker.m.daocloud.io/rancher/k3s:v1.34.5-k3s1 rancher/k3s:v1.34.5-k3s1
docker tag docker.m.daocloud.io/library/busybox:1.35 busybox:1.35
docker tag docker.m.daocloud.io/library/nginx:alpine nginx:alpine

# =============================================================================
# 步骤 2：导入镜像到 K3S 容器的 containerd
# =============================================================================
# 方法 A：使用 crictl（推荐）
docker save rancher/mirrored-pause:3.6 | docker exec -i test-node-server-1 ctr images import -

docker save rancher/mirrored-coredns-coredns:1.14.1 | docker exec -i test-node-server-1 ctr images import -

docker save rancher/local-path-provisioner:v0.0.34 | docker exec -i test-node-server-1 ctr images import -

docker save busybox:1.35 | docker exec -i test-node-server-1 ctr images import -

docker save nginx:alpine | docker exec -i test-node-server-1 ctr images import -

# =============================================================================
# 步骤 3：验证镜像已导入
# =============================================================================
docker exec test-node-server-1 ctr images ls | grep rancher

# =============================================================================
# 步骤 4：删除卡住的 Pod，让它们重新创建
# =============================================================================
docker exec test-node-server-1 kubectl delete pod -n kube-system --all

# =============================================================================
# 步骤 5：等待并验证（60 秒后）
# =============================================================================
echo "等待 60 秒..."
sleep 60
docker exec test-node-server-1 kubectl get pods -n kube-system
```

---

### Q7: K3S 测试集群完整验证

```bash
# =============================================================================
# K3S 测试集群完整验证
# =============================================================================

# 1. 节点状态
echo "=== 1. 节点状态 ==="
docker exec test-node-server-1 kubectl get nodes -o wide

# 2. 系统 Pod
echo ""
echo "=== 2. 系统组件 ==="
docker exec test-node-server-1 kubectl get pods -n kube-system

# 3. DNS 解析测试
echo ""
echo "=== 3. DNS 解析测试 ==="
docker exec test-node-server-1 kubectl run test-dns --rm -it --image=busybox:1.35 -- nslookup kubernetes.default 2>&1 | head -8

# 4. 外网连通性测试
echo ""
echo "=== 4. 外网连通性测试 ==="
docker exec test-node-server-1 kubectl run test-net --rm -it --image=busybox:1.35 -- ping -c 3 8.8.8.8 2>&1 | tail -5

# 5. 存储功能测试
echo ""
echo "=== 5. 存储功能测试 ==="
docker exec test-node-server-1 kubectl get storageclass

# 6. 应用部署测试
echo ""
echo "=== 6. 应用部署测试 ==="
docker exec test-node-server-1 kubectl create deployment nginx --image=nginx:alpine --replicas=2
sleep 10
docker exec test-node-server-1 kubectl get pods -l app=nginx -o wide
docker exec test-node-server-1 kubectl delete deployment nginx

echo ""
echo "=== 验证完成 ✅ ==="
```

---

## ✅ 验收标准

### 单节点验收

- [ ] K3S 集群状态为 Ready
- [ ] local-path 存储类已配置
- [ ] Traefik 反向代理正常运行
- [ ] 所有系统 Pod 状态为 Running
- [ ] 存储测试通过

### 多节点验收

- [ ] 所有节点状态为 Ready
- [ ] 节点 IP 分配正确
- [ ] Pod 跨节点调度正常
- [ ] Traefik 高可用测试通过
- [ ] 健康检查脚本通过

---

## 📚 相关文档

- **脚本参考:** `scripts/deployment/k3s/` 目录
- **健康检查:** `scripts/deployment/k3s/health_check.sh`
- **存储测试:** `scripts/deployment/k3s/test-storage.yaml`

---

**文档版本:** 3.0.0
**最后更新:** 2026-03-12
**维护者:** DevOps Team
