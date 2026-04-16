# 宗师级密码统一管理解决方案

**文档版本**: v1.0
**创建日期**: 2026-03-18
**适用范围**: Story 0.4-0.7 (K3S/Gitea/Harbor/ArgoCD)
**安全等级**: 🔴 机密

---

## 📋 执行摘要

本文档提供 sisys 企业战略规划管理系统的**宗师级密码统一管理解决方案**，基于对 Story 0.4-0.7 的深入分析，涵盖 K3S、Gitea、Harbor、ArgoCD、Docker/Container 等核心系统的密码管理。

### 核心发现

| 系统 | 密码数量 | 存储位置 | 管理方式 | 风险等级 |
|------|---------|---------|---------|---------|
| **K3S** | 1 | kubeconfig | 文件 | 🟡 中 |
| **Gitea** | 6 | Kubernetes Secret | 占位符+CI/CD注入 | 🟢 低 |
| **Harbor** | 5 | Kubernetes Secret | 脚本生成+手动应用 | 🟡 中 |
| **ArgoCD** | 3 | Kubernetes Secret | 占位符+手动配置 | 🟡 中 |
| **Docker/Container** | 2 | Docker Config/Secret | 明文/环境变量 | 🔴 高 |

### 密码清单总览

**共计 17 个核心密码**，分布在 5 个系统中：

```
┌─────────────────────────────────────────────────────────────────┐
│                        密码资产清单                              │
├─────────────────────────────────────────────────────────────────┤
│ K3S (1 个)                                                       │
│ ├── admin (kubeconfig)                                          │
│ └── 位置：~/.kube/config, /etc/rancher/k3s/k3s.yaml            │
├─────────────────────────────────────────────────────────────────┤
│ Gitea (6 个)                                                     │
│ ├── GITEA_ADMIN_PASSWORD (管理员密码)                           │
│ ├── GITEA_SECRET_KEY (应用密钥)                                 │
│ ├── GITEA_INTERNAL_TOKEN (内部 Token)                           │
│ ├── GITEA_JWT_SECRET (OAuth2 JWT 密钥)                          │
│ ├── GITEA_DB_PASSWORD (数据库密码)                              │
│ └── GITEA_DB_ADMIN_PASSWORD (数据库管理员密码)                  │
├─────────────────────────────────────────────────────────────────┤
│ Harbor (5 个)                                                    │
│ ├── HARBOR_ADMIN_PASSWORD (管理员密码)                          │
│ ├── HARBOR_SECRET_KEY (核心密钥)                                │
│ ├── HARBOR_POSTGRES_PASSWORD (数据库密码)                       │
│ ├── HARBOR_REDIS_PASSWORD (Redis 密码)                          │
│ └── HARBOR_REGISTRY_CREDENTIAL_SECRET (Registry 密钥)           │
├─────────────────────────────────────────────────────────────────┤
│ ArgoCD (3 个)                                                    │
│ ├── argocd-initial-admin-secret (初始管理员密码)                │
│ ├── argocd-gitea-creds password (Gitea Token)                   │
│ └── argocd-image-updater-secret (Harbor Robot Token)            │
├─────────────────────────────────────────────────────────────────┤
│ Docker/Container (2 个)                                          │
│ ├── MINIO_ROOT_PASSWORD (MinIO 管理员密码)                      │
│ └── POSTGRES_PASSWORD (PostgreSQL 密码)                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔍 现状分析

### 1. K3S 密码管理

**当前状态**:
- **密码类型**: kubeconfig (证书 + Token 组合)
- **存储位置**:
  - WSL2: `/etc/rancher/k3s/k3s.yaml`
  - 用户：`~/.kube/config`
- **访问方式**: kubectl 自动读取
- **风险点**:
  - ⚠️ kubeconfig 文件权限可能过宽
  - ⚠️ 多节点部署时 kubeconfig 通过 Docker 容器传输
  - ⚠️ 无密码轮换机制

**当前配置**:
```yaml
# K3S kubeconfig 示例
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: <CA_DATA>
    server: https://127.0.0.1:6443
  name: default
contexts:
- context:
    cluster: default
    user: default
  name: default
current-context: default
users:
- name: default
  user:
    client-certificate-data: <CERT_DATA>
    client-key-data: <KEY_DATA>
