# Gitea 部署指南 - Story 0.5

**版本:** 1.0.0
**日期:** 2026-03-12
**状态:** 开发中
**关联 Story:** 0-5-gitea-code-hosting

---

## 📋 概述

本指南描述如何在 K3S 集群上部署 Gitea v1.25.4 代码托管平台。

### 技术栈

- **Gitea**: v1.25.4 ✅ (已由 Agimtech 测试验证)
- **数据库**: PostgreSQL 15
- **Helm**: v3.x
- **Ingress**: Traefik v3.x
- **存储**: local-path-provisioner (NVMe SSD)

### 依赖关系

**前置依赖:**
- ✅ Story 0.4: K3S 集群部署 (已完成)
  - K3S v1.34.5
  - Traefik v3.x
  - local-path-provisioner

---

## 🚀 快速开始

### 1. 添加 Helm 仓库

```bash
helm repo add gitea-charts https://dl.gitea.com/charts/
helm repo update
```

### 2. 创建命名空间

```bash
kubectl create namespace gitea
```

### 3. 创建 Kubernetes Secrets

#### 创建管理员账号 Secret

```bash
kubectl create secret generic gitea-admin-secret \
  --namespace gitea \
  --from-literal=username=gitea_admin \
  --from-literal=password='YourSecurePassword123!' \
  --from-literal=email=admin@sisys.local
```

**密码要求:**
- 最小长度：12 位
- 必须包含：大写字母 + 小写字母 + 数字 + 特殊符号
- 示例：`YourSecurePassword123!`

#### 创建 PostgreSQL Secret

```bash
kubectl create secret generic gitea-postgresql-secret \
  --namespace gitea \
  --from-literal=password='YourDbPassword123!' \
  --from-literal=admin-password='YourAdminPassword123!'
```

### 4. 部署 Gitea

```bash
# 使用 Helm 部署
helm install gitea gitea-charts/gitea \
  --namespace gitea \
  --values deploy/kubernetes/gitea/values.yaml
```

或使用 Kustomize:

```bash
# 使用 Kustomize 部署
kubectl apply -k deploy/kubernetes/gitea/
```

### 5. 验证部署

```bash
# 检查 Pod 状态
kubectl get pods -n gitea

# 期望输出:
# NAME                     READY   STATUS    RESTARTS   AGE
# gitea-0                  1/1     Running   0          2m
# gitea-postgresql-0       1/1     Running   0          2m

# 检查服务状态
kubectl get services -n gitea

# 期望输出:
# NAME                 TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)    AGE
# gitea-http           ClusterIP   10.43.x.x        <none>        3000/TCP   2m
# gitea-ssh            ClusterIP   10.43.x.x        <none>        2222/TCP   2m
# gitea-postgresql     ClusterIP   10.43.x.x        <none>        5432/TCP   2m

# 检查 Ingress 状态
kubectl get ingress -n gitea

# 期望输出:
# NAME            CLASS    HOSTS                ADDRESS     PORTS     AGE
# gitea-ingress   traefik  gitea.sisys.local    192.168.x.x 80, 443   2m
```

### 6. 访问 Gitea

访问：https://gitea.sisys.local

**初始管理员账号:**
- 用户名：`gitea_admin`
- 密码：创建 Secret 时设置的密码

---

## 📁 文件结构

```
sisys/
├── deploy/kubernetes/
│   └── gitea/
│       ├── namespace.yaml         # 命名空间配置
│       ├── values.yaml            # Helm Chart 配置
│       ├── ingress.yaml           # Ingress 配置
│       ├── kustomization.yaml     # Kustomize 配置
│       ├── secrets.yaml           # Secrets 配置 (示例)
│       └── config/
│           └── app.ini            # Gitea 应用配置
├── docs/
│   └── deployment/
│       └── GITEA_INSTALLATION.md  # 本文件
└── tests/
    └── deployment/
        └── test_gitea.py          # Gitea 部署测试
```

