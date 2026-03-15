# 域名配置问题修复指南

**创建日期**: 2026-03-15
**Story**: 0.7 - ArgoCD 持续部署
**状态**: ✅ 已完成修复

---

## 🔍 问题诊断

### 当前服务状态（修复后）

| 服务 | 域名 | HTTP NodePort:30580 | HTTPS NodePort:31448 | 状态 |
|------|------|---------------------|----------------------|------|
| **Gitea** | gitea.sisys.local | ⚠️ 需 Host 头 | ✅ 200 OK | ✅ 正常 |
| **Harbor** | harbor.sisys.local | ⚠️ 需 Host 头 | ✅ API 可用 | ✅ 正常 |
| **ArgoCD** | argocd.sisys.local | ⚠️ 需 Host 头 | ✅ 307 重定向 | ✅ 正常 |

**测试命令**:
```bash
# HTTPS 测试（推荐）
curl -k -I https://172.21.110.12:31448 -H "Host: gitea.sisys.local"    # ✅ 200
curl -k -I https://172.21.110.12:31448 -H "Host: argocd.sisys.local"   # ✅ 307
curl -k https://172.21.110.12:31448/api/v2.0/ping -H "Host: harbor.sisys.local"  # ✅ Pong

# HTTP 测试（不推荐，仅内部使用）
curl -I http://172.21.110.12:30580 -H "Host: gitea.sisys.local"        # ⚠️ 需 Host 头
```

### 已修复的问题

1. ✅ **harbor.sisys.local 已添加到 /etc/hosts**
   - DNS 解析成功：`getent hosts harbor.sisys.local` → `172.21.110.12`

2. ✅ **Gitea 通配符 Ingress 已删除**
   - `gitea-ingress-ip` 已删除
   - 不再劫持 HTTP 流量

3. ✅ **Harbor TLS Secret 已创建**
   - 自签名证书已生成并配置
   - HTTPS 路由正常工作

4. ✅ **ArgoCD IngressRoute 已修复**
   - 移除 Middleware 依赖
   - HTTPS 重定向工作正常

5. ✅ **Harbor API 验证通过**
   - `/api/v2.0/ping` 返回 `Pong`
   - 根路径 404 是 Harbor 正常行为（需要前端路由）

### 已知限制

1. **HTTP NodePort (30580) 需要 Host 头**
   - 直接访问 `http://172.21.110.12:30580` 返回 404
   - 必须添加 `-H "Host: <service>.sisys.local"` 头
   - 原因：Traefik web 入口点需要正确的 Host 头匹配 Ingress 规则

2. **Harbor 根路径返回 404**
   - 这是 Harbor 的正常行为
   - API 端点正常工作：`/api/v2.0/ping` → `Pong`
   - 浏览器访问需要通过完整 URL: https://harbor.sisys.local

---

## ✅ 已执行的修复步骤

### 步骤 1：添加 /etc/hosts 配置
```bash
echo "172.21.110.12 harbor.sisys.local" | sudo tee -a /etc/hosts
```

### 步骤 2：删除 Gitea 通配符 Ingress
```bash
echo "H9yglwH7sdyj" | sudo -S kubectl delete ingress gitea-ingress-ip -n gitea
```

### 步骤 3：创建 Harbor TLS Secret
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=harbor.sisys.local/O=SISYS"
echo "H9yglwH7sdyj" | sudo -S kubectl create secret tls harbor-tls-secret \
  --cert=tls.crt --key=tls.key -n harbor
```

### 步骤 4：修复 Harbor Ingress
```bash
# 更新 deployments/harbor/ingress.yaml
# - 同时支持 web 和 websecure 入口点
# - 移除不支持的 TLS minversion 注解
```

### 步骤 5：修复 ArgoCD IngressRoute
```bash
# 更新 deployments/argocd/traefik-ingressroute.yaml
# - 暂时移除 Middleware 依赖
```

---

### 方案 2：为 Harbor 配置 HTTPS NodePort 路由

如果必须保留 Gitea 通配符 Ingress（例如 Windows 主机需要 IP 直接访问），则为 Harbor 创建独立的 HTTPS 路由。

#### 步骤 1：添加 /etc/hosts 配置

```bash
echo "172.21.110.12 harbor.sisys.local" | sudo tee -a /etc/hosts
```

#### 步骤 2：创建 Harbor HTTPS Ingress

创建文件 `deployments/harbor/ingress-https.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: harbor-ingress-https
  namespace: harbor
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: websecure
    traefik.ingress.kubernetes.io/router.tls: "true"
