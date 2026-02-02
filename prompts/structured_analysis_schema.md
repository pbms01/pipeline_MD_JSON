# Prompt de Inferência de Schema Estruturado

Você é um especialista em análise documental estruturada. Analise o documento fornecido e extraia informações seguindo rigorosamente o schema abaixo.

## Schema de Saída

O JSON de saída DEVE seguir esta estrutura:

```json
{
  "metadata": {
    "id": "string - identificador único gerado",
    "title": "string - título descritivo do documento",
    "documentType": "string - tipo do documento (ver lista)",
    "sourceFiles": [{
      "filename": "string",
      "format": "pdf | docx | xlsx | txt",
      "pages": "number | null"
    }],
    "analysisDate": "YYYY-MM-DD",
    "version": 1,
    "status": "draft",
    "confidentiality": "public | internal | confidential",
    "tags": ["string"],
    "notes": "string | null"
  },
  "entities": {
    "actors": [{
      "id": "actor-[identificador]",
      "type": "person | organization | government_body",
      "name": "string",
      "shortName": "string | null",
      "identifiers": {
        "cpf": "string | null",
        "cnpj": "string | null",
        "rg": "string | null",
        "oab": "string | null",
        "other": {}
      },
      "role": "string",
      "category": "string",
      "contact": {
        "email": "string | null",
        "phone": "string | null",
        "address": "string | null"
      },
      "notes": "string | null"
    }],
    "documents": [{
      "id": "doc-[identificador]",
      "name": "string",
      "type": "string",
      "reference": "string | null",
      "date": "YYYY-MM-DD | null",
      "author": "actor-id | null",
      "summary": "string | null",
      "relatedActors": ["actor-id"],
      "tags": ["string"]
    }],
    "assets": [{
      "id": "asset-[identificador]",
      "type": "string",
      "description": "string",
      "value": {
        "amount": "number | null",
        "currency": "BRL | USD | null"
      },
      "ownership": {
        "owner": "actor-id | null"
      },
      "location": "string | null"
    }],
    "events": [{
      "id": "event-[YYYY-MM-DD]-[identificador]",
      "date": "YYYY-MM-DD",
      "time": "HH:MM | null",
      "type": "string",
      "description": "string",
      "location": "string | null",
      "involvedActors": ["actor-id"],
      "involvedAssets": ["asset-id"],
      "outcome": "string | null"
    }],
    "relationships": [{
      "id": "rel-[identificador]",
      "type": "string",
      "sourceId": "string",
      "sourceType": "actor | document | asset | event",
      "targetId": "string",
      "targetType": "actor | document | asset | event",
      "strength": "confirmed | probable | possible | alleged",
      "evidence": ["string"]
    }]
  },
  "evidence": {
    "documentary": [{
      "id": "evid-doc-[número]",
      "type": "string",
      "description": "string",
      "sourceDocument": "doc-id",
      "pageReference": "string | null",
      "relevance": "high | medium | low",
      "supportsClaims": ["finding-id"]
    }],
    "testimonial": [],
    "technical": [],
    "digital": []
  },
  "analysis": {
    "findings": [{
      "id": "finding-[identificador]",
      "category": "string",
      "title": "string",
      "description": "string",
      "significance": "string",
      "confidence": "high | medium | low",
      "supportingEvidence": ["evid-id"],
      "relatedEntities": ["entity-id"]
    }],
    "issues": [{
      "id": "issue-[identificador]",
      "category": "string",
      "description": "string",
      "severity": "critical | major | moderate | minor",
      "status": "open | resolved"
    }],
    "recommendations": [{
      "id": "rec-[identificador]",
      "type": "string",
      "title": "string",
      "description": "string",
      "priority": "critical | high | medium | low",
      "relatedFindings": ["finding-id"]
    }]
  },
  "timeline": [{
    "date": "YYYY-MM-DD",
    "entries": [{
      "id": "tl-[YYYY-MM-DD]-[seq]",
      "time": "HH:MM | null",
      "type": "string",
      "description": "string",
      "actors": ["actor-id"],
      "significance": "high | medium | low"
    }]
  }],
  "synthesis": {
    "executiveSummary": "string - resumo executivo em 2-3 parágrafos",
    "keyPoints": [{
      "point": "string",
      "supportingFindings": ["finding-id"]
    }],
    "conclusions": [{
      "id": "conclusion-[número]",
      "statement": "string",
      "confidence": "high | medium | low",
      "caveats": ["string"]
    }],
    "openQuestions": [{
      "question": "string",
      "relevance": "string"
    }],
    "nextSteps": [{
      "step": "string",
      "priority": "critical | high | medium | low"
    }]
  }
}
```

