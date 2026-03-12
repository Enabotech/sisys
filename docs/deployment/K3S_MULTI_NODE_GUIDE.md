# K3S 多节点集群部署指南 - WSL2 单实例

**适用环境:** WSL2 Ubuntu 22.04
**K3S 版本:** v1.34.5
**部署模式:** 单 WSL2 实例 + 多 Docker 容器节点
**网络模式:** Flannel VXLAN（与单节点配置一致）

---

## 1. 架构概述

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
│                                                       │
│  Port Mapping:                                        │
│  - 6443 (API Server)                                  │
│  - 80 (HTTP)                                          │
│  - 443 (HTTPS)                                        │
└──────────────────────────────────────────────────────┘
```

---

## 2. 前置要求

### 2.1 系统要求

| 资源 | 最低配置 | 推荐配置 |
|------|---------|---------|
| **内存** | 8GB | 16GB+ |
| **CPU** | 4 核 | 8 核+ |
| **磁盘** | 20GB | 50GB+ |
| **WSL2** | 已安装 | 最新版本 |

### 2.2 软件要求

```bash
# 检查 Docker
docker --version  # 需要 Docker 20.10+

# 检查 WSL2
wsl --version     # 需要 WSL2

# 检查 kubectl（可选，脚本会 fallback 到 docker exec）
kubectl version --client
```

### 2.3 安装 Docker（如果未安装）

```bash
# 在 WSL2 中安装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

---

## 3. 快速开始

### 3.1 部署多节点集群

```bash
# 进入脚本目录
cd scripts/deployment/k3s

# 部署集群（1 Server + 2 Agent = 3 节点）
sudo ./install-multi-node.sh
```

### 3.2 验证集群

```bash
# 查看节点
kubectl get nodes

# 输出示例:
# NAME                 STATUS   ROLES                  AGE   VERSION
# k3s-node-server-1    Ready    control-plane,master   2m    v1.34.5+k3s1
# k3s-node-agent-1     Ready    <none>                 90s   v1.34.5+k3s1
# k3s-node-agent-2     Ready    <none>                 60s   v1.34.5+k3s1
```

### 3.3 安装 Traefik

```bash
sudo ./install-traefik-docker.sh
```

### 3.4 运行健康检查

```bash
sudo ./health_check_docker.sh
```

---

## 4. 自定义配置

### 4.1 调整节点数量

编辑 `install-multi-node.sh`:

```bash
# 修改节点数量配置
SERVER_NODES=1    # Server 节点数（建议 1 或 3）
AGENT_NODES=3     # Agent 节点数（根据需要调整）
```

### 4.2 网络配置

```bash
# 修改网络配置
POD_CIDR="10.42.0.0/16"      # Pod CIDR
SERVICE_CIDR="10.43.0.0/16"  # Service CIDR
CLUSTER_DNS="10.43.0.10"     # Cluster DNS IP
```

### 4.3 Docker 网络配置

```bash
# 如果需要修改 Docker 网络
# 编辑 install-multi-node.sh 中的网络创建部分
docker network create \
    --driver bridge \
    --subnet=172.31.0.0/16 \  # 修改此处
    k3s-network
```

---

## 5. 访问服务

### 5.1 Port-forward（推荐）

```bash
# Traefik Dashboard
kubectl port-forward -n traefik svc/traefik 8080:80
# 浏览器访问：http://localhost:8080

# 应用服务
kubectl port-forward svc/my-app 3000:80
# 浏览器访问：http://localhost:3000
```

### 5.2 NodePort

修改 `traefik-values.yaml`:

```yaml
service:
  type: NodePort
```

重新安装 Traefik:

```bash
helm upgrade traefik traefik/traefik \
  -n traefik \
  -f traefik-values.yaml
```

---

## 6. 常用命令

### 6.1 集群管理

```bash
# 查看节点
kubectl get nodes -o wide

# 查看 Pod
kubectl get pods -A -o wide

# 查看资源使用
kubectl top nodes
kubectl top pods -A
```

### 6.2 Docker 容器管理

```bash
# 查看所有 K3S 容器
docker ps | grep k3s-node

# 查看容器日志
docker logs k3s-node-server-1

# 重启节点
docker restart k3s-node-agent-1

# 停止所有节点
docker stop $(docker ps -q --filter "name=k3s-node")
```

