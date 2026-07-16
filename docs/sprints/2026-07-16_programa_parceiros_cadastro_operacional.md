# Programa de Parceiros — Cadastro Operacional (em produção)

Data: 2026-07-16
PR: [#460](https://github.com/mickbap/tribultz/pull/460) — mergeado
Governança: [ADR-0011](https://github.com/mickbap/tribultz-brain/blob/main/knowledge/decisions/2026-07-16-autenticacao-por-ator-identidade-vs-contexto.md) · [RFC-0026](https://github.com/mickbap/tribultz-brain/blob/main/knowledge/rfcs/RFC-0026-programa-de-parceiros.md) (`tribultz-brain`)

## Resumo executivo

Segunda entrega do Programa de Parceiros, sobre a fundação de autenticação do PR #459: o Owner já consegue, pelo admin, dar a um parceiro (ex.: Dra. Kátia Pollon) uma conta de login de verdade. **Já está em produção e verificado.**

Ainda **não existe**: tela para o Owner fazer isso pela interface (hoje é uma chamada de API), dashboard do parceiro, nem nada de comissão/financeiro.

## O que foi ao ar

Um novo endpoint (`POST /partners/{id}/account`) que cria a conta de login de um parceiro já cadastrado. O parceiro criado assim consegue logar pelo mesmo `/login` que qualquer outro usuário da plataforma usa — validado com um teste que faz esse login de verdade contra o fluxo real.

**Achado que mudou a forma de construir isso:** os documentos do Brain descreviam um fluxo de "convite por e-mail → código → senha" para novos usuários. Ao investigar o código real, esse fluxo **nunca foi construído** — o que existe de fato é mais simples: o Owner define uma senha inicial na hora de criar a conta. Construímos o cadastro do parceiro espelhando o que **existe de verdade**, não o que a documentação descrevia (a documentação foi corrigida à parte, isso não bloqueou a entrega).

## Guardrails aplicados

- Só um parceiro **ativo** pode ganhar conta.
- Um parceiro tem no máximo **uma** conta (evita duplicidade).
- O e-mail da conta precisa ser único **em toda a plataforma**, não só entre parceiros — sem essa checagem, duas contas com o mesmo e-mail quebrariam o login de ambas (achado técnico real, coberto por teste).
- Toda criação de conta fica registrada na auditoria.
- Nenhum dado financeiro envolvido, como já vinha sendo seguido nas entregas anteriores.

## Validação e pós-deploy

- 11 testes novos (o cenário de sucesso, os 4 bloqueios acima, e o login ponta a ponta); suite completa do backend: **683 de 683**.
- Deploy automático rodou ao mesclar o PR — verificado depois, não presumido:
  - Produção no commit do merge (`e602117`).
  - `/health/deep`: todos os serviços `ok`.
  - Containers todos de pé e saudáveis.
  - O endpoint novo responde `401` (exige login) em produção — confirma que subiu corretamente, sem testar com dado real.

## Escopo — o que ainda falta na Fase 1

1. **Tela no admin** para o Owner criar a conta do parceiro (hoje só existe a API).
2. **Dashboard do parceiro** — onde ele vê código, link e empresas indicadas.
3. **Extensão do Command Center** — visão consolidada de todos os parceiros para o Owner.

## Próximo passo

Aguardando direção sobre qual dos três itens acima entra primeiro.