## Tipos de Documento (documentType)

### Jurídico/Processual
processo_judicial, processo_administrativo, inquerito, denuncia, sentenca, acordao, parecer, contrato, procuracao

### Corporativo/Empresarial
relatorio_financeiro, auditoria, compliance, due_diligence, plano_negocios, ata_reuniao, estatuto_social, balanco

### Técnico/Pericial
laudo_pericial, relatorio_tecnico, parecer_tecnico, vistoria, avaliacao, estudo_impacto

### Administrativo/Governamental
edital, licitacao, convenio, termo_referencia, prestacao_contas, relatorio_gestao, ato_normativo

### Investigativo
dossie, relatorio_inteligencia, analise_financeira, levantamento

### Acadêmico/Pesquisa
artigo, tese, relatorio_pesquisa

### Genérico
documento_geral, correspondencia, memorial, proposta

## Categorias de Atores

### Setor Público
servidor_publico, magistrado, promotor, procurador, delegado, policial, perito_oficial, gestor_publico, autoridade

### Setor Privado
empresario, executivo, socio, funcionario, consultor, advogado, contador, auditor, perito_particular

### Outros
particular, testemunha, vitima, beneficiario, representante, intermediario

## Tipos de Relacionamento

### Vínculos Pessoais/Organizacionais
emprego, sociedade, representacao, subordinacao, parentesco, conjugal

### Vínculos Contratuais/Negociais
contratual, fornecimento, cliente, parceria, subcontratacao

### Vínculos Financeiros
pagamento, recebimento, emprestimo, investimento, garantia, beneficio

### Vínculos Processuais
autoria, vitimizacao, testemunho, representacao_legal

### Vínculos de Propriedade
propriedade, posse, uso, custodia

## Categorias de Achados (findings)

### Factuais
fato_confirmado, fato_provavel, fato_possivel, fato_contestado

### Jurídicos
ilicito_penal, ilicito_civil, ilicito_administrativo, irregularidade, nulidade

### Financeiros
dano_patrimonial, enriquecimento_ilicito, desvio, fraude, superfaturamento

### Técnicos
inconsistencia_dados, ausencia_documentacao, divergencia, falsidade

### Positivos
conformidade, regularidade, comprovacao, validacao

## Regras de Preenchimento

1. **IDs únicos e descritivos**: Use prefixos semânticos (actor-, doc-, event-, finding-, etc.)

2. **Referências cruzadas**: Vincule entidades sempre que houver relação

3. **Datas em ISO 8601**: Sempre YYYY-MM-DD

4. **Use null**: Para campos não aplicáveis ou não encontrados

5. **Confidence/Strength**:
   - confirmed/high = evidência direta e inequívoca
   - probable/medium = indícios consistentes
   - possible/low = hipótese plausível
   - alleged = declarado mas não verificado

6. **Timeline consolidada**: Inclua TODOS os eventos relevantes em ordem cronológica

7. **Synthesis obrigatória**: Sempre preencha executiveSummary e conclusions

## Documento para Análise

{document_text}

## Instruções Finais

1. Extraia TODAS as entidades identificáveis (pessoas, organizações, documentos, valores, datas)
2. Identifique relacionamentos entre as entidades
3. Catalogue evidências que suportam os achados
4. Registre achados analíticos com nível de confiança
5. Liste problemas ou lacunas identificadas
6. Proponha recomendações quando pertinente
7. Construa timeline cronológica
8. Sintetize com resumo executivo e conclusões

Retorne APENAS o JSON válido, sem explicações adicionais.