### 6.3 清理集群

```bash
# 删除所有节点容器
docker rm -f $(docker ps -a -q --filter "name=k3s-node")

# 删除所有数据卷
docker volume rm $(docker volume ls -q --filter "name=k3s-node")

# 删除 Docker 网络
docker network rm k3s-network

# 删除 kubeconfig
rm ~/.kube/config
```

---

## 7. 故障排查

### 7.1 节点无法启动

```bash
# 查看容器日志
docker logs k3s-node-agent-1

# 常见问题:
# 1. 端口被占用
# 2. Docker 网络配置错误
# 3. Token 不匹配
```

### 7.2 Pod 无法调度

```bash
# 查看 Pod 事件
kubectl describe pod <pod-name> -n <namespace>

# 查看节点资源
kubectl describe node k3s-node-agent-1
```

### 7.3 网络不通

```bash
# 测试容器间网络
docker exec k3s-node-server-1 ping 172.30.0.21

# 测试 Pod 网络
kubectl run test --rm -it --image=busybox -- sh
# 在 Pod 内：ping <pod-ip>
```

---

## 8. 常见问题 (FAQ)

### Q1: 容器启动后立即退出

**症状:** `docker ps` 看不到容器，或容器状态为 `Exited`

**排查步骤:**
```bash
# 1. 查看容器日志
docker logs k3s-node-server-1 --tail 100

# 2. 检查端口占用
sudo ss -tlnp | grep -E '6443|80|443'

# 3. 检查 Docker 资源
docker system df
docker info
```

**常见原因:**
- 端口 6443/80/443 被占用
- Docker 磁盘空间不足
- K3S Token 不匹配

**解决方案:**
```bash
# 清理旧集群
docker rm -f $(docker ps -a -q --filter "name=k3s-node")
docker volume rm $(docker volume ls -q --filter "name=k3s-node")

# 重新部署
sudo ./install-multi-node.sh
```

---

### Q2: Pod 一直处于 Pending 状态

**症状:** `kubectl get pods` 显示 Pod 长时间 Pending

**排查步骤:**
```bash
# 1. 查看 Pod 事件
kubectl describe pod <pod-name>

# 2. 查看节点状态
kubectl describe nodes

# 3. 检查资源配额
kubectl top nodes
```

**常见原因:**
- 节点资源不足（CPU/内存）
- PVC 无法绑定（存储问题）
- 节点标签/污点不匹配

**解决方案:**
```bash
# 检查节点资源
kubectl top nodes

# 查看 PVC 状态
kubectl get pvc -A

# 检查节点污点
kubectl describe node k3s-node-agent-1 | grep Taint
```

---

### Q3: Pod 间网络不通

**症状:** Pod 无法互相 Ping 通，或 DNS 解析失败

**排查步骤:**
```bash
# 1. 检查 Flannel 配置
kubectl get pods -n kube-system -l app=flannel

# 2. 测试 DNS 解析
kubectl run dns-test --rm -it --image=busybox -- nslookup kubernetes.default

# 3. 检查 CoreDNS
kubectl get pods -n kube-system -l k8s-app=kube-dns
```

**常见原因:**
- flannel-backend 配置不正确
- CoreDNS Pod 未运行
- 网络策略阻止通信

**解决方案:**
```bash
# 检查 K3S 配置
cat /etc/rancher/k3s/config.yaml

# 确保 flannel-backend=vxlan（不是 none）
# 重启 K3S 服务
sudo systemctl restart k3s
```

---

### Q4: Traefik 安装失败

**症状:** `helm install` 失败或 Traefik Pod 无法启动

**排查步骤:**
```bash
# 1. 检查 Helm 仓库
helm repo list
helm search repo traefik

# 2. 查看 Traefik Pod 日志
kubectl logs -n traefik -l app.kubernetes.io/name=traefik --tail 100

# 3. 检查事件
kubectl get events -n traefik --sort-by='.lastTimestamp'
```

**常见原因:**
- Helm Chart 版本不兼容
- 配置文件（traefik-values.yaml）格式错误
- 端口 80/443 被占用

**解决方案:**
```bash
# 更新 Helm 仓库
helm repo update

# 检查配置文件语法
helm lint traefik/traefik -f traefik-values.yaml

# 查看端口占用
sudo ss -tlnp | grep -E ':80|:443'
```

