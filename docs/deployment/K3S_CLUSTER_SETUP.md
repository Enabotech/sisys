# K3S 集群部署指南

**版本：** 1.0
**日期：** 2026-03-05
**适用：** 高性能 PC (13700K + 32G RAM + 1T SSD + 10T HDD)

---

## 📋 概述

本指南介绍如何在高性能 PC 上部署 K3S 轻量级 Kubernetes 集群，为 Gitea、Harbor、ArgoCD 提供运行时环境。

**技术栈:**
- K3S v1.28.x
- Longhorn v1.5.3 (分布式存储)
- Traefik v2.10 (反向代理)

---

## 🔧 前置条件

### 硬件要求
- CPU: 4 核以上 (推荐 13700K 16 核)
- 内存：16GB 以上 (推荐 32GB)
- 磁盘：100GB SSD + 大容量 HDD
- 网络：固定 IP 地址

### 软件要求
- 操作系统：Ubuntu 22.04 LTS / Windows 11 + WSL2
- Docker: 20.10+
- Curl: 已安装

---

## 📦 步骤 1: 安装 K3S

### Ubuntu/Debian

```bash
# 下载并运行安装脚本
curl -sfL https://get.k3s.io | sh -

# 验证安装
sudo kubectl get nodes
# 输出：NAME         STATUS   ROLES                  AGE   VERSION
#       sisys-pc     Ready    control-plane,master   1m    v1.28.x

# 查看 K3S 服务状态
sudo systemctl status k3s
```

### 配置 K3S 资源限制 (针对 13700K + 32G RAM 优化)

```bash
# 创建 K3S 配置文件
sudo mkdir -p /etc/rancher/k3s

cat > /etc/rancher/k3s/config.yaml <<EOF
# 节点配置
node-name: sisys-pc
cluster-init: true

# 网络配置
flannel-backend: none  # 使用 Calico 或其他 CNI
disable-network-policy: false

# 禁用不需要的组件 (节省资源)
disable:
  - traefik        # 使用独立的 Traefik Helm Chart
  - servicelb      # 使用 MetalLB 或其他 LB
  - metrics-server # 可选：独立安装
  - local-storage  # 使用 Longhorn

# API Server 配置
kube-apiserver-arg:
  - max-requests-inflight=1000
  - max-mutating-requests-inflight=500

# Controller Manager 配置
kube-controller-manager-arg:
  - node-cidr-mask-size=24

# Scheduler 配置
kube-scheduler-arg:
  - leader-elect=true

# 资源限制 (针对 32G RAM 优化)
# etcd 内存限制
etcd-memory-limit: 2048

# API Server 内存限制
apiserver-memory-limit: 2048

# Controller Manager 内存限制
controller-manager-memory-limit: 1024

# Scheduler 内存限制
scheduler-memory-limit: 512

# Kubelet 配置
kubelet-arg:
  - max-pods=110
  - serialization-verbosity=0

# 系统预留资源
system-reserved:
  - cpu=2000m
  - memory=4Gi

# Kube 预留资源
kube-reserved:
  - cpu=1000m
  - memory=2Gi

# 日志配置
debug: false
logging: 0
EOF

# 重启 K3S 服务
sudo systemctl restart k3s

# 验证配置
sudo kubectl get nodes -o wide
sudo kubectl top nodes
```

### 资源分配建议表

| 硬件配置 | etcd 内存 | API Server | Controller | Scheduler | 可用 Pod |
|---------|----------|-----------|------------|-----------|---------|
| 8 核 + 16G | 1Gi | 1Gi | 512Mi | 256Mi | ~50 |
| 16 核 + 32G | 2Gi | 2Gi | 1Gi | 512Mi | ~110 |
| 32 核 + 64G | 4Gi | 4Gi | 2Gi | 1Gi | ~250 |

**13700K + 32G RAM 推荐配置：**
- K3S 系统总占用：约 5.5GB
- Longhorn 存储：约 2GB
- 可用工作负载：约 24.5GB
- 可部署 Pod 数：约 100-110 个

### Windows 11 + WSL2

```bash
# 在 WSL2 中执行
curl -sfL https://get.k3s.io | sh -

# 配置 kubectl 别名
echo 'alias kubectl="sudo kubectl"' >> ~/.bashrc
source ~/.bashrc

# 验证安装
kubectl get nodes
```

