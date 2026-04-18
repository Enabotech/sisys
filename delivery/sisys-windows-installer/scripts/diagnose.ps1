# ============================================================================
# 一键诊断脚本
# 功能：诊断安装问题并生成报告
# TDD 测试 - Task 2d
# ============================================================================

function Start-OneClickDiagnose {
    <#
    .SYNOPSIS
        一键诊断安装问题

    .DESCRIPTION
        自动检测以下问题：
        1. 系统要求（Windows 版本、虚拟化）
        2. Docker 状态
        3. 网络连接
        4. 端口占用
        5. 磁盘空间

    .OUTPUTS
        Hashtable - 诊断结果
    #>

    Write-Host "🔍 开始一键诊断..." -ForegroundColor Cyan
    Write-Host ""

    $diagnosis = @{}

    # 1. 检查系统要求
    Write-Host "1️⃣ 检查系统要求..." -ForegroundColor Yellow
    $osInfo = Get-CimInstance Win32_OperatingSystem
    $osVersion = [version]$osInfo.Version

    if ($osVersion.Major -ge 10) {
        Write-Host "   ✅ Windows 版本: $($osInfo.Caption)" -ForegroundColor Green
        $diagnosis.OSOk = $true
    } else {
        Write-Host "   ❌ Windows 版本过低: $($osInfo.Caption)" -ForegroundColor Red
        $diagnosis.OSOk = $false
    }

    # 检查虚拟化
    try {
        $computerInfo = Get-ComputerInfo
        if ($computerInfo.HyperVisorPresent) {
            Write-Host "   ✅ 虚拟化已启用" -ForegroundColor Green
            $diagnosis.VirtualizationOk = $true
        } else {
            Write-Host "   ⚠️  虚拟化未启用（请在 BIOS 中启用）" -ForegroundColor Yellow
            $diagnosis.VirtualizationOk = $false
        }
    } catch {
        Write-Host "   ⚠️  无法检查虚拟化状态" -ForegroundColor Yellow
        $diagnosis.VirtualizationOk = $null
    }
    Write-Host ""

    # 2. 检查 Docker 状态
    Write-Host "2️⃣ 检查 Docker 状态..." -ForegroundColor Yellow
    try {
        $dockerVersion = docker --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✅ Docker: $dockerVersion" -ForegroundColor Green
            $diagnosis.DockerInstalled = $true
        } else {
            Write-Host "   ❌ Docker 未安装或不可用" -ForegroundColor Red
            $diagnosis.DockerInstalled = $false
        }
    } catch {
        Write-Host "   ❌ Docker 命令执行失败" -ForegroundColor Red
        $diagnosis.DockerInstalled = $false
    }

    try {
        $dockerInfo = docker info 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✅ Docker 服务正在运行" -ForegroundColor Green
            $diagnosis.DockerRunning = $true
        } else {
            Write-Host "   ⚠️  Docker 服务未运行" -ForegroundColor Yellow
            $diagnosis.DockerRunning = $false
        }
    } catch {
        $diagnosis.DockerRunning = $false
    }
    Write-Host ""

    # 3. 检查网络连接
    Write-Host "3️⃣ 检查网络连接..." -ForegroundColor Yellow
    try {
        $testConnection = Test-Connection -ComputerName docker.com -Count 1 -Quiet
        if ($testConnection) {
            Write-Host "   ✅ 网络正常（可访问 docker.com）" -ForegroundColor Green
            $diagnosis.NetworkOk = $true
        } else {
            Write-Host "   ❌ 网络异常（无法访问 docker.com）" -ForegroundColor Red
            $diagnosis.NetworkOk = $false
        }
    } catch {
        Write-Host "   ❌ 网络检测失败" -ForegroundColor Red
        $diagnosis.NetworkOk = $false
    }
    Write-Host ""

    # 4. 检查端口占用
    Write-Host "4️⃣ 检查端口占用..." -ForegroundColor Yellow
    $port8080 = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue
    if ($port8080) {
        Write-Host "   ⚠️  端口 8080 已被占用" -ForegroundColor Yellow
        Write-Host "   占用进程 ID: $($port8080.OwningProcess)" -ForegroundColor Gray
        $diagnosis.Port8080Ok = $false
    } else {
        Write-Host "   ✅ 端口 8080 可用" -ForegroundColor Green
        $diagnosis.Port8080Ok = $true
    }
    Write-Host ""

    # 5. 检查磁盘空间
    Write-Host "5️⃣ 检查磁盘空间..." -ForegroundColor Yellow
    $disk = Get-PSDrive C
    $freeGB = [math]::Round($disk.Free / 1GB, 2)

    if ($freeGB -ge 50) {
        Write-Host "   ✅ 磁盘空间充足: ${freeGB}GB 可用" -ForegroundColor Green
        $diagnosis.DiskSpaceOk = $true
    } elseif ($freeGB -ge 20) {
        Write-Host "   ⚠️  磁盘空间紧张: ${freeGB}GB 可用（建议 ≥ 50GB）" -ForegroundColor Yellow
        $diagnosis.DiskSpaceOk = $true
    } else {
        Write-Host "   ❌ 磁盘空间不足: ${freeGB}GB 可用（建议 ≥ 50GB）" -ForegroundColor Red
        $diagnosis.DiskSpaceOk = $false
    }
    Write-Host ""

    # 生成诊断报告
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "📊 诊断报告" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray

    $issues = @()

    if (-not $diagnosis.OSOk) { $issues += "Windows 版本过低" }
    if (-not $diagnosis.VirtualizationOk) { $issues += "虚拟化未启用" }
    if (-not $diagnosis.DockerInstalled) { $issues += "Docker 未安装" }
    if (-not $diagnosis.DockerRunning) { $issues += "Docker 服务未运行" }
    if (-not $diagnosis.NetworkOk) { $issues += "网络异常" }
    if (-not $diagnosis.Port8080Ok) { $issues += "端口 8080 被占用" }
    if (-not $diagnosis.DiskSpaceOk) { $issues += "磁盘空间不足" }

    if ($issues.Count -eq 0) {
        Write-Host "✅ 未发现问题，系统状态良好！" -ForegroundColor Green
        $diagnosis.Status = "OK"
    } else {
        Write-Host "❌ 发现 $($issues.Count) 个问题:" -ForegroundColor Red
        $issues | ForEach-Object { Write-Host "   - $_" -ForegroundColor Red }
        $diagnosis.Status = "IssuesFound"
        $diagnosis.Issues = $issues
    }

    Write-Host ""

    return $diagnosis
}

