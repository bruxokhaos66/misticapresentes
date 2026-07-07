@echo off
setlocal
cd /d "%~dp0"

echo Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist MisticaPresentes.spec del /q MisticaPresentes.spec

echo Gerando executavel Mística Presentes com pacote Isis...
python -m PyInstaller ^
  --onefile ^
  --windowed ^
  --name "MisticaPresentes" ^
  --hidden-import=isis ^
  --hidden-import=isis.memory ^
  --hidden-import=services.isis_service ^
  --collect-all isis ^
  --collect-submodules isis ^
  --collect-submodules services ^
  app.py

if errorlevel 1 (
  echo.
  echo ERRO: falha ao gerar o executavel.
  pause
  exit /b 1
)

echo.
echo OK: executavel gerado em dist\MisticaPresentes.exe
pause
