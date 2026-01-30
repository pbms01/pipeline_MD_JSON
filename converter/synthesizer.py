"""
synthesizer.py - Sintetiza resultados em ParsedDocument.

Este módulo combina os resultados de todas as etapas de processamento
em uma estrutura unificada ParsedDocument.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import logging

from .models import (
    ParsedDocument, DocumentMetadata, ProcessingInfo,
    Section, Table, Figure, Equation, Footnote,
    ExtractedText, StructuralAnalysis, RoutingPlan, VisionResult,
    ExtractedEntities, generate_doc_id, generate_section_id
)

logger = logging.getLogger(__name__)


class Synthesizer:
    """Sintetiza resultados em ParsedDocument."""

    def __init__(self):
        self._section_counter = 0

    def synthesize(
        self,
        source_file: str,
        extracted_texts: List[ExtractedText],
        analysis_results: List[StructuralAnalysis],
        routing_plans: Optional[List[RoutingPlan]] = None,
        vision_results: Optional[List[VisionResult]] = None,
        extracted_assets: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> ParsedDocument:
        """
        Sintetiza todos os resultados em ParsedDocument.

        Args:
            source_file: Nome do arquivo original
            extracted_texts: Textos extraídos por página
            analysis_results: Análises estruturais por página
            routing_plans: Planos de roteamento (opcional)
            vision_results: Resultados de visão (opcional)
            extracted_assets: Assets extraídos (opcional)
            **kwargs: Parâmetros adicionais

        Returns:
            ParsedDocument
        """
        # Criar metadados
        metadata = self._create_metadata(source_file, extracted_texts, analysis_results)

        # Combinar seções de todas as páginas
        sections = self._build_sections(analysis_results, vision_results)

        # Coletar tabelas
        tables = self._collect_tables(analysis_results, vision_results)

        # Coletar figuras
        figures = self._collect_figures(analysis_results, vision_results, extracted_assets)

        # Coletar equações
        equations = self._collect_equations(analysis_results, vision_results)

        # Coletar footnotes
        footnotes = self._collect_footnotes(analysis_results)

        # Criar mapa de texto bruto por página
        raw_text_by_page = {
            et.page_number: et.raw_text
            for et in extracted_texts
        }

        # Gerar resumo (placeholder - será gerado por LLM se necessário)
        summary = self._generate_summary_placeholder(extracted_texts)

        return ParsedDocument(
            metadata=metadata,
            sections=sections,
            tables=tables,
            figures=figures,
            equations=equations,
            footnotes=footnotes,
            summary=summary,
            raw_text_by_page=raw_text_by_page,
            processing=ProcessingInfo()
        )

    def _create_metadata(
        self,
        source_file: str,
        extracted_texts: List[ExtractedText],
        analysis_results: List[StructuralAnalysis]
    ) -> DocumentMetadata:
        """Cria metadados do documento."""
        # Extrair título do primeiro heading
        title = None
        for analysis in analysis_results:
            if analysis.headings:
                title = analysis.headings[0].text
                break

        # Contar páginas
        page_count = len(extracted_texts)

        return DocumentMetadata(
            id=generate_doc_id(),
            source_file=source_file,
            title=title,
            document_type="unknown",  # Será preenchido pela inferência de schema
            page_count=page_count,
            language="pt"
        )

    def _build_sections(
        self,
        analysis_results: List[StructuralAnalysis],
        vision_results: Optional[List[VisionResult]] = None
    ) -> List[Section]:
        """Constrói hierarquia de seções."""
        sections: List[Section] = []
        current_sections: Dict[int, Section] = {}  # level -> section

        for analysis in analysis_results:
            page = analysis.page_number

            for heading in analysis.headings:
                level = heading.level

                # Coletar conteúdo para esta seção
                content_parts = []
                for para in analysis.paragraphs:
                    content_parts.append(para.text)

                content = "\n\n".join(content_parts)

                section = Section(
                    id=generate_section_id(self._section_counter),
                    title=heading.text,
                    level=level,
                    content=content,
                    page_start=page,
                    page_end=page
                )
                self._section_counter += 1

                # Adicionar referências a tabelas e figuras nesta página
                for table in analysis.tables:
                    section.tables_refs.append(table.id)
                for figure in analysis.figures:
                    section.figures_refs.append(figure.id)

                # Organizar hierarquia
                if level == 1:
                    sections.append(section)
                    current_sections = {1: section}
                else:
                    # Encontrar seção pai
                    parent_level = level - 1
                    while parent_level > 0 and parent_level not in current_sections:
                        parent_level -= 1

                    if parent_level in current_sections:
                        current_sections[parent_level].subsections.append(section)
                    else:
                        sections.append(section)

                    current_sections[level] = section

        # Se não houver headings, criar seção única com todo o conteúdo
        if not sections:
            all_content = []
            for analysis in analysis_results:
                for para in analysis.paragraphs:
                    all_content.append(para.text)

            if all_content:
                sections.append(Section(
                    id=generate_section_id(0),
                    title="Documento",
                    level=1,
                    content="\n\n".join(all_content),
                    page_start=1,
                    page_end=len(analysis_results)
                ))

        return sections

    def _collect_tables(
        self,
        analysis_results: List[StructuralAnalysis],
        vision_results: Optional[List[VisionResult]] = None
    ) -> List[Table]:
        """Coleta todas as tabelas."""
        tables = []
        seen_ids = set()

        # Tabelas da análise estrutural
        for analysis in analysis_results:
            for table in analysis.tables:
                if table.id not in seen_ids:
                    tables.append(table)
                    seen_ids.add(table.id)

        # Tabelas da visão (podem sobrescrever ou adicionar)
        if vision_results:
            for vr in vision_results:
                for table in vr.tables:
                    if table.id not in seen_ids:
                        tables.append(table)
                        seen_ids.add(table.id)

        return tables

    def _collect_figures(
        self,
        analysis_results: List[StructuralAnalysis],
        vision_results: Optional[List[VisionResult]] = None,
        extracted_assets: Optional[List[Dict[str, Any]]] = None
    ) -> List[Figure]:
        """Coleta todas as figuras."""
        figures = []
        seen_ids = set()

        # Figuras da análise estrutural
        for analysis in analysis_results:
            for figure in analysis.figures:
                if figure.id not in seen_ids:
                    figures.append(figure)
                    seen_ids.add(figure.id)

        # Figuras da visão
        if vision_results:
            for vr in vision_results:
                for figure in vr.figures:
                    if figure.id not in seen_ids:
                        figures.append(figure)
                        seen_ids.add(figure.id)

        # Assets extraídos que não têm figura correspondente
        if extracted_assets:
            for idx, asset in enumerate(extracted_assets):
                fig_id = f"fig_asset_{idx}"
                if fig_id not in seen_ids:
                    figure = Figure(
                        id=fig_id,
                        element_type="figure",
                        page=asset.get("page", 1),
                        asset_path=asset.get("path", ""),
                        figure_type="image"
                    )
                    figures.append(figure)

        return figures

    def _collect_equations(
        self,
        analysis_results: List[StructuralAnalysis],
        vision_results: Optional[List[VisionResult]] = None
    ) -> List[Equation]:
        """Coleta todas as equações."""
        equations = []
        seen_ids = set()

        for analysis in analysis_results:
            for eq in analysis.equations:
                if eq.id not in seen_ids:
                    equations.append(eq)
                    seen_ids.add(eq.id)

        if vision_results:
            for vr in vision_results:
                for eq in vr.equations:
                    if eq.id not in seen_ids:
                        equations.append(eq)
                        seen_ids.add(eq.id)

        return equations

    def _collect_footnotes(
        self,
        analysis_results: List[StructuralAnalysis]
    ) -> List[Footnote]:
        """Coleta todas as notas de rodapé."""
        footnotes = []
        for analysis in analysis_results:
            footnotes.extend(analysis.footnotes)
        return footnotes

    def _generate_summary_placeholder(
        self,
        extracted_texts: List[ExtractedText]
    ) -> str:
        """Gera placeholder de resumo."""
        # Pegar primeiros parágrafos como resumo temporário
        all_text = " ".join(et.raw_text for et in extracted_texts[:3])

        # Truncar
        if len(all_text) > 500:
            all_text = all_text[:500] + "..."

        return all_text


def synthesize_document(
    source_file: str,
    extracted_texts: List[ExtractedText],
    analysis_results: List[StructuralAnalysis],
    routing_plans: Optional[List[RoutingPlan]] = None,
    vision_results: Optional[List[VisionResult]] = None,
    extracted_assets: Optional[List[Dict[str, Any]]] = None,
    **kwargs
) -> ParsedDocument:
    """
    Função de conveniência para sintetizar documento.

    Args:
        source_file: Nome do arquivo
        extracted_texts: Textos extraídos
        analysis_results: Análises estruturais
        routing_plans: Planos de roteamento
        vision_results: Resultados de visão
        extracted_assets: Assets extraídos
        **kwargs: Parâmetros adicionais

    Returns:
        ParsedDocument
    """
    synthesizer = Synthesizer()
    return synthesizer.synthesize(
        source_file=source_file,
        extracted_texts=extracted_texts,
        analysis_results=analysis_results,
        routing_plans=routing_plans,
        vision_results=vision_results,
        extracted_assets=extracted_assets,
        **kwargs
    )
