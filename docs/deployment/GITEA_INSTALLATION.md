# Gitea v1.25.4 部署指南

**版本：** 1.0
**日期：** 2026-03-05
**适用：** K3S 集群 (Story 0.1 完成后)

---

## 📋 概述

本指南介绍如何在 K3S 集群上部署 Gitea v1.25.4 代码托管平台，为开发团队提供 Git 仓库管理和 CI/CD 触发功能。

**技术栈:**
- Gitea v1.25.4 ✅ (已由 Agimtech 验证)
- PostgreSQL 15 (数据库)
- Helm v3 (包管理)
- Traefik v2.10 (反向代理)

---

## 🔧 前置条件

### 依赖检查
- [ ] K3S 集群已部署 (Story 0.1 ✅)
- [ ] Longhorn 存储已配置
- [ ] Traefik 反向代理已配置
- [ ] Helm v3 已安装

### 验证 Helm

```bash
# 检查 Helm 版本
helm version
# 期望输出：version.BuildInfo{Version:"v3.x.x", ...}

# 如未安装 Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

---

## 📦 步骤 1: 添加 Gitea Helm 仓库

```bash
# 添加 Gitea Helm Chart 仓库
helm repo add gitea-charts https://dl.gitea.com/charts/
helm repo update

# 验证仓库
helm search repo gitea-charts
# 期望输出：gitea-charts/gitea  1.25.4  1.25.4
```

---

## 📦 步骤 2: 创建命名空间和配置

```bash
# 创建 Gitea 命名空间
kubectl create namespace gitea

# 创建 Gitea 配置文件
cat > gitea-values.yaml <<EOF
gitea:
  admin:
    username: admin
    password: admin123
    email: admin@sisys.local

  config:
    APP_NAME: "SISYS Gitea"
    RUN_MODE: prod

    repository:
      ROOT: /data/git/repositories

    database:
      DB_TYPE: postgres
      HOST: gitea-postgresql:5432
      NAME: gitea
      USER: gitea
      PASSWD: gitea

    service:
      DISABLE_REGISTRATION: false
      REQUIRE_SIGNIN_VIEW: false

    server:
      DOMAIN: gitea.local
      HTTP_PORT: 3000
      ROOT_URL: http://gitea.local/

postgresql:
  enabled: true
  auth:
    database: gitea
    username: gitea
    password: gitea

  persistence:
    enabled: true
    storageClass: longhorn
    size: 50Gi

persistence:
  enabled: true
  storageClass: longhorn
  size: 100Gi

ingress:
  enabled: true
  className: traefik
  hosts:
    - host: gitea.local
      paths:
        - path: /
          pathType: Prefix
EOF
```

---

## 📦 步骤 3: 部署 Gitea

```bash
# 安装 Gitea
helm install gitea gitea-charts/gitea \
  --namespace gitea \
  --create-namespace \
  --version 1.25.4 \
  -f gitea-values.yaml

# 查看部署状态
helm list -n gitea
kubectl get pods -n gitea
kubectl get svc -n gitea

# 等待 Gitea 就绪
kubectl rollout status deployment/gitea -n gitea
```

---

## 📦 步骤 4: 配置 HTTPS (使用 cert-manager)

### 4.1 安装 cert-manager

```bash
# 创建 cert-manager 命名空间
kubectl create namespace cert-manager

# 添加 Jetstack Helm 仓库
helm repo add jetstack https://charts.jetstack.io
helm repo update

# 安装 cert-manager
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.14.0 \
  --set installCRDs=true

# 验证安装
kubectl get pods -n cert-manager
# 期望输出：cert-manager-xxx, cert-manager-cainjector-xxx, cert-manager-webhook-xxx 都为 Running
```

### 4.2 创建 ClusterIssuer

```bash
# 创建 Let's Encrypt ClusterIssuer (生产环境)
cat > cluster-issuer-prod.yaml <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@sisys.local
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: traefik
EOF

