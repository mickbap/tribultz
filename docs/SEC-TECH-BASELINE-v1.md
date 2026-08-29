# SEC-TECH-BASELINE-v1

**Fotografia técnica para o agente "Segurança Tribultz"**
Produzida pelo Techlead em atendimento à requisição documental de Produto (Ermes) de 17/08/2026.

> **Natureza deste documento.** É levantamento, não plano de correção. Nada foi
> implementado em consequência desta ordem.
>
> **Como ler as afirmações.** Cada uma carrega o estado em que se encontra, e os
> estados **não são sinônimos**:
>
> | Estado | Significado |
> |---|---|
> | `MAIN` | está no código de `main` |
> | `MERGEADO` | PR incorporado a `main` |
> | `DEPLOYADO` | o commit foi aplicado na VM de produção |
> | `PRODUÇÃO` | comportamento **observado** em produção, não inferido do código |
> | `TESTADO` | há teste automatizado que exercita o comportamento |
> | `REGRESSÃO PERMANENTE` | há teste no CI que **falha** se o comportamento regredir |
> | `PR ABERTO` | existe PR, ainda não incorporado |
> | `NÃO DEMONSTRADO` | não encontrei evidência suficiente — ver §13 |
>
> Onde eu **não** verifiquei, está escrito que não verifiquei. Num baseline de
> segurança, inferência apresentada como fato é o pior defeito possível.

---

## 1. Estado de referência

| Item | Valor |
|---|---|
| Commit de `main` | `eb968915a230b4b14038870d06b151827a7dd702` |
| Commit em produção | `eb968915a230b4b14038870d06b151827a7dd702` — **idêntico a `main`** |
| Último deploy | 2026-08-17T18:14:28Z · `success` |
| Data/hora da referência | 17/08/2026, ~15:20 (America/Sao_Paulo) |
| Verificação de produção | `/health/deep` → `status=ok`, 7/7 subsistemas; 20 rotas públicas e 16 da área logada respondendo `200` |

### Ambientes

Existem **dois**, e a ausência do terceiro é deliberada (`docs/infra/operations_runbook.md`):

| Ambiente | Composição |
|---|---|
| **local** | Docker Compose do desenvolvedor — Postgres, Redis e MinIO em container |
| **produção** | VM Magalu — `api`, `worker`, `beat`, `redis` em container; **Postgres e Object Storage são serviços gerenciados externos** |

**Não existe staging.** Portanto a pergunta "diferenças de segurança entre
produção e staging" **não se aplica**; o que existe são diferenças
local↔produção, e elas são arquiteturais, não drift:

| | local | produção |
|---|---|---|
| Postgres | container `postgres:16-alpine` | Magalu DBaaS (externo, host privado) |
| Object Storage | MinIO em container | Magalu Object Storage (S3) |
| Migração | serviço one-shot `migrate` | passo do `deploy.sh` |

**Consequência de segurança que decorre disso:** não há ambiente de ensaio para
mudança de autorização. Toda alteração de auth vai de local para produção, com o
CI como único intermediário. `NÃO DEMONSTRADO` que isso seja suficiente.

---

## 2. Arquitetura relevante à segurança

| Camada | Tecnologia | Nota de segurança |
|---|---|---|
| Frontend | Next.js 16 / React 19, deploy Vercel | Deploy independente do backend; não compartilha processo |
| Backend | FastAPI (Python 3.12), SQLAlchemy, Alembic | Único ponto de enforcement de autorização |
| Banco | PostgreSQL 16 gerenciado, multi-tenant por coluna | `tenant_id` em todas as tabelas de domínio; **sem RLS** — isolamento é de aplicação |
| Cache / broker | Redis 7 (container na VM) | Broker do Celery e backing do rate limiter |
| Workers / jobs | Celery 5.6 + beat | Executam com o mesmo acesso ao banco que a API |
| Armazenamento | S3 (Magalu Object Storage) | Acesso por URL pré-assinada, TTL 900s (`documents.py:36`) |
| APIs | REST sob `/api/v1` | Duas superfícies: sessão (Bearer JWT) e pay-per-call (`X-API-Key`) |
| Serviços externos | Asaas (billing), OpenRouter (IA), HubSpot, Resend (SMTP), Sentry | Cada um com credencial própria em `/opt/tribultz/.env` |
| Autenticação | JWT HS256, `JWT_EXPIRES_MIN=480` (8h) | Ver §6 |
| Billing | Asaas + tabelas `plans`/`subscriptions`/`usage_tracking` | Plano governa entitlement (§9) |
| Webhooks | Asaas, Rumy | Dois mecanismos distintos de verificação (§5). O webhook Attio foi removido em 29/08/2026 (ROUND 18-A) |
| Observabilidade | Sentry, `/health/deep`, `AdminAuditLog`, workflow `monitor` | §11 |
| CI/CD | GitHub Actions — `backend-gates`, `frontend-build`, `deploy-prod` via SSH | §12 |

