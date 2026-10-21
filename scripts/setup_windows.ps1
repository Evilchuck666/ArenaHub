# Development setup: installs uv if missing, a uv-managed Python and every
# project dependency into .venv\. No system Python is needed.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host ">> Installing uv..."
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

Write-Host ">> Installing the uv-managed Python..."
uv python install
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host ">> Creating .venv and installing dependencies..."
uv sync
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Done. Useful commands:"
Write-Host "  uv run arenahub                                        # run the app"
Write-Host "  uv run pytest                                          # run the tests"
Write-Host "  uv run pyinstaller ArenaHub.spec --clean --noconfirm   # single-file build in dist\"
