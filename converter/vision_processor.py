"""
vision_processor.py - Processamento visual via Claude Vision.

Este módulo usa Claude Vision para processar elementos complexos
que não podem ser bem extraídos via texto:
- Tabelas complexas
- Figuras e diagramas
- Equações
- Páginas escaneadas
"""
import base64
import time
from typing import List, Optional, Dict, Any
import logging
import json
import re

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from .models import (
    VisionResult, RoutingPlan, Table, Figure, Equation,
    TableColumn, ProcessingMethod
)
from config.settings import (
    CLAUDE_VISION_MODEL, CLAUDE_MAX_TOKENS,
    VISION_MAX_RETRIES, VISION_RETRY_DELAY, VISION_TIMEOUT
)

logger = logging.getLogger(__name__)


# === PROMPTS ===

PAGE_VISION_PROMPT = """Analise esta página de documento e extraia todo o conteúdo de forma estruturada.

## Instruções

1. **Texto**: Extraia todo o texto preservando a hierarquia (títulos, parágrafos, listas).

2. **Tabelas**: Para cada tabela:
   - Identifique cabeçalhos e dados
   - Preserve a estrutura de linhas e colunas
   - Note se há células mescladas
   - Retorne em formato markdown

3. **Figuras**: Para cada figura/imagem:
   - Descreva o conteúdo detalhadamente
   - Identifique legendas se presentes
   - Classifique o tipo (gráfico, diagrama, foto, etc.)

4. **Equações**: Transcreva equações em LaTeX.

## Formato de Resposta

Retorne JSON no seguinte formato:

```json
{
  "content": "Texto completo da página em markdown",
  "tables": [
    {
      "title": "Título da tabela ou null",
      "headers": ["Col1", "Col2"],
      "data": [["val1", "val2"]],
      "has_merged_cells": false,
      "markdown": "| Col1 | Col2 |\\n|---|---|\\n| val1 | val2 |"
    }
  ],
  "figures": [
    {
      "title": "Título ou null",
      "caption": "Legenda ou null",
      "description": "Descrição detalhada do conteúdo",
      "type": "chart|diagram|photo|screenshot|other"
    }
  ],
  "equations": [
    {
      "latex": "E = mc^2",
      "label": "eq1 ou null",
      "is_inline": false
    }
  ]
}
```

Página {page_number} de {total_pages}:"""


TABLE_VISION_PROMPT = """Extraia esta tabela de forma estruturada.

## Instruções

1. Identifique todas as linhas de cabeçalho
2. Extraia todas as células de dados
3. Note células mescladas (spanning multiple rows/columns)
4. Identifique o tipo de dados em cada coluna

## Formato de Resposta

```json
{
  "title": "Título da tabela ou null",
  "headers": ["Coluna 1", "Coluna 2", "Coluna 3"],
  "column_types": ["text", "number", "date"],
  "data": [
    ["valor1", "valor2", "valor3"],
    ["valor4", "valor5", "valor6"]
  ],
  "has_merged_cells": false,
  "notes": "Observações sobre a tabela"
}
```"""


FIGURE_VISION_PROMPT = """Descreva esta figura/imagem detalhadamente.

## Instruções

1. Descreva o conteúdo visual em detalhes
2. Identifique texto, legendas ou anotações
3. Classifique o tipo de figura
4. Extraia dados se for um gráfico

## Formato de Resposta

```json
{
  "title": "Título identificado ou null",
  "caption": "Legenda identificada ou null",
  "description": "Descrição detalhada do conteúdo visual",
  "type": "chart|diagram|photo|screenshot|illustration|other",
  "alt_text": "Texto alternativo conciso para acessibilidade",
  "extracted_data": null
}
```

Se for um gráfico com dados visíveis, inclua em extracted_data:
```json
"extracted_data": {
  "chart_type": "bar|line|pie|scatter|other",
  "data_points": [{"label": "A", "value": 10}]
}
```"""


