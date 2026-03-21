# S7 — Exemplos anonimizados + gabarito (baseado no feedback Contabilidade 2026-03-21)

Objetivo: 3 exemplos anonimizados com gabarito (findings esperados) para evoluir o motor de validação.
Fonte: feedback do time de contabilidade recebido em 21/03/2026 (sem XMLs reais — exemplos construídos pelo time de engenharia).

## Checklist de anonimização
- Remover/mascarar CNPJ/CPF, razão social, nomes, endereços, inscrições, números internos e URLs sensíveis.
- Manter somente o necessário para reproduzir as regras (CST/cClassTrib/código serviço/NCM/CEST/IBS/CBS).
- Preferir trocar valores por *** ou hashes quando não forem usados por validação.

---

## Alíquotas de referência (período de teste — reforma tributária)

| Tributo | Alíquota | Base legal |
|---------|----------|------------|
| CBS     | 0,10%    | LC 214 + LC 227 (13/jan/2026) |
| IBS     | 0,90%    | LC 214 + LC 227 (13/jan/2026) |

---

## Exemplo A — FAIL (3 FATAL + 1 ALERT)

- **Arquivo:** `example_a.xml`
- **Contexto:** NFS-e de consultoria empresarial, R$ 10.000,00. Emitida sem considerar a reforma tributária — sem campos IBS/CBS, ClassTrib incompleto, CEST ausente.

### Gabarito de findings

| # | rule_id | Sev | Campo | Resultado | Motivo |
|---|---------|-----|-------|-----------|--------|
| 1 | IBSCBS_MISSING | FATAL | IBS/CBS | **FAIL** | Tags `<ValorCBS>`, `<ValorIBS>`, `<AliquotaCBS>`, `<AliquotaIBS>` ausentes. Obrigatório informar percentual e valor de cada tributo conforme LC 214. |
| 2 | CCLASSTRIB_6_DIGITS | FATAL | cClassTrib | **FAIL** | Valor `1722` tem 4 dígitos — esperado exatamente 6 dígitos. |
| 3 | CEST_MISSING | FATAL | CEST | **FAIL** | Tag `<CEST>` ausente. Código CEST obrigatório conforme nova classificação. |
| 4 | CST_3_DIGITS | — | CST | **PASS** | Valor `090` tem 3 dígitos — correto. |
| 5 | SERVICE_CODE_6_DIGITS | — | CodigoServico | **PASS** | Valor `172201` tem 6 dígitos — correto. |
| 6 | NCM_PLACEHOLDER | ALERT | NCM | **ALERT** | NCM `84713012` presente — revisar classificação vigente. |

**Evidência mínima por finding:**
- IBSCBS_MISSING: XML completo + xpath `/NFS-e/infNfse//Valores` mostrando ausência das tags
- CCLASSTRIB_6_DIGITS: snippet `<cClassTrib>1722</cClassTrib>` + xpath `/NFS-e/infNfse//cClassTrib`
- CEST_MISSING: XML completo + xpath `/NFS-e/infNfse//Servico` mostrando ausência da tag

---

## Exemplo B — FAIL (2 FATAL + 1 ALERT)

- **Arquivo:** `example_b.xml`
- **Contexto:** NFS-e de manutenção de TI, R$ 10.000,00. Campos IBS/CBS presentes mas com cálculo incorreto. CEST presente mas formato antigo.

### Gabarito de findings

| # | rule_id | Sev | Campo | Resultado | Motivo |
|---|---------|-----|-------|-----------|--------|
| 1 | IBSCBS_CALC | FATAL | ValorCBS | **FAIL** | CBS informado R$ 15,00 — esperado R$ 10,00 (0,10% × R$ 10.000,00). Diferença de R$ 5,00. |
| 2 | IBSCBS_CALC | FATAL | ValorIBS | **FAIL** | IBS informado R$ 50,00 — esperado R$ 90,00 (0,90% × R$ 10.000,00). Diferença de R$ 40,00. |
| 3 | CEST_FORMAT | FATAL | CEST | **FAIL** | Valor `21049` tem 5 dígitos — esperado 7 dígitos (formato novo). |
| 4 | CST_3_DIGITS | — | CST | **PASS** | Valor `090` — correto. |
| 5 | CCLASSTRIB_6_DIGITS | — | cClassTrib | **PASS** | Valor `140501` — correto. |
| 6 | SERVICE_CODE_6_DIGITS | — | CodigoServico | **PASS** | Valor `140501` — correto. |
| 7 | NCM_PLACEHOLDER | ALERT | NCM | **ALERT** | NCM `84714900` presente — revisar classificação vigente. |