---

## 📦 步骤 2: 配置 Longhorn 存储

```bash
# 添加 Longhorn Helm 仓库
helm repo add longhorn https://charts.longhorn.io
helm repo update

# 安装 Longhorn
kubectl apply -f https://raw.githubusercontent.com/longhorn/longhorn/v1.5.3/deploy/longhorn.yaml

# 等待 Longhorn 就绪
kubectl get pods -n longhorn-system
# 所有 Pod 状态应为 Running

# 访问 Longhorn UI
kubectl -n longhorn-system port-forward svc/longhorn-frontend 8080:80
# 浏览器访问：http://localhost:8080
```

### 配置存储类

```bash
# 设置 Longhorn 为默认存储类
kubectl patch storageclass longhorn -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

# 验证存储类
kubectl get storageclass
# 输出：NAME         PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE   ALLOWVOLUMEEXPANSION   AGE
#       longhorn   driver.longhorn.io      Delete          Immediate           true                   1m
```

---

## 📦 步骤 3: 配置 Traefik 反向代理

```bash
# 添加 Traefik Helm 仓库
helm repo add traefik https://traefik.github.io/charts
helm repo update

# 创建 Traefik 配置文件
cat > traefik-values.yaml <<EOF
ports:
  web:
    port: 80
  websecure:
    port: 443
    tls:
      enabled: true

providers:
  kubernetesCRD:
    enabled: true
  kubernetesIngress:
    enabled: true
EOF

# 安装 Traefik
helm install traefik traefik/traefik -n traefik --create-namespace -f traefik-values.yaml

# 验证安装
kubectl get pods -n traefik
kubectl get svc -n traefik
```

### 配置 Ingress

```bash
# 创建示例 Ingress
cat > example-ingress.yaml <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: example
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
spec:
  rules:
  - host: example.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: example-service
            port:
              number: 80
EOF

kubectl apply -f example-ingress.yaml
```

---

## 📦 步骤 4: 集群健康检查

```bash
# 检查节点状态
kubectl get nodes
# 期望输出：Ready

# 检查系统 Pod
kubectl get pods -n kube-system
# 所有 Pod 状态应为 Running

# 检查存储类
kubectl get storageclass
# 期望输出：longhorn (default)

# 检查 Traefik
kubectl get pods -n traefik
kubectl get svc -n traefik

# 运行集群诊断
kubectl cluster-info
kubectl top nodes
kubectl top pods --all-namespaces
```

---

## 🔧 故障排查

### K3S 启动失败

```bash
# 查看 K3S 日志
sudo journalctl -u k3s -f

# 重启 K3S 服务
sudo systemctl restart k3s

# 检查端口占用
sudo netstat -tlnp | grep :6443
```

### Longhorn 存储不足

```bash
# 查看存储使用情况
kubectl get pv
kubectl get pvc --all-namespaces

# 清理未使用的 PVC
kubectl delete pvc <pvc-name> -n <namespace>
```

### Traefik 路由失败

```bash
# 查看 Traefik 日志
kubectl logs -n traefik -l app.kubernetes.io/name=traefik

# 检查 Ingress 配置
kubectl describe ingress <ingress-name>
```

---

## 📊 性能优化

### K3S 优化

```bash
# 配置 K3S 参数
sudo mkdir -p /etc/rancher/k3s
cat > /etc/rancher/k3s/config.yaml <<EOF
node-name: sisys-pc
cluster-init: true
flannel-backend: none
disable:
  - traefik
  - servicelb
  - metrics-server
EOF

sudo systemctl restart k3s
```

### Longhorn 优化

```bash
# 配置 Longhorn 参数 (通过 UI)
# 1. 访问 Longhorn UI
# 2. Settings -> General
# 3. 配置：
#    - Default Replica Count: 1 (单机)
#    - Guaranteed Instance Manager CPU: 10%
```

---

## ✅ 验收标准

- [ ] K3S 集群状态为 Ready
- [ ] Longhorn 存储类已配置为默认
- [ ] Traefik 反向代理正常运行
- [ ] 所有系统 Pod 状态为 Running
- [ ] 集群健康检查通过

---

**下一步：** `docs/deployment/GITEA_INSTALLATION.md`
