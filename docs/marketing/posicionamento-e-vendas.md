# Instruções de Marketing & Vendas — Tribultz (RASCUNHO)

> **Princípio inegociável:** vender **só o que o produto entrega e gateia**. Cada
> promessa de tier paga tem de bater com um gate **real** no código (server-side).
> O prospecto deste mercado testa antes de assinar — blefe descoberto = venda
> perdida + credibilidade perdida. Esta régua só é válida a partir do PR #384
> (gate de export server-side); antes dele, PDF/evidência eram entregues de graça.

## 1. A régua: grátis (ativação) × pago (conversão)

| | Entregue | Papel no funil |
|---|---|---|
| **Grátis (trial)** | Evidência **on-screen**: findings, severidade, **base legal** (LC citada), recomendação, evidência de fonte | **Ativação** — o prospecto *vê* funcionar e confia |
| **Pago** | **Exportar o artefato auditável (PDF)** + volume + lote + multi-CNPJ + API + dashboard | **Conversão** — o entregável que vai pro contador/auditor/fisco |

Mensagem-mãe: **"Veja de graça que sua NF-e está certa. Pague para ter o documento auditável que comprova."**

## 2. O que cada tier realmente entrega (fonte: `frontend/src/lib/plan.ts`)

| Tier | Preço | Validações | Export PDF auditável | Lote | Multi-CNPJ | API | Dashboard |
|------|-------|-----------|:---:|:---:|:---:|:---:|:---:|
| **Trial** | grátis (3 dias) | 5 (total) | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Starter** | R$ 49,90/mês | 10/mês | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Profissional** ⭐ | R$ 149/mês | 500/mês | ✅ | ✅ | ❌ | ✅ | ✅ |
| **Empresarial** | R$ 249/mês | 2.000/mês | ✅ | ✅ | ✅ (até 10 CNPJs) | ✅ | ✅ |
| **Contador** | R$ 349/mês | ilimitadas | ✅ | ✅ | ✅ | ✅ | ✅ |

**Fato comercial que marketing PRECISA respeitar:** o **export auditável (PDF) começa no Profissional**. Starter é "on-screen + dashboard + mais volume" — **não** exporta. A alavanca do artefato é o salto Starter→Profissional.

## 3. Ganchos de conversão reais (por que assinar)

1. **O artefato auditável (PDF)** — o documento com base legal que se entrega ao contador, anexa numa defesa de autuação ou arquiva como prova de compliance. Só no Profissional+. **Esta é a alavanca principal.**
2. **Volume / continuidade** — 5 (trial) → 10 → 500 → 2.000 → ilimitado. Quem valida NF-e recorrentemente estoura a cota rápido.
3. **Lote** (validação em massa) — Profissional+.
4. **Multi-CNPJ (filiais)** — Empresarial (até 10) e Contador.
5. **API** — integração ao ERP/automação — Profissional+.

## 4. Mensagens por persona

- **Empresa pequena / emissor avulso (→ Starter/Profissional):** "Evite a Rejeição 1024 e as penalidades de ago/2026. Teste grátis; quando precisar do laudo auditável, assine."
- **Empresa com volume / filiais (→ Empresarial):** "Valide em lote, até 10 CNPJs, com relatório auditável e API pro seu ERP."
- **Contador / escritório (→ Contador):** "Validações ilimitadas, multi-CNPJ, justificativa técnica por finding e API — a ferramenta da sua carteira de clientes."

## 5. Guardrails para a máquina de vendas (GPT) — OBRIGATÓRIO

**NUNCA:**
- Prometer feature que não tem gate real (a régua acima é a fonte da verdade).
- Dizer que **Starter** exporta PDF/relatório auditável — **não exporta**.
- Inventar número de regras/códigos. Use os reais do produto (`RULES_COUNT`, `CLASSTRIB_COUNT`) — e não cite valor fixo que pode envelhecer.
- Dar conselho fiscal/jurídico definitivo. A Tribultz **valida e evidencia**; a decisão é do contribuinte/contador.

**SEMPRE:**
- Vender a **evidência on-screen como prova grátis** (CTA: "teste e veja") e o **export auditável como o motivo de assinar**.
- Ancorar urgência nos fatos do domínio já públicos no site: **Rejeição 1024** (erro CST × cClassTrib) e **penalidades CBS/IBS a partir de ago/2026** (fim do período pedagógico).
- Ser honesto sobre limites: cota de validações é o limitador real do trial (5) e dos planos.
- Direcionar a dúvida fiscal específica ao WhatsApp (lead `generate_lead`) — ver [[utm-conventions]] para marcar a origem.

## 6. Atribuição (fechar o loop com o GA4)
Todo link de campanha usa UTMs ([[utm-conventions]]). Os eventos do funil
(`generate_lead` → `sign_up` → `begin_checkout` → `purchase`) já estão
instrumentados, então marketing consegue medir **conversão e receita por canal**
— a base para decidir onde investir.

---

### Decisões que peço confirmação antes de finalizar
1. **Salto Starter→Profissional (3×) para liberar export** — manter, ou criar um tier intermediário / permitir X exports/mês no Starter como gancho?
2. **Tom de urgência** (Rejeição 1024 / ago/2026) — quão agressivo? Hoje o site já usa.
3. Público-alvo primário para a copy inicial: **empresas** ou **contadores**?
