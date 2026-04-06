# 证书自动续期实施方案

> **创建日期**: 2026-04-06
> **状态**: 待审批
> **涉及系统**: K3S / Gitea / Action Runner / ArgoCD / Harbor
> **目标**: 实现全系统 TLS 证书自动签发和续期，消除手动维护

---

## 目录

1. [当前状态分析](#1-当前状态分析)
2. [目标架构](#2-目标架构)
3. [分阶段实施计划](#3-分阶段实施计划)
4. [详细执行步骤](#4-详细执行步骤)
5. [文件清单](#5-文件清单)
6. [风险评估与缓解](#6-风险评估与缓解)
7. [回滚方案](#7-回滚方案)
8. [验证清单](#8-验证清单)

---

## 1. 当前状态分析

### 1.1 证书现状

| 组件 | 证书类型 | 有效期 | 续期方式 | 指纹 |
|------|---------|--------|---------|------|
| **K3S CA** | ECDSA 自签 CA | 10 年 (2036-03-08) | K3S 自动管理 | - |
| **Gitea** | RSA 2048 自签 | 1 年 (2027-03-17) | ❌ 手动 | `62:60:B3:EB...` |
| **Harbor** | RSA 2048 自签 | 1 年 (2027-03-17) | ❌ 手动 | `62:60:B3:EB...` |
| **ArgoCD** | RSA 2048 自签 | 1 年 (2027-03-17) | ❌ 手动 | `62:60:B3:EB...` |

### 1.2 关键发现

1. **三个服务使用完全相同的证书**
   - Gitea/Harbor/ArgoCD 证书 SHA256 指纹完全一致
   - 同一份证书文件被复制使用
   - 主题: `CN=*.sisys.local, O=SISYS`
   - 自签证书 (Issuer = Subject)

2. **containerd 当前跳过证书验证**
   ```yaml
   # /etc/rancher/k3s/registries.yaml
   configs:
     harbor.sisys.local:
       tls:
         insecure_skip_verify: true  # ← 当前不验证证书
   ```

3. **无自动续期机制**
   - 未安装 cert-manager
   - 证书到期前需手动重新生成并替换
   - 无证书到期监控告警

### 1.3 CA 信任链与 Runner/DinD 证书同步机制

#### 当前 CA 信任架构

```
自签泛域名证书 *.sisys.local (RSA 2048, 1年有效期)
├── Gitea TLS Secret (gitea-tls-secret)
├── Harbor TLS Secret (harbor-tls-secret)
├── ArgoCD TLS Secret (argocd-tls-secret)
└── Runner CA Secret (ca-certificates) ← 同步到 DinD 容器
```

#### Runner/DinD CA 证书同步机制

系统中有 **3 个 Runner 命名空间**，每个都通过以下机制同步 CA 证书：

| 命名空间 | CA Secret 名称 | 证书来源 | 同步方式 |
|---------|---------------|---------|---------|
| `gitea-advacts` | `ca-certificates` | 自签 *.sisys.local | Secret 挂载 |
| `gitea-actions` | `ca-certificates` | 自签 *.sisys.local | Secret 挂载 |
| `gitea` | (使用 kube-root-ca.crt) | K3S CA | ConfigMap 自动同步 |

**详细同步流程**:

```yaml
# 1. Secret 定义 (每个命名空间独立创建)
apiVersion: v1
kind: Secret
metadata:
  name: ca-certificates
  namespace: gitea-advacts
type: Opaque
data:
  ca-certificates.crt: <base64-encoded-self-signed-cert>

# 2. StatefulSet 挂载配置
spec:
  containers:
  - name: runner
    volumeMounts:
    - mountPath: /tmp/gitea-ca.crt    # 挂载到临时目录
      name: ca-certificates
      readOnly: true
      subPath: ca-certificates.crt
    env:
    - name: GIT_SSL_NO_VERIFY
      value: "false"                   # 启用 SSL 验证
    - name: NODE_EXTRA_CA_CERTS
      value: /etc/ssl/certs/ca-certificates.crt  # Node.js 额外 CA

  # 3. 启动脚本动态追加证书
  command: ["/bin/sh", "-c"]
  args:
    - |
      # 安装基础 ca-certificates 包
      apk add --no-cache git curl ca-certificates

      # 如果存在 Gitea CA，追加到系统证书包
      if [ -f /tmp/gitea-ca.crt ]; then
        cat /etc/ssl/certs/ca-certificates.crt > /tmp/system-ca.crt
        cat /tmp/gitea-ca.crt >> /tmp/system-ca.crt
        cp /tmp/system-ca.crt /etc/ssl/certs/ca-certificates.crt
      fi

      export GIT_SSL_NO_VERIFY=false
      export NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt
```

#### DinD 容器 Docker Daemon 配置

DinD 容器通过 `daemon.json` 配置 Harbor 为**不安全注册表**（绕过 TLS 验证）：

```json
{
  "insecure-registries": ["harbor.sisys.local"],
  "dns": ["10.43.0.10", "8.8.8.8"],
  "dns-search": ["gitea-advacts.svc.cluster.local", "svc.cluster.local"],
  "features": { "buildkit": true }
}
```

**关键点**:
- `insecure-registries` 使 Docker 跳过 Harbor 证书验证
- DinD 容器本身不验证 Harbor TLS
- 但 Runner 容器内的 `git` 和 `node` 需要验证 Gitea/Harbor 证书

#### CI Pipeline 中的 CA 链配置

CI workflow (`.gitea/workflows/ci.yaml`) 中显式配置 CA 链：

```yaml
# Phase: 构建和推送镜像
- name: 配置 CA 链
  run: |
    # 写入 Harbor CA
    mkdir -p /tmp/buildkit-certs
    printf '%s' "${{ secrets.HARBOR_CA_CRT }}" > /tmp/buildkit-certs/harbor/ca.crt

    # 安装 Harbor CA 到系统信任链 (Alpine)
    cp /tmp/buildkit-certs/harbor/ca.crt /usr/local/share/ca-certificates/harbor.crt
    update-ca-certificates

    # 配置 Buildkit 使用 CA
    cat > buildkitd.toml <<EOF
    [registry."harbor.sisys.local"]
      ca = ["/tmp/buildkit-certs/harbor/ca.crt"]
    EOF

- name: 登录 Harbor
  uses: docker/login-action@v3
  with:
    registry: ${{ vars.HARBOR_REGISTRY }}
    username: ${{ secrets.HARBOR_ROBOT_USERNAME }}
    password: ${{ secrets.HARBOR_ROBOT_PASSWORD }}

# Trivy 扫描配置
env:
  TRIVY_INSECURE: 'true'              # 跳过 TLS 验证
  TRIVY_DB_REPOSITORY: 'harbor.sisys.local/sisys/aquasecurity/trivy-db:2'
```

#### 当前 CA 同步问题分析

| 问题 | 影响 | 自动续期后变化 |
|------|------|--------------|
| **静态 Secret** | CA 证书手动创建，过期需手动更新 | cert-manager 自动续期后需同步更新 Secret |
| **多命名空间复制** | 每个命名空间独立维护 `ca-certificates` Secret | 需建立自动同步机制 |
| **insecure-registries** | DinD 跳过验证，证书更换无影响 | 可保持不变或移除以提升安全性 |
| **CI Pipeline 硬编码** | `secrets.HARBOR_CA_CRT` 需手动更新 | 需改为动态获取或自动同步 |
| **NODE_EXTRA_CA_CERTS** | Node.js 独立信任链 | 需确保与系统证书同步 |

### 1.4 信任关系

```
当前架构:
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Gitea      │    │   Harbor     │    │   ArgoCD     │
│ 自签证书     │    │ 自签证书     │    │ 自签证书     │
│ (同一份)     │    │ (同一份)     │    │ (同一份)     │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                  ┌────────▼────────┐
                  │   containerd    │
                  │ insecure:true   │
                  └────────┬────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
     ┌────────▼────────┐      ┌────────▼────────┐
     │  Runner DinD    │      │  CI Pipeline    │
     │ insecure-regs   │      │ HARBOR_CA_CRT   │
     └─────────────────┘      └─────────────────┘
```

**问题**:
- 证书到期前需要手动更新 3 个服务
- containerd 不验证证书，存在中间人攻击风险
- 无自动续期，维护成本高

---

## 2. 目标架构

### 2.1 证书层次结构

```
目标架构:
┌─────────────────────────────────────────────────────────┐
│                 内部 CA (*.sisys.local CA)                │
│  算法: ECDSA P-256  |  有效期: 10年  |  自动续期: 否      │
│  用途: 签发内部服务证书 + Runner/DinD 信任锚              │
└────────┬─────────────────┬─────────────────┬─────────────┘
         │                 │                 │
    ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
    │ Harbor  │      │ Gitea   │      │ ArgoCD  │
    │ TLS     │      │ TLS     │      │ TLS     │
    │ 90天    │      │ 90天    │      │ 90天    │
    │ 自动续期│      │ 自动续期│      │ 自动续期│
    └────┬────┘      └────┬────┘      └────┬────┘
         │                │                │
         └────────────────┴────────────────┘
                          │
                 ┌────────▼────────┐
                 │   containerd    │
                 │  信任内部 CA    │
                 └────────┬────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
     ┌────────▼────────┐     ┌────────▼────────┐
     │  Runner DinD    │     │  CI Pipeline    │
     │ 自动同步 CA     │     │ 自动同步 CA     │
     └─────────────────┘     └─────────────────┘
```

### 2.2 Runner/DinD CA 自动同步机制

```
CA 同步架构:
┌─────────────────────────────────────────────────────────┐
│           cert-manager 签发新服务证书                      │
│                    ↓                                     │
│           更新 TLS Secret (harbor-tls-secret)             │
│                    ↓                                     │
│     ┌──────────────┴──────────────┐                      │
│     │  CA 同步控制器 (CronJob)    │                      │
│     │  每 5 分钟检查证书变化       │                      │
│     └──────┬──────────┬──────────┘                      │
│            │          │                                  │
│   ┌────────▼──┐  ┌───▼────────┐                         │
│   │gitea-     │  │gitea-      │  ... (其他命名空间)      │
│   │advacts    │  │actions     │                         │
│   │ca-cert    │  │ca-cert     │                         │
│   └───────────┘  └────────────┘                         │
└─────────────────────────────────────────────────────────┘
```

**同步机制**:

| 组件 | 同步方式 | 更新频率 | 影响 |
|------|---------|---------|------|
| **Runner CA Secret** | CronJob 自动同步 | 证书变化后 5 分钟内 | 需重启 Runner Pod |
| **DinD insecure-registries** | 保持不变 | 无需更新 | 证书更换无影响 |
| **CI Pipeline CA** | 从 Secret 动态注入 | 每次 Pipeline 执行 | 无需修改 workflow |
| **containerd CA** | 节点级同步脚本 | 证书变化后执行 | 需重启 containerd |

### 2.3 关键改进

| 改进项 | 当前状态 | 目标状态 |
|--------|---------|---------|
| 证书管理 | 手动 | cert-manager 自动 |
| 证书有效期 | 1 年 | 90 天 (自动续期) |
| 证书层级 | 扁平 (各自独立) | 层次化 (CA → 服务证书) |
| containerd 验证 | insecure_skip_verify | 完整验证 |
| 续期操作 | 手动更新 3 个服务 | 零人工干预 |

---

## 3. 分阶段实施计划

### 阶段概览 (修正版)

| 阶段 | 名称 | 预计时间 | 影响范围 | 风险等级 |
|------|------|---------|---------|---------|
| Phase 1 | 部署内部 CA + cert-manager v1.16.2 | 30 分钟 | 无服务中断 | 低 |
| Phase 2 | 更新 containerd 信任 (K3S 原生) | 10 分钟 | containerd 短暂重启 | 中 |
| Phase 3 | 迁移 Harbor 证书 | 15 分钟 | Harbor 短暂重启 | 中 |
| Phase 4 | 迁移 Gitea 证书 | 15 分钟 | Gitea 短暂重启 | 中 |
| Phase 5 | 迁移 ArgoCD 证书 | 15 分钟 | ArgoCD 短暂重启 | 中 |
| Phase 5.5 | 同步 CA 到 Runner 命名空间 | 15 分钟 | Runner 短暂重启 | 中 |
| Phase 6 | 部署 Pod 热加载 (Reloader) | 10 分钟 | 无影响 | 低 |
| Phase 6.5 | 部署监控告警 (必选) | 5 分钟 | 无影响 | 无 |
| Phase 7 | E2E 测试和故障注入 | 20 分钟 | 无影响 | 无 |

> **🟠 修正**: Phase 顺序调整 - 先更新 containerd 信任 (Phase 2)，再迁移服务证书 (Phase 3-5)。
> 这确保容器运行时在证书更换前已信任新 CA。

---

## 4. 详细执行步骤

### Phase 1: 部署内部 CA + cert-manager (30 分钟)

#### 1.1 生成内部 CA 密钥对

```bash
# 创建目录结构
mkdir -p deployments/certificates

# 生成内部 CA 私钥 (ECDSA P-256)
openssl ecparam -genkey -name prime256v1 -noout -out deployments/certificates/ca.key

# 生成 CA 证书 (10 年有效期)
openssl req -new -x509 -key deployments/certificates/ca.key \
  -out deployments/certificates/ca.crt \
  -days 3650 \
  -subj "/O=SISYS/CN=SISYS Internal CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign"

# 创建 Kubernetes Secret
kubectl create secret tls sisys-internal-ca \
  --cert=deployments/certificates/ca.crt \
  --key=deployments/certificates/ca.key \
  -n cert-manager --dry-run=client -o yaml | \
  kubectl apply -f -
```

**生成的配置文件**:
```yaml
# deployments/certificates/internal-ca.yaml
apiVersion: v1
kind: Secret
metadata:
  name: sisys-internal-ca
  namespace: cert-manager
  labels:
    app: certificate-authority
    managed-by: kustomize
type: kubernetes.io/tls
data:
  tls.crt: <base64-encoded-ca-cert>
  tls.key: <base64-encoded-ca-key>
```

#### 1.2 安装 cert-manager

```bash
# 检查是否已安装
kubectl get deployment -n cert-manager 2>/dev/null || echo "未安装"

# 安装 cert-manager (使用 K3S 兼容版本)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.2/cert-manager.yaml

# 等待组件就绪
kubectl wait --for=condition=Available deployment/cert-manager -n cert-manager --timeout=120s
kubectl wait --for=condition=Available deployment/cert-manager-cainjector -n cert-manager --timeout=120s
kubectl wait --for=condition=Available deployment/cert-manager-webhook -n cert-manager --timeout=120s
```

#### 1.3 创建 InternalCA ClusterIssuer

```yaml
# deployments/certificates/clusterissuer.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: sisys-internal-ca
  labels:
    app: certificate-authority
    managed-by: kustomize
spec:
  ca:
    secretName: sisys-internal-ca
```

**应用配置**:
```bash
kubectl apply -f deployments/certificates/clusterissuer.yaml

# 验证
kubectl get clusterissuer sisys-internal-ca
```

#### 1.4 CA 证书备份与安全存储

```bash
# 1. 备份 CA 证书和私钥
cp deployments/certificates/ca.crt /etc/kubernetes/ca.crt
cp deployments/certificates/ca.key /etc/kubernetes/ca.key

# 2. 设置严格权限 (仅 root 可读)
chmod 600 /etc/kubernetes/ca.key
chmod 644 /etc/kubernetes/ca.crt
chown root:root /etc/kubernetes/ca.key /etc/kubernetes/ca.crt
```

> **🔴 安全警告**: CA 私钥以 Kubernetes Secret 明文存储在 etcd 中，
> 任何有 etcd 访问权限的用户都可提取私钥并签发伪造证书。

**缓解措施**:

```bash
# 方案 1: 启用 K3S etcd 加密 (推荐 MVP 阶段)
# 编辑 K3S 配置 /etc/rancher/k3s/config.yaml
cat >> /etc/rancher/k3s/config.yaml << 'EOF'
encrypt-secrets:
  - v1/Secret
EOF
sudo systemctl restart k3s

# 方案 2: 使用外部密钥管理 (生产推荐)
# - HashiCorp Vault
# - AWS KMS / GCP Cloud KMS
# - 将 cert-manager 配置为使用 KMS 签名器

# 验证 etcd 加密
sudo etcdctl get /registry/secrets/cert-manager/sisys-internal-ca --endpoints=127.0.0.1:2379 | \
  grep -c "BEGIN EC PRIVATE KEY"  # 应返回 0 (已加密)   # pragma: allowlist secret
```

**CA 私钥访问控制清单**:

| 角色 | 访问方式 | 权限 |
|------|---------|------|
| cert-manager | Kubernetes Secret (自动) | 读写 |
| 运维人员 | `/etc/kubernetes/ca.key` | 仅读取 (紧急恢复) |
| CI/CD Pipeline | 无 | ❌ 禁止访问 |
| 开发者 | 无 | ❌ 禁止访问 |

---

### Phase 2: 迁移 Harbor 证书 (15 分钟)

#### 2.1 备份现有证书

```bash
kubectl get secret -n harbor harbor-tls-secret -o yaml > backup/harbor-tls-backup-$(date +%Y%m%d).yaml
```

#### 2.2 创建 Harbor Certificate 资源

```yaml
# deployments/harbor/harbor-certificate.yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: harbor-tls
  namespace: harbor
  labels:
    app: harbor
    story: "0.6"
  annotations:
    description: "Harbor TLS 证书 (cert-manager 自动管理)"
spec:
  # 目标 Secret 名称 (与现有 secret 相同，自动替换)
  secretName: harbor-tls-secret

  # 证书有效期和续期策略
  duration: 2160h       # 90 天
  renewBefore: 720h     # 到期前 30 天续期

  # 证书主题
  subject:
    organizations:
      - SISYS

  # DNS 名称 (精确 SAN，不使用通配符)
  # ⚠️ 修正: 避免 *.sisys.local，任一证书泄露可冒充任意服务
  dnsNames:
    - harbor.sisys.local
    # 如需子域名: core.harbor.sisys.local, registry.harbor.sisys.local

  # 私钥配置
  privateKey:
    algorithm: ECDSA
    size: 256
    rotationPolicy: Always  # 每次续期轮换密钥

  # 证书用途
  usages:
    - server auth
    - client auth

  # 使用内部 CA 签发
  issuerRef:
    name: sisys-internal-ca
    kind: ClusterIssuer
    group: cert-manager.io
```

#### 2.3 应用并验证

```bash
# 应用 Certificate 资源
kubectl apply -f deployments/harbor/harbor-certificate.yaml

# 等待证书签发完成
kubectl wait --for=condition=Ready certificate/harbor-tls -n harbor --timeout=60s

# 验证新证书
kubectl get secret -n harbor harbor-tls-secret -o jsonpath='{.data.tls\.crt}' | base64 -d | \
  openssl x509 -noout -subject -issuer -dates -fingerprint -sha256
```

**预期输出**:
```
subject=O = SISYS, CN = *.sisys.local
issuer=O = SISYS, CN = SISYS Internal CA
notBefore=Apr  6 XX:XX:XX 2026 GMT
notAfter=Jul  5 XX:XX:XX 2026 GMT
sha256 Fingerprint=XX:XX:XX:...  ← 新指纹，与原证书不同
```

#### 2.4 重启 Harbor Pod 使新证书生效

```bash
# 滚动重启相关组件
kubectl rollout restart deployment harbor-core -n harbor
kubectl rollout restart deployment harbor-nginx -n harbor

# 等待重启完成
kubectl rollout status deployment harbor-core -n harbor --timeout=120s
kubectl rollout status deployment harbor-nginx -n harbor --timeout=120s

# 验证 HTTPS 访问
curl -vk https://harbor.sisys.local/api/v2.0/ping
```

---

### Phase 3: 迁移 Gitea 证书 (15 分钟)

#### 3.1 备份现有证书

```bash
kubectl get secret -n gitea gitea-tls-secret -o yaml > backup/gitea-tls-backup-$(date +%Y%m%d).yaml
```

#### 3.2 创建 Gitea Certificate 资源

```yaml
# deployments/gitea/gitea-certificate.yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: gitea-tls
  namespace: gitea
  labels:
    app: gitea
spec:
  secretName: gitea-tls-secret
  duration: 2160h       # 90 天
  renewBefore: 720h     # 30 天前续期
  dnsNames:
    - gitea.sisys.local  # ✅ 精确 SAN，不使用通配符
  privateKey:
    algorithm: ECDSA
    size: 256
    rotationPolicy: Always
  usages:
    - server auth
  issuerRef:
    name: sisys-internal-ca
    kind: ClusterIssuer
```

#### 3.3 应用并重启

```bash
kubectl apply -f deployments/gitea/gitea-certificate.yaml
kubectl wait --for=condition=Ready certificate/gitea-tls -n gitea --timeout=60s

# 重启 Gitea
kubectl rollout restart deployment gitea -n gitea
kubectl rollout status deployment gitea -n gitea --timeout=120s

# 验证
curl -vk https://gitea.sisys.local/api/v1/version
```

---

### Phase 4: 迁移 ArgoCD 证书 (15 分钟)

#### 4.1 备份现有证书

```bash
kubectl get secret -n argocd argocd-tls-secret -o yaml > backup/argocd-tls-backup-$(date +%Y%m%d).yaml
```

#### 4.2 创建 ArgoCD Certificate 资源

```yaml
# deployments/argocd/argocd-certificate.yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: argocd-tls
  namespace: argocd
  labels:
    app: argocd
spec:
  secretName: argocd-tls-secret
  duration: 2160h
  renewBefore: 720h
  dnsNames:
    - argocd.sisys.local  # ✅ 精确 SAN，不使用通配符
  privateKey:
    algorithm: ECDSA
    size: 256
    rotationPolicy: Always
  usages:
    - server auth
  issuerRef:
    name: sisys-internal-ca
    kind: ClusterIssuer
```

#### 4.3 应用并重启

```bash
kubectl apply -f deployments/argocd/argocd-certificate.yaml
kubectl wait --for=condition=Ready certificate/argocd-tls -n argocd --timeout=60s

# 重启 ArgoCD Server
kubectl rollout restart deployment argocd-server -n argocd
kubectl rollout status deployment argocd-server -n argocd --timeout=120s

# 验证
curl -vk https://argocd.sisys.local/api/version
```

---

### Phase 5: 更新 containerd 信任 (10 分钟)

#### 5.1 备份现有配置

```bash
cp /etc/rancher/k3s/registries.yaml /etc/rancher/k3s/registries.yaml.backup-$(date +%Y%m%d)
```

#### 5.2 安装内部 CA 到 containerd (K3S 原生方式)

> **⚠️ 关键修正**: 直接修改 `/etc/containerd/certs.d/` 会与 K3S 内置 containerd 配置冲突。
> K3S 使用自定义 containerd 配置路径，应通过 K3S 路径分发 CA。

```bash
# ✅ 正确方式：使用 K3S 原生 containerd 配置路径
# K3S 会同步 /etc/rancher/k3s/ 配置到内置 containerd

# 1. 创建 K3S 证书目录
sudo mkdir -p /etc/rancher/k3s/certs

# 2. 安装内部 CA 证书
sudo cp /etc/kubernetes/ca.crt /etc/rancher/k3s/certs/internal-ca.crt
sudo chmod 644 /etc/rancher/k3s/certs/internal-ca.crt

# 3. 创建 K3S containerd hosts.toml
sudo mkdir -p /var/lib/rancher/k3s/agent/etc/containerd/certs.d/_default
cat > /var/lib/rancher/k3s/agent/etc/containerd/certs.d/_default/hosts.toml << 'EOF'
server = "https://harbor.sisys.local"

[host."https://harbor.sisys.local"]
  capabilities = ["pull", "resolve", "push"]
  ca = "/etc/rancher/k3s/certs/internal-ca.crt"
EOF
```

**⚠️ 常见错误**:

| 错误路径 | 正确路径 | 原因 |
|---------|---------|------|
| `/etc/containerd/certs.d/` | `/var/lib/rancher/k3s/agent/etc/containerd/certs.d/` | K3S 使用内置 containerd 配置 |
| 直接修改 containerd 配置 | 通过 K3S `registries.yaml` 同步 | 直接修改会被 K3S 覆盖 |

#### 5.3 更新 registries.yaml

```yaml
# 修改前 (当前配置)
configs:
  harbor.sisys.local:
    tls:
      insecure_skip_verify: true  # ← 移除这行
    auth:
      username: "robot$sisys+gitea-runner-push"
      password: ""   # pragma: allowlist secret

# 修改后
configs:
  harbor.sisys.local:
    tls:
      # insecure_skip_verify 已移除，使用完整证书验证
    auth:
      username: "robot$sisys+gitea-runner-push"
      password: ""   # pragma: allowlist secret
```

#### 5.4 重启 containerd

```bash
# 重启 containerd 服务
systemctl restart containerd

# 验证 containerd 状态
systemctl status containerd

# 测试镜像拉取 (使用测试镜像)
kubectl run test-pull --image=harbor.sisys.local/sisys/tools/gitea:1.25.4-rootless \
  --restart=Never --dry-run=client -o yaml | kubectl apply -f -

# 等待并验证
kubectl wait --for=condition=Ready pod/test-pull --timeout=60s
kubectl delete pod test-pull
```

---

### Phase 5.5: 同步 CA 到 Runner 命名空间和 DinD (15 分钟)

#### 5.5.1 CA 同步策略选择

> **🟡 改进**: 5 分钟轮询对 90 天证书来说是过度设计。
> 改为**事件驱动**方式：监听 cert-manager Certificate 变化自动触发同步。

**方案对比**:

| 方案 | 触发时机 | 资源消耗 | 延迟 | 推荐度 |
|------|---------|---------|------|--------|
| 轮询 (5 分钟) | 定时检查 | 高 (每 5 分钟 API 调用) | ≤5 分钟 | ❌ 不推荐 |
| **事件驱动 (推荐)** | cert-manager Certificate 更新事件 | 极低 (仅事件触发) | <10 秒 | ✅ 推荐 |
| 手动触发 | 运维人员手动运行 | 无 | 人工延迟 | ⚠️ 备份方案 |

**事件驱动实现**:

```yaml
# deployments/certificates/ca-sync-job.yaml
# 此 Job 由 cert-manager Certificate 更新事件触发
apiVersion: batch/v1
kind: Job
metadata:
  name: ca-cert-sync
  namespace: cert-manager
  labels:
    app: ca-sync
    managed-by: kustomize
  annotations:
    # 由 cert-manager 的 post-issuance hook 触发
    # 或通过 Kubernetes Event 监听实现
    trigger: "cert-manager-certificate-updated"
spec:
  template:
    spec:
      serviceAccountName: ca-sync-sa
      containers:
      - name: ca-sync
        # ✅ 使用固定版本，禁止 :latest
        image: bitnami/kubectl:1.31.4
        command: ["/bin/sh", "-c"]
        args:
          - |
            #!/bin/sh
            set -euo pipefail

            echo "🔄 开始 CA 证书同步..."

            # 获取内部 CA 证书
            CA_CRT=$(kubectl get secret sisys-internal-ca -n cert-manager \
              -o jsonpath='{.data.tls\.crt}')

            # ✅ 补全所有命名空间
            NAMESPACES="gitea-advacts gitea-actions gitea harbor argocd"

            for NS in $NAMESPACES; do
              echo "📋 检查命名空间: $NS"

              # 检查命名空间是否存在
              if ! kubectl get namespace $NS >/dev/null 2>&1; then
                echo "⚠️ 命名空间 $NS 不存在，跳过"
                continue
              fi

              # 获取现有 CA Secret (如果存在)
              EXISTING_CRT=$(kubectl get secret ca-certificates -n $NS \
                -o jsonpath='{.data.ca-certificates\.crt}' 2>/dev/null || echo "")

              # 比较证书是否变化
              if [ "$CA_CRT" != "$EXISTING_CRT" ]; then
                echo "🔄 证书已变化，正在更新..."

                # 创建/更新 Secret
                kubectl create secret generic ca-certificates \
                  --from-literal=ca-certificates.crt="$CA_CRT" \
                  -n $NS \
                  --dry-run=client -o yaml | kubectl apply -f -

                echo "✅ $NS CA 证书已更新"

                # 重启相关 Pod 使新证书生效
                echo "🔄 重启相关 Pod..."
                kubectl rollout restart statefulset gitea-runner-dind -n $NS 2>/dev/null || true
                kubectl rollout restart deployment harbor-core -n $NS 2>/dev/null || true
              else
                echo "✅ $NS 证书已是最新"
              fi
            done

            echo "✅ CA 证书同步完成"
      restartPolicy: Never
  backoffLimit: 3
  ttlSecondsAfterFinished: 3600
```

**自动触发机制**:

```bash
# 方案 1: 使用 cert-manager 的 Certificate status 变更触发
# 创建 EventWatcher 监听 Certificate 事件
cat << 'EOF' | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: cert-watcher
rules:
- apiGroups: ["cert-manager.io"]
  resources: ["certificates"]
  verbs: ["get", "watch", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: cert-watcher-binding
subjects:
- kind: ServiceAccount
  name: ca-sync-sa
  namespace: cert-manager
roleRef:
  kind: ClusterRole
  name: cert-watcher
  apiGroup: rbac.authorization.k8s.io
EOF

# 方案 2: 手动触发 (备份方案)
kubectl create job -n cert-manager ca-cert-sync-manual \
  --from=job/ca-cert-sync
```

#### 5.5.2 创建 ServiceAccount 和 RBAC (全命名空间)

> **🟠 关键修正**: 原方案仅定义了 `gitea-advacts` 的 RBAC，
> 缺少 `gitea-actions`、`gitea`、`harbor`、`argocd` 等命名空间。

```yaml
# deployments/certificates/ca-sync-rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ca-sync-sa
  namespace: cert-manager
---
# 基础权限：读取 cert-manager 命名空间的 CA Secret
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: ca-sync-role
  namespace: cert-manager
rules:
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["sisys-internal-ca"]  # ✅ 最小权限：仅读取特定 Secret
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ca-sync-rolebinding
  namespace: cert-manager
subjects:
- kind: ServiceAccount
  name: ca-sync-sa
  namespace: cert-manager
roleRef:
  kind: Role
  name: ca-sync-role
  apiGroup: rbac.authorization.k8s.io
---
# ✅ 为每个需要同步的命名空间创建独立 Role/RoleBinding
# 使用变量定义目标命名空间列表 (在 apply 时展开)
{{- range $ns := list "gitea-advacts" "gitea-actions" "gitea" "harbor" "argocd" }}
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: ca-sync-role-remote
  namespace: {{ $ns }}
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list", "create", "update", "patch"]
- apiGroups: ["apps"]
  resources: ["statefulsets", "deployments"]
  verbs: ["get", "patch"]  # 用于 rollout restart
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ca-sync-rolebinding-remote
  namespace: {{ $ns }}
subjects:
- kind: ServiceAccount
  name: ca-sync-sa
  namespace: cert-manager
roleRef:
  kind: Role
  name: ca-sync-role-remote
  apiGroup: rbac.authorization.k8s.io
---
{{- end }}
```

**实际部署时的 RBAC 应用** (不使用模板引擎时):

```bash
# 为每个命名空间应用 RBAC
for NS in gitea-advacts gitea-actions gitea harbor argocd; do
  kubectl create role ca-sync-role-remote -n $NS \
    --verb=get,list,create,update,patch --resource=secrets \
    --verb=get,patch --resource=statefulsets,deployments
  kubectl create rolebinding ca-sync-rolebinding-remote -n $NS \
    --role=ca-sync-role-remote \
    --serviceaccount=cert-manager:ca-sync-sa
done
```

**应用配置**:

```bash
# 应用 RBAC
kubectl apply -f deployments/certificates/ca-sync-rbac.yaml

# 应用 CronJob
kubectl apply -f deployments/certificates/ca-sync-cronjob.yaml

# 验证 CronJob
kubectl get cronjob -n cert-manager

# 手动触发一次同步进行测试
kubectl create job -n cert-manager ca-sync-manual --from=cronjob/ca-cert-sync
kubectl logs -n cert-manager job/ca-sync-manual -f
```

#### 5.5.3 更新 CI Pipeline 动态获取 CA

> **🟠 关键修正**: CI Pipeline 在 Runner 容器内运行，访问 K8s Secret 需要额外 RBAC。
> 原方案可能导致静默失败。

**CI Pipeline RBAC 配置**:

```yaml
# .gitea/workflows/ci.yaml 中添加 RBAC 检查
# 方案 1: Runner ServiceAccount 已绑定足够权限 (推荐)
# 检查当前 Runner SA 权限:
kubectl auth can-i get secrets --as=system:serviceaccount:gitea-advacts:gitea-runner-dind \
  -n gitea-advacts

# 如果返回 no，需要添加权限:
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: runner-secret-reader
  namespace: gitea-advacts
rules:
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["ca-certificates"]  # ✅ 最小权限
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: runner-secret-reader-binding
  namespace: gitea-advacts
subjects:
- kind: ServiceAccount
  name: gitea-runner-dind  # Runner 使用的 SA
  namespace: gitea-advacts
roleRef:
  kind: Role
  name: runner-secret-reader
  apiGroup: rbac.authorization.k8s.io
```

**修改后的 CI Pipeline**:

```yaml
# .gitea/workflows/ci.yaml
- name: 配置 CA 链
  run: |
    # ✅ 从命名空间 Secret 动态获取 CA (带 RBAC 检查)
    NS=$(cat /var/run/secrets/kubernetes.io/serviceaccount/namespace)

    # 检查 RBAC 权限
    if ! kubectl auth can-i get secrets --namespace=$NS 2>/dev/null; then
      echo "⚠️ 无 K8s Secret 读取权限，使用环境变量回退"
      echo "$HARBOR_CA_CRT_ENV" > /tmp/buildkit-certs/harbor/ca.crt
    else
      CA_CRT=$(kubectl get secret ca-certificates -n $NS \
        -o jsonpath='{.data.ca-certificates\.crt}' 2>/dev/null | base64 -d || echo "")
      if [ -n "$CA_CRT" ]; then
        echo "$CA_CRT" > /tmp/buildkit-certs/harbor/ca.crt
      else
        echo "⚠️ CA Secret 不存在，使用环境变量"
        echo "$HARBOR_CA_CRT_ENV" > /tmp/buildkit-certs/harbor/ca.crt
      fi
    fi

    # 安装到系统信任链
    cp /tmp/buildkit-certs/harbor/ca.crt /usr/local/share/ca-certificates/harbor.crt
    update-ca-certificates
```

#### 5.5.4 验证 CA 同步

```bash
# 验证 Runner CA 证书
kubectl get secret -n gitea-advacts ca-certificates -o jsonpath='{.data.ca-certificates\.crt}' | base64 -d | \
  openssl x509 -noout -subject -issuer

# 验证 Runner 容器内证书
kubectl exec -n gitea-advacts gitea-runner-dind-0 -- cat /etc/ssl/certs/ca-certificates.crt | \
  grep -A 2 "SISYS Internal CA"

# 触发 Pipeline 测试
gitea 手动触发 CI Pipeline
```

---

### Phase 6: 更新 containerd 信任 (10 分钟)

#### 6.1 备份现有配置

```bash
cp /etc/rancher/k3s/registries.yaml /etc/rancher/k3s/registries.yaml.backup-$(date +%Y%m%d)
```

#### 6.2 安装内部 CA 到 containerd

```bash
# 创建证书目录
mkdir -p /etc/containerd/certs.d

# 复制内部 CA 证书
cp /etc/kubernetes/ca.crt /etc/containerd/certs.d/ca.crt
```

---

### Phase 7: 验证自动续期 (5 分钟)

#### 7.1 检查所有 Certificate 状态

# 预期输出:
# NAMESPACE   NAME           READY   SECRET               AGE
# harbor      harbor-tls     True    harbor-tls-secret    10m
# gitea       gitea-tls      True    gitea-tls-secret     8m
# argocd      argocd-tls     True    argocd-tls-secret    5m
```

#### 6.2 验证续期策略

```bash
kubectl describe certificate harbor-tls -n harbor | grep -A 10 "Status:"
# 检查:
# - Not Before / Not After 日期
# - Renewal Time
# - Last Transition Time
```

#### 6.3 监控配置

```bash
# 创建 Certificate 到期告警 (可选)
cat << EOF | kubectl apply -f -
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: certificate-expiry-alert
  namespace: cert-manager
spec:
  groups:
  - name: certificate.rules
    rules:
    - alert: CertificateExpiringSoon
      expr: certmanager_certificate_expiration_timestamp_seconds - time() < 7*24*3600
      for: 1h
      labels:
        severity: warning
      annotations:
        summary: "Certificate {{ $labels.name }} expires in less than 7 days"
        description: "Certificate {{ $labels.namespace }}/{{ $labels.name }} is about to expire"
EOF
```

#### 6.3 监控配置 (必选，非可选)

> **🟠 关键修正**: 对"自动续期"系统，续期失败告警是**必须**而非可选。

```bash
# 创建 Certificate 到期告警 (必选)
cat << 'EOF' | kubectl apply -f -
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: certificate-expiry-alert
  namespace: cert-manager
spec:
  groups:
  - name: certificate.rules
    rules:
    # 告警 1: 证书将在 7 天内到期 (Warning)
    - alert: CertificateExpiringSoon
      expr: certmanager_certificate_expiration_timestamp_seconds - time() < 7*24*3600
      for: 1h
      labels:
        severity: warning
      annotations:
        summary: "证书 {{ $labels.name }} 将在 7 天内到期"
        description: "命名空间 {{ $labels.namespace }} 中的证书 {{ $labels.name }} 即将到期，自动续期可能失败"

    # 告警 2: 证书将在 24 小时内到期 (Critical)
    - alert: CertificateExpiringCritical
      expr: certmanager_certificate_expiration_timestamp_seconds - time() < 24*3600
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "🔴 证书 {{ $labels.name }} 将在 24 小时内到期！"
        description: "立即检查 cert-manager 日志: kubectl logs -n cert-manager -l app=cert-manager"

    # 告警 3: 证书续期失败
    - alert: CertificateRenewalFailed
      expr: certmanager_certificate_ready_status{condition="False"} == 1
      for: 15m
      labels:
        severity: critical
      annotations:
        summary: "🔴 证书 {{ $labels.name }} 续期失败"
        description: "证书状态: Ready=False 超过 15 分钟，检查 Issuer 配置和 CA 可用性"
EOF
```

### Phase 6.5: Pod 证书热加载策略 (必选)

> **🟠 关键修正**: Secret 更新后 Pod **不会**自动 reload 新证书。
> 需要明确的热加载策略。

**方案选择**:

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **Reloader** (推荐) | 自动 watch Secret 变化并重启 Pod | 需额外部署 | ✅ 推荐 |
| cert-manager + csi-driver | Pod 内自动挂载新证书 | 配置复杂 | ⚠️ 高级用户 |
| 手动 rollout restart | 简单直接 | 需人工操作 | ❌ 不推荐 |

**部署 Reloader**:

```bash
# 安装 Reloader
kubectl apply -f https://github.com/stakater/Reloader/releases/download/v1.0.105/reloader.yaml

# 为每个 Deployment/StatefulSet 添加注解
# 示例: Harbor Core
kubectl annotate deployment harbor-core -n harbor \
  reloader.stakater.com/auto="true"

# 示例: Harbor Nginx
kubectl annotate deployment harbor-nginx -n harbor \
  reloader.stakater.com/auto="true"

# 示例: Gitea
kubectl annotate deployment gitea -n gitea \
  reloader.stakater.com/auto="true"

# 验证 Reloader 配置
kubectl get deployment -A -o jsonpath='{range .items[*]}{.metadata.name}: {.metadata.annotations.reloader\.stakater\.com/auto}{"\n"}{end}'
```

**热加载验证**:

```bash
# 1. 触发证书续期 (模拟)
kubectl annotate certificate harbor-tls -n harbor \
  cert-manager.io/issue-temporary-certificate=true --overwrite

# 2. 观察 Reloader 是否触发 Pod 重启
kubectl get events -n harbor --sort-by='.lastTimestamp' | grep -i reloader

# 3. 验证 Pod 使用新证书
kubectl exec harbor-core-xxx -n harbor -- cat /etc/harbor/ssl/tls.crt | \
  openssl x509 -noout -dates
```

### Phase 7: 证书续期 E2E 测试和故障注入 (必选)

> **🔴 关键修正**: 部署时一切正常，90 天后首次续期可能失败且无人在场。
> **必须在部署前验证续期流程。**

#### 7.1 续期模拟测试

```bash
#!/bin/bash
# deployments/certificates/test-renewal.sh
# 证书续期 E2E 测试脚本
set -euo pipefail

echo "🧪 开始证书续期 E2E 测试..."

# 测试 1: 缩短证书续期时间，触发立即续期
echo "📋 测试 1: 触发证书续期..."
kubectl annotate certificate harbor-tls -n harbor \
  cert-manager.io/issue-temporary-certificate=true --overwrite || true

# 等待续期完成 (最多 60 秒)
echo "⏳ 等待续期完成..."
for i in $(seq 1 12); do
  READY=$(kubectl get certificate harbor-tls -n harbor \
    -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
  if [ "$READY" = "True" ]; then
    echo "✅ 证书续期成功"
    break
  fi
  echo "  等待中... ($i/12)"
  sleep 5
done

# 测试 2: 验证新证书指纹不同
echo "📋 测试 2: 验证证书已更新..."
NEW_FINGERPRINT=$(kubectl get secret harbor-tls-secret -n harbor \
  -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -fingerprint -sha256)
echo "新证书指纹: $NEW_FINGERPRINT"

# 测试 3: 验证 CA 同步 Job 执行成功
echo "📋 测试 3: 验证 CA 同步..."
kubectl create job -n cert-manager ca-sync-test --from=job/ca-cert-sync
kubectl wait --for=condition=Complete job/ca-sync-test -n cert-manager --timeout=120s
echo "✅ CA 同步成功"

# 测试 4: 验证 Pod 热加载
echo "📋 测试 4: 验证 Pod 热加载..."
sleep 30  # 等待 Reloader 触发
POD_RESTARTS=$(kubectl get deployment harbor-core -n harbor \
  -o jsonpath='{.status.conditions[?(@.type=="Available")].status}')
echo "Harbor Core 可用性: $POD_RESTARTS"

# 测试 5: 验证服务可访问
echo "📋 测试 5: 验证服务可访问..."
curl -sk https://harbor.sisys.local/api/v2.0/ping > /dev/null && echo "✅ Harbor 可访问"
curl -sk https://gitea.sisys.local/api/v1/version > /dev/null && echo "✅ Gitea 可访问"
curl -sk https://argocd.sisys.local/api/version > /dev/null && echo "✅ ArgoCD 可访问"

echo ""
echo "✅ 证书续期 E2E 测试全部通过！"
```

#### 7.2 故障注入测试

```bash
#!/bin/bash
# deployments/certificates/test-failure-injection.sh
# 故障注入测试: 模拟续期失败场景
set -euo pipefail

echo "🧪 开始故障注入测试..."

# 场景 1: 模拟 CA Secret 不可用
echo "📋 场景 1: CA Secret 临时删除..."
kubectl get secret sisys-internal-ca -n cert-manager -o yaml > /tmp/ca-backup.yaml
kubectl delete secret sisys-internal-ca -n cert-manager

# 触发续期
kubectl annotate certificate harbor-tls -n harbor \
  force-renew="$(date +%s)" --overwrite

# 验证续期失败 (预期行为)
sleep 30
READY=$(kubectl get certificate harbor-tls -n harbor \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
if [ "$READY" = "False" ]; then
  echo "✅ 续期失败符合预期 (CA 不可用)"
else
  echo "❌ 续期不应成功"
fi

# 恢复 CA
kubectl apply -f /tmp/ca-backup.yaml
rm /tmp/ca-backup.yaml

# 场景 2: 模拟 RBAC 权限不足
echo "📋 场景 2: RBAC 权限不足..."
# (暂时删除 ca-sync-sa 的 RoleBinding)
kubectl delete rolebinding ca-sync-rolebinding-remote -n gitea-advacts 2>/dev/null || true

# 触发 CA 同步
kubectl create job -n cert-manager ca-sync-fail-test --from=job/ca-cert-sync

# 验证同步失败 (预期行为)
sleep 15
JOB_STATUS=$(kubectl get job ca-sync-fail-test -n cert-manager \
  -o jsonpath='{.status.failed}' 2>/dev/null || echo "0")
if [ "$JOB_STATUS" != "0" ]; then
  echo "✅ 同步失败符合预期 (RBAC 不足)"
fi

# 恢复 RBAC
kubectl apply -f deployments/certificates/ca-sync-rbac.yaml

echo ""
echo "✅ 故障注入测试完成！"
```

**运行测试**:

```bash
# 部署前必须运行
bash deployments/certificates/test-renewal.sh
bash deployments/certificates/test-failure-injection.sh
```

---

## 5. 文件清单

### 新增文件 (修正版)

| 文件路径 | 类型 | 用途 |
|---------|------|------|
| `deployments/certificates/internal-ca.yaml` | Secret | 内部 CA 密钥对 |
| `deployments/certificates/clusterissuer.yaml` | ClusterIssuer | cert-manager CA 签发器 |
| `deployments/certificates/ca-sync-job.yaml` | Job | CA 事件驱动同步 |
| `deployments/certificates/ca-sync-rbac.yaml` | RBAC | 全命名空间权限 |
| `deployments/certificates/test-renewal.sh` | Script | 证书续期 E2E 测试 |
| `deployments/certificates/test-failure-injection.sh` | Script | 故障注入测试 |
| `deployments/certificates/README.md` | Markdown | 证书管理文档 |
| `deployments/harbor/harbor-certificate.yaml` | Certificate | Harbor TLS 证书定义 |
| `deployments/gitea/gitea-certificate.yaml` | Certificate | Gitea TLS 证书定义 |
| `deployments/argocd/argocd-certificate.yaml` | Certificate | ArgoCD TLS 证书定义 |

### 备份文件

| 文件路径 | 用途 |
|---------|------|
| `backup/harbor-tls-backup-YYYYMMDD.yaml` | Harbor 原证书备份 |
| `backup/gitea-tls-backup-YYYYMMDD.yaml` | Gitea 原证书备份 |
| `backup/argocd-tls-backup-YYYYMMDD.yaml` | ArgoCD 原证书备份 |
| `/etc/rancher/k3s/registries.yaml.backup-YYYYMMDD` | containerd 原配置备份 |

---

## 6. 风险评估与缓解

### 6.1 风险矩阵

| 风险项 | 可能性 | 影响程度 | 风险等级 | 缓解措施 |
|--------|--------|---------|---------|---------|
| cert-manager 安装失败 | 低 | 低 | **低** | 使用稳定版本，验证 CRDs 创建 |
| 新证书签发失败 | 低 | 中 | **低** | 保留原证书备份，可快速回滚 |
| 服务重启后无法启动 | 低 | 高 | **中** | 滚动重启，验证健康检查 |
| containerd 重启中断镜像拉取 | 中 | 低 | **低** | 持续仅数秒，在低峰期执行 |
| 自动续期失败 | 低 | 中 | **低** | 设置告警监控，90 天窗口 |
| CA 密钥泄露 | 极低 | 高 | **中** | 严格权限控制，600 权限 |

### 6.2 各阶段风险详情

#### Phase 1: 低风险
- 仅部署基础设施，不影响现有服务
- 失败可安全清理，无副作用

#### Phase 2-4: 中等风险
- 每个服务独立操作，可逐一验证
- 单个服务失败不影响其他服务
- 回滚只需恢复备份 Secret

#### Phase 5: 中等风险
- containerd 重启影响所有 Pod 镜像拉取
- 持续仅 2-5 秒
- 已在运行的 Pod 不受影响

#### Phase 6: 无风险
- 仅验证操作，无配置变更

---

## 7. 回滚方案

### 7.1 通用回滚原则

1. **保留所有原证书备份** - Phase 2-4 每步操作前备份
2. **按相反顺序回滚** - 从 Phase 5 → Phase 1
3. **验证每个回滚步骤** - 确认服务恢复正常

### 7.2 分阶段回滚命令

#### 回滚 Phase 5 (containerd)

```bash
# 恢复原 registries.yaml
cp /etc/rancher/k3s/registries.yaml.backup-YYYYMMDD /etc/rancher/k3s/registries.yaml

# 移除 CA 证书
rm -f /etc/containerd/certs.d/ca.crt
rm -rf /etc/containerd/certs.d/harbor.sisys.local/
rm -rf /etc/containerd/certs.d/_default/

# 重启 containerd
systemctl restart containerd

# 验证
crictl pull harbor.sisys.local/sisys/tools/gitea:1.25.4-rootless
```

#### 回滚 Phase 2-4 (服务证书)

```bash
# 恢复 Harbor 原证书
kubectl apply -f backup/harbor-tls-backup-YYYYMMDD.yaml

# 重启使原证书生效
kubectl rollout restart deployment harbor-core harbor-nginx -n harbor

# 删除 Certificate 资源
kubectl delete -f deployments/harbor/harbor-certificate.yaml

# 对 Gitea/ArgoCD 执行相同操作
```

#### 回滚 Phase 1 (cert-manager)

```bash
# 删除 cert-manager (仅当完全失败时)
kubectl delete -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.3/cert-manager.yaml

# 删除内部 CA Secret
kubectl delete secret sisys-internal-ca -n cert-manager
```

---

## 8. 验证清单

### 8.1 Phase 1 验证

- [ ] cert-manager Pod 全部 Running (v1.16.2)
- [ ] ClusterIssuer `sisys-internal-ca` 状态 Ready
- [ ] CA 证书已备份到 `/etc/kubernetes/` (权限 600)
- [ ] etcd Secret 加密已启用 (验证: `etcdctl get` 返回加密内容)
- [ ] 各命名空间 kube-root-ca.crt 未变化

### 8.2 Phase 2 验证 (containerd 信任 - K3S 原生)

- [ ] `/var/lib/rancher/k3s/agent/etc/containerd/certs.d/_default/hosts.toml` 已创建
- [ ] `/etc/rancher/k3s/certs/internal-ca.crt` 已安装
- [ ] `registries.yaml` 中 `insecure_skip_verify` 已移除
- [ ] K3S 重启成功
- [ ] `crictl pull harbor.sisys.local/...` 成功
- [ ] 现有 Pod 未受影响

### 8.3 Phase 3 验证 (Harbor)

- [ ] Certificate `harbor-tls` Ready=True
- [ ] harbor-tls-secret 证书指纹已更新
- [ ] 证书 Issuer 为 `SISYS Internal CA`
- [ ] 证书 SAN 仅包含 `harbor.sisys.local` (无通配符)
- [ ] `curl -vk https://harbor.sisys.local` 返回 200
- [ ] Harbor Core/Nginx Pod Running
- [ ] Gitea Runner 可推送镜像到 Harbor
- [ ] Reloader 注解已添加

### 8.4 Phase 4 验证 (Gitea)

- [ ] Certificate `gitea-tls` Ready=True
- [ ] gitea-tls-secret 证书指纹已更新
- [ ] 证书 SAN 仅包含 `gitea.sisys.local` (无通配符)
- [ ] `curl -vk https://gitea.sisys.local` 返回 200
- [ ] Gitea Web 界面可访问
- [ ] Git 操作正常 (clone/push/pull)
- [ ] Reloader 注解已添加

### 8.5 Phase 5 验证 (ArgoCD)

- [ ] Certificate `argocd-tls` Ready=True
- [ ] argocd-tls-secret 证书指纹已更新
- [ ] 证书 SAN 仅包含 `argocd.sisys.local` (无通配符)
- [ ] `curl -vk https://argocd.sisys.local` 返回 200
- [ ] ArgoCD Web 界面可登录
- [ ] Application 同步正常
- [ ] Reloader 注解已添加

### 8.6 Phase 5.5 验证 (Runner/DinD CA 同步)

- [ ] CA 同步 Job 已创建并运行
- [ ] 所有命名空间 CA Secret 已更新 (gitea-advacts, gitea-actions, gitea, harbor, argocd)
- [ ] Runner Pod 重启后能正常连接 Gitea/Harbor
- [ ] CI Pipeline 能成功读取 CA 并构建镜像
- [ ] `update-ca-certificates` 在 Alpine 容器内执行成功
- [ ] CI Pipeline RBAC 已验证 (runner-secret-reader)

### 8.7 Phase 6 验证 (Pod 热加载)

- [ ] Reloader 已部署并 Running
- [ ] 所有 Deployment/StatefulSet 已添加 `reloader.stakater.com/auto="true"` 注解
- [ ] 触发证书更新后 Pod 自动重启
- [ ] 重启后 Pod 使用新证书 (验证: `openssl x509 -noout -dates`)

### 8.8 Phase 6.5 验证 (监控告警)

- [ ] PrometheusRule `certificate-expiry-alert` 已创建
- [ ] CertificateExpiringSoon 告警规则生效 (7 天)
- [ ] CertificateExpiringCritical 告警规则生效 (24 小时)
- [ ] CertificateRenewalFailed 告警规则生效
- [ ] 告警能正确触发 (测试: 模拟证书到期)

### 8.9 Phase 7 验证 (E2E 测试)

- [ ] 证书续期 E2E 测试通过 (`test-renewal.sh`)
- [ ] 故障注入测试通过 (`test-failure-injection.sh`)
- [ ] CA Secret 删除场景: 续期正确失败
- [ ] RBAC 不足场景: CA 同步正确失败
- [ ] 所有服务在证书更新后可正常访问

---

## 附录

### A. 证书规格参考

| 属性 | 内部 CA | 服务证书 |
|------|--------|---------|
| 算法 | ECDSA P-256 | ECDSA P-256 |
| 有效期 | 10 年 | 90 天 |
| 续期 | 手动 | 自动 (提前 30 天) |
| 密钥轮换 | 否 | 是 (每次续期) |
| SAN | - | `*.sisys.local`, `service.sisys.local` |

### B. 常用诊断命令

```bash
# 查看证书状态
kubectl get certificate -A
kubectl describe certificate <name> -n <namespace>

# 查看 cert-manager 日志
kubectl logs -n cert-manager deployment/cert-manager

# 查看证书详情
kubectl get secret <name> -n <namespace> -o jsonpath='{.data.tls\.crt}' | base64 -d | \
  openssl x509 -noout -text

# 测试 TLS 连接
openssl s_client -connect harbor.sisys.local:443 -servername harbor.sisys.local

# 验证证书链
openssl verify -CAfile /etc/kubernetes/ca.crt /tmp/service.crt
```

### C. 相关文档

- [cert-manager 官方文档](https://cert-manager.io/docs/)
- [K3S 私有镜像仓库配置](https://docs.k3s.io/installation/private-registry)
- [containerd 证书配置](https://github.com/containerd/containerd/blob/main/docs/hosts.md)

---

*方案制定日期: 2026-04-06*
*基于实际运行时配置分析*
*待审批后执行*
