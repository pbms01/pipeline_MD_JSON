# Entity Extraction Prompt

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
