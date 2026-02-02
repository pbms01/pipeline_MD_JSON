#!/usr/bin/env python3
"""
Script de instalação do Pipeline MD/JSON v3.
Execute: python install.py

Isso irá baixar e instalar todos os arquivos necessários.
"""
import os
import urllib.request
import json

# URLs base do repositório (ajuste se necessário)
BASE_RAW = "https://raw.githubusercontent.com/pbms01/pipeline_MD_JSON/main/"

# Lista de arquivos essenciais para criar manualmente
ESSENTIAL_FILES = {
    "requirements.txt": """# Pipeline MD/JSON v3 - Requirements
anthropic>=0.39.0
python-dotenv>=1.0.0
pymupdf>=1.24.0
python-docx>=1.1.0
Pillow>=10.0.0
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
pydantic>=2.0.0
python-multipart>=0.0.6
""",
}

def create_directories():
    """Cria estrutura de diretórios."""
    dirs = [
        "converter",
        "config",
        "frontend/static/css",
        "frontend/static/js",
        "prompts",
        "schemas",
        "temp",
        "output"
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"  Criado: {d}/")

def create_essential_files():
    """Cria arquivos essenciais."""
    for filename, content in ESSENTIAL_FILES.items():
        with open(filename, 'w') as f:
            f.write(content)
        print(f"  Criado: {filename}")

def main():
    print("\n" + "="*50)
    print("  Pipeline MD/JSON v3 - Instalação")
    print("="*50 + "\n")

    print("1. Criando diretórios...")
    create_directories()

    print("\n2. Criando arquivos essenciais...")
    create_essential_files()

    print("\n" + "="*50)
    print("  Estrutura básica criada!")
    print("="*50)
    print("""
Próximos passos:
1. Instale as dependências:
   pip install -r requirements.txt

2. Os arquivos principais precisam ser copiados manualmente.
   Peça ao Claude para mostrar cada arquivo individualmente.

3. Configure sua API key:
   export ANTHROPIC_API_KEY=sua_chave

4. Execute:
   python run.py
""")

if __name__ == "__main__":
    main()
