# Gitea Runner 注册配置指南

本文档详细介绍 Gitea Actions Runner 的注册、配置和管理流程。

## 目录

- [Gitea Runner 注册配置](#gitea-runner-注册配置)
  - [目录](#目录)
  - [1. Runner 概述](#1-runner-概述)
  - [2. Docker Executor 配置](#2-docker-executor-配置)
    - [2.1 安装 Docker Runner](#21-安装-docker-runner)
    - [2.2 配置 Docker Executor](#22-配置-docker-executor)
    - [2.3 Docker-in-Docker 配置](#23-docker-in-docker-配置)
  - [3. Kubernetes Executor 配置](#3-kubernetes-executor-配置)
    - [3.1 安装 Kubernetes Runner](#31-安装-kubernetes-runner)
    - [3.2 配置 K8s Executor](#32-配置-k8s-executor)
    - [3.3 Pod 模板配置](#33-pod-模板配置)
  - [4. 并发控制配置](#4-并发控制配置)
    - [4.1 Runner 级别并发控制](#41-runner-级别并发控制)
    - [4.2 Workflow 级别并发控制](#42-workflow-级别并发控制)
    - [4.3 队列管理](#43-队列管理)
  - [5. 故障排查](#5-故障排查)
    - [5.1 Runner 无法注册](#51-runner-无法注册)
    - [5.2 Job 执行失败](#52-job-执行失败)
    - [5.3 容器构建问题](#53-容器构建问题)
    - [5.4 网络连接问题](#54-网络连接问题)
    - [5.5 日志收集](#55-日志收集)

---

## 1. Runner 概述

Gitea Actions Runner 是执行 CI/CD 工作流的代理程序，支持多种执行器：

| 执行器类型 | 适用场景 | 隔离级别 | 资源利用率 |
|-----------|---------|---------|-----------|
| Docker | 通用构建任务 | 容器级 | 高 |
| Kubernetes | 多租户/大规模 | Pod 级 | 中 |
| Shell | 简单任务/裸机 | 进程级 | 最高 |

### Runner 架构

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Gitea Server  │────▶│   Runner Pool    │────▶│   Executors     │
│   (Actions API) │     │   (Load Balance) │     │   (Docker/K8s)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

---

## 2. Docker Executor 配置

### 2.1 安装 Docker Runner

```bash
# 下载 Runner
wget https://github.com/gitea/act_runner/releases/latest/download/act_runner-linux-amd64
chmod +x act_runner-linux-amd64

# 或使用 Docker 运行
docker pull gitea/act_runner:latest
```

### 2.2 配置 Docker Executor

创建配置文件 `config.yaml`：

```yaml
runner:
  name: "docker-runner-01"
  labels:
    - "docker"
    - "linux"
    - "x86_64"
  workdir: "/opt/gitea-runner/work"

server:
  addr: "https://gitea.example.com"
  protocol: "https"
  token: "YOUR_RUNNER_TOKEN"

container:
  network: "host"
  options: "--privileged"
  volumes:
    - "/var/run/docker.sock:/var/run/docker.sock"
    - "/tmp:/tmp"
  env_vars:
    - "DOCKER_HOST=unix:///var/run/docker.sock"
```

启动 Runner：

```bash
# 二进制方式
./act_runner-linux-amd64 daemon -C config.yaml

# Docker 方式
docker run -d \
  --name gitea-runner \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /opt/gitea-runner/work:/opt/gitea-runner/work \
  -e GITEA_INSTANCE_URL=https://gitea.example.com \
  -e GITEA_RUNNER_TOKEN=YOUR_TOKEN \
  -e GITEA_RUNNER_NAME=docker-runner-01 \
  -e GITEA_RUNNER_LABELS=docker,linux,x86_64 \
  gitea/act_runner:latest
```

### 2.3 Docker-in-Docker 配置

对于需要构建 Docker 镜像的场景：

```yaml
container:
  options: |
    --privileged
    -v /var/run/docker.sock:/var/run/docker.sock
    -v /tmp/build:/tmp/build
  env_vars:
    - "DOCKER_BUILDKIT=1"
    - "DOCKER_HOST=unix:///var/run/docker.sock"
  volumes:
    - "/var/run/docker.sock:/var/run/docker.sock"
    - "/tmp/build:/tmp/build"
```

Workflow 示例：

```yaml
name: Build and Push Docker Image

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: docker
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Harbor
        uses: docker/login-action@v3
        with:
          registry: harbor.example.com
          username: ${{ secrets.HARBOR_USERNAME }}
          password: ${{ secrets.HARBOR_PASSWORD }}

      - name: Build and Push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: harbor.example.com/project/app:${{ github.sha }}
```

---

## 3. Kubernetes Executor 配置

### 3.1 安装 Kubernetes Runner

```bash
# 使用 Helm 安装
helm repo add gitea https://dl.gitea.com/charts/
helm install gitea-runner gitea/act-runner \
  --namespace gitea-runners \
  --create-namespace \
  -f runner-values.yaml
```

### 3.2 配置 K8s Executor

创建 `runner-values.yaml`：

```yaml
replicaCount: 3

gitea:
  url: https://gitea.example.com
  token: YOUR_RUNNER_TOKEN

runner:
  name: "k8s-runner"
  labels:
    - "kubernetes"
    - "linux"
  capacity: 10

kubernetes:
  enabled: true
  namespace: gitea-jobs
  serviceAccountName: gitea-runner-sa

  podTemplate:
    spec:
      containers:
        - name: runner
          image: gitea/act_runner:latest
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2000m"
              memory: "4Gi"

      imagePullSecrets:
        - name: harbor-registry-secret

      nodeSelector:
        runner-type: ci-cd

      tolerations:
        - key: "ci-cd"
          operator: "Equal"
          value: "true"
          effect: "NoSchedule"
```

### 3.3 Pod 模板配置

定义自定义 Pod 模板用于不同类型的任务：

```yaml
# pod-templates.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: runner-pod-templates
  namespace: gitea-jobs
data:
  # 基础构建模板
  base-build: |
    apiVersion: v1
    kind: Pod
    spec:
      containers:
        - name: base
          image: gitea/act_runner:latest
          env:
            - name: DOCKER_HOST
              value: "tcp://localhost:2375"
        - name: dind
          image: docker:24-dind
          securityContext:
            privileged: true
          env:
            - name: DOCKER_TLS_CERTDIR
              value: ""

  # Node.js 构建模板
  nodejs-build: |
    apiVersion: v1
    kind: Pod
    spec:
      containers:
        - name: node
          image: node:20-alpine
          command: ["cat"]
          tty: true

  # Python 构建模板
  python-build: |
    apiVersion: v1
    kind: Pod
    spec:
      containers:
        - name: python
          image: python:3.12-slim
          command: ["cat"]
          tty: true
```

创建 ServiceAccount 和 RBAC：

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: gitea-runner-sa
  namespace: gitea-jobs

---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: gitea-runner-role
  namespace: gitea-jobs
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "pods/exec"]
    verbs: ["get", "list", "create", "delete", "watch"]
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: gitea-runner-binding
  namespace: gitea-jobs
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: gitea-runner-role
subjects:
  - kind: ServiceAccount
    name: gitea-runner-sa
    namespace: gitea-jobs
```

---

## 4. 并发控制配置

### 4.1 Runner 级别并发控制

配置单个 Runner 的最大并发任务数：

```yaml
# config.yaml
runner:
  capacity: 5          # 最大并发任务数
  max_jobs: 10         # 队列最大任务数
  timeout: 3600        # 任务超时时间（秒）

server:
  heartbeat_interval: 30  # 心跳间隔
```

### 4.2 Workflow 级别并发控制

在 Workflow 中配置并发组：

```yaml
name: Deploy Application

on:
  push:
    branches: [main]

concurrency:
  group: deploy-${{ github.ref }}
  cancel-in-progress: true

jobs:
  deploy:
    runs-on: docker
    steps:
      - name: Deploy
        run: ./deploy.sh
```

### 4.3 队列管理

查看 Runner 队列状态：

```bash
# 查看 Runner 状态
curl -H "Authorization: token YOUR_TOKEN" \
  https://gitea.example.com/api/v1/runners

# 查看队列深度
curl -H "Authorization: token YOUR_TOKEN" \
  https://gitea.example.com/api/v1/repos/{owner}/{repo}/actions/runners/queue
```

配置队列优先级：

```yaml
# 在 Runner 配置中
queue:
  priority:
    - pattern: "main|release/*"
      priority: high
    - pattern: "feature/*"
      priority: normal
    - pattern: "dependabot/*"
      priority: low
```

---

## 5. 故障排查

### 5.1 Runner 无法注册

**症状**: Runner 启动后无法在 Gitea UI 中显示

**排查步骤**:

```bash
# 1. 检查网络连接
curl -v https://gitea.example.com/api/v1/version

# 2. 验证 Token
curl -H "Authorization: token YOUR_TOKEN" \
  https://gitea.example.com/api/v1/user

# 3. 检查 Runner 日志
docker logs gitea-runner --tail 100

# 4. 检查防火墙规则
telnet gitea.example.com 443
```

**常见原因**:
- Token 过期或无效
- 网络不通或防火墙阻止
- Gitea Server 未启用 Actions 功能

### 5.2 Job 执行失败

**症状**: Workflow 任务执行失败

**排查步骤**:

```bash
# 1. 查看任务日志
# 在 Gitea UI 中查看 Actions -> Workflow -> Job -> Logs

# 2. 检查 Runner 资源
docker stats gitea-runner

# 3. 检查容器执行环境
docker exec -it gitea-runner sh
ps aux | grep act

# 4. 验证 Docker Socket 挂载
docker exec gitea-runner docker ps
```

### 5.3 容器构建问题

**症状**: Docker 构建失败或镜像推送失败

**排查步骤**:

```bash
# 1. 检查 Docker 守护进程
docker info

# 2. 验证 Registry 认证
docker login harbor.example.com

# 3. 检查磁盘空间
df -h /var/lib/docker

# 4. 清理构建缓存
docker builder prune -a
```

### 5.4 网络连接问题

**症状**: Runner 无法拉取镜像或推送代码

**排查步骤**:

```bash
# 1. 检查 DNS 解析
nslookup harbor.example.com
nslookup gitea.example.com

# 2. 测试镜像拉取
docker pull harbor.example.com/base-images/node:20

# 3. 检查代理配置
echo $HTTP_PROXY
echo $HTTPS_PROXY

# 4. 验证证书
openssl s_client -connect harbor.example.com:443
```

### 5.5 日志收集

收集完整日志用于问题诊断：

```bash
# Runner 日志
docker logs gitea-runner > runner-$(date +%Y%m%d).log 2>&1

# Docker 守护进程日志
journalctl -u docker > docker-$(date +%Y%m%d).log 2>&1

# Kubernetes Runner 日志
kubectl logs -n gitea-runners -l app=act-runner > k8s-runner-$(date +%Y%m%d).log

# 收集系统信息
uname -a
docker version
docker info
kubectl version
```

---

## 附录：Runner 健康检查脚本

```bash
#!/bin/bash
# runner-health-check.sh

RUNNER_URL="https://gitea.example.com"
TOKEN="YOUR_TOKEN"

echo "=== Gitea Runner Health Check ==="

# 检查 Gitea Server 连通性
echo -n "Gitea Server: "
if curl -s -o /dev/null -w "%{http_code}" "$RUNNER_URL" | grep -q "200"; then
    echo "✓ OK"
else
    echo "✗ FAILED"
fi

# 检查 Runner 状态
echo -n "Runner Registration: "
RESPONSE=$(curl -s -H "Authorization: token $TOKEN" "$RUNNER_URL/api/v1/user")
if echo "$RESPONSE" | grep -q "login"; then
    echo "✓ OK"
else
    echo "✗ FAILED"
fi

# 检查 Docker 状态
echo -n "Docker Daemon: "
if docker info > /dev/null 2>&1; then
    echo "✓ OK"
else
    echo "✗ FAILED"
fi

# 检查磁盘空间
echo "Disk Usage:"
df -h /var/lib/docker | tail -1

echo "=== Health Check Complete ==="
```
