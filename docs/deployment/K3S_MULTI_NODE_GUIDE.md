# K3S 多节点集群部署指南 - WSL2 单实例

**适用环境:** WSL2 Ubuntu 22.04
**K3S 版本:** v1.34.5
**部署模式:** 单 WSL2 实例 + 多 Docker 容器节点

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
# 在 Pod 内: ping <pod-ip>
```

---

## 8. 存储说明

### 8.1 local-path-provisioner

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

### 8.2 存储限制

| 特性 | 支持 | 说明 |
|------|------|------|
| **ReadWriteOnce** | ✅ | 单节点读写 |
| **ReadWriteMany** | ❌ | 不支持（需要 NFS） |
| **跨节点迁移** | ❌ | PVC 绑定到特定节点 |
| **数据持久化** | ✅ | Docker volume 持久化 |

---

## 9. 性能优化

### 9.1 WSL2 资源配置

创建/编辑 `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
memory=16GB
processors=8
swap=4GB
```

### 9.2 K3S 资源限制

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

---

## 10. 适用场景

### ✅ 推荐场景

- 本地开发和测试
- 多节点功能验证
- CI/CD 流水线测试
- Kubernetes 学习
- Helm Chart 测试

### ❌ 不推荐场景

- 生产环境部署
- 高性能要求场景
- 需要共享存储的应用
- 需要 LoadBalancer 的场景

---

## 11. 下一步

1. **部署应用** - 开始部署您的应用到多节点集群
2. **配置 CI/CD** - 集成 Gitea + K3S 流水线
3. **监控告警** - 部署 Prometheus + Grafana
4. **日志收集** - 部署 Loki + Promtail

---

**文档版本:** 1.0
**更新日期:** 2026-03-11
**维护者:** DevOps Team
