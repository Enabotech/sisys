# ⚡ 快速修复：build-dependency-image 工作流失败

## 🔴 问题诊断

根据错误日志：
```
expression evaluated to '%!t(string=/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel)'
```

**原因**: `vars.HARBOR_REGISTRY` 为空，导致 URL 缺少域名

---

## ✅ 解决方案（5 分钟）

### 步骤 1: 登录 Gitea

```bash
# 浏览器访问
https://gitea.sisys.local

# 使用管理员账号
用户名：gitea_admin
密码：Admin@123456
```

### 步骤 2: 进入仓库设置

1. 导航到您的仓库（例如：`agimtech/sisys`）
2. 点击顶部菜单的 **设置**
3. 选择左侧的 **Actions** → **变量**

### 步骤 3: 添加 Variables

点击 **"新建变量"**，添加以下 2 个变量：

#### Variable 1: HARBOR_REGISTRY
```
名称：HARBOR_REGISTRY
值：harbor.sisys.local
```

#### Variable 2: HARBOR_PROJECT
```
名称：HARBOR_PROJECT
值：sisys
```

### 步骤 4: 添加 Secrets

点击 **"新建机密"**，添加以下 2 个密钥：

#### Secret 1: HARBOR_ROBOT_USERNAME
```
名称：HARBOR_ROBOT_USERNAME
值：robot$sisys+gitea-runner-push
```

#### Secret 2: HARBOR_ROBOT_PASSWORD
```
名称：HARBOR_ROBOT_PASSWORD
值：gXuC2AcG1231JB8mfZmyCnhDKy6nKcRd
```

### 步骤 5: 验证配置

配置完成后，变量列表应该显示：

| 类型 | 名称 | 值 |
|------|------|-----|
| Variable | `HARBOR_REGISTRY` | `harbor.sisys.local` |
| Variable | `HARBOR_PROJECT` | `sisys` |
| Secret | `HARBOR_ROBOT_USERNAME` | `********` |
| Secret | `HARBOR_ROBOT_PASSWORD` | `********` |

### 步骤 6: 重新运行工作流

1. 访问：`https://gitea.sisys.local/{您的仓库}/actions`
2. 点击左侧的 **Build Dependency Image**
3. 点击 **"Run workflow"** 按钮
4. 选择分支：`main`
5. 点击 **"Run workflow"**

---

## 🔍 验证日志

工作流启动后，检查日志应该显示：

```
✅ 正确:
expression evaluated to 'harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel'

❌ 错误 (之前):
expression evaluated to '%!t(string=/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel)'
```

---

## 🛠️ 可选：运行验证脚本

```bash
# 运行验证脚本检查配置
./scripts/ci/verify-variables.sh
```

---

## 📊 完整配置清单

### Gitea Variables (仓库级别)

| 名称 | 值 | 位置 |
|------|-----|------|
| `HARBOR_REGISTRY` | `harbor.sisys.local` | Settings → Actions → Variables |
| `HARBOR_PROJECT` | `sisys` | Settings → Actions → Variables |
| `GPU_ENABLED` | `false` | Settings → Actions → Variables (可选) |

### Gitea Secrets (仓库级别)

| 名称 | 值 | 位置 |
|------|-----|------|
| `HARBOR_ROBOT_USERNAME` | `robot$sisys+gitea-runner-push` | Settings → Actions → Secrets |
| `HARBOR_ROBOT_PASSWORD` | `gXuC2AcG1231JB8mfZmyCnhDKy6nKcRd` | Settings → Actions → Secrets |

---

## ❓ 常见问题

### Q1: Variables 和 Secrets 有什么区别？

- **Variables**: 非敏感配置，可以在日志中看到
- **Secrets**: 敏感信息，会被加密存储和显示为 `***`

### Q2: 配置后仍然失败？

1. 确认变量名**完全一致**（区分大小写）
2. 确认在**正确的仓库**配置（不是组织级别）
3. 等待 1-2 分钟让配置生效
4. 重新运行工作流（不是重新运行失败的任务）

### Q3: 如何查看完整的错误日志？

```bash
# 在 Gitea UI 中:
1. Actions → 选择失败的工作流
2. 点击失败的任务（如 "📦 构建依赖镜像"）
3. 展开日志查看完整输出
```

---

## 📞 需要帮助？

如果按照以上步骤仍然无法解决，请提供：

1. Gitea Variables 配置截图
2. 完整的工作流日志
3. 运行 `./scripts/ci/verify-variables.sh` 的输出
