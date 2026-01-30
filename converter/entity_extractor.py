"""
entity_extractor.py - Extrai entidades nomeadas do documento.

Este módulo extrai entidades padronizadas (pessoas, organizações, datas, etc.)
que fazem parte da camada fixa do JSON.
"""
import json
import re
from typing import Dict, Any, List, Optional
import logging

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from .models import (
    ExtractedEntities, Person, Organization, Location,
    DateMention, MonetaryValue
)
from config.settings import CLAUDE_MODEL

logger = logging.getLogger(__name__)


ENTITY_EXTRACTION_PROMPT = """
Extraia todas as entidades nomeadas deste documento.

## Categorias de Entidades

### Pessoas
- Nomes completos
- Papel/função quando mencionado

### Organizações
- Empresas, instituições, órgãos
- Tipo quando identificável (empresa, governo, ONG, etc.)

### Locais
- Cidades, estados, países
- Endereços completos
- Tipo: city, state, country, address, region

### Datas
- Todas as datas mencionadas
- Formato original e normalizado (YYYY-MM-DD)
- Contexto: o que a data representa

### Valores Monetários
- Todos os valores em dinheiro
- Valor numérico quando possível
- Moeda
- Contexto: o que o valor representa

### Termos Técnicos
- Siglas e acrônimos
- Termos específicos do domínio
- Jargão técnico

## Formato de Resposta

```json
{
  "people": [
    {"name": "Nome Completo", "role": "Cargo/Função ou null"}
  ],
  "organizations": [
    {"name": "Nome da Organização", "type": "company|government|ngo|institution|other"}
  ],
  "locations": [
    {"name": "Nome do Local", "type": "city|state|country|address|region|other"}
  ],
  "dates": [
    {"original": "texto original", "normalized": "YYYY-MM-DD ou null", "context": "significado"}
  ],
  "monetary_values": [
    {"original": "R$ 1.000,00", "value": 1000.00, "currency": "BRL", "context": "significado"}
  ],
  "technical_terms": ["termo1", "termo2"]
}
```

## Regras
1. Não invente entidades - extraia apenas o que está no texto
2. Para datas ambíguas, coloque normalized como null
3. Para valores não numéricos ("milhões"), tente converter
4. Remova duplicatas
5. Retorne APENAS o JSON válido

## Documento

{document_text}
"""


