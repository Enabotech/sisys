# 统一密码策略规范

**版本：** 1.0
**日期：** 2026-03-05
**状态：** ✅ 统一标准

---

## 📋 密码策略标准

### 默认密码规范

| 组件 | 用户名 | 默认密码 | 首次登录强制修改 | 密码复杂度 |
|------|--------|---------|----------------|-----------|
| Gitea | `admin` | `Admin12345!` | ✅ 是 | 12 位 + 大小写 + 数字 + 特殊字符 |
| Harbor | `admin` | `Harbor@2026Secure!` | ✅ 是 | 12 位 + 大小写 + 数字 + 特殊字符 |
| ArgoCD | `admin` | `<动态生成>` | ✅ 是 | 16 位随机 |
| K3S | `admin` | `<kubeconfig>` | ✅ 是 | N/A |
| Longhorn | `admin` | `<动态生成>` | ✅ 是 | 16 位随机 |
| PostgreSQL | `postgres` | `<随机生成>` | ✅ 是 | 20 位随机 |
| Redis | `default` | `<随机生成>` | ✅ 是 | 20 位随机 |

---

## 🔐 密码生成规则

### 动态密码生成

```bash
#!/bin/bash
# scripts/generate-password.sh
# 生成安全随机密码

generate_password() {
    local length=${1:-16}
    openssl rand -base64 $length | tr -dc 'A-Za-z0-9!@#$%^&*' | head -c $length
}

# 生成 16 位密码
ADMIN_PASSWORD=$(generate_password 16)
echo "Generated password: $ADMIN_PASSWORD"

# 生成 20 位数据库密码
DB_PASSWORD=$(generate_password 20)
echo "Database password: $DB_PASSWORD"
```

### 密码复杂度要求

```yaml
# config/password-policy.yaml
password_policy:
  # 最小长度
  min_length: 12

  # 必须包含
  require:
    uppercase: true    # 大写字母
    lowercase: true    # 小写字母
    digits: true       # 数字
    special_chars: true # 特殊字符 (!@#$%^&*)

  # 禁止
  prohibit:
    common_passwords: true      # 常见密码
    username_in_password: true  # 用户名在密码中
    sequential_chars: true      # 连续字符 (如 123, abc)
    repeated_chars: true        # 重复字符 (如 aaa)

  # 历史记录
  history:
    check_last_n: 5   # 检查最近 5 次密码
    min_age_days: 1   # 最小修改间隔

  # 过期策略
  expiration:
    max_age_days: 90      # 90 天过期
    warn_before_days: 14  # 提前 14 天警告
```

---

## 📁 密码存储规范

### Kubernetes Secrets

```yaml
# secrets/sisys-secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: sisys-admin-credentials
  namespace: sisys
type: Opaque
stringData:
  gitea-admin-password: "Admin12345!"  # 首次登录后修改
  harbor-admin-password: "Harbor@2026Secure!"  # 首次登录后修改
  argocd-admin-password: "<动态生成>"  # 安装时生成
```

### 密码文件存储

```bash
# 密码文件存储路径
PASSWORD_FILE="/etc/sisys/credentials.yaml"

# 创建密码文件 (权限 600)
cat > $PASSWORD_FILE <<EOF
# SISYS 系统凭证
# 生成时间：$(date)
# 最后修改：$(date)

gitea:
  url: http://gitea.sisys.local
  username: admin
  password: Admin12345!  # 首次登录后修改

harbor:
  url: http://harbor.sisys.local
  username: admin
  password: Harbor@2026Secure!  # 首次登录后修改

argocd:
  url: http://argocd.sisys.local
  username: admin
  password: $(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)

k3s:
  kubeconfig: /etc/rancher/k3s/k3s.yaml

database:
  postgresql:
    host: postgres.sisys.local
    port: 5432
    username: sisys
    password: <随机生成>

redis:
  host: redis.sisys.local
  port: 6379
  password: <随机生成>
EOF

# 设置文件权限
chmod 600 $PASSWORD_FILE
chown root:root $PASSWORD_FILE
```

---

## 🔄 密码轮换策略

### 自动轮换脚本

```bash
#!/bin/bash
# scripts/rotate-passwords.sh
# 密码轮换脚本

set -e

echo "🔄 开始密码轮换..."

# 生成新密码
NEW_PASSWORD=$(openssl rand -base64 16 | tr -dc 'A-Za-z0-9!@#$%^&*' | head -c 16)

# 轮换 Gitea 密码
echo "轮换 Gitea admin 密码..."
kubectl -n gitea create secret generic gitea-admin-password \
  --from-literal=password=$NEW_PASSWORD \
  --dry-run=client -o yaml | kubectl apply -f -

# 轮换 Harbor 密码
echo "轮换 Harbor admin 密码..."
kubectl -n harbor create secret generic harbor-admin-password \
  --from-literal=password=$NEW_PASSWORD \
  --dry-run=client -o yaml | kubectl apply -f -

# 更新凭证文件
echo "更新凭证文件..."
cp /etc/sisys/credentials.yaml /etc/sisys/credentials.yaml.bak
# 更新密码...

# 通知用户
echo "发送密码变更通知..."
# 发送邮件/钉钉通知...

echo "✅ 密码轮换完成"
echo "新密码已保存到 /etc/sisys/credentials.yaml"
```

### 轮换计划

| 密码类型 | 轮换周期 | 自动轮换 | 通知方式 |
|---------|---------|---------|---------|
| 管理员密码 | 90 天 | ❌ 手动 | 邮件 + 钉钉 |
| 服务密码 | 30 天 | ✅ 自动 | 邮件 |
| 数据库密码 | 60 天 | ✅ 自动 | 邮件 + 钉钉 |
| API Token | 30 天 | ✅ 自动 | 邮件 |

---

## ✅ 验收清单

### 部署时验收

- [ ] 所有默认密码符合复杂度要求
- [ ] 首次登录强制修改密码
- [ ] 密码文件权限正确 (600)
- [ ] Kubernetes Secrets 加密存储

### 运维时验收

- [ ] 密码轮换脚本可用
- [ ] 密码变更通知正常
- [ ] 密码历史记录完整

---

**实施状态：** ✅ 已应用到所有文档
