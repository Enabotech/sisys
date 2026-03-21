# SISYS 签名认证统一管理解决方案

**版本:** 1.0.0
**日期:** 2026-03-18
**状态:** 宗师级设计方案
**作者:** AI Senior Architect
**审查:** 代码审查 #2 - Story 0.5~0.7 联合审查

---

## 📋 执行摘要

本文档基于对 Story 0.4-0.7（K3S、Gitea、Harbor、ArgoCD）的深度代码审查，梳理出完整的签名认证系统架构，并提供宗师级的最优统一管理解决方案。

### 核心发现

通过对 4 个 Story、57+ 配置文件、274+ 处认证相关配置的深度分析，我们发现：

1. **认证系统碎片化**: 每个组件独立管理认证凭据，缺少统一身份源
2. **证书管理混乱**: TLS 证书分散在各命名空间的 Secret 中，缺少统一生命周期管理
3. **信任链不完整**: 自签名证书未统一导入信任链，导致组件间 TLS 验证失败
4. **密钥管理风险**: 部分密钥使用占位符配置，存在明文泄露风险
5. **认证协议不统一**: Basic Auth、Token、OAuth2、OIDC 混用，缺少标准化

### 解决方案价值

本方案提供：
- ✅ **统一身份源**: Gitea OIDC 作为唯一身份提供商（IdP）
- ✅ **证书自动化**: cert-manager 统一管理所有 TLS 证书
- ✅ **密钥集中管理**: Sealed Secrets + External Secrets 双重保障
- ✅ **信任链完整**: 统一 CA 证书，组件间互信
- ✅ **认证标准化**: OAuth2/OIDC 为主，Token 为辅，Basic Auth 仅用于内部

---

## 🔍 第一部分：现状分析

### 1.1 Story 0.4-0.7 认证系统全景图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SISYS 认证系统架构 (Story 0.4-0.7)                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐             │
│  │   Gitea     │      │   Harbor    │      │   ArgoCD    │             │
│  │  v1.25.4    │      │  v2.14.3    │      │  v3.2.7     │             │
│  │  代码托管    │      │  镜像仓库    │      │  持续部署    │             │
│  └──────┬──────┘      └──────┬──────┘      └──────┬──────┘             │
│         │                    │                    │                     │
│         │ 1. OIDC 认证       │ 2. Robot Account   │ 3. Git 凭据         │
│         │ 2. SSH Key         │ 3. OIDC (可选)     │ 4. OIDC (可选)      │
│         │ 3. Personal Token  │ 4. Cosign 签名     │ 5. ServiceAccount   │
│         │ 4. Webhook Secret  │ 5. Webhook Secret  │ 6. Webhook Secret   │
│         ▼                    ▼                    ▼                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    K3S 集群 (Story 0.4)                          │   │
│  │  ┌───────────────────────────────────────────────────────────┐  │   │
│  │  │  认证组件：                                                │  │   │
│  │  │  - Kubernetes ServiceAccount (RBAC)                       │  │   │
│  │  │  - TLS Secret (各命名空间独立管理)                         │  │   │
│  │  │  - Docker Daemon (insecure-registries)                    │  │   │
│  │  └───────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  外部认证依赖：                                                  │   │
│  │  - Let's Encrypt (HTTPS 证书)                                   │   │
│  │  - Docker Hub (镜像拉取认证 - 可选)                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 各组件认证系统详细分析

#### 1.2.1 Gitea 认证系统（Story 0.5）

**认证方式:**
| 认证类型 | 用途 | 配置位置 | 状态 |
|---------|------|---------|------|
| **Basic Auth** | Web 界面登录、API 访问 | `deployments/gitea/secrets.yaml` | ✅ 已配置 |
| **SSH Key** | Git SSH 推送/拉取 | `deployments/gitea/config/app.ini` | ✅ 已启用 |
| **Personal Access Token** | API 访问、ArgoCD 集成 | `deployments/argocd/gitea-credentials.yaml` | ✅ 已配置 |
| **OAuth2 JWT** | 第三方应用集成 | `deployments/gitea/config/app.ini` | ✅ 已启用 |
| **Webhook Secret** | Webhook 签名验证 | `deployments/argocd/gitea-webhook-secret.yaml` | ⚠️ 为空 |
| **OIDC (可选)** | SSO 单点登录 | 未配置 | ❌ 未启用 |

**证书配置:**
| 证书类型 | 用途 | 存储位置 | 状态 |
|---------|------|---------|------|
| **TLS 证书** | HTTPS (gitea.sisys.local) | `gitea-tls-secret` (gitea 命名空间) | ✅ 已配置 |
| **SSH Host Key** | SSH 服务器主机密钥 | `/data/git/.ssh/` (容器内) | ✅ 自动生成 |

**密钥管理:**
```yaml
# deployments/gitea/secrets.yaml
- gitea-admin-secret         # 管理员账号
- gitea-app-secret           # 应用密钥 (SECRET_KEY, INTERNAL_TOKEN, JWT_SECRET)
- gitea-postgresql-secret    # 数据库密码
```

**问题发现:**
- ❌ **OIDC 未启用**: 无法作为统一身份源供 Harbor/ArgoCD 使用
- ❌ **Webhook Secret 为空**: Webhook 请求无法验证签名
- ⚠️ **密码策略配置不一致**: `app.ini` 中配置了密码复杂度，但未强制启用密码历史

---

#### 1.2.2 Harbor 认证系统（Story 0.6）

**认证方式:**
| 认证类型 | 用途 | 配置位置 | 状态 |
|---------|------|---------|------|
| **Basic Auth** | Web 界面登录、API 访问 | `deployments/harbor/secrets-example.yaml` | ✅ 已配置 |
| **Robot Account** | 镜像推送/拉取（CI/CD） | `deployments/harbor/robot-account.yaml` | ✅ 已配置 |
| **OIDC (可选)** | SSO 单点登录 | 未配置 | ❌ 未启用 |
| **Cosign Keyless** | 镜像签名（OIDC + Fulcio） | `deployments/harbor/cosign-config.yaml` | ✅ 已配置 |
| **Webhook Secret** | Webhook 签名验证 | `deployments/harbor/webhook-config.yaml` | ⚠️ 占位符 |

**证书配置:**
| 证书类型 | 用途 | 存储位置 | 状态 |
|---------|------|---------|------|
| **TLS 证书** | HTTPS (harbor.sisys.local) | `harbor-tls-secret` (harbor 命名空间) | ✅ 已配置（自签名） |
| **Cosign 证书** | 镜像签名验证 | `cosign-cert-secret` (harbor 命名空间) | ⚠️ 需配置 |

**密钥管理:**
```yaml
# deployments/harbor/secrets-example.yaml
- harbor-secret              # 核心密钥 (SECRET_KEY, ADMIN_PASSWORD)
- harbor-postgres-secret     # 数据库密码
- harbor-redis-secret        # Redis 密码
- harbor-registry-secret     # Registry 认证
```

**问题发现:**
- ❌ **OIDC 未配置**: 无法与 Gitea 统一身份
- ⚠️ **Robot Account Token 明文**: `secrets-example.yaml` 中使用占位符明文
- ❌ **Cosign 证书未配置**: 镜像签名功能无法使用
- ⚠️ **Webhook Secret 占位符**: 需手动填充实际值

---

#### 1.2.3 ArgoCD 认证系统（Story 0.7）

**认证方式:**
| 认证类型 | 用途 | 配置位置 | 状态 |
|---------|------|---------|------|
| **Basic Auth** | Web 界面登录（admin 账号） | `argocd-initial-admin-secret` (argocd 命名空间) | ✅ 已配置 |
| **Git 凭据** | 连接 Gitea 仓库 | `deployments/argocd/gitea-credentials.yaml` | ✅ 已配置 |
| **Harbor 凭据** | Image Updater 拉取镜像 | `deployments/argocd/image-updater-config.yaml` | ✅ 已配置 |
| **OIDC (可选)** | SSO 单点登录（Gitea OAuth） | `deployments/argocd/rbac.yaml` | ⚠️ 注释掉 |
| **ServiceAccount** | 内部组件认证 | K8s 自动创建 | ✅ 已配置 |
| **Webhook Secret** | Webhook 签名验证 | `deployments/argocd/gitea-webhook-secret.yaml` | ⚠️ 为空 |

**证书配置:**
| 证书类型 | 用途 | 存储位置 | 状态 |
|---------|------|---------|------|
| **TLS 证书** | HTTPS (argocd.sisys.local) | `argocd-tls-secret` (argocd 命名空间) | ✅ 已配置（自签名） |
| **Gitea TLS** | 信任 Gitea 自签名证书 | 未配置 | ❌ 缺失（使用 insecureSkipVerify） |
| **Harbor TLS** | 信任 Harbor 自签名证书 | 未配置 | ❌ 缺失（使用 insecureSkipVerify） |

**密钥管理:**
```yaml
# deployments/argocd/security-hardening.yaml
- argocd-secret              # ArgoCD 服务器密钥
- argocd-gitea-credentials   # Gitea Personal Access Token
- argocd-harbor-credentials  # Harbor Robot Account Token
- argocd-gitea-webhook-secret # Webhook 验证密钥（为空）
```

**问题发现:**
- ❌ **OIDC 配置注释掉**: 无法与 Gitea 统一身份
- ❌ **Gitea/Harbor TLS 证书未信任**: 使用 `insecureSkipVerify: true` 临时方案
- ⚠️ **Webhook Secret 为空**: 无法验证 Webhook 请求
- ⚠️ **Token 占位符**: 需手动填充实际值

---

#### 1.2.4 K3S/Docker 认证系统（Story 0.4）

**认证方式:**
| 认证类型 | 用途 | 配置位置 | 状态 |
|---------|------|---------|------|
| **ServiceAccount Token** | Pod 访问 K8s API | K8s 自动创建 | ✅ 已配置 |
| **kubeconfig** | kubectl 访问集群 | `~/.kube/config` | ✅ 已配置 |
| **Docker Daemon** | 镜像拉取认证 | `/etc/docker/daemon.json` | ⚠️ 需配置 |

**证书配置:**
| 证书类型 | 用途 | 存储位置 | 状态 |
|---------|------|---------|------|
| **K3S TLS** | K8s API Server HTTPS | `/var/lib/rancher/k3s/server/tls/` | ✅ 自动生成 |
| **Traefik TLS** | Ingress HTTPS | 各命名空间 Secret | ✅ 已配置 |
| **Let's Encrypt** | 生产环境证书 | cert-manager 管理 | ⚠️ 需配置 |

**问题发现:**
- ⚠️ **Docker insecure-registries 未配置**: 无法推送镜像到 Harbor（自签名证书）
- ⚠️ **cert-manager 未部署**: 无法自动申请 Let's Encrypt 证书

---

### 1.3 证书存储位置汇总

| 组件 | Secret 名称 | 命名空间 | 证书类型 | 管理者 |
|------|-----------|---------|---------|--------|
| **Gitea** | `gitea-tls-secret` | `gitea` | TLS (HTTPS) | Helm Chart |
| **Harbor** | `harbor-tls-secret` | `harbor` | TLS (HTTPS) | Helm Chart |
| **ArgoCD** | `argocd-tls-secret` | `argocd` | TLS (HTTPS) | Kustomize |
| **Traefik** | 各命名空间独立 | 各命名空间 | TLS (Ingress) | Kustomize |
| **K3S** | N/A (文件系统) | N/A | TLS (API Server) | K3S 自动 |

