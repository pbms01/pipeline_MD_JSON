"""
structure_analyzer.py - Análise estrutural de documentos.

Este módulo analisa o texto extraído para identificar elementos estruturais:
- Headings (títulos)
- Parágrafos
- Listas
- Tabelas
- Figuras
- Equações
"""
from typing import List, Optional, Tuple, Dict, Any
import re
import logging

from .models import (
    ExtractedText, TextBlock, StructuralAnalysis,
    Heading, Paragraph, ListItem, Table, Figure, Equation,
    Footnote, TableColumn, BoundingBox, ElementType,
    generate_id
)
from .utils import is_heading_text, detect_list_item, normalize_text

logger = logging.getLogger(__name__)


class StructureAnalyzer:
    """Analisa estrutura de documentos extraídos."""

    def __init__(
        self,
        body_font_size: float = 12.0,
        heading_threshold: float = 14.0
    ):
        self.body_font_size = body_font_size
        self.heading_threshold = heading_threshold
        self._heading_counter = 0
        self._paragraph_counter = 0
        self._list_counter = 0
        self._table_counter = 0
        self._figure_counter = 0
        self._equation_counter = 0

    def analyze(self, extracted_texts: List[ExtractedText]) -> List[StructuralAnalysis]:
        """
        Analisa lista de textos extraídos.

        Args:
            extracted_texts: Lista de ExtractedText por página

        Returns:
            Lista de StructuralAnalysis por página
        """
        results = []
        for extracted in extracted_texts:
            analysis = self._analyze_page(extracted)
            results.append(analysis)
        return results

    def _analyze_page(self, extracted: ExtractedText) -> StructuralAnalysis:
        """Analisa uma página."""
        analysis = StructuralAnalysis(page_number=extracted.page_number)

        if not extracted.blocks:
            return analysis

        # Agrupar blocos por proximidade vertical para formar elementos
        current_paragraph_blocks: List[TextBlock] = []
        in_list = False
        list_items: List[TextBlock] = []

        for block in extracted.blocks:
            text = block.text.strip()
            if not text:
                continue

            # Verificar se é heading
            is_heading, level = self._detect_heading(block)
            if is_heading:
                # Finalizar parágrafo anterior se houver
                if current_paragraph_blocks:
                    para = self._create_paragraph(current_paragraph_blocks, extracted.page_number)
                    analysis.paragraphs.append(para)
                    current_paragraph_blocks = []

                # Finalizar lista se houver
                if list_items:
                    analysis.list_items.extend(self._create_list_items(list_items, extracted.page_number))
                    list_items = []
                    in_list = False

                heading = self._create_heading(block, level, extracted.page_number)
                analysis.headings.append(heading)
                continue

            # Verificar se é item de lista
            is_list, list_type, list_level, index = detect_list_item(text)
            if is_list:
                # Finalizar parágrafo anterior se houver
                if current_paragraph_blocks:
                    para = self._create_paragraph(current_paragraph_blocks, extracted.page_number)
                    analysis.paragraphs.append(para)
                    current_paragraph_blocks = []

                list_items.append(block)
                in_list = True
                continue

            # Se estava em lista mas não é mais item
            if in_list and list_items:
                analysis.list_items.extend(self._create_list_items(list_items, extracted.page_number))
                list_items = []
                in_list = False

            # Verificar se parece tabela (múltiplas colunas alinhadas)
            if self._looks_like_table_row(text):
                # Por enquanto, adicionar como parágrafo
                # Tabelas complexas serão detectadas por visão
                pass

            # É parágrafo normal
            current_paragraph_blocks.append(block)

        # Finalizar elementos pendentes
        if current_paragraph_blocks:
            para = self._create_paragraph(current_paragraph_blocks, extracted.page_number)
            analysis.paragraphs.append(para)

        if list_items:
            analysis.list_items.extend(self._create_list_items(list_items, extracted.page_number))

        # Detectar tabelas por padrão no texto raw
        tables = self._detect_tables_in_text(extracted.raw_text, extracted.page_number)
        analysis.tables.extend(tables)

        # Detectar equações
        equations = self._detect_equations(extracted.raw_text, extracted.page_number)
        analysis.equations.extend(equations)

        # Detectar notas de rodapé
        footnotes = self._detect_footnotes(extracted.blocks, extracted.page_number)
        analysis.footnotes.extend(footnotes)

        return analysis

    def _detect_heading(self, block: TextBlock) -> Tuple[bool, int]:
        """Detecta se bloco é heading e retorna nível."""
        text = block.text.strip()

        # Verificar por padrões de numeração
        is_heading, level = is_heading_text(text, block.font_size, self.body_font_size)
        if is_heading:
            return True, level

        # Verificar por tamanho de fonte
        if block.font_size and block.font_size >= self.heading_threshold:
            ratio = block.font_size / self.body_font_size
            if ratio >= 1.8:
                return True, 1
            elif ratio >= 1.5:
                return True, 2
            elif ratio >= 1.2:
                return True, 3

        # Verificar se é curto e em negrito
        if block.is_bold and len(text) < 100 and not text.endswith(('.', ',', ';')):
            return True, 3

        return False, 0

    def _create_heading(self, block: TextBlock, level: int, page: int) -> Heading:
        """Cria elemento Heading."""
        self._heading_counter += 1
        return Heading(
            id=f"h_{self._heading_counter}",
            element_type=ElementType.HEADING,
            page=page,
            bbox=block.bbox,
            text=normalize_text(block.text),
            level=level
        )

    def _create_paragraph(self, blocks: List[TextBlock], page: int) -> Paragraph:
        """Cria elemento Paragraph a partir de blocos."""
        self._paragraph_counter += 1

        # Concatenar texto
        text = " ".join(b.text for b in blocks)
        text = normalize_text(text)

        # Criar bbox que engloba todos os blocos
        if blocks:
            bbox = BoundingBox(
                x0=min(b.bbox.x0 for b in blocks),
                y0=min(b.bbox.y0 for b in blocks),
                x1=max(b.bbox.x1 for b in blocks),
                y1=max(b.bbox.y1 for b in blocks),
                page=page
            )
        else:
            bbox = None

        return Paragraph(
            id=f"p_{self._paragraph_counter}",
            element_type=ElementType.PARAGRAPH,
            page=page,
            bbox=bbox,
            text=text
        )

    def _create_list_items(self, blocks: List[TextBlock], page: int) -> List[ListItem]:
        """Cria elementos ListItem."""
        items = []
        for block in blocks:
            self._list_counter += 1
            is_list, list_type, level, index = detect_list_item(block.text)

            # Remover marcador do texto
            text = re.sub(r'^[-•●○◦▪▸►*]\s+', '', block.text)
            text = re.sub(r'^(\d+|\([a-z]\)|\([ivx]+\))[.)]\s+', '', text, flags=re.IGNORECASE)
            text = normalize_text(text)

            items.append(ListItem(
                id=f"li_{self._list_counter}",
                element_type=ElementType.LIST_ITEM,
                page=page,
                bbox=block.bbox,
                text=text,
                list_type=list_type,
                level=level,
                index=index
            ))
        return items

    def _looks_like_table_row(self, text: str) -> bool:
        """Verifica se texto parece uma linha de tabela."""
        # Múltiplos tabs ou espaços grandes indicam possível tabela
        if '\t' in text and text.count('\t') >= 2:
            return True
        if '|' in text and text.count('|') >= 2:
            return True
        # Múltiplos espaços duplos
        if text.count('  ') >= 3:
            return True
        return False

    def _detect_tables_in_text(self, text: str, page: int) -> List[Table]:
        """Detecta tabelas no texto bruto."""
        tables = []

        # Padrão: linhas com separadores consistentes
        lines = text.split('\n')
        table_lines: List[str] = []
        in_table = False

        for line in lines:
            if self._looks_like_table_row(line):
                if not in_table:
                    in_table = True
                table_lines.append(line)
            else:
                if in_table and len(table_lines) >= 2:
                    table = self._parse_table_lines(table_lines, page)
                    if table:
                        tables.append(table)
                table_lines = []
                in_table = False

        # Verificar última tabela
        if in_table and len(table_lines) >= 2:
            table = self._parse_table_lines(table_lines, page)
            if table:
                tables.append(table)

        return tables

    def _parse_table_lines(self, lines: List[str], page: int) -> Optional[Table]:
        """Tenta parsear linhas como tabela."""
        if not lines:
            return None

        self._table_counter += 1

        # Detectar separador
        separator = '\t' if '\t' in lines[0] else '|' if '|' in lines[0] else '  '

        data = []
        for line in lines:
            if separator == '  ':
                # Split por múltiplos espaços
                cells = re.split(r'\s{2,}', line.strip())
            else:
                cells = [c.strip() for c in line.split(separator)]
            cells = [c for c in cells if c]  # Remover vazios
            if cells:
                data.append(cells)

        if not data:
            return None

        # Assumir primeira linha como cabeçalho
        header = data[0]
        columns = [TableColumn(name=h, col_type="text") for h in header]

        return Table(
            id=f"table_{self._table_counter}",
            element_type=ElementType.TABLE,
            page=page,
            columns=columns,
            data=data[1:] if len(data) > 1 else [],
            confidence=0.6  # Baixa confiança para detecção por texto
        )

    def _detect_equations(self, text: str, page: int) -> List[Equation]:
        """Detecta equações no texto."""
        equations = []

        # Padrões LaTeX
        latex_patterns = [
            r'\$\$(.+?)\$\$',  # Display math
            r'\$(.+?)\$',      # Inline math
            r'\\begin\{equation\}(.+?)\\end\{equation\}',
            r'\\begin\{align\}(.+?)\\end\{align\}',
        ]

        for pattern in latex_patterns:
            for match in re.finditer(pattern, text, re.DOTALL):
                self._equation_counter += 1
                latex = match.group(1).strip()
                is_inline = pattern.startswith(r'\$(.+')

                equations.append(Equation(
                    id=f"eq_{self._equation_counter}",
                    element_type=ElementType.EQUATION,
                    page=page,
                    latex=latex,
                    is_inline=is_inline
                ))

        return equations

    def _detect_footnotes(self, blocks: List[TextBlock], page: int) -> List[Footnote]:
        """Detecta notas de rodapé."""
        footnotes = []

        # Notas geralmente no rodapé, fonte menor
        page_height = max((b.bbox.y1 for b in blocks), default=0)
        footnote_threshold = page_height * 0.85  # Últimos 15% da página

        for block in blocks:
            if block.bbox.y0 > footnote_threshold:
                # Verificar padrão de nota
                text = block.text.strip()
                match = re.match(r'^(\d+|[*†‡§])\s*(.+)', text)
                if match:
                    marker, content = match.groups()
                    footnotes.append(Footnote(
                        id=generate_id("fn"),
                        element_type=ElementType.FOOTNOTE,
                        page=page,
                        bbox=block.bbox,
                        marker=marker,
                        text=content
                    ))

        return footnotes


def analyze_structure(
    extracted_texts: List[ExtractedText],
    body_font_size: float = 12.0,
    heading_threshold: float = 14.0
) -> List[StructuralAnalysis]:
    """
    Função de conveniência para análise estrutural.

    Args:
        extracted_texts: Textos extraídos
        body_font_size: Tamanho da fonte do corpo
        heading_threshold: Threshold para headings

    Returns:
        Lista de StructuralAnalysis
    """
    analyzer = StructureAnalyzer(body_font_size, heading_threshold)
    return analyzer.analyze(extracted_texts)
