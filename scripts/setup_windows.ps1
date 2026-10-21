# Instala uv (si falta), Python y todas las dependencias del proyecto.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host ">> Instalando uv..."
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

Write-Host ">> Instalando Python gestionado por uv..."
uv python install
Write-Host ">> Creando .venv e instalando dependencias..."
uv sync

Write-Host ""
Write-Host "Listo. Comandos utiles:"
Write-Host "  uv run arenahub"
Write-Host "  uv run pyinstaller ArenaHub.spec --clean --noconfirm"