function Export-DiagnosisReport {
    <#
    .SYNOPSIS
        导出诊断报告到文件

    .PARAMETER Diagnosis
        诊断结果

    .PARAMETER OutputPath
        输出路径
    #>
    param(
        [Hashtable]$Diagnosis,
        [string]$OutputPath = "$env:TEMP\SISYS-Diagnosis-$(Get-Date -Format 'yyyyMMdd-HHmmss').txt"
    )

    $report = @"
SISYS 诊断报告
生成时间: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

系统信息:
  OS: $([System.Environment]::OSVersion.VersionString)
  架构: $([System.Environment]::Is64BitOperatingSystem ? "64-bit" : "32-bit")

诊断结果:
  系统要求: $(if ($Diagnosis.OSOk) { "✅" } else { "❌" })
  虚拟化: $(if ($Diagnosis.VirtualizationOk) { "✅" } else { "⚠️" })
  Docker 安装: $(if ($Diagnosis.DockerInstalled) { "✅" } else { "❌" })
  Docker 运行: $(if ($Diagnosis.DockerRunning) { "✅" } else { "⚠️" })
  网络: $(if ($Diagnosis.NetworkOk) { "✅" } else { "❌" })
  端口 8080: $(if ($Diagnosis.Port8080Ok) { "✅" } else { "⚠️" })
  磁盘空间: $(if ($Diagnosis.DiskSpaceOk) { "✅" } else { "❌" })

问题列表:
$(if ($Diagnosis.Issues) { $Diagnosis.Issues | ForEach-Object { "  - $_" } } else { "  无" })

建议操作:
  1. 查看快速入门指南: docs\quick-start-guide.md
  2. 联系技术支持: support@sisys.local
"@

    $report | Out-File -FilePath $OutputPath -Encoding UTF8

    Write-Host "📄 诊断报告已保存: $OutputPath" -ForegroundColor Cyan
    return $OutputPath
}

# 执行诊断
$diagnosis = Start-OneClickDiagnose

# 导出报告
Export-DiagnosisReport -Diagnosis $diagnosis
