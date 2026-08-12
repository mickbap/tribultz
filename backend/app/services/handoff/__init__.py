"""Domínio local do handoff comercial Rumy → Tribultz → Attio (Round 4, F3).

Módulos:
- contract  — HandoffEvent v1.1 (envelope interno; known/absent explícito)
- adapter   — interface do adapter Rumy (F2 definitivo BLOQUEADO até payload real)
- identity  — resolução determinística de pessoa (DEC-5)
- ownership — máquinas de ownership/automation, guards, SLA, auditoria
- service   — ingestão idempotente de eventos (ledger + transições)
- metrics   — métricas locais derivadas do banco

Sem efeito externo: nenhum router/task registra estes módulos nesta fatia; o
consumo real chega em fatias futuras atrás das flags RUMY_*/HANDOFF_* (OFF).
"""
