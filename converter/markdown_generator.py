"""
markdown_generator.py - Gera Markdown estruturado do documento.

Este módulo gera saída Markdown formatada a partir do ParsedDocument,
incluindo frontmatter YAML, table of contents e formatação apropriada.
"""
from typing import List, Optional
from datetime import datetime
import logging

from .models import (
    ParsedDocument, Section, Table, Figure, Equation, Footnote
)

logger = logging.getLogger(__name__)


class MarkdownGenerator:
    """Gera Markdown a partir de ParsedDocument."""

    def __init__(
        self,
        include_frontmatter: bool = True,
        include_toc: bool = False,
        assets_path: str = "assets"
    ):
        self.include_frontmatter = include_frontmatter
        self.include_toc = include_toc
        self.assets_path = assets_path

    def generate(self, doc: ParsedDocument) -> str:
        """
        Gera Markdown completo do documento.

        Args:
            doc: ParsedDocument

        Returns:
            String Markdown
        """
        parts = []

        # Frontmatter YAML
        if self.include_frontmatter:
            frontmatter = self._generate_frontmatter(doc)
            parts.append(frontmatter)

        # Título
        if doc.metadata.title:
            parts.append(f"# {doc.metadata.title}\n")

        # Table of Contents
        if self.include_toc:
            toc = self._generate_toc(doc.sections)
            if toc:
                parts.append("## Sumário\n")
                parts.append(toc)
                parts.append("")

        # Resumo
        if doc.summary:
            parts.append("## Resumo\n")
            parts.append(doc.summary)
            parts.append("")

        # Seções
        for section in doc.sections:
            section_md = self._render_section(section, doc)
            parts.append(section_md)

        # Figuras não referenciadas nas seções
        unreferenced_figures = self._get_unreferenced_figures(doc)
        if unreferenced_figures:
            parts.append("## Figuras\n")
            for fig in unreferenced_figures:
                parts.append(self._render_figure(fig))

        # Notas de rodapé
        if doc.footnotes:
            parts.append("## Notas\n")
            for fn in doc.footnotes:
                parts.append(f"[^{fn.marker}]: {fn.text}\n")

        return "\n".join(parts)

    def _generate_frontmatter(self, doc: ParsedDocument) -> str:
        """Gera frontmatter YAML."""
        lines = ["---"]

        if doc.metadata.title:
            lines.append(f'title: "{doc.metadata.title}"')

        if doc.metadata.authors:
            if len(doc.metadata.authors) == 1:
                lines.append(f'author: "{doc.metadata.authors[0]}"')
            else:
                lines.append("authors:")
                for author in doc.metadata.authors:
                    lines.append(f'  - "{author}"')

        if doc.metadata.date:
            lines.append(f"date: {doc.metadata.date}")

        lines.append(f"document_type: {doc.metadata.document_type}")
        lines.append(f"source_file: {doc.metadata.source_file}")
        lines.append(f"page_count: {doc.metadata.page_count}")
        lines.append(f"language: {doc.metadata.language}")

        if doc.metadata.keywords:
            lines.append("keywords:")
            for kw in doc.metadata.keywords:
                lines.append(f'  - "{kw}"')

        lines.append(f"converted_at: {datetime.now().isoformat()}")
        lines.append("---\n")

        return "\n".join(lines)

    def _generate_toc(self, sections: List[Section], level: int = 0) -> str:
        """Gera table of contents."""
        lines = []
        indent = "  " * level

        for section in sections:
            # Criar link para a seção
            anchor = self._create_anchor(section.title)
            lines.append(f"{indent}- [{section.title}](#{anchor})")

            # Subseções recursivamente
            if section.subsections:
                sub_toc = self._generate_toc(section.subsections, level + 1)
                lines.append(sub_toc)

        return "\n".join(lines)

    def _create_anchor(self, text: str) -> str:
        """Cria anchor para link interno."""
        # Converter para lowercase, remover caracteres especiais
        anchor = text.lower()
        anchor = anchor.replace(" ", "-")
        # Remover caracteres não alfanuméricos exceto hífen
        anchor = "".join(c for c in anchor if c.isalnum() or c == "-")
        return anchor

    def _render_section(self, section: Section, doc: ParsedDocument, level_offset: int = 0) -> str:
        """Renderiza uma seção como Markdown."""
        parts = []

        # Heading (ajustar nível)
        heading_level = min(section.level + level_offset, 6)
        heading_prefix = "#" * heading_level
        parts.append(f"{heading_prefix} {section.title}\n")

        # Conteúdo
        if section.content:
            parts.append(section.content)
            parts.append("")

        # Tabelas referenciadas
        for table_ref in section.tables_refs:
            table = self._find_table(doc.tables, table_ref)
            if table:
                parts.append(self._render_table(table))
                parts.append("")

        # Figuras referenciadas
        for fig_ref in section.figures_refs:
            figure = self._find_figure(doc.figures, fig_ref)
            if figure:
                parts.append(self._render_figure(figure))
                parts.append("")

        # Subseções recursivamente
        for subsection in section.subsections:
            sub_md = self._render_section(subsection, doc, level_offset)
            parts.append(sub_md)

        return "\n".join(parts)

    def _render_table(self, table: Table) -> str:
        """Renderiza tabela como Markdown."""
        lines = []

        # Título
        if table.title:
            lines.append(f"**{table.title}**\n")

        # Se já tem markdown pronto (da visão), usar
        if table.markdown:
            lines.append(table.markdown)
            return "\n".join(lines)

        # Construir tabela
        if not table.columns and not table.data:
            return ""

        # Headers
        if table.columns:
            headers = [col.name for col in table.columns]
        elif table.data:
            headers = [f"Col {i+1}" for i in range(len(table.data[0]))]
        else:
            return ""

        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")

        # Data rows
        for row in table.data:
            cells = [str(cell) if cell is not None else "" for cell in row]
            # Garantir mesmo número de células que headers
            while len(cells) < len(headers):
                cells.append("")
            lines.append("| " + " | ".join(cells[:len(headers)]) + " |")

        return "\n".join(lines)

    def _render_figure(self, figure: Figure) -> str:
        """Renderiza figura como Markdown."""
        parts = []

        # Path da imagem
        if figure.asset_path:
            img_path = f"{self.assets_path}/{figure.asset_path}"
        else:
            img_path = ""

        # Alt text
        alt = figure.alt_text or figure.title or "Figura"

        if img_path:
            parts.append(f"![{alt}]({img_path})")

        # Caption
        if figure.caption:
            parts.append(f"*{figure.caption}*")
        elif figure.title:
            parts.append(f"*{figure.title}*")

        return "\n".join(parts)

    def _render_equation(self, equation: Equation) -> str:
        """Renderiza equação como Markdown/LaTeX."""
        if equation.is_inline:
            return f"${equation.latex}$"
        else:
            lines = ["$$", equation.latex, "$$"]
            if equation.label:
                lines.append(f"*({equation.label})*")
            return "\n".join(lines)

    def _find_table(self, tables: List[Table], table_id: str) -> Optional[Table]:
        """Encontra tabela por ID."""
        for table in tables:
            if table.id == table_id:
                return table
        return None

    def _find_figure(self, figures: List[Figure], fig_id: str) -> Optional[Figure]:
        """Encontra figura por ID."""
        for fig in figures:
            if fig.id == fig_id:
                return fig
        return None

    def _get_unreferenced_figures(self, doc: ParsedDocument) -> List[Figure]:
        """Retorna figuras não referenciadas em seções."""
        referenced = set()
        for section in doc.sections:
            referenced.update(section.figures_refs)
            for sub in section.subsections:
                referenced.update(sub.figures_refs)

        return [f for f in doc.figures if f.id not in referenced]


def generate_markdown(
    doc: ParsedDocument,
    include_frontmatter: bool = True,
    include_toc: bool = False,
    assets_path: str = "assets"
) -> str:
    """
    Função de conveniência para gerar Markdown.

    Args:
        doc: ParsedDocument
        include_frontmatter: Incluir frontmatter YAML
        include_toc: Incluir table of contents
        assets_path: Caminho para assets

    Returns:
        String Markdown
    """
    generator = MarkdownGenerator(
        include_frontmatter=include_frontmatter,
        include_toc=include_toc,
        assets_path=assets_path
    )
    return generator.generate(doc)
