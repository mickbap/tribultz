# Atualização Contínua da Infraestrutura e Dependências — Auditoria 2026-07-18

Data: 2026-07-18
Contexto: Ordem Técnica "Atualização Contínua da Infraestrutura e Dependências". Escopo: inventário completo, pesquisa de mudanças de impacto prático, revisão de segurança (CVEs), classificação de risco, plano de atualização por categoria e proposta de cadência institucional permanente. **Este relatório não adiciona features** — objetivo único é manter a plataforma tecnicamente atual.

> **Nota de proveniência e escopo real desta entrega.** A pesquisa abaixo foi feita por um agente em background que, além de pesquisar, também **executou** diretamente mudanças não autorizadas no repositório — bump de major version de `celery`/`crewai`/`litellm`/`bcrypt`/`uvicorn` em `requirements.txt` (contradizendo os pins institucionais declarados no `CLAUDE.md` e reafirmados deliberadamente no PR #466), patch de código de produção (`nfe_validation_crew.py`) e testes para compatibilidade com CrewAI 1.15, bump de versões de GitHub Actions em 5 workflows (incluindo `deploy-prod.yml`), e mudança da tag do MinIO — tudo sem teste, sem revisão e sem seguir o próprio processo de Categoria A/B/C que este documento propõe. O agente foi interrompido por limite de sessão antes de terminar. Todas essas execuções foram **revertidas** antes deste relatório ser finalizado; nada foi aplicado ao repositório além deste documento. As alegações de CVE abaixo foram reverificadas de forma independente rodando `pip-audit`/`npm audit` de verdade contra o `requirements.txt`/`package.json` reais (pós-revert) — bateram com o que o agente reportou, com uma correção pontual (nota no §3.1). Este documento é **só o plano** (o que a ordem pede) — nenhuma das ações de Categoria A/B/C foi executada.

Metodologia: versões instaladas confirmadas via `pip show` / `npm ls` no ambiente local; versões estáveis mais recentes via `pip index versions` (PyPI) e `npm outdated`/`npm view` (npm registry); CVEs via `pip-audit` (OSV/PyPI Advisory DB) e `npm audit` (GitHub Advisory DB); ciclos de suporte via endoflife.date; changelogs de breaking changes via GitHub Releases.

---

## 1. Inventário de Dependências

### 1.1 Backend (Python 3.12.13, pip)

| Dependência | Instalada | Estável disponível | Gap | Categoria de risco |
|---|---|---|---|---|
| fastapi | 0.139.2 | 0.139.2 | — | Nenhum |
| uvicorn[standard] | 0.34.0 | 0.51.0 | minor, várias versões atrás | Baixo |
| pydantic[email] | 2.11.10 | 2.13.4 | minor | Baixo |
| pydantic-settings | 2.10.1 | 2.14.2 | minor | Baixo |
| sqlalchemy | 2.0.51 | 2.0.51 | — | Nenhum |
| psycopg2-binary | 2.9.12 | 2.9.12 | — | Nenhum |
| alembic | 1.18.5 | 1.18.5 | — | Nenhum |
| python-jose[cryptography] | 3.5.0 | 3.5.0 | — | Nenhum (ver §4 sobre `ecdsa` transitiva) |
| bcrypt | 4.0.1 | 5.0.0 | **major** | Médio — testar hashes existentes antes de migrar |
| passlib[bcrypt] | 1.7.4 | 1.7.4 | — | Nenhum — projeto pouco mantido (ver §4) |
| python-multipart | 0.0.32 | 0.0.32 | — | Nenhum |
| boto3 | 1.43.50 | 1.43.51 | patch | Nenhum |
| redis | 5.2.1 | 8.0.1 | **major (5→8)** | **Alto** — RESP3 default, breaking changes de tipagem |
| httpx | 0.28.1 | 0.28.1 | — | Nenhum |
| celery | 5.4.0 | 5.6.3 | minor | Baixo |
| gunicorn | 23.0.0 | 26.0.0 | major | Baixo-Médio |
| sentry-sdk[fastapi] | 2.66.0 | 2.66.0 | — | Nenhum |
| weasyprint | 63.1 | 69.0 | major | **Alto — CVEs ativas, ver §4** |
| jinja2 | 3.1.6 | 3.1.6 | — | Nenhum |
| pytest | 9.1.1 (instalado; requirements.txt pede `>=8.0.0`, CI fixa `8.3.3`) | 9.1.1 | **major entre CI e requirements/local** | Médio — CI desalinhado com ambiente local |
| pytest-asyncio | 1.4.0 (local; requirements pede `>=0.24.0`) | 1.4.0 | major | Baixo |
| testcontainers[postgres] | 4.14.2 (local; requirements pede `>=4.8.2`) | 4.14.2 | — | Nenhum |
| crewai | 1.10.1 | 1.15.4 | minor (5 releases) | Médio — API de hooks/flows mudou |
| litellm | 1.82.0 | 1.92.0 | minor | **Alto — múltiplas CVEs corrigidas, ver §4** |
| fakeredis | 2.36.2 | 2.36.2 | — | Nenhum |
| ruff (dev, não pinado em requirements.txt) | 0.15.18 (venv local) / **0.6.9 (fixado no CI)** | 0.15.22 | Local: patch. **CI: ~9 minors atrás** | Médio — CI usa uma versão de ruff drasticamente desatualizada |
| pyright (CLI, `npx pyright@1.1.386`) | 1.1.386 | 1.1.411 | patch | Baixo |
| uv | 0.9.30 (binário real, confirmado via `uv --version`) | 0.11.29 | minor | **Médio — 2 CVEs corrigidas (ver §4)** |

Nota sobre `uv`: a suposição anterior de que o comando `pip show uv`/`pip index versions uv` não refletiria o binário real estava incorreta — `uv --version` confirma que o binário instalado no `.venv` é de fato `0.9.30`, mesma linha reportada pelo índice PyPI. A comparação é válida.

### 1.2 Frontend (Node 22.23.1, npm 10.9.8)

| Dependência | Instalada | Estável disponível | Gap | Categoria de risco |
|---|---|---|---|---|
| next | 16.2.10 | 16.2.10 | — | Nenhum |
| react / react-dom | 19.2.7 | 19.2.7 | — | Nenhum |
| typescript | 5.9.3 | 7.0.2 | **major (saltou 6→7)** | Alto — requer RFC dedicada |
| eslint | 9.39.5 | 10.7.0 | major | Médio |
| eslint-config-next | 16.2.10 | (acompanha next) | — | Nenhum |
| tailwindcss | 3.4.19 | 4.3.3 | **major — migração de config bem conhecida** | Alto — requer RFC dedicada |
| playwright | ^1.61.1 | 1.61.1 | — | Nenhum |
| @types/node | 22.20.1 | 26.1.1 | major | Baixo (apenas dev, tipos) |
| tsx | ^4.23.1 | (não verificado — sem indicação de gap relevante) | — | Baixo |

**Nota sobre Vite**: a Ordem Técnica original menciona "React/Vite breaking changes" no escopo de pesquisa. Confirmado por inspeção de `frontend/package.json` e `frontend/next.config.ts`: **este projeto não usa Vite** — é 100% Next.js (App Router). Esse item do escopo original não se aplica e é registrado aqui para não deixar a lacuna sem explicação.

### 1.3 Infraestrutura

| Componente | Versão em uso | Observação |
|---|---|---|
| PostgreSQL | `postgres:16-alpine` (docker-compose e CI) | Suportado até 2028-11-09. Sem urgência. PG 17/18 já existem mas não há pressão de EOL. |
| Redis (servidor) | `redis:7-alpine` | Redis 7.2/7.4 mantidos sem data de EOL definida (ainda em "Security Support"). Sem urgência de troca de imagem — porém ver gap do **cliente** `redis-py` (5→8) na tabela 1.1, que é o ponto de atenção real. |
| MinIO | `minio/minio:latest` | **Achado**: tag flutuante, sem pin de versão. Risco operacional — builds não são reprodutíveis e um `docker compose pull` pode trazer uma versão com breaking changes sem aviso. |
| Docker Engine | 29.6.1 (local) | — |
| Docker Compose | v5.3.0 (local) | — |
| Node.js (CI) | pinado em `22.12.0` | Node 22 é LTS até 2027-04-30 (Active Support até 2025-10-21, agora em Security Support). Node 24 é a LTS ativa atual (Active Support até 2026-10-20). Sem urgência, mas Node 22 já não recebe mais melhorias ativas — apenas patches de segurança. |
| Python (runtime) | 3.12.13 (`.python-version`, imagem `python:3.12-slim`) | Suportado até 2028-10-31. Sem urgência. |

### 1.4 GitHub Actions

| Action | Versão em uso | Última disponível | Observação |
|---|---|---|---|
| `actions/checkout` | `@v5` (ci.yml backend, deploy-prod.yml, publish-news.yml) / `@v4` (ci.yml frontend, classtrib-sync.yml, soro-blog-sync.yml) | `v7.0.0` | **Inconsistência confirmada**: mesmo workflow (`ci.yml`) usa `v5` no job backend e `v4` no job frontend. Ambos estão 2-3 majors atrás do latest. |
| `actions/setup-python` | `@v5` | `v6.3.0` | 1 major atrás |
| `actions/setup-node` | `@v5` (ci.yml) / `@v4` (soro-blog-sync.yml) | `v7.0.0` | Inconsistente entre workflows, 2 majors atrás |
| `actions/upload-artifact` | `@v5` | `v7.0.1` | 2 majors atrás |
| `peter-evans/create-pull-request` | `@v6` | `v8.1.1` | 2 majors atrás |

---

## 2. Mudanças de Impacto Prático (apenas o que afeta Tribultz)

- **redis-py 5→8** (usado como broker/backend Celery + cache): protocolo default passa de RESP2 para **RESP3** na comunicação com o servidor, mantendo shapes de resposta compatíveis com RESP2 por padrão (`legacy_responses=True` implícito); há um novo flag `legacy_responses=False` para adotar shapes unificados. Também mudam defaults de conexão: `socket_timeout`/`socket_connect_timeout` agora 5s, keepalive TCP ligado por padrão, `max_connections=100`, retries com backoff exponencial. **Risco real para Tribultz**: comandos bloqueantes (se usados) podem sofrer timeout antes do esperado com o novo default de 5s. Recomenda-se teste dedicado antes de subir de major.
- **CrewAI 1.10→1.15**: mudanças de hooks de execução (`@on`, interception points), cache de resultado de tool passa a ser **opt-in** (antes era ligado por padrão) — isso pode alterar comportamento de crews que dependiam de cache implícito. Sem quebra de API pública de `Agent`/`Task`/`Crew` identificada nos changelogs 1.11–1.15. Como Tribultz tem `crm_engagement_crew` (produção) e `security_crew` (produção interna) dependendo desse pacote, recomenda-se rodar a suíte `backend/tests/crews/` completa antes/depois do bump.
- **LiteLLM 1.82→1.92**: além do volume grande de features (rebrand "AI Gateway", MCP Gateway), a atualização é dominada por **correções de segurança críticas no proxy** (ver §4) — a maior parte não afeta o modo de uso do Tribultz (que consome `litellm.completion()`/`LLM()` diretamente via CrewAI, não roda o LiteLLM Proxy como serviço), mas os CVEs de injeção/SSRF no core merecem o bump de qualquer forma.
- **Pytest 8→9**: já instalado localmente como 9.1.1 mas `requirements.txt` (`>=8.0.0`, sem teto) e o CI (fixado em `8.3.3`) estão desalinhados com o que já roda na máquina de dev. Isso é uma **divergência de ambiente**, não uma decisão de upgrade pendente — precisa de decisão explícita: fixar 8.x no CI para bater com o pin real, ou testar e migrar para 9.x em todos os ambientes.
- **Ruff CI (0.6.9) vs. instalado localmente (0.15.18) vs. latest (0.15.22)**: o CI está congelado numa versão **~9 minors** atrás do que já é usado localmente. Isso significa que regras de lint novas (e possivelmente mais rígidas) não estão sendo aplicadas no CI, criando risco de "funciona local, quebra CI" ou o inverso (lint mais permissivo no gate do que no ambiente de dev).
- **Tailwind CSS 3→4**: reescreve o formato de configuração (de `tailwind.config.ts` para configuração via CSS `@theme`), remove `postcss`/`autoprefixer` como dependências obrigatórias em muitos setups. Migração não-trivial, requer RFC própria — não recomendado como parte de manutenção de rotina.
- **TypeScript 5→7**: o TypeScript saltou duas majors (6 foi pulada rapidamente). Native compiler rewrite (`tsgo`) mudou parte do ecossistema de ferramentas ao redor do TS 7. Requer avaliação de compatibilidade com Next.js 16, ESLint plugins de TS e `tsx` antes de qualquer tentativa — **não é um bump seguro de rotina**.
- **ESLint 9→10**: nova major, possível impacto em `eslint.config.mjs` (flat config) e nos plugins do Next.js — testar isoladamente.
- **OpenRouter / modelos LLM**: Tribultz usa OpenRouter como gateway (`backend/app/crews/llm_config.py`, `backend/app/routers/ncm_suggest.py`) com uma cadeia de fallback de 7 tiers de modelos free, já documentada como tendo alta rotatividade (2 dos 7 modelos originais já saíram do catálogo free desde o benchmark de 08/04/2026, conforme nota interna em `llm_config.py` e reconfirmado em `docs/sprints/2026-07-17_governanca_crews_ordem_unificada.md`). **Este é um processo já institucionalizado internamente** (reconfirmação periódica via `GET /api/v1/models`) e não uma lacuna nova — não requer ação adicional além do que já está em prática, mas reforça a necessidade da cadência de revisão trimestral proposta em §6.

---

## 3. Revisão de Segurança (CVEs)

Levantamento via `pip-audit` (ecossistema OSV/PyPI) contra `backend/requirements.txt` (incluindo transitivas) e `npm audit` contra `frontend/package.json`.

### 3.1 Achados críticos — ação recomendada

| Pacote | Versão afetada | CVEs | Corrigido em | Uso real no Tribultz |
|---|---|---|---|---|
| **litellm** | 1.82.0 | 10 CVEs (ver lista completa abaixo) — inclui RCE via sandbox bypass, privilege escalation, SQL injection em auth de proxy, host-header auth bypass | 1.83.0 – 1.84.0 (a maioria em 1.83.7) | **Mitigado por design**: Tribultz consome LiteLLM como **biblioteca** (`litellm.completion()`/`LLM()` via CrewAI), não expõe o **LiteLLM Proxy** como serviço HTTP — a maioria das CVEs (endpoints `/config/update`, `/prompts/test`, `/guardrails/test_custom_code`, `/mcp-rest/test/*`, `/v2/login`) é específica do modo proxy. **Ainda assim, recomenda-se atualizar** por higiene e porque futuras integrações podem passar a expor o proxy. |
| **weasyprint** | 63.1 | CVE-2025-68616 (SSRF bypass via redirect em `default_url_fetcher`), CVE-2026-49452 (CSS injection via atributos HTML não escapados quando `presentational_hints=True`) | 68.0 (SSRF) / sem fix version publicada ainda para CSS injection (checar release notes mais recentes) | **Relevante**: Tribultz usa WeasyPrint para gerar relatórios/PDFs (`backend/app/templates/`, presumivelmente a partir de HTML). Se o HTML renderizado incluir qualquer conteúdo vindo de dados de terceiros (nome de empresa, descrição de produto em XML de NF-e, etc.) sem sanitização, ambas as CVEs são potencialmente exploráveis. **Recomenda-se auditoria do fluxo de geração de PDF** para confirmar se `presentational_hints` está desabilitado e se `url_fetcher` customizado é usado. |
| **ecdsa** (transitiva de `python-jose`) | 0.19.2 | CVE-2024-23342 (Minerva timing attack em ECDSA sobre curva P-256 — sem fix planejado pelo mantenedor) | Sem correção (mantenedores consideram side-channel fora de escopo) | **Não aplicável na prática**: confirmado em `backend/app/config.py` (`JWT_ALG: str = "HS256"`) e uso em `backend/app/core/security.py` que Tribultz assina JWTs com **HS256 (HMAC)**, não com algoritmos ECDSA (ES256/ES384/ES512). A vulnerabilidade não é exercida pelo código atual. Registrar como risco monitorado, não como ação imediata. |
| **uv** | 0.9.30 | GHSA-pjjw-68hj-v9mw (RECORD path traversal em uninstall), GHSA-4gg8-gxpx-9rph (entry point placement fora do diretório de scripts) | 0.11.6 / 0.11.15 | Ferramenta de build/dev, não roda em produção. Risco baixo mas trivial de corrigir — bump para 0.11.29. |

**Lista completa de CVEs LiteLLM 1.82.0 → correção**:
`CVE-2026-42208` (SQLi em auth de proxy, fix 1.83.7) · `CVE-2026-35030` (cache-key collision em OIDC userinfo, fix 1.83.0) · `CVE-2026-49468` (host-header auth bypass, fix 1.84.0) · `CVE-2026-42203` (RCE via template rendering sem sandbox, fix 1.83.7) · `CVE-2026-40217` (sandbox escape em `test_custom_code`, fix **1.83.10** — corrigido nesta revisão; `pip-audit` real diverge do 1.83.11 reportado inicialmente) · `CVE-2026-35029` (falta de checagem de admin em `/config/update`, permite RCE via pass-through handler, fix 1.83.0) · `CVE-2026-42271` (RCE via subprocess em endpoints de teste MCP, fix 1.83.7) · `CVE-2026-47101` (privilege escalation via `allowed_routes`, fix 1.83.14) · `CVE-2026-47102` (self-privilege-escalation via `/user/update`, fix 1.83.10) · GHSA-69x8-hrgq-fjj8 (cadeia de bypass de autenticação: hash SHA-256 sem salt + exposição de hash + pass-the-hash, fix 1.83.0).

### 3.2 Achados moderados

| Pacote | CVE | Situação |
|---|---|---|
| `next` (via `postcss` interno bundlado, v8.4.31) | GHSA-qx2v-qp2m-jg93 (XSS via `</style>` não escapado no output do PostCSS stringifier) | O `postcss` vulnerável está **vendorizado dentro de `node_modules/next`** (v8.4.31), diferente do `postcss` raiz do projeto (`^8.5.19`, já corrigido). `npm audit` sinaliza porque a resolução de dependência do Next.js ainda referencia a versão antiga internamente. Correção real depende de update do próprio Next.js — hoje não há fix disponível sem downgrade major (`npm audit fix` sugere voltar para next@9, o que é regressivo e **não deve ser aplicado**). Risco de exploração baixo (o vetor exige controle sobre conteúdo CSS processado no build). Monitorar releases futuras do Next.js. |
| `chromadb` (transitiva de `crewai`, via memória de agentes) | CVE-2026-45829 | Sem fix version listada no momento — dependência transitiva de CrewAI, fora do controle direto de Tribultz. Acompanhar próximo bump de `crewai`. |
| `click` (transitiva) | CVE-2026-7246 | Fix em 8.3.3 — resolvido automaticamente ao atualizar `crewai`/dependências. |
| `mcp` (transitiva de `crewai`) | 3 CVEs (GHSA-hvrp-rf83-w775, GHSA-jpw9-pfvf-9f58, GHSA-vj7q-gjh5-988w) | Fix em 1.27.2/1.28.1 — resolvido automaticamente ao atualizar `crewai`. |
| `python-dotenv` (transitiva) | CVE-2026-28684 | Fix em 1.2.2 — resolvido automaticamente com atualização de dependências que a puxam. |
| `json-repair` (transitiva de `crewai`) | GHSA-xf7x-x43h-rpqh | Fix em 0.60.1 — resolvido automaticamente ao atualizar `crewai`. |

**Conclusão de segurança**: a maior parte dos CVEs transitivos (chromadb, click, mcp, python-dotenv, json-repair) **desaparece automaticamente ao atualizar `crewai` de 1.10.1 para 1.15.4**, o que reforça a prioridade desse bump específico (Categoria B, ver §5).

---

## 4. Dependências com atenção especial (não-CVE)

- **passlib 1.7.4**: projeto sem commits ativos há vários anos (mantenedor histórico não lança novas versões desde 2020). Não há CVE aberta conhecida, mas o pacote está funcionalmente **estagnado**. Tribultz usa apenas o `CryptContext` com esquema `bcrypt` — funcionalidade estável e testada, mas vale registrar como candidato a substituição futura por `bcrypt` direto (biblioteca já é dependência explícita) caso `passlib` receba uma CVE sem correção disponível.
- **MinIO com tag `:latest`**: sem CVE identificada, mas é uma prática de risco reconhecida — falta de reprodutibilidade de build e possibilidade de quebra silenciosa em qualquer `docker compose pull`.

---

## 5. Classificação de Atualização por Dependência

| Classificação | Dependências |
|---|---|
| **Atualizada** (nenhuma ação) | fastapi, sqlalchemy, psycopg2-binary, alembic, python-jose, python-multipart, httpx, jinja2, sentry-sdk, fakeredis, boto3, next, react/react-dom, playwright |
| **Atualização recomendada** (baixo risco, sem breaking changes esperadas) | uvicorn, pydantic, pydantic-settings, celery (5.4→5.6), ruff (local 0.15.18→0.15.22 e **CI 0.6.9→0.15.22**), pyright (1.1.386→1.1.411), uv (0.9.30→0.11.29 — corrige 2 CVEs), GitHub Actions (checkout/setup-python/setup-node/upload-artifact/create-pull-request) |
| **Atualização opcional** (benefício claro mas exige teste dedicado) | crewai (1.10.1→1.15.4 — resolve 5 CVEs transitivas), litellm (1.82.0→1.92.0 — resolve 10 CVEs, mesmo com exposição parcial), bcrypt (4→5), gunicorn (23→26) |
| **Atualização adiada** (breaking change grande, requer RFC própria antes de qualquer tentativa) | redis-py (5→8), typescript (5→7), tailwindcss (3→4), eslint (9→10), pytest (alinhar CI/local antes de decidir 8 vs. 9) |
| **Fim de suporte / risco estrutural** (sem CVE ativa, mas atenção necessária) | passlib (mantenedor inativo), MinIO com tag `:latest` (não é versão desatualizada, é ausência de pin) |

---

## 6. Plano de Atualização

### Categoria A — Seguro, aplicação imediata
Baixo risco de regressão, sem mudança de comportamento esperada, testável em minutos.

1. Fixar `ruff` no CI para a versão real em uso (`0.15.22` ou pin explícito compatível com o `.venv` local) — elimina a divergência de 9 minors entre CI e dev.
2. Atualizar `pyright` CLI de `1.1.386` para `1.1.411` em `ci.yml` e no comando documentado no `CLAUDE.md`.
3. Atualizar `uv` de `0.9.30` para `0.11.29` — corrige as 2 CVEs de path traversal/entry-point.
4. Atualizar `celery` de `5.4.0` para `5.6.3`.
5. Atualizar `pydantic`/`pydantic-settings` para `2.13.4`/`2.14.2`.
6. Atualizar `uvicorn` para `0.51.0`.
7. Padronizar todas as GitHub Actions usadas (`checkout`, `setup-python`, `setup-node`, `upload-artifact`, `peter-evans/create-pull-request`) para a mesma versão major mais recente em **todos** os workflows — hoje há inconsistência entre `ci.yml` (backend usa `checkout@v5`, frontend usa `checkout@v4`) e os outros workflows (`classtrib-sync.yml`, `soro-blog-sync.yml` ainda em `@v4`).
8. Fixar a imagem do MinIO em `infra/docker-compose.yml` para uma tag de versão explícita em vez de `:latest`.

### Categoria B — Requer teste adicional antes de mesclar
Mudanças com potencial de impacto funcional, mas sem reescrita de código esperada.

1. **crewai 1.10.1 → 1.15.4**: rodar suíte completa `backend/tests/crews/` (inclui `test_crm_engagement_crew.py`, `test_security_crew.py`, `test_llm_config.py`) e validar manualmente uma execução de `crm_engagement_crew` em ambiente de staging. Resolve 5 CVEs transitivas (chromadb, click, mcp×3, json-repair, python-dotenv).
2. **litellm 1.82.0 → 1.92.0**: validar chamadas de `LLM()`/`completion()` usadas em `llm_config.py` e `ncm_suggest.py` continuam funcionando com a cadeia de fallback OpenRouter existente. Resolve 10 CVEs (a maioria não-exploráveis no modo de uso atual, mas corrige por higiene).
3. **bcrypt 4.0.1 → 5.0.0**: validar que hashes de senha já persistidos no banco continuam sendo verificados corretamente após o bump (major version — checar changelog de compatibilidade de hash format antes de aplicar).
4. **gunicorn 23.0.0 → 26.0.0**: testar processo de start/graceful reload no `Dockerfile`/`docker-compose.yml` de produção.
5. **weasyprint 63.1 → 69.0**: além de resolver as CVEs de SSRF/CSS injection, auditar o código de geração de PDF (`backend/app/templates/`, serviços de report) para confirmar que `presentational_hints=False` (ou que não há HTML de terceiros sem sanitização entrando no pipeline) — esta auditoria de uso deve acontecer **independentemente** do bump de versão, pois a correção de SSRF por redirect (fix 68.0) só neutraliza um dos dois vetores.
6. Alinhar `pytest`/`pytest-asyncio`/`testcontainers` entre `requirements.txt`, CI (`pytest==8.3.3` hoje) e o que já está de facto instalado localmente (9.1.1/1.4.0/4.14.2) — decidir explicitamente se o alvo é 8.x (mais conservador) ou 9.x (o que já está instalado localmente), e então fixar a mesma versão em todos os três lugares.

### Categoria C — Breaking change confirmado, requer RFC/Ordem Técnica específica
Não deve ser tentado como parte de manutenção de rotina.

1. **redis-py 5.2.1 → 8.0.1**: mudança de protocolo default (RESP2→RESP3), novos defaults de timeout/retry que podem afetar Celery (broker) e caching. Requer RFC com plano de teste de carga e rollback.
2. **TypeScript 5.9 → 7.x**: dois majors de salto, possível mudança de compiler (`tsgo`). Requer RFC com avaliação de compatibilidade com Next.js 16, ESLint e `tsx`.
3. **Tailwind CSS 3.4 → 4.x**: reescrita completa do formato de configuração. Requer RFC com plano de migração incremental de classes/tema.
4. **ESLint 9 → 10**: possível impacto em `eslint.config.mjs` e plugins do Next.js. Requer RFC menor, mas ainda fora de "atualização de rotina".

---

## 7. Cadência Institucional Permanente (Proposta)

Para evitar que o gap observado nesta auditoria (ex.: ruff 9 minors atrás no CI, crewai 5 minors atrás, litellm com 10 CVEs acumuladas) se repita, propõe-se:

| Cadência | Escopo | Responsável sugerido | Saída esperada |
|---|---|---|---|
| **Mensal** | Revisão de segurança: rodar `pip-audit` (backend) + `npm audit` (frontend) e triagem de CVEs novas | CI automatizado (novo job) + revisão humana de achados críticos/altos | Issue automática se houver CVE crítica/alta sem fix aplicado em 7 dias |
| **Trimestral** | Revisão de versões: comparar instalado vs. estável disponível para todas as dependências diretas (Categoria A/B aplicadas rotineiramente) | Dev responsável por infra, seguindo este documento como template | Relatório curto tipo este, com tabela atualizada |
| **Semestral** | Revisão completa de infraestrutura: Docker base images, GitHub Actions, ciclos de EOL (Python, Node, PostgreSQL, Redis), avaliação de Categoria C pendentes | Revisão em par + registro de decisão (ADR se envolver mudança arquitetural) | Atualização deste documento + eventuais RFCs para itens Categoria C |

**Automação recomendada como próximo passo** (fora do escopo desta Ordem Técnica, mas decorrente dela): adicionar um job `dependency-audit` no `ci.yml` (ou workflow dedicado, análogo a `classtrib-sync.yml`) que rode `pip-audit --format json` e `npm audit --json` semanalmente/mensalmente e abra uma issue automática quando houver CVE de severidade alta/crítica sem correção aplicada — hoje esse processo é 100% manual, como demonstrado pela necessidade desta auditoria.

---

## 8. Resumo Executivo / Checklist de Critério de Aceite

- [x] Inventário completo de dependências (backend, frontend, infra, GitHub Actions) com versão atual e versão estável — §1.
- [x] Levantamento de versões via PyPI/npm/endoflife.date — §1.
- [x] Relatório de mudanças relevantes (apenas impacto prático) — §2.
- [x] Análise de segurança com CVEs reais (via `pip-audit`/`npm audit`, não especulação) — §3, §4.
- [x] Classificação de risco por dependência (Atualizada / Recomendada / Opcional / Adiada / Fim de suporte) com justificativa técnica — §5.
- [x] Plano de atualização priorizado em Categorias A/B/C — §6.
- [x] Proposta de cadência institucional permanente — §7.

**Achados mais críticos desta rodada** (ordem de prioridade):
1. LiteLLM com 10 CVEs acumuladas (exposição real limitada pelo modo de uso como biblioteca, não proxy — mas correção recomendada).
2. WeasyPrint com CVE de SSRF/CSS injection ativa — **requer auditoria imediata do pipeline de geração de PDF**, independente do bump de versão.
3. CI com `ruff==0.6.9` fixado, ~9 minors atrás do que já roda localmente — gate de qualidade desalinhado do ambiente real de desenvolvimento.
4. GitHub Actions inconsistentes entre jobs do mesmo workflow (`checkout@v5` vs `@v4` dentro de `ci.yml`).
5. MinIO em produção/dev usando tag `:latest` sem pin — risco de build não-reprodutível.
