@echo off
chcp 65001 >nul
title Mística Presentes

echo ========================================
echo      INICIANDO MÍSTICA PRESENTES
echo ========================================
echo.

cd /d "%~dp0"

if not exist "app.py" (
    echo ERRO: app.py não encontrado.
    echo.
    echo Coloque este arquivo BAT dentro da pasta do projeto:
    echo C:\Users\fredi\BruxoBR\misticapresentes
    echo.
    pause
    exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python não encontrado no computador.
    echo Instale o Python ou verifique se ele está no PATH.
    echo.
    pause
    exit /b 1
)

echo Atualizando dependências principais...
python -m pip install -r requirements.txt

echo.
echo Abrindo o aplicativo...
python app.py

echo.
echo O aplicativo foi fechado.
pause
