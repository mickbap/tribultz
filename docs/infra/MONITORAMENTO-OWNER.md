# Monitoramento do Tribultz — guia do Owner

**Para:** Mickel (Owner / superadmin)
**Versão 1 · 19 de agosto de 2026**

Como olhar o Tribultz por dentro: o que existe, onde ficam as respostas e em que
ordem procurar quando algo parece errado. Tudo aqui é acesso que você já tem.

> **Estado no momento desta escrita:** 2 superadmins ativos, 4 tenants,
> **0 Founding Partners admitidos e 0 grants ativos** — o Programa está
> provisionado mas vazio. O painel de Founding Partners vai aparecer sem linhas
> até a primeira admissão, e isso é o estado correto, não defeito.

---

## 1. Os quatro lugares de onde a verdade vem

Não são equivalentes, e confundi-los é a origem de quase todo diagnóstico errado.

| Fonte | O que ela responde | O que ela **não** responde |
|---|---|---|
| **Painel admin** (`/admin`) | o que o produto vê: tenants, usuários, uso, audit log | se a infraestrutura está sadia |
| **`/health/deep`** | se cada dependência responde agora | se o comportamento do produto está correto |
| **VM** (SSH) | estado real de containers, banco, disco, memória | histórico de quem fez o quê |
| **GitHub Actions** | o que foi entregue e se o deploy passou | se o que subiu funciona de fato |

A regra que salvou tempo repetidas vezes nesta semana: **evidência ao vivo vence
relatório**, inclusive relatório meu. Quando as duas discordam, quem manda é o
sistema.

---

## 2. Verificação de rotina — um comando

```bash
bash tools/posdeploy_check.sh "o que você quer conferir"
```

Roda em cerca de um minuto e confere, em sequência: os 7 subsistemas do
`/health/deep`, os 4 containers na VM, 20 rotas públicas, 16 rotas da área
logada, se a API protegida devolve 401 (e não 5xx), e se o feed do changelog tem
duplicata.

Termina em **APROVADO** ou lista o que falhou, e o código de saída é o número de
falhas. Use depois de todo deploy e sempre que suspeitar de algo — é mais rápido
que abrir cinco telas.

---

## 3. Entrar como Owner

**1.** `https://tribultz.com.br/login` com sua conta.
**2.** O item **Admin** aparece no rodapé do menu lateral. Ele só é exibido para
quem tem papel `superadmin` — e a autorização real acontece no backend, não na
interface: mesmo que alguém force a URL, o servidor recusa.

### O que cada tela do admin responde

| Tela | Pergunta que ela responde |
|---|---|
| **Visão geral** | como está o negócio agora: contas, volume, atividade |
| **Tenants** | quais empresas existem; ativar/desativar |
| **Parceiros** | rede de parceiros e atribuição comercial |
| **Founding Partners** | o Command Center: admitir empresa, conceder e revogar grant, encerrar |
| **Prospecção** | pipeline comercial direto e diagnósticos gerados |
| **Usuários** | quem tem acesso; ativar/desativar |
| **Uso & Operações** | consumo por conta — franquia, validações, API |
| **Saúde do sistema** | leitura do `/health/deep` dentro do produto |
| **Audit log** | **quem fez o quê** nas ações administrativas |

**Desativar usuário ou tenant tem efeito imediato.** O backend relê o usuário no
banco a cada requisição, então não há espera por expiração de sessão. É o
mecanismo mais rápido de contenção que você tem hoje.

### Admitir um Founding Partner

Em **Admin → Founding Partners**. Ao admitir, o sistema cria o tenant e o usuário
de login, com a **senha inicial que você define** — mínimo 8 caracteres — e já
marca o e-mail como verificado. Se você conceder o Grant no mesmo ato, ele vale
pelo período que você informar e concede o plano **Contador** (validação sem
limite, PDF, lote, painel, API, até 50 CNPJs).

Duas coisas a saber antes da primeira admissão, porque o cliente vai perceber:

- **O cliente não consegue trocar a própria senha dentro da plataforma** — não
  existe essa tela. Ele tem de sair e usar "Esqueci minha senha". Está explicado
  no manual do cliente.
- **Não existe tela para o cliente adicionar CNPJ.** O plano concede até 50
  vínculos e o endpoint existe no backend, mas sem interface — a inclusão passa
  por você.

Toda mutação no Command Center é auditada e aparece no **Audit log**. E há um
guardrail no código: o Command Center **nunca cria nem altera assinatura** —
Asaas segue sendo a única origem de assinatura paga, e o Grant é autorização
excepcional, por período.

---

## 4. Saúde da plataforma

### Automático

O workflow **monitor** roda a cada 5 minutos, consulta o `/health/deep` e, em
falha, envia alerta por e-mail para **mickel@tribultz.com.br**. Se o alerta
chegar, o primeiro passo é o comando da §2 — ele diz se é a plataforma inteira ou
um subsistema só.

### Manual

```bash
curl -s https://api.tribultz.com.br/health/deep | python3 -m json.tool
```

Leitura dos campos:

| Campo | O que significa cair |
|---|---|
| `db` | banco gerenciado inacessível — **crítico**, o produto para |
| `storage` | object storage fora — **crítico**, validação com evidência para |
| `redis` | fila de jobs degrada; validação simples segue |
| `email` | verificação de e-mail e recuperação de senha param |
| `asaas_api` | cobrança e webhook de pagamento degradam |
| `ai_engine` | sugestão de NCM para; validação determinística **não** depende disso |
| `hubspot` | integração comercial degrada |

