# Prompt de Descoberta Indutiva de Schema

Você é um especialista em análise documental. Sua tarefa é descobrir a ESTRUTURA NATURAL deste documento.

## Instruções

1. **Identifique o tipo de documento** (contrato, ata, laudo, processo, relatório, etc.)

2. **Descubra a estrutura inerente** - Cada tipo de documento tem sua própria organização natural:
   - Contrato: partes, objeto, valor, prazo, obrigações, penalidades
   - Ata: data, participantes, pauta, deliberações, encaminhamentos
   - Laudo: objeto, metodologia, constatações, conclusão técnica
   - Processo: partes, pedido, causa de pedir, provas, decisão
   - Relatório: objetivo, metodologia, resultados, conclusões
   - etc.

3. **Extraia os dados** conforme a estrutura descoberta

## Formato de Resposta (JSON)

```json
{
  "documentType": "tipo identificado",
  "title": "título descritivo",
  "date": "YYYY-MM-DD ou null",
  "summary": "resumo em 2-3 frases",
  "schema": {
    "description": "breve descrição da estrutura do documento",
    "sections": ["lista das seções principais identificadas"]
  },
  "extractedData": {
    // Estrutura ESPECÍFICA para este tipo de documento
    // Use nomes de campos que façam sentido para ESTE documento
  }
}
```

## Exemplos de extractedData por tipo:

**Contrato:**
```json
"extractedData": {
  "partes": [{"nome": "", "papel": "contratante|contratado", "documento": ""}],
  "objeto": "descrição do objeto",
  "valor": {"total": 0, "moeda": "BRL", "formaPagamento": ""},
  "vigencia": {"inicio": "", "fim": "", "prazo": ""},
  "obrigacoes": {"contratante": [], "contratado": []},
  "garantias": [],
  "penalidades": [],
  "foro": ""
}
```

**Ata de Reunião:**
```json
"extractedData": {
  "reuniao": {"data": "", "hora": "", "local": "", "tipo": ""},
  "participantes": [{"nome": "", "cargo": "", "presenca": "presente|ausente"}],
  "pauta": ["item1", "item2"],
  "deliberacoes": [{"assunto": "", "decisao": "", "votos": ""}],
  "encaminhamentos": [{"acao": "", "responsavel": "", "prazo": ""}]
}
```

**Laudo/Parecer Técnico:**
```json
"extractedData": {
  "identificacao": {"numero": "", "data": "", "solicitante": ""},
  "objeto": "descrição do que foi analisado",
  "metodologia": "como foi feita a análise",
  "constatacoes": [{"item": "", "descricao": "", "evidencia": ""}],
  "conclusao": "conclusão técnica",
  "recomendacoes": []
}
```

**Processo Judicial:**
```json
"extractedData": {
  "processo": {"numero": "", "vara": "", "comarca": ""},
  "partes": {"autor": [], "reu": [], "terceiros": []},
  "objeto": "tipo de ação",
  "pedidos": [],
  "fundamentacao": "resumo dos fundamentos",
  "provas": [],
  "decisao": {"tipo": "", "dispositivo": "", "data": ""}
}
```

**Relatório:**
```json
"extractedData": {
  "identificacao": {"titulo": "", "autor": "", "data": ""},
  "objetivo": "objetivo do relatório",
  "metodologia": "como foi realizado",
  "resultados": [],
  "conclusoes": [],
  "recomendacoes": []
}
```

## Regras

1. **DESCUBRA** a estrutura - não force um schema predefinido
2. Use campos que façam sentido para ESTE documento específico
3. Seja conciso - máximo 5 itens por array, exceto quando essencial
4. Omita campos sem dados (não inclua campos vazios ou null)
5. Retorne APENAS JSON válido, sem texto antes ou depois

## Documento para Análise

{document_text}
