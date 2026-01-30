"""
schema_inferrer.py - Infere estrutura semântica específica do documento via LLM.

Este módulo é o coração da "camada dinâmica" do sistema híbrido.
Ele analisa o documento e infere quais campos são relevantes para
aquele tipo específico de documento.
"""
import json
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import logging
import time

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from .models import InferredSchema
from config.settings import CLAUDE_MODEL, PROMPTS_DIR

logger = logging.getLogger(__name__)


# === PROMPTS ===

SCHEMA_INFERENCE_PROMPT = """
Você é um especialista em análise documental. Sua tarefa é analisar o documento fornecido e extrair sua estrutura semântica específica.

## Objetivo
1. Identificar o TIPO de documento
2. Determinar os CAMPOS relevantes para este tipo específico
3. Extrair os VALORES para cada campo
4. Explicar brevemente por que cada campo é relevante

## Tipos de Documento Conhecidos
- contrato: Acordos legais entre partes
- laudo_tecnico: Avaliações técnicas, perícias, vistorias
- relatorio: Relatórios de atividades, resultados, análises
- manual: Manuais de operação, instruções, procedimentos
- artigo: Artigos científicos, acadêmicos, técnicos
- ata: Atas de reunião, assembleias
- parecer: Pareceres jurídicos, técnicos
- proposta: Propostas comerciais, técnicas
- norma: Normas, regulamentos, políticas
- outro: Outros tipos não listados

## Regras de Extração

### Nomenclatura de Campos
- Use português brasileiro
- Use snake_case (ex: data_assinatura, valor_total)
- Seja específico mas conciso

### Estrutura de Campos
- Campos simples: strings, números, datas
- Campos compostos: objetos com subcampos
- Campos múltiplos: arrays quando houver mais de um item

### Tipos de Dados
- Texto: strings
- Números: inteiros ou decimais
- Datas: formato ISO (YYYY-MM-DD) quando possível
- Booleanos: true/false
- Listas: arrays

## Formato de Resposta

```json
{
  "_document_type": "tipo_identificado",
  "_confidence": 0.95,
  "_fields_explanation": {
    "campo1": "Por que este campo é relevante para este tipo de documento",
    "campo2": "Explicação do campo"
  },

  "campo1": "valor extraído",
  "campo2": 12345,
  "campo_composto": {
    "subcampo1": "valor",
    "subcampo2": "valor"
  },
  "campo_lista": [
    {"item": "valor1"},
    {"item": "valor2"}
  ]
}
```

## Instruções Finais
1. Analise o documento cuidadosamente
2. Identifique o tipo mais apropriado
3. Extraia TODOS os campos relevantes para este tipo
4. Não invente informações - use null se não encontrar
5. Seja preciso nos valores extraídos
6. Retorne APENAS o JSON válido, sem explicações adicionais

## Documento para Análise

{document_text}
"""


DOCUMENT_TYPE_DETECTION_PROMPT = """
Analise rapidamente este documento e identifique seu tipo.

Tipos possíveis:
- contrato
- laudo_tecnico
- relatorio
- manual
- artigo
- ata
- parecer
- proposta
- norma
- outro

Documento (primeiras páginas):
{document_preview}

Responda APENAS com um JSON:
```json
{{
  "document_type": "tipo_identificado",
  "confidence": 0.95,
  "reasoning": "breve explicação"
}}
```
"""


# === TYPE-SPECIFIC PROMPTS ===