Segredos vivem em `/opt/tribultz/.env` na VM (`0600 root:root`), fonte de
verdade declarada em `docs/infra/secrets_inventory.md`. **Nenhum valor consta
deste documento.**

---

## 3. Trust boundaries

| # | Fronteira | Onde ocorre o enforcement | Estado |
|---|---|---|---|
| B1 | Internet → frontend (Vercel) | nenhum enforcement de autorização; o frontend é código público | `MAIN` |
| B2 | Frontend → API | `Depends(get_current_user)` / `get_current_actor` decodifica o JWT e **relê o usuário no banco** (`deps.py:38-70`) | `MAIN` · `TESTADO` |
| B3 | Internet → API pública sem sessão | `/api/v1/public/*`, `/api/v1/news` (GET), `/health/*`: sem auth, com rate limit por IP | `MAIN` · `PRODUÇÃO` |
| B4 | Integrador → API pay-per-call | `_resolve_api_key` valida hash, `is_active` e saldo (`public_api.py:133`) | `MAIN` |
| B5 | Provedor externo → webhook | três mecanismos distintos, ver §5 | `MAIN` |
| B6 | Tenant A ↔ Tenant B | filtro `WHERE tenant_id == current_user.tenant_id` nas consultas de domínio | `MAIN` · §7 |
| B7 | Usuário → superadmin | `require_superadmin` / `require_plan` | `MAIN` · `TESTADO` |
| B8 | API → S3 | URL pré-assinada de TTL curto; cliente nunca recebe credencial de bucket | `MAIN` |
| B9 | CI → produção | SSH com chave em secret do GitHub | `MAIN` |

**Observação sobre B2:** o token é validado **e** o usuário é relido do banco a
cada requisição, incluindo `deleted_at` (LGPD) e `is_active`. Isso significa que
desativar ou excluir um usuário tem efeito **imediato**, sem esperar expiração
de token — propriedade forte, e provavelmente não intencional como mecanismo de
revogação. Ver §6.

---

## 4. Modelo de identidade e autoridade

### Entidades

| Entidade | Tabela | Papel |
|---|---|---|
| **User** | `users` | Identidade que autentica. Campos de autoridade: `role`, `account_type`, `tenant_id`, `is_active`, `deleted_at` |
| **Tenant** | `tenants` | Organização. `slug` derivado do CNPJ (`cnpj-<CNPJ>`) ou informado |
| **Membership** | `user_tenants` | Vínculo N:N `user`↔`tenant`, com `role` e `is_default` |
| **Owner** | — | **Não é entidade.** "Dono" é `User.tenant_id == tenant.id`. Ver §7 |
| **Admin** | — | `User.role == "admin"`, atribuído no register a partir de `account_type` (§8, SEC-INV-3) |
| **Partner** | `partners`, `partner_users` | Ator sem `tenant_id` (RFC-0026) |
| **Grant** | `early_grants` / `early_adopters` | Licença que **precede** a assinatura; resolvida por `resolve_effective_license` |
| **Billing** | `plans`, `subscriptions`, `usage_tracking` | Governa entitlement de recurso e franquia |
| **CNPJ** | `users.cnpj`, `tenants.slug` | Identificador **público**; ver §8 |
| **Convite** | — | **NÃO EXISTE.** Não há fluxo de convite implementado. Ver §13 |
| **Matriz / filial** | — | **NÃO EXISTE** no domínio. `plans.max_cnpj` limita quantidade de vínculos, não modela hierarquia. Ver §13 |
| **Representação** | — | **NÃO IMPLEMENTADA**. Ver §13 |

### Autoridade — onde é verificada no servidor

