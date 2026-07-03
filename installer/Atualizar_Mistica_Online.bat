@echo off
setlocal
chcp 65001 >nul

title Atualizar Mistica Presentes Online

echo ==============================================
echo  Atualizador Online - Mistica Presentes
echo ==============================================
echo.

set "URL=https://github.com/bruxokhaos66/misticapresentes/releases/download/mistica-latest/Instalador_Mistica_Presentes.zip"
set "TEMPZIP=%TEMP%\Instalador_Mistica_Presentes.zip"
set "TEMPDIR=%TEMP%\Instalador_Mistica_Presentes"

echo Baixando a versao mais recente...
curl -L "%URL%" -o "%TEMPZIP%"

if not exist "%TEMPZIP%" (
  echo ERRO: nao foi possivel baixar o instalador online.
  pause
  exit /b 1
)

if exist "%TEMPDIR%" rmdir /S /Q "%TEMPDIR%"
mkdir "%TEMPDIR%"

echo Extraindo pacote...
tar -xf "%TEMPZIP%" -C "%TEMPDIR%"

if exist "%TEMPDIR%\Instalador_Mistica_Presentes\Instalar_Mistica_Presentes.bat" (
  call "%TEMPDIR%\Instalador_Mistica_Presentes\Instalar_Mistica_Presentes.bat"
) else if exist "%TEMPDIR%\Instalar_Mistica_Presentes.bat" (
  call "%TEMPDIR%\Instalar_Mistica_Presentes.bat"
) else (
  echo ERRO: instalador interno nao encontrado no pacote baixado.
  pause
  exit /b 1
)

echo.
echo Atualizacao concluida.
echo.
pause
endlocal
