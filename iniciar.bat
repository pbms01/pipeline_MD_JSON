@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

REM Verificar se ambiente virtual existe
if not exist venv\Scripts\activate.bat (
    echo [ERRO] Ambiente virtual nao encontrado!
    echo Execute primeiro: instalar.bat
    pause
    exit /b 1
)

REM Ativar ambiente virtual
call venv\Scripts\activate.bat

REM Iniciar aplicacao
python run.py %*
