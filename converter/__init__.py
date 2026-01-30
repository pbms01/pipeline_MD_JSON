"""
converter/__init__.py - Orquestrador principal do pipeline v3 híbrido.

Este módulo coordena todas as etapas do pipeline de conversão:
1. Detecção de tipo e características
2. Extração de texto bruto
3. Análise estrutural
4. Roteamento por complexidade
5. Processamento visual (quando necessário)
6. Síntese em ParsedDocument
7. Inferência de schema específico
8. Extração de entidades
9. Geração de chunks
10. Geração de outputs (MD + JSON híbrido)
"""
from pathlib import Path
from typing import Optional, Callable
import time
import json
import logging

from .models import (
    ParsedDocument, DocumentMetadata, ConversionOutput,
    ConversionConfig, ProcessingInfo, InferredSchema
)
from .detector import detect_document, DocumentInfo
from .text_extractor import TextExtractor, extract_text
from .structure_analyzer import analyze_structure
from .complexity_router import route_complexity
from .asset_extractor import AssetExtractor, extract_assets
from .renderer import render_document
from .vision_processor import VisionProcessor
from .schema_inferrer import infer_document_schema, detect_and_infer
from .entity_extractor import extract_entities
from .synthesizer import synthesize_document
from .chunk_generator import generate_chunks
from .markdown_generator import generate_markdown
from .json_generator import generate_json

from config.settings import SUPPORTED_EXTENSIONS, MAX_PAGES, OUTPUT_DIR

logger = logging.getLogger(__name__)