```

### 2. Gitea 密码管理

**当前状态**:
- **密码类型**: 6 个密钥
- **存储位置**: Kubernetes Secret (gitea-admin-secret, gitea-app-secret, gitea-postgresql-secret)
- **管理方式**: 占位符 + CI/CD 注入
- **优势**:
  - ✅ 使用 Kubernetes Secret 存储
  - ✅ 支持 CI/CD 自动注入
  - ✅ 有完整的 secrets.yaml 模板

**当前配置**:
```yaml
# deploy/kubernetes/gitea/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: gitea-admin-secret
  namespace: gitea
type: Opaque
stringData:
  username: "gitea_admin"
  password: "${GITEA_ADMIN_PASSWORD}"  # 占位符
```

**风险点**:
- ⚠️ 开发环境使用明文占位符
- ⚠️ 依赖 CI/CD 正确配置环境变量
- ⚠️ 无自动轮换机制

### 3. Harbor 密码管理

**当前状态**:
- **密码类型**: 5 个密钥
- **存储位置**: Kubernetes Secret (harbor-secret)
- **管理方式**: 脚本生成 + 手动应用
- **优势**:
  - ✅ 有完整的密码生成脚本 (`generate-harbor-secrets.sh`)
  - ✅ 密码符合复杂度要求 (12 位 + 大小写 + 数字 + 符号)
  - ✅ 有密码策略初始化 Job

**当前配置**:
```yaml
# deploy/kubernetes/harbor/secrets-example.yaml
apiVersion: v1
kind: Secret
metadata:
  name: harbor-secret
  namespace: harbor
type: Opaque
stringData:
  SECRET_KEY: "dev-secret-key-please-change-in-production"
  HARBOR_ADMIN_PASSWORD: "Harbor@2026Secure!"
  POSTGRES_PASSWORD: "postgres123"
  REDIS_PASSWORD: "redis123"
  REGISTRY_CREDENTIAL_SECRET: "registry-dev-secret"
```

**风险点**:
- ⚠️ 示例文件包含明文密码
- ⚠️ 依赖手动执行脚本生成密码
- ⚠️ 密码文件未加密存储

### 4. ArgoCD 密码管理

**当前状态**:
- **密码类型**: 3 个密钥
- **存储位置**: Kubernetes Secret
- **管理方式**: 占位符 + 手动配置
- **优势**:
  - ✅ 使用 Kubernetes Secret 存储
  - ✅ Gitea Token 已实际生成并配置

**当前配置**:
```yaml
# deploy/kubernetes/argocd/gitea-credentials.yaml
apiVersion: v1
kind: Secret
metadata:
  name: argocd-gitea-creds
  namespace: argocd
type: Opaque
stringData:
  username: gitea_admin
  password: "1f182aca3d38b66f7e49c034d98fb15bf02434b7"  # 实际 Token
  insecure: "true"
```

**风险点**:
- ⚠️ Token 以明文形式存在于 YAML 文件
- ⚠️ 使用 `insecure: "true"` 信任自签名证书
- ⚠️ 初始密码从 Secret 获取但未自动轮换

### 5. Docker/Container 密码管理

**当前状态**:
- **密码类型**: 2 个密钥 (MinIO, PostgreSQL)
- **存储位置**: Docker Compose 环境变量
- **管理方式**: .env 文件
- **风险点**:
  - 🔴 .env 文件可能提交到 git
  - 🔴 明文存储在 docker-compose.yml
  - 🔴 无访问控制

**当前配置**:
```yaml
# docker/docker-compose.prod.yml
services:
  postgres:
    environment:
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
  minio:
    environment:
      - MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
```

---

## 🏆 宗师级解决方案

### 架构设计原则

```
┌─────────────────────────────────────────────────────────────────┐
│                    密码统一管理架构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │  密码生成器   │────▶│  密码存储库   │────▶│  密码注入器   │   │
│  │  Generator   │     │   Vault      │     │   Injector   │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│         │                   │                   │              │
│         ▼                   ▼                   ▼              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │  复杂度验证   │     │  加密存储     │     │  自动轮换     │   │
│  │  Validator   │     │   Encrypt    │     │   Rotator    │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 核心组件

#### 1. 统一密码生成器 (Unified Password Generator)

