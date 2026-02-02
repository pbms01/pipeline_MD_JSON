"""
schema_inferrer.py - Infere estrutura semântica do documento usando Schema de Análise Estruturada.

Este módulo implementa inferência de schema seguindo uma arquitetura padronizada
para extração, estruturação e análise de informações documentais.

Schema estruturado:
- metadata: Metadados do documento
- entities: Atores, documentos, ativos, eventos, relacionamentos
- evidence: Elementos probatórios
- analysis: Achados, problemas, recomendações
- timeline: Linha do tempo consolidada
- synthesis: Síntese conclusiva
"""
import json
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
from datetime import date
import uuid
import re

# Carregar variáveis de ambiente
from dotenv import load_dotenv

# Tentar carregar .env do diretório do projeto
_project_root = Path(__file__).parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
else:
    load_dotenv()  # Fallback para busca padrão

# Verificar se a API key está disponível
_api_key = os.getenv("ANTHROPIC_API_KEY")
if not _api_key:
    logging.warning("ANTHROPIC_API_KEY not found in environment. Schema inference will fail.")

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from .models import InferredSchema
from config.settings import CLAUDE_MODEL, PROMPTS_DIR

logger = logging.getLogger(__name__)


# === STRUCTURED ANALYSIS PROMPT ===

STRUCTURED_ANALYSIS_PROMPT = """Você é um especialista em análise documental estruturada. Analise o documento fornecido e extraia informações seguindo rigorosamente o schema JSON abaixo.

## Estrutura de Saída Obrigatória

```json
{
  "metadata": {
    "id": "doc-[uuid-curto]",
    "title": "string - título descritivo",
    "documentType": "string - tipo (ver lista abaixo)",
    "analysisDate": "YYYY-MM-DD",
    "version": 1,
    "status": "draft",
    "confidentiality": "internal",
    "tags": ["string"],
    "notes": "string | null"
  },
  "entities": {
    "actors": [
      {
        "id": "actor-[nome-slug]",
        "type": "person | organization | government_body",
        "name": "string - nome completo",
        "shortName": "string | null",
        "identifiers": {
          "cpf": "string | null",
          "cnpj": "string | null",
          "rg": "string | null",
          "oab": "string | null"
        },
        "role": "string - função/cargo",
        "category": "string - categoria funcional",
        "contact": {
          "email": "string | null",
          "phone": "string | null",
          "address": "string | null"
        },
        "notes": "string | null"
      }
    ],
    "documents": [
      {
        "id": "doc-[tipo]-[ref]",
        "name": "string - título do documento",
        "type": "string - tipo documental",
        "reference": "string | null - número/protocolo",
        "date": "YYYY-MM-DD | null",
        "author": "actor-id | null",
        "summary": "string | null",
        "relatedActors": ["actor-id"],
        "tags": ["string"]
      }
    ],
    "assets": [
      {
        "id": "asset-[tipo]-[seq]",
        "type": "string - tipo do ativo",
        "description": "string",
        "value": {
          "amount": "number | null",
          "currency": "BRL | USD | null",
          "valuationType": "mercado | contabil | declarado | null"
        },
        "ownership": {
          "owner": "actor-id | null"
        },
        "location": "string | null",
        "status": "string | null"
      }
    ],
    "events": [
      {
        "id": "event-[YYYY-MM-DD]-[desc]",
        "date": "YYYY-MM-DD",
        "time": "HH:MM | null",
        "type": "string - tipo do evento",
        "description": "string",
        "location": "string | null",
        "involvedActors": ["actor-id"],
        "involvedAssets": ["asset-id"],
        "outcome": "string | null"
      }
    ],
    "relationships": [
      {
        "id": "rel-[source]-[target]",
        "type": "string - tipo de relacionamento",
        "sourceId": "string - ID origem",
        "sourceType": "actor | document | asset | event",
        "targetId": "string - ID destino",
        "targetType": "actor | document | asset | event",
        "strength": "confirmed | probable | possible | alleged",
        "evidence": ["string - descrição da evidência"]
      }
    ]
  },
  "evidence": {
    "documentary": [
      {
        "id": "evid-doc-[seq]",
        "type": "string",
        "description": "string",
        "sourceDocument": "doc-id | null",
        "pageReference": "string | null",
        "relevance": "high | medium | low",
        "supportsClaims": ["finding-id"]
      }
    ],
    "testimonial": [],
    "technical": [],
    "digital": []
  },
  "analysis": {
    "findings": [
      {
        "id": "finding-[desc]",
        "category": "fato_confirmado | fato_provavel | irregularidade | conformidade | ...",
        "title": "string - título conciso",
        "description": "string - descrição detalhada",
        "significance": "string - relevância/impacto",
        "confidence": "high | medium | low",
        "supportingEvidence": ["evid-id"],
        "relatedEntities": ["entity-id"]
      }
    ],
    "issues": [
      {
        "id": "issue-[desc]",
        "category": "documento_ausente | informacao_conflitante | ...",
        "description": "string",
        "severity": "critical | major | moderate | minor",
        "status": "open | resolved"
      }
    ],
    "recommendations": [
      {
        "id": "rec-[desc]",
        "type": "diligencia | requisicao | monitoramento | ...",
        "title": "string",
        "description": "string",
        "priority": "critical | high | medium | low",
        "relatedFindings": ["finding-id"]
      }
    ]
  },
  "timeline": [
    {
      "date": "YYYY-MM-DD",
      "entries": [
        {
          "id": "tl-[YYYY-MM-DD]-[seq]",
          "time": "HH:MM | null",
          "type": "string",
          "description": "string",
          "actors": ["actor-id"],
          "significance": "high | medium | low"
        }
      ]
    }
  ],
  "synthesis": {
    "executiveSummary": "string - resumo executivo em 2-3 parágrafos",
    "keyPoints": [
      {
        "point": "string - ponto principal",
        "supportingFindings": ["finding-id"]
      }
    ],
    "conclusions": [
      {
        "id": "conclusion-[seq]",
        "statement": "string - afirmação conclusiva",
        "confidence": "high | medium | low",
        "caveats": ["string - ressalvas"]
      }
    ],
    "openQuestions": [
      {
        "question": "string - questão pendente",
        "relevance": "string - por que importa"
      }
    ],
    "nextSteps": [
      {
        "step": "string - próximo passo",
        "priority": "critical | high | medium | low"
      }
    ]
  }
}
```

## Tipos de Documento (documentType)
- Jurídico: processo_judicial, processo_administrativo, inquerito, denuncia, sentenca, acordao, parecer, contrato, procuracao
- Corporativo: relatorio_financeiro, auditoria, compliance, ata_reuniao, estatuto_social, balanco
- Técnico: laudo_pericial, relatorio_tecnico, parecer_tecnico, vistoria, avaliacao
- Administrativo: edital, licitacao, convenio, termo_referencia, prestacao_contas
- Acadêmico: artigo, tese, relatorio_pesquisa
- Genérico: documento_geral, correspondencia, memorial, proposta

## Categorias de Atores
- Público: servidor_publico, magistrado, promotor, procurador, delegado, policial, gestor_publico
- Privado: empresario, executivo, socio, funcionario, advogado, contador, auditor
- Outros: particular, testemunha, vitima, beneficiario, representante

## Tipos de Relacionamento
- Pessoais: emprego, sociedade, representacao, subordinacao, parentesco
- Negociais: contratual, fornecimento, cliente, parceria
- Financeiros: pagamento, recebimento, emprestimo, investimento
- Propriedade: propriedade, posse, uso, custodia

## Regras de Preenchimento
1. IDs únicos com prefixos semânticos (actor-, doc-, event-, finding-, etc.)
2. Datas sempre em YYYY-MM-DD
3. Use null para campos não encontrados
4. Confidence: high=evidência direta, medium=indícios, low=hipótese
5. Timeline DEVE conter todos os eventos em ordem cronológica
6. Synthesis SEMPRE com executiveSummary e pelo menos uma conclusion

## Documento para Análise

{document_text}

Retorne APENAS o JSON válido, sem explicações adicionais.
"""


