# NOVA - Advanced Local AI Agent and Workstation
# PowerShell Launcher

[Console]::Title = "NOVA - AI Workstation"
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "  NOVA -- Advanced Local AI Agent and Workstation" -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verify Python version
try {
    $pythonVer = python --version 2>&1
    Write-Host "[INFO] Detected $pythonVer" -ForegroundColor Gray
} catch {
    Write-Host "[ERROR] Python is not installed or not in system PATH." -ForegroundColor Red
    exit 1
}

# 2. Check Port 46815
$portInUse = Get-NetTCPConnection -LocalPort 46815 -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Host "[ERROR] Port 46815 is already occupied by process ID $($portInUse[0].OwningProcess)." -ForegroundColor Red
    Write-Host "Please stop the existing process or run stop.bat before launching NOVA." -ForegroundColor Red
    exit 1
}

# 3. Configure Path
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir
$env:PYTHONPATH = $scriptDir

# 4. Launch Browser delayed
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://127.0.0.1:46815"
} | Out-Null

Write-Host "[INFO] Starting NOVA on http://127.0.0.1:46815 ..." -ForegroundColor Green
Write-Host "[INFO] Press Ctrl+C to stop the workstation." -ForegroundColor Yellow
Write-Host ""

# 5. Run Uvicorn server
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 46815 --log-level info
