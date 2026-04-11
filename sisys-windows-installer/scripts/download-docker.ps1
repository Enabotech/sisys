# ============================================================================
# Docker 下载管理脚本
# 功能：下载 Docker Desktop 或 Rancher Desktop
# TDD 测试 - Task 2b
# ============================================================================

param(
    [ValidateSet("DockerDesktop", "RancherDesktop")]
    [string]$DownloadTarget = "DockerDesktop",
    [string]$DownloadPath = "$env:TEMP",
    [switch]$Silent = $false
)

function Get-DockerDesktopDownloadUrl {
    <#
    .SYNOPSIS
        获取 Docker Desktop 最新稳定版下载链接
    .DESCRIPTION
        从 GitHub API 动态获取最新版本号（修复 H4）
    .OUTPUTS
        Hashtable - 包含 URL、版本号、文件大小和 SHA256 哈希值
    #>
    
    try {
        # 从 GitHub Releases API 获取最新版本
        $response = Invoke-RestMethod -Uri "https://api.github.com/repos/docker/desktop-win/releases/latest" -ErrorAction Stop
        $latestVersion = $response.tag_name -replace '^v', ''
        
        # 查找安装程序的下载链接
        $asset = $response.assets | Where-Object { $_.name -like "*Docker*Installer.exe" }
        
        if ($asset) {
            $downloadUrl = $asset.browser_download_url
            $fileSize = $asset.size
        } else {
            # 备用：使用已知格式构建 URL
            $downloadUrl = "https://desktop.docker.com/win/main/amd64/$latestVersion/Docker%20Desktop%20Installer.exe"
            $fileSize = 0  # 未知大小
        }
        
        Write-Verbose "Docker Desktop 最新版本: $latestVersion"
        Write-Verbose "下载链接: $downloadUrl"
        
        return @{
            Url = $downloadUrl
            Version = $latestVersion
            Size = $fileSize
            # SHA256 应从官方渠道获取，这里设为空由用户验证
            SHA256 = ""
        }
    } catch {
        Write-Warning "无法获取最新版本信息，使用已知最新版本: 4.26.1"
        return @{
            Url = "https://desktop.docker.com/win/main/amd64/4.26.1/Docker%20Desktop%20Installer.exe"
            Version = "4.26.1"
            Size = 550MB
            SHA256 = ""
        }
    }
}

function Get-RancherDesktopDownloadUrl {
    <#
    .SYNOPSIS
        获取 Rancher Desktop 最新稳定版下载链接
    .DESCRIPTION
        从 GitHub API 动态获取最新版本号（修复 H4）
    .OUTPUTS
        Hashtable - 包含 URL、版本号、文件大小
    #>
    
    try {
        # 从 GitHub Releases API 获取最新版本
        $response = Invoke-RestMethod -Uri "https://api.github.com/repos/rancher-sandbox/rancher-desktop/releases/latest" -ErrorAction Stop
        $latestVersion = $response.tag_name -replace '^v', ''
        
        $asset = $response.assets | Where-Object { $_.name -like "*.exe" }
        
        if ($asset) {
            $downloadUrl = $asset.browser_download_url
            $fileSize = $asset.size
        } else {
            $downloadUrl = "https://github.com/rancher-sandbox/rancher-desktop/releases/download/v$latestVersion/Rancher.Desktop.Setup.$latestVersion.exe"
            $fileSize = 0
        }
        
        Write-Verbose "Rancher Desktop 最新版本: $latestVersion"
        Write-Verbose "下载链接: $downloadUrl"
        
        return @{
            Url = $downloadUrl
            Version = $latestVersion
            Size = $fileSize
            SHA256 = ""
        }
    } catch {
        Write-Warning "无法获取 Rancher Desktop 最新版本信息，使用已知最新版本: 1.12.0"
        return @{
            Url = "https://github.com/rancher-sandbox/rancher-desktop/releases/download/v1.12.0/Rancher.Desktop.Setup.1.12.0.exe"
            Version = "1.12.0"
            Size = 150MB
            SHA256 = ""
        }
    }
}

