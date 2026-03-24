#!/usr/bin/env python3
"""
run.py - Script de inicialização do Pipeline MD/JSON v3.

Uso:
    python run.py              # Inicia servidor FastAPI na porta 8080
    python run.py --port 3000  # Porta customizada
    python run.py --streamlit  # Usa Streamlit ao invés de FastAPI
    python run.py --help       # Mostra ajuda
"""
import argparse
import os
import sys
from pathlib import Path

# Carregar .env do diretório do script
from dotenv import load_dotenv
_script_dir = Path(__file__).parent.absolute()
_env_file = _script_dir / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
else:
    load_dotenv()  # Busca padrão


def check_dependencies():
    """Verifica se dependências estão instaladas."""
    missing = []

    try:
        import anthropic
    except ImportError:
        missing.append("anthropic")

    try:
        import fitz
    except ImportError:
        missing.append("pymupdf")

    try:
        import docx
    except ImportError:
        missing.append("python-docx")

    try:
        from PIL import Image
    except ImportError:
        missing.append("Pillow")

    if missing:
        print("Dependências faltando:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nInstale com: pip install -r requirements.txt")
        sys.exit(1)


def check_api_key():
    """Verifica se ANTHROPIC_API_KEY está configurada."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Aviso: ANTHROPIC_API_KEY não configurada.")
        print("Configure com: export ANTHROPIC_API_KEY=your_key")
        print("Continuando mesmo assim...\n")


def run_fastapi(host: str = "127.0.0.1", port: int = 8080, reload: bool = False):
    """Inicia servidor FastAPI."""
    try:
        import uvicorn
    except ImportError:
        print("uvicorn não instalado. Instale com: pip install uvicorn[standard]")
        sys.exit(1)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                   Pipeline MD/JSON v3                         ║
║                                                               ║
║  Servidor iniciando em: http://{host}:{port}                  ║
║                                                               ║
║  Interface web:         http://{host}:{port}/app              ║
║  API docs:              http://{host}:{port}/docs             ║
║  Health check:          http://{host}:{port}/health           ║
║                                                               ║
║  Pressione Ctrl+C para parar                                  ║
╚══════════════════════════════════════════════════════════════╝
""")

    uvicorn.run(
        "api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


def run_streamlit(port: int = 8501):
    """Inicia servidor Streamlit."""
    try:
        import streamlit.web.cli as stcli
    except ImportError:
        print("streamlit não instalado. Instale com: pip install streamlit")
        sys.exit(1)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                   Pipeline MD/JSON v3                         ║
║                        (Streamlit)                            ║
║                                                               ║
║  Interface disponível em: http://localhost:{port}             ║
║                                                               ║
║  Pressione Ctrl+C para parar                                  ║
╚══════════════════════════════════════════════════════════════╝
""")

    sys.argv = [
        "streamlit", "run", "app.py",
        "--server.port", str(port),
        "--server.headless", "true"
    ]
    stcli.main()


def main():
    """Função principal."""
    parser = argparse.ArgumentParser(
        description="Pipeline MD/JSON v3 - Servidor",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host para bind (padrão: 127.0.0.1)"
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Porta do servidor (padrão: 8080 para FastAPI, 8501 para Streamlit)"
    )

    parser.add_argument(
        "--streamlit",
        action="store_true",
        help="Usar Streamlit ao invés de FastAPI"
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Auto-reload em mudanças (apenas FastAPI)"
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Apenas verificar dependências"
    )

    args = parser.parse_args()

    # Verificar dependências
    check_dependencies()

    if args.check:
        print("Todas as dependências estão instaladas!")
        return

    # Verificar API key
    check_api_key()

    # Mudar para diretório do script
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)

    # Iniciar servidor
    if args.streamlit:
        port = args.port if args.port != 8080 else 8501
        run_streamlit(port)
    else:
        run_fastapi(args.host, args.port, args.reload)


if __name__ == "__main__":
    main()