---

## ⚙️ 配置说明

### Helm Chart 配置 (values.yaml)

**关键配置项:**

```yaml
# 副本数 (MVP 阶段)
replicaCount: 1

# 镜像版本
image:
  repository: gitea/gitea
  tag: "1.25.4"

# 资源限制 (MVP 临时配置)
resources:
  limits:
    cpu: "1000m"  # 1 Core
    memory: "2Gi"

# 安全配置
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  privileged: false

# 持久化存储
persistence:
  enabled: true
  storageClass: local-path
  size: 10Gi

# Ingress 配置
ingress:
  enabled: true
  className: traefik
  hosts:
    - host: gitea.sisys.local
```

### Gitea 应用配置 (app.ini)

**安全配置:**

```ini
[security]
INSTALL_LOCK = true
PASSWORD_COMPLEXITY = upper,lower,digit,special
MIN_PASSWORD_LENGTH = 12
DISABLE_REGISTRATION = true  # 禁用普通用户注册
REQUIRE_SIGNIN_VIEW = true   # 需要登录才能查看

[service]
DISABLE_REGISTRATION = true
REQUIRE_SIGNIN_VIEW = true
ENABLE_BASIC_AUTHENTICATION = true
ENABLE_OPENID_SIGNIN = false

[actions]
ENABLED = true  # 启用 Gitea Actions (Story 0.9 准备)
```

---

## 🔒 安全加固

### 1. TLS/SSL 配置

- **TLS 版本**: TLS 1.3 强制启用
- **证书颁发**: Let's Encrypt
- **HSTS**: 启用

验证 TLS 配置:

```bash
openssl s_client -connect gitea.sisys.local:443 -tls1_3
```

### 2. 容器安全

- 非 root 用户运行
- 只读根文件系统
- 禁用特权模式
- 限制 Linux Capabilities

### 3. 网络安全

- NetworkPolicy 默认拒绝
- 仅允许 Traefik Ingress 访问
- 禁用普通用户注册

---

## 🧪 测试

运行测试套件:

```bash
# 运行所有 Gitea 测试
pytest tests/deploy/test_gitea.py -v

# 运行特定测试
pytest tests/deploy/test_gitea.py::TestGiteaDeployment::test_gitea_pod_running -v

# 运行带标记的测试
pytest tests/deploy/test_gitea.py -m "验收标准"
```

### 测试覆盖

- ✅ AC1: Gitea v1.25.4 部署成功
- ✅ AC2: Gitea Web 界面可正常访问
- ✅ AC3: PostgreSQL 数据库连接成功
- ✅ AC4: 管理员账号创建成功
- ✅ AC5: HTTPS 证书配置完成

---

## 🔧 故障排查

### Pod 无法启动

```bash
# 查看 Pod 日志
kubectl logs -n gitea -l app.kubernetes.io/name=gitea

# 查看 Pod 事件
kubectl describe pod -n gitea -l app.kubernetes.io/name=gitea

# 进入 Pod 调试
kubectl exec -it -n gitea <pod-name> -- /bin/sh
```

### 数据库连接失败

```bash
# 检查 PostgreSQL Pod
kubectl get pods -n gitea -l app.kubernetes.io/name=postgresql

# 测试数据库连接
kubectl exec -n gitea <gitea-pod> -- nc -zv gitea-postgresql 5432

# 查看 PostgreSQL 日志
kubectl logs -n gitea -l app.kubernetes.io/name=postgresql
```

### HTTPS 证书问题

```bash
# 检查 cert-manager 状态
kubectl get certificates -n gitea

# 查看证书详情
kubectl describe certificate gitea-tls -n gitea

# 检查 Ingress TLS 配置
kubectl get ingress gitea-ingress -n gitea -o yaml
```

---

## 📊 监控与运维

### 健康检查端点

