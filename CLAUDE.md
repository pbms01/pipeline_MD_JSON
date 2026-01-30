# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Overview

**pipeline_MD_JSON** - Pipeline Híbrido v3 para conversão de documentos PDF/DOCX em Markdown e JSON estruturado com inferência dinâmica de schema.

### Filosofia
Este pipeline implementa uma arquitetura híbrida que combina:
- **Camada Fixa**: Estrutura consistente (metadata, sections, entities, chunks) que sistemas downstream sempre podem contar
- **Camada Dinâmica**: Schema inferido via LLM específico para cada tipo de documento (contratos, laudos, relatórios, etc.)

## Project Status

v3.0.0 - Implementação inicial completa

## Build & Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run Streamlit interface
streamlit run app.py

# Run programmatically
python -c "from converter import convert_document; result = convert_document('documento.pdf')"

# Run tests
pytest tests/

# Lint
black converter/ app.py
isort converter/ app.py
mypy converter/
```

## Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=your_api_key_here

# Optional
LOG_LEVEL=INFO
```

## Architecture

```
pipeline_MD_JSON/
├── app.py                      # Streamlit web interface
├── converter/                  # Core conversion package
│   ├── __init__.py            # Main orchestrator (convert_document)
│   ├── models.py              # All dataclasses and types
│   ├── detector.py            # Document type detection
│   ├── text_extractor.py      # Text extraction from PDF/DOCX
│   ├── structure_analyzer.py  # Structural analysis (headings, tables, etc.)
│   ├── asset_extractor.py     # Image/asset extraction
│   ├── renderer.py            # PDF page rendering for vision
│   ├── complexity_router.py   # Routes elements to text/vision processing
│   ├── vision_processor.py    # Claude Vision processing
│   ├── schema_inferrer.py     # Dynamic schema inference via LLM
│   ├── entity_extractor.py    # Named entity extraction
│   ├── synthesizer.py         # Combines results into ParsedDocument
│   ├── chunk_generator.py     # RAG chunk generation
│   ├── markdown_generator.py  # Markdown output generation
│   ├── json_generator.py      # Hybrid JSON output generation
│   └── utils.py               # Utility functions
├── config/
│   └── settings.py            # Centralized configuration
├── schemas/
│   └── base_schema.json       # JSON Schema for hybrid output
├── prompts/
│   ├── schema_inference.md    # Prompt for schema inference
│   └── entity_extraction.md   # Prompt for entity extraction
├── tests/                     # Test files
├── temp/                      # Temporary files (auto-created)
├── output/                    # Output files (auto-created)
└── requirements.txt           # Python dependencies
```

### Pipeline Flow

1. **Detection** - Identify document type (PDF native/scanned/mixed, DOCX)
2. **Text Extraction** - Extract text with position and formatting info
3. **Structure Analysis** - Identify headings, paragraphs, tables, figures
4. **Complexity Routing** - Decide text vs vision processing per element
5. **Asset Extraction** - Extract images and save as assets
6. **Vision Processing** - Process complex elements via Claude Vision
7. **Synthesis** - Combine all results into ParsedDocument
8. **Schema Inference** - Infer document-specific schema via LLM
9. **Entity Extraction** - Extract named entities (people, orgs, dates, etc.)
10. **Chunk Generation** - Create RAG-optimized chunks
11. **Output Generation** - Generate Markdown and hybrid JSON

## Code Conventions

- Python 3.10+ with type hints
- Dataclasses for data structures (see `models.py`)
- Each module has a main class and a convenience function
- Error handling with graceful degradation
- Logging via `logging` module
- Portuguese language in user-facing content (prompts, field names)

## Key Files

| File | Purpose |
|------|---------|
| `converter/__init__.py` | Main `convert_document()` function |
| `converter/models.py` | All dataclasses: `ParsedDocument`, `ConversionConfig`, `InferredSchema`, etc. |
| `converter/schema_inferrer.py` | Dynamic schema inference via Claude |
| `converter/json_generator.py` | Generates hybrid JSON (fixed + dynamic layers) |
| `app.py` | Streamlit web interface |
| `config/settings.py` | All configuration constants |
| `schemas/base_schema.json` | JSON Schema for validation |

## Key Types

```python
# Main conversion function
def convert_document(
    file_path: Path,
    config: Optional[ConversionConfig] = None,
    progress_callback: Optional[Callable] = None
) -> ConversionOutput

# Configuration
@dataclass
class ConversionConfig:
    enable_schema_inference: bool = True
    extract_entities: bool = True
    chunk_size: int = 500
    # ... more options

# Output
@dataclass
class ConversionOutput:
    markdown: str
    json_data: Dict[str, Any]
    parsed_document: ParsedDocument
    success: bool
    errors: List[str]
    warnings: List[str]

# Dynamic schema
@dataclass
class InferredSchema:
    schema_inferred: bool
    document_type: str
    confidence: float
    fields: Dict[str, Any]  # Dynamic fields vary by document
```

## Document Types Supported

The schema inferrer recognizes these document types:
- `contrato` - Legal contracts
- `laudo_tecnico` - Technical reports/inspections
- `relatorio` - Reports
- `manual` - Manuals/instructions
- `artigo` - Articles
- `ata` - Meeting minutes
- `parecer` - Legal/technical opinions
- `proposta` - Proposals
- `norma` - Norms/regulations
- `outro` - Other

## Development Notes

### Adding a New Document Type

1. Add type to `InferredDocumentType` enum in `models.py`
2. Add type-specific prompt to `TYPE_SPECIFIC_PROMPTS` in `schema_inferrer.py`
3. Add keywords to `DOCUMENT_TYPE_KEYWORDS` in `config/settings.py`
4. Optionally add schema example to `schemas/document_types/`

### Testing Locally

```python
from pathlib import Path
from converter import convert_document, ConversionConfig

result = convert_document(
    Path("test.pdf"),
    ConversionConfig(
        enable_schema_inference=True,
        output_dir="./output"
    )
)

print(f"Type: {result.parsed_document.metadata.document_type}")
print(f"Confidence: {result.parsed_document.structured_data.confidence}")
```

### Dependencies

Core:
- `anthropic` - Claude API client
- `pymupdf` (fitz) - PDF processing
- `python-docx` - DOCX processing
- `Pillow` - Image processing
- `streamlit` - Web interface

### Performance Considerations

- Schema inference adds ~2000 tokens per document
- Vision processing adds significant cost for complex pages
- Use `enable_schema_inference=False` for high-volume, low-cost scenarios
- Chunk size affects RAG quality vs token usage tradeoff
