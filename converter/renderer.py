"""
renderer.py - Renderização de páginas de documentos como imagens.

Este módulo renderiza páginas de PDF como imagens para processamento
via visão computacional (LLM com capacidade visual).
"""
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass
import io
import logging

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from config.settings import RENDER_DPI, RENDER_FORMAT, MAX_IMAGE_DIMENSION

logger = logging.getLogger(__name__)


@dataclass
class RenderedPage:
    """Página renderizada como imagem."""
    page_number: int
    image: bytes  # PNG bytes
    width: int
    height: int
    dpi: int
    format: str = "PNG"


class DocumentRenderer:
    """Renderiza páginas de documentos como imagens."""

    def __init__(
        self,
        dpi: int = RENDER_DPI,
        output_format: str = RENDER_FORMAT,
        max_dimension: int = MAX_IMAGE_DIMENSION
    ):
        self.dpi = dpi
        self.output_format = output_format
        self.max_dimension = max_dimension

    def render_pdf(
        self,
        file_path: Path,
        pages: Optional[List[int]] = None
    ) -> List[RenderedPage]:
        """
        Renderiza páginas de PDF como imagens.

        Args:
            file_path: Caminho do PDF
            pages: Lista de números de página (1-indexed) ou None para todas

        Returns:
            Lista de RenderedPage
        """
        if not HAS_PYMUPDF:
            raise ImportError("PyMuPDF é necessário para renderizar PDFs")

        file_path = Path(file_path)
        doc = fitz.open(str(file_path))

        try:
            rendered_pages = []

            # Determinar quais páginas renderizar
            if pages is None:
                page_indices = range(len(doc))
            else:
                page_indices = [p - 1 for p in pages if 0 <= p - 1 < len(doc)]

            for page_idx in page_indices:
                page = doc[page_idx]
                rendered = self._render_page(page, page_idx + 1)
                rendered_pages.append(rendered)

            return rendered_pages

        finally:
            doc.close()

    def _render_page(self, page, page_number: int) -> RenderedPage:
        """Renderiza uma página como imagem."""
        # Calcular zoom baseado no DPI desejado
        zoom = self.dpi / 72.0  # PDF padrão é 72 DPI
        matrix = fitz.Matrix(zoom, zoom)

        # Renderizar
        pix = page.get_pixmap(matrix=matrix)

        # Verificar se precisa redimensionar
        width = pix.width
        height = pix.height

        if width > self.max_dimension or height > self.max_dimension:
            # Calcular novo tamanho mantendo proporção
            scale = min(self.max_dimension / width, self.max_dimension / height)
            new_width = int(width * scale)
            new_height = int(height * scale)

            if HAS_PIL:
                # Usar PIL para redimensionamento de qualidade
                img = Image.frombytes("RGB", (width, height), pix.samples)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                output_buffer = io.BytesIO()
                img.save(output_buffer, format=self.output_format)
                image_bytes = output_buffer.getvalue()
                width, height = new_width, new_height
            else:
                # Usar PyMuPDF diretamente (menos qualidade)
                new_matrix = fitz.Matrix(scale * zoom, scale * zoom)
                pix = page.get_pixmap(matrix=new_matrix)
                image_bytes = pix.tobytes(self.output_format.lower())
                width, height = pix.width, pix.height
        else:
            image_bytes = pix.tobytes(self.output_format.lower())

        return RenderedPage(
            page_number=page_number,
            image=image_bytes,
            width=width,
            height=height,
            dpi=self.dpi,
            format=self.output_format
        )

    def render_region(
        self,
        file_path: Path,
        page_number: int,
        x0: float, y0: float, x1: float, y1: float
    ) -> RenderedPage:
        """
        Renderiza uma região específica de uma página.

        Args:
            file_path: Caminho do PDF
            page_number: Número da página (1-indexed)
            x0, y0, x1, y1: Coordenadas da região

        Returns:
            RenderedPage da região
        """
        if not HAS_PYMUPDF:
            raise ImportError("PyMuPDF é necessário para renderizar PDFs")

        file_path = Path(file_path)
        doc = fitz.open(str(file_path))

        try:
            page = doc[page_number - 1]

            # Criar clip rect
            clip = fitz.Rect(x0, y0, x1, y1)

            # Renderizar com clip
            zoom = self.dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix, clip=clip)

            image_bytes = pix.tobytes(self.output_format.lower())

            return RenderedPage(
                page_number=page_number,
                image=image_bytes,
                width=pix.width,
                height=pix.height,
                dpi=self.dpi,
                format=self.output_format
            )

        finally:
            doc.close()


def render_document(
    file_path: Path,
    pages: Optional[List[int]] = None,
    dpi: int = RENDER_DPI
) -> List[RenderedPage]:
    """
    Função de conveniência para renderizar documento.

    Args:
        file_path: Caminho do arquivo
        pages: Páginas específicas ou None para todas
        dpi: Resolução de renderização

    Returns:
        Lista de RenderedPage
    """
    renderer = DocumentRenderer(dpi=dpi)
    return renderer.render_pdf(file_path, pages)


def render_page(file_path: Path, page_number: int, dpi: int = RENDER_DPI) -> RenderedPage:
    """
    Renderiza uma única página.

    Args:
        file_path: Caminho do arquivo
        page_number: Número da página (1-indexed)
        dpi: Resolução

    Returns:
        RenderedPage
    """
    renderer = DocumentRenderer(dpi=dpi)
    pages = renderer.render_pdf(file_path, [page_number])
    return pages[0] if pages else None
