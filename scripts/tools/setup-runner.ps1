# Self-hosted Runner 自动化安装脚本

**用途：** 一键安装和配置 GitHub Actions Self-hosted Runner
**系统要求：** Windows 10/11, 16G+ RAM, Docker Desktop
**日期：** 2026-03-05

---

## 📥 安装脚本

### setup-runner.ps1

```powershell
#!/usr/bin/env pwsh
# GitHub Actions Self-hosted Runner 自动化安装脚本
# 适用于：Windows 10/11 + Docker Desktop

param(
    [Parameter(Mandatory=$true)]
    [string]$GitHubToken,

    [Parameter(Mandatory=$false)]
    [string]$RepoUrl = "https://github.com/Agimtech/sisys",

    [Parameter(Mandatory=$false)]
    [string]$RunnerName = "sisys-local-runner",

    [Parameter(Mandatory=$false)]
    [string]$InstallPath = "C:\actions-runner",

    [Parameter(Mandatory=$false)]
    [switch]$SkipDockerCheck
)

$ErrorActionPreference = "Stop"

# =========================================
# 1. 系统检查
# =========================================
Write-Host "`n=== 1. 系统检查 ===" -ForegroundColor Cyan

# 检查 PowerShell 版本
if ($PSVersionTable.PSVersion.Major -lt 7) {
    Write-Host "⚠️  建议升级 PowerShell 到 7.0+" -ForegroundColor Yellow
    Write-Host "   当前版本：$($PSVersionTable.PSVersion)"
}

# 检查磁盘空间
$disk = Get-WmiObject Win32_LogicalDisk -DeviceId "C:"
$freeGB = [math]::Round($disk.FreeSpace / 1GB, 2)
Write-Host "✓ C 盘可用空间：${freeGB}GB"

if ($freeGB -lt 50) {
    Write-Host "⚠️  警告：C 盘空间不足 50GB，可能影响 Runner 运行" -ForegroundColor Yellow
}

# 检查 Docker
if (-not $SkipDockerCheck) {
    Write-Host "`n=== 检查 Docker ===" -ForegroundColor Cyan
    try {
        $dockerVersion = docker --version 2>&1
        Write-Host "✓ Docker 已安装：$dockerVersion" -ForegroundColor Green

        # 检查 Docker 是否运行
        docker info | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Docker 服务运行正常" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Docker 服务未运行，请启动 Docker Desktop" -ForegroundColor Yellow
            exit 1
        }
    } catch {
        Write-Host "❌ Docker 未安装或未配置" -ForegroundColor Red
        Write-Host "   请安装 Docker Desktop: https://docs.docker.com/desktop/install/windows-install/"
        exit 1
    }
}

# 检查 Git
Write-Host "`n=== 检查 Git ===" -ForegroundColor Cyan
try {
    $gitVersion = git --version 2>&1
    Write-Host "✓ Git 已安装：$gitVersion" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Git 未安装，部分功能可能受限" -ForegroundColor Yellow
}

# =========================================
# 2. 创建安装目录
# =========================================
Write-Host "`n=== 2. 创建安装目录 ===" -ForegroundColor Cyan

if (-not (Test-Path $InstallPath)) {
    Write-Host "创建目录：$InstallPath"
    New-Item -ItemType Directory -Path $InstallPath | Out-Null
    Write-Host "✓ 目录创建成功" -ForegroundColor Green
} else {
    Write-Host "✓ 目录已存在：$InstallPath" -ForegroundColor Yellow
}

Set-Location $InstallPath

# =========================================
# 3. 下载 Runner
# =========================================
Write-Host "`n=== 3. 下载 GitHub Actions Runner ===" -ForegroundColor Cyan

# 获取最新版本
$latestRelease = Invoke-RestMethod -Uri "https://api.github.com/repos/actions/runner/releases/latest" -Method Get
$version = $latestRelease.tag_name.TrimStart('v')
$downloadUrl = "https://github.com/actions/runner/releases/download/v$version/actions-runner-win-x64-$version.zip"
$zipFile = Join-Path $InstallPath "actions-runner.zip"

