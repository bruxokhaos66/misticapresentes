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
set "APPDIR=%DESTINO%\MisticaPresentes"
set "DESKTOP=%USERPROFILE%\Desktop"
set "ATALHO=%DESKTOP%\Mistica Presentes.lnk"

if not exist "%DESTINO%" mkdir "%DESTINO%"

if exist "%ORIGEM%MisticaPresentes" (
  xcopy "%ORIGEM%MisticaPresentes" "%APPDIR%" /E /I /Y
) else if exist "%ORIGEM%MisticaPresentes.exe" (
  if not exist "%APPDIR%" mkdir "%APPDIR%"
  copy /Y "%ORIGEM%MisticaPresentes.exe" "%APPDIR%\MisticaPresentes.exe"
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

if exist "%ORIGEM%Atualizar_Mistica_Online.bat" (
  copy /Y "%ORIGEM%Atualizar_Mistica_Online.bat" "%DESTINO%\Atualizar_Mistica_Online.bat"
  copy /Y "%ORIGEM%Atualizar_Mistica_Online.bat" "%DESKTOP%\Atualizar_Mistica_Online.bat"
)

set "TARGET=%APPDIR%\MisticaLauncher.exe"
if not exist "%TARGET%" set "TARGET=%APPDIR%\MisticaPresentes.exe"
set "ICON=%APPDIR%\mistica_xamanico_moderno.ico"
if not exist "%ICON%" set "ICON=%TARGET%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%ATALHO%'); $Shortcut.TargetPath = '%TARGET%'; $Shortcut.WorkingDirectory = '%APPDIR%'; $Shortcut.IconLocation = '%ICON%'; $Shortcut.Description = 'Mistica Presentes - abrir pelo Launcher'; $Shortcut.Save()"

if exist "%DESKTOP%\MisticaPresentes.exe" del /f /q "%DESKTOP%\MisticaPresentes.exe"
if exist "%DESKTOP%\MisticaLauncher.exe" del /f /q "%DESKTOP%\MisticaLauncher.exe"

if exist "%DESTINO%\ServidorMisticaApp\ServidorMisticaApp.exe" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%DESKTOP%\Servidor Mística App.lnk'); $Shortcut.TargetPath = '%DESTINO%\ServidorMisticaApp\ServidorMisticaApp.exe'; $Shortcut.WorkingDirectory = '%DESTINO%\ServidorMisticaApp'; $Shortcut.Description = 'Servidor local da Mistica Presentes'; $Shortcut.Save()"
)

echo.
echo Instalacao concluida.
echo.
echo Atalho principal criado na Area de Trabalho:
echo - Mistica Presentes.lnk
echo.
echo IMPORTANTE:
echo Sempre abra o sistema pelo atalho Mistica Presentes.
echo Ele aponta para o MisticaLauncher.exe, que verifica atualizacoes antes de abrir.
echo.
pause
endlocal