`status` é `ok` só quando os críticos estão sadios **e** os opcionais estão `ok`
ou `unconfigured`. Latência normal hoje fica entre 700 ms e 1 s.

---

## 5. A VM, quando o problema é infraestrutura

```bash
ssh tribultz-vm
```

Comandos que resolvem a maioria das perguntas:

```bash
# containers: api, worker, beat, redis — todos devem estar Up/healthy
cd /opt/tribultz && sudo docker compose -f infra/docker-compose.prod.yml ps

# log da API (últimas linhas, ao vivo)
sudo docker compose -f infra/docker-compose.prod.yml logs -f --tail=100 api

# recursos
df -h / && free -m && uptime

# reinício pendente do sistema
test -f /var/run/reboot-required && cat /var/run/reboot-required
```

**Postgres e object storage não são containers** — são serviços gerenciados da
Magalu. Se o `db` cair no health, o problema não está na VM.

### Checagem de acesso

```bash
bash tools/check_access.sh
```

Confere SSH, `mgc`, `gh`, Vercel, drift do `.env.prod` e produção no ar. Falha em
SSH ou `mgc` significa que você perdeu acesso operacional — trate primeiro.

### Backup do banco

Snapshot automático diário do DBaaS, às 02:00 UTC, retenção de 7 dias:

```bash
mgc dbaas snapshots instances-snapshots list \
  --instance-id=87ae9966-6664-41c4-815f-adc90004f41a --type=AUTOMATED -o json
```

O `mgc` imprime barra de progresso com escape de terminal no meio do JSON; se
for processar a saída, limpe antes. **Cuidado:** `mgc auth tenant current`
imprime token em texto puro — não rode isso com a tela compartilhada.

O runbook completo de restore está em `docs/infra/operations_runbook.md`. A
restauração cria **instância nova** — a Magalu não sobrescreve a existente.

---

## 6. O que foi entregue

```bash
gh run list --workflow=deploy-prod.yml --limit 5
gh pr list --state merged --limit 10
```

Para confirmar que produção está no mesmo commit que `main`:

```bash
git rev-parse HEAD
ssh tribultz-vm 'git -C /opt/tribultz rev-parse HEAD'
```

Divergência aqui significa deploy que não completou, e é a primeira coisa a
checar quando "a correção subiu mas o problema continua".

Merge em `main` que toca `backend/**` ou `infra/**` dispara deploy automático,
com rollback automático em falha. Frontend vai por Vercel, em trilha separada.

---

## 7. Feed público do changelog

```bash
curl -s https://api.tribultz.com.br/api/v1/news | python3 -m json.tool | head -40
```

Duas coisas a saber, porque custaram correção esta semana:

- **`DELETE` no banco não resolve.** Cinco entradas de catálogo são repostas pelo
  seed a cada subida da aplicação. Curadoria passa pelo arquivo de seed ou pelo
  endpoint de publicação.
- **Publicação exige declaração explícita.** Um PR só publica se tiver a seção
  `## Changelog público` com linha `Título:`. Sem isso, nada sai — e há denylist
  de vocabulário interno mais checagem estrutural que abortam publicação suspeita.

---

## 8. Ordem de investigação quando algo parece errado

1. `bash tools/posdeploy_check.sh` — separa "plataforma fora" de "comportamento errado"
2. Se subsistema caiu → §4 para identificar qual, §5 se for infraestrutura
3. Se as rotas respondem mas o comportamento está errado → **Audit log** (quem mexeu) e log da API (o que aconteceu)
4. Se começou depois de um deploy → §6 para comparar commits e ler o run do deploy
5. Se é conta específica → **Admin → Usuários / Uso & Operações** para ver plano efetivo e franquia

---

## 9. Onde estão os limites do que você consegue ver

Honestidade sobre o instrumental, porque monitorar acreditando ter visibilidade
que não existe é pior que saber que não tem:

| Lacuna | Consequência prática |
|---|---|
| **Sem ambiente de ensaio** | mudança de autorização vai de local a produção, com o CI como único intermediário |
| **Audit log cobre ação administrativa, não ação de usuário** | não há trilha de "usuário X baixou documento Y" |
| **Sem alerta sobre evento de autorização** | o monitor cobre disponibilidade; tentativa de acesso indevido não gera alerta |
| **Sem retenção de log declarada** | log de aplicação vive no stdout do container; não há política conhecida |
| **Rate limiter cai para memória sem Redis** | o teto passa a ser por processo, silenciosamente |
| **`bloqueado-por-evidencia`** | issues com esse label não são fila — estão esperando documento externo, não trabalho |

O levantamento completo está em `docs/SEC-TECH-BASELINE-v1.md`, seção 13, com 17
lacunas e a razão de cada uma não estar demonstrada. **Esse arquivo ainda está no
PR #666, não em `main`** — se você buscar no repositório e não achar, é por isso.

---

## Referência rápida

| | |
|---|---|
| Painel admin | https://tribultz.com.br/admin |
| Saúde da API | https://api.tribultz.com.br/health/deep |
| Feed do changelog | https://api.tribultz.com.br/api/v1/news |
| Verificação completa | `bash tools/posdeploy_check.sh` |
| Acesso operacional | `bash tools/check_access.sh` |
| VM | `ssh tribultz-vm` |
| Runbook de infra | `docs/infra/operations_runbook.md` |
| Baseline de segurança | `docs/SEC-TECH-BASELINE-v1.md` (PR #666, ainda não em `main`) |
| Segredos (onde vivem, sem valores) | `docs/infra/secrets_inventory.md` |
