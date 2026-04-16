# ArgoCD 访问指南

## ✅ 部署状态

- **ArgoCD 版本**: v2.10.1
- **Helm Chart**: argo-cd-6.4.0
- **Pod 状态**: 6/6 Running
- **API 验证**: 通过

## 🔐 登录信息

- **URL**: https://argocd.sisys.local
- **用户名**: admin
- **初始密码**: `1iD3hQFVMi82v0TP`

## 🌐 访问方式

### 方式 1: 使用 Host 头（推荐测试）

```bash
# 使用 curl 测试
curl -k -H "Host: argocd.sisys.local" https://<WSL2_IP>:<NODEPORT>/

# 使用浏览器访问（需要手动输入 IP 和端口）
https://<WSL2_IP>:<NODEPORT>/
# 然后在浏览器开发者工具中设置 Host 头为 argocd.sisys.local
```

### 方式 2: 配置 Windows hosts 文件（推荐日常使用）

如果您在 Windows 上使用浏览器访问，需要修改 Windows 的 hosts 文件：

1. 以管理员身份打开记事本
2. 打开文件：`C:\Windows\System32\drivers\etc\hosts`
3. 添加以下行：
   ```
   <WSL2_IP>    argocd.sisys.local
   ```
4. 保存文件
5. 刷新 DNS 缓存：`ipconfig /flushdns`
6. 访问：https://argocd.sisys.local

### 方式 3: 使用 kubectl port-forward（临时访问）

```bash
# 在终端运行
kubectl port-forward -n argocd svc/argocd-server 8443:443

# 然后访问
https://localhost:8443
```

### 方式 4: 使用 NodePort 直接访问

```bash
# Traefik HTTPS NodePort: 31448
# 在浏览器访问：
https://<WSL2_IP>:<NODEPORT>/

# 需要在浏览器中设置 Host 头或使用浏览器扩展
```

## 🔧 故障排除

### 问题：ERR_NAME_NOT_RESOLVED

**原因**: DNS 无法解析域名

**解决方案**:
1. 检查 hosts 文件配置
2. Windows 用户需要修改 Windows hosts 文件（不是 WSL2 的）
3. 使用 `nslookup argocd.sisys.local` 测试 DNS 解析

### 问题：连接被拒绝 (Connection Refused)

**原因**: 使用了错误的端口

**解决方案**:
- 使用 NodePort 31448 (HTTPS) 或 30580 (HTTP)
- 或使用 port-forward 方式

### 问题：显示 Gitea 页面而不是 ArgoCD

**原因**: Host 头配置不正确

**解决方案**:
- 确保使用正确的 Host 头 `argocd.sisys.local`
- 检查浏览器是否缓存了错误的响应

## 📝 首次登录步骤

1. 访问 ArgoCD Web 界面
2. 使用用户名 `admin` 和初始密码登录
3. 首次登录会强制要求修改密码
4. 密码要求：
   - 至少 12 位
   - 包含大写字母
   - 包含小写字母
   - 包含数字
   - 包含特殊符号

## 🔑 修改密码命令（可选）

```bash
# 使用 ArgoCD CLI
argocd login argocd.sisys.local
argocd account update-password
```

## 📊 监控命令

```bash
# 查看 Pod 状态
kubectl get pods -n argocd

# 查看服务状态
kubectl get svc -n argocd

# 查看 Ingress
kubectl get ingress -n argocd

# 查看日志
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-server
```

## 🧪 测试验证

```bash
# 测试 API 版本
curl -k -H "Host: argocd.sisys.local" https://<WSL2_IP>:<NODEPORT>/api/version

# 测试健康检查
curl -k -H "Host: argocd.sisys.local" https://<WSL2_IP>:<NODEPORT>/healthz
```

## 📅 部署日期

2026-03-15

## 📞 支持

如有问题，请查看：
- Story 文件：`_bmad-output/implementation-artifacts/stories/0.7-argocd-continuous-deployment.md`
- 部署配置：`deploy/kubernetes/argocd/`
- 测试文件：`tests/deployment/test_argocd.py`
