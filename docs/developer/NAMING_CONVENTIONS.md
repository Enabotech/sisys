# Epic 0 命名规范与端口配置

**版本：** 1.0
**日期：** 2026-03-05
**状态：** ✅ 统一标准

---

## 📋 统一命名规范

### 域名命名规范

**格式：** `<component>.sisys.local`

| 组件 | 域名 | 说明 |
|------|------|------|
| Gitea | `gitea.sisys.local` | 代码托管 |
| Harbor | `harbor.sisys.local` | 镜像仓库 |
| ArgoCD | `argocd.sisys.local` | 持续部署 |
| SISYS App | `sisys.local` | 应用系统 |
| Longhorn | `longhorn.sisys.local` | 存储管理 |

### Hosts 配置

```bash
# Windows: C:\Windows\System32\drivers\etc\hosts
# Linux/Mac: /etc/hosts

# K3S Cluster
10.0.0.1  k3s.sisys.local

# Development Tools
10.0.0.1  gitea.sisys.local
10.0.0.1  harbor.sisys.local
10.0.0.1  argocd.sisys.local
10.0.0.1  longhorn.sisys.local

# Application
10.0.0.1  sisys.local
```

---

## 🔌 端口号统一配置

### 外部访问端口

| 组件 | 外部端口 | 内部端口 | 协议 | 说明 |
|------|---------|---------|------|------|
| Gitea | 80/443 | 3000 | HTTP/HTTPS | 通过 Traefik 反向代理 |
| Harbor | 80/443 | 8080 | HTTP/HTTPS | 通过 Traefik 反向代理 |
| ArgoCD | 80/443 | 8088 | HTTP/HTTPS | 通过 Traefik 反向代理 |
| SISYS App | 80/443 | 8000 | HTTP/HTTPS | 通过 Traefik 反向代理 |

### 内部服务端口

| 组件 | 端口 | 协议 | 说明 |
|------|------|------|------|
| K3S API | 6443 | HTTPS | Kubernetes API Server |
| Gitea SSH | 2222 | SSH | Git SSH 访问 |
| PostgreSQL | 5432 | TCP | 数据库 |
| Redis | 6379 | TCP | 缓存 |
| Harbor Core | 8080 | HTTP | Harbor 内部通信 |

---

## 🔐 默认账号密码规范

### 统一密码策略

**要求：**
- 最小长度：12 位
- 包含大小写字母
- 包含数字
- 包含特殊字符

### 默认账号清单

| 组件 | 用户名 | 默认密码 | 首次登录强制修改 |
|------|--------|---------|----------------|
| Gitea | `admin` | `Admin12345!` | ✅ 是 |
| Harbor | `admin` | `Harbor12345!` | ✅ 是 |
| ArgoCD | `admin` | `<动态生成>` | ✅ 是 |
| K3S | `admin` | `<kubeconfig>` | ✅ 是 |

**获取 ArgoCD 初始密码：**
```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
```

---

## 📁 文件路径规范

### 部署文件路径

```
/opt/sisys/
├── k3s/
│   └── config.yaml
├── gitea/
│   └── gitea-values.yaml
├── harbor/
│   └── harbor-values.yaml
├── argocd/
│   └── argocd-values.yaml
└── scripts/
    ├── install.sh
    ├── backup.sh
    └── restore.sh
```

### 文档路径

```
docs/
├── deployment/
│   ├── K3S_CLUSTER_SETUP.md
│   ├── GITEA_INSTALLATION.md
│   ├── HARBOR_INSTALLATION.md
│   ├── ARGOCD_SETUP.md
│   ├── GITEA_RUNNER_SETUP.md
│   └── CI_CD_PIPELINE_TEMPLATE.md
├── delivery/
│   ├── WINDOWS_INSTALLER.md
│   ├── MAC_INSTALLER.md
│   ├── LINUX_INSTALLER.md
│   ├── AUTO_DIAGNOSE_AND_FIX.md
│   └── CONFIG_WIZARD.md
└── developer/
    ├── EPIC_0_REFACTORED.md
    ├── TEST_FRAMEWORK_SETUP.md
    └── ...
```

---

## 🔄 环境变量规范

### 全局环境变量

```bash
# /etc/environment

# 系统配置
SISYS_ENV=development
SISYS_VERSION=1.0.0

# 镜像仓库
REGISTRY=harbor.sisys.local
REGISTRY_USERNAME=admin
REGISTRY_PASSWORD=Harbor12345!

# K3S 配置
KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# 域名配置
GITEA_URL=http://gitea.sisys.local
HARBOR_URL=http://harbor.sisys.local
ARGOCD_URL=http://argocd.sisys.local
SISYS_URL=http://sisys.local
```

---

## ✅ 验收清单

### 部署验收

- [ ] 所有域名可解析
- [ ] 所有服务可通过统一端口访问
- [ ] HTTPS 证书配置正确
- [ ] 默认密码已修改

### 文档验收

- [ ] 所有文档使用统一命名
- [ ] 所有文档使用统一端口号
- [ ] 所有文档使用统一域名

---

**实施状态：** ✅ 已应用到所有文档
