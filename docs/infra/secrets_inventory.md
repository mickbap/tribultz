# Inventário de Segredos — Tribultz

> Validado em 2026-07-15. **Este arquivo não contém valores de credenciais** — apenas onde vivem, como validar e o que está pendente. Pode ser commitado.

## Fonte de verdade

**`/opt/tribultz/.env` na VM de produção** (root, `0600`). É o arquivo que os containers realmente leem.

Cópias locais derivam dela e ficam obsoletas em silêncio. Em 2026-07-15 o `.env.prod` local estava 3 meses defasado e não tinha `GITHUB_TOKEN`, `NEWS_PUBLISH_TOKEN`, `SENTRY_DSN` nem `SENTRY_TRACES_SAMPLE_RATE`. Antes de tratar qualquer cópia local como referência, sincronize:

```bash
cp .env.prod ".env.prod.bak.$(date +%Y%m%d-%H%M%S)"
ssh -i ~/.ssh/id_ed25519 ubuntu@201.54.20.18 'sudo cat /opt/tribultz/.env' > .env.prod
```

## Onde os segredos estão hoje

| Local | Conteúdo | Versionado? |
|-------|----------|-------------|
| `/opt/tribultz/.env` (VM) | 48 chaves — fonte de verdade | não (fora do git) |
| `.env.prod` (local) | espelho da VM | não — `.gitignore:139` |
| `.env` (local) | dev; maioria placeholder, não credencial real | não — `.gitignore:138` |
| `secrets/credentials.md` | credenciais de produção em markdown | não — `.gitignore:143` |
| `.secrets/auth.json` | login de app (email/password/tenant) | não — `.gitignore:213` |
| `frontend/.vercel/*.local` | só `VERCEL_OIDC_TOKEN` (efêmero) e vars públicas | não — `.gitignore:236` |
| GitHub Actions Secrets | deploy: `MAGALU_SSH_KEY`, `MAGALU_SSH_HOST`, `MAGALU_SSH_USER` | n/a |
| Memória do Claude | `reference_magalu_cloud.md`, `reference_services.md` | n/a |

Nenhum segredo está rastreado pelo git — só `.env.prod.template` e os `.env.example`. Verificado em 2026-07-15.

Não existe token de deploy da Vercel: o deploy do frontend é via integração GitHub, não via token.

## Attio — criação e armazenamento da API key (PO-2026-07-CRM-001)

> Pendente: ainda não existe `ATTIO_API_KEY` em nenhum lugar da lista acima. Passos abaixo para gerar e guardar — sem valores reais neste arquivo.

**Pré-requisito**: precisa ser **admin do workspace Attio**. Se não for, peça para quem é.

1. No Attio, clique no dropdown ao lado do nome do workspace → **Workspace settings**.
2. Aba **Developers**.
3. **+ New access token**.
4. Dê um nome identificável (ex.: `tribultz-backend-prod`) e marque os **Scopes** necessários — no mínimo leitura+escrita de Objects/Records (companies, people) e de Lists (pipeline/deals), mais o scope de Notes e o de Webhooks se formos consumir eventos (item 9 da PO). A lista exata de scopes aparece na própria tela de criação — confirme lá, não neste doc.
5. Crie o token. **Aparece uma única vez** — copie imediatamente. Não expira sozinho, mas pode ser revogado/deletado a qualquer momento na mesma tela (ícone de olho para reexibir, menu de três pontos para editar/apagar).
6. Guarde seguindo o mesmo padrão de todo segredo deste projeto (ver "Onde os segredos estão hoje" acima): a única fonte de verdade é `/opt/tribultz/.env` na VM — adicione `ATTIO_API_KEY=<valor>` lá (nunca num commit, nunca colado no chat). Replique para `.env.prod` local e `secrets/credentials.md` se for usar essas cópias.
7. `ATTIO_WORKSPACE` não é segredo (é o slug/ID do workspace, visível na URL do Attio) — pode ficar em `.env.example` com placeholder.
8. `ATTIO_WEBHOOK_SECRET` é gerado pelo Attio ao criar o webhook (item 9 da PO), não na tela de token — trate com o mesmo cuidado do token.