class VisionProcessor:
    """Processa documentos usando Claude Vision."""

    def __init__(
        self,
        model: str = CLAUDE_VISION_MODEL,
        max_tokens: int = CLAUDE_MAX_TOKENS,
        max_retries: int = VISION_MAX_RETRIES,
        retry_delay: float = VISION_RETRY_DELAY
    ):
        if not HAS_ANTHROPIC:
            raise ImportError("anthropic é necessário para processamento visual")

        self.client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def process_page(
        self,
        image_bytes: bytes,
        page_number: int,
        total_pages: int,
        routing_plan: Optional[RoutingPlan] = None
    ) -> VisionResult:
        """
        Processa uma página inteira via visão.

        Args:
            image_bytes: Bytes da imagem PNG
            page_number: Número da página
            total_pages: Total de páginas
            routing_plan: Plano de roteamento (opcional)

        Returns:
            VisionResult
        """
        start_time = time.time()

        prompt = PAGE_VISION_PROMPT.format(
            page_number=page_number,
            total_pages=total_pages
        )

        response = self._call_vision_api(image_bytes, prompt)
        processing_time = time.time() - start_time

        # Parse response
        result = self._parse_page_response(response, page_number)
        result.processing_time = processing_time

        return result

    def process_table(
        self,
        image_bytes: bytes,
        page_number: int
    ) -> Table:
        """
        Processa uma tabela específica via visão.

        Args:
            image_bytes: Bytes da imagem da tabela
            page_number: Número da página

        Returns:
            Table extraída
        """
        response = self._call_vision_api(image_bytes, TABLE_VISION_PROMPT)
        return self._parse_table_response(response, page_number)

    def process_figure(
        self,
        image_bytes: bytes,
        page_number: int
    ) -> Figure:
        """
        Processa uma figura específica via visão.

        Args:
            image_bytes: Bytes da imagem
            page_number: Número da página

        Returns:
            Figure com descrição
        """
        response = self._call_vision_api(image_bytes, FIGURE_VISION_PROMPT)
        return self._parse_figure_response(response, page_number)

    def _call_vision_api(self, image_bytes: bytes, prompt: str) -> Dict[str, Any]:
        """Chama API de visão com retry."""
        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        for attempt in range(self.max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_b64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }]
                )

                # Extrair texto da resposta
                text = response.content[0].text
                tokens_used = response.usage.input_tokens + response.usage.output_tokens

                # Parse JSON
                parsed = self._parse_json_response(text)
                parsed["_tokens_used"] = tokens_used

                return parsed

            except anthropic.RateLimitError:
                logger.warning(f"Rate limit hit, tentativa {attempt + 1}/{self.max_retries}")
                time.sleep(self.retry_delay * (attempt + 1))

            except anthropic.APIError as e:
                logger.error(f"API error: {e}")
                if attempt == self.max_retries - 1:
                    raise

        return {"_error": "Max retries exceeded", "_tokens_used": 0}

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Extrai JSON da resposta do modelo."""
        text = text.strip()

        # Remover marcadores de código
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        # Encontrar JSON
        start = text.find("{")
        end = text.rfind("}") + 1

        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error: {e}")
                return {"_raw_text": text[:1000], "_parse_error": str(e)}

        return {"_raw_text": text[:1000]}

    def _parse_page_response(self, response: Dict[str, Any], page_number: int) -> VisionResult:
        """Parse resposta de página completa."""
        content = response.get("content", "")
        tokens_used = response.get("_tokens_used", 0)

        # Parse tabelas
        tables = []
        for idx, t in enumerate(response.get("tables", [])):
            table = Table(
                id=f"table_v_{page_number}_{idx}",
                element_type="table",
                page=page_number,
                title=t.get("title"),
                columns=[TableColumn(name=h) for h in t.get("headers", [])],
                data=t.get("data", []),
                has_merged_cells=t.get("has_merged_cells", False),
                markdown=t.get("markdown"),
                confidence=0.9,
                processing_method=ProcessingMethod.VISION_LLM
            )
            tables.append(table)

        # Parse figuras
        figures = []
        for idx, f in enumerate(response.get("figures", [])):
            figure = Figure(
                id=f"fig_v_{page_number}_{idx}",
                element_type="figure",
                page=page_number,
                title=f.get("title"),
                caption=f.get("caption"),
                alt_text=f.get("description") or f.get("alt_text"),
                figure_type=f.get("type", "other"),
                confidence=0.85,
                processing_method=ProcessingMethod.VISION_LLM
            )
            figures.append(figure)

        # Parse equações
        equations = []
        for idx, eq in enumerate(response.get("equations", [])):
            equation = Equation(
                id=f"eq_v_{page_number}_{idx}",
                element_type="equation",
                page=page_number,
                latex=eq.get("latex", ""),
                label=eq.get("label"),
                is_inline=eq.get("is_inline", False),
                confidence=0.9,
                processing_method=ProcessingMethod.VISION_LLM
            )
            equations.append(equation)

        return VisionResult(
            page_number=page_number,
            content=content,
            tables=tables,
            figures=figures,
            equations=equations,
            tokens_used=tokens_used,
            confidence=0.9
        )

    def _parse_table_response(self, response: Dict[str, Any], page_number: int) -> Table:
        """Parse resposta de tabela."""
        headers = response.get("headers", [])
        column_types = response.get("column_types", ["text"] * len(headers))

        columns = [
            TableColumn(name=h, col_type=t)
            for h, t in zip(headers, column_types)
        ]

        return Table(
            id=f"table_vision_{page_number}",
            element_type="table",
            page=page_number,
            title=response.get("title"),
            columns=columns,
            data=response.get("data", []),
            has_merged_cells=response.get("has_merged_cells", False),
            confidence=0.9,
            processing_method=ProcessingMethod.VISION_LLM
        )

    def _parse_figure_response(self, response: Dict[str, Any], page_number: int) -> Figure:
        """Parse resposta de figura."""
        return Figure(
            id=f"fig_vision_{page_number}",
            element_type="figure",
            page=page_number,
            title=response.get("title"),
            caption=response.get("caption"),
            alt_text=response.get("alt_text") or response.get("description"),
            figure_type=response.get("type", "other"),
            confidence=0.85,
            processing_method=ProcessingMethod.VISION_LLM
        )


def process_page_vision(
    image_bytes: bytes,
    page_number: int,
    total_pages: int
) -> VisionResult:
    """Função de conveniência para processar página."""
    processor = VisionProcessor()
    return processor.process_page(image_bytes, page_number, total_pages)