**功能**:
- 生成符合复杂度要求的密码
- 支持多种密码格式 (Base64, Hex, URL-safe)
- 自动验证密码强度
- 生成密码审计日志

**实现**:
```bash
#!/bin/bash
# scripts/security/unified-password-generator.sh

generate_password() {
    local length=${1:-32}
    local type=${2:-all}  # all, alphanumeric, base64, hex

    case $type in
        all)
            openssl rand -base64 $length | \
            tr -dc 'A-Za-z0-9!@#$%^&*' | head -c $length
            ;;
        base64)
            openssl rand -base64 $length
            ;;
        hex)
            openssl rand -hex $length
            ;;
        alphanumeric)
            openssl rand -base64 $length | \
            tr -dc 'A-Za-z0-9' | head -c $length
            ;;
    esac
}

validate_password() {
    local password=$1
    local min_length=${2:-12}

    # 检查长度
    if [[ ${#password} -lt $min_length ]]; then
        echo "❌ 密码长度不足 $min_length 位"
        return 1
    fi

    # 检查大写字母
    if ! [[ $password =~ [A-Z] ]]; then
        echo "❌ 密码必须包含大写字母"
        return 1
    fi

    # 检查小写字母
    if ! [[ $password =~ [a-z] ]]; then
        echo "❌ 密码必须包含小写字母"
        return 1
    fi

    # 检查数字
    if ! [[ $password =~ [0-9] ]]; then
        echo "❌ 密码必须包含数字"
        return 1
    fi

    # 检查特殊字符
    if ! [[ $password =~ [!@#$%^&*] ]]; then
        echo "❌ 密码必须包含特殊字符"
        return 1
    fi

    echo "✅ 密码验证通过"
    return 0
}
```

#### 2. 密码存储库 (Password Vault)

**推荐方案**: HashiCorp Vault (生产环境)

**架构**:
```
┌─────────────────────────────────────────────────────────┐
│                    HashiCorp Vault                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  Gitea      │  │  Harbor     │  │  ArgoCD     │    │
│  │  Secrets    │  │  Secrets    │  │  Secrets    │    │
│  └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  K3S        │  │  Docker     │  │  Database   │    │
│  │  Config     │  │  Config     │  │  Config     │    │
│  └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │          Audit Log (所有访问记录)                │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**部署配置**:
```yaml
# deploy/kubernetes/vault/vault-values.yaml
server:
  dev:
    enabled: false  # 生产环境禁用 dev 模式

  ha:
    enabled: true
    raft:
      enabled: true
      config: |
        ui = true
        listener "tcp" {
          address = "0.0.0.0:8200"
          tls_disable = false
          tls_cert_file = "/vault/tls/tls.crt"
          tls_key_file = "/vault/tls/tls.key"
        }
        storage "raft" {
          path = "/vault/data"
        }

  extraEnvironmentVars:
    VAULT_LOG_LEVEL: "info"
    VAULT_MAX_LEASE_TTL: "87600h"  # 10 年
```

#### 3. 密码注入器 (Secret Injector)

**功能**: 从 Vault 自动注入密码到 Kubernetes Secret

**实现**: External Secrets Operator

```yaml
# deploy/kubernetes/external-secrets/external-secret-gitea.yaml
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
        key: sisys/gitea
        property: username
    - secretKey: password
      remoteRef:
        key: sisys/gitea
        property: admin_password
```

#### 4. 自动轮换器 (Auto Rotator)

**功能**: 定期自动轮换密码

**实现**:
```yaml
# deploy/kubernetes/vault/password-rotation-policy.yaml
apiVersion: secrets.hashicorp.com/v1alpha1
kind: StaticAccount
metadata:
  name: gitea-admin-password
  namespace: vault
spec:
  mount: secret
  role: gitea-admin
  targetSecret:
    name: gitea-admin-secret
    namespace: gitea
  rotationSchedule: "0 0 1 * *"  # 每月 1 日轮换
  rotationWindow: 24h
