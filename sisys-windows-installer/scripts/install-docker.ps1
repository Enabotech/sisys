# ============================================================================
# Docker 静默安装脚本
# 功能：安装 Docker Desktop 或 Rancher Desktop（静默模式）
# TDD 测试 - Task 2c
# ============================================================================

param(
    [ValidateSet("DockerDesktop", "RancherDesktop")]
    [string]$InstallTarget = "DockerDesktop",
    [string]$InstallerPath,
    [int]$MaxRetries = 2,
    [int]$RetryDelaySeconds = 10
)

function Test-VirtualizationPrerequisites {
    <#
    .SYNOPSIS
        检查虚拟化前置条件（修复 H6）

    .OUTPUTS
        Boolean - True 表示满足前置条件
    #>

    Write-Host "🔍 检查虚拟化前置条件..." -ForegroundColor Cyan

    # 1. 检查 Windows 版本
    $osInfo = Get-CimInstance Win32_OperatingSystem
    $osVersion = [version]$osInfo.Version

    if ($osVersion.Major -lt 10 -or ($osVersion.Major -eq 10 -and $osVersion.Build -lt 19041)) {
        Write-Host "❌ Windows 版本过低（需要 Windows 10 2004+）" -ForegroundColor Red
        Write-Host "   当前版本: $($osInfo.Caption) (Build $($osVersion.Build))" -ForegroundColor Gray
        return $false
    }
    Write-Host "✅ Windows 版本: $($osInfo.Caption)" -ForegroundColor Green

    # 2. 检查虚拟化支持
    try {
        $computerInfo = Get-CimInstance Win32_ComputerSystem
        if ($computerInfo.HypervisorPresent) {
            Write-Host "✅ 虚拟化已启用" -ForegroundColor Green
        } else {
            Write-Host "❌ 虚拟化未启用" -ForegroundColor Red
            Write-Host "   请在 BIOS/UEFI 中启用虚拟化技术 (VT-x/AMD-V)" -ForegroundColor Yellow
            return $false
        }
    } catch {
        Write-Host "⚠️  无法检查虚拟化状态: $_" -ForegroundColor Yellow
    }

    # 3. 检查 WSL2 或 Hyper-V
    $wslInstalled = $false
    $hyperVInstalled = $false

    try {
        $wsl = wsl --status 2>&1
        if ($LASTEXITCODE -eq 0) {
            $wslInstalled = $true
            Write-Host "✅ WSL2 已安装" -ForegroundColor Green
        }
    } catch {
        # WSL 未安装
    }

    try {
        $hyperV = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All -ErrorAction Stop
        if ($hyperV.State -eq "Enabled") {
            $hyperVInstalled = $true
            Write-Host "✅ Hyper-V 已启用" -ForegroundColor Green
        }
    } catch {
        # Hyper-V 未安装或不可用
    }

    if (-not $wslInstalled -and -not $hyperVInstalled) {
        Write-Host "❌ 未检测到 WSL2 或 Hyper-V" -ForegroundColor Red
        Write-Host ""
        Write-Host "💡 安装建议:" -ForegroundColor Yellow
        Write-Host "   1. 启用 WSL2（推荐）: wsl --install" -ForegroundColor Gray
        Write-Host "   2. 或启用 Hyper-V: Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All" -ForegroundColor Gray
        Write-Host "   3. 重启计算机后重试" -ForegroundColor Gray
        return $false
    }

    Write-Host ""
    return $true
}