**Evidência mínima por finding:**
- IBSCBS_CALC (CBS): snippet `<ValorCBS>15.00</ValorCBS>` + xpath `/NFS-e/infNfse//ValorCBS` + cálculo esperado
- IBSCBS_CALC (IBS): snippet `<ValorIBS>50.00</ValorIBS>` + xpath `/NFS-e/infNfse//ValorIBS` + cálculo esperado
- CEST_FORMAT: snippet `<CEST>21049</CEST>` + xpath `/NFS-e/infNfse//CEST`

---

## Exemplo C — PASS (0 FATAL, 1 ALERT informativo)

- **Arquivo:** `example_c.xml`
- **Contexto:** NFS-e de desenvolvimento de software, R$ 25.000,00. Todos os campos corretos, cálculos batendo, layout completo conforme Portal Nacional.

### Gabarito de findings

| # | rule_id | Sev | Campo | Resultado | Motivo |
|---|---------|-----|-------|-----------|--------|
| 1 | IBSCBS_MISSING | — | IBS/CBS | **PASS** | Tags presentes com alíquota e valor. |
| 2 | IBSCBS_CALC | — | ValorCBS | **PASS** | CBS R$ 25,00 = 0,10% × R$ 25.000,00 ✓ |
| 3 | IBSCBS_CALC | — | ValorIBS | **PASS** | IBS R$ 225,00 = 0,90% × R$ 25.000,00 ✓ |
| 4 | CST_3_DIGITS | — | CST | **PASS** | Valor `090` — correto. |
| 5 | CCLASSTRIB_6_DIGITS | — | cClassTrib | **PASS** | Valor `140101` — correto. |
| 6 | SERVICE_CODE_6_DIGITS | — | CodigoServico | **PASS** | Valor `140101` — correto. |
| 7 | CEST_FORMAT | — | CEST | **PASS** | Valor `2104900` — 7 dígitos, correto. |
| 8 | NCM_PLACEHOLDER | ALERT | NCM | **ALERT** | NCM `84713012` presente — revisar classificação vigente (informativo). |

**Evidência mínima:** Nenhum finding FATAL — relatório auditável mostra conformidade total.

---

## Modelo de relatório auditável (formato solicitado pela contabilidade)

### Tabela de Nota (visão por documento)

| NF | BASE ICMS | VALOR ICMS | IBS | CBS | CEST | CLASSTRIB | Resultado |
|----|-----------|------------|-----|-----|------|-----------|-----------|
| Ex. A (000000001) | 10.000,00 | — | — | — | — | 1722 | **FAIL** |
| Ex. B (000000042) | 10.000,00 | — | 50,00 | 15,00 | 21049 | 140501 | **FAIL** |
| Ex. C (000000099) | 25.000,00 | — | 225,00 | 25,00 | 2104900 | 140101 | **PASS** |

### Tabela de Validação (visão por regra)

| Validação | Inputs necessários | Regra | Severidade | Evidência mínima | Saída esperada |
|-----------|--------------------|-------|------------|-------------------|----------------|
| IBS/CBS presentes | Tags IBS/CBS no XML | Campos obrigatórios conforme LC 214 | FATAL | XML + xpath | PASS se presentes, FAIL se ausentes |
| Cálculo IBS/CBS correto | BaseCalculo, AliquotaCBS (0,10%), AliquotaIBS (0,90%) | Valor = Base × Alíquota (tolerância R$ 0,01) | FATAL | Snippet com valores + cálculo esperado | PASS se dentro da tolerância |
| ClassTrib válido | cClassTrib | Exatamente 6 dígitos, conforme categoria do negócio | FATAL | Snippet + xpath | PASS se 6 dígitos |
| CEST válido | CEST | Presente e com 7 dígitos (classificação nova) | FATAL | Snippet + xpath | PASS se presente e 7 dígitos |
| Layout do documento | Estrutura XML | Conforme padrões do Portal Nacional de NFS-e | FATAL | XML completo | PASS se bem-formado |
| CST válido | CST | Exatamente 3 dígitos | FATAL | Snippet + xpath | PASS se 3 dígitos |
| Código de serviço | CodigoServico | Exatamente 6 dígitos | FATAL | Snippet + xpath | PASS se 6 dígitos |
| NCM (revisão) | NCM | Revisar classificação fiscal vigente | ALERT | Snippet + xpath | ALERT informativo |

---

## Vocabulário fiscal (padronizado com contabilidade)

| Termo | Significado |
|-------|-------------|
| CEST | Classificação principal |
| ClassTrib | Nova classificação conforme reforma |
| IBS | Imposto sobre Bens e Serviços (novo — estadual/municipal) |
| CBS | Contribuição sobre Bens e Serviços (novo — federal) |
| Nota Nacional | Nota de serviço emitida no portal nacional |
| ISS | Imposto sobre o serviço |
| ICMS | Imposto dos produtos |
| Split Payment | Novo modo de crédito do governo |
| Cashback | Retorno do imposto pago ao consumidor |
