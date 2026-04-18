# ============================================================================
# Docker 检测脚本
# 功能：检测系统中是否已安装 Docker
# ============================================================================

function Test-DockerInstallation {
    <#
    .SYNOPSIS
        检测 Docker 是否已安装

    .DESCRIPTION
        通过多种方式检测 Docker Desktop 是否已安装：
        1. 检查注册表
        2. 检查 PATH 环境变量
        3. 检查 Docker 服务是否运行

    .OUTPUTS
        Boolean - True 表示 Docker 已安装，False 表示未安装
    #>

    Write-Host "🔍 正在检测 Docker 环境..." -ForegroundColor Cyan

    # 方法 1: 检查注册表
    $dockerRegistryPath = $null

    # 检查 HKLM
    $dockerRegistryPath = Get-ItemProperty -Path "HKLM:\SOFTWARE\Docker Inc.\Docker Desktop" -Name "InstallPath" -ErrorAction SilentlyContinue

    # 如果 HKLM 没有，检查 HKCU
    if (-not $dockerRegistryPath) {
        $dockerRegistryPath = Get-ItemProperty -Path "HKCU:\SOFTWARE\Docker Inc.\Docker Desktop" -Name "InstallPath" -ErrorAction SilentlyContinue
    }

    if ($dockerRegistryPath) {
        Write-Host "✅ 通过注册表检测到 Docker Desktop" -ForegroundColor Green
        Write-Host "   安装路径: $($dockerRegistryPath.InstallPath)" -ForegroundColor Gray
        return $true
    }

    # 方法 2: 检查 docker.exe 是否在 PATH 中
    $dockerExe = Get-Command docker -ErrorAction SilentlyContinue

    if ($dockerExe) {
        Write-Host "✅ 通过 PATH 检测到 docker.exe" -ForegroundColor Green
        Write-Host "   路径: $($dockerExe.Source)" -ForegroundColor Gray

        # 方法 3: 验证 Docker 是否可执行
        try {
            $dockerVersion = docker --version 2>&1
            Write-Host "   版本: $dockerVersion" -ForegroundColor Gray

            # 检查 Docker 服务是否运行
            $dockerInfo = docker info 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ Docker 服务正在运行" -ForegroundColor Green
                return $true
            } else {
                Write-Host "⚠️  Docker 已安装但服务未运行" -ForegroundColor Yellow
                Write-Host "   请启动 Docker Desktop" -ForegroundColor Gray
                return $false
            }
        } catch {
            Write-Host "⚠️  Docker 命令执行失败" -ForegroundColor Yellow
            return $false
        }
    }

    # 未检测到 Docker
    Write-Host "❌ 未检测到 Docker 运行环境" -ForegroundColor Red
    return $false
}

function Get-DockerVersion {
    <#
    .SYNOPSIS
        获取 Docker 版本信息

    .OUTPUTS
        Hashtable - 包含 Docker 版本信息
    #>

    try {
        $versionOutput = docker --version 2>&1
        $versionString = $versionOutput -replace "Docker version ", ""

        # 解析主版本号
        $major = ($versionString -split "\.")[0] -as [int]

        return @{
            Version = $versionString
            Major = $major
            Installed = $true
        }
    } catch {
        return @{
            Version = $null
            Major = $null
            Installed = $false
        }
    }
}

function Test-DockerCompose {
    <#
    .SYNOPSIS
        检测 Docker Compose 是否可用

    .OUTPUTS
        Boolean - True 表示 Docker Compose 可用
    #>

    try {
        $composeVersion = docker compose version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Docker Compose 可用" -ForegroundColor Green
            Write-Host "   版本: $composeVersion" -ForegroundColor Gray
            return $true
        }
    } catch {
        Write-Host "❌ Docker Compose 不可用" -ForegroundColor Red
        return $false
    }

    return $false
}

# 执行检测
$isDockerInstalled = Test-DockerInstallation

if ($isDockerInstalled) {
    $version = Get-DockerVersion
    $composeOk = Test-DockerCompose

    Write-Host ""
    Write-Host "📊 Docker 环境状态" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
    Write-Host "Docker: ✅ 已安装 (v$($version.Version))"
    Write-Host "Docker Compose: $(if ($composeOk) { '✅ 可用' } else { '❌ 不可用' })"
    Write-Host ""

    exit 0
} else {
    Write-Host ""
    Write-Host "💡 建议操作:" -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
    Write-Host "1. 选择自动安装 Docker Desktop（推荐）"
    Write-Host "2. 选择安装 Rancher Desktop（开源免费）"
    Write-Host "3. 手动下载: https://docker.com"
    Write-Host ""

    exit 1
}
