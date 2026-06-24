param(
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  throw "Backend virtualenv not found. Run: cd backend; python -m venv .venv; .\.venv\Scripts\pip.exe install -r requirements.txt"
}

Push-Location $BackendDir
try {
  & $Python -m uvicorn app.main:app --host $HostName --port $Port
}
finally {
  Pop-Location
}
