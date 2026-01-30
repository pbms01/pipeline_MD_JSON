"""
json_generator.py - Gera JSON híbrido (camada fixa + camada dinâmica).

Este módulo gera a saída JSON estruturada do documento, combinando:
- Camada fixa: metadata, content, entities, chunks, processing_info
- Camada dinâmica: structured_data (schema inferido)
"""
import json
from typing import Dict, Any, List
from datetime import datetime
import logging

from .models import (
    ParsedDocument, Section, Table, Figure,
    ExtractedEntities, Chunk, DocumentMetadata,
    ProcessingInfo, InferredSchema
)

logger = logging.getLogger(__name__)


class JSONGenerator:
    """
    Gera JSON híbrido com:
    - Camada fixa: metadata, content, entities, chunks, processing_info
    - Camada dinâmica: structured_data (schema inferido)
    """

    def __init__(
        self,
        include_chunks: bool = True,
        include_raw_text: bool = False,
        include_structured_data: bool = True,
        pretty_print: bool = True
    ):
        self.include_chunks = include_chunks
        self.include_raw_text = include_raw_text
        self.include_structured_data = include_structured_data
        self.pretty_print = pretty_print

    def generate(self, doc: ParsedDocument) -> Dict[str, Any]:
        """
        Gera estrutura JSON completa do documento.

        Args:
            doc: ParsedDocument processado

        Returns:
            Dicionário JSON-serializable
        """
        result = {
            # === CAMADA FIXA ===
            "metadata": self._serialize_metadata(doc.metadata),
            "content": self._serialize_content(doc),
            "entities": self._serialize_entities(doc.entities),
            "processing_info": self._serialize_processing(doc.processing)
        }

        # Chunks (fixo, mas opcional)
        if self.include_chunks:
            result["chunks"] = self._serialize_chunks(doc.chunks)

        # === CAMADA DINÂMICA ===
        if self.include_structured_data and doc.structured_data:
            result["structured_data"] = doc.structured_data.to_dict()
        elif self.include_structured_data:
            # Sem inferência, incluir placeholder
            result["structured_data"] = {
                "_schema_inferred": False,
                "_document_type": doc.metadata.document_type,
                "_note": "Schema inference was disabled"
            }

        # Raw text (opcional)
        if self.include_raw_text:
            result["raw_text_by_page"] = doc.raw_text_by_page

        return result

    def generate_string(self, doc: ParsedDocument) -> str:
        """Gera JSON como string formatada."""
        data = self.generate(doc)

        if self.pretty_print:
            return json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
                default=self._json_serializer
            )
        else:
            return json.dumps(
                data,
                ensure_ascii=False,
                default=self._json_serializer
            )

    def _json_serializer(self, obj):
        """Serializer customizado para tipos não-JSON."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return str(obj)

    def _serialize_metadata(self, meta: DocumentMetadata) -> Dict[str, Any]:
        """Serializa metadados (camada fixa)."""
        return {
            "id": meta.id,
            "source_file": meta.source_file,
            "title": meta.title,
            "document_type": meta.document_type,
            "document_type_confidence": meta.document_type_confidence,
            "authors": meta.authors,
            "date": meta.date,
            "language": meta.language,
            "page_count": meta.page_count,
            "keywords": meta.keywords
        }

    def _serialize_content(self, doc: ParsedDocument) -> Dict[str, Any]:
        """Serializa conteúdo estruturado (camada fixa)."""
        return {
            "summary": doc.summary,
            "sections": [self._serialize_section(s) for s in doc.sections],
            "tables": [self._serialize_table(t) for t in doc.tables],
            "figures": [self._serialize_figure(f) for f in doc.figures]
        }

    def _serialize_section(self, section: Section) -> Dict[str, Any]:
        """Serializa uma seção (estrutura genérica)."""
        return {
            "id": section.id,
            "title": section.title,
            "level": section.level,
            "content": section.content,
            "page_start": section.page_start,
            "page_end": section.page_end,
            "subsections": [
                self._serialize_section(s) for s in section.subsections
            ],
            "tables_refs": section.tables_refs,
            "figures_refs": section.figures_refs
        }

    def _serialize_table(self, table: Table) -> Dict[str, Any]:
        """Serializa uma tabela."""
        return {
            "id": table.id,
            "title": table.title,
            "page": table.page,
            "columns": [
                {"name": c.name, "type": c.col_type}
                for c in table.columns
            ],
            "data": table.data,
            "has_merged_cells": table.has_merged_cells,
            "source": table.processing_method.value if table.processing_method else "text_extraction",
            "confidence": table.confidence
        }

    def _serialize_figure(self, figure: Figure) -> Dict[str, Any]:
        """Serializa uma figura."""
        result = {
            "id": figure.id,
            "asset_path": figure.asset_path,
            "title": figure.title,
            "caption": figure.caption,
            "alt_text": figure.alt_text,
            "figure_type": figure.figure_type,
            "page": figure.page
        }

        if figure.width and figure.height:
            result["dimensions"] = {
                "width": figure.width,
                "height": figure.height
            }

        return result

    def _serialize_entities(self, entities: ExtractedEntities) -> Dict[str, Any]:
        """Serializa entidades (camada fixa, estrutura padronizada)."""
        return entities.to_dict()

    def _serialize_chunks(self, chunks: List[Chunk]) -> List[Dict[str, Any]]:
        """Serializa chunks para RAG (camada fixa)."""
        return [chunk.to_dict() for chunk in chunks]

    def _serialize_processing(self, proc: ProcessingInfo) -> Dict[str, Any]:
        """Serializa informações de processamento."""
        return proc.to_dict()


def generate_json(
    doc: ParsedDocument,
    as_string: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Função de conveniência para gerar JSON.

    Args:
        doc: ParsedDocument
        as_string: Se True, retorna string JSON
        **kwargs: Parâmetros adicionais para JSONGenerator

    Returns:
        Dicionário JSON ou string
    """
    generator = JSONGenerator(**kwargs)

    if as_string:
        return generator.generate_string(doc)
    return generator.generate(doc)
