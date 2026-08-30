# Decisão — Integração Attio: backend custom é o caminho oficial de automação

> **SUPERADA em 29/08/2026 (ROUND 18-A).** O Attio deixou de fazer parte da
> arquitetura operacional da Tribultz: o cockpit comercial passou para o Excel
> mantido pelo Economista e o Rumy segue como origem da prospecção. Router,
> webhook, `app/integrations/attio/` e as variáveis `ATTIO_*` foram removidos.
> O documento fica como registro do que foi decidido e por quê — não descreve
> mais o sistema atual.

> Registrada em 12/08/2026 por ordem do Round 2 (Ermes — Produto/Vendas), seção 1.
> Decisão de arquitetura **FECHADA**. Contexto do programa: PO-2026-07-CRM-001.

## Decisão

Para o fluxo operacional do Programa Comercial (handoff Rumy → Attio):

- **Backend custom** (`backend/app/integrations/attio/` — cliente HTTP próprio, fatias
  da PO-2026-07-CRM-001) é o **caminho oficial de integração automática** com o Attio.
- O **MCP oficial do Attio** (`.mcp.json` → `https://mcp.attio.com/mcp`, PR #572)
  continua existindo para **operações assistidas/interativas** (consulta e apoio via
  agente com sessão humana), mas **não é mecanismo de automação** do handoff.

**Motivo funcional**: o handoff precisa ocorrer **por evento**, sem depender de uma
sessão humana autenticada. O MCP pressupõe sessão interativa autenticada por usuário
(OAuth); automação orientada a evento exige credencial de serviço e código versionado,
testável e auditável — o backend custom.

## Tratamento da proposta de revert

- **PR #571** ("revert(crm): remove integração backend do Attio, adota MCP oficial")
  permanece **fechado sem merge**, como registro histórico da alternativa avaliada. A
  parte que valia por conta própria (o MCP para uso assistido) foi extraída e mergeada
  no PR #572.
- A branch remota **`revert/attio-backend-integration`** fica obsoleta com esta
  decisão. **Recomendação**: excluí-la após o aceite do Round 2 (o conteúdo permanece
  preservado no PR #571 fechado). A exclusão **não foi executada** no Round 2, que
  veda remoção de código.

## Registro canônico

O ADR canônico desta decisão deve entrar no Brain (`knowledge/decisions/`) pelo gate
de entrada vigente; este arquivo é o registro operacional no repositório do produto.
Pendência conhecida: clone local do Brain desatualizado nesta máquina (apontada no
parecer QA do Round 1, bloqueio B-8).
