param(
  [string]$HostName = "127.0.0.1",
  [int]$Port = 3000
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $RepoRoot "frontend"

Push-Location $FrontendDir
try {
  & npm.cmd run dev -- --hostname $HostName --port $Port
}
finally {
  Pop-Location
}