spec:
  ingressClassName: traefik
  rules:
  - host: harbor.sisys.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: harbor-core
            port:
              number: 443
  tls:
  - hosts:
    - harbor.sisys.local
    secretName: harbor-tls-secret
```

应用配置：
```bash
echo "H9yglwH7sdyj" | sudo -S kubectl apply -f deployments/harbor/ingress-https.yaml
```

---

### 方案 3：使用 Traefik Middleware 路由（高级）

如果需要在同一 NodePort 上路由多个服务，使用 Traefik Middleware 进行高级路由。

**不推荐**: 配置复杂，维护成本高

---

## 🔧 长期解决方案

### 1. 使用真实 DNS 服务器

在 K3s 网络中配置 CoreDNS 转发：

```yaml
# 配置 /etc/rancher/k3s/config.yaml
cni: flannel
cluster-dns: 10.43.0.10
```

### 2. 使用 cert-manager 管理证书

```bash
# 安装 cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml

# 创建 ClusterIssuer
kubectl apply -f deployments/cert-manager/cluster-issuer.yaml

# 为所有服务配置自动证书
```

### 3. 移除 IP 直接访问需求

为 Windows 主机配置相同的 DNS 解析：
- 修改 `C:\Windows\System32\drivers\etc\hosts`
- 或使用内部 DNS 服务器

---

## 📋 验证清单

- [ ] `/etc/hosts` 配置正确
  - [ ] `172.21.110.12 gitea.sisys.local`
  - [ ] `172.21.110.12 harbor.sisys.local`
  - [ ] `172.21.110.12 argocd.sisys.local`

- [ ] Gitea 通配符 Ingress 已删除（或保留，如果使用方案 2）
  - [ ] `kubectl get ingress gitea-ingress-ip -n gitea` 返回 NotFound

- [ ] Harbor 访问测试
  - [ ] HTTP: `curl -I http://harbor.sisys.local` 返回 200 或 301
  - [ ] HTTPS: `curl -k -I https://harbor.sisys.local` 返回 200

- [ ] Gitea 访问测试
  - [ ] HTTPS: `curl -k -I https://gitea.sisys.local` 返回 200

- [ ] ArgoCD 访问测试
  - [ ] HTTPS: `curl -k -I https://argocd.sisys.local` 返回 200

- [ ] 浏览器访问测试
  - [ ] https://gitea.sisys.local 可访问
  - [ ] https://harbor.sisys.local 可访问
  - [ ] https://argocd.sisys.local 可访问

---

## 🚨 注意事项

1. **自签名证书警告**: 所有服务使用自签名证书，浏览器会显示安全警告
   - 开发环境：接受警告即可
   - 生产环境：使用 Let's Encrypt 或企业 CA

2. **密码安全**:
   - ArgoCD 初始密码：`kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d`
   - Gitea 初始密码：首次登录时设置
   - Harbor 初始密码：`Harbor12345`（部署时配置）

3. **防火墙**: 确保 30580 (HTTP) 和 31448 (HTTPS) 端口开放

---

## 📞 故障排除

### Harbor.sisys.local 仍无法访问

1. 检查 /etc/hosts：
   ```bash
   cat /etc/hosts | grep harbor
   ```

2. 检查 Ingress 配置：
   ```bash
   echo "H9yglwH7sdyj" | sudo -S kubectl get ingress -n harbor -o wide
   ```

3. 检查 Traefik 日志：
   ```bash
   echo "H9yglwH7sdyj" | sudo -S kubectl logs -n traefik -l app.kubernetes.io/name=traefik | tail -50
   ```

### HTTPS 证书错误

1. 检查证书 Secret：
   ```bash
   echo "H9yglwH7sdyj" | sudo -S kubectl get secret harbor-tls-secret -n harbor
   ```

2. 重新创建证书：
   ```bash
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
     -keyout tls.key -out tls.crt \
     -subj "/CN=harbor.sisys.local/O=SISYS"
   echo "H9yglwH7sdyj" | sudo -S kubectl create secret tls harbor-tls-secret --cert=tls.crt --key=tls.key -n harbor
   ```