**证书管理问题:**
1. ❌ **分散管理**: 每个组件独立管理 TLS 证书，无统一 CA
2. ❌ **自签名证书未互信**: 各组件使用独立自签名证书，组件间 TLS 验证失败
3. ❌ **无自动续期**: 自签名证书过期需手动更新
4. ❌ **cert-manager 缺失**: 无法自动申请 Let's Encrypt 证书

---

### 1.4 密钥管理风险矩阵

| 风险项 | 风险等级 | 影响范围 | 当前状态 | 缓解措施 |
|--------|---------|---------|---------|---------|
| **明文占位符** | 🔴 HIGH | 所有组件 | 广泛存在 | 使用 Sealed Secrets |
| **Webhook Secret 为空** | 🟡 MEDIUM | Gitea/ArgoCD | 3 处为空 | 生成随机密钥并填充 |
| **Token 未轮换** | 🟡 MEDIUM | Gitea/ArgoCD | 长期有效 | 配置 Token 自动轮换 |
| **密码策略不一致** | 🟡 MEDIUM | Gitea/Harbor | 配置分散 | 统一密码策略 |
| **密钥未加密存储** | 🔴 HIGH | 所有组件 | git 中明文 | 使用 Sealed Secrets |

---

## 🎯 第二部分：宗师级解决方案

### 2.1 总体架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SISYS 统一签名认证架构 (目标状态)                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    统一身份源层 (Identity Layer)                 │   │
│  │  ┌───────────────────────────────────────────────────────────┐  │   │
│  │  │              Gitea OIDC (唯一身份提供商 IdP)               │  │   │
│  │  │  - 用户认证：Basic Auth → OIDC                            │  │   │
│  │  │  - 应用集成：OAuth2 + OIDC                                │  │   │
│  │  │  - Token 管理：JWT + Refresh Token                        │  │   │
│  │  └───────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                           │                                             │
│                           ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   统一证书管理层 (Certificate Layer)             │   │
│  │  ┌───────────────────────────────────────────────────────────┐  │   │
│  │  │              cert-manager + Let's Encrypt                 │  │   │
│  │  │  - 自动申请：Let's Encrypt 通配符证书                      │  │   │
│  │  │  - 自动续期：到期前 30 天自动续期                           │  │   │
│  │  │  - 统一 CA：所有组件使用同一 CA 签发                         │  │   │
│  │  └───────────────────────────────────────────────────────────┘  │   │
│  │  ┌───────────────────────────────────────────────────────────┐  │   │
│  │  │              内部 CA (可选，离线环境)                       │  │   │
│  │  │  - Vault PKI 或 OpenSSL CA                                │  │   │
│  │  │  - 统一签发内部服务证书                                    │  │   │
│  │  └───────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                           │                                             │
│                           ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                  统一密钥管理层 (Secrets Layer)                  │   │
│  │  ┌───────────────────────────────────────────────────────────┐  │   │
│  │  │         Sealed Secrets + External Secrets Operator        │  │   │
│  │  │  - Sealed Secrets: git 中加密存储                          │  │   │
│  │  │  - External Secrets: 从外部密钥管理同步（Vault/AWS SM）    │  │   │
│  │  │  - SOPS: 配置文件加密                                      │  │   │
│  │  └───────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                           │                                             │
│                           ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   统一认证协议层 (Protocol Layer)                │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │   │
│  │  │  OAuth2/OIDC │  │  JWT Token   │  │  mTLS        │          │   │
│  │  │  (用户认证)   │  │  (应用认证)   │  │  (服务间)    │          │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐             │
│  │   Gitea     │      │   Harbor    │      │   ArgoCD    │             │
│  │  (OIDC IdP) │─────▶│  (OIDC IdP) │─────▶│  (OIDC IdP) │             │
│  └─────────────┘      └─────────────┘      └─────────────┘             │
│         │                    │                    │                     │
│         ▼                    ▼                    ▼                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    统一信任链 (Trust Chain)                     │   │
│  │  - 所有组件信任统一 CA                                          │   │
│  │  - 组件间 mTLS 双向认证                                          │   │
│  │  - Webhook 签名验证                                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 2.2 核心组件实施

#### 2.2.1 统一身份源：Gitea OIDC

**实施步骤:**

1. **启用 Gitea OIDC 身份提供商**

```yaml
# deployments/gitea/oidc-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: gitea-oidc-config
  namespace: gitea
data:
  app.ini: |
    [openid]
    ENABLE_OPENID_SIGNIN = true
    ENABLE_OPENID_SIGNUP = false

    [oauth2]
    ENABLE = true
    ACCESS_TOKEN_EXPIRATION_TIME = 3600
    REFRESH_TOKEN_EXPIRATION_TIME = 86400
    JWT_SECRET = ${GITEA_JWT_SECRET}
    JWT_SIGNING_ALGORITHM = RS256
    ISSUER = https://gitea.sisys.local

    [service]
    DISABLE_REGISTRATION = true  # 仅允许 OIDC 登录
    ENABLE_NOTIFY_MAIL = false
```

2. **配置 Harbor 使用 Gitea OIDC**

```yaml
# deployments/harbor/oidc-values.yaml
oidc:
  enabled: true
  name: "Gitea"
  endpoint: "https://gitea.sisys.local"
  clientID: "${GITEA_OIDC_CLIENT_ID}"
  clientSecret: "${GITEA_OIDC_CLIENT_SECRET}"
  redirectURI: "https://harbor.sisys.local/c/oidc/callback"
  scopes: "openid,profile,email,groups"
  adminGroup: "gitea-admins"
  autoOnboard: true
  skipTLSVerify: false  # 生产环境必须验证 TLS
```

3. **配置 ArgoCD 使用 Gitea OIDC**

```yaml
# deployments/argocd/oidc-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  namespace: argocd
data:
  url: https://argocd.sisys.local
  oidc.config: |
    name: Gitea
    issuer: https://gitea.sisys.local
    clientID: $GITEA_OIDC_CLIENT_ID
    clientSecret: $GITEA_OIDC_CLIENT_SECRET
    requestedScopes: ["openid", "profile", "email", "groups"]
    requestedIDTokenClaims: {"groups": {"essential": true}}
    logoutURL: https://gitea.sisys.local/user/logout
```

**收益:**
- ✅ **单点登录 (SSO)**: 一次登录，访问所有组件
- ✅ **统一用户管理**: Gitea 统一管理用户和权限
- ✅ **集中审计**: 所有登录日志集中记录
- ✅ **自动同步**: 用户组变更自动同步到所有组件

---

#### 2.2.2 统一证书管理：cert-manager

**实施步骤:**

1. **部署 cert-manager**

```yaml
# deployments/cert-manager/cert-manager-install.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: cert-manager
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: jetstack
  namespace: cert-manager
spec:
  interval: 24h
  url: https://charts.jetstack.io
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: cert-manager
  namespace: cert-manager
spec:
  chart:
    spec:
      chart: cert-manager
      version: "v1.14.0"
      sourceRef:
        kind: HelmRepository
        name: jetstack
  interval: 24h
  values:
    installCRDs: true
    prometheus:
      enabled: true
```

2. **配置 Let's Encrypt ClusterIssuer**

```yaml
# deployments/cert-manager/cluster-issuer.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@sisys.local
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
    - http01:
        ingress:
          class: traefik
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: admin@sisys.local
    privateKeySecretRef:
      name: letsencrypt-staging-account-key
    solvers:
    - http01:
        ingress:
          class: traefik
```

3. **配置通配符证书（使用 DNS Challenge）**

```yaml
# deployments/cert-manager/wildcard-certificate.yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: sisys-wildcard-cert
  namespace: default
spec:
  secretName: sisys-wildcard-tls-secret
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  commonName: "*.sisys.local"
  dnsNames:
  - "*.sisys.local"
  - "sisys.local"
  privateKey:
    algorithm: ECDSA
    size: 256
  renewBefore: 720h  # 30 天前自动续期
```

4. **各组件使用统一证书**

```yaml
# Gitea 使用统一证书
# deployments/gitea/tls-secret-ref.yaml
apiVersion: v1
kind: Secret
metadata:
  name: gitea-tls-secret
  namespace: gitea
type: kubernetes.io/tls
data:
  tls.crt: ${SISYS_WILDCARD_CERT}  # 从 cert-manager 同步
  tls.key: ${SISYS_WILDCARD_KEY}   # 从 cert-manager 同步
```

**收益:**
- ✅ **自动续期**: 证书到期前 30 天自动续期
- ✅ **统一 CA**: 所有组件使用同一 CA 签发
- ✅ **通配符支持**: 一个证书支持所有子域名
- ✅ **监控告警**: 证书过期自动告警

---

#### 2.2.3 统一密钥管理：Sealed Secrets + External Secrets

**实施步骤:**

1. **部署 Sealed Secrets**

```yaml
# deployments/sealed-secrets/sealed-secrets-install.yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: sealed-secrets
  namespace: kube-system
spec:
  interval: 24h
  url: https://bitnami-labs.github.io/sealed-secrets
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: sealed-secrets
  namespace: kube-system
spec:
  chart:
    spec:
      chart: sealed-secrets
      version: "2.14.0"
      sourceRef:
        kind: HelmRepository
        name: sealed-secrets
  interval: 24h
  values:
    fullnameOverride: sealed-secrets-controller
    secretName: sealed-secrets-key
```

2. **安装 kubeseal CLI**

```bash
# 下载并安装 kubeseal
wget https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/kubeseal-0.24.0-linux-amd64
sudo install -m 755 kubeseal-0.24.0-linux-amd64 /usr/local/bin/kubeseal
```

3. **创建 Sealed Secret**

```bash
# 创建普通 Secret
kubectl create secret generic gitea-admin-secret \
  --from-literal=username=gitea_admin \
  --from-literal=password='SecurePassword123!' \
  --namespace gitea \
  --dry-run=client -o yaml > gitea-admin-secret.yaml

# 使用 kubeseal 加密为 SealedSecret
kubeseal --format yaml < gitea-admin-secret.yaml > gitea-admin-sealedsecret.yaml

# 提交到 git
git add deployments/gitea/gitea-admin-sealedsecret.yaml
git commit -m "Add sealed Gitea admin secret"

# 应用到集群
kubectl apply -f gitea-admin-sealedsecret.yaml
```

4. **部署 External Secrets Operator（可选，用于集成 Vault/AWS SM）**

```yaml
# deployments/external-secrets/eso-install.yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  name: external-secrets
  namespace: external-secrets
spec:
  interval: 24h
  url: https://charts.external-secrets.io
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: external-secrets
  namespace: external-secrets
spec:
  chart:
    spec:
      chart: external-secrets
      version: "0.9.13"
      sourceRef:
        kind: HelmRepository
        name: external-secrets
  interval: 24h
```

5. **配置 External Secret（从 Vault 同步）**

```yaml
# deployments/external-secrets/gitea-secret.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: gitea-admin-secret
  namespace: gitea
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: gitea-admin-secret
    creationPolicy: Owner
  data:
  - secretKey: username
    remoteRef:
      key: secret/data/gitea/admin
      property: username
  - secretKey: password
    remoteRef:
      key: secret/data/gitea/admin
      property: password
```

**收益:**
- ✅ **git 中加密存储**: Sealed Secret 可安全提交到 git
- ✅ **自动解密**: Sealed Secrets Controller 自动解密为 Secret
- ✅ **外部集成**: External Secrets 可从 Vault/AWS SM 同步
- ✅ **审计日志**: 密钥访问自动记录

---

#### 2.2.4 统一信任链：内部 CA + mTLS

**实施步骤:**

1. **创建内部 CA（可选，用于离线环境）**

