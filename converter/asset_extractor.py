"""
asset_extractor.py - Extração de assets (imagens) de documentos.

Este módulo extrai imagens e outros assets de PDFs e DOCX,
salvando-os em formatos padronizados.
"""
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import io
import logging

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from docx import Document as DocxDocument
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    HAS_PYTHON_DOCX = True
except ImportError:
    HAS_PYTHON_DOCX = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from .models import ExtractedAsset, BoundingBox, DocumentType
from config.settings import ASSET_MIN_SIZE, ASSET_FORMAT, ASSET_QUALITY

logger = logging.getLogger(__name__)


class AssetExtractor:
    """Extrai assets (imagens) de documentos."""

    def __init__(
        self,
        min_size: Tuple[int, int] = ASSET_MIN_SIZE,
        output_format: str = ASSET_FORMAT,
        quality: int = ASSET_QUALITY
    ):
        self.min_size = min_size
        self.output_format = output_format
        self.quality = quality

    def extract(self, file_path: Path, doc_type: DocumentType) -> List[ExtractedAsset]:
        """
        Extrai todos os assets do documento.

        Args:
            file_path: Caminho do arquivo
            doc_type: Tipo do documento

        Returns:
            Lista de ExtractedAsset
        """
        file_path = Path(file_path)

        if doc_type in (DocumentType.PDF_NATIVE, DocumentType.PDF_SCANNED, DocumentType.PDF_MIXED):
            return self._extract_from_pdf(file_path)
        elif doc_type in (DocumentType.DOCX, DocumentType.DOC):
            return self._extract_from_docx(file_path)
        else:
            return []

    def _extract_from_pdf(self, file_path: Path) -> List[ExtractedAsset]:
        """Extrai imagens de PDF."""
        if not HAS_PYMUPDF:
            logger.warning("PyMuPDF não disponível para extração de imagens")
            return []

        assets = []
        doc = fitz.open(str(file_path))

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images(full=True)

                for img_index, img_info in enumerate(image_list):
                    xref = img_info[0]

                    try:
                        base_image = doc.extract_image(xref)
                        if not base_image:
                            continue

                        image_bytes = base_image["image"]
                        image_ext = base_image.get("ext", "png")

                        # Converter para PIL para processamento
                        if HAS_PIL:
                            img = Image.open(io.BytesIO(image_bytes))
                            width, height = img.size

                            # Filtrar imagens muito pequenas
                            if width < self.min_size[0] or height < self.min_size[1]:
                                continue

                            # Converter para formato desejado
                            output_buffer = io.BytesIO()
                            if img.mode in ('RGBA', 'P'):
                                img = img.convert('RGB')
                            img.save(output_buffer, format=self.output_format.upper(), quality=self.quality)
                            image_bytes = output_buffer.getvalue()
                        else:
                            width = base_image.get("width", 0)
                            height = base_image.get("height", 0)

                        # Tentar obter bbox da imagem
                        bbox = self._get_image_bbox(page, xref, page_num + 1)

                        assets.append(ExtractedAsset(
                            page_number=page_num + 1,
                            asset_type="image",
                            image_data=image_bytes,
                            width=width,
                            height=height,
                            format=self.output_format,
                            bbox=bbox
                        ))

                    except Exception as e:
                        logger.warning(f"Erro ao extrair imagem {xref} da página {page_num + 1}: {e}")

        finally:
            doc.close()

        return assets

    def _get_image_bbox(self, page, xref: int, page_num: int) -> Optional[BoundingBox]:
        """Tenta obter bbox da imagem na página."""
        try:
            for img in page.get_images():
                if img[0] == xref:
                    # Obter posição da imagem
                    rects = page.get_image_rects(img)
                    if rects:
                        rect = rects[0]
                        return BoundingBox(
                            x0=rect.x0,
                            y0=rect.y0,
                            x1=rect.x1,
                            y1=rect.y1,
                            page=page_num
                        )
        except Exception:
            pass
        return None

    def _extract_from_docx(self, file_path: Path) -> List[ExtractedAsset]:
        """Extrai imagens de DOCX."""
        if not HAS_PYTHON_DOCX:
            logger.warning("python-docx não disponível para extração de imagens")
            return []

        assets = []
        doc = DocxDocument(str(file_path))

        for rel in doc.part.rels.values():
            if "image" in rel.reltype:
                try:
                    image_bytes = rel.target_part.blob

                    width = 0
                    height = 0

                    if HAS_PIL:
                        img = Image.open(io.BytesIO(image_bytes))
                        width, height = img.size

                        # Filtrar imagens pequenas
                        if width < self.min_size[0] or height < self.min_size[1]:
                            continue

                        # Converter formato
                        output_buffer = io.BytesIO()
                        if img.mode in ('RGBA', 'P'):
                            img = img.convert('RGB')
                        img.save(output_buffer, format=self.output_format.upper(), quality=self.quality)
                        image_bytes = output_buffer.getvalue()

                    assets.append(ExtractedAsset(
                        page_number=1,  # DOCX não tem páginas reais
                        asset_type="image",
                        image_data=image_bytes,
                        width=width,
                        height=height,
                        format=self.output_format
                    ))

                except Exception as e:
                    logger.warning(f"Erro ao extrair imagem de DOCX: {e}")

        return assets

    def save_assets(
        self,
        assets: List[ExtractedAsset],
        output_dir: Path,
        prefix: str = "img"
    ) -> List[Path]:
        """
        Salva assets em disco.

        Args:
            assets: Lista de assets extraídos
            output_dir: Diretório de saída
            prefix: Prefixo para nomes de arquivo

        Returns:
            Lista de caminhos dos arquivos salvos
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_paths = []

        for idx, asset in enumerate(assets):
            filename = f"{prefix}_page{asset.page_number}_{idx + 1}.{asset.format}"
            filepath = output_dir / filename

            with open(filepath, 'wb') as f:
                f.write(asset.image_data)

            saved_paths.append(filepath)

        return saved_paths


def extract_assets(file_path: Path, doc_type: Optional[DocumentType] = None) -> List[ExtractedAsset]:
    """
    Função de conveniência para extrair assets.

    Args:
        file_path: Caminho do arquivo
        doc_type: Tipo do documento (detectado automaticamente se None)

    Returns:
        Lista de ExtractedAsset
    """
    from .detector import detect_document

    file_path = Path(file_path)

    if doc_type is None:
        doc_info = detect_document(file_path)
        doc_type = doc_info.doc_type

    extractor = AssetExtractor()
    return extractor.extract(file_path, doc_type)