```

---

## 📋 实施方案

### 阶段 1: 立即实施 (本周)

**目标**: 解决当前高风险问题

| 任务 | 优先级 | 负责人 | 预计时间 |
|------|-------|--------|---------|
| 1. 删除所有明文密码文件 | P0 | DevOps | 1 小时 |
| 2. 配置 .gitignore 排除所有 Secret 文件 | P0 | DevOps | 30 分钟 |
| 3. 使用 sops 加密现有 Secret YAML | P0 | DevOps | 2 小时 |
| 4. 配置 kubeconfig 文件权限 (600) | P0 | DevOps | 30 分钟 |
| 5. 创建密码管理策略文档 | P1 | 安全团队 | 4 小时 |

**实施步骤**:

```bash
# 1. 删除明文密码文件
find . -name "*credentials*.txt" -o -name "*password*.txt" | xargs shred -u

# 2. 配置 .gitignore
cat >> .gitignore << 'EOF'

# Secrets
.secrets/
*.secret.yaml
*-secret.yaml
!*.secret.example.yaml
credentials.txt
*.credentials
.env
!.env.example
EOF

# 3. 使用 sops 加密
sops -e deploy/kubernetes/harbor/secrets-example.yaml > deploy/kubernetes/harbor/secrets.enc.yaml
shred -u deploy/kubernetes/harbor/secrets-example.yaml

# 4. 配置 kubeconfig 权限
chmod 600 ~/.kube/config
chmod 600 /etc/rancher/k3s/k3s.yaml
```

### 阶段 2: 短期实施 (2 周内)

**目标**: 建立统一的密码管理基础设施

| 任务 | 优先级 | 负责人 | 预计时间 |
|------|-------|--------|---------|
| 1. 部署 HashiCorp Vault | P0 | DevOps | 1 天 |
| 2. 安装 External Secrets Operator | P0 | DevOps | 4 小时 |
| 3. 迁移所有 Secret 到 Vault | P0 | DevOps | 2 天 |
| 4. 配置自动轮换策略 | P1 | DevOps | 1 天 |
| 5. 配置审计日志 | P1 | 安全团队 | 4 小时 |

**Vault 初始化脚本**:

```bash
#!/bin/bash
# scripts/security/init-vault.sh

set -euo pipefail

# 1. 初始化 Vault
vault operator init -key-shares=5 -key-threshold=3 > vault-init.output

# 2. 保存 unseal keys (应存储到安全的密码管理器)
grep "Unseal Key" vault-init.output > vault-unseal-keys.txt
chmod 400 vault-unseal-keys.txt

# 3. Unseal Vault
vault operator unseal  # 需要 3 个不同的 unseal key

# 4. 登录
export VAULT_ADDR='https://vault.sisys.local:8200'
vault login

# 5. 启用 KV Secrets Engine
vault secrets enable -path=sisys kv-v2

# 6. 创建 Gitea 策略
vault policy write gitea-policy - <<EOF
path "secret/data/sisys/gitea/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "secret/metadata/sisys/gitea/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
EOF

# 7. 创建 AppRole
vault auth enable approle
vault write auth/approle/role/gitea-role \
    token_policies="gitea-policy" \
    token_ttl=1h \
    token_max_ttl=4h
```

### 阶段 3: 中期实施 (1 个月内)

**目标**: 完善密码管理流程和工具

| 任务 | 优先级 | 负责人 | 预计时间 |
|------|-------|--------|---------|
| 1. 开发统一密码生成 CLI 工具 | P1 | 开发团队 | 3 天 |
| 2. 集成到 CI/CD 流水线 | P1 | DevOps | 2 天 |
| 3. 配置密码复杂度策略 | P1 | 安全团队 | 1 天 |
| 4. 实施密码访问审计 | P1 | 安全团队 | 2 天 |
| 5. 创建密码管理培训材料 | P2 | 安全团队 | 1 天 |

**统一密码 CLI 工具**:

```python
#!/usr/bin/env python3
# scripts/security/password-cli.py

import argparse
import secrets
import string
import json
import sys
from pathlib import Path

def generate_password(length=32, use_special=True):
    """生成符合复杂度要求的密码"""
    alphabet = string.ascii_letters + string.digits
    if use_special:
        alphabet += "!@#$%^&*"

    # 确保包含所有字符类型
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
    ]
    if use_special:
        password.append(secrets.choice("!@#$%^&*"))

    # 填充剩余长度
    password += [secrets.choice(alphabet) for _ in range(length - len(password))]

    # 打乱顺序
    secrets.SystemRandom().shuffle(password)

    return ''.join(password)

