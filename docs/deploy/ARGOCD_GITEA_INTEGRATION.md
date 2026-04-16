# ArgoCD Gitea 集成配置指南

本文档介绍如何配置 ArgoCD 与 Gitea 代码仓库的集成。

## 前置条件

- ✅ Story 0.4: K3S 集群部署完成
- ✅ Story 0.5: Gitea 代码托管部署完成
- ✅ Story 0.7 Task 1-3: ArgoCD 部署完成

## 配置步骤

### 方法一：自动脚本（推荐）

1. **运行配置脚本**

```bash
# 设置环境变量（可选）
export GITEA_USERNAME=admin
export GITEA_PASSWORD=your_admin_password
export GITEA_REPO=sisys/sisys

# 运行配置脚本
./scripts/deployment/argocd/configure-gitea-integration.sh
```

脚本将自动完成以下操作：
- 创建 Gitea Personal Access Token
- 配置 ArgoCD 仓库凭据
- 创建 Gitea Webhook
- 验证配置

### 方法二：手动配置

#### 步骤 1: 创建 Gitea Personal Access Token

1. 登录 Gitea: https://gitea.sisys.local
2. 点击右上角用户头像 -> **设置**
3. 进入 **应用** 页面
4. 点击 **生成新 Token**
5. 填写 Token 名称：`argocd-webhook`
6. 选择权限范围：
   - ✅ `repo` - 访问仓库
   - ✅ `admin:repo_hook` - 管理 Webhook
7. 点击 **生成 Token**
8. **复制 Token**（只显示一次，请妥善保存）

#### 步骤 2: 存储 Token 到 Kubernetes Secret

```bash
# 替换 YOUR_TOKEN_HERE 为实际 Token
kubectl create secret generic argocd-gitea-token \
    -n argocd \
    --from-literal=token='YOUR_TOKEN_HERE'
```

#### 步骤 3: 配置 ArgoCD 仓库凭据

```bash
# 应用配置文件
kubectl apply -f deploy/kubernetes/argocd/gitea-credentials.yaml
```

#### 步骤 4: 添加仓库到 ArgoCD

```bash
# 获取 Token
TOKEN=$(kubectl get secret argocd-gitea-token -n argocd -o jsonpath='{.data.token}' | base64 -d)

# 添加仓库
kubectl exec -n argocd deploy/argocd-server -- \
    argocd repo add https://gitea.sisys.local/sisys/sisys.git \
    --username admin \
    --password $TOKEN \
    --insecure-skip-server-verification
```

#### 步骤 5: 配置 Gitea Webhook

1. 进入 Gitea 仓库：https://gitea.sisys.local/sisys/sisys
2. 点击 **设置** -> **Webhook**
3. 点击 **添加 Webhook** -> **Gitea Webhook**
4. 配置 Webhook:
   - **URL**: `https://argocd.sisys.local/api/webhook`
   - **内容类型**: `application/json`
   - **触发事件**: 选择
     - ✅ Push 事件
     - ✅ 创建事件
     - ✅ 删除事件
   - ✅ 激活
   - ✅ 跳过 TLS 证书验证（开发环境）
5. 点击 **添加 Webhook**

#### 步骤 6: 验证 Webhook

1. 在 Gitea Webhook 页面，点击 Webhook 右侧的 **测试** 按钮
2. 选择 **发送测试事件**
3. 查看 ArgoCD 日志确认收到 Webhook:

```bash
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-server --tail=50
```

## 验证配置

### 1. 验证 ArgoCD 仓库连接

```bash
kubectl exec -n argocd deploy/argocd-server -- argocd repo list
```

期望输出：
```
URL                       TYPE  NAME   STATUS  MESSAGE
https://gitea.sisys.local/sisys/sisys.git  git          Success
```

### 2. 验证 Webhook 配置

```bash
# 查看 Gitea Webhook 列表
curl -k -H "Authorization: token YOUR_TOKEN" \
    https://gitea.sisys.local/api/v1/repos/sisys/sisys/hooks
```

### 3. 测试端到端流程

1. 修改代码并提交：
```bash
git add .
git commit -m "test: 测试 ArgoCD 自动同步"
git push gitea main
```

2. 观察 ArgoCD 日志：
```bash
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller -f
```

3. 查看 ArgoCD Application 状态：
```bash
kubectl exec -n argocd deploy/argocd-server -- argocd app list
```

## 故障排除

### 问题 1: Token 创建失败

**症状**: 运行脚本时提示 "Failed to get access token"

**解决方案**:
1. 检查 Gitea 用户名密码是否正确
2. 确认 Gitea 可访问：`curl -k https://gitea.sisys.local`
3. 手动创建 Token（见方法二步骤 1）

### 问题 2: ArgoCD 无法连接仓库

**症状**: `argocd repo add` 命令失败

**解决方案**:
1. 检查 Token 权限是否包含 `repo` 和 `admin:repo_hook`
2. 验证 Gitea 仓库 URL 是否正确
3. 检查网络连接：`kubectl exec -n argocd deploy/argocd-server -- curl -k https://gitea.sisys.local`

### 问题 3: Webhook 不触发

**症状**: 代码推送后 ArgoCD 没有自动同步

**解决方案**:
1. 检查 Webhook 配置是否正确
2. 查看 Gitea Webhook 日志：进入仓库 -> 设置 -> Webhook -> 查看最近投递
3. 检查 ArgoCD Webhook 端点是否可访问
4. 确认 TLS 证书配置（开发环境可跳过验证）

### 问题 4: HTTPS 证书验证失败

**症状**: SSL 证书验证错误

**解决方案**:
1. 开发环境：使用 `--insecure-skip-server-verification` 参数
2. 生产环境：配置有效的 TLS 证书

## 安全建议

1. **Token 管理**:
   - 定期轮换 Token（建议每 90 天）
   - 使用最小权限原则
   - 不在代码中硬编码 Token

2. **Webhook 安全**:
   - 使用 Webhook 密钥验证请求来源
   - 限制 Webhook IP 范围
   - 启用 TLS 加密

3. **网络隔离**:
   - 配置 NetworkPolicy 限制 ArgoCD 只能访问 Gitea
   - 使用内部服务名访问（避免经过 Ingress）

## 参考文档

- [ArgoCD 仓库凭据配置](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/#repositories)
- [Gitea Webhook 文档](https://docs.gitea.io/en-us/webhooks/)
- Story 0.7: ArgoCD 持续部署

## 下一步

- Task 5: Harbor 镜像仓库集成
- Task 6: Application 配置
- Task 7: 多环境配置