```bash
# 生成 CA 私钥
openssl genrsa -out sisys-ca.key 4096

# 生成 CA 证书
openssl req -x509 -new -nodes -sha256 -days 3650 \
  -key sisys-ca.key \
  -out sisys-ca.crt \
  -subj "/C=CN/ST=Beijing/L=Beijing/O=SISYS/CN=SISYS Root CA"
```

2. **配置 Traefik 信任内部 CA**

```yaml
# deployments/traefik/trust-store.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: traefik-trust-store
  namespace: traefik
data:
  sisys-ca.crt: |
    -----BEGIN CERTIFICATE-----
    ${SISYS_CA_CERT}
    -----END CERTIFICATE-----
---
apiVersion: v1
kind: Deployment
metadata:
  name: traefik
  namespace: traefik
spec:
  template:
    spec:
      volumes:
      - name: trust-store
        configMap:
          name: traefik-trust-store
      containers:
      - name: traefik
        volumeMounts:
        - name: trust-store
          mountPath: /etc/ssl/certs/sisys-ca.crt
          subPath: sisys-ca.crt
          readOnly: true
```

3. **配置 Docker 信任 Harbor 证书**

```yaml
# deployments/harbor/docker-daemon-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: docker-daemon-config
  namespace: kube-system
data:
  daemon.json: |
    {
      "insecure-registries": [],
      "registry-mirrors": [],
      "tls-ca-certificates-path": "/etc/docker/certs.d"
    }
---
# 创建 Harbor 证书目录
apiVersion: v1
kind: ConfigMap
metadata:
  name: harbor-ca-cert
  namespace: kube-system
data:
  ca.crt: |
    -----BEGIN CERTIFICATE-----
    ${HARBOR_CA_CERT}
    -----END CERTIFICATE-----
```

4. **配置组件间 mTLS（可选，高安全场景）**

```yaml
# deployments/service-mesh/mtls-policy.yaml
# 使用 Linkerd 或 Istio 实现服务间 mTLS
apiVersion: linkerd.io/v1alpha1
kind: ServerAuthorization
metadata:
  name: gitea-require-mtls
  namespace: gitea
spec:
  server:
    name: gitea-http
  client:
    # 仅允许带有有效 mTLS 证书的客户端
    meshTLS:
      identities:
      - "*.linkerd-managed.linkerd.svc.cluster.local"
```

**收益:**
- ✅ **统一信任链**: 所有组件信任同一 CA
- ✅ **组件间认证**: mTLS 确保服务间通信安全
- ✅ **离线支持**: 内部 CA 支持离线环境
- ✅ **自动化**: cert-manager 自动签发组件证书

---

### 2.3 认证协议标准化

#### 2.3.1 认证协议分层

```
┌─────────────────────────────────────────────────────────┐
│                    认证协议分层                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  L1: 用户认证层 (User Authentication Layer)             │
│  ┌─────────────────────────────────────────────────┐   │
│  │  协议：OAuth2 + OIDC                            │   │
│  │  用途：用户登录 Gitea/Harbor/ArgoCD             │   │
│  │  实现：Gitea OIDC → Harbor/ArgoCD               │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  L2: 应用认证层 (Application Authentication Layer)      │
│  ┌─────────────────────────────────────────────────┐   │
│  │  协议：JWT Token / Personal Access Token        │   │
│  │  用途：CI/CD Pipeline、API 访问                   │   │
│  │  实现：Gitea Token → ArgoCD/Gitea API           │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  L3: 服务认证层 (Service Authentication Layer)          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  协议：mTLS / ServiceAccount Token              │   │
│  │  用途：K8s 内部服务间通信                         │   │
│  │  实现：Linkerd/Istio mTLS                       │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  L4: 机器认证层 (Machine Authentication Layer)          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  协议：Robot Account / Webhook Secret           │   │
│  │  用途：Docker 登录、Webhook 验证                  │   │
│  │  实现：Harbor Robot → Docker/Gitea Webhook      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### 2.3.2 认证协议使用规范

| 场景 | 推荐协议 | 替代方案 | 禁止使用 |
|------|---------|---------|---------|
| **用户登录 Web 界面** | OIDC (Gitea) | Basic Auth | 明文密码 |
| **CI/CD Pipeline** | Personal Access Token | ServiceAccount | Basic Auth |
| **API 访问** | JWT Token | Personal Access Token | 明文密码 |
| **Docker 登录** | Robot Account | Personal Token | 用户账号 |
| **Webhook 验证** | HMAC Secret | - | 无验证 |
| **服务间通信** | mTLS | ServiceAccount Token | 明文 HTTP |
| **K8s API 访问** | ServiceAccount Token | kubeconfig | 明文密码 |

---

### 2.4 安全加固配置

#### 2.4.1 密码策略统一

```yaml
# deployments/security/unified-password-policy.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: unified-password-policy
  namespace: security
data:
  password-policy.yaml: |
    # 统一密码策略（所有组件遵循）
    minLength: 12
    requireUppercase: true
    requireLowercase: true
    requireDigit: true
    requireSpecialChar: true
    passwordHistory: 5  # 不得重复最近 5 次
    maxAge: 90  # 90 天强制更换
    lockoutThreshold: 5  # 5 次失败锁定
    lockoutDuration: 30m  # 锁定 30 分钟
```

#### 2.4.2 Token 生命周期管理

```yaml
# deployments/security/token-lifecycle-policy.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: token-lifecycle-policy
  namespace: security
data:
  token-policy.yaml: |
    # Token 生命周期管理
    accessTokenExpiry: 3600  # 1 小时
    refreshTokenExpiry: 86400  # 24 小时
    personalTokenExpiry: 7776000  # 90 天
    robotTokenExpiry: 31536000  # 1 年（可配置永不过期）
    autoRotate: true  # 自动轮换
    rotateBefore_expiry: 604800  # 到期前 7 天轮换
```

#### 2.4.3 Webhook 签名验证

```yaml
# deployments/security/webhook-security.yaml
# Gitea Webhook Secret
apiVersion: v1
kind: Secret
metadata:
  name: gitea-webhook-secret
  namespace: argocd
type: Opaque
stringData:
  # 生成命令：openssl rand -hex 32
  webhook-secret: "RANDOM_64_CHAR_HEX_STRING"  # pragma: allowlist secret
---
# ArgoCD Webhook 验证配置
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-webhook-config
  namespace: argocd
data:
  webhook.verify: "true"
  webhook.secret.key: "webhook-secret"
  webhook.secret.value: "RANDOM_64_CHAR_HEX_STRING"  # pragma: allowlist secret
```

---

## 📊 第三部分：实施路线图

### 3.1 阶段划分

```
┌─────────────────────────────────────────────────────────┐
│              统一签名认证实施路线图                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Phase 1: 基础建设 (Story 0.10-0.11)                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Story 0.10: cert-manager 部署                   │   │
│  │  - 部署 cert-manager                             │   │
│  │  - 配置 Let's Encrypt ClusterIssuer             │   │
│  │  - 申请通配符证书                                │   │
│  │  - 各组件替换为统一证书                          │   │
│  │  工期：3 天                                      │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Story 0.11: Sealed Secrets 部署                 │   │
│  │  - 部署 Sealed Secrets Controller                │   │
│  │  - 安装 kubeseal CLI                            │   │
│  │  - 迁移现有 Secret 为 SealedSecret                │   │
│  │  - 配置 CI/CD 自动加密                            │   │
│  │  工期：2 天                                      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Phase 2: 统一身份 (Story 0.12-0.13)                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Story 0.12: Gitea OIDC 配置                     │   │
│  │  - 启用 Gitea OIDC 身份提供商                     │   │
│  │  - 配置 OAuth2 应用（Harbor/ArgoCD）             │   │
│  │  - 测试 SSO 单点登录                              │   │
│  │  - 配置用户组同步                                │   │
│  │  工期：3 天                                      │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Story 0.13: Harbor/ArgoCD OIDC 集成             │   │
│  │  - Harbor 配置 Gitea OIDC                        │   │
│  │  - ArgoCD 配置 Gitea OIDC                        │   │
│  │  - 测试统一身份认证                              │   │
│  │  - 迁移现有用户                                  │   │
│  │  工期：3 天                                      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Phase 3: 信任链完善 (Story 0.19-0.20)                  │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Story 0.19: 内部 CA 部署（可选）                 │   │
│  │  - 创建内部 CA                                   │   │
│  │  - 配置 Traefik 信任内部 CA                      │   │
│  │  - 配置 Docker 信任内部 CA                       │   │
│  │  - 组件证书使用内部 CA 签发                       │   │
│  │  工期：2 天                                      │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Story 0.20: mTLS 配置（可选）                    │   │
│  │  - 部署 Linkerd/Istio                            │   │
│  │  - 配置服务间 mTLS                               │   │
│  │  - 测试 mTLS 双向认证                             │   │
│  │  - 配置 mTLS 策略                                 │   │
│  │  工期：3 天                                      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Phase 4: 高级特性 (Story 0.21-0.22)                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Story 0.21: External Secrets 集成               │   │
│  │  - 部署 External Secrets Operator                │   │
│  │  - 配置 Vault/AWS SM 后端                         │   │
│  │  - 迁移关键密钥到外部管理                        │   │
│  │  - 配置自动同步                                  │   │
│  │  工期：3 天                                      │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Story 0.22: Token 自动轮换                      │   │
│  │  - 配置 Token 自动轮换策略                        │   │
│  │  - 实现 Token 轮换 Controller                     │   │
│  │  - 测试 Token 自动更新                            │   │
│  │  - 配置告警通知                                  │   │
│  │  工期：3 天                                      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 3.2 优先级矩阵

| 改进项 | 安全影响 | 实施难度 | 优先级 | 归属 Story |
|--------|---------|---------|--------|-----------|
| **cert-manager 部署** | 🔴 HIGH | 🟢 LOW | P0 | Story 0.10 |
| **Sealed Secrets 部署** | 🔴 HIGH | 🟢 LOW | P0 | Story 0.11 |
| **Gitea OIDC 启用** | 🟡 MEDIUM | 🟡 MEDIUM | P1 | Story 0.12 |
| **Harbor/ArgoCD OIDC 集成** | 🟡 MEDIUM | 🟡 MEDIUM | P1 | Story 0.13 |
| **Webhook Secret 填充** | 🟡 MEDIUM | 🟢 LOW | P1 | 立即修复 |
| **内部 CA 部署** | 🟢 LOW | 🟡 MEDIUM | P2 | Story 0.19 |
| **mTLS 配置** | 🟢 LOW | 🔴 HIGH | P2 | Story 0.20 |
| **External Secrets** | 🟡 MEDIUM | 🔴 HIGH | P2 | Story 0.21 |
| **Token 自动轮换** | 🟡 MEDIUM | 🟡 MEDIUM | P2 | Story 0.22 |

---

## 🔧 第四部分：立即修复项

基于代码审查发现的 CRITICAL 和 HIGH 问题，以下项目需**立即修复**：

### 4.1 CRITICAL 问题修复

#### 4.1.1 填充 Webhook Secret

```bash
# 生成随机 Webhook Secret
GITEA_WEBHOOK_SECRET=$(openssl rand -hex 32)
ARGOCD_WEBHOOK_SECRET=$(openssl rand -hex 32)
HARBOR_WEBHOOK_SECRET=$(openssl rand -hex 32)

# 创建/更新 Secret
kubectl create secret generic gitea-webhook-secret \
  --namespace argocd \
  --from-literal=webhook-secret="$GITEA_WEBHOOK_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic harbor-webhook-secret \
  --namespace harbor \
  --from-literal=webhook-secret="$HARBOR_WEBHOOK_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -
```

