# Diff Regulamentos IBS/CBS 30/abr/2026 × Regras Tribultz

**Fontes analisadas:**
- Regulamento do IBS — publicado 30/abr/2026 (Comitê Gestor do IBS)
- Regulamento da CBS — publicado 30/abr/2026 (Receita Federal)
- LC 214/2025 + LC 227/2026 (base legal)
- NT 2025.002-RTC (especificação XML NF-e)

**Implementações auditadas:**
- `frontend/src/lib/validation/xmlRules.ts`
- `backend/app/crews/tools/validate_ibscbs_rules_tool.py`
- `backend/app/crews/tools/parse_nfe_xml_tool.py` (CST_TABLE)

**Auditado em:** 2026-05-31
**Autor:** Tribultz Techlead

---

## Tabela REGRA × STATUS

| # | ID da Regra | Implementada | Status | Impacto | Observação |
|---|---|---|---|---|---|
| 1 | `XML_PARSE` | ✅ | **OK** | — | XML válido e parseável. Sem alteração nos regulamentos. |
| 2 | `CST_3_DIGITS` | ✅ | **OK** | — | Formato CST 3 dígitos confirmado na NT 2025.002 e regulamentos. |
| 3 | `CCLASSTRIB_6_DIGITS` | ✅ | **OK** | — | Formato cClassTrib 6 dígitos inalterado. Tabela atualizada via PR #274 (migration 0018). |
| 4 | `SERVICE_CODE_6_DIGITS` | ✅ | **OK** | — | NFS-e: código de serviço sem alteração. |
| 5 | `CST_VALID` | ✅ | **OK** | — | 14 CSTs da NT 2025.002-RTC confirmados nos regulamentos (000, 001, 002, 070, 200, 410, 510, 515, 550, 620, 800, 810, 811, 830). Sem CSTs novos. |
| 6 | `CST_GROUP_MATCH` | ✅ | **OK** | — | Mapeamento CST ↔ grupo XML (gIBSCBS, gIBSCBSMono, gTransfCred, gAjusteCompet, gEstornoCred) confirmado pelos regulamentos. |
| 7 | `CST_SEMANTIC` | ✅ | **OK** | — | CST 070 (imunidade/isenção) e 410 (suspensão) sem valor tributário: confirmado e reforçado. |
| 8 | `IBSCBS_MISSING` | ✅ | **OK** | — | Grupo `<IBSCBS>` obrigatório para todos os CSTs de 000–550. Mantido. |
| 9 | `IBSCBS_CALC` | ✅ | **OK parcial** | Baixo | Cálculo `vCBS = vBC × pCBS` correto. Regulamento CBS art. 12 especifica que vBC deve incluir ICMS destacado para bens na transição 2026 — nossa regra valida o cálculo sem verificar a composição do vBC. Ver issue filha #276. |
| 10 | `IBSCBS_UF_CALC` | ✅ | **OK** | — | `vIBSUF = vBC × pIBSUF`: regulamento IBS cap. 4 confirma. |
| 11 | `IBSCBS_MUN_CALC` | ✅ | **OK** | — | `vIBSMun = vBC × pIBSMun`: regulamento IBS cap. 4 confirma. |
| 12 | `IBSCBS_SPLIT` | ✅ | **OK** | — | `vIBS = vIBSUF + vIBSMun`: estrutural, confirmado. |
| 13 | `IBSCBS_TOTAL` | ✅ | **OK** | — | Totais = soma dos itens: estrutural, confirmado. |
| 14 | `CEST_MISSING` | ✅ | **🔴 UPDATE** | **Alto** | **False positive crítico.** CEST é campo do grupo `<prod>`, obrigatório apenas para produtos com substituição tributária (ST). Nossa regra dispara para TODOS os produtos, gerando falsos positivos que bloqueiam emissões legítimas. Corrigido para `WARNING` neste PR. Ver issue filha #275. |
| 15 | `CEST_FORMAT` | ✅ | **OK** | — | 7 dígitos: formato inalterado. |
| 16 | `LAYOUT_PORTAL` | ✅ | **OK** | — | NFS-e Nacional: sem alteração nas obrigações acessórias da reforma. |
| 17 | `LAYOUT_NFE` | ✅ | **OK** | — | NF-e: estrutura `emit + det + total` confirmada. |
| 18 | `NCM_PLACEHOLDER` | ✅ | **OK** | — | Advisory de revisão NCM: mantido como ALERT. |
| 19 | `BENEFITS_PLACEHOLDER` | ✅ | **OK** | — | Advisory de créditos e benefícios: mantido como ALERT. |
| — | **Split Payment `indPag`** | ❌ | **🆕 NOVA** | **Alto** | Regulamento IBS cap. 5: para operações sujeitas ao split payment automático (Pix, TED, cartão), a NF-e deve conter `indPag=3` ou `indPag=4`. Atualmente não validamos. Issue filha #277. |
| — | **Monofásico downstream** | ❌ | **🆕 NOVA** | **Médio** | CST 620 (monofásico): distribuidores downstream devem emitir com `vCBS=0` e `vIBS=0`. Atual `CST_SEMANTIC` só verifica 070/410. Issue filha #278. |
| — | **Alíquota × cClassTrib** | ❌ | **🆕 NOVA** | **Médio** | Validar se `pCBS` e `pIBSUF+pIBSMun` correspondem às alíquotas esperadas para o `cClassTrib` declarado (cross-reference com tabela SVRS). Issue filha #279. |
| — | **Cashback (PF)** | ❌ | **📋 BACKLOG** | Baixo | Regulamento cashback: NF-e emitida para pessoa física deve sinalizar elegibilidade ao cashback. Baixa urgência até 2027. |
| — | **Composição vBC (ICMS-in)** | ❌ | **📋 BACKLOG** | Baixo | vBC deve incluir ICMS destacado na transição 2026. Requer leitura do `vICMS` do XML para verificar inclusão. Alta complexidade, baixo impacto imediato. |

