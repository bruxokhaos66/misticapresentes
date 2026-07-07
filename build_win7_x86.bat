@echo off
setlocal
cd /d "%~dp0"

echo ======================================================
echo  Build Mística Presentes - Windows 7 Professional 32 bits
echo  Saida esperada: dist\MisticaPresentes-Win7-x86.exe
echo ======================================================
echo.

set "PY_CMD=py -3.8-32"
%PY_CMD% --version >nul 2>&1
if errorlevel 1 (
  echo ERRO: Python 3.8 32 bits nao encontrado pelo comando: %PY_CMD%
  echo.
  echo Instale o Python 3.8.10 Windows x86 e marque Add Python to PATH.
  echo Depois rode este arquivo novamente.
  pause
  exit /b 1
)

%PY_CMD% -c "import struct, sys; raise SystemExit(0 if struct.calcsize('P')*8 == 32 else 1)"
if errorlevel 1 (
  echo ERRO: o Python encontrado nao e 32 bits.
  echo Use Python 3.8.10 Windows x86 para gerar executavel compativel com Windows 7 32 bits.
  pause
  exit /b 1
)

echo Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist MisticaPresentes-Win7-x86.spec del /q MisticaPresentes-Win7-x86.spec

echo Instalando dependencias Win7 x86...
%PY_CMD% -m pip install --upgrade pip setuptools wheel
%PY_CMD% -m pip install -r requirements-win7-x86.txt
if errorlevel 1 (
  echo.
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
  --hidden-import=isis ^
  --hidden-import=isis.memory ^
  --hidden-import=services.isis_service ^
  --collect-all isis ^
  --collect-submodules isis ^
  --collect-submodules services ^
  app.py

if errorlevel 1 (
  echo.
  echo ERRO: falha ao gerar o executavel Win7 x86.
  pause
  exit /b 1
)

echo.
echo OK: executavel gerado em dist\MisticaPresentes-Win7-x86.exe
echo.
echo Copie esse arquivo para o computador Windows 7 Professional 32 bits.
echo Se nao abrir, instale o Microsoft Visual C++ Redistributable 2015-2022 x86.
pause