TYPE_SPECIFIC_PROMPTS = {
    "contrato": """
Extraia os seguintes campos deste CONTRATO:

```json
{
  "_document_type": "contrato",
  "_confidence": 0.95,

  "tipo_contrato": "prestação de serviços | compra e venda | locação | outro",

  "partes": {
    "contratante": {
      "nome": "",
      "documento": "CPF ou CNPJ",
      "endereco": "",
      "representante": ""
    },
    "contratada": {
      "nome": "",
      "documento": "",
      "endereco": "",
      "representante": ""
    }
  },

  "objeto": "descrição completa do objeto",

  "valor": {
    "total": 0.00,
    "moeda": "BRL",
    "forma_pagamento": "",
    "parcelas": null
  },

  "vigencia": {
    "inicio": "YYYY-MM-DD",
    "fim": "YYYY-MM-DD",
    "renovacao_automatica": false
  },

  "clausulas_importantes": [
    {
      "numero": 1,
      "titulo": "",
      "resumo": ""
    }
  ],

  "multas_penalidades": [
    {
      "descricao": "",
      "valor_percentual": null
    }
  ],

  "foro": "",
  "data_assinatura": "YYYY-MM-DD",
  "testemunhas": []
}
```

Documento:
{document_text}

Retorne APENAS o JSON preenchido.
""",

    "laudo_tecnico": """
Extraia os seguintes campos deste LAUDO TÉCNICO:

```json
{
  "_document_type": "laudo_tecnico",
  "_confidence": 0.95,

  "tipo_laudo": "estrutural | elétrico | ambiental | avaliação | outro",

  "identificacao": {
    "numero": "",
    "data_emissao": "YYYY-MM-DD",
    "data_vistoria": "YYYY-MM-DD"
  },

  "objeto_analise": {
    "descricao": "",
    "endereco": "",
    "tipo": ""
  },

  "solicitante": {
    "nome": "",
    "documento": ""
  },

  "metodologia": {
    "tipo_vistoria": "",
    "instrumentos_utilizados": [],
    "normas_referencia": []
  },

  "constatacoes": [
    {
      "item": "",
      "local": "",
      "descricao": "",
      "gravidade": "baixa | média | alta | crítica",
      "evidencias": []
    }
  ],

  "conclusao": {
    "situacao_geral": "",
    "parecer": "",
    "urgencia": "baixa | média | alta | imediata"
  },

  "recomendacoes": [
    {
      "acao": "",
      "prazo": "",
      "prioridade": ""
    }
  ],

  "responsavel_tecnico": {
    "nome": "",
    "profissao": "",
    "registro_conselho": "",
    "numero_art_rrt": ""
  },

  "anexos_mencionados": []
}
```

Documento:
{document_text}

Retorne APENAS o JSON preenchido.
""",

    "relatorio": """
Extraia os seguintes campos deste RELATÓRIO:

```json
{
  "_document_type": "relatorio",
  "_confidence": 0.95,

  "tipo_relatorio": "atividades | resultados | progresso | análise | outro",

  "identificacao": {
    "titulo": "",
    "numero": "",
    "versao": "",
    "data": "YYYY-MM-DD"
  },

  "periodo_referencia": {
    "inicio": "YYYY-MM-DD",
    "fim": "YYYY-MM-DD"
  },

  "autor": {
    "nome": "",
    "cargo": "",
    "departamento": ""
  },

  "destinatario": "",

  "objetivo": "",

  "sumario_executivo": "",

  "metodologia": "",

  "resultados_principais": [
    {
      "item": "",
      "descricao": "",
      "dados": null
    }
  ],

  "indicadores": [
    {
      "nome": "",
      "valor_atual": null,
      "meta": null,
      "status": ""
    }
  ],

  "problemas_identificados": [],

  "conclusoes": [],

  "recomendacoes": [],

  "proximos_passos": [
    {
      "acao": "",
      "responsavel": "",
      "prazo": ""
    }
  ]
}
```

Documento:
{document_text}

Retorne APENAS o JSON preenchido.
"""
}


