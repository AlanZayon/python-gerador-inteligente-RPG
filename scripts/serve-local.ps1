
# Serve Arcane Forge from this machine to friends: API + worker + Tailscale Funnel.
# Prereqs: 9router running on :20128, Redis reachable via REDIS_URL, Tailscale logged in with Funnel enabled.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\serve-local.ps1 [-Port 5000]

param(
    [int]$Port = 5000
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "venv\Scripts\python.exe"

function Test-Port([int]$p) {
    $client = New-Object System.Net.Sockets.TcpClient

    try {
        $client.ConnectAsync("127.0.0.1", $p).Wait(1000) | Out-Null
        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

# Validate Python environment
if (-not (Test-Path $python)) {
    throw "venv not found at $python"
}

# Validate Tailscale
if (-not (Get-Command tailscale -ErrorAction SilentlyContinue)) {
    throw "tailscale CLI not found (winget install Tailscale.Tailscale)"
}

# Validate 9router
if (-not (Test-Port 20128)) {
    Write-Warning "9router is not answering on :20128 - GM turns and generation will fail."
}

# Validate environment configuration
$envFile = Join-Path $root ".env"

if (-not (Test-Path $envFile)) {
    throw ".env file not found at $envFile"
}

$envText = Get-Content $envFile -Raw

if ($envText -match "(?im)^\s*AUTH_DEV_MODE\s*=\s*true\s*$") {
    throw "AUTH_DEV_MODE=true in .env: anyone with the Funnel URL would get in. Set it to false and configure Clerk."
}

# Start API
$apiCommand = "`$host.UI.RawUI.WindowTitle = 'Arcane API'; Set-Location '$root'; & '$python' app.py"

Start-Process powershell.exe `
    -WorkingDirectory $root `
    -ArgumentList @("-NoExit", "-Command", $apiCommand)

# Start Worker
$workerCommand = "`$host.UI.RawUI.WindowTitle = 'Arcane Worker'; Set-Location '$root'; & '$python' worker.py"

Start-Process powershell.exe `
    -WorkingDirectory $root `
    -ArgumentList @("-NoExit", "-Command", $workerCommand)

# Expose API through Tailscale Funnel
tailscale funnel --bg $Port

# Show Funnel status
tailscale funnel status