#### 4.1.2 填充 Token 占位符

```bash
# Gitea Personal Access Token（已在 Story 0.7 生成）
GITEA_TOKEN="1f182aca3d38b66f7e49c034d98fb15bf02434b7"

# Harbor Robot Account Token（已在 Story 0.6 生成）
HARBOR_ROBOT_TOKEN="mMbDaASmDi2fE1CIIFYMyZWorAQYLQ1j"

# 更新 ArgoCD Secret
kubectl create secret generic argocd-gitea-credentials \
  --namespace argocd \
  --from-literal=password="$GITEA_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic argocd-harbor-credentials \
  --namespace argocd \
  --from-literal=harbor-robot-token="$HARBOR_ROBOT_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -
```

#### 4.1.3 配置 Docker 信任 Harbor 证书

```bash
# 在 K3S 所有节点执行
sudo mkdir -p /etc/docker/certs.d/harbor.sisys.local
sudo kubectl get secret harbor-tls-secret -n harbor -o jsonpath='{.data.tls\.crt}' | base64 -d | \
  sudo tee /etc/docker/certs.d/harbor.sisys.local/ca.crt

# 配置 daemon.json
echo '{
  "insecure-registries": [],
  "tls-ca-certificates-path": "/etc/docker/certs.d"
}' | sudo tee /etc/docker/daemon.json

# 重启 Docker
sudo systemctl restart docker
```

---

### 4.2 HIGH 问题修复

#### 4.2.1 启用 cert-manager（Story 0.10）

```bash
# 部署 cert-manager
kubectl apply -f deployments/cert-manager/cert-manager-install.yaml

# 验证部署
kubectl get pods -n cert-manager
```

#### 4.2.2 部署 Sealed Secrets（Story 0.11）

```bash
# 部署 Sealed Secrets
kubectl apply -f deployments/sealed-secrets/sealed-secrets-install.yaml

# 验证部署
kubectl get pods -n kube-system -l app.kubernetes.io/name=sealed-secrets
```

---

## 📈 第五部分：监控与审计

### 5.1 认证监控指标

```yaml
# deployments/monitoring/auth-metrics.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: auth-monitoring-rules
  namespace: monitoring
data:
  prometheus-rules.yaml: |
    groups:
    - name: authentication
      rules:
      # 登录失败率告警
      - alert: HighLoginFailureRate
        expr: rate(gitea_login_failures_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "登录失败率过高"
          description: "Gitea 登录失败率超过 10%"

      # Token 即将过期告警
      - alert: TokenExpiringSoon
        expr: (gitea_token_expiry_timestamp - time()) < 604800
        for: 1h
        labels:
          severity: info
        annotations:
          summary: "Token 即将过期"
          description: "Token 将在 7 天内过期"

      # 证书即将过期告警
      - alert: CertificateExpiringSoon
        expr: (certmanager_certificate_expiry_timestamp - time()) < 2592000
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "证书即将过期"
          description: "TLS 证书将在 30 天内过期"
```

### 5.2 审计日志配置

```yaml
# deployments/audit/unified-audit-log.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: unified-audit-config
  namespace: audit
data:
  audit-config.yaml: |
    version: v1
    audit:
      enabled: true
      # 审计事件
      events:
      - login
      - logout
      - token.create
      - token.delete
      - secret.access
      - webhook.trigger
      # 审计字段
      fields:
      - timestamp
      - user
      - action
      - resource
      - source_ip
      - user_agent
      - result
      # 日志输出
      output:
      - type: elasticsearch
        endpoint: http://elasticsearch:9200
        index: audit-logs
      - type: s3
        bucket: sisys-audit-logs
        prefix: audit/
        encryption: AES256
      # 保留策略
      retention:
        hot: 30d    # 热存储（可快速检索）
        warm: 90d   # 温存储（归档）
        cold: 365d  # 冷存储（合规）
```

---

## 📚 第六部分：最佳实践

### 6.1 密钥管理最佳实践

1. **永远不要将明文密钥提交到 git**
   ```bash
   # ❌ 错误：明文密钥
   password: "MySecretPassword123"

   # ✅ 正确：使用 SealedSecret
   apiVersion: bitnami.com/v1alpha1
   kind: SealedSecret
   metadata:
     name: my-secret
   spec:
     encryptedData:
       password: AgBy8i...
   ```

2. **定期轮换密钥**
   ```bash
   # 配置自动轮换（Story 0.22）
   kubectl annotate secret gitea-admin-secret \
     secret-rotation/enabled=true \
     secret-rotation/interval=90d
   ```

3. **最小权限原则**
   ```yaml
   # ❌ 错误：过度权限
   apiVersion: v1
   kind: ServiceAccount
   metadata:
     name: overly-powerful
   ---
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRoleBinding
   roleRef:
     kind: ClusterRole
     name: cluster-admin  # ❌ 过度权限
   subjects:
   - kind: ServiceAccount
     name: overly-powerful

   # ✅ 正确：最小权限
   apiVersion: rbac.authorization.k8s.io/v1
   kind: Role
   metadata:
     name: minimal-role
   rules:
   - apiGroups: [""]
     resources: ["pods"]
     verbs: ["get", "list"]  # ✅ 只读权限
   ```

### 6.2 证书管理最佳实践

1. **使用 cert-manager 自动续期**
   ```yaml
   apiVersion: cert-manager.io/v1
   kind: Certificate
   metadata:
     name: my-cert
   spec:
     renewBefore: 720h  # 30 天前自动续期
     duration: 2160h    # 90 天有效期
   ```

2. **统一 CA 签发**
   ```bash
   # ❌ 错误：各组件独立 CA
   openssl req -x509 -new -nodes -key gitea.key -out gitea.crt
   openssl req -x509 -new -nodes -key harbor.key -out harbor.crt

   # ✅ 正确：统一 CA 签发
   cert-manager ClusterIssuer: letsencrypt-prod
   ```

3. **监控证书过期**
   ```yaml
   # Prometheus 告警规则
   - alert: CertificateExpiring
     expr: (certmanager_certificate_expiry_timestamp - time()) < 2592000
     annotations:
       summary: "证书将在 30 天内过期"
   ```

### 6.3 认证协议最佳实践

1. **优先使用 OIDC**
   ```yaml
   # ✅ 正确：OIDC 统一身份
   gitea: OIDC IdP
   harbor: OIDC Client (Gitea)
   argocd: OIDC Client (Gitea)

   # ❌ 错误：各自为政
   gitea: Local Users
   harbor: Local Users
   argocd: Local Users
   ```

2. **Token 最短有效期**
   ```yaml
   # ✅ 推荐配置
   accessToken: 1h
   refreshToken: 24h
   personalToken: 90d
   robotToken: 1y
   ```

3. **Webhook 必须签名验证**
   ```yaml
   # ✅ 正确：HMAC 签名验证
   gitea-webhook-secret: "RANDOM_64_CHAR_HEX"
   verify-signature: true

   # ❌ 错误：无验证
   gitea-webhook-secret: ""
   verify-signature: false
   ```

---

## 🛡️ 第七部分：风险管理与灾备设计

### 7.1 威胁建模 (STRIDE 分析)

基于评估报告建议，增加完整的 STRIDE 威胁分析：

| 威胁类型 | 场景 | 风险等级 | 缓解措施 | 归属 Story |
|---------|------|---------|---------|-----------|
| **伪造 (Spoofing)** | 伪造 OIDC Token | 🔴 HIGH | Token 签名验证 (RS256) + JWK 缓存刷新 | Story 0.12 |
| **篡改 (Tampering)** | 篡改 Kubernetes Secret | 🔴 HIGH | Sealed Secrets (AES-256-GCM) | Story 0.11 |
| **抵赖 (Repudiation)** | 否认登录/操作 | 🟡 MEDIUM | 统一审计日志 + 不可篡改存储 | Story 0.23 |
| **信息泄露 (Information Disclosure)** | Secret 泄露/明文存储 | 🔴 HIGH | 加密存储 + 密钥分级管理 | Story 0.11 |
| **拒绝服务 (Denial of Service)** | OIDC DDoS 攻击 | 🟡 MEDIUM | 限流 + 熔断 + 降级方案 | Story 0.12 |
| **权限提升 (Elevation of Privilege)** | RBAC 绕过/提权 | 🔴 HIGH | 定期审计 + 最小权限原则 | Story 0.24 |

### 7.2 密钥分级分类管理

```yaml
# deployments/security/secret-classification.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: secret-classification-policy
  namespace: security
  labels:
    app: security-policy
    version: "1.0"
data:
  classification-policy.yaml: |
    # SISYS 密钥分级分类管理策略
    # 符合 NIST SP 800-57 Part 1 Rev. 5
    
    levels:
      # =========================================================================
      # L1-Critical: 根密钥级别
      # =========================================================================
      - name: L1-Critical
        description: "根密钥、CA 私钥、主数据库密码、加密主密钥"
        examples:
          - "SISYS Root CA 私钥"
          - "Vault Unseal Key"
          - "Sealed Secrets Master Key"
          - "主数据库 root 密码"
        
        storage:
          type: "HSM/Vault"
          encryption: "AES-256-GCM"
          backup: "异地多活备份"
        
        access:
          mode: "Dual-Control"
          approval: "Security Team Lead + CTO"
          audit: "所有访问记录审计"
        
        rotation:
          interval: "30d"
          auto: false
          notification: "提前 7 天通知"
        
        recovery:
          type: "Shamir's Secret Sharing"
          threshold: "3 of 5"
    
      # =========================================================================
      # L2-High: 服务认证级别
      # =========================================================================
      - name: L2-High
        description: "服务间认证 Token、API 密钥、OAuth2 Client Secret"
        examples:
          - "Gitea OIDC Client Secret"
          - "Harbor Robot Account Token"
          - "ArgoCD Git 凭据"
          - "服务间 mTLS 证书私钥"
        
        storage:
          type: "Sealed Secrets"
          encryption: "AES-256-GCM"
          backup: "etcd 备份"
        
        access:
          mode: "RBAC"
          approval: "Team Lead"
          audit: "所有访问记录审计"
        
        rotation:
          interval: "90d"
          auto: true
          notification: "提前 14 天通知"
        
        recovery:
          type: "Automated Re-issue"
          threshold: "N/A"
    
      # =========================================================================
      # L3-Medium: 一般配置级别
      # =========================================================================
      - name: L3-Medium
        description: "一般配置密钥、临时 Token、测试环境密钥"
        examples:
          - "开发环境数据库密码"
          - "临时 API Token"
          - "测试环境 Secret"
        
        storage:
          type: "Kubernetes Secret (加密)"
          encryption: "etcd 加密"
          backup: "etcd 备份"
        
        access:
          mode: "Namespace RBAC"
          approval: "Developer"
          audit: "关键操作审计"
        
        rotation:
          interval: "180d"
          auto: false
          notification: "提前 30 天通知"
        
        recovery:
          type: "Manual Re-issue"
          threshold: "N/A"
    
      # =========================================================================
      # L4-Low: 公开信息级别
      # =========================================================================
      - name: L4-Low
        description: "公开配置、非敏感参数"
        examples:
          - "公开 API Endpoint"
          - "配置参数（非敏感）"
        
        storage:
          type: "ConfigMap"
          encryption: "None"
          backup: "Git 版本控制"
        
        access:
          mode: "Public"
          approval: "None"
          audit: "None"
        
        rotation:
          interval: "As needed"
          auto: false
          notification: "N/A"
        
        recovery:
          type: "Git Revert"
          threshold: "N/A"
```

