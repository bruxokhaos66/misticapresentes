@echo off
setlocal
cd /d "%~dp0"

echo ======================================================
echo  Build Mistica Presentes - Windows 7 Professional 32 bits
echo  Saida esperada: dist\MisticaPresentes-Win7-x86.exe
echo ======================================================
echo.

set "PY_CMD=py -3.8-32"
%PY_CMD% --version >nul 2>&1
if errorlevel 1 (
  echo ERRO: Python 3.8 32 bits nao encontrado pelo comando: %PY_CMD%
  echo Instale o Python 3.8.10 Windows x86 e marque Add Python to PATH.
  pause
  exit /b 1
)

%PY_CMD% -c "import struct, sqlite3; print('SQLite:', sqlite3.sqlite_version); raise SystemExit(0 if struct.calcsize('P')*8 == 32 else 1)"
if errorlevel 1 (
  echo ERRO: o Python encontrado nao e 32 bits ou SQLite nao carregou.
  pause
  exit /b 1
)

for /f "usebackq delims=" %%P in (`%PY_CMD% -c "import sys; print(sys.base_prefix)"`) do set "PY_PREFIX=%%P"
set "SQLITE_PYD=%PY_PREFIX%\DLLs\_sqlite3.pyd"
set "SQLITE_DLL=%PY_PREFIX%\DLLs\sqlite3.dll"
if not exist "%SQLITE_PYD%" (
  echo ERRO: _sqlite3.pyd nao encontrado em %PY_PREFIX%\DLLs
  pause
  exit /b 1
)
if not exist "%SQLITE_DLL%" (
  echo ERRO: sqlite3.dll nao encontrado em %PY_PREFIX%\DLLs
  pause
  exit /b 1
)

echo Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist MisticaPresentes-Win7-x86.spec del /q MisticaPresentes-Win7-x86.spec

echo Instalando dependencias Win7 x86...
%PY_CMD% -m pip install --upgrade "pip<25" setuptools wheel
%PY_CMD% -m pip install -r requirements-win7-x86.txt
if errorlevel 1 (
  echo ERRO: falha ao instalar dependencias.
  pause
  exit /b 1
)

echo.
echo Gerando MisticaPresentes-Win7-x86.exe...
%PY_CMD% -m PyInstaller ^
  --onefile ^
  --windowed ^
  --name "MisticaPresentes-Win7-x86" ^
  --hidden-import=sqlite3 ^
  --hidden-import=_sqlite3 ^
  --hidden-import=isis ^
  --hidden-import=isis.memory ^
  --hidden-import=repositories ^
  --hidden-import=services ^
  --hidden-import=services.isis_service ^
  --hidden-import=customtkinter ^
  --hidden-import=PIL._tkinter_finder ^
  --hidden-import=pyttsx3.drivers ^
  --hidden-import=pyttsx3.drivers.sapi5 ^
  --collect-submodules=sqlite3 ^
  --collect-all=isis ^
  --collect-submodules=isis ^
  --collect-submodules=repositories ^
  --collect-submodules=services ^
  --add-data "database;database" ^
  --add-data "repositories;repositories" ^
  --add-data "services;services" ^
  --add-data "assets;assets" ^
  --add-data "mistica_presentes.py;." ^
  --add-data "config.py;." ^
  --add-data "app_version.py;." ^
  --add-data "auto_updater.py;." ^
  --add-binary "%SQLITE_PYD%;." ^
  --add-binary "%SQLITE_DLL%;." ^
  app.py

if errorlevel 1 (
  echo ERRO: falha ao gerar o executavel Win7 x86.
  pause
  exit /b 1
)

if not exist "dist\MisticaPresentes-Win7-x86.exe" (
  echo ERRO: executavel nao foi gerado.
  pause
  exit /b 1
)

echo.
echo OK: executavel gerado em dist\MisticaPresentes-Win7-x86.exe
pause
