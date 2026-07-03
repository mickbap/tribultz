> ⚠️ **DEPRECATED (02/07/2026)** — este arquivo não recebe mais atualizações.
> A fonte canônica agora é o tribultz-brain: [knowledge/marketing/posicionamento-e-vendas.md](https://github.com/mickbap/tribultz-brain/blob/main/knowledge/marketing/posicionamento-e-vendas.md).
> Mantido temporariamente na etapa 1 da migração (RFC-0001); remoção em etapa futura.

# Instruções de Marketing & Vendas — Tribultz

> **Decisões cravadas (29/06/2026):** público primário = **empresa que emite**
> (âncora); tom = **agressivo/deadline** (Rejeição 1024 + penalidades ago-2026);
> export auditável = **gate pago a partir do Profissional** (mantido, #384).
> Contador é público **secundário** (expansão), não a âncora da copy.

> **Princípio inegociável:** vender **só o que o produto entrega e gateia**. Cada
> promessa de tier paga bate com um gate **real** no código (server-side, #384).
> O prospecto testa antes de assinar — blefe descoberto = venda + credibilidade
> perdidas.

## 1. Posicionamento (âncora: empresa emissora)

**Quem é o alvo:** empresa que **emite** NF-e/NFS-e/NFC-e e tem medo concreto de
**Rejeição 1024** (CST × cClassTrib incompatível) e das **penalidades CBS/IBS a
partir de agosto/2026** (fim do período pedagógico).

**Mensagem-mãe:**
> **"Sua NF-e vai ser rejeitada — e a partir de agosto/2026 isso vira multa. Veja de graça onde está o erro. Tenha o laudo auditável que comprova a correção."**

A primeira frase vende o **risco** (agressivo), a segunda a **prova grátis**
(ativação), a terceira o **artefato pago** (conversão).

## 2. A régua: grátis (ativação) × pago (conversão)

| | Entregue | Papel no funil |
|---|---|---|
| **Grátis (trial)** | Evidência **on-screen**: findings, severidade, **base legal** (LC citada), recomendação, evidência de fonte | **Ativação** — o emissor *vê* o erro e o risco |
| **Pago** | **Exportar o laudo auditável (PDF)** + volume + lote + multi-CNPJ + API + dashboard | **Conversão** — o documento que comprova/defende perante o fisco |

## 3. O que cada tier entrega (fonte: `frontend/src/lib/plan.ts` + gate #384)

| Tier | Preço | Validações | Export PDF | Lote | Multi-CNPJ | API | Dashboard |
|------|-------|-----------|:---:|:---:|:---:|:---:|:---:|
| **Trial** | grátis (3 dias) | 5 (total) | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Starter** | R$ 49,90/mês | 10/mês | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Profissional** ⭐ | R$ 149/mês | 500/mês | ✅ | ✅ | ❌ | ✅ | ✅ |
| **Empresarial** | R$ 249/mês | 2.000/mês | ✅ | ✅ | ✅ (até 10 CNPJs) | ✅ | ✅ |
| **Contador** | R$ 349/mês | ilimitadas | ✅ | ✅ | ✅ | ✅ | ✅ |

**Fato comercial inviolável na copy:** o **export auditável (PDF) começa no
Profissional**. **Starter NÃO exporta** — é "veja na tela + dashboard + mais
volume". A alavanca do laudo é o salto **Starter → Profissional**.

## 4. Funil de conversão (empresa emissora)

1. **Topo (medo):** anúncio/landing martela Rejeição 1024 + deadline ago-2026.
2. **Ativação (prova grátis):** trial mostra o erro na tela com a LC citada — "está vendo? sua nota tem isto."
3. **Conversão (o laudo):** "para corrigir com segurança e ter o **documento auditável** que comprova, assine o **Profissional**." O artefato é o gancho — e agora é pago de verdade.
4. **Expansão:** volume (estoura a cota) → upgrade; filiais → Empresarial; escritório/carteira → Contador.

## 5. Mensagens por persona (ordem de prioridade)

1. **Empresa emissora avulsa/pequena (PRIMÁRIA → Profissional):**
   "Pare de tomar Rejeição 1024. Valide grátis, corrija e **baixe o laudo auditável** antes que a multa de ago/2026 chegue."
2. **Empresa com volume / filiais (→ Empresarial):**
   "Valide em lote, até 10 CNPJs, laudo auditável e API pro seu ERP — compliance de CBS/IBS em escala."
3. **Contador / escritório (SECUNDÁRIA → Contador):**
   "Blinde sua carteira: validações ilimitadas, multi-CNPJ, justificativa técnica por finding e API." *(expansão, não a âncora da campanha inicial)*

## 6. Tom: agressivo / deadline (guia de escrita)

- **Liderar com risco concreto:** "Rejeição 1024", "multa a partir de ago/2026", "fim do período pedagógico".
- **Contador regressivo / prazo** é aceitável (ago-2026 é fato público, já usado no site).
- **Verbos diretos:** "Pare de…", "Evite a multa", "Não emita no escuro".
- **Limite ético:** urgência é sobre **fato regulatório real**, nunca FUD inventado. Não prometer imunidade a multa — prometer **evidência e laudo** que sustentam a correção.

## 7. Guardrails para a máquina de vendas (GPT) — OBRIGATÓRIO

**NUNCA:**
- Prometer feature sem gate real (a régua da seção 3 é a fonte da verdade).
- Dizer que **Starter** exporta PDF/laudo — **não exporta**.
- Inventar nº de regras/códigos — usar os reais do produto (`RULES_COUNT`, `CLASSTRIB_COUNT`), sem cravar valor que envelhece.
- Dar conselho fiscal/jurídico definitivo nem **prometer que elimina multa**. A Tribultz **valida e evidencia**; a decisão é do contribuinte/contador.

**SEMPRE:**
- Vender **on-screen = prova grátis** ("teste e veja o erro") e **export = motivo de assinar** (o laudo auditável).
- Ancorar urgência em **Rejeição 1024** e **penalidades ago-2026** (fatos do site).
- Ser honesto sobre limites: a **cota de validações** é o limitador real (trial = 5).
- Mandar dúvida fiscal específica pro **WhatsApp** (evento `generate_lead`) com UTM ([[utm-conventions]]).

## 8. Atribuição — fechar o loop (GA4)
Todo link de campanha usa UTMs ([[utm-conventions]]). Os eventos do funil
(`generate_lead` → `sign_up` → `begin_checkout` → `purchase`) estão
instrumentados (#379/#380), então marketing mede **conversão e receita por
canal** — base para realocar verba. KPI-âncora: **CAC por canal × receita
(`purchase`)**.
