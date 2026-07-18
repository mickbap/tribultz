# Repriorização Estratégica do Backlog de Produto

Data: 2026-07-18
Contexto: Ordem Técnica "Repriorização Estratégica do Backlog de Produto". Reclassifica as 31 Issues abertas em `mickbap/tribultz`, substituindo o critério predominantemente arquitetural/técnico de priorização por um critério orientado a valor entregue ao cliente — preservando a governança técnica já institucionalizada (Auditoria Arquitetural + Auditoria Contínua de Dependências).

## 1. Onde vive cada peça

| Entrega | Onde vive |
|---|---|
| Matriz de pontuação (6 critérios, 31 issues, evidência por linha) | [`backlog-priority-matrix.md`](https://github.com/mickbap/tribultz-brain/blob/main/knowledge/product/backlog-priority-matrix.md) (Brain) |
| Roadmap por horizonte (curto/médio/longo + contínuo + bloqueado) | [`roadmap.md`](https://github.com/mickbap/tribultz-brain/blob/main/knowledge/product/roadmap.md) (Brain) |
| Critérios permanentes + cadência de revisão (mensal/trimestral) | [`backlog-governance.md`](https://github.com/mickbap/tribultz-brain/blob/main/knowledge/process/backlog-governance.md) (Brain) |
| Reclassificação real (labels + fechamento) | [tribultz-brain#7](https://github.com/mickbap/tribultz-brain/pull/7) (governança) + as 28 issues abertas em `mickbap/tribultz` (execução, já aplicada) |

## 2. Mudança de fundo

O esquema P0–P3 anterior misturava **urgência técnica/de risco** com **prioridade de produto**. No esquema novo:

- **P0 — Valor imediato**: aumenta valor percebido, reduz tempo do usuário, aumenta conversão, ou fortalece diferencial competitivo de forma direta.
- **P1 — Evolução do Produto**: nova capacidade relevante, incluindo discovery.
- **P2 — Plataforma**: infra, segurança, observabilidade, performance, atualizações — **mesmo quando o risco técnico é alto**.
- **P3 — Dívida Técnica**: refatoração, cosmético, sem impacto direto no usuário.

Consequência direta: itens que eram **P0 por urgência de risco** (ex.: `#446` classtrib-sync sem alerta, `#447` sem backup de Postgres) viram **P2** — não é redução de importância, é mudança de eixo. Isso foi explicado individualmente nessas duas issues para não gerar confusão na equipe.

## 3. Resultado da reclassificação

| De → Para | Issues |
|---|---|
| **→ P0** (6) | #258, #404, #405, #406, #419, #423 |
| **→ P1** (6) | #276, #439, #440, #441, #442, #443 |
| **→ P2** (11, sendo 2 críticos e 4 bloqueados por infra externa) | #398, #412, #422 (sem mudança), #432, #435, #436, #437 (sem mudança), #446, #447, #448, #449 (sem mudança) |
| **→ P3** (4, sem mudança) | #400, #401, #402, #450 |
| **Fechadas** (3 — housekeeping) | #424, #427, #430 |

**Total**: 31 issues avaliadas → 28 permanecem abertas e classificadas, 3 fechadas.

## 4. Achado relevante

`#424`, `#427` e `#430` (Partner Attribution, Grant Adapter, Landing Founding Partners) tinham **100% do escopo entregue** — checklist inteiro marcado, PR mergeado referenciando o número da issue no commit (`feat(#424)`, `feat(#427)`, `feat(#430)`) — e nunca foram fechadas. Fechadas nesta ordem, cada uma com comentário linkando o PR que a implementou.

## 5. Roadmap resultante (resumo)

- **Curto prazo** (objetivo: conformidade regulatória com prazo em 2026 + integridade do motor fiscal + destravar conversão do programa comercial ativo): `#404`, `#405`, `#406` (NTs com prazo de produção 03/11/2026), `#419`, `#423` (Cockpit Early Adopters — "Revenue First"), `#441` (quick win), `#446`, `#447` (P2 críticos).
- **Médio prazo** (retenção + janela competitiva): `#258` (credit tracking, sticky feature), `#440`, `#442`, `#276`, `#398`, `#412`, `#448`, `#449`.
- **Longo prazo** (dependente de validação — funil Discovery → Customer Evidence → RFC da Epic #444): `#439`, `#443`.
- **Contínuo** (dívida técnica, sem prazo forçado): `#400`, `#401`, `#402`, `#450`.
- **Bloqueado** (dependência externa do owner, fora da fila de engenharia): `#432`, `#435`, `#436`, `#437`.

Roadmap completo com objetivo de negócio por horizonte: [`roadmap.md`](https://github.com/mickbap/tribultz-brain/blob/main/knowledge/product/roadmap.md).

## 6. Governança permanente

Toda Issue nova passa a exigir, antes de entrar no backlog: classificação estratégica (P0–P3), estimativa de impacto, e justificativa de prioridade — issues técnicas informam risco mitigado + impacto operacional + motivo de não poder esperar. Cadência: revisão **mensal** de prioridades, revisão **trimestral** do roadmap. Issues de competitive-parity continuam presas ao funil já institucionalizado (Competitive Intelligence → Discovery → Customer Evidence → RFC) — nunca sobem de P1 sem Customer Evidence associada.

## 7. Nota metodológica — honestidade sobre a base de evidência

Os critérios "Impacto na receita" e "Diferencial competitivo" são estimativas informadas por sinal real disponível (gap matrix competitivo em `tribultz-brain`, pricing tiers, demanda relatada no corpo das próprias issues, RFCs de origem) — **não são dados de receita/mercado medidos**. Onde a issue já carregava evidência explícita, a pontuação foi ancorada nela e citada na coluna "Evidência" da matriz. Onde não havia evidência real, a pontuação foi conservadora e isso está dito explicitamente — nenhuma pontuação foi apresentada como mais certa do que realmente é.

## Pendências conhecidas

1. **4 issues bloqueadas por dependência externa** (`#432`, `#435`, `#436`, `#437`) — aguardam ação do owner (acesso Magalu/Vercel), não entram em nenhum horizonte do roadmap até desbloqueio.
2. **Issues de competitive-parity sem Customer Evidence** (`#439`–`#443`) — permanecem em P1/discovery até passarem pelo funil formal da Epic #444, mesmo as que endereçam gaps 🔴 críticos na matriz competitiva.
3. **Próxima revisão mensal** de prioridades ainda não tem data agendada — a política define cadência, não quando começa o primeiro ciclo.
