# Windows Hosts 配置说明
# 用于解决 SISYS 服务域名解析问题

## 问题说明

WSL2 的 `/etc/hosts` 配置不影响 Windows 浏览器。
从 Windows 浏览器访问 https://<service>.sisys.local:31448 时，需要在 Windows hosts 文件中添加 DNS 映射。

## 解决方案

### 步骤 1：以管理员身份打开记事本

1. 按 `Win + X`，选择 "Windows PowerShell (管理员)" 或 "终端 (管理员)"
2. 运行命令：
   ```powershell
   notepad C:\Windows\System32\drivers\etc\hosts
   ```

### 步骤 2：添加以下行到 hosts 文件末尾

```
172.21.110.12    gitea.sisys.local
172.21.110.12    harbor.sisys.local
172.21.110.12    argocd.sisys.local
```

### 步骤 3：保存并关闭

1. 按 `Ctrl + S` 保存
2. 关闭记事本

### 步骤 4：刷新 DNS 缓存

在管理员 PowerShell 中运行：
```powershell
Clear-DnsClientCache
```

### 步骤 5：验证配置

打开命令提示符或 PowerShell，运行：
```powershell
ping gitea.sisys.local
ping harbor.sisys.local
ping argocd.sisys.local
```

应该看到解析到 `172.21.110.12`

## 访问方式

配置完成后，在浏览器中访问：

| 服务 | URL |
|------|-----|
| **Gitea** | https://gitea.sisys.local:31448 |
| **Harbor** | https://harbor.sisys.local:31448 |
| **ArgoCD** | https://argocd.sisys.local:31448 |

## 注意事项

1. **自签名证书警告**：浏览器会显示"您的连接不是私密连接"，点击"高级" → "继续访问"即可
2. **端口号**：必须包含端口号 `:31448`（Traefik HTTPS NodePort）
3. **管理员权限**：修改 hosts 文件需要管理员权限

## 故障排除

### 如果仍然无法解析

1. 检查 hosts 文件是否正确保存：
   ```powershell
   Get-Content C:\Windows\System32\drivers\etc\hosts
   ```

2. 检查 DNS 缓存是否已刷新：
   ```powershell
   Get-DnsClientCache | Select-Object Entry, Name
   ```

3. 尝试重启浏览器

### 如果连接被拒绝

1. 检查 K3s 集群是否运行正常
2. 检查 Traefik 服务状态：
   ```bash
   echo "H9yglwH7sdyj" | sudo -S kubectl get svc -n traefik
   ```

3. 检查 NodePort 是否开放：
   ```bash
   netstat -an | grep 31448
   ```

## 替代方案：直接 IP 访问

如果无法修改 hosts 文件，可以使用 IP + Host 头方式访问（仅用于测试）：

```bash
# 使用 curl 测试
curl -k https://172.21.110.12:31448 -H "Host: harbor.sisys.local"

# 浏览器无法直接使用 Host 头，需要修改 hosts 文件
```
