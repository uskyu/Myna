param(
  [int]$Port = 3456,
  [string]$DataDir = "$env:APPDATA\Myna",
  [switch]$NoBrowser,
  [switch]$Background
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Root "runtime\python\python.exe"
$Bootstrap = Join-Path $Root "scripts\windows\bootstrap.py"

if (!(Test-Path $Python)) {
  $Python = Join-Path $Root ".venv\Scripts\python.exe"
}

if (!(Test-Path $Python)) {
  $Python = "python"
}

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "db") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "uploads") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "workspaces") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "hermes\profiles") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "logs") | Out-Null

$env:PORT = "$Port"
$env:MYNA_DATA_DIR = $DataDir
$env:MYNA_DB_DIR = Join-Path $DataDir "db"
$env:MYNA_WORKSPACES_ROOT = Join-Path $DataDir "workspaces"
$env:MYNA_PROFILES_DIR = Join-Path $DataDir "hermes\profiles"
$env:HERMES_PATH = Join-Path $Root "vendor\hermes-agent"
$url = "http://127.0.0.1:$Port"
Write-Host "Starting Myna on $url"
Write-Host "Data directory: $DataDir"

$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
  Write-Host "Port $Port is already in use. Start with another port, for example:" -ForegroundColor Yellow
  Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\windows\start-myna.ps1 -Port 3457" -ForegroundColor Yellow
  exit 1
}

$outLog = Join-Path $DataDir "logs\myna.out.log"
$errLog = Join-Path $DataDir "logs\myna.err.log"

if ($Background) {
  $bootstrapCmd = @(
    "`$env:PORT='$Port'"
    "`$env:MYNA_DATA_DIR='$DataDir'"
    "`$env:MYNA_DB_DIR='" + (Join-Path $DataDir "db") + "'"
    "`$env:MYNA_WORKSPACES_ROOT='" + (Join-Path $DataDir "workspaces") + "'"
    "`$env:MYNA_PROFILES_DIR='" + (Join-Path $DataDir "hermes\profiles") + "'"
    "`$env:HERMES_PATH='" + (Join-Path $Root "vendor\hermes-agent") + "'"
    "Set-Location '$Backend'"
    "& '$Python' '$Bootstrap'"
  ) -join "; "

  $proc = Start-Process -FilePath "powershell.exe" `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $bootstrapCmd) `
    -WorkingDirectory $Backend `
    -WindowStyle Hidden `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -PassThru

  $healthy = $false
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    if ($proc.HasExited) {
      Write-Host "Myna failed to start. Check logs:" -ForegroundColor Red
      Write-Host "  $outLog"
      Write-Host "  $errLog"
      exit 1
    }
    try {
      $resp = Invoke-WebRequest -UseBasicParsing "$url/health" -TimeoutSec 2
      if ($resp.StatusCode -eq 200) {
        $healthy = $true
        break
      }
    } catch {}
  }

  if (-not $healthy) {
    Write-Host "Myna did not become ready in time. Check logs:" -ForegroundColor Red
    Write-Host "  $outLog"
    Write-Host "  $errLog"
    exit 1
  }

  if (!$NoBrowser) {
    Start-Process $url | Out-Null
  }

  Write-Host "Myna is running at $url"
  Write-Host "Logs:"
  Write-Host "  $outLog"
  Write-Host "  $errLog"
  exit 0
}

Push-Location $Backend
try {
  & $Python $Bootstrap
}
finally {
  Pop-Location
}