def convert_document(
    file_path: Path,
    config: Optional[ConversionConfig] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> ConversionOutput:
    """
    Converte um documento para Markdown e JSON híbrido.

    Pipeline v3:
    1. Detectar tipo e características
    2. Extrair texto bruto
    3. Analisar estrutura
    4. Rotear complexidade
    5. Processar elementos complexos com visão
    6. Sintetizar em ParsedDocument
    7. Inferir schema específico (se habilitado)
    8. Extrair entidades
    9. Gerar chunks
    10. Gerar outputs (MD + JSON híbrido)

    Args:
        file_path: Caminho do documento
        config: Configurações de conversão
        progress_callback: Callback de progresso (stage, current, total)

    Returns:
        ConversionOutput com markdown, json e metadados
    """
    config = config or ConversionConfig()
    file_path = Path(file_path)
    output_dir = Path(config.output_dir) if config.output_dir else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    errors = []
    warnings = []
    total_tokens = 0
    vision_calls = 0

    def notify(stage: str, current: int, total: int):
        if progress_callback:
            progress_callback(stage, current, total)
        logger.info(f"Stage: {stage} - {current}/{total}")

    try:
        # === 1. DETECÇÃO ===
        notify("detection", 0, 1)
        doc_info = detect_document(file_path)
        notify("detection", 1, 1)

        if doc_info.page_count > MAX_PAGES:
            errors.append(f"Documento excede limite de {MAX_PAGES} páginas")
            return _error_output(errors)

        # === 2. EXTRAÇÃO DE TEXTO ===
        notify("text_extraction", 0, doc_info.page_count)
        text_extractor = TextExtractor()
        extracted_texts = text_extractor.extract(file_path, doc_info.doc_type)
        notify("text_extraction", len(extracted_texts), len(extracted_texts))

        # Texto completo para análises posteriores
        full_text = "\n\n".join(et.raw_text for et in extracted_texts)

        # Calibrar thresholds
        body_font = text_extractor.get_body_font_size() or 12.0
        heading_threshold = text_extractor.get_heading_threshold() or 14.0

        # === 3. ANÁLISE ESTRUTURAL ===
        notify("structure_analysis", 0, len(extracted_texts))
        analysis_results = analyze_structure(
            extracted_texts,
            body_font_size=body_font,
            heading_threshold=heading_threshold
        )
        notify("structure_analysis", len(analysis_results), len(analysis_results))

        # === 4. ROTEAMENTO ===
        notify("routing", 0, 1)
        routing_plans = route_complexity(
            analysis_results,
            document_type=doc_info.doc_type.value,
            prefer_vision_for_tables=config.prefer_vision_for_tables,
            prefer_vision_for_equations=config.prefer_vision_for_equations
        )
        notify("routing", 1, 1)

        # === 5. EXTRAÇÃO DE ASSETS ===
        notify("asset_extraction", 0, 1)
        assets = extract_assets(file_path, doc_info.doc_type)
        assets_dir = output_dir / "assets"
        assets_dir.mkdir(exist_ok=True)
        asset_extractor = AssetExtractor()
        asset_paths = asset_extractor.save_assets(assets, assets_dir)
        extracted_assets = [
            {"path": str(p.name), "page": a.page_number}
            for p, a in zip(asset_paths, assets)
        ]
        notify("asset_extraction", 1, 1)

        # === 6. PROCESSAMENTO COM VISÃO ===
        vision_results = []
        pages_needing_vision = [
            (plan.page_number, plan)
            for plan in routing_plans
            if plan.requires_full_page_vision
        ]

        if pages_needing_vision:
            notify("vision_processing", 0, len(pages_needing_vision))
            try:
                rendered_pages = render_document(file_path)
                vision_processor = VisionProcessor()

                for idx, (page_num, plan) in enumerate(pages_needing_vision):
                    if page_num <= len(rendered_pages):
                        page_image = rendered_pages[page_num - 1].image
                        result = vision_processor.process_page(
                            page_image, page_num, doc_info.page_count, plan
                        )
                        vision_results.append(result)
                        total_tokens += result.tokens_used
                        vision_calls += 1
                    notify("vision_processing", idx + 1, len(pages_needing_vision))
            except Exception as e:
                warnings.append(f"Vision processing failed: {e}")
                logger.warning(f"Vision processing error: {e}")

        # === 7. SÍNTESE INICIAL ===
        notify("synthesis", 0, 1)
        parsed_doc = synthesize_document(
            source_file=file_path.name,
            extracted_texts=extracted_texts,
            analysis_results=analysis_results,
            routing_plans=routing_plans,
            vision_results=vision_results,
            extracted_assets=extracted_assets,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap
        )
        notify("synthesis", 1, 1)

        # === 8. INFERÊNCIA DE SCHEMA (NOVO) ===
        inferred_schema = None
        schema_confidence = 0.0

        if config.enable_schema_inference:
            notify("schema_inference", 0, 1)

            try:
                inferred_schema = infer_document_schema(
                    full_text,
                    include_explanations=config.include_fields_explanation
                )
                schema_confidence = inferred_schema.confidence

                # Atualizar metadados com tipo inferido
                parsed_doc.metadata.document_type = inferred_schema.document_type
                parsed_doc.metadata.document_type_confidence = schema_confidence

                # Estimar tokens usados (aproximado)
                total_tokens += 2000  # Estimativa conservadora

            except Exception as e:
                warnings.append(f"Schema inference failed: {e}")
                logger.warning(f"Schema inference error: {e}")
                inferred_schema = InferredSchema(
                    schema_inferred=False,
                    document_type="unknown",
                    confidence=0.0,
                    fields={"_error": str(e)}
                )

            notify("schema_inference", 1, 1)

        parsed_doc.structured_data = inferred_schema

        # === 9. EXTRAÇÃO DE ENTIDADES ===
        if config.extract_entities:
            notify("entity_extraction", 0, 1)

            try:
                entities = extract_entities(full_text, use_llm=True)
                parsed_doc.entities = entities
                total_tokens += 1000  # Estimativa
            except Exception as e:
                warnings.append(f"Entity extraction failed: {e}")
                logger.warning(f"Entity extraction error: {e}")

            notify("entity_extraction", 1, 1)

        # === 10. GERAÇÃO DE CHUNKS ===
        notify("chunk_generation", 0, 1)
        parsed_doc.chunks = generate_chunks(
            parsed_doc.sections,
            parsed_doc.tables,
            parsed_doc.figures,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            document_type=parsed_doc.metadata.document_type
        )
        notify("chunk_generation", 1, 1)

        # === 11. ATUALIZAR PROCESSING INFO ===
        processing_time = time.time() - start_time
        parsed_doc.processing = ProcessingInfo(
            pipeline_version="3.0.0",
            processing_time_seconds=processing_time,
            tokens_used=total_tokens,
            vision_calls=vision_calls,
            schema_inference_used=config.enable_schema_inference,
            confidence_overall=_calculate_overall_confidence(parsed_doc),
            confidence_schema=schema_confidence,
            warnings=warnings
        )

        # === 12. GERAÇÃO DE OUTPUTS ===
        notify("generation", 0, 2)

        # Markdown
        markdown = ""
        markdown_path = None
        if config.generate_markdown:
            markdown = generate_markdown(
                parsed_doc,
                include_frontmatter=config.include_frontmatter,
                include_toc=config.include_toc,
                assets_path="assets"
            )
            markdown_path = output_dir / f"{file_path.stem}.md"
            markdown_path.write_text(markdown, encoding="utf-8")

        notify("generation", 1, 2)

        # JSON (híbrido)
        json_data = {}
        json_path = None
        if config.generate_json:
            json_data = generate_json(
                parsed_doc,
                include_chunks=config.include_chunks,
                include_raw_text=config.include_raw_text,
                include_structured_data=config.enable_schema_inference,
                pretty_print=config.pretty_print
            )
            json_path = output_dir / f"{file_path.stem}.json"
            json_path.write_text(
                json.dumps(json_data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

        notify("generation", 2, 2)

        return ConversionOutput(
            markdown=markdown,
            json_data=json_data,
            markdown_path=str(markdown_path) if markdown_path else None,
            json_path=str(json_path) if json_path else None,
            assets_dir=str(assets_dir),
            parsed_document=parsed_doc,
            success=True,
            errors=errors,
            warnings=warnings
        )

    except Exception as e:
        logger.exception(f"Conversion failed: {e}")
        errors.append(str(e))
        return _error_output(errors)


def _error_output(errors: list) -> ConversionOutput:
    """Cria output de erro."""
    return ConversionOutput(
        markdown="",
        json_data={},
        success=False,
        errors=errors
    )


def _calculate_overall_confidence(doc: ParsedDocument) -> float:
    """Calcula confiança geral baseada em múltiplos fatores."""
    scores = []

    # Confiança do schema
    if doc.structured_data:
        scores.append(doc.structured_data.confidence)

    # Confiança baseada em cobertura de texto
    if doc.raw_text_by_page:
        text_lengths = [len(t) for t in doc.raw_text_by_page.values()]
        if text_lengths:
            avg_length = sum(text_lengths) / len(text_lengths)
            # Páginas com >500 chars = alta confiança
            text_confidence = min(avg_length / 500, 1.0)
            scores.append(text_confidence)

    # Confiança baseada em estrutura
    if doc.sections:
        # Documento com seções bem definidas = maior confiança
        scores.append(0.9)
    else:
        scores.append(0.5)

    return sum(scores) / len(scores) if scores else 0.5


# Exports
__all__ = [
    "convert_document",
    "ConversionConfig",
    "ConversionOutput",
    "ParsedDocument",
    "InferredSchema",
    "detect_document",
    "extract_text",
    "analyze_structure",
    "generate_markdown",
    "generate_json",
]
