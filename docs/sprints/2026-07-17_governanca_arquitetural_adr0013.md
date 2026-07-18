# Governança Arquitetural — ADR-0013 (Ordem Técnica de Institucionalização)

Data: 2026-07-17/18
Contexto: sequência direta da Ordem Técnica das Crews (ver [relatório anterior](2026-07-17_governanca_crews_ordem_unificada.md)). Aquela ordem resolveu um caso concreto (5 Crews sem estado institucional); esta generaliza a solução — governança arquitetural deixa de depender de decisão pontual e passa a ter processo, inventário e auditoria automatizada permanentes.

## 1. Decisão — 5 partes, uma ordem única

| Parte | Conteúdo | Onde vive |
|---|---|---|
| I | **Política de Depreciação** — ciclo obrigatório de 4 estados (Ativa/Deprecada/Descontinuada/Removida) + processo obrigatório antes de qualquer remoção. Nasceu do caso ChatOps: decisão de produto e remoção de código ficaram ~3 meses desalinhadas. | `knowledge/process/deprecation-policy.md` (Brain) |
| II | **Inventário Arquitetural** — registro único de toda capacidade permanente (auth, motor determinístico, Crews, Celery, APIs, integrações, componentes removidos). Nunca apaga linha, só muda estado. | `knowledge/engineering/architecture-inventory.md` (Brain) |
| III | **Auditoria arquitetural automatizada** — `tools/architecture_audit.py`, roda contra o estado real do repo (não depende de memória de quem audita). | `tools/architecture_audit.py` (Produto) |
| IV | **ADR-0013** — consolida os 7 princípios que já governavam a arquitetura (governança precede implementação; identidade≠contexto; motor determinístico é fonte oficial; Crew tem ciclo de vida; remoção segue processo; governança é auditável; critério técnico é objetivo). Não introduz princípio novo, só torna explícito o que já era seguido. | `knowledge/decisions/2026-07-18-principios-permanentes-da-arquitetura.md` (Brain) |
| V | **Definition of Ready + template de ADR** — toda ordem técnica futura confronta inventário, política de depreciação, ADR-0013 e classificação de Crews *antes* de começar; template de ADR ganha campo obrigatório "Natureza" (cria/altera/depreca/remove capacidade). | `knowledge/process/definition-of-ready.md` + `knowledge/decisions/README.md` (Brain) |

## 2. O que a auditoria automatizada checa

`tools/architecture_audit.py` roda 5 verificações contra o repo real, sem depender de memória de quem audita:

1. Crews sem header `Status:` no docstring (classificação institucional)
2. Tasks Celery definidas em `app/tasks/` mas ausentes de `autodiscover_tasks`
3. Ferramentas em `app/crews/tools/` sem nenhum import fora do próprio arquivo
4. Routers reais (`app/routers/`) vs. lista documentada no `CLAUDE.md`
5. Sincronia Brain × produto — Crews existentes vs. inventário em `knowledge/engineering/crews.md` (pula com aviso se `../tribultz-brain` não existir; ausência do Brain não bloqueia a auditoria)

Projetada para futura integração ao CI — não integrada nesta entrega (não bloqueia a ordem, conforme especificado).

## 3. Achado real (rodada de 2026-07-17)

```
[OK] Crews sem classificação institucional
[1 achado] Tasks Celery ausentes de autodiscover_tasks
  - task_f_security_audit.py define uma task mas o módulo não está em autodiscover_tasks
[OK] Ferramentas órfãs em app/crews/tools/
[OK] Routers reais vs. CLAUDE.md
[OK] Sincronia Brain × produto (Crews)
```

Único achado real: `task_f_security_audit` fora do autodiscover — já documentado como pendência conhecida (decisão de frequência/cadência, não de escopo; ver pendência #1 do relatório de Crews). Zero falso positivo depois de 2 rodadas de calibração do regex de sincronia com o Brain (`Descontinuada` é exceção válida — a Política de Depreciação exige nunca apagar a linha do inventário).

## 4. Deploys e verificação

| PR | Repo | Conteúdo | Verificação |
|---|---|---|---|
| [tribultz-brain#4](https://github.com/mickbap/tribultz-brain/pull/4) | Brain | Partes I, II, IV, V | `lint_brain.py` (0 erros) + `build_index.py` (106 docs sincronizados) — repo sem CI/deploy, merge direto |
| [tribultz#470](https://github.com/mickbap/tribultz/pull/470) | Produto | Parte III (`architecture_audit.py`) | `ruff` limpo, `pyright` 0 erros, 682 testes (`pytest`, nenhum código de `app/` tocado) — [CI verde](https://github.com/mickbap/tribultz/actions/runs/29624159503) |

Ambos merged em 2026-07-17 (mesma sessão da Ordem Técnica das Crews).

## Pendências conhecidas — fora do escopo desta ordem, registradas

1. **`task_f_security_audit` continua fora do `beat_schedule`/`autodiscover_tasks`** — mesma pendência já registrada no relatório de Crews; falta decisão de frequência antes de ativar.
2. **Auditoria não integrada ao CI** — hoje roda manualmente (`cd backend && source .venv/bin/activate && python ../tools/architecture_audit.py`); integração futura, não bloqueada por nada técnico.
3. **DoR v2 e template de ADR com campo "Natureza"** valem a partir de agora — ordens técnicas já em andamento antes de 2026-07-17 não são retroativamente exigidas a se conformar.