function Test-DownloadIntegrity {
    <#
    .SYNOPSIS
        验证下载文件的完整性（修复 H5: 添加 SHA256 哈希校验）
    
    .PARAMETER FilePath
        下载的文件路径
    
    .PARAMETER ExpectedSize
        预期的文件大小（字节），0 表示不检查大小
    
    .PARAMETER ExpectedSHA256
        预期的 SHA256 哈希值，空字符串表示不检查哈希
    
    .OUTPUTS
        Boolean - True 表示验证通过
    #>
    param(
        [string]$FilePath,
        [long]$ExpectedSize = 0,
        [string]$ExpectedSHA256 = ""
    )
    
    if (-not (Test-Path $FilePath)) {
        Write-Host "❌ 文件不存在: $FilePath" -ForegroundColor Red
        return $false
    }
    
    $actualSize = (Get-Item $FilePath).Length
    
    # 检查文件大小（如果提供了预期大小）
    if ($ExpectedSize -gt 0) {
        # 允许 5% 的容差（修复 EC-46）
        $tolerance = $ExpectedSize * 0.05
        if ([Math]::Abs($actualSize - $ExpectedSize) -gt $tolerance) {
            Write-Host "⚠️  文件大小超出容差范围" -ForegroundColor Yellow
            Write-Host "   预期: $([Math]::Round($ExpectedSize / 1MB, 1)) MB (±5%)" -ForegroundColor Gray
            Write-Host "   实际: $([Math]::Round($actualSize / 1MB, 1)) MB" -ForegroundColor Gray
            return $false
        }
        Write-Host "✅ 文件大小验证通过 ($([Math]::Round($actualSize / 1MB, 1)) MB)" -ForegroundColor Green
    }
    
    # SHA256 哈希校验（如果提供了预期哈希）
    if (-not [string]::IsNullOrWhiteSpace($ExpectedSHA256)) {
        Write-Host "🔐 计算 SHA256 哈希..." -ForegroundColor Cyan
        $actualHash = (Get-FileHash -Path $FilePath -Algorithm SHA256).Hash
        
        if ($actualHash -ne $ExpectedSHA256) {
            Write-Host "❌ SHA256 哈希不匹配!" -ForegroundColor Red
            Write-Host "   预期: $ExpectedSHA256" -ForegroundColor Gray
            Write-Host "   实际: $actualHash" -ForegroundColor Gray
            return $false
        }
        Write-Host "✅ SHA256 哈希验证通过" -ForegroundColor Green
    }
    
    return $true
}

function Start-DownloadWithProgress {
    <#
    .SYNOPSIS
        下载文件并显示进度
    
    .PARAMETER Url
        下载链接
    
    .PARAMETER OutputPath
        保存路径
    
    .OUTPUTS
        Boolean - True 表示下载成功
    #>
    param(
        [string]$Url,
        [string]$OutputPath
    )
    
    Write-Host "📥 开始下载..." -ForegroundColor Cyan
    Write-Host "   URL: $Url" -ForegroundColor Gray
    Write-Host "   保存至: $OutputPath" -ForegroundColor Gray
    Write-Host ""
    
    try {
        # 使用 BitsTransfer 或 Invoke-WebRequest 下载
        if (Get-Module -ListAvailable -Name BitsTransfer) {
            # Windows BITS (Background Intelligent Transfer Service)
            Start-BitsTransfer -Source $Url -Destination $OutputPath -DisplayName "SISYS Docker 下载" -Description "正在下载 Docker 安装程序..."
        } else {
            # 备用下载方法
            Invoke-WebRequest -Uri $Url -OutFile $OutputPath -UseBasicParsing
        }
        
        Write-Host ""
        Write-Host "✅ 下载完成!" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "❌ 下载失败: $_" -ForegroundColor Red
        return $false
    }
}

