$ErrorActionPreference = "Stop"

Write-Host "Mistica Presentes - Build Windows EXE" -ForegroundColor Cyan

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = "python"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ExeName = "Mistica Presentes.exe"
$DistExe = Join-Path $Root "dist\$ExeName"
$DesktopExe = Join-Path $Desktop $ExeName

Write-Host "Pasta do projeto: $Root"
Write-Host "Area de Trabalho: $Desktop"

if (!(Test-Path ".venv")) {
    Write-Host "Criando ambiente virtual .venv..." -ForegroundColor Yellow
    & $Python -m venv .venv
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

Write-Host "Atualizando pip..." -ForegroundColor Yellow
& $VenvPython -m pip install --upgrade pip

Write-Host "Instalando dependencias..." -ForegroundColor Yellow
& $VenvPython -m pip install -r requirements.txt

Write-Host "Executando testes..." -ForegroundColor Yellow
& $VenvPython -m pytest

Write-Host "Limpando builds antigos..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }
if (Test-Path "Mistica Presentes.spec") { Remove-Item "Mistica Presentes.spec" -Force }

Write-Host "Gerando EXE com PyInstaller..." -ForegroundColor Yellow
& $VenvPython -m PyInstaller `
    --onefile `
    --windowed `
    --name "Mistica Presentes" `
    --collect-all customtkinter `
    --collect-submodules services `
    --collect-submodules repositories `
    --collect-submodules reports `
    --collect-submodules isis `
    --collect-submodules ui `
    app.py

if (!(Test-Path $DistExe)) {
    throw "EXE nao encontrado em: $DistExe"
}

Copy-Item $DistExe $DesktopExe -Force

Write-Host "Build concluido com sucesso!" -ForegroundColor Green
Write-Host "EXE salvo em: $DesktopExe" -ForegroundColor Green