# 创建 Let's Encrypt Staging ClusterIssuer (测试环境)
cat > cluster-issuer-staging.yaml <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: admin@sisys.local
    privateKeySecretRef:
      name: letsencrypt-staging
    solvers:
    - http01:
        ingress:
          class: traefik
EOF

# 应用 ClusterIssuer
kubectl apply -f cluster-issuer-staging.yaml
kubectl apply -f cluster-issuer-prod.yaml
```

### 4.3 配置 Gitea TLS

```bash
# 更新 gitea-values.yaml 启用 TLS
cat > gitea-values-tls.yaml <<EOF
gitea:
  admin:
    username: admin
    password: Admin12345!
    email: admin@sisys.local

  config:
    APP_NAME: "SISYS Gitea"
    RUN_MODE: prod

    server:
      DOMAIN: gitea.sisys.local
      HTTP_PORT: 3000
      ROOT_URL: https://gitea.sisys.local/
      PROTOCOL: https
      CERT_FILE: /data/gitea/https/tls.crt
      KEY_FILE: /data/gitea/https/tls.key

ingress:
  enabled: true
  className: traefik
  hosts:
    - host: gitea.sisys.local
      paths:
        - path: /
          pathType: Prefix
  tls:
  - hosts:
    - gitea.sisys.local
    secretName: gitea-tls

# cert-manager 自动创建 TLS Secret
certificates:
  enabled: true
  issuer:
    name: letsencrypt-staging  # 测试环境使用 staging，生产环境改为 letsencrypt-prod
    kind: ClusterIssuer
  secretName: gitea-tls
EOF

# 部署 Gitea with TLS
helm install gitea gitea-charts/gitea \
  --namespace gitea \
  --create-namespace \
  --version 1.25.4 \
  -f gitea-values-tls.yaml

# 验证证书状态
kubectl get certificates -n gitea
# 期望输出：NAME         READY   SECRET       AGE
#           gitea-tls   True    gitea-tls    5m

kubectl get secret gitea-tls -n gitea
# 期望输出：NAME         TYPE                DATA   AGE
#           gitea-tls   kubernetes.io/tls   2      5m
```

### 4.4 验证 HTTPS 访问

```bash
# 配置 hosts
echo "10.0.0.1 gitea.sisys.local" | sudo tee -a /etc/hosts

# 浏览器访问：https://gitea.sisys.local
# 检查证书是否有效（Staging 证书浏览器会警告，生产证书不会）

# 命令行验证
curl -I https://gitea.sisys.local
# 期望输出：HTTP/2 200

# 检查证书详情
kubectl get secret gitea-tls -n gitea -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -text -noout
```

---

## 📦 步骤 5: 自签名证书方案 (内网环境)

### 5.1 创建自签名证书

```bash
# 生成自签名证书
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key \
  -out tls.crt \
  -subj "/CN=gitea.sisys.local/O=SISYS/C=CN" \
  -addext "subjectAltName=DNS:gitea.sisys.local,DNS:*.sisys.local"

# 创建 Kubernetes Secret
kubectl create secret tls gitea-tls \
  --cert=tls.crt \
  --key=tls.key \
  -n gitea

# 将 CA 证书添加到系统信任库 (Linux)
sudo cp tls.crt /usr/local/share/ca-certificates/sisys-ca.crt
sudo update-ca-certificates

# 将 CA 证书添加到系统信任库 (Windows)
# 1. 双击 tls.crt
# 2. 点击"安装证书"
# 3. 选择"本地计算机"
# 4. 选择"将所有的证书都放入下列存储"
# 5. 点击"浏览"，选择"受信任的根证书颁发机构"
# 6. 完成安装
```

### 5.2 使用自签名证书部署

```bash
# 更新 gitea-values.yaml 使用自签名证书
cat > gitea-values-selfsigned.yaml <<EOF
gitea:
  admin:
    username: admin
    password: Admin12345!
    email: admin@sisys.local

  config:
    APP_NAME: "SISYS Gitea"
    RUN_MODE: prod

    server:
      DOMAIN: gitea.sisys.local
      HTTP_PORT: 3000
      ROOT_URL: https://gitea.sisys.local/
      PROTOCOL: https
      CERT_FILE: /data/gitea/https/tls.crt
      KEY_FILE: /data/gitea/https/tls.key

