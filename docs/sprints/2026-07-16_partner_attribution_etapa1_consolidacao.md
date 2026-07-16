# Programa de Parceiros — Etapa 1: Consolidação do modelo atual

Data: 2026-07-16
Escopo: validar e documentar o fluxo de Partner Attribution já existente (RFC-0025). **Nenhuma alteração funcional.**

## Fluxo validado no código

| Item | Onde vive | Confirmado |
|---|---|---|
| `partner_code` | `backend/app/models/partner.py` — `Partner.code`, único, `normalize_partner_code()` valida `^[A-Z0-9_-]{3,32}$`, sempre uppercase | ✅ |
| Partner Attribution (entidade) | `Partner` model — `id, type, name, company, email, phone, code, status, notes, created_at, updated_at`. Tipos: `lawyer, accountant, consultancy, erp, association, influencer, other` | ✅ |
| Relacionamento Partner → Tenant | `tenants.partner_id` (FK opcional, nunca obrigatória) — migration `2026_07_08_0024_add_partners.py` | ✅ |
| Captura automática por URL | `frontend/src/app/register/page.tsx` — lê `?partner=`/`?ref=` no `useEffect` client-side, normaliza uppercase | ✅ |
| Persistência do vínculo | Gravado em `tenants.partner_id` na criação/reuso do Tenant por CNPJ no `/register`. Código inválido/inativo não bloqueia cadastro (segue sem vínculo) | ✅ |
| CRUD admin | `backend/app/routers/admin.py` — `GET/POST /partners`, `PATCH /partners/{id}`, `POST /partners/{id}/active` (desativar, nunca apagar) | ✅ |
| Visualização Command Center | `/admin/tenants` — coluna Parceiro + filtro (`frontend/src/app/admin/tenants/page.tsx`) | ✅ |
| Testes | `test_partner_code.py` (4), `test_partner_admin.py` (5) — normalização, catálogo, status, CRUD, captura | ✅ |

**Critério de aceite do RFC-0025** ("cadastrar um Partner · gerar código · acessar `/register` com esse código · criar Tenant vinculado · ver origem em `/admin/tenants` · preservar por todo o ciclo de vida"): **atendido integralmente pelo código atual**, sem necessidade de nenhuma mudança nesta etapa.

## Guardrails ativos hoje (RFC-0025 + `claims.md`, tribultz-brain)

- Partner é **exclusivamente origem comercial** — nunca comissão, contrato ou financeiro (docstring do model, linha 3-5, cita o guardrail explicitamente).
- RFC-0025 lista como **fora de escopo**: Programa de Parceiros, Portal do Parceiro, Comissão, Financeiro, Ranking, Dashboard do parceiro, Pagamentos, Gamificação, Automação de indicação.
- `claims.md` (marketing): nunca comunicar a proveniência como "comissão, contrato, financeiro, programa de parceiros ou portal".

O modelo atual **não tem nenhum campo** de comissão/financeiro — confirma o guardrail sendo respeitado à risca no código, não só na documentação.

## Nota

RFC-0025 também registra, nos princípios arquiteturais, que este modelo foi desenhado para **"crescer naturalmente para Programa de Parceiros, Portal, Comissão... sem quebra estrutural"** — ou seja, a evolução pedida nas próximas etapas é compatível com a arquitetura, mas ainda não foi autorizada formalmente (o RFC segue com status `proposed` e o guardrail de "fora de escopo" continua ativo). Ver discussão em andamento antes de iniciar Etapa 2 em diante.
