---
name: S7 Accounting Team Feedback
description: Requisitos do time de contabilidade para validações fiscais, relatório auditável e exemplos — recebido em 2026-03-21
type: project
---

## Top 5 Validações priorizadas pelo time de contabilidade

1. **Falta IBS e CBS** — precisa informar o percentual de cada um nas notas
2. **Cálculo IBS/CBS incorreto** — alíquotas de 0,10% (CBS) e 0,90% (IBS) precisam aparecer conforme montante da nota
3. **Código ClassTrib incorreto** — verificar conforme categoria do negócio
4. **CEST incorreto** — códigos novos da classificação, muitos contribuintes não estão usando
5. **Layout do documento incorreto** — de acordo com padrões do portal nacional de NFS-e

**Why:** Estas são as validações que o time de contabilidade considera mais urgentes e frequentes no dia a dia. Veio diretamente dos stakeholders de domínio.

**How to apply:** Usar como base para issue #34 (Top 10 rules phase 1). Cada regra precisa ser determinística com evidência auditável no formato Findings/Evidence v1.1.

## Formato de relatório auditável solicitado

**Tabela de validação:**
- Validação → Inputs necessários → Regra → Severidade → Evidência mínima → Saída esperada

**Colunas do relatório de nota:**
- NF | BASE ICMS | VALOR ICMS | IBS | CBS | CEST | CLASSTRIB

**Exemplos:** Querem 3 documentos anonimizados com gabarito PASS/FAIL/ALERTA — preferem exemplos do dia a dia de trabalho real.

**Prazo sugerido pelo time:** 48-72h para o modelo de relatório (texto simples).

## Alíquotas de referência informadas
- CBS: 0,10%
- IBS: 0,90%
- (Estes são valores do período de teste/transição da reforma)
