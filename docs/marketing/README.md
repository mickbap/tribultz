# Material de Marketing — Tribultz

Ponto de entrada único do material de aquisição/vendas. Tudo aqui é coerente com
o produto **real** (gates server-side, #384) e com as decisões cravadas em
29/06/2026: **público primário = empresa que emite**, **tom agressivo/deadline**,
**export auditável pago a partir do Profissional**.

## Índice

| Documento | O que é |
|-----------|---------|
| [posicionamento-e-vendas.md](posicionamento-e-vendas.md) | **Fonte da verdade** de posicionamento: régua grátis×pago, tiers, personas, guardrails, KPIs |
| [system-prompt-gpt-vendas.md](system-prompt-gpt-vendas.md) | System prompt (markdown) para colar no GPT de vendas |
| [copy/landing-hero.md](copy/landing-hero.md) | Headlines, sub, benefícios e CTAs da landing |
| [copy/anuncios.md](copy/anuncios.md) | Variações Google Ads (RSA) e Meta |
| [copy/email-whatsapp.md](copy/email-whatsapp.md) | Sequências de e-mail e mensagens de WhatsApp |
| [../analytics/utm-conventions.md](../analytics/utm-conventions.md) | Padrão de UTMs (atribuição por canal) |

## A régua, em uma linha
**Veja de graça que sua NF-e está certa (on-screen). Pague para ter o laudo auditável que comprova (Profissional+).**

## Fontes canônicas (não inventar/divergir)
- **Preços e o que cada plano entrega:** site `tribultz.com.br` + `frontend/src/lib/plan.ts`.
- **Gate de export:** `require_plan` no backend (#384) — export = Profissional+.
- **Nº de regras/códigos:** valores reais do produto (`RULES_COUNT`, `CLASSTRIB_COUNT`) — nunca cravar número fixo na copy.

## Guardrails (valem para toda peça e para o GPT)
- ❌ Nunca prometer imunidade/eliminação de multa → ✅ "evidência e laudo que **sustentam** a correção".
- ❌ Nunca dizer que **Starter exporta** o laudo → exporta só Profissional+.
- ❌ Não dar parecer fiscal/jurídico definitivo → encaminhar caso específico ao **WhatsApp** do time.
- ❌ Não inventar números/casos/descontos.

## Medição (fecha o loop)
Funil instrumentado no GA4: `generate_lead` → `sign_up` → `begin_checkout` →
`purchase` (#379/#380). Toda campanha usa UTMs. **KPI-âncora: CAC por canal ×
receita (`purchase`).**

## Como usar
1. Leia o **posicionamento** (contexto e limites).
2. Pegue a **copy** do canal que vai rodar; marque os links com **UTM**.
3. Para o atendimento automatizado, cole o **system prompt** no GPT de vendas.
4. Acompanhe conversão/receita por canal no GA4 e realoque verba.
