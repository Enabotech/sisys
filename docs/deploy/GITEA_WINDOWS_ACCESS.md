# Gitea 访问指南 - Windows 主机访问 WSL2

## ✅ 访问方式（已配置成功）

### 从 WSL2 内部访问

```bash
# HTTPS（推荐，使用域名）
curl -k https://gitea.sisys.local:nodeport

# HTTP
curl http://gitea.sisys.local:nodeport
```

### 从 Windows 11 主机访问

**方式 1：使用 IP 地址（无需配置）**

| 协议 | URL | 说明 |
|------|-----|------|
| **HTTP** | http://<WSL2_IP>:nodeport | 简单，但无加密 |
| **HTTPS** | https://<WSL2_IP>:<NODEPORT> | 加密，但证书警告（自签名） |

**方式 2：配置 Windows hosts 文件（推荐）**

1. **以管理员身份打开 PowerShell**

2. **添加 hosts 条目**：
   ```powershell
   Add-Content -Path "C:\Windows\System32\drivers\etc\hosts" -Value "<WSL2_IP> gitea.sisys.local"
   ```

3. **验证配置**：
   ```powershell
   ping gitea.sisys.local
   # 应该返回 <WSL2_IP>
   ```

4. **在 Edge 浏览器访问**：
   - HTTP: http://gitea.sisys.local:nodeport
   - HTTPS: https://gitea.sisys.local:nodeport

---

## 🔒 证书警告说明

**HTTPS 访问时会显示"连接不安全"**，这是因为：
- Gitea 使用自签名证书（不是由受信任的 CA 颁发）
- 这在开发环境是正常的

**解决方法：**
1. 点击页面上的"高级"或"详细信息"
2. 选择"继续前往网站（不安全）"或"接受风险并继续"
3. 或者使用 HTTP 访问（无加密但无证书警告）

---

## 📋 端口说明

| 服务 | WSL2 内部 | Windows 主机访问 |
|------|----------|-----------------|
| Traefik HTTP | 80 | 30580 (NodePort) |
| Traefik HTTPS | 443 | 31448 (NodePort) |
| Gitea 内部 | 3000 | 不直接暴露 |

---

## 🔍 故障排查

### 1. 检查 WSL2 IP 地址

```powershell
# 在 PowerShell 中运行
wsl hostname -I
# 应该返回 <WSL2_IP>（或类似）
```

### 2. 检查防火墙

如果无法访问，确保 Windows 防火墙允许 WSL2 网络：

```powershell
# 在 PowerShell（管理员）中运行
New-NetFirewallRule -DisplayName "WSL2 K3S" -Direction Inbound -LocalPort 30580,31448 -Protocol TCP -Action Allow
```

### 3. 测试连接

```bash
# 在 WSL2 中测试
curl http://<WSL2_IP>:nodeport
# 应该返回 HTML 页面
```

### 4. 检查 K3S 服务

```bash
# 在 WSL2 中运行
echo "your-pwd" | sudo -S k3s kubectl get svc -n traefik
# 确认 NodePort 配置
```

---

## 🎯 推荐访问方式

**Windows 主机用户推荐：**

1. **日常开发**：使用 HTTP http://gitea.sisys.local:nodeport（配置 hosts 后）
2. **需要加密**：使用 HTTPS https://gitea.sisys.local:nodeport（接受证书警告）
3. **临时访问**：直接使用 IP http://<WSL2_IP>:nodeport

---

## 📝 管理员登录

- **URL**: http://gitea.sisys.local:nodeport 或 https://gitea.sisys.local:nodeport
- **用户名**: `gitea_admin`
- **密码**: `Admin@123456`

首次登录需要修改密码（安全策略要求）。

---

## 配置时间

- **创建时间**: 2026-03-13
- **WSL2 IP**: <WSL2_IP>
- **HTTP NodePort**: 30580
- **HTTPS NodePort**: 31448