---

## Resumo executivo

### Regras atuais: 19 implementadas

| Status | Quantidade | Regras |
|---|---|---|
| ✅ OK | 16 | XML_PARSE, CST_3_DIGITS, CCLASSTRIB_6_DIGITS, SERVICE_CODE_6_DIGITS, CST_VALID, CST_GROUP_MATCH, CST_SEMANTIC, IBSCBS_MISSING, IBSCBS_CALC, IBSCBS_UF_CALC, IBSCBS_MUN_CALC, IBSCBS_SPLIT, IBSCBS_TOTAL, CEST_FORMAT, LAYOUT_PORTAL, LAYOUT_NFE |
| 🔴 UPDATE | 1 | CEST_MISSING (false positive → downgrade para WARNING) |
| ✅ OK parcial | 1 | IBSCBS_CALC (cálculo correto, composição vBC não validada) |
| ✅ ALERT | 2 | NCM_PLACEHOLDER, BENEFITS_PLACEHOLDER |

### Novas regras necessárias (issues filhas abertas)

| Issue | Regra | Prioridade | Sprints |
|---|---|---|---|
| #275 | `CEST_MISSING` — escopo correto (só ST) | Alta | Imediato |
| #277 | `SPLIT_PAYMENT_INDPAG` | Alta | Próximo sprint |
| #278 | `MONOFASICO_ZERO` (CST 620 downstream) | Média | Próximo sprint |
| #279 | `ALIQUOTA_CLASSTRIB` (cross-reference pCBS × cClassTrib) | Média | Sprint seguinte |
| #276 | `VBC_ICMS_COMPOSICAO` | Baixa | Backlog |

### Conclusão

**O motor atual está estruturalmente correto** para o período 2026. Nenhuma regra existente produz falso negativo crítico (deixar passar erros reais). O único falso positivo de impacto é o `CEST_MISSING` em FATAL — afeta produtos não-ST que emitem sem CEST legitimamente.

As novas regras do Regulamento de 30/abr/2026 mais impactantes (`indPag` para split payment e `vCBS=0` para monofásico downstream) não estão implementadas e podem causar conformidade silenciosa incorreta para esses casos específicos.

**Recomendação de prioridade:**
1. Corrigir `CEST_MISSING` (FATAL→WARNING) — imediato, evita bloqueio de NF-e legítimas
2. Implementar `SPLIT_PAYMENT_INDPAG` — split payment obrigatório a partir de 2027
3. Implementar `MONOFASICO_ZERO` — monofásico já ativo em 2026

---

*Este documento deve ser atualizado a cada publicação de nota técnica (NT) ou regulamento complementar pelo Comitê Gestor do IBS ou Receita Federal.*
