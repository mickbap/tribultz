# Execução da Categoria A e Institucionalização da Auditoria de Dependências

Data: 2026-07-18
Contexto: Ordem Técnica de execução direta, sequência da [Auditoria de Dependências](2026-07-18_atualizacao_continua_dependencias.md) de mais cedo hoje. Executa **só** os itens classificados como Categoria A naquele relatório, audita o pipeline de PDF, e institucionaliza o monitoramento contínuo (workflow automatizado + política no Brain). Categoria B e C permanecem congeladas, como a ordem exigiu.

Execução feita **diretamente por mim, sem subagentes em background** — lição do incidente da sessão anterior, em que um agente sem isolamento executou mudanças não autorizadas. Cada item abaixo foi aplicado e validado individualmente antes do próximo.

## 1. Categoria A — aplicada e validada item por item

| Item | De → Para | Validação |
|---|---|---|
| `uv` (CI) | 0.9.30 → 0.11.29 | ruff + pyright + pytest (682) + auditoria arquitetural |
| `ruff` (pin no CI) | 0.6.9 → 0.15.22 | idem — `ruff check` limpo com a versão nova |
| `pyright` (CI + `CLAUDE.md`) | 1.1.386 → 1.1.411 | idem — 0 erros com a versão nova |
| `celery` | 5.4.0 → 5.6.3 | ruff/pyright/pytest + **smoke test real**: rebuild do container `worker`, conectou no Redis real, registrou as 14 tasks, `beat` iniciou o scheduler normalmente |
| `uvicorn` | 0.34.0 → 0.51.0 | ruff/pyright/pytest + **smoke test real**: API subiu no Docker, `/health` respondeu `{"status":"ok"}` |
| GitHub Actions (5 workflows) | `checkout` v4/v5→v7, `setup-python` v5→v6, `setup-node` v4/v5→v7, `upload-artifact` v5→v7, `peter-evans/create-pull-request` v6→v8 | Versões confirmadas via API do GitHub (`gh api repos/.../releases/latest`) antes de aplicar; YAML validado nos 5 arquivos |
| MinIO (tag) | `:latest` → `RELEASE.2025-09-07T16-13-09Z` | Confirmado via Docker Hub que essa É a imagem que `:latest` resolve hoje (MinIO não publica imagem nova desde set/2025, apesar de ter GitHub Releases mais recentes sem imagem Docker correspondente). Container recriado, `healthy`, `/minio/health/live` → 200 |
| Frontend (build final) | — | `npm run build` limpo + 156 testes passando (nenhuma dependência de frontend mudou nesta ordem — só a versão das Actions que rodam o job) |

**Correção ao relatório anterior**: `pydantic`/`pydantic-settings` **não foram atualizados**. O relatório de auditoria os classificou como "Atualização recomendada" (2.11.10→2.13.4 / 2.10.1→2.14.2) comparando só números de versão. Inspecionando o `METADATA` real do wheel do CrewAI 1.10.1, ele trava `pydantic~=2.11.9` e `pydantic-settings~=2.10.1` — as versões já instaladas **já são o teto máximo** dentro dessa trava (confirmado via `pip index versions`: 2.11.10 é o último patch da série 2.11.x, 2.10.1 é o último da série 2.10.x). Atualizar quebraria o pin institucional do CrewAI, que é Categoria B nesta ordem — fora de escopo. Não há ação possível aqui sem primeiro decidir sobre o CrewAI. Isso virou lição registrada na política do Brain (ver §4).

## 2. Auditoria funcional do pipeline de PDF (WeasyPrint)

Únicos dois pontos de chamada no código: `backend/app/services/pdf_service.py` (`generate_validation_report_pdf` e `generate_batch_report_pdf`). Inspecionado linha a linha:

- `HTML(string=html).write_pdf()` — **sem** `url_fetcher` customizado, **sem** `presentational_hints=True` (usa o default `False` da lib).
- Os dois templates (`report_validation.html`, `report_batch.html`) são **100% CSS inline** — nenhuma referência a `<img>`, `<link>`, `@import` ou `url()` externo em nenhum dos dois.
- Todo dado dinâmico é interpolado via Jinja2 com `Environment(autoescape=True)`, **sem nenhum `|safe`/`Markup()`** em lugar nenhum — nem no serviço, nem nos templates.

