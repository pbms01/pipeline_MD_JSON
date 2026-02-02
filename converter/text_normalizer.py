"""
text_normalizer.py - Limpeza e normalização de texto para economia de tokens.

Este módulo prepara o texto do documento antes de enviar para o LLM,
removendo redundâncias e normalizando formatação para reduzir tokens.
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def normalize_text(
    text: str,
    max_chars: Optional[int] = None,
    remove_headers_footers: bool = True,
    compact_whitespace: bool = True,
    remove_page_numbers: bool = True,
    deduplicate_lines: bool = True
) -> str:
    """
    Normaliza e limpa texto para economia de tokens.

    Args:
        text: Texto bruto do documento
        max_chars: Limite máximo de caracteres (None = sem limite)
        remove_headers_footers: Remove cabeçalhos/rodapés repetitivos
        compact_whitespace: Compacta espaços em branco excessivos
        remove_page_numbers: Remove indicadores de página
        deduplicate_lines: Remove linhas duplicadas consecutivas

    Returns:
        Texto normalizado
    """
    if not text:
        return ""

    original_len = len(text)

    # 1. Remover caracteres de controle inválidos (exceto newlines e tabs)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    # 2. Normalizar quebras de linha (CRLF -> LF)
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # 3. Remover indicadores de página
    if remove_page_numbers:
        # Padrões comuns: "Página X de Y", "Page X", "- X -", etc.
        text = re.sub(r'\n\s*[-–—]\s*\d+\s*[-–—]\s*\n', '\n', text)
        text = re.sub(r'\n\s*[Pp]ágina\s+\d+\s*(de\s+\d+)?\s*\n', '\n', text)
        text = re.sub(r'\n\s*[Pp]age\s+\d+\s*(of\s+\d+)?\s*\n', '\n', text)
        text = re.sub(r'\n\s*\d+\s*/\s*\d+\s*\n', '\n', text)
        # Número de página isolado em linha
        text = re.sub(r'\n\s*\d{1,4}\s*\n', '\n', text)

    # 4. Remover cabeçalhos/rodapés repetitivos
    if remove_headers_footers:
        text = _remove_repeated_headers_footers(text)

    # 5. Compactar espaços em branco
    if compact_whitespace:
        # Múltiplos espaços -> um espaço
        text = re.sub(r'[ \t]+', ' ', text)
        # Espaços no início/fim de linhas
        text = re.sub(r' *\n *', '\n', text)
        # Múltiplas quebras de linha -> máximo duas
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Tabs -> espaço
        text = text.replace('\t', ' ')

    # 6. Remover linhas duplicadas consecutivas
    if deduplicate_lines:
        text = _deduplicate_consecutive_lines(text)

    # 7. Normalizar pontuação
    text = _normalize_punctuation(text)

    # 8. Compactar listas e enumerações
    text = _compact_lists(text)

    # 9. Remover linhas vazias no início e fim
    text = text.strip()

    # 10. Aplicar limite de caracteres se especificado
    if max_chars and len(text) > max_chars:
        # Truncar de forma inteligente (no fim de uma sentença)
        text = _smart_truncate(text, max_chars)

    final_len = len(text)
    reduction = ((original_len - final_len) / original_len * 100) if original_len > 0 else 0
    logger.info(f"[NORMALIZE] Text reduced from {original_len} to {final_len} chars ({reduction:.1f}% reduction)")

    return text


def _remove_repeated_headers_footers(text: str, min_occurrences: int = 2) -> str:
    """Remove cabeçalhos e rodapés que aparecem repetidamente."""
    lines = text.split('\n')
    if len(lines) < 20:
        return text

    # Identificar padrões de cabeçalho/rodapé
    # Analisar as primeiras e últimas linhas de cada "página" (aproximado por quebras duplas)
    pages = text.split('\n\n\n')
    if len(pages) < 2:
        return text

    # Coletar candidatos a cabeçalhos (primeiras linhas de cada seção)
    header_candidates = {}
    footer_candidates = {}

    for page in pages:
        page_lines = [l.strip() for l in page.strip().split('\n') if l.strip()]
        if len(page_lines) >= 2:
            # Primeira linha como candidato a cabeçalho
            header = page_lines[0][:100]  # Limitar tamanho
            if len(header) > 5:
                header_candidates[header] = header_candidates.get(header, 0) + 1

            # Última linha como candidato a rodapé
            footer = page_lines[-1][:100]
            if len(footer) > 5:
                footer_candidates[footer] = footer_candidates.get(footer, 0) + 1

    # Remover padrões que aparecem frequentemente
    patterns_to_remove = []
    for pattern, count in header_candidates.items():
        if count >= min_occurrences:
            patterns_to_remove.append(pattern)
    for pattern, count in footer_candidates.items():
        if count >= min_occurrences:
            patterns_to_remove.append(pattern)

    # Aplicar remoção
    for pattern in patterns_to_remove:
        # Escapar caracteres especiais de regex
        escaped = re.escape(pattern)
        text = re.sub(rf'^{escaped}\s*\n', '', text, flags=re.MULTILINE)
        text = re.sub(rf'\n{escaped}\s*$', '', text, flags=re.MULTILINE)

    return text


def _deduplicate_consecutive_lines(text: str) -> str:
    """Remove linhas idênticas consecutivas."""
    lines = text.split('\n')
    result = []
    prev_line = None

    for line in lines:
        stripped = line.strip()
        # Manter linha se for diferente da anterior ou se for vazia (para espaçamento)
        if stripped != prev_line or stripped == '':
            result.append(line)
            if stripped:  # Só atualiza prev_line se não for vazia
                prev_line = stripped

    return '\n'.join(result)


def _normalize_punctuation(text: str) -> str:
    """Normaliza caracteres de pontuação."""
    # Aspas tipográficas -> aspas simples
    text = re.sub(r'[""]', '"', text)
    text = re.sub(r"['']", "'", text)

    # Travessões -> hífen simples
    text = re.sub(r'[–—]', '-', text)

    # Múltiplos pontos/hífens
    text = re.sub(r'\.{4,}', '...', text)
    text = re.sub(r'-{3,}', '--', text)
    text = re.sub(r'_{3,}', '__', text)

    # Espaços antes de pontuação
    text = re.sub(r' +([.,;:!?])', r'\1', text)

    return text


def _compact_lists(text: str) -> str:
    """Compacta listas numeradas e com marcadores."""
    # Remover espaços excessivos em itens de lista
    text = re.sub(r'\n(\s*[-•●○]\s*)', r'\n- ', text)
    text = re.sub(r'\n(\s*\d+[.)]\s*)', lambda m: f"\n{m.group(1).strip()} ", text)

    return text


def _smart_truncate(text: str, max_chars: int) -> str:
    """Trunca texto de forma inteligente, preservando sentenças completas."""
    if len(text) <= max_chars:
        return text

    # Encontrar o último ponto final antes do limite
    truncated = text[:max_chars]

    # Procurar último fim de sentença
    last_period = max(
        truncated.rfind('. '),
        truncated.rfind('.\n'),
        truncated.rfind('? '),
        truncated.rfind('?\n'),
        truncated.rfind('! '),
        truncated.rfind('!\n')
    )

    if last_period > max_chars * 0.7:  # Se encontrou ponto após 70% do texto
        truncated = truncated[:last_period + 1]
    else:
        # Fallback: cortar na última quebra de parágrafo
        last_para = truncated.rfind('\n\n')
        if last_para > max_chars * 0.5:
            truncated = truncated[:last_para]

    return truncated + "\n\n[... documento truncado ...]"


def estimate_tokens(text: str) -> int:
    """
    Estima o número de tokens para um texto.

    Usa heurística simples: ~4 caracteres por token em português.
    """
    if not text:
        return 0
    # Aproximação: 1 token ≈ 4 caracteres em português
    return len(text) // 4


def get_reduction_stats(original: str, normalized: str) -> dict:
    """Retorna estatísticas de redução."""
    orig_chars = len(original)
    norm_chars = len(normalized)
    orig_tokens = estimate_tokens(original)
    norm_tokens = estimate_tokens(normalized)

    return {
        "original_chars": orig_chars,
        "normalized_chars": norm_chars,
        "char_reduction_pct": round((orig_chars - norm_chars) / orig_chars * 100, 1) if orig_chars > 0 else 0,
        "estimated_original_tokens": orig_tokens,
        "estimated_normalized_tokens": norm_tokens,
        "estimated_token_savings": orig_tokens - norm_tokens
    }
