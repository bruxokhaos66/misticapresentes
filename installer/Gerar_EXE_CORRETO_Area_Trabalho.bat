@echo off
setlocal
chcp 65001 >nul

title Gerar EXE Correto - Mistica Presentes

echo ==============================================
echo  Gerando EXE correto - Mistica Presentes
echo ==============================================
echo.

cd /d "%~dp0.."

python -m pip install pyinstaller

if exist build rmdir /S /Q build
if exist dist rmdir /S /Q dist
if exist MisticaPresentes_CORRETO.spec del /Q MisticaPresentes_CORRETO.spec

python -m PyInstaller --noconfirm --onefile --windowed --name "MisticaPresentes_CORRETO" --add-data "mistica_presentes.py;." --add-data "app_runtime_patch.py;." --add-data "app_sync_status_patch.py;." --add-data "app_scroll_patch.py;." --add-data "config.py;." --add-data "database;database" --add-data "services;services" --add-data "isis;isis" --add-data "backend;backend" app.py

set "PASTA=%USERPROFILE%\Desktop\mistica exe correto"
if not exist "%PASTA%" mkdir "%PASTA%"
copy /Y "dist\MisticaPresentes_CORRETO.exe" "%PASTA%\MisticaPresentes_CORRETO.exe"

echo.
echo EXE correto criado em:
echo %PASTA%\MisticaPresentes_CORRETO.exe
echo.
pause
endlocal