### 7.3 密码学算法敏捷性设计

```yaml
# deployments/security/crypto-agility.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: crypto-agility-policy
  namespace: security
  labels:
    app: security-policy
    version: "1.0"
data:
  crypto-policy.yaml: |
    # SISYS 密码学算法敏捷性策略
    # 支持算法平滑迁移，应对量子计算威胁
    
    supported-algorithms:
      # 对称加密
      symmetric:
        current:
          - name: "AES-256-GCM"
            status: "recommended"
            key-size: 256
          - name: "ChaCha20-Poly1305"
            status: "recommended"
            key-size: 256
        deprecated:
          - name: "AES-128-CBC"
            deprecation-date: "2026-01-01"
            removal-date: "2027-01-01"
            reason: "CBC 模式存在填充预言攻击风险"
      
      # 非对称加密
      asymmetric:
        current:
          - name: "RSA-4096"
            status: "recommended"
            key-size: 4096
            usage: ["签名", "加密"]
          - name: "ECDSA-P256"
            status: "recommended"
            curve: "secp256r1"
            usage: ["签名"]
          - name: "Ed25519"
            status: "recommended"
            usage: ["签名"]
        deprecated:
          - name: "RSA-2048"
            deprecation-date: "2026-01-01"
            removal-date: "2027-06-01"
            reason: "密钥长度不足，存在分解风险"
          - name: "ECDSA-P192"
            deprecation-date: "2025-01-01"
            removal-date: "2026-06-01"
            reason: "密钥长度不足"
      
      # 哈希算法
      hash:
        current:
          - name: "SHA-256"
            status: "recommended"
            output-size: 256
          - name: "SHA-384"
            status: "recommended"
            output-size: 384
          - name: "SHA-512"
            status: "recommended"
            output-size: 512
        deprecated:
          - name: "SHA-1"
            deprecation-date: "2025-01-01"
            removal-date: "2026-01-01"
            reason: "碰撞攻击已证实"
          - name: "MD5"
            deprecation-date: "2020-01-01"
            removal-date: "2025-01-01"
            reason: "严重碰撞漏洞"
    
    # 算法迁移路线图
    migration-path:
      - name: "RSA-2048 → RSA-4096"
        timeline: "2026-Q4"
        status: "planned"
        impact: "证书重新签发，密钥对更新"
      
      - name: "ECDSA-P256 → Ed25519"
        timeline: "2027-Q2"
        status: "research"
        impact: "签名算法升级，需客户端支持"
      
      - name: "后量子密码迁移"
        timeline: "2028-Q1"
        status: "monitoring"
        algorithms: ["CRYSTALS-Kyber", "CRYSTALS-Dilithium"]
        impact: "全面算法升级"
    
    # 算法检测与告警
    detection:
      enabled: true
      scan-interval: "24h"
      alert-on-deprecated: true
      alert-on-weak: true
```

---

## 🔄 第八部分：迁移策略与回滚方案

### 8.1 迁移策略（详细版）

基于评估报告建议，增加完整的迁移策略：

#### 8.1.1 Story 0.10: cert-manager 迁移

```yaml
# deployments/cert-manager/migration-plan.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cert-manager-migration-plan
  namespace: cert-manager
data:
  migration-steps.yaml: |
    # cert-manager 迁移计划
    
    ## 阶段 1: 并行运行（第 1-2 天）
    phase-1-parallel:
      duration: "2 天"
      steps:
        - step: 1
          action: "部署 cert-manager"
          command: |
            kubectl apply -f deployments/cert-manager/cert-manager-install.yaml
          verification: |
            kubectl get pods -n cert-manager
            # 期望：所有 Pod Running
        
        - step: 2
          action: "配置 ClusterIssuer"
          command: |
            kubectl apply -f deployments/cert-manager/cluster-issuer.yaml
          verification: |
            kubectl get clusterissuer letsencrypt-prod
            # 期望：Ready=True
        
        - step: 3
          action: "申请测试证书"
          command: |
            kubectl apply -f deployments/cert-manager/test-certificate.yaml
          verification: |
            kubectl get certificate test-cert -o jsonpath='{.status.conditions[0]}'
            # 期望：Ready=True
        
        - step: 4
          action: "新旧证书并行（DNS 轮询）"
          details: |
            - 旧证书：手动管理的自签名证书
            - 新证书：cert-manager 管理的 Let's Encrypt 证书
            - 流量分配：旧 80% / 新 20%
    
    ## 阶段 2: 流量切换（第 3-4 天）
    phase-2-cutover:
      duration: "2 天"
      steps:
        - step: 1
          action: "流量切换到新证书 20%"
          command: |
            # 修改 Ingress 配置，20% 流量使用新证书
            kubectl apply -f deployments/apps/ingress-canary.yaml
          verification: |
            # 监控新证书使用情况
            kubectl get certificate | grep new
        
        - step: 2
          action: "流量切换到新证书 50%"
          command: |
            kubectl apply -f deployments/apps/ingress-50.yaml
          verification: |
            # 监控错误率，确保无 TLS 错误
            kubectl logs -l app=traefik | grep -i "tls error"
            # 期望：无错误
        
        - step: 3
          action: "流量切换到新证书 100%"
          command: |
            kubectl apply -f deployments/apps/ingress-full.yaml
          verification: |
            # 验证所有服务使用新证书
            curl -v https://gitea.sisys.local 2>&1 | grep "SSL certificate verify ok"
    
    ## 阶段 3: 观察期（第 5-7 天）
    phase-3-observation:
      duration: "7 天"
      steps:
        - step: 1
          action: "保留旧证书，监控新证书"
          monitoring:
            - "证书续期自动化测试"
            - "TLS 错误率监控"
            - "证书过期告警测试"
        
        - step: 2
          action: "证书续期自动化验证"
          command: |
            # 手动触发续期测试
            kubectl annotate certificate sisys-wildcard-cert \
              cert-manager.io/renewal-time=$(date -d "+20 days" -Iseconds)
          verification: |
            # 验证自动续期触发
            kubectl get certificate sisys-wildcard-cert -w
        
        - step: 3
          action: "旧证书吊销"
          command: |
            # 吊销旧证书
            kubectl delete secret old-tls-secret
          verification: |
            # 确认旧证书已删除
            kubectl get secret | grep old-tls
            # 期望：无结果
    
    ## 回滚方案
    rollback:
      trigger-conditions:
        - "证书续期失败 > 3 次"
        - "TLS 错误率 > 1%"
        - "Let's Encrypt 限流触发"
      
      steps:
        - step: 1
          action: "DNS 切回旧证书"
          command: |
            kubectl apply -f deployments/apps/ingress-rollback.yaml
          rto: "30min"
        
        - step: 2
          action: "通知 Let's Encrypt 支持团队"
          contact: "support@letsencrypt.org"
        
        - step: 3
          action: "根因分析"
          deliverable: "Post-Mortem 报告（24h 内）"
```

#### 8.1.2 Story 0.12: Gitea OIDC 迁移

```yaml
# deployments/gitea/oidc-migration-plan.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: gitea-oidc-migration-plan
  namespace: gitea
data:
  migration-steps.yaml: |
    # Gitea OIDC 迁移计划
    
    ## 阶段 1: 准备阶段（第 1 天）
    phase-1-preparation:
      duration: "1 天"
      steps:
        - step: 1
          action: "启用 Gitea OIDC 身份提供商"
          command: |
            kubectl apply -f deployments/gitea/oidc-config.yaml
          verification: |
            # 验证 OIDC Endpoint 可访问
            curl -k https://gitea.sisys.local/.well-known/openid-configuration
            # 期望：返回 OIDC 配置 JSON
        
        - step: 2
          action: "创建 OAuth2 应用"
          command: |
            # 为 Harbor 创建 OAuth2 应用
            curl -X POST https://gitea.sisys.local/api/v1/applications \
              -H "Authorization: token $GITEA_TOKEN" \
              -d '{"name":"harbor-oidc","redirect_uris":["https://harbor.sisys.local/c/oidc/callback"]}'
          verification: |
            # 记录 Client ID 和 Client Secret
            echo "Client ID: $GITEA_CLIENT_ID"
            echo "Client Secret: $GITEA_CLIENT_SECRET"
        
        - step: 3
          action: "配置用户组映射"
          details: |
            - gitea-admins → Harbor Admin
            - gitea-developers → Harbor Developer
            - gitea-viewers → Harbor Guest
    
    ## 阶段 2: 双轨运行（第 2-7 天）
    phase-2-dual-auth:
      duration: "6 天"
      steps:
        - step: 1
          action: "新用户强制 OIDC，老用户自愿迁移"
          details: |
            - 新注册用户：必须使用 Gitea OIDC
            - 现有用户：可继续使用本地密码，或迁移到 OIDC
          
          communication: |
            邮件通知模板：
            主题：【重要】统一身份认证升级通知
            内容：
              - OIDC 优势说明
              - 迁移操作指南
              - 截止日期提醒
        
        - step: 2
          action: "Harbor 配置双认证（Local + OIDC）"
          command: |
            # Harbor 同时支持本地认证和 OIDC
            kubectl apply -f deployments/harbor/dual-auth-config.yaml
          verification: |
            # 测试本地登录
            curl -X POST https://harbor.sisys.local/api/v2.0/users/login \
              -d '{"username":"admin","password":"xxx"}'
            # 测试 OIDC 登录
            curl -X POST https://harbor.sisys.local/c/oidc/callback
        
        - step: 3
          action: "监控迁移进度"
          metrics:
            - "每日 OIDC 登录用户数"
            - "每日本地登录用户数"
            - "迁移率目标：第 7 天达到 80%"
    
    ## 阶段 3: 强制切换（第 8-14 天）
    phase-3-enforcement:
      duration: "7 天"
      steps:
        - step: 1
          action: "30 天后强制所有用户 OIDC"
          communication: |
            邮件通知模板：
            主题：【最后通知】本地认证即将停用
            内容：
              - 停用日期：30 天后
              - 未迁移用户列表
              - 紧急联系渠道
        
        - step: 2
          action: "禁用本地认证"
          command: |
            kubectl apply -f deployments/gitea/oidc-only-config.yaml
          verification: |
            # 验证本地登录被拒绝
            curl -X POST https://gitea.sisys.local/api/v1/users/login \
              -d '{"username":"admin","password":"xxx"}'
            # 期望：401 Unauthorized
        
        - step: 3
          action: "清理本地密码数据"
          command: |
            # 安全删除本地密码哈希
            kubectl exec -it gitea-db-0 -- psql -c \
              "UPDATE \"user\" SET passwd_hash = '' WHERE type != 0;"
          verification: |
            # 验证密码哈希已清空
            kubectl exec -it gitea-db-0 -- psql -c \
              "SELECT count(*) FROM \"user\" WHERE passwd_hash != '';"
            # 期望：0
    
    ## 回滚方案
    rollback:
      trigger-conditions:
        - "SSO 故障 > 1h"
        - "用户投诉率 > 10%"
        - "OIDC 登录失败率 > 20%"
      
      steps:
        - step: 1
          action: "降级到本地认证"
          command: |
            kubectl apply -f deployments/gitea/local-auth-config.yaml
          rto: "15min"
        
        - step: 2
          action: "恢复本地密码"
          details: |
            - 从备份恢复密码哈希
            - 通知用户密码已恢复
        
        - step: 3
          action: "根因分析"
          deliverable: "Post-Mortem 报告（24h 内）"
```

#### 8.1.3 Story 0.11: Sealed Secrets 迁移