def validate_password(password, min_length=12):
    """验证密码复杂度"""
    errors = []

    if len(password) < min_length:
        errors.append(f"密码长度不足 {min_length} 位")

    if not any(c.isupper() for c in password):
        errors.append("密码必须包含大写字母")

    if not any(c.islower() for c in password):
        errors.append("密码必须包含小写字母")

    if not any(c.isdigit() for c in password):
        errors.append("密码必须包含数字")

    if not any(c in "!@#$%^&*" for c in password):
        errors.append("密码必须包含特殊字符 (!@#$%^&*)")

    return errors

def main():
    parser = argparse.ArgumentParser(description='统一密码管理 CLI')
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # generate 命令
    gen_parser = subparsers.add_parser('generate', help='生成密码')
    gen_parser.add_argument('-l', '--length', type=int, default=32, help='密码长度')
    gen_parser.add_argument('--no-special', action='store_true', help='不包含特殊字符')
    gen_parser.add_argument('-c', '--count', type=int, default=1, help='生成数量')
    gen_parser.add_argument('--validate', action='store_true', help='生成后验证')

    # validate 命令
    val_parser = subparsers.add_parser('validate', help='验证密码')
    val_parser.add_argument('password', help='要验证的密码')
    val_parser.add_argument('-m', '--min-length', type=int, default=12, help='最小长度')

    # store 命令
    store_parser = subparsers.add_parser('store', help='存储密码到 Vault')
    store_parser.add_argument('--system', required=True, help='系统名称 (gitea/harbor/argocd)')
    store_parser.add_argument('--key', required=True, help='密钥名称')
    store_parser.add_argument('--value', help='密码值 (不指定则从 stdin 读取)')

    args = parser.parse_args()

    if args.command == 'generate':
        for i in range(args.count):
            password = generate_password(args.length, not args.no_special)
            if args.validate:
                errors = validate_password(password)
                if errors:
                    print(f"❌ 密码验证失败：{', '.join(errors)}", file=sys.stderr)
                    sys.exit(1)
                print(f"✅ 密码验证通过")
            print(password)

    elif args.command == 'validate':
        errors = validate_password(args.password, args.min_length)
        if errors:
            print(f"❌ 密码验证失败：{', '.join(errors)}")
            sys.exit(1)
        print("✅ 密码验证通过")

    elif args.command == 'store':
        # TODO: 集成 Vault API
        print(f"存储密码到 Vault: {args.system}/{args.key}")

if __name__ == '__main__':
    main()
```

### 阶段 4: 长期实施 (3 个月内)

**目标**: 建立完整的密码治理体系

| 任务 | 优先级 | 负责人 | 预计时间 |
|------|-------|--------|---------|
| 1. 实施零信任架构 | P2 | 安全团队 | 2 周 |
| 2. 配置异常检测告警 | P2 | 安全团队 | 1 周 |
| 3. 实施密码使用分析 | P2 | 安全团队 | 1 周 |
| 4. 定期渗透测试 | P2 | 外部团队 | 每季度 |
| 5. 合规审计 (等保 2.0/SOX) | P1 | 合规团队 | 持续 |

---

## 🔐 密码策略

### 复杂度要求

| 系统 | 最小长度 | 大写字母 | 小写字母 | 数字 | 特殊字符 | 历史记录 | 过期天数 |
|------|---------|---------|---------|------|---------|---------|---------|
| **K3S** | 32 | ✅ | ✅ | ✅ | ✅ | N/A | 365 |
| **Gitea** | 12 | ✅ | ✅ | ✅ | ✅ | 5 | 90 |
| **Harbor** | 12 | ✅ | ✅ | ✅ | ✅ | 5 | 90 |
| **ArgoCD** | 12 | ✅ | ✅ | ✅ | ✅ | 5 | 90 |
| **Database** | 16 | ✅ | ✅ | ✅ | ✅ | 10 | 60 |
| **Docker** | 16 | ✅ | ✅ | ✅ | ✅ | N/A | 90 |

### 密码生成规则

```yaml
# 密码策略配置 (统一)
password_policy:
  # 基础要求
  min_length: 12
  max_length: 128

  # 字符类型要求
  require_uppercase: true
  require_lowercase: true
  require_digits: true
  require_special: true
  special_characters: "!@#$%^&*"

  # 复杂度要求
  min_unique_chars: 4  # 至少包含 4 种字符类型
  min_entropy_bits: 60  # 最小熵

  # 历史记录
  password_history_count: 5  # 不得重复最近 5 次密码

  # 过期策略
  password_expiration_days: 90
  password_expiration_warning_days: 7  # 提前 7 天警告

  # 锁定策略
  max_failed_attempts: 5  # 最大失败尝试次数
  lockout_duration_minutes: 30  # 锁定时长
