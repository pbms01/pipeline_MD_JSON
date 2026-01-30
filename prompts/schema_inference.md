# Schema Inference Prompt

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
