# DEC-9 — Uma única implementação canônica do domínio de handoff

> Registrada em 12/08/2026 por ordem do Round 8 (Ermes — Produto/Vendas), §1/§3.
> Contexto: PO-2026-07-CRM-001, série de Rounds do handoff Rumy → Attio.
>
> **Nota de 29/08/2026 (ROUND 18-A):** o Attio foi descomissionado. A DEC-9
> continua valendo no que importa — uma única implementação canônica do domínio
> de handoff — só que o destino externo deixou de existir: o handoff termina no
> domínio local, que sempre foi a autoridade.

## Decisão

**Linha canônica: PRs #620 → #621 → #622 → #623** — escolhida por estar
integrada, validada contra o Attio real (F4 executada, contract-test 21/21) e
materialmente mais avançada.

A implementação paralela `feat/commercial-handoff-f1-f3` (tip `37557a9`,
migration concorrente com a MESMA revision `2026_08_12_0037`, tabelas
`commercial_*`) **não foi integrada**: sem renumeração, sem segunda família de
models, sem compatibilidade entre as duas. Foi tratada como fonte temporária de
três ativos portáveis e **descartada** após o porte.

## Ativos portados (comportamento, não duplicação)

1. **Teste de rollback real da migration** (`tests/test_zz_handoff_migration_rollback.py`)
   — upgrade → downgrade (artefatos somem) → upgrade (voltam com constraints) →
   restaura head. Adaptado da linha descartada.
2. **Cobertura extra do UNOBSERVABLE estrutural** — ausência ≠ 0 ≠ null
   interpretável ≠ string convertível (json.dumps quebra; int(str) quebra).
3. **Asserção da hierarquia dos relógios** — `pause_sla < accept_sla <
   first_action_sla` (a pausa é a exposição aceita; tem que ser a mais apertada).

## Invariante decorrente

**INV-3 — SINGLE HANDOFF FOUNDATION** (Round 8 §13): existe exatamente uma
implementação ativa para persistência, identidade, contrato, ownership,
suppression e processamento do handoff comercial. Guardada por teste
(`tests/test_single_foundation.py`): 1 revision `2026_08_12_0037`, 1 head
Alembic, zero referências a `commercial_*`, uma única definição de
OwnershipState/AutomationState/HandoffEvent/ProviderCapability.

## Registro canônico

ADR no Brain (knowledge/decisions/) pendente de entrada via gate (B-8 da série).
