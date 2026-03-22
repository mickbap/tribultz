# Sprint 7 — Discovery consolidado (Top 10 + paths + runbook)

Status (21/03/2026):
- Template de coleta (Roberta) no repo: `docs/sprints/S6_Discovery_Roberta_Template.md` (issue #20)
- Exemplos anonimizados + gabarito: `docs/sprints/discovery/examples/` — 3 XMLs construídos pelo time de engenharia com base no feedback da contabilidade (21/03/2026)
- Top 10 regras atualizadas com input direto do time de contabilidade (alíquotas CBS 0,10% / IBS 0,90%)
- Base legal: LC 214 (lei geral) + LC 227 (13/jan/2026, atualizações)

## 1) Top 10 validações (baseline do time — preencher/refinar com Roberta)

Regras 1–5: já implementadas no motor (S6). Regras 6–10: novas, priorizadas pelo time de contabilidade (21/03/2026).

| # | rule_id | Doc | Sev | Campo / Onde está (exemplo) | Regra (objetiva) | Evidência mínima | UI esperada |
|---|---------|-----|-----|------------------------------|------------------|------------------|-------------|
| 1 | CST_3_DIGITS | NFSE | FATAL | CST — /NFS-e/infNfse//CST | CST deve ter exatamente 3 dígitos | XML + snippet + xpath | “CST inválido… Corrigir no ERP e reemitir.” |
| 2 | CCLASSTRIB_6_DIGITS | NFSE | FATAL | cClassTrib — /NFS-e/infNfse//cClassTrib | cClassTrib deve ter exatamente 6 dígitos — verificar conforme categoria do negócio | XML + snippet + xpath | “ClassTrib incorreto… Verificar código conforme categoria do negócio e reemitir.” |
| 3 | SERVICE_CODE_6_DIGITS | NFSE | FATAL | CodigoServico — /NFS-e/infNfse//CodigoServico | Código de serviço deve ter exatamente 6 dígitos | XML + snippet + xpath | “Código de serviço inválido… Corrigir no ERP e reemitir.” |
| 4 | XML_PARSE | NFSE/NFE | FATAL | documento inteiro | XML deve ser bem-formado e parseável | XML completo | “XML inválido… Verificar arquivo/cole o XML correto.” |
| 5 | NCM_PLACEHOLDER | NFSE/NFE | ALERT | NCM — /NFS-e/infNfse//NCM | Revisar NCM conforme classificação vigente | XML + snippet + xpath | “Revisar NCM… manter evidência de suporte.” |
| 6 | IBSCBS_MISSING | NFSE | FATAL | IBS/CBS — /NFS-e/infNfse//Valores | Tags IBS e CBS obrigatórias. Precisa informar o percentual e valor de cada tributo nas notas (CBS 0,10%, IBS 0,90%) | XML + xpath mostrando ausência | “IBS/CBS ausentes na nota. Informar alíquota e valor conforme LC 214.” |
| 7 | IBSCBS_CALC | NFSE | FATAL | ValorCBS/ValorIBS — /NFS-e/infNfse//ValorCBS, //ValorIBS | Cálculo IBS/CBS incorreto. ValorCBS = Base × 0,10%, ValorIBS = Base × 0,90%. Tolerância: R$ 0,01 | XML + snippet + cálculo esperado | “Cálculo CBS/IBS incorreto. Esperado R$ X, informado R$ Y. Corrigir valores.” |
| 8 | CEST_MISSING | NFSE | FATAL | CEST — /NFS-e/infNfse//CEST | CEST obrigatório conforme nova classificação. Muitos contribuintes não estão usando os códigos novos | XML + xpath mostrando ausência | “CEST ausente. Informar código CEST conforme nova classificação.” |
| 9 | CEST_FORMAT | NFSE | FATAL | CEST — /NFS-e/infNfse//CEST | CEST deve ter exatamente 7 dígitos (formato novo) | XML + snippet + xpath | “CEST inválido (esperado 7 dígitos). Verificar código atualizado.” |
| 10 | LAYOUT_PORTAL | NFSE | FATAL | Estrutura XML | Layout do documento deve seguir padrões do Portal Nacional de NFS-e (tags obrigatórias: Valores, Servico, PrestadorServico, TomadorServico) | XML completo | “Layout fora do padrão do Portal Nacional. Verificar estrutura do documento.” |

## 2) Paths/variações comuns

Atenção: NFS-e varia por provedor; abaixo consolidamos paths do motor atual + novos campos da reforma.

### CST
- XPath: `/NFS-e/infNfse//CST`
- Formato: 3 dígitos (ex: `090`)
- Snippet inválido: `<CST>12</CST>`

### cClassTrib (ClassTrib)
- XPath: `/NFS-e/infNfse//cClassTrib`
- Formato: 6 dígitos — verificar conforme categoria do negócio
- Snippet inválido: `<cClassTrib>1722</cClassTrib>` (apenas 4 dígitos)

### Código de Serviço
- XPath: `/NFS-e/infNfse//CodigoServico`
- Variações conhecidas: `CodigoServicoPrestado`, `ItemListaServico`, `cServ`, `codigoServico`
- Formato: 6 dígitos

### NCM
- XPath: `/NFS-e/infNfse//NCM`
- Severidade: ALERT (informativo — revisar classificação vigente)

### IBS / CBS (NOVO — reforma tributária)
- XPaths: `/NFS-e/infNfse//AliquotaIBS`, `//ValorIBS`, `//AliquotaCBS`, `//ValorCBS`
- Alíquotas de referência (período de teste): CBS 0,10% / IBS 0,90%
- Regra de cálculo: `Valor = BaseCalculo × Alíquota` (tolerância R$ 0,01)
- Base legal: LC 214 + LC 227 (13/jan/2026)

### CEST (NOVO — nova classificação)
- XPath: `/NFS-e/infNfse//CEST`
- Formato: 7 dígitos (ex: `2104900`)
- Muitos contribuintes ainda usam códigos antigos com menos dígitos
- Snippet inválido: `<CEST>21049</CEST>` (apenas 5 dígitos)

## 3) Exemplos anonimizados + gabarito

3 exemplos construídos pelo time de engenharia com base no feedback da contabilidade (21/03/2026):

| Exemplo | Arquivo | Cenário | Resultado |
|---------|---------|---------|-----------|
| A | `example_a.xml` | Consultoria R$ 10k — IBS/CBS ausentes, ClassTrib 4 dígitos, CEST ausente | **FAIL** (3 FATAL) |
| B | `example_b.xml` | Manutenção TI R$ 10k — CBS e IBS com cálculo errado, CEST 5 dígitos | **FAIL** (2 FATAL cálculo + 1 FATAL formato) |
| C | `example_c.xml` | Software R$ 25k — tudo correto, cálculos batendo | **PASS** (0 FATAL) |

Gabarito detalhado: `docs/sprints/discovery/examples/S6_Discovery_Examples.md`

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
- Top 10 regras atualizadas com feedback contabilidade (21/03/2026)
- 3 XMLs anonimizados + gabarito PASS/FAIL/ALERT completo
- Novas regras: IBSCBS_MISSING, IBSCBS_CALC, CEST_MISSING, CEST_FORMAT, LAYOUT_PORTAL