| Relação | Verificação | Arquivo | Estado |
|---|---|---|---|
| usuário autenticado | decode JWT + releitura no banco + `is_active` + `deleted_at` | `api/deps.py:38-70` | `MAIN` · `TESTADO` |
| plano efetivo (grant tem precedência) | `_get_effective_plan` → `resolve_effective_license` | `api/plan_gate.py:237` | `MAIN` · `TESTADO` |
| recurso restrito por plano | `require_plan(*slugs)` | `api/plan_gate.py:62` | `MAIN` · `TESTADO` |
| franquia de uso | `check_usage_limit` (pré-checagem) + `increment_usage` (consumo atômico) | `api/plan_gate.py:84,154` | `MAIN` · `REGRESSÃO PERMANENTE` (`test_trial_regua.py`) |
| superadmin | `require_superadmin` | `routers/admin.py` | `MAIN` · `TESTADO` |
| acesso ao tenant no switch | `SELECT UserTenant WHERE user_id AND tenant_id` → 403 | `routers/auth.py:736-747` | `MAIN` |
| ingresso em tenant povoado | contagem de **donos** → 409 | `routers/auth.py:338-355` | `MAIN` · `REGRESSÃO PERMANENTE` |
| dado de domínio | `WHERE tenant_id == current_user.tenant_id` | `routers/documents.py:278,324,356`, `jobs.py:192` | `MAIN` |
| criação de API key | `has_api_access` do plano efetivo | `routers/public_api.py:253` | `MAIN` · §9 |

**`role` vs `plano` — distinção que importa.** `role` (`admin`/`contador`/`user`)
governa autoridade **dentro** do tenant. `plano` governa **quais recursos**
existem. São eixos independentes: ser `admin` de um tenant Trial não concede API.

---

## 5. Fluxos sensíveis

| Fluxo | Entry point | Ator | Pré-condição | Controle server-side | Dados afetados |
|---|---|---|---|---|---|
| register | `POST /api/v1/auth/register` | anônimo | e-mail livre | e-mail único (409); CNPJ validado na Receita; **contenção de tenant povoado** (409 se houver dono); `role` derivado de `account_type` **auto-declarado** | cria `User`, `Tenant`, `Subscription` trial |
| login | `POST /api/v1/auth/login` | anônimo | credencial | hash de senha (passlib); `is_active`; emite JWT 8h | — |
| recuperação de senha | `POST /api/v1/auth/forgot-password` | anônimo | e-mail | token de e-mail; envio por Resend | `email_verification_token` |
| criar/associar CNPJ | `POST /api/v1/auth/add-cnpj` | autenticado | `account_type == "contador"` (403 caso contrário); limite `plans.max_cnpj` | CNPJ validado na Receita; cria `UserTenant` **sem dono** | cria `Tenant` + membership |
| criar tenant | implícito no register e no add-cnpj | — | — | `_get_or_create_tenant_for_cnpj` | `tenants` |
| convite | — | — | — | **não existe** | — |
| grants | `routers/founding_partners.py` | superadmin / fluxo de licenciamento | — | `resolve_effective_license` dá precedência ao grant sobre a assinatura | `early_grants` |
| troca de tenant | `POST /api/v1/auth/switch-tenant` | autenticado | membership existente | 403 sem membership; emite JWT novo com claim `tenant_id` | **nenhum dado** — ver §7 |
| documentos | `GET/POST /api/v1/documents` | autenticado | sessão | filtro por `current_user.tenant_id` | `documents` |
| upload XML | `POST /api/v1/validate-xml/*` | autenticado | plano + franquia | `check_usage_limit` antes, `increment_usage` depois | `documents`, `jobs`, S3 |
| upload SPED | `POST /api/v1/sped/*` | autenticado | sessão | `Authorization: Bearer` | `sped_ingestion_runs`, S3 |
| exportação | `GET /api/v1/documents/{id}/download` | autenticado | dono do tenant do documento | filtro por tenant + URL pré-assinada TTL 900s | S3 |
| API keys | `POST/GET/DELETE /api/v1/api-keys` | autenticado | **`has_api_access`** na criação | criação: 403 sem entitlement; listagem/revogação: por `user_id` | `api_keys` |
| API pay-per-call | `POST /api/v1/public-api/classify` | integrador | `X-API-Key` válida com saldo | hash + `is_active` + saldo > 0; **não revalida plano** (§9) | debita `credits_balance` |
| webhook Asaas | `POST /api/v1/webhooks/asaas` | Asaas | — | header `asaas-access-token` conferido; **sempre 200** para evitar retry | `payments`, `subscriptions` |
| webhook Rumy | `POST /api/v1/webhooks/rumy` | Rumy | `RUMY_WEBHOOK_ENABLED` | **404 quando a flag está off (default)**; assinatura por header | handoff |
| operação administrativa | `/api/v1/admin/*` | superadmin | `require_superadmin` | grava `AdminAuditLog` | multi-tenant |
| diagnóstico público | `POST /api/v1/public/validate` | anônimo | — | rate limit por IP; **processa em memória e descarta** | nenhum persistido |
| calculadora pública | `POST /api/v1/public/calculadora/*` | anônimo | — | rate limit por IP + limite diário; validação de entrada (422) | nenhum |

