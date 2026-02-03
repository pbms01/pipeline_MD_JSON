# Descoberta Indutiva de Schema

Analise o documento e extraia sua estrutura natural.

## Formato de Resposta

```json
{
  "documentType": "contrato|ata|laudo|processo|relatorio|outro",
  "title": "título curto",
  "date": "YYYY-MM-DD",
  "summary": "uma frase",
  "schema": {
    "description": "tipo de documento em uma frase",
    "sections": ["seção1", "seção2", "seção3"]
  },
  "extractedData": {}
}
```

## REGRAS CRÍTICAS

1. **MÁXIMO 3000 caracteres** no JSON total
2. **MÁXIMO 3 itens** por array
3. **Strings curtas** - máximo 100 caracteres cada
4. **Sem arrays aninhados** em extractedData
5. **Omita campos vazios**
6. **APENAS JSON** - sem markdown, sem explicações

## extractedData - seja BREVE

Para cada tipo, extraia apenas os campos mais importantes:

- **Contrato**: partes (nomes), objeto (1 frase), valor, vigência
- **Ata**: data, participantes (nomes), deliberações (resumidas)
- **Laudo**: objeto, conclusão
- **Processo**: número, partes, pedido, decisão
- **Relatório**: objetivo, conclusão

## Documento

{document_text}