- **健康检查**: `/api/healthz`
- **版本信息**: `/api/version`
- **指标端点**: `/metrics` (需配置)

### 日志收集

```bash
# 实时查看日志
kubectl logs -f -n gitea -l app.kubernetes.io/name=gitea

# 导出日志
kubectl logs -n gitea -l app.kubernetes.io/name=gitea > gitea.log
```

### 备份策略

```bash
# PostgreSQL 备份 (K3S 定时备份)
# 每日凌晨 2 点自动执行，保留 7 天

# 手动备份 Gitea 数据
kubectl exec -n gitea <gitea-pod> -- \
  tar czf /tmp/gitea-backup.tar.gz /data/git/repositories
```

---

## 📈 扩容指南

### MVP → V1 扩容

**触发条件:**
- CPU 使用率持续>80%
- 内存使用率持续>85%
- 存储使用率>80%

**扩容目标:**

```yaml
resources:
  limits:
    cpu: "2000m"  # 2 Cores (架构规划值)
    memory: "4Gi"  # 保留增长空间

persistence:
  size: 50Gi  # 根据使用情况调整
```

**执行扩容:**

```bash
# 更新资源限制
kubectl set resources deployment gitea \
  --limits=cpu=2000m,memory=4Gi \
  --requests=cpu=1000m,memory=2Gi \
  -n gitea

# 更新存储容量
kubectl patch pvc gitea-data -n gitea \
  -p '{"spec":{"resources":{"requests":{"storage":"50Gi"}}}}'
```

---

## 🔗 集成准备

### Story 0.6 (Harbor) 集成

```bash
# 创建 Harbor Robot Account (Story 0.6 执行)
# 用于 Gitea 推送镜像
```

### Story 0.7 (ArgoCD) 集成

```bash
# 创建 ArgoCD Git 仓库凭证 (Story 0.7 执行)
argocd repo add https://gitea.sisys.local/sisys/sisys.git \
  --username <git-user> --password <git-token>
```

### Story 0.8 (Gitea Runner) 集成

```bash
# 注册 Gitea Runner (Story 0.8 执行)
gitea-runner register \
  --url https://gitea.sisys.local \
  --token <runner-token> \
  --labels sisys-runner
```

### Story 0.9 (CI/CD Pipeline) 集成

```bash
# 创建 Pipeline 模板 (Story 0.9 执行)
# .gitea/workflows/ci-cd-template.yml
```

---

## ✅ 验收检查清单

### 功能验收

- [ ] Gitea Pod 运行正常
- [ ] Gitea Web 界面可访问
- [ ] PostgreSQL 数据库连接成功
- [ ] 管理员账号创建成功
- [ ] HTTPS 证书配置有效
- [ ] Git LFS 功能可用
- [ ] 所有 TDD 测试通过

### 安全验收

- [ ] TLS 1.3 强制启用
- [ ] HSTS 启用
- [ ] 普通用户注册已禁用
- [ ] 管理员密码符合复杂度要求
- [ ] 2FA 已配置
- [ ] 容器以非 root 用户运行
- [ ] NetworkPolicy 已配置
- [ ] 镜像漏洞扫描通过

### 架构验收

- [ ] 存储使用 local-path (NVMe SSD)
- [ ] Ingress 配置正确
- [ ] 密钥存储于 Kubernetes Secret
- [ ] 资源限制已配置

---

## 📚 参考资料

- [Gitea Helm Chart Documentation](https://gitea.com/gitea/helm-chart)
- [Gitea v1.25.4 Release Notes](https://github.com/go-gitea/gitea/releases)
- [Kubernetes Ingress Documentation](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [Traefik Kubernetes Ingress Provider](https://doc.traefik.io/traefik/providers/kubernetes-ingress/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Gitea Security Configuration](https://docs.gitea.com/administration/config-cheat-sheet#security)

---

**文档状态:** 开发中
**最后更新:** 2026-03-12
**负责人:** Dev Agent
