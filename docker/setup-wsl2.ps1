# sisys - WSL 2 Setup Script for Windows
# This PowerShell script automates WSL 2 and Docker Engine setup
# Run from PowerShell (Administrator)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  sisys - WSL 2 Setup Script" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] Please run this script as Administrator (Right-click > Run as Administrator)" -ForegroundColor Red
    exit 1
}

Write-Host "[INFO] Running as Administrator" -ForegroundColor Green
Write-Host ""

# Step 1: Enable WSL
Write-Host "[STEP 1/5] Enabling WSL..." -ForegroundColor Yellow
try {
    wsl --install
    Write-Host "[OK] WSL enabled" -ForegroundColor Green
} catch {
    Write-Host "[WARN] WSL may already be enabled: $_" -ForegroundColor Yellow
}
Write-Host ""

# Step 2: Set WSL 2 as default
Write-Host "[STEP 2/5] Setting WSL 2 as default..." -ForegroundColor Yellow
try {
    wsl --set-default-version 2
    Write-Host "[OK] WSL 2 set as default" -ForegroundColor Green
} catch {
    Write-Host "[WARN] May already be set: $_" -ForegroundColor Yellow
}
Write-Host ""

# Step 3: Install Ubuntu 22.04
Write-Host "[STEP 3/5] Installing Ubuntu 22.04..." -ForegroundColor Yellow
try {
    wsl --install -d Ubuntu-22.04
    Write-Host "[OK] Ubuntu 22.04 installed" -ForegroundColor Green
    Write-Host "[INFO] Please restart your computer after installation completes" -ForegroundColor Cyan
} catch {
    Write-Host "[WARN] Ubuntu may already be installed: $_" -ForegroundColor Yellow
}
Write-Host ""

# Step 4: Verify WSL installation
Write-Host "[STEP 4/5] Verifying WSL installation..." -ForegroundColor Yellow
wsl --list --verbose
Write-Host ""

# Step 5: Provide next steps
Write-Host "[STEP 5/5] Next Steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Restart your computer if prompted" -ForegroundColor White
Write-Host "2. Launch Ubuntu 22.04 from Start Menu or run: wsl" -ForegroundColor White
Write-Host "3. Complete Ubuntu setup (create username and password)" -ForegroundColor White
Write-Host "4. Run the Docker setup script inside Ubuntu:" -ForegroundColor White
Write-Host ""
Write-Host "   cd ~" -ForegroundColor Cyan
Write-Host "   git clone <repository-url>" -ForegroundColor Cyan
Write-Host "   cd sisys" -ForegroundColor Cyan
Write-Host "   bash docker/setup-wsl2-docker.sh" -ForegroundColor Cyan
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Ask for restart
$restart = Read-Host "Would you like to restart now? (y/n)"
if ($restart -eq "y") {
    Restart-Computer -Force
}