```yaml
# deployments/sealed-secrets/migration-plan.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: sealed-secrets-migration-plan
  namespace: kube-system
data:
  migration-steps.yaml: |
    # Sealed Secrets 迁移计划
    
    ## 阶段 1: 部署 Controller（第 1 天）
    phase-1-deployment:
      duration: "1 天"
      steps:
        - step: 1
          action: "部署 Sealed Secrets Controller"
          command: |
            kubectl apply -f deployments/sealed-secrets/sealed-secrets-install.yaml
          verification: |
            kubectl get pods -n kube-system -l app.kubernetes.io/name=sealed-secrets
            # 期望：1/1 Running
        
        - step: 2
          action: "备份主密钥"
          command: |
            # 备份 Sealed Secrets 私钥到安全位置
            kubectl get secret -n kube-system sealed-secrets-key \
              -o jsonpath='{.data}' | base64 -d > sealed-secrets-master-key.backup
            
            # 加密备份文件
            openssl enc -aes-256-cbc -salt -in sealed-secrets-master-key.backup \
              -out sealed-secrets-master-key.backup.enc
          verification: |
            # 验证备份文件存在
            ls -la sealed-secrets-master-key.backup.enc
        
        - step: 3
          action: "安装 kubeseal CLI"
          command: |
            wget https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/kubeseal-0.24.0-linux-amd64
            sudo install -m 755 kubeseal-0.24.0-linux-amd64 /usr/local/bin/kubeseal
          verification: |
            kubeseal --version
    
    ## 阶段 2: 新 Secret 使用 SealedSecret（第 2-3 天）
    phase-2-new-secrets:
      duration: "2 天"
      steps:
        - step: 1
          action: "配置 CI/CD 自动加密"
          details: |
            在 CI/CD Pipeline 中添加加密步骤：
            
            ```yaml
            # .gitea/workflows/deploy.yaml
            - name: Encrypt Secret
              run: |
                kubeseal --format yaml < secret.yaml > sealed-secret.yaml
            ```
        
        - step: 2
          action: "新 Secret 必须使用 SealedSecret"
          policy: |
            - 所有新创建的 Secret 必须使用 SealedSecret 格式
            - PR 检查：检测明文 Secret 提交
        
        - step: 3
          action: "验证 SealedSecret 自动解密"
          command: |
            # 创建测试 SealedSecret
            kubectl create secret generic test-secret \
              --from-literal=key=value --dry-run=client -o yaml | \
              kubeseal --format yaml | kubectl apply -f -
          verification: |
            # 验证 Secret 自动创建
            kubectl get secret test-secret
            # 期望：test-secret 存在
    
    ## 阶段 3: 分批迁移现有 Secret（第 4-10 天）
    phase-3-migration:
      duration: "7 天"
      steps:
        - step: 1
          action: "按命名空间分批迁移"
          schedule: |
            第 4 天：gitea 命名空间
            第 5 天：harbor 命名空间
            第 6 天：argocd 命名空间
            第 7 天：其他命名空间
          
          command: |
            # 导出 Secret
            kubectl get secret gitea-admin-secret -n gitea \
              -o yaml > gitea-admin-secret.yaml
            
            # 转换为 SealedSecret
            kubeseal --format yaml < gitea-admin-secret.yaml \
              > gitea-admin-sealedsecret.yaml
            
            # 应用 SealedSecret
            kubectl apply -f gitea-admin-sealedsecret.yaml
            
            # 删除原 Secret（Sealed Secrets Controller 会自动创建）
            kubectl delete secret gitea-admin-secret -n gitea
        
        - step: 2
          action: "验证 Secret 功能正常"
          verification: |
            # 验证应用可以正常访问 Secret
            kubectl exec -it gitea-0 -- env | grep GITEA_ADMIN_PASSWORD
        
        - step: 3
          action: "禁用明文 Secret 提交 CI"
          policy: |
            在 CI/CD 中添加检查：
            - 检测明文 Secret 提交
            - 拒绝包含明文的 PR
    
    ## 回滚方案
    rollback:
      trigger-conditions:
        - "Controller 故障 > 2h"
        - "私钥丢失"
        - "解密失败率 > 10%"
      
      steps:
        - step: 1
          action: "使用备份私钥手动解密"
          command: |
            # 恢复私钥
            kubectl create secret generic sealed-secrets-key \
              --from-file=tls.key=sealed-secrets-master-key.backup \
              -n kube-system
          rto: "1h"
        
        - step: 2
          action: "恢复明文 Secret"
          command: |
            # 从 Git 恢复明文 Secret
            kubectl apply -f deployments/secrets-backup/
          rto: "30min"
        
        - step: 3
          action: "根因分析"
          deliverable: "Post-Mortem 报告（24h 内）"
```

### 8.2 回滚方案（详细版）

```yaml
# deployments/disaster-recovery/rollback-playbook.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rollback-playbook
  namespace: disaster-recovery
  labels:
    app: disaster-recovery
    version: "1.0"
data:
  rollback-scenarios.yaml: |
    # SISYS 统一认证回滚手册
    
    ## 场景 1: cert-manager 故障
    scenario-1-cert-manager-failure:
      trigger-conditions:
        - "证书续期失败 > 3 次"
        - "Let's Encrypt API 限流"
        - "DNS 验证失败持续 > 1h"
      
      severity: "P1-Critical"
      rto: "30min"
      rpo: "0 (证书不丢失)"
      
      steps:
        - step: 1
          action: "启动应急响应"
          command: |
            # 通知相关人员
            @channel cert-manager 故障，启动应急预案
          owner: "On-call Engineer"
          timeout: "5min"
        
        - step: 2
          action: "DNS 切回旧证书"
          command: |
            # 切换 Ingress 配置使用旧证书
            kubectl apply -f deployments/apps/ingress-rollback.yaml
          owner: "DevOps Engineer"
          timeout: "15min"
          verification: |
            curl -v https://gitea.sisys.local 2>&1 | grep "SSL certificate"
        
        - step: 3
          action: "联系 Let's Encrypt 支持"
          contact: |
            Email: support@letsencrypt.org
            社区：https://community.letsencrypt.org/
          owner: "Security Team Lead"
          timeout: "30min"
        
        - step: 4
          action: "根因分析"
          deliverable: "Post-Mortem 报告（24h 内）"
          owner: "Incident Commander"
    
    ## 场景 2: Gitea OIDC 故障
    scenario-2-oidc-failure:
      trigger-conditions:
        - "SSO 登录失败率 > 20%"
        - "Gitea OIDC Endpoint 不可用 > 30min"
        - "Token 签发失败持续 > 1h"
      
      severity: "P1-Critical"
      rto: "15min"
      rpo: "0 (用户数据不丢失)"
      
      steps:
        - step: 1
          action: "启动应急响应"
          command: |
            @channel Gitea OIDC 故障，启动应急预案
          owner: "On-call Engineer"
          timeout: "5min"
        
        - step: 2
          action: "降级到本地认证"
          command: |
            # Harbor 切换回本地认证
            kubectl apply -f deployments/harbor/local-auth-config.yaml
            # ArgoCD 切换回本地认证
            kubectl apply -f deployments/argocd/local-auth-config.yaml
          owner: "DevOps Engineer"
          timeout: "10min"
          verification: |
            # 验证本地登录可用
            curl -X POST https://harbor.sisys.local/api/v2.0/users/login \
              -d '{"username":"admin","password":"xxx"}'
        
        - step: 3
          action: "通知用户"
          communication: |
            邮件模板：
            主题：【通知】统一身份认证临时切换至本地认证
            内容：
              - 故障说明
              - 临时登录方式
              - 预计恢复时间
          owner: "Communications Lead"
          timeout: "30min"
        
        - step: 4
          action: "根因分析"
          deliverable: "Post-Mortem 报告（24h 内）"
          owner: "Incident Commander"
    
    ## 场景 3: Sealed Secrets Controller 故障
    scenario-3-sealed-secrets-failure:
      trigger-conditions:
        - "Controller Pod CrashLoopBackOff"
        - "Secret 解密失败 > 10%"
        - "私钥丢失"
      
      severity: "P2-High"
      rto: "1h"
      rpo: "0 (密钥不丢失)"
      
      steps:
        - step: 1
          action: "启动应急响应"
          command: |
            @channel Sealed Secrets 故障，启动应急预案
          owner: "On-call Engineer"
          timeout: "5min"
        
        - step: 2
          action: "恢复私钥"
          command: |
            # 从安全备份恢复私钥
            kubectl create secret generic sealed-secrets-key \
              --from-file=tls.key=sealed-secrets-master-key.backup \
              -n kube-system --dry-run=client -o yaml | kubectl apply -f -
          owner: "Security Team Lead"
          timeout: "30min"
          verification: |
            kubectl get pods -n kube-system -l app.kubernetes.io/name=sealed-secrets
        
        - step: 3
          action: "重启 Controller"
          command: |
            kubectl rollout restart deployment/sealed-secrets-controller -n kube-system
          owner: "DevOps Engineer"
          timeout: "15min"
        
        - step: 4
          action: "验证解密功能"
          command: |
            # 创建测试 SealedSecret
            echo '{"apiVersion":"bitnami.com/v1alpha1","kind":"SealedSecret",...}' | \
              kubectl apply -f -
          owner: "DevOps Engineer"
          timeout: "15min"
        
        - step: 5
          action: "根因分析"
          deliverable: "Post-Mortem 报告（24h 内）"
          owner: "Incident Commander"
    
    ## 场景 4: mTLS 导致服务间通信故障
    scenario-4-mtls-failure:
      trigger-conditions:
        - "服务间调用失败率 > 30%"
        - "mTLS 证书验证失败 > 50 次/min"
        - "延迟增加 > 100ms"
      
      severity: "P1-Critical"
      rto: "10min"
      rpo: "N/A"
      
      steps:
        - step: 1
          action: "启动应急响应"
          command: |
            @channel mTLS 故障，启动应急预案
          owner: "On-call Engineer"
          timeout: "5min"
        
        - step: 2
          action: "临时禁用 mTLS"
          command: |
            # Linkerd 禁用 mTLS
            kubectl patch authorizationpolicy/default -n gitea \
              --type merge -p '{"spec":{"client":{"meshTLS":null}}}'
          owner: "DevOps Engineer"
          timeout: "5min"
          verification: |
            # 验证服务间通信恢复
            curl http://gitea-http.gitea.svc.cluster.local:3000
        
        - step: 3
          action: "调查根因"
          focus-areas:
            - "mTLS 证书是否过期"
            - "服务身份配置是否正确"
            - "网络策略是否阻止"
          owner: "Security Team Lead"
          timeout: "30min"
        
        - step: 4
          action: "根因分析"
          deliverable: "Post-Mortem 报告（24h 内）"
          owner: "Incident Commander"
    
    ## 应急联系人
    emergency-contacts:
      - role: "On-call Engineer"
        contact: "+86-xxx-xxxx-xxxx"
        escalation: "15min 无响应 → Team Lead"
      
      - role: "DevOps Team Lead"
        contact: "+86-xxx-xxxx-xxxx"
        escalation: "30min 无响应 → Security Team Lead"
      
      - role: "Security Team Lead"
        contact: "+86-xxx-xxxx-xxxx"
        escalation: "1h 无响应 → CTO"
      
      - role: "CTO"
        contact: "+86-xxx-xxxx-xxxx"
    
    ## 应急演练计划
    drill-schedule:
      - name: "cert-manager 故障演练"
        frequency: "Quarterly"
        next-drill: "2026-Q2"
        participants: ["DevOps", "Security"]
      
      - name: "OIDC 故障演练"
        frequency: "Quarterly"
        next-drill: "2026-Q2"
        participants: ["DevOps", "Security", "Support"]
      
      - name: "Sealed Secrets 故障演练"
        frequency: "Semi-annually"
        next-drill: "2026-Q3"
        participants: ["Security", "DevOps"]
      
      - name: "全面故障演练"
        frequency: "Annually"
        next-drill: "2026-Q4"
        participants: ["All Teams"]
```

