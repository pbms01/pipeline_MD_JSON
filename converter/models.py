"""
models.py - Dataclasses e tipos para o pipeline v3 híbrido.

Este módulo define todas as estruturas de dados usadas pelo pipeline,
incluindo a camada fixa (sempre presente) e a camada dinâmica (inferida).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import uuid


# === ENUMS ===

class DocumentType(Enum):
    """Tipo técnico do documento (formato de arquivo)."""
    PDF_NATIVE = "pdf_native"
    PDF_SCANNED = "pdf_scanned"
    PDF_MIXED = "pdf_mixed"
    DOCX = "docx"
    DOC = "doc"
    UNKNOWN = "unknown"


class InferredDocumentType(Enum):
    """Tipos de documento inferidos semanticamente."""
    CONTRATO = "contrato"
    LAUDO_TECNICO = "laudo_tecnico"
    RELATORIO = "relatorio"
    MANUAL = "manual"
    ARTIGO = "artigo"
    APRESENTACAO = "apresentacao"
    ATA = "ata"
    PARECER = "parecer"
    PROPOSTA = "proposta"
    NORMA = "norma"
    OUTRO = "outro"


class ElementType(Enum):
    """Tipos de elementos do documento."""
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    FIGURE = "figure"
    EQUATION = "equation"
    CODE_BLOCK = "code_block"
    BLOCKQUOTE = "blockquote"
    FOOTNOTE = "footnote"
    PAGE_BREAK = "page_break"
    UNKNOWN = "unknown"


class ComplexityLevel(Enum):
    """Nível de complexidade para roteamento."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class ProcessingMethod(Enum):
    """Método usado para processar o elemento."""
    TEXT_EXTRACTION = "text_extraction"
    STRUCTURAL_ANALYSIS = "structural_analysis"
    VISION_LLM = "vision_llm"
    HYBRID = "hybrid"


# === STRUCTURED DATA (CAMADA DINÂMICA) ===

