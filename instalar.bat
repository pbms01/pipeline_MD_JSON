@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║           Pipeline MD/JSON v3 - Instalador                   ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

REM Verificar se Python esta instalado
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Python encontrado
    goto :check_pip
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Python encontrado (py launcher)
    set PYTHON_CMD=py
    goto :check_pip
)

echo [!] Python nao encontrado. Iniciando download...
echo.

REM Baixar Python
set PYTHON_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
set PYTHON_INSTALLER=python_installer.exe

echo Baixando Python 3.11.9...
curl -L -o %PYTHON_INSTALLER% %PYTHON_URL%
if %errorlevel% neq 0 (
    echo [ERRO] Falha no download. Verifique sua conexao.
    echo Baixe manualmente: %PYTHON_URL%
    pause
    exit /b 1
)

echo.
echo Instalando Python (isso pode levar alguns minutos)...
echo IMPORTANTE: Nao feche esta janela!
echo.

REM Instalar Python silenciosamente com PATH
%PYTHON_INSTALLER% /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1

if %errorlevel% neq 0 (
    echo [ERRO] Falha na instalacao do Python.
    echo Tente instalar manualmente: %PYTHON_INSTALLER%
    pause
    exit /b 1
)

del %PYTHON_INSTALLER%
echo [OK] Python instalado com sucesso!
echo.
echo IMPORTANTE: Feche e reabra este terminal, depois execute instalar.bat novamente.
pause
exit /b 0

:check_pip
REM Definir comando Python
where python >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
) else (
    set PYTHON_CMD=py
)

echo [OK] Usando: %PYTHON_CMD%
echo.

REM Verificar pip
%PYTHON_CMD% -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Instalando pip...
    %PYTHON_CMD% -m ensurepip --upgrade
)

REM Criar ambiente virtual
echo Criando ambiente virtual...
if exist venv (
    echo [!] Ambiente virtual ja existe, pulando...
) else (
    %PYTHON_CMD% -m venv venv
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao criar ambiente virtual
        pause
        exit /b 1
    )
)
echo [OK] Ambiente virtual criado
echo.

REM Ativar ambiente virtual e instalar dependencias
echo Instalando dependencias (isso pode levar alguns minutos)...
echo.
call venv\Scripts\activate.bat

python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Falha ao instalar dependencias
    pause
    exit /b 1
)

echo.
echo [OK] Dependencias instaladas
echo.

REM Verificar/criar arquivo .env
if not exist .env (
    echo Criando arquivo .env...
    echo # Pipeline MD/JSON v3 - Configuracao> .env
    echo.>> .env
    echo # OBRIGATORIO: Sua chave da API Anthropic>> .env
    echo ANTHROPIC_API_KEY=sua_chave_aqui>> .env
    echo.>> .env
    echo # Opcional>> .env
    echo LOG_LEVEL=INFO>> .env
    echo.
    echo [!] IMPORTANTE: Edite o arquivo .env e adicione sua ANTHROPIC_API_KEY
    echo.
)

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║              INSTALACAO CONCLUIDA COM SUCESSO!               ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║                                                              ║
echo ║  Proximo passo:                                              ║
echo ║  1. Edite o arquivo .env com sua ANTHROPIC_API_KEY           ║
echo ║  2. Execute: iniciar.bat                                     ║
echo ║                                                              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
pause