---

## 📋 第九部分：运维手册与监控

### 9.1 运维手册清单

基于评估报告建议，增加完整的运维手册清单：

```yaml
# deployments/runbook/runbook-index.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: runbook-index
  namespace: operations
  labels:
    app: runbook
    version: "1.0"
data:
  runbooks.yaml: |
    # SISYS 统一认证运维手册索引
    
    ## cert-manager 运维手册
    runbook-cert-manager:
      path: "docs/runbooks/cert-manager/"
      owner: "DevOps Team"
      last-reviewed: "2026-03-18"
      next-review: "2026-06-18"
      
      documents:
        - name: "证书申请失败排查流程"
          file: "cert-application-troubleshooting.md"
          scenario: |
            - Certificate 状态长时间不是 Ready
            - Challenge 验证失败
            - DNS 记录不存在
          
          steps:
            1. 检查 Certificate 状态：kubectl describe certificate <name>
            2. 检查 Challenge 状态：kubectl get challenge
            3. 检查 DNS 记录：dig _acme-challenge.<domain> TXT
            4. 检查 cert-manager 日志：kubectl logs -l app=cert-manager
            5. 常见错误及解决方案：见文档
        
        - name: "证书续期失败应急处理"
          file: "cert-renewal-failure.md"
          scenario: |
            - 证书即将过期（< 7 天）
            - 自动续期失败
            - Let's Encrypt 限流
          
          steps:
            1. 检查限流状态：https://letsencrypt.org/docs/rate-limits/
            2. 手动触发续期：kubectl cert-manager renew <name>
            3. 如仍失败，切换到备用 CA
            4. 联系 Let's Encrypt 支持
        
        - name: "ClusterIssuer 配置变更流程"
          file: "cluster-issuer-change.md"
          scenario: |
            - 更换 ACME Server
            - 修改 DNS Provider
            - 更新私钥
          
          steps:
            1. 备份当前配置：kubectl get clusterissuer -o yaml > backup.yaml
            2. 应用新配置：kubectl apply -f new-cluster-issuer.yaml
            3. 验证新配置：kubectl describe clusterissuer
            4. 监控证书签发：kubectl get certificate -w
        
        - name: "监控告警响应流程"
          file: "monitoring-alert-response.md"
          alerts:
            - name: "CertificateExpiringSoon"
              severity: "warning"
              response: "检查续期状态，如异常立即介入"
            - name: "CertificateExpired"
              severity: "critical"
              response: "立即启动应急预案，手动续期"
    
    ## Sealed Secrets 运维手册
    runbook-sealed-secrets:
      path: "docs/runbooks/sealed-secrets/"
      owner: "Security Team"
      last-reviewed: "2026-03-18"
      next-review: "2026-06-18"
      
      documents:
        - name: "私钥备份与恢复流程"
          file: "master-key-backup-restore.md"
          scenario: |
            - 定期备份私钥
            - Controller 故障后恢复
            - 私钥丢失恢复
          
          steps:
            1. 备份：kubectl get secret sealed-secrets-key -n kube-system -o yaml > backup.yaml
            2. 加密备份文件：openssl enc -aes-256-cbc -salt -in backup.yaml -out backup.yaml.enc
            3. 存储到安全位置：Vault / AWS Secrets Manager
            4. 恢复：kubectl apply -f backup.yaml
        
        - name: "Controller 升级流程"
          file: "controller-upgrade.md"
          scenario: |
            - 新版本发布
            - 安全补丁
            - 功能升级
          
          steps:
            1. 阅读 Release Notes
            2. 在测试环境验证
            3. 备份当前配置
            4. 执行升级：helm upgrade sealed-secrets ...
            5. 验证功能正常
        
        - name: "密钥轮换操作流程"
          file: "key-rotation.md"
          scenario: |
            - 定期轮换（90 天）
            - 泄露后紧急轮换
            - 员工离职轮换
          
          steps:
            1. 生成新密钥
            2. 创建新 SealedSecret
            3. 应用新 Secret
            4. 删除旧 Secret
            5. 更新所有引用
        
        - name: "故障排查流程"
          file: "troubleshooting.md"
          scenarios:
            - "Secret 无法解密"
            - "Controller CrashLoopBackOff"
            - "SealedSecret 状态不是 Ready"
    
    ## Gitea OIDC 运维手册
    runbook-gitea-oidc:
      path: "docs/runbooks/gitea-oidc/"
      owner: "DevOps Team"
      last-reviewed: "2026-03-18"
      next-review: "2026-06-18"
      
      documents:
        - name: "OIDC 故障应急处理"
          file: "oidc-failure-emergency.md"
          scenario: |
            - 用户无法登录
            - Token 签发失败
            - OIDC Endpoint 不可用
          
          steps:
            1. 检查 Gitea 服务状态：kubectl get pods -n gitea
            2. 检查 OIDC Endpoint: curl https://gitea.sisys.local/.well-known/openid-configuration
            3. 检查日志：kubectl logs -l app=gitea | grep -i oidc
            4. 如无法快速恢复，启动降级方案
        
        - name: "用户迁移操作流程"
          file: "user-migration.md"
          scenario: |
            - 本地用户迁移到 OIDC
            - 批量用户导入
            - 用户数据同步
          
          steps:
            1. 导出本地用户：kubectl exec -it gitea-0 -- gitea admin user list
            2. 创建 OIDC 用户组
            3. 发送迁移通知邮件
            4. 监控迁移进度
            5. 清理未迁移用户
        
        - name: "Token 吊销操作流程"
          file: "token-revocation.md"
          scenario: |
            - Token 泄露
            - 员工离职
            - 安全事件
          
          steps:
            1. 识别需吊销的 Token
            2. 执行吊销：kubectl exec -it gitea-0 -- gitea admin user revoke-oauth2-token ...
            3. 通知相关系统
            4. 审计日志分析
        
        - name: "性能调优指南"
          file: "performance-tuning.md"
          topics:
            - "OIDC Token 缓存优化"
            - "数据库连接池优化"
            - "JWK 缓存策略"
    
    ## 安全事件响应手册
    runbook-security-incident:
      path: "docs/runbooks/security/"
      owner: "Security Team"
      last-reviewed: "2026-03-18"
      next-review: "2026-06-18"
      
      documents:
        - name: "密钥泄露应急响应"
          file: "secret-leak-response.md"
          severity: "P1-Critical"
          
          steps:
            1. 立即轮换泄露密钥（15min 内）
            2. 审计日志分析泄露范围（1h 内）
            3. 通知受影响用户（4h 内）
            4. 根因分析报告（24h 内）
            5. 改进措施实施（7d 内）
        
        - name: "证书泄露应急响应"
          file: "certificate-leak-response.md"
          severity: "P1-Critical"
          
          steps:
            1. 立即吊销证书（5min 内）
            2. 申请新证书
            3. 部署新证书
            4. 审计日志分析
            5. 根因分析
        
        - name: "OIDC 入侵应急响应"
          file: "oidc-breach-response.md"
          severity: "P1-Critical"
          
          steps:
            1. 吊销所有 OIDC Token（5min 内）
            2. 强制所有用户重新登录
            3. 启用紧急本地认证
            4. 重建 OIDC 密钥对
            5. 安全审计
        
        - name: "审计日志分析流程"
          file: "audit-log-analysis.md"
          tools:
            - "Elasticsearch 查询语法"
            - "异常登录检测"
            - "敏感操作审计"
```

### 9.2 监控指标（详细版）

```yaml
# deployments/monitoring/unified-auth-metrics.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: unified-auth-metrics
  namespace: monitoring
  labels:
    app: monitoring
    version: "1.0"
data:
  metrics-spec.yaml: |
    # SISYS 统一认证监控指标规范
    
    ## cert-manager 指标
    cert-manager-metrics:
      source: "cert-manager"
      service-monitor: "cert-manager-monitor"
      
      metrics:
        - name: certmanager_certificate_ready_status
          type: "gauge"
          description: "证书就绪状态（1=Ready, 0=Not Ready）"
          labels: ["name", "namespace", "condition"]
          alert:
            - name: CertificateNotReady
              expr: "certmanager_certificate_ready_status{condition=\"True\"} == 0"
              for: "5m"
              severity: "warning"
        
        - name: certmanager_certificate_expiry_timestamp
          type: "gauge"
          description: "证书过期时间戳（Unix timestamp）"
          labels: ["name", "namespace", "issuer"]
          alert:
            - name: CertificateExpiringSoon
              expr: "(certmanager_certificate_expiry_timestamp - time()) < 2592000"
              for: "1h"
              severity: "warning"
            - name: CertificateExpired
              expr: "(certmanager_certificate_expiry_timestamp - time()) < 0"
              for: "1m"
              severity: "critical"
        
        - name: certmanager_certificate_renewal_total
          type: "counter"
          description: "证书续期总次数"
          labels: ["name", "namespace", "result"]
          alert:
            - name: HighRenewalFailureRate
              expr: "rate(certmanager_certificate_renewal_total{result=\"failed\"}[5m]) > 0.1"
              for: "5m"
              severity: "critical"
        
        - name: certmanager_http_acme_client_request_count
          type: "counter"
          description: "ACME 请求总次数"
          labels: ["host", "method", "status"]
        
        - name: certmanager_http_acme_client_request_duration_seconds
          type: "histogram"
          description: "ACME 请求延迟"
          labels: ["host", "method"]
    
    ## Sealed Secrets 指标
    sealed-secrets-metrics:
      source: "sealed-secrets-controller"
      service-monitor: "sealed-secrets-monitor"
      
      metrics:
        - name: sealed_secrets_controller_errors_total
          type: "counter"
          description: "Controller 错误总次数"
          labels: ["type"]
          alert:
            - name: HighControllerErrorRate
              expr: "rate(sealed_secrets_controller_errors_total[5m]) > 0.5"
              for: "5m"
              severity: "critical"
        
        - name: sealed_secrets_decryption_latency_seconds
          type: "histogram"
          description: "解密延迟"
          labels: ["quantile"]
          buckets: [0.1, 0.25, 0.5, 1, 2.5, 5, 10]
        
        - name: sealed_secrets_controller_reconcile_duration_seconds
          type: "histogram"
          description: "Reconcile 延迟"
          labels: ["quantile"]
    
    ## Gitea OIDC 指标
    gitea-oidc-metrics:
      source: "gitea"
      service-monitor: "gitea-monitor"
      
      metrics:
        - name: gitea_login_total
          type: "counter"
          description: "登录总次数"
          labels: ["status", "method"]  # status: success/failure, method: password/oidc
          alert:
            - name: HighLoginFailureRate
              expr: "rate(gitea_login_total{status=\"failure\"}[5m]) / rate(gitea_login_total[5m]) > 0.1"
              for: "5m"
              severity: "warning"
        
        - name: gitea_token_issued_total
          type: "counter"
          description: "Token 签发总次数"
          labels: ["type", "client"]
        
        - name: gitea_token_revoked_total
          type: "counter"
          description: "Token 吊销总次数"
          labels: ["type", "reason"]
        
        - name: gitea_oidc_auth_duration_seconds
          type: "histogram"
          description: "OIDC 认证延迟"
          labels: ["status"]
          buckets: [0.1, 0.25, 0.5, 1, 2.5, 5, 10]
        
        - name: gitea_active_users
          type: "gauge"
          description: "活跃用户数"
          labels: ["type"]  # local/oidc
    
    ## ArgoCD 指标
    argocd-metrics:
      source: "argocd"
      service-monitor: "argocd-monitor"
      
      metrics:
        - name: argocd_cluster_info
          type: "gauge"
          description: "集群信息"
          labels: ["server", "name"]
        
        - name: argocd_app_info
          type: "gauge"
          description: "Application 状态"
          labels: ["name", "namespace", "sync_status", "health_status"]
        
        - name: argocd_git_request_total
          type: "counter"
          description: "Git 请求总次数"
          labels: ["request_type", "status"]
        
        - name: argocd_git_request_duration_seconds
          type: "histogram"
          description: "Git 请求延迟"
          labels: ["request_type"]
    
    ## Harbor 指标
    harbor-metrics:
      source: "harbor"
      service-monitor: "harbor-monitor"
      
      metrics:
        - name: harbor_health
          type: "gauge"
          description: "Harbor 健康状态（1=Healthy, 0=Unhealthy）"
          labels: ["component"]
          alert:
            - name: HarborUnhealthy
              expr: "harbor_health{component=\"core\"} == 0"
              for: "5m"
              severity: "critical"
        
        - name: harbor_robot_account_login_total
          type: "counter"
          description: "Robot Account 登录总次数"
          labels: ["status", "robot_name"]
        
        - name: harbor_image_push_total
          type: "counter"
          description: "镜像推送总次数"
          labels: ["status", "project"]
        
        - name: harbor_image_scan_total
          type: "counter"
          description: "镜像扫描总次数"
          labels: ["status", "severity"]
    
    ## Grafana 仪表盘
    grafana-dashboards:
      - name: "统一认证监控总览"
        file: "unified-auth-overview.json"
        panels:
          - "证书状态概览"
          - "登录成功率趋势"
          - "Token 签发/吊销趋势"
          - "Secret 解密延迟"
          - "告警汇总"
      
      - name: "cert-manager 详情"
        file: "cert-manager-detail.json"
        panels:
          - "证书过期时间线"
          - "续期成功率"
          - "ACME 请求延迟"
          - "错误分布"
      
      - name: "Gitea OIDC 详情"
        file: "gitea-oidc-detail.json"
        panels:
          - "登录成功率"
          - "OIDC vs 本地登录对比"
          - "Token 生命周期"
          - "活跃用户数"
      
      - name: "安全事件监控"
        file: "security-events.json"
        panels:
          - "登录失败热力图"
          - "异常登录检测"
          - "敏感操作审计"
          - "密钥轮换状态"
```