```

---

## 📊 监控与审计

### 审计日志格式

```json
{
  "timestamp": "2026-03-18T10:30:00Z",
  "event_type": "secret_access",
  "actor": {
    "type": "service_account",
    "name": "argocd-repo-server",
    "namespace": "argocd"
  },
  "target": {
    "system": "gitea",
    "secret_name": "gitea-admin-secret",
    "field": "password"
  },
  "action": "read",
  "result": "success",
  "metadata": {
    "ip_address": "10.42.0.15",
    "user_agent": "vault-client/1.0",
    "request_id": "req-123456"
  }
}
```

### 告警规则

| 告警名称 | 触发条件 | 严重性 | 响应时间 |
|---------|---------|-------|---------|
| 密码泄露嫌疑 | 同一密码 5 次失败访问 | 🔴 P0 | 15 分钟 |
| 异常密码访问 | 非工作时间访问 Secret | 🟡 P1 | 1 小时 |
| 密码即将过期 | 密码剩余有效期 < 7 天 | 🟢 P2 | 24 小时 |
| 未授权访问尝试 | 无权限访问 Secret | 🔴 P0 | 15 分钟 |
| 密码强度不足 | 新密码不符合策略 | 🟡 P1 | 1 小时 |

---

## 📚 最佳实践

### 1. 密码存储

✅ **应该**:
- 使用 Kubernetes Secret 存储运行时密码
- 使用 HashiCorp Vault 存储主密码
- 使用 sops 加密静态 Secret 文件
- 定期轮换密码 (90 天)

❌ **不应该**:
- 在 git 中存储明文密码
- 在代码中硬编码密码
- 通过明文传输密码 (使用 HTTPS/TLS)
- 共享密码 (每人/服务独立密码)

### 2. 密码传输

✅ **应该**:
- 使用 TLS 1.3 加密传输
- 使用 Kubernetes Secret 注入
- 使用 Vault Agent 自动注入

❌ **不应该**:
- 通过邮件/聊天工具发送密码
- 在日志中打印密码
- 通过 URL 参数传递密码

### 3. 密码轮换

✅ **应该**:
- 定期自动轮换 (90 天)
- 离职人员立即回收权限
- 密码泄露时立即轮换
- 保留密码历史记录

❌ **不应该**:
- 使用相同密码超过 1 年
- 轮换后不更新所有系统
- 不测试新密码就轮换

---

## 🧪 验证测试

### 密码策略测试

```python
# tests/security/test_password_policy.py

import pytest
import subprocess
import re

class TestPasswordPolicy:
    """密码策略验证测试"""

    def test_password_length(self):
        """测试密码最小长度"""
        result = subprocess.run(
            ['scripts/security/password-cli.py', 'generate', '-l', '12'],
            capture_output=True, text=True
        )
        password = result.stdout.strip()
        assert len(password) >= 12, "密码长度不足 12 位"

    def test_password_complexity(self):
        """测试密码复杂度"""
        result = subprocess.run(
            ['scripts/security/password-cli.py', 'generate'],
            capture_output=True, text=True
        )
        password = result.stdout.strip()

        assert re.search(r'[A-Z]', password), "缺少大写字母"
        assert re.search(r'[a-z]', password), "缺少小写字母"
        assert re.search(r'[0-9]', password), "缺少数字"
        assert re.search(r'[!@#$%^&*]', password), "缺少特殊字符"

    def test_gitea_secrets_no_plaintext(self):
        """验证 Gitea Secret 无明文密码"""
        with open('deploy/kubernetes/gitea/secrets.yaml') as f:
            content = f.read()

        # 应该使用占位符
        assert '${GITEA_ADMIN_PASSWORD}' in content
        # 不应该有明文密码
        assert not re.search(r'password:\s*["\'][A-Za-z0-9]+["\']', content)

    def test_harbor_secrets_encrypted(self):
        """验证 Harbor Secret 已加密"""
        # 应该存在加密文件
        assert Path('deploy/kubernetes/harbor/secrets.enc.yaml').exists()

        # 加密文件应包含 sops 元数据
        with open('deploy/kubernetes/harbor/secrets.enc.yaml') as f:
            content = f.read()
        assert 'sops:' in content
