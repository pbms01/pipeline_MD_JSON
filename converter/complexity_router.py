"""
complexity_router.py - Roteamento baseado em complexidade.

Este módulo decide quais elementos devem ser processados via:
- Extração de texto simples
- Análise estrutural
- Visão LLM (para elementos complexos)
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

from .models import (
    StructuralAnalysis, RoutingPlan, ComplexityLevel,
    Table, Figure, Equation
)
from config.settings import COMPLEX_TABLE_THRESHOLD

logger = logging.getLogger(__name__)


class ComplexityRouter:
    """Determina método de processamento por complexidade."""

    def __init__(
        self,
        prefer_vision_for_tables: bool = False,
        prefer_vision_for_equations: bool = True,
        table_complexity_threshold: float = COMPLEX_TABLE_THRESHOLD
    ):
        self.prefer_vision_for_tables = prefer_vision_for_tables
        self.prefer_vision_for_equations = prefer_vision_for_equations
        self.table_complexity_threshold = table_complexity_threshold

    def route(
        self,
        analyses: List[StructuralAnalysis],
        document_type: str = "unknown"
    ) -> List[RoutingPlan]:
        """
        Cria planos de roteamento para cada página.

        Args:
            analyses: Análises estruturais por página
            document_type: Tipo de documento (para ajustes)

        Returns:
            Lista de RoutingPlan por página
        """
        plans = []

        for analysis in analyses:
            plan = self._create_plan(analysis, document_type)
            plans.append(plan)

        return plans

    def _create_plan(
        self,
        analysis: StructuralAnalysis,
        document_type: str
    ) -> RoutingPlan:
        """Cria plano de roteamento para uma página."""
        complexity = self._assess_complexity(analysis)
        requires_vision = False
        elements_for_vision: List[str] = []
        elements_for_text: List[str] = []
        reasons: List[str] = []

        # Avaliar tabelas
        for table in analysis.tables:
            needs_vision, reason = self._table_needs_vision(table)
            if needs_vision:
                elements_for_vision.append(table.id)
                reasons.append(reason)
            else:
                elements_for_text.append(table.id)

        # Avaliar figuras (sempre precisam de visão para descrição)
        for figure in analysis.figures:
            elements_for_vision.append(figure.id)
            reasons.append("Figure requires vision for description")

        # Avaliar equações
        for equation in analysis.equations:
            if self.prefer_vision_for_equations:
                elements_for_vision.append(equation.id)
                reasons.append("Equation processing via vision")
            else:
                elements_for_text.append(equation.id)

        # Se há muitos elementos complexos, pode ser melhor processar página inteira
        total_complex = len(elements_for_vision)
        total_elements = len(analysis.all_elements)

        requires_full_page_vision = False

        # Heurísticas para visão de página completa
        if total_elements > 0:
            complex_ratio = total_complex / total_elements
            if complex_ratio > 0.5:
                requires_full_page_vision = True
                reasons.append("High ratio of complex elements")

        # PDFs escaneados sempre precisam de visão
        # (isso seria detectado antes, mas podemos verificar aqui também)

        return RoutingPlan(
            page_number=analysis.page_number,
            complexity=complexity,
            requires_full_page_vision=requires_full_page_vision,
            elements_for_vision=elements_for_vision,
            elements_for_text=elements_for_text,
            reason="; ".join(reasons) if reasons else "Standard text extraction"
        )

    def _assess_complexity(self, analysis: StructuralAnalysis) -> ComplexityLevel:
        """Avalia complexidade geral da página."""
        score = 0

        # Tabelas aumentam complexidade
        score += len(analysis.tables) * 2

        # Tabelas com células mescladas são mais complexas
        for table in analysis.tables:
            if table.has_merged_cells:
                score += 3

        # Figuras aumentam complexidade
        score += len(analysis.figures) * 2

        # Equações aumentam complexidade
        score += len(analysis.equations) * 2

        # Muitos headings podem indicar estrutura complexa
        if len(analysis.headings) > 5:
            score += 1

        if score >= 8:
            return ComplexityLevel.COMPLEX
        elif score >= 3:
            return ComplexityLevel.MODERATE
        else:
            return ComplexityLevel.SIMPLE

    def _table_needs_vision(self, table: Table) -> tuple[bool, str]:
        """Determina se tabela precisa de visão."""
        # Se preferência é sempre usar visão
        if self.prefer_vision_for_tables:
            return True, "Vision preferred for tables"

        # Tabelas com baixa confiança na extração
        if table.confidence < self.table_complexity_threshold:
            return True, f"Low extraction confidence: {table.confidence:.2f}"

        # Tabelas com células mescladas
        if table.has_merged_cells:
            return True, "Table has merged cells"

        # Tabelas muito grandes podem precisar de visão
        if table.row_count > 20 or table.col_count > 10:
            return True, f"Large table: {table.row_count}x{table.col_count}"

        return False, ""


def route_complexity(
    analyses: List[StructuralAnalysis],
    document_type: str = "unknown",
    prefer_vision_for_tables: bool = False,
    prefer_vision_for_equations: bool = True
) -> List[RoutingPlan]:
    """
    Função de conveniência para roteamento.

    Args:
        analyses: Análises estruturais
        document_type: Tipo de documento
        prefer_vision_for_tables: Preferir visão para tabelas
        prefer_vision_for_equations: Preferir visão para equações

    Returns:
        Lista de RoutingPlan
    """
    router = ComplexityRouter(
        prefer_vision_for_tables=prefer_vision_for_tables,
        prefer_vision_for_equations=prefer_vision_for_equations
    )
    return router.route(analyses, document_type)
