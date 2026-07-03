@echo off
setlocal
chcp 65001 >nul

title Gerar Instalador - Mistica Presentes

echo ==============================================
echo  Gerador do Instalador - Mistica Presentes
echo  Windows 10 e Windows 11
echo ==============================================
echo.

cd /d "%~dp0.."

python -m pip install --upgrade pyinstaller fastapi uvicorn

if exist build rmdir /S /Q build
if exist dist rmdir /S /Q dist
if exist MisticaPresentes.spec del /Q MisticaPresentes.spec
if exist ServidorMisticaApp.spec del /Q ServidorMisticaApp.spec

python -m PyInstaller --noconfirm --onedir --windowed --name "MisticaPresentes" --add-data "mistica_presentes.py;." --add-data "app_runtime_patch.py;." --add-data "app_frajola_patch.py;." --add-data "app_sync_status_patch.py;." --add-data "app_scroll_patch.py;." --add-data "config.py;." --add-data "database;database" --add-data "services;services" --add-data "isis;isis" --add-data "backend;backend" app.py

python -m PyInstaller --noconfirm --onedir --console --name "ServidorMisticaApp" --add-data "backend;backend" --add-data "database;database" --add-data "services;services" --add-data "config.py;." servidor_app.py

set "PACOTE=%USERPROFILE%\Desktop\Instalador_Mistica_Presentes"
if exist "%PACOTE%" rmdir /S /Q "%PACOTE%"
mkdir "%PACOTE%"

xcopy "dist\MisticaPresentes" "%PACOTE%\MisticaPresentes" /E /I /Y
xcopy "dist\ServidorMisticaApp" "%PACOTE%\ServidorMisticaApp" /E /I /Y
copy /Y "installer\Instalar_Mistica_Presentes.bat" "%PACOTE%\Instalar_Mistica_Presentes.bat"

echo.
echo Instalador criado em:
echo %PACOTE%
echo.
echo Para instalar em outro computador, copie a pasta inteira:
echo Instalador_Mistica_Presentes
echo.
echo Depois execute:
echo Instalar_Mistica_Presentes.bat
echo.
pause
endlocal
