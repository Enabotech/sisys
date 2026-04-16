# Gitea Runner Token 配置指南

本文档说明如何配置 Gitea Runner Token 并存储到 Kubernetes Secret。

## 前置条件

- ✅ Story 0.5: Gitea 代码托管已部署
- ✅ Gitea 管理员账号可访问
- ✅ kubectl 已配置并可访问 K3S 集群

## Task 1: Gitea Runner Token 配置

### 1.1 在 Gitea 管理页面创建 Runner Token

**步骤：**

1. 登录 Gitea 管理页面：https://gitea.sisys.local
2. 使用管理员账号登录（默认：`gitea_admin`）
3. 点击右上角头像 → **站点管理**
4. 左侧菜单选择 **设置** → **Actions**
5. 点击 **添加 Runner** 按钮
6. 填写 Runner 信息：
   - **Runner 名称**: `k8s-runner-01`
   - **Runner 标签**: `docker,k8s,standard`
   - **Runner 类型**: 组织级别（为整个站点创建）
7. 点击 **生成 Token**
8. **重要**: 复制生成的 Token（类似：`1f182aca3d38b66f7e49c034d98fb15bf02434b7`）
   - ⚠️ Token 只会显示一次，请立即保存

**权限要求：**

Runner Token 需要以下权限：
- `repo`: 读取和写入仓库
- `actions`: 读取和写入 Actions 配置

### 1.2 存储 Token 到 Kubernetes Secret

**方法 A: 使用 kubectl 命令**

```bash
# 1. 将 Token 存储到 Kubernetes Secret
kubectl create secret generic gitea-runner-token \
  --from-literal=token=YOUR_TOKEN_HERE \
  -n gitea-actions \
  --dry-run=client -o yaml | kubectl apply -f -
```

**方法 B: 使用提供的 Secret 文件**

```bash
# 1. 编辑 Secret 文件
vim deploy/kubernetes/gitea-runner/gitea-runner-token-secret.yaml

# 2. 替换 Token 占位符
# 将 'REPLACE_WITH_YOUR_GITEA_RUNNER_TOKEN' 替换为实际 Token 的 base64 编码

# 3. 生成 base64 编码
echo -n "YOUR_TOKEN_HERE" | base64

# 4. 应用 Secret
kubectl apply -f deploy/kubernetes/gitea-runner/gitea-runner-token-secret.yaml
```

**验证 Secret 创建：**

```bash
# 检查 Secret 是否存在
kubectl get secret gitea-runner-token -n gitea-actions

# 验证 Token 值（可选）
kubectl get secret gitea-runner-token -n gitea-actions \
  -o jsonpath='{.data.token}' | base64 -d
```

### 1.3 配置 Token 过期策略

**推荐配置：**

- **Token 轮换周期**: 90 天
- **提前提醒**: 7 天
- **自动轮换**: 手动审批（安全考虑）

**Token 管理最佳实践：**

1. **定期轮换**: 每 90 天更换一次 Token
2. **监控过期**: 设置提醒在到期前 7 天通知
3. **权限审计**: 每季度检查 Token 权限
4. **泄露响应**: 如 Token 泄露，立即撤销并重新生成

**Token 轮换步骤：**

```bash
# 1. 在 Gitea 管理页面撤销旧 Token
# 管理页面 → 设置 → Actions → 删除问题 Token

# 2. 生成新 Token（参考步骤 1.1）

# 3. 更新 Kubernetes Secret
kubectl create secret generic gitea-runner-token \
  --from-literal=token=NEW_TOKEN_HERE \
  -n gitea-actions \
  --dry-run=client -o yaml | kubectl apply -f -

# 4. 重启 Runner 使新 Token 生效
kubectl rollout restart deployment/gitea-runner -n gitea-actions

# 5. 验证 Runner 状态
kubectl get pods -n gitea-actions
```

### 1.4 验证 Token 权限

**验证步骤：**

```bash
# 1. 使用 Token 测试 Gitea API 连接
TOKEN=$(kubectl get secret gitea-runner-token -n gitea-actions \
  -o jsonpath='{.data.token}' | base64 -d)

curl -k -H "Authorization: token $TOKEN" \
  https://gitea.sisys.local/api/v1/admin/runners

# 预期响应：返回 Runner 列表（包含刚创建的 Runner）
```

**权限验证检查清单：**

- [ ] Token 可以访问 Gitea API
- [ ] Token 有 `repo` 权限（可读取/写入仓库）
- [ ] Token 有 `actions` 权限（可配置 Actions）
- [ ] Token 在 Gitea 管理页面显示为"活跃"状态
- [ ] Token 未过期

## 故障排除

### 问题 1: Secret 创建失败

**错误信息：**
```
Error from server (AlreadyExists): secrets "gitea-runner-token" already exists
```

**解决方案：**
```bash
# 更新现有 Secret
kubectl create secret generic gitea-runner-token \
  --from-literal=token=NEW_TOKEN_HERE \
  -n gitea-actions \
  --dry-run=client -o yaml | kubectl apply -f -
```

### 问题 2: Token 认证失败

**错误信息：**
```
authentication required: invalid token
```

**解决方案：**
1. 检查 Token 是否正确复制（无多余空格）
2. 验证 Token 在 Gitea 管理页面是否仍然活跃
3. 重新生成 Token 并更新 Secret

### 问题 3: Runner 无法连接 Gitea

**错误信息：**
```
failed to register runner: connection refused
```

**解决方案：**
```bash
# 1. 检查 Gitea 服务是否可访问
kubectl exec -n gitea-actions <runner-pod-name> -- \
  curl -k https://gitea.sisys.local/api/v1/version

# 2. 检查 Token 是否正确
kubectl get secret gitea-runner-token -n gitea-actions \
  -o jsonpath='{.data.token}' | base64 -d

# 3. 验证 Runner 配置
kubectl get configmap gitea-runner-config -n gitea-actions -o yaml
```

## 安全考虑

### Token 存储安全

- ✅ 所有 Token 存储于 Kubernetes Secret（加密存储）
- ✅ 禁止在 Git 仓库中明文存储 Token
- ✅ 使用环境变量注入方式访问 Token

### Token 访问控制

- ✅ Token 权限最小化（仅 repo 和 actions）
- ✅ 定期轮换 Token（90 天）
- ✅ 监控 Token 使用情况

### 审计日志

- ✅ 记录 Token 创建时间
- ✅ 记录 Token 轮换历史
- ✅ 记录 Token 使用情况

## 下一步

Token 配置完成后，继续执行：

1. ✅ Task 1.4: 验证 Token 权限
2. ➡️ Task 2: Gitea Runner 部署
3. ➡️ Task 3: Docker Executor 配置
4. ➡️ Task 4: K8s Executor 配置

## 参考文档

- [Gitea Runner 官方文档](https://docs.gitea.com/usage/actions/runner)
- [Kubernetes Secret 管理](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Story 0.8: Gitea Runner 配置](_bmad-output/implementation-artifacts/stories/0-8-gitea-runner-configuration.md)
