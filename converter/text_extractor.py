"""
text_extractor.py - Extração de texto de documentos.

Este módulo extrai texto bruto de PDFs e DOCX, preservando
informações de posição e formatação quando disponíveis.
"""
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from collections import Counter
import logging

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from docx import Document as DocxDocument
    from docx.shared import Pt
    HAS_PYTHON_DOCX = True
except ImportError:
    HAS_PYTHON_DOCX = False

from .models import (
    ExtractedText, TextBlock, BoundingBox, DocumentType
)
from .utils import clean_text, merge_hyphenated_words

logger = logging.getLogger(__name__)


class TextExtractor:
    """Extrai texto de documentos PDF e DOCX."""

    def __init__(self):
        self._font_sizes: List[float] = []
        self._body_font_size: Optional[float] = None
        self._heading_threshold: Optional[float] = None

    def extract(self, file_path: Path, doc_type: DocumentType) -> List[ExtractedText]:
        """
        Extrai texto do documento.

        Args:
            file_path: Caminho do arquivo
            doc_type: Tipo do documento

        Returns:
            Lista de ExtractedText por página
        """
        file_path = Path(file_path)

        if doc_type in (DocumentType.PDF_NATIVE, DocumentType.PDF_SCANNED, DocumentType.PDF_MIXED):
            return self._extract_pdf(file_path)
        elif doc_type in (DocumentType.DOCX, DocumentType.DOC):
            return self._extract_docx(file_path)
        else:
            raise ValueError(f"Tipo de documento não suportado: {doc_type}")

    def _extract_pdf(self, file_path: Path) -> List[ExtractedText]:
        """Extrai texto de PDF usando PyMuPDF."""
        if not HAS_PYMUPDF:
            raise ImportError("PyMuPDF é necessário para extrair texto de PDFs")

        results = []
        doc = fitz.open(str(file_path))

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_result = self._extract_pdf_page(page, page_num + 1)
                results.append(page_result)

            # Calibrar thresholds após extrair todas as páginas
            self._calibrate_thresholds()

        finally:
            doc.close()

        return results

    def _extract_pdf_page(self, page, page_number: int) -> ExtractedText:
        """Extrai texto de uma página PDF."""
        blocks: List[TextBlock] = []
        raw_text_parts: List[str] = []

        # Extrair com informações de formatação
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        page_width = page.rect.width
        page_height = page.rect.height
        total_text_area = 0.0

        for block in text_dict.get("blocks", []):
            if block["type"] != 0:  # Não é texto
                continue

            block_bbox = block["bbox"]

            for line in block.get("lines", []):
                line_text_parts = []
                line_fonts: List[str] = []
                line_sizes: List[float] = []
                line_is_bold = False
                line_is_italic = False

                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text.strip():
                        continue

                    line_text_parts.append(text)
                    line_fonts.append(span.get("font", ""))
                    size = span.get("size", 12.0)
                    line_sizes.append(size)
                    self._font_sizes.append(size)

                    # Detectar bold/italic pelo nome da fonte
                    font_name = span.get("font", "").lower()
                    if "bold" in font_name or "black" in font_name:
                        line_is_bold = True
                    if "italic" in font_name or "oblique" in font_name:
                        line_is_italic = True

                if line_text_parts:
                    line_text = "".join(line_text_parts)
                    raw_text_parts.append(line_text)

                    # Usar tamanho médio da linha
                    avg_size = sum(line_sizes) / len(line_sizes) if line_sizes else 12.0
                    # Usar fonte mais comum
                    font_name = Counter(line_fonts).most_common(1)[0][0] if line_fonts else None

                    line_bbox = line["bbox"]
                    bbox = BoundingBox(
                        x0=line_bbox[0],
                        y0=line_bbox[1],
                        x1=line_bbox[2],
                        y1=line_bbox[3],
                        page=page_number
                    )

                    total_text_area += bbox.area

                    blocks.append(TextBlock(
                        text=line_text,
                        bbox=bbox,
                        font_name=font_name,
                        font_size=avg_size,
                        is_bold=line_is_bold,
                        is_italic=line_is_italic
                    ))

        # Calcular cobertura de texto
        page_area = page_width * page_height
        text_coverage = total_text_area / page_area if page_area > 0 else 0

        # Juntar texto raw
        raw_text = "\n".join(raw_text_parts)
        raw_text = merge_hyphenated_words(raw_text)
        raw_text = clean_text(raw_text)

        return ExtractedText(
            page_number=page_number,
            blocks=blocks,
            raw_text=raw_text,
            has_text=len(raw_text.strip()) > 0,
            text_coverage=text_coverage
        )

    def _extract_docx(self, file_path: Path) -> List[ExtractedText]:
        """Extrai texto de DOCX."""
        if not HAS_PYTHON_DOCX:
            raise ImportError("python-docx é necessário para extrair texto de DOCX")

        doc = DocxDocument(str(file_path))

        # DOCX não tem páginas reais, tratamos como uma única "página"
        blocks: List[TextBlock] = []
        raw_text_parts: List[str] = []

        y_position = 0.0

        for para in doc.paragraphs:
            if not para.text.strip():
                continue

            raw_text_parts.append(para.text)

            # Extrair formatação
            font_size = 12.0
            font_name = None
            is_bold = False
            is_italic = False

            if para.runs:
                first_run = para.runs[0]
                if first_run.font.size:
                    font_size = first_run.font.size.pt
                    self._font_sizes.append(font_size)
                font_name = first_run.font.name
                is_bold = first_run.bold or False
                is_italic = first_run.italic or False

            # Criar bbox simulado (DOCX não tem posições reais)
            bbox = BoundingBox(
                x0=0,
                y0=y_position,
                x1=500,
                y1=y_position + font_size,
                page=1
            )
            y_position += font_size + 5

            blocks.append(TextBlock(
                text=para.text,
                bbox=bbox,
                font_name=font_name,
                font_size=font_size,
                is_bold=is_bold,
                is_italic=is_italic
            ))

        raw_text = "\n\n".join(raw_text_parts)
        raw_text = clean_text(raw_text)

        self._calibrate_thresholds()

        # Retornar como página única
        return [ExtractedText(
            page_number=1,
            blocks=blocks,
            raw_text=raw_text,
            has_text=len(raw_text.strip()) > 0,
            text_coverage=1.0  # Não aplicável para DOCX
        )]

    def _calibrate_thresholds(self):
        """Calibra thresholds baseado nos tamanhos de fonte encontrados."""
        if not self._font_sizes:
            self._body_font_size = 12.0
            self._heading_threshold = 14.0
            return

        # Tamanho mais comum é provavelmente o corpo do texto
        size_counter = Counter(round(s, 1) for s in self._font_sizes)
        most_common = size_counter.most_common(1)[0][0]

        self._body_font_size = most_common
        # Headings são tipicamente 20%+ maiores
        self._heading_threshold = most_common * 1.2

    def get_body_font_size(self) -> Optional[float]:
        """Retorna tamanho da fonte do corpo calibrado."""
        return self._body_font_size

    def get_heading_threshold(self) -> Optional[float]:
        """Retorna threshold para identificar headings."""
        return self._heading_threshold


def extract_text(file_path: Path, doc_type: DocumentType) -> List[ExtractedText]:
    """
    Função de conveniência para extrair texto.

    Args:
        file_path: Caminho do arquivo
        doc_type: Tipo do documento

    Returns:
        Lista de ExtractedText
    """
    extractor = TextExtractor()
    return extractor.extract(file_path, doc_type)


def get_full_text(extracted_texts: List[ExtractedText]) -> str:
    """
    Concatena texto de todas as páginas.

    Args:
        extracted_texts: Lista de ExtractedText

    Returns:
        Texto completo
    """
    return "\n\n".join(et.raw_text for et in extracted_texts if et.raw_text)