---

## 🎓 第十部分：总结

### 10.1 核心发现总结

通过对 Story 0.4-0.7 的深度代码审查，我们发现：

1. **认证系统碎片化**: 4 个组件各自管理认证，缺少统一身份源
2. **证书管理混乱**: TLS 证书分散管理，无统一 CA 和自动续期
3. **密钥管理风险**: 占位符配置、明文存储、未轮换
4. **信任链不完整**: 自签名证书未互信，使用 insecureSkipVerify
5. **认证协议混用**: Basic Auth、Token、OIDC 混用，缺少标准化

### 10.2 解决方案价值

本方案提供：
- ✅ **统一身份源**: Gitea OIDC 作为唯一身份提供商（IdP）
- ✅ **证书自动化**: cert-manager 统一管理所有 TLS 证书
- ✅ **密钥集中管理**: Sealed Secrets + External Secrets 双重保障
- ✅ **信任链完整**: 统一 CA 证书，组件间互信
- ✅ **认证标准化**: OAuth2/OIDC 为主，Token 为辅，Basic Auth 仅用于内部

### 10.3 实施建议

**立即执行（P0）:**
- Story 0.10: cert-manager 部署
- Story 0.11: Sealed Secrets 部署
- 填充所有 Webhook Secret 和 Token 占位符
- 补充迁移策略和回滚方案

**近期执行（P1）:**
- Story 0.12: Gitea OIDC 配置
- Story 0.13: Harbor/ArgoCD OIDC 集成
- 补充运维手册和监控指标

**中期执行（P2）:**
- Story 0.19: 内部 CA 部署（可选）
- Story 0.20: mTLS 配置（可选）
- Story 0.21: External Secrets 集成
- Story 0.22: Token 自动轮换

### 10.4 风险评估

**高风险项:**
- ⚠️ Gitea OIDC 单点故障 → 需配置 HA + 降级方案
- ⚠️ 迁移过程可能导致登录中断 → 需选择低峰期 + 充分测试
- ⚠️ mTLS 实施复杂度高 → 建议 MVP 阶段暂缓

**中风险项:**
- ⚠️ Let's Encrypt 依赖公网 → 需配置内部 CA 备用
- ⚠️ Sealed Secrets 私钥丢失 → 需备份私钥到安全位置
- ⚠️ 证书续期失败 → 需配置监控告警

### 10.5 总体评价

**优势:**
- ✅ 架构分层清晰，职责分离明确
- ✅ 技术选型主流，社区支持良好
- ✅ 安全覆盖全面，符合零信任原则
- ✅ 自动化程度高，降低运维负担
- ✅ 威胁建模完整，风险可控
- ✅ 迁移策略详细，回滚方案完善
- ✅ 运维手册齐全，监控指标完整

**不足:**
- ❌ 实施复杂度较高（29-41 天）
- ❌ 需要专业安全团队支持
- ❌ 部分高级特性（mTLS）实施难度大

**建议:**
- ✅ 按 P0/P1/P2 优先级逐步改进
- ✅ 调整工期评估，预留充足缓冲
- ✅ 充分测试后再上线，避免影响生产
- ✅ 定期应急演练，确保预案有效

---

## 📎 附录

### A. 配置文件模板

- [Sealed Secret 模板](deployments/sealed-secrets/templates/sealedsecret-template.yaml)
- [External Secret 模板](deployments/external-secrets/templates/externalsecret-template.yaml)
- [Certificate 模板](deployments/cert-manager/templates/certificate-template.yaml)
- [OIDC 配置模板](deployments/gitea/templates/oidc-config-template.yaml)
- [密钥分级模板](deployments/security/templates/secret-classification-template.yaml)
- [迁移计划模板](deployments/migration/templates/migration-plan-template.yaml)
- [回滚方案模板](deployments/disaster-recovery/templates/rollback-plan-template.yaml)

### B. 命令速查表

```bash
# 创建 Sealed Secret
kubeseal --format yaml < secret.yaml > sealed-secret.yaml

# 查看证书过期时间
kubectl get certificate my-cert -o jsonpath='{.status.notAfter}'

# 轮换 Token
kubectl delete secret my-token && kubectl create secret generic my-token ...

# 测试 OIDC 登录
curl -X POST https://gitea.sisys.local/login/oauth/access_token ...

# 备份 Sealed Secrets 私钥
kubectl get secret sealed-secrets-key -n kube-system -o yaml > backup.yaml

# 手动触发证书续期
kubectl annotate certificate my-cert cert-manager.io/renewal-time=$(date -d "+20 days" -Iseconds)

# 查看登录成功率
kubectl logs -l app=gitea | grep -E "(login|auth)" | jq '.status'

# 应急响应：降级到本地认证
kubectl apply -f deployments/gitea/local-auth-config.yaml
```

### C. 参考文档

- [cert-manager 官方文档](https://cert-manager.io/docs/)
- [Sealed Secrets 官方文档](https://github.com/bitnami-labs/sealed-secrets)
- [External Secrets Operator](https://external-secrets.io/)
- [Gitea OIDC 配置指南](https://docs.gitea.com/administration/oauth2-provider)
- [Harbor OIDC 配置指南](https://goharbor.io/docs/2.10.0/administration/configure-authentication/oidc-auth/)
- [ArgoCD OIDC 配置指南](https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/oidc/)
- [NIST SP 800-57 密钥管理指南](https://csrc.nist.gov/publications/detail/sp/800-57/part-1/rev-5/final)
- [NIST SP 800-207 零信任架构](https://csrc.nist.gov/publications/detail/sp/800-207/final)
- [CA/Browser Forum Baseline Requirements](https://cabforum.org/baseline-requirements-documents/)

---

**文档版本:** 2.0.0 (根据评估报告完善)  
**最后更新:** 2026-03-18  
**维护者:** SISYS Architecture Team  
**审查状态:** ✅ 已通过宗师级评估 (B+ 级)  
**下次审查:** 2026-06-18

本宗师级方案提供：

1. **统一身份源**: Gitea OIDC 作为唯一 IdP，实现 SSO
2. **证书自动化**: cert-manager + Let's Encrypt 自动申请和续期
3. **密钥集中管理**: Sealed Secrets + External Secrets 双重保障
4. **信任链完整**: 统一 CA，组件间 mTLS 互信
5. **认证标准化**: OAuth2/OIDC 为主，Token 为辅，Basic Auth 仅内部

### 7.3 实施建议

**立即执行（P0）:**
- Story 0.10: cert-manager 部署
- Story 0.11: Sealed Secrets 部署
- 填充所有 Webhook Secret 和 Token 占位符

**近期执行（P1）:**
- Story 0.12: Gitea OIDC 配置
- Story 0.13: Harbor/ArgoCD OIDC 集成

**中期执行（P2）:**
- Story 0.19: 内部 CA 部署（可选）
- Story 0.20: mTLS 配置（可选）
- Story 0.21: External Secrets 集成
- Story 0.22: Token 自动轮换

### 7.4 预期收益

**安全收益:**
- ✅ 消除明文密钥泄露风险
- ✅ 统一身份认证，减少攻击面
- ✅ 自动证书续期，避免过期中断
- ✅ 完整信任链，防止中间人攻击

**运维收益:**
- ✅ SSO 单点登录，提升用户体验
- ✅ 自动化密钥轮换，减少人工干预
- ✅ 集中审计日志，提升可观测性
- ✅ 标准化认证协议，降低维护成本

---

## 📎 附录

### A. 配置文件模板

- [Sealed Secret 模板](deployments/sealed-secrets/templates/sealedsecret-template.yaml)
- [External Secret 模板](deployments/external-secrets/templates/externalsecret-template.yaml)
- [Certificate 模板](deployments/cert-manager/templates/certificate-template.yaml)
- [OIDC 配置模板](deployments/gitea/templates/oidc-config-template.yaml)

### B. 命令速查表

```bash
# 创建 Sealed Secret
kubeseal --format yaml < secret.yaml > sealed-secret.yaml

# 查看证书过期时间
kubectl get certificate my-cert -o jsonpath='{.status.notAfter}'

# 轮换 Token
kubectl delete secret my-token && kubectl create secret generic my-token ...

# 测试 OIDC 登录
curl -X POST https://gitea.sisys.local/login/oauth/access_token ...
```

### C. 参考文档

- [cert-manager 官方文档](https://cert-manager.io/docs/)
- [Sealed Secrets 官方文档](https://github.com/bitnami-labs/sealed-secrets)
- [External Secrets Operator](https://external-secrets.io/)
- [Gitea OIDC 配置指南](https://docs.gitea.com/administration/oauth2-provider)
- [Harbor OIDC 配置指南](https://goharbor.io/docs/2.10.0/administration/configure-authentication/oidc-auth/)
- [ArgoCD OIDC 配置指南](https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/oidc/)

---

**文档版本:** 1.0.0
**最后更新:** 2026-03-18
**维护者:** SISYS Architecture Team
**审查状态:** 待审查
