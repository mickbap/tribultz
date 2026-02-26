# Sprint 6 — Discovery consolidado (Top 10 + paths + runbook)

Status (26/02/2026):
- Template de coleta (Roberta) já no repo: `docs/sprints/S6_Discovery_Roberta_Template.md` (issue #20)
- Exemplos anonimizados + gabarito: PR #30 (DRAFT) / issue #21 — aguardando material da Roberta
- Este documento consolida o que já sabemos + estrutura para completar assim que Roberta enviar exemplos/paths

## 1) Top 10 validações (baseline do time — preencher/refinar com Roberta)

Observação: linhas 1–5 refletem regras/UX já implementadas ou placeholders atuais; linhas 6–10 são itens esperados para completar com Roberta.

| # | rule_id | Doc | Sev | Campo / Onde está (exemplo) | Regra (objetiva) | Evidência mínima | UI esperada |
|---|---------|-----|-----|------------------------------|------------------|------------------|-------------|
| 1 | CST_3_DIGITS | NFSE | FATAL | CST — /NFS-e/infNfse//CST | CST deve ter exatamente 3 dígitos | XML + snippet + xpath | “CST inválido… Corrigir no ERP e reemitir.” |
| 2 | CCLASSTRIB_6_DIGITS | NFSE | FATAL | cClassTrib — /NFS-e/infNfse//cClassTrib | cClassTrib deve ter exatamente 6 dígitos | XML + snippet + xpath | “cClassTrib inválido… Corrigir no ERP e reemitir.” |
| 3 | SERVICE_CODE_6_DIGITS | NFSE | FATAL | CodigoServico — /NFS-e/infNfse//CodigoServico | Código de serviço deve ter exatamente 6 dígitos | XML + snippet + xpath | “Código de serviço inválido… Corrigir no ERP e reemitir.” |
| 4 | XML_PARSE | NFSE/NFE | FATAL | documento inteiro | XML deve ser bem-formado e parseável | XML completo | “XML inválido… Verificar arquivo/cole o XML correto.” |
| 5 | NCM_PLACEHOLDER | NFSE/NFE | ALERT | NCM — /NFS-e/infNfse//NCM | Revisar NCM conforme classificação vigente | XML + snippet + xpath | “Revisar NCM… manter evidência de suporte.” |
| 6 | BENEFITS_PLACEHOLDER | NFSE/NFE | ALERT | (variável) | Revisar benefícios/créditos aplicáveis | print/link/nota interna + justificativa | “Documentar justificativa fiscal…” |
| 7 | IBSCBS_FIELDS (TBD) | NFSE | ALERT/FATAL (TBD) | (TBD) | Campos IBS/CBS específicos de NFS-e/Portal Nacional | XML + snippet + xpath | Mensagem + recomendação (TBD) |
| 8 | MUNICIPIO_BASE (TBD) | NFSE | ALERT (TBD) | (TBD) | Divergência de município/base em multi-CNPJ/filiais | XML + evidência complementar | Mensagem orientada a operação/filial |
| 9 | CREDIT_RULES (TBD) | NFSE/NFE | ALERT (TBD) | (TBD) | Consistência de créditos permitidos (placeholder hoje) | XML + regra de negócio | “Revisar crédito…” |
| 10 | BENEFIT_CODE (TBD) | NFSE/NFE | ALERT/FATAL (TBD) | (TBD) | Benefícios/códigos específicos por operação | XML + print/link | Mensagem + recomendação (TBD) |

## 2) Paths/variações comuns (baseline do código hoje)

Atenção: NFS-e varia por provedor; abaixo é “o que o motor atual encontra” nos fixtures/mock.

### CST
- XPath usado hoje (baseline): `/NFS-e/infNfse//CST`
- Snippet típico: `<CST>12</CST>` (exemplo inválido)
- TODO Roberta: indicar variações de tag/caminho nos layouts reais

### cClassTrib
- XPath usado hoje: `/NFS-e/infNfse//cClassTrib`
- Snippet típico: `<cClassTrib>65432</cClassTrib>` (exemplo inválido)
- TODO Roberta: variações e onde aparece em Portal Nacional x provedores

### Código de Serviço
- XPath usado hoje: `/NFS-e/infNfse//CodigoServico`
- Snippet típico: `<CodigoServico>1234</CodigoServico>` (exemplo inválido)
- TODO Roberta: nomenclaturas alternativas (CodigoServicoPrestado, ItemListaServico, etc.)

### NCM
- XPath usado hoje: `/NFS-e/infNfse//NCM`
- TODO Roberta: quando ALERTA vs quando (se existir) FATAL + mensagem preferida

## 3) Exemplos anonimizados + gabarito

PR #30 (DRAFT) contém scaffold em: `docs/sprints/discovery/examples/`

Assim que Roberta enviar 3 exemplos anonimizados, preencher:
- `example_a.xml`, `example_b.xml`, `example_c.xml`
- `S6_Discovery_Examples.md` com gabarito (findings esperados)

## 4) Runbook (time) — como evoluir o motor

### Onde adicionar regra
- Engine de validação: `frontend/src/lib/validation/xmlRules.ts`
- Testes unitários: `frontend/src/lib/validation/xmlRules.test.ts`
- Fixtures XML: `frontend/src/lib/validation/fixtures/*.xml`

### Como garantir evidência (fonte)
- Todo finding deve retornar `where` com `xpath` e/ou `snippet` (ideal: ambos)
- Evidência deve apontar para fonte primária (XML/link/print) — prioridade máxima

### Como marcar severidade e recomendação
- Severidade: FATAL trava/indica bloqueio; ALERT informa e permite seguir
- Recommendation padrão (baseline): “Corrigir no ERP e reemitir (com justificativa se necessário).”

### Como validar (DoD técnico)
- Adicionar fixture que dispara a regra
- Adicionar teste unitário cobrindo:
  - `finding.rule_id`, `severity`
  - presença de `where.snippet/xpath`
- Rodar: `npm test --silent` e `npm run build`

## DoD (#22)
- Documento consolidado versionado no repo
- Referencia template (#20) e exemplos (#21/#30)
- Top 10 + paths + runbook claros o suficiente para execução do time