class EntityExtractor:
    """
    Extrai entidades nomeadas do documento.

    Usa combinação de:
    1. Regex para padrões conhecidos (datas, valores)
    2. LLM para entidades semânticas (pessoas, orgs)
    """

    def __init__(self, model: str = CLAUDE_MODEL):
        self.model = model
        if HAS_ANTHROPIC:
            self.client = anthropic.Anthropic()
        else:
            self.client = None

        # Padrões regex para extração rápida
        self.patterns = {
            "date_br": re.compile(r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\b'),
            "date_iso": re.compile(r'\b(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})\b'),
            "date_extenso": re.compile(
                r'\b(\d{1,2})\s+de\s+(janeiro|fevereiro|março|abril|maio|junho|'
                r'julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})\b',
                re.IGNORECASE
            ),
            "money_br": re.compile(r'R\$\s*([\d.,]+)'),
            "money_usd": re.compile(r'US\$\s*([\d.,]+)'),
            "cpf": re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}[-.]?\d{2}\b'),
            "cnpj": re.compile(r'\b\d{2}\.?\d{3}\.?\d{3}[/]?\d{4}[-.]?\d{2}\b'),
        }

    def extract(
        self,
        document_text: str,
        use_llm: bool = True,
        max_chars: int = 20000
    ) -> ExtractedEntities:
        """
        Extrai entidades do documento.

        Args:
            document_text: Texto do documento
            use_llm: Se True, usa LLM para extração semântica
            max_chars: Máximo de caracteres para LLM

        Returns:
            ExtractedEntities
        """
        entities = ExtractedEntities()

        # Extração por regex (rápida)
        regex_dates = self._extract_dates_regex(document_text)
        regex_money = self._extract_money_regex(document_text)

        if use_llm and self.client:
            # Extração via LLM (mais completa)
            llm_entities = self._extract_via_llm(document_text[:max_chars])

            # Mesclar resultados
            entities = self._merge_entities(llm_entities, regex_dates, regex_money)
        else:
            entities.dates = regex_dates
            entities.monetary_values = regex_money

        return entities

    def _extract_dates_regex(self, text: str) -> List[DateMention]:
        """Extrai datas usando regex."""
        dates = []
        seen = set()

        # Meses para conversão
        months = {
            'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04',
            'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08',
            'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
        }

        # Formato BR: dd/mm/yyyy
        for match in self.patterns["date_br"].finditer(text):
            original = match.group(0)
            if original in seen:
                continue
            seen.add(original)

            try:
                d, m, y = match.groups()
                y = f"20{y}" if len(y) == 2 else y
                normalized = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
                dates.append(DateMention(original=original, normalized=normalized))
            except Exception:
                dates.append(DateMention(original=original))

        # Formato extenso: "15 de março de 2024"
        for match in self.patterns["date_extenso"].finditer(text):
            original = match.group(0)
            if original in seen:
                continue
            seen.add(original)

            try:
                d, m, y = match.groups()
                m_num = months.get(m.lower(), '01')
                normalized = f"{y}-{m_num}-{d.zfill(2)}"
                dates.append(DateMention(original=original, normalized=normalized))
            except Exception:
                dates.append(DateMention(original=original))

        return dates

    def _extract_money_regex(self, text: str) -> List[MonetaryValue]:
        """Extrai valores monetários usando regex."""
        values = []
        seen = set()

        # Reais
        for match in self.patterns["money_br"].finditer(text):
            original = f"R$ {match.group(1)}"
            if original in seen:
                continue
            seen.add(original)

            try:
                value_str = match.group(1).replace('.', '').replace(',', '.')
                value = float(value_str)
                values.append(MonetaryValue(
                    original=original,
                    value=value,
                    currency="BRL"
                ))
            except Exception:
                values.append(MonetaryValue(original=original, currency="BRL"))

        # Dólares
        for match in self.patterns["money_usd"].finditer(text):
            original = f"US$ {match.group(1)}"
            if original in seen:
                continue
            seen.add(original)

            try:
                value_str = match.group(1).replace(',', '')
                value = float(value_str)
                values.append(MonetaryValue(
                    original=original,
                    value=value,
                    currency="USD"
                ))
            except Exception:
                values.append(MonetaryValue(original=original, currency="USD"))

        return values

    def _extract_via_llm(self, text: str) -> ExtractedEntities:
        """Extrai entidades usando LLM."""
        if not self.client:
            return ExtractedEntities()

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{
                    "role": "user",
                    "content": ENTITY_EXTRACTION_PROMPT.format(document_text=text)
                }]
            )

            result = self._parse_json_response(response.content[0].text)

            return ExtractedEntities(
                people=[
                    Person(name=p["name"], role=p.get("role"))
                    for p in result.get("people", [])
                    if isinstance(p, dict) and "name" in p
                ],
                organizations=[
                    Organization(name=o["name"], org_type=o.get("type"))
                    for o in result.get("organizations", [])
                    if isinstance(o, dict) and "name" in o
                ],
                locations=[
                    Location(name=l["name"], location_type=l.get("type", "other"))
                    for l in result.get("locations", [])
                    if isinstance(l, dict) and "name" in l
                ],
                dates=[
                    DateMention(
                        original=d["original"],
                        normalized=d.get("normalized"),
                        context=d.get("context")
                    )
                    for d in result.get("dates", [])
                    if isinstance(d, dict) and "original" in d
                ],
                monetary_values=[
                    MonetaryValue(
                        original=m["original"],
                        value=m.get("value"),
                        currency=m.get("currency"),
                        context=m.get("context")
                    )
                    for m in result.get("monetary_values", [])
                    if isinstance(m, dict) and "original" in m
                ],
                technical_terms=result.get("technical_terms", [])
            )
        except Exception as e:
            logger.warning(f"Error extracting entities via LLM: {e}")
            return ExtractedEntities()

    def _merge_entities(
        self,
        llm_entities: ExtractedEntities,
        regex_dates: List[DateMention],
        regex_money: List[MonetaryValue]
    ) -> ExtractedEntities:
        """Mescla entidades de LLM com regex."""
        # Para datas e valores, preferir LLM (tem contexto)
        # mas adicionar regex que LLM não pegou

        merged_dates = []
        seen_dates = set()

        # Primeiro, adicionar do LLM (tem contexto)
        for d in llm_entities.dates:
            seen_dates.add(d.original)
            merged_dates.append(d)

        # Adicionar regex que LLM não pegou
        for d in regex_dates:
            if d.original not in seen_dates:
                merged_dates.append(d)

        # Mesmo para valores monetários
        merged_money = []
        seen_money = set()

        for m in llm_entities.monetary_values:
            seen_money.add(m.original)
            merged_money.append(m)

        for m in regex_money:
            if m.original not in seen_money:
                merged_money.append(m)

        return ExtractedEntities(
            people=llm_entities.people,
            organizations=llm_entities.organizations,
            locations=llm_entities.locations,
            dates=merged_dates,
            monetary_values=merged_money,
            technical_terms=llm_entities.technical_terms
        )

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Extrai JSON da resposta."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]

        start = text.find("{")
        end = text.rfind("}") + 1

        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        return {}


def extract_entities(
    document_text: str,
    use_llm: bool = True
) -> ExtractedEntities:
    """Função de conveniência."""
    extractor = EntityExtractor()
    return extractor.extract(document_text, use_llm)