@dataclass
class InferredSchema:
    """
    Schema inferido dinamicamente pelo LLM.

    Esta é a representação da "camada dinâmica" do JSON.
    A estrutura interna (fields) varia por tipo de documento.
    """
    # Meta-campos (sempre presentes)
    schema_inferred: bool = True
    document_type: str = "unknown"
    schema_version: str = "1.0"
    inference_model: str = "claude-sonnet-4-5-20250929"
    confidence: float = 0.0
    fields_explanation: Dict[str, str] = field(default_factory=dict)

    # Campos dinâmicos (variam por documento)
    fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário para serialização JSON."""
        result = {
            "_schema_inferred": self.schema_inferred,
            "_document_type": self.document_type,
            "_schema_version": self.schema_version,
            "_inference_model": self.inference_model,
            "_confidence": self.confidence,
        }

        if self.fields_explanation:
            result["_fields_explanation"] = self.fields_explanation

        # Adicionar campos dinâmicos no nível raiz
        result.update(self.fields)

        return result


# === ESTRUTURAS BÁSICAS ===

@dataclass
class BoundingBox:
    """Caixa delimitadora de um elemento na página."""
    x0: float
    y0: float
    x1: float
    y1: float
    page: int

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def area(self) -> float:
        return self.width * self.height


@dataclass
class TextBlock:
    """Bloco de texto com posição e formatação."""
    text: str
    bbox: BoundingBox
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    is_bold: bool = False
    is_italic: bool = False
    color: Optional[str] = None


@dataclass
class ExtractedText:
    """Texto extraído de uma página."""
    page_number: int
    blocks: List[TextBlock]
    raw_text: str
    has_text: bool
    text_coverage: float  # Proporção da página coberta por texto


# === ELEMENTOS DO DOCUMENTO ===

@dataclass
class DocumentElement:
    """Classe base para elementos do documento."""
    id: str
    element_type: ElementType
    page: int
    bbox: Optional[BoundingBox] = None
    confidence: float = 1.0
    processing_method: ProcessingMethod = ProcessingMethod.TEXT_EXTRACTION


@dataclass
class Heading(DocumentElement):
    """Título ou cabeçalho."""
    text: str = ""
    level: int = 1

    def __post_init__(self):
        self.element_type = ElementType.HEADING


@dataclass
class Paragraph(DocumentElement):
    """Parágrafo de texto."""
    text: str = ""

    def __post_init__(self):
        self.element_type = ElementType.PARAGRAPH


@dataclass
class ListItem(DocumentElement):
    """Item de lista."""
    text: str = ""
    list_type: str = "unordered"  # "ordered" ou "unordered"
    level: int = 0
    index: Optional[int] = None

    def __post_init__(self):
        self.element_type = ElementType.LIST_ITEM


@dataclass
class TableColumn:
    """Coluna de tabela."""
    name: str
    col_type: str = "text"  # "text", "number", "date", "currency"


@dataclass
class Table(DocumentElement):
    """Tabela extraída do documento."""
    title: Optional[str] = None
    columns: List[TableColumn] = field(default_factory=list)
    data: List[List[Any]] = field(default_factory=list)
    has_merged_cells: bool = False
    header_rows: int = 1
    markdown: Optional[str] = None  # Representação em markdown

    def __post_init__(self):
        self.element_type = ElementType.TABLE

    @property
    def row_count(self) -> int:
        return len(self.data)

    @property
    def col_count(self) -> int:
        return len(self.columns) if self.columns else (len(self.data[0]) if self.data else 0)


@dataclass
class Figure(DocumentElement):
    """Figura ou imagem."""
    asset_path: str = ""
    title: Optional[str] = None
    caption: Optional[str] = None
    alt_text: Optional[str] = None
    figure_type: str = "other"  # "chart", "diagram", "photo", "screenshot", "other"
    width: Optional[int] = None
    height: Optional[int] = None

    def __post_init__(self):
        self.element_type = ElementType.FIGURE


@dataclass
class Equation(DocumentElement):
    """Equação matemática."""
    latex: str = ""
    label: Optional[str] = None
    is_inline: bool = False

    def __post_init__(self):
        self.element_type = ElementType.EQUATION


@dataclass
class Footnote(DocumentElement):
    """Nota de rodapé."""
    marker: str = ""
    text: str = ""

    def __post_init__(self):
        self.element_type = ElementType.FOOTNOTE


@dataclass
class CodeBlock(DocumentElement):
    """Bloco de código."""
    code: str = ""
    language: Optional[str] = None

    def __post_init__(self):
        self.element_type = ElementType.CODE_BLOCK


# === SEÇÕES ===

@dataclass
class Section:
    """Seção do documento com hierarquia."""
    id: str
    title: str
    level: int
    content: str = ""
    page_start: int = 1
    page_end: int = 1
    subsections: List['Section'] = field(default_factory=list)
    elements: List[DocumentElement] = field(default_factory=list)
    tables_refs: List[str] = field(default_factory=list)
    figures_refs: List[str] = field(default_factory=list)

    def get_full_text(self) -> str:
        """Retorna texto completo incluindo subseções."""
        parts = [self.content]
        for sub in self.subsections:
            parts.append(sub.get_full_text())
        return "\n\n".join(filter(None, parts))


# === ENTIDADES ===

@dataclass
class Person:
    """Pessoa mencionada no documento."""
    name: str
    role: Optional[str] = None
    mentions: int = 1


@dataclass
class Organization:
    """Organização mencionada no documento."""
    name: str
    org_type: Optional[str] = None  # "company", "government", "ngo", etc.
    mentions: int = 1


@dataclass
class Location:
    """Local mencionado no documento."""
    name: str
    location_type: str = "other"  # "city", "state", "country", "address"
    mentions: int = 1


@dataclass
class DateMention:
    """Data mencionada no documento."""
    original: str
    normalized: Optional[str] = None  # Formato ISO: YYYY-MM-DD
    context: Optional[str] = None


@dataclass
class MonetaryValue:
    """Valor monetário mencionado no documento."""
    original: str
    value: Optional[float] = None
    currency: Optional[str] = None
    context: Optional[str] = None


@dataclass
class ExtractedEntities:
    """Todas as entidades extraídas do documento."""
    people: List[Person] = field(default_factory=list)
    organizations: List[Organization] = field(default_factory=list)
    locations: List[Location] = field(default_factory=list)
    dates: List[DateMention] = field(default_factory=list)
    monetary_values: List[MonetaryValue] = field(default_factory=list)
    technical_terms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "people": [{"name": p.name, "role": p.role, "mentions": p.mentions} for p in self.people],
            "organizations": [{"name": o.name, "type": o.org_type, "mentions": o.mentions} for o in self.organizations],
            "locations": [{"name": l.name, "type": l.location_type, "mentions": l.mentions} for l in self.locations],
            "dates": [{"original": d.original, "normalized": d.normalized, "context": d.context} for d in self.dates],
            "monetary_values": [{"original": m.original, "value": m.value, "currency": m.currency, "context": m.context} for m in self.monetary_values],
            "technical_terms": self.technical_terms
        }


# === CHUNKS ===

@dataclass
class Chunk:
    """Chunk de texto para RAG."""
    id: str
    text: str
    token_count: int = 0
    section_id: Optional[str] = None
    section_title: Optional[str] = None
    page: int = 1
    chunk_index: int = 0
    has_table: bool = False
    has_figure: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "id": self.id,
            "text": self.text,
            "token_count": self.token_count,
            "section_id": self.section_id,
            "section_title": self.section_title,
            "page": self.page,
            "chunk_index": self.chunk_index,
            "has_table": self.has_table,
            "has_figure": self.has_figure,
            "metadata": self.metadata
        }


# === METADADOS ===

@dataclass
class DocumentMetadata:
    """Metadados do documento."""
    id: str
    source_file: str
    title: Optional[str] = None
    document_type: str = "unknown"
    document_type_confidence: float = 0.0
    authors: List[str] = field(default_factory=list)
    date: Optional[str] = None
    language: str = "pt"
    page_count: int = 0
    keywords: List[str] = field(default_factory=list)
    file_size_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "id": self.id,
            "source_file": self.source_file,
            "title": self.title,
            "document_type": self.document_type,
            "document_type_confidence": self.document_type_confidence,
            "authors": self.authors,
            "date": self.date,
            "language": self.language,
            "page_count": self.page_count,
            "keywords": self.keywords
        }


@dataclass
class ProcessingInfo:
    """Informações sobre o processamento."""
    converted_at: datetime = field(default_factory=datetime.now)
    pipeline_version: str = "3.0.0"
    processing_time_seconds: float = 0.0
    tokens_used: int = 0
    vision_calls: int = 0
    schema_inference_used: bool = False
    confidence_overall: float = 1.0
    confidence_text: float = 1.0
    confidence_structure: float = 1.0
    confidence_schema: float = 1.0
    confidence_entities: float = 1.0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "converted_at": self.converted_at.isoformat() if isinstance(self.converted_at, datetime) else str(self.converted_at),
            "pipeline_version": self.pipeline_version,
            "processing_time_seconds": round(self.processing_time_seconds, 2),
            "tokens_used": self.tokens_used,
            "vision_calls": self.vision_calls,
            "schema_inference_used": self.schema_inference_used,
            "confidence_scores": {
                "overall": round(self.confidence_overall, 3),
                "text_extraction": round(self.confidence_text, 3),
                "structure_detection": round(self.confidence_structure, 3),
                "schema_inference": round(self.confidence_schema, 3),
                "entity_extraction": round(self.confidence_entities, 3)
            },
            "warnings": self.warnings
        }


# === DOCUMENTO PARSEADO (ESTRUTURA CENTRAL) ===

@dataclass
class ParsedDocument:
    """
    Documento parseado - estrutura central do pipeline v3.

    Combina:
    - Camada fixa (metadata, sections, entities, chunks)
    - Camada dinâmica (structured_data com schema inferido)
    """
    # Metadados (fixo)
    metadata: DocumentMetadata

    # Conteúdo estruturado genérico (fixo)
    sections: List[Section] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    figures: List[Figure] = field(default_factory=list)
    equations: List[Equation] = field(default_factory=list)
    footnotes: List[Footnote] = field(default_factory=list)

    # Resumo (fixo, sempre gerado)
    summary: Optional[str] = None

    # Schema inferido (dinâmico)
    structured_data: Optional[InferredSchema] = None

    # Entidades (fixo)
    entities: ExtractedEntities = field(default_factory=ExtractedEntities)

    # Chunks para RAG (fixo)
    chunks: List[Chunk] = field(default_factory=list)

    # Info de processamento (fixo)
    processing: ProcessingInfo = field(default_factory=ProcessingInfo)

    # Dados brutos
    raw_text_by_page: Dict[int, str] = field(default_factory=dict)
    elements: List[DocumentElement] = field(default_factory=list)

    def get_full_text(self) -> str:
        """Retorna texto completo do documento."""
        if self.raw_text_by_page:
            return "\n\n".join(
                self.raw_text_by_page[p]
                for p in sorted(self.raw_text_by_page.keys())
            )
        return "\n\n".join(s.get_full_text() for s in self.sections)


# === RESULTADO DA CONVERSÃO ===

@dataclass
class ConversionOutput:
    """Saída completa da conversão."""
    markdown: str
    json_data: Dict[str, Any]
    markdown_path: Optional[str] = None
    json_path: Optional[str] = None
    assets_dir: Optional[str] = None
    parsed_document: Optional[ParsedDocument] = None
    success: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# === CONFIGURAÇÃO ===

@dataclass
class ConversionConfig:
    """Configurações para a conversão."""
    # Output
    output_dir: Optional[str] = None
    generate_markdown: bool = True
    generate_json: bool = True

    # Inferência de schema (NOVO)
    enable_schema_inference: bool = True
    schema_inference_model: str = "claude-sonnet-4-5-20250929"
    include_fields_explanation: bool = False

    # Processamento
    prefer_vision_for_tables: bool = False
    prefer_vision_for_equations: bool = True
    vision_dpi: int = 150

    # Chunks
    chunk_size: int = 500
    chunk_overlap: int = 50

    # Entidades
    extract_entities: bool = True

    # Markdown
    include_frontmatter: bool = True
    include_toc: bool = False

    # JSON
    include_chunks: bool = True
    include_raw_text: bool = False
    pretty_print: bool = True


# === ANÁLISE ESTRUTURAL ===

@dataclass
class StructuralAnalysis:
    """Resultado da análise estrutural de uma página."""
    page_number: int
    headings: List[Heading] = field(default_factory=list)
    paragraphs: List[Paragraph] = field(default_factory=list)
    list_items: List[ListItem] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    figures: List[Figure] = field(default_factory=list)
    equations: List[Equation] = field(default_factory=list)
    footnotes: List[Footnote] = field(default_factory=list)

    @property
    def all_elements(self) -> List[DocumentElement]:
        """Retorna todos os elementos."""
        elements: List[DocumentElement] = []
        elements.extend(self.headings)
        elements.extend(self.paragraphs)
        elements.extend(self.list_items)
        elements.extend(self.tables)
        elements.extend(self.figures)
        elements.extend(self.equations)
        elements.extend(self.footnotes)
        return elements


# === ROTEAMENTO ===

@dataclass
class RoutingPlan:
    """Plano de roteamento para uma página."""
    page_number: int
    complexity: ComplexityLevel
    requires_full_page_vision: bool = False
    elements_for_vision: List[str] = field(default_factory=list)  # IDs dos elementos
    elements_for_text: List[str] = field(default_factory=list)
    reason: str = ""


# === VISÃO ===

@dataclass
class VisionResult:
    """Resultado do processamento visual."""
    page_number: int
    content: str  # Conteúdo extraído
    tables: List[Table] = field(default_factory=list)
    figures: List[Figure] = field(default_factory=list)
    equations: List[Equation] = field(default_factory=list)
    tokens_used: int = 0
    confidence: float = 1.0
    processing_time: float = 0.0


# === ASSET ===

@dataclass
class ExtractedAsset:
    """Asset extraído do documento (imagem)."""
    page_number: int
    asset_type: str  # "image", "chart", "diagram"
    image_data: bytes = field(default=b"", repr=False)
    width: int = 0
    height: int = 0
    format: str = "png"
    bbox: Optional[BoundingBox] = None


# === DOCUMENTO INFO ===

@dataclass
class DocumentInfo:
    """Informações básicas do documento detectado."""
    file_path: str
    file_name: str
    file_size: int
    doc_type: DocumentType
    page_count: int
    has_text: bool
    has_images: bool
    is_encrypted: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


# === HELPERS ===

def generate_id(prefix: str = "") -> str:
    """Gera um ID único."""
    uid = str(uuid.uuid4())[:8]
    return f"{prefix}_{uid}" if prefix else uid


def generate_doc_id() -> str:
    """Gera ID para documento."""
    return f"doc_{uuid.uuid4()}"


def generate_chunk_id(index: int) -> str:
    """Gera ID para chunk."""
    return f"chunk_{index:04d}"


def generate_section_id(index: int) -> str:
    """Gera ID para seção."""
    return f"sec_{index}"


def generate_table_id(index: int) -> str:
    """Gera ID para tabela."""
    return f"table_{index}"


def generate_figure_id(index: int) -> str:
    """Gera ID para figura."""
    return f"fig_{index}"
