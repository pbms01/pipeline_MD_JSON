"""
chunk_generator.py - Geração de chunks para RAG.

Este módulo divide o documento em chunks otimizados para
sistemas de Retrieval Augmented Generation (RAG).
"""
from typing import List, Optional, Dict, Any
import re
import logging

from .models import (
    Chunk, Section, Table, Figure,
    generate_chunk_id
)
from .utils import estimate_token_count
from config.settings import (
    CHUNK_SIZE_DEFAULT, CHUNK_OVERLAP_DEFAULT,
    MIN_CHUNK_SIZE, MAX_CHUNK_SIZE
)

logger = logging.getLogger(__name__)


class ChunkGenerator:
    """Gera chunks semânticos para RAG."""

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE_DEFAULT,
        chunk_overlap: int = CHUNK_OVERLAP_DEFAULT,
        min_chunk_size: int = MIN_CHUNK_SIZE,
        max_chunk_size: int = MAX_CHUNK_SIZE
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self._chunk_index = 0

    def generate(
        self,
        sections: List[Section],
        tables: Optional[List[Table]] = None,
        figures: Optional[List[Figure]] = None,
        document_type: str = "unknown"
    ) -> List[Chunk]:
        """
        Gera chunks do documento.

        Estratégia:
        1. Chunking por seções (respeita hierarquia)
        2. Chunks especiais para tabelas
        3. Metadados incluídos em cada chunk

        Args:
            sections: Seções do documento
            tables: Tabelas (opcional)
            figures: Figuras (opcional)
            document_type: Tipo de documento

        Returns:
            Lista de Chunks
        """
        chunks = []

        # Processar seções
        for section in sections:
            section_chunks = self._chunk_section(section, document_type)
            chunks.extend(section_chunks)

        # Processar tabelas como chunks separados
        if tables:
            for table in tables:
                table_chunk = self._chunk_table(table, document_type)
                if table_chunk:
                    chunks.append(table_chunk)

        return chunks

    def _chunk_section(
        self,
        section: Section,
        document_type: str,
        parent_title: Optional[str] = None
    ) -> List[Chunk]:
        """Gera chunks de uma seção."""
        chunks = []

        # Construir título completo com hierarquia
        full_title = section.title
        if parent_title:
            full_title = f"{parent_title} > {section.title}"

        # Se seção é pequena, criar chunk único
        content = section.content.strip()
        token_count = estimate_token_count(content)

        if token_count <= self.chunk_size:
            if token_count >= self.min_chunk_size or content:
                chunk = self._create_chunk(
                    text=content,
                    section_id=section.id,
                    section_title=full_title,
                    page=section.page_start,
                    has_table=bool(section.tables_refs),
                    has_figure=bool(section.figures_refs),
                    document_type=document_type
                )
                chunks.append(chunk)
        else:
            # Dividir conteúdo em chunks menores
            text_chunks = self._split_text(content)
            for text in text_chunks:
                chunk = self._create_chunk(
                    text=text,
                    section_id=section.id,
                    section_title=full_title,
                    page=section.page_start,
                    has_table=bool(section.tables_refs),
                    has_figure=bool(section.figures_refs),
                    document_type=document_type
                )
                chunks.append(chunk)

        # Processar subseções recursivamente
        for subsection in section.subsections:
            sub_chunks = self._chunk_section(subsection, document_type, full_title)
            chunks.extend(sub_chunks)

        return chunks

    def _split_text(self, text: str) -> List[str]:
        """Divide texto em chunks com overlap."""
        if not text:
            return []

        # Dividir por parágrafos primeiro
        paragraphs = re.split(r'\n\n+', text)

        chunks = []
        current_chunk = []
        current_tokens = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_tokens = estimate_token_count(para)

            # Se parágrafo é maior que chunk máximo, dividir por sentenças
            if para_tokens > self.max_chunk_size:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_tokens = 0

                # Dividir parágrafo em sentenças
                sentences = self._split_sentences(para)
                for sentence in sentences:
                    sent_tokens = estimate_token_count(sentence)
                    if current_tokens + sent_tokens > self.chunk_size and current_chunk:
                        chunks.append(" ".join(current_chunk))
                        # Overlap: manter última sentença
                        if self.chunk_overlap > 0 and current_chunk:
                            current_chunk = current_chunk[-1:]
                            current_tokens = estimate_token_count(current_chunk[0])
                        else:
                            current_chunk = []
                            current_tokens = 0
                    current_chunk.append(sentence)
                    current_tokens += sent_tokens
                continue

            # Verificar se adicionar parágrafo excede tamanho
            if current_tokens + para_tokens > self.chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                # Overlap: manter último parágrafo se couber
                if self.chunk_overlap > 0 and para_tokens < self.chunk_overlap:
                    current_chunk = [current_chunk[-1]] if current_chunk else []
                    current_tokens = estimate_token_count(current_chunk[0]) if current_chunk else 0
                else:
                    current_chunk = []
                    current_tokens = 0

            current_chunk.append(para)
            current_tokens += para_tokens

        # Adicionar chunk final
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """Divide texto em sentenças."""
        # Padrão simples para fim de sentença
        pattern = r'(?<=[.!?])\s+(?=[A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ])'
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]

    def _chunk_table(self, table: Table, document_type: str) -> Optional[Chunk]:
        """Cria chunk para uma tabela."""
        # Criar representação textual da tabela
        lines = []

        if table.title:
            lines.append(f"Tabela: {table.title}")

        # Cabeçalhos
        if table.columns:
            headers = [c.name for c in table.columns]
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join(["---"] * len(headers)) + "|")

        # Dados
        for row in table.data[:20]:  # Limitar linhas para não exceder chunk
            row_str = [str(cell) if cell is not None else "" for cell in row]
            lines.append("| " + " | ".join(row_str) + " |")

        if len(table.data) > 20:
            lines.append(f"... ({len(table.data) - 20} linhas adicionais)")

        text = "\n".join(lines)

        if not text.strip():
            return None

        return self._create_chunk(
            text=text,
            section_id=None,
            section_title=f"Tabela: {table.title}" if table.title else "Tabela",
            page=table.page,
            has_table=True,
            has_figure=False,
            document_type=document_type
        )

    def _create_chunk(
        self,
        text: str,
        section_id: Optional[str],
        section_title: Optional[str],
        page: int,
        has_table: bool,
        has_figure: bool,
        document_type: str
    ) -> Chunk:
        """Cria um chunk."""
        chunk_id = generate_chunk_id(self._chunk_index)
        self._chunk_index += 1

        return Chunk(
            id=chunk_id,
            text=text,
            token_count=estimate_token_count(text),
            section_id=section_id,
            section_title=section_title,
            page=page,
            chunk_index=self._chunk_index - 1,
            has_table=has_table,
            has_figure=has_figure,
            metadata={
                "document_type": document_type
            }
        )


def generate_chunks(
    sections: List[Section],
    tables: Optional[List[Table]] = None,
    figures: Optional[List[Figure]] = None,
    chunk_size: int = CHUNK_SIZE_DEFAULT,
    chunk_overlap: int = CHUNK_OVERLAP_DEFAULT,
    document_type: str = "unknown"
) -> List[Chunk]:
    """
    Função de conveniência para gerar chunks.

    Args:
        sections: Seções do documento
        tables: Tabelas (opcional)
        figures: Figuras (opcional)
        chunk_size: Tamanho do chunk em tokens
        chunk_overlap: Overlap entre chunks
        document_type: Tipo de documento

    Returns:
        Lista de Chunks
    """
    generator = ChunkGenerator(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    return generator.generate(sections, tables, figures, document_type)