Documentação oficial: [Generate an API key (Attio Help Center)](https://attio.com/help/apps/other-apps/generating-an-api-key) · [Authenticating requests (Attio Docs)](https://docs.attio.com/rest-api/guides/authentication).

## Como validar (sem imprimir valores)

```bash
g(){ grep -E "^$1=" .env.prod | head -1 | cut -d= -f2- | tr -d '"'"'"'\r'; }

# OpenRouter / Asaas / Resend / HubSpot — espera-se HTTP 200
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $(g OPENROUTER_API_KEY)" https://openrouter.ai/api/v1/key
curl -s -o /dev/null -w '%{http_code}\n' -H "access_token: $(g ASAAS_API_KEY)"          https://api.asaas.com/v3/myAccount
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $(g SMTP_PASSWORD)"   https://api.resend.com/domains
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $(g HUBSPOT_PRIVATE_APP_TOKEN)" 'https://api.hubapi.com/crm/v3/objects/contacts?limit=1'

# Attio — espera-se HTTP 200 (token ausente/errado responde 401)
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $(g ATTIO_API_KEY)" https://api.attio.com/v2/objects

# Object Storage Magalu
curl -s -o /dev/null -w '%{http_code}\n' --aws-sigv4 "aws:amz:$(g S3_REGION):s3" \
  --user "$(g S3_ACCESS_KEY):$(g S3_SECRET_KEY)" "$(g S3_ENDPOINT)/$(g S3_BUCKET)/?list-type=2&max-keys=1"

# Cloudflare — espera-se "success":true e "status":"active"
curl -s -H "Authorization: Bearer <token>" https://api.cloudflare.com/client/v4/user/tokens/verify

# Cloudflare Analytics (tráfego do site, painel admin, #518) — token dedicado,
# escopo Zone:Analytics:Read + Zone:Zone:Read só na zona tribultz.com.br —
# espera-se "success":true e um objeto "data" com viewer.zones
curl -s -X POST https://api.cloudflare.com/client/v4/graphql \
  -H "Authorization: Bearer $(g CLOUDFLARE_ANALYTICS_TOKEN)" -H "Content-Type: application/json" \
  -d '{"query":"query($z:string!){viewer{zones(filter:{zoneTag:$z}){httpRequests1dGroups(limit:1){uniq{uniques}}}}}","variables":{"z":"0dca11f87046e628725aba0347548ccf"}}'

# Magalu CLI e SSH
mgc virtual-machine instances list --api-key <key>
ssh -i ~/.ssh/id_ed25519 ubuntu@201.54.20.18 'echo ok'
```

Para comparar cópia local com a VM sem expor valores, compare o md5 de cada valor chave a chave — foi assim que o drift de 3 meses foi detectado.

## Estado em 2026-07-15

Válidos: Magalu (API key, SSH, Object Storage), Cloudflare, Turnstile, Asaas produção, OpenRouter, HubSpot, GitHub.

## Resolvido (2026-08-07): Resend (`SMTP_PASSWORD`)

Chave revogada (401) desde antes de 15/07 — corrigido mediante **exceção pontual**
à ordem de não-rotação, autorizada explicitamente pelo usuário (o caso já estava
registrado como pendência abaixo desde 15/07; a ordem geral permanece em vigor
para as demais credenciais). Nova chave gerada no dashboard do Resend, propagada
via `sed` remoto direto em `/opt/tribultz/.env` (sem puxar o arquivo inteiro pra
uma sessão) e no `.env.prod` local. `docker compose restart api worker beat`
aplicado; `/health/deep` confirmou `"email":"ok"` pós-restart.
**`secrets/credentials.md` não existe neste Mac** (provável arquivo só-Windows,
condizente com a seção "Por que funciona no Windows e não no Mac" abaixo) —
não atualizado; pendente confirmar/replicar na máquina onde o arquivo vive.

## Resolvido (2026-07-29): `CLOUDFLARE_ANALYTICS_TOKEN`

Gerado e testado (E2E, local) para a seção de tráfego do site no painel admin
(#518) — token dedicado, escopo mínimo (`Zone:Analytics:Read` + `Zone:Zone:Read`
só na zona `tribultz.com.br`), sem custo. Adicionado a `/opt/tribultz/.env` na
VM entre 22/07 e 29/07 (fora desta sessão); a cópia local do `.env.prod` estava
desatualizada e foi resincronizada em 29/07 via `bash tools/check_access.sh`
(seção 5 apontou o drift). `CLOUDFLARE_ZONE_ID` (`0dca11f87046e628725aba0347548ccf`)
não é segredo — já tem default no `app/config.py`.

> 🔒 **Ordem vigente (2026-07-15): NÃO rotacionar, revogar nem encerrar sessão de credencial alguma enquanto o produto não escala.** Vale inclusive para as pendências listadas abaixo — inclusive as comprovadamente vazadas ou já revogadas. Documentar e seguir; não propor rotação de novo. O objetivo da fase é acesso livre e sem atrito a partir de Windows e Mac. Reavaliar quando o produto escalar.
>
> Contexto que sustenta a ordem: **deploy não usa credencial local alguma** — frontend pelo `vercel[bot]` (GitHub App), backend pelo Actions com `MAGALU_SSH_KEY`. Nenhuma ação sobre credencial local pode conflitar com deploy.

**Pendências abertas** (registradas, sem ação — ver ordem acima)**:**

1. **`GITHUB_TOKEN` de produção é um OAuth pessoal.** O valor em `/opt/tribultz/.env` é byte a byte o mesmo token `gho_` do `gh` CLI do `mickbap` (confirmado por hash). Consequências: `gh auth logout`, troca de máquina ou expiração do OAuth derrubam produção junto; e o escopo `repo` alcança todos os repositórios da conta, não só este. Deveria ser um fine-grained PAT restrito a `mickbap/tribultz` ou um GitHub App.

2. **`gh` CLI sem escopo `workflow`.** Escopos atuais: `gist`, `read:org`, `repo`. Alterar `.github/workflows/**` via API/CLI falha; só via push.

3. **`refresh_token` do mgc exposto em transcript** (Mac, 2026-07-15). Um `mgc auth tenant set` imprimiu `access_token` e `refresh_token` completos em texto puro numa sessão de agente. O `refresh_token` continua cunhando access tokens até um `mgc auth logout` — que, por ordem vigente, **não será executado**. Prevenção: sempre redirecionar a saída desse comando (`> /dev/null 2>&1`).

## Por que "funciona no Windows" e não no Mac

Validado em 2026-07-15. A intuição de que Magalu e Vercel "acessam via GitHub por causa dos deploys" mistura duas coisas distintas — **deploy** e **acesso operacional** — e a resposta é diferente para cada serviço.

**Magalu: não existe login nenhum em máquina alguma.** `~/AppData/Roaming/mgc/default/auth.yaml` (Windows) tem `access_token`, `refresh_token`, `access_key_id` e `secret_access_key` **todos vazios**. Sem credencial explícita, o mgc falha com `RefreshToken is not set`. O acesso "funciona" no Windows apenas porque a API key é injetada a cada comando via `--api-key`, lida de `secrets/credentials.md` / memória do Claude — nenhum dos dois vai para o Mac. **Essa é a causa raiz do bloqueio no Mac: não há o que "levar junto" além da string da key.**

Duas formas de resolver, ambas verificadas:
- **`MGC_API_KEY` como variável de ambiente** — funciona, apesar de não aparecer em `mgc --help`. É o caminho mais simples.
- **`mgc auth login`** — fluxo OAuth por navegador. Falha em bash headless (sem TTY), mas funciona num Mac com GUI. Gera sessão persistente de verdade.

Não existe caminho para *persistir uma key já existente*: `mgc auth api-key` só tem `create`, `get`, `list` e `revoke`.

### Armadilha dos dois tenants

A conta tem **dois tenants Magalu**, e `mgc auth login` cai no **errado** por padrão:

| Tenant | UUID | Hospeda a VM? |
|--------|------|---------------|
| `mickel.baptista@outlook.com` (pessoal) | `ff4cd2a8-5f78-42d1-b047-ec90c1afe100` | não — é onde o `mgc auth login` cai por padrão |
| `mickel@6tech.net.br` (managed) | `77554d12-fe63-4697-ac4f-9bfb3bc926a4` | **sim** — `tribultz-api` e o Object Storage vivem aqui |

Sintoma: login funciona, nenhum erro aparece, e `mgc virtual-machine instances list` volta **vazio** — parece falta de permissão, mas é tenant errado.

```bash
mgc auth tenant list      # lista os dois — seguro, não imprime token
mgc auth tenant current   # mostra o ativo — seguro, não imprime token
mgc auth tenant set 77554d12-fe63-4697-ac4f-9bfb3bc926a4 > /dev/null 2>&1   # PERIGOSO sem redirect
```

> Ao conferir a saída do mgc, não filtre por `name:` ou `state:`: o CLI injeta códigos ANSI de cor **entre** a palavra e os dois-pontos, e o grep literal nunca casa — parece que a VM sumiu quando ela está lá. Filtre por um valor contíguo (ex.: `tribultz-api`) ou use `| sed -E 's/\x1b\[[0-9;]*m//g'` antes do grep.

> ⚠️ **`mgc auth tenant set` imprime `access_token` e `refresh_token` completos em texto puro no stdout.** Redirecione a saída (`> /dev/null`) e nunca rode esse comando com o terminal compartilhado, em screenshot ou em sessão de agente cujo transcript fique salvo. Um `refresh_token` vazado continua valendo até a sessão ser encerrada com `mgc auth logout`.

**Vercel: login é por máquina, e não há nada para migrar.** O CLI usa OAuth — `auth.json` guarda um access token de ~8h mais um `refreshToken` que o renova sozinho. Copiar esse arquivo para o Mac é inútil (expira e é vinculado à sessão). No Mac: `vercel login`. Só é necessário para deploy manual.

**Nenhum deploy depende do seu laptop.** O frontend é publicado pelo `vercel[bot]` via GitHub App (deployments de Production e Preview criados por ele em 2026-07-14). O backend é publicado pelo GitHub Actions via SSH, usando os secrets `MAGALU_SSH_KEY` / `MAGALU_SSH_HOST` / `MAGALU_SSH_USER`. Ou seja: mesmo com zero credencial local, **você nunca fica sem conseguir fazer deploy** — o que se perde sem credencial local é o acesso operacional (inspecionar VM, ler logs, rodar migrations).

## Verificação de acessos

`bash tools/check_access.sh` — checa SSH, mgc, gh, Vercel, drift do `.env.prod` e saúde da produção, com PASS/FAIL e a correção de cada falha. Não contém nem escreve segredos; lê a key de `$MGC_API_KEY`. Rode isso **no Mac antes de depender dele**.

## Onboarding em máquina nova (incl. Mac)

```bash
# 1. Chave SSH — o macOS RECUSA chave com permissão frouxa; o Windows tolera
chmod 600 ~/.ssh/id_ed25519
ssh-keygen -lf ~/.ssh/id_ed25519.pub   # esperado: SHA256:ydI3GwtHcGHjUvcCzFQgOp7zypbiVwqqiicGlhun7gg (tribultz-infra)
ssh -i ~/.ssh/id_ed25519 ubuntu@201.54.20.18 'echo ok'

# 2. mgc CLI — no Mac use o build darwin_arm64 (Apple Silicon) ou darwin_amd64 (Intel)
#    Releases oficiais: github.com/MagaluCloud/mgccli — confira o sha256 contra mgccli_<ver>_checksums.txt
curl -sLO https://github.com/MagaluCloud/mgccli/releases/download/v0.61.2/mgccli_0.61.2_darwin_arm64.tar.gz
shasum -a 256 mgccli_0.61.2_darwin_arm64.tar.gz    # comparar com o checksums.txt da release
tar xzf mgccli_0.61.2_darwin_arm64.tar.gz && sudo mv mgc /usr/local/bin/ && mgc --version

# 3. Credencial da Magalu — SEM isto o mgc não funciona (não há login persistido).
#    Traga a API key da máquina antiga por um canal seguro (gerenciador de senhas).
#    Opção A — variável de ambiente (verificada; não aparece no --help):
echo 'export MGC_API_KEY="<a key de tribultz-cli-tenant>"' >> ~/.zshrc && source ~/.zshrc
mgc virtual-machine instances list        # esperado: tribultz-api / running
#    Opção B — login OAuth de verdade (funciona no Mac por ter navegador):
mgc auth login

# 4. .env.prod — puxe da VM, nunca copie de outra máquina
ssh -i ~/.ssh/id_ed25519 ubuntu@201.54.20.18 'sudo cat /opt/tribultz/.env' > .env.prod

# 5. gh CLI
gh auth login

# 6. Vercel — só para deploy manual; deploy por push não precisa disto
npm i -g vercel && vercel login
cd frontend && vercel link      # org team_Yj7YsH3ejoP3hlLyQivNVlS4, projeto tribultz

# 7. Validar tudo antes de confiar na máquina
bash tools/check_access.sh
```

Não copie `~/Library/Application Support/com.vercel.cli/auth.json` nem o `auth.yaml` do mgc da máquina antiga: o primeiro expira em horas e o segundo está vazio.

`mgc auth login --headless` não funciona sem TTY — use sempre `--api-key` explícito.

No Windows, `mgc` está em `C:\mgc\mgc.exe` e `C:\mgc` foi adicionado ao PATH do usuário em 2026-07-15 (shells já abertos precisam ser reiniciados para enxergar).

## Se um dia migrar para um cofre

Avaliado em 2026-07-15 e **adiado**. Um container de segredos exposto na VM exigiria abrir porta nova para a internet — hoje o UFW só abre 22/80/443 com fail2ban, e um cofre exposto aumentaria a superfície de ataque justamente no serviço mais sensível. Para o tamanho atual do time, SOPS + age (arquivo cifrado versionado, decifrado localmente) resolve o acesso multi-máquina sem servidor nem porta aberta. Vault/Infisical só compensa com rotação automática e auditoria multi-usuário.

Qualquer migração deve usar **a VM como origem**, nunca uma cópia local.
