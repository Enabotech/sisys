# sisys - WSL 2 快速参考卡片

## 🚀 快速开始（方案 2：WSL 2）

### 第一次设置

#### 1. 从 Windows PowerShell 运行（管理员）

```powershell
# 导航到项目 docker 目录
cd g:\ai\sisys\docker

# 运行 WSL 2 安装脚本
.\setup-wsl2.ps1

# 重启电脑（如果提示）
```

#### 2. 从 Ubuntu 终端运行

```bash
# 打开 Ubuntu 22.04（从开始菜单或 wsl 命令）

# 导航到项目目录
cd ~/sisys  # 如果在主目录克隆
# 或
cd /mnt/g/ai/sisys  # 如果从 Windows 路径访问

# 运行 Docker 安装脚本
bash docker/setup-wsl2-docker.sh

# 重新登录或运行
newgrp docker
```

#### 3. 验证安装

```bash
# 测试 Docker（无需 sudo）
docker ps

# 启动服务
cd docker
docker-compose up -d

# 检查状态
docker-compose ps
```

---

## 📁 重要目录位置

### ✅ 推荐位置（WSL 文件系统 - 快速）

```bash
~/sisys              # 主目录中的项目
/home/username/sisys # 完整路径
```

### ❌ 避免位置（Windows 文件系统 - 慢速）

```bash
/mnt/c/sisys         # 慢！避免使用
/mnt/g/ai/sisys      # 慢！避免使用
```

---

## 🔧 常用命令

### WSL 管理（PowerShell）

```powershell
# 查看安装的 WSL 发行版
wsl --list --verbose

# 启动 WSL
wsl

# 关闭 WSL
wsl --shutdown

# 以特定用户身份运行
wsl -u username

# 在 WSL 中运行命令
wsl pwd
wsl ls -la
```

### Docker 管理（Ubuntu）

```bash
# 启动 Docker 守护进程
sudo systemctl start docker

# 停止 Docker 守护进程
sudo systemctl stop docker

# 查看 Docker 状态
sudo systemctl status docker

# 启用 Docker 开机自启
sudo systemctl enable docker

# 重启 Docker
sudo systemctl restart docker
```

### Docker Compose 命令

**Docker Desktop 用户:**
```bash
# 使用 docker compose（无连字符）
docker compose up -d
docker compose down
docker compose ps
docker compose logs -f
```

**Docker Engine 用户:**
```bash
# 使用 docker-compose（带连字符）或 docker compose
docker-compose up -d
docker-compose down
docker-compose ps
docker-compose logs -f
```

**检查安装:**
```bash
# Docker Desktop
docker compose version

# Docker Engine
docker-compose version
# 或
docker compose version
```

---

## 🔍 故障排查

### Docker 守护进程未运行

```bash
# 启动 Docker
sudo systemctl start docker

# 检查状态
sudo systemctl status docker

# 如果失败，查看日志
sudo journalctl -u docker.service
```

### 权限错误（Permission Denied）

```bash
# 重新添加用户到 docker 组
sudo usermod -aG docker $USER

# 应用更改
newgrp docker

# 或退出并重新登录
exit
# 然后重新连接 WSL
```

### 端口已被占用

```powershell
# 从 PowerShell 查找占用端口的进程
netstat -ano | findstr :5432

# 停止冲突的服务
# 或修改 docker-compose.yml 中的端口
```

### WSL 网络问题

```powershell
# 从 PowerShell 重置 WSL
wsl --shutdown
wsl

# 在 Ubuntu 中重启 Docker
sudo systemctl restart docker
```

### 磁盘空间不足

```bash
# 清理 Docker 资源
docker system prune -a --volumes

# 清理 apt 缓存
sudo apt clean

# 查看磁盘使用
df -h
```

---

## 📊 服务访问

### 从 WSL 访问

```bash
# 所有服务通过 localhost 访问
curl http://localhost:5432  # PostgreSQL
curl http://localhost:6379  # Redis
curl http://localhost:6333  # Qdrant
curl http://localhost:9000  # MinIO
curl http://localhost:7474  # Neo4j
```

### 从 Windows 访问

```powershell
# WSL 2 网络是共享的，可以直接访问
curl http://localhost:5432  # PostgreSQL
curl http://localhost:6379  # Redis
```

### 从其他设备访问

默认情况下，服务只绑定到 localhost，不从网络访问。
如需从网络访问，修改 `docker-compose.yml` 中的端口绑定。

---

## 💡 性能优化技巧

### 1. 始终在 WSL 文件系统中工作

```bash
# ✅ 好 - 快速 I/O
cd ~/sisys

# ❌ 差 - 慢速 I/O
cd /mnt/c/sisys
```

### 2. 使用 VSCode Remote - WSL

```bash
# 从 WSL 终端打开 VSCode
code .
```

### 3. 增加 WSL 内存（可选）

创建 `%USERPROFILE%\.wslconfig`：

```ini
[wsl2]
memory=16GB
processors=8
swap=8GB
```

### 4. 定期清理 Docker

```bash
# 清理未使用的资源
docker system prune

# 清理所有资源（谨慎使用）
docker system prune -a --volumes
```

---

## 📞 获取帮助

### 检查 WSL 版本

```powershell
# 从 PowerShell
wsl --list --verbose
```

### 检查 Docker 状态

```bash
# 从 Ubuntu
docker info
docker-compose version
```

### 查看日志

```bash
# Docker 日志
sudo journalctl -u docker.service

# Docker Compose 日志
docker-compose logs -f
```

---

## 🔗 相关文档

- **完整设置指南**: `WSL2_SETUP.md`
- **Docker Compose 配置**: `docker-compose.yml`
- **项目 README**: `../README.md`
- **快速设置指南**: `../docs/delivery/QUICK_SETUP.md`

---

## 📝 文档修订历史

| 版本 | 日期 | 修订内容 | 修订人 |
|------|------|---------|--------|
| 1.0.0 | 2026-02-28 | 初始版本 | 开发团队 |
| 1.1.0 | 2026-03-02 | 添加相关文档链接、统一日期格式 | AI 架构师 |

---

**最后更新:** 2026-03-02
**文档版本:** 1.1.0
**WSL 版本:** 2
**Ubuntu 版本:** 22.04 LTS
