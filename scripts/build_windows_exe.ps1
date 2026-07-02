$ErrorActionPreference = "Stop"

Write-Host "Mistica Presentes - Build Windows EXE" -ForegroundColor Cyan

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = "python"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ExeName = "Mistica Presentes.exe"
$DistExe = Join-Path $Root "dist\$ExeName"
$DesktopExe = Join-Path $Desktop $ExeName
$AssetsDir = Join-Path $Root "assets"
$IconPath = Join-Path $AssetsDir "mistica_presentes.ico"

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

Write-Host "Gerando icone do aplicativo..." -ForegroundColor Yellow
if (!(Test-Path $AssetsDir)) { New-Item -ItemType Directory -Path $AssetsDir | Out-Null }
$IconScript = @'
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path.cwd()
assets = root / "assets"
assets.mkdir(exist_ok=True)
ico = assets / "mistica_presentes.ico"

size = 256
img = Image.new("RGBA", (size, size), (26, 18, 33, 255))
d = ImageDraw.Draw(img)

# borda dourada e círculo central
d.rounded_rectangle((10, 10, size - 10, size - 10), radius=38, outline=(216, 181, 109, 255), width=10)
d.ellipse((52, 44, size - 52, size - 60), outline=(216, 181, 109, 255), width=5)

# lua/símbolo discreto
d.arc((74, 58, 182, 166), start=78, end=282, fill=(216, 181, 109, 255), width=9)
d.polygon([(128, 34), (138, 68), (174, 68), (145, 88), (156, 122), (128, 101), (100, 122), (111, 88), (82, 68), (118, 68)], fill=(216, 181, 109, 255))

try:
    font_big = ImageFont.truetype("arialbd.ttf", 62)
    font_small = ImageFont.truetype("arial.ttf", 20)
except Exception:
    font_big = ImageFont.load_default()
    font_small = ImageFont.load_default()

texto = "MP"
bbox = d.textbbox((0, 0), texto, font=font_big)
d.text(((size - (bbox[2]-bbox[0])) / 2, 132), texto, font=font_big, fill=(255, 244, 214, 255))
sub = "Mistica"
bbox2 = d.textbbox((0, 0), sub, font=font_small)
d.text(((size - (bbox2[2]-bbox2[0])) / 2, 196), sub, font=font_small, fill=(216, 181, 109, 255))

img.save(ico, sizes=[(256,256), (128,128), (64,64), (48,48), (32,32), (16,16)])
print(ico)
'@
$IconScriptPath = Join-Path $env:TEMP "gerar_icone_mistica.py"
Set-Content -Path $IconScriptPath -Value $IconScript -Encoding UTF8
& $VenvPython $IconScriptPath

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
    --icon "$IconPath" `
    --add-data "$IconPath;assets" `
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
Write-Host "Icone usado: $IconPath" -ForegroundColor Green