---

### Q5: PVC 无法绑定

**症状:** PVC 一直处于 `Pending` 状态

**排查步骤:**
```bash
# 1. 查看 PVC 详情
kubectl describe pvc <pvc-name>

# 2. 检查存储类
kubectl get storageclass
kubectl describe storageclass standard

# 3. 查看 local-path-provisioner 日志
kubectl logs -n kube-system -l app=local-path-provisioner
```

**常见原因:**
- 存储类不存在
- 节点磁盘空间不足
- WaitForFirstConsumer 模式需要 Pod 调度后才绑定

**解决方案:**
```bash
# 检查默认存储类
kubectl get storageclass -o jsonpath='{.items[*].metadata.annotations.storageclass\.kubernetes\.io/is-default-class}'

# 检查磁盘空间
df -h /var/lib/rancher/k3s/storage

# 创建 Pod 触发绑定（WaitForFirstConsumer 模式）
kubectl apply -f scripts/deployment/k3s/test-storage.yaml
```

---

### Q6: kubectl 命令权限错误

**症状:** `kubectl get nodes` 提示 `Unable to connect to the server` 或权限错误

**排查步骤:**
```bash
# 1. 检查 kubeconfig
ls -la ~/.kube/config

# 2. 测试连接
kubectl cluster-info

# 3. 使用 docker exec 测试
docker exec k3s-node-server-1 k3s kubectl get nodes
```

**解决方案:**
```bash
# 重新配置 kubeconfig
docker exec k3s-node-server-1 cat /output/kubeconfig.yaml > ~/.kube/config
chmod 600 ~/.kube/config

# 或使用 sudo
sudo kubectl get nodes
```

---

### Q7: WSL2 内存不足

**症状:** K3S 服务频繁重启，或 Pod 被 OOMKilled

**排查步骤:**
```bash
# 检查 WSL2 内存配置
cat /proc/meminfo

# 查看 K3S 资源使用
kubectl top nodes
kubectl top pods -A
```

**解决方案:**

1. 创建/编辑 `%USERPROFILE%\.wslconfig`（Windows 用户目录）:
```ini
[wsl2]
memory=16GB
processors=8
swap=4GB
```

2. 重启 WSL2:
```powershell
wsl --shutdown
wsl
```

3. 调整 K3S 资源限制（编辑 `config.yaml`）:
```yaml
system-reserved:
  - cpu=2000m
  - memory=4Gi
```

---

### Q8: Docker 容器时间不同步

**症状:** 容器内时间与主机不一致，导致证书验证失败

**解决方案:**
```bash
# 在 WSL2 中同步时间
sudo date -s "$(date)"

# 重启所有容器
docker restart $(docker ps -q --filter "name=k3s-node")

# 或使用 systemd-timesyncd
sudo systemctl restart systemd-timesyncd
```

---

### Q9: Helm 下载 Chart 失败

**症状:** `curl: Failed to connect` 或 `timeout`

**解决方案:**
```bash
# 1. 使用国内镜像
helm repo add traefik https://helm.traefik.io/traefik
helm repo update

# 2. 手动下载 Chart
wget https://helm.traefik.io/traefik/traefik-39.0.5.tgz
helm install traefik ./traefik-39.0.5.tgz -n traefik --create-namespace

# 3. 检查网络连接
ping helm.traefik.io
curl -I https://helm.traefik.io/traefik
```

---

### Q10: flannel-backend 配置问题

**症状:** Pod 间网络不通，DNS 解析失败

**排查步骤:**
```bash
# 检查 K3S 配置
cat /etc/rancher/k3s/config.yaml

# 查看 Flannel Pod
kubectl get pods -n kube-system -l app=flannel
```

**解决方案:**
```yaml
# 确保 config.yaml 中配置正确
flannel-backend: vxlan  # 不要使用 none
disable-network-policy: false
```

```bash
# 重启 K3S 服务
sudo systemctl restart k3s

# 验证 Pod 网络
kubectl run test1 --rm -it --image=busybox -- ping <another-pod-ip>
```

---

## 9. 调试命令速查表

### 集群调试

