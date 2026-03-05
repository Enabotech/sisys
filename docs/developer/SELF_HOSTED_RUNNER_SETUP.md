# Self-hosted Runner 配置指南

**机器配置：** 13700K + 32G RAM + 32G VRAM GPU + 1T SSD + 10T HD
**用途：** GitHub Actions CI/CD + 本地开发 + AI 模型推理
**日期：** 2026-03-05

---

## 🎯 目标

1. **解决 GitHub-hosted Runner 磁盘空间不足问题**
2. **利用本地强大硬件加速 CI/CD**
3. **支持本地 AI 模型推理和开发**
4. **降低 CI/CD 成本和时间**

---

## 📋 Self-hosted Runner 配置

### 1. 安装 GitHub Actions Runner

#### 步骤 1: 创建 Runner 目录

```bash
# Windows PowerShell (管理员)
cd C:\
mkdir actions-runner
cd actions-runner
```

#### 步骤 2: 下载 Runner

```powershell
# 下载最新 Runner
$version = "2.322.0"  # 检查最新版本
$url = "https://github.com/actions/runner/releases/download/v$version/actions-runner-win-x64-$version.zip"
Invoke-WebRequest -Uri $url -OutFile "actions-runner.zip"

# 解压
Expand-Archive -Path "actions-runner.zip" -DestinationPath .
```

#### 步骤 3: 配置 Runner

```powershell
# 从 GitHub 仓库 Settings → Actions → Runners 获取注册令牌
# 然后运行：
.\config.cmd --url https://github.com/YOUR_USERNAME/sisys --token YOUR_TOKEN
```

**配置选项：**
```
√ Enter the name of the runner: sisys-local-runner
√ Enter the name of a group: local,gpu,high-memory
√ Enter the URL of your GitHub Enterprise Server: [留空]
√ Enter a replace token for actions runner config: [留空]
√ Enter the runner scope (organization/repository): repository
√ Work folder (default): _work
```

#### 步骤 4: 注册为 Windows 服务

```powershell
# 安装服务
.\svcinstall.cmd

# 配置服务（自动启动）
.\svcconfigure.cmd

# 启动服务
.\svcstart.cmd
```

#### 步骤 5: 验证 Runner 状态

在 GitHub 仓库的 **Settings → Actions → Runners** 中查看：
- ✅ Runner 状态应为 **Online**
- ✅ 标签应包含：`self-hosted`, `windows`, `x64`, `local`, `gpu`

---

### 2. 优化 Runner 配置

#### 配置 Runner 标签（用于工作流路由）

```powershell
# 编辑 .runner 文件
notepad .runner

# 添加自定义标签
{
  "agentName": "sisys-local-runner",
  "labels": ["self-hosted", "windows", "x64", "local", "gpu", "high-memory", "10t-storage"],
  "workFolder": "C:\\actions-runner\\_work",
  ...
}
```

#### 配置 Runner 资源限制

```powershell
# 编辑 .env 文件
notepad .env

# 添加环境变量
RUNNER_TOOL_CACHE=C:\actions-runner\_toolcache
RUNNER_TEMP=C:\actions-runner\_temp
```

---

### 3. 更新 CI/CD 工作流

#### 方案 A: 仅 Docker Build 使用 Self-hosted Runner

**修改 `.github/workflows/ci.yml` Job 5:**

```yaml
  build-docker:
    name: Build Docker Image
    runs-on: [self-hosted, windows, gpu]  # ← 使用本地 Runner
    timeout-minutes: 20
    needs: [unit-tests, integration-tests]
    outputs:
      image_tag: ${{ steps.meta.outputs.tags }}
    steps:
      # ... 其他步骤不变

      - name: Build Docker image (optimized)
        uses: docker/build-push-action@v5
        with:
          context: .
          file: docker/Dockerfile.prod
          push: false
          tags: ${{ steps.meta.outputs.tags }}
          load: true
          # 本地 Runner 磁盘充足，不需要特殊优化
```

**优点：**
- ✅ 解决磁盘空间问题（1T SSD）
- ✅ 构建速度快（13700K + 32G RAM）
- ✅ 不影响其他 Job

**缺点：**
- ⚠️ 需要混合 Runner 管理
- ⚠️ Docker 镜像需要推送到 Registry

---

#### 方案 B: 所有 Job 使用 Self-hosted Runner（推荐）

**修改整个工作流：**

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  code-quality:
    runs-on: [self-hosted, windows, x64]
    # ... 其他配置

  unit-tests:
    runs-on: [self-hosted, windows, x64]
    needs: [code-quality]
    # ... 其他配置

  integration-tests:
    runs-on: [self-hosted, windows, x64]
    needs: [unit-tests]
    # ... 其他配置

  build-docker:
    runs-on: [self-hosted, windows, gpu, high-memory]
    needs: [unit-tests, integration-tests]
    # GPU 用于 AI 模型测试（如果有）
    # ... 其他配置
```

**优点：**
- ✅ 完全控制 Runner 配置
- ✅ 无磁盘空间限制
- ✅ 构建速度更快
- ✅ 无 GitHub Actions 分钟数限制

**缺点：**
- ⚠️ 需要维护 Runner 可用性
- ⚠️ 需要配置网络和安全

---

### 4. Docker 配置优化

#### 启用 Docker Buildx

```powershell
# 安装 Docker Desktop（如果未安装）
# https://docs.docker.com/desktop/install/windows-install/

