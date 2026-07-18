# Governança das Crews (CrewAgents) — Ordem Técnica Unificada

Data: 2026-07-17/18
Contexto: avaliação das capacidades dos CrewAgents pedida nesta sessão, decorrente do fix do bug de login (#464). A auditoria encontrou 5 Crews sem estado institucional — a Ordem Técnica Unificada resolveu isso de ponta a ponta: governança no Brain primeiro, execução no produto depois.

## 1. Decisão — classificação oficial das 5 Crews

| Crew | Status | Onde vive a decisão |
|---|---|---|
| CRM Engagement | **Produção** | `knowledge/engineering/crews.md` |
| Security (SOC + CloudSec + SRE) | **Produção Interna** — ferramenta operacional da Tribultz, nunca produto sem RFC própria | idem |
| NFe Validation | **Dormante** — motor determinístico continua sendo a validação oficial; único gatilho de reativação: camada interpretativa em linguagem natural sobre os findings | idem |
| ChatOps | **Descontinuada** | [ADR-0012](https://github.com/mickbap/tribultz-brain/blob/main/knowledge/decisions/2026-07-17-encerramento-chatops-crew.md) |
| DevOps (`crews/tribultz_devops/`) | **Descontinuada** — legado experimental do Sprint 2, nunca integrado, zero automação dependia dele | `crews.md` |

Ciclo de vida institucionalizado (Produção / Dormante / Experimental / Descontinuada) — toda Crew futura entra nesse regime desde a criação, não depois.

## 2. Políticas permanentes registradas

- **Security Crew**: nunca antecipar interface para cliente; oferecer a tenants exige RFC específica.
- **LLM fallback**: critério oficial em 5 níveis — disponibilidade (gate) → velocidade → contexto → qualidade (avaliação periódica, nunca subjetiva) → custo (modelo pago só via RFC própria).
- **Teste mínimo obrigatório**: toda Crew nova cobre métodos públicos + parser de saída + fluxos de erro + fallback de LLM indisponível antes de entrar em `main`.
- **Auth**: nenhuma Crew cria mecanismo próprio — todas reutilizam ADR-0011 (`get_current_actor`).

## 3. Execução no produto

- Removido por completo: `chatops_crew.py`, `executor.py`, 4 ferramentas exclusivas do ChatOps + testes, `crews/tribultz_chatops/` e `crews/tribultz_devops/` inteiros.
- Preservado (dependência real da NFeValidationCrew, que fica Dormante): `ParseNFeXMLTool`, `ValidateIBSCBSRulesTool`, `memory_system.py`, `llm_config.py`.
- Header de status adicionado no docstring das 3 Crews que restam.
- Cadeia de fallback LLM renovada: 2 dos 7 modelos originais (benchmark 08/04/2026) tinham saído do catálogo free do OpenRouter — substituídos, verificados live + tool-calling em 17/07/2026.
- Cobertura de teste fechada para Security Crew e CRM Engagement Crew (zero teste antes desta rodada; 20 testes novos).

## 4. Achado real da auditoria final

`.github/workflows/ci.yml` tinha um smoke-check (`CrewAI import sanity`) importando `TribultzChatOpsCrew` diretamente. Sem essa correção, o CI teria quebrado na próxima alteração em `app/crews/` — não no momento da remoção em si (o PR que remove e o PR que quebraria o CI seriam o mesmo), mas ilustra o tipo de referência escondida que só aparece auditando de verdade, não perguntando "alguém usa isso?". Corrigido para importar as 3 Crews que restam.

## 5. Deploys e verificação

| PR | Repo | Conteúdo | Deploy |
|---|---|---|---|
| [tribultz-brain#3](https://github.com/mickbap/tribultz-brain/pull/3) | Brain | ADR-0012 + `crews.md` + ref cruzada no ADR-0011 | repo sem CI/deploy — merge direto |
| [tribultz#467](https://github.com/mickbap/tribultz/pull/467) | Produto | Cadeia LLM + 20 testes novos | [run bem-sucedido](https://github.com/mickbap/tribultz/actions), API healthy |
| [tribultz#468](https://github.com/mickbap/tribultz/pull/468) | Produto | Remoção ChatOps/DevOps + docs + fix do CI | deploy em 46s, API healthy pós-deploy |

Gates finais: 682 testes (`pytest`), `ruff` e `pyright` (bare, `backend/` inteiro) limpos. `FastAPI` importa (33 rotas) e `Celery` registra as 9 tasks sem erro, incluindo `task_f_security_audit` (ver pendência abaixo).

## Pendências conhecidas — fora do escopo desta ordem, registradas

1. **`task_f_security_audit` continua fora do `beat_schedule`/`autodiscover_tasks`.** A Ordem definiu o *domínio* da Security Crew (interna) mas explicitamente não pediu para ativar a execução automática — falta decisão de frequência/cadência antes disso.
2. **Reativação da NFeValidationCrew** depende de uma decisão de produto futura (oferecer explicação em linguagem natural sobre os findings) — sem essa decisão, ela permanece Dormante indefinidamente, por design.
3. **`Sprint2_ChatPrep_and_Sprint3_ChatMVP.md`** (raiz do repo) e os arquivos em `docs/sprints/`/`docs/reports/` ainda citam ChatOps/DevOps — deixados intactos de propósito (histórico não se reescreve).