```

### 架构合规测试

```python
# tests/security/test_password_architecture.py

import pytest
import kubernetes
import os

class TestPasswordArchitecture:
    """密码管理架构验证测试"""

    @pytest.fixture
    def k8s_client(self):
        """初始化 Kubernetes 客户端"""
        kubernetes.config.load_kube_config()
        return kubernetes.client.CoreV1Api()

    def test_secrets_use_kubernetes_secret(self, k8s_client):
        """验证所有系统使用 Kubernetes Secret"""
        namespaces = ['gitea', 'harbor', 'argocd']

        for ns in namespaces:
            secrets = k8s_client.list_namespaced_secret(namespace=ns)
            assert len(secrets.items) > 0, f"{ns} 命名空间没有 Secret"

    def test_no_configmap_contains_password(self, k8s_client):
        """验证 ConfigMap 不包含密码"""
        namespaces = ['gitea', 'harbor', 'argocd']
        password_patterns = ['password', 'secret', 'token', 'key']

        for ns in namespaces:
            configmaps = k8s_client.list_namespaced_configmap(namespace=ns)
            for cm in configmaps.items:
                for key, value in cm.data.items():
                    for pattern in password_patterns:
                        assert pattern.lower() not in key.lower(), \
                            f"ConfigMap {cm.name}/{key} 可能包含敏感信息"

    def test_kubeconfig_permissions(self):
        """验证 kubeconfig 文件权限"""
        kubeconfig_paths = [
            os.path.expanduser('~/.kube/config'),
            '/etc/rancher/k3s/k3s.yaml'
        ]

        for path in kubeconfig_paths:
            if os.path.exists(path):
                mode = os.stat(path).st_mode & 0o777
                assert mode == 0o600, f"{path} 权限应为 600, 实际为 {oct(mode)}"
```

---

## 📖 参考文档

### 内部文档

- [Gitea Secrets 管理指南](../deployment/GITEA_SECRETS_GUIDE.md)
- [Harbor 密码生成脚本](../../scripts/security/generate-harbor-secrets.sh)
- [ArgoCD 安全加固配置](../../deploy/kubernetes/argocd/security-hardening.yaml)
- [K3S 部署指南](../deployment/K3S_DEPLOYMENT_GUIDE.md)

### 外部资源

- [HashiCorp Vault 官方文档](https://www.vaultproject.io/docs)
- [External Secrets Operator](https://external-secrets.io/)
- [Mozilla sops 加密工具](https://github.com/mozilla/sops)
- [Kubernetes Secrets 最佳实践](https://kubernetes.io/docs/concepts/configuration/secret/)
- [OWASP 密码存储指南](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)

---

## 📝 变更日志

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|---------|
| v1.0 | 2026-03-18 | AI 宗师级开发者 | 初始版本，基于 Story 0.4-0.7 分析 |

---

## ✅ 检查清单

### 立即可执行

- [ ] 删除所有明文密码文件
- [ ] 配置 .gitignore 排除 Secret 文件
- [ ] 使用 sops 加密现有 Secret YAML
- [ ] 配置 kubeconfig 文件权限 (600)

### 本周执行

- [ ] 部署 HashiCorp Vault
- [ ] 安装 External Secrets Operator
- [ ] 迁移所有 Secret 到 Vault
- [ ] 配置自动轮换策略

### 本月执行

- [ ] 开发统一密码生成 CLI 工具
- [ ] 集成到 CI/CD 流水线
- [ ] 配置密码复杂度策略
- [ ] 实施密码访问审计

### 本季度执行

- [ ] 实施零信任架构
- [ ] 配置异常检测告警
- [ ] 实施密码使用分析
- [ ] 定期渗透测试

---

**文档结束**
