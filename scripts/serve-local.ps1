# Serve Arcane Forge from this machine to friends: API + worker + Tailscale Funnel.
# Prereqs: 9router running on :20128, Redis reachable via REDIS_URL, Tailscale logged in with Funnel enabled.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\serve-local.ps1 [-Port 5000]

param([int]$Port = 5000)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "venv\Scripts\python.exe"

function Test-Port([int]$p) {
    $client = New-Object System.Net.Sockets.TcpClient
    try { $client.ConnectAsync("127.0.0.1", $p).Wait(1000) -and $client.Connected } catch { $false } finally { $client.Dispose() }
}

if (-not (Test-Path $python)) { throw "venv not found at $python" }
if (-not (Get-Command tailscale -ErrorAction SilentlyContinue)) { throw "tailscale CLI not found (winget install Tailscale.Tailscale)" }
if (-not (Test-Port 20128)) { Write-Warning "9router is not answering on :20128 — GM turns and generation will fail." }

$envFile = Join-Path $root ".env"
$envText = Get-Content $envFile -Raw
if ($envText -match "(?m)^AUTH_DEV_MODE=true") { throw "AUTH_DEV_MODE=true in .env: anyone with the Funnel URL would get in. Set it to false and configure Clerk." }

Start-Process powershell -WorkingDirectory $root -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='Arcane API'; & '$python' app.py"
Start-Process powershell -WorkingDirectory $root -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='Arcane Worker'; & '$python' worker.py"

tailscale funnel --bg $Port
tailscale funnel status