Write-Host "最新版本：v$version"
Write-Host "下载地址：$downloadUrl"

# 检查是否已下载
if (Test-Path $zipFile) {
    Write-Host "✓ 安装包已存在，跳过下载" -ForegroundColor Green
} else {
    Write-Host "下载 Runner..."
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipFile
    Write-Host "✓ 下载完成" -ForegroundColor Green
}

# =========================================
# 4. 解压 Runner
# =========================================
Write-Host "`n=== 4. 解压 Runner ===" -ForegroundColor Cyan

# 检查是否已解压
if (Test-Path (Join-Path $InstallPath "config.cmd")) {
    Write-Host "✓ Runner 已解压，跳过" -ForegroundColor Yellow
} else {
    Write-Host "解压中..."
    Expand-Archive -Path $zipFile -DestinationPath $InstallPath -Force
    Write-Host "✓ 解压完成" -ForegroundColor Green
}

# =========================================
# 5. 配置 Runner
# =========================================
Write-Host "`n=== 5. 配置 Runner ===" -ForegroundColor Cyan

$labels = "self-hosted,windows,x64,local,gpu,high-memory,10t-storage"
Write-Host "Runner 标签：$labels"

# 运行配置命令
Write-Host "运行配置..."
& .\config.cmd --url $RepoUrl `
               --token $GitHubToken `
               --name $RunnerName `
               --labels $labels `
               --work "_work" `
               --unattended

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Runner 配置成功" -ForegroundColor Green
} else {
    Write-Host "❌ Runner 配置失败" -ForegroundColor Red
    exit 1
}

# =========================================
# 6. 注册为 Windows 服务
# =========================================
Write-Host "`n=== 6. 注册为 Windows 服务 ===" -ForegroundColor Cyan

Write-Host "安装服务..."
.\svcinstall.cmd

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ 服务安装成功" -ForegroundColor Green
} else {
    Write-Host "⚠️  服务安装失败，可以手动运行" -ForegroundColor Yellow
}

# =========================================
# 7. 配置 Docker
# =========================================
Write-Host "`n=== 7. 配置 Docker Buildx ===" -ForegroundColor Cyan

try {
    # 创建 Buildx builder
    $builderName = "sisys-builder"
    docker buildx ls | Select-String $builderName | Out-Null

    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Buildx builder 已存在：$builderName" -ForegroundColor Yellow
    } else {
        Write-Host "创建 Buildx builder..."
        docker buildx create --use --name $builderName
        Write-Host "✓ Buildx builder 创建成功" -ForegroundColor Green
    }

    # 验证
    docker buildx ls
} catch {
    Write-Host "⚠️  Docker Buildx 配置失败" -ForegroundColor Yellow
}

# =========================================
# 8. 配置防火墙
# =========================================
Write-Host "`n=== 8. 配置防火墙规则 ===" -ForegroundColor Cyan

Write-Host "添加 GitHub Actions IP 白名单..."
$github_ips = @(
    "140.82.112.0/20",
    "143.55.64.0/20",
    "185.199.108.0/22",
    "192.30.252.0/22"
)

foreach ($ip in $github_ips) {
    $ruleName = "GitHub Actions - $ip"
    $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

    if (-not $existingRule) {
        New-NetFirewallRule -DisplayName $ruleName `
                           -RemoteAddress $ip `
                           -Direction Inbound `
                           -Action Allow `
                           -Enabled True | Out-Null
        Write-Host "✓ 添加规则：$ruleName"
    }
}

Write-Host "✓ 防火墙规则配置完成" -ForegroundColor Green

# =========================================
# 9. 启动 Runner 服务
# =========================================
Write-Host "`n=== 9. 启动 Runner 服务 ===" -ForegroundColor Cyan

$serviceName = Get-Service | Where-Object { $_.DisplayName -like "*actions.runner*" } | Select-Object -First1