function Start-DockerDesktopInstall {
    <#
    .SYNOPSIS
        静默安装 Docker Desktop

    .PARAMETER InstallerPath
        安装程序路径

    .OUTPUTS
        Boolean - True 表示安装成功
    #>
    param([string]$InstallerPath)

    Write-Host "🔧 开始安装 Docker Desktop..." -ForegroundColor Cyan
    Write-Host "   安装程序: $InstallerPath" -ForegroundColor Gray
    Write-Host ""

    # Docker Desktop 静默安装参数
    # --quiet: 静默模式
    # --accept-license: 接受许可条款
    # --noreboot: 安装后不重启
    $arguments = @(
        "install",
        "--quiet",
        "--accept-license",
        "--noreboot"
    )

    try {
        $process = Start-Process -FilePath $InstallerPath `
            -ArgumentList $arguments `
            -Wait `
            -PassThru `
            -NoNewWindow `
            -ErrorAction Stop

        if ($process.ExitCode -eq 0) {
            Write-Host "✅ Docker Desktop 安装成功" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ Docker Desktop 安装失败 (退出码: $($process.ExitCode))" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "❌ 安装过程出错: $_" -ForegroundColor Red
        return $false
    }
}

function Start-RancherDesktopInstall {
    <#
    .SYNOPSIS
        静默安装 Rancher Desktop

    .PARAMETER InstallerPath
        安装程序路径

    .OUTPUTS
        Boolean - True 表示安装成功
    #>
    param([string]$InstallerPath)

    Write-Host "🔧 开始安装 Rancher Desktop..." -ForegroundColor Cyan
    Write-Host "   安装程序: $InstallerPath" -ForegroundColor Gray
    Write-Host ""

    # Rancher Desktop 静默安装参数
    $arguments = @(
        "/S",  # 静默模式
        "/norestart"  # 不重启
    )

    try {
        $process = Start-Process -FilePath $InstallerPath `
            -ArgumentList $arguments `
            -Wait `
            -PassThru `
            -NoNewWindow `
            -ErrorAction Stop

        if ($process.ExitCode -eq 0) {
            Write-Host "✅ Rancher Desktop 安装成功" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ Rancher Desktop 安装失败 (退出码: $($process.ExitCode))" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "❌ 安装过程出错: $_" -ForegroundColor Red
        return $false
    }
}

function Start-DockerInstallWithRetry {
    <#
    .SYNOPSIS
        带重试机制的 Docker 安装

    .PARAMETER InstallTarget
        安装目标 (DockerDesktop/RancherDesktop)

    .PARAMETER InstallerPath
        安装程序路径

    .PARAMETER MaxRetries
        最大重试次数

    .OUTPUTS
        Boolean - True 表示安装成功
    #>
    param(
        [string]$InstallTarget,
        [string]$InstallerPath,
        [int]$MaxRetries = 2
    )

    $attempt = 1

    while ($attempt -le $MaxRetries) {
        Write-Host ""
        Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
        Write-Host "安装尝试 $attempt/$MaxRetries" -ForegroundColor Cyan
        Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
        Write-Host ""

        $success = $false

        if ($InstallTarget -eq "DockerDesktop") {
            $success = Start-DockerDesktopInstall -InstallerPath $InstallerPath
        } else {
            $success = Start-RancherDesktopInstall -InstallerPath $InstallerPath
        }

        if ($success) {
            return $true
        }

        $attempt++

        if ($attempt -le $MaxRetries) {
            Write-Host ""
            Write-Host "⏳ $RetryDelaySeconds 秒后重试..." -ForegroundColor Yellow
            Start-Sleep -Seconds $RetryDelaySeconds
        }
    }

    Write-Host ""
    Write-Host "❌ 安装失败（已重试 $MaxRetries 次）" -ForegroundColor Red
    return $false
}

function Show-InstallProgress {
    <#
    .SYNOPSIS
        显示安装进度
    #>
    param(
        [string]$Stage,
        [int]$PercentComplete
    )

    $bar = "[" + ("█" * ($PercentComplete / 5)) + ("░" * (20 - $PercentComplete / 5)) + "]"

    Write-Host "`r$bar $PercentComplete% - $Stage" -NoNewline
}

# ============================================================================
# 主逻辑
# ============================================================================

Write-Host "🎯 Docker 安装管理器" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
Write-Host ""

# 修复 H6: 检查虚拟化前置条件
if (-not (Test-VirtualizationPrerequisites)) {
    Write-Host "❌ 虚拟化前置条件不满足，无法继续安装" -ForegroundColor Red
    exit 1
}

# 验证安装程序是否存在
if (-not (Test-Path $InstallerPath)) {
    Write-Host "❌ 安装程序不存在: $InstallerPath" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 建议操作:" -ForegroundColor Yellow
    Write-Host "   1. 先运行 download-docker.ps1 下载安装程序" -ForegroundColor Gray
    Write-Host "   2. 或手动下载: https://docker.com" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

# 显示进度
Show-InstallProgress -Stage "准备安装..." -PercentComplete 0

# 执行安装（带重试）
$installOk = Start-DockerInstallWithRetry `
    -InstallTarget $InstallTarget `
    -InstallerPath $InstallerPath `
    -MaxRetries $MaxRetries

if ($installOk) {
    Show-InstallProgress -Stage "安装完成！" -PercentComplete 100
    Write-Host ""
    Write-Host ""
    Write-Host "✅ Docker 安装成功！" -ForegroundColor Green
    Write-Host ""
    Write-Host "💡 下一步:" -ForegroundColor Cyan
    Write-Host "   1. 启动 Docker Desktop" -ForegroundColor Gray
    Write-Host "   2. 完成初始设置向导" -ForegroundColor Gray
    Write-Host "   3. 验证安装: docker --version" -ForegroundColor Gray
    Write-Host ""
    exit 0
} else {
    Write-Host ""
    Write-Host "❌ Docker 安装失败" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 故障排查建议:" -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
    Write-Host "1. 检查系统要求（Windows 10/11 64-bit）"
    Write-Host "2. 确认虚拟化已启用（BIOS 设置）"
    Write-Host "3. 检查是否有足够的磁盘空间"
    Write-Host "4. 以管理员身份运行安装程序"
    Write-Host "5. 查看安装日志: %TEMP%\DockerDesktopInstaller.log"
    Write-Host ""
    exit 1
}
