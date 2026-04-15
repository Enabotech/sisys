# Gitea 外部访问配置指南

## ✅ 访问方式（已配置成功）

### 1. DNS hosts 文件配置

```bash
# 已配置
<WSL2_IP> gitea.sisys.local
```

### 2. 访问 URL

| 协议 | URL | 状态 |
|------|-----|------|
| **HTTPS** | https://gitea.sisys.local:nodeport | ✅ 工作正常 |
| **HTTP** | http://gitea.sisys.local:nodeport | ✅ 工作正常 |

### 3. 管理员登录

- **URL**: https://gitea.sisys.local:nodeport
- **用户名**: `gitea_admin`
- **密码**: `Admin@123456`

首次登录需要修改密码（安全策略要求）。

---

## 网络架构说明

```
互联网/局域网
    │
    ▼ 访问 <WSL2_IP>:<NODEPORT> (HTTPS)
你的机器
    │
    ▼ DNS 解析 gitea.sisys.local → <WSL2_IP>
K3S 集群 (NodePort)
    │
    ▼ NodePort 31448
Traefik Ingress Controller (traefik 命名空间)
    │
    ▼ Ingress 路由
Gitea Service (gitea 命名空间)
    │
    ▼ 端口 3000
Gitea Pod
```

---

## 端口说明

| 服务 | NodePort | 说明 |
|------|----------|------|
| Traefik HTTP | 30580 | 80 端口映射 |
| Traefik HTTPS | 31448 | 443 端口映射 |
| Gitea 内部 | 3000 | Gitea 容器内部端口 |

---

## 局域网访问

如果你需要从同一局域网的其他机器访问：

1. **在其他机器上配置 hosts**：
   ```bash
   # 将 <WSL2_IP> 替换为你的 K3S 服务器 IP
   <K3S_SERVER_IP> gitea.sisys.local
   ```

2. **确保防火墙允许访问**：
   ```bash
   # Ubuntu/Debian
   sudo ufw allow 30580/tcp
   sudo ufw allow 31448/tcp

   # 或使用 iptables
   sudo iptables -A INPUT -p tcp --dport 30580 -j ACCEPT
   sudo iptables -A INPUT -p tcp --dport 31448 -j ACCEPT
   ```

---

## 故障排查

### 检查 Traefik 状态
```bash
echo "H9yglwH7sdyj" | sudo -S k3s kubectl get pods -n traefik
```

### 检查 Gitea 状态
```bash
echo "H9yglwH7sdyj" | sudo -S k3s kubectl get pods -n gitea
```

### 检查 Ingress 状态
```bash
echo "H9yglwH7sdyj" | sudo -S k3s kubectl get ingress -n gitea
```

### 查看 Traefik 日志
```bash
echo "H9yglwH7sdyj" | sudo -S k3s kubectl logs -n traefik -l app.kubernetes.io/name=traefik --tail=50
```

### 测试内部连接
```bash
# 从 Traefik Pod 测试到 Gitea 的连接
echo "H9yglwH7sdyj" | sudo -S k3s kubectl exec -n traefik $(sudo k3s kubectl get pod -n traefik -l app.kubernetes.io/name=traefik -o jsonpath='{.items[0].metadata.name}') -- curl -I http://gitea-http.gitea.svc.cluster.local:3000
```

---

## 管理员登录信息

- **URL**: https://gitea.sisys.local:nodeport
- **用户名**: `gitea_admin`
- **密码**: `Admin@123456`

首次登录需要修改密码（安全策略要求）。

---

## 生成文件

- 创建时间：2026-03-13
- K3S 服务器 IP: <WSL2_IP>
- Traefik NodePort: 30580 (HTTP), 31448 (HTTPS)