if ($serviceName) {
    Write-Host "发现服务：$($serviceName.DisplayName)"

    if ($serviceName.Status -eq "Running") {
        Write-Host "✓ 服务已在运行" -ForegroundColor Green
    } else {
        Write-Host "启动服务..."
        Start-Service -Name $serviceName.Name
        Write-Host "✓ 服务启动成功" -ForegroundColor Green
    }
} else {
    Write-Host "⚠️  未找到 Runner 服务，可以手动启动：" -ForegroundColor Yellow
    Write-Host "   .\run.cmd"
}

# =========================================
# 10. 验证安装
# =========================================
Write-Host "`n=== 10. 验证安装 ===" -ForegroundColor Cyan

Write-Host "检查 Runner 状态..."
Start-Sleep -Seconds 5

# 检查服务状态
if ($serviceName) {
    $status = Get-Service -Name $serviceName.Name
    Write-Host "服务状态：$($status.Status)" -ForegroundColor $(if ($status.Status -eq "Running") { "Green" } else { "Yellow" })
}

# 检查 Runner 目录
Write-Host "`n安装目录内容:"
Get-ChildItem $InstallPath | Select-Object Name, Length, LastWriteTime | Format-Table

# =========================================
# 11. 完成提示
# =========================================
Write-Host "`n=== ✅ 安装完成！ ===" -ForegroundColor Green

Write-Host @"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GitHub Actions Self-hosted Runner 安装成功！
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📍 安装路径：$InstallPath
🏷️  Runner 名称：$RunnerName
🏷️  标签：$labels

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

下一步操作：

1. 在 GitHub 仓库中验证 Runner 状态：
   $RepoUrl/settings/actions/runners

2. 等待 Runner 上线（通常 30-60 秒）

3. 测试工作流：
   git push 触发 CI/CD

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

管理命令：

- 查看服务状态：Get-Service -Name "actions.runner.*"
- 重启服务：Restart-Service -Name "actions.runner.*"
- 停止服务：Stop-Service -Name "actions.runner.*"
- 手动运行：.\run.cmd
- 卸载服务：.\svcuninstall.cmd

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"@ -ForegroundColor White

# =========================================
# 12. 创建管理脚本
# =========================================
Write-Host "`n=== 12. 创建管理脚本 ===" -ForegroundColor Cyan

$managerScript = @"
#!/usr/bin/env pwsh
# GitHub Actions Runner 管理脚本

param(
    [ValidateSet('status','start','stop','restart','logs','uninstall')]
    [string]`$Action = 'status'
)

`$serviceName = Get-Service -Name "actions.runner.*" -ErrorAction SilentlyContinue

switch (`$Action) {
    'status' {
        if (`$serviceName) {
            Write-Host "服务名称：`$(`$serviceName.DisplayName)"
            Write-Host "服务状态：`$(`$serviceName.Status)"
            Write-Host "启动类型：`$(`$serviceName.StartType)"
        } else {
            Write-Host "❌ 未找到 Runner 服务"
        }
    }

    'start' {
        if (`$serviceName) {
            Start-Service -Name `$serviceName.Name
            Write-Host "✓ 服务已启动"
        } else {
            Write-Host "❌ 未找到 Runner 服务"
        }
    }

    'stop' {
        if (`$serviceName) {
            Stop-Service -Name `$serviceName.Name
            Write-Host "✓ 服务已停止"
        } else {
            Write-Host "❌ 未找到 Runner 服务"
        }
    }

    'restart' {
        if (`$serviceName) {
            Restart-Service -Name `$serviceName.Name
            Write-Host "✓ 服务已重启"
        } else {
            Write-Host "❌ 未找到 Runner 服务"
        }
    }

    'logs' {
        `$logPath = "$InstallPath\_diag"
        if (Test-Path `$logPath) {
            Get-ChildItem `$logPath -Filter *.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object {
                Get-Content `$_.FullName -Tail 50
            }
        } else {
            Write-Host "❌ 未找到日志目录"
        }
    }

    'uninstall' {
        Write-Host "⚠️  即将卸载 Runner 服务..."
        `$confirm = Read-Host "确认卸载？(y/N)"
        if (`$confirm -eq 'y') {
            if (`$serviceName) {
                Stop-Service -Name `$serviceName.Name -Force
                & .\svcuninstall.cmd
                Write-Host "✓ 服务已卸载"
            } else {
                Write-Host "❌ 未找到 Runner 服务"
            }
        }
    }
}
"@

