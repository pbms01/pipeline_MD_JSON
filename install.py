#!/usr/bin/env python3
"""
install.py - Instalador completo do Pipeline MD/JSON v3.

Uso:
    python install.py          # Instalação interativa completa
    python install.py --yes    # Aceitar defaults sem perguntar
    python install.py --help   # Ajuda

Este script:
1. Verifica versão do Python (3.10+)
2. Cria virtual environment
3. Instala todas as dependências
4. Configura o arquivo .env (API key)
5. Cria diretórios necessários
6. Executa health check
"""
import os
import platform
import subprocess
import sys
import venv
from pathlib import Path

# ─── Constantes ───────────────────────────────────────────────

PROJECT_DIR = Path(__file__).parent.resolve()
VENV_DIR = PROJECT_DIR / ".venv"
REQUIRED_PYTHON = (3, 10)
DIRECTORIES = ["temp", "output"]
TOTAL_STEPS = 6


# ─── Cores e Formatação ──────────────────────────────────────

class Style:
    """Cores ANSI com fallback para Windows."""

    GREEN = ""
    RED = ""
    YELLOW = ""
    BLUE = ""
    BOLD = ""
    RESET = ""

    @classmethod
    def init(cls):
        """Inicializa suporte a cores."""
        if not sys.stdout.isatty():
            return

        if platform.system() == "Windows":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                # Enable Virtual Terminal Processing
                handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
                mode = ctypes.c_ulong()
                kernel32.GetConsoleMode(handle, ctypes.byref(mode))
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
            except Exception:
                return  # Sem suporte a cores

        cls.GREEN = "\033[32m"
        cls.RED = "\033[31m"
        cls.YELLOW = "\033[33m"
        cls.BLUE = "\033[34m"
        cls.BOLD = "\033[1m"
        cls.RESET = "\033[0m"

    @classmethod
    def success(cls, msg):
        print(f"  {cls.GREEN}OK{cls.RESET}  {msg}")

    @classmethod
    def error(cls, msg):
        print(f"  {cls.RED}ERRO{cls.RESET}  {msg}")

    @classmethod
    def warning(cls, msg):
        print(f"  {cls.YELLOW}AVISO{cls.RESET}  {msg}")

    @classmethod
    def info(cls, msg):
        print(f"  {cls.BLUE}INFO{cls.RESET}  {msg}")

    @classmethod
    def step(cls, n, total, msg):
        print(f"\n{cls.BOLD}[{n}/{total}] {msg}{cls.RESET}")

    @classmethod
    def header(cls, msg):
        width = 56
        print()
        print(f"{cls.BOLD}{'=' * width}")
        print(f"  {msg}")
        print(f"{'=' * width}{cls.RESET}")
        print()


# ─── Helpers ──────────────────────────────────────────────────

def get_python_path(venv_path: Path) -> Path:
    if platform.system() == "Windows":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def get_pip_path(venv_path: Path) -> Path:
    if platform.system() == "Windows":
        return venv_path / "Scripts" / "pip.exe"
    return venv_path / "bin" / "pip"


def ask_yes_no(prompt: str, default_yes: bool = True) -> bool:
    """Pergunta sim/não ao usuário."""
    suffix = "[S/n]" if default_yes else "[s/N]"
    response = input(f"  {prompt} {suffix}: ").strip().lower()
    if response in ("", ):
        return default_yes
    return response in ("y", "yes", "s", "sim")


# ─── Etapa 1: Verificar Python ───────────────────────────────