---

## 6. Sessão e credenciais

### Token de sessão

| Propriedade | Valor | Estado |
|---|---|---|
| Tipo | JWT, `HS256` (`config.py:22`) | `MAIN` |
| Expiração | `JWT_EXPIRES_MIN = 480` → **8 horas** | `MAIN` |
| Claims | `sub`, `actor_type`, `tenant_id`, `role`, `account_type` | `MAIN` |
| **Refresh token** | **NÃO EXISTE** | — |
| **Logout server-side** | **NÃO EXISTE** — nenhum endpoint de logout | — |
| **Revogação / blacklist** | **NÃO EXISTE** — nenhuma denylist, nenhum `token_version` | — |

**Como revogação acontece de fato, apesar de não haver mecanismo:** `deps.py`
relê o usuário no banco a cada requisição e recusa se `is_active == False` ou
`deleted_at != None`. Então desativar o usuário derruba o acesso **imediatamente**.
`NÃO DEMONSTRADO` que isso esteja documentado ou tratado como controle
intencional — é efeito colateral da releitura, e um refactor que cacheasse o
usuário o eliminaria em silêncio.

### API keys

| Propriedade | Valor | Estado |
|---|---|---|
| Formato | prefixo `tribultz_sk_`, armazenada como **SHA-256** (`public_api.py`) | `MAIN` |
| Exibição | chave em claro **uma única vez**, na criação | `MAIN` |
| Limite | 5 ativas por conta | `MAIN` |
| Crédito inicial | 100 na criação | `MAIN` |
| Revogação | `DELETE /api/v1/api-keys/{id}`, por `user_id` | `MAIN` |
| **Expiração** | **NÃO EXISTE** — chave não vence | — |
| **Rotação** | **NÃO EXISTE** — não há fluxo de rotação | — |
| **Scopes** | **NÃO EXISTEM** — a chave dá acesso a todo endpoint de `X-API-Key` | — |
| Revalidação de plano no uso | **NÃO OCORRE** — ver §9 | — |

### Rate limits

`RateLimiter` (`services/rate_limit.py`) usa Redis quando disponível e cai para
**dicionário em memória do processo** quando não. Em produção há Redis, então o
limite é compartilhado; **no fallback o limite passa a ser por processo**, e
como a API roda com múltiplos processos isso multiplica o teto efetivo.
`NÃO DEMONSTRADO` que exista alarme para o fallback ocorrer silenciosamente.

Onde há limite, por IP (`MAIN`, verificado em `routers/auth.py`):

| Rota | Teto | Extra |
|---|---|---|
| `login` | **5** por janela (`auth.py:38,164`) | + **captcha Turnstile** (`verify_captcha`, `auth.py:166`) |
| `register` | **3** por janela (`auth.py:41,297`) | + **captcha Turnstile** (`auth.py:299`) |
| `forgot-password` | limitado (`_forgot_limiter`, `auth.py:857`) | — |
| reenvio de verificação | limitado (`auth.py:596`) | — |
| calculadora pública | por IP + teto diário | — |
| `public.py` (diagnóstico) | por IP | — |

Default do limitador: `limit = 10` por janela (`rate_limit.py:19`), sobrescrito
por rota onde é mais restritivo.