$managerScriptPath = Join-Path $InstallPath "manage-runner.ps1"
$managerScript | Out-File -FilePath $managerScriptPath -Encoding UTF8
Write-Host "✓ 管理脚本已创建：$managerScriptPath" -ForegroundColor Green

Write-Host "`n使用示例：" -ForegroundColor Cyan
Write-Host "  .\manage-runner.ps1 status    # 查看状态"
Write-Host "  .\manage-runner.ps1 start     # 启动服务"
Write-Host "  .\manage-runner.ps1 restart   # 重启服务"
Write-Host "  .\manage-runner.ps1 logs      # 查看日志"
Write-Host "  .\manage-runner.ps1 uninstall # 卸载服务"

```

---

## 🚀 使用方法

### 1. 获取 GitHub Token

1. 打开 GitHub 仓库：**Settings → Actions → Runners**
2. 点击 **Add runner**
3. 复制 **Runner registration token**（有效期 1 小时）

### 2. 运行安装脚本

```powershell
# PowerShell (管理员)
cd g:\ai\sisys\scripts
.\setup-runner.ps1 -GitHubToken "YOUR_TOKEN_HERE"
```

### 3. 验证安装

```powershell
# 查看 Runner 状态
.\manage-runner.ps1 status

# 查看日志
.\manage-runner.ps1 logs

# 在 GitHub 仓库中查看
# Settings → Actions → Runners → 应该看到 sisys-local-runner Online
```

---

## 📋 配置选项

### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `-GitHubToken` | ✅ | - | GitHub Runner 注册令牌 |
| `-RepoUrl` | ❌ | `https://github.com/Agimtech/sisys` | GitHub 仓库 URL |
| `-RunnerName` | ❌ | `sisys-local-runner` | Runner 名称 |
| `-InstallPath` | ❌ | `C:\actions-runner` | 安装路径 |
| `-SkipDockerCheck` | ❌ | `false` | 跳过 Docker 检查 |

### 示例

```powershell
# 基本安装
.\setup-runner.ps1 -GitHubToken "YOUR_TOKEN"

# 自定义安装路径
.\setup-runner.ps1 -GitHubToken "YOUR_TOKEN" -InstallPath "D:\github-runner"

# 自定义 Runner 名称
.\setup-runner.ps1 -GitHubToken "YOUR_TOKEN" -RunnerName "my-runner"

# 跳过 Docker 检查（无 Docker 环境）
.\setup-runner.ps1 -GitHubToken "YOUR_TOKEN" -SkipDockerCheck
```

---

## 🔧 故障排查

### Runner 离线

```powershell
# 检查服务状态
.\manage-runner.ps1 status

# 重启服务
.\manage-runner.ps1 restart

# 查看日志
.\manage-runner.ps1 logs
```

### Docker 构建失败

```powershell
# 清理 Docker
docker system prune -af --volumes

# 重建 Buildx
docker buildx rm sisys-builder
docker buildx create --use --name sisys-builder

# 验证
docker run --rm hello-world
```

### 磁盘空间不足

```powershell
# 清理 C 盘
docker system prune -af
Remove-Item -Path "$env:LOCALAPPDATA\Docker\logs" -Recurse -Force
Remove-Item -Path "$env:LOCALAPPDATA\Temp" -Recurse -Force
```

---

## 📚 参考资源

- [GitHub Actions Runner 文档](https://docs.github.com/en/actions/hosting-your-own-runners)
- [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)

---

**脚本状态：** ✅ 已完成
**测试状态：** ⏳ 待测试
**负责人：** Charlie (DevOps)
