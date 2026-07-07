$ErrorActionPreference = "Stop"

Write-Host "== Mistica Presentes - Build Windows 7 32 bits =="

python -m pip install --upgrade "pip<25"
python -m pip install -r requirements-win7-32.txt
python -c "import sqlite3, sys; print('SQLite OK:', sqlite3.sqlite_version); print('Python:', sys.version)"

if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist\MisticaPresentes) { Remove-Item dist\MisticaPresentes -Recurse -Force }

$pythonPrefix = python -c "import sys; print(sys.base_prefix)"
$dllDir = Join-Path $pythonPrefix "DLLs"
$sqlitePyd = Join-Path $dllDir "_sqlite3.pyd"
$sqliteDll = Join-Path $dllDir "sqlite3.dll"

if (!(Test-Path $sqlitePyd)) { throw "_sqlite3.pyd not found in $dllDir" }
if (!(Test-Path $sqliteDll)) { throw "sqlite3.dll not found in $dllDir" }

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
  "repositories;repositories"
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
  "--hidden-import=repositories"
  "--collect-submodules=repositories"
  "--hidden-import=services"
  "--collect-submodules=services"
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

if (!(Test-Path dist\MisticaPresentes\MisticaPresentes.exe)) { throw "Build failed: exe not found." }
if (!(Test-Path dist\MisticaPresentes\_sqlite3.pyd)) { throw "Build failed: _sqlite3.pyd missing." }
if (!(Test-Path dist\MisticaPresentes\sqlite3.dll)) { throw "Build failed: sqlite3.dll missing." }
if (!(Test-Path dist\MisticaPresentes\repositories)) { throw "Build failed: repositories folder missing." }
if (!(Test-Path dist\MisticaPresentes\services)) { throw "Build failed: services folder missing." }

Write-Host "Build OK: dist\MisticaPresentes\MisticaPresentes.exe"