> **Correção de uma afirmação minha.** Numa primeira passagem eu havia registrado
> como lacuna "não encontrei rate limit em login/register/forgot-password".
> **Estava errado** — existem os três, e ainda há captcha em login e register. Só
> apareceu porque fui verificar antes de commitar. Registro o erro porque um
> baseline que inventa lacuna manda o analista caçar fantasma, o que custa tanto
> quanto esconder lacuna real.

---

## 7. Multi-tenancy

### Como o tenant é determinado

**Pela coluna `User.tenant_id`**, lida do banco a cada requisição. Não pela
claim do JWT.

### Como o acesso é autorizado

Filtro explícito em cada consulta de domínio:
`WHERE <tabela>.tenant_id == current_user.tenant_id`. Não há Row-Level Security
no Postgres — o isolamento é **de aplicação**, e depende de cada consulta
lembrar do filtro. `NÃO DEMONSTRADO` que exista varredura automática garantindo
que nenhuma consulta de domínio esqueça o filtro.

### Onde IDs controlados pelo cliente entram

| Entrada | Tratamento | Avaliação |
|---|---|---|
| `X-Tenant-Id` (header) | **liberado no CORS (`main.py:69`) e nunca lido pelo servidor** | o frontend envia (ex.: `uploadSped`); nenhum código do backend o consulta. Hoje é inerte — mas é uma porta declarada aberta que um handler futuro pode passar a ler sem perceber que é dado do cliente |
| `tenant_id` no corpo do `switch-tenant` | validado contra `UserTenant` do usuário → 403 | correto |
| claim `tenant_id` do JWT | **nenhum código de autorização a lê** | ver abaixo |
| `cnpj` no register / add-cnpj | validado na Receita; determina o slug do tenant | é dado **público** — base do SEC-INV-3 |
| `{id}` de documento/job na URL | consulta sempre casada com `tenant_id` do usuário | correto nos pontos verificados |

### Duas fontes de "tenant atual" — achado

`switch-tenant` verifica o membership e emite um JWT novo com a claim
`tenant_id` do tenant escolhido. **A autorização, porém, usa
`current_user.tenant_id` — a coluna, que o switch não altera.**

Consequências:

1. Trocar de tenant muda a claim e a interface, mas **não** muda o escopo dos
   dados no servidor. É o que o #626 registrou como "switch_tenant é cosmético
   para leitura". Hoje isso é *fail-closed*: o contador não passa a ler o dado do
   cliente.
2. **O risco é o inverso do óbvio:** o dia em que algum handler novo autorizar
   pela claim (que é o dado mais "à mão" no token), ele passará a confiar num
   valor que o `switch-tenant` deixa o usuário escolher entre seus memberships —
   e divergirá de todo o resto do código, que usa a coluna.

Estado: `MAIN`. `NÃO DEMONSTRADO` que exista teste ou lint impedindo autorização
pela claim.

### Owner × Admin × Membership

| Conceito | Como é representado | Onde importa |
|---|---|---|
| **Owner** | `User.tenant_id == tenant.id` | é o que a contenção do #625 conta |
| **Membership** | linha em `user_tenants` | é o que o `switch-tenant` exige |
| **Admin** | `User.role == "admin"` | autoridade dentro do tenant |

**A divergência entre os dois primeiros é a origem do #626:** o `/add-cnpj` cria
membership **sem** owner, e a contenção só conta owners.

### Invariantes com regressão permanente

| Invariante | Onde | Estado |
|---|---|---|
| SEC-INV-1/2 — CNPJ público não concede ingresso em tenant **com dono** | `tests/security/test_tenant_isolation_r10.py` | `REGRESSÃO PERMANENTE` |
| Bypass via shell reservado (`/add-cnpj`) — **caracterização, não proteção** | idem, `test_bypass_da_contencao_via_shell_reservado_por_add_cnpj` | `REGRESSÃO PERMANENTE` do **comportamento atual, indesejado** |
| Trial: franquia vitalícia, expiração por data, consumo concorrente | `tests/test_trial_regua.py` | `REGRESSÃO PERMANENTE` |
| SEC-INV-3 — `account_type` não concede autoridade sobre terceiro | — | **sem regressão** — invariante ferida, ver §8 |

⚠️ O teste do bypass é **verde para o comportamento errado**. Quem ler a suíte
sem ler o docstring pode concluir que o caso está protegido. Está *documentado*,
não protegido.

