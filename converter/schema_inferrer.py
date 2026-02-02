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

# Log para diagnóstico
logging.info(f"[DOTENV] Project root: {_project_root}")
logging.info(f"[DOTENV] Looking for .env at: {_env_file}")
logging.info(f"[DOTENV] .env exists: {_env_file.exists()}")

if _env_file.exists():
    load_dotenv(_env_file)
    logging.info(f"[DOTENV] Loaded .env from: {_env_file}")
else:
    # Tentar busca padrão
    load_dotenv()
    logging.info("[DOTENV] Used default dotenv search")

# Verificar se a API key está disponível
_api_key = os.getenv("ANTHROPIC_API_KEY")
if _api_key:
    logging.info(f"[DOTENV] ANTHROPIC_API_KEY found (length: {len(_api_key)})")
else:
    logging.warning("ANTHROPIC_API_KEY not found in environment. Schema inference will fail.")

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from .models import InferredSchema
from .text_normalizer import normalize_text, get_reduction_stats
from config.settings import CLAUDE_MODEL, PROMPTS_DIR

logger = logging.getLogger(__name__)


# === STRUCTURED ANALYSIS PROMPT ===

STRUCTURED_ANALYSIS_PROMPT = """Analise o documento e extraia informações estruturadas em JSON.

IMPORTANTE: Seja CONCISO. Máximo 5 itens por array. Omita campos sem dados.

## Schema JSON (preencha apenas campos relevantes):

```json
{
  "metadata": {
    "id": "doc-[uuid-8chars]",
    "title": "título descritivo curto",
    "documentType": "tipo do documento",
    "date": "YYYY-MM-DD ou null",
    "parties": ["partes principais envolvidas"],
    "summary": "resumo em 1-2 frases"
  },
  "actors": [
    {"name": "nome", "role": "papel/função", "type": "person|org|gov"}
  ],
  "keyDates": [
    {"date": "YYYY-MM-DD", "event": "descrição curta"}
  ],
  "keyFacts": [
    {"fact": "fato relevante", "source": "onde no documento"}
  ],
  "values": [
    {"amount": 0, "currency": "BRL", "context": "contexto"}
  ],
  "issues": [
    {"issue": "problema/irregularidade identificada", "severity": "high|medium|low"}
  ],
  "conclusions": [
    {"conclusion": "conclusão principal", "confidence": "high|medium|low"}
  ],
  "recommendations": [
    {"action": "ação recomendada", "priority": "high|medium|low"}
  ]
}
```

## Tipos de Documento
processo_judicial, contrato, laudo_tecnico, relatorio, ata_reuniao, parecer, proposta, edital, outro

## Regras
1. MÁXIMO 5 itens por array
2. Omita seções sem dados (use arrays vazios [])
3. Foque nos elementos MAIS IMPORTANTES
4. Texto conciso e direto
5. Retorne APENAS JSON válido, sem explicações

## Documento para Análise

{document_text}
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
            # Normalizar texto para economia de tokens
            original_len = len(document_text)
            text_to_analyze = normalize_text(
                document_text,
                max_chars=max_chars,
                remove_headers_footers=True,
                compact_whitespace=True,
                remove_page_numbers=True,
                deduplicate_lines=True
            )

            # Log de estatísticas de redução
            stats = get_reduction_stats(document_text[:max_chars], text_to_analyze)
            logger.info(
                f"[NORMALIZE] Text optimization: {stats['original_chars']} -> {stats['normalized_chars']} chars "
                f"({stats['char_reduction_pct']}% reduction, ~{stats['estimated_token_savings']} tokens saved)"
            )

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
            "actors": [],
            "keyDates": [],
            "keyFacts": [],
            "values": [],
            "issues": [],
            "conclusions": [],
            "recommendations": []
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
            for field in ["id", "title", "documentType", "date", "parties", "summary"]:
                val = safe_get(src_metadata, field)
                if val is not None:
                    clean_schema["metadata"][field] = val

        # Copiar arrays do novo schema simplificado
        for array_field in ["actors", "keyDates", "keyFacts", "values", "issues", "conclusions", "recommendations"]:
            val = safe_get(result, array_field, [])
            if isinstance(val, list):
                clean_schema[array_field] = val[:5]  # Limitar a 5 itens

        # Usar resultado limpo
        result = clean_schema

        # Completar campos obrigatórios de metadata
        metadata = result["metadata"]
        if not metadata.get("id"):
            metadata["id"] = f"doc-{uuid.uuid4().hex[:8]}"
        if not metadata.get("date"):
            metadata["date"] = date.today().isoformat()

        # Adicionar source se fornecido
        if source_filename:
            metadata["source"] = source_filename

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
        if not isinstance(result, dict):
            return 0.3

        score = 0.0
        max_score = 5.0  # 5 categorias possíveis

        try:
            # Metadata (tem título e tipo?)
            meta = result.get("metadata", {})
            if meta.get("title") and meta.get("documentType"):
                score += 1.0
            elif meta.get("title") or meta.get("documentType"):
                score += 0.5

            # Actors
            actors = result.get("actors", [])
            if isinstance(actors, list) and len(actors) > 0:
                score += 1.0

            # Key Facts
            facts = result.get("keyFacts", [])
            if isinstance(facts, list) and len(facts) > 0:
                score += 1.0

            # Conclusions
            conclusions = result.get("conclusions", [])
            if isinstance(conclusions, list) and len(conclusions) > 0:
                score += 1.0

            # Issues ou Recommendations
            issues = result.get("issues", [])
            recs = result.get("recommendations", [])
            if (isinstance(issues, list) and len(issues) > 0) or \
               (isinstance(recs, list) and len(recs) > 0):
                score += 1.0

        except Exception as e:
            logger.debug(f"Error calculating confidence: {e}")
            return 0.3

        confidence = score / max_score
        return round(max(confidence, 0.3), 2)

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
                logger.warning(f"JSON parse error at position {e.pos}: {e.msg}")
                logger.info(f"[TRACE] Attempting JSON recovery strategies...")

                # Estratégia 1: Truncar progressivamente até encontrar JSON válido
                recovered = self._try_recover_json(json_str, e.pos)
                if recovered:
                    logger.info(f"[TRACE] JSON recovery succeeded!")
                    return recovered

                # Se nenhuma estratégia funcionou
                logger.warning(f"[TRACE] All JSON recovery strategies failed")
                return self._create_safe_dict({
                    "_error": f"JSON parse error at position {e.pos}: {e.msg}",
                    "_raw_text": json_str[:500]
                })

        logger.warning("No valid JSON structure found")
        return self._create_safe_dict({"_error": "No valid JSON found", "_raw_text": original_text[:500]})

    def _try_recover_json(self, json_str: str, error_pos: int) -> Optional[Dict[str, Any]]:
        """Tenta recuperar um JSON válido de uma string com erros."""
        logger.info(f"[RECOVERY] Starting recovery, error at position {error_pos}, total length {len(json_str)}")

        # Estratégia 1: Encontrar último objeto/array completo antes do erro
        logger.info("[RECOVERY] Strategy 1: Finding last complete structure")

        # Procurar por padrões de fechamento válidos antes do erro
        # Padrões: }, ], "valor" seguido de } ou ]
        search_start = max(0, error_pos - 5000)
        search_text = json_str[search_start:error_pos]

        # Encontrar todas as posições de fechamento de objetos/arrays
        close_positions = []
        for i, char in enumerate(search_text):
            if char in '}]':
                close_positions.append(search_start + i)

        # Tentar do mais próximo do erro para trás
        for close_pos in reversed(close_positions[-50:]):  # Últimas 50 posições
            candidate = json_str[:close_pos + 1]

            # Contar estruturas abertas (considerando strings)
            open_braces, open_brackets = self._count_open_structures(candidate)

            if open_braces >= 0 and open_brackets >= 0:
                # Fechar estruturas abertas
                closing = ']' * open_brackets + '}' * open_braces
                test_json = candidate + closing

                try:
                    parsed = json.loads(test_json)
                    logger.info(f"[RECOVERY] Strategy 1 success at position {close_pos}")
                    return self._create_safe_dict(parsed)
                except json.JSONDecodeError:
                    continue

        # Estratégia 2: Truncar no último } ou ] válido e fechar estruturas
        logger.info("[RECOVERY] Strategy 2: Progressive truncation with structure closing")

        # Tentar posições progressivamente menores
        for target_pos in range(error_pos - 100, max(1000, error_pos - 10000), -100):
            candidate = json_str[:target_pos]

            # Encontrar o último fechamento válido
            last_close = max(candidate.rfind('}'), candidate.rfind(']'))
            if last_close > 0:
                candidate = candidate[:last_close + 1]

                open_braces, open_brackets = self._count_open_structures(candidate)

                if open_braces >= 0 and open_brackets >= 0:
                    closing = ']' * open_brackets + '}' * open_braces
                    test_json = candidate + closing

                    try:
                        parsed = json.loads(test_json)
                        logger.info(f"[RECOVERY] Strategy 2 success at position {last_close}")
                        return self._create_safe_dict(parsed)
                    except json.JSONDecodeError:
                        continue

        # Estratégia 3: Extrair seções individuais com regex melhorado
        logger.info("[RECOVERY] Strategy 3: Extracting individual sections")
        sections = self._extract_sections_regex(json_str)
        if sections:
            logger.info(f"[RECOVERY] Strategy 3 extracted {len(sections)} sections: {list(sections.keys())}")
            return self._create_safe_dict(sections)

        # Estratégia 4: Remover linhas do final progressivamente
        logger.info("[RECOVERY] Strategy 4: Removing lines from end")
        lines = json_str.split('\n')

        for remove_count in range(1, min(200, len(lines) - 10)):
            partial = '\n'.join(lines[:-remove_count])

            # Encontrar último fechamento
            last_close = max(partial.rfind('}'), partial.rfind(']'))
            if last_close > 0:
                partial = partial[:last_close + 1]

                open_braces, open_brackets = self._count_open_structures(partial)

                if open_braces >= 0 and open_brackets >= 0:
                    closing = ']' * open_brackets + '}' * open_braces
                    test_json = partial + closing

                    try:
                        parsed = json.loads(test_json)
                        logger.info(f"[RECOVERY] Strategy 4 success by removing {remove_count} lines")
                        return self._create_safe_dict(parsed)
                    except json.JSONDecodeError:
                        continue

        logger.warning("[RECOVERY] All strategies failed")
        return None

    def _count_open_structures(self, text: str) -> tuple:
        """Conta chaves e colchetes abertos, ignorando os que estão dentro de strings."""
        open_braces = 0
        open_brackets = 0
        in_string = False
        escape_next = False

        for char in text:
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
                open_braces += 1
            elif char == '}':
                open_braces -= 1
            elif char == '[':
                open_brackets += 1
            elif char == ']':
                open_brackets -= 1

        return open_braces, open_brackets

    def _extract_sections_regex(self, json_str: str) -> Optional[Dict[str, Any]]:
        """Extrai seções principais do JSON usando busca mais robusta."""
        sections = {}

        # Padrões para encontrar início de seções (novo schema simplificado)
        section_names = ["metadata", "actors", "keyDates", "keyFacts", "values", "issues", "conclusions", "recommendations"]

        for name in section_names:
            # Encontrar início da seção
            pattern = rf'"{name}"\s*:\s*'
            match = re.search(pattern, json_str)
            if not match:
                continue

            start_pos = match.end()
            if start_pos >= len(json_str):
                continue

            # Determinar se é objeto ou array
            first_char = json_str[start_pos:start_pos+1].strip()
            if not first_char:
                continue

            if first_char == '{':
                # Encontrar o fechamento do objeto
                content = self._extract_balanced_structure(json_str[start_pos:], '{', '}')
            elif first_char == '[':
                # Encontrar o fechamento do array
                content = self._extract_balanced_structure(json_str[start_pos:], '[', ']')
            else:
                continue

            if content:
                try:
                    parsed = json.loads(content)
                    sections[name] = parsed
                except json.JSONDecodeError:
                    # Tentar fechar estruturas abertas
                    open_braces, open_brackets = self._count_open_structures(content)
                    if open_braces >= 0 and open_brackets >= 0:
                        fixed = content + ']' * open_brackets + '}' * open_braces
                        try:
                            parsed = json.loads(fixed)
                            sections[name] = parsed
                        except json.JSONDecodeError:
                            pass

        return sections if sections else None

    def _extract_balanced_structure(self, text: str, open_char: str, close_char: str) -> Optional[str]:
        """Extrai uma estrutura balanceada (objeto ou array) do início do texto."""
        if not text or text[0] != open_char:
            return None

        count = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(text):
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
            if char == open_char:
                count += 1
            elif char == close_char:
                count -= 1
                if count == 0:
                    return text[:i + 1]

        # Se não fechou, retornar o que temos
        return text if count > 0 else None

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