**Parecer técnico:**

| CVE | Classificação | Justificativa |
|---|---|---|
| CVE-2025-68616 (SSRF via redirect no `default_url_fetcher`) | **Mitigado pela ausência de superfície** | O código vulnerável existe na lib instalada, mas nunca é exercido: não há nenhuma URL externa nos templates para o fetcher buscar, e nenhum dado dinâmico vira URL fetchável (tudo é texto autoescapado). Ainda assim, recomenda-se o bump de versão (Categoria B) como defesa em profundidade — um template futuro poderia introduzir uma referência externa sem que quem escrever lembre desta análise. |
| CVE-2026-49452 (CSS injection via `presentational_hints=True`) | **Não aplicável** | O parâmetro nunca é passado como `True` em nenhum dos dois call sites — o vetor exige exatamente essa configuração, que o código não usa. |

## 3. Automação — `.github/workflows/dependency-audit.yml`

Workflow novo, testado localmente (YAML validado, todo bloco bash com `bash -n`, scripts Python testados contra `pip-audit`/`npm audit` reais do repo):

- **Semanal** (segunda-feira): `pip-audit` + `npm audit`.
- **Mensal** (dia 1): a mesma varredura **mais** comparação de versões (`pip list --outdated`, `npm outdated`) e inventário de imagens Docker + GitHub Actions em uso.
- Relatório sempre sobe como artifact (`dependency-audit-report`, retenção 90 dias).
- **Nunca abre PR.** Abre (ou comenta, se já existir) uma Issue com label `security` só quando há vulnerabilidade **Alta/Crítica sem nenhuma versão de correção publicada** — testado contra os dados reais de hoje: dispararia para `weasyprint` (CVE-2026-49452, sem fix), `chromadb` (CVE-2026-45829, sem fix) e `ecdsa` (CVE-2024-23342, sem fix por decisão do mantenedor). As 2 vulnerabilidades moderadas do `next`/`postcss` corretamente **não** disparam (severidade abaixo do limiar).
- `workflow_dispatch` com input `full_review` para rodar a revisão completa sob demanda.

## 4. Política permanente (Brain)

[`knowledge/process/dependency-audit-policy.md`](https://github.com/mickbap/tribultz-brain/pull/6) — classificação A/B/C com critério verificável, a armadilha pydantic×crewai documentada como lição permanente, e a cadência de revisão manual (mensal/trimestral/semestral) espelhando a Auditoria Arquitetural.

## 5. Verificação final

- `ruff check app/ tests/ ../tools/` — limpo (versão 0.15.22)
- `npx pyright@1.1.411` — 0 erros
- `pytest -q` — 682 passed
- `python ../tools/architecture_audit.py` — mesmo achado conhecido (`task_f_security_audit`), nenhuma regressão
- Docker Compose: `api`, `worker`, `beat`, `minio` recriados e saudáveis; `/health` (API) e `/minio/health/live` (MinIO) respondendo
- Frontend: `npm run build` limpo, `npm test --silent` — 156 passed
- YAML dos 6 workflows (5 alterados + 1 novo) validado com `yaml.safe_load`

## Pendências conhecidas — fora do escopo desta ordem, registradas

1. **Categoria B congelada** (CrewAI, LiteLLM, WeasyPrint, bcrypt, gunicorn, alinhamento pytest) — aguarda branch própria + validação funcional dedicada por item, conforme a própria ordem exige.
2. **Categoria C congelada** (redis-py 8, TypeScript 7, Tailwind 4, ESLint 10) — aguarda RFC própria por item.
3. **`task_f_security_audit` continua fora do autodiscover** — mesma pendência registrada nos três relatórios anteriores desta sequência.
4. **Abertura automática de Issue** só será validada de verdade na primeira execução real do workflow em produção (semanal/mensal ou `workflow_dispatch` manual) — a lógica foi testada contra dados reais localmente, mas a chamada à API de Issues do GitHub em si não pôde ser exercida fora do runner.
