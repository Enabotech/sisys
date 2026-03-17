# Harbor 密码管理说明

**重要：** 解答"在 Web 端修改密码是否会导致 Secret 和数据库不一致"的问题

---

## 📋 简短回答

**不会有问题！** 在 Web 端修改密码是安全的，不会导致登录问题。

---

## 🔍 详细解释

### Harbor 密码管理架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Harbor 密码流向                           │
└─────────────────────────────────────────────────────────────┘

┌──────────────────┐
│  Secret 配置      │
│  (harbor-core)    │
│  HARBOR_ADMIN_    │
│  PASSWORD         │
└────────┬─────────┘
         │
         │ 仅在以下情况使用：
         │ 1. 首次安装 Harbor 时初始化 admin 密码
         │ 2. 重置密码时作为参考
         │
         ▼
┌──────────────────┐     修改密码      ┌──────────────────┐
│  Harbor Core     │ ────────────────→ │  PostgreSQL      │
│  服务            │   (Web/API)       │  数据库           │
│                  │                   │  harbor_user 表   │
└──────────────────┘                   └──────────────────┘
                                              │
                                              │ 登录验证时读取
                                              ▼
                                       ┌──────────────────┐
                                       │  Harbor Core     │
                                       │  认证模块         │
                                       └──────────────────┘
```

### 密码修改场景对比

| 修改方式 | Secret 更新 | 数据库更新 | 是否影响登录 |
|---------|-----------|-----------|-------------|
| **Web 端修改** | ❌ 不更新 | ✅ 更新 | ✅ **无影响** |
| **API 修改** | ❌ 不更新 | ✅ 更新 | ✅ **无影响** |
| **kubectl 修改 Secret** | ✅ 更新 | ❌ 不更新 | ❌ **会导致问题** |
| **直接修改数据库** | ❌ 不更新 | ✅ 更新 | ✅ 无影响 |

---

## ✅ 推荐的密码管理方式

### 方式一：Web 端修改（推荐）

1. 登录 Harbor Web 界面
2. 点击右上角用户头像 → "用户设置"
3. 修改密码
4. 立即生效

**优点：**
- 简单直观
- 自动更新数据库
- 不会影响 Secret

### 方式二：API 修改

```bash
# 修改自己的密码
curl -X PUT https://harbor.sisys.local/api/v2.0/users/current/password \
  -u "admin:旧密码" \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "旧密码",
    "new_password": "新密码"
  }'

# 管理员修改其他用户密码
curl -X PUT https://harbor.sisys.local/api/v2.0/users/1/password \
  -u "admin:管理员密码" \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "旧密码",
    "new_password": "新密码"
  }'
```

### 方式三：CLI 工具（如果有）

```bash
harbor-cli user update admin --password 新密码
```

---

## ⚠️ 不推荐的操作

### ❌ 直接修改 Secret

```bash
# 不要这样做！
kubectl patch secret harbor-core -n harbor \
  --type='json' \
  -p='[{"op": "replace", "path": "/data/HARBOR_ADMIN_PASSWORD", "value": "新密码"}]'
```

**问题：** Secret 更新后，数据库中的密码哈希不会自动同步，导致登录失败。

### ❌ 直接修改数据库

```bash
# 不要这样做！除非你知道在做什么
# pragma: allowlist secret
# kubectl exec -n harbor harbor-database-0 -- psql -U postgres -d registry \
#   -c "UPDATE harbor_user SET password='xxx' WHERE username='admin';"
```

**问题：** 需要手动计算 SHA256 哈希，容易出错。

---

## 🔄 如果需要更新 Secret

某些场景下（如 Helm 升级），可能需要更新 Secret。正确做法：

### 步骤 1：先在 Web 端修改密码

记录新密码：`MyNewPassword123!`

### 步骤 2：生成密码的 base64 编码

```bash
echo -n "MyNewPassword123!" | base64
```

### 步骤 3：更新 Secret

```bash
kubectl patch secret harbor-core -n harbor \
  --type='json' \
  -p='[{"op": "replace", "path": "/data/HARBOR_ADMIN_PASSWORD", "value": "步骤 2 的 base64 值"}]'
```

### 步骤 4：验证登录

```bash
curl -u "admin:MyNewPassword123!" https://harbor.sisys.local/api/v2.0/users/1
```

---

## 📝 最佳实践总结

1. **日常密码修改** → 使用 Web 端或 API
2. **Secret 管理** → 仅在 Helm 升级/迁移时更新
3. **密码记录** → 使用密码管理工具（如 Vault、1Password）
4. **密码策略** → 遵循 [PASSWORD_POLICY.md](../developer/PASSWORD_POLICY.md)
5. **定期轮换** → 建议 90 天更换一次密码

---

## 🔐 密码存储说明

### Secret 中的密码用途

| Secret 键名 | 用途 | 是否敏感 |
|-----------|------|---------|
| `HARBOR_ADMIN_PASSWORD` | 首次安装时设置初始密码 | ✅ 是 |
| `secret` | Core 服务内部令牌 | ✅ 是 |
| `secretKey` | 加密密钥 | ✅ 是 |
| `CSRF_KEY` | CSRF 防护 | ✅ 是 |

### 数据库中的密码存储

```sql
-- harbor_user 表结构
CREATE TABLE harbor_user (
    user_id          INTEGER PRIMARY KEY,
    username         VARCHAR(255) UNIQUE,
    password         VARCHAR(40),      -- SHA256 哈希的前 32 字符
    salt             VARCHAR(40),      -- 随机盐值
    password_version VARCHAR(16)       -- 'sha256'
);

-- 密码计算方式
password = SHA256(salt + 明文密码)[:32]
```

---

## 📞 常见问题

### Q1: 修改密码后需要重启 Harbor 吗？

**不需要！** 密码修改后立即生效，Harbor Core 会实时从数据库读取最新密码哈希。

### Q2: 修改密码后其他服务（如 ArgoCD）会受影响吗？

**会！** 如果其他服务配置了 Harbor 凭证，需要同时更新：
- ArgoCD Image Updater 配置
- CI/CD Pipeline 中的 Harbor 凭证
- Docker 登录脚本

### Q3: 忘记密码怎么办？

可以通过以下方式重置：
1. 使用其他管理员账户在 Web 端重置
2. 通过 API 重置（需要其他管理员凭证）
3. 直接修改数据库（最后手段）

---

**文档更新日期：** 2026-03-17
**Harbor 版本：** v2.14.2