# 启用 Buildx
docker buildx create --use --name sisys-builder

# 验证
docker buildx ls
```

#### 配置 Docker 存储驱动

```powershell
# 编辑 Docker 配置
# C:\ProgramData\docker\config\daemon.json

{
  "storage-driver": "overlay2",
  "data-root": "D:\\docker-data",  # 使用 10T HD 存储 Docker 数据
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

**重启 Docker 服务：**
```powershell
Restart-Service docker
```

---

### 5. 安全配置

#### 网络隔离

```powershell
# 配置 Windows 防火墙
# 仅允许 GitHub Actions IP 范围

$github_ips = @(
    "140.82.112.0/20",
    "143.55.64.0/20",
    "185.199.108.0/22",
    "192.30.252.0/22"
)

foreach ($ip in $github_ips) {
    New-NetFirewallRule -DisplayName "GitHub Actions" -RemoteAddress $ip -Direction Inbound -Action Allow
}
```

#### Runner 权限管理

```powershell
# 创建专用服务账户
New-LocalUser -Name "github-runner" -Password (ConvertTo-SecureString "StrongPassword123!" -AsPlainText -Force)

# 分配最小权限
Add-LocalGroupMember -Group "Users" -Member "github-runner"
```

---

## 🚀 本地开发环境集成

### 1. 使用本地 Runner 进行开发测试

```bash
# 本地运行 CI 工作流（使用 act 工具）
# 安装 act
choco install act

# 运行工作流
act -P ubuntu-latest=local -P self-hosted=local
```

### 2. GPU 加速 AI 模型测试

**利用 32G VRAM GPU 进行 AI 模型测试：**

```yaml
  ai-model-tests:
    runs-on: [self-hosted, windows, gpu]
    needs: [unit-tests]
    steps:
      - name: Setup GPU
        run: |
          nvidia-smi  # 验证 GPU 可用

      - name: Run AI model tests
        run: |
          poetry run pytest tests/ai/ -v --gpu
```

### 3. 大文件测试（10T HD）

```yaml
  large-data-tests:
    runs-on: [self-hosted, windows, 10t-storage]
    needs: [integration-tests]
    steps:
      - name: Setup large test data
        run: |
          # 使用 10T HD 存储测试数据
          D:\test-data\setup.bat
```

---

## 📊 性能对比

| 指标 | GitHub-hosted | Self-hosted (本地) | 提升 |
|------|--------------|-------------------|------|
| **CPU** | 2-4 核 | 16 核 (13700K) | 4-8x |
| **内存** | 7-16GB | 32GB | 2-4x |
| **磁盘** | 14GB | 1TB SSD + 10T HD | 700x+ |
| **GPU** | 无 | 32G VRAM | ∞ |
| **构建时间** | 15-30 分钟 | 3-8 分钟 | 3-5x |
| **成本** | $/分钟 | 电费 | 90%+ 节省 |

---

## 🔧 故障排查

### Runner 离线

```powershell
# 检查服务状态
Get-Service -Name "actions.runner.*"

# 重启服务
Restart-Service -Name "actions.runner.*"

# 查看日志
Get-Content C:\actions-runner\_diag\*.log -Tail 100
```

### Docker 构建失败

```powershell
# 清理 Docker
docker system prune -af --volumes

# 重建 Buildx
docker buildx rm sisys-builder
docker buildx create --use --name sisys-builder

# 验证 Docker
docker run --rm hello-world
```

### GPU 不可用

```powershell
# 检查 NVIDIA 驱动
nvidia-smi

# 更新驱动
# https://www.nvidia.com/drivers

# 验证 CUDA
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

---

## 📈 监控和维护

### Runner 健康检查

```powershell
# 创建健康检查脚本
# C:\actions-runner\health-check.ps1

while ($true) {
    $status = Get-Service -Name "actions.runner.*"
    if ($status.Status -ne "Running") {
        Restart-Service -Name "actions.runner.*"
        Send-Notification "Runner restarted"
    }
    Start-Sleep -Seconds 300
}
```

### 磁盘空间监控

```powershell
# 监控磁盘空间
$disk = Get-WmiObject Win32_LogicalDisk -DeviceId "C:"
$free = [math]::Round($disk.FreeSpace / 1GB, 2)

if ($free -lt 50) {
    Send-Notification "Low disk space: ${free}GB"
    docker system prune -af
}
```

---

## 🎯 下一步

1. **安装 Runner** - 按照步骤 1-5 安装
2. **测试工作流** - 推送代码触发 CI/CD
3. **监控性能** - 对比构建时间和成功率
4. **优化配置** - 根据实际使用情况调整

---

## 📚 参考资源

- [GitHub Actions Self-hosted Runner 文档](https://docs.github.com/en/actions/hosting-your-own-runners)
- [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
- [NVIDIA CUDA on Windows](https://docs.nvidia.com/cuda/wsl-user-guide/index.html)

---

**配置状态：** ⏳ 待实施
**预计实施时间：** 1-2 小时
**负责人：** Charlie (DevOps)