class SchemaInferrer:
    """
    Infere schema específico do documento via LLM.

    Este módulo:
    1. Detecta o tipo de documento
    2. Infere campos relevantes para aquele tipo
    3. Extrai valores dos campos
    4. Opcionalmente explica por que cada campo foi incluído
    """

    def __init__(
        self,
        model: str = CLAUDE_MODEL,
        include_explanations: bool = False
    ):
        if not HAS_ANTHROPIC:
            raise ImportError("anthropic é necessário para inferência de schema")

        self.client = anthropic.Anthropic()
        self.model = model
        self.include_explanations = include_explanations
        self._load_prompts()

    def _load_prompts(self):
        """Carrega prompts customizados se existirem."""
        prompt_path = PROMPTS_DIR / "schema_inference.md"
        if prompt_path.exists():
            self.inference_prompt = prompt_path.read_text(encoding="utf-8")
        else:
            self.inference_prompt = SCHEMA_INFERENCE_PROMPT

    def detect_document_type(
        self,
        document_text: str,
        max_preview_chars: int = 5000
    ) -> Tuple[str, float]:
        """
        Detecta rapidamente o tipo de documento.

        Args:
            document_text: Texto do documento
            max_preview_chars: Máximo de caracteres para análise

        Returns:
            Tupla (tipo, confiança)
        """
        preview = document_text[:max_preview_chars]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": DOCUMENT_TYPE_DETECTION_PROMPT.format(
                    document_preview=preview
                )
            }]
        )

        result = self._parse_json_response(response.content[0].text)

        return (
            result.get("document_type", "outro"),
            result.get("confidence", 0.5)
        )

    def infer_schema(
        self,
        document_text: str,
        document_type: Optional[str] = None,
        max_chars: int = 30000
    ) -> InferredSchema:
        """
        Infere schema completo do documento.

        Args:
            document_text: Texto completo do documento
            document_type: Tipo pré-detectado (opcional)
            max_chars: Máximo de caracteres para enviar ao LLM

        Returns:
            InferredSchema com campos dinâmicos
        """
        # Truncar se necessário
        text_to_analyze = document_text[:max_chars]
        if len(document_text) > max_chars:
            text_to_analyze += "\n\n[... documento truncado para análise ...]"

        # Chamar LLM
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": self.inference_prompt.format(
                    document_text=text_to_analyze
                )
            }]
        )

        # Parsear resposta
        result = self._parse_json_response(response.content[0].text)

        # Extrair meta-campos
        doc_type = result.pop("_document_type", document_type or "outro")
        confidence = result.pop("_confidence", 0.8)
        explanations = result.pop("_fields_explanation", {})

        # Remover outros meta-campos que possam ter vindo
        for key in list(result.keys()):
            if key.startswith("_"):
                result.pop(key)

        return InferredSchema(
            schema_inferred=True,
            document_type=doc_type,
            confidence=confidence,
            fields_explanation=explanations if self.include_explanations else {},
            fields=result,
            inference_model=self.model
        )

    def infer_with_known_type(
        self,
        document_text: str,
        document_type: str,
        type_specific_prompt: Optional[str] = None
    ) -> InferredSchema:
        """
        Infere schema sabendo o tipo do documento.

        Útil quando você já sabe o tipo e quer um prompt mais específico.

        Args:
            document_text: Texto do documento
            document_type: Tipo conhecido
            type_specific_prompt: Prompt customizado para o tipo

        Returns:
            InferredSchema
        """
        # Se tiver prompt específico, usar
        if type_specific_prompt:
            prompt = type_specific_prompt
        else:
            # Usar prompt padrão com hint de tipo
            prompt = self.inference_prompt.replace(
                "Identificar o TIPO de documento",
                f"O documento é do tipo '{document_type}'. Extrair campos específicos"
            )

        # Truncar documento
        max_chars = 30000
        text = document_text[:max_chars]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": prompt.format(document_text=text)
            }]
        )

        result = self._parse_json_response(response.content[0].text)

        # Forçar tipo conhecido
        result["_document_type"] = document_type

        confidence = result.pop("_confidence", 0.9)
        explanations = result.pop("_fields_explanation", {})

        for key in list(result.keys()):
            if key.startswith("_"):
                result.pop(key)

        return InferredSchema(
            schema_inferred=True,
            document_type=document_type,
            confidence=confidence,
            fields_explanation=explanations if self.include_explanations else {},
            fields=result,
            inference_model=self.model
        )

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Extrai JSON da resposta do LLM."""
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
                return {
                    "_error": f"JSON parse error: {e}",
                    "_raw_text": text[start:end][:500]
                }

        return {"_error": "No JSON found", "_raw_text": text[:500]}


def infer_document_schema(
    document_text: str,
    document_type: Optional[str] = None,
    include_explanations: bool = False
) -> InferredSchema:
    """
    Função de conveniência para inferir schema.

    Args:
        document_text: Texto do documento
        document_type: Tipo pré-conhecido (opcional)
        include_explanations: Incluir explicação de cada campo

    Returns:
        InferredSchema
    """
    inferrer = SchemaInferrer(include_explanations=include_explanations)

    if document_type and document_type in TYPE_SPECIFIC_PROMPTS:
        return inferrer.infer_with_known_type(
            document_text,
            document_type,
            TYPE_SPECIFIC_PROMPTS[document_type]
        )
    else:
        return inferrer.infer_schema(document_text, document_type)


def detect_and_infer(
    document_text: str,
    include_explanations: bool = False
) -> InferredSchema:
    """
    Detecta tipo e infere schema em duas etapas.

    Mais preciso mas usa 2 chamadas de API.
    """
    inferrer = SchemaInferrer(include_explanations=include_explanations)

    # Passo 1: Detectar tipo
    doc_type, type_confidence = inferrer.detect_document_type(document_text)

    # Passo 2: Inferir com tipo conhecido
    if doc_type in TYPE_SPECIFIC_PROMPTS:
        schema = inferrer.infer_with_known_type(
            document_text,
            doc_type,
            TYPE_SPECIFIC_PROMPTS[doc_type]
        )
    else:
        schema = inferrer.infer_schema(document_text, doc_type)

    # Atualizar confiança
    schema.confidence = min(schema.confidence, type_confidence)

    return schema
