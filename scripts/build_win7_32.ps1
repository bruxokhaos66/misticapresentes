$ErrorActionPreference = "Stop"

Write-Host "== Mística Presentes - Build Windows 7 32 bits =="
Write-Host "Use Python 3.8.x 32-bit. Em GitHub Actions, setup-python usa architecture x86."

python -m pip install --upgrade "pip<25"
python -m pip install -r requirements-win7-32.txt

python - <<'PY'
import sqlite3, sys
print('SQLite OK:', sqlite3.sqlite_version)
print('Python:', sys.version)
PY

if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist\MisticaPresentes) { Remove-Item dist\MisticaPresentes -Recurse -Force }

$pythonPrefix = python -c "import sys; print(sys.base_prefix)"
$dllDir = Join-Path $pythonPrefix "DLLs"
$sqlitePyd = Join-Path $dllDir "_sqlite3.pyd"
$sqliteDll = Join-Path $dllDir "sqlite3.dll"

if (!(Test-Path $sqlitePyd)) { throw "_sqlite3.pyd não encontrado em $dllDir" }
if (!(Test-Path $sqliteDll)) { throw "sqlite3.dll não encontrado em $dllDir" }

$addData = @(
  "mistica_presentes.py;."
  "config.py;."
  "app_version.py;."
  "auto_updater.py;."
  "app_runtime_patch.py;."
  "app_sync_status_patch.py;."
  "app_painel_guard_patch.py;."
  "app_scroll_patch.py;."
  "database;database"
  "services;services"
  "assets;assets"
)

$args = @(
  "--noconfirm"
  "--clean"
  "--windowed"
  "--name", "MisticaPresentes"
  "--distpath", "dist"
  "--workpath", "build"
  "--hidden-import=sqlite3"
  "--hidden-import=_sqlite3"
  "--collect-submodules=sqlite3"
  "--add-binary", "$sqlitePyd;."
  "--add-binary", "$sqliteDll;."
)

foreach ($item in $addData) {
  if (Test-Path ($item.Split(';')[0])) {
    $args += "--add-data"
    $args += $item
  }
}

$args += "--hidden-import=customtkinter"
$args += "--hidden-import=PIL._tkinter_finder"
$args += "--hidden-import=pyttsx3.drivers"
$args += "--hidden-import=pyttsx3.drivers.sapi5"
$args += "app.py"

python -m PyInstaller @args

if (!(Test-Path dist\MisticaPresentes\MisticaPresentes.exe)) {
  throw "Build falhou: exe não encontrado."
}

if (!(Test-Path dist\MisticaPresentes\_sqlite3.pyd)) {
  throw "Build falhou: _sqlite3.pyd não foi empacotado."
}

if (!(Test-Path dist\MisticaPresentes\sqlite3.dll)) {
  throw "Build falhou: sqlite3.dll não foi empacotado."
}

Write-Host "Build concluído: dist\MisticaPresentes\MisticaPresentes.exe"
Write-Host "SQLite empacotado com sucesso."