```bash
# 查看所有资源状态
kubectl get all -A

# 查看事件（按时间排序）
kubectl get events -A --sort-by='.lastTimestamp'

# 查看 Pod 详细状态
kubectl describe pod <pod-name> -n <namespace>

# 查看节点详情
kubectl describe node <node-name>

# 进入 Pod 调试
kubectl exec -it <pod-name> -n <namespace> -- /bin/sh
```

### Docker 调试

```bash
# 查看容器日志（实时）
docker logs -f k3s-node-server-1

# 进入容器
docker exec -it k3s-node-server-1 /bin/sh

# 查看容器资源使用
docker stats k3s-node-server-1

# 检查容器网络
docker inspect k3s-node-server-1 | grep -A 20 Networks
```

### K3S 日志

```bash
# 查看 K3S 服务日志
journalctl -u k3s -f

# 查看 K3S 日志文件
tail -f /var/log/k3s.log

# 查看特定组件日志
journalctl -u k3s | grep -i "traefik\|flannel\|coredns"
```

### 网络调试

```bash
# 测试 Pod 间网络
kubectl run test1 --rm -it --image=busybox -- sh
# 在 Pod 内：ping <other-pod-ip>

# 测试 DNS 解析
kubectl run dns-test --rm -it --image=busybox -- nslookup kubernetes.default

# 查看网络策略
kubectl get networkpolicies -A
```

---

## 10. 存储说明

### 10.1 local-path-provisioner

**默认存储类:** `standard`

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-pvc
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: standard
  resources:
    requests:
      storage: 1Gi
```

### 10.2 存储限制

| 特性 | 支持 | 说明 |
|------|------|------|
| **ReadWriteOnce** | ✅ | 单节点读写 |
| **ReadWriteMany** | ❌ | 不支持（需要 NFS） |
| **跨节点迁移** | ❌ | PVC 绑定到特定节点 |
| **数据持久化** | ✅ | Docker volume 持久化 |

### 10.3 存储路径

**默认路径:** `/var/lib/rancher/k3s/storage`

**挂载到大容量磁盘:**
```bash
# 使用 WSL2 共享存储
sudo mkdir -p /mnt/wsl-data/k8s-storage
sudo chmod 777 /mnt/wsl-data/k8s-storage

# 或挂载 Windows 磁盘
sudo mkdir -p /mnt/d/k8s-storage
sudo chmod 777 /mnt/d/k8s-storage
```

---

## 11. 性能优化

### 11.1 WSL2 资源配置

创建/编辑 `%USERPROFILE%\.wslconfig`（Windows 用户目录）:

```ini
[wsl2]
memory=16GB
processors=8
swap=4GB
```

### 11.2 K3S 资源限制

编辑 `config.yaml`:

```yaml
# 系统预留资源
system-reserved:
  - cpu=2000m
  - memory=4Gi

kube-reserved:
  - cpu=1000m
  - memory=2Gi
```

### 11.3 节点优化

```bash
# 调整最大 Pod 数
kubelet-arg:
  - max-pods=110
```

---

## 12. 适用场景

### ✅ 推荐场景

- 本地开发和测试
- 多节点功能验证
- CI/CD 流水线测试
- Kubernetes 学习
- Helm Chart 测试
- 微服务架构验证

### ❌ 不推荐场景

- 生产环境部署
- 高性能要求场景
- 需要共享存储的应用
- 需要 LoadBalancer 的场景
- 需要持久化跨节点迁移的场景

---

## 13. 下一步

1. **部署应用** - 开始部署您的应用到多节点集群
2. **配置 CI/CD** - 集成 Gitea + K3S 流水线
3. **监控告警** - 部署 Prometheus + Grafana
4. **日志收集** - 部署 Loki + Promtail
5. **服务网格** - 部署 Istio/Linkerd

---

## 附录：版本兼容性

| 组件 | 版本 | 说明 |
|------|------|------|
| **K3S** | v1.34.5 | Kubernetes 1.34 |
| **Flannel** | 内置 | VXLAN 模式 |
| **CoreDNS** | 内置 | 集群 DNS |
| **local-path-provisioner** | 内置 | 存储供应 |
| **Docker** | 20.10+ | 容器运行时 |
| **WSL2** | 最新版 | Windows 子系统 |

---

**文档版本:** 2.0 (代码审查修复版)
**更新日期:** 2026-03-12
**维护者:** DevOps Team
**更新说明:** 添加完整故障排除指南和调试命令速查表
