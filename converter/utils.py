"""
utils.py - Funções utilitárias para o pipeline.
"""
import re
import unicodedata
from typing import List, Optional, Tuple
from pathlib import Path


def normalize_text(text: str) -> str:
    """Normaliza texto removendo caracteres especiais e espaços extras."""
    if not text:
        return ""
    # Normalizar unicode
    text = unicodedata.normalize("NFKC", text)
    # Remover múltiplos espaços
    text = re.sub(r'\s+', ' ', text)
    # Remover espaços no início e fim
    return text.strip()


def clean_text(text: str) -> str:
    """Limpa texto removendo caracteres de controle."""
    if not text:
        return ""
    # Remover caracteres de controle exceto newlines e tabs
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    return text


def extract_title_from_text(text: str, max_length: int = 100) -> Optional[str]:
    """Extrai título provável do início do texto."""
    if not text:
        return None

    lines = text.strip().split('\n')
    for line in lines[:5]:  # Procura nas primeiras 5 linhas
        line = line.strip()
        if len(line) > 10 and len(line) < max_length:
            # Verificar se parece um título (não termina com pontuação de frase)
            if not line.endswith(('.', ',', ';', ':')):
                return line
    return None


def estimate_token_count(text: str) -> int:
    """Estima contagem de tokens (aproximado)."""
    if not text:
        return 0
    # Aproximação: ~4 caracteres por token para português
    return len(text) // 4


def split_into_sentences(text: str) -> List[str]:
    """Divide texto em sentenças."""
    if not text:
        return []

    # Padrão para fim de sentença
    pattern = r'(?<=[.!?])\s+(?=[A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇÑ])'
    sentences = re.split(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def is_heading_text(text: str, font_size: Optional[float] = None,
                    body_font_size: float = 12.0) -> Tuple[bool, int]:
    """
    Verifica se texto é um heading e retorna o nível.

    Returns:
        Tupla (is_heading, level)
    """
    if not text:
        return False, 0

    text = text.strip()

    # Verificar padrões de numeração (1., 1.1, 1.1.1, etc.)
    numbered_pattern = r'^(\d+\.)+\s*\d*\.?\s*'
    if re.match(numbered_pattern, text):
        # Contar níveis pela quantidade de pontos
        dots = text.count('.')
        level = min(dots, 6)
        return True, level

    # Verificar se é curto e em maiúsculas (típico de título)
    if len(text) < 100 and text.isupper():
        return True, 1

    # Verificar por tamanho da fonte
    if font_size and font_size > body_font_size * 1.2:
        ratio = font_size / body_font_size
        if ratio > 1.8:
            return True, 1
        elif ratio > 1.5:
            return True, 2
        elif ratio > 1.2:
            return True, 3

    return False, 0


def detect_list_item(text: str) -> Tuple[bool, str, int, Optional[int]]:
    """
    Detecta se texto é item de lista.

    Returns:
        Tupla (is_list_item, list_type, level, index)
    """
    if not text:
        return False, "", 0, None

    text = text.strip()

    # Lista ordenada: "1.", "a)", "(i)", etc.
    ordered_patterns = [
        (r'^(\d+)[.)]\s+', 'ordered'),
        (r'^([a-z])[.)]\s+', 'ordered'),
        (r'^\(([ivxlcdm]+)\)\s+', 'ordered'),
        (r'^\((\d+)\)\s+', 'ordered'),
    ]

    for pattern, list_type in ordered_patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            return True, list_type, 0, None

    # Lista não-ordenada: "-", "*", "•", etc.
    unordered_patterns = [
        r'^[-•●○◦▪▸►]\s+',
        r'^\*\s+',
    ]

    for pattern in unordered_patterns:
        if re.match(pattern, text):
            return True, 'unordered', 0, None

    return False, "", 0, None


def merge_hyphenated_words(text: str) -> str:
    """Junta palavras quebradas por hífen no fim da linha."""
    if not text:
        return ""
    # Padrão: palavra- \n continuação
    pattern = r'(\w+)-\s*\n\s*(\w+)'
    return re.sub(pattern, r'\1\2', text)


def extract_page_numbers(text: str) -> List[int]:
    """Extrai números de página mencionados no texto."""
    pattern = r'(?:página|pág\.?|pg\.?|p\.)\s*(\d+)'
    matches = re.findall(pattern, text, re.IGNORECASE)
    return [int(m) for m in matches]


def sanitize_filename(filename: str) -> str:
    """Sanitiza nome de arquivo removendo caracteres inválidos."""
    # Remover caracteres inválidos
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remover múltiplos underscores
    filename = re.sub(r'_+', '_', filename)
    # Limitar tamanho
    if len(filename) > 200:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:200] + ('.' + ext if ext else '')
    return filename


def get_file_extension(file_path: Path) -> str:
    """Retorna extensão do arquivo em minúsculas."""
    return file_path.suffix.lower()


def is_supported_file(file_path: Path, supported_extensions: set) -> bool:
    """Verifica se arquivo é suportado."""
    return get_file_extension(file_path) in supported_extensions


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Trunca texto mantendo palavras inteiras."""
    if not text or len(text) <= max_length:
        return text

    truncated = text[:max_length - len(suffix)]
    # Encontrar último espaço
    last_space = truncated.rfind(' ')
    if last_space > max_length // 2:
        truncated = truncated[:last_space]

    return truncated + suffix


def format_file_size(size_bytes: int) -> str:
    """Formata tamanho de arquivo para leitura humana."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def parse_date_br(date_str: str) -> Optional[str]:
    """
    Converte data em formato brasileiro para ISO.

    Args:
        date_str: Data em formato DD/MM/YYYY ou similar

    Returns:
        Data em formato YYYY-MM-DD ou None
    """
    patterns = [
        (r'(\d{1,2})/(\d{1,2})/(\d{4})', lambda m: f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"),
        (r'(\d{1,2})-(\d{1,2})-(\d{4})', lambda m: f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"),
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
    ]

    for pattern, converter in patterns:
        match = re.search(pattern, date_str)
        if match:
            return converter(match)

    return None


def parse_monetary_value_br(value_str: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Converte valor monetário brasileiro.

    Args:
        value_str: Valor em formato "R$ 1.234,56" ou similar

    Returns:
        Tupla (valor numérico, moeda) ou (None, None)
    """
    # Detectar moeda
    currency = None
    if 'R$' in value_str or 'BRL' in value_str:
        currency = 'BRL'
    elif 'US$' in value_str or 'USD' in value_str:
        currency = 'USD'
    elif 'EUR' in value_str or '€' in value_str:
        currency = 'EUR'

    # Extrair valor numérico
    # Formato brasileiro: 1.234.567,89
    match = re.search(r'[\d.,]+', value_str)
    if match:
        value_text = match.group()
        # Verificar se usa formato brasileiro (vírgula como decimal)
        if ',' in value_text and '.' in value_text:
            # Brasileiro: remover pontos e trocar vírgula por ponto
            value_text = value_text.replace('.', '').replace(',', '.')
        elif ',' in value_text:
            # Só vírgula: trocar por ponto
            value_text = value_text.replace(',', '.')

        try:
            return float(value_text), currency
        except ValueError:
            pass

    return None, currency