---

## 8. Estado dos achados conhecidos

| ID | Descrição | Estado | Produção? | Correção | Regressão | Resíduo |
|---|---|---|---|---|---|---|
| **#625** | CNPJ público concedia ingresso admin cross-tenant em tenant povoado (P0) | `MERGEADO` · `DEPLOYADO` | contido | contagem de donos → 409 (`auth.py:338`) | `REGRESSÃO PERMANENTE` | sim → #626 |
| **#626** / SEC-INV-3 | `account_type` auto-declarado concede `role=admin`; e a contenção é **bypassável** via shell reservado por `/add-cnpj` | **ABERTA** · P1 aceito pelo QA em 17/08 | **sim, alcançável** | **nenhuma** | caracterização em `MAIN` (`REGRESSÃO PERMANENTE` do estado atual) | é o resíduo |
| **#627** | PR do QA com o teste de caracterização | `PR ABERTO`, **substituído** | — | — | — | conflito add/add pós-squash do #625 |
| **#664** | Porta o teste do #627 para `main` | `MERGEADO` · `DEPLOYADO` | — | somente teste | `REGRESSÃO PERMANENTE` | — |
| **AUTH DEV** | — | **NÃO DEMONSTRADO** | ? | ? | ? | ver nota abaixo |
| **Trial/API entitlement** | endpoint de criação de API key não consultava `has_api_access` | `MERGEADO` · `DEPLOYADO` (#647) | corrigido na criação | gate em `public_api.py:253` | **fraca** — o teste faz `grep` no fonte, não exercita comportamento | **sim** — o consumo não revalida plano (§9) |
| **Copy de API no Trial** | 6 superfícies apresentavam API/créditos como benefício do Trial, incluindo FAQ em JSON-LD afirmando o contrário da decisão | `MERGEADO` · `DEPLOYADO` (#665) | corrigido | copy derivada da política única | `REGRESSÃO PERMANENTE` (`trial.test.ts`) | nenhum |
| **#617** | `pCBS`/`pIBSUF`/`pIBSMun` tratados como fração — FATAL em nota correta, e snippet entregue ao cliente com alíquota 100× menor | `MERGEADO` · `DEPLOYADO` (#629) | corrigido em 4 sites | divisão por 100 na fronteira | `REGRESSÃO PERMANENTE` | não é achado de segurança; entra por integridade de saída |

**Sobre AUTH DEV:** não localizei nenhum artefato com esse nome no código —
zero ocorrências de `AUTH_DEV`, `auth_dev` ou variantes em `backend/app`. A
única referência que encontrei é textual, no corpo do PR #627: *"não toca AUTH
DEV (NO-GO do Round 10)"*. **Não documento estado técnico de algo que não
consegui localizar.** Se AUTH DEV é um fluxo, flag ou decisão, preciso do
ponteiro do QA para incluí-lo — ver §13.

---

## 9. Estado Trial/API

Conforme a ordem, aqui **não houve exploração adicional**: é o que está
documentado e verificado.

| Pergunta | Resposta | Estado |
|---|---|---|
| `trial.api = false` está enforced? | **Na criação de credencial, sim.** `POST /api/v1/api-keys` consulta `_get_effective_plan` e exige `has_api_access` → 403 (`public_api.py:253-259`) | `MAIN` · `DEPLOYADO` |
| Onde `has_api_access` é consultado? | **Um único lugar:** `public_api.py:253`. O valor vem de `plans.has_api_access`, que é `FALSE` para `trial` desde a migration `0004` (maio) | `MAIN` |
| Quais endpoints criam/gerenciam API keys? | `POST /api/v1/api-keys` (cria, **com gate**), `GET /api/v1/api-keys` (lista, por `user_id`), `DELETE /api/v1/api-keys/{id}` (revoga, por `user_id`) | `MAIN` |
| Existe outro caminho conhecido de obtenção/uso? | **Sim, de uso.** `_resolve_api_key` (`public_api.py:133`) valida apenas hash, `is_active` e saldo. **Não revalida o plano.** Uma chave obtida enquanto havia direito segue funcionando depois que o direito termina — chave criada antes do gate; upgrade → cria chave → volta a Trial; grant expirado | `MAIN` |
| Exposição viva | **zero chaves ativas em produção** na consulta de 17/08 — defeito latente, não incidente | `PRODUÇÃO` |
| Regressões existentes | `test_item4_endpoint_de_api_key_respeita_has_api_access` faz **`assert "has_api_access" in fonte`** — grep no código-fonte. Não exercita comportamento. **Nenhum** teste cobre revalidação no consumo, porque ela não existe | `TESTADO` (fraco) |

**Leitura honesta:** o entitlement está fechado na porta de emissão e aberto na
porta de uso. Enquanto não existir chave emitida, a diferença é teórica.

---

## 10. Upload e documentos

```
entrada → validação → processamento → armazenamento → associação tenant → retenção → acesso
```

| Etapa | Mecanismo | Estado |
|---|---|---|
| **entrada** | `POST` autenticado (XML, SPED). Público equivalente: `/api/v1/public/validate` | `MAIN` |
| **validação** | extensão `.xml`; limite de **2 MB** (`diagnostico/page.tsx:47` no cliente; validação de conteúdo no motor); parsing por regex, **não por XSD** | `MAIN` |
| **processamento** | motor determinístico `validate_xml`; jobs longos via Celery | `MAIN` |
| **armazenamento** | S3 (Magalu). `put_object` com credencial de servidor; cliente nunca recebe credencial | `MAIN` |
| **associação tenant** | `Document.tenant_id = current_user.tenant_id` na criação | `MAIN` |
| **retenção / descarte** | `task_j_retention.py` — `RETENTION_DAYS = 365`, purga documentos expirados | `MAIN` · `TESTADO` (`test_document_retention.py`) |
| **acesso / exportação** | URL pré-assinada, `DOWNLOAD_TTL_SECONDS = 900` (15 min), emitida só após filtro por tenant | `MAIN` |
| **diagnóstico público** | processado **em memória e descartado**; nada persistido. Política publicada em `/data-policy` e no endpoint `/api/v1/public/data-policy` (6 compromissos) | `MAIN` · `PRODUÇÃO` |

**`NÃO DEMONSTRADO`:** que o parsing por regex esteja protegido contra XXE ou
entity expansion. Como não há parser XML de árvore no caminho verificado (é
regex sobre texto), o vetor clássico de XXE provavelmente **não se aplica** —
mas eu não auditei todos os caminhos, e "provavelmente não se aplica" não é
demonstração. Ver §13.

---

## 11. Logging e auditoria

| Evento | Onde | Correlação |
|---|---|---|
| Ação administrativa | `AdminAuditLog` (`admin.py:492`, `billing.py:38`), consultável em `/api/v1/admin/audit-log` | ator + ação + alvo |
| `register` bloqueado por tenant povoado | `logger.info("register_blocked_existing_tenant", extra={cnpj, tenant_slug})` | CNPJ + slug |
| CNPJ adicionado | `logger.info("cnpj_added", extra={user_id, cnpj, tenant_slug})` | user + tenant |
| Webhook rejeitado | `logger.warning` em Asaas e Rumy | motivo |
| Requisição de validação | `X-Transaction-Id` propagado pelo cliente | transação ponta a ponta |
| Falha de probe de saúde | `logger.warning` por subsistema | — |
| Exceção não tratada | Sentry (`init_sentry`, no-op sem DSN) | — |

**`NÃO DEMONSTRADO`:** política de retenção de log; se logs de aplicação vão
além do stdout do container; se há alerta acionável sobre eventos de segurança —
o workflow `monitor` cobre disponibilidade, não autorização. Nenhum log real
consta deste documento.

---

## 12. CI/CD e regressão

`backend-gates` (Pytest → auditoria arquitetural informativa → Ruff → Pyright) e
`frontend-build` (`npm test` → `npm run build`). Merge em `main` afetando
`backend/**` ou `infra/**` dispara `deploy-prod` via SSH, com rollback
automático em falha.

| Área | Suíte | Natureza |
|---|---|---|
| AUTH | `tests/test_auth.py` | comportamento |
| Tenant / isolamento | `tests/security/test_tenant_isolation_r10.py` | SEC-INV-1/2 protegidas; bypass do #626 **caracterizado** |
| Autorização admin | `tests/test_admin_access.py`, `test_founding_partners_admin.py`, `test_partner_admin.py`, `test_partner_auth.py` | comportamento |
| API entitlement | `tests/test_trial_regua.py` | 9 itens; o de API key é **grep no fonte** |
| Grants | `tests/test_early_adopter_cockpit.py` | comportamento |
| Upload / retenção | `tests/test_document_retention.py`, `test_documents.py`, `test_sped*.py` | comportamento |
| Feed público | `tests/test_publish_news_script.py` (35 casos) | impede conteúdo interno no feed |

**Nota de método adotada em 17/08:** guard só conta como entregue depois de
**falhar de propósito** uma vez. Dois guards escritos nesta semana passaram
verdes sem verificar nada — um por `\w` não casar acento em JS, outro por usar
tipo de commit não publicável.

---

## 13. Lacunas conhecidas

Controles cuja existência ou cobertura eu **não** considero demonstrada. Esta é
a seção mais importante para o agente de segurança.

| # | Lacuna | Por que não está demonstrada |
|---|---|---|
| L1 | **SEC-INV-3 sem correção** | `account_type` auto-declarado ainda concede `role=admin`, e a contenção é bypassável via shell reservado. Alcançável em produção. Nenhuma correção — fechar exige decidir o fluxo de ingresso autorizado |
| L2 | **Fluxo de convite não existe** | a contenção do #625 diz que o ingresso de 2º usuário "exige fluxo autorizado explícito"; esse fluxo **não foi implementado**, então o estado é: 2º usuário simplesmente não entra |
| L3 | **Revalidação de plano no uso de API key** | o entitlement é verificado só na emissão |
| L4 | **Sem expiração, rotação ou scope de API key** | chave é perpétua e total |
| L5 | **Sem logout, refresh ou revogação de token** | JWT de 8h só "morre" pelo relógio; a revogação efetiva é efeito colateral da releitura do usuário, não controle declarado |
| L7 | **Fallback silencioso do rate limiter para memória** | sem Redis o limite passa a ser por processo, multiplicando o teto; sem alarme conhecido |
| L8 | **Sem RLS no Postgres** | isolamento depende de cada consulta lembrar o filtro; não há varredura garantindo isso |
| L9 | **Duas fontes de "tenant atual"** | claim do JWT × coluna do usuário; hoje só a coluna autoriza, mas nada impede um handler futuro de usar a claim |
| L10 | **`X-Tenant-Id` declarado no CORS e não lido** | porta aberta e inerte; risco é de adoção futura por engano |
| L11 | **AUTH DEV não localizado** | referenciado em texto de PR, ausente do código. Preciso do ponteiro do QA |
| L12 | **XXE / entity expansion no parsing de XML** | o caminho verificado é regex sobre texto, o que provavelmente afasta o vetor — mas não auditei todos os caminhos |
| L13 | **Sem ambiente de ensaio** | mudança de autorização vai de local a produção sem intermediário além do CI |
| L14 | **Retenção e alerta de log** | não há política de retenção conhecida nem alerta sobre evento de autorização |
| L15 | **Cópias antigas de `.env` na VM** | 5 arquivos com credenciais **ainda válidas** (ordem permanente de não rotacionar). Permissões corretas (`0600 root:root`), mas o raio de exposição de um comprometimento do host é maior que a contagem sugere |
| L16 | **Cobertura de teste do gate de API é `grep`** | `assert "has_api_access" in fonte` não exercita comportamento; um refactor que mantivesse a string e removesse o gate passaria verde |
| L17 | **`select-mode` / modos de teste** | gate verificado: `if user.role != "superadmin": 403` (`auth.py:801-805`). O que **não** auditei é o efeito do modo escolhido a jusante — o JWT novo carrega `plan_slug` de teste, e não verifiquei se algum handler trata esse plano como entitlement real |
| L18 | **Matriz/filial e representação inexistentes** | a precificação comunica "matriz + filiais" (achado anterior de Produto) e o domínio não modela hierarquia; `max_cnpj` conta vínculos |

---

## Rastreabilidade

Este documento afirma o que foi lido no commit
`eb968915a230b4b14038870d06b151827a7dd702` e o que foi observado em produção em
17/08/2026. Onde há divergência entre relatório anterior e código, **o código
prevaleceu**. Onde não houve verificação, está escrito `NÃO DEMONSTRADO`.

Nenhum segredo, token, credencial, connection string ou documento fiscal real
consta deste arquivo.