ingress:
  enabled: true
  className: traefik
  hosts:
    - host: gitea.sisys.local
      paths:
        - path: /
          pathType: Prefix
  tls:
  - hosts:
    - gitea.sisys.local
    secretName: gitea-tls
EOF

# 部署
helm install gitea gitea-charts/gitea \
  --namespace gitea \
  --create-namespace \
  --version 1.25.4 \
  -f gitea-values-selfsigned.yaml
```

---

## 📦 步骤 6: 访问和验证

```bash
# 获取访问地址
kubectl get ingress -n gitea
# 输出：NAME    CLASS    HOSTS          ADDRESS   PORTS   AGE
#       gitea   traefik   gitea.local   10.0.0.1   80      1m

# 配置本地 hosts (Windows: C:\Windows\System32\drivers\etc\hosts)
echo "10.0.0.1 gitea.local" | sudo tee -a /etc/hosts

# 浏览器访问：http://gitea.local
# 默认账号：admin / admin123
```

### 验证 Gitea 功能

```bash
# 检查 Gitea API
curl -X GET http://gitea.local/api/v1/version

# 创建测试仓库
curl -X POST http://gitea.local/api/v1/user/repos \
  -H "Content-Type: application/json" \
  -d '{"name":"test-repo","private":false}' \
  -u admin:admin123
```

---

## 🔧 故障排查

### Gitea Pod 启动失败

```bash
# 查看 Pod 日志
kubectl logs -n gitea -l app.kubernetes.io/name=gitea

# 检查数据库连接
kubectl exec -it -n gitea deployment/gitea -- nc -zv gitea-postgresql 5432
```

### 无法访问 Gitea

```bash
# 检查 Ingress 配置
kubectl describe ingress gitea -n gitea

# 检查 Traefik 日志
kubectl logs -n traefik -l app.kubernetes.io/name=traefik

# 测试本地访问
kubectl port-forward -n gitea svc/gitea 3000:3000
curl http://localhost:3000
```

### 数据库连接失败

```bash
# 检查 PostgreSQL 状态
kubectl get pods -n gitea | grep postgres
kubectl logs -n gitea -l app.kubernetes.io/name=postgresql

# 测试数据库连接
kubectl exec -it -n gitea deployment/gitea -- psql -h gitea-postgresql -U gitea -d gitea
```

---

## 📊 性能优化

### Gitea 配置优化

```yaml
# gitea-values.yaml 追加配置
gitea:
  config:
    cache:
      ADAPTER: memory
      INTERVAL: 60

    session:
      PROVIDER: memory

    picture:
      DISABLE_GRAVATAR: false
      ENABLE_FEDERATED_AVATAR: false

    webhook:
      ALLOWED_HOST_LIST: *
```

### 资源限制

```yaml
# gitea-values.yaml 追加配置
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 2000m
    memory: 2Gi
```

---

## ✅ 验收标准

- [ ] Gitea v1.25.4 部署成功
- [ ] PostgreSQL 数据库配置完成
- [ ] HTTPS 证书配置完成 (可选)
- [ ] 初始管理员账号创建成功
- [ ] 可以通过 http://gitea.local 访问
- [ ] API 测试通过

---

## 🔐 安全建议

1. **修改默认密码**
   - 首次登录后立即修改 admin 密码
   - 启用双因素认证 (2FA)

2. **配置访问控制**
   - 禁用公开注册 (如需要)
   - 配置仓库访问权限

3. **定期备份**
   - 配置 Gitea 备份任务
   - 备份到外部存储

---

**下一步：** `docs/deployment/HARBOR_INSTALLATION.md`
