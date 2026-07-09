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
set "PUBLICDESKTOP=%PUBLIC%\Desktop"

for /f "usebackq delims=" %%D in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESKTOP=%%D"
if "%DESKTOP%"=="" set "DESKTOP=%USERPROFILE%\Desktop"

if not exist "%DESTINO%" mkdir "%DESTINO%"
if not exist "%APPDIR%" mkdir "%APPDIR%"

if exist "%ORIGEM%MisticaPresentes" (
  xcopy "%ORIGEM%MisticaPresentes" "%APPDIR%" /E /I /Y
) else if exist "%ORIGEM%MisticaPresentes.exe" (
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
)

set "TARGET=%APPDIR%\MisticaLauncher.exe"
if not exist "%TARGET%" set "TARGET=%APPDIR%\MisticaPresentes.exe"
set "ICON=%APPDIR%\mistica_xamanico_moderno.ico"
if not exist "%ICON%" set "ICON=%TARGET%"

echo Criando atalho na Area de Trabalho...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$desktop=[Environment]::GetFolderPath('Desktop'); if([string]::IsNullOrWhiteSpace($desktop)){ $desktop='%DESKTOP%' }; if(!(Test-Path $desktop)){ New-Item -ItemType Directory -Force -Path $desktop | Out-Null }; $target='%TARGET%'; $work='%APPDIR%'; $icon='%ICON%'; $lnk=Join-Path $desktop 'Mistica Presentes.lnk'; $WshShell=New-Object -ComObject WScript.Shell; $Shortcut=$WshShell.CreateShortcut($lnk); $Shortcut.TargetPath=$target; $Shortcut.WorkingDirectory=$work; $Shortcut.IconLocation=$icon; $Shortcut.Description='Mistica Presentes - abrir pelo Launcher'; $Shortcut.Save(); Write-Host 'Atalho criado em:' $lnk"

if exist "%PUBLICDESKTOP%" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$target='%TARGET%'; $work='%APPDIR%'; $icon='%ICON%'; $desktop='%PUBLICDESKTOP%'; $lnk=Join-Path $desktop 'Mistica Presentes.lnk'; try { $WshShell=New-Object -ComObject WScript.Shell; $Shortcut=$WshShell.CreateShortcut($lnk); $Shortcut.TargetPath=$target; $Shortcut.WorkingDirectory=$work; $Shortcut.IconLocation=$icon; $Shortcut.Description='Mistica Presentes - abrir pelo Launcher'; $Shortcut.Save(); Write-Host 'Atalho publico criado em:' $lnk } catch { Write-Host 'Nao consegui criar atalho publico:' $_ }"
)

if exist "%DESKTOP%\MisticaPresentes.exe" del /f /q "%DESKTOP%\MisticaPresentes.exe"
if exist "%DESKTOP%\MisticaLauncher.exe" del /f /q "%DESKTOP%\MisticaLauncher.exe"

if exist "%DESTINO%\ServidorMisticaApp\ServidorMisticaApp.exe" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$desktop=[Environment]::GetFolderPath('Desktop'); if([string]::IsNullOrWhiteSpace($desktop)){ $desktop='%DESKTOP%' }; $WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut((Join-Path $desktop 'Servidor Mistica App.lnk')); $Shortcut.TargetPath = '%DESTINO%\ServidorMisticaApp\ServidorMisticaApp.exe'; $Shortcut.WorkingDirectory = '%DESTINO%\ServidorMisticaApp'; $Shortcut.Description = 'Servidor local da Mistica Presentes'; $Shortcut.Save()"
)

echo.
echo Instalacao concluida.
echo.
echo Atalho principal criado na Area de Trabalho:
echo - Mistica Presentes.lnk
echo.
echo Caminho detectado da Area de Trabalho:
echo %DESKTOP%
echo.
echo IMPORTANTE:
echo Sempre abra o sistema pelo atalho Mistica Presentes.
echo Ele aponta para o MisticaLauncher.exe, que verifica atualizacoes antes de abrir.
echo.
pause
endlocal
