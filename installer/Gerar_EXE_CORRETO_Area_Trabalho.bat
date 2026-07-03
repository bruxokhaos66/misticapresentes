@echo off
setlocal
chcp 65001 >nul

title Gerar EXE Correto - Mistica Presentes

echo ==============================================
echo  Gerando EXE correto - Mistica Presentes
echo  Windows 10 e Windows 11
echo ==============================================
echo.

cd /d "%~dp0.."

python -m pip install pyinstaller

if exist build rmdir /S /Q build
if exist dist rmdir /S /Q dist

python -m PyInstaller --noconfirm MisticaPresentes_CORRETO.spec

set "PASTA=%USERPROFILE%\Desktop\mistica exe correto"
if not exist "%PASTA%" mkdir "%PASTA%"
copy /Y "dist\MisticaPresentes_CORRETO.exe" "%PASTA%\MisticaPresentes_CORRETO.exe"

echo.
echo EXE correto criado em:
echo %PASTA%\MisticaPresentes_CORRETO.exe
echo.
pause
endlocal
