# Harbor 架构与运行配置分析报告

> **生成日期**: 2026-04-06
> **Harbor 版本**: v2.14.2
> **命名空间**: `harbor`
> **集群**: K3S (sisys-node-01)
> **文档状态**: ✅ 已验证（基于实际运行时配置）

---

## 目录

1. [系统概览](#1-系统概览)
2. [架构拓扑图](#2-架构拓扑图)
3. [组件详细配置](#3-组件详细配置)
4. [网络与路由配置](#4-网络与路由配置)
5. [存储架构](#5-存储架构)
6. [安全配置](#6-安全配置)
7. [Trivy 漏洞扫描配置](#7-trivy-漏洞扫描配置)
8. [配置差异分析](#8-配置差异分析)
9. [运维指南](#9-运维指南)
10. [附录](#10-附录)

---

## 1. 系统概览

| 项目 | 配置值 |
|------|--------|
| **Harbor 版本** | v2.14.2 (goharbor/*-photon:v2.14.2) |
| **Helm Chart** | harbor/harbor (managed-by: Helm) |
| **命名空间** | `harbor` |
| **外部访问 URL** | `https://harbor.sisys.local` |
| **Ingress 控制器** | Traefik v3.x (IngressRoute CRD) |
| **TLS 证书** | 自签泛域名证书 `*.sisys.local` (RSA 2048, 有效期至 2027-03-17) |
| **TLS 策略** | 强制 TLS 1.3 (TLSOption) |
| **存储类型** | `local-path` / `local-path-ssd` / `native-hdd-vhdx` |
| **认证模式** | `db_auth` (本地数据库认证) |
| **项目数量** | 2 (library + sisys) |
| **sisys 项目仓库数** | 38 |

### 1.1 容器镜像清单

| 组件 | 镜像 | 副本数 |
|------|------|--------|
| Core | `goharbor/harbor-core:v2.14.2` | 1 |
| Portal | `goharbor/harbor-portal:v2.14.2` | 1 |
| Registry | `goharbor/registry-photon:v2.14.2` | 1 (2 containers) |
| RegistryCtl | `goharbor/harbor-registryctl:v2.14.2` | 1 (sidecar) |
| Jobservice | `goharbor/harbor-jobservice:v2.14.2` | 1 |
| Database | `goharbor/harbor-db:v2.14.2` | 1 (StatefulSet) |
| Redis | `goharbor/redis-photon:v2.14.2` | 1 (StatefulSet) |
| Trivy | `goharbor/trivy-adapter-photon:v2.14.2` | 1 (StatefulSet) |
| Nginx | `goharbor/nginx-photon:v2.14.2` | 1 |

---

## 2. 架构拓扑图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Traefik Ingress (websecure)                      │
│                        TLS 1.3 Only (TLSOption)                          │
│                     Cipher: AES_128_GCM / AES_256_GCM / CHACHA20         │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ HTTPS:443 (harbor.sisys.local)
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Harbor IngressRoute (Kustomize)                   │
│                                                                          │
│  Priority 100: /c/login, /c/portal/login    → harbor-core:80 (http)     │
│  Priority  90: /c/, /api/, /service/, /v2/  → harbor-core:80 (http)     │
│  Priority  10: /harbor/                     → harbor-portal:80 (http)   │
│  Priority   5: /* (兜底)                     → harbor-portal:80 (http)   │
│                                                                          │
│  TLS Secret: harbor-tls-secret (自签泛域名证书 *.sisys.local)            │
└───────┬─────────────────────────────┬───────────────────────────────────┘
        │                             │
        ▼                             ▼
┌───────────────┐          ┌──────────────────┐
│  harbor-core  │          │  harbor-portal   │
│  Deployment   │          │   Deployment     │
│  CPU: 500m-2  │          │   CPU: 100m-200m │
│  MEM: 1Gi-4Gi │          │   MEM: 256M-512M │
│  IP: 10.42.0.182          │   IP: 10.42.0.161 │
└───────┬───────┘          └──────────────────┘
        │
        ├────────────────── 内部组件通信 (ClusterIP Services) ─────────────┤
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Harbor 内部服务                                  │
│                                                                          │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────────┐   │
│  │ harbor-registry │   │harbor-jobservice│   │   harbor-trivy      │   │
│  │ 2 containers    │   │  Deployment     │   │   StatefulSet       │   │
│  │ :5000, :8080    │   │  workers: 10    │   │   :8080             │   │
│  │ IP:10.42.0.186  │   │  IP:10.42.0.169 │   │   IP:10.42.0.189    │   │
│  └────────┬────────┘   └────────┬────────┘   └──────────┬──────────┘   │
│           │                     │                       │               │
│           │                     │                       │               │
│  ┌────────▼────────┐   ┌────────▼────────┐   ┌──────────▼──────────┐   │
│  │ harbor-database │   │  harbor-redis   │   │   harbor-nginx      │   │
│  │ StatefulSet     │   │  StatefulSet    │   │   Deployment (代理) │   │
│  │ PostgreSQL      │   │  :6379          │   │   :80, :443         │   │
│  │ IP:10.42.0.187  │   │  IP:10.42.0.174 │   │   IP:10.42.0.165    │   │
│  └─────────────────┘   └─────────────────┘   └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Services 清单

| Service 名称 | ClusterIP | 端口 | 选择器 |
|-------------|-----------|------|--------|
| `harbor` | 10.43.157.173 | 80/TCP, 443/TCP | app=harbor, component=nginx |
| `harbor-core` | 10.43.235.89 | 80/TCP | app=harbor, component=core |
| `harbor-registry` | 10.43.57.133 | 5000/TCP, 8080/TCP | app=harbor, component=registry |
| `harbor-jobservice` | 10.43.199.148 | 80/TCP | app=harbor, component=jobservice |
| `harbor-portal` | 10.43.2.78 | 80/TCP | app=harbor, component=portal |
| `harbor-database` | 10.43.66.164 | 5432/TCP | app=harbor, component=database |
| `harbor-redis` | 10.43.18.115 | 6379/TCP | app=harbor, component=redis |
| `harbor-trivy` | 10.43.92.10 | 8080/TCP | app=harbor, component=trivy |

---

## 3. 组件详细配置

### 3.1 Harbor Core

**资源类型**: Deployment
**镜像**: `goharbor/harbor-core:v2.14.2`
**副本数**: 1

#### 资源配置
| 资源 | Requests | Limits |
|------|----------|--------|
| CPU | 500m | 2000m (2 核) |
| 内存 | 1Gi | 4Gi |

#### 关键环境变量 (ConfigMap: harbor-core)
```yaml
DATABASE_TYPE: postgresql
POSTGRESQL_HOST: harbor-database
POSTGRESQL_PORT: "5432"
POSTGRESQL_DATABASE: registry
POSTGRESQL_USERNAME: postgres
POSTGRESQL_SSLMODE: disable
POSTGRESQL_MAX_IDLE_CONNS: "100"
POSTGRESQL_MAX_OPEN_CONNS: "900"

_REDIS_URL_CORE: redis://harbor-redis:6379/0?idle_timeout_seconds=30
_REDIS_URL_REG: redis://harbor-redis:6379/2?idle_timeout_seconds=30

CORE_URL: http://harbor-core:80
CORE_LOCAL_URL: http://127.0.0.1:8080
PORTAL_URL: http://harbor-portal
JOBSERVICE_URL: http://harbor-jobservice
REGISTRY_URL: http://harbor-registry:5000
REGISTRY_CONTROLLER_URL: http://harbor-registry:8080
TOKEN_SERVICE_URL: http://harbor-core:80/service/token
TRIVY_ADAPTER_URL: http://harbor-trivy:8080

EXT_ENDPOINT: https://harbor.sisys.local
LOG_LEVEL: info
WITH_TRIVY: "true"
REGISTRY_STORAGE_PROVIDER_NAME: filesystem
REGISTRY_CREDENTIAL_USERNAME: harbor_registry_user
```

#### 健康检查
- **Startup Probe**: HTTP GET `/api/v2.0/ping` :8080 (failureThreshold: 360, period: 10s)
- **Liveness Probe**: HTTP GET `/api/v2.0/ping` :8080 (failureThreshold: 2, period: 10s)
- **Readiness Probe**: HTTP GET `/api/v2.0/ping` :8080 (failureThreshold: 2, period: 10s)

#### 安全上下文
```yaml
runAsNonRoot: true
runAsUser: 10000
fsGroup: 10000
allowPrivilegeEscalation: false
privileged: false
capabilities.drop: [ALL]
seccompProfile.type: RuntimeDefault
automountServiceAccountToken: false
```

### 3.2 Harbor Registry

**资源类型**: Deployment (Sidecar 模式)
**容器**:
- `registry`: `goharbor/registry-photon:v2.14.2`
- `registryctl`: `goharbor/harbor-registryctl:v2.14.2`

#### Registry 配置 (ConfigMap: harbor-registry)
```yaml
# config.yml
version: 0.1
storage:
  filesystem:
    rootdirectory: /storage
  cache:
    layerinfo: redis    # Redis 缓存层
  delete:
    enabled: true
  maintenance:
    uploadpurging:
      enabled: true
      age: 168h         # 7 天
      interval: 24h

redis:
  addr: harbor-redis:6379
  db: 2
  pool:
    maxidle: 100
    maxactive: 500
    idletimeout: 60s

http:
  addr: :5000
  debug:
    addr: localhost:5001

auth:
  htpasswd:
    realm: harbor-registry-basic-realm
    path: /etc/registry/passwd

compatibility:
  schema1:
    enabled: true       # 兼容 Docker Schema V1
```

#### RegistryCtl 配置
```yaml
protocol: "http"
port: 8080
log_level: info
registry_config: "/etc/registry/config.yml"
```

### 3.3 Harbor Jobservice

**资源类型**: Deployment
**镜像**: `goharbor/harbor-jobservice:v2.14.2`

#### 关键配置 (ConfigMap: harbor-jobservice)
```yaml
protocol: "http"
port: 8080
worker_pool:
  workers: 10
  backend: "redis"
  redis_pool:
    redis_url: "redis://harbor-redis:6379/1"
    namespace: "harbor_job_service_namespace"
    idle_timeout_second: 3600

job_loggers:
  - name: "FILE"
    level: INFO
    settings:
      base_dir: "/var/log/jobs"
    sweeper:
      duration: 14      # 日志保留 14 天

reaper:
  max_update_hours: 24      # 任务最大更新时间
  max_dangling_hours: 168   # 悬空任务最大时长 (7 天)
```

### 3.4 Harbor Database (PostgreSQL)

**资源类型**: StatefulSet
**镜像**: `goharbor/harbor-db:v2.14.2`
**副本数**: 1

#### 配置详情
```yaml
env:
  PGDATA: /var/lib/postgresql/data/pgdata
envFrom:
  - secretRef: harbor-database   # POSTGRES_PASSWORD

securityContext:
  runAsNonRoot: true
  runAsUser: 999
  fsGroup: 999
  allowPrivilegeEscalation: false
  privileged: false
  capabilities.drop: [ALL]
  seccompProfile.type: RuntimeDefault

shm:
  emptyDir:
    medium: Memory
    sizeLimit: 512Mi

terminationGracePeriodSeconds: 120
```

#### 健康检查
- **Liveness/Readiness**: exec `/docker-healthcheck.sh`
- **initialDelaySeconds**: 300 (liveness), 1 (readiness)

### 3.5 Harbor Redis

**资源类型**: StatefulSet
**镜像**: Redis (goharbor/redis-photon:v2.14.2)
**副本数**: 1
**端口**: 6379

### 3.6 Harbor Portal

**资源类型**: Deployment
**镜像**: `goharbor/harbor-portal:v2.14.2`
**用途**: 静态 Web 前端服务

### 3.7 Harbor Nginx (内部代理)

**资源类型**: Deployment
**镜像**: `goharbor/nginx-photon:v2.14.2`
**用途**: 内部组件代理 (非外部流量入口)
**外部流量由 Traefik IngressRoute 直接路由到 harbor-core/harbor-portal**

---

## 4. 网络与路由配置

### 4.1 IngressRoute (Traefik CRD)

**资源**: `ingressroute.traefik.io/harbor-ingressroute`
**命名空间**: `harbor`
**EntryPoints**: `websecure` (HTTPS)

#### 路由规则

| 优先级 | 匹配规则 | 目标服务 | 端口 | 协议 |
|--------|---------|---------|------|------|
| 100 | `Host(harbor.sisys.local) && Path(/c/login)` | harbor-core | 80 | http |
| 100 | `Host(harbor.sisys.local) && PathPrefix(/c/portal/login)` | harbor-core | 80 | http |
| 90 | `Host(harbor.sisys.local) && PathPrefix(/c/)` | harbor-core | 80 | http |
| 90 | `Host(harbor.sisys.local) && PathPrefix(/api/)` | harbor-core | 80 | http |
| 90 | `Host(harbor.sisys.local) && PathPrefix(/service/)` | harbor-core | 80 | http |
| 90 | `Host(harbor.sisys.local) && PathPrefix(/v2/)` | harbor-core | 80 | http |
| 10 | `Host(harbor.sisys.local) && PathPrefix(/harbor/)` | harbor-portal | 80 | http |
| 5 | `Host(harbor.sisys.local) && PathPrefix(/)` | harbor-portal | 80 | http |

> **注意**: Helm Chart 中的 `expose.ingress.enabled=false`，使用独立 Kustomize 管理的 IngressRoute CRD

### 4.2 TLSOption (Traefik TLS 策略)

**资源**: `tlsoption.traefik.io/default-tls-options`
**命名空间**: `default` (Traefik 在此命名空间查找)

```yaml
spec:
  minVersion: VersionTLS13
  maxVersion: VersionTLS13
  cipherSuites:
    - TLS_AES_128_GCM_SHA256
    - TLS_AES_256_GCM_SHA384
    - TLS_CHACHA20_POLY1305_SHA256
  sniStrict: true
  preferServerCipherSuites: true
```

### 4.3 TLS 证书

**Secret**: `harbor-tls-secret` (kubernetes.io/tls)
**证书类型**: 自签泛域名证书

| 属性 | 值 |
|------|-----|
| **Subject** | CN=*.sisys.local, O=SISYS |
| **Issuer** | CN=*.sisys.local, O=SISYS (自签) |
| **公钥算法** | RSA 2048 bit |
| **签名算法** | sha256WithRSAEncryption |
| **有效期** | 2026-03-17 ~ 2027-03-17 (1 年) |
| **SAN** | *.sisys.local |

### 4.4 NetworkPolicy (8 条策略)

| 策略名称 | 类型 | 作用 |
|---------|------|------|
| `harbor-default-deny` | Ingress+Egress | 默认拒绝所有流量 |
| `harbor-allow-traefik-ingress` | Ingress | 允许 Traefik (kube-system/traefik-system) → harbor-core:443 |
| `harbor-allow-internal-communication` | Ingress | 允许 harbor 命名空间内 Pod 互相访问 (80, 443, 5432, 6379) |
| `harbor-allow-core-to-postgres` | Ingress | harbor-core → harbor-database:5432 |
| `harbor-allow-core-to-redis` | Ingress | harbor-core → harbor-redis:6379 |
| `harbor-allow-registry-storage` | Egress | harbor-registry → harbor-registry:5000 |
| `harbor-allow-dns` | Egress | 所有 Pod → kube-dns:53 (UDP/TCP) |
| `harbor-allow-trivy-external` | Egress | Trivy → 外部网络 (443, 80)，排除 RFC1918 私有地址 |

---

## 5. 存储架构

### 5.1 PVC 清单

| PVC 名称 | 容量 | StorageClass | 访问模式 | 用途 | 状态 |
|---------|------|-------------|---------|------|------|
| `database-data-harbor-database-0` | 1Gi | local-path | RWO | PostgreSQL 数据 | Bound |
| `data-harbor-redis-0` | 1Gi | local-path | RWO | Redis 数据 | Bound |
| `data-harbor-trivy-0` | 5Gi | local-path | RWO | Trivy 缓存/报告 | Bound |
| `harbor-jobservice` | 1Gi | local-path | RWO | JobService 日志 | Bound |
| `harbor-registry-hot` | 50Gi | **local-path-ssd** | RWO | Registry 热存储 (SSD) | Bound |
| `harbor-registry-warm` | 2Ti | **native-hdd-vhdx** | RWO | Registry 温存储 (HDD) | Bound |
| `harbor-registry-cold` | - | local-path-hdd | RWO | Registry 冷存储 | **Pending** |

### 5.2 存储分层架构

```
Registry 存储策略:
┌─────────────────────────────────────────────┐
│  Hot (50Gi SSD) - harbor-registry-warm      │  ← 实际挂载
│  用途: 最近推送的镜像层，高频访问              │
│  StorageClass: local-path-ssd               │
├─────────────────────────────────────────────┤
│  Warm (2Ti HDD) - harbor-registry-warm      │  ← 实际挂载 (2Ti)
│  用途: 历史镜像层，中等频率访问                │
│  StorageClass: native-hdd-vhdx              │
├─────────────────────────────────────────────┤
│  Cold (Pending) - harbor-registry-cold      │  ← 未绑定
│  用途: 归档镜像，极低频率访问                  │
│  StorageClass: local-path-hdd               │
└─────────────────────────────────────────────┘
```

> **注意**: Registry Deployment 当前仅挂载 `harbor-registry-warm` PVC，实际存储架构为热温两层。Cold storage PVC 存在但未绑定到 Deployment。

### 5.3 存储配置对比

| 组件 | values.yaml 配置 | 实际运行时 | 差异 |
|------|-----------------|-----------|------|
| Database PVC | 10Gi | **1Gi** | ⚠️ 实际为配置的 1/10 |
| Registry PVC | 50Gi (registry) + 10Gi (chart) | **50Gi SSD + 2Ti HDD** | ⚠️ 实际远超配置 (分层存储) |
| Jobservice PVC | 5Gi | **1Gi** | ⚠️ 实际为配置的 1/5 |
| Trivy PVC | 未明确 | 5Gi | - (与 StatefulSet 文件一致) |
| Redis PVC | 未明确 | 1Gi | - |

---

## 6. 安全配置

### 6.1 容器安全

| 组件 | runAsNonRoot | runAsUser | 只读根文件系统 | 特权模式 | Capabilities | Seccomp |
|------|-------------|-----------|--------------|---------|-------------|---------|
| Core | true | 10000 | - | false | DROP ALL | RuntimeDefault |
| Registry | true | 10000 | - | false | DROP ALL | RuntimeDefault |
| Jobservice | - | - | - | - | - | - |
| Database | true | 999 | - | false | DROP ALL | RuntimeDefault |
| Trivy | - | - | - | - | - | RuntimeDefault |

### 6.2 认证与授权

| 配置项 | 值 |
|--------|-----|
| **认证模式** | `db_auth` (本地数据库) |
| **自注册** | 禁用 (仅管理员邀请制) |
| **会话超时** | 4320 分钟 (3 天) |
| **管理员密码** | 存储在 `harbor-secret` Secret 中 |
| **Cookie 安全** | secure: true, httpOnly: true |

### 6.3 Secret 管理

**Secret 名称**: `harbor-secret`
**包含的密钥** (7 个):

| 密钥名称 | 用途 |
|---------|------|
| `HARBOR_ADMIN_PASSWORD` | Harbor 管理员密码 |
| `POSTGRES_PASSWORD` | PostgreSQL 数据库密码 |
| `POSTGRES_USERNAME` | postgres (明文) |
| `POSTGRES_DATABASE` | registry (明文) |
| `REDIS_PASSWORD` | Redis 密码 |
| `REGISTRY_CREDENTIAL_SECRET` | Registry 凭证密钥 |
| `SECRET_KEY` | Harbor 加密密钥 (≥32 字节) |

### 6.4 TLS 安全

| 项目 | 配置 |
|------|------|
| **最小 TLS 版本** | TLS 1.3 |
| **最大 TLS 版本** | TLS 1.3 |
| **加密套件** | TLS_AES_128_GCM_SHA256, TLS_AES_256_GCM_SHA384, TLS_CHACHA20_POLY1305_SHA256 |
| **SNI 严格模式** | 启用 |
| **HSTS 安全头** | ❌ **未部署** (Middleware 缺失) |
| **CSP 策略** | ❌ **未部署** |

### 6.5 网络安全总结

| 安全层 | 状态 | 详情 |
|--------|------|------|
| DefaultDeny Ingress | ✅ | 所有入站流量默认拒绝 |
| DefaultDeny Egress | ✅ | 所有出站流量默认拒绝 |
| Traefik 入站白名单 | ✅ | 仅允许 kube-system/traefik-system 的 Traefik Pod |
| 内部组件隔离 | ✅ | 仅 harbor 标签 Pod 可互相访问 |
| 数据库访问控制 | ✅ | 仅 harbor-core 可访问 PostgreSQL/Redis |
| DNS 解析 | ✅ | 仅允许 kube-dns |
| Trivy 外部访问 | ✅ | 仅允许 HTTPS 访问外部 (排除内网) |

---

## 7. Trivy 漏洞扫描配置

### 7.1 基本信息

| 项目 | 值 |
|------|-----|
| **资源类型** | StatefulSet |
| **镜像** | `goharbor/trivy-adapter-photon:v2.14.2` |
| **副本数** | 1 |
| **端口** | 8080 (api-server) |
| **PVC** | 5Gi (local-path) |

### 7.2 扫描配置 (实际环境变量)

```yaml
SCANNER_TRIVY_SEVERITY: HIGH,CRITICAL
SCANNER_TRIVY_VULN_TYPE: os,library
SCANNER_TRIVY_TIMEOUT: 5m0s
SCANNER_TRIVY_DEBUG_MODE: false
SCANNER_TRIVY_IGNORE_UNFIXED: false
SCANNER_TRIVY_SKIP_UPDATE: false
SCANNER_TRIVY_SKIP_JAVA_DB_UPDATE: false
SCANNER_TRIVY_OFFLINE_SCAN: false
SCANNER_TRIVY_SECURITY_CHECKS: vuln
SCANNER_TRIVY_INSECURE: true

# 漏洞数据库来源 (内部 Harbor 仓库)
SCANNER_TRIVY_DB_REPOSITORY: harbor.sisys.local/sisys/aquasecurity/trivy-db:2
SCANNER_TRIVY_JAVA_DB_REPOSITORY: harbor.sisys.local/sisys/aquasecurity/trivy-java-db:1
SCANNER_TRIVY_CHECKS_BUNDLE_REPOSITORY: harbor.sisys.local/sisys/aquasecurity/trivy-checks:2

# Redis 连接
SCANNER_REDIS_URL: (from secret harbor-trivy/redisURL)
SCANNER_STORE_REDIS_URL: (from secret harbor-trivy/redisURL)
SCANNER_JOB_QUEUE_REDIS_URL: (from secret harbor-trivy/redisURL)
```

### 7.3 Trivy ConfigMap 资源

| ConfigMap | 数据 | 用途 |
|-----------|------|------|
| `trivy-scan-config` | scan-policy | 扫描策略 (onPush, schedule) |
| `trivy-db-update-config` | db-update-config | 漏洞数据库更新配置 |
| `trivy-scan-policies` | on-push-policy, schedule-policy, alert-policy | 扫描与告警策略 |
| `trivy-webhook-notify` | webhook-config | Webhook 通知配置 (→ Gitea) |

### 7.4 漏洞数据库更新策略

| 配置项 | 值 |
|--------|-----|
| **自动更新** | 启用 |
| **更新调度** | 每天凌晨 4:00 |
| **更新来源** | 内部 Harbor 仓库 (非 GitHub) |
| **重试策略** | 最多 3 次，间隔 30 分钟，退避倍数 2 |
| **超时** | 10 分钟 |

> **关键发现**: Trivy 配置为从 **内部 Harbor 仓库** (`harbor.sisys.local/sisys/aquasecurity/*`) 拉取漏洞数据库，而非直接从 GitHub/GHCR 拉取。这意味着需要先手动同步漏洞数据库到 Harbor 仓库。

### 7.5 Trivy 健康检查

- **Liveness**: HTTP GET `/probe/healthy` :8080 (initialDelay: 5s, failure: 10)
- **Readiness**: HTTP GET `/probe/ready` :8080 (initialDelay: 5s, failure: 3)

---

## 8. 配置差异分析

### 8.1 values.yaml vs 实际运行时

| # | 配置项 | values.yaml 声明 | 实际运行时 | 差异等级 | 说明 |
|---|--------|-----------------|-----------|---------|------|
| 1 | Harbor 版本 | v2.14.3 | **v2.14.2** | ⚠️ MEDIUM | 配置文件版本与实际不符 |
| 2 | Database PVC | 10Gi | **1Gi** | 🔴 HIGH | 实际仅为配置的 10%，生产风险 |
| 3 | Registry PVC | 50Gi + 10Gi (chart) | **50Gi SSD + 2Ti HDD** | ℹ️ INFO | 实际采用分层存储，远超配置 |
| 4 | Jobservice PVC | 5Gi | **1Gi** | ⚠️ MEDIUM | 实际仅为配置的 20% |
| 5 | Middleware | 定义 security-headers | **未部署** | 🔴 HIGH | 缺少 HSTS/CSP 等安全头 |
| 6 | TLS 证书 | cert-manager/Let's Encrypt | **自签泛域名证书** | ℹ️ INFO | 未使用 cert-manager |
| 7 | Registry 副本 | 1 | **1** (但曾设为 0) | ℹ️ INFO | 当前正常 |
| 8 | Redis DB 索引 | 未明确 | Core:0, Reg:2, Job:1 | ℹ️ INFO | 三组件使用不同 DB |
| 9 | PostgreSQL 连接 | maxIdle:50, maxOpen:1000 | **maxIdle:100, maxOpen:900** | ℹ️ INFO | 实际连接池更大 |
| 10 | Schema V1 兼容 | 未提及 | **enabled: true** | ℹ️ INFO | 兼容旧版 Docker |
| 11 | 密码策略 Job | 定义了 password-policy-init Job | **未运行** (Job 不存在) | ⚠️ MEDIUM | 策略可能未生效 |
| 12 | Robot Account Job | 定义了 create-robot-account Job | **未运行** | ⚠️ MEDIUM | 可能通过 UI 手动创建 |

### 8.2 关键风险项

#### 🔴 HIGH-001: Database PVC 容量不足

- **问题**: values.yaml 配置 10Gi，实际仅分配 1Gi
- **影响**: PostgreSQL 数据可能占满空间导致服务中断
- **建议**: 扩容至至少 10Gi，或监控使用率并提前扩容

#### 🔴 HIGH-002: Middleware 未部署

- **问题**: `middleware.yaml` 定义了安全响应头 Middleware，但未实际应用到 IngressRoute
- **影响**: 缺少以下安全头:
  - HSTS (HTTP Strict Transport Security)
  - Content-Security-Policy
  - X-Frame-Options: DENY
  - X-Content-Type-Options: nosniff
  - XSS-Protection
- **建议**: 在 IngressRoute 中引用 `harbor-middleware-chain`

#### ⚠️ MEDIUM-001: 密码策略 Job 未执行

- **问题**: `password-policy-job.yaml` 定义了初始化 Job，但集群中不存在
- **影响**: 密码策略 (最小 12 位、复杂度要求、密码历史) 可能未生效
- **建议**: 手动执行 Job 或通过 Harbor UI 验证/配置密码策略

#### ⚠️ MEDIUM-002: Trivy 漏洞数据库来源

- **问题**: Trivy 配置为从内部 Harbor 拉取漏洞数据库，需确保仓库已同步
- **影响**: 如仓库无更新，漏洞扫描结果可能过时
- **建议**: 建立自动化同步机制或切换为 GitHub 源

---

## 9. 运维指南

### 9.1 常用命令

```bash
# 查看所有 Pod 状态
kubectl get pods -n harbor -o wide

# 查看组件日志
kubectl logs -n harbor deployment/harbor-core -f
kubectl logs -n harbor statefulset/harbor-trivy -f
kubectl logs -n harbor statefulset/harbor-database -f

# 查看 PVC 使用情况
kubectl get pvc -n harbor

# 查看 Helm Release 状态
helm list -n harbor

# 验证 HTTPS 访问
curl -vk https://harbor.sisys.local/api/v2.0/ping

# 检查 TLS 证书
echo | openssl s_client -connect harbor.sisys.local:443 -servername harbor.sisys.local 2>/dev/null | openssl x509 -noout -dates

# 查看 NetworkPolicy
kubectl get networkpolicy -n harbor

# 查看 IngressRoute
kubectl get ingressroute -n harbor
```

### 9.2 备份策略

| 组件 | 备份方式 | 频率 | 保留 |
|------|---------|------|------|
| PostgreSQL | K3S etcd-snapshot | 每日 02:00 | 7 天 |
| Redis | 无 (缓存层) | - | - |
| Registry PVC | K3S etcd-snapshot | 每日 02:00 | 7 天 |
| TLS 证书 | 手动备份 Secret | 按需 | - |

### 9.3 扩容触发条件

| 组件 | 触发条件 | 扩容目标 |
|------|---------|---------|
| Registry 存储 | 使用率 > 80% | 100Gi → 500Gi |
| Database 存储 | 使用率 > 70% | 1Gi → 10Gi |
| Core 副本数 | CPU 持续 > 70% | 1 → 2 (需 HA 配置) |

### 9.4 故障排查

#### Trivy 扫描不工作
```bash
# 检查 Trivy 状态
kubectl logs -n harbor harbor-trivy-0 | grep "Starting API server"

# 验证漏洞数据库
kubectl logs -n harbor harbor-trivy-0 | grep "vulnerability database"

# 检查内部仓库是否可访问
kubectl exec harbor-trivy-0 -n harbor -- curl -s http://harbor-registry:5000/v2/_catalog
```

#### Core 启动失败
```bash
# 检查数据库连接
kubectl exec harbor-core -n harbor -- nc -zv harbor-database 5432

# 检查 Redis 连接
kubectl exec harbor-core -n harbor -- nc -zv harbor-redis 6379

# 查看启动日志
kubectl logs -n harbor deployment/harbor-core --previous
```

#### 存储问题
```bash
# 查看 PV 详情
kubectl get pv -n harbor -o wide

# 检查 StorageClass
kubectl get storageclass

# 查看 Pending PVC 事件
kubectl describe pvc harbor-registry-cold -n harbor
```

---

## 10. 附录

### 10.1 Harbor 项目配置

| 项目 | 可见性 | 仓库数 | 自动扫描 | 漏洞阻止 | Cosign 签名 | CVE 白名单 |
|------|--------|--------|---------|---------|-----------|-----------|
| `library` | 公开 | 0 | - | - | - | 空 |
| `sisys` | 公开 | 38 | ✅ 启用 | ❌ 未启用 | ❌ 未启用 | 复用系统 |

### 10.2 Redis 数据库分配

| Harbor 组件 | Redis DB | 用途 |
|------------|----------|------|
| Core | DB 0 | 会话、缓存 |
| Jobservice | DB 1 | 任务队列 |
| Registry | DB 2 | 层信息缓存 |

### 10.3 关键端口汇总

| 组件 | 端口 | 协议 | 用途 |
|------|------|------|------|
| Harbor Core | 8080 | HTTP | API 服务 |
| Harbor Core | 80 | HTTP | Service 暴露 |
| Registry | 5000 | HTTP | Docker Registry API |
| Registry | 5001 | HTTP | Debug 端点 |
| RegistryCtl | 8080 | HTTP | Registry 控制 |
| Jobservice | 8080 | HTTP | 任务调度 |
| Database | 5432 | TCP | PostgreSQL |
| Redis | 6379 | TCP | Redis |
| Trivy | 8080 | HTTP | 扫描 API |
| Nginx | 80, 443 | HTTP/HTTPS | 内部代理 |
| IngressRoute | 443 | HTTPS | 外部入口 (Traefik) |

### 10.4 部署配置文件清单

| 文件 | 类型 | 管理方式 | 状态 |
|------|------|---------|------|
| `values.yaml` | Helm Values | Helm | ✅ 参考配置 |
| `config/harbor.yml` | 应用配置 | ConfigMap | ✅ 参考配置 |
| `kustomization.yaml` | Kustomize | Kustomize | ✅ 资源编排 |
| `namespace.yaml` | Namespace | Kustomize | ✅ 已部署 |
| `ingress-route.yaml` | IngressRoute | Kustomize | ✅ 已部署 |
| `middleware.yaml` | Middleware | Kustomize | ❌ **未部署** |
| `tlsoption.yaml` | TLSOption | Kustomize | ✅ 已部署 (default ns) |
| `networkpolicy.yaml` | NetworkPolicy | Kustomize | ✅ 已部署 (8 条) |
| `password-policy-job.yaml` | Job | Kustomize | ❌ **未执行** |
| `robot-account.yaml` | Job/Config | 手动 | ⚠️ 参考模板 |
| `trivy-config.yaml` | ConfigMap | 手动 | ✅ 已部署 |
| `harbor-letsencrypt.yaml` | CertManager | 手动 | ❌ **未使用** (自签证书) |
| `cosign-config.yaml` | ConfigMap | 手动 | ⚠️ 参考配置 |
| `webhook-config.yaml` | ConfigMap | 手动 | ⚠️ 参考配置 |
| `harbor-trivy-statefulset.yaml` | StatefulSet | 手动 | ✅ 参考实际配置 |

### 10.5 参考文档

- [Harbor 官方文档](https://goharbor.io/docs/)
- [Harbor Helm Chart](https://github.com/goharbor/harbor-helm)
- [Trivy Scanner 文档](https://aquasecurity.github.io/trivy/)
- [Cosign 镜像签名](https://github.com/sigstore/cosign)
- Traefik IngressRoute 文档

---

*文档生成时间: 2026-04-06*
*基于实际运行时配置验证*
*Harbor 版本: v2.14.2*