class SchemaInferrer:
    """
    Infere schema estruturado do documento via LLM.

    Implementa o Schema de Análise Documental Estruturada com:
    - metadata: Informações do documento
    - entities: Atores, documentos, ativos, eventos, relacionamentos
    - evidence: Elementos probatórios
    - analysis: Achados, problemas, recomendações
    - timeline: Cronologia consolidada
    - synthesis: Síntese conclusiva
    """

    def __init__(
        self,
        model: str = CLAUDE_MODEL,
        include_explanations: bool = False
    ):
        if not HAS_ANTHROPIC:
            raise ImportError("anthropic é necessário para inferência de schema")

        # Passar API key explicitamente
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.include_explanations = include_explanations
        self._load_prompts()

    def _load_prompts(self):
        """Carrega prompts customizados se existirem."""
        prompt_path = PROMPTS_DIR / "structured_analysis_schema.md"
        if prompt_path.exists():
            content = prompt_path.read_text(encoding="utf-8")
            # Extrair apenas a parte após "## Documento para Análise" se existir
            if "{document_text}" in content:
                self.inference_prompt = content
            else:
                self.inference_prompt = STRUCTURED_ANALYSIS_PROMPT
        else:
            self.inference_prompt = STRUCTURED_ANALYSIS_PROMPT

    def infer_schema(
        self,
        document_text: str,
        document_type: Optional[str] = None,
        max_chars: int = 30000,
        source_filename: Optional[str] = None
    ) -> InferredSchema:
        """
        Infere schema estruturado completo do documento.

        Args:
            document_text: Texto completo do documento
            document_type: Tipo pré-detectado (opcional)
            max_chars: Máximo de caracteres para enviar ao LLM
            source_filename: Nome do arquivo fonte

        Returns:
            InferredSchema com estrutura completa de análise documental
        """
        try:
            # Truncar se necessário
            text_to_analyze = document_text[:max_chars]
            if len(document_text) > max_chars:
                text_to_analyze += "\n\n[... documento truncado para análise ...]"

            # Chamar LLM
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,  # Aumentado para schema completo
                messages=[{
                    "role": "user",
                    "content": self.inference_prompt.replace("{document_text}", text_to_analyze)
                }]
            )

            # Parsear resposta
            raw_response = response.content[0].text
            logger.info(f"[TRACE] Got LLM response, length: {len(raw_response)}")

            result = self._parse_json_response(raw_response)
            logger.info(f"[TRACE] _parse_json_response returned type: {type(result).__name__}")

            # Verificar se result é um dicionário válido
            if not isinstance(result, dict):
                logger.error(f"_parse_json_response returned non-dict: {type(result)}")
                return self._create_error_schema(
                    f"Invalid response type: {type(result)}",
                    document_type
                )

            # Log das chaves do resultado
            try:
                keys = list(result.keys())
                logger.info(f"[TRACE] Result has {len(keys)} keys: {keys[:5]}...")
            except Exception as e:
                logger.error(f"[TRACE] Error listing result keys: {e}")

            # Verificar se houve erro no parsing usando try-except completo
            has_error = False
            error_msg = None
            raw_text = None
            try:
                has_error = "_error" in result
                if has_error:
                    error_msg = result.get("_error", "Unknown error")
                    raw_text = result.get("_raw_text")
            except Exception as e:
                logger.error(f"Error checking for _error key: {e}")

            if has_error:
                logger.warning(f"Schema inference returned error: {error_msg}")
                return self._create_error_schema(error_msg, document_type, raw_text)

            logger.info(f"[TRACE] About to call _validate_and_complete_schema")

            # Validar e completar estrutura
            result = self._validate_and_complete_schema(result, source_filename)

            logger.info(f"[TRACE] _validate_and_complete_schema returned successfully")

            # Extrair tipo de documento e confiança
            doc_type = self._extract_document_type(result, document_type)
            confidence = self._calculate_confidence(result)

            return InferredSchema(
                schema_inferred=True,
                document_type=doc_type,
                confidence=confidence,
                fields=result,
                inference_model=self.model,
                schema_version="2.0"
            )

        except Exception as e:
            import traceback
            logger.error(f"Unexpected error in infer_schema: {type(e).__name__}: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return self._create_error_schema(
                f"{type(e).__name__}: {str(e)}",
                document_type
            )

    def _create_error_schema(
        self,
        error_message: str,
        document_type: Optional[str] = None,
        raw_text: Optional[str] = None
    ) -> InferredSchema:
        """Cria schema com erro."""
        error_fields = {"_error": error_message}
        if raw_text:
            error_fields["_raw_text"] = raw_text[:500]

        return InferredSchema(
            schema_inferred=False,
            document_type=document_type or "unknown",
            confidence=0.0,
            fields=error_fields,
            inference_model=self.model,
            schema_version="2.0"
        )

    def _validate_and_complete_schema(
        self,
        result: Dict[str, Any],
        source_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Valida e completa o schema com valores padrão."""

        # Criar estrutura limpa do zero e copiar dados válidos
        clean_schema = {
            "metadata": {},
            "entities": {
                "actors": [],
                "documents": [],
                "assets": [],
                "events": [],
                "relationships": []
            },
            "evidence": {
                "documentary": [],
                "testimonial": [],
                "technical": [],
                "digital": []
            },
            "analysis": {
                "findings": [],
                "issues": [],
                "recommendations": []
            },
            "timeline": [],
            "synthesis": {
                "executiveSummary": "",
                "keyPoints": [],
                "conclusions": [],
                "openQuestions": [],
                "nextSteps": []
            }
        }

        # Função auxiliar para obter valor de forma segura
        def safe_get(d, key, default=None):
            """Obtém valor de dict de forma segura, ignorando chaves malformadas."""
            if not isinstance(d, dict):
                return default

            # Usar get() que é mais seguro que 'in' + acesso
            try:
                val = d.get(key)
                if val is not None:
                    return val
            except Exception:
                pass

            # Fallback: iterar pelas chaves buscando match
            try:
                for k in list(d.keys()):
                    try:
                        if k == key:
                            return d.get(k, default)
                        if isinstance(k, str):
                            clean_k = k.strip().strip('"').strip("'").strip()
                            if clean_k == key:
                                return d.get(k, default)
                    except Exception:
                        continue
            except Exception:
                pass

            return default

        # Copiar metadata
        src_metadata = safe_get(result, "metadata", {})
        if isinstance(src_metadata, dict):
            for field in ["id", "title", "documentType", "analysisDate", "version",
                          "status", "confidentiality", "tags", "notes", "sourceFiles"]:
                val = safe_get(src_metadata, field)
                if val is not None:
                    clean_schema["metadata"][field] = val

        # Copiar entities
        src_entities = safe_get(result, "entities", {})
        if isinstance(src_entities, dict):
            for entity_type in ["actors", "documents", "assets", "events", "relationships"]:
                val = safe_get(src_entities, entity_type, [])
                if isinstance(val, list):
                    clean_schema["entities"][entity_type] = val

        # Copiar evidence
        src_evidence = safe_get(result, "evidence", {})
        if isinstance(src_evidence, dict):
            for ev_type in ["documentary", "testimonial", "technical", "digital"]:
                val = safe_get(src_evidence, ev_type, [])
                if isinstance(val, list):
                    clean_schema["evidence"][ev_type] = val

        # Copiar analysis
        src_analysis = safe_get(result, "analysis", {})
        if isinstance(src_analysis, dict):
            for an_type in ["findings", "issues", "recommendations"]:
                val = safe_get(src_analysis, an_type, [])
                if isinstance(val, list):
                    clean_schema["analysis"][an_type] = val

        # Copiar timeline
        src_timeline = safe_get(result, "timeline", [])
        if isinstance(src_timeline, list):
            clean_schema["timeline"] = src_timeline

        # Copiar synthesis
        src_synthesis = safe_get(result, "synthesis", {})
        if isinstance(src_synthesis, dict):
            val = safe_get(src_synthesis, "executiveSummary", "")
            if isinstance(val, str):
                clean_schema["synthesis"]["executiveSummary"] = val
            for field in ["keyPoints", "conclusions", "openQuestions", "nextSteps"]:
                val = safe_get(src_synthesis, field, [])
                if isinstance(val, list):
                    clean_schema["synthesis"][field] = val

        # Usar resultado limpo
        result = clean_schema

        # Completar campos obrigatórios de metadata
        metadata = result["metadata"]
        if not metadata.get("id"):
            metadata["id"] = f"doc-{uuid.uuid4().hex[:8]}"
        if not metadata.get("analysisDate"):
            metadata["analysisDate"] = date.today().isoformat()
        if "version" not in metadata:
            metadata["version"] = 1
        if not metadata.get("status"):
            metadata["status"] = "draft"
        if not metadata.get("confidentiality"):
            metadata["confidentiality"] = "internal"
        if "tags" not in metadata:
            metadata["tags"] = []

        # Adicionar sourceFiles se fornecido
        if source_filename and "sourceFiles" not in metadata:
            metadata["sourceFiles"] = [{
                "filename": source_filename,
                "format": Path(source_filename).suffix.lstrip(".") if source_filename else "unknown"
            }]

        return result

    def _extract_document_type(
        self,
        result: Dict[str, Any],
        fallback: Optional[str] = None
    ) -> str:
        """Extrai o tipo de documento do resultado."""
        doc_type = None

        # Usar acesso seguro via get()
        try:
            metadata = result.get("metadata") if isinstance(result, dict) else None
            if isinstance(metadata, dict):
                doc_type = metadata.get("documentType")
        except Exception as e:
            logger.debug(f"Error extracting document type: {e}")

        # Fallback
        if not doc_type:
            doc_type = fallback or "documento_geral"

        return doc_type

    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        """Calcula confiança baseado na completude do schema."""
        score = 0.0
        max_score = 0.0

        if not isinstance(result, dict):
            return 0.3

        try:
            # Metadata (peso 0.1)
            max_score += 0.1
            meta = result.get("metadata")
            if isinstance(meta, dict):
                if meta.get("title") and meta.get("documentType"):
                    score += 0.1
                elif meta.get("title") or meta.get("documentType"):
                    score += 0.05

            # Entities (peso 0.3)
            max_score += 0.3
            entities = result.get("entities")
            if isinstance(entities, dict):
                # Actors
                actors = entities.get("actors")
                if isinstance(actors, list) and len(actors) > 0:
                    score += 0.1
                # Events
                events = entities.get("events")
                if isinstance(events, list) and len(events) > 0:
                    score += 0.1
                # Relationships
                rels = entities.get("relationships")
                if isinstance(rels, list) and len(rels) > 0:
                    score += 0.1

            # Analysis (peso 0.3)
            max_score += 0.3
            analysis = result.get("analysis")
            if isinstance(analysis, dict):
                findings = analysis.get("findings")
                if isinstance(findings, list) and len(findings) > 0:
                    score += 0.15
                recs = analysis.get("recommendations")
                if isinstance(recs, list) and len(recs) > 0:
                    score += 0.15

            # Synthesis (peso 0.3)
            max_score += 0.3
            synthesis = result.get("synthesis")
            if isinstance(synthesis, dict):
                if synthesis.get("executiveSummary"):
                    score += 0.15
                conclusions = synthesis.get("conclusions")
                if isinstance(conclusions, list) and len(conclusions) > 0:
                    score += 0.15

        except Exception as e:
            logger.debug(f"Error calculating confidence: {e}")
            return 0.3

        # Normalizar para 0-1
        confidence = score / max_score if max_score > 0 else 0.0

        # Mínimo de 0.3 se temos algum conteúdo válido
        if score > 0 and confidence < 0.3:
            confidence = 0.3

        return round(confidence, 2)

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Extrai JSON da resposta do LLM e retorna um dict completamente limpo."""
        logger.info(f"[TRACE] _parse_json_response started, input length: {len(text)}")
        original_text = text
        text = text.strip()

        # Remover marcadores de código (várias formas)
        code_block_pattern = r'```(?:json)?\s*\n([\s\S]*?)\n```'
        matches = re.findall(code_block_pattern, text)
        if matches:
            text = max(matches, key=len)
            logger.debug(f"Found code block, extracted {len(text)} chars")
        else:
            code_block_pattern2 = r'```(?:json)?(.*?)```'
            matches2 = re.findall(code_block_pattern2, text, re.DOTALL)
            if matches2:
                text = max(matches2, key=len)
                logger.debug(f"Found code block (pattern 2), extracted {len(text)} chars")
            else:
                if text.startswith("```json"):
                    text = text[7:]
                elif text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]

        text = text.strip()

        # Encontrar o JSON balanceado
        start = text.find("{")
        if start < 0:
            logger.warning("No JSON object found in response")
            return self._create_safe_dict({"_error": "No JSON object found", "_raw_text": original_text[:500]})

        # Encontrar o fechamento balanceado
        brace_count = 0
        end = -1
        in_string = False
        escape_next = False

        for i, char in enumerate(text[start:], start):
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break

        if end <= start:
            end = text.rfind("}") + 1
            logger.debug(f"Using rfind fallback, end={end}")

        if start >= 0 and end > start:
            json_str = text[start:end]
            logger.debug(f"Extracted JSON string of length {len(json_str)}")

            # Limpar problemas comuns
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)

            try:
                logger.info(f"[TRACE] About to call json.loads")
                parsed = json.loads(json_str)
                logger.info(f"[TRACE] json.loads succeeded, type: {type(parsed).__name__}")
                # CRÍTICO: Criar dict completamente novo e limpo
                logger.info(f"[TRACE] About to call _create_safe_dict")
                result = self._create_safe_dict(parsed)
                logger.info(f"[TRACE] _create_safe_dict returned, type: {type(result).__name__}")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error: {e}")

                # Tentar reparar JSON
                try:
                    fixed = re.sub(r"'([^']+)':", r'"\1":', json_str)
                    parsed = json.loads(fixed)
                    return self._create_safe_dict(parsed)
                except json.JSONDecodeError:
                    pass

                return self._create_safe_dict({
                    "_error": f"JSON parse error at position {e.pos}: {e.msg}",
                    "_raw_text": json_str[:500]
                })

        logger.warning("No valid JSON structure found")
        return self._create_safe_dict({"_error": "No valid JSON found", "_raw_text": original_text[:500]})

    def _create_safe_dict(self, obj: Any) -> Any:
        """Cria uma estrutura de dados completamente nova e segura."""
        if obj is None:
            return None

        if isinstance(obj, dict):
            # Criar novo dict do zero
            new_dict = {}
            try:
                # Iterar de forma segura
                items_list = []
                try:
                    items_list = list(obj.items())
                except Exception as e:
                    logger.debug(f"Error getting items: {e}")
                    return {}

                for item in items_list:
                    try:
                        key, value = item
                        # Validar e limpar a chave
                        if isinstance(key, str):
                            clean_key = key.strip()
                            # Remover caracteres problemáticos
                            if '\n' in clean_key or '\r' in clean_key:
                                # Tentar extrair a parte válida da chave
                                clean_key = clean_key.replace('\n', '').replace('\r', '').strip()
                                if clean_key.startswith('"') and clean_key.endswith('"'):
                                    clean_key = clean_key[1:-1]
                                clean_key = clean_key.strip()
                            # Só adicionar se a chave for válida
                            if clean_key and len(clean_key) < 100:
                                new_dict[clean_key] = self._create_safe_dict(value)
                        elif isinstance(key, (int, float, bool)):
                            new_dict[str(key)] = self._create_safe_dict(value)
                    except Exception as e:
                        logger.debug(f"Error processing item: {e}")
                        continue
            except Exception as e:
                logger.debug(f"Error in _create_safe_dict for dict: {e}")
                return {}
            return new_dict

        elif isinstance(obj, list):
            new_list = []
            for item in obj:
                try:
                    new_list.append(self._create_safe_dict(item))
                except Exception:
                    continue
            return new_list

        elif isinstance(obj, (str, int, float, bool)):
            return obj

        else:
            # Para outros tipos, tentar converter para string
            try:
                return str(obj)
            except Exception:
                return None

    # Manter métodos legados para compatibilidade
    def detect_document_type(
        self,
        document_text: str,
        max_preview_chars: int = 5000
    ) -> tuple:
        """Detecta rapidamente o tipo de documento (método legado)."""
        # Usar inferência completa mas extrair apenas tipo
        schema = self.infer_schema(document_text[:max_preview_chars])
        return (schema.document_type, schema.confidence)

    def infer_with_known_type(
        self,
        document_text: str,
        document_type: str,
        type_specific_prompt: Optional[str] = None
    ) -> InferredSchema:
        """Infere schema com tipo conhecido (método legado)."""
        return self.infer_schema(document_text, document_type=document_type)


# === FUNÇÕES DE CONVENIÊNCIA ===

def infer_document_schema(
    document_text: str,
    document_type: Optional[str] = None,
    include_explanations: bool = False,
    source_filename: Optional[str] = None
) -> InferredSchema:
    """
    Função de conveniência para inferir schema estruturado.

    Args:
        document_text: Texto do documento
        document_type: Tipo pré-conhecido (opcional)
        include_explanations: Incluir explicações (não usado no schema v2)
        source_filename: Nome do arquivo fonte

    Returns:
        InferredSchema com estrutura completa de análise documental
    """
    inferrer = SchemaInferrer(include_explanations=include_explanations)
    return inferrer.infer_schema(
        document_text,
        document_type=document_type,
        source_filename=source_filename
    )


def detect_and_infer(
    document_text: str,
    include_explanations: bool = False
) -> InferredSchema:
    """
    Detecta tipo e infere schema em uma única chamada.

    Com o schema v2, detecção e inferência são feitas juntas.
    """
    return infer_document_schema(document_text, include_explanations=include_explanations)
