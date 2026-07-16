# Programa de Parceiros — Fundação de Autenticação

Data: 2026-07-16
PR: [#459](https://github.com/mickbap/tribultz/pull/459) — aberto, aguardando review
Governança: [RFC-0026](https://github.com/mickbap/tribultz-brain/blob/main/knowledge/rfcs/RFC-0026-programa-de-parceiros.md) (`tribultz-brain`)

## Resumo executivo

Primeira entrega de código do Programa de Parceiros: a plataforma agora sabe autenticar um **parceiro** (ex.: Dra. Kátia Pollon) como ator próprio, sem confundi-lo com uma empresa-cliente (Tenant) e sem exigir uma tela nova de login separada. É a base sobre a qual o cadastro do parceiro, o dashboard dele e a extensão do Command Center serão construídos nas próximas etapas — nenhum desses três ainda existe.

**Nenhuma informação financeira, comissão ou pagamento foi implementada.** Fora de escopo por decisão explícita, conforme RFC-0026.

> **Leitura oficial deste PR:** não é só a documentação de uma feature do Programa de Parceiros — é uma evolução da arquitetura de autenticação da Tribultz, com validade permanente para qualquer ator futuro.

## Decisão arquitetural consolidada

> A autenticação da Tribultz autentica identidades.
> A autorização define contexto e permissões.
> Novos domínios reutilizam a mesma infraestrutura de autenticação.

Este passa a ser o princípio oficial para toda evolução futura da autenticação da plataforma — não um detalhe de implementação do Programa de Parceiros.

## Benefícios obtidos

- Eliminação do Tenant artificial (a primeira proposta previa criar uma "empresa" fictícia só para o parceiro logar — descartada).
- Reutilização integral da infraestrutura de autenticação existente — nenhum sistema paralelo.
- Compatibilidade total com os usuários e tenants atuais — zero regressão (677/677 testes).
- Base preparada para novos atores institucionais futuros, sem necessidade de redesenho.
- Redução de dívida técnica futura: a próxima vez que a plataforma precisar de um novo tipo de ator, o modelo já existe.

## O que NÃO muda (para evitar interpretação futura equivocada)

Permanecem **inalterados**: fluxo de login, convite, primeiro acesso, OTP, recuperação de senha, auditoria, sessão, usuários atuais, tenants atuais. Esta entrega **estende** a autenticação para um novo domínio de ator — não **substitui** nem **modifica** o comportamento existente para quem já usa a plataforma hoje.

## O que muda, na prática

Hoje, todo login na Tribultz assume implicitamente "isso é alguém de uma empresa cliente". Essa entrega generaliza esse conceito: o sistema de login passa a reconhecer **dois tipos de ator** — quem é de uma empresa (como sempre foi) e quem é um parceiro (novo). Um parceiro poderá usar exatamente o mesmo fluxo de convite, criação de senha e login que qualquer outro usuário já usa hoje — não é um sistema paralelo, é o mesmo sistema reconhecendo um novo tipo de conta.

Guardrail preservado: um Partner **nunca** vira uma empresa-cliente, e vice-versa. O banco de dados agora **impede estruturalmente** que essa distinção seja violada por acidente (não é só uma regra de código, é uma restrição no próprio banco).

## Validação

- 14 testes novos, cobrindo: o parceiro conseguindo logar sem quebrar nada; um parceiro não conseguindo acessar áreas de empresa-cliente (e vice-versa); a restrição do banco funcionando.
- Suite completa do backend: **677 de 677 testes passando** — ou seja, nada que já existia foi afetado.
- Um problema real foi encontrado e corrigido **durante** a implementação (não estava previsto na proposta técnica original): três endpoints antigos chamavam uma função interna de um jeito que quebraria com essa mudança. A ferramenta de checagem de tipos (pyright) pegou isso antes de virar bug em produção; foi corrigido no mesmo PR.

## Escopo delimitado — este PR NÃO implementa

- Cadastro operacional do parceiro (convite, criação de conta de verdade).
- Dashboard do parceiro.
- Comissão.
- Carteira financeira.
- Pagamentos.
- Relatórios comerciais.
- Command Center expandido (visão de parceiros/indicações).

Todos pertencem às próximas etapas do Programa de Parceiros — nenhum está bloqueado por esta entrega, mas nenhum está pronto ainda.

## Decisão de processo que vale registrar

Esta entrega passou por duas rodadas de revisão arquitetural antes de virar código:
1. Primeira proposta previa criar uma "empresa" fictícia no banco só para o parceiro poder logar — foi corretamente barrada por misturar dois conceitos que deveriam ficar separados.
2. Segunda proposta generalizava a solução, mas ainda tratava "tenant" como o conceito central — foi refinada para que o **ator autenticado** (seja ele qual for) vire o conceito central, e "empresa" passe a ser só um contexto usado quando aplicável.

O modelo que entrou em código é o da segunda rodada — pensado para caber o próximo tipo de ator que a Tribultz precisar (ex.: parceiros institucionais maiores) sem precisar redesenhar de novo.

## Próximo passo

PR #459 aguardando review antes do merge. Após aprovado, sigo para o fluxo de criação de conta do parceiro (Etapa seguinte da Fase 1).
