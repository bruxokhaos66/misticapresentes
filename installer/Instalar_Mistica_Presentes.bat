@echo off
setlocal
chcp 65001 >nul

title Instalador - Mistica Presentes

echo ==============================================
echo  Instalador - Mistica Presentes
echo  Windows 10 e Windows 11
echo ==============================================
echo.

set "ORIGEM=%~dp0"
set "DESTINO=%LOCALAPPDATA%\MisticaPresentes"
set "DESKTOP=%USERPROFILE%\Desktop"

if not exist "%DESTINO%" mkdir "%DESTINO%"

if exist "%ORIGEM%MisticaPresentes" (
  xcopy "%ORIGEM%MisticaPresentes" "%DESTINO%\MisticaPresentes" /E /I /Y
) else if exist "%ORIGEM%MisticaPresentes.exe" (
  if not exist "%DESTINO%\MisticaPresentes" mkdir "%DESTINO%\MisticaPresentes"
  copy /Y "%ORIGEM%MisticaPresentes.exe" "%DESTINO%\MisticaPresentes\MisticaPresentes.exe"
) else (
  echo ERRO: programa nao encontrado junto do instalador.
  pause
  exit /b 1
)

if exist "%ORIGEM%ServidorMisticaApp" (
  xcopy "%ORIGEM%ServidorMisticaApp" "%DESTINO%\ServidorMisticaApp" /E /I /Y
) else if exist "%ORIGEM%ServidorMisticaApp.exe" (
  if not exist "%DESTINO%\ServidorMisticaApp" mkdir "%DESTINO%\ServidorMisticaApp"
  copy /Y "%ORIGEM%ServidorMisticaApp.exe" "%DESTINO%\ServidorMisticaApp\ServidorMisticaApp.exe"
) else (
  echo AVISO: servidor local nao encontrado junto do instalador.
)

copy /Y "%DESTINO%\MisticaPresentes\MisticaPresentes.exe" "%DESKTOP%\MisticaPresentes.exe"

if exist "%DESTINO%\ServidorMisticaApp\ServidorMisticaApp.exe" (
  copy /Y "%DESTINO%\ServidorMisticaApp\ServidorMisticaApp.exe" "%DESKTOP%\ServidorMisticaApp.exe"
)

echo.
echo Instalacao concluida.
echo Arquivos criados na Area de Trabalho:
echo - MisticaPresentes.exe
echo - ServidorMisticaApp.exe
echo.
pause
endlocal