def check_python_version():
    if sys.version_info < REQUIRED_PYTHON:
        Style.error(
            f"Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}+ necessario. "
            f"Encontrado: {sys.version_info.major}.{sys.version_info.minor}"
        )
        print()
        print("  Instale Python 3.10+ em: https://www.python.org/downloads/")
        sys.exit(1)
    Style.success(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")


# ─── Etapa 2: Virtual Environment ────────────────────────────

def detect_existing_venv():
    """Procura venv existente."""
    candidates = [
        PROJECT_DIR / ".venv",
        PROJECT_DIR / "venv",
        PROJECT_DIR / "env",
    ]
    for candidate in candidates:
        pip = get_pip_path(candidate)
        if pip.exists():
            return candidate
    return None


def create_or_reuse_venv(auto_yes: bool = False) -> Path:
    existing = detect_existing_venv()

    if existing:
        Style.info(f"Virtual environment encontrado: {existing.name}/")
        if auto_yes or ask_yes_no("Reutilizar?"):
            return existing
        Style.info("Criando novo...")

    Style.info(f"Criando virtual environment em: {VENV_DIR.name}/")
    try:
        venv.create(str(VENV_DIR), with_pip=True, clear=True)
    except Exception as e:
        Style.error(f"Falha ao criar venv: {e}")
        if platform.system() == "Linux":
            Style.info("No Ubuntu/Debian, instale: sudo apt install python3-venv")
        sys.exit(1)

    # Verificar que foi criado
    python = get_python_path(VENV_DIR)
    if not python.exists():
        Style.error(f"Python nao encontrado em: {python}")
        Style.info("Possivel interferencia de antivirus. Tente desativar temporariamente.")
        sys.exit(1)

    Style.success(f"Virtual environment criado: {VENV_DIR.name}/")
    return VENV_DIR


# ─── Etapa 3: Dependências ───────────────────────────────────

def install_dependencies(venv_path: Path):
    python = get_python_path(venv_path)
    pip = get_pip_path(venv_path)

    # Upgrade pip
    Style.info("Atualizando pip...")
    result = subprocess.run(
        [str(python), "-m", "pip", "install", "--upgrade", "pip"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        Style.warning("Falha ao atualizar pip, continuando...")

    # Instalar requirements.txt
    req_file = PROJECT_DIR / "requirements.txt"
    if not req_file.exists():
        Style.error(f"Arquivo nao encontrado: {req_file.name}")
        sys.exit(1)

    Style.info(f"Instalando dependencias de {req_file.name}...")
    print()
    result = subprocess.run(
        [str(pip), "install", "-r", str(req_file)],
        cwd=str(PROJECT_DIR)
    )

    if result.returncode != 0:
        Style.error("Falha na instalacao de dependencias!")
        Style.info("Tente manualmente: pip install -r requirements.txt")
        sys.exit(1)

    print()
    Style.success("Dependencias instaladas")

    # Instalar projeto em modo editável
    pyproject = PROJECT_DIR / "pyproject.toml"
    if pyproject.exists():
        Style.info("Instalando projeto (pip install -e .)...")
        result = subprocess.run(
            [str(pip), "install", "-e", str(PROJECT_DIR)],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            Style.success("Projeto instalado em modo editavel")
        else:
            Style.warning("pip install -e . falhou (nao critico)")


# ─── Etapa 4: Configurar .env ────────────────────────────────

def setup_env_file(auto_yes: bool = False):
    env_file = PROJECT_DIR / ".env"

    if env_file.exists():
        Style.info("Arquivo .env ja existe.")
        if not auto_yes and not ask_yes_no("Sobrescrever?", default_yes=False):
            Style.info("Mantendo .env existente.")
            return

    print()
    Style.info("Configuracao da API Key Anthropic")
    print("  Obtenha sua chave em: https://console.anthropic.com/")
    print()

    if auto_yes:
        api_key = ""
    else:
        api_key = input("  Cole sua ANTHROPIC_API_KEY (ou Enter para pular): ").strip()

    if not api_key:
        Style.warning("Sem API key. Configure depois no arquivo .env")
        api_key = "sk-ant-api03-your-key-here"

    env_content = (
        "# Pipeline MD/JSON v3 - Environment Variables\n"
        f"ANTHROPIC_API_KEY={api_key}\n"
        "LOG_LEVEL=INFO\n"
    )

    env_file.write_text(env_content, encoding="utf-8")
    Style.success(f"Arquivo .env criado")


# ─── Etapa 5: Diretórios ─────────────────────────────────────

def create_directories():
    for dirname in DIRECTORIES:
        dirpath = PROJECT_DIR / dirname
        dirpath.mkdir(parents=True, exist_ok=True)
    Style.success(f"Diretorios criados: {', '.join(DIRECTORIES)}")


# ─── Etapa 6: Health Check ───────────────────────────────────

def run_health_check(venv_path: Path) -> bool:
    python = get_python_path(venv_path)

    checks = [
        ("anthropic", "Anthropic SDK"),
        ("fitz", "PyMuPDF"),
        ("docx", "python-docx"),
        ("PIL", "Pillow"),
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("streamlit", "Streamlit"),
        ("pydantic", "Pydantic"),
        ("dotenv", "python-dotenv"),
    ]

    all_ok = True
    for module, name in checks:
        result = subprocess.run(
            [str(python), "-c", f"import {module}"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            Style.success(name)
        else:
            Style.error(f"{name} - FALHOU")
            all_ok = False

    # Verificar API key
    check_code = (
        "import os; from dotenv import load_dotenv; load_dotenv(); "
        "k = os.getenv('ANTHROPIC_API_KEY', ''); "
        "print('OK' if k and 'your-key' not in k else 'NO')"
    )
    result = subprocess.run(
        [str(python), "-c", check_code],
        capture_output=True, text=True, cwd=str(PROJECT_DIR)
    )
    if result.stdout.strip() == "OK":
        Style.success("ANTHROPIC_API_KEY configurada")
    else:
        Style.warning("ANTHROPIC_API_KEY nao configurada (edite o .env)")

    return all_ok


# ─── Instruções Pós-Instalação ────────────────────────────────

def show_post_install(venv_path: Path):
    system = platform.system()

    if system == "Windows":
        activate = f"  CMD:        {venv_path}\\Scripts\\activate"
        activate_ps = f"  PowerShell: {venv_path}\\Scripts\\Activate.ps1"
        activate_section = f"{activate}\n{activate_ps}"
    else:
        activate_section = f"  source {venv_path}/bin/activate"

    Style.header("Instalacao Concluida!")

    print(f"  Ativar virtual environment:")
    print(f"{activate_section}")
    print()
    print(f"  Iniciar servidor:")
    print(f"    python run.py              # FastAPI em http://127.0.0.1:8000")
    print(f"    python run.py --streamlit  # Streamlit em http://127.0.0.1:8501")
    print()
    print(f"  Usar CLI:")
    print(f"    python cli.py documento.pdf")
    print()
    print(f"  Interface web:")
    print(f"    http://127.0.0.1:8000/app")
    print()


# ─── Main ─────────────────────────────────────────────────────

def main():
    Style.init()

    auto_yes = "--yes" in sys.argv or "-y" in sys.argv

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)

    Style.header("Pipeline MD/JSON v3 - Instalacao")
    print(f"  Plataforma: {platform.system()} ({platform.machine()})")
    print(f"  Python:     {sys.version.split()[0]}")
    print(f"  Projeto:    {PROJECT_DIR}")

    # Etapa 1
    Style.step(1, TOTAL_STEPS, "Verificando Python...")
    check_python_version()

    # Etapa 2
    Style.step(2, TOTAL_STEPS, "Configurando virtual environment...")
    venv_path = create_or_reuse_venv(auto_yes)

    # Etapa 3
    Style.step(3, TOTAL_STEPS, "Instalando dependencias...")
    install_dependencies(venv_path)

    # Etapa 4
    Style.step(4, TOTAL_STEPS, "Configurando ambiente (.env)...")
    setup_env_file(auto_yes)

    # Etapa 5
    Style.step(5, TOTAL_STEPS, "Criando diretorios...")
    create_directories()

    # Etapa 6
    Style.step(6, TOTAL_STEPS, "Verificando instalacao...")
    run_health_check(venv_path)

    # Fim
    show_post_install(venv_path)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Instalacao cancelada pelo usuario.")
        sys.exit(1)
