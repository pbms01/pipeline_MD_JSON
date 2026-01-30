"""
settings.py - Configurações do pipeline v3.

Este módulo centraliza todas as configurações do pipeline híbrido
para processamento de documentos MD/JSON.
"""
import os
from pathlib import Path

# === PATHS ===
BASE_DIR = Path(__file__).parent.parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "output"
PROMPTS_DIR = BASE_DIR / "prompts"
SCHEMAS_DIR = BASE_DIR / "schemas"

# Criar diretórios se não existirem
TEMP_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === API ===
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
CLAUDE_VISION_MODEL = "claude-sonnet-4-5-20250929"
CLAUDE_MAX_TOKENS = 8192

# === RENDERIZAÇÃO ===
RENDER_DPI = 150
RENDER_FORMAT = "PNG"
MAX_IMAGE_DIMENSION = 2048

# === PROCESSAMENTO ===
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc"}
MAX_PAGES = 100
MAX_FILE_SIZE_MB = 50

# === INFERÊNCIA DE SCHEMA ===
ENABLE_SCHEMA_INFERENCE_DEFAULT = True
SCHEMA_INFERENCE_MAX_CHARS = 30000
INCLUDE_FIELDS_EXPLANATION_DEFAULT = False

# === EXTRAÇÃO DE ENTIDADES ===
EXTRACT_ENTITIES_DEFAULT = True
ENTITY_EXTRACTION_MAX_CHARS = 20000

# === CHUNKING ===
CHUNK_SIZE_DEFAULT = 500
CHUNK_OVERLAP_DEFAULT = 50
MIN_CHUNK_SIZE = 50
MAX_CHUNK_SIZE = 2000

# === ASSETS ===
ASSET_MIN_SIZE = (50, 50)
ASSET_FORMAT = "png"
ASSET_QUALITY = 95

# === THRESHOLDS ===
# Threshold para considerar página como "escaneada" (baixa cobertura de texto)
SCANNED_PAGE_THRESHOLD = 0.1
# Threshold mínimo de confiança para aceitar resultado
MIN_CONFIDENCE_THRESHOLD = 0.5
# Threshold para usar visão em tabelas complexas
COMPLEX_TABLE_THRESHOLD = 0.7

# === LOGGING ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# === VISION PROCESSING ===
VISION_MAX_RETRIES = 3
VISION_RETRY_DELAY = 1.0
VISION_TIMEOUT = 60

# === DOCUMENT TYPE DETECTION ===
DOCUMENT_TYPE_KEYWORDS = {
    "contrato": ["contrato", "contratante", "contratada", "cláusula", "vigência", "objeto"],
    "laudo_tecnico": ["laudo", "vistoria", "patologia", "constatação", "parecer técnico", "art"],
    "relatorio": ["relatório", "período", "análise", "resultados", "conclusão"],
    "manual": ["manual", "instruções", "procedimento", "passo a passo", "operação"],
    "artigo": ["resumo", "abstract", "introdução", "metodologia", "referências"],
    "ata": ["ata", "reunião", "assembleia", "deliberação", "pauta"],
    "parecer": ["parecer", "análise jurídica", "fundamentação", "conclusão"],
    "proposta": ["proposta", "orçamento", "escopo", "prazo", "investimento"],
    "norma": ["norma", "regulamento", "política", "diretrizes", "procedimentos"],
}
