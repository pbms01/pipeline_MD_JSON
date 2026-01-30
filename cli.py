#!/usr/bin/env python3
"""
cli.py - Interface de linha de comando para o Pipeline MD/JSON v3.

Uso:
    python cli.py arquivo.pdf [opções]
    python cli.py arquivo.docx --no-schema --output ./saida

Opções:
    --output, -o      Diretório de saída (padrão: ./output)
    --no-schema       Desabilitar inferência de schema
    --no-entities     Desabilitar extração de entidades
    --no-markdown     Não gerar arquivo Markdown
    --no-json         Não gerar arquivo JSON
    --vision-tables   Usar visão para processar tabelas
    --chunk-size      Tamanho do chunk para RAG (padrão: 500)
    --chunk-overlap   Overlap entre chunks (padrão: 50)
    --verbose, -v     Modo verboso
    --quiet, -q       Modo silencioso
    --help, -h        Mostrar ajuda
"""
import argparse
import sys
import time
from pathlib import Path
from typing import Optional
import json


def create_parser() -> argparse.ArgumentParser:
    """Cria parser de argumentos."""
    parser = argparse.ArgumentParser(
        prog="pipeline-md-json",
        description="Pipeline MD/JSON v3 - Conversor Híbrido de Documentos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s documento.pdf
  %(prog)s contrato.pdf -o ./resultado --verbose
  %(prog)s relatorio.docx --no-schema --chunk-size 300
  %(prog)s laudo.pdf --vision-tables
        """
    )

    # Argumentos posicionais
    parser.add_argument(
        "file",
        type=str,
        help="Arquivo PDF ou DOCX para converter"
    )

    # Output
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="./output",
        help="Diretório de saída (padrão: ./output)"
    )

    # Schema
    parser.add_argument(
        "--no-schema",
        action="store_true",
        help="Desabilitar inferência de schema via LLM"
    )

    # Entities
    parser.add_argument(
        "--no-entities",
        action="store_true",
        help="Desabilitar extração de entidades"
    )

    # Output formats
    parser.add_argument(
        "--no-markdown",
        action="store_true",
        help="Não gerar arquivo Markdown"
    )

    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Não gerar arquivo JSON"
    )

    # Processing
    parser.add_argument(
        "--vision-tables",
        action="store_true",
        help="Usar Claude Vision para processar tabelas complexas"
    )

    # Chunks
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Tamanho do chunk em tokens (padrão: 500)"
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help="Overlap entre chunks em tokens (padrão: 50)"
    )

    # Markdown options
    parser.add_argument(
        "--no-frontmatter",
        action="store_true",
        help="Não incluir frontmatter YAML no Markdown"
    )

    parser.add_argument(
        "--with-toc",
        action="store_true",
        help="Incluir sumário no Markdown"
    )

    # JSON options
    parser.add_argument(
        "--with-raw-text",
        action="store_true",
        help="Incluir texto bruto por página no JSON"
    )

    # Verbosity
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Modo verboso - mostra progresso detalhado"
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Modo silencioso - apenas erros"
    )

    # JSON output to stdout
    parser.add_argument(
        "--json-stdout",
        action="store_true",
        help="Imprimir resultado JSON no stdout"
    )

    return parser


def print_progress(stage: str, current: int, total: int, verbose: bool):
    """Imprime progresso."""
    if not verbose:
        return

    stages_names = {
        "detection": "Detectando tipo",
        "text_extraction": "Extraindo texto",
        "structure_analysis": "Analisando estrutura",
        "routing": "Roteando",
        "asset_extraction": "Extraindo assets",
        "vision_processing": "Processando visão",
        "synthesis": "Sintetizando",
        "schema_inference": "Inferindo schema",
        "entity_extraction": "Extraindo entidades",
        "chunk_generation": "Gerando chunks",
        "generation": "Gerando saídas"
    }

    name = stages_names.get(stage, stage)
    percent = (current / total * 100) if total > 0 else 0
    bar_width = 30
    filled = int(bar_width * current / total) if total > 0 else 0

    bar = "█" * filled + "░" * (bar_width - filled)
    print(f"\r  [{bar}] {percent:5.1f}% - {name:<20}", end="", flush=True)

    if current >= total:
        print()


def main():
    """Função principal."""
    parser = create_parser()
    args = parser.parse_args()

    # Validar arquivo
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Erro: Arquivo não encontrado: {file_path}", file=sys.stderr)
        sys.exit(1)

    extension = file_path.suffix.lower()
    if extension not in [".pdf", ".docx", ".doc"]:
        print(f"Erro: Formato não suportado: {extension}", file=sys.stderr)
        print("Use arquivos PDF ou DOCX.", file=sys.stderr)
        sys.exit(1)

    # Criar diretório de saída
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Configurar verbosidade
    verbose = args.verbose and not args.quiet
    quiet = args.quiet

    if not quiet:
        print(f"\n{'='*60}")
        print(f"  Pipeline MD/JSON v3")
        print(f"{'='*60}")
        print(f"  Arquivo: {file_path.name}")
        print(f"  Saída:   {output_dir}")
        print(f"{'='*60}\n")

    try:
        # Import tardio
        from converter import convert_document, ConversionConfig

        # Criar config
        config = ConversionConfig(
            output_dir=str(output_dir),
            enable_schema_inference=not args.no_schema,
            extract_entities=not args.no_entities,
            generate_markdown=not args.no_markdown,
            generate_json=not args.no_json,
            prefer_vision_for_tables=args.vision_tables,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            include_frontmatter=not args.no_frontmatter,
            include_toc=args.with_toc,
            include_raw_text=args.with_raw_text
        )

        # Callback de progresso
        def progress_callback(stage, current, total):
            print_progress(stage, current, total, verbose)

        # Converter
        start_time = time.time()
        result = convert_document(
            file_path,
            config=config,
            progress_callback=progress_callback if verbose else None
        )
        elapsed = time.time() - start_time

        # Verificar resultado
        if not result.success:
            print(f"\nErro na conversão:", file=sys.stderr)
            for error in result.errors:
                print(f"  - {error}", file=sys.stderr)
            sys.exit(1)

        # Mostrar resultado
        if not quiet:
            print(f"\n{'='*60}")
            print(f"  Conversão concluída!")
            print(f"{'='*60}")

            if result.parsed_document:
                doc = result.parsed_document
                print(f"  Tipo de documento: {doc.metadata.document_type}")

                if doc.structured_data:
                    print(f"  Confiança:         {doc.structured_data.confidence:.1%}")

                print(f"  Páginas:           {doc.metadata.page_count}")
                print(f"  Seções:            {len(doc.sections)}")
                print(f"  Tabelas:           {len(doc.tables)}")
                print(f"  Figuras:           {len(doc.figures)}")
                print(f"  Chunks:            {len(doc.chunks)}")

            print(f"\n  Tempo:             {elapsed:.2f}s")

            if result.markdown_path:
                print(f"  Markdown:          {result.markdown_path}")
            if result.json_path:
                print(f"  JSON:              {result.json_path}")

            if result.warnings:
                print(f"\n  Avisos:")
                for warning in result.warnings:
                    print(f"    - {warning}")

            print(f"{'='*60}\n")

        # Output JSON to stdout se solicitado
        if args.json_stdout:
            print(json.dumps(result.json_data, indent=2, ensure_ascii=False))

    except ImportError as e:
        print(f"Erro de importação: {e}", file=sys.stderr)
        print("Verifique se todas as dependências estão instaladas.", file=sys.stderr)
        print("Execute: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"\nErro: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