function Get-EstimatedDownloadTime {
    <#
    .SYNOPSIS
        估算下载时间
    
    .PARAMETER FileSizeBytes
        文件大小（字节）
    
    .PARAMETER SpeedMbps
        网速（Mbps）
    
    .OUTPUTS
        string - 预估时间字符串
    #>
    param(
        [long]$FileSizeBytes,
        [double]$SpeedMbps = 20  # 默认 20Mbps
    )
    
    # 转换为 Mb (megabits)
    $fileSizeMb = ($FileSizeBytes * 8) / 1MB
    $timeSeconds = $fileSizeMb / $SpeedMbps
    
    if ($timeSeconds -lt 60) {
        return "约 $([math]::Ceiling($timeSeconds)) 秒"
    } elseif ($timeSeconds -lt 3600) {
        return "约 $([math]::Ceiling($timeSeconds / 60)) 分钟"
    } else {
        return "约 $([math]::Ceiling($timeSeconds / 3600)) 小时"
    }
}

function Show-DockerLicenseNotice {
    <#
    .SYNOPSIS
        显示 Docker Desktop 许可条款说明
    #>
    
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
    Write-Host "⚠️  Docker Desktop 许可条款说明" -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Docker Desktop 订阅服务条款：" -ForegroundColor White
    Write-Host ""
    Write-Host "✅ 以下用户可继续使用：" -ForegroundColor Green
    Write-Host "   - 个人用户（非商业用途）" -ForegroundColor Gray
    Write-Host "   - 教育机构" -ForegroundColor Gray
    Write-Host "   - 非营利组织" -ForegroundColor Gray
    Write-Host "   - 小型企业（员工 < 250 人 且 年收入 < $10M）" -ForegroundColor Gray
    Write-Host ""
    Write-Host "❌ 以下用户需要付费订阅：" -ForegroundColor Red
    Write-Host "   - 大型企业（员工 ≥ 250 人 或 年收入 ≥ $10M）" -ForegroundColor Gray
    Write-Host ""
    Write-Host "详细信息: https://www.docker.com/pricing/faq/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "💡 替代方案：" -ForegroundColor Yellow
    Write-Host "   - Rancher Desktop（开源免费）" -ForegroundColor Gray
    Write-Host "   - Podman Desktop（开源免费）" -ForegroundColor Gray
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
    Write-Host ""
}

# ============================================================================
# 主逻辑
# ============================================================================

Write-Host "🎯 Docker 下载管理器" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
Write-Host ""

# 显示许可条款（如果选择 Docker Desktop）
if ($DownloadTarget -eq "DockerDesktop") {
    Show-DockerLicenseNotice
}

# 获取下载链接
if ($DownloadTarget -eq "DockerDesktop") {
    $downloadUrl = Get-DockerDesktopDownloadUrl
    $outputFile = Join-Path $DownloadPath "DockerDesktopInstaller.exe"
    $expectedSize = 550MB  # 约 550MB
} else {
    $downloadUrl = Get-RancherDesktopDownloadUrl
    $outputFile = Join-Path $DownloadPath "RancherDesktopInstaller.exe"
    $expectedSize = 150MB  # 约 150MB
}

# 估算下载时间
$estimatedTime = Get-EstimatedDownloadTime -FileSizeBytes $expectedSize
Write-Host "📊 下载信息" -ForegroundColor Cyan
Write-Host "   文件大小: $([math]::Round($expectedSize / 1MB, 1)) MB" -ForegroundColor Gray
Write-Host "   预计时长: $estimatedTime（基于 20Mbps 网速）" -ForegroundColor Gray
Write-Host ""

# 执行下载
$downloadOk = Start-DownloadWithProgress -Url $downloadUrl -OutputPath $outputFile

if ($downloadOk) {
    # 验证完整性
    $integrityOk = Test-DownloadIntegrity -FilePath $outputFile -ExpectedSize $expectedSize
    
    if ($integrityOk) {
        Write-Host ""
        Write-Host "✅ Docker 安装程序下载完成！" -ForegroundColor Green
        Write-Host "   文件位置: $outputFile" -ForegroundColor Gray
        exit 0
    } else {
        Write-Host "⚠️  文件完整性验证失败" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "❌ 下载失败" -ForegroundColor Red
    exit 1
}
